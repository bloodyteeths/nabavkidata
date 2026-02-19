#!/usr/bin/env python3
"""
Prepare OCDS data updates locally as SQL file.
No DB connection needed - just outputs SQL statements.
"""
import gzip
import json
import re
from datetime import datetime
from decimal import Decimal

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except:
        return None

def parse_value(val):
    if val is None:
        return None
    try:
        return str(Decimal(str(val)))
    except:
        return None

def escape_sql(s):
    if s is None:
        return 'NULL'
    s = str(s).replace("'", "''")
    return f"'{s}'"

def extract_uuid(ocid):
    match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', ocid)
    return match.group(1) if match else None

def main():
    print("Loading OCDS data and generating SQL...")

    output_file = open('ocds_updates.sql', 'w')
    output_file.write("-- OCDS data updates\n")
    output_file.write("-- Run this after scraper/embeddings finish\n\n")

    count = 0
    with gzip.open('/Users/tamsar/Downloads/nabavkidata/ocds_data/mk_full.jsonl.gz', 'rt') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                ocid = record.get('ocid', '')
                uuid = extract_uuid(ocid)
                if not uuid:
                    continue

                tender = record.get('tender', {})
                buyer = record.get('buyer', {})

                # Get winner from awards
                winner = None
                actual_value = None
                for award in record.get('awards', []):
                    for supplier in award.get('suppliers', []):
                        winner = supplier.get('name')
                    if award.get('value', {}).get('amount'):
                        actual_value = award['value']['amount']

                # Get CPV
                cpv = None
                for item in tender.get('items', []):
                    cpv = item.get('classification', {}).get('id')
                    if cpv:
                        break

                # Get contact
                contact = {}
                for party in record.get('parties', []):
                    if 'buyer' in party.get('roles', []):
                        contact = party.get('contactPoint', {})
                        break

                # Bids count
                bids = record.get('bids', {}).get('details', [])
                num_bidders = len(bids) if bids else None

                # Bids data
                bids_data = []
                for bid in bids:
                    for tenderer in bid.get('tenderers', []):
                        bids_data.append({
                            'company': tenderer.get('name'),
                            'amount': bid.get('value', {}).get('amount')
                        })

                # Lots
                lots = []
                for lot in tender.get('lots', []):
                    lots.append({
                        'id': lot.get('id'),
                        'title': lot.get('title'),
                        'value': lot.get('value', {}).get('amount')
                    })

                # Items
                items = []
                for item in tender.get('items', []):
                    items.append({
                        'id': item.get('id'),
                        'description': item.get('description'),
                        'quantity': item.get('quantity'),
                        'unit': item.get('unit', {}).get('name'),
                        'cpv': item.get('classification', {}).get('id')
                    })

                # Dates
                pub_date = parse_date(record.get('date'))
                opening_date = parse_date(tender.get('tenderPeriod', {}).get('startDate'))
                closing_date = parse_date(tender.get('tenderPeriod', {}).get('endDate'))

                # Values
                estimated_value = parse_value(tender.get('value', {}).get('amount'))
                actual_value_str = parse_value(actual_value)

                # Build UPDATE statement
                updates = []
                if winner:
                    updates.append(f"winner = COALESCE(winner, {escape_sql(winner[:500])})")
                if actual_value_str:
                    updates.append(f"actual_value_mkd = COALESCE(actual_value_mkd, {actual_value_str})")
                if estimated_value:
                    updates.append(f"estimated_value_mkd = COALESCE(estimated_value_mkd, {estimated_value})")
                if num_bidders:
                    updates.append(f"num_bidders = COALESCE(num_bidders, {num_bidders})")
                if cpv:
                    updates.append(f"cpv_code = COALESCE(cpv_code, {escape_sql(cpv)})")
                if contact.get('name'):
                    updates.append(f"contact_person = COALESCE(contact_person, {escape_sql(contact['name'][:200])})")
                if contact.get('email'):
                    updates.append(f"contact_email = COALESCE(contact_email, {escape_sql(contact['email'][:200])})")
                if contact.get('telephone'):
                    updates.append(f"contact_phone = COALESCE(contact_phone, {escape_sql(contact['telephone'][:50])})")
                if pub_date:
                    updates.append(f"publication_date = COALESCE(publication_date, '{pub_date}')")
                if opening_date:
                    updates.append(f"opening_date = COALESCE(opening_date, '{opening_date}')")
                if closing_date:
                    updates.append(f"closing_date = COALESCE(closing_date, '{closing_date}')")
                if lots:
                    updates.append(f"lots_data = COALESCE(lots_data, {escape_sql(json.dumps(lots))}::jsonb)")
                    updates.append(f"num_lots = COALESCE(num_lots, {len(lots)})")
                    updates.append(f"has_lots = COALESCE(has_lots, {len(lots) > 1})")
                if items:
                    updates.append(f"items_data = COALESCE(items_data, {escape_sql(json.dumps(items))}::jsonb)")
                if bids_data:
                    # Store bids in a field - we may need to create tender_bidders entries
                    pass

                if updates:
                    updates.append("updated_at = NOW()")
                    sql = f"UPDATE tenders SET {', '.join(updates)} WHERE source_url LIKE '%{uuid}';\n"
                    output_file.write(sql)
                    count += 1

                if count % 50000 == 0:
                    print(f"Processed {count} records...")

            except Exception as e:
                pass

    output_file.close()
    print(f"Done! Generated {count} UPDATE statements in ocds_updates.sql")
    print(f"File size: {os.path.getsize('ocds_updates.sql') / 1024 / 1024:.1f} MB")

import os
if __name__ == '__main__':
    main()
