"""
Enrich mk_companies with data from Brave Search API.

Single-query strategy per company:
  Search Cyrillic name broadly → gets CompanyWall results (EDB, NACE, revenue)
  AND other sites (email, phone) all in one API call.

Uses Latin-to-Cyrillic conversion since our DB has Latin names from URL slugs
but Brave has indexed the Cyrillic versions.

Usage:
    # Enrich up to 100 companies (test)
    python3 brave_enrich.py --limit 100

    # Enrich all unenriched companies
    python3 brave_enrich.py

    # Dry run (don't write to DB)
    python3 brave_enrich.py --limit 10 --dry-run

    # Only target companies missing emails
    python3 brave_enrich.py --emails-only --limit 500
"""
import asyncio
import json
import os
import re
import sys
import argparse
import logging
from urllib.parse import quote

import asyncpg
import httpx
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

BRAVE_API_KEY = os.getenv('BRAVE_API_KEY', 'BSAcPXveYuCRHlJB8X16DQoY0Gr51wT')
BRAVE_URL = 'https://api.search.brave.com/res/v1/web/search'
DATABASE_URL = os.getenv('DATABASE_URL', '')

# Rate limit: ~1 req/sec even on paid plan
RATE_LIMIT_DELAY = 1.2

# Latin to Macedonian Cyrillic mapping
MULTI_CHAR = {
    'dzh': 'џ', 'gj': 'ѓ', 'kj': 'ќ', 'lj': 'љ', 'nj': 'њ',
    'dz': 'ѕ', 'zh': 'ж', 'ch': 'ч', 'sh': 'ш',
}
SINGLE_CHAR = {
    'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е',
    'z': 'з', 'i': 'и', 'j': 'ј', 'k': 'к', 'l': 'л', 'm': 'м',
    'n': 'н', 'o': 'о', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т',
    'u': 'у', 'f': 'ф', 'h': 'х', 'c': 'ц',
}


def latin_to_cyrillic(text):
    """Convert Latin transliteration to Macedonian Cyrillic."""
    result = text.lower()
    for lat, cyr in sorted(MULTI_CHAR.items(), key=lambda x: -len(x[0])):
        result = result.replace(lat, cyr)
    for lat, cyr in SINGLE_CHAR.items():
        result = result.replace(lat, cyr)
    return result


def extract_company_core_name(name):
    """Extract core company name, removing legal form suffixes and common words."""
    n = name.strip()
    # Remove common legal forms
    for form in ['DOOEL', 'DOO', 'AD', 'TP', 'JP', 'DPTU', 'DPTSTU', 'DTU',
                 'UVOZ', 'IZVOZ', 'Uvoz', 'Izvoz', 'Eksport', 'Import',
                 'Dooel', 'Doo', 'Ad', 'Tp', 'Jp']:
        n = re.sub(rf'\b{form}\b', '', n, flags=re.IGNORECASE)
    # Remove year suffixes
    n = re.sub(r'\b\d{4}\b', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def parse_snippet(description, url=''):
    """Extract structured data from a Brave search snippet."""
    if not description:
        return {}

    # Remove HTML tags
    desc = re.sub(r'<[^>]+>', '', description)
    result = {}

    # EDB (tax ID: 13 digits typically, preceded by ЕДБ)
    m = re.search(r'ЕДБ[:\s]*(\d{10,15})', desc)
    if m:
        result['edb'] = m.group(1)

    # EMBS (registration number: 5-8 digits)
    m = re.search(r'ЕМБС[:\s]*(\d{5,8})', desc)
    if m:
        result['embs'] = m.group(1)

    # Email - search across the full snippet
    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', desc)
    for email in emails:
        email = email.rstrip('.')
        # Skip junk emails
        if any(x in email.lower() for x in [
            'companywall', 'google', 'example', 'sentry', 'webpack',
            'noreply', 'no-reply', 'test@', 'admin@localhost'
        ]):
            continue
        result['email'] = email
        break

    # Phone - must NOT be inside an EDB number
    # Match Macedonian phone formats specifically
    m = re.search(r'(?<!\d)(\+389[\s-]?\d{1,2}[\s-]?\d{3}[\s-]?\d{2,4})(?!\d)', desc)
    if not m:
        # Try 0XX format but not inside longer number sequences
        m = re.search(r'(?<!\d)(0[2-9]\d[\s-]?\d{3}[\s-]?\d{2,4})(?!\d)', desc)
    if m:
        result['phone'] = m.group(1).strip()

    # Income/Revenue
    m = re.search(r'Income\s*([\d.,]+)', desc)
    if m:
        try:
            result['revenue'] = float(m.group(1).replace('.', '').replace(',', '.'))
        except (ValueError, TypeError):
            pass

    # Category (NACE description)
    m = re.search(r'Category\s+(.+?)(?:,\s*Income|,\s*$|\s*$)', desc)
    if m:
        result['nace_description'] = m.group(1).strip()[:500]

    # Full official name (usually the first part before ", ЕДБ")
    m = re.search(r'^(.+?)(?:,\s*ЕДБ|$)', desc)
    if m:
        name = m.group(1).strip()
        if 5 < len(name) < 200:
            result['full_name'] = name

    return result


async def search_brave(client, query, count=10):
    """Search Brave API and return results."""
    try:
        resp = await client.get(
            BRAVE_URL,
            params={'q': query, 'count': count},
            headers={
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip',
                'X-Subscription-Token': BRAVE_API_KEY,
            },
            timeout=15.0,
        )
        if resp.status_code == 429:
            logger.warning("Rate limited! Waiting 30s...")
            await asyncio.sleep(30)
            return []
        if resp.status_code != 200:
            logger.warning(f"Brave API error: {resp.status_code}")
            return []

        data = resp.json()
        return data.get('web', {}).get('results', [])
    except Exception as e:
        logger.error(f"Brave API error: {e}")
        return []


async def get_companies_to_enrich(pool, limit, emails_only=False):
    """Get companies that need enrichment."""
    async with pool.acquire() as conn:
        if emails_only:
            # Companies with CompanyWall data but no email
            rows = await conn.fetch("""
                SELECT company_id, name, companywall_id, source_url, city_mk
                FROM mk_companies
                WHERE name IS NOT NULL
                  AND email IS NULL
                  AND LENGTH(name) > 3
                ORDER BY company_id
                LIMIT $1
            """, limit)
        else:
            # Companies with companywall_id but no EDB
            rows = await conn.fetch("""
                SELECT company_id, name, companywall_id, source_url, city_mk
                FROM mk_companies
                WHERE companywall_id IS NOT NULL
                  AND edb IS NULL
                  AND name IS NOT NULL
                ORDER BY company_id
                LIMIT $1
            """, limit)
        return rows


async def update_company(pool, company_id, data):
    """Update company with enriched data."""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE mk_companies SET
                edb = COALESCE($2, edb),
                embs = COALESCE($3, embs),
                email = COALESCE($4, email),
                phone = COALESCE($5, phone),
                revenue = COALESCE($6, revenue),
                nace_description = COALESCE($7, nace_description),
                updated_at = NOW()
            WHERE company_id = $1
        """,
            company_id,
            data.get('edb'),
            data.get('embs'),
            data.get('email'),
            data.get('phone'),
            data.get('revenue'),
            data.get('nace_description'),
        )


async def enrich_single_query(client, company):
    """Single query per company: broad search to find EDB, email, phone all at once.

    Strategy: Search for the Cyrillic company name without site: restriction.
    This returns both CompanyWall results (for EDB/NACE) and other sites (for email/phone).
    """
    name = company['name']
    core_name = extract_company_core_name(name)
    cyrillic_name = latin_to_cyrillic(core_name)
    city = company['city_mk'] or ''
    city_cyr = latin_to_cyrillic(city) if city else ''

    # Single broad query - Cyrillic name + city for disambiguation
    # No site: restriction so we get CompanyWall + other sources
    query = f'"{cyrillic_name}"'
    if city_cyr and len(city_cyr) > 2:
        query += f' {city_cyr}'

    results = await search_brave(client, query, count=10)

    merged = {}
    email = None
    phone = None

    for r in results:
        url = r.get('url', '')
        desc = r.get('description', '')

        # From CompanyWall results: extract EDB, NACE, revenue
        if 'companywall.com.mk' in url:
            cw_data = parse_snippet(desc, url)
            if cw_data.get('edb') and not merged.get('edb'):
                merged['edb'] = cw_data['edb']
            if cw_data.get('embs') and not merged.get('embs'):
                merged['embs'] = cw_data['embs']
            if cw_data.get('revenue') and not merged.get('revenue'):
                merged['revenue'] = cw_data['revenue']
            if cw_data.get('nace_description') and not merged.get('nace_description'):
                merged['nace_description'] = cw_data['nace_description']

        # From ALL results: extract email and phone
        clean_desc = re.sub(r'<[^>]+>', '', desc)

        if not email:
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', clean_desc)
            for e in emails:
                e = e.rstrip('.')
                if any(x in e.lower() for x in [
                    'companywall', 'google', 'example', 'sentry', 'webpack',
                    'noreply', 'no-reply', 'test@', 'localhost', 'wixpress',
                    'sitebuilder', 'squarespace', 'godaddy',
                ]):
                    continue
                email = e
                break

        if not phone:
            m = re.search(r'(?<!\d)(\+389[\s-]?\d{1,2}[\s-]?\d{3}[\s-]?\d{2,4})(?!\d)', clean_desc)
            if not m:
                m = re.search(r'(?<!\d)(0[2-9]\d[\s-]?\d{3}[\s-]?\d{2,4})(?!\d)', clean_desc)
            if m:
                phone = m.group(1).strip()

    if email:
        merged['email'] = email
    if phone:
        merged['phone'] = phone

    return merged if merged else {}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=100000)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--emails-only', action='store_true',
                        help='Only search for emails (skip CompanyWall EDB pass)')
    args = parser.parse_args()

    if not DATABASE_URL:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    db_url = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)

    companies = await get_companies_to_enrich(pool, args.limit, args.emails_only)
    logger.info(f"Found {len(companies)} companies to enrich")

    stats = {'queries': 0, 'enriched': 0, 'with_email': 0, 'with_edb': 0, 'with_phone': 0}

    async with httpx.AsyncClient() as client:
        for i, company in enumerate(companies):
            name = company['name']

            # Single query per company - broad search finds both EDB and email
            merged_data = await enrich_single_query(client, company)
            stats['queries'] += 1
            await asyncio.sleep(RATE_LIMIT_DELAY)

            if merged_data:
                if merged_data.get('email'):
                    stats['with_email'] += 1
                if merged_data.get('edb'):
                    stats['with_edb'] += 1
                if merged_data.get('phone'):
                    stats['with_phone'] += 1

                if not args.dry_run:
                    await update_company(pool, company['company_id'], merged_data)

                stats['enriched'] += 1
                logger.info(
                    f"[{i+1}/{len(companies)}] {name[:40]} | "
                    f"EDB:{merged_data.get('edb','-')} | "
                    f"Email:{merged_data.get('email','-')} | "
                    f"Phone:{merged_data.get('phone','-')}"
                )
            else:
                logger.debug(f"[{i+1}] No data for {name[:40]}")

            # Progress report every 50
            if (i + 1) % 50 == 0:
                logger.info(
                    f"Progress: {i+1}/{len(companies)} | "
                    f"Queries: {stats['queries']} | "
                    f"Enriched: {stats['enriched']} | "
                    f"Emails: {stats['with_email']} | "
                    f"EDBs: {stats['with_edb']} | "
                    f"Phones: {stats['with_phone']}"
                )

    logger.info(f"Done! {json.dumps(stats)}")
    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
