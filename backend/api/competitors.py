"""
Competitors API endpoints
Track and analyze competitor activity in tenders
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

from database import get_db
from api.auth import get_current_user

router = APIRouter(prefix="/competitors", tags=["competitors"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class CompetitorActivityDetails(BaseModel):
    """Additional details for activity items"""
    estimated_value: Optional[Decimal] = None
    discount_percent: Optional[float] = None
    num_bidders: Optional[int] = None
    rank: Optional[int] = None

    class Config:
        from_attributes = True


class CompetitorActivity(BaseModel):
    """Single competitor activity item"""
    type: str  # "won", "bid", "lost"
    company_name: str
    tender_id: str
    tender_title: str
    amount: Optional[Decimal] = None
    timestamp: Optional[datetime] = None
    details: Optional[CompetitorActivityDetails] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v) if v else None
        }


class CompetitorActivityResponse(BaseModel):
    """Response for competitor activity feed"""
    activities: List[CompetitorActivity]
    total_count: int
    period: str = "30 days"


class PricingPattern(BaseModel):
    """Pricing behavior analysis"""
    avg_discount: Optional[float] = None
    discount_range: dict = {"min": None, "max": None}
    price_consistency: Optional[float] = None
    avg_bid_mkd: Optional[float] = None
    median_bid_mkd: Optional[float] = None

    class Config:
        from_attributes = True


class CategoryPreference(BaseModel):
    """Category/CPV code preference"""
    cpv_code: Optional[str] = None
    name: Optional[str] = None
    count: int = 0
    win_rate: Optional[float] = None

    class Config:
        from_attributes = True


class SizePreference(BaseModel):
    """Tender size preference"""
    range: str
    count: int = 0
    win_rate: Optional[float] = None
    avg_discount: Optional[float] = None

    class Config:
        from_attributes = True


class SeasonalActivity(BaseModel):
    """Monthly activity pattern"""
    month: str
    bids: int = 0
    wins: int = 0

    class Config:
        from_attributes = True


class TopCompetitor(BaseModel):
    """Frequently competing company"""
    company: str
    overlap_count: int = 0
    head_to_head_wins: int = 0
    head_to_head_losses: int = 0

    class Config:
        from_attributes = True


class WinFactors(BaseModel):
    """Factors correlating with wins"""
    discount_correlation: Optional[str] = None
    preferred_size: Optional[str] = None
    preferred_categories: List[str] = []
    success_rate_by_entity_type: dict = {}

    class Config:
        from_attributes = True


class BiddingPatternResponse(BaseModel):
    """Complete bidding pattern analysis"""
    company_name: str
    analysis_period: str
    total_bids: int = 0
    total_wins: int = 0
    overall_win_rate: Optional[float] = None

    pricing_pattern: PricingPattern
    category_preferences: List[CategoryPreference] = []
    size_preferences: dict = {}
    seasonal_activity: List[SeasonalActivity] = []
    top_competitors: List[TopCompetitor] = []
    win_factors: WinFactors

    class Config:
        from_attributes = True


# ============================================================================
# GET COMPETITOR ACTIVITY FEED
# ============================================================================

@router.get("/activity", response_model=CompetitorActivityResponse)
async def get_competitor_activity(
    company_names: List[str] = Query([], description="List of company names to track"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of activities to return"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get chronological activity feed for tracked competitors.

    Returns recent activity including:
    - Tender wins (is_winner = true)
    - Submitted bids (all bids)
    - Lost tenders (bid submitted but not winner)

    Activities are sorted by tender publication_date DESC.

    Parameters:
    - company_names: Array of company names to track
    - limit: Maximum number of activities (default 50)
    """

    # If no companies specified, return empty
    if not company_names:
        return CompetitorActivityResponse(
            activities=[],
            total_count=0,
            period="30 days"
        )

    # Build query to get all bidder activity
    # We'll determine activity type based on:
    # - "won" if is_winner = true
    # - "bid" for all bids (including winners)
    # - "lost" if is_winner = false AND tender status is awarded

    query = text("""
        WITH bidder_activity AS (
            SELECT
                tb.company_name,
                tb.tender_id,
                t.title as tender_title,
                t.procuring_entity,
                t.category,
                t.publication_date,
                t.closing_date,
                t.status,
                tb.bid_amount_mkd,
                tb.is_winner,
                tb.rank,
                tb.disqualified,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.num_bidders
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_name = ANY(:company_names)
            ORDER BY t.publication_date DESC NULLS LAST
            LIMIT :limit
        )
        SELECT
            CASE
                WHEN is_winner = true THEN 'won'
                WHEN is_winner = false AND status IN ('awarded', 'closed') THEN 'lost'
                ELSE 'bid'
            END as activity_type,
            company_name,
            tender_id,
            tender_title,
            bid_amount_mkd,
            publication_date,
            estimated_value_mkd,
            actual_value_mkd,
            num_bidders,
            rank,
            is_winner
        FROM bidder_activity
        ORDER BY publication_date DESC NULLS LAST
    """)

    result = await db.execute(query, {
        "company_names": company_names,
        "limit": limit
    })
    rows = result.fetchall()

    # Build activities list
    activities = []
    for row in rows:
        # Calculate discount percentage if applicable
        discount_percent = None
        if row.activity_type == 'won' and row.estimated_value_mkd and row.bid_amount_mkd:
            if row.estimated_value_mkd > 0:
                discount_percent = ((row.estimated_value_mkd - row.bid_amount_mkd) / row.estimated_value_mkd) * 100

        details = CompetitorActivityDetails(
            estimated_value=row.estimated_value_mkd,
            discount_percent=discount_percent,
            num_bidders=row.num_bidders,
            rank=row.rank
        )

        activity = CompetitorActivity(
            type=row.activity_type,
            company_name=row.company_name,
            tender_id=row.tender_id,
            tender_title=row.tender_title,
            amount=row.bid_amount_mkd,
            timestamp=row.publication_date,
            details=details
        )

        activities.append(activity)

    return CompetitorActivityResponse(
        activities=activities,
        total_count=len(activities),
        period="30 days"
    )


# ============================================================================
# BIDDING PATTERN ANALYSIS
# ============================================================================

@router.get("/{company_name}/patterns", response_model=BiddingPatternResponse)
async def get_bidding_patterns(
    company_name: str,
    analysis_months: int = Query(24, ge=1, le=60, description="Number of months to analyze"),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze competitor bidding patterns and behavior.

    Provides comprehensive analysis including:
    - Pricing patterns (discounts, consistency)
    - Category preferences (top CPV codes)
    - Size preferences (small/medium/large tenders)
    - Seasonal activity (monthly bid frequency)
    - Top competitors (companies they frequently compete against)
    - Win factors (what correlates with their success)

    Parameters:
    - company_name: Exact company name to analyze
    - analysis_months: Number of months of historical data to analyze (default: 24)
    """

    # ========================================================================
    # 1. BASIC STATISTICS
    # ========================================================================

    basic_stats_query = text(f"""
        WITH date_threshold AS (
            SELECT NOW() - INTERVAL '{analysis_months} months' as cutoff
        )
        SELECT
            COUNT(DISTINCT tb.bidder_id) as total_bids,
            COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as total_wins,
            CASE
                WHEN COUNT(DISTINCT tb.bidder_id) > 0
                THEN (COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE)::float / COUNT(DISTINCT tb.bidder_id) * 100)
                ELSE 0
            END as win_rate
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        CROSS JOIN date_threshold dt
        WHERE tb.company_name ILIKE :company_name
            AND t.closing_date >= dt.cutoff
    """)

    result = await db.execute(basic_stats_query, {
        "company_name": company_name
    })
    stats = result.fetchone()

    if not stats or stats.total_bids == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No bidding data found for company '{company_name}' in the last {analysis_months} months"
        )

    total_bids = stats.total_bids
    total_wins = stats.total_wins
    overall_win_rate = float(stats.win_rate) if stats.win_rate else 0.0

    # ========================================================================
    # 2. PRICING PATTERN ANALYSIS
    # ========================================================================

    pricing_query = text(f"""
        WITH date_threshold AS (
            SELECT NOW() - INTERVAL '{analysis_months} months' as cutoff
        ),
        bid_analysis AS (
            SELECT
                tb.bid_amount_mkd,
                t.estimated_value_mkd,
                CASE
                    WHEN t.estimated_value_mkd > 0
                    THEN ((t.estimated_value_mkd - tb.bid_amount_mkd) / t.estimated_value_mkd * 100)
                    ELSE NULL
                END as discount_pct
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            CROSS JOIN date_threshold dt
            WHERE tb.company_name ILIKE :company_name
                AND t.closing_date >= dt.cutoff
                AND tb.bid_amount_mkd IS NOT NULL
                AND tb.bid_amount_mkd > 0
        )
        SELECT
            AVG(discount_pct) as avg_discount,
            MIN(discount_pct) as min_discount,
            MAX(discount_pct) as max_discount,
            STDDEV(discount_pct) as discount_stddev,
            AVG(bid_amount_mkd) as avg_bid,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY bid_amount_mkd) as median_bid
        FROM bid_analysis
        WHERE discount_pct IS NOT NULL
    """)

    pricing_result = await db.execute(pricing_query, {
        "company_name": company_name
    })
    pricing_row = pricing_result.fetchone()

    # Calculate price consistency (inverse of coefficient of variation)
    price_consistency = None
    if pricing_row and pricing_row.avg_discount and pricing_row.discount_stddev:
        # Consistency score: 1 - (stddev / mean), clamped to 0-1
        cv = abs(pricing_row.discount_stddev / pricing_row.avg_discount) if pricing_row.avg_discount != 0 else 0
        price_consistency = max(0, min(1, 1 - cv / 2))  # Normalize to 0-1 range

    pricing_pattern = PricingPattern(
        avg_discount=float(pricing_row.avg_discount) if pricing_row and pricing_row.avg_discount else None,
        discount_range={
            "min": float(pricing_row.min_discount) if pricing_row and pricing_row.min_discount else None,
            "max": float(pricing_row.max_discount) if pricing_row and pricing_row.max_discount else None
        },
        price_consistency=float(price_consistency) if price_consistency else None,
        avg_bid_mkd=float(pricing_row.avg_bid) if pricing_row and pricing_row.avg_bid else None,
        median_bid_mkd=float(pricing_row.median_bid) if pricing_row and pricing_row.median_bid else None
    )

    # ========================================================================
    # 3. CATEGORY PREFERENCES (Top 5 CPV codes)
    # ========================================================================

    category_query = text(f"""
        WITH date_threshold AS (
            SELECT NOW() - INTERVAL '{analysis_months} months' as cutoff
        )
        SELECT
            t.cpv_code,
            t.category as name,
            COUNT(DISTINCT tb.bidder_id) as bid_count,
            COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as win_count,
            CASE
                WHEN COUNT(DISTINCT tb.bidder_id) > 0
                THEN (COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE)::float / COUNT(DISTINCT tb.bidder_id) * 100)
                ELSE 0
            END as win_rate
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        CROSS JOIN date_threshold dt
        WHERE tb.company_name ILIKE :company_name
            AND t.closing_date >= dt.cutoff
            AND t.cpv_code IS NOT NULL
        GROUP BY t.cpv_code, t.category
        ORDER BY bid_count DESC
        LIMIT 5
    """)

    category_result = await db.execute(category_query, {
        "company_name": company_name
    })
    category_rows = category_result.fetchall()

    category_preferences = [
        CategoryPreference(
            cpv_code=row.cpv_code,
            name=row.name or "Unknown",
            count=row.bid_count,
            win_rate=float(row.win_rate) if row.win_rate else 0.0
        )
        for row in category_rows
    ]

    # ========================================================================
    # 4. SIZE PREFERENCES (Small/Medium/Large tenders)
    # ========================================================================

    size_query = text(f"""
        WITH date_threshold AS (
            SELECT NOW() - INTERVAL '{analysis_months} months' as cutoff
        ),
        size_categorized AS (
            SELECT
                tb.is_winner,
                tb.bid_amount_mkd,
                t.estimated_value_mkd,
                CASE
                    WHEN t.estimated_value_mkd > 0 AND tb.bid_amount_mkd > 0
                    THEN ((t.estimated_value_mkd - tb.bid_amount_mkd) / t.estimated_value_mkd * 100)
                    ELSE NULL
                END as discount_pct,
                CASE
                    WHEN t.estimated_value_mkd < 500000 THEN 'small'
                    WHEN t.estimated_value_mkd < 2000000 THEN 'medium'
                    ELSE 'large'
                END as size_category
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            CROSS JOIN date_threshold dt
            WHERE tb.company_name ILIKE :company_name
                AND t.closing_date >= dt.cutoff
                AND t.estimated_value_mkd IS NOT NULL
                AND t.estimated_value_mkd > 0
        )
        SELECT
            size_category,
            COUNT(*) as total_bids,
            COUNT(*) FILTER (WHERE is_winner = TRUE) as wins,
            CASE
                WHEN COUNT(*) > 0
                THEN (COUNT(*) FILTER (WHERE is_winner = TRUE)::float / COUNT(*) * 100)
                ELSE 0
            END as win_rate,
            AVG(discount_pct) FILTER (WHERE discount_pct IS NOT NULL) as avg_discount
        FROM size_categorized
        GROUP BY size_category
        ORDER BY
            CASE size_category
                WHEN 'small' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'large' THEN 3
            END
    """)

    size_result = await db.execute(size_query, {
        "company_name": company_name
    })
    size_rows = size_result.fetchall()

    size_labels = {
        'small': '0-500K MKD',
        'medium': '500K-2M MKD',
        'large': '2M+ MKD'
    }

    size_preferences = {}
    for row in size_rows:
        size_preferences[row.size_category] = SizePreference(
            range=size_labels.get(row.size_category, row.size_category),
            count=row.total_bids,
            win_rate=float(row.win_rate) if row.win_rate else 0.0,
            avg_discount=float(row.avg_discount) if row.avg_discount else None
        )

    # ========================================================================
    # 5. SEASONAL ACTIVITY (Monthly bid frequency)
    # ========================================================================

    seasonal_query = text(f"""
        WITH date_threshold AS (
            SELECT NOW() - INTERVAL '{analysis_months} months' as cutoff
        )
        SELECT
            TO_CHAR(t.closing_date, 'Month') as month,
            EXTRACT(MONTH FROM t.closing_date) as month_num,
            COUNT(DISTINCT tb.bidder_id) as bids,
            COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as wins
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        CROSS JOIN date_threshold dt
        WHERE tb.company_name ILIKE :company_name
            AND t.closing_date >= dt.cutoff
        GROUP BY TO_CHAR(t.closing_date, 'Month'), EXTRACT(MONTH FROM t.closing_date)
        ORDER BY month_num
    """)

    seasonal_result = await db.execute(seasonal_query, {
        "company_name": company_name
    })
    seasonal_rows = seasonal_result.fetchall()

    seasonal_activity = [
        SeasonalActivity(
            month=row.month.strip(),
            bids=row.bids,
            wins=row.wins
        )
        for row in seasonal_rows
    ]

    # ========================================================================
    # 6. TOP COMPETITORS (Companies they frequently compete against)
    # ========================================================================

    competitors_query = text(f"""
        WITH date_threshold AS (
            SELECT NOW() - INTERVAL '{analysis_months} months' as cutoff
        ),
        company_tenders AS (
            -- Get all tenders where target company participated
            SELECT DISTINCT tb.tender_id
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            CROSS JOIN date_threshold dt
            WHERE tb.company_name ILIKE :company_name
                AND t.closing_date >= dt.cutoff
        ),
        competing_companies AS (
            -- Get other bidders in same tenders
            SELECT
                tb2.company_name,
                tb2.is_winner as competitor_won,
                tb1.is_winner as target_won
            FROM company_tenders ct
            JOIN tender_bidders tb1 ON ct.tender_id = tb1.tender_id
            JOIN tender_bidders tb2 ON ct.tender_id = tb2.tender_id
            WHERE tb1.company_name ILIKE :company_name
                AND tb2.company_name NOT ILIKE :company_name
                AND tb2.company_name IS NOT NULL
        )
        SELECT
            company_name,
            COUNT(*) as overlap_count,
            COUNT(*) FILTER (WHERE target_won = TRUE AND competitor_won = FALSE) as our_wins,
            COUNT(*) FILTER (WHERE target_won = FALSE AND competitor_won = TRUE) as their_wins
        FROM competing_companies
        GROUP BY company_name
        ORDER BY overlap_count DESC
        LIMIT 10
    """)

    competitors_result = await db.execute(competitors_query, {
        "company_name": company_name
    })
    competitors_rows = competitors_result.fetchall()

    top_competitors = [
        TopCompetitor(
            company=row.company_name,
            overlap_count=row.overlap_count,
            head_to_head_wins=row.our_wins,
            head_to_head_losses=row.their_wins
        )
        for row in competitors_rows
    ]

    # ========================================================================
    # 7. WIN FACTORS (What correlates with success)
    # ========================================================================

    # Determine if lower discount correlates with wins
    discount_correlation = "Unknown"
    if pricing_row and pricing_row.avg_discount:
        avg_discount = float(pricing_row.avg_discount)
        if avg_discount < 5:
            discount_correlation = "Wins with minimal discount (competitive pricing)"
        elif avg_discount > 20:
            discount_correlation = "Wins with aggressive discounts (price-sensitive)"
        else:
            discount_correlation = "Wins with moderate discounts (balanced approach)"

    # Determine preferred size based on highest win rate
    preferred_size = None
    max_win_rate = 0
    for size, prefs in size_preferences.items():
        if prefs.win_rate and prefs.win_rate > max_win_rate:
            max_win_rate = prefs.win_rate
            preferred_size = f"{size.capitalize()} tenders ({prefs.range})"

    # Top 3 categories
    preferred_categories = [
        f"{cat.name} ({cat.cpv_code})" if cat.cpv_code else cat.name
        for cat in category_preferences[:3]
    ]

    # Success rate by entity type
    entity_type_query = text(f"""
        WITH date_threshold AS (
            SELECT NOW() - INTERVAL '{analysis_months} months' as cutoff
        )
        SELECT
            t.contracting_entity_category,
            COUNT(*) as total_bids,
            COUNT(*) FILTER (WHERE tb.is_winner = TRUE) as wins,
            CASE
                WHEN COUNT(*) > 0
                THEN (COUNT(*) FILTER (WHERE tb.is_winner = TRUE)::float / COUNT(*) * 100)
                ELSE 0
            END as win_rate
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        CROSS JOIN date_threshold dt
        WHERE tb.company_name ILIKE :company_name
            AND t.closing_date >= dt.cutoff
            AND t.contracting_entity_category IS NOT NULL
        GROUP BY t.contracting_entity_category
        HAVING COUNT(*) >= 3  -- Only include entity types with 3+ bids
        ORDER BY win_rate DESC
        LIMIT 5
    """)

    entity_type_result = await db.execute(entity_type_query, {
        "company_name": company_name
    })
    entity_type_rows = entity_type_result.fetchall()

    success_rate_by_entity_type = {
        row.contracting_entity_category: float(row.win_rate) if row.win_rate else 0.0
        for row in entity_type_rows
    }

    win_factors = WinFactors(
        discount_correlation=discount_correlation,
        preferred_size=preferred_size,
        preferred_categories=preferred_categories,
        success_rate_by_entity_type=success_rate_by_entity_type
    )

    # ========================================================================
    # BUILD RESPONSE
    # ========================================================================

    return BiddingPatternResponse(
        company_name=company_name,
        analysis_period=f"{analysis_months} months",
        total_bids=total_bids,
        total_wins=total_wins,
        overall_win_rate=overall_win_rate,
        pricing_pattern=pricing_pattern,
        category_preferences=category_preferences,
        size_preferences=size_preferences,
        seasonal_activity=seasonal_activity,
        top_competitors=top_competitors,
        win_factors=win_factors
    )


# ============================================================================
# COMPANY ANALYSIS (for competitor detail page)
# ============================================================================

class RecentWin(BaseModel):
    """A recent win for the company"""
    tender_id: str
    title: str
    procuring_entity: str
    category: Optional[str] = None
    cpv_code: Optional[str] = None
    contract_value_mkd: Optional[float] = None
    date: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommonCategory(BaseModel):
    """Common category for the company"""
    category: str
    bid_count: int
    win_count: int
    won_value_mkd: float = 0

    class Config:
        from_attributes = True


class FrequentInstitution(BaseModel):
    """Frequently worked with institution"""
    institution: str
    bid_count: int
    win_count: int
    avg_bid_mkd: Optional[float] = None

    class Config:
        from_attributes = True


class TenderStats(BaseModel):
    """Tender statistics for a company"""
    total_bids: int = 0
    total_wins: int = 0
    win_rate: float = 0.0
    avg_bid_value_mkd: Optional[float] = None
    total_won_value_mkd: Optional[float] = None
    first_bid_date: Optional[datetime] = None
    last_bid_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class CompanyAnalysisResponse(BaseModel):
    """Complete company analysis response"""
    company_name: str
    summary: str
    tender_stats: TenderStats
    recent_wins: List[RecentWin] = []
    common_categories: List[CommonCategory] = []
    frequent_institutions: List[FrequentInstitution] = []
    ai_insights: str = ""

    class Config:
        from_attributes = True


@router.get("/analyze/{company_name}", response_model=CompanyAnalysisResponse)
async def analyze_company(
    company_name: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get comprehensive analysis of a competitor company.

    Returns:
    - Company summary
    - Tender statistics (bids, wins, win rate, values)
    - Recent wins with details
    - Common categories/CPV codes
    - Frequent institutions/entities
    - AI-generated insights
    """

    # 1. Get basic stats
    stats_query = text("""
        SELECT
            COUNT(DISTINCT tb.bidder_id) as total_bids,
            COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as total_wins,
            AVG(tb.bid_amount_mkd) as avg_bid_value,
            SUM(tb.bid_amount_mkd) FILTER (WHERE tb.is_winner = TRUE) as total_won_value,
            MIN(t.publication_date) as first_bid_date,
            MAX(t.publication_date) as last_bid_date
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name ILIKE :company_name
    """)

    result = await db.execute(stats_query, {"company_name": company_name})
    stats_row = result.fetchone()

    if not stats_row or stats_row.total_bids == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for company '{company_name}'"
        )

    total_bids = stats_row.total_bids or 0
    total_wins = stats_row.total_wins or 0
    win_rate = (total_wins / total_bids) if total_bids > 0 else 0

    tender_stats = TenderStats(
        total_bids=total_bids,
        total_wins=total_wins,
        win_rate=win_rate,
        avg_bid_value_mkd=float(stats_row.avg_bid_value) if stats_row.avg_bid_value else None,
        total_won_value_mkd=float(stats_row.total_won_value) if stats_row.total_won_value else None,
        first_bid_date=stats_row.first_bid_date,
        last_bid_date=stats_row.last_bid_date
    )

    # 2. Get recent wins
    wins_query = text("""
        SELECT
            t.tender_id,
            t.title,
            t.procuring_entity,
            t.category,
            t.cpv_code,
            tb.bid_amount_mkd as contract_value_mkd,
            COALESCE(t.closing_date, t.publication_date) as date
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name ILIKE :company_name
            AND tb.is_winner = TRUE
        ORDER BY COALESCE(t.closing_date, t.publication_date) DESC NULLS LAST
        LIMIT 10
    """)

    wins_result = await db.execute(wins_query, {"company_name": company_name})
    recent_wins = [
        RecentWin(
            tender_id=row.tender_id,
            title=row.title or "Unknown",
            procuring_entity=row.procuring_entity or "Unknown",
            category=row.category,
            cpv_code=row.cpv_code,
            contract_value_mkd=float(row.contract_value_mkd) if row.contract_value_mkd else None,
            date=row.date
        )
        for row in wins_result.fetchall()
    ]

    # 3. Get common categories
    categories_query = text("""
        SELECT
            COALESCE(t.category, 'Непознато') as category,
            COUNT(DISTINCT tb.bidder_id) as bid_count,
            COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as win_count,
            COALESCE(SUM(tb.bid_amount_mkd) FILTER (WHERE tb.is_winner = TRUE), 0) as won_value_mkd
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name ILIKE :company_name
        GROUP BY COALESCE(t.category, 'Непознато')
        ORDER BY bid_count DESC
        LIMIT 10
    """)

    cat_result = await db.execute(categories_query, {"company_name": company_name})
    common_categories = [
        CommonCategory(
            category=row.category,
            bid_count=row.bid_count,
            win_count=row.win_count,
            won_value_mkd=float(row.won_value_mkd) if row.won_value_mkd else 0
        )
        for row in cat_result.fetchall()
    ]

    # 4. Get frequent institutions
    institutions_query = text("""
        SELECT
            t.procuring_entity as institution,
            COUNT(DISTINCT tb.bidder_id) as bid_count,
            COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as win_count,
            AVG(tb.bid_amount_mkd) as avg_bid_mkd
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name ILIKE :company_name
            AND t.procuring_entity IS NOT NULL
        GROUP BY t.procuring_entity
        ORDER BY bid_count DESC
        LIMIT 10
    """)

    inst_result = await db.execute(institutions_query, {"company_name": company_name})
    frequent_institutions = [
        FrequentInstitution(
            institution=row.institution,
            bid_count=row.bid_count,
            win_count=row.win_count,
            avg_bid_mkd=float(row.avg_bid_mkd) if row.avg_bid_mkd else None
        )
        for row in inst_result.fetchall()
    ]

    # 5. Generate summary and AI insights
    summary = f"{company_name} има поднесено {total_bids} понуди и освоено {total_wins} тендери со стапка на успешност од {win_rate*100:.1f}%."

    insights = []
    if win_rate > 0.5:
        insights.append(f"Компанијата има висока стапка на успешност ({win_rate*100:.1f}%).")
    elif win_rate > 0.3:
        insights.append(f"Компанијата има солидна стапка на успешност ({win_rate*100:.1f}%).")
    else:
        insights.append(f"Компанијата има ниска стапка на успешност ({win_rate*100:.1f}%).")

    if common_categories:
        top_cat = common_categories[0]
        insights.append(f"Најактивна во категоријата '{top_cat.category}' со {top_cat.bid_count} понуди.")

    if frequent_institutions:
        top_inst = frequent_institutions[0]
        insights.append(f"Најчесто соработува со '{top_inst.institution}'.")

    if tender_stats.total_won_value_mkd:
        insights.append(f"Вкупна вредност на освоени тендери: {tender_stats.total_won_value_mkd:,.0f} МКД.")

    ai_insights = " ".join(insights)

    return CompanyAnalysisResponse(
        company_name=company_name,
        summary=summary,
        tender_stats=tender_stats,
        recent_wins=recent_wins,
        common_categories=common_categories,
        frequent_institutions=frequent_institutions,
        ai_insights=ai_insights
    )


# ============================================================================
# HEAD-TO-HEAD COMPARISON
# ============================================================================

class HeadToHeadConfrontation(BaseModel):
    """Single head-to-head confrontation record"""
    tender_id: str
    title: str
    winner: str
    company_a_bid: Optional[Decimal] = None
    company_b_bid: Optional[Decimal] = None
    date: Optional[datetime] = None
    estimated_value: Optional[Decimal] = None
    num_bidders: Optional[int] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v) if v else None
        }


class CategoryDominance(BaseModel):
    """Category where a company dominates"""
    category: str
    cpv_code: Optional[str] = None
    win_count: int = 0
    total_count: int = 0
    win_rate: float = 0.0

    class Config:
        from_attributes = True


class HeadToHeadResponse(BaseModel):
    """Head-to-head comparison response"""
    company_a: str
    company_b: str
    total_confrontations: int
    company_a_wins: int
    company_b_wins: int
    ties: int
    avg_bid_difference: Optional[float] = None  # Positive if A bids lower on average
    company_a_categories: List[CategoryDominance] = []
    company_b_categories: List[CategoryDominance] = []
    recent_confrontations: List[HeadToHeadConfrontation] = []
    ai_insights: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/head-to-head", response_model=HeadToHeadResponse)
async def get_head_to_head(
    company_a: str = Query(..., description="First company name"),
    company_b: str = Query(..., description="Second company name"),
    limit: int = Query(20, ge=1, le=100, description="Max recent confrontations to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get head-to-head comparison between two competitors.

    Analyzes tenders where both companies submitted bids and provides:
    - Total confrontations
    - Win/loss record for each company
    - Average bid difference
    - Category dominance for each company
    - Recent confrontation details
    - AI-generated insights

    Parameters:
    - company_a: First company name
    - company_b: Second company name
    - limit: Maximum number of recent confrontations to return (default: 20)
    """

    # ========================================================================
    # 1. FIND ALL TENDERS WHERE BOTH COMPANIES BID
    # ========================================================================

    confrontations_query = text("""
        WITH company_a_bids AS (
            SELECT
                tender_id,
                bid_amount_mkd as a_bid,
                is_winner as a_winner,
                rank as a_rank
            FROM tender_bidders
            WHERE company_name ILIKE :company_a
        ),
        company_b_bids AS (
            SELECT
                tender_id,
                bid_amount_mkd as b_bid,
                is_winner as b_winner,
                rank as b_rank
            FROM tender_bidders
            WHERE company_name ILIKE :company_b
        ),
        confrontations AS (
            SELECT
                t.tender_id,
                t.title,
                t.category,
                t.cpv_code,
                t.estimated_value_mkd,
                t.num_bidders,
                t.closing_date,
                t.publication_date,
                a.a_bid,
                a.a_winner,
                a.a_rank,
                b.b_bid,
                b.b_winner,
                b.b_rank,
                CASE
                    WHEN a.a_winner = TRUE AND b.b_winner = FALSE THEN 'a'
                    WHEN b.b_winner = TRUE AND a.a_winner = FALSE THEN 'b'
                    WHEN a.a_winner = TRUE AND b.b_winner = TRUE THEN 'tie'
                    ELSE NULL
                END as winner
            FROM company_a_bids a
            JOIN company_b_bids b ON a.tender_id = b.tender_id
            JOIN tenders t ON a.tender_id = t.tender_id
        )
        SELECT
            tender_id,
            title,
            category,
            cpv_code,
            estimated_value_mkd,
            num_bidders,
            COALESCE(closing_date, publication_date) as date,
            a_bid,
            b_bid,
            a_winner,
            b_winner,
            winner
        FROM confrontations
        ORDER BY date DESC NULLS LAST
    """)

    result = await db.execute(confrontations_query, {
        "company_a": company_a,
        "company_b": company_b
    })
    rows = result.fetchall()

    if not rows:
        # No confrontations found
        return HeadToHeadResponse(
            company_a=company_a,
            company_b=company_b,
            total_confrontations=0,
            company_a_wins=0,
            company_b_wins=0,
            ties=0,
            avg_bid_difference=None,
            company_a_categories=[],
            company_b_categories=[],
            recent_confrontations=[],
            ai_insights=f"No direct confrontations found between {company_a} and {company_b}. These companies have not bid on the same tenders."
        )

    # ========================================================================
    # 2. CALCULATE STATISTICS
    # ========================================================================

    total_confrontations = len(rows)
    company_a_wins = sum(1 for r in rows if r.winner == 'a')
    company_b_wins = sum(1 for r in rows if r.winner == 'b')
    ties = sum(1 for r in rows if r.winner == 'tie')

    # Calculate average bid difference (positive if A bids lower)
    bid_differences = []
    for r in rows:
        if r.a_bid is not None and r.b_bid is not None:
            # Positive value means A bids lower
            diff = float(r.b_bid - r.a_bid)
            bid_differences.append(diff)

    avg_bid_difference = sum(bid_differences) / len(bid_differences) if bid_differences else None

    # ========================================================================
    # 3. CATEGORY DOMINANCE
    # ========================================================================

    # Group by category for each company
    categories = {}
    for r in rows:
        cat = r.category or "Unknown"
        if cat not in categories:
            categories[cat] = {
                "category": cat,
                "cpv_code": r.cpv_code,
                "total": 0,
                "a_wins": 0,
                "b_wins": 0
            }
        categories[cat]["total"] += 1
        if r.winner == 'a':
            categories[cat]["a_wins"] += 1
        elif r.winner == 'b':
            categories[cat]["b_wins"] += 1

    # Determine dominance (need at least 2 confrontations and >50% win rate)
    company_a_categories = []
    company_b_categories = []

    for cat_data in categories.values():
        if cat_data["total"] >= 2:  # At least 2 confrontations
            a_rate = (cat_data["a_wins"] / cat_data["total"]) * 100
            b_rate = (cat_data["b_wins"] / cat_data["total"]) * 100

            if a_rate > 50:
                company_a_categories.append(CategoryDominance(
                    category=cat_data["category"],
                    cpv_code=cat_data["cpv_code"],
                    win_count=cat_data["a_wins"],
                    total_count=cat_data["total"],
                    win_rate=round(a_rate, 1)
                ))
            if b_rate > 50:
                company_b_categories.append(CategoryDominance(
                    category=cat_data["category"],
                    cpv_code=cat_data["cpv_code"],
                    win_count=cat_data["b_wins"],
                    total_count=cat_data["total"],
                    win_rate=round(b_rate, 1)
                ))

    # Sort by win rate descending
    company_a_categories.sort(key=lambda x: x.win_rate, reverse=True)
    company_b_categories.sort(key=lambda x: x.win_rate, reverse=True)

    # ========================================================================
    # 4. RECENT CONFRONTATIONS
    # ========================================================================

    recent_confrontations = []
    for r in rows[:limit]:
        # Determine winner name
        winner_name = None
        if r.winner == 'a':
            winner_name = company_a
        elif r.winner == 'b':
            winner_name = company_b
        elif r.winner == 'tie':
            winner_name = "Both"
        else:
            winner_name = "Unknown"

        recent_confrontations.append(HeadToHeadConfrontation(
            tender_id=r.tender_id,
            title=r.title,
            winner=winner_name,
            company_a_bid=r.a_bid,
            company_b_bid=r.b_bid,
            date=r.date,
            estimated_value=r.estimated_value_mkd,
            num_bidders=r.num_bidders
        ))

    # ========================================================================
    # 5. AI INSIGHTS
    # ========================================================================

    # Generate basic insights based on the data
    insights = []

    # Win rate comparison
    a_win_rate = (company_a_wins / total_confrontations * 100) if total_confrontations > 0 else 0
    b_win_rate = (company_b_wins / total_confrontations * 100) if total_confrontations > 0 else 0

    if a_win_rate > b_win_rate + 10:
        insights.append(f"{company_a} has a significant advantage with {a_win_rate:.1f}% win rate compared to {company_b}'s {b_win_rate:.1f}%.")
    elif b_win_rate > a_win_rate + 10:
        insights.append(f"{company_b} has a significant advantage with {b_win_rate:.1f}% win rate compared to {company_a}'s {a_win_rate:.1f}%.")
    else:
        insights.append(f"The competition is relatively balanced with {company_a} at {a_win_rate:.1f}% and {company_b} at {b_win_rate:.1f}% win rates.")

    # Pricing strategy
    if avg_bid_difference is not None:
        if abs(avg_bid_difference) < 10000:
            insights.append(f"Both companies have very similar pricing strategies (average difference: {abs(avg_bid_difference):,.0f} MKD).")
        elif avg_bid_difference > 0:
            insights.append(f"{company_a} typically bids {avg_bid_difference:,.0f} MKD lower than {company_b} on average.")
        else:
            insights.append(f"{company_b} typically bids {abs(avg_bid_difference):,.0f} MKD lower than {company_a} on average.")

    # Category dominance
    if company_a_categories:
        top_a_cat = company_a_categories[0]
        insights.append(f"{company_a} dominates in {top_a_cat.category} with {top_a_cat.win_rate:.0f}% win rate ({top_a_cat.win_count}/{top_a_cat.total_count} wins).")

    if company_b_categories:
        top_b_cat = company_b_categories[0]
        insights.append(f"{company_b} dominates in {top_b_cat.category} with {top_b_cat.win_rate:.0f}% win rate ({top_b_cat.win_count}/{top_b_cat.total_count} wins).")

    # Confrontation frequency
    if total_confrontations < 5:
        insights.append(f"Limited data: Only {total_confrontations} direct confrontations found. More data would provide better insights.")
    elif total_confrontations > 20:
        insights.append(f"Extensive competition history: {total_confrontations} direct confrontations provide strong statistical confidence.")

    ai_insights_text = " ".join(insights)

    # ========================================================================
    # 6. BUILD RESPONSE
    # ========================================================================

    return HeadToHeadResponse(
        company_a=company_a,
        company_b=company_b,
        total_confrontations=total_confrontations,
        company_a_wins=company_a_wins,
        company_b_wins=company_b_wins,
        ties=ties,
        avg_bid_difference=avg_bid_difference,
        company_a_categories=company_a_categories[:5],  # Top 5
        company_b_categories=company_b_categories[:5],  # Top 5
        recent_confrontations=recent_confrontations,
        ai_insights=ai_insights_text
    )
