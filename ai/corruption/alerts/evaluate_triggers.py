#!/usr/bin/env python3
"""
Evaluate corruption alert triggers for new tenders.

Run via cron after each scraper + corruption analysis run, or manually:

    python3 ai/corruption/alerts/evaluate_triggers.py

Environment variables:
    DATABASE_URL  - PostgreSQL connection string (required)

The script:
  1. Connects to the database.
  2. Instantiates the CorruptionAlerter.
  3. Calls evaluate_new_tenders() which processes all tenders analyzed
     since the last evaluation run.
  4. Logs the summary.
  5. Exits with code 0 on success, 1 on failure.
"""

import asyncio
import asyncpg
import os
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('corruption_alert_evaluator')


async def main():
    """Main entry point for the alert evaluation cron job."""
    start_time = datetime.utcnow()
    logger.info("Starting corruption alert evaluation...")

    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)

    # Strip SQLAlchemy dialect prefix if present
    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")

    pool = None
    try:
        # Create connection pool
        pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=4,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
        logger.info("Database connection pool created")

        # Verify tables exist
        async with pool.acquire() as conn:
            tables_exist = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'corruption_alert_subscriptions'
                )
            """)
            if not tables_exist:
                logger.error(
                    "Alert tables not found. Run migration 044_corruption_alerts.sql first."
                )
                sys.exit(1)

            # Check active subscriptions count
            sub_count = await conn.fetchval(
                "SELECT COUNT(*) FROM corruption_alert_subscriptions WHERE active = TRUE"
            )
            logger.info(f"Active subscriptions: {sub_count}")

            if sub_count == 0:
                logger.info("No active subscriptions. Nothing to evaluate.")
                return

        # Import and run the alerter
        from corruption_alerter import CorruptionAlerter

        alerter = CorruptionAlerter()
        summary = await alerter.evaluate_new_tenders(pool)

        # Log results
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Evaluation complete in {elapsed:.1f}s:")
        logger.info(f"  Tenders evaluated: {summary['evaluated']}")
        logger.info(f"  Alerts generated:  {summary['alerts_generated']}")
        logger.info(f"  Errors:            {summary['errors']}")
        logger.info(f"  Period:            {summary['since']} to {summary['until']}")

        if summary['by_rule_type']:
            logger.info("  Alerts by rule type:")
            for rule_type, count in sorted(summary['by_rule_type'].items()):
                logger.info(f"    {rule_type}: {count}")

        if summary['errors'] > 0:
            logger.warning(f"Completed with {summary['errors']} errors. Check logs above.")

    except asyncpg.PostgresError as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if pool:
            await pool.close()
            logger.info("Database connection pool closed")


if __name__ == '__main__':
    asyncio.run(main())
