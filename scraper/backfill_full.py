#!/usr/bin/env python3
"""
FULL backfill: All 57 tender fields + documents + bidders.

Extracts everything the Scrapy spider extracts, but faster using parallel Playwright.

Usage:
    python3 backfill_full.py --browsers 3 --pages-per-browser 2 --batch 50
"""

import os
import sys
import asyncio
import logging
import argparse
import re
import json
import uuid
from typing import List, Dict, Optional, Tuple, Any
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
        logging.FileHandler('backfill_full.log')
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', 5432)),
    'database': os.environ.get('POSTGRES_DB', 'nabavkidata'),
    'user': os.environ.get('POSTGRES_USER', 'nabavki_user'),
    'password': os.environ.get('POSTGRES_PASSWORD', ''),
}

# ============================================================================
# FIELD EXTRACTION PATTERNS (from Scrapy spider)
# ============================================================================

FIELD_SELECTORS = {
    # NOTE: tender_id is NOT extracted - we use the database tender_id
    'title': [
        'label[label-for="SUBJECT:"] + label.dosie-value',
        'label[label-for*="SUBJECT"] + label.dosie-value',
    ],
    'description': [
        'label[label-for="DETAIL DESCRIPTION OF THE ITEM TO BE PROCURED DOSIE"] + label.dosie-value',
        'label[label-for="DESCRIPTION DOSIE"] + label.dosie-value',
    ],
    'procuring_entity': [
        'label[label-for="CONTRACTING INSTITUTION NAME DOSIE"] + label.dosie-value',
        'label[label-for="CONTRACTING AUTHORITY NAME DOSIE"] + label.dosie-value',
    ],
    'category': [
        'label[label-for="TYPE OF PROCUREMENT DOSIE"] + label.dosie-value',
        'label[label-for="TYPE OF CONTRACT DOSIE"] + label.dosie-value',
    ],
    'procedure_type': [
        'label[label-for="TYPE OF CALL:"] + label.dosie-value',
        'label[label-for="PROCEDURE TYPE DOSIE"] + label.dosie-value',
    ],
    'winner': [
        'label[label-for="NAME OF CONTACT OF PROCUREMENT DOSSIE"] + label.dosie-value',
        'label[label-for="WINNER NAME DOSIE"] + label.dosie-value',
        'label[label-for="SELECTED BIDDER DOSIE"] + label.dosie-value',
    ],
    'contract_duration': [
        'label[label-for="PERIOD IN MONTHS"] + label.dosie-value',
        'label[label-for="CONTRACT DURATION DOSIE"] + label.dosie-value',
    ],
    'contact_person': [
        'label[label-for="CONTRACTING INSTITUTION CONTACT PERSON DOSIE"] + label.dosie-value',
        'label[label-for="CONTACT PERSON DOSIE"] + label.dosie-value',
    ],
    'contact_email': [
        'label[label-for="CONTRACTING INSTITUTION EMAIL DOSIE"] + label.dosie-value',
        'label[label-for="EMAIL DOSIE"] + label.dosie-value',
    ],
    'contact_phone': [
        'label[label-for="CONTRACTING INSTITUTION PHONE DOSIE"] + label.dosie-value',
        'label[label-for="PHONE DOSIE"] + label.dosie-value',
    ],
    'evaluation_method': [
        'label[label-for="CRITERION FOR ASSIGNMENT OF CONTRACT DOSIE"] + label.dosie-value',
        'label[label-for="AWARD CRITERIA DOSIE"] + label.dosie-value',
    ],
    'delivery_location': [
        'label[label-for="DELIVERY OF GOODS LOCATION OF WORKS DOSIE"] + label.dosie-value',
    ],
    'num_bidders': [
        'label[label-for="NUMBER OF OFFERS DOSSIE"] + label.dosie-value',
    ],
    'has_lots': [
        'label[label-for="CAN BE DIVEDED ON LOTS DOSIE"] + label.dosie-value',
    ],
    'contracting_entity_category': [
        'label[label-for="CATEGORY OF CONTRACTING INSTITUTION AND ITS MAIN ROLE DOSSIE"] + label.dosie-value',
    ],
    'procurement_holder': [
        'label[label-for="NAME OF CONTACT OF PROCUREMENT DOSSIE"] + label.dosie-value',
    ],
}

DATE_SELECTORS = {
    'publication_date': [
        'label[label-for="ANNOUNCEMENT DATE DOSSIE"] + label.dosie-value',
        'label[label-for="PUBLICATION DATE DOSIE"] + label.dosie-value',
    ],
    'opening_date': [
        'label[label-for*="PUBLIC OPENING"] + label.dosie-value',
        'label[label-for="DATE AND HOUR OF THE PUBLIC OPENING DOSSIE"] + label.dosie-value',
        'label[label-for="DEAD LINE DATE DOSSIE"] + label.dosie-value',
    ],
    'closing_date': [
        'label[label-for="DEAD LINE DATE DOSSIE"] + label.dosie-value',
        'label[label-for="DEADLINE DATE DOSIE"] + label.dosie-value',
    ],
    'contract_signing_date': [
        'label[label-for="DATE OF CONTRACT SIGNING DOSIE"] + label.dosie-value',
        'label[label-for="CONTRACT DATE DOSIE"] + label.dosie-value',
    ],
    'bureau_delivery_date': [
        'label[label-for="DATE OF DELIVERY TO BUREAU DOSSIE"] + label.dosie-value',
    ],
}

VALUE_SELECTORS = {
    'estimated_value_mkd': [
        'label[label-for="ESTIMATED VALUE WITHOUT VAT"] + label.dosie-value',
        'label[label-for="ESTIMATED VALUE DOSIE"] + label.dosie-value',
        'label[label-for*="ESTIMATED VALUE"] + label.dosie-value',
    ],
    'actual_value_mkd': [
        'label[label-for="ASSIGNED CONTRACT VALUE WITHOUT VAT"] + label.dosie-value',
        'label[label-for="ASSIGNED CONTRACT VALUE DOSSIE"] + label.dosie-value',
        'label[label-for*="ASSIGNED CONTRACT VALUE"] + label.dosie-value',
        'label[label-for*="CONTRACT VALUE"] + label.dosie-value',
    ],
    'security_deposit_mkd': [
        'label[label-for="SECURITY DEPOSIT DOSIE"] + label.dosie-value',
        'label[label-for*="SECURITY DEPOSIT"] + label.dosie-value',
    ],
    'performance_guarantee_mkd': [
        'label[label-for="PERFORMANCE GUARANTEE DOSIE"] + label.dosie-value',
        'label[label-for*="PERFORMANCE GUARANTEE"] + label.dosie-value',
    ],
    'highest_bid_mkd': [
        'label[label-for="HIGEST OFFER VALUE DOSSIE"] + label.dosie-value',
    ],
    'lowest_bid_mkd': [
        'label[label-for="LOWEST OFFER VALUE DOSSIE"] + label.dosie-value',
    ],
}


@dataclass
class DocumentInfo:
    file_name: str
    file_url: str
    doc_type: str = "document"


@dataclass
class TenderData:
    """All extracted tender data."""
    tender_id: str
    dossier_id: str
    # Text fields
    title: Optional[str] = None
    description: Optional[str] = None
    procuring_entity: Optional[str] = None
    category: Optional[str] = None
    procedure_type: Optional[str] = None
    winner: Optional[str] = None
    contract_duration: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    evaluation_method: Optional[str] = None
    delivery_location: Optional[str] = None
    contracting_entity_category: Optional[str] = None
    procurement_holder: Optional[str] = None
    cpv_code: Optional[str] = None
    # Dates
    publication_date: Optional[str] = None
    opening_date: Optional[str] = None
    closing_date: Optional[str] = None
    contract_signing_date: Optional[str] = None
    bureau_delivery_date: Optional[str] = None
    # Values
    estimated_value_mkd: Optional[float] = None
    actual_value_mkd: Optional[float] = None
    security_deposit_mkd: Optional[float] = None
    performance_guarantee_mkd: Optional[float] = None
    highest_bid_mkd: Optional[float] = None
    lowest_bid_mkd: Optional[float] = None
    # Numbers
    num_bidders: Optional[int] = None
    has_lots: Optional[bool] = None
    # Complex data
    documents: List[DocumentInfo] = field(default_factory=list)
    bidders_json: Optional[str] = None
    raw_html: Optional[str] = None
    # Status
    success: bool = False
    error: Optional[str] = None


def parse_value(text: str) -> Optional[float]:
    """Parse monetary value from text."""
    if not text:
        return None
    text = text.strip()
    # Remove currency and non-numeric chars
    text = re.sub(r'[A-Za-zА-Яа-я\s\*\(\)]', '', text)
    text = text.replace('МКД', '').replace('MKD', '').replace('ден', '').replace('EUR', '')
    text = text.replace('.', '').replace(',', '.')  # European format
    try:
        value = float(text)
        if 0 < value < 100_000_000_000:
            return value
    except:
        pass
    return None


def parse_date(text: str) -> Optional[str]:
    """Parse date from various formats to YYYY-MM-DD."""
    if not text:
        return None
    text = text.strip()

    # Common date patterns
    patterns = [
        (r'(\d{2})\.(\d{2})\.(\d{4})', lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),  # DD.MM.YYYY
        (r'(\d{4})-(\d{2})-(\d{2})', lambda m: m.group(0)),  # YYYY-MM-DD
        (r'(\d{2})/(\d{2})/(\d{4})', lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),  # DD/MM/YYYY
    ]

    for pattern, formatter in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return formatter(match)
            except:
                continue
    return None


def parse_int(text: str) -> Optional[int]:
    """Parse integer from text."""
    if not text:
        return None
    match = re.search(r'(\d+)', text.strip())
    if match:
        return int(match.group(1))
    return None


def extract_cpv_code(html: str) -> Optional[str]:
    """Extract CPV code using regex pattern matching."""
    # CPV codes are 8-digit codes, optionally with -digit suffix
    cpv_pattern = r'\b(\d{8}(?:-\d)?)\b'
    matches = re.findall(cpv_pattern, html)

    for match in matches:
        # Valid CPV division codes are 01-98
        if match.startswith('0000') or match.startswith('9999'):
            continue
        try:
            division = int(match[:2])
            if 1 <= division <= 98:
                return match
        except ValueError:
            continue
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
    return 'tender_docs'


async def extract_field(page: Page, selectors: List[str]) -> Optional[str]:
    """Extract text from first matching selector."""
    for selector in selectors:
        try:
            elem = await page.query_selector(selector)
            if elem:
                text = await elem.text_content()
                if text and text.strip() and text.strip() not in ['/', '-', '']:
                    return text.strip()
        except:
            continue
    return None


async def extract_documents(page: Page) -> List[DocumentInfo]:
    """Extract document URLs from the page."""
    documents = []
    seen_urls = set()

    # Try to click documents tab first
    doc_tab_selectors = [
        'a:has-text("Документација")',
        'a:has-text("документација")',
        'a[href*="documents"]',
        '.nav-tabs a:nth-child(2)',
    ]

    for selector in doc_tab_selectors:
        try:
            tab = await page.query_selector(selector)
            if tab:
                await tab.click()
                await asyncio.sleep(1)
                break
        except:
            continue

    # Extract document links
    link_selectors = [
        'a[href*="Download"]',
        'a[href*=".pdf"]',
        'a[href*="/File/"]',
        'a[href*="GetFile"]',
        'a[href*="DownloadDoc"]',
        'a[href*="DownloadPublicFile"]',
    ]

    for selector in link_selectors:
        try:
            links = await page.query_selector_all(selector)
            for link in links[:20]:
                href = await link.get_attribute('href')
                if not href:
                    continue

                if href.startswith('/'):
                    href = 'https://e-nabavki.gov.mk' + href
                elif not href.startswith('http'):
                    continue

                if 'ohridskabanka' in href.lower() or href in seen_urls:
                    continue
                seen_urls.add(href)

                text = await link.text_content()
                filename = text.strip() if text else href.split('/')[-1]

                documents.append(DocumentInfo(
                    file_name=filename[:255],
                    file_url=href[:1000],
                    doc_type=categorize_document(filename)
                ))
        except:
            continue

    return documents


async def extract_tender_full(page: Page, url: str, tender_id: str, dossier_id: str) -> TenderData:
    """Extract ALL fields from a tender page."""
    data = TenderData(tender_id=tender_id, dossier_id=dossier_id)

    try:
        # Navigate to tender page
        await page.goto(url, wait_until='domcontentloaded', timeout=25000)

        # Wait for Angular content
        try:
            await page.wait_for_selector('.dosie-value', timeout=15000)
        except:
            pass

        await asyncio.sleep(0.5)

        # Get page HTML for CPV extraction and raw storage
        html = await page.content()
        data.raw_html = html[:50000] if len(html) > 50000 else html  # Limit size

        # Extract text fields
        for field_name, selectors in FIELD_SELECTORS.items():
            value = await extract_field(page, selectors)
            if value:
                setattr(data, field_name, value)

        # Extract dates
        for field_name, selectors in DATE_SELECTORS.items():
            text = await extract_field(page, selectors)
            if text:
                date_val = parse_date(text)
                if date_val:
                    setattr(data, field_name, date_val)

        # Extract monetary values
        for field_name, selectors in VALUE_SELECTORS.items():
            text = await extract_field(page, selectors)
            if text:
                value = parse_value(text)
                if value:
                    setattr(data, field_name, value)

        # Parse num_bidders as int
        if data.num_bidders and isinstance(data.num_bidders, str):
            data.num_bidders = parse_int(data.num_bidders)

        # Parse has_lots as bool
        if data.has_lots and isinstance(data.has_lots, str):
            data.has_lots = data.has_lots.lower() in ('да', 'yes', 'true')

        # Extract CPV code from HTML
        data.cpv_code = extract_cpv_code(html)

        # Extract documents
        data.documents = await extract_documents(page)

        data.success = True

    except Exception as e:
        data.error = str(e)[:200]

    return data


class BrowserWorker:
    """Worker with browser context for parallel processing."""

    def __init__(self, worker_id: int, browser: Browser, max_pages: int = 2):
        self.worker_id = worker_id
        self.browser = browser
        self.max_pages = max_pages
        self.semaphore = asyncio.Semaphore(max_pages)
        self.context = None

    async def init_context(self):
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            java_script_enabled=True,
        )

    async def process_tender(self, tender: Dict) -> TenderData:
        """Process a single tender."""
        async with self.semaphore:
            tender_id = tender['tender_id']
            dossier_id = tender['dossier_id']
            url = tender['source_url']

            # Use main tender page URL
            if '/dossie/' in url:
                url = re.sub(r'/dossie/([^/]+)/?.*$', r'/dossie/\1', url)

            page = None
            try:
                page = await self.context.new_page()
                data = await extract_tender_full(page, url, tender_id, dossier_id)
                return data
            except Exception as e:
                return TenderData(
                    tender_id=tender_id,
                    dossier_id=dossier_id,
                    success=False,
                    error=str(e)[:200]
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
    """Get tenders that need full extraction."""
    # Get tenders missing key fields
    query = f"""
        SELECT t.tender_id, t.dossier_id, t.source_url
        FROM tenders t
        WHERE t.source_url LIKE '%%e-nabavki%%'
          AND t.dossier_id IS NOT NULL
          AND (
            t.actual_value_mkd IS NULL
            OR t.winner IS NULL
            OR t.cpv_code IS NULL
            OR t.opening_date IS NULL
          )
        ORDER BY t.tender_id
        LIMIT {batch_size} OFFSET {offset}
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return cur.fetchall()


def update_tender_batch(conn, updates: List[TenderData]):
    """Update tenders with extracted data."""
    if not updates:
        return

    # Build update query with all fields
    update_data = []
    for u in updates:
        if not u.success:
            continue
        update_data.append((
            u.title,
            u.description,
            u.procuring_entity,
            u.category,
            u.procedure_type,
            u.winner,
            u.contract_duration,
            u.contact_person,
            u.contact_email,
            u.contact_phone,
            u.evaluation_method,
            u.delivery_location,
            u.contracting_entity_category,
            u.cpv_code,
            u.publication_date,
            u.opening_date,
            u.closing_date,
            u.contract_signing_date,
            u.bureau_delivery_date,
            u.estimated_value_mkd,
            u.actual_value_mkd,
            u.security_deposit_mkd,
            u.performance_guarantee_mkd,
            u.highest_bid_mkd,
            u.lowest_bid_mkd,
            u.num_bidders,
            u.has_lots,
            u.tender_id,
        ))

    if update_data:
        query = """
            UPDATE tenders SET
                title = COALESCE(%s, title),
                description = COALESCE(%s, description),
                procuring_entity = COALESCE(%s, procuring_entity),
                category = COALESCE(%s, category),
                procedure_type = COALESCE(%s, procedure_type),
                winner = COALESCE(%s, winner),
                contract_duration = COALESCE(%s, contract_duration),
                contact_person = COALESCE(%s, contact_person),
                contact_email = COALESCE(%s, contact_email),
                contact_phone = COALESCE(%s, contact_phone),
                evaluation_method = COALESCE(%s, evaluation_method),
                delivery_location = COALESCE(%s, delivery_location),
                contracting_entity_category = COALESCE(%s, contracting_entity_category),
                cpv_code = COALESCE(%s, cpv_code),
                publication_date = COALESCE(%s::date, publication_date),
                opening_date = COALESCE(%s::date, opening_date),
                closing_date = COALESCE(%s::date, closing_date),
                contract_signing_date = COALESCE(%s::date, contract_signing_date),
                bureau_delivery_date = COALESCE(%s::date, bureau_delivery_date),
                estimated_value_mkd = COALESCE(%s, estimated_value_mkd),
                actual_value_mkd = COALESCE(%s, actual_value_mkd),
                security_deposit_mkd = COALESCE(%s, security_deposit_mkd),
                performance_guarantee_mkd = COALESCE(%s, performance_guarantee_mkd),
                highest_bid_mkd = COALESCE(%s, highest_bid_mkd),
                lowest_bid_mkd = COALESCE(%s, lowest_bid_mkd),
                num_bidders = COALESCE(%s, num_bidders),
                has_lots = COALESCE(%s, has_lots),
                updated_at = NOW()
            WHERE tender_id = %s
        """
        with conn.cursor() as cur:
            execute_batch(cur, query, update_data, page_size=50)
        logger.info(f"✅ Updated {len(update_data)} tenders")

    # Insert documents
    doc_inserts = []
    for u in updates:
        for doc in u.documents:
            doc_inserts.append((
                str(uuid.uuid4()),
                u.tender_id,
                doc.file_name,
                doc.file_url,
                doc.doc_type,
                'pending',
            ))

    if doc_inserts:
        # Use INSERT with subquery to check for existing docs (partial index workaround)
        query = """
            INSERT INTO documents (doc_id, tender_id, file_name, file_url, doc_type, extraction_status)
            SELECT %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM documents
                WHERE tender_id = %s AND file_url = %s
            )
        """
        # Expand doc_inserts to include duplicate params for WHERE clause
        expanded_inserts = [(d[0], d[1], d[2], d[3], d[4], d[5], d[1], d[3]) for d in doc_inserts]
        with conn.cursor() as cur:
            execute_batch(cur, query, expanded_inserts, page_size=100)
        logger.info(f"📄 Inserted up to {len(doc_inserts)} documents")

    conn.commit()


async def run_backfill(num_browsers: int, pages_per_browser: int, batch_size: int, max_tenders: int = None):
    """Main backfill function."""
    logger.info(f"🚀 Starting FULL backfill: {num_browsers} browsers × {pages_per_browser} pages")
    logger.info(f"📦 Extracting: ALL fields + documents")

    conn = psycopg2.connect(**DB_CONFIG)
    logger.info("📦 Connected to database")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM tenders
            WHERE source_url LIKE '%e-nabavki%'
              AND dossier_id IS NOT NULL
              AND (actual_value_mkd IS NULL OR winner IS NULL OR cpv_code IS NULL OR opening_date IS NULL)
        """)
        total = cur.fetchone()[0]

    logger.info(f"📊 Tenders needing full extraction: {total:,}")

    if max_tenders:
        total = min(total, max_tenders)
        logger.info(f"⚡ Limited to {max_tenders:,} tenders")

    async with async_playwright() as p:
        browsers = []
        workers = []

        for i in range(num_browsers):
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
            )
            browsers.append(browser)
            worker = BrowserWorker(i, browser, pages_per_browser)
            await worker.init_context()
            workers.append(worker)

        logger.info(f"🌐 Launched {num_browsers} browsers")

        offset = 0
        processed = 0
        success_count = 0
        field_counts = {'actual_value': 0, 'winner': 0, 'cpv': 0, 'docs': 0}
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
                        data = await coro
                        updates.append(data)

                        if data.success:
                            success_count += 1
                            if data.actual_value_mkd:
                                field_counts['actual_value'] += 1
                            if data.winner:
                                field_counts['winner'] += 1
                            if data.cpv_code:
                                field_counts['cpv'] += 1
                            field_counts['docs'] += len(data.documents)

                        processed += 1

                        if processed % 25 == 0:
                            elapsed = time.time() - start_time
                            rate = processed / elapsed if elapsed > 0 else 0
                            eta = (total - processed) / rate if rate > 0 else 0
                            logger.info(
                                f"⏳ {processed:,}/{total:,} ({100*processed/total:.1f}%) | "
                                f"💰{field_counts['actual_value']} 🏆{field_counts['winner']} "
                                f"📋{field_counts['cpv']} 📄{field_counts['docs']} | "
                                f"🚀 {rate:.2f}/sec | ⏰ ETA: {eta/3600:.1f}h"
                            )
                    except Exception as e:
                        logger.error(f"Task error: {e}")
                        processed += 1

                update_tender_batch(conn, updates)
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
╔═══════════════════════════════════════════════════╗
║         🎉 FULL BACKFILL COMPLETE! 🎉            ║
╠═══════════════════════════════════════════════════╣
║ Processed: {processed:>25,} tenders            ║
║ Successful: {success_count:>24,} tenders            ║
║ actual_value: {field_counts['actual_value']:>22,}                  ║
║ winner: {field_counts['winner']:>28,}                  ║
║ cpv_code: {field_counts['cpv']:>26,}                  ║
║ documents: {field_counts['docs']:>25,}                  ║
║ Time: {elapsed/3600:>30.2f} hours            ║
║ Rate: {rate:>30.2f} /sec             ║
╚═══════════════════════════════════════════════════╝
""")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Full backfill: all fields + documents')
    parser.add_argument('--browsers', type=int, default=3, help='Number of browsers')
    parser.add_argument('--pages-per-browser', type=int, default=2, help='Concurrent pages per browser')
    parser.add_argument('--batch', type=int, default=50, help='Database batch size')
    parser.add_argument('--max', type=int, default=None, help='Max tenders to process')

    args = parser.parse_args()

    asyncio.run(run_backfill(
        num_browsers=args.browsers,
        pages_per_browser=args.pages_per_browser,
        batch_size=args.batch,
        max_tenders=args.max
    ))
