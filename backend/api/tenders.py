"""
Tender API endpoints
CRUD operations for tenders
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, List
from datetime import date
from decimal import Decimal

from database import get_db
from models import Tender, TenderBidder, TenderLot, Supplier
from schemas import (
    TenderCreate,
    TenderUpdate,
    TenderResponse,
    TenderListResponse,
    TenderSearchRequest,
    MessageResponse
)

router = APIRouter(prefix="/tenders", tags=["tenders"])


# ============================================================================
# TENDER STATISTICS (Must be defined BEFORE path parameter routes)
# ============================================================================

@router.get("/stats/overview")
async def get_tender_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get tender statistics overview

    Returns counts, totals, and breakdowns.

    Note: A tender is considered:
    - "open": status='open' AND closing_date >= today (verified open)
    - "closing_soon": status='open' AND closing_date is within 7 days
    - "closed": status='closed' OR (status='open' AND closing_date < today)
    - "unknown": status='open' but closing_date is NULL (can't verify)
    """
    from datetime import date as date_type, timedelta

    today = date_type.today()
    week_from_now = today + timedelta(days=7)

    # Total tenders
    total_query = select(func.count()).select_from(Tender)
    total_tenders = await db.scalar(total_query)

    # VERIFIED OPEN tenders (have closing_date >= today)
    open_query = select(func.count()).select_from(Tender).where(
        and_(
            Tender.status == "open",
            Tender.closing_date.isnot(None),
            Tender.closing_date >= today
        )
    )
    open_tenders = await db.scalar(open_query)

    # CLOSING SOON (within 7 days)
    closing_soon_query = select(func.count()).select_from(Tender).where(
        and_(
            Tender.status == "open",
            Tender.closing_date.isnot(None),
            Tender.closing_date >= today,
            Tender.closing_date <= week_from_now
        )
    )
    closing_soon_tenders = await db.scalar(closing_soon_query)

    # Effectively CLOSED tenders:
    # - status is 'closed', OR
    # - status is 'open' but closing_date < today
    closed_query = select(func.count()).select_from(Tender).where(
        or_(
            Tender.status == "closed",
            and_(
                Tender.status == "open",
                Tender.closing_date.isnot(None),
                Tender.closing_date < today
            )
        )
    )
    closed_tenders = await db.scalar(closed_query)

    # Awarded tenders
    awarded_query = select(func.count()).select_from(Tender).where(Tender.status == "awarded")
    awarded_tenders = await db.scalar(awarded_query)

    # UNKNOWN status (open but no closing_date - can't verify)
    unknown_query = select(func.count()).select_from(Tender).where(
        and_(
            Tender.status == "open",
            Tender.closing_date.is_(None)
        )
    )
    unknown_tenders = await db.scalar(unknown_query)

    # Total value
    value_query = select(func.sum(Tender.estimated_value_mkd)).select_from(Tender)
    total_value = await db.scalar(value_query) or 0

    # Average value
    avg_query = select(func.avg(Tender.estimated_value_mkd)).select_from(Tender)
    avg_value = await db.scalar(avg_query) or 0

    # Tenders by category (top 10)
    category_query = select(
        Tender.category,
        func.count().label('count')
    ).where(
        Tender.category.isnot(None)
    ).group_by(
        Tender.category
    ).order_by(
        func.count().desc()
    ).limit(10)

    result = await db.execute(category_query)
    categories = {row[0]: row[1] for row in result}

    # Tenders by source_category
    source_category_query = select(
        Tender.source_category,
        func.count().label('count')
    ).group_by(
        Tender.source_category
    ).order_by(
        func.count().desc()
    )

    result = await db.execute(source_category_query)
    source_categories = {row[0] or 'unknown': row[1] for row in result}

    return {
        "total_tenders": total_tenders,
        "open_tenders": open_tenders,  # Verified open (have closing_date >= today)
        "closing_soon_tenders": closing_soon_tenders,  # Closing within 7 days
        "closed_tenders": closed_tenders,
        "awarded_tenders": awarded_tenders,
        "unknown_status_tenders": unknown_tenders,  # No closing_date, can't verify
        "total_value_mkd": float(total_value),
        "avg_value_mkd": float(avg_value),
        "tenders_by_category": categories,
        "tenders_by_source_category": source_categories,
        "current_date": today.isoformat()  # For UI reference
    }


@router.get("/stats/recent")
async def get_recent_tenders(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get most recently added tenders

    Parameters:
    - limit: Number of tenders to return
    """
    query = select(Tender).order_by(
        Tender.created_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    tenders = result.scalars().all()

    return {
        "count": len(tenders),
        "tenders": [TenderResponse.from_orm(t) for t in tenders]
    }


@router.get("/compare")
async def compare_tenders(
    ids: str = Query(..., description="Comma-separated tender IDs"),
    db: AsyncSession = Depends(get_db)
):
    """
    Compare multiple tenders side-by-side

    Parameters:
    - ids: Comma-separated list of tender IDs (e.g., "12345/2025,67890/2024")

    Returns:
    - List of tenders with key comparison fields
    """
    # Parse tender IDs from comma-separated string
    tender_ids = [id.strip() for id in ids.split(",")]

    if not tender_ids:
        raise HTTPException(status_code=400, detail="No tender IDs provided")

    if len(tender_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 tenders can be compared at once")

    # Query all tenders
    query = select(Tender).where(Tender.tender_id.in_(tender_ids))
    result = await db.execute(query)
    tenders = result.scalars().all()

    if not tenders:
        raise HTTPException(status_code=404, detail="No tenders found with provided IDs")

    # Return comparison data
    return {
        "total": len(tenders),
        "requested": len(tender_ids),
        "tenders": [
            {
                "tender_id": t.tender_id,
                "title": t.title,
                "procuring_entity": t.procuring_entity,
                "category": t.category,
                "cpv_code": t.cpv_code,
                "status": t.status,
                "estimated_value_mkd": float(t.estimated_value_mkd) if t.estimated_value_mkd else None,
                "estimated_value_eur": float(t.estimated_value_eur) if t.estimated_value_eur else None,
                "actual_value_mkd": float(t.actual_value_mkd) if t.actual_value_mkd else None,
                "actual_value_eur": float(t.actual_value_eur) if t.actual_value_eur else None,
                "opening_date": t.opening_date.isoformat() if t.opening_date else None,
                "closing_date": t.closing_date.isoformat() if t.closing_date else None,
                "publication_date": t.publication_date.isoformat() if t.publication_date else None,
                "procedure_type": t.procedure_type,
                "winner": t.winner,
                "num_bidders": t.num_bidders,
                "has_lots": t.has_lots,
                "source_url": t.source_url,
                "source_category": t.source_category
            }
            for t in tenders
        ]
    }


@router.get("/price_history")
async def get_price_history(
    cpv_code: str = Query(None, description="Filter by CPV code prefix"),
    category: str = Query(None, description="Filter by tender category"),
    entity: str = Query(None, description="Filter by procuring entity name"),
    period: str = Query("1y", regex="^(30d|90d|1y|all)$", description="Time period: 30d, 90d, 1y, or all"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get price history and trends over time

    Parameters:
    - cpv_code: Filter by CPV code prefix (e.g., "45000000" for construction works)
    - category: Filter by tender category
    - entity: Filter by procuring entity (partial match)
    - period: Time period (30d, 90d, 1y, all)

    Returns:
    - Time series data grouped by month showing average estimated and awarded values
    - Useful for charting price trends
    """
    from datetime import datetime, timedelta
    from sqlalchemy import extract, case

    # Calculate date filter based on period
    filters = []
    if period != "all":
        days_map = {"30d": 30, "90d": 90, "1y": 365}
        cutoff_date = datetime.utcnow().date() - timedelta(days=days_map[period])
        filters.append(Tender.opening_date >= cutoff_date)

    # Add other filters
    if cpv_code:
        filters.append(Tender.cpv_code.startswith(cpv_code))
    if category:
        filters.append(Tender.category == category)
    if entity:
        filters.append(Tender.procuring_entity.ilike(f"%{entity}%"))

    # Build query to group by year-month
    query = select(
        extract('year', Tender.opening_date).label('year'),
        extract('month', Tender.opening_date).label('month'),
        func.count().label('tender_count'),
        func.avg(Tender.estimated_value_mkd).label('avg_estimated_mkd'),
        func.avg(Tender.estimated_value_eur).label('avg_estimated_eur'),
        func.avg(Tender.actual_value_mkd).label('avg_awarded_mkd'),
        func.avg(Tender.actual_value_eur).label('avg_awarded_eur'),
        func.sum(Tender.estimated_value_mkd).label('total_estimated_mkd'),
        func.sum(Tender.actual_value_mkd).label('total_awarded_mkd')
    ).where(
        and_(
            Tender.opening_date.isnot(None),
            *filters
        )
    ).group_by(
        extract('year', Tender.opening_date),
        extract('month', Tender.opening_date)
    ).order_by(
        extract('year', Tender.opening_date).asc(),
        extract('month', Tender.opening_date).asc()
    )

    result = await db.execute(query)
    rows = result.fetchall()

    # Format data for charting
    time_series = [
        {
            "period": f"{int(row.year)}-{int(row.month):02d}",
            "year": int(row.year),
            "month": int(row.month),
            "tender_count": row.tender_count,
            "avg_estimated_mkd": float(row.avg_estimated_mkd) if row.avg_estimated_mkd else None,
            "avg_estimated_eur": float(row.avg_estimated_eur) if row.avg_estimated_eur else None,
            "avg_awarded_mkd": float(row.avg_awarded_mkd) if row.avg_awarded_mkd else None,
            "avg_awarded_eur": float(row.avg_awarded_eur) if row.avg_awarded_eur else None,
            "total_estimated_mkd": float(row.total_estimated_mkd) if row.total_estimated_mkd else None,
            "total_awarded_mkd": float(row.total_awarded_mkd) if row.total_awarded_mkd else None
        }
        for row in rows
    ]

    return {
        "period": period,
        "filters": {
            "cpv_code": cpv_code,
            "category": category,
            "entity": entity
        },
        "data_points": len(time_series),
        "time_series": time_series
    }


# ============================================================================
# GET TENDERS
# ============================================================================

@router.get("", response_model=TenderListResponse)
async def list_tenders(
    page: int = Query(1, ge=1, description="Page number (1-indexed, must be >= 1)"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page (1-200)"),
    category: Optional[str] = None,
    status: Optional[str] = None,
    source_category: Optional[str] = Query(None, description="Filter by source category (active, awarded, cancelled, etc.)"),
    procuring_entity: Optional[str] = None,
    cpv_code: Optional[str] = None,
    min_estimated_mkd: Optional[Decimal] = Query(None, description="Minimum estimated value in MKD"),
    max_estimated_mkd: Optional[Decimal] = Query(None, description="Maximum estimated value in MKD"),
    min_estimated_eur: Optional[Decimal] = Query(None, description="Minimum estimated value in EUR"),
    max_estimated_eur: Optional[Decimal] = Query(None, description="Maximum estimated value in EUR"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="asc or desc"),
    db: AsyncSession = Depends(get_db)
):
    """
    List tenders with pagination and filtering

    Parameters:
    - page: Page number (1-indexed)
    - page_size: Items per page
    - category: Filter by category
    - status: Filter by status (open, closed, awarded)
    - source_category: Filter by source category (active, awarded, cancelled, historical)
    - procuring_entity: Filter by procuring entity
    - cpv_code: Filter by CPV code
    - min_estimated_mkd: Minimum estimated value in MKD
    - max_estimated_mkd: Maximum estimated value in MKD
    - min_estimated_eur: Minimum estimated value in EUR
    - max_estimated_eur: Maximum estimated value in EUR
    - sort_by: Field to sort by
    - sort_order: Sort order (asc or desc)
    """
    # Build query
    query = select(Tender)

    # Apply filters
    filters = []
    if category:
        filters.append(Tender.category == category)
    if status:
        filters.append(Tender.status == status)
    if source_category:
        filters.append(Tender.source_category == source_category)
    if procuring_entity:
        filters.append(Tender.procuring_entity.ilike(f"%{procuring_entity}%"))
    if cpv_code:
        filters.append(Tender.cpv_code.startswith(cpv_code))
    # Estimated value filters (MKD)
    if min_estimated_mkd is not None:
        filters.append(Tender.estimated_value_mkd >= min_estimated_mkd)
    if max_estimated_mkd is not None:
        filters.append(Tender.estimated_value_mkd <= max_estimated_mkd)
    # Estimated value filters (EUR)
    if min_estimated_eur is not None:
        filters.append(Tender.estimated_value_eur >= min_estimated_eur)
    if max_estimated_eur is not None:
        filters.append(Tender.estimated_value_eur <= max_estimated_eur)

    if filters:
        query = query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(Tender)
    if filters:
        count_query = count_query.where(and_(*filters))
    total = await db.scalar(count_query)

    # Sort
    sort_column = getattr(Tender, sort_by, Tender.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    tenders = result.scalars().all()

    return TenderListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[TenderResponse.from_orm(t) for t in tenders]
    )


@router.post("/search", response_model=TenderListResponse)
async def search_tenders(
    search: TenderSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Advanced tender search with multiple filters

    Request body contains search criteria
    """
    # Build query
    query = select(Tender)
    filters = []

    # Text search (search in title and description)
    if search.query:
        text_filter = or_(
            Tender.title.ilike(f"%{search.query}%"),
            Tender.description.ilike(f"%{search.query}%"),
            Tender.procuring_entity.ilike(f"%{search.query}%")
        )
        filters.append(text_filter)

    # Exact filters
    if search.category:
        filters.append(Tender.category == search.category)
    if search.status:
        filters.append(Tender.status == search.status)
    if search.procuring_entity:
        filters.append(Tender.procuring_entity.ilike(f"%{search.procuring_entity}%"))
    if search.cpv_code:
        filters.append(Tender.cpv_code.startswith(search.cpv_code))

    # Value range filters (MKD)
    if search.min_value_mkd:
        filters.append(Tender.estimated_value_mkd >= search.min_value_mkd)
    if search.max_value_mkd:
        filters.append(Tender.estimated_value_mkd <= search.max_value_mkd)
    # Value range filters (EUR)
    if search.min_value_eur:
        filters.append(Tender.estimated_value_eur >= search.min_value_eur)
    if search.max_value_eur:
        filters.append(Tender.estimated_value_eur <= search.max_value_eur)

    # Date range filters
    if search.opening_date_from:
        filters.append(Tender.opening_date >= search.opening_date_from)
    if search.opening_date_to:
        filters.append(Tender.opening_date <= search.opening_date_to)
    if search.closing_date_from:
        filters.append(Tender.closing_date >= search.closing_date_from)
    if search.closing_date_to:
        filters.append(Tender.closing_date <= search.closing_date_to)

    # NEW FILTER FIELDS - Added 2025-11-24
    if search.procedure_type:
        filters.append(Tender.procedure_type == search.procedure_type)
    if search.contracting_entity_category:
        filters.append(Tender.contracting_entity_category == search.contracting_entity_category)
    if search.contract_signing_date_from:
        filters.append(Tender.contract_signing_date >= search.contract_signing_date_from)
    if search.contract_signing_date_to:
        filters.append(Tender.contract_signing_date <= search.contract_signing_date_to)
    # Source category filter
    if hasattr(search, 'source_category') and search.source_category:
        filters.append(Tender.source_category == search.source_category)

    # Apply filters
    if filters:
        query = query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(Tender)
    if filters:
        count_query = count_query.where(and_(*filters))
    total = await db.scalar(count_query)

    # Sort
    sort_column = getattr(Tender, search.sort_by, Tender.created_at)
    if search.sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Paginate
    offset = (search.page - 1) * search.page_size
    query = query.offset(offset).limit(search.page_size)

    # Execute
    result = await db.execute(query)
    tenders = result.scalars().all()

    return TenderListResponse(
        total=total,
        page=search.page,
        page_size=search.page_size,
        items=[TenderResponse.from_orm(t) for t in tenders]
    )


# ============================================================================
# METADATA ENDPOINTS (categories, CPV codes)
# ============================================================================

@router.get("/categories")
async def get_tender_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all unique tender categories with counts

    Returns list of categories sorted by count (most common first)
    """
    query = select(
        Tender.category,
        func.count().label('count')
    ).where(
        Tender.category.isnot(None),
        Tender.category != ''
    ).group_by(
        Tender.category
    ).order_by(
        func.count().desc()
    )

    result = await db.execute(query)
    categories = [
        {"category": row[0], "count": row[1]}
        for row in result
    ]

    return {
        "total": len(categories),
        "categories": categories
    }


@router.get("/cpv-codes")
async def get_cpv_codes(
    prefix: str = Query(None, description="Filter by CPV code prefix (e.g., '45' for construction)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of CPV codes to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all unique CPV codes with counts and tender statistics

    Parameters:
    - prefix: Filter by CPV code prefix (e.g., "45" for construction works)
    - limit: Maximum number of codes to return

    Returns list of CPV codes sorted by frequency
    """
    filters = [
        Tender.cpv_code.isnot(None),
        Tender.cpv_code != ''
    ]

    if prefix:
        filters.append(Tender.cpv_code.startswith(prefix))

    query = select(
        Tender.cpv_code,
        func.count().label('tender_count'),
        func.sum(Tender.estimated_value_mkd).label('total_value_mkd'),
        func.avg(Tender.estimated_value_mkd).label('avg_value_mkd')
    ).where(
        and_(*filters)
    ).group_by(
        Tender.cpv_code
    ).order_by(
        func.count().desc()
    ).limit(limit)

    result = await db.execute(query)
    cpv_codes = [
        {
            "cpv_code": row[0],
            "tender_count": row[1],
            "total_value_mkd": float(row[2]) if row[2] else None,
            "avg_value_mkd": float(row[3]) if row[3] else None
        }
        for row in result
    ]

    return {
        "total": len(cpv_codes),
        "prefix_filter": prefix,
        "cpv_codes": cpv_codes
    }


# ============================================================================
# TENDER PRICE HISTORY (Per-Tender)
# ============================================================================

@router.get("/{number}/{year}/price_history")
async def get_tender_price_history(
    number: str,
    year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get price/value history for a specific tender.

    Returns chronological list of value changes from amendments,
    initial value, and final awarded value.

    Tender ID format: {number}/{year} e.g. 19816/2025
    """
    from sqlalchemy import text

    tender_id = f"{number}/{year}"

    # First get tender basic info
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get amendments related to value changes
    amendments_query = text("""
        SELECT
            amendment_date as date,
            amendment_type as type,
            field_changed,
            old_value,
            new_value,
            reason
        FROM tender_amendments
        WHERE tender_id = :tender_id
          AND (field_changed ILIKE '%value%' OR field_changed ILIKE '%price%' OR field_changed ILIKE '%вредност%')
        ORDER BY amendment_date ASC
    """)

    amendments_result = await db.execute(amendments_query, {"tender_id": tender_id})
    amendments = amendments_result.fetchall()

    # Build price history timeline
    history = []

    # Add initial value entry
    if tender.estimated_value_mkd:
        history.append({
            "date": tender.publication_date.isoformat() if tender.publication_date else tender.opening_date.isoformat() if tender.opening_date else None,
            "type": "initial",
            "value_mkd": float(tender.estimated_value_mkd),
            "value_eur": float(tender.estimated_value_eur) if tender.estimated_value_eur else None,
            "change_percent": 0.0,
            "reason": "Почетна проценета вредност"
        })

    # Add amendments
    previous_value = float(tender.estimated_value_mkd) if tender.estimated_value_mkd else 0
    for amend in amendments:
        try:
            new_val = float(amend.new_value) if amend.new_value else None
            old_val = float(amend.old_value) if amend.old_value else previous_value

            change_pct = 0.0
            if old_val and new_val:
                change_pct = ((new_val - old_val) / old_val) * 100

            history.append({
                "date": amend.date.isoformat() if amend.date else None,
                "type": "amendment",
                "value_mkd": new_val,
                "value_eur": None,
                "change_percent": round(change_pct, 2),
                "reason": amend.reason or f"Измена: {amend.field_changed}"
            })

            if new_val:
                previous_value = new_val
        except (ValueError, TypeError):
            continue

    # Add award value if different from estimated
    if tender.actual_value_mkd and tender.status in ['awarded', 'closed']:
        change_pct = 0.0
        if tender.estimated_value_mkd:
            change_pct = ((float(tender.actual_value_mkd) - float(tender.estimated_value_mkd)) / float(tender.estimated_value_mkd)) * 100

        history.append({
            "date": tender.contract_signing_date.isoformat() if tender.contract_signing_date else None,
            "type": "award",
            "value_mkd": float(tender.actual_value_mkd),
            "value_eur": float(tender.actual_value_eur) if tender.actual_value_eur else None,
            "change_percent": round(change_pct, 2),
            "reason": f"Доделена вредност на {tender.winner}" if tender.winner else "Доделена вредност"
        })

    # Calculate total value change
    total_change_pct = 0.0
    if history and len(history) > 1:
        initial = history[0].get("value_mkd", 0)
        final = history[-1].get("value_mkd", 0)
        if initial and final:
            total_change_pct = ((final - initial) / initial) * 100

    return {
        "tender_id": tender_id,
        "title": tender.title,
        "current_value_mkd": float(tender.actual_value_mkd or tender.estimated_value_mkd) if (tender.actual_value_mkd or tender.estimated_value_mkd) else None,
        "initial_value_mkd": float(tender.estimated_value_mkd) if tender.estimated_value_mkd else None,
        "history": history,
        "total_amendments": tender.amendment_count or len(amendments),
        "value_change_percent": round(total_change_pct, 2)
    }


# ============================================================================
# TENDER AI SUMMARY
# ============================================================================

@router.get("/{number}/{year}/ai_summary")
async def get_tender_ai_summary(
    number: str,
    year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-generated summary for a specific tender.

    Returns structured summary including:
    - Overview text
    - Key requirements
    - Complexity assessment
    - Competition level
    - Deadline urgency

    Note: Full AI summary requires Starter+ tier. Free tier gets basic summary.

    Tender ID format: {number}/{year} e.g. 19816/2025
    """
    from datetime import datetime, timedelta

    tender_id = f"{number}/{year}"

    # Get tender
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Calculate deadline urgency
    urgency = "unknown"
    days_remaining = None
    if tender.closing_date:
        today = datetime.utcnow().date()
        days_remaining = (tender.closing_date - today).days
        if days_remaining < 0:
            urgency = "closed"
        elif days_remaining <= 3:
            urgency = "critical"
        elif days_remaining <= 7:
            urgency = "urgent"
        elif days_remaining <= 14:
            urgency = "soon"
        else:
            urgency = "normal"

    # Estimate complexity based on available data
    complexity = "medium"
    complexity_factors = []

    if tender.has_lots and tender.num_lots and tender.num_lots > 3:
        complexity = "high"
        complexity_factors.append(f"{tender.num_lots} лотови")
    if tender.estimated_value_mkd and tender.estimated_value_mkd > 10000000:
        complexity = "high"
        complexity_factors.append("Висока вредност")
    if tender.num_bidders and tender.num_bidders > 5:
        complexity_factors.append(f"{tender.num_bidders} понудувачи")

    # Estimate competition level
    competition = "unknown"
    if tender.num_bidders:
        if tender.num_bidders >= 5:
            competition = "high"
        elif tender.num_bidders >= 3:
            competition = "medium"
        else:
            competition = "low"

    # Extract key requirements from description (basic extraction)
    key_requirements = []
    if tender.description:
        desc_lower = tender.description.lower()
        if "гаранција" in desc_lower or "депозит" in desc_lower:
            key_requirements.append("Потребна гаранција/депозит")
        if "сертификат" in desc_lower or "iso" in desc_lower:
            key_requirements.append("Потребни сертификати")
        if "искуство" in desc_lower or "референц" in desc_lower:
            key_requirements.append("Потребно претходно искуство")
        if "рок" in desc_lower or "испорака" in desc_lower:
            key_requirements.append("Специфични рокови за испорака")

    # Build basic overview
    overview_parts = []
    if tender.procuring_entity:
        overview_parts.append(f"Набавка од {tender.procuring_entity}.")
    if tender.category:
        overview_parts.append(f"Категорија: {tender.category}.")
    if tender.estimated_value_mkd:
        overview_parts.append(f"Проценета вредност: {tender.estimated_value_mkd:,.0f} МКД.")
    if tender.procedure_type:
        overview_parts.append(f"Процедура: {tender.procedure_type}.")

    overview = " ".join(overview_parts) if overview_parts else "Нема доволно информации за резиме."

    # Suggested CPV codes
    suggested_cpv = []
    if tender.cpv_code:
        suggested_cpv.append(tender.cpv_code)
        if len(tender.cpv_code) >= 2:
            suggested_cpv.append(tender.cpv_code[:2] + "000000")

    return {
        "tender_id": tender_id,
        "title": tender.title,
        "summary": {
            "overview": overview,
            "key_requirements": key_requirements if key_requirements else ["Нема извлечени барања"],
            "estimated_complexity": complexity,
            "complexity_factors": complexity_factors,
            "suggested_cpv_codes": suggested_cpv,
            "deadline_urgency": urgency,
            "days_remaining": days_remaining,
            "competition_level": competition
        },
        "generated_at": datetime.utcnow().isoformat(),
        "model": "rule-based-v1",
        "note": "За детална AI анализа потребна е Starter+ претплата"
    }


# ============================================================================
# TENDER DOCUMENTS (Must be before the path parameter route)
# ============================================================================
# Routes use /{number}/{year}/... pattern to handle tender IDs with slashes like "19816/2025"

@router.get("/{number}/{year}/documents")
async def get_tender_documents(
    number: str,
    year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all documents for a specific tender.

    Returns list of documents including file names, URLs, and extraction status.
    Tender ID format: {number}/{year} e.g. 19816/2025
    """
    from models import Document
    from schemas import DocumentResponse

    # Construct tender_id from path components
    tender_id = f"{number}/{year}"

    # First verify tender exists
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get documents
    doc_query = select(Document).where(Document.tender_id == tender_id).order_by(Document.uploaded_at.desc())
    result = await db.execute(doc_query)
    documents = result.scalars().all()

    return {
        "tender_id": tender_id,
        "total": len(documents),
        "documents": [DocumentResponse.from_orm(doc) for doc in documents]
    }


@router.get("/{number}/{year}/bidders")
async def get_tender_bidders(
    number: str,
    year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all bidders/participants for a specific tender.

    Returns list of bidders with their bid amounts, winner status, and ranking.
    Tender ID format: {number}/{year} e.g. 19816/2025
    """
    # Construct tender_id from path components
    tender_id = f"{number}/{year}"

    # First verify tender exists
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Query tender_bidders table
    query = select(TenderBidder).where(TenderBidder.tender_id == tender_id).order_by(
        TenderBidder.rank.asc().nulls_last(),
        TenderBidder.is_winner.desc()
    )
    result = await db.execute(query)
    bidders = result.scalars().all()

    return {
        "tender_id": tender_id,
        "total": len(bidders),
        "bidders": [
            {
                "bidder_id": str(b.bidder_id),
                "company_name": b.company_name,
                "tax_id": b.company_tax_id,
                "bid_amount_mkd": float(b.bid_amount_mkd) if b.bid_amount_mkd else None,
                "bid_amount_eur": float(b.bid_amount_eur) if b.bid_amount_eur else None,
                "rank": b.rank,
                "is_winner": b.is_winner,
                "disqualified": b.disqualified,
                "disqualification_reason": b.disqualification_reason
            }
            for b in bidders
        ]
    }


@router.get("/{number}/{year}/lots")
async def get_tender_lots(
    number: str,
    year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all lots for a specific tender.

    Returns list of lots with their values, CPV codes, and winner information.
    Tender ID format: {number}/{year} e.g. 19816/2025
    """
    # Construct tender_id from path components
    tender_id = f"{number}/{year}"

    # First verify tender exists
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Query tender_lots table
    query = select(TenderLot).where(TenderLot.tender_id == tender_id).order_by(
        TenderLot.lot_number.asc()
    )
    result = await db.execute(query)
    lots = result.scalars().all()

    return {
        "tender_id": tender_id,
        "has_lots": tender.has_lots or False,
        "total": len(lots),
        "lots": [
            {
                "lot_id": str(l.lot_id),
                "lot_number": l.lot_number,
                "lot_title": l.lot_title,
                "lot_description": l.lot_description,
                "estimated_value_mkd": float(l.estimated_value_mkd) if l.estimated_value_mkd else None,
                "estimated_value_eur": float(l.estimated_value_eur) if l.estimated_value_eur else None,
                "actual_value_mkd": float(l.actual_value_mkd) if l.actual_value_mkd else None,
                "actual_value_eur": float(l.actual_value_eur) if l.actual_value_eur else None,
                "cpv_code": l.cpv_code,
                "winner": l.winner,
                "quantity": l.quantity,
                "unit": l.unit
            }
            for l in lots
        ]
    }


@router.get("/by-id/{tender_id:path}/raw-json")
async def get_tender_raw_json(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get raw scraped JSON data for a specific tender.

    Returns the raw_data_json field containing all original scraped data.
    Useful for debugging, data recovery, and accessing fields not in the schema.
    Tender ID format: Any format (e.g., 01069/2025/K1, UUID, etc.)
    """
    from sqlalchemy import text

    # Normalize encoded slashes
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")

    # Query tender with raw_data_json
    query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get raw_data_json
    raw_json = tender.raw_data_json

    if not raw_json:
        return {
            "tender_id": tender.tender_id,
            "has_raw_data": False,
            "raw_data": None,
            "message": "No raw data available. Tender may have been scraped before raw_data_json was implemented."
        }

    # Parse JSON if it's a string
    import json
    if isinstance(raw_json, str):
        try:
            raw_json = json.loads(raw_json)
        except json.JSONDecodeError:
            pass

    return {
        "tender_id": tender.tender_id,
        "has_raw_data": True,
        "raw_data": raw_json,
        "title": tender.title,
        "status": tender.status
    }


@router.get("/{number}/{year}/suppliers")
async def get_tender_suppliers(number: str, year: str, db: AsyncSession = Depends(get_db)):
    """Get suppliers/winners associated with a tender. Tender ID format: {number}/{year}"""
    tender_id = f"{number}/{year}"

    # Get the tender to find winner
    tender = await db.execute(
        select(Tender).where(Tender.tender_id == tender_id)
    )
    tender = tender.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    suppliers = []

    # If tender has a winner, look up in suppliers table
    if tender.winner:
        supplier_query = await db.execute(
            select(Supplier).where(
                or_(
                    Supplier.company_name.ilike(f"%{tender.winner}%"),
                    Supplier.company_name == tender.winner
                )
            )
        )
        supplier = supplier_query.scalar_one_or_none()

        if supplier:
            suppliers.append({
                "supplier_id": str(supplier.supplier_id),
                "company_name": supplier.company_name,
                "tax_id": supplier.tax_id,
                "city": supplier.city,
                "total_wins": supplier.total_wins,
                "total_bids": supplier.total_bids,
                "win_rate": float(supplier.win_rate) if supplier.win_rate else None,
                "total_contract_value_mkd": float(supplier.total_contract_value_mkd) if supplier.total_contract_value_mkd else None,
                "is_winner": True
            })

    # Also get bidders who are in suppliers table
    bidders_query = await db.execute(
        select(TenderBidder).where(TenderBidder.tender_id == tender_id)
    )
    bidders = bidders_query.scalars().all()

    for bidder in bidders:
        if bidder.company_name and bidder.company_name != tender.winner:
            supplier_query = await db.execute(
                select(Supplier).where(
                    Supplier.company_name.ilike(f"%{bidder.company_name}%")
                )
            )
            supplier = supplier_query.scalar_one_or_none()
            if supplier and not any(s["company_name"] == supplier.company_name for s in suppliers):
                suppliers.append({
                    "supplier_id": str(supplier.supplier_id),
                    "company_name": supplier.company_name,
                    "tax_id": supplier.tax_id,
                    "city": supplier.city,
                    "total_wins": supplier.total_wins,
                    "total_bids": supplier.total_bids,
                    "win_rate": float(supplier.win_rate) if supplier.win_rate else None,
                    "total_contract_value_mkd": float(supplier.total_contract_value_mkd) if supplier.total_contract_value_mkd else None,
                    "is_winner": False
                })

    return {
        "tender_id": tender_id,
        "winner": tender.winner,
        "awarded_value_mkd": float(tender.actual_value_mkd) if tender.actual_value_mkd else None,
        "total": len(suppliers),
        "suppliers": suppliers
    }


# ============================================================================
# GET SINGLE TENDER (Path parameter - must be LAST among GET routes)
# ============================================================================

@router.get("/{tender_id:path}", response_model=TenderResponse)
async def get_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get tender by ID. Supports IDs containing slashes (encoded in the path).
    """
    # Normalize encoded slash IDs
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")
    query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    return TenderResponse.from_orm(tender)


# ============================================================================
# CREATE/UPDATE/DELETE TENDERS
# ============================================================================

@router.post("", response_model=TenderResponse, status_code=201)
async def create_tender(
    tender: TenderCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create new tender

    Request body contains tender data
    """
    # Check if tender already exists
    query = select(Tender).where(Tender.tender_id == tender.tender_id)
    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Tender with ID {tender.tender_id} already exists"
        )

    # Create tender
    db_tender = Tender(**tender.dict())
    db.add(db_tender)
    await db.commit()
    await db.refresh(db_tender)

    return TenderResponse.from_orm(db_tender)


@router.put("/{tender_id}", response_model=TenderResponse)
async def update_tender(
    tender_id: str,
    tender_update: TenderUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update tender

    Parameters:
    - tender_id: Tender ID

    Request body contains fields to update
    """
    # Get tender
    query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(query)
    db_tender = result.scalar_one_or_none()

    if not db_tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Update fields
    update_data = tender_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_tender, field, value)

    await db.commit()
    await db.refresh(db_tender)

    return TenderResponse.from_orm(db_tender)


@router.delete("/{tender_id}", response_model=MessageResponse)
async def delete_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete tender

    Parameters:
    - tender_id: Tender ID
    """
    # Get tender
    query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(query)
    db_tender = result.scalar_one_or_none()

    if not db_tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Delete
    await db.delete(db_tender)
    await db.commit()

    return MessageResponse(
        message="Tender deleted successfully",
        detail=f"Tender {tender_id} has been removed"
    )
