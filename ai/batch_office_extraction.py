#!/usr/bin/env python3
"""
Batch Office Document Extraction Script for Nabavkidata

Process Word (DOCX, DOC) and Excel (XLSX, XLS) documents to extract:
- Tables with structured data
- Bill of Quantities (BOQ) items
- Price lists and specifications
- Bidder information

Usage:
    python ai/batch_office_extraction.py --all-pending     # Process all pending Office docs
    python ai/batch_office_extraction.py --file document.xlsx --tender-id 12345_2025
    python ai/batch_office_extraction.py --directory scraper/downloads/files/ --limit 50
    python ai/batch_office_extraction.py --file-type xlsx   # Process only Excel files
"""

import os
import sys
import asyncio
import asyncpg
import argparse
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai.office_extraction import extract_from_office_document

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchOfficeExtractor:
    """
    Batch processing for Office document extraction
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'total_tables': 0,
            'total_items': 0,
            'by_type': {
                'docx': {'processed': 0, 'success': 0, 'items': 0},
                'doc': {'processed': 0, 'success': 0, 'items': 0},
                'xlsx': {'processed': 0, 'success': 0, 'items': 0},
                'xls': {'processed': 0, 'success': 0, 'items': 0},
            },
            'errors': []
        }

    async def process_file(
        self,
        file_path: str,
        tender_id: Optional[str] = None,
        doc_id: Optional[int] = None
    ) -> Dict:
        """
        Process a single Office document

        Args:
            file_path: Path to Office document
            tender_id: Optional tender ID
            doc_id: Optional document ID from database

        Returns:
            Processing result dict
        """
        logger.info(f"Processing: {os.path.basename(file_path)}")

        ext = os.path.splitext(file_path)[1].lower().replace('.', '')

        try:
            # Extract tables and items
            result = extract_from_office_document(file_path)

            # Update stats
            self.stats['total_processed'] += 1
            self.stats['by_type'][ext]['processed'] += 1

            if result['items'] or result['tables']:
                # Store in database
                stored_items = await self._store_results(
                    result,
                    tender_id=tender_id,
                    doc_id=doc_id
                )

                self.stats['successful'] += 1
                self.stats['by_type'][ext]['success'] += 1
                self.stats['total_tables'] += result['metadata']['table_count']
                self.stats['total_items'] += stored_items
                self.stats['by_type'][ext]['items'] += stored_items

                logger.info(
                    f"Success: {result['metadata']['table_count']} tables, "
                    f"{stored_items} items stored"
                )

                return {
                    'success': True,
                    'tables': result['metadata']['table_count'],
                    'items': stored_items,
                    'file_path': file_path
                }
            else:
                logger.warning(f"No extractable data found in {os.path.basename(file_path)}")
                return {
                    'success': False,
                    'error': 'No extractable data',
                    'file_path': file_path
                }

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
            self.stats['failed'] += 1
            self.stats['errors'].append({
                'file': file_path,
                'error': str(e)
            })
            return {
                'success': False,
                'error': str(e),
                'file_path': file_path
            }

    async def _store_results(
        self,
        result: Dict,
        tender_id: Optional[str] = None,
        doc_id: Optional[int] = None
    ) -> int:
        """
        Store extraction results in database

        Returns:
            Number of items stored
        """
        items_stored = 0

        # If we don't have tender_id but have doc_id, get it from database
        if not tender_id and doc_id:
            tender_id = await self._get_tender_id(doc_id)

        if not tender_id:
            # Try to extract from filename
            filename = result['metadata']['file_name']
            tender_id = self._extract_tender_id_from_filename(filename)

        if not tender_id:
            logger.warning("No tender_id available - items will not be stored")
            return 0

        # Store items
        for item in result['items']:
            try:
                await self.pool.execute(
                    """
                    INSERT INTO product_items (
                        tender_id,
                        name,
                        quantity,
                        unit,
                        unit_price,
                        total_price,
                        specifications,
                        extraction_method,
                        extraction_confidence,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT DO NOTHING
                    """,
                    tender_id,
                    item['item_name'],
                    item['quantity'],
                    item['unit'],
                    item['unit_price'],
                    item['total_price'],
                    item['specifications'],
                    f"office_{item['extraction_source']}",  # e.g., 'office_excel'
                    item['confidence'],
                    json.dumps({
                        'source_sheet': item['source_sheet'],
                        'table_index': item['table_index'],
                        'table_type': item['table_type'],
                        'item_number': item['item_number']
                    })
                )
                items_stored += 1
            except Exception as e:
                logger.error(f"Error storing item: {e}")

        # Update document status if doc_id provided
        if doc_id:
            try:
                await self.pool.execute(
                    """
                    UPDATE documents
                    SET extraction_status = 'success',
                        content_text = $2,
                        specifications_json = $3,
                        processed_at = NOW()
                    WHERE doc_id = $1
                    """,
                    doc_id,
                    result['text'][:50000] if result['text'] else None,  # Limit text size
                    json.dumps(result['metadata'])
                )
            except Exception as e:
                logger.warning(f"Could not update document status: {e}")

        return items_stored

    async def _get_tender_id(self, doc_id: int) -> Optional[str]:
        """Get tender_id from document ID"""
        try:
            row = await self.pool.fetchrow(
                "SELECT tender_id FROM documents WHERE doc_id = $1",
                doc_id
            )
            return row['tender_id'] if row else None
        except Exception as e:
            logger.error(f"Error getting tender_id: {e}")
            return None

    def _extract_tender_id_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract tender_id from filename pattern like: 12345_2025_hash.xlsx
        """
        import re
        match = re.match(r'^(\d+_\d{4})', filename)
        return match.group(1) if match else None

    async def process_pending_documents(
        self,
        file_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Process all pending Office documents from database

        Args:
            file_type: Filter by extension (docx, doc, xlsx, xls)
            limit: Maximum number to process

        Returns:
            Summary statistics
        """
        logger.info("Fetching pending Office documents from database...")

        # Build query
        query = """
            SELECT doc_id, tender_id, file_path, file_name
            FROM documents
            WHERE extraction_status = 'pending'
        """

        if file_type:
            query += f" AND LOWER(file_name) LIKE '%.{file_type.lower()}'"
        else:
            query += """
                AND (LOWER(file_name) LIKE '%.docx'
                     OR LOWER(file_name) LIKE '%.doc'
                     OR LOWER(file_name) LIKE '%.xlsx'
                     OR LOWER(file_name) LIKE '%.xls')
            """

        query += " ORDER BY doc_id"

        if limit:
            query += f" LIMIT {limit}"

        try:
            docs = await self.pool.fetch(query)
            logger.info(f"Found {len(docs)} pending Office documents")

            for idx, doc in enumerate(docs, 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing document {idx}/{len(docs)}")
                logger.info(f"{'='*60}")

                await self.process_file(
                    doc['file_path'],
                    tender_id=doc['tender_id'],
                    doc_id=doc['doc_id']
                )

            return self.stats

        except Exception as e:
            logger.error(f"Error fetching pending documents: {e}", exc_info=True)
            return self.stats

    async def process_directory(
        self,
        directory: str,
        file_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Process all Office documents in a directory

        Args:
            directory: Directory path to scan
            file_type: Filter by extension (docx, doc, xlsx, xls)
            limit: Maximum number to process

        Returns:
            Summary statistics
        """
        logger.info(f"Scanning directory: {directory}")

        extensions = [f'.{file_type}'] if file_type else ['.docx', '.doc', '.xlsx', '.xls']
        files = []

        for ext in extensions:
            files.extend(Path(directory).glob(f'**/*{ext}'))

        files = sorted(files)[:limit] if limit else sorted(files)

        logger.info(f"Found {len(files)} Office documents")

        for idx, file_path in enumerate(files, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing file {idx}/{len(files)}")
            logger.info(f"{'='*60}")

            await self.process_file(str(file_path))

        return self.stats

    def print_summary(self):
        """Print processing summary"""
        print(f"\n{'='*60}")
        print("BATCH OFFICE EXTRACTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total Processed: {self.stats['total_processed']}")
        print(f"Successful: {self.stats['successful']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Total Tables: {self.stats['total_tables']}")
        print(f"Total Items Extracted: {self.stats['total_items']}")
        print(f"\nBy File Type:")
        for ftype, data in self.stats['by_type'].items():
            if data['processed'] > 0:
                print(f"  {ftype.upper()}: {data['processed']} processed, "
                      f"{data['success']} success, {data['items']} items")

        if self.stats['errors']:
            print(f"\nErrors ({len(self.stats['errors'])}):")
            for err in self.stats['errors'][:10]:  # Show first 10
                print(f"  - {os.path.basename(err['file'])}: {err['error']}")

        print(f"{'='*60}\n")


async def main():
    parser = argparse.ArgumentParser(
        description='Batch process Office documents for Nabavkidata'
    )
    parser.add_argument(
        '--file',
        help='Process a single file'
    )
    parser.add_argument(
        '--directory',
        help='Process all Office documents in directory'
    )
    parser.add_argument(
        '--all-pending',
        action='store_true',
        help='Process all pending documents from database'
    )
    parser.add_argument(
        '--tender-id',
        help='Tender ID for single file processing'
    )
    parser.add_argument(
        '--file-type',
        choices=['docx', 'doc', 'xlsx', 'xls'],
        help='Filter by file type'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of documents to process'
    )
    parser.add_argument(
        '--db-host',
        default='localhost',
        help='Database host'
    )
    parser.add_argument(
        '--db-name',
        default='nabavkidata',
        help='Database name'
    )
    parser.add_argument(
        '--db-user',
        default='postgres',
        help='Database user'
    )
    parser.add_argument(
        '--db-password',
        default='postgres',
        help='Database password'
    )

    args = parser.parse_args()

    # Connect to database
    logger.info("Connecting to database...")
    pool = await asyncpg.create_pool(
        host=args.db_host,
        database=args.db_name,
        user=args.db_user,
        password=args.db_password,
        min_size=1,
        max_size=5
    )

    try:
        extractor = BatchOfficeExtractor(pool)

        if args.file:
            # Process single file
            await extractor.process_file(
                args.file,
                tender_id=args.tender_id
            )
        elif args.directory:
            # Process directory
            await extractor.process_directory(
                args.directory,
                file_type=args.file_type,
                limit=args.limit
            )
        elif args.all_pending:
            # Process all pending from database
            await extractor.process_pending_documents(
                file_type=args.file_type,
                limit=args.limit
            )
        else:
            parser.print_help()
            return

        # Print summary
        extractor.print_summary()

    finally:
        await pool.close()
        logger.info("Database connection closed")


if __name__ == '__main__':
    asyncio.run(main())
