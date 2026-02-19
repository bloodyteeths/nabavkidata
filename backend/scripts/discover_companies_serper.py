#!/usr/bin/env python3
"""
Use Serper API to DISCOVER new Macedonian companies by industry.
This finds company names we don't have yet, then we can enrich them.

Usage:
    python3 scripts/discover_companies_serper.py --dry-run
    python3 scripts/discover_companies_serper.py --limit=100
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import json
import re
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "3f204d308413293294eba57d56ff6e9958762197")

# Industry search queries - each will find new companies
INDUSTRY_QUERIES = [
    # IT & Technology
    "ИТ компании Македонија контакт",
    "софтвер компании Скопје",
    "веб дизајн агенција Македонија",
    "дигитален маркетинг агенција Скопје",

    # Construction
    "градежни компании Скопје",
    "градежништво фирми Битола",
    "архитектонско биро Македонија",

    # Manufacturing
    "производство фирми Скопје",
    "фабрика Македонија контакт",
    "индустрија компании Велес",

    # Trade & Retail
    "трговија на големо Скопје",
    "дистрибутер Македонија",
    "увоз извоз компании",

    # Healthcare
    "приватна здравствена установа Скопје",
    "стоматолошка ординација Македонија",
    "медицински центар контакт",

    # Finance
    "консалтинг компанија Скопје",
    "сметководствено биро Македонија",
    "осигурителна компанија Скопје",

    # Food & Agriculture
    "прехранбена индустрија Македонија",
    "земјоделска компанија",
    "ресторани кетеринг Скопје",

    # Transportation
    "транспортни компании Македонија",
    "логистика фирми Скопје",
    "шпедиција Македонија",

    # Services
    "маркетинг агенција Скопје",
    "правна канцеларија Скопје",
    "хотели Охрид контакт",
    "туристичка агенција Македонија",

    # Energy
    "енергетика компанија Македонија",
    "соларни панели инсталација Скопје",

    # Specific cities
    "компании Куманово",
    "фирми Прилеп",
    "бизниси Штип",
    "претпријатија Тетово",
]


def extract_company_info(result: dict) -> list:
    """Extract company names and emails from Serper results"""
    companies = []

    if not result:
        return companies

    for item in result.get('organic', []):
        title = item.get('title', '')
        snippet = item.get('snippet', '')
        link = item.get('link', '')

        # Extract potential company names from titles
        # Look for patterns like "КОМПАНИЈА - услуги" or "Друштво за..."
        company_patterns = [
            r'([А-ЯA-Z][А-Яа-яA-Za-z\s\-\.]{5,40}?)(?:\s*[-–|]\s|\s*\||$)',
            r'(Друштво[^,]{10,60})',
            r'([А-ЯA-Z][А-Яа-яA-Za-z]{3,20}\s+ДООЕЛ)',
            r'([А-ЯA-Z][А-Яа-яA-Za-z]{3,20}\s+ДОО)',
        ]

        for pattern in company_patterns:
            matches = re.findall(pattern, title)
            for match in matches:
                name = match.strip()
                if len(name) > 10 and not any(x in name.lower() for x in ['google', 'facebook', 'linkedin', 'youtube']):
                    # Extract email if available
                    emails = re.findall(r'[\w\.\-]+@[\w\.\-]+\.\w+', snippet)
                    valid_emails = [e.lower() for e in emails if not any(x in e.lower() for x in ['example.com', 'gmail.com', 'yahoo.com'])]

                    companies.append({
                        'name': name,
                        'email': valid_emails[0] if valid_emails else None,
                        'website': link if '.mk' in link else None,
                        'source_query': result.get('searchParameters', {}).get('q', '')
                    })

    # Also check knowledge graph
    kg = result.get('knowledgeGraph', {})
    if kg.get('title'):
        companies.append({
            'name': kg['title'],
            'email': kg.get('email'),
            'website': kg.get('website'),
            'source_query': result.get('searchParameters', {}).get('q', '')
        })

    return companies


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
        "num": 20  # More results
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 403:
                print(f"    [RATE LIMITED]")
                return None
            else:
                return None
    except Exception as e:
        return None


async def main():
    print("=" * 70)
    print("DISCOVER NEW COMPANIES VIA SERPER")
    print("=" * 70)

    dry_run = '--dry-run' in sys.argv

    limit = len(INDUSTRY_QUERIES)
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    conn = await asyncpg.connect(DATABASE_URL)

    # Get existing company names for deduplication
    existing = await conn.fetch("SELECT LOWER(TRIM(company_name)) as name FROM suppliers")
    existing_names = set(r['name'] for r in existing)
    print(f"\nExisting suppliers: {len(existing_names)}")

    all_new_companies = []

    async with aiohttp.ClientSession() as session:
        for i, query in enumerate(INDUSTRY_QUERIES[:limit]):
            print(f"\n[{i+1}/{min(limit, len(INDUSTRY_QUERIES))}] Searching: {query[:50]}...")

            result = await search_serper(session, query)
            if result:
                companies = extract_company_info(result)

                # Filter out existing
                new_companies = []
                for c in companies:
                    if c['name'].lower().strip() not in existing_names:
                        new_companies.append(c)
                        existing_names.add(c['name'].lower().strip())  # Prevent duplicates

                all_new_companies.extend(new_companies)
                print(f"    Found {len(companies)} companies, {len(new_companies)} are NEW")

                for c in new_companies[:3]:
                    email_str = f" -> {c['email']}" if c['email'] else ""
                    print(f"      - {c['name'][:45]}{email_str}")

            await asyncio.sleep(1)  # Rate limit

    print(f"\n" + "=" * 70)
    print(f"DISCOVERY COMPLETE")
    print(f"=" * 70)
    print(f"Total NEW companies found: {len(all_new_companies)}")
    print(f"With email: {len([c for c in all_new_companies if c['email']])}")

    if dry_run:
        print("\n[DRY RUN - No changes made]")
        await conn.close()
        return

    # Insert new companies
    inserted = 0
    for company in all_new_companies:
        try:
            supplier_id = await conn.fetchval("""
                INSERT INTO suppliers (company_name, website, source, created_at, updated_at)
                VALUES ($1, $2, 'serper_discovery', NOW(), NOW())
                ON CONFLICT (company_name) DO NOTHING
                RETURNING supplier_id
            """, company['name'], company.get('website'))

            if supplier_id:
                inserted += 1

                # Add email if available
                if company.get('email'):
                    await conn.execute("""
                        INSERT INTO supplier_contacts
                        (supplier_id, email, email_type, source_domain, confidence_score, status, created_at)
                        VALUES ($1, $2, 'info', 'serper_discovery', 70, 'new', NOW())
                        ON CONFLICT (supplier_id, email) DO NOTHING
                    """, supplier_id, company['email'])
        except Exception as e:
            pass

    print(f"\nInserted {inserted} new companies to database")

    # Final stats
    total = await conn.fetchval("SELECT COUNT(*) FROM suppliers")
    print(f"Total suppliers now: {total}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
