#!/usr/bin/env python3
"""
Update opentender tenders with correct e-nabavki URLs from OCDS mapping.
Maps OCID UUIDs to tender IDs and updates source_url and dossier_id.
"""
import asyncio
import csv
import os
import re
import asyncpg

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)

OCDS_URLS_FILE = '/home/ubuntu/nabavkidata/ocds_data/ocds_urls.csv'


async def main():
    print("Loading OCDS URL mappings...")

    # Load mappings: last 12 chars of UUID -> (enabavki_url, dossier_id)
    mappings = {}
    with open(OCDS_URLS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ocid_uuid = row['ocid_uuid']
            # Get last 12 chars (matching tender_id suffix)
            uuid_suffix = ocid_uuid.replace('-', '')[-12:]
            mappings[uuid_suffix] = {
                'source_url': row['enabavki_url'],
                'dossier_id': row['dossier_id']
            }

    print(f"Loaded {len(mappings)} mappings")

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Find opentender tenders
        rows = await conn.fetch("""
            SELECT tender_id, source_url
            FROM tenders
            WHERE tender_id LIKE 'OT-%'
            AND (source_url LIKE '%opentender%' OR source_url IS NULL OR dossier_id IS NULL)
        """)

        print(f"Found {len(rows)} opentender tenders to check")

        updated = 0
        not_found = 0

        for row in rows:
            tender_id = row['tender_id']
            # Extract UUID suffix from tender_id (e.g., "OT-91c66638498a/2020" -> "91c66638498a")
            match = re.search(r'OT-([a-f0-9]{12})/', tender_id)
            if not match:
                continue

            uuid_suffix = match.group(1)

            if uuid_suffix in mappings:
                mapping = mappings[uuid_suffix]
                await conn.execute("""
                    UPDATE tenders
                    SET source_url = $1, dossier_id = $2
                    WHERE tender_id = $3
                """, mapping['source_url'], mapping['dossier_id'], tender_id)
                updated += 1
                if updated % 1000 == 0:
                    print(f"  Updated {updated} tenders...")
            else:
                not_found += 1

        print(f"\nDone!")
        print(f"  Updated: {updated}")
        print(f"  No mapping found: {not_found}")

    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
