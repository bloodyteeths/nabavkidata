"""
Scrapy pipelines for PDF handling and database insertion
Includes: PDF download, Cyrillic extraction, database storage
"""
import asyncpg
import asyncio
import os
import hashlib
import logging
import json
from datetime import datetime
from pathlib import Path
from itemadapter import ItemAdapter
from scrapy.utils.defer import deferred_from_coro
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

    async def _close_spider_async(self, spider):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

    def close_spider(self, spider):
        # Scrapy expects a Deferred; wrap coroutine to avoid un-awaited warnings
        return deferred_from_coro(self._close_spider_async(spider))

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

            # Check if file already exists (skip re-download and calculate hash)
            if file_path.exists():
                logger.info(f"File already exists, skipping download: {filename}")
                adapter['file_path'] = str(file_path)
                adapter['file_name'] = filename
                adapter['file_size_bytes'] = file_path.stat().st_size

                # Calculate hash for existing file
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                adapter['file_hash'] = file_hash

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

                # Calculate SHA-256 hash for deduplication
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()

                logger.info(f"File hash: {file_hash[:16]}...")

                # Set item fields
                adapter['file_path'] = str(file_path)
                adapter['file_name'] = filename
                adapter['file_size_bytes'] = actual_size
                adapter['mime_type'] = content_type
                adapter['file_hash'] = file_hash

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

        # Title fallback logic: Use procuring_entity or tender_id if title is missing
        title = adapter.get('title')
        if not title or len(title.strip()) < 3:
            fallback_title = (
                adapter.get('description') or
                adapter.get('procuring_entity') or
                f"Tender {adapter.get('tender_id')}"
            )
            adapter['title'] = fallback_title
            logger.warning(f"Missing title for tender {adapter.get('tender_id')}, using fallback: {fallback_title[:50]}")

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
    Supports incremental scraping with change detection (Phase 5).
    """

    def __init__(self):
        self.conn = None
        self.existing_documents = set()  # Cache for duplicate prevention
        self.scrape_run_id = None  # Track current scrape run
        self.stats = {
            'tenders_new': 0,
            'tenders_updated': 0,
            'tenders_unchanged': 0,
            'errors': 0,
        }

    def open_spider(self, spider):
        """Initialize (connection happens in first item)."""
        logger.info("DatabasePipeline: Ready")
        # Store spider reference for accessing mode parameter
        self.spider = spider

    async def _close_spider_async(self, spider):
        """Close database connection and finalize scrape run."""
        if self.conn:
            # Finalize scrape_history record if we have one
            if self.scrape_run_id:
                try:
                    await self.conn.execute("""
                        UPDATE scrape_history
                        SET completed_at = CURRENT_TIMESTAMP,
                            tenders_new = $2,
                            tenders_updated = $3,
                            tenders_unchanged = $4,
                            errors = $5,
                            status = 'completed',
                            duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))
                        WHERE id = $1
                    """,
                        self.scrape_run_id,
                        self.stats['tenders_new'],
                        self.stats['tenders_updated'],
                        self.stats['tenders_unchanged'],
                        self.stats['errors']
                    )
                    logger.info(f"✓ Scrape run #{self.scrape_run_id} completed: "
                                f"new={self.stats['tenders_new']}, "
                                f"updated={self.stats['tenders_updated']}, "
                                f"unchanged={self.stats['tenders_unchanged']}")
                except Exception as e:
                    logger.error(f"Failed to finalize scrape history: {e}")

            await self.conn.close()
            logger.info("DatabasePipeline: Connection closed")

    def close_spider(self, spider):
        return deferred_from_coro(self._close_spider_async(spider))

    def _compute_content_hash(self, adapter) -> str:
        """Compute SHA-256 hash of tender content for change detection."""
        # Fields to include in hash (core tender data that indicates changes)
        hash_fields = [
            'tender_id', 'title', 'description', 'status', 'winner',
            'estimated_value_mkd', 'actual_value_mkd', 'closing_date',
            'opening_date', 'procuring_entity', 'cpv_code', 'procedure_type'
        ]

        content_parts = []
        for field in hash_fields:
            value = adapter.get(field)
            if value is not None:
                content_parts.append(f"{field}:{value}")

        content_str = '|'.join(content_parts)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    async def _init_scrape_run(self, spider):
        """Initialize a scrape_history record for this run."""
        try:
            mode = getattr(spider, 'mode', 'scrape')
            category = getattr(spider, 'category', 'active')

            self.scrape_run_id = await self.conn.fetchval("""
                INSERT INTO scrape_history (mode, category, status)
                VALUES ($1, $2, 'running')
                RETURNING id
            """, mode, category)

            logger.info(f"✓ Started scrape run #{self.scrape_run_id} (mode={mode}, category={category})")
        except Exception as e:
            logger.warning(f"Could not create scrape_history record: {e}")
            # Non-fatal, continue without tracking

    async def _check_tender_change(self, tender_id: str, new_hash: str) -> str:
        """
        Check if tender exists and if content has changed.

        Returns:
            'new' - Tender doesn't exist in database
            'updated' - Tender exists but content changed
            'unchanged' - Tender exists and content is the same
        """
        try:
            existing = await self.conn.fetchrow("""
                SELECT content_hash, scrape_count FROM tenders
                WHERE tender_id = $1
            """, tender_id)

            if not existing:
                self.stats['tenders_new'] += 1
                return 'new'

            old_hash = existing['content_hash']

            if old_hash and old_hash == new_hash:
                self.stats['tenders_unchanged'] += 1
                return 'unchanged'
            else:
                self.stats['tenders_updated'] += 1
                return 'updated'

        except Exception as e:
            logger.warning(f"Error checking tender change: {e}")
            self.stats['errors'] += 1
            return 'new'  # Default to new on error

    async def process_item_async(self, item, spider):
        """Async database insertion with comprehensive error handling."""
        if not self.conn:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.error("❌ DATABASE_URL not set!")
                return item

            # Strip SQLAlchemy driver suffix (+asyncpg) for asyncpg.connect()
            database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

            try:
                self.conn = await asyncpg.connect(database_url)
                logger.info("✓ DatabasePipeline: Connected to database")
                # Initialize scrape run tracking
                await self._init_scrape_run(spider)
            except Exception as e:
                logger.error(f"❌ Failed to connect to database: {e}")
                return item

        adapter = ItemAdapter(item)

        try:
            if item.__class__.__name__ == 'TenderItem':
                tender_id = adapter.get('tender_id', 'UNKNOWN')
                logger.info(f"→ Processing tender: {tender_id}")

                # Compute content hash for change detection
                content_hash = self._compute_content_hash(adapter)
                adapter['content_hash'] = content_hash

                # Check if tender exists and if content changed
                change_result = await self._check_tender_change(tender_id, content_hash)

                await self.insert_tender(adapter, change_result)
                logger.info(f"✓ Saved tender: {tender_id} ({change_result})")

                # Insert related data (lots, bidders, amendments)
                await self.insert_tender_lots(self.conn, tender_id, adapter.get('lots_data'))
                await self.insert_tender_bidders(self.conn, tender_id, adapter.get('bidders_data'))
                await self.insert_tender_amendments(self.conn, tender_id, adapter.get('amendments_data'))

            elif item.__class__.__name__ == 'DocumentItem':
                doc_name = adapter.get('file_name', 'UNKNOWN')
                logger.info(f"→ Processing document: {doc_name}")
                await self.insert_document(adapter)
                logger.info(f"✓ Saved document: {doc_name}")
        except Exception as e:
            item_type = item.__class__.__name__
            item_id = adapter.get('tender_id') or adapter.get('file_name', 'UNKNOWN')
            logger.error(f"❌ Failed to save {item_type} [{item_id}]: {e}")
            logger.exception("Full traceback:")
            # Still return item so it's counted and not lost

        return item

    async def process_item(self, item, spider):
        """Process items asynchronously (Scrapy supports async pipelines natively)."""
        return await self.process_item_async(item, spider)

    def _parse_date_string(self, date_str):
        """Convert ISO date string to date object for asyncpg"""
        if not date_str or not isinstance(date_str, str):
            return None
        try:
            from datetime import date as date_type
            parts = date_str.split('-')
            if len(parts) == 3:
                return date_type(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            return None
        return None

    def _parse_datetime_string(self, dt_str):
        """Convert ISO datetime string to datetime object for asyncpg"""
        if not dt_str:
            return datetime.utcnow()
        if isinstance(dt_str, datetime):
            return dt_str
        if isinstance(dt_str, str):
            try:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            except Exception:
                return datetime.utcnow()
        return datetime.utcnow()

    async def insert_tender(self, item, change_result: str = 'new'):
        """
        Upsert tender into database with change tracking.

        Uses ON CONFLICT to update existing records while preserving history.

        Args:
            item: ItemAdapter with tender data
            change_result: 'new', 'updated', or 'unchanged'
        """
        # For unchanged tenders, update scrape_count, scraped_at, and backfill estimated values
        if change_result == 'unchanged':
            await self.conn.execute("""
                UPDATE tenders
                SET scrape_count = scrape_count + 1,
                    scraped_at = CURRENT_TIMESTAMP,
                    estimated_value_mkd = COALESCE($2, estimated_value_mkd),
                    estimated_value_eur = COALESCE($3, estimated_value_eur)
                WHERE tender_id = $1
            """, item.get('tender_id'), item.get('estimated_value_mkd'), item.get('estimated_value_eur'))
            logger.info(f"Tender {item.get('tender_id')} unchanged, updated scrape_count")
            return

        # Convert date strings to date objects for asyncpg
        opening_date = self._parse_date_string(item.get('opening_date'))
        closing_date = self._parse_date_string(item.get('closing_date'))
        publication_date = self._parse_date_string(item.get('publication_date'))
        contract_signing_date = self._parse_date_string(item.get('contract_signing_date'))
        bureau_delivery_date = self._parse_date_string(item.get('bureau_delivery_date'))
        last_amendment_date = self._parse_date_string(item.get('last_amendment_date'))
        scraped_at = self._parse_datetime_string(item.get('scraped_at'))

        # Map status values to database constraint (open, closed, awarded, cancelled)
        status = item.get('status', 'open')
        if status == 'active':
            status = 'open'

        # Phase 3 fields - Extract new contact and evaluation fields
        contact_person = item.get('contact_person')
        contact_email = item.get('contact_email')
        contact_phone = item.get('contact_phone')
        num_bidders = item.get('num_bidders')
        security_deposit_mkd = item.get('security_deposit_mkd')
        performance_guarantee_mkd = item.get('performance_guarantee_mkd')
        payment_terms = item.get('payment_terms')
        evaluation_method = item.get('evaluation_method')
        award_criteria = item.get('award_criteria')  # JSONB - will be parsed as JSON by asyncpg
        has_lots = item.get('has_lots')
        num_lots = item.get('num_lots')
        amendment_count = item.get('amendment_count', 0)  # Default to 0

        # Phase 5 fields - Incremental scraping
        content_hash = item.get('content_hash')
        source_category = item.get('source_category')

        # Determine if this is a new tender (for first_scraped_at)
        is_new = change_result == 'new'

        await self.conn.execute("""
            INSERT INTO tenders (
                tender_id, title, description, category, procuring_entity,
                opening_date, closing_date, publication_date,
                estimated_value_mkd, estimated_value_eur,
                actual_value_mkd, actual_value_eur,
                cpv_code, status, winner, source_url, language, scraped_at,
                procedure_type, contract_signing_date, contract_duration,
                contracting_entity_category, procurement_holder, bureau_delivery_date,
                contact_person, contact_email, contact_phone,
                num_bidders, security_deposit_mkd, performance_guarantee_mkd,
                payment_terms, evaluation_method, award_criteria,
                has_lots, num_lots, amendment_count, last_amendment_date,
                content_hash, source_category, first_scraped_at, scrape_count, last_modified
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42)
            ON CONFLICT (tender_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                winner = EXCLUDED.winner,
                estimated_value_mkd = COALESCE(EXCLUDED.estimated_value_mkd, tenders.estimated_value_mkd),
                estimated_value_eur = COALESCE(EXCLUDED.estimated_value_eur, tenders.estimated_value_eur),
                actual_value_mkd = EXCLUDED.actual_value_mkd,
                actual_value_eur = EXCLUDED.actual_value_eur,
                procedure_type = EXCLUDED.procedure_type,
                contract_signing_date = EXCLUDED.contract_signing_date,
                contract_duration = EXCLUDED.contract_duration,
                contracting_entity_category = EXCLUDED.contracting_entity_category,
                procurement_holder = EXCLUDED.procurement_holder,
                bureau_delivery_date = EXCLUDED.bureau_delivery_date,
                contact_person = EXCLUDED.contact_person,
                contact_email = EXCLUDED.contact_email,
                contact_phone = EXCLUDED.contact_phone,
                num_bidders = EXCLUDED.num_bidders,
                security_deposit_mkd = EXCLUDED.security_deposit_mkd,
                performance_guarantee_mkd = EXCLUDED.performance_guarantee_mkd,
                payment_terms = EXCLUDED.payment_terms,
                evaluation_method = EXCLUDED.evaluation_method,
                award_criteria = EXCLUDED.award_criteria,
                has_lots = EXCLUDED.has_lots,
                num_lots = EXCLUDED.num_lots,
                amendment_count = EXCLUDED.amendment_count,
                last_amendment_date = EXCLUDED.last_amendment_date,
                content_hash = EXCLUDED.content_hash,
                source_category = EXCLUDED.source_category,
                scrape_count = tenders.scrape_count + 1,
                last_modified = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
        """,
            item.get('tender_id'),
            item.get('title'),
            item.get('description'),
            item.get('category'),
            item.get('procuring_entity'),
            opening_date,
            closing_date,
            publication_date,
            item.get('estimated_value_mkd'),
            item.get('estimated_value_eur'),
            item.get('actual_value_mkd'),
            item.get('actual_value_eur'),
            item.get('cpv_code'),
            status,
            item.get('winner'),
            item.get('source_url'),
            item.get('language', 'mk'),
            scraped_at,
            item.get('procedure_type'),
            contract_signing_date,
            item.get('contract_duration'),
            item.get('contracting_entity_category'),
            item.get('procurement_holder'),
            bureau_delivery_date,
            contact_person,
            contact_email,
            contact_phone,
            num_bidders,
            security_deposit_mkd,
            performance_guarantee_mkd,
            payment_terms,
            evaluation_method,
            award_criteria,
            has_lots,
            num_lots,
            amendment_count,
            last_amendment_date,
            content_hash,
            source_category,
            scraped_at if is_new else None,  # first_scraped_at - only set for new tenders
            1,  # scrape_count starts at 1
            datetime.utcnow() if change_result == 'updated' else None  # last_modified
        )

        logger.info(f"Tender saved ({change_result}): {item.get('tender_id')}")

    async def insert_document(self, item):
        """
        Insert document into database with duplicate prevention.

        Uses file_hash for deduplication, falling back to file_url + tender_id.
        Includes new categorization fields: doc_category, doc_version, upload_date, file_hash.
        """
        file_url = item.get('file_url')
        tender_id = item.get('tender_id')
        file_hash = item.get('file_hash')

        # Check for duplicates using file_hash first (most reliable)
        if file_hash:
            existing_by_hash = await self.conn.fetchval("""
                SELECT doc_id FROM documents
                WHERE file_hash = $1
                LIMIT 1
            """, file_hash)

            if existing_by_hash:
                logger.info(f"Document already exists (hash: {file_hash[:16]}...), skipping: {item.get('file_name')}")
                return

        # Fallback: Check for duplicates using file_url + tender_id
        duplicate_key = f"{tender_id}:{file_url}"

        if duplicate_key in self.existing_documents:
            logger.info(f"Skipping duplicate document: {item.get('file_name')}")
            return

        # Check database for existing document by URL
        existing_by_url = await self.conn.fetchval("""
            SELECT doc_id FROM documents
            WHERE tender_id = $1 AND file_url = $2
            LIMIT 1
        """, tender_id, file_url)

        if existing_by_url:
            logger.info(f"Document already exists in database: {item.get('file_name')}")
            self.existing_documents.add(duplicate_key)
            return

        # Parse upload_date from item (may come from document metadata)
        upload_date = self._parse_date_string(item.get('upload_date'))

        # Insert new document with categorization fields
        await self.conn.execute("""
            INSERT INTO documents (
                tender_id, doc_type, file_name, file_path, file_url,
                content_text, extraction_status, file_size_bytes,
                page_count, mime_type,
                doc_category, doc_version, upload_date, file_hash
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (doc_id) DO UPDATE SET
                content_text = EXCLUDED.content_text,
                extraction_status = EXCLUDED.extraction_status,
                file_size_bytes = EXCLUDED.file_size_bytes,
                page_count = EXCLUDED.page_count,
                mime_type = EXCLUDED.mime_type,
                doc_category = EXCLUDED.doc_category,
                doc_version = EXCLUDED.doc_version,
                upload_date = EXCLUDED.upload_date,
                file_hash = EXCLUDED.file_hash,
                updated_at = CURRENT_TIMESTAMP
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
            item.get('mime_type'),
            item.get('doc_category'),  # New field - NULL allowed
            item.get('doc_version'),   # New field - NULL allowed
            upload_date,               # New field - NULL allowed
            file_hash                  # New field - for deduplication
        )

        # Add to cache
        self.existing_documents.add(duplicate_key)

        logger.info(
            f"✓ Document saved: {item.get('file_name')} "
            f"[{item.get('extraction_status')}] "
            f"[category: {item.get('doc_category') or 'N/A'}] "
            f"[hash: {file_hash[:16] if file_hash else 'N/A'}...]"
        )

    async def insert_tender_lots(self, conn, tender_id: str, lots_data: str):
        """
        Insert lot data for a tender.

        Args:
            conn: asyncpg connection object
            tender_id: ID of the tender
            lots_data: JSON string containing array of lot objects
        """
        if not lots_data:
            return

        try:
            lots = json.loads(lots_data)
            if not lots or not isinstance(lots, list):
                return

            for lot in lots:
                await conn.execute('''
                    INSERT INTO tender_lots (
                        tender_id, lot_number, lot_title, lot_description,
                        estimated_value_mkd, estimated_value_eur,
                        actual_value_mkd, actual_value_eur,
                        cpv_code, winner, quantity, unit
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (lot_id) DO NOTHING
                ''',
                    tender_id,
                    lot.get('lot_number'),
                    lot.get('lot_title'),
                    lot.get('lot_description'),
                    lot.get('estimated_value_mkd'),
                    lot.get('estimated_value_eur'),
                    lot.get('actual_value_mkd'),
                    lot.get('actual_value_eur'),
                    lot.get('cpv_code'),
                    lot.get('winner'),
                    lot.get('quantity'),
                    lot.get('unit')
                )

            logger.info(f"✓ Inserted {len(lots)} lots for tender {tender_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing lots JSON for {tender_id}: {e}")
        except Exception as e:
            logger.error(f"Error inserting lots for {tender_id}: {e}")

    async def insert_tender_bidders(self, conn, tender_id: str, bidders_data: str):
        """
        Insert bidder data for a tender.

        Args:
            conn: asyncpg connection object
            tender_id: ID of the tender
            bidders_data: JSON string containing array of bidder objects
        """
        if not bidders_data:
            return

        try:
            bidders = json.loads(bidders_data)
            if not bidders or not isinstance(bidders, list):
                return

            for bidder in bidders:
                await conn.execute('''
                    INSERT INTO tender_bidders (
                        tender_id, lot_id, company_name, company_tax_id,
                        company_address, bid_amount_mkd, bid_amount_eur,
                        is_winner, rank, disqualified, disqualification_reason
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (bidder_id) DO NOTHING
                ''',
                    tender_id,
                    bidder.get('lot_id'),  # UUID reference to tender_lots, may be NULL
                    bidder.get('company_name'),
                    bidder.get('company_tax_id'),
                    bidder.get('company_address'),
                    bidder.get('bid_amount_mkd'),
                    bidder.get('bid_amount_eur'),
                    bidder.get('is_winner', False),
                    bidder.get('rank'),
                    bidder.get('disqualified', False),
                    bidder.get('disqualification_reason')
                )

            logger.info(f"✓ Inserted {len(bidders)} bidders for tender {tender_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing bidders JSON for {tender_id}: {e}")
        except Exception as e:
            logger.error(f"Error inserting bidders for {tender_id}: {e}")

    async def insert_tender_amendments(self, conn, tender_id: str, amendments_data: str):
        """
        Insert amendment data for a tender.

        Args:
            conn: asyncpg connection object
            tender_id: ID of the tender
            amendments_data: JSON string containing array of amendment objects
        """
        if not amendments_data:
            return

        try:
            amendments = json.loads(amendments_data)
            if not amendments or not isinstance(amendments, list):
                return

            for amendment in amendments:
                # Parse amendment_date if it's a string
                amendment_date = self._parse_date_string(amendment.get('amendment_date'))

                await conn.execute('''
                    INSERT INTO tender_amendments (
                        tender_id, amendment_date, amendment_type,
                        field_changed, old_value, new_value,
                        reason, announcement_url
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (amendment_id) DO NOTHING
                ''',
                    tender_id,
                    amendment_date,
                    amendment.get('amendment_type'),
                    amendment.get('field_changed'),
                    amendment.get('old_value'),
                    amendment.get('new_value'),
                    amendment.get('reason'),
                    amendment.get('announcement_url')
                )

            logger.info(f"✓ Inserted {len(amendments)} amendments for tender {tender_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing amendments JSON for {tender_id}: {e}")
        except Exception as e:
            logger.error(f"Error inserting amendments for {tender_id}: {e}")
