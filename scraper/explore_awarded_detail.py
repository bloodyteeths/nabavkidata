#!/usr/bin/env python3
"""
Explore awarded tender detail page structure to understand bidder table selectors
"""
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

USERNAME = "teknomed"
PASSWORD = "7Jb*Gr=2"

async def explore_awarded_detail():
    """Login and explore specific awarded tender detail page"""
    print("=" * 70)
    print("Exploring Awarded Tender Detail Page Structure")
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
            await page.goto('https://e-nabavki.gov.mk', wait_until='networkidle', timeout=60000)
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

            # Go to awarded tenders list (contracts)
            print("\n2. Navigating to awarded tenders list...")
            await page.goto('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts/0',
                          wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(5000)

            # Screenshot the list
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            await page.screenshot(path=f'/tmp/nabavki_contracts_list_{timestamp}.png', full_page=True)

            # Look for contract notice links (dossie-acpp)
            acpp_links = await page.query_selector_all('a[href*="dossie-acpp"]')
            print(f"   Found {len(acpp_links)} dossie-acpp links")

            if acpp_links:
                # Get first contract detail
                first_link = acpp_links[0]
                href = await first_link.get_attribute('href')
                print(f"   First link href: {href}")

                await first_link.click()
                await page.wait_for_timeout(5000)

                # Screenshot detail page
                await page.screenshot(path=f'/tmp/nabavki_detail_awarded_0_{timestamp}.png', full_page=True)

                # Save HTML for analysis
                html = await page.content()
                with open(f'/tmp/nabavki_detail_awarded_0_{timestamp}.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"   Saved detail page HTML")

                # Now analyze the page structure for bidders
                print("\n3. Analyzing page structure for bidder data...")

                # Look for section headers
                section_headers = await page.query_selector_all('h3, h4, .dosie-group-header, label.dosie-label')
                print(f"\n   Section headers found: {len(section_headers)}")

                for i, header in enumerate(section_headers[:30]):
                    text = await header.inner_text()
                    if text.strip():
                        # Look for bidder/contract related sections
                        text_clean = text.strip()[:80]
                        if any(kw in text_clean for kw in ['Понудувач', 'Договор', 'Известување', 'ДЕЛ', 'носител']):
                            print(f"   *** {i}: {text_clean}")
                        else:
                            print(f"       {i}: {text_clean}")

                # Look for tables
                tables = await page.query_selector_all('table')
                print(f"\n   Tables found: {len(tables)}")

                for i, table in enumerate(tables):
                    table_html = await table.inner_html()

                    # Check if this table has bidder-related content
                    bidder_keywords = ['Понудувач', 'носител', 'Договор', 'ДОО', 'ДООЕЛ', 'Вредност', 'склучен']
                    has_bidder_content = any(kw in table_html for kw in bidder_keywords)

                    if has_bidder_content:
                        print(f"\n   *** TABLE {i} - HAS BIDDER CONTENT ***")

                        # Get headers
                        headers = await table.query_selector_all('th')
                        header_texts = []
                        for th in headers:
                            th_text = await th.inner_text()
                            header_texts.append(th_text.strip()[:50])
                        print(f"       Headers: {header_texts}")

                        # Get sample rows
                        rows = await table.query_selector_all('tbody tr')
                        print(f"       Rows: {len(rows)}")

                        for j, row in enumerate(rows[:3]):
                            cells = await row.query_selector_all('td')
                            cell_texts = []
                            for cell in cells:
                                cell_text = await cell.inner_text()
                                cell_texts.append(cell_text.strip()[:40])
                            print(f"       Row {j}: {cell_texts}")

                        # Save this specific table
                        with open(f'/tmp/bidder_table_{i}_{timestamp}.html', 'w', encoding='utf-8') as f:
                            f.write(table_html)

                # Look for dosie-value labels with bidder info
                print("\n4. Looking for dosie-value labels with bidder info...")

                dosie_values = await page.query_selector_all('label.dosie-value')
                for i, label in enumerate(dosie_values):
                    text = await label.inner_text()
                    text_clean = text.strip()

                    # Company name indicators
                    if any(kw in text_clean for kw in ['ДОО', 'ДООЕЛ', 'АД', 'Друштво', 'ДПТУ']):
                        # Get preceding label
                        parent = await label.evaluate_handle('(el) => el.parentElement')
                        prev_label = await parent.evaluate('(el) => el.querySelector("label.dosie-label")?.innerText || ""')
                        print(f"   {i}: [{prev_label[:30]}] = {text_clean[:60]}")

                # Check for ng-repeat elements with bidder data
                print("\n5. Looking for ng-repeat bidder elements...")
                ng_repeats = await page.query_selector_all('[ng-repeat]')
                for elem in ng_repeats:
                    ng_attr = await elem.get_attribute('ng-repeat')
                    if ng_attr and any(kw in ng_attr.lower() for kw in ['contract', 'bidder', 'ponudu', 'izvestuvan']):
                        text = await elem.inner_text()
                        print(f"   ng-repeat='{ng_attr}' -> {text[:100]}...")

                # Look for specific contract award sections
                print("\n6. Looking for contract award notification section...")

                # Section V - Contract Award Notices
                section_v = await page.query_selector('div:has-text("ДЕЛ V: ИЗВЕСТУВАЊА ЗА СКЛУЧЕН ДОГОВОР")')
                if section_v:
                    print("   Found Section V!")
                    section_v_html = await section_v.inner_html()
                    with open(f'/tmp/section_v_{timestamp}.html', 'w', encoding='utf-8') as f:
                        f.write(section_v_html)

                # Go back and try another tender
                print("\n7. Trying a few more awarded tenders...")

            else:
                # Try the realized-contract URL
                print("\n   No dossie-acpp links found, trying realized-contract...")
                await page.goto('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/realized-contract',
                              wait_until='networkidle', timeout=60000)
                await page.wait_for_timeout(5000)
                await page.screenshot(path=f'/tmp/nabavki_realized_{timestamp}.png', full_page=True)

                realized_links = await page.query_selector_all('a[href*="dossie"]')
                print(f"   Found {len(realized_links)} dossie links in realized contracts")

            # Save cookies for later use
            cookies = await context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            with open('/tmp/enabavki_cookies_awarded.txt', 'w') as f:
                f.write(cookie_str)
            print(f"\n8. Saved {len(cookies)} cookies")

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path='/tmp/explore_awarded_error.png')

        finally:
            await browser.close()

    print("\n" + "=" * 70)
    print("Done - check /tmp/ for screenshots and HTML files")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(explore_awarded_detail())
