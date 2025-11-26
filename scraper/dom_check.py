#!/usr/bin/env python3
"""Check DOM structure of tender page"""
import asyncio
from playwright.async_api import async_playwright

async def check_dom():
    url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/74056a47-3858-46ee-b222-6e7a863a9bd8/1'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        # Check different selectors
        print("Checking selectors:")
        selectors = {
            'label.dosie-label': 'label.dosie-label',
            'label.dosieLabel': 'label.dosieLabel',
            'label[class*="dosie"]': 'label[class*="dosie"]',
            'label': 'label',
            'dt': 'dt',
            'th': 'th',
            '.col-md-4': '.col-md-4',
            'div.row': 'div.row',
        }

        for name, sel in selectors.items():
            count = len(await page.query_selector_all(sel))
            print(f"  {name}: {count}")

        # Get first 10 labels with text
        print("\nFirst 10 labels:")
        labels = await page.query_selector_all('label')
        for i, lab in enumerate(labels[:10]):
            text = await lab.inner_text()
            cls = await lab.get_attribute('class')
            print(f"  [{cls}] {text[:50]}")

        # Check for Angular ng-bind
        print("\nAngular elements:")
        ng_elements = await page.query_selector_all('[ng-bind], [ng-model]')
        print(f"  ng-bind/ng-model elements: {len(ng_elements)}")

        for i, el in enumerate(ng_elements[:5]):
            text = await el.inner_text()
            ng_bind = await el.get_attribute('ng-bind')
            print(f"  [{ng_bind}] {text[:50] if text else 'empty'}")

        # Get all visible text with "Број" or "Оглас"
        print("\nSearching for tender number:")
        content = await page.content()
        if 'Број на оглас' in content:
            print("  Found 'Број на оглас' in content")
            # Find the element
            broj_el = await page.query_selector('//*[contains(text(), "Број на оглас")]')
            if broj_el:
                parent = await broj_el.evaluate('el => el.parentElement.outerHTML.substring(0, 300)')
                print(f"  Parent HTML: {parent}")

        await browser.close()

asyncio.run(check_dom())
