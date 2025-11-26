"""
Procuring Entities API endpoints
Entity profiles and tender statistics
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from database import get_db
from models import ProcuringEntity, Tender

router = APIRouter(prefix="/entities", tags=["entities"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class EntityResponse(BaseModel):
    """Single entity response"""
    entity_id: str
    entity_name: str
    entity_type: Optional[str] = None
    category: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    total_tenders: int = 0
    total_value_mkd: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EntityListResponse(BaseModel):
    """Paginated entity list response"""
    total: int
    page: int
    page_size: int
    items: List[EntityResponse]


class EntityWithTendersResponse(EntityResponse):
    """Entity with recent tenders"""
    recent_tenders: List[dict] = []
    tender_count_by_status: dict = {}


# ============================================================================
# LIST ENTITIES
# ============================================================================

@router.get("", response_model=EntityListResponse)
async def list_entities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    city: Optional[str] = None,
    category: Optional[str] = None,
    sort_by: str = Query("total_tenders", description="Field to sort by"),
    sort_order: str = Query("desc", description="asc or desc"),
    db: AsyncSession = Depends(get_db)
):
    """
    List procuring entities with pagination and filtering

    Parameters:
    - page: Page number (1-indexed)
    - page_size: Items per page
    - search: Search in entity name
    - city: Filter by city
    - category: Filter by category
    - sort_by: Field to sort by (total_tenders, entity_name, created_at)
    - sort_order: Sort order (asc or desc)
    """
    # Build query
    query = select(ProcuringEntity)

    # Apply filters
    filters = []
    if search:
        filters.append(ProcuringEntity.entity_name.ilike(f"%{search}%"))
    if city:
        filters.append(ProcuringEntity.city == city)
    if category:
        filters.append(ProcuringEntity.category == category)

    if filters:
        query = query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(ProcuringEntity)
    if filters:
        count_query = count_query.where(and_(*filters))
    total = await db.scalar(count_query)

    # Sort
    sort_column = getattr(ProcuringEntity, sort_by, ProcuringEntity.total_tenders)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    entities = result.scalars().all()

    return EntityListResponse(
        total=total or 0,
        page=page,
        page_size=page_size,
        items=[EntityResponse(
            entity_id=str(e.entity_id),
            entity_name=e.entity_name,
            entity_type=e.entity_type,
            category=e.category,
            tax_id=e.tax_id,
            address=e.address,
            city=e.city,
            contact_person=e.contact_person,
            contact_email=e.contact_email,
            contact_phone=e.contact_phone,
            website=e.website,
            total_tenders=e.total_tenders or 0,
            total_value_mkd=float(e.total_value_mkd) if e.total_value_mkd else None,
            created_at=e.created_at
        ) for e in entities]
    )


# ============================================================================
# GET ENTITY BY ID
# ============================================================================

@router.get("/{entity_id}", response_model=EntityWithTendersResponse)
async def get_entity(
    entity_id: str,
    include_tenders: bool = Query(True, description="Include recent tenders"),
    tender_limit: int = Query(10, ge=1, le=50, description="Max tenders to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get entity profile by ID with optional recent tenders

    Parameters:
    - entity_id: Entity UUID
    - include_tenders: Whether to include recent tenders
    - tender_limit: Maximum number of tenders to include
    """
    # Get entity
    query = select(ProcuringEntity).where(ProcuringEntity.entity_id == entity_id)
    result = await db.execute(query)
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Build response
    response = EntityWithTendersResponse(
        entity_id=str(entity.entity_id),
        entity_name=entity.entity_name,
        entity_type=entity.entity_type,
        category=entity.category,
        tax_id=entity.tax_id,
        address=entity.address,
        city=entity.city,
        contact_person=entity.contact_person,
        contact_email=entity.contact_email,
        contact_phone=entity.contact_phone,
        website=entity.website,
        total_tenders=entity.total_tenders or 0,
        total_value_mkd=float(entity.total_value_mkd) if entity.total_value_mkd else None,
        created_at=entity.created_at,
        recent_tenders=[],
        tender_count_by_status={}
    )

    if include_tenders:
        # Get recent tenders for this entity
        tenders_query = select(Tender).where(
            Tender.procuring_entity == entity.entity_name
        ).order_by(Tender.created_at.desc()).limit(tender_limit)

        tenders_result = await db.execute(tenders_query)
        tenders = tenders_result.scalars().all()

        response.recent_tenders = [
            {
                "tender_id": t.tender_id,
                "title": t.title,
                "status": t.status,
                "procedure_type": t.procedure_type,
                "estimated_value_mkd": float(t.estimated_value_mkd) if t.estimated_value_mkd else None,
                "opening_date": t.opening_date.isoformat() if t.opening_date else None,
                "closing_date": t.closing_date.isoformat() if t.closing_date else None,
            }
            for t in tenders
        ]

        # Get tender count by status
        status_query = select(
            Tender.status,
            func.count(Tender.tender_id).label('count')
        ).where(
            Tender.procuring_entity == entity.entity_name
        ).group_by(Tender.status)

        status_result = await db.execute(status_query)
        response.tender_count_by_status = {
            row.status: row.count for row in status_result
        }

    return response


# ============================================================================
# GET ENTITY BY NAME
# ============================================================================

@router.get("/by-name/{entity_name}", response_model=EntityWithTendersResponse)
async def get_entity_by_name(
    entity_name: str,
    include_tenders: bool = Query(True),
    tender_limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get entity profile by name

    Parameters:
    - entity_name: Entity name (exact match)
    - include_tenders: Whether to include recent tenders
    - tender_limit: Maximum number of tenders to include
    """
    # Get entity by name
    query = select(ProcuringEntity).where(ProcuringEntity.entity_name == entity_name)
    result = await db.execute(query)
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Reuse the get_entity logic
    return await get_entity(
        entity_id=str(entity.entity_id),
        include_tenders=include_tenders,
        tender_limit=tender_limit,
        db=db
    )
