"""
Batch Prediction Script - Using Real Data Models

Re-analyzes all tenders in the database using trained ML models.
Uses the proper FeatureExtractor with 113 features.
"""

import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
import joblib
import numpy as np

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
XGB_MODEL_PATH = MODELS_DIR / "xgboost_real.joblib"
RF_MODEL_PATH = MODELS_DIR / "random_forest_real.joblib"

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL")
)


def load_models():
    """Load trained models with preprocessing."""
    models = {}

    if XGB_MODEL_PATH.exists():
        xgb_package = joblib.load(XGB_MODEL_PATH)
        models['xgboost'] = {
            'model': xgb_package['model'],
            'imputer': xgb_package['imputer'],
            'scaler': xgb_package['scaler'],
            'feature_names': xgb_package['feature_names']
        }
        logger.info(f"Loaded XGBoost model ({len(xgb_package['feature_names'])} features)")

    if RF_MODEL_PATH.exists():
        rf_package = joblib.load(RF_MODEL_PATH)
        models['random_forest'] = {
            'model': rf_package['model'],
            'imputer': rf_package['imputer'],
            'scaler': rf_package['scaler'],
            'feature_names': rf_package['feature_names']
        }
        logger.info(f"Loaded Random Forest model ({len(rf_package['feature_names'])} features)")

    return models


def get_risk_level(probability: float) -> str:
    """Convert probability to risk level."""
    if probability >= 0.8:
        return "critical"
    elif probability >= 0.6:
        return "high"
    elif probability >= 0.4:
        return "medium"
    elif probability >= 0.2:
        return "low"
    return "minimal"


async def get_tenders_batch(conn, limit: int, skip_existing: bool = True) -> List[Dict]:
    """Fetch a batch of tenders, optionally skipping already predicted ones."""
    if skip_existing:
        query = """
            SELECT tender_id
            FROM tenders
            WHERE status IN ('awarded', 'closed', 'completed')
              AND NOT EXISTS (
                  SELECT 1 FROM ml_predictions mp
                  WHERE mp.tender_id = tenders.tender_id
                    AND mp.model_version = 'xgboost_rf_v1'
              )
            ORDER BY tender_id
            LIMIT $1
        """
        rows = await conn.fetch(query, limit)
    else:
        query = """
            SELECT tender_id
            FROM tenders
            WHERE status IN ('awarded', 'closed', 'completed')
            ORDER BY tender_id
            LIMIT $1
        """
        rows = await conn.fetch(query, limit)

    return [row['tender_id'] for row in rows]


async def save_predictions(conn, predictions: List[Dict]):
    """Save predictions to ml_predictions table."""
    if not predictions:
        return

    query = """
        INSERT INTO ml_predictions (
            tender_id, risk_score, risk_level, confidence,
            model_scores, top_features, feature_importance,
            model_version, ensemble_type, predicted_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (tender_id, model_version)
        DO UPDATE SET
            risk_score = EXCLUDED.risk_score,
            risk_level = EXCLUDED.risk_level,
            confidence = EXCLUDED.confidence,
            model_scores = EXCLUDED.model_scores,
            top_features = EXCLUDED.top_features,
            feature_importance = EXCLUDED.feature_importance,
            predicted_at = EXCLUDED.predicted_at,
            updated_at = now()
    """

    for pred in predictions:
        try:
            await conn.execute(
                query,
                pred['tender_id'],
                pred['risk_score'],
                pred['risk_level'],
                pred['confidence'],
                json.dumps(pred.get('model_scores', {})),
                json.dumps(pred.get('top_features', [])),
                json.dumps(pred.get('feature_importance', {})),
                'xgboost_rf_v1',
                'ensemble',
                datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Error saving prediction for {pred['tender_id']}: {e}")


async def run_batch_predictions(
    batch_size: int = 100,
    max_tenders: Optional[int] = None,
    skip_existing: bool = True
):
    """Run batch predictions on all tenders."""

    # Load models
    models = load_models()

    if not models:
        logger.error("No models loaded. Please train models first.")
        return

    # Use XGBoost as primary model
    primary_model = models.get('xgboost') or models.get('random_forest')
    if not primary_model:
        logger.error("No valid model found")
        return

    model = primary_model['model']
    imputer = primary_model['imputer']
    scaler = primary_model['scaler']
    feature_names = primary_model['feature_names']

    # Connect to database
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)

    try:
        # Initialize feature extractor
        extractor = FeatureExtractor(pool)

        async with pool.acquire() as conn:
            # Get count
            if skip_existing:
                remaining_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM tenders
                    WHERE status IN ('awarded', 'closed', 'completed')
                      AND NOT EXISTS (
                          SELECT 1 FROM ml_predictions mp
                          WHERE mp.tender_id = tenders.tender_id
                            AND mp.model_version = 'xgboost_rf_v1'
                      )
                """)
                already_done = await conn.fetchval(
                    "SELECT COUNT(*) FROM ml_predictions WHERE model_version = 'xgboost_rf_v1'"
                )
                logger.info(f"Already processed: {already_done:,}, Remaining: {remaining_count:,}")
            else:
                remaining_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM tenders WHERE status IN ('awarded', 'closed', 'completed')"
                )
                logger.info(f"Total tenders: {remaining_count:,}")

            if max_tenders:
                remaining_count = min(remaining_count, max_tenders)

            if remaining_count == 0:
                logger.info("All tenders already processed!")
                return

            processed = 0
            failed = 0

            while processed < remaining_count:
                # Fetch batch of tender IDs
                tender_ids = await get_tenders_batch(conn, batch_size, skip_existing)

                if not tender_ids:
                    break

                # Extract features for batch
                features_list = []
                valid_ids = []

                for tender_id in tender_ids:
                    try:
                        fv = await extractor.extract_features(tender_id, include_metadata=False)
                        features_list.append(fv.feature_array)
                        valid_ids.append(tender_id)
                    except Exception as e:
                        failed += 1
                        if failed <= 5:
                            logger.warning(f"Failed to extract features for {tender_id}: {e}")

                if not features_list:
                    continue

                # Prepare features
                X = np.array(features_list)
                X = np.nan_to_num(X, nan=0, posinf=0, neginf=0)
                X = imputer.transform(X)
                X = scaler.transform(X)

                # Predict
                try:
                    probs = model.predict_proba(X)[:, 1]
                except Exception as e:
                    logger.error(f"Prediction failed: {e}")
                    continue

                # Create prediction records
                predictions = []
                for tender_id, prob in zip(valid_ids, probs):
                    prob = float(prob)
                    risk_level = get_risk_level(prob)

                    predictions.append({
                        'tender_id': tender_id,
                        'risk_score': int(prob * 100),
                        'risk_level': risk_level,
                        'confidence': prob,
                        'model_scores': {'xgboost': prob},
                        'top_features': feature_names[:10],
                        'feature_importance': {}
                    })

                # Save predictions
                try:
                    await save_predictions(conn, predictions)
                except Exception as e:
                    logger.error(f"Error saving batch: {e}")
                    continue

                processed += len(valid_ids)

                if processed % 500 == 0:
                    logger.info(f"Processed {processed:,}/{remaining_count:,} tenders ({100*processed/remaining_count:.1f}%), {failed} failed")

            logger.info(f"Completed! Processed {processed:,} tenders, {failed} failed")

    finally:
        await pool.close()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Batch predict tender risk scores with real models')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size')
    parser.add_argument('--max-tenders', type=int, default=None, help='Max tenders to process')
    parser.add_argument('--reprocess', action='store_true', help='Reprocess already predicted tenders')

    args = parser.parse_args()

    await run_batch_predictions(
        batch_size=args.batch_size,
        max_tenders=args.max_tenders,
        skip_existing=not args.reprocess
    )


if __name__ == "__main__":
    asyncio.run(main())
