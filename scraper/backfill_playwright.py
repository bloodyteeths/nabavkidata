#!/usr/bin/env python3
"""
ULTRA-FAST parallel backfill script using Playwright (async).

Optimized for EC2 with 3.8GB RAM:
- Uses Playwright async with browser pool
- 15 concurrent contexts (each ~100MB)
- Estimated: 15 workers × 15 sec/page = 3,600 tenders/hour
- 197,970 ÷ 3,600 = ~55 hours

Usage:
    python3 backfill_playwright.py --workers 15 --batch 500
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

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backfill_pw.log')
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

# XPath patterns for extracting actual_value
ACTUAL_VALUE_SELECTORS = [
    "label[label-for='ASSIGNED CONTRACT VALUE WITHOUT VAT'] + label.dosie-value",
    "label[label-for='ASSIGNED CONTRACT VALUE DOSSIE'] + label.dosie-value",
    "label[label-for*='ASSIGNED CONTRACT VALUE'] + label.dosie-value",
]

BIDDER_COUNT_SELECTORS = [
    "label[label-for='TENDERER COUNT'] + label.dosie-value",
    "label[label-for*='TENDERER'] + label.dosie-value",
]


@dataclass
class TenderUpdate:
    """Represents a tender update."""
    tender_id: str
    dossier_id: str
    actual_value_mkd: Optional[float] = None
    num_bidders: Optional[int] = None
    extraction_success: bool = False
    error_message: Optional[str] = None


def parse_value(text: str) -> Optional[float]:
    """Parse monetary value from text."""
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
    except (ValueError, TypeError):
        pass
    return None


def parse_bidder_count(text: str) -> Optional[int]:
    """Parse bidder count from text."""
    if not text:
        return None
    match = re.search(r'(\d+)', text)
    if match:
        count = int(match.group(1))
        if 0 <= count <= 1000:
            return count
    return None


async def extract_tender_data(page: Page, url: str) -> Tuple[Optional[float], Optional[int], Optional[str]]:
    """Navigate to tender page and extract data."""
    try:
        # Navigate with shorter timeout
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)

        # Wait for Angular to load content
        try:
            await page.wait_for_selector('.dosie-value', timeout=15000)
        except:
            return None, None, "No dosie-value found"

        # Brief wait for data binding
        await asyncio.sleep(0.5)

        # Extract actual_value
        actual_value = None
        for selector in ACTUAL_VALUE_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    text = await elem.text_content()
                    if text and text.strip() not in ['/', '-', '']:
                        value = parse_value(text)
                        if value:
                            actual_value = value
                            break
                if actual_value:
                    break
            except:
                continue

        # Extract bidder count
        num_bidders = None
        for selector in BIDDER_COUNT_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    text = await elem.text_content()
                    if text and text.strip() not in ['/', '-', '']:
                        count = parse_bidder_count(text)
                        if count is not None:
                            num_bidders = count
                            break
                if num_bidders is not None:
                    break
            except:
                continue

        return actual_value, num_bidders, None

    except Exception as e:
        return None, None, str(e)[:100]


def get_pending_tenders(conn, batch_size: int, offset: int) -> List[Dict]:
    """Get batch of tenders that need extraction."""
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


def update_tenders_batch(conn, updates: List[TenderUpdate]):
    """Batch update tenders."""
    if not updates:
        return
    success_updates = [(u.actual_value_mkd, u.num_bidders, u.tender_id)
                       for u in updates if u.extraction_success and u.actual_value_mkd]
    if success_updates:
        query = """
            UPDATE tenders
            SET actual_value_mkd = %s, num_bidders = COALESCE(%s, num_bidders)
            WHERE tender_id = %s
        """
        with conn.cursor() as cur:
            execute_batch(cur, query, success_updates, page_size=100)
        conn.commit()
        logger.info(f"Updated {len(success_updates)} tenders")


async def process_tender(context: BrowserContext, tender: Dict, semaphore: asyncio.Semaphore) -> TenderUpdate:
    """Process a single tender."""
    async with semaphore:
        tender_id = tender['tender_id']
        dossier_id = tender['dossier_id']
        url = tender['source_url']

        # Ensure URL goes to the contract tab
        if '/dossie/' in url and not url.endswith('/14'):
            url = re.sub(r'/dossie/([^/]+)/?.*$', r'/dossie/\1/14', url)

        page = None
        try:
            page = await context.new_page()
            actual_value, num_bidders, error = await extract_tender_data(page, url)

            return TenderUpdate(
                tender_id=tender_id,
                dossier_id=dossier_id,
                actual_value_mkd=actual_value,
                num_bidders=num_bidders,
                extraction_success=(actual_value is not None),
                error_message=error
            )
        except Exception as e:
            return TenderUpdate(
                tender_id=tender_id,
                dossier_id=dossier_id,
                extraction_success=False,
                error_message=str(e)[:100]
            )
        finally:
            if page:
                await page.close()


async def run_backfill_async(workers: int, batch_size: int, max_tenders: int = None):
    """Main async backfill function."""
    logger.info(f"Starting Playwright backfill with {workers} workers")

    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    logger.info("Connected to database")

    # Get total count
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM tenders
            WHERE source_url LIKE '%e-nabavki%'
              AND actual_value_mkd IS NULL
              AND dossier_id IS NOT NULL
        """)
        total = cur.fetchone()[0]

    logger.info(f"Total tenders to process: {total}")

    if max_tenders:
        total = min(total, max_tenders)
        logger.info(f"Limited to {max_tenders} tenders")

    async with async_playwright() as p:
        # Launch browser with optimizations
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-gpu',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--disable-images',
            ]
        )
        logger.info("Browser launched")

        # Create browser context
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            java_script_enabled=True,
        )

        # Semaphore to limit concurrent pages
        semaphore = asyncio.Semaphore(workers)

        offset = 0
        processed = 0
        success_count = 0
        start_time = time.time()

        try:
            while offset < total:
                # Calculate batch size
                remaining = (max_tenders - processed) if max_tenders else total - offset
                actual_batch_size = min(batch_size, remaining)
                if actual_batch_size <= 0:
                    break

                # Get batch
                batch = get_pending_tenders(conn, actual_batch_size, offset)
                if not batch:
                    break

                logger.info(f"Processing batch: {len(batch)} tenders (offset {offset})")

                # Process batch concurrently
                tasks = [process_tender(context, t, semaphore) for t in batch]
                updates = []

                for coro in asyncio.as_completed(tasks):
                    update = await coro
                    updates.append(update)

                    if update.extraction_success:
                        success_count += 1

                    processed += 1

                    # Progress update every 50
                    if processed % 50 == 0:
                        elapsed = time.time() - start_time
                        rate = processed / elapsed if elapsed > 0 else 0
                        eta = (total - processed) / rate if rate > 0 else 0
                        logger.info(
                            f"Progress: {processed}/{total} ({100*processed/total:.1f}%) | "
                            f"Success: {success_count} ({100*success_count/processed:.1f}%) | "
                            f"Rate: {rate:.2f}/sec | ETA: {eta/3600:.1f}h"
                        )

                # Update database
                update_tenders_batch(conn, updates)

                offset += actual_batch_size

                if max_tenders and processed >= max_tenders:
                    break

        finally:
            await context.close()
            await browser.close()

    conn.close()

    elapsed = time.time() - start_time
    logger.info(f"""
=== BACKFILL COMPLETE ===
Processed: {processed} tenders
Successful: {success_count} ({100*success_count/processed:.1f}% if processed else 0)
Time: {elapsed/3600:.2f} hours
Rate: {processed/elapsed:.2f} tenders/sec
""")


def run_backfill(workers: int, batch_size: int, max_tenders: int = None):
    """Sync wrapper for async backfill."""
    asyncio.run(run_backfill_async(workers, batch_size, max_tenders))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill actual_value using Playwright')
    parser.add_argument('--workers', type=int, default=15, help='Concurrent pages (default 15)')
    parser.add_argument('--batch', type=int, default=500, help='Database batch size')
    parser.add_argument('--max', type=int, default=None, help='Max tenders to process')

    args = parser.parse_args()

    run_backfill(
        workers=args.workers,
        batch_size=args.batch,
        max_tenders=args.max
    )
