#!/usr/bin/env python3
"""
Batch Process Pending Documents

This script processes the 7,369 documents with extraction_status='pending':
1. Downloads documents from e-nabavki.gov.mk
2. Extracts text from PDFs, DOCX, XLSX using multiple engines
3. Updates database with extracted content
4. Generates embeddings for semantic search

Features:
- Resumable: Can be stopped and restarted without reprocessing
- Error handling: Categorizes failures (download_failed, auth_required, ocr_required)
- Progress tracking: Shows stats every 10 documents
- Batch processing: Configurable batch sizes for memory management
- Embedding generation: Optional integration with embeddings pipeline

Usage:
    # Process 100 documents
    python3 process_pending_docs.py --limit 100

    # Process all pending documents
    python3 process_pending_docs.py --all

    # Resume from checkpoint
    python3 process_pending_docs.py --resume

    # With embeddings generation
    python3 process_pending_docs.py --limit 100 --generate-embeddings

    # Dry run (check what would be processed)
    python3 process_pending_docs.py --dry-run

    # Process specific tender
    python3 process_pending_docs.py --tender-id 23178/2025
"""
import asyncio
import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import time

import asyncpg
import aiohttp
import aiofiles

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from document_parser import parse_file, is_supported_document, ExtractionResult
from spec_extractor import extract_specifications, TechnicalSpecification
from financial_bid_extractor import FinancialBidExtractor, FinancialBid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/process_pending_docs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL')

# Detect environment and set appropriate paths
SCRIPT_DIR = Path(__file__).parent
if (SCRIPT_DIR / 'downloads' / 'files').exists():
    # Running from local directory
    DEFAULT_FILES_STORE = str(SCRIPT_DIR / 'downloads' / 'files')
elif Path('/home/ubuntu/nabavkidata/scraper/downloads/files').exists():
    # Running on server
    DEFAULT_FILES_STORE = '/home/ubuntu/nabavkidata/scraper/downloads/files'
else:
    # Fallback: create in script directory
    DEFAULT_FILES_STORE = str(SCRIPT_DIR / 'downloads' / 'files')

FILES_STORE = Path(os.getenv('FILES_STORE', DEFAULT_FILES_STORE))
CHECKPOINT_FILE = Path('/tmp/process_pending_docs_checkpoint.json')


class ProcessingStats:
    """Track processing statistics"""
    def __init__(self):
        self.total_processed = 0
        self.success = 0
        self.failed = 0
        self.download_failed = 0
        self.auth_required = 0
        self.ocr_required = 0
        self.skipped_external = 0
        self.skipped_empty = 0
        self.start_time = time.time()

    def update_from_status(self, status: str):
        """Update stats based on extraction status"""
        self.total_processed += 1
        if status == 'success':
            self.success += 1
        elif status == 'download_failed':
            self.download_failed += 1
        elif status == 'auth_required':
            self.auth_required += 1
        elif status == 'ocr_required':
            self.ocr_required += 1
        elif status == 'skipped_external':
            self.skipped_external += 1
        elif status in ('skip_empty', 'skip_minimal', 'skip_boilerplate'):
            self.skipped_empty += 1
        else:
            self.failed += 1

    def get_summary(self) -> str:
        """Get formatted summary"""
        elapsed = time.time() - self.start_time
        rate = self.total_processed / elapsed if elapsed > 0 else 0

        return f"""
=== Processing Summary ===
Total Processed: {self.total_processed}
Success: {self.success} ({self.success/max(self.total_processed,1)*100:.1f}%)
Failed: {self.failed}
  - Download Failed: {self.download_failed}
  - Auth Required: {self.auth_required}
  - OCR Required: {self.ocr_required}
  - Skipped (external/empty): {self.skipped_external + self.skipped_empty}
Elapsed Time: {elapsed/60:.1f} minutes
Processing Rate: {rate*60:.1f} docs/min
=========================="""


class CheckpointManager:
    """Manage processing checkpoints for resumability"""

    def __init__(self, checkpoint_file: Path):
        self.checkpoint_file = checkpoint_file
        self.processed_doc_ids = set()
        self.load()

    def load(self):
        """Load checkpoint from file"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    self.processed_doc_ids = set(data.get('processed_doc_ids', []))
                logger.info(f"Loaded checkpoint: {len(self.processed_doc_ids)} documents already processed")
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")

    def save(self):
        """Save checkpoint to file"""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump({
                    'processed_doc_ids': list(self.processed_doc_ids),
                    'updated_at': datetime.utcnow().isoformat()
                }, f)
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def is_processed(self, doc_id: str) -> bool:
        """Check if document was already processed"""
        return doc_id in self.processed_doc_ids

    def mark_processed(self, doc_id: str):
        """Mark document as processed"""
        self.processed_doc_ids.add(doc_id)
        if len(self.processed_doc_ids) % 10 == 0:
            self.save()

    def clear(self):
        """Clear checkpoint"""
        self.processed_doc_ids = set()
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()


class PendingDocumentProcessor:
    """Process pending documents with robust error handling"""

    def __init__(self, database_url: str, files_store: Path,
                 generate_embeddings: bool = False):
        self.database_url = database_url
        self.files_store = files_store
        self.files_store.mkdir(parents=True, exist_ok=True)
        self.generate_embeddings = generate_embeddings
        self.conn: Optional[asyncpg.Connection] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.financial_bid_extractor = FinancialBidExtractor()
        self.stats = ProcessingStats()
        self.checkpoint = CheckpointManager(CHECKPOINT_FILE)

    async def connect(self):
        """Connect to database and create HTTP session"""
        self.conn = await asyncpg.connect(self.database_url)
        timeout = aiohttp.ClientTimeout(total=180, connect=30, sock_read=120)
        self.http_session = aiohttp.ClientSession(timeout=timeout)
        logger.info("Connected to database and HTTP session")

    async def close(self):
        """Close connections"""
        if self.conn:
            await self.conn.close()
        if self.http_session:
            await self.http_session.close()
        logger.info("Connections closed")

    async def get_pending_documents(self, limit: Optional[int] = None,
                                   tender_id: Optional[str] = None,
                                   offset: int = 0) -> List[Dict[str, Any]]:
        """Get documents with extraction_status='pending'"""
        if tender_id:
            query = """
                SELECT doc_id, tender_id, file_url, file_name, file_path,
                       extraction_status, mime_type
                FROM documents
                WHERE tender_id = $1
                ORDER BY doc_id
            """
            rows = await self.conn.fetch(query, tender_id)
        else:
            query = """
                SELECT doc_id, tender_id, file_url, file_name, file_path,
                       extraction_status, mime_type
                FROM documents
                WHERE extraction_status = 'pending'
                ORDER BY doc_id
            """

            if limit:
                query += f" LIMIT {limit}"
            if offset > 0:
                query += f" OFFSET {offset}"

            rows = await self.conn.fetch(query)

        return [dict(row) for row in rows]

    async def get_stats(self) -> Dict[str, int]:
        """Get current statistics from database"""
        result = await self.conn.fetch("""
            SELECT extraction_status, COUNT(*) as count
            FROM documents
            GROUP BY extraction_status
        """)
        return {row['extraction_status'] or 'null': row['count'] for row in result}

    def _get_extension(self, url: str, mime_type: Optional[str] = None) -> str:
        """Get file extension from URL or MIME type"""
        url_lower = url.lower()

        # Try to infer from URL first
        if '.pdf' in url_lower:
            return '.pdf'
        elif '.docx' in url_lower or 'wordprocessingml' in str(mime_type):
            return '.docx'
        elif '.doc' in url_lower and '.docx' not in url_lower:
            return '.doc'
        elif '.xlsx' in url_lower or 'spreadsheetml' in str(mime_type):
            return '.xlsx'
        elif '.xls' in url_lower and '.xlsx' not in url_lower:
            return '.xls'

        # Try MIME type
        if mime_type:
            if 'pdf' in mime_type:
                return '.pdf'
            elif 'wordprocessingml' in mime_type or 'msword' in mime_type:
                return '.docx'
            elif 'spreadsheetml' in mime_type or 'excel' in mime_type:
                return '.xlsx'

        # Default to PDF
        return '.pdf'

    async def download_document(self, doc: Dict[str, Any]) -> Tuple[Optional[Path], str]:
        """
        Download a document if not already downloaded

        Returns:
            (file_path, status) where status is 'success', 'download_failed',
            'auth_required', or 'skipped_external'
        """
        file_url = doc.get('file_url')
        doc_id = doc['doc_id']

        # Check for missing URL
        if not file_url or file_url.strip() == '':
            logger.warning(f"Document {doc_id} has no URL")
            await self.conn.execute(
                "UPDATE documents SET extraction_status = 'download_failed' WHERE doc_id = $1",
                doc_id
            )
            return None, 'download_failed'

        # Skip external documents (bank guarantees)
        if 'ohridskabanka' in file_url.lower():
            logger.info(f"Skipping external document: {file_url}")
            await self.conn.execute(
                "UPDATE documents SET extraction_status = 'skipped_external' WHERE doc_id = $1",
                doc_id
            )
            return None, 'skipped_external'

        # Generate filename
        url_hash = hashlib.md5(file_url.encode('utf-8')).hexdigest()[:12]
        tender_id = doc.get('tender_id', 'unknown').replace('/', '_')
        ext = self._get_extension(file_url, doc.get('mime_type'))
        filename = f"{tender_id}_{url_hash}{ext}"
        file_path = self.files_store / filename

        # Check if already downloaded
        if file_path.exists() and file_path.stat().st_size > 100:
            logger.debug(f"Document already exists: {filename}")
            # Update database with file path
            await self.conn.execute(
                "UPDATE documents SET file_path = $1 WHERE doc_id = $2",
                str(file_path), doc_id
            )
            return file_path, 'success'

        # Download
        try:
            logger.info(f"Downloading: {file_url[:100]}...")
            async with self.http_session.get(file_url, allow_redirects=True) as response:
                # Check for authentication/authorization errors
                if response.status == 401 or response.status == 403:
                    logger.warning(f"Auth required: HTTP {response.status}")
                    await self.conn.execute(
                        "UPDATE documents SET extraction_status = 'auth_required' WHERE doc_id = $1",
                        doc_id
                    )
                    return None, 'auth_required'

                if response.status != 200:
                    logger.error(f"Download failed: HTTP {response.status}")
                    await self.conn.execute(
                        "UPDATE documents SET extraction_status = 'download_failed' WHERE doc_id = $1",
                        doc_id
                    )
                    return None, 'download_failed'

                # Check content type
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    # Might be an error page
                    content = await response.text()
                    if len(content) < 10000 and ('login' in content.lower() or
                                                  'error' in content.lower()):
                        logger.warning(f"Downloaded HTML error page")
                        await self.conn.execute(
                            "UPDATE documents SET extraction_status = 'download_invalid' WHERE doc_id = $1",
                            doc_id
                        )
                        return None, 'download_invalid'

                # Stream to file
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

            size = file_path.stat().st_size

            # Validate file size
            if size < 100:
                logger.warning(f"Downloaded file too small: {size} bytes")
                file_path.unlink()
                await self.conn.execute(
                    "UPDATE documents SET extraction_status = 'download_invalid' WHERE doc_id = $1",
                    doc_id
                )
                return None, 'download_invalid'

            logger.info(f"Downloaded: {filename} ({size / 1024:.1f} KB)")

            # Update database with file path
            await self.conn.execute(
                "UPDATE documents SET file_path = $1 WHERE doc_id = $2",
                str(file_path), doc_id
            )

            return file_path, 'success'

        except asyncio.TimeoutError:
            logger.error(f"Download timeout: {file_url}")
            await self.conn.execute(
                "UPDATE documents SET extraction_status = 'download_timeout' WHERE doc_id = $1",
                doc_id
            )
            return None, 'download_timeout'

        except Exception as e:
            logger.error(f"Download error: {e}")
            if file_path.exists():
                file_path.unlink()
            await self.conn.execute(
                "UPDATE documents SET extraction_status = 'download_failed' WHERE doc_id = $1",
                doc_id
            )
            return None, 'download_failed'

    async def extract_text(self, file_path: Path) -> Optional[ExtractionResult]:
        """Extract text from document using multi-engine parser"""
        if not file_path.exists():
            return None

        # Check if file type is supported
        if not is_supported_document(str(file_path)):
            logger.info(f"Unsupported file type: {file_path.name}")
            return None

        try:
            # Use universal parser for all supported file types
            result = parse_file(str(file_path))

            # Check if extraction yielded meaningful content
            if len(result.text) < 50:
                logger.warning(f"Minimal text extracted: {len(result.text)} chars")
                return None

            logger.info(f"Extracted {len(result.text)} chars from {file_path.suffix}, "
                       f"{len(result.cpv_codes)} CPV codes, "
                       f"{len(result.company_names)} companies")
            return result

        except Exception as e:
            logger.error(f"Extraction error for {file_path.name}: {e}")
            return None

    async def update_document(self, doc_id: str, extraction_result: ExtractionResult,
                            spec: Optional[TechnicalSpecification] = None,
                            tender_id: str = None):
        """Update document record with extracted content"""
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

        # Determine extraction status
        if len(extraction_result.text) < 50:
            status = 'skip_minimal'
        elif extraction_result.text and 'банкарска' in extraction_result.text.lower():
            # Check for bank guarantee boilerplate
            if len(extraction_result.text) < 500:
                status = 'skip_bank_guarantee'
            else:
                status = 'success'
        else:
            status = 'success'

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
            status,
            extraction_result.page_count,
            datetime.utcnow(),
            spec_json,
            doc_id
        )

        # Insert product items if spec extraction found items
        if spec and tender_id and status == 'success':
            items_inserted = 0
            all_items = list(spec.items)
            for lot in spec.lots:
                all_items.extend(lot.items)

            for item in all_items:
                if not item.name or len(item.name.strip()) < 3:
                    continue

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
                    logger.warning(f"Failed to insert product item: {e}")

            if items_inserted > 0:
                logger.info(f"Inserted {items_inserted} product items for tender {tender_id}")

    async def process_document(self, doc: Dict[str, Any]) -> str:
        """
        Process a single document end-to-end

        Returns:
            extraction_status: The final status of the document
        """
        doc_id = doc['doc_id']
        tender_id = doc.get('tender_id', 'unknown')
        file_name = doc.get('file_name', 'unknown')
        file_url = doc.get('file_url', '')

        # Skip if already processed (via checkpoint)
        if self.checkpoint.is_processed(doc_id):
            logger.debug(f"Skipping already processed: {doc_id}")
            return 'already_processed'

        logger.info(f"Processing {doc_id}: {file_name} (tender {tender_id})")

        try:
            # Step 1: Download if needed
            file_path = doc.get('file_path')
            if file_path:
                file_path = Path(file_path)

            if not file_path or not file_path.exists():
                file_path, download_status = await self.download_document(doc)
                if not file_path:
                    self.checkpoint.mark_processed(doc_id)
                    return download_status

            # Step 2: Extract text
            result = await self.extract_text(file_path)
            if not result or not result.text:
                # Mark as OCR required for documents that couldn't be extracted
                await self.conn.execute(
                    "UPDATE documents SET extraction_status = 'ocr_required' WHERE doc_id = $1",
                    doc_id
                )
                self.checkpoint.mark_processed(doc_id)
                return 'ocr_required'

            # Step 3: Try specialized financial bid extraction
            financial_bid = None
            is_bid_doc = 'DownloadBidFile' in file_url or 'Bids/' in file_url
            if is_bid_doc or self.financial_bid_extractor.is_financial_bid(result.text):
                logger.info(f"Detected financial bid document")
                financial_bid = self.financial_bid_extractor.extract(result.text, file_name)
                if financial_bid and financial_bid.items:
                    logger.info(f"Financial bid extracted {len(financial_bid.items)} items")
                    # Insert financial bid items (similar to update_document but for bids)
                    # Simplified here - full implementation would be similar to process_documents.py

            # Step 4: Run general spec extraction
            spec = extract_specifications(
                result.text,
                result.tables,
                tender_id,
                file_name
            )

            # Step 5: Update database
            if financial_bid and financial_bid.items:
                # Financial bid items already handled, just update metadata
                await self.update_document(doc_id, result, spec=None, tender_id=None)
            else:
                # Use general spec extraction
                await self.update_document(doc_id, result, spec, tender_id)

            self.checkpoint.mark_processed(doc_id)
            return 'success'

        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}", exc_info=True)
            await self.conn.execute(
                "UPDATE documents SET extraction_status = 'failed' WHERE doc_id = $1",
                doc_id
            )
            self.checkpoint.mark_processed(doc_id)
            return 'failed'

    async def process_batch(self, limit: Optional[int] = None,
                          tender_id: Optional[str] = None,
                          offset: int = 0) -> ProcessingStats:
        """Process a batch of pending documents"""
        docs = await self.get_pending_documents(limit, tender_id, offset)

        if not docs:
            logger.info("No documents to process")
            return self.stats

        logger.info(f"Found {len(docs)} documents to process")

        for i, doc in enumerate(docs):
            status = await self.process_document(doc)
            self.stats.update_from_status(status)

            # Progress log every 10 documents
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(docs)} | "
                           f"Success: {self.stats.success} | "
                           f"Failed: {self.stats.failed} | "
                           f"Rate: {self.stats.total_processed/(time.time()-self.stats.start_time)*60:.1f} docs/min")

        # Final checkpoint save
        self.checkpoint.save()

        logger.info(self.stats.get_summary())
        return self.stats

    async def generate_embeddings_for_extracted(self):
        """Generate embeddings for successfully extracted documents"""
        if not self.generate_embeddings:
            return

        logger.info("Generating embeddings for extracted documents...")

        try:
            # Import embeddings pipeline
            sys.path.insert(0, str(Path(__file__).parent.parent / 'ai'))
            from embeddings import EmbeddingsPipeline

            pipeline = EmbeddingsPipeline(database_url=self.database_url)

            # Get documents without embeddings
            docs = await self.conn.fetch("""
                SELECT d.doc_id, d.tender_id, d.content_text, d.file_name,
                       t.title as tender_title, t.category as tender_category
                FROM documents d
                JOIN tenders t ON d.tender_id = t.tender_id
                WHERE d.extraction_status = 'success'
                  AND d.content_text IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id)
                LIMIT 100
            """)

            if not docs:
                logger.info("No documents need embeddings")
                return

            documents = [
                {
                    'doc_id': row['doc_id'],
                    'tender_id': row['tender_id'],
                    'text': row['content_text'],
                    'metadata': {
                        'file_name': row['file_name'],
                        'tender_title': row['tender_title'],
                        'tender_category': row['tender_category']
                    }
                }
                for row in docs
            ]

            logger.info(f"Generating embeddings for {len(documents)} documents...")
            results = await pipeline.process_documents_batch(documents)

            success_count = sum(1 for embed_ids in results.values() if embed_ids)
            logger.info(f"Generated embeddings for {success_count}/{len(documents)} documents")

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description='Batch process pending documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--limit', type=int,
                       help='Number of documents to process')
    parser.add_argument('--all', action='store_true',
                       help='Process all pending documents')
    parser.add_argument('--tender-id', type=str,
                       help='Process documents for specific tender')
    parser.add_argument('--offset', type=int, default=0,
                       help='Skip first N documents')
    parser.add_argument('--generate-embeddings', action='store_true',
                       help='Generate embeddings after extraction')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from checkpoint')
    parser.add_argument('--clear-checkpoint', action='store_true',
                       help='Clear checkpoint and start fresh')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without processing')
    parser.add_argument('--db-url', type=str, default=DATABASE_URL,
                       help='Database URL')

    args = parser.parse_args()

    # Create processor
    processor = PendingDocumentProcessor(
        database_url=args.db_url,
        files_store=FILES_STORE,
        generate_embeddings=args.generate_embeddings
    )

    try:
        await processor.connect()

        # Show current stats
        current_stats = await processor.get_stats()
        logger.info("Current database statistics:")
        for status, count in sorted(current_stats.items()):
            logger.info(f"  {status}: {count}")

        # Clear checkpoint if requested
        if args.clear_checkpoint:
            processor.checkpoint.clear()
            logger.info("Checkpoint cleared")

        # Dry run
        if args.dry_run:
            docs = await processor.get_pending_documents(
                limit=args.limit,
                tender_id=args.tender_id,
                offset=args.offset
            )
            logger.info(f"Would process {len(docs)} documents")
            if docs:
                logger.info("Sample documents:")
                for doc in docs[:5]:
                    logger.info(f"  {doc['doc_id']}: {doc['file_name']} (tender {doc['tender_id']})")
            return

        # Process documents
        if args.all:
            logger.info("Processing ALL pending documents...")
            # Get total count
            total = current_stats.get('pending', 0)
            logger.info(f"Total pending documents: {total}")

            # Process in batches of 100
            batch_size = 100
            offset = 0
            while True:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing batch starting at offset {offset}")
                logger.info(f"{'='*60}\n")

                stats = await processor.process_batch(
                    limit=batch_size,
                    offset=offset
                )

                if stats.total_processed == 0:
                    logger.info("No more documents to process")
                    break

                offset += batch_size

                # Optional: Generate embeddings after each batch
                if args.generate_embeddings:
                    await processor.generate_embeddings_for_extracted()
        else:
            # Process single batch
            await processor.process_batch(
                limit=args.limit,
                tender_id=args.tender_id,
                offset=args.offset
            )

            # Generate embeddings if requested
            if args.generate_embeddings:
                await processor.generate_embeddings_for_extracted()

        # Show final stats
        logger.info("\n" + "="*60)
        logger.info("FINAL STATISTICS")
        logger.info("="*60)
        final_stats = await processor.get_stats()
        for status, count in sorted(final_stats.items()):
            logger.info(f"  {status}: {count}")
        logger.info("="*60)

    finally:
        await processor.close()


if __name__ == '__main__':
    asyncio.run(main())
