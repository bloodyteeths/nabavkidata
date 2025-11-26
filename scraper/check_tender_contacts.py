#!/usr/bin/env python3
"""Check what contact info is available on tender detail pages"""

import asyncio
from playwright.async_api import async_playwright

async def check_all_labels():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/feca8208-fe37-4b07-9f6c-cf6c32102a4a'
        print(f'Checking: {url}\n')

        await page.goto(url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        # Get ALL labels and their values using JavaScript
        result = await page.evaluate('''() => {
            const labels = document.querySelectorAll('label[label-for]');
            const data = [];
            labels.forEach(label => {
                const labelFor = label.getAttribute('label-for');
                const nextSibling = label.nextElementSibling;
                const value = nextSibling ? nextSibling.innerText : '';

                // Filter for interesting fields
                const keywords = ['EMAIL', 'PHONE', 'TEL', 'CONTACT', 'OPERATOR', 'NAME', 'ADDRESS', 'CITY', 'PROCUREMENT', 'WINNER'];
                if (labelFor && keywords.some(kw => labelFor.toUpperCase().includes(kw))) {
                    data.push({
                        label: labelFor,
                        value: value.substring(0, 150)
                    });
                }
            });
            return data;
        }''')

        print('=== CONTACT-RELATED FIELDS ON PAGE ===\n')
        for item in result:
            label = item['label']
            value = item['value']
            print(f"{label}:")
            print(f"  -> {value}")
            print()

        # Also get all emails found on page
        import re
        content = await page.content()
        emails = list(set(re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)))
        print(f'\n=== ALL EMAILS ON PAGE ===')
        for email in emails:
            print(f"  {email}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_all_labels())
