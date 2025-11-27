"""
Contracts Spider - Scrapes awarded contracts from e-nabavki.gov.mk
Enhanced with login functionality to extract detailed bidder/item data

This spider:
1. Logs into e-nabavki.gov.mk using credentials from environment variables
2. Scrapes contracts list table to get basic contract data and links
3. Visits each contract's detail page to extract:
   - All bidders with their bid amounts
   - Items/products with prices and quantities
   - Documents

Environment Variables (REQUIRED for detail scraping):
    NABAVKI_USERNAME: Login username for e-nabavki.gov.mk
    NABAVKI_PASSWORD: Login password for e-nabavki.gov.mk

Usage:
    # Basic scraping (list table only - no login required):
    scrapy crawl contracts -a max_pages=10

    # Full scraping with detail pages (requires login):
    NABAVKI_USERNAME=xxx NABAVKI_PASSWORD=xxx scrapy crawl contracts -a scrape_details=true

Table structure on contracts page (12 columns):
- Column 0: Број на оглас (Tender number) - links to dossie-acpp
- Column 1: Договорен орган (Contracting authority)
- Column 2: Предмет на договорот (Contract subject)
- Column 3: Вид на договор (Contract type: Стоки/Услуги/Работи)
- Column 4: Вид на постапка (Procedure type)
- Column 5: Датум на договор (Contract date)
- Column 6: Носител на набавката (Winner/Procurement holder) ***
- Column 7: Проценета вредност со ДДВ (Estimated value with VAT)
- Column 8: Вредност на договорот со ДДВ (Contract value with VAT)
- Column 9: Датум на објава (Publication date)
- Column 10: Вистински сопственици (Beneficial owners) - "Прикажи" button
- Column 11: Документи (Documents) - "Прикажи" button
"""

import scrapy
import json
import re
import os
import logging
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List
from pathlib import Path
from scrapy_playwright.page import PageMethod
from scraper.items import TenderItem, DocumentItem

logger = logging.getLogger(__name__)

# Cookie storage path for session persistence
COOKIE_FILE = Path('/tmp/contracts_auth_cookies.json')
SESSION_FILE = Path('/tmp/contracts_auth_session.json')


class ContractsSpider(scrapy.Spider):
    name = 'contracts'
    allowed_domains = ['e-nabavki.gov.mk']

    # Start URL - contracts list page
    start_urls = ['https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0']

    # Login page URL
    LOGIN_URL = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/home'

    custom_settings = {
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 120000,
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'CONCURRENT_REQUESTS': 1,  # Sequential to handle pagination properly
        'DOWNLOAD_DELAY': 1,
    }

    def __init__(self, max_pages=None, scrape_details=None, username=None, password=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages) if max_pages else 15000  # 109K records / 10 per page
        self.contracts_scraped = 0
        self.bidders_extracted = 0
        self.details_scraped = 0

        # Whether to scrape detail pages (requires login)
        self.scrape_details = scrape_details == 'true' or scrape_details is True

        # Get credentials from args or environment
        self.username = username or os.environ.get('NABAVKI_USERNAME')
        self.password = password or os.environ.get('NABAVKI_PASSWORD')

        # Session state
        self.is_logged_in = False
        self.cookies = None
        self.login_time = None

        # Pending detail URLs to scrape (collected from list, scraped after)
        self.pending_detail_urls = []

        # Stats
        self.stats = {
            'login_success': False,
            'contracts_scraped': 0,
            'details_scraped': 0,
            'bidders_extracted': 0,
            'documents_extracted': 0,
            'errors': [],
        }

        logger.warning("=" * 70)
        logger.warning("CONTRACTS SPIDER INITIALIZED")
        logger.warning("=" * 70)
        logger.warning(f"Max pages: {self.max_pages}")
        logger.warning(f"Scrape details: {self.scrape_details}")
        logger.warning(f"Username: {self.username or 'Not provided'}")
        logger.warning("=" * 70)

    def _load_saved_cookies(self) -> bool:
        """Load saved cookies from file if they exist and are not expired."""
        try:
            if COOKIE_FILE.exists() and SESSION_FILE.exists():
                with open(SESSION_FILE, 'r') as f:
                    session_data = json.load(f)

                # Check if session is still valid (cookies expire after 4 hours)
                login_time = datetime.fromisoformat(session_data.get('login_time', '2000-01-01'))
                expiry_time = login_time + timedelta(hours=4)

                if datetime.utcnow() < expiry_time:
                    with open(COOKIE_FILE, 'r') as f:
                        self.cookies = json.load(f)

                    self.login_time = login_time
                    logger.warning(f"Loaded saved cookies from {COOKIE_FILE}")
                    logger.warning(f"Session valid until: {expiry_time.isoformat()}")
                    return True
                else:
                    logger.warning("Saved cookies have expired, will re-login")

        except Exception as e:
            logger.warning(f"Could not load saved cookies: {e}")

        return False

    def _save_cookies(self, cookies: List[Dict]) -> None:
        """Save cookies to file for reuse in subsequent runs."""
        try:
            self.login_time = datetime.utcnow()
            expiry_time = self.login_time + timedelta(hours=4)

            # Save cookies
            with open(COOKIE_FILE, 'w') as f:
                json.dump(cookies, f, indent=2)

            # Save session metadata
            session_data = {
                'login_time': self.login_time.isoformat(),
                'username': self.username,
                'cookie_count': len(cookies),
            }
            with open(SESSION_FILE, 'w') as f:
                json.dump(session_data, f, indent=2)

            logger.warning(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")
            logger.warning(f"Session valid until: {expiry_time.isoformat()}")

        except Exception as e:
            logger.error(f"Could not save cookies: {e}")

    def start_requests(self):
        """Start with login if scraping details, otherwise go to contracts list"""
        if self.scrape_details:
            # Check if credentials are provided
            if not self.username or not self.password:
                logger.error("Credentials required for detail scraping! Set NABAVKI_USERNAME and NABAVKI_PASSWORD")
                logger.warning("Falling back to basic list scraping (no login)")
                self.scrape_details = False
            else:
                # Try to load saved cookies first
                if self._load_saved_cookies():
                    logger.warning("Using saved session cookies")
                    self.is_logged_in = True
                    self.stats['login_success'] = True
                else:
                    # Need to login first
                    logger.warning("Starting login process...")
                    yield scrapy.Request(
                        self.LOGIN_URL,
                        callback=self.perform_login,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'playwright_page_goto_kwargs': {
                                'wait_until': 'networkidle',
                                'timeout': 120000,
                            },
                        },
                        errback=self.errback_playwright,
                        dont_filter=True
                    )
                    return  # Login will chain to contracts list

        # Go to contracts list (either after login or for basic scraping)
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_contracts_list,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                        'timeout': 120000,
                    },
                },
                errback=self.errback_playwright,
                dont_filter=True,
            )

    async def perform_login(self, response):
        """Perform login using Playwright"""
        page = response.meta.get('playwright_page')

        if not page:
            logger.error("No Playwright page available for login")
            return

        try:
            logger.warning("Attempting login to e-nabavki.gov.mk...")
            logger.warning(f"Using credentials: {self.username}")

            # Wait for page to fully load (Angular app)
            await page.wait_for_timeout(3000)

            # =========================================================
            # STEP 1: Find and fill the username field
            # =========================================================
            username_selectors = [
                'input[placeholder*="Корисничко"]',
                'input[placeholder*="корисничко"]',
                'input[ng-model*="userName"]',
                'input[ng-model*="username"]',
                'input[type="text"]',
                'input[name="userName"]',
                'input[name="username"]',
            ]

            username_filled = False
            for selector in username_selectors:
                try:
                    field = await page.query_selector(selector)
                    if field:
                        is_visible = await field.is_visible()
                        if is_visible:
                            await field.fill('')
                            await field.fill(self.username)
                            username_filled = True
                            logger.info(f"✓ Filled username with selector: {selector}")
                            break
                except Exception:
                    continue

            if not username_filled:
                logger.error("✗ Could not find username field")
                await page.close()
                return

            # =========================================================
            # STEP 2: Find and fill the password field
            # =========================================================
            password_selectors = [
                'input[type="password"]',
                'input[placeholder*="Лозинка"]',
                'input[placeholder*="лозинка"]',
                'input[ng-model*="password"]',
            ]

            password_filled = False
            for selector in password_selectors:
                try:
                    field = await page.query_selector(selector)
                    if field:
                        is_visible = await field.is_visible()
                        if is_visible:
                            await field.fill('')
                            await field.fill(self.password)
                            password_filled = True
                            logger.info(f"✓ Filled password with selector: {selector}")
                            break
                except Exception:
                    continue

            if not password_filled:
                logger.error("✗ Could not find password field")
                await page.close()
                return

            await page.wait_for_timeout(500)

            # =========================================================
            # STEP 3: Click the submit button
            # =========================================================
            submit_selectors = [
                'button:has-text("Влез")',
                'input[value="Влез"]',
                'button[type="submit"]',
                'input[type="submit"]',
                'button[ng-click*="login"]',
                'button.btn-primary',
            ]

            submitted = False
            for selector in submit_selectors:
                try:
                    btn = await page.query_selector(selector)
                    if btn:
                        is_visible = await btn.is_visible()
                        if is_visible:
                            await btn.click()
                            submitted = True
                            logger.info(f"✓ Clicked submit with selector: {selector}")
                            break
                except Exception:
                    continue

            if not submitted:
                logger.warning("No submit button found, pressing Enter")
                await page.keyboard.press('Enter')

            # =========================================================
            # STEP 4: Wait for login to complete and verify
            # =========================================================
            logger.warning("Waiting for login to complete...")
            await page.wait_for_timeout(5000)

            # Check for successful login indicators
            page_content = await page.content()
            success_texts = ['одјава', 'logout', 'профил', 'profile', self.username.lower()]
            login_verified = any(text in page_content.lower() for text in success_texts)

            if login_verified:
                self.is_logged_in = True
                self.stats['login_success'] = True

                logger.warning("=" * 70)
                logger.warning("✓ LOGIN SUCCESSFUL")
                logger.warning("=" * 70)

                # Save cookies for future use
                cookies = await page.context.cookies()
                self._save_cookies(cookies)

                await page.close()

                # Now go to contracts list
                for url in self.start_urls:
                    yield scrapy.Request(
                        url=url,
                        callback=self.parse_contracts_list,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'playwright_page_goto_kwargs': {
                                'wait_until': 'networkidle',
                                'timeout': 120000,
                            },
                        },
                        errback=self.errback_playwright,
                        dont_filter=True,
                    )
            else:
                logger.error("✗ LOGIN FAILED - Could not verify successful login")
                self.stats['errors'].append('Login failed')
                await page.close()
                # Fall back to basic scraping
                self.scrape_details = False
                for url in self.start_urls:
                    yield scrapy.Request(
                        url=url,
                        callback=self.parse_contracts_list,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'playwright_page_goto_kwargs': {
                                'wait_until': 'networkidle',
                                'timeout': 120000,
                            },
                        },
                        errback=self.errback_playwright,
                        dont_filter=True,
                    )

        except Exception as e:
            logger.error(f"Login error: {e}")
            self.stats['errors'].append(f'Login error: {str(e)}')
            try:
                await page.close()
            except:
                pass

    async def parse_contracts_list(self, response):
        """
        Parse the contracts list table and extract winner data from each row.
        Handles pagination to scrape all 109K+ contracts.
        """
        page = response.meta.get('playwright_page')

        if not page:
            logger.error("No Playwright page available")
            return

        try:
            # Wait for contracts table to load
            await page.wait_for_selector('table#contracts-grid tbody tr', timeout=60000)
            await page.wait_for_timeout(3000)  # Extra wait for data binding
            logger.info("✓ Contracts table loaded successfully")

            current_page = 1
            consecutive_empty = 0
            consecutive_errors = 0

            while current_page <= self.max_pages:
                try:
                    # Extract data from current page's table rows
                    rows = await page.query_selector_all('table#contracts-grid tbody tr')

                    if not rows:
                        consecutive_empty += 1
                        if consecutive_empty >= 3:
                            logger.warning("No rows found for 3 consecutive pages, stopping")
                            break
                        await page.wait_for_timeout(2000)
                        continue
                    else:
                        consecutive_empty = 0
                        consecutive_errors = 0  # Reset error counter on success

                    logger.info(f"Page {current_page}: Processing {len(rows)} contract rows")

                    for row in rows:
                        try:
                            contract_data, detail_url = await self._extract_row_data(row, page)
                            if contract_data:
                                self.contracts_scraped += 1
                                self.stats['contracts_scraped'] += 1

                                # Collect detail URL for later scraping if logged in
                                if self.scrape_details and detail_url:
                                    self.pending_detail_urls.append({
                                        'url': detail_url,
                                        'tender_id': contract_data.get('tender_id'),
                                        'basic_data': dict(contract_data),
                                    })
                                else:
                                    # Yield immediately if not scraping details
                                    yield contract_data
                        except Exception as e:
                            logger.warning(f"Error extracting row: {e}")
                            continue

                    # Progress logging every 50 pages
                    if current_page % 50 == 0:
                        logger.warning(f"Progress: Page {current_page}, Contracts: {self.contracts_scraped}, Pending details: {len(self.pending_detail_urls)}")

                    # Try to go to next page
                    has_next = await self._click_next_page(page)
                    if not has_next:
                        logger.info("No more pages available")
                        break

                    current_page += 1

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Error on page {current_page} (attempt {consecutive_errors}): {e}")
                    if consecutive_errors >= 5:
                        logger.error("Too many consecutive errors, stopping list scraping")
                        break
                    await page.wait_for_timeout(5000)
                    continue

            logger.warning(f"✓ List scraping complete: {self.contracts_scraped} contracts")

            await page.close()

            # Now scrape detail pages if logged in
            if self.scrape_details and self.pending_detail_urls:
                logger.warning(f"Starting detail scraping for {len(self.pending_detail_urls)} contracts...")
                for detail_info in self.pending_detail_urls:
                    yield scrapy.Request(
                        url=detail_info['url'],
                        callback=self.parse_contract_detail,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'playwright_page_goto_kwargs': {
                                'wait_until': 'networkidle',
                                'timeout': 120000,
                            },
                            'tender_id': detail_info['tender_id'],
                            'basic_data': detail_info['basic_data'],
                        },
                        errback=self.errback_playwright,
                        dont_filter=True,
                    )

        except Exception as e:
            logger.error(f"Error parsing contracts list: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                await page.close()
            except:
                pass

    async def _extract_row_data(self, row, page) -> tuple:
        """
        Extract contract and winner data from a table row.
        Returns (TenderItem, detail_url) tuple.
        """
        cells = await row.query_selector_all('td')

        if len(cells) < 10:
            logger.warning(f"Row has only {len(cells)} cells, skipping")
            return None, None

        try:
            # Extract tender link and number
            tender_link_elem = await cells[0].query_selector('a')
            tender_link = await tender_link_elem.get_attribute('href') if tender_link_elem else None
            tender_number_text = await cells[0].inner_text()
            tender_number = tender_number_text.strip()

            # Extract tender ID from link (UUID format) or use tender number
            tender_id = None
            detail_url = None
            if tender_link:
                uuid_match = re.search(r'dossie-acpp/([a-f0-9-]{36})', tender_link)
                if uuid_match:
                    tender_id = uuid_match.group(1)
                # Construct full detail URL
                if tender_link.startswith('#'):
                    detail_url = f'https://e-nabavki.gov.mk/PublicAccess/home.aspx{tender_link}'
                elif tender_link.startswith('/'):
                    detail_url = f'https://e-nabavki.gov.mk{tender_link}'
                elif not tender_link.startswith('http'):
                    detail_url = f'https://e-nabavki.gov.mk/PublicAccess/home.aspx{tender_link}'
                else:
                    detail_url = tender_link

            # Fallback: use tender number as ID
            if not tender_id:
                tender_id = tender_number.replace('/', '_')

            # Extract other fields
            contracting_authority = (await cells[1].inner_text()).strip() if len(cells) > 1 else ''
            contract_subject = (await cells[2].inner_text()).strip() if len(cells) > 2 else ''
            contract_type = (await cells[3].inner_text()).strip() if len(cells) > 3 else ''
            procedure_type = (await cells[4].inner_text()).strip() if len(cells) > 4 else ''
            contract_date = (await cells[5].inner_text()).strip() if len(cells) > 5 else ''
            winner_name = (await cells[6].inner_text()).strip() if len(cells) > 6 else ''
            estimated_value_text = (await cells[7].inner_text()).strip() if len(cells) > 7 else ''
            contract_value_text = (await cells[8].inner_text()).strip() if len(cells) > 8 else ''
            publication_date = (await cells[9].inner_text()).strip() if len(cells) > 9 else ''

            # Debug log first extraction
            if self.contracts_scraped == 0:
                logger.info(f"First row extracted: tender={tender_number}, winner={winner_name[:30] if winner_name else 'N/A'}...")

            # Parse currency values
            estimated_value = self._parse_currency(estimated_value_text)
            contract_value = self._parse_currency(contract_value_text)

            # Parse dates
            contract_date_parsed = self._parse_date(contract_date)
            publication_date_parsed = self._parse_date(publication_date)

            if winner_name:
                self.bidders_extracted += 1
                self.stats['bidders_extracted'] += 1

            # Create bidder data for the winner (basic data from list)
            bidders_data = None
            if winner_name:
                bidders_data = json.dumps([{
                    'company_name': winner_name,
                    'bid_amount_mkd': contract_value,
                    'is_winner': True,
                    'rank': 1,
                    'disqualified': False
                }], ensure_ascii=False)

            # Return a TenderItem
            item = TenderItem()
            item['tender_id'] = tender_id
            item['title'] = contract_subject
            item['procuring_entity'] = contracting_authority
            item['category'] = contract_type
            item['procedure_type'] = procedure_type
            item['contract_signing_date'] = contract_date_parsed
            item['publication_date'] = publication_date_parsed
            item['estimated_value_mkd'] = estimated_value
            item['actual_value_mkd'] = contract_value
            item['winner'] = winner_name
            item['bidders_data'] = bidders_data
            item['status'] = 'awarded'
            item['source_category'] = 'awarded'
            item['source_url'] = detail_url or tender_link
            item['scraped_at'] = datetime.now().isoformat()

            return item, detail_url

        except Exception as e:
            logger.warning(f"Error extracting row data: {e}")
            return None, None

    async def parse_contract_detail(self, response):
        """
        Parse contract detail page to extract bidders, items, and documents.
        This is called for each contract when scrape_details=true.
        """
        page = response.meta.get('playwright_page')
        tender_id = response.meta.get('tender_id')
        basic_data = response.meta.get('basic_data', {})

        if not page:
            logger.error(f"No Playwright page for detail: {tender_id}")
            return

        try:
            logger.info(f"Scraping detail page for: {tender_id}")

            # Wait for detail page to load
            await page.wait_for_selector('label.dosie-value, .tender-detail, .dossie-content', timeout=30000)
            await page.wait_for_timeout(2000)

            # Start with basic data from list
            item = TenderItem()
            for key, value in basic_data.items():
                item[key] = value

            # Extract additional data from detail page
            html_content = await page.content()

            # =========================================================
            # Extract ALL bidders (not just winner)
            # =========================================================
            bidders = await self._extract_bidders_from_page(page, tender_id)
            if bidders:
                item['bidders_data'] = json.dumps(bidders, ensure_ascii=False)
                item['num_bidders'] = len(bidders)
                self.stats['bidders_extracted'] += len(bidders) - 1  # Don't double count winner

            # =========================================================
            # Extract CPV code
            # =========================================================
            cpv_code = await self._extract_cpv_code(page)
            if cpv_code:
                item['cpv_code'] = cpv_code

            # =========================================================
            # Extract contact information
            # =========================================================
            contact_person = await self._extract_field(page, 'contact_person')
            contact_email = await self._extract_field(page, 'contact_email')
            contact_phone = await self._extract_field(page, 'contact_phone')
            if contact_person:
                item['contact_person'] = contact_person
            if contact_email:
                item['contact_email'] = contact_email
            if contact_phone:
                item['contact_phone'] = contact_phone

            # =========================================================
            # Extract documents
            # =========================================================
            documents = await self._extract_documents(page, tender_id)
            if documents:
                item['documents_data'] = documents
                self.stats['documents_extracted'] += len(documents)

            # =========================================================
            # Extract lots/items if available
            # =========================================================
            lots = await self._extract_lots(page, tender_id)
            if lots:
                item['lots_data'] = json.dumps(lots, ensure_ascii=False)
                item['has_lots'] = True
                item['num_lots'] = len(lots)

            # Generate content hash
            item['content_hash'] = self._generate_content_hash(item)

            self.details_scraped += 1
            self.stats['details_scraped'] += 1

            logger.info(f"✓ Detail scraped: {tender_id} - {len(bidders) if bidders else 0} bidders, {len(documents) if documents else 0} docs")

            # Yield document items
            if documents:
                for doc in documents:
                    yield DocumentItem(
                        tender_id=doc.get('tender_id'),
                        file_url=doc.get('url'),
                        file_name=doc.get('file_name'),
                        doc_category=doc.get('doc_category'),
                        upload_date=doc.get('upload_date'),
                        doc_type=doc.get('doc_type', 'document'),
                        extraction_status='pending'
                    )

            yield item

        except Exception as e:
            logger.error(f"Error scraping detail for {tender_id}: {e}")
            self.stats['errors'].append(f"Detail error {tender_id}: {str(e)}")
            # Still yield basic data
            item = TenderItem()
            for key, value in basic_data.items():
                item[key] = value
            yield item

        finally:
            try:
                await page.close()
            except:
                pass

    async def _extract_bidders_from_page(self, page, tender_id: str) -> List[Dict]:
        """Extract all bidders with their bid amounts from detail page"""
        bidders = []

        try:
            # Look for bidder tables with various selectors
            table_selectors = [
                'table:has(th:text-matches("Понудувач|Учесник|Економски оператор", "i"))',
                'table.bidders-table',
                '#bidders-grid',
                'table:has(td:text-matches("Понудувач", "i"))',
            ]

            for selector in table_selectors:
                try:
                    table = await page.query_selector(selector)
                    if table:
                        rows = await table.query_selector_all('tbody tr')
                        if rows:
                            for idx, row in enumerate(rows, start=1):
                                cells = await row.query_selector_all('td')
                                if len(cells) >= 2:
                                    company_name = await cells[0].inner_text()
                                    company_name = company_name.strip() if company_name else ''

                                    # Try to find bid amount in any cell
                                    bid_amount = None
                                    for cell in cells:
                                        cell_text = await cell.inner_text()
                                        amount = self._parse_currency(cell_text)
                                        if amount:
                                            bid_amount = amount
                                            break

                                    # Check if winner
                                    row_html = await row.inner_html()
                                    is_winner = any(ind in row_html.lower() for ind in ['победник', 'добитник', 'избран', 'winner'])
                                    disqualified = 'дисквалиф' in row_html.lower()

                                    if company_name:
                                        bidders.append({
                                            'company_name': company_name,
                                            'bid_amount_mkd': bid_amount,
                                            'is_winner': is_winner,
                                            'rank': idx,
                                            'disqualified': disqualified,
                                        })
                            break  # Found bidders table, stop looking
                except Exception:
                    continue

            # Alternative: Look for bidder info in text sections
            if not bidders:
                # Try to extract from page text using patterns
                page_text = await page.content()

                # Look for "Понудувачи:" section
                bidder_section_match = re.search(r'Понудувачи[:\s]*(.+?)(?=<h|<div class="section"|$)', page_text, re.DOTALL | re.IGNORECASE)
                if bidder_section_match:
                    section = bidder_section_match.group(1)
                    # Extract company names from list items or divs
                    company_matches = re.findall(r'<li[^>]*>([^<]+)</li>|<div[^>]*class="bidder[^"]*"[^>]*>([^<]+)</div>', section)
                    for match in company_matches:
                        company_name = match[0] or match[1]
                        if company_name:
                            bidders.append({
                                'company_name': company_name.strip(),
                                'bid_amount_mkd': None,
                                'is_winner': False,
                                'rank': len(bidders) + 1,
                                'disqualified': False,
                            })

        except Exception as e:
            logger.warning(f"Error extracting bidders: {e}")

        return bidders

    async def _extract_cpv_code(self, page) -> Optional[str]:
        """Extract CPV code from detail page"""
        try:
            selectors = [
                'label[label-for*="CPV"] + label.dosie-value',
                'label:has-text("CPV") + label.dosie-value',
                '*:has-text("CPV код")',
            ]

            for selector in selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        text = await elem.inner_text()
                        # Extract 8-digit CPV code
                        match = re.search(r'\b(\d{8}(?:-\d)?)\b', text)
                        if match:
                            return match.group(1)
                except Exception:
                    continue

            # Fallback: search page text
            page_text = await page.content()
            match = re.search(r'\b(\d{8}-\d)\b', page_text)
            if match:
                return match.group(1)
            match = re.search(r'\b(\d{8})\b(?!\d)', page_text)
            if match:
                return match.group(1)

        except Exception as e:
            logger.debug(f"Error extracting CPV: {e}")

        return None

    async def _extract_field(self, page, field_name: str) -> Optional[str]:
        """Extract a field from detail page using multiple selectors"""
        FIELD_SELECTORS = {
            'contact_person': [
                'label:has-text("Контакт лице") + label.dosie-value',
                'label[label-for*="CONTACT PERSON"] + label.dosie-value',
            ],
            'contact_email': [
                'label:has-text("Е-пошта") + label.dosie-value',
                'label:has-text("E-mail") + label.dosie-value',
            ],
            'contact_phone': [
                'label:has-text("Телефон") + label.dosie-value',
            ],
        }

        selectors = FIELD_SELECTORS.get(field_name, [])
        for selector in selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    text = await elem.inner_text()
                    text = text.strip()
                    if text and text not in ('N/A', '-', ''):
                        return text
            except Exception:
                continue

        return None

    async def _extract_documents(self, page, tender_id: str) -> List[Dict]:
        """Extract document links from detail page"""
        documents = []
        seen_urls = set()

        try:
            # Look for document links
            link_selectors = [
                'a[href*="Download"]',
                'a[href*=".pdf"]',
                'a[href*=".doc"]',
                'a[href*="File"]',
                'a[href*="Attachment"]',
            ]

            for selector in link_selectors:
                try:
                    links = await page.query_selector_all(selector)
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and href not in seen_urls:
                            seen_urls.add(href)

                            if not href.startswith('http'):
                                href = f'https://e-nabavki.gov.mk{href}'

                            # Skip external bank docs
                            if 'ohridskabanka' in href.lower():
                                continue

                            # Extract filename
                            filename = href.split('/')[-1] if '/' in href else 'document'
                            if '?' in filename:
                                filename = filename.split('?')[0]

                            # Classify document
                            doc_category = self._classify_document(filename, href)

                            documents.append({
                                'url': href,
                                'tender_id': tender_id,
                                'doc_category': doc_category,
                                'upload_date': None,
                                'file_name': filename,
                                'doc_type': 'document',
                            })
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Error extracting documents: {e}")

        return documents

    async def _extract_lots(self, page, tender_id: str) -> List[Dict]:
        """Extract lot/item information from detail page"""
        lots = []

        try:
            # Look for lot tables
            table_selectors = [
                'table:has(th:text-matches("Лот|Дел|Предмет", "i"))',
                '#lots-grid',
                'table.lots-table',
            ]

            for selector in table_selectors:
                try:
                    table = await page.query_selector(selector)
                    if table:
                        rows = await table.query_selector_all('tbody tr')
                        for idx, row in enumerate(rows, start=1):
                            cells = await row.query_selector_all('td')
                            if len(cells) >= 2:
                                lot_title = await cells[0].inner_text()
                                lot_title = lot_title.strip() if lot_title else ''

                                lot_data = {
                                    'lot_number': str(idx),
                                    'lot_title': lot_title,
                                }

                                # Try to extract value and CPV
                                for cell in cells:
                                    cell_text = await cell.inner_text()
                                    # CPV code
                                    cpv_match = re.search(r'\b(\d{8})\b', cell_text)
                                    if cpv_match:
                                        lot_data['cpv_code'] = cpv_match.group(1)
                                    # Value
                                    amount = self._parse_currency(cell_text)
                                    if amount and 'estimated_value_mkd' not in lot_data:
                                        lot_data['estimated_value_mkd'] = amount

                                lots.append(lot_data)
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Error extracting lots: {e}")

        return lots

    def _classify_document(self, filename: str, url: str) -> str:
        """Classify document by type based on filename/URL"""
        combined = (filename + ' ' + url).lower()

        classifications = {
            'tender_document': ['тендер', 'набавка', 'јавен', 'tender', 'procurement'],
            'technical_spec': ['технич', 'спецификација', 'spec', 'technical'],
            'amendment': ['измен', 'допол', 'amend', 'correction'],
            'award': ['одлука', 'резултат', 'award', 'decision', 'result'],
            'contract': ['договор', 'contract', 'потпишан'],
            'bid': ['понуда', 'bid', 'offer'],
        }

        for category, keywords in classifications.items():
            if any(kw in combined for kw in keywords):
                return category

        return 'other'

    def _parse_currency(self, value_text: str) -> Optional[float]:
        """Parse Macedonian currency format: 1.234.567,89ден."""
        if not value_text:
            return None

        try:
            # Remove "ден." suffix and whitespace
            cleaned = value_text.replace('ден.', '').replace('ден', '').strip()

            # Handle Macedonian format: 1.234.567,89
            cleaned = cleaned.replace('.', '').replace(',', '.')

            value = float(cleaned)
            return value if value > 0 else None
        except (ValueError, AttributeError):
            return None

    def _parse_date(self, date_text: str) -> Optional[str]:
        """Parse date in DD.MM.YYYY format to ISO format"""
        if not date_text:
            return None

        try:
            dt = datetime.strptime(date_text.strip(), '%d.%m.%Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            return None

    def _generate_content_hash(self, item) -> str:
        """Generate hash of tender content for change detection"""
        content_parts = []
        for field in ['tender_id', 'title', 'closing_date', 'estimated_value_mkd', 'winner', 'bidders_data']:
            value = item.get(field)
            if value is not None:
                content_parts.append(f"{field}:{value}")
        content_str = '|'.join(content_parts)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()[:16]

    async def _click_next_page(self, page) -> bool:
        """Click the Next button in pagination, return False if no more pages"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                next_btn = await page.query_selector('li.next:not(.disabled) a')

                if not next_btn:
                    return False

                await next_btn.click()
                await page.wait_for_timeout(3000)

                await page.wait_for_selector('table#contracts-grid tbody tr', timeout=120000)
                await page.wait_for_timeout(1500)

                return True

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Pagination attempt {attempt + 1} failed: {e}, retrying...")
                    await page.wait_for_timeout(5000)
                    continue
                else:
                    logger.warning(f"Pagination failed after {max_retries} attempts: {e}")
                    return False
        return False

    async def errback_playwright(self, failure):
        """Handle Playwright errors"""
        logger.error(f"Playwright error: {failure.value}")
        self.stats['errors'].append(str(failure.value))

        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except:
                pass

    def close(self, reason):
        """Called when spider closes - print statistics"""
        logger.warning("=" * 70)
        logger.warning("CONTRACTS SPIDER COMPLETE - STATISTICS")
        logger.warning("=" * 70)
        logger.warning(f"Login success: {self.stats['login_success']}")
        logger.warning(f"Scrape details: {self.scrape_details}")
        logger.warning(f"Contracts scraped: {self.stats['contracts_scraped']}")
        logger.warning(f"Details scraped: {self.stats['details_scraped']}")
        logger.warning(f"Bidders extracted: {self.stats['bidders_extracted']}")
        logger.warning(f"Documents extracted: {self.stats['documents_extracted']}")
        logger.warning(f"Errors: {len(self.stats['errors'])}")
        if self.stats['errors'][:5]:
            logger.warning(f"Sample errors: {self.stats['errors'][:5]}")
        logger.warning("=" * 70)
