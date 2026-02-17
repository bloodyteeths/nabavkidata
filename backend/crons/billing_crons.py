#!/usr/bin/env python3
"""
Billing Cron Jobs for nabavkidata.com

Run via cron:
# Reset daily usage counters at midnight
0 0 * * * cd /home/ubuntu/nabavkidata && python3 backend/crons/billing_crons.py reset_daily

# Reset monthly usage counters on 1st of month
0 0 1 * * cd /home/ubuntu/nabavkidata && python3 backend/crons/billing_crons.py reset_monthly

# Expire trials and downgrade to free (every hour)
0 * * * * cd /home/ubuntu/nabavkidata && python3 backend/crons/billing_crons.py expire_trials

# Cleanup old webhook events (weekly on Sunday)
0 3 * * 0 cd /home/ubuntu/nabavkidata && python3 backend/crons/billing_crons.py cleanup_webhooks
"""
import os
import sys
import asyncio
import logging
from datetime import datetime, date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_db_pool():
    """Create database connection pool"""
    database_url = os.getenv('DATABASE_URL', '')
    # Convert asyncpg URL format
    db_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
    return await asyncpg.create_pool(db_url, min_size=1, max_size=5)


async def reset_daily_counters():
    """Reset all daily usage counters"""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE usage_counters
                SET count = 0, last_reset_at = NOW(), updated_at = NOW()
                WHERE period_type = 'daily'
                  AND period_start < CURRENT_DATE
            """)
            logger.info(f"Reset daily counters: {result}")
    finally:
        await pool.close()


async def reset_monthly_counters():
    """Reset all monthly usage counters (run on 1st of month)"""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE usage_counters
                SET count = 0, last_reset_at = NOW(), updated_at = NOW()
                WHERE period_type = 'monthly'
                  AND period_start < DATE_TRUNC('month', CURRENT_DATE)
            """)
            logger.info(f"Reset monthly counters: {result}")
    finally:
        await pool.close()


async def expire_trials():
    """Expire trials that have passed their end date and downgrade to free"""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            # Expire trials
            result = await conn.fetch("""
                UPDATE users
                SET trial_expired = TRUE,
                    subscription_tier = 'free',
                    updated_at = NOW()
                WHERE trial_ends_at < NOW()
                  AND trial_expired = FALSE
                  AND subscription_tier = 'trial'
                RETURNING user_id, email
            """)

            if result:
                logger.info(f"Expired {len(result)} trials")
                for row in result:
                    logger.info(f"  - User {row['user_id']} ({row['email']}) trial expired")
                    # TODO: Send trial expired email notification
            else:
                logger.info("No trials to expire")
    finally:
        await pool.close()


async def cleanup_webhooks():
    """Delete webhook events older than 90 days"""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM webhook_events
                WHERE processed_at < NOW() - INTERVAL '90 days'
            """)
            logger.info(f"Cleaned up old webhook events: {result}")
    finally:
        await pool.close()


async def show_stats():
    """Show current billing stats"""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            # Active trials
            trials = await conn.fetchval("""
                SELECT COUNT(*) FROM users
                WHERE subscription_tier = 'trial'
                  AND trial_ends_at > NOW()
            """)

            # Expired trials (today)
            expired_today = await conn.fetchval("""
                SELECT COUNT(*) FROM users
                WHERE trial_expired = TRUE
                  AND updated_at >= CURRENT_DATE
            """)

            # Paid subscribers
            paid = await conn.fetchval("""
                SELECT COUNT(*) FROM users
                WHERE subscription_tier IN ('starter', 'professional', 'enterprise')
            """)

            # Usage counters today
            usage = await conn.fetch("""
                SELECT counter_type, SUM(count) as total
                FROM usage_counters
                WHERE period_type = 'daily'
                  AND period_start = CURRENT_DATE
                GROUP BY counter_type
            """)

            print(f"\n=== Billing Stats ({datetime.now().isoformat()}) ===")
            print(f"Active trials: {trials}")
            print(f"Expired today: {expired_today}")
            print(f"Paid subscribers: {paid}")
            print(f"\nToday's usage:")
            for row in usage:
                print(f"  {row['counter_type']}: {row['total']}")
    finally:
        await pool.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python billing_crons.py <command>")
        print("Commands: reset_daily, reset_monthly, expire_trials, cleanup_webhooks, stats")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'reset_daily':
        asyncio.run(reset_daily_counters())
    elif command == 'reset_monthly':
        asyncio.run(reset_monthly_counters())
    elif command == 'expire_trials':
        asyncio.run(expire_trials())
    elif command == 'cleanup_webhooks':
        asyncio.run(cleanup_webhooks())
    elif command == 'stats':
        asyncio.run(show_stats())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
