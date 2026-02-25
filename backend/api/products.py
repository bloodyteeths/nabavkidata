"""
Product Search API endpoints
Provides search and browse capabilities for product items extracted from tender documents
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, select, and_, or_
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, timedelta
import logging

from database import get_db
from models import ProductItem, Tender, User
from middleware.entitlements import require_module, check_price_view_quota
from middleware.rbac import get_optional_user
from config.plans import ModuleName, has_module_access
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

# Sort options mapping
SORT_MAP = {
    "date_desc": "t.opening_date DESC NULLS LAST, p.name",
    "date_asc": "t.opening_date ASC NULLS LAST, p.name",
    "price_asc": "p.unit_price ASC NULLS LAST, p.name",
    "price_desc": "p.unit_price DESC NULLS LAST, p.name",
    "quantity_desc": "p.quantity DESC NULLS LAST, p.name",
    "relevance": "CASE WHEN p.unit_price > 0 THEN 0 ELSE 1 END, t.opening_date DESC NULLS LAST",
}

# Quality filters: exclude junk extractions
QUALITY_FILTER = """
    AND p.extraction_confidence >= 0.5
    AND LENGTH(p.name) >= 5
    AND p.name NOT LIKE '3.%'
    AND p.name NOT LIKE '1.%'
    AND p.name NOT LIKE '2.%'
"""

# In-memory cache for stats
_stats_cache = {"data": None, "expires": None}


async def _check_prices(user: Optional[User], db: AsyncSession) -> dict:
    """Check price view quota for user. Returns quota info dict."""
    return await check_price_view_quota(user, db, increment=True)


@router.get("/search")
async def search_products(
    q: Optional[str] = Query(None, max_length=500, description="Search query (optional for browse mode)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    cpv_code: Optional[str] = Query(None, description="Filter by CPV code prefix"),
    min_price: Optional[float] = Query(None, description="Minimum unit price"),
    max_price: Optional[float] = Query(None, description="Maximum unit price"),
    procuring_entity: Optional[str] = Query(None, description="Filter by procuring entity"),
    sort_by: Optional[str] = Query("relevance", description="Sort: relevance, date_desc, date_asc, price_asc, price_desc, quantity_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Search or browse products across all tender documents.

    Can be used in two modes:
    - Search mode: provide q parameter to search by product name
    - Browse mode: provide cpv_code to browse products by category

    At least one of q or cpv_code must be provided.
    """
    if not q and not cpv_code:
        raise HTTPException(status_code=400, detail="At least q or cpv_code must be provided")

    offset = (page - 1) * page_size

    # Build dynamic WHERE clause
    where_clauses = []
    params = {"limit": page_size, "offset": offset}

    if q:
        # Use full-text search with ILIKE fallback
        where_clauses.append("""(
            p.search_vector @@ plainto_tsquery('simple', :search_term)
            OR p.name ILIKE :name_pattern
        )""")
        params["search_term"] = q
        params["name_pattern"] = f"%{q}%"

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

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    # Server-side sorting
    order_clause = SORT_MAP.get(sort_by, SORT_MAP["relevance"])

    # Single query with COUNT(*) OVER() to get total + results in one pass
    # Quality filter excludes junk extractions (low confidence, numbered clauses)
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
            t.winner,
            COUNT(*) OVER() as total_count
        FROM product_items p
        JOIN tenders t ON p.tender_id = t.tender_id
        WHERE {where_sql}
            {QUALITY_FILTER}
        ORDER BY {order_clause}
        LIMIT :limit OFFSET :offset
    """)

    # Fix 9: Price summary aggregate query (runs in parallel with main query)
    price_summary_query = text(f"""
        SELECT
            COUNT(*) FILTER (WHERE p.unit_price > 0) as items_with_price,
            MIN(p.unit_price) FILTER (WHERE p.unit_price > 0) as min_price,
            MAX(p.unit_price) FILTER (WHERE p.unit_price > 0 AND p.unit_price < 100000000) as max_price,
            AVG(p.unit_price) FILTER (WHERE p.unit_price > 0 AND p.unit_price < 100000000) as avg_price,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.unit_price)
                FILTER (WHERE p.unit_price > 0 AND p.unit_price < 100000000) as median_price,
            MIN(p.unit) as common_unit
        FROM product_items p
        JOIN tenders t ON p.tender_id = t.tender_id
        WHERE {where_sql}
            {QUALITY_FILTER}
            AND p.extraction_confidence >= 0.6
    """)

    try:
        # Check price view quota (rate-limited per tier)
        quota = await _check_prices(current_user, db)
        has_prices = quota["has_quota"]

        result = await db.execute(search_query, params)
        rows = result.fetchall()

        total = rows[0].total_count if rows else 0

        items = []
        for row in rows:
            items.append(ProductSearchResult(
                id=row.id,
                name=row.name,
                quantity=row.quantity,
                unit=row.unit,
                unit_price=row.unit_price if has_prices else None,
                total_price=row.total_price if has_prices else None,
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

        # Build price summary (only for users with price access)
        price_summary = None
        if has_prices:
            price_result = await db.execute(price_summary_query, params)
            price_row = price_result.fetchone()
            if price_row and price_row.items_with_price and price_row.items_with_price > 0:
                price_summary = {
                    "items_with_price": price_row.items_with_price,
                    "min_price": round(float(price_row.min_price), 2) if price_row.min_price else None,
                    "max_price": round(float(price_row.max_price), 2) if price_row.max_price else None,
                    "avg_price": round(float(price_row.avg_price), 2) if price_row.avg_price else None,
                    "median_price": round(float(price_row.median_price), 2) if price_row.median_price else None,
                    "common_unit": price_row.common_unit,
                }

        response = {
            "query": q or "",
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [item.dict() if hasattr(item, 'dict') else item.model_dump() for item in items],
            "price_summary": price_summary,
            "price_gated": not has_prices,
            "price_views_remaining": quota["remaining"],
            "price_views_limit": quota["limit"],
            "price_views_used": quota["used"],
        }
        return response

    except Exception as e:
        logger.error(f"Product search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/aggregate", response_model=ProductAggregationResponse,
            dependencies=[Depends(require_module(ModuleName.ANALYTICS))])
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


@router.get("/by-tender/{tender_number}/{tender_year}")
async def get_products_by_tender(
    tender_number: str,
    tender_year: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Get all product items for a specific tender"""
    quota = await _check_prices(current_user, db)
    has_prices = quota["has_quota"]
    tender_id = f"{tender_number}/{tender_year}"
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

    items = [
        ProductItemResponse(
            id=row.id,
            tender_id=row.tender_id,
            document_id=row.document_id,
            item_number=row.item_number,
            lot_number=row.lot_number,
            name=row.name,
            quantity=row.quantity,
            unit=row.unit,
            unit_price=row.unit_price if has_prices else None,
            total_price=row.total_price if has_prices else None,
            specifications=row.specifications,
            cpv_code=row.cpv_code,
            extraction_confidence=row.extraction_confidence,
            created_at=row.created_at
        )
        for row in rows
    ]

    return {
        "items": [item.dict() if hasattr(item, 'dict') else item.model_dump() for item in items],
        "price_gated": not has_prices,
        "price_views_remaining": quota["remaining"],
        "price_views_limit": quota["limit"],
        "price_views_used": quota["used"],
    }


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


@router.get("/top-names")
async def get_top_product_names(
    cpv_code: Optional[str] = Query(None, description="CPV division prefix to filter (e.g. '33')"),
    limit: int = Query(15, ge=1, le=30),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the most frequently occurring product names, optionally within a CPV division.

    Returns popular product names as clickable quick-filter chips.
    """
    where_clauses = [
        "name IS NOT NULL",
        "name != ''",
        "LENGTH(name) BETWEEN 3 AND 120",
        "name !~ '^[0-9]+\\.'",  # exclude legal clause text like "1.3. ..."
    ]
    params: dict = {"limit": limit}

    if cpv_code:
        where_clauses.append("cpv_code LIKE :cpv_prefix")
        params["cpv_prefix"] = f"{cpv_code}%"

    where_sql = " AND ".join(where_clauses)

    query = text(f"""
        SELECT name, COUNT(*) as cnt
        FROM product_items
        WHERE {where_sql}
        GROUP BY name
        ORDER BY cnt DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    return {
        "names": [{"name": row.name, "count": row.cnt} for row in rows]
    }


@router.get("/stats")
async def get_product_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get overall product statistics (available to all users)"""
    global _stats_cache

    # Return cached stats if fresh (15 minute TTL)
    if _stats_cache["data"] and _stats_cache["expires"] and _stats_cache["expires"] > datetime.now():
        return _stats_cache["data"]

    stats_query = text("""
        SELECT
            COUNT(*) as total_products,
            COUNT(DISTINCT tender_id) as tenders_with_products,
            COUNT(DISTINCT name) as unique_products,
            AVG(extraction_confidence) as avg_confidence,
            COUNT(unit_price) as with_unit_price,
            COUNT(total_price) as with_total_price,
            COUNT(CASE WHEN extraction_confidence >= 0.7 THEN 1 END) as high_confidence,
            COUNT(CASE WHEN extraction_confidence >= 0.7 AND (unit_price IS NOT NULL OR total_price IS NOT NULL) THEN 1 END) as high_conf_with_price,
            COUNT(DISTINCT CASE WHEN unit_price IS NOT NULL THEN tender_id END) as tenders_with_prices
        FROM product_items
    """)

    result = await db.execute(stats_query)
    row = result.fetchone()

    data = {
        "total_products": row.total_products or 0,
        "tenders_with_products": row.tenders_with_products or 0,
        "unique_products": row.unique_products or 0,
        "avg_confidence": float(row.avg_confidence) if row.avg_confidence else None,
        "with_unit_price": row.with_unit_price or 0,
        "with_total_price": row.with_total_price or 0,
        "high_confidence": row.high_confidence or 0,
        "high_conf_with_price": row.high_conf_with_price or 0,
        "tenders_with_prices": row.tenders_with_prices or 0,
    }

    _stats_cache = {"data": data, "expires": datetime.now() + timedelta(minutes=15)}
    return data
