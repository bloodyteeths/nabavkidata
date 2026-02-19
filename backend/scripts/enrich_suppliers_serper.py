#!/usr/bin/env python3
"""
Enrich suppliers without emails using Serper API (Google Search)

Usage:
    python3 scripts/enrich_suppliers_serper.py --dry-run    # Preview only
    python3 scripts/enrich_suppliers_serper.py --limit=100  # Limit queries
    python3 scripts/enrich_suppliers_serper.py              # Full enrichment
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

# Serper API - User's key
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "3f204d308413293294eba57d56ff6e9958762197")


def extract_brand_name(company_name: str) -> str:
    """Extract short brand name from full legal name for better search"""
    if not company_name:
        return ""

    # Common Macedonian company prefixes to remove
    prefixes = [
        r'^Друштво за .+? ',
        r'^Трговско друштво .+? ',
        r'^Акционерско друштво .+? ',
        r'^Јавно претпријатие .+? ',
        r'^ЈЗУ\s+',
        r'^ЈП\s+',
        r'^ООУ\s+',
        r'^ОУ\s+',
        r'^ДООЕЛ\s*',
        r'^ДОО\s*',
        r'^Општина\s+',
    ]

    name = company_name
    for prefix in prefixes:
        name = re.sub(prefix, '', name, flags=re.IGNORECASE)

    # Remove suffixes
    suffixes = [
        r'\s+ДООЕЛ.*$',
        r'\s+ДОО.*$',
        r'\s+АД.*$',
        r'\s+увоз.*$',
        r'\s+извоз.*$',
        r'\s+експорт.*$',
        r'\s+импорт.*$',
        r'\s+-\s+Скопје.*$',
        r'\s+Скопје.*$',
    ]

    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)

    # Extract the brand part (usually in caps or at the start)
    # Try to find the main brand name
    caps_match = re.search(r'([А-ЯA-Z][А-Яа-яA-Za-z\s\-]{2,25})', name)
    if caps_match:
        return caps_match.group(1).strip()

    return name[:35].strip()


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
            elif resp.status == 403:
                print(f"    [RATE LIMITED] API quota exhausted")
                return None
            else:
                print(f"    [ERROR] Status {resp.status}")
                return None
    except Exception as e:
        print(f"    [ERROR] {e}")
        return None


def extract_emails_from_results(result: dict) -> list:
    """Extract emails from Serper search results"""
    emails = []

    if not result:
        return emails

    # Check organic results
    for item in result.get('organic', []):
        snippet = item.get('snippet', '') + ' ' + item.get('title', '')

        # Find emails in snippet
        found_emails = re.findall(r'[\w\.\-]+@[\w\.\-]+\.\w+', snippet)
        for email in found_emails:
            email = email.lower()
            # Filter out junk
            if (email not in emails and
                not email.endswith('.png') and
                not email.endswith('.jpg') and
                '@' in email and
                not any(x in email for x in ['example.com', 'sentry.io', 'wixpress', 'no-reply', 'noreply'])):
                # Skip generic emails
                if not any(generic in email for generic in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com']):
                    emails.append(email)

    # Check knowledge graph
    kg = result.get('knowledgeGraph', {})
    if kg.get('email'):
        email = kg['email'].lower()
        if email not in emails:
            emails.append(email)

    return emails[:3]  # Max 3 emails per supplier


def extract_website_from_results(result: dict) -> str:
    """Extract company website from Serper results"""
    if not result:
        return None

    # Check knowledge graph first
    kg = result.get('knowledgeGraph', {})
    if kg.get('website'):
        return kg['website']

    # Check organic results for .mk domain
    for item in result.get('organic', []):
        link = item.get('link', '')
        if '.mk' in link and 'facebook' not in link and 'linkedin' not in link:
            return link

    return None


async def get_suppliers_without_email(conn, limit: int = None) -> list:
    """Get suppliers without emails"""
    query = """
        SELECT s.supplier_id, s.company_name, s.city
        FROM suppliers s
        LEFT JOIN supplier_contacts sc ON s.supplier_id = sc.supplier_id
        WHERE sc.id IS NULL
        ORDER BY s.created_at DESC
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = await conn.fetch(query)
    return [dict(r) for r in rows]


async def enrich_supplier(conn, session, supplier: dict) -> dict:
    """Enrich a single supplier with Serper"""
    supplier_id = supplier['supplier_id']
    company_name = supplier['company_name']

    brand = extract_brand_name(company_name)

    # Search queries to try
    queries = [
        f"{brand} Македонија контакт email",
        f"{brand} official website contact",
    ]

    all_emails = []
    website = None

    for query in queries[:1]:  # Only use first query to save API credits
        result = await search_serper(session, query)

        if result:
            emails = extract_emails_from_results(result)
            for email in emails:
                if email not in all_emails:
                    all_emails.append(email)

            if not website:
                website = extract_website_from_results(result)

        await asyncio.sleep(0.5)  # Rate limit between queries

    # Store results
    contacts_added = 0
    for email in all_emails:
        try:
            await conn.execute("""
                INSERT INTO supplier_contacts
                (supplier_id, email, email_type, source_domain, confidence_score, status, created_at)
                VALUES ($1, $2, 'info', 'serper_search', 60, 'new', NOW())
                ON CONFLICT (supplier_id, email) DO NOTHING
            """, supplier_id, email)
            contacts_added += 1
        except Exception as e:
            pass

    # Update website if found
    if website:
        await conn.execute("""
            UPDATE suppliers SET website = $1, updated_at = NOW()
            WHERE supplier_id = $2 AND website IS NULL
        """, website, supplier_id)

    return {
        'emails': all_emails,
        'website': website,
        'contacts_added': contacts_added
    }


async def main():
    print("=" * 70)
    print("SERPER API ENRICHMENT FOR SUPPLIERS")
    print("=" * 70)

    dry_run = '--dry-run' in sys.argv

    # Parse limit
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    if dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    conn = await asyncpg.connect(DATABASE_URL)

    # Get suppliers without email
    suppliers = await get_suppliers_without_email(conn, limit)
    print(f"\nFound {len(suppliers)} suppliers without email")

    if not suppliers:
        print("No suppliers to enrich!")
        await conn.close()
        return

    if dry_run:
        print("\nSample suppliers to enrich:")
        for s in suppliers[:10]:
            brand = extract_brand_name(s['company_name'])
            print(f"  - {s['company_name'][:50]}...")
            print(f"    Brand: {brand}")
        await conn.close()
        return

    # Enrich suppliers
    print(f"\nEnriching {len(suppliers)} suppliers...")

    async with aiohttp.ClientSession() as session:
        enriched = 0
        emails_found = 0
        websites_found = 0
        rate_limited = False

        for i, supplier in enumerate(suppliers):
            if rate_limited:
                print(f"\n[STOPPED] Rate limited after {enriched} queries")
                break

            result = await enrich_supplier(conn, session, supplier)
            enriched += 1

            if result['emails']:
                emails_found += len(result['emails'])
                print(f"  [{enriched}/{len(suppliers)}] {supplier['company_name'][:40]}... -> {result['emails']}")
            else:
                if enriched <= 20 or enriched % 50 == 0:
                    print(f"  [{enriched}/{len(suppliers)}] {supplier['company_name'][:40]}... -> No email")

            if result['website']:
                websites_found += 1

            # Rate limit
            await asyncio.sleep(1)

            # Progress report
            if enriched % 50 == 0:
                print(f"\n  ... Progress: {enriched}/{len(suppliers)}, found {emails_found} emails, {websites_found} websites\n")

        print(f"\n" + "=" * 70)
        print(f"ENRICHMENT COMPLETE")
        print(f"=" * 70)
        print(f"Suppliers processed: {enriched}")
        print(f"Emails found: {emails_found}")
        print(f"Websites found: {websites_found}")

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_suppliers,
            COUNT(DISTINCT s.supplier_id) FILTER (WHERE sc.id IS NOT NULL) as with_contacts
        FROM suppliers s
        LEFT JOIN supplier_contacts sc ON s.supplier_id = sc.supplier_id
    """)

    email_stats = await conn.fetchrow("""
        SELECT COUNT(*) as total, COUNT(DISTINCT email) as unique_emails
        FROM supplier_contacts WHERE email IS NOT NULL
    """)

    print(f"\nDatabase totals:")
    print(f"  Total suppliers: {stats['total_suppliers']}")
    print(f"  With contacts: {stats['with_contacts']}")
    print(f"  Total emails: {email_stats['total']}")
    print(f"  Unique emails: {email_stats['unique_emails']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
