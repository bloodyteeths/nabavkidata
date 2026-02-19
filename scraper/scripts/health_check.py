#!/usr/bin/env python3
"""
Scraper Health Check

Monitors scraping jobs and alerts on failures
"""
import os
import sys
import asyncio
import asyncpg
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def check_scraper_health():
    """
    Check scraper health by analyzing recent job history

    Alerts if:
    - No successful scrapes in last 24 hours
    - High error rate (>50% in last 10 jobs)
    - Jobs taking unusually long
    """
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)

    conn = await asyncpg.connect(database_url)

    try:
        # Check if scraping_jobs table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'scraping_jobs'
            )
        """)

        if not table_exists:
            print("⚠️  scraping_jobs table not found (run scheduler first)")
            return

        # Get last successful scrape
        last_success = await conn.fetchrow("""
            SELECT completed_at, tenders_scraped, documents_scraped
            FROM scraping_jobs
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 1
        """)

        now = datetime.utcnow()
        hours_since_success = None

        if last_success:
            completed_at = last_success['completed_at']
            hours_since_success = (now - completed_at).total_seconds() / 3600

        # Get recent jobs (last 10)
        recent_jobs = await conn.fetch("""
            SELECT status, completed_at - started_at as duration, errors_count
            FROM scraping_jobs
            WHERE completed_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 10
        """)

        # Calculate metrics
        total_jobs = len(recent_jobs)
        failed_jobs = sum(1 for job in recent_jobs if job['status'] == 'failed')
        error_rate = (failed_jobs / total_jobs * 100) if total_jobs > 0 else 0

        avg_duration = None
        if recent_jobs:
            durations = [job['duration'].total_seconds() for job in recent_jobs if job['duration']]
            if durations:
                avg_duration = sum(durations) / len(durations)

        # Print health report
        print("\n" + "=" * 60)
        print("SCRAPER HEALTH CHECK")
        print("=" * 60)
        print(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("")

        # Last successful scrape
        if last_success:
            print(f"Last successful scrape: {completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  ({hours_since_success:.1f} hours ago)")
            print(f"  Tenders: {last_success['tenders_scraped']}")
            print(f"  Documents: {last_success['documents_scraped']}")

            if hours_since_success > 24:
                print("  ⚠️  WARNING: No successful scrape in 24 hours!")
        else:
            print("⚠️  No successful scrapes found")

        print("")

        # Error rate
        print(f"Recent jobs (last {total_jobs}):")
        print(f"  Failed: {failed_jobs}")
        print(f"  Error rate: {error_rate:.1f}%")

        if error_rate > 50:
            print("  ⚠️  WARNING: High error rate!")

        print("")

        # Average duration
        if avg_duration:
            print(f"Average job duration: {avg_duration / 60:.1f} minutes")

            if avg_duration > 3600:  # > 1 hour
                print("  ⚠️  WARNING: Jobs taking unusually long!")

        print("")

        # Overall status
        if hours_since_success and hours_since_success <= 2 and error_rate < 20:
            print("✓ Status: HEALTHY")
        elif hours_since_success and hours_since_success <= 24 and error_rate < 50:
            print("⚠️  Status: WARNING")
        else:
            print("❌ Status: UNHEALTHY")

        print("=" * 60)
        print("")

        # Exit code based on health
        if hours_since_success and hours_since_success > 24:
            sys.exit(1)  # Alert
        elif error_rate > 50:
            sys.exit(1)  # Alert

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_scraper_health())
