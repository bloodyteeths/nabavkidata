#!/usr/bin/env python3
"""
Analyze tender detail page structure to understand field extraction.
"""
import asyncio
from playwright.async_api import async_playwright

async def analyze_tender_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Test with an awarded tender
        url = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/53e296c7-fc8b-46e6-97d3-48f4ea309acf"
        print(f"Loading: {url}")

        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Check what we got
        html = await page.content()
        print(f"Page size: {len(html)} bytes")

        # Look for any dosie-value elements
        dosie_count = await page.evaluate("() => document.querySelectorAll('.dosie-value').length")
        print(f"dosie-value elements: {dosie_count}")

        # Look for any label-for elements
        label_for_count = await page.evaluate("() => document.querySelectorAll('label[label-for]').length")
        print(f"label-for elements: {label_for_count}")

        # Get all label-for attributes and their values
        print("=" * 80)
        print("ALL LABEL-FOR ATTRIBUTES AND VALUES")
        print("=" * 80)

        results = await page.evaluate("""() => {
            const labels = document.querySelectorAll('label[label-for]');
            const data = [];
            for (let label of labels) {
                const labelFor = label.getAttribute('label-for') || '';
                const labelText = label.innerText.trim();

                let value = null;
                let next = label.nextElementSibling;
                while(next) {
                    if(next.classList && next.classList.contains('dosie-value')) {
                        value = next.innerText.trim().substring(0, 100);
                        break;
                    }
                    next = next.nextElementSibling;
                }

                if (value && value.length > 0) {
                    data.push([labelFor, labelText, value]);
                }
            }
            return data;
        }""")

        for item in results:
            print(f"[{item[0]}] {item[1]} => {item[2]}")

        # Also get all dosie-value elements
        print("\n" + "=" * 80)
        print("ALL DOSIE-VALUE ELEMENTS")
        print("=" * 80)

        values = await page.evaluate("""() => {
            const elems = document.querySelectorAll('.dosie-value');
            return Array.from(elems).slice(0, 50).map(e => {
                const text = e.innerText.trim().substring(0, 80);
                // Try to get preceding label
                let prevLabel = '';
                let prev = e.previousElementSibling;
                while(prev) {
                    if(prev.tagName === 'LABEL' && prev.getAttribute('label-for')) {
                        prevLabel = prev.innerText.trim();
                        break;
                    }
                    prev = prev.previousElementSibling;
                }
                return [prevLabel, text];
            });
        }""")

        for v in values:
            if v[1]:
                print(f"  [{v[0] or 'NO LABEL'}]: {v[1]}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_tender_page())
