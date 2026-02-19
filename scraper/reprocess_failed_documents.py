#!/usr/bin/env python3
"""
Re-process failed documents after Tesseract OCR installation.

This script:
1. Finds documents with 'failed' or 'ocr_required' status
2. Re-downloads them (if URL available)
3. Re-extracts text using the updated parser (now with Tesseract OCR)
4. Updates database with extracted content
5. Deletes files after extraction to save space

Usage:
    python reprocess_failed_documents.py --limit 500
    python reprocess_failed_documents.py --status failed
    python reprocess_failed_documents.py --status ocr_required
"""

import asyncio
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
from datetime import datetime

import asyncpg
import aiohttp
import aiofiles

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from document_parser import parse_file, is_supported_document

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
def _normalize_db_url(url: str) -> str:
    if url.startswith('postgresql+asyncpg://'):
        return url.replace('postgresql+asyncpg://', 'postgresql://')
    return url

DATABASE_URL = _normalize_db_url(os.getenv(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
))
FILES_STORE = Path(os.getenv('FILES_STORE', '/home/ubuntu/nabavkidata/scraper/downloads/files'))
FILES_STORE.mkdir(parents=True, exist_ok=True)

# Load auth cookies
COOKIE_FILE = Path('/tmp/contracts_auth_cookies.json')


class FailedDocumentReprocessor:
    """Re-process documents that failed extraction"""

    def __init__(self):
        self.conn = None
        self.session = None
        self.stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
        }

    async def connect(self):
        """Connect to database and create HTTP session"""
        self.conn = await asyncpg.connect(DATABASE_URL)

        # Create session with auth cookies if available
        jar = aiohttp.CookieJar()
        self.session = aiohttp.ClientSession(cookie_jar=jar, timeout=aiohttp.ClientTimeout(total=300))

        if COOKIE_FILE.exists():
            try:
                with open(COOKIE_FILE, 'r') as f:
                    cookies = json.load(f)
                for cookie in cookies:
                    domain = cookie.get('domain', 'e-nabavki.gov.mk').lstrip('.')
                    self.session.cookie_jar.update_cookies(
                        {cookie['name']: cookie['value']},
                        aiohttp.yarl.URL(f"https://{domain}/")
                    )
                logger.info(f"Loaded {len(cookies)} auth cookies")
            except Exception as e:
                logger.warning(f"Could not load auth cookies: {e}")

        logger.info("Connected to database")

    async def close(self):
        """Close connections"""
        if self.session:
            await self.session.close()
        if self.conn:
            await self.conn.close()
        logger.info("Connections closed")

    async def get_failed_documents(self, statuses: list, limit: int) -> list:
        """Get documents that need reprocessing"""
        status_placeholders = ', '.join(f"${i+2}" for i in range(len(statuses)))
        query = f"""
            SELECT doc_id, tender_id, file_url, file_name, extraction_status
            FROM documents
            WHERE extraction_status IN ({status_placeholders})
              AND file_url IS NOT NULL
              AND file_url NOT LIKE '%ohridskabanka%'
            ORDER BY doc_id
            LIMIT $1
        """
        rows = await self.conn.fetch(query, limit, *statuses)
        logger.info(f"Found {len(rows)} documents to reprocess")
        return [dict(r) for r in rows]

    def _get_extension(self, url: str) -> str:
        """Get file extension from URL"""
        url_lower = url.lower()
        for ext in ['.docx', '.doc', '.xlsx', '.xls', '.pdf']:
            if ext in url_lower:
                return ext
        return '.pdf'

    async def download_document(self, doc: dict) -> Path:
        """Download document file"""
        file_url = doc['file_url']
        tender_id = doc.get('tender_id', 'unknown').replace('/', '_')

        url_hash = hashlib.md5(file_url.encode()).hexdigest()[:12]
        ext = self._get_extension(file_url)
        filename = f"{tender_id}_{url_hash}{ext}"
        file_path = FILES_STORE / filename

        # Download
        try:
            async with self.session.get(file_url) as response:
                if response.status != 200:
                    logger.warning(f"Download failed: HTTP {response.status}")
                    return None

                content = await response.read()

                # Check if it's HTML (auth failed)
                if b'<!DOCTYPE' in content[:200] or b'<html' in content[:200].lower():
                    logger.warning(f"Got HTML instead of file (auth required): {filename}")
                    return None

                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(content)

                logger.info(f"Downloaded: {filename} ({len(content) / 1024:.1f} KB)")
                return file_path

        except Exception as e:
            logger.error(f"Download error: {e}")
            return None

    async def extract_and_update(self, doc: dict, file_path: Path) -> bool:
        """Extract text from document and update database"""
        doc_id = doc['doc_id']

        try:
            if not is_supported_document(str(file_path)):
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return False

            result = parse_file(str(file_path))

            if not result.text or len(result.text.strip()) < 50:
                logger.warning(f"Extraction produced minimal text ({len(result.text) if result.text else 0} chars)")
                await self.conn.execute("""
                    UPDATE documents SET extraction_status = 'failed', updated_at = NOW()
                    WHERE doc_id = $1
                """, doc_id)
                return False

            # Build metadata with full tables data
            metadata = {
                'engine_used': result.engine_used,
                'has_tables': result.has_tables,
                'table_count': len(result.tables),
                'tables': result.tables,  # Store actual table data as raw JSON
                'cpv_codes': result.cpv_codes,
                'company_names': result.company_names,
                'emails': result.emails,
                'phones': result.phones,
                'reprocessed_at': datetime.utcnow().isoformat(),
            }

            # Update database
            await self.conn.execute("""
                UPDATE documents SET
                    content_text = $1,
                    extraction_status = 'success',
                    page_count = $2,
                    specifications_json = $3,
                    extracted_at = NOW(),
                    updated_at = NOW()
                WHERE doc_id = $4
            """,
                result.text,
                result.page_count,
                json.dumps(metadata, ensure_ascii=False),
                doc_id
            )

            logger.info(f"✅ Extracted {len(result.text)} chars using {result.engine_used}")
            return True

        except Exception as e:
            logger.error(f"Extraction error: {e}")
            await self.conn.execute("""
                UPDATE documents SET extraction_status = 'failed', updated_at = NOW()
                WHERE doc_id = $1
            """, doc_id)
            return False

        finally:
            # Always delete file after processing
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"🗑️ Deleted file: {file_path.name}")
            except Exception as e:
                logger.warning(f"Could not delete file: {e}")

    async def process_document(self, doc: dict) -> bool:
        """Process a single document"""
        doc_id = doc['doc_id']
        logger.info(f"Processing: {doc_id} ({doc.get('file_name', 'unknown')})")

        # Download
        file_path = await self.download_document(doc)
        if not file_path:
            # Mark as auth_required if download failed
            await self.conn.execute("""
                UPDATE documents SET extraction_status = 'auth_required', updated_at = NOW()
                WHERE doc_id = $1
            """, doc_id)
            return False

        # Extract and update
        success = await self.extract_and_update(doc, file_path)
        return success

    async def run(self, statuses: list, limit: int):
        """Main run loop"""
        await self.connect()

        try:
            docs = await self.get_failed_documents(statuses, limit)

            for i, doc in enumerate(docs):
                self.stats['processed'] += 1

                if await self.process_document(doc):
                    self.stats['success'] += 1
                else:
                    self.stats['failed'] += 1

                # Progress log every 10 docs
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i+1}/{len(docs)} | Success: {self.stats['success']} | Failed: {self.stats['failed']}")

                # Small delay
                await asyncio.sleep(0.2)

            logger.info(f"\n{'='*50}")
            logger.info(f"REPROCESSING COMPLETE")
            logger.info(f"{'='*50}")
            logger.info(f"Processed: {self.stats['processed']}")
            logger.info(f"Success: {self.stats['success']}")
            logger.info(f"Failed: {self.stats['failed']}")
            logger.info(f"{'='*50}")

        finally:
            await self.close()


async def main():
    parser = argparse.ArgumentParser(description='Reprocess failed documents')
    parser.add_argument('--limit', '-l', type=int, default=500,
                       help='Maximum documents to process')
    parser.add_argument('--status', '-s', action='append', dest='statuses',
                       default=[],
                       help='Extraction status to reprocess (can use multiple times)')
    args = parser.parse_args()

    # Default statuses if none specified
    if not args.statuses:
        args.statuses = ['failed', 'ocr_required']

    reprocessor = FailedDocumentReprocessor()
    await reprocessor.run(args.statuses, args.limit)


if __name__ == '__main__':
    asyncio.run(main())
