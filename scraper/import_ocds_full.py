#!/usr/bin/env python3
"""
Import ALL OCDS data into our database.
Updates existing OpenTender records with rich data from OCDS.
"""
import argparse
import asyncio
import gzip
import json
import logging
import os
import re
from datetime import datetime

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


def parse_date(date_str: str):
    """Parse ISO date string to date."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
    except:
        return None


def extract_dossier_id(url: str) -> str:
    """Extract UUID from e-nabavki URL."""
    match = re.search(r'/dossie(?:-acpp)?/([a-f0-9-]{36})', url)
    return match.group(1) if match else None


def parse_ocds_record(record: dict) -> dict:
    """Extract all relevant fields from OCDS record."""
    ocid = record.get('ocid', '')
    tender = record.get('tender', {})
    buyer = record.get('buyer', {})

    # Get e-nabavki URL
    enabavki_url = None
    dossier_id = None
    for doc in tender.get('documents', []):
        url = doc.get('url', '')
        if 'e-nabavki.gov.mk' in url and '/dossie' in url:
            enabavki_url = url if url.startswith('http') else f'https://{url}'
            dossier_id = extract_dossier_id(url)
            break

    # Get CPV from items
    cpv_code = None
    for item in tender.get('items', []):
        cpv = item.get('classification', {}).get('id')
        if cpv:
            cpv_code = cpv
            break

    # Get buyer contact
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

    # Get bids
    bids = []
    for bid in record.get('bids', {}).get('details', []):
        for tenderer in bid.get('tenderers', []):
            bids.append({
                'company_name': tenderer.get('name'),
                'bid_amount': bid.get('value', {}).get('amount'),
                'lot_id': bid.get('relatedLots', [None])[0]
            })

    # Get lots
    lots = []
    for lot in tender.get('lots', []):
        lots.append({
            'lot_number': lot.get('id'),
            'lot_title': lot.get('title'),
            'estimated_value': lot.get('value', {}).get('amount')
        })

    # Get items
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
        'ocid': ocid,
        'tender_id_ot': f"OT-{ocid.split('-')[-1][:12]}/{str(parse_date(record.get('date')))[0:4] if parse_date(record.get('date')) else '2020'}" if ocid else None,
        'enabavki_url': enabavki_url,
        'dossier_id': dossier_id,
        'title': tender.get('title'),
        'description': tender.get('description'),
        'procuring_entity': buyer.get('name'),
        'estimated_value_mkd': tender.get('value', {}).get('amount'),
        'actual_value_mkd': actual_value,
        'cpv_code': cpv_code,
        'opening_date': parse_date(tender.get('tenderPeriod', {}).get('startDate')),
        'closing_date': parse_date(tender.get('tenderPeriod', {}).get('endDate')),
        'publication_date': parse_date(record.get('date')),
        'procedure_type': tender.get('procurementMethodDetails'),
        'category': tender.get('mainProcurementCategory'),
        'evaluation_method': tender.get('awardCriteria'),
        'contract_duration': str(tender.get('contractPeriod', {}).get('durationInDays', '')) + ' days' if tender.get('contractPeriod', {}).get('durationInDays') else None,
        'contact_person': contact.get('name'),
        'contact_email': contact.get('email'),
        'contact_phone': contact.get('telephone'),
        'winner': winner,
        'num_bidders': len(bids),
        'bids': bids,
        'lots': lots,
        'items': items,
        'has_lots': len(lots) > 1,
        'num_lots': len(lots),
    }


async def import_ocds_data(jsonl_path: str):
    """Process OCDS file and update database."""
    # Use connection pool instead of single connection
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=5,
        command_timeout=60,
        timeout=60
    )

    stats = {
        'records': 0,
        'updated': 0,
        'lots_added': 0,
        'bidders_added': 0,
    }

    open_func = gzip.open if jsonl_path.endswith('.gz') else open

    with open_func(jsonl_path, 'rt', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            p = parse_ocds_record(record)
            stats['records'] += 1

            # Find the matching OpenTender record by OCID in source_url
            ocid_part = p['ocid'].split('-')[-1] if p['ocid'] else None
            if not ocid_part:
                continue

            async with pool.acquire() as conn:
                tender_id = await conn.fetchval("""
                    SELECT tender_id FROM tenders
                    WHERE source_url LIKE $1
                    LIMIT 1
                """, f"%{ocid_part}%")

                if not tender_id:
                    continue

                # Update tender with ALL OCDS data
                await conn.execute("""
                    UPDATE tenders SET
                        source_url = COALESCE($2, source_url),
                        dossier_id = COALESCE($3, dossier_id),
                        description = COALESCE($4, description),
                        estimated_value_mkd = COALESCE($5, estimated_value_mkd),
                        actual_value_mkd = COALESCE($6, actual_value_mkd),
                        cpv_code = COALESCE($7, cpv_code),
                        opening_date = COALESCE($8, opening_date),
                        closing_date = COALESCE($9, closing_date),
                        publication_date = COALESCE($10, publication_date),
                        procedure_type = COALESCE($11, procedure_type),
                        category = COALESCE($12, category),
                        evaluation_method = COALESCE($13, evaluation_method),
                        contract_duration = COALESCE($14, contract_duration),
                        contact_person = COALESCE($15, contact_person),
                        contact_email = COALESCE($16, contact_email),
                        contact_phone = COALESCE($17, contact_phone),
                        winner = COALESCE($18, winner),
                        num_bidders = COALESCE($19, num_bidders),
                        has_lots = COALESCE($20, has_lots),
                        num_lots = COALESCE($21, num_lots),
                        items_data = $22::jsonb,
                        lots_data = $23::jsonb,
                        updated_at = NOW()
                    WHERE tender_id = $1
                """,
                    tender_id,
                    p['enabavki_url'],
                    p['dossier_id'],
                    p['description'] if p['description'] != 'null' else None,
                    p['estimated_value_mkd'],
                    p['actual_value_mkd'],
                    p['cpv_code'],
                    p['opening_date'],
                    p['closing_date'],
                    p['publication_date'],
                    p['procedure_type'],
                    p['category'],
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
                        """, tender_id, lot['lot_number'], lot['lot_title'], lot['estimated_value'])
                        stats['lots_added'] += 1
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
                        """, tender_id, bid['company_name'][:500], bid['bid_amount'])
                        stats['bidders_added'] += 1
                    except:
                        pass

            if stats['updated'] % 1000 == 0:
                logger.info(f"Updated {stats['updated']}/{stats['records']} tenders, {stats['lots_added']} lots, {stats['bidders_added']} bidders")

    await pool.close()
    logger.info(f"=== DONE: {stats['updated']} tenders, {stats['lots_added']} lots, {stats['bidders_added']} bidders ===")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('jsonl_path')
    args = parser.parse_args()
    asyncio.run(import_ocds_data(args.jsonl_path))
