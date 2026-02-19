#!/usr/bin/env python3
"""
Campaign Sender Cron Job
Runs periodically to send campaign emails with throttling

Add to crontab:
    # Run every hour during business hours (9am-6pm)
    0 9-18 * * 1-5 cd /home/ubuntu/nabavkidata && python -m backend.crons.campaign_sender_cron

    # Run follow-ups once daily at 10am
    0 10 * * 1-5 cd /home/ubuntu/nabavkidata && python -m backend.crons.campaign_sender_cron --followups
"""
import os
import sys
import asyncio
import logging
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("campaign_cron")

# Database configuration
DB_HOST = os.getenv("DB_HOST", "nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "nabavkidata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


async def get_pool():
    """Create database connection pool"""
    return await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        min_size=2,
        max_size=10
    )


async def send_campaign_batches(pool, batch_size: int = 10):
    """Send batches for all active campaigns"""
    from backend.services.campaign_sender import CampaignSender

    async with pool.acquire() as conn:
        # Get all active campaigns
        campaigns = await conn.fetch("""
            SELECT id, name, settings FROM report_campaigns WHERE status = 'active'
        """)

    if not campaigns:
        logger.info("Нема активни кампањи")
        return

    sender = CampaignSender(pool)

    try:
        for campaign in campaigns:
            campaign_id = str(campaign['id'])
            logger.info(f"Обработка на кампања: {campaign['name']}")

            # Check rate limits
            can_send, msg = await sender.can_send(campaign_id)
            if not can_send:
                logger.info(f"  Лимит достигнат: {msg}")
                continue

            # Send batch
            result = await sender.send_campaign_batch(campaign_id, batch_size=batch_size)

            logger.info(f"  Испратени: {result['sent']}, Неуспешни: {result['failed']}, " +
                        f"Скипнати: {result['skipped_rate_limit']}")

    finally:
        await sender.close()


async def send_followups(pool):
    """Send follow-up emails for all active campaigns"""
    from backend.services.campaign_sender import CampaignSender

    async with pool.acquire() as conn:
        campaigns = await conn.fetch("""
            SELECT id, name FROM report_campaigns WHERE status = 'active'
        """)

    if not campaigns:
        logger.info("Нема активни кампањи за follow-up")
        return

    sender = CampaignSender(pool)

    try:
        for campaign in campaigns:
            campaign_id = str(campaign['id'])
            logger.info(f"Follow-up за кампања: {campaign['name']}")

            result = await sender.send_followups(campaign_id)

            logger.info(f"  Follow-up 1: {result['followup1_sent']}, " +
                        f"Follow-up 2: {result['followup2_sent']}")

    finally:
        await sender.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--followups", action="store_true", help="Send follow-ups only")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info(f"Campaign cron started at {datetime.utcnow()}")

    pool = await get_pool()

    try:
        if args.followups:
            await send_followups(pool)
        else:
            await send_campaign_batches(pool, batch_size=args.batch_size)

    except Exception as e:
        logger.error(f"Error in campaign cron: {e}")
        raise
    finally:
        await pool.close()

    logger.info("Campaign cron completed")


if __name__ == "__main__":
    asyncio.run(main())
