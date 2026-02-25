#!/usr/bin/env python3
"""
Generate sample PDF reports for top companies
Run with: python -m backend.cli.generate_sample_reports --limit 5
"""
import os
import sys
import asyncio
import argparse
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncpg

# Load env
from dotenv import load_dotenv
load_dotenv()

# Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "nabavkidata")
DB_USER = os.getenv("DB_USER", "nabavki_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

REPORTS_DIR = os.getenv("REPORTS_DIR", "/tmp/nabavkidata_reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


async def get_pool():
    return await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        min_size=2,
        max_size=10
    )


async def get_top_companies(pool, limit: int = 10):
    """Get top companies by wins in last 12 months"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                tb.company_name,
                tb.company_tax_id,
                COUNT(DISTINCT tb.tender_id) as participations,
                COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) as wins,
                COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd END), 0) as total_value
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE t.publication_date >= NOW() - INTERVAL '12 months'
              AND tb.company_name IS NOT NULL
              AND LENGTH(TRIM(tb.company_name)) > 3
            GROUP BY tb.company_name, tb.company_tax_id
            HAVING COUNT(DISTINCT tb.tender_id) >= 5
               AND COUNT(DISTINCT CASE WHEN tb.is_winner THEN tb.tender_id END) >= 2
            ORDER BY wins DESC, total_value DESC
            LIMIT $1
        """, limit)

        return [dict(r) for r in rows]


async def generate_report(pool, company: dict):
    """Generate a single report"""
    from backend.services.report_generator import ReportGenerator

    generator = ReportGenerator(pool)

    result = await generator.generate_report(
        company_name=company['company_name'],
        company_tax_id=company.get('company_tax_id'),
        email="test@example.com"  # Placeholder for sample
    )

    return result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", "-l", type=int, default=5, help="Number of reports to generate")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"Generating {args.limit} sample PDF reports")
    print(f"{'='*60}")

    pool = await get_pool()

    # Get top companies
    print("\nFetching top companies by tender wins...")
    companies = await get_top_companies(pool, args.limit)

    if not companies:
        print("No companies found matching criteria!")
        return

    print(f"Found {len(companies)} companies:\n")
    for i, c in enumerate(companies, 1):
        print(f"  {i}. {c['company_name'][:50]}")
        print(f"     Participations: {c['participations']}, Wins: {c['wins']}, Value: {c['total_value']:,.0f} MKD")

    # Generate reports
    print(f"\n{'='*60}")
    print("Generating PDF reports...")
    print(f"{'='*60}\n")

    generated = []
    for i, company in enumerate(companies, 1):
        print(f"[{i}/{len(companies)}] {company['company_name'][:40]}...")

        try:
            result = await generate_report(pool, company)

            if result.get('success'):
                print(f"  ✓ PDF saved: {result['pdf_path']}")
                print(f"    Size: {result['pdf_size_bytes']:,} bytes")
                print(f"    Stats: {result['stats'].get('participations_12m')} participations, "
                      f"{result['stats'].get('wins_12m')} wins")
                print(f"    Missed opportunities: {result.get('missed_opportunities_count', 0)}")
                generated.append(result)
            else:
                print(f"  ✗ Error: {result.get('error')}")

        except Exception as e:
            print(f"  ✗ Exception: {e}")

    await pool.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Generated: {len(generated)}/{len(companies)} reports")
    print(f"Reports saved to: {REPORTS_DIR}")
    print(f"\nTo view reports:")
    for r in generated:
        print(f"  {r['pdf_path']}")


if __name__ == "__main__":
    asyncio.run(main())
