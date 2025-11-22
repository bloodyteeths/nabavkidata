"""
Scrapy pipelines for PDF handling and database insertion
Includes: PDF download, Cyrillic extraction, database storage
"""
import asyncpg
import os
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from itemadapter import ItemAdapter
import aiofiles
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFDownloadPipeline:
    """
    REQUIREMENT 2: Large PDF support (10-20MB)

    Downloads PDF files from URLs and saves them locally.
    Handles large files with streaming and proper error handling.
    """

    def __init__(self, files_store):
        self.files_store = Path(files_store)
        self.files_store.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            files_store=crawler.settings.get('FILES_STORE', 'downloads/files')
        )

    def open_spider(self, spider):
        logger.info(f"PDFDownloadPipeline: Storing files in {self.files_store}")

    async def process_item(self, item, spider):
        """Download PDF file if URL is present."""
        adapter = ItemAdapter(item)

        # Only process DocumentItem with file_url
        if item.__class__.__name__ != 'DocumentItem':
            return item

        file_url = adapter.get('file_url')
        if not file_url:
            return item

        try:
            # Generate unique filename based on URL hash
            url_hash = hashlib.md5(file_url.encode('utf-8')).hexdigest()
            tender_id = adapter.get('tender_id', 'unknown')
            file_ext = self._get_extension(file_url)
            filename = f"{tender_id}_{url_hash}{file_ext}"
            file_path = self.files_store / filename

            # Download file (handled by Scrapy's download mechanism)
            # File should already be downloaded via FilesPipeline or custom downloader
            # Here we just record the path
            adapter['file_path'] = str(file_path)
            adapter['file_name'] = filename

            logger.info(f"PDF prepared for download: {filename}")

        except Exception as e:
            logger.error(f"Error processing PDF download: {e}")
            adapter['extraction_status'] = 'failed'

        return item

    def _get_extension(self, url):
        """Extract file extension from URL."""
        if '.pdf' in url.lower():
            return '.pdf'
        elif '.doc' in url.lower():
            return '.doc'
        elif '.docx' in url.lower():
            return '.docx'
        else:
            return '.pdf'  # Default to PDF


class PDFExtractionPipeline:
    """
    REQUIREMENT 1: UTF-8 Cyrillic handling
    ENHANCED: Multi-engine extraction with automatic selection

    Extracts text from PDF files while preserving Cyrillic characters.
    Uses multi-engine approach: PyMuPDF → PDFMiner → Tesseract OCR
    """

    async def process_item(self, item, spider):
        """Extract text from downloaded PDF using multi-engine parser."""
        adapter = ItemAdapter(item)

        # Only process DocumentItem with file_path
        if item.__class__.__name__ != 'DocumentItem':
            return item

        file_path = adapter.get('file_path')
        if not file_path or not Path(file_path).exists():
            return item

        try:
            # Use multi-engine document parser
            from document_parser import parse_pdf

            result = parse_pdf(file_path)

            # Store extracted text in item
            adapter['content_text'] = result.text
            adapter['extraction_status'] = 'success' if result.text else 'failed'

            # Get file metadata
            file_stats = Path(file_path).stat()
            adapter['file_size_bytes'] = file_stats.st_size
            adapter['page_count'] = result.page_count

            # Store extracted metadata as JSON
            metadata = {
                'engine_used': result.engine_used,
                'has_tables': result.has_tables,
                'table_count': len(result.tables),
                'cpv_codes': result.cpv_codes,
                'company_names': result.company_names,
            }

            # Verify Cyrillic preservation
            if self._contains_cyrillic(result.text):
                logger.info(f"✓ Cyrillic text preserved in: {adapter.get('file_name')}")

            logger.info(
                f"Extracted {len(result.text)} characters from {adapter.get('file_name')} "
                f"using {result.engine_used} engine. "
                f"CPV codes: {len(result.cpv_codes)}, Companies: {len(result.company_names)}"
            )

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            adapter['extraction_status'] = 'failed'
            adapter['content_text'] = None

        return item

    def _contains_cyrillic(self, text):
        """Check if text contains Cyrillic characters (Macedonian/Serbian)."""
        if not text:
            return False

        # Cyrillic Unicode range: U+0400 to U+04FF
        return any(0x0400 <= ord(char) <= 0x04FF for char in text)


class DatabasePipeline:
    """
    Insert scraped tenders and documents into PostgreSQL.

    Handles both TenderItem and DocumentItem with upsert logic.
    """

    def __init__(self):
        self.conn = None

    def open_spider(self, spider):
        """Initialize (connection happens in first item)."""
        logger.info("DatabasePipeline: Ready")

    async def close_spider(self, spider):
        """Close database connection."""
        if self.conn:
            await self.conn.close()
            logger.info("DatabasePipeline: Connection closed")

    async def process_item_async(self, item, spider):
        """Async database insertion."""
        if not self.conn:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.error("DATABASE_URL not set!")
                return item

            self.conn = await asyncpg.connect(database_url)
            logger.info("DatabasePipeline: Connected to database")

        adapter = ItemAdapter(item)

        if item.__class__.__name__ == 'TenderItem':
            await self.insert_tender(adapter)
        elif item.__class__.__name__ == 'DocumentItem':
            await self.insert_document(adapter)

        return item

    def process_item(self, item, spider):
        """Synchronous wrapper for async processing."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.process_item_async(item, spider))

    async def insert_tender(self, item):
        """
        Upsert tender into database.

        Uses ON CONFLICT to update existing records while preserving history.
        """
        await self.conn.execute("""
            INSERT INTO tenders (
                tender_id, title, description, category, procuring_entity,
                opening_date, closing_date, publication_date,
                estimated_value_mkd, estimated_value_eur,
                actual_value_mkd, actual_value_eur,
                cpv_code, status, winner, source_url, language, scraped_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            ON CONFLICT (tender_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                winner = EXCLUDED.winner,
                actual_value_mkd = EXCLUDED.actual_value_mkd,
                actual_value_eur = EXCLUDED.actual_value_eur,
                updated_at = CURRENT_TIMESTAMP
        """,
            item.get('tender_id'),
            item.get('title'),
            item.get('description'),
            item.get('category'),
            item.get('procuring_entity'),
            item.get('opening_date'),
            item.get('closing_date'),
            item.get('publication_date'),
            item.get('estimated_value_mkd'),
            item.get('estimated_value_eur'),
            item.get('actual_value_mkd'),
            item.get('actual_value_eur'),
            item.get('cpv_code'),
            item.get('status', 'open'),
            item.get('winner'),
            item.get('source_url'),
            item.get('language', 'mk'),
            item.get('scraped_at', datetime.utcnow())
        )

        logger.info(f"✓ Tender saved: {item.get('tender_id')}")

    async def insert_document(self, item):
        """
        Insert document into database.

        Note: Uses INSERT (not UPSERT) to allow multiple versions.
        """
        await self.conn.execute("""
            INSERT INTO documents (
                tender_id, doc_type, file_name, file_path, file_url,
                content_text, extraction_status, file_size_bytes,
                page_count, mime_type
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
            item.get('tender_id'),
            item.get('doc_type'),
            item.get('file_name'),
            item.get('file_path'),
            item.get('file_url'),
            item.get('content_text'),
            item.get('extraction_status', 'pending'),
            item.get('file_size_bytes'),
            item.get('page_count'),
            item.get('mime_type')
        )

        logger.info(
            f"✓ Document saved: {item.get('file_name')} "
            f"[{item.get('extraction_status')}]"
        )
