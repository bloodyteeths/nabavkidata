"""
TENDER DETAIL EXTRACTION ARCHITECTURE
======================================

Multi-tier fallback extraction system for e-nabavki.gov.mk tender detail pages.

DESIGN PHILOSOPHY:
- Resilience: 5-level fallback chain for every field
- Adaptability: Survives website structure changes
- Observability: Comprehensive logging and statistics
- Accuracy: Multi-format parsers with validation

EXTRACTION STRATEGY:
Level 1: Primary CSS selector (fastest, most specific)
Level 2: XPath alternative (different DOM approach)
Level 3: Label-based extraction (find "Назив:" then extract adjacent value)
Level 4: Regex pattern matching (content-based, structure-independent)
Level 5: Default/null handling with appropriate logging

AUTHOR: Agent B - Tender Detail Extraction Logic Architect
DATE: 2025-11-24
"""

import re
import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Any, Tuple
from decimal import Decimal, InvalidOperation
import hashlib

logger = logging.getLogger(__name__)


class ExtractionStats:
    """Track extraction success/failure statistics for monitoring"""

    def __init__(self):
        self.total_extractions = 0
        self.field_success = {}
        self.field_failures = {}
        self.fallback_levels_used = {}

    def record_success(self, field_name: str, fallback_level: int):
        """Record successful extraction"""
        self.field_success[field_name] = self.field_success.get(field_name, 0) + 1

        if field_name not in self.fallback_levels_used:
            self.fallback_levels_used[field_name] = {}
        self.fallback_levels_used[field_name][fallback_level] = \
            self.fallback_levels_used[field_name].get(fallback_level, 0) + 1

    def record_failure(self, field_name: str):
        """Record extraction failure"""
        self.field_failures[field_name] = self.field_failures.get(field_name, 0) + 1

    def get_success_rate(self, field_name: str) -> float:
        """Calculate success rate for a field"""
        success = self.field_success.get(field_name, 0)
        failures = self.field_failures.get(field_name, 0)
        total = success + failures
        return (success / total * 100) if total > 0 else 0.0

    def log_statistics(self):
        """Log comprehensive extraction statistics"""
        logger.info("=" * 80)
        logger.info("EXTRACTION STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total tenders processed: {self.total_extractions}")
        logger.info("")
        logger.info("Field-by-field success rates:")
        logger.info("-" * 80)

        all_fields = set(list(self.field_success.keys()) + list(self.field_failures.keys()))
        critical_fields = {'tender_id', 'title', 'procuring_entity', 'closing_date'}

        for field in sorted(all_fields):
            rate = self.get_success_rate(field)
            success = self.field_success.get(field, 0)
            failures = self.field_failures.get(field, 0)

            # Status indicator
            if rate >= 90:
                status = "EXCELLENT"
            elif rate >= 70:
                status = "GOOD"
            elif rate >= 50:
                status = "WARNING"
            else:
                status = "CRITICAL"

            logger.info(f"  [{status:8}] {field:30} {rate:6.2f}% ({success}/{success + failures})")

            # Alert on critical field failures
            if field in critical_fields and rate < 80:
                logger.error(
                    f"STRUCTURE CHANGE ALERT: '{field}' extraction rate is {rate:.1f}% "
                    f"(expected >80%). Website structure may have changed!"
                )

            # Show fallback distribution for this field
            if field in self.fallback_levels_used:
                levels = self.fallback_levels_used[field]
                level_dist = ", ".join([f"L{lvl}:{cnt}" for lvl, cnt in sorted(levels.items())])
                logger.debug(f"    Fallback distribution: {level_dist}")

        logger.info("=" * 80)


class DateParser:
    """
    Robust date parser supporting multiple formats and Macedonian locale.

    Supported formats:
    - dd.mm.yyyy (15.03.2024)
    - dd/mm/yyyy (15/03/2024)
    - yyyy-mm-dd (2024-03-15)
    - dd-mm-yyyy (15-03-2024)
    - Macedonian month names
    - Relative dates (вчера, денес)
    """

    # Macedonian month name mappings
    MACEDONIAN_MONTHS = {
        'јануари': 1, 'јануари,': 1,
        'фебруари': 2, 'фебруари,': 2,
        'март': 3, 'март,': 3,
        'април': 4, 'април,': 4,
        'мај': 5, 'мај,': 5,
        'јуни': 6, 'јуни,': 6,
        'јули': 7, 'јули,': 7,
        'август': 8, 'август,': 8,
        'септември': 9, 'септември,': 9,
        'октомври': 10, 'октомври,': 10,
        'ноември': 11, 'ноември,': 11,
        'декември': 12, 'декември,': 12,
    }

    # Date format patterns (order matters - try most specific first)
    DATE_FORMATS = [
        '%d.%m.%Y',      # 15.03.2024
        '%d/%m/%Y',      # 15/03/2024
        '%Y-%m-%d',      # 2024-03-15 (ISO format)
        '%d-%m-%Y',      # 15-03-2024
        '%d.%m.%y',      # 15.03.24
        '%d/%m/%y',      # 15/03/24
        '%Y/%m/%d',      # 2024/03/15
    ]

    @staticmethod
    def parse(date_string: str) -> Optional[date]:
        """
        Parse date string with multiple format support.

        Args:
            date_string: Date string in various formats

        Returns:
            date object or None if parsing fails
        """
        if not date_string or not isinstance(date_string, str):
            return None

        # Clean the string
        date_string = date_string.strip()

        # Handle relative dates (Macedonian)
        if date_string.lower() in ['денес', 'today']:
            return date.today()
        elif date_string.lower() in ['вчера', 'yesterday']:
            from datetime import timedelta
            return date.today() - timedelta(days=1)

        # Try Macedonian month names (e.g., "15 март 2024")
        macedonian_date = DateParser._parse_macedonian_month(date_string)
        if macedonian_date:
            return macedonian_date

        # Try standard date formats
        for fmt in DateParser.DATE_FORMATS:
            try:
                parsed = datetime.strptime(date_string, fmt).date()

                # Sanity check: date should be between 2000 and 2050
                if 2000 <= parsed.year <= 2050:
                    return parsed
            except (ValueError, AttributeError):
                continue

        # Extract date using regex as last resort
        # Pattern: dd.mm.yyyy or dd/mm/yyyy or yyyy-mm-dd
        patterns = [
            r'(\d{1,2})[./](\d{1,2})[./](\d{4})',  # dd.mm.yyyy or dd/mm/yyyy
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # yyyy-mm-dd
        ]

        for pattern in patterns:
            match = re.search(pattern, date_string)
            if match:
                try:
                    if len(match.group(1)) == 4:  # yyyy-mm-dd
                        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    else:  # dd.mm.yyyy
                        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))

                    parsed = date(year, month, day)
                    if 2000 <= parsed.year <= 2050:
                        return parsed
                except (ValueError, AttributeError):
                    continue

        logger.debug(f"Could not parse date: '{date_string}'")
        return None

    @staticmethod
    def _parse_macedonian_month(date_string: str) -> Optional[date]:
        """Parse dates with Macedonian month names (e.g., '15 март 2024')"""
        # Pattern: day month year (e.g., "15 март 2024")
        pattern = r'(\d{1,2})\s+([а-яА-Я]+)\s+(\d{4})'
        match = re.search(pattern, date_string)

        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))

            month = DateParser.MACEDONIAN_MONTHS.get(month_name)
            if month:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass

        return None


class CurrencyParser:
    """
    Robust currency parser supporting European and US number formats.

    Supported formats:
    - European: 1.234.567,89 or 1 234 567,89
    - US: 1,234,567.89
    - Mixed: 1.234.567 or 1,234,567 (no decimal)
    - Currency symbols: MKD, денари, EUR, €
    - Value ranges: "100,000 - 200,000 MKD" (extracts first value)
    """

    @staticmethod
    def parse(value_string: str, currency: str = 'MKD') -> Optional[Decimal]:
        """
        Extract numeric value from currency string.

        Args:
            value_string: Currency string with various formats
            currency: Expected currency (for validation)

        Returns:
            Decimal value or None if parsing fails
        """
        if not value_string or not isinstance(value_string, str):
            return None

        # Clean the string
        original = value_string
        value_string = value_string.strip()

        # Handle ranges - extract first value (estimated value)
        if '-' in value_string or 'до' in value_string or 'to' in value_string:
            # Split by range separator and take first part
            parts = re.split(r'[-–—]|до|to', value_string)
            if parts:
                value_string = parts[0].strip()
                logger.debug(f"Range detected, using first value: {value_string}")

        # Remove currency symbols and text
        # Common patterns: MKD, EUR, €, денари, денар, евра, евро
        value_string = re.sub(r'(?i)(MKD|EUR|€|денари?|евро?а?)', '', value_string)

        # Remove any remaining non-numeric characters except digits, comma, dot, space
        cleaned = re.sub(r'[^\d,.\s]', '', value_string).strip()

        if not cleaned:
            logger.debug(f"No numeric value found in: '{original}'")
            return None

        # Remove spaces (European thousand separator)
        cleaned = cleaned.replace(' ', '')

        # Determine number format by analyzing separators
        try:
            parsed_value = CurrencyParser._parse_number_format(cleaned)

            # Sanity checks
            if parsed_value < 0:
                logger.warning(f"Negative currency value: {parsed_value} from '{original}'")
                return None

            if parsed_value > 10_000_000_000:  # 10 billion
                logger.warning(f"Suspiciously large value: {parsed_value} from '{original}'")
                return None

            return parsed_value

        except (ValueError, InvalidOperation) as e:
            logger.debug(f"Could not parse currency: '{original}' - {e}")
            return None

    @staticmethod
    def _parse_number_format(cleaned: str) -> Decimal:
        """
        Determine if European (1.234,56) or US (1,234.56) format and parse accordingly.
        """
        # No separators - simple integer
        if ',' not in cleaned and '.' not in cleaned:
            return Decimal(cleaned)

        # Only dots - could be US format or European thousands
        if ',' not in cleaned and '.' in cleaned:
            # Count dots
            dot_count = cleaned.count('.')
            if dot_count == 1:
                # Check position - if last 3 digits, likely decimal (US), otherwise thousands (EU)
                dot_pos = cleaned.rfind('.')
                digits_after = len(cleaned) - dot_pos - 1
                if digits_after <= 2:
                    # US format: 1234.56
                    return Decimal(cleaned)
                else:
                    # European thousands: 1.234 -> 1234
                    return Decimal(cleaned.replace('.', ''))
            else:
                # Multiple dots - European thousands: 1.234.567
                return Decimal(cleaned.replace('.', ''))

        # Only commas - could be European decimal or US thousands
        if '.' not in cleaned and ',' in cleaned:
            comma_count = cleaned.count(',')
            if comma_count == 1:
                # Check position
                comma_pos = cleaned.rfind(',')
                digits_after = len(cleaned) - comma_pos - 1
                if digits_after <= 2:
                    # European decimal: 1234,56 -> 1234.56
                    return Decimal(cleaned.replace(',', '.'))
                else:
                    # US thousands: 1,234 -> 1234
                    return Decimal(cleaned.replace(',', ''))
            else:
                # Multiple commas - US thousands: 1,234,567
                return Decimal(cleaned.replace(',', ''))

        # Both dots and commas - determine which is decimal separator
        last_comma = cleaned.rfind(',')
        last_dot = cleaned.rfind('.')

        if last_comma > last_dot:
            # European format: 1.234.567,89 -> comma is decimal
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            # US format: 1,234,567.89 -> dot is decimal
            cleaned = cleaned.replace(',', '')

        return Decimal(cleaned)


class StatusDetector:
    """
    Intelligent tender status detection based on multiple signals.

    Status values:
    - 'open': Actively accepting bids
    - 'closed': Deadline passed, no winner yet
    - 'awarded': Winner announced
    - 'cancelled': Tender cancelled
    - 'draft': Not yet published (rare)

    Detection strategy:
    1. Explicit status field (if present)
    2. Winner field presence -> 'awarded'
    3. Closing date comparison with today -> 'closed' if past
    4. Keywords in text (отворен, затворен, доделен, откажан)
    5. Default to 'open' if uncertain
    """

    # Macedonian and English status keywords
    STATUS_KEYWORDS = {
        'open': ['отворен', 'активен', 'open', 'active', 'објавен'],
        'closed': ['затворен', 'истечен', 'closed', 'expired', 'завршен'],
        'awarded': ['доделен', 'awarded', 'договор потпишан', 'contract signed', 'избран'],
        'cancelled': ['откажан', 'поништен', 'cancelled', 'canceled', 'annulled'],
        'draft': ['нацрт', 'draft', 'во подготовка', 'in preparation'],
    }

    @staticmethod
    def detect(tender_data: Dict[str, Any], page_text: str = '') -> str:
        """
        Detect tender status from multiple signals.

        Args:
            tender_data: Dictionary with extracted tender fields
            page_text: Full page text for keyword search

        Returns:
            Status string: 'open', 'closed', 'awarded', 'cancelled', or 'draft'
        """
        # 1. Check for explicit status field
        explicit_status = tender_data.get('status')
        if explicit_status and explicit_status.lower() in StatusDetector.STATUS_KEYWORDS:
            return explicit_status.lower()

        # 2. If winner is present -> awarded
        winner = tender_data.get('winner')
        if winner and len(str(winner).strip()) > 2:
            logger.debug("Status: awarded (winner field present)")
            return 'awarded'

        # 3. Check awarded values - if present, likely awarded
        awarded_mkd = tender_data.get('awarded_value_mkd')
        awarded_eur = tender_data.get('awarded_value_eur')
        if awarded_mkd or awarded_eur:
            logger.debug("Status: awarded (awarded value present)")
            return 'awarded'

        # 4. Date-based detection
        closing_date = tender_data.get('closing_date')
        if closing_date:
            if isinstance(closing_date, str):
                closing_date = DateParser.parse(closing_date)

            if closing_date and closing_date < date.today():
                # Past deadline - either closed or awarded
                # If no winner, it's just closed
                logger.debug(f"Status: closed (closing_date {closing_date} is in past)")
                return 'closed'

        # 5. Keyword-based detection from page text
        if page_text:
            page_text_lower = page_text.lower()

            # Check each status in priority order
            for status in ['cancelled', 'awarded', 'closed', 'draft', 'open']:
                keywords = StatusDetector.STATUS_KEYWORDS[status]
                for keyword in keywords:
                    if keyword in page_text_lower:
                        logger.debug(f"Status: {status} (keyword '{keyword}' found)")
                        return status

        # 6. Default to 'open' if closing date is in future or not determined
        logger.debug("Status: open (default)")
        return 'open'


class DocumentExtractor:
    """
    Extract and classify documents from tender detail pages.

    Document types:
    - tender_document: Main tender documentation
    - technical_spec: Technical specifications
    - amendment: Amendments and addenda
    - award: Award decision notices
    - contract: Signed contracts
    - other: Miscellaneous documents
    """

    # Document type classification keywords
    DOC_TYPE_KEYWORDS = {
        'tender_document': [
            'тендер', 'tender', 'набавка', 'procurement',
            'јавен оглас', 'public notice', 'покана', 'invitation'
        ],
        'technical_spec': [
            'технич', 'technical', 'спецификација', 'specification',
            'барања', 'requirements', 'услови', 'conditions'
        ],
        'amendment': [
            'измен', 'amendment', 'допол', 'addend', 'дополнение', 'annex'
        ],
        'award': [
            'одлука', 'decision', 'доделување', 'award',
            'избор', 'selection', 'резултат', 'result'
        ],
        'contract': [
            'договор', 'contract', 'потпишан', 'signed'
        ],
    }

    @staticmethod
    def extract_documents(response, tender_id: str) -> List[Dict[str, Any]]:
        """
        Extract all documents from tender detail page.

        Args:
            response: Scrapy response object
            tender_id: Tender ID for association

        Returns:
            List of document dictionaries with metadata
        """
        documents = []

        # Multiple strategies to find document links
        doc_selectors = [
            # Direct file links
            'a[href$=".pdf"]::attr(href)',
            'a[href$=".PDF"]::attr(href)',
            'a[href$=".doc"]::attr(href)',
            'a[href$=".docx"]::attr(href)',
            'a[href$=".xls"]::attr(href)',
            'a[href$=".xlsx"]::attr(href)',

            # Download links (Macedonian and English)
            'a:contains("Преземи")::attr(href)',
            'a:contains("Download")::attr(href)',
            'a:contains("Симни")::attr(href)',

            # Common container classes
            'div.documents a::attr(href)',
            'div.attachments a::attr(href)',
            'div.files a::attr(href)',
            'div[class*="document"] a::attr(href)',
            'div[class*="attachment"] a::attr(href)',
            'div[class*="file"] a::attr(href)',
            'table.documents a::attr(href)',
            'ul.document-list a::attr(href)',
        ]

        # Also get link text for better classification
        link_data = []

        for selector in doc_selectors:
            # Get both href and text
            links = response.css(selector.replace('::attr(href)', ''))
            for link in links:
                href = link.css('::attr(href)').get()
                text = link.css('::text').get()
                title = link.css('::attr(title)').get()

                if href:
                    link_data.append({
                        'url': href,
                        'text': text or '',
                        'title': title or '',
                    })

        # Deduplicate by URL
        seen_urls = set()
        for link_info in link_data:
            url = link_info['url']
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Build full URL
            full_url = response.urljoin(url)

            # Extract metadata
            file_name = DocumentExtractor._extract_filename(full_url, link_info['text'])
            doc_type = DocumentExtractor._classify_document(
                file_name,
                link_info['text'],
                link_info['title']
            )

            documents.append({
                'tender_id': tender_id,
                'file_url': full_url,
                'file_name': file_name,
                'doc_type': doc_type,
                'link_text': link_info['text'],
                'link_title': link_info['title'],
            })

        logger.info(f"Extracted {len(documents)} documents for tender {tender_id}")
        return documents

    @staticmethod
    def _extract_filename(url: str, link_text: str = '') -> str:
        """Extract filename from URL or generate from link text"""
        # Try to get filename from URL
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Get last part of path
        filename = path.split('/')[-1] if '/' in path else path

        if filename and len(filename) > 3:
            return filename

        # Generate from link text
        if link_text:
            # Clean and truncate
            safe_text = re.sub(r'[^\w\s-]', '', link_text).strip()
            safe_text = re.sub(r'[-\s]+', '_', safe_text)
            return f"{safe_text[:50]}.pdf"

        # Generate hash-based filename
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"document_{url_hash}.pdf"

    @staticmethod
    def _classify_document(filename: str, link_text: str, link_title: str) -> str:
        """
        Classify document type based on filename and link text.

        Args:
            filename: Document filename
            link_text: Link text/label
            link_title: Link title attribute

        Returns:
            Document type: tender_document, technical_spec, amendment, award, contract, other
        """
        # Combine all text for keyword matching
        combined = f"{filename} {link_text} {link_title}".lower()

        # Check each type's keywords
        for doc_type, keywords in DocumentExtractor.DOC_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined:
                    return doc_type

        # Default to 'other'
        return 'other'


class TenderExtractor:
    """
    Main tender field extractor with multi-fallback architecture.

    FIELD EXTRACTION STRATEGY:
    Each field has a 5-level fallback chain:
    1. Primary CSS selector (fastest)
    2. XPath alternative (different approach)
    3. Label-based extraction (find label, extract adjacent value)
    4. Regex pattern matching (structure-independent)
    5. Default/null with logging

    FIELDS EXTRACTED:
    Core fields:
    - tender_id, title, description, category, procuring_entity
    - cpv_code, opening_date, closing_date, publication_date
    - estimated_value_mkd, estimated_value_eur
    - awarded_value_mkd, awarded_value_eur
    - status, winner, source_url, language

    New fields (to be added):
    - procedure_type
    - contract_signing_date
    - contract_duration
    - contracting_entity_category
    - procurement_holder
    - bureau_delivery_date
    """

    # FIELD EXTRACTION CONFIGURATION
    # This will be populated with real selectors by Agent A
    FIELD_EXTRACTORS = {
        'tender_id': [
            {'type': 'css', 'selector': 'span.tender-id::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.reference-number::text', 'priority': 1},
            {'type': 'xpath', 'selector': '//span[@class="tender-id"]/text()', 'priority': 2},
            {'type': 'label', 'macedonian': 'Број', 'english': 'Number', 'priority': 3},
            {'type': 'label', 'macedonian': 'Референца', 'english': 'Reference', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:ID|Број|Reference)[:\s]+([A-Z0-9/-]+)', 'priority': 4},
            {'type': 'url_param', 'param_names': ['id', 'tenderid', 'tender'], 'priority': 1},
            {'type': 'default', 'value': None, 'log_level': 'ERROR'},
        ],

        'title': [
            {'type': 'css', 'selector': 'h1.tender-title::text', 'priority': 1},
            {'type': 'css', 'selector': 'h1::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.title::text', 'priority': 1},
            {'type': 'xpath', 'selector': '//h1/text()', 'priority': 2},
            {'type': 'label', 'macedonian': 'Назив', 'english': 'Title', 'priority': 3},
            {'type': 'label', 'macedonian': 'Име на набавка', 'english': 'Procurement Name', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:Назив|Title)[:\s]+(.+?)(?:<|$)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'ERROR'},
        ],

        'description': [
            {'type': 'css', 'selector': 'div.description::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.tender-description::text', 'priority': 1},
            {'type': 'css', 'selector': 'p.description::text', 'priority': 1},
            {'type': 'xpath', 'selector': '//div[@class="description"]//text()', 'priority': 2},
            {'type': 'label', 'macedonian': 'Опис', 'english': 'Description', 'priority': 3},
            {'type': 'label', 'macedonian': 'Предмет на набавка', 'english': 'Subject', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'WARNING'},
        ],

        'procuring_entity': [
            {'type': 'css', 'selector': 'div.procuring-entity::text', 'priority': 1},
            {'type': 'css', 'selector': 'span.entity::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.organization::text', 'priority': 1},
            {'type': 'xpath', 'selector': '//div[@class="procuring-entity"]/text()', 'priority': 2},
            {'type': 'label', 'macedonian': 'Нарачател', 'english': 'Contracting Authority', 'priority': 3},
            {'type': 'label', 'macedonian': 'Договорен орган', 'english': 'Procuring Entity', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:Нарачател|Contracting)[:\s]+([^\n<]+)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'WARNING'},
        ],

        'category': [
            {'type': 'css', 'selector': 'span.category::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.procurement-category::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Категорија', 'english': 'Category', 'priority': 3},
            {'type': 'label', 'macedonian': 'Тип', 'english': 'Type', 'priority': 3},
            {'type': 'keyword_analysis', 'priority': 4},  # Content-based classification
            {'type': 'default', 'value': 'Other', 'log_level': 'INFO'},
        ],

        'cpv_code': [
            {'type': 'css', 'selector': 'span.cpv-code::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.cpv::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'CPV', 'english': 'CPV', 'priority': 3},
            {'type': 'label', 'macedonian': 'CPV Код', 'english': 'CPV Code', 'priority': 3},
            {'type': 'regex', 'pattern': r'CPV[:\s]+([0-9-]+)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'opening_date': [
            {'type': 'css', 'selector': 'span.opening-date::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.date-opening::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Отворање', 'english': 'Opening', 'priority': 3},
            {'type': 'label', 'macedonian': 'Датум на отворање', 'english': 'Opening Date', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'closing_date': [
            {'type': 'css', 'selector': 'span.closing-date::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.date-closing::text', 'priority': 1},
            {'type': 'css', 'selector': 'span.deadline::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Затворање', 'english': 'Closing', 'priority': 3},
            {'type': 'label', 'macedonian': 'Краен рок', 'english': 'Deadline', 'priority': 3},
            {'type': 'label', 'macedonian': 'Рок за поднесување', 'english': 'Submission Deadline', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'WARNING'},
        ],

        'publication_date': [
            {'type': 'css', 'selector': 'span.publication-date::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.date-publication::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Објавено', 'english': 'Published', 'priority': 3},
            {'type': 'label', 'macedonian': 'Датум на објава', 'english': 'Publication Date', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'estimated_value_mkd': [
            {'type': 'css', 'selector': 'span.estimated-mkd::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.value-estimated-mkd::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Проценета вредност (МКД)', 'english': 'Estimated Value (MKD)', 'priority': 3},
            {'type': 'label', 'macedonian': 'Вредност МКД', 'english': 'Value MKD', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:Проценета|Estimated).*?([0-9.,\s]+)\s*(?:MKD|ден)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'estimated_value_eur': [
            {'type': 'css', 'selector': 'span.estimated-eur::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.value-estimated-eur::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Проценета вредност (ЕУР)', 'english': 'Estimated Value (EUR)', 'priority': 3},
            {'type': 'label', 'macedonian': 'Вредност ЕУР', 'english': 'Value EUR', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:Проценета|Estimated).*?([0-9.,\s]+)\s*(?:EUR|€)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'awarded_value_mkd': [
            {'type': 'css', 'selector': 'span.awarded-mkd::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.value-awarded-mkd::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Доделена вредност (МКД)', 'english': 'Awarded Value (MKD)', 'priority': 3},
            {'type': 'label', 'macedonian': 'Вредност на договор МКД', 'english': 'Contract Value MKD', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:Доделена|Awarded|Contract).*?([0-9.,\s]+)\s*(?:MKD|ден)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'awarded_value_eur': [
            {'type': 'css', 'selector': 'span.awarded-eur::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.value-awarded-eur::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Доделена вредност (ЕУР)', 'english': 'Awarded Value (EUR)', 'priority': 3},
            {'type': 'label', 'macedonian': 'Вредност на договор ЕУР', 'english': 'Contract Value EUR', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:Доделена|Awarded|Contract).*?([0-9.,\s]+)\s*(?:EUR|€)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'winner': [
            {'type': 'css', 'selector': 'div.winner::text', 'priority': 1},
            {'type': 'css', 'selector': 'span.awarded-to::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.contractor::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Добитник', 'english': 'Winner', 'priority': 3},
            {'type': 'label', 'macedonian': 'Избран понудувач', 'english': 'Selected Bidder', 'priority': 3},
            {'type': 'label', 'macedonian': 'Договорен операtор', 'english': 'Contractor', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        # NEW FIELDS TO BE ADDED

        'procedure_type': [
            {'type': 'css', 'selector': 'span.procedure-type::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.procurement-type::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Вид на постапка', 'english': 'Procedure Type', 'priority': 3},
            {'type': 'label', 'macedonian': 'Тип на постапка', 'english': 'Type of Procedure', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:Вид на постапка|Procedure Type)[:\s]+(.+?)(?:<|$)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'contract_signing_date': [
            {'type': 'css', 'selector': 'span.contract-date::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.signing-date::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Датум на потпишување', 'english': 'Signing Date', 'priority': 3},
            {'type': 'label', 'macedonian': 'Договор потпишан', 'english': 'Contract Signed', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'contract_duration': [
            {'type': 'css', 'selector': 'span.contract-duration::text', 'priority': 1},
            {'type': 'css', 'selector': 'div.duration::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Траење на договор', 'english': 'Contract Duration', 'priority': 3},
            {'type': 'label', 'macedonian': 'Период', 'english': 'Period', 'priority': 3},
            {'type': 'regex', 'pattern': r'(?:Траење|Duration)[:\s]+(.+?)(?:<|$)', 'priority': 4},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'contracting_entity_category': [
            {'type': 'css', 'selector': 'span.entity-category::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Категорија на орган', 'english': 'Entity Category', 'priority': 3},
            {'type': 'label', 'macedonian': 'Тип на нарачател', 'english': 'Authority Type', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'procurement_holder': [
            {'type': 'css', 'selector': 'span.procurement-holder::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Носител на постапка', 'english': 'Procurement Holder', 'priority': 3},
            {'type': 'label', 'macedonian': 'Раководител', 'english': 'Manager', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],

        'bureau_delivery_date': [
            {'type': 'css', 'selector': 'span.bureau-date::text', 'priority': 1},
            {'type': 'label', 'macedonian': 'Датум на доставување до биро', 'english': 'Bureau Delivery Date', 'priority': 3},
            {'type': 'label', 'macedonian': 'Доставено до биро', 'english': 'Delivered to Bureau', 'priority': 3},
            {'type': 'default', 'value': None, 'log_level': 'INFO'},
        ],
    }

    def __init__(self):
        self.stats = ExtractionStats()
        self.date_parser = DateParser()
        self.currency_parser = CurrencyParser()
        self.status_detector = StatusDetector()
        self.document_extractor = DocumentExtractor()

    def extract_field(self, response, field_name: str) -> Any:
        """
        Extract single field using multi-tier fallback strategy.

        Args:
            response: Scrapy response object
            field_name: Name of field to extract

        Returns:
            Extracted value (type varies by field)
        """
        if field_name not in self.FIELD_EXTRACTORS:
            logger.warning(f"No extractor configuration for field: {field_name}")
            return None

        extractors = self.FIELD_EXTRACTORS[field_name]

        for level, extractor_config in enumerate(extractors, start=1):
            try:
                result = self._apply_extractor(response, extractor_config, field_name)

                if result is not None and (not isinstance(result, str) or result.strip()):
                    # Success!
                    self.stats.record_success(field_name, level)

                    if level > 1:
                        logger.debug(
                            f"{field_name}: Extracted using fallback level {level} "
                            f"({extractor_config['type']})"
                        )

                    return result

            except Exception as e:
                logger.debug(f"{field_name}: Extractor level {level} failed - {e}")
                continue

        # All extractors failed
        self.stats.record_failure(field_name)

        # Get log level from last extractor (default)
        log_level = extractors[-1].get('log_level', 'WARNING')
        log_func = getattr(logger, log_level.lower(), logger.warning)
        log_func(f"{field_name}: All extraction strategies failed")

        return None

    def _apply_extractor(self, response, config: Dict, field_name: str) -> Any:
        """Apply a single extraction strategy"""
        extractor_type = config['type']

        if extractor_type == 'css':
            return response.css(config['selector']).get()

        elif extractor_type == 'xpath':
            return response.xpath(config['selector']).get()

        elif extractor_type == 'label':
            # Try Macedonian first, then English
            for lang in ['macedonian', 'english']:
                if lang in config:
                    result = self._extract_by_label(response, config[lang])
                    if result:
                        return result
            return None

        elif extractor_type == 'regex':
            pattern = config['pattern']
            match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
            return match.group(1).strip() if match else None

        elif extractor_type == 'url_param':
            # Extract from URL parameters
            for param_name in config['param_names']:
                pattern = rf'[?&]{param_name}=([^&]+)'
                match = re.search(pattern, response.url, re.IGNORECASE)
                if match:
                    return match.group(1)
            return None

        elif extractor_type == 'keyword_analysis':
            # Content-based category classification
            return self._classify_category(response)

        elif extractor_type == 'default':
            return config.get('value')

        else:
            logger.warning(f"Unknown extractor type: {extractor_type}")
            return None

    def _extract_by_label(self, response, label_text: str) -> Optional[str]:
        """
        Find value by locating a label first.

        Patterns tried:
        1. Label: Value (inline)
        2. <td>Label</td><td>Value</td> (table cells)
        3. <div>Label</div><div>Value</div> (divs)
        4. <span>Label</span> Value (adjacent)
        """
        patterns = [
            # Inline with colon
            rf'{re.escape(label_text)}\s*:\s*([^\n<]+)',

            # Table cells (flexible whitespace)
            rf'<td[^>]*>\s*{re.escape(label_text)}\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>',

            # Divs
            rf'<div[^>]*>\s*{re.escape(label_text)}\s*[:\s]*</div>\s*<div[^>]*>\s*([^<]+?)\s*</div>',

            # Spans
            rf'<span[^>]*>\s*{re.escape(label_text)}\s*[:\s]*</span>\s*([^<\n]+)',

            # Labels
            rf'<label[^>]*>\s*{re.escape(label_text)}\s*[:\s]*</label>\s*([^<\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Remove HTML tags if any
                value = re.sub(r'<[^>]+>', '', value).strip()
                if value:
                    return value

        return None

    def _classify_category(self, response) -> str:
        """
        Classify tender category based on content analysis.

        Uses keyword matching in both Macedonian and English.
        """
        text = ' '.join(response.xpath('//body//text()').getall()).lower()

        categories = {
            'IT Equipment': [
                'компјутер', 'софтвер', 'хардвер', 'it опрема',
                'computer', 'software', 'hardware', 'laptop', 'server'
            ],
            'Construction': [
                'градеж', 'изградба', 'реконструкција', 'санација',
                'construction', 'building', 'renovation', 'infrastructure'
            ],
            'Medical Equipment': [
                'медицинска опрема', 'здравствена', 'болница', 'лекарства',
                'medical', 'health', 'hospital', 'pharmaceutical', 'medicine'
            ],
            'Consulting Services': [
                'консултантски', 'советување', 'услуги',
                'consulting', 'advisory', 'services', 'expertise'
            ],
            'Vehicles': [
                'возила', 'автомобил', 'моторни',
                'vehicle', 'automotive', 'car', 'truck', 'bus'
            ],
            'Furniture': [
                'мебел', 'намештај', 'канцелариска',
                'furniture', 'office furniture', 'desk', 'chair'
            ],
            'Food & Catering': [
                'храна', 'прехрана', 'кетеринг',
                'food', 'catering', 'meal', 'restaurant'
            ],
            'Office Supplies': [
                'канцелариски материјали', 'хартија',
                'office supplies', 'paper', 'stationery'
            ],
        }

        for category, keywords in categories.items():
            for keyword in keywords:
                # Use word boundary for short keywords
                if len(keyword) <= 3:
                    if re.search(rf'\b{re.escape(keyword)}\b', text):
                        return category
                elif keyword in text:
                    return category

        return 'Other'

    def extract_all_fields(self, response) -> Dict[str, Any]:
        """
        Extract all fields from tender detail page.

        Args:
            response: Scrapy response object

        Returns:
            Dictionary with all extracted tender fields
        """
        self.stats.total_extractions += 1

        logger.info(f"Extracting tender from: {response.url}")

        tender_data = {}

        # Extract basic fields
        tender_data['tender_id'] = self.extract_field(response, 'tender_id')
        tender_data['title'] = self.extract_field(response, 'title')
        tender_data['description'] = self.extract_field(response, 'description')
        tender_data['category'] = self.extract_field(response, 'category')
        tender_data['procuring_entity'] = self.extract_field(response, 'procuring_entity')
        tender_data['cpv_code'] = self.extract_field(response, 'cpv_code')

        # Extract dates (with parsing)
        opening_date_str = self.extract_field(response, 'opening_date')
        tender_data['opening_date'] = self.date_parser.parse(opening_date_str) if opening_date_str else None

        closing_date_str = self.extract_field(response, 'closing_date')
        tender_data['closing_date'] = self.date_parser.parse(closing_date_str) if closing_date_str else None

        publication_date_str = self.extract_field(response, 'publication_date')
        tender_data['publication_date'] = self.date_parser.parse(publication_date_str) if publication_date_str else None

        # Extract currency values (with parsing)
        est_mkd_str = self.extract_field(response, 'estimated_value_mkd')
        tender_data['estimated_value_mkd'] = self.currency_parser.parse(est_mkd_str, 'MKD') if est_mkd_str else None

        est_eur_str = self.extract_field(response, 'estimated_value_eur')
        tender_data['estimated_value_eur'] = self.currency_parser.parse(est_eur_str, 'EUR') if est_eur_str else None

        awarded_mkd_str = self.extract_field(response, 'awarded_value_mkd')
        tender_data['awarded_value_mkd'] = self.currency_parser.parse(awarded_mkd_str, 'MKD') if awarded_mkd_str else None

        awarded_eur_str = self.extract_field(response, 'awarded_value_eur')
        tender_data['awarded_value_eur'] = self.currency_parser.parse(awarded_eur_str, 'EUR') if awarded_eur_str else None

        # Extract winner
        tender_data['winner'] = self.extract_field(response, 'winner')

        # Extract NEW fields
        tender_data['procedure_type'] = self.extract_field(response, 'procedure_type')

        contract_date_str = self.extract_field(response, 'contract_signing_date')
        tender_data['contract_signing_date'] = self.date_parser.parse(contract_date_str) if contract_date_str else None

        tender_data['contract_duration'] = self.extract_field(response, 'contract_duration')
        tender_data['contracting_entity_category'] = self.extract_field(response, 'contracting_entity_category')
        tender_data['procurement_holder'] = self.extract_field(response, 'procurement_holder')

        bureau_date_str = self.extract_field(response, 'bureau_delivery_date')
        tender_data['bureau_delivery_date'] = self.date_parser.parse(bureau_date_str) if bureau_date_str else None

        # Detect status (intelligent multi-signal detection)
        page_text = ' '.join(response.xpath('//body//text()').getall())
        tender_data['status'] = self.status_detector.detect(tender_data, page_text)

        # Add metadata
        tender_data['source_url'] = response.url
        tender_data['language'] = 'mk'
        tender_data['scraped_at'] = datetime.utcnow()

        # Validate critical fields
        self._validate_tender(tender_data)

        logger.info(f"Extraction complete for tender: {tender_data.get('tender_id', 'UNKNOWN')}")

        return tender_data

    def extract_documents(self, response, tender_id: str) -> List[Dict[str, Any]]:
        """
        Extract all documents from tender detail page.

        Args:
            response: Scrapy response object
            tender_id: Tender ID for association

        Returns:
            List of document dictionaries
        """
        return self.document_extractor.extract_documents(response, tender_id)

    def _validate_tender(self, tender_data: Dict[str, Any]):
        """
        Validate extracted tender data.

        Checks:
        - Required fields present
        - Date logic (publication <= opening <= closing)
        - Value ranges (positive numbers)
        - Field lengths

        Logs warnings for validation failures.
        """
        # Check required fields
        required_fields = ['tender_id', 'title']
        for field in required_fields:
            if not tender_data.get(field):
                logger.error(f"VALIDATION ERROR: Missing required field '{field}'")

        # Validate title length
        title = tender_data.get('title', '')
        if title and len(title) < 3:
            logger.warning(f"VALIDATION WARNING: Title too short: '{title}'")

        # Validate date logic
        pub_date = tender_data.get('publication_date')
        open_date = tender_data.get('opening_date')
        close_date = tender_data.get('closing_date')

        if pub_date and open_date and pub_date > open_date:
            logger.warning(
                f"VALIDATION WARNING: publication_date ({pub_date}) > opening_date ({open_date})"
            )

        if open_date and close_date and open_date > close_date:
            logger.warning(
                f"VALIDATION WARNING: opening_date ({open_date}) > closing_date ({close_date})"
            )

        # Validate currency values
        for field in ['estimated_value_mkd', 'estimated_value_eur',
                     'awarded_value_mkd', 'awarded_value_eur']:
            value = tender_data.get(field)
            if value is not None:
                try:
                    value_float = float(value)
                    if value_float < 0:
                        logger.warning(f"VALIDATION WARNING: {field} is negative: {value_float}")
                    elif value_float > 10_000_000_000:  # 10 billion
                        logger.warning(f"VALIDATION WARNING: {field} suspiciously high: {value_float}")
                except (ValueError, TypeError):
                    logger.warning(f"VALIDATION WARNING: {field} is not numeric: {value}")

    def get_statistics(self) -> ExtractionStats:
        """Get extraction statistics object"""
        return self.stats

    def log_statistics(self):
        """Log extraction statistics summary"""
        self.stats.log_statistics()


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == '__main__':
    """
    Example usage of TenderExtractor.

    This shows how Agent A will integrate the extractor into the spider.
    """

    # In actual spider (nabavki_spider.py):

    # 1. Initialize extractor (once per spider instance)
    # extractor = TenderExtractor()

    # 2. In parse_tender_detail method:
    # tender_data = extractor.extract_all_fields(response)
    # documents = extractor.extract_documents(response, tender_data['tender_id'])

    # 3. Yield items
    # yield TenderItem(tender_data)
    # for doc in documents:
    #     yield DocumentItem(doc)

    # 4. On spider close, log statistics:
    # extractor.log_statistics()

    print("TenderExtractor architecture ready!")
    print("Waiting for Agent A to provide real selectors from e-nabavki.gov.mk...")
