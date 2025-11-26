#!/usr/bin/env python3
"""
Test script to investigate the InstitutionGridData.aspx page structure
for awarded tenders (contracts).
"""

import asyncio
from playwright.async_api import async_playwright

async def test_awarded_page():
    """Test the awarded tenders page (InstitutionGridData.aspx)"""

    urls_to_test = [
        "https://e-nabavki.gov.mk/InstitutionGridData.aspx#/ciContractsGrid/",
        "https://e-nabavki.gov.mk/InstitutionGridData.aspx#/ciContractsGrid",
        "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/contracts",
        "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices",  # Working reference
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="mk-MK"
        )

        for url in urls_to_test:
            print(f"\n{'='*60}")
            print(f"Testing: {url}")
            print("="*60)

            page = await context.new_page()

            try:
                # Navigate with longer timeout
                await page.goto(url, wait_until="networkidle", timeout=90000)
                await page.wait_for_timeout(5000)  # Extra wait for Angular

                # Get page title and current URL
                title = await page.title()
                current_url = page.url
                print(f"Title: {title}")
                print(f"Current URL: {current_url}")

                # Check for common table selectors
                selectors_to_check = [
                    ("table#notices-grid tbody tr", "Notices grid rows"),
                    ("table tbody tr", "Generic table rows"),
                    (".RowStyle", "RowStyle elements"),
                    (".AltRowStyle", "AltRowStyle elements"),
                    ("[ng-repeat]", "Angular ng-repeat"),
                    ("table.dataTable", "DataTable"),
                    (".dataTables_wrapper", "DataTables wrapper"),
                    ("table", "Any tables"),
                    ("tr", "Any table rows"),
                    ("a[href*='dossie']", "Dossie links"),
                    ("a[href*='contract']", "Contract links"),
                    ("a[href*='Contract']", "Contract links (capital)"),
                ]

                for selector, description in selectors_to_check:
                    try:
                        elements = await page.query_selector_all(selector)
                        count = len(elements)
                        if count > 0:
                            print(f"✓ {description} ({selector}): {count}")
                            # Get first element text if available
                            if count <= 5:
                                for i, el in enumerate(elements[:3]):
                                    text = await el.inner_text()
                                    if text:
                                        print(f"    [{i}]: {text[:100]}...")
                    except Exception as e:
                        print(f"✗ {description}: Error - {e}")

                # Check page content for keywords
                content = await page.content()
                keywords = ['договор', 'contract', 'tender', 'набавк', 'понуд', 'оглас']
                print(f"\nContent analysis (length: {len(content)}):")
                for kw in keywords:
                    count = content.lower().count(kw.lower())
                    if count > 0:
                        print(f"  '{kw}': {count} occurrences")

                # Check for any visible error messages
                error_selectors = [
                    ".error",
                    ".alert-danger",
                    "[class*='error']",
                    "[class*='Error']",
                ]
                for es in error_selectors:
                    try:
                        error_els = await page.query_selector_all(es)
                        if error_els:
                            for err in error_els[:2]:
                                txt = await err.inner_text()
                                if txt.strip():
                                    print(f"⚠ Error element: {txt[:200]}")
                    except:
                        pass

                # Take screenshot
                screenshot_name = url.replace("https://", "").replace("/", "_").replace("#", "_").replace(":", "")[:50]
                await page.screenshot(path=f"/tmp/awarded_{screenshot_name}.png")
                print(f"Screenshot saved to: /tmp/awarded_{screenshot_name}.png")

            except Exception as e:
                print(f"❌ Error: {e}")

            finally:
                await page.close()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_awarded_page())
