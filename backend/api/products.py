"""
Product Search API endpoints
Provides search capabilities for product items extracted from tender documents
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, select, and_, or_
from typing import Optional, List
from decimal import Decimal
import logging

from database import get_db
from models import ProductItem, Tender
from schemas import (
    ProductSearchRequest,
    ProductSearchResponse,
    ProductSearchResult,
    ProductItemResponse,
    ProductAggregationResponse,
    ProductAggregation
)

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)


@router.get("/search", response_model=ProductSearchResponse)
async def search_products(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    year: Optional[int] = Query(None, description="Filter by year"),
    cpv_code: Optional[str] = Query(None, description="Filter by CPV code prefix"),
    min_price: Optional[float] = Query(None, description="Minimum unit price"),
    max_price: Optional[float] = Query(None, description="Maximum unit price"),
    procuring_entity: Optional[str] = Query(None, description="Filter by procuring entity"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for products across all tender documents.

    This endpoint allows searching for specific products like:
    - "paracetamol" - Find all paracetamol purchases
    - "intraocular lens" - Find intraocular lens procurements
    - "medical equipment" - Find medical equipment tenders

    Returns product items with their tender context including procuring entity,
    quantities, prices, and specifications.
    """
    offset = (page - 1) * page_size

    # Build dynamic WHERE clause based on provided filters
    where_clauses = ["(p.name ILIKE :name_pattern OR p.raw_text ILIKE :name_pattern)"]
    params = {"name_pattern": f"%{q}%", "limit": page_size, "offset": offset}

    if year is not None:
        where_clauses.append("EXTRACT(YEAR FROM t.opening_date) = :year")
        params["year"] = year
    if cpv_code:
        where_clauses.append("p.cpv_code LIKE :cpv_pattern")
        params["cpv_pattern"] = f"{cpv_code}%"
    if min_price is not None:
        where_clauses.append("p.unit_price >= :min_price")
        params["min_price"] = min_price
    if max_price is not None:
        where_clauses.append("p.unit_price <= :max_price")
        params["max_price"] = max_price
    if procuring_entity:
        where_clauses.append("t.procuring_entity ILIKE :entity_pattern")
        params["entity_pattern"] = f"%{procuring_entity}%"

    where_sql = " AND ".join(where_clauses)

    search_query = text(f"""
        SELECT
            p.id,
            p.name,
            p.quantity,
            p.unit,
            p.unit_price,
            p.total_price,
            p.specifications,
            p.cpv_code,
            p.extraction_confidence,
            p.tender_id,
            t.title as tender_title,
            t.procuring_entity,
            t.opening_date,
            t.status,
            t.winner
        FROM product_items p
        JOIN tenders t ON p.tender_id = t.tender_id
        WHERE {where_sql}
        ORDER BY t.opening_date DESC NULLS LAST, p.name
        LIMIT :limit OFFSET :offset
    """)

    count_query = text(f"""
        SELECT COUNT(*)
        FROM product_items p
        JOIN tenders t ON p.tender_id = t.tender_id
        WHERE {where_sql}
    """)

    try:
        # Get total count
        count_result = await db.execute(count_query, params)
        total = count_result.scalar() or 0

        # Get results
        result = await db.execute(search_query, params)
        rows = result.fetchall()

        items = []
        for row in rows:
            items.append(ProductSearchResult(
                id=row.id,
                name=row.name,
                quantity=row.quantity,
                unit=row.unit,
                unit_price=row.unit_price,
                total_price=row.total_price,
                specifications=row.specifications,
                cpv_code=row.cpv_code,
                extraction_confidence=row.extraction_confidence,
                tender_id=row.tender_id,
                tender_title=row.tender_title,
                procuring_entity=row.procuring_entity,
                opening_date=row.opening_date,
                status=row.status,
                winner=row.winner
            ))

        return ProductSearchResponse(
            query=q,
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )

    except Exception as e:
        logger.error(f"Product search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/aggregate", response_model=ProductAggregationResponse)
async def aggregate_products(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated statistics for products matching the search query.

    Returns price ranges, total quantities, and tender counts grouped by product name.
    Useful for market analysis and price comparison.
    """
    agg_query = text("""
        SELECT
            p.name,
            SUM(p.quantity) as total_quantity,
            AVG(p.unit_price) as avg_unit_price,
            MIN(p.unit_price) as min_unit_price,
            MAX(p.unit_price) as max_unit_price,
            COUNT(DISTINCT p.tender_id) as tender_count,
            array_agg(DISTINCT EXTRACT(YEAR FROM t.opening_date)::int)
                FILTER (WHERE t.opening_date IS NOT NULL) as years
        FROM product_items p
        JOIN tenders t ON p.tender_id = t.tender_id
        WHERE p.name ILIKE :name_pattern
        GROUP BY p.name
        ORDER BY tender_count DESC
        LIMIT 50
    """)

    result = await db.execute(agg_query, {"name_pattern": f"%{q}%"})
    rows = result.fetchall()

    aggregations = []
    for row in rows:
        aggregations.append(ProductAggregation(
            product_name=row.name,
            total_quantity=row.total_quantity,
            avg_unit_price=row.avg_unit_price,
            min_unit_price=row.min_unit_price,
            max_unit_price=row.max_unit_price,
            tender_count=row.tender_count,
            years=sorted([y for y in (row.years or []) if y]) if row.years else []
        ))

    return ProductAggregationResponse(
        query=q,
        aggregations=aggregations
    )


@router.get("/by-tender/{tender_id}", response_model=List[ProductItemResponse])
async def get_products_by_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all product items for a specific tender"""
    query = text("""
        SELECT
            id, tender_id, document_id, item_number, lot_number,
            name, quantity, unit, unit_price, total_price,
            specifications, cpv_code, extraction_confidence, created_at
        FROM product_items
        WHERE tender_id = :tender_id
        ORDER BY lot_number NULLS LAST, item_number NULLS LAST, name
    """)

    result = await db.execute(query, {"tender_id": tender_id})
    rows = result.fetchall()

    return [
        ProductItemResponse(
            id=row.id,
            tender_id=row.tender_id,
            document_id=row.document_id,
            item_number=row.item_number,
            lot_number=row.lot_number,
            name=row.name,
            quantity=row.quantity,
            unit=row.unit,
            unit_price=row.unit_price,
            total_price=row.total_price,
            specifications=row.specifications,
            cpv_code=row.cpv_code,
            extraction_confidence=row.extraction_confidence,
            created_at=row.created_at
        )
        for row in rows
    ]


@router.get("/suggestions")
async def get_product_suggestions(
    q: str = Query(..., min_length=2, max_length=100, description="Partial query for suggestions"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get autocomplete suggestions for product names.

    Returns distinct product names that match the partial query.
    """
    query = text("""
        SELECT DISTINCT name
        FROM product_items
        WHERE name ILIKE :pattern
        ORDER BY name
        LIMIT :limit
    """)

    result = await db.execute(query, {"pattern": f"%{q}%", "limit": limit})
    rows = result.fetchall()

    return {"suggestions": [row.name for row in rows]}


@router.get("/stats")
async def get_product_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get overall product statistics"""
    stats_query = text("""
        SELECT
            COUNT(*) as total_products,
            COUNT(DISTINCT tender_id) as tenders_with_products,
            COUNT(DISTINCT name) as unique_products,
            AVG(extraction_confidence) as avg_confidence
        FROM product_items
    """)

    result = await db.execute(stats_query)
    row = result.fetchone()

    return {
        "total_products": row.total_products or 0,
        "tenders_with_products": row.tenders_with_products or 0,
        "unique_products": row.unique_products or 0,
        "avg_confidence": float(row.avg_confidence) if row.avg_confidence else None
    }
