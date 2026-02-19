"""
Batch Prediction Script

Re-analyzes all tenders in the database using trained ML models.
Stores predictions in ml_predictions table.
"""

import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

import asyncpg
import joblib
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
MODELS_DIR = Path(__file__).parent / "models"
RF_MODEL_PATH = MODELS_DIR / "random_forest.joblib"
XGB_MODEL_PATH = MODELS_DIR / "xgboost.joblib"
PREPROCESSING_PATH = MODELS_DIR / "preprocessing.joblib"

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL")
)


def load_models():
    """Load trained models and preprocessor."""
    models = {}

    if RF_MODEL_PATH.exists():
        rf_data = joblib.load(RF_MODEL_PATH)
        # Handle both direct model and dict wrapper
        if isinstance(rf_data, dict) and 'model' in rf_data:
            models['random_forest'] = rf_data['model']
        else:
            models['random_forest'] = rf_data
        logger.info("Loaded Random Forest model")

    if XGB_MODEL_PATH.exists():
        xgb_data = joblib.load(XGB_MODEL_PATH)
        # Handle both direct model and dict wrapper
        if isinstance(xgb_data, dict) and 'model' in xgb_data:
            models['xgboost'] = xgb_data['model']
        else:
            models['xgboost'] = xgb_data
        logger.info("Loaded XGBoost model")

    preprocessor = None
    if PREPROCESSING_PATH.exists():
        preprocessor = joblib.load(PREPROCESSING_PATH)
        logger.info("Loaded preprocessor")

    return models, preprocessor


def extract_features(tender: Dict) -> Dict[str, float]:
    """Extract ML features from tender data matching XGBoost model expectations.

    XGBoost expects 20 features:
    ['has_winner', 'num_bidders', 'single_bidder', 'bidder_count',
     'estimated_value_mkd', 'actual_value_mkd', 'has_price_data', 'price_deviation',
     'price_ratio', 'bid_mean', 'bid_std', 'bid_cv', 'deadline_days', 'short_deadline',
     'num_documents', 'amendment_count', 'has_amendments', 'flag_count',
     'max_flag_score', 'avg_flag_score']
    """
    num_bidders = tender.get('num_bidders') or 0
    estimated_value = float(tender.get('estimated_value_mkd') or 0)
    actual_value = float(tender.get('actual_value_mkd') or 0)
    flag_count = tender.get('flag_count') or 0
    max_flag_score = float(tender.get('max_flag_score') or 0)

    # Calculate price ratio and deviation
    price_ratio = 1.0
    price_deviation = 0.0
    if estimated_value > 0 and actual_value > 0:
        price_ratio = actual_value / estimated_value
        price_deviation = abs(price_ratio - 1.0)

    # Calculate deadline days
    deadline_days = 30  # Default
    if tender.get('publication_date') and tender.get('closing_date'):
        try:
            pub = pd.to_datetime(tender['publication_date'])
            closing = pd.to_datetime(tender['closing_date'])
            deadline_days = (closing - pub).days
        except:
            pass

    features = {
        # Core features matching XGBoost model
        'has_winner': 1 if tender.get('winner') else 0,
        'num_bidders': num_bidders,
        'single_bidder': 1 if num_bidders == 1 else 0,
        'bidder_count': num_bidders,

        # Price features
        'estimated_value_mkd': estimated_value,
        'actual_value_mkd': actual_value,
        'has_price_data': 1 if (estimated_value > 0 or actual_value > 0) else 0,
        'price_deviation': price_deviation,
        'price_ratio': price_ratio,

        # Bid statistics (defaults since we don't have individual bids)
        'bid_mean': actual_value if actual_value > 0 else estimated_value,
        'bid_std': 0.0,  # No bid variance data available
        'bid_cv': 0.0,   # Coefficient of variation

        # Timing
        'deadline_days': deadline_days,
        'short_deadline': 1 if deadline_days < 15 else 0,

        # Procedural
        'num_documents': tender.get('num_documents') or 0,
        'amendment_count': tender.get('amendment_count') or 0,
        'has_amendments': 1 if (tender.get('amendment_count') or 0) > 0 else 0,

        # Risk flags
        'flag_count': flag_count,
        'max_flag_score': max_flag_score,
        'avg_flag_score': max_flag_score if flag_count > 0 else 0.0,
    }

    return features


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


async def get_tenders_batch(conn, offset: int, limit: int, skip_existing: bool = True) -> List[Dict]:
    """Fetch a batch of tenders from the database, optionally skipping already predicted ones."""
    if skip_existing:
        # Skip tenders that already have predictions
        query = """
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.winner,
                t.status,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.publication_date,
                t.closing_date,
                t.num_bidders,
                t.has_lots,
                0 as amendment_count,
                (SELECT COUNT(*) FROM documents d WHERE d.tender_id = t.tender_id) as num_documents,
                (SELECT COUNT(*) FROM corruption_flags cf WHERE cf.tender_id = t.tender_id) as flag_count,
                (SELECT COALESCE(MAX(score), 0) FROM corruption_flags cf WHERE cf.tender_id = t.tender_id) as max_flag_score
            FROM tenders t
            WHERE NOT EXISTS (
                SELECT 1 FROM ml_predictions mp
                WHERE mp.tender_id = t.tender_id AND mp.model_version = 'xgboost_rf_v1'
            )
            ORDER BY t.tender_id
            LIMIT $1
        """
        rows = await conn.fetch(query, limit)
    else:
        query = """
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.winner,
                t.status,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.publication_date,
                t.closing_date,
                t.num_bidders,
                t.has_lots,
                0 as amendment_count,
                (SELECT COUNT(*) FROM documents d WHERE d.tender_id = t.tender_id) as num_documents,
                (SELECT COUNT(*) FROM corruption_flags cf WHERE cf.tender_id = t.tender_id) as flag_count,
                (SELECT COALESCE(MAX(score), 0) FROM corruption_flags cf WHERE cf.tender_id = t.tender_id) as max_flag_score
            FROM tenders t
            ORDER BY t.tender_id
            OFFSET $1
            LIMIT $2
        """
        rows = await conn.fetch(query, offset, limit)
    return [dict(row) for row in rows]


async def save_predictions(conn, predictions: List[Dict]):
    """Save predictions to ml_predictions table."""
    if not predictions:
        return

    # Group predictions by tender_id and combine model scores
    tender_predictions = {}
    for pred in predictions:
        tid = pred['tender_id']
        if tid not in tender_predictions:
            tender_predictions[tid] = {
                'tender_id': tid,
                'risk_score': pred['risk_score'],
                'risk_level': pred['risk_level'],
                'confidence': pred['confidence'],
                'model_scores': {},
                'top_features': pred.get('top_features', []),
                'feature_importance': pred.get('feature_importance', {}),
            }
        # Add model score
        tender_predictions[tid]['model_scores'][pred['model_name']] = pred['confidence']
        # Use highest score
        if pred['risk_score'] > tender_predictions[tid]['risk_score']:
            tender_predictions[tid]['risk_score'] = pred['risk_score']
            tender_predictions[tid]['risk_level'] = pred['risk_level']
            tender_predictions[tid]['confidence'] = pred['confidence']

    # Upsert predictions
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

    for pred in tender_predictions.values():
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


async def run_batch_predictions(batch_size: int = 1000, max_tenders: Optional[int] = None):
    """Run batch predictions on all tenders."""

    # Load models
    models, preprocessor = load_models()

    if not models:
        logger.error("No models loaded. Please train models first.")
        return

    # Use only XGBoost model (RandomForest has 113 features which we can't easily recreate)
    if 'random_forest' in models:
        del models['random_forest']
        logger.info("Skipping RandomForest (needs 113 features)")

    # XGBoost feature names in correct order
    feature_names = [
        'has_winner', 'num_bidders', 'single_bidder', 'bidder_count',
        'estimated_value_mkd', 'actual_value_mkd', 'has_price_data', 'price_deviation',
        'price_ratio', 'bid_mean', 'bid_std', 'bid_cv', 'deadline_days', 'short_deadline',
        'num_documents', 'amendment_count', 'has_amendments', 'flag_count',
        'max_flag_score', 'avg_flag_score'
    ]

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get remaining count (skip already processed)
        remaining_count = await conn.fetchval("""
            SELECT COUNT(*) FROM tenders t
            WHERE NOT EXISTS (
                SELECT 1 FROM ml_predictions mp
                WHERE mp.tender_id = t.tender_id AND mp.model_version = 'xgboost_rf_v1'
            )
        """)
        already_done = await conn.fetchval(
            "SELECT COUNT(*) FROM ml_predictions WHERE model_version = 'xgboost_rf_v1'"
        )

        logger.info(f"Already processed: {already_done:,}, Remaining: {remaining_count:,}")

        if max_tenders:
            remaining_count = min(remaining_count, max_tenders)

        if remaining_count == 0:
            logger.info("All tenders already processed!")
            return

        processed = 0

        while processed < remaining_count:
            # Fetch batch (skipping already processed)
            try:
                tenders = await get_tenders_batch(conn, 0, batch_size, skip_existing=True)
            except Exception as e:
                logger.error(f"Connection error, reconnecting: {e}")
                await conn.close()
                conn = await asyncpg.connect(DATABASE_URL)
                continue

            if not tenders:
                break

            # Extract features
            features_list = []
            tender_ids = []

            for tender in tenders:
                features = extract_features(tender)
                features_list.append(features)
                tender_ids.append(tender['tender_id'])

            # Create DataFrame
            df = pd.DataFrame(features_list)

            # Ensure correct column order if we have feature names
            if feature_names:
                for fn in feature_names:
                    if fn not in df.columns:
                        df[fn] = 0
                df = df[feature_names]

            # Make predictions
            predictions = []

            for model_name, model in models.items():
                try:
                    # Predict probabilities
                    if hasattr(model, 'predict_proba'):
                        probs = model.predict_proba(df)[:, 1]
                    else:
                        probs = model.predict(df)

                    # Create prediction records
                    for i, (tender_id, prob) in enumerate(zip(tender_ids, probs)):
                        prob = float(prob)
                        risk_level = get_risk_level(prob)

                        # Get feature importance for this prediction
                        feature_imp = {}
                        if hasattr(model, 'feature_importances_'):
                            for j, (fname, imp) in enumerate(zip(df.columns, model.feature_importances_)):
                                feature_imp[fname] = float(imp)

                        predictions.append({
                            'tender_id': tender_id,
                            'model_name': model_name,
                            'risk_score': int(prob * 100),
                            'risk_level': risk_level,
                            'confidence': prob,
                            'model_scores': {'probability': prob},
                            'top_features': list(feature_imp.keys())[:10] if feature_imp else [],
                            'feature_importance': feature_imp
                        })
                except Exception as e:
                    logger.error(f"Error predicting with {model_name}: {e}")

            # Save predictions
            try:
                await save_predictions(conn, predictions)
            except Exception as e:
                logger.error(f"Error saving batch, reconnecting: {e}")
                await conn.close()
                conn = await asyncpg.connect(DATABASE_URL)
                continue

            processed += len(tenders)

            if processed % 10000 == 0:
                logger.info(f"Processed {processed:,}/{remaining_count:,} tenders ({100*processed/remaining_count:.1f}%)")

        logger.info(f"Completed! Processed {processed:,} tenders")

    finally:
        await conn.close()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Batch predict tender risk scores')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size')
    parser.add_argument('--max-tenders', type=int, default=None, help='Max tenders to process')

    args = parser.parse_args()

    await run_batch_predictions(
        batch_size=args.batch_size,
        max_tenders=args.max_tenders
    )


if __name__ == "__main__":
    asyncio.run(main())
