#!/usr/bin/env python3
"""
E-Pazar API Spider - JSON API-based scraper for e-pazar.gov.mk
Electronic Public Procurement Marketplace of North Macedonia

This spider uses the public JSON API endpoints (no browser needed).
Much faster and more reliable than Playwright browser automation.

API Endpoints:
- /api/tender/searchActiveTenders - Active procurements (823+)
- /api/tender/searchCompletedsTenders - Completed with decisions (813+)
- /api/contractDocument/getAllSignedContracts - Signed contracts (1116+)
- /api/economicoperator/getAllEO - All suppliers
- /api/contractauthority/getAllCA - All contracting authorities
"""

import scrapy
import json
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Generator

logger = logging.getLogger(__name__)


class EPazarApiItem(scrapy.Item):
    """E-Pazar tender/contract item for database"""
    # Core identifiers
    tender_id = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()

    # Contracting authority
    contracting_authority = scrapy.Field()
    contracting_authority_id = scrapy.Field()
    contracting_authority_city = scrapy.Field()
    contracting_authority_category = scrapy.Field()
    contracting_authority_activity = scrapy.Field()
    contracting_authority_address = scrapy.Field()
    contracting_authority_postcode = scrapy.Field()

    # Values
    estimated_value_mkd = scrapy.Field()
    contract_value_mkd = scrapy.Field()

    # Procedure & Status
    procurement_type = scrapy.Field()
    status = scrapy.Field()
    tender_status_id = scrapy.Field()

    # Dates
    publication_date = scrapy.Field()
    deadline_date = scrapy.Field()
    contract_date = scrapy.Field()
    closing_date = scrapy.Field()

    # Winner/Supplier (for signed contracts)
    winner_name = scrapy.Field()
    winner_id = scrapy.Field()
    winner_address = scrapy.Field()
    winner_city = scrapy.Field()
    winner_type = scrapy.Field()

    # Contract details
    contract_number = scrapy.Field()
    contract_document_id = scrapy.Field()
    contract_filename = scrapy.Field()
    evident_number = scrapy.Field()

    # Source
    source_url = scrapy.Field()
    source_category = scrapy.Field()
    language = scrapy.Field()

    # Documents data (JSON string for pipeline)
    documents_data = scrapy.Field()

    # Items/Products data (JSON string for pipeline)
    items_data = scrapy.Field()

    # Contact info
    contact_person = scrapy.Field()
    contact_email = scrapy.Field()
    contact_phone = scrapy.Field()
    delivery_address = scrapy.Field()
    delivery_description = scrapy.Field()

    # Metadata
    scraped_at = scrapy.Field()
    content_hash = scrapy.Field()
    raw_data = scrapy.Field()  # Store original JSON


class EPazarApiSpider(scrapy.Spider):
    """
    JSON API-based spider for e-pazar.gov.mk

    Usage:
        scrapy crawl epazar_api -a category=active
        scrapy crawl epazar_api -a category=completed
        scrapy crawl epazar_api -a category=contracts
        scrapy crawl epazar_api -a category=all
        scrapy crawl epazar_api -a category=all -a max_pages=5
    """

    name = 'epazar_api'
    allowed_domains = ['e-pazar.gov.mk']

    BASE_URL = 'https://e-pazar.gov.mk'

    # JSON API endpoints
    API_ENDPOINTS = {
        'active': '/api/tender/searchActiveTenders',
        'completed': '/api/tender/searchCompletedsTenders',
        'contracts': '/api/contractDocument/getAllSignedContracts',
    }

    # Detail API endpoints
    DETAIL_ENDPOINT = '/api/tender/getPublishedTenderDetails'
    ITEMS_ENDPOINT = '/api/tenderproductrequirement/getTenderProductRequirementsbyTenderId'

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,  # Faster since it's just JSON API
        "CONCURRENT_REQUESTS": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "ROBOTSTXT_OBEY": True,
        "ITEM_PIPELINES": {
            "scraper.pipelines.EPazarValidationPipeline": 100,
            "scraper.pipelines.EPazarDatabasePipeline": 300,
        },
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; nabavkidata-bot/1.0; +https://nabavkidata.com/bot)",
        }
    }

    def __init__(self, category='all', max_pages=None, max_items=None, page_size=50, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category.lower()
        self.max_pages = int(max_pages) if max_pages else None
        self.max_items = int(max_items) if max_items else None
        self.page_size = int(page_size)
        self.items_scraped = 0

        # Statistics
        self.stats = {
            'tenders_scraped': 0,
            'contracts_scraped': 0,
            'pages_processed': 0,
            'errors': 0,
        }

        logger.info(f"EPazar API Spider: category={self.category}, max_pages={self.max_pages}, max_items={self.max_items}, page_size={self.page_size}")

    def start_requests(self):
        """Generate initial API requests"""

        categories = ['active', 'completed', 'contracts'] if self.category == 'all' else [self.category]

        for cat in categories:
            if cat not in self.API_ENDPOINTS:
                logger.warning(f"Unknown category: {cat}")
                continue

            endpoint = self.API_ENDPOINTS[cat]
            url = f"{self.BASE_URL}{endpoint}?PageNumber=0&PageSize={self.page_size}"

            if cat == 'active':
                url += "&TenderActiveStatus=all"

            logger.info(f"Starting category: {cat}, URL: {url}")

            yield scrapy.Request(
                url,
                callback=self.parse_api_response,
                meta={
                    'category': cat,
                    'page_number': 0,
                    'endpoint': endpoint,
                },
                errback=self.errback_request,
            )

    def _should_stop_scraping(self) -> bool:
        """Check if we should stop due to max_items limit"""
        if self.max_items and self.items_scraped >= self.max_items:
            return True
        return False

    def _yield_item(self, item):
        """Helper to yield item and track count"""
        self.items_scraped += 1
        return item

    def parse_api_response(self, response):
        """Parse JSON API response"""
        category = response.meta['category']
        page_number = response.meta['page_number']
        endpoint = response.meta['endpoint']

        # Check max_items limit
        if self._should_stop_scraping():
            logger.info(f"[{category}] Reached max_items limit: {self.max_items}")
            return

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            self.stats['errors'] += 1
            return

        total_pages = data.get('totalPages', 0)
        total_count = data.get('totalCount', 0)
        items = data.get('data', [])

        logger.info(f"[{category}] Page {page_number + 1}/{total_pages}, got {len(items)} items (total: {total_count})")
        self.stats['pages_processed'] += 1

        # Process items - fetch detail data for each tender (not for contracts which already have full data)
        for item_data in items:
            # Check max_items limit before processing each item
            if self._should_stop_scraping():
                logger.info(f"[{category}] Reached max_items limit: {self.max_items}")
                return

            tender_id_num = item_data.get('tenderId')

            if category != 'contracts' and tender_id_num:
                # For active/completed tenders, fetch detail data
                detail_url = f"{self.BASE_URL}{self.DETAIL_ENDPOINT}/{tender_id_num}"
                yield scrapy.Request(
                    detail_url,
                    callback=self.parse_tender_detail,
                    meta={
                        'category': category,
                        'list_data': item_data,
                        'tender_id_num': tender_id_num,
                    },
                    errback=self.errback_request,
                    dont_filter=True,
                )
            else:
                # For contracts, process directly (already has full data)
                parsed_item = self._parse_item(item_data, category, None, None)
                if parsed_item:
                    yield self._yield_item(parsed_item)
                    self.stats['contracts_scraped'] += 1

        # Pagination - request next page (unless we hit max_items)
        next_page = page_number + 1

        if next_page < total_pages:
            # Check max_items limit before requesting next page
            if self._should_stop_scraping():
                logger.info(f"[{category}] Reached max_items limit: {self.max_items}, stopping pagination")
                return

            if self.max_pages and next_page >= self.max_pages:
                logger.info(f"[{category}] Reached max pages limit: {self.max_pages}")
                return

            next_url = f"{self.BASE_URL}{endpoint}?PageNumber={next_page}&PageSize={self.page_size}"
            if category == 'active':
                next_url += "&TenderActiveStatus=all"

            yield scrapy.Request(
                next_url,
                callback=self.parse_api_response,
                meta={
                    'category': category,
                    'page_number': next_page,
                    'endpoint': endpoint,
                },
                errback=self.errback_request,
            )

    def parse_tender_detail(self, response):
        """Parse tender detail API response and then fetch items"""
        category = response.meta['category']
        list_data = response.meta['list_data']
        tender_id_num = response.meta['tender_id_num']

        try:
            detail_data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse detail for tender {tender_id_num}: {e}")
            # Fall back to list data only
            parsed_item = self._parse_item(list_data, category, None, None)
            if parsed_item and not self._should_stop_scraping():
                yield self._yield_item(parsed_item)
                self.stats['tenders_scraped'] += 1
            return

        # Now fetch items data
        items_url = f"{self.BASE_URL}{self.ITEMS_ENDPOINT}/{tender_id_num}?PageNumber=0&PageSize=100"
        yield scrapy.Request(
            items_url,
            callback=self.parse_tender_items,
            meta={
                'category': category,
                'list_data': list_data,
                'detail_data': detail_data,
                'tender_id_num': tender_id_num,
            },
            errback=self.errback_items_request,
            dont_filter=True,
        )

    def errback_items_request(self, failure):
        """Handle items request errors - still yield the tender without items"""
        request = failure.request
        category = request.meta['category']
        list_data = request.meta['list_data']
        detail_data = request.meta.get('detail_data')

        logger.warning(f"Items request failed, yielding tender without items: {failure.value}")

        parsed_item = self._parse_item(list_data, category, detail_data, None)
        if parsed_item:
            # Can't yield from errback, so just log
            logger.info(f"Would yield tender without items: {parsed_item.get('tender_id')}")
        self.stats['errors'] += 1

    def parse_tender_items(self, response):
        """Parse tender items/products API response"""
        category = response.meta['category']
        list_data = response.meta['list_data']
        detail_data = response.meta.get('detail_data')
        tender_id_num = response.meta['tender_id_num']

        items_data = None
        try:
            items_response = json.loads(response.text)
            items_list = items_response.get('data', [])
            if items_list:
                # Simplify items data for storage
                items_data = [{
                    'line_number': item.get('tenderRequirementOrderNumber', 0),
                    'item_name': item.get('tenderProductName', ''),
                    'item_description': item.get('tenderProductDescription', ''),
                    'quantity': item.get('tenderProductQuantity'),
                    'unit': item.get('tenderProductMesureUnitName', ''),
                } for item in items_list]
                logger.info(f"Found {len(items_data)} items for tender {tender_id_num}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse items for tender {tender_id_num}: {e}")

        # Now create the final item with all data
        parsed_item = self._parse_item(list_data, category, detail_data, items_data)
        if parsed_item and not self._should_stop_scraping():
            yield self._yield_item(parsed_item)
            self.stats['tenders_scraped'] += 1

    def _parse_item(self, data: Dict, category: str, detail_data: Optional[Dict] = None, items_data: Optional[List] = None) -> Optional[EPazarApiItem]:
        """Parse a single tender/contract from JSON"""
        try:
            item = EPazarApiItem()

            if category == 'contracts':
                # Signed contract structure
                tender = data.get('tender', {})
                ca = data.get('contractAuthotiry', {})  # Note: API has typo "Authotiry"
                eo = data.get('economicOperator', {})

                item['tender_id'] = f"EPAZAR-{data.get('tenderId', '')}"
                item['title'] = tender.get('tenderName', '')
                item['contract_number'] = tender.get('tenderNumber', '')
                item['contract_document_id'] = data.get('contractDocumentId')
                item['contract_filename'] = data.get('fileName')
                item['evident_number'] = data.get('evidentNumber')

                # Contracting authority - full details from signed contracts
                item['contracting_authority'] = ca.get('contractAuthorityName', '')
                item['contracting_authority_id'] = ca.get('contractAuthorityId')
                item['contracting_authority_city'] = ca.get('contractAuthorityCity', '')
                item['contracting_authority_category'] = ca.get('contractAuthorityCategoryName', '')
                item['contracting_authority_activity'] = ca.get('contractAuthorityMainActivityName', '')
                item['contracting_authority_address'] = ca.get('contractAuthorityAddress', '')
                item['contracting_authority_postcode'] = ca.get('contractAuthorityPostCode', '')

                # Winner/Supplier - full details
                item['winner_name'] = eo.get('economicOperatorName', '')
                item['winner_id'] = eo.get('economicOperatorId')
                item['winner_address'] = eo.get('economicOperatorAddress', '')
                item['winner_city'] = eo.get('economicOperatorCity', '')
                item['winner_type'] = eo.get('economicOperatorType', '')

                # Values - contractValueWithDdv is the awarded value (with VAT)
                item['contract_value_mkd'] = data.get('contractValueWithDdv')

                # Dates
                item['contract_date'] = self._parse_date(data.get('dateSigned'))
                item['publication_date'] = self._parse_date(data.get('createTime'))

                # Status
                item['status'] = 'signed'
                item['procurement_type'] = tender.get('tenderProcurementType', '')

                # Contract document as documents_data
                if data.get('fileName'):
                    docs = [{
                        'doc_type': 'contract',
                        'file_name': data.get('fileName'),
                        'file_url': f"https://e-pazar.gov.mk/api/contractDocument/download/{data.get('contractDocumentId')}"
                    }]
                    item['documents_data'] = json.dumps(docs, ensure_ascii=False)

            else:
                # Active or Completed tender structure
                item['tender_id'] = f"EPAZAR-{data.get('tenderId', '')}"
                item['title'] = data.get('tenderName', '')
                item['contract_number'] = data.get('tenderNumber', '')

                # Contracting authority - from list data
                item['contracting_authority'] = data.get('contractAuthorityName', '')
                item['contracting_authority_id'] = data.get('contractAuthorityId')

                # If we have detail_data, extract additional fields
                if detail_data:
                    # Description from detail API
                    item['description'] = detail_data.get('tenderDescription', '')

                    # Contact info from detail API
                    item['contact_person'] = detail_data.get('tenderContactPerson', '')
                    item['contact_email'] = detail_data.get('tenderContactMail', '')
                    item['contact_phone'] = detail_data.get('tenderContactPhone', '')
                    item['delivery_address'] = detail_data.get('tenderDeliveryAddress', '')
                    item['delivery_description'] = detail_data.get('tenderDeliveryDescription', '')

                    # Enhanced contracting authority from detail
                    ca = detail_data.get('contractAuthority', {})
                    if ca:
                        item['contracting_authority'] = ca.get('contractAuthorityName', '') or item.get('contracting_authority', '')
                        item['contracting_authority_city'] = ca.get('contractAuthorityCity', '')
                        item['contracting_authority_address'] = ca.get('contractAuthorityAddress', '')
                        item['contracting_authority_postcode'] = ca.get('contractAuthorityPostCode', '')
                        item['contracting_authority_category'] = ca.get('contractAuthorityCategoryName', '')
                        item['contracting_authority_activity'] = ca.get('contractAuthorityMainActivityName', '')

                    # Documents from detail API (more complete)
                    tender_docs = detail_data.get('tenderDocuments', [])
                    if tender_docs:
                        docs = []
                        for doc in tender_docs:
                            doc_type = 'evaluation_report' if doc.get('documentTypeId') == 2 else 'tender_document'
                            docs.append({
                                'doc_type': doc_type,
                                'file_name': doc.get('fileName'),
                                'file_url': doc.get('fileLocation'),
                                'evident_number': doc.get('evidentNumber'),
                                'upload_date': self._parse_date(doc.get('createTime'))
                            })
                        item['documents_data'] = json.dumps(docs, ensure_ascii=False)
                        logger.info(f"Found {len(docs)} documents for tender {item['tender_id']}")
                else:
                    # Fallback: Extract tenderDocuments if present in list data (completed tenders have these)
                    tender_docs = data.get('tenderDocuments', [])
                    if tender_docs:
                        docs = []
                        for doc in tender_docs:
                            doc_type = 'evaluation_report' if doc.get('documentTypeId') == 2 else 'tender_document'
                            docs.append({
                                'doc_type': doc_type,
                                'file_name': doc.get('fileName'),
                                'file_url': doc.get('fileLocation'),
                                'evident_number': doc.get('evidentNumber'),
                                'upload_date': self._parse_date(doc.get('createTime'))
                            })
                        item['documents_data'] = json.dumps(docs, ensure_ascii=False)
                        logger.info(f"Found {len(docs)} documents (from list) for tender {item['tender_id']}")

                # Items data if available
                if items_data:
                    item['items_data'] = json.dumps(items_data, ensure_ascii=False)
                    logger.info(f"Added {len(items_data)} items for tender {item['tender_id']}")

                # Dates
                item['publication_date'] = self._parse_date(data.get('tenderParticipationStartDate'))
                item['deadline_date'] = self._parse_date(data.get('tenderParticipationDeadline'))
                item['closing_date'] = self._parse_date(data.get('tenderParticipationDeadline'))

                # Status - map tenderStatusId to meaningful status
                status_id = data.get('tenderStatusId', 0)
                item['tender_status_id'] = status_id
                if category == 'active':
                    item['status'] = 'active'
                elif category == 'completed':
                    # Status 7 = completed with decision
                    item['status'] = 'completed' if status_id == 7 else 'awarded'
                else:
                    item['status'] = 'unknown'

                item['procurement_type'] = data.get('tenderProcurementType', '')

            # Common fields
            item['source_url'] = f"{self.BASE_URL}/tender/{data.get('tenderId', '')}"
            item['source_category'] = f"epazar_{category}"
            item['language'] = 'mk'
            item['scraped_at'] = datetime.utcnow().isoformat()

            # Store raw data for reference
            item['raw_data'] = json.dumps(data, ensure_ascii=False)

            # Content hash for change detection
            item['content_hash'] = self._calculate_hash(item)

            return item

        except Exception as e:
            logger.error(f"Error parsing item: {e}")
            self.stats['errors'] += 1
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse date string to YYYY-MM-DD format"""
        if not date_str:
            return None

        try:
            # Handle ISO format: 2025-11-25T14:30:00
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            return date_str[:10]  # Just take first 10 chars
        except Exception:
            return None

    def _calculate_hash(self, item: EPazarApiItem) -> str:
        """Calculate content hash for change detection"""
        content = json.dumps({
            'tender_id': item.get('tender_id'),
            'title': item.get('title'),
            'status': item.get('status'),
            'contract_value_mkd': str(item.get('contract_value_mkd', '')),
            'winner_name': item.get('winner_name', ''),
        }, sort_keys=True, ensure_ascii=False)

        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def errback_request(self, failure):
        """Handle request errors"""
        logger.error(f"Request failed: {failure.value}")
        self.stats['errors'] += 1

    def closed(self, reason):
        """Log final statistics"""
        logger.info("=" * 60)
        logger.info("E-Pazar API Spider Statistics:")
        logger.info(f"  Category: {self.category}")
        logger.info(f"  Tenders Scraped: {self.stats['tenders_scraped']}")
        logger.info(f"  Contracts Scraped: {self.stats['contracts_scraped']}")
        logger.info(f"  Pages Processed: {self.stats['pages_processed']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"  Close Reason: {reason}")
        logger.info("=" * 60)
