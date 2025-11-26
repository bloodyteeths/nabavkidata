#!/usr/bin/env python3
"""Download sample PDFs from medical tenders"""
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from playwright.async_api import async_playwright

SAMPLE_DIR = Path("/home/ubuntu/nabavkidata/scraper/sample_pdfs")

async def download_medical_pdfs():
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Go to awarded contracts list and look for medical tenders
        url = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notifications-for-acpp"
        print(f"Loading awarded contracts list: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Search for medical tenders (лекови = medicines)
        search_input = await page.query_selector('input[type="search"], input[placeholder*="Пребарај"]')
        if search_input:
            await search_input.fill("лекови")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(3000)

        # Get tender links
        tender_links = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="dossie-acpp"]');
            return Array.from(links).slice(0, 5).map(a => ({
                href: a.getAttribute('href'),
                text: a.innerText.trim()
            }));
        }""")

        print(f"Found {len(tender_links)} medical tender links")

        all_docs = []

        # Visit each tender
        for i, tender in enumerate(tender_links[:3]):
            href = tender.get('href', '')
            text = tender.get('text', '')[:50]
            print(f"\n=== Tender {i+1}: {text} ===")

            if not href:
                continue

            # Make absolute URL
            if href.startswith('#'):
                tender_url = f"https://e-nabavki.gov.mk/PublicAccess/home.aspx{href}"
            else:
                tender_url = href

            try:
                await page.goto(tender_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)

                # Find document links
                doc_links = await page.evaluate("""() => {
                    const anchors = document.querySelectorAll('a');
                    return Array.from(anchors).filter(a => {
                        const href = a.getAttribute('href') || '';
                        return (href.includes('Download') || href.includes('.pdf') ||
                                href.includes('/File/') || href.includes('/Bids/')) &&
                               !href.includes('ohridskabanka');
                    }).map(a => ({
                        href: a.getAttribute('href'),
                        text: a.innerText.trim()
                    }));
                }""")

                print(f"  Found {len(doc_links)} documents")
                for doc in doc_links[:3]:
                    print(f"    {doc.get('text', '')[:40]} => {doc.get('href', '')[:60]}")
                all_docs.extend(doc_links)

            except Exception as e:
                print(f"  Error: {e}")

        await browser.close()

        # Download documents
        print("\n\n=== DOWNLOADING MEDICAL DOCUMENTS ===")
        async with aiohttp.ClientSession() as session:
            downloaded = 0
            for doc in all_docs[:10]:
                href = doc.get('href', '')
                if not href or downloaded >= 5:
                    continue

                if href.startswith('/'):
                    href = 'https://e-nabavki.gov.mk' + href

                filename = f"medical_{downloaded+1}.pdf"
                filepath = SAMPLE_DIR / filename

                try:
                    print(f"Downloading: {href[:80]}...")
                    async with session.get(href, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(filepath, 'wb') as f:
                                async for chunk in resp.content.iter_chunked(8192):
                                    await f.write(chunk)
                            size = filepath.stat().st_size
                            print(f"  Saved: {filename} ({size/1024:.1f} KB)")
                            downloaded += 1
                        else:
                            print(f"  Failed: HTTP {resp.status}")
                except Exception as e:
                    print(f"  Error: {e}")

        print(f"\nDownloaded {downloaded} medical documents")

if __name__ == "__main__":
    asyncio.run(download_medical_pdfs())
