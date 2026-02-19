#!/usr/bin/env python3
"""
Reveal emails for existing Apollo contacts using credits.
This script processes contacts already in the database that don't have real emails.

Usage:
    python3 scripts/apollo_reveal_emails.py --dry-run
    python3 scripts/apollo_reveal_emails.py --limit=100  # Reveal 100 emails
    python3 scripts/apollo_reveal_emails.py              # Reveal all
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "M5Ker5RzIA9flD0s_IONEA")
APOLLO_BASE_URL = "https://api.apollo.io/v1"


async def reveal_email(session, first_name: str, last_name: str, company_name: str) -> dict:
    """Reveal email for a contact using people/match (uses credits)"""
    url = f"{APOLLO_BASE_URL}/people/match"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }

    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": company_name,
        "reveal_personal_emails": True
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                person = data.get('person', {})
                email = person.get('email')

                # Check if it's a real email
                if email and '@' in email and 'not_unlocked' not in email.lower():
                    return {
                        'email': email,
                        'email_status': person.get('email_status'),
                        'phone': person.get('phone_number'),
                        'linkedin_url': person.get('linkedin_url')
                    }
                return None
            elif resp.status == 403 or resp.status == 429:
                text = await resp.text()
                if 'credit' in text.lower() or 'limit' in text.lower():
                    return {'error': 'OUT_OF_CREDITS'}
                return {'error': f'RATE_LIMITED: {resp.status}'}
            else:
                return None
    except Exception as e:
        print(f"    Request error: {e}")
        return None


async def main():
    print("=" * 70)
    print("APOLLO EMAIL REVEAL")
    print("=" * 70)

    dry_run = '--dry-run' in sys.argv

    # Parse limit
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    conn = await asyncpg.connect(DATABASE_URL)

    # Get contacts without real emails
    query = """
        SELECT apollo_id, first_name, last_name, company_name
        FROM apollo_contacts
        WHERE email IS NULL
           OR email LIKE '%not_unlocked%'
           OR email = ''
        ORDER BY company_name
    """
    if limit:
        query += f" LIMIT {limit}"

    contacts = await conn.fetch(query)
    print(f"\nFound {len(contacts)} contacts needing email reveal")

    if dry_run:
        print("\n[DRY RUN - No changes will be made]")
        for c in contacts[:10]:
            print(f"  Would reveal: {c['first_name']} {c['last_name']} at {c['company_name']}")
        await conn.close()
        return

    revealed = 0
    failed = 0
    out_of_credits = False

    async with aiohttp.ClientSession() as session:
        for i, contact in enumerate(contacts, 1):
            if out_of_credits:
                break

            first_name = contact['first_name']
            last_name = contact['last_name']
            company = contact['company_name']
            apollo_id = contact['apollo_id']

            if not first_name or not last_name or not company:
                failed += 1
                continue

            result = await reveal_email(session, first_name, last_name, company)

            if result and result.get('error') == 'OUT_OF_CREDITS':
                print(f"\n⚠️  OUT OF CREDITS after {revealed} reveals")
                out_of_credits = True
                break

            if result and result.get('email'):
                # Update database
                await conn.execute("""
                    UPDATE apollo_contacts
                    SET email = $1,
                        email_status = $2,
                        phone = COALESCE($3, phone),
                        linkedin_url = COALESCE($4, linkedin_url),
                        updated_at = NOW()
                    WHERE apollo_id = $5
                """, result['email'], result.get('email_status'),
                     result.get('phone'), result.get('linkedin_url'), apollo_id)

                revealed += 1
                if revealed <= 20 or revealed % 50 == 0:
                    print(f"  ✓ [{i}/{len(contacts)}] {first_name} {last_name} -> {result['email']}")
            else:
                failed += 1

            # Rate limiting - be gentle with API
            await asyncio.sleep(0.3)

            # Progress report
            if i % 100 == 0:
                print(f"\n  Progress: {revealed} revealed, {failed} failed ({i}/{len(contacts)} processed)")

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN email IS NOT NULL AND email NOT LIKE '%not_unlocked%' THEN 1 END) as with_email
        FROM apollo_contacts
    """)

    print("\n" + "=" * 70)
    print("REVEAL COMPLETE")
    print("=" * 70)
    print(f"Emails revealed this run: {revealed}")
    print(f"Failed/skipped: {failed}")
    print(f"\nDatabase totals:")
    print(f"  Total Apollo contacts: {stats['total']}")
    print(f"  With real email: {stats['with_email']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
