"""
Item Bid Extractor

Extracts per-item bidding data from tender documents to populate the item_bids table.
This is CRITICAL for answering questions like:
- "Who bid what price for surgical drapes?"
- "What did Company X offer for item Y?"
- "Which bidder had the lowest price per item?"

Data Sources:
1. Bid evaluation documents (comparison tables showing all bids side-by-side)
2. Individual bid submission documents (single bidder's offer)
3. Award decision documents (final prices and winners)
4. ePazar data (e-auction bids)

Key Challenge: Link items → bidders → prices across different document formats
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
import asyncpg
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ItemBid:
    """Represents a single bid for a specific item"""
    tender_id: str
    item_id: int
    bidder_id: str
    company_name: str
    company_tax_id: Optional[str] = None
    lot_id: Optional[str] = None
    quantity_offered: Optional[Decimal] = None
    unit_price_mkd: Optional[Decimal] = None
    total_price_mkd: Optional[Decimal] = None
    unit_price_eur: Optional[Decimal] = None
    delivery_days: Optional[int] = None
    warranty_months: Optional[int] = None
    brand_model: Optional[str] = None
    country_of_origin: Optional[str] = None
    is_compliant: bool = True
    is_winner: bool = False
    rank: Optional[int] = None
    evaluation_score: Optional[Decimal] = None
    disqualification_reason: Optional[str] = None
    extraction_source: str = 'document'
    extraction_confidence: Optional[float] = None
    source_document_id: Optional[str] = None
    source_table_id: Optional[str] = None
    source_page_number: Optional[int] = None
    raw_data: Optional[Dict] = None


class ItemBidExtractor:
    """Extract item-level bids from documents"""

    # Patterns to identify bid comparison tables
    BID_TABLE_PATTERNS = [
        r'споредб.*понуд',  # Macedonian: bid comparison
        r'евалуациј',  # Macedonian: evaluation
        r'рангирање',  # Macedonian: ranking
        r'понудувач.*цена',  # Macedonian: bidder...price
        r'bid.*comparison',
        r'evaluation.*matrix',
        r'price.*comparison',
        r'offer.*comparison',
    ]

    # Column name patterns for different data types
    ITEM_NAME_PATTERNS = [
        r'артик[ау]л',  # Macedonian: article
        r'производ',  # Macedonian: product
        r'ставка',  # Macedonian: item
        r'опис',  # Macedonian: description
        r'item',
        r'product',
        r'description',
        r'назив',  # Macedonian: name
    ]

    COMPANY_PATTERNS = [
        r'понудувач',  # Macedonian: bidder
        r'компанија',  # Macedonian: company
        r'фирма',  # Macedonian: firm
        r'bidder',
        r'company',
        r'supplier',
    ]

    PRICE_PATTERNS = [
        r'цена.*единиц',  # Macedonian: unit price
        r'единичн.*цена',  # Macedonian: unit price
        r'вкупн.*цена',  # Macedonian: total price
        r'unit.*price',
        r'price.*unit',
        r'total.*price',
        r'amount',
        r'mkd',
        r'eur',
    ]

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def extract_from_table(
        self,
        table_id: str,
        tender_id: str,
        table_data: Dict,
        document_id: Optional[str] = None
    ) -> List[ItemBid]:
        """
        Extract item bids from a structured table.

        Args:
            table_id: UUID of the extracted table
            tender_id: Tender ID
            table_data: Normalized table data (rows and columns)
            document_id: Source document UUID

        Returns:
            List of extracted ItemBid objects
        """
        if not table_data or 'rows' not in table_data:
            logger.warning(f"Table {table_id} has no row data")
            return []

        # Detect table type
        table_type = self._detect_table_type(table_data)
        logger.info(f"Detected table type: {table_type}")

        if table_type == 'bid_comparison':
            return await self._extract_from_comparison_table(
                table_id, tender_id, table_data, document_id
            )
        elif table_type == 'single_bid':
            return await self._extract_from_single_bid_table(
                table_id, tender_id, table_data, document_id
            )
        elif table_type == 'award_decision':
            return await self._extract_from_award_table(
                table_id, tender_id, table_data, document_id
            )
        else:
            logger.warning(f"Unknown table type for table {table_id}")
            return []

    def _detect_table_type(self, table_data: Dict) -> str:
        """
        Detect the type of table (bid comparison, single bid, award decision).

        Heuristics:
        - Bid comparison: Multiple company columns with prices
        - Single bid: One company, multiple items with prices
        - Award decision: Winner column, contract amounts
        """
        headers = table_data.get('headers', [])
        if not headers:
            return 'unknown'

        headers_str = ' '.join([str(h).lower() for h in headers])

        # Count company/bidder columns
        company_cols = sum(1 for h in headers if self._matches_pattern(str(h), self.COMPANY_PATTERNS))

        # Count price columns
        price_cols = sum(1 for h in headers if self._matches_pattern(str(h), self.PRICE_PATTERNS))

        # Check for winner indicators
        has_winner = any(re.search(r'победник|winner|award', str(h), re.I) for h in headers)

        if company_cols >= 2 and price_cols >= 2:
            return 'bid_comparison'
        elif has_winner:
            return 'award_decision'
        elif company_cols == 1 and price_cols >= 1:
            return 'single_bid'
        else:
            return 'unknown'

    async def _extract_from_comparison_table(
        self,
        table_id: str,
        tender_id: str,
        table_data: Dict,
        document_id: Optional[str]
    ) -> List[ItemBid]:
        """
        Extract from bid comparison table.

        Typical structure:
        | Item | Qty | Company A Price | Company B Price | Company C Price | Winner |
        """
        bids = []
        headers = table_data.get('headers', [])
        rows = table_data.get('rows', [])

        # Map column indices to data types
        item_col = self._find_column(headers, self.ITEM_NAME_PATTERNS)
        qty_col = self._find_column(headers, [r'количин', r'qty', r'quantity'])

        # Find all company-price column pairs
        company_price_cols = self._find_company_price_columns(headers)

        if item_col is None or not company_price_cols:
            logger.warning("Could not identify item or price columns")
            return []

        # Get or create bidders
        bidder_map = await self._get_or_create_bidders(
            tender_id,
            [company for company, _ in company_price_cols]
        )

        # Process each row
        for row_idx, row in enumerate(rows):
            if row_idx == 0:  # Skip header row if present
                continue

            item_name = self._get_cell_value(row, item_col)
            if not item_name or len(item_name) < 3:
                continue

            quantity = self._get_cell_value(row, qty_col) if qty_col is not None else None

            # Get or create product item
            item_id = await self._get_or_create_product_item(
                tender_id, item_name, quantity, row_idx
            )

            if not item_id:
                continue

            # Extract bid for each company
            for company_name, price_col in company_price_cols:
                price_str = self._get_cell_value(row, price_col)
                price = self._parse_price(price_str)

                if price is None or price <= 0:
                    continue  # Skip empty or invalid prices

                bidder_id = bidder_map.get(company_name)
                if not bidder_id:
                    continue

                bid = ItemBid(
                    tender_id=tender_id,
                    item_id=item_id,
                    bidder_id=bidder_id,
                    company_name=company_name,
                    quantity_offered=Decimal(str(quantity)) if quantity else None,
                    unit_price_mkd=price,
                    total_price_mkd=price * Decimal(str(quantity)) if quantity and price else price,
                    extraction_source='table',
                    extraction_confidence=0.85,
                    source_document_id=document_id,
                    source_table_id=table_id,
                    raw_data={'row_index': row_idx, 'row_data': row}
                )
                bids.append(bid)

        return bids

    async def _extract_from_single_bid_table(
        self,
        table_id: str,
        tender_id: str,
        table_data: Dict,
        document_id: Optional[str]
    ) -> List[ItemBid]:
        """
        Extract from single bidder's offer document.

        Typical structure:
        | Item | Qty | Unit Price | Total Price | Brand |
        """
        # Implementation similar to comparison table but for single bidder
        # Would need to identify the bidder from document metadata
        logger.info("Single bid table extraction not yet implemented")
        return []

    async def _extract_from_award_table(
        self,
        table_id: str,
        tender_id: str,
        table_data: Dict,
        document_id: Optional[str]
    ) -> List[ItemBid]:
        """
        Extract from award decision table.

        Typical structure:
        | Item | Quantity | Winner | Contract Price |
        """
        logger.info("Award table extraction not yet implemented")
        return []

    def _find_column(self, headers: List, patterns: List[str]) -> Optional[int]:
        """Find the first column matching any of the patterns"""
        for idx, header in enumerate(headers):
            if self._matches_pattern(str(header), patterns):
                return idx
        return None

    def _find_company_price_columns(self, headers: List) -> List[Tuple[str, int]]:
        """
        Find company-price column pairs.

        Returns: List of (company_name, price_column_index) tuples
        """
        pairs = []

        # Strategy 1: Look for adjacent company + price columns
        for idx, header in enumerate(headers):
            header_str = str(header).lower()
            if self._matches_pattern(header, self.COMPANY_PATTERNS):
                # Look for price in next few columns
                for offset in range(1, min(4, len(headers) - idx)):
                    next_header = str(headers[idx + offset])
                    if self._matches_pattern(next_header, self.PRICE_PATTERNS):
                        company_name = self._clean_company_name(header)
                        pairs.append((company_name, idx + offset))
                        break

        # Strategy 2: Look for columns with company names that also contain prices
        if not pairs:
            for idx, header in enumerate(headers):
                header_str = str(header)
                # Check if header contains both company indicator and price
                if (self._matches_pattern(header_str, self.COMPANY_PATTERNS) and
                    self._matches_pattern(header_str, self.PRICE_PATTERNS)):
                    company_name = self._clean_company_name(header)
                    pairs.append((company_name, idx))

        return pairs

    def _matches_pattern(self, text: str, patterns: List[str]) -> bool:
        """Check if text matches any of the regex patterns"""
        text_lower = text.lower()
        return any(re.search(pattern, text_lower, re.I) for pattern in patterns)

    def _clean_company_name(self, header: str) -> str:
        """Extract company name from column header"""
        # Remove common prefixes/suffixes
        name = str(header)
        name = re.sub(r'(понудувач|bidder|company|price|цена)[:.\s-]*', '', name, flags=re.I)
        name = name.strip()
        return name if name else str(header)

    def _get_cell_value(self, row: List, col_idx: int) -> Optional[str]:
        """Safely get cell value from row"""
        if col_idx is None or col_idx >= len(row):
            return None
        return str(row[col_idx]).strip() if row[col_idx] else None

    def _parse_price(self, price_str: Optional[str]) -> Optional[Decimal]:
        """Parse price string to Decimal"""
        if not price_str:
            return None

        # Remove currency symbols, spaces, commas
        price_str = re.sub(r'[^\d.,\-]', '', price_str)
        price_str = price_str.replace(',', '.')

        try:
            return Decimal(price_str)
        except:
            return None

    async def _get_or_create_bidders(
        self,
        tender_id: str,
        company_names: List[str]
    ) -> Dict[str, str]:
        """
        Get or create bidder records and return mapping of company_name -> bidder_id
        """
        bidder_map = {}

        async with self.db_pool.acquire() as conn:
            for company_name in company_names:
                if not company_name:
                    continue

                # Try to find existing bidder
                bidder = await conn.fetchrow("""
                    SELECT bidder_id FROM tender_bidders
                    WHERE tender_id = $1 AND company_name = $2
                    LIMIT 1
                """, tender_id, company_name)

                if bidder:
                    bidder_map[company_name] = str(bidder['bidder_id'])
                else:
                    # Create new bidder
                    new_bidder = await conn.fetchrow("""
                        INSERT INTO tender_bidders (tender_id, company_name)
                        VALUES ($1, $2)
                        RETURNING bidder_id
                    """, tender_id, company_name)
                    bidder_map[company_name] = str(new_bidder['bidder_id'])

        return bidder_map

    async def _get_or_create_product_item(
        self,
        tender_id: str,
        item_name: str,
        quantity: Optional[float],
        item_number: int
    ) -> Optional[int]:
        """
        Get or create product item and return item_id
        """
        async with self.db_pool.acquire() as conn:
            # Try to find existing item by name match
            item = await conn.fetchrow("""
                SELECT id FROM product_items
                WHERE tender_id = $1 AND LOWER(name) = LOWER($2)
                LIMIT 1
            """, tender_id, item_name)

            if item:
                return item['id']

            # Create new item
            new_item = await conn.fetchrow("""
                INSERT INTO product_items (tender_id, name, quantity, item_number)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, tender_id, item_name, quantity, item_number)

            return new_item['id'] if new_item else None

    async def save_item_bids(self, bids: List[ItemBid]) -> int:
        """
        Save extracted item bids to database.

        Returns: Number of bids saved
        """
        if not bids:
            return 0

        saved_count = 0

        async with self.db_pool.acquire() as conn:
            for bid in bids:
                try:
                    await conn.execute("""
                        INSERT INTO item_bids (
                            tender_id, lot_id, item_id, bidder_id,
                            company_name, company_tax_id,
                            quantity_offered, unit_price_mkd, total_price_mkd, unit_price_eur,
                            delivery_days, warranty_months, brand_model, country_of_origin,
                            is_compliant, is_winner, rank, evaluation_score, disqualification_reason,
                            extraction_source, extraction_confidence,
                            source_document_id, source_table_id, source_page_number,
                            raw_data
                        ) VALUES (
                            $1, $2, $3, $4,
                            $5, $6,
                            $7, $8, $9, $10,
                            $11, $12, $13, $14,
                            $15, $16, $17, $18, $19,
                            $20, $21,
                            $22, $23, $24,
                            $25
                        )
                        ON CONFLICT (item_id, bidder_id)
                        DO UPDATE SET
                            quantity_offered = EXCLUDED.quantity_offered,
                            unit_price_mkd = EXCLUDED.unit_price_mkd,
                            total_price_mkd = EXCLUDED.total_price_mkd,
                            unit_price_eur = EXCLUDED.unit_price_eur,
                            brand_model = EXCLUDED.brand_model,
                            extraction_confidence = EXCLUDED.extraction_confidence,
                            updated_at = NOW()
                    """,
                        bid.tender_id, bid.lot_id, bid.item_id, bid.bidder_id,
                        bid.company_name, bid.company_tax_id,
                        bid.quantity_offered, bid.unit_price_mkd, bid.total_price_mkd, bid.unit_price_eur,
                        bid.delivery_days, bid.warranty_months, bid.brand_model, bid.country_of_origin,
                        bid.is_compliant, bid.is_winner, bid.rank, bid.evaluation_score, bid.disqualification_reason,
                        bid.extraction_source, bid.extraction_confidence,
                        bid.source_document_id, bid.source_table_id, bid.source_page_number,
                        bid.raw_data
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving item bid: {e}")
                    continue

        logger.info(f"Saved {saved_count}/{len(bids)} item bids")
        return saved_count


async def extract_item_bids_from_tender(
    db_pool: asyncpg.Pool,
    tender_id: str
) -> int:
    """
    Extract item bids for a tender from all available tables.

    Args:
        db_pool: Database connection pool
        tender_id: Tender ID to process

    Returns:
        Total number of bids extracted
    """
    extractor = ItemBidExtractor(db_pool)

    # Get all extracted tables for this tender
    async with db_pool.acquire() as conn:
        tables = await conn.fetch("""
            SELECT table_id, normalized_data, doc_id
            FROM extracted_tables
            WHERE tender_id = $1
            AND table_type IN ('bid_comparison', 'evaluation', 'financial')
            ORDER BY created_at DESC
        """, tender_id)

    total_bids = 0

    for table in tables:
        table_id = str(table['table_id'])
        table_data = table['normalized_data']
        doc_id = str(table['doc_id']) if table['doc_id'] else None

        logger.info(f"Extracting bids from table {table_id}")

        bids = await extractor.extract_from_table(
            table_id, tender_id, table_data, doc_id
        )

        saved = await extractor.save_item_bids(bids)
        total_bids += saved

    logger.info(f"Extracted {total_bids} total item bids for tender {tender_id}")
    return total_bids
