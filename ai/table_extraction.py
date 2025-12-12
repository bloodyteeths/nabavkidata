"""
Multi-Engine Table Extraction Pipeline

Extracts structured tables from PDF documents using multiple engines with automatic fallback.

Engines (in order of preference):
1. pdfplumber - Best for digital PDFs with clean tables
2. camelot (lattice) - For bordered tables
3. camelot (stream) - For borderless tables
4. tabula - Java-based, reliable fallback
5. PyMuPDF - Geometry-based extraction

Each engine returns:
- List of tables as DataFrames
- Confidence score
- Page numbers
- Extraction metadata

Features:
- Multi-engine with automatic selection and fallback
- Macedonian language support
- Item extraction with pattern matching
- Table type classification (items, bidders, specifications)
- Confidence scoring
- Database integration ready
"""

import os
import json
import logging
import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd

# Import all available PDF engines
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.warning("pdfplumber not available")

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    logging.warning("camelot not available")

try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False
    logging.warning("tabula-py not available")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logging.warning("PyMuPDF not available")

logger = logging.getLogger(__name__)


class TableType(Enum):
    """Types of tables found in tender documents"""
    ITEMS = "items"  # List of items/products to be procured
    BIDDERS = "bidders"  # List of bidders/participants
    SPECIFICATIONS = "specifications"  # Technical specifications
    FINANCIAL = "financial"  # Financial bid/pricing
    EVALUATION = "evaluation"  # Evaluation criteria
    UNKNOWN = "unknown"


@dataclass
class ExtractedTable:
    """Represents a single extracted table"""
    data: pd.DataFrame  # The actual table data
    page_number: int  # Page where table was found
    table_index: int  # Index on the page (0, 1, 2...)
    engine_used: str  # Which engine extracted this table
    confidence: float  # Confidence score 0-1
    raw_text: str  # Raw text representation
    table_type: TableType  # Classified table type
    metadata: Dict[str, Any]  # Additional metadata

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'data': self.data.to_dict(orient='records'),
            'page_number': self.page_number,
            'table_index': self.table_index,
            'engine_used': self.engine_used,
            'confidence': self.confidence,
            'raw_text': self.raw_text,
            'table_type': self.table_type.value,
            'metadata': self.metadata,
            'row_count': len(self.data),
            'col_count': len(self.data.columns)
        }


class TableExtractor:
    """
    Multi-engine table extractor with automatic engine selection
    """

    def __init__(self, preferred_engine: Optional[str] = None):
        """
        Initialize table extractor

        Args:
            preferred_engine: Preferred engine to try first ('pdfplumber', 'camelot', 'tabula', 'pymupdf')
        """
        self.preferred_engine = preferred_engine
        self.engines = self._initialize_engines()
        logger.info(f"Initialized TableExtractor with {len(self.engines)} available engines")

    def _initialize_engines(self) -> List[Tuple[str, callable]]:
        """Initialize available extraction engines"""
        engines = []

        # Add engines in order of preference
        if self.preferred_engine == 'pdfplumber' and PDFPLUMBER_AVAILABLE:
            engines.append(('pdfplumber', self._extract_pdfplumber))

        if PDFPLUMBER_AVAILABLE and self.preferred_engine != 'pdfplumber':
            engines.append(('pdfplumber', self._extract_pdfplumber))

        if CAMELOT_AVAILABLE:
            engines.append(('camelot_lattice', self._extract_camelot_lattice))
            engines.append(('camelot_stream', self._extract_camelot_stream))

        if TABULA_AVAILABLE:
            engines.append(('tabula', self._extract_tabula))

        if PYMUPDF_AVAILABLE:
            engines.append(('pymupdf', self._extract_pymupdf))

        return engines

    def extract_tables(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None,
        min_confidence: float = 0.3
    ) -> List[ExtractedTable]:
        """
        Extract tables from PDF using multi-engine approach

        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum number of pages to process (None = all)
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            List of ExtractedTable objects
        """
        all_tables = []

        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return []

        logger.info(f"Extracting tables from: {pdf_path}")

        # Try each engine until we get good results
        for engine_name, engine_func in self.engines:
            try:
                logger.info(f"Trying engine: {engine_name}")
                tables = engine_func(pdf_path, max_pages=max_pages)

                # Filter by confidence
                high_confidence_tables = [
                    t for t in tables
                    if t.confidence >= min_confidence
                ]

                if high_confidence_tables:
                    logger.info(f"Engine {engine_name} extracted {len(high_confidence_tables)} tables")
                    all_tables.extend(high_confidence_tables)
                    # Use first successful engine (no fallback if we got results)
                    break
                else:
                    logger.info(f"Engine {engine_name} found no high-confidence tables")

            except Exception as e:
                logger.warning(f"Engine {engine_name} failed: {e}")
                continue

        # Classify table types
        for table in all_tables:
            table.table_type = self._classify_table_type(table.data)

        logger.info(f"Total tables extracted: {len(all_tables)}")
        return all_tables

    def _extract_pdfplumber(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None
    ) -> List[ExtractedTable]:
        """Extract tables using pdfplumber (best for digital PDFs)"""
        import pdfplumber

        tables = []

        with pdfplumber.open(pdf_path) as pdf:
            pages_to_process = pdf.pages[:max_pages] if max_pages else pdf.pages

            for page_num, page in enumerate(pages_to_process):
                try:
                    page_tables = page.extract_tables()

                    for idx, table_data in enumerate(page_tables):
                        if not table_data or len(table_data) < 2:
                            continue

                        # Convert to DataFrame
                        # First row is usually headers
                        headers = table_data[0] if table_data else []
                        rows = table_data[1:] if len(table_data) > 1 else []

                        # Clean headers (remove None, empty strings)
                        headers = [h if h else f"Column_{i}" for i, h in enumerate(headers)]

                        # Create DataFrame
                        df = pd.DataFrame(rows, columns=headers)

                        # Clean DataFrame
                        df = self._clean_dataframe(df)

                        # Skip if too small
                        if len(df) < 1 or len(df.columns) < 2:
                            continue

                        # Calculate confidence
                        confidence = self._calculate_confidence_pdfplumber(df, table_data)

                        tables.append(ExtractedTable(
                            data=df,
                            page_number=page_num + 1,
                            table_index=idx,
                            engine_used='pdfplumber',
                            confidence=confidence,
                            raw_text=str(table_data),
                            table_type=TableType.UNKNOWN,
                            metadata={
                                'rows': len(df),
                                'cols': len(df.columns),
                                'extraction_settings': page.extract_tables.__name__
                            }
                        ))

                except Exception as e:
                    logger.warning(f"pdfplumber failed on page {page_num + 1}: {e}")
                    continue

        return tables

    def _extract_camelot_lattice(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None
    ) -> List[ExtractedTable]:
        """Extract tables using Camelot lattice mode (bordered tables)"""
        import camelot

        tables = []

        try:
            # Extract with lattice mode (for bordered tables)
            pages = f"1-{max_pages}" if max_pages else "all"
            camelot_tables = camelot.read_pdf(
                pdf_path,
                pages=pages,
                flavor='lattice',
                line_scale=40
            )

            for idx, table in enumerate(camelot_tables):
                df = table.df

                # Clean DataFrame
                df = self._clean_dataframe(df)

                # Skip if too small
                if len(df) < 1 or len(df.columns) < 2:
                    continue

                # Get page number
                page_num = table.page

                # Confidence from Camelot's accuracy metric
                confidence = float(table.accuracy) / 100.0

                tables.append(ExtractedTable(
                    data=df,
                    page_number=page_num,
                    table_index=idx,
                    engine_used='camelot_lattice',
                    confidence=confidence,
                    raw_text=df.to_string(),
                    table_type=TableType.UNKNOWN,
                    metadata={
                        'rows': len(df),
                        'cols': len(df.columns),
                        'accuracy': table.accuracy,
                        'whitespace': table.whitespace
                    }
                ))

        except Exception as e:
            logger.warning(f"Camelot lattice extraction failed: {e}")

        return tables

    def _extract_camelot_stream(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None
    ) -> List[ExtractedTable]:
        """Extract tables using Camelot stream mode (borderless tables)"""
        import camelot

        tables = []

        try:
            # Extract with stream mode (for borderless tables)
            pages = f"1-{max_pages}" if max_pages else "all"
            camelot_tables = camelot.read_pdf(
                pdf_path,
                pages=pages,
                flavor='stream',
                edge_tol=50
            )

            for idx, table in enumerate(camelot_tables):
                df = table.df

                # Clean DataFrame
                df = self._clean_dataframe(df)

                # Skip if too small
                if len(df) < 1 or len(df.columns) < 2:
                    continue

                page_num = table.page
                confidence = float(table.accuracy) / 100.0

                tables.append(ExtractedTable(
                    data=df,
                    page_number=page_num,
                    table_index=idx,
                    engine_used='camelot_stream',
                    confidence=confidence,
                    raw_text=df.to_string(),
                    table_type=TableType.UNKNOWN,
                    metadata={
                        'rows': len(df),
                        'cols': len(df.columns),
                        'accuracy': table.accuracy
                    }
                ))

        except Exception as e:
            logger.warning(f"Camelot stream extraction failed: {e}")

        return tables

    def _extract_tabula(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None
    ) -> List[ExtractedTable]:
        """Extract tables using tabula-py (Java-based)"""
        import tabula

        tables = []

        try:
            # Extract all tables from PDF
            pages = f"1-{max_pages}" if max_pages else "all"
            tabula_tables = tabula.read_pdf(
                pdf_path,
                pages=pages,
                multiple_tables=True,
                pandas_options={'header': None}
            )

            for idx, df in enumerate(tabula_tables):
                # Clean DataFrame
                df = self._clean_dataframe(df)

                # Skip if too small
                if len(df) < 1 or len(df.columns) < 2:
                    continue

                # Estimate confidence based on completeness
                confidence = self._calculate_confidence_generic(df)

                tables.append(ExtractedTable(
                    data=df,
                    page_number=idx + 1,  # Tabula doesn't provide exact page
                    table_index=idx,
                    engine_used='tabula',
                    confidence=confidence,
                    raw_text=df.to_string(),
                    table_type=TableType.UNKNOWN,
                    metadata={
                        'rows': len(df),
                        'cols': len(df.columns)
                    }
                ))

        except Exception as e:
            logger.warning(f"Tabula extraction failed: {e}")

        return tables

    def _extract_pymupdf(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None
    ) -> List[ExtractedTable]:
        """Extract tables using PyMuPDF geometry-based approach"""
        import fitz

        tables = []

        try:
            doc = fitz.open(pdf_path)
            pages_to_process = min(max_pages, len(doc)) if max_pages else len(doc)

            for page_num in range(pages_to_process):
                page = doc[page_num]

                # Use PyMuPDF's find_tables (if available in version)
                try:
                    page_tables = page.find_tables()

                    for idx, table in enumerate(page_tables):
                        # Extract table data
                        table_data = table.extract()

                        if not table_data or len(table_data) < 2:
                            continue

                        # Convert to DataFrame
                        headers = table_data[0]
                        rows = table_data[1:]
                        df = pd.DataFrame(rows, columns=headers)

                        # Clean DataFrame
                        df = self._clean_dataframe(df)

                        # Skip if too small
                        if len(df) < 1 or len(df.columns) < 2:
                            continue

                        confidence = self._calculate_confidence_generic(df)

                        tables.append(ExtractedTable(
                            data=df,
                            page_number=page_num + 1,
                            table_index=idx,
                            engine_used='pymupdf',
                            confidence=confidence,
                            raw_text=df.to_string(),
                            table_type=TableType.UNKNOWN,
                            metadata={
                                'rows': len(df),
                                'cols': len(df.columns)
                            }
                        ))

                except AttributeError:
                    # find_tables not available in this version
                    logger.warning("PyMuPDF find_tables not available")
                    break

            doc.close()

        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}")

        return tables

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and normalize DataFrame"""
        # Remove completely empty rows
        df = df.dropna(how='all')

        # Remove completely empty columns
        df = df.dropna(axis=1, how='all')

        # Strip whitespace from string columns
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip()

        # Replace 'None', 'nan', etc. with actual None
        df = df.replace(['None', 'nan', 'NaN', ''], pd.NA)

        # Reset index
        df = df.reset_index(drop=True)

        return df

    def _calculate_confidence_pdfplumber(
        self,
        df: pd.DataFrame,
        raw_table: List[List]
    ) -> float:
        """Calculate confidence score for pdfplumber extraction"""
        score = 0.5  # Base score

        # More rows = higher confidence
        if len(df) >= 3:
            score += 0.2
        if len(df) >= 10:
            score += 0.1

        # More columns = higher confidence (tables usually have multiple columns)
        if len(df.columns) >= 3:
            score += 0.1

        # Check data completeness
        non_null_ratio = df.notna().sum().sum() / (len(df) * len(df.columns))
        score += non_null_ratio * 0.1

        return min(score, 1.0)

    def _calculate_confidence_generic(self, df: pd.DataFrame) -> float:
        """Calculate generic confidence score"""
        score = 0.5  # Base score

        # Check dimensions
        if len(df) >= 3 and len(df.columns) >= 2:
            score += 0.2

        # Check completeness
        non_null_ratio = df.notna().sum().sum() / (len(df) * len(df.columns))
        score += non_null_ratio * 0.3

        return min(score, 1.0)

    def _classify_table_type(self, df: pd.DataFrame) -> TableType:
        """Classify table type based on column names and content"""
        # Convert column names to string and lowercase
        columns_str = ' '.join([str(col).lower() for col in df.columns])

        # Check for first few rows content too
        content_sample = ' '.join([
            str(val).lower()
            for val in df.head(3).values.flatten()
            if pd.notna(val)
        ])

        combined_text = columns_str + ' ' + content_sample

        # Item table patterns (Macedonian + English)
        item_patterns = [
            r'р\.?\s*бр', r'реден', r'назив', r'опис', r'производ',
            r'артикл', r'количин', r'цена', r'единица', r'мера',
            r'item', r'product', r'description', r'quantity', r'price',
            r'unit', r'amount'
        ]

        # Bidder table patterns
        bidder_patterns = [
            r'понудувач', r'учесник', r'понуда', r'компанија',
            r'bidder', r'participant', r'company', r'vendor', r'supplier'
        ]

        # Specification patterns
        spec_patterns = [
            r'спецификац', r'барањ', r'критериум', r'карактеристик',
            r'specification', r'requirement', r'criteria', r'characteristic'
        ]

        # Financial patterns
        financial_patterns = [
            r'финансиск', r'буџет', r'износ', r'вкупно', r'тотал',
            r'financial', r'budget', r'total', r'cost', r'payment'
        ]

        # Count matches
        item_score = sum(1 for p in item_patterns if re.search(p, combined_text))
        bidder_score = sum(1 for p in bidder_patterns if re.search(p, combined_text))
        spec_score = sum(1 for p in spec_patterns if re.search(p, combined_text))
        financial_score = sum(1 for p in financial_patterns if re.search(p, combined_text))

        # Return type with highest score
        scores = {
            TableType.ITEMS: item_score,
            TableType.BIDDERS: bidder_score,
            TableType.SPECIFICATIONS: spec_score,
            TableType.FINANCIAL: financial_score
        }

        max_score = max(scores.values())
        if max_score >= 2:  # At least 2 patterns matched
            return max(scores, key=scores.get)

        return TableType.UNKNOWN


class ItemExtractor:
    """
    Extract structured items from tables with Macedonian language support

    Extracts procurement items from tender documents including:
    - Item number/ID
    - Item name/description
    - Quantity
    - Unit of measure
    - Unit price
    - Total price
    - Specifications
    """

    # Column mapping patterns (regex -> standardized name)
    COLUMN_PATTERNS = {
        # Item number (Macedonian + English)
        r'р\.?\s*бр|реден.*број|ред.*бр|rbr|item.*no|#|no\.?$': 'item_number',

        # Item name/description
        r'назив|име|опис|производ|артикл|наименование|name|desc|product|item': 'item_name',

        # Quantity
        r'колич|кол\.?|бр\.?\s*на|quantity|qty|amount': 'quantity',

        # Unit of measure
        r'единица|мера|ед\.?\s*мера|ј\.?\s*м|unit$|uom|measure': 'unit',

        # Unit price
        r'единечна.*цена|цена.*единица|ед\.?\s*цена|unit.*price|price.*unit': 'unit_price',

        # Total price
        r'вкупн|вкупно.*цена|тотал|укупн|total|sum|amount': 'total_price',

        # Specifications
        r'спец|тех.*барањ|карактер|техн.*опис|spec|requirement|detail': 'specifications',

        # Additional fields
        r'cpv|класиф': 'cpv_code',
        r'забелешк|напомен|note|remark': 'notes',
    }

    def __init__(self):
        self.compiled_patterns = {
            re.compile(pattern, re.IGNORECASE | re.UNICODE): field
            for pattern, field in self.COLUMN_PATTERNS.items()
        }

    def extract_items(self, tables: List[ExtractedTable]) -> List[Dict]:
        """
        Extract procurement items from tables

        Args:
            tables: List of ExtractedTable objects

        Returns:
            List of item dictionaries with standardized fields
        """
        all_items = []

        for table in tables:
            # Only process ITEMS or UNKNOWN type tables
            if table.table_type not in [TableType.ITEMS, TableType.UNKNOWN]:
                continue

            # Map columns to standard names
            mapped_df = self._map_columns(table.data)

            # Extract items from rows
            for row_idx, row in mapped_df.iterrows():
                item = self._parse_row(row, table, row_idx)

                if item and self._is_valid_item(item):
                    all_items.append(item)

        logger.info(f"Extracted {len(all_items)} items from {len(tables)} tables")
        return all_items

    def _map_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map DataFrame columns to standardized names"""
        # Create mapping
        column_mapping = {}

        for col in df.columns:
            col_str = str(col).strip()

            # Try to match against patterns
            for pattern, standard_name in self.compiled_patterns.items():
                if pattern.search(col_str):
                    column_mapping[col] = standard_name
                    break

        # Rename columns
        mapped_df = df.rename(columns=column_mapping)

        logger.debug(f"Column mapping: {column_mapping}")
        return mapped_df

    def _parse_row(
        self,
        row: pd.Series,
        table: ExtractedTable,
        row_idx: int
    ) -> Optional[Dict]:
        """Parse a single row into an item dictionary"""
        try:
            item = {
                'source_table_page': table.page_number,
                'source_table_index': table.table_index,
                'source_row_index': row_idx,
                'extraction_engine': table.engine_used,
                'extraction_confidence': table.confidence,
            }

            # Extract standard fields
            if 'item_number' in row.index:
                item['item_number'] = self._clean_text(row['item_number'])

            if 'item_name' in row.index:
                item['item_name'] = self._clean_text(row['item_name'])

            if 'quantity' in row.index:
                item['quantity'] = self._parse_number(row['quantity'])

            if 'unit' in row.index:
                item['unit'] = self._clean_text(row['unit'])

            if 'unit_price' in row.index:
                item['unit_price'] = self._parse_number(row['unit_price'])

            if 'total_price' in row.index:
                item['total_price'] = self._parse_number(row['total_price'])

            if 'specifications' in row.index:
                item['specifications'] = self._clean_text(row['specifications'])

            if 'cpv_code' in row.index:
                item['cpv_code'] = self._clean_text(row['cpv_code'])

            if 'notes' in row.index:
                item['notes'] = self._clean_text(row['notes'])

            # Include original data
            item['raw_data'] = row.to_dict()

            return item

        except Exception as e:
            logger.warning(f"Failed to parse row {row_idx}: {e}")
            return None

    def _is_valid_item(self, item: Dict) -> bool:
        """Validate that item has minimum required fields"""
        # Must have at least item name or number
        has_identifier = (
            item.get('item_name') or
            item.get('item_number')
        )

        # Check if item name is not just a header
        if item.get('item_name'):
            name = str(item['item_name']).lower()
            # Skip header rows
            header_words = ['назив', 'опис', 'name', 'description', 'item', 'артикл']
            if any(name == word for word in header_words):
                return False

        return bool(has_identifier)

    def _clean_text(self, value: Any) -> Optional[str]:
        """Clean text value"""
        if pd.isna(value):
            return None

        text = str(value).strip()

        # Remove None strings
        if text.lower() in ['none', 'nan', '']:
            return None

        return text

    def _parse_number(self, value: Any) -> Optional[float]:
        """Parse numeric value (handles Macedonian formatting)"""
        if pd.isna(value):
            return None

        # Convert to string
        text = str(value).strip()

        # Remove currency symbols
        text = re.sub(r'[денMKDEUR€$]', '', text, flags=re.IGNORECASE)

        # Handle Macedonian number format (1.234,56)
        # vs English format (1,234.56)

        # Check which format is used
        if ',' in text and '.' in text:
            # Both separators present
            comma_pos = text.rfind(',')
            dot_pos = text.rfind('.')

            if comma_pos > dot_pos:
                # Macedonian format: 1.234,56
                text = text.replace('.', '').replace(',', '.')
            else:
                # English format: 1,234.56
                text = text.replace(',', '')
        elif ',' in text:
            # Only comma - assume decimal separator
            text = text.replace(',', '.')

        # Remove remaining spaces
        text = text.replace(' ', '')

        try:
            return float(text)
        except ValueError:
            logger.warning(f"Could not parse number: {value}")
            return None


# Convenience functions
def extract_tables_from_pdf(
    pdf_path: str,
    engine: Optional[str] = None,
    min_confidence: float = 0.3
) -> List[ExtractedTable]:
    """
    Extract tables from PDF file

    Args:
        pdf_path: Path to PDF file
        engine: Preferred engine ('pdfplumber', 'camelot', 'tabula', 'pymupdf')
        min_confidence: Minimum confidence threshold

    Returns:
        List of ExtractedTable objects
    """
    extractor = TableExtractor(preferred_engine=engine)
    return extractor.extract_tables(pdf_path, min_confidence=min_confidence)


def extract_items_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Extract procurement items from PDF file

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of item dictionaries
    """
    # Extract tables
    tables = extract_tables_from_pdf(pdf_path)

    # Extract items
    item_extractor = ItemExtractor()
    items = item_extractor.extract_items(tables)

    return items


# Example usage and testing
if __name__ == '__main__':
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python table_extraction.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"TABLE EXTRACTION TEST")
    print(f"{'='*60}\n")

    print(f"PDF: {pdf_path}\n")

    # Extract tables
    print("Extracting tables...")
    tables = extract_tables_from_pdf(pdf_path)

    print(f"\nFound {len(tables)} tables:\n")

    for i, table in enumerate(tables):
        print(f"\nTable {i+1}:")
        print(f"  Page: {table.page_number}")
        print(f"  Engine: {table.engine_used}")
        print(f"  Type: {table.table_type.value}")
        print(f"  Confidence: {table.confidence:.2f}")
        print(f"  Dimensions: {len(table.data)} rows x {len(table.data.columns)} columns")
        print(f"  Columns: {list(table.data.columns)}")
        print(f"\nFirst 3 rows:")
        print(table.data.head(3))

    # Extract items
    print(f"\n{'='*60}")
    print("Extracting items...")
    items = extract_items_from_pdf(pdf_path)

    print(f"\nFound {len(items)} items:\n")

    for i, item in enumerate(items[:5]):  # Show first 5
        print(f"\nItem {i+1}:")
        for key, value in item.items():
            if key != 'raw_data':
                print(f"  {key}: {value}")

    print(f"\n{'='*60}\n")
