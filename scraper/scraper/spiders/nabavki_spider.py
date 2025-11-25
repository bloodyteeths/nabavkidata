"""
E-nabavki.gov.mk Spider - Multi-Category Scraper with Playwright
Scrapes tenders from North Macedonia's public procurement portal
Supports: active, awarded, cancelled, historical, discovery, and incremental modes

Usage:
    scrapy crawl nabavki                              # Default: active tenders
    scrapy crawl nabavki -a category=active           # Active tenders only
    scrapy crawl nabavki -a category=awarded          # Awarded tenders
    scrapy crawl nabavki -a category=cancelled        # Cancelled tenders
    scrapy crawl nabavki -a category=historical       # Historical archive
    scrapy crawl nabavki -a category=all              # All categories
    scrapy crawl nabavki -a mode=discover             # Discover available categories
    scrapy crawl nabavki -a mode=incremental          # Only scrape new/changed tenders
    scrapy crawl nabavki -a mode=full                 # Full scrape (default)

Phase 5 (Incremental Mode):
    - mode=incremental: Uses content_hash to detect changes, skips unchanged tenders
    - mode=full: Scrapes all tenders regardless of change status (default)
"""

import scrapy
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
import re
import json
from scrapy.http import Response
from scraper.items import TenderItem, DocumentItem

logger = logging.getLogger(__name__)


class NabavkiSpider(scrapy.Spider):
    name = 'nabavki'
    allowed_domains = ['e-nabavki.gov.mk']

    # Category URL mapping - discovered URLs
    # Based on site exploration (2025-11-24)
    #
    # FINDINGS:
    # - PublicAccess/home.aspx#/notices: WORKING - active tenders
    # - PublicAccess/home.aspx#/contracts/0: WORKING - contract notices with dossie-acpp links (awarded/contracted)
    # - PublicAccess/home.aspx#/cancelations: WORKING - cancellation list (no direct links yet)
    # - PublicAccess/home.aspx#/tender-winners/0: WORKING - award decisions (no direct links yet)
    # - InstitutionGridData.aspx#/ciContractsGrid: Exists but renders marketing page (no data without auth)
    #
    CATEGORY_URLS = {
        'active': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices',
        'awarded': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0',  # contract notices (awarded/contract signed)
        'cancelled': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/cancelations',
        'historical': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/realized-contract',  # realized contracts (closest to archive)
        'contracts': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0',
        'tender_winners': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/tender-winners/0',
        'planned': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/announcement-plans',
    }

    # Candidate URLs to probe during discovery
    # Includes both PublicAccess routes and InstitutionGridData routes
    DISCOVERY_CANDIDATES = {
        'awarded': [
            '#/contracts/0',
            '#/notifications-for-acpp',
            '#/tender-winners/0',
            '#/tender-winners',
        ],
        'cancelled': [
            '#/cancelations',
            '#/cancelled',
            '#/annulled',
            '#/ponisteni',  # Macedonian: "cancelled"
        ],
        'historical': [
            '#/realized-contract',
            '#/contracts/0',
            '#/tender-winners/0',
        ],
        'contracts': [
            '#/contracts/0',
            '#/notifications-for-acpp',
        ],
        'planned': [
            '#/announcement-plans',
            '#/planned',
            '#/upcoming',
            '#/planirani',  # Macedonian: "planned"
        ],
    }

    # Base URLs for different sections of the site
    BASE_URLS = {
        'public_access': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx',
        'institution_grid': 'https://e-nabavki.gov.mk/InstitutionGridData.aspx',
        'notification': 'https://e-nabavki.gov.mk/PublicAccess/NotificationForACPP/default.aspx',
    }

    # Custom settings to ensure proper request processing
    custom_settings = {
        "DOWNLOAD_DELAY": 0.25,
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1,
        "PLAYWRIGHT_MAX_CONTEXTS": 4,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        "DUPEFILTER_CLASS": "scrapy.dupefilters.BaseDupeFilter",
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 0.5,
        "AUTOTHROTTLE_MAX_DELAY": 2.0,
    }

    def __init__(self, category='active', mode='scrape', *args, **kwargs):
        """
        Initialize spider with category and mode parameters.

        Args:
            category: One of 'active', 'awarded', 'cancelled', 'historical', 'all'
            mode: 'scrape' (default), 'discover' (probe URLs), 'incremental' (only new/changed),
                  or 'full' (alias for scrape)
        """
        super().__init__(*args, **kwargs)
        self.category = category.lower()
        self.mode = mode.lower()

        # Normalize mode aliases
        if self.mode == 'full':
            self.mode = 'scrape'

        self.discovered_urls = {}
        self.existing_tender_hashes = {}  # For incremental mode
        self.stats = {
            'tenders_found': 0,
            'tenders_scraped': 0,
            'tenders_skipped': 0,  # For incremental mode
            'extraction_failures': {},
            'categories_discovered': [],
            'categories_failed': [],
        }

    def start_requests(self):
        """
        Generate start requests based on category and mode parameters.

        Modes:
        - 'discover': Probe all candidate URLs to find working categories
        - 'scrape': Scrape tenders from specified category(ies)
        """
        if self.mode == 'discover':
            # Discovery mode: probe all candidate URLs to find working ones
            logger.warning("="*60)
            logger.warning("DISCOVERY MODE: Probing for available category URLs")
            logger.warning("="*60)

            # Probe routes on both PublicAccess and InstitutionGridData base URLs
            base_urls_to_try = [
                self.BASE_URLS['public_access'],
                self.BASE_URLS['institution_grid'],
            ]

            for category, candidates in self.DISCOVERY_CANDIDATES.items():
                for route in candidates:
                    for base_url in base_urls_to_try:
                        full_url = f"{base_url}{route}"
                        logger.info(f"Probing {category}: {full_url}")
                        yield scrapy.Request(
                            full_url,
                            callback=self.parse_discovery,
                            meta={
                                'playwright': True,
                                'playwright_include_page': True,
                                'playwright_page_goto_kwargs': {
                                    'wait_until': 'networkidle',
                                    'timeout': 30000,
                                },
                                'category': category,
                                'route': route,
                                'base_url': base_url,
                            },
                            errback=self.errback_discovery,
                            dont_filter=True
                        )

            # Also probe known working URLs
            for cat, url in self.CATEGORY_URLS.items():
                if url:
                    logger.info(f"Probing known URL for {cat}: {url}")
                    yield scrapy.Request(
                        url,
                        callback=self.parse_discovery,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'playwright_page_goto_kwargs': {
                                'wait_until': 'networkidle',
                                'timeout': 30000,
                            },
                            'category': cat,
                            'route': url.split('#')[-1] if '#' in url else url,
                            'base_url': url.split('#')[0] if '#' in url else url,
                        },
                        errback=self.errback_discovery,
                        dont_filter=True
                    )

        else:
            # Scrape mode: scrape tenders from specified category
            urls_to_scrape = []

            if self.category == 'all':
                # Scrape all known working categories
                for cat, url in self.CATEGORY_URLS.items():
                    if url:
                        urls_to_scrape.append((cat, url))
            elif self.category in self.CATEGORY_URLS:
                url = self.CATEGORY_URLS.get(self.category)
                if url:
                    urls_to_scrape.append((self.category, url))
                else:
                    logger.error(f"Category '{self.category}' URL not known. Run with mode=discover first.")
                    return
            else:
                logger.error(f"Unknown category: {self.category}")
                logger.info(f"Available categories: {list(self.CATEGORY_URLS.keys())}")
                return

            for cat, url in urls_to_scrape:
                logger.warning(f"Starting scraper for category '{cat}': {url}")
                yield scrapy.Request(
                    url,
                    callback=self.parse,
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

    async def parse_discovery(self, response):
        """
        Parse response during discovery mode to check if URL contains tenders.
        """
        category = response.meta.get('category')
        route = response.meta.get('route')
        page = response.meta.get('playwright_page')

        tender_count = 0
        url_works = False

        if page:
            try:
                # Wait for potential tender table to load
                await page.wait_for_timeout(3000)

                # Check for tender rows using various selectors
                selectors_to_check = [
                    'table#notices-grid tbody tr',
                    '.RowStyle',
                    '.AltRowStyle',
                    'table tbody tr td a',
                    '[ng-repeat*="tender"]',
                    '[ng-repeat*="notice"]',
                    '.tender-row',
                    '.notice-row',
                ]

                for selector in selectors_to_check:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements and len(elements) > 0:
                            tender_count = len(elements)
                            url_works = True
                            break
                    except:
                        continue

                # Check for direct tender links (dossie/dossie-acpp)
                if not url_works:
                    try:
                        link_elems = await page.query_selector_all("a[href*='dossie']")
                        if link_elems:
                            tender_count = len(link_elems)
                            url_works = True
                    except Exception:
                        pass

                # Also check page content for indicators
                if not url_works:
                    content = await page.content()
                    indicators = ['tender', 'notice', 'nabavk', 'оглас', 'набавк', 'понуд']
                    if any(ind in content.lower() for ind in indicators):
                        url_works = True

            except Exception as e:
                logger.warning(f"Discovery error for {route}: {e}")
            finally:
                try:
                    await page.close()
                except:
                    pass

        if url_works:
            logger.warning(f"✅ FOUND: {category} at {route} - {tender_count} items")
            self.stats['categories_discovered'].append({
                'category': category,
                'route': route,
                'url': response.url,
                'item_count': tender_count
            })
        else:
            logger.info(f"❌ NOT FOUND: {category} at {route}")
            self.stats['categories_failed'].append({
                'category': category,
                'route': route
            })

    async def errback_discovery(self, failure):
        """Handle discovery errors"""
        request = failure.request
        category = request.meta.get('category')
        route = request.meta.get('route')
        logger.info(f"❌ Discovery failed for {category} at {route}: {failure.value}")

    async def parse(self, response):
        """
        Parse tender listings page (Angular DataTable)
        Extracts tender links from table#notices-grid
        """
        page = response.meta.get('playwright_page')
        source_category = response.meta.get('category', 'active')

        if page:
            try:
                # Wait for Angular DataTable to load
                await page.wait_for_selector('table#notices-grid tbody tr', timeout=15000)
                await page.wait_for_timeout(2000)  # Extra wait for data binding
                logger.info(f"✓ Angular DataTable loaded successfully for category: {source_category}")
            except Exception as e:
                logger.error(f"Failed to wait for DataTable: {e}")

        logger.info(f"Parsing listing page ({source_category}): {response.url}")

        tender_links = []

        # Prefer Playwright anchors to support dossie-acpp pages (contracts/awards)
        if page:
            try:
                link_elems = await page.query_selector_all("a[href*='dossie']")
                tender_links.extend([
                    await elem.get_attribute('href')
                    for elem in link_elems
                    if await elem.get_attribute('href')
                ])
            except Exception as e:
                logger.warning(f"Failed to extract links via Playwright: {e}")

        # Fallback to HTML selectors
        if not tender_links:
            tender_links = response.css('table#notices-grid tbody tr td:first-child a[href*=\"/dossie/\"]::attr(href)').getall()

        if not tender_links:
            tender_links = response.css('table tbody tr td a[target=\"_blank\"]::attr(href)').getall()

        self.stats['tenders_found'] += len(tender_links)
        logger.info(f"✓ Found {len(tender_links)} tender links in {source_category}")

        # CRITICAL: Close listing page's Playwright page to free up context for detail pages
        if page:
            try:
                await page.close()
                logger.info("✓ Closed listing page Playwright context")
            except Exception as e:
                logger.warning(f"Failed to close listing page: {e}")

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

            # Force Playwright and disable dupefilter for hash-based URLs
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

        # Pagination temporarily disabled for testing detail page processing
        # TODO: Re-implement pagination after detail pages are working
        logger.info("Pagination: Skipped (page context already closed for detail processing)")

    async def _find_next_page(self, response, page):
        """
        Find and click next page button in DataTables pagination
        Returns URL to current page to trigger re-parsing after click
        """
        if not page:
            return None

        try:
            # DataTables pagination: look for "Next" button
            next_selectors = [
                'a.paginate_button.next:not(.disabled)',
                'button[aria-label="Next"]:not([disabled])',
                'a[aria-label="Next page"]:not(.disabled)',
                'li.next:not(.disabled) a',
                'a:has-text("Next"):not(.disabled)',
                'a:has-text("Следна"):not(.disabled)',  # Macedonian for "Next"
            ]

            for selector in next_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        # Check if button is clickable (not disabled)
                        is_disabled = await button.get_attribute('class')
                        if is_disabled and 'disabled' in is_disabled:
                            logger.info("Pagination: Next button is disabled (last page reached)")
                            return None

                        logger.info(f"✓ Found Next button with selector: {selector}")

                        # Click the button and wait for navigation/update
                        await button.click()
                        await page.wait_for_timeout(2000)  # Wait for DataTable to update
                        await page.wait_for_selector('table#notices-grid tbody tr', timeout=10000)

                        # Return current URL to re-parse the page with new data
                        current_url = page.url
                        logger.info(f"✓ Clicked Next button, re-parsing page")
                        return current_url

                except Exception as e:
                    continue

            logger.info("Pagination: No next page button found (last page)")
            return None

        except Exception as e:
            logger.warning(f"Error in pagination: {e}")
            return None

    async def parse_tender_detail(self, response):
        """
        Parse tender detail page using label-based extraction
        Angular page structure: <label label-for="...">Label:</label> <label class="dosie-value">Value</label>
        """
        # CRITICAL: Log that we're processing detail page
        logger.warning(f"🔥 PROCESSING DETAIL PAGE: {response.url}")

        page = response.meta.get('playwright_page')

        if page:
            try:
                # Wait for Angular to render content
                await page.wait_for_selector('label.dosie-value', timeout=20000)
                await page.wait_for_timeout(1500)
                logger.info("✓ Tender detail page loaded")

                # Get updated HTML content after JavaScript execution
                html_content = await page.content()

                # Replace response body with rendered HTML
                response = response.replace(body=html_content.encode('utf-8'))
                logger.info("✓ Updated response with rendered HTML")

            except Exception as e:
                logger.error(f"❌ Failed to wait for dosie-value labels: {e}")
            finally:
                # Close Playwright page safely
                try:
                    await page.close()
                    logger.info("✓ Closed Playwright page")
                except Exception as e:
                    logger.warning(f"Failed to close page: {e}")

        source_category = response.meta.get('source_category', 'active')
        logger.info(f"Extracting tender from ({source_category}): {response.url}")

        # Initialize tender data
        tender = {
            'source_url': response.url,
            'scraped_at': datetime.utcnow().isoformat(),
            'language': 'mk',
            'source_category': source_category,  # Track which category this tender came from
        }

        # Extract all fields using label-based selectors
        tender['tender_id'] = self._extract_field(response, 'tender_id')
        tender['title'] = self._extract_field(response, 'title')
        tender['description'] = self._extract_field(response, 'description')
        tender['procuring_entity'] = self._extract_field(response, 'procuring_entity')
        tender['category'] = self._extract_field(response, 'category')
        tender['cpv_code'] = self._extract_field(response, 'cpv_code')
        tender['procedure_type'] = self._extract_field(response, 'procedure_type')
        tender['contracting_entity_category'] = self._extract_field(response, 'contracting_entity_category')
        tender['procurement_holder'] = self._extract_field(response, 'procurement_holder')

        # Extract dates
        tender['publication_date'] = self._extract_date(response, 'publication_date')
        tender['opening_date'] = self._extract_date(response, 'opening_date')
        tender['closing_date'] = self._extract_date(response, 'closing_date')
        tender['contract_signing_date'] = self._extract_date(response, 'contract_signing_date')
        tender['bureau_delivery_date'] = self._extract_date(response, 'bureau_delivery_date')

        # Extract values
        tender['estimated_value_mkd'] = self._extract_currency(response, 'estimated_value_mkd')
        tender['estimated_value_eur'] = self._extract_currency(response, 'estimated_value_eur')
        tender['actual_value_mkd'] = self._extract_currency(response, 'actual_value_mkd')
        tender['actual_value_eur'] = self._extract_currency(response, 'actual_value_eur')
        tender['security_deposit_mkd'] = self._extract_currency(response, 'security_deposit_mkd')
        tender['performance_guarantee_mkd'] = self._extract_currency(response, 'performance_guarantee_mkd')

        # Extract other fields
        tender['contract_duration'] = self._extract_field(response, 'contract_duration')
        tender['winner'] = self._extract_field(response, 'winner')

        # Extract contact fields
        tender['contact_person'] = self._extract_field(response, 'contact_person')
        tender['contact_email'] = self._extract_field(response, 'contact_email')
        tender['contact_phone'] = self._extract_field(response, 'contact_phone')

        # Extract financial and evaluation fields
        tender['payment_terms'] = self._extract_field(response, 'payment_terms')
        tender['evaluation_method'] = self._extract_field(response, 'evaluation_method')

        # Extract bidders and lots
        tender_id = tender.get('tender_id', 'unknown')
        bidders_list = self._extract_bidders(response, tender_id)
        lots_list = self._extract_lots(response, tender_id)

        # Set bidder and lot related fields
        tender['bidders_data'] = json.dumps(bidders_list, ensure_ascii=False) if bidders_list else None
        tender['lots_data'] = json.dumps(lots_list, ensure_ascii=False) if lots_list else None
        tender['num_bidders'] = len(bidders_list)
        tender['has_lots'] = bool(lots_list)
        tender['num_lots'] = len(lots_list)

        tender['status'] = self._detect_status(tender)

        # Extract documents and yield DocumentItems for pipeline processing
        documents = self._extract_documents(response, tender.get('tender_id', 'unknown'))
        tender['documents_data'] = documents
        logger.warning(f"Documents captured for {tender.get('tender_id')}: {len(documents)}")
        for doc in documents:
            logger.warning(f"Yielding document item for tender {tender.get('tender_id')}: {doc.get('file_name')}")
            if hasattr(self, "crawler") and self.crawler:
                self.crawler.stats.inc_value("documents_yielded", 1)
            yield DocumentItem(
                tender_id=doc.get('tender_id'),
                file_url=doc.get('url'),
                file_name=doc.get('file_name'),
                doc_category=doc.get('doc_category'),
                upload_date=doc.get('upload_date'),
                doc_type=doc.get('doc_type', 'document'),
                extraction_status='pending'
            )

        # Log extraction statistics
        self._log_extraction_stats(tender)
        self.stats['tenders_scraped'] += 1

        logger.warning(f"✅ Successfully extracted tender: {tender.get('tender_id')}")

        # Yield tender item
        yield TenderItem(**tender)

    def _extract_field(self, response: Response, field_name: str) -> Optional[str]:
        """
        Extract field using label-based selectors with fallbacks
        """
        # Define label-for attributes for each field
        FIELD_LABELS = {
            'tender_id': [
                'label[label-for="ANNOUNCEMENT NUMBER DOSIE"] + label.dosie-value::text',
                'label:contains("Број на оглас:") + label.dosie-value::text',
                'label.dosie-value:contains("/")::text',
            ],
            'title': [
                'label[label-for*="SUBJECT"] + label.dosie-value::text',
                'label:contains("Предмет на договорот") + label.dosie-value::text',
                'label:contains("Предмет на делот") + label.dosie-value::text',
            ],
            'description': [
                'label[label-for*="SUBJECT"] + label.dosie-value::text',
                'label:contains("Предмет") + label.dosie-value::text',
            ],
            'procuring_entity': [
                'label[label-for="CONTRACTING INSTITUTION NAME DOSIE"] + label.dosie-value::text',
                'label:contains("Договорен орган") + label.dosie-value::text',
                'label:contains("Назив на договорниот орган") + label.dosie-value::text',
            ],
            'category': [
                'label:contains("Вид на договорот:") + label.dosie-value::text',
                'label:contains("Вид на договорот") ~ label.dosie-value::text',
            ],
            'cpv_code': [
                'label:contains("CPV") + label.dosie-value::text',
                'label[label-for*="CPV"] + label.dosie-value::text',
            ],
            'procedure_type': [
                'label[label-for="TYPE OF CALL:"] + label.dosie-value::text',
                'label:contains("Вид на постапка:") + label.dosie-value::text',
            ],
            'contracting_entity_category': [
                'label:contains("Категорија") + label.dosie-value::text',
            ],
            'procurement_holder': [
                'label:contains("Носител") + label.dosie-value::text',
            ],
            'contract_duration': [
                'label:contains("Времетраење") + label.dosie-value::text',
                'label:contains("Период") + label.dosie-value::text',
            ],
            'winner': [
                'label:contains("Добитник") + label.dosie-value::text',
                'label:contains("Избран понудувач") + label.dosie-value::text',
            ],
            'contact_person': [
                'label:contains("Контакт лице") + label.dosie-value::text',
                'label:contains("Contact person") + label.dosie-value::text',
                'label:contains("Лице за контакт") + label.dosie-value::text',
                'label[label-for*="CONTACT"] + label.dosie-value::text',
            ],
            'contact_email': [
                'label:contains("Е-пошта") + label.dosie-value::text',
                'label:contains("Email") + label.dosie-value::text',
                'label:contains("E-mail") + label.dosie-value::text',
                'label:contains("Електронска пошта") + label.dosie-value::text',
            ],
            'contact_phone': [
                'label:contains("Телефон") + label.dosie-value::text',
                'label:contains("Phone") + label.dosie-value::text',
                'label:contains("Тел.") + label.dosie-value::text',
                'label:contains("Telephone") + label.dosie-value::text',
            ],
            'payment_terms': [
                'label:contains("Услови за плаќање") + label.dosie-value::text',
                'label:contains("Payment terms") + label.dosie-value::text',
                'label:contains("Начин на плаќање") + label.dosie-value::text',
                'label:contains("Рок за плаќање") + label.dosie-value::text',
            ],
            'evaluation_method': [
                'label:contains("Метод на евалуација") + label.dosie-value::text',
                'label:contains("Evaluation method") + label.dosie-value::text',
                'label:contains("Критериум") + label.dosie-value::text',
                'label:contains("Критериуми за доделување") + label.dosie-value::text',
                'label:contains("Критериум за избор") + label.dosie-value::text',
            ],
        }

        selectors = FIELD_LABELS.get(field_name, [])

        for selector in selectors:
            try:
                value = response.css(selector).get()
                if value:
                    value = value.strip()
                    if value:
                        return value
            except Exception as e:
                continue

        return None

    def _extract_date(self, response: Response, field_name: str) -> Optional[str]:
        """Extract and parse date fields"""
        DATE_FIELDS = {
            'publication_date': [
                'label[label-for="ANNOUNCEMENT DATE DOSSIE"] + label.dosie-value::text',
                'label:contains("Датум на објавување") + label.dosie-value::text',
            ],
            'opening_date': [
                'label:contains("Датум на отворање") + label.dosie-value::text',
            ],
            'closing_date': [
                'label:contains("Рок за поднесување") + label.dosie-value::text',
                'label:contains("Краен рок") + label.dosie-value::text',
            ],
            'contract_signing_date': [
                'label:contains("Датум на склучување") + label.dosie-value::text',
            ],
            'bureau_delivery_date': [
                'label:contains("Датум на достава") + label.dosie-value::text',
            ],
        }

        selectors = DATE_FIELDS.get(field_name, [])

        for selector in selectors:
            try:
                date_str = response.css(selector).get()
                if date_str:
                    date_str = date_str.strip()
                    parsed = self._parse_date(date_str)
                    if parsed:
                        return parsed
            except Exception as e:
                continue

        return None

    def _parse_date(self, date_string: str) -> Optional[str]:
        """Parse Macedonian date format to ISO format"""
        if not date_string:
            return None

        # Remove Macedonian words
        date_string = re.sub(r'(година|год\.?|часот)', '', date_string).strip()

        patterns = [
            r'(\d{2})\.(\d{2})\.(\d{4})',  # DD.MM.YYYY
            r'(\d{2})/(\d{2})/(\d{4})',    # DD/MM/YYYY
            r'(\d{4})-(\d{2})-(\d{2})',    # YYYY-MM-DD
        ]

        for pattern in patterns:
            match = re.search(pattern, date_string)
            if match:
                if pattern == patterns[2]:  # Already ISO format
                    return match.group(0)
                else:
                    day, month, year = match.groups()
                    return f"{year}-{month}-{day}"

        return None

    def _extract_currency(self, response: Response, field_name: str) -> Optional[Decimal]:
        """
        Extract and parse currency values using XPath for better text matching.

        The e-nabavki site structure:
        - Label: <label label-for="ESTIMATED VALUE NO DDV"> Проценета вредност без ДДВ:</label>
        - Value: <label class="dosie-value ng-binding">200.000,00</label>

        Note: Values often don't include currency suffix (МКД/EUR), just the number.
        For estimated_value_mkd, we get the first numeric value.
        For estimated_value_eur, we look for a second value or EUR indicator.
        """
        # XPath selectors for currency fields
        CURRENCY_XPATH = {
            'estimated_value_mkd': [
                # Primary: Look for label with "ESTIMATED VALUE" label-for attribute
                '//label[contains(@label-for, "ESTIMATED VALUE")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Also try text-based matching
                '//label[contains(text(), "Проценета вредност") and not(contains(text(), "Објавување"))]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Fallback: any dosie-value after estimated value label
                '//label[contains(text(), "Проценета вредност без")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
            ],
            'estimated_value_eur': [
                # EUR is usually the second value or has EUR in the text
                '//label[contains(@label-for, "ESTIMATED VALUE")]/following-sibling::label[contains(@class, "dosie-value")][contains(text(), "EUR")]/text()',
                '//label[contains(text(), "Проценета вредност")]/following-sibling::label[contains(@class, "dosie-value")][contains(text(), "EUR")]/text()',
                # Second value after estimated value label
                '//label[contains(@label-for, "ESTIMATED VALUE")]/following-sibling::label[contains(@class, "dosie-value")][2]/text()',
            ],
            'actual_value_mkd': [
                '//label[contains(@label-for, "CONTRACT VALUE")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Вредност на договорот")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Contract value")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
            ],
            'actual_value_eur': [
                '//label[contains(@label-for, "CONTRACT VALUE")]/following-sibling::label[contains(@class, "dosie-value")][contains(text(), "EUR")]/text()',
                '//label[contains(text(), "Вредност на договорот")]/following-sibling::label[contains(@class, "dosie-value")][2]/text()',
            ],
            'security_deposit_mkd': [
                '//label[contains(text(), "Гаранција за учество")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
                '//label[contains(text(), "Security deposit")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
                '//label[contains(text(), "Депозит")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
            ],
            'performance_guarantee_mkd': [
                '//label[contains(text(), "Гаранција за извршување")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
                '//label[contains(text(), "Performance guarantee")]/following-sibling::label[contains(@class, "dosie-value")]/text()',
            ],
        }

        xpaths = CURRENCY_XPATH.get(field_name, [])

        for xpath in xpaths:
            try:
                values = response.xpath(xpath).getall()
                for value_str in values:
                    if value_str:
                        value_str = value_str.strip()
                        # Skip "Не" or "Да" values (these are yes/no indicators)
                        if value_str in ('Не', 'Да', 'No', 'Yes'):
                            continue
                        parsed = self._parse_currency(value_str)
                        if parsed:
                            logger.info(f"Extracted {field_name}: {parsed} from '{value_str}'")
                            return parsed
            except Exception as e:
                logger.debug(f"XPath error for {field_name}: {e}")
                continue

        return None

    def _parse_currency(self, value_string: str) -> Optional[Decimal]:
        """Parse European currency format"""
        if not value_string:
            return None

        # Remove currency symbols and text
        number_str = re.sub(r'[^\d,\.]', '', value_string)

        if not number_str:
            return None

        try:
            # European format: 1.234.567,89
            if '.' in number_str and ',' in number_str:
                number_str = number_str.replace('.', '').replace(',', '.')
            elif ',' in number_str:
                number_str = number_str.replace(',', '.')

            return Decimal(number_str)
        except:
            return None

    def _categorize_document(self, filename: str, doc_type: str) -> str:
        """
        Categorize document based on filename patterns

        Returns one of:
        - 'technical_specs' - Technical specifications
        - 'financial_docs' - Financial/budget documents
        - 'award_decision' - Award decision/announcement
        - 'contract' - Contract documents
        - 'tender_docs' - General tender documentation
        - 'amendments' - Amendments/modifications
        - 'clarifications' - Q&A, clarifications
        - 'other' - Unknown category
        """
        filename_lower = filename.lower()

        # Technical specifications
        if any(keyword in filename_lower for keyword in [
            'технички', 'technical', 'спецификација', 'specification',
            'технічки', 'tech_spec'
        ]):
            return 'technical_specs'

        # Financial/budget documents
        if any(keyword in filename_lower for keyword in [
            'финансиски', 'финанс', 'буџет', 'budget', 'financial',
            'фінансов', 'price', 'цена', 'вредност', 'value'
        ]):
            return 'financial_docs'

        # Award decision/announcement
        if any(keyword in filename_lower for keyword in [
            'одлука', 'decision', 'award', 'доделување', 'избор',
            'winner', 'добитник', 'резултат', 'result'
        ]):
            return 'award_decision'

        # Contract documents
        if any(keyword in filename_lower for keyword in [
            'договор', 'contract', 'уговор', 'склучување'
        ]):
            return 'contract'

        # Amendments/modifications
        if any(keyword in filename_lower for keyword in [
            'измени', 'измена', 'amendment', 'модификаци', 'modification',
            'дополнување', 'addendum'
        ]):
            return 'amendments'

        # Clarifications/Q&A
        if any(keyword in filename_lower for keyword in [
            'појаснување', 'clarification', 'прашања', 'question',
            'одговор', 'answer', 'q&a', 'qa'
        ]):
            return 'clarifications'

        # Tender documentation (default for generic tender docs)
        if any(keyword in filename_lower for keyword in [
            'тендер', 'tender', 'документација', 'documentation',
            'оглас', 'notice', 'конкурс'
        ]):
            return 'tender_docs'

        # Default category
        return 'other'

    def _extract_documents(self, response: Response, tender_id: str) -> List[Dict[str, Any]]:
        """Extract document links with categorization and metadata"""
        documents = []

        doc_selectors = [
            'a[href*="Download"]::attr(href)',
            'a[href*=".pdf"]::attr(href)',
            'a[href*="File"]::attr(href)',
        ]

        for selector in doc_selectors:
            links = response.css(selector).getall()
            for link in links:
                if link:
                    # Make absolute URL
                    if not link.startswith('http'):
                        link = 'https://e-nabavki.gov.mk' + link

                    # Extract filename from URL or use a default
                    filename = link.split('/')[-1] if '/' in link else 'document.pdf'

                    # Attempt to extract document type from nearby text
                    # This would require more context from the DOM, using filename for now
                    doc_type = 'document'

                    # Categorize document
                    doc_category = self._categorize_document(filename, doc_type)

                    # Try to extract upload date from page context
                    # Look for date near the document link (this is a best-effort attempt)
                    upload_date = None
                    try:
                        # Try to find date in parent or sibling elements
                        # This selector might need adjustment based on actual page structure
                        date_selectors = [
                            'label:contains("Датум"):contains("upload")::text',
                            'span.date::text',
                            'label.dosie-value:contains("/")::text'
                        ]
                        for date_selector in date_selectors:
                            date_text = response.css(date_selector).get()
                            if date_text:
                                parsed_date = self._parse_date(date_text)
                                if parsed_date:
                                    upload_date = parsed_date
                                    break
                    except Exception as e:
                        logger.debug(f"Could not extract upload date for {filename}: {e}")

                    documents.append({
                        'url': link,
                        'tender_id': tender_id,
                        'doc_category': doc_category,
                        'upload_date': upload_date,
                        'file_name': filename,
                        'doc_type': doc_type,
                    })

        logger.info(f"Extracted {len(documents)} documents for tender {tender_id}")
        return documents

    def _extract_bidders(self, response: Response, tender_id: str) -> List[dict]:
        """
        Extract all bidders/participants from tender page
        Returns list of dicts: [
            {
                'company_name': 'Company ABC',
                'bid_amount_mkd': 150000.00,
                'is_winner': True,
                'rank': 1,
                'disqualified': False
            },
            ...
        ]
        """
        bidders = []

        try:
            # Look for bidder tables with various selectors
            # Pattern 1: DataTable with bidder information (using XPath for contains)
            bidder_table_selectors = [
                '//table[.//th[contains(text(), "Понудувач")]]',
                '//table[.//th[contains(text(), "Учесник")]]',
                '//table[.//th[contains(text(), "Економски оператор")]]',
                '//table[contains(@class, "bidders-table")]',
                '//table[contains(@ng-repeat, "bidder")]',
            ]

            bidder_table = None
            for selector in bidder_table_selectors:
                table = response.xpath(selector)
                if table:
                    bidder_table = table
                    break

            if bidder_table:
                # Extract rows from table
                rows = bidder_table.css('tbody tr')

                for idx, row in enumerate(rows, start=1):
                    cells = row.css('td')

                    if len(cells) >= 2:
                        bidder_data = {}

                        # Try to extract company name (usually first column)
                        company_name = cells[0].css('::text').get()
                        if company_name:
                            bidder_data['company_name'] = company_name.strip()

                        # Try to extract bid amount (look for currency patterns)
                        for cell in cells:
                            cell_text = cell.css('::text').get()
                            if cell_text:
                                amount = self._parse_currency(cell_text)
                                if amount:
                                    bidder_data['bid_amount_mkd'] = float(amount)
                                    break

                        # Check if this is the winner (look for indicators)
                        is_winner = False
                        row_html = row.get()
                        winner_indicators = ['победник', 'добитник', 'избран', 'winner', 'selected']
                        if any(indicator in row_html.lower() for indicator in winner_indicators):
                            is_winner = True

                        bidder_data['is_winner'] = is_winner
                        bidder_data['rank'] = idx
                        bidder_data['disqualified'] = False

                        if bidder_data.get('company_name'):
                            bidders.append(bidder_data)

            # Pattern 2: Single winner field (already extracted in main method)
            # If no table found but winner exists, create single bidder entry
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

            # Pattern 3: Look for ng-repeat bidder elements in Angular
            ng_bidders = response.css('[ng-repeat*="ponuduvac"], [ng-repeat*="bidder"]')
            if ng_bidders and not bidders:
                for idx, elem in enumerate(ng_bidders, start=1):
                    company = elem.css('.company-name::text, .bidder-name::text').get()
                    if company:
                        bidders.append({
                            'company_name': company.strip(),
                            'bid_amount_mkd': None,
                            'is_winner': False,
                            'rank': idx,
                            'disqualified': False
                        })

        except Exception as e:
            logger.warning(f"Error extracting bidders for tender {tender_id}: {e}")

        logger.info(f"Extracted {len(bidders)} bidder(s) for tender {tender_id}")
        return bidders

    def _extract_lots(self, response: Response, tender_id: str) -> List[dict]:
        """
        Extract lot information if tender has multiple lots
        Returns list of dicts: [
            {
                'lot_number': '1',
                'lot_title': 'IT Equipment',
                'estimated_value_mkd': 50000.00,
                'winner': 'Company XYZ'
            },
            ...
        ]
        """
        lots = []

        try:
            # First check if tender is dividable (has lots)
            is_dividable_selectors = [
                '//label[contains(text(), "Делива набавка")]/following-sibling::label[@class="dosie-value"]/text()',
                '//label[contains(@label-for, "LOTS")]/following-sibling::label[@class="dosie-value"]/text()',
            ]

            is_dividable = False
            for selector in is_dividable_selectors:
                value = response.xpath(selector).get()
                if value:
                    value = value.strip().lower()
                    if 'да' in value or 'yes' in value:
                        is_dividable = True
                        break

            if not is_dividable:
                logger.info(f"Tender {tender_id} is not dividable (no lots)")
                return []

            # Look for lot tables/sections
            lot_table_selectors = [
                '//table[.//th[contains(text(), "Лот")]]',
                '//table[.//th[contains(text(), "Партија")]]',
                '//table[contains(@class, "lots-table")]',
                '//table[contains(@ng-repeat, "lot")]',
                '//*[contains(@ng-repeat, "lot")]',
            ]

            lot_elements = None
            for selector in lot_table_selectors:
                elements = response.xpath(selector)
                if elements:
                    lot_elements = elements
                    break

            if lot_elements:
                # Extract from table structure
                if 'table' in lot_table_selectors[0]:
                    rows = lot_elements.css('tbody tr')

                    for row in rows:
                        cells = row.css('td')

                        if len(cells) >= 2:
                            lot_data = {}

                            # Extract lot number (usually first column)
                            lot_num = cells[0].css('::text').get()
                            if lot_num:
                                lot_data['lot_number'] = lot_num.strip()

                            # Extract lot title/description
                            lot_title = cells[1].css('::text').get() if len(cells) > 1 else None
                            if lot_title:
                                lot_data['lot_title'] = lot_title.strip()

                            # Look for estimated value
                            for cell in cells:
                                cell_text = cell.css('::text').get()
                                if cell_text:
                                    amount = self._parse_currency(cell_text)
                                    if amount:
                                        lot_data['estimated_value_mkd'] = float(amount)
                                        break

                            # Look for winner in row
                            winner_cell = None
                            for cell in cells:
                                cell_text = cell.css('::text').get()
                                if cell_text and len(cell_text.strip()) > 5:
                                    # Likely a company name if it's longer text
                                    if not any(char.isdigit() for char in cell_text[:20]):
                                        winner_cell = cell_text.strip()
                                        break

                            if winner_cell:
                                lot_data['winner'] = winner_cell

                            if lot_data.get('lot_number'):
                                lots.append(lot_data)
                else:
                    # Extract from individual lot sections
                    for idx, elem in enumerate(lot_elements, start=1):
                        lot_data = {
                            'lot_number': str(idx),
                            'lot_title': elem.css('.lot-title::text, .lot-name::text').get(),
                            'estimated_value_mkd': None,
                            'winner': None
                        }

                        # Try to find value in the element
                        elem_text = elem.get()
                        amount = self._parse_currency(elem_text)
                        if amount:
                            lot_data['estimated_value_mkd'] = float(amount)

                        lots.append(lot_data)

        except Exception as e:
            logger.warning(f"Error extracting lots for tender {tender_id}: {e}")

        logger.info(f"Extracted {len(lots)} lot(s) for tender {tender_id}")
        return lots

    def _detect_status(self, tender: Dict[str, Any]) -> str:
        """Auto-detect tender status from available fields"""
        source_category = tender.get('source_category', '')
        if source_category in ('awarded', 'contracts', 'tender_winners'):
            return 'awarded'
        if 'cancel' in source_category:
            return 'cancelled'
        if tender.get('winner'):
            return 'awarded'
        elif tender.get('closing_date'):
            return 'active'
        else:
            return 'published'

    def _log_extraction_stats(self, tender: Dict[str, Any]):
        """Log extraction statistics"""
        extracted_fields = {k: v for k, v in tender.items() if v is not None}
        logger.info(f"Extracted {len(extracted_fields)}/{len(tender)} fields for tender {tender.get('tender_id')}")

    async def errback_playwright(self, failure):
        """Handle Playwright errors"""
        logger.error(f"Playwright request failed: {failure.request.url}")
        logger.error(f"Error: {failure.value}")

    def close(self, reason):
        """Called when spider closes"""
        logger.warning("=" * 80)
        logger.warning("SCRAPING COMPLETE")
        logger.warning("=" * 80)
        logger.warning(f"Spider closing: {reason}")
        logger.warning(f"Mode: {self.mode}")
        logger.warning(f"Category: {self.category}")
        logger.warning(f"Tenders found: {self.stats['tenders_found']}")
        logger.warning(f"Tenders scraped: {self.stats['tenders_scraped']}")
        logger.warning(f"Tenders skipped (unchanged): {self.stats['tenders_skipped']}")
        logger.warning(f"Extraction failures: {self.stats['extraction_failures']}")

        # Output discovery results
        if self.mode == 'discover':
            logger.warning("=" * 80)
            logger.warning("DISCOVERY RESULTS")
            logger.warning("=" * 80)

            if self.stats['categories_discovered']:
                logger.warning("✅ WORKING CATEGORIES:")
                for cat in self.stats['categories_discovered']:
                    logger.warning(f"  - {cat['category']}: {cat['route']} ({cat['item_count']} items)")

                # Save discovery results to file
                discovery_file = '/tmp/e_nabavki_discovered_urls.json'
                try:
                    with open(discovery_file, 'w') as f:
                        json.dump({
                            'discovered': self.stats['categories_discovered'],
                            'failed': self.stats['categories_failed'],
                            'timestamp': datetime.utcnow().isoformat()
                        }, f, indent=2)
                    logger.warning(f"Discovery results saved to: {discovery_file}")
                except Exception as e:
                    logger.error(f"Failed to save discovery results: {e}")
            else:
                logger.warning("❌ No new categories discovered")

            if self.stats['categories_failed']:
                logger.info("Failed routes:")
                for cat in self.stats['categories_failed']:
                    logger.info(f"  - {cat['category']}: {cat['route']}")

        if hasattr(self, 'crawler'):
            logger.warning(f"Scheduler stats: {self.crawler.stats.get_stats()}")

        logger.warning("=" * 80)
