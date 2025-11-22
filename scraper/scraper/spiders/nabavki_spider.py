"""
Nabavki.gov.mk Spider - Structure-Change Resilient Design

RESILIENCE STRATEGY:
1. Multi-selector fallback chains (try multiple CSS/XPath)
2. Content-based extraction (pattern matching > hardcoded paths)
3. Flexible field detection (labels/keywords > positions)
4. Graceful degradation (continue on missing fields)
5. Extraction success monitoring (detect structure changes)
"""
import scrapy
from scrapy import Request
from datetime import datetime
import re
import logging
from scraper.items import TenderItem, DocumentItem

logger = logging.getLogger(__name__)


class FieldExtractor:
    """
    Resilient field extraction with multiple fallback strategies.

    Survives structure changes by trying multiple approaches per field.
    """

    @staticmethod
    def extract_with_fallbacks(response, field_name, selectors):
        """
        Try multiple selectors until one succeeds.

        Args:
            response: Scrapy response object
            field_name: Name of field being extracted (for logging)
            selectors: List of selector dictionaries with 'type' and 'path'

        Returns:
            Extracted value or None
        """
        for i, selector_config in enumerate(selectors):
            try:
                sel_type = selector_config['type']
                sel_path = selector_config['path']

                if sel_type == 'css':
                    result = response.css(sel_path).get()
                elif sel_type == 'xpath':
                    result = response.xpath(sel_path).get()
                elif sel_type == 'regex':
                    pattern = selector_config['pattern']
                    text = response.text
                    match = re.search(pattern, text)
                    result = match.group(1) if match else None
                elif sel_type == 'label':
                    # Extract by finding label then getting adjacent value
                    label = selector_config['label']
                    result = FieldExtractor._extract_by_label(response, label)
                else:
                    continue

                if result and result.strip():
                    if i > 0:
                        logger.debug(
                            f"{field_name}: Fallback #{i} succeeded ({sel_type})"
                        )
                    return result.strip()

            except Exception as e:
                logger.debug(f"{field_name}: Selector {i} failed - {e}")
                continue

        logger.warning(f"{field_name}: All selectors failed")
        return None

    @staticmethod
    def _extract_by_label(response, label_text):
        """
        Find value by locating a label/key first.

        Example: "Tenderer: Company XYZ" → extracts "Company XYZ"
        """
        # Try various label patterns
        patterns = [
            # Macedonian/English with colon
            rf'{re.escape(label_text)}\s*:\s*([^\n<]+)',
            # In table cells
            rf'<td[^>]*>{re.escape(label_text)}</td>\s*<td[^>]*>([^<]+)</td>',
            # In divs
            rf'<div[^>]*>{re.escape(label_text)}[:\s]*</div>\s*<div[^>]*>([^<]+)</div>',
        ]

        for pattern in patterns:
            match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return None


class NabavkiSpider(scrapy.Spider):
    """
    Resilient spider for e-nabavki.gov.mk

    Features:
    - Multi-selector fallback chains
    - Content-based field detection
    - Extraction success tracking
    - Automatic structure change alerts
    """

    name = "nabavki"
    allowed_domains = ["e-nabavki.gov.mk"]

    # Allow custom start_urls via spider arguments
    def __init__(self, start_url=None, *args, **kwargs):
        super(NabavkiSpider, self).__init__(*args, **kwargs)

        if start_url:
            self.start_urls = [start_url]
        else:
            # Default starting points (multiple entry points for resilience)
            self.start_urls = [
                "https://e-nabavki.gov.mk/PublicAccess/home.aspx",
                "https://e-nabavki.gov.mk/PublicAccess/Tenders.aspx",
            ]

        # Track extraction success for monitoring
        self.extraction_stats = {
            'total_tenders': 0,
            'successful_extractions': {},
            'failed_fields': {},
        }

    custom_settings = {
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 1,
        'RETRY_TIMES': 3,
        'USER_AGENT': 'Mozilla/5.0 (compatible; nabavkidata-bot/1.0; +https://nabavkidata.com/bot)',
        # Enable Playwright for pages that need JavaScript
        'PLAYWRIGHT_CONTEXTS': {
            'default': {
                'viewport': {'width': 1920, 'height': 1080},
            }
        }
    }

    def parse(self, response):
        """
        Parse listing page - extract tender links

        Resilience: Multiple fallback selectors for tender links
        """
        logger.info(f"Parsing listing page: {response.url}")

        # FALLBACK CHAIN: Try multiple ways to find tender links
        tender_links = []

        # Strategy 1: Common tender list selectors
        selectors = [
            'div.tender-item a::attr(href)',
            'tr.tender-row a::attr(href)',
            'div.procurement-item a::attr(href)',
            'table.tenders a::attr(href)',
            'div[class*="tender"] a::attr(href)',
            'tr[class*="tender"] a::attr(href)',
            # Generic: Any link with "tender" or "nabavka" in href
            'a[href*="tender"]::attr(href)',
            'a[href*="Tender"]::attr(href)',
            'a[href*="nabavka"]::attr(href)',
        ]

        for selector in selectors:
            links = response.css(selector).getall()
            if links:
                tender_links.extend(links)
                logger.info(f"Found {len(links)} tender links using: {selector}")
                break

        # Deduplicate
        tender_links = list(set(tender_links))

        if not tender_links:
            logger.warning(f"No tender links found on {response.url}")
            # Try Playwright for JS-rendered content
            if 'playwright' not in response.meta:
                logger.info("Retrying with Playwright...")
                yield Request(
                    response.url,
                    callback=self.parse,
                    meta={'playwright': True},
                    dont_filter=True
                )

        # Follow tender links
        for link in tender_links:
            yield response.follow(link, callback=self.parse_tender_detail)

        # PAGINATION: Multiple fallback strategies
        next_page = self._find_next_page(response)
        if next_page:
            logger.info(f"Following pagination: {next_page}")
            yield response.follow(next_page, callback=self.parse)

    def _find_next_page(self, response):
        """
        Find pagination link with multiple fallbacks
        """
        selectors = [
            'a.next::attr(href)',
            'a.pagination-next::attr(href)',
            'a[rel="next"]::attr(href)',
            'a:contains("Next")::attr(href)',
            'a:contains("Следно")::attr(href)',  # Macedonian
            'a:contains("»")::attr(href)',
            'a[title*="next" i]::attr(href)',
        ]

        for selector in selectors:
            next_page = response.css(selector).get()
            if next_page:
                return next_page

        return None

    def parse_tender_detail(self, response):
        """
        Extract tender details with maximum resilience

        Uses FieldExtractor for multi-selector fallbacks
        """
        self.extraction_stats['total_tenders'] += 1

        logger.info(f"Parsing tender: {response.url}")

        # Create TenderItem
        tender = TenderItem()

        # TENDER ID (critical field)
        tender['tender_id'] = self._extract_tender_id(response)

        # TITLE - Multiple fallback selectors
        tender['title'] = FieldExtractor.extract_with_fallbacks(
            response, 'title', [
                {'type': 'css', 'path': 'h1.tender-title::text'},
                {'type': 'css', 'path': 'h1::text'},
                {'type': 'css', 'path': 'div.title::text'},
                {'type': 'css', 'path': 'span.tender-name::text'},
                {'type': 'xpath', 'path': '//h1/text()'},
                {'type': 'label', 'label': 'Назив'},  # Macedonian: "Title"
                {'type': 'label', 'label': 'Title'},
                {'type': 'label', 'label': 'Име'},
            ]
        )

        # DESCRIPTION
        tender['description'] = self._extract_description(response)

        # PROCURING ENTITY
        tender['procuring_entity'] = FieldExtractor.extract_with_fallbacks(
            response, 'procuring_entity', [
                {'type': 'css', 'path': 'div.procuring-entity::text'},
                {'type': 'css', 'path': 'span.entity::text'},
                {'type': 'css', 'path': 'div.organization::text'},
                {'type': 'label', 'label': 'Нарачател'},  # Macedonian
                {'type': 'label', 'label': 'Procuring Entity'},
                {'type': 'label', 'label': 'Contracting Authority'},
                {'type': 'regex', 'pattern': r'(?:Нарачател|Entity)[:\s]+([^\n<]+)'},
            ]
        )

        # CATEGORY (content-based)
        tender['category'] = self._extract_category(response)

        # CPV CODE
        tender['cpv_code'] = FieldExtractor.extract_with_fallbacks(
            response, 'cpv_code', [
                {'type': 'css', 'path': 'span.cpv-code::text'},
                {'type': 'css', 'path': 'div.cpv::text'},
                {'type': 'label', 'label': 'CPV'},
                {'type': 'label', 'label': 'CPV Код'},
                {'type': 'regex', 'pattern': r'CPV[:\s]+([0-9-]+)'},
            ]
        )

        # DATES
        tender['opening_date'] = self._extract_date(response, 'opening')
        tender['closing_date'] = self._extract_date(response, 'closing')
        tender['publication_date'] = self._extract_date(response, 'publication')

        # VALUES
        tender['estimated_value_mkd'] = self._extract_currency(response, 'estimated', 'MKD')
        tender['estimated_value_eur'] = self._extract_currency(response, 'estimated', 'EUR')
        tender['actual_value_mkd'] = self._extract_currency(response, 'actual', 'MKD')
        tender['actual_value_eur'] = self._extract_currency(response, 'actual', 'EUR')

        # STATUS (content-based detection)
        tender['status'] = self._extract_status(response)

        # WINNER (for awarded tenders)
        tender['winner'] = FieldExtractor.extract_with_fallbacks(
            response, 'winner', [
                {'type': 'css', 'path': 'div.winner::text'},
                {'type': 'css', 'path': 'span.awarded-to::text'},
                {'type': 'label', 'label': 'Добитник'},  # Macedonian: "Winner"
                {'type': 'label', 'label': 'Winner'},
                {'type': 'label', 'label': 'Awarded to'},
            ]
        )

        # METADATA
        tender['source_url'] = response.url
        tender['language'] = 'mk'
        tender['scraped_at'] = datetime.utcnow()

        # Track extraction success
        self._track_extraction_success(tender)

        # Yield tender item
        yield tender

        # Extract document links
        yield from self._extract_documents(response, tender['tender_id'])

    def _extract_tender_id(self, response):
        """
        Extract tender ID with multiple fallback strategies
        """
        # Strategy 1: From URL parameters
        url = response.url
        patterns = [
            r'[?&]id=([^&]+)',
            r'[?&]tenderid=([^&]+)',
            r'[?&]tender=([^&]+)',
            r'/tender/([^/?]+)',
            r'/(\d+)/?$',
        ]

        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)

        # Strategy 2: From page content
        tender_id = FieldExtractor.extract_with_fallbacks(
            response, 'tender_id', [
                {'type': 'css', 'path': 'span.tender-id::text'},
                {'type': 'css', 'path': 'div.reference-number::text'},
                {'type': 'label', 'label': 'Број'},  # Macedonian: "Number"
                {'type': 'label', 'label': 'Reference'},
                {'type': 'regex', 'pattern': r'ID[:\s]+([A-Z0-9/-]+)'},
            ]
        )

        if tender_id:
            return tender_id

        # Fallback: Use URL hash
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _extract_description(self, response):
        """
        Extract description from multiple possible locations
        """
        # Try structured selectors first
        desc = FieldExtractor.extract_with_fallbacks(
            response, 'description', [
                {'type': 'css', 'path': 'div.description::text'},
                {'type': 'css', 'path': 'div.tender-description::text'},
                {'type': 'css', 'path': 'p.description::text'},
            ]
        )

        if desc:
            return desc

        # Fallback: Extract all text in description-like containers
        containers = response.css(
            'div[class*="description"], '
            'div[class*="content"], '
            'div[class*="details"]'
        ).getall()

        if containers:
            # Clean HTML and join
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = True
            return h.handle(containers[0]).strip()

        return None

    def _extract_category(self, response):
        """
        Determine category from content (resilient to structure changes)
        """
        # Get all text content
        text = ' '.join(response.css('body::text').getall()).lower()

        # Macedonian and English keywords
        categories = {
            'IT Equipment': ['компјутер', 'софтвер', 'хардвер', 'it', 'computer', 'software', 'hardware'],
            'Construction': ['градеж', 'изградба', 'реконструк', 'construction', 'building'],
            'Medical': ['медицин', 'здрав', 'болниц', 'medical', 'health', 'hospital'],
            'Consulting': ['консалт', 'советув', 'consulting', 'advisory'],
            'Vehicles': ['возила', 'автомобил', 'vehicle', 'automotive'],
            'Furniture': ['мебел', 'намештај', 'furniture'],
            'Food': ['храна', 'прехран', 'food', 'catering'],
        }

        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category

        return 'Other'

    def _extract_date(self, response, date_type):
        """
        Extract dates with multiple format support

        Args:
            date_type: 'opening', 'closing', or 'publication'
        """
        # Build label variations
        labels = {
            'opening': ['Отворање', 'Opening', 'Start', 'Објава'],
            'closing': ['Затворање', 'Closing', 'Deadline', 'Рок'],
            'publication': ['Објавено', 'Published', 'Publication'],
        }

        selectors = []
        for label in labels.get(date_type, []):
            selectors.append({'type': 'label', 'label': label})

        # Add CSS selectors
        selectors.extend([
            {'type': 'css', 'path': f'span.{date_type}-date::text'},
            {'type': 'css', 'path': f'div.date-{date_type}::text'},
        ])

        date_str = FieldExtractor.extract_with_fallbacks(response, f'{date_type}_date', selectors)

        if date_str:
            return self._parse_date(date_str)

        return None

    def _parse_date(self, date_str):
        """
        Parse date with multiple format support
        """
        if not date_str:
            return None

        # Clean string
        date_str = date_str.strip()

        # Try multiple formats
        formats = [
            '%d.%m.%Y',
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d.%m.%y',
            '%d/%m/%y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                continue

        logger.debug(f"Could not parse date: {date_str}")
        return None

    def _extract_currency(self, response, value_type, currency):
        """
        Extract currency values

        Args:
            value_type: 'estimated' or 'actual'
            currency: 'MKD' or 'EUR'
        """
        labels = {
            'estimated': ['Проценета', 'Estimated', 'Budget'],
            'actual': ['Вредност', 'Actual', 'Final', 'Awarded'],
        }

        selectors = []
        for label in labels.get(value_type, []):
            selectors.append({'type': 'label', 'label': f"{label} ({currency})"})
            selectors.append({'type': 'label', 'label': label})

        value_str = FieldExtractor.extract_with_fallbacks(
            response, f'{value_type}_{currency}', selectors
        )

        if value_str:
            return self._parse_currency(value_str)

        return None

    def _parse_currency(self, currency_str):
        """
        Extract numeric value from currency string
        """
        if not currency_str:
            return None

        # Remove everything except digits, commas, and dots
        cleaned = re.sub(r'[^\d,.]', '', currency_str)

        # Handle various number formats
        # European: 1.234.567,89
        # US: 1,234,567.89

        if ',' in cleaned and '.' in cleaned:
            # Determine which is decimal separator
            last_comma = cleaned.rfind(',')
            last_dot = cleaned.rfind('.')

            if last_comma > last_dot:
                # European format
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # US format
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Could be European decimal or thousands separator
            if cleaned.count(',') == 1 and len(cleaned.split(',')[1]) == 2:
                # Likely decimal
                cleaned = cleaned.replace(',', '.')
            else:
                # Likely thousands
                cleaned = cleaned.replace(',', '')

        try:
            return float(cleaned)
        except:
            logger.debug(f"Could not parse currency: {currency_str}")
            return None

    def _extract_status(self, response):
        """
        Determine tender status from content
        """
        text = ' '.join(response.css('body::text').getall()).lower()

        status_keywords = {
            'open': ['отворен', 'активен', 'open', 'active'],
            'closed': ['затворен', 'истечен', 'closed', 'expired'],
            'awarded': ['доделен', 'awarded', 'contract signed'],
            'cancelled': ['откажан', 'cancelled', 'canceled'],
        }

        for status, keywords in status_keywords.items():
            if any(kw in text for kw in keywords):
                return status

        # Fallback: Check dates
        closing_str = FieldExtractor.extract_with_fallbacks(
            response, 'closing_check', [
                {'type': 'label', 'label': 'Closing'},
                {'type': 'label', 'label': 'Deadline'},
            ]
        )

        if closing_str:
            closing_date = self._parse_date(closing_str)
            if closing_date and closing_date < datetime.now().date():
                return 'closed'

        return 'open'  # Default

    def _extract_documents(self, response, tender_id):
        """
        Extract document links from tender page
        """
        # Multiple strategies to find document links
        doc_selectors = [
            'a[href$=".pdf"]::attr(href)',
            'a[href$=".doc"]::attr(href)',
            'a[href$=".docx"]::attr(href)',
            'a:contains("Download")::attr(href)',
            'a:contains("Преземи")::attr(href)',  # Macedonian: "Download"
            'div.documents a::attr(href)',
            'div.attachments a::attr(href)',
        ]

        doc_links = []
        for selector in doc_selectors:
            links = response.css(selector).getall()
            doc_links.extend(links)

        # Deduplicate
        doc_links = list(set(doc_links))

        logger.info(f"Found {len(doc_links)} documents for tender {tender_id}")

        for doc_url in doc_links:
            doc_item = DocumentItem()
            doc_item['tender_id'] = tender_id
            doc_item['file_url'] = response.urljoin(doc_url)
            doc_item['doc_type'] = self._classify_document(doc_url)

            yield doc_item

    def _classify_document(self, url):
        """
        Classify document type from URL/filename
        """
        url_lower = url.lower()

        if 'tender' in url_lower or 'тендер' in url_lower:
            return 'tender_document'
        elif 'technical' in url_lower or 'технич' in url_lower:
            return 'technical_specification'
        elif 'contract' in url_lower or 'договор' in url_lower:
            return 'contract'
        else:
            return 'other'

    def _track_extraction_success(self, tender):
        """
        Track which fields were successfully extracted

        Helps detect structure changes by monitoring success rates
        """
        for field, value in tender.items():
            if field not in self.extraction_stats['successful_extractions']:
                self.extraction_stats['successful_extractions'][field] = 0
                self.extraction_stats['failed_fields'][field] = 0

            if value is not None and value != '':
                self.extraction_stats['successful_extractions'][field] += 1
            else:
                self.extraction_stats['failed_fields'][field] += 1

    def closed(self, reason):
        """
        Log extraction statistics on spider close

        Alerts if extraction rates are unusually low (possible structure change)
        """
        logger.info("=" * 60)
        logger.info("EXTRACTION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total tenders processed: {self.extraction_stats['total_tenders']}")

        if self.extraction_stats['total_tenders'] > 0:
            logger.info("\nField Success Rates:")

            critical_fields = ['tender_id', 'title', 'procuring_entity']

            for field in sorted(self.extraction_stats['successful_extractions'].keys()):
                success = self.extraction_stats['successful_extractions'][field]
                failed = self.extraction_stats['failed_fields'][field]
                total = success + failed
                rate = (success / total * 100) if total > 0 else 0

                status = "✓" if rate >= 80 else "⚠" if rate >= 50 else "✗"
                logger.info(f"  {status} {field}: {rate:.1f}% ({success}/{total})")

                # Alert on critical field failures
                if field in critical_fields and rate < 80:
                    logger.error(
                        f"STRUCTURE CHANGE ALERT: {field} extraction rate is {rate:.1f}% "
                        f"(expected >80%). Website structure may have changed!"
                    )

        logger.info("=" * 60)
