"""
Match CompanyWall sitemap records (Latin names) with existing mk_companies (Cyrillic names).

Merges data: adds companywall_id/source_url to existing records that already have emails,
and adds email/phone to CW records that match existing records.

Usage:
    python3 match_companywall.py --dry-run    # Preview matches
    python3 match_companywall.py              # Apply merges
"""
import asyncio
import argparse
import logging
import os
import re
import sys

import asyncpg
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', '')

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


def normalize_name(name):
    """Normalize a company name for matching."""
    n = name.upper().strip()
    # Remove common legal form suffixes
    for form in ['ДООЕЛ', 'DOOEL', 'ДОО', 'DOO', 'АД', 'AD', 'ТП', 'TP', 'ЈП', 'JP',
                 'УВОЗ', 'ИЗВОЗ', 'UVOZ', 'IZVOZ', 'EKSPORT', 'IMPORT',
                 'ЕКСПОРТ', 'ИМПОРТ', 'ЗР', 'ZR', 'ЗК', 'ZK',
                 'ДТУ', 'DTU', 'ДПТУ', 'DPTU', 'ДПТСТУ', 'DPTSTU']:
        n = n.replace(form, '')
    # Remove extra spaces, dashes, special chars
    n = re.sub(r'[\s\-_.,;:\"\'()]+', ' ', n).strip()
    # Remove trailing numbers that might be year suffixes
    n = re.sub(r'\s+\d{4}$', '', n)
    return n


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=100000)
    args = parser.parse_args()

    if not DATABASE_URL:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    db_url = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)

    async with pool.acquire() as conn:
        # Get CW companies (Latin names, no email)
        cw_rows = await conn.fetch("""
            SELECT company_id, name, city_mk, companywall_id, source_url
            FROM mk_companies
            WHERE companywall_id IS NOT NULL
              AND email IS NULL
            LIMIT $1
        """, args.limit)

        # Get existing companies with emails (Cyrillic names)
        email_rows = await conn.fetch("""
            SELECT company_id, name, city_mk, email, phone, edb, embs
            FROM mk_companies
            WHERE email IS NOT NULL
              AND companywall_id IS NULL
        """)

    logger.info(f"CW companies (no email): {len(cw_rows)}")
    logger.info(f"Existing companies (with email): {len(email_rows)}")

    # Build lookup of existing companies by normalized Cyrillic name
    # Key: normalized_cyrillic_name -> list of records
    existing_by_name = {}
    for row in email_rows:
        norm = normalize_name(row['name'])
        if norm:
            existing_by_name.setdefault(norm, []).append(row)

    matches = []
    for cw in cw_rows:
        # Convert CW Latin name to Cyrillic and normalize
        cyrillic_name = latin_to_cyrillic(cw['name'])
        norm_cw = normalize_name(cyrillic_name)
        if not norm_cw:
            continue

        # Try exact normalized match
        candidates = existing_by_name.get(norm_cw, [])

        # Also try without numbers (some have year suffixes)
        if not candidates:
            norm_no_num = re.sub(r'\s*\d+\s*', ' ', norm_cw).strip()
            if norm_no_num != norm_cw:
                candidates = existing_by_name.get(norm_no_num, [])

        if not candidates:
            continue

        # If multiple candidates, prefer same city
        cw_city = (cw['city_mk'] or '').upper()
        best = None
        for c in candidates:
            c_city = (c['city_mk'] or '').upper()
            # Convert CW city (Latin) to Cyrillic for comparison
            cw_city_cyr = latin_to_cyrillic(cw_city).upper() if cw_city else ''
            if c_city and cw_city_cyr and (c_city in cw_city_cyr or cw_city_cyr in c_city):
                best = c
                break
        if not best:
            best = candidates[0]

        matches.append({
            'cw_id': cw['company_id'],
            'cw_name': cw['name'],
            'cw_companywall_id': cw['companywall_id'],
            'cw_source_url': cw['source_url'],
            'existing_id': best['company_id'],
            'existing_name': best['name'],
            'existing_email': best['email'],
            'existing_phone': best.get('phone'),
            'existing_edb': best.get('edb'),
        })

    logger.info(f"Found {len(matches)} matches")

    if matches:
        # Show some examples
        for m in matches[:20]:
            logger.info(
                f"  {m['cw_name'][:30]:30s} <-> {m['existing_name'][:30]:30s} | "
                f"Email: {m['existing_email']}"
            )

    if args.dry_run:
        logger.info("Dry run - not writing to DB")
        return

    # Apply merges: update existing records with CW data, delete CW duplicates
    updated = 0
    deleted = 0
    async with pool.acquire() as conn:
        for m in matches:
            # Add companywall_id + source_url to existing record
            await conn.execute("""
                UPDATE mk_companies SET
                    companywall_id = $2,
                    source_url = $3,
                    updated_at = NOW()
                WHERE company_id = $1
                  AND companywall_id IS NULL
            """, m['existing_id'], m['cw_companywall_id'], m['cw_source_url'])
            updated += 1

            # Delete the CW duplicate record
            await conn.execute("""
                DELETE FROM mk_companies WHERE company_id = $1
            """, m['cw_id'])
            deleted += 1

    logger.info(f"Updated {updated} existing records with CW data")
    logger.info(f"Deleted {deleted} duplicate CW records")

    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
