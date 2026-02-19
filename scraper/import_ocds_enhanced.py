#!/usr/bin/env python3
"""
Enhanced OCDS Import - Phase 1 Fix
Uses dossier_id matching for better coverage.
Extracts ALL awards and bidders from OCDS data.

Expected improvement: 5% → 50% actual_value, 4% → 60% bidders
"""
import argparse
import gzip
import json
import logging
import os
import re
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

# MKD to EUR rate (for converting OCDS EUR values)
EUR_TO_MKD = 61.5


def parse_date(date_str: str) -> Optional[str]:
    """Parse ISO date to YYYY-MM-DD."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except:
        return None


def extract_uuid_from_ocid(ocid: str) -> Optional[str]:
    """Extract UUID from OCID like ocds-70d2nz-ce3b436a-d5a2-3f9c-a4d1-3b97de73a37e."""
    if not ocid:
        return None
    match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', ocid)
    return match.group(1) if match else None


def convert_value(amount: Any, currency: str = 'MKD') -> Optional[float]:
    """Convert value to MKD."""
    if amount is None:
        return None
    try:
        val = float(amount)
        if currency == 'EUR':
            val *= EUR_TO_MKD
        return val
    except:
        return None


def parse_ocds_record(record: dict) -> Dict[str, Any]:
    """Extract all data from OCDS record."""
    ocid = record.get('ocid', '')
    uuid = extract_uuid_from_ocid(ocid)
    tender = record.get('tender', {})
    buyer = record.get('buyer', {})

    # Get tender value
    tender_value = tender.get('value', {})
    estimated_value = convert_value(
        tender_value.get('amount'),
        tender_value.get('currency', 'MKD')
    )

    # Get ALL awards - find the one with value
    awards = record.get('awards', [])
    actual_value = None
    winner = None
    all_winners = []

    for award in awards:
        # Get value from award
        award_value = award.get('value', {})
        if award_value.get('amount'):
            val = convert_value(award_value['amount'], award_value.get('currency', 'MKD'))
            if val and (actual_value is None or val > actual_value):
                actual_value = val

        # Get suppliers (winners)
        for supplier in award.get('suppliers', []):
            name = supplier.get('name')
            if name:
                all_winners.append(name)
                if not winner:
                    winner = name

    # Get ALL bidders from bids.details
    bids_data = record.get('bids', {}).get('details', [])
    bidders = []

    for bid in bids_data:
        bid_value = bid.get('value', {})
        bid_amount = convert_value(bid_value.get('amount'), bid_value.get('currency', 'MKD'))

        for tenderer in bid.get('tenderers', []):
            name = tenderer.get('name')
            if name:
                is_winner = name in all_winners
                bidders.append({
                    'company_name': name[:500],
                    'bid_amount': bid_amount,
                    'is_winner': is_winner,
                    'lot_id': bid.get('relatedLots', [None])[0]
                })

    # If no bids but we have awards, create bidder entries from awards
    if not bidders and awards:
        for award in awards:
            award_value = award.get('value', {})
            bid_amount = convert_value(award_value.get('amount'), award_value.get('currency', 'MKD'))
            for supplier in award.get('suppliers', []):
                name = supplier.get('name')
                if name:
                    bidders.append({
                        'company_name': name[:500],
                        'bid_amount': bid_amount,
                        'is_winner': True,
                        'lot_id': None
                    })

    # Get CPV
    cpv_code = None
    for item in tender.get('items', []):
        cpv = item.get('classification', {}).get('id')
        if cpv:
            cpv_code = cpv
            break

    # Get contact from parties
    contact = {}
    for party in record.get('parties', []):
        if 'buyer' in party.get('roles', []):
            contact = party.get('contactPoint', {})
            break

    # Get lots
    lots = []
    for lot in tender.get('lots', []):
        lot_value = lot.get('value', {})
        lots.append({
            'lot_number': lot.get('id'),
            'lot_title': lot.get('title'),
            'estimated_value': convert_value(lot_value.get('amount'), lot_value.get('currency', 'MKD'))
        })

    return {
        'uuid': uuid,
        'ocid': ocid,
        'title': tender.get('title'),
        'description': tender.get('description'),
        'procuring_entity': buyer.get('name'),
        'estimated_value_mkd': estimated_value,
        'actual_value_mkd': actual_value,
        'cpv_code': cpv_code,
        'opening_date': parse_date(tender.get('tenderPeriod', {}).get('startDate')),
        'closing_date': parse_date(tender.get('tenderPeriod', {}).get('endDate')),
        'publication_date': parse_date(record.get('date')),
        'procedure_type': tender.get('procurementMethodDetails'),
        'contact_person': contact.get('name'),
        'contact_email': contact.get('email'),
        'contact_phone': contact.get('telephone'),
        'winner': winner,
        'num_bidders': len(bidders),
        'bidders': bidders,
        'lots': lots,
        'has_lots': len(lots) > 1,
        'num_lots': len(lots) if lots else None,
    }


def execute_with_retry(cur, conn, sql, params, max_retries=3):
    """Execute SQL with deadlock retry."""
    for attempt in range(max_retries):
        try:
            cur.execute(sql, params)
            return True
        except psycopg2.errors.DeadlockDetected:
            conn.rollback()
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
            else:
                return False
        except Exception as e:
            return False
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Limit records to process (0=all)')
    parser.add_argument('--skip', type=int, default=0, help='Skip first N records (for resume)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated')
    args = parser.parse_args()

    ocds_path = '/Users/tamsar/Downloads/nabavkidata/ocds_data/mk_full.jsonl.gz'

    logger.info("=" * 60)
    logger.info("ENHANCED OCDS IMPORT - Phase 1")
    logger.info("=" * 60)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Load UUID → dossier_id mapping
    logger.info("Loading UUID → dossier_id mapping...")
    cur.execute("SELECT uuid, dossier_id FROM ocds_mapping")
    uuid_to_dossier = {row[0]: row[1] for row in cur.fetchall()}
    logger.info(f"Loaded {len(uuid_to_dossier):,} mappings")

    # Load dossier_id → tender_id mapping
    logger.info("Loading dossier_id → tender_id mapping...")
    cur.execute("SELECT dossier_id, tender_id FROM tenders WHERE dossier_id IS NOT NULL")
    dossier_to_tender = {row[0]: row[1] for row in cur.fetchall()}
    logger.info(f"Loaded {len(dossier_to_tender):,} tender mappings")

    stats = {
        'processed': 0,
        'matched': 0,
        'updated_value': 0,
        'updated_winner': 0,
        'bidders_added': 0,
        'lots_added': 0,
        'no_uuid': 0,
        'no_dossier': 0,
        'no_tender': 0,
    }

    logger.info(f"Processing OCDS file: {ocds_path}")
    if args.skip:
        logger.info(f"Skipping first {args.skip:,} records")

    with gzip.open(ocds_path, 'rt', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            data = parse_ocds_record(record)
            stats['processed'] += 1

            # Skip records for resume
            if stats['processed'] <= args.skip:
                if stats['processed'] % 10000 == 0:
                    logger.info(f"Skipping... {stats['processed']:,}/{args.skip:,}")
                continue

            if args.limit and stats['processed'] > args.limit + args.skip:
                break

            # Find tender via UUID → dossier_id → tender_id
            uuid = data['uuid']
            if not uuid:
                stats['no_uuid'] += 1
                continue

            dossier_id = uuid_to_dossier.get(uuid)
            if not dossier_id:
                stats['no_dossier'] += 1
                continue

            tender_id = dossier_to_tender.get(dossier_id)
            if not tender_id:
                stats['no_tender'] += 1
                continue

            stats['matched'] += 1

            if args.dry_run:
                if data['actual_value_mkd']:
                    logger.info(f"Would update {tender_id}: actual_value={data['actual_value_mkd']}, winner={data['winner']}, bidders={len(data['bidders'])}")
                continue

            # Update tender
            updates = []
            params = []

            if data['actual_value_mkd']:
                updates.append("actual_value_mkd = COALESCE(actual_value_mkd, %s)")
                params.append(data['actual_value_mkd'])
                stats['updated_value'] += 1

            if data['winner']:
                updates.append("winner = COALESCE(winner, %s)")
                params.append(data['winner'][:500])
                stats['updated_winner'] += 1

            if data['num_bidders']:
                updates.append("num_bidders = COALESCE(num_bidders, %s)")
                params.append(data['num_bidders'])

            if data['cpv_code']:
                updates.append("cpv_code = COALESCE(cpv_code, %s)")
                params.append(data['cpv_code'])

            if data['opening_date']:
                updates.append("opening_date = COALESCE(opening_date, %s)")
                params.append(data['opening_date'])

            if data['closing_date']:
                updates.append("closing_date = COALESCE(closing_date, %s)")
                params.append(data['closing_date'])

            if data['contact_person']:
                updates.append("contact_person = COALESCE(contact_person, %s)")
                params.append(data['contact_person'][:200])

            if data['contact_email']:
                updates.append("contact_email = COALESCE(contact_email, %s)")
                params.append(data['contact_email'][:200])

            if data['contact_phone']:
                updates.append("contact_phone = COALESCE(contact_phone, %s)")
                params.append(data['contact_phone'][:50])

            if data['procedure_type']:
                updates.append("procedure_type = COALESCE(procedure_type, %s)")
                params.append(data['procedure_type'][:200])

            if updates:
                updates.append("updated_at = NOW()")
                params.append(tender_id)
                sql = f"UPDATE tenders SET {', '.join(updates)} WHERE tender_id = %s"
                if not execute_with_retry(cur, conn, sql, params):
                    logger.warning(f"Failed to update tender {tender_id} after retries")

            # Insert bidders
            for bidder in data['bidders']:
                try:
                    cur.execute("""
                        INSERT INTO tender_bidders (tender_id, company_name, bid_amount_mkd, is_winner)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (tender_id, company_name) DO UPDATE SET
                            bid_amount_mkd = COALESCE(EXCLUDED.bid_amount_mkd, tender_bidders.bid_amount_mkd),
                            is_winner = EXCLUDED.is_winner OR tender_bidders.is_winner
                    """, (tender_id, bidder['company_name'], bidder['bid_amount'], bidder['is_winner']))
                    stats['bidders_added'] += 1
                except Exception as e:
                    pass  # Ignore constraint errors

            # Insert lots
            for lot in data['lots']:
                try:
                    cur.execute("""
                        INSERT INTO tender_lots (tender_id, lot_number, lot_title, estimated_value_mkd)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (tender_id, lot['lot_number'], lot['lot_title'], lot['estimated_value']))
                    stats['lots_added'] += 1
                except:
                    pass

            # Commit every 1000 records
            if stats['matched'] % 1000 == 0:
                conn.commit()
                logger.info(f"Progress: {stats['processed']:,} processed, {stats['matched']:,} matched, "
                           f"{stats['updated_value']:,} values, {stats['bidders_added']:,} bidders")

    conn.commit()
    cur.close()
    conn.close()

    logger.info("=" * 60)
    logger.info("IMPORT COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Processed:      {stats['processed']:,}")
    logger.info(f"Matched:        {stats['matched']:,}")
    logger.info(f"Values updated: {stats['updated_value']:,}")
    logger.info(f"Winners added:  {stats['updated_winner']:,}")
    logger.info(f"Bidders added:  {stats['bidders_added']:,}")
    logger.info(f"Lots added:     {stats['lots_added']:,}")
    logger.info(f"No UUID:        {stats['no_uuid']:,}")
    logger.info(f"No dossier:     {stats['no_dossier']:,}")
    logger.info(f"No tender:      {stats['no_tender']:,}")


if __name__ == '__main__':
    main()
