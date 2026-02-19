#!/usr/bin/env python3
"""
Batch Counterfactual Generation Script

Queries the top high-risk tenders that do not yet have cached counterfactual
explanations, generates DiCE-style counterfactuals for each, and caches the
results in the counterfactual_explanations table.

Usage:
    # Generate for top 100 high-risk tenders without cached CFs
    python batch_counterfactuals.py

    # Custom limit and threshold
    python batch_counterfactuals.py --limit 200 --min-score 70

    # Re-generate for all (ignore cache)
    python batch_counterfactuals.py --force

Environment:
    DATABASE_URL  - PostgreSQL connection string (required)

Author: nabavkidata.com
License: Proprietary
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List

import asyncpg
from dotenv import load_dotenv
load_dotenv()


# Resolve project paths so imports work when running standalone
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_AI_CORRUPTION_DIR = os.path.join(_SCRIPT_DIR, '..')
_AI_DIR = os.path.join(_AI_CORRUPTION_DIR, '..')
_BACKEND_DIR = os.path.join(_AI_DIR, '..', 'backend')

for p in [_SCRIPT_DIR, _AI_CORRUPTION_DIR, _AI_DIR, _BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from counterfactual_engine import CounterfactualEngine
from counterfactual_cache import CounterfactualCache

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.getenv('DATABASE_URL')


async def create_pool() -> asyncpg.Pool:
    """Create a standalone asyncpg pool for batch use."""
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Example: export DATABASE_URL='postgresql://user:pass@host:5432/dbname'"
        )
    dsn = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, command_timeout=60)
    logger.info("Database pool created")
    return pool


async def fetch_high_risk_tenders(
    pool: asyncpg.Pool,
    min_score: float,
    limit: int,
    force: bool,
) -> List[Dict[str, Any]]:
    """Fetch high-risk tenders that need counterfactual generation.

    Args:
        pool: asyncpg pool.
        min_score: Minimum risk score to consider.
        limit: Maximum number of tenders to process.
        force: If True, ignore cache and return all high-risk tenders.

    Returns:
        List of dicts with tender_id and risk_score.
    """
    async with pool.acquire() as conn:
        if force:
            rows = await conn.fetch(
                """
                SELECT tender_id, risk_score
                FROM tender_risk_scores
                WHERE risk_score >= $1
                ORDER BY risk_score DESC
                LIMIT $2
                """,
                min_score,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT trs.tender_id, trs.risk_score
                FROM tender_risk_scores trs
                WHERE trs.risk_score >= $1
                  AND NOT EXISTS (
                      SELECT 1 FROM counterfactual_explanations ce
                      WHERE ce.tender_id = trs.tender_id
                  )
                ORDER BY trs.risk_score DESC
                LIMIT $2
                """,
                min_score,
                limit,
            )

    results = []
    for row in rows:
        results.append({
            'tender_id': row['tender_id'],
            'risk_score': float(row['risk_score']),
        })

    logger.info(
        f"Found {len(results)} high-risk tenders "
        f"(min_score={min_score}, limit={limit}, force={force})"
    )
    return results


async def fetch_tender_features(
    pool: asyncpg.Pool, tender_id: str
) -> Dict[str, Any]:
    """Fetch corruption flag scores for a tender and assemble a feature dict.

    Reads from corruption_flags table and also fetches num_bidders and
    estimated_value from the tenders table.
    """
    features: Dict[str, Any] = {}

    async with pool.acquire() as conn:
        # Corruption flags: use max score per flag type (matching CRI logic)
        flag_rows = await conn.fetch(
            """
            SELECT flag_type, MAX(score) AS max_score
            FROM corruption_flags
            WHERE tender_id = $1 AND (false_positive IS NULL OR false_positive = false)
            GROUP BY flag_type
            """,
            tender_id,
        )
        for row in flag_rows:
            ft = row['flag_type']
            score = float(row['max_score']) if row['max_score'] is not None else 0.0
            # Binary flags get 1 if score > 0, continuous flags keep their score
            feat_def = CounterfactualEngine.FEATURE_DEFS.get(ft, {})
            if feat_def.get('type') == 'binary':
                features[ft] = 1 if score > 0 else 0
            else:
                features[ft] = score

        # Tender metadata
        tender_row = await conn.fetchrow(
            """
            SELECT num_bidders, estimated_value_mkd
            FROM tenders
            WHERE tender_id = $1
            """,
            tender_id,
        )
        if tender_row:
            features['num_bidders'] = int(tender_row['num_bidders']) if tender_row['num_bidders'] else 1
            features['estimated_value_mkd'] = (
                float(tender_row['estimated_value_mkd'])
                if tender_row['estimated_value_mkd']
                else 0.0
            )

    return features


async def run_batch(
    limit: int = 100,
    min_score: float = 60.0,
    target_score: float = 30.0,
    top_k: int = 5,
    force: bool = False,
) -> Dict[str, Any]:
    """Main batch processing routine.

    Returns:
        Summary dict with counts and timing.
    """
    pool = await create_pool()
    t0 = time.time()

    try:
        tenders = await fetch_high_risk_tenders(pool, min_score, limit, force)

        engine = CounterfactualEngine(target_score=target_score)
        processed = 0
        cached = 0
        failed = 0
        total_cfs = 0

        for i, tender_info in enumerate(tenders, 1):
            tender_id = tender_info['tender_id']
            risk_score = tender_info['risk_score']

            try:
                features = await fetch_tender_features(pool, tender_id)

                if not features:
                    logger.warning(f"[{i}/{len(tenders)}] No features for {tender_id}, skipping")
                    failed += 1
                    continue

                counterfactuals = engine.generate(
                    original_features=features,
                    original_score=risk_score,
                    top_k=top_k,
                )

                if counterfactuals:
                    saved = await CounterfactualCache.save(pool, tender_id, risk_score, counterfactuals)
                    cached += saved
                    total_cfs += len(counterfactuals)
                    logger.info(
                        f"[{i}/{len(tenders)}] {tender_id}: score={risk_score:.1f}, "
                        f"generated={len(counterfactuals)}, saved={saved}"
                    )
                else:
                    logger.info(
                        f"[{i}/{len(tenders)}] {tender_id}: score={risk_score:.1f}, "
                        f"no counterfactuals generated (may already be below target)"
                    )

                processed += 1

            except Exception as e:
                logger.error(f"[{i}/{len(tenders)}] Failed for {tender_id}: {e}")
                failed += 1

        elapsed = time.time() - t0
        summary = {
            'total_tenders': len(tenders),
            'processed': processed,
            'failed': failed,
            'total_counterfactuals_generated': total_cfs,
            'total_cached': cached,
            'elapsed_seconds': round(elapsed, 2),
            'avg_per_tender_seconds': round(elapsed / max(processed, 1), 3),
        }

        logger.info(f"Batch complete: {json.dumps(summary, indent=2)}")
        return summary

    finally:
        await pool.close()
        logger.info("Database pool closed")


def main():
    parser = argparse.ArgumentParser(
        description='Batch generate counterfactual explanations for high-risk tenders'
    )
    parser.add_argument(
        '--limit', type=int, default=100,
        help='Maximum number of tenders to process (default: 100)'
    )
    parser.add_argument(
        '--min-score', type=float, default=60.0,
        help='Minimum risk score threshold (default: 60.0)'
    )
    parser.add_argument(
        '--target-score', type=float, default=30.0,
        help='Target risk score for counterfactuals (default: 30.0)'
    )
    parser.add_argument(
        '--top-k', type=int, default=5,
        help='Number of counterfactuals per tender (default: 5)'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Re-generate even if cached counterfactuals exist'
    )
    args = parser.parse_args()

    summary = asyncio.run(run_batch(
        limit=args.limit,
        min_score=args.min_score,
        target_score=args.target_score,
        top_k=args.top_k,
        force=args.force,
    ))

    print(f"\n{'='*60}")
    print("BATCH COUNTERFACTUAL GENERATION SUMMARY")
    print(f"{'='*60}")
    for key, val in summary.items():
        print(f"  {key}: {val}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
