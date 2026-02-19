#!/usr/bin/env python3
"""
Import existing leads from suppliers and apollo_contacts into outreach_leads table.
Handles deduplication and segment assignment.

Usage:
    python3 scripts/import_leads_to_outreach.py
"""
import asyncio
import os
import asyncpg
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")


def calculate_quality_score(segment: str, job_title: str, has_domain: bool, has_linkedin: bool) -> int:
    """Calculate quality score 1-100"""
    score = 50

    # Segment bonus
    if segment == 'A':
        score += 30
    elif segment == 'B':
        score += 15

    # Title bonus
    title = (job_title or '').lower()
    if any(t in title for t in ['ceo', 'owner', 'founder', 'director', 'president']):
        score += 15
    elif any(t in title for t in ['manager', 'head', 'chief', 'vp']):
        score += 10
    elif any(t in title for t in ['procurement', 'purchasing', 'nabavki']):
        score += 20  # Extra relevant for tenders

    # Data quality bonus
    if has_domain:
        score += 5
    if has_linkedin:
        score += 5

    return min(100, max(1, score))


async def main():
    print("=" * 70)
    print("IMPORT LEADS TO OUTREACH SYSTEM")
    print("=" * 70)

    conn = await asyncpg.connect(DATABASE_URL)

    # Stats
    imported_a = 0
    imported_b = 0
    duplicates = 0

    # Step 1: Import Segment A (supplier_contacts - tender participants)
    print("\n[1/2] Importing Segment A (Tender Participants)...")

    supplier_contacts = await conn.fetch("""
        SELECT DISTINCT ON (sc.email)
            sc.email,
            sc.contact_name as full_name,
            s.company_name,
            s.contact_person as contact_person,
            s.city,
            s.website as company_domain,
            s.supplier_id
        FROM supplier_contacts sc
        JOIN suppliers s ON sc.supplier_id = s.supplier_id
        WHERE sc.email IS NOT NULL
          AND sc.email != ''
          AND sc.email NOT LIKE '%@example%'
        ORDER BY sc.email, sc.created_at DESC
    """)

    print(f"  Found {len(supplier_contacts)} supplier contacts")

    for contact in supplier_contacts:
        email = contact['email'].lower().strip()

        # Extract domain from website
        domain = None
        if contact['company_domain']:
            domain = contact['company_domain'].replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]

        # Use contact_name or contact_person as name
        full_name = contact['full_name'] or contact['contact_person']

        quality = calculate_quality_score('A', None, bool(domain), False)

        try:
            await conn.execute("""
                INSERT INTO outreach_leads (
                    email, full_name, company_name,
                    segment, source, quality_score,
                    company_domain, city, country, supplier_id
                ) VALUES ($1, $2, $3, 'A', 'enabavki', $4, $5, $6, 'North Macedonia', $7)
                ON CONFLICT (email) DO UPDATE SET
                    segment = CASE WHEN outreach_leads.segment > 'A' THEN 'A' ELSE outreach_leads.segment END,
                    quality_score = GREATEST(outreach_leads.quality_score, EXCLUDED.quality_score),
                    supplier_id = COALESCE(outreach_leads.supplier_id, EXCLUDED.supplier_id),
                    updated_at = NOW()
            """,
                email,
                full_name,
                contact['company_name'],
                quality,
                domain,
                contact['city'],
                contact['supplier_id']
            )
            imported_a += 1
        except Exception as e:
            duplicates += 1

    print(f"  ✓ Imported {imported_a} Segment A leads")

    # Step 2: Import Segment B (apollo_contacts - decision makers)
    print("\n[2/2] Importing Segment B (Apollo Decision Makers)...")

    apollo_contacts = await conn.fetch("""
        SELECT
            email,
            full_name,
            first_name,
            last_name,
            company_name,
            job_title,
            company_domain,
            company_industry,
            company_size,
            city,
            country,
            linkedin_url,
            phone,
            id as apollo_id
        FROM apollo_contacts
        WHERE email IS NOT NULL
          AND email NOT LIKE '%not_unlocked%'
          AND email != ''
          AND (country ILIKE '%macedonia%' OR country ILIKE '%FYROM%')
        ORDER BY email
    """)

    print(f"  Found {len(apollo_contacts)} Apollo contacts with email")

    for contact in apollo_contacts:
        email = contact['email'].lower().strip()
        has_linkedin = bool(contact['linkedin_url'])
        has_domain = bool(contact['company_domain'])

        quality = calculate_quality_score('B', contact['job_title'], has_domain, has_linkedin)

        try:
            await conn.execute("""
                INSERT INTO outreach_leads (
                    email, full_name, first_name, last_name, company_name,
                    job_title, segment, source, quality_score,
                    company_domain, company_industry, company_size,
                    city, country, linkedin_url, phone, apollo_contact_id
                ) VALUES ($1, $2, $3, $4, $5, $6, 'B', 'apollo', $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (email) DO UPDATE SET
                    -- Only update if new data is better (segment B won't override A)
                    linkedin_url = COALESCE(outreach_leads.linkedin_url, EXCLUDED.linkedin_url),
                    phone = COALESCE(outreach_leads.phone, EXCLUDED.phone),
                    company_industry = COALESCE(outreach_leads.company_industry, EXCLUDED.company_industry),
                    apollo_contact_id = COALESCE(outreach_leads.apollo_contact_id, EXCLUDED.apollo_contact_id),
                    updated_at = NOW()
            """,
                email,
                contact['full_name'],
                contact['first_name'],
                contact['last_name'],
                contact['company_name'],
                contact['job_title'],
                quality,
                contact['company_domain'],
                contact['company_industry'],
                contact['company_size'],
                contact['city'],
                contact['country'] or 'North Macedonia',
                contact['linkedin_url'],
                contact['phone'],
                contact['apollo_id']
            )
            imported_b += 1
        except Exception as e:
            duplicates += 1

    print(f"  ✓ Imported {imported_b} Segment B leads")

    # Final stats
    stats = await conn.fetch("""
        SELECT segment, source, COUNT(*) as count, ROUND(AVG(quality_score), 1) as avg_quality
        FROM outreach_leads
        GROUP BY segment, source
        ORDER BY segment, source
    """)

    total = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")

    print("\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"\nTotal leads in outreach_leads: {total}")
    print("\nBreakdown by segment/source:")
    for row in stats:
        print(f"  Segment {row['segment']} ({row['source']}): {row['count']} leads (avg quality: {row['avg_quality']})")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
