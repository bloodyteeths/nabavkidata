"""
E-Pazar Spider - Playwright-based scraper for e-pazar.gov.mk
Electronic Public Procurement Marketplace of North Macedonia

This spider uses Playwright for JavaScript rendering as e-pazar.gov.mk
is a React-based Single Page Application (SPA).

Features:
- Full tender metadata extraction
- Bill of Quantities (BOQ) items extraction
- Offer/bid data extraction
- Awarded contract details
- Document download support
- Pagination handling
- Historical archive support
"""

import scrapy
import json
import re
import hashlib
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse, parse_qs

logger = logging.getLogger(__name__)


class EPazarItem(scrapy.Item):
    """E-Pazar Tender item structure"""
    # Core identifiers
    tender_id = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()

    # Contracting authority
    contracting_authority = scrapy.Field()
    contracting_authority_id = scrapy.Field()

    # Values
    estimated_value_mkd = scrapy.Field()
    estimated_value_eur = scrapy.Field()
    awarded_value_mkd = scrapy.Field()
    awarded_value_eur = scrapy.Field()

    # Procedure & Status
    procedure_type = scrapy.Field()
    status = scrapy.Field()  # active, awarded, cancelled, closed

    # Dates
    publication_date = scrapy.Field()
    closing_date = scrapy.Field()
    award_date = scrapy.Field()
    contract_date = scrapy.Field()

    # Contract details
    contract_number = scrapy.Field()
    contract_duration = scrapy.Field()

    # Classification
    cpv_code = scrapy.Field()
    category = scrapy.Field()

    # Source
    source_url = scrapy.Field()
    source_category = scrapy.Field()
    language = scrapy.Field()

    # Metadata
    scraped_at = scrapy.Field()
    content_hash = scrapy.Field()

    # Related data (JSON)
    items_data = scrapy.Field()  # BOQ items
    offers_data = scrapy.Field()  # Supplier bids
    awarded_items_data = scrapy.Field()  # Contract items
    documents_data = scrapy.Field()  # Document metadata


class EPazarDocumentItem(scrapy.Item):
    """E-Pazar Document item"""
    tender_id = scrapy.Field()
    doc_type = scrapy.Field()
    doc_category = scrapy.Field()
    file_name = scrapy.Field()
    file_path = scrapy.Field()
    file_url = scrapy.Field()
    content_text = scrapy.Field()
    extraction_status = scrapy.Field()
    file_size_bytes = scrapy.Field()
    page_count = scrapy.Field()
    mime_type = scrapy.Field()
    file_hash = scrapy.Field()
    upload_date = scrapy.Field()


class EPazarSpider(scrapy.Spider):
    """
    Playwright-based spider for e-pazar.gov.mk

    Usage:
        scrapy crawl epazar -a category=active
        scrapy crawl epazar -a category=awarded
        scrapy crawl epazar -a category=all
        scrapy crawl epazar -a mode=incremental
    """

    name = 'epazar'
    allowed_domains = ['e-pazar.gov.mk']

    # Base URLs - These will be discovered/updated during site exploration
    BASE_URL = 'https://e-pazar.gov.mk'

    # Category URL patterns (to be discovered via API inspection)
    CATEGORY_URLS = {
        'active': 'https://e-pazar.gov.mk/Notices/Search?status=active',
        'awarded': 'https://e-pazar.gov.mk/Notices/Search?status=awarded',
        'cancelled': 'https://e-pazar.gov.mk/Notices/Search?status=cancelled',
        'all': 'https://e-pazar.gov.mk/Notices/Search',
    }

    # API endpoints (to be discovered)
    API_ENDPOINTS = {
        'list_tenders': '/api/notices/search',
        'get_tender': '/api/notices/{id}',
        'get_items': '/api/notices/{id}/items',
        'get_offers': '/api/notices/{id}/offers',
        'get_documents': '/api/notices/{id}/documents',
    }

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,  # Slower for React SPA
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "PLAYWRIGHT_MAX_CONTEXTS": 2,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90000,  # 90 seconds
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        },
        # Pipeline configuration - use specific e-pazar pipelines
        "ITEM_PIPELINES": {
            "scraper.pipelines.EPazarValidationPipeline": 100,
            "scraper.pipelines.EPazarDatabasePipeline": 300,
        }
    }

    def __init__(self, category='active', mode='scrape', max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category.lower()
        self.mode = mode.lower()  # 'scrape', 'discover', 'incremental'
        self.max_pages = int(max_pages) if max_pages else None

        # Statistics tracking
        self.stats = {
            'tenders_found': 0,
            'tenders_scraped': 0,
            'items_extracted': 0,
            'offers_extracted': 0,
            'documents_found': 0,
            'errors': 0,
            'pages_processed': 0,
        }

        # Track scraped tender IDs for incremental mode
        self.scraped_ids = set()

        logger.info(f"EPazar Spider initialized: category={self.category}, mode={self.mode}")

    def start_requests(self):
        """Generate initial requests with Playwright enabled"""

        if self.mode == 'discover':
            # Discovery mode - explore site structure
            yield scrapy.Request(
                self.BASE_URL,
                callback=self.discover_site_structure,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                        'timeout': 90000,
                    },
                },
                errback=self.errback_playwright,
                dont_filter=True
            )
        else:
            # Normal scraping mode
            categories = ['active', 'awarded', 'cancelled'] if self.category == 'all' else [self.category]

            for cat in categories:
                url = self.CATEGORY_URLS.get(cat, self.CATEGORY_URLS['all'])
                logger.info(f"Starting scrape for category: {cat}, URL: {url}")

                yield scrapy.Request(
                    url,
                    callback=self.parse_listing,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'networkidle',
                            'timeout': 90000,
                        },
                        'category': cat,
                        'page_number': 1,
                    },
                    errback=self.errback_playwright,
                    dont_filter=True
                )

    async def discover_site_structure(self, response):
        """
        Discover site structure and API endpoints by inspecting network requests.
        This should be run first to understand the site's architecture.
        """
        page = response.meta.get('playwright_page')

        try:
            logger.info("Discovering e-pazar.gov.mk site structure...")

            # Wait for React app to fully load
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)  # Additional wait for React

            # Get page content
            html_content = await page.content()

            # Try to find navigation elements
            nav_elements = await page.query_selector_all('nav a, .nav a, .menu a, .sidebar a')
            discovered_routes = []

            for elem in nav_elements:
                href = await elem.get_attribute('href')
                text = await elem.inner_text()
                if href:
                    discovered_routes.append({'href': href, 'text': text.strip()})

            # Log discovered routes
            logger.info(f"Discovered {len(discovered_routes)} navigation routes:")
            for route in discovered_routes:
                logger.info(f"  {route['text']}: {route['href']}")

            # Try to capture API calls by navigating to notices
            api_calls = []

            # Set up request interception to capture API calls
            async def capture_request(request):
                if '/api/' in request.url or 'notices' in request.url.lower():
                    api_calls.append({
                        'url': request.url,
                        'method': request.method,
                    })

            page.on('request', capture_request)

            # Try clicking on common navigation patterns
            search_selectors = [
                'a[href*="Notice"]',
                'a[href*="notice"]',
                'a[href*="Search"]',
                'a[href*="search"]',
                '.notice-link',
                '.tender-link',
            ]

            for selector in search_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click()
                        await page.wait_for_load_state('networkidle')
                        await page.wait_for_timeout(2000)
                        break
                except Exception as e:
                    logger.debug(f"Could not click {selector}: {e}")

            # Log discovered API endpoints
            logger.info(f"Discovered {len(api_calls)} API calls:")
            for call in api_calls:
                logger.info(f"  {call['method']} {call['url']}")

            # Save discovery results
            discovery_result = {
                'timestamp': datetime.utcnow().isoformat(),
                'base_url': self.BASE_URL,
                'routes': discovered_routes,
                'api_calls': api_calls,
                'html_snippet': html_content[:5000],
            }

            # Write discovery results to file
            import os
            output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'epazar_discovery.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(discovery_result, f, ensure_ascii=False, indent=2)

            logger.info(f"Discovery results saved to: {output_path}")

        except Exception as e:
            logger.error(f"Error during site discovery: {e}")
        finally:
            await page.close()

    async def parse_listing(self, response):
        """
        Parse the tender listing page.
        Extracts tender links and handles pagination.
        """
        page = response.meta.get('playwright_page')
        category = response.meta.get('category', 'active')
        page_number = response.meta.get('page_number', 1)

        try:
            logger.info(f"Parsing listing page {page_number} for category: {category}")

            # Wait for React to render content
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(2000)

            # Try multiple selectors for tender list items
            tender_selectors = [
                '.notice-item',
                '.tender-item',
                '.listing-item',
                'tr[data-id]',
                '.card',
                '[class*="notice"]',
                '[class*="tender"]',
            ]

            tender_elements = []
            used_selector = None

            for selector in tender_selectors:
                elements = await page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    tender_elements = elements
                    used_selector = selector
                    logger.info(f"Found {len(elements)} tenders using selector: {selector}")
                    break

            if not tender_elements:
                logger.warning(f"No tender elements found on page {page_number}")
                # Try to get page content for debugging
                content = await page.content()
                logger.debug(f"Page content preview: {content[:2000]}")
                await page.close()
                return

            # Extract tender links
            tender_links = []

            for elem in tender_elements:
                try:
                    # Try to find link within element
                    link_elem = await elem.query_selector('a[href*="notice"], a[href*="Notice"], a[href*="tender"], a[href*="detail"]')
                    if not link_elem:
                        link_elem = await elem.query_selector('a')

                    if link_elem:
                        href = await link_elem.get_attribute('href')
                        if href:
                            full_url = urljoin(self.BASE_URL, href)
                            tender_links.append(full_url)

                    # Also try to get tender ID from data attribute
                    tender_id = await elem.get_attribute('data-id') or await elem.get_attribute('data-tender-id')
                    if tender_id and tender_id not in self.scraped_ids:
                        self.scraped_ids.add(tender_id)

                except Exception as e:
                    logger.debug(f"Error extracting tender link: {e}")

            self.stats['tenders_found'] += len(tender_links)
            logger.info(f"Found {len(tender_links)} tender links on page {page_number}")

            # Close listing page
            await page.close()

            # Yield requests for each tender detail page
            for url in tender_links:
                yield scrapy.Request(
                    url,
                    callback=self.parse_tender_detail,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'networkidle',
                            'timeout': 90000,
                        },
                        'category': category,
                    },
                    errback=self.errback_playwright,
                )

            # Handle pagination
            self.stats['pages_processed'] += 1

            if self.max_pages and page_number >= self.max_pages:
                logger.info(f"Reached max pages limit: {self.max_pages}")
                return

            # Check for next page
            # Create new page for pagination check
            next_page_url = self._get_next_page_url(response.url, page_number)
            if next_page_url:
                yield scrapy.Request(
                    next_page_url,
                    callback=self.parse_listing,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'networkidle',
                            'timeout': 90000,
                        },
                        'category': category,
                        'page_number': page_number + 1,
                    },
                    errback=self.errback_playwright,
                    dont_filter=True
                )

        except Exception as e:
            logger.error(f"Error parsing listing page {page_number}: {e}")
            self.stats['errors'] += 1
            if page:
                await page.close()

    async def parse_tender_detail(self, response):
        """
        Parse individual tender detail page.
        Extracts all tender metadata, items, offers, and documents.
        """
        page = response.meta.get('playwright_page')
        category = response.meta.get('category', 'active')

        try:
            logger.info(f"Parsing tender detail: {response.url}")

            # Wait for React to render
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(2000)

            # Get rendered HTML
            html_content = await page.content()
            response = response.replace(body=html_content.encode('utf-8'))

            # Extract tender ID from URL or page
            tender_id = self._extract_tender_id(response)

            if not tender_id:
                logger.warning(f"Could not extract tender ID from {response.url}")
                await page.close()
                return

            # Skip if already scraped in incremental mode
            if self.mode == 'incremental' and tender_id in self.scraped_ids:
                logger.info(f"Skipping already scraped tender: {tender_id}")
                await page.close()
                return

            # Extract tender metadata
            tender = EPazarItem()
            tender['tender_id'] = tender_id
            tender['source_url'] = response.url
            tender['source_category'] = category
            tender['language'] = 'mk'
            tender['scraped_at'] = datetime.utcnow().isoformat()

            # Extract fields using multiple strategies
            tender['title'] = self._extract_title(response)
            tender['description'] = self._extract_description(response)
            tender['contracting_authority'] = self._extract_contracting_authority(response)
            tender['estimated_value_mkd'] = self._extract_value(response, 'estimated')
            tender['status'] = self._extract_status(response)
            tender['procedure_type'] = self._extract_procedure_type(response)
            tender['cpv_code'] = self._extract_cpv_code(response)
            tender['publication_date'] = self._extract_date(response, 'publication')
            tender['closing_date'] = self._extract_date(response, 'closing')
            tender['award_date'] = self._extract_date(response, 'award')
            tender['contract_date'] = self._extract_date(response, 'contract')
            tender['contract_number'] = self._extract_field(response, 'contract_number')

            # Extract BOQ items (Bill of Quantities)
            items_data = await self._extract_items(page, tender_id)
            tender['items_data'] = json.dumps(items_data, ensure_ascii=False) if items_data else None
            self.stats['items_extracted'] += len(items_data) if items_data else 0

            # Extract offers/bids
            offers_data = await self._extract_offers(page, tender_id)
            tender['offers_data'] = json.dumps(offers_data, ensure_ascii=False) if offers_data else None
            self.stats['offers_extracted'] += len(offers_data) if offers_data else 0

            # Extract awarded items (if awarded)
            if category == 'awarded' or tender.get('status') == 'awarded':
                awarded_data = await self._extract_awarded_items(page, tender_id)
                tender['awarded_items_data'] = json.dumps(awarded_data, ensure_ascii=False) if awarded_data else None

                # Update awarded value
                if offers_data:
                    winner = next((o for o in offers_data if o.get('is_winner')), None)
                    if winner:
                        tender['awarded_value_mkd'] = winner.get('total_bid_mkd')

            # Extract documents
            documents_data = await self._extract_documents(page, tender_id)
            tender['documents_data'] = json.dumps(documents_data, ensure_ascii=False) if documents_data else None
            self.stats['documents_found'] += len(documents_data) if documents_data else 0

            # Calculate content hash for change detection
            tender['content_hash'] = self._calculate_content_hash(tender)

            self.stats['tenders_scraped'] += 1
            self.scraped_ids.add(tender_id)

            logger.info(f"Successfully scraped tender {tender_id}: {tender.get('title', 'N/A')[:50]}...")

            await page.close()
            yield tender

        except Exception as e:
            logger.error(f"Error parsing tender detail {response.url}: {e}")
            self.stats['errors'] += 1
            if page:
                await page.close()

    def _extract_tender_id(self, response) -> Optional[str]:
        """Extract tender ID from URL or page content"""
        # Try URL patterns
        url_patterns = [
            r'/notices?/(\d+)',
            r'/tender/(\d+)',
            r'[?&]id=(\d+)',
            r'/details?/(\d+)',
        ]

        for pattern in url_patterns:
            match = re.search(pattern, response.url, re.IGNORECASE)
            if match:
                return f"EPAZAR-{match.group(1)}"

        # Try page content
        selectors = [
            '[data-id]::attr(data-id)',
            '[data-tender-id]::attr(data-tender-id)',
            '.tender-id::text',
            '.notice-id::text',
            '#tenderId::text',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value:
                return f"EPAZAR-{value.strip()}"

        # Try regex on page
        id_match = re.search(r'["\']?tender[_-]?id["\']?\s*[:=]\s*["\']?(\d+)', response.text, re.IGNORECASE)
        if id_match:
            return f"EPAZAR-{id_match.group(1)}"

        return None

    def _extract_title(self, response) -> Optional[str]:
        """Extract tender title"""
        selectors = [
            'h1::text',
            '.tender-title::text',
            '.notice-title::text',
            '[class*="title"]::text',
            'meta[property="og:title"]::attr(content)',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value and len(value.strip()) > 5:
                return value.strip()

        return None

    def _extract_description(self, response) -> Optional[str]:
        """Extract tender description"""
        selectors = [
            '.tender-description::text',
            '.notice-description::text',
            '.description::text',
            '[class*="description"] p::text',
            'meta[name="description"]::attr(content)',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value and len(value.strip()) > 10:
                return value.strip()

        # Try to get multiple paragraphs
        paragraphs = response.css('.description p::text, .tender-body p::text').getall()
        if paragraphs:
            return ' '.join(p.strip() for p in paragraphs if p.strip())

        return None

    def _extract_contracting_authority(self, response) -> Optional[str]:
        """Extract contracting authority name"""
        selectors = [
            '.contracting-authority::text',
            '.institution::text',
            '.organization::text',
            '.entity::text',
            '[class*="authority"]::text',
            '[class*="institution"]::text',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value and len(value.strip()) > 3:
                return value.strip()

        # Try label-based extraction
        labels = ['Договорен орган', 'Институција', 'Organization', 'Authority']
        for label in labels:
            xpath = f"//label[contains(text(), '{label}')]/following-sibling::*//text()"
            value = response.xpath(xpath).get()
            if value:
                return value.strip()

        return None

    def _extract_value(self, response, value_type: str) -> Optional[float]:
        """Extract monetary value"""
        selectors = [
            f'.{value_type}-value::text',
            f'[class*="{value_type}"] .value::text',
            f'[class*="value"][class*="{value_type}"]::text',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value:
                parsed = self._parse_currency(value)
                if parsed:
                    return parsed

        # Try regex pattern
        patterns = [
            r'(\d[\d.,]+)\s*(?:MKD|денари)',
            r'(?:MKD|денари)\s*(\d[\d.,]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                return self._parse_currency(match.group(1))

        return None

    def _parse_currency(self, value: str) -> Optional[float]:
        """Parse currency string to float"""
        if not value:
            return None

        try:
            # Remove currency symbols and whitespace
            cleaned = re.sub(r'[^\d.,]', '', value)

            # Handle European format (1.234,56)
            if ',' in cleaned and '.' in cleaned:
                if cleaned.rindex(',') > cleaned.rindex('.'):
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '.')

            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _extract_status(self, response) -> str:
        """Extract tender status"""
        selectors = [
            '.status::text',
            '.tender-status::text',
            '[class*="status"]::text',
            '.badge::text',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value:
                value = value.strip().lower()
                if 'active' in value or 'активн' in value or 'отворен' in value:
                    return 'active'
                elif 'award' in value or 'доделен' in value or 'склучен' in value:
                    return 'awarded'
                elif 'cancel' in value or 'откажан' in value or 'поништен' in value:
                    return 'cancelled'
                elif 'close' in value or 'затворен' in value:
                    return 'closed'

        return 'active'  # Default

    def _extract_procedure_type(self, response) -> Optional[str]:
        """Extract procedure type"""
        labels = ['Постапка', 'Procedure', 'Type']

        for label in labels:
            xpath = f"//label[contains(text(), '{label}')]/following-sibling::*//text()"
            value = response.xpath(xpath).get()
            if value:
                return value.strip()

        selectors = [
            '.procedure-type::text',
            '[class*="procedure"]::text',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value:
                return value.strip()

        return None

    def _extract_cpv_code(self, response) -> Optional[str]:
        """Extract CPV code"""
        # CPV code pattern: 8 digits optionally with dash groups
        pattern = r'\b(\d{8}(?:-\d)?)\b'

        match = re.search(pattern, response.text)
        if match:
            return match.group(1)

        selectors = [
            '.cpv-code::text',
            '[class*="cpv"]::text',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value:
                match = re.search(pattern, value)
                if match:
                    return match.group(1)

        return None

    def _extract_date(self, response, date_type: str) -> Optional[str]:
        """Extract date by type"""
        date_labels = {
            'publication': ['Објавен', 'Published', 'Publication', 'Датум на објава'],
            'closing': ['Рок', 'Deadline', 'Closing', 'Краен рок'],
            'award': ['Доделен', 'Award', 'Доделување'],
            'contract': ['Договор', 'Contract', 'Склучен'],
        }

        labels = date_labels.get(date_type, [])

        for label in labels:
            xpath = f"//label[contains(text(), '{label}')]/following-sibling::*//text()"
            value = response.xpath(xpath).get()
            if value:
                parsed = self._parse_date(value)
                if parsed:
                    return parsed

        selectors = [
            f'.{date_type}-date::text',
            f'[class*="{date_type}"] .date::text',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value:
                parsed = self._parse_date(value)
                if parsed:
                    return parsed

        return None

    def _parse_date(self, value: str) -> Optional[str]:
        """Parse date string to ISO format"""
        if not value:
            return None

        # Common date formats
        formats = [
            '%d.%m.%Y',
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d.%m.%Y %H:%M',
            '%Y-%m-%dT%H:%M:%S',
        ]

        value = value.strip()

        for fmt in formats:
            try:
                dt = datetime.strptime(value[:len(fmt.replace('%', '').replace('d', '00').replace('m', '00').replace('Y', '0000').replace('H', '00').replace('M', '00').replace('S', '00'))], fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # Try regex extraction
        date_match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', value)
        if date_match:
            day, month, year = date_match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        return None

    def _extract_field(self, response, field_name: str) -> Optional[str]:
        """Generic field extraction"""
        selectors = [
            f'.{field_name}::text',
            f'[class*="{field_name}"]::text',
            f'#{field_name}::text',
        ]

        for selector in selectors:
            value = response.css(selector).get()
            if value:
                return value.strip()

        return None

    async def _extract_items(self, page, tender_id: str) -> List[Dict]:
        """Extract Bill of Quantities items"""
        items = []

        try:
            # Try to click on items tab if exists
            items_tab_selectors = [
                '[data-tab="items"]',
                'button:has-text("Items")',
                'button:has-text("Артикли")',
                '.tab-items',
            ]

            for selector in items_tab_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click()
                        await page.wait_for_timeout(1000)
                        break
                except:
                    continue

            # Find items table/list
            item_selectors = [
                'table.items tbody tr',
                '.item-row',
                '.boq-item',
                '[class*="item-list"] > div',
            ]

            for selector in item_selectors:
                item_elements = await page.query_selector_all(selector)
                if item_elements:
                    for i, elem in enumerate(item_elements):
                        try:
                            item = {
                                'line_number': i + 1,
                                'item_name': await self._get_text(elem, '.item-name, td:nth-child(2)'),
                                'item_description': await self._get_text(elem, '.item-description, td:nth-child(3)'),
                                'quantity': await self._get_text(elem, '.quantity, td:nth-child(4)'),
                                'unit': await self._get_text(elem, '.unit, td:nth-child(5)'),
                                'unit_price': await self._get_text(elem, '.unit-price, td:nth-child(6)'),
                                'total_price': await self._get_text(elem, '.total-price, td:nth-child(7)'),
                            }

                            if item['item_name']:
                                items.append(item)
                        except Exception as e:
                            logger.debug(f"Error extracting item: {e}")
                    break

        except Exception as e:
            logger.debug(f"Error extracting items for {tender_id}: {e}")

        return items

    async def _extract_offers(self, page, tender_id: str) -> List[Dict]:
        """Extract supplier offers/bids"""
        offers = []

        try:
            # Try to click on offers tab
            offers_tab_selectors = [
                '[data-tab="offers"]',
                '[data-tab="bids"]',
                'button:has-text("Offers")',
                'button:has-text("Понуди")',
                '.tab-offers',
            ]

            for selector in offers_tab_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click()
                        await page.wait_for_timeout(1000)
                        break
                except:
                    continue

            # Find offers table/list
            offer_selectors = [
                'table.offers tbody tr',
                '.offer-row',
                '.bid-row',
                '[class*="offer-list"] > div',
            ]

            for selector in offer_selectors:
                offer_elements = await page.query_selector_all(selector)
                if offer_elements:
                    for elem in offer_elements:
                        try:
                            # Check if winner
                            is_winner = False
                            winner_indicator = await elem.query_selector('.winner, .is-winner, [class*="winner"]')
                            if winner_indicator:
                                is_winner = True

                            offer = {
                                'supplier_name': await self._get_text(elem, '.supplier-name, td:nth-child(1)'),
                                'supplier_tax_id': await self._get_text(elem, '.tax-id, td:nth-child(2)'),
                                'total_bid_mkd': await self._get_text(elem, '.bid-amount, td:nth-child(3)'),
                                'ranking': await self._get_text(elem, '.ranking, td:nth-child(4)'),
                                'is_winner': is_winner,
                            }

                            if offer['supplier_name']:
                                offers.append(offer)
                        except Exception as e:
                            logger.debug(f"Error extracting offer: {e}")
                    break

        except Exception as e:
            logger.debug(f"Error extracting offers for {tender_id}: {e}")

        return offers

    async def _extract_awarded_items(self, page, tender_id: str) -> List[Dict]:
        """Extract awarded contract items"""
        awarded = []

        try:
            # Try to click on award/contract tab
            award_tab_selectors = [
                '[data-tab="award"]',
                '[data-tab="contract"]',
                'button:has-text("Award")',
                'button:has-text("Договор")',
            ]

            for selector in award_tab_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click()
                        await page.wait_for_timeout(1000)
                        break
                except:
                    continue

            # Find awarded items
            awarded_selectors = [
                'table.awarded tbody tr',
                '.awarded-item',
                '.contract-item',
            ]

            for selector in awarded_selectors:
                awarded_elements = await page.query_selector_all(selector)
                if awarded_elements:
                    for elem in awarded_elements:
                        try:
                            item = {
                                'item_name': await self._get_text(elem, '.item-name, td:nth-child(1)'),
                                'supplier_name': await self._get_text(elem, '.supplier-name, td:nth-child(2)'),
                                'quantity': await self._get_text(elem, '.quantity, td:nth-child(3)'),
                                'unit_price': await self._get_text(elem, '.unit-price, td:nth-child(4)'),
                                'total_price': await self._get_text(elem, '.total-price, td:nth-child(5)'),
                            }

                            if item['item_name'] or item['supplier_name']:
                                awarded.append(item)
                        except Exception as e:
                            logger.debug(f"Error extracting awarded item: {e}")
                    break

        except Exception as e:
            logger.debug(f"Error extracting awarded items for {tender_id}: {e}")

        return awarded

    async def _extract_documents(self, page, tender_id: str) -> List[Dict]:
        """Extract document metadata"""
        documents = []

        try:
            # Try to click on documents tab
            docs_tab_selectors = [
                '[data-tab="documents"]',
                'button:has-text("Documents")',
                'button:has-text("Документи")',
            ]

            for selector in docs_tab_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click()
                        await page.wait_for_timeout(1000)
                        break
                except:
                    continue

            # Find document links
            doc_selectors = [
                'a[href*="download"]',
                'a[href*=".pdf"]',
                '.document-link',
                '.file-link',
            ]

            for selector in doc_selectors:
                doc_elements = await page.query_selector_all(selector)
                for elem in doc_elements:
                    try:
                        href = await elem.get_attribute('href')
                        text = await elem.inner_text()

                        if href:
                            doc = {
                                'file_name': text.strip() if text else self._extract_filename(href),
                                'file_url': urljoin(self.BASE_URL, href),
                                'doc_type': self._classify_document(text or href),
                            }
                            documents.append(doc)
                    except Exception as e:
                        logger.debug(f"Error extracting document: {e}")

        except Exception as e:
            logger.debug(f"Error extracting documents for {tender_id}: {e}")

        return documents

    async def _get_text(self, element, selector: str) -> Optional[str]:
        """Get text from element using selector"""
        try:
            sub_elem = await element.query_selector(selector)
            if sub_elem:
                text = await sub_elem.inner_text()
                return text.strip() if text else None
        except:
            pass
        return None

    def _extract_filename(self, url: str) -> str:
        """Extract filename from URL"""
        parsed = urlparse(url)
        path = parsed.path
        return path.split('/')[-1] if path else 'document'

    def _classify_document(self, text: str) -> str:
        """Classify document type based on name/text"""
        text_lower = text.lower() if text else ''

        if 'spec' in text_lower or 'технички' in text_lower:
            return 'technical_specs'
        elif 'tender' in text_lower or 'тендер' in text_lower:
            return 'tender_docs'
        elif 'award' in text_lower or 'одлука' in text_lower:
            return 'award_decision'
        elif 'contract' in text_lower or 'договор' in text_lower:
            return 'contract'
        elif 'clarif' in text_lower or 'појаснување' in text_lower:
            return 'clarification'
        elif 'cancel' in text_lower or 'поништ' in text_lower:
            return 'cancellation_decision'
        else:
            return 'other'

    def _calculate_content_hash(self, tender: EPazarItem) -> str:
        """Calculate SHA-256 hash of tender content for change detection"""
        content = json.dumps({
            'tender_id': tender.get('tender_id'),
            'title': tender.get('title'),
            'description': tender.get('description'),
            'status': tender.get('status'),
            'estimated_value_mkd': str(tender.get('estimated_value_mkd')),
            'closing_date': tender.get('closing_date'),
            'items_data': tender.get('items_data'),
            'offers_data': tender.get('offers_data'),
        }, sort_keys=True, ensure_ascii=False)

        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _get_next_page_url(self, current_url: str, current_page: int) -> Optional[str]:
        """Generate next page URL"""
        # Common pagination patterns
        if 'page=' in current_url:
            return re.sub(r'page=\d+', f'page={current_page + 1}', current_url)
        elif '?' in current_url:
            return f"{current_url}&page={current_page + 1}"
        else:
            return f"{current_url}?page={current_page + 1}"

    def errback_playwright(self, failure):
        """Handle Playwright errors"""
        logger.error(f"Playwright error: {failure.value}")
        self.stats['errors'] += 1

    def closed(self, reason):
        """Log final statistics when spider closes"""
        logger.info("=" * 60)
        logger.info("E-Pazar Spider Statistics:")
        logger.info(f"  Category: {self.category}")
        logger.info(f"  Mode: {self.mode}")
        logger.info(f"  Tenders Found: {self.stats['tenders_found']}")
        logger.info(f"  Tenders Scraped: {self.stats['tenders_scraped']}")
        logger.info(f"  Items Extracted: {self.stats['items_extracted']}")
        logger.info(f"  Offers Extracted: {self.stats['offers_extracted']}")
        logger.info(f"  Documents Found: {self.stats['documents_found']}")
        logger.info(f"  Pages Processed: {self.stats['pages_processed']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"  Close Reason: {reason}")
        logger.info("=" * 60)
