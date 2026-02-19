#!/usr/bin/env python3
"""
Import OCDS data into our database.
- Adds e-nabavki URLs to OpenTender records for scraping
- Imports bids into tender_bidders
- Imports lots into tender_lots
"""
import argparse
import asyncio
import gzip
import json
import logging
import os
import re

import asyncpg
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


def extract_dossier_id(url: str) -> str:
    """Extract UUID from e-nabavki URL."""
    match = re.search(r'/dossie(?:-acpp)?/([a-f0-9-]{36})', url)
    return match.group(1) if match else None


def parse_ocds_record(record: dict) -> dict:
    """Extract relevant fields from OCDS record."""
    ocid = record.get('ocid', '')
    tender = record.get('tender', {})

    # Get e-nabavki URL from documents
    enabavki_url = None
    dossier_id = None
    for doc in tender.get('documents', []):
        url = doc.get('url', '')
        if 'e-nabavki.gov.mk' in url and '/dossie' in url:
            enabavki_url = url if url.startswith('http') else f'https://{url}'
            dossier_id = extract_dossier_id(url)
            break

    # Get bids
    bids_data = []
    for bid in record.get('bids', {}).get('details', []):
        for tenderer in bid.get('tenderers', []):
            bids_data.append({
                'company_name': tenderer.get('name'),
                'bid_amount_mkd': bid.get('value', {}).get('amount'),
                'lot_number': bid.get('relatedLots', [None])[0]
            })

    # Get lots
    lots_data = []
    for lot in tender.get('lots', []):
        lots_data.append({
            'lot_number': lot.get('id'),
            'lot_title': lot.get('title'),
            'estimated_value_mkd': lot.get('value', {}).get('amount')
        })

    return {
        'ocid': ocid,
        'ocid_uuid': ocid.split('-', 2)[-1] if ocid else None,
        'enabavki_url': enabavki_url,
        'dossier_id': dossier_id,
        'title': tender.get('title'),
        'description': tender.get('description'),
        'estimated_value': tender.get('value', {}).get('amount'),
        'buyer_name': record.get('buyer', {}).get('name'),
        'bids': bids_data,
        'lots': lots_data,
    }


async def import_ocds_data(jsonl_path: str, batch_size: int = 500):
    """Process OCDS file and update database."""
    conn = await asyncpg.connect(DATABASE_URL)

    # Count records
    total_ot = await conn.fetchval("SELECT COUNT(*) FROM tenders WHERE source_url LIKE '%opentender%'")
    ot_missing_dossier = await conn.fetchval("""
        SELECT COUNT(*) FROM tenders
        WHERE source_url LIKE '%opentender%' AND (dossier_id IS NULL OR dossier_id = '')
    """)
    logger.info(f"OpenTender tenders: {total_ot}, missing dossier_id: {ot_missing_dossier}")

    # Process OCDS
    stats = {
        'records': 0,
        'with_url': 0,
        'tenders_updated': 0,
        'lots_inserted': 0,
        'bidders_inserted': 0,
    }

    open_func = gzip.open if jsonl_path.endswith('.gz') else open

    with open_func(jsonl_path, 'rt', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            parsed = parse_ocds_record(record)
            stats['records'] += 1

            if not parsed['enabavki_url'] or not parsed['ocid_uuid']:
                continue

            stats['with_url'] += 1

            # Find matching OpenTender record
            tender_id = await conn.fetchval("""
                SELECT tender_id FROM tenders
                WHERE source_url LIKE '%opentender%'
                  AND source_url LIKE $1
                  AND (dossier_id IS NULL OR dossier_id = '')
                LIMIT 1
            """, f"%{parsed['ocid_uuid']}%")

            if not tender_id:
                continue

            # Update tender with e-nabavki URL
            await conn.execute("""
                UPDATE tenders
                SET source_url = $1,
                    dossier_id = $2,
                    raw_data_json = COALESCE(raw_data_json, '{}'::jsonb) || $3::jsonb
                WHERE tender_id = $4
            """,
                parsed['enabavki_url'],
                parsed['dossier_id'],
                json.dumps({'ocds_data': True}),
                tender_id
            )
            stats['tenders_updated'] += 1

            # Insert lots
            for lot in parsed['lots']:
                try:
                    await conn.execute("""
                        INSERT INTO tender_lots (tender_id, lot_number, lot_title, estimated_value_mkd)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT DO NOTHING
                    """, tender_id, lot['lot_number'], lot['lot_title'], lot['estimated_value_mkd'])
                    stats['lots_inserted'] += 1
                except Exception:
                    pass

            # Insert bidders
            for bid in parsed['bids']:
                if not bid['company_name']:
                    continue
                try:
                    await conn.execute("""
                        INSERT INTO tender_bidders (tender_id, company_name, bid_amount_mkd)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (tender_id, company_name) DO UPDATE SET bid_amount_mkd = $3
                    """, tender_id, bid['company_name'][:500], bid['bid_amount_mkd'])
                    stats['bidders_inserted'] += 1
                except Exception:
                    pass

            if stats['tenders_updated'] % 500 == 0:
                logger.info(f"Progress: {stats['records']} records, {stats['tenders_updated']} tenders updated")

    await conn.close()

    logger.info("=== IMPORT COMPLETE ===")
    for k, v in stats.items():
        logger.info(f"  {k}: {v}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import OCDS data')
    parser.add_argument('jsonl_path', help='Path to OCDS JSONL file')
    parser.add_argument('--batch-size', type=int, default=500)
    args = parser.parse_args()

    asyncio.run(import_ocds_data(args.jsonl_path, args.batch_size))
