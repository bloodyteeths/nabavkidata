"""
Financial Bid (Финансиска понуда) Extractor for Macedonian Procurement Documents

This specialized extractor parses the standardized format of financial bid documents
submitted through the e-nabavki.gov.mk system.

Format Structure (all Financial Bid documents follow this pattern):
================================================================================
Дел I Финансиска понуда
Врз основа на огласот {TENDER_ID} објавен од страна на {PROCURING_ENTITY}...

Финансиска понуда
[Optional: Предмет на дел: {LOT_DESCRIPTION}]

| Шифра | Назив на ставка | Мерна единица | Количина | Единечна цена | Вкупна цена (без ДДВ) | ДДВ | Цена со ДДВ |
|-------|-----------------|---------------|----------|---------------|----------------------|-----|-------------|
| CPV   | Item name       | Unit          | Qty      | Unit Price    | Total w/o VAT        | VAT | Total w/VAT |

Вкупно: {TOTAL_NO_VAT} ден | {VAT} ден | {TOTAL_WITH_VAT} ден

Вкупната цена на нашата понуда... изнесува: {AMOUNT} ({AMOUNT_IN_WORDS}) денари.
================================================================================

Author: Nabavkidata AI Agent
Date: 2025-11-26
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


@dataclass
class BidItem:
    """Single item from financial bid table"""
    cpv_code: Optional[str] = None
    name: str = ""
    unit: Optional[str] = None
    quantity: Optional[float] = None
    unit_price_mkd: Optional[Decimal] = None
    total_price_mkd: Optional[Decimal] = None  # Without VAT
    vat_amount_mkd: Optional[Decimal] = None
    total_with_vat_mkd: Optional[Decimal] = None
    lot_number: Optional[int] = None
    lot_description: Optional[str] = None
    item_number: Optional[int] = None
    raw_text: Optional[str] = None


@dataclass
class FinancialBid:
    """Complete financial bid extracted from document"""
    tender_id: str
    procuring_entity: Optional[str] = None
    tender_title: Optional[str] = None
    items: List[BidItem] = field(default_factory=list)
    total_amount_mkd: Optional[Decimal] = None
    total_vat_mkd: Optional[Decimal] = None
    total_with_vat_mkd: Optional[Decimal] = None
    bidder_acceptance: Dict[str, bool] = field(default_factory=dict)
    extraction_confidence: float = 0.0
    source_document: Optional[str] = None


class FinancialBidExtractor:
    """
    Extract structured data from Macedonian financial bid PDFs.

    These documents follow a standardized format from e-nabavki.gov.mk
    and contain the most valuable product/service data.
    """

    # Header text that identifies a financial bid document
    BID_HEADER_PATTERNS = [
        r'финансиска понуда',
        r'financial offer',
        r'дел\s+i\s+финансиска',
    ]

    # Pattern to extract tender ID and procuring entity from intro
    INTRO_PATTERN = re.compile(
        r'огласот\s+(\d+/\d+)\s+објавен\s+од\s+страна\s+на\s+(.+?),?\s+за\s+(.+?),?\s+со\s+спроведување',
        re.IGNORECASE | re.DOTALL
    )

    # Pattern for lot sections
    LOT_PATTERN = re.compile(
        r'предмет\s+на\s+дел:\s*(.+?)(?=\n|$)',
        re.IGNORECASE
    )

    # Table header detection - these columns are standard in all bid documents
    TABLE_HEADERS = {
        'cpv': ['шифра', 'cpv'],
        'name': ['назив на ставка', 'назив', 'опис'],
        'unit': ['мерна единица', 'единица', 'ед.'],
        'quantity': ['количина', 'кол.'],
        'unit_price': ['единечна цена', 'ед. цена'],
        'total_no_vat': ['вкупна цена', 'без ддв', 'вкупно'],
        'vat': ['ддв'],
        'total_with_vat': ['цена со ддв', 'со ддв'],
    }

    # Pattern to extract total summary
    TOTAL_PATTERN = re.compile(
        r'вкупната\s+цена[^:]*изнесува[:\s]*'
        r'([\d\.,]+)\s*'
        r'\(([^)]+)\)\s*'
        r'(?:денари|ден)',
        re.IGNORECASE | re.DOTALL
    )

    # VAT total pattern
    VAT_TOTAL_PATTERN = re.compile(
        r'износ\s+на\s+ддв\s+изнесува\s+([\d\.,]+)',
        re.IGNORECASE
    )

    # Acceptance conditions
    ACCEPTANCE_PATTERNS = {
        'delivery': r'I\.1\s+.*прифаќаме.*испорака',
        'payment': r'I\.2\s+.*согласуваме.*плаќање',
        'validity': r'I\.3\s+.*понуда.*важи',
        'conditions': r'I\.4\s+.*прифаќаме.*услови',
    }

    def __init__(self):
        pass

    def is_financial_bid(self, text: str) -> bool:
        """Check if document is a financial bid"""
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in self.BID_HEADER_PATTERNS)

    def extract(self, text: str, document_name: str = "unknown") -> Optional[FinancialBid]:
        """
        Extract financial bid data from PDF text.

        Args:
            text: Full text content from PDF
            document_name: Source document identifier

        Returns:
            FinancialBid object with extracted data, or None if not a bid document
        """
        if not self.is_financial_bid(text):
            logger.debug(f"Document {document_name} is not a financial bid")
            return None

        bid = FinancialBid(
            tender_id="unknown",
            source_document=document_name
        )

        # Extract intro information
        self._extract_intro(text, bid)

        # Extract items from text (line-by-line parsing)
        self._extract_items_from_text(text, bid)

        # Extract totals
        self._extract_totals(text, bid)

        # Extract acceptance conditions
        self._extract_acceptance(text, bid)

        # Calculate confidence
        bid.extraction_confidence = self._calculate_confidence(bid)

        logger.info(
            f"Extracted financial bid: tender={bid.tender_id}, "
            f"items={len(bid.items)}, confidence={bid.extraction_confidence:.2f}"
        )

        return bid

    def _extract_intro(self, text: str, bid: FinancialBid) -> None:
        """Extract tender ID, procuring entity, and title from intro paragraph"""
        match = self.INTRO_PATTERN.search(text)
        if match:
            bid.tender_id = match.group(1).strip()
            bid.procuring_entity = match.group(2).strip()
            bid.tender_title = match.group(3).strip()

    def _extract_items_from_text(self, text: str, bid: FinancialBid) -> None:
        """
        Extract items by parsing the text line by line.

        The standard bid format has items in a table structure that
        gets extracted as text with patterns like:

        Pattern 1 (CPV split across lines):
        33652100
        -6
        Набавка на L01ЕA03,
        Nilotinib, 200mg, капсула;
        Капсула
        5.376,00
        1.210,00
        6.504.960,00
        325.248,00
        6.830.208,00

        Pattern 2 (All in sequence):
        45111300-1  Демонтажа на...  Парче  37,00  5.996,25  221.861,25
        """
        lines = text.split('\n')
        current_lot = None
        current_lot_num = 0
        item_num = 0

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Check for lot header
            lot_match = self.LOT_PATTERN.search(line)
            if lot_match:
                current_lot_num += 1
                current_lot = lot_match.group(1).strip()
                i += 1
                continue

            # Skip header lines and summary lines
            if self._is_header_line(line) or 'вкупно' in line.lower():
                i += 1
                continue

            # Look for CPV code at start of line (8 digits)
            cpv_match = re.match(r'^(\d{8})\s*$', line)
            if cpv_match:
                # CPV code might be split: "33652100" on one line, "-6" on next
                cpv_code = cpv_match.group(1)
                i += 1

                # Check if next line is the CPV suffix (-6)
                if i < len(lines):
                    next_line = lines[i].strip()
                    suffix_match = re.match(r'^-(\d)\s*$', next_line)
                    if suffix_match:
                        cpv_code = cpv_code + '-' + suffix_match.group(1)
                        i += 1

                # Now collect item data: name parts, then unit, then numbers
                item_parts = []
                numeric_values = []

                while i < len(lines):
                    next_line = lines[i].strip()

                    # Stop conditions
                    if not next_line:
                        i += 1
                        continue

                    # Check if we hit another CPV code
                    if re.match(r'^\d{8}\s*$', next_line):
                        break

                    # Check if we hit another lot
                    if self.LOT_PATTERN.search(next_line):
                        break

                    # Check if we hit the total line
                    if 'вкупно' in next_line.lower():
                        break

                    # Check if this is a numeric value (quantity/price)
                    if self._is_pure_number(next_line):
                        numeric_values.append(next_line)
                    else:
                        # It's part of the item description
                        item_parts.append(next_line)

                    i += 1

                # Build item name from non-numeric parts (excluding unit)
                # Typical structure: [name_part1, name_part2, ..., unit, qty, prices...]
                item_name = ""
                item_unit = None

                # Find where name ends and unit begins
                for idx, part in enumerate(item_parts):
                    if self._looks_like_unit(part):
                        item_unit = part
                        item_name = ' '.join(item_parts[:idx])
                        break
                else:
                    # No unit found in parts - name is all parts
                    item_name = ' '.join(item_parts)

                if item_name:
                    item_num += 1
                    item = self._create_item_from_values(
                        cpv_code=cpv_code,
                        name=item_name.strip(),
                        values=numeric_values,
                        lot_num=current_lot_num,
                        lot_desc=current_lot,
                        item_num=item_num
                    )
                    if item:
                        if item_unit:
                            item.unit = item_unit
                        bid.items.append(item)

                continue

            # Also try to match CPV code with suffix on same line (45111300-1)
            cpv_full_match = re.match(r'^(\d{8}-\d)\s*(.*)$', line)
            if cpv_full_match:
                cpv_code = cpv_full_match.group(1)
                remaining = cpv_full_match.group(2).strip()

                # Collect more parts
                item_parts = [remaining] if remaining else []
                numeric_values = []
                i += 1

                while i < len(lines):
                    next_line = lines[i].strip()

                    if not next_line:
                        i += 1
                        continue

                    if re.match(r'^\d{8}', next_line):
                        break
                    if self.LOT_PATTERN.search(next_line):
                        break
                    if 'вкупно' in next_line.lower():
                        break

                    if self._is_pure_number(next_line):
                        numeric_values.append(next_line)
                    else:
                        item_parts.append(next_line)

                    i += 1

                item_name = ""
                item_unit = None

                for idx, part in enumerate(item_parts):
                    if self._looks_like_unit(part):
                        item_unit = part
                        item_name = ' '.join(item_parts[:idx])
                        break
                else:
                    item_name = ' '.join(item_parts)

                if item_name:
                    item_num += 1
                    item = self._create_item_from_values(
                        cpv_code=cpv_code,
                        name=item_name.strip(),
                        values=numeric_values,
                        lot_num=current_lot_num,
                        lot_desc=current_lot,
                        item_num=item_num
                    )
                    if item:
                        if item_unit:
                            item.unit = item_unit
                        bid.items.append(item)

                continue

            i += 1

    def _is_pure_number(self, text: str) -> bool:
        """Check if text is primarily a number (for prices/quantities)"""
        # Remove common suffixes
        cleaned = text.replace('ден', '').replace('денари', '').strip()
        # Match number patterns like: 5.376,00 or 1.210,00 or 37,00
        if re.match(r'^[\d\.,\s]+$', cleaned):
            return True
        return False

    def _looks_like_unit(self, text: str) -> bool:
        """Check if text looks like a unit of measure"""
        text_lower = text.lower().strip()
        units = [
            'парче', 'комад', 'ком.', 'бр.', 'единица',
            'капсула', 'таблета', 'ампула',
            'кг', 'килограм', 'тон', 'грам', 'мг',
            'литар', 'мл', 'л.',
            'метар', 'м.', 'м2', 'м3', 'км',
            'работен час', 'час',
            'процент', '%',
            'единица за активност',
        ]
        return any(unit in text_lower for unit in units)

    def _is_numeric_row(self, line: str) -> bool:
        """Check if line contains mostly numeric values (prices/quantities)"""
        # Remove common text elements
        cleaned = re.sub(r'(ден|денари|парче|комад|кг|м|м2)', '', line, flags=re.IGNORECASE)
        cleaned = re.sub(r'[^\d,.\s]', '', cleaned).strip()

        if not cleaned:
            return False

        # Count digits vs other chars
        digits = sum(c.isdigit() for c in line)
        total = len(line.replace(' ', ''))

        return digits > 0 and digits / total > 0.4 if total > 0 else False

    def _is_header_line(self, line: str) -> bool:
        """Check if line is a table header"""
        line_lower = line.lower()
        header_words = ['шифра', 'назив', 'количина', 'цена', 'ддв', 'единица']
        matches = sum(1 for word in header_words if word in line_lower)
        return matches >= 2

    def _extract_numbers(self, line: str) -> List[str]:
        """Extract all number-like strings from a line"""
        # Pattern for Macedonian number format: 1.234.567,89 or 1234,89 or 1234.89
        numbers = re.findall(r'[\d]+(?:[.,][\d]+)*', line)
        return numbers

    def _parse_mkd_number(self, value: str) -> Optional[Decimal]:
        """
        Parse Macedonian/European number format to Decimal.

        Formats:
        - 1.234.567,89 (Macedonian: . as thousands, , as decimal)
        - 1234,89 (no thousands separator)
        - 1234.89 (US format)
        """
        if not value:
            return None

        try:
            value = value.strip()

            # Count separators
            dots = value.count('.')
            commas = value.count(',')

            if dots > 0 and commas > 0:
                # Macedonian format: 1.234.567,89
                # Remove dots (thousands), replace comma with dot (decimal)
                value = value.replace('.', '').replace(',', '.')
            elif commas == 1 and dots == 0:
                # Single comma is decimal: 1234,89
                value = value.replace(',', '.')
            # else: assume US format or no decimal

            return Decimal(value)

        except (InvalidOperation, ValueError):
            return None

    def _create_item_from_values(
        self,
        cpv_code: str,
        name: str,
        values: List[str],
        lot_num: int,
        lot_desc: Optional[str],
        item_num: int
    ) -> Optional[BidItem]:
        """
        Create BidItem from extracted values.

        Expected order: unit, quantity, unit_price, total_no_vat, vat, total_with_vat
        But the actual columns may vary, so we try to infer from values.
        """
        item = BidItem(
            cpv_code=cpv_code,
            name=name.strip(),
            lot_number=lot_num if lot_num > 0 else None,
            lot_description=lot_desc,
            item_number=item_num,
            raw_text=f"{cpv_code} | {name} | {' | '.join(values)}"
        )

        # Try to parse values - typically: quantity, unit_price, total_no_vat, vat, total_with_vat
        parsed_values = []
        for v in values:
            parsed = self._parse_mkd_number(v)
            if parsed is not None:
                parsed_values.append(parsed)

        # Assign values based on position and magnitude
        if len(parsed_values) >= 5:
            # Full row: qty, unit_price, total_no_vat, vat, total_with_vat
            item.quantity = float(parsed_values[0])
            item.unit_price_mkd = parsed_values[1]
            item.total_price_mkd = parsed_values[2]
            item.vat_amount_mkd = parsed_values[3]
            item.total_with_vat_mkd = parsed_values[4]
        elif len(parsed_values) >= 4:
            # Missing one value - try to infer
            item.quantity = float(parsed_values[0])
            item.unit_price_mkd = parsed_values[1]
            item.total_price_mkd = parsed_values[2]
            item.total_with_vat_mkd = parsed_values[3]
        elif len(parsed_values) >= 3:
            item.quantity = float(parsed_values[0])
            item.unit_price_mkd = parsed_values[1]
            item.total_price_mkd = parsed_values[2]
        elif len(parsed_values) >= 2:
            item.quantity = float(parsed_values[0])
            item.total_price_mkd = parsed_values[1]
        elif len(parsed_values) >= 1:
            # Single value - probably total
            item.total_price_mkd = parsed_values[0]

        # Try to extract unit from name
        item.unit = self._extract_unit_from_name(name)

        return item

    def _extract_unit_from_name(self, name: str) -> Optional[str]:
        """Extract unit of measure from item name"""
        name_lower = name.lower()

        unit_patterns = [
            (r'\b(парче|парчиња)\b', 'Парче'),
            (r'\b(комад|комади)\b', 'Комад'),
            (r'\b(кг|килограм)\b', 'КГ'),
            (r'\b(тон|тони)\b', 'Тон'),
            (r'\b(литар|литри)\b', 'Литар'),
            (r'\b(метар|метри)\b', 'Метар'),
            (r'\b(м2|квадратен)\b', 'М2'),
            (r'\b(м3|кубен)\b', 'М3'),
            (r'\b(капсула|капсули)\b', 'Капсула'),
            (r'\b(таблета|таблети)\b', 'Таблета'),
            (r'\b(ампула|ампули)\b', 'Ампула'),
            (r'\b(работен час)\b', 'Работен час'),
            (r'\b(единица)\b', 'Единица'),
            (r'\b(процент|%)\b', 'Процент'),
        ]

        for pattern, unit in unit_patterns:
            if re.search(pattern, name_lower):
                return unit

        return None

    def _extract_totals(self, text: str, bid: FinancialBid) -> None:
        """Extract total amounts from the summary section"""
        # Main total
        match = self.TOTAL_PATTERN.search(text)
        if match:
            bid.total_amount_mkd = self._parse_mkd_number(match.group(1))

        # VAT total
        vat_match = self.VAT_TOTAL_PATTERN.search(text)
        if vat_match:
            bid.total_vat_mkd = self._parse_mkd_number(vat_match.group(1))

    def _extract_acceptance(self, text: str, bid: FinancialBid) -> None:
        """Extract bidder acceptance statements"""
        for key, pattern in self.ACCEPTANCE_PATTERNS.items():
            bid.bidder_acceptance[key] = bool(re.search(pattern, text, re.IGNORECASE))

    def _calculate_confidence(self, bid: FinancialBid) -> float:
        """Calculate extraction confidence based on extracted data"""
        score = 0.0

        # Has items
        if bid.items:
            score += 0.4
            # More items = higher confidence
            score += min(0.2, len(bid.items) * 0.02)

        # Has tender ID
        if bid.tender_id and bid.tender_id != "unknown":
            score += 0.1

        # Has procuring entity
        if bid.procuring_entity:
            score += 0.1

        # Has totals
        if bid.total_amount_mkd:
            score += 0.1

        # Items have prices
        items_with_prices = sum(1 for item in bid.items if item.total_price_mkd)
        if bid.items:
            price_ratio = items_with_prices / len(bid.items)
            score += price_ratio * 0.1

        return min(1.0, score)

    def to_product_items(self, bid: FinancialBid) -> List[Dict]:
        """
        Convert FinancialBid to product_items table format.

        Returns list of dicts ready for database insertion.
        """
        items = []

        for item in bid.items:
            items.append({
                'tender_id': bid.tender_id,
                'item_number': item.item_number,
                'lot_number': item.lot_number,
                'name': item.name,
                'quantity': item.quantity,
                'unit': item.unit,
                'unit_price': float(item.unit_price_mkd) if item.unit_price_mkd else None,
                'total_price': float(item.total_price_mkd) if item.total_price_mkd else None,
                'cpv_code': item.cpv_code,
                'specifications': {
                    'lot_description': item.lot_description,
                    'vat_amount': float(item.vat_amount_mkd) if item.vat_amount_mkd else None,
                    'total_with_vat': float(item.total_with_vat_mkd) if item.total_with_vat_mkd else None,
                },
                'extraction_confidence': bid.extraction_confidence,
                'raw_text': item.raw_text,
            })

        return items


# Convenience function
def extract_financial_bid(text: str, document_name: str = "unknown") -> Optional[FinancialBid]:
    """
    Extract financial bid from document text.

    Usage:
        bid = extract_financial_bid(pdf_text, "bid_document.pdf")
        if bid:
            for item in bid.items:
                print(f"{item.name}: {item.total_price_mkd} MKD")
    """
    extractor = FinancialBidExtractor()
    return extractor.extract(text, document_name)


def extract_bid_items_for_db(text: str, document_name: str = "unknown") -> List[Dict]:
    """
    Extract items from financial bid in database-ready format.

    Usage:
        items = extract_bid_items_for_db(pdf_text)
        for item in items:
            db.insert('product_items', item)
    """
    bid = extract_financial_bid(text, document_name)
    if bid:
        extractor = FinancialBidExtractor()
        return extractor.to_product_items(bid)
    return []
