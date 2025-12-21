"""
Suppliers API endpoints
Supplier profiles and tender participation history
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

from database import get_db

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class SupplierResponse(BaseModel):
    """Supplier profile response"""
    supplier_id: str
    company_name: str
    tax_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = "North Macedonia"
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None

    # Statistics
    total_bids: int = 0
    total_wins: int = 0
    win_rate: Optional[float] = None
    total_value_won_mkd: Optional[Decimal] = None

    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SupplierListResponse(BaseModel):
    """Paginated supplier list response"""
    total: int
    page: int
    page_size: int
    items: List[SupplierResponse]


class SupplierTenderParticipation(BaseModel):
    """Tender participation record"""
    tender_id: str
    title: str
    procuring_entity: str
    bid_amount_mkd: Optional[Decimal] = None
    rank: Optional[int] = None
    is_winner: bool = False
    status: str
    closing_date: Optional[datetime] = None


class SupplierDetailResponse(SupplierResponse):
    """Detailed supplier response with tender history"""
    recent_participations: List[SupplierTenderParticipation] = []
    wins_by_category: dict = {}
    wins_by_entity: dict = {}


# ============================================================================
# LIST SUPPLIERS
# ============================================================================

@router.get("", response_model=SupplierListResponse)
async def list_suppliers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    city: Optional[str] = None,
    min_wins: Optional[int] = None,
    sort_by: str = Query("total_wins", description="Field to sort by"),
    sort_order: str = Query("desc", description="asc or desc"),
    db: AsyncSession = Depends(get_db)
):
    """
    List suppliers with pagination and filtering

    Parameters:
    - page: Page number (1-indexed)
    - page_size: Items per page
    - search: Search in company name
    - city: Filter by city
    - min_wins: Minimum number of tender wins
    - sort_by: Field to sort by (total_wins, total_bids, win_rate, company_name)
    - sort_order: Sort order (asc or desc)
    """
    # Build query - Note: suppliers table has total_contract_value_mkd not total_value_won_mkd
    base_query = """
        SELECT
            supplier_id::text, company_name, tax_id,
            address, city,
            contact_person, contact_email, contact_phone, website,
            total_bids, total_wins, win_rate, total_contract_value_mkd,
            created_at
        FROM suppliers
        WHERE 1=1
    """

    params = {}

    # Apply filters
    if search:
        base_query += " AND company_name ILIKE :search"
        params["search"] = f"%{search}%"
    if city:
        base_query += " AND city = :city"
        params["city"] = city
    if min_wins:
        base_query += " AND total_wins >= :min_wins"
        params["min_wins"] = min_wins

    # Count total
    count_query = f"SELECT COUNT(*) FROM ({base_query}) as filtered"
    count_result = await db.execute(text(count_query), params)
    total = count_result.scalar() or 0

    # Sort
    valid_sort_fields = ['total_wins', 'total_bids', 'win_rate', 'company_name', 'created_at']
    if sort_by not in valid_sort_fields:
        sort_by = 'total_wins'
    order = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
    base_query += f" ORDER BY {sort_by} {order} NULLS LAST"

    # Paginate
    offset = (page - 1) * page_size
    base_query += f" LIMIT :limit OFFSET :offset"
    params["limit"] = page_size
    params["offset"] = offset

    # Execute
    result = await db.execute(text(base_query), params)
    rows = result.fetchall()

    items = [
        SupplierResponse(
            supplier_id=str(row.supplier_id),
            company_name=row.company_name,
            tax_id=row.tax_id,
            address=row.address,
            city=row.city,
            country="North Macedonia",
            contact_person=row.contact_person,
            contact_email=row.contact_email,
            contact_phone=row.contact_phone,
            website=row.website,
            total_bids=row.total_bids or 0,
            total_wins=row.total_wins or 0,
            win_rate=float(row.win_rate) if row.win_rate else None,
            total_value_won_mkd=row.total_contract_value_mkd,
            created_at=row.created_at
        )
        for row in rows
    ]

    return SupplierListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


# ============================================================================
# SUPPLIER AGGREGATE STATS
# ============================================================================

class SupplierStatsResponse(BaseModel):
    """Aggregate supplier statistics"""
    total_suppliers: int
    suppliers_with_wins: int
    total_bids: int
    average_win_rate: Optional[float]


@router.get("/stats", response_model=SupplierStatsResponse)
async def get_supplier_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregate statistics for all suppliers"""
    query = text("""
        SELECT
            COUNT(*) as total_suppliers,
            COUNT(*) FILTER (WHERE total_wins > 0) as suppliers_with_wins,
            COALESCE(SUM(total_bids), 0) as total_bids,
            ROUND(AVG(win_rate) FILTER (WHERE win_rate IS NOT NULL), 1) as average_win_rate
        FROM suppliers
    """)
    result = await db.execute(query)
    row = result.fetchone()

    return SupplierStatsResponse(
        total_suppliers=row.total_suppliers,
        suppliers_with_wins=row.suppliers_with_wins,
        total_bids=row.total_bids,
        average_win_rate=float(row.average_win_rate) if row.average_win_rate else None
    )


# ============================================================================
# GET ALL KNOWN WINNERS (for competitor selection)
# IMPORTANT: Must be defined BEFORE /{supplier_id} to avoid route conflict
# ============================================================================

@router.get("/winners")
async def get_known_winners(
    search: str = Query(None, description="Optional search filter"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of all known tender winners for competitor selection.

    This combines:
    1. Winners from tender_bidders table
    2. Winners from tenders.winner field
    3. Suppliers from suppliers table

    Returns a deduplicated list sorted by win count.
    """
    # Combined query to get all known winning companies
    query = text("""
        WITH all_winners AS (
            -- From suppliers table
            SELECT
                company_name,
                total_wins as wins,
                total_bids as bids,
                total_contract_value_mkd as total_value
            FROM suppliers
            WHERE total_wins > 0

            UNION ALL

            -- From tender_bidders
            SELECT
                company_name,
                COUNT(*) FILTER (WHERE is_winner) as wins,
                COUNT(*) as bids,
                SUM(bid_amount_mkd) FILTER (WHERE is_winner) as total_value
            FROM tender_bidders
            WHERE company_name IS NOT NULL
            GROUP BY company_name

            UNION ALL

            -- From tenders.winner field
            SELECT
                winner as company_name,
                COUNT(*) as wins,
                COUNT(*) as bids,
                SUM(actual_value_mkd) as total_value
            FROM tenders
            WHERE winner IS NOT NULL AND winner != ''
            GROUP BY winner
        ),
        aggregated AS (
            SELECT
                company_name,
                SUM(wins) as total_wins,
                SUM(bids) as total_bids,
                SUM(total_value) as total_contract_value
            FROM all_winners
            WHERE company_name IS NOT NULL AND company_name != ''
            GROUP BY company_name
        )
        SELECT
            company_name,
            total_wins,
            total_bids,
            total_contract_value
        FROM aggregated
        WHERE company_name ILIKE :search_pattern
        ORDER BY total_wins DESC, total_bids DESC
        LIMIT :limit
    """)

    search_pattern = f"%{search}%" if search else "%"
    result = await db.execute(query, {
        "search_pattern": search_pattern,
        "limit": limit
    })
    rows = result.fetchall()

    return {
        "total": len(rows),
        "winners": [
            {
                "company_name": row.company_name,
                "total_wins": row.total_wins or 0,
                "total_bids": row.total_bids or 0,
                "total_contract_value": float(row.total_contract_value) if row.total_contract_value else None
            }
            for row in rows
        ]
    }


# ============================================================================
# SEARCH SUPPLIERS BY NAME
# IMPORTANT: Must be defined BEFORE /{supplier_id} to avoid route conflict
# ============================================================================

@router.get("/search/{company_name}", response_model=List[SupplierResponse])
async def search_suppliers_by_name(
    company_name: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Search suppliers by company name (fuzzy search)

    Parameters:
    - company_name: Search term
    - limit: Maximum results to return
    """
    search_query = text("""
        SELECT
            supplier_id::text, company_name, tax_id,
            address, city,
            contact_person, contact_email, contact_phone, website,
            total_bids, total_wins, win_rate, total_contract_value_mkd,
            created_at
        FROM suppliers
        WHERE company_name ILIKE :search
        ORDER BY total_wins DESC NULLS LAST
        LIMIT :limit
    """)

    result = await db.execute(search_query, {"search": f"%{company_name}%", "limit": limit})
    rows = result.fetchall()

    return [
        SupplierResponse(
            supplier_id=str(row.supplier_id),
            company_name=row.company_name,
            tax_id=row.tax_id,
            address=row.address,
            city=row.city,
            country="North Macedonia",
            contact_person=row.contact_person,
            contact_email=row.contact_email,
            contact_phone=row.contact_phone,
            website=row.website,
            total_bids=row.total_bids or 0,
            total_wins=row.total_wins or 0,
            win_rate=float(row.win_rate) if row.win_rate else None,
            total_value_won_mkd=row.total_contract_value_mkd,
            created_at=row.created_at
        )
        for row in rows
    ]


# ============================================================================
# GET SUPPLIER BY ID
# ============================================================================

@router.get("/{supplier_id}", response_model=SupplierDetailResponse)
async def get_supplier(
    supplier_id: str,
    include_participations: bool = Query(True, description="Include recent tender participations"),
    participation_limit: int = Query(100, ge=1, le=500, description="Max participations to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get supplier profile by ID with optional participation history

    Parameters:
    - supplier_id: Supplier UUID
    - include_participations: Whether to include tender history
    - participation_limit: Maximum number of participations to include
    """
    import uuid

    # Validate UUID format
    try:
        uuid.UUID(supplier_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid supplier ID format. Must be a valid UUID.")

    # Get supplier
    supplier_query = text("""
        SELECT
            supplier_id::text, company_name, tax_id,
            address, city,
            contact_person, contact_email, contact_phone, website,
            total_bids, total_wins, win_rate, total_contract_value_mkd,
            created_at
        FROM suppliers
        WHERE supplier_id = :supplier_id
    """)

    result = await db.execute(supplier_query, {"supplier_id": supplier_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Build response
    response = SupplierDetailResponse(
        supplier_id=str(row.supplier_id),
        company_name=row.company_name,
        tax_id=row.tax_id,
        address=row.address,
        city=row.city,
        country="North Macedonia",
        contact_person=row.contact_person,
        contact_email=row.contact_email,
        contact_phone=row.contact_phone,
        website=row.website,
        total_bids=row.total_bids or 0,
        total_wins=row.total_wins or 0,
        win_rate=float(row.win_rate) if row.win_rate else None,
        total_value_won_mkd=row.total_contract_value_mkd,
        created_at=row.created_at,
        recent_participations=[],
        wins_by_category={},
        wins_by_entity={}
    )

    if include_participations:
        # Get recent tender participations by matching company_name
        participations_query = text("""
            SELECT
                t.tender_id, t.title, t.procuring_entity,
                tb.bid_amount_mkd, tb.rank, tb.is_winner,
                t.status, t.closing_date
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            JOIN suppliers s ON tb.company_name = s.company_name
            WHERE s.supplier_id = :supplier_id
            ORDER BY t.closing_date DESC NULLS LAST
            LIMIT :limit
        """)

        part_result = await db.execute(
            participations_query,
            {"supplier_id": supplier_id, "limit": participation_limit}
        )
        part_rows = part_result.fetchall()

        response.recent_participations = [
            SupplierTenderParticipation(
                tender_id=r.tender_id,
                title=r.title,
                procuring_entity=r.procuring_entity,
                bid_amount_mkd=r.bid_amount_mkd,
                rank=r.rank,
                is_winner=r.is_winner or False,
                status=r.status,
                closing_date=r.closing_date
            )
            for r in part_rows
        ]

        # Get wins by category
        category_query = text("""
            SELECT t.category, COUNT(*) as win_count
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            JOIN suppliers s ON tb.company_name = s.company_name
            WHERE s.supplier_id = :supplier_id AND tb.is_winner = TRUE
            GROUP BY t.category
        """)
        cat_result = await db.execute(category_query, {"supplier_id": supplier_id})
        response.wins_by_category = {r.category or 'unknown': r.win_count for r in cat_result}

        # Get wins by entity
        entity_query = text("""
            SELECT t.procuring_entity, COUNT(*) as win_count
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            JOIN suppliers s ON tb.company_name = s.company_name
            WHERE s.supplier_id = :supplier_id AND tb.is_winner = TRUE
            GROUP BY t.procuring_entity
            ORDER BY win_count DESC
            LIMIT 10
        """)
        entity_result = await db.execute(entity_query, {"supplier_id": supplier_id})
        response.wins_by_entity = {r.procuring_entity: r.win_count for r in entity_result}

    return response
