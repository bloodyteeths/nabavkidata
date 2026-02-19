#!/usr/bin/env python3
"""
Backfill PDF extraction for existing documents.
Processes documents with file_path but no specifications_json.
"""
import os
import json
import asyncio
import logging
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


async def process_documents(limit: int = 100, batch_size: int = 10):
    """Process documents that need PDF extraction."""
    conn = await asyncpg.connect(DATABASE_URL)
    parser = ResilientDocumentParser()

    try:
        # Get documents that have file_path but no specifications_json
        # and where file_path contains .pdf
        docs = await conn.fetch("""
            SELECT doc_id, tender_id, file_name, file_path, file_url
            FROM documents
            WHERE file_path IS NOT NULL
              AND file_path != ''
              AND (specifications_json IS NULL OR specifications_json::text = '{}')
              AND LOWER(file_name) LIKE '%%.pdf'
            ORDER BY doc_id
            LIMIT $1
        """, limit)

        logger.info(f"Found {len(docs)} documents to process")

        processed = 0
        errors = 0

        for doc in docs:
            doc_id = doc['doc_id']
            file_path = doc['file_path']
            file_name = doc['file_name']

            # Check if file exists
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path} for doc_id={doc_id}")
                errors += 1
                continue

            try:
                # Extract PDF content
                logger.info(f"Processing doc_id={doc_id}: {file_name}")
                result = parser.parse_document(file_path)

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

        logger.info(f"Completed: processed={processed}, errors={errors}")

    finally:
        await conn.close()


async def check_status():
    """Check current extraction status."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN specifications_json IS NOT NULL AND specifications_json::text != '{}' THEN 1 END) as has_specs,
                COUNT(CASE WHEN content_text IS NOT NULL AND content_text != '' THEN 1 END) as has_text,
                COUNT(CASE WHEN file_path IS NOT NULL AND file_path != '' THEN 1 END) as has_file,
                COUNT(CASE WHEN LOWER(file_name) LIKE '%%.pdf' THEN 1 END) as is_pdf
            FROM documents
        """)

        print(f"""
Document Extraction Status:
--------------------------
Total documents: {stats['total']}
Has specifications_json: {stats['has_specs']}
Has content_text: {stats['has_text']}
Has file_path: {stats['has_file']}
Is PDF: {stats['is_pdf']}
        """)

        # Sample documents with specifications_json
        samples = await conn.fetch("""
            SELECT doc_id, file_name,
                   LEFT(specifications_json::text, 200) as specs_preview
            FROM documents
            WHERE specifications_json IS NOT NULL
              AND specifications_json::text != '{}'
            LIMIT 3
        """)

        if samples:
            print("Sample documents with extracted specs:")
            for s in samples:
                print(f"  - doc_id={s['doc_id']}: {s['file_name']}")
                print(f"    specs: {s['specs_preview']}...")

    finally:
        await conn.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        asyncio.run(check_status())
    else:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
        asyncio.run(process_documents(limit=limit))
