#!/usr/bin/env python3
"""
Backfill document URLs from raw_data_json for documents that are missing file_url.

This script:
1. Finds tenders with raw_data_json->documents_data
2. Checks for documents in the documents table that have no file_url
3. Updates documents with the URL from raw_data_json

Usage:
    python backfill_document_urls.py [--limit N] [--dry-run]
"""
import asyncio
import argparse
import logging
import os
import json
from typing import Optional

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


async def backfill_urls(limit: Optional[int] = None, dry_run: bool = False):
    """Backfill missing document URLs from raw_data_json"""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Find tenders with documents_data in raw_data_json
        query = """
            SELECT
                t.tender_id,
                t.raw_data_json->'documents_data' as documents_data
            FROM tenders t
            WHERE t.raw_data_json IS NOT NULL
              AND t.raw_data_json->'documents_data' IS NOT NULL
              AND jsonb_array_length(t.raw_data_json->'documents_data') > 0
              AND EXISTS (
                  SELECT 1 FROM documents d
                  WHERE d.tender_id = t.tender_id
                  AND (d.file_url IS NULL OR d.file_url = '')
              )
        """
        if limit:
            query += f" LIMIT {limit}"

        tenders = await conn.fetch(query)
        logger.info(f"Found {len(tenders)} tenders with documents needing URL backfill")

        updated_count = 0
        inserted_count = 0
        skipped_count = 0

        for row in tenders:
            tender_id = row['tender_id']
            docs_data = row['documents_data']

            if not docs_data:
                continue

            # Parse JSON if needed
            if isinstance(docs_data, str):
                docs_data = json.loads(docs_data)

            for doc in docs_data:
                if not isinstance(doc, dict):
                    continue

                file_url = doc.get('url') or doc.get('file_url')
                file_name = doc.get('file_name')

                if not file_url:
                    continue

                # Try to update existing document by file_name
                if file_name:
                    if dry_run:
                        logger.info(f"[DRY-RUN] Would update {tender_id}: {file_name} -> {file_url[:80]}...")
                        updated_count += 1
                    else:
                        # Check if URL already exists for this tender
                        existing_url = await conn.fetchval("""
                            SELECT doc_id FROM documents
                            WHERE tender_id = $1 AND file_url = $2
                        """, tender_id, file_url)

                        if existing_url:
                            skipped_count += 1
                            continue

                        result = await conn.execute("""
                            UPDATE documents
                            SET file_url = $1
                            WHERE tender_id = $2
                              AND file_name = $3
                              AND (file_url IS NULL OR file_url = '')
                        """, file_url, tender_id, file_name)

                        if 'UPDATE 1' in result:
                            updated_count += 1
                            logger.info(f"Updated {tender_id}: {file_name}")
                        else:
                            # Document doesn't exist - insert it
                            try:
                                await conn.execute("""
                                    INSERT INTO documents (tender_id, file_name, file_url, doc_type, extraction_status)
                                    VALUES ($1, $2, $3, $4, 'pending')
                                    ON CONFLICT DO NOTHING
                                """, tender_id, file_name, file_url, doc.get('doc_category') or 'document')
                                inserted_count += 1
                                logger.info(f"Inserted {tender_id}: {file_name}")
                            except Exception as e:
                                logger.warning(f"Failed to insert {tender_id}/{file_name}: {e}")
                                skipped_count += 1

        logger.info(f"Backfill complete: {updated_count} updated, {inserted_count} inserted, {skipped_count} skipped")

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description='Backfill document URLs from raw_data_json')
    parser.add_argument('--limit', type=int, help='Limit number of tenders to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    await backfill_urls(limit=args.limit, dry_run=args.dry_run)


if __name__ == '__main__':
    asyncio.run(main())
