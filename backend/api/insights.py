"""
Insights API endpoints
Business intelligence and market analysis for the Trends/Insights page
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, desc
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, date, timedelta

from database import get_db
from models import Tender, TenderBidder, ProcuringEntity

router = APIRouter(prefix="/insights", tags=["insights"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class UpcomingOpportunityItem(BaseModel):
    """Single upcoming opportunity"""
    tender_id: str
    title: str
    estimated_value_mkd: Optional[float]
    closing_date: Optional[date]
    days_left: int
    category: Optional[str]
    procuring_entity: Optional[str]
    cpv_code: Optional[str]


class UpcomingOpportunitiesResponse(BaseModel):
    """Grouped upcoming opportunities by urgency"""
    closing_soon: List[UpcomingOpportunityItem]  # 0-7 days
    closing_this_month: List[UpcomingOpportunityItem]  # 8-14 days
    upcoming: List[UpcomingOpportunityItem]  # 15-30 days
    total: int


class TopWinnerItem(BaseModel):
    """Top winner statistics"""
    name: str
    win_count: int
    total_value_won: Optional[float]
    avg_contract_value: Optional[float]
    categories: List[str]


class TopWinnersResponse(BaseModel):
    """Top 20 winners"""
    winners: List[TopWinnerItem]
    total: int


class PriceBenchmarkItem(BaseModel):
    """Price benchmark for a CPV division"""
    cpv_division: str
    cpv_division_name: Optional[str]
    avg_value: Optional[float]
    median_value: Optional[float]
    min_value: Optional[float]
    max_value: Optional[float]
    tender_count: int


class PriceBenchmarksResponse(BaseModel):
    """Price benchmarks by category"""
    category: str
    benchmarks: List[PriceBenchmarkItem]
    total_divisions: int


class ActiveBuyerItem(BaseModel):
    """Active buyer/institution statistics"""
    entity_name: str
    tender_count: int
    total_value: Optional[float]
    categories_breakdown: dict


class ActiveBuyersResponse(BaseModel):
    """Top 20 most active buyers"""
    buyers: List[ActiveBuyerItem]
    total: int


class SeasonalPatternItem(BaseModel):
    """Seasonal pattern data point"""
    month: str  # YYYY-MM format
    month_name: str  # e.g., "January 2025"
    tender_count: int
    total_value: Optional[float]
    avg_value: Optional[float]
    category_breakdown: dict


class SeasonalPatternsResponse(BaseModel):
    """Seasonal patterns over last 12 months"""
    patterns: List[SeasonalPatternItem]
    total_months: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/upcoming-opportunities", response_model=UpcomingOpportunitiesResponse)
async def get_upcoming_opportunities(
    cpv_prefix: Optional[str] = Query(None, description="Filter by CPV code prefix (e.g., '45' for construction)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get upcoming opportunities grouped by urgency

    Returns tenders closing in next 30 days, grouped by time remaining:
    - closing_soon: 0-7 days
    - closing_this_month: 8-14 days
    - upcoming: 15-30 days
    """
    today = date.today()
    cutoff_30d = today + timedelta(days=30)

    # Build query
    query = select(
        Tender.tender_id,
        Tender.title,
        Tender.estimated_value_mkd,
        Tender.closing_date,
        Tender.category,
        Tender.procuring_entity,
        Tender.cpv_code
    ).where(
        and_(
            Tender.closing_date.isnot(None),
            Tender.closing_date >= today,
            Tender.closing_date <= cutoff_30d,
            Tender.status.in_(['open', 'active', 'Активен'])
        )
    )

    # Optional CPV filter
    if cpv_prefix:
        query = query.where(Tender.cpv_code.like(f"{cpv_prefix}%"))

    query = query.order_by(Tender.closing_date.asc())

    result = await db.execute(query)
    tenders = result.all()

    # Group by urgency
    closing_soon = []
    closing_this_month = []
    upcoming = []

    for t in tenders:
        if not t.closing_date:
            continue

        days_left = (t.closing_date - today).days

        item = UpcomingOpportunityItem(
            tender_id=t.tender_id,
            title=t.title,
            estimated_value_mkd=float(t.estimated_value_mkd) if t.estimated_value_mkd else None,
            closing_date=t.closing_date,
            days_left=days_left,
            category=t.category,
            procuring_entity=t.procuring_entity,
            cpv_code=t.cpv_code
        )

        if days_left <= 7:
            closing_soon.append(item)
        elif days_left <= 14:
            closing_this_month.append(item)
        else:
            upcoming.append(item)

    return UpcomingOpportunitiesResponse(
        closing_soon=closing_soon,
        closing_this_month=closing_this_month,
        upcoming=upcoming,
        total=len(tenders)
    )


@router.get("/top-winners", response_model=TopWinnersResponse)
async def get_top_winners(
    cpv_prefix: Optional[str] = Query(None, description="Filter by CPV code prefix"),
    limit: int = Query(20, ge=1, le=100, description="Number of top winners to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get top winners by contract count and value

    Analyzes awarded tenders to find companies that win most frequently.
    Returns winner name, win count, total value won, and categories.
    """
    # Query top winners from tender_bidders table
    cpv_filter = ""
    if cpv_prefix:
        cpv_filter = "AND t.cpv_code LIKE :cpv_pattern"

    query = text(f"""
        WITH winner_stats AS (
            SELECT
                tb.company_name,
                COUNT(DISTINCT tb.tender_id) as win_count,
                SUM(tb.bid_amount_mkd) as total_value_won,
                AVG(tb.bid_amount_mkd) as avg_contract_value,
                ARRAY_AGG(DISTINCT t.category) FILTER (WHERE t.category IS NOT NULL) as categories
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.is_winner = true
                AND t.status IN ('awarded', 'Доделен', 'contracted', 'Склучен договор')
                {cpv_filter}
            GROUP BY tb.company_name
            HAVING COUNT(DISTINCT tb.tender_id) > 0
        )
        SELECT
            company_name,
            win_count,
            total_value_won,
            avg_contract_value,
            categories
        FROM winner_stats
        ORDER BY win_count DESC, total_value_won DESC NULLS LAST
        LIMIT :limit
    """)

    params: dict = {"limit": limit}
    if cpv_prefix:
        params["cpv_pattern"] = f"{cpv_prefix}%"

    result = await db.execute(query, params)
    rows = result.fetchall()

    winners = [
        TopWinnerItem(
            name=row.company_name,
            win_count=row.win_count,
            total_value_won=float(row.total_value_won) if row.total_value_won else None,
            avg_contract_value=float(row.avg_contract_value) if row.avg_contract_value else None,
            categories=row.categories or []
        )
        for row in rows
    ]

    return TopWinnersResponse(
        winners=winners,
        total=len(winners)
    )


@router.get("/price-benchmarks", response_model=PriceBenchmarksResponse)
async def get_price_benchmarks(
    category: str = Query(..., description="Category: Стоки, Услуги, or Работи"),
    cpv_prefix: Optional[str] = Query(None, description="Filter by CPV code prefix"),
    limit: int = Query(10, ge=1, le=50, description="Number of top CPV divisions"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get price benchmarks by CPV division

    For each category (Стоки/Goods, Услуги/Services, Работи/Works),
    calculates average, median, min, max values grouped by CPV division
    (first 2 digits of CPV code).
    """
    # Query price statistics by CPV division
    cpv_filter = ""
    if cpv_prefix:
        cpv_filter = "AND cpv_code LIKE :cpv_pattern"

    query = text(f"""
        WITH cpv_stats AS (
            SELECT
                SUBSTRING(cpv_code FROM 1 FOR 2) as cpv_division,
                estimated_value_mkd
            FROM tenders
            WHERE category = :category
                AND cpv_code IS NOT NULL
                AND estimated_value_mkd IS NOT NULL
                AND estimated_value_mkd > 0
                {cpv_filter}
        )
        SELECT
            cpv_division,
            COUNT(*) as tender_count,
            AVG(estimated_value_mkd) as avg_value,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY estimated_value_mkd) as median_value,
            MIN(estimated_value_mkd) as min_value,
            MAX(estimated_value_mkd) as max_value
        FROM cpv_stats
        WHERE cpv_division ~ '^[0-9]{{2}}$'
        GROUP BY cpv_division
        HAVING COUNT(*) >= 3
        ORDER BY tender_count DESC
        LIMIT :limit
    """)

    params: dict = {"category": category, "limit": limit}
    if cpv_prefix:
        params["cpv_pattern"] = f"{cpv_prefix}%"

    result = await db.execute(query, params)
    rows = result.fetchall()

    # CPV division name mapping (first 2 digits)
    cpv_divisions = {
        "03": "Agricultural products",
        "09": "Petroleum products, fuel, electricity",
        "14": "Mining products",
        "15": "Food, beverages, tobacco",
        "18": "Clothing, footwear",
        "22": "Printed matter and related products",
        "24": "Chemical products",
        "30": "Office and computing machinery",
        "31": "Electrical machinery and apparatus",
        "32": "Radio, television and communication equipment",
        "33": "Medical equipment and pharmaceuticals",
        "34": "Transport equipment and auxiliary products",
        "35": "Security and defence equipment",
        "37": "Musical instruments and sports goods",
        "38": "Laboratory and optical equipment",
        "39": "Furniture and miscellaneous equipment",
        "41": "Collected and purified water",
        "42": "Industrial machinery",
        "43": "Mining machinery",
        "44": "Construction structures and materials",
        "45": "Construction work",
        "48": "Software package and information systems",
        "50": "Repair and maintenance services",
        "51": "Installation services",
        "55": "Hotel, restaurant and retail trade services",
        "60": "Transport services",
        "63": "Supporting transport services and travel agencies",
        "64": "Postal and telecommunications services",
        "65": "Public utilities",
        "66": "Financial and insurance services",
        "70": "Real estate services",
        "71": "Architectural and engineering services",
        "72": "IT services",
        "73": "Research and development services",
        "75": "Administration and defence services",
        "76": "Services related to the oil and gas industry",
        "77": "Agricultural and forestry services",
        "79": "Business services",
        "80": "Education and training services",
        "85": "Health and social work services",
        "90": "Sewage, refuse and cleaning services",
        "92": "Recreational, cultural and sporting services",
        "98": "Other community and social services"
    }

    benchmarks = [
        PriceBenchmarkItem(
            cpv_division=row.cpv_division,
            cpv_division_name=cpv_divisions.get(row.cpv_division, f"Division {row.cpv_division}"),
            avg_value=float(row.avg_value) if row.avg_value else None,
            median_value=float(row.median_value) if row.median_value else None,
            min_value=float(row.min_value) if row.min_value else None,
            max_value=float(row.max_value) if row.max_value else None,
            tender_count=row.tender_count
        )
        for row in rows
    ]

    return PriceBenchmarksResponse(
        category=category,
        benchmarks=benchmarks,
        total_divisions=len(benchmarks)
    )


@router.get("/active-buyers", response_model=ActiveBuyersResponse)
async def get_active_buyers(
    category: Optional[str] = Query(None, description="Filter by category"),
    days: int = Query(90, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(20, ge=1, le=100, description="Number of top buyers"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get most active procuring entities

    Returns top institutions by tender count in the specified period.
    Includes tender count, total value, and category breakdown.
    """
    cutoff_date = date.today() - timedelta(days=days)

    # Query active buyers
    category_filter = ""
    if category:
        category_filter = "AND category = :category"

    query = text(f"""
        SELECT
            procuring_entity,
            COUNT(*) as tender_count,
            SUM(estimated_value_mkd) as total_value,
            JSONB_OBJECT_AGG(
                COALESCE(category, 'unknown'),
                category_count
            ) as categories_breakdown
        FROM (
            SELECT
                procuring_entity,
                estimated_value_mkd,
                category,
                COUNT(*) OVER (PARTITION BY procuring_entity, category) as category_count
            FROM tenders
            WHERE procuring_entity IS NOT NULL
                AND opening_date >= :cutoff_date
                {category_filter}
        ) t
        GROUP BY procuring_entity
        HAVING COUNT(*) > 0
        ORDER BY tender_count DESC, total_value DESC NULLS LAST
        LIMIT :limit
    """)

    params: dict = {"cutoff_date": cutoff_date, "limit": limit}
    if category:
        params["category"] = category

    result = await db.execute(query, params)
    rows = result.fetchall()

    buyers = [
        ActiveBuyerItem(
            entity_name=row.procuring_entity,
            tender_count=row.tender_count,
            total_value=float(row.total_value) if row.total_value else None,
            categories_breakdown=row.categories_breakdown or {}
        )
        for row in rows
    ]

    return ActiveBuyersResponse(
        buyers=buyers,
        total=len(buyers)
    )


@router.get("/seasonal-patterns", response_model=SeasonalPatternsResponse)
async def get_seasonal_patterns(
    category: Optional[str] = Query(None, description="Filter by category"),
    months: int = Query(12, ge=1, le=24, description="Number of months to analyze"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get seasonal patterns by month

    Shows which months have the most tender activity by category.
    Uses closing_date or opening_date (NOT created_at) for accurate seasonality.
    Returns last N months of data.
    """
    # Build query dynamically to avoid NULL type inference issues
    category_filter = ""
    if category:
        category_filter = "AND category = :category"

    query = text(f"""
        WITH monthly_data AS (
            SELECT
                DATE_TRUNC('month', COALESCE(closing_date, opening_date)) as month,
                category,
                estimated_value_mkd
            FROM tenders
            WHERE COALESCE(closing_date, opening_date) IS NOT NULL
                AND COALESCE(closing_date, opening_date) >= NOW() - INTERVAL '1 month' * :months
                {category_filter}
        )
        SELECT
            TO_CHAR(month, 'YYYY-MM') as month_key,
            TO_CHAR(month, 'Month YYYY') as month_name,
            COUNT(*) as tender_count,
            SUM(estimated_value_mkd) as total_value,
            AVG(estimated_value_mkd) as avg_value,
            JSONB_OBJECT_AGG(
                COALESCE(category, 'unknown'),
                category_count
            ) as category_breakdown
        FROM (
            SELECT
                month,
                estimated_value_mkd,
                category,
                COUNT(*) OVER (PARTITION BY month, category) as category_count
            FROM monthly_data
        ) t
        GROUP BY month
        ORDER BY month DESC
    """)

    params: dict = {"months": months}
    if category:
        params["category"] = category

    result = await db.execute(query, params)
    rows = result.fetchall()

    patterns = [
        SeasonalPatternItem(
            month=row.month_key,
            month_name=row.month_name.strip(),
            tender_count=row.tender_count,
            total_value=float(row.total_value) if row.total_value else None,
            avg_value=float(row.avg_value) if row.avg_value else None,
            category_breakdown=row.category_breakdown or {}
        )
        for row in rows
    ]

    return SeasonalPatternsResponse(
        patterns=patterns,
        total_months=len(patterns)
    )
