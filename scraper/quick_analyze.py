#!/usr/bin/env python3
"""Quick tender page analysis"""
import asyncio
from playwright.async_api import async_playwright

async def analyze():
    url = 'https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/74056a47-3858-46ee-b222-6e7a863a9bd8/1'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Loading: {url}")
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        # Get page title
        title = await page.title()
        print(f'Title: {title}')
        print(f'URL: {page.url}')

        # Check for key elements
        content = await page.content()
        print(f'Content length: {len(content)}')

        # Check for tender data
        keywords = ['Број на оглас', 'Договорен орган', 'Проценета вредност', 'Делива набавка', 'Победник', 'Понудувач']
        for kw in keywords:
            if kw in content:
                print(f'Found: {kw}')
            else:
                print(f'NOT found: {kw}')

        # Check for tables
        tables = await page.evaluate('() => document.querySelectorAll("table").length')
        print(f'Tables: {tables}')

        # Get all label-value pairs
        pairs = await page.evaluate('''
            () => {
                const pairs = [];
                document.querySelectorAll('label.dosie-label').forEach(label => {
                    const key = label.innerText.trim();
                    const valueEl = label.nextElementSibling;
                    if (valueEl) {
                        const value = valueEl.innerText?.trim().substring(0, 100);
                        if (key && value) {
                            pairs.push({key: key, value: value});
                        }
                    }
                });
                return pairs;
            }
        ''')
        print(f'\nLabel-value pairs found: {len(pairs)}')
        for p in pairs[:20]:
            print(f'  {p["key"]}: {p["value"]}')

        # Check for "Делива набавка" (Dividable procurement)
        dividable = await page.evaluate('''
            () => {
                const labels = document.querySelectorAll('label');
                for (const label of labels) {
                    if (label.innerText?.includes('Делива')) {
                        const valueEl = label.nextElementSibling;
                        return valueEl?.innerText?.trim() || 'N/A';
                    }
                }
                return 'Not found';
            }
        ''')
        print(f'\nДелива набавка (Dividable): {dividable}')

        # Check for document section
        docs = await page.evaluate('''
            () => {
                const docs = [];
                // Look for document links
                document.querySelectorAll('a').forEach(a => {
                    const href = a.getAttribute('href') || '';
                    const text = a.innerText?.trim() || '';
                    if (href.includes('download') || href.includes('.pdf') ||
                        href.includes('.doc') || href.includes('Document') ||
                        text.toLowerCase().includes('документ') || text.toLowerCase().includes('download')) {
                        docs.push({text: text.substring(0, 50), href: href.substring(0, 100)});
                    }
                });
                return docs;
            }
        ''')
        print(f'\nDocument links found: {len(docs)}')
        for d in docs[:5]:
            print(f'  {d["text"]}: {d["href"]}')

        # Take screenshot
        await page.screenshot(path='/tmp/tender_page.png')
        print('\nScreenshot saved to /tmp/tender_page.png')

        await browser.close()

asyncio.run(analyze())
