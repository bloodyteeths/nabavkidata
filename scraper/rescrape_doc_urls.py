#!/usr/bin/env python3
"""
Re-scrape document URLs from e-nabavki.gov.mk for documents missing file_url.

Uses Playwright to render AngularJS pages and extract document download links
from ng-click attributes and href elements.

Usage:
    python3 rescrape_doc_urls.py --limit 500 --workers 3
    python3 rescrape_doc_urls.py --dry-run
"""
import asyncio
import argparse
import json
import logging
import os
import re
import urllib.parse
from typing import List, Dict, Optional

import asyncpg
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL.startswith('postgresql+asyncpg://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://', 1)

BASE_URL = "https://e-nabavki.gov.mk/PublicAccess/home.aspx#"


def extract_documents_from_html(html: str, tender_id: str) -> List[Dict]:
    """Extract document URLs from rendered HTML page."""
    documents = []
    seen_urls = set()

    def add_doc(url: str, name: str = ""):
        if not url or url in seen_urls:
            return
        if url.startswith('/'):
            url = 'https://e-nabavki.gov.mk' + url
        elif not url.startswith('http'):
            url = 'https://e-nabavki.gov.mk/' + url
        if url in seen_urls:
            return
        seen_urls.add(url)
        if not name:
            parsed = urllib.parse.urlparse(url)
            if 'fileId=' in url:
                file_id = urllib.parse.parse_qs(parsed.query).get('fileId', ['unknown'])[0]
                name = f"document_{file_id[:8]}.pdf"
            else:
                name = os.path.basename(parsed.path) or "document.pdf"
        documents.append({'url': url, 'file_name': name, 'tender_id': tender_id})

    # Extract from PreviewDocumentConfirm ng-click
    ng_click_pattern = re.compile(r'PreviewDocumentConfirm\((\{.*?\})\)', re.DOTALL)
    for match in ng_click_pattern.finditer(html):
        try:
            doc_data = json.loads(match.group(1))
            doc_url = doc_data.get('DocumentUrl', '')
            doc_name = doc_data.get('DocumentName', '')
            file_id = doc_data.get('FileId', '')
            if doc_url:
                add_doc(doc_url, doc_name)
            if file_id:
                add_doc(f"https://e-nabavki.gov.mk/File/DownloadPublicFile?fileId={file_id}", doc_name)
        except (json.JSONDecodeError, Exception):
            pass

    # Extract from previewDocumentModal
    modal_pattern = re.compile(
        r'previewDocumentModal\([^,]+,\s*["\']([^"\']+)["\'],\s*["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']',
        re.DOTALL
    )
    for match in modal_pattern.finditer(html):
        file_id, doc_name, doc_url = match.group(1), match.group(2), match.group(3)
        if doc_url:
            add_doc(doc_url, doc_name)

    # Extract from href links
    href_patterns = [
        re.compile(r'href="([^"]*Download[^"]*)"', re.I),
        re.compile(r'href="([^"]*\.pdf[^"]*)"', re.I),
        re.compile(r'href="([^"]*fileId=[^"]*)"', re.I),
        re.compile(r'href="([^"]*DownloadPublicFile[^"]*)"', re.I),
        re.compile(r'href="([^"]*DownloadContractFile[^"]*)"', re.I),
        re.compile(r'href="([^"]*\.docx?[^"]*)"', re.I),
        re.compile(r'href="([^"]*\.xlsx?[^"]*)"', re.I),
    ]
    for pattern in href_patterns:
        for match in pattern.finditer(html):
            add_doc(match.group(1))

    return documents


async def scrape_tender_docs(page, tender_id: str, dossier_id: Optional[str]) -> List[Dict]:
    """Visit a tender detail page and extract document URLs."""
    if dossier_id:
        url = f"{BASE_URL}/dossie-acpp/{dossier_id}"
    else:
        url = f"{BASE_URL}/dossie/{tender_id}"

    try:
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)  # Wait for AngularJS to render

        # Try clicking document tabs if they exist
        for tab_selector in [
            'a:has-text("Документи")',
            'a:has-text("документ")',
            '[ng-click*="document"]',
            '.nav-tabs a:nth-child(3)',
        ]:
            try:
                tab = await page.query_selector(tab_selector)
                if tab:
                    await tab.click()
                    await page.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        html = await page.content()
        docs = extract_documents_from_html(html, tender_id)
        return docs

    except Exception as e:
        logger.warning(f"Failed to scrape {tender_id}: {e}")
        return []


async def worker(worker_id: int, queue: asyncio.Queue, pool: asyncpg.Pool,
                 browser, dry_run: bool, stats: dict):
    """Worker that processes tenders from the queue."""
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    )
    page = await context.new_page()

    while True:
        try:
            tender_id, dossier_id = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        docs = await scrape_tender_docs(page, tender_id, dossier_id)
        stats['processed'] += 1

        if docs:
            stats['docs_found'] += len(docs)
            if not dry_run:
                async with pool.acquire() as conn:
                    for doc in docs:
                        try:
                            # Try to update existing document
                            result = await conn.execute("""
                                UPDATE documents
                                SET file_url = $1
                                WHERE tender_id = $2
                                  AND file_name = $3
                                  AND (file_url IS NULL OR file_url = '')
                            """, doc['url'], doc['tender_id'], doc['file_name'])

                            if 'UPDATE 1' in result:
                                stats['updated'] += 1
                            elif 'UPDATE 0' in result:
                                # Try matching by partial file_name (document_<8chars>)
                                if 'fileId=' in doc['url']:
                                    file_id = urllib.parse.parse_qs(
                                        urllib.parse.urlparse(doc['url']).query
                                    ).get('fileId', [''])[0]
                                    if file_id:
                                        partial_name = f"document_{file_id[:8]}"
                                        result2 = await conn.execute("""
                                            UPDATE documents
                                            SET file_url = $1
                                            WHERE tender_id = $2
                                              AND file_name LIKE $3
                                              AND (file_url IS NULL OR file_url = '')
                                        """, doc['url'], doc['tender_id'], f"{partial_name}%")
                                        if 'UPDATE' in result2 and 'UPDATE 0' not in result2:
                                            stats['updated'] += 1
                        except Exception as e:
                            logger.debug(f"DB update error for {doc['tender_id']}: {e}")
            else:
                for doc in docs:
                    logger.info(f"[DRY-RUN] {doc['tender_id']}: {doc['file_name']} -> {doc['url'][:80]}")

        if stats['processed'] % 50 == 0:
            logger.info(
                f"Worker {worker_id}: {stats['processed']} tenders processed, "
                f"{stats['docs_found']} docs found, {stats['updated']} updated"
            )

    await page.close()
    await context.close()


async def main():
    parser = argparse.ArgumentParser(description='Re-scrape document URLs from e-nabavki')
    parser.add_argument('--limit', type=int, default=None, help='Max tenders to process')
    parser.add_argument('--workers', type=int, default=2, help='Parallel browser tabs')
    parser.add_argument('--dry-run', action='store_true', help='Preview without DB changes')
    args = parser.parse_args()

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=args.workers + 2)

    # Get tenders with pending docs missing file_url
    async with pool.acquire() as conn:
        query = """
            SELECT DISTINCT d.tender_id, t.dossier_id
            FROM documents d
            JOIN tenders t ON d.tender_id = t.tender_id
            WHERE d.extraction_status = 'pending'
              AND (d.file_url IS NULL OR d.file_url = '')
            ORDER BY d.tender_id
        """
        if args.limit:
            query += f" LIMIT {args.limit}"
        rows = await conn.fetch(query)

    logger.info(f"Found {len(rows)} tenders to re-scrape (workers={args.workers})")

    if not rows:
        logger.info("Nothing to do")
        return

    queue = asyncio.Queue()
    for row in rows:
        queue.put_nowait((row['tender_id'], row.get('dossier_id')))

    stats = {'processed': 0, 'docs_found': 0, 'updated': 0}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        workers = [
            worker(i, queue, pool, browser, args.dry_run, stats)
            for i in range(min(args.workers, len(rows)))
        ]
        await asyncio.gather(*workers)

        await browser.close()

    await pool.close()

    logger.info(
        f"DONE: {stats['processed']} tenders processed, "
        f"{stats['docs_found']} document URLs found, "
        f"{stats['updated']} documents updated in DB"
    )


if __name__ == '__main__':
    asyncio.run(main())
