#!/usr/bin/env python3
"""
Re-scrape ePazar tenders that are missing items_data.
Uses the e-pazar.gov.mk JSON API directly.
"""

import os
import sys
import json
import time
import logging
import requests
from typing import Optional, Dict, List
from dotenv import load_dotenv
load_dotenv()


# Add parent to path
sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata')

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'nabavki_user',
    'password': os.getenv('DB_PASSWORD', ''),
    'database': 'nabavkidata',
}

# ePazar API endpoints
BASE_URL = "https://e-pazar.gov.mk"
API_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def get_tender_items(tender_id: str) -> List[Dict]:
    """Fetch tender items from e-pazar API"""
    try:
        # Extract numeric ID from tender_id
        # tender_id format: "EPAZAR-123" or "epazar_123"
        numeric_id = tender_id.replace('EPAZAR-', '').replace('epazar_', '')

        # Items API endpoint
        url = f"{BASE_URL}/api/tenderproductrequirement/getTenderProductRequirementsbyTenderId/{numeric_id}"

        response = requests.get(url, headers=API_HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data and 'data' in data:
                return data['data']
        return []
    except Exception as e:
        logger.error(f"Error fetching items for {tender_id}: {e}")
        return []


def get_tender_details(tender_id: str) -> Optional[Dict]:
    """Fetch tender details from API"""
    try:
        # Extract numeric ID from tender_id
        numeric_id = tender_id.replace('EPAZAR-', '').replace('epazar_', '')

        # Detail endpoint
        url = f"{BASE_URL}/api/tender/getPublishedTenderDetails/{numeric_id}"

        response = requests.get(url, headers=API_HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data:
                return data
        return None
    except Exception as e:
        logger.error(f"Error fetching tender {tender_id}: {e}")
        return None


def extract_items_from_response(data: Dict) -> List[Dict]:
    """Extract items/products from tender API response"""
    items = []

    # Check various possible locations for items data
    possible_keys = ['items', 'products', 'tenderItems', 'goods', 'lotItems', 'lots']

    for key in possible_keys:
        if key in data and data[key]:
            raw_items = data[key]
            if isinstance(raw_items, list):
                for item in raw_items:
                    extracted = extract_item_fields(item)
                    if extracted:
                        items.append(extracted)

    # Check nested structures
    if 'lots' in data and data['lots']:
        for lot in data['lots']:
            if isinstance(lot, dict):
                for key in ['items', 'products', 'lotItems']:
                    if key in lot and lot[key]:
                        for item in lot[key]:
                            extracted = extract_item_fields(item)
                            if extracted:
                                items.append(extracted)

    return items


def extract_item_fields(item: Dict) -> Optional[Dict]:
    """Extract standard fields from item"""
    if not isinstance(item, dict):
        return None

    return {
        'name': item.get('name') or item.get('itemName') or item.get('description') or item.get('productName'),
        'quantity': item.get('quantity') or item.get('qty') or item.get('amount'),
        'unit': item.get('unit') or item.get('unitOfMeasure') or item.get('measureUnit'),
        'unit_price': item.get('unitPrice') or item.get('price') or item.get('pricePerUnit'),
        'total_price': item.get('totalPrice') or item.get('totalValue') or item.get('value'),
        'cpv_code': item.get('cpvCode') or item.get('cpv'),
        'specifications': item.get('specifications') or item.get('technicalSpecifications'),
    }


def format_api_item(item: Dict) -> Dict:
    """Format API item to standard format"""
    return {
        'name': item.get('tenderProductName'),
        'description': item.get('tenderProductDescription'),
        'quantity': item.get('tenderProductQuantity'),
        'unit': item.get('tenderProductMesureUnitName'),
        'attributes': item.get('tenderProductAttributes'),  # XML attributes
        'cpv_code': None,  # Not in this API
        'order_number': item.get('tenderRequirementOrderNumber'),
        'product_type_id': item.get('productTypeId'),
        'category_id': item.get('categoryId'),
    }


def rescrape_missing_items(limit: int = None, dry_run: bool = False):
    """Re-scrape ePazar tenders missing items_data"""

    conn = psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        dbname=DB_CONFIG['database']
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Get tenders missing items_data
        query = """
            SELECT tender_id, title, source_url, raw_data_json
            FROM epazar_tenders
            WHERE items_data IS NULL OR items_data = '[]'
            ORDER BY created_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        tenders = cur.fetchall()
        logger.info(f"Found {len(tenders)} tenders missing items_data")

        if dry_run:
            for t in tenders[:10]:
                logger.info(f"  Would process: {t['tender_id']} - {t['title'][:50] if t['title'] else 'Unknown'}...")
            return

        updated = 0
        skipped = 0
        api_errors = 0

        for i, tender in enumerate(tenders):
            tender_id = tender['tender_id']
            title = tender['title'] or 'Unknown'

            logger.info(f"[{i+1}/{len(tenders)}] Processing: {title[:50]}...")

            # Fetch items from dedicated items API
            api_items = get_tender_items(tender_id)

            if api_items:
                # Format items to standard structure
                items = [format_api_item(item) for item in api_items]
                items_json = json.dumps(items, ensure_ascii=False)

                cur.execute("""
                    UPDATE epazar_tenders
                    SET items_data = %s,
                        updated_at = NOW()
                    WHERE tender_id = %s
                """, (items_json, tender_id))
                conn.commit()
                updated += 1
                logger.info(f"  ✓ Updated with {len(items)} items")
            else:
                skipped += 1
                logger.info(f"  ✗ No items found")

            # Rate limiting
            time.sleep(0.3)

        logger.info(f"\n{'='*50}")
        logger.info(f"RE-SCRAPE COMPLETE")
        logger.info(f"{'='*50}")
        logger.info(f"Updated: {updated}")
        logger.info(f"Skipped: {skipped}")
        logger.info(f"Total: {len(tenders)}")

    finally:
        cur.close()
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Re-scrape ePazar items')
    parser.add_argument('--limit', type=int, default=None, help='Max tenders to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    rescrape_missing_items(limit=args.limit, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
