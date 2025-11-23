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
    Enhanced with actual file download functionality.
    """

    def __init__(self, files_store):
        self.files_store = Path(files_store)
        self.files_store.mkdir(parents=True, exist_ok=True)
        self.session = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            files_store=crawler.settings.get('FILES_STORE', 'downloads/files')
        )

    def open_spider(self, spider):
        logger.info(f"PDFDownloadPipeline: Storing files in {self.files_store}")
        # Create aiohttp session for downloads
        import aiohttp
        self.session = aiohttp.ClientSession()

    async def close_spider(self, spider):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

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

            # Check if file already exists (skip re-download)
            if file_path.exists():
                logger.info(f"File already exists, skipping download: {filename}")
                adapter['file_path'] = str(file_path)
                adapter['file_name'] = filename
                adapter['file_size_bytes'] = file_path.stat().st_size
                return item

            # Download file with streaming (for large files)
            logger.info(f"Downloading file: {file_url}")

            async with self.session.get(file_url, timeout=300) as response:  # 5 minute timeout
                if response.status != 200:
                    logger.error(f"Failed to download {file_url}: HTTP {response.status}")
                    adapter['extraction_status'] = 'download_failed'
                    return item

                # Get content type and size
                content_type = response.headers.get('Content-Type', '')
                content_length = response.headers.get('Content-Length')

                if content_length:
                    size_mb = int(content_length) / (1024 * 1024)
                    logger.info(f"Downloading {size_mb:.2f} MB file")

                # Stream download to file
                async with aiofiles.open(file_path, 'wb') as f:
                    chunk_size = 8192  # 8KB chunks
                    downloaded = 0
                    async for chunk in response.content.iter_chunked(chunk_size):
                        await f.write(chunk)
                        downloaded += len(chunk)

                # Verify download
                actual_size = file_path.stat().st_size
                logger.info(f"Download complete: {filename} ({actual_size / 1024 / 1024:.2f} MB)")

                # Set item fields
                adapter['file_path'] = str(file_path)
                adapter['file_name'] = filename
                adapter['file_size_bytes'] = actual_size
                adapter['mime_type'] = content_type

                # Verify minimum file size (avoid empty/corrupted downloads)
                if actual_size < 100:  # Less than 100 bytes is suspicious
                    logger.warning(f"Downloaded file is too small: {filename} ({actual_size} bytes)")
                    adapter['extraction_status'] = 'download_corrupted'
                    file_path.unlink()  # Delete corrupted file
                    return item

        except asyncio.TimeoutError:
            logger.error(f"Download timeout for {file_url}")
            adapter['extraction_status'] = 'download_timeout'
        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            adapter['extraction_status'] = 'download_failed'
            # Clean up partial download
            if file_path.exists():
                file_path.unlink()

        return item

    def _get_extension(self, url):
        """Extract file extension from URL."""
        url_lower = url.lower()
        if '.pdf' in url_lower:
            return '.pdf'
        elif '.docx' in url_lower:
            return '.docx'
        elif '.doc' in url_lower:
            return '.doc'
        elif '.xls' in url_lower:
            return '.xls'
        elif '.xlsx' in url_lower:
            return '.xlsx'
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


class DataValidationPipeline:
    """
    Validate tender data before database insertion.

    Validates:
    - Required fields (tender_id, title)
    - Date formats and logical date ranges
    - Price values (positive, reasonable ranges)
    - Data types and constraints
    """

    def process_item(self, item, spider):
        """Validate item data."""
        adapter = ItemAdapter(item)

        # Only validate TenderItem
        if item.__class__.__name__ != 'TenderItem':
            return item

        # Validate required fields
        if not adapter.get('tender_id'):
            logger.error("Validation failed: Missing tender_id")
            raise ValueError("tender_id is required")

        if not adapter.get('title') or len(adapter.get('title', '').strip()) < 3:
            logger.error(f"Validation failed: Invalid title for tender {adapter.get('tender_id')}")
            raise ValueError("title must be at least 3 characters")

        # Validate dates
        opening_date = adapter.get('opening_date')
        closing_date = adapter.get('closing_date')
        publication_date = adapter.get('publication_date')

        # Check date logic: publication <= opening <= closing
        if publication_date and opening_date and publication_date > opening_date:
            logger.warning(f"Date logic issue: publication_date > opening_date for {adapter.get('tender_id')}")

        if opening_date and closing_date and opening_date > closing_date:
            logger.warning(f"Date logic issue: opening_date > closing_date for {adapter.get('tender_id')}")

        # Validate prices (must be positive)
        for price_field in ['estimated_value_mkd', 'estimated_value_eur', 'actual_value_mkd', 'actual_value_eur']:
            price = adapter.get(price_field)
            if price is not None:
                try:
                    price_float = float(price)
                    if price_float < 0:
                        logger.warning(f"Invalid {price_field}: negative value for {adapter.get('tender_id')}")
                        adapter[price_field] = None
                    elif price_float > 1_000_000_000:  # 1 billion MKD/EUR sanity check
                        logger.warning(f"Suspicious {price_field}: extremely high value for {adapter.get('tender_id')}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid {price_field}: not a number for {adapter.get('tender_id')}")
                    adapter[price_field] = None

        logger.info(f"Validation passed: {adapter.get('tender_id')}")
        return item


class DatabasePipeline:
    """
    Insert scraped tenders and documents into PostgreSQL.

    Handles both TenderItem and DocumentItem with upsert logic.
    Includes duplicate prevention for documents.
    """

    def __init__(self):
        self.conn = None
        self.existing_documents = set()  # Cache for duplicate prevention

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
        Insert document into database with duplicate prevention.

        Uses file_url + tender_id as duplicate key.
        """
        file_url = item.get('file_url')
        tender_id = item.get('tender_id')

        # Check for duplicates using file_url + tender_id
        duplicate_key = f"{tender_id}:{file_url}"

        if duplicate_key in self.existing_documents:
            logger.info(f"Skipping duplicate document: {item.get('file_name')}")
            return

        # Check database for existing document
        existing = await self.conn.fetchval("""
            SELECT doc_id FROM documents
            WHERE tender_id = $1 AND file_url = $2
            LIMIT 1
        """, tender_id, file_url)

        if existing:
            logger.info(f"Document already exists in database: {item.get('file_name')}")
            self.existing_documents.add(duplicate_key)
            return

        # Insert new document
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

        # Add to cache
        self.existing_documents.add(duplicate_key)

        logger.info(
            f"✓ Document saved: {item.get('file_name')} "
            f"[{item.get('extraction_status')}]"
        )
