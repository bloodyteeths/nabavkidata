#!/usr/bin/env python3
"""
Authenticated Document Downloader for e-nabavki.gov.mk

This script:
1. Authenticates using Playwright (like nabavki_auth_spider)
2. Saves cookies for reuse
3. Downloads all pending/failed documents with authentication
4. Validates downloads (detects HTML login pages vs real files)
5. Updates database with new file paths

Usage:
    python auth_download_documents.py --limit 100
    python auth_download_documents.py --file-type xlsx
    python auth_download_documents.py --redownload-failed
"""

import os
import sys
import json
import asyncio
import hashlib
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
import asyncpg

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
COOKIE_FILE = Path('/tmp/nabavki_auth_cookies.json')
SESSION_FILE = Path('/tmp/nabavki_auth_session.json')
FILES_STORE = Path(os.environ.get('FILES_STORE', '/Users/tamsar/Downloads/nabavkidata/scraper/downloads/files'))

# Load credentials from .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

NABAVKI_USERNAME = os.environ.get('NABAVKI_USERNAME')
NABAVKI_PASSWORD = os.environ.get('NABAVKI_PASSWORD')

# Database connection
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'user': os.environ.get('DB_USER', 'nabavki_user'),
    'password': os.environ.get('DB_PASSWORD', '9fagrPSDfQqBjrKZZLVrJY2Am'),
    'database': os.environ.get('DB_NAME', 'nabavkidata'),
}


class AuthenticatedDownloader:
    """Downloads documents from e-nabavki.gov.mk with authentication"""

    def __init__(self):
        self.cookies: List[Dict] = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        self.stats = {
            'total': 0,
            'downloaded': 0,
            'failed': 0,
            'skipped': 0,
            'already_exists': 0,
        }

    async def authenticate(self) -> bool:
        """Authenticate using Playwright and save cookies"""

        # Check for existing valid cookies
        if self._load_saved_cookies():
            logger.info("Using existing valid cookies")
            return True

        logger.info("Authenticating with Playwright...")

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False

        if not NABAVKI_USERNAME or not NABAVKI_PASSWORD:
            logger.error("Credentials not found. Set NABAVKI_USERNAME and NABAVKI_PASSWORD")
            return False

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                # Navigate to login page
                logger.info("Navigating to e-nabavki.gov.mk...")
                await page.goto('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/home',
                               wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_timeout(3000)

                # Fill username
                username_selectors = [
                    'input[placeholder*="Корисничко"]',
                    'input[ng-model*="userName"]',
                    'input[type="text"]:not([type="password"])',
                ]

                for selector in username_selectors:
                    try:
                        field = await page.query_selector(selector)
                        if field and await field.is_visible():
                            await field.fill(NABAVKI_USERNAME)
                            logger.info(f"Filled username field: {selector}")
                            break
                    except:
                        continue

                # Fill password
                password_field = await page.query_selector('input[type="password"]')
                if password_field:
                    await password_field.fill(NABAVKI_PASSWORD)
                    logger.info("Filled password field")

                await page.wait_for_timeout(500)

                # Submit login
                submit_selectors = ['button:has-text("Влез")', 'button[type="submit"]', 'input[type="submit"]']
                for selector in submit_selectors:
                    try:
                        btn = await page.query_selector(selector)
                        if btn and await btn.is_visible():
                            await btn.click()
                            logger.info(f"Clicked submit: {selector}")
                            break
                    except:
                        continue

                # Wait for login to complete
                await page.wait_for_timeout(5000)

                # Check login success
                page_content = await page.content()
                if any(ind in page_content.lower() for ind in ['одјава', 'logout', NABAVKI_USERNAME.lower()]):
                    logger.info("✅ LOGIN SUCCESSFUL")

                    # Save cookies
                    self.cookies = await context.cookies()
                    self._save_cookies()

                    await browser.close()
                    return True
                else:
                    logger.error("❌ LOGIN FAILED - Check credentials")
                    await browser.close()
                    return False

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def _load_saved_cookies(self) -> bool:
        """Load saved cookies if they exist and are not expired"""
        try:
            if COOKIE_FILE.exists() and SESSION_FILE.exists():
                with open(SESSION_FILE, 'r') as f:
                    session_data = json.load(f)

                login_time = datetime.fromisoformat(session_data.get('login_time', '2000-01-01'))
                expiry_time = login_time + timedelta(hours=4)

                if datetime.utcnow() < expiry_time:
                    with open(COOKIE_FILE, 'r') as f:
                        self.cookies = json.load(f)
                    logger.info(f"Loaded {len(self.cookies)} cookies (valid until {expiry_time})")
                    return True
                else:
                    logger.info("Saved cookies expired")
        except Exception as e:
            logger.warning(f"Could not load cookies: {e}")
        return False

    def _save_cookies(self):
        """Save cookies to file"""
        try:
            login_time = datetime.utcnow()

            with open(COOKIE_FILE, 'w') as f:
                json.dump(self.cookies, f, indent=2)

            session_data = {
                'login_time': login_time.isoformat(),
                'username': NABAVKI_USERNAME,
                'cookie_count': len(self.cookies),
            }
            with open(SESSION_FILE, 'w') as f:
                json.dump(session_data, f, indent=2)

            logger.info(f"Saved {len(self.cookies)} cookies to {COOKIE_FILE}")
        except Exception as e:
            logger.error(f"Could not save cookies: {e}")

    async def init_session(self):
        """Initialize aiohttp session with cookies"""
        from yarl import URL

        jar = aiohttp.CookieJar()
        self.session = aiohttp.ClientSession(cookie_jar=jar)

        # Add cookies to session
        for cookie in self.cookies:
            try:
                domain = cookie.get('domain', 'e-nabavki.gov.mk')
                if domain.startswith('.'):
                    domain = domain[1:]

                self.session.cookie_jar.update_cookies(
                    {cookie['name']: cookie['value']},
                    URL(f"https://{domain}/")
                )
            except Exception as e:
                logger.debug(f"Could not add cookie: {e}")

        logger.info(f"Session initialized with {len(self.cookies)} cookies")

    async def init_db(self):
        """Initialize database connection pool"""
        self.db_pool = await asyncpg.create_pool(**DB_CONFIG, min_size=2, max_size=10)
        logger.info("Database connection established")

    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        if self.db_pool:
            await self.db_pool.close()

    async def get_pending_documents(self, file_types: List[str] = None,
                                     limit: int = None,
                                     redownload_failed: bool = False) -> List[Dict]:
        """Get documents that need downloading from database"""

        conditions = ["file_url LIKE 'https://e-nabavki%'"]
        conditions.append("file_url NOT LIKE '%ohridskabanka%'")

        if redownload_failed:
            # Include documents that were downloaded but are actually HTML
            conditions.append("""
                (extraction_status IN ('pending', 'download_failed', 'auth_required')
                 OR (extraction_status = 'success' AND (file_size_bytes IS NULL OR file_size_bytes < 1000)))
            """)
        else:
            conditions.append("extraction_status IN ('pending', 'download_failed', 'auth_required')")

        if file_types:
            type_conditions = []
            for ft in file_types:
                type_conditions.append(f"LOWER(file_name) LIKE '%.{ft.lower()}'")
            conditions.append(f"({' OR '.join(type_conditions)})")

        query = f"""
            SELECT doc_id, tender_id, file_url, file_name, file_path
            FROM documents
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE
                    WHEN LOWER(file_name) LIKE '%.xlsx' THEN 1
                    WHEN LOWER(file_name) LIKE '%.xls' THEN 2
                    WHEN LOWER(file_name) LIKE '%.docx' THEN 3
                    WHEN LOWER(file_name) LIKE '%.doc' THEN 4
                    ELSE 5
                END
            {'LIMIT ' + str(limit) if limit else ''}
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        logger.info(f"Found {len(rows)} documents to download")
        return [dict(r) for r in rows]

    def _generate_filename(self, tender_id: str, url: str, original_name: str) -> str:
        """Generate unique filename for downloaded file"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        ext = Path(original_name).suffix.lower() or '.pdf'
        safe_tender_id = str(tender_id).replace('/', '_').replace('\\', '_')
        return f"{safe_tender_id}_{url_hash}{ext}"

    def _is_html_content(self, content: bytes) -> bool:
        """Check if downloaded content is HTML (login page) instead of actual file"""
        if len(content) < 100:
            return True

        # Check for HTML indicators
        content_start = content[:500].lower()
        html_indicators = [b'<!doctype html', b'<html', b'<!doctype', b'<head', b'<body']

        if any(ind in content_start for ind in html_indicators):
            return True

        # Check for Macedonian login page text
        if b'\xd0\x9d\xd0\xb0\xd1\x98\xd0\xb0\xd0\xb2\xd0\xb8' in content:  # "Најави" in UTF-8
            return True
        if b'\xd0\x9b\xd0\xbe\xd0\xb7\xd0\xb8\xd0\xbd\xd0\xba\xd0\xb0' in content:  # "Лозинка"
            return True

        return False

    def _validate_file_type(self, content: bytes, expected_ext: str) -> bool:
        """Validate file content matches expected type"""
        # File magic bytes
        signatures = {
            '.pdf': [b'%PDF'],
            '.docx': [b'PK\x03\x04'],  # ZIP archive (Office Open XML)
            '.xlsx': [b'PK\x03\x04'],
            '.doc': [b'\xd0\xcf\x11\xe0'],  # OLE Compound Document
            '.xls': [b'\xd0\xcf\x11\xe0'],
        }

        expected_sigs = signatures.get(expected_ext.lower(), [])
        if not expected_sigs:
            return True  # Unknown type, assume valid

        return any(content.startswith(sig) for sig in expected_sigs)

    async def download_document(self, doc: Dict) -> bool:
        """Download a single document with authentication"""
        doc_id = doc['doc_id']
        url = doc['file_url']
        file_name = doc['file_name']
        tender_id = doc['tender_id']

        # Generate local filename
        local_filename = self._generate_filename(tender_id, url, file_name)
        local_path = FILES_STORE / local_filename

        # Check if already exists and is valid
        if local_path.exists() and local_path.stat().st_size > 1000:
            # Check if it's not HTML
            with open(local_path, 'rb') as f:
                content = f.read(500)
            if not self._is_html_content(content):
                logger.debug(f"Already exists: {local_filename}")
                self.stats['already_exists'] += 1
                return True

        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status != 200:
                    logger.warning(f"HTTP {response.status} for {url}")
                    await self._update_doc_status(doc_id, 'download_failed',
                                                  error=f"HTTP {response.status}")
                    self.stats['failed'] += 1
                    return False

                content = await response.read()

                # Check if we got HTML login page
                if self._is_html_content(content):
                    logger.warning(f"Got HTML instead of file: {file_name}")
                    await self._update_doc_status(doc_id, 'auth_required',
                                                  error="Received login page HTML")
                    self.stats['failed'] += 1
                    return False

                # Validate file type
                ext = Path(file_name).suffix.lower()
                if not self._validate_file_type(content, ext):
                    logger.warning(f"File type mismatch for {file_name}")

                # Save file
                FILES_STORE.mkdir(parents=True, exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(content)

                # Calculate hash
                file_hash = hashlib.sha256(content).hexdigest()

                # Update database
                await self._update_doc_success(doc_id, str(local_path), len(content), file_hash)

                logger.info(f"✅ Downloaded: {file_name} ({len(content):,} bytes)")
                self.stats['downloaded'] += 1
                return True

        except asyncio.TimeoutError:
            logger.warning(f"Timeout downloading {url}")
            await self._update_doc_status(doc_id, 'download_failed', error="Timeout")
            self.stats['failed'] += 1
            return False
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            await self._update_doc_status(doc_id, 'download_failed', error=str(e))
            self.stats['failed'] += 1
            return False

    async def _update_doc_status(self, doc_id: str, status: str, error: str = None):
        """Update document status in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE documents
                SET extraction_status = $1,
                    updated_at = NOW()
                WHERE doc_id = $2
            """, status, doc_id)

    async def _update_doc_success(self, doc_id: str, file_path: str,
                                   file_size: int, file_hash: str):
        """Update document after successful download"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE documents
                SET file_path = $1,
                    file_size_bytes = $2,
                    file_hash = $3,
                    extraction_status = 'pending',
                    updated_at = NOW()
                WHERE doc_id = $4
            """, file_path, file_size, file_hash, doc_id)

    async def run(self, file_types: List[str] = None,
                  limit: int = None,
                  redownload_failed: bool = False):
        """Main execution flow"""

        # Authenticate
        if not await self.authenticate():
            logger.error("Authentication failed. Cannot proceed.")
            return

        # Initialize session and database
        await self.init_session()
        await self.init_db()

        try:
            # Get documents to download
            documents = await self.get_pending_documents(
                file_types=file_types,
                limit=limit,
                redownload_failed=redownload_failed
            )

            self.stats['total'] = len(documents)

            if not documents:
                logger.info("No documents to download")
                return

            # Download documents with concurrency limit
            semaphore = asyncio.Semaphore(5)  # Max 5 concurrent downloads

            async def download_with_semaphore(doc):
                async with semaphore:
                    return await self.download_document(doc)

            tasks = [download_with_semaphore(doc) for doc in documents]

            # Process in batches for progress reporting
            batch_size = 10
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i+batch_size]
                await asyncio.gather(*batch)

                progress = min(i + batch_size, len(tasks))
                logger.info(f"Progress: {progress}/{len(tasks)} "
                           f"(Downloaded: {self.stats['downloaded']}, "
                           f"Failed: {self.stats['failed']})")

            # Print summary
            logger.info("=" * 60)
            logger.info("DOWNLOAD COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Total documents: {self.stats['total']}")
            logger.info(f"Downloaded: {self.stats['downloaded']}")
            logger.info(f"Already existed: {self.stats['already_exists']}")
            logger.info(f"Failed: {self.stats['failed']}")
            logger.info("=" * 60)

        finally:
            await self.close()


async def main():
    parser = argparse.ArgumentParser(description='Download documents with authentication')
    parser.add_argument('--file-type', '-t', action='append', dest='file_types',
                       help='File types to download (xlsx, docx, pdf, etc). Can be used multiple times.')
    parser.add_argument('--limit', '-l', type=int, default=None,
                       help='Maximum number of documents to download')
    parser.add_argument('--redownload-failed', '-r', action='store_true',
                       help='Re-download documents that were marked success but are actually HTML')

    args = parser.parse_args()

    downloader = AuthenticatedDownloader()
    await downloader.run(
        file_types=args.file_types,
        limit=args.limit,
        redownload_failed=args.redownload_failed
    )


if __name__ == '__main__':
    asyncio.run(main())
