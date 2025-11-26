#!/usr/bin/env python3
"""Find document links on tender page"""
import asyncio
from playwright.async_api import async_playwright

async def find_docs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/53e296c7-fc8b-46e6-97d3-48f4ea309acf"
        print(f"Loading: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Look for ALL anchor tags with href
        print("=" * 80)
        print("ALL LINKS ON PAGE")
        print("=" * 80)

        links = await page.evaluate("""() => {
            const anchors = document.querySelectorAll('a[href]');
            return Array.from(anchors).map(a => ({
                href: a.getAttribute('href'),
                text: a.innerText.trim().substring(0, 50),
                classname: a.className
            })).filter(l => l.href && !l.href.startsWith('#/') && !l.href.startsWith('javascript'));
        }""")

        for link in links[:30]:
            href = link.get('href', '')[:80]
            text = link.get('text', '')
            cls = link.get('classname', '')
            print(f"[{cls}] {text} => {href}")

        # Specifically look for PDF/Download links
        print("\n" + "=" * 80)
        print("DOCUMENT DOWNLOAD LINKS")
        print("=" * 80)

        doc_links = await page.evaluate("""() => {
            const anchors = document.querySelectorAll('a');
            return Array.from(anchors).filter(a => {
                const href = a.getAttribute('href') || '';
                return href.includes('Download') || href.includes('.pdf') || href.includes('File') || href.includes('document');
            }).map(a => ({
                href: a.getAttribute('href'),
                text: a.innerText.trim()
            }));
        }""")

        for link in doc_links:
            text = link.get('text', '')[:40]
            href = link.get('href', '')
            print(f"{text} => {href}")

        # Check for any ng-click or download buttons
        print("\n" + "=" * 80)
        print("NG-CLICK ELEMENTS (Angular download handlers)")
        print("=" * 80)

        ng_elements = await page.evaluate("""() => {
            const elems = document.querySelectorAll('[ng-click]');
            return Array.from(elems).map(e => ({
                tag: e.tagName,
                ngClick: e.getAttribute('ng-click'),
                text: e.innerText.trim().substring(0, 50)
            })).filter(e => e.ngClick && (e.ngClick.includes('download') || e.ngClick.includes('file') || e.ngClick.includes('document')));
        }""")

        for elem in ng_elements[:20]:
            print(f"[{elem.get('tag')}] {elem.get('text')} => {elem.get('ngClick')}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(find_docs())
