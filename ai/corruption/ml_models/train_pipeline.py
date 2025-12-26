"""
End-to-End Training Pipeline for Corruption Detection Models

This module provides a complete training pipeline that:
1. Extracts data from the database
2. Computes features using the feature extractor
3. Splits data (train/validation/test) with stratification
4. Trains multiple models (RF, XGBoost, NN, Anomaly)
5. Evaluates and logs metrics via MLflow
6. Saves best models
7. Generates comprehensive training report

Usage:
    python train_pipeline.py --limit 50000 --output-dir ./models

Author: NabavkiData
License: Proprietary
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import pickle

import numpy as np
import asyncpg
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import classification_report

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from ai.corruption.features.feature_extractor import FeatureExtractor, FeatureVector
from ai.corruption.ml_models.tracking import (
    CorruptionMLflowTracker, TrainingConfig, ModelMetrics,
    calculate_metrics, get_tracker
)

logger = logging.getLogger(__name__)


@dataclass
class TrainingData:
    """Container for training data splits."""
    X_train: np.ndarray
    X_val: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_val: np.ndarray
    y_test: np.ndarray
    tender_ids_train: List[str]
    tender_ids_val: List[str]
    tender_ids_test: List[str]
    feature_names: List[str]
    scaler: StandardScaler


@dataclass
class TrainingResult:
    """Result from training a single model."""
    model_name: str
    model_type: str
    model: Any
    train_metrics: ModelMetrics
    val_metrics: ModelMetrics
    test_metrics: ModelMetrics
    feature_importance: Optional[Dict[str, float]] = None
    training_time_seconds: float = 0.0
    hyperparameters: Dict[str, Any] = None


class CorruptionTrainingPipeline:
    """
    End-to-end training pipeline for corruption detection.

    Handles all aspects of model training:
    - Data extraction and preparation
    - Feature engineering
    - Model training (multiple algorithms)
    - Evaluation and metric logging
    - Model persistence
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        output_dir: str = "./models",
        random_seed: int = 42
    ):
        """
        Initialize the training pipeline.

        Args:
            db_url: PostgreSQL connection URL
            output_dir: Directory to save trained models
            random_seed: Random seed for reproducibility
        """
        self.db_url = db_url or os.environ.get(
            'DATABASE_URL',
            'postgresql://postgres:password@localhost:5432/nabavkidata'
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.random_seed = random_seed

        self.pool: Optional[asyncpg.Pool] = None
        self.tracker: Optional[CorruptionMLflowTracker] = None
        self.feature_extractor: Optional[FeatureExtractor] = None

        np.random.seed(random_seed)

        logger.info(f"Training pipeline initialized. Output: {self.output_dir}")

    async def initialize(self):
        """Initialize database connection and MLflow tracker."""
        # Parse connection URL
        if self.db_url.startswith('postgresql://'):
            dsn = self.db_url
        else:
            dsn = self.db_url

        self.pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=2,
            max_size=10,
            command_timeout=300
        )

        self.feature_extractor = FeatureExtractor(self.pool)
        self.tracker = get_tracker()

        logger.info("Pipeline initialized with database and MLflow connection")

    async def cleanup(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()

    async def extract_training_data(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_bidders: int = 0
    ) -> Tuple[List[FeatureVector], np.ndarray]:
        """
        Extract and prepare training data from database.

        We use several heuristics for pseudo-labeling since we don't have
        verified corruption labels:
        - High-risk based on corruption_flags table
        - Known patterns (single bidder + repeat winner + high value)

        Args:
            limit: Maximum number of samples
            start_date: Filter tenders from this date
            end_date: Filter tenders until this date
            min_bidders: Minimum number of bidders required

        Returns:
            Tuple of (feature vectors, labels)
        """
        logger.info("Extracting training data from database...")

        # Build query for awarded tenders with risk information
        query = """
            WITH tender_risk AS (
                SELECT
                    t.tender_id,
                    COALESCE(trs.risk_score, 0) as risk_score,
                    COALESCE(trs.flag_count, 0) as flag_count,
                    CASE
                        -- High risk: flag count >= 3 or risk_score >= 70
                        WHEN COALESCE(trs.flag_count, 0) >= 3 THEN 1
                        WHEN COALESCE(trs.risk_score, 0) >= 70 THEN 1
                        -- Suspicious patterns (pseudo-labels)
                        WHEN t.num_bidders = 1
                             AND EXISTS (
                                SELECT 1 FROM tenders t2
                                WHERE t2.winner = t.winner
                                  AND t2.procuring_entity = t.procuring_entity
                                  AND t2.publication_date < t.publication_date
                                  AND t2.publication_date >= t.publication_date - INTERVAL '12 months'
                                GROUP BY t2.winner
                                HAVING COUNT(*) >= 5
                             ) THEN 1
                        -- Clean: low risk and verified
                        WHEN COALESCE(trs.risk_score, 0) <= 20
                             AND COALESCE(trs.flag_count, 0) = 0 THEN 0
                        -- Unknown: somewhere in between (will be excluded)
                        ELSE -1
                    END as label
                FROM tenders t
                LEFT JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
                WHERE t.status IN ('awarded', 'completed', 'closed')
                  AND t.winner IS NOT NULL
        """

        conditions = []
        params = []
        param_idx = 1

        if start_date:
            conditions.append(f"t.publication_date >= ${param_idx}")
            params.append(start_date)
            param_idx += 1

        if end_date:
            conditions.append(f"t.publication_date <= ${param_idx}")
            params.append(end_date)
            param_idx += 1

        if min_bidders > 0:
            conditions.append(f"t.num_bidders >= ${param_idx}")
            params.append(min_bidders)
            param_idx += 1

        if conditions:
            query += " AND " + " AND ".join(conditions)

        query += """
            )
            SELECT tender_id, risk_score, flag_count, label
            FROM tender_risk
            WHERE label IN (0, 1)  -- Exclude unknown
            ORDER BY
                -- Balance classes by sampling
                label,
                RANDOM()
        """

        if limit:
            query += f" LIMIT {limit}"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        logger.info(f"Found {len(rows)} tenders with labels")

        # Count class distribution
        labels = [row['label'] for row in rows]
        positive = sum(labels)
        negative = len(labels) - positive
        logger.info(f"Class distribution: {negative} clean, {positive} suspicious")

        # Extract features for each tender
        tender_ids = [row['tender_id'] for row in rows]
        feature_vectors = await self.feature_extractor.extract_features_batch(tender_ids)

        # Create label array matching successful extractions
        successful_ids = {fv.tender_id for fv in feature_vectors}
        labels_array = np.array([
            row['label'] for row in rows
            if row['tender_id'] in successful_ids
        ], dtype=np.float32)

        logger.info(f"Extracted features for {len(feature_vectors)} tenders")

        return feature_vectors, labels_array

    def prepare_data_splits(
        self,
        feature_vectors: List[FeatureVector],
        labels: np.ndarray,
        test_size: float = 0.15,
        val_size: float = 0.15
    ) -> TrainingData:
        """
        Prepare stratified train/validation/test splits.

        Args:
            feature_vectors: List of extracted features
            labels: Label array
            test_size: Proportion for test set
            val_size: Proportion for validation set

        Returns:
            TrainingData object with splits
        """
        logger.info("Preparing data splits...")

        # Convert to numpy arrays
        X = np.stack([fv.feature_array for fv in feature_vectors])
        tender_ids = [fv.tender_id for fv in feature_vectors]
        feature_names = feature_vectors[0].feature_names

        # Replace NaN and Inf with 0
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # First split: train+val vs test
        X_trainval, X_test, y_trainval, y_test, ids_trainval, ids_test = train_test_split(
            X, labels, tender_ids,
            test_size=test_size,
            stratify=labels,
            random_state=self.random_seed
        )

        # Second split: train vs val
        val_proportion = val_size / (1 - test_size)
        X_train, X_val, y_train, y_val, ids_train, ids_val = train_test_split(
            X_trainval, y_trainval, ids_trainval,
            test_size=val_proportion,
            stratify=y_trainval,
            random_state=self.random_seed
        )

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        X_test_scaled = scaler.transform(X_test)

        logger.info(f"Data splits: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")
        logger.info(f"Train class balance: {y_train.sum()}/{len(y_train)} ({100*y_train.mean():.1f}% positive)")

        return TrainingData(
            X_train=X_train_scaled,
            X_val=X_val_scaled,
            X_test=X_test_scaled,
            y_train=y_train,
            y_val=y_val,
            y_test=y_test,
            tender_ids_train=ids_train,
            tender_ids_val=ids_val,
            tender_ids_test=ids_test,
            feature_names=feature_names,
            scaler=scaler
        )

    def train_random_forest(
        self,
        data: TrainingData,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> TrainingResult:
        """
        Train a Random Forest classifier.

        Args:
            data: TrainingData object
            hyperparameters: Optional hyperparameters override

        Returns:
            TrainingResult with trained model and metrics
        """
        logger.info("Training Random Forest...")
        start_time = datetime.utcnow()

        # Default hyperparameters
        params = {
            'n_estimators': 200,
            'max_depth': 20,
            'min_samples_split': 5,
            'min_samples_leaf': 2,
            'max_features': 'sqrt',
            'class_weight': 'balanced',
            'n_jobs': -1,
            'random_state': self.random_seed
        }
        if hyperparameters:
            params.update(hyperparameters)

        model = RandomForestClassifier(**params)
        model.fit(data.X_train, data.y_train)

        # Predictions
        train_pred = model.predict(data.X_train)
        train_proba = model.predict_proba(data.X_train)[:, 1]
        val_pred = model.predict(data.X_val)
        val_proba = model.predict_proba(data.X_val)[:, 1]
        test_pred = model.predict(data.X_test)
        test_proba = model.predict_proba(data.X_test)[:, 1]

        # Metrics
        train_metrics = calculate_metrics(data.y_train, train_pred, train_proba)
        val_metrics = calculate_metrics(data.y_val, val_pred, val_proba)
        test_metrics = calculate_metrics(data.y_test, test_pred, test_proba)

        # Feature importance
        importance = dict(zip(data.feature_names, model.feature_importances_))

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Random Forest trained in {elapsed:.1f}s. Val F1: {val_metrics.f1:.3f}")

        return TrainingResult(
            model_name="random_forest",
            model_type="random_forest",
            model=model,
            train_metrics=train_metrics,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            feature_importance=importance,
            training_time_seconds=elapsed,
            hyperparameters=params
        )

    def train_xgboost(
        self,
        data: TrainingData,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> TrainingResult:
        """
        Train an XGBoost classifier.

        Args:
            data: TrainingData object
            hyperparameters: Optional hyperparameters override

        Returns:
            TrainingResult with trained model and metrics
        """
        try:
            import xgboost as xgb
        except ImportError:
            logger.warning("XGBoost not installed, skipping")
            return None

        logger.info("Training XGBoost...")
        start_time = datetime.utcnow()

        # Calculate scale_pos_weight for class imbalance
        neg_count = (data.y_train == 0).sum()
        pos_count = (data.y_train == 1).sum()
        scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0

        # Default hyperparameters
        params = {
            'n_estimators': 300,
            'max_depth': 8,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'min_child_weight': 3,
            'gamma': 0.1,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'scale_pos_weight': scale_pos_weight,
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'use_label_encoder': False,
            'random_state': self.random_seed,
            'n_jobs': -1
        }
        if hyperparameters:
            params.update(hyperparameters)

        model = xgb.XGBClassifier(**params)

        # Train with early stopping
        model.fit(
            data.X_train, data.y_train,
            eval_set=[(data.X_val, data.y_val)],
            verbose=False
        )

        # Predictions
        train_pred = model.predict(data.X_train)
        train_proba = model.predict_proba(data.X_train)[:, 1]
        val_pred = model.predict(data.X_val)
        val_proba = model.predict_proba(data.X_val)[:, 1]
        test_pred = model.predict(data.X_test)
        test_proba = model.predict_proba(data.X_test)[:, 1]

        # Metrics
        train_metrics = calculate_metrics(data.y_train, train_pred, train_proba)
        val_metrics = calculate_metrics(data.y_val, val_pred, val_proba)
        test_metrics = calculate_metrics(data.y_test, test_pred, test_proba)

        # Feature importance
        importance = dict(zip(data.feature_names, model.feature_importances_))

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"XGBoost trained in {elapsed:.1f}s. Val F1: {val_metrics.f1:.3f}")

        return TrainingResult(
            model_name="xgboost",
            model_type="xgboost",
            model=model,
            train_metrics=train_metrics,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            feature_importance=importance,
            training_time_seconds=elapsed,
            hyperparameters=params
        )

    def train_neural_network(
        self,
        data: TrainingData,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> TrainingResult:
        """
        Train a Neural Network classifier.

        Args:
            data: TrainingData object
            hyperparameters: Optional hyperparameters override

        Returns:
            TrainingResult with trained model and metrics
        """
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from torch.utils.data import DataLoader, TensorDataset
        except ImportError:
            logger.warning("PyTorch not installed, skipping neural network")
            return None

        logger.info("Training Neural Network...")
        start_time = datetime.utcnow()

        # Default hyperparameters
        params = {
            'hidden_layers': [128, 64, 32],
            'dropout': 0.3,
            'learning_rate': 0.001,
            'batch_size': 64,
            'epochs': 100,
            'early_stopping_patience': 10
        }
        if hyperparameters:
            params.update(hyperparameters)

        # Define network architecture
        class CorruptionNN(nn.Module):
            def __init__(self, input_dim, hidden_layers, dropout):
                super().__init__()
                layers = []
                prev_dim = input_dim

                for hidden_dim in hidden_layers:
                    layers.extend([
                        nn.Linear(prev_dim, hidden_dim),
                        nn.BatchNorm1d(hidden_dim),
                        nn.ReLU(),
                        nn.Dropout(dropout)
                    ])
                    prev_dim = hidden_dim

                layers.append(nn.Linear(prev_dim, 1))
                layers.append(nn.Sigmoid())

                self.network = nn.Sequential(*layers)

            def forward(self, x):
                return self.network(x)

        # Prepare data
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        X_train_t = torch.FloatTensor(data.X_train).to(device)
        y_train_t = torch.FloatTensor(data.y_train).reshape(-1, 1).to(device)
        X_val_t = torch.FloatTensor(data.X_val).to(device)
        y_val_t = torch.FloatTensor(data.y_val).reshape(-1, 1).to(device)
        X_test_t = torch.FloatTensor(data.X_test).to(device)

        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(train_dataset, batch_size=params['batch_size'], shuffle=True)

        # Create model
        model = CorruptionNN(
            input_dim=data.X_train.shape[1],
            hidden_layers=params['hidden_layers'],
            dropout=params['dropout']
        ).to(device)

        # Class weight for imbalanced data
        pos_weight = torch.tensor([
            (data.y_train == 0).sum() / max((data.y_train == 1).sum(), 1)
        ]).to(device)

        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        optimizer = optim.Adam(model.parameters(), lr=params['learning_rate'])
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        # Training loop with early stopping
        best_val_loss = float('inf')
        patience_counter = 0
        best_model_state = None

        for epoch in range(params['epochs']):
            model.train()
            train_loss = 0.0

            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            # Validation
            model.eval()
            with torch.no_grad():
                val_outputs = model(X_val_t)
                val_loss = criterion(val_outputs, y_val_t).item()

            scheduler.step(val_loss)

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                best_model_state = model.state_dict().copy()
            else:
                patience_counter += 1
                if patience_counter >= params['early_stopping_patience']:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break

        # Load best model
        if best_model_state:
            model.load_state_dict(best_model_state)

        # Predictions
        model.eval()
        with torch.no_grad():
            train_proba = model(X_train_t).cpu().numpy().flatten()
            val_proba = model(X_val_t).cpu().numpy().flatten()
            test_proba = model(X_test_t).cpu().numpy().flatten()

        train_pred = (train_proba >= 0.5).astype(int)
        val_pred = (val_proba >= 0.5).astype(int)
        test_pred = (test_proba >= 0.5).astype(int)

        # Metrics
        train_metrics = calculate_metrics(data.y_train, train_pred, train_proba)
        val_metrics = calculate_metrics(data.y_val, val_pred, val_proba)
        test_metrics = calculate_metrics(data.y_test, test_pred, test_proba)

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Neural Network trained in {elapsed:.1f}s. Val F1: {val_metrics.f1:.3f}")

        return TrainingResult(
            model_name="neural_network",
            model_type="neural_network",
            model=model,
            train_metrics=train_metrics,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            feature_importance=None,  # NN doesn't have built-in feature importance
            training_time_seconds=elapsed,
            hyperparameters=params
        )

    def train_anomaly_detector(
        self,
        data: TrainingData,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> TrainingResult:
        """
        Train an Isolation Forest anomaly detector.

        Uses unsupervised learning - trained only on clean data,
        then detects anomalies (potential corruption).

        Args:
            data: TrainingData object
            hyperparameters: Optional hyperparameters override

        Returns:
            TrainingResult with trained model and metrics
        """
        logger.info("Training Anomaly Detector (Isolation Forest)...")
        start_time = datetime.utcnow()

        # Default hyperparameters
        params = {
            'n_estimators': 200,
            'max_samples': 'auto',
            'contamination': 0.1,
            'max_features': 0.8,
            'bootstrap': False,
            'random_state': self.random_seed,
            'n_jobs': -1
        }
        if hyperparameters:
            params.update(hyperparameters)

        # Train only on clean samples (semi-supervised approach)
        clean_mask = data.y_train == 0
        X_clean = data.X_train[clean_mask]

        model = IsolationForest(**params)
        model.fit(X_clean)

        # Predict (anomaly = -1, normal = 1)
        def predict_and_score(X):
            raw_scores = model.decision_function(X)
            # Convert to probability-like scores (0-1, higher = more anomalous)
            scores = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-10)
            predictions = (model.predict(X) == -1).astype(int)  # -1 = anomaly = 1
            return predictions, scores

        train_pred, train_proba = predict_and_score(data.X_train)
        val_pred, val_proba = predict_and_score(data.X_val)
        test_pred, test_proba = predict_and_score(data.X_test)

        # Metrics
        train_metrics = calculate_metrics(data.y_train, train_pred, train_proba)
        val_metrics = calculate_metrics(data.y_val, val_pred, val_proba)
        test_metrics = calculate_metrics(data.y_test, test_pred, test_proba)

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Anomaly Detector trained in {elapsed:.1f}s. Val F1: {val_metrics.f1:.3f}")

        return TrainingResult(
            model_name="anomaly_detector",
            model_type="isolation_forest",
            model=model,
            train_metrics=train_metrics,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            feature_importance=None,
            training_time_seconds=elapsed,
            hyperparameters=params
        )

    def train_ensemble(
        self,
        data: TrainingData,
        base_models: List[TrainingResult]
    ) -> TrainingResult:
        """
        Train an ensemble combining predictions from base models.

        Uses a meta-learner (logistic regression) on base model predictions.

        Args:
            data: TrainingData object
            base_models: List of trained base models

        Returns:
            TrainingResult with ensemble model and metrics
        """
        from sklearn.linear_model import LogisticRegression

        logger.info("Training Ensemble...")
        start_time = datetime.utcnow()

        # Get predictions from each base model
        def get_predictions(model_result, X):
            model = model_result.model
            model_type = model_result.model_type

            if model_type == 'neural_network':
                import torch
                model.eval()
                with torch.no_grad():
                    device = next(model.parameters()).device
                    X_t = torch.FloatTensor(X).to(device)
                    proba = model(X_t).cpu().numpy().flatten()
            elif model_type == 'isolation_forest':
                raw_scores = model.decision_function(X)
                proba = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-10)
            else:
                proba = model.predict_proba(X)[:, 1]

            return proba

        # Stack predictions
        train_preds = np.column_stack([
            get_predictions(m, data.X_train) for m in base_models
        ])
        val_preds = np.column_stack([
            get_predictions(m, data.X_val) for m in base_models
        ])
        test_preds = np.column_stack([
            get_predictions(m, data.X_test) for m in base_models
        ])

        # Meta-learner
        meta_model = LogisticRegression(
            class_weight='balanced',
            random_state=self.random_seed,
            max_iter=1000
        )
        meta_model.fit(train_preds, data.y_train)

        # Ensemble predictions
        train_pred = meta_model.predict(train_preds)
        train_proba = meta_model.predict_proba(train_preds)[:, 1]
        val_pred = meta_model.predict(val_preds)
        val_proba = meta_model.predict_proba(val_preds)[:, 1]
        test_pred = meta_model.predict(test_preds)
        test_proba = meta_model.predict_proba(test_preds)[:, 1]

        # Metrics
        train_metrics = calculate_metrics(data.y_train, train_pred, train_proba)
        val_metrics = calculate_metrics(data.y_val, val_pred, val_proba)
        test_metrics = calculate_metrics(data.y_test, test_pred, test_proba)

        # Create ensemble wrapper
        ensemble = {
            'meta_model': meta_model,
            'base_models': [m.model for m in base_models],
            'base_model_types': [m.model_type for m in base_models]
        }

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Ensemble trained in {elapsed:.1f}s. Val F1: {val_metrics.f1:.3f}")

        return TrainingResult(
            model_name="ensemble",
            model_type="ensemble",
            model=ensemble,
            train_metrics=train_metrics,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            feature_importance=None,
            training_time_seconds=elapsed,
            hyperparameters={'base_models': [m.model_name for m in base_models]}
        )

    async def run_training(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        models_to_train: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run the complete training pipeline.

        Args:
            limit: Maximum samples to use
            start_date: Filter start date
            end_date: Filter end date
            models_to_train: List of models to train (default: all)

        Returns:
            Training report dictionary
        """
        if models_to_train is None:
            models_to_train = ['random_forest', 'xgboost', 'neural_network', 'anomaly', 'ensemble']

        logger.info("=" * 60)
        logger.info("Starting Corruption Detection Training Pipeline")
        logger.info("=" * 60)

        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'parameters': {
                'limit': limit,
                'start_date': start_date,
                'end_date': end_date,
                'models': models_to_train
            },
            'results': {}
        }

        try:
            # 1. Extract data
            feature_vectors, labels = await self.extract_training_data(
                limit=limit,
                start_date=start_date,
                end_date=end_date
            )

            if len(feature_vectors) < 100:
                raise ValueError(f"Insufficient training data: {len(feature_vectors)} samples")

            # 2. Prepare splits
            data = self.prepare_data_splits(feature_vectors, labels)

            report['data_summary'] = {
                'total_samples': len(feature_vectors),
                'train_samples': len(data.y_train),
                'val_samples': len(data.y_val),
                'test_samples': len(data.y_test),
                'feature_count': len(data.feature_names),
                'positive_rate': float(labels.mean())
            }

            # 3. Train models
            trained_models = []

            for model_name in models_to_train:
                if model_name == 'ensemble':
                    continue  # Train ensemble last

                # Start MLflow run
                config = TrainingConfig(
                    model_type=model_name,
                    hyperparameters={},
                    feature_count=len(data.feature_names),
                    training_samples=len(data.y_train),
                    validation_samples=len(data.y_val),
                    test_samples=len(data.y_test),
                    data_start_date=start_date,
                    data_end_date=end_date
                )

                self.tracker.start_run(
                    run_name=f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M')}",
                    config=config,
                    tags={'pipeline': 'full_training'}
                )

                try:
                    if model_name == 'random_forest':
                        result = self.train_random_forest(data)
                    elif model_name == 'xgboost':
                        result = self.train_xgboost(data)
                    elif model_name == 'neural_network':
                        result = self.train_neural_network(data)
                    elif model_name == 'anomaly':
                        result = self.train_anomaly_detector(data)
                    else:
                        logger.warning(f"Unknown model: {model_name}")
                        self.tracker.end_run("FAILED")
                        continue

                    if result is None:
                        self.tracker.end_run("FAILED")
                        continue

                    trained_models.append(result)

                    # Log metrics
                    self.tracker.log_metrics(result.train_metrics, prefix="train_")
                    self.tracker.log_metrics(result.val_metrics, prefix="val_")
                    self.tracker.log_metrics(result.test_metrics, prefix="test_")

                    # Log feature importance
                    if result.feature_importance:
                        self.tracker.log_feature_importance(
                            data.feature_names,
                            np.array([result.feature_importance.get(n, 0) for n in data.feature_names])
                        )

                    # Log ROC and PR curves
                    if model_name != 'anomaly':
                        test_proba = result.model.predict_proba(data.X_test)[:, 1]
                    else:
                        raw_scores = result.model.decision_function(data.X_test)
                        test_proba = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-10)

                    self.tracker.log_roc_curve(data.y_test, test_proba)
                    self.tracker.log_precision_recall_curve(data.y_test, test_proba)

                    # Log confusion matrix
                    test_pred = (test_proba >= 0.5).astype(int)
                    self.tracker.log_confusion_matrix(data.y_test, test_pred)

                    # Save model
                    self.tracker.log_model(
                        result.model,
                        model_name,
                        signature_input=data.X_test[:5],
                        signature_output=test_pred[:5]
                    )

                    # Save to disk
                    model_path = self.output_dir / f"{model_name}.pkl"
                    with open(model_path, 'wb') as f:
                        pickle.dump(result.model, f)

                    report['results'][model_name] = {
                        'train_f1': result.train_metrics.f1,
                        'val_f1': result.val_metrics.f1,
                        'test_f1': result.test_metrics.f1,
                        'test_auc_roc': result.test_metrics.auc_roc,
                        'test_precision': result.test_metrics.precision,
                        'test_recall': result.test_metrics.recall,
                        'training_time_seconds': result.training_time_seconds
                    }

                    self.tracker.end_run("FINISHED")

                except Exception as e:
                    logger.error(f"Failed to train {model_name}: {e}")
                    self.tracker.end_run("FAILED")

            # 4. Train ensemble if requested and we have base models
            if 'ensemble' in models_to_train and len(trained_models) >= 2:
                config = TrainingConfig(
                    model_type='ensemble',
                    hyperparameters={'base_models': [m.model_name for m in trained_models]},
                    feature_count=len(data.feature_names),
                    training_samples=len(data.y_train),
                    validation_samples=len(data.y_val),
                    test_samples=len(data.y_test)
                )

                self.tracker.start_run(
                    run_name=f"ensemble_{datetime.now().strftime('%Y%m%d_%H%M')}",
                    config=config,
                    tags={'pipeline': 'full_training'}
                )

                try:
                    result = self.train_ensemble(data, trained_models)

                    self.tracker.log_metrics(result.train_metrics, prefix="train_")
                    self.tracker.log_metrics(result.val_metrics, prefix="val_")
                    self.tracker.log_metrics(result.test_metrics, prefix="test_")

                    # Save ensemble
                    model_path = self.output_dir / "ensemble.pkl"
                    with open(model_path, 'wb') as f:
                        pickle.dump(result.model, f)

                    report['results']['ensemble'] = {
                        'train_f1': result.train_metrics.f1,
                        'val_f1': result.val_metrics.f1,
                        'test_f1': result.test_metrics.f1,
                        'test_auc_roc': result.test_metrics.auc_roc,
                        'test_precision': result.test_metrics.precision,
                        'test_recall': result.test_metrics.recall
                    }

                    self.tracker.end_run("FINISHED")

                except Exception as e:
                    logger.error(f"Failed to train ensemble: {e}")
                    self.tracker.end_run("FAILED")

            # 5. Save scaler and feature names
            with open(self.output_dir / "scaler.pkl", 'wb') as f:
                pickle.dump(data.scaler, f)

            with open(self.output_dir / "feature_names.json", 'w') as f:
                json.dump(data.feature_names, f)

            # 6. Determine best model
            best_model = max(
                report['results'].items(),
                key=lambda x: x[1].get('test_f1', 0)
            )
            report['best_model'] = {
                'name': best_model[0],
                'test_f1': best_model[1]['test_f1']
            }

            # 7. Save report
            report_path = self.output_dir / "training_report.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info("=" * 60)
            logger.info(f"Training complete! Best model: {best_model[0]} (F1: {best_model[1]['test_f1']:.3f})")
            logger.info(f"Models saved to: {self.output_dir}")
            logger.info("=" * 60)

            return report

        except Exception as e:
            logger.error(f"Training pipeline failed: {e}")
            report['error'] = str(e)
            raise


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Train corruption detection models")
    parser.add_argument('--limit', type=int, default=None, help='Maximum samples to use')
    parser.add_argument('--start-date', type=str, default=None, help='Filter start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None, help='Filter end date (YYYY-MM-DD)')
    parser.add_argument('--output-dir', type=str, default='./models', help='Output directory')
    parser.add_argument('--models', type=str, default='all',
                       help='Models to train (comma-separated): random_forest,xgboost,neural_network,anomaly,ensemble')
    parser.add_argument('--db-url', type=str, default=None, help='Database URL')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Parse models list
    if args.models == 'all':
        models = ['random_forest', 'xgboost', 'neural_network', 'anomaly', 'ensemble']
    else:
        models = [m.strip() for m in args.models.split(',')]

    # Run pipeline
    pipeline = CorruptionTrainingPipeline(
        db_url=args.db_url,
        output_dir=args.output_dir,
        random_seed=args.seed
    )

    try:
        await pipeline.initialize()
        report = await pipeline.run_training(
            limit=args.limit,
            start_date=args.start_date,
            end_date=args.end_date,
            models_to_train=models
        )

        print("\n" + "=" * 60)
        print("TRAINING SUMMARY")
        print("=" * 60)
        for model_name, metrics in report.get('results', {}).items():
            print(f"\n{model_name}:")
            print(f"  Test F1:        {metrics.get('test_f1', 0):.4f}")
            print(f"  Test AUC-ROC:   {metrics.get('test_auc_roc', 0):.4f}")
            print(f"  Test Precision: {metrics.get('test_precision', 0):.4f}")
            print(f"  Test Recall:    {metrics.get('test_recall', 0):.4f}")

        if 'best_model' in report:
            print(f"\nBest Model: {report['best_model']['name']} (F1: {report['best_model']['test_f1']:.4f})")

    finally:
        await pipeline.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
