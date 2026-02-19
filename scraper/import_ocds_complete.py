#!/usr/bin/env python3
"""
Import ALL OCDS data into database - comprehensive version.
Imports: URLs, bids, lots, items, awards, parties, values, dates.
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

    # Extract UUID from OCID for matching
    ocid_uuid = ocid.split('-')[-1] if ocid else None

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
        'contract_duration': f"{tender.get('contractPeriod', {}).get('durationInDays', '')} days" if tender.get('contractPeriod', {}).get('durationInDays') else None,
        'contact_person': contact.get('name'),
        'contact_email': contact.get('email'),
        'contact_phone': contact.get('telephone'),
        'winner': winner,
        'num_bidders': len(bids),
        'has_lots': len(lots) > 1,
        'num_lots': len(lots),
        'bids': bids,
        'lots': lots,
        'items': items,
    }


async def import_all(jsonl_path):
    """Import all OCDS data."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, command_timeout=120, timeout=60)

    stats = {'processed': 0, 'updated': 0, 'bidders': 0, 'lots': 0}

    open_func = gzip.open if jsonl_path.endswith('.gz') else open

    with open_func(jsonl_path, 'rt', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            p = parse_record(record)
            stats['processed'] += 1

            if not p['ocid_uuid']:
                continue

            async with pool.acquire() as conn:
                # Find matching tender
                tender_id = await conn.fetchval("""
                    SELECT tender_id FROM tenders
                    WHERE source_url LIKE '%opentender%'
                      AND source_url LIKE $1
                    LIMIT 1
                """, f"%{p['ocid_uuid']}%")

                if not tender_id:
                    continue

                # Update tender with ALL OCDS data
                await conn.execute("""
                    UPDATE tenders SET
                        source_url = COALESCE($2, source_url),
                        dossier_id = COALESCE($3, dossier_id),
                        description = COALESCE($4, description),
                        category = COALESCE($5, category),
                        procedure_type = COALESCE($6, procedure_type),
                        publication_date = COALESCE($7, publication_date),
                        opening_date = COALESCE($8, opening_date),
                        closing_date = COALESCE($9, closing_date),
                        estimated_value_mkd = COALESCE($10, estimated_value_mkd),
                        actual_value_mkd = COALESCE($11, actual_value_mkd),
                        cpv_code = COALESCE($12, cpv_code),
                        evaluation_method = COALESCE($13, evaluation_method),
                        contract_duration = COALESCE($14, contract_duration),
                        contact_person = COALESCE($15, contact_person),
                        contact_email = COALESCE($16, contact_email),
                        contact_phone = COALESCE($17, contact_phone),
                        winner = COALESCE($18, winner),
                        num_bidders = COALESCE($19, num_bidders),
                        has_lots = COALESCE($20, has_lots),
                        num_lots = COALESCE($21, num_lots),
                        items_data = COALESCE($22::jsonb, items_data),
                        lots_data = COALESCE($23::jsonb, lots_data),
                        updated_at = NOW()
                    WHERE tender_id = $1
                """,
                    tender_id,
                    p['enabavki_url'],
                    p['dossier_id'],
                    p['description'] if p['description'] != 'null' else None,
                    p['category'],
                    p['procedure_type'],
                    p['publication_date'],
                    p['opening_date'],
                    p['closing_date'],
                    p['estimated_value_mkd'],
                    p['actual_value_mkd'],
                    p['cpv_code'],
                    p['evaluation_method'],
                    p['contract_duration'],
                    p['contact_person'],
                    p['contact_email'],
                    p['contact_phone'],
                    p['winner'],
                    p['num_bidders'],
                    p['has_lots'],
                    p['num_lots'],
                    json.dumps(p['items']) if p['items'] else None,
                    json.dumps(p['lots']) if p['lots'] else None,
                )
                stats['updated'] += 1

                # Insert lots
                for lot in p['lots']:
                    try:
                        await conn.execute("""
                            INSERT INTO tender_lots (tender_id, lot_number, lot_title, estimated_value_mkd)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT DO NOTHING
                        """, tender_id, lot['lot_number'], lot['lot_title'], parse_value(lot['estimated_value']))
                        stats['lots'] += 1
                    except:
                        pass

                # Insert bidders
                for bid in p['bids']:
                    if not bid.get('company_name'):
                        continue
                    try:
                        await conn.execute("""
                            INSERT INTO tender_bidders (tender_id, company_name, bid_amount_mkd)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (tender_id, company_name) DO UPDATE SET bid_amount_mkd = EXCLUDED.bid_amount_mkd
                        """, tender_id, bid['company_name'][:500], parse_value(bid['bid_amount']))
                        stats['bidders'] += 1
                    except:
                        pass

            if stats['updated'] % 1000 == 0:
                logger.info(f"Updated {stats['updated']}/{stats['processed']} tenders, {stats['lots']} lots, {stats['bidders']} bidders")

    await pool.close()
    logger.info(f"=== DONE: {stats['updated']} tenders, {stats['lots']} lots, {stats['bidders']} bidders ===")


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else '/Users/tamsar/Downloads/nabavkidata/ocds_data/mk_full.jsonl.gz'
    asyncio.run(import_all(path))
