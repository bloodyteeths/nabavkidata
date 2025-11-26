#!/usr/bin/env python3
"""
Debug script to see what's actually on a tender detail page
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_tender_page():
    url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/99b6f70f-e4b0-4001-86be-b31b5e062d01'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Loading: {url}")
        await page.goto(url, wait_until='networkidle', timeout=60000)

        # Wait a bit for Angular to render
        await page.wait_for_timeout(5000)

        print("\n" + "="*80)
        print("CHECKING FOR COMMON SELECTORS")
        print("="*80)

        # Check for various selectors
        selectors_to_check = [
            'label.dosie-value',
            'label.dossie-value',
            'label[class*="value"]',
            'div.dosie-value',
            'div.dossie-value',
            'div[class*="value"]',
            'label[label-for]',
            'table',
            'div.tender-detail',
            'div.ng-scope',
        ]

        for selector in selectors_to_check:
            try:
                elements = await page.query_selector_all(selector)
                print(f"✓ Found {len(elements)} elements with selector: {selector}")
                if len(elements) > 0 and len(elements) < 10:
                    for i, elem in enumerate(elements[:3]):
                        text = await elem.text_content()
                        print(f"  [{i}] {text[:100] if text else 'NO TEXT'}")
            except Exception as e:
                print(f"✗ Error with selector {selector}: {e}")

        # Get all labels
        print("\n" + "="*80)
        print("ALL LABELS ON PAGE")
        print("="*80)
        labels = await page.query_selector_all('label')
        print(f"Total labels found: {len(labels)}")
        for i, label in enumerate(labels[:20]):  # Show first 20
            text = await label.text_content()
            class_name = await label.get_attribute('class')
            label_for = await label.get_attribute('label-for')
            print(f"[{i}] class='{class_name}' label-for='{label_for}' text='{text[:50] if text else 'NO TEXT'}'")

        # Get page HTML
        print("\n" + "="*80)
        print("SAMPLE HTML (first 2000 chars)")
        print("="*80)
        html = await page.content()
        print(html[:2000])

        # Save full HTML for inspection
        with open('debug_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("\nFull HTML saved to: debug_page.html")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(debug_tender_page())
