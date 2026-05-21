#!/usr/bin/env python3
"""
Discover email contacts for tender-winning companies.

Three-phase discovery pipeline:
  Phase A: Extract emails from raw_data_json (JSONB) — OCDS contactPoint, parties, etc.
  Phase B: Search via Brave Search API for company emails
  Phase C: Scrape discovered company websites for emails on homepage/contact pages

After discovering a contact email, updates the suppliers table and creates
an outreach_leads record if one doesn't exist for that email.

Run: python3 crons/discover_contacts.py
     python3 crons/discover_contacts.py --dry-run
     python3 crons/discover_contacts.py --limit 100 --phase A
     python3 crons/discover_contacts.py --phase B --limit 50
     python3 crons/discover_contacts.py --phase C --limit 50
Cron: 0 3 * * * cd /home/ubuntu/nabavkidata/backend && python3 crons/discover_contacts.py --limit 200 >> /var/log/nabavkidata/discover_contacts.log 2>&1
"""

import os
import sys
import asyncio
import argparse
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import asyncpg
import dns.resolver
import httpx
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

DATABASE_URL = os.getenv('DATABASE_URL')
BRAVE_API_KEY = os.getenv('BRAVE_API_KEY', '')
BRAVE_URL = 'https://api.search.brave.com/res/v1/web/search'
BRAVE_RATE_LIMIT_DELAY = 1.1  # seconds between requests (API limit ~1 req/sec)

# Email extraction regex — intentionally broad to catch emails in HTML/text
EMAIL_REGEX = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
)

# Stricter validation for final candidate emails
VALID_EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)

# Domains to skip — freemail, government, placeholder, and example domains
SKIP_DOMAINS: Set[str] = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'example.com',
    'mail.com', 'aol.com', 'icloud.com', 'live.com', 'msn.com',
    'test.com', 'email.com', 'tempmail.com', 'yopmail.com',
    'gov.mk', 'finance.gov.mk', 'e-nabavki.gov.mk',
    'nabavkidata.com',
    # Image/file extensions that look like emails in regex
    'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf', 'css', 'js',
}

# Common file-extension false positives in email regex
SKIP_EMAIL_PATTERNS = [
    r'\.png$', r'\.jpg$', r'\.jpeg$', r'\.gif$', r'\.svg$',
    r'\.css$', r'\.js$', r'\.pdf$', r'\.woff', r'\.ttf',
    r'@2x\.', r'@3x\.',
    r'^[0-9]+@',  # Starts with only numbers
]

# MX record cache: domain -> bool
_mx_cache: Dict[str, bool] = {}

# Company name prefixes to strip for cleaner search queries
COMPANY_PREFIXES = [
    'Друштво за трговија и услуги',
    'Друштво за производство трговија и услуги',
    'Друштво за трговија',
    'Друштво за производство и трговија',
    'Друштво за градежништво трговија и услуги',
    'Друштво за производство',
    'Трговско друштво за',
    'Трговско друштво',
    'Акционерско друштво',
    'Градежно друштво',
    'Друштво за',
    'ДООЕЛ', 'ДОО', 'АД', 'Производство',
    'увоз-извоз', 'увоз извоз',
]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def clean_company_name(name: str) -> str:
    """Strip common legal prefixes/suffixes from Macedonian company names for search."""
    if not name:
        return ''
    result = name.strip()
    for prefix in COMPANY_PREFIXES:
        result = result.replace(prefix, '').strip()
    # Remove extra whitespace and trailing commas/dashes
    result = re.sub(r'\s+', ' ', result).strip(' ,-')
    return result


def extract_domain_from_email(email: str) -> str:
    """Extract domain from email address."""
    if '@' in email:
        return email.split('@')[1].lower()
    return ''


def is_valid_email(email: str) -> bool:
    """Validate email format — reject Cyrillic chars, too-short, bad format."""
    if not email or len(email) < 5:
        return False
    if not VALID_EMAIL_REGEX.match(email):
        return False
    # Reject Cyrillic characters in email
    if any('Ѐ' <= c <= 'ӿ' for c in email):
        return False
    # Reject known false-positive patterns
    for pattern in SKIP_EMAIL_PATTERNS:
        if re.search(pattern, email, re.IGNORECASE):
            return False
    domain = extract_domain_from_email(email)
    if domain in SKIP_DOMAINS:
        return False
    # Reject domains that are just TLDs or too short
    if '.' not in domain or len(domain) < 4:
        return False
    return True


def has_valid_mx(domain: str) -> bool:
    """Check if domain has valid MX (or A) records. Results are cached."""
    if domain in _mx_cache:
        return _mx_cache[domain]
    try:
        dns.resolver.resolve(domain, 'MX', lifetime=5)
        _mx_cache[domain] = True
        return True
    except Exception:
        pass
    # Fallback: check A record
    try:
        dns.resolver.resolve(domain, 'A', lifetime=5)
        _mx_cache[domain] = True
        return True
    except Exception:
        _mx_cache[domain] = False
        return False


def extract_emails_from_text(text: str) -> List[str]:
    """Extract all valid email addresses from a block of text."""
    if not text:
        return []
    raw = EMAIL_REGEX.findall(text.lower())
    seen = set()
    results = []
    for email in raw:
        if email not in seen and is_valid_email(email):
            seen.add(email)
            results.append(email)
    return results


def pick_best_email(emails: List[str], company_name: str = '') -> Optional[str]:
    """Pick the best email from a list. Prefer info@, office@, contact@, then company domain."""
    if not emails:
        return None
    if len(emails) == 1:
        return emails[0]

    # Score each email
    scored = []
    brand = clean_company_name(company_name).lower().replace(' ', '') if company_name else ''

    for email in emails:
        score = 0
        local, domain = email.split('@', 1) if '@' in email else (email, '')

        # Prefer professional prefixes
        if local in ('info', 'office', 'contact', 'kontakt'):
            score += 30
        elif local.startswith('info') or local.startswith('office'):
            score += 20
        elif local.startswith('contact') or local.startswith('kontakt'):
            score += 15
        elif local in ('sales', 'admin', 'direktor', 'director'):
            score += 10

        # Prefer .mk domains
        if domain.endswith('.mk'):
            score += 15
        elif domain.endswith('.com'):
            score += 5

        # Prefer domain matching the brand name
        domain_base = domain.split('.')[0] if domain else ''
        if brand and brand in domain_base:
            score += 25
        elif brand and domain_base in brand:
            score += 20

        scored.append((score, email))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def extract_website_from_url(url: str) -> Optional[str]:
    """Extract clean website base URL from a search result URL."""
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return None


# =============================================================================
# PHASE A: EXTRACT EMAILS FROM raw_data_json
# =============================================================================

async def phase_a_extract_from_raw_data(conn, limit: int, dry_run: bool) -> dict:
    """
    Scan raw_data_json for bidder/supplier emails.

    Sources within raw_data_json:
    - OCDS records: parties[].contactPoint.email, bids.details[].tenderers[].contactPoint.email
    - Scraped data: bidders_data (JSON string), contact_email (this is buyer, skip)
    - Any email patterns in the full JSON text
    """
    logger.info("=" * 60)
    logger.info("PHASE A: Extract emails from raw_data_json")
    logger.info("=" * 60)

    stats = {'scanned': 0, 'emails_found': 0, 'suppliers_updated': 0, 'leads_created': 0}

    # Get winners that don't have emails in suppliers table yet
    # We join with suppliers to check, and scan raw_data_json for emails
    rows = await conn.fetch("""
        SELECT DISTINCT t.winner, t.tender_id, t.raw_data_json
        FROM tenders t
        WHERE t.winner IS NOT NULL
          AND t.winner != ''
          AND t.raw_data_json IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM suppliers s
              WHERE s.company_name = t.winner
                AND s.contact_email IS NOT NULL
                AND s.contact_email != ''
          )
        ORDER BY t.publication_date DESC NULLS LAST
        LIMIT $1
    """, limit)

    logger.info(f"Found {len(rows)} tenders to scan for embedded emails")

    # Group by winner to avoid processing same company multiple times
    winner_tenders: Dict[str, List[dict]] = {}
    for row in rows:
        winner = row['winner']
        if winner not in winner_tenders:
            winner_tenders[winner] = []
        winner_tenders[winner].append(row)

    logger.info(f"Unique winners to process: {len(winner_tenders)}")

    for winner, tenders in winner_tenders.items():
        stats['scanned'] += 1
        found_emails = []

        for tender_row in tenders:
            raw_json = tender_row['raw_data_json']

            # Parse JSONB — asyncpg returns it as a string or dict
            if isinstance(raw_json, str):
                try:
                    raw_data = json.loads(raw_json)
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(raw_json, dict):
                raw_data = raw_json
            else:
                continue

            # --- Source 1: OCDS parties with supplier/tenderer role ---
            parties = raw_data.get('parties', [])
            if isinstance(parties, list):
                for party in parties:
                    if not isinstance(party, dict):
                        continue
                    roles = party.get('roles', [])
                    name = party.get('name', '')
                    # Only extract from supplier/tenderer parties, not buyers
                    if any(r in roles for r in ['supplier', 'tenderer']):
                        contact = party.get('contactPoint', {})
                        if isinstance(contact, dict):
                            email = contact.get('email', '')
                            if email and is_valid_email(email):
                                found_emails.append(email.lower())

            # --- Source 2: OCDS bids.details[].tenderers[] contactPoint ---
            bids = raw_data.get('bids', {})
            if isinstance(bids, dict):
                for detail in bids.get('details', []):
                    if not isinstance(detail, dict):
                        continue
                    for tenderer in detail.get('tenderers', []):
                        if not isinstance(tenderer, dict):
                            continue
                        contact = tenderer.get('contactPoint', {})
                        if isinstance(contact, dict):
                            email = contact.get('email', '')
                            if email and is_valid_email(email):
                                found_emails.append(email.lower())

            # --- Source 3: OCDS awards[].suppliers[] ---
            awards = raw_data.get('awards', [])
            if isinstance(awards, list):
                for award in awards:
                    if not isinstance(award, dict):
                        continue
                    for supplier in award.get('suppliers', []):
                        if not isinstance(supplier, dict):
                            continue
                        contact = supplier.get('contactPoint', {})
                        if isinstance(contact, dict):
                            email = contact.get('email', '')
                            if email and is_valid_email(email):
                                found_emails.append(email.lower())

            # --- Source 4: bidders_data (stored as JSON string in raw_data_json) ---
            bidders_data_str = raw_data.get('bidders_data')
            if bidders_data_str:
                try:
                    if isinstance(bidders_data_str, str):
                        bidders_list = json.loads(bidders_data_str)
                    elif isinstance(bidders_data_str, list):
                        bidders_list = bidders_data_str
                    else:
                        bidders_list = []

                    for bidder in bidders_list:
                        if isinstance(bidder, dict):
                            for key in ('email', 'contact_email', 'e_mail'):
                                email = bidder.get(key, '')
                                if email and is_valid_email(email):
                                    found_emails.append(email.lower())
                except (json.JSONDecodeError, TypeError):
                    pass

            # --- Source 5: Brute-force email extraction from entire JSON text ---
            # Convert to string and extract any email patterns
            # Exclude the buyer's contact_email to avoid false attribution
            buyer_email = (raw_data.get('contact_email') or '').lower()
            json_text = json.dumps(raw_data, ensure_ascii=False)
            all_emails = extract_emails_from_text(json_text)
            for email in all_emails:
                if email.lower() != buyer_email and email.lower() not in found_emails:
                    found_emails.append(email.lower())

        # Deduplicate and pick best
        found_emails = list(set(found_emails))
        # Remove any that match the procuring entity's contact email
        if found_emails:
            best_email = pick_best_email(found_emails, winner)
            if best_email:
                stats['emails_found'] += 1
                logger.info(f"  [A] {winner[:50]} -> {best_email}")

                if not dry_run:
                    # Update or create supplier record
                    updated = await _upsert_supplier_email(conn, winner, best_email)
                    if updated:
                        stats['suppliers_updated'] += 1

                    # Create outreach lead
                    created = await _create_outreach_lead(
                        conn, best_email, winner, source='raw_data_json'
                    )
                    if created:
                        stats['leads_created'] += 1

    logger.info(f"Phase A complete: scanned={stats['scanned']}, "
                f"emails_found={stats['emails_found']}, "
                f"suppliers_updated={stats['suppliers_updated']}, "
                f"leads_created={stats['leads_created']}")
    return stats


# =============================================================================
# PHASE B: BRAVE SEARCH API
# =============================================================================

async def phase_b_brave_search(conn, client: httpx.AsyncClient, limit: int, dry_run: bool) -> dict:
    """
    Search Brave for company emails for winners without known emails.
    Rate-limited to ~1 request/second.
    """
    logger.info("=" * 60)
    logger.info("PHASE B: Brave Search for company emails")
    logger.info("=" * 60)

    if not BRAVE_API_KEY:
        logger.error("BRAVE_API_KEY not set, skipping Phase B")
        return {'skipped': True, 'reason': 'no_api_key'}

    stats = {'searched': 0, 'emails_found': 0, 'websites_found': 0,
             'suppliers_updated': 0, 'leads_created': 0, 'rate_limited': 0}

    # Get winners without emails, that haven't been Brave-searched yet
    # We use the suppliers table and a raw_data marker to track what's been searched
    winners = await conn.fetch("""
        WITH unique_winners AS (
            SELECT DISTINCT t.winner,
                   COUNT(*) as tender_count,
                   SUM(COALESCE(t.estimated_value_mkd, 0)) as total_value
            FROM tenders t
            WHERE t.winner IS NOT NULL
              AND t.winner != ''
              AND LENGTH(t.winner) > 3
            GROUP BY t.winner
            ORDER BY tender_count DESC
        )
        SELECT uw.winner, uw.tender_count, uw.total_value
        FROM unique_winners uw
        LEFT JOIN suppliers s ON s.company_name = uw.winner
        WHERE (s.contact_email IS NULL OR s.contact_email = '')
          AND NOT EXISTS (
              SELECT 1 FROM outreach_leads ol
              WHERE ol.company_name = uw.winner
                AND ol.email IS NOT NULL
          )
          AND NOT EXISTS (
              SELECT 1 FROM suppliers s2
              WHERE s2.company_name = uw.winner
                AND s2.website IS NOT NULL
                AND s2.website != ''
                AND (s2.updated_at > NOW() - INTERVAL '7 days')
          )
        LIMIT $1
    """, limit)

    logger.info(f"Found {len(winners)} winners to search via Brave")

    for i, row in enumerate(winners, 1):
        winner = row['winner']
        clean_name = clean_company_name(winner)
        if not clean_name or len(clean_name) < 3:
            continue

        stats['searched'] += 1

        # Search query: company name + email + .mk site preference
        query = f'"{clean_name}" email контакт site:.mk'
        results = await _brave_search(client, query)

        if results is None:
            stats['rate_limited'] += 1
            logger.warning("Rate limited, stopping Phase B")
            break

        # Extract emails and websites from search results
        found_emails = []
        found_websites = []
        all_text = ''

        for result in results:
            title = result.get('title', '')
            snippet = result.get('description', '')
            url = result.get('url', '')
            all_text += f" {title} {snippet} "

            # Collect potential company websites
            if url:
                website = extract_website_from_url(url)
                if website and not any(skip in website for skip in
                    ['facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com',
                     'youtube.com', 'wikipedia.org', 'google.com', 'nabavkidata.com',
                     'e-nabavki.gov.mk', 'ujp.gov.mk', 'crm.com.mk']):
                    found_websites.append(website)

        # Extract emails from snippets
        found_emails = extract_emails_from_text(all_text)

        # If no emails found in first search, try a broader query
        if not found_emails:
            query2 = f'"{clean_name}" Македонија email'
            results2 = await _brave_search(client, query2)
            if results2 is None:
                stats['rate_limited'] += 1
                break
            for result in results2:
                all_text += f" {result.get('title', '')} {result.get('description', '')} "
                url = result.get('url', '')
                if url:
                    website = extract_website_from_url(url)
                    if website and not any(skip in website for skip in
                        ['facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com',
                         'youtube.com', 'wikipedia.org', 'google.com', 'nabavkidata.com',
                         'e-nabavki.gov.mk']):
                        found_websites.append(website)
            found_emails = extract_emails_from_text(all_text)

        # Store website even if no email found (for Phase C)
        website_to_store = found_websites[0] if found_websites else None
        if website_to_store:
            stats['websites_found'] += 1

        best_email = pick_best_email(found_emails, winner) if found_emails else None

        if best_email:
            # Validate MX before accepting
            domain = extract_domain_from_email(best_email)
            if has_valid_mx(domain):
                stats['emails_found'] += 1
                logger.info(f"  [B] {winner[:50]} -> {best_email}")

                if not dry_run:
                    await _upsert_supplier_email(conn, winner, best_email, website=website_to_store)
                    stats['suppliers_updated'] += 1

                    created = await _create_outreach_lead(
                        conn, best_email, winner, source='brave_search'
                    )
                    if created:
                        stats['leads_created'] += 1
            else:
                logger.info(f"  [B] {winner[:50]} -> {best_email} (SKIP: no MX)")
                # Still store website if found
                if website_to_store and not dry_run:
                    await _upsert_supplier_website(conn, winner, website_to_store)
        elif website_to_store and not dry_run:
            # No email but found website — store it for Phase C
            await _upsert_supplier_website(conn, winner, website_to_store)
            logger.info(f"  [B] {winner[:50]} -> no email, website: {website_to_store}")

        # Progress logging
        if i % 25 == 0:
            logger.info(f"  Progress: {i}/{len(winners)} searched, "
                        f"{stats['emails_found']} emails, "
                        f"{stats['websites_found']} websites")

        # Rate limit
        await asyncio.sleep(BRAVE_RATE_LIMIT_DELAY)

    logger.info(f"Phase B complete: searched={stats['searched']}, "
                f"emails_found={stats['emails_found']}, "
                f"websites_found={stats['websites_found']}, "
                f"suppliers_updated={stats['suppliers_updated']}, "
                f"leads_created={stats['leads_created']}")
    return stats


async def _brave_search(client: httpx.AsyncClient, query: str, count: int = 10) -> Optional[list]:
    """Execute a Brave Search API query. Returns None if rate-limited."""
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
            logger.warning("Brave API rate limited (429)")
            await asyncio.sleep(30)
            return None
        if resp.status_code != 200:
            logger.warning(f"Brave API error: {resp.status_code}")
            return []
        data = resp.json()
        return data.get('web', {}).get('results', [])
    except Exception as e:
        logger.error(f"Brave search error: {e}")
        return []


# =============================================================================
# PHASE C: SCRAPE COMPANY WEBSITES
# =============================================================================

async def phase_c_scrape_websites(conn, client: httpx.AsyncClient, limit: int, dry_run: bool) -> dict:
    """
    For companies with websites but no emails, scrape homepage and /contact page
    to extract email addresses via regex.
    """
    logger.info("=" * 60)
    logger.info("PHASE C: Scrape company websites for emails")
    logger.info("=" * 60)

    stats = {'scraped': 0, 'emails_found': 0, 'suppliers_updated': 0,
             'leads_created': 0, 'errors': 0}

    # Get suppliers with websites but no emails
    suppliers = await conn.fetch("""
        SELECT supplier_id, company_name, website
        FROM suppliers
        WHERE website IS NOT NULL
          AND website != ''
          AND (contact_email IS NULL OR contact_email = '')
        ORDER BY total_wins DESC NULLS LAST
        LIMIT $1
    """, limit)

    logger.info(f"Found {len(suppliers)} suppliers with websites but no emails")

    for i, row in enumerate(suppliers, 1):
        company = row['company_name']
        website = row['website'].rstrip('/')

        stats['scraped'] += 1
        found_emails = []

        # Try homepage and common contact page paths
        pages_to_try = [
            website,
            f"{website}/contact",
            f"{website}/kontakt",
            f"{website}/about",
            f"{website}/za-nas",
            f"{website}/about-us",
        ]

        for page_url in pages_to_try:
            try:
                resp = await client.get(
                    page_url,
                    follow_redirects=True,
                    timeout=10.0,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (compatible; NabavkiBot/1.0; +https://nabavkidata.com)',
                        'Accept': 'text/html,application/xhtml+xml',
                        'Accept-Language': 'mk,en;q=0.5',
                    }
                )
                if resp.status_code == 200:
                    content_type = resp.headers.get('content-type', '')
                    if 'text/html' in content_type or 'text/plain' in content_type:
                        page_emails = extract_emails_from_text(resp.text)
                        found_emails.extend(page_emails)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError,
                    httpx.TooManyRedirects, Exception) as e:
                # Only log on first page (homepage) — contact pages often 404
                if page_url == website:
                    logger.debug(f"  Error scraping {page_url}: {e}")
                continue

            # Small delay between page requests to the same site
            await asyncio.sleep(0.3)

        # Deduplicate
        found_emails = list(set(found_emails))
        best_email = pick_best_email(found_emails, company) if found_emails else None

        if best_email:
            domain = extract_domain_from_email(best_email)
            if has_valid_mx(domain):
                stats['emails_found'] += 1
                logger.info(f"  [C] {company[:50]} -> {best_email}")

                if not dry_run:
                    await _upsert_supplier_email(conn, company, best_email)
                    stats['suppliers_updated'] += 1

                    created = await _create_outreach_lead(
                        conn, best_email, company, source='website_scrape'
                    )
                    if created:
                        stats['leads_created'] += 1
            else:
                logger.info(f"  [C] {company[:50]} -> {best_email} (SKIP: no MX)")
        else:
            stats['errors'] += 1

        # Progress logging
        if i % 25 == 0:
            logger.info(f"  Progress: {i}/{len(suppliers)} scraped, "
                        f"{stats['emails_found']} emails found")

        # Polite delay between different sites
        await asyncio.sleep(0.5)

    logger.info(f"Phase C complete: scraped={stats['scraped']}, "
                f"emails_found={stats['emails_found']}, "
                f"suppliers_updated={stats['suppliers_updated']}, "
                f"leads_created={stats['leads_created']}")
    return stats


# =============================================================================
# DATABASE HELPERS
# =============================================================================

async def _upsert_supplier_email(conn, company_name: str, email: str,
                                  website: str = None) -> bool:
    """Update or create a supplier record with the discovered email."""
    try:
        existing = await conn.fetchrow(
            "SELECT supplier_id, contact_email FROM suppliers WHERE company_name = $1",
            company_name
        )
        if existing:
            # Only update if no email yet
            if not existing['contact_email']:
                update_parts = ["contact_email = $2", "updated_at = NOW()"]
                params = [company_name, email]
                if website:
                    update_parts.append(f"website = COALESCE(website, ${len(params) + 1})")
                    params.append(website)
                await conn.execute(
                    f"UPDATE suppliers SET {', '.join(update_parts)} WHERE company_name = $1",
                    *params
                )
                return True
            return False
        else:
            # Create new supplier record
            # Count tender wins and total value for this company
            win_data = await conn.fetchrow("""
                SELECT COUNT(*) as wins,
                       SUM(COALESCE(estimated_value_mkd, 0)) as total_value
                FROM tenders
                WHERE winner = $1
            """, company_name)
            await conn.execute("""
                INSERT INTO suppliers (
                    company_name, contact_email, website,
                    total_wins, total_contract_value_mkd
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (company_name) DO UPDATE SET
                    contact_email = COALESCE(suppliers.contact_email, EXCLUDED.contact_email),
                    website = COALESCE(suppliers.website, EXCLUDED.website),
                    updated_at = NOW()
            """, company_name, email, website,
                win_data['wins'] if win_data else 0,
                win_data['total_value'] if win_data else 0)
            return True
    except Exception as e:
        logger.error(f"Error upserting supplier {company_name}: {e}")
        return False


async def _upsert_supplier_website(conn, company_name: str, website: str) -> bool:
    """Store a discovered website for a supplier (for later Phase C scraping)."""
    try:
        existing = await conn.fetchrow(
            "SELECT supplier_id, website FROM suppliers WHERE company_name = $1",
            company_name
        )
        if existing:
            if not existing['website']:
                await conn.execute(
                    "UPDATE suppliers SET website = $2, updated_at = NOW() WHERE company_name = $1",
                    company_name, website
                )
                return True
            return False
        else:
            win_data = await conn.fetchrow("""
                SELECT COUNT(*) as wins,
                       SUM(COALESCE(estimated_value_mkd, 0)) as total_value
                FROM tenders WHERE winner = $1
            """, company_name)
            await conn.execute("""
                INSERT INTO suppliers (company_name, website, total_wins, total_contract_value_mkd)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (company_name) DO UPDATE SET
                    website = COALESCE(suppliers.website, EXCLUDED.website),
                    updated_at = NOW()
            """, company_name, website,
                win_data['wins'] if win_data else 0,
                win_data['total_value'] if win_data else 0)
            return True
    except Exception as e:
        logger.error(f"Error upserting supplier website {company_name}: {e}")
        return False


async def _create_outreach_lead(conn, email: str, company_name: str,
                                 source: str) -> bool:
    """Create an outreach_leads record if one doesn't already exist for this email."""
    try:
        # Check if lead already exists
        exists = await conn.fetchval(
            "SELECT 1 FROM outreach_leads WHERE email = $1",
            email.lower()
        )
        if exists:
            return False

        # Check if this email belongs to a registered user
        is_user = await conn.fetchval(
            "SELECT 1 FROM users WHERE LOWER(email) = LOWER($1)", email
        )
        if is_user:
            logger.info(f"  Skip lead creation for registered user: {email}")
            return False

        # Check suppression list
        is_suppressed = await conn.fetchval(
            "SELECT 1 FROM suppression_list WHERE email = $1", email.lower()
        )
        if is_suppressed:
            logger.info(f"  Skip lead creation for suppressed email: {email}")
            return False

        # Calculate quality score based on tender wins
        win_count = await conn.fetchval(
            "SELECT COUNT(*) FROM tenders WHERE winner = $1", company_name
        ) or 0

        # Base score 70 for discovered contacts, bonus for wins
        quality_score = min(100, 70 + min(25, win_count * 2))

        # Get supplier_id if exists
        supplier_id = await conn.fetchval(
            "SELECT supplier_id FROM suppliers WHERE company_name = $1",
            company_name
        )

        await conn.execute("""
            INSERT INTO outreach_leads (
                email, company_name, segment, source, quality_score,
                company_domain, country, supplier_id, raw_data
            ) VALUES ($1, $2, 'A', $3, $4, $5, 'North Macedonia', $6, $7)
            ON CONFLICT (email) DO NOTHING
        """,
            email.lower(),
            company_name,
            source,
            quality_score,
            extract_domain_from_email(email),
            supplier_id,
            json.dumps({
                'discovered_at': datetime.utcnow().isoformat(),
                'discovery_source': source,
                'tender_wins': win_count,
            })
        )
        return True
    except Exception as e:
        logger.error(f"Error creating outreach lead for {email}: {e}")
        return False


# =============================================================================
# MAIN
# =============================================================================

async def run(args):
    """Main entry point — runs selected phases."""
    logger.info("=" * 60)
    logger.info("DISCOVER CONTACTS")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info(f"Phase: {args.phase or 'ALL'}")
    logger.info(f"Limit: {args.limit}")
    if args.dry_run:
        logger.info("*** DRY RUN — no database changes ***")
    logger.info("=" * 60)

    conn = await asyncpg.connect(DATABASE_URL)
    all_stats = {}

    try:
        # Show current state
        total_winners = await conn.fetchval("""
            SELECT COUNT(DISTINCT winner) FROM tenders
            WHERE winner IS NOT NULL AND winner != ''
        """)
        with_email = await conn.fetchval("""
            SELECT COUNT(*) FROM suppliers
            WHERE contact_email IS NOT NULL AND contact_email != ''
        """)
        total_leads = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")

        logger.info(f"Current state: {total_winners} unique winners, "
                     f"{with_email} with emails, {total_leads} outreach leads")

        async with httpx.AsyncClient() as client:
            # Phase A: Extract from raw_data_json
            if args.phase is None or args.phase == 'A':
                all_stats['phase_a'] = await phase_a_extract_from_raw_data(
                    conn, args.limit, args.dry_run
                )

            # Phase B: Brave Search
            if args.phase is None or args.phase == 'B':
                all_stats['phase_b'] = await phase_b_brave_search(
                    conn, client, args.limit, args.dry_run
                )

            # Phase C: Scrape websites
            if args.phase is None or args.phase == 'C':
                all_stats['phase_c'] = await phase_c_scrape_websites(
                    conn, client, args.limit, args.dry_run
                )

        # Final summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("DISCOVERY COMPLETE")
        logger.info("=" * 60)

        total_found = sum(
            s.get('emails_found', 0)
            for s in all_stats.values()
            if isinstance(s, dict)
        )
        total_leads_created = sum(
            s.get('leads_created', 0)
            for s in all_stats.values()
            if isinstance(s, dict)
        )

        logger.info(f"Total emails discovered: {total_found}")
        logger.info(f"Total outreach leads created: {total_leads_created}")

        # Updated state
        with_email_after = await conn.fetchval("""
            SELECT COUNT(*) FROM suppliers
            WHERE contact_email IS NOT NULL AND contact_email != ''
        """)
        total_leads_after = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")
        logger.info(f"Suppliers with emails: {with_email} -> {with_email_after}")
        logger.info(f"Outreach leads: {total_leads} -> {total_leads_after}")

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description='Discover email contacts for tender winners')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without making database changes')
    parser.add_argument('--limit', type=int, default=500,
                        help='Max companies to process per phase (default: 500)')
    parser.add_argument('--phase', choices=['A', 'B', 'C'],
                        help='Run only a specific phase (default: all)')
    args = parser.parse_args()

    await run(args)


if __name__ == '__main__':
    asyncio.run(main())
