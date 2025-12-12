"""
E-nabavki.gov.mk Authenticated Spider - Enhanced for Lot-Level Data
Uses Playwright for JavaScript rendering and authentication

ENHANCED VERSION:
- Extracts ALL bidders (not just winners) from VendorOfferers
- Extracts lot-level award data from NotificationForAcppTable
- Captures highest/lowest bid values
- Stores raw JSON for debugging/fallback

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
from scraper.items import TenderItem, DocumentItem, LotAwardItem

logger = logging.getLogger(__name__)

# Cookie storage path
COOKIE_FILE = Path('/tmp/nabavki_auth_cookies.json')
SESSION_FILE = Path('/tmp/nabavki_auth_session.json')


class NabavkiAuthSpider(scrapy.Spider):
    """
    Authenticated spider for e-nabavki.gov.mk - Enhanced for lot-level data

    Features:
    - Persistent cookie storage for session reuse
    - max_items parameter for controlled testing
    - Enhanced extraction: ALL bidders, lot awards, bid ranges
    - Raw JSON storage for debugging
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

    LOGIN_URL = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/home'

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,  # Increased to be gentler on slow site
        "CONCURRENT_REQUESTS": 1,  # Single request at a time for stability
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1,
        "PLAYWRIGHT_MAX_CONTEXTS": 1,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        "DUPEFILTER_CLASS": "scrapy.dupefilters.BaseDupeFilter",
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        # Retry settings to handle timeouts
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,  # More retries for slow site
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        # Longer timeout for slow e-nabavki site
        "DOWNLOAD_TIMEOUT": 90,
    }

    def __init__(self, category='active', username=None, password=None, max_items=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category.lower()

        self.username = username or os.environ.get('NABAVKI_USERNAME')
        self.password = password or os.environ.get('NABAVKI_PASSWORD')

        if not self.username or not self.password:
            raise ValueError(
                "Credentials required! Set NABAVKI_USERNAME and NABAVKI_PASSWORD environment variables "
                "or pass -a username=xxx -a password=xxx to the spider."
            )

        self.max_items = int(max_items) if max_items else None
        self.items_scraped = 0

        self.is_logged_in = False
        self.cookies = None
        self.login_time = None
        self.cookie_expiry = None

        self.stats = {
            'login_attempts': 0,
            'login_success': False,
            'login_time': None,
            'cookie_expiry': None,
            'tenders_found': 0,
            'tenders_scraped': 0,
            'tenders_skipped': 0,
            'lot_awards_extracted': 0,
            'all_bidders_extracted': 0,
            'field_fill_rates': {},
            'errors': [],
            'categories_processed': [],
        }

        logger.warning("=" * 70)
        logger.warning("ENHANCED AUTHENTICATED SCRAPER - LOT-LEVEL DATA")
        logger.warning("=" * 70)
        logger.warning(f"Category: {self.category}")
        logger.warning(f"Username: {self.username}")
        logger.warning(f"Max items: {self.max_items or 'unlimited'}")
        logger.warning("=" * 70)

    def _load_saved_cookies(self) -> bool:
        """Load saved cookies from file if they exist and are not expired."""
        try:
            if COOKIE_FILE.exists() and SESSION_FILE.exists():
                with open(SESSION_FILE, 'r') as f:
                    session_data = json.load(f)

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
                    return True
        except Exception as e:
            logger.warning(f"Could not load saved cookies: {e}")

        return False

    def _save_cookies(self, cookies: List[Dict]) -> None:
        """Save cookies to file for reuse."""
        try:
            self.login_time = datetime.utcnow()
            self.cookie_expiry = self.login_time + timedelta(hours=4)

            with open(COOKIE_FILE, 'w') as f:
                json.dump(cookies, f, indent=2)

            session_data = {
                'login_time': self.login_time.isoformat(),
                'username': self.username,
                'cookie_count': len(cookies),
            }
            with open(SESSION_FILE, 'w') as f:
                json.dump(session_data, f, indent=2)

            logger.warning(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")
        except Exception as e:
            logger.error(f"Could not save cookies: {e}")

    def start_requests(self):
        """Start with login page or use saved cookies"""
        if self._load_saved_cookies():
            self.is_logged_in = True
            self.stats['login_success'] = True
            yield from self._generate_category_requests()
        else:
            yield scrapy.Request(
                self.LOGIN_URL,
                callback=self.perform_login,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'domcontentloaded',
                        'timeout': 90000,
                    },
                },
                errback=self.errback_playwright,
                dont_filter=True
            )

    def _generate_category_requests(self):
        """Generate requests for target categories after login"""
        if self.category == 'all':
            for cat, url in self.CATEGORY_URLS.items():
                yield scrapy.Request(
                    url,
                    callback=self.parse_authenticated_listing,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'domcontentloaded',
                            'timeout': 90000,
                        },
                        'category': cat,
                    },
                    errback=self.errback_playwright,
                    dont_filter=True
                )
        else:
            url = self.CATEGORY_URLS.get(self.category)
            if url:
                yield scrapy.Request(
                    url,
                    callback=self.parse_authenticated_listing,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'domcontentloaded',
                            'timeout': 90000,
                        },
                        'category': self.category,
                    },
                    errback=self.errback_playwright,
                    dont_filter=True
                )

    async def perform_login(self, response):
        """Perform login using Playwright"""
        page = response.meta.get('playwright_page')
        self.stats['login_attempts'] += 1

        if not page:
            logger.error("No Playwright page available for login")
            return

        try:
            logger.warning("Attempting login to e-nabavki.gov.mk...")
            await page.wait_for_timeout(3000)

            # Fill username
            username_selectors = [
                'input[placeholder*="Корисничко"]',
                'input[ng-model*="userName"]',
                'input[type="text"]',
            ]

            for selector in username_selectors:
                try:
                    field = await page.query_selector(selector)
                    if field and await field.is_visible():
                        await field.fill(self.username)
                        logger.info(f"Filled username with: {selector}")
                        break
                except:
                    continue

            # Fill password
            password_field = await page.query_selector('input[type="password"]')
            if password_field:
                await password_field.fill(self.password)

            await page.wait_for_timeout(500)

            # Submit
            submit_selectors = ['button:has-text("Влез")', 'button[type="submit"]']
            for selector in submit_selectors:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        break
                except:
                    continue

            await page.wait_for_timeout(5000)

            # Check login success
            page_content = await page.content()
            if any(ind in page_content.lower() for ind in ['одјава', 'logout', self.username.lower()]):
                self.is_logged_in = True
                self.stats['login_success'] = True
                logger.warning("LOGIN SUCCESSFUL")

                cookies = await page.context.cookies()
                self._save_cookies(cookies)
                await page.close()

                for request in self._generate_category_requests():
                    yield request
            else:
                logger.error("LOGIN FAILED")
                await page.close()

        except Exception as e:
            logger.error(f"Login error: {e}")
            try:
                await page.close()
            except:
                pass

    async def parse_authenticated_listing(self, response):
        """Parse listing page and extract tender links from ALL pages"""
        if self.max_items and self.items_scraped >= self.max_items:
            return

        page = response.meta.get('playwright_page')
        source_category = response.meta.get('category', 'active')

        logger.warning(f"Parsing listing for: {source_category}")
        self.stats['categories_processed'].append(source_category)

        if page:
            try:
                await page.wait_for_selector('table tbody tr', timeout=15000)
                await page.wait_for_timeout(3000)
            except:
                pass

        tender_links = []
        current_page = 1
        max_pages = getattr(self, 'max_pages', 100)  # Limit pages to prevent infinite loops

        # PAGINATION LOOP: Collect ALL tender links from ALL pages in single session
        while page and current_page <= max_pages:
            # Extract tender links from current page
            page_links_count = 0
            try:
                link_selectors = ["a[href*='dossie']", "a[href*='/tender/']"]
                for selector in link_selectors:
                    try:
                        elems = await page.query_selector_all(selector)
                        for elem in elems:
                            href = await elem.get_attribute('href')
                            if href and 'dossie' in href and href not in tender_links:
                                tender_links.append(href)
                                page_links_count += 1
                    except:
                        continue
            except:
                pass

            logger.warning(f"Found {page_links_count} new tenders on page {current_page} of {source_category} (total: {len(tender_links)})")
            self.stats['tenders_found'] = len(tender_links)

            # If we found 0 new tenders on a page after page 1, we might be stuck
            if current_page > 1 and page_links_count == 0:
                logger.info(f"No new tenders found on page {current_page}, stopping pagination")
                break

            # Check if we've reached max_items
            if self.max_items and len(tender_links) >= self.max_items:
                logger.info(f"Reached max_items limit ({self.max_items}), stopping pagination")
                break

            # Try to click "Next" button to go to next page
            next_button_selectors = [
                'a:has-text("Следна")',  # "Next" in Macedonian
                'a:has-text(">")',
                'a:has-text("»")',
                '.pagination li:last-child a',
                'button[ng-click*="next"]',
                'a[ng-click*="next"]',
                '.next-page',
            ]

            next_clicked = False
            for selector in next_button_selectors:
                try:
                    next_btn = await page.query_selector(selector)
                    if next_btn and await next_btn.is_visible():
                        # Check if button is enabled (not disabled class)
                        is_disabled = await next_btn.get_attribute('class')
                        if is_disabled and 'disabled' in str(is_disabled).lower():
                            continue

                        # Check parent li for disabled state (Bootstrap pagination)
                        parent = await next_btn.evaluate_handle('el => el.parentElement')
                        if parent:
                            parent_class = await parent.get_property('className')
                            parent_class_str = await parent_class.json_value()
                            if 'disabled' in str(parent_class_str).lower():
                                continue

                        await next_btn.click()
                        logger.info(f"Clicked next page button using selector: {selector}")

                        # Wait for Angular SPA to reload content
                        # Method 1: Wait for network to become idle
                        try:
                            await page.wait_for_load_state('networkidle', timeout=30000)
                        except:
                            pass  # Continue anyway

                        # Method 2: Wait a fixed time for Angular to render
                        await page.wait_for_timeout(5000)

                        # Method 3: Try waiting for table, but don't fail if it doesn't appear
                        try:
                            await page.wait_for_selector('table tbody tr', timeout=10000)
                        except:
                            logger.warning(f"Table selector not found after clicking next, continuing anyway...")

                        # Give Angular a bit more time to stabilize
                        await page.wait_for_timeout(2000)

                        next_clicked = True
                        break
                except Exception as e:
                    logger.debug(f"Next button selector {selector} failed: {e}")
                    continue

            if next_clicked:
                current_page += 1
            else:
                logger.info(f"No more pages available for {source_category} (stopped at page {current_page})")
                break

        if page:
            try:
                await page.close()
            except:
                pass

        tender_links = list(set(tender_links))
        logger.warning(f"Total unique tenders collected for {source_category}: {len(tender_links)} from {current_page} pages")

        if self.max_items:
            remaining = self.max_items - self.items_scraped
            tender_links = tender_links[:remaining]

        for link in tender_links:
            if link.startswith('#'):
                full_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx' + link
            elif link.startswith('/'):
                full_url = 'https://e-nabavki.gov.mk' + link
            elif not link.startswith('http'):
                full_url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx' + link
            else:
                full_url = link

            yield scrapy.Request(
                url=full_url,
                callback=self.parse_tender_detail,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'domcontentloaded',
                        'timeout': 90000,
                    },
                    'source_category': source_category,
                },
                errback=self.errback_playwright,
                dont_filter=True
            )

    async def parse_tender_detail(self, response):
        """Parse tender detail page with enhanced lot-level extraction"""
        if self.max_items and self.items_scraped >= self.max_items:
            return

        page = response.meta.get('playwright_page')
        source_category = response.meta.get('source_category', 'active')

        raw_offers_html = ""
        if page:
            try:
                await page.wait_for_selector('label.dosie-value', timeout=30000)
                await page.wait_for_timeout(2000)

                # Try to click on "Понуди" tab to load offers data
                try:
                    offers_tab = await page.query_selector('a:has-text("Понуди"), li:has-text("Понуди")')
                    if offers_tab:
                        await offers_tab.click()
                        await page.wait_for_timeout(2000)
                        logger.info("Clicked on Offers tab")
                except:
                    pass

                html_content = await page.content()
                response = response.replace(body=html_content.encode('utf-8'))

                # Extract raw offers section HTML for debugging
                try:
                    offers_section = await page.query_selector('[ng-if*="VendorOfferers"], .offers-section, #offers')
                    if offers_section:
                        raw_offers_html = await offers_section.inner_html()
                except:
                    pass

                # ENHANCED: Extract bidders from Angular scope BEFORE closing page
                playwright_bidders = []
                try:
                    js_code = """
                        (function() {
                            try {
                                var scope = angular.element(document.body).scope();
                                if (!scope) return [];

                                var vendors = null;

                                // Path 1: model.Information.VendorOfferers (contract detail)
                                if (scope.model && scope.model.Information && scope.model.Information.VendorOfferers) {
                                    vendors = scope.model.Information.VendorOfferers;
                                }
                                // Path 2: Dossie.VendorOfferers (tender detail)
                                else if (scope.Dossie && scope.Dossie.VendorOfferers) {
                                    vendors = scope.Dossie.VendorOfferers;
                                }
                                // Path 3: Check child scopes
                                else {
                                    var elems = document.querySelectorAll('[ng-repeat*="VendorOfferers"]');
                                    for (var i = 0; i < elems.length; i++) {
                                        var s = angular.element(elems[i]).scope();
                                        if (s && s.$parent) {
                                            var p = s.$parent;
                                            if (p.model && p.model.Information && p.model.Information.VendorOfferers) {
                                                vendors = p.model.Information.VendorOfferers;
                                                break;
                                            }
                                        }
                                    }
                                }

                                if (!vendors || !vendors.length) return [];

                                return vendors.map(function(v, idx) {
                                    var name = v.Vendor ? v.Vendor.Name : (v.Name || null);
                                    var edb = v.Vendor ? v.Vendor.EDB : (v.EDB || null);
                                    var amount = v.OfferValue || v.BidAmount || v.Value || null;

                                    return {
                                        rank: idx + 1,
                                        company_name: name,
                                        tax_id: edb,
                                        bid_amount_mkd: amount,
                                        is_winner: v.IsWinner || false,
                                        disqualified: v.IsDisqualified || false
                                    };
                                });
                            } catch(e) {}
                            return [];
                        })()
                    """
                    angular_bidders = await page.evaluate(js_code)
                    playwright_bidders = [b for b in (angular_bidders or []) if b.get("company_name")]
                    if playwright_bidders:
                        logger.info(f"Extracted {len(playwright_bidders)} bidders from Angular scope")
                except Exception as e:
                    logger.debug(f"Angular bidder extraction: {e}")

                # Store in meta for later use
                response.meta["playwright_bidders"] = playwright_bidders

                # FALLBACK: If Angular scope extraction failed, extract from rendered HTML
                if not playwright_bidders:
                    try:
                        html_bidders = []
                        # Get all VendorOfferers table rows from rendered HTML
                        rows = await page.query_selector_all('tbody.ng-scope tr, tr.ng-scope')
                        for idx, row in enumerate(rows):
                            cells = await row.query_selector_all('td')
                            if cells and len(cells) >= 1:
                                text = await cells[0].inner_text() if cells else ""
                                if text and text.strip() and len(text.strip()) > 3:
                                    html_bidders.append({
                                        "rank": idx + 1,
                                        "company_name": text.strip(),
                                        "is_winner": False,
                                        "disqualified": False
                                    })
                        if html_bidders:
                            response.meta["playwright_bidders"] = html_bidders
                            logger.info(f"Extracted {len(html_bidders)} bidders from rendered HTML")
                    except Exception as e:
                        logger.debug(f"HTML bidder extraction: {e}")

                # Capture the entire page HTML for AI processing
                try:
                    full_html = await page.content()
                    response.meta["raw_page_html"] = full_html[:100000] if full_html else None
                except:
                    pass

            except Exception as e:
                logger.error(f"Detail page load error: {e}")
            finally:
                try:
                    await page.close()
                except:
                    pass

        # Build tender data
        tender = {
            'source_url': response.url,
            'scraped_at': datetime.utcnow().isoformat(),
            'language': 'mk',
            'source_category': source_category,
        }

        # Extract basic fields
        tender['tender_id'] = self._extract_tender_id(response)
        tender['title'] = self._extract_field(response, 'title')
        tender['description'] = self._extract_field(response, 'description')
        tender['procuring_entity'] = self._extract_field(response, 'procuring_entity')
        tender['category'] = self._extract_field(response, 'category')
        tender['procedure_type'] = self._extract_field(response, 'procedure_type')
        tender['cpv_code'] = self._extract_cpv_code(response)

        # Dates
        tender['publication_date'] = self._extract_date(response, 'publication_date')
        tender['opening_date'] = self._extract_date(response, 'opening_date')
        tender['closing_date'] = self._extract_date(response, 'closing_date')
        tender['contract_signing_date'] = self._extract_date(response, 'contract_signing_date')

        # Values
        tender['estimated_value_mkd'] = self._extract_currency(response, 'estimated_value_mkd')
        tender['actual_value_mkd'] = self._extract_currency(response, 'actual_value_mkd')

        # Winner (primary)
        tender['winner'] = self._extract_field(response, 'winner')

        # Contact info
        tender['contact_person'] = self._extract_field(response, 'contact_person')
        tender['contact_email'] = self._extract_field(response, 'contact_email')
        tender['contact_phone'] = self._extract_field(response, 'contact_phone')

        # Status
        tender['status'] = self._detect_status(tender, source_category)

        # ===========================================
        # ENHANCED: Extract ALL bidders
        # ===========================================
        # Use Playwright-extracted bidders (from Angular scope) if available
        all_bidders = response.meta.get('playwright_bidders', [])
        if not all_bidders:
            # Fallback to XPath extraction
            all_bidders = self._extract_all_bidders(response, tender.get('tender_id', 'unknown'))
        logger.info(f"Total bidders found: {len(all_bidders)} for tender {tender.get('tender_id')}")
        tender['bidders_data'] = json.dumps(all_bidders, ensure_ascii=False) if all_bidders else None
        tender['all_bidders_json'] = json.dumps(all_bidders, ensure_ascii=False) if all_bidders else None
        tender['num_bidders'] = len(all_bidders)
        self.stats['all_bidders_extracted'] += len(all_bidders)

        # ===========================================
        # ENHANCED: Extract lot-level awards
        # ===========================================
        lot_awards = self._extract_lot_awards(response, tender.get('tender_id', 'unknown'))
        tender['lot_awards_json'] = json.dumps(lot_awards, ensure_ascii=False) if lot_awards else None
        self.stats['lot_awards_extracted'] += len(lot_awards)

        # ===========================================
        # ENHANCED: Extract bid range
        # ===========================================
        bid_range = self._extract_bid_range(response)
        tender['highest_bid'] = float(bid_range.get('highest_bid_mkd')) if bid_range.get('highest_bid_mkd') else None
        tender['lowest_bid'] = float(bid_range.get('lowest_bid_mkd')) if bid_range.get('lowest_bid_mkd') else None

        # Store raw HTML for debugging
        tender['raw_offers_html'] = raw_offers_html[:50000] if raw_offers_html else None  # Limit size

        # Extract lots
        lots_list = self._extract_lots(response, tender.get('tender_id', 'unknown'))
        tender['lots_data'] = json.dumps(lots_list, ensure_ascii=False) if lots_list else None
        tender['has_lots'] = len(lots_list) > 0
        tender['num_lots'] = len(lots_list)

        # Extract documents
        documents = self._extract_documents(response, tender.get('tender_id', 'unknown'))
        tender['documents_data'] = json.dumps(documents, ensure_ascii=False) if documents else None

        # Content hash
        tender['content_hash'] = self._generate_content_hash(tender)

        # Update stats
        self.items_scraped += 1
        self.stats['tenders_scraped'] += 1

        logger.warning(f"Extracted tender {self.items_scraped}: {tender.get('tender_id')} - Bidders: {len(all_bidders)}, Awards: {len(lot_awards)}")

        # Yield document items
        for doc in documents:
            # Skip ohridskabanka.mk documents (external bank guarantees - not relevant)
            doc_url = doc.get('url', '')
            if 'ohridskabanka' in doc_url.lower():
                logger.info(f"Skipping ohridskabanka.mk document: {doc_url}")
                continue

            yield DocumentItem(
                tender_id=doc.get('tender_id'),
                file_url=doc.get('url'),
                file_name=doc.get('file_name'),
                doc_category=doc.get('doc_category'),
                doc_type='document',
                extraction_status='pending'
            )

        # Yield lot award items
        for award in lot_awards:
            yield LotAwardItem(
                tender_id=tender.get('tender_id'),
                award_number=award.get('award_number'),
                lot_numbers=award.get('lot_numbers'),
                winner_name=award.get('winner_name'),
                winner_tax_id=award.get('winner_tax_id'),
                contract_value_mkd=award.get('contract_value_mkd'),
                contract_date=award.get('contract_date'),
                num_lots=award.get('num_lots'),
                raw_data=json.dumps(award, ensure_ascii=False),
                source_url=response.url
            )

        yield TenderItem(**tender)

    def _extract_all_bidders(self, response: Response, tender_id: str) -> List[Dict]:
        """
        Extract ALL bidders from VendorOfferers Angular repeat.
        This captures all participating bidders, not just winners.
        """
        bidders = []

        try:
            # Method 1: Look for bidder table
            bidder_table_xpaths = [
                '//table[.//th[contains(text(), "Понудувач")]]',
                '//table[.//th[contains(text(), "ЕДБ")]]',
                '//table[.//th[contains(text(), "Износ на понуда")]]',
                '//div[contains(@ng-if, "VendorOfferers")]//table',
            ]

            bidder_table = None
            for xpath in bidder_table_xpaths:
                table = response.xpath(xpath)
                if table:
                    bidder_table = table
                    break

            if bidder_table:
                rows = bidder_table.xpath('.//tbody/tr | .//tr[td]')
                for idx, row in enumerate(rows, start=1):
                    cells = row.xpath('.//td')
                    if len(cells) >= 2:
                        bidder_data = {'rank': idx}

                        # Company name
                        for i in range(min(3, len(cells))):
                            text = cells[i].xpath('.//text()').get()
                            if text:
                                text = text.strip()
                                # Company names are longer text, not just numbers
                                if len(text) > 3 and not text.replace(',', '').replace('.', '').replace(' ', '').isdigit():
                                    if 'company_name' not in bidder_data:
                                        bidder_data['company_name'] = text
                                    break

                        # Tax ID (EDB) - usually numeric
                        for i in range(min(4, len(cells))):
                            text = cells[i].xpath('.//text()').get()
                            if text:
                                text = text.strip()
                                if re.match(r'^[A-Z0-9]{7,15}$', text):
                                    bidder_data['tax_id'] = text
                                    break

                        # Bid amount
                        for cell in cells:
                            text = cell.xpath('.//text()').get()
                            if text:
                                amount = self._parse_currency(text)
                                if amount and amount > 100:
                                    bidder_data['bid_amount_mkd'] = float(amount)
                                    break

                        # Check winner status
                        row_html = row.get() or ''
                        bidder_data['is_winner'] = any(ind in row_html.lower() for ind in ['победник', 'добитник', 'избран', 'winner'])
                        bidder_data['disqualified'] = 'дисквалиф' in row_html.lower()

                        if bidder_data.get('company_name'):
                            bidders.append(bidder_data)

            # Fallback to winner-only
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

    def _extract_lot_awards(self, response: Response, tender_id: str) -> List[Dict]:
        """
        Extract lot-level award notifications from NotificationForAcppTable.
        """
        lot_awards = []

        try:
            # Find award table
            award_table_xpaths = [
                '//div[contains(@ng-if, "NotificationForAcpp")]//table',
                '//table[.//th[contains(text(), "Дел") or contains(text(), "Лот")]]',
                '//table[.//th[contains(text(), "Добитник")]]',
                '//table[.//th[contains(text(), "Вредност")]]',
            ]

            award_table = None
            for xpath in award_table_xpaths:
                table = response.xpath(xpath)
                if table:
                    award_table = table
                    break

            if award_table:
                rows = award_table.xpath('.//tbody/tr | .//tr[td]')
                for idx, row in enumerate(rows, start=1):
                    cells = row.xpath('.//td')
                    if len(cells) >= 2:
                        award_data = {
                            'award_number': idx,
                            'tender_id': tender_id,
                        }

                        # Extract lot numbers (usually first column, format: "13, 14, 20")
                        first_cell = cells[0].xpath('.//text()').get()
                        if first_cell:
                            first_cell = first_cell.strip()
                            if re.match(r'^[\d,\s]+$', first_cell):
                                award_data['lot_numbers'] = first_cell

                        # Extract winner name
                        for i in range(1, min(4, len(cells))):
                            text = cells[i].xpath('.//text()').get()
                            if text:
                                text = text.strip()
                                # Winner names are company names (longer text)
                                if len(text) > 5 and not re.match(r'^[\d,.\s]+$', text):
                                    if 'winner_name' not in award_data:
                                        award_data['winner_name'] = text
                                        break

                        # Extract contract value
                        for cell in cells:
                            text = cell.xpath('.//text()').get()
                            if text:
                                amount = self._parse_currency(text)
                                if amount and amount > 1000:
                                    if 'contract_value_mkd' not in award_data:
                                        award_data['contract_value_mkd'] = float(amount)

                        # Extract date
                        for cell in cells:
                            text = cell.xpath('.//text()').get()
                            if text:
                                date = self._parse_date(text)
                                if date:
                                    award_data['contract_date'] = date

                        if award_data.get('winner_name') or award_data.get('lot_numbers'):
                            # Count lots
                            if award_data.get('lot_numbers'):
                                lots = [l.strip() for l in award_data['lot_numbers'].split(',') if l.strip()]
                                award_data['num_lots'] = len(lots)
                            else:
                                award_data['num_lots'] = 1

                            lot_awards.append(award_data)

        except Exception as e:
            logger.warning(f"Error extracting lot awards: {e}")

        return lot_awards

    def _extract_bid_range(self, response: Response) -> Dict[str, Decimal]:
        """Extract highest and lowest bid values"""
        bid_range = {}

        try:
            # Highest bid
            highest_xpaths = [
                '//label[contains(@label-for, "HighestOfferValue")]/following-sibling::label/text()',
                '//label[contains(text(), "Највисока понуда")]/following-sibling::label/text()',
            ]
            for xpath in highest_xpaths:
                value = response.xpath(xpath).get()
                if value:
                    parsed = self._parse_currency(value)
                    if parsed:
                        bid_range['highest_bid_mkd'] = parsed
                        break

            # Lowest bid
            lowest_xpaths = [
                '//label[contains(@label-for, "LowestOfferValue")]/following-sibling::label/text()',
                '//label[contains(text(), "Најниска понуда")]/following-sibling::label/text()',
            ]
            for xpath in lowest_xpaths:
                value = response.xpath(xpath).get()
                if value:
                    parsed = self._parse_currency(value)
                    if parsed:
                        bid_range['lowest_bid_mkd'] = parsed
                        break

        except Exception as e:
            logger.warning(f"Error extracting bid range: {e}")

        return bid_range

    def _extract_tender_id(self, response: Response) -> Optional[str]:
        """Extract tender ID from page"""
        selectors = [
            'label[label-for="ANNOUNCEMENT NUMBER DOSIE"] + label.dosie-value::text',
            '//label[contains(text(), "Број на оглас")]/following-sibling::label/text()',
        ]
        for selector in selectors:
            try:
                if selector.startswith('//'):
                    value = response.xpath(selector).get()
                else:
                    value = response.css(selector).get()
                if value and '/' in value.strip():
                    return value.strip()
            except:
                continue

        # Fallback: extract from URL
        match = re.search(r'dossie[^/]*/([a-f0-9-]+)', response.url)
        if match:
            return match.group(1)
        return None

    def _extract_cpv_code(self, response: Response) -> Optional[str]:
        """Extract CPV code"""
        page_text = response.text
        match = re.search(r'\b(\d{8}-\d)\b', page_text)
        if match:
            return match.group(1)
        match = re.search(r'\b(\d{8})\b(?!\d)', page_text)
        if match:
            return match.group(1)
        return None

    def _extract_field(self, response: Response, field_name: str) -> Optional[str]:
        """Extract field using selectors"""
        FIELD_SELECTORS = {
            'title': ['label[label-for*="SUBJECT"] + label.dosie-value::text'],
            'description': ['label[label-for*="DETAIL"] + label.dosie-value::text'],
            'procuring_entity': ['label[label-for="CONTRACTING INSTITUTION NAME DOSIE"] + label.dosie-value::text'],
            'category': ['label:contains("Вид на договорот") + label.dosie-value::text'],
            'procedure_type': ['label[label-for="TYPE OF CALL:"] + label.dosie-value::text'],
            'winner': [
                'label:contains("Добитник") + label.dosie-value::text',
                'label:contains("Избран понудувач") + label.dosie-value::text',
            ],
            'contact_person': ['label:contains("Контакт лице") + label.dosie-value::text'],
            'contact_email': ['label:contains("Е-пошта") + label.dosie-value::text'],
            'contact_phone': ['label:contains("Телефон") + label.dosie-value::text'],
        }

        for selector in FIELD_SELECTORS.get(field_name, []):
            try:
                value = response.css(selector).get()
                if value and value.strip():
                    return value.strip()
            except:
                continue
        return None

    def _extract_date(self, response: Response, field_name: str) -> Optional[str]:
        """Extract date field"""
        DATE_SELECTORS = {
            'publication_date': ['label[label-for="ANNOUNCEMENT DATE DOSSIE"] + label.dosie-value::text'],
            'opening_date': ['label:contains("Датум на отворање") + label.dosie-value::text'],
            'closing_date': ['label:contains("Рок за поднесување") + label.dosie-value::text'],
            'contract_signing_date': ['label:contains("Датум на склучување") + label.dosie-value::text'],
        }

        for selector in DATE_SELECTORS.get(field_name, []):
            try:
                value = response.css(selector).get()
                if value:
                    parsed = self._parse_date(value)
                    if parsed:
                        return parsed
            except:
                continue
        return None

    def _parse_date(self, date_string: str) -> Optional[str]:
        """Parse Macedonian date format to ISO"""
        if not date_string:
            return None
        date_string = re.sub(r'(година|год\.?|часот)', '', date_string).strip()
        patterns = [
            (r'(\d{2})\.(\d{2})\.(\d{4})', '{2}-{1}-{0}'),
            (r'(\d{4})-(\d{2})-(\d{2})', '{0}-{1}-{2}'),
        ]
        for pattern, template in patterns:
            match = re.search(pattern, date_string)
            if match:
                return template.format(*match.groups())
        return None

    def _extract_currency(self, response: Response, field_name: str) -> Optional[Decimal]:
        """Extract currency value"""
        CURRENCY_XPATHS = {
            'estimated_value_mkd': ['//label[contains(text(), "Проценета вредност")]/following-sibling::label/text()'],
            'actual_value_mkd': ['//label[contains(text(), "Вредност на договорот")]/following-sibling::label/text()'],
        }
        for xpath in CURRENCY_XPATHS.get(field_name, []):
            try:
                values = response.xpath(xpath).getall()
                for v in values:
                    parsed = self._parse_currency(v)
                    if parsed:
                        return parsed
            except:
                continue
        return None

    def _parse_currency(self, value_string: str) -> Optional[Decimal]:
        """Parse European currency format"""
        if not value_string:
            return None
        number_str = re.sub(r'[^\d,\.]', '', value_string)
        if not number_str:
            return None
        try:
            if '.' in number_str and ',' in number_str:
                number_str = number_str.replace('.', '').replace(',', '.')
            elif ',' in number_str:
                number_str = number_str.replace(',', '.')
            return Decimal(number_str)
        except:
            return None

    def _extract_lots(self, response: Response, tender_id: str) -> List[Dict]:
        """Extract lot information"""
        lots = []
        try:
            lot_table = response.xpath('//table[.//th[contains(text(), "Лот")]]')
            if lot_table:
                rows = lot_table.css('tbody tr')
                for idx, row in enumerate(rows, start=1):
                    lot_data = {'lot_number': str(idx)}
                    title = row.css('td:first-child::text').get()
                    if title:
                        lot_data['lot_title'] = title.strip()
                    lots.append(lot_data)
        except:
            pass
        return lots

    def _extract_documents(self, response: Response, tender_id: str) -> List[Dict]:
        """Extract document links"""
        documents = []
        seen = set()

        for selector in ['a[href*="Download"]::attr(href)', 'a[href*=".pdf"]::attr(href)']:
            for link in response.css(selector).getall():
                if link and link not in seen:
                    seen.add(link)
                    if not link.startswith('http'):
                        link = 'https://e-nabavki.gov.mk' + link
                    documents.append({
                        'url': link,
                        'tender_id': tender_id,
                        'file_name': link.split('/')[-1],
                        'doc_category': 'document',
                    })
        return documents

    def _detect_status(self, tender: Dict, source_category: str) -> str:
        """Detect tender status"""
        if source_category in ('awarded', 'contracts', 'tender_winners', 'historical'):
            return 'awarded'
        if source_category == 'cancelled':
            return 'cancelled'
        if tender.get('winner'):
            return 'awarded'
        return 'open' if source_category == 'active' else 'published'

    def _generate_content_hash(self, tender: Dict) -> str:
        """Generate hash for change detection"""
        content = f"{tender.get('tender_id', '')}{tender.get('title', '')}{tender.get('winner', '')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def errback_playwright(self, failure):
        """Handle errors - close page and continue"""
        logger.error(f"Playwright error: {failure.value}")
        self.stats['errors'].append(str(failure.value))

        # Try to close the page to free resources
        try:
            request = failure.request
            if hasattr(request, 'meta') and request.meta.get('playwright_page'):
                page = request.meta['playwright_page']
                await page.close()
                logger.info("Closed failed page, continuing to next URL")
        except Exception as e:
            logger.debug(f"Could not close page: {e}")

    def close(self, reason):
        """Log final stats"""
        logger.warning("=" * 70)
        logger.warning("ENHANCED SCRAPING COMPLETE")
        logger.warning(f"Tenders scraped: {self.stats['tenders_scraped']}")
        logger.warning(f"Total bidders extracted: {self.stats['all_bidders_extracted']}")
        logger.warning(f"Total lot awards extracted: {self.stats['lot_awards_extracted']}")
        logger.warning("=" * 70)
