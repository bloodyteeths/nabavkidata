"""
Tender API endpoints
CRUD operations for tenders
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from typing import Optional, List
from datetime import date
from decimal import Decimal
import os
import json
import re

from database import get_db
from models import Tender, TenderBidder, TenderLot, Supplier, Document, User, ProductItem
from api.auth import get_current_user
from utils.timezone import get_ai_date_context
from schemas import (
    TenderCreate,
    TenderUpdate,
    TenderResponse,
    TenderListResponse,
    TenderSearchRequest,
    MessageResponse,
    TenderChatRequest,
    TenderChatResponse,
    TenderChatSource
)

# Import Gemini for AI summaries
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = bool(os.getenv('GEMINI_API_KEY'))
    if GEMINI_AVAILABLE:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
except ImportError:
    GEMINI_AVAILABLE = False

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
    search: Optional[str] = Query(None, description="Search in title, description"),
    category: Optional[str] = None,
    status: Optional[str] = None,
    source_category: Optional[str] = Query(None, description="Filter by source category (active, awarded, cancelled, etc.)"),
    procuring_entity: Optional[str] = None,
    cpv_code: Optional[str] = None,
    procedure_type: Optional[str] = Query(None, description="Filter by procedure type"),
    min_estimated_mkd: Optional[Decimal] = Query(None, description="Minimum estimated value in MKD"),
    max_estimated_mkd: Optional[Decimal] = Query(None, description="Maximum estimated value in MKD"),
    min_estimated_eur: Optional[Decimal] = Query(None, description="Minimum estimated value in EUR"),
    max_estimated_eur: Optional[Decimal] = Query(None, description="Maximum estimated value in EUR"),
    opening_date_from: Optional[date] = Query(None, description="Filter by opening date from"),
    opening_date_to: Optional[date] = Query(None, description="Filter by opening date to"),
    closing_date_from: Optional[date] = Query(None, description="Filter by closing date from"),
    closing_date_to: Optional[date] = Query(None, description="Filter by closing date to"),
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

    # Text search in title and description
    if search:
        text_filter = or_(
            Tender.title.ilike(f"%{search}%"),
            Tender.description.ilike(f"%{search}%"),
            Tender.procuring_entity.ilike(f"%{search}%")
        )
        filters.append(text_filter)

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
    if procedure_type:
        filters.append(Tender.procedure_type == procedure_type)

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

    # Date range filters
    if opening_date_from:
        filters.append(Tender.opening_date >= opening_date_from)
    if opening_date_to:
        filters.append(Tender.opening_date <= opening_date_to)
    if closing_date_from:
        filters.append(Tender.closing_date >= closing_date_from)
    if closing_date_to:
        filters.append(Tender.closing_date <= closing_date_to)

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
# EXPORT ENDPOINTS (Starter+ tiers only)
# ============================================================================

@router.post("/export")
async def export_tenders(
    search: TenderSearchRequest,
    format: str = Query("csv", regex="^(csv|json)$", description="Export format: csv or json"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export tender search results to CSV or JSON format.

    Requires Starter tier or higher.
    Maximum 1000 results per export.

    Args:
        search: Same search criteria as /search endpoint
        format: Export format (csv or json)

    Returns:
        CSV or JSON file as download
    """
    from fastapi.responses import StreamingResponse
    import csv
    import io

    # Check tier - must be starter or higher
    user_tier = getattr(current_user, 'subscription_tier', 'free').lower()
    if user_tier == 'free':
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Export feature requires Starter tier or higher",
                "upgrade_url": "/pricing"
            }
        )

    # Build query (same as search)
    query = select(Tender)
    filters = []

    if search.query:
        text_filter = or_(
            Tender.title.ilike(f"%{search.query}%"),
            Tender.description.ilike(f"%{search.query}%"),
            Tender.procuring_entity.ilike(f"%{search.query}%")
        )
        filters.append(text_filter)

    if search.category:
        filters.append(Tender.category == search.category)
    if search.status:
        filters.append(Tender.status == search.status)
    if search.procuring_entity:
        filters.append(Tender.procuring_entity.ilike(f"%{search.procuring_entity}%"))
    if search.cpv_code:
        filters.append(Tender.cpv_code.startswith(search.cpv_code))
    if search.min_value_mkd:
        filters.append(Tender.estimated_value_mkd >= search.min_value_mkd)
    if search.max_value_mkd:
        filters.append(Tender.estimated_value_mkd <= search.max_value_mkd)
    if search.min_value_eur:
        filters.append(Tender.estimated_value_eur >= search.min_value_eur)
    if search.max_value_eur:
        filters.append(Tender.estimated_value_eur <= search.max_value_eur)
    if search.opening_date_from:
        filters.append(Tender.opening_date >= search.opening_date_from)
    if search.opening_date_to:
        filters.append(Tender.opening_date <= search.opening_date_to)
    if search.closing_date_from:
        filters.append(Tender.closing_date >= search.closing_date_from)
    if search.closing_date_to:
        filters.append(Tender.closing_date <= search.closing_date_to)
    if search.procedure_type:
        filters.append(Tender.procedure_type == search.procedure_type)
    if hasattr(search, 'source_category') and search.source_category:
        filters.append(Tender.source_category == search.source_category)

    if filters:
        query = query.where(and_(*filters))

    # Sort and limit to 1000 results
    sort_column = getattr(Tender, search.sort_by, Tender.created_at)
    if search.sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    query = query.limit(1000)

    result = await db.execute(query)
    tenders = result.scalars().all()

    if format == "json":
        # JSON export
        export_data = []
        for t in tenders:
            export_data.append({
                "tender_id": t.tender_id,
                "title": t.title,
                "procuring_entity": t.procuring_entity,
                "category": t.category,
                "status": t.status,
                "cpv_code": t.cpv_code,
                "estimated_value_mkd": float(t.estimated_value_mkd) if t.estimated_value_mkd else None,
                "estimated_value_eur": float(t.estimated_value_eur) if t.estimated_value_eur else None,
                "opening_date": t.opening_date.isoformat() if t.opening_date else None,
                "closing_date": t.closing_date.isoformat() if t.closing_date else None,
                "source_url": t.source_url,
                "procedure_type": t.procedure_type,
            })

        return {
            "total": len(export_data),
            "format": "json",
            "data": export_data
        }

    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "Tender ID", "Title", "Procuring Entity", "Category", "Status",
            "CPV Code", "Estimated Value (MKD)", "Estimated Value (EUR)",
            "Opening Date", "Closing Date", "Procedure Type", "Source URL"
        ])

        # Data rows
        for t in tenders:
            writer.writerow([
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.category,
                t.status,
                t.cpv_code,
                float(t.estimated_value_mkd) if t.estimated_value_mkd else "",
                float(t.estimated_value_eur) if t.estimated_value_eur else "",
                t.opening_date.isoformat() if t.opening_date else "",
                t.closing_date.isoformat() if t.closing_date else "",
                t.procedure_type or "",
                t.source_url or ""
            ])

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=tenders_export_{date.today().isoformat()}.csv"
            }
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

@router.get("/{number}/{year:int}/price_history")
async def get_tender_price_history(
    number: str,
    year: int,
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

@router.get("/{number}/{year:int}/ai_summary")
async def get_tender_ai_summary(
    number: str,
    year: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-generated summary for a specific tender.

    Returns structured summary including:
    - Overview text (AI-generated)
    - Key requirements
    - Strategic insights
    - Complexity assessment
    - Competition level
    - Deadline urgency

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

    # Get documents for additional context
    doc_query = select(Document).where(Document.tender_id == tender_id)
    doc_result = await db.execute(doc_query)
    documents = doc_result.scalars().all()

    # Get document text excerpts for AI context
    doc_texts = []
    for doc in documents[:3]:  # Limit to first 3 docs
        if doc.content_text:
            doc_texts.append(doc.content_text[:3000])  # First 3000 chars each

    # Get bidders info
    bidder_query = select(TenderBidder).where(TenderBidder.tender_id == tender_id)
    bidder_result = await db.execute(bidder_query)
    bidders = bidder_result.scalars().all()

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

    # Build context for AI
    tender_context = f"""
Тендер ID: {tender_id}
Наслов: {tender.title or 'Н/А'}
Набавувач: {tender.procuring_entity or 'Н/А'}
Категорија: {tender.category or 'Н/А'}
CPV код: {tender.cpv_code or 'Н/А'}
Проценета вредност: {f'{tender.estimated_value_mkd:,.0f} МКД' if tender.estimated_value_mkd else 'Н/А'}
Тип процедура: {tender.procedure_type or 'Н/А'}
Статус: {tender.status or 'Н/А'}
Краен рок: {tender.closing_date.isoformat() if tender.closing_date else 'Н/А'}
Број на понудувачи: {tender.num_bidders or 0}
Број на лотови: {tender.num_lots or 1}

Опис:
{tender.description[:5000] if tender.description else 'Нема опис'}
"""

    # Add bidder info
    if bidders:
        bidder_info = "\n\nПонудувачи:\n"
        for b in bidders[:10]:
            winner_mark = " (ПОБЕДНИК)" if b.is_winner else ""
            bidder_info += f"- {b.company_name}{winner_mark}"
            if b.bid_amount_mkd:
                bidder_info += f" - {b.bid_amount_mkd:,.0f} МКД"
            bidder_info += "\n"
        tender_context += bidder_info

    # Add document excerpts
    if doc_texts:
        tender_context += "\n\nИзводи од документи:\n"
        for i, text in enumerate(doc_texts, 1):
            tender_context += f"\n--- Документ {i} ---\n{text}\n"

    # Generate AI summary
    overview = ""
    key_requirements = []
    strategic_insights = []
    model_used = "rule-based-v1"

    if GEMINI_AVAILABLE:
        try:
            # Use configured model or fallback
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
            model = genai.GenerativeModel(model_name)

            # Add date context
            date_context = get_ai_date_context()

            prompt = f"""{date_context}

Анализирај го овој јавен тендер и дај структурирано резиме на македонски јазик.

{tender_context}

Одговори во JSON формат со следната структура:
{{
  "overview": "2-3 реченици општ преглед на набавката - што се бара, од кого, зошто е важно",
  "key_requirements": ["барање 1", "барање 2", ...],
  "strategic_insights": ["совет 1", "совет 2", ...],
  "recommended_actions": ["акција 1", "акција 2", ...]
}}

За key_requirements - извлечи ги најважните технички, финансиски и правни барања.
За strategic_insights - дај корисни совети за компании кои сакаат да учествуваат.
За recommended_actions - конкретни чекори што треба да се превземат.

Биди концизен и практичен. Фокусирај се на информации корисни за понудувачи."""

            # Relaxed safety settings for business content
            response = model.generate_content(prompt)

            # Handle safety blocks
            response_text = None
            try:
                response_text = response.text
            except ValueError:
                pass

            # Parse JSON from response
            if response_text:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        overview = parsed.get('overview', '')
                        key_requirements = parsed.get('key_requirements', [])
                        strategic_insights = parsed.get('strategic_insights', [])
                        model_used = model_name
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            print(f"Gemini AI summary failed: {e}")
            # Fall through to rule-based

    # Fallback to rule-based if AI failed
    if not overview:
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

        # Basic keyword extraction for requirements
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
            "strategic_insights": strategic_insights if strategic_insights else [],
            "estimated_complexity": complexity,
            "complexity_factors": complexity_factors,
            "suggested_cpv_codes": suggested_cpv,
            "deadline_urgency": urgency,
            "days_remaining": days_remaining,
            "competition_level": competition
        },
        "generated_at": datetime.utcnow().isoformat(),
        "model": model_used
    }


# ============================================================================
# TENDER AI CHAT
# ============================================================================

@router.post("/{number}/{year:int}/chat", response_model=TenderChatResponse)
async def chat_with_tender(
    number: str,
    year: int,
    request: TenderChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Chat with AI about a specific tender using RAG.

    Fetches tender data including:
    - All tender fields (title, description, procuring_entity, estimated_value_mkd, etc.)
    - Bidders from tender_bidders table
    - Documents with content_text from documents table

    Builds context for Gemini and returns AI-generated answer in Macedonian.

    Requires authentication.

    Tender ID format: {number}/{year} e.g. 19816/2025
    """
    tender_id = f"{number}/{year}"

    # Check if Gemini is available
    if not GEMINI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI service not available. Configure GEMINI_API_KEY."
        )

    # Validate question
    if not request.question or len(request.question.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Question must be at least 3 characters"
        )

    # Get tender
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get bidders
    bidder_query = select(TenderBidder).where(TenderBidder.tender_id == tender_id)
    bidder_result = await db.execute(bidder_query)
    bidders = bidder_result.scalars().all()

    # Get documents with content
    doc_query = select(Document).where(
        Document.tender_id == tender_id
    ).where(
        Document.content_text.isnot(None)
    ).order_by(Document.uploaded_at.desc())
    doc_result = await db.execute(doc_query)
    documents = doc_result.scalars().all()

    # Build context for AI
    tender_context = f"""Тендер ID: {tender_id}
Наслов: {tender.title or 'Н/А'}
Набавувач: {tender.procuring_entity or 'Н/А'}
Категорија: {tender.category or 'Н/А'}
CPV код: {tender.cpv_code or 'Н/А'}
Проценета вредност: {f'{tender.estimated_value_mkd:,.0f} МКД' if tender.estimated_value_mkd else 'Н/А'}
Тип процедура: {tender.procedure_type or 'Н/А'}
Статус: {tender.status or 'Н/А'}
Датум на објавување: {tender.publication_date.isoformat() if tender.publication_date else 'Н/А'}
Датум на отворање: {tender.opening_date.isoformat() if tender.opening_date else 'Н/А'}
Краен рок: {tender.closing_date.isoformat() if tender.closing_date else 'Н/А'}
Број на понудувачи: {tender.num_bidders or 0}
Број на лотови: {tender.num_lots or 1}
Победник: {tender.winner or 'Н/А'}
Доделена вредност: {f'{tender.actual_value_mkd:,.0f} МКД' if tender.actual_value_mkd else 'Н/А'}

Опис:
{tender.description[:3000] if tender.description else 'Нема опис'}
"""

    # Add bidder info
    if bidders:
        bidder_info = "\n\nПонудувачи:\n"
        for b in bidders[:15]:
            winner_mark = " (ПОБЕДНИК)" if b.is_winner else ""
            bidder_info += f"- {b.company_name}{winner_mark}"
            if b.bid_amount_mkd:
                bidder_info += f" - {b.bid_amount_mkd:,.0f} МКД"
            if b.rank:
                bidder_info += f" (Ранг: {b.rank})"
            bidder_info += "\n"
        tender_context += bidder_info

    # Add document excerpts
    sources = []
    if documents:
        tender_context += "\n\nДокументи:\n"
        for i, doc in enumerate(documents[:5], 1):  # Limit to first 5 docs
            if doc.content_text:
                excerpt = doc.content_text[:5000]  # First 5000 chars
                tender_context += f"\n--- Документ {i}: {doc.file_name or 'Без име'} ---\n{excerpt}\n"
                sources.append({
                    "doc_id": str(doc.doc_id),
                    "file_name": doc.file_name,
                    "excerpt": excerpt[:200]  # Short preview for sources
                })

    # Build conversation history context
    history_context = ""
    if request.conversation_history:
        history_context = "\n\nПретходна конверзација:\n"
        for msg in request.conversation_history[-5:]:  # Last 5 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                history_context += f"Прашање: {content}\n"
            elif role == "assistant":
                history_context += f"Одговор: {content}\n"

    # Generate AI response
    try:
        # Use configured model or fallback
        model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
        model = genai.GenerativeModel(model_name)

        system_prompt = """Ти си асистент за јавни набавки. Одговарај на прашања за овој тендер на македонски јазик.

Упатства:
- Биди специфичен и цитирај извори кога е можно
- Ако информацијата не е достапна во контекстот, јасно кажи дека не знаеш
- Користи податоци од документите и tender деталите
- Одговори на македонски јазик
- Биди концизен но информативен (2-4 реченици)"""

        prompt = f"""{system_prompt}

{tender_context}
{history_context}

Прашање на корисникот: {request.question}

Одговор:"""

        # Relaxed safety settings for business content
        response = model.generate_content(prompt)

        # Handle safety blocks
        try:
            answer = response.text
        except ValueError:
            answer = "Не можам да генерирам одговор. Обидете се со поинакво прашање."

        # Calculate confidence based on data availability
        confidence = 0.5  # Base confidence
        if tender.description:
            confidence += 0.1
        if bidders:
            confidence += 0.1
        if documents:
            confidence += 0.2
        if tender.estimated_value_mkd:
            confidence += 0.05
        if tender.winner:
            confidence += 0.05

        confidence = min(confidence, 1.0)

        # Format sources for response
        formatted_sources = [
            TenderChatSource(
                doc_id=s["doc_id"],
                file_name=s["file_name"],
                excerpt=s["excerpt"]
            )
            for s in sources
        ]

        return TenderChatResponse(
            answer=answer,
            sources=formatted_sources,
            confidence=round(confidence, 2),
            tender_id=tender_id
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"AI chat failed: {str(e)}"
        )


# ============================================================================
# TENDER DOCUMENTS (Must be before the path parameter route)
# ============================================================================
# Routes use /{number}/{year:int}/... pattern to handle tender IDs with slashes like "19816/2025"

@router.get("/{number}/{year:int}/documents")
async def get_tender_documents(
    number: str,
    year: int,
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


@router.get("/{number}/{year:int}/bidders")
async def get_tender_bidders(
    number: str,
    year: int,
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


@router.get("/{number}/{year:int}/lots")
async def get_tender_lots(
    number: str,
    year: int,
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


@router.get("/{number}/{year:int}/enhanced")
async def get_enhanced_tender(
    number: str,
    year: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get enhanced tender data with all fields, bidders, price analysis, and completeness score.
    Tender ID format: {number}/{year} e.g. 19816/2025

    This endpoint provides a comprehensive view of the tender including:
    - All standard tender fields
    - Bidders from tender_bidders table with fallback to raw_data_json
    - Price analysis (estimated, winning bid, bid range, num bidders)
    - Data completeness score (0-1)
    - Documents with file_url for download
    """
    tender_id = f"{number}/{year}"
    return await get_enhanced_tender_by_id(tender_id, db)


@router.get("/{number}/{year:int}/suppliers")
async def get_tender_suppliers(number: str, year: int, db: AsyncSession = Depends(get_db)):
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
# FLEXIBLE TENDER ENDPOINTS (Accept any tender_id format - UUID or number/year)
# These must be BEFORE the catch-all route
# ============================================================================

@router.get("/by-id/{tender_id:path}/ai_summary")
async def get_tender_ai_summary_by_id(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-generated summary for a tender by any ID format.
    Accepts both UUID format and number/year format.
    Uses Gemini AI for intelligent analysis.
    """
    from datetime import datetime
    import logging
    logger = logging.getLogger(__name__)

    # Normalize the tender_id
    original_id = tender_id
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")
    logger.info(f"AI Summary requested for tender_id: {original_id} -> {tender_id}")

    # Get tender
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        logger.warning(f"AI Summary: Tender not found for id: {tender_id}")
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get documents for additional context
    doc_query = select(Document).where(Document.tender_id == tender_id)
    doc_result = await db.execute(doc_query)
    documents = doc_result.scalars().all()

    # Get document text excerpts for AI context
    doc_texts = []
    for doc in documents[:3]:  # Limit to first 3 docs
        if doc.content_text:
            doc_texts.append(doc.content_text[:3000])

    # Get bidders info
    bidder_query = select(TenderBidder).where(TenderBidder.tender_id == tender_id)
    bidder_result = await db.execute(bidder_query)
    bidders = bidder_result.scalars().all()

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

    # Estimate complexity
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

    # Build context for AI
    tender_context = f"""
Тендер ID: {tender_id}
Наслов: {tender.title or 'Н/А'}
Набавувач: {tender.procuring_entity or 'Н/А'}
Категорија: {tender.category or 'Н/А'}
CPV код: {tender.cpv_code or 'Н/А'}
Проценета вредност: {f'{tender.estimated_value_mkd:,.0f} МКД' if tender.estimated_value_mkd else 'Н/А'}
Тип процедура: {tender.procedure_type or 'Н/А'}
Статус: {tender.status or 'Н/А'}
Краен рок: {tender.closing_date.isoformat() if tender.closing_date else 'Н/А'}
Број на понудувачи: {tender.num_bidders or 0}
Број на лотови: {tender.num_lots or 1}

Опис:
{tender.description[:5000] if tender.description else 'Нема опис'}
"""

    # Add bidder info
    if bidders:
        bidder_info = "\n\nПонудувачи:\n"
        for b in bidders[:10]:
            winner_mark = " (ПОБЕДНИК)" if b.is_winner else ""
            bidder_info += f"- {b.company_name}{winner_mark}"
            if b.bid_amount_mkd:
                bidder_info += f" - {b.bid_amount_mkd:,.0f} МКД"
            bidder_info += "\n"
        tender_context += bidder_info

    # Add document excerpts
    if doc_texts:
        tender_context += "\n\nИзводи од документи:\n"
        for i, text in enumerate(doc_texts, 1):
            tender_context += f"\n--- Документ {i} ---\n{text}\n"

    # Generate AI summary
    overview = ""
    key_requirements = []
    strategic_insights = []
    model_used = "rule-based-v1"

    if GEMINI_AVAILABLE:
        try:
            # Use configured model or fallback
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
            model = genai.GenerativeModel(model_name)

            # Add date context
            date_context = get_ai_date_context()

            prompt = f"""{date_context}

Анализирај го овој јавен тендер и дај структурирано резиме на македонски јазик.

{tender_context}

Одговори во JSON формат со следната структура:
{{
  "overview": "2-3 реченици општ преглед на набавката - што се бара, од кого, зошто е важно",
  "key_requirements": ["барање 1", "барање 2", ...],
  "strategic_insights": ["совет 1", "совет 2", ...],
  "recommended_actions": ["акција 1", "акција 2", ...]
}}

За key_requirements - извлечи ги најважните технички, финансиски и правни барања.
За strategic_insights - дај корисни совети за компании кои сакаат да учествуваат.
За recommended_actions - конкретни чекори што треба да се превземат.

Биди концизен и практичен. Фокусирај се на информации корисни за понудувачи."""

            # Relaxed safety settings for business content
            response = model.generate_content(prompt)

            # Handle safety blocks (finish_reason=2 means SAFETY)
            response_text = None
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    # finish_reason: 1=STOP (normal), 2=SAFETY, 3=RECITATION, 4=OTHER
                    if candidate.finish_reason in [2, 3, 4]:
                        logger.warning(f"Gemini response blocked: finish_reason={candidate.finish_reason}")
                        response_text = None
                    else:
                        try:
                            response_text = response.text
                        except ValueError:
                            response_text = None
                else:
                    try:
                        response_text = response.text
                    except ValueError:
                        response_text = None
            else:
                try:
                    response_text = response.text
                except ValueError:
                    response_text = None

            # Parse JSON from response if we got one
            if response_text:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        overview = parsed.get('overview', '')
                        key_requirements = parsed.get('key_requirements', [])
                        strategic_insights = parsed.get('strategic_insights', [])
                        model_used = model_name
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            logger.error(f"Gemini AI summary failed: {e}")
            # Fall through to rule-based

    # Fallback to rule-based if AI failed
    if not overview:
        overview = f"Тендер за {tender.title or 'без наслов'}"
        if tender.procuring_entity:
            overview += f" од {tender.procuring_entity}"
        if tender.estimated_value_mkd:
            overview += f". Проценета вредност: {tender.estimated_value_mkd:,.0f} МКД"
        if tender.category:
            overview += f". Категорија: {tender.category}"

        # Extract basic requirements from description
        if tender.description:
            desc_lower = tender.description.lower()
            if "гаранција" in desc_lower or "депозит" in desc_lower:
                key_requirements.append("Потребна гаранција/депозит")
            if "сертификат" in desc_lower or "iso" in desc_lower:
                key_requirements.append("Потребни сертификати")
            if "искуство" in desc_lower or "референц" in desc_lower:
                key_requirements.append("Потребно претходно искуство")

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
            "strategic_insights": strategic_insights if strategic_insights else [],
            "estimated_complexity": complexity,
            "complexity_factors": complexity_factors,
            "suggested_cpv_codes": suggested_cpv,
            "deadline_urgency": urgency,
            "days_remaining": days_remaining,
            "competition_level": competition
        },
        "generated_at": datetime.utcnow().isoformat(),
        "model": model_used
    }


@router.get("/by-id/{tender_id:path}/bid-advice")
async def get_tender_bid_advice_by_id(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-powered bid recommendations for a tender.
    Returns market analysis, historical data, and bid strategies.
    """
    from datetime import datetime
    import statistics

    # Normalize the tender_id
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")

    # Get tender
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get bidders for this tender
    bidder_query = select(TenderBidder).where(TenderBidder.tender_id == tender_id)
    bidder_result = await db.execute(bidder_query)
    bidders = bidder_result.scalars().all()

    # Get historical data for similar tenders (same CPV code)
    historical_bids = []
    avg_discount = 0.0
    competition_level = "unknown"

    if tender.cpv_code:
        # Get similar tenders from last 2 years
        hist_query = text("""
            SELECT t.tender_id, t.estimated_value_mkd, t.actual_value_mkd,
                   t.num_bidders, tb.bid_amount_mkd, tb.is_winner
            FROM tenders t
            LEFT JOIN tender_bidders tb ON t.tender_id = tb.tender_id
            WHERE t.cpv_code LIKE :cpv_prefix
              AND t.tender_id != :current_tender
              AND t.publication_date > NOW() - INTERVAL '2 years'
              AND t.actual_value_mkd IS NOT NULL
            ORDER BY t.publication_date DESC
            LIMIT 100
        """)
        hist_result = await db.execute(hist_query, {
            "cpv_prefix": tender.cpv_code[:4] + "%",
            "current_tender": tender_id
        })
        historical_data = hist_result.fetchall()

        # Calculate statistics
        discounts = []
        winning_bids = []
        bidder_counts = []

        for row in historical_data:
            if row.estimated_value_mkd and row.actual_value_mkd:
                discount = float((row.estimated_value_mkd - row.actual_value_mkd) / row.estimated_value_mkd * 100)
                discounts.append(discount)
            if row.bid_amount_mkd and row.is_winner:
                winning_bids.append(float(row.bid_amount_mkd))
            if row.num_bidders:
                bidder_counts.append(row.num_bidders)

        if discounts:
            avg_discount = float(statistics.mean(discounts))
        if bidder_counts:
            avg_bidders = statistics.mean(bidder_counts)
            if avg_bidders >= 5:
                competition_level = "high"
            elif avg_bidders >= 3:
                competition_level = "medium"
            else:
                competition_level = "low"

    # Build market analysis
    market_analysis = {
        "avg_discount": round(avg_discount, 2),
        "typical_bidders": len(bidders) if bidders else 0,
        "price_trend": "stable",
        "competition_level": competition_level
    }

    # Build historical data summary
    historical_summary = {
        "similar_tenders": len(set(r.tender_id for r in historical_data)) if 'historical_data' in dir() and historical_data else 0,
        "avg_winning_bid": round(statistics.mean(winning_bids), 0) if winning_bids else None,
        "min_bid": round(min(winning_bids), 0) if winning_bids else None,
        "max_bid": round(max(winning_bids), 0) if winning_bids else None,
        "avg_discount_pct": round(avg_discount, 2)
    }

    # Generate bid recommendations
    recommendations = []
    estimated_value = float(tender.estimated_value_mkd) if tender.estimated_value_mkd else 0

    if estimated_value > 0:
        # Aggressive strategy - 15-20% below estimate
        aggressive_bid = estimated_value * (1 - (avg_discount + 5) / 100) if avg_discount else estimated_value * 0.82
        recommendations.append({
            "strategy": "aggressive",
            "recommended_bid": round(aggressive_bid, 0),
            "win_probability": 0.7 if competition_level == "low" else 0.5,
            "reasoning": f"Агресивна понуда со попуст од {round((1 - aggressive_bid/estimated_value) * 100, 1)}% под проценетата вредност"
        })

        # Balanced strategy - around average discount
        balanced_bid = estimated_value * (1 - avg_discount / 100) if avg_discount else estimated_value * 0.9
        recommendations.append({
            "strategy": "balanced",
            "recommended_bid": round(balanced_bid, 0),
            "win_probability": 0.5,
            "reasoning": f"Балансирана понуда со попуст од {round((1 - balanced_bid/estimated_value) * 100, 1)}% базирано на историски просек"
        })

        # Safe strategy - smaller discount
        safe_bid = estimated_value * (1 - max(0, avg_discount - 5) / 100) if avg_discount else estimated_value * 0.95
        recommendations.append({
            "strategy": "safe",
            "recommended_bid": round(safe_bid, 0),
            "win_probability": 0.3 if competition_level == "high" else 0.4,
            "reasoning": f"Безбедна понуда со попуст од {round((1 - safe_bid/estimated_value) * 100, 1)}% за поголема профитабилност"
        })

    # Get competitor insights
    competitor_insights = []
    for b in bidders[:5]:
        if b.company_name:
            # Get historical win rate for this company
            comp_query = text("""
                SELECT COUNT(*) as total_bids,
                       SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as wins
                FROM tender_bidders
                WHERE company_name = :company
            """)
            comp_result = await db.execute(comp_query, {"company": b.company_name})
            comp_stats = comp_result.fetchone()

            if comp_stats and comp_stats.total_bids > 0:
                win_rate = (comp_stats.wins / comp_stats.total_bids) * 100
                competitor_insights.append({
                    "company": b.company_name,
                    "win_rate": round(win_rate, 1),
                    "avg_discount": round(avg_discount, 1)  # Use overall avg as estimate
                })

    # Generate AI summary
    ai_summary = f"За овој тендер има {len(bidders)} понудувачи. "
    if avg_discount > 0:
        ai_summary += f"Историски просечен попуст за слични тендери е {round(avg_discount, 1)}%. "
    ai_summary += f"Ниво на конкуренција: {competition_level}."

    return {
        "tender_id": tender_id,
        "tender_title": tender.title,
        "estimated_value": float(tender.estimated_value_mkd) if tender.estimated_value_mkd else None,
        "cpv_code": tender.cpv_code,
        "category": tender.category,
        "procuring_entity": tender.procuring_entity,
        "market_analysis": market_analysis,
        "historical_data": historical_summary,
        "recommendations": recommendations,
        "competitor_insights": competitor_insights,
        "ai_summary": ai_summary,
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/by-id/{tender_id:path}/price_history")
async def get_tender_price_history_by_id(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get price/value history for a tender by any ID format.
    Accepts both UUID format and number/year format.
    """
    from sqlalchemy import text

    # Normalize the tender_id
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")

    # Get tender
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Build price history points
    points = []

    # Initial publication point
    if tender.publication_date and tender.estimated_value_mkd:
        points.append({
            "date": tender.publication_date.isoformat(),
            "estimated_value_mkd": float(tender.estimated_value_mkd),
            "awarded_value_mkd": None,
            "type": "publication"
        })

    # Award point if awarded
    if tender.status in ['awarded', 'completed'] and tender.actual_value_mkd:
        award_date = tender.contract_signing_date or tender.closing_date or tender.publication_date
        if award_date:
            points.append({
                "date": award_date.isoformat(),
                "estimated_value_mkd": float(tender.estimated_value_mkd) if tender.estimated_value_mkd else None,
                "awarded_value_mkd": float(tender.actual_value_mkd),
                "type": "award"
            })

    # Sort by date
    points.sort(key=lambda x: x["date"])

    return {
        "tender_id": tender_id,
        "points": points
    }


@router.get("/by-id/{tender_id:path}/documents")
async def get_tender_documents_by_id(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get documents for a tender by any ID format."""
    from models import Document
    from schemas import DocumentResponse

    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")

    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    doc_query = select(Document).where(Document.tender_id == tender_id).order_by(Document.uploaded_at.desc())
    result = await db.execute(doc_query)
    documents = result.scalars().all()

    return {
        "tender_id": tender_id,
        "total": len(documents),
        "documents": [DocumentResponse.from_orm(doc) for doc in documents]
    }


@router.get("/by-id/{tender_id:path}/bidders")
async def get_tender_bidders_by_id(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get bidders for a tender by any ID format."""
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")

    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    bidder_query = select(TenderBidder).where(
        TenderBidder.tender_id == tender_id
    ).order_by(TenderBidder.ranking.asc().nullslast())
    result = await db.execute(bidder_query)
    bidders = result.scalars().all()

    return {
        "tender_id": tender_id,
        "total": len(bidders),
        "bidders": [
            {
                "bidder_id": str(b.bidder_id),
                "company_name": b.company_name,
                "bid_amount_mkd": float(b.bid_amount_mkd) if b.bid_amount_mkd else None,
                "is_winner": b.is_winner,
                "ranking": b.ranking,
                "bid_date": b.bid_date.isoformat() if b.bid_date else None,
                "disqualification_reason": b.disqualification_reason
            }
            for b in bidders
        ]
    }


@router.get("/by-id/{tender_id:path}/ai-products")
async def get_ai_products_by_id(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get AI-extracted products for a tender by any ID format."""
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")

    # Check tender exists
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get product items for this tender
    products_query = select(ProductItem).where(
        ProductItem.tender_id == tender_id
    ).order_by(ProductItem.item_number.asc().nullslast())
    result = await db.execute(products_query)
    products = result.scalars().all()

    # Get count of source documents
    doc_query = select(func.count(Document.doc_id)).where(
        Document.tender_id == tender_id
    )
    doc_result = await db.execute(doc_query)
    source_documents = doc_result.scalar() or 0

    if not products:
        return {
            "tender_id": tender_id,
            "extraction_status": "no_documents" if source_documents == 0 else "extraction_failed",
            "products": [],
            "summary": "Не се пронајдени производи во документацијата" if source_documents > 0 else "Нема достапни документи за анализа",
            "source_documents": source_documents
        }

    return {
        "tender_id": tender_id,
        "extraction_status": "success",
        "products": [
            {
                "name": p.name,
                "quantity": str(p.quantity) if p.quantity else None,
                "unit": p.unit,
                "unit_price": str(p.unit_price) if p.unit_price else None,
                "total_price": str(p.total_price) if p.total_price else None,
                "specifications": json.dumps(p.specifications) if p.specifications else None,
                "category": p.category
            }
            for p in products
        ],
        "summary": f"Извлечени {len(products)} производи/ставки од тендерската документација",
        "source_documents": source_documents
    }


@router.get("/by-id/{tender_id:path}/enhanced")
async def get_enhanced_tender_by_id(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get enhanced tender data with all fields, bidders, price analysis, and completeness score.

    This endpoint provides a comprehensive view of the tender including:
    - All standard tender fields
    - Bidders from tender_bidders table with fallback to raw_data_json
    - Price analysis (estimated, winning bid, bid range, num bidders)
    - Data completeness score (0-1)
    - Documents with file_url for download
    """
    import json

    # Normalize tender ID
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")

    # Get tender
    tender_query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(tender_query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Get bidders from tender_bidders table
    bidder_query = select(TenderBidder).where(
        TenderBidder.tender_id == tender_id
    ).order_by(TenderBidder.rank.asc().nullslast(), TenderBidder.is_winner.desc())
    result = await db.execute(bidder_query)
    db_bidders = result.scalars().all()

    # Format bidders
    bidders = [
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
        for b in db_bidders
    ]

    # Fallback to raw_data_json if no bidders in table
    if not bidders and tender.raw_data_json:
        try:
            raw_json = tender.raw_data_json if isinstance(tender.raw_data_json, dict) else json.loads(tender.raw_data_json)
            bidders_data = raw_json.get('bidders_data')
            if bidders_data:
                if isinstance(bidders_data, str):
                    bidders = json.loads(bidders_data)
                elif isinstance(bidders_data, list):
                    bidders = bidders_data
        except (json.JSONDecodeError, TypeError):
            pass

    # Calculate price analysis
    price_analysis = {
        "estimated_value": float(tender.estimated_value_mkd) if tender.estimated_value_mkd else None,
        "winning_bid": None,
        "lowest_bid": None,
        "highest_bid": None,
        "num_bidders": len(bidders)
    }

    # Get winning bid
    if tender.actual_value_mkd:
        price_analysis["winning_bid"] = float(tender.actual_value_mkd)
    else:
        # Try to find winner bid from bidders
        for b in bidders:
            if b.get("is_winner") and b.get("bid_amount_mkd"):
                price_analysis["winning_bid"] = b["bid_amount_mkd"]
                break

    # Calculate lowest and highest bids
    bid_amounts = [b["bid_amount_mkd"] for b in bidders if b.get("bid_amount_mkd") is not None]
    if bid_amounts:
        price_analysis["lowest_bid"] = min(bid_amounts)
        price_analysis["highest_bid"] = max(bid_amounts)

    # Get documents
    doc_query = select(Document).where(Document.tender_id == tender_id).order_by(Document.uploaded_at.desc())
    result = await db.execute(doc_query)
    documents = result.scalars().all()

    doc_list = [
        {
            "doc_id": str(doc.doc_id),
            "doc_type": doc.doc_type,
            "file_name": doc.file_name,
            "file_url": doc.file_url,
            "file_path": doc.file_path,
            "extraction_status": doc.extraction_status,
            "file_size_bytes": doc.file_size_bytes,
            "page_count": doc.page_count,
            "mime_type": doc.mime_type,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
        }
        for doc in documents
    ]

    # Calculate data completeness score
    completeness_score = 0.0
    total_weight = 0.0

    # Define field weights
    fields_to_check = [
        ("title", 0.1, tender.title),
        ("description", 0.15, tender.description),
        ("estimated_value_mkd", 0.1, tender.estimated_value_mkd),
        ("actual_value_mkd", 0.1, tender.actual_value_mkd),
        ("winner", 0.1, tender.winner),
        ("procuring_entity", 0.1, tender.procuring_entity),
        ("has_bidders", 0.2, len(bidders) > 0),
        ("has_documents", 0.15, len(documents) > 0)
    ]

    for field_name, weight, value in fields_to_check:
        total_weight += weight
        if value:
            completeness_score += weight

    # Normalize to 0-1 scale
    data_completeness = round(completeness_score / total_weight, 2) if total_weight > 0 else 0.0

    # Build response with all tender fields
    response = {
        "tender_id": tender.tender_id,
        "title": tender.title,
        "description": tender.description,
        "category": tender.category,
        "procuring_entity": tender.procuring_entity,
        "opening_date": tender.opening_date.isoformat() if tender.opening_date else None,
        "closing_date": tender.closing_date.isoformat() if tender.closing_date else None,
        "publication_date": tender.publication_date.isoformat() if tender.publication_date else None,
        "estimated_value_mkd": float(tender.estimated_value_mkd) if tender.estimated_value_mkd else None,
        "estimated_value_eur": float(tender.estimated_value_eur) if tender.estimated_value_eur else None,
        "actual_value_mkd": float(tender.actual_value_mkd) if tender.actual_value_mkd else None,
        "actual_value_eur": float(tender.actual_value_eur) if tender.actual_value_eur else None,
        "cpv_code": tender.cpv_code,
        "status": tender.status,
        "winner": tender.winner,
        "source_url": tender.source_url,
        "language": tender.language,
        "source_category": tender.source_category,
        "procedure_type": tender.procedure_type,
        "contract_signing_date": tender.contract_signing_date.isoformat() if tender.contract_signing_date else None,
        "contract_duration": tender.contract_duration,
        "contracting_entity_category": tender.contracting_entity_category,
        "procurement_holder": tender.procurement_holder,
        "bureau_delivery_date": tender.bureau_delivery_date.isoformat() if tender.bureau_delivery_date else None,
        "contact_person": tender.contact_person,
        "contact_email": tender.contact_email,
        "contact_phone": tender.contact_phone,
        "num_bidders": tender.num_bidders,
        "security_deposit_mkd": float(tender.security_deposit_mkd) if tender.security_deposit_mkd else None,
        "performance_guarantee_mkd": float(tender.performance_guarantee_mkd) if tender.performance_guarantee_mkd else None,
        "payment_terms": tender.payment_terms,
        "evaluation_method": tender.evaluation_method,
        "award_criteria": tender.award_criteria,
        "has_lots": tender.has_lots,
        "num_lots": tender.num_lots,
        "amendment_count": tender.amendment_count,
        "last_amendment_date": tender.last_amendment_date.isoformat() if tender.last_amendment_date else None,
        "scraped_at": tender.scraped_at.isoformat() if tender.scraped_at else None,
        "created_at": tender.created_at.isoformat() if tender.created_at else None,
        "updated_at": tender.updated_at.isoformat() if tender.updated_at else None,

        # Enhanced fields
        "bidders": bidders,
        "price_analysis": price_analysis,
        "data_completeness": data_completeness,
        "documents": doc_list
    }

    return response


# ============================================================================
# GET SINGLE TENDER (Path parameter - must be LAST among GET routes)
# ============================================================================

@router.get("/{tender_id:path}")
async def get_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get tender by ID. Supports IDs containing slashes (encoded in the path).
    Returns tender data with bidders parsed from raw_data_json.
    """
    import json

    # Normalize encoded slash IDs
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")
    query = select(Tender).where(Tender.tender_id == tender_id)
    result = await db.execute(query)
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Build response with parsed bidders from raw_data_json
    response = TenderResponse.from_orm(tender).dict()

    # Parse bidders_data from raw_data_json if available
    bidders = []
    lots = []
    if tender.raw_data_json:
        try:
            raw_json = tender.raw_data_json if isinstance(tender.raw_data_json, dict) else json.loads(tender.raw_data_json)

            # Extract bidders_data
            bidders_data = raw_json.get('bidders_data')
            if bidders_data:
                if isinstance(bidders_data, str):
                    bidders = json.loads(bidders_data)
                elif isinstance(bidders_data, list):
                    bidders = bidders_data

            # Extract lots_data
            lots_data = raw_json.get('lots_data')
            if lots_data:
                if isinstance(lots_data, str):
                    lots = json.loads(lots_data)
                elif isinstance(lots_data, list):
                    lots = lots_data
        except (json.JSONDecodeError, TypeError) as e:
            # Log but don't fail - just return empty bidders
            pass

    response['bidders'] = bidders
    response['lots'] = lots
    response['raw_data_json'] = tender.raw_data_json

    return response


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
