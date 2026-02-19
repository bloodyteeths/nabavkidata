#!/usr/bin/env python3
"""
Analyze ALL awarded tenders for corruption risk.
Assigns risk scores to every tender, even if no flags are detected.

This ensures 100% coverage of awarded tenders in the risk analysis.
"""

import asyncio
import asyncpg
import logging
import json
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL")


async def analyze_all_awarded_tenders():
    """Analyze all awarded tenders and assign risk scores"""

    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)

    try:
        async with pool.acquire() as conn:
            # First, run the corruption detector to get flags
            logger.info("Step 1: Getting existing flags from corruption_flags table...")

            # Get all flags grouped by tender
            flags_by_tender = {}
            flags = await conn.fetch("""
                SELECT tender_id, flag_type, severity, score, description
                FROM corruption_flags
                WHERE false_positive = FALSE
            """)

            for f in flags:
                tid = f['tender_id']
                if tid not in flags_by_tender:
                    flags_by_tender[tid] = []
                flags_by_tender[tid].append({
                    'flag_type': f['flag_type'],
                    'severity': f['severity'],
                    'score': f['score'],
                    'description': f['description']
                })

            logger.info(f"Found flags for {len(flags_by_tender)} tenders")

            # Get ALL awarded/completed tenders (both statuses mean awarded in practice)
            logger.info("Step 2: Getting all awarded/completed tenders...")
            awarded = await conn.fetch("""
                SELECT
                    tender_id,
                    num_bidders,
                    estimated_value_mkd,
                    actual_value_mkd,
                    winner,
                    procuring_entity
                FROM tenders
                WHERE status = 'awarded'
                   OR (status = 'completed' AND winner IS NOT NULL AND winner != '')
            """)

            logger.info(f"Found {len(awarded)} awarded tenders")

            # Calculate risk score for each tender
            logger.info("Step 3: Calculating risk scores for all tenders...")

            insert_count = 0
            update_count = 0
            batch = []

            for tender in awarded:
                tid = tender['tender_id']
                tender_flags = flags_by_tender.get(tid, [])

                # Calculate score
                if tender_flags:
                    # Has flags - use weighted average
                    weights = {
                        'single_bidder': 1.0,
                        'repeat_winner': 1.2,
                        'price_anomaly': 1.1,
                        'bid_clustering': 1.3,
                        'short_deadline': 0.9,
                    }

                    weighted_sum = sum(
                        f['score'] * weights.get(f['flag_type'], 1.0)
                        for f in tender_flags
                    )
                    multiplier = 1 + (len(tender_flags) - 1) * 0.15
                    risk_score = int(weighted_sum * multiplier / len(tender_flags))
                    risk_score = min(100, risk_score)
                    flag_count = len(tender_flags)
                else:
                    # No flags - assign base score based on tender characteristics
                    risk_score = 0
                    flag_count = 0

                    # Single bidder but below 500K threshold - still somewhat risky
                    if tender['num_bidders'] == 1:
                        risk_score = 25
                    # Multiple bidders - low risk
                    elif tender['num_bidders'] and tender['num_bidders'] > 1:
                        risk_score = 5
                    # Unknown bidder count - minimal info
                    else:
                        risk_score = 10

                # Determine risk level
                if risk_score >= 80:
                    risk_level = 'critical'
                elif risk_score >= 60:
                    risk_level = 'high'
                elif risk_score >= 40:
                    risk_level = 'medium'
                elif risk_score >= 20:
                    risk_level = 'low'
                else:
                    risk_level = 'minimal'

                batch.append((
                    tid,
                    risk_score,
                    risk_level,
                    flag_count,
                    json.dumps(tender_flags) if tender_flags else None
                ))

                # Insert in batches of 500
                if len(batch) >= 500:
                    await conn.executemany("""
                        INSERT INTO tender_risk_scores
                        (tender_id, risk_score, risk_level, flag_count, flags_summary)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (tender_id) DO UPDATE SET
                            risk_score = EXCLUDED.risk_score,
                            risk_level = EXCLUDED.risk_level,
                            flag_count = EXCLUDED.flag_count,
                            flags_summary = EXCLUDED.flags_summary,
                            last_analyzed = CURRENT_TIMESTAMP
                    """, batch)
                    insert_count += len(batch)
                    logger.info(f"Processed {insert_count} tenders...")
                    batch = []

            # Insert remaining
            if batch:
                await conn.executemany("""
                    INSERT INTO tender_risk_scores
                    (tender_id, risk_score, risk_level, flag_count, flags_summary)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (tender_id) DO UPDATE SET
                        risk_score = EXCLUDED.risk_score,
                        risk_level = EXCLUDED.risk_level,
                        flag_count = EXCLUDED.flag_count,
                        flags_summary = EXCLUDED.flags_summary,
                        last_analyzed = CURRENT_TIMESTAMP
                """, batch)
                insert_count += len(batch)

            logger.info(f"Processed {insert_count} total tenders")

            # Get final statistics
            logger.info("Step 4: Final statistics...")
            stats = await conn.fetch("""
                SELECT risk_level, COUNT(*) as count
                FROM tender_risk_scores
                GROUP BY risk_level
                ORDER BY count DESC
            """)

            print("\n" + "=" * 60)
            print("RISK ANALYSIS COMPLETE")
            print("=" * 60)
            print(f"\nTotal tenders analyzed: {insert_count}")
            print("\nRisk Level Distribution:")
            for s in stats:
                print(f"  {s['risk_level']}: {s['count']}")
            print("=" * 60)

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(analyze_all_awarded_tenders())
