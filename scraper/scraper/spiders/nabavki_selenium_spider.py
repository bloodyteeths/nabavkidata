"""
E-nabavki.gov.mk Selenium Spider - For Local Scraping

This spider uses Selenium instead of Playwright for JavaScript rendering.
More stable on Mac than Playwright. Designed for local historical backfill.

Usage:
    scrapy crawl nabavki_selenium -a category=awarded -a year_filter=2025
    scrapy crawl nabavki_selenium -a category=active -a max_listing_pages=50
    scrapy crawl nabavki_selenium -a category=awarded -a year=2021

Note: This spider runs synchronously due to Selenium's blocking nature.
"""

import scrapy
import logging
import re
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)
from selenium.webdriver.common.action_chains import ActionChains

from scraper.items import TenderItem, DocumentItem

logger = logging.getLogger(__name__)


class NabavkiSeleniumSpider(scrapy.Spider):
    """
    Selenium-based spider for e-nabavki.gov.mk.
    Mirrors the Playwright spider logic but uses Selenium for stability.
    """

    name = 'nabavki_selenium'
    allowed_domains = ['e-nabavki.gov.mk']

    CATEGORY_URLS = {
        'active': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices',
        'awarded': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0',
        'cancelled': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/cancelations',
        'historical': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/realized-contract',
        'tender_winners': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/tender-winners/0',
    }

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS": 1,  # Selenium is single-threaded
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 120,
        # Disable Playwright for this spider
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler",
            "https": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler",
        },
    }

    def __init__(self, category='awarded', year=None, start_page=1,
                 max_listing_pages=None, year_filter=None, headless=True,
                 force_full_scan=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.category = category.lower()
        self.year = int(year) if year and str(year).lower() not in ('none', 'current', '') else None
        self.start_page = int(start_page)
        self.max_listing_pages = int(max_listing_pages) if max_listing_pages else 1000
        self.year_filter = self._parse_year_filter(year_filter)
        self.headless = str(headless).lower() in ('true', '1', 'yes', '')
        self.force_full_scan = str(force_full_scan).lower() in ('true', '1', 'yes')

        self.driver = None
        self.stats = {
            'pages_scraped': 0,
            'tenders_found': 0,
            'tenders_saved': 0,
            'tenders_skipped': 0,
            'errors': 0,
        }

        logger.warning(f"Spider initialized: category={self.category}, year={self.year}, "
                      f"max_listing_pages={self.max_listing_pages}, year_filter={self.year_filter}")

    def _parse_year_filter(self, year_filter):
        """Parse year_filter into a set of years."""
        if not year_filter or str(year_filter).lower() in ('none', ''):
            return None

        years = set()
        year_filter = str(year_filter).strip()

        if '-' in year_filter and ',' not in year_filter:
            parts = year_filter.split('-')
            if len(parts) == 2:
                try:
                    start_year = int(parts[0].strip())
                    end_year = int(parts[1].strip())
                    years = set(range(start_year, end_year + 1))
                except ValueError:
                    pass
        elif ',' in year_filter:
            for part in year_filter.split(','):
                try:
                    years.add(int(part.strip()))
                except ValueError:
                    pass
        else:
            try:
                years.add(int(year_filter))
            except ValueError:
                pass

        return years if years else None

    def setup_driver(self):
        """Initialize Selenium Chrome WebDriver."""
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--window-size=1920,1200')
        options.add_argument('--disable-blink-features=AutomationControlled')

        try:
            self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            logger.error(f"Chrome WebDriver failed: {e}")
            # Fallback to Safari on Mac
            logger.info("Trying Safari WebDriver...")
            self.driver = webdriver.Safari()

        self.driver.set_page_load_timeout(90)
        self.driver.implicitly_wait(10)
        logger.info(f"WebDriver initialized: {type(self.driver).__name__}")

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
            time.sleep(2)

    def wait_for_table(self, timeout: int = 30) -> bool:
        """Wait for DataTable to load."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
            time.sleep(1)
            return True
        except TimeoutException:
            return False

    def get_page_info(self) -> str:
        """Get current page info text."""
        try:
            info_elem = self.driver.find_element(By.CSS_SELECTOR, ".dataTables_info")
            return info_elem.text
        except NoSuchElementException:
            return ""

    def select_archive_year(self, year: int) -> bool:
        """Select archive year (2008-2021) via modal dialog."""
        if year < 2008 or year > 2021:
            logger.warning(f"Archive year {year} out of range (2008-2021), skipping")
            return False

        try:
            # Find and click archive dialog button
            btn = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH,
                    "//*[@ng-click=\"openChangeArchiveYearDialog('sm',$event)\"]"))
            )
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)

            # Wait for modal to appear
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".modal.in, .modal-dialog"))
            )

            # Select the year radio button
            radio = self.driver.find_element(By.CSS_SELECTOR,
                f".modal input[type='radio'][value='{year}']")
            self.driver.execute_script("arguments[0].click();", radio)
            time.sleep(0.5)

            # Click confirm button (Потврди)
            confirm_btn = self.driver.find_element(By.XPATH,
                "//div[contains(@class,'modal')]//button[contains(text(),'Потврди')]")
            self.driver.execute_script("arguments[0].click();", confirm_btn)
            time.sleep(3)

            self.wait_for_angular()

            # Wait for table to reload with archive data
            time.sleep(3)
            self.wait_for_table()

            logger.warning(f"Selected archive year: {year}")
            return True

        except Exception as e:
            logger.error(f"Failed to select archive year {year}: {e}")
            return False

    def apply_year_filter_server(self, year: int) -> bool:
        """Apply server-side year filter using date inputs."""
        try:
            # Find date inputs
            date_from = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "input[ng-model*='dateFrom'], input[ng-model*='datumOd'], input[placeholder*='Од']"))
            )
            date_to = self.driver.find_element(By.CSS_SELECTOR,
                "input[ng-model*='dateTo'], input[ng-model*='datumDo'], input[placeholder*='До']")

            # Clear and set dates
            date_from.clear()
            date_from.send_keys(f"01.01.{year}")
            time.sleep(0.5)

            date_to.clear()
            date_to.send_keys(f"31.12.{year}")
            time.sleep(0.5)

            # Click search button
            try:
                search_btn = self.driver.find_element(By.CSS_SELECTOR,
                    "button[ng-click*='search'], button.btn-primary, button[type='submit']")
                search_btn.click()
            except NoSuchElementException:
                date_to.send_keys("\n")

            time.sleep(3)
            self.wait_for_angular()

            logger.warning(f"Applied year filter: {year}")
            return True

        except Exception as e:
            logger.warning(f"Could not apply year filter: {e}")
            return False

    def get_tender_links(self) -> List[str]:
        """Extract tender detail links from current page."""
        links = []
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR,
                "a[href*='dossie-acpp'], a[href*='dossie/']")
            for elem in elements:
                try:
                    href = elem.get_attribute('href')
                    if href and ('dossie-acpp' in href or '/dossie/' in href):
                        links.append(href)
                except StaleElementReferenceException:
                    continue
        except Exception as e:
            logger.error(f"Error extracting tender links: {e}")

        return list(set(links))

    def click_next_page(self) -> bool:
        """Click next page button using JavaScript to avoid click interception."""
        try:
            selectors = [
                "a.paginate_button.next:not(.disabled)",
                "li.next:not(.disabled) a",
                ".pagination .next a",
            ]

            for selector in selectors:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    classes = next_btn.get_attribute('class') or ''
                    if 'disabled' in classes:
                        continue

                    # Use JavaScript click to avoid interception
                    self.driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(2)
                    self.wait_for_angular()

                    # Verify page changed
                    time.sleep(1)
                    return True

                except NoSuchElementException:
                    continue

            return False

        except Exception as e:
            logger.error(f"Error clicking next page: {e}")
            return False

    def extract_tender_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Navigate to tender detail page and extract data."""
        try:
            self.driver.get(url)
            time.sleep(2)
            self.wait_for_angular()

            # Wait for content
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".panel, .card, table, h1, h2"))
            )

            tender = {'source_url': url}

            # Extract tender ID from URL
            id_match = re.search(r'/dossie-acpp/([a-f0-9-]+)', url)
            if id_match:
                tender['internal_id'] = id_match.group(1)

            # Field extraction patterns
            field_patterns = {
                'tender_id': [
                    # Correct selector for awarded tenders
                    ("xpath", "//label[@label-for='PROCESS NUMBER FOR NOTIFICATION DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[@label-for='NUMBER ACPP']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[contains(text(),'Број на огласот')]/following-sibling::*"),
                    ("xpath", "//label[contains(text(),'Број')]/following-sibling::*"),
                ],
                'title': [
                    # Correct selector for subject
                    ("xpath", "//label[@label-for='SUBJECT:']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[@label-for='DETAIL DESCRIPTION OF THE ITEM TO BE PROCURED DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[contains(text(),'Предмет на договорот')]/following-sibling::*"),
                    ("css", "h1"),
                ],
                'procuring_entity': [
                    # Correct selector for contracting authority
                    ("xpath", "//label[@label-for='CONTRACTING INSTITUTION NAME DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[contains(text(),'Назив на договорниот орган')]/following-sibling::*"),
                    ("xpath", "//label[contains(text(),'Договорен орган')]/following-sibling::*"),
                ],
                'estimated_value': [
                    ("xpath", "//label[contains(text(),'Проценета вредност')]/following-sibling::*"),
                    ("xpath", "//label[@label-for='ESTIMATED VALUE NEW']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//td[contains(text(),'Вредност')]/following-sibling::td"),
                ],
                # ACTUAL VALUE - Contract value (the winning bid amount)
                'actual_value': [
                    ("xpath", "//label[@label-for='ASSIGNED CONTRACT VALUE WITHOUT VAT']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[@label-for='ASSIGNED CONTRACT VALUE DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[contains(@label-for, 'CONTRACT VALUE')]/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[contains(text(),'Вредност на договор')]/following-sibling::*"),
                    ("xpath", "//label[contains(text(),'Доделена вредност')]/following-sibling::*"),
                ],
                'cpv_code': [
                    ("xpath", "//label[contains(text(),'CPV')]/following-sibling::*"),
                    ("xpath", "//td[contains(text(),'CPV')]/following-sibling::td"),
                    ("xpath", "//span[contains(@ng-bind, 'cpvCode')]"),
                ],
                'publication_date': [
                    ("xpath", "//label[contains(text(),'Датум на објава')]/following-sibling::*"),
                    ("xpath", "//td[contains(text(),'Датум')]/following-sibling::td"),
                ],
                'winner': [
                    # Correct selectors from Playwright spider
                    ("xpath", "//label[@label-for='NAME OF CONTACT OF PROCUREMENT DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[@label-for='WINNER NAME DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[@label-for='SELECTED BIDDER DOSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[contains(text(),'Избран понудувач')]/following-sibling::*"),
                    ("xpath", "//label[contains(text(),'економски оператор')]/following-sibling::*"),
                ],
                'procedure_type': [
                    ("xpath", "//label[@label-for='TYPE OF CALL:']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[contains(text(),'Вид на постапка')]/following-sibling::*"),
                ],
                'num_bidders': [
                    ("xpath", "//label[@label-for='NUMBER OF OFFERS DOSSIE']/following-sibling::label[contains(@class, 'dosie-value')]"),
                    ("xpath", "//label[contains(text(),'Број на понуди')]/following-sibling::*"),
                ],
            }

            for field, patterns in field_patterns.items():
                for method, selector in patterns:
                    try:
                        if method == "xpath":
                            elem = self.driver.find_element(By.XPATH, selector)
                        else:
                            elem = self.driver.find_element(By.CSS_SELECTOR, selector)

                        text = elem.text.strip()
                        if text and len(text) > 1:
                            tender[field] = text
                            break
                    except NoSuchElementException:
                        continue

            # Parse values
            if 'estimated_value' in tender:
                try:
                    value_text = tender['estimated_value']
                    value_clean = re.sub(r'[^\d.,]', '', value_text).replace(',', '')
                    if value_clean:
                        tender['estimated_value_mkd'] = Decimal(value_clean)
                except Exception:
                    pass

            # Parse actual_value (contract value) - CRITICAL for awarded tenders
            if 'actual_value' in tender:
                try:
                    value_text = tender['actual_value']
                    # Handle Macedonian number format: 1.234.567,89
                    value_clean = value_text.replace('.', '').replace(',', '.')
                    value_clean = re.sub(r'[^\d.]', '', value_clean)
                    if value_clean:
                        tender['actual_value_mkd'] = Decimal(value_clean)
                        logger.info(f"Extracted actual_value: {tender['actual_value_mkd']}")
                except Exception as e:
                    logger.debug(f"Failed to parse actual_value '{tender.get('actual_value')}': {e}")

            # Parse num_bidders
            if 'num_bidders' in tender:
                try:
                    tender['num_bidders'] = int(re.sub(r'[^\d]', '', tender['num_bidders']))
                except Exception:
                    pass

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

            # Extract bidders from table
            tender['bidders'] = self.extract_bidders()

            # Get documents
            tender['documents'] = self.extract_documents()

            return tender if tender.get('tender_id') or tender.get('title') else None

        except Exception as e:
            logger.error(f"Error extracting tender from {url}: {e}")
            self.stats['errors'] += 1
            return None

    def extract_documents(self) -> List[Dict[str, str]]:
        """Extract document links from tender detail page."""
        documents = []
        try:
            # Try clicking Documents tab
            try:
                doc_tabs = self.driver.find_elements(By.CSS_SELECTOR,
                    "a[ng-click*='document'], li[heading*='Документ'] a, a:contains('Документи')")
                for tab in doc_tabs:
                    try:
                        self.driver.execute_script("arguments[0].click();", tab)
                        time.sleep(1)
                        break
                    except:
                        continue
            except:
                pass

            # Find document links
            doc_links = self.driver.find_elements(By.CSS_SELECTOR,
                "a[href*='Download'], a[href*='download'], a[ng-click*='download']")

            for link in doc_links:
                try:
                    href = link.get_attribute('href') or ''
                    onclick = link.get_attribute('ng-click') or ''
                    text = link.text.strip()

                    if href and ('Download' in href or 'download' in href):
                        documents.append({
                            'file_url': href,
                            'file_name': text or 'document.pdf'
                        })
                    elif onclick and 'download' in onclick.lower():
                        # Extract file ID from ng-click
                        id_match = re.search(r"'([a-f0-9-]+)'", onclick)
                        if id_match:
                            file_id = id_match.group(1)
                            documents.append({
                                'file_url': f"https://e-nabavki.gov.mk/File/DownloadContractFile?fileId={file_id}",
                                'file_name': text or f'document_{file_id[:8]}.pdf'
                            })
                except:
                    continue

        except Exception as e:
            logger.debug(f"Document extraction error: {e}")

        return documents

    def extract_bidders(self) -> List[Dict[str, Any]]:
        """Extract bidders from tender detail page bidder tables."""
        bidders = []
        try:
            # Look for bidder tables using various selectors
            table_selectors = [
                "//table[.//th[contains(text(),'Понудувач')]]",
                "//table[.//th[contains(text(),'Учесник')]]",
                "//table[.//th[contains(text(),'Економски оператор')]]",
                "//table[contains(@class, 'bidders-table')]",
                "//table[contains(@ng-repeat, 'bidder')]",
            ]

            bidder_table = None
            for selector in table_selectors:
                try:
                    tables = self.driver.find_elements(By.XPATH, selector)
                    if tables:
                        bidder_table = tables[0]
                        break
                except NoSuchElementException:
                    continue

            if bidder_table:
                rows = bidder_table.find_elements(By.CSS_SELECTOR, "tbody tr")

                for idx, row in enumerate(rows):
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if not cells:
                            continue

                        # Extract company name (usually first cell with text)
                        company_name = None
                        bid_amount = None

                        for cell in cells:
                            text = cell.text.strip()
                            if not text:
                                continue

                            # Check if it's a number (bid amount)
                            if re.match(r'^[\d.,\s]+$', text.replace('.', '').replace(',', '')):
                                try:
                                    value_clean = text.replace('.', '').replace(',', '.')
                                    value_clean = re.sub(r'[^\d.]', '', value_clean)
                                    if value_clean:
                                        bid_amount = float(value_clean)
                                except:
                                    pass
                            elif len(text) > 3 and not company_name:
                                company_name = text[:500]

                        if company_name:
                            bidders.append({
                                'company_name': company_name,
                                'bid_amount_mkd': bid_amount,
                                'is_winner': idx == 0,  # First row often winner
                                'rank': idx + 1
                            })

                    except StaleElementReferenceException:
                        continue

                if bidders:
                    logger.info(f"Extracted {len(bidders)} bidders from table")

        except Exception as e:
            logger.debug(f"Bidder extraction error: {e}")

        return bidders

    def start_requests(self):
        """Generate initial request - we handle everything in parse()."""
        url = self.CATEGORY_URLS.get(self.category, self.CATEGORY_URLS['awarded'])
        yield scrapy.Request(
            url,
            callback=self.parse,
            meta={'category': self.category},
            dont_filter=True
        )

    def parse(self, response):
        """Main parsing method - uses Selenium for JavaScript rendering."""
        try:
            self.setup_driver()

            url = self.CATEGORY_URLS.get(self.category, self.CATEGORY_URLS['awarded'])
            logger.info(f"Navigating to: {url}")

            self.driver.get(url)
            time.sleep(3)
            self.wait_for_angular()

            if not self.wait_for_table():
                logger.error("Failed to load tender table")
                return

            # Apply archive year selection if specified (2008-2021)
            if self.year and 2008 <= self.year <= 2021:
                logger.warning(f"Selecting archive year {self.year} via modal...")
                if not self.select_archive_year(self.year):
                    logger.error(f"Failed to select archive year {self.year}")
                    return
                time.sleep(2)
                self.wait_for_table()

            # Apply year filter if specified (for server-side date filtering)
            elif self.year_filter:
                years = sorted(self.year_filter)
                logger.warning(f"Applying server-side date filter for years {years[0]}-{years[-1]}...")
                self.apply_year_filter_server(years[0])

            page_info = self.get_page_info()
            logger.warning(f"After date filter: {page_info}")

            # Scrape listing pages
            page_num = 0
            seen_links = set()

            while page_num < self.max_listing_pages:
                page_num += 1
                logger.info(f"Processing listing page {page_num}/{self.max_listing_pages}")

                links = self.get_tender_links()
                new_links = [l for l in links if l not in seen_links]
                seen_links.update(links)

                self.stats['pages_scraped'] += 1
                self.stats['tenders_found'] += len(new_links)

                logger.info(f"Found {len(new_links)} new tenders on page {page_num}")

                # Process each tender
                for link in new_links:
                    logger.warning(f"🔥 PROCESSING DETAIL PAGE: {link}")

                    tender_data = self.extract_tender_data(link)
                    if tender_data:
                        # Check year filter
                        if self.year_filter:
                            pub_date = tender_data.get('publication_date')
                            if pub_date and hasattr(pub_date, 'year'):
                                if pub_date.year not in self.year_filter:
                                    self.stats['tenders_skipped'] += 1
                                    continue

                        # Yield TenderItem
                        item = TenderItem()
                        item['tender_id'] = tender_data.get('tender_id', f"SEL-{tender_data.get('internal_id', 'UNK')}")
                        item['title'] = tender_data.get('title', 'Unknown')
                        item['procuring_entity'] = tender_data.get('procuring_entity')
                        item['estimated_value_mkd'] = tender_data.get('estimated_value_mkd')
                        item['actual_value_mkd'] = tender_data.get('actual_value_mkd')  # NEW: Contract value
                        item['cpv_code'] = tender_data.get('cpv_code')
                        item['publication_date'] = tender_data.get('publication_date')
                        item['winner'] = tender_data.get('winner')
                        item['num_bidders'] = tender_data.get('num_bidders')  # NEW: Number of bidders
                        item['source_url'] = tender_data.get('source_url')
                        item['procedure_type'] = tender_data.get('procedure_type')
                        item['status'] = 'awarded' if self.category == 'awarded' else 'open'

                        # Log extraction with actual_value for debugging
                        actual_val = item.get('actual_value_mkd')
                        logger.warning(f"✅ Extracted tender: {item['tender_id']} | actual_value={actual_val} | bidders={len(tender_data.get('bidders', []))}")
                        self.stats['tenders_saved'] += 1

                        yield item

                        # Yield bidders (NEW)
                        for bidder in tender_data.get('bidders', []):
                            bidder_item = {
                                'type': 'bidder',
                                'tender_id': item['tender_id'],
                                'company_name': bidder.get('company_name'),
                                'bid_amount_mkd': bidder.get('bid_amount_mkd'),
                                'is_winner': bidder.get('is_winner', False),
                            }
                            # Note: Pipeline will need to handle this
                            logger.debug(f"  Bidder: {bidder.get('company_name')[:50]}... | {bidder.get('bid_amount_mkd')}")

                        # Yield documents
                        for doc in tender_data.get('documents', []):
                            doc_item = DocumentItem()
                            doc_item['tender_id'] = item['tender_id']
                            doc_item['file_url'] = doc.get('file_url')
                            doc_item['file_name'] = doc.get('file_name')
                            yield doc_item

                    # Return to listing page
                    self.driver.get(url)
                    time.sleep(2)
                    self.wait_for_angular()

                    # Re-apply filter and navigate to current page
                    if self.year_filter:
                        years = sorted(self.year_filter)
                        self.apply_year_filter_server(years[0])

                    # Navigate to current page
                    for _ in range(page_num - 1):
                        if not self.click_next_page():
                            break

                    time.sleep(1)

                # Try next page
                if not self.click_next_page():
                    logger.info("Reached last page")
                    break

                # Stop if no new links found
                if not new_links and not self.force_full_scan:
                    logger.info("No new links found, stopping pagination")
                    break

        except Exception as e:
            logger.error(f"Spider error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            if self.driver:
                self.driver.quit()

            logger.warning("=" * 60)
            logger.warning("SCRAPE STATISTICS")
            logger.warning(f"Pages scraped: {self.stats['pages_scraped']}")
            logger.warning(f"Tenders found: {self.stats['tenders_found']}")
            logger.warning(f"Tenders saved: {self.stats['tenders_saved']}")
            logger.warning(f"Tenders skipped: {self.stats['tenders_skipped']}")
            logger.warning(f"Errors: {self.stats['errors']}")
            logger.warning("=" * 60)

    def closed(self, reason):
        """Clean up when spider closes."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
