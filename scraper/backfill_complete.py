#!/usr/bin/env python3
"""
Complete backfill: actual_value + document URLs.

Extracts:
1. actual_value_mkd from tender page
2. Document URLs from the documents tab
3. Inserts documents into documents table

Usage:
    python3 backfill_complete.py --browsers 3 --pages-per-browser 3 --batch 50
"""

import os
import sys
import asyncio
import logging
import argparse
import re
import uuid
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from playwright.async_api import async_playwright, Browser, Page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backfill_complete.log')
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

# CSS selectors for actual_value
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
class DocumentInfo:
    """Document extracted from tender page."""
    file_name: str
    file_url: str
    doc_type: str = "document"


@dataclass
class TenderUpdate:
    """Result of processing a tender."""
    tender_id: str
    dossier_id: str
    actual_value_mkd: Optional[float] = None
    num_bidders: Optional[int] = None
    documents: List[DocumentInfo] = field(default_factory=list)
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


def categorize_document(filename: str) -> str:
    """Categorize document based on filename."""
    fn = filename.lower()

    if any(x in fn for x in ['одлука', 'odluka', 'decision', 'award']):
        return 'award_decision'
    if any(x in fn for x in ['договор', 'dogovor', 'contract']):
        return 'contract'
    if any(x in fn for x in ['спецификација', 'tehnicka', 'specifikacija', 'technical']):
        return 'technical_specs'
    if any(x in fn for x in ['понуда', 'ponuda', 'bid', 'offer']):
        return 'bid_docs'
    if any(x in fn for x in ['финанси', 'finansi', 'budget', 'цена', 'cena', 'price']):
        return 'financial_docs'
    if any(x in fn for x in ['документација', 'dokumentacija', 'tender']):
        return 'tender_docs'

    return 'other'


async def extract_tender_data(page: Page, url: str, click_docs_tab: bool = True) -> Tuple[Optional[float], Optional[int], List[DocumentInfo], Optional[str]]:
    """
    Extract actual_value, bidders, and document URLs from tender page.
    """
    try:
        # Navigate to the tender page
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)

        # Wait for Angular content
        try:
            await page.wait_for_selector('.dosie-value', timeout=12000)
        except:
            pass

        await asyncio.sleep(0.5)

        # Extract actual_value
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

        # Extract bidder count
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

        # Extract document URLs
        documents = []

        if click_docs_tab:
            # Try to click on the Documents tab
            docs_tab_selectors = [
                'a:has-text("Документација")',
                'a:has-text("документација")',
                'a[href*="documents"]',
                '.nav-tabs a:nth-child(2)',
                'a:has-text("Documents")',
            ]

            for selector in docs_tab_selectors:
                try:
                    tab = await page.query_selector(selector)
                    if tab:
                        await tab.click()
                        await asyncio.sleep(1)  # Wait for tab content to load
                        break
                except:
                    continue

        # Look for document links (PDFs)
        doc_link_selectors = [
            'a[href*=".pdf"]',
            'a[href*="/Download/"]',
            'a[href*="GetFile"]',
            'a[ng-click*="download"]',
            '.document-list a',
            'table.documents a',
        ]

        seen_urls = set()
        for selector in doc_link_selectors:
            try:
                links = await page.query_selector_all(selector)
                for link in links[:20]:  # Limit to 20 docs per tender
                    href = await link.get_attribute('href')
                    if not href:
                        continue

                    # Make absolute URL
                    if href.startswith('/'):
                        href = 'https://e-nabavki.gov.mk' + href
                    elif not href.startswith('http'):
                        continue

                    # Skip external sites
                    if 'ohridskabanka.mk' in href:
                        continue

                    # Skip duplicates
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # Get filename
                    text = await link.text_content()
                    filename = text.strip() if text else href.split('/')[-1]

                    documents.append(DocumentInfo(
                        file_name=filename[:255],
                        file_url=href[:1000],
                        doc_type=categorize_document(filename)
                    ))
            except:
                continue

        return actual_value, num_bidders, documents, None

    except Exception as e:
        return None, None, [], str(e)[:100]


class BrowserWorker:
    """Worker with its own browser context."""

    def __init__(self, worker_id: int, browser: Browser, max_pages: int = 3):
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
        """Process a single tender."""
        async with self.semaphore:
            tender_id = tender['tender_id']
            dossier_id = tender['dossier_id']
            url = tender['source_url']

            # Fix URL - go to main tender page (not a specific tab)
            if '/dossie/' in url:
                # Remove tab number if present
                url = re.sub(r'/dossie/([^/]+)/?.*$', r'/dossie/\1', url)

            page = None
            try:
                page = await self.context.new_page()
                value, bidders, docs, error = await extract_tender_data(page, url, click_docs_tab=True)

                self.processed += 1
                success = (value is not None) or (len(docs) > 0)
                if success:
                    self.successes += 1

                return TenderUpdate(
                    tender_id=tender_id,
                    dossier_id=dossier_id,
                    actual_value_mkd=value,
                    num_bidders=bidders,
                    documents=docs,
                    success=success,
                    error=error
                )
            except Exception as e:
                self.processed += 1
                return TenderUpdate(
                    tender_id=tender_id,
                    dossier_id=dossier_id,
                    success=False,
                    error=str(e)[:100]
                )
            finally:
                if page:
                    try:
                        await page.close()
                    except:
                        pass

    async def close(self):
        if self.context:
            try:
                await self.context.close()
            except:
                pass


def get_pending_tenders(conn, batch_size: int, offset: int) -> List[Dict]:
    """Get tenders that need processing."""
    # Get tenders missing actual_value OR missing documents
    query = f"""
        SELECT t.tender_id, t.dossier_id, t.source_url
        FROM tenders t
        LEFT JOIN (
            SELECT tender_id, COUNT(*) as doc_count
            FROM documents
            GROUP BY tender_id
        ) d ON t.tender_id = d.tender_id
        WHERE t.source_url LIKE '%%e-nabavki%%'
          AND t.dossier_id IS NOT NULL
          AND (t.actual_value_mkd IS NULL OR COALESCE(d.doc_count, 0) = 0)
        ORDER BY t.tender_id
        LIMIT {batch_size} OFFSET {offset}
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return cur.fetchall()


def update_tenders_batch(conn, updates: List[TenderUpdate]):
    """Update tenders and insert documents."""
    if not updates:
        return

    # Update tender values
    value_updates = [(u.actual_value_mkd, u.num_bidders, u.tender_id)
                     for u in updates if u.actual_value_mkd]

    if value_updates:
        query = """
            UPDATE tenders
            SET actual_value_mkd = COALESCE(%s, actual_value_mkd),
                num_bidders = COALESCE(%s, num_bidders)
            WHERE tender_id = %s
        """
        with conn.cursor() as cur:
            execute_batch(cur, query, value_updates, page_size=100)
        logger.info(f"✅ Updated {len(value_updates)} tender values")

    # Insert documents (skip existing)
    doc_inserts = []
    for u in updates:
        for doc in u.documents:
            doc_inserts.append((
                str(uuid.uuid4()),  # doc_id
                u.tender_id,
                doc.file_name,
                doc.file_url,
                doc.doc_type,
                'pending',  # extraction_status
            ))

    if doc_inserts:
        query = """
            INSERT INTO documents (doc_id, tender_id, file_name, file_url, doc_type, extraction_status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tender_id, file_url) DO NOTHING
        """
        with conn.cursor() as cur:
            execute_batch(cur, query, doc_inserts, page_size=100)
        logger.info(f"📄 Inserted up to {len(doc_inserts)} documents")

    conn.commit()


async def run_backfill(num_browsers: int, pages_per_browser: int, batch_size: int, max_tenders: int = None):
    """Main backfill function."""
    total_workers = num_browsers * pages_per_browser
    logger.info(f"🚀 Starting COMPLETE backfill: {num_browsers} browsers × {pages_per_browser} pages")
    logger.info(f"📦 Extracting: actual_value + document URLs")

    conn = psycopg2.connect(**DB_CONFIG)
    logger.info("📦 Connected to database")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM tenders t
            LEFT JOIN (SELECT tender_id, COUNT(*) as doc_count FROM documents GROUP BY tender_id) d
            ON t.tender_id = d.tender_id
            WHERE t.source_url LIKE '%e-nabavki%'
              AND t.dossier_id IS NOT NULL
              AND (t.actual_value_mkd IS NULL OR COALESCE(d.doc_count, 0) = 0)
        """)
        total = cur.fetchone()[0]

    logger.info(f"📊 Tenders needing processing: {total:,}")

    if max_tenders:
        total = min(total, max_tenders)
        logger.info(f"⚡ Limited to {max_tenders:,} tenders")

    async with async_playwright() as p:
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
                ]
            )
            browsers.append(browser)

            worker = BrowserWorker(i, browser, pages_per_browser)
            await worker.init_context()
            workers.append(worker)

        logger.info(f"🌐 Launched {num_browsers} browsers")

        offset = 0
        processed = 0
        value_count = 0
        doc_count = 0
        start_time = time.time()
        worker_idx = 0

        try:
            while processed < total:
                remaining = (max_tenders - processed) if max_tenders else total - processed
                actual_batch = min(batch_size, remaining)
                if actual_batch <= 0:
                    break

                batch = get_pending_tenders(conn, actual_batch, offset)
                if not batch:
                    logger.info("No more tenders to process")
                    break

                logger.info(f"📦 Batch: {len(batch)} tenders")

                tasks = []
                for tender in batch:
                    worker = workers[worker_idx % num_browsers]
                    tasks.append(worker.process_tender(tender))
                    worker_idx += 1

                updates = []
                for coro in asyncio.as_completed(tasks):
                    try:
                        update = await coro
                        updates.append(update)

                        if update.actual_value_mkd:
                            value_count += 1
                        doc_count += len(update.documents)

                        processed += 1

                        if processed % 50 == 0:
                            elapsed = time.time() - start_time
                            rate = processed / elapsed if elapsed > 0 else 0
                            eta = (total - processed) / rate if rate > 0 else 0
                            logger.info(
                                f"⏳ {processed:,}/{total:,} ({100*processed/total:.1f}%) | "
                                f"💰 {value_count} values | 📄 {doc_count} docs | "
                                f"🚀 {rate:.1f}/sec | ⏰ ETA: {eta/3600:.1f}h"
                            )
                    except Exception as e:
                        logger.error(f"Task error: {e}")
                        processed += 1

                update_tenders_batch(conn, updates)
                offset += actual_batch

        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            for worker in workers:
                await worker.close()
            for browser in browsers:
                try:
                    await browser.close()
                except:
                    pass

    conn.close()

    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0

    logger.info(f"""
╔══════════════════════════════════════════╗
║     🎉 COMPLETE BACKFILL DONE! 🎉       ║
╠══════════════════════════════════════════╣
║ Processed: {processed:>20,} tenders    ║
║ Values extracted: {value_count:>13,}          ║
║ Documents found: {doc_count:>14,}           ║
║ Time: {elapsed/3600:>25.2f} hours     ║
║ Rate: {rate:>25.1f} /sec      ║
╚══════════════════════════════════════════╝
""")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Complete backfill: values + documents')
    parser.add_argument('--browsers', type=int, default=3, help='Number of browsers')
    parser.add_argument('--pages-per-browser', type=int, default=3, help='Concurrent pages per browser')
    parser.add_argument('--batch', type=int, default=50, help='Database batch size')
    parser.add_argument('--max', type=int, default=None, help='Max tenders to process')

    args = parser.parse_args()

    asyncio.run(run_backfill(
        num_browsers=args.browsers,
        pages_per_browser=args.pages_per_browser,
        batch_size=args.batch,
        max_tenders=args.max
    ))
