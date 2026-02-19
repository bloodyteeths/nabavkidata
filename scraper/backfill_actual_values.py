#!/usr/bin/env python3
"""
ULTRA-FAST parallel backfill script for 197K tenders missing actual_value.

Strategy:
1. We already have 197,548 tender URLs in the database
2. Use 20-40 parallel Selenium browsers (not Playwright - it's faster)
3. Minimal page wait (just wait for Angular to load actual_value)
4. Direct database updates (skip Scrapy overhead)
5. Resume from last position if interrupted

Expected performance:
- 40 browsers × 15 sec/page = 2,400 tenders/hour
- 197,548 ÷ 2,400 = ~82 hours with 40 browsers
- Or ~41 hours with 80 browsers (EC2 limit ~RAM/100MB per browser)

Usage:
    python3 backfill_actual_values.py --workers 40 --batch 1000
"""

import os
import sys
import time
import logging
import argparse
import re
from queue import Queue, Empty
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backfill.log')
    ]
)
logger = logging.getLogger(__name__)

# Database connection (from environment or defaults)
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
    'port': int(os.environ.get('POSTGRES_PORT', 5432)),
    'database': os.environ.get('POSTGRES_DB', 'nabavkidata'),
    'user': os.environ.get('POSTGRES_USER', 'nabavki_user'),
    'password': os.environ.get('POSTGRES_PASSWORD', ''),
}

# XPath patterns for extracting actual_value
ACTUAL_VALUE_XPATHS = [
    "//label[@label-for='ASSIGNED CONTRACT VALUE WITHOUT VAT']/following-sibling::label[contains(@class, 'dosie-value')]",
    "//label[@label-for='ASSIGNED CONTRACT VALUE DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]",
    "//label[contains(@label-for, 'ASSIGNED CONTRACT VALUE')]/following-sibling::label[contains(@class, 'dosie-value')]",
    "//label[contains(text(), 'Вредност на доделен договор')]/following-sibling::label",
    "//label[contains(text(), 'Склучен договор')]/following-sibling::label",
]

BIDDER_COUNT_XPATHS = [
    "//label[@label-for='TENDERER COUNT']/following-sibling::label[contains(@class, 'dosie-value')]",
    "//label[contains(@label-for, 'TENDERER')]/following-sibling::label",
    "//label[contains(text(), 'Број на понуди')]/following-sibling::label",
]


@dataclass
class TenderUpdate:
    """Represents a tender update to be written to DB."""
    tender_id: str
    dossier_id: str
    actual_value_mkd: Optional[float] = None
    num_bidders: Optional[int] = None
    extraction_success: bool = False
    error_message: Optional[str] = None


class BrowserPool:
    """Pool of reusable Chrome browsers for parallel processing."""

    def __init__(self, size: int = 10, headless: bool = True):
        self.size = size
        self.headless = headless
        self.pool = Queue(maxsize=size)
        self.lock = Lock()
        self.created = 0
        self._initialize_pool()

    def _create_driver(self) -> webdriver.Chrome:
        """Create an optimized Chrome driver."""
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')

        # Performance optimizations
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')

        # Disable images and CSS for speed
        prefs = {
            'profile.managed_default_content_settings.images': 2,
            'profile.managed_default_content_settings.stylesheets': 2,
        }
        options.add_experimental_option('prefs', prefs)

        # Block unnecessary resource types
        options.add_argument('--blink-settings=imagesEnabled=false')

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(3)

        return driver

    def _initialize_pool(self):
        """Pre-create some browsers."""
        initial_count = min(5, self.size)  # Start with 5 browsers
        for _ in range(initial_count):
            try:
                driver = self._create_driver()
                self.pool.put(driver)
                self.created += 1
            except Exception as e:
                logger.error(f"Failed to create browser: {e}")

    def get(self, timeout: float = 30) -> webdriver.Chrome:
        """Get a browser from the pool (or create new one)."""
        try:
            return self.pool.get(timeout=timeout)
        except Empty:
            # Pool empty, create new if under limit
            with self.lock:
                if self.created < self.size:
                    try:
                        driver = self._create_driver()
                        self.created += 1
                        return driver
                    except Exception as e:
                        logger.error(f"Failed to create browser: {e}")
                        raise
            # At limit, wait for one to become available
            return self.pool.get(timeout=timeout)

    def release(self, driver: webdriver.Chrome):
        """Return a browser to the pool."""
        try:
            # Clear any stale state
            driver.delete_all_cookies()
            self.pool.put(driver)
        except Exception as e:
            logger.warning(f"Failed to release browser: {e}")
            try:
                driver.quit()
            except:
                pass
            with self.lock:
                self.created -= 1

    def shutdown(self):
        """Shutdown all browsers in the pool."""
        while not self.pool.empty():
            try:
                driver = self.pool.get_nowait()
                driver.quit()
            except:
                pass


def parse_value(text: str) -> Optional[float]:
    """Parse monetary value from text."""
    if not text:
        return None

    # Remove currency symbols and whitespace
    text = text.strip()
    text = re.sub(r'[A-Za-z\s\*\(\)]', '', text)
    text = text.replace('МКД', '').replace('MKD', '').replace('ден', '')
    text = text.replace('.', '').replace(',', '.')  # European number format

    try:
        value = float(text)
        # Sanity check - values should be positive and reasonable
        if 0 < value < 100_000_000_000:  # Up to 100 billion MKD
            return value
    except (ValueError, TypeError):
        pass

    return None


def parse_bidder_count(text: str) -> Optional[int]:
    """Parse bidder count from text."""
    if not text:
        return None

    # Extract first number
    match = re.search(r'(\d+)', text)
    if match:
        count = int(match.group(1))
        if 0 <= count <= 1000:  # Sanity check
            return count

    return None


def extract_tender_data(driver: webdriver.Chrome, url: str) -> Tuple[Optional[float], Optional[int], Optional[str]]:
    """
    Navigate to tender page and extract actual_value and bidder count.
    Returns (actual_value, num_bidders, error_message)
    """
    try:
        # Navigate to the page
        driver.get(url)

        # Wait for Angular to load (look for the main content)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'dosie-value'))
            )
        except TimeoutException:
            return None, None, "Timeout waiting for page load"

        # Brief wait for Angular data binding
        time.sleep(1)

        # Extract actual_value
        actual_value = None
        for xpath in ACTUAL_VALUE_XPATHS:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                for elem in elements:
                    text = elem.text.strip()
                    if text and text not in ['/', '-', '']:
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
        for xpath in BIDDER_COUNT_XPATHS:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                for elem in elements:
                    text = elem.text.strip()
                    if text and text not in ['/', '-', '']:
                        count = parse_bidder_count(text)
                        if count is not None:
                            num_bidders = count
                            break
                if num_bidders is not None:
                    break
            except:
                continue

        return actual_value, num_bidders, None

    except TimeoutException:
        return None, None, "Page load timeout"
    except WebDriverException as e:
        return None, None, f"WebDriver error: {str(e)[:100]}"
    except Exception as e:
        return None, None, f"Unexpected error: {str(e)[:100]}"


def get_pending_tenders(conn, batch_size: int = 1000, offset: int = 0) -> List[Dict]:
    """Get batch of tenders that need actual_value extraction."""
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
    """Batch update tenders with extracted values."""
    if not updates:
        return

    # Separate successful and failed updates
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
        logger.info(f"Updated {len(success_updates)} tenders with actual_value")


def process_tender(browser_pool: BrowserPool, tender: Dict) -> TenderUpdate:
    """Process a single tender - get browser, extract, release browser."""
    tender_id = tender['tender_id']
    dossier_id = tender['dossier_id']
    url = tender['source_url']

    # Ensure URL goes to the awarded/contract tab
    if '/dossie/' in url and not url.endswith('/14'):
        # /14 is typically the awarded contract tab
        url = re.sub(r'/dossie/([^/]+)/?.*$', r'/dossie/\1/14', url)

    driver = None
    try:
        driver = browser_pool.get(timeout=60)
        actual_value, num_bidders, error = extract_tender_data(driver, url)

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
            error_message=str(e)[:200]
        )

    finally:
        if driver:
            browser_pool.release(driver)


def run_backfill(workers: int = 20, batch_size: int = 1000, max_tenders: int = None):
    """Run the parallel backfill process."""
    logger.info(f"Starting backfill with {workers} workers, batch size {batch_size}")

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

    # Initialize browser pool
    browser_pool = BrowserPool(size=workers, headless=True)
    logger.info(f"Initialized browser pool with {workers} browsers")

    # Process in batches
    offset = 0
    processed = 0
    success_count = 0
    start_time = time.time()

    try:
        while offset < total:
            # Calculate actual batch size (respect max_tenders limit)
            remaining = (max_tenders - processed) if max_tenders else total - offset
            actual_batch_size = min(batch_size, remaining)
            if actual_batch_size <= 0:
                break

            # Get batch of tenders
            batch = get_pending_tenders(conn, actual_batch_size, offset)
            if not batch:
                break

            logger.info(f"Processing batch {offset // batch_size + 1}: {len(batch)} tenders")

            # Process batch in parallel
            updates = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(process_tender, browser_pool, t): t for t in batch}

                for future in as_completed(futures):
                    try:
                        update = future.result(timeout=120)
                        updates.append(update)

                        if update.extraction_success:
                            success_count += 1
                            logger.debug(f"✅ {update.tender_id}: {update.actual_value_mkd}")
                        else:
                            logger.debug(f"❌ {update.tender_id}: {update.error_message}")

                        processed += 1

                        # Progress update every 50 tenders
                        if processed % 50 == 0:
                            elapsed = time.time() - start_time
                            rate = processed / elapsed if elapsed > 0 else 0
                            eta = (total - processed) / rate if rate > 0 else 0
                            logger.info(
                                f"Progress: {processed}/{total} ({100*processed/total:.1f}%) | "
                                f"Success: {success_count} ({100*success_count/processed:.1f}%) | "
                                f"Rate: {rate:.1f}/sec | ETA: {eta/3600:.1f}h"
                            )

                    except Exception as e:
                        logger.error(f"Future failed: {e}")

            # Batch update database
            update_tenders_batch(conn, updates)

            offset += batch_size

            if max_tenders and processed >= max_tenders:
                break

    finally:
        browser_pool.shutdown()
        conn.close()

    # Final stats
    elapsed = time.time() - start_time
    logger.info(f"""
=== BACKFILL COMPLETE ===
Processed: {processed} tenders
Successful: {success_count} ({100*success_count/processed:.1f}%)
Time: {elapsed/3600:.2f} hours
Rate: {processed/elapsed:.2f} tenders/sec
""")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill actual_value for e-nabavki tenders')
    parser.add_argument('--workers', type=int, default=20, help='Number of parallel browser workers')
    parser.add_argument('--batch', type=int, default=1000, help='Database batch size')
    parser.add_argument('--max', type=int, default=None, help='Maximum tenders to process (for testing)')

    args = parser.parse_args()

    run_backfill(
        workers=args.workers,
        batch_size=args.batch,
        max_tenders=args.max
    )
