#!/usr/bin/env python3
"""
PARALLEL enrichment of mk_companies - 10x faster!
Uses connection pool for concurrent DB operations.
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import json
import re
import argparse
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


async def search_company_email(session, semaphore, company_name: str, city: str = None) -> dict:
    """Search for company email using Serper Google Search API"""

    async with semaphore:
        query = f'"{company_name}" email'
        if city:
            query += f' {city}'
        query += ' Macedonia'

        try:
            async with session.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json"
                },
                json={"q": query, "num": 10},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 400:
                    text = await resp.text()
                    if "Not enough credits" in text:
                        return {"error": "NO_CREDITS"}
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}

                data = await resp.json()
                text_parts = []

                for result in data.get("organic", []):
                    text_parts.append(result.get("title", ""))
                    text_parts.append(result.get("snippet", ""))

                kg = data.get("knowledgeGraph", {})
                if kg:
                    text_parts.append(kg.get("description", ""))
                    for attr in kg.get("attributes", {}).values():
                        text_parts.append(str(attr))

                if data.get("answerBox"):
                    text_parts.append(data["answerBox"].get("answer", ""))
                    text_parts.append(data["answerBox"].get("snippet", ""))

                all_text = " ".join(text_parts).lower()
                emails = EMAIL_PATTERN.findall(all_text)

                valid_emails = []
                bad_patterns = ['example', 'test', 'noreply', 'sentry', '.png', '.jpg', 'wixpress',
                               'sample@sample', 'email@email', 'user@domain', 'name@company',
                               'yourname@', 'youremail@', 'info@domain', 'info@example',
                               'jane_doe@', 'john_doe@', 'first@last', 'firstname@']
                for email in emails:
                    email = email.lower()
                    if any(x in email for x in bad_patterns):
                        continue
                    valid_emails.append(email)

                if valid_emails:
                    mk_emails = [e for e in valid_emails if '.mk' in e]
                    info_emails = [e for e in valid_emails if e.startswith(('info@', 'contact@', 'office@'))]
                    best_email = mk_emails[0] if mk_emails else (info_emails[0] if info_emails else valid_emails[0])
                    return {"email": best_email, "source": "serper_search", "all_emails": list(set(valid_emails))[:5]}

                return {"email": None, "source": "serper_search"}

        except asyncio.TimeoutError:
            return {"error": "timeout"}
        except Exception as e:
            return {"error": str(e)}


async def process_company(session, semaphore, pool, company, stats, stats_lock):
    """Process a single company"""
    company_id = company['company_id']
    company_name = company['name']
    city = company['city_en']

    result = await search_company_email(session, semaphore, company_name, city)

    if result.get("error") == "NO_CREDITS":
        async with stats_lock:
            stats['no_credits'] = True
        return

    async with stats_lock:
        stats['processed'] += 1

    if "error" in result:
        async with stats_lock:
            stats['errors'] += 1
    elif result.get("email"):
        async with stats_lock:
            stats['enriched'] += 1
            enriched_count = stats['enriched']

        email = result["email"]

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE mk_companies
                SET email = $1, email_source = $2, email_found_at = NOW(),
                    email_search_attempted = true, email_search_at = NOW()
                WHERE company_id = $3
            """, email, result["source"], company_id)

            await conn.execute("""
                INSERT INTO outreach_leads (
                    email, company_name, segment, source, quality_score,
                    country, phone, raw_data
                ) VALUES ($1, $2, 'C', 'mk_companies', 60, 'North Macedonia', $3, $4)
                ON CONFLICT (email) DO NOTHING
            """, email, company_name, company['phone'],
                json.dumps({'source': 'mk_companies', 'city': city, 'category': company['category_en']}))

        if enriched_count <= 20 or enriched_count % 50 == 0:
            print(f"  ✓ {company_name[:35]}... -> {email}")
    else:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE mk_companies
                SET email_search_attempted = true, email_search_at = NOW()
                WHERE company_id = $1
            """, company_id)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', type=int, default=1000, help='Companies per run')
    parser.add_argument('--concurrency', type=int, default=10, help='Parallel requests')
    args = parser.parse_args()

    if not SERPER_API_KEY:
        print("ERROR: Set SERPER_API_KEY environment variable")
        sys.exit(1)

    print("=" * 70)
    print("PARALLEL ENRICH MK_COMPANIES")
    print("=" * 70)
    print(f"Batch size: {args.batch_size} | Concurrency: {args.concurrency}")

    # Create connection pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)

    async with pool.acquire() as conn:
        companies = await conn.fetch("""
            SELECT company_id, name, city_en, phone, category_en
            FROM mk_companies
            WHERE email IS NULL
            AND (email_search_attempted IS NULL OR email_search_attempted = false)
            LIMIT $1
        """, args.batch_size)

        print(f"Found {len(companies)} companies to enrich")

        if not companies:
            print("No companies to process!")
            await pool.close()
            return

        total_stats = await conn.fetchrow("""
            SELECT COUNT(*) as total, COUNT(email) as with_email,
                   COUNT(CASE WHEN email_search_attempted THEN 1 END) as searched
            FROM mk_companies
        """)
        print(f"DB: {total_stats['total']} total, {total_stats['with_email']} with email, {total_stats['searched']} searched")

    print(f"\nStarting parallel enrichment ({args.concurrency} concurrent)...\n")

    stats = {'processed': 0, 'enriched': 0, 'errors': 0, 'no_credits': False}
    stats_lock = asyncio.Lock()
    start_time = datetime.now()
    semaphore = asyncio.Semaphore(args.concurrency)

    connector = aiohttp.TCPConnector(limit=args.concurrency + 5)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Process in chunks for progress updates
        chunk_size = 100
        for i in range(0, len(companies), chunk_size):
            if stats['no_credits']:
                print("\n⚠️  API CREDITS EXHAUSTED!")
                break

            chunk = companies[i:i + chunk_size]
            tasks = [process_company(session, semaphore, pool, c, stats, stats_lock) for c in chunk]
            await asyncio.gather(*tasks)

            elapsed = (datetime.now() - start_time).total_seconds()
            rate = stats['processed'] / elapsed * 60 if elapsed > 0 else 0
            hit_rate = stats['enriched'] / stats['processed'] * 100 if stats['processed'] > 0 else 0
            print(f"  Progress: {stats['processed']}/{len(companies)} | {stats['enriched']} emails ({hit_rate:.1f}%) | {rate:.0f}/min")

            # Small delay between chunks to avoid rate limiting
            await asyncio.sleep(2)

    async with pool.acquire() as conn:
        final_stats = await conn.fetchrow("""
            SELECT COUNT(*) as total, COUNT(email) as with_email,
                   COUNT(CASE WHEN email_search_attempted THEN 1 END) as searched
            FROM mk_companies
        """)
        total_leads = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")

    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Processed: {stats['processed']}")
    print(f"Emails found: {stats['enriched']}")
    print(f"Hit rate: {stats['enriched']/stats['processed']*100:.1f}%" if stats['processed'] > 0 else "N/A")
    print(f"Errors: {stats['errors']}")
    print(f"\nmk_companies: {final_stats['with_email']}/{final_stats['total']} with email ({final_stats['searched']} searched)")
    print(f"Total outreach leads: {total_leads}")

    if stats['no_credits']:
        print("\n⚠️  STOPPED: API credits exhausted. Use new API key.")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
