#!/usr/bin/env python3
"""
TURBO backfill - Multiple browsers for max parallelism.

Each browser handles multiple pages concurrently.
With 6 browsers × 5 concurrent pages = 30 parallel extractions.

Usage:
    python3 backfill_turbo.py --browsers 6 --pages-per-browser 5 --batch 200
"""

import os
import sys
import asyncio
import logging
import argparse
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import time
from asyncio import Queue

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from playwright.async_api import async_playwright, Browser, Page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backfill_turbo.log')
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
    'port': int(os.environ.get('POSTGRES_PORT', 5432)),
    'database': os.environ.get('POSTGRES_DB', 'nabavkidata'),
    'user': os.environ.get('POSTGRES_USER', 'nabavki_user'),
    'password': os.environ.get('POSTGRES_PASSWORD', ''),
}

# CSS selectors
VALUE_SELECTORS = [
    "label[label-for='ASSIGNED CONTRACT VALUE WITHOUT VAT'] + label.dosie-value",
    "label[label-for='ASSIGNED CONTRACT VALUE DOSSIE'] + label.dosie-value",
    "label[label-for*='ASSIGNED CONTRACT VALUE'] + label.dosie-value",
    "label[label-for*='CONTRACT VALUE'] + label.dosie-value",
]

BIDDER_SELECTORS = [
    "label[label-for='TENDERER COUNT'] + label.dosie-value",
    "label[label-for*='TENDERER'] + label.dosie-value",
]


@dataclass
class TenderUpdate:
    tender_id: str
    dossier_id: str
    actual_value_mkd: Optional[float] = None
    num_bidders: Optional[int] = None
    success: bool = False
    error: Optional[str] = None


def parse_value(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'[A-Za-z\s\*\(\)]', '', text)
    text = text.replace('МКД', '').replace('MKD', '').replace('ден', '')
    text = text.replace('.', '').replace(',', '.')
    try:
        value = float(text)
        if 0 < value < 100_000_000_000:
            return value
    except:
        pass
    return None


def parse_bidders(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r'(\d+)', text)
    if match:
        count = int(match.group(1))
        if 0 <= count <= 1000:
            return count
    return None


async def extract_tender(page: Page, url: str) -> Tuple[Optional[float], Optional[int], Optional[str]]:
    """Extract data from a tender page."""
    try:
        # Navigate with short timeout
        await page.goto(url, wait_until='domcontentloaded', timeout=15000)

        # Wait for Angular content
        try:
            await page.wait_for_selector('.dosie-value', timeout=10000)
        except:
            return None, None, "No dosie-value"

        await asyncio.sleep(0.3)

        # Extract value
        actual_value = None
        for sel in VALUE_SELECTORS:
            try:
                elem = await page.query_selector(sel)
                if elem:
                    text = await elem.text_content()
                    if text and text.strip() not in ['/', '-', '', '0', '0.00']:
                        v = parse_value(text)
                        if v:
                            actual_value = v
                            break
            except:
                continue

        # Extract bidders
        num_bidders = None
        for sel in BIDDER_SELECTORS:
            try:
                elem = await page.query_selector(sel)
                if elem:
                    text = await elem.text_content()
                    if text:
                        b = parse_bidders(text)
                        if b is not None:
                            num_bidders = b
                            break
            except:
                continue

        return actual_value, num_bidders, None

    except Exception as e:
        return None, None, str(e)[:50]


class BrowserWorker:
    """A worker with its own browser and concurrent page pool."""

    def __init__(self, worker_id: int, browser: Browser, max_pages: int = 5):
        self.worker_id = worker_id
        self.browser = browser
        self.max_pages = max_pages
        self.semaphore = asyncio.Semaphore(max_pages)
        self.context = None
        self.processed = 0
        self.successes = 0

    async def init_context(self):
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            java_script_enabled=True,
        )

    async def process_tender(self, tender: Dict) -> TenderUpdate:
        """Process a single tender using this worker's browser."""
        async with self.semaphore:
            tender_id = tender['tender_id']
            dossier_id = tender['dossier_id']
            url = tender['source_url']

            # Fix URL to go to contract tab
            if '/dossie/' in url and not url.endswith('/14'):
                url = re.sub(r'/dossie/([^/]+)/?.*$', r'/dossie/\1/14', url)

            page = None
            try:
                page = await self.context.new_page()
                value, bidders, error = await extract_tender(page, url)

                self.processed += 1
                if value:
                    self.successes += 1

                return TenderUpdate(
                    tender_id=tender_id,
                    dossier_id=dossier_id,
                    actual_value_mkd=value,
                    num_bidders=bidders,
                    success=(value is not None),
                    error=error
                )
            except Exception as e:
                self.processed += 1
                return TenderUpdate(
                    tender_id=tender_id,
                    dossier_id=dossier_id,
                    success=False,
                    error=str(e)[:50]
                )
            finally:
                if page:
                    await page.close()

    async def close(self):
        if self.context:
            await self.context.close()


def get_pending_tenders(conn, batch_size: int, offset: int) -> List[Dict]:
    query = f"""
        SELECT tender_id, dossier_id, source_url
        FROM tenders
        WHERE source_url LIKE '%%e-nabavki%%'
          AND actual_value_mkd IS NULL
          AND dossier_id IS NOT NULL
        ORDER BY tender_id
        LIMIT {batch_size} OFFSET {offset}
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return cur.fetchall()


def update_db(conn, updates: List[TenderUpdate]):
    success_updates = [(u.actual_value_mkd, u.num_bidders, u.tender_id)
                       for u in updates if u.success and u.actual_value_mkd]
    if success_updates:
        query = """
            UPDATE tenders
            SET actual_value_mkd = %s, num_bidders = COALESCE(%s, num_bidders)
            WHERE tender_id = %s
        """
        with conn.cursor() as cur:
            execute_batch(cur, query, success_updates, page_size=100)
        conn.commit()
        logger.info(f"✅ DB updated: {len(success_updates)} tenders")


async def run_backfill(num_browsers: int, pages_per_browser: int, batch_size: int, max_tenders: int = None):
    """Main backfill function with multiple browsers."""
    total_workers = num_browsers * pages_per_browser
    logger.info(f"🚀 Starting TURBO backfill: {num_browsers} browsers × {pages_per_browser} pages = {total_workers} concurrent")

    conn = psycopg2.connect(**DB_CONFIG)
    logger.info("📦 Connected to database")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM tenders
            WHERE source_url LIKE '%e-nabavki%'
              AND actual_value_mkd IS NULL
              AND dossier_id IS NOT NULL
        """)
        total = cur.fetchone()[0]

    logger.info(f"📊 Total tenders to process: {total:,}")

    if max_tenders:
        total = min(total, max_tenders)
        logger.info(f"⚡ Limited to {max_tenders:,} tenders")

    async with async_playwright() as p:
        # Launch multiple browsers
        browsers = []
        workers = []

        for i in range(num_browsers):
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-gpu',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--single-process',
                    '--disable-images',
                ]
            )
            browsers.append(browser)

            worker = BrowserWorker(i, browser, pages_per_browser)
            await worker.init_context()
            workers.append(worker)

        logger.info(f"🌐 Launched {num_browsers} browsers")

        offset = 0
        processed = 0
        success_count = 0
        start_time = time.time()

        # Round-robin assignment of tenders to workers
        worker_idx = 0

        try:
            while offset < total:
                remaining = (max_tenders - processed) if max_tenders else total - offset
                actual_batch = min(batch_size, remaining)
                if actual_batch <= 0:
                    break

                batch = get_pending_tenders(conn, actual_batch, offset)
                if not batch:
                    break

                logger.info(f"📦 Batch: {len(batch)} tenders (offset {offset:,})")

                # Create tasks distributed across workers
                tasks = []
                for tender in batch:
                    worker = workers[worker_idx % num_browsers]
                    tasks.append(worker.process_tender(tender))
                    worker_idx += 1

                # Process all concurrently
                updates = []
                for coro in asyncio.as_completed(tasks):
                    update = await coro
                    updates.append(update)

                    if update.success:
                        success_count += 1

                    processed += 1

                    if processed % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = processed / elapsed if elapsed > 0 else 0
                        eta = (total - processed) / rate if rate > 0 else 0
                        pct = 100 * processed / total
                        success_pct = 100 * success_count / processed if processed else 0
                        logger.info(
                            f"⏳ {processed:,}/{total:,} ({pct:.1f}%) | "
                            f"✅ {success_count:,} ({success_pct:.0f}%) | "
                            f"🚀 {rate:.1f}/sec | "
                            f"⏰ ETA: {eta/3600:.1f}h"
                        )

                update_db(conn, updates)
                offset += actual_batch

                if max_tenders and processed >= max_tenders:
                    break

        finally:
            # Cleanup
            for worker in workers:
                await worker.close()
            for browser in browsers:
                await browser.close()

    conn.close()

    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0
    success_pct = 100 * success_count / processed if processed else 0

    logger.info(f"""
╔══════════════════════════════════════╗
║     🎉 BACKFILL COMPLETE! 🎉        ║
╠══════════════════════════════════════╣
║ Processed: {processed:>15,} tenders ║
║ Successful: {success_count:>14,} ({success_pct:.0f}%) ║
║ Time: {elapsed/3600:>19.2f} hours  ║
║ Rate: {rate:>19.1f} /sec   ║
╚══════════════════════════════════════╝
""")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TURBO backfill with multiple browsers')
    parser.add_argument('--browsers', type=int, default=6, help='Number of browsers (default 6)')
    parser.add_argument('--pages-per-browser', type=int, default=5, help='Concurrent pages per browser (default 5)')
    parser.add_argument('--batch', type=int, default=200, help='Database batch size')
    parser.add_argument('--max', type=int, default=None, help='Max tenders to process')

    args = parser.parse_args()

    asyncio.run(run_backfill(
        num_browsers=args.browsers,
        pages_per_browser=args.pages_per_browser,
        batch_size=args.batch,
        max_tenders=args.max
    ))
