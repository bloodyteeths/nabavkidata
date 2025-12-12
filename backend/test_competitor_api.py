"""
Test script for Competitor Tracking API endpoints
Phase 5.1 - UI Refactor Roadmap
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import os

# Database connection
DATABASE_URL = "postgresql+asyncpg://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com/nabavkidata"

async def test_queries():
    """Test all SQL queries used by the API"""
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("COMPETITOR TRACKING API - Query Tests")
        print("=" * 80)
        
        # Test 1: Search companies query
        print("\n1. Testing search companies query...")
        search_query = text("""
            SELECT
                tb.company_name,
                tb.company_tax_id as tax_id,
                COUNT(*) as total_bids,
                COUNT(*) FILTER (WHERE tb.is_winner = true) as total_wins,
                ROUND((COUNT(*) FILTER (WHERE tb.is_winner = true)::numeric / NULLIF(COUNT(*), 0) * 100), 2) as win_rate,
                SUM(tb.bid_amount_mkd) FILTER (WHERE tb.is_winner = true) as total_contract_value
            FROM tender_bidders tb
            WHERE tb.company_name ILIKE :search_pattern
            GROUP BY tb.company_name, tb.company_tax_id
            ORDER BY total_wins DESC, total_bids DESC
            LIMIT :limit
        """)
        
        result = await db.execute(search_query, {
            "search_pattern": "%МАКЕДОНСКИ%",
            "limit": 5
        })
        rows = result.fetchall()
        print(f"   Found {len(rows)} companies matching search")
        for row in rows[:3]:
            print(f"   - {row.company_name[:50]}... (Bids: {row.total_bids}, Wins: {row.total_wins})")
        
        # Test 2: Get competitor stats
        print("\n2. Testing competitor stats query...")
        test_company = rows[0].company_name if rows else "Unknown"
        
        stats_query = text("""
            SELECT
                company_name,
                total_bids,
                total_wins,
                win_rate,
                avg_bid_discount,
                top_cpv_codes,
                top_categories,
                last_updated
            FROM competitor_stats
            WHERE company_name = :company_name
        """)
        
        result = await db.execute(stats_query, {"company_name": test_company})
        row = result.fetchone()
        if row:
            print(f"   Company: {row.company_name[:50]}...")
            print(f"   Total Bids: {row.total_bids}")
            print(f"   Total Wins: {row.total_wins}")
            print(f"   Win Rate: {row.win_rate}%")
            print(f"   Avg Discount: {row.avg_bid_discount}%")
            print(f"   Last Updated: {row.last_updated}")
        else:
            print(f"   No stats found for {test_company}")
        
        # Test 3: Recent tenders query
        print("\n3. Testing recent tenders query...")
        recent_query = text("""
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                tb.bid_amount_mkd,
                t.estimated_value_mkd,
                tb.is_winner,
                tb.rank,
                t.closing_date,
                t.status
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_name = :company_name
            ORDER BY t.closing_date DESC NULLS LAST
            LIMIT 5
        """)
        
        result = await db.execute(recent_query, {"company_name": test_company})
        rows = result.fetchall()
        print(f"   Found {len(rows)} recent tenders")
        for row in rows[:3]:
            status = "WON" if row.is_winner else "BID"
            print(f"   - [{status}] {row.title[:40]}... (Rank: {row.rank})")
        
        # Test 4: List tracked competitors (simulated user)
        print("\n4. Testing list tracked competitors query...")
        # Create a test user first
        user_query = text("SELECT user_id FROM users LIMIT 1")
        user_result = await db.execute(user_query)
        user = user_result.fetchone()
        
        if user:
            list_query = text("""
                SELECT
                    tracking_id,
                    user_id,
                    company_name,
                    tax_id,
                    notes,
                    created_at
                FROM tracked_competitors
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """)
            
            result = await db.execute(list_query, {"user_id": str(user.user_id)})
            rows = result.fetchall()
            print(f"   User {user.user_id} is tracking {len(rows)} competitors")
        else:
            print("   No users found in database")
        
        # Test 5: Database table status
        print("\n5. Database table status...")
        status_query = text("""
            SELECT 'tracked_competitors' as table_name, COUNT(*) as row_count 
            FROM tracked_competitors
            UNION ALL
            SELECT 'competitor_stats', COUNT(*) FROM competitor_stats
            UNION ALL
            SELECT 'tender_bidders', COUNT(*) FROM tender_bidders
        """)
        
        result = await db.execute(status_query)
        for row in result:
            print(f"   {row.table_name}: {row.row_count} rows")
        
        print("\n" + "=" * 80)
        print("All queries executed successfully!")
        print("=" * 80)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_queries())
