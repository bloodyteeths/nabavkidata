#!/usr/bin/env python3
"""
Process PDFs from URLs in the database.
Downloads PDFs from file_url and extracts content/specifications.
"""
import os
import json
import asyncio
import logging
import tempfile
import aiohttp
import asyncpg
from pathlib import Path
from document_parser import ResilientDocumentParser
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


async def download_pdf(session: aiohttp.ClientSession, url: str, temp_dir: str) -> str | None:
    """Download PDF to temp directory, return path or None on failure."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            if resp.status == 200:
                content = await resp.read()
                if len(content) < 100:
                    logger.warning(f"PDF too small ({len(content)} bytes): {url}")
                    return None

                # Generate filename from URL
                filename = url.split('/')[-1].split('?')[0]
                if not filename.lower().endswith('.pdf'):
                    filename = f"{hash(url)}.pdf"

                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(content)
                return filepath
            else:
                logger.warning(f"Failed to download {url}: status {resp.status}")
                return None
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return None


async def process_documents(limit: int = 100):
    """Process documents that have file_url but no specifications_json."""
    conn = await asyncpg.connect(DATABASE_URL)
    parser = ResilientDocumentParser()

    # Create temp directory for downloads
    temp_dir = tempfile.mkdtemp(prefix='nabavki_pdf_')
    logger.info(f"Using temp directory: {temp_dir}")

    try:
        # Get documents that have file_url but no specifications_json
        docs = await conn.fetch("""
            SELECT doc_id, tender_id, file_name, file_url
            FROM documents
            WHERE file_url IS NOT NULL
              AND file_url != ''
              AND (specifications_json IS NULL OR specifications_json::text = '{}')
              AND LOWER(file_name) LIKE '%%.pdf'
            ORDER BY doc_id
            LIMIT $1
        """, limit)

        logger.info(f"Found {len(docs)} documents to process")

        processed = 0
        errors = 0

        async with aiohttp.ClientSession() as session:
            for doc in docs:
                doc_id = doc['doc_id']
                file_url = doc['file_url']
                file_name = doc['file_name']

                logger.info(f"Processing doc_id={doc_id}: {file_name}")

                # Download PDF
                filepath = await download_pdf(session, file_url, temp_dir)
                if not filepath:
                    logger.warning(f"Could not download: {file_url}")
                    errors += 1
                    continue

                try:
                    # Extract PDF content
                    result = parser.parse_document(filepath)

                    # Build metadata
                    metadata = {
                        'engine_used': result.engine_used,
                        'has_tables': result.has_tables,
                        'table_count': len(result.tables),
                        'cpv_codes': result.cpv_codes,
                        'company_names': result.company_names,
                        'emails': result.emails,
                        'phones': result.phones,
                    }

                    # Update document
                    await conn.execute("""
                        UPDATE documents
                        SET content_text = $2,
                            extraction_status = 'success',
                            specifications_json = $3
                        WHERE doc_id = $1
                    """, doc_id, result.text[:500000] if result.text else '', json.dumps(metadata, ensure_ascii=False))

                    processed += 1
                    logger.info(
                        f"✓ Extracted doc_id={doc_id}: {len(result.text or '')} chars, "
                        f"CPV: {len(result.cpv_codes)}, Companies: {len(result.company_names)}, "
                        f"Emails: {len(result.emails)}, Phones: {len(result.phones)}"
                    )

                except Exception as e:
                    logger.error(f"Error processing doc_id={doc_id}: {e}")
                    await conn.execute("""
                        UPDATE documents
                        SET extraction_status = 'failed'
                        WHERE doc_id = $1
                    """, doc_id)
                    errors += 1

                finally:
                    # Clean up downloaded file
                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)

        logger.info(f"Completed: processed={processed}, errors={errors}")

    finally:
        await conn.close()
        # Clean up temp directory
        try:
            os.rmdir(temp_dir)
        except:
            pass


async def check_status():
    """Check current extraction status."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN specifications_json IS NOT NULL AND specifications_json::text != '{}' THEN 1 END) as has_specs,
                COUNT(CASE WHEN content_text IS NOT NULL AND content_text != '' THEN 1 END) as has_text,
                COUNT(CASE WHEN file_url IS NOT NULL AND file_url != '' THEN 1 END) as has_url,
                COUNT(CASE WHEN LOWER(file_name) LIKE '%%.pdf' THEN 1 END) as is_pdf
            FROM documents
        """)

        # Count PDFs with URL but no specs
        need_processing = await conn.fetchval("""
            SELECT COUNT(*)
            FROM documents
            WHERE file_url IS NOT NULL
              AND file_url != ''
              AND (specifications_json IS NULL OR specifications_json::text = '{}')
              AND LOWER(file_name) LIKE '%%.pdf'
        """)

        print(f"""
Document Extraction Status:
--------------------------
Total documents: {stats['total']}
Has specifications_json: {stats['has_specs']}
Has content_text: {stats['has_text']}
Has file_url: {stats['has_url']}
Is PDF: {stats['is_pdf']}

PDFs needing extraction: {need_processing}
        """)

        # Sample documents needing processing
        samples = await conn.fetch("""
            SELECT doc_id, file_name, file_url
            FROM documents
            WHERE file_url IS NOT NULL
              AND file_url != ''
              AND (specifications_json IS NULL OR specifications_json::text = '{}')
              AND LOWER(file_name) LIKE '%%.pdf'
            LIMIT 5
        """)

        if samples:
            print("Sample PDFs to process:")
            for s in samples:
                print(f"  - doc_id={s['doc_id']}: {s['file_name']}")
                print(f"    URL: {s['file_url'][:80]}...")

    finally:
        await conn.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        asyncio.run(check_status())
    else:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
        asyncio.run(process_documents(limit=limit))
