#!/usr/bin/env python3
"""
Extract bidder information from raw_data_json and populate tender_bidders table.

This script:
1. Parses raw_json.full_text to extract bidder names and bid amounts from contract award notifications
2. Extracts bidder data from OCDS records (if available)
3. Populates the tender_bidders table with company name, bid amount, rank, and is_winner

Usage:
    python3 extract_bidders.py --limit 1000        # Process 1000 tenders
    python3 extract_bidders.py --all               # Process all tenders
    python3 extract_bidders.py --tender-id 12345/2025  # Process specific tender
"""

import argparse
import asyncio
import json
import logging
import os
import re
from decimal import Decimal
from typing import List, Dict, Any, Optional

import asyncpg
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


class BidderExtractor:
    """Extract bidder information from various data sources."""

    def __init__(self):
        self.stats = {
            'tenders_processed': 0,
            'bidders_extracted': 0,
            'bidders_inserted': 0,
            'errors': 0,
        }

    def extract_from_full_text(self, full_text: str, tender_id: str) -> List[Dict[str, Any]]:
        """
        Extract bidders from raw_json.full_text (contract award notification HTML).

        Pattern in HTML:
        IV.1.3) Број на добиени понуди: 3
        Назив на понудувачи
        Друштво за производство, промет, трговија и услуги ТРИНИКС ДОО Скопје
        Друштво за услуги производство и трговија ПЕЛИКАН КОРПОРАТИОН ДООЕЛ Струга
        ...
        Највисока добиена понуда: 23.440,00
        Најниска добиена понуда: 1.200,00
        """
        if not full_text:
            return []

        bidders = []

        # Pattern 1: Extract bidders from "Назив на понудувачи" section
        # This section lists all companies that submitted bids
        bidder_section_pattern = r'Назив на понудувачи\s+(.*?)\s+Највисока добиена понуда'
        match = re.search(bidder_section_pattern, full_text, re.DOTALL)

        if match:
            bidder_text = match.group(1)

            # Split company names more intelligently
            # Look for patterns like "Друштво...ДОО" or "Трговско...ДООЕЛ"
            company_pattern = r'((?:Друштво|Трговско|Акционерско)[^\n]+?(?:ДОО|ДООЕЛ|АД|Скопје|Битола|Струга|Куманово|Гостивар|Охрид|Велес|Штип|Кочани))'
            company_names = re.findall(company_pattern, bidder_text)

            # Fallback: split by newlines if pattern matching didn't work
            if not company_names:
                company_lines = [line.strip() for line in bidder_text.split('\n') if line.strip()]

                # Filter out lines that are clearly not company names
                for line in company_lines:
                    # Skip very short lines or lines with just numbers
                    if len(line) < 10 or line.replace(',', '').replace('.', '').replace(' ', '').isdigit():
                        continue
                    # Company names typically contain "Друштво", "ДОО", "ДООЕЛ", or similar
                    if any(keyword in line for keyword in ['Друштво', 'ДОО', 'ДООЕЛ', 'АД', 'АКЦИОНЕРСКО', 'Трговско']):
                        company_names.append(line)


            for idx, company_name in enumerate(company_names, start=1):
                bidders.append({
                    'company_name': company_name.strip(),
                    'bid_amount_mkd': None,
                    'is_winner': False,
                    'rank': idx,
                    'disqualified': False,
                })

        # Pattern 2: Extract highest and lowest bid amounts
        highest_bid_pattern = r'Највисока добиена понуда:\s*([\d.,]+)'
        lowest_bid_pattern = r'Најниска добиена понуда:\s*([\d.,]+)'

        highest_match = re.search(highest_bid_pattern, full_text)
        lowest_match = re.search(lowest_bid_pattern, full_text)

        highest_bid = self._parse_currency(highest_match.group(1)) if highest_match else None
        lowest_bid = self._parse_currency(lowest_match.group(1)) if lowest_match else None

        # Pattern 3: Extract winner from "Име на носителот на набавката" section
        winner_pattern = r'Име на носителот на набавката:\s*(.*?)(?:\n|Вистински сопственици)'
        winner_match = re.search(winner_pattern, full_text, re.DOTALL)

        winner_name = None
        if winner_match:
            winner_name = winner_match.group(1).strip()

        # Pattern 4: Extract contract value for winner
        contract_value_pattern = r'Вредност на склучениот договор без вклучен ДДВ\s*([\d.,]+)'
        contract_match = re.search(contract_value_pattern, full_text)

        contract_value = self._parse_currency(contract_match.group(1)) if contract_match else None

        # Pattern 5: Extract lot-level awards from "ИЗВЕСТУВАЊА ЗА СКЛУЧЕН ДОГОВОР" table
        # This table shows multiple winners for different lots
        lot_awards = self._extract_lot_awards(full_text)

        # Merge lot awards into bidders list
        for award in lot_awards:
            # Check if bidder already exists
            existing = None
            for bidder in bidders:
                if award['company_name'] in bidder['company_name'] or bidder['company_name'] in award['company_name']:
                    existing = bidder
                    break

            if existing:
                # Update existing bidder with winner status and amount
                existing['is_winner'] = True
                if award.get('bid_amount_mkd'):
                    existing['bid_amount_mkd'] = award['bid_amount_mkd']
            else:
                # Add new bidder
                bidders.append({
                    'company_name': award['company_name'],
                    'bid_amount_mkd': award.get('bid_amount_mkd'),
                    'is_winner': True,
                    'rank': len(bidders) + 1,
                    'disqualified': False,
                })

        # Mark winner from main section
        if winner_name:
            # Try to find winner in bidders list and mark them
            winner_found = False
            for bidder in bidders:
                if winner_name in bidder['company_name'] or bidder['company_name'] in winner_name:
                    bidder['is_winner'] = True
                    if contract_value and not bidder['bid_amount_mkd']:
                        bidder['bid_amount_mkd'] = contract_value
                    winner_found = True
                    break

            # If winner not found in list, add them
            if not winner_found:
                bidders.append({
                    'company_name': winner_name,
                    'bid_amount_mkd': contract_value,
                    'is_winner': True,
                    'rank': 1,
                    'disqualified': False,
                })

        # Assign bid amounts based on rank if we have highest/lowest
        if highest_bid and lowest_bid and len(bidders) > 1:
            # Assign highest bid to last ranked bidder (highest price)
            # Assign lowest bid to winner (lowest price in procurement)
            for bidder in bidders:
                if bidder['is_winner'] and not bidder['bid_amount_mkd']:
                    bidder['bid_amount_mkd'] = lowest_bid
                elif not bidder['is_winner'] and not bidder['bid_amount_mkd']:
                    # Distribute amounts between highest and lowest
                    if bidder['rank'] == len(bidders):
                        bidder['bid_amount_mkd'] = highest_bid

        logger.info(f"Extracted {len(bidders)} bidder(s) from full_text for {tender_id}")
        return bidders

    def _extract_lot_awards(self, full_text: str) -> List[Dict[str, Any]]:
        """
        Extract lot-level award data from contract notification table.

        Pattern:
        ДЕЛ V: ИЗВЕСТУВАЊА ЗА СКЛУЧЕН ДОГОВОР
        ...
        1 1, 3, 4, 7, 8 ... ПЕЛИКАН КОРПОРАТИОН ДООЕЛ Струга ... 598.212,02
        2 2 ... АСТИГ ТРЕЈД ДООЕЛ ... 291.963,86
        """
        lot_awards = []

        # Find the awards table section
        awards_section_pattern = r'ДЕЛ V: ИЗВЕСТУВАЊА ЗА СКЛУЧЕН ДОГОВОР.*?Реден број.*?Вкупно:'
        awards_match = re.search(awards_section_pattern, full_text, re.DOTALL)

        if not awards_match:
            return lot_awards

        awards_text = awards_match.group(0)

        # Extract table rows - each row has: number, lots, org, winner, description, type, amount
        # Pattern: number followed by lot numbers, followed by org name, winner name, amount
        row_pattern = r'(\d+)\s+[\d,\s]+\s+[^\n]*?\s+(Друштво[^\n]+?(?:ДОО|ДООЕЛ|АД)[^\n]+?)\s+[^\n]*?\s+([\d.,]+)'

        for match in re.finditer(row_pattern, awards_text):
            award_num = match.group(1)
            company_name = match.group(2).strip()
            amount_str = match.group(3).strip()

            amount = self._parse_currency(amount_str)

            if company_name and amount:
                lot_awards.append({
                    'company_name': company_name,
                    'bid_amount_mkd': amount,
                    'is_winner': True,
                })

        return lot_awards

    def _parse_currency(self, value_str: str) -> Optional[float]:
        """Parse European currency format to float."""
        if not value_str:
            return None

        try:
            # Remove spaces and handle European format (1.234.567,89)
            clean = value_str.replace(' ', '').replace('\xa0', '')

            # European format: dots for thousands, comma for decimal
            if '.' in clean and ',' in clean:
                clean = clean.replace('.', '').replace(',', '.')
            elif ',' in clean:
                clean = clean.replace(',', '.')

            return float(clean)
        except (ValueError, AttributeError):
            return None

    def extract_from_ocds(self, raw_data_json: dict) -> List[Dict[str, Any]]:
        """
        Extract bidders from OCDS data (OpenTender imports).

        OCDS structure:
        {
            "bids": {
                "details": [
                    {
                        "tenderers": [{"name": "Company ABC"}],
                        "value": {"amount": 150000.00}
                    }
                ]
            },
            "awards": [
                {
                    "suppliers": [{"name": "Winner Company"}],
                    "value": {"amount": 100000.00}
                }
            ]
        }
        """
        if not raw_data_json or not isinstance(raw_data_json, dict):
            return []

        bidders = []

        # Extract from bids.details
        bids_data = raw_data_json.get('bids', {}).get('details', [])

        for idx, bid in enumerate(bids_data, start=1):
            tenderers = bid.get('tenderers', [])
            bid_value = bid.get('value', {}).get('amount')

            for tenderer in tenderers:
                company_name = tenderer.get('name')
                if company_name:
                    bidders.append({
                        'company_name': company_name,
                        'bid_amount_mkd': bid_value,
                        'is_winner': False,
                        'rank': idx,
                        'disqualified': False,
                    })

        # Extract winners from awards
        awards_data = raw_data_json.get('awards', [])

        for award in awards_data:
            suppliers = award.get('suppliers', [])
            award_value = award.get('value', {}).get('amount')

            for supplier in suppliers:
                winner_name = supplier.get('name')
                if not winner_name:
                    continue

                # Find bidder in list and mark as winner
                found = False
                for bidder in bidders:
                    if bidder['company_name'] == winner_name:
                        bidder['is_winner'] = True
                        if award_value and not bidder['bid_amount_mkd']:
                            bidder['bid_amount_mkd'] = award_value
                        found = True
                        break

                # If winner not in bids list, add them
                if not found:
                    bidders.append({
                        'company_name': winner_name,
                        'bid_amount_mkd': award_value,
                        'is_winner': True,
                        'rank': 1,
                        'disqualified': False,
                    })

        return bidders

    async def process_tender(self, conn, tender_id: str, raw_json: dict) -> int:
        """
        Process a single tender and extract bidders.

        Returns number of bidders inserted.
        """
        # Try extracting from different sources
        bidders = []

        # Source 1: Extract from full_text (contract award notifications)
        if raw_json and isinstance(raw_json, dict):
            full_text = raw_json.get('full_text', '')

            if full_text and 'Назив на понудувачи' in full_text:
                bidders.extend(self.extract_from_full_text(full_text, tender_id))

            # Source 2: Extract from OCDS data (for OpenTender records)
            if 'bids' in raw_json or 'awards' in raw_json:
                ocds_bidders = self.extract_from_ocds(raw_json)
                # Merge with existing bidders (avoid duplicates)
                for ocds_bidder in ocds_bidders:
                    if not any(b['company_name'] == ocds_bidder['company_name'] for b in bidders):
                        bidders.append(ocds_bidder)

        if not bidders:
            return 0

        # Insert bidders into database
        inserted = 0
        for bidder in bidders:
            try:
                await conn.execute('''
                    INSERT INTO tender_bidders (
                        tender_id, company_name, bid_amount_mkd,
                        is_winner, rank, disqualified
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (tender_id, company_name) DO UPDATE SET
                        bid_amount_mkd = COALESCE(EXCLUDED.bid_amount_mkd, tender_bidders.bid_amount_mkd),
                        is_winner = COALESCE(EXCLUDED.is_winner, tender_bidders.is_winner),
                        rank = COALESCE(EXCLUDED.rank, tender_bidders.rank)
                ''',
                    tender_id,
                    bidder['company_name'],
                    bidder.get('bid_amount_mkd'),
                    bidder.get('is_winner', False),
                    bidder.get('rank'),
                    bidder.get('disqualified', False)
                )
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting bidder for {tender_id}: {e}")
                self.stats['errors'] += 1

        return inserted

    async def run(self, limit: Optional[int] = None, tender_id: Optional[str] = None):
        """Main extraction process."""
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=5,
            command_timeout=120
        )

        try:
            async with pool.acquire() as conn:
                # Build query based on parameters
                # Check both raw_json (has full_text) and raw_data_json (from scraper pipeline)
                if tender_id:
                    query = """
                        SELECT tender_id,
                               COALESCE(raw_json, raw_data_json) as raw_json
                        FROM tenders
                        WHERE tender_id = $1
                    """
                    params = [tender_id]
                else:
                    # Process tenders with bidder data that don't have bidders extracted yet
                    query = """
                        SELECT t.tender_id,
                               COALESCE(t.raw_json, t.raw_data_json) as raw_json
                        FROM tenders t
                        LEFT JOIN tender_bidders tb ON t.tender_id = tb.tender_id
                        WHERE tb.bidder_id IS NULL
                          AND (
                            (t.raw_json::text LIKE '%Назив на понудувачи%')
                            OR (t.raw_data_json::text LIKE '%Назив на понудувачи%')
                            OR (t.raw_json::jsonb ? 'bids')
                            OR (t.raw_json::jsonb ? 'awards')
                          )
                        ORDER BY t.created_at DESC
                    """
                    if limit:
                        query += f" LIMIT {limit}"
                    params = []

                rows = await conn.fetch(query, *params)
                logger.info(f"Processing {len(rows)} tenders...")

                for row in rows:
                    tid = row['tender_id']
                    raw_json = row['raw_json']

                    # Parse JSON if it's a string
                    if isinstance(raw_json, str):
                        try:
                            raw_json = json.loads(raw_json)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse JSON for {tid}")
                            raw_json = None

                    try:
                        inserted = await self.process_tender(conn, tid, raw_json)

                        self.stats['tenders_processed'] += 1
                        self.stats['bidders_inserted'] += inserted

                        if inserted > 0:
                            logger.info(f"✓ {tid}: Inserted {inserted} bidder(s)")

                        # Progress update every 100 tenders
                        if self.stats['tenders_processed'] % 100 == 0:
                            logger.warning(f"Progress: {self.stats['tenders_processed']} tenders, "
                                         f"{self.stats['bidders_inserted']} bidders inserted")

                    except Exception as e:
                        logger.error(f"Error processing tender {tid}: {e}")
                        self.stats['errors'] += 1

        finally:
            await pool.close()

        # Print final statistics
        logger.warning("=" * 60)
        logger.warning("EXTRACTION COMPLETE")
        logger.warning("=" * 60)
        logger.warning(f"Tenders processed: {self.stats['tenders_processed']}")
        logger.warning(f"Bidders inserted: {self.stats['bidders_inserted']}")
        logger.warning(f"Errors: {self.stats['errors']}")
        logger.warning(f"Average bidders per tender: {self.stats['bidders_inserted'] / max(self.stats['tenders_processed'], 1):.2f}")


async def main():
    parser = argparse.ArgumentParser(description='Extract bidder data from tenders')
    parser.add_argument('--limit', type=int, help='Number of tenders to process')
    parser.add_argument('--all', action='store_true', help='Process all tenders')
    parser.add_argument('--tender-id', type=str, help='Process specific tender by ID')

    args = parser.parse_args()

    extractor = BidderExtractor()

    if args.tender_id:
        await extractor.run(tender_id=args.tender_id)
    elif args.all:
        await extractor.run(limit=None)
    else:
        await extractor.run(limit=args.limit or 1000)


if __name__ == '__main__':
    asyncio.run(main())
