"""
Backend Alert Matching Engine - Phase 6.1
Intelligent tender alert system with matching engine and notification management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func, text
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
import logging
import json
import re

from database import get_db
from models import User
from api.auth import get_current_user
from api.corruption import latin_to_cyrillic

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"]
)


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class AlertCriteria(BaseModel):
    """Flexible criteria for alert matching"""
    keywords: Optional[List[str]] = Field(None, description="Keywords to match in title/description")
    cpv_codes: Optional[List[str]] = Field(None, description="CPV codes to match (4-digit prefix)")
    entities: Optional[List[str]] = Field(None, description="Procuring entities to match")
    budget_min: Optional[float] = Field(None, description="Minimum budget in MKD")
    budget_max: Optional[float] = Field(None, description="Maximum budget in MKD")
    competitors: Optional[List[str]] = Field(None, description="Competitor companies to track")


class AlertCreate(BaseModel):
    """Schema for creating a new alert"""
    name: str = Field(..., min_length=1, max_length=200, description="Alert name")
    alert_type: str = Field(..., description="Alert type: keyword, cpv, entity, competitor, budget")
    criteria: AlertCriteria = Field(..., description="Alert matching criteria")
    notification_channels: List[str] = Field(["email", "in_app"], description="Notification channels")


class AlertUpdate(BaseModel):
    """Schema for updating an alert"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    criteria: Optional[AlertCriteria] = None
    is_active: Optional[bool] = None
    notification_channels: Optional[List[str]] = None


class AlertResponse(BaseModel):
    """Schema for alert response"""
    alert_id: UUID
    user_id: UUID
    name: str
    alert_type: str
    criteria: Dict[str, Any]
    is_active: bool
    notification_channels: List[str]
    created_at: datetime
    updated_at: datetime
    match_count: Optional[int] = None
    unread_count: Optional[int] = None

    class Config:
        from_attributes = True


class MatchReason(BaseModel):
    """Match reason detail"""
    type: str
    message: str


class AlertMatchResponse(BaseModel):
    """Schema for alert match response"""
    match_id: UUID
    alert_id: UUID
    tender_id: str
    tender_source: str
    match_score: float
    match_reasons: List[str]
    is_read: bool
    notified_at: Optional[datetime]
    created_at: datetime
    tender_details: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class MarkReadRequest(BaseModel):
    """Schema for marking matches as read"""
    match_ids: List[UUID] = Field(..., description="List of match IDs to mark as read")


class CheckAlertsResponse(BaseModel):
    """Response for check-now endpoint"""
    alerts_checked: int
    matches_found: int
    tenders_scanned: int
    execution_time_ms: int


# ============================================================================
# ALERT MATCHING ENGINE
# ============================================================================

async def check_alert_against_tender(alert: dict, tender: dict) -> tuple[bool, float, list]:
    """
    Check if tender matches alert criteria

    Returns:
        tuple: (matches: bool, score: float, reasons: List[str])
    """
    criteria = alert.get('criteria', {})
    score = 0.0
    reasons = []

    # Keyword matching (bilingual: checks both Latin and Cyrillic variants)
    if criteria.get('keywords'):
        tender_text = f"{tender.get('title', '')} {tender.get('description', '')}".lower()
        matched_keywords = []
        for kw in criteria['keywords']:
            kw_lower = kw.lower()
            kw_cyrillic = latin_to_cyrillic(kw).lower()
            # Short keywords (<=3 chars) use word boundary to avoid false positives
            if len(kw_lower) <= 3:
                pattern = r'(?<!\w)' + re.escape(kw_lower) + r'(?!\w)'
                if re.search(pattern, tender_text):
                    matched_keywords.append(kw)
                elif kw_cyrillic != kw_lower:
                    pattern_cyr = r'(?<!\w)' + re.escape(kw_cyrillic) + r'(?!\w)'
                    if re.search(pattern_cyr, tender_text):
                        matched_keywords.append(kw)
            else:
                if kw_lower in tender_text or (kw_cyrillic != kw_lower and kw_cyrillic in tender_text):
                    matched_keywords.append(kw)

        if matched_keywords:
            score += 25
            reasons.append(f"Keywords matched: {', '.join(matched_keywords)}")

    # CPV code matching (match first 4 digits for category matching)
    if criteria.get('cpv_codes'):
        tender_cpv = tender.get('cpv_code', '')
        matched_cpvs = []
        for cpv in criteria['cpv_codes']:
            if tender_cpv and tender_cpv.startswith(cpv[:4]):
                matched_cpvs.append(cpv)

        if matched_cpvs:
            score += 30
            reasons.append(f"CPV codes matched: {', '.join(matched_cpvs)}")

    # Entity matching
    if criteria.get('entities'):
        entity = tender.get('procuring_entity', '').lower()
        matched_entities = []
        for e in criteria['entities']:
            if e.lower() in entity:
                matched_entities.append(e)

        if matched_entities:
            score += 25
            reasons.append(f"Entities matched: {', '.join(matched_entities)}")

    # Budget range matching
    if criteria.get('budget_min') is not None or criteria.get('budget_max') is not None:
        value = tender.get('estimated_value_mkd') or 0
        budget_min = criteria.get('budget_min', 0)
        budget_max = criteria.get('budget_max', float('inf'))

        if budget_min <= value <= budget_max:
            score += 20
            reasons.append(f"Budget in range: {value:,.0f} MKD")

    # Competitor tracking (check winner field for awarded tenders)
    if criteria.get('competitors'):
        winner = tender.get('winner', '').lower()
        matched_competitors = []
        for comp in criteria['competitors']:
            if comp.lower() in winner:
                matched_competitors.append(comp)

        if matched_competitors:
            score += 25
            reasons.append(f"Competitors matched: {', '.join(matched_competitors)}")

    # Require at least one meaningful criterion (keyword=25, CPV=30, entity=25)
    # Budget-only match (20) is not enough on its own
    matches = score >= 25
    final_score = min(score, 100.0)

    return matches, final_score, reasons


async def check_alerts_for_user(db: AsyncSession, user_id: UUID, limit_tenders: int = 100) -> Dict[str, Any]:
    """
    Check all active alerts for a user against recent tenders

    Args:
        db: Database session
        user_id: User UUID
        limit_tenders: Number of recent tenders to check

    Returns:
        dict: Statistics about matching process
    """
    start_time = datetime.now()

    # Get all active alerts for user
    alerts_result = await db.execute(
        select(text("alert_id, name, alert_type, criteria"))
        .select_from(text("tender_alerts"))
        .where(text("user_id = :user_id AND is_active = true"))
        .params(user_id=str(user_id))
    )
    alerts = [
        {
            'alert_id': row[0],
            'name': row[1],
            'alert_type': row[2],
            'criteria': row[3]
        }
        for row in alerts_result.fetchall()
    ]

    if not alerts:
        return {
            'alerts_checked': 0,
            'matches_found': 0,
            'tenders_scanned': 0,
            'execution_time_ms': 0
        }

    # Get recent tenders from both e-nabavki AND e-pazar
    tenders_result = await db.execute(
        text("""
            (SELECT tender_id, title, description, procuring_entity,
                    estimated_value_mkd, cpv_code, winner,
                    'e-nabavki' as source, created_at
             FROM tenders
             ORDER BY created_at DESC
             LIMIT :limit)
            UNION ALL
            (SELECT tender_id, title, description, contracting_authority,
                    estimated_value_mkd, cpv_code, '',
                    'e-pazar' as source, created_at
             FROM epazar_tenders
             ORDER BY created_at DESC
             LIMIT :limit)
            ORDER BY created_at DESC
            LIMIT :limit
        """).params(limit=limit_tenders)
    )

    tenders = [
        {
            'tender_id': row[0],
            'title': row[1],
            'description': row[2],
            'procuring_entity': row[3],
            'estimated_value_mkd': float(row[4]) if row[4] else 0,
            'cpv_code': row[5],
            'winner': row[6],
            'source': row[7]
        }
        for row in tenders_result.fetchall()
    ]

    matches_found = 0

    # Check each alert against each tender
    for alert in alerts:
        for tender in tenders:
            # Check if match already exists
            existing_match = await db.execute(
                text("""
                    SELECT match_id FROM alert_matches
                    WHERE alert_id = :alert_id AND tender_id = :tender_id
                """).params(
                    alert_id=str(alert['alert_id']),
                    tender_id=tender['tender_id']
                )
            )

            if existing_match.scalar():
                continue  # Skip if already matched

            # Check if tender matches alert criteria
            matches, score, reasons = await check_alert_against_tender(alert, tender)

            if matches:
                # Insert match record
                await db.execute(
                    text("""
                        INSERT INTO alert_matches
                        (alert_id, tender_id, tender_source, match_score, match_reasons, is_read, created_at)
                        VALUES (:alert_id, :tender_id, :tender_source, :match_score, CAST(:match_reasons AS jsonb), false, NOW())
                    """).params(
                        alert_id=str(alert['alert_id']),
                        tender_id=tender['tender_id'],
                        tender_source=tender['source'],
                        match_score=score,
                        match_reasons=json.dumps(reasons)
                    )
                )
                matches_found += 1

    await db.commit()

    execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

    return {
        'alerts_checked': len(alerts),
        'matches_found': matches_found,
        'tenders_scanned': len(tenders),
        'execution_time_ms': execution_time
    }


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("")
async def list_alerts(
    include_counts: bool = Query(True, description="Include match counts"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all alerts for the current user with optional match counts
    """
    # Get alerts
    result = await db.execute(
        text("""
            SELECT alert_id, user_id, name, alert_type, criteria,
                   is_active, notification_channels, created_at, updated_at
            FROM tender_alerts
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """).params(user_id=str(current_user.user_id))
    )

    alerts = []
    for row in result.fetchall():
        # Parse JSONB fields
        criteria = row[4] if isinstance(row[4], dict) else (json.loads(row[4]) if row[4] else {})
        channels = row[6] if isinstance(row[6], list) else (json.loads(row[6]) if row[6] else [])

        alert_dict = {
            'id': str(row[0]),
            'alert_id': row[0],
            'user_id': row[1],
            'name': row[2],
            'alert_type': row[3],
            'criteria': criteria,
            'is_active': row[5],
            'channels': channels,
            'notification_channels': channels,
            'created_at': row[7].isoformat() if row[7] else None,
            'updated_at': row[8].isoformat() if row[8] else None
        }

        # Get match counts if requested
        if include_counts:
            counts_result = await db.execute(
                text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE NOT is_read) as unread
                    FROM alert_matches
                    WHERE alert_id = :alert_id
                """).params(alert_id=str(row[0]))
            )
            counts = counts_result.fetchone()
            alert_dict['match_count'] = counts[0] if counts else 0
            alert_dict['unread_count'] = counts[1] if counts else 0

        alerts.append(alert_dict)

    return {'alerts': alerts, 'total': len(alerts)}


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new tender alert
    """
    # Validate alert_type
    valid_types = ['keyword', 'cpv', 'entity', 'competitor', 'budget', 'combined']
    if alert.alert_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid alert_type. Must be one of: {', '.join(valid_types)}"
        )

    # Insert alert
    result = await db.execute(
        text("""
            INSERT INTO tender_alerts
            (user_id, name, alert_type, criteria, notification_channels, is_active, created_at, updated_at)
            VALUES (:user_id, :name, :alert_type, :criteria, :notification_channels, true, NOW(), NOW())
            RETURNING alert_id, user_id, name, alert_type, criteria, is_active,
                      notification_channels, created_at, updated_at
        """).params(
            user_id=str(current_user.user_id),
            name=alert.name,
            alert_type=alert.alert_type,
            criteria=alert.criteria.model_dump(exclude_none=True),
            notification_channels=alert.notification_channels
        )
    )

    await db.commit()

    row = result.fetchone()
    return AlertResponse(
        alert_id=row[0],
        user_id=row[1],
        name=row[2],
        alert_type=row[3],
        criteria=row[4],
        is_active=row[5],
        notification_channels=row[6],
        created_at=row[7],
        updated_at=row[8]
    )


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: UUID,
    alert_update: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing alert
    """
    # Verify alert belongs to user
    check_result = await db.execute(
        text("SELECT user_id FROM tender_alerts WHERE alert_id = :alert_id")
        .params(alert_id=str(alert_id))
    )
    row = check_result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    if str(row[0]) != str(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this alert"
        )

    # Build update query dynamically
    update_fields = []
    params = {'alert_id': str(alert_id)}

    if alert_update.name is not None:
        update_fields.append("name = :name")
        params['name'] = alert_update.name

    if alert_update.criteria is not None:
        update_fields.append("criteria = :criteria")
        params['criteria'] = alert_update.criteria.model_dump(exclude_none=True)

    if alert_update.is_active is not None:
        update_fields.append("is_active = :is_active")
        params['is_active'] = alert_update.is_active

    if alert_update.notification_channels is not None:
        update_fields.append("notification_channels = :notification_channels")
        params['notification_channels'] = alert_update.notification_channels

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_fields.append("updated_at = NOW()")

    # Execute update
    result = await db.execute(
        text(f"""
            UPDATE tender_alerts
            SET {', '.join(update_fields)}
            WHERE alert_id = :alert_id
            RETURNING alert_id, user_id, name, alert_type, criteria, is_active,
                      notification_channels, created_at, updated_at
        """).params(**params)
    )

    await db.commit()

    row = result.fetchone()
    return AlertResponse(
        alert_id=row[0],
        user_id=row[1],
        name=row[2],
        alert_type=row[3],
        criteria=row[4],
        is_active=row[5],
        notification_channels=row[6],
        created_at=row[7],
        updated_at=row[8]
    )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an alert (cascade deletes all matches)
    """
    # Verify alert belongs to user
    check_result = await db.execute(
        text("SELECT user_id FROM tender_alerts WHERE alert_id = :alert_id")
        .params(alert_id=str(alert_id))
    )
    row = check_result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    if str(row[0]) != str(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this alert"
        )

    # Delete alert (matches will be cascade deleted)
    await db.execute(
        text("DELETE FROM tender_alerts WHERE alert_id = :alert_id")
        .params(alert_id=str(alert_id))
    )

    await db.commit()
    return None


@router.get("/{alert_id}/matches", response_model=List[AlertMatchResponse])
async def get_alert_matches(
    alert_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="Number of matches to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    unread_only: bool = Query(False, description="Return only unread matches"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get matches for a specific alert with pagination
    """
    # Verify alert belongs to user
    check_result = await db.execute(
        text("SELECT user_id FROM tender_alerts WHERE alert_id = :alert_id")
        .params(alert_id=str(alert_id))
    )
    row = check_result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    if str(row[0]) != str(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this alert's matches"
        )

    # Build query with optional unread filter
    where_clause = "WHERE alert_id = :alert_id"
    if unread_only:
        where_clause += " AND NOT is_read"

    # Get matches
    result = await db.execute(
        text(f"""
            SELECT match_id, alert_id, tender_id, tender_source, match_score,
                   match_reasons, is_read, notified_at, created_at
            FROM alert_matches
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """).params(
            alert_id=str(alert_id),
            limit=limit,
            offset=offset
        )
    )

    matches = []
    for row in result.fetchall():
        # Fetch tender details (try e-nabavki first, then e-pazar)
        tender_result = await db.execute(
            text("""
                SELECT tender_id, title, procuring_entity, estimated_value_mkd,
                       closing_date, status, cpv_code
                FROM tenders
                WHERE tender_id = :tender_id
            """).params(tender_id=row[2])
        )
        tender_row = tender_result.fetchone()

        if not tender_row:
            # Try e-pazar
            tender_result = await db.execute(
                text("""
                    SELECT tender_id, title, contracting_authority, estimated_value_mkd,
                           closing_date, status, cpv_code
                    FROM epazar_tenders
                    WHERE tender_id = :tender_id
                """).params(tender_id=row[2])
            )
            tender_row = tender_result.fetchone()

        tender_details = None
        if tender_row:
            tender_details = {
                'tender_id': tender_row[0],
                'title': tender_row[1],
                'procuring_entity': tender_row[2],
                'estimated_value_mkd': float(tender_row[3]) if tender_row[3] else None,
                'closing_date': tender_row[4].isoformat() if tender_row[4] else None,
                'status': tender_row[5],
                'cpv_code': tender_row[6]
            }

        matches.append(AlertMatchResponse(
            match_id=row[0],
            alert_id=row[1],
            tender_id=row[2],
            tender_source=row[3],
            match_score=float(row[4]),
            match_reasons=row[5],
            is_read=row[6],
            notified_at=row[7],
            created_at=row[8],
            tender_details=tender_details
        ))

    return matches


@router.post("/mark-read")
async def mark_matches_read(
    request: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark specified matches as read
    """
    if not request.match_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No match IDs provided"
        )

    # Verify all matches belong to user's alerts
    verify_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM alert_matches am
            JOIN tender_alerts ta ON am.alert_id = ta.alert_id
            WHERE am.match_id = ANY(:match_ids) AND ta.user_id = :user_id
        """).params(
            match_ids=[str(mid) for mid in request.match_ids],
            user_id=str(current_user.user_id)
        )
    )

    count = verify_result.scalar()
    if count != len(request.match_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to mark some of these matches"
        )

    # Mark as read
    await db.execute(
        text("""
            UPDATE alert_matches
            SET is_read = true
            WHERE match_id = ANY(:match_ids)
        """).params(match_ids=[str(mid) for mid in request.match_ids])
    )

    await db.commit()

    return {
        "success": True,
        "marked_read": len(request.match_ids)
    }


@router.post("/matches/read")
async def mark_matches_read_alt(
    request: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Alias for /mark-read (frontend compatibility)"""
    return await mark_matches_read(request, db, current_user)


@router.post("/check-now", response_model=CheckAlertsResponse)
async def check_alerts_now(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Force check all active alerts for the current user against recent tenders
    Useful for testing and immediate updates
    """
    result = await check_alerts_for_user(db, current_user.user_id, limit_tenders=100)

    return CheckAlertsResponse(
        alerts_checked=result['alerts_checked'],
        matches_found=result['matches_found'],
        tenders_scanned=result['tenders_scanned'],
        execution_time_ms=result['execution_time_ms']
    )


@router.get("/matches")
async def get_all_matches(
    alert_id: Optional[str] = Query(None, description="Filter by specific alert ID"),
    limit: int = Query(50, ge=1, le=200, description="Number of matches to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    unread_only: bool = Query(False, description="Return only unread matches"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all matches across all user's alerts, optionally filtered by alert_id
    """
    # Build query based on filters
    if alert_id:
        # Verify alert belongs to user
        check_result = await db.execute(
            text("SELECT user_id FROM tender_alerts WHERE alert_id = :alert_id")
            .params(alert_id=alert_id)
        )
        row = check_result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )

        if str(row[0]) != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this alert's matches"
            )

        where_clause = "WHERE am.alert_id = :alert_id"
        params = {'alert_id': alert_id, 'limit': limit, 'offset': offset}
    else:
        where_clause = "WHERE ta.user_id = :user_id"
        params = {'user_id': str(current_user.user_id), 'limit': limit, 'offset': offset}

    if unread_only:
        where_clause += " AND NOT am.is_read"

    # Get matches with alert names
    result = await db.execute(
        text(f"""
            SELECT am.match_id, am.alert_id, ta.name as alert_name, am.tender_id,
                   am.tender_source, am.match_score, am.match_reasons, am.is_read,
                   am.notified_at, am.created_at
            FROM alert_matches am
            JOIN tender_alerts ta ON am.alert_id = ta.alert_id
            {where_clause}
            ORDER BY am.created_at DESC
            LIMIT :limit OFFSET :offset
        """).params(**params)
    )

    matches = []
    for row in result.fetchall():
        # Fetch tender details (try e-nabavki first, then e-pazar)
        tender_result = await db.execute(
            text("""
                SELECT tender_id, title, procuring_entity, estimated_value_mkd,
                       closing_date, status, cpv_code
                FROM tenders
                WHERE tender_id = :tender_id
            """).params(tender_id=row[3])
        )
        tender_row = tender_result.fetchone()

        if not tender_row:
            # Try e-pazar
            tender_result = await db.execute(
                text("""
                    SELECT tender_id, title, contracting_authority, estimated_value_mkd,
                           closing_date, status, cpv_code
                    FROM epazar_tenders
                    WHERE tender_id = :tender_id
                """).params(tender_id=row[3])
            )
            tender_row = tender_result.fetchone()

        tender_details = None
        if tender_row:
            tender_details = {
                'tender_id': tender_row[0],
                'title': tender_row[1],
                'procuring_entity': tender_row[2],
                'estimated_value_mkd': float(tender_row[3]) if tender_row[3] else None,
                'closing_date': tender_row[4].isoformat() if tender_row[4] else None,
                'status': tender_row[5],
                'cpv_code': tender_row[6]
            }

        # Parse match_reasons (JSONB comes as list or string)
        reasons_raw = row[6]
        if isinstance(reasons_raw, str):
            try:
                reasons_parsed = json.loads(reasons_raw)
            except (json.JSONDecodeError, TypeError):
                reasons_parsed = [reasons_raw] if reasons_raw else []
        elif isinstance(reasons_raw, list):
            reasons_parsed = reasons_raw
        else:
            reasons_parsed = []

        matches.append({
            'match_id': str(row[0]),
            'alert_id': str(row[1]),
            'alert_name': row[2],
            'tender_id': row[3],
            'tender_source': row[4],
            'match_score': float(row[5]),
            'match_reasons': reasons_parsed,
            'is_read': row[7],
            'notified_at': row[8].isoformat() if row[8] else None,
            'created_at': row[9].isoformat() if row[9] else None,
            'matched_at': row[9].isoformat() if row[9] else None,
            'tender_title': tender_details.get('title', '') if tender_details else '',
            'tender': tender_details,
            'tender_details': tender_details
        })

    # Get total count
    count_result = await db.execute(
        text(f"""
            SELECT COUNT(*)
            FROM alert_matches am
            JOIN tender_alerts ta ON am.alert_id = ta.alert_id
            {where_clause.replace(':limit', '0').replace(':offset', '0')}
        """).params(**{k: v for k, v in params.items() if k not in ['limit', 'offset']})
    )
    total = count_result.scalar() or 0

    return {
        'matches': matches,
        'total': total
    }


# ============================================================================
# MATCH FEEDBACK
# ============================================================================

class MatchFeedbackRequest(BaseModel):
    """Schema for submitting feedback on a match"""
    match_id: UUID
    feedback: str = Field(..., description="'up' or 'down'")


@router.post("/matches/feedback")
async def submit_match_feedback(
    request: MatchFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit thumbs up/down feedback on an alert match
    """
    if request.feedback not in ('up', 'down'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback must be 'up' or 'down'"
        )

    # Verify match belongs to user's alert
    verify_result = await db.execute(
        text("""
            SELECT am.match_id FROM alert_matches am
            JOIN tender_alerts ta ON ta.alert_id = am.alert_id
            WHERE am.match_id = :match_id AND ta.user_id = :user_id
        """).params(
            match_id=str(request.match_id),
            user_id=str(current_user.user_id)
        )
    )

    if not verify_result.scalar():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to provide feedback on this match"
        )

    await db.execute(
        text("""
            UPDATE alert_matches
            SET user_feedback = :feedback, feedback_at = NOW()
            WHERE match_id = :match_id
        """).params(
            feedback=request.feedback,
            match_id=str(request.match_id)
        )
    )

    await db.commit()

    return {
        "success": True,
        "match_id": str(request.match_id),
        "feedback": request.feedback
    }
