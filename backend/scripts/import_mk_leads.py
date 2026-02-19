#!/usr/bin/env python3
"""
Import mk_companies with emails into outreach_leads for cold drip campaigns.

Assigns segment:
  A = company matches a tender supplier (by name+city) — tender-active
  B = general business (yellowpages, companywall) — growth-potential

Quality score based on data completeness and source reliability.

Usage:
    python3 scripts/import_mk_leads.py --dry-run --limit 100
    python3 scripts/import_mk_leads.py --segment B --limit 5000
    python3 scripts/import_mk_leads.py              # Full import
"""
import asyncio
import os
import sys
import argparse
import logging

import asyncpg

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


def calculate_quality_score(company):
    """Score 1-100 based on data completeness and source reliability."""
    score = 0

    # Email presence is the baseline
    if company['email']:
        score += 30

    # Contact data completeness
    if company['phone']:
        score += 10
    if company['website']:
        score += 10
    if company['address']:
        score += 10

    # Source reliability
    source = (company['email_source'] or '').lower()
    if source == 'yellowpages':
        score += 20  # Verified directory listing
    elif source in ('companywall', 'central_registry'):
        score += 15
    elif source in ('google', 'serper', 'brave'):
        score += 10
    else:
        score += 5

    # Company data richness
    if company.get('nace_code'):
        score += 5
    if company.get('city_mk'):
        score += 5
    if company.get('companywall_id'):
        score += 5

    return min(100, max(1, score))


async def main():
    parser = argparse.ArgumentParser(description='Import mk_companies into outreach_leads')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing to DB')
    parser.add_argument('--limit', type=int, default=0, help='Max companies to import (0=all)')
    parser.add_argument('--segment', choices=['A', 'B'], help='Only import specific segment')
    parser.add_argument('--source-filter', help='Only import from specific email_source (e.g. yellowpages)')
    args = parser.parse_args()

    db_url = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)

    # Step 1: Build set of tender-active company names for segment assignment
    logger.info("Loading tender supplier names for segment classification...")
    async with pool.acquire() as conn:
        suppliers = await conn.fetch("""
            SELECT DISTINCT UPPER(TRIM(company_name)) as name, UPPER(TRIM(city)) as city
            FROM suppliers
            WHERE company_name IS NOT NULL
        """)

    supplier_names = set()
    supplier_name_city = set()
    for s in suppliers:
        if s['name'] and len(s['name']) >= 3:
            supplier_names.add(s['name'])
            if s['city']:
                supplier_name_city.add((s['name'], s['city']))

    logger.info(f"Loaded {len(supplier_names)} unique supplier names, {len(supplier_name_city)} name+city pairs")

    # Step 2: Load existing outreach emails for dedup
    logger.info("Loading existing outreach_leads emails for dedup...")
    async with pool.acquire() as conn:
        existing_emails = set()
        rows = await conn.fetch("SELECT email FROM outreach_leads")
        for r in rows:
            existing_emails.add(r['email'].lower().strip())

        # Load suppression list
        suppressed = set()
        rows = await conn.fetch("SELECT email FROM suppression_list")
        for r in rows:
            suppressed.add(r['email'].lower().strip())

        # Load campaign unsubscribes
        rows = await conn.fetch("SELECT email FROM campaign_unsubscribes")
        for r in rows:
            suppressed.add(r['email'].lower().strip())

    logger.info(f"Existing leads: {len(existing_emails)}, Suppressed: {len(suppressed)}")

    # Step 3: Query mk_companies with email
    query = """
        SELECT company_id, name, email, phone, address, city_mk, website,
               email_source, companywall_id, nace_code, nace_description,
               category_mk, source_url
        FROM mk_companies
        WHERE email IS NOT NULL AND email != ''
    """
    params = []

    if args.source_filter:
        query += " AND email_source = $1"
        params.append(args.source_filter)

    query += " ORDER BY company_id"

    if args.limit > 0:
        query += f" LIMIT {args.limit}"

    async with pool.acquire() as conn:
        companies = await conn.fetch(query, *params)

    logger.info(f"Found {len(companies)} mk_companies with email")

    # Step 4: Process and import
    stats = {
        'total': 0,
        'imported_a': 0,
        'imported_b': 0,
        'skipped_exists': 0,
        'skipped_suppressed': 0,
        'skipped_invalid': 0,
        'errors': 0,
    }

    batch = []
    batch_size = 200

    for company in companies:
        stats['total'] += 1
        email = company['email'].lower().strip()

        # Skip invalid emails
        if not email or '@' not in email or len(email) < 5:
            stats['skipped_invalid'] += 1
            continue

        # Skip gov/edu emails
        if any(x in email for x in ['.gov.mk', '.edu.mk', 'ukim.edu', '@un.org']):
            stats['skipped_invalid'] += 1
            continue

        # Skip already imported
        if email in existing_emails:
            stats['skipped_exists'] += 1
            continue

        # Skip suppressed
        if email in suppressed:
            stats['skipped_suppressed'] += 1
            continue

        # Determine segment
        comp_name = (company['name'] or '').upper().strip()
        comp_city = (company['city_mk'] or '').upper().strip()

        is_tender_active = (
            comp_name in supplier_names
            or (comp_name, comp_city) in supplier_name_city
        )

        segment = 'A' if is_tender_active else 'B'

        # Filter by segment if requested
        if args.segment and segment != args.segment:
            continue

        quality = calculate_quality_score(company)

        # Determine source string
        source = company['email_source'] or 'mk_companies'

        # Determine industry from NACE or category
        industry = company.get('nace_description') or company.get('category_mk') or None

        batch.append({
            'email': email,
            'company_name': company['name'],
            'segment': segment,
            'source': source,
            'quality_score': quality,
            'city': company['city_mk'],
            'phone': company['phone'],
            'mk_company_id': company['company_id'],
            'company_domain': company['website'],
            'company_industry': industry,
        })

        # Track for dedup within this run
        existing_emails.add(email)

        if segment == 'A':
            stats['imported_a'] += 1
        else:
            stats['imported_b'] += 1

        # Flush batch
        if len(batch) >= batch_size and not args.dry_run:
            await _insert_batch(pool, batch)
            batch = []

    # Final batch
    if batch and not args.dry_run:
        await _insert_batch(pool, batch)

    # Log results
    logger.info("=" * 60)
    if args.dry_run:
        logger.info("DRY RUN — no data written to DB")
    logger.info(f"Total processed: {stats['total']}")
    logger.info(f"Imported Segment A (tender-active): {stats['imported_a']}")
    logger.info(f"Imported Segment B (growth-potential): {stats['imported_b']}")
    logger.info(f"Skipped (already exists): {stats['skipped_exists']}")
    logger.info(f"Skipped (suppressed): {stats['skipped_suppressed']}")
    logger.info(f"Skipped (invalid email): {stats['skipped_invalid']}")

    # Show DB stats
    if not args.dry_run:
        async with pool.acquire() as conn:
            db_stats = await conn.fetch("""
                SELECT segment, source, COUNT(*) as count,
                       ROUND(AVG(quality_score), 1) as avg_quality
                FROM outreach_leads
                GROUP BY segment, source
                ORDER BY segment, source
            """)
            total = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")
            logger.info(f"\nTotal outreach_leads: {total}")
            for row in db_stats:
                logger.info(f"  Segment {row['segment']} ({row['source']}): {row['count']} (avg quality: {row['avg_quality']})")

    await pool.close()


async def _insert_batch(pool, batch):
    """Insert a batch of leads into outreach_leads."""
    async with pool.acquire() as conn:
        for lead in batch:
            try:
                await conn.execute("""
                    INSERT INTO outreach_leads (
                        email, company_name, segment, source, quality_score,
                        city, phone, mk_company_id, company_domain,
                        company_industry, country
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'North Macedonia')
                    ON CONFLICT (email) DO UPDATE SET
                        segment = CASE WHEN outreach_leads.segment > EXCLUDED.segment
                                       THEN EXCLUDED.segment ELSE outreach_leads.segment END,
                        quality_score = GREATEST(outreach_leads.quality_score, EXCLUDED.quality_score),
                        mk_company_id = COALESCE(outreach_leads.mk_company_id, EXCLUDED.mk_company_id),
                        phone = COALESCE(outreach_leads.phone, EXCLUDED.phone),
                        company_domain = COALESCE(outreach_leads.company_domain, EXCLUDED.company_domain),
                        company_industry = COALESCE(outreach_leads.company_industry, EXCLUDED.company_industry),
                        updated_at = NOW()
                """,
                    lead['email'],
                    lead['company_name'],
                    lead['segment'],
                    lead['source'],
                    lead['quality_score'],
                    lead['city'],
                    lead['phone'],
                    lead['mk_company_id'],
                    lead['company_domain'],
                    lead['company_industry'],
                )
            except Exception as e:
                logger.debug(f"Insert error for {lead['email']}: {e}")


if __name__ == '__main__':
    asyncio.run(main())
