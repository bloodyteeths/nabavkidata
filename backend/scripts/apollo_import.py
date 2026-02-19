#!/usr/bin/env python3
"""
Import contacts from Apollo.io with full personalization data.
Pulls decision makers from Macedonia for cold outreach.

Usage:
    python3 scripts/apollo_import.py --dry-run
    python3 scripts/apollo_import.py --pages=10  # Import 10 pages (250 contacts)
    python3 scripts/apollo_import.py              # Full import
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

# Apollo API endpoints
APOLLO_BASE_URL = "https://api.apollo.io/v1"


async def reveal_email(session, person: dict) -> dict:
    """Reveal/unlock email for a contact using people/match (uses credits)"""
    url = f"{APOLLO_BASE_URL}/people/match"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }

    # Use name + company for matching
    first_name = person.get('first_name', '')
    last_name = person.get('last_name', '')
    org = person.get('organization', {}) or {}
    org_name = org.get('name', '')

    if not first_name or not last_name or not org_name:
        return None

    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": org_name,
        "reveal_personal_emails": True  # This costs credits
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('person', {})
            else:
                text = await resp.text()
                if "credit" in text.lower() or "limit" in text.lower() or "403" in str(resp.status):
                    return {"error": "OUT_OF_CREDITS"}
                print(f"    API error: {text[:100]}")
                return None
    except Exception as e:
        print(f"    Request error: {e}")
        return None


async def search_people(session, page: int = 1, reveal_emails: bool = True, countries: list = None) -> dict:
    """
    Search for people in target countries using Apollo API.
    Focus on decision makers (Owners, Directors, CEOs, etc.)
    """
    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY
    }

    # Default to Macedonia only - get ALL contacts from Macedonia first
    if countries is None:
        countries = [
            "Macedonia", "North Macedonia"  # ~6,000+ decision makers
        ]

    payload = {
        "page": page,
        "per_page": 100,  # Max per page for efficiency

        # Location filter: Balkans region
        "person_locations": countries,

        # Job titles: Decision makers
        "person_titles": [
            "Owner", "Director", "CEO", "Managing Director",
            "General Manager", "CFO", "CTO", "COO",
            "Founder", "Co-Founder", "Partner",
            "Head of", "VP", "Vice President",
            "Procurement", "Purchasing", "Supply Chain"  # Added for B2G relevance
        ],

        # Company size: SMBs (most tender participants)
        "organization_num_employees_ranges": [
            "1,10", "11,20", "21,50", "51,100", "101,200", "201,500", "501,1000"
        ],

        # Request email reveal
        "reveal_personal_emails": reveal_emails,
        "reveal_phone_number": reveal_emails,
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                text = await resp.text()
                print(f"    Apollo API error {resp.status}: {text[:200]}")
                return None
    except Exception as e:
        print(f"    Request error: {e}")
        return None


async def get_contact_details(session, apollo_id: str) -> dict:
    """Get full contact details including email"""
    url = f"{APOLLO_BASE_URL}/people/{apollo_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }

    try:
        async with session.get(url, headers=headers, timeout=30) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
    except:
        return None


async def enrich_contact(session, email: str) -> dict:
    """Enrich a contact by email to get full details"""
    url = f"{APOLLO_BASE_URL}/people/match"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }

    payload = {
        "email": email,
        "reveal_personal_emails": True
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
    except:
        return None


async def create_tables_if_needed(conn):
    """Create apollo_contacts table if it doesn't exist"""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS apollo_contacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            apollo_id VARCHAR(100) UNIQUE,
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            full_name VARCHAR(500),
            email VARCHAR(255),
            email_status VARCHAR(50),
            job_title VARCHAR(255),
            seniority VARCHAR(100),
            department VARCHAR(100),
            linkedin_url TEXT,
            phone VARCHAR(100),
            company_name VARCHAR(500),
            company_domain VARCHAR(255),
            company_linkedin TEXT,
            company_industry VARCHAR(255),
            company_size VARCHAR(100),
            company_location VARCHAR(500),
            city VARCHAR(255),
            country VARCHAR(100),
            personalization_data JSONB,
            raw_data JSONB,
            supplier_id UUID REFERENCES suppliers(supplier_id),
            imported_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_apollo_contacts_email ON apollo_contacts(email);
        CREATE INDEX IF NOT EXISTS idx_apollo_contacts_company ON apollo_contacts(company_name);
        CREATE INDEX IF NOT EXISTS idx_apollo_contacts_supplier ON apollo_contacts(supplier_id);
    """)


async def insert_contact(conn, person: dict) -> bool:
    """Insert a contact from Apollo into database"""

    # Extract all available data for personalization
    apollo_id = person.get('id')
    first_name = person.get('first_name', '')
    last_name = person.get('last_name', '')
    full_name = person.get('name', f"{first_name} {last_name}".strip())

    email = person.get('email')
    email_status = person.get('email_status')

    title = person.get('title', '')
    seniority = person.get('seniority', '')
    departments = person.get('departments', [])
    department = departments[0] if departments else ''

    linkedin_url = person.get('linkedin_url')
    phone = person.get('phone_number')

    # Company info
    org = person.get('organization', {}) or {}
    company_name = org.get('name', '')
    company_domain = org.get('primary_domain', '')
    company_linkedin = org.get('linkedin_url')
    company_industry = org.get('industry', '')
    company_size = org.get('estimated_num_employees')

    # Location
    city = person.get('city', '')
    country = person.get('country', '')
    company_location = org.get('raw_address', '')

    # Personalization data for cold emails
    personalization = {
        'title': title,
        'seniority': seniority,
        'department': department,
        'company_industry': company_industry,
        'company_size': company_size,
        'keywords': org.get('keywords', []),
        'technologies': org.get('technologies', []),
        'recent_news': person.get('headline', ''),
    }

    try:
        await conn.execute("""
            INSERT INTO apollo_contacts (
                apollo_id, first_name, last_name, full_name,
                email, email_status, job_title, seniority, department,
                linkedin_url, phone,
                company_name, company_domain, company_linkedin,
                company_industry, company_size, company_location,
                city, country,
                personalization_data, raw_data
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            )
            ON CONFLICT (apollo_id) DO UPDATE SET
                email = EXCLUDED.email,
                email_status = EXCLUDED.email_status,
                job_title = EXCLUDED.job_title,
                updated_at = NOW()
        """,
            apollo_id, first_name, last_name, full_name,
            email, email_status, title, seniority, department,
            linkedin_url, phone,
            company_name, company_domain, company_linkedin,
            company_industry, str(company_size) if company_size else None, company_location,
            city, country,
            json.dumps(personalization), json.dumps(person)
        )
        return True
    except Exception as e:
        print(f"    Insert error: {e}")
        return False


async def link_to_suppliers(conn):
    """Link Apollo contacts to existing suppliers by company name"""
    result = await conn.execute("""
        UPDATE apollo_contacts ac
        SET supplier_id = s.supplier_id
        FROM suppliers s
        WHERE LOWER(TRIM(ac.company_name)) = LOWER(TRIM(s.company_name))
          AND ac.supplier_id IS NULL
    """)
    return result


async def main():
    print("=" * 70)
    print("APOLLO.IO CONTACT IMPORT")
    print("=" * 70)

    dry_run = '--dry-run' in sys.argv

    # Parse pages
    max_pages = 100  # Default to get as many as possible
    for arg in sys.argv:
        if arg.startswith('--pages='):
            max_pages = int(arg.split('=')[1])

    conn = await asyncpg.connect(DATABASE_URL)
    await create_tables_if_needed(conn)

    print(f"\nSearching Apollo for Macedonian decision makers...")
    print(f"Max pages: {max_pages} (25 contacts per page)")

    total_imported = 0
    total_with_email = 0

    async with aiohttp.ClientSession() as session:
        page = 1
        empty_pages = 0
        out_of_credits = False
        revealed_emails = 0

        while page <= max_pages and empty_pages < 3 and not out_of_credits:
            print(f"\n[Page {page}/{max_pages}] Fetching contacts...")

            result = await search_people(session, page)

            if not result:
                empty_pages += 1
                page += 1
                continue

            people = result.get('people', [])
            if not people:
                empty_pages += 1
                print(f"    No more contacts found")
                page += 1
                continue

            pagination = result.get('pagination', {})
            total_available = pagination.get('total_entries', 0)
            print(f"    Found {len(people)} contacts (total available: {total_available:,})")

            if dry_run:
                for p in people[:5]:
                    email = p.get('email', 'N/A')
                    name = p.get('name', 'N/A')
                    title = p.get('title', 'N/A')
                    company = p.get('organization', {}).get('name', 'N/A')
                    country = p.get('country', 'N/A')
                    print(f"      - {name} | {title} | {company} | {country}")
            else:
                for person in people:
                    # Try to reveal email using people/match
                    revealed = await reveal_email(session, person)

                    if revealed and revealed.get('error') == 'OUT_OF_CREDITS':
                        print(f"\n    [OUT OF CREDITS] Stopping email reveals")
                        out_of_credits = True
                        break

                    # Use revealed data if available, otherwise use search data
                    if revealed and revealed.get('email') and '@' in revealed.get('email', ''):
                        person['email'] = revealed['email']
                        person['phone_number'] = revealed.get('phone_number')
                        revealed_emails += 1
                        if revealed_emails <= 20 or revealed_emails % 50 == 0:
                            print(f"      ✓ Revealed: {person.get('name')} -> {revealed['email']}")

                    success = await insert_contact(conn, person)
                    if success:
                        total_imported += 1
                        if person.get('email') and '@' in person.get('email', '') and 'not_unlocked' not in person.get('email', ''):
                            total_with_email += 1

                    await asyncio.sleep(0.2)  # Rate limit for reveals

            page += 1
            await asyncio.sleep(0.5)  # Rate limit between pages

            # Progress report
            if page % 5 == 0:
                print(f"\n    Progress: {total_imported} imported, {revealed_emails} emails revealed")

    if dry_run:
        print(f"\n[DRY RUN - No changes made]")
        await conn.close()
        return

    # Link to existing suppliers
    print(f"\nLinking contacts to existing suppliers...")
    await link_to_suppliers(conn)

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_contacts,
            COUNT(email) as with_email,
            COUNT(DISTINCT company_name) as unique_companies,
            COUNT(supplier_id) as linked_to_suppliers
        FROM apollo_contacts
    """)

    print(f"\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"Total contacts imported: {total_imported}")
    print(f"With email: {total_with_email}")
    print(f"\nDatabase totals:")
    print(f"  Total Apollo contacts: {stats['total_contacts']}")
    print(f"  With email: {stats['with_email']}")
    print(f"  Unique companies: {stats['unique_companies']}")
    print(f"  Linked to suppliers: {stats['linked_to_suppliers']}")

    # Sample personalization data
    sample = await conn.fetchrow("""
        SELECT full_name, email, job_title, company_name, personalization_data
        FROM apollo_contacts
        WHERE email IS NOT NULL
        LIMIT 1
    """)

    if sample:
        print(f"\nSample contact for personalization:")
        print(f"  Name: {sample['full_name']}")
        print(f"  Email: {sample['email']}")
        print(f"  Title: {sample['job_title']}")
        print(f"  Company: {sample['company_name']}")
        print(f"  Personalization: {sample['personalization_data']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
