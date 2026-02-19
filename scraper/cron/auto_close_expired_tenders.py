#!/usr/bin/env python3
"""
Auto-close expired e-pazar tenders

Updates e-pazar tenders from 'active' to 'closed' when closing_date has passed.
Should be run daily via cron.

Usage:
    python3 auto_close_expired_tenders.py
"""
import os
import sys
import asyncio
import logging
from datetime import datetime

# Add project root to path so we can import db_pool
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# DATABASE_URL must be set in environment (e.g. via .env file)
# No hardcoded fallback for security

# Now import after setting env
from ai.db_pool import get_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def close_expired_tenders():
    """Update expired active tenders to closed status"""
    try:
        async with get_connection() as conn:
            # Get count of expired active tenders
            count_query = """
                SELECT COUNT(*)
                FROM epazar_tenders
                WHERE status = 'active'
                AND closing_date < CURRENT_DATE
            """
            expired_count = await conn.fetchval(count_query)

            if expired_count == 0:
                logger.info("No expired active tenders found")
                return 0

            logger.info(f"Found {expired_count} expired active tenders to close")

            # Update expired tenders
            update_query = """
                UPDATE epazar_tenders
                SET status = 'closed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'active'
                AND closing_date < CURRENT_DATE
            """
            result = await conn.execute(update_query)

            # Extract number from result string "UPDATE N"
            updated_count = int(result.split()[-1])

            logger.info(f"Successfully closed {updated_count} expired tenders")

            # Get current status distribution
            stats_query = """
                SELECT status, COUNT(*) as count
                FROM epazar_tenders
                GROUP BY status
                ORDER BY count DESC
            """
            stats = await conn.fetch(stats_query)

            logger.info("Current e-pazar tender status distribution:")
            for row in stats:
                logger.info(f"  {row['status']}: {row['count']}")

            return updated_count

    except Exception as e:
        logger.error(f"Error closing expired tenders: {e}", exc_info=True)
        raise


async def main():
    """Main entry point"""
    start_time = datetime.now()
    logger.info("Starting auto-close expired tenders job")

    try:
        updated_count = await close_expired_tenders()
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Job completed successfully in {duration:.2f}s. Updated {updated_count} tenders")
        return 0
    except Exception as e:
        logger.error(f"Job failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
