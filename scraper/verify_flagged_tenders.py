#!/usr/bin/env python3
"""
Verification Script for Flagged Tenders

This script provides a command-line interface to verify flagged tenders
using the verification spider and Gemini API for web enrichment.

Usage:
    # Verify specific tender IDs
    python verify_flagged_tenders.py --tender-ids 12345/2024,67890/2023

    # Verify all flagged tenders with anomaly score > 0.7
    python verify_flagged_tenders.py --from-db --min-score 0.7 --limit 50

    # Verify with web search enrichment
    python verify_flagged_tenders.py --tender-ids 12345/2024 --web-search

    # Verify known corruption cases
    python verify_flagged_tenders.py --known-cases
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Known corruption case tender IDs (verified matches from ground truth analysis)
KNOWN_CORRUPTION_TENDERS = {
    # MK-2021-001: Software/Biometric Case
    # 72 billion MKD tender from State Election Commission
    'MK-2021-001': {
        'tender_ids': ['OT-d6600950cd56/2020'],
        'name': 'Biometric Case',
        'entity': 'State Election Commission',
        'description': 'Suspicious biometric/software tender'
    },

    # MK-2024-001: TEC Negotino Fuel Oil
    # Multiple fuel/energy tenders (Note: RKM mazut case not in DB - different procurement)
    'MK-2024-001': {
        'tender_ids': [
            '14987/2019',  # Electricity
            '18928/2020',  # Electricity
            '17600/2024',  # Fuels (JP Komunalna higiena)
        ],
        'name': 'TEC Negotino',
        'entity': 'ESM / TEC Negotino',
        'description': 'Energy sector tenders - Note: 212M EUR RKM mazut case is separate'
    },

    # MK-2024-002: State Lottery
    'MK-2024-002': {
        'tender_ids': [
            '21437/2023',  # Software license maintenance
            '21441/2023',  # Commercial audit services
        ],
        'name': 'State Lottery',
        'entity': 'Државна видеолотарија',
        'description': 'State lottery IT and audit contracts'
    },

    # MK-2022-001: Kamcev Land Parcels
    'MK-2022-001': {
        'tender_ids': [],  # Only "possible" matches - land/construction tenders
        'name': 'Kamcev Land Case',
        'entity': 'Various municipalities',
        'description': 'Land development tenders - need manual verification'
    },
}


def run_spider(tender_ids: list, web_search: bool = False) -> dict:
    """Run the verification spider with given parameters."""
    cmd = [
        'scrapy', 'crawl', 'verify',
        '-a', f'tender_ids={",".join(tender_ids)}',
    ]

    if web_search:
        cmd.extend(['-a', 'web_search=true'])

    logger.info(f"Running spider: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        logger.error(f"Spider failed: {result.stderr}")
        return {'error': result.stderr}

    return {'output': result.stdout}


def run_db_verification(min_score: float, limit: int, web_search: bool = False) -> dict:
    """Run verification on flagged tenders from database."""
    cmd = [
        'scrapy', 'crawl', 'verify',
        '-a', 'from_db=true',
        '-a', f'min_score={min_score}',
        '-a', f'limit={limit}',
    ]

    if web_search:
        cmd.extend(['-a', 'web_search=true'])

    logger.info(f"Running spider: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        logger.error(f"Spider failed: {result.stderr}")
        return {'error': result.stderr}

    return {'output': result.stdout}


def verify_known_cases(web_search: bool = False) -> dict:
    """Verify all known corruption cases."""
    results = {}

    for case_id, case_data in KNOWN_CORRUPTION_TENDERS.items():
        tender_ids = case_data['tender_ids']

        if not tender_ids:
            logger.warning(f"No tender IDs for {case_id} ({case_data['name']})")
            results[case_id] = {'status': 'no_tender_ids'}
            continue

        logger.info(f"Verifying {case_id}: {case_data['name']}")
        logger.info(f"  Tender IDs: {tender_ids}")

        result = run_spider(tender_ids, web_search)
        results[case_id] = {
            'name': case_data['name'],
            'tender_ids': tender_ids,
            'result': result
        }

    return results


async def quick_db_check(tender_ids: list) -> dict:
    """Quick database check without running full spider."""
    import asyncpg

    db_config = {
        'host': os.getenv('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'nabavkidata'),
        'user': os.getenv('DB_USER', 'nabavkidata_admin'),
        'password': os.getenv('DB_PASSWORD', ''),
    }

    conn = await asyncpg.connect(**db_config)

    results = {}
    for tender_id in tender_ids:
        row = await conn.fetchrow("""
            SELECT
                t.tender_id, t.title, t.procuring_entity, t.winner,
                t.estimated_value_mkd, t.actual_value_mkd, t.status,
                cf.anomaly_score, cf.flags
            FROM tenders t
            LEFT JOIN corruption_flags cf ON t.tender_id = cf.tender_id
            WHERE t.tender_id = $1
        """, tender_id)

        if row:
            results[tender_id] = dict(row)
        else:
            results[tender_id] = {'error': 'not_found'}

    await conn.close()
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Verify flagged tenders from e-nabavki with optional web enrichment'
    )

    parser.add_argument(
        '--tender-ids',
        type=str,
        help='Comma-separated list of tender IDs to verify'
    )

    parser.add_argument(
        '--from-db',
        action='store_true',
        help='Verify flagged tenders from database'
    )

    parser.add_argument(
        '--min-score',
        type=float,
        default=0.5,
        help='Minimum anomaly score for database selection (default: 0.5)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of tenders to verify (default: 50)'
    )

    parser.add_argument(
        '--web-search',
        action='store_true',
        help='Enable Gemini web search enrichment'
    )

    parser.add_argument(
        '--known-cases',
        action='store_true',
        help='Verify all known corruption cases'
    )

    parser.add_argument(
        '--quick-check',
        action='store_true',
        help='Quick database check without running spider'
    )

    args = parser.parse_args()

    if args.known_cases:
        logger.info("Verifying known corruption cases...")
        results = verify_known_cases(args.web_search)
        print(json.dumps(results, indent=2, default=str))

    elif args.tender_ids:
        tender_ids = [t.strip() for t in args.tender_ids.split(',')]

        if args.quick_check:
            logger.info(f"Quick check for {len(tender_ids)} tenders...")
            results = asyncio.run(quick_db_check(tender_ids))
            print(json.dumps(results, indent=2, default=str))
        else:
            logger.info(f"Verifying {len(tender_ids)} specific tenders...")
            result = run_spider(tender_ids, args.web_search)
            print(result.get('output', result.get('error', 'Unknown error')))

    elif args.from_db:
        logger.info(f"Verifying flagged tenders (min_score={args.min_score}, limit={args.limit})...")
        result = run_db_verification(args.min_score, args.limit, args.web_search)
        print(result.get('output', result.get('error', 'Unknown error')))

    else:
        parser.print_help()
        print("\nExample commands:")
        print("  python verify_flagged_tenders.py --known-cases")
        print("  python verify_flagged_tenders.py --tender-ids 12345/2024,67890/2023 --web-search")
        print("  python verify_flagged_tenders.py --from-db --min-score 0.7 --limit 100")


if __name__ == '__main__':
    main()
