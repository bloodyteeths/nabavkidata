#!/usr/bin/env python3
"""
Enrich Apollo contacts with Serper - find emails for contacts without them.
Prioritizes high-value decision makers (CEO, Director, Owner).

Usage:
    python3 scripts/enrich_apollo_serper.py --dry-run
    python3 scripts/enrich_apollo_serper.py --limit=100
    python3 scripts/enrich_apollo_serper.py  # Use all available credits
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import re
import json
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "3f204d308413293294eba57d56ff6e9958762197")

# Email regex
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Skip generic emails
SKIP_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'example.com',
                'email.com', 'mail.com', 'test.com', 'domain.com'}


async def search_email(session, name: str, company: str, domain: str = None) -> str:
    """Search for person's email using Serper"""

    # Build search query
    if domain:
        query = f'"{name}" email @{domain}'
    else:
        query = f'"{name}" "{company}" email'

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"q": query, "num": 10}

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()

            # Search in all results
            all_text = ""

            # Organic results
            for item in data.get('organic', []):
                all_text += f" {item.get('title', '')} {item.get('snippet', '')} "

            # Knowledge graph
            kg = data.get('knowledgeGraph', {})
            all_text += f" {kg.get('description', '')} "

            # Find emails
            emails = EMAIL_PATTERN.findall(all_text.lower())

            # Filter and prioritize
            for email in emails:
                email_domain = email.split('@')[1] if '@' in email else ''

                # Skip generic domains
                if email_domain in SKIP_DOMAINS:
                    continue

                # Prefer company domain match
                if domain and domain.lower() in email_domain:
                    return email

                # Accept if looks like business email
                if email_domain and '.' in email_domain:
                    return email

            return None
    except Exception as e:
        print(f"    Search error: {e}")
        return None


async def main():
    print("=" * 70)
    print("ENRICH APOLLO CONTACTS WITH SERPER")
    print("=" * 70)

    dry_run = '--dry-run' in sys.argv

    # Parse limit
    limit = 141  # Default to remaining Serper credits
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    conn = await asyncpg.connect(DATABASE_URL)

    # Get contacts needing emails, prioritize by title
    contacts = await conn.fetch("""
        SELECT apollo_id, first_name, last_name, full_name,
               company_name, company_domain, job_title, country
        FROM apollo_contacts
        WHERE (email IS NULL OR email LIKE '%not_unlocked%' OR email = '')
          AND first_name IS NOT NULL
          AND last_name IS NOT NULL
          AND company_name IS NOT NULL
        ORDER BY
            CASE
                WHEN job_title ILIKE '%ceo%' OR job_title ILIKE '%owner%' THEN 1
                WHEN job_title ILIKE '%director%' OR job_title ILIKE '%founder%' THEN 2
                WHEN job_title ILIKE '%manager%' OR job_title ILIKE '%head%' THEN 3
                WHEN job_title ILIKE '%procurement%' OR job_title ILIKE '%purchasing%' THEN 4
                ELSE 5
            END,
            company_name
        LIMIT $1
    """, limit)

    print(f"\nFound {len(contacts)} contacts to enrich")
    print(f"Serper credits to use: {limit}")

    if dry_run:
        print("\n[DRY RUN - No API calls]")
        for c in contacts[:10]:
            print(f"  Would search: {c['full_name']} at {c['company_name']} ({c['job_title']})")
        await conn.close()
        return

    enriched = 0
    searched = 0

    async with aiohttp.ClientSession() as session:
        for i, contact in enumerate(contacts, 1):
            name = contact['full_name'] or f"{contact['first_name']} {contact['last_name']}"
            company = contact['company_name']
            domain = contact['company_domain']
            apollo_id = contact['apollo_id']

            email = await search_email(session, name, company, domain)
            searched += 1

            if email:
                # Update database
                await conn.execute("""
                    UPDATE apollo_contacts
                    SET email = $1,
                        email_status = 'serper_enriched',
                        updated_at = NOW()
                    WHERE apollo_id = $2
                """, email, apollo_id)

                enriched += 1
                print(f"  ✓ [{i}/{len(contacts)}] {name} ({contact['job_title']}) -> {email}")

            # Progress
            if i % 20 == 0:
                print(f"\n  Progress: {searched} searched, {enriched} emails found ({enriched/searched*100:.1f}%)\n")

            # Rate limit
            await asyncio.sleep(0.5)

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN email IS NOT NULL AND email NOT LIKE '%not_unlocked%' THEN 1 END) as with_email
        FROM apollo_contacts
    """)

    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Searched: {searched}")
    print(f"Emails found: {enriched} ({enriched/searched*100:.1f}% hit rate)")
    print(f"\nApollo contacts total: {stats['total']}")
    print(f"Apollo contacts with email: {stats['with_email']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
