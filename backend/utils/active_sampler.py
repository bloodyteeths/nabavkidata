"""
Active Learning Sampler

Selects tenders that would be most informative to label, using 3 strategies:
1. Boundary: tenders near CRI decision boundary (~50 risk score)
2. Disagreement: tenders where rule-based flags and ML predictions disagree
3. Novel: tenders with unusual flag combinations not seen before

Used by:
- GET /api/corruption/review-queue  (returns top-N from queue)
- Cron job (weekly refresh of the queue)
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# CRI decision boundary score (tenders near this are most informative)
BOUNDARY_CENTER = 50
BOUNDARY_HALF_WIDTH = 15  # tenders in [35, 65] are "boundary"

# How many items per strategy
DEFAULT_BOUNDARY_COUNT = 10
DEFAULT_DISAGREEMENT_COUNT = 6
DEFAULT_NOVEL_COUNT = 4


async def _select_boundary_tenders(pool, limit: int = DEFAULT_BOUNDARY_COUNT) -> List[Dict]:
    """
    Select tenders whose CRI risk score is near the decision boundary.
    These are the most uncertain cases and labeling them gives maximal
    information gain for weight calibration.
    """
    rows = await pool.fetch("""
        SELECT
            mft.tender_id,
            mft.risk_score,
            mft.total_flags,
            -- Priority: closer to boundary center = higher priority
            1.0 / (1.0 + ABS(mft.risk_score - $1)) as priority_score
        FROM mv_flagged_tenders mft
        WHERE mft.risk_score BETWEEN $2 AND $3
          AND NOT EXISTS (
              SELECT 1 FROM corruption_reviews cr
              WHERE cr.tender_id = mft.tender_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM active_learning_queue alq
              WHERE alq.tender_id = mft.tender_id AND alq.reviewed = TRUE
          )
        ORDER BY ABS(mft.risk_score - $1) ASC, mft.total_flags DESC
        LIMIT $4
    """,
        BOUNDARY_CENTER,
        BOUNDARY_CENTER - BOUNDARY_HALF_WIDTH,
        BOUNDARY_CENTER + BOUNDARY_HALF_WIDTH,
        limit,
    )

    return [
        {
            'tender_id': row['tender_id'],
            'priority_score': float(row['priority_score']),
            'selection_reason': 'boundary',
        }
        for row in rows
    ]


async def _select_disagreement_tenders(pool, limit: int = DEFAULT_DISAGREEMENT_COUNT) -> List[Dict]:
    """
    Select tenders where rule-based CRI score and ML prediction disagree.
    E.g., CRI says high-risk but ML says low-risk, or vice versa.
    Requires ml_predictions table to exist.
    """
    try:
        rows = await pool.fetch("""
            SELECT
                mft.tender_id,
                mft.risk_score as cri_score,
                mp.risk_score as ml_score,
                ABS(mft.risk_score - mp.risk_score) as score_diff,
                -- Higher disagreement = higher priority
                ABS(mft.risk_score - mp.risk_score) / 100.0 as priority_score
            FROM mv_flagged_tenders mft
            JOIN ml_predictions mp ON mft.tender_id = mp.tender_id
            WHERE ABS(mft.risk_score - mp.risk_score) > 20
              AND NOT EXISTS (
                  SELECT 1 FROM corruption_reviews cr
                  WHERE cr.tender_id = mft.tender_id
              )
            ORDER BY ABS(mft.risk_score - mp.risk_score) DESC
            LIMIT $1
        """, limit)

        return [
            {
                'tender_id': row['tender_id'],
                'priority_score': float(row['priority_score']),
                'selection_reason': 'disagreement',
            }
            for row in rows
        ]
    except Exception as e:
        # ml_predictions table might not exist yet
        logger.debug(f"Disagreement selection skipped: {e}")
        return []


async def _select_novel_tenders(pool, limit: int = DEFAULT_NOVEL_COUNT) -> List[Dict]:
    """
    Select tenders with unusual flag combinations that haven't been reviewed.
    "Novel" means the combination of flag types is rare in the dataset.
    """
    rows = await pool.fetch("""
        WITH flag_combos AS (
            -- Get the flag type combination per tender
            SELECT
                cf.tender_id,
                ARRAY_AGG(DISTINCT cf.flag_type ORDER BY cf.flag_type) as combo
            FROM corruption_flags cf
            WHERE cf.false_positive = FALSE
            GROUP BY cf.tender_id
        ),
        combo_frequency AS (
            -- Count how often each combination appears
            SELECT combo, COUNT(*) as freq
            FROM flag_combos
            GROUP BY combo
        ),
        rare_combos AS (
            SELECT
                fc.tender_id,
                fc.combo,
                cf2.freq,
                -- Rarer combos get higher priority (inverse frequency)
                1.0 / cf2.freq as priority_score
            FROM flag_combos fc
            JOIN combo_frequency cf2 ON fc.combo = cf2.combo
            WHERE cf2.freq <= 3  -- flag combos seen 3 or fewer times
              AND NOT EXISTS (
                  SELECT 1 FROM corruption_reviews cr
                  WHERE cr.tender_id = fc.tender_id
              )
        )
        SELECT tender_id, priority_score
        FROM rare_combos
        ORDER BY priority_score DESC, tender_id
        LIMIT $1
    """, limit)

    return [
        {
            'tender_id': row['tender_id'],
            'priority_score': float(row['priority_score']),
            'selection_reason': 'novel',
        }
        for row in rows
    ]


async def select_for_review(pool, n: int = 20) -> List[Dict]:
    """
    Select top-N most informative tenders for review.

    Combines three strategies:
    - Boundary: ~50% of slots (tenders near decision boundary)
    - Disagreement: ~30% of slots (CRI vs ML mismatch)
    - Novel: ~20% of slots (rare flag combinations)

    Args:
        pool: asyncpg connection pool
        n: number of tenders to select

    Returns:
        List of {tender_id, priority_score, selection_reason}
    """
    boundary_n = max(1, int(n * 0.5))
    disagree_n = max(1, int(n * 0.3))
    novel_n = max(1, n - boundary_n - disagree_n)

    boundary = await _select_boundary_tenders(pool, boundary_n)
    disagreement = await _select_disagreement_tenders(pool, disagree_n)
    novel = await _select_novel_tenders(pool, novel_n)

    # Combine and deduplicate by tender_id
    seen = set()
    combined = []
    for item in boundary + disagreement + novel:
        if item['tender_id'] not in seen:
            seen.add(item['tender_id'])
            combined.append(item)

    # Sort by priority descending, take top n
    combined.sort(key=lambda x: x['priority_score'], reverse=True)
    return combined[:n]


async def refresh_active_queue(pool) -> int:
    """
    Rebuild the active_learning_queue table.
    Called by cron weekly or manually via admin endpoint.

    Steps:
    1. Clear unreviewed items from the queue
    2. Select new informative tenders
    3. Insert them into the queue

    Returns:
        Number of items queued
    """
    candidates = await select_for_review(pool, n=50)

    if not candidates:
        logger.info("No candidates found for active learning queue")
        return 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Remove old unreviewed items (keep reviewed ones for history)
            await conn.execute("""
                DELETE FROM active_learning_queue WHERE reviewed = FALSE
            """)

            # Insert new candidates
            for item in candidates:
                await conn.execute("""
                    INSERT INTO active_learning_queue
                        (tender_id, priority_score, selection_reason)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (tender_id) DO UPDATE SET
                        priority_score = EXCLUDED.priority_score,
                        selection_reason = EXCLUDED.selection_reason,
                        selected_at = NOW(),
                        reviewed = FALSE
                """,
                    item['tender_id'],
                    item['priority_score'],
                    item['selection_reason'],
                )

    logger.info(f"Refreshed active learning queue with {len(candidates)} items")
    return len(candidates)


async def get_queue_items(pool, limit: int = 20, include_tender_info: bool = True) -> List[Dict]:
    """
    Get items from the active learning queue with optional tender details.

    Args:
        pool: asyncpg connection pool
        limit: max items to return
        include_tender_info: whether to join with tenders table for details

    Returns:
        List of queue items with tender details
    """
    if include_tender_info:
        rows = await pool.fetch("""
            SELECT
                alq.queue_id,
                alq.tender_id,
                alq.priority_score,
                alq.selection_reason,
                alq.selected_at,
                t.title,
                t.procuring_entity,
                t.winner,
                t.estimated_value_mkd,
                t.status,
                mft.risk_score,
                mft.total_flags,
                mft.flag_types,
                mft.max_severity
            FROM active_learning_queue alq
            JOIN tenders t ON alq.tender_id = t.tender_id
            LEFT JOIN mv_flagged_tenders mft ON alq.tender_id = mft.tender_id
            WHERE alq.reviewed = FALSE
            ORDER BY alq.priority_score DESC
            LIMIT $1
        """, limit)
    else:
        rows = await pool.fetch("""
            SELECT queue_id, tender_id, priority_score, selection_reason, selected_at
            FROM active_learning_queue
            WHERE reviewed = FALSE
            ORDER BY priority_score DESC
            LIMIT $1
        """, limit)

    result = []
    for row in rows:
        item = {
            'queue_id': row['queue_id'],
            'tender_id': row['tender_id'],
            'priority_score': float(row['priority_score']),
            'selection_reason': row['selection_reason'],
            'selected_at': row['selected_at'].isoformat() if row['selected_at'] else None,
        }
        if include_tender_info:
            item['title'] = row.get('title')
            item['procuring_entity'] = row.get('procuring_entity')
            item['winner'] = row.get('winner')
            item['estimated_value_mkd'] = float(row['estimated_value_mkd']) if row.get('estimated_value_mkd') else None
            item['status'] = row.get('status')
            item['risk_score'] = row.get('risk_score')
            item['total_flags'] = row.get('total_flags')
            item['flag_types'] = list(row['flag_types']) if row.get('flag_types') else []
            item['max_severity'] = row.get('max_severity')

        result.append(item)

    return result
