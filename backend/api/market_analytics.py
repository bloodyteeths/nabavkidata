"""
Market Analytics API endpoints
Advanced market intelligence and competitor analysis
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from decimal import Decimal

from database import get_db
from models import User
from api.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["market-analytics"])


# ============================================================================
# TIER REQUIREMENTS
# ============================================================================

TIER_ACCESS = {
    "market-overview": ["free", "starter", "professional", "enterprise"],
    "competitor-analysis": ["starter", "professional", "enterprise"],
    "category-trends": ["free", "starter", "professional", "enterprise"],
    "supplier-strength": ["starter", "professional", "enterprise"]
}


def check_tier_access(endpoint: str, user: User) -> bool:
    """Check if user's tier has access to the endpoint"""
    tier = getattr(user, 'subscription_tier', 'free')
    if tier is None:
        tier = 'free'
    tier = tier.lower()
    allowed_tiers = TIER_ACCESS.get(endpoint, [])
    return tier in allowed_tiers


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class MarketOverviewResponse(BaseModel):
    total_tenders: int
    total_value_mkd: Optional[float]
    open_tenders: int
    closing_soon: int
    awarded_this_month: int
    avg_competition: Optional[float]
    top_categories: List[dict]
    top_entities: List[dict]
    value_distribution: dict
    monthly_trend: List[dict]
    generated_at: datetime


class CompetitorData(BaseModel):
    company_name: str
    total_bids: int
    total_wins: int
    win_rate: float
    total_value_won_mkd: Optional[float]
    avg_bid_amount: Optional[float]
    categories: List[str]
    recent_wins: List[dict]


class CompetitorAnalysisResponse(BaseModel):
    period: str
    competitors: List[CompetitorData]
    market_comparison: dict
    head_to_head: Optional[dict]
    generated_at: datetime


class CategoryTrendData(BaseModel):
    category: str
    tender_count: int
    total_value_mkd: Optional[float]
    avg_value_mkd: Optional[float]
    growth_rate: Optional[float]
    avg_competition: Optional[float]
    top_winners: List[dict]
    monthly_trend: List[dict]


class CategoryTrendsResponse(BaseModel):
    period: str
    categories: List[CategoryTrendData]
    generated_at: datetime


class SupplierStrengthResponse(BaseModel):
    supplier_id: str
    company_name: str
    strength_score: float
    metrics: dict
    rankings: dict
    trends: dict
    recent_activity: List[dict]
    generated_at: datetime


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_period_start(period: str) -> datetime:
    """Convert period string to start date"""
    now = datetime.utcnow()
    period_days = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "6m": 180,
        "1y": 365,
        "all": 3650
    }
    days = period_days.get(period, 365)
    return now - timedelta(days=days)


# ============================================================================
# MARKET OVERVIEW
# ============================================================================

@router.get("/market-overview", response_model=MarketOverviewResponse)
async def get_market_overview(
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive market overview dashboard.

    Returns:
    - Total tenders and value
    - Open and closing soon counts
    - Average competition (bidders per tender)
    - Top categories and entities
    - Value distribution
    - Monthly trend (last 12 months)

    Public endpoint - no authentication required.
    """
    now = datetime.utcnow()
    week_from_now = now + timedelta(days=7)
    month_start = now.replace(day=1)

    # Get totals
    totals_query = text("""
        SELECT
            COUNT(*) as total_tenders,
            COALESCE(SUM(estimated_value_mkd), 0) as total_value,
            COUNT(*) FILTER (WHERE status = 'open' AND closing_date >= CURRENT_DATE) as open_tenders,
            COUNT(*) FILTER (WHERE status = 'open' AND closing_date >= CURRENT_DATE AND closing_date <= :week_from_now) as closing_soon,
            COUNT(*) FILTER (WHERE status = 'awarded' AND opening_date >= :month_start) as awarded_this_month,
            AVG(num_bidders) FILTER (WHERE num_bidders > 0) as avg_competition
        FROM tenders
    """)

    totals_result = await db.execute(totals_query, {
        "week_from_now": week_from_now.date(),
        "month_start": month_start.date()
    })
    totals = totals_result.fetchone()

    # Top categories
    categories_query = text("""
        SELECT category, COUNT(*) as count, SUM(estimated_value_mkd) as value
        FROM tenders
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    categories_result = await db.execute(categories_query)
    top_categories = [
        {"category": row.category, "count": row.count, "value": float(row.value) if row.value else None}
        for row in categories_result.fetchall()
    ]

    # Top entities
    entities_query = text("""
        SELECT procuring_entity, COUNT(*) as count, SUM(estimated_value_mkd) as value
        FROM tenders
        WHERE procuring_entity IS NOT NULL
        GROUP BY procuring_entity
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    entities_result = await db.execute(entities_query)
    top_entities = [
        {"entity": row.procuring_entity, "count": row.count, "value": float(row.value) if row.value else None}
        for row in entities_result.fetchall()
    ]

    # Value distribution
    value_dist_query = text("""
        SELECT
            COUNT(*) FILTER (WHERE estimated_value_mkd < 100000) as under_100k,
            COUNT(*) FILTER (WHERE estimated_value_mkd >= 100000 AND estimated_value_mkd < 500000) as "100k_500k",
            COUNT(*) FILTER (WHERE estimated_value_mkd >= 500000 AND estimated_value_mkd < 1000000) as "500k_1m",
            COUNT(*) FILTER (WHERE estimated_value_mkd >= 1000000 AND estimated_value_mkd < 5000000) as "1m_5m",
            COUNT(*) FILTER (WHERE estimated_value_mkd >= 5000000 AND estimated_value_mkd < 10000000) as "5m_10m",
            COUNT(*) FILTER (WHERE estimated_value_mkd >= 10000000) as over_10m
        FROM tenders
        WHERE estimated_value_mkd IS NOT NULL
    """)
    value_dist_result = await db.execute(value_dist_query)
    dist_row = value_dist_result.fetchone()
    value_distribution = {
        "under_100k": dist_row.under_100k,
        "100k_500k": dist_row._mapping["100k_500k"],
        "500k_1m": dist_row._mapping["500k_1m"],
        "1m_5m": dist_row._mapping["1m_5m"],
        "5m_10m": dist_row._mapping["5m_10m"],
        "over_10m": dist_row.over_10m
    }

    # Monthly trend (last 12 months)
    trend_query = text("""
        SELECT
            date_trunc('month', opening_date) as month,
            COUNT(*) as count,
            SUM(estimated_value_mkd) as value
        FROM tenders
        WHERE opening_date >= NOW() - INTERVAL '12 months'
          AND opening_date IS NOT NULL
        GROUP BY date_trunc('month', opening_date)
        ORDER BY month
    """)
    trend_result = await db.execute(trend_query)
    monthly_trend = [
        {
            "month": row.month.strftime("%Y-%m") if row.month else None,
            "count": row.count,
            "value": float(row.value) if row.value else None
        }
        for row in trend_result.fetchall()
    ]

    return MarketOverviewResponse(
        total_tenders=totals.total_tenders or 0,
        total_value_mkd=float(totals.total_value) if totals.total_value else None,
        open_tenders=totals.open_tenders or 0,
        closing_soon=totals.closing_soon or 0,
        awarded_this_month=totals.awarded_this_month or 0,
        avg_competition=float(totals.avg_competition) if totals.avg_competition else None,
        top_categories=top_categories,
        top_entities=top_entities,
        value_distribution=value_distribution,
        monthly_trend=monthly_trend,
        generated_at=datetime.utcnow()
    )


# ============================================================================
# COMPETITOR ANALYSIS
# ============================================================================

@router.get("/competitor-analysis", response_model=CompetitorAnalysisResponse)
async def get_competitor_analysis(
    competitors: str = Query(..., description="Comma-separated list of competitor company names"),
    period: str = Query("1y", description="Period: 30d, 90d, 6m, 1y, all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze competitors' tender performance.

    Parameters:
    - competitors: Comma-separated company names
    - period: Time period for analysis

    Returns detailed bidding statistics, win rates, and head-to-head comparison.

    Requires Starter+ tier.
    """
    if not check_tier_access("competitor-analysis", current_user):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Competitor analysis requires Starter tier or higher",
                "current_tier": getattr(current_user, 'subscription_tier', 'free'),
                "upgrade_url": "/pricing"
            }
        )

    # Parse competitor names
    competitor_list = [c.strip() for c in competitors.split(",") if c.strip()]
    if not competitor_list:
        raise HTTPException(status_code=400, detail="At least one competitor name required")

    if len(competitor_list) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 competitors allowed")

    start_date = get_period_start(period)

    # Get competitor statistics
    competitor_data = []
    for company_name in competitor_list:
        stats_query = text("""
            SELECT
                tb.company_name,
                COUNT(*) as total_bids,
                COUNT(*) FILTER (WHERE tb.is_winner) as total_wins,
                AVG(tb.bid_amount_mkd) as avg_bid,
                SUM(tb.bid_amount_mkd) FILTER (WHERE tb.is_winner) as value_won,
                array_agg(DISTINCT t.category) FILTER (WHERE t.category IS NOT NULL) as categories
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_name ILIKE :company_name
              AND t.opening_date >= :start_date
            GROUP BY tb.company_name
        """)

        result = await db.execute(stats_query, {
            "company_name": f"%{company_name}%",
            "start_date": start_date.date()
        })
        row = result.fetchone()

        if row and row.total_bids > 0:
            # Get recent wins
            wins_query = text("""
                SELECT t.tender_id, t.title, t.procuring_entity, t.actual_value_mkd, t.closing_date
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE tb.company_name ILIKE :company_name
                  AND tb.is_winner = TRUE
                  AND t.opening_date >= :start_date
                ORDER BY t.closing_date DESC
                LIMIT 5
            """)
            wins_result = await db.execute(wins_query, {
                "company_name": f"%{company_name}%",
                "start_date": start_date.date()
            })
            recent_wins = [
                {
                    "tender_id": w.tender_id,
                    "title": w.title,
                    "entity": w.procuring_entity,
                    "value": float(w.actual_value_mkd) if w.actual_value_mkd else None,
                    "date": w.closing_date.isoformat() if w.closing_date else None
                }
                for w in wins_result.fetchall()
            ]

            win_rate = (row.total_wins / row.total_bids * 100) if row.total_bids > 0 else 0

            competitor_data.append(CompetitorData(
                company_name=row.company_name,
                total_bids=row.total_bids,
                total_wins=row.total_wins,
                win_rate=round(win_rate, 2),
                total_value_won_mkd=float(row.value_won) if row.value_won else None,
                avg_bid_amount=float(row.avg_bid) if row.avg_bid else None,
                categories=row.categories if row.categories else [],
                recent_wins=recent_wins
            ))

    # Market comparison
    market_query = text("""
        SELECT
            COUNT(DISTINCT tb.company_name) as total_bidders,
            AVG(win_rate) as market_avg_win_rate
        FROM (
            SELECT
                company_name,
                COUNT(*) FILTER (WHERE is_winner)::float / NULLIF(COUNT(*), 0) * 100 as win_rate
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE t.opening_date >= :start_date
            GROUP BY company_name
        ) sub
    """)
    market_result = await db.execute(market_query, {"start_date": start_date.date()})
    market_row = market_result.fetchone()

    market_comparison = {
        "total_market_bidders": market_row.total_bidders if market_row else 0,
        "market_avg_win_rate": round(float(market_row.market_avg_win_rate), 2) if market_row and market_row.market_avg_win_rate else 0
    }

    # Head-to-head comparison (if multiple competitors)
    head_to_head = None
    if len(competitor_data) >= 2:
        head_to_head = {
            "highest_win_rate": max(competitor_data, key=lambda x: x.win_rate).company_name,
            "most_bids": max(competitor_data, key=lambda x: x.total_bids).company_name,
            "highest_value": max(competitor_data, key=lambda x: x.total_value_won_mkd or 0).company_name
        }

    return CompetitorAnalysisResponse(
        period=period,
        competitors=competitor_data,
        market_comparison=market_comparison,
        head_to_head=head_to_head,
        generated_at=datetime.utcnow()
    )


# ============================================================================
# TOP MARKET COMPETITORS (no specific input required)
# ============================================================================

@router.get("/top-competitors")
async def get_top_competitors(
    period: str = Query("1y", description="Period: 30d, 90d, 6m, 1y, all"),
    limit: int = Query(20, ge=1, le=50, description="Number of competitors to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get top market competitors based on tender wins and participation.

    This endpoint automatically finds the most active bidders in the market
    without requiring specific competitor names.

    Requires Starter+ tier.
    """
    if not check_tier_access("competitor-analysis", current_user):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Competitor analysis requires Starter tier or higher",
                "current_tier": getattr(current_user, 'subscription_tier', 'free'),
                "upgrade_url": "/pricing"
            }
        )

    start_date = get_period_start(period)

    # Get top competitors by wins and bids
    query = text("""
        SELECT
            tb.company_name as name,
            COUNT(*) as bids_count,
            COUNT(*) FILTER (WHERE tb.is_winner) as wins,
            SUM(tb.bid_amount_mkd) FILTER (WHERE tb.is_winner) as total_value_mkd,
            ROUND(COUNT(*) FILTER (WHERE tb.is_winner)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as win_rate,
            array_agg(DISTINCT t.category) FILTER (WHERE t.category IS NOT NULL) as categories
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE t.opening_date >= :start_date
          AND tb.company_name IS NOT NULL AND tb.company_name != ''
        GROUP BY tb.company_name
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) FILTER (WHERE tb.is_winner) DESC, COUNT(*) DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {
        "start_date": start_date.date(),
        "limit": limit
    })
    rows = result.fetchall()

    competitors = []
    for row in rows:
        competitors.append({
            "name": row.name,
            "bids_count": row.bids_count,
            "wins": row.wins,
            "total_value_mkd": float(row.total_value_mkd) if row.total_value_mkd else 0,
            "win_rate": float(row.win_rate) if row.win_rate else 0,
            "categories": row.categories[:5] if row.categories else []
        })

    # Get market summary
    summary_query = text("""
        SELECT
            COUNT(DISTINCT tb.company_name) as total_bidders,
            COUNT(*) as total_bids,
            COUNT(*) FILTER (WHERE tb.is_winner) as total_awards,
            SUM(tb.bid_amount_mkd) FILTER (WHERE tb.is_winner) as total_awarded_value
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE t.opening_date >= :start_date
    """)
    summary_result = await db.execute(summary_query, {"start_date": start_date.date()})
    summary_row = summary_result.fetchone()

    summary = {
        "total_bidders": summary_row.total_bidders if summary_row else 0,
        "total_bids": summary_row.total_bids if summary_row else 0,
        "total_awards": summary_row.total_awards if summary_row else 0,
        "total_awarded_value_mkd": float(summary_row.total_awarded_value) if summary_row and summary_row.total_awarded_value else 0,
        "period": period
    }

    return {
        "competitors": competitors,
        "summary": summary,
        "generated_at": datetime.utcnow().isoformat()
    }


# ============================================================================
# CATEGORY TRENDS
# ============================================================================

@router.get("/category-trends", response_model=CategoryTrendsResponse)
async def get_category_trends(
    categories: Optional[str] = Query(None, description="Comma-separated category names (optional)"),
    period: str = Query("1y", description="Period: 30d, 90d, 6m, 1y, all"),
    limit: int = Query(20, ge=1, le=50, description="Number of categories to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get tender trends by category.

    Parameters:
    - categories: Optional filter for specific categories
    - period: Time period for analysis
    - limit: Max categories to return

    Returns category statistics, growth rates, and monthly trends.

    Public endpoint - no authentication required.
    """
    start_date = get_period_start(period)
    prev_period_start = start_date - (datetime.utcnow() - start_date)

    # Build category filter
    category_filter = ""
    params = {"start_date": start_date.date(), "prev_start": prev_period_start.date(), "limit": limit}

    if categories:
        category_list = [c.strip() for c in categories.split(",") if c.strip()]
        if category_list:
            category_filter = "AND category = ANY(:categories)"
            params["categories"] = category_list

    # Get category statistics
    query = text(f"""
        WITH current_period AS (
            SELECT
                category,
                COUNT(*) as tender_count,
                SUM(estimated_value_mkd) as total_value,
                AVG(estimated_value_mkd) as avg_value,
                AVG(num_bidders) FILTER (WHERE num_bidders > 0) as avg_competition
            FROM tenders
            WHERE category IS NOT NULL AND category != ''
              AND opening_date >= :start_date
              {category_filter}
            GROUP BY category
        ),
        prev_period AS (
            SELECT
                category,
                COUNT(*) as tender_count
            FROM tenders
            WHERE category IS NOT NULL AND category != ''
              AND opening_date >= :prev_start AND opening_date < :start_date
              {category_filter}
            GROUP BY category
        )
        SELECT
            c.category,
            c.tender_count,
            c.total_value,
            c.avg_value,
            c.avg_competition,
            CASE
                WHEN p.tender_count > 0
                THEN ((c.tender_count - p.tender_count)::float / p.tender_count * 100)
                ELSE NULL
            END as growth_rate
        FROM current_period c
        LEFT JOIN prev_period p ON c.category = p.category
        ORDER BY c.tender_count DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    categories_data = []
    for row in rows:
        # Get top winners for category
        winners_query = text("""
            SELECT winner, COUNT(*) as wins
            FROM tenders
            WHERE category = :category
              AND winner IS NOT NULL AND winner != ''
              AND opening_date >= :start_date
            GROUP BY winner
            ORDER BY wins DESC
            LIMIT 5
        """)
        winners_result = await db.execute(winners_query, {
            "category": row.category,
            "start_date": start_date.date()
        })
        top_winners = [
            {"company": w.winner, "wins": w.wins}
            for w in winners_result.fetchall()
        ]

        # Get monthly trend for category
        trend_query = text("""
            SELECT
                date_trunc('month', opening_date) as month,
                COUNT(*) as count,
                SUM(estimated_value_mkd) as value
            FROM tenders
            WHERE category = :category
              AND opening_date >= :start_date
            GROUP BY date_trunc('month', opening_date)
            ORDER BY month
        """)
        trend_result = await db.execute(trend_query, {
            "category": row.category,
            "start_date": start_date.date()
        })
        monthly_trend = [
            {
                "month": t.month.strftime("%Y-%m") if t.month else None,
                "count": t.count,
                "value": float(t.value) if t.value else None
            }
            for t in trend_result.fetchall()
        ]

        categories_data.append(CategoryTrendData(
            category=row.category,
            tender_count=row.tender_count,
            total_value_mkd=float(row.total_value) if row.total_value else None,
            avg_value_mkd=float(row.avg_value) if row.avg_value else None,
            growth_rate=round(float(row.growth_rate), 2) if row.growth_rate else None,
            avg_competition=float(row.avg_competition) if row.avg_competition else None,
            top_winners=top_winners,
            monthly_trend=monthly_trend
        ))

    return CategoryTrendsResponse(
        period=period,
        categories=categories_data,
        generated_at=datetime.utcnow()
    )


# ============================================================================
# SUPPLIER STRENGTH
# ============================================================================

@router.get("/supplier-strength/{supplier_id}", response_model=SupplierStrengthResponse)
async def get_supplier_strength(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate comprehensive supplier strength score.

    Returns:
    - Strength score (0-100)
    - Key performance metrics
    - Market rankings
    - Activity trends

    Requires Starter+ tier.
    """
    if not check_tier_access("supplier-strength", current_user):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Supplier strength analysis requires Starter tier or higher",
                "current_tier": getattr(current_user, 'subscription_tier', 'free'),
                "upgrade_url": "/pricing"
            }
        )

    import uuid
    try:
        uuid.UUID(supplier_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid supplier ID format")

    # Get supplier basic info
    supplier_query = text("""
        SELECT supplier_id, company_name, total_wins, total_bids, win_rate,
               total_contract_value_mkd, city, industries, created_at
        FROM suppliers
        WHERE supplier_id = :supplier_id
    """)
    supplier_result = await db.execute(supplier_query, {"supplier_id": supplier_id})
    supplier = supplier_result.fetchone()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Calculate metrics
    win_rate = float(supplier.win_rate) if supplier.win_rate else 0
    total_wins = supplier.total_wins or 0
    total_bids = supplier.total_bids or 0
    total_value = float(supplier.total_contract_value_mkd) if supplier.total_contract_value_mkd else 0

    # Category diversity
    diversity_query = text("""
        SELECT COUNT(DISTINCT t.category) as categories
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.supplier_id = :supplier_id
    """)
    diversity_result = await db.execute(diversity_query, {"supplier_id": supplier_id})
    category_diversity = diversity_result.scalar() or 0

    # Entity relationships
    entities_query = text("""
        SELECT COUNT(DISTINCT t.procuring_entity) as entities
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.supplier_id = :supplier_id AND tb.is_winner = TRUE
    """)
    entities_result = await db.execute(entities_query, {"supplier_id": supplier_id})
    entity_relationships = entities_result.scalar() or 0

    # Calculate strength score (0-100)
    score_components = {
        "win_rate": min(win_rate * 1.5, 30),  # Max 30 points
        "volume": min(total_wins * 2, 25),    # Max 25 points
        "value": min(total_value / 10000000, 20),  # Max 20 points for 10M+
        "diversity": min(category_diversity * 2, 15),  # Max 15 points
        "relationships": min(entity_relationships * 2, 10)  # Max 10 points
    }
    strength_score = min(sum(score_components.values()), 100)

    # Determine value tier
    if total_value >= 50000000:
        value_tier = "enterprise"
    elif total_value >= 10000000:
        value_tier = "large"
    elif total_value >= 1000000:
        value_tier = "medium"
    else:
        value_tier = "small"

    # Rankings
    overall_rank_query = text("""
        SELECT COUNT(*) + 1 as rank
        FROM suppliers
        WHERE total_contract_value_mkd > :value
    """)
    overall_rank_result = await db.execute(overall_rank_query, {"value": total_value})
    overall_rank = overall_rank_result.scalar() or 1

    city_rank_query = text("""
        SELECT COUNT(*) + 1 as rank
        FROM suppliers
        WHERE city = :city AND total_contract_value_mkd > :value
    """)
    city_rank_result = await db.execute(city_rank_query, {
        "city": supplier.city,
        "value": total_value
    })
    city_rank = city_rank_result.scalar() or 1

    # Trends (6m vs 12m win rate)
    trend_query = text("""
        SELECT
            COUNT(*) FILTER (WHERE t.opening_date >= NOW() - INTERVAL '6 months' AND tb.is_winner)::float /
                NULLIF(COUNT(*) FILTER (WHERE t.opening_date >= NOW() - INTERVAL '6 months'), 0) * 100 as win_rate_6m,
            COUNT(*) FILTER (WHERE t.opening_date >= NOW() - INTERVAL '12 months' AND tb.is_winner)::float /
                NULLIF(COUNT(*) FILTER (WHERE t.opening_date >= NOW() - INTERVAL '12 months'), 0) * 100 as win_rate_12m,
            COUNT(*) FILTER (WHERE t.opening_date >= NOW() - INTERVAL '6 months') as activity_6m,
            COUNT(*) FILTER (WHERE t.opening_date >= NOW() - INTERVAL '12 months' AND t.opening_date < NOW() - INTERVAL '6 months') as activity_prev_6m
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.supplier_id = :supplier_id
    """)
    trend_result = await db.execute(trend_query, {"supplier_id": supplier_id})
    trend_row = trend_result.fetchone()

    win_rate_6m = float(trend_row.win_rate_6m) if trend_row.win_rate_6m else 0
    win_rate_12m = float(trend_row.win_rate_12m) if trend_row.win_rate_12m else 0
    activity_6m = trend_row.activity_6m or 0
    activity_prev_6m = trend_row.activity_prev_6m or 0

    win_rate_trend = "stable"
    if win_rate_6m > win_rate_12m * 1.1:
        win_rate_trend = "improving"
    elif win_rate_6m < win_rate_12m * 0.9:
        win_rate_trend = "declining"

    activity_trend = "stable"
    if activity_6m > activity_prev_6m * 1.2:
        activity_trend = "increasing"
    elif activity_6m < activity_prev_6m * 0.8:
        activity_trend = "decreasing"

    # Recent activity
    activity_query = text("""
        SELECT t.tender_id, t.title, tb.bid_amount_mkd, tb.is_winner, t.closing_date
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.supplier_id = :supplier_id
        ORDER BY t.closing_date DESC NULLS LAST
        LIMIT 10
    """)
    activity_result = await db.execute(activity_query, {"supplier_id": supplier_id})
    recent_activity = [
        {
            "tender_id": a.tender_id,
            "title": a.title,
            "bid_amount": float(a.bid_amount_mkd) if a.bid_amount_mkd else None,
            "won": a.is_winner,
            "date": a.closing_date.isoformat() if a.closing_date else None
        }
        for a in activity_result.fetchall()
    ]

    return SupplierStrengthResponse(
        supplier_id=str(supplier.supplier_id),
        company_name=supplier.company_name,
        strength_score=round(strength_score, 1),
        metrics={
            "win_rate": round(win_rate, 2),
            "total_wins": total_wins,
            "total_bids": total_bids,
            "total_value_mkd": total_value,
            "market_share": None,  # Would need total market calculation
            "category_diversity": category_diversity,
            "entity_relationships": entity_relationships,
            "value_tier": value_tier
        },
        rankings={
            "overall": overall_rank,
            "in_city": city_rank if supplier.city else None
        },
        trends={
            "win_rate_6m": round(win_rate_6m, 2),
            "win_rate_12m": round(win_rate_12m, 2),
            "win_rate_trend": win_rate_trend,
            "activity_trend": activity_trend
        },
        recent_activity=recent_activity,
        generated_at=datetime.utcnow()
    )
