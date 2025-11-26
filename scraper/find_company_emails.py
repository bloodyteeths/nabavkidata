#!/usr/bin/env python3
"""
Find company email addresses by searching the web.

Strategy:
1. Search DuckDuckGo for company name (doesn't block like Google)
2. Visit company website if found
3. Extract email from website
4. Also check Macedonian business directories
"""

import asyncio
import re
import logging
from typing import List, Optional, Dict
from urllib.parse import quote_plus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try httpx first (simpler), fall back to playwright
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from playwright.async_api import async_playwright


class CompanyEmailFinder:
    """Find company emails using web search"""

    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    # Domains to skip (not real company emails)
    SKIP_DOMAINS = [
        'google.com', 'facebook.com', 'twitter.com', 'instagram.com',
        'example.com', 'sentry.io', 'schema.org', 'w3.org',
        'cloudflare.com', 'googleapis.com', 'gstatic.com',
        'youtube.com', 'yahoo.com', 'hotmail.com', 'gmail.com',
        'outlook.com', 'live.com', 'gov.mk'  # Skip gov emails
    ]

    def __init__(self):
        self.browser = None
        self.context = None

    async def __aenter__(self):
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        return self

    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()

    def _extract_emails(self, text: str) -> List[str]:
        """Extract valid emails from text"""
        emails = set()
        matches = re.findall(self.EMAIL_PATTERN, text, re.IGNORECASE)

        for email in matches:
            email = email.lower().strip()
            # Skip invalid domains
            domain = email.split('@')[-1]
            if not any(skip in domain for skip in self.SKIP_DOMAINS):
                emails.add(email)

        return list(emails)

    async def search_duckduckgo(self, company_name: str) -> List[str]:
        """Search DuckDuckGo for company email"""
        page = await self.context.new_page()

        try:
            # Clean company name for search
            clean_name = company_name.replace('ДООЕЛ', '').replace('ДОО', '').replace('АД', '').strip()
            query = f'{clean_name} контакт email'
            url = f'https://duckduckgo.com/html/?q={quote_plus(query)}'

            logger.info(f"Searching DuckDuckGo: {clean_name}")

            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            content = await page.content()
            emails = self._extract_emails(content)

            logger.info(f"  Found {len(emails)} emails from DuckDuckGo")
            return emails[:5]  # Return top 5

        except Exception as e:
            logger.warning(f"  DuckDuckGo search failed: {e}")
            return []
        finally:
            await page.close()

    async def search_company_website(self, company_name: str) -> List[str]:
        """Try to find and visit company website"""
        page = await self.context.new_page()

        try:
            # Search for company website
            clean_name = company_name.replace('ДООЕЛ', '').replace('ДОО', '').replace('АД', '').strip()
            query = f'{clean_name} site:.mk'
            url = f'https://duckduckgo.com/html/?q={quote_plus(query)}'

            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            # Look for .mk domain links in results
            links = await page.query_selector_all('a.result__url')
            mk_sites = []

            for link in links[:5]:
                href = await link.get_attribute('href')
                if href and '.mk' in href:
                    mk_sites.append(href)

            # Visit first .mk site found
            all_emails = []
            for site in mk_sites[:2]:
                try:
                    logger.info(f"  Visiting: {site}")
                    await page.goto(site, wait_until='domcontentloaded', timeout=15000)
                    await page.wait_for_timeout(1000)

                    content = await page.content()
                    emails = self._extract_emails(content)
                    all_emails.extend(emails)

                    if emails:
                        logger.info(f"  Found emails on site: {emails}")
                        break
                except Exception as e:
                    logger.debug(f"  Could not visit {site}: {e}")
                    continue

            return list(set(all_emails))[:5]

        except Exception as e:
            logger.warning(f"  Website search failed: {e}")
            return []
        finally:
            await page.close()

    async def find_email(self, company_name: str) -> Dict:
        """Find email for a company using multiple methods"""
        result = {
            'company_name': company_name,
            'emails_found': [],
            'source': None
        }

        # Method 1: DuckDuckGo search
        emails = await self.search_duckduckgo(company_name)
        if emails:
            result['emails_found'] = emails
            result['source'] = 'duckduckgo'
            return result

        # Method 2: Find and visit company website
        emails = await self.search_company_website(company_name)
        if emails:
            result['emails_found'] = emails
            result['source'] = 'company_website'
            return result

        return result


async def test_finder():
    """Test the email finder with sample companies"""

    # Sample winner companies from our database
    test_companies = [
        'ЈТ БУИЛД ДООЕЛ Тетово',
        'АЛФАНЕТ Делчево',
        'Друштво за производство трговија и услуги МЕДИКА ДОО Скопје',
    ]

    async with CompanyEmailFinder() as finder:
        for company in test_companies:
            print(f"\n{'='*60}")
            print(f"Company: {company}")
            print('='*60)

            result = await finder.find_email(company)

            if result['emails_found']:
                print(f"✓ Emails found: {result['emails_found']}")
                print(f"  Source: {result['source']}")
            else:
                print("✗ No emails found")


if __name__ == "__main__":
    asyncio.run(test_finder())
