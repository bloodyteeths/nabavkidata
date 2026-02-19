#!/usr/bin/env python3
"""
Enrich tender bidders (Segment A - highest quality) with Serper.
These are companies that actively participate in government tenders.

Usage:
    SERPER_API_KEY=xxx python3 scripts/enrich_tender_bidders.py
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


def extract_domain(email):
    if '@' in email:
        return email.split('@')[1].lower()
    return None


def clean_company_name(name):
    """Clean Macedonian company names for search"""
    if not name:
        return ''
    # Remove common prefixes
    prefixes = ['Друштво за', 'Трговско друштво за', 'Акционерско друштво',
                'Градежно друштво', 'ДОО', 'ДООЕЛ', 'АД', 'Производство']
    result = name
    for prefix in prefixes:
        result = result.replace(prefix, '').strip()
    return result.strip()


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


async def enrich_company(session, company_name: str) -> dict:
    """Find email for a company using multiple strategies"""

    result = {'email': None, 'domain': None, 'method': None}
    clean_name = clean_company_name(company_name)

    # Strategy 1: Company + Macedonia + email search
    emails = await search_serper(session, f'"{clean_name}" Македонија email контакт')
    if emails:
        result['email'] = emails[0]
        result['domain'] = extract_domain(emails[0])
        result['method'] = 'macedonian_search'
        return result

    # Strategy 2: Company + contact search (Latin)
    emails = await search_serper(session, f'"{clean_name}" Macedonia email contact')
    if emails:
        result['email'] = emails[0]
        result['domain'] = extract_domain(emails[0])
        result['method'] = 'latin_search'
        return result

    # Strategy 3: Simple company search
    emails = await search_serper(session, f'{company_name} email')
    if emails:
        result['email'] = emails[0]
        result['domain'] = extract_domain(emails[0])
        result['method'] = 'simple_search'
        return result

    return result


async def main():
    print("=" * 70)
    print("ENRICH TENDER BIDDERS (SEGMENT A)")
    print("=" * 70)

    if not SERPER_API_KEY:
        print("Error: SERPER_API_KEY not set")
        return

    conn = await asyncpg.connect(DATABASE_URL)

    # Get unique winning companies not already in outreach_leads
    companies = await conn.fetch("""
        SELECT DISTINCT company_name,
               COUNT(*) as bid_count,
               SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as win_count,
               MAX(bid_amount_mkd) as max_bid
        FROM tender_bidders
        WHERE company_name IS NOT NULL
          AND LENGTH(company_name) > 10
          AND company_name NOT LIKE '%-%'
          AND company_name NOT IN (
              SELECT DISTINCT company_name
              FROM outreach_leads
              WHERE company_name IS NOT NULL
          )
        GROUP BY company_name
        ORDER BY win_count DESC, bid_count DESC
    """)

    print(f"\nFound {len(companies)} companies to enrich")
    print(f"Starting enrichment...\n")

    enriched = 0
    searched = 0
    start_time = datetime.now()

    async with aiohttp.ClientSession() as session:
        for i, company in enumerate(companies, 1):
            result = await enrich_company(session, company['company_name'])
            searched += 1

            if result['email']:
                # Calculate quality score based on wins
                base_score = 85  # High base score for tender participants
                win_bonus = min(10, company['win_count'] * 2)
                quality = min(100, base_score + win_bonus)

                await conn.execute("""
                    INSERT INTO outreach_leads (
                        email, company_name, segment, source, quality_score,
                        company_domain, country, raw_data
                    ) VALUES ($1, $2, 'A', 'tender_bidder', $3, $4, 'North Macedonia', $5)
                    ON CONFLICT (email) DO UPDATE SET
                        segment = CASE WHEN outreach_leads.segment > 'A' THEN 'A' ELSE outreach_leads.segment END,
                        quality_score = GREATEST(outreach_leads.quality_score, EXCLUDED.quality_score),
                        updated_at = NOW()
                """,
                    result['email'],
                    company['company_name'],
                    quality,
                    result['domain'],
                    {'bids': company['bid_count'], 'wins': company['win_count'], 'max_bid': float(company['max_bid']) if company['max_bid'] else None}
                )

                enriched += 1
                if enriched <= 30 or enriched % 50 == 0:
                    print(f"  ✓ [{i}/{len(companies)}] {company['company_name'][:50]}... -> {result['email']} ({result['method']})")

            if i % 50 == 0:
                rate = enriched / searched * 100 if searched > 0 else 0
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = searched / elapsed * 60 if elapsed > 0 else 0
                print(f"\n  Progress: {searched}/{len(companies)} | {enriched} emails ({rate:.1f}%) | {speed:.0f}/min\n")

            await asyncio.sleep(0.4)

    # Final stats
    total_outreach = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")
    segment_a = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads WHERE segment = 'A'")

    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Searched: {searched}")
    print(f"Emails found: {enriched} ({enriched/searched*100:.1f}% hit rate)")
    print(f"\nSegment A leads: {segment_a}")
    print(f"Total outreach leads: {total_outreach}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
