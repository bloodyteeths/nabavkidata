"""
Scraper Scheduler - Automated periodic scraping

Features:
- Scheduled scraping (hourly, daily, weekly)
- Incremental updates (only new/changed tenders)
- Error handling and retry logic
- Scraping history tracking
- Resource management
"""
import os
import sys
import logging
import asyncio
import asyncpg
from datetime import datetime, timedelta
from pathlib import Path
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from typing import Optional, Dict, List
from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)


class ScrapingHistory:
    """
    Track scraping job history in database
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None

    async def connect(self):
        """Establish database connection"""
        if not self.conn:
            self.conn = await asyncpg.connect(self.database_url)
            # Create scraping_jobs table if not exists
            await self._ensure_table_exists()

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def _ensure_table_exists(self):
        """Create scraping_jobs table if it doesn't exist"""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scraping_jobs (
                job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                status VARCHAR(50) NOT NULL,
                tenders_scraped INTEGER DEFAULT 0,
                documents_scraped INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                error_message TEXT,
                spider_name VARCHAR(100),
                incremental BOOLEAN DEFAULT TRUE,
                last_scraped_date TIMESTAMP
            )
        """)

    async def start_job(self, spider_name: str, incremental: bool = True) -> str:
        """
        Record start of scraping job

        Returns:
            job_id (str)
        """
        result = await self.conn.fetchrow("""
            INSERT INTO scraping_jobs (
                started_at, status, spider_name, incremental
            ) VALUES ($1, $2, $3, $4)
            RETURNING job_id
        """, datetime.utcnow(), 'running', spider_name, incremental)

        job_id = str(result['job_id'])
        logger.info(f"Started scraping job: {job_id}")
        return job_id

    async def complete_job(
        self,
        job_id: str,
        status: str = 'completed',
        tenders_scraped: int = 0,
        documents_scraped: int = 0,
        errors_count: int = 0,
        error_message: Optional[str] = None
    ):
        """Record completion of scraping job"""
        await self.conn.execute("""
            UPDATE scraping_jobs SET
                completed_at = $1,
                status = $2,
                tenders_scraped = $3,
                documents_scraped = $4,
                errors_count = $5,
                error_message = $6,
                last_scraped_date = $1
            WHERE job_id = $7
        """,
            datetime.utcnow(),
            status,
            tenders_scraped,
            documents_scraped,
            errors_count,
            error_message,
            job_id
        )

        logger.info(
            f"Completed job {job_id}: {status}, "
            f"{tenders_scraped} tenders, {documents_scraped} documents"
        )

    async def get_last_scrape_time(self) -> Optional[datetime]:
        """Get timestamp of last successful scrape"""
        result = await self.conn.fetchrow("""
            SELECT last_scraped_date
            FROM scraping_jobs
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 1
        """)

        if result and result['last_scraped_date']:
            return result['last_scraped_date']
        return None

    async def get_recent_jobs(self, limit: int = 10) -> List[Dict]:
        """Get recent scraping jobs"""
        rows = await self.conn.fetch("""
            SELECT
                job_id,
                started_at,
                completed_at,
                status,
                tenders_scraped,
                documents_scraped,
                errors_count,
                spider_name,
                incremental
            FROM scraping_jobs
            ORDER BY started_at DESC
            LIMIT $1
        """, limit)

        return [dict(row) for row in rows]


class IncrementalScraper:
    """
    Handles incremental scraping (only new/updated tenders)
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None

    async def connect(self):
        """Establish database connection"""
        if not self.conn:
            self.conn = await asyncpg.connect(self.database_url)

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def get_existing_tender_ids(self) -> set:
        """Get set of tender IDs already in database"""
        rows = await self.conn.fetch("SELECT tender_id FROM tenders")
        return {row['tender_id'] for row in rows}

    async def get_recently_updated_tenders(self, since: datetime) -> set:
        """Get tender IDs updated since given timestamp"""
        rows = await self.conn.fetch("""
            SELECT tender_id
            FROM tenders
            WHERE updated_at >= $1
        """, since)
        return {row['tender_id'] for row in rows}

    async def should_scrape_tender(
        self,
        tender_id: str,
        last_scrape_time: Optional[datetime] = None
    ) -> bool:
        """
        Determine if tender should be scraped

        Logic:
        - New tender (not in DB) → scrape
        - Existing tender + no last_scrape_time → skip
        - Existing tender + has last_scrape_time → check if updated
        """
        result = await self.conn.fetchrow("""
            SELECT updated_at
            FROM tenders
            WHERE tender_id = $1
        """, tender_id)

        if not result:
            # New tender
            return True

        if not last_scrape_time:
            # Existing tender, no incremental scraping
            return False

        # Check if updated since last scrape
        tender_updated = result['updated_at']
        return tender_updated > last_scrape_time


class ScraperScheduler:
    """
    Main scheduler for automated scraping
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        self.history = ScrapingHistory(self.database_url)
        self.incremental = IncrementalScraper(self.database_url)

    async def run_scrape(
        self,
        spider_name: str = 'nabavki',
        incremental: bool = True,
        max_pages: Optional[int] = None
    ) -> Dict:
        """
        Run scraping job

        Args:
            spider_name: Spider to run (default: 'nabavki')
            incremental: Only scrape new/updated tenders
            max_pages: Limit pages to scrape (for testing)

        Returns:
            Job statistics: {job_id, status, tenders_scraped, ...}
        """
        logger.info(f"Starting scrape: spider={spider_name}, incremental={incremental}")

        # Connect to database
        await self.history.connect()
        await self.incremental.connect()

        # Start job tracking
        job_id = await self.history.start_job(spider_name, incremental)

        try:
            # Get last scrape time for incremental scraping
            last_scrape_time = None
            if incremental:
                last_scrape_time = await self.history.get_last_scrape_time()
                logger.info(f"Last scrape: {last_scrape_time}")

            # Run spider
            stats = await self._run_spider(
                spider_name,
                last_scrape_time=last_scrape_time,
                max_pages=max_pages
            )

            # Mark job as completed
            await self.history.complete_job(
                job_id,
                status='completed',
                tenders_scraped=stats.get('tenders_scraped', 0),
                documents_scraped=stats.get('documents_scraped', 0),
                errors_count=stats.get('errors_count', 0)
            )

            # Auto-trigger embeddings if documents were scraped
            embedding_stats = None
            if stats.get('documents_scraped', 0) > 0:
                try:
                    logger.info("Auto-triggering embeddings for new documents...")
                    embedding_stats = await self._trigger_embeddings(job_id)
                    logger.info(
                        f"✓ Embeddings generated: {embedding_stats.get('total_embeddings', 0)} "
                        f"from {embedding_stats.get('total_processed', 0)} documents"
                    )
                except Exception as e:
                    logger.warning(f"Auto-embedding failed (non-critical): {e}")

            result = {
                'job_id': job_id,
                'status': 'completed',
                **stats
            }

            if embedding_stats:
                result['embedding_stats'] = embedding_stats

            return result

        except Exception as e:
            logger.error(f"Scraping job failed: {e}")

            # Mark job as failed
            await self.history.complete_job(
                job_id,
                status='failed',
                errors_count=1,
                error_message=str(e)
            )

            # Send email alert to admin
            try:
                await self._send_failure_alert(job_id, str(e))
            except Exception as email_error:
                logger.error(f"Failed to send email alert: {email_error}")

            return {
                'job_id': job_id,
                'status': 'failed',
                'error': str(e)
            }

        finally:
            # Cleanup
            await self.history.close()
            await self.incremental.close()

    async def _trigger_embeddings(self, job_id: str) -> Dict:
        """
        Trigger embeddings generation for documents from scraping job

        Args:
            job_id: Scraping job ID

        Returns:
            Embedding statistics
        """
        try:
            # Import here to avoid circular dependencies
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../ai/embeddings'))
            from pipeline import trigger_after_scrape

            stats = await trigger_after_scrape(job_id)
            return stats

        except ImportError as e:
            logger.warning(f"Embeddings pipeline not available: {e}")
            return {'total_processed': 0, 'total_embeddings': 0, 'errors': 0}

    async def _run_spider(
        self,
        spider_name: str,
        last_scrape_time: Optional[datetime] = None,
        max_pages: Optional[int] = None
    ) -> Dict:
        """
        Run Scrapy spider and return statistics

        Note: Scrapy runs synchronously, so we use run_in_executor
        """
        def run_scrapy():
            """Run Scrapy in subprocess"""
            # Get Scrapy settings
            settings = get_project_settings()

            # Add custom settings
            if max_pages:
                settings.set('CLOSESPIDER_PAGECOUNT', max_pages)

            # Create crawler process
            process = CrawlerProcess(settings)

            # Add spider
            process.crawl(spider_name)

            # Run (blocks until complete)
            process.start()

            # Get statistics from spider
            # (In real implementation, spider would write stats to DB)
            return {
                'tenders_scraped': 0,  # Placeholder
                'documents_scraped': 0,
                'errors_count': 0,
            }

        # Run Scrapy in executor (non-blocking)
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(None, run_scrapy)

        return stats

    async def get_scraping_history(self, limit: int = 10) -> List[Dict]:
        """Get recent scraping job history"""
        await self.history.connect()
        try:
            return await self.history.get_recent_jobs(limit)
        finally:
            await self.history.close()

    async def _send_failure_alert(self, job_id: str, error_message: str):
        """
        Send email alert to admin on scraper failure

        Args:
            job_id: Failed job ID
            error_message: Error message
        """
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@nabavkidata.com')

        try:
            # Import here to avoid circular dependencies
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_user = os.getenv('SMTP_USER', '')
            smtp_password = os.getenv('SMTP_PASSWORD', '')
            from_email = os.getenv('FROM_EMAIL', smtp_user)

            if not smtp_user or not smtp_password:
                logger.warning("SMTP credentials not configured, skipping email alert")
                return

            # Create email
            message = MIMEMultipart('alternative')
            message['Subject'] = f"[ALERT] Scraper Job Failed - {job_id}"
            message['From'] = f"Nabavkidata Scraper <{from_email}>"
            message['To'] = admin_email

            # Plain text version
            text_content = f"""
Scraper Job Failed

Job ID: {job_id}
Status: Failed
Error: {error_message}

Please investigate this issue and restart the scraper if necessary.

View scraper status: https://nabavkidata.com/admin/scraper
            """

            # HTML version
            html_content = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4;">
    <table style="width: 100%; padding: 20px;">
        <tr>
            <td align="center">
                <table style="width: 600px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 40px 30px; text-align: center; background-color: #dc3545; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Scraper Job Failed</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <div style="padding: 15px; background-color: #f8d7da; border-left: 4px solid #dc3545; color: #721c24; margin-bottom: 20px;">
                                <strong>Alert:</strong> A scraping job has failed and requires attention.
                            </div>
                            <p style="margin-top: 20px;"><strong>Job Details:</strong></p>
                            <ul style="color: #333333; font-size: 16px; line-height: 1.8;">
                                <li><strong>Job ID:</strong> {job_id}</li>
                                <li><strong>Status:</strong> Failed</li>
                            </ul>
                            <p style="margin-top: 20px;"><strong>Error Message:</strong></p>
                            <pre style="padding: 15px; background-color: #f4f4f4; border-left: 3px solid #999; font-family: monospace; font-size: 14px; color: #333; white-space: pre-wrap; word-wrap: break-word;">{error_message}</pre>
                            <p style="margin-top: 25px;">Please investigate this issue and restart the scraper if necessary.</p>
                            <table style="margin: 30px auto;">
                                <tr>
                                    <td style="border-radius: 4px; background-color: #007bff;">
                                        <a href="https://nabavkidata.com/admin/scraper" style="display: inline-block; padding: 12px 40px; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff; text-decoration: none;">
                                            View Scraper Status
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 30px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                &copy; 2025 Nabavkidata. Automated System Alert.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
            """

            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')

            message.attach(text_part)
            message.attach(html_part)

            # Send email
            await aiosmtplib.send(
                message,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                start_tls=True
            )

            logger.info(f"Failure alert sent to {admin_email}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")


# CLI Commands

async def run_scrape_job(
    incremental: bool = True,
    max_pages: Optional[int] = None
):
    """
    CLI command to run scraping job

    Usage:
        python scheduler.py run --incremental --max-pages 10
    """
    scheduler = ScraperScheduler()
    result = await scheduler.run_scrape(
        incremental=incremental,
        max_pages=max_pages
    )

    print("\n" + "=" * 60)
    print("SCRAPING JOB COMPLETED")
    print("=" * 60)
    print(f"Job ID: {result['job_id']}")
    print(f"Status: {result['status']}")

    if result['status'] == 'completed':
        print(f"Tenders scraped: {result.get('tenders_scraped', 0)}")
        print(f"Documents scraped: {result.get('documents_scraped', 0)}")
        print(f"Errors: {result.get('errors_count', 0)}")
    else:
        print(f"Error: {result.get('error', 'Unknown')}")

    print("=" * 60)


async def show_history(limit: int = 10):
    """
    CLI command to show scraping history

    Usage:
        python scheduler.py history --limit 20
    """
    scheduler = ScraperScheduler()
    jobs = await scheduler.get_scraping_history(limit)

    print("\n" + "=" * 60)
    print("SCRAPING JOB HISTORY")
    print("=" * 60)

    for job in jobs:
        print(f"\nJob ID: {job['job_id']}")
        print(f"  Started: {job['started_at']}")
        print(f"  Completed: {job['completed_at']}")
        print(f"  Status: {job['status']}")
        print(f"  Spider: {job['spider_name']}")
        print(f"  Incremental: {job['incremental']}")
        print(f"  Tenders: {job['tenders_scraped']}")
        print(f"  Documents: {job['documents_scraped']}")
        print(f"  Errors: {job['errors_count']}")

    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Scraper Scheduler')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run scraping job')
    run_parser.add_argument(
        '--incremental',
        action='store_true',
        default=True,
        help='Only scrape new/updated tenders'
    )
    run_parser.add_argument(
        '--full',
        action='store_true',
        help='Full scrape (not incremental)'
    )
    run_parser.add_argument(
        '--max-pages',
        type=int,
        help='Maximum pages to scrape (for testing)'
    )

    # History command
    history_parser = subparsers.add_parser('history', help='Show scraping history')
    history_parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Number of jobs to show'
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )

    # Run command
    if args.command == 'run':
        incremental = not args.full if args.full else args.incremental
        asyncio.run(run_scrape_job(incremental, args.max_pages))

    elif args.command == 'history':
        asyncio.run(show_history(args.limit))

    else:
        parser.print_help()
