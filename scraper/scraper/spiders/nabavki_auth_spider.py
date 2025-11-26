"""
E-nabavki.gov.mk Authenticated Spider - Scrapes protected pages with login
Uses Playwright for JavaScript rendering and authentication

PHASE H Implementation:
- Robust Playwright authentication flow
- Cookie persistence and reuse
- max_items support for controlled testing
- Comprehensive field extraction

Usage:
    scrapy crawl nabavki_auth -a category=active -a max_items=10
    scrapy crawl nabavki_auth -a category=awarded
    scrapy crawl nabavki_auth -a category=all

Environment Variables (REQUIRED):
    NABAVKI_USERNAME: Login username for e-nabavki.gov.mk
    NABAVKI_PASSWORD: Login password for e-nabavki.gov.mk
"""

import scrapy
import logging
import os
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
import re
import hashlib
from pathlib import Path
from scrapy.http import Response
from scraper.items import TenderItem, DocumentItem

logger = logging.getLogger(__name__)

# Cookie storage path
COOKIE_FILE = Path('/tmp/nabavki_auth_cookies.json')
SESSION_FILE = Path('/tmp/nabavki_auth_session.json')


class NabavkiAuthSpider(scrapy.Spider):
    """
    Authenticated spider for e-nabavki.gov.mk

    Features:
    - Persistent cookie storage for session reuse
    - max_items parameter for controlled testing
    - Comprehensive field extraction with fallbacks
    - Detailed statistics and health reporting
    """

    name = 'nabavki_auth'
    allowed_domains = ['e-nabavki.gov.mk']

    # Category URL mapping for authenticated pages
    CATEGORY_URLS = {
        'active': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices',
        'awarded': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0',
        'cancelled': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/cancelations',
        'historical': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/realized-contract',
        'tender_winners': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/tender-winners/0',
        'planned': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/announcement-plans',
    }

    # Login page URL - the home page has the login form on the left side
    LOGIN_URL = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/home'

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1,
        "PLAYWRIGHT_MAX_CONTEXTS": 2,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        "DUPEFILTER_CLASS": "scrapy.dupefilters.BaseDupeFilter",
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 5.0,
    }

    def __init__(self, category='active', username=None, password=None, max_items=None, *args, **kwargs):
        """
        Initialize authenticated spider.

        Args:
            category: One of 'active', 'awarded', 'cancelled', 'historical', 'tender_winners', 'planned', 'all'
            username: Login username (optional, uses NABAVKI_USERNAME env var)
            password: Login password (optional, uses NABAVKI_PASSWORD env var)
            max_items: Maximum number of tenders to scrape (for testing)

        Raises:
            ValueError: If credentials are not provided via args or environment variables
        """
        super().__init__(*args, **kwargs)
        self.category = category.lower()

        # Get credentials from args or environment - NO DEFAULTS
        self.username = username or os.environ.get('NABAVKI_USERNAME')
        self.password = password or os.environ.get('NABAVKI_PASSWORD')

        # Validate credentials are provided
        if not self.username or not self.password:
            raise ValueError(
                "Credentials required! Set NABAVKI_USERNAME and NABAVKI_PASSWORD environment variables "
                "or pass -a username=xxx -a password=xxx to the spider."
            )

        # Max items for controlled testing
        self.max_items = int(max_items) if max_items else None
        self.items_scraped = 0

        # Session state
        self.is_logged_in = False
        self.cookies = None
        self.login_time = None
        self.cookie_expiry = None

        # Statistics for health reporting
        self.stats = {
            'login_attempts': 0,
            'login_success': False,
            'login_time': None,
            'cookie_expiry': None,
            'tenders_found': 0,
            'tenders_scraped': 0,
            'tenders_skipped': 0,
            'field_fill_rates': {},
            'errors': [],
            'categories_processed': [],
        }

        logger.warning("=" * 70)
        logger.warning("PHASE H: AUTHENTICATED SCRAPER INITIALIZED")
        logger.warning("=" * 70)
        logger.warning(f"Category: {self.category}")
        logger.warning(f"Username: {self.username}")
        logger.warning(f"Max items: {self.max_items or 'unlimited'}")
        logger.warning("=" * 70)

    def _load_saved_cookies(self) -> bool:
        """
        Load saved cookies from file if they exist and are not expired.

        Returns:
            True if valid cookies were loaded, False otherwise
        """
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
                    self.cookie_expiry = expiry_time
                    self.stats['login_time'] = login_time.isoformat()
                    self.stats['cookie_expiry'] = expiry_time.isoformat()

                    logger.warning(f"Loaded saved cookies from {COOKIE_FILE}")
                    logger.warning(f"Session valid until: {expiry_time.isoformat()}")
                    return True
                else:
                    logger.warning("Saved cookies have expired, will re-login")

        except Exception as e:
            logger.warning(f"Could not load saved cookies: {e}")

        return False

    def _save_cookies(self, cookies: List[Dict]) -> None:
        """
        Save cookies to file for reuse in subsequent runs.

        Args:
            cookies: List of cookie dictionaries from Playwright
        """
        try:
            self.login_time = datetime.utcnow()
            self.cookie_expiry = self.login_time + timedelta(hours=4)

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

            self.stats['login_time'] = self.login_time.isoformat()
            self.stats['cookie_expiry'] = self.cookie_expiry.isoformat()

            logger.warning(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")
            logger.warning(f"Session valid until: {self.cookie_expiry.isoformat()}")

        except Exception as e:
            logger.error(f"Could not save cookies: {e}")

    def start_requests(self):
        """Start with login page or use saved cookies"""
        logger.warning("=" * 70)
        logger.warning("AUTHENTICATED SCRAPER - Starting")
        logger.warning("=" * 70)

        # Try to load saved cookies first
        if self._load_saved_cookies():
            logger.warning("Using saved session cookies")
            self.is_logged_in = True
            self.stats['login_success'] = True

            # Go directly to scraping
            yield from self._generate_category_requests()
        else:
            # Need to login
            logger.warning("No valid saved cookies, performing login")
            yield scrapy.Request(
                self.LOGIN_URL,
                callback=self.perform_login,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                        'timeout': 60000,
                    },
                },
                errback=self.errback_playwright,
                dont_filter=True
            )

    def _generate_category_requests(self):
        """Generate requests for target categories after login"""
        if self.category == 'all':
            # Scrape all categories
            for cat, url in self.CATEGORY_URLS.items():
                yield scrapy.Request(
                    url,
                    callback=self.parse_authenticated_listing,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'networkidle',
                            'timeout': 60000,
                        },
                        'category': cat,
                    },
                    errback=self.errback_playwright,
                    dont_filter=True
                )
        else:
            # Single category
            url = self.CATEGORY_URLS.get(self.category)
            if url:
                yield scrapy.Request(
                    url,
                    callback=self.parse_authenticated_listing,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'networkidle',
                            'timeout': 60000,
                        },
                        'category': self.category,
                    },
                    errback=self.errback_playwright,
                    dont_filter=True
                )
            else:
                logger.error(f"Unknown category: {self.category}")

    async def perform_login(self, response):
        """
        Perform login using Playwright with updated selectors for e-nabavki.gov.mk

        The login form is on the left side of the home page:
        - Title: "ВЛЕЗ" (Login)
        - Username field: "Корисничко име" placeholder
        - Password field: "Лозинка" placeholder
        - Submit button: "Влез"
        """
        page = response.meta.get('playwright_page')
        self.stats['login_attempts'] += 1

        if not page:
            logger.error("No Playwright page available for login")
            return

        try:
            logger.warning("Attempting login to e-nabavki.gov.mk...")
            logger.warning(f"Using credentials: {self.username}")

            # Wait for page to fully load (Angular app)
            await page.wait_for_timeout(3000)

            # Save initial screenshot
            await self._save_screenshot(page, 'login_page_initial')

            # =========================================================
            # STEP 1: Find and fill the username field
            # The field has placeholder "Корисничко име" (Username)
            # =========================================================
            username_selectors = [
                # By placeholder text (Cyrillic)
                'input[placeholder*="Корисничко"]',
                'input[placeholder*="корисничко"]',
                # By ng-model (Angular binding)
                'input[ng-model*="userName"]',
                'input[ng-model*="username"]',
                'input[ng-model*="Username"]',
                # By type and position
                'input[type="text"]',
                # By name
                'input[name="userName"]',
                'input[name="username"]',
                # Generic text input in login form
                '.login input[type="text"]',
                'form input[type="text"]:first-of-type',
            ]

            username_filled = False
            for selector in username_selectors:
                try:
                    field = await page.query_selector(selector)
                    if field:
                        # Check if it's visible and enabled
                        is_visible = await field.is_visible()
                        if is_visible:
                            await field.fill('')  # Clear first
                            await field.fill(self.username)
                            username_filled = True
                            logger.info(f"✓ Filled username with selector: {selector}")
                            break
                except Exception as e:
                    continue

            if not username_filled:
                logger.error("✗ Could not find username field")
                await self._save_screenshot(page, 'login_no_username')
                # Try to dump page HTML for debugging
                html = await page.content()
                logger.debug(f"Page HTML snippet: {html[:2000]}")
                await page.close()
                return

            # =========================================================
            # STEP 2: Find and fill the password field
            # The field has placeholder "Лозинка" (Password)
            # =========================================================
            password_selectors = [
                'input[type="password"]',
                'input[placeholder*="Лозинка"]',
                'input[placeholder*="лозинка"]',
                'input[ng-model*="password"]',
                'input[ng-model*="Password"]',
                'input[name="password"]',
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
                except Exception as e:
                    continue

            if not password_filled:
                logger.error("✗ Could not find password field")
                await self._save_screenshot(page, 'login_no_password')
                await page.close()
                return

            await page.wait_for_timeout(500)
            await self._save_screenshot(page, 'login_credentials_filled')

            # =========================================================
            # STEP 3: Click the submit button
            # Button text: "Влез" (Enter/Login)
            # =========================================================
            submit_selectors = [
                # By text content (Cyrillic)
                'button:has-text("Влез")',
                'input[value="Влез"]',
                # By type
                'button[type="submit"]',
                'input[type="submit"]',
                # By ng-click
                'button[ng-click*="login"]',
                'button[ng-click*="Login"]',
                # By class
                'button.btn-primary',
                '.login button',
                '.login-form button',
                # Generic submit
                'form button',
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
                except Exception as e:
                    continue

            if not submitted:
                # Fallback: press Enter key
                logger.warning("No submit button found, pressing Enter")
                await page.keyboard.press('Enter')
                submitted = True

            # =========================================================
            # STEP 4: Wait for login to complete and verify
            # =========================================================
            logger.warning("Waiting for login to complete...")
            await page.wait_for_timeout(5000)

            await self._save_screenshot(page, 'login_after_submit')

            # Check for successful login indicators
            success_indicators = [
                # Logout button appears after login
                'a:has-text("Одјава")',
                'button:has-text("Одјава")',
                # User menu/profile
                '.user-menu',
                '.user-profile',
                '[ng-if*="isLoggedIn"]',
                # Username display
                f':has-text("{self.username}")',
                # Logout link
                'a[href*="logout"]',
                'a[ng-click*="logout"]',
            ]

            login_verified = False
            for selector in success_indicators:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        is_visible = await elem.is_visible()
                        if is_visible:
                            login_verified = True
                            logger.warning(f"✓ Login verified with indicator: {selector}")
                            break
                except:
                    continue

            # Also check page content for success indicators
            page_content = await page.content()
            success_texts = ['одјава', 'logout', 'профил', 'profile', self.username.lower()]
            for text in success_texts:
                if text in page_content.lower():
                    login_verified = True
                    logger.warning(f"✓ Login verified: found '{text}' in page content")
                    break

            # Only check for SPECIFIC error messages if we didn't find success indicators
            # Don't use generic 'error' as it appears in JavaScript on every page
            if not login_verified:
                error_indicators = [
                    'Погрешно корисничко име',
                    'Погрешна лозинка',
                    'Invalid username',
                    'Invalid password',
                    'Невалидни кредeнцијали',
                    'Login failed',
                ]

                for error_text in error_indicators:
                    if error_text.lower() in page_content.lower():
                        logger.error(f"✗ Login failed: found error '{error_text}'")
                        break

            if login_verified:
                self.is_logged_in = True
                self.stats['login_success'] = True

                logger.warning("=" * 70)
                logger.warning("✓ LOGIN SUCCESSFUL")
                logger.warning("=" * 70)

                # Save cookies for future use
                cookies = await page.context.cookies()
                self._save_cookies(cookies)

                await self._save_screenshot(page, 'login_success')
                await page.close()

                # Generate requests for categories
                for request in self._generate_category_requests():
                    yield request

            else:
                logger.error("=" * 70)
                logger.error("✗ LOGIN FAILED - Could not verify successful login")
                logger.error("=" * 70)
                await self._save_screenshot(page, 'login_failed')
                self.stats['errors'].append('Login failed - no success indicator found')
                await page.close()

        except Exception as e:
            logger.error(f"Login error: {e}")
            self.stats['errors'].append(f'Login error: {str(e)}')
            try:
                await self._save_screenshot(page, 'login_error')
                await page.close()
            except:
                pass

    async def _save_screenshot(self, page, name: str):
        """Save screenshot for debugging"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f'/tmp/nabavki_{name}_{timestamp}.png'
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.warning(f"Could not save screenshot: {e}")

    async def parse_authenticated_listing(self, response):
        """
        Parse listing page after authentication.
        Extracts tender links and follows them.
        """
        # Check if we've hit max_items limit
        if self.max_items and self.items_scraped >= self.max_items:
            logger.warning(f"Reached max_items limit ({self.max_items}), stopping")
            return

        page = response.meta.get('playwright_page')
        source_category = response.meta.get('category', 'active')

        logger.warning(f"Parsing authenticated listing for category: {source_category}")
        self.stats['categories_processed'].append(source_category)

        if page:
            try:
                # Wait for data table to load
                await page.wait_for_selector('table tbody tr, .tender-list, .notices-list', timeout=15000)
                await page.wait_for_timeout(3000)

                await self._save_screenshot(page, f'listing_{source_category}')

            except Exception as e:
                logger.warning(f"Timeout waiting for listing: {e}")

        tender_links = []

        # Extract tender links using Playwright
        if page:
            try:
                # Multiple selectors for tender detail links
                link_selectors = [
                    "a[href*='dossie']",
                    "a[href*='dossie-acpp']",
                    "a[href*='/tender/']",
                    "table tbody tr td a",
                    ".tender-item a",
                    ".notice-item a",
                ]

                for selector in link_selectors:
                    try:
                        link_elems = await page.query_selector_all(selector)
                        for elem in link_elems:
                            href = await elem.get_attribute('href')
                            if href and ('dossie' in href or '/tender/' in href):
                                tender_links.append(href)
                    except:
                        continue

            except Exception as e:
                logger.warning(f"Error extracting links: {e}")

        # Deduplicate links
        tender_links = list(set(tender_links))
        self.stats['tenders_found'] += len(tender_links)
        logger.warning(f"Found {len(tender_links)} tender links in {source_category}")

        # Close listing page
        if page:
            try:
                await page.close()
            except:
                pass

        # Apply max_items limit
        if self.max_items:
            remaining = self.max_items - self.items_scraped
            if remaining < len(tender_links):
                tender_links = tender_links[:remaining]
                logger.warning(f"Limited to {remaining} tenders due to max_items")

        # Follow each tender link
        for link in tender_links:
            # Construct absolute URL
            if link.startswith('#'):
                full_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx' + link
            elif link.startswith('/'):
                full_url = 'https://e-nabavki.gov.mk' + link
            elif not link.startswith('http'):
                full_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx' + link
            else:
                full_url = link

            logger.info(f"Following tender ({source_category}): {full_url}")

            yield scrapy.Request(
                url=full_url,
                callback=self.parse_tender_detail,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                        'timeout': 60000,
                    },
                    'source_category': source_category,
                },
                errback=self.errback_playwright,
                dont_filter=True
            )

    async def parse_tender_detail(self, response):
        """
        Parse tender detail page with comprehensive field extraction.
        Uses multiple selector strategies with fallbacks.
        """
        # Check max_items limit
        if self.max_items and self.items_scraped >= self.max_items:
            logger.warning(f"Reached max_items limit ({self.max_items}), skipping")
            return

        logger.info(f"Processing detail page: {response.url}")

        page = response.meta.get('playwright_page')
        source_category = response.meta.get('source_category', 'active')

        if page:
            try:
                # Wait for tender details to load
                await page.wait_for_selector('label.dosie-value, .tender-detail, .dossie-content', timeout=30000)
                await page.wait_for_timeout(2000)

                # Get rendered HTML
                html_content = await page.content()
                response = response.replace(body=html_content.encode('utf-8'))

                await self._save_screenshot(page, f'detail_{source_category}_{self.items_scraped}')

            except Exception as e:
                logger.error(f"Failed to wait for detail page: {e}")
                self.stats['errors'].append(f"Detail page timeout: {response.url}")
            finally:
                try:
                    await page.close()
                except:
                    pass

        # Extract tender data using comprehensive selectors
        tender = {
            'source_url': response.url,
            'scraped_at': datetime.utcnow().isoformat(),
            'language': 'mk',
            'source_category': source_category,
        }

        # =========================================================
        # Extract all tender fields with multiple selector fallbacks
        # =========================================================

        # Tender ID
        tender['tender_id'] = self._extract_tender_id(response)

        # Basic info
        tender['title'] = self._extract_field(response, 'title')
        tender['description'] = self._extract_field(response, 'description')
        tender['procuring_entity'] = self._extract_field(response, 'procuring_entity')
        tender['category'] = self._extract_field(response, 'category')
        tender['procedure_type'] = self._extract_field(response, 'procedure_type')
        tender['contracting_entity_category'] = self._extract_field(response, 'contracting_entity_category')
        tender['procurement_holder'] = self._extract_field(response, 'procurement_holder')
        tender['evaluation_method'] = self._extract_field(response, 'evaluation_method')

        # CPV Code (extract numeric code)
        tender['cpv_code'] = self._extract_cpv_code(response)

        # Dates
        tender['publication_date'] = self._extract_date(response, 'publication_date')
        tender['opening_date'] = self._extract_date(response, 'opening_date')
        tender['closing_date'] = self._extract_date(response, 'closing_date')
        tender['contract_signing_date'] = self._extract_date(response, 'contract_signing_date')
        tender['bureau_delivery_date'] = self._extract_date(response, 'bureau_delivery_date')

        # Currency values
        tender['estimated_value_mkd'] = self._extract_currency(response, 'estimated_value_mkd')
        tender['estimated_value_eur'] = self._extract_currency(response, 'estimated_value_eur')
        tender['actual_value_mkd'] = self._extract_currency(response, 'actual_value_mkd')
        tender['actual_value_eur'] = self._extract_currency(response, 'actual_value_eur')
        tender['security_deposit_mkd'] = self._extract_currency(response, 'security_deposit_mkd')
        tender['performance_guarantee_mkd'] = self._extract_currency(response, 'performance_guarantee_mkd')

        # Winner info
        tender['winner'] = self._extract_field(response, 'winner')

        # Contact info
        tender['contact_person'] = self._extract_field(response, 'contact_person')
        tender['contact_email'] = self._extract_field(response, 'contact_email')
        tender['contact_phone'] = self._extract_field(response, 'contact_phone')

        # Status detection
        tender['status'] = self._detect_status(tender, source_category)

        # Extract bidders
        bidders_list = self._extract_bidders(response, tender.get('tender_id', 'unknown'))
        tender['bidders_data'] = json.dumps(bidders_list, ensure_ascii=False) if bidders_list else None
        tender['num_bidders'] = len(bidders_list)

        # Extract lots
        lots_list = self._extract_lots(response, tender.get('tender_id', 'unknown'))
        tender['lots_data'] = json.dumps(lots_list, ensure_ascii=False) if lots_list else None
        tender['has_lots'] = len(lots_list) > 0
        tender['num_lots'] = len(lots_list)

        # Extract documents
        documents = self._extract_documents(response, tender.get('tender_id', 'unknown'))
        tender['documents_data'] = json.dumps(documents, ensure_ascii=False) if documents else None

        # Generate content hash for change detection
        tender['content_hash'] = self._generate_content_hash(tender)

        # Update statistics
        self.items_scraped += 1
        self.stats['tenders_scraped'] += 1
        self._update_field_fill_rates(tender)

        logger.warning(f"✓ Extracted tender {self.items_scraped}: {tender.get('tender_id')} - {tender.get('title', '')[:50]}")

        # Yield document items
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

        yield TenderItem(**tender)

    def _extract_tender_id(self, response: Response) -> Optional[str]:
        """Extract tender ID from page"""
        selectors = [
            # Label-based selectors (most reliable)
            'label[label-for="ANNOUNCEMENT NUMBER DOSIE"] + label.dosie-value::text',
            'label[label-for="PROCESS NUMBER FOR NOTIFICATION DOSSIE"] + label.dosie-value::text',
            # CSS selectors
            '.announcement-number::text',
            '.tender-id::text',
            # XPath
            '//label[contains(text(), "Број на оглас")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
            '//label[contains(text(), "Број на постапка")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
        ]

        for selector in selectors:
            try:
                if selector.startswith('//'):
                    value = response.xpath(selector).get()
                else:
                    value = response.css(selector).get()
                if value:
                    value = value.strip()
                    if value and '/' in value:
                        return value
            except:
                continue

        # Fallback: extract from URL
        url = response.url
        match = re.search(r'dossie[^/]*/([a-f0-9-]+)', url)
        if match:
            return match.group(1)

        return None

    def _extract_cpv_code(self, response: Response) -> Optional[str]:
        """Extract CPV code (numeric 8-digit code with optional -N suffix)"""
        selectors = [
            'label[label-for="CPV CODE DOSIE"] + label.dosie-value::text',
            'label:contains("CPV") + label.dosie-value::text',
            '//label[contains(text(), "CPV")]/following-sibling::label/text()',
            # Table format: look in tables after "Шифра" header
            'table td:first-child::text',
            'tr td::text',
        ]

        for selector in selectors:
            try:
                if selector.startswith('//'):
                    values = response.xpath(selector).getall()
                else:
                    values = response.css(selector).getall()

                for value in values:
                    if value:
                        value = value.strip()
                        # Extract CPV code with optional -N suffix (e.g., 64000000-6)
                        match = re.search(r'\b(\d{8}(?:-\d)?)\b', value)
                        if match:
                            return match.group(1)
                        # Extract 8-digit CPV code
                        match = re.search(r'\b(\d{8})\b', value)
                        if match:
                            return match.group(1)
            except:
                continue

        # Fallback: search full page text for CPV pattern
        try:
            page_text = response.text
            # CPV codes are 8 digits, optionally with -N suffix
            match = re.search(r'\b(\d{8}-\d)\b', page_text)
            if match:
                return match.group(1)
            match = re.search(r'\b(\d{8})\b(?!\d)', page_text)
            if match:
                # Verify it looks like a CPV code (not a phone number, etc)
                code = match.group(1)
                if code[0] in '012345678':  # CPV codes start with 0-8
                    return code
        except:
            pass

        return None

    def _extract_field(self, response: Response, field_name: str) -> Optional[str]:
        """Extract field using multiple selector strategies"""

        # Define selectors for each field
        FIELD_SELECTORS = {
            'title': [
                'label[label-for*="SUBJECT"] + label.dosie-value::text',
                'label:contains("Предмет на договорот") + label.dosie-value::text',
                'label:contains("Предмет") + label.dosie-value::text',
                '//label[contains(text(), "Предмет")]/following-sibling::label/text()',
                '.tender-title::text',
                'h1.title::text',
            ],
            'description': [
                'label[label-for*="DETAIL DESCRIPTION"] + label.dosie-value::text',
                'label:contains("Подетален опис") + label.dosie-value::text',
                '//label[contains(text(), "опис")]/following-sibling::label/text()',
            ],
            'procuring_entity': [
                'label[label-for="CONTRACTING INSTITUTION NAME DOSIE"] + label.dosie-value::text',
                'label[label-for="CONTRACTING AUTHORITY NAME DOSIE"] + label.dosie-value::text',
                'label:contains("Договорен орган") + label.dosie-value::text',
                'label:contains("Име на институција") + label.dosie-value::text',
                '//label[contains(text(), "Договорен орган")]/following-sibling::label/text()',
            ],
            'category': [
                'label:contains("Вид на договорот") + label.dosie-value::text',
                'label:contains("Категорија") + label.dosie-value::text',
                'label[label-for*="TYPE OF CONTRACT"] + label.dosie-value::text',
            ],
            'procedure_type': [
                'label[label-for="TYPE OF CALL:"] + label.dosie-value::text',
                'label:contains("Вид на постапка") + label.dosie-value::text',
                '//label[contains(text(), "Вид на постапка")]/following-sibling::label/text()',
            ],
            'contracting_entity_category': [
                'label:contains("Категорија на договорен орган") + label.dosie-value::text',
                'label[label-for*="CATEGORY OF CONTRACTING"] + label.dosie-value::text',
            ],
            'procurement_holder': [
                'label:contains("Носител на набавка") + label.dosie-value::text',
                'label[label-for*="NAME OF CONTACT OF PROCUREMENT"] + label.dosie-value::text',
            ],
            'evaluation_method': [
                'label:contains("Критериум за избор") + label.dosie-value::text',
                'label:contains("Метод на евалуација") + label.dosie-value::text',
                'label[label-for*="EVALUATION"] + label.dosie-value::text',
            ],
            'winner': [
                'label:contains("Добитник") + label.dosie-value::text',
                'label:contains("Избран понудувач") + label.dosie-value::text',
                'label:contains("Договорна страна") + label.dosie-value::text',
                'label:contains("Економски оператор") + label.dosie-value::text',
                '//label[contains(text(), "Добитник")]/following-sibling::label/text()',
            ],
            'contact_person': [
                'label:contains("Контакт лице") + label.dosie-value::text',
                'label[label-for*="CONTACT PERSON"] + label.dosie-value::text',
                '//label[contains(text(), "Контакт лице")]/following-sibling::label/text()',
            ],
            'contact_email': [
                'label:contains("Е-пошта") + label.dosie-value::text',
                'label:contains("E-mail") + label.dosie-value::text',
                'label:contains("Email") + label.dosie-value::text',
                'label[label-for*="EMAIL"] + label.dosie-value::text',
                '//label[contains(text(), "пошта")]/following-sibling::label/text()',
            ],
            'contact_phone': [
                'label:contains("Телефон") + label.dosie-value::text',
                'label[label-for*="PHONE"] + label.dosie-value::text',
                '//label[contains(text(), "Телефон")]/following-sibling::label/text()',
            ],
        }

        selectors = FIELD_SELECTORS.get(field_name, [])

        for selector in selectors:
            try:
                if selector.startswith('//'):
                    value = response.xpath(selector).get()
                else:
                    value = response.css(selector).get()
                if value:
                    value = value.strip()
                    if value and value not in ('N/A', 'n/a', '-', ''):
                        return value
            except:
                continue

        return None

    def _extract_date(self, response: Response, field_name: str) -> Optional[str]:
        """Extract and parse date fields"""
        DATE_SELECTORS = {
            'publication_date': [
                'label[label-for="ANNOUNCEMENT DATE DOSSIE"] + label.dosie-value::text',
                'label[label-for="PUBLICATION DATE DOSIE"] + label.dosie-value::text',
                'label:contains("Датум на објавување") + label.dosie-value::text',
            ],
            'opening_date': [
                'label[label-for="OPENING DATE DOSIE"] + label.dosie-value::text',
                'label:contains("Датум на отворање") + label.dosie-value::text',
            ],
            'closing_date': [
                'label[label-for="CLOSING DATE DOSIE"] + label.dosie-value::text',
                'label[label-for="SUBMISSION DEADLINE"] + label.dosie-value::text',
                'label:contains("Рок за поднесување") + label.dosie-value::text',
                'label:contains("Краен рок") + label.dosie-value::text',
                # V.2.1) format from authenticated pages
                '*:contains("најдоцна до")::text',
                '*:contains("доставаат најдоцна")::text',
                'div:contains("V.2.1")::text',
            ],
            'contract_signing_date': [
                'label[label-for="SIGNING DATE DOSIE"] + label.dosie-value::text',
                'label:contains("Датум на склучување") + label.dosie-value::text',
                'label:contains("Датум на потпишување") + label.dosie-value::text',
            ],
            'bureau_delivery_date': [
                'label[label-for="BUREAU DELIVERY DATE DOSIE"] + label.dosie-value::text',
                'label:contains("Датум на достава") + label.dosie-value::text',
                'label:contains("Доставено до биро") + label.dosie-value::text',
            ],
        }

        selectors = DATE_SELECTORS.get(field_name, [])

        for selector in selectors:
            try:
                date_str = response.css(selector).get()
                if date_str:
                    date_str = date_str.strip()
                    parsed = self._parse_date(date_str)
                    if parsed:
                        return parsed
            except:
                continue

        # Fallback: search for closing_date in page text using specific patterns
        if field_name == 'closing_date':
            try:
                page_text = response.text
                # Look for "најдоцна до: DD.MM.YYYY" pattern
                match = re.search(r'најдоцна до[:\s]+(\d{2}\.\d{2}\.\d{4})', page_text)
                if match:
                    return self._parse_date(match.group(1))
                # Look for "V.2.1)" section with date
                match = re.search(r'V\.2\.1\)[^:]*:?\s*(\d{2}\.\d{2}\.\d{4})', page_text)
                if match:
                    return self._parse_date(match.group(1))
                # Look for deadline pattern
                match = re.search(r'(рок за поднесување|deadline)[^:]*:?\s*(\d{2}\.\d{2}\.\d{4})', page_text, re.IGNORECASE)
                if match:
                    return self._parse_date(match.group(2))
            except:
                pass

        return None

    def _parse_date(self, date_string: str) -> Optional[str]:
        """Parse Macedonian date format to ISO format"""
        if not date_string:
            return None

        # Remove common suffixes
        date_string = re.sub(r'(година|год\.?|часот|во\s+\d{2}:\d{2})', '', date_string).strip()

        patterns = [
            (r'(\d{2})\.(\d{2})\.(\d{4})', '{2}-{1}-{0}'),  # DD.MM.YYYY
            (r'(\d{2})/(\d{2})/(\d{4})', '{2}-{1}-{0}'),   # DD/MM/YYYY
            (r'(\d{4})-(\d{2})-(\d{2})', '{0}-{1}-{2}'),   # YYYY-MM-DD
        ]

        for pattern, template in patterns:
            match = re.search(pattern, date_string)
            if match:
                groups = match.groups()
                return template.format(*groups)

        return None

    def _extract_currency(self, response: Response, field_name: str) -> Optional[Decimal]:
        """Extract currency values with European number format support"""
        CURRENCY_XPATHS = {
            'estimated_value_mkd': [
                '//label[contains(@label-for, "ESTIMATED VALUE")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Проценета вредност")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'estimated_value_eur': [
                '//label[contains(@label-for, "ESTIMATED VALUE")]/following-sibling::label[contains(@class, "dosie-value")][2]/text()',
            ],
            'actual_value_mkd': [
                '//label[contains(@label-for, "CONTRACT VALUE")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Вредност на договорот")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "ASSIGNED CONTRACT VALUE")]/following-sibling::label[1]/text()',
            ],
            'actual_value_eur': [
                '//label[contains(@label-for, "CONTRACT VALUE")]/following-sibling::label[contains(@class, "dosie-value")][2]/text()',
            ],
            'security_deposit_mkd': [
                '//label[contains(@label-for, "SECURITY DEPOSIT")]/following-sibling::label/text()',
                '//label[contains(text(), "Гаранција за учество")]/following-sibling::label/text()',
            ],
            'performance_guarantee_mkd': [
                '//label[contains(@label-for, "PERFORMANCE GUARANTEE")]/following-sibling::label/text()',
                '//label[contains(text(), "Гаранција за квалитет")]/following-sibling::label/text()',
            ],
        }

        xpaths = CURRENCY_XPATHS.get(field_name, [])

        for xpath in xpaths:
            try:
                values = response.xpath(xpath).getall()
                for value_str in values:
                    if value_str:
                        value_str = value_str.strip()
                        # Skip non-numeric values
                        if value_str in ('Не', 'Да', 'No', 'Yes', '-', 'N/A'):
                            continue
                        parsed = self._parse_currency(value_str)
                        if parsed:
                            return parsed
            except:
                continue

        return None

    def _parse_currency(self, value_string: str) -> Optional[Decimal]:
        """Parse European currency format (1.234.567,89)"""
        if not value_string:
            return None

        # Remove currency symbols and non-numeric chars except . and ,
        number_str = re.sub(r'[^\d,\.]', '', value_string)
        if not number_str:
            return None

        try:
            # European format: 1.234.567,89 -> 1234567.89
            if '.' in number_str and ',' in number_str:
                number_str = number_str.replace('.', '').replace(',', '.')
            elif ',' in number_str:
                # Single comma could be decimal separator
                if number_str.count(',') == 1 and len(number_str.split(',')[1]) <= 2:
                    number_str = number_str.replace(',', '.')
                else:
                    number_str = number_str.replace(',', '')

            return Decimal(number_str)
        except:
            return None

    def _extract_bidders(self, response: Response, tender_id: str) -> List[Dict]:
        """Extract bidder information from tender page"""
        bidders = []

        try:
            # Look for bidder tables
            table_xpaths = [
                '//table[.//th[contains(text(), "Понудувач")]]',
                '//table[.//th[contains(text(), "Учесник")]]',
                '//table[.//th[contains(text(), "Економски оператор")]]',
                '//div[contains(@class, "bidders")]//table',
            ]

            bidder_table = None
            for xpath in table_xpaths:
                table = response.xpath(xpath)
                if table:
                    bidder_table = table
                    break

            if bidder_table:
                rows = bidder_table.css('tbody tr')
                for idx, row in enumerate(rows, start=1):
                    cells = row.css('td')
                    if len(cells) >= 2:
                        bidder_data = {}

                        # Company name (usually first cell)
                        company_name = cells[0].css('::text').get()
                        if company_name:
                            bidder_data['company_name'] = company_name.strip()

                        # Look for bid amount
                        for cell in cells:
                            cell_text = cell.css('::text').get()
                            if cell_text:
                                amount = self._parse_currency(cell_text)
                                if amount:
                                    bidder_data['bid_amount_mkd'] = float(amount)
                                    break

                        # Check if winner
                        row_html = row.get()
                        winner_indicators = ['победник', 'добитник', 'избран', 'winner', 'selected']
                        bidder_data['is_winner'] = any(ind in row_html.lower() for ind in winner_indicators)
                        bidder_data['rank'] = idx
                        bidder_data['disqualified'] = 'дисквалиф' in row_html.lower()

                        if bidder_data.get('company_name'):
                            bidders.append(bidder_data)

            # If no table, get winner from field
            if not bidders:
                winner_name = self._extract_field(response, 'winner')
                actual_value = self._extract_currency(response, 'actual_value_mkd')
                if winner_name:
                    bidders.append({
                        'company_name': winner_name,
                        'bid_amount_mkd': float(actual_value) if actual_value else None,
                        'is_winner': True,
                        'rank': 1,
                        'disqualified': False
                    })

        except Exception as e:
            logger.warning(f"Error extracting bidders: {e}")

        return bidders

    def _extract_lots(self, response: Response, tender_id: str) -> List[Dict]:
        """Extract lot information"""
        lots = []

        try:
            # Look for lot tables
            lot_xpaths = [
                '//table[.//th[contains(text(), "Лот")]]',
                '//div[contains(@class, "lots")]//table',
                '//table[.//th[contains(text(), "Дел")]]',
            ]

            lot_table = None
            for xpath in lot_xpaths:
                table = response.xpath(xpath)
                if table:
                    lot_table = table
                    break

            if lot_table:
                rows = lot_table.css('tbody tr')
                for idx, row in enumerate(rows, start=1):
                    cells = row.css('td')
                    if len(cells) >= 2:
                        lot_data = {
                            'lot_number': str(idx),
                            'lot_title': cells[0].css('::text').get('').strip() if cells else '',
                        }

                        # Extract additional lot info
                        for cell in cells:
                            cell_text = cell.css('::text').get('')
                            # CPV code
                            cpv_match = re.search(r'\b(\d{8})\b', cell_text)
                            if cpv_match:
                                lot_data['cpv_code'] = cpv_match.group(1)
                            # Value
                            amount = self._parse_currency(cell_text)
                            if amount and 'estimated_value_mkd' not in lot_data:
                                lot_data['estimated_value_mkd'] = float(amount)

                        lots.append(lot_data)

        except Exception as e:
            logger.warning(f"Error extracting lots: {e}")

        return lots

    def _extract_documents(self, response: Response, tender_id: str) -> List[Dict]:
        """Extract document links"""
        documents = []

        doc_selectors = [
            'a[href*="Download"]::attr(href)',
            'a[href*=".pdf"]::attr(href)',
            'a[href*=".doc"]::attr(href)',
            'a[href*=".xls"]::attr(href)',
            'a[href*="File"]::attr(href)',
            'a[href*="Attachment"]::attr(href)',
        ]

        seen_urls = set()

        for selector in doc_selectors:
            links = response.css(selector).getall()
            for link in links:
                if link and link not in seen_urls:
                    seen_urls.add(link)

                    if not link.startswith('http'):
                        link = 'https://e-nabavki.gov.mk' + link

                    # Extract filename
                    filename = link.split('/')[-1] if '/' in link else 'document'
                    if '?' in filename:
                        filename = filename.split('?')[0]

                    # Classify document
                    doc_category = self._classify_document(filename, link)

                    documents.append({
                        'url': link,
                        'tender_id': tender_id,
                        'doc_category': doc_category,
                        'upload_date': None,
                        'file_name': filename,
                        'doc_type': 'document',
                    })

        return documents

    def _classify_document(self, filename: str, url: str) -> str:
        """Classify document by type based on filename"""
        filename_lower = filename.lower()
        url_lower = url.lower()

        classifications = {
            'tender_document': ['тендер', 'набавка', 'јавен', 'tender', 'procurement'],
            'technical_spec': ['технич', 'спецификација', 'spec', 'technical'],
            'amendment': ['измен', 'допол', 'amend', 'correction'],
            'award': ['одлука', 'резултат', 'award', 'decision', 'result'],
            'contract': ['договор', 'contract', 'потпишан'],
            'clarification': ['појаснување', 'clarification', 'question'],
        }

        combined = filename_lower + ' ' + url_lower

        for category, keywords in classifications.items():
            if any(kw in combined for kw in keywords):
                return category

        return 'other'

    def _detect_status(self, tender: Dict, source_category: str) -> str:
        """Detect tender status from various signals"""
        # Category-based status
        if source_category in ('awarded', 'contracts', 'tender_winners', 'historical'):
            return 'awarded'
        if source_category == 'cancelled':
            return 'cancelled'

        # Winner presence
        if tender.get('winner'):
            return 'awarded'

        # Contract value presence
        if tender.get('actual_value_mkd'):
            return 'awarded'

        # Default to open for active
        if source_category == 'active':
            return 'open'

        return 'published'

    def _generate_content_hash(self, tender: Dict) -> str:
        """Generate hash of tender content for change detection"""
        # Use key fields for hash
        content = f"{tender.get('tender_id', '')}{tender.get('title', '')}{tender.get('closing_date', '')}{tender.get('estimated_value_mkd', '')}{tender.get('winner', '')}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

    def _update_field_fill_rates(self, tender: Dict):
        """Update field fill rate statistics"""
        key_fields = [
            'tender_id', 'title', 'closing_date', 'estimated_value_mkd',
            'cpv_code', 'contact_person', 'contact_email', 'contact_phone',
            'procuring_entity', 'procedure_type', 'evaluation_method'
        ]

        for field in key_fields:
            if field not in self.stats['field_fill_rates']:
                self.stats['field_fill_rates'][field] = {'filled': 0, 'total': 0}

            self.stats['field_fill_rates'][field]['total'] += 1
            if tender.get(field):
                self.stats['field_fill_rates'][field]['filled'] += 1

    async def errback_playwright(self, failure):
        """Handle Playwright errors"""
        logger.error(f"Playwright request failed: {failure.request.url}")
        logger.error(f"Error: {failure.value}")
        self.stats['errors'].append(str(failure.value))

    def close(self, reason):
        """Called when spider closes - generate health report"""
        logger.warning("=" * 80)
        logger.warning("AUTHENTICATED SCRAPING COMPLETE - STATISTICS")
        logger.warning("=" * 80)
        logger.warning(f"Category: {self.category}")
        logger.warning(f"Max items: {self.max_items or 'unlimited'}")
        logger.warning(f"Login success: {self.stats['login_success']}")
        logger.warning(f"Tenders found: {self.stats['tenders_found']}")
        logger.warning(f"Tenders scraped: {self.stats['tenders_scraped']}")
        logger.warning(f"Tenders skipped: {self.stats['tenders_skipped']}")
        logger.warning(f"Errors: {len(self.stats['errors'])}")

        # Print field fill rates
        logger.warning("-" * 40)
        logger.warning("FIELD FILL RATES:")
        for field, rates in self.stats['field_fill_rates'].items():
            if rates['total'] > 0:
                pct = (rates['filled'] / rates['total']) * 100
                logger.warning(f"  {field}: {pct:.1f}% ({rates['filled']}/{rates['total']})")

        # Print errors
        if self.stats['errors']:
            logger.warning("-" * 40)
            logger.warning("ERRORS:")
            for err in self.stats['errors'][:10]:
                logger.warning(f"  - {err}")

        logger.warning("=" * 80)

        # Save health report to JSON
        self._save_health_report()

    def _save_health_report(self):
        """Save detailed health report to JSON file"""
        try:
            health_data = {
                'spider': 'nabavki_auth',
                'run_time': datetime.utcnow().isoformat(),
                'category': self.category,
                'max_items': self.max_items,
                'login_success': self.stats['login_success'],
                'login_time': self.stats.get('login_time'),
                'cookie_expiry': self.stats.get('cookie_expiry'),
                'tenders_found': self.stats['tenders_found'],
                'tenders_scraped': self.stats['tenders_scraped'],
                'tenders_skipped': self.stats['tenders_skipped'],
                'success_rate': (self.stats['tenders_scraped'] / self.stats['tenders_found'] * 100) if self.stats['tenders_found'] > 0 else 0,
                'field_fill_rates': {
                    field: (rates['filled'] / rates['total'] * 100) if rates['total'] > 0 else 0
                    for field, rates in self.stats['field_fill_rates'].items()
                },
                'errors_count': len(self.stats['errors']),
                'errors': self.stats['errors'][:20],
                'categories_processed': self.stats['categories_processed'],
            }

            health_file = Path('/tmp/nabavki_auth_health.json')
            with open(health_file, 'w') as f:
                json.dump(health_data, f, indent=2, ensure_ascii=False)

            logger.warning(f"Health report saved to: {health_file}")

        except Exception as e:
            logger.error(f"Could not save health report: {e}")
