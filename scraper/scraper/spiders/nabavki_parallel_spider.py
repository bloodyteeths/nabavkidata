"""
E-nabavki.gov.mk PARALLEL Spider - Optimized for Speed
Scrapes all historical tenders in hours instead of days.

Strategy:
1. Phase 1: Collect ALL URLs first (fast pagination, no detail fetching)
2. Phase 2: Process details in parallel with worker pool

Optimizations:
- Separates URL collection from detail extraction
- Uses page pooling (reuses browser pages)
- Disables images/CSS for faster loads
- Parallel processing with configurable workers
- Direct database writes (bypasses Scrapy pipeline overhead)

Usage:
    # Collect URLs for year 2019
    python nabavki_parallel_spider.py --collect-urls --year 2019

    # Process collected URLs with 10 workers
    python nabavki_parallel_spider.py --process-urls --workers 10

    # Full run for all years
    python nabavki_parallel_spider.py --full-run --workers 20
"""

import os
import sys
import time
import json
import logging
import argparse
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import List, Dict, Optional, Any
import queue

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)

import psycopg2
from psycopg2.extras import execute_values

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'nabavki'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'port': 5432
}

# URLs directory
URLS_DIR = Path(__file__).parent.parent.parent / 'collected_urls'
URLS_DIR.mkdir(exist_ok=True)


class FastBrowserPool:
    """Pool of reusable browser pages for parallel processing."""

    def __init__(self, size: int = 10, headless: bool = True):
        self.size = size
        self.headless = headless
        self.drivers: List[webdriver.Chrome] = []
        self.available = queue.Queue()
        self.lock = Lock()
        self._init_pool()

    def _create_driver(self) -> webdriver.Chrome:
        """Create optimized Chrome driver."""
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')

        # Speed optimizations
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')

        # Disable images and CSS for faster loading
        prefs = {
            'profile.managed_default_content_settings.images': 2,
            'profile.managed_default_content_settings.stylesheets': 2,
        }
        options.add_experimental_option('prefs', prefs)

        # Block unnecessary resources
        options.add_argument('--blink-settings=imagesEnabled=false')

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(5)
        return driver

    def _init_pool(self):
        """Initialize the browser pool."""
        logger.info(f"Initializing browser pool with {self.size} instances...")
        for i in range(self.size):
            driver = self._create_driver()
            self.drivers.append(driver)
            self.available.put(driver)
        logger.info(f"Browser pool ready with {self.size} instances")

    def get(self, timeout: float = 30) -> webdriver.Chrome:
        """Get a browser from the pool."""
        return self.available.get(timeout=timeout)

    def release(self, driver: webdriver.Chrome):
        """Return a browser to the pool."""
        self.available.put(driver)

    def close_all(self):
        """Close all browsers."""
        for driver in self.drivers:
            try:
                driver.quit()
            except:
                pass


class URLCollector:
    """Fast URL collection from listing pages."""

    CATEGORY_URL = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0'

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None

    def _setup_driver(self):
        """Setup optimized Chrome driver."""
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        # Keep images for now as they might affect Angular rendering

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(90)
        self.driver.implicitly_wait(10)

    def _wait_for_angular(self, timeout: int = 30):
        """Wait for Angular to finish loading."""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script(
                    "return typeof angular !== 'undefined' && "
                    "angular.element(document).injector() && "
                    "angular.element(document).injector().get('$http').pendingRequests.length === 0"
                )
            )
        except:
            time.sleep(2)

    def _wait_for_table(self, timeout: int = 30) -> bool:
        """Wait for DataTable to load."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
            return True
        except:
            return False

    def _select_archive_year(self, year: int) -> bool:
        """Select archive year via modal."""
        if year < 2008 or year > 2021:
            return False

        try:
            btn = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH,
                    "//*[@ng-click=\"openChangeArchiveYearDialog('sm',$event)\"]"))
            )
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".modal.in, .modal-dialog"))
            )

            radio = self.driver.find_element(By.CSS_SELECTOR,
                f".modal input[type='radio'][value='{year}']")
            self.driver.execute_script("arguments[0].click();", radio)
            time.sleep(0.5)

            confirm_btn = self.driver.find_element(By.XPATH,
                "//div[contains(@class,'modal')]//button[contains(text(),'Потврди')]")
            self.driver.execute_script("arguments[0].click();", confirm_btn)
            time.sleep(3)

            self._wait_for_angular()
            self._wait_for_table()

            logger.info(f"Selected archive year: {year}")
            return True
        except Exception as e:
            logger.error(f"Failed to select archive year {year}: {e}")
            return False

    def _try_change_page_size(self) -> bool:
        """Try to change DataTables page size to 100 for faster pagination."""
        try:
            # Look for page size selector
            selectors = [
                "select[name*='length']",
                "select.form-control",
                ".dataTables_length select",
            ]

            for sel in selectors:
                try:
                    select = self.driver.find_element(By.CSS_SELECTOR, sel)
                    # Try to select 100
                    options = select.find_elements(By.TAG_NAME, "option")
                    for opt in options:
                        if opt.get_attribute('value') in ['100', '50', '25']:
                            opt.click()
                            time.sleep(2)
                            self._wait_for_angular()
                            logger.info(f"Changed page size to {opt.get_attribute('value')}")
                            return True
                except:
                    continue
            return False
        except:
            return False

    def _get_page_info(self) -> tuple:
        """Get current page info (current, total records)."""
        try:
            info = self.driver.find_element(By.CSS_SELECTOR, ".dataTables_info").text
            # Parse "Прикажани од 1 до 10 од вкупно 39,426 записи"
            match = re.search(r'од вкупно ([\d,\.]+)', info)
            if match:
                total = int(match.group(1).replace(',', '').replace('.', ''))
                return total
        except:
            pass
        return 0

    def _get_tender_urls(self) -> List[str]:
        """Extract tender URLs from current page."""
        urls = []
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='dossie-acpp']")
            for elem in elements:
                href = elem.get_attribute('href')
                if href and 'dossie-acpp' in href:
                    urls.append(href)
        except:
            pass
        return list(set(urls))

    def _click_next_page(self) -> bool:
        """Click next page button."""
        try:
            selectors = [
                "a.paginate_button.next:not(.disabled)",
                "li.next:not(.disabled) a",
            ]

            for selector in selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    classes = btn.get_attribute('class') or ''
                    if 'disabled' in classes:
                        continue

                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    self._wait_for_angular()
                    return True
                except:
                    continue
            return False
        except:
            return False

    def collect_urls_for_year(self, year: int, max_pages: int = 5000) -> List[str]:
        """Collect all tender URLs for a specific year."""
        all_urls = []

        try:
            self._setup_driver()

            logger.info(f"Navigating to listing page...")
            self.driver.get(self.CATEGORY_URL)
            time.sleep(4)
            self._wait_for_angular()

            if not self._wait_for_table():
                logger.error("Failed to load table")
                return []

            # Select archive year if needed
            if 2008 <= year <= 2021:
                if not self._select_archive_year(year):
                    return []

            # Try to increase page size
            self._try_change_page_size()

            total_records = self._get_page_info()
            logger.info(f"Year {year}: {total_records:,} total records")

            # Collect URLs from all pages
            page = 0
            while page < max_pages:
                page += 1

                urls = self._get_tender_urls()
                new_count = len([u for u in urls if u not in all_urls])
                all_urls.extend([u for u in urls if u not in all_urls])

                if page % 50 == 0:
                    logger.info(f"Year {year} - Page {page}: {len(all_urls):,} URLs collected")

                if new_count == 0:
                    logger.info(f"No new URLs on page {page}, might be last page")

                if not self._click_next_page():
                    logger.info(f"Reached last page at {page}")
                    break

            logger.info(f"Year {year}: Collected {len(all_urls):,} URLs from {page} pages")
            return all_urls

        finally:
            if self.driver:
                self.driver.quit()

    def save_urls(self, year: int, urls: List[str]):
        """Save collected URLs to file."""
        filepath = URLS_DIR / f"urls_{year}.json"
        with open(filepath, 'w') as f:
            json.dump({
                'year': year,
                'count': len(urls),
                'collected_at': datetime.now().isoformat(),
                'urls': urls
            }, f, indent=2)
        logger.info(f"Saved {len(urls):,} URLs to {filepath}")


class TenderExtractor:
    """Extract tender details from a URL."""

    FIELD_PATTERNS = {
        'tender_id': [
            "//label[@label-for='PROCESS NUMBER FOR NOTIFICATION DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]",
            "//label[@label-for='NUMBER ACPP']/following-sibling::label[contains(@class, 'dosie-value')]",
        ],
        'title': [
            "//label[@label-for='SUBJECT:']/following-sibling::label[contains(@class, 'dosie-value')]",
            "//label[@label-for='DETAIL DESCRIPTION OF THE ITEM TO BE PROCURED DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]",
        ],
        'procuring_entity': [
            "//label[@label-for='CONTRACTING INSTITUTION NAME DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]",
        ],
        'estimated_value': [
            "//label[@label-for='ESTIMATED VALUE NEW']/following-sibling::label[contains(@class, 'dosie-value')]",
        ],
        'actual_value': [
            "//label[@label-for='ASSIGNED CONTRACT VALUE WITHOUT VAT']/following-sibling::label[contains(@class, 'dosie-value')]",
            "//label[@label-for='ASSIGNED CONTRACT VALUE DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]",
        ],
        'winner': [
            "//label[@label-for='NAME OF CONTACT OF PROCUREMENT DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]",
            "//label[@label-for='WINNER NAME DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]",
        ],
        'num_bidders': [
            "//label[@label-for='NUMBER OF OFFERS DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]",
        ],
        'cpv_code': [
            "//label[contains(text(),'CPV')]/following-sibling::*",
        ],
        'procedure_type': [
            "//label[@label-for='TYPE OF CALL:']/following-sibling::label[contains(@class, 'dosie-value')]",
        ],
    }

    @staticmethod
    def extract(driver: webdriver.Chrome, url: str) -> Optional[Dict[str, Any]]:
        """Extract tender data from URL."""
        try:
            driver.get(url)
            time.sleep(2)

            # Wait for Angular
            try:
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script(
                        "return typeof angular !== 'undefined' && "
                        "angular.element(document).injector() && "
                        "angular.element(document).injector().get('$http').pendingRequests.length === 0"
                    )
                )
            except:
                time.sleep(2)

            # Wait for content
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "label.dosie-value"))
            )

            tender = {'source_url': url}

            # Extract dossier_id from URL
            match = re.search(r'/dossie-acpp/([a-f0-9-]+)', url)
            if match:
                tender['dossier_id'] = match.group(1)

            # Extract fields
            for field, xpaths in TenderExtractor.FIELD_PATTERNS.items():
                for xpath in xpaths:
                    try:
                        elem = driver.find_element(By.XPATH, xpath)
                        text = elem.text.strip()
                        if text:
                            tender[field] = text
                            break
                    except:
                        continue

            # Parse numeric values
            if 'estimated_value' in tender:
                try:
                    val = tender['estimated_value'].replace('.', '').replace(',', '.')
                    val = re.sub(r'[^\d.]', '', val)
                    tender['estimated_value_mkd'] = Decimal(val) if val else None
                except:
                    pass

            if 'actual_value' in tender:
                try:
                    val = tender['actual_value'].replace('.', '').replace(',', '.')
                    val = re.sub(r'[^\d.]', '', val)
                    tender['actual_value_mkd'] = Decimal(val) if val else None
                except:
                    pass

            if 'num_bidders' in tender:
                try:
                    tender['num_bidders'] = int(re.sub(r'[^\d]', '', tender['num_bidders']))
                except:
                    pass

            # Get raw HTML for RAG
            try:
                tender['raw_page_html'] = driver.page_source
            except:
                pass

            return tender

        except Exception as e:
            logger.error(f"Error extracting {url}: {e}")
            return None


class ParallelProcessor:
    """Process tender URLs in parallel."""

    def __init__(self, num_workers: int = 10, headless: bool = True):
        self.num_workers = num_workers
        self.pool = FastBrowserPool(size=num_workers, headless=headless)
        self.db_lock = Lock()
        self.stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'start_time': None
        }

    def _get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(**DB_CONFIG)

    def _save_tender(self, tender: Dict[str, Any]) -> bool:
        """Save tender to database."""
        if not tender.get('tender_id'):
            return False

        try:
            with self.db_lock:
                conn = self._get_db_connection()
                cur = conn.cursor()

                # Upsert tender
                cur.execute("""
                    INSERT INTO tenders (
                        tender_id, title, procuring_entity,
                        estimated_value_mkd, actual_value_mkd,
                        winner, num_bidders, cpv_code, procedure_type,
                        source_url, dossier_id, status, scraped_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (tender_id) DO UPDATE SET
                        actual_value_mkd = COALESCE(EXCLUDED.actual_value_mkd, tenders.actual_value_mkd),
                        winner = COALESCE(EXCLUDED.winner, tenders.winner),
                        num_bidders = COALESCE(EXCLUDED.num_bidders, tenders.num_bidders),
                        raw_page_html = EXCLUDED.raw_page_html,
                        scraped_at = EXCLUDED.scraped_at
                """, (
                    tender.get('tender_id'),
                    tender.get('title'),
                    tender.get('procuring_entity'),
                    tender.get('estimated_value_mkd'),
                    tender.get('actual_value_mkd'),
                    tender.get('winner'),
                    tender.get('num_bidders'),
                    tender.get('cpv_code'),
                    tender.get('procedure_type'),
                    tender.get('source_url'),
                    tender.get('dossier_id'),
                    'awarded',
                    datetime.now()
                ))

                conn.commit()
                cur.close()
                conn.close()
                return True

        except Exception as e:
            logger.error(f"DB error for {tender.get('tender_id')}: {e}")
            return False

    def _process_url(self, url: str) -> bool:
        """Process a single URL using a pooled browser."""
        driver = None
        try:
            driver = self.pool.get(timeout=60)
            tender = TenderExtractor.extract(driver, url)

            if tender:
                if self._save_tender(tender):
                    self.stats['success'] += 1
                    return True

            self.stats['failed'] += 1
            return False

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            self.stats['failed'] += 1
            return False

        finally:
            if driver:
                self.pool.release(driver)
            self.stats['processed'] += 1

    def process_urls(self, urls: List[str]):
        """Process URLs in parallel."""
        self.stats['start_time'] = time.time()
        total = len(urls)

        logger.info(f"Processing {total:,} URLs with {self.num_workers} workers...")

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = {executor.submit(self._process_url, url): url for url in urls}

            for future in as_completed(futures):
                url = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Worker error for {url}: {e}")

                # Log progress
                if self.stats['processed'] % 100 == 0:
                    elapsed = time.time() - self.stats['start_time']
                    rate = self.stats['processed'] / elapsed * 60  # per minute
                    eta = (total - self.stats['processed']) / rate if rate > 0 else 0
                    logger.info(
                        f"Progress: {self.stats['processed']:,}/{total:,} "
                        f"({self.stats['success']:,} success, {self.stats['failed']:,} failed) "
                        f"Rate: {rate:.1f}/min, ETA: {eta:.1f} min"
                    )

        elapsed = time.time() - self.stats['start_time']
        logger.info(f"Completed in {elapsed/60:.1f} minutes")
        logger.info(f"Success: {self.stats['success']:,}, Failed: {self.stats['failed']:,}")

        self.pool.close_all()


def collect_all_years(years: List[int], headless: bool = True):
    """Collect URLs for all years in parallel."""
    from concurrent.futures import ProcessPoolExecutor

    def collect_year(year):
        collector = URLCollector(headless=headless)
        urls = collector.collect_urls_for_year(year)
        collector.save_urls(year, urls)
        return year, len(urls)

    logger.info(f"Collecting URLs for years: {years}")

    # Run in parallel (one process per year)
    with ProcessPoolExecutor(max_workers=min(len(years), 4)) as executor:
        results = list(executor.map(collect_year, years))

    total = sum(count for _, count in results)
    logger.info(f"Total URLs collected: {total:,}")
    return results


def load_urls_from_files() -> List[str]:
    """Load all collected URLs from files."""
    all_urls = []
    for filepath in URLS_DIR.glob("urls_*.json"):
        with open(filepath) as f:
            data = json.load(f)
            all_urls.extend(data['urls'])
            logger.info(f"Loaded {data['count']:,} URLs from {filepath.name}")
    return all_urls


def main():
    parser = argparse.ArgumentParser(description='Fast parallel tender scraper')
    parser.add_argument('--collect-urls', action='store_true', help='Collect URLs only')
    parser.add_argument('--process-urls', action='store_true', help='Process collected URLs')
    parser.add_argument('--full-run', action='store_true', help='Full run: collect + process')
    parser.add_argument('--year', type=int, help='Specific year to process')
    parser.add_argument('--years', type=str, help='Year range (e.g., "2008-2021")')
    parser.add_argument('--workers', type=int, default=10, help='Number of parallel workers')
    parser.add_argument('--headless', type=bool, default=True, help='Run headless')

    args = parser.parse_args()

    # Parse years
    years = []
    if args.year:
        years = [args.year]
    elif args.years:
        if '-' in args.years:
            start, end = map(int, args.years.split('-'))
            years = list(range(start, end + 1))
        else:
            years = [int(y.strip()) for y in args.years.split(',')]
    else:
        years = list(range(2008, 2022))  # Default: all archive years

    if args.collect_urls or args.full_run:
        logger.info("=== PHASE 1: URL COLLECTION ===")
        collect_all_years(years, headless=args.headless)

    if args.process_urls or args.full_run:
        logger.info("=== PHASE 2: PARALLEL PROCESSING ===")
        urls = load_urls_from_files()

        if urls:
            processor = ParallelProcessor(num_workers=args.workers, headless=args.headless)
            processor.process_urls(urls)
        else:
            logger.error("No URLs found. Run --collect-urls first.")


if __name__ == '__main__':
    main()
