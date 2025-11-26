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
                # Increased timeout from 15s to 30s for slow e-nabavki.gov.mk responses
                await page.wait_for_selector('table#notices-grid tbody tr', timeout=30000)
                await page.wait_for_timeout(2000)  # Extra wait for data binding
                logger.info(f"✓ Angular DataTable loaded successfully for category: {source_category}")
            except Exception as e:
                logger.error(f"Failed to wait for DataTable: {e}")

        logger.info(f"Parsing listing page ({source_category}): {response.url}")

        tender_links = []
        # For full historical scrape: ~109K awarded contracts / 10 per page = ~11K pages
        # Set high limit but with safety check for same-page detection
        max_pages_to_scrape = 15000  # Allow scraping all historical data

        # Prefer Playwright anchors to support dossie-acpp pages (contracts/awards)
        # Also handle pagination - collect links from multiple pages
        if page:
            current_page = 1
            consecutive_zero_new = 0  # Track consecutive pages with no new links
            last_link_count = 0

            while current_page <= max_pages_to_scrape:
                try:
                    # Extract links from current page
                    link_elems = await page.query_selector_all("a[href*='dossie']")
                    page_links = []
                    for elem in link_elems:
                        href = await elem.get_attribute('href')
                        if href and href not in tender_links:
                            page_links.append(href)
                            tender_links.append(href)

                    new_links_count = len(page_links)
                    logger.info(f"Page {current_page}: Found {new_links_count} new tender links (total: {len(tender_links)})")

                    # Safety check: if 3 consecutive pages have no new links, pagination is stuck
                    if new_links_count == 0:
                        consecutive_zero_new += 1
                        if consecutive_zero_new >= 3:
                            logger.warning(f"Pagination stuck: {consecutive_zero_new} consecutive pages with no new links")
                            break
                    else:
                        consecutive_zero_new = 0

                    # Check if we should go to next page
                    if current_page >= max_pages_to_scrape:
                        logger.info(f"Reached max pages limit ({max_pages_to_scrape})")
                        break

                    # Try to click Next button
                    has_next = await self._click_next_page(page)
                    if not has_next:
                        logger.info("No more pages available")
                        break

                    current_page += 1

                    # Log progress every 100 pages
                    if current_page % 100 == 0:
                        logger.warning(f"Progress: Page {current_page}, Total links: {len(tender_links)}")

                except Exception as e:
                    logger.warning(f"Error on page {current_page}: {e}")
                    break

        # Fallback to HTML selectors if no links found via Playwright
        if not tender_links:
            tender_links = response.css('table#notices-grid tbody tr td:first-child a[href*=\"/dossie/\"]::attr(href)').getall()

        if not tender_links:
            tender_links = response.css('table tbody tr td a[target=\"_blank\"]::attr(href)').getall()

        # Deduplicate
        tender_links = list(set(tender_links))

        self.stats['tenders_found'] += len(tender_links)
        logger.warning(f"✓ Total unique tender links found in {source_category}: {len(tender_links)}")

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

        # Pagination is now handled in the main loop above - all links collected before closing page
        logger.info("Pagination: All pages processed within single page context")

    async def _click_next_page(self, page) -> bool:
        """
        Click the Next button in pagination.
        Returns True if successfully clicked and page changed, False if no more pages.
        """
        try:
            # Get current page info BEFORE clicking
            old_page_info = ""
            try:
                info_elem = await page.query_selector('.dataTables_info, #notices-grid_info')
                if info_elem:
                    old_page_info = await info_elem.inner_text()
            except:
                pass

            # DataTables pagination selectors - try multiple approaches
            # The key insight: DataTables uses #tableid_next as the Next button ID
            next_selectors = [
                '#notices-grid_next',  # DataTables standard ID-based selector
                'a.paginate_button.next',  # Class-based selector
                '.dataTables_paginate .next',
                'a[data-dt-idx="next"]',
                'li.next a',
            ]

            for selector in next_selectors:
                try:
                    next_btn = await page.query_selector(selector)
                    if next_btn:
                        # Check if disabled
                        class_attr = await next_btn.get_attribute('class') or ''
                        if 'disabled' in class_attr:
                            logger.info(f"Next button disabled: {selector}")
                            continue

                        # Get position and scroll into view
                        await next_btn.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)

                        # Click using JavaScript for more reliable interaction
                        await page.evaluate('(el) => el.click()', next_btn)
                        logger.info(f"Clicked Next button via JS: {selector}")

                        # Wait for table to update - check for loading indicator or row change
                        await page.wait_for_timeout(3000)

                        # Verify page actually changed by checking pagination info
                        try:
                            new_info_elem = await page.query_selector('.dataTables_info, #notices-grid_info')
                            if new_info_elem:
                                new_page_info = await new_info_elem.inner_text()
                                if new_page_info != old_page_info:
                                    logger.info(f"Page changed: {old_page_info} -> {new_page_info}")
                                    return True
                                else:
                                    logger.warning(f"Page info unchanged after click: {new_page_info}")
                                    # Try clicking again with force
                                    continue
                        except:
                            pass

                        # Even if we can't verify, assume success if we clicked
                        return True

                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            # If no selector worked, try clicking page numbers directly
            try:
                # Find current page number and click next
                current_page_btn = await page.query_selector('.paginate_button.current')
                if current_page_btn:
                    current_text = await current_page_btn.inner_text()
                    current_num = int(current_text.strip())
                    next_num = current_num + 1

                    # Click on next page number
                    next_page_btn = await page.query_selector(f'.paginate_button:has-text("{next_num}")')
                    if next_page_btn:
                        await page.evaluate('(el) => el.click()', next_page_btn)
                        await page.wait_for_timeout(3000)
                        logger.info(f"Clicked page number {next_num}")
                        return True
            except Exception as e:
                logger.debug(f"Page number click failed: {e}")

            logger.info("No working Next button found or last page reached")
            return False
        except Exception as e:
            logger.warning(f"Error clicking next page: {e}")
            return False

    async def _handle_pagination(self, page, source_category: str) -> Optional[str]:
        """
        Handle pagination for the listing page.
        Clicks the "Next" button and returns the new page URL if available.
        Returns None if no more pages.
        """
        try:
            # Look for pagination info to see total pages
            page_info_selectors = [
                '.dataTables_info',
                '#notices-grid_info',
                '.pagination-info',
            ]

            for selector in page_info_selectors:
                try:
                    info_elem = await page.query_selector(selector)
                    if info_elem:
                        info_text = await info_elem.inner_text()
                        logger.info(f"Pagination info: {info_text}")
                        break
                except:
                    continue

            # Look for Next button in DataTables pagination
            next_selectors = [
                'a.paginate_button.next:not(.disabled)',
                'li.next:not(.disabled) a',
                'a:has-text("Следна"):not(.disabled)',
                'a:has-text("Next"):not(.disabled)',
                'button:has-text("Следна"):not([disabled])',
                '#notices-grid_next:not(.disabled)',
            ]

            for selector in next_selectors:
                try:
                    next_btn = await page.query_selector(selector)
                    if next_btn:
                        # Check if truly clickable (not disabled)
                        class_attr = await next_btn.get_attribute('class') or ''
                        if 'disabled' in class_attr:
                            logger.info(f"Next button found but disabled ({selector})")
                            continue

                        logger.info(f"Found Next button with selector: {selector}")

                        # Click and wait for table to refresh
                        await next_btn.click()
                        await page.wait_for_timeout(3000)  # Wait for data to load

                        # Try to wait for table refresh
                        try:
                            await page.wait_for_selector('table tbody tr', timeout=20000)
                        except:
                            pass

                        # Return current URL (will be re-parsed with new data)
                        current_url = page.url
                        logger.info(f"Clicked Next - new page loaded: {current_url}")
                        return current_url

                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            logger.info("No Next button found or all pages scraped")
            return None

        except Exception as e:
            logger.warning(f"Pagination handling error: {e}")
            return None

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
                        await page.wait_for_selector('table#notices-grid tbody tr', timeout=20000)

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
                # Increased timeout from 20s to 30s for slow pages
                await page.wait_for_selector('label.dosie-value', timeout=30000)
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
        tender['cpv_code'] = self._extract_cpv_code(response)
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

        # Extract additional bid data (highest/lowest bids)
        tender['highest_bid'] = self._extract_currency(response, 'highest_bid')
        tender['lowest_bid'] = self._extract_currency(response, 'lowest_bid')

        # Extract delivery location
        tender['delivery_location'] = self._extract_field(response, 'delivery_location')

        # Extract dossier_id (UUID) from URL
        # URL format: https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/UUID
        import re
        url = response.url
        dossier_match = re.search(r'/dossie-acpp/([a-f0-9-]{36})', url)
        if dossier_match:
            tender['dossier_id'] = dossier_match.group(1)
        else:
            tender['dossier_id'] = None

        # Extract number of bidders from page (NUMBER OF OFFERS DOSSIE shows actual count)
        num_bidders_str = self._extract_field(response, 'num_bidders')
        if num_bidders_str:
            try:
                tender['num_bidders'] = int(num_bidders_str.strip())
            except (ValueError, TypeError):
                tender['num_bidders'] = None

        # Extract has_lots from page
        has_lots_str = self._extract_field(response, 'has_lots')
        if has_lots_str:
            tender['has_lots'] = has_lots_str.lower() in ('да', 'yes', 'true')
        else:
            tender['has_lots'] = False

        # Extract bidders and lots data
        tender_id = tender.get('tender_id', 'unknown')
        bidders_list = self._extract_bidders(response, tender_id)
        lots_list = self._extract_lots(response, tender_id)

        # Set bidder and lot related fields
        tender['bidders_data'] = json.dumps(bidders_list, ensure_ascii=False) if bidders_list else None
        tender['lots_data'] = json.dumps(lots_list, ensure_ascii=False) if lots_list else None

        # Override num_bidders if we have a list (fallback)
        if tender.get('num_bidders') is None and bidders_list:
            tender['num_bidders'] = len(bidders_list)

        tender['num_lots'] = len(lots_list) if lots_list else 0

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
        Extract field using XPath label-for attribute selectors.

        CRITICAL: Scrapy CSS selectors don't support :contains() pseudo-selector.
        We use XPath with label[@label-for="..."] for reliable extraction.
        """
        # XPath selectors based on label-for attributes discovered from page analysis
        FIELD_XPATH = {
            'tender_id': [
                # For notifications/contracts
                '//label[@label-for="PROCESS NUMBER FOR NOTIFICATION DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # For active tenders
                '//label[@label-for="ANNOUNCEMENT NUMBER DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="NUMBER OF NOTICE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Fallback: look for pattern like 12345/2025 in any dosie-value
                '//label[contains(@class, "dosie-value")][contains(text(), "/202")]/text()',
            ],
            'title': [
                '//label[@label-for="SUBJECT:"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "SUBJECT")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'description': [
                # English label-for detailed description
                '//label[@label-for="DETAIL DESCRIPTION OF THE ITEM TO BE PROCURED DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="DESCRIPTION DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels - detailed description
                '//label[contains(text(), "Подетален опис")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Опис на предметот")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Детален опис")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels - subject of procurement (shorter)
                '//label[contains(text(), "Предмет на набавка")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Предмет на договорот")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Catch-all: any long text (>100 chars) in dosie-value that's likely a description
                '//label[contains(@class, "dosie-value") and string-length(text()) > 100]/text()',
            ],
            'procuring_entity': [
                '//label[@label-for="CONTRACTING INSTITUTION NAME DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="CONTRACTING AUTHORITY NAME DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels
                '//label[contains(text(), "Назив на договорниот орган")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Договорен орган")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'category': [
                '//label[@label-for="TYPE OF PROCUREMENT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="TYPE OF CONTRACT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'cpv_code': [
                # PRIMARY: Extract any 8-digit CPV code pattern from the page
                # Note: CPV codes are embedded in the page HTML, not always in labeled fields
                # This will be handled by _extract_cpv_code method
                '//label[@label-for="CPV CODE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "CPV")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian CPV labels
                '//label[contains(text(), "CPV код")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "CPV")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'procedure_type': [
                '//label[@label-for="TYPE OF CALL:"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PROCEDURE TYPE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'contracting_entity_category': [
                '//label[@label-for="CATEGORY OF CONTRACTING INSTITUTION AND ITS MAIN ROLE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'procurement_holder': [
                # This is actually the winner in awarded contracts
                '//label[@label-for="NAME OF CONTACT OF PROCUREMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'contract_duration': [
                '//label[@label-for="PERIOD IN MONTHS"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="CONTRACT DURATION DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'winner': [
                # Winner name (contractor who won the tender)
                '//label[@label-for="NAME OF CONTACT OF PROCUREMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="WINNER NAME DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="SELECTED BIDDER DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'contact_person': [
                '//label[@label-for="CONTRACTING INSTITUTION CONTACT PERSON DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="CONTACT PERSON DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'contact_email': [
                '//label[@label-for="CONTRACTING INSTITUTION EMAIL DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="EMAIL DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'contact_phone': [
                '//label[@label-for="CONTRACTING INSTITUTION PHONE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PHONE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'payment_terms': [
                # Primary: Various payment terms labels found on e-nabavki pages
                '//label[@label-for="PAYMENT TERMS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PAYMENT TERMS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="TERMS OF PAYMENT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="TERMS OF PAYMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PAYMENT DEADLINE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PAYMENT DEADLINE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PAYMENT PERIOD DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PAYMENT PERIOD DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels for payment terms
                '//label[contains(text(), "Услови за плаќање")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Рок за плаќање")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Плаќање")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # General contains for "PAYMENT" in label-for
                '//label[contains(@label-for, "PAYMENT")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'evaluation_method': [
                '//label[@label-for="CRITERION FOR ASSIGNMENT OF CONTRACT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="AWARD CRITERIA DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'delivery_location': [
                '//label[@label-for="DELIVERY OF GOODS LOCATION OF WORKS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'num_bidders': [
                '//label[@label-for="NUMBER OF OFFERS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'highest_bid': [
                '//label[@label-for="HIGEST OFFER VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'lowest_bid': [
                '//label[@label-for="LOWEST OFFER VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'has_lots': [
                '//label[@label-for="CAN BE DIVEDED ON LOTS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
        }

        xpaths = FIELD_XPATH.get(field_name, [])

        for xpath in xpaths:
            try:
                values = response.xpath(xpath).getall()
                for value in values:
                    if value:
                        value = value.strip()
                        if value and len(value) > 0:
                            logger.debug(f"Extracted {field_name}: {value[:50]}...")
                            return value
            except Exception as e:
                logger.debug(f"XPath error for {field_name}: {e}")
                continue

        return None

    def _extract_cpv_code(self, response: Response) -> Optional[str]:
        """
        Extract CPV code using regex pattern matching on the entire page.
        CPV codes are 8-digit numbers, optionally followed by -digit (e.g., 72410000-7)
        """
        # First try labeled extraction
        cpv_xpaths = [
            '//label[@label-for="CPV CODE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            '//label[contains(@label-for, "CPV")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            '//label[contains(text(), "CPV код")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            '//label[contains(text(), "CPV")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
        ]

        for xpath in cpv_xpaths:
            try:
                values = response.xpath(xpath).getall()
                for value in values:
                    if value:
                        value = value.strip()
                        # Check if it's a valid CPV code pattern
                        cpv_match = re.match(r'^(\d{8})(-\d)?$', value)
                        if cpv_match:
                            logger.info(f"Extracted CPV code via label: {value}")
                            return value
            except Exception:
                continue

        # Fallback: Search entire HTML for CPV pattern
        # CPV codes are 8-digit codes, optionally with -digit suffix
        html_text = response.text

        # Find all 8-digit patterns with optional -digit suffix
        cpv_pattern = r'\b(\d{8}(?:-\d)?)\b'
        matches = re.findall(cpv_pattern, html_text)

        # Filter out common false positives
        valid_cpv_codes = []
        for match in matches:
            # CPV codes start with specific prefixes (not 00000000 or 99999999)
            if match.startswith('0000') or match.startswith('9999'):
                continue
            # Valid CPV division codes are 01-98
            try:
                division = int(match[:2])
                if 1 <= division <= 98:
                    valid_cpv_codes.append(match)
            except ValueError:
                continue

        if valid_cpv_codes:
            # Return the first valid CPV code found
            cpv_code = valid_cpv_codes[0]
            logger.info(f"Extracted CPV code via regex: {cpv_code}")
            return cpv_code

        return None

    def _extract_date(self, response: Response, field_name: str) -> Optional[str]:
        """Extract and parse date fields using XPath selectors"""
        # XPath selectors based on label-for attributes
        DATE_XPATH = {
            'publication_date': [
                '//label[@label-for="ANNOUNCEMENT DATE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PUBLICATION DATE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'opening_date': [
                # PRIMARY: Exact label-for from live page analysis (active tenders)
                '//label[@label-for="PUBLIC OPENING OF THE TENDERS WILL BE HELD ON THE DAY AND HOUR DEFINED AS THE DEAD LINE FOR THEIR DELIVERY DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Alternate English label-for values
                '//label[@label-for="OPENING DATE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="BID OPENING DATE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="DATE OF OPENING OFFERS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # For awarded tenders - use contract signing date as proxy for opening
                '//label[@label-for="DATE WHEN CONTRACT WAS ASSIGNED DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian text-based search
                '//label[contains(text(), "Јавното отворање на понудите")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Отворање на понуди")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Датум на отворање")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'closing_date': [
                # PRIMARY: Exact label-for from live page inspection (Nov 2025)
                # "THE REQUEST FOR PARTICIPATION TO BE DELIVERED UNTIL DOSSIE" is the submission deadline
                '//label[@label-for="THE REQUEST FOR PARTICIPATION TO BE DELIVERED UNTIL DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Alternate: Some pages use this variant
                '//label[@label-for="THE TENDERS TO BE DELIVERED AT LEAST UNTIL"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="DEADLINE FOR QUESTIONING DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="SUBMISSION DEADLINE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="DEADLINE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian text-based fallbacks
                '//label[contains(text(), "Краен рок за поставување прашања")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Крајниот рок за доставување")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Рок за поднесување")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Крајниот рок")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'contract_signing_date': [
                '//label[@label-for="DATE WHEN CONTRACT WAS ASSIGNED DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="CONTRACT SIGNING DATE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'bureau_delivery_date': [
                '//label[@label-for="DATE OF DELIVERY DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="DELIVERY DATE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
        }

        xpaths = DATE_XPATH.get(field_name, [])

        for xpath in xpaths:
            try:
                values = response.xpath(xpath).getall()
                for date_str in values:
                    if date_str:
                        date_str = date_str.strip()
                        parsed = self._parse_date(date_str)
                        if parsed:
                            logger.debug(f"Extracted {field_name}: {parsed}")
                            return parsed
            except Exception as e:
                logger.debug(f"XPath error for {field_name}: {e}")
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

        The e-nabavki site structure (from page analysis):
        - Estimated value: label-for="ESTIMATED VALUE NEW" => "1.000.000,44"
        - Contract value without VAT: label-for="ASSIGNED CONTRACT VALUE WITHOUT VAT" => "507.000,00"
        - Contract value with VAT: label-for="ASSIGNED CONTRACT VALUE DOSSIE" => "598.260,00"
        """
        # XPath selectors based on actual label-for attributes discovered
        CURRENCY_XPATH = {
            'estimated_value_mkd': [
                # Primary: "ESTIMATED VALUE NEW" from page analysis
                '//label[@label-for="ESTIMATED VALUE NEW"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="ESTIMATED VALUE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="ESTIMATED VALUE NO DDV"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="ESTIMATED VALUE WITHOUT VAT"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels for estimated value
                '//label[contains(text(), "Проценета вредност")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Предвидена вредност")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Вредност без ДДВ")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Broad English pattern
                '//label[contains(@label-for, "ESTIMATED VALUE")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'estimated_value_eur': [
                # EUR is usually marked or second value
                '//label[@label-for="ESTIMATED VALUE EUR"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "ESTIMATED VALUE")]/following-sibling::label[contains(@class, "dosie-value")][contains(text(), "EUR")]/text()',
            ],
            'actual_value_mkd': [
                # Contract value without VAT (this is the winning bid)
                '//label[@label-for="ASSIGNED CONTRACT VALUE WITHOUT VAT"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Contract value with VAT
                '//label[@label-for="ASSIGNED CONTRACT VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "CONTRACT VALUE")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'actual_value_eur': [
                '//label[@label-for="ASSIGNED CONTRACT VALUE EUR"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "CONTRACT VALUE")]/following-sibling::label[contains(@class, "dosie-value")][contains(text(), "EUR")]/text()',
            ],
            'security_deposit_mkd': [
                # Изјава за сериозност (Bid guarantee / Security deposit)
                '//label[@label-for="IMPORTANCE STATEMENT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="SECURITY DEPOSIT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="BID GUARANTEE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'performance_guarantee_mkd': [
                # Гаранција за квалитетно извршување на договорот (Performance guarantee)
                '//label[@label-for="ASSURANCE OF QUALITY EXECUTION OF AGREEMENT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PERFORMANCE GUARANTEE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'highest_bid': [
                '//label[@label-for="HIGEST OFFER VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="HIGHEST OFFER VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Највисока понуда")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'lowest_bid': [
                '//label[@label-for="LOWEST OFFER VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Најниска понуда")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
        }

        xpaths = CURRENCY_XPATH.get(field_name, [])

        for xpath in xpaths:
            try:
                values = response.xpath(xpath).getall()
                for value_str in values:
                    if value_str:
                        value_str = value_str.strip()
                        # For guarantee fields, extract percentage from brackets like "[15.00 %]"
                        if field_name in ('security_deposit_mkd', 'performance_guarantee_mkd'):
                            parsed = self._parse_guarantee_percentage(value_str)
                            if parsed:
                                logger.info(f"Extracted {field_name}: {parsed}% from '{value_str}'")
                                return parsed
                            continue
                        # Skip "Не" or "Да" values (these are yes/no indicators)
                        if value_str in ('Не', 'Да', 'No', 'Yes', '%'):
                            continue
                        parsed = self._parse_currency(value_str)
                        if parsed:
                            logger.info(f"Extracted {field_name}: {parsed} from '{value_str}'")
                            return parsed
            except Exception as e:
                logger.debug(f"XPath error for {field_name}: {e}")
                continue

        return None

    def _parse_guarantee_percentage(self, value_string: str) -> Optional[Decimal]:
        """
        Extract percentage value from guarantee field text.
        Examples:
        - "Да [15.00 %]" -> 15.00
        - "Да [5.00 %]" -> 5.00
        - "Не" -> None
        """
        if not value_string:
            return None

        # Look for percentage pattern in brackets: [15.00 %] or [5.00%]
        percentage_match = re.search(r'\[(\d+(?:[.,]\d+)?)\s*%?\]', value_string)
        if percentage_match:
            try:
                number_str = percentage_match.group(1).replace(',', '.')
                return Decimal(number_str)
            except:
                pass

        # Also try pattern without brackets: "15.00 %" or "15,00%"
        percentage_match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', value_string)
        if percentage_match:
            try:
                number_str = percentage_match.group(1).replace(',', '.')
                return Decimal(number_str)
            except:
                pass

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
        seen_urls = set()  # Dedupe

        # XPath selectors for document links - more comprehensive
        doc_xpaths = [
            '//a[contains(@href, "Download")]/@href',
            '//a[contains(@href, ".pdf")]/@href',
            '//a[contains(@href, "/File/")]/@href',
            '//a[contains(@href, "/Bids/")]/@href',
            '//a[contains(@href, "fileId=")]/@href',
            '//a[contains(@href, "document")]/@href',
            '//a[contains(@href, ".docx")]/@href',
            '//a[contains(@href, ".xlsx")]/@href',
        ]

        doc_selectors = [
            'a[href*="Download"]::attr(href)',
            'a[href*=".pdf"]::attr(href)',
            'a[href*="File"]::attr(href)',
            'a[href*="Bids"]::attr(href)',
            'a[href*="fileId"]::attr(href)',
        ]

        def add_document(link):
            """Helper to add document after validation"""
            if not link or link in seen_urls:
                return
            seen_urls.add(link)

            # Make absolute URL
            if link.startswith('/'):
                link = 'https://e-nabavki.gov.mk' + link
            elif not link.startswith('http'):
                link = 'https://e-nabavki.gov.mk/' + link

            # Filter out external URLs (only keep e-nabavki.gov.mk documents)
            # Skip bank guarantee PDFs and other external links
            if 'e-nabavki.gov.mk' not in link:
                logger.debug(f"Skipping external document URL: {link}")
                return

            # Extract filename from URL
            import urllib.parse
            parsed = urllib.parse.urlparse(link)
            if 'fileId=' in link:
                # For fileId URLs, generate filename from fileId
                file_id = urllib.parse.parse_qs(parsed.query).get('fileId', ['unknown'])[0]
                filename = f"document_{file_id[:8]}.pdf"
            else:
                filename = urllib.parse.unquote(parsed.path.split('/')[-1]) if '/' in parsed.path else 'document.pdf'

            # Clean up filename
            filename = filename.replace('%20', ' ').replace('%', '_')

            doc_type = 'document'
            doc_category = self._categorize_document(filename, doc_type)

            documents.append({
                'url': link,
                'tender_id': tender_id,
                'doc_category': doc_category,
                'upload_date': None,
                'file_name': filename,
                'doc_type': doc_type,
            })

        # Try CSS selectors first
        for selector in doc_selectors:
            links = response.css(selector).getall()
            for link in links:
                add_document(link)

        # Also try XPath selectors
        for xpath in doc_xpaths:
            links = response.xpath(xpath).getall()
            for link in links:
                add_document(link)

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
        """
        Auto-detect tender status from available fields.

        IMPORTANT: Status must match DB constraint:
        CHECK (status IN ('open', 'closed', 'awarded', 'cancelled'))
        """
        source_category = tender.get('source_category', '')

        # Handle awarded tenders
        if source_category in ('awarded', 'contracts', 'tender_winners'):
            return 'awarded'
        if tender.get('winner'):
            return 'awarded'

        # Handle cancelled tenders
        if 'cancel' in source_category.lower():
            return 'cancelled'

        # Handle active/open tenders
        # Default to 'open' for active tenders (NOT 'active' or 'published')
        closing_date = tender.get('closing_date')
        if closing_date:
            # Check if past closing date
            try:
                from datetime import datetime
                close_dt = datetime.strptime(closing_date, '%Y-%m-%d')
                if close_dt < datetime.now():
                    return 'closed'
            except:
                pass

        # Default status for active tenders
        return 'open'

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
