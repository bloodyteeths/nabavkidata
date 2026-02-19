#!/usr/bin/env python3
"""
Extract text from ePazar documents (PDFs).

Downloads PDFs from e-pazar.gov.mk and extracts text content
to make them searchable and available for AI analysis.
"""

import os
import sys
import json
import asyncio
import logging
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, Dict, List
import argparse
from dotenv import load_dotenv
load_dotenv()


# Add parent directory to path
sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata')
sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata/scraper')

import asyncpg
import httpx

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com',
    'port': 5432,
    'user': 'nabavki_user',
    'password': os.getenv('DB_PASSWORD', ''),
    'database': 'nabavkidata',
}


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """Extract text from PDF using multiple methods"""
    text = None

    # Try PyMuPDF (fitz) first - fast and reliable
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        text = '\n'.join(text_parts)
        if text and len(text.strip()) > 100:
            return text.strip()
    except Exception as e:
        logger.debug(f"PyMuPDF failed: {e}")

    # Try pdfminer as fallback
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(pdf_path)
        if text and len(text.strip()) > 100:
            return text.strip()
    except Exception as e:
        logger.debug(f"pdfminer failed: {e}")

    # Return whatever we got
    return text.strip() if text else None


async def download_pdf(url: str, timeout: int = 30) -> Optional[bytes]:
    """Download PDF from URL"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; nabavkidata-bot/1.0)',
                'Accept': 'application/pdf,*/*'
            })

            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'pdf' in content_type.lower() or response.content[:4] == b'%PDF':
                    return response.content
                else:
                    logger.warning(f"Not a PDF: {url} (content-type: {content_type})")
            else:
                logger.warning(f"Download failed: {url} (status: {response.status_code})")
    except Exception as e:
        logger.error(f"Download error for {url}: {e}")

    return None


async def process_document(doc: Dict, conn: asyncpg.Connection) -> Dict:
    """Process a single document: download, extract, update DB"""
    doc_id = doc['doc_id']
    file_url = doc['file_url']
    tender_id = doc['tender_id']

    result = {
        'doc_id': doc_id,
        'success': False,
        'status': 'pending',
        'content_length': 0,
        'error': None
    }

    try:
        # Download PDF
        logger.info(f"Downloading: {file_url}")
        pdf_content = await download_pdf(file_url)

        if not pdf_content:
            result['status'] = 'download_failed'
            result['error'] = 'Failed to download'
            await conn.execute("""
                UPDATE epazar_documents
                SET extraction_status = $1, file_size_bytes = 0
                WHERE doc_id = $2
            """, 'download_failed', doc_id)
            return result

        file_size = len(pdf_content)
        file_hash = hashlib.sha256(pdf_content).hexdigest()

        # Save to temp file and extract
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(pdf_content)
            tmp_path = tmp.name

        try:
            text = extract_text_from_pdf(tmp_path)
        finally:
            os.unlink(tmp_path)

        if text and len(text) > 50:
            # Success - update with extracted content
            await conn.execute("""
                UPDATE epazar_documents
                SET content_text = $1,
                    extraction_status = 'success',
                    file_size_bytes = $2,
                    file_hash = $3
                WHERE doc_id = $4
            """, text, file_size, file_hash, doc_id)

            result['success'] = True
            result['status'] = 'success'
            result['content_length'] = len(text)
            logger.info(f"  ✓ Extracted {len(text)} chars from {doc['file_name']}")
        else:
            # Extraction failed (maybe scanned PDF)
            await conn.execute("""
                UPDATE epazar_documents
                SET extraction_status = 'ocr_required',
                    file_size_bytes = $1,
                    file_hash = $2
                WHERE doc_id = $3
            """, file_size, file_hash, doc_id)

            result['status'] = 'ocr_required'
            result['error'] = 'No text extracted - may need OCR'
            logger.info(f"  ⚠ No text in {doc['file_name']} - may need OCR")

    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
        logger.error(f"  ✗ Error processing {doc['file_name']}: {e}")

        await conn.execute("""
            UPDATE epazar_documents
            SET extraction_status = 'failed'
            WHERE doc_id = $1
        """, doc_id)

    return result


async def main(limit: int = None, dry_run: bool = False):
    """Main extraction loop"""

    # Connect to database
    conn = await asyncpg.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database']
    )

    try:
        # Get pending documents
        query = """
            SELECT doc_id, tender_id, file_name, file_url
            FROM epazar_documents
            WHERE extraction_status = 'pending'
              AND file_url IS NOT NULL
              AND file_url != ''
            ORDER BY tender_id DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        docs = await conn.fetch(query)
        logger.info(f"Found {len(docs)} pending ePazar documents")

        if dry_run:
            for doc in docs[:10]:
                print(f"Would process: {doc['tender_id']} - {doc['file_name']}")
                print(f"  URL: {doc['file_url']}")
            return

        # Process documents
        stats = {'processed': 0, 'success': 0, 'failed': 0}

        for i, doc in enumerate(docs):
            logger.info(f"[{i+1}/{len(docs)}] Processing {doc['tender_id']}: {doc['file_name']}")

            result = await process_document(dict(doc), conn)
            stats['processed'] += 1

            if result['success']:
                stats['success'] += 1
            else:
                stats['failed'] += 1

            # Progress update every 10 docs
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{len(docs)} - Success: {stats['success']}, Failed: {stats['failed']}")

            # Rate limiting
            await asyncio.sleep(0.5)

        # Final summary
        print("\n" + "=" * 60)
        print("EPAZAR DOCUMENT EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"Processed: {stats['processed']}")
        print(f"Success: {stats['success']}")
        print(f"Failed: {stats['failed']}")
        print("=" * 60)

    finally:
        await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract text from ePazar PDFs')
    parser.add_argument('--limit', type=int, default=None, help='Max documents to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, dry_run=args.dry_run))
