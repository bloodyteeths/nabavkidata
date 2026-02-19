#!/usr/bin/env python3
"""
Continue OCDS import from where we left off.
"""
import gzip
import json
import re
import psycopg2
from psycopg2.extras import execute_batch

DATABASE_URL = os.getenv('DATABASE_URL')

def extract_uuid(ocid):
    match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', ocid)
    return match.group(1) if match else None

def extract_dossier_id(url):
    match = re.search(r'/dossie(?:-acpp)?/([a-f0-9-]{36})', url)
    return match.group(1) if match else None

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Check current count
    cur.execute("SELECT COUNT(*) FROM ocds_mapping")
    current = cur.fetchone()[0]
    print(f"Current mappings: {current}")

    # Get existing UUIDs
    print("Loading existing UUIDs...")
    cur.execute("SELECT uuid FROM ocds_mapping")
    existing = set(row[0] for row in cur.fetchall())
    print(f"Existing UUIDs: {len(existing)}")

    # Load remaining records
    print("Loading remaining OCDS data...")
    records = []
    with gzip.open('/Users/tamsar/Downloads/nabavkidata/ocds_data/mk_full.jsonl.gz', 'rt') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                ocid = record.get('ocid', '')
                uuid = extract_uuid(ocid)
                if not uuid or uuid in existing:
                    continue

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

    print(f"New records to insert: {len(records)}")

    # Insert in small batches
    batch_size = 1000
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        execute_batch(cur, """
            INSERT INTO ocds_mapping (uuid, dossier_id, enabavki_url)
            VALUES (%s, %s, %s)
            ON CONFLICT (uuid) DO NOTHING
        """, batch)
        conn.commit()
        print(f"Inserted {min(i+batch_size, len(records))}/{len(records)}")

    cur.execute("SELECT COUNT(*) FROM ocds_mapping")
    total = cur.fetchone()[0]
    print(f"Total mappings now: {total}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
