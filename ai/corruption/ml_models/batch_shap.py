"""
Batch SHAP Pre-computation Script

Pre-computes SHAP values for flagged/high-risk tenders and stores them
in the ml_shap_cache table for fast API lookups.

Designed to run as a cron job:
    python3 batch_shap.py --limit 500 --batch-size 50

Features:
- Processes only tenders with ml_predictions but no SHAP cache
- Batched processing (default 50) to manage memory on EC2 (3.8GB RAM)
- Graceful error handling per-tender
- Progress logging
- Option to prioritize high-risk tenders

Author: nabavkidata.com
License: Proprietary
"""

import os
import sys
import json
import logging
import asyncio
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
import numpy as np

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from features.feature_extractor import FeatureExtractor
from ml_models.shap_explainer import get_shap_explainer, is_shap_available

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL")
)


async def ensure_cache_table(conn) -> bool:
    """
    Ensure the ml_shap_cache table exists.

    Returns:
        True if the table exists or was created, False on error.
    """
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ml_shap_cache (
                tender_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                shap_values JSONB NOT NULL,
                base_value FLOAT,
                prediction FLOAT,
                computed_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_shap_cache_computed ON ml_shap_cache(computed_at)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_shap_cache_model ON ml_shap_cache(model_name)
        """)
        return True
    except Exception as e:
        logger.error(f"Error ensuring cache table: {e}")
        return False


async def get_tenders_needing_shap(
    conn,
    limit: int = 500,
    high_risk_only: bool = False,
    min_risk_score: int = 0
) -> List[Dict]:
    """
    Get tenders that have ML predictions but no SHAP cache.

    Args:
        conn: asyncpg connection
        limit: Maximum number of tenders to return
        high_risk_only: If True, only process tenders with risk_score >= 40
        min_risk_score: Minimum risk score threshold

    Returns:
        List of dicts with tender_id and risk_score
    """
    risk_threshold = 40 if high_risk_only else min_risk_score

    query = """
        SELECT mp.tender_id, mp.risk_score
        FROM ml_predictions mp
        WHERE NOT EXISTS (
            SELECT 1 FROM ml_shap_cache sc
            WHERE sc.tender_id = mp.tender_id
        )
        AND mp.risk_score >= $1
        ORDER BY mp.risk_score DESC
        LIMIT $2
    """

    rows = await conn.fetch(query, risk_threshold, limit)
    return [{'tender_id': row['tender_id'], 'risk_score': row['risk_score']} for row in rows]


async def store_shap_result(conn, tender_id: str, result: Dict) -> bool:
    """
    Store a SHAP computation result in the cache.

    Args:
        conn: asyncpg connection
        tender_id: The tender ID
        result: Dict from SHAPExplainer.explain_tender()

    Returns:
        True on success, False on failure
    """
    try:
        await conn.execute("""
            INSERT INTO ml_shap_cache (tender_id, model_name, shap_values, base_value, prediction, computed_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (tender_id)
            DO UPDATE SET
                model_name = EXCLUDED.model_name,
                shap_values = EXCLUDED.shap_values,
                base_value = EXCLUDED.base_value,
                prediction = EXCLUDED.prediction,
                computed_at = NOW()
        """,
            tender_id,
            result.get('model_name', 'xgboost'),
            json.dumps(result.get('shap_values', {})),
            result.get('base_value', 0.0),
            result.get('prediction', 0.0)
        )
        return True
    except Exception as e:
        logger.error(f"Error storing SHAP result for {tender_id}: {e}")
        return False


async def run_batch_shap(
    limit: int = 500,
    batch_size: int = 50,
    high_risk_only: bool = False,
    min_risk_score: int = 0,
    model_name: str = 'xgboost'
):
    """
    Main batch SHAP pre-computation routine.

    Args:
        limit: Total number of tenders to process
        batch_size: Process this many tenders at a time
        high_risk_only: Only process high-risk tenders (score >= 40)
        min_risk_score: Minimum risk score threshold
        model_name: Which model to explain ('xgboost' or 'random_forest')
    """
    # Check SHAP availability
    if not is_shap_available():
        logger.error("SHAP package is not installed. Cannot compute SHAP values.")
        logger.error("Install with: pip install shap")
        return

    # Initialize SHAP explainer (loads models)
    explainer = get_shap_explainer()
    available_models = explainer.get_available_models()

    if not available_models:
        logger.error("No ML models available. Please train models first.")
        return

    if model_name not in available_models:
        model_name = available_models[0]
        logger.info(f"Requested model not available, using {model_name}")

    logger.info(f"Using model: {model_name}")
    logger.info(f"Available models: {available_models}")

    # Connect to database
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)

    try:
        async with pool.acquire() as conn:
            # Ensure cache table exists
            if not await ensure_cache_table(conn):
                logger.error("Could not create/verify cache table")
                return

            # Get tenders needing SHAP computation
            tenders = await get_tenders_needing_shap(
                conn, limit=limit,
                high_risk_only=high_risk_only,
                min_risk_score=min_risk_score
            )

            if not tenders:
                logger.info("No tenders need SHAP computation. All up to date!")
                return

            # Stats
            total_cached = await conn.fetchval("SELECT COUNT(*) FROM ml_shap_cache")
            total_predictions = await conn.fetchval("SELECT COUNT(*) FROM ml_predictions")

            logger.info(f"SHAP cache: {total_cached}/{total_predictions} tenders cached")
            logger.info(f"Will process {len(tenders)} tenders (batch_size={batch_size})")

        # Initialize feature extractor
        extractor = FeatureExtractor(pool)

        processed = 0
        succeeded = 0
        failed = 0
        start_time = time.time()

        # Process in batches
        for batch_start in range(0, len(tenders), batch_size):
            batch = tenders[batch_start:batch_start + batch_size]
            batch_succeeded = 0

            for tender_info in batch:
                tender_id = tender_info['tender_id']
                risk_score = tender_info['risk_score']

                try:
                    # Extract features
                    fv = await extractor.extract_features(tender_id, include_metadata=False)

                    # Compute SHAP values
                    result = explainer.explain_tender(fv.feature_array, model_name=model_name)

                    if result is not None:
                        # Store in cache
                        async with pool.acquire() as conn:
                            stored = await store_shap_result(conn, tender_id, result)
                            if stored:
                                succeeded += 1
                                batch_succeeded += 1
                            else:
                                failed += 1
                    else:
                        failed += 1
                        if failed <= 5:
                            logger.warning(f"SHAP computation returned None for {tender_id}")

                except Exception as e:
                    failed += 1
                    if failed <= 10:
                        logger.warning(f"Failed to process {tender_id} (risk={risk_score}): {e}")

                processed += 1

            # Progress logging
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = (len(tenders) - processed) / rate if rate > 0 else 0

            logger.info(
                f"Batch {batch_start // batch_size + 1}: "
                f"{processed}/{len(tenders)} processed "
                f"({succeeded} cached, {failed} failed) "
                f"[{rate:.1f} tenders/sec, ~{remaining:.0f}s remaining]"
            )

        # Final summary
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info("BATCH SHAP PRE-COMPUTATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total processed: {processed}")
        logger.info(f"Successfully cached: {succeeded}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Time elapsed: {elapsed:.1f}s")
        logger.info(f"Rate: {processed / elapsed:.1f} tenders/sec" if elapsed > 0 else "N/A")

    finally:
        await pool.close()


async def invalidate_cache(
    model_name: Optional[str] = None,
    older_than_days: Optional[int] = None
):
    """
    Invalidate (delete) cached SHAP values.

    Args:
        model_name: If set, only invalidate for this model
        older_than_days: If set, only invalidate entries older than this many days
    """
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)

    try:
        async with pool.acquire() as conn:
            conditions = []
            params = []

            if model_name:
                conditions.append(f"model_name = ${len(params) + 1}")
                params.append(model_name)

            if older_than_days:
                conditions.append(f"computed_at < NOW() - INTERVAL '{older_than_days} days'")

            where_clause = " AND ".join(conditions) if conditions else "TRUE"

            count = await conn.fetchval(f"SELECT COUNT(*) FROM ml_shap_cache WHERE {where_clause}", *params)
            logger.info(f"Will invalidate {count} cached SHAP entries")

            if count > 0:
                await conn.execute(f"DELETE FROM ml_shap_cache WHERE {where_clause}", *params)
                logger.info(f"Deleted {count} cached entries")

    finally:
        await pool.close()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Batch pre-compute SHAP values for tenders')
    parser.add_argument('--limit', type=int, default=500,
                        help='Maximum number of tenders to process (default: 500)')
    parser.add_argument('--batch-size', type=int, default=50,
                        help='Process this many tenders per batch (default: 50)')
    parser.add_argument('--high-risk-only', action='store_true',
                        help='Only process tenders with risk_score >= 40')
    parser.add_argument('--min-risk-score', type=int, default=0,
                        help='Minimum risk score to process (default: 0)')
    parser.add_argument('--model', type=str, default='xgboost',
                        choices=['xgboost', 'random_forest'],
                        help='Model to explain (default: xgboost)')
    parser.add_argument('--invalidate', action='store_true',
                        help='Invalidate all cached values (recompute on next run)')
    parser.add_argument('--invalidate-older-than', type=int, default=None,
                        help='Invalidate cache entries older than N days')

    args = parser.parse_args()

    if args.invalidate:
        await invalidate_cache(model_name=args.model)
    elif args.invalidate_older_than:
        await invalidate_cache(older_than_days=args.invalidate_older_than)
    else:
        await run_batch_shap(
            limit=args.limit,
            batch_size=args.batch_size,
            high_risk_only=args.high_risk_only,
            min_risk_score=args.min_risk_score,
            model_name=args.model
        )


if __name__ == "__main__":
    asyncio.run(main())
