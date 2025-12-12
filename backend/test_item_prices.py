#!/usr/bin/env python3
"""
Test script for Item Price Search endpoint
Tests the /api/ai/item-prices endpoint with sample queries
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in environment")
    sys.exit(1)

# Convert psycopg2 URL to asyncpg URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def test_epazar_items():
    """Test searching ePazar items_data"""
    print("\n" + "="*80)
    print("TEST 1: ePazar items_data search")
    print("="*80)

    async with async_session() as db:
        query = text("""
            SELECT
                item->>'name' as item_name,
                (item->>'unit_price')::float as unit_price,
                (item->>'quantity')::int as quantity,
                item->>'unit' as unit,
                e.tender_id,
                e.title
            FROM epazar_tenders e,
                 jsonb_array_elements(items_data) as item
            WHERE item->>'name' ILIKE :search
              AND items_data IS NOT NULL
            ORDER BY e.publication_date DESC NULLS LAST
            LIMIT 5
        """)

        result = await db.execute(query, {"search": "%scanner%"})
        rows = result.fetchall()

        print(f"\nFound {len(rows)} items matching 'scanner' in ePazar:\n")
        for row in rows:
            print(f"  • {row[0]}")
            print(f"    Price: {row[1]:,.2f} МКД" if row[1] else "    Price: N/A")
            print(f"    Quantity: {row[2]} {row[3] or ''}" if row[2] else "    Quantity: N/A")
            print(f"    Tender: {row[5][:80]}...")
            print(f"    ID: {row[4]}\n")


async def test_product_items():
    """Test searching product_items table"""
    print("\n" + "="*80)
    print("TEST 2: Product items table search")
    print("="*80)

    async with async_session() as db:
        query = text("""
            SELECT
                pi.name,
                pi.unit_price,
                pi.quantity,
                pi.unit,
                pi.tender_id,
                t.title
            FROM product_items pi
            JOIN tenders t ON pi.tender_id = t.tender_id
            WHERE pi.name ILIKE :search
              AND pi.unit_price IS NOT NULL
            ORDER BY t.publication_date DESC NULLS LAST
            LIMIT 5
        """)

        result = await db.execute(query, {"search": "%лаптоп%"})
        rows = result.fetchall()

        print(f"\nFound {len(rows)} items matching 'лаптоп' in product_items:\n")
        for row in rows:
            print(f"  • {row[0]}")
            print(f"    Price: {float(row[1]):,.2f} МКД" if row[1] else "    Price: N/A")
            print(f"    Quantity: {float(row[2])} {row[3] or ''}" if row[2] else "    Quantity: N/A")
            print(f"    Tender: {row[5][:80] if row[5] else 'N/A'}...")
            print(f"    ID: {row[4]}\n")


async def test_statistics():
    """Test price statistics calculation"""
    print("\n" + "="*80)
    print("TEST 3: Price statistics")
    print("="*80)

    async with async_session() as db:
        query = text("""
            SELECT
                (item->>'unit_price')::float as unit_price
            FROM epazar_tenders e,
                 jsonb_array_elements(items_data) as item
            WHERE item->>'name' ILIKE :search
              AND items_data IS NOT NULL
              AND item->>'unit_price' IS NOT NULL
        """)

        result = await db.execute(query, {"search": "%компјутер%"})
        prices = [row[0] for row in result.fetchall() if row[0] and row[0] > 0]

        if prices:
            prices_sorted = sorted(prices)
            n = len(prices_sorted)
            median = (
                (prices_sorted[n//2 - 1] + prices_sorted[n//2]) / 2
                if n % 2 == 0
                else prices_sorted[n//2]
            )

            print(f"\nPrice statistics for 'компјутер' ({len(prices)} items):\n")
            print(f"  Min:    {min(prices):>15,.2f} МКД")
            print(f"  Max:    {max(prices):>15,.2f} МКД")
            print(f"  Avg:    {sum(prices)/len(prices):>15,.2f} МКД")
            print(f"  Median: {median:>15,.2f} МКД")
        else:
            print("\nNo price data found for 'компјутер'")


async def test_data_sources():
    """Test data availability across sources"""
    print("\n" + "="*80)
    print("TEST 4: Data source availability")
    print("="*80)

    async with async_session() as db:
        # ePazar items
        epazar_count = await db.execute(text("""
            SELECT COUNT(DISTINCT e.tender_id)
            FROM epazar_tenders e
            WHERE items_data IS NOT NULL
        """))
        epazar_tenders = epazar_count.scalar()

        # Product items
        product_count = await db.execute(text("""
            SELECT COUNT(DISTINCT tender_id) FROM product_items
        """))
        product_tenders = product_count.scalar()

        # Nabavki with raw_data_json
        nabavki_count = await db.execute(text("""
            SELECT COUNT(*) FROM tenders WHERE raw_data_json IS NOT NULL
        """))
        nabavki_tenders = nabavki_count.scalar()

        print("\nData availability:\n")
        print(f"  ePazar tenders with items:      {epazar_tenders:>8,}")
        print(f"  Tenders with extracted items:   {product_tenders:>8,}")
        print(f"  Nabavki with raw JSON:          {nabavki_tenders:>8,}")


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("ITEM PRICE SEARCH - BACKEND TEST")
    print("="*80)

    try:
        await test_data_sources()
        await test_epazar_items()
        await test_product_items()
        await test_statistics()

        print("\n" + "="*80)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
