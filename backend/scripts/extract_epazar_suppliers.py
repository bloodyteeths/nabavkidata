#!/usr/bin/env python3
"""
Extract suppliers/winners from e-pazar raw_data_json and add to suppliers table.
Also enriches them with Serper API to find contact emails.

Usage:
    python3 scripts/extract_epazar_suppliers.py --dry-run   # Preview only
    python3 scripts/extract_epazar_suppliers.py             # Extract and insert
    python3 scripts/extract_epazar_suppliers.py --enrich    # Also enrich with Serper
"""
import os
import sys
import asyncio
import asyncpg
import json
import re
import aiohttp
from datetime import datetime

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL")

# Serper API
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "3f204d308413293294eba57d56ff6e9958762197")


def extract_brand_name(company_name: str) -> str:
    """Extract short brand name from full legal name"""
    if not company_name:
        return ""

    # Remove common prefixes
    prefixes = [
        r'^Друштво за .+? ',
        r'^Трговско друштво .+? ',
        r'^ДООЕЛ\s*',
        r'^ДОО\s*',
    ]

    name = company_name
    for prefix in prefixes:
        name = re.sub(prefix, '', name, flags=re.IGNORECASE)

    # Extract the brand part (usually in caps)
    caps_match = re.search(r'([А-ЯA-Z][А-Яа-яA-Za-z\s\-]{2,30})', name)
    if caps_match:
        return caps_match.group(1).strip()

    return name[:40].strip()


def extract_city(address: str) -> str:
    """Extract city from address"""
    if not address:
        return None

    cities = ['Скопје', 'Битола', 'Охрид', 'Прилеп', 'Куманово', 'Тетово', 'Велес',
              'Штип', 'Струмица', 'Кавадарци', 'Гостивар', 'Кочани', 'Струга',
              'Кичево', 'Свети Николе', 'Демир Капија', 'Радовиш', 'Илинден',
              'Skopje', 'Bitola', 'Ohrid', 'Prilep', 'Kumanovo', 'Tetovo', 'Veles']

    for city in cities:
        if city.lower() in address.lower():
            return city
    return None


async def get_epazar_winners(conn) -> list:
    """Extract unique winners from e-pazar raw_data_json"""

    # Get all signed contracts with raw_data_json
    rows = await conn.fetch("""
        SELECT tender_id, raw_data_json, source_category, awarded_value_mkd
        FROM epazar_tenders
        WHERE raw_data_json IS NOT NULL
          AND source_category = 'epazar_contracts'
    """)

    winners = {}

    for row in rows:
        try:
            raw_data = row['raw_data_json']
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)

            # Extract economic operator (winner) from signed contracts
            eo = raw_data.get('economicOperator', {})
            winner_name = eo.get('economicOperatorName', '')

            if not winner_name or len(winner_name) < 3:
                continue

            winner_id = eo.get('economicOperatorId')
            winner_address = eo.get('economicOperatorAddress', '')
            winner_city = eo.get('economicOperatorCity', '') or extract_city(winner_address)

            # Use winner name as key to deduplicate
            key = winner_name.strip().lower()

            if key not in winners:
                winners[key] = {
                    'company_name': winner_name.strip(),
                    'epazar_id': winner_id,
                    'address': winner_address,
                    'city': winner_city,
                    'contract_count': 1,
                    'total_value_mkd': float(row['awarded_value_mkd'] or 0),
                }
            else:
                winners[key]['contract_count'] += 1
                winners[key]['total_value_mkd'] += float(row['awarded_value_mkd'] or 0)

        except Exception as e:
            print(f"Error parsing {row['tender_id']}: {e}")
            continue

    return list(winners.values())


async def check_existing_suppliers(conn, winners: list) -> tuple:
    """Check which winners are already in suppliers table"""

    new_winners = []
    existing_count = 0

    for winner in winners:
        company_name = winner['company_name']

        # Check if exists (case-insensitive)
        existing = await conn.fetchval("""
            SELECT supplier_id FROM suppliers
            WHERE LOWER(TRIM(company_name)) = LOWER(TRIM($1))
        """, company_name)

        if existing:
            existing_count += 1
        else:
            new_winners.append(winner)

    return new_winners, existing_count


async def insert_supplier(conn, winner: dict) -> str:
    """Insert a new supplier and return supplier_id"""

    result = await conn.fetchval("""
        INSERT INTO suppliers (company_name, address, city, total_wins, total_contract_value_mkd, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        ON CONFLICT (company_name) DO NOTHING
        RETURNING supplier_id
    """,
        winner['company_name'],
        winner.get('address'),
        winner.get('city'),
        winner.get('contract_count', 0),
        winner.get('total_value_mkd', 0)
    )

    return str(result) if result else None


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
                return None
    except Exception as e:
        return None


def extract_emails_from_serper(result: dict) -> list:
    """Extract emails from Serper results"""
    emails = []

    if not result:
        return emails

    for item in result.get('organic', []):
        snippet = item.get('snippet', '') + ' ' + item.get('title', '')

        found_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', snippet)
        for email in found_emails:
            email = email.lower()
            if email not in emails and not email.endswith('.png') and '@' in email:
                # Skip common junk emails
                if not any(x in email for x in ['example.com', 'gmail.com', 'yahoo.com', 'hotmail.com', 'sentry.io']):
                    emails.append(email)

    return emails[:3]  # Max 3 emails per supplier


async def enrich_supplier(conn, session, supplier_id: str, company_name: str) -> list:
    """Enrich a supplier with Serper API"""
    brand = extract_brand_name(company_name)
    query = f"{brand} Македонија контакт email"

    result = await search_serper(session, query)
    emails = extract_emails_from_serper(result)

    inserted_emails = []
    for email in emails:
        try:
            await conn.execute("""
                INSERT INTO supplier_contacts (supplier_id, email, email_type, source_domain, confidence_score, status, created_at)
                VALUES ($1, $2, 'info', 'serper_epazar', 60, 'new', NOW())
                ON CONFLICT (supplier_id, email) DO NOTHING
            """, supplier_id, email)
            inserted_emails.append(email)
        except Exception as e:
            pass

    return inserted_emails


async def main():
    print("=" * 60)
    print("EXTRACT E-PAZAR SUPPLIERS")
    print("=" * 60)

    dry_run = '--dry-run' in sys.argv
    do_enrich = '--enrich' in sys.argv

    conn = await asyncpg.connect(DATABASE_URL)

    # Extract winners from raw_data_json
    print("\nExtracting winners from e-pazar raw_data_json...")
    winners = await get_epazar_winners(conn)
    print(f"Found {len(winners)} unique winners in e-pazar contracts")

    if not winners:
        print("No winners found. Make sure e-pazar scraper has run.")
        await conn.close()
        return

    # Check which are new
    new_winners, existing_count = await check_existing_suppliers(conn, winners)
    print(f"Already in suppliers: {existing_count}")
    print(f"New companies to add: {len(new_winners)}")

    # Show top winners by contract count
    print("\nTop 10 new companies by contract count:")
    sorted_winners = sorted(new_winners, key=lambda x: x['contract_count'], reverse=True)
    for i, w in enumerate(sorted_winners[:10], 1):
        print(f"  {i}. {w['company_name'][:50]}... ({w['contract_count']} contracts, {w['total_value_mkd']:,.0f} MKD)")

    if dry_run:
        print("\n[DRY RUN MODE - No changes made]")
        await conn.close()
        return

    # Insert new suppliers
    print(f"\nInserting {len(new_winners)} new suppliers...")
    inserted = 0
    supplier_ids = []

    for winner in new_winners:
        supplier_id = await insert_supplier(conn, winner)
        if supplier_id:
            inserted += 1
            supplier_ids.append((supplier_id, winner['company_name']))
            if inserted <= 20:
                print(f"  [{inserted}] {winner['company_name'][:50]}...")

    print(f"\nInserted {inserted} new suppliers from e-pazar")

    # Enrich with Serper if requested
    if do_enrich and supplier_ids:
        print(f"\nEnriching {len(supplier_ids)} suppliers with Serper...")

        async with aiohttp.ClientSession() as session:
            enriched = 0
            emails_found = 0

            for supplier_id, company_name in supplier_ids:
                emails = await enrich_supplier(conn, session, supplier_id, company_name)
                enriched += 1

                if emails:
                    emails_found += len(emails)
                    print(f"  [{enriched}] {company_name[:40]}... -> {emails}")

                # Rate limit
                await asyncio.sleep(1)

                # Progress
                if enriched % 10 == 0:
                    print(f"  ... enriched {enriched}/{len(supplier_ids)}")

            print(f"\nEnriched {enriched} suppliers, found {emails_found} emails")

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_suppliers,
            COUNT(DISTINCT s.supplier_id) FILTER (WHERE sc.id IS NOT NULL) as with_email
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
