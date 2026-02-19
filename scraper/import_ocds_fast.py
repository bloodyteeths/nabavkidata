#!/usr/bin/env python3
"""
Fast OCDS import - batched updates to avoid blocking.
Updates in chunks of 1000 records.
"""
import gzip
import json
import os
import re
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv('DATABASE_URL')

def extract_uuid(ocid):
    """Extract UUID from OCID like ocds-70d2nz-{uuid}"""
    match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', ocid)
    return match.group(1) if match else None

def extract_dossier_id(url):
    """Extract dossier ID from e-nabavki URL"""
    match = re.search(r'/dossie(?:-acpp)?/([a-f0-9-]{36})', url)
    return match.group(1) if match else None

def main():
    print("Loading OCDS data...")
    records = []

    with gzip.open('/Users/tamsar/Downloads/nabavkidata/ocds_data/mk_full.jsonl.gz', 'rt') as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                ocid = record.get('ocid', '')
                uuid = extract_uuid(ocid)
                if not uuid:
                    continue

                # Find e-nabavki URL
                tender = record.get('tender', {})
                for doc in tender.get('documents', []):
                    url = doc.get('url', '')
                    if 'e-nabavki.gov.mk' in url and '/dossie' in url:
                        dossier_id = extract_dossier_id(url)
                        if dossier_id:
                            enabavki_url = url if url.startswith('http') else f'https://{url}'
                            records.append((uuid, dossier_id, enabavki_url))
                            break
            except:
                pass

            if (i + 1) % 50000 == 0:
                print(f"Parsed {i+1} records, found {len(records)} with URLs")

    print(f"Total records with e-nabavki URLs: {len(records)}")

    # Connect to DB
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # First, create a mapping table
    print("Creating mapping table...")
    cur.execute("DROP TABLE IF EXISTS ocds_mapping")
    cur.execute("""
        CREATE TABLE ocds_mapping (
            uuid TEXT PRIMARY KEY,
            dossier_id TEXT,
            enabavki_url TEXT
        )
    """)
    conn.commit()

    # Bulk insert mappings
    print("Inserting mappings...")
    batch_size = 5000
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        execute_batch(cur, """
            INSERT INTO ocds_mapping (uuid, dossier_id, enabavki_url)
            VALUES (%s, %s, %s)
            ON CONFLICT (uuid) DO NOTHING
        """, batch)
        conn.commit()
        print(f"Inserted {min(i+batch_size, len(records))}/{len(records)}")

    # Create index
    print("Creating index...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocds_mapping_uuid ON ocds_mapping(uuid)")
    conn.commit()

    # Now update tenders in batches
    print("Updating tenders in batches...")
    cur.execute("""
        SELECT COUNT(*) FROM tenders
        WHERE source_url LIKE '%opentender%'
        AND dossier_id IS NULL
    """)
    total = cur.fetchone()[0]
    print(f"Tenders to update: {total}")

    # Update in batches using LIMIT/OFFSET alternative
    updated = 0
    batch_size = 2000

    while True:
        cur.execute("""
            WITH to_update AS (
                SELECT t.tender_id, m.dossier_id, m.enabavki_url
                FROM tenders t
                JOIN ocds_mapping m ON SUBSTRING(t.source_url FROM '[a-f0-9-]{36}$') = m.uuid
                WHERE t.source_url LIKE '%%opentender%%'
                AND t.dossier_id IS NULL
                LIMIT %s
            )
            UPDATE tenders t SET
                dossier_id = u.dossier_id,
                source_url = u.enabavki_url,
                updated_at = NOW()
            FROM to_update u
            WHERE t.tender_id = u.tender_id
        """, (batch_size,))

        rows = cur.rowcount
        conn.commit()
        updated += rows
        print(f"Updated {updated} tenders...")

        if rows == 0:
            break

    print(f"Done! Total updated: {updated}")

    # Cleanup
    cur.execute("DROP TABLE IF EXISTS ocds_mapping")
    conn.commit()

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
