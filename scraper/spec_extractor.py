"""
Technical Specification Extractor for Procurement Documents

Extracts:
- Product names (medicines, medical devices, equipment, construction materials)
- Quantities and units
- Technical specifications (dimensions, capacity, model requirements)
- Price per unit
- Lot structure (lot number, items per lot)

Supports:
- Macedonian and English text
- Table parsing
- Multiple document formats (specs, BOQ, price lists)
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class ProductItem:
    """Single product/item from technical specification"""
    name: str
    name_mk: Optional[str] = None  # Macedonian name
    name_en: Optional[str] = None  # English name (if available)
    quantity: Optional[float] = None
    unit: Optional[str] = None  # piece, kg, liter, meter, etc.
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    specifications: Dict[str, str] = field(default_factory=dict)
    lot_number: Optional[int] = None
    item_number: Optional[int] = None
    cpv_code: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    raw_text: Optional[str] = None  # Original text for debugging


@dataclass
class LotInfo:
    """Lot information from tender"""
    lot_number: int
    title: str
    description: Optional[str] = None
    estimated_value: Optional[Decimal] = None
    items: List[ProductItem] = field(default_factory=list)
    cpv_code: Optional[str] = None
    winner: Optional[str] = None
    winning_price: Optional[Decimal] = None


@dataclass
class TechnicalSpecification:
    """Complete technical specification extracted from document"""
    tender_id: str
    document_name: str
    lots: List[LotInfo] = field(default_factory=list)
    items: List[ProductItem] = field(default_factory=list)  # Non-lot items
    total_estimated_value: Optional[Decimal] = None
    currency: str = "MKD"
    extraction_confidence: float = 0.0
    raw_tables: List[List[List[str]]] = field(default_factory=list)


class SpecificationExtractor:
    """
    Extract technical specifications from procurement document text
    """

    # Unit patterns (Macedonian and English)
    UNIT_PATTERNS = {
        # Count
        r'\b(парче|пар|комад|ком\.?|piece|pcs?|unit|бр\.?)\b': 'piece',
        r'\b(кутија|кутии|box|boxes|pkg)\b': 'box',
        r'\b(пакет|пакети|pack|package)\b': 'package',
        r'\b(сет|sets?)\b': 'set',

        # Weight
        r'\b(килограм|кг\.?|kg|kilogram)\b': 'kg',
        r'\b(грам|гр\.?|g|gram)\b': 'g',
        r'\b(тон|тони|ton|tonnes?)\b': 'ton',
        r'\b(мг\.?|mg|milligram)\b': 'mg',

        # Volume
        r'\b(литар|литри|л\.?|liter|litre|l)\b': 'liter',
        r'\b(мл\.?|ml|milliliter)\b': 'ml',
        r'\b(м3|m3|cubic meter)\b': 'm3',

        # Length
        r'\b(метар|метри|м\.?|meter|metre|m)\b': 'meter',
        r'\b(км\.?|km|kilometer)\b': 'km',
        r'\b(см\.?|cm|centimeter)\b': 'cm',
        r'\b(мм\.?|mm|millimeter)\b': 'mm',

        # Area
        r'\b(м2|m2|square meter|квадратен метар)\b': 'm2',

        # Time
        r'\b(месец|месеци|month|months)\b': 'month',
        r'\b(година|години|year|years)\b': 'year',
        r'\b(ден|дена|денови|day|days)\b': 'day',

        # Medical specific
        r'\b(ампула|ампули|ampul|ampule|amp)\b': 'ampule',
        r'\b(таблета|таблети|tablet|tab)\b': 'tablet',
        r'\b(капсула|капсули|capsule|cap)\b': 'capsule',
        r'\b(флакон|флакони|vial|bottle)\b': 'vial',
        r'\b(доза|дози|dose|doses)\b': 'dose',
    }

    # Medical product patterns
    MEDICINE_PATTERNS = [
        # Generic medicine names (often Latin/English in Macedonian docs)
        r'([A-Za-z]{3,}(?:\s+[A-Za-z]+)*)\s*(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|IU))',
        # Medicine with dosage form
        r'([A-Za-z]{3,}(?:\s+[A-Za-z]+)*)\s*(таблети|капсули|ампули|раствор|инјекција)',
        # ATC code format
        r'([A-Z]\d{2}[A-Z]{2}\d{2})',
    ]

    # Medical device patterns
    DEVICE_PATTERNS = [
        # Stents, implants
        r'(стент|stent)\s*([\w\s]+)',
        r'(имплант|implant)\s*([\w\s]+)',
        r'(катетер|catheter)\s*([\w\s]+)',
        r'(протеза|prosthesis|prosthetic)\s*([\w\s]+)',
        # Intraocular lens
        r'(интраокуларн[аи]? леќ[аи]?|intraocular lens|IOL)',
        # Surgical instruments
        r'(хируршки инструмент|surgical instrument)',
        # Equipment
        r'(апарат|уред|машина|device|equipment|apparatus)\s+за\s+([\w\s]+)',
    ]

    # Construction/works patterns
    CONSTRUCTION_PATTERNS = [
        r'(бетон|concrete)\s*([А-Яа-яA-Za-z0-9\s/]+)',
        r'(арматура|reinforcement|rebar)',
        r'(керамички плочки|tiles|ceramic)',
        r'(асфалт|asphalt)',
        r'(цевка|pipe|тръба)\s*([\w\s]+)',
    ]

    # Lot patterns
    LOT_PATTERNS = [
        r'[Дд]ел\s*(\d+)',  # Дел 1, Дел 2
        r'[Лл]от\s*(\d+)',  # Лот 1
        r'[Pp]art\s*(\d+)',
        r'[Ll]ot\s*(\d+)',
        r'[Сс]тавка\s*(\d+)',  # Ставка 1
    ]

    # Quantity patterns
    QUANTITY_PATTERNS = [
        r'[Кк]оличина[:\s]+(\d+(?:[,\.]\d+)?)',
        r'[Qq]uantity[:\s]+(\d+(?:[,\.]\d+)?)',
        r'[Бб]р(?:ој)?[:\s\.]+(\d+(?:[,\.]\d+)?)',
        r'(\d+(?:[,\.]\d+)?)\s*(?:парче|ком|бр|pcs|piece)',
    ]

    # Price patterns
    PRICE_PATTERNS = [
        r'(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{1,2})?)\s*(?:ден|МКД|MKD)',
        r'(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{1,2})?)\s*(?:EUR|евро)',
        r'[Цц]ена[:\s]+(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{1,2})?)',
        r'[Pp]rice[:\s]+(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{1,2})?)',
    ]

    def __init__(self):
        self.compiled_patterns = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance"""
        for pattern, unit in self.UNIT_PATTERNS.items():
            self.compiled_patterns[pattern] = (re.compile(pattern, re.IGNORECASE | re.UNICODE), unit)

    def extract_from_text(self, text: str, tender_id: str = "unknown",
                          document_name: str = "unknown") -> TechnicalSpecification:
        """
        Extract technical specifications from document text

        Args:
            text: Full text content from PDF
            tender_id: Tender identifier
            document_name: Source document name

        Returns:
            TechnicalSpecification with extracted items and lots
        """
        spec = TechnicalSpecification(
            tender_id=tender_id,
            document_name=document_name
        )

        # Split text into sections
        lines = text.split('\n')

        # Track current lot
        current_lot = None
        current_lot_number = 0

        # Process line by line looking for items
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Check for lot boundary
            lot_match = self._extract_lot_number(line)
            if lot_match:
                # Save previous lot
                if current_lot and current_lot.items:
                    spec.lots.append(current_lot)

                current_lot_number = lot_match
                current_lot = LotInfo(
                    lot_number=current_lot_number,
                    title=self._extract_lot_title(line, lines, i)
                )
                continue

            # Try to extract product item
            item = self._extract_product_item(line, lines, i)
            if item:
                item.lot_number = current_lot_number if current_lot else None

                if current_lot:
                    current_lot.items.append(item)
                else:
                    spec.items.append(item)

        # Save last lot
        if current_lot and current_lot.items:
            spec.lots.append(current_lot)

        # Calculate confidence
        total_items = len(spec.items) + sum(len(lot.items) for lot in spec.lots)
        spec.extraction_confidence = min(1.0, total_items / 10.0)  # Simple heuristic

        logger.info(f"Extracted {total_items} items from {document_name}, "
                   f"{len(spec.lots)} lots, confidence: {spec.extraction_confidence:.2f}")

        return spec

    def _extract_lot_number(self, line: str) -> Optional[int]:
        """Extract lot number from line"""
        for pattern in self.LOT_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass
        return None

    def _extract_lot_title(self, line: str, lines: List[str], index: int) -> str:
        """Extract lot title from line and context"""
        # Remove lot number pattern
        title = line
        for pattern in self.LOT_PATTERNS:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        # Clean up
        title = re.sub(r'^[\s\-:]+', '', title)
        title = re.sub(r'[\s\-:]+$', '', title)

        # If title is empty, try next line
        if not title and index + 1 < len(lines):
            title = lines[index + 1].strip()

        return title or f"Lot {index}"

    def _extract_product_item(self, line: str, lines: List[str], index: int) -> Optional[ProductItem]:
        """
        Extract product item from line

        Looks for:
        - Item number pattern (1., 1), a., etc.)
        - Product name
        - Quantity and unit
        - Price
        """
        # Skip header/footer lines
        skip_patterns = [
            r'^страна\s*\d+',  # Page numbers
            r'^page\s*\d+',
            r'^\d+$',  # Just numbers
            r'^[\-_=]+$',  # Separators
            r'^вкупно|^total',  # Totals
            r'^техничка спецификација',  # Headers
            r'^technical specification',
        ]
        for skip in skip_patterns:
            if re.match(skip, line, re.IGNORECASE):
                return None

        # Check for item number pattern at start
        item_number_match = re.match(r'^(\d+)[.\)]\s*(.+)', line)
        if not item_number_match:
            # Also try letter patterns
            item_number_match = re.match(r'^([a-zA-Zа-яА-Я])[.\)]\s*(.+)', line)

        if not item_number_match:
            # Look for medicine/device patterns even without item number
            for pattern in self.MEDICINE_PATTERNS + self.DEVICE_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    break
            else:
                return None  # No recognizable pattern

        # Extract item number
        try:
            item_num = int(item_number_match.group(1)) if item_number_match else None
            remaining = item_number_match.group(2) if item_number_match else line
        except (ValueError, AttributeError):
            item_num = None
            remaining = line

        # Extract name (first substantial part)
        name = self._extract_product_name(remaining)
        if not name or len(name) < 3:
            return None

        # Extract quantity
        quantity, unit = self._extract_quantity(line, lines, index)

        # Extract price
        unit_price, total_price = self._extract_prices(line, lines, index)

        # Extract specifications
        specs = self._extract_specifications(line, lines, index)

        return ProductItem(
            name=name,
            name_mk=name if self._is_cyrillic(name) else None,
            name_en=name if not self._is_cyrillic(name) else None,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            total_price=total_price,
            specifications=specs,
            item_number=item_num,
            raw_text=line
        )

    def _extract_product_name(self, text: str) -> str:
        """Extract product name from text"""
        # Remove quantity/price patterns from end
        name = text
        for pattern in self.QUANTITY_PATTERNS + self.PRICE_PATTERNS:
            name = re.sub(pattern, '', name)

        # Remove unit patterns from end
        for pattern in self.UNIT_PATTERNS.keys():
            name = re.sub(pattern + r'\s*$', '', name, flags=re.IGNORECASE)

        # Clean up
        name = re.sub(r'\s+', ' ', name)
        name = name.strip(' \t\n\r-:,.')

        # Truncate if too long
        if len(name) > 200:
            name = name[:200]

        return name

    def _extract_quantity(self, line: str, lines: List[str], index: int) -> Tuple[Optional[float], Optional[str]]:
        """Extract quantity and unit from line or context"""
        # Try quantity patterns
        for pattern in self.QUANTITY_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                try:
                    qty = float(match.group(1).replace(',', '.'))
                    # Find associated unit
                    unit = self._find_unit_in_text(line)
                    return qty, unit
                except ValueError:
                    pass

        # Try to find standalone number + unit
        num_unit_match = re.search(r'(\d+(?:[,\.]\d+)?)\s*([а-яА-Яa-zA-Z]{1,15})', line)
        if num_unit_match:
            try:
                qty = float(num_unit_match.group(1).replace(',', '.'))
                unit_text = num_unit_match.group(2)
                unit = self._normalize_unit(unit_text)
                if unit:
                    return qty, unit
            except ValueError:
                pass

        return None, None

    def _find_unit_in_text(self, text: str) -> Optional[str]:
        """Find and normalize unit in text"""
        for pattern, normalized_unit in self.compiled_patterns.values():
            if pattern.search(text):
                return normalized_unit
        return None

    def _normalize_unit(self, unit_text: str) -> Optional[str]:
        """Normalize unit text to standard form"""
        unit_lower = unit_text.lower()
        for pattern, normalized_unit in self.compiled_patterns.values():
            if pattern.search(unit_lower):
                return normalized_unit
        return unit_text if len(unit_text) <= 10 else None

    def _extract_prices(self, line: str, lines: List[str], index: int) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Extract unit price and total price"""
        prices = []
        for pattern in self.PRICE_PATTERNS:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                try:
                    # Parse Macedonian/European number format
                    price_str = match.group(1)
                    # Convert: 1.234,56 -> 1234.56
                    price_str = price_str.replace('.', '').replace(',', '.')
                    prices.append(Decimal(price_str))
                except Exception:
                    pass

        if len(prices) >= 2:
            return prices[0], prices[1]  # unit, total
        elif len(prices) == 1:
            return prices[0], None
        return None, None

    def _extract_specifications(self, line: str, lines: List[str], index: int) -> Dict[str, str]:
        """Extract technical specifications (dimensions, capacity, etc.)"""
        specs = {}

        # Look for specification patterns
        spec_patterns = [
            (r'димензии?[:\s]+([^\n,]+)', 'dimensions'),
            (r'dimension[s]?[:\s]+([^\n,]+)', 'dimensions'),
            (r'тежина[:\s]+([^\n,]+)', 'weight'),
            (r'weight[:\s]+([^\n,]+)', 'weight'),
            (r'капацитет[:\s]+([^\n,]+)', 'capacity'),
            (r'capacity[:\s]+([^\n,]+)', 'capacity'),
            (r'материјал[:\s]+([^\n,]+)', 'material'),
            (r'material[:\s]+([^\n,]+)', 'material'),
            (r'боја[:\s]+([^\n,]+)', 'color'),
            (r'color[:\s]+([^\n,]+)', 'color'),
            (r'производител[:\s]+([^\n,]+)', 'manufacturer'),
            (r'manufacturer[:\s]+([^\n,]+)', 'manufacturer'),
            (r'модел[:\s]+([^\n,]+)', 'model'),
            (r'model[:\s]+([^\n,]+)', 'model'),
            # Medical specific
            (r'доза[:\s]+([^\n,]+)', 'dosage'),
            (r'dosage[:\s]+([^\n,]+)', 'dosage'),
            (r'форма[:\s]+([^\n,]+)', 'form'),
            (r'форм[:\s]+([^\n,]+)', 'form'),
            (r'јачина[:\s]+([^\n,]+)', 'strength'),
            (r'strength[:\s]+([^\n,]+)', 'strength'),
        ]

        # Check current line and next few lines
        context = line
        for j in range(1, 4):
            if index + j < len(lines):
                context += ' ' + lines[index + j]

        for pattern, spec_name in spec_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                specs[spec_name] = match.group(1).strip()

        return specs

    def _is_cyrillic(self, text: str) -> bool:
        """Check if text contains Cyrillic characters"""
        return any(0x0400 <= ord(c) <= 0x04FF for c in text)

    def extract_from_tables(self, tables: List[List[List[str]]],
                           tender_id: str = "unknown") -> List[ProductItem]:
        """
        Extract items from pre-extracted tables

        Args:
            tables: List of tables from PDF parser

        Returns:
            List of ProductItem extracted from tables
        """
        items = []

        for table_idx, table in enumerate(tables):
            if len(table) < 2:  # Need header + at least one row
                continue

            # Try to identify columns
            header = table[0] if table else []
            col_mapping = self._identify_columns(header)

            if not col_mapping:
                continue

            # Extract items from rows
            for row_idx, row in enumerate(table[1:], start=1):
                try:
                    item = self._extract_item_from_row(row, col_mapping)
                    if item:
                        item.item_number = row_idx
                        items.append(item)
                except Exception as e:
                    logger.warning(f"Failed to extract row {row_idx}: {e}")

        logger.info(f"Extracted {len(items)} items from {len(tables)} tables")
        return items

    def _identify_columns(self, header: List[str]) -> Dict[str, int]:
        """
        Identify column indices from header row.

        Expected format from Macedonian procurement documents:
        - Шифра (CPV code)
        - Назив на ставка (Item name)
        - Димензија/тежина/единица (Specifications)
        - Мерна единица (Unit)
        - Количина (Quantity)
        - Единечна цена (Unit price)
        - Вкупна цена (без ДДВ) (Total price without VAT)
        - ДДВ (VAT)
        - Цена со ДДВ (Price with VAT)
        """
        mapping = {}

        # Column identification patterns (Macedonian + English)
        column_patterns = {
            'cpv_code': ['шифра', 'cpv', 'код'],
            'name': ['назив', 'name', 'description', 'опис', 'ставка'],
            'specifications': ['димензија', 'тежина', 'карактеристик', 'specification', 'specs'],
            'unit': ['мерна единица', 'единица', 'мерка', 'unit', 'ем'],
            'quantity': ['количина', 'бр', 'qty', 'quantity', 'број'],
            'unit_price': ['единечна', 'единична цена', 'unit price'],
            'total_price_no_vat': ['вкупна цена', 'без ддв', 'total without vat', 'цена без'],
            'vat': ['ддв', 'vat', 'данок'],
            'total_price_with_vat': ['цена со ддв', 'total with vat', 'со ддв'],
        }

        for i, col in enumerate(header):
            col_lower = col.lower().strip()

            for field, patterns in column_patterns.items():
                if field in mapping:
                    continue  # Already found this field

                for pattern in patterns:
                    if pattern in col_lower:
                        mapping[field] = i
                        break

        # Fallback: if we have price columns but couldn't distinguish them
        # First price column = unit_price, second = total without VAT, third = total with VAT
        if 'unit_price' not in mapping and 'total_price_no_vat' not in mapping:
            price_cols = []
            for i, col in enumerate(header):
                if 'цена' in col.lower() or 'price' in col.lower():
                    price_cols.append(i)

            if len(price_cols) >= 1:
                mapping['unit_price'] = price_cols[0]
            if len(price_cols) >= 2:
                mapping['total_price_no_vat'] = price_cols[1]
            if len(price_cols) >= 3:
                mapping['vat'] = price_cols[2]
            if len(price_cols) >= 4:
                mapping['total_price_with_vat'] = price_cols[3]

        return mapping

    def _extract_item_from_row(self, row: List[str], col_mapping: Dict[str, int]) -> Optional[ProductItem]:
        """
        Extract ProductItem from table row using column mapping.

        Captures all fields from Macedonian procurement bid tables:
        - CPV code (Шифра)
        - Name (Назив на ставка)
        - Specifications (Димензија/тежина/единица)
        - Unit (Мерна единица)
        - Quantity (Количина)
        - Unit price (Единечна цена)
        - Total without VAT (Вкупна цена без ДДВ)
        - VAT (ДДВ)
        - Total with VAT (Цена со ДДВ)
        """
        if 'name' not in col_mapping:
            return None

        name = row[col_mapping['name']] if col_mapping['name'] < len(row) else None
        if not name or len(name.strip()) < 2:
            return None

        # Clean up name
        name = name.strip()

        # Extract CPV code
        cpv_code = None
        if 'cpv_code' in col_mapping and col_mapping['cpv_code'] < len(row):
            cpv_raw = row[col_mapping['cpv_code']].strip()
            # CPV codes can be like "30213100-6" or "30213100\n-6"
            cpv_raw = cpv_raw.replace('\n', '').replace(' ', '')
            if cpv_raw and len(cpv_raw) >= 8:
                cpv_code = cpv_raw

        # Extract specifications
        specs = {}
        if 'specifications' in col_mapping and col_mapping['specifications'] < len(row):
            spec_text = row[col_mapping['specifications']].strip()
            if spec_text:
                specs['dimensions'] = spec_text

        # Extract quantity
        quantity = None
        if 'quantity' in col_mapping and col_mapping['quantity'] < len(row):
            try:
                qty_str = row[col_mapping['quantity']].replace(',', '.').replace(' ', '').strip()
                quantity = float(qty_str)
            except (ValueError, AttributeError):
                pass

        # Extract unit
        unit = None
        if 'unit' in col_mapping and col_mapping['unit'] < len(row):
            unit_raw = row[col_mapping['unit']].strip()
            unit = self._normalize_unit(unit_raw) or unit_raw

        # Parse price - handles Macedonian format: 19.399,00 -> 19399.00
        def parse_price(val: str) -> Optional[Decimal]:
            if not val:
                return None
            try:
                # Remove spaces
                val = val.strip().replace(' ', '')
                # Remove currency suffix
                val = val.replace('ден', '').replace('МКД', '').replace('MKD', '').strip()
                # Handle Macedonian format: 19.399,00 (thousands with . , decimal with ,)
                if ',' in val and '.' in val:
                    # 19.399,00 -> 19399.00
                    val = val.replace('.', '').replace(',', '.')
                elif ',' in val:
                    # 399,00 -> 399.00
                    val = val.replace(',', '.')
                return Decimal(val)
            except Exception:
                return None

        # Extract all price fields
        unit_price = None
        if 'unit_price' in col_mapping and col_mapping['unit_price'] < len(row):
            unit_price = parse_price(row[col_mapping['unit_price']])

        total_price_no_vat = None
        if 'total_price_no_vat' in col_mapping and col_mapping['total_price_no_vat'] < len(row):
            total_price_no_vat = parse_price(row[col_mapping['total_price_no_vat']])

        vat_amount = None
        if 'vat' in col_mapping and col_mapping['vat'] < len(row):
            vat_amount = parse_price(row[col_mapping['vat']])
            if vat_amount:
                specs['vat_amount'] = str(vat_amount)

        total_price_with_vat = None
        if 'total_price_with_vat' in col_mapping and col_mapping['total_price_with_vat'] < len(row):
            total_price_with_vat = parse_price(row[col_mapping['total_price_with_vat']])
            if total_price_with_vat:
                specs['total_with_vat'] = str(total_price_with_vat)

        return ProductItem(
            name=name,
            cpv_code=cpv_code,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            total_price=total_price_no_vat,  # Store without VAT as the base price
            specifications=specs,
            raw_text=' | '.join([str(c) for c in row])  # Store raw row for debugging
        )


# Convenience function
def extract_specifications(text: str, tables: List[List[List[str]]] = None,
                          tender_id: str = "unknown",
                          document_name: str = "unknown") -> TechnicalSpecification:
    """
    Extract technical specifications from document

    Usage:
        spec = extract_specifications(pdf_text, pdf_tables, tender_id="12345/2025")
        for lot in spec.lots:
            for item in lot.items:
                print(f"{item.name}: {item.quantity} {item.unit}")
    """
    extractor = SpecificationExtractor()
    spec = extractor.extract_from_text(text, tender_id, document_name)

    # Also extract from tables if provided
    if tables:
        table_items = extractor.extract_from_tables(tables, tender_id)
        spec.items.extend(table_items)

    return spec
