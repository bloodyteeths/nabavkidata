#!/usr/bin/env python3
"""
Scrape Central Registry of Macedonia (crm.com.mk) for company contact data.
Uses Playwright for browser automation and optionally 2captcha for reCAPTCHA.

Usage:
    # Without CAPTCHA solving (limited, may hit blocks)
    python3 scripts/scrape_central_registry.py

    # With 2captcha service
    TWOCAPTCHA_API_KEY=xxx python3 scripts/scrape_central_registry.py

    # Search specific companies
    python3 scripts/scrape_central_registry.py --company="ДИГИТАЛ ОНЕ"
"""
import os
import sys
import asyncio
import asyncpg
import json
import re
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY")
RECAPTCHA_SITE_KEY = "6LcLUNAZAAAAAJ08HQkGbOwh5F2RP5LCpxwQycdS"
CRM_BASE_URL = "https://www.crm.com.mk"

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Please install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)


async def solve_recaptcha_2captcha(page_url: str) -> str:
    """Solve reCAPTCHA using 2captcha service"""
    if not TWOCAPTCHA_API_KEY:
        return None

    try:
        import aiohttp

        # Submit CAPTCHA
        async with aiohttp.ClientSession() as session:
            submit_url = "https://2captcha.com/in.php"
            params = {
                "key": TWOCAPTCHA_API_KEY,
                "method": "userrecaptcha",
                "googlekey": RECAPTCHA_SITE_KEY,
                "pageurl": page_url,
                "json": 1
            }
            async with session.get(submit_url, params=params) as resp:
                data = await resp.json()
                if data.get("status") != 1:
                    print(f"  2captcha submit error: {data}")
                    return None
                captcha_id = data["request"]

            # Poll for result
            result_url = "https://2captcha.com/res.php"
            for _ in range(60):  # Max 2 minutes
                await asyncio.sleep(2)
                params = {
                    "key": TWOCAPTCHA_API_KEY,
                    "action": "get",
                    "id": captcha_id,
                    "json": 1
                }
                async with session.get(result_url, params=params) as resp:
                    data = await resp.json()
                    if data.get("status") == 1:
                        return data["request"]
                    if "CAPCHA_NOT_READY" not in str(data):
                        print(f"  2captcha error: {data}")
                        return None

            return None
    except Exception as e:
        print(f"  2captcha error: {e}")
        return None


async def search_company(page, company_name: str) -> dict:
    """Search for a company in Central Registry"""
    result = {
        'embs': None,
        'name': None,
        'address': None,
        'status': None,
        'activity': None,
        'email': None,
        'phone': None,
        'website': None,
        'found': False
    }

    try:
        # Navigate to basic profile search
        search_url = f"{CRM_BASE_URL}/mk/otvoreni-podatotsi/osnoven-profil-na-registriran-subjekt"
        await page.goto(search_url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(2)

        # Find and fill the name search field
        name_input = await page.query_selector('input[formcontrolname="nazivCtrl"]')
        if name_input:
            await name_input.fill(company_name)
            await asyncio.sleep(1)

            # Click search button
            search_btn = await page.query_selector('button[type="submit"]')
            if search_btn:
                await search_btn.click()
                await asyncio.sleep(3)

                # Check for CAPTCHA
                captcha_visible = await page.query_selector('.recaptcha-checkbox-border')
                if captcha_visible:
                    print(f"  CAPTCHA detected for {company_name[:30]}...")

                    if TWOCAPTCHA_API_KEY:
                        token = await solve_recaptcha_2captcha(search_url)
                        if token:
                            # Inject the token
                            await page.evaluate(f'''
                                document.querySelector('[name="g-recaptcha-response"]').value = "{token}";
                                if (typeof grecaptcha !== 'undefined') {{
                                    grecaptcha.getResponse = function() {{ return "{token}"; }};
                                }}
                            ''')
                            await search_btn.click()
                            await asyncio.sleep(3)
                    else:
                        print("    No 2captcha key, skipping...")
                        return result

                # Wait for results
                await page.wait_for_selector('.search-results, .no-results, .company-card', timeout=10000)

                # Get page content
                content = await page.content()

                # Extract emails from page
                emails = EMAIL_PATTERN.findall(content.lower())
                if emails:
                    # Filter out common invalid emails
                    valid_emails = [e for e in emails if '@' in e and
                                   not any(x in e for x in ['example', 'test', 'noreply', 'crm.org.mk'])]
                    if valid_emails:
                        result['email'] = valid_emails[0]

                # Try to find company details in the results
                company_cards = await page.query_selector_all('.company-card, .search-result-item, tr')
                for card in company_cards:
                    card_text = await card.text_content()
                    if company_name.lower()[:20] in card_text.lower():
                        result['found'] = True
                        result['name'] = company_name

                        # Extract EMBS if available
                        embs_match = re.search(r'\b(\d{7})\b', card_text)
                        if embs_match:
                            result['embs'] = embs_match.group(1)

                        break

        return result

    except Exception as e:
        print(f"  Error searching {company_name[:30]}: {e}")
        return result


async def main():
    print("=" * 70)
    print("CENTRAL REGISTRY SCRAPER")
    print("=" * 70)

    if TWOCAPTCHA_API_KEY:
        print(f"2captcha API key configured: {TWOCAPTCHA_API_KEY[:10]}...")
    else:
        print("⚠️  No 2captcha API key - CAPTCHA will block searches")
        print("   Set TWOCAPTCHA_API_KEY environment variable")

    conn = await asyncpg.connect(DATABASE_URL)

    # Check for specific company search
    specific_company = None
    for arg in sys.argv:
        if arg.startswith('--company='):
            specific_company = arg.split('=', 1)[1]

    if specific_company:
        companies = [{'company_name': specific_company, 'win_count': 0}]
    else:
        # Get companies from tender_bidders not in outreach_leads
        companies = await conn.fetch("""
            SELECT DISTINCT company_name,
                   SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as win_count
            FROM tender_bidders
            WHERE company_name IS NOT NULL
              AND LENGTH(company_name) > 10
              AND company_name NOT LIKE '%-%'
              AND company_name NOT IN (
                  SELECT DISTINCT company_name
                  FROM outreach_leads
                  WHERE company_name IS NOT NULL
              )
            GROUP BY company_name
            ORDER BY win_count DESC
            LIMIT 100
        """)

    print(f"\nFound {len(companies)} companies to search")
    print("Starting search...\n")

    found = 0
    emails_found = 0
    start_time = datetime.now()

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        for i, company in enumerate(companies, 1):
            company_name = company['company_name']
            result = await search_company(page, company_name)

            if result['found']:
                found += 1

                if result['email']:
                    emails_found += 1

                    # Add to outreach_leads
                    await conn.execute("""
                        INSERT INTO outreach_leads (
                            email, company_name, segment, source, quality_score,
                            company_domain, country, raw_data
                        ) VALUES ($1, $2, 'A', 'central_registry', 90, $3, 'North Macedonia', $4)
                        ON CONFLICT (email) DO UPDATE SET
                            segment = CASE WHEN outreach_leads.segment > 'A' THEN 'A' ELSE outreach_leads.segment END,
                            quality_score = GREATEST(outreach_leads.quality_score, EXCLUDED.quality_score),
                            updated_at = NOW()
                    """,
                        result['email'],
                        company_name,
                        result['email'].split('@')[1] if result['email'] else None,
                        json.dumps({'embs': result['embs'], 'search': company_name})
                    )

                    print(f"  ✓ [{i}/{len(companies)}] {company_name[:40]}... -> {result['email']}")

            if i % 10 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"\n  Progress: {i}/{len(companies)} | Found: {found} | Emails: {emails_found} | {i/elapsed*60:.0f}/min\n")

            await asyncio.sleep(2)  # Be respectful

        await browser.close()

    # Final stats
    total_outreach = await conn.fetchval("SELECT COUNT(*) FROM outreach_leads")

    print("\n" + "=" * 70)
    print("SCRAPE COMPLETE")
    print("=" * 70)
    print(f"Companies searched: {len(companies)}")
    print(f"Found in registry: {found}")
    print(f"Emails extracted: {emails_found}")
    print(f"\nTotal outreach leads: {total_outreach}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
