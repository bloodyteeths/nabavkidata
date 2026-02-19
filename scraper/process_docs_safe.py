#!/usr/bin/env python3
"""
Safe document processor - downloads, extracts, and DELETES files.

Key features:
- Processes documents one at a time
- Deletes PDF immediately after successful extraction
- Checks disk space before each download
- Stops if disk space < 1GB

Usage:
    python3 process_docs_safe.py --limit 100
    python3 process_docs_safe.py --continuous  # Run until all done
"""

import os
import sys
import asyncio
import logging
import argparse
import shutil
from pathlib import Path
from datetime import datetime

import asyncpg
import aiohttp
import aiofiles

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from document_parser import parse_file, is_supported_document
except ImportError:
    parse_file = None
    is_supported_document = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('process_docs_safe.log')
    ]
)
logger = logging.getLogger(__name__)

# Config
DATABASE_URL = os.getenv('DATABASE_URL')
FILES_DIR = Path('/home/ubuntu/nabavkidata/scraper/downloads/files')
MIN_DISK_GB = 1.0  # Stop if less than 1GB free


def get_free_disk_gb() -> float:
    """Get free disk space in GB."""
    stat = shutil.disk_usage('/')
    return stat.free / (1024 ** 3)


async def download_file(session: aiohttp.ClientSession, url: str, filepath: Path) -> bool:
    """Download file from URL."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                logger.warning(f"Download failed: HTTP {resp.status}")
                return False

            async with aiofiles.open(filepath, 'wb') as f:
                async for chunk in resp.content.iter_chunked(8192):
                    await f.write(chunk)

            size_kb = filepath.stat().st_size / 1024
            logger.info(f"Downloaded: {filepath.name} ({size_kb:.1f} KB)")
            return True
    except Exception as e:
        logger.error(f"Download error: {e}")
        if filepath.exists():
            filepath.unlink()
        return False


def extract_text_from_pdf(filepath: Path) -> str:
    """Extract text from PDF using available methods."""
    text = ""

    # Method 1: Try document_parser if available
    if parse_file:
        try:
            result = parse_file(str(filepath))
            if result and result.text:
                return result.text
        except Exception as e:
            logger.debug(f"document_parser failed: {e}")

    # Method 2: Try PyMuPDF
    try:
        import fitz
        doc = fitz.open(str(filepath))
        for page in doc:
            text += page.get_text()
        doc.close()
        if text.strip():
            return text
    except Exception as e:
        logger.debug(f"PyMuPDF failed: {e}")

    # Method 3: Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(str(filepath)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except Exception as e:
        logger.debug(f"pdfplumber failed: {e}")

    # Method 4: Try Tesseract OCR
    try:
        import subprocess
        result = subprocess.run(
            ['tesseract', str(filepath), 'stdout', '-l', 'mkd+eng'],
            capture_output=True, text=True, timeout=120
        )
        if result.stdout.strip():
            return result.stdout
    except Exception as e:
        logger.debug(f"Tesseract failed: {e}")

    return text


async def process_document(conn: asyncpg.Connection, session: aiohttp.ClientSession, doc: dict) -> bool:
    """Process a single document: download, extract, delete."""
    doc_id = str(doc['doc_id'])  # Convert UUID to string
    file_url = doc['file_url']
    tender_id = doc['tender_id']

    # Generate filename
    safe_tender = tender_id.replace('/', '_')
    filename = f"{safe_tender}_{doc_id[:12]}.pdf"
    filepath = FILES_DIR / filename

    try:
        # Check disk space
        free_gb = get_free_disk_gb()
        if free_gb < MIN_DISK_GB:
            logger.error(f"Low disk space: {free_gb:.2f}GB < {MIN_DISK_GB}GB minimum")
            return False

        # Download
        if not await download_file(session, file_url, filepath):
            await conn.execute(
                "UPDATE documents SET extraction_status = 'download_failed' WHERE doc_id = $1",
                doc_id
            )
            return False

        # Extract text
        text = extract_text_from_pdf(filepath)

        # Delete file IMMEDIATELY after extraction
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted: {filename}")

        # Update database
        if text and len(text.strip()) > 50:
            await conn.execute("""
                UPDATE documents
                SET content_text = $1,
                    extraction_status = 'success',
                    extracted_at = NOW()
                WHERE doc_id = $2
            """, text[:500000], doc_id)  # Limit text size
            logger.info(f"✅ Extracted {len(text)} chars from {tender_id}")
            return True
        else:
            await conn.execute(
                "UPDATE documents SET extraction_status = 'failed' WHERE doc_id = $1",
                doc_id
            )
            logger.warning(f"❌ No text extracted from {tender_id}")
            return False

    except Exception as e:
        logger.error(f"Error processing {doc_id}: {e}")
        # Always clean up file
        if filepath.exists():
            filepath.unlink()
        await conn.execute(
            "UPDATE documents SET extraction_status = 'failed' WHERE doc_id = $1",
            doc_id
        )
        return False


async def get_pending_documents(conn: asyncpg.Connection, limit: int) -> list:
    """Get pending documents to process."""
    return await conn.fetch("""
        SELECT doc_id, tender_id, file_url, file_name
        FROM documents
        WHERE extraction_status = 'pending'
          AND file_url IS NOT NULL
          AND file_url != ''
          AND file_url LIKE 'http%'
        ORDER BY doc_id
        LIMIT $1
    """, limit)


async def run_processor(limit: int, continuous: bool = False):
    """Main processor loop."""
    logger.info(f"Starting safe document processor (limit={limit}, continuous={continuous})")

    FILES_DIR.mkdir(parents=True, exist_ok=True)

    conn = await asyncpg.connect(DATABASE_URL)
    logger.info("Connected to database")

    async with aiohttp.ClientSession() as session:
        total_processed = 0
        total_success = 0

        while True:
            # Check disk space
            free_gb = get_free_disk_gb()
            logger.info(f"Free disk space: {free_gb:.2f}GB")

            if free_gb < MIN_DISK_GB:
                logger.error(f"Stopping: disk space too low ({free_gb:.2f}GB)")
                break

            # Get pending documents
            docs = await get_pending_documents(conn, min(limit, 50))

            if not docs:
                if continuous:
                    logger.info("No pending documents. Waiting 60s...")
                    await asyncio.sleep(60)
                    continue
                else:
                    logger.info("No more pending documents.")
                    break

            logger.info(f"Processing batch of {len(docs)} documents")

            for doc in docs:
                success = await process_document(conn, session, doc)
                total_processed += 1
                if success:
                    total_success += 1

                # Progress log every 10
                if total_processed % 10 == 0:
                    logger.info(f"Progress: {total_processed} processed, {total_success} success ({100*total_success/total_processed:.0f}%)")

            if not continuous and total_processed >= limit:
                break

    await conn.close()

    logger.info(f"""
=== PROCESSING COMPLETE ===
Total processed: {total_processed}
Successful: {total_success}
Success rate: {100*total_success/total_processed:.1f}%
""")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Safe document processor')
    parser.add_argument('--limit', type=int, default=100, help='Max documents to process')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')

    args = parser.parse_args()

    asyncio.run(run_processor(args.limit, args.continuous))
