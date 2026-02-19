#!/usr/bin/env python3
"""Extract e-nabavki URLs from OCDS data and save as CSV for bulk import."""
import gzip
import json
import re
import csv

def extract_dossier_id(url: str) -> str:
    match = re.search(r'/dossie(?:-acpp)?/([a-f0-9-]{36})', url)
    return match.group(1) if match else None

rows = []
with gzip.open('mk_full.jsonl.gz', 'rt', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if not line.strip():
            continue
        record = json.loads(line)
        ocid = record.get('ocid', '')

        # Extract UUID from OCID: ocds-70d2nz-UUID
        if not ocid:
            continue
        ocid_uuid = ocid.split('-', 2)[-1] if '-' in ocid else None
        if not ocid_uuid:
            continue

        # Get e-nabavki URL
        tender = record.get('tender', {})
        for doc in tender.get('documents', []):
            url = doc.get('url', '')
            if 'e-nabavki.gov.mk' in url and '/dossie' in url:
                enabavki_url = url if url.startswith('http') else f'https://{url}'
                dossier_id = extract_dossier_id(url)
                rows.append({
                    'ocid_uuid': ocid_uuid,
                    'enabavki_url': enabavki_url,
                    'dossier_id': dossier_id
                })
                break

        if (i + 1) % 50000 == 0:
            print(f"Processed {i + 1} records, found {len(rows)} URLs")

print(f"Total: {len(rows)} URLs found")

with open('ocds_urls.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['ocid_uuid', 'enabavki_url', 'dossier_id'])
    writer.writeheader()
    writer.writerows(rows)

print(f"Saved to ocds_urls.csv")
