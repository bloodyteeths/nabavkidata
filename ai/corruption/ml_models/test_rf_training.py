#!/usr/bin/env python3
"""
Test Random Forest Training Pipeline with Synthetic Data

This script validates the training pipeline works correctly using
synthetic data that mimics the structure of real corruption detection features.

Run this to test the pipeline without database access:
    python test_rf_training.py

Author: NabavkiData
"""

import os
import sys
import json
import tempfile
import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai.corruption.ml_models.random_forest import (
    CorruptionRandomForest,
    ModelMetrics,
    FeatureImportance,
    quick_train_random_forest
)
from ai.corruption.features.feature_extractor import FeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_synthetic_data(
    n_samples: int = 5000,
    n_features: int = 113,
    corruption_rate: float = 0.15,
    random_seed: int = 42
):
    """
    Generate synthetic data that mimics corruption detection features.

    Creates data where corruption indicators correlate with the label,
    simulating realistic feature patterns.

    Args:
        n_samples: Number of samples to generate
        n_features: Number of features (should match real feature count)
        corruption_rate: Proportion of corrupt samples
        random_seed: Random seed

    Returns:
        Tuple of (X, y, feature_names)
    """
    np.random.seed(random_seed)

    # Get real feature names
    class MockPool:
        pass
    extractor = FeatureExtractor(MockPool())
    feature_names = extractor.feature_names

    # Generate base features (random normal)
    X = np.random.randn(n_samples, n_features)

    # Generate labels with specified corruption rate
    n_corrupt = int(n_samples * corruption_rate)
    y = np.zeros(n_samples, dtype=np.int32)
    corrupt_indices = np.random.choice(n_samples, n_corrupt, replace=False)
    y[corrupt_indices] = 1

    # Add correlations for key corruption indicators
    # These features should be more extreme for corrupt tenders

    feature_to_idx = {name: i for i, name in enumerate(feature_names)}

    # Single bidder is strong corruption signal
    if 'single_bidder' in feature_to_idx:
        idx = feature_to_idx['single_bidder']
        X[corrupt_indices, idx] += 2.0

    # High win rate at institution
    if 'winner_high_win_rate' in feature_to_idx:
        idx = feature_to_idx['winner_high_win_rate']
        X[corrupt_indices, idx] += 1.5

    # Very high win rate
    if 'winner_very_high_win_rate' in feature_to_idx:
        idx = feature_to_idx['winner_very_high_win_rate']
        X[corrupt_indices, idx] += 1.8

    # Price exact match to estimate
    if 'price_exact_match_estimate' in feature_to_idx:
        idx = feature_to_idx['price_exact_match_estimate']
        X[corrupt_indices, idx] += 1.5

    # Low bid variance (collusion signal)
    if 'bid_low_variance' in feature_to_idx:
        idx = feature_to_idx['bid_low_variance']
        X[corrupt_indices, idx] += 1.2

    # Short deadline
    if 'deadline_very_short' in feature_to_idx:
        idx = feature_to_idx['deadline_very_short']
        X[corrupt_indices, idx] += 1.0

    # Repeat winner
    if 'winner_prev_wins_at_institution' in feature_to_idx:
        idx = feature_to_idx['winner_prev_wins_at_institution']
        X[corrupt_indices, idx] += 1.5

    # Dominant supplier
    if 'winner_dominant_supplier' in feature_to_idx:
        idx = feature_to_idx['winner_dominant_supplier']
        X[corrupt_indices, idx] += 1.3

    # Related bidders
    if 'has_related_bidders' in feature_to_idx:
        idx = feature_to_idx['has_related_bidders']
        X[corrupt_indices, idx] += 1.0

    # Add some noise
    X += np.random.randn(n_samples, n_features) * 0.1

    # Add some missing values (5% of data)
    missing_mask = np.random.random((n_samples, n_features)) < 0.05
    X[missing_mask] = np.nan

    logger.info(f"Generated {n_samples} samples with {n_features} features")
    logger.info(f"Corruption rate: {y.mean()*100:.1f}% ({y.sum()} corrupt)")

    return X, y, feature_names


def test_pipeline():
    """Test the complete training pipeline."""
    logger.info("=" * 60)
    logger.info("Testing Random Forest Training Pipeline")
    logger.info("=" * 60)

    # Generate synthetic data
    X, y, feature_names = generate_synthetic_data(
        n_samples=5000,
        corruption_rate=0.15
    )

    # Split data
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logger.info(f"\nTrain: {len(y_train)} samples ({y_train.sum()} corrupt)")
    logger.info(f"Test:  {len(y_test)} samples ({y_test.sum()} corrupt)")

    # Preprocess: Handle missing values
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    imputer = SimpleImputer(strategy='median')
    X_train = imputer.fit_transform(X_train)
    X_test = imputer.transform(X_test)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # Test 1: Basic training with cross-validation
    logger.info("\n" + "-" * 40)
    logger.info("Test 1: Basic Training with Cross-Validation")
    logger.info("-" * 40)

    rf = CorruptionRandomForest(
        n_estimators=100,  # Fewer trees for speed
        max_depth=15,
        class_weight='balanced'
    )

    rf, cv_scores = rf.fit_with_cv(
        X_train, y_train,
        n_folds=5,
        feature_names=feature_names
    )

    logger.info(f"CV ROC-AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})")

    # Test 2: Evaluate on test set
    logger.info("\n" + "-" * 40)
    logger.info("Test 2: Evaluation on Test Set")
    logger.info("-" * 40)

    metrics = rf.evaluate(X_test, y_test)

    logger.info(f"Accuracy:          {metrics.accuracy:.4f}")
    logger.info(f"Precision:         {metrics.precision:.4f}")
    logger.info(f"Recall:            {metrics.recall:.4f}")
    logger.info(f"F1 Score:          {metrics.f1:.4f}")
    logger.info(f"ROC-AUC:           {metrics.roc_auc:.4f}")
    logger.info(f"Average Precision: {metrics.average_precision:.4f}")
    logger.info(f"\nClassification Report:\n{metrics.classification_report}")

    # Test 3: Feature importance
    logger.info("\n" + "-" * 40)
    logger.info("Test 3: Feature Importance")
    logger.info("-" * 40)

    importance = rf.get_feature_importance(
        feature_names=feature_names,
        X=X_test,
        y=y_test,
        compute_permutation=True,
        n_repeats=5
    )

    logger.info("\nTop 10 Features (MDI):")
    for name, imp in importance.get_top_features(10, 'mdi'):
        logger.info(f"  {name}: {imp:.4f}")

    logger.info("\nTop 10 Features (Permutation):")
    for name, imp in importance.get_top_features(10, 'permutation'):
        logger.info(f"  {name}: {imp:.4f}")

    # Test 4: Prediction with confidence
    logger.info("\n" + "-" * 40)
    logger.info("Test 4: Prediction with Confidence")
    logger.info("-" * 40)

    results = rf.predict_with_confidence(X_test[:5])
    for i, r in enumerate(results):
        logger.info(f"Sample {i}: prediction={r['prediction']}, "
                   f"probability={r['probability']:.4f}, "
                   f"confidence={r['confidence']:.4f}")

    # Test 5: Optimal threshold
    logger.info("\n" + "-" * 40)
    logger.info("Test 5: Optimal Threshold Selection")
    logger.info("-" * 40)

    opt_threshold, opt_score = rf.get_optimal_threshold(X_test, y_test, metric='f1')
    logger.info(f"Optimal threshold for F1: {opt_threshold:.4f} (score: {opt_score:.4f})")

    # Test 6: Save and load model
    logger.info("\n" + "-" * 40)
    logger.info("Test 6: Model Persistence")
    logger.info("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "test_model")
        rf.save(model_path)
        logger.info(f"Model saved to: {model_path}.joblib")

        # Load model
        rf_loaded = CorruptionRandomForest.load(model_path)
        logger.info(f"Model loaded, is_fitted: {rf_loaded.is_fitted}")

        # Verify predictions match
        y_pred_original = rf.predict(X_test[:10])
        y_pred_loaded = rf_loaded.predict(X_test[:10])
        assert np.array_equal(y_pred_original, y_pred_loaded), "Predictions don't match!"
        logger.info("Loaded model predictions match original!")

    # Test 7: Quick train helper function
    logger.info("\n" + "-" * 40)
    logger.info("Test 7: Quick Train Helper Function")
    logger.info("-" * 40)

    rf_quick, metrics_quick, importance_quick = quick_train_random_forest(
        X_train, y_train, X_test, y_test,
        feature_names=feature_names,
        tune_hyperparameters=False
    )

    logger.info(f"Quick train - Test F1: {metrics_quick.f1:.4f}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("ALL TESTS PASSED!")
    logger.info("=" * 60)

    return {
        'status': 'success',
        'cv_roc_auc': float(cv_scores.mean()),
        'test_f1': metrics.f1,
        'test_roc_auc': metrics.roc_auc,
        'test_precision': metrics.precision,
        'test_recall': metrics.recall
    }


def test_hyperparameter_tuning():
    """Test hyperparameter tuning with a small grid."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Hyperparameter Tuning (Small Grid)")
    logger.info("=" * 60)

    # Generate smaller dataset for faster tuning
    X, y, feature_names = generate_synthetic_data(
        n_samples=2000,
        corruption_rate=0.15
    )

    # Preprocess
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    imputer = SimpleImputer(strategy='median')
    X = imputer.fit_transform(X)

    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    # Small parameter grid
    param_grid = {
        'n_estimators': [50, 100],
        'max_depth': [10, 20],
        'min_samples_leaf': [1, 2]
    }

    rf = CorruptionRandomForest()
    rf, best_params = rf.hyperparameter_tune(
        X, y,
        param_grid=param_grid,
        n_folds=3
    )

    logger.info(f"\nBest parameters: {best_params}")
    logger.info(f"Model summary: {json.dumps(rf.get_model_summary(), indent=2, default=str)}")

    return {
        'status': 'success',
        'best_params': best_params
    }


if __name__ == '__main__':
    # Run all tests
    try:
        results = test_pipeline()
        print(f"\n\nPipeline test results: {json.dumps(results, indent=2)}")

        tuning_results = test_hyperparameter_tuning()
        print(f"\n\nHyperparameter tuning results: {json.dumps(tuning_results, indent=2)}")

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
