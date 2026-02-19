"""
Batch Temporal Analysis Processor

Builds temporal risk profiles for all institutions and companies with 5+ tenders.
Designed to run as a weekly cron job.

Usage:
    # Process all institutions
    python batch_temporal.py

    # Process only companies
    python batch_temporal.py --entity-type company

    # Process a specific entity
    python batch_temporal.py --entity-name "Општина Битола" --entity-type institution

    # Limit number of entities to process
    python batch_temporal.py --limit 100

    # Custom lookback window (days)
    python batch_temporal.py --window-days 1095

Cron example (weekly, Sundays at 4 AM UTC):
    0 4 * * 0 cd /home/ubuntu/nabavkidata/ai/corruption/ml_models && python3 batch_temporal.py >> /var/log/nabavkidata/batch_temporal.log 2>&1
"""

import os
import sys
import json
import logging
import asyncio
import argparse
from datetime import datetime
from typing import Optional
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
load_dotenv()


# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml_models.temporal_analyzer import TemporalAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL"),
)

# Minimum number of tenders for an entity to be included
MIN_TENDERS = 5


async def get_entities(
    conn,
    entity_type: str = "institution",
    limit: Optional[int] = None,
    entity_name: Optional[str] = None,
) -> list:
    """
    Get list of entities with enough tenders for temporal analysis.

    Args:
        conn: asyncpg connection
        entity_type: 'institution' or 'company'
        limit: Max number of entities to return
        entity_name: Specific entity name to process (if set, ignores limit)

    Returns:
        List of (entity_name, tender_count) tuples
    """
    if entity_type == "institution":
        field = "procuring_entity"
    else:
        field = "winner"

    if entity_name:
        # Process a specific entity
        count = await conn.fetchval(
            f"SELECT COUNT(*) FROM tenders WHERE {field} ILIKE $1",
            entity_name,
        )
        return [(entity_name, count)]

    # Get all entities with MIN_TENDERS+ tenders, ordered by tender count DESC
    query = f"""
        SELECT {field} AS entity_name, COUNT(*) AS tender_count
        FROM tenders
        WHERE {field} IS NOT NULL
          AND {field} != ''
        GROUP BY {field}
        HAVING COUNT(*) >= $1
        ORDER BY COUNT(*) DESC
    """
    params = [MIN_TENDERS]

    if limit:
        query += f" LIMIT ${len(params) + 1}"
        params.append(limit)

    rows = await conn.fetch(query, *params)
    return [(row["entity_name"], row["tender_count"]) for row in rows]


async def upsert_profile(conn, profile: dict) -> bool:
    """
    Insert or update an entity temporal profile in the database.

    Args:
        conn: asyncpg connection
        profile: Output of TemporalAnalyzer.get_entity_risk_profile()

    Returns:
        True if successful, False otherwise
    """
    try:
        trajectory_data = profile.get("trajectory", {})
        temporal_features = profile.get("temporal_features", {})
        change_points = profile.get("change_points", [])
        summary_stats = profile.get("summary_stats", {})

        # Determine last change point date
        last_cp_date = None
        if change_points:
            last_cp_str = change_points[-1].get("date")
            if last_cp_str:
                try:
                    from temporal_analyzer import _parse_date
                    last_cp_date = _parse_date(last_cp_str)
                except Exception:
                    pass

        # Parse period dates
        period_start = None
        period_end = None
        if profile.get("period_start"):
            try:
                from temporal_analyzer import _parse_date
                period_start = _parse_date(profile["period_start"])
            except Exception:
                pass
        if profile.get("period_end"):
            try:
                from temporal_analyzer import _parse_date
                period_end = _parse_date(profile["period_end"])
            except Exception:
                pass

        await conn.execute(
            """
            INSERT INTO entity_temporal_profiles (
                entity_name, entity_type, temporal_features, trajectory,
                trajectory_confidence, trajectory_description, trajectory_recommendation,
                change_points, last_change_point_date,
                risk_trend_slope, risk_volatility,
                summary_stats, tender_count,
                period_start, period_end, computed_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW()
            )
            ON CONFLICT (entity_name, entity_type) DO UPDATE SET
                temporal_features = EXCLUDED.temporal_features,
                trajectory = EXCLUDED.trajectory,
                trajectory_confidence = EXCLUDED.trajectory_confidence,
                trajectory_description = EXCLUDED.trajectory_description,
                trajectory_recommendation = EXCLUDED.trajectory_recommendation,
                change_points = EXCLUDED.change_points,
                last_change_point_date = EXCLUDED.last_change_point_date,
                risk_trend_slope = EXCLUDED.risk_trend_slope,
                risk_volatility = EXCLUDED.risk_volatility,
                summary_stats = EXCLUDED.summary_stats,
                tender_count = EXCLUDED.tender_count,
                period_start = EXCLUDED.period_start,
                period_end = EXCLUDED.period_end,
                computed_at = NOW()
            """,
            profile["entity"],
            profile["entity_type"],
            json.dumps(temporal_features),
            trajectory_data.get("trajectory"),
            trajectory_data.get("confidence", 0.0),
            trajectory_data.get("description"),
            trajectory_data.get("recommendation"),
            json.dumps(change_points),
            last_cp_date,
            temporal_features.get("risk_trend_slope"),
            temporal_features.get("risk_volatility"),
            json.dumps(summary_stats),
            profile.get("total_tenders", 0),
            period_start,
            period_end,
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to upsert profile for {profile.get('entity')}: {e}"
        )
        return False


async def run_batch(
    entity_type: str = "institution",
    limit: Optional[int] = None,
    entity_name: Optional[str] = None,
    window_days: int = 730,
    batch_size: int = 50,
):
    """
    Main batch processing loop.

    Args:
        entity_type: 'institution' or 'company'
        limit: Max number of entities to process
        entity_name: Specific entity to process
        window_days: Lookback window in days
        batch_size: How many entities to process before logging progress
    """
    logger.info(
        f"Starting temporal batch analysis: type={entity_type}, "
        f"limit={limit}, window_days={window_days}"
    )

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    analyzer = TemporalAnalyzer()

    try:
        async with pool.acquire() as conn:
            entities = await get_entities(conn, entity_type, limit, entity_name)

        total = len(entities)
        logger.info(f"Found {total} entities to process")

        if total == 0:
            logger.info("No entities to process. Done.")
            return

        processed = 0
        succeeded = 0
        failed = 0
        start_time = datetime.utcnow()

        for i, (name, tender_count) in enumerate(entities):
            try:
                profile = await analyzer.get_entity_risk_profile(
                    pool, name, entity_type, window_days
                )

                async with pool.acquire() as conn:
                    ok = await upsert_profile(conn, profile)

                if ok:
                    succeeded += 1
                else:
                    failed += 1

            except Exception as e:
                failed += 1
                if failed <= 10:
                    logger.error(f"Error processing '{name}': {e}")

            processed += 1

            # Progress logging
            if processed % batch_size == 0 or processed == total:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                rate = processed / elapsed if elapsed > 0 else 0
                trajectory_info = profile.get("trajectory", {}).get("trajectory", "?") if profile else "?"
                logger.info(
                    f"Progress: {processed}/{total} "
                    f"({100 * processed / total:.1f}%) | "
                    f"OK={succeeded} Failed={failed} | "
                    f"{rate:.1f} entities/sec | "
                    f"Last: '{name[:40]}' -> {trajectory_info}"
                )

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Batch complete: {succeeded}/{total} succeeded, "
            f"{failed} failed in {elapsed:.1f}s"
        )

    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(
        description="Batch temporal analysis for corruption detection"
    )
    parser.add_argument(
        "--entity-type",
        choices=["institution", "company", "both"],
        default="both",
        help="Type of entity to process (default: both)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of entities per type to process",
    )
    parser.add_argument(
        "--entity-name",
        type=str,
        default=None,
        help="Process a specific entity by name",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=730,
        help="Lookback window in days (default: 730 = 2 years)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Log progress every N entities (default: 50)",
    )

    args = parser.parse_args()

    types_to_process = []
    if args.entity_type == "both":
        types_to_process = ["institution", "company"]
    else:
        types_to_process = [args.entity_type]

    for et in types_to_process:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing entity type: {et}")
        logger.info(f"{'='*60}")
        asyncio.run(
            run_batch(
                entity_type=et,
                limit=args.limit,
                entity_name=args.entity_name,
                window_days=args.window_days,
                batch_size=args.batch_size,
            )
        )

    logger.info("All done.")


if __name__ == "__main__":
    main()
