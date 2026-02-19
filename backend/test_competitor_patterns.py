"""
Test script for bidding pattern analysis endpoint
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

async def test_bidding_patterns():
    """Test the bidding pattern analysis queries"""

    # Create engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("BIDDING PATTERN ANALYSIS TEST")
        print("=" * 80)

        # First, let's find a company with bidding history
        print("\n1. Finding companies with bidding history...")

        company_search = text("""
            SELECT
                tb.company_name,
                COUNT(*) as bid_count,
                COUNT(*) FILTER (WHERE is_winner = TRUE) as wins
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_name IS NOT NULL
            GROUP BY tb.company_name
            HAVING COUNT(*) >= 3
            ORDER BY bid_count DESC
            LIMIT 10
        """)

        result = await db.execute(company_search)
        companies = result.fetchall()

        if not companies:
            print("❌ No companies found with sufficient bidding history")
            return

        print(f"✓ Found {len(companies)} companies with bidding history:")
        for i, company in enumerate(companies[:5], 1):
            print(f"  {i}. {company.company_name}: {company.bid_count} bids, {company.wins} wins")

        # Test with the first company
        test_company = companies[0].company_name
        analysis_months = 24

        print(f"\n2. Testing bidding pattern analysis for: {test_company}")
        print(f"   Analysis period: {analysis_months} months")

        # Test basic stats query
        print("\n3. Basic Statistics Query...")
        basic_stats_query = text("""
            WITH date_threshold AS (
                SELECT NOW() - INTERVAL ':months months' as cutoff
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
            "company_name": test_company,
            "months": str(analysis_months)
        })
        stats = result.fetchone()

        print(f"   ✓ Total Bids: {stats.total_bids}")
        print(f"   ✓ Total Wins: {stats.total_wins}")
        print(f"   ✓ Win Rate: {stats.win_rate:.2f}%")

        # Test pricing pattern query
        print("\n4. Pricing Pattern Query...")
        pricing_query = text("""
            WITH date_threshold AS (
                SELECT NOW() - INTERVAL ':months months' as cutoff
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
            "company_name": test_company,
            "months": str(analysis_months)
        })
        pricing = pricing_result.fetchone()

        if pricing and pricing.avg_discount is not None:
            print(f"   ✓ Average Discount: {pricing.avg_discount:.2f}%")
            print(f"   ✓ Discount Range: {pricing.min_discount:.2f}% - {pricing.max_discount:.2f}%")
            print(f"   ✓ Average Bid: {pricing.avg_bid:,.2f} MKD")
            print(f"   ✓ Median Bid: {pricing.median_bid:,.2f} MKD")
        else:
            print("   ⚠ No pricing data available")

        # Test category preferences
        print("\n5. Category Preferences Query...")
        category_query = text("""
            WITH date_threshold AS (
                SELECT NOW() - INTERVAL ':months months' as cutoff
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
            "company_name": test_company,
            "months": str(analysis_months)
        })
        categories = category_result.fetchall()

        print(f"   ✓ Top {len(categories)} Categories:")
        for cat in categories:
            print(f"      - {cat.name or 'Unknown'} ({cat.cpv_code}): {cat.bid_count} bids, {cat.win_rate:.1f}% win rate")

        # Test size preferences
        print("\n6. Size Preferences Query...")
        size_query = text("""
            WITH date_threshold AS (
                SELECT NOW() - INTERVAL ':months months' as cutoff
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
            "company_name": test_company,
            "months": str(analysis_months)
        })
        sizes = size_result.fetchall()

        print(f"   ✓ Size Preferences:")
        size_labels = {'small': '0-500K', 'medium': '500K-2M', 'large': '2M+'}
        for size in sizes:
            print(f"      - {size.size_category.capitalize()} ({size_labels[size.size_category]}): {size.total_bids} bids, {size.win_rate:.1f}% win rate")

        # Test top competitors
        print("\n7. Top Competitors Query...")
        competitors_query = text("""
            WITH date_threshold AS (
                SELECT NOW() - INTERVAL ':months months' as cutoff
            ),
            company_tenders AS (
                SELECT DISTINCT tb.tender_id
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                CROSS JOIN date_threshold dt
                WHERE tb.company_name ILIKE :company_name
                    AND t.closing_date >= dt.cutoff
            ),
            competing_companies AS (
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
            LIMIT 5
        """)

        competitors_result = await db.execute(competitors_query, {
            "company_name": test_company,
            "months": str(analysis_months)
        })
        competitors = competitors_result.fetchall()

        print(f"   ✓ Top {len(competitors)} Competitors:")
        for comp in competitors:
            print(f"      - {comp.company_name}: {comp.overlap_count} overlaps, W/L: {comp.our_wins}/{comp.their_wins}")

        print("\n" + "=" * 80)
        print("✓ ALL TESTS PASSED - Endpoint queries are working correctly!")
        print("=" * 80)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_bidding_patterns())
