#!/usr/bin/env python3
"""
Extract items/products from contract documents using Gemini AI.

This script processes contract PDFs that have been OCR'd and uses Gemini
to extract structured item information (name, quantity, unit price, etc.)
"""
import asyncio
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

import asyncpg
from dotenv import load_dotenv
load_dotenv()


# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from gemini_extractor import GeminiExtractor, parse_european_number

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


class ContractItemExtractor:
    def __init__(self):
        self.conn: Optional[asyncpg.Connection] = None
        self.gemini_extractor = GeminiExtractor()

    async def connect(self):
        """Connect to database"""
        self.conn = await asyncpg.connect(DATABASE_URL)
        logger.info("Connected to database")

    async def close(self):
        """Close connections"""
        if self.conn:
            await self.conn.close()
        logger.info("Connections closed")

    async def get_contracts_to_process(self, limit: int = 100,
                                        tender_id: Optional[str] = None) -> List[Dict]:
        """Get contracts that haven't had items extracted yet"""
        if tender_id:
            query = """
                SELECT d.doc_id, d.tender_id, d.content_text, d.file_name
                FROM documents d
                WHERE d.tender_id = $1
                  AND d.doc_category = 'contract'
                  AND d.extraction_status = 'success'
                  AND d.content_text IS NOT NULL
                  AND LENGTH(d.content_text) > 500
                ORDER BY d.doc_id
            """
            rows = await self.conn.fetch(query, tender_id)
        else:
            # Get contracts for tenders that don't have items yet
            query = """
                SELECT d.doc_id, d.tender_id, d.content_text, d.file_name
                FROM documents d
                WHERE d.doc_category = 'contract'
                  AND d.extraction_status = 'success'
                  AND d.content_text IS NOT NULL
                  AND LENGTH(d.content_text) > 500
                  AND d.tender_id NOT IN (
                      SELECT DISTINCT tender_id FROM product_items WHERE tender_id IS NOT NULL
                  )
                ORDER BY d.doc_id
                LIMIT $1
            """
            rows = await self.conn.fetch(query, limit)

        return [dict(row) for row in rows]

    async def extract_items_with_gemini(self, contract_text: str) -> List[Dict]:
        """Use Gemini to extract items from contract text"""
        # Use unified Gemini extractor
        return self.gemini_extractor.extract_and_normalize(contract_text, 'contract')

    async def save_items(self, doc_id: str, tender_id: str, items: List[Dict]) -> int:
        """Save extracted items to product_items table"""
        items_inserted = 0

        for i, item in enumerate(items):
            name = item.get('name', '').strip()
            if not name or len(name) < 3:
                continue

            try:
                await self.conn.execute("""
                    INSERT INTO product_items (
                        tender_id, document_id, item_number,
                        name, quantity, unit, unit_price, total_price,
                        specifications, extraction_confidence, extraction_method
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT DO NOTHING
                """,
                    tender_id,
                    doc_id,
                    i + 1,
                    name,
                    str(item.get('quantity', '')) if item.get('quantity') else None,
                    item.get('unit'),
                    parse_european_number(item.get('unit_price')),
                    parse_european_number(item.get('total_price')),
                    json.dumps({'specifications': item.get('specifications', '')}, ensure_ascii=False),
                    0.7,  # Confidence for contract extraction
                    'gemini_contract'
                )
                items_inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert item '{name[:30]}...': {e}")

        return items_inserted

    async def process_contract(self, doc: Dict) -> int:
        """Process a single contract document"""
        doc_id = str(doc['doc_id'])
        tender_id = doc['tender_id']
        content = doc['content_text']

        logger.info(f"Processing contract for tender {tender_id} ({len(content)} chars)")

        # Extract items using Gemini
        items = await self.extract_items_with_gemini(content)

        if not items:
            logger.info(f"No items extracted from contract for {tender_id}")
            return 0

        logger.info(f"Extracted {len(items)} items from contract for {tender_id}")

        # Save items
        saved = await self.save_items(doc_id, tender_id, items)
        logger.info(f"Saved {saved} items for tender {tender_id}")

        return saved


async def main():
    parser = argparse.ArgumentParser(description='Extract items from contracts using Gemini')
    parser.add_argument('--limit', type=int, default=50, help='Number of contracts to process')
    parser.add_argument('--tender-id', type=str, help='Process specific tender')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without saving')
    args = parser.parse_args()

    extractor = ContractItemExtractor()

    try:
        await extractor.connect()

        # Get contracts to process
        contracts = await extractor.get_contracts_to_process(
            limit=args.limit,
            tender_id=args.tender_id
        )

        logger.info(f"Found {len(contracts)} contracts to process")

        if not contracts:
            logger.info("No contracts need processing")
            return

        total_items = 0
        processed = 0

        for doc in contracts:
            if args.dry_run:
                logger.info(f"[DRY RUN] Would process: {doc['tender_id']} - {doc['file_name']}")
                continue

            items = await extractor.process_contract(doc)
            total_items += items
            processed += 1

            # Rate limiting - don't overwhelm Gemini API
            if processed < len(contracts):
                await asyncio.sleep(1)

        logger.info(f"\nProcessing complete: {processed} contracts, {total_items} items extracted")

    finally:
        await extractor.close()


if __name__ == '__main__':
    asyncio.run(main())
