#!/usr/bin/env python3
"""
XGBoost Training Script for Corruption Detection

This script trains an XGBoost model on the labeled dataset for corruption detection.
The labeled dataset contains 300 samples (150 positive, 150 negative) with features
extracted from tenders.

Features:
- Loads labeled dataset from ground_truth/labeled_dataset.json
- Extracts feature vectors from the samples
- Implements hyperparameter tuning with cross-validation
- Saves trained model to models/xgboost.joblib
- Outputs training metrics and feature importance

Usage:
    python train_xgboost.py
    python train_xgboost.py --tune  # With hyperparameter tuning
    python train_xgboost.py --cv-folds 10  # Custom CV folds

Author: nabavkidata.com
License: Proprietary
"""

import os
import sys
import json
import logging
import argparse
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import pickle

import numpy as np
import pandas as pd
import joblib

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_score,
    cross_val_predict,
    RandomizedSearchCV
)
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    classification_report,
    confusion_matrix
)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import XGBoost model class
from ai.corruption.ml_models.xgboost_model import (
    CorruptionXGBoost,
    XGBModelMetrics,
    XGBFeatureImportance,
    quick_train_xgboost
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LabeledDatasetLoader:
    """
    Loads and preprocesses the labeled dataset for XGBoost training.

    The labeled dataset JSON contains:
    - metadata: Dataset statistics
    - samples: List of labeled samples with features
    """

    def __init__(self, dataset_path: str):
        """
        Initialize loader with dataset path.

        Args:
            dataset_path: Path to labeled_dataset.json
        """
        self.dataset_path = Path(dataset_path)
        self.dataset: Optional[Dict] = None
        self.feature_names: Optional[List[str]] = None

    def load(self) -> Dict:
        """Load dataset from JSON file."""
        logger.info(f"Loading labeled dataset from {self.dataset_path}")

        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            self.dataset = json.load(f)

        metadata = self.dataset.get('metadata', {})
        logger.info(f"Dataset loaded:")
        logger.info(f"  Total samples: {metadata.get('total_samples', len(self.dataset.get('samples', [])))}")
        logger.info(f"  Positive samples: {metadata.get('positive_samples', 'N/A')}")
        logger.info(f"  Negative samples: {metadata.get('negative_samples', 'N/A')}")

        return self.dataset

    def extract_features_and_labels(self) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        """
        Extract feature matrix and labels from the dataset.

        Returns:
            Tuple of (X, y, feature_names, tender_ids)
        """
        if self.dataset is None:
            self.load()

        samples = self.dataset.get('samples', [])

        if not samples:
            raise ValueError("No samples found in dataset")

        # Determine feature names from first sample
        first_features = samples[0].get('features', {})

        # Define numeric features to extract (exclude non-numeric like 'tender_id', 'status', 'flag_types')
        numeric_feature_names = [
            'has_winner', 'num_bidders', 'single_bidder', 'bidder_count',
            'estimated_value_mkd', 'actual_value_mkd', 'has_price_data',
            'price_deviation', 'price_ratio', 'bid_mean', 'bid_std', 'bid_cv',
            'deadline_days', 'short_deadline', 'num_documents', 'amendment_count',
            'has_amendments', 'flag_count', 'max_flag_score', 'avg_flag_score'
        ]

        # Filter to features that exist in the dataset
        available_features = []
        for feat in numeric_feature_names:
            if feat in first_features:
                available_features.append(feat)

        self.feature_names = available_features
        logger.info(f"Extracting {len(available_features)} numeric features")

        # Extract features and labels
        X_list = []
        y_list = []
        tender_ids = []

        for sample in samples:
            features = sample.get('features', {})
            label = sample.get('label', 0)
            tender_id = sample.get('tender_id', '')

            # Extract feature vector
            feature_vector = []
            for feat_name in available_features:
                value = features.get(feat_name, 0.0)
                # Handle None values
                if value is None:
                    value = 0.0
                # Handle string values (shouldn't happen but be safe)
                if isinstance(value, str):
                    try:
                        value = float(value)
                    except ValueError:
                        value = 0.0
                feature_vector.append(float(value))

            X_list.append(feature_vector)
            y_list.append(int(label))
            tender_ids.append(tender_id)

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.int32)

        logger.info(f"Extracted features: X shape = {X.shape}, y shape = {y.shape}")
        logger.info(f"Label distribution: {(y == 1).sum()} positive, {(y == 0).sum()} negative")

        return X, y, self.feature_names, tender_ids


class XGBoostTrainer:
    """
    Complete training pipeline for XGBoost corruption detection model.

    This class handles:
    - Data preprocessing (imputation, scaling)
    - Cross-validation
    - Hyperparameter tuning with RandomizedSearchCV
    - Model training and evaluation
    - Model persistence
    """

    def __init__(
        self,
        output_dir: str = "./models",
        random_seed: int = 42
    ):
        """
        Initialize trainer.

        Args:
            output_dir: Directory to save trained models
            random_seed: Random seed for reproducibility
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.random_seed = random_seed

        # Preprocessing objects
        self.imputer: Optional[SimpleImputer] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: Optional[List[str]] = None

        np.random.seed(random_seed)
        logger.info(f"XGBoostTrainer initialized. Output: {self.output_dir}")

    def preprocess_features(
        self,
        X_train: np.ndarray,
        X_test: np.ndarray,
        fit: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocess features: handle missing values and scale.

        Args:
            X_train: Training features
            X_test: Test features
            fit: Whether to fit preprocessors

        Returns:
            Tuple of (X_train_processed, X_test_processed)
        """
        # Replace infinities with NaN
        X_train = np.where(np.isinf(X_train), np.nan, X_train)
        X_test = np.where(np.isinf(X_test), np.nan, X_test)

        # Handle missing values
        if fit or self.imputer is None:
            self.imputer = SimpleImputer(strategy='median')
            X_train = self.imputer.fit_transform(X_train)
        else:
            X_train = self.imputer.transform(X_train)
        X_test = self.imputer.transform(X_test)

        # Standardize features
        if fit or self.scaler is None:
            self.scaler = StandardScaler()
            X_train = self.scaler.fit_transform(X_train)
        else:
            X_train = self.scaler.transform(X_train)
        X_test = self.scaler.transform(X_test)

        return X_train, X_test

    def cross_validate(
        self,
        model: CorruptionXGBoost,
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int = 5
    ) -> Dict[str, Any]:
        """
        Perform stratified k-fold cross-validation.

        Args:
            model: XGBoost model instance
            X: Features
            y: Labels
            n_folds: Number of CV folds

        Returns:
            Dictionary with CV results
        """
        logger.info(f"Performing {n_folds}-fold stratified cross-validation...")

        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=self.random_seed)

        # Track metrics across folds
        metrics = {
            'accuracy': [],
            'precision': [],
            'recall': [],
            'f1': [],
            'roc_auc': []
        }

        y_pred_all = np.zeros_like(y)
        y_proba_all = np.zeros_like(y, dtype=np.float32)

        for fold, (train_idx, val_idx) in enumerate(cv.split(X, y)):
            X_train_fold, X_val_fold = X[train_idx], X[val_idx]
            y_train_fold, y_val_fold = y[train_idx], y[val_idx]

            # Calculate scale_pos_weight for this fold
            n_neg = (y_train_fold == 0).sum()
            n_pos = (y_train_fold == 1).sum()
            scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

            # Train model for this fold
            fold_model = CorruptionXGBoost(
                n_estimators=model.params['n_estimators'],
                max_depth=model.params['max_depth'],
                learning_rate=model.params['learning_rate'],
                scale_pos_weight=scale_pos_weight,
                random_state=self.random_seed
            )

            fold_model.fit(
                X_train_fold, y_train_fold,
                eval_set=[(X_val_fold, y_val_fold)],
                early_stopping_rounds=30,
                verbose=False
            )

            # Predict on validation fold
            y_pred = fold_model.predict(X_val_fold)
            y_proba = fold_model.predict_proba(X_val_fold)[:, 1]

            y_pred_all[val_idx] = y_pred
            y_proba_all[val_idx] = y_proba

            # Calculate metrics for this fold
            metrics['accuracy'].append(accuracy_score(y_val_fold, y_pred))
            metrics['precision'].append(precision_score(y_val_fold, y_pred, zero_division=0))
            metrics['recall'].append(recall_score(y_val_fold, y_pred, zero_division=0))
            metrics['f1'].append(f1_score(y_val_fold, y_pred, zero_division=0))
            metrics['roc_auc'].append(roc_auc_score(y_val_fold, y_proba))

            logger.info(f"  Fold {fold + 1}: F1={metrics['f1'][-1]:.4f}, ROC-AUC={metrics['roc_auc'][-1]:.4f}")

        # Aggregate results
        results = {}
        for metric_name, scores in metrics.items():
            scores_arr = np.array(scores)
            results[metric_name] = {
                'scores': scores_arr.tolist(),
                'mean': float(scores_arr.mean()),
                'std': float(scores_arr.std())
            }
            logger.info(f"  {metric_name}: {scores_arr.mean():.4f} (+/- {scores_arr.std() * 2:.4f})")

        # Overall confusion matrix
        results['confusion_matrix'] = confusion_matrix(y, y_pred_all).tolist()
        results['classification_report'] = classification_report(
            y, y_pred_all, target_names=['Clean', 'Flagged']
        )

        return results

    def hyperparameter_tune(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int = 5,
        n_iter: int = 30
    ) -> Tuple[CorruptionXGBoost, Dict[str, Any]]:
        """
        Perform hyperparameter tuning with RandomizedSearchCV.

        Args:
            X: Features
            y: Labels
            n_folds: Number of CV folds
            n_iter: Number of random parameter combinations

        Returns:
            Tuple of (best_model, best_params)
        """
        import xgboost as xgb

        logger.info(f"Starting hyperparameter tuning with {n_iter} iterations...")

        # Calculate scale_pos_weight
        n_neg = (y == 0).sum()
        n_pos = (y == 1).sum()
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

        # Parameter distributions for randomized search
        param_distributions = {
            'max_depth': [3, 4, 5, 6, 7, 8, 10],
            'learning_rate': [0.01, 0.02, 0.05, 0.1, 0.15, 0.2],
            'n_estimators': [100, 200, 300, 400, 500],
            'subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
            'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
            'min_child_weight': [1, 2, 3, 5, 7],
            'reg_alpha': [0, 0.01, 0.1, 0.5, 1.0],
            'reg_lambda': [0.5, 1.0, 1.5, 2.0, 5.0],
            'gamma': [0, 0.1, 0.2, 0.5, 1.0]
        }

        base_model = xgb.XGBClassifier(
            objective='binary:logistic',
            eval_metric='auc',
            scale_pos_weight=scale_pos_weight,
            n_jobs=-1,
            random_state=self.random_seed,
            tree_method='hist'
        )

        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=self.random_seed)

        random_search = RandomizedSearchCV(
            base_model,
            param_distributions,
            n_iter=n_iter,
            cv=cv,
            scoring='roc_auc',
            n_jobs=-1,
            verbose=1,
            random_state=self.random_seed,
            refit=True
        )

        start_time = datetime.utcnow()
        random_search.fit(X, y)
        search_time = (datetime.utcnow() - start_time).total_seconds()

        best_params = random_search.best_params_
        best_score = random_search.best_score_

        logger.info(f"Best ROC-AUC: {best_score:.4f}")
        logger.info(f"Best parameters: {best_params}")
        logger.info(f"Search completed in {search_time:.1f}s")

        # Create CorruptionXGBoost with best parameters
        best_model = CorruptionXGBoost(
            n_estimators=best_params.get('n_estimators', 200),
            max_depth=best_params.get('max_depth', 6),
            learning_rate=best_params.get('learning_rate', 0.1),
            subsample=best_params.get('subsample', 0.8),
            colsample_bytree=best_params.get('colsample_bytree', 0.8),
            min_child_weight=best_params.get('min_child_weight', 1),
            reg_alpha=best_params.get('reg_alpha', 0),
            reg_lambda=best_params.get('reg_lambda', 1.0),
            gamma=best_params.get('gamma', 0),
            scale_pos_weight=scale_pos_weight,
            random_state=self.random_seed
        )

        return best_model, best_params

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str],
        tune_hyperparameters: bool = False,
        cv_folds: int = 5
    ) -> Tuple[CorruptionXGBoost, XGBModelMetrics, XGBFeatureImportance, Dict]:
        """
        Train the XGBoost model.

        Args:
            X_train: Training features
            y_train: Training labels
            X_test: Test features
            y_test: Test labels
            feature_names: List of feature names
            tune_hyperparameters: Whether to perform hyperparameter tuning
            cv_folds: Number of cross-validation folds

        Returns:
            Tuple of (model, metrics, feature_importance, cv_results)
        """
        logger.info("=" * 60)
        logger.info("Training XGBoost Corruption Detection Model")
        logger.info("=" * 60)

        self.feature_names = feature_names

        # Calculate scale_pos_weight
        n_neg = (y_train == 0).sum()
        n_pos = (y_train == 1).sum()
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0
        logger.info(f"Class distribution - Positive: {n_pos}, Negative: {n_neg}")
        logger.info(f"Scale pos weight: {scale_pos_weight:.4f}")

        if tune_hyperparameters:
            # Hyperparameter tuning on full training data
            xgb_model, best_params = self.hyperparameter_tune(
                X_train, y_train,
                n_folds=cv_folds,
                n_iter=30
            )

            # Train final model with best params
            xgb_model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                early_stopping_rounds=50,
                scale_pos_weight=scale_pos_weight,
                feature_names=feature_names,
                verbose=True
            )
        else:
            # Create model with default hyperparameters
            xgb_model = CorruptionXGBoost(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=3,
                reg_alpha=0.1,
                reg_lambda=1.0,
                scale_pos_weight=scale_pos_weight,
                random_state=self.random_seed
            )

            # Train with early stopping
            xgb_model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                early_stopping_rounds=50,
                scale_pos_weight=scale_pos_weight,
                feature_names=feature_names,
                verbose=True
            )

        # Cross-validation results
        logger.info("\nPerforming cross-validation...")
        cv_results = self.cross_validate(xgb_model, X_train, y_train, n_folds=cv_folds)

        # Evaluate on test set
        logger.info("\nEvaluating on test set...")
        metrics = xgb_model.evaluate(X_test, y_test)

        # Add CV scores to metrics
        metrics.cv_scores = np.array(cv_results['roc_auc']['scores'])
        metrics.cv_mean = cv_results['roc_auc']['mean']
        metrics.cv_std = cv_results['roc_auc']['std']

        # Get feature importance
        importance = xgb_model.get_feature_importance(feature_names)

        # Log top features
        logger.info("\nTop 15 Most Important Features (Gain):")
        for name, imp in importance.get_top_features(15, method='gain'):
            logger.info(f"  {name}: {imp:.4f}")

        return xgb_model, metrics, importance, cv_results

    def save_model(
        self,
        model: CorruptionXGBoost,
        metrics: XGBModelMetrics,
        importance: XGBFeatureImportance,
        cv_results: Dict,
        model_name: str = "xgboost"
    ) -> str:
        """
        Save trained model and artifacts.

        Args:
            model: Trained model
            metrics: Model metrics
            importance: Feature importance
            cv_results: Cross-validation results
            model_name: Base name for saved files

        Returns:
            Path to saved model
        """
        # Save model using joblib
        model_path = self.output_dir / f"{model_name}.joblib"

        # Save the entire model object
        model_data = {
            'model': model.model,
            'params': model.params,
            'feature_names': model.feature_names,
            'training_metadata': model.training_metadata,
            'best_iteration': model.best_iteration,
            'imputer': self.imputer,
            'scaler': self.scaler
        }
        joblib.dump(model_data, model_path)

        # Also save in XGBoost native format for compatibility
        model.save(str(self.output_dir / model_name))

        # Save metrics
        metrics_path = self.output_dir / f"{model_name}_metrics.json"
        metrics_dict = metrics.to_dict()
        metrics_dict['cv_results'] = cv_results
        with open(metrics_path, 'w') as f:
            json.dump(metrics_dict, f, indent=2)

        # Save feature importance
        importance_df = importance.to_dataframe()
        importance_path = self.output_dir / f"{model_name}_feature_importance.csv"
        importance_df.to_csv(importance_path, index=False)

        logger.info(f"\nModel saved to: {model_path}")
        logger.info(f"Metrics saved to: {metrics_path}")
        logger.info(f"Feature importance saved to: {importance_path}")

        return str(model_path)


def main():
    """Main entry point for XGBoost training."""
    parser = argparse.ArgumentParser(description="Train XGBoost for corruption detection")
    parser.add_argument('--dataset', type=str,
                       default=str(Path(__file__).parent.parent / 'ground_truth' / 'labeled_dataset.json'),
                       help='Path to labeled dataset JSON')
    parser.add_argument('--output-dir', type=str,
                       default=str(Path(__file__).parent / 'models'),
                       help='Output directory for saved models')
    parser.add_argument('--tune', action='store_true',
                       help='Perform hyperparameter tuning')
    parser.add_argument('--cv-folds', type=int, default=5,
                       help='Number of cross-validation folds')
    parser.add_argument('--test-size', type=float, default=0.2,
                       help='Proportion for test set')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 70)
    print("XGBoost Training for Corruption Detection")
    print("=" * 70)
    print(f"\nDataset: {args.dataset}")
    print(f"Output directory: {args.output_dir}")
    print(f"Hyperparameter tuning: {args.tune}")
    print(f"CV folds: {args.cv_folds}")
    print(f"Test size: {args.test_size}")
    print(f"Random seed: {args.seed}")
    print()

    # Check if dataset exists
    if not Path(args.dataset).exists():
        print(f"ERROR: Dataset not found at {args.dataset}")
        print("Please run create_labeled_dataset.py first to generate the dataset.")
        sys.exit(1)

    # Load dataset
    loader = LabeledDatasetLoader(args.dataset)
    X, y, feature_names, tender_ids = loader.extract_features_and_labels()

    # Split data
    X_train, X_test, y_train, y_test, ids_train, ids_test = train_test_split(
        X, y, tender_ids,
        test_size=args.test_size,
        stratify=y,
        random_state=args.seed
    )

    print(f"\nData split:")
    print(f"  Training: {len(y_train)} samples ({(y_train == 1).sum()} positive, {(y_train == 0).sum()} negative)")
    print(f"  Test: {len(y_test)} samples ({(y_test == 1).sum()} positive, {(y_test == 0).sum()} negative)")
    print()

    # Initialize trainer
    trainer = XGBoostTrainer(
        output_dir=args.output_dir,
        random_seed=args.seed
    )

    # Preprocess features
    X_train_processed, X_test_processed = trainer.preprocess_features(X_train, X_test)

    # Train model
    model, metrics, importance, cv_results = trainer.train(
        X_train_processed, y_train,
        X_test_processed, y_test,
        feature_names=feature_names,
        tune_hyperparameters=args.tune,
        cv_folds=args.cv_folds
    )

    # Save model
    model_path = trainer.save_model(model, metrics, importance, cv_results)

    # Print summary
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)
    print(f"\nTest Set Performance:")
    print(f"  Accuracy:          {metrics.accuracy:.4f}")
    print(f"  Precision:         {metrics.precision:.4f}")
    print(f"  Recall:            {metrics.recall:.4f}")
    print(f"  F1 Score:          {metrics.f1:.4f}")
    print(f"  ROC-AUC:           {metrics.roc_auc:.4f}")
    print(f"  Average Precision: {metrics.average_precision:.4f}")
    print(f"  Best Iteration:    {metrics.best_iteration}")

    print(f"\nCross-Validation ({args.cv_folds}-fold):")
    print(f"  ROC-AUC: {cv_results['roc_auc']['mean']:.4f} (+/- {cv_results['roc_auc']['std']*2:.4f})")
    print(f"  F1:      {cv_results['f1']['mean']:.4f} (+/- {cv_results['f1']['std']*2:.4f})")

    print(f"\nConfusion Matrix:")
    print(f"  {metrics.confusion_matrix}")

    print(f"\nClassification Report:")
    print(metrics.classification_report)

    print(f"\nTop 10 Most Important Features:")
    for i, (name, imp) in enumerate(importance.get_top_features(10, method='gain')):
        print(f"  {i+1}. {name}: {imp:.4f}")

    print(f"\nModel saved to: {model_path}")
    print("=" * 70)

    return {
        'model_path': model_path,
        'metrics': metrics.to_dict(),
        'cv_results': cv_results
    }


if __name__ == '__main__':
    main()
