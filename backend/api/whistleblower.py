"""
Anonymous Whistleblower Portal API

Public endpoints (no auth) for anonymous tip submission and status checking.
Admin endpoints for tip management, triage review, and case linking.

Security notes:
- POST /tips and GET /tips/{tracking_code}/status are fully anonymous (no auth)
- All /admin/* endpoints require admin role via JWT
- No IP addresses or user-agent strings are stored to protect anonymity
- Tracking codes are cryptographically random (WB-XXXX-XXXX format)
"""

import json
import logging
import secrets
import string
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime

from db_pool import get_asyncpg_pool
from middleware.rbac import require_admin

logger = logging.getLogger(__name__)

# Ensure ai/corruption is importable for the triage engine
_AI_ROOT = Path(__file__).parent.parent.parent / "ai" / "corruption"
if str(_AI_ROOT.parent.parent) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT.parent.parent))

# Lazy-loaded triage engine singleton
_triage_engine = None


def _get_triage_engine():
    """Lazily import and instantiate the TipTriageEngine."""
    global _triage_engine
    if _triage_engine is None:
        try:
            from ai.corruption.tips.tip_triage import TipTriageEngine
            _triage_engine = TipTriageEngine()
            logger.info("TipTriageEngine initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize TipTriageEngine: {e}")
            _triage_engine = None
    return _triage_engine


router = APIRouter(
    prefix="/api/whistleblower",
    tags=["Whistleblower"]
)

# Valid categories for tip submission
VALID_CATEGORIES = {'bid_rigging', 'bribery', 'conflict_of_interest', 'fraud', 'other'}

# Valid statuses for tip lifecycle
VALID_STATUSES = {'new', 'reviewing', 'investigating', 'verified', 'dismissed', 'linked'}


def _generate_tracking_code() -> str:
    """Generate a cryptographically random tracking code like 'WB-XXXX-XXXX'.

    Uses secrets module for unpredictable randomness.
    Format chosen for easy verbal communication (no ambiguous characters).
    """
    # Exclude easily confused characters: 0/O, 1/I/L
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"WB-{part1}-{part2}"


def _parse_jsonb(value):
    """Safely parse a JSONB value that may come back as str or dict/list from asyncpg."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


# ============================================================================
# PUBLIC ENDPOINTS (No authentication required)
# ============================================================================


@router.post("/tips", status_code=status.HTTP_201_CREATED)
async def submit_tip(body: dict):
    """Submit an anonymous corruption tip. Returns a tracking code for status checks.

    Body: {
        "category": "bid_rigging" | "bribery" | "conflict_of_interest" | "fraud" | "other",
        "description": "Detailed description of suspected corruption...",
        "evidence_urls": ["https://..."] (optional)
    }

    Returns: {"tracking_code": "WB-XXXX-XXXX", "message": "Tip submitted successfully"}

    This endpoint is fully anonymous. No authentication is required.
    No IP addresses or identifying information are stored.
    """
    # 1. Validate required fields
    description = (body.get('description') or '').strip()
    if not description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Description is required. Please provide details about the suspected corruption."
        )

    if len(description) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Description is too short. Please provide at least 20 characters of detail."
        )

    if len(description) > 50000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Description is too long. Maximum 50,000 characters allowed."
        )

    category = (body.get('category') or 'other').strip().lower()
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    evidence_urls = body.get('evidence_urls') or []
    if not isinstance(evidence_urls, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="evidence_urls must be a list of URL strings."
        )
    # Validate and limit URLs
    if len(evidence_urls) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 evidence URLs allowed per tip."
        )
    for url in evidence_urls:
        if not isinstance(url, str) or len(url) > 2000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each evidence URL must be a string under 2000 characters."
            )

    # 2. Generate unique tracking code
    tracking_code = _generate_tracking_code()

    # 3. Run tip triage
    triage_results = {}
    triage_score = 0.0
    urgency = 'low'

    pool = await get_asyncpg_pool()
    engine = _get_triage_engine()
    if engine:
        try:
            triage_results = await engine.triage(
                pool, description, category, evidence_urls)
            triage_score = triage_results.get('triage_score', 0.0)
            urgency = triage_results.get('urgency', 'low')
        except Exception as e:
            logger.error(f"Triage engine failed for tip: {e}")
            # Continue without triage -- the tip is still saved

    # 4. Insert into database
    try:
        async with pool.acquire() as conn:
            # Ensure tracking code is unique (extremely unlikely collision)
            for attempt in range(5):
                existing = await conn.fetchval(
                    "SELECT 1 FROM whistleblower_tips WHERE tracking_code = $1",
                    tracking_code
                )
                if not existing:
                    break
                tracking_code = _generate_tracking_code()

            await conn.execute(
                """
                INSERT INTO whistleblower_tips
                    (tracking_code, category, description, evidence_urls,
                     triage_score, urgency, matched_tender_ids, matched_entity_ids,
                     extracted_entities, triage_details, status)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7::jsonb, $8::jsonb,
                        $9::jsonb, $10::jsonb, 'new')
                """,
                tracking_code,
                category,
                description,
                json.dumps(evidence_urls),
                triage_score,
                urgency,
                json.dumps(triage_results.get('matched_tender_ids', [])),
                json.dumps(triage_results.get('matched_entity_ids', [])),
                json.dumps(triage_results.get('extracted_entities', [])),
                json.dumps({
                    'category_analysis': triage_results.get('category_analysis', ''),
                    'suggested_actions': triage_results.get('suggested_actions', []),
                    'detail_richness': triage_results.get('detail_richness', 0),
                    'specificity_score': triage_results.get('specificity_score', 0),
                }),
            )

            # Insert initial status update record
            await conn.execute(
                """
                INSERT INTO tip_status_updates (tip_id, old_status, new_status, note, updated_by)
                SELECT tip_id, NULL, 'new', 'Tip submitted anonymously', 'system'
                FROM whistleblower_tips WHERE tracking_code = $1
                """,
                tracking_code
            )

    except Exception as e:
        logger.error(f"Failed to save whistleblower tip: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit tip. Please try again later."
        )

    logger.info(f"Anonymous tip submitted: {tracking_code} (score={triage_score}, urgency={urgency})")

    return {
        "tracking_code": tracking_code,
        "message": "Tip submitted successfully. Save your tracking code to check the status later."
    }


@router.get("/tips/{tracking_code}/status")
async def check_tip_status(tracking_code: str):
    """Check the status of a previously submitted tip using the tracking code.

    Returns limited information only (status and public message).
    No internal triage details are exposed to preserve investigation integrity.

    This endpoint is fully anonymous. No authentication is required.
    """
    # Validate tracking code format
    if not tracking_code or len(tracking_code) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tracking code format."
        )

    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT status, submitted_at, updated_at
                FROM whistleblower_tips
                WHERE tracking_code = $1
                """,
                tracking_code.upper().strip()
            )

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tracking code not found. Please check your code and try again."
                )

            # Get the latest public status message (if any)
            latest_update = await conn.fetchrow(
                """
                SELECT note, updated_at
                FROM tip_status_updates
                WHERE tip_id = (
                    SELECT tip_id FROM whistleblower_tips WHERE tracking_code = $1
                )
                AND updated_by = 'system'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                tracking_code.upper().strip()
            )

            # Map internal status to user-friendly messages
            status_messages = {
                'new': 'Your tip has been received and is awaiting review.',
                'reviewing': 'Your tip is currently being reviewed by our team.',
                'investigating': 'Your tip is under active investigation.',
                'verified': 'Your tip has been verified and action is being taken.',
                'dismissed': 'After review, this tip could not be verified with available information.',
                'linked': 'Your tip has been linked to an active investigation.',
            }

            tip_status = row['status']
            status_message = status_messages.get(tip_status, 'Status unknown.')

            return {
                "tracking_code": tracking_code.upper().strip(),
                "status": tip_status,
                "status_message": status_message,
                "submitted_at": row['submitted_at'].isoformat() if row['submitted_at'] else None,
                "last_updated": row['updated_at'].isoformat() if row['updated_at'] else None,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check tip status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check status. Please try again later."
        )


# ============================================================================
# ADMIN ENDPOINTS (Require admin role via JWT)
# ============================================================================


@router.get("/admin/tips", dependencies=[Depends(require_admin)])
async def list_tips(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_triage_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum triage score"),
    urgency: Optional[str] = Query(None, description="Filter by urgency"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("submitted_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """List all tips with filtering, sorting, and pagination.

    Supports filtering by status, category, urgency, and minimum triage score.
    Default sort is newest first.
    """
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Build dynamic WHERE clause
            conditions = []
            params = []
            param_idx = 1

            if status_filter:
                if status_filter not in VALID_STATUSES:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
                    )
                conditions.append(f"status = ${param_idx}")
                params.append(status_filter)
                param_idx += 1

            if category:
                if category not in VALID_CATEGORIES:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
                    )
                conditions.append(f"category = ${param_idx}")
                params.append(category)
                param_idx += 1

            if min_triage_score is not None:
                conditions.append(f"triage_score >= ${param_idx}")
                params.append(min_triage_score)
                param_idx += 1

            if urgency:
                if urgency not in ('low', 'medium', 'high', 'critical'):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid urgency. Must be: low, medium, high, critical"
                    )
                conditions.append(f"urgency = ${param_idx}")
                params.append(urgency)
                param_idx += 1

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Validate sort field to prevent SQL injection
            allowed_sort_fields = {
                'submitted_at', 'updated_at', 'triage_score', 'urgency', 'status', 'category'
            }
            if sort_by not in allowed_sort_fields:
                sort_by = 'submitted_at'
            if sort_order.lower() not in ('asc', 'desc'):
                sort_order = 'desc'

            # Count total
            count_query = f"SELECT COUNT(*) FROM whistleblower_tips {where_clause}"
            total = await conn.fetchval(count_query, *params)

            # Fetch page
            offset = (page - 1) * page_size
            data_query = f"""
                SELECT tip_id, tracking_code, category,
                       LEFT(description, 200) AS description_preview,
                       triage_score, urgency, status,
                       matched_tender_ids, matched_entity_ids,
                       submitted_at, updated_at, linked_case_id
                FROM whistleblower_tips
                {where_clause}
                ORDER BY {sort_by} {sort_order}
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([page_size, offset])

            rows = await conn.fetch(data_query, *params)

            tips = []
            for row in rows:
                tips.append({
                    'tip_id': row['tip_id'],
                    'tracking_code': row['tracking_code'],
                    'category': row['category'],
                    'description_preview': row['description_preview'],
                    'triage_score': row['triage_score'],
                    'urgency': row['urgency'],
                    'status': row['status'],
                    'matched_tender_ids': _parse_jsonb(row['matched_tender_ids']),
                    'matched_entity_ids': _parse_jsonb(row['matched_entity_ids']),
                    'submitted_at': row['submitted_at'].isoformat() if row['submitted_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                    'linked_case_id': row['linked_case_id'],
                })

            return {
                'tips': tips,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': max(1, (total + page_size - 1) // page_size),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list tips: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tips."
        )


@router.get("/admin/tips/{tip_id}", dependencies=[Depends(require_admin)])
async def get_tip_detail(tip_id: int):
    """Get full tip details including triage results, status history, and linked case.

    Returns all internal details visible only to administrators.
    """
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT tip_id, tracking_code, category, description,
                       evidence_urls, triage_score, urgency,
                       matched_tender_ids, matched_entity_ids,
                       extracted_entities, triage_details,
                       status, linked_case_id,
                       submitted_at, updated_at
                FROM whistleblower_tips
                WHERE tip_id = $1
                """,
                tip_id
            )

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tip with ID {tip_id} not found."
                )

            # Fetch status update history
            updates = await conn.fetch(
                """
                SELECT update_id, old_status, new_status, note, updated_by, updated_at
                FROM tip_status_updates
                WHERE tip_id = $1
                ORDER BY updated_at DESC
                """,
                tip_id
            )

            status_history = [
                {
                    'update_id': u['update_id'],
                    'old_status': u['old_status'],
                    'new_status': u['new_status'],
                    'note': u['note'],
                    'updated_by': u['updated_by'],
                    'updated_at': u['updated_at'].isoformat() if u['updated_at'] else None,
                }
                for u in updates
            ]

            # Fetch linked case info if available
            linked_case = None
            if row['linked_case_id']:
                case_row = await conn.fetchrow(
                    """
                    SELECT case_id, title, status
                    FROM investigation_cases
                    WHERE case_id = $1
                    """,
                    row['linked_case_id']
                )
                if case_row:
                    linked_case = {
                        'case_id': case_row['case_id'],
                        'title': case_row['title'],
                        'status': case_row['status'],
                    }

            triage_details = _parse_jsonb(row['triage_details']) or {}

            return {
                'tip_id': row['tip_id'],
                'tracking_code': row['tracking_code'],
                'category': row['category'],
                'description': row['description'],
                'evidence_urls': _parse_jsonb(row['evidence_urls']) or [],
                'triage_score': row['triage_score'],
                'urgency': row['urgency'],
                'matched_tender_ids': _parse_jsonb(row['matched_tender_ids']) or [],
                'matched_entity_ids': _parse_jsonb(row['matched_entity_ids']) or [],
                'extracted_entities': _parse_jsonb(row['extracted_entities']) or [],
                'triage_details': triage_details,
                'detail_richness': triage_details.get('detail_richness', 0),
                'specificity_score': triage_details.get('specificity_score', 0),
                'category_analysis': triage_details.get('category_analysis', ''),
                'suggested_actions': triage_details.get('suggested_actions', []),
                'status': row['status'],
                'linked_case_id': row['linked_case_id'],
                'linked_case': linked_case,
                'status_history': status_history,
                'submitted_at': row['submitted_at'].isoformat() if row['submitted_at'] else None,
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tip detail (id={tip_id}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tip details."
        )


@router.patch("/admin/tips/{tip_id}", dependencies=[Depends(require_admin)])
async def update_tip(tip_id: int, body: dict):
    """Update tip status and add analyst notes.

    Body: {
        "status": "reviewing" | "investigating" | "verified" | "dismissed",
        "note": "Analyst notes about this status change..." (optional)
    }

    Creates a status update record for audit trail.
    """
    new_status = (body.get('status') or '').strip().lower()
    note = (body.get('note') or '').strip()

    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status field is required."
        )

    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )

    if len(note) > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note is too long. Maximum 5,000 characters."
        )

    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Get current status
            current = await conn.fetchrow(
                "SELECT tip_id, status FROM whistleblower_tips WHERE tip_id = $1",
                tip_id
            )

            if not current:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tip with ID {tip_id} not found."
                )

            old_status = current['status']

            if old_status == new_status and not note:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No changes detected. Status is already the same and no note provided."
                )

            # Update the tip
            await conn.execute(
                """
                UPDATE whistleblower_tips
                SET status = $1, updated_at = NOW()
                WHERE tip_id = $2
                """,
                new_status, tip_id
            )

            # Record the status change
            await conn.execute(
                """
                INSERT INTO tip_status_updates (tip_id, old_status, new_status, note, updated_by)
                VALUES ($1, $2, $3, $4, 'admin')
                """,
                tip_id, old_status, new_status, note or None
            )

            logger.info(f"Tip {tip_id} status updated: {old_status} -> {new_status}")

            return {
                'tip_id': tip_id,
                'old_status': old_status,
                'new_status': new_status,
                'note': note or None,
                'updated_at': datetime.utcnow().isoformat(),
                'message': f"Tip status updated from '{old_status}' to '{new_status}'."
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tip {tip_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tip."
        )


@router.post("/admin/tips/{tip_id}/link-case", dependencies=[Depends(require_admin)])
async def link_tip_to_case(tip_id: int, body: dict):
    """Link a whistleblower tip to an investigation case.

    Body: {"case_id": 123}

    Updates the tip status to 'linked' and creates an audit trail entry.
    """
    case_id = body.get('case_id')
    if not case_id or not isinstance(case_id, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="case_id is required and must be an integer."
        )

    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Verify tip exists
            tip = await conn.fetchrow(
                "SELECT tip_id, status, linked_case_id FROM whistleblower_tips WHERE tip_id = $1",
                tip_id
            )
            if not tip:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tip with ID {tip_id} not found."
                )

            # Verify case exists
            case = await conn.fetchrow(
                "SELECT case_id, title, status FROM investigation_cases WHERE case_id = $1",
                case_id
            )
            if not case:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Investigation case with ID {case_id} not found."
                )

            old_status = tip['status']

            # Update tip with case link
            await conn.execute(
                """
                UPDATE whistleblower_tips
                SET linked_case_id = $1, status = 'linked', updated_at = NOW()
                WHERE tip_id = $2
                """,
                case_id, tip_id
            )

            # Record the status change
            await conn.execute(
                """
                INSERT INTO tip_status_updates (tip_id, old_status, new_status, note, updated_by)
                VALUES ($1, $2, 'linked', $3, 'admin')
                """,
                tip_id, old_status,
                f"Linked to investigation case #{case_id}: {case['title']}"
            )

            logger.info(f"Tip {tip_id} linked to investigation case {case_id}")

            return {
                'tip_id': tip_id,
                'case_id': case_id,
                'case_title': case['title'],
                'case_status': case['status'],
                'tip_status': 'linked',
                'message': f"Tip successfully linked to investigation case #{case_id}."
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to link tip {tip_id} to case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link tip to case."
        )


@router.get("/admin/stats", dependencies=[Depends(require_admin)])
async def get_whistleblower_stats():
    """Get whistleblower portal statistics.

    Returns aggregate statistics including:
    - Total tips count
    - Breakdown by status and category
    - Average triage score
    - Tips submitted this week and month
    - Urgency distribution
    - Linked cases count
    """
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Total tips
            total = await conn.fetchval("SELECT COUNT(*) FROM whistleblower_tips")

            # By status
            status_rows = await conn.fetch(
                """
                SELECT status, COUNT(*) AS count
                FROM whistleblower_tips
                GROUP BY status
                ORDER BY count DESC
                """
            )
            by_status = {row['status']: row['count'] for row in status_rows}

            # By category
            category_rows = await conn.fetch(
                """
                SELECT category, COUNT(*) AS count
                FROM whistleblower_tips
                GROUP BY category
                ORDER BY count DESC
                """
            )
            by_category = {row['category']: row['count'] for row in category_rows}

            # By urgency
            urgency_rows = await conn.fetch(
                """
                SELECT urgency, COUNT(*) AS count
                FROM whistleblower_tips
                GROUP BY urgency
                ORDER BY count DESC
                """
            )
            by_urgency = {row['urgency']: row['count'] for row in urgency_rows}

            # Average triage score
            avg_score = await conn.fetchval(
                "SELECT COALESCE(AVG(triage_score), 0) FROM whistleblower_tips"
            )

            # Tips this week
            tips_this_week = await conn.fetchval(
                """
                SELECT COUNT(*) FROM whistleblower_tips
                WHERE submitted_at >= NOW() - INTERVAL '7 days'
                """
            )

            # Tips this month
            tips_this_month = await conn.fetchval(
                """
                SELECT COUNT(*) FROM whistleblower_tips
                WHERE submitted_at >= DATE_TRUNC('month', NOW())
                """
            )

            # Linked to cases
            linked_count = await conn.fetchval(
                "SELECT COUNT(*) FROM whistleblower_tips WHERE linked_case_id IS NOT NULL"
            )

            # High priority (critical + high urgency, status != dismissed)
            high_priority = await conn.fetchval(
                """
                SELECT COUNT(*) FROM whistleblower_tips
                WHERE urgency IN ('critical', 'high')
                  AND status NOT IN ('dismissed', 'verified', 'linked')
                """
            )

            # Average time to first review (from new to reviewing)
            avg_review_time = await conn.fetchval(
                """
                SELECT AVG(EXTRACT(EPOCH FROM (u.updated_at - t.submitted_at)) / 3600)
                FROM tip_status_updates u
                JOIN whistleblower_tips t ON t.tip_id = u.tip_id
                WHERE u.new_status = 'reviewing' AND u.old_status = 'new'
                """
            )

            return {
                'total_tips': total,
                'by_status': by_status,
                'by_category': by_category,
                'by_urgency': by_urgency,
                'avg_triage_score': round(float(avg_score), 1),
                'tips_this_week': tips_this_week,
                'tips_this_month': tips_this_month,
                'linked_to_cases': linked_count,
                'high_priority_pending': high_priority,
                'avg_review_time_hours': round(float(avg_review_time), 1) if avg_review_time else None,
            }

    except Exception as e:
        logger.error(f"Failed to compute whistleblower stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics."
        )
