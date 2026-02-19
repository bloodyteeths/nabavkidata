#!/usr/bin/env python3
"""
Bulk import OCDS data - efficient version using temp table and JOIN.
"""
import asyncio
import gzip
import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal

import asyncpg
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
    except:
        return None


def parse_value(val):
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except:
        return None


def extract_dossier_id(url):
    match = re.search(r'/dossie(?:-acpp)?/([a-f0-9-]{36})', url)
    return match.group(1) if match else None


def parse_record(record):
    """Parse OCDS record into our schema."""
    ocid = record.get('ocid', '')
    tender = record.get('tender', {})
    buyer = record.get('buyer', {})

    # Extract UUID from OCID for matching (format: ocds-70d2nz-{uuid})
    # The uuid is a 36 char pattern like 14706e80-d487-39c4-a4c3-d4523552f9ef
    uuid_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', ocid)
    ocid_uuid = uuid_match.group(1) if uuid_match else None

    # Get e-nabavki URL
    enabavki_url = None
    dossier_id = None
    for doc in tender.get('documents', []):
        url = doc.get('url', '')
        if 'e-nabavki.gov.mk' in url and '/dossie' in url:
            enabavki_url = url if url.startswith('http') else f'https://{url}'
            dossier_id = extract_dossier_id(url)
            break

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

    # Get winner from awards
    winner = None
    actual_value = None
    for award in record.get('awards', []):
        for supplier in award.get('suppliers', []):
            winner = supplier.get('name')
        if award.get('value', {}).get('amount'):
            actual_value = award['value']['amount']

    # Bids
    bids = []
    for bid in record.get('bids', {}).get('details', []):
        for tenderer in bid.get('tenderers', []):
            bids.append({
                'company_name': tenderer.get('name'),
                'bid_amount': bid.get('value', {}).get('amount'),
                'lot_id': bid.get('relatedLots', [None])[0]
            })

    # Lots
    lots = []
    for lot in tender.get('lots', []):
        lots.append({
            'lot_number': lot.get('id'),
            'lot_title': lot.get('title'),
            'estimated_value': lot.get('value', {}).get('amount')
        })

    return {
        'ocid_uuid': ocid_uuid,
        'enabavki_url': enabavki_url,
        'dossier_id': dossier_id,
        'title': tender.get('title'),
        'description': tender.get('description'),
        'procuring_entity': buyer.get('name'),
        'category': tender.get('mainProcurementCategory'),
        'procedure_type': tender.get('procurementMethodDetails'),
        'publication_date': parse_date(record.get('date')),
        'opening_date': parse_date(tender.get('tenderPeriod', {}).get('startDate')),
        'closing_date': parse_date(tender.get('tenderPeriod', {}).get('endDate')),
        'estimated_value_mkd': parse_value(tender.get('value', {}).get('amount')),
        'actual_value_mkd': parse_value(actual_value),
        'cpv_code': cpv,
        'evaluation_method': tender.get('awardCriteria'),
        'contact_person': contact.get('name'),
        'contact_email': contact.get('email'),
        'contact_phone': contact.get('telephone'),
        'winner': winner,
        'num_bidders': len(bids),
        'has_lots': len(lots) > 1,
        'num_lots': len(lots),
        'bids_json': json.dumps(bids) if bids else None,
        'lots_json': json.dumps(lots) if lots else None,
    }


async def import_bulk(jsonl_path):
    """Import OCDS data using efficient bulk update."""
    conn = await asyncpg.connect(DATABASE_URL, timeout=120)

    logger.info("Loading OCDS data into memory...")
    open_func = gzip.open if jsonl_path.endswith('.gz') else open

    # Parse all records
    records = []
    with open_func(jsonl_path, 'rt', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                p = parse_record(record)
                if p['ocid_uuid'] and (p['dossier_id'] or p['enabavki_url']):
                    records.append(p)
            except:
                pass
            if (i + 1) % 50000 == 0:
                logger.info(f"Parsed {i+1} records...")

    logger.info(f"Loaded {len(records)} records with URLs")

    # Create temp table
    await conn.execute("DROP TABLE IF EXISTS ocds_temp")
    await conn.execute("""
        CREATE TEMP TABLE ocds_temp (
            ocid_uuid TEXT PRIMARY KEY,
            enabavki_url TEXT,
            dossier_id TEXT,
            description TEXT,
            category TEXT,
            procedure_type TEXT,
            publication_date DATE,
            opening_date DATE,
            closing_date DATE,
            estimated_value DECIMAL(18,2),
            actual_value DECIMAL(18,2),
            cpv_code TEXT,
            evaluation_method TEXT,
            contact_person TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            winner TEXT,
            num_bidders INT,
            has_lots BOOLEAN,
            num_lots INT,
            bids_json JSONB,
            lots_json JSONB
        )
    """)

    # Bulk insert into temp table
    logger.info("Inserting into temp table...")
    await conn.executemany("""
        INSERT INTO ocds_temp VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
        ON CONFLICT (ocid_uuid) DO NOTHING
    """, [
        (r['ocid_uuid'], r['enabavki_url'], r['dossier_id'],
         r['description'][:5000] if r['description'] else None, r['category'],
         r['procedure_type'], r['publication_date'], r['opening_date'], r['closing_date'],
         r['estimated_value_mkd'], r['actual_value_mkd'], r['cpv_code'],
         r['evaluation_method'], r['contact_person'], r['contact_email'], r['contact_phone'],
         r['winner'], r['num_bidders'], r['has_lots'], r['num_lots'],
         r['bids_json'], r['lots_json'])
        for r in records
    ])

    count = await conn.fetchval("SELECT COUNT(*) FROM ocds_temp")
    logger.info(f"Temp table has {count} records")

    # First, get tender_ids for opentender records
    logger.info("Finding matching tenders (this may take a few minutes)...")

    # Create index on source_url substring
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tenders_source_uuid
        ON tenders (SUBSTRING(source_url FROM '[a-f0-9-]{36}$'))
        WHERE source_url LIKE '%opentender%'
    """)

    # Bulk update
    logger.info("Running bulk update...")
    result = await conn.execute("""
        UPDATE tenders t SET
            source_url = COALESCE(o.enabavki_url, t.source_url),
            dossier_id = COALESCE(o.dossier_id, t.dossier_id),
            description = COALESCE(o.description, t.description),
            category = COALESCE(o.category, t.category),
            procedure_type = COALESCE(o.procedure_type, t.procedure_type),
            publication_date = COALESCE(o.publication_date, t.publication_date),
            opening_date = COALESCE(o.opening_date, t.opening_date),
            closing_date = COALESCE(o.closing_date, t.closing_date),
            estimated_value_mkd = COALESCE(o.estimated_value, t.estimated_value_mkd),
            actual_value_mkd = COALESCE(o.actual_value, t.actual_value_mkd),
            cpv_code = COALESCE(o.cpv_code, t.cpv_code),
            evaluation_method = COALESCE(o.evaluation_method, t.evaluation_method),
            contact_person = COALESCE(o.contact_person, t.contact_person),
            contact_email = COALESCE(o.contact_email, t.contact_email),
            contact_phone = COALESCE(o.contact_phone, t.contact_phone),
            winner = COALESCE(o.winner, t.winner),
            num_bidders = COALESCE(o.num_bidders, t.num_bidders),
            has_lots = COALESCE(o.has_lots, t.has_lots),
            num_lots = COALESCE(o.num_lots, t.num_lots),
            items_data = COALESCE(o.bids_json, t.items_data),
            lots_data = COALESCE(o.lots_json, t.lots_data),
            updated_at = NOW()
        FROM ocds_temp o
        WHERE t.source_url LIKE '%opentender%'
          AND SUBSTRING(t.source_url FROM '[a-f0-9-]{36}$') = o.ocid_uuid
    """)

    logger.info(f"Update result: {result}")

    # Check results
    updated = await conn.fetchval("SELECT COUNT(*) FROM tenders WHERE dossier_id IS NOT NULL")
    logger.info(f"Tenders with dossier_id: {updated}")

    await conn.close()
    logger.info("Done!")


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else '/home/ubuntu/nabavkidata/ocds_data/mk_full.jsonl.gz'
    asyncio.run(import_bulk(path))
