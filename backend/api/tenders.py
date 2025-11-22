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
from models import Tender
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
# GET TENDERS
# ============================================================================

@router.get("", response_model=TenderListResponse)
async def list_tenders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    status: Optional[str] = None,
    procuring_entity: Optional[str] = None,
    cpv_code: Optional[str] = None,
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
    - procuring_entity: Filter by procuring entity
    - cpv_code: Filter by CPV code
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
    if procuring_entity:
        filters.append(Tender.procuring_entity.ilike(f"%{procuring_entity}%"))
    if cpv_code:
        filters.append(Tender.cpv_code.startswith(cpv_code))

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

    # Value range filters
    if search.min_value_mkd:
        filters.append(Tender.estimated_value_mkd >= search.min_value_mkd)
    if search.max_value_mkd:
        filters.append(Tender.estimated_value_mkd <= search.max_value_mkd)

    # Date range filters
    if search.opening_date_from:
        filters.append(Tender.opening_date >= search.opening_date_from)
    if search.opening_date_to:
        filters.append(Tender.opening_date <= search.opening_date_to)
    if search.closing_date_from:
        filters.append(Tender.closing_date >= search.closing_date_from)
    if search.closing_date_to:
        filters.append(Tender.closing_date <= search.closing_date_to)

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


@router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get tender by ID

    Parameters:
    - tender_id: Tender ID
    """
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


# ============================================================================
# TENDER STATISTICS
# ============================================================================

@router.get("/stats/overview")
async def get_tender_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get tender statistics overview

    Returns counts, totals, and breakdowns
    """
    # Total tenders
    total_query = select(func.count()).select_from(Tender)
    total_tenders = await db.scalar(total_query)

    # Tenders by status
    open_query = select(func.count()).select_from(Tender).where(Tender.status == "open")
    open_tenders = await db.scalar(open_query)

    closed_query = select(func.count()).select_from(Tender).where(Tender.status == "closed")
    closed_tenders = await db.scalar(closed_query)

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

    return {
        "total_tenders": total_tenders,
        "open_tenders": open_tenders,
        "closed_tenders": closed_tenders,
        "total_value_mkd": float(total_value),
        "avg_value_mkd": float(avg_value),
        "tenders_by_category": categories
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
