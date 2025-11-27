#!/usr/bin/env python3
"""
Explore awarded tender pages by clicking through the list
"""
import asyncio
from playwright.async_api import async_playwright

USERNAME = "teknomed"
PASSWORD = "7Jb*Gr=2"

async def explore():
    """Login and explore awarded tender pages"""
    print("=" * 70)
    print("Exploring Awarded Tenders - Clicking Through List")
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

            # Handle modal
            try:
                continue_btn = await page.wait_for_selector('button:has-text("Продолжи")', timeout=5000)
                if continue_btn:
                    await continue_btn.click()
                    await page.wait_for_timeout(2000)
            except:
                pass

            print("   Login successful!")

            # Navigate to left menu -> ОГЛАСИ (Notices)
            print("\n2. Navigating via menu...")

            # Click on ОГЛАСИ menu item
            oglasi_menu = await page.query_selector('li:has-text("ОГЛАСИ")')
            if oglasi_menu:
                await oglasi_menu.click()
                await page.wait_for_timeout(2000)
                print("   Clicked ОГЛАСИ menu")

                # Look for submenu items
                submenu_items = await page.query_selector_all('li:has-text("Склучени договори"), li:has-text("Доделени"), a:has-text("Склучени"), a:has-text("Доделени")')
                print(f"   Found {len(submenu_items)} awarded-related submenu items")

                for item in submenu_items:
                    text = await item.inner_text()
                    print(f"     - {text}")

            # Try the direct URL for awarded/completed notices
            print("\n3. Trying direct URLs for awarded tenders...")

            urls_to_try = [
                'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices/concluded-contract',
                'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices/awarded',
                'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/announcements?category=concluded',
                'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/concluded-contracts',
            ]

            for url in urls_to_try:
                print(f"\n   Trying: {url}")
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(4000)

                # Check if we got a tender list
                tables = await page.query_selector_all('table')
                rows = await page.query_selector_all('tr')
                links = await page.query_selector_all('a[href*="dossie"]')

                print(f"   Tables: {len(tables)}, Rows: {len(rows)}, Dossie links: {len(links)}")

                if len(links) > 0:
                    await page.screenshot(path='/tmp/awarded_list_found.png', full_page=True)
                    html = await page.content()
                    with open('/tmp/awarded_list_found.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    print("   ✓ Found awarded tender list!")

                    # Click on first tender
                    print("\n4. Clicking on first tender link...")
                    first_link = links[0]
                    href = await first_link.get_attribute('href')
                    print(f"   Link href: {href}")

                    await first_link.click()
                    await page.wait_for_timeout(5000)

                    # Save tender detail page
                    await page.screenshot(path='/tmp/tender_detail_clicked.png', full_page=True)
                    detail_html = await page.content()
                    with open('/tmp/tender_detail_clicked.html', 'w', encoding='utf-8') as f:
                        f.write(detail_html)
                    print("   ✓ Tender detail page saved")

                    # Look for bidder/winner info
                    bidder_keywords = ['Понудувач', 'Избран понудувач', 'Победник', 'Добитник',
                                      'Економски оператор', 'Договор со']

                    for kw in bidder_keywords:
                        if kw in detail_html:
                            print(f"   ✓ Found '{kw}' in detail page")

                    # Look for tables with bidder info
                    detail_tables = await page.query_selector_all('table')
                    print(f"\n   Found {len(detail_tables)} tables in detail page")

                    for i, table in enumerate(detail_tables):
                        table_html = await table.inner_html()
                        if any(kw in table_html for kw in ['Понудувач', 'ДОО', 'ДООЕЛ', 'АД']):
                            print(f"   Table {i} may contain bidder data")
                            with open(f'/tmp/bidder_table_{i}.html', 'w', encoding='utf-8') as f:
                                f.write(table_html)

                    # Look for dosie-value labels that might have winner info
                    dosie_values = await page.query_selector_all('label.dosie-value')
                    print(f"\n   Found {len(dosie_values)} dosie-value labels")

                    for i, label in enumerate(dosie_values[:20]):
                        text = await label.inner_text()
                        if text.strip():
                            print(f"     {i}: {text[:60]}...")

                    break

            # Also try clicking through the main menu structure
            print("\n5. Exploring menu structure...")

            # Look for all clickable menu items
            menu_items = await page.query_selector_all('li.hasChildren, li[ng-click], a[ng-click]')
            print(f"   Found {len(menu_items)} menu items")

            for i, item in enumerate(menu_items[:10]):
                try:
                    text = await item.inner_text()
                    text = text.strip().split('\n')[0]  # First line only
                    if text:
                        print(f"     {i}: {text[:50]}")
                except:
                    pass

            # Save cookies
            cookies = await context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            with open('/tmp/enabavki_cookies.txt', 'w') as f:
                f.write(cookie_str)
            print(f"\n6. Saved {len(cookies)} cookies")

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path='/tmp/explore_error.png')

        finally:
            await browser.close()

    print("\n" + "=" * 70)
    print("Done - check /tmp/ for screenshots")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(explore())
