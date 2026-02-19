#!/usr/bin/env python3
"""
Batch Table Extraction Script

Process multiple PDFs and store extracted tables/items in database.
Useful for backfilling existing documents or batch processing new uploads.

Usage:
    python ai/batch_table_extraction.py --directory scraper/downloads/files/
    python ai/batch_table_extraction.py --file tender.pdf --tender-id 12345_2025
    python ai/batch_table_extraction.py --all-documents  # Process all documents from DB
"""

import os
import sys
import asyncio
import asyncpg
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai.table_storage import TableStorage, store_pdf_tables
from ai.table_extraction import extract_tables_from_pdf

logger = logging.getLogger(__name__)


class BatchTableExtractor:
    """
    Batch processing for table extraction
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
        self.storage = TableStorage(db_pool)
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'total_tables': 0,
            'total_items': 0,
            'errors': []
        }

    async def process_file(
        self,
        pdf_path: str,
        tender_id: Optional[str] = None,
        doc_id: Optional[str] = None
    ) -> Dict:
        """
        Process a single PDF file

        Args:
            pdf_path: Path to PDF
            tender_id: Optional tender ID
            doc_id: Optional document ID

        Returns:
            Processing result
        """
        logger.info(f"Processing: {pdf_path}")

        try:
            result = await self.storage.process_and_store_pdf(
                pdf_path,
                tender_id=tender_id,
                doc_id=doc_id
            )

            self.stats['total_processed'] += 1
            self.stats['successful'] += 1
            self.stats['total_tables'] += result['tables_stored']
            self.stats['total_items'] += result['items_stored']

            return result

        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}")
            self.stats['total_processed'] += 1
            self.stats['failed'] += 1
            self.stats['errors'].append({
                'file': pdf_path,
                'error': str(e)
            })

            return {
                'pdf_path': pdf_path,
                'error': str(e),
                'success': False
            }

    async def process_directory(
        self,
        directory: str,
        pattern: str = "*.pdf",
        limit: Optional[int] = None
    ) -> Dict:
        """
        Process all PDFs in a directory

        Args:
            directory: Directory path
            pattern: File pattern (default: *.pdf)
            limit: Maximum number of files to process

        Returns:
            Batch processing results
        """
        pdf_files = list(Path(directory).glob(pattern))

        if limit:
            pdf_files = pdf_files[:limit]

        logger.info(f"Found {len(pdf_files)} PDF files in {directory}")

        for pdf_path in pdf_files:
            await self.process_file(str(pdf_path))

        return self.stats

    async def process_all_documents_from_db(
        self,
        limit: Optional[int] = None,
        only_missing: bool = True
    ) -> Dict:
        """
        Process all documents from database

        Args:
            limit: Maximum number to process
            only_missing: Only process documents without extracted tables

        Returns:
            Batch processing results
        """
        # Query documents from database
        query = """
            SELECT
                doc_id::text,
                tender_id,
                file_path,
                file_type
            FROM documents
            WHERE file_type = 'pdf'
        """

        if only_missing:
            query += """
                AND doc_id NOT IN (
                    SELECT DISTINCT doc_id
                    FROM extracted_tables
                    WHERE doc_id IS NOT NULL
                )
            """

        query += " ORDER BY created_at DESC"

        if limit:
            query += f" LIMIT {limit}"

        async with self.pool.acquire() as conn:
            documents = await conn.fetch(query)

        logger.info(f"Found {len(documents)} documents to process")

        for doc in documents:
            file_path = doc['file_path']

            # Check if file exists
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue

            await self.process_file(
                file_path,
                tender_id=doc['tender_id'],
                doc_id=doc['doc_id']
            )

        return self.stats

    def print_stats(self):
        """Print processing statistics"""
        print("\n" + "="*60)
        print("BATCH TABLE EXTRACTION STATISTICS")
        print("="*60)
        print(f"Total Processed:  {self.stats['total_processed']}")
        print(f"Successful:       {self.stats['successful']}")
        print(f"Failed:           {self.stats['failed']}")
        print(f"Total Tables:     {self.stats['total_tables']}")
        print(f"Total Items:      {self.stats['total_items']}")

        if self.stats['errors']:
            print(f"\nErrors ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Show first 10
                print(f"  - {error['file']}: {error['error']}")

        print("="*60 + "\n")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Batch table extraction from PDF documents'
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--file',
        help='Single PDF file to process'
    )
    input_group.add_argument(
        '--directory',
        help='Directory containing PDF files'
    )
    input_group.add_argument(
        '--all-documents',
        action='store_true',
        help='Process all documents from database'
    )

    # Options
    parser.add_argument(
        '--tender-id',
        help='Tender ID (for single file mode)'
    )
    parser.add_argument(
        '--doc-id',
        help='Document ID (for single file mode)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of files to process'
    )
    parser.add_argument(
        '--pattern',
        default='*.pdf',
        help='File pattern for directory mode (default: *.pdf)'
    )
    parser.add_argument(
        '--database-url',
        default=os.getenv('DATABASE_URL', 'postgresql://localhost:5432/nabavkidata'),
        help='Database connection URL'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Convert database URL to async
    db_url = args.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    # Create database connection pool
    logger.info(f"Connecting to database...")
    pool = await asyncpg.create_pool(db_url)

    try:
        extractor = BatchTableExtractor(pool)

        # Process based on mode
        if args.file:
            logger.info(f"Processing single file: {args.file}")
            result = await extractor.process_file(
                args.file,
                tender_id=args.tender_id,
                doc_id=args.doc_id
            )
            print(f"\nResult: {result}")

        elif args.directory:
            logger.info(f"Processing directory: {args.directory}")
            await extractor.process_directory(
                args.directory,
                pattern=args.pattern,
                limit=args.limit
            )

        elif args.all_documents:
            logger.info("Processing all documents from database")
            await extractor.process_all_documents_from_db(
                limit=args.limit
            )

        # Print statistics
        extractor.print_stats()

    finally:
        await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
