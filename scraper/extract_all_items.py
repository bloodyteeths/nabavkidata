#!/usr/bin/env python3
"""
Extract product items from ALL document types using Gemini AI.

Processes documents that have been text-extracted but NOT yet run through
the Gemini product extraction pipeline. Handles all document categories.

Uses concurrent processing (10 parallel Gemini calls) for speed.

Usage:
    python3 extract_all_items.py --limit 500 --workers 10
    python3 extract_all_items.py --category bid --limit 200
    python3 extract_all_items.py --tender-id 12345/2025
    python3 extract_all_items.py --dry-run --limit 100
"""
import asyncio
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from threading import Lock

import asyncpg
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from gemini_extractor import GeminiExtractor, parse_european_number

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    """Convert SQLAlchemy URL format to asyncpg format."""
    if url and url.startswith('postgresql+asyncpg://'):
        return url.replace('postgresql+asyncpg://', 'postgresql://')
    return url

DATABASE_URL = _normalize_database_url(os.getenv('DATABASE_URL', ''))

# Category → extraction_method mapping
CATEGORY_METHOD_MAP = {
    'bid': 'gemini_bid',
    'contract': 'gemini_contract',
    'tender_docs': 'gemini_tender_docs',
    'technical_specs': 'gemini_technical_specs',
    'financial_docs': 'gemini_financial_docs',
    'award_decision': 'gemini_award_decision',
    'other': 'gemini_other',
    None: 'gemini_other',
}

CATEGORY_CONFIDENCE = {
    'bid': 0.75,
    'contract': 0.7,
    'tender_docs': 0.6,
    'technical_specs': 0.6,
    'financial_docs': 0.7,
    'award_decision': 0.65,
    'other': 0.5,
    None: 0.5,
}

CATEGORY_PRIORITY = ['bid', 'contract', 'financial_docs', 'tender_docs', 'technical_specs', 'award_decision', 'other']


class AllItemsExtractor:
    def __init__(self, workers: int = 10):
        self.pool: Optional[asyncpg.Pool] = None
        self.gemini = GeminiExtractor()
        self.semaphore = asyncio.Semaphore(workers)
        self.stats_lock = Lock()
        self.stats = {
            'docs_processed': 0,
            'docs_with_items': 0,
            'docs_failed': 0,
            'docs_empty': 0,
            'total_items': 0,
            'items_with_price': 0,
        }

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=15)
        logger.info(f"Connected to database (pool size 2-15)")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def get_documents_to_process(self, limit: int = 100,
                                        category: Optional[str] = None,
                                        tender_id: Optional[str] = None) -> List[Dict]:
        """Get documents for tenders that don't already have priced product items."""
        # Skip tenders that already have items WITH prices (backfill-safe)
        SKIP_CLAUSE = """
            AND d.tender_id NOT IN (
                SELECT DISTINCT tender_id FROM product_items
                WHERE unit_price IS NOT NULL AND unit_price > 0
            )
        """

        async with self.pool.acquire() as conn:
            if tender_id:
                query = """
                    SELECT d.doc_id, d.tender_id, d.content_text, d.file_name,
                           d.doc_category, d.file_url
                    FROM documents d
                    WHERE d.tender_id = $1
                      AND d.extraction_status = 'success'
                      AND d.content_text IS NOT NULL
                      AND LENGTH(d.content_text) > 300
                    ORDER BY d.doc_id
                """
                rows = await conn.fetch(query, tender_id)
            elif category:
                if category == 'NULL':
                    query = f"""
                        SELECT d.doc_id, d.tender_id, d.content_text, d.file_name,
                               d.doc_category, d.file_url
                        FROM documents d
                        WHERE d.doc_category IS NULL
                          AND d.extraction_status = 'success'
                          AND d.content_text IS NOT NULL
                          AND LENGTH(d.content_text) > 300
                          {SKIP_CLAUSE}
                        ORDER BY LENGTH(d.content_text) DESC
                        LIMIT $1
                    """
                    rows = await conn.fetch(query, limit)
                else:
                    query = f"""
                        SELECT d.doc_id, d.tender_id, d.content_text, d.file_name,
                               d.doc_category, d.file_url
                        FROM documents d
                        WHERE d.doc_category = $1
                          AND d.extraction_status = 'success'
                          AND d.content_text IS NOT NULL
                          AND LENGTH(d.content_text) > 300
                          {SKIP_CLAUSE}
                        ORDER BY LENGTH(d.content_text) DESC
                        LIMIT $2
                    """
                    rows = await conn.fetch(query, category, limit)
            else:
                query = f"""
                    SELECT d.doc_id, d.tender_id, d.content_text, d.file_name,
                           d.doc_category, d.file_url
                    FROM documents d
                    WHERE d.extraction_status = 'success'
                      AND d.content_text IS NOT NULL
                      AND LENGTH(d.content_text) > 300
                      {SKIP_CLAUSE}
                    ORDER BY
                        CASE d.doc_category
                            WHEN 'bid' THEN 1
                            WHEN 'contract' THEN 2
                            WHEN 'financial_docs' THEN 3
                            WHEN 'tender_docs' THEN 4
                            WHEN 'technical_specs' THEN 5
                            WHEN 'award_decision' THEN 6
                            WHEN 'other' THEN 7
                            ELSE 8
                        END,
                        LENGTH(d.content_text) DESC
                    LIMIT $1
                """
                rows = await conn.fetch(query, limit)

        return [dict(row) for row in rows]

    async def save_items(self, conn, doc_id: str, tender_id: str,
                         items: List[Dict], doc_category: str) -> int:
        """Save extracted items to product_items table."""
        extraction_method = CATEGORY_METHOD_MAP.get(doc_category, 'gemini_other')
        confidence = CATEGORY_CONFIDENCE.get(doc_category, 0.5)
        saved = 0
        price_count = 0

        for i, item in enumerate(items):
            name = (item.get('name') or '').strip()
            if not name or len(name) < 3:
                continue

            unit_price = parse_european_number(item.get('unit_price'))
            total_price = parse_european_number(item.get('total_price'))
            quantity = None
            try:
                q = item.get('quantity')
                if q is not None:
                    quantity = float(str(q).replace(',', '.').replace(' ', ''))
            except (ValueError, TypeError):
                pass

            if unit_price is not None and (unit_price < 0 or unit_price > 10_000_000_000):
                unit_price = None
            if total_price is not None and (total_price < 0 or total_price > 10_000_000_000):
                total_price = None

            # Price normalization: derive unit_price from total_price / quantity
            if total_price and quantity and quantity > 0:
                derived = total_price / quantity
                if unit_price is None:
                    # No unit_price at all — calculate it
                    unit_price = round(derived, 2)
                elif abs(unit_price * quantity - total_price) > total_price * 0.05:
                    # unit_price * qty doesn't match total — trust total_price, recalculate unit
                    unit_price = round(derived, 2)
            elif unit_price and quantity and quantity > 0 and total_price is None:
                # Have unit but no total — calculate total
                total_price = round(unit_price * quantity, 2)

            try:
                await conn.execute("""
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
                    unit_price,
                    total_price,
                    json.dumps({'specifications': item.get('specifications', '')}, ensure_ascii=False) if item.get('specifications') else None,
                    confidence,
                    extraction_method
                )
                saved += 1
                if unit_price is not None and unit_price > 0:
                    price_count += 1
            except Exception as e:
                logger.warning(f"Insert failed for '{name[:30]}': {e}")

        return saved, price_count

    async def process_document(self, doc: Dict) -> int:
        """Process a single document through Gemini extraction (with concurrency limit)."""
        async with self.semaphore:
            doc_id = str(doc['doc_id'])
            tender_id = doc['tender_id']
            content = doc['content_text']
            doc_category = doc.get('doc_category') or 'other'

            try:
                # Run synchronous Gemini call in thread pool
                items = await asyncio.to_thread(
                    self.gemini.extract_and_normalize, content, doc_category
                )
            except Exception as e:
                logger.error(f"Gemini failed for {tender_id}: {e}")
                with self.stats_lock:
                    self.stats['docs_failed'] += 1
                return 0

            if not items:
                with self.stats_lock:
                    self.stats['docs_processed'] += 1
                    self.stats['docs_empty'] += 1
                return 0

            # Save to DB using a connection from the pool
            async with self.pool.acquire() as conn:
                saved, price_count = await self.save_items(conn, doc_id, tender_id, items, doc_category)

            with self.stats_lock:
                self.stats['docs_processed'] += 1
                self.stats['docs_with_items'] += 1
                self.stats['total_items'] += saved
                self.stats['items_with_price'] += price_count

            logger.info(f"[{doc_category}] {tender_id}: {saved} items ({price_count} w/price)")
            return saved

    def print_stats(self, elapsed: float):
        s = self.stats
        total = s['docs_processed'] + s['docs_failed']
        logger.info("=" * 60)
        logger.info(f"EXTRACTION COMPLETE ({elapsed:.0f}s)")
        logger.info(f"  Documents processed:  {total}")
        logger.info(f"  - With items:         {s['docs_with_items']}")
        logger.info(f"  - Empty (no items):   {s['docs_empty']}")
        logger.info(f"  - Failed:             {s['docs_failed']}")
        logger.info(f"  Total items saved:    {s['total_items']}")
        logger.info(f"  Items with prices:    {s['items_with_price']}")
        if total > 0:
            yield_rate = s['docs_with_items'] / total * 100
            docs_per_min = total / elapsed * 60
            logger.info(f"  Yield rate:           {yield_rate:.0f}%")
            logger.info(f"  Speed:                {docs_per_min:.1f} docs/min")
        logger.info("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description='Extract product items from all document types using Gemini AI')
    parser.add_argument('--limit', type=int, default=500, help='Max documents to process')
    parser.add_argument('--workers', type=int, default=10, help='Concurrent Gemini calls')
    parser.add_argument('--category', type=str, choices=CATEGORY_PRIORITY + ['NULL'],
                        help='Process only this doc category')
    parser.add_argument('--tender-id', type=str, help='Process specific tender')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    args = parser.parse_args()

    extractor = AllItemsExtractor(workers=args.workers)

    try:
        await extractor.connect()

        docs = await extractor.get_documents_to_process(
            limit=args.limit,
            category=args.category,
            tender_id=args.tender_id
        )

        logger.info(f"Found {len(docs)} documents to process (workers={args.workers})")

        if not docs:
            logger.info("Nothing to process")
            return

        if args.dry_run:
            cat_counts = {}
            for doc in docs:
                cat = doc.get('doc_category') or 'NULL'
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
            logger.info("Would process:")
            for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
                logger.info(f"  {cat}: {count} docs")
            return

        start_time = time.time()

        # Process all docs concurrently (semaphore limits parallelism)
        tasks = [extractor.process_document(doc) for doc in docs]

        # Process in chunks to show progress
        chunk_size = 50
        for chunk_start in range(0, len(tasks), chunk_size):
            chunk = tasks[chunk_start:chunk_start + chunk_size]
            await asyncio.gather(*chunk)
            elapsed = time.time() - start_time
            done = min(chunk_start + chunk_size, len(tasks))
            rate = done / elapsed * 60
            logger.info(f"--- Progress: {done}/{len(docs)} ({rate:.1f} docs/min, {elapsed:.0f}s elapsed) ---")

        elapsed = time.time() - start_time
        extractor.print_stats(elapsed)

    finally:
        await extractor.close()


if __name__ == '__main__':
    asyncio.run(main())
