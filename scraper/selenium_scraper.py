#!/usr/bin/env python3
"""
Selenium-based E-Nabavki Scraper for Local Use

This is a standalone scraper using Selenium (more stable on Mac than Playwright).
Designed for historical backfill - scrapes awarded tenders and saves to database.

Usage:
    python selenium_scraper.py --year 2025 --max-pages 100
    python selenium_scraper.py --year 2024 --max-pages 500
    python selenium_scraper.py --category active --max-pages 50

Requirements:
    pip install selenium webdriver-manager asyncpg
"""

import argparse
import asyncio
import logging
import os
import re
import sys
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

import asyncpg
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from dotenv import load_dotenv
load_dotenv()


# Try newer webdriver-manager with Chrome for Testing support
try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.core.os_manager import ChromeType
    USE_CHROME_FOR_TESTING = True
except ImportError:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_CHROME_FOR_TESTING = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/selenium_scrape_{datetime.now().strftime("%Y%m%d_%H%M")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)

# Category URLs
CATEGORY_URLS = {
    'active': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices',
    'awarded': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0',
    'cancelled': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/cancelations',
}


class SeleniumScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.pool = None
        self.stats = {
            'pages_scraped': 0,
            'tenders_found': 0,
            'tenders_saved': 0,
            'tenders_updated': 0,
            'errors': 0,
        }

    def setup_driver(self):
        """Initialize Chrome WebDriver with optimal settings."""
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')

        # Performance optimizations
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')

        # Try multiple approaches to get ChromeDriver
        try:
            # First try: Use Chrome for Testing (newer approach)
            if USE_CHROME_FOR_TESTING:
                service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
            else:
                service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e1:
            logger.warning(f"ChromeDriverManager failed: {e1}")
            try:
                # Second try: Use system Chrome without specifying driver
                self.driver = webdriver.Chrome(options=options)
            except Exception as e2:
                logger.warning(f"System Chrome failed: {e2}")
                # Third try: Use Safari (available on Mac)
                logger.info("Falling back to Safari WebDriver")
                from selenium.webdriver.safari.options import Options as SafariOptions
                safari_options = SafariOptions()
                self.driver = webdriver.Safari(options=safari_options)

        self.driver.set_page_load_timeout(60)
        self.driver.implicitly_wait(10)

        logger.info(f"WebDriver initialized: {type(self.driver).__name__}")

    async def setup_database(self):
        """Initialize database connection pool."""
        # Convert URL for asyncpg (remove +asyncpg if present)
        db_url = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        self.pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
        logger.info("Database connection pool created")

    def wait_for_angular(self, timeout: int = 30):
        """Wait for Angular to finish loading."""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script(
                    "return typeof angular !== 'undefined' && "
                    "angular.element(document).injector() && "
                    "angular.element(document).injector().get('$http').pendingRequests.length === 0"
                )
            )
        except TimeoutException:
            # Fallback: just wait for page to be somewhat stable
            time.sleep(2)

    def wait_for_table(self, timeout: int = 30):
        """Wait for DataTable to load."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
            # Additional wait for data to populate
            time.sleep(1)
            return True
        except TimeoutException:
            logger.warning("Table not found within timeout")
            return False

    def get_page_info(self) -> str:
        """Get current page info text (e.g., 'Прикажани од 1 до 10 од вкупно 29,431 записи')."""
        try:
            info_elem = self.driver.find_element(By.CSS_SELECTOR, ".dataTables_info")
            return info_elem.text
        except NoSuchElementException:
            return ""

    def apply_year_filter(self, year: int):
        """Apply server-side year filter using date inputs."""
        try:
            # Find date filter inputs
            date_from = self.driver.find_element(By.CSS_SELECTOR, "input[ng-model*='dateFrom'], input[placeholder*='Од']")
            date_to = self.driver.find_element(By.CSS_SELECTOR, "input[ng-model*='dateTo'], input[placeholder*='До']")

            # Set date range for the year
            date_from.clear()
            date_from.send_keys(f"01.01.{year}")

            date_to.clear()
            date_to.send_keys(f"31.12.{year}")

            # Click search/filter button
            try:
                search_btn = self.driver.find_element(By.CSS_SELECTOR, "button[ng-click*='search'], button.btn-primary")
                search_btn.click()
            except NoSuchElementException:
                # Try pressing Enter
                date_to.send_keys("\n")

            time.sleep(3)
            self.wait_for_angular()

            logger.info(f"Applied year filter: {year}")
            return True

        except NoSuchElementException as e:
            logger.warning(f"Could not find date filter elements: {e}")
            return False

    def get_tender_links(self) -> List[str]:
        """Extract tender detail links from current page."""
        links = []
        try:
            # Find links to tender details (dossie-acpp pages)
            elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='dossie-acpp'], a[href*='dossie/']")
            for elem in elements:
                href = elem.get_attribute('href')
                if href and ('dossie-acpp' in href or 'dossie/' in href):
                    links.append(href)
        except Exception as e:
            logger.error(f"Error extracting tender links: {e}")

        return list(set(links))  # Deduplicate

    def click_next_page(self) -> bool:
        """Click next page button using JavaScript to avoid interception."""
        try:
            # Try different next page selectors
            selectors = [
                "a.paginate_button.next:not(.disabled)",
                "li.next:not(.disabled) a",
                "button.next:not(:disabled)",
                ".pagination .next a",
            ]

            for selector in selectors:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    classes = next_btn.get_attribute('class') or ''
                    if 'disabled' in classes:
                        continue

                    # Use JavaScript click to avoid element interception
                    self.driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(2)
                    self.wait_for_angular()
                    return True
                except NoSuchElementException:
                    continue

            return False

        except Exception as e:
            logger.error(f"Error clicking next page: {e}")
            return False

    def extract_tender_details(self, url: str) -> Optional[Dict[str, Any]]:
        """Navigate to tender detail page and extract data."""
        try:
            self.driver.get(url)
            time.sleep(2)
            self.wait_for_angular()

            tender = {'source_url': url}

            # Extract tender ID from URL
            id_match = re.search(r'/dossie-acpp/([a-f0-9-]+)', url)
            if id_match:
                tender['internal_id'] = id_match.group(1)

            # Wait for content to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".panel, .card, h1, h2"))
            )

            # Extract fields using various selectors
            field_mappings = {
                'tender_id': [
                    "//label[contains(text(),'Број')]/following-sibling::*",
                    "//td[contains(text(),'Број')]/following-sibling::td",
                    ".tender-number, .broj-nabavka",
                ],
                'title': [
                    "//label[contains(text(),'Наслов')]/following-sibling::*",
                    "//td[contains(text(),'Предмет')]/following-sibling::td",
                    "h1, h2, .tender-title",
                ],
                'procuring_entity': [
                    "//label[contains(text(),'Договорен орган')]/following-sibling::*",
                    "//td[contains(text(),'Договорен орган')]/following-sibling::td",
                    ".procuring-entity, .dogovoren-organ",
                ],
                'estimated_value': [
                    "//label[contains(text(),'Проценета вредност')]/following-sibling::*",
                    "//td[contains(text(),'Вредност')]/following-sibling::td",
                ],
                'cpv_code': [
                    "//label[contains(text(),'CPV')]/following-sibling::*",
                    "//td[contains(text(),'CPV')]/following-sibling::td",
                ],
                'publication_date': [
                    "//label[contains(text(),'Датум на објава')]/following-sibling::*",
                    "//td[contains(text(),'Датум')]/following-sibling::td",
                ],
                'winner': [
                    "//label[contains(text(),'Избран понудувач')]/following-sibling::*",
                    "//td[contains(text(),'Добитник')]/following-sibling::td",
                    ".winner, .izbran-ponuduvac",
                ],
            }

            for field, selectors in field_mappings.items():
                for selector in selectors:
                    try:
                        if selector.startswith('//'):
                            elem = self.driver.find_element(By.XPATH, selector)
                        else:
                            elem = self.driver.find_element(By.CSS_SELECTOR, selector)

                        text = elem.text.strip()
                        if text:
                            tender[field] = text
                            break
                    except NoSuchElementException:
                        continue

            # Parse numeric values
            if 'estimated_value' in tender:
                try:
                    value_text = tender['estimated_value']
                    # Remove currency symbols and whitespace
                    value_clean = re.sub(r'[^\d.,]', '', value_text)
                    value_clean = value_clean.replace(',', '')
                    tender['estimated_value_mkd'] = Decimal(value_clean)
                except Exception:
                    pass

            # Parse dates
            if 'publication_date' in tender:
                try:
                    date_text = tender['publication_date']
                    for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y']:
                        try:
                            tender['publication_date'] = datetime.strptime(date_text, fmt).date()
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            return tender if tender.get('tender_id') or tender.get('title') else None

        except Exception as e:
            logger.error(f"Error extracting tender from {url}: {e}")
            self.stats['errors'] += 1
            return None

    async def save_tender(self, tender: Dict[str, Any]) -> bool:
        """Save tender to database using UPSERT."""
        if not tender.get('tender_id') and not tender.get('title'):
            return False

        # Generate tender_id if not present
        if not tender.get('tender_id'):
            tender['tender_id'] = f"SELENIUM-{tender.get('internal_id', 'UNKNOWN')}"

        try:
            async with self.pool.acquire() as conn:
                # Check if tender exists
                existing = await conn.fetchrow(
                    "SELECT tender_id, scraped_at FROM tenders WHERE tender_id = $1",
                    tender['tender_id']
                )

                if existing:
                    # Update existing tender
                    await conn.execute("""
                        UPDATE tenders SET
                            title = COALESCE($2, title),
                            procuring_entity = COALESCE($3, procuring_entity),
                            estimated_value_mkd = COALESCE($4, estimated_value_mkd),
                            cpv_code = COALESCE($5, cpv_code),
                            publication_date = COALESCE($6, publication_date),
                            winner = COALESCE($7, winner),
                            source_url = COALESCE($8, source_url),
                            scraped_at = NOW(),
                            updated_at = NOW()
                        WHERE tender_id = $1
                    """,
                        tender['tender_id'],
                        tender.get('title'),
                        tender.get('procuring_entity'),
                        tender.get('estimated_value_mkd'),
                        tender.get('cpv_code'),
                        tender.get('publication_date'),
                        tender.get('winner'),
                        tender.get('source_url'),
                    )
                    self.stats['tenders_updated'] += 1
                    logger.info(f"Updated tender: {tender['tender_id']}")
                else:
                    # Insert new tender
                    await conn.execute("""
                        INSERT INTO tenders (
                            tender_id, title, procuring_entity, estimated_value_mkd,
                            cpv_code, publication_date, winner, source_url,
                            status, scraped_at, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'awarded', NOW(), NOW(), NOW())
                    """,
                        tender['tender_id'],
                        tender.get('title', 'Unknown'),
                        tender.get('procuring_entity'),
                        tender.get('estimated_value_mkd'),
                        tender.get('cpv_code'),
                        tender.get('publication_date'),
                        tender.get('winner'),
                        tender.get('source_url'),
                    )
                    self.stats['tenders_saved'] += 1
                    logger.info(f"Saved new tender: {tender['tender_id']}")

                return True

        except Exception as e:
            logger.error(f"Database error saving tender {tender.get('tender_id')}: {e}")
            self.stats['errors'] += 1
            return False

    async def scrape(self, category: str = 'awarded', year: Optional[int] = None, max_pages: int = 100):
        """Main scraping method."""
        try:
            # Setup
            self.setup_driver()
            await self.setup_database()

            # Navigate to category
            url = CATEGORY_URLS.get(category, CATEGORY_URLS['awarded'])
            logger.info(f"Starting scrape: category={category}, year={year}, max_pages={max_pages}")
            logger.info(f"Navigating to: {url}")

            self.driver.get(url)
            time.sleep(3)
            self.wait_for_angular()

            if not self.wait_for_table():
                logger.error("Failed to load tender table")
                return

            # Apply year filter if specified
            if year:
                self.apply_year_filter(year)

            # Get initial page info
            page_info = self.get_page_info()
            logger.info(f"Initial page info: {page_info}")

            # Scrape pages
            page_num = 0
            all_tender_links = []

            while page_num < max_pages:
                page_num += 1
                logger.info(f"Processing page {page_num}/{max_pages}")

                # Get tender links from current page
                links = self.get_tender_links()
                if not links:
                    logger.warning(f"No tender links found on page {page_num}")
                    # Try to continue anyway

                all_tender_links.extend(links)
                self.stats['pages_scraped'] += 1
                self.stats['tenders_found'] += len(links)

                logger.info(f"Found {len(links)} tenders on page {page_num} (total: {len(all_tender_links)})")

                # Try to go to next page
                if not self.click_next_page():
                    logger.info("Reached last page or pagination failed")
                    break

            logger.info(f"Collected {len(all_tender_links)} tender links from {page_num} pages")

            # Now scrape each tender detail page
            for i, link in enumerate(all_tender_links):
                logger.info(f"Scraping tender {i+1}/{len(all_tender_links)}: {link}")

                tender = self.extract_tender_details(link)
                if tender:
                    await self.save_tender(tender)

                # Rate limiting
                time.sleep(0.5)

            # Print final stats
            logger.info("=" * 60)
            logger.info("SCRAPE COMPLETE")
            logger.info(f"Pages scraped: {self.stats['pages_scraped']}")
            logger.info(f"Tenders found: {self.stats['tenders_found']}")
            logger.info(f"Tenders saved (new): {self.stats['tenders_saved']}")
            logger.info(f"Tenders updated: {self.stats['tenders_updated']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info("=" * 60)

        finally:
            if self.driver:
                self.driver.quit()
            if self.pool:
                await self.pool.close()


def main():
    parser = argparse.ArgumentParser(description='Selenium-based E-Nabavki Scraper')
    parser.add_argument('--category', default='awarded', choices=['active', 'awarded', 'cancelled'],
                        help='Category to scrape')
    parser.add_argument('--year', type=int, help='Filter by year (e.g., 2025)')
    parser.add_argument('--max-pages', type=int, default=100, help='Maximum pages to scrape')
    parser.add_argument('--headless', action='store_true', default=True, help='Run in headless mode')
    parser.add_argument('--no-headless', action='store_true', help='Run with visible browser')

    args = parser.parse_args()

    headless = not args.no_headless

    scraper = SeleniumScraper(headless=headless)
    asyncio.run(scraper.scrape(
        category=args.category,
        year=args.year,
        max_pages=args.max_pages
    ))


if __name__ == '__main__':
    main()
