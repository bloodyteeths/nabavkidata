#!/usr/bin/env python3
"""
Fast parallel email reveal for Apollo contacts.
Uses concurrent requests for speed.
"""
import os
import sys
import asyncio
import asyncpg
import aiohttp
import json
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "M5Ker5RzIA9flD0s_IONEA")
APOLLO_BASE_URL = "https://api.apollo.io/v1"

CONCURRENCY = 10  # Parallel requests
revealed_count = 0
failed_count = 0
out_of_credits = False


async def reveal_and_update(session, conn, contact):
    """Reveal email and update database"""
    global revealed_count, failed_count, out_of_credits

    if out_of_credits:
        return

    first_name = contact['first_name']
    last_name = contact['last_name']
    company = contact['company_name']
    apollo_id = contact['apollo_id']

    if not first_name or not last_name or not company:
        failed_count += 1
        return

    url = f"{APOLLO_BASE_URL}/people/match"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_API_KEY
    }
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": company,
        "reveal_personal_emails": True
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                person = data.get('person', {})
                email = person.get('email')

                if email and '@' in email and 'not_unlocked' not in email.lower():
                    await conn.execute("""
                        UPDATE apollo_contacts
                        SET email = $1, email_status = $2, updated_at = NOW()
                        WHERE apollo_id = $3
                    """, email, person.get('email_status'), apollo_id)

                    revealed_count += 1
                    if revealed_count <= 30 or revealed_count % 100 == 0:
                        print(f"  ✓ {first_name} {last_name} -> {email}")
                else:
                    failed_count += 1
            elif resp.status in (403, 429):
                text = await resp.text()
                if 'credit' in text.lower():
                    out_of_credits = True
                    print(f"\n⚠️  OUT OF CREDITS")
                failed_count += 1
            else:
                failed_count += 1
    except Exception as e:
        failed_count += 1


async def main():
    global revealed_count, failed_count, out_of_credits

    print("=" * 70)
    print("FAST APOLLO EMAIL REVEAL (10 concurrent)")
    print("=" * 70)

    conn = await asyncpg.connect(DATABASE_URL)

    # Get contacts needing reveal
    contacts = await conn.fetch("""
        SELECT apollo_id, first_name, last_name, company_name
        FROM apollo_contacts
        WHERE email IS NULL OR email LIKE '%not_unlocked%' OR email = ''
        ORDER BY company_name
    """)

    print(f"\nFound {len(contacts)} contacts needing email reveal")
    print(f"Starting parallel reveal (10 at a time)...\n")

    start_time = datetime.now()

    connector = aiohttp.TCPConnector(limit=CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Process in batches
        batch_size = 50
        for i in range(0, len(contacts), batch_size):
            if out_of_credits:
                break

            batch = contacts[i:i+batch_size]
            tasks = [reveal_and_update(session, conn, c) for c in batch]
            await asyncio.gather(*tasks)

            # Progress
            processed = min(i + batch_size, len(contacts))
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = revealed_count / elapsed if elapsed > 0 else 0
            print(f"\n  Progress: {processed}/{len(contacts)} processed, {revealed_count} revealed ({rate:.1f}/sec)")

            await asyncio.sleep(0.5)  # Brief pause between batches

    # Final stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN email IS NOT NULL AND email NOT LIKE '%not_unlocked%' THEN 1 END) as with_email
        FROM apollo_contacts
    """)

    elapsed = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 70)
    print("REVEAL COMPLETE")
    print("=" * 70)
    print(f"Time: {elapsed:.0f} seconds")
    print(f"Revealed this run: {revealed_count}")
    print(f"Failed/no email: {failed_count}")
    print(f"\nDatabase totals:")
    print(f"  Total Apollo contacts: {stats['total']}")
    print(f"  With real email: {stats['with_email']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
