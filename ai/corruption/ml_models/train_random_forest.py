#!/usr/bin/env python3
"""
Random Forest Training Script for Corruption Detection

This script provides a complete training pipeline for the Random Forest
corruption detection model, including:

1. Data extraction from database (corruption_flags + known cases)
2. Feature preprocessing (null handling, scaling)
3. Class balancing (SMOTE or class_weight)
4. Stratified K-Fold cross-validation
5. Hyperparameter tuning with GridSearchCV
6. Model training and evaluation
7. Model persistence with joblib

Usage:
    python train_random_forest.py --limit 50000 --output-dir ./models

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
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import pickle
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_score,
    cross_val_predict,
    GridSearchCV
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
    confusion_matrix,
    precision_recall_curve,
    roc_curve
)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import local modules
from ai.corruption.ml_models.random_forest import (
    CorruptionRandomForest,
    ModelMetrics,
    FeatureImportance,
    quick_train_random_forest
)
from ai.corruption.ground_truth.known_cases import (
    get_all_cases,
    CORRUPTION_INDICATORS
)

logger = logging.getLogger(__name__)


class RandomForestTrainer:
    """
    Complete training pipeline for Random Forest corruption detection model.

    This class handles:
    - Data extraction from database
    - Feature preprocessing (imputation, scaling)
    - Class imbalance handling (SMOTE or class_weight)
    - Cross-validation
    - Hyperparameter tuning
    - Model training and evaluation
    - Model persistence
    """

    def __init__(
        self,
        output_dir: str = "./models",
        random_seed: int = 42,
        use_smote: bool = False
    ):
        """
        Initialize the trainer.

        Args:
            output_dir: Directory to save trained models
            random_seed: Random seed for reproducibility
            use_smote: Whether to use SMOTE for oversampling (requires imblearn)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.random_seed = random_seed
        self.use_smote = use_smote

        # Preprocessing objects (fitted during training)
        self.imputer: Optional[SimpleImputer] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: Optional[List[str]] = None

        np.random.seed(random_seed)

        logger.info(f"RandomForestTrainer initialized. Output: {self.output_dir}")

    async def extract_training_data(
        self,
        limit: Optional[int] = None,
        negative_ratio: float = 1.0,
        min_flags: int = 1
    ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        """
        Extract training data from database.

        Args:
            limit: Maximum number of positive samples
            negative_ratio: Ratio of negative to positive samples
            min_flags: Minimum flags to consider a tender as positive

        Returns:
            Tuple of (X, y, feature_names, tender_ids)
        """
        import asyncpg
        from ai.corruption.features.feature_extractor import FeatureExtractor
        from ai.corruption.ml_models.training_data import (
            TrainingDataExtractor,
            create_connection_pool
        )

        logger.info("Extracting training data from database...")

        pool = await create_connection_pool()

        try:
            extractor = TrainingDataExtractor(pool)

            # Get flagged tenders (positive examples)
            flagged_ids = await extractor.get_flagged_tenders(
                min_flags=min_flags,
                limit=limit
            )
            n_positive = len(flagged_ids)

            if n_positive == 0:
                raise ValueError("No flagged tenders found in database")

            # Get clean tenders (negative examples)
            n_negative = int(n_positive * negative_ratio)
            clean_ids = await extractor.get_clean_tenders(
                n_negative,
                exclude_tender_ids=flagged_ids
            )

            logger.info(f"Found {n_positive} positive, {len(clean_ids)} negative samples")

            # Combine and create labels
            all_tender_ids = flagged_ids + clean_ids
            y = np.array([1] * n_positive + [0] * len(clean_ids), dtype=np.int32)

            # Extract features
            X, feature_names, successful_ids = await extractor.extract_features_for_tenders(
                all_tender_ids
            )

            # Filter labels to match successful extractions
            id_to_label = dict(zip(all_tender_ids, y))
            y_filtered = np.array([id_to_label[tid] for tid in successful_ids], dtype=np.int32)

            self.feature_names = feature_names

            logger.info(f"Extracted {X.shape[1]} features for {len(successful_ids)} tenders")

            return X, y_filtered, feature_names, successful_ids

        finally:
            await pool.close()

    def preprocess_features(
        self,
        X_train: np.ndarray,
        X_test: np.ndarray,
        fit: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocess features: handle nulls and scale.

        Args:
            X_train: Training features
            X_test: Test features
            fit: Whether to fit preprocessors (True for training, False for inference)

        Returns:
            Tuple of (X_train_processed, X_test_processed)
        """
        # Replace infinities with NaN
        X_train = np.where(np.isinf(X_train), np.nan, X_train)
        X_test = np.where(np.isinf(X_test), np.nan, X_test)

        # Handle missing values with median imputation
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

        nan_count = np.isnan(X_train).sum() + np.isnan(X_test).sum()
        if nan_count > 0:
            logger.warning(f"Still have {nan_count} NaN values after imputation")

        return X_train, X_test

    def compute_class_weights(self, y: np.ndarray) -> Dict[int, float]:
        """
        Compute balanced class weights.

        Args:
            y: Label array

        Returns:
            Dictionary mapping class -> weight
        """
        classes, counts = np.unique(y, return_counts=True)
        n_samples = len(y)
        n_classes = len(classes)

        weights = {}
        for cls, count in zip(classes, counts):
            weights[int(cls)] = n_samples / (n_classes * count)

        logger.info(f"Class distribution: {dict(zip(classes, counts))}")
        logger.info(f"Computed class weights: {weights}")

        return weights

    def apply_smote(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply SMOTE for oversampling minority class.

        Args:
            X: Features
            y: Labels

        Returns:
            Tuple of (X_resampled, y_resampled)
        """
        try:
            from imblearn.over_sampling import SMOTE

            smote = SMOTE(random_state=self.random_seed)
            X_resampled, y_resampled = smote.fit_resample(X, y)

            logger.info(f"SMOTE: {len(y)} -> {len(y_resampled)} samples")
            logger.info(f"  Before: {(y==1).sum()} positive, {(y==0).sum()} negative")
            logger.info(f"  After: {(y_resampled==1).sum()} positive, {(y_resampled==0).sum()} negative")

            return X_resampled, y_resampled

        except ImportError:
            logger.warning("imblearn not installed, skipping SMOTE. Install with: pip install imbalanced-learn")
            return X, y

    def cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model: RandomForestClassifier,
        n_folds: int = 5
    ) -> Dict[str, Any]:
        """
        Perform stratified k-fold cross-validation.

        Args:
            X: Features
            y: Labels
            model: Model to evaluate
            n_folds: Number of CV folds

        Returns:
            Dictionary with CV results
        """
        logger.info(f"Performing {n_folds}-fold stratified cross-validation...")

        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=self.random_seed)

        # Multiple scoring metrics
        scoring = {
            'accuracy': 'accuracy',
            'precision': 'precision',
            'recall': 'recall',
            'f1': 'f1',
            'roc_auc': 'roc_auc'
        }

        results = {}
        for metric_name, scorer in scoring.items():
            scores = cross_val_score(
                model, X, y,
                cv=cv,
                scoring=scorer,
                n_jobs=-1
            )
            results[metric_name] = {
                'scores': scores.tolist(),
                'mean': float(scores.mean()),
                'std': float(scores.std())
            }
            logger.info(f"  {metric_name}: {scores.mean():.4f} (+/- {scores.std() * 2:.4f})")

        # Get CV predictions for confusion matrix
        y_pred_cv = cross_val_predict(model, X, y, cv=cv, n_jobs=-1)
        results['confusion_matrix'] = confusion_matrix(y, y_pred_cv).tolist()
        results['classification_report'] = classification_report(y, y_pred_cv, target_names=['Clean', 'Flagged'])

        return results

    def hyperparameter_tune(
        self,
        X: np.ndarray,
        y: np.ndarray,
        param_grid: Optional[Dict] = None,
        n_folds: int = 5
    ) -> Tuple[RandomForestClassifier, Dict[str, Any]]:
        """
        Perform hyperparameter tuning with GridSearchCV.

        Args:
            X: Features
            y: Labels
            param_grid: Parameter grid (uses default if None)
            n_folds: Number of CV folds

        Returns:
            Tuple of (best_model, best_params)
        """
        if param_grid is None:
            # Optimized parameter grid for corruption detection
            param_grid = {
                'n_estimators': [100, 200, 300],
                'max_depth': [10, 20, 30, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4],
                'max_features': ['sqrt', 'log2', 0.3],
                'class_weight': ['balanced', 'balanced_subsample']
            }

        logger.info(f"Starting hyperparameter tuning with GridSearchCV ({n_folds}-fold CV)...")
        logger.info(f"Parameter grid: {param_grid}")

        base_model = RandomForestClassifier(
            n_jobs=-1,
            random_state=self.random_seed,
            oob_score=True
        )

        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=self.random_seed)

        grid_search = GridSearchCV(
            base_model,
            param_grid,
            cv=cv,
            scoring='roc_auc',  # Optimize for AUC-ROC
            n_jobs=-1,
            verbose=2,
            refit=True,
            return_train_score=True
        )

        start_time = datetime.utcnow()
        grid_search.fit(X, y)
        search_time = (datetime.utcnow() - start_time).total_seconds()

        best_params = grid_search.best_params_
        best_score = grid_search.best_score_

        logger.info(f"Best ROC-AUC: {best_score:.4f}")
        logger.info(f"Best parameters: {best_params}")
        logger.info(f"Search completed in {search_time:.1f}s")

        # Get CV results summary
        cv_results = pd.DataFrame(grid_search.cv_results_)
        top_5 = cv_results.nlargest(5, 'mean_test_score')[
            ['params', 'mean_test_score', 'std_test_score', 'mean_train_score']
        ]
        logger.info(f"\nTop 5 configurations:\n{top_5}")

        return grid_search.best_estimator_, best_params

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        tune_hyperparameters: bool = False,
        param_grid: Optional[Dict] = None
    ) -> Tuple[CorruptionRandomForest, ModelMetrics, FeatureImportance]:
        """
        Train the Random Forest model.

        Args:
            X_train: Training features
            y_train: Training labels
            X_test: Test features
            y_test: Test labels
            tune_hyperparameters: Whether to perform hyperparameter tuning
            param_grid: Custom parameter grid for tuning

        Returns:
            Tuple of (trained_model, test_metrics, feature_importance)
        """
        logger.info("=" * 60)
        logger.info("Training Random Forest Corruption Detection Model")
        logger.info("=" * 60)

        # Compute class weights
        class_weights = self.compute_class_weights(y_train)

        # Apply SMOTE if requested
        if self.use_smote:
            X_train, y_train = self.apply_smote(X_train, y_train)

        # Create model
        rf = CorruptionRandomForest(
            n_estimators=200,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            class_weight='balanced' if not self.use_smote else None,
            n_jobs=-1,
            random_state=self.random_seed
        )

        if tune_hyperparameters:
            # Hyperparameter tuning
            best_model, best_params = self.hyperparameter_tune(
                X_train, y_train,
                param_grid=param_grid
            )
            rf.model = best_model
            rf.is_fitted = True
            rf.feature_names = self.feature_names
            rf.training_metadata = {
                'n_samples': X_train.shape[0],
                'n_features': X_train.shape[1],
                'n_positive': int(y_train.sum()),
                'n_negative': int((~y_train.astype(bool)).sum()),
                'hyperparameter_tuning': {
                    'best_params': best_params
                },
                'trained_at': datetime.utcnow().isoformat()
            }
        else:
            # Train with cross-validation
            rf.fit_with_cv(
                X_train, y_train,
                n_folds=5,
                class_weights=class_weights if not self.use_smote else None,
                feature_names=self.feature_names,
                scoring='roc_auc'
            )

        # Evaluate on test set
        logger.info("\nEvaluating on test set...")
        metrics = rf.evaluate(X_test, y_test)

        # Get feature importance
        importance = rf.get_feature_importance(
            feature_names=self.feature_names,
            X=X_test,
            y=y_test,
            compute_permutation=True,
            n_repeats=10
        )

        # Log top features
        logger.info("\nTop 15 Most Important Features (MDI):")
        for name, imp in importance.get_top_features(15, method='mdi'):
            logger.info(f"  {name}: {imp:.4f}")

        if importance.permutation_importance is not None:
            logger.info("\nTop 15 Most Important Features (Permutation):")
            for name, imp in importance.get_top_features(15, method='permutation'):
                logger.info(f"  {name}: {imp:.4f}")

        return rf, metrics, importance

    def save_model(
        self,
        model: CorruptionRandomForest,
        metrics: ModelMetrics,
        importance: FeatureImportance,
        cv_results: Optional[Dict] = None
    ) -> str:
        """
        Save trained model and artifacts to disk.

        Args:
            model: Trained model
            metrics: Model metrics
            importance: Feature importance
            cv_results: Optional CV results

        Returns:
            Path to saved model
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        model_name = f"corruption_rf_{timestamp}"

        # Save model
        model_path = self.output_dir / f"{model_name}.joblib"
        model.save(str(model_path).replace('.joblib', ''))

        # Save preprocessing objects
        preprocessing_path = self.output_dir / f"{model_name}_preprocessing.pkl"
        with open(preprocessing_path, 'wb') as f:
            pickle.dump({
                'imputer': self.imputer,
                'scaler': self.scaler,
                'feature_names': self.feature_names
            }, f)

        # Save metrics
        metrics_path = self.output_dir / f"{model_name}_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump({
                'accuracy': metrics.accuracy,
                'precision': metrics.precision,
                'recall': metrics.recall,
                'f1': metrics.f1,
                'roc_auc': metrics.roc_auc,
                'average_precision': metrics.average_precision,
                'confusion_matrix': metrics.confusion_matrix.tolist(),
                'classification_report': metrics.classification_report,
                'cv_mean': metrics.cv_mean,
                'cv_std': metrics.cv_std,
                'cv_results': cv_results
            }, f, indent=2)

        # Save feature importance
        importance_df = importance.to_dataframe()
        importance_path = self.output_dir / f"{model_name}_feature_importance.csv"
        importance_df.to_csv(importance_path, index=False)

        logger.info(f"\nModel saved to: {model_path}")
        logger.info(f"Preprocessing saved to: {preprocessing_path}")
        logger.info(f"Metrics saved to: {metrics_path}")
        logger.info(f"Feature importance saved to: {importance_path}")

        return str(model_path)

    async def run(
        self,
        limit: Optional[int] = None,
        negative_ratio: float = 1.0,
        min_flags: int = 1,
        test_size: float = 0.2,
        tune_hyperparameters: bool = False
    ) -> Dict[str, Any]:
        """
        Run the complete training pipeline.

        Args:
            limit: Maximum positive samples
            negative_ratio: Ratio of negative to positive samples
            min_flags: Minimum flags for positive classification
            test_size: Proportion for test set
            tune_hyperparameters: Whether to perform hyperparameter tuning

        Returns:
            Training report dictionary
        """
        logger.info("=" * 60)
        logger.info("Starting Random Forest Training Pipeline")
        logger.info("=" * 60)

        start_time = datetime.utcnow()
        report = {
            'timestamp': start_time.isoformat(),
            'parameters': {
                'limit': limit,
                'negative_ratio': negative_ratio,
                'min_flags': min_flags,
                'test_size': test_size,
                'tune_hyperparameters': tune_hyperparameters,
                'use_smote': self.use_smote
            }
        }

        try:
            # 1. Extract data
            X, y, feature_names, tender_ids = await self.extract_training_data(
                limit=limit,
                negative_ratio=negative_ratio,
                min_flags=min_flags
            )

            report['data'] = {
                'total_samples': len(y),
                'positive_samples': int(y.sum()),
                'negative_samples': int((~y.astype(bool)).sum()),
                'n_features': len(feature_names)
            }

            # 2. Train/test split
            X_train, X_test, y_train, y_test, ids_train, ids_test = train_test_split(
                X, y, tender_ids,
                test_size=test_size,
                stratify=y,
                random_state=self.random_seed
            )

            logger.info(f"Train: {len(y_train)} samples, Test: {len(y_test)} samples")

            # 3. Preprocess
            X_train, X_test = self.preprocess_features(X_train, X_test, fit=True)

            # 4. Cross-validation on training set
            base_model = RandomForestClassifier(
                n_estimators=200,
                max_depth=20,
                min_samples_split=5,
                min_samples_leaf=2,
                max_features='sqrt',
                class_weight='balanced',
                n_jobs=-1,
                random_state=self.random_seed
            )
            cv_results = self.cross_validate(X_train, y_train, base_model)
            report['cross_validation'] = cv_results

            # 5. Train model
            model, metrics, importance = self.train(
                X_train, y_train, X_test, y_test,
                tune_hyperparameters=tune_hyperparameters
            )

            # 6. Save model
            model_path = self.save_model(model, metrics, importance, cv_results)

            # 7. Build report
            report['metrics'] = {
                'accuracy': metrics.accuracy,
                'precision': metrics.precision,
                'recall': metrics.recall,
                'f1': metrics.f1,
                'roc_auc': metrics.roc_auc,
                'average_precision': metrics.average_precision
            }
            report['model_path'] = model_path

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            report['training_time_seconds'] = elapsed

            # Save report
            report_path = self.output_dir / "training_report.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            # Print summary
            logger.info("\n" + "=" * 60)
            logger.info("TRAINING COMPLETE")
            logger.info("=" * 60)
            logger.info(f"\nTest Set Performance:")
            logger.info(f"  Accuracy:          {metrics.accuracy:.4f}")
            logger.info(f"  Precision:         {metrics.precision:.4f}")
            logger.info(f"  Recall:            {metrics.recall:.4f}")
            logger.info(f"  F1 Score:          {metrics.f1:.4f}")
            logger.info(f"  ROC-AUC:           {metrics.roc_auc:.4f}")
            logger.info(f"  Average Precision: {metrics.average_precision:.4f}")
            logger.info(f"\nCross-Validation (5-fold):")
            logger.info(f"  F1: {cv_results['f1']['mean']:.4f} (+/- {cv_results['f1']['std']*2:.4f})")
            logger.info(f"  ROC-AUC: {cv_results['roc_auc']['mean']:.4f} (+/- {cv_results['roc_auc']['std']*2:.4f})")
            logger.info(f"\nConfusion Matrix:")
            logger.info(f"  {metrics.confusion_matrix}")
            logger.info(f"\nTraining time: {elapsed:.1f} seconds")
            logger.info(f"Model saved to: {model_path}")

            return report

        except Exception as e:
            logger.error(f"Training failed: {e}")
            report['error'] = str(e)
            raise


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Train Random Forest for corruption detection")
    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum positive samples to use')
    parser.add_argument('--negative-ratio', type=float, default=1.0,
                       help='Ratio of negative to positive samples')
    parser.add_argument('--min-flags', type=int, default=1,
                       help='Minimum flags for positive classification')
    parser.add_argument('--test-size', type=float, default=0.2,
                       help='Proportion for test set')
    parser.add_argument('--output-dir', type=str, default='./models',
                       help='Output directory for saved models')
    parser.add_argument('--tune', action='store_true',
                       help='Perform hyperparameter tuning')
    parser.add_argument('--smote', action='store_true',
                       help='Use SMOTE for oversampling')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose logging')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run training
    trainer = RandomForestTrainer(
        output_dir=args.output_dir,
        use_smote=args.smote
    )

    report = await trainer.run(
        limit=args.limit,
        negative_ratio=args.negative_ratio,
        min_flags=args.min_flags,
        test_size=args.test_size,
        tune_hyperparameters=args.tune
    )

    return report


if __name__ == '__main__':
    asyncio.run(main())
