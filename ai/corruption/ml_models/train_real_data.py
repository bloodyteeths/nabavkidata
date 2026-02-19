"""
Proper ML Training on Real Data

This script trains corruption detection models using:
1. Real labeled data from corruption_flags table (not synthetic)
2. Full FeatureExtractor with 112 features (not simplified 20)
3. Proper train/test split with stratification
4. Cross-validation with real metrics

Author: nabavkidata.com
"""

import os
from dotenv import load_dotenv
load_dotenv()
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import asyncpg
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from features.feature_extractor import FeatureExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL")
)
async def create_labeled_dataset(
    pool: asyncpg.Pool,
    positive_min_score: int = 30,  # Lower threshold to get more positive samples
    max_samples_per_class: int = 5000,
    balanced: bool = True
) -> Tuple[List[str], List[int]]:
    """
    Create labeled dataset from real corruption flags.

    POSITIVE class (label=1): Tenders with corruption_flags score >= positive_min_score
    NEGATIVE class (label=0): Tenders with no flags AND >= negative_min_bidders bidders

    This uses real patterns from our rule-based detection, not synthetic data.
    """
    logger.info("Creating labeled dataset from real corruption flags...")

    async with pool.acquire() as conn:
        # Get POSITIVE samples: High-risk tenders with RELIABLE flags only
        # EXCLUDE single_bidder - unreliable due to missing bidder data from OpenTender/OCDS
        # Use only: short_deadline, price_anomaly, bid_clustering, repeat_winner
        positive_query = """
            SELECT tender_id FROM (
                SELECT DISTINCT t.tender_id
                FROM tenders t
                JOIN corruption_flags cf ON t.tender_id = cf.tender_id
                WHERE cf.flag_type IN ('short_deadline', 'price_anomaly', 'bid_clustering', 'repeat_winner')
                  AND cf.score >= $1
                  AND t.status IN ('awarded', 'closed', 'completed')
            ) sub
            ORDER BY RANDOM()
            LIMIT $2
        """
        positive_rows = await conn.fetch(positive_query, positive_min_score, max_samples_per_class)
        positive_ids = [row['tender_id'] for row in positive_rows]
        logger.info(f"Found {len(positive_ids)} positive samples (reliable flags, score >= {positive_min_score})")

        # Get NEGATIVE samples: Clean tenders - no RELIABLE flags
        # Can have single_bidder flag (unreliable) but not the others
        negative_query = """
            SELECT t.tender_id
            FROM tenders t
            WHERE t.status IN ('awarded', 'closed', 'completed')
              AND NOT EXISTS (
                  SELECT 1 FROM corruption_flags cf
                  WHERE cf.tender_id = t.tender_id
                    AND cf.flag_type IN ('short_deadline', 'price_anomaly', 'bid_clustering', 'repeat_winner')
              )
            ORDER BY RANDOM()
            LIMIT $1
        """
        neg_limit = len(positive_ids) * 3 if balanced else max_samples_per_class  # 3:1 ratio for better learning
        negative_rows = await conn.fetch(negative_query, neg_limit)
        negative_ids = [row['tender_id'] for row in negative_rows]
        logger.info(f"Found {len(negative_ids)} negative samples (no reliable flags)")

    # Combine
    tender_ids = positive_ids + negative_ids
    labels = [1] * len(positive_ids) + [0] * len(negative_ids)

    logger.info(f"Total dataset: {len(tender_ids)} samples ({len(positive_ids)} positive, {len(negative_ids)} negative)")
    return tender_ids, labels
async def extract_features_for_dataset(
    pool: asyncpg.Pool,
    tender_ids: List[str],
    batch_size: int = 100
) -> Tuple[np.ndarray, List[str], List[str]]:
    """
    Extract features for all tenders using the full FeatureExtractor.

    Returns:
        features: numpy array of shape (n_samples, n_features)
        feature_names: list of feature names
        valid_ids: list of tender IDs that were successfully extracted
    """
    logger.info(f"Extracting features for {len(tender_ids)} tenders...")

    extractor = FeatureExtractor(pool)
    feature_names = extractor.feature_names

    all_features = []
    valid_ids = []
    failed = 0

    for i in range(0, len(tender_ids), batch_size):
        batch_ids = tender_ids[i:i+batch_size]

        for tender_id in batch_ids:
            try:
                fv = await extractor.extract_features(tender_id, include_metadata=False)
                all_features.append(fv.feature_array)
                valid_ids.append(tender_id)
            except Exception as e:
                failed += 1
                if failed <= 5:
                    logger.warning(f"Failed to extract features for {tender_id}: {e}")

        if (i + batch_size) % 500 == 0:
            logger.info(f"Extracted features for {i + batch_size}/{len(tender_ids)} tenders")

    logger.info(f"Feature extraction complete: {len(valid_ids)} success, {failed} failed")

    if not all_features:
        raise ValueError("No features could be extracted")

    return np.array(all_features), feature_names, valid_ids
def preprocess_features(
    X_train: np.ndarray,
    X_test: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, SimpleImputer, StandardScaler]:
    """
    Preprocess features: impute missing values and scale.
    """
    # Impute NaN/inf values
    imputer = SimpleImputer(strategy='median')
    X_train_imp = imputer.fit_transform(np.nan_to_num(X_train, nan=0, posinf=0, neginf=0))
    X_test_imp = imputer.transform(np.nan_to_num(X_test, nan=0, posinf=0, neginf=0))

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_imp)
    X_test_scaled = scaler.transform(X_test_imp)

    return X_train_scaled, X_test_scaled, imputer, scaler
def train_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    feature_names: List[str]
) -> Tuple[XGBClassifier, Dict]:
    """
    Train XGBoost classifier with proper hyperparameters.
    """
    logger.info("Training XGBoost classifier...")

    # Model for cross-validation (no early stopping)
    cv_model = XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=1,
        gamma=0,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=1,
        random_state=42,
        n_jobs=-1
    )

    # Cross-validation first
    cv_scores = cross_val_score(cv_model, X_train, y_train, cv=5, scoring='roc_auc')

    # Final model with early stopping
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=1,
        gamma=0,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=1,
        random_state=42,
        n_jobs=-1,
        eval_metric='auc',
        early_stopping_rounds=20
    )

    # Split for early stopping
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=0.2, random_state=42, stratify=y_train
    )

    model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        verbose=False
    )

    # Feature importance
    importance = dict(zip(feature_names, model.feature_importances_))
    top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:20]

    metrics = {
        'cv_auc_mean': float(np.mean(cv_scores)),
        'cv_auc_std': float(np.std(cv_scores)),
        'cv_scores': [float(s) for s in cv_scores],
        'best_iteration': int(model.best_iteration) if hasattr(model, 'best_iteration') else 0,
        'top_features': top_features
    }

    logger.info(f"XGBoost CV AUC: {metrics['cv_auc_mean']:.4f} (+/- {metrics['cv_auc_std']:.4f})")

    return model, metrics
def train_random_forest(
    X_train: np.ndarray,
    y_train: np.ndarray,
    feature_names: List[str]
) -> Tuple[RandomForestClassifier, Dict]:
    """
    Train Random Forest classifier.
    """
    logger.info("Training Random Forest classifier...")

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features='sqrt',
        bootstrap=True,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='roc_auc')

    # Feature importance
    importance = dict(zip(feature_names, model.feature_importances_))
    top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:20]

    metrics = {
        'cv_auc_mean': float(np.mean(cv_scores)),
        'cv_auc_std': float(np.std(cv_scores)),
        'cv_scores': [float(s) for s in cv_scores],
        'n_estimators': model.n_estimators,
        'top_features': top_features
    }

    logger.info(f"Random Forest CV AUC: {metrics['cv_auc_mean']:.4f} (+/- {metrics['cv_auc_std']:.4f})")

    return model, metrics
def evaluate_model(
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_name: str
) -> Dict:
    """
    Evaluate model on test set.
    """
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    # Check for constant predictions
    unique_preds = np.unique(y_pred)
    unique_probs = len(np.unique(np.round(y_proba, 2)))

    if len(unique_preds) == 1:
        logger.warning(f"{model_name} outputs constant predictions! All samples predicted as {unique_preds[0]}")

    if unique_probs < 5:
        logger.warning(f"{model_name} has low probability diversity: only {unique_probs} unique values")

    metrics = {
        'accuracy': float(accuracy_score(y_test, y_pred)),
        'precision': float(precision_score(y_test, y_pred, zero_division=0)),
        'recall': float(recall_score(y_test, y_pred, zero_division=0)),
        'f1': float(f1_score(y_test, y_pred, zero_division=0)),
        'roc_auc': float(roc_auc_score(y_test, y_proba)),
        'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
        'unique_predictions': int(len(unique_preds)),
        'prob_min': float(y_proba.min()),
        'prob_max': float(y_proba.max()),
        'prob_std': float(y_proba.std())
    }

    logger.info(f"\n{model_name} Test Results:")
    logger.info(f"  Accuracy: {metrics['accuracy']:.4f}")
    logger.info(f"  Precision: {metrics['precision']:.4f}")
    logger.info(f"  Recall: {metrics['recall']:.4f}")
    logger.info(f"  F1: {metrics['f1']:.4f}")
    logger.info(f"  ROC AUC: {metrics['roc_auc']:.4f}")
    logger.info(f"  Prob range: [{metrics['prob_min']:.4f}, {metrics['prob_max']:.4f}] std={metrics['prob_std']:.4f}")
    logger.info(f"  Confusion Matrix:\n{confusion_matrix(y_test, y_pred)}")

    return metrics
async def main():
    """Main training pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description='Train corruption detection models on real data')
    parser.add_argument('--max-samples', type=int, default=5000, help='Max samples per class')
    parser.add_argument('--positive-min-score', type=int, default=30, help='Min corruption flag score for positive class')
    parser.add_argument('--test-size', type=float, default=0.2, help='Test set size')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("REAL DATA ML TRAINING PIPELINE")
    logger.info("=" * 60)
    logger.info("EXCLUDING single_bidder flag (unreliable due to missing OpenTender/OCDS data)")
    logger.info("Using only: short_deadline, price_anomaly, bid_clustering, repeat_winner")
    logger.info(f"Parameters:")
    logger.info(f"  Max samples per class: {args.max_samples}")
    logger.info(f"  Positive min score: {args.positive_min_score}")
    logger.info(f"  Test size: {args.test_size}")

    # Connect to database
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)

    try:
        # Step 1: Create labeled dataset (excluding unreliable single_bidder flag)
        tender_ids, labels = await create_labeled_dataset(
            pool,
            positive_min_score=args.positive_min_score,
            max_samples_per_class=args.max_samples,
            balanced=True
        )

        # Step 2: Extract features
        X, feature_names, valid_ids = await extract_features_for_dataset(pool, tender_ids)

        # Align labels with valid IDs
        id_to_label = dict(zip(tender_ids, labels))
        y = np.array([id_to_label[tid] for tid in valid_ids])

        logger.info(f"Final dataset: {len(y)} samples, {X.shape[1]} features")
        logger.info(f"Class distribution: {np.sum(y == 0)} negative, {np.sum(y == 1)} positive")

        # Step 3: Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=args.test_size, random_state=42, stratify=y
        )

        logger.info(f"Train set: {len(y_train)} samples")
        logger.info(f"Test set: {len(y_test)} samples")

        # Step 4: Preprocess
        X_train_scaled, X_test_scaled, imputer, scaler = preprocess_features(X_train, X_test)

        # Step 5: Train models
        xgb_model, xgb_train_metrics = train_xgboost(X_train_scaled, y_train, feature_names)
        rf_model, rf_train_metrics = train_random_forest(X_train_scaled, y_train, feature_names)

        # Step 6: Evaluate on test set
        xgb_test_metrics = evaluate_model(xgb_model, X_test_scaled, y_test, "XGBoost")
        rf_test_metrics = evaluate_model(rf_model, X_test_scaled, y_test, "Random Forest")

        # Step 7: Save models and metadata
        logger.info("\nSaving models...")

        # Save XGBoost
        xgb_package = {
            'model': xgb_model,
            'imputer': imputer,
            'scaler': scaler,
            'feature_names': feature_names,
            'n_features': len(feature_names),
            'trained_on': 'real_data',
            'is_synthetic': False
        }
        joblib.dump(xgb_package, MODELS_DIR / "xgboost_real.joblib")

        # Save Random Forest
        rf_package = {
            'model': rf_model,
            'imputer': imputer,
            'scaler': scaler,
            'feature_names': feature_names,
            'n_features': len(feature_names),
            'trained_on': 'real_data',
            'is_synthetic': False
        }
        joblib.dump(rf_package, MODELS_DIR / "random_forest_real.joblib")

        # Save preprocessing separately
        preprocessing = {
            'imputer': imputer,
            'scaler': scaler,
            'feature_names': feature_names,
            'n_features': len(feature_names)
        }
        joblib.dump(preprocessing, MODELS_DIR / "preprocessing_real.joblib")

        # Save metrics
        all_metrics = {
            'training_timestamp': datetime.utcnow().isoformat(),
            'dataset': {
                'total_samples': len(y),
                'positive_samples': int(np.sum(y == 1)),
                'negative_samples': int(np.sum(y == 0)),
                'n_features': len(feature_names),
                'feature_names': feature_names,
                'is_synthetic': False,
                'positive_min_score': args.positive_min_score,
                'label_strategy': 'reliable_flags_only (excludes single_bidder)'
            },
            'xgboost': {
                'train': xgb_train_metrics,
                'test': xgb_test_metrics
            },
            'random_forest': {
                'train': rf_train_metrics,
                'test': rf_test_metrics
            }
        }

        with open(MODELS_DIR / "training_metrics_real.json", 'w') as f:
            json.dump(all_metrics, f, indent=2, default=str)

        # Save feature importance
        pd.DataFrame(xgb_train_metrics['top_features'], columns=['feature', 'importance']).to_csv(
            MODELS_DIR / "xgboost_real_feature_importance.csv", index=False
        )
        pd.DataFrame(rf_train_metrics['top_features'], columns=['feature', 'importance']).to_csv(
            MODELS_DIR / "rf_real_feature_importance.csv", index=False
        )

        logger.info("\n" + "=" * 60)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Models saved to: {MODELS_DIR}")
        logger.info(f"XGBoost Test AUC: {xgb_test_metrics['roc_auc']:.4f}")
        logger.info(f"Random Forest Test AUC: {rf_test_metrics['roc_auc']:.4f}")

        # Sanity check
        if xgb_test_metrics['prob_std'] < 0.01:
            logger.error("WARNING: XGBoost predictions have very low variance - model may still be broken!")
        else:
            logger.info("XGBoost predictions have good variance - model is differentiating!")

        if rf_test_metrics['prob_std'] < 0.01:
            logger.error("WARNING: Random Forest predictions have very low variance - model may still be broken!")
        else:
            logger.info("Random Forest predictions have good variance - model is differentiating!")

    finally:
        await pool.close()
if __name__ == "__main__":
    asyncio.run(main())
