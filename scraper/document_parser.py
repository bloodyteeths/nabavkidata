"""
Multi-Engine Document Parser - Extremely Resilient

ENGINES:
1. PyMuPDF (fitz) - Fast, best for text-based PDFs with Cyrillic
2. PDFMiner - Fallback for complex layouts
3. Tesseract OCR - For scanned/image PDFs

FEATURES:
- Automatic engine selection based on PDF characteristics
- Table structure detection and extraction
- CPV code extraction (multiple patterns)
- Company name extraction from award decisions
- Cyrillic-safe throughout
"""
import logging
import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# PDF extraction engines
import fitz  # PyMuPDF
from pdfminer.high_level import extract_text as pdfminer_extract
from pdfminer.layout import LAParams

# OCR engine
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of document parsing"""
    text: str
    engine_used: str
    page_count: int
    has_tables: bool
    tables: List[List[List[str]]]  # List of tables, each table is list of rows
    cpv_codes: List[str]
    company_names: List[str]
    emails: List[str]  # Extracted email addresses
    phones: List[str]  # Extracted phone numbers
    metadata: Dict


class PDFAnalyzer:
    """
    Analyze PDF characteristics to select optimal extraction engine
    """

    @staticmethod
    def analyze_pdf(pdf_path: str) -> Dict:
        """
        Analyze PDF to determine best extraction strategy

        Returns:
            analysis: {
                'page_count': int,
                'has_text': bool,
                'text_percentage': float,
                'is_scanned': bool,
                'has_complex_layout': bool,
                'recommended_engine': str
            }
        """
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)

            # Analyze first few pages
            sample_pages = min(3, page_count)
            total_text_chars = 0
            total_image_area = 0
            total_page_area = 0

            for page_num in range(sample_pages):
                page = doc[page_num]

                # Get text content
                text = page.get_text("text")
                total_text_chars += len(text.strip())

                # Get images
                image_list = page.get_images()
                for img in image_list:
                    # Approximate image coverage
                    total_image_area += 1  # Simplified

                # Page area
                rect = page.rect
                total_page_area += rect.width * rect.height

            doc.close()

            # Determine characteristics
            avg_chars_per_page = total_text_chars / sample_pages if sample_pages > 0 else 0
            has_text = avg_chars_per_page > 50
            has_images = total_image_area > 0
            is_scanned = has_images and avg_chars_per_page < 100

            # Text percentage (heuristic)
            text_percentage = min(100, (avg_chars_per_page / 2000) * 100)

            # Complex layout detection (heuristic: many small text blocks)
            has_complex_layout = False  # Simplified for now

            # Recommend engine
            if is_scanned:
                recommended_engine = 'tesseract'
            elif has_complex_layout:
                recommended_engine = 'pdfminer'
            else:
                recommended_engine = 'pymupdf'

            return {
                'page_count': page_count,
                'has_text': has_text,
                'text_percentage': text_percentage,
                'is_scanned': is_scanned,
                'has_complex_layout': has_complex_layout,
                'recommended_engine': recommended_engine,
            }

        except Exception as e:
            logger.error(f"PDF analysis failed: {e}")
            return {
                'page_count': 0,
                'has_text': False,
                'text_percentage': 0,
                'is_scanned': False,
                'has_complex_layout': False,
                'recommended_engine': 'pymupdf',
            }


class MultiEngineExtractor:
    """
    Multi-engine PDF text extraction with automatic fallback
    """

    @staticmethod
    def extract_with_pymupdf(pdf_path: str) -> Tuple[str, Dict]:
        """
        Extract using PyMuPDF (fastest, best for Cyrillic)
        """
        try:
            doc = fitz.open(pdf_path)
            text_pages = []
            metadata = {'page_count': len(doc)}

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                text_pages.append(text)

            doc.close()
            full_text = "\n\n".join(text_pages)

            # Verify Cyrillic
            has_cyrillic = any(0x0400 <= ord(c) <= 0x04FF for c in full_text)
            metadata['has_cyrillic'] = has_cyrillic

            logger.info(f"PyMuPDF extracted {len(full_text)} chars from {pdf_path}")
            return full_text, metadata

        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {e}")
            raise

    @staticmethod
    def extract_with_pdfminer(pdf_path: str) -> Tuple[str, Dict]:
        """
        Extract using PDFMiner (better for complex layouts)
        """
        try:
            # Configure LAParams for better layout analysis
            laparams = LAParams(
                line_margin=0.5,
                word_margin=0.1,
                char_margin=2.0,
                boxes_flow=0.5,
                detect_vertical=True,
            )

            text = pdfminer_extract(pdf_path, laparams=laparams)
            metadata = {'engine': 'pdfminer'}

            logger.info(f"PDFMiner extracted {len(text)} chars from {pdf_path}")
            return text, metadata

        except Exception as e:
            logger.error(f"PDFMiner extraction failed: {e}")
            raise

    @staticmethod
    def extract_with_tesseract(pdf_path: str) -> Tuple[str, Dict]:
        """
        Extract using Tesseract OCR (for scanned PDFs)
        """
        if not TESSERACT_AVAILABLE:
            raise ImportError("Tesseract not available")

        try:
            # Convert PDF pages to images, then OCR
            doc = fitz.open(pdf_path)
            text_pages = []

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Render page to image
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x resolution
                img_data = pix.tobytes("png")

                # Convert to PIL Image
                from io import BytesIO
                img = Image.open(BytesIO(img_data))

                # OCR with Macedonian + English
                text = pytesseract.image_to_string(
                    img,
                    lang='mkd+eng',  # Macedonian + English
                    config='--oem 3 --psm 1'  # Auto page segmentation
                )
                text_pages.append(text)

            doc.close()
            full_text = "\n\n".join(text_pages)
            metadata = {'engine': 'tesseract', 'page_count': len(text_pages)}

            logger.info(f"Tesseract OCR extracted {len(full_text)} chars from {pdf_path}")
            return full_text, metadata

        except Exception as e:
            logger.error(f"Tesseract extraction failed: {e}")
            raise

    @classmethod
    def extract_auto(cls, pdf_path: str) -> Tuple[str, str, Dict]:
        """
        Automatically select best extraction engine

        Returns:
            (text, engine_used, metadata)
        """
        # Analyze PDF
        analysis = PDFAnalyzer.analyze_pdf(pdf_path)
        recommended_engine = analysis['recommended_engine']

        logger.info(f"PDF analysis: {analysis}")
        logger.info(f"Recommended engine: {recommended_engine}")

        # Try engines in order of preference
        engines = [recommended_engine]
        if recommended_engine != 'pymupdf':
            engines.append('pymupdf')
        if recommended_engine != 'pdfminer':
            engines.append('pdfminer')
        if TESSERACT_AVAILABLE and recommended_engine != 'tesseract':
            engines.append('tesseract')

        last_error = None
        for engine in engines:
            try:
                if engine == 'pymupdf':
                    text, metadata = cls.extract_with_pymupdf(pdf_path)
                elif engine == 'pdfminer':
                    text, metadata = cls.extract_with_pdfminer(pdf_path)
                elif engine == 'tesseract':
                    text, metadata = cls.extract_with_tesseract(pdf_path)
                else:
                    continue

                # Validate extraction
                if len(text.strip()) > 50:  # Minimum text threshold
                    logger.info(f"Successfully extracted with {engine}")
                    return text, engine, metadata
                else:
                    logger.warning(f"{engine} extracted only {len(text)} chars, trying next engine")

            except Exception as e:
                last_error = e
                logger.warning(f"Engine {engine} failed: {e}, trying next")
                continue

        # All engines failed
        raise Exception(f"All extraction engines failed. Last error: {last_error}")


class TableExtractor:
    """
    Detect and extract table structures from PDF
    """

    @staticmethod
    def detect_tables(pdf_path: str) -> List[List[List[str]]]:
        """
        Detect and extract tables from PDF

        Returns:
            List of tables, where each table is a list of rows,
            and each row is a list of cell values
        """
        try:
            doc = fitz.open(pdf_path)
            all_tables = []

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Strategy 1: Look for structured tables using text blocks
                tables = TableExtractor._extract_tables_from_blocks(page)
                all_tables.extend(tables)

            doc.close()

            logger.info(f"Extracted {len(all_tables)} tables from {pdf_path}")
            return all_tables

        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return []

    @staticmethod
    def _extract_tables_from_blocks(page) -> List[List[List[str]]]:
        """
        Extract tables by analyzing text block positions
        """
        # Get text blocks with positions
        blocks = page.get_text("dict")["blocks"]

        # Simple heuristic: detect grid-like text patterns
        # (This is simplified - production code would use tabula-py or camelot)

        tables = []

        # Look for aligned text blocks (table-like structure)
        text_lines = []
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text_lines.append({
                            'text': span['text'],
                            'x': span['bbox'][0],
                            'y': span['bbox'][1],
                        })

        # Group by Y coordinate (rows)
        y_groups = {}
        for line in text_lines:
            y = round(line['y'] / 5) * 5  # Group similar Y positions
            if y not in y_groups:
                y_groups[y] = []
            y_groups[y].append(line)

        # If we have multiple rows with similar X positions, likely a table
        if len(y_groups) >= 3:  # At least 3 rows
            # Sort rows by Y
            sorted_rows = sorted(y_groups.items())

            # Extract table
            table = []
            for y, items in sorted_rows:
                # Sort items by X within row
                row = [item['text'] for item in sorted(items, key=lambda x: x['x'])]
                if len(row) >= 2:  # At least 2 columns
                    table.append(row)

            if len(table) >= 3:
                tables.append(table)

        return tables


class CPVExtractor:
    """
    Extract CPV (Common Procurement Vocabulary) codes from text
    """

    # CPV code patterns
    CPV_PATTERNS = [
        r'\b(\d{8})-?(\d)\b',  # Standard: 12345678-9
        r'CPV[:\s]+(\d{8})-?(\d)',  # With CPV label
        r'CPV[:\s]*код[:\s]*(\d{8})-?(\d)',  # Macedonian
        r'[Кк]од[:\s]+(\d{8})-?(\d)',  # Код: 12345678-9
    ]

    @staticmethod
    def extract_cpv_codes(text: str) -> List[str]:
        """
        Extract CPV codes from text using multiple patterns

        Returns:
            List of CPV codes in format "12345678-9"
        """
        cpv_codes = set()

        for pattern in CPVExtractor.CPV_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Reconstruct CPV code
                if len(match.groups()) == 2:
                    code = f"{match.group(1)}-{match.group(2)}"
                else:
                    code = match.group(1)

                # Validate CPV code format
                if CPVExtractor._validate_cpv(code):
                    cpv_codes.add(code)

        logger.info(f"Extracted {len(cpv_codes)} CPV codes")
        return sorted(list(cpv_codes))

    @staticmethod
    def _validate_cpv(code: str) -> bool:
        """
        Validate CPV code format

        CPV format: 8 digits + hyphen + 1 check digit
        Example: 45000000-7
        """
        # Remove hyphen for validation
        clean = code.replace('-', '')

        # Must be 9 digits
        if not clean.isdigit() or len(clean) != 9:
            return False

        # First 8 digits define category
        # Last digit is check digit
        return True


class ContactExtractor:
    """
    Extract contact information (emails, phones) from text
    """

    # Email pattern
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    # Phone patterns (Macedonian format)
    PHONE_PATTERNS = [
        r'\+389\s*\d{2}\s*\d{3}\s*\d{3}',  # +389 XX XXX XXX
        r'0\d{2}[\s\-]?\d{3}[\s\-]?\d{3}',  # 0XX XXX XXX or 0XX-XXX-XXX
        r'\d{3}[\s\-]?\d{3}[\s\-]?\d{3}',   # XXX XXX XXX
        r'\(\d{2,3}\)\s*\d{3}[\s\-]?\d{3}', # (XX) XXX-XXX
        r'\d{9,12}',                         # 9-12 digits
    ]

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """
        Extract email addresses from text

        Returns:
            List of unique email addresses
        """
        emails = set()

        matches = re.findall(ContactExtractor.EMAIL_PATTERN, text, re.IGNORECASE)
        for email in matches:
            email = email.lower().strip()
            # Validate email
            if ContactExtractor._validate_email(email):
                emails.add(email)

        logger.info(f"Extracted {len(emails)} email addresses")
        return sorted(list(emails))

    @staticmethod
    def _validate_email(email: str) -> bool:
        """Validate email address"""
        # Skip common false positives
        invalid_domains = ['example.com', 'test.com', 'localhost', 'domain.com']
        if any(domain in email for domain in invalid_domains):
            return False

        # Skip image/file extensions
        invalid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.doc']
        if any(email.endswith(ext) for ext in invalid_extensions):
            return False

        # Must have valid TLD
        tld = email.split('.')[-1]
        if len(tld) < 2 or len(tld) > 10:
            return False

        return True

    @staticmethod
    def extract_phones(text: str) -> List[str]:
        """
        Extract phone numbers from text

        Returns:
            List of unique phone numbers
        """
        phones = set()

        for pattern in ContactExtractor.PHONE_PATTERNS:
            matches = re.findall(pattern, text)
            for phone in matches:
                phone = ContactExtractor._clean_phone(phone)
                if ContactExtractor._validate_phone(phone):
                    phones.add(phone)

        logger.info(f"Extracted {len(phones)} phone numbers")
        return sorted(list(phones))

    @staticmethod
    def _clean_phone(phone: str) -> str:
        """Clean phone number"""
        # Remove spaces, dashes, parentheses
        phone = re.sub(r'[\s\-\(\)]', '', phone)
        return phone

    @staticmethod
    def _validate_phone(phone: str) -> bool:
        """Validate phone number"""
        # Must be at least 7 digits
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 7 or len(digits) > 15:
            return False

        # Skip obvious non-phones (prices, IDs, etc.)
        # If it's exactly 8 digits and starts with specific patterns, might be CPV
        if len(digits) == 8 and digits[0] in '0123456789':
            return False  # Likely a code, not a phone

        return True


class CompanyExtractor:
    """
    Extract company names from award decisions and tender documents
    """

    # Patterns for company names
    AWARD_PATTERNS = [
        # Macedonian patterns
        r'[Дд]обитник[:\s]+([А-ЯЃЌЉЊЏШЧЖа-яѓќљњџшчж\s\-\.]+(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД))',
        r'[Дд]оделен[а-я]*\s+на[:\s]+([А-ЯЃЌЉЊЏШЧЖа-яѓќљњџшчж\s\-\.]+(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД))',
        r'[Кк]омпанија[:\s]+([А-ЯЃЌЉЊЏШЧЖа-яѓќљњџшчж\s\-\.]+(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД))',

        # English patterns
        r'[Ww]inner[:\s]+([A-Z][A-Za-z\s\-\.]+(?:LLC|Ltd|Inc|Corp|Co))',
        r'[Aa]warded\s+to[:\s]+([A-Z][A-Za-z\s\-\.]+(?:LLC|Ltd|Inc|Corp|Co))',
        r'[Cc]ontractor[:\s]+([A-Z][A-Za-z\s\-\.]+(?:LLC|Ltd|Inc|Corp|Co))',

        # Generic pattern (company with legal form)
        r'([А-ЯЃЌЉЊЏШЧЖа-яѓќљњџшчжA-Z][А-ЯЃЌЉЊЏШЧЖа-яѓќљњџшчжA-Za-z\s\-\.]{3,50}(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД|LLC|Ltd|Inc|Corp))',
    ]

    @staticmethod
    def extract_companies(text: str) -> List[str]:
        """
        Extract company names from text using multiple patterns

        Returns:
            List of unique company names
        """
        companies = set()

        for pattern in CompanyExtractor.AWARD_PATTERNS:
            matches = re.finditer(pattern, text, re.UNICODE)
            for match in matches:
                company = match.group(1).strip()

                # Clean up
                company = CompanyExtractor._clean_company_name(company)

                # Validate
                if CompanyExtractor._validate_company_name(company):
                    companies.add(company)

        logger.info(f"Extracted {len(companies)} company names")
        return sorted(list(companies))

    @staticmethod
    def _clean_company_name(name: str) -> str:
        """Clean and normalize company name"""
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name)

        # Remove trailing dots/dashes
        name = name.rstrip('.-')

        # Capitalize properly
        # (Keep original case for Cyrillic)

        return name.strip()

    @staticmethod
    def _validate_company_name(name: str) -> bool:
        """Validate company name"""
        # Minimum length
        if len(name) < 5:
            return False

        # Maximum length
        if len(name) > 200:
            return False

        # Must contain legal form
        legal_forms = ['ДООЕЛ', 'ДОО', 'АД', 'ДПТУ', 'ООД', 'LLC', 'Ltd', 'Inc', 'Corp', 'Co']
        if not any(form in name for form in legal_forms):
            return False

        return True


class ResilientDocumentParser:
    """
    Extremely resilient document parser combining all extraction strategies
    """

    def __init__(self):
        self.extractor = MultiEngineExtractor()
        self.table_extractor = TableExtractor()
        self.cpv_extractor = CPVExtractor()
        self.company_extractor = CompanyExtractor()
        self.contact_extractor = ContactExtractor()

    def parse_document(self, pdf_path: str) -> ExtractionResult:
        """
        Parse PDF document with all extraction features

        Returns:
            ExtractionResult with text, tables, CPV codes, companies, etc.
        """
        logger.info(f"Parsing document: {pdf_path}")

        try:
            # 1. Extract text (multi-engine with auto-selection)
            text, engine_used, metadata = self.extractor.extract_auto(pdf_path)

            # 2. Detect and extract tables
            tables = self.table_extractor.detect_tables(pdf_path)
            has_tables = len(tables) > 0

            # 3. Extract CPV codes from text
            cpv_codes = self.cpv_extractor.extract_cpv_codes(text)

            # 4. Extract company names
            company_names = self.company_extractor.extract_companies(text)

            # 5. Extract contact information (emails, phones)
            emails = self.contact_extractor.extract_emails(text)
            phones = self.contact_extractor.extract_phones(text)

            # 6. Count pages
            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)
                doc.close()
            except:
                page_count = metadata.get('page_count', 0)

            # Build result
            result = ExtractionResult(
                text=text,
                engine_used=engine_used,
                page_count=page_count,
                has_tables=has_tables,
                tables=tables,
                cpv_codes=cpv_codes,
                company_names=company_names,
                emails=emails,
                phones=phones,
                metadata=metadata
            )

            logger.info(f"Parsing complete: {len(text)} chars, {page_count} pages, "
                       f"{len(tables)} tables, {len(cpv_codes)} CPV codes, "
                       f"{len(company_names)} companies, {len(emails)} emails, {len(phones)} phones")

            return result

        except Exception as e:
            logger.error(f"Document parsing failed: {e}")
            # Return empty result on failure (graceful degradation)
            return ExtractionResult(
                text="",
                engine_used="failed",
                page_count=0,
                has_tables=False,
                tables=[],
                cpv_codes=[],
                company_names=[],
                emails=[],
                phones=[],
                metadata={'error': str(e)}
            )


# Convenience function
def parse_pdf(pdf_path: str) -> ExtractionResult:
    """
    Parse PDF document with all features

    Usage:
        result = parse_pdf('tender.pdf')
        print(result.text)
        print(result.cpv_codes)
        print(result.company_names)
    """
    parser = ResilientDocumentParser()
    return parser.parse_document(pdf_path)
