#!/usr/bin/env python3
"""
Real-time scraper monitoring dashboard
Displays key metrics and system health status
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()



class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    END = '\033[0m'


async def get_database_stats():
    """Get database statistics"""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print(f"{Colors.RED}ERROR: DATABASE_URL not set{Colors.END}")
        sys.exit(1)

    try:
        conn = await asyncpg.connect(db_url, timeout=10)

        # Total tenders
        total = await conn.fetchval("SELECT COUNT(*) FROM tenders")

        # Today's scrapes
        today = await conn.fetchval("""
            SELECT COUNT(*) FROM tenders
            WHERE scraped_at >= CURRENT_DATE
        """)

        # This week's scrapes
        week = await conn.fetchval("""
            SELECT COUNT(*) FROM tenders
            WHERE scraped_at >= CURRENT_DATE - INTERVAL '7 days'
        """)

        # Active tenders (open and not expired)
        active = await conn.fetchval("""
            SELECT COUNT(*) FROM tenders
            WHERE status = 'open' AND closing_date >= CURRENT_DATE
        """)

        # Recent awards (last 7 days)
        recent_awards = await conn.fetchval("""
            SELECT COUNT(*) FROM tenders
            WHERE status = 'awarded' AND scraped_at >= NOW() - INTERVAL '7 days'
        """)

        # Tenders by status
        status_counts = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM tenders
            GROUP BY status
            ORDER BY count DESC
        """)

        # Document statistics
        doc_total = await conn.fetchval("SELECT COUNT(*) FROM documents") or 0

        doc_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'processing') as processing
            FROM documents
        """) if doc_total > 0 else None

        # Document success rate (last 7 days)
        doc_success_rate = await conn.fetchval("""
            SELECT
                ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'completed') / NULLIF(COUNT(*), 0), 2)
            FROM documents
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """) or 0.0

        # Top CPV codes
        top_cpv = await conn.fetch("""
            SELECT
                UNNEST(string_to_array(cpv_codes, ',')) as cpv,
                COUNT(*) as count
            FROM tenders
            WHERE cpv_codes IS NOT NULL
            GROUP BY cpv
            ORDER BY count DESC
            LIMIT 5
        """)

        # Recent high-value tenders
        high_value = await conn.fetch("""
            SELECT title, estimated_value, closing_date
            FROM tenders
            WHERE estimated_value > 1000000
            AND status = 'open'
            AND closing_date >= CURRENT_DATE
            ORDER BY estimated_value DESC
            LIMIT 5
        """)

        await conn.close()

        return {
            'total': total,
            'today': today,
            'week': week,
            'active': active,
            'recent_awards': recent_awards,
            'status_counts': status_counts,
            'doc_total': doc_total,
            'doc_stats': doc_stats,
            'doc_success_rate': doc_success_rate,
            'top_cpv': top_cpv,
            'high_value': high_value,
        }

    except Exception as e:
        print(f"{Colors.RED}Database error: {e}{Colors.END}")
        sys.exit(1)


def get_log_stats():
    """Get log file statistics"""
    log_dir = Path("/home/ubuntu/nabavkidata/scraper/logs")

    if not log_dir.exists():
        return None

    # Count log files
    log_files = list(log_dir.glob("*.log"))
    compressed_logs = list(log_dir.glob("*.log.gz"))

    # Recent logs
    recent_logs = sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]

    # Total log size
    total_size = sum(f.stat().st_size for f in log_files + compressed_logs)

    return {
        'log_files': len(log_files),
        'compressed_logs': len(compressed_logs),
        'total_size': total_size,
        'recent_logs': recent_logs,
    }


def get_cron_status():
    """Check cron job status"""
    import subprocess

    try:
        # Get crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        if result.returncode != 0:
            return None

        # Count scraper jobs
        lines = result.stdout.split('\n')
        scraper_jobs = [l for l in lines if 'nabavkidata' in l.lower() and not l.strip().startswith('#')]

        return {
            'total_jobs': len(scraper_jobs),
            'jobs': scraper_jobs,
        }

    except Exception as e:
        return None


def format_size(bytes):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0


def format_number(num):
    """Format number with commas"""
    return f"{num:,}"


def print_dashboard(stats, log_stats, cron_stats):
    """Print the monitoring dashboard"""

    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}{Colors.CYAN}NABAVKIDATA SCRAPER MONITORING DASHBOARD{Colors.END}")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("")

    # DATABASE STATISTICS
    print(f"{Colors.BOLD}DATABASE STATISTICS{Colors.END}")
    print("-" * 80)
    print(f"Total Tenders:        {Colors.GREEN}{format_number(stats['total'])}{Colors.END}")
    print(f"Scraped Today:        {Colors.YELLOW}{format_number(stats['today'])}{Colors.END}")
    print(f"Scraped This Week:    {format_number(stats['week'])}")
    print(f"Active Tenders:       {Colors.BLUE}{format_number(stats['active'])}{Colors.END}")
    print(f"Recent Awards (7d):   {format_number(stats['recent_awards'])}")
    print("")

    # TENDER STATUS BREAKDOWN
    print(f"{Colors.BOLD}TENDER STATUS BREAKDOWN{Colors.END}")
    print("-" * 80)
    for row in stats['status_counts']:
        status = row['status'] or 'unknown'
        count = row['count']
        print(f"  {status:20} {format_number(count):>10}")
    print("")

    # DOCUMENT STATISTICS
    print(f"{Colors.BOLD}DOCUMENT PROCESSING{Colors.END}")
    print("-" * 80)
    print(f"Total Documents:      {format_number(stats['doc_total'])}")
    if stats['doc_stats']:
        print(f"  Completed:          {Colors.GREEN}{format_number(stats['doc_stats']['completed'])}{Colors.END}")
        print(f"  Pending:            {Colors.YELLOW}{format_number(stats['doc_stats']['pending'])}{Colors.END}")
        print(f"  Processing:         {Colors.BLUE}{format_number(stats['doc_stats']['processing'])}{Colors.END}")
        print(f"  Failed:             {Colors.RED}{format_number(stats['doc_stats']['failed'])}{Colors.END}")
    print(f"Success Rate (7d):    {stats['doc_success_rate']:.2f}%")
    print("")

    # TOP CPV CODES
    if stats['top_cpv']:
        print(f"{Colors.BOLD}TOP CPV CODES{Colors.END}")
        print("-" * 80)
        for row in stats['top_cpv']:
            cpv = row['cpv'].strip()
            count = row['count']
            print(f"  {cpv:30} {format_number(count):>10}")
        print("")

    # HIGH-VALUE TENDERS
    if stats['high_value']:
        print(f"{Colors.BOLD}HIGH-VALUE OPEN TENDERS{Colors.END}")
        print("-" * 80)
        for row in stats['high_value']:
            title = (row['title'][:50] + '...') if len(row['title']) > 50 else row['title']
            value = row['estimated_value']
            closing = row['closing_date'].strftime('%Y-%m-%d') if row['closing_date'] else 'N/A'
            print(f"  {title:52} ${value:>12,.2f}  Closes: {closing}")
        print("")

    # LOG FILE STATISTICS
    if log_stats:
        print(f"{Colors.BOLD}LOG FILE STATISTICS{Colors.END}")
        print("-" * 80)
        print(f"Active Log Files:     {log_stats['log_files']}")
        print(f"Compressed Logs:      {log_stats['compressed_logs']}")
        print(f"Total Storage:        {format_size(log_stats['total_size'])}")
        print("")
        if log_stats['recent_logs']:
            print("Recent Log Files:")
            for log in log_stats['recent_logs']:
                mtime = datetime.fromtimestamp(log.stat().st_mtime)
                age = datetime.now() - mtime
                size = format_size(log.stat().st_size)
                print(f"  {log.name:40} {size:>10}  {age.seconds // 60}m ago")
        print("")

    # CRON JOB STATUS
    if cron_stats:
        print(f"{Colors.BOLD}CRON JOB STATUS{Colors.END}")
        print("-" * 80)
        print(f"Active Jobs:          {cron_stats['total_jobs']}")
        print("")
        print("Scheduled Jobs:")
        for job in cron_stats['jobs']:
            if job.strip():
                print(f"  {job}")
        print("")

    # SYSTEM HEALTH INDICATORS
    print(f"{Colors.BOLD}HEALTH INDICATORS{Colors.END}")
    print("-" * 80)

    # Check if scraping is active
    scraping_healthy = stats['today'] > 0
    if scraping_healthy:
        print(f"  Scraping Activity:  {Colors.GREEN}✓ Active{Colors.END}")
    else:
        print(f"  Scraping Activity:  {Colors.RED}✗ No scrapes today{Colors.END}")

    # Check document processing
    doc_healthy = stats['doc_stats'] and stats['doc_stats']['pending'] < 1000
    if doc_healthy:
        print(f"  Document Queue:     {Colors.GREEN}✓ Healthy{Colors.END}")
    else:
        print(f"  Document Queue:     {Colors.YELLOW}⚠ Large queue{Colors.END}")

    # Check success rate
    success_healthy = stats['doc_success_rate'] > 80
    if success_healthy:
        print(f"  Success Rate:       {Colors.GREEN}✓ Good{Colors.END}")
    else:
        print(f"  Success Rate:       {Colors.YELLOW}⚠ Below threshold{Colors.END}")

    print("")
    print("=" * 80)


async def main():
    """Main function"""
    try:
        # Get all statistics
        print("Loading statistics...")
        stats = await get_database_stats()
        log_stats = get_log_stats()
        cron_stats = get_cron_status()

        # Print dashboard
        print_dashboard(stats, log_stats, cron_stats)

    except KeyboardInterrupt:
        print("\nMonitoring interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
