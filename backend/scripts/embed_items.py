#!/usr/bin/env python3
"""
Generate embeddings for product items.

This script creates vector embeddings for all product items to enable
semantic search for questions like "What were the prices for surgical drapes?"
"""

import os
import sys
import json
import asyncio
import logging
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata')
sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata/ai')

import psycopg2
from psycopg2.extras import RealDictCursor
import google.generativeai as genai

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com',
    'port': 5432,
    'user': 'nabavki_user',
    'password': os.getenv('DB_PASSWORD', ''),
    'database': 'nabavkidata',
}

# Configure Gemini
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("No GEMINI_API_KEY set - embeddings won't be generated")


def format_item_text(item: Dict) -> str:
    """Format item data as text for embedding"""
    parts = []

    # Item name is most important
    if item.get('name'):
        parts.append(f"Product: {item['name']}")

    # Quantity and unit
    if item.get('quantity') and item.get('unit'):
        parts.append(f"Quantity: {item['quantity']} {item['unit']}")
    elif item.get('quantity'):
        parts.append(f"Quantity: {item['quantity']}")

    # Pricing
    if item.get('unit_price'):
        parts.append(f"Unit Price: {item['unit_price']} MKD")
    if item.get('total_price'):
        parts.append(f"Total Price: {item['total_price']} MKD")

    # CPV code
    if item.get('cpv_code'):
        parts.append(f"CPV Code: {item['cpv_code']}")

    # Tender info
    if item.get('tender_id'):
        parts.append(f"Tender: {item['tender_id']}")
    if item.get('tender_title'):
        parts.append(f"Tender Title: {item['tender_title']}")
    if item.get('procuring_entity'):
        parts.append(f"Procuring Entity: {item['procuring_entity']}")

    # Specifications (if JSON)
    if item.get('specifications') and item['specifications'] != '{}':
        try:
            specs = json.loads(item['specifications']) if isinstance(item['specifications'], str) else item['specifications']
            if specs:
                specs_str = ', '.join(f"{k}: {v}" for k, v in specs.items())
                parts.append(f"Specifications: {specs_str}")
        except:
            pass

    # Raw text for additional context
    if item.get('raw_text'):
        try:
            raw = json.loads(item['raw_text'])
            # Add any fields not already included
            for key, val in raw.items():
                if val and key not in ['name', 'quantity', 'unit', 'unit_price', 'total_price', 'cpv_code']:
                    parts.append(f"{key}: {val}")
        except:
            pass

    return '\n'.join(parts)


def generate_embedding_sync(text: str) -> Optional[List[float]]:
    """Generate embedding using Gemini (synchronous)"""
    if not GEMINI_API_KEY:
        logger.error("GOOGLE_API_KEY not set")
        return None

    try:
        result = genai.embed_content(
            model='models/gemini-embedding-001',
            content=text,
            task_type='retrieval_document',
            output_dimensionality=768
        )
        return result['embedding']
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def embed_items(limit: int = None, dry_run: bool = False):
    """Generate embeddings for product items"""

    conn = psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        dbname=DB_CONFIG['database']
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Get items that need embeddings
        # Items with pricing are most valuable
        query = """
            SELECT pi.id, pi.tender_id, pi.name, pi.quantity, pi.unit,
                   pi.unit_price, pi.total_price, pi.cpv_code,
                   pi.specifications::text, pi.raw_text,
                   t.title as tender_title, t.procuring_entity
            FROM product_items pi
            LEFT JOIN tenders t ON pi.tender_id = t.tender_id
            WHERE pi.unit_price IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM embeddings e
                  WHERE e.metadata->>'item_id' = pi.id::text
              )
            ORDER BY pi.unit_price DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        items = cur.fetchall()
        logger.info(f"Found {len(items)} items to embed")

        if dry_run:
            for item in items[:5]:
                text = format_item_text(dict(item))
                print(f"\n--- Item {item['id']} ---")
                print(text)
            return

        # Process items
        embedded = 0
        for i, item in enumerate(items):
            item_dict = dict(item)
            text = format_item_text(item_dict)

            logger.info(f"[{i+1}/{len(items)}] Embedding: {item['name'][:50]}...")

            embedding = generate_embedding_sync(text)
            if not embedding:
                logger.warning(f"Failed to generate embedding for item {item['id']}")
                continue

            # Store embedding
            metadata = {
                'item_id': str(item['id']),
                'item_name': item['name'],
                'unit_price': float(item['unit_price']) if item['unit_price'] else None,
                'cpv_code': item['cpv_code'],
                'tender_title': item.get('tender_title'),
                'type': 'product_item'
            }

            cur.execute("""
                INSERT INTO embeddings (tender_id, chunk_text, chunk_index, metadata, vector)
                VALUES (%s, %s, %s, %s, %s)
            """, (item['tender_id'], text, 0, json.dumps(metadata), embedding))
            conn.commit()

            embedded += 1

            # Progress update
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{len(items)} ({embedded} embedded)")

            # Rate limiting
            import time
            time.sleep(0.2)

        logger.info(f"\nEmbedded {embedded} items")

    finally:
        cur.close()
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None, help='Max items to embed')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be embedded')
    args = parser.parse_args()

    embed_items(limit=args.limit, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
