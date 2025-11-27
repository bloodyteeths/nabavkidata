#!/usr/bin/env python3
"""
Explore awarded tender pages to understand bidder/lot data structure
"""
import asyncio
from playwright.async_api import async_playwright

USERNAME = "teknomed"
PASSWORD = "7Jb*Gr=2"

async def explore_awarded_tender():
    """Login and explore awarded tender pages to understand data structure"""
    print("=" * 70)
    print("Exploring Awarded Tender Pages for Bidder/Lot Data")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            # Login
            print("\n1. Logging in...")
            await page.goto('https://e-nabavki.gov.mk', wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)

            username_field = await page.query_selector('input[placeholder*="Корисничко"]')
            password_field = await page.query_selector('input[type="password"]')

            if username_field and password_field:
                await username_field.fill(USERNAME)
                await password_field.fill(PASSWORD)
                submit = await page.query_selector('input[type="submit"]')
                if submit:
                    await submit.click()
                    await page.wait_for_timeout(5000)
                    print("   Login submitted")

            # Handle modal
            try:
                continue_btn = await page.wait_for_selector('button:has-text("Продолжи")', timeout=5000)
                if continue_btn:
                    await continue_btn.click()
                    await page.wait_for_timeout(2000)
            except:
                pass

            print("   Login successful!")

            # Navigate to awarded tenders list
            print("\n2. Navigating to awarded tenders list...")
            await page.goto('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/awarded-tenders',
                          wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(5000)

            await page.screenshot(path='/tmp/awarded_list.png', full_page=True)
            print("   Screenshot saved: /tmp/awarded_list.png")

            # Get some awarded tender IDs from the list
            html = await page.content()
            with open('/tmp/awarded_list.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("   HTML saved: /tmp/awarded_list.html")

            # Try to find tender links
            tender_links = await page.query_selector_all('a[href*="dossie"]')
            print(f"   Found {len(tender_links)} tender links")

            # Also look for rows in the table
            table_rows = await page.query_selector_all('tr[ng-repeat]')
            print(f"   Found {len(table_rows)} table rows")

            # Navigate to specific awarded tender detail pages
            test_tenders = [
                ('21492', '2025'),  # Recent
                ('21000', '2025'),
                ('20800', '2025'),
                ('19500', '2024'),
                ('18910', '2025'),  # Known tender
            ]

            for tender_num, tender_year in test_tenders:
                print(f"\n3. Exploring tender {tender_num}/{tender_year}...")
                tender_url = f'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{tender_num}/{tender_year}'
                await page.goto(tender_url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(4000)

                # Take full page screenshot
                await page.screenshot(path=f'/tmp/tender_{tender_num}_main.png', full_page=True)
                print(f"   Main page screenshot saved")

                # Save HTML for analysis
                html = await page.content()
                with open(f'/tmp/tender_{tender_num}.html', 'w', encoding='utf-8') as f:
                    f.write(html)

                # Look for tabs
                tabs = await page.query_selector_all('a[ng-click], li[ng-click], button[ng-click]')
                tab_texts = []
                for tab in tabs:
                    text = await tab.inner_text()
                    if text.strip():
                        tab_texts.append(text.strip())

                print(f"   Found tabs/buttons: {tab_texts[:10]}")  # First 10

                # Look for specific bidder-related sections
                bidder_keywords = ['Понудувач', 'Понуди', 'Резултати', 'Избран', 'Победник',
                                  'Економски оператор', 'Договор', 'Лот', 'Дел']

                for keyword in bidder_keywords:
                    if keyword in html:
                        print(f"   ✓ Found '{keyword}' in page")

                # Try to find and click on different tabs
                tab_selectors = [
                    ('a:has-text("Понуди")', 'Bids tab'),
                    ('a:has-text("Резултати")', 'Results tab'),
                    ('a:has-text("Договор")', 'Contract tab'),
                    ('a:has-text("Одлука")', 'Decision tab'),
                    ('a:has-text("Избрани")', 'Selected tab'),
                    ('a:has-text("Лотови")', 'Lots tab'),
                    ('li:has-text("Понуди")', 'Bids li'),
                    ('li:has-text("Резултати")', 'Results li'),
                ]

                for selector, desc in tab_selectors:
                    try:
                        tab = await page.query_selector(selector)
                        if tab:
                            visible = await tab.is_visible()
                            if visible:
                                print(f"\n   Clicking on {desc}...")
                                await tab.click()
                                await page.wait_for_timeout(3000)

                                await page.screenshot(path=f'/tmp/tender_{tender_num}_{desc.replace(" ", "_")}.png', full_page=True)
                                print(f"   Screenshot saved for {desc}")

                                # Save HTML
                                tab_html = await page.content()
                                with open(f'/tmp/tender_{tender_num}_{desc.replace(" ", "_")}.html', 'w', encoding='utf-8') as f:
                                    f.write(tab_html)

                                # Look for bidder data in tables
                                tables = await page.query_selector_all('table')
                                print(f"   Found {len(tables)} tables")

                                # Look for company names
                                company_patterns = ['ДООЕЛ', 'ДОО', 'АД', 'ДПТУ']
                                for pattern in company_patterns:
                                    cells = await page.query_selector_all(f'td:has-text("{pattern}")')
                                    if cells:
                                        print(f"   Found {len(cells)} cells with '{pattern}'")
                                        for i, cell in enumerate(cells[:3]):
                                            text = await cell.inner_text()
                                            print(f"      {i+1}. {text[:80]}...")
                    except Exception as e:
                        pass  # Tab not found or not clickable

                # Also check for ng-repeat patterns that might contain bidder data
                ng_repeats = await page.query_selector_all('[ng-repeat]')
                print(f"\n   Found {len(ng_repeats)} ng-repeat elements")

                for i, elem in enumerate(ng_repeats[:5]):
                    ng_attr = await elem.get_attribute('ng-repeat')
                    text = await elem.inner_text()
                    print(f"   {i+1}. ng-repeat='{ng_attr}' -> {text[:50]}...")

                # Check if this tender has bidder/winner info - if yes, stop exploring more
                if 'Победник' in html or 'Избран понудувач' in html:
                    print(f"\n   ✓ This tender has winner info - good candidate for extraction!")
                    break

            # Save cookies
            cookies = await context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            with open('/tmp/enabavki_cookies.txt', 'w') as f:
                f.write(cookie_str)
            print(f"\n4. Saved {len(cookies)} cookies to /tmp/enabavki_cookies.txt")

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path='/tmp/explore_error.png')

        finally:
            await browser.close()

    print("\n" + "=" * 70)
    print("Exploration Complete - Check /tmp/ for screenshots and HTML files")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(explore_awarded_tender())
