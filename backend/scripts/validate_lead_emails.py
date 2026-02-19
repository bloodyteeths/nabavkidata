#!/usr/bin/env python3
"""
Validate outreach lead emails by:
1. Regex check for invalid characters (Cyrillic in domain, malformed)
2. DNS MX record lookup for email domains
3. Suppress leads with invalid emails

Usage:
  python3 validate_lead_emails.py --dry-run
  python3 validate_lead_emails.py
"""
import asyncio
import asyncpg
import argparse
import logging
import re
import dns.resolver
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

DB_DSN = os.getenv("DATABASE_URL")

# Cyrillic characters that should never appear in email addresses
CYRILLIC_RE = re.compile(r'[\u0400-\u04FF]')
# Basic email regex
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def validate_email_format(email: str) -> tuple:
    """Check email format. Returns (is_valid, reason)."""
    if not email or not email.strip():
        return False, "empty"

    email = email.strip().lower()

    # Check for Cyrillic characters
    if CYRILLIC_RE.search(email):
        return False, "cyrillic_chars"

    # Check basic format
    if not EMAIL_RE.match(email):
        return False, "invalid_format"

    # Check domain has at least one dot
    parts = email.split('@')
    if len(parts) != 2:
        return False, "invalid_format"

    domain = parts[1]
    if '.' not in domain:
        return False, "no_tld"

    if domain.endswith('.'):
        return False, "trailing_dot"

    return True, "ok"


def check_mx_record(domain: str, cache: dict) -> tuple:
    """Check if domain has valid MX records. Returns (has_mx, reason)."""
    if domain in cache:
        return cache[domain]

    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=5)
        if answers:
            cache[domain] = (True, "has_mx")
            return True, "has_mx"
        cache[domain] = (False, "no_mx_records")
        return False, "no_mx_records"
    except dns.resolver.NXDOMAIN:
        cache[domain] = (False, "domain_not_found")
        return False, "domain_not_found"
    except dns.resolver.NoAnswer:
        # No MX but try A record fallback
        try:
            dns.resolver.resolve(domain, 'A', lifetime=5)
            cache[domain] = (True, "has_a_record")
            return True, "has_a_record"
        except Exception:
            cache[domain] = (False, "no_mx_no_a")
            return False, "no_mx_no_a"
    except dns.resolver.NoNameservers:
        cache[domain] = (False, "no_nameservers")
        return False, "no_nameservers"
    except dns.exception.Timeout:
        cache[domain] = (False, "dns_timeout")
        return False, "dns_timeout"
    except Exception as e:
        cache[domain] = (False, f"dns_error:{str(e)[:50]}")
        return False, f"dns_error:{str(e)[:50]}"


async def main():
    parser = argparse.ArgumentParser(description='Validate outreach lead emails')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, no changes')
    args = parser.parse_args()

    conn = await asyncpg.connect(DB_DSN)

    # Get all not_contacted leads
    leads = await conn.fetch("""
        SELECT lead_id, email, company_name, segment
        FROM outreach_leads
        WHERE outreach_status = 'not_contacted'
        ORDER BY segment, lead_id
    """)

    logger.info(f"Checking {len(leads)} not_contacted leads...")

    mx_cache = {}
    invalid_format = []
    no_mx = []
    valid = []
    stats = defaultdict(int)

    for i, lead in enumerate(leads):
        email = (lead['email'] or '').strip().lower()

        # Step 1: Format validation
        is_valid, reason = validate_email_format(email)
        if not is_valid:
            invalid_format.append((lead['lead_id'], email, lead['company_name'], reason))
            stats[f"format:{reason}"] += 1
            continue

        # Step 2: MX record check
        domain = email.split('@')[1]
        has_mx, mx_reason = check_mx_record(domain, mx_cache)
        if not has_mx:
            no_mx.append((lead['lead_id'], email, lead['company_name'], mx_reason))
            stats[f"mx:{mx_reason}"] += 1
            continue

        valid.append(lead['lead_id'])

        if (i + 1) % 500 == 0:
            logger.info(f"  Checked {i+1}/{len(leads)} — {len(invalid_format)} invalid format, {len(no_mx)} no MX, {len(mx_cache)} domains cached")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"VALIDATION RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Total checked:    {len(leads)}")
    logger.info(f"Valid:            {len(valid)}")
    logger.info(f"Invalid format:   {len(invalid_format)}")
    logger.info(f"No MX record:     {len(no_mx)}")
    logger.info(f"Domains checked:  {len(mx_cache)}")
    logger.info(f"\nBreakdown:")
    for reason, count in sorted(stats.items(), key=lambda x: -x[1]):
        logger.info(f"  {reason}: {count}")

    if invalid_format:
        logger.info(f"\nSample invalid format emails:")
        for lid, email, name, reason in invalid_format[:20]:
            logger.info(f"  [{reason}] {email} — {name}")

    if no_mx:
        logger.info(f"\nSample no-MX emails:")
        for lid, email, name, reason in no_mx[:20]:
            logger.info(f"  [{reason}] {email} — {name}")

    # Suppress invalid leads
    all_invalid = invalid_format + no_mx
    if not all_invalid:
        logger.info("\nNo invalid leads found!")
        await conn.close()
        return

    if args.dry_run:
        logger.info(f"\nDRY RUN — would suppress {len(all_invalid)} leads")
        await conn.close()
        return

    logger.info(f"\nSuppressing {len(all_invalid)} invalid leads...")

    # Batch update: mark as bounced
    invalid_ids = [x[0] for x in all_invalid]
    batch_size = 500
    for i in range(0, len(invalid_ids), batch_size):
        batch = invalid_ids[i:i+batch_size]
        await conn.execute("""
            UPDATE outreach_leads
            SET outreach_status = 'bounced'
            WHERE lead_id = ANY($1::uuid[])
        """, batch)
        logger.info(f"  Updated {min(i+batch_size, len(invalid_ids))}/{len(invalid_ids)}")

    # Add to suppression list
    invalid_emails = [(x[1], x[3]) for x in all_invalid]
    for email, reason in invalid_emails:
        await conn.execute("""
            INSERT INTO suppression_list (email, reason, source, notes, created_at)
            VALUES ($1, 'invalid_email', 'mx_validation', $2, NOW())
            ON CONFLICT (email) DO NOTHING
        """, email, reason)

    logger.info(f"\nDone! Suppressed {len(all_invalid)} leads.")

    # Final stats
    remaining = await conn.fetchval("""
        SELECT COUNT(*) FROM outreach_leads WHERE outreach_status = 'not_contacted'
    """)
    logger.info(f"Remaining not_contacted leads: {remaining}")

    await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
