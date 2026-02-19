#!/usr/bin/env python3
"""
Find company emails from Central Registry of Macedonia (crm.com.mk)
Uses the company names from our winner database to look up their registration info
"""

import asyncio
import asyncpg
import os
import logging
import re
from playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Email regex
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

async def search_company_crm(page, company_name: str) -> dict:
    """Search for company on crm.com.mk and extract contact info"""
    result = {
        'company_name': company_name,
        'email': None,
        'phone': None,
        'website': None,
        'address': None,
        'tax_id': None,
    }

    try:
        # Go to CRM search page
        await page.goto('https://www.crm.com.mk/DS/default.aspx?lang=mk', timeout=30000)
        await page.wait_for_timeout(2000)

        # Extract short company name (e.g., "БИОТЕК" from full name)
        # Try to find the main company name without legal suffixes
        short_name = company_name
        # Remove common suffixes
        for suffix in ['ДООЕЛ', 'ДОО', 'АД', 'експорт-импорт', 'увоз-извоз', 'Скопје', 'Тетово', 'Битола', 'Охрид', 'Струмица']:
            short_name = short_name.replace(suffix, '')
        short_name = short_name.strip()

        # Look for search input
        search_input = await page.query_selector('input[type="text"]')
        if search_input:
            await search_input.fill(short_name[:30])  # Limit search term
            await page.wait_for_timeout(1000)

            # Try to submit search
            search_btn = await page.query_selector('input[type="submit"], button[type="submit"]')
            if search_btn:
                await search_btn.click()
                await page.wait_for_timeout(3000)

        # Get page content and search for emails
        content = await page.content()

        # Find emails in page
        emails = EMAIL_PATTERN.findall(content)
        valid_emails = [e for e in emails if not e.endswith('.gov.mk') and 'crm.com.mk' not in e]
        if valid_emails:
            result['email'] = valid_emails[0]
            logger.info(f"  Found email: {result['email']}")

    except Exception as e:
        logger.error(f"  Error searching CRM: {e}")

    return result


async def search_company_google(page, company_name: str) -> dict:
    """Search for company email via Google"""
    result = {
        'company_name': company_name,
        'email': None,
        'website': None,
    }

    try:
        # Extract key company name
        # e.g., "Друштво за промет и услуги БИОТЕК ДОО експорт-импорт Скопје" -> "БИОТЕК"
        words = company_name.split()
        # Find words in ALL CAPS (likely the company name)
        key_words = [w for w in words if w.isupper() and len(w) > 2]
        if not key_words:
            # Try to find capitalized words
            key_words = [w for w in words if w[0].isupper() and len(w) > 3]

        search_term = ' '.join(key_words[:2]) if key_words else company_name[:30]
        search_query = f"{search_term} Macedonia email contact"

        logger.info(f"  Searching Google for: {search_query}")

        # Use DuckDuckGo (less likely to block)
        await page.goto(f'https://duckduckgo.com/?q={search_query}', timeout=30000)
        await page.wait_for_timeout(3000)

        # Get page content
        content = await page.content()

        # Find emails in search results
        emails = EMAIL_PATTERN.findall(content)
        # Filter out common non-company emails
        valid_emails = [
            e for e in emails
            if not any(x in e.lower() for x in ['gov.mk', 'duckduckgo', 'google', 'example', 'email@'])
        ]

        if valid_emails:
            result['email'] = valid_emails[0]
            logger.info(f"  Found email via search: {result['email']}")

    except Exception as e:
        logger.error(f"  Error in Google search: {e}")

    return result


async def main():
    """Main function to find company emails"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not set")
        return

    database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

    # Connect to database
    conn = await asyncpg.connect(database_url)
    logger.info("Connected to database")

    # Get winner companies without emails
    winners = await conn.fetch("""
        SELECT DISTINCT c.entity_name, c.contact_id
        FROM contacts c
        WHERE c.contact_type = 'winner'
          AND (c.email IS NULL OR c.email = '')
        ORDER BY c.entity_name
        LIMIT 20
    """)

    logger.info(f"Found {len(winners)} winner companies without emails")

    if not winners:
        logger.info("No companies to process")
        await conn.close()
        return

    # Launch browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        found_count = 0

        for i, winner in enumerate(winners, 1):
            company_name = winner['entity_name']
            contact_id = winner['contact_id']

            logger.info(f"[{i}/{len(winners)}] Processing: {company_name[:60]}...")

            # Try CRM first
            result = await search_company_crm(page, company_name)

            # If no email, try Google search
            if not result.get('email'):
                result = await search_company_google(page, company_name)

            # Update database if email found
            if result.get('email'):
                await conn.execute("""
                    UPDATE contacts
                    SET email = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE contact_id = $2
                """, result['email'], contact_id)
                logger.info(f"  ✓ Updated contact with email: {result['email']}")
                found_count += 1
            else:
                logger.info(f"  ✗ No email found")

            # Rate limit
            await asyncio.sleep(2)

        await browser.close()

    await conn.close()

    logger.info("=" * 60)
    logger.info(f"COMPLETE: Found {found_count}/{len(winners)} company emails")
    logger.info("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
