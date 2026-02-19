#!/usr/bin/env python3
"""
Import and reveal emails from Apollo for Balkans countries.
Processes contacts with parallel requests for speed.

Usage:
    python3 scripts/apollo_import_balkans.py --country=Serbia --pages=100
    python3 scripts/apollo_import_balkans.py --country=Croatia --pages=50
    python3 scripts/apollo_import_balkans.py --all --pages=50  # All Balkans
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "M5Ker5RzIA9flD0s_IONEA")
APOLLO_BASE_URL = "https://api.apollo.io/v1"

COUNTRIES = {
    "Serbia": ["Serbia"],
    "Kosovo": ["Kosovo"],
    "Albania": ["Albania"],
    "Montenegro": ["Montenegro"],
    "Bosnia": ["Bosnia", "Bosnia and Herzegovina"],
    "Croatia": ["Croatia"],
    "Slovenia": ["Slovenia"],
}

CONCURRENCY = 10
stats = {"imported": 0, "revealed": 0, "failed": 0}
out_of_credits = False


async def search_people(session, countries: list, page: int) -> dict:
    """Search Apollo for decision makers"""
    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }

    payload = {
        "page": page,
        "per_page": 100,
        "person_locations": countries,
        "person_titles": [
            "Owner", "Director", "CEO", "Managing Director",
            "General Manager", "CFO", "CTO", "COO",
            "Founder", "Co-Founder", "Partner",
            "Procurement", "Purchasing", "Supply Chain"
        ],
        "organization_num_employees_ranges": [
            "1,10", "11,20", "21,50", "51,100", "101,200", "201,500", "501,1000"
        ]
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
    except:
        return None


async def reveal_and_insert(session, conn, person: dict) -> bool:
    """Reveal email and insert contact"""
    global stats, out_of_credits

    if out_of_credits:
        return False

    apollo_id = person.get('id')
    first_name = person.get('first_name', '')
    last_name = person.get('last_name', '')
    org = person.get('organization', {}) or {}
    company_name = org.get('name', '')

    if not first_name or not last_name or not company_name:
        return False

    # Try to reveal email
    reveal_url = f"{APOLLO_BASE_URL}/people/match"
    headers = {"Content-Type": "application/json", "X-Api-Key": APOLLO_API_KEY}
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": company_name,
        "reveal_personal_emails": True
    }

    email = None
    email_status = None

    try:
        async with session.post(reveal_url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                revealed = data.get('person', {})
                email = revealed.get('email')
                email_status = revealed.get('email_status')

                if email and 'not_unlocked' in email.lower():
                    email = None

            elif resp.status in (403, 429):
                text = await resp.text()
                if 'credit' in text.lower():
                    out_of_credits = True
                    print(f"\n⚠️  OUT OF CREDITS")
                    return False
    except:
        pass

    # Insert contact
    full_name = person.get('name', f"{first_name} {last_name}".strip())
    title = person.get('title', '')
    seniority = person.get('seniority', '')
    departments = person.get('departments', [])
    department = departments[0] if departments else ''
    linkedin_url = person.get('linkedin_url')
    phone = person.get('phone_number')
    city = person.get('city', '')
    country = person.get('country', '')
    company_domain = org.get('primary_domain', '')
    company_linkedin = org.get('linkedin_url')
    company_industry = org.get('industry', '')
    company_size = org.get('estimated_num_employees')
    company_location = org.get('raw_address', '')

    personalization = {
        'title': title,
        'seniority': seniority,
        'department': department,
        'company_industry': company_industry,
        'company_size': company_size,
        'keywords': org.get('keywords', []),
        'technologies': org.get('technologies', []),
    }

    try:
        await conn.execute("""
            INSERT INTO apollo_contacts (
                apollo_id, first_name, last_name, full_name,
                email, email_status, job_title, seniority, department,
                linkedin_url, phone,
                company_name, company_domain, company_linkedin,
                company_industry, company_size, company_location,
                city, country, personalization_data, raw_data
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            )
            ON CONFLICT (apollo_id) DO UPDATE SET
                email = COALESCE(EXCLUDED.email, apollo_contacts.email),
                email_status = COALESCE(EXCLUDED.email_status, apollo_contacts.email_status),
                updated_at = NOW()
        """,
            apollo_id, first_name, last_name, full_name,
            email, email_status, title, seniority, department,
            linkedin_url, phone,
            company_name, company_domain, company_linkedin,
            company_industry, str(company_size) if company_size else None, company_location,
            city, country, json.dumps(personalization), json.dumps(person)
        )

        stats["imported"] += 1
        if email and '@' in email:
            stats["revealed"] += 1
            if stats["revealed"] <= 30 or stats["revealed"] % 100 == 0:
                print(f"  ✓ {first_name} {last_name} ({country}) -> {email}")
        return True
    except Exception as e:
        stats["failed"] += 1
        return False


async def process_country(session, conn, country_name: str, locations: list, max_pages: int):
    """Process all contacts from a country"""
    global out_of_credits

    print(f"\n{'='*60}")
    print(f"IMPORTING: {country_name}")
    print(f"{'='*60}")

    # First check total available
    result = await search_people(session, locations, 1)
    if not result:
        print(f"  Failed to search {country_name}")
        return

    total_available = result.get('pagination', {}).get('total_entries', 0)
    print(f"Total available: {total_available:,} contacts")
    print(f"Fetching up to {max_pages} pages (100 contacts each)...")

    for page in range(1, max_pages + 1):
        if out_of_credits:
            print(f"  Stopping - out of credits")
            break

        result = await search_people(session, locations, page)
        if not result:
            break

        people = result.get('people', [])
        if not people:
            print(f"  No more contacts at page {page}")
            break

        # Process batch with concurrency
        tasks = [reveal_and_insert(session, conn, p) for p in people]
        await asyncio.gather(*tasks)

        if page % 5 == 0 or page == 1:
            print(f"  Page {page}: {stats['imported']} imported, {stats['revealed']} emails revealed")

        await asyncio.sleep(0.3)


async def main():
    print("=" * 70)
    print("APOLLO BALKANS IMPORT")
    print("=" * 70)

    # Parse arguments
    target_country = None
    max_pages = 100
    import_all = '--all' in sys.argv

    for arg in sys.argv:
        if arg.startswith('--country='):
            target_country = arg.split('=')[1]
        elif arg.startswith('--pages='):
            max_pages = int(arg.split('=')[1])

    if not target_country and not import_all:
        print("\nUsage:")
        print("  --country=Serbia   Import single country")
        print("  --all              Import all Balkans")
        print("  --pages=100        Max pages per country")
        return

    conn = await asyncpg.connect(DATABASE_URL)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector) as session:
        if import_all:
            for country, locations in COUNTRIES.items():
                if out_of_credits:
                    break
                await process_country(session, conn, country, locations, max_pages)
        else:
            if target_country not in COUNTRIES:
                print(f"Unknown country: {target_country}")
                print(f"Available: {', '.join(COUNTRIES.keys())}")
                return
            await process_country(session, conn, target_country,
                                  COUNTRIES[target_country], max_pages)

    # Final stats
    db_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN email IS NOT NULL AND email NOT LIKE '%not_unlocked%' THEN 1 END) as with_email,
            COUNT(DISTINCT country) as countries
        FROM apollo_contacts
    """)

    print("\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"This run: {stats['imported']} imported, {stats['revealed']} emails revealed")
    print(f"\nDatabase totals:")
    print(f"  Total Apollo contacts: {db_stats['total']}")
    print(f"  With email: {db_stats['with_email']}")
    print(f"  Countries: {db_stats['countries']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
