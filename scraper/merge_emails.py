"""
Merge emails from original mk_companies records (Cyrillic names)
to CompanyWall records (Latin names) by matching name+city.

Strategy:
1. Load all records with email but no CW ID (11K, Cyrillic names)
2. Load all CW records without email (120K+, Latin names)
3. Convert CW Latin names → Cyrillic
4. Match by normalized Cyrillic name + city
5. Copy email (and phone if missing) from original to CW record

Usage:
    python3 merge_emails.py --dry-run    # Preview matches
    python3 merge_emails.py              # Apply merges
"""
import asyncio
import os
import re
import sys
import logging
import argparse

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
    result = text.lower()
    for lat, cyr in sorted(MULTI_CHAR.items(), key=lambda x: -len(x[0])):
        result = result.replace(lat, cyr)
    for lat, cyr in SINGLE_CHAR.items():
        result = result.replace(lat, cyr)
    return result


def normalize_name(name):
    """Normalize a company name for matching."""
    n = name.upper().strip()
    # Remove common legal forms
    for form in ['ДООЕЛ', 'ДОО', 'АД', 'ТП', 'ЈП', 'ДПТУ', 'ДПТСТУ', 'ДТУ',
                 'DOOEL', 'DOO', 'AD', 'TP', 'JP', 'DPTU', 'DPTSTU', 'DTU',
                 'УВОЗ', 'ИЗВОЗ', 'ЕКСПОРТ', 'ИМПОРТ',
                 'UVOZ', 'IZVOZ', 'EKSPORT', 'IMPORT']:
        n = re.sub(rf'\b{form}\b', '', n, flags=re.IGNORECASE)
    # Remove punctuation and extra spaces
    n = re.sub(r'[^\w\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def normalize_city(city):
    """Normalize city name."""
    if not city:
        return ''
    return city.upper().strip()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--min-name-len', type=int, default=4,
                        help='Minimum name length after normalization to consider a match')
    args = parser.parse_args()

    if not DATABASE_URL:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    db_url = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)

    async with pool.acquire() as conn:
        # Load original records with email (Cyrillic names)
        originals = await conn.fetch("""
            SELECT company_id, name, city_mk, email, phone
            FROM mk_companies
            WHERE email IS NOT NULL AND companywall_id IS NULL
              AND name IS NOT NULL
        """)
        logger.info(f"Loaded {len(originals)} records with email (Cyrillic names)")

        # Load CW records without email (Latin names)
        cw_records = await conn.fetch("""
            SELECT company_id, name, city_mk, email, phone, companywall_id
            FROM mk_companies
            WHERE companywall_id IS NOT NULL AND email IS NULL
              AND name IS NOT NULL
        """)
        logger.info(f"Loaded {len(cw_records)} CW records without email (Latin names)")

    # Build lookup from normalized Cyrillic name + city → original record
    orig_lookup = {}
    for rec in originals:
        norm_name = normalize_name(rec['name'])
        norm_city = normalize_city(rec['city_mk'])
        if len(norm_name) >= args.min_name_len:
            key = (norm_name, norm_city)
            if key not in orig_lookup:
                orig_lookup[key] = rec

    # Also build name-only lookup for cases where city might differ
    orig_name_lookup = {}
    for rec in originals:
        norm_name = normalize_name(rec['name'])
        if len(norm_name) >= 8:  # Longer names can match without city
            if norm_name not in orig_name_lookup:
                orig_name_lookup[norm_name] = rec
            else:
                # Multiple records with same name - don't match by name alone
                orig_name_lookup[norm_name] = None

    logger.info(f"Built lookup: {len(orig_lookup)} name+city keys, "
                f"{sum(1 for v in orig_name_lookup.values() if v)} unique name keys")

    # Match CW records to originals
    matches = []
    for cw_rec in cw_records:
        latin_name = cw_rec['name']
        cyrillic_name = latin_to_cyrillic(latin_name)
        norm_cyr = normalize_name(cyrillic_name)

        # Convert Latin city to Cyrillic for proper matching
        cw_city = cw_rec['city_mk'] or ''
        cw_city_cyr = latin_to_cyrillic(cw_city).upper().strip() if cw_city else ''

        # Try name + city match first (strict - requires both to match)
        key = (norm_cyr, cw_city_cyr)
        orig = orig_lookup.get(key)

        # Fall back to name-only match ONLY for very long unique names (15+ chars)
        if not orig and len(norm_cyr) >= 15:
            orig = orig_name_lookup.get(norm_cyr)

        if orig:
            email = orig['email']
            # Skip government/institutional emails being assigned to companies
            if email and any(x in email.lower() for x in [
                '.gov.mk', '.edu.mk', 'ukim.edu', 'stat.gov', 'ujp.gov',
                'redcross', 'unicef', 'undp', '@un.org',
            ]):
                continue
            matches.append({
                'cw_id': cw_rec['company_id'],
                'cw_name': latin_name,
                'cw_city': cw_rec['city_mk'],
                'orig_id': orig['company_id'],
                'orig_name': orig['name'],
                'orig_city': orig['city_mk'],
                'email': email,
                'phone': orig['phone'] if not cw_rec['phone'] else None,
            })

    logger.info(f"Found {len(matches)} matches!")

    # Show sample matches
    for m in matches[:20]:
        logger.info(
            f"  MATCH: CW '{m['cw_name']}' ({m['cw_city']}) "
            f"← orig '{m['orig_name']}' ({m['orig_city']}) "
            f"email={m['email']}"
        )

    if len(matches) > 20:
        logger.info(f"  ... and {len(matches) - 20} more matches")

    if not args.dry_run and matches:
        logger.info("Applying merges...")
        async with pool.acquire() as conn:
            updated = 0
            for m in matches:
                await conn.execute("""
                    UPDATE mk_companies SET
                        email = COALESCE($2, email),
                        phone = COALESCE($3, phone),
                        updated_at = NOW()
                    WHERE company_id = $1
                """, m['cw_id'], m['email'], m['phone'])
                updated += 1
            logger.info(f"Updated {updated} CW records with emails")

        # Show new stats
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total,
                    COUNT(email) as with_email,
                    COUNT(CASE WHEN companywall_id IS NOT NULL AND email IS NOT NULL THEN 1 END) as cw_with_email
                FROM mk_companies
            """)
            logger.info(f"New stats: total={stats['total']}, with_email={stats['with_email']}, cw_with_email={stats['cw_with_email']}")

    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
