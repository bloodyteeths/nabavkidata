#!/usr/bin/env python3
"""
Train Random Forest Model from Labeled Dataset

This script trains the Random Forest corruption detection model using
the labeled dataset created by create_labeled_dataset.py.

The labeled dataset contains:
- Positive samples: Known corruption cases + high-score flagged tenders
- Negative samples: Low-risk clean tenders with good competition

Training process:
1. Load labeled_dataset.json
2. Extract features from database using FeatureExtractor
3. Split into train/test sets (stratified)
4. Train with cross-validation
5. Evaluate and output metrics (with MLflow tracking)
6. Save model to models/random_forest.joblib

Usage:
    python train_from_labeled.py
    python train_from_labeled.py --tune  # Enable hyperparameter tuning
    python train_from_labeled.py --no-mlflow  # Disable MLflow tracking

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import asyncpg
import json
import os
import sys
import logging
import argparse
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from ai.corruption.ml_models.random_forest import (
    CorruptionRandomForest,
    ModelMetrics,
    FeatureImportance,
    quick_train_random_forest
)
from ai.corruption.features.feature_extractor import FeatureExtractor

# MLflow imports (optional)
try:
    import mlflow
    from ai.corruption.ml_models.tracking import (
        setup_mlflow,
        mlflow_run,
        TrainingConfig,
        calculate_metrics as calc_mlflow_metrics,
        log_dataset_info,
        log_hyperparameter_search,
    )
    from ai.corruption.ml_models.mlflow_config import quick_setup
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    mlflow = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GROUND_TRUTH_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'ground_truth')
LABELED_DATASET_PATH = os.path.join(GROUND_TRUTH_DIR, 'labeled_dataset.json')
MODELS_DIR = os.path.join(SCRIPT_DIR, 'models')
MODEL_OUTPUT_PATH = os.path.join(MODELS_DIR, 'random_forest.joblib')

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


def parse_dsn(url: str) -> Dict[str, str]:
    """Parse PostgreSQL connection URL into components."""
    # Format: postgresql://user:password@host/database
    url = url.replace('postgresql://', '')
    user_pass, host_db = url.split('@')
    user, password = user_pass.split(':')
    host, database = host_db.split('/')

    return {
        'user': user,
        'password': password,
        'host': host,
        'database': database
    }


def load_labeled_dataset(path: str) -> Dict[str, Any]:
    """Load the labeled dataset from JSON file."""
    logger.info(f"Loading labeled dataset from {path}")

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Labeled dataset not found at {path}. "
            f"Run create_labeled_dataset.py first."
        )

    with open(path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    metadata = dataset.get('metadata', {})
    samples = dataset.get('samples', [])

    logger.info(f"Loaded {len(samples)} samples")
    logger.info(f"  Positive: {metadata.get('positive_samples', 0)}")
    logger.info(f"  Negative: {metadata.get('negative_samples', 0)}")

    return dataset


async def extract_features_for_samples(
    pool: asyncpg.Pool,
    samples: List[Dict],
    show_progress: bool = True
) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
    """
    Extract features for all samples in the labeled dataset.

    Args:
        pool: Database connection pool
        samples: List of sample dictionaries with tender_id and label
        show_progress: Whether to log progress

    Returns:
        Tuple of (X, y, feature_names, successful_tender_ids)
    """
    feature_extractor = FeatureExtractor(pool)

    features_list = []
    labels_list = []
    successful_ids = []
    failed_count = 0

    total = len(samples)
    for i, sample in enumerate(samples):
        if show_progress and (i + 1) % 20 == 0:
            logger.info(f"Extracting features: {i + 1}/{total} ({(i+1)/total*100:.1f}%)")

        tender_id = sample['tender_id']
        label = sample['label']

        try:
            feature_vector = await feature_extractor.extract_features(
                tender_id, include_metadata=False
            )
            features_list.append(feature_vector.feature_array)
            labels_list.append(label)
            successful_ids.append(tender_id)
        except Exception as e:
            failed_count += 1
            if failed_count <= 10:
                logger.warning(f"Failed to extract features for {tender_id}: {e}")

    if failed_count > 10:
        logger.warning(f"... and {failed_count - 10} more failures")

    if not features_list:
        raise ValueError("Failed to extract features for any sample")

    X = np.vstack(features_list)
    y = np.array(labels_list, dtype=np.int32)
    feature_names = feature_extractor.feature_names

    logger.info(
        f"Extracted features for {len(successful_ids)}/{total} samples "
        f"({len(feature_names)} features each)"
    )

    return X, y, feature_names, successful_ids


def prepare_training_data(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.2,
    random_state: int = 42
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, StandardScaler, SimpleImputer]:
    """
    Prepare training data with imputation and scaling.

    Args:
        X: Feature matrix
        y: Labels
        test_size: Fraction for test set
        random_state: Random seed

    Returns:
        Tuple of (X_train, X_test, y_train, y_test, scaler, imputer)
    """
    logger.info("Preparing training data...")

    # Handle missing values (replace inf with nan, then impute)
    X = np.where(np.isinf(X), np.nan, X)
    imputer = SimpleImputer(strategy='median')
    X = imputer.fit_transform(X)

    nan_count = np.isnan(X).sum()
    if nan_count > 0:
        logger.warning(f"Still have {nan_count} NaN values after imputation")
        X = np.nan_to_num(X, nan=0.0)

    # Train/test split with stratification
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        stratify=y,
        random_state=random_state
    )

    # Scale features
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    logger.info(f"Train set: {len(y_train)} samples ({y_train.sum()} positive)")
    logger.info(f"Test set: {len(y_test)} samples ({y_test.sum()} positive)")

    return X_train, X_test, y_train, y_test, scaler, imputer


def compute_class_weights(y: np.ndarray) -> Dict[int, float]:
    """Compute balanced class weights."""
    classes, counts = np.unique(y, return_counts=True)
    n_samples = len(y)
    n_classes = len(classes)

    weights = {}
    for cls, count in zip(classes, counts):
        weights[int(cls)] = n_samples / (n_classes * count)

    logger.info(f"Class distribution: {dict(zip(classes, counts))}")
    logger.info(f"Computed class weights: {weights}")

    return weights


def print_metrics(metrics: ModelMetrics, title: str = "Model Metrics"):
    """Print formatted metrics."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)
    print(f"Accuracy:           {metrics.accuracy:.4f}")
    print(f"Precision:          {metrics.precision:.4f}")
    print(f"Recall:             {metrics.recall:.4f}")
    print(f"F1 Score:           {metrics.f1:.4f}")
    print(f"ROC-AUC:            {metrics.roc_auc:.4f}")
    print(f"Average Precision:  {metrics.average_precision:.4f}")

    if metrics.cv_mean is not None:
        print(f"\nCross-Validation (5-fold):")
        print(f"  Mean ROC-AUC:     {metrics.cv_mean:.4f} (+/- {metrics.cv_std*2:.4f})")

    print(f"\nConfusion Matrix:")
    print(f"                   Predicted")
    print(f"               Clean    Flagged")
    print(f"  Actual Clean   {metrics.confusion_matrix[0,0]:5d}      {metrics.confusion_matrix[0,1]:5d}")
    print(f"  Actual Flagged {metrics.confusion_matrix[1,0]:5d}      {metrics.confusion_matrix[1,1]:5d}")

    print(f"\n{metrics.classification_report}")


def print_feature_importance(importance: FeatureImportance, top_n: int = 20):
    """Print top feature importance."""
    print(f"\n{'='*60}")
    print(f"Top {top_n} Most Important Features (MDI)")
    print('='*60)

    top_features = importance.get_top_features(top_n, method='mdi')
    for i, (name, imp) in enumerate(top_features, 1):
        print(f"{i:2d}. {name:40s} {imp:.4f}")

    if importance.permutation_importance is not None:
        print(f"\n{'='*60}")
        print(f"Top {top_n} Most Important Features (Permutation)")
        print('='*60)

        top_perm = importance.get_top_features(top_n, method='permutation')
        for i, (name, imp) in enumerate(top_perm, 1):
            print(f"{i:2d}. {name:40s} {imp:.4f}")


async def train_model(
    tune_hyperparameters: bool = False,
    test_size: float = 0.2,
    n_cv_folds: int = 5,
    use_mlflow: bool = True
) -> Tuple[CorruptionRandomForest, ModelMetrics, FeatureImportance]:
    """
    Main training function.

    Args:
        tune_hyperparameters: Whether to run GridSearchCV
        test_size: Fraction for test set
        n_cv_folds: Number of CV folds
        use_mlflow: Whether to track with MLflow

    Returns:
        Tuple of (model, metrics, feature_importance)
    """
    print("="*70)
    print("RANDOM FOREST TRAINING FROM LABELED DATASET")
    print("="*70)
    print(f"Started at: {datetime.now().isoformat()}")

    # Initialize MLflow if available and enabled
    tracker = None
    mlflow_run_id = None
    if use_mlflow and MLFLOW_AVAILABLE:
        try:
            tracker = setup_mlflow(experiment_name="corruption_detection_rf")
            print(f"MLflow tracking enabled. Experiment: corruption_detection_rf")
        except Exception as e:
            logger.warning(f"Failed to initialize MLflow: {e}")
            tracker = None

    # Load labeled dataset
    dataset = load_labeled_dataset(LABELED_DATASET_PATH)
    samples = dataset['samples']

    if len(samples) == 0:
        raise ValueError("No samples in labeled dataset")

    # Connect to database
    dsn = parse_dsn(DATABASE_URL)
    pool = await asyncpg.create_pool(
        host=dsn['host'],
        database=dsn['database'],
        user=dsn['user'],
        password=dsn['password'],
        min_size=2,
        max_size=10
    )

    try:
        # Extract features
        print("\n" + "-"*60)
        print("STEP 1: Feature Extraction")
        print("-"*60)
        X, y, feature_names, tender_ids = await extract_features_for_samples(pool, samples)

        # Prepare data
        print("\n" + "-"*60)
        print("STEP 2: Data Preparation")
        print("-"*60)
        X_train, X_test, y_train, y_test, scaler, imputer = prepare_training_data(
            X, y, test_size=test_size
        )

        # Compute class weights
        class_weights = compute_class_weights(y_train)

        # Start MLflow run if tracking is enabled
        if tracker:
            config = TrainingConfig(
                model_type="random_forest",
                hyperparameters={
                    "n_estimators": 200,
                    "max_depth": None,
                    "min_samples_split": 5,
                    "min_samples_leaf": 2,
                    "class_weight": "balanced",
                    "tune_hyperparameters": tune_hyperparameters,
                },
                feature_count=len(feature_names),
                training_samples=len(y_train),
                validation_samples=0,  # No separate validation in this script
                test_samples=len(y_test),
                class_weights=class_weights,
                random_seed=42
            )
            run_name = f"rf_labeled_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            mlflow_run_id = tracker.start_run(
                run_name=run_name,
                config=config,
                tags={
                    "data_source": "labeled_dataset",
                    "tuned": str(tune_hyperparameters).lower()
                }
            )
            # Log dataset info
            log_dataset_info(
                train_size=len(y_train),
                val_size=0,
                test_size=len(y_test),
                n_features=len(feature_names),
                positive_rate=float(y_train.mean()),
                feature_names=feature_names
            )

        # Train model
        print("\n" + "-"*60)
        print("STEP 3: Model Training")
        print("-"*60)

        rf = CorruptionRandomForest(
            n_estimators=200,
            max_depth=None,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',
            random_state=42
        )

        best_params = None
        if tune_hyperparameters:
            print("Running hyperparameter tuning (this may take a while)...")
            param_grid = {
                'n_estimators': [100, 200, 300],
                'max_depth': [10, 20, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4]
            }
            rf, best_params = rf.hyperparameter_tune(
                X_train, y_train,
                param_grid=param_grid,
                n_folds=n_cv_folds
            )
            print(f"Best parameters: {best_params}")
            # Log hyperparameter search to MLflow
            if tracker:
                log_hyperparameter_search(
                    search_results={"param_grid": param_grid},
                    best_params=best_params,
                    best_score=rf.training_metadata.get('hyperparameter_tuning', {}).get('best_score', 0),
                    metric_name="roc_auc"
                )
        else:
            rf, cv_scores = rf.fit_with_cv(
                X_train, y_train,
                n_folds=n_cv_folds,
                class_weights=class_weights,
                feature_names=feature_names
            )
            print(f"CV ROC-AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})")
            # Log CV scores to MLflow
            if tracker:
                mlflow.log_metrics({
                    "cv_mean_roc_auc": float(cv_scores.mean()),
                    "cv_std_roc_auc": float(cv_scores.std()),
                })

        # Evaluate
        print("\n" + "-"*60)
        print("STEP 4: Model Evaluation")
        print("-"*60)

        metrics = rf.evaluate(X_test, y_test, compute_cv=True, n_folds=n_cv_folds)
        print_metrics(metrics)

        # Log metrics to MLflow
        if tracker:
            tracker.log_metrics({
                "test_accuracy": metrics.accuracy,
                "test_precision": metrics.precision,
                "test_recall": metrics.recall,
                "test_f1": metrics.f1,
                "test_roc_auc": metrics.roc_auc,
                "test_average_precision": metrics.average_precision,
            })
            # Log confusion matrix
            y_pred = rf.predict(X_test)
            tracker.log_confusion_matrix(y_test, y_pred)
            # Log ROC and PR curves
            y_proba = rf.predict_proba(X_test)[:, 1]
            tracker.log_roc_curve(y_test, y_proba)
            tracker.log_precision_recall_curve(y_test, y_proba)

        # Feature importance
        print("\n" + "-"*60)
        print("STEP 5: Feature Importance Analysis")
        print("-"*60)

        importance = rf.get_feature_importance(
            feature_names=feature_names,
            X=X_test,
            y=y_test,
            compute_permutation=True,
            n_repeats=10
        )
        print_feature_importance(importance)

        # Log feature importance to MLflow
        if tracker:
            tracker.log_feature_importance(
                feature_names=feature_names,
                importance_scores=importance.mdi_importance,
                importance_type="mdi",
                top_n=30
            )

        # Find optimal threshold
        print("\n" + "-"*60)
        print("STEP 6: Optimal Threshold Search")
        print("-"*60)

        opt_threshold, opt_f1 = rf.get_optimal_threshold(X_test, y_test, metric='f1')
        print(f"Optimal threshold for F1: {opt_threshold:.4f} (F1: {opt_f1:.4f})")

        if tracker:
            mlflow.log_params({
                "optimal_threshold": opt_threshold,
                "optimal_f1_score": opt_f1,
            })

        # Save model
        print("\n" + "-"*60)
        print("STEP 7: Saving Model")
        print("-"*60)

        os.makedirs(MODELS_DIR, exist_ok=True)
        rf.save(MODEL_OUTPUT_PATH.replace('.joblib', ''))
        print(f"Model saved to: {MODEL_OUTPUT_PATH}")

        # Log model to MLflow
        if tracker:
            tracker.log_model(
                model=rf.model,  # The underlying sklearn model
                model_name="random_forest",
                signature_input=X_test[:5],
                signature_output=rf.predict(X_test[:5]),
                register=False  # Don't register automatically
            )
            # Log training report
            tracker.log_training_report({
                "model_type": "random_forest",
                "n_samples": len(samples),
                "n_train": len(y_train),
                "n_test": len(y_test),
                "n_features": len(feature_names),
                "class_weights": class_weights,
                "metrics": {
                    "accuracy": metrics.accuracy,
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                    "roc_auc": metrics.roc_auc,
                    "average_precision": metrics.average_precision,
                },
                "optimal_threshold": opt_threshold,
                "hyperparameters": best_params if best_params else {
                    "n_estimators": 200,
                    "max_depth": None,
                    "min_samples_split": 5,
                    "min_samples_leaf": 2,
                },
                "top_features": [
                    {"name": name, "importance": float(imp)}
                    for name, imp in importance.get_top_features(30)
                ]
            })

        # Save preprocessing objects
        import joblib
        preprocessing_path = os.path.join(MODELS_DIR, 'preprocessing.joblib')
        joblib.dump({
            'scaler': scaler,
            'imputer': imputer,
            'feature_names': feature_names,
            'optimal_threshold': opt_threshold,
            'training_metadata': {
                'n_samples': len(samples),
                'n_train': len(y_train),
                'n_test': len(y_test),
                'n_features': len(feature_names),
                'class_weights': class_weights,
                'trained_at': datetime.utcnow().isoformat(),
                'labeled_dataset_path': LABELED_DATASET_PATH,
                'mlflow_run_id': mlflow_run_id if tracker else None,
            }
        }, preprocessing_path)
        print(f"Preprocessing saved to: {preprocessing_path}")

        # Save metrics report
        metrics_path = os.path.join(MODELS_DIR, 'training_metrics.json')
        with open(metrics_path, 'w') as f:
            json.dump({
                'accuracy': metrics.accuracy,
                'precision': metrics.precision,
                'recall': metrics.recall,
                'f1': metrics.f1,
                'roc_auc': metrics.roc_auc,
                'average_precision': metrics.average_precision,
                'cv_mean': metrics.cv_mean,
                'cv_std': metrics.cv_std,
                'optimal_threshold': opt_threshold,
                'confusion_matrix': metrics.confusion_matrix.tolist(),
                'top_features': [
                    {'name': name, 'importance': imp}
                    for name, imp in importance.get_top_features(30)
                ],
                'training_completed_at': datetime.utcnow().isoformat(),
                'mlflow_run_id': mlflow_run_id if tracker else None,
            }, f, indent=2)
        print(f"Metrics saved to: {metrics_path}")

        # End MLflow run
        if tracker:
            tracker.end_run("FINISHED")
            print(f"\nMLflow Run ID: {mlflow_run_id}")
            print(f"View results: mlflow ui --port 5000")

        print("\n" + "="*70)
        print("TRAINING COMPLETED SUCCESSFULLY")
        print("="*70)
        print(f"\nSummary:")
        print(f"  Samples used:     {len(tender_ids)}")
        print(f"  Train/Test split: {len(y_train)}/{len(y_test)}")
        print(f"  Features:         {len(feature_names)}")
        print(f"  ROC-AUC:          {metrics.roc_auc:.4f}")
        print(f"  F1 Score:         {metrics.f1:.4f}")
        print(f"  Model saved to:   {MODEL_OUTPUT_PATH}")
        if tracker and mlflow_run_id:
            print(f"  MLflow Run ID:    {mlflow_run_id}")

        return rf, metrics, importance

    except Exception as e:
        # End MLflow run with FAILED status on error
        if tracker and mlflow_run_id:
            tracker.end_run("FAILED")
        raise

    finally:
        await pool.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Train Random Forest model from labeled dataset'
    )
    parser.add_argument(
        '--tune',
        action='store_true',
        help='Enable hyperparameter tuning (slower but potentially better)'
    )
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.2,
        help='Fraction of data for testing (default: 0.2)'
    )
    parser.add_argument(
        '--cv-folds',
        type=int,
        default=5,
        help='Number of cross-validation folds (default: 5)'
    )
    parser.add_argument(
        '--no-mlflow',
        action='store_true',
        help='Disable MLflow experiment tracking'
    )

    args = parser.parse_args()

    # Check if labeled dataset exists
    if not os.path.exists(LABELED_DATASET_PATH):
        print(f"ERROR: Labeled dataset not found at {LABELED_DATASET_PATH}")
        print(f"Please run create_labeled_dataset.py first:")
        print(f"  cd {GROUND_TRUTH_DIR}")
        print(f"  python create_labeled_dataset.py")
        sys.exit(1)

    # Run training
    use_mlflow = not args.no_mlflow and MLFLOW_AVAILABLE
    if not use_mlflow:
        print("MLflow tracking disabled" if args.no_mlflow else "MLflow not available")

    asyncio.run(train_model(
        tune_hyperparameters=args.tune,
        test_size=args.test_size,
        n_cv_folds=args.cv_folds,
        use_mlflow=use_mlflow
    ))


if __name__ == "__main__":
    main()
