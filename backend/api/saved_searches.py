"""
Saved Searches API endpoints
CRUD operations for user saved searches/alerts
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
import json

from database import get_db
from models import User, Alert
from api.auth import get_current_user

# Note: Using "/queries" instead of "/search" to avoid ad-blocker keyword filters
router = APIRouter(prefix="/queries", tags=["saved-queries"])


# ============================================================================
# TIER LIMITS
# ============================================================================

SAVED_SEARCH_LIMITS = {
    "free": 3,
    "starter": 10,
    "professional": 50,
    "enterprise": 500
}


# ============================================================================
# SCHEMAS
# ============================================================================

class SavedSearchFilters(BaseModel):
    """Search filter criteria"""
    query: Optional[str] = None
    category: Optional[str] = None
    cpv_code: Optional[str] = None
    procuring_entity: Optional[str] = None
    status: Optional[str] = None
    min_value_mkd: Optional[float] = None
    max_value_mkd: Optional[float] = None
    source_category: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    procedure_type: Optional[str] = None
    closing_date_from: Optional[str] = None
    closing_date_to: Optional[str] = None


class SavedSearchCreate(BaseModel):
    """Request schema for creating a saved search"""
    name: str = Field(..., min_length=1, max_length=255, description="Name for this saved search")
    filters: SavedSearchFilters = Field(..., description="Search filter criteria")
    notify_on_match: bool = Field(default=False, description="Send notifications when new matches found")
    notification_frequency: str = Field(default="daily", description="Notification frequency: instant, daily, weekly")


class SavedSearchUpdate(BaseModel):
    """Request schema for updating a saved search"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    filters: Optional[SavedSearchFilters] = None
    notify_on_match: Optional[bool] = None
    notification_frequency: Optional[str] = None
    is_active: Optional[bool] = None


class SavedSearchResponse(BaseModel):
    """Response schema for a saved search"""
    id: str
    name: str
    filters: dict
    notify_on_match: bool
    notification_frequency: str
    is_active: bool
    match_count: int = 0
    last_triggered: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SavedSearchListResponse(BaseModel):
    """Response schema for list of saved searches"""
    total: int
    limit: int
    used: int
    items: List[SavedSearchResponse]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_tier(user: User) -> str:
    """Get user subscription tier"""
    tier = getattr(user, 'subscription_tier', 'free')
    if tier is None:
        tier = 'free'
    return tier.lower()


async def count_user_saved_searches(db: AsyncSession, user_id: UUID) -> int:
    """Count user's saved searches"""
    result = await db.execute(
        text("SELECT COUNT(*) FROM alerts WHERE user_id = :user_id"),
        {"user_id": str(user_id)}
    )
    return result.scalar() or 0


async def count_matching_tenders(db: AsyncSession, filters: dict) -> int:
    """Count tenders matching the search filters"""
    conditions = ["1=1"]
    params = {}

    if filters.get("query"):
        conditions.append("(title ILIKE :query OR description ILIKE :query)")
        params["query"] = f"%{filters['query']}%"

    if filters.get("category"):
        conditions.append("category = :category")
        params["category"] = filters["category"]

    if filters.get("cpv_code"):
        conditions.append("cpv_code LIKE :cpv_code")
        params["cpv_code"] = f"{filters['cpv_code']}%"

    if filters.get("procuring_entity"):
        conditions.append("procuring_entity ILIKE :entity")
        params["entity"] = f"%{filters['procuring_entity']}%"

    if filters.get("status"):
        conditions.append("status = :status")
        params["status"] = filters["status"]

    if filters.get("min_value_mkd"):
        conditions.append("estimated_value_mkd >= :min_value")
        params["min_value"] = filters["min_value_mkd"]

    if filters.get("max_value_mkd"):
        conditions.append("estimated_value_mkd <= :max_value")
        params["max_value"] = filters["max_value_mkd"]

    if filters.get("source_category"):
        conditions.append("source_category = :source_category")
        params["source_category"] = filters["source_category"]

    query = text(f"SELECT COUNT(*) FROM tenders WHERE {' AND '.join(conditions)}")
    result = await db.execute(query, params)
    return result.scalar() or 0


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/saved", response_model=SavedSearchListResponse)
async def list_saved_searches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all saved searches for the current user.

    Returns saved searches with match counts and tier limits.
    """
    user_id = current_user.user_id
    tier = get_user_tier(current_user)
    limit = SAVED_SEARCH_LIMITS.get(tier, 3)

    # Get all saved searches
    query = text("""
        SELECT
            alert_id, name, filters, frequency, is_active, last_triggered, created_at
        FROM alerts
        WHERE user_id = :user_id
        ORDER BY created_at DESC
    """)

    result = await db.execute(query, {"user_id": str(user_id)})
    rows = result.fetchall()

    items = []
    for row in rows:
        # Parse filters JSON
        filters = row.filters if isinstance(row.filters, dict) else {}

        # Count matching tenders
        match_count = await count_matching_tenders(db, filters)

        items.append(SavedSearchResponse(
            id=str(row.alert_id),
            name=row.name,
            filters=filters,
            notify_on_match=row.is_active or False,
            notification_frequency=row.frequency or "daily",
            is_active=row.is_active or False,
            match_count=match_count,
            last_triggered=row.last_triggered,
            created_at=row.created_at
        ))

    return SavedSearchListResponse(
        total=len(items),
        limit=limit,
        used=len(items),
        items=items
    )


@router.post("/saved", response_model=SavedSearchResponse, status_code=201)
async def create_saved_search(
    search: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new saved search.

    Tier limits:
    - Free: 3 saved searches
    - Starter: 10 saved searches
    - Professional: 50 saved searches
    - Enterprise: 500 saved searches
    """
    user_id = current_user.user_id
    tier = get_user_tier(current_user)
    limit = SAVED_SEARCH_LIMITS.get(tier, 3)

    # Check tier limit
    current_count = await count_user_saved_searches(db, user_id)
    if current_count >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                "message": f"Saved search limit reached. Your {tier} tier allows {limit} saved searches.",
                "tier": tier,
                "limit": limit,
                "used": current_count,
                "upgrade_url": "/pricing"
            }
        )

    # Validate notification frequency
    valid_frequencies = ["instant", "daily", "weekly"]
    if search.notification_frequency not in valid_frequencies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid notification frequency. Must be one of: {valid_frequencies}"
        )

    # Convert filters to dict
    filters_dict = search.filters.dict(exclude_none=True)

    # Create saved search using alerts table
    insert_query = text("""
        INSERT INTO alerts (user_id, name, filters, frequency, is_active, created_at)
        VALUES (:user_id, :name, :filters::jsonb, :frequency, :is_active, NOW())
        RETURNING alert_id, name, filters, frequency, is_active, last_triggered, created_at
    """)

    result = await db.execute(insert_query, {
        "user_id": str(user_id),
        "name": search.name,
        "filters": json.dumps(filters_dict),
        "frequency": search.notification_frequency,
        "is_active": search.notify_on_match
    })
    await db.commit()

    row = result.fetchone()

    # Count matching tenders
    match_count = await count_matching_tenders(db, filters_dict)

    return SavedSearchResponse(
        id=str(row.alert_id),
        name=row.name,
        filters=row.filters if isinstance(row.filters, dict) else filters_dict,
        notify_on_match=row.is_active or False,
        notification_frequency=row.frequency or "daily",
        is_active=row.is_active or False,
        match_count=match_count,
        last_triggered=row.last_triggered,
        created_at=row.created_at
    )


@router.get("/saved/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific saved search by ID.
    """
    user_id = current_user.user_id

    query = text("""
        SELECT alert_id, name, filters, frequency, is_active, last_triggered, created_at
        FROM alerts
        WHERE alert_id = :search_id AND user_id = :user_id
    """)

    result = await db.execute(query, {
        "search_id": search_id,
        "user_id": str(user_id)
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Saved search not found")

    filters = row.filters if isinstance(row.filters, dict) else {}
    match_count = await count_matching_tenders(db, filters)

    return SavedSearchResponse(
        id=str(row.alert_id),
        name=row.name,
        filters=filters,
        notify_on_match=row.is_active or False,
        notification_frequency=row.frequency or "daily",
        is_active=row.is_active or False,
        match_count=match_count,
        last_triggered=row.last_triggered,
        created_at=row.created_at
    )


@router.put("/saved/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: str,
    update: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing saved search.
    """
    user_id = current_user.user_id

    # Verify ownership
    check_query = text("""
        SELECT alert_id FROM alerts
        WHERE alert_id = :search_id AND user_id = :user_id
    """)
    check_result = await db.execute(check_query, {
        "search_id": search_id,
        "user_id": str(user_id)
    })
    if not check_result.fetchone():
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Build update query dynamically
    update_fields = []
    params = {"search_id": search_id, "user_id": str(user_id)}

    if update.name is not None:
        update_fields.append("name = :name")
        params["name"] = update.name

    if update.filters is not None:
        update_fields.append("filters = :filters::jsonb")
        params["filters"] = json.dumps(update.filters.dict(exclude_none=True))

    if update.notify_on_match is not None:
        update_fields.append("is_active = :is_active")
        params["is_active"] = update.notify_on_match

    if update.notification_frequency is not None:
        valid_frequencies = ["instant", "daily", "weekly"]
        if update.notification_frequency not in valid_frequencies:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid notification frequency. Must be one of: {valid_frequencies}"
            )
        update_fields.append("frequency = :frequency")
        params["frequency"] = update.notification_frequency

    if update.is_active is not None:
        update_fields.append("is_active = :active")
        params["active"] = update.is_active

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_query = text(f"""
        UPDATE alerts
        SET {', '.join(update_fields)}
        WHERE alert_id = :search_id AND user_id = :user_id
        RETURNING alert_id, name, filters, frequency, is_active, last_triggered, created_at
    """)

    result = await db.execute(update_query, params)
    await db.commit()

    row = result.fetchone()
    filters = row.filters if isinstance(row.filters, dict) else {}
    match_count = await count_matching_tenders(db, filters)

    return SavedSearchResponse(
        id=str(row.alert_id),
        name=row.name,
        filters=filters,
        notify_on_match=row.is_active or False,
        notification_frequency=row.frequency or "daily",
        is_active=row.is_active or False,
        match_count=match_count,
        last_triggered=row.last_triggered,
        created_at=row.created_at
    )


@router.delete("/saved/{search_id}")
async def delete_saved_search(
    search_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a saved search.
    """
    user_id = current_user.user_id

    # Delete and verify ownership in single query
    delete_query = text("""
        DELETE FROM alerts
        WHERE alert_id = :search_id AND user_id = :user_id
        RETURNING alert_id
    """)

    result = await db.execute(delete_query, {
        "search_id": search_id,
        "user_id": str(user_id)
    })
    await db.commit()

    deleted = result.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved search not found")

    return {"message": "Saved search deleted successfully", "id": search_id}


@router.post("/saved/{search_id}/run")
async def run_saved_search(
    search_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute a saved search and return matching tenders.
    """
    user_id = current_user.user_id

    # Get saved search
    query = text("""
        SELECT filters FROM alerts
        WHERE alert_id = :search_id AND user_id = :user_id
    """)

    result = await db.execute(query, {
        "search_id": search_id,
        "user_id": str(user_id)
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Saved search not found")

    filters = row.filters if isinstance(row.filters, dict) else {}

    # Build tender query
    conditions = ["1=1"]
    params = {"limit": page_size, "offset": (page - 1) * page_size}

    if filters.get("query"):
        conditions.append("(title ILIKE :query OR description ILIKE :query)")
        params["query"] = f"%{filters['query']}%"

    if filters.get("category"):
        conditions.append("category = :category")
        params["category"] = filters["category"]

    if filters.get("cpv_code"):
        conditions.append("cpv_code LIKE :cpv_code")
        params["cpv_code"] = f"{filters['cpv_code']}%"

    if filters.get("procuring_entity"):
        conditions.append("procuring_entity ILIKE :entity")
        params["entity"] = f"%{filters['procuring_entity']}%"

    if filters.get("status"):
        conditions.append("status = :status")
        params["status"] = filters["status"]

    if filters.get("min_value_mkd"):
        conditions.append("estimated_value_mkd >= :min_value")
        params["min_value"] = filters["min_value_mkd"]

    if filters.get("max_value_mkd"):
        conditions.append("estimated_value_mkd <= :max_value")
        params["max_value"] = filters["max_value_mkd"]

    if filters.get("source_category"):
        conditions.append("source_category = :source_category")
        params["source_category"] = filters["source_category"]

    where_clause = " AND ".join(conditions)

    # Count total
    count_query = text(f"SELECT COUNT(*) FROM tenders WHERE {where_clause}")
    count_params = {k: v for k, v in params.items() if k not in ["limit", "offset"]}
    total_result = await db.execute(count_query, count_params)
    total = total_result.scalar() or 0

    # Get tenders
    tenders_query = text(f"""
        SELECT tender_id, title, procuring_entity, category, cpv_code,
               estimated_value_mkd, status, closing_date, source_url
        FROM tenders
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    tenders_result = await db.execute(tenders_query, params)
    tenders = [
        {
            "tender_id": row.tender_id,
            "title": row.title,
            "procuring_entity": row.procuring_entity,
            "category": row.category,
            "cpv_code": row.cpv_code,
            "estimated_value_mkd": float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
            "status": row.status,
            "closing_date": row.closing_date.isoformat() if row.closing_date else None,
            "source_url": row.source_url
        }
        for row in tenders_result.fetchall()
    ]

    # Update last_triggered
    await db.execute(
        text("UPDATE alerts SET last_triggered = NOW() WHERE alert_id = :search_id"),
        {"search_id": search_id}
    )
    await db.commit()

    return {
        "search_id": search_id,
        "filters": filters,
        "total": total,
        "page": page,
        "page_size": page_size,
        "tenders": tenders
    }
