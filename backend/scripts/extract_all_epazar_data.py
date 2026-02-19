#!/usr/bin/env python3
"""
Extract ALL data from e-pazar.gov.mk APIs:
- 1,272 Economic Operators (suppliers/bidders)
- 461 Contracting Authorities
- Contact info from ALL tender details (direct emails!)

Usage:
    python3 scripts/extract_all_epazar_data.py --dry-run   # Preview
    python3 scripts/extract_all_epazar_data.py             # Full extraction
    python3 scripts/extract_all_epazar_data.py --contacts-only  # Only tender contacts
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
if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL")

BASE_URL = "https://e-pazar.gov.mk/api"


def extract_city(name: str) -> str:
    """Extract city from company/authority name"""
    cities = ['Скопје', 'Битола', 'Охрид', 'Прилеп', 'Куманово', 'Тетово', 'Велес',
              'Штип', 'Струмица', 'Кавадарци', 'Гостивар', 'Кочани', 'Струга',
              'Кичево', 'Свети Николе', 'Демир Капија', 'Радовиш', 'Илинден',
              'Кратово', 'Виница', 'Берово', 'Неготино', 'Валандово', 'Гевгелија',
              'Делчево', 'Пробиштип', 'Крива Паланка', 'Македонски Брод', 'Ресен',
              'Дебар', 'Свети Николе', 'Богданци', 'Крушево']
    for city in cities:
        if city.lower() in name.lower():
            return city
    return None


async def fetch_json(session, url: str) -> dict:
    """Fetch JSON from URL"""
    try:
        async with session.get(url, timeout=60) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                print(f"  Error {resp.status}: {url}")
                return None
    except Exception as e:
        print(f"  Request failed: {e}")
        return None


async def get_all_economic_operators(session) -> list:
    """Fetch all 1,272 economic operators"""
    print("\n[1/3] Fetching ALL Economic Operators...")
    data = await fetch_json(session, f"{BASE_URL}/economicoperator/getAllEO")
    if data:
        print(f"      Found {len(data)} economic operators")
        return data
    return []


async def get_all_contracting_authorities(session) -> list:
    """Fetch all 461 contracting authorities"""
    print("\n[2/3] Fetching ALL Contracting Authorities...")
    data = await fetch_json(session, f"{BASE_URL}/contractauthority/getAllCA")
    if data:
        print(f"      Found {len(data)} contracting authorities")
        return data
    return []


async def get_all_tender_ids(session) -> set:
    """Get all unique tender IDs from active, completed, and contracts"""
    print("\n[3/3] Collecting ALL tender IDs for contact extraction...")
    tender_ids = set()

    # Active tenders
    for page in range(50):  # Max 50 pages
        url = f"{BASE_URL}/tender/searchActiveTenders?PageNumber={page}&PageSize=100&TenderActiveStatus=all"
        data = await fetch_json(session, url)
        if not data or not data.get('data'):
            break
        for item in data['data']:
            tender_ids.add(item.get('tenderId'))
        if page == 0:
            total = data.get('totalCount', 0)
            print(f"      Active tenders: {total}")
        await asyncio.sleep(0.2)

    # Completed tenders
    for page in range(50):
        url = f"{BASE_URL}/tender/searchCompletedsTenders?PageNumber={page}&PageSize=100"
        data = await fetch_json(session, url)
        if not data or not data.get('data'):
            break
        for item in data['data']:
            tender_ids.add(item.get('tenderId'))
        if page == 0:
            total = data.get('totalCount', 0)
            print(f"      Completed tenders: {total}")
        await asyncio.sleep(0.2)

    print(f"      Total unique tender IDs: {len(tender_ids)}")
    return tender_ids


async def extract_tender_contacts(session, tender_ids: set, conn, dry_run: bool) -> dict:
    """Extract contact info from tender details"""
    print(f"\nExtracting contacts from {len(tender_ids)} tenders...")

    contacts_found = {
        'emails': [],
        'phones': [],
        'persons': [],
        'created_suppliers': 0
    }

    processed = 0
    for tender_id in tender_ids:
        if not tender_id:
            continue

        url = f"{BASE_URL}/tender/getPublishedTenderDetails/{tender_id}"
        data = await fetch_json(session, url)

        if data:
            email = data.get('tenderContactMail', '').strip()
            phone = data.get('tenderContactPhone', '').strip()
            person = data.get('tenderContactPerson', '').strip()
            ca_data = data.get('contractAuthority', {})
            authority_name = ca_data.get('contractAuthorityName', '')
            authority_city = ca_data.get('contractAuthorityCity', '')
            authority_id = ca_data.get('contractAuthorityId')

            if email and '@' in email and authority_name:
                contacts_found['emails'].append({
                    'email': email.lower(),
                    'person': person,
                    'phone': phone,
                    'company': authority_name,
                    'tender_id': tender_id
                })

                if not dry_run:
                    # Find supplier for the contracting authority
                    supplier_id = await conn.fetchval("""
                        SELECT supplier_id FROM suppliers
                        WHERE LOWER(TRIM(company_name)) = LOWER(TRIM($1))
                    """, authority_name)

                    # If not found, CREATE the supplier
                    if not supplier_id and len(authority_name) > 5:
                        try:
                            supplier_id = await conn.fetchval("""
                                INSERT INTO suppliers (company_name, city, epazar_ca_id, source, created_at, updated_at)
                                VALUES ($1, $2, $3, 'epazar_tender_ca', NOW(), NOW())
                                ON CONFLICT (company_name) DO UPDATE SET updated_at = NOW()
                                RETURNING supplier_id
                            """, authority_name, authority_city, str(authority_id) if authority_id else None)
                            if supplier_id:
                                contacts_found['created_suppliers'] += 1
                        except Exception as e:
                            pass

                    if supplier_id:
                        # Add contact
                        try:
                            await conn.execute("""
                                INSERT INTO supplier_contacts
                                (supplier_id, email, contact_name, phone, email_type, source_domain, confidence_score, status, created_at)
                                VALUES ($1, $2, $3, $4, 'primary', 'epazar_tender', 90, 'new', NOW())
                                ON CONFLICT (supplier_id, email) DO UPDATE SET
                                    contact_name = COALESCE(EXCLUDED.contact_name, supplier_contacts.contact_name),
                                    phone = COALESCE(EXCLUDED.phone, supplier_contacts.phone),
                                    confidence_score = GREATEST(supplier_contacts.confidence_score, 90)
                            """, supplier_id, email.lower(), person, phone)
                        except Exception as e:
                            pass

            if phone:
                contacts_found['phones'].append(phone)
            if person:
                contacts_found['persons'].append(person)

        processed += 1
        if processed % 100 == 0:
            print(f"      Processed {processed}/{len(tender_ids)} tenders, found {len(contacts_found['emails'])} emails, created {contacts_found['created_suppliers']} new suppliers")

        await asyncio.sleep(0.1)  # Rate limit

    return contacts_found


async def import_economic_operators(conn, operators: list, dry_run: bool) -> int:
    """Import economic operators to suppliers table"""
    print(f"\nImporting {len(operators)} economic operators to suppliers...")

    inserted = 0
    already_exists = 0

    for op in operators:
        name = op.get('economicOperatorName', '').strip()
        epazar_id = op.get('economicOperatorId')

        if not name or len(name) < 5:
            continue

        # Check if exists
        existing = await conn.fetchval("""
            SELECT supplier_id FROM suppliers
            WHERE LOWER(TRIM(company_name)) = LOWER(TRIM($1))
        """, name)

        if existing:
            already_exists += 1
            continue

        if dry_run:
            inserted += 1
            if inserted <= 10:
                print(f"      [NEW] {name[:60]}...")
            continue

        # Insert new supplier
        city = extract_city(name)
        try:
            result = await conn.fetchval("""
                INSERT INTO suppliers (company_name, city, epazar_operator_id, source, created_at, updated_at)
                VALUES ($1, $2, $3, 'epazar_operator', NOW(), NOW())
                ON CONFLICT (company_name) DO NOTHING
                RETURNING supplier_id
            """, name, city, str(epazar_id) if epazar_id else None)

            if result:
                inserted += 1
                if inserted <= 20:
                    print(f"      [{inserted}] {name[:60]}...")
        except Exception as e:
            print(f"      Error: {e}")

    print(f"      Inserted: {inserted}, Already existed: {already_exists}")
    return inserted


async def import_contracting_authorities(conn, authorities: list, dry_run: bool) -> int:
    """Import contracting authorities to suppliers table (they're also potential customers!)"""
    print(f"\nImporting {len(authorities)} contracting authorities to suppliers...")

    inserted = 0
    already_exists = 0

    for ca in authorities:
        name = ca.get('contractAuthorityName', '').strip()
        ca_id = ca.get('contractAuthorityId')

        if not name or len(name) < 5:
            continue

        # Check if exists
        existing = await conn.fetchval("""
            SELECT supplier_id FROM suppliers
            WHERE LOWER(TRIM(company_name)) = LOWER(TRIM($1))
        """, name)

        if existing:
            already_exists += 1
            continue

        if dry_run:
            inserted += 1
            if inserted <= 10:
                print(f"      [NEW] {name[:60]}...")
            continue

        # Insert new supplier
        city = extract_city(name)
        try:
            result = await conn.fetchval("""
                INSERT INTO suppliers (company_name, city, epazar_ca_id, source, created_at, updated_at)
                VALUES ($1, $2, $3, 'epazar_authority', NOW(), NOW())
                ON CONFLICT (company_name) DO NOTHING
                RETURNING supplier_id
            """, name, city, str(ca_id) if ca_id else None)

            if result:
                inserted += 1
                if inserted <= 20:
                    print(f"      [{inserted}] {name[:60]}...")
        except Exception as e:
            print(f"      Error: {e}")

    print(f"      Inserted: {inserted}, Already existed: {already_exists}")
    return inserted


async def main():
    print("=" * 70)
    print("E-PAZAR COMPREHENSIVE DATA EXTRACTION")
    print("=" * 70)

    dry_run = '--dry-run' in sys.argv
    contacts_only = '--contacts-only' in sys.argv

    if dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    conn = await asyncpg.connect(DATABASE_URL)

    # Check if required columns exist, add if not
    try:
        await conn.execute("""
            ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS epazar_operator_id VARCHAR(50);
            ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS epazar_ca_id VARCHAR(50);
            ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS source VARCHAR(50);
        """)
    except Exception as e:
        print(f"Column check: {e}")

    async with aiohttp.ClientSession() as session:
        total_inserted = 0

        if not contacts_only:
            # 1. Get all economic operators
            operators = await get_all_economic_operators(session)
            if operators:
                inserted = await import_economic_operators(conn, operators, dry_run)
                total_inserted += inserted

            # 2. Get all contracting authorities
            authorities = await get_all_contracting_authorities(session)
            if authorities:
                inserted = await import_contracting_authorities(conn, authorities, dry_run)
                total_inserted += inserted

        # 3. Get tender contacts
        tender_ids = await get_all_tender_ids(session)
        if tender_ids:
            contacts = await extract_tender_contacts(session, tender_ids, conn, dry_run)
            print(f"\n      Total contacts extracted:")
            print(f"        - Emails: {len(contacts['emails'])}")
            print(f"        - Phones: {len(contacts['phones'])}")
            print(f"        - Contact persons: {len(contacts['persons'])}")

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_suppliers,
            COUNT(*) FILTER (WHERE source = 'epazar_operator') as from_operators,
            COUNT(*) FILTER (WHERE source = 'epazar_authority') as from_authorities,
            COUNT(DISTINCT s.supplier_id) FILTER (WHERE sc.id IS NOT NULL) as with_contacts
        FROM suppliers s
        LEFT JOIN supplier_contacts sc ON s.supplier_id = sc.supplier_id
    """)

    email_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_emails,
            COUNT(*) FILTER (WHERE source_domain = 'epazar_tender') as from_tenders,
            COUNT(*) FILTER (WHERE confidence_score >= 90) as high_confidence
        FROM supplier_contacts
        WHERE email IS NOT NULL
    """)

    print("\n" + "=" * 70)
    print("FINAL STATISTICS")
    print("=" * 70)
    print(f"Total suppliers: {stats['total_suppliers']}")
    print(f"  - From e-pazar operators: {stats['from_operators']}")
    print(f"  - From e-pazar authorities: {stats['from_authorities']}")
    print(f"  - With contacts: {stats['with_contacts']}")
    print(f"\nTotal emails: {email_stats['total_emails']}")
    print(f"  - From tender details: {email_stats['from_tenders']}")
    print(f"  - High confidence (90+): {email_stats['high_confidence']}")

    await conn.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
