"""
Counterfactual Explanations Cache Manager

Stores and retrieves cached counterfactual explanations from PostgreSQL
to avoid expensive re-computation via the genetic algorithm.

Table: counterfactual_explanations (see db/migrations/043_counterfactuals.sql)

Author: nabavkidata.com
License: Proprietary
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CounterfactualCache:
    """Cache counterfactual explanations in PostgreSQL to avoid recomputation."""

    @staticmethod
    async def get_cached(pool, tender_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached counterfactuals for a tender.

        Args:
            pool: asyncpg connection pool.
            tender_id: The tender identifier.

        Returns:
            List of counterfactual dicts if cached, or None if not found.
        """
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        counterfactual_features,
                        counterfactual_score,
                        distance,
                        feasibility_score,
                        num_changes,
                        original_score,
                        generated_at
                    FROM counterfactual_explanations
                    WHERE tender_id = $1
                    ORDER BY distance ASC, num_changes ASC
                    """,
                    tender_id,
                )

                if not rows:
                    return None

                results = []
                for row in rows:
                    cf_features = row['counterfactual_features']
                    if isinstance(cf_features, str):
                        cf_features = json.loads(cf_features) if cf_features else {}
                    elif not isinstance(cf_features, dict):
                        cf_features = {}

                    results.append({
                        'changed_features': cf_features,
                        'counterfactual_score': float(row['counterfactual_score']),
                        'distance': float(row['distance']),
                        'feasibility': float(row['feasibility_score']),
                        'num_changes': int(row['num_changes']),
                        'original_score': float(row['original_score']),
                        'generated_at': row['generated_at'].isoformat() if row['generated_at'] else None,
                        'cached': True,
                    })

                logger.debug(f"Retrieved {len(results)} cached counterfactuals for tender {tender_id}")
                return results

        except Exception as e:
            # Table may not exist yet if migration has not been run
            logger.debug(f"Counterfactual cache lookup failed for {tender_id}: {e}")
            return None

    @staticmethod
    async def save(
        pool,
        tender_id: str,
        original_score: float,
        counterfactuals: List[Dict[str, Any]],
    ) -> int:
        """Save counterfactuals to cache.

        Args:
            pool: asyncpg connection pool.
            tender_id: The tender identifier.
            original_score: The original risk score.
            counterfactuals: List of counterfactual dicts from CounterfactualEngine.generate().

        Returns:
            Number of rows inserted.
        """
        if not counterfactuals:
            return 0

        try:
            async with pool.acquire() as conn:
                # Delete existing cached results for this tender (replace strategy)
                await conn.execute(
                    "DELETE FROM counterfactual_explanations WHERE tender_id = $1",
                    tender_id,
                )

                inserted = 0
                for cf in counterfactuals:
                    cf_features = cf.get('changed_features', {})
                    # Ensure JSON-serializable
                    if not isinstance(cf_features, str):
                        cf_features_json = json.dumps(cf_features, default=str)
                    else:
                        cf_features_json = cf_features

                    await conn.execute(
                        """
                        INSERT INTO counterfactual_explanations
                            (tender_id, original_score, counterfactual_features,
                             counterfactual_score, distance, feasibility_score,
                             num_changes, generated_at)
                        VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, NOW())
                        """,
                        tender_id,
                        float(original_score),
                        cf_features_json,
                        float(cf.get('counterfactual_score', 0)),
                        float(cf.get('distance', 0)),
                        float(cf.get('feasibility', 0)),
                        int(cf.get('num_changes', 0)),
                    )
                    inserted += 1

                logger.info(f"Cached {inserted} counterfactuals for tender {tender_id}")
                return inserted

        except Exception as e:
            logger.error(f"Failed to cache counterfactuals for {tender_id}: {e}")
            return 0

    @staticmethod
    async def invalidate(pool, tender_id: str) -> bool:
        """Invalidate cache for a tender (when risk score changes).

        Args:
            pool: asyncpg connection pool.
            tender_id: The tender identifier.

        Returns:
            True if any rows were deleted, False otherwise.
        """
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM counterfactual_explanations WHERE tender_id = $1",
                    tender_id,
                )
                deleted = int(result.split()[-1]) if result else 0
                if deleted > 0:
                    logger.info(f"Invalidated {deleted} cached counterfactuals for tender {tender_id}")
                return deleted > 0

        except Exception as e:
            logger.debug(f"Cache invalidation failed for {tender_id}: {e}")
            return False

    @staticmethod
    async def get_stats(pool) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with total_cached, unique_tenders, avg_per_tender, oldest, newest.
        """
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) AS total_cached,
                        COUNT(DISTINCT tender_id) AS unique_tenders,
                        MIN(generated_at) AS oldest,
                        MAX(generated_at) AS newest
                    FROM counterfactual_explanations
                    """
                )
                if row:
                    total = int(row['total_cached'])
                    unique = int(row['unique_tenders'])
                    return {
                        'total_cached': total,
                        'unique_tenders': unique,
                        'avg_per_tender': round(total / unique, 1) if unique > 0 else 0,
                        'oldest': row['oldest'].isoformat() if row['oldest'] else None,
                        'newest': row['newest'].isoformat() if row['newest'] else None,
                    }
        except Exception as e:
            logger.debug(f"Failed to get cache stats: {e}")

        return {
            'total_cached': 0,
            'unique_tenders': 0,
            'avg_per_tender': 0,
            'oldest': None,
            'newest': None,
        }
