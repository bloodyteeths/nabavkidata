#!/usr/bin/env python3
"""
Integration Example - Complete Document Processing Pipeline

Demonstrates how to integrate table extraction with existing systems:
- Document parsing (text extraction)
- Table extraction (structured data)
- Embeddings generation (vector search)
- Database storage (all components)

This is a reference implementation showing the complete workflow.
"""

import os
import sys
import asyncio
import asyncpg
import logging
from typing import Dict, List, Optional
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import existing systems
from scraper.document_parser import ResilientDocumentParser, parse_pdf
from ai.table_extraction import extract_tables_from_pdf, extract_items_from_pdf
from ai.table_storage import TableStorage
from ai.embeddings import EmbeddingsGenerator

logger = logging.getLogger(__name__)


class CompleteDocumentProcessor:
    """
    Complete document processing pipeline integrating all extraction systems
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
        self.doc_parser = ResilientDocumentParser()
        self.table_storage = TableStorage(db_pool)
        self.embeddings_gen = EmbeddingsGenerator()

    async def process_document(
        self,
        pdf_path: str,
        tender_id: str,
        doc_id: Optional[str] = None,
        generate_embeddings: bool = True
    ) -> Dict:
        """
        Complete document processing workflow

        Args:
            pdf_path: Path to PDF file
            tender_id: Tender ID
            doc_id: Optional document ID
            generate_embeddings: Whether to generate embeddings

        Returns:
            Complete processing results
        """
        logger.info(f"Processing document: {pdf_path}")

        results = {
            'pdf_path': pdf_path,
            'tender_id': tender_id,
            'doc_id': doc_id
        }

        try:
            # Step 1: Parse full document (text extraction)
            logger.info("Step 1: Extracting text and metadata...")
            doc_result = self.doc_parser.parse_document(pdf_path)

            results['text_extraction'] = {
                'engine': doc_result.engine_used,
                'page_count': doc_result.page_count,
                'text_length': len(doc_result.text),
                'has_tables': doc_result.has_tables,
                'cpv_codes': doc_result.cpv_codes,
                'companies': doc_result.company_names,
                'emails': doc_result.emails,
                'phones': doc_result.phones
            }

            # Step 2: Extract tables and items
            logger.info("Step 2: Extracting tables and items...")
            table_result = await self.table_storage.process_and_store_pdf(
                pdf_path,
                tender_id=tender_id,
                doc_id=doc_id
            )

            results['table_extraction'] = table_result

            # Step 3: Generate embeddings (optional)
            if generate_embeddings and doc_result.text:
                logger.info("Step 3: Generating embeddings...")

                # Generate embeddings for full text
                await self.embeddings_gen.process_document(
                    text=doc_result.text,
                    tender_id=tender_id,
                    doc_id=doc_id
                )

                # Generate embeddings for extracted items
                items = await self.table_storage.get_items_by_tender(tender_id)

                item_embeddings_count = 0
                for item in items:
                    if item.get('item_name'):
                        # Generate embedding for item description
                        await self.embeddings_gen.generate_embedding(
                            text=item['item_name'],
                            metadata={
                                'type': 'procurement_item',
                                'tender_id': tender_id,
                                'item_id': str(item['item_id'])
                            }
                        )
                        item_embeddings_count += 1

                results['embeddings'] = {
                    'text_embeddings': 'generated',
                    'item_embeddings': item_embeddings_count
                }

            # Step 4: Store complete metadata
            logger.info("Step 4: Storing complete metadata...")
            await self._store_document_metadata(
                doc_id=doc_id,
                tender_id=tender_id,
                doc_result=doc_result,
                table_result=table_result
            )

            results['success'] = True
            logger.info("Document processing complete!")

            return results

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            results['success'] = False
            results['error'] = str(e)
            return results

    async def _store_document_metadata(
        self,
        doc_id: Optional[str],
        tender_id: str,
        doc_result,
        table_result: Dict
    ):
        """
        Store complete document metadata in database
        """
        if not doc_id:
            return

        # Update documents table with extracted metadata
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE documents
                SET
                    extraction_metadata = jsonb_build_object(
                        'text_engine', $1,
                        'page_count', $2,
                        'text_length', $3,
                        'cpv_codes', $4,
                        'companies', $5,
                        'emails', $6,
                        'phones', $7,
                        'tables_extracted', $8,
                        'items_extracted', $9,
                        'processed_at', NOW()
                    )
                WHERE doc_id = $10
            """,
                doc_result.engine_used,
                doc_result.page_count,
                len(doc_result.text),
                doc_result.cpv_codes,
                doc_result.company_names,
                doc_result.emails,
                doc_result.phones,
                table_result['tables_stored'],
                table_result['items_stored'],
                doc_id
            )

    async def batch_process_tender_documents(
        self,
        tender_id: str,
        generate_embeddings: bool = True
    ) -> List[Dict]:
        """
        Process all documents for a specific tender

        Args:
            tender_id: Tender ID
            generate_embeddings: Whether to generate embeddings

        Returns:
            List of processing results
        """
        logger.info(f"Processing all documents for tender {tender_id}")

        # Get all documents for tender
        async with self.pool.acquire() as conn:
            documents = await conn.fetch("""
                SELECT
                    doc_id::text,
                    file_path,
                    file_type
                FROM documents
                WHERE tender_id = $1
                AND file_type = 'pdf'
                ORDER BY created_at
            """, tender_id)

        results = []

        for doc in documents:
            if not os.path.exists(doc['file_path']):
                logger.warning(f"File not found: {doc['file_path']}")
                continue

            result = await self.process_document(
                pdf_path=doc['file_path'],
                tender_id=tender_id,
                doc_id=doc['doc_id'],
                generate_embeddings=generate_embeddings
            )

            results.append(result)

        return results

    async def generate_tender_summary(self, tender_id: str) -> Dict:
        """
        Generate complete summary of extracted data for a tender

        Args:
            tender_id: Tender ID

        Returns:
            Complete summary
        """
        async with self.pool.acquire() as conn:
            # Get all extracted items
            items = await conn.fetch("""
                SELECT
                    item_name,
                    quantity,
                    unit,
                    total_price,
                    cpv_code
                FROM extracted_items
                WHERE tender_id = $1
                ORDER BY total_price DESC NULLS LAST
            """, tender_id)

            # Get all tables
            tables = await conn.fetch("""
                SELECT
                    table_type,
                    page_number,
                    confidence_score,
                    row_count
                FROM extracted_tables
                WHERE tender_id = $1
                ORDER BY page_number
            """, tender_id)

            # Get CPV codes from text extraction
            cpv_codes = await conn.fetchval("""
                SELECT extraction_metadata->'cpv_codes'
                FROM documents
                WHERE tender_id = $1
                LIMIT 1
            """, tender_id)

            # Calculate totals
            total_value = sum(
                float(item['total_price'] or 0)
                for item in items
            )

            item_count = len(items)

        return {
            'tender_id': tender_id,
            'total_value': total_value,
            'item_count': item_count,
            'table_count': len(tables),
            'cpv_codes': cpv_codes or [],
            'items': [dict(item) for item in items],
            'tables': [dict(table) for table in tables]
        }


# Example usage
async def main():
    """Example usage"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Database connection
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'postgresql://localhost:5432/nabavkidata'
    )

    pool = await asyncpg.create_pool(DATABASE_URL)

    try:
        processor = CompleteDocumentProcessor(pool)

        # Example 1: Process single document
        print("\n" + "="*60)
        print("EXAMPLE 1: Process Single Document")
        print("="*60 + "\n")

        result = await processor.process_document(
            pdf_path='scraper/downloads/files/19033_2025_6633182ae207ccfb4239090ea380c431.pdf',
            tender_id='19033_2025',
            generate_embeddings=False  # Set to True in production
        )

        print(f"Success: {result['success']}")
        print(f"\nText Extraction:")
        for key, value in result['text_extraction'].items():
            print(f"  {key}: {value}")

        print(f"\nTable Extraction:")
        for key, value in result['table_extraction'].items():
            if key not in ['table_ids', 'item_ids']:
                print(f"  {key}: {value}")

        # Example 2: Generate tender summary
        print("\n" + "="*60)
        print("EXAMPLE 2: Generate Tender Summary")
        print("="*60 + "\n")

        summary = await processor.generate_tender_summary('19033_2025')

        print(f"Tender ID: {summary['tender_id']}")
        print(f"Total Value: {summary['total_value']:,.2f}")
        print(f"Item Count: {summary['item_count']}")
        print(f"Table Count: {summary['table_count']}")

        print(f"\nTop 5 Items by Value:")
        for i, item in enumerate(summary['items'][:5], 1):
            print(f"  {i}. {item['item_name'][:50]}...")
            print(f"     Quantity: {item['quantity']} {item['unit']}")
            print(f"     Price: {item['total_price']:,.2f}")

    finally:
        await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
