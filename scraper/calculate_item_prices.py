#!/usr/bin/env python3
"""
Calculate estimated item prices from tender totals and winning bids.

Since the e-pazar API doesn't provide item-level prices, we estimate them by:
1. Using winning bid totals divided by item count (simple average)
2. Using awarded_value_mkd from tender if winning bid unavailable
3. Applying quantity weighting when quantity data is available

This provides approximate price intelligence for similar item searches.
"""

import asyncio
import asyncpg
import os
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


async def calculate_simple_prices(conn):
    """
    Simple calculation: tender_total / item_count
    This distributes the total value evenly across all items.
    """
    logger.info("Calculating simple average prices from tender totals...")

    # Update items where we have winning bid data
    updated_from_bids = await conn.execute("""
        WITH winning_bids AS (
            SELECT
                o.tender_id,
                SUM(o.total_bid_mkd) as total_winning_bid,
                COUNT(DISTINCT o.supplier_name) as winner_count
            FROM epazar_offers o
            WHERE o.is_winner = true AND o.total_bid_mkd > 0
            GROUP BY o.tender_id
        ),
        tender_item_counts AS (
            SELECT
                tender_id,
                COUNT(*) as item_count,
                SUM(COALESCE(quantity, 1)) as total_quantity
            FROM epazar_items
            GROUP BY tender_id
        )
        UPDATE epazar_items i
        SET
            estimated_unit_price_mkd = ROUND(
                wb.total_winning_bid / NULLIF(tic.total_quantity, 0),
                2
            ),
            estimated_total_price_mkd = ROUND(
                (wb.total_winning_bid / NULLIF(tic.item_count, 0)) * COALESCE(i.quantity, 1),
                2
            ),
            updated_at = NOW()
        FROM winning_bids wb
        JOIN tender_item_counts tic ON wb.tender_id = tic.tender_id
        WHERE i.tender_id = wb.tender_id
          AND i.estimated_unit_price_mkd IS NULL
    """)
    logger.info(f"Updated items from winning bids: {updated_from_bids}")

    # For items without winning bids, use awarded_value_mkd from tender
    updated_from_awarded = await conn.execute("""
        WITH tender_item_counts AS (
            SELECT
                tender_id,
                COUNT(*) as item_count,
                SUM(COALESCE(quantity, 1)) as total_quantity
            FROM epazar_items
            GROUP BY tender_id
        )
        UPDATE epazar_items i
        SET
            estimated_unit_price_mkd = ROUND(
                t.awarded_value_mkd / NULLIF(tic.total_quantity, 0),
                2
            ),
            estimated_total_price_mkd = ROUND(
                (t.awarded_value_mkd / NULLIF(tic.item_count, 0)) * COALESCE(i.quantity, 1),
                2
            ),
            updated_at = NOW()
        FROM epazar_tenders t
        JOIN tender_item_counts tic ON t.tender_id = tic.tender_id
        WHERE i.tender_id = t.tender_id
          AND i.estimated_unit_price_mkd IS NULL
          AND t.awarded_value_mkd > 0
    """)
    logger.info(f"Updated items from awarded values: {updated_from_awarded}")

    return updated_from_bids, updated_from_awarded


async def calculate_category_based_prices(conn):
    """
    For items still without prices, use category/CPV code averages.
    This provides broader market estimates based on similar items.
    """
    logger.info("Calculating category-based prices for remaining items...")

    # Calculate average prices per CPV code from known prices
    updated = await conn.execute("""
        WITH cpv_averages AS (
            SELECT
                SUBSTRING(cpv_code FROM 1 FOR 5) as cpv_prefix,
                AVG(estimated_unit_price_mkd) as avg_unit_price,
                COUNT(*) as sample_size
            FROM epazar_items
            WHERE estimated_unit_price_mkd > 0
              AND cpv_code IS NOT NULL
            GROUP BY SUBSTRING(cpv_code FROM 1 FOR 5)
            HAVING COUNT(*) >= 3  -- Need at least 3 samples
        )
        UPDATE epazar_items i
        SET
            estimated_unit_price_mkd = ROUND(ca.avg_unit_price, 2),
            estimated_total_price_mkd = ROUND(ca.avg_unit_price * COALESCE(i.quantity, 1), 2),
            updated_at = NOW()
        FROM cpv_averages ca
        WHERE SUBSTRING(i.cpv_code FROM 1 FOR 5) = ca.cpv_prefix
          AND i.estimated_unit_price_mkd IS NULL
    """)
    logger.info(f"Updated items from CPV averages: {updated}")
    return updated


async def calculate_name_similarity_prices(conn):
    """
    For items still without prices, use similar item name averages.
    Uses first 20 chars of item name as similarity key.
    """
    logger.info("Calculating name-based prices for remaining items...")

    updated = await conn.execute("""
        WITH name_averages AS (
            SELECT
                LOWER(SUBSTRING(item_name FROM 1 FOR 20)) as name_prefix,
                AVG(estimated_unit_price_mkd) as avg_unit_price,
                COUNT(*) as sample_size
            FROM epazar_items
            WHERE estimated_unit_price_mkd > 0
              AND item_name IS NOT NULL
              AND LENGTH(item_name) >= 10
            GROUP BY LOWER(SUBSTRING(item_name FROM 1 FOR 20))
            HAVING COUNT(*) >= 2
        )
        UPDATE epazar_items i
        SET
            estimated_unit_price_mkd = ROUND(na.avg_unit_price, 2),
            estimated_total_price_mkd = ROUND(na.avg_unit_price * COALESCE(i.quantity, 1), 2),
            updated_at = NOW()
        FROM name_averages na
        WHERE LOWER(SUBSTRING(i.item_name FROM 1 FOR 20)) = na.name_prefix
          AND i.estimated_unit_price_mkd IS NULL
    """)
    logger.info(f"Updated items from name similarity: {updated}")
    return updated


async def print_stats(conn):
    """Print current price coverage statistics."""
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_items,
            COUNT(estimated_unit_price_mkd) FILTER (WHERE estimated_unit_price_mkd > 0) as has_unit_price,
            COUNT(estimated_total_price_mkd) FILTER (WHERE estimated_total_price_mkd > 0) as has_total_price,
            ROUND(AVG(estimated_unit_price_mkd) FILTER (WHERE estimated_unit_price_mkd > 0), 2) as avg_unit_price,
            MIN(estimated_unit_price_mkd) FILTER (WHERE estimated_unit_price_mkd > 0) as min_unit_price,
            MAX(estimated_unit_price_mkd) FILTER (WHERE estimated_unit_price_mkd > 0) as max_unit_price
        FROM epazar_items
    """)

    print("\n=== Item Price Statistics ===")
    print(f"Total items: {stats['total_items']}")
    print(f"Items with unit price: {stats['has_unit_price']} ({100*stats['has_unit_price']/stats['total_items']:.1f}%)")
    print(f"Items with total price: {stats['has_total_price']} ({100*stats['has_total_price']/stats['total_items']:.1f}%)")
    if stats['avg_unit_price']:
        print(f"Avg unit price: {stats['avg_unit_price']:,.2f} MKD")
        print(f"Min unit price: {stats['min_unit_price']:,.2f} MKD")
        print(f"Max unit price: {stats['max_unit_price']:,.2f} MKD")


async def main():
    """Run all price calculation steps."""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        print("=== E-Pazar Item Price Calculator ===\n")

        # Print initial stats
        print("Before calculation:")
        await print_stats(conn)

        # Run calculations in order of confidence
        await calculate_simple_prices(conn)
        await calculate_category_based_prices(conn)
        await calculate_name_similarity_prices(conn)

        # Print final stats
        print("\nAfter calculation:")
        await print_stats(conn)

        # Show sample of calculated prices
        samples = await conn.fetch("""
            SELECT
                item_name,
                quantity,
                unit,
                estimated_unit_price_mkd,
                estimated_total_price_mkd
            FROM epazar_items
            WHERE estimated_unit_price_mkd > 0
            ORDER BY updated_at DESC
            LIMIT 10
        """)

        print("\n=== Sample Calculated Prices ===")
        for s in samples:
            name = s['item_name'][:40] if s['item_name'] else 'N/A'
            print(f"{name}: {s['estimated_unit_price_mkd']:,.2f} MKD/unit x {s['quantity']} = {s['estimated_total_price_mkd']:,.2f} MKD")

    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
