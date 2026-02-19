#!/usr/bin/env python3
"""
Import companies from tender_bidders into suppliers table
Then enrich them with Serper API to find emails
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import json
import re
from datetime import datetime

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")

# Serper API
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "db407e928ec8df5b6a798f5ce833ce648b74f130")

async def get_bidders_not_in_suppliers(conn) -> list:
    """Get companies from tender_bidders that are not in suppliers"""
    query = """
    WITH bidders_to_add AS (
      SELECT DISTINCT TRIM(tb.company_name) as company_name, COUNT(*) as bid_count
      FROM tender_bidders tb
      LEFT JOIN suppliers s ON LOWER(TRIM(tb.company_name)) = LOWER(TRIM(s.company_name))
      WHERE s.supplier_id IS NULL
        AND LENGTH(tb.company_name) > 10
        AND tb.company_name !~ '^[0-9]+$'
        AND tb.company_name !~ '^[0-9]{8}'
        AND tb.company_name NOT LIKE '%CPV%'
        AND tb.company_name NOT LIKE '%Дел %'
        AND tb.company_name NOT LIKE '%Партија%'
        AND tb.company_name NOT ILIKE '%Не се пронајдени%'
        AND tb.company_name NOT ILIKE '%набавка на%'
        AND tb.company_name NOT ILIKE '%ЈЗУ%'
        AND tb.company_name NOT ILIKE '%Приватна здравствена%'
        AND tb.company_name NOT ILIKE '%болница%'
        AND tb.company_name NOT ILIKE '%Квалитет%'
        AND (tb.company_name LIKE '%Друштво%' OR tb.company_name LIKE '%Трговско%'
             OR tb.company_name LIKE '%Акционерско%' OR tb.company_name LIKE '%ОКТА%'
             OR tb.company_name LIKE '%Фабрика%')
      GROUP BY TRIM(tb.company_name)
      HAVING COUNT(*) >= 2
    )
    SELECT company_name, bid_count FROM bidders_to_add ORDER BY bid_count DESC;
    """
    rows = await conn.fetch(query)
    return [dict(r) for r in rows]


def extract_brand_name(company_name: str) -> str:
    """Extract short brand name from full legal name"""
    # Common patterns in Macedonian company names
    patterns = [
        r'(?:Друштво|Трговско друштво|Акционерско друштво)[^А-ЯA-Z]*([А-ЯA-Z][А-Яа-яA-Za-z\s\-]+?)(?:\s+ДООЕЛ|\s+ДОО|\s+АД|\s+увоз|\s+експорт|\s+Скопје|\s+Битола|\s+Охрид|\s+Прилеп|\s+Куманово)',
        r'([А-ЯA-Z][А-Яа-яA-Za-z\s\-]{2,20})(?:\s+ДООЕЛ|\s+ДОО|\s+АД)',
    ]

    for pattern in patterns:
        match = re.search(pattern, company_name, re.IGNORECASE)
        if match:
            brand = match.group(1).strip()
            # Clean up
            brand = re.sub(r'\s+', ' ', brand)
            if len(brand) > 3 and len(brand) < 50:
                return brand

    # Fallback: return first 30 chars
    return company_name[:30]


def extract_city(company_name: str) -> str:
    """Extract city from company name"""
    cities = ['Скопје', 'Битола', 'Охрид', 'Прилеп', 'Куманово', 'Тетово', 'Велес',
              'Штип', 'Струмица', 'Кавадарци', 'Гостивар', 'Кочани', 'Струга',
              'Кичево', 'Свети Николе', 'Демир Капија', 'Радовиш', 'Илинден']
    for city in cities:
        if city.lower() in company_name.lower():
            return city
    return None


async def insert_supplier(conn, company_name: str, bid_count: int) -> str:
    """Insert a new supplier and return supplier_id"""
    city = extract_city(company_name)

    query = """
    INSERT INTO suppliers (company_name, city, total_bids, created_at, updated_at)
    VALUES ($1, $2, $3, NOW(), NOW())
    ON CONFLICT (company_name) DO NOTHING
    RETURNING supplier_id;
    """

    try:
        result = await conn.fetchval(query, company_name, city, bid_count)
        return str(result) if result else None
    except Exception as e:
        print(f"Error inserting {company_name[:50]}: {e}")
        return None


async def search_serper(session, query: str) -> dict:
    """Search using Serper API"""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "gl": "mk",
        "hl": "mk",
        "num": 10
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                print(f"Serper error: {resp.status}")
                return None
    except Exception as e:
        print(f"Serper request failed: {e}")
        return None


def extract_contact_from_serper(result: dict) -> dict:
    """Extract contact info from Serper results"""
    contacts = {
        'emails': [],
        'phones': [],
        'website': None
    }

    if not result:
        return contacts

    # Check organic results
    for item in result.get('organic', []):
        snippet = item.get('snippet', '') + ' ' + item.get('title', '')
        link = item.get('link', '')

        # Extract emails
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', snippet)
        for email in emails:
            if email not in contacts['emails'] and not email.endswith('.png'):
                contacts['emails'].append(email.lower())

        # Extract phones
        phones = re.findall(r'(?:\+389|02|0\d{2})[\s\-]?\d{3}[\s\-]?\d{3,4}', snippet)
        for phone in phones:
            clean_phone = re.sub(r'\s+', '', phone)
            if clean_phone not in contacts['phones']:
                contacts['phones'].append(clean_phone)

        # Get website
        if not contacts['website'] and '.mk' in link:
            contacts['website'] = link

    # Check knowledge graph
    kg = result.get('knowledgeGraph', {})
    if kg.get('website'):
        contacts['website'] = kg['website']
    if kg.get('phone'):
        contacts['phones'].append(kg['phone'])

    return contacts


async def enrich_supplier(conn, session, supplier_id: str, company_name: str) -> dict:
    """Enrich a supplier with Serper API"""
    brand_name = extract_brand_name(company_name)

    # Search query
    query = f"{brand_name} Македонија контакт email"

    result = await search_serper(session, query)
    contacts = extract_contact_from_serper(result)

    # Update supplier with website
    if contacts['website']:
        await conn.execute("""
            UPDATE suppliers SET website = $1, updated_at = NOW()
            WHERE supplier_id = $2
        """, contacts['website'], supplier_id)

    # Insert contacts
    for email in contacts['emails'][:3]:  # Max 3 emails per supplier
        try:
            await conn.execute("""
                INSERT INTO supplier_contacts (supplier_id, contact_type, contact_value, source, created_at)
                VALUES ($1, 'email', $2, 'serper_search', NOW())
                ON CONFLICT DO NOTHING
            """, supplier_id, email)
        except Exception as e:
            pass  # Ignore duplicates

    for phone in contacts['phones'][:2]:  # Max 2 phones
        try:
            await conn.execute("""
                INSERT INTO supplier_contacts (supplier_id, contact_type, contact_value, source, created_at)
                VALUES ($1, 'phone', $2, 'serper_search', NOW())
                ON CONFLICT DO NOTHING
            """, supplier_id, phone)
        except Exception as e:
            pass

    return contacts


async def main():
    print("=" * 60)
    print("IMPORT BIDDERS TO SUPPLIERS")
    print("=" * 60)

    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = await asyncpg.connect(DATABASE_URL)

    # Get bidders not in suppliers
    bidders = await get_bidders_not_in_suppliers(conn)
    print(f"\nFound {len(bidders)} companies to import")

    # Check command line args
    dry_run = '--dry-run' in sys.argv
    limit = 999
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    skip_enrich = '--skip-enrich' in sys.argv

    if dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")
        for b in bidders[:20]:
            print(f"  - {b['company_name'][:60]}... ({b['bid_count']} bids)")
        print(f"  ... and {len(bidders) - 20} more")
        await conn.close()
        return

    # Insert suppliers
    print(f"\nInserting up to {limit} suppliers...")
    inserted = 0
    supplier_ids = []

    for bidder in bidders[:limit]:
        supplier_id = await insert_supplier(conn, bidder['company_name'], bidder['bid_count'])
        if supplier_id:
            inserted += 1
            supplier_ids.append((supplier_id, bidder['company_name']))
            print(f"  [{inserted}] Inserted: {bidder['company_name'][:50]}...")

    print(f"\nInserted {inserted} new suppliers")

    # Enrich with Serper
    if not skip_enrich and supplier_ids:
        print(f"\nEnriching {len(supplier_ids)} suppliers with Serper...")
        async with aiohttp.ClientSession() as session:
            enriched = 0
            emails_found = 0

            for supplier_id, company_name in supplier_ids:
                contacts = await enrich_supplier(conn, session, supplier_id, company_name)
                enriched += 1

                if contacts['emails']:
                    emails_found += len(contacts['emails'])
                    print(f"  [{enriched}] {company_name[:40]}... -> {contacts['emails']}")
                else:
                    print(f"  [{enriched}] {company_name[:40]}... -> No email found")

                # Rate limit
                await asyncio.sleep(1)

            print(f"\nEnriched {enriched} suppliers, found {emails_found} emails")

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_suppliers,
            COUNT(DISTINCT s.supplier_id) FILTER (WHERE sc.contact_type = 'email') as with_email
        FROM suppliers s
        LEFT JOIN supplier_contacts sc ON s.supplier_id = sc.supplier_id
    """)

    print(f"\n" + "=" * 60)
    print(f"FINAL STATS")
    print(f"=" * 60)
    print(f"Total suppliers: {stats['total_suppliers']}")
    print(f"With email: {stats['with_email']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
