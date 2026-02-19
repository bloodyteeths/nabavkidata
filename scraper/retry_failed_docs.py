#!/usr/bin/env python3
"""
Retry Failed Document Extractions

This script retries extraction for documents that previously failed with:
- failed: Generic extraction failure (retry with all engines)
- ocr_required: Scanned PDFs or documents without text (use Tesseract OCR)
- download_failed: Download issues (retry with better error handling)
- download_timeout: Timeout during download (retry with increased timeout)

Strategy:
1. Analyze failure type and select appropriate retry strategy
2. For OCR required: Force Tesseract OCR on the existing file
3. For download failures: Retry download with exponential backoff
4. For generic failures: Retry extraction with all available engines
5. Mark permanently failed documents after max retries

Usage:
    # Retry specific failure type
    python retry_failed_docs.py --status ocr_required --limit 100

    # Retry all failure types
    python retry_failed_docs.py --all --limit 500

    # Retry specific tender
    python retry_failed_docs.py --tender-id 12345/2025

    # Dry run (no database updates)
    python retry_failed_docs.py --dry-run --limit 10
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
from dotenv import load_dotenv
load_dotenv()


# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from document_parser import (
    parse_file,
    MultiEngineExtractor,
    ExtractionResult,
    TESSERACT_AVAILABLE
)
from spec_extractor import extract_specifications
from financial_bid_extractor import FinancialBidExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
def _normalize_database_url(url: str) -> str:
    """Convert SQLAlchemy URL format to asyncpg format"""
    if url.startswith('postgresql+asyncpg://'):
        return url.replace('postgresql+asyncpg://', 'postgresql://')
    return url

DATABASE_URL = _normalize_database_url(
    os.getenv('DATABASE_URL',
              os.getenv('DATABASE_URL'))
)
FILES_STORE = Path(os.getenv('FILES_STORE', '/home/ubuntu/nabavkidata/scraper/downloads/files'))

# Retry configuration
MAX_RETRIES = 3
DOWNLOAD_TIMEOUT = 600  # 10 minutes for slow downloads
BACKOFF_FACTOR = 2  # Exponential backoff


class FailureAnalyzer:
    """Analyze document failures and recommend retry strategies"""

    @staticmethod
    def analyze_failure(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze document failure and return retry strategy

        Returns:
            {
                'strategy': 'ocr'|'redownload'|'retry_extraction'|'skip',
                'reason': str,
                'force_ocr': bool,
                'retry_download': bool,
                'retry_extraction': bool
            }
        """
        status = doc.get('extraction_status')
        file_path_str = doc.get('file_path')
        file_url = doc.get('file_url')

        # Convert file_path to Path object and check existence
        file_exists = False
        if file_path_str:
            file_path = Path(file_path_str)
            file_exists = file_path.exists()

        # OCR required - file exists but no text extracted
        if status == 'ocr_required':
            if file_exists:
                return {
                    'strategy': 'ocr',
                    'reason': 'Document requires OCR (scanned PDF)',
                    'force_ocr': True,
                    'retry_download': False,
                    'retry_extraction': True
                }
            else:
                return {
                    'strategy': 'redownload_then_ocr',
                    'reason': 'File missing, re-download then OCR',
                    'force_ocr': True,
                    'retry_download': True,
                    'retry_extraction': True
                }

        # Download failures - retry download
        if status in ('download_failed', 'download_timeout'):
            if not file_url or file_url.strip() == '':
                return {
                    'strategy': 'skip',
                    'reason': 'No file URL available',
                    'force_ocr': False,
                    'retry_download': False,
                    'retry_extraction': False
                }
            return {
                'strategy': 'redownload',
                'reason': f'Download failed: {status}',
                'force_ocr': False,
                'retry_download': True,
                'retry_extraction': True
            }

        # Generic failure - try all extraction methods
        if status == 'failed':
            # If file exists locally, retry extraction only
            if file_exists:
                return {
                    'strategy': 'retry_extraction',
                    'reason': 'File exists, retry extraction with all engines',
                    'force_ocr': False,
                    'retry_download': False,
                    'retry_extraction': True
                }
            # If file missing, re-download first
            elif file_url and file_url.strip():
                return {
                    'strategy': 'redownload_then_extract',
                    'reason': 'File missing, re-download then extract',
                    'force_ocr': False,
                    'retry_download': True,
                    'retry_extraction': True
                }
            else:
                return {
                    'strategy': 'skip',
                    'reason': 'No file path or URL available',
                    'force_ocr': False,
                    'retry_download': False,
                    'retry_extraction': False
                }

        # Unknown status
        return {
            'strategy': 'skip',
            'reason': f'Unknown status: {status}',
            'force_ocr': False,
            'retry_download': False,
            'retry_extraction': False
        }


class RetryProcessor:
    """Process failed documents with intelligent retry strategies"""

    def __init__(self, database_url: str, files_store: Path, dry_run: bool = False):
        self.database_url = database_url
        self.files_store = files_store
        self.files_store.mkdir(parents=True, exist_ok=True)
        self.dry_run = dry_run
        self.conn: Optional[asyncpg.Connection] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.financial_bid_extractor = FinancialBidExtractor()

        # Stats
        self.stats = {
            'attempted': 0,
            'success': 0,
            'ocr_success': 0,
            'redownload_success': 0,
            'failed': 0,
            'skipped': 0,
            'permanently_failed': 0
        }

    async def connect(self):
        """Connect to database and create HTTP session"""
        self.conn = await asyncpg.connect(self.database_url)
        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
        )
        logger.info("Connected to database")

        # Check Tesseract availability
        if TESSERACT_AVAILABLE:
            logger.info("Tesseract OCR is available for scanned documents")
        else:
            logger.warning("Tesseract OCR not available - install with: pip install pytesseract pillow")

    async def close(self):
        """Close connections"""
        if self.conn:
            await self.conn.close()
        if self.http_session:
            await self.http_session.close()
        logger.info("Connections closed")

    async def get_failed_documents(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        tender_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get failed documents to retry"""

        if tender_id:
            query = """
                SELECT doc_id, tender_id, file_url, file_name, file_path, extraction_status
                FROM documents
                WHERE tender_id = $1
                  AND extraction_status IN ('failed', 'ocr_required', 'download_failed', 'download_timeout')
                ORDER BY doc_id
            """
            rows = await self.conn.fetch(query, tender_id)
        elif status:
            query = """
                SELECT doc_id, tender_id, file_url, file_name, file_path, extraction_status
                FROM documents
                WHERE extraction_status = $1
                ORDER BY doc_id
                LIMIT $2
            """
            rows = await self.conn.fetch(query, status, limit)
        else:
            query = """
                SELECT doc_id, tender_id, file_url, file_name, file_path, extraction_status
                FROM documents
                WHERE extraction_status IN ('failed', 'ocr_required', 'download_failed', 'download_timeout')
                ORDER BY
                    CASE extraction_status
                        WHEN 'ocr_required' THEN 1
                        WHEN 'download_failed' THEN 2
                        WHEN 'download_timeout' THEN 3
                        WHEN 'failed' THEN 4
                    END,
                    doc_id
                LIMIT $1
            """
            rows = await self.conn.fetch(query, limit)

        return [dict(row) for row in rows]

    async def download_document_with_retry(
        self,
        doc: Dict[str, Any],
        max_retries: int = MAX_RETRIES
    ) -> Optional[Path]:
        """Download document with exponential backoff retry"""
        file_url = doc.get('file_url', '').strip()
        if not file_url:
            logger.warning(f"Document {doc['doc_id']} has no URL")
            return None

        # Skip external documents
        if 'ohridskabanka' in file_url.lower():
            logger.info(f"Skipping external document: {file_url}")
            return None

        # Generate filename
        url_hash = hashlib.md5(file_url.encode('utf-8')).hexdigest()[:12]
        tender_id = doc.get('tender_id', 'unknown').replace('/', '_')
        ext = self._get_extension(file_url)
        filename = f"{tender_id}_{url_hash}{ext}"
        file_path = self.files_store / filename

        # Check if already exists and valid
        if file_path.exists() and file_path.stat().st_size > 100:
            logger.info(f"Document already exists: {filename}")
            return file_path

        # Retry with exponential backoff
        for attempt in range(max_retries):
            try:
                wait_time = BACKOFF_FACTOR ** attempt
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s wait")
                    await asyncio.sleep(wait_time)

                logger.info(f"Downloading: {file_url[:80]}...")
                async with self.http_session.get(file_url) as response:
                    if response.status != 200:
                        logger.error(f"Download failed: HTTP {response.status}")
                        if response.status in (404, 410):  # Permanent failures
                            return None
                        continue  # Retry on temporary errors

                    # Stream to file
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)

                size = file_path.stat().st_size
                if size < 100:
                    logger.error(f"Downloaded file too small: {size} bytes")
                    file_path.unlink()
                    continue

                logger.info(f"Downloaded: {filename} ({size / 1024:.1f} KB)")

                # Update database with file path
                if not self.dry_run:
                    await self.conn.execute(
                        "UPDATE documents SET file_path = $1 WHERE doc_id = $2",
                        str(file_path), doc['doc_id']
                    )

                return file_path

            except asyncio.TimeoutError:
                logger.error(f"Download timeout (attempt {attempt + 1}/{max_retries})")
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.error(f"Download error (attempt {attempt + 1}/{max_retries}): {e}")
                if file_path.exists():
                    file_path.unlink()

        # All retries failed
        logger.error(f"Failed to download after {max_retries} attempts")
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

    async def extract_with_ocr(self, file_path: Path) -> Optional[ExtractionResult]:
        """Extract text using OCR (for scanned documents)"""
        if not TESSERACT_AVAILABLE:
            logger.error("Tesseract OCR not available")
            return None

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        try:
            # Only PDFs support OCR in our current setup
            if file_path.suffix.lower() != '.pdf':
                logger.warning(f"OCR only supported for PDFs, got: {file_path.suffix}")
                return None

            logger.info(f"Forcing OCR extraction for: {file_path.name}")
            text, metadata = MultiEngineExtractor.extract_with_tesseract(str(file_path))

            if not text or len(text.strip()) < 50:
                logger.warning(f"OCR extracted insufficient text: {len(text)} chars")
                return None

            # Create extraction result
            result = ExtractionResult(
                text=text,
                engine_used='tesseract_ocr',
                page_count=metadata.get('page_count', 0),
                has_tables=False,
                tables=[],
                cpv_codes=[],
                company_names=[],
                emails=[],
                phones=[],
                metadata=metadata
            )

            logger.info(f"OCR extracted {len(text)} chars from {file_path.name}")
            return result

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return None

    async def extract_text_with_fallback(
        self,
        file_path: Path,
        force_ocr: bool = False
    ) -> Optional[ExtractionResult]:
        """Extract text with all available methods and fallback to OCR"""

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        # If OCR is forced, use it directly
        if force_ocr and file_path.suffix.lower() == '.pdf':
            return await self.extract_with_ocr(file_path)

        try:
            # Try standard extraction first
            result = parse_file(str(file_path))

            # Check if extraction was successful
            if result and result.text and len(result.text.strip()) > 50:
                logger.info(f"Standard extraction successful: {len(result.text)} chars")
                return result

            # Standard extraction failed or insufficient text
            logger.warning(f"Standard extraction got only {len(result.text) if result else 0} chars")

            # Fallback to OCR for PDFs
            if file_path.suffix.lower() == '.pdf' and TESSERACT_AVAILABLE:
                logger.info("Falling back to OCR extraction")
                return await self.extract_with_ocr(file_path)

            return None

        except Exception as e:
            logger.error(f"Extraction failed: {e}")

            # Last resort: try OCR for PDFs
            if file_path.suffix.lower() == '.pdf' and TESSERACT_AVAILABLE:
                logger.info("Exception occurred, trying OCR as last resort")
                return await self.extract_with_ocr(file_path)

            return None

    def _is_bid_document(self, file_url: str) -> bool:
        """Check if document URL indicates a financial bid document"""
        if not file_url:
            return False
        return 'DownloadBidFile' in file_url or 'Bids/' in file_url

    async def insert_financial_bid_items(
        self,
        doc_id: str,
        tender_id: str,
        file_url: str,
        bid
    ) -> int:
        """Insert items from financial bid extraction"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert {len(bid.items)} financial bid items")
            return len(bid.items)

        items_inserted = 0
        for item in bid.items:
            if not item.name or len(item.name.strip()) < 3:
                continue

            try:
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
                    tender_id, doc_id, item.item_number, item.lot_number,
                    item.name, item.quantity, item.unit,
                    float(item.unit_price_mkd) if item.unit_price_mkd else None,
                    float(item.total_price_mkd) if item.total_price_mkd else None,
                    json.dumps(specs, ensure_ascii=False) if specs else '{}',
                    item.cpv_code, item.raw_text, bid.extraction_confidence,
                    file_url, 'financial_bid'
                )
                items_inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert bid item: {e}")

        logger.info(f"Inserted {items_inserted} financial bid items")
        return items_inserted

    async def update_document(
        self,
        doc_id: str,
        extraction_result: ExtractionResult,
        spec = None,
        tender_id: str = None
    ):
        """Update document with extraction results"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update doc {doc_id} with {len(extraction_result.text)} chars")
            return

        # Prepare spec JSON
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

        # Insert product items if spec available
        if spec and tender_id:
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
                        tender_id, doc_id, item.item_number, item.lot_number,
                        item.name, item.quantity, item.unit,
                        float(item.unit_price) if item.unit_price else None,
                        float(item.total_price) if item.total_price else None,
                        json.dumps(item.specifications, ensure_ascii=False) if item.specifications else '{}',
                        item.cpv_code, item.raw_text, spec.extraction_confidence
                    )
                    items_inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to insert product item: {e}")

            if items_inserted > 0:
                logger.info(f"Inserted {items_inserted} product items")

    async def mark_permanently_failed(self, doc_id: str, reason: str):
        """Mark document as permanently failed"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would mark doc {doc_id} as permanently_failed: {reason}")
            return

        await self.conn.execute("""
            UPDATE documents SET
                extraction_status = 'permanently_failed',
                extracted_at = $1
            WHERE doc_id = $2
        """, datetime.utcnow(), doc_id)
        logger.info(f"Marked document {doc_id} as permanently failed: {reason}")

    async def process_document(self, doc: Dict[str, Any]) -> bool:
        """Process a single failed document with retry strategy"""
        doc_id = doc['doc_id']
        tender_id = doc.get('tender_id', 'unknown')
        file_name = doc.get('file_name', 'unknown')
        file_url = doc.get('file_url', '')

        self.stats['attempted'] += 1

        logger.info(f"\n{'='*80}")
        logger.info(f"Processing document {self.stats['attempted']}: {file_name}")
        logger.info(f"Tender: {tender_id}, Status: {doc['extraction_status']}")

        # Analyze failure and determine strategy
        analysis = FailureAnalyzer.analyze_failure(doc)
        logger.info(f"Strategy: {analysis['strategy']} - {analysis['reason']}")

        if analysis['strategy'] == 'skip':
            logger.warning(f"Skipping: {analysis['reason']}")
            self.stats['skipped'] += 1
            return False

        try:
            # Step 1: Download if needed
            file_path = doc.get('file_path')
            if file_path:
                file_path = Path(file_path)

            if analysis['retry_download'] or not file_path or not file_path.exists():
                logger.info("Attempting download...")
                file_path = await self.download_document_with_retry(doc)
                if not file_path:
                    await self.mark_permanently_failed(doc_id, "Download failed after retries")
                    self.stats['permanently_failed'] += 1
                    return False
                self.stats['redownload_success'] += 1

            # Step 2: Extract text
            if analysis['retry_extraction']:
                logger.info(f"Attempting extraction (force_ocr={analysis['force_ocr']})...")
                result = await self.extract_text_with_fallback(file_path, analysis['force_ocr'])

                if not result or not result.text or len(result.text.strip()) < 50:
                    await self.mark_permanently_failed(doc_id, "Extraction failed - insufficient text")
                    self.stats['permanently_failed'] += 1
                    return False

                logger.info(f"Extraction successful: {len(result.text)} chars using {result.engine_used}")

                if result.engine_used == 'tesseract_ocr':
                    self.stats['ocr_success'] += 1

                # Step 3: Try financial bid extraction
                financial_bid = None
                if self._is_bid_document(file_url) or self.financial_bid_extractor.is_financial_bid(result.text):
                    logger.info("Detected financial bid document")
                    financial_bid = self.financial_bid_extractor.extract(result.text, file_name)
                    if financial_bid and financial_bid.items:
                        await self.insert_financial_bid_items(doc_id, tender_id, file_url, financial_bid)

                # Step 4: General spec extraction
                spec = extract_specifications(result.text, result.tables, tender_id, file_name)

                # Step 5: Update database
                if financial_bid and financial_bid.items:
                    await self.update_document(doc_id, result, spec=None, tender_id=None)
                else:
                    await self.update_document(doc_id, result, spec, tender_id)

                self.stats['success'] += 1
                logger.info(f"✓ Document processed successfully")
                return True

        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")
            self.stats['failed'] += 1
            return False

    async def process_batch(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        tender_id: Optional[str] = None
    ):
        """Process a batch of failed documents"""
        docs = await self.get_failed_documents(status, limit, tender_id)

        logger.info(f"\n{'='*80}")
        logger.info(f"Found {len(docs)} failed documents to retry")
        if status:
            logger.info(f"Filtering by status: {status}")
        logger.info(f"{'='*80}\n")

        for doc in docs:
            await self.process_document(doc)

            # Progress update every 10 docs
            if self.stats['attempted'] % 10 == 0:
                self._print_stats()

        # Final stats
        logger.info(f"\n{'='*80}")
        logger.info("FINAL RESULTS")
        logger.info(f"{'='*80}")
        self._print_stats()

    def _print_stats(self):
        """Print current statistics"""
        total = self.stats['attempted']
        success_rate = (self.stats['success'] / total * 100) if total > 0 else 0

        logger.info(f"Progress: {self.stats['attempted']} documents attempted")
        logger.info(f"  ✓ Success: {self.stats['success']} ({success_rate:.1f}%)")
        logger.info(f"    - OCR success: {self.stats['ocr_success']}")
        logger.info(f"    - Re-download success: {self.stats['redownload_success']}")
        logger.info(f"  ✗ Failed: {self.stats['failed']}")
        logger.info(f"  ⊗ Permanently failed: {self.stats['permanently_failed']}")
        logger.info(f"  ⊘ Skipped: {self.stats['skipped']}")


async def main():
    parser = argparse.ArgumentParser(
        description='Retry failed document extractions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Retry OCR required documents
  python retry_failed_docs.py --status ocr_required --limit 100

  # Retry all download failures
  python retry_failed_docs.py --status download_failed --limit 50

  # Retry all failure types (prioritizes OCR first)
  python retry_failed_docs.py --all --limit 500

  # Retry specific tender
  python retry_failed_docs.py --tender-id 12345/2025

  # Dry run to test
  python retry_failed_docs.py --dry-run --limit 10
        """
    )
    parser.add_argument(
        '--status',
        choices=['failed', 'ocr_required', 'download_failed', 'download_timeout'],
        help='Retry specific failure type'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Retry all failure types (prioritizes OCR required)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Number of documents to process (default: 100)'
    )
    parser.add_argument(
        '--tender-id',
        type=str,
        help='Process failed documents for specific tender'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test run without database updates'
    )
    parser.add_argument(
        '--db-url',
        type=str,
        default=DATABASE_URL,
        help='Database URL'
    )
    args = parser.parse_args()

    # Validate arguments
    if args.tender_id and (args.status or args.all):
        parser.error("--tender-id cannot be used with --status or --all")

    if not args.tender_id and not args.status and not args.all:
        parser.error("Must specify one of: --status, --all, or --tender-id")

    # Create processor
    processor = RetryProcessor(
        database_url=args.db_url,
        files_store=FILES_STORE,
        dry_run=args.dry_run
    )

    try:
        await processor.connect()

        # Show initial statistics
        if not args.tender_id:
            stats_query = """
                SELECT extraction_status, COUNT(*) as count
                FROM documents
                WHERE extraction_status IN ('failed', 'ocr_required', 'download_failed', 'download_timeout')
                GROUP BY extraction_status
                ORDER BY count DESC
            """
            stats = await processor.conn.fetch(stats_query)
            logger.info("\nCurrent failure statistics:")
            for row in stats:
                logger.info(f"  {row['extraction_status']}: {row['count']}")
            logger.info("")

        # Process documents
        status_filter = args.status if args.status else None
        await processor.process_batch(
            status=status_filter,
            limit=args.limit,
            tender_id=args.tender_id
        )

    finally:
        await processor.close()


if __name__ == '__main__':
    asyncio.run(main())
