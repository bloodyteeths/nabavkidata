#!/usr/bin/env python3
"""Download sample PDFs from e-nabavki to analyze their structure"""
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from playwright.async_api import async_playwright

SAMPLE_DIR = Path("/home/ubuntu/nabavkidata/scraper/sample_pdfs")

async def download_sample_pdfs():
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Try multiple tender pages to find documents
        tender_urls = [
            "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/1e6a5d6b-e839-46ba-8bec-9c97f54f2d4e",
            "https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/53e296c7-fc8b-46e6-97d3-48f4ea309acf",
        ]

        all_docs = []

        for url in tender_urls:
            print(f"\nLoading: {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)

                # Find all document download links
                doc_links = await page.evaluate("""() => {
                    const anchors = document.querySelectorAll('a');
                    return Array.from(anchors).filter(a => {
                        const href = a.getAttribute('href') || '';
                        return href.includes('Download') || href.includes('.pdf') || href.includes('/File/') || href.includes('/Bids/');
                    }).map(a => ({
                        href: a.getAttribute('href'),
                        text: a.innerText.trim()
                    }));
                }""")

                print(f"Found {len(doc_links)} document links")
                for link in doc_links:
                    href = link.get('href', '')
                    text = link.get('text', '')[:50]
                    print(f"  {text} => {href[:80]}")
                    all_docs.append(link)

            except Exception as e:
                print(f"Error: {e}")

        await browser.close()

        # Download first 5 documents
        print("\n\n=== DOWNLOADING DOCUMENTS ===")
        async with aiohttp.ClientSession() as session:
            for i, doc in enumerate(all_docs[:5]):
                href = doc.get('href', '')
                if not href:
                    continue

                # Make absolute URL
                if href.startswith('/'):
                    href = 'https://e-nabavki.gov.mk' + href

                # Generate filename
                filename = f"sample_{i+1}.pdf"
                filepath = SAMPLE_DIR / filename

                try:
                    print(f"Downloading: {href[:80]}...")
                    async with session.get(href, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(filepath, 'wb') as f:
                                async for chunk in resp.content.iter_chunked(8192):
                                    await f.write(chunk)
                            size = filepath.stat().st_size
                            print(f"  Saved: {filename} ({size/1024:.1f} KB)")
                        else:
                            print(f"  Failed: HTTP {resp.status}")
                except Exception as e:
                    print(f"  Error: {e}")

        print(f"\nDownloaded files in: {SAMPLE_DIR}")

if __name__ == "__main__":
    asyncio.run(download_sample_pdfs())
