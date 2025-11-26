#!/usr/bin/env python3
"""
Standalone script to process and extract text/specifications from documents.

This script:
1. Downloads documents that haven't been downloaded yet
2. Extracts text from PDFs
3. Parses technical specifications (products, quantities, prices)
4. Creates embeddings for semantic search
5. Updates the database with extracted content

Usage:
    python process_documents.py --limit 100
    python process_documents.py --tender-id 12345/2025
    python process_documents.py --all
"""
import asyncio
import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import asyncpg
import aiohttp
import aiofiles

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from document_parser import parse_pdf, ExtractionResult
from spec_extractor import extract_specifications, TechnicalSpecification
from financial_bid_extractor import FinancialBidExtractor, FinancialBid, BidItem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata')
FILES_STORE = Path(os.getenv('FILES_STORE', '/home/ubuntu/nabavkidata/scraper/downloads/files'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')


class DocumentProcessor:
    """Process documents: download, extract, embed"""

    def __init__(self, database_url: str, files_store: Path):
        self.database_url = database_url
        self.files_store = files_store
        self.files_store.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[asyncpg.Connection] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.financial_bid_extractor = FinancialBidExtractor()

    async def connect(self):
        """Connect to database and create HTTP session"""
        self.conn = await asyncpg.connect(self.database_url)
        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300)  # 5 min timeout
        )
        logger.info("Connected to database")

    async def close(self):
        """Close connections"""
        if self.conn:
            await self.conn.close()
        if self.http_session:
            await self.http_session.close()
        logger.info("Connections closed")

    async def get_pending_documents(self, limit: int = 100,
                                   tender_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documents that need processing"""
        if tender_id:
            query = """
                SELECT doc_id, tender_id, file_url, file_name, file_path, extraction_status
                FROM documents
                WHERE tender_id = $1
                ORDER BY doc_id
            """
            rows = await self.conn.fetch(query, tender_id)
        else:
            query = """
                SELECT doc_id, tender_id, file_url, file_name, file_path, extraction_status
                FROM documents
                WHERE (extraction_status = 'pending' OR extraction_status IS NULL)
                  AND file_url IS NOT NULL AND file_url != ''
                ORDER BY doc_id
                LIMIT $1
            """
            rows = await self.conn.fetch(query, limit)

        return [dict(row) for row in rows]

    async def download_document(self, doc: Dict[str, Any]) -> Optional[Path]:
        """Download a document if not already downloaded"""
        file_url = doc.get('file_url')
        if not file_url:
            logger.warning(f"Document {doc['id']} has no URL")
            return None

        # Skip ohridskabanka.mk documents (external bank guarantees)
        if 'ohridskabanka' in file_url.lower():
            logger.info(f"Skipping ohridskabanka.mk document: {file_url}")
            return None

        # Generate filename
        url_hash = hashlib.md5(file_url.encode('utf-8')).hexdigest()[:12]
        tender_id = doc.get('tender_id', 'unknown').replace('/', '_')
        ext = self._get_extension(file_url)
        filename = f"{tender_id}_{url_hash}{ext}"
        file_path = self.files_store / filename

        # Check if already downloaded
        if file_path.exists() and file_path.stat().st_size > 100:
            logger.info(f"Document already exists: {filename}")
            return file_path

        # Download
        try:
            logger.info(f"Downloading: {file_url[:80]}...")
            async with self.http_session.get(file_url) as response:
                if response.status != 200:
                    logger.error(f"Download failed: HTTP {response.status}")
                    return None

                # Stream to file
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

            size = file_path.stat().st_size
            logger.info(f"Downloaded: {filename} ({size / 1024:.1f} KB)")

            # Update database with file path
            await self.conn.execute(
                "UPDATE documents SET file_path = $1 WHERE doc_id = $2",
                str(file_path), doc['doc_id']
            )

            return file_path

        except Exception as e:
            logger.error(f"Download error: {e}")
            if file_path.exists():
                file_path.unlink()
            return None

    def _get_extension(self, url: str) -> str:
        """Get file extension from URL"""
        url_lower = url.lower()
        if '.pdf' in url_lower:
            return '.pdf'
        elif '.docx' in url_lower:
            return '.docx'
        elif '.doc' in url_lower:
            return '.doc'
        elif '.xlsx' in url_lower:
            return '.xlsx'
        elif '.xls' in url_lower:
            return '.xls'
        return '.pdf'  # Default

    async def extract_text(self, file_path: Path) -> Optional[ExtractionResult]:
        """Extract text from PDF using multi-engine parser"""
        if not file_path.exists():
            return None

        if not str(file_path).lower().endswith('.pdf'):
            logger.info(f"Skipping non-PDF: {file_path.name}")
            return None

        try:
            result = parse_pdf(str(file_path))
            logger.info(f"Extracted {len(result.text)} chars, "
                       f"{len(result.cpv_codes)} CPV codes, "
                       f"{len(result.company_names)} companies")
            return result
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return None

    def extract_specifications(self, text: str, tables: List,
                              tender_id: str, doc_name: str) -> TechnicalSpecification:
        """Extract product specifications from text"""
        return extract_specifications(text, tables, tender_id, doc_name)

    async def update_document(self, doc_id: str, extraction_result: ExtractionResult,
                            spec: Optional[TechnicalSpecification] = None,
                            tender_id: str = None):
        """Update document record with extracted content and insert product items"""
        # Prepare specification data as JSON
        spec_json = None
        if spec:
            spec_data = {
                'lots': [
                    {
                        'lot_number': lot.lot_number,
                        'title': lot.title,
                        'items': [
                            {
                                'name': item.name,
                                'quantity': item.quantity,
                                'unit': item.unit,
                                'unit_price': str(item.unit_price) if item.unit_price else None,
                                'specifications': item.specifications
                            }
                            for item in lot.items
                        ]
                    }
                    for lot in spec.lots
                ],
                'items': [
                    {
                        'name': item.name,
                        'quantity': item.quantity,
                        'unit': item.unit,
                        'unit_price': str(item.unit_price) if item.unit_price else None,
                        'specifications': item.specifications
                    }
                    for item in spec.items
                ],
                'extraction_confidence': spec.extraction_confidence
            }
            spec_json = json.dumps(spec_data, ensure_ascii=False)

        # Update document
        await self.conn.execute("""
            UPDATE documents SET
                content_text = $1,
                extraction_status = $2,
                page_count = $3,
                extracted_at = $4,
                specifications_json = $5
            WHERE doc_id = $6
        """,
            extraction_result.text,
            'success' if extraction_result.text else 'failed',
            extraction_result.page_count,
            datetime.utcnow(),
            spec_json,
            doc_id
        )

        # Insert product items into product_items table for searchability
        if spec and tender_id:
            items_inserted = 0
            all_items = list(spec.items)
            for lot in spec.lots:
                all_items.extend(lot.items)

            for item in all_items:
                if not item.name or len(item.name.strip()) < 3:
                    continue  # Skip items without valid names

                try:
                    await self.conn.execute("""
                        INSERT INTO product_items (
                            tender_id, document_id, item_number, lot_number,
                            name, quantity, unit, unit_price, total_price,
                            specifications, cpv_code, raw_text, extraction_confidence
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT DO NOTHING
                    """,
                        tender_id,
                        doc_id,
                        item.item_number,
                        item.lot_number,
                        item.name,
                        item.quantity,
                        item.unit,
                        float(item.unit_price) if item.unit_price else None,
                        float(item.total_price) if item.total_price else None,
                        json.dumps(item.specifications, ensure_ascii=False) if item.specifications else '{}',
                        item.cpv_code,
                        item.raw_text,
                        spec.extraction_confidence
                    )
                    items_inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to insert product item '{item.name[:30]}...': {e}")

            logger.info(f"Inserted {items_inserted} product items for tender {tender_id}")

        logger.info(f"Updated document {doc_id} with {len(extraction_result.text)} chars")

    def _is_bid_document(self, file_url: str) -> bool:
        """Check if document URL indicates a financial bid document"""
        if not file_url:
            return False
        # Bid documents come from Bids/DownloadBidFile endpoint
        return 'DownloadBidFile' in file_url or 'Bids/' in file_url

    async def insert_financial_bid_items(self, doc_id: str, tender_id: str,
                                         file_url: str, bid: FinancialBid) -> int:
        """Insert items from financial bid extraction into product_items table"""
        items_inserted = 0

        for item in bid.items:
            if not item.name or len(item.name.strip()) < 3:
                continue

            try:
                # Build specifications JSON
                specs = {}
                if item.vat_amount_mkd:
                    specs['vat_amount_mkd'] = str(item.vat_amount_mkd)
                if item.total_with_vat_mkd:
                    specs['total_with_vat_mkd'] = str(item.total_with_vat_mkd)
                if item.lot_description:
                    specs['lot_description'] = item.lot_description

                await self.conn.execute("""
                    INSERT INTO product_items (
                        tender_id, document_id, item_number, lot_number,
                        name, quantity, unit, unit_price, total_price,
                        specifications, cpv_code, raw_text, extraction_confidence,
                        source_document_url, extraction_method
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT DO NOTHING
                """,
                    tender_id,
                    doc_id,
                    item.item_number,
                    item.lot_number,
                    item.name,
                    item.quantity,
                    item.unit,
                    float(item.unit_price_mkd) if item.unit_price_mkd else None,
                    float(item.total_price_mkd) if item.total_price_mkd else None,
                    json.dumps(specs, ensure_ascii=False) if specs else '{}',
                    item.cpv_code,
                    item.raw_text,
                    bid.extraction_confidence,
                    file_url,
                    'financial_bid'
                )
                items_inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert bid item '{item.name[:30]}...': {e}")

        logger.info(f"Inserted {items_inserted} items from financial bid for tender {tender_id}")
        return items_inserted

    async def process_document(self, doc: Dict[str, Any]) -> bool:
        """Process a single document end-to-end"""
        doc_id = doc['doc_id']
        tender_id = doc.get('tender_id', 'unknown')
        file_name = doc.get('file_name', 'unknown')
        file_url = doc.get('file_url', '')

        # Skip ohridskabanka.mk documents (external bank guarantees)
        if 'ohridskabanka' in file_url.lower():
            logger.info(f"Skipping ohridskabanka.mk document {doc_id}: {file_url}")
            await self.conn.execute(
                "UPDATE documents SET extraction_status = 'skipped_external' WHERE doc_id = $1",
                doc_id
            )
            return False

        logger.info(f"Processing document {doc_id}: {file_name} for tender {tender_id}")

        try:
            # Step 1: Download if needed
            file_path = doc.get('file_path')
            if file_path:
                file_path = Path(file_path)
            if not file_path or not file_path.exists():
                file_path = await self.download_document(doc)

            if not file_path:
                await self.conn.execute(
                    "UPDATE documents SET extraction_status = 'failed' WHERE doc_id = $1",
                    doc_id
                )
                return False

            # Step 2: Extract text
            result = await self.extract_text(file_path)
            if not result or not result.text:
                # Use 'ocr_required' for documents that couldn't be extracted (likely scanned)
                await self.conn.execute(
                    "UPDATE documents SET extraction_status = 'ocr_required' WHERE doc_id = $1",
                    doc_id
                )
                return False

            # Step 3: Try specialized financial bid extraction first for bid documents
            financial_bid = None
            if self._is_bid_document(file_url) or self.financial_bid_extractor.is_financial_bid(result.text):
                logger.info(f"Detected financial bid document, using specialized extractor")
                financial_bid = self.financial_bid_extractor.extract(result.text, file_name)
                if financial_bid and financial_bid.items:
                    logger.info(f"Financial bid extractor found {len(financial_bid.items)} items")
                    await self.insert_financial_bid_items(doc_id, tender_id, file_url, financial_bid)

            # Step 4: Also run general spec extraction (as fallback/complement)
            spec = self.extract_specifications(
                result.text,
                result.tables,
                tender_id,
                file_name
            )

            # Step 5: Update database (don't duplicate items if financial_bid already extracted)
            if financial_bid and financial_bid.items:
                # Financial bid items already inserted, just update document metadata
                await self.update_document(doc_id, result, spec=None, tender_id=None)
            else:
                # Use general spec extraction
                await self.update_document(doc_id, result, spec, tender_id)

            return True

        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")
            await self.conn.execute(
                "UPDATE documents SET extraction_status = 'failed' WHERE doc_id = $1",
                doc_id
            )
            return False

    async def process_batch(self, limit: int = 100, tender_id: Optional[str] = None):
        """Process a batch of documents"""
        docs = await self.get_pending_documents(limit, tender_id)
        logger.info(f"Found {len(docs)} documents to process")

        success = 0
        failed = 0

        for doc in docs:
            if await self.process_document(doc):
                success += 1
            else:
                failed += 1

            # Progress log
            if (success + failed) % 10 == 0:
                logger.info(f"Progress: {success + failed}/{len(docs)} "
                           f"(success: {success}, failed: {failed})")

        logger.info(f"Processing complete: {success} success, {failed} failed")
        return success, failed


async def main():
    parser = argparse.ArgumentParser(description='Process tender documents')
    parser.add_argument('--limit', type=int, default=100,
                       help='Number of documents to process')
    parser.add_argument('--tender-id', type=str,
                       help='Process documents for specific tender')
    parser.add_argument('--all', action='store_true',
                       help='Process all pending documents')
    parser.add_argument('--db-url', type=str, default=DATABASE_URL,
                       help='Database URL')
    args = parser.parse_args()

    # Create processor
    processor = DocumentProcessor(
        database_url=args.db_url,
        files_store=FILES_STORE
    )

    try:
        await processor.connect()

        if args.all:
            # Get total count
            count = await processor.conn.fetchval(
                "SELECT COUNT(*) FROM documents WHERE file_url IS NOT NULL AND file_url != ''"
            )
            logger.info(f"Processing all {count} documents with URLs")
            # Process in batches
            batch_size = 100
            total_success = 0
            total_failed = 0
            offset = 0
            while True:
                docs = await processor.conn.fetch("""
                    SELECT id, tender_id, file_url, file_name, file_path, extraction_status
                    FROM documents
                    WHERE file_url IS NOT NULL AND file_url != ''
                    ORDER BY id
                    LIMIT $1 OFFSET $2
                """, batch_size, offset)
                if not docs:
                    break
                for doc in docs:
                    if await processor.process_document(dict(doc)):
                        total_success += 1
                    else:
                        total_failed += 1
                offset += batch_size
                logger.info(f"Batch complete: {offset}/{count}")
            logger.info(f"Total: {total_success} success, {total_failed} failed")
        else:
            await processor.process_batch(
                limit=args.limit,
                tender_id=args.tender_id
            )

    finally:
        await processor.close()


if __name__ == '__main__':
    asyncio.run(main())
