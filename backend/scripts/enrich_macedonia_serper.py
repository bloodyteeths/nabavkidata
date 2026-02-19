#!/usr/bin/env python3
"""
Enrich MACEDONIA-ONLY Apollo contacts using Serper.
Combines person search and company domain search for best results.

Usage:
    python3 scripts/enrich_macedonia_serper.py --limit=3500
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
                'mail.com', 'test.com', 'domain.com', 'email.com', 'aol.com',
                'icloud.com', 'live.com', 'msn.com', 'protonmail.com'}


def extract_domain(email):
    if '@' in email:
        return email.split('@')[1].lower()
    return None


def generate_email_variants(first_name, last_name, domain):
    first = re.sub(r'[^a-z]', '', first_name.lower().strip()) if first_name else ''
    last = re.sub(r'[^a-z]', '', last_name.lower().strip()) if last_name else ''

    if not first or not last or not domain:
        return []

    return [
        f"{first}.{last}@{domain}",
        f"{first}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}{last}@{domain}",
    ]


async def search_serper(session: aiohttp.ClientSession, query: str) -> list:
    """Search Serper and extract emails"""
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "num": 10}

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status != 200:
                return []

            data = await resp.json()
            all_text = ""

            for item in data.get('organic', []):
                all_text += f" {item.get('title', '')} {item.get('snippet', '')} "

            kg = data.get('knowledgeGraph', {})
            all_text += f" {kg.get('description', '')} "

            emails = EMAIL_PATTERN.findall(all_text.lower())
            return [e for e in emails if extract_domain(e) not in SKIP_DOMAINS]
    except:
        return []


async def enrich_contact(session, conn, contact: dict) -> bool:
    """Try multiple search strategies to find email"""

    first_name = contact['first_name'] or ''
    last_name = contact['last_name'] or ''
    full_name = contact['full_name'] or f"{first_name} {last_name}".strip()
    company = contact['company_name'] or ''
    apollo_id = contact['apollo_id']

    if not full_name or not company:
        return False

    # Clean company name
    company_clean = re.sub(r'\b(doo|dooel|ltd|llc|inc|d\.o\.o\.?)\b', '', company, flags=re.I).strip()

    # Strategy 1: Person + company email search
    emails = await search_serper(session, f'"{full_name}" "{company_clean}" email Macedonia')

    # Strategy 2: Company contact search (if no results)
    if not emails:
        emails = await search_serper(session, f'"{company_clean}" Macedonia email contact @')

    # Strategy 3: Company website search
    if not emails:
        emails = await search_serper(session, f'"{company_clean}" Macedonia site contact')

    if emails:
        # Use first found email or generate from domain
        email = emails[0]
        domain = extract_domain(email)

        # Try to make it personal
        variants = generate_email_variants(first_name, last_name, domain)
        if variants:
            email = variants[0]  # first.last@domain

        await conn.execute("""
            UPDATE apollo_contacts
            SET email = $1,
                email_status = 'serper_mk',
                company_domain = $2,
                updated_at = NOW()
            WHERE apollo_id = $3
        """, email, domain, apollo_id)

        return True

    return False


async def main():
    print("=" * 70)
    print("MACEDONIA-ONLY SERPER ENRICHMENT")
    print("=" * 70)

    if not SERPER_API_KEY:
        print("Error: SERPER_API_KEY not set")
        return

    limit = 3500
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    conn = await asyncpg.connect(DATABASE_URL)

    # Get Macedonia contacts without email
    contacts = await conn.fetch("""
        SELECT apollo_id, first_name, last_name, full_name, company_name, job_title
        FROM apollo_contacts
        WHERE (country ILIKE '%macedonia%' OR country ILIKE '%FYROM%')
          AND (email IS NULL OR email LIKE '%not_unlocked%' OR email = '')
          AND company_name IS NOT NULL
          AND company_name != ''
        ORDER BY
            CASE
                WHEN job_title ILIKE '%ceo%' OR job_title ILIKE '%owner%' THEN 1
                WHEN job_title ILIKE '%director%' OR job_title ILIKE '%founder%' THEN 2
                WHEN job_title ILIKE '%manager%' THEN 3
                ELSE 4
            END,
            company_name
        LIMIT $1
    """, limit)

    print(f"\nFound {len(contacts)} Macedonia contacts to enrich")
    print(f"Starting enrichment...\n")

    enriched = 0
    searched = 0
    start_time = datetime.now()

    async with aiohttp.ClientSession() as session:
        for i, contact in enumerate(contacts, 1):
            success = await enrich_contact(session, conn, contact)
            searched += 1

            if success:
                enriched += 1
                if enriched <= 30 or enriched % 100 == 0:
                    print(f"  ✓ [{i}/{len(contacts)}] {contact['full_name']} ({contact['job_title'][:30] if contact['job_title'] else 'N/A'})")

            if i % 100 == 0:
                rate = enriched / searched * 100 if searched > 0 else 0
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = searched / elapsed * 60 if elapsed > 0 else 0
                print(f"\n  Progress: {searched}/{len(contacts)} | {enriched} emails ({rate:.1f}%) | {speed:.0f}/min\n")

            await asyncio.sleep(0.4)

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN email IS NOT NULL AND email NOT LIKE '%not_unlocked%' THEN 1 END) as with_email
        FROM apollo_contacts
        WHERE country ILIKE '%macedonia%' OR country ILIKE '%FYROM%'
    """)

    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Searched: {searched}")
    print(f"Emails found: {enriched} ({enriched/searched*100:.1f}% hit rate)")
    print(f"\nMacedonia Apollo contacts: {stats['total']}")
    print(f"Macedonia with email: {stats['with_email']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
