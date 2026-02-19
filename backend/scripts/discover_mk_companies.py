#!/usr/bin/env python3
"""
Discover Macedonian companies using Serper search.
Searches by industry, city, and common company types to find new leads.

Usage:
    SERPER_API_KEY=xxx python3 scripts/discover_mk_companies.py --limit=1000
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
                'mail.com', 'aol.com', 'icloud.com', 'live.com', 'msn.com', 'protonmail.com'}

# Industries relevant for government tenders
INDUSTRIES = [
    "градежништво",          # Construction
    "ИТ компанија",          # IT company
    "софтвер",               # Software
    "медицинска опрема",     # Medical equipment
    "канцелариски материјал", # Office supplies
    "превоз транспорт",      # Transport
    "безбедност обезбедување", # Security
    "чистење хигиена",       # Cleaning
    "печатење графички",     # Printing
    "храна угостителство",   # Food/catering
    "телекомуникации",       # Telecom
    "инженеринг",            # Engineering
    "архитектура",           # Architecture
    "консалтинг",            # Consulting
    "маркетинг агенција",    # Marketing agency
    "правни услуги адвокат", # Legal services
    "сметководство",         # Accounting
    "осигурување",           # Insurance
    "увоз извоз",            # Import/export
    "производство",          # Manufacturing
]

# Cities in Macedonia
CITIES = [
    "Скопје", "Битола", "Куманово", "Прилеп", "Тетово",
    "Охрид", "Велес", "Штип", "Струмица", "Гостивар",
    "Кавадарци", "Кочани", "Струга", "Гевгелија", "Кичево"
]

# Company type searches
COMPANY_TYPES = [
    "ДООЕЛ Македонија",      # Single-member LLC
    "ДОО Скопје",            # LLC Skopje
    "компанија mk",          # Company mk
    "фирма Македонија",      # Firm Macedonia
]


def extract_domain(email):
    if '@' in email:
        return email.split('@')[1].lower()
    return None


async def search_serper(session, query: str) -> dict:
    """Search Serper and extract company info with emails"""
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "num": 20, "gl": "mk"}  # Macedonia locale

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status != 200:
                return {'results': [], 'emails': []}

            data = await resp.json()
            results = []
            all_emails = []

            for item in data.get('organic', []):
                title = item.get('title', '')
                snippet = item.get('snippet', '')
                link = item.get('link', '')

                # Extract emails from snippet
                emails = EMAIL_PATTERN.findall(snippet.lower())
                valid_emails = [e for e in emails if extract_domain(e) not in SKIP_DOMAINS]

                if valid_emails:
                    all_emails.extend(valid_emails)

                # Try to identify company name from title
                company_name = None
                if any(x in title.lower() for x in ['дооел', 'доо', 'ltd', 'llc', 'company']):
                    company_name = title.split('|')[0].split('-')[0].strip()
                elif '.mk' in link or '.com.mk' in link:
                    company_name = title.split('|')[0].split('-')[0].strip()

                if company_name and len(company_name) > 3:
                    domain = None
                    if link:
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(link)
                            domain = parsed.netloc.replace('www.', '')
                        except:
                            pass

                    results.append({
                        'company_name': company_name[:200],
                        'domain': domain,
                        'url': link,
                        'emails': valid_emails
                    })

            return {'results': results, 'emails': list(set(all_emails))}
    except Exception as e:
        return {'results': [], 'emails': []}


async def main():
    print("=" * 70)
    print("DISCOVER MACEDONIAN COMPANIES VIA SERPER")
    print("=" * 70)

    if not SERPER_API_KEY:
        print("Error: SERPER_API_KEY not set")
        return

    limit = 1000
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    conn = await asyncpg.connect(DATABASE_URL)

    # Create discovery table if not exists
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS discovered_companies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_name VARCHAR(500),
            domain VARCHAR(255),
            email VARCHAR(255),
            source_query TEXT,
            source_url TEXT,
            processed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_discovered_email ON discovered_companies(email);
        CREATE INDEX IF NOT EXISTS idx_discovered_domain ON discovered_companies(domain);
    """)

    print(f"\nSearching for companies (limit: {limit} queries)...")

    queries_done = 0
    companies_found = 0
    emails_found = 0
    start_time = datetime.now()

    # Generate search queries
    search_queries = []

    # Industry + city combinations
    for industry in INDUSTRIES:
        for city in CITIES[:5]:  # Top 5 cities
            search_queries.append(f"{industry} {city} email контакт")

    # Company types
    for ctype in COMPANY_TYPES:
        search_queries.append(f"{ctype} email contact")

    # Industry-only searches
    for industry in INDUSTRIES:
        search_queries.append(f"{industry} Македонија email компанија")

    print(f"Generated {len(search_queries)} search queries")

    async with aiohttp.ClientSession() as session:
        for query in search_queries[:limit]:
            data = await search_serper(session, query)
            queries_done += 1

            # Process results
            for result in data['results']:
                if result.get('emails'):
                    for email in result['emails']:
                        try:
                            await conn.execute("""
                                INSERT INTO discovered_companies
                                    (company_name, domain, email, source_query, source_url)
                                VALUES ($1, $2, $3, $4, $5)
                                ON CONFLICT DO NOTHING
                            """,
                                result['company_name'],
                                result['domain'],
                                email,
                                query,
                                result.get('url')
                            )
                            emails_found += 1
                        except:
                            pass

                    companies_found += 1

            # Progress
            if queries_done % 20 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"  Progress: {queries_done}/{min(limit, len(search_queries))} queries | "
                      f"{companies_found} companies | {emails_found} emails | "
                      f"{queries_done/elapsed*60:.0f} queries/min")

            await asyncio.sleep(0.5)

    # Import to outreach_leads (Segment C)
    print("\nImporting discovered companies to outreach_leads...")

    imported = await conn.execute("""
        INSERT INTO outreach_leads (email, company_name, company_domain, segment, source, quality_score, country)
        SELECT DISTINCT ON (email)
            email,
            company_name,
            domain,
            'C',
            'serper_discovery',
            40,
            'North Macedonia'
        FROM discovered_companies
        WHERE email IS NOT NULL
          AND email NOT IN (SELECT email FROM outreach_leads)
        ON CONFLICT (email) DO NOTHING
    """)

    # Stats
    total_discovered = await conn.fetchval("SELECT COUNT(*) FROM discovered_companies")
    total_outreach = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")

    print("\n" + "=" * 70)
    print("DISCOVERY COMPLETE")
    print("=" * 70)
    print(f"Queries executed: {queries_done}")
    print(f"Companies found: {companies_found}")
    print(f"Emails found: {emails_found}")
    print(f"\nTotal discovered companies: {total_discovered}")
    print(f"Total outreach leads: {total_outreach}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
