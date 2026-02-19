"""
Scrape yellowpages.com.mk for company emails, phones, addresses.

~42,000 companies, ~43% have emails (~18K), 100% have phones.
Public data, robots.txt allows crawling with 10s delay.

URLs: firma.php?id=1 through id=55819

Usage:
    # Test with 20 companies
    python3 scrape_yellowpages.py --limit 20

    # Full scrape (respects robots.txt 10s delay)
    python3 scrape_yellowpages.py

    # Fast mode (1s delay, ~15 hours for full scrape)
    python3 scrape_yellowpages.py --delay 1

    # Resume from specific ID
    python3 scrape_yellowpages.py --start-id 10000

    # Dry run (don't write to DB)
    python3 scrape_yellowpages.py --limit 50 --dry-run
"""
import asyncio
import os
import re
import sys
import argparse
import logging

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', '')
MAX_ID = 55820  # IDs go up to ~55819 based on sitemap

# Latin to Macedonian Cyrillic mapping (for matching)
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
    """Normalize company name for matching."""
    n = name.upper().strip()
    for form in ['ДООЕЛ', 'ДОО', 'АД', 'ТП', 'ЈП', 'ДПТУ', 'ДПТСТУ', 'ДТУ',
                 'DOOEL', 'DOO', 'AD', 'TP', 'JP', 'DPTU',
                 'УВОЗ', 'ИЗВОЗ', 'ЕКСПОРТ', 'ИМПОРТ']:
        n = re.sub(rf'\b{form}\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'[^\w\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def extract_city_from_address(address):
    """Extract city from yellowpages address like 'УЛИЦА 123, СКОПЈЕ'."""
    if not address:
        return None
    parts = address.split(',')
    if len(parts) >= 2:
        return parts[-1].strip()
    return address.strip()


def parse_yp_page(html):
    """Parse a yellowpages.com.mk company page."""
    if not html or len(html) < 500:
        return None

    # Check if it's a valid company page
    title_m = re.search(r'<title>([^<]+)', html)
    if not title_m:
        return None
    title = title_m.group(1).strip()
    if title in ('Yellow Pages Macedonia', ''):
        return None

    data = {'name': title}

    # Extract fields using the Text="" pattern
    fields = {
        'address': r'Text="адреса:">([^<]+)',
        'phone': r'Text="телефон 1:">([^<]+)',
        'phone2': r'Text="телефон 2:">([^<]+)',
        'fax': r'Text="факс:">([^<]+)',
        'email': r'Text="e-mail:">([^<]+)',
        'website': r'Text="web:">([^<]+)',
        'facebook': r'Text="facebook:">([^<]+)',
        'instagram': r'Text="Instagram:">([^<]+)',
    }

    for field, pattern in fields.items():
        m = re.search(pattern, html)
        if m:
            val = m.group(1).strip()
            if val:
                data[field] = val

    # Extract city from address
    if data.get('address'):
        data['city'] = extract_city_from_address(data['address'])

    return data if data.get('name') else None


async def fetch_page(client, yp_id):
    """Fetch a yellowpages company page."""
    try:
        resp = await client.get(
            f'https://yellowpages.com.mk/firma.php?id={yp_id}',
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception as e:
        logger.debug(f"Error fetching ID {yp_id}: {e}")
        return None



async def build_lookup(pool):
    """Build in-memory lookup from mk_companies (one-time)."""
    async with pool.acquire() as conn:
        companies = await conn.fetch("""
            SELECT company_id, name, email, phone, city_mk
            FROM mk_companies
            WHERE name IS NOT NULL AND email IS NULL
        """)

    logger.info(f"Loaded {len(companies)} companies needing emails")

    lookup_name_city = {}
    lookup_name_only = {}

    for c in companies:
        name = c['name']
        norm = normalize_name(name)
        city = (c['city_mk'] or '').upper().strip()

        # Also convert Latin name to Cyrillic for CW records
        norm_cyr = normalize_name(latin_to_cyrillic(name))

        for n in (norm, norm_cyr):
            if len(n) >= 4:
                key = (n, city)
                if key not in lookup_name_city:
                    lookup_name_city[key] = c

                if len(n) >= 10:
                    if n not in lookup_name_only:
                        lookup_name_only[n] = c
                    else:
                        lookup_name_only[n] = None  # Ambiguous

    logger.info(f"Built lookup: {len(lookup_name_city)} name+city, "
                f"{sum(1 for v in lookup_name_only.values() if v)} unique names")

    return lookup_name_city, lookup_name_only


async def match_batch(pool, yp_data_list, lookup_name_city, lookup_name_only, dry_run=False):
    """Match YP data to existing records OR insert new ones. Store all fields."""
    stats = {'matched': 0, 'updated': 0, 'inserted': 0, 'no_data': 0}

    for yp in yp_data_list:
        email = yp.get('email')
        phone = yp.get('phone')
        name = yp.get('name', '')
        address = yp.get('address')
        city = yp.get('city')
        website = yp.get('website')
        yp_id = yp.get('yp_id')

        if not name or len(name) < 2:
            stats['no_data'] += 1
            continue

        yp_name = normalize_name(name)
        yp_city = (city or '').upper().strip()

        # Try name + city match
        match = lookup_name_city.get((yp_name, yp_city))

        # Try name only for longer names
        if not match and len(yp_name) >= 10:
            match = lookup_name_only.get(yp_name)

        if match:
            # UPDATE existing record with new data
            stats['matched'] += 1
            if not dry_run:
                async with pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE mk_companies SET
                            email = COALESCE(email, $2),
                            phone = COALESCE(phone, $3),
                            address = COALESCE(address, $4),
                            website = COALESCE(website, $5),
                            email_source = CASE WHEN email IS NULL AND $2 IS NOT NULL
                                           THEN 'yellowpages' ELSE email_source END,
                            updated_at = NOW()
                        WHERE company_id = $1
                    """, match['company_id'], email, phone, address, website)
                stats['updated'] += 1
                # Remove from lookup so we don't update same record twice
                lookup_name_city.pop((yp_name, yp_city), None)
                if len(yp_name) >= 10:
                    lookup_name_only.pop(yp_name, None)
        else:
            # INSERT new company record
            if not dry_run:
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO mk_companies
                            (name, email, phone, address, city_mk, website,
                             email_source, source_url, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                    """,
                        name, email, phone, address, city,
                        website,
                        'yellowpages' if email else None,
                        f'https://yellowpages.com.mk/firma.php?id={yp_id}',
                    )
            stats['inserted'] += 1

    return stats


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-id', type=int, default=1)
    parser.add_argument('--limit', type=int, default=0, help='Max pages to fetch (0=all)')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='Delay between requests in seconds (robots.txt says 10)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--batch-size', type=int, default=500,
                        help='Save to DB every N companies')
    args = parser.parse_args()

    if not DATABASE_URL:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    db_url = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)

    end_id = MAX_ID
    if args.limit > 0:
        end_id = min(args.start_id + args.limit, MAX_ID)

    stats = {
        'fetched': 0, 'valid': 0, 'with_email': 0, 'with_phone': 0,
        'empty': 0, 'errors': 0,
    }

    all_yp_data = []

    # Load company lookup ONCE at start (not per batch)
    logger.info("Loading mk_companies lookup (one-time)...")
    lookup_name_city, lookup_name_only = await build_lookup(pool)

    logger.info(f"Scraping yellowpages.com.mk IDs {args.start_id} to {end_id} "
                f"(delay={args.delay}s, dry_run={args.dry_run})")

    match_totals = {'matched': 0, 'updated': 0, 'inserted': 0, 'no_data': 0}

    async with httpx.AsyncClient(
        headers={'User-Agent': 'Mozilla/5.0 (compatible; NabavkiBot/1.0)'},
        follow_redirects=True,
    ) as client:
        for yp_id in range(args.start_id, end_id):
            html = await fetch_page(client, yp_id)
            stats['fetched'] += 1

            if html:
                data = parse_yp_page(html)
                if data:
                    stats['valid'] += 1
                    if data.get('email'):
                        stats['with_email'] += 1
                    if data.get('phone'):
                        stats['with_phone'] += 1
                    data['yp_id'] = yp_id
                    all_yp_data.append(data)
                else:
                    stats['empty'] += 1
            else:
                stats['errors'] += 1

            # Progress every 500
            if stats['fetched'] % 500 == 0:
                logger.info(
                    f"Progress: ID {yp_id} | fetched={stats['fetched']} | "
                    f"valid={stats['valid']} | emails={stats['with_email']} | "
                    f"phones={stats['with_phone']} | matched={match_totals['matched']}"
                )

            # Batch save every N companies
            if len(all_yp_data) >= args.batch_size:
                batch_stats = await match_batch(pool, all_yp_data, lookup_name_city,
                                                lookup_name_only, args.dry_run)
                for k, v in batch_stats.items():
                    match_totals[k] = match_totals.get(k, 0) + v
                logger.info(f"Batch: {batch_stats} | Total matched: {match_totals['matched']}")
                all_yp_data = []

            await asyncio.sleep(args.delay)

    # Final batch
    if all_yp_data:
        batch_stats = await match_batch(pool, all_yp_data, lookup_name_city,
                                        lookup_name_only, args.dry_run)
        for k, v in batch_stats.items():
            match_totals[k] = match_totals.get(k, 0) + v
        logger.info(f"Final batch: {batch_stats}")

    logger.info(f"Match totals: {match_totals}")

    # Print final stats
    logger.info(f"=== SCRAPE COMPLETE ===")
    logger.info(f"Fetched: {stats['fetched']}")
    logger.info(f"Valid companies: {stats['valid']}")
    logger.info(f"With email: {stats['with_email']}")
    logger.info(f"With phone: {stats['with_phone']}")
    logger.info(f"Empty/invalid: {stats['empty']}")

    # Show DB stats
    async with pool.acquire() as conn:
        db_stats = await conn.fetchrow("""
            SELECT COUNT(*) as total,
                   COUNT(email) as with_email,
                   COUNT(phone) as with_phone
            FROM mk_companies
        """)
        logger.info(f"DB stats: total={db_stats['total']}, "
                    f"with_email={db_stats['with_email']}, "
                    f"with_phone={db_stats['with_phone']}")

    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
