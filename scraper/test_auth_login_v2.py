#!/usr/bin/env python3
"""
Test authenticated login to e-nabavki.gov.mk - Version 2
Verifies credentials work and explores bidder/lot data access
"""
import asyncio
import os
from playwright.async_api import async_playwright

# Credentials
USERNAME = "teknomed"
PASSWORD = "" + os.getenv("NABAVKI_PASSWORD", "") + ""

async def test_login():
    """Test login to e-nabavki.gov.mk and explore tender data"""
    print("=" * 60)
    print("Testing e-nabavki.gov.mk Authentication - v2")
    print("=" * 60)

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            # Navigate to login page
            print("\n1. Navigating to e-nabavki.gov.mk...")
            await page.goto('https://e-nabavki.gov.mk', wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)

            # Enter credentials
            print("\n2. Entering credentials...")
            username_field = await page.query_selector('input[placeholder*="Корисничко"]')
            password_field = await page.query_selector('input[type="password"]')

            if username_field and password_field:
                await username_field.fill(USERNAME)
                await password_field.fill(PASSWORD)
                print("   Credentials entered")
            else:
                print("   ERROR: Login fields not found")
                return

            # Click login button
            submit = await page.query_selector('input[type="submit"]')
            if submit:
                await submit.click()
                await page.wait_for_timeout(5000)
                print("   Login submitted")

            # Handle the modal popup - click "Продолжи" (Continue)
            print("\n3. Handling modal popup...")
            try:
                continue_btn = await page.wait_for_selector('button:has-text("Продолжи")', timeout=5000)
                if continue_btn:
                    await continue_btn.click()
                    await page.wait_for_timeout(2000)
                    print("   Modal dismissed")
            except:
                print("   No modal found or already dismissed")

            # Verify login by checking for logout button or user menu
            print("\n4. Verifying login status...")
            html = await page.content()

            if 'Одјава' in html or 'logout' in html.lower():
                print("   LOGIN SUCCESSFUL!")
            else:
                # Check for user-specific elements
                logged_in_indicators = ['teknomed', 'Профил', 'Мои огласи', 'Мои понуди']
                for ind in logged_in_indicators:
                    if ind in html:
                        print(f"   LOGIN SUCCESSFUL! Found '{ind}' in page")
                        break

            await page.screenshot(path='/tmp/enabavki_logged_in.png')
            print("   Screenshot saved to /tmp/enabavki_logged_in.png")

            # Navigate to a known awarded tender to see bidder data
            print("\n5. Navigating to awarded tender detail page...")
            # Try several known awarded tenders
            test_tenders = [
                ('21492', '2025'),
                ('21000', '2025'),
                ('20500', '2025'),
                ('19000', '2024'),
            ]

            for tender_num, tender_year in test_tenders:
                tender_url = f'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{tender_num}/{tender_year}'
                print(f"\n   Trying tender: {tender_num}/{tender_year}")
                await page.goto(tender_url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(4000)

                html = await page.content()

                # Check for bidder-related content
                bidder_keywords = ['Понудувач', 'Понуди', 'Економски оператор', 'Победник', 'Избран']
                lot_keywords = ['Лот', 'Дел', 'Партија']

                found_bidders = any(kw in html for kw in bidder_keywords)
                found_lots = any(kw in html for kw in lot_keywords)

                print(f"      Bidder info present: {found_bidders}")
                print(f"      Lot info present: {found_lots}")

                # Look for specific tabs/sections that contain bidder data
                tabs = await page.query_selector_all('a[ng-click*="tab"]')
                print(f"      Found {len(tabs)} tabs")

                for tab in tabs:
                    tab_text = await tab.inner_text()
                    if tab_text.strip():
                        print(f"        - {tab_text.strip()}")

                # Try to find and click on "Понуди" (Bids) or similar tab
                bid_tabs = await page.query_selector_all('a:has-text("Понуди"), a:has-text("Избрани понудувачи"), a:has-text("Резултати")')
                for bid_tab in bid_tabs:
                    tab_text = await bid_tab.inner_text()
                    print(f"\n   Found bid-related tab: '{tab_text}'")
                    try:
                        await bid_tab.click()
                        await page.wait_for_timeout(2000)
                        print("      Clicked on tab")

                        # Take screenshot of bid data
                        await page.screenshot(path=f'/tmp/enabavki_bids_{tender_num}.png', full_page=True)
                        print(f"      Screenshot saved to /tmp/enabavki_bids_{tender_num}.png")

                        # Get the HTML content for analysis
                        tab_html = await page.content()
                        with open(f'/tmp/enabavki_bids_{tender_num}.html', 'w', encoding='utf-8') as f:
                            f.write(tab_html)
                        print(f"      HTML saved to /tmp/enabavki_bids_{tender_num}.html")

                        # Look for table data
                        tables = await page.query_selector_all('table')
                        print(f"      Found {len(tables)} tables in bid section")

                        # Look for bidder names
                        bidder_cells = await page.query_selector_all('td:has-text("ДООЕЛ"), td:has-text("ДОО"), td:has-text("АД")')
                        if bidder_cells:
                            print(f"      Found {len(bidder_cells)} potential bidder entries")
                            for i, cell in enumerate(bidder_cells[:5]):  # Show first 5
                                cell_text = await cell.inner_text()
                                print(f"        {i+1}. {cell_text[:60]}...")

                        break
                    except Exception as e:
                        print(f"      Error clicking tab: {e}")

                # If we found bidder data, analyze one tender in detail
                if found_bidders:
                    print(f"\n6. Analyzing bidder data structure for tender {tender_num}/{tender_year}...")

                    # Look for specific bidder data elements
                    selectors_to_check = [
                        ('table.bidders-table', 'Bidders table'),
                        ('div[ng-repeat*="ponuda"]', 'Bid entries'),
                        ('div[ng-repeat*="bidder"]', 'Bidder entries'),
                        ('tr[ng-repeat]', 'Table rows with ng-repeat'),
                        ('.winner', 'Winner element'),
                        ('[ng-if*="winner"]', 'Winner ng-if element'),
                    ]

                    for selector, desc in selectors_to_check:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            print(f"      Found {len(elements)} {desc}")

                    break  # Stop after finding a tender with bidder data

            # Get and save cookies for spider use
            cookies = await context.cookies()
            print(f"\n7. Captured {len(cookies)} cookies")

            # Save cookies for spider
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            with open('/tmp/enabavki_cookies.txt', 'w') as f:
                f.write(cookie_str)
            print("   Cookies saved to /tmp/enabavki_cookies.txt")

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path='/tmp/enabavki_error.png')

        finally:
            await browser.close()

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_login())
