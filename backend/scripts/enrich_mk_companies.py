#!/usr/bin/env python3
"""
Enrich mk_companies table (46,994 companies) with emails using Serper.
This is the main path to reaching 50K leads for Macedonia.

Usage:
    SERPER_API_KEY=xxx python3 scripts/enrich_mk_companies.py

Options:
    --batch-size N    Process N companies per run (default: 1000)
    --skip-attempted  Skip companies that were already searched
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


async def search_company_email(session, company_name: str, city: str = None) -> dict:
    """Search for company email using Serper Google Search API"""

    # Build search query - company name + "email" + optional city
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
            json={"q": query, "num": 10}
        ) as resp:
            if resp.status != 200:
                return {"error": f"HTTP {resp.status}"}

            data = await resp.json()

            # Extract all text from results
            text_parts = []

            # Organic results
            for result in data.get("organic", []):
                text_parts.append(result.get("title", ""))
                text_parts.append(result.get("snippet", ""))

            # Knowledge graph
            kg = data.get("knowledgeGraph", {})
            if kg:
                text_parts.append(kg.get("description", ""))
                for attr in kg.get("attributes", {}).values():
                    text_parts.append(str(attr))

            # Answer box
            if data.get("answerBox"):
                text_parts.append(data["answerBox"].get("answer", ""))
                text_parts.append(data["answerBox"].get("snippet", ""))

            all_text = " ".join(text_parts).lower()

            # Find emails
            emails = EMAIL_PATTERN.findall(all_text)

            # Filter valid emails
            valid_emails = []
            for email in emails:
                email = email.lower()
                # Skip generic/invalid emails
                bad_patterns = ['example', 'test', 'noreply', 'sentry', '.png', '.jpg', 'wixpress',
                               'sample@sample', 'email@email', 'user@domain', 'name@company',
                               'yourname@', 'youremail@', 'info@domain', 'info@example',
                               'jane_doe@', 'john_doe@', 'first@last', 'firstname@']
                if any(x in email for x in bad_patterns):
                    continue
                # Prefer .mk domains or info@ emails
                valid_emails.append(email)

            if valid_emails:
                # Prioritize: info@, contact@, .mk domains
                mk_emails = [e for e in valid_emails if '.mk' in e]
                info_emails = [e for e in valid_emails if e.startswith(('info@', 'contact@', 'office@'))]

                best_email = mk_emails[0] if mk_emails else (info_emails[0] if info_emails else valid_emails[0])

                return {
                    "email": best_email,
                    "source": "serper_search",
                    "all_emails": list(set(valid_emails))[:5]
                }

            return {"email": None, "source": "serper_search"}

    except Exception as e:
        return {"error": str(e)}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', type=int, default=1000, help='Companies per run')
    parser.add_argument('--skip-attempted', action='store_true', help='Skip already searched')
    args = parser.parse_args()

    if not SERPER_API_KEY:
        print("ERROR: Set SERPER_API_KEY environment variable")
        sys.exit(1)

    print("=" * 70)
    print("ENRICH MK_COMPANIES WITH EMAILS")
    print("=" * 70)
    print(f"Batch size: {args.batch_size}")
    print(f"Skip attempted: {args.skip_attempted}")

    conn = await asyncpg.connect(DATABASE_URL)

    # Get companies to enrich
    if args.skip_attempted:
        query = """
            SELECT company_id, name, city_en, phone, category_en
            FROM mk_companies
            WHERE email IS NULL
            AND (email_search_attempted IS NULL OR email_search_attempted = false)
            LIMIT $1
        """
    else:
        query = """
            SELECT company_id, name, city_en, phone, category_en
            FROM mk_companies
            WHERE email IS NULL
            LIMIT $1
        """

    companies = await conn.fetch(query, args.batch_size)
    print(f"\nFound {len(companies)} companies to enrich")

    if not companies:
        print("No companies to process!")
        await conn.close()
        return

    # Stats
    total_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(email) as with_email,
            COUNT(CASE WHEN email_search_attempted THEN 1 END) as searched
        FROM mk_companies
    """)
    print(f"Database stats: {total_stats['total']} total, {total_stats['with_email']} with email, {total_stats['searched']} searched")

    print("\nStarting enrichment...\n")

    enriched = 0
    errors = 0
    start_time = datetime.now()

    async with aiohttp.ClientSession() as session:
        for i, company in enumerate(companies, 1):
            company_id = company['company_id']
            company_name = company['name']
            city = company['city_en']

            result = await search_company_email(session, company_name, city)

            if "error" in result:
                errors += 1
                if "429" in str(result["error"]) or "quota" in str(result["error"]).lower():
                    print(f"\n  API quota exhausted at {i}/{len(companies)}")
                    break
            elif result.get("email"):
                enriched += 1
                email = result["email"]

                # Update mk_companies
                await conn.execute("""
                    UPDATE mk_companies
                    SET email = $1,
                        email_source = $2,
                        email_found_at = NOW(),
                        email_search_attempted = true,
                        email_search_at = NOW()
                    WHERE company_id = $3
                """, email, result["source"], company_id)

                # Add to outreach_leads (Segment C - Registry companies)
                await conn.execute("""
                    INSERT INTO outreach_leads (
                        email, company_name, segment, source, quality_score,
                        country, phone, raw_data
                    ) VALUES ($1, $2, 'C', 'mk_companies', 60, 'North Macedonia', $3, $4)
                    ON CONFLICT (email) DO NOTHING
                """,
                    email,
                    company_name,
                    company['phone'],
                    json.dumps({
                        'source': 'mk_companies',
                        'city': city,
                        'category': company['category_en'],
                        'all_emails': result.get('all_emails', [])
                    })
                )

                if enriched <= 20 or enriched % 50 == 0:
                    print(f"  ✓ [{i}/{len(companies)}] {company_name[:35]}... -> {email}")
            else:
                # Mark as searched but no email found
                await conn.execute("""
                    UPDATE mk_companies
                    SET email_search_attempted = true,
                        email_search_at = NOW()
                    WHERE company_id = $1
                """, company_id)

            # Progress update
            if i % 100 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = i / elapsed * 60 if elapsed > 0 else 0
                hit_rate = enriched / i * 100 if i > 0 else 0
                print(f"\n  Progress: {i}/{len(companies)} | {enriched} emails ({hit_rate:.1f}%) | {rate:.0f}/min\n")

            # Rate limit - 50 requests/min for Serper free tier
            await asyncio.sleep(1.2)

    # Final stats
    final_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(email) as with_email,
            COUNT(CASE WHEN email_search_attempted THEN 1 END) as searched
        FROM mk_companies
    """)

    total_leads = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")

    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Processed: {len(companies)}")
    print(f"Emails found: {enriched}")
    print(f"Hit rate: {enriched/len(companies)*100:.1f}%")
    print(f"Errors: {errors}")
    print(f"\nmk_companies: {final_stats['with_email']}/{final_stats['total']} with email ({final_stats['searched']} searched)")
    print(f"Total outreach leads: {total_leads}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
