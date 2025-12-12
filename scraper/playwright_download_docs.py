#!/usr/bin/env python3
"""
Playwright Document Downloader for e-nabavki.gov.mk

Downloads Word/Excel documents using Playwright browser automation.
This uses Playwright for BOTH authentication AND downloads since the
DownloadDoc.aspx endpoint requires active browser session with proper
state (ViewState, session tokens, etc.).

Usage:
    python playwright_download_docs.py --limit 100
    python playwright_download_docs.py --file-type docx --file-type xlsx
"""

import os
import sys
import asyncio
import hashlib
import logging
import argparse
import shutil
import json
from pathlib import Path
from datetime import datetime
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
FILES_STORE = Path(os.environ.get('FILES_STORE', '/home/ubuntu/nabavkidata/scraper/downloads/files'))
FILES_STORE.mkdir(parents=True, exist_ok=True)

COOKIE_FILE = Path('/tmp/playwright_doc_cookies.json')
DOWNLOAD_DIR = Path('/tmp/playwright_downloads')
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Load credentials
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')
load_dotenv(Path(__file__).parent / '.env')

NABAVKI_USERNAME = os.environ.get('NABAVKI_USERNAME')
NABAVKI_PASSWORD = os.environ.get('NABAVKI_PASSWORD')

# Database
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata')
if DB_URL.startswith('postgresql+asyncpg://'):
    DB_URL = DB_URL.replace('postgresql+asyncpg://', 'postgresql://')


class PlaywrightDocDownloader:
    """Downloads documents using Playwright for both auth AND downloads"""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.db = None
        self.stats = {'downloaded': 0, 'failed': 0, 'skipped': 0}

    async def connect_db(self):
        """Connect to database"""
        self.db = await asyncpg.connect(DB_URL)
        logger.info("Connected to database")

    async def close(self):
        """Cleanup"""
        if self.db:
            await self.db.close()
        if self.page:
            try:
                await self.page.close()
            except:
                pass
        if self.context:
            try:
                await self.context.close()
            except:
                pass
        if self.browser:
            try:
                await self.browser.close()
            except:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except:
                pass

    async def authenticate(self):
        """Login to e-nabavki.gov.mk using Playwright"""
        from playwright.async_api import async_playwright

        logger.info("Starting Playwright browser for authentication...")
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

        # Create context with download support
        self.context = await self.browser.new_context(
            accept_downloads=True,
            viewport={'width': 1920, 'height': 1080}
        )

        self.page = await self.context.new_page()

        logger.info("Navigating to login page...")
        await self.page.goto('https://e-nabavki.gov.mk/', wait_until='networkidle', timeout=60000)
        await asyncio.sleep(2)

        # Fill login form
        logger.info("Logging in...")
        try:
            # Username field
            username_sel = 'input[placeholder*="Корисничко"], input[name*="user"], input[type="text"]:first-of-type'
            await self.page.fill(username_sel, NABAVKI_USERNAME)

            # Password field
            password_sel = 'input[type="password"]'
            await self.page.fill(password_sel, NABAVKI_PASSWORD)

            # Submit
            submit_sel = 'input[type="submit"], button[type="submit"]'
            await self.page.click(submit_sel)

            await asyncio.sleep(5)

            # Check if logged in
            content = await self.page.content()
            url = self.page.url

            login_success = (
                'Одјави се' in content or
                'Logout' in content or
                'Мои набавки' in content or
                'PublicAccess/Login.aspx' not in url
            )

            if login_success or 'Login.aspx' not in url:
                logger.info("Login successful!")

                # Save cookies for debugging
                cookies = await self.context.cookies()
                with open(COOKIE_FILE, 'w') as f:
                    json.dump(cookies, f, indent=2)
                logger.info(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")

                return True
            else:
                logger.error("Login failed - still on login page")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def get_pending_documents(self, file_types: list, limit: int) -> list:
        """Get documents to download - focus on auth_required status"""
        type_conditions = []
        for ft in file_types:
            type_conditions.append(f"file_url ILIKE '%.{ft}%'")

        where_types = " OR ".join(type_conditions)

        query = f"""
            SELECT doc_id, tender_id, file_url, file_name
            FROM documents
            WHERE ({where_types})
              AND extraction_status = 'auth_required'
              AND file_url IS NOT NULL
              AND file_url NOT LIKE '%ohridskabanka%'
            ORDER BY doc_id
            LIMIT $1
        """

        rows = await self.db.fetch(query, limit)
        logger.info(f"Found {len(rows)} auth_required documents to download")
        return [dict(r) for r in rows]

    async def download_document_via_playwright(self, doc: dict) -> bool:
        """Download document using Playwright's download handling"""
        doc_id = doc['doc_id']
        tender_id = doc.get('tender_id', 'unknown').replace('/', '_')
        file_url = doc['file_url']

        # Generate filename
        url_hash = hashlib.md5(file_url.encode()).hexdigest()[:12]
        ext = self._get_extension(file_url)
        local_filename = f"{tender_id}_{url_hash}{ext}"
        dest_path = FILES_STORE / local_filename

        # Skip if already downloaded and valid
        if dest_path.exists() and dest_path.stat().st_size > 1000:
            # Verify it's not HTML
            with open(dest_path, 'rb') as f:
                header = f.read(100)
            if b'<!DOCTYPE' not in header and b'<html' not in header.lower():
                logger.info(f"Already exists: {local_filename}")
                self.stats['skipped'] += 1
                return True

        try:
            logger.info(f"Attempting download: {local_filename}")

            # Navigate to the document URL - this should trigger a download
            # Use expect_download to capture the download event
            async with self.page.expect_download(timeout=60000) as download_info:
                await self.page.goto(file_url, wait_until='commit', timeout=60000)

            download = await download_info.value

            # Save the downloaded file
            temp_path = DOWNLOAD_DIR / f"temp_{url_hash}{ext}"
            await download.save_as(str(temp_path))

            # Verify the download
            if not temp_path.exists():
                logger.warning(f"Download file not found: {local_filename}")
                await self._update_status(doc_id, 'download_failed')
                self.stats['failed'] += 1
                return False

            size = temp_path.stat().st_size

            if size < 100:
                logger.warning(f"File too small ({size} bytes): {local_filename}")
                temp_path.unlink()
                await self._update_status(doc_id, 'download_failed')
                self.stats['failed'] += 1
                return False

            # Check if it's HTML (login page)
            with open(temp_path, 'rb') as f:
                header = f.read(500)

            is_html = (
                b'<!DOCTYPE' in header or
                b'<html' in header.lower() or
                b'<HTML' in header or
                b'Login.aspx' in header
            )

            if is_html:
                logger.warning(f"Got HTML instead of file: {local_filename}")
                temp_path.unlink()
                await self._update_status(doc_id, 'auth_required')
                self.stats['failed'] += 1
                return False

            # Move to final destination
            shutil.move(str(temp_path), str(dest_path))

            size_kb = size / 1024
            logger.info(f"Downloaded: {local_filename} ({size_kb:.1f} KB)")

            # Clear garbage content_text
            await self._update_status_and_clear(doc_id, 'downloaded', str(dest_path))
            self.stats['downloaded'] += 1
            return True

        except Exception as e:
            error_msg = str(e)

            # Check if it's a page navigation (not a download)
            if 'net::ERR' in error_msg or 'Navigation' in error_msg or 'Download' in error_msg:
                # The page navigated instead of downloading - check content
                try:
                    content = await self.page.content()

                    # Check if we got a login page
                    if 'Корисничко име' in content or 'Лозинка' in content or 'Login' in content:
                        logger.warning(f"Redirected to login page: {local_filename}")
                        await self._update_status(doc_id, 'auth_required')
                        self.stats['failed'] += 1
                        return False

                    # Check if we got an error page
                    if 'error' in content.lower() or 'грешка' in content.lower():
                        logger.warning(f"Got error page: {local_filename}")
                        await self._update_status(doc_id, 'download_failed')
                        self.stats['failed'] += 1
                        return False

                except:
                    pass

            logger.error(f"Download error for {doc_id}: {e}")
            await self._update_status(doc_id, 'download_failed')
            self.stats['failed'] += 1
            return False

    def _get_extension(self, url: str) -> str:
        """Get file extension from URL"""
        url_lower = url.lower()
        for ext in ['.docx', '.doc', '.xlsx', '.xls', '.pdf']:
            if ext in url_lower:
                return ext
        return '.bin'

    async def _update_status(self, doc_id: str, status: str, file_path: str = None):
        """Update document status in database"""
        if file_path:
            await self.db.execute("""
                UPDATE documents
                SET extraction_status = $1, file_path = $2, updated_at = NOW()
                WHERE doc_id = $3
            """, status, file_path, doc_id)
        else:
            await self.db.execute("""
                UPDATE documents
                SET extraction_status = $1, updated_at = NOW()
                WHERE doc_id = $2
            """, status, doc_id)

    async def _update_status_and_clear(self, doc_id: str, status: str, file_path: str):
        """Update status and clear garbage content_text"""
        await self.db.execute("""
            UPDATE documents
            SET extraction_status = $1, file_path = $2, content_text = NULL, updated_at = NOW()
            WHERE doc_id = $3
        """, status, file_path, doc_id)

    async def run(self, file_types: list, limit: int):
        """Main run loop"""
        await self.connect_db()

        if not await self.authenticate():
            logger.error("Authentication failed!")
            return

        docs = await self.get_pending_documents(file_types, limit)

        for i, doc in enumerate(docs):
            await self.download_document_via_playwright(doc)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{len(docs)} | Downloaded: {self.stats['downloaded']} | Failed: {self.stats['failed']}")

            # Small delay to be nice to the server
            await asyncio.sleep(0.5)

        logger.info(f"\n=== COMPLETE ===")
        logger.info(f"Downloaded: {self.stats['downloaded']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Skipped (already exist): {self.stats['skipped']}")


async def main():
    parser = argparse.ArgumentParser(description='Download documents with Playwright')
    parser.add_argument('--file-type', '-t', dest='file_types', action='append',
                       default=[], help='File types to download (docx, xlsx, etc)')
    parser.add_argument('--limit', '-l', type=int, default=100,
                       help='Maximum documents to download')
    args = parser.parse_args()

    if not args.file_types:
        args.file_types = ['docx', 'doc', 'xlsx', 'xls']

    downloader = PlaywrightDocDownloader()
    try:
        await downloader.run(args.file_types, args.limit)
    finally:
        await downloader.close()


if __name__ == '__main__':
    asyncio.run(main())
