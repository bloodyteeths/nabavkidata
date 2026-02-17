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
        "DOWNLOAD_DELAY": 0.1,
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 4,
        "PLAYWRIGHT_MAX_CONTEXTS": 2,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        "DUPEFILTER_CLASS": "scrapy.dupefilters.BaseDupeFilter",
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 0.1,
        "AUTOTHROTTLE_MAX_DELAY": 0.5,
    }

    def __init__(self, category='active', mode='scrape', year=None, start_page=1,
                 max_listing_pages=None, reverse=False, year_filter=None,
                 date_from=None, date_to=None, force_full_scan=False, *args, **kwargs):
        """
        Initialize spider with category, mode, and pagination parameters.

        Args:
            category: One of 'active', 'awarded', 'cancelled', 'historical', 'all'
            mode: 'scrape' (default), 'discover' (probe URLs), 'incremental' (only new/changed),
                  or 'full' (alias for scrape)
            year: Archive year to scrape (2008-2021). If None or 'current', uses current period.
            start_page: Starting page number for pagination (default: 1)
            max_listing_pages: Maximum listing pages to scrape (default: None = unlimited)
            reverse: If True, paginate in reverse order (last page first)
            year_filter: Filter to only save tenders from specific years.
                        Format: "2024" (single year), "2022-2024" (range), or "2022,2023,2024" (list)
                        Tenders outside this range will be skipped after extraction.
            date_from: Start date for server-side filtering (format: YYYY-MM-DD).
                      Works with archive years to target specific date ranges.
            date_to: End date for server-side filtering (format: YYYY-MM-DD).
            force_full_scan: If True, continue pagination through ALL pages even when hitting
                            duplicate links. Use for historical backfills to ensure complete data.
        """
        super().__init__(*args, **kwargs)
        self.category = category.lower()
        self.mode = mode.lower()

        # Parse year parameter (for archive selection)
        if year is None or str(year).lower() in ('none', 'current', ''):
            self.year = None  # Current period
        else:
            self.year = int(year)

        # Parse year_filter parameter (for filtering extracted tenders)
        self.year_filter = self._parse_year_filter(year_filter)

        # Parse date_from and date_to for server-side date filtering
        self.date_from = self._parse_date(date_from)
        self.date_to = self._parse_date(date_to)

        # Force full scan - continue through ALL pages even with duplicates
        self.force_full_scan = str(force_full_scan).lower() in ('true', '1', 'yes')

        # Pagination parameters
        self.start_page = int(start_page)
        self.max_listing_pages = int(max_listing_pages) if max_listing_pages else None

        # Table ID for DataTable - will be detected dynamically
        # Different pages use different table IDs:
        # - notices-grid: for public notices/tenders
        # - contracts-grid: for contracts/awarded
        self.table_id = None
        self.reverse = str(reverse).lower() in ('true', '1', 'yes')

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

        # Log parameters
        date_info = f", date_from={self.date_from}, date_to={self.date_to}" if self.date_from or self.date_to else ""
        full_scan_info = ", force_full_scan=True" if self.force_full_scan else ""
        logger.warning(f"Spider initialized: category={self.category}, year={self.year}, "
                      f"start_page={self.start_page}, max_listing_pages={self.max_listing_pages}, "
                      f"reverse={self.reverse}, year_filter={self.year_filter}{date_info}{full_scan_info}")

    def _parse_year_filter(self, year_filter):
        """
        Parse year_filter parameter into a set of years to include.

        Args:
            year_filter: String like "2024", "2022-2024", or "2022,2023,2024"

        Returns:
            Set of years to include, or None if no filter
        """
        if not year_filter or str(year_filter).lower() in ('none', ''):
            return None

        years = set()
        year_filter = str(year_filter).strip()

        # Handle range format: "2022-2024"
        if '-' in year_filter and ',' not in year_filter:
            parts = year_filter.split('-')
            if len(parts) == 2:
                try:
                    start_year = int(parts[0].strip())
                    end_year = int(parts[1].strip())
                    years = set(range(start_year, end_year + 1))
                except ValueError:
                    logger.warning(f"Invalid year_filter range: {year_filter}")
                    return None

        # Handle comma-separated format: "2022,2023,2024"
        elif ',' in year_filter:
            for part in year_filter.split(','):
                try:
                    years.add(int(part.strip()))
                except ValueError:
                    pass

        # Handle single year: "2024"
        else:
            try:
                years.add(int(year_filter))
            except ValueError:
                logger.warning(f"Invalid year_filter: {year_filter}")
                return None

        if years:
            logger.info(f"Year filter active: will only save tenders from years {sorted(years)}")
            return years
        return None

    def _parse_date(self, date_str):
        """
        Parse date string into a date object.

        Args:
            date_str: Date string in YYYY-MM-DD format, or None

        Returns:
            datetime.date object, or None if invalid/empty
        """
        if not date_str or str(date_str).lower() in ('none', ''):
            return None

        try:
            from datetime import datetime as dt
            # Support multiple formats
            date_str = str(date_str).strip()
            for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
                try:
                    parsed = dt.strptime(date_str, fmt).date()
                    logger.info(f"Parsed date '{date_str}' -> {parsed} (type: {type(parsed).__name__})")
                    return parsed
                except ValueError:
                    continue
            logger.warning(f"Invalid date format: {date_str} (use YYYY-MM-DD)")
            return None
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None

    def _tender_passes_year_filter(self, tender):
        """
        Check if a tender passes the year filter.

        Args:
            tender: Tender dict with publication_date or opening_date

        Returns:
            True if tender should be saved, False if it should be skipped
        """
        if not self.year_filter:
            return True  # No filter, save all

        # Try to get year from various date fields
        tender_year = None

        for date_field in ['publication_date', 'opening_date', 'closing_date', 'contract_signing_date']:
            date_val = tender.get(date_field)
            if date_val:
                try:
                    if hasattr(date_val, 'year'):
                        tender_year = date_val.year
                    elif isinstance(date_val, str) and len(date_val) >= 4:
                        # Try to extract year from date string
                        import re
                        year_match = re.search(r'20[0-2][0-9]', date_val)
                        if year_match:
                            tender_year = int(year_match.group())
                    if tender_year:
                        break
                except Exception:
                    pass

        if tender_year is None:
            # If we can't determine year, let it through (better to include than exclude)
            logger.debug(f"Could not determine year for tender {tender.get('tender_id')}, including it")
            return True

        passes = tender_year in self.year_filter
        if not passes:
            logger.debug(f"Skipping tender {tender.get('tender_id')} - year {tender_year} not in filter {self.year_filter}")
        return passes

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
                                    'wait_until': 'domcontentloaded',
                                    'timeout': 20000,
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
                                'wait_until': 'domcontentloaded',
                                'timeout': 20000,
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
                            'wait_until': 'domcontentloaded',
                            'timeout': 20000,
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
                await page.wait_for_timeout(500)

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
                    except Exception as e:
                        logger.error(f"Error checking selector {selector} during discovery: {e}")
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
                except Exception as e:
                    logger.error(f"Error closing discovery page: {e}")

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

        Supports:
        - year: Archive year selection (2008-2021)
        - start_page: Start pagination from specific page
        - max_listing_pages: Limit number of pages to scrape
        - reverse: Paginate in reverse order (last page first)
        """
        page = response.meta.get('playwright_page')
        source_category = response.meta.get('category', 'active')

        if page:
            try:
                # Wait for Angular DataTable to load - try both common table IDs
                # contracts-grid is used for awarded/contracts pages
                # notices-grid is used for public notices pages
                try:
                    await page.wait_for_selector('table.dataTable tbody tr', timeout=30000)
                except Exception as e:
                    logger.error(f"Error waiting for DataTable generic selector, trying specific selectors: {e}")
                    await page.wait_for_selector('table#contracts-grid tbody tr, table#notices-grid tbody tr', timeout=15000)
                await page.wait_for_timeout(500)  # Extra wait for data binding

                # Detect the actual table ID being used
                await self._detect_table_id(page)
                logger.info(f"✓ Angular DataTable loaded successfully for category: {source_category} (table: {self.table_id})")
            except Exception as e:
                logger.error(f"Failed to wait for DataTable: {e}")

            # STEP 1: Select archive year if specified (2008-2021)
            if self.year and 2008 <= self.year <= 2021:
                logger.warning(f"Selecting archive year {self.year}...")
                year_selected = await self._select_archive_year(page, self.year)
                if not year_selected:
                    logger.error(f"FAILED to select archive year {self.year} - aborting scrape")
                    await page.close()
                    return
                logger.warning(f"✓ Archive year {self.year} selected successfully")

            # STEP 1b: Apply date filter if date_from/date_to or year_filter is set
            # This filters at server level - MUCH faster than scanning through pages
            # date_from/date_to work WITH archive years to target specific date ranges
            if self.date_from or self.date_to:
                # Use explicit date range (works with archive years too)
                logger.warning(f"Applying server-side date filter: {self.date_from} to {self.date_to}...")
                filter_applied = await self._apply_date_range_filter(page, self.date_from, self.date_to)
                if not filter_applied:
                    logger.warning("Date filter may not have applied - continuing anyway")
            elif self.year_filter and not self.year:  # year_filter only for current period (not archives)
                years = sorted(self.year_filter)
                year_start = min(years)
                year_end = max(years)
                logger.warning(f"Applying server-side date filter for years {year_start}-{year_end}...")
                filter_applied = await self._apply_date_filter(page, year_start, year_end)
                if not filter_applied:
                    logger.warning("Date filter may not have applied - continuing anyway")

        logger.info(f"Parsing listing page ({source_category}): {response.url}")

        tender_links = []
        # Use max_listing_pages parameter if set, otherwise use high default
        max_pages_to_scrape = self.max_listing_pages if self.max_listing_pages else 15000

        # Prefer Playwright anchors to support dossie-acpp pages (contracts/awards)
        # Also handle pagination - collect links from multiple pages
        if page:
            # STEP 2: Handle reverse pagination
            if self.reverse:
                logger.warning("Reverse pagination mode: navigating to last page...")
                await self._go_to_last_page(page)
                await page.wait_for_timeout(1000)

            # STEP 3: Navigate to start_page if greater than 1 (and not reverse mode)
            elif self.start_page > 1:
                logger.warning(f"Navigating to start page {self.start_page}...")
                await self._go_to_page(page, self.start_page)
                await page.wait_for_timeout(1000)

            current_page = 1  # Counter for pages scraped (not absolute page number)
            consecutive_zero_new = 0  # Track consecutive pages with no new links
            last_link_count = 0

            skipped_by_year_filter = 0

            archive_recovery_attempts = 0
            max_archive_recoveries = 5  # Maximum times to try recovering from table corruption
            last_successful_page = 0

            while current_page <= max_pages_to_scrape:
                try:
                    # Check if table has become empty (filter state lost - archive year OR date filter)
                    table_info = await page.evaluate(
                        "() => document.querySelector('.dataTables_info')?.innerText || ''"
                    )
                    if 'од вкупно 0 записи' in table_info or 'of 0 entries' in table_info.lower():
                        archive_recovery_attempts += 1
                        if archive_recovery_attempts > max_archive_recoveries:
                            logger.error(f"Filter state lost too many times ({archive_recovery_attempts}), stopping")
                            break

                        filter_type = "archive year" if self.year else "date filter" if self.year_filter else "unknown"
                        logger.warning(f"Filter state lost ({filter_type}, showing 0 records), attempting recovery #{archive_recovery_attempts}...")

                        # Re-navigate to page
                        await page.goto(response.url, wait_until='networkidle', timeout=60000)
                        await page.wait_for_timeout(3000)
                        await self._detect_table_id(page)

                        # Re-apply the appropriate filter
                        if self.year:
                            # Archive year recovery
                            year_selected = await self._select_archive_year(page, self.year)
                            if not year_selected:
                                logger.error(f"Failed to re-select archive year {self.year}")
                                break
                            logger.warning(f"✓ Archive year {self.year} recovered")
                        elif self.year_filter:
                            # Date filter recovery
                            years = sorted(self.year_filter)
                            year_start = min(years)
                            year_end = max(years)
                            filter_applied = await self._apply_date_filter(page, year_start, year_end)
                            if not filter_applied:
                                logger.error(f"Failed to re-apply date filter {year_start}-{year_end}")
                                break
                            logger.warning(f"✓ Date filter {year_start}-{year_end} recovered")
                        elif self.date_from or self.date_to:
                            # Explicit date range recovery
                            filter_applied = await self._apply_date_range_filter(page, self.date_from, self.date_to)
                            if not filter_applied:
                                logger.error(f"Failed to re-apply date range filter")
                                break
                            logger.warning(f"✓ Date range filter recovered")

                        # Jump to last successful page
                        if last_successful_page > 1:
                            logger.info(f"Jumping back to page {last_successful_page}...")
                            await self._go_to_page(page, last_successful_page)
                            await page.wait_for_timeout(2000)

                        logger.warning(f"✓ Filter recovered, continuing from page {last_successful_page}")
                        continue  # Retry current page

                    # Extract links from current page
                    link_elems = await page.query_selector_all("a[href*='dossie']")
                    page_links = []
                    page_skipped = 0
                    links_found_on_page = 0  # Track total links found (before filtering)
                    for elem in link_elems:
                        href = await elem.get_attribute('href')
                        if href and href not in tender_links:
                            links_found_on_page += 1  # Count new links before filtering
                            # OPTIMIZATION: If year_filter is set, check tender_id year from link text
                            # Link text format: "19810/2025" - we can filter BEFORE visiting detail page
                            if self.year_filter:
                                link_text = await elem.inner_text()
                                # Extract year from tender_id (e.g., "19810/2025" -> 2025)
                                import re
                                year_match = re.search(r'/(\d{4})$', link_text.strip())
                                if year_match:
                                    tender_year = int(year_match.group(1))
                                    if tender_year not in self.year_filter:
                                        page_skipped += 1
                                        skipped_by_year_filter += 1
                                        continue  # Skip this tender - wrong year

                            # Add to both lists (after year filter passes or if no filter)
                            page_links.append(href)
                            tender_links.append(href)  # Track for deduplication

                    new_links_count = len(page_links)
                    year_info = f" (year={self.year})" if self.year else ""
                    filter_info = f", skipped {page_skipped} (year filter)" if page_skipped > 0 else ""
                    logger.info(f"Page {current_page}{year_info}: Found {new_links_count} new tender links (total: {len(tender_links)}){filter_info}")

                    # INCREMENTAL PROCESSING: Yield requests immediately for this page's links
                    # This prevents losing progress if scraper crashes - each page's tenders are queued immediately
                    for link in page_links:
                        # Construct absolute URL
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
                                    'timeout': 20000,
                                },
                                'source_category': source_category,
                            },
                            errback=self.errback_playwright,
                            dont_filter=True
                        )

                    # Track last page with successful link extraction (for archive recovery)
                    if links_found_on_page > 0 or new_links_count > 0:
                        last_successful_page = current_page
                        archive_recovery_attempts = 0  # Reset recovery counter on success

                    # Safety check: if 3 consecutive pages have no new links BEFORE filtering, pagination is stuck
                    # NOTE: We check links_found_on_page (before year filter) not new_links_count (after filter)
                    # This allows scraper to continue through pages of filtered-out tenders
                    # SKIP this check if force_full_scan is enabled (for historical backfills)
                    if links_found_on_page == 0:
                        consecutive_zero_new += 1
                        if consecutive_zero_new >= 3 and not self.force_full_scan:
                            logger.warning(f"Pagination stuck: {consecutive_zero_new} consecutive pages with no new links")
                            break
                        elif consecutive_zero_new >= 3 and self.force_full_scan:
                            logger.info(f"Force full scan: continuing despite {consecutive_zero_new} pages with no new links")
                    else:
                        consecutive_zero_new = 0

                    # Check if we should go to next page
                    if current_page >= max_pages_to_scrape:
                        logger.info(f"Reached max pages limit ({max_pages_to_scrape})")
                        break

                    # Navigate to next/previous page based on mode
                    if self.reverse:
                        has_more = await self._click_previous_page(page)
                    else:
                        has_more = await self._click_next_page(page)

                    if not has_more:
                        logger.info("No more pages available")
                        break

                    current_page += 1

                    # Log progress every 50 pages
                    if current_page % 50 == 0:
                        logger.warning(f"Progress: Page {current_page}/{max_pages_to_scrape}, Total links: {len(tender_links)}{year_info}")

                except Exception as e:
                    logger.warning(f"Error on page {current_page}: {e}")
                    # Close Playwright page before breaking to prevent page leak
                    try:
                        await page.close()
                        page = None  # Prevent double-close in cleanup below
                    except Exception as close_err:
                        logger.error(f"Error closing page after pagination error: {close_err}")
                    break

        # Fallback to HTML selectors if no links found via Playwright
        # (Links are now yielded inline, but we still need fallback for non-Playwright mode)
        if not tender_links:
            fallback_links = response.css('table#notices-grid tbody tr td:first-child a[href*=\"/dossie/\"]::attr(href)').getall()
            if not fallback_links:
                fallback_links = response.css('table tbody tr td a[target=\"_blank\"]::attr(href)').getall()

            # Yield fallback links (only if Playwright didn't find any)
            for link in fallback_links:
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
                            'timeout': 20000,
                        },
                        'source_category': source_category,
                    },
                    errback=self.errback_playwright,
                    dont_filter=True
                )
            tender_links = fallback_links

        self.stats['tenders_found'] += len(tender_links)
        logger.warning(f"✓ Total unique tender links found in {source_category}: {len(tender_links)} (yielded incrementally)")

        # CRITICAL: Close listing page's Playwright page to free up context for detail pages
        if page:
            try:
                await page.close()
                logger.info("✓ Closed listing page Playwright context")
            except Exception as e:
                logger.warning(f"Failed to close listing page: {e}")

        logger.info("✓ Pagination complete - tenders yielded incrementally per-page")

    async def _detect_table_id(self, page) -> str:
        """
        Detect the DataTable's table ID dynamically.
        Different pages use different table IDs:
        - notices-grid: for public notices/tenders
        - contracts-grid: for contracts/awarded

        Returns:
            The detected table ID, or 'notices-grid' as fallback
        """
        if self.table_id:
            return self.table_id

        try:
            # Try to find the DataTable by looking for common table IDs
            table_ids = ['notices-grid', 'contracts-grid', 'DataTables_Table_0']

            for table_id in table_ids:
                has_table = await page.evaluate(f'''() => {{
                    var table = document.getElementById('{table_id}');
                    return table && table.classList.contains('dataTable');
                }}''')
                if has_table:
                    self.table_id = table_id
                    logger.info(f"Detected DataTable ID: {table_id}")
                    return table_id

            # Fallback: find any table with dataTable class
            detected = await page.evaluate('''() => {
                var tables = document.querySelectorAll('table.dataTable');
                if (tables.length > 0 && tables[0].id) {
                    return tables[0].id;
                }
                return null;
            }''')

            if detected:
                self.table_id = detected
                logger.info(f"Detected DataTable ID via class: {detected}")
                return detected

            # Default fallback
            self.table_id = 'notices-grid'
            logger.warning("Could not detect table ID, using default: notices-grid")
            return self.table_id

        except Exception as e:
            logger.warning(f"Error detecting table ID: {e}, using default: notices-grid")
            self.table_id = 'notices-grid'
            return self.table_id

    def _get_table_selector(self, suffix: str = '') -> str:
        """Get the correct selector for the DataTable elements."""
        table_id = self.table_id or 'notices-grid'
        if suffix:
            return f'#{table_id}_{suffix}'
        return f'#{table_id}'

    async def _click_next_page(self, page) -> bool:
        """
        Click the Next button in pagination.
        Returns True if successfully clicked and page changed, False if no more pages.
        """
        try:
            # Make sure we have the table ID
            if not self.table_id:
                await self._detect_table_id(page)

            # Get current page info BEFORE clicking
            old_page_info = ""
            info_selector = f'.dataTables_info, {self._get_table_selector("info")}'
            try:
                info_elem = await page.query_selector(info_selector)
                if info_elem:
                    old_page_info = await info_elem.inner_text()
            except Exception as e:
                logger.error(f"Error reading current page info before pagination: {e}")

            # DataTables pagination selectors - try multiple approaches
            # The key insight: DataTables uses #tableid_next as the Next button ID
            # Use dynamic table ID to build selectors
            next_selectors = [
                self._get_table_selector('next'),  # DataTables standard ID-based selector (e.g., #contracts-grid_next)
                'a.paginate_button.next',  # Class-based selector
                '.dataTables_paginate .next',
                'a[data-dt-idx="next"]',
                'li.next a',
            ]

            # Retry entire process up to 3 times if page doesn't change
            for retry_attempt in range(3):
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

                            # Wait for table to update - longer wait for archive mode
                            # Archive year queries may take longer to fetch data
                            wait_time = 3000 if self.year else 2000  # Longer wait for archive years
                            await page.wait_for_timeout(wait_time)

                            # Verify page actually changed by checking pagination info
                            try:
                                new_info_elem = await page.query_selector(info_selector)
                                if new_info_elem:
                                    new_page_info = await new_info_elem.inner_text()
                                    if new_page_info != old_page_info:
                                        logger.info(f"Page changed: {old_page_info} -> {new_page_info}")
                                        return True
                                    else:
                                        # Wait a bit longer and check again (archive mode can be slow)
                                        await page.wait_for_timeout(2000)
                                        new_page_info = await new_info_elem.inner_text()
                                        if new_page_info != old_page_info:
                                            logger.info(f"Page changed (after retry): {old_page_info} -> {new_page_info}")
                                            return True
                                        logger.warning(f"Page info unchanged after click: {new_page_info}")
                                        continue
                            except Exception as e:
                                logger.error(f"Error verifying page change after Next click: {e}")

                            # Even if we can't verify, assume success if we clicked
                            return True

                    except Exception as e:
                        logger.debug(f"Selector {selector} failed: {e}")
                        continue

                # If all selectors failed, wait before retry
                if retry_attempt < 2:
                    logger.warning(f"All pagination selectors failed, retry {retry_attempt + 1}/3...")
                    await page.wait_for_timeout(3000)

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
                        await page.wait_for_timeout(2000)
                        logger.info(f"Clicked page number {next_num}")
                        return True
            except Exception as e:
                logger.debug(f"Page number click failed: {e}")

            logger.info("No working Next button found or last page reached")
            return False
        except Exception as e:
            logger.warning(f"Error clicking next page: {e}")
            return False

    async def _select_archive_year(self, page, year: int) -> bool:
        """
        Select an archive year (2008-2021) using the archive year selector modal.
        Uses JavaScript click to bypass modal overlay interception.

        Args:
            page: Playwright page object
            year: Year to select (2008-2021)

        Returns:
            True if year was successfully selected, False otherwise
        """
        logger.info(f"Selecting archive year: {year}")

        try:
            # Step 1: Wait for and click the archive button
            archive_btn_selector = 'a[ng-controller="archiveYearController"]'
            try:
                await page.wait_for_selector(archive_btn_selector, timeout=15000)
            except Exception as e:
                logger.error(f"Archive button not found: {e}")
                return False

            archive_btn = await page.query_selector(archive_btn_selector)
            if not archive_btn:
                logger.error("Archive button selector returned None")
                return False

            await archive_btn.click()
            logger.info("Clicked archive button")

            # Step 2: Wait for modal to appear
            await page.wait_for_timeout(2000)  # Wait for modal animation
            modal_check = await page.query_selector('.modal-dialog, .modal-content, .modal-body')
            if not modal_check:
                logger.error("Archive modal did not appear")
                return False

            logger.info("Archive modal opened")

            # Step 3: Select year using JavaScript (bypasses overlay interception)
            js_select_year = f"""
            () => {{
                // Method 1: Find by label text and click associated radio button
                const labels = document.querySelectorAll('.modal label, .modal-body label');
                for (const label of labels) {{
                    if (label.textContent.trim() === '{year}') {{
                        // Try to find input radio inside or before the label
                        const radio = label.querySelector('input[type="radio"]') ||
                                      label.previousElementSibling;
                        if (radio && radio.type === 'radio') {{
                            radio.click();
                            radio.checked = true;
                            return 'clicked_radio';
                        }}
                        // Fallback: click the label itself
                        label.click();
                        return 'clicked_label';
                    }}
                }}

                // Method 2: Find any element with exact year text
                const allElements = document.querySelectorAll('.modal *');
                for (const el of allElements) {{
                    if (el.textContent.trim() === '{year}' &&
                        el.tagName !== 'SCRIPT' && el.tagName !== 'STYLE') {{
                        el.click();
                        return 'clicked_element';
                    }}
                }}

                return 'not_found';
            }}
            """

            result = await page.evaluate(js_select_year)
            logger.info(f"Year selection result: {result}")

            if result == 'not_found':
                logger.error(f"Year {year} not found in modal")
                # Debug: log modal content
                try:
                    modal_text = await page.evaluate(
                        "() => document.querySelector('.modal-body, .modal-content')?.innerText || 'no modal'"
                    )
                    logger.info(f"Modal content preview: {modal_text[:200]}...")
                except Exception as e:
                    logger.error(f"Error reading modal content for debugging: {e}")
                return False

            await page.wait_for_timeout(1000)

            # Step 4: Click confirm button using JavaScript
            js_confirm = """
            () => {
                const buttons = document.querySelectorAll('.modal button, .modal-footer button');
                for (const btn of buttons) {
                    const text = btn.textContent.trim().toLowerCase();
                    // Macedonian: "Потврди" = Confirm, "Откажи" = Cancel
                    if (text.includes('потврди') || text.includes('confirm') || text === 'ok') {
                        btn.click();
                        return 'confirmed';
                    }
                }
                // Try clicking any primary/success button
                const primary = document.querySelector('.modal .btn-primary, .modal .btn-success');
                if (primary) {
                    primary.click();
                    return 'clicked_primary';
                }
                return 'no_confirm_button';
            }
            """

            confirm_result = await page.evaluate(js_confirm)
            logger.info(f"Confirm button result: {confirm_result}")

            if confirm_result == 'no_confirm_button':
                logger.error("Could not find confirm button in modal")
                return False

            # Step 5: Wait for page to reload with new year's data
            await page.wait_for_timeout(3000)

            # Verify modal is closed
            modal_still_open = await page.query_selector('.modal-dialog')
            if modal_still_open:
                # Try clicking outside the modal to close it
                await page.keyboard.press('Escape')
                await page.wait_for_timeout(1000)

            # Wait for DataTable to load with new data
            # Use generic selector that works for any DataTable
            try:
                await page.wait_for_selector('table.dataTable tbody tr', timeout=15000)
            except Exception as e:
                logger.warning(f"Table might not have loaded after year selection: {e}")

            # Re-detect table ID after archive year selection (table may be recreated)
            self.table_id = None  # Reset to force re-detection
            await self._detect_table_id(page)

            # Step 6: Verify selection by checking page content
            info_text = ""
            try:
                info_elem = await page.query_selector(f'.dataTables_info, {self._get_table_selector("info")}')
                if info_elem:
                    info_text = await info_elem.inner_text()
                    logger.warning(f"Archive year {year} loaded: {info_text}")
            except Exception as e:
                logger.error(f"Error verifying archive year selection: {e}")

            logger.warning(f"Successfully selected archive year {year}")
            return True

        except Exception as e:
            logger.error(f"Failed to select archive year {year}: {e}")
            return False

    async def _apply_date_filter(self, page, year_start: int, year_end: int = None) -> bool:
        """
        Apply date filter using Angular scope to filter tenders by publication period.
        This is MUCH faster than scanning through pages - filters at server level.

        Args:
            page: Playwright page object
            year_start: Start year (e.g., 2024)
            year_end: End year (optional, defaults to year_start)

        Returns:
            True if filter was successfully applied, False otherwise
        """
        if year_end is None:
            year_end = year_start

        logger.info(f"Applying date filter: {year_start} - {year_end}")

        try:
            # Get record count before filtering
            info_before = await page.evaluate(
                "() => document.querySelector('.dataTables_info')?.innerText || ''"
            )
            logger.info(f"Before filter: {info_before}")

            # Use JavaScript to find Angular scope, set date range, and call filter
            js_apply_filter = f"""
            (function() {{
                // Find the scope with searchModel
                var scope = null;
                var all = document.querySelectorAll('*');
                for (var i = 0; i < all.length; i++) {{
                    try {{
                        var s = angular.element(all[i]).scope();
                        if (s && s.searchModel) {{
                            scope = s;
                            break;
                        }}
                    }} catch(e) {{}}
                }}

                if (!scope || !scope.searchModel) {{
                    return {{error: 'No searchModel found in Angular scope'}};
                }}

                // Set date range (PeriodFrom/PeriodTo for publication period)
                var fromDate = new Date({year_start}, 0, 1);  // Jan 1
                var toDate = new Date({year_end}, 11, 31);    // Dec 31

                scope.searchModel.PeriodFrom = fromDate;
                scope.searchModel.PeriodTo = toDate;

                // Apply scope changes first, then call filter
                scope.$apply(function() {{
                    if (scope.filter && typeof scope.filter === 'function') {{
                        scope.filter();
                    }}
                }});

                return {{
                    status: 'success',
                    periodFrom: fromDate.toISOString(),
                    periodTo: toDate.toISOString()
                }};
            }})()
            """

            result = await page.evaluate(js_apply_filter)
            logger.info(f"Date filter result: {result}")

            if result.get('error'):
                logger.error(f"Failed to apply date filter: {result['error']}")
                return False

            # Wait for table to reload with filtered data
            await page.wait_for_timeout(5000)

            # Verify filter was applied by checking record count changed
            info_after = await page.evaluate(
                "() => document.querySelector('.dataTables_info')?.innerText || ''"
            )
            logger.warning(f"After date filter ({year_start}-{year_end}): {info_after}")

            # Wait for table to be stable
            # Use generic selector that works for any DataTable
            try:
                await page.wait_for_selector('table.dataTable tbody tr', timeout=15000)
            except Exception as e:
                logger.warning(f"Table may still be loading after date filter: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to apply date filter: {e}")
            return False

    async def _apply_date_range_filter(self, page, date_from=None, date_to=None) -> bool:
        """
        Apply date range filter using Angular scope with specific dates.
        Works with archive years to target specific date ranges within the archive.

        Args:
            page: Playwright page object
            date_from: Start date (datetime.date object, string, or None)
            date_to: End date (datetime.date object, string, or None)

        Returns:
            True if filter was successfully applied, False otherwise
        """
        from datetime import date as date_type

        # Helper to convert to date object if needed
        def ensure_date(d):
            if d is None:
                return None
            if isinstance(d, date_type):
                return d
            if isinstance(d, str):
                # Parse string to date
                from datetime import datetime as dt
                for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
                    try:
                        return dt.strptime(d.strip(), fmt).date()
                    except ValueError:
                        continue
            logger.warning(f"Could not convert to date: {d} (type: {type(d).__name__})")
            return None

        date_from = ensure_date(date_from)
        date_to = ensure_date(date_to)

        # Build JavaScript date constructors
        if date_from:
            # JavaScript months are 0-indexed
            from_js = f"new Date({date_from.year}, {date_from.month - 1}, {date_from.day})"
        else:
            from_js = "null"

        if date_to:
            # JavaScript months are 0-indexed
            to_js = f"new Date({date_to.year}, {date_to.month - 1}, {date_to.day})"
        else:
            to_js = "null"

        logger.info(f"Applying date range filter: {date_from} to {date_to}")

        try:
            # Get record count before filtering
            info_before = await page.evaluate(
                "() => document.querySelector('.dataTables_info')?.innerText || ''"
            )
            logger.info(f"Before date range filter: {info_before}")

            # Use JavaScript to find Angular scope, set date range, and call filter
            js_apply_filter = f"""
            (function() {{
                // Find the scope with searchModel
                var scope = null;
                var all = document.querySelectorAll('*');
                for (var i = 0; i < all.length; i++) {{
                    try {{
                        var s = angular.element(all[i]).scope();
                        if (s && s.searchModel) {{
                            scope = s;
                            break;
                        }}
                    }} catch(e) {{}}
                }}

                if (!scope || !scope.searchModel) {{
                    return {{error: 'No searchModel found in Angular scope'}};
                }}

                // Set date range (PeriodFrom/PeriodTo for publication period)
                var fromDate = {from_js};
                var toDate = {to_js};

                if (fromDate) scope.searchModel.PeriodFrom = fromDate;
                if (toDate) scope.searchModel.PeriodTo = toDate;

                // Apply scope changes first, then call filter
                scope.$apply(function() {{
                    if (scope.filter && typeof scope.filter === 'function') {{
                        scope.filter();
                    }}
                }});

                return {{
                    status: 'success',
                    periodFrom: fromDate ? fromDate.toISOString() : null,
                    periodTo: toDate ? toDate.toISOString() : null
                }};
            }})()
            """

            result = await page.evaluate(js_apply_filter)
            logger.info(f"Date range filter result: {result}")

            if result.get('error'):
                logger.error(f"Failed to apply date range filter: {result['error']}")
                return False

            # Wait for table to reload with filtered data
            await page.wait_for_timeout(5000)

            # Verify filter was applied by checking record count changed
            info_after = await page.evaluate(
                "() => document.querySelector('.dataTables_info')?.innerText || ''"
            )
            logger.warning(f"After date range filter ({date_from} to {date_to}): {info_after}")

            # Wait for table to be stable
            try:
                await page.wait_for_selector('table.dataTable tbody tr', timeout=15000)
            except Exception as e:
                logger.warning(f"Table may still be loading after date range filter: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to apply date range filter: {e}")
            return False

    async def _go_to_page(self, page, target_page: int) -> bool:
        """
        Navigate to a specific page number using DataTables API for direct jump.

        Args:
            page: Playwright page object
            target_page: Target page number to navigate to (1-indexed)

        Returns:
            True if successfully navigated, False otherwise
        """
        if target_page <= 1:
            return True  # Already on first page

        logger.info(f"Navigating directly to page {target_page} using DataTables API...")

        try:
            # Get current page info before navigation
            info_before = await page.evaluate(
                "() => document.querySelector('.dataTables_info')?.innerText || ''"
            )

            # Use DataTables API to jump directly to page (0-indexed internally)
            # Try different table IDs that e-nabavki might use
            js_jump = f"""
            () => {{
                // Try to find the DataTable instance
                const tableIds = ['contracts-grid', 'notices-grid', 'DataTables_Table_0', 'tbl'];

                for (const id of tableIds) {{
                    const table = document.getElementById(id);
                    if (table && $.fn.DataTable.isDataTable('#' + id)) {{
                        const dt = $('#' + id).DataTable();
                        const totalPages = dt.page.info().pages;
                        const targetIdx = {target_page - 1};  // DataTables uses 0-indexed pages

                        if (targetIdx < totalPages) {{
                            dt.page(targetIdx).draw('page');
                            return {{ success: true, tableId: id, page: targetIdx + 1, totalPages: totalPages }};
                        }} else {{
                            return {{ success: false, error: 'Page ' + {target_page} + ' exceeds total ' + totalPages }};
                        }}
                    }}
                }}

                // Fallback: try to find any DataTable
                const tables = $.fn.dataTable.tables();
                if (tables.length > 0) {{
                    const dt = $(tables[0]).DataTable();
                    const totalPages = dt.page.info().pages;
                    const targetIdx = {target_page - 1};

                    if (targetIdx < totalPages) {{
                        dt.page(targetIdx).draw('page');
                        return {{ success: true, tableId: 'auto', page: targetIdx + 1, totalPages: totalPages }};
                    }}
                }}

                return {{ success: false, error: 'No DataTable found' }};
            }}
            """

            result = await page.evaluate(js_jump)
            logger.info(f"DataTables jump result: {result}")

            if result.get('success'):
                # Wait for table to redraw
                await page.wait_for_timeout(2000)

                # Verify page changed
                info_after = await page.evaluate(
                    "() => document.querySelector('.dataTables_info')?.innerText || ''"
                )

                if info_before != info_after:
                    logger.info(f"Successfully jumped to page {target_page} (total: {result.get('totalPages')})")
                    return True
                else:
                    logger.warning(f"Page info unchanged after jump attempt")

            # Fallback to clicking if DataTables API didn't work
            logger.warning(f"DataTables API jump failed, falling back to click navigation...")
            return await self._go_to_page_by_clicking(page, target_page)

        except Exception as e:
            logger.error(f"Error navigating to page {target_page}: {e}")
            return await self._go_to_page_by_clicking(page, target_page)

    async def _go_to_page_by_clicking(self, page, target_page: int) -> bool:
        """
        Fallback: Navigate to a specific page by clicking next repeatedly.
        Only used if DataTables API jump fails.
        """
        logger.info(f"Clicking through to page {target_page}...")

        try:
            current_num = 1

            while current_num < target_page:
                has_next = await self._click_next_page(page)
                if not has_next:
                    logger.warning(f"Could not navigate beyond page {current_num}")
                    return False

                current_num += 1

                # Log progress every 50 pages
                if current_num % 50 == 0:
                    logger.info(f"Navigation progress: page {current_num}/{target_page}")

            logger.info(f"Successfully navigated to page {target_page}")
            return True

        except Exception as e:
            logger.error(f"Error clicking to page {target_page}: {e}")
            return False

    async def _go_to_last_page(self, page) -> bool:
        """
        Navigate to the last page for reverse pagination.

        Returns:
            True if successfully navigated, False otherwise
        """
        logger.info("Navigating to last page for reverse pagination...")

        try:
            # Make sure we have the table ID
            if not self.table_id:
                await self._detect_table_id(page)

            # Try clicking "Last" button if available
            # Use dynamic table ID for the first selector
            last_selectors = [
                f'{self._get_table_selector("last")}:not(.disabled)',  # e.g., #contracts-grid_last
                'a.paginate_button.last:not(.disabled)',
                '.dataTables_paginate .last:not(.disabled)',
            ]

            for selector in last_selectors:
                try:
                    last_btn = await page.query_selector(selector)
                    if last_btn:
                        class_attr = await last_btn.get_attribute('class') or ''
                        if 'disabled' not in class_attr:
                            await page.evaluate('(el) => el.click()', last_btn)
                            await page.wait_for_timeout(2000)
                            logger.info(f"Clicked Last button: {selector}")
                            return True
                except Exception as e:
                    logger.error(f"Error clicking Last button with selector {selector}: {e}")
                    continue

            # If no Last button, try to find total pages and click highest
            try:
                page_buttons = await page.query_selector_all('.paginate_button:not(.previous):not(.next):not(.last):not(.first)')
                if page_buttons:
                    # Find the highest page number
                    max_page = 1
                    max_btn = None
                    for btn in page_buttons:
                        try:
                            text = await btn.inner_text()
                            num = int(text.strip())
                            if num > max_page:
                                max_page = num
                                max_btn = btn
                        except Exception as e:
                            logger.error(f"Error parsing page button number: {e}")
                            continue

                    if max_btn:
                        await page.evaluate('(el) => el.click()', max_btn)
                        await page.wait_for_timeout(2000)
                        logger.info(f"Clicked highest visible page: {max_page}")
                        return True
            except Exception as e:
                logger.debug(f"Error finding page buttons: {e}")

            logger.warning("Could not navigate to last page")
            return False

        except Exception as e:
            logger.error(f"Error navigating to last page: {e}")
            return False

    async def _click_previous_page(self, page) -> bool:
        """
        Click the Previous button in pagination for reverse navigation.

        Returns:
            True if successfully clicked and page changed, False if no more pages.
        """
        try:
            # Make sure we have the table ID
            if not self.table_id:
                await self._detect_table_id(page)

            prev_selectors = [
                f'{self._get_table_selector("previous")}:not(.disabled)',  # e.g., #contracts-grid_previous
                'a.paginate_button.previous:not(.disabled)',
                '.dataTables_paginate .previous:not(.disabled)',
                'a[data-dt-idx="previous"]:not(.disabled)',
            ]

            for selector in prev_selectors:
                try:
                    prev_btn = await page.query_selector(selector)
                    if prev_btn:
                        class_attr = await prev_btn.get_attribute('class') or ''
                        if 'disabled' in class_attr:
                            continue

                        await page.evaluate('(el) => el.click()', prev_btn)
                        await page.wait_for_timeout(1000)
                        logger.info(f"Clicked Previous button: {selector}")
                        return True
                except Exception as e:
                    logger.error(f"Error clicking Previous button with selector {selector}: {e}")
                    continue

            logger.info("No Previous button found or first page reached")
            return False

        except Exception as e:
            logger.warning(f"Error clicking previous page: {e}")
            return False

    async def _handle_pagination(self, page, source_category: str) -> Optional[str]:
        """
        Handle pagination for the listing page.
        Clicks the "Next" button and returns the new page URL if available.
        Returns None if no more pages.
        """
        try:
            # Make sure we have the table ID
            if not self.table_id:
                await self._detect_table_id(page)

            # Look for pagination info to see total pages
            page_info_selectors = [
                '.dataTables_info',
                self._get_table_selector('info'),  # e.g., #contracts-grid_info
                '.pagination-info',
            ]

            for selector in page_info_selectors:
                try:
                    info_elem = await page.query_selector(selector)
                    if info_elem:
                        info_text = await info_elem.inner_text()
                        logger.info(f"Pagination info: {info_text}")
                        break
                except Exception as e:
                    logger.error(f"Error reading pagination info with selector {selector}: {e}")
                    continue

            # Look for Next button in DataTables pagination
            # Use dynamic table ID for ID-based selector
            next_selectors = [
                'a.paginate_button.next:not(.disabled)',
                'li.next:not(.disabled) a',
                'a:has-text("Следна"):not(.disabled)',
                'a:has-text("Next"):not(.disabled)',
                'button:has-text("Следна"):not([disabled])',
                f'{self._get_table_selector("next")}:not(.disabled)',  # e.g., #contracts-grid_next
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
                        await page.wait_for_timeout(1000)  # Wait for data to load

                        # Try to wait for table refresh
                        try:
                            await page.wait_for_selector('table tbody tr', timeout=20000)
                        except Exception as e:
                            logger.error(f"Error waiting for table refresh after Next click: {e}")

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
            # Make sure we have the table ID
            if not self.table_id:
                await self._detect_table_id(page)

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
                        await page.wait_for_timeout(500)  # Wait for DataTable to update
                        # Use generic table selector that works for any DataTable
                        await page.wait_for_selector('table.dataTable tbody tr', timeout=20000)

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
        documents_html = ""  # Store HTML from documents tab

        if page:
            try:
                # Wait for Angular to render content
                # Increased timeout from 20s to 30s for slow pages
                await page.wait_for_selector('label.dosie-value', timeout=30000)
                await page.wait_for_timeout(500)
                logger.info("✓ Tender detail page loaded")

                # Get main page HTML first
                html_content = await page.content()

                # ============================================
                # CLICK ON ДОКУМЕНТАЦИЈА TAB TO LOAD DOCUMENTS
                # ============================================
                try:
                    # Try multiple selectors for the Documentation tab
                    doc_tab_selectors = [
                        'a[href*="documents"]',  # Link containing 'documents'
                        'a:has-text("Документација")',  # Tab with Macedonian text
                        'a:has-text("Documents")',  # English version
                        '.nav-tabs a:nth-child(2)',  # Second tab (often documents)
                        'ul.nav-tabs li:nth-child(2) a',  # Second tab item
                        '[ng-click*="document"]',  # Angular click handler
                        'a[data-toggle="tab"]:has-text("Документација")',
                    ]

                    doc_tab_clicked = False
                    for selector in doc_tab_selectors:
                        try:
                            doc_tab = await page.query_selector(selector)
                            if doc_tab:
                                await doc_tab.click()
                                await page.wait_for_timeout(500)  # Wait for tab content to load
                                logger.info(f"✓ Clicked documents tab using selector: {selector}")
                                doc_tab_clicked = True
                                break
                        except Exception as e:
                            continue

                    if doc_tab_clicked:
                        # Get the updated HTML with document links
                        documents_html = await page.content()
                        logger.info("✓ Captured HTML from documents tab")
                    else:
                        logger.warning("⚠ Could not find documents tab to click")

                except Exception as e:
                    logger.warning(f"⚠ Failed to click documents tab: {e}")

                # Combine main page HTML with documents tab HTML
                if documents_html:
                    # Append document links section to main HTML
                    combined_html = html_content + "\n<!-- DOCUMENTS TAB -->\n" + documents_html
                    response = response.replace(body=combined_html.encode('utf-8'))
                else:
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

        # Fallback: derive publication_date from other dates if not found
        # For awarded/historical tenders, use contract_signing_date or opening_date
        if not tender['publication_date']:
            if tender['contract_signing_date']:
                tender['publication_date'] = tender['contract_signing_date']
                logger.debug(f"Using contract_signing_date as publication_date fallback")
            elif tender['opening_date']:
                tender['publication_date'] = tender['opening_date']
                logger.debug(f"Using opening_date as publication_date fallback")

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

        # Check year filter BEFORE extracting/yielding documents
        if not self._tender_passes_year_filter(tender):
            self.stats['tenders_skipped'] += 1
            logger.info(f"⏭️ Skipping tender {tender.get('tender_id')} (year filter)")
            return

        # Extract documents and yield DocumentItems for pipeline processing
        documents = self._extract_documents(response, tender.get('tender_id', 'unknown'))
        tender['documents_data'] = documents
        logger.warning(f"Documents captured for {tender.get('tender_id')}: {len(documents)}")
        for doc in documents:
            # Skip ohridskabanka.mk documents (external bank guarantees - not relevant)
            doc_url = doc.get('url', '')
            if 'ohridskabanka' in doc_url.lower():
                logger.info(f"Skipping ohridskabanka.mk document: {doc_url}")
                continue

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
                '//label[@label-for="TYPE OF PROCUREMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="TYPE OF CONTRACT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels
                '//label[contains(text(), "Вид на набавка")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Вид на договор")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Предмет на договорот за набавка")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # General contains
                '//label[contains(@label-for, "TYPE OF PROCUREMENT")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "TYPE OF CONTRACT")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
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
                '//label[@label-for="PROCEDURE TYPE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="TYPE OF CALL DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels
                '//label[contains(text(), "Вид на постапка")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Тип на постапка")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Вид на оглас")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # General contains
                '//label[contains(@label-for, "PROCEDURE TYPE")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "TYPE OF CALL")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
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
                '//label[@label-for="CONTRACT DURATION DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="PERIOD IN MONTHS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels
                '//label[contains(text(), "Период во месеци")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Траење на договорот")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Рок на траење")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # General contains
                '//label[contains(@label-for, "PERIOD IN MONTHS")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "CONTRACT DURATION")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'winner': [
                # Winner name (contractor who won the tender)
                '//label[@label-for="NAME OF CONTACT OF PROCUREMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="WINNER NAME DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="SELECTED BIDDER DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="NAME OF CONTACT OF PROCUREMENT DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="WINNER NAME DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="SELECTED BIDDER DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels
                '//label[contains(text(), "Избран понудувач")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Назив на носителот")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Договорна страна")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Име на понудувач")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # General contains
                '//label[contains(@label-for, "WINNER")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "SELECTED BIDDER")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
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
                '//label[@label-for="CRITERION FOR ASSIGNMENT OF CONTRACT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels for evaluation/award criteria
                '//label[contains(text(), "Критериум за доделување")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Критериум за избор")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Критериум")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # General contains for CRITERION/AWARD in label-for
                '//label[contains(@label-for, "CRITERION")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "AWARD CRITERIA")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'delivery_location': [
                '//label[@label-for="DELIVERY OF GOODS LOCATION OF WORKS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="DELIVERY OF GOODS LOCATION OF WORKS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="DELIVERY LOCATION DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels
                '//label[contains(text(), "Место на испорака")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Место на извршување")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Локација")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # General contains for DELIVERY/LOCATION
                '//label[contains(@label-for, "DELIVERY")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'num_bidders': [
                '//label[@label-for="NUMBER OF OFFERS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="NUMBER OF OFFERS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="NUMBER OF BIDS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian labels
                '//label[contains(text(), "Број на понуди")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Број на примени понуди")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # General contains
                '//label[contains(@label-for, "NUMBER OF OFFERS")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "NUMBER OF BIDS")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'highest_bid': [
                '//label[@label-for="HIGEST OFFER VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="HIGHEST OFFER VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="HIGEST OFFER VALUE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian
                '//label[contains(text(), "Највисока понуда")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "HIGEST OFFER")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "HIGHEST OFFER")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'lowest_bid': [
                '//label[@label-for="LOWEST OFFER VALUE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="LOWEST OFFER VALUE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian
                '//label[contains(text(), "Најниска понуда")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(@label-for, "LOWEST OFFER")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
            ],
            'has_lots': [
                '//label[@label-for="CAN BE DIVEDED ON LOTS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="CAN BE DIVIDED ON LOTS DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="CAN BE DIVEDED ON LOTS DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian
                '//label[contains(text(), "Може да се дели на лотови")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "лотови")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
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
                # For awarded/historical contracts - announcement date variants
                '//label[@label-for="DATE WHEN NOTICE WAS PUBLISHED DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="NOTICE PUBLICATION DATE DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="DATE OF ANNOUNCEMENT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[@label-for="ANNOUNCEMENT OF CONTRACT DOSSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                # Macedonian text-based fallbacks
                '//label[contains(text(), "Датум на објавување")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "Датум на објава")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
                '//label[contains(text(), "датум на известувањето")]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
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
            except Exception as e:
                logger.error(f"Error parsing bracketed percentage from '{value_string}': {e}")

        # Also try pattern without brackets: "15.00 %" or "15,00%"
        percentage_match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', value_string)
        if percentage_match:
            try:
                number_str = percentage_match.group(1).replace(',', '.')
                return Decimal(number_str)
            except Exception as e:
                logger.error(f"Error parsing percentage from '{value_string}': {e}")

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
        except Exception as e:
            logger.error(f"Error parsing currency from '{value_string}': {e}")
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
        import json
        import re
        import urllib.parse

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
            '//a[contains(@href, "GetAttachmentChangesFile")]/@href',
            '//a[contains(@href, "DownloadDoc")]/@href',
            '//a[contains(@href, "DownloadPublicFile")]/@href',
        ]

        doc_selectors = [
            'a[href*="Download"]::attr(href)',
            'a[href*=".pdf"]::attr(href)',
            'a[href*="File"]::attr(href)',
            'a[href*="Bids"]::attr(href)',
            'a[href*="fileId"]::attr(href)',
            'a[href*="GetAttachmentChangesFile"]::attr(href)',
            'a[href*="DownloadDoc"]::attr(href)',
            'a[href*="DownloadPublicFile"]::attr(href)',
        ]

        def add_document(link, filename=None):
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

            # Extract filename from URL if not provided
            if not filename:
                parsed = urllib.parse.urlparse(link)
                if 'fileId=' in link:
                    # For fileId URLs, generate filename from fileId
                    file_id = urllib.parse.parse_qs(parsed.query).get('fileId', ['unknown'])[0]
                    filename = f"document_{file_id[:8]}.pdf"
                elif 'fname=' in link:
                    # Extract filename from fname parameter
                    filename = urllib.parse.parse_qs(parsed.query).get('fname', ['document.pdf'])[0]
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
            logger.debug(f"Added document: {filename} -> {link[:80]}...")

        # ============================================
        # EXTRACT DOCUMENTS FROM ng-click ATTRIBUTES
        # Documents are embedded in PreviewDocumentConfirm({...}) calls
        # ============================================
        ng_click_pattern = re.compile(r'PreviewDocumentConfirm\((\{.*?\})\)', re.DOTALL)

        # Find all elements with ng-click containing PreviewDocumentConfirm
        ng_click_elements = response.xpath('//*[contains(@ng-click, "PreviewDocumentConfirm")]/@ng-click').getall()

        for ng_click in ng_click_elements:
            try:
                match = ng_click_pattern.search(ng_click)
                if match:
                    json_str = match.group(1)
                    # Parse the JSON document data
                    doc_data = json.loads(json_str)

                    doc_url = doc_data.get('DocumentUrl', '')
                    doc_name = doc_data.get('DocumentName', '')
                    file_id = doc_data.get('FileId', '')

                    if doc_url:
                        # Build full URL
                        if doc_url.startswith('/'):
                            full_url = 'https://e-nabavki.gov.mk' + doc_url
                        elif not doc_url.startswith('http'):
                            full_url = 'https://e-nabavki.gov.mk/' + doc_url
                        else:
                            full_url = doc_url

                        add_document(full_url, doc_name)
                        logger.info(f"Extracted ng-click document: {doc_name}")

                    # Also try to build public download URL from FileId
                    if file_id and file_id not in str(seen_urls):
                        public_url = f"https://e-nabavki.gov.mk/File/DownloadPublicFile?fileId={file_id}"
                        add_document(public_url, doc_name)

            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse ng-click JSON: {e}")
            except Exception as e:
                logger.debug(f"Error extracting ng-click document: {e}")

        # Also extract from previewDocumentModal calls
        preview_modal_pattern = re.compile(r'previewDocumentModal\([^,]+,\s*["\']([^"\']+)["\'],\s*["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']', re.DOTALL)
        preview_elements = response.xpath('//*[contains(@ng-click, "previewDocumentModal")]/@ng-click').getall()

        for ng_click in preview_elements:
            try:
                match = preview_modal_pattern.search(ng_click)
                if match:
                    file_id = match.group(1)
                    doc_name = match.group(2)
                    doc_url = match.group(3)

                    if doc_url:
                        if doc_url.startswith('/'):
                            full_url = 'https://e-nabavki.gov.mk' + doc_url
                        elif not doc_url.startswith('http'):
                            full_url = 'https://e-nabavki.gov.mk/' + doc_url
                        else:
                            full_url = doc_url
                        add_document(full_url, doc_name)
                        logger.info(f"Extracted previewDocumentModal document: {doc_name}")
            except Exception as e:
                logger.debug(f"Error extracting previewDocumentModal document: {e}")

        # Try CSS selectors for href links
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
            except Exception as e:
                logger.error(f"Error parsing closing date '{closing_date}': {e}")

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
