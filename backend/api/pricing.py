"""
Historical Price Aggregation API & AI Bid Advisor
Provides statistical analysis of tender pricing trends by CPV code
and AI-powered bid recommendations
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
import os
import statistics

from database import get_db
from models import User
from api.auth import get_current_user
from utils.timezone import get_ai_date_context
from utils.product_quality import product_quality_filter
from middleware.entitlements import require_module
from config.plans import ModuleName

router = APIRouter(prefix="/ai", tags=["pricing"])

# Import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = bool(os.getenv('GEMINI_API_KEY'))
    if GEMINI_AVAILABLE:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
except ImportError:
    GEMINI_AVAILABLE = False


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class PriceHistoryPoint(BaseModel):
    """Single time period data point"""
    period: str  # "2024-01" or "2024-Q1"
    tender_count: int
    avg_estimated: Optional[float]
    avg_actual: Optional[float]
    avg_discount_pct: Optional[float]  # percentage below estimate
    avg_bidders: Optional[float]


class PriceHistoryResponse(BaseModel):
    """Historical pricing data response"""
    cpv_code: str
    cpv_description: Optional[str]
    time_range: str  # "2023-01 to 2024-12"
    data_points: List[PriceHistoryPoint]
    trend: str  # "increasing", "decreasing", "stable"
    trend_pct: float  # percentage change over period
    total_tenders: int


class BidRecommendation(BaseModel):
    """Single bid recommendation strategy"""
    strategy: str  # "aggressive", "balanced", "safe"
    recommended_bid: float
    win_probability: float  # 0-1
    reasoning: str


class BidAdvisorResponse(BaseModel):
    """AI-powered bid advisor response"""
    tender_id: str
    tender_title: str
    estimated_value: Optional[float]
    cpv_code: Optional[str]
    category: Optional[str]
    procuring_entity: Optional[str]
    market_analysis: Dict[str, Any]  # {avg_discount: float, typical_bidders: int, price_trend: str, competition_level: str}
    historical_data: Dict[str, Any]  # {similar_tenders: int, avg_winning_bid: float, min_bid: float, max_bid: float, etc}
    recommendations: List[BidRecommendation]
    competitor_insights: List[Dict[str, Any]]  # [{company: str, win_rate: float, avg_discount: float}]
    item_prices: Optional[List[Dict[str, Any]]] = None  # [{item_name: str, avg_price: float, unit: str}]
    ai_summary: str
    generated_at: str


# ============================================================================
# PRICE HISTORY ENDPOINT
# ============================================================================

@router.get("/price-history/{cpv_code}", response_model=PriceHistoryResponse,
            dependencies=[Depends(require_module(ModuleName.ANALYTICS))])
async def get_price_history(
    cpv_code: str,
    months: int = Query(24, ge=1, le=120, description="Number of months to look back"),
    group_by: str = Query("month", regex="^(month|quarter)$", description="Group by month or quarter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get historical pricing data aggregated by time period

    Aggregates tender data by CPV code and time period to show:
    - Average estimated values
    - Average actual/winning values
    - Average discount percentage
    - Average number of bidders
    - Pricing trends over time

    Parameters:
    - cpv_code: CPV code to analyze (prefix matching)
    - months: Number of months to look back (1-120, default 24)
    - group_by: Time period grouping - "month" or "quarter" (default "month")

    Returns:
    - Aggregated pricing data by time period
    - Overall trend analysis (increasing/decreasing/stable)
    - Trend percentage change
    """

    # Validate CPV code format (should be digits)
    if not cpv_code or not cpv_code[0].isdigit():
        raise HTTPException(
            status_code=400,
            detail="Invalid CPV code format. Must start with digits."
        )

    # Determine time truncation based on grouping
    time_trunc = 'month' if group_by == 'month' else 'quarter'

    # Query for aggregated price history
    # Note: We use make_interval() to safely parameterize the INTERVAL value
    query = text("""
        WITH price_data AS (
            SELECT
                DATE_TRUNC(:time_trunc, publication_date) as period,
                COUNT(*) as tender_count,
                AVG(estimated_value_mkd) as avg_estimated,
                AVG(actual_value_mkd) as avg_actual,
                AVG(CASE
                    WHEN estimated_value_mkd > 0 AND actual_value_mkd IS NOT NULL THEN
                        (estimated_value_mkd - actual_value_mkd) / estimated_value_mkd * 100
                    END
                ) as avg_discount_pct,
                AVG(num_bidders) as avg_bidders
            FROM tenders
            WHERE cpv_code LIKE :cpv_prefix
              AND publication_date > NOW() - make_interval(months => :months)
              AND publication_date IS NOT NULL
              AND status IN ('awarded', 'completed', 'active')
            GROUP BY DATE_TRUNC(:time_trunc, publication_date)
            HAVING COUNT(*) > 0
        )
        SELECT
            period,
            tender_count,
            avg_estimated,
            avg_actual,
            avg_discount_pct,
            avg_bidders
        FROM price_data
        ORDER BY period ASC
    """)

    try:
        result = await db.execute(
            query,
            {
                "time_trunc": time_trunc,
                "cpv_prefix": f"{cpv_code}%",
                "months": months
            }
        )
        rows = result.fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
        )

    if not rows:
        # No data found for this CPV code
        return PriceHistoryResponse(
            cpv_code=cpv_code,
            cpv_description=None,
            time_range="No data available",
            data_points=[],
            trend="stable",
            trend_pct=0.0,
            total_tenders=0
        )

    # Build data points
    data_points = []
    total_tenders = 0

    for row in rows:
        period_date = row[0]

        # Format period string
        if group_by == 'month':
            period_str = period_date.strftime('%Y-%m')
        else:  # quarter
            quarter = (period_date.month - 1) // 3 + 1
            period_str = f"{period_date.year}-Q{quarter}"

        tender_count = int(row[1])
        total_tenders += tender_count

        data_points.append(PriceHistoryPoint(
            period=period_str,
            tender_count=tender_count,
            avg_estimated=float(row[2]) if row[2] is not None else None,
            avg_actual=float(row[3]) if row[3] is not None else None,
            avg_discount_pct=float(row[4]) if row[4] is not None else None,
            avg_bidders=float(row[5]) if row[5] is not None else None
        ))

    # Calculate time range
    time_range = "No data"
    if data_points:
        time_range = f"{data_points[0].period} to {data_points[-1].period}"

    # Calculate trend
    trend = "stable"
    trend_pct = 0.0

    if len(data_points) >= 4:
        # Compare first half vs second half averages
        mid_point = len(data_points) // 2

        first_half = data_points[:mid_point]
        second_half = data_points[mid_point:]

        # Calculate average actual values for each half
        first_half_avg = _calculate_period_avg(first_half, 'avg_actual')
        second_half_avg = _calculate_period_avg(second_half, 'avg_actual')

        # If no actual values, use estimated values
        if first_half_avg is None or second_half_avg is None:
            first_half_avg = _calculate_period_avg(first_half, 'avg_estimated')
            second_half_avg = _calculate_period_avg(second_half, 'avg_estimated')

        # Calculate percentage change
        if first_half_avg and second_half_avg and first_half_avg > 0:
            trend_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100

            if trend_pct > 5:
                trend = "increasing"
            elif trend_pct < -5:
                trend = "decreasing"
            else:
                trend = "stable"

    # Get CPV description from database
    cpv_description = await _get_cpv_description(db, cpv_code)

    return PriceHistoryResponse(
        cpv_code=cpv_code,
        cpv_description=cpv_description,
        time_range=time_range,
        data_points=data_points,
        trend=trend,
        trend_pct=round(trend_pct, 2),
        total_tenders=total_tenders
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _calculate_period_avg(periods: List[PriceHistoryPoint], field: str) -> Optional[float]:
    """Calculate average of a field across periods, weighted by tender count"""
    total_value = 0.0
    total_tenders = 0

    for period in periods:
        value = getattr(period, field)
        if value is not None and period.tender_count > 0:
            total_value += value * period.tender_count
            total_tenders += period.tender_count

    if total_tenders == 0:
        return None

    return total_value / total_tenders


async def _get_cpv_description(db: AsyncSession, cpv_code: str) -> Optional[str]:
    """Get CPV code description from database or cache"""
    try:
        # Try to get from tenders table first
        query = text("""
            SELECT category
            FROM tenders
            WHERE cpv_code LIKE :cpv_prefix
              AND category IS NOT NULL
            LIMIT 1
        """)

        result = await db.execute(query, {"cpv_prefix": f"{cpv_code}%"})
        row = result.fetchone()

        if row and row[0]:
            return row[0]

        # Fallback to common CPV codes
        cpv_descriptions = {
            "33000000": "Medical equipment, pharmaceuticals and personal care products",
            "33100000": "Medical equipment",
            "33140000": "Medical consumables",
            "33600000": "Pharmaceutical products",
            "45000000": "Construction work",
            "45200000": "Works for complete or part construction",
            "45300000": "Building installation work",
            "45400000": "Building completion work",
            "50000000": "Repair and maintenance services",
            "50100000": "Repair and maintenance of vehicles",
            "50700000": "Repair and maintenance services of building installations",
            "60000000": "Transport services",
            "60100000": "Road transport services",
            "60400000": "Air transport services",
            "66000000": "Financial and insurance services",
            "66100000": "Banking services",
            "71000000": "Architectural and engineering services",
            "71300000": "Engineering services",
            "72000000": "IT services",
            "72200000": "Software programming",
            "72400000": "Internet services",
            "79000000": "Business services",
            "79100000": "Legal services",
            "79200000": "Accounting services",
            "79300000": "Market research",
            "79400000": "Consulting services",
            "79500000": "Office support services",
            "79600000": "Recruitment services",
            "79700000": "Investigation and security services",
            "80000000": "Education and training services",
            "85000000": "Health and social work services",
            "90000000": "Sewage and refuse disposal services",
            "92000000": "Recreational, cultural and sporting services",
            "98000000": "Other community and personal services",
            "09000000": "Petroleum products, fuel and electricity",
            "14000000": "Mining products",
            "15000000": "Food and beverages",
            "18000000": "Clothing and footwear",
            "22000000": "Printed matter",
            "30000000": "Office equipment",
            "31000000": "Electrical machinery",
            "32000000": "Radio and communication equipment",
            "34000000": "Transport equipment",
            "38000000": "Laboratory equipment",
            "39000000": "Furniture",
            "42000000": "Industrial machinery",
            "44000000": "Construction structures and materials",
            "48000000": "Software packages",
        }

        # Try exact match first, then prefix match
        if cpv_code in cpv_descriptions:
            return cpv_descriptions[cpv_code]

        # Try 8-digit prefix
        if len(cpv_code) >= 8:
            prefix_8 = cpv_code[:8]
            if prefix_8 in cpv_descriptions:
                return cpv_descriptions[prefix_8]

        return None

    except Exception as e:
        print(f"Error fetching CPV description: {e}")
        return None


# ============================================================================
# BID ADVISOR ENDPOINT
# ============================================================================

@router.get("/bid-advisor/{number}/{year}", response_model=BidAdvisorResponse,
            dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_bid_advisor(
    number: str,
    year: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI-powered bid advisor for tender pricing strategy

    Analyzes historical data and provides bid recommendations:
    - Aggressive: Lower price, higher risk
    - Balanced: Median market price
    - Safe: Conservative price, lower risk

    Args:
        number: Tender number (e.g., "08-9876")
        year: Tender year (e.g., "2024")

    Returns:
        BidAdvisorResponse with recommendations and market analysis
    """
    tender_id = f"{number}/{year}"

    # ========================================================================
    # 1. FETCH CURRENT TENDER DATA
    # ========================================================================
    tender_query = text("""
        SELECT
            tender_id,
            title,
            estimated_value_mkd,
            actual_value_mkd,
            cpv_code,
            category,
            procuring_entity,
            status,
            num_bidders
        FROM tenders
        WHERE tender_id = :tender_id
    """)

    result = await db.execute(tender_query, {"tender_id": tender_id})
    tender = result.fetchone()

    if not tender:
        raise HTTPException(
            status_code=404,
            detail=f"Tender {tender_id} not found"
        )

    (tender_id, title, estimated_value_mkd, actual_value_mkd,
     cpv_code, category, procuring_entity, status, num_bidders) = tender

    # ========================================================================
    # 2. FIND SIMILAR TENDERS (BY CPV CODE OR CATEGORY)
    # ========================================================================
    similar_tenders_query = text("""
        SELECT
            t.tender_id,
            t.title,
            t.estimated_value_mkd,
            t.actual_value_mkd,
            t.winner,
            t.cpv_code,
            t.category,
            t.publication_date,
            t.procuring_entity,
            t.num_bidders
        FROM tenders t
        WHERE (
            (t.cpv_code = :cpv_code OR t.category = :category)
            OR (t.cpv_code LIKE :cpv_prefix AND t.cpv_code IS NOT NULL)
        )
        AND (t.status = 'awarded' OR t.status = 'completed')
        AND t.publication_date > CURRENT_DATE - INTERVAL '2 years'
        AND t.actual_value_mkd IS NOT NULL
        AND t.actual_value_mkd > 0
        AND t.tender_id != :tender_id
        ORDER BY t.publication_date DESC
        LIMIT 50
    """)

    # CPV prefix for broader matching (e.g., "33000000" -> "33%")
    cpv_prefix = f"{cpv_code[:2]}%" if cpv_code and len(cpv_code) >= 2 else None

    result = await db.execute(similar_tenders_query, {
        "cpv_code": cpv_code,
        "category": category,
        "cpv_prefix": cpv_prefix,
        "tender_id": tender_id
    })
    similar_tenders = result.fetchall()

    # ========================================================================
    # 3. GET ALL BIDDERS FOR SIMILAR TENDERS
    # ========================================================================
    if similar_tenders:
        similar_tender_ids = [t[0] for t in similar_tenders]

        # Create placeholders for the IN clause
        placeholders = ', '.join([f':tid_{i}' for i in range(len(similar_tender_ids))])

        bidders_query = text(f"""
            SELECT
                tb.company_name,
                tb.bid_amount_mkd,
                tb.is_winner,
                tb.rank,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.tender_id,
                t.procuring_entity
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.tender_id IN ({placeholders})
            AND tb.bid_amount_mkd IS NOT NULL
            AND tb.bid_amount_mkd > 0
            ORDER BY t.publication_date DESC
        """)

        # Build params dict dynamically
        params = {f'tid_{i}': tid for i, tid in enumerate(similar_tender_ids)}

        result = await db.execute(bidders_query, params)
        all_bidders = result.fetchall()
    else:
        all_bidders = []

    # ========================================================================
    # 3.5 FETCH PER-ITEM PRICES FOR CURRENT TENDER AND SIMILAR TENDERS
    # ========================================================================
    item_prices = []

    # Get items from product_items table for current tender
    current_items_query = text(f"""
        SELECT
            pi.name,
            pi.unit_price,
            pi.quantity,
            pi.unit,
            pi.total_price
        FROM product_items pi
        WHERE pi.tender_id = :tender_id
          AND pi.unit_price IS NOT NULL
            {product_quality_filter("pi", "strict")}
        LIMIT 20
    """)

    try:
        result = await db.execute(current_items_query, {"tender_id": tender_id})
        current_items = result.fetchall()
        for row in current_items:
            item_prices.append({
                "item_name": row[0],
                "unit_price": float(row[1]) if row[1] else None,
                "quantity": float(row[2]) if row[2] else None,
                "unit": row[3],
                "total_price": float(row[4]) if row[4] else None,
                "source": "current_tender"
            })
    except Exception as e:
        logger.warning(f"Failed to fetch current tender items: {e}")

    # Get market benchmark prices for similar items
    if category or cpv_code:
        benchmark_query = text(f"""
            SELECT
                pi.name as item_name,
                AVG(pi.unit_price) as avg_price,
                MIN(pi.unit_price) as min_price,
                MAX(pi.unit_price) as max_price,
                COUNT(*) as occurrences,
                pi.unit
            FROM product_items pi
            JOIN tenders t ON pi.tender_id = t.tender_id
            WHERE (t.cpv_code = :cpv_code OR t.category = :category)
              AND pi.unit_price IS NOT NULL
              AND pi.unit_price > 0
              AND t.publication_date > CURRENT_DATE - INTERVAL '2 years'
                {product_quality_filter("pi", "strict")}
            GROUP BY pi.name, pi.unit
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
            LIMIT 15
        """)

        try:
            result = await db.execute(benchmark_query, {
                "cpv_code": cpv_code,
                "category": category
            })
            benchmark_items = result.fetchall()
            for row in benchmark_items:
                item_prices.append({
                    "item_name": row[0],
                    "avg_price": float(row[1]) if row[1] else None,
                    "min_price": float(row[2]) if row[2] else None,
                    "max_price": float(row[3]) if row[3] else None,
                    "occurrences": row[4],
                    "unit": row[5],
                    "source": "market_benchmark"
                })
        except Exception as e:
            logger.warning(f"Failed to fetch benchmark prices: {e}")

    # ========================================================================
    # 4. CALCULATE STATISTICS
    # ========================================================================
    winning_bids = []
    all_bids = []
    discounts = []  # (estimated - winning) / estimated * 100
    bidder_stats = {}  # company_name -> {bids, wins, total_value}

    for bidder in all_bidders:
        (company_name, bid_amount, is_winner, rank,
         est_value, actual_value, t_id, proc_entity) = bidder

        all_bids.append(float(bid_amount))

        if is_winner:
            winning_bids.append(float(bid_amount))

            # Calculate discount if estimated value exists
            if est_value and est_value > 0:
                discount_pct = ((float(est_value) - float(bid_amount)) / float(est_value)) * 100
                discounts.append(discount_pct)

        # Track bidder stats
        if company_name:
            if company_name not in bidder_stats:
                bidder_stats[company_name] = {
                    'bids': 0,
                    'wins': 0,
                    'total_bid_value': 0,
                    'total_won_value': 0
                }

            bidder_stats[company_name]['bids'] += 1
            bidder_stats[company_name]['total_bid_value'] += float(bid_amount)

            if is_winner:
                bidder_stats[company_name]['wins'] += 1
                bidder_stats[company_name]['total_won_value'] += float(bid_amount)

    # Calculate market statistics
    historical_data = {
        "similar_tenders": len(similar_tenders),
        "total_bids_analyzed": len(all_bids),
        "winning_bids_count": len(winning_bids),
        "avg_winning_bid": round(statistics.mean(winning_bids), 2) if winning_bids else None,
        "median_winning_bid": round(statistics.median(winning_bids), 2) if winning_bids else None,
        "min_winning_bid": round(min(winning_bids), 2) if winning_bids else None,
        "max_winning_bid": round(max(winning_bids), 2) if winning_bids else None,
        "std_dev": round(statistics.stdev(winning_bids), 2) if len(winning_bids) > 1 else None
    }

    market_analysis = {
        "avg_discount_percentage": round(statistics.mean(discounts), 2) if discounts else None,
        "typical_bidders_per_tender": round(statistics.mean([t[9] or 0 for t in similar_tenders]), 1) if similar_tenders else None,
        "price_trend": "stable",  # Will be enhanced by AI
        "competition_level": "high" if len(all_bids) / max(len(similar_tenders), 1) > 3 else "medium"
    }

    # ========================================================================
    # 5. COMPETITOR INSIGHTS
    # ========================================================================
    competitor_insights = []

    for company_name, stats in sorted(
        bidder_stats.items(),
        key=lambda x: x[1]['wins'],
        reverse=True
    )[:10]:
        win_rate = (stats['wins'] / stats['bids'] * 100) if stats['bids'] > 0 else 0
        avg_bid = stats['total_bid_value'] / stats['bids'] if stats['bids'] > 0 else 0
        avg_discount = None

        # Calculate average discount for this company
        company_discounts = []
        for bidder in all_bidders:
            if bidder[0] == company_name and bidder[2]:  # is_winner
                if bidder[4] and bidder[4] > 0:  # has estimated_value
                    disc = ((float(bidder[4]) - float(bidder[1])) / float(bidder[4])) * 100
                    company_discounts.append(disc)

        if company_discounts:
            avg_discount = round(statistics.mean(company_discounts), 2)

        competitor_insights.append({
            "company": company_name,
            "total_bids": stats['bids'],
            "total_wins": stats['wins'],
            "win_rate": round(win_rate, 1),
            "avg_bid_mkd": round(avg_bid, 2),
            "avg_discount_percentage": avg_discount
        })

    # ========================================================================
    # 6. GENERATE AI-POWERED RECOMMENDATIONS
    # ========================================================================
    recommendations = []
    ai_summary = ""

    if GEMINI_AVAILABLE and winning_bids:
        try:
            model = genai.GenerativeModel(GEMINI_MODEL)

            # Add date context
            date_context = get_ai_date_context()

            # Prepare context for AI
            context = f"""{date_context}

Анализирај ги следниве историски податоци за тендерско наддавање и генерирај препораки за цена на понуда.

ТЕКОВЕН ТЕНДЕР:
- Тендер ID: {tender_id}
- Наслов: {title[:150]}
- Проценета вредност: {estimated_value_mkd:,.0f} МКД
- CPV Код: {cpv_code}
- Категорија: {category}
- Наддавачи: {num_bidders or 'непознато'}

ИСТОРИСКА АНАЛИЗА (последни 2 години, {len(similar_tenders)} слични тендери):
- Вкупно понуди анализирани: {len(all_bids)}
- Победнички понуди: {len(winning_bids)}
- Просечна победничка понуда: {historical_data['avg_winning_bid']:,.0f} МКД
- Медијана победничка понуда: {historical_data['median_winning_bid']:,.0f} МКД
- Минимална победничка понуда: {historical_data['min_winning_bid']:,.0f} МКД
- Максимална победничка понуда: {historical_data['max_winning_bid']:,.0f} МКД
- Просечен попуст: {market_analysis['avg_discount_percentage']:.1f}%

ТОП КОНКУРЕНТИ:
{chr(10).join([f"- {c['company']}: {c['total_wins']}/{c['total_bids']} победи ({c['win_rate']:.1f}%), просек {c['avg_bid_mkd']:,.0f} МКД" for c in competitor_insights[:5]])}

ПАЗАРНИ ЦЕНИ ПО АРТИКЛИ (ако се достапни):
{chr(10).join([f"- {item['item_name'][:50]}: просек {item.get('avg_price', item.get('unit_price', 0)):,.0f} МКД/{item.get('unit', 'ед.')} (мин: {item.get('min_price', 0):,.0f}, макс: {item.get('max_price', 0):,.0f})" for item in item_prices[:10] if item.get('avg_price') or item.get('unit_price')]) or 'Нема достапни податоци за единечни цени'}

ГЕНЕРИРАЈ 3 СТРАТЕГИИ ЗА ПОНУДА:

1. АГРЕСИВНА стратегија (ниска цена, висок ризик):
   - Препорачана понуда: [износ во МКД]
   - Веројатност за победа: [0.X број помеѓу 0 и 1]
   - Образложение: [1-2 реченици зошто е ова добра/лоша стратегија]

2. БАЛАНСИРАНА стратегија (средна цена, умерен ризик):
   - Препорачана понуда: [износ во МКД]
   - Веројатност за победа: [0.X број помеѓу 0 и 1]
   - Образложение: [1-2 реченици]

3. БЕЗБЕДНА стратегија (висока цена, низок ризик):
   - Препорачана понуда: [износ во МКД]
   - Веројатност за победа: [0.X број помеѓу 0 и 1]
   - Образложение: [1-2 реченици]

ЗАВРШНА АНАЛИЗА:
[2-3 реченици со клучни согледувања за пазарот, конкуренцијата и препораки]

ОДГОВОРИ ВО СЛЕДНИОТ JSON ФОРМАТ:
{{
  "strategies": [
    {{
      "strategy": "aggressive",
      "recommended_bid": 123456.78,
      "win_probability": 0.45,
      "reasoning": "објаснување на македонски"
    }},
    {{
      "strategy": "balanced",
      "recommended_bid": 234567.89,
      "win_probability": 0.65,
      "reasoning": "објаснување на македонски"
    }},
    {{
      "strategy": "safe",
      "recommended_bid": 345678.90,
      "win_probability": 0.85,
      "reasoning": "објаснување на македонски"
    }}
  ],
  "summary": "завршна анализа на македонски (2-3 реченици)"
}}

ВАЖНО: Препорачаните понуди МОРА да бидат базирани на историските податоци. Агресивната треба да биде пониска од медијаната, балансираната околу медијаната, а безбедната повисока."""

            # Relaxed safety settings for business content
            response = model.generate_content(context)
            try:
                response_text = response.text
            except ValueError:
                response_text = "{}"

            # Parse JSON from response
            import json
            import re

            # Extract JSON from response (may have markdown code blocks)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())

                # Build recommendations
                for strategy in parsed.get('strategies', []):
                    recommendations.append({
                        "strategy": strategy.get('strategy', ''),
                        "recommended_bid": float(strategy.get('recommended_bid', 0)),
                        "win_probability": float(strategy.get('win_probability', 0.5)),
                        "reasoning": strategy.get('reasoning', '')
                    })

                ai_summary = parsed.get('summary', '')

        except Exception as e:
            print(f"AI recommendation failed: {e}")
            import traceback
            traceback.print_exc()
            # Continue with fallback recommendations

    # ========================================================================
    # 7. FALLBACK RECOMMENDATIONS (IF AI FAILS OR UNAVAILABLE)
    # ========================================================================
    if not recommendations and winning_bids:
        median_bid = statistics.median(winning_bids)
        std_dev = statistics.stdev(winning_bids) if len(winning_bids) > 1 else median_bid * 0.1

        # Aggressive: 1 std dev below median
        aggressive_bid = max(median_bid - std_dev, min(winning_bids))

        # Balanced: median
        balanced_bid = median_bid

        # Safe: 1 std dev above median
        safe_bid = min(median_bid + std_dev, max(winning_bids))

        recommendations = [
            {
                "strategy": "aggressive",
                "recommended_bid": round(aggressive_bid, 2),
                "win_probability": 0.45,
                "reasoning": f"Понуда под пазарната медијана ({median_bid:,.0f} МКД). Висок ризик, но потенцијално конкурентна цена."
            },
            {
                "strategy": "balanced",
                "recommended_bid": round(balanced_bid, 2),
                "win_probability": 0.65,
                "reasoning": f"Медијана на пазарот. Балансира цена и веројатност за победа."
            },
            {
                "strategy": "safe",
                "recommended_bid": round(safe_bid, 2),
                "win_probability": 0.85,
                "reasoning": f"Конзервативна понуда над медијаната. Поголема сигурност за добивање договор."
            }
        ]

        ai_summary = f"Анализирани се {len(similar_tenders)} слични тендери со медијана на победничка понуда од {median_bid:,.0f} МКД. Пазарот покажува {market_analysis['competition_level']} ниво на конкуренција со просечен попуст од {market_analysis['avg_discount_percentage']:.1f}%."

    # If no historical data at all
    if not recommendations:
        if estimated_value_mkd:
            recommendations = [
                {
                    "strategy": "aggressive",
                    "recommended_bid": round(float(estimated_value_mkd) * 0.85, 2),
                    "win_probability": 0.40,
                    "reasoning": "Нема доволно историски податоци. Препорака базирана на проценета вредност со 15% попуст."
                },
                {
                    "strategy": "balanced",
                    "recommended_bid": round(float(estimated_value_mkd) * 0.95, 2),
                    "win_probability": 0.60,
                    "reasoning": "Препорака базирана на проценета вредност со 5% попуст."
                },
                {
                    "strategy": "safe",
                    "recommended_bid": round(float(estimated_value_mkd) * 1.00, 2),
                    "win_probability": 0.80,
                    "reasoning": "Понуда на ниво на проценета вредност. Безбедна опција."
                }
            ]
            ai_summary = "Недостасуваат историски податоци за споредба. Препораките се базирани на проценетата вредност на тендерот."
        else:
            raise HTTPException(
                status_code=404,
                detail="No historical data found and no estimated value available for this tender"
            )

    # ========================================================================
    # 8. BUILD RESPONSE
    # ========================================================================
    return BidAdvisorResponse(
        tender_id=tender_id,
        tender_title=title,
        estimated_value=float(estimated_value_mkd) if estimated_value_mkd else None,
        cpv_code=cpv_code,
        category=category,
        procuring_entity=procuring_entity,
        market_analysis=market_analysis,
        historical_data=historical_data,
        recommendations=recommendations,
        competitor_insights=competitor_insights,
        item_prices=item_prices if item_prices else None,
        ai_summary=ai_summary,
        generated_at=datetime.utcnow().isoformat()
    )


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/pricing-health")
async def pricing_health():
    """Health check for pricing API"""
    return {
        "status": "healthy",
        "service": "pricing-api",
        "ai_available": GEMINI_AVAILABLE,
        "endpoints": {
            "/api/ai/price-history/{cpv_code}": "Get historical price aggregation",
            "/api/ai/bid-advisor/{number}/{year}": "Get AI-powered bid recommendations"
        }
    }
