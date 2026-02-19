#!/usr/bin/env python3
"""
Background job to enrich company database with email addresses.

Sources:
1. yellowpages.com.mk - Yellow Pages Macedonia
2. whitepages.mk - Business directory
3. zk.mk - Zlatna Kniga (Golden Book)
4. Company websites (if available)
5. Google search as fallback

Usage:
    python email_enrichment_job.py              # Process 50 companies
    python email_enrichment_job.py --batch 100  # Process 100 companies
    python email_enrichment_job.py --continuous # Run continuously (1 per minute)
"""

import asyncio
import argparse
import logging
import re
import random
from typing import List, Optional, Dict
from urllib.parse import quote_plus
from datetime import datetime

import asyncpg
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = os.getenv('DATABASE_URL')

# Email extraction pattern
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Domains to skip
SKIP_DOMAINS = [
    'google.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'example.com', 'sentry.io', 'schema.org', 'w3.org', 'wixpress.com',
    'cloudflare.com', 'googleapis.com', 'gstatic.com', 'sentry-next.wixpress.com',
    'youtube.com', 'yahoo.com', 'microsoft.com', 'apple.com',
]


class EmailEnricher:
    """Find company emails from various sources"""

    def __init__(self):
        self.browser = None
        self.context = None
        self.playwright = None

    async def start(self):
        """Start browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )

    async def stop(self):
        """Stop browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def _extract_emails(self, text: str) -> List[str]:
        """Extract valid emails from text"""
        emails = set()
        matches = re.findall(EMAIL_PATTERN, text, re.IGNORECASE)

        for email in matches:
            email = email.lower().strip()
            domain = email.split('@')[-1]

            # Skip invalid domains
            if any(skip in domain for skip in SKIP_DOMAINS):
                continue

            # Skip obviously fake emails
            if len(email) > 100 or len(email) < 6:
                continue

            emails.add(email)

        return list(emails)

    async def search_yellow_pages(self, company_name: str) -> Optional[Dict]:
        """Search yellowpages.com.mk"""
        page = await self.context.new_page()

        try:
            # Clean company name
            clean_name = company_name.split()[0] if company_name else ''
            url = f'https://yellowpages.com.mk/?s={quote_plus(clean_name)}'

            logger.debug(f"  Searching Yellow Pages: {clean_name}")
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(2000)

            content = await page.content()
            emails = self._extract_emails(content)

            if emails:
                return {'email': emails[0], 'source': 'yellow_pages'}

            return None

        except Exception as e:
            logger.debug(f"  Yellow Pages error: {e}")
            return None
        finally:
            await page.close()

    async def search_whitepages(self, company_name: str) -> Optional[Dict]:
        """Search whitepages.mk"""
        page = await self.context.new_page()

        try:
            clean_name = company_name.split()[0] if company_name else ''
            url = f'https://whitepages.mk/yellowpages/?search={quote_plus(clean_name)}'

            logger.debug(f"  Searching Whitepages: {clean_name}")
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(2000)

            content = await page.content()
            emails = self._extract_emails(content)

            if emails:
                return {'email': emails[0], 'source': 'whitepages'}

            return None

        except Exception as e:
            logger.debug(f"  Whitepages error: {e}")
            return None
        finally:
            await page.close()

    async def search_zlatna_kniga(self, company_name: str) -> Optional[Dict]:
        """Search zk.mk (Zlatna Kniga)"""
        page = await self.context.new_page()

        try:
            clean_name = company_name.split()[0] if company_name else ''
            url = f'https://zk.mk/dynamic/prebaruvanje?query={quote_plus(clean_name)}'

            logger.debug(f"  Searching Zlatna Kniga: {clean_name}")
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(2000)

            content = await page.content()
            emails = self._extract_emails(content)

            if emails:
                return {'email': emails[0], 'source': 'zlatna_kniga'}

            return None

        except Exception as e:
            logger.debug(f"  Zlatna Kniga error: {e}")
            return None
        finally:
            await page.close()

    async def search_google(self, company_name: str, city: str = '') -> Optional[Dict]:
        """Search Google for company email"""
        page = await self.context.new_page()

        try:
            # Build search query
            query = f'{company_name} {city} Macedonia email contact'
            url = f'https://www.google.com/search?q={quote_plus(query)}'

            logger.debug(f"  Searching Google: {company_name}")
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(3000)

            content = await page.content()
            emails = self._extract_emails(content)

            if emails:
                return {'email': emails[0], 'source': 'google'}

            return None

        except Exception as e:
            logger.debug(f"  Google error: {e}")
            return None
        finally:
            await page.close()

    async def search_company_website(self, website: str) -> Optional[Dict]:
        """Visit company website to find email"""
        if not website or website == 'nan' or 'companiesdata.cloud' in website:
            return None

        page = await self.context.new_page()

        try:
            # Ensure URL has protocol
            if not website.startswith('http'):
                website = 'https://' + website

            logger.debug(f"  Visiting website: {website}")
            await page.goto(website, wait_until='domcontentloaded', timeout=15000)
            await page.wait_for_timeout(2000)

            content = await page.content()
            emails = self._extract_emails(content)

            # Also check contact page
            if not emails:
                contact_links = await page.query_selector_all('a[href*="contact"], a[href*="kontakt"]')
                for link in contact_links[:2]:
                    try:
                        await link.click()
                        await page.wait_for_timeout(2000)
                        content = await page.content()
                        emails = self._extract_emails(content)
                        if emails:
                            break
                    except:
                        continue

            if emails:
                return {'email': emails[0], 'source': 'company_website'}

            return None

        except Exception as e:
            logger.debug(f"  Website error: {e}")
            return None
        finally:
            await page.close()

    async def find_email(self, company_name: str, city: str = '', website: str = '') -> Optional[Dict]:
        """
        Find email for company using multiple sources.
        Returns dict with 'email' and 'source' or None.
        """

        # Try sources - Google first as it's most effective

        # 1. Google search (most effective for finding company emails)
        result = await self.search_google(company_name, city)
        if result:
            return result

        # 2. Company website (if available)
        if website:
            result = await self.search_company_website(website)
            if result:
                return result

        # 3. Yellow Pages Macedonia
        result = await self.search_yellow_pages(company_name)
        if result:
            return result

        # 4. Whitepages.mk
        result = await self.search_whitepages(company_name)
        if result:
            return result

        # 5. Zlatna Kniga
        result = await self.search_zlatna_kniga(company_name)
        if result:
            return result

        return None


async def process_batch(batch_size: int = 50):
    """Process a batch of companies without emails"""

    conn = await asyncpg.connect(DATABASE_URL)
    enricher = EmailEnricher()
    await enricher.start()

    try:
        # Get companies without email that haven't been searched yet
        # Prioritize larger cities and business categories more likely to have email
        companies = await conn.fetch("""
            SELECT company_id, name, city_en, website
            FROM mk_companies
            WHERE email IS NULL
              AND (email_search_attempted = FALSE OR email_search_attempted IS NULL)
            ORDER BY
                CASE city_en
                    WHEN 'SKOPJE' THEN 1
                    WHEN 'Bitola' THEN 2
                    WHEN 'Kumanovo' THEN 3
                    WHEN 'Tetovo' THEN 4
                    WHEN 'Ohrid' THEN 5
                    WHEN 'Strumica' THEN 6
                    ELSE 10
                END,
                company_id
            LIMIT $1
        """, batch_size)

        logger.info(f"Processing {len(companies)} companies...")

        found_count = 0
        not_found_count = 0

        for i, company in enumerate(companies):
            company_id = company['company_id']
            name = company['name']
            city = company['city_en'] or ''
            website = company['website'] or ''

            logger.info(f"[{i+1}/{len(companies)}] {name} ({city})")

            # Search for email
            result = await enricher.find_email(name, city, website)

            if result:
                # Found email - update database
                await conn.execute("""
                    UPDATE mk_companies
                    SET email = $1,
                        email_source = $2,
                        email_found_at = NOW(),
                        email_search_attempted = TRUE,
                        email_search_at = NOW(),
                        updated_at = NOW()
                    WHERE company_id = $3
                """, result['email'], result['source'], company_id)

                logger.info(f"  ✓ Found: {result['email']} (from {result['source']})")
                found_count += 1
            else:
                # No email found - mark as searched
                await conn.execute("""
                    UPDATE mk_companies
                    SET email_search_attempted = TRUE,
                        email_search_at = NOW(),
                        updated_at = NOW()
                    WHERE company_id = $1
                """, company_id)

                logger.info(f"  ✗ No email found")
                not_found_count += 1

            # Random delay between 3-8 seconds to avoid being blocked
            delay = random.uniform(3, 8)
            await asyncio.sleep(delay)

        logger.info(f"\n{'='*50}")
        logger.info(f"BATCH COMPLETE")
        logger.info(f"  Found: {found_count}")
        logger.info(f"  Not found: {not_found_count}")
        logger.info(f"  Total processed: {len(companies)}")

    finally:
        await enricher.stop()
        await conn.close()


async def run_continuous():
    """Run continuously, processing one company per minute"""

    logger.info("Starting continuous email enrichment...")
    logger.info("Processing 1 company per minute to avoid rate limits")

    while True:
        try:
            await process_batch(batch_size=1)
        except Exception as e:
            logger.error(f"Error in batch: {e}")

        # Wait 1 minute before next company
        await asyncio.sleep(60)


async def get_stats():
    """Get enrichment statistics"""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(email) as with_email,
                COUNT(*) FILTER (WHERE email_search_attempted = TRUE) as searched,
                COUNT(*) FILTER (WHERE email_search_attempted = FALSE OR email_search_attempted IS NULL) as pending
            FROM mk_companies
        """)

        by_source = await conn.fetch("""
            SELECT email_source, COUNT(*) as count
            FROM mk_companies
            WHERE email IS NOT NULL
            GROUP BY email_source
            ORDER BY count DESC
        """)

        print("\n" + "="*50)
        print("EMAIL ENRICHMENT STATISTICS")
        print("="*50)
        print(f"Total companies: {stats['total']:,}")
        print(f"With email: {stats['with_email']:,}")
        print(f"Already searched: {stats['searched']:,}")
        print(f"Pending search: {stats['pending']:,}")
        print(f"\nBy source:")
        for row in by_source:
            print(f"  {row['email_source']}: {row['count']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Email enrichment job')
    parser.add_argument('--batch', type=int, default=50, help='Batch size')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--stats', action='store_true', help='Show statistics')

    args = parser.parse_args()

    if args.stats:
        asyncio.run(get_stats())
    elif args.continuous:
        asyncio.run(run_continuous())
    else:
        asyncio.run(process_batch(args.batch))
