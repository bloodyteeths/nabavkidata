#!/usr/bin/env python3
"""Find all documents in a contract page"""

import asyncio
import re
from playwright.async_api import async_playwright

async def find_all_docs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/feca8208-fe37-4b07-9f6c-cf6c32102a4a'
        print(f'Checking: {url}')

        await page.goto(url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        # Get full HTML and save it
        content = await page.content()
        with open('/tmp/full_page.html', 'w') as f:
            f.write(content)

        # Find all fileId references
        file_ids = re.findall(r'fileId=([a-f0-9-]+)', content)
        print(f'\nFound {len(file_ids)} file IDs:')
        for fid in set(file_ids):
            print(f'  {fid}')

        # Find all download URLs
        download_pattern = r'/(File|Bids)/Download[^"\'>\s]+'
        download_urls = re.findall(download_pattern, content)
        print(f'\nFound download URLs in HTML')

        # Better: find all hrefs with download
        all_links = await page.query_selector_all('a[href]')
        print(f'\n=== All links with download/file ===')
        for link in all_links:
            href = await link.get_attribute('href')
            if href and ('download' in href.lower() or 'file' in href.lower() or 'bids' in href.lower()):
                text = await link.inner_text()
                print(f'  {text.strip()[:50] or "(no text)"}: {href}')

        # Look for document sections/tables
        print('\n=== Document sections ===')
        doc_sections = await page.query_selector_all('table, .documents, .files, [class*="document"], [class*="file"]')
        for section in doc_sections[:5]:
            class_name = await section.get_attribute('class')
            text = await section.inner_text()
            if 'документ' in text.lower() or 'file' in text.lower() or 'download' in text.lower():
                print(f'Section ({class_name}): {text[:200]}...')

        await page.screenshot(path='/tmp/full_page.png', full_page=True)
        print('\nFull page screenshot saved to /tmp/full_page.png')

        await browser.close()

if __name__ == "__main__":
    asyncio.run(find_all_docs())
