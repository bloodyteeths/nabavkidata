#!/usr/bin/env python3
"""
Enrich Apollo contacts by finding company emails via Serper.
Searches for company contact info rather than individual emails.

Usage:
    python3 scripts/enrich_apollo_company.py --limit=1000
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import re
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
SKIP_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'example.com',
                'mail.com', 'test.com', 'domain.com', 'email.com', 'sampleemail.com'}


def extract_domain(email):
    """Extract domain from email"""
    if '@' in email:
        return email.split('@')[1].lower()
    return None


def generate_email_variants(first_name, last_name, domain):
    """Generate common email patterns"""
    first = first_name.lower().strip()
    last = last_name.lower().strip()

    # Handle special characters
    first = re.sub(r'[^a-z]', '', first)
    last = re.sub(r'[^a-z]', '', last)

    if not first or not last or not domain:
        return []

    return [
        f"{first}.{last}@{domain}",
        f"{first}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}{last[0]}@{domain}",
        f"{first}_{last}@{domain}",
        f"{last}.{first}@{domain}",
    ]


async def search_company_email(session, company: str, country: str) -> dict:
    """Search for company contact email"""

    # Clean company name
    company_clean = re.sub(r'\b(doo|dooel|ltd|llc|inc|corp|gmbh|d\.o\.o\.?)\b', '', company, flags=re.I).strip()

    query = f'"{company_clean}" {country} email contact site'

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "num": 10}

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()
            all_text = ""

            for item in data.get('organic', []):
                all_text += f" {item.get('title', '')} {item.get('snippet', '')} "

            # Also check knowledge graph
            kg = data.get('knowledgeGraph', {})
            all_text += f" {kg.get('description', '')} "

            emails = EMAIL_PATTERN.findall(all_text.lower())

            # Filter and find best email
            valid_emails = []
            for email in emails:
                domain = extract_domain(email)
                if domain and domain not in SKIP_DOMAINS:
                    valid_emails.append(email)

            if valid_emails:
                # Return first valid email and its domain
                return {
                    'email': valid_emails[0],
                    'domain': extract_domain(valid_emails[0]),
                    'all_emails': list(set(valid_emails))[:5]
                }

            return None
    except Exception as e:
        return None


async def main():
    print("=" * 70)
    print("ENRICH APOLLO CONTACTS (COMPANY EMAIL SEARCH)")
    print("=" * 70)

    if not SERPER_API_KEY:
        print("Error: SERPER_API_KEY not set")
        return

    limit = 1000
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    conn = await asyncpg.connect(DATABASE_URL)

    # Get unique companies needing enrichment
    companies = await conn.fetch("""
        SELECT DISTINCT company_name, country,
               (SELECT apollo_id FROM apollo_contacts ac2
                WHERE ac2.company_name = ac.company_name
                  AND (ac2.email IS NULL OR ac2.email LIKE '%not_unlocked%')
                LIMIT 1) as sample_apollo_id,
               (SELECT first_name FROM apollo_contacts ac2
                WHERE ac2.company_name = ac.company_name LIMIT 1) as sample_first,
               (SELECT last_name FROM apollo_contacts ac2
                WHERE ac2.company_name = ac.company_name LIMIT 1) as sample_last
        FROM apollo_contacts ac
        WHERE (email IS NULL OR email LIKE '%not_unlocked%' OR email = '')
          AND company_name IS NOT NULL
          AND company_name != ''
        ORDER BY company_name
        LIMIT $1
    """, limit)

    print(f"\nFound {len(companies)} unique companies to search")

    searched = 0
    found = 0
    updated = 0

    async with aiohttp.ClientSession() as session:
        for i, company in enumerate(companies, 1):
            company_name = company['company_name']
            country = company['country'] or 'Macedonia'

            result = await search_company_email(session, company_name, country)
            searched += 1

            if result:
                found += 1
                domain = result['domain']
                company_email = result['email']

                # Update all contacts from this company with generated emails
                contacts = await conn.fetch("""
                    SELECT apollo_id, first_name, last_name
                    FROM apollo_contacts
                    WHERE company_name = $1
                      AND (email IS NULL OR email LIKE '%not_unlocked%')
                """, company_name)

                for contact in contacts:
                    # Try to generate personalized email
                    variants = generate_email_variants(
                        contact['first_name'] or '',
                        contact['last_name'] or '',
                        domain
                    )

                    # Use first variant or company email
                    email = variants[0] if variants else company_email

                    await conn.execute("""
                        UPDATE apollo_contacts
                        SET email = $1,
                            email_status = 'serper_company',
                            company_domain = $2,
                            updated_at = NOW()
                        WHERE apollo_id = $3
                    """, email, domain, contact['apollo_id'])
                    updated += 1

                if found <= 30 or found % 50 == 0:
                    print(f"  ✓ [{i}/{len(companies)}] {company_name} -> {domain} ({len(contacts)} contacts)")

            if i % 100 == 0:
                print(f"\n  Progress: {searched} searched, {found} domains found, {updated} contacts updated\n")

            await asyncio.sleep(0.5)

    # Stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN email IS NOT NULL AND email NOT LIKE '%not_unlocked%' THEN 1 END) as with_email
        FROM apollo_contacts
    """)

    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Companies searched: {searched}")
    print(f"Domains found: {found} ({found/searched*100:.1f}%)")
    print(f"Contacts updated: {updated}")
    print(f"\nApollo contacts total: {stats['total']}")
    print(f"Apollo contacts with email: {stats['with_email']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
