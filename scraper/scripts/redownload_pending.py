#!/usr/bin/env python3
"""
Re-download Script for Pending Documents

PHASE 3 Enhancement: Re-downloads documents that failed due to missing authentication.
Uses saved session cookies from authenticated spiders.

Usage:
    python3 redownload_pending.py --limit 100 --batch-size 10
"""

import os
import sys
import asyncio
import asyncpg
import aiohttp
import aiofiles
import hashlib
import logging
import json
import argparse
from pathlib import Path
from datetime import datetime
from yarl import URL
from dotenv import load_dotenv
load_dotenv()


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger('redownload')

# Cookie file paths (shared with pipelines)
AUTH_COOKIE_FILE = Path('/tmp/nabavki_auth_cookies.json')
CONTRACTS_COOKIE_FILE = Path('/tmp/contracts_auth_cookies.json')

# Default download directory
DEFAULT_FILES_STORE = os.environ.get('FILES_STORE', '/home/ubuntu/nabavkidata/scraper/downloads/files')


class DocumentRedownloader:
    """
    Re-downloads documents that failed due to authentication issues.
    """

    def __init__(self, database_url: str, files_store: str = DEFAULT_FILES_STORE):
        self.database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        self.files_store = Path(files_store)
        self.files_store.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.session = None
        self.cookies = None
        self.stats = {
            'attempted': 0,
            'success': 0,
            'auth_required': 0,
            'download_failed': 0,
            'skipped': 0
        }

    def _load_auth_cookies(self):
        """Load saved authentication cookies from spider session files."""
        cookie_files = [AUTH_COOKIE_FILE, CONTRACTS_COOKIE_FILE]

        for cookie_file in cookie_files:
            if cookie_file.exists():
                try:
                    with open(cookie_file, 'r') as f:
                        self.cookies = json.load(f)
                    logger.info(f"✓ Loaded {len(self.cookies)} auth cookies from {cookie_file}")
                    return True
                except Exception as e:
                    logger.warning(f"Could not load cookies from {cookie_file}: {e}")

        logger.error("⚠ No auth cookies found! Run authenticated spider first.")
        return False

    async def connect(self):
        """Establish database and HTTP connections."""
        # Database connection
        self.conn = await asyncpg.connect(self.database_url)
        logger.info("Connected to database")

        # Load cookies
        if not self._load_auth_cookies():
            raise RuntimeError("Cannot proceed without authentication cookies")

        # Create aiohttp session with cookies
        jar = aiohttp.CookieJar()
        self.session = aiohttp.ClientSession(cookie_jar=jar)

        # Add cookies to session
        if self.cookies:
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
                    logger.debug(f"Could not add cookie {cookie.get('name')}: {e}")

    async def close(self):
        """Close connections."""
        if self.session:
            await self.session.close()
        if self.conn:
            await self.conn.close()
        logger.info("Connections closed")

    async def get_pending_documents(self, limit: int = 100) -> list:
        """
        Get documents that need re-download.

        Includes:
        - pending: Never downloaded
        - auth_required: Failed due to authentication
        - download_invalid: Got HTML instead of PDF
        """
        rows = await self.conn.fetch("""
            SELECT doc_id, tender_id, file_url, file_name, extraction_status
            FROM documents
            WHERE extraction_status IN ('pending', 'auth_required', 'download_invalid')
              AND file_url IS NOT NULL
              AND file_url LIKE 'https://e-nabavki%'
            ORDER BY uploaded_at DESC NULLS LAST
            LIMIT $1
        """, limit)

        logger.info(f"Found {len(rows)} documents to re-download")
        return rows

    async def download_document(self, doc: dict) -> dict:
        """
        Download a single document with authentication.

        Returns status dict with success/failure info.
        """
        doc_id = doc['doc_id']
        file_url = doc['file_url']
        tender_id = doc['tender_id']

        self.stats['attempted'] += 1

        try:
            # Generate filename
            url_hash = hashlib.md5(file_url.encode()).hexdigest()[:8]
            safe_tender_id = str(tender_id).replace('/', '_')[:50]
            file_ext = '.pdf' if '.pdf' in file_url.lower() else '.bin'
            filename = f"{safe_tender_id}_{url_hash}{file_ext}"
            file_path = self.files_store / filename

            # Download with authentication
            logger.info(f"Downloading: {file_url[:80]}...")

            async with self.session.get(file_url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} for {doc_id}")
                    self.stats['download_failed'] += 1
                    return {'doc_id': doc_id, 'status': 'download_failed', 'http_status': response.status}

                # Stream download
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

            # Verify file
            actual_size = file_path.stat().st_size

            if actual_size < 100:
                logger.warning(f"File too small: {filename} ({actual_size} bytes)")
                file_path.unlink()
                self.stats['download_failed'] += 1
                return {'doc_id': doc_id, 'status': 'download_corrupted'}

            # Check if it's a login page (HTML instead of PDF)
            with open(file_path, 'rb') as f:
                file_header = f.read(1024)

            is_valid_pdf = file_header.startswith(b'%PDF')
            is_html = b'<html' in file_header.lower() or b'<!doctype' in file_header.lower()
            is_login = is_html and (b'login' in file_header.lower() or b'password' in file_header.lower())

            if is_login:
                logger.warning(f"⚠ Downloaded LOGIN PAGE: {filename}")
                file_path.unlink()
                self.stats['auth_required'] += 1
                return {'doc_id': doc_id, 'status': 'auth_required'}
            elif is_html and not is_valid_pdf:
                logger.warning(f"⚠ Downloaded HTML (not PDF): {filename}")
                file_path.unlink()
                self.stats['download_failed'] += 1
                return {'doc_id': doc_id, 'status': 'download_invalid'}

            # Calculate file hash
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            # Update database
            await self.conn.execute("""
                UPDATE documents
                SET file_path = $1,
                    file_name = $2,
                    file_size_bytes = $3,
                    file_hash = $4,
                    extraction_status = 'pending'
                WHERE doc_id = $5
            """, str(file_path), filename, actual_size, file_hash, doc_id)

            logger.info(f"✓ Downloaded: {filename} ({actual_size / 1024:.1f} KB)")
            self.stats['success'] += 1
            return {'doc_id': doc_id, 'status': 'success', 'file_path': str(file_path), 'size': actual_size}

        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading {doc_id}")
            self.stats['download_failed'] += 1
            return {'doc_id': doc_id, 'status': 'timeout'}
        except Exception as e:
            logger.error(f"Error downloading {doc_id}: {e}")
            self.stats['download_failed'] += 1
            return {'doc_id': doc_id, 'status': 'error', 'error': str(e)}

    async def process_batch(self, limit: int = 100, batch_size: int = 10):
        """
        Process documents in batches.
        """
        await self.connect()

        try:
            documents = await self.get_pending_documents(limit)

            if not documents:
                logger.info("No documents to re-download")
                return self.stats

            # Process in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(documents) + batch_size - 1) // batch_size

                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} documents)")

                # Download batch concurrently
                tasks = [self.download_document(dict(doc)) for doc in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Brief pause between batches to avoid rate limiting
                if i + batch_size < len(documents):
                    await asyncio.sleep(1)

            return self.stats

        finally:
            await self.close()


async def main():
    parser = argparse.ArgumentParser(description='Re-download pending documents with authentication')
    parser.add_argument('--limit', type=int, default=100, help='Maximum documents to process')
    parser.add_argument('--batch-size', type=int, default=10, help='Documents per batch')
    args = parser.parse_args()

    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    redownloader = DocumentRedownloader(database_url)
    stats = await redownloader.process_batch(limit=args.limit, batch_size=args.batch_size)

    print("\n" + "=" * 60)
    print("RE-DOWNLOAD COMPLETE")
    print("=" * 60)
    print(f"Attempted:       {stats['attempted']}")
    print(f"Successful:      {stats['success']}")
    print(f"Auth Required:   {stats['auth_required']}")
    print(f"Download Failed: {stats['download_failed']}")
    print(f"Skipped:         {stats['skipped']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
