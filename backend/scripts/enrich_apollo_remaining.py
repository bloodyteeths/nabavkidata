#!/usr/bin/env python3
"""
Enrich ALL remaining Apollo MK contacts without email using Serper.
Uses company domain from Apollo data for better results.

Usage:
    SERPER_API_KEY=xxx python3 scripts/enrich_apollo_remaining.py
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import re
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
SKIP_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'example.com',
                'mail.com', 'aol.com', 'icloud.com', 'live.com', 'msn.com'}


def clean_name(name):
    """Clean name for search"""
    if not name:
        return ''
    return re.sub(r'[^\w\s]', '', name).strip()


def extract_domain(email):
    if '@' in email:
        return email.split('@')[1].lower()
    return None


def generate_email(first_name, last_name, domain):
    """Generate most likely email pattern"""
    first = re.sub(r'[^a-z]', '', (first_name or '').lower())
    last = re.sub(r'[^a-z]', '', (last_name or '').lower())
    if first and last and domain:
        return f"{first}.{last}@{domain}"
    elif first and domain:
        return f"{first}@{domain}"
    return None


async def search_serper(session, query: str) -> list:
    """Search Serper and extract emails"""
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "num": 10}

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status != 200:
                if resp.status == 429:
                    print("\n⚠️  Rate limited, waiting...")
                    await asyncio.sleep(5)
                return []

            data = await resp.json()
            all_text = ""
            for item in data.get('organic', []):
                all_text += f" {item.get('title', '')} {item.get('snippet', '')} "
            all_text += f" {data.get('knowledgeGraph', {}).get('description', '')} "

            emails = EMAIL_PATTERN.findall(all_text.lower())
            return [e for e in emails if extract_domain(e) not in SKIP_DOMAINS]
    except Exception as e:
        return []


async def enrich_contact(session, contact: dict) -> dict:
    """Find email for a contact using multiple strategies"""

    first_name = clean_name(contact['first_name'])
    last_name = clean_name(contact['last_name'])
    full_name = contact['full_name'] or f"{first_name} {last_name}".strip()
    company = clean_name(contact['company_name'])
    domain = contact['company_domain']

    result = {'email': None, 'domain': None, 'method': None}

    # Strategy 1: If we have domain, search on their website
    if domain:
        domain_clean = domain.replace('www.', '')
        emails = await search_serper(session, f"site:{domain_clean} email contact")
        if emails:
            result['domain'] = extract_domain(emails[0])
            # Generate personalized email
            generated = generate_email(first_name, last_name, result['domain'])
            result['email'] = generated or emails[0]
            result['method'] = 'domain_search'
            return result

    # Strategy 2: Person + Company search
    if full_name and company:
        emails = await search_serper(session, f'"{full_name}" "{company}" email')
        if emails:
            result['email'] = emails[0]
            result['domain'] = extract_domain(emails[0])
            result['method'] = 'person_company'
            return result

    # Strategy 3: Company + Macedonia search
    if company:
        emails = await search_serper(session, f'"{company}" Macedonia email contact')
        if emails:
            result['domain'] = extract_domain(emails[0])
            generated = generate_email(first_name, last_name, result['domain'])
            result['email'] = generated or emails[0]
            result['method'] = 'company_search'
            return result

    return result


async def main():
    print("=" * 70)
    print("ENRICH REMAINING APOLLO MK CONTACTS")
    print("=" * 70)

    if not SERPER_API_KEY:
        print("Error: SERPER_API_KEY not set")
        return

    conn = await asyncpg.connect(DATABASE_URL)

    # Get MK contacts without email
    contacts = await conn.fetch("""
        SELECT
            id, apollo_id, first_name, last_name, full_name,
            company_name, company_domain, job_title
        FROM apollo_contacts
        WHERE (country ILIKE '%macedonia%' OR country ILIKE '%FYROM%')
          AND (email IS NULL OR email LIKE '%not_unlocked%' OR email = '')
          AND company_name IS NOT NULL
        ORDER BY
            CASE WHEN company_domain IS NOT NULL THEN 0 ELSE 1 END,  -- Prioritize those with domain
            company_name
    """)

    print(f"\nFound {len(contacts)} MK contacts to enrich")
    print(f"Starting enrichment...\n")

    enriched = 0
    searched = 0
    start_time = datetime.now()

    async with aiohttp.ClientSession() as session:
        for i, contact in enumerate(contacts, 1):
            result = await enrich_contact(session, contact)
            searched += 1

            if result['email']:
                await conn.execute("""
                    UPDATE apollo_contacts
                    SET email = $1,
                        email_status = 'serper_final',
                        company_domain = COALESCE(company_domain, $2),
                        updated_at = NOW()
                    WHERE apollo_id = $3
                """, result['email'], result['domain'], contact['apollo_id'])

                # Also add to outreach_leads
                await conn.execute("""
                    INSERT INTO outreach_leads (
                        email, full_name, first_name, last_name, company_name,
                        job_title, segment, source, quality_score,
                        company_domain, country, apollo_contact_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, 'B', 'apollo', 75, $7, 'North Macedonia', $8)
                    ON CONFLICT (email) DO NOTHING
                """,
                    result['email'],
                    contact['full_name'],
                    contact['first_name'],
                    contact['last_name'],
                    contact['company_name'],
                    contact['job_title'],
                    result['domain'],
                    contact['id']  # Use UUID id, not apollo_id
                )

                enriched += 1
                if enriched <= 30 or enriched % 100 == 0:
                    print(f"  ✓ [{i}/{len(contacts)}] {contact['full_name']} -> {result['email']} ({result['method']})")

            if i % 100 == 0:
                rate = enriched / searched * 100 if searched > 0 else 0
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = searched / elapsed * 60 if elapsed > 0 else 0
                print(f"\n  Progress: {searched}/{len(contacts)} | {enriched} emails ({rate:.1f}%) | {speed:.0f}/min\n")

            await asyncio.sleep(0.4)

    # Final stats
    total_outreach = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")
    mk_with_email = await conn.fetchval("""
        SELECT COUNT(*) FROM apollo_contacts
        WHERE (country ILIKE '%macedonia%' OR country ILIKE '%FYROM%')
          AND email IS NOT NULL AND email NOT LIKE '%not_unlocked%'
    """)

    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Searched: {searched}")
    print(f"Emails found: {enriched} ({enriched/searched*100:.1f}% hit rate)")
    print(f"\nMK Apollo with email: {mk_with_email}")
    print(f"Total outreach leads: {total_outreach}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
