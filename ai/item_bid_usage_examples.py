"""
Item Bids Usage Examples

This script demonstrates how to use the item_bids table and extraction logic
to answer critical questions like:
- "Who bid what price for surgical drapes?"
- "What did Company X offer for item Y?"
- "Which bidder had the lowest price per item?"

Usage:
    python item_bid_usage_examples.py
"""

import asyncio
import asyncpg
import os
from decimal import Decimal
from typing import List, Dict
import json
from dotenv import load_dotenv
load_dotenv()



# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'nabavki_user',
    'password': os.getenv('DB_PASSWORD', ''),
    'database': 'nabavkidata'
}


async def create_pool():
    """Create database connection pool"""
    return await asyncpg.create_pool(**DB_CONFIG, min_size=2, max_size=10)


# ============================================================================
# CRITICAL QUERY EXAMPLES
# ============================================================================

async def query_who_bid_for_item(pool: asyncpg.Pool, item_search: str):
    """
    Answer: "Who bid for [item]?"

    Example: "Who bid for surgical drapes?"
    """
    print(f"\n{'='*80}")
    print(f"QUERY: Who bid for '{item_search}'?")
    print(f"{'='*80}\n")

    async with pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                item_name,
                company_name,
                unit_price_mkd,
                quantity_offered,
                total_price_mkd,
                is_winner,
                rank,
                brand_model
            FROM v_item_bids_full
            WHERE
                item_name ILIKE $1
                OR item_name_mk ILIKE $1
            ORDER BY item_name, unit_price_mkd ASC
        """, f'%{item_search}%')

        if not results:
            print(f"No bids found for items matching '{item_search}'")
            return

        current_item = None
        for row in results:
            if row['item_name'] != current_item:
                current_item = row['item_name']
                print(f"\n📦 Item: {current_item}")
                print(f"   {'Company':<40} {'Unit Price':<15} {'Qty':<10} {'Total':<15} {'Winner':<8} {'Rank'}")
                print(f"   {'-'*100}")

            winner_mark = "✓" if row['is_winner'] else ""
            rank = row['rank'] or '-'
            qty = row['quantity_offered'] or '-'

            print(f"   {row['company_name'][:40]:<40} "
                  f"{row['unit_price_mkd']:>12,.2f} MKD "
                  f"{str(qty):<10} "
                  f"{row['total_price_mkd']:>12,.2f} MKD "
                  f"{winner_mark:<8} "
                  f"{rank}")


async def query_what_company_offered(pool: asyncpg.Pool, company_name: str, tender_id: str = None):
    """
    Answer: "What did Company X offer?"

    Example: "What did Medimpex offer for tender 12345?"
    """
    print(f"\n{'='*80}")
    print(f"QUERY: What did '{company_name}' offer" + (f" for tender {tender_id}?" if tender_id else "?"))
    print(f"{'='*80}\n")

    async with pool.acquire() as conn:
        if tender_id:
            results = await conn.fetch("""
                SELECT
                    tender_id,
                    tender_title,
                    item_name,
                    quantity_offered,
                    unit_price_mkd,
                    total_price_mkd,
                    brand_model,
                    is_winner,
                    rank
                FROM v_item_bids_full
                WHERE
                    company_name ILIKE $1
                    AND tender_id = $2
                ORDER BY unit_price_mkd DESC
            """, f'%{company_name}%', tender_id)
        else:
            results = await conn.fetch("""
                SELECT
                    tender_id,
                    tender_title,
                    item_name,
                    quantity_offered,
                    unit_price_mkd,
                    total_price_mkd,
                    brand_model,
                    is_winner
                FROM v_item_bids_full
                WHERE
                    company_name ILIKE $1
                ORDER BY tender_id, unit_price_mkd DESC
                LIMIT 50
            """, f'%{company_name}%')

        if not results:
            print(f"No offers found from companies matching '{company_name}'")
            return

        current_tender = None
        total_value = 0
        items_count = 0
        wins_count = 0

        for row in results:
            if row['tender_id'] != current_tender:
                current_tender = row['tender_id']
                print(f"\n🏛️  Tender: {row['tender_title'][:60]} ({row['tender_id']})")
                print(f"   {'Item':<40} {'Qty':<10} {'Unit Price':<15} {'Total':<15} {'Winner'}")
                print(f"   {'-'*100}")

            winner_mark = "✓" if row['is_winner'] else ""
            qty = row['quantity_offered'] or '-'

            print(f"   {row['item_name'][:40]:<40} "
                  f"{str(qty):<10} "
                  f"{row['unit_price_mkd']:>12,.2f} MKD "
                  f"{row['total_price_mkd']:>12,.2f} MKD "
                  f"{winner_mark}")

            total_value += float(row['total_price_mkd'] or 0)
            items_count += 1
            if row['is_winner']:
                wins_count += 1

        print(f"\n📊 Summary:")
        print(f"   Total items bid on: {items_count}")
        print(f"   Items won: {wins_count}")
        print(f"   Total bid value: {total_value:,.2f} MKD")


async def query_lowest_bidder_per_item(pool: asyncpg.Pool, tender_id: str):
    """
    Answer: "Who had the lowest price for each item?"

    Example: "Who had the lowest price for each item in tender 12345?"
    """
    print(f"\n{'='*80}")
    print(f"QUERY: Who had the lowest price for each item in tender {tender_id}?")
    print(f"{'='*80}\n")

    async with pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                item_name,
                total_bids,
                lowest_bidder,
                min_price,
                winner_name,
                winner_price,
                CASE
                    WHEN winner_price IS NOT NULL AND min_price IS NOT NULL
                    THEN ROUND(((winner_price - min_price) / min_price * 100)::numeric, 2)
                    ELSE NULL
                END as price_difference_percent
            FROM v_item_bid_comparison
            WHERE tender_id = $1
            AND total_bids > 0
            ORDER BY min_price DESC
        """, tender_id)

        if not results:
            print(f"No bids found for tender {tender_id}")
            return

        print(f"{'Item':<40} {'Bids':<6} {'Lowest Bidder':<30} {'Min Price':<15} {'Winner':<30} {'Winner Price':<15} {'Diff %'}")
        print(f"{'-'*150}")

        for row in results:
            lowest = row['lowest_bidder'][:30] if row['lowest_bidder'] else 'N/A'
            winner = row['winner_name'][:30] if row['winner_name'] else 'N/A'
            min_price = f"{row['min_price']:,.2f}" if row['min_price'] else 'N/A'
            winner_price = f"{row['winner_price']:,.2f}" if row['winner_price'] else 'N/A'
            diff = f"+{row['price_difference_percent']}%" if row['price_difference_percent'] else '-'

            print(f"{row['item_name'][:40]:<40} "
                  f"{row['total_bids']:<6} "
                  f"{lowest:<30} "
                  f"{min_price:<15} "
                  f"{winner:<30} "
                  f"{winner_price:<15} "
                  f"{diff}")


async def query_bid_comparison_table(pool: asyncpg.Pool, tender_id: str):
    """
    Generate a full bid comparison table (like in evaluation documents)

    Shows all bidders side-by-side for each item
    """
    print(f"\n{'='*80}")
    print(f"BID COMPARISON TABLE for Tender {tender_id}")
    print(f"{'='*80}\n")

    async with pool.acquire() as conn:
        # Get all items and their bids
        results = await conn.fetch("""
            SELECT
                item_name,
                all_bids
            FROM v_item_bid_comparison
            WHERE tender_id = $1
            AND total_bids > 0
            ORDER BY item_id
        """, tender_id)

        if not results:
            print(f"No bids found for tender {tender_id}")
            return

        for row in results:
            print(f"\n📦 {row['item_name']}")

            if row['all_bids']:
                bids = row['all_bids']
                print(f"   {'Company':<40} {'Unit Price':<15} {'Brand/Model':<30} {'Winner'}")
                print(f"   {'-'*110}")

                for bid in bids:
                    if bid:  # Filter out null entries
                        company = bid.get('company_name', 'N/A')[:40]
                        price = bid.get('unit_price_mkd', 0)
                        brand = bid.get('brand_model', '')[:30] if bid.get('brand_model') else '-'
                        winner = "✓" if bid.get('is_winner') else ""

                        print(f"   {company:<40} {price:>12,.2f} MKD {brand:<30} {winner}")


async def query_company_performance(pool: asyncpg.Pool, company_name: str = None):
    """
    Analyze company performance across item categories
    """
    print(f"\n{'='*80}")
    print(f"COMPANY PERFORMANCE ANALYSIS" + (f" for '{company_name}'" if company_name else ""))
    print(f"{'='*80}\n")

    async with pool.acquire() as conn:
        if company_name:
            results = await conn.fetch("""
                SELECT * FROM v_company_item_performance
                WHERE company_name ILIKE $1
                ORDER BY items_won DESC
            """, f'%{company_name}%')
        else:
            results = await conn.fetch("""
                SELECT * FROM v_company_item_performance
                ORDER BY total_value_won DESC
                LIMIT 20
            """)

        if not results:
            print("No performance data available")
            return

        print(f"{'Company':<40} {'Category':<25} {'Bids':<6} {'Won':<6} {'Win%':<8} {'Avg Price':<15} {'Total Won'}")
        print(f"{'-'*130}")

        for row in results:
            company = row['company_name'][:40]
            category = row['category'][:25] if row['category'] else 'N/A'

            print(f"{company:<40} "
                  f"{category:<25} "
                  f"{row['items_bid_on']:<6} "
                  f"{row['items_won']:<6} "
                  f"{row['win_rate_percent']:<8.1f} "
                  f"{row['avg_unit_price']:>12,.2f} "
                  f"{row['total_value_won']:>12,.0f}")


# ============================================================================
# DATA INSERTION EXAMPLES
# ============================================================================

async def insert_sample_bids(pool: asyncpg.Pool):
    """
    Insert sample item bids for testing

    This demonstrates how to manually insert bids (useful for data from APIs or manual entry)
    """
    print(f"\n{'='*80}")
    print(f"INSERTING SAMPLE ITEM BIDS")
    print(f"{'='*80}\n")

    # First, we need a tender, items, and bidders
    async with pool.acquire() as conn:
        # Check if we have any tenders
        tender = await conn.fetchrow("""
            SELECT tender_id FROM tenders LIMIT 1
        """)

        if not tender:
            print("No tenders found in database. Cannot insert sample bids.")
            return

        tender_id = tender['tender_id']
        print(f"Using tender: {tender_id}")

        # Get or create a sample item
        item = await conn.fetchrow("""
            SELECT id FROM product_items WHERE tender_id = $1 LIMIT 1
        """, tender_id)

        if not item:
            item = await conn.fetchrow("""
                INSERT INTO product_items (tender_id, name, quantity)
                VALUES ($1, 'Sample Surgical Drapes', 100)
                RETURNING id
            """, tender_id)

        item_id = item['id']
        print(f"Using item: {item_id}")

        # Create sample bidders
        bidders = []
        for company in ['Medimpex DOOEL', 'Alkaloid AD', 'Replek Farm DOOEL']:
            bidder = await conn.fetchrow("""
                INSERT INTO tender_bidders (tender_id, company_name)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                RETURNING bidder_id
            """, tender_id, company)

            if not bidder:
                bidder = await conn.fetchrow("""
                    SELECT bidder_id FROM tender_bidders
                    WHERE tender_id = $1 AND company_name = $2
                """, tender_id, company)

            bidders.append((bidder['bidder_id'], company))

        # Insert bids for each company
        prices = [Decimal('150.00'), Decimal('145.50'), Decimal('152.00')]

        for idx, (bidder_id, company) in enumerate(bidders):
            price = prices[idx]
            total = price * Decimal('100')  # quantity

            await conn.execute("""
                INSERT INTO item_bids (
                    tender_id, item_id, bidder_id, company_name,
                    quantity_offered, unit_price_mkd, total_price_mkd,
                    is_winner, rank,
                    extraction_source
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
                )
                ON CONFLICT (item_id, bidder_id)
                DO UPDATE SET
                    unit_price_mkd = EXCLUDED.unit_price_mkd,
                    total_price_mkd = EXCLUDED.total_price_mkd
            """, tender_id, item_id, bidder_id, company,
                Decimal('100'), price, total,
                idx == 1,  # Second company wins (lowest price)
                idx + 1,  # Rank
                'manual'
            )

            print(f"   ✓ Inserted bid: {company} - {price} MKD/unit")

        print(f"\n✅ Successfully inserted {len(bidders)} sample bids")
        return tender_id


# ============================================================================
# MAIN DEMO
# ============================================================================

async def main():
    """Run all example queries"""
    pool = await create_pool()

    try:
        # Insert sample data first
        tender_id = await insert_sample_bids(pool)

        if tender_id:
            # Run example queries
            await query_who_bid_for_item(pool, 'surgical')
            await query_lowest_bidder_per_item(pool, tender_id)
            await query_bid_comparison_table(pool, tender_id)

        # These work across all tenders
        await query_company_performance(pool)

        print(f"\n{'='*80}")
        print("ADDITIONAL QUERY EXAMPLES:")
        print(f"{'='*80}\n")
        print("""
# 1. Find all bids for a specific item name:
SELECT * FROM v_item_bids_full
WHERE item_name ILIKE '%хируршки%'
ORDER BY unit_price_mkd;

# 2. Compare prices across bidders for an item:
SELECT * FROM v_item_bid_comparison
WHERE item_name ILIKE '%gaza%';

# 3. Find items where winner wasn't the lowest bidder:
SELECT
    item_name,
    winner_name,
    winner_price,
    lowest_bidder,
    min_price,
    (winner_price - min_price) as price_difference
FROM v_item_bid_comparison
WHERE winner_price > min_price
ORDER BY price_difference DESC;

# 4. Company win rate analysis:
SELECT * FROM v_company_item_performance
ORDER BY win_rate_percent DESC;

# 5. Find suspicious pricing (outliers):
SELECT
    ib.*,
    comp.avg_price,
    comp.price_stddev,
    (ib.unit_price_mkd - comp.avg_price) / NULLIF(comp.price_stddev, 0) as z_score
FROM item_bids ib
JOIN v_item_bid_comparison comp ON ib.item_id = comp.item_id
WHERE ABS((ib.unit_price_mkd - comp.avg_price) / NULLIF(comp.price_stddev, 0)) > 2
ORDER BY z_score DESC;
        """)

    finally:
        await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
