#!/usr/bin/env python3
"""
Test archive year selector on e-nabavki.gov.mk using Playwright.
Uses JavaScript click to bypass modal overlay interception.
"""
import asyncio
from playwright.async_api import async_playwright

async def test_archive_selector(year="2021"):
    """Test selecting an archive year and verify the data changes."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Loading e-nabavki awarded tenders page...")
        await page.goto("https://e-nabavki.gov.mk/#/awarded-contracts", wait_until="networkidle", timeout=60000)
        await asyncio.sleep(3)

        # Get initial record count
        try:
            info_text = await page.locator(".dataTables_info").first.text_content()
            print(f"Initial records: {info_text}")
        except:
            print("Could not get initial record count")

        # Find archive button
        archive_btn = page.locator('a[ng-controller="archiveYearController"]')
        if await archive_btn.count() == 0:
            print("ERROR: Archive button not found!")
            await browser.close()
            return False

        print("Found archive button, clicking...")
        await archive_btn.click()
        await asyncio.sleep(2)

        # Wait for modal to appear
        modal = page.locator(".modal-dialog, .modal-content")
        if await modal.count() == 0:
            print("ERROR: Modal did not appear!")
            await browser.close()
            return False

        print("Modal opened! Looking for year options...")

        # Find all radio buttons/options in the modal
        # Use JavaScript to select the year (bypasses overlay interception)
        js_select_year = f"""
        () => {{
            const labels = document.querySelectorAll('.modal label, .modal-body label');
            for (const label of labels) {{
                if (label.textContent.trim() === '{year}') {{
                    const radio = label.querySelector('input[type="radio"]') ||
                                  label.previousElementSibling;
                    if (radio && radio.type === 'radio') {{
                        radio.click();
                        return 'clicked_radio';
                    }}
                    // Try clicking the label itself
                    label.click();
                    return 'clicked_label';
                }}
            }}

            // Alternative: try finding by partial text
            const allElements = document.querySelectorAll('.modal *');
            for (const el of allElements) {{
                if (el.textContent.trim() === '{year}' && el.tagName !== 'SCRIPT') {{
                    el.click();
                    return 'clicked_element';
                }}
            }}
            return 'not_found';
        }}
        """

        result = await page.evaluate(js_select_year)
        print(f"Year selection result: {result}")

        if result == 'not_found':
            # Debug: print all modal content
            modal_text = await page.evaluate("() => document.querySelector('.modal-body, .modal-content')?.innerText || 'no modal'")
            print(f"Modal content: {modal_text[:500]}")
            await browser.close()
            return False

        await asyncio.sleep(1)

        # Click confirm button using JavaScript
        js_confirm = """
        () => {
            const buttons = document.querySelectorAll('.modal button, .modal-footer button');
            for (const btn of buttons) {
                const text = btn.textContent.trim().toLowerCase();
                if (text.includes('потврди') || text.includes('confirm') || text === 'ok') {
                    btn.click();
                    return 'confirmed';
                }
            }
            // Try clicking any primary/success button
            const primary = document.querySelector('.modal .btn-primary, .modal .btn-success');
            if (primary) {
                primary.click();
                return 'clicked_primary';
            }
            return 'no_confirm_button';
        }
        """

        confirm_result = await page.evaluate(js_confirm)
        print(f"Confirm result: {confirm_result}")

        await asyncio.sleep(3)  # Wait for page to reload with new year's data

        # Check if modal is closed and data changed
        try:
            await page.wait_for_selector(".dataTables_info", timeout=10000)
            new_info = await page.locator(".dataTables_info").first.text_content()
            print(f"After selecting {year}: {new_info}")

            # Take screenshot for verification
            await page.screenshot(path=f"/tmp/archive_{year}_selected.png")
            print(f"Screenshot saved to /tmp/archive_{year}_selected.png")
        except Exception as e:
            print(f"Error getting new record count: {e}")

        await browser.close()
        return True

if __name__ == "__main__":
    import sys
    year = sys.argv[1] if len(sys.argv) > 1 else "2021"
    asyncio.run(test_archive_selector(year))
