#!/usr/bin/env python3
"""
Migration script to parse bidders_data and lots_data from raw_data_json
into normalized tender_lots and tender_bidders tables.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import asyncpg
from asyncpg.pool import Pool
from dotenv import load_dotenv
load_dotenv()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/tamsar/Downloads/nabavkidata/scripts/migration_raw_json.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MigrationStats:
    """Track migration statistics"""
    def __init__(self):
        self.tenders_with_bidders = 0
        self.tenders_with_lots = 0
        self.bidders_inserted = 0
        self.bidders_updated = 0
        self.bidders_skipped = 0
        self.lots_inserted = 0
        self.lots_updated = 0
        self.errors = []
        self.start_time = datetime.now()

    def add_error(self, tender_id: str, error: str):
        self.errors.append({"tender_id": tender_id, "error": error})
        logger.error(f"Error for tender {tender_id}: {error}")

    def print_summary(self):
        duration = datetime.now() - self.start_time
        logger.info("=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration}")
        logger.info(f"Tenders with parseable bidders_data: {self.tenders_with_bidders}")
        logger.info(f"Tenders with parseable lots_data: {self.tenders_with_lots}")
        logger.info(f"Bidders inserted: {self.bidders_inserted}")
        logger.info(f"Bidders updated: {self.bidders_updated}")
        logger.info(f"Bidders skipped (duplicates): {self.bidders_skipped}")
        logger.info(f"Lots inserted: {self.lots_inserted}")
        logger.info(f"Lots updated: {self.lots_updated}")
        logger.info(f"Total errors: {len(self.errors)}")

        if self.errors:
            logger.info("\nFirst 10 errors:")
            for err in self.errors[:10]:
                logger.info(f"  - {err['tender_id']}: {err['error']}")

        logger.info("=" * 80)


async def get_db_pool() -> Pool:
    """Create database connection pool"""
    return await asyncpg.create_pool(
        host='nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com',
        port=5432,
        user='nabavki_user',
        password=os.getenv('DB_PASSWORD', ''),
        database='nabavkidata',
        min_size=2,
        max_size=10
    )


def parse_bidders_data(bidders_json_str: str) -> Optional[List[Dict]]:
    """Parse bidders_data from JSON string"""
    if not bidders_json_str or bidders_json_str == 'null' or bidders_json_str == '':
        return None

    try:
        bidders = json.loads(bidders_json_str)
        if isinstance(bidders, list) and len(bidders) > 0:
            return bidders
        return None
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse bidders_data: {e}")
        return None


def parse_lots_data(lots_json_str: str) -> Optional[List[Dict]]:
    """Parse lots_data from JSON string"""
    if not lots_json_str or lots_json_str == 'null' or lots_json_str == '':
        return None

    try:
        lots = json.loads(lots_json_str)
        if isinstance(lots, list) and len(lots) > 0:
            return lots
        return None
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse lots_data: {e}")
        return None


async def process_bidders(
    conn: asyncpg.Connection,
    tender_id: str,
    bidders: List[Dict],
    stats: MigrationStats
) -> None:
    """Process and insert bidders for a tender"""
    for bidder in bidders:
        try:
            company_name = bidder.get('company_name', '').strip()
            if not company_name:
                logger.warning(f"Skipping bidder with no company_name for tender {tender_id}")
                continue

            # Check if bidder already exists for this tender
            existing = await conn.fetchrow(
                """
                SELECT bidder_id FROM tender_bidders
                WHERE tender_id = $1 AND company_name = $2
                """,
                tender_id, company_name
            )

            if existing:
                stats.bidders_skipped += 1
                logger.debug(f"Bidder already exists: {company_name} for tender {tender_id}")
                continue

            # Extract bidder data
            bid_amount_mkd = bidder.get('bid_amount_mkd')
            if bid_amount_mkd is not None:
                try:
                    bid_amount_mkd = float(bid_amount_mkd)
                except (ValueError, TypeError):
                    bid_amount_mkd = None

            is_winner = bidder.get('is_winner', False)
            if isinstance(is_winner, str):
                is_winner = is_winner.lower() in ('true', '1', 'yes')

            rank = bidder.get('rank')
            if rank is not None:
                try:
                    rank = int(rank)
                except (ValueError, TypeError):
                    rank = None

            disqualified = bidder.get('disqualified', False)
            if isinstance(disqualified, str):
                disqualified = disqualified.lower() in ('true', '1', 'yes')

            disqualification_reason = bidder.get('disqualification_reason')
            company_tax_id = bidder.get('company_tax_id')
            company_address = bidder.get('company_address')

            # Insert bidder
            await conn.execute(
                """
                INSERT INTO tender_bidders (
                    tender_id, company_name, company_tax_id, company_address,
                    bid_amount_mkd, is_winner, rank, disqualified,
                    disqualification_reason, raw_data_json
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                tender_id, company_name, company_tax_id, company_address,
                bid_amount_mkd, is_winner, rank, disqualified,
                disqualification_reason, json.dumps(bidder)
            )

            stats.bidders_inserted += 1
            logger.debug(f"Inserted bidder: {company_name} for tender {tender_id}")

        except Exception as e:
            stats.add_error(tender_id, f"Error processing bidder {bidder.get('company_name', 'unknown')}: {str(e)}")


async def process_lots(
    conn: asyncpg.Connection,
    tender_id: str,
    lots: List[Dict],
    stats: MigrationStats
) -> None:
    """Process and insert lots for a tender"""
    for lot in lots:
        try:
            lot_number = lot.get('lot_number', '').strip()
            lot_title = lot.get('lot_title', '').strip()

            # Check if lot already exists
            existing = await conn.fetchrow(
                """
                SELECT lot_id FROM tender_lots
                WHERE tender_id = $1 AND lot_number = $2
                """,
                tender_id, lot_number
            )

            if existing:
                logger.debug(f"Lot already exists: {lot_number} for tender {tender_id}")
                continue

            # Extract lot data
            lot_description = lot.get('lot_description')
            estimated_value_mkd = lot.get('estimated_value_mkd')
            estimated_value_eur = lot.get('estimated_value_eur')
            actual_value_mkd = lot.get('actual_value_mkd')
            actual_value_eur = lot.get('actual_value_eur')
            cpv_code = lot.get('cpv_code')
            winner = lot.get('winner')
            quantity = lot.get('quantity')
            unit = lot.get('unit')

            # Convert numeric values
            for key in ['estimated_value_mkd', 'estimated_value_eur', 'actual_value_mkd', 'actual_value_eur']:
                value = lot.get(key)
                if value is not None:
                    try:
                        lot[key] = float(value)
                    except (ValueError, TypeError):
                        lot[key] = None

            # Insert lot
            await conn.execute(
                """
                INSERT INTO tender_lots (
                    tender_id, lot_number, lot_title, lot_description,
                    estimated_value_mkd, estimated_value_eur,
                    actual_value_mkd, actual_value_eur,
                    cpv_code, winner, quantity, unit
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                tender_id, lot_number, lot_title, lot_description,
                lot.get('estimated_value_mkd'), lot.get('estimated_value_eur'),
                lot.get('actual_value_mkd'), lot.get('actual_value_eur'),
                cpv_code, winner, quantity, unit
            )

            stats.lots_inserted += 1
            logger.debug(f"Inserted lot: {lot_number} for tender {tender_id}")

        except Exception as e:
            stats.add_error(tender_id, f"Error processing lot {lot.get('lot_number', 'unknown')}: {str(e)}")


async def migrate_tender_data(pool: Pool, stats: MigrationStats) -> None:
    """Main migration function"""
    async with pool.acquire() as conn:
        # Get all tenders with raw_data_json
        tenders = await conn.fetch(
            """
            SELECT tender_id, raw_data_json
            FROM tenders
            WHERE raw_data_json IS NOT NULL
            ORDER BY tender_id
            """
        )

        logger.info(f"Found {len(tenders)} tenders with raw_data_json")

        processed = 0
        for tender in tenders:
            tender_id = tender['tender_id']
            raw_data = tender['raw_data_json']

            if not raw_data:
                continue

            try:
                # Convert raw_data to dict if it's a string
                if isinstance(raw_data, str):
                    raw_data = json.loads(raw_data)
                elif not isinstance(raw_data, dict):
                    logger.warning(f"Unexpected raw_data type for tender {tender_id}: {type(raw_data)}")
                    continue

                # Process bidders_data
                bidders_json_str = raw_data.get('bidders_data')
                bidders = parse_bidders_data(bidders_json_str)

                if bidders:
                    stats.tenders_with_bidders += 1
                    await process_bidders(conn, tender_id, bidders, stats)

                # Process lots_data
                lots_json_str = raw_data.get('lots_data')
                lots = parse_lots_data(lots_json_str)

                if lots:
                    stats.tenders_with_lots += 1
                    await process_lots(conn, tender_id, lots, stats)

                processed += 1
                if processed % 100 == 0:
                    logger.info(f"Processed {processed}/{len(tenders)} tenders...")

            except Exception as e:
                stats.add_error(tender_id, f"Error processing tender: {str(e)}")

        logger.info(f"Completed processing {processed} tenders")


async def main():
    """Main entry point"""
    logger.info("Starting migration of raw_data_json to normalized tables...")

    stats = MigrationStats()
    pool = None

    try:
        pool = await get_db_pool()
        logger.info("Database connection pool created")

        await migrate_tender_data(pool, stats)

        stats.print_summary()

        return 0 if len(stats.errors) == 0 else 1

    except Exception as e:
        logger.error(f"Fatal error during migration: {str(e)}", exc_info=True)
        return 1

    finally:
        if pool:
            await pool.close()
            logger.info("Database connection pool closed")


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
