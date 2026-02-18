"""
Scrapy pipelines for PDF handling and database insertion
Includes: PDF download, Cyrillic extraction, database storage

PHASE 2 Enhancements:
- Authenticated PDF downloads using saved session cookies
- Login page detection (prevents storing HTML as PDF)
- Raw JSON storage for debugging and data recovery
- Improved extraction status tracking
"""
import asyncpg
import asyncio
import os
import hashlib
import logging
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from itemadapter import ItemAdapter
from scrapy.utils.defer import deferred_from_coro
from scrapy.exceptions import DropItem
from scraper.items import DocumentItem, LotAwardItem, CompanyWallItem
import aiofiles
import fitz  # PyMuPDF
from yarl import URL

logger = logging.getLogger(__name__)

# Cookie file paths (shared with spiders)
AUTH_COOKIE_FILE = Path('/tmp/nabavki_auth_cookies.json')
CONTRACTS_COOKIE_FILE = Path('/tmp/contracts_auth_cookies.json')


class PDFDownloadPipeline:
    """
    REQUIREMENT 2: Large PDF support (10-20MB)

    Downloads PDF files from URLs and saves them locally.
    Handles large files with streaming and proper error handling.

    PHASE 2 Enhancement: Authenticated downloads using saved session cookies.
    Documents on e-nabavki.gov.mk require authentication - without cookies,
    the server returns a login page HTML instead of the actual PDF.
    """

    def __init__(self, files_store):
        self.files_store = Path(files_store)
        self.files_store.mkdir(parents=True, exist_ok=True)
        self.session = None
        self.cookies = None
        self.auth_loaded = False

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            files_store=crawler.settings.get('FILES_STORE', 'downloads/files')
        )

    def _load_auth_cookies(self):
        """
        Load saved authentication cookies from spider session files.
        Tries both nabavki_auth and contracts spider cookie files.
        """
        cookie_files = [AUTH_COOKIE_FILE, CONTRACTS_COOKIE_FILE]

        for cookie_file in cookie_files:
            if cookie_file.exists():
                try:
                    with open(cookie_file, 'r') as f:
                        self.cookies = json.load(f)
                    logger.info(f"✓ Loaded {len(self.cookies)} auth cookies from {cookie_file}")
                    self.auth_loaded = True
                    return True
                except Exception as e:
                    logger.warning(f"Could not load cookies from {cookie_file}: {e}")

        logger.warning("⚠ No auth cookies found - PDF downloads may fail for protected documents")
        return False

    def open_spider(self, spider):
        logger.info(f"PDFDownloadPipeline: Storing files in {self.files_store}")

        # Load saved authentication cookies
        self._load_auth_cookies()

        # Create aiohttp session with cookie jar
        import aiohttp
        jar = aiohttp.CookieJar()
        self.session = aiohttp.ClientSession(cookie_jar=jar)

        # Add cookies to session for e-nabavki.gov.mk domain
        if self.cookies:
            for cookie in self.cookies:
                try:
                    domain = cookie.get('domain', 'e-nabavki.gov.mk')
                    # Ensure domain doesn't start with a dot
                    if domain.startswith('.'):
                        domain = domain[1:]

                    self.session.cookie_jar.update_cookies(
                        {cookie['name']: cookie['value']},
                        URL(f"https://{domain}/")
                    )
                except Exception as e:
                    logger.debug(f"Could not add cookie {cookie.get('name')}: {e}")

            logger.info(f"✓ Added {len(self.cookies)} cookies to download session")

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

        # Skip ohridskabanka.mk documents (external bank guarantees)
        if 'ohridskabanka' in file_url.lower():
            logger.info(f"Skipping ohridskabanka.mk document: {file_url}")
            adapter['extraction_status'] = 'skipped_external'
            return item

        try:
            # Generate unique filename based on URL hash
            url_hash = hashlib.md5(file_url.encode('utf-8')).hexdigest()
            tender_id = adapter.get('tender_id', 'unknown')
            # Replace / with _ in tender_id to create valid filename (e.g., "21513/2025" -> "21513_2025")
            safe_tender_id = tender_id.replace('/', '_')
            file_ext = self._get_extension(file_url)
            filename = f"{safe_tender_id}_{url_hash}{file_ext}"
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

                # PHASE 2: Detect if downloaded file is a login page (HTML) instead of actual PDF
                # This happens when authentication cookies are missing or expired
                with open(file_path, 'rb') as f:
                    file_header = f.read(1024)

                is_valid_pdf = file_header.startswith(b'%PDF')
                is_html_page = (
                    b'<html' in file_header.lower() or
                    b'<!doctype' in file_header.lower() or
                    b'<head>' in file_header.lower()
                )
                # Check for login page indicators in HTML
                is_login_page = is_html_page and (
                    b'login' in file_header.lower() or
                    b'password' in file_header.lower() or
                    # Macedonian: "Корисничко име" (username), "Лозинка" (password)
                    'корисничко'.encode('utf-8') in file_header.lower() or
                    'лозинка'.encode('utf-8') in file_header.lower()
                )

                if is_login_page:
                    logger.warning(f"⚠ Downloaded file is LOGIN PAGE (auth required): {filename}")
                    adapter['extraction_status'] = 'auth_required'
                    file_path.unlink()  # Delete invalid file
                    return item
                elif is_html_page and not is_valid_pdf:
                    logger.warning(f"⚠ Downloaded file is HTML (not PDF): {filename}")
                    adapter['extraction_status'] = 'download_invalid'
                    file_path.unlink()  # Delete invalid file
                    return item
                elif not is_valid_pdf and actual_size < 5000:
                    # Small file that's not a PDF - likely an error page
                    logger.warning(f"⚠ Downloaded file is not a valid PDF: {filename}")
                    adapter['extraction_status'] = 'download_invalid'
                    file_path.unlink()
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

    NON-BLOCKING: Documents are marked as 'pending' and saved to database.
    Actual text extraction (OCR) happens in a separate worker process to avoid
    blocking the scraper. This allows the scraper to continue immediately after
    downloading files.

    Worker process: A separate CLI script processes documents with status='pending'
    and updates the extraction_status, content_text, and specifications_json fields.
    """

    async def process_item(self, item, spider):
        """
        Mark document as pending for extraction (non-blocking).

        The actual extraction happens in a separate worker process that:
        1. Queries documents with extraction_status='pending'
        2. Runs parse_file() with OCR if needed
        3. Updates extraction_status, content_text, specifications_json

        This keeps the scraper fast and non-blocking.
        """
        adapter = ItemAdapter(item)

        # Only process DocumentItem with file_path
        if item.__class__.__name__ != 'DocumentItem':
            return item

        file_path = adapter.get('file_path')
        if not file_path or not Path(file_path).exists():
            return item

        # Skip ohridskabanka.mk documents (external bank guarantees)
        file_url = adapter.get('file_url', '')
        if 'ohridskabanka' in file_url.lower():
            logger.info(f"Skipping extraction for ohridskabanka.mk document: {file_path}")
            adapter['extraction_status'] = 'skipped_external'
            return item

        # NON-BLOCKING: Mark as pending instead of extracting immediately
        # A separate worker will process this document asynchronously
        file_ext = Path(file_path).suffix.lower()

        # Check if file type is supported for extraction
        from document_parser import is_supported_document

        if is_supported_document(file_path):
            # Mark as pending - worker will extract later
            adapter['extraction_status'] = 'pending'
            adapter['content_text'] = None
            adapter['specifications_json'] = None
            adapter['page_count'] = None

            logger.info(f"Marked document as pending for extraction: {adapter.get('file_name')}")
        else:
            # Unsupported file types are marked immediately
            logger.warning(f"Unsupported file type: {file_ext} for {adapter.get('file_name')}")
            adapter['extraction_status'] = 'unsupported'
            adapter['content_text'] = None
            adapter['specifications_json'] = None

        # Get file metadata
        file_path_obj = Path(file_path)
        if file_path_obj.exists():
            file_stats = file_path_obj.stat()
            adapter['file_size_bytes'] = file_stats.st_size

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
            source_url = adapter.get('source_url', 'unknown')
            logger.error(f"Validation failed: Missing tender_id for tender from {source_url}")
            raise DropItem(f"Missing tender_id - skipping tender from {source_url}")

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
        self.pool = None  # Connection pool instead of single connection
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
        """Close database connection pool and finalize scrape run."""
        if self.pool:
            # Finalize scrape_history record if we have one
            if self.scrape_run_id:
                try:
                    async with self.pool.acquire() as conn:
                        await conn.execute("""
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

            await self.pool.close()
            logger.info("DatabasePipeline: Connection pool closed")

    def close_spider(self, spider):
        return deferred_from_coro(self._close_spider_async(spider))

    # Procedure type normalization map (Cyrillic & variant labels → canonical)
    PROCEDURE_TYPE_MAP = {
        'отворена постапка': 'Open',
        'open procedure': 'Open',
        'open': 'Open',
        'pt_open': 'Open',
        'поедноставена отворена постапка': 'SimplifiedOpenProcedure',
        'simplified open procedure': 'SimplifiedOpenProcedure',
        'набавки од мала вредност': 'LowEstimatedValueProcedure',
        'low estimated value procedure': 'LowEstimatedValueProcedure',
        'барање за прибирање на понуди': 'RequestForProposal',
        'request for proposal': 'RequestForProposal',
        'постапка со преговарање со претходно објавување': 'NegotiatedWithPublication',
        'negotiated procedure with prior publication': 'NegotiatedWithPublication',
        'постапка со преговарање без претходно објавување': 'NegotiatedWithoutPublication',
        'negotiated procedure without prior publication': 'NegotiatedWithoutPublication',
        'квалификационен систем': 'QualificationSystem',
        'qualification system': 'QualificationSystem',
        'конкурс за избор на идејно решение': 'BidForChoosingIdealSolution',
    }

    @staticmethod
    def _normalize_procedure_type(raw: str) -> str:
        """Normalize procedure type to canonical English name."""
        if not raw:
            return raw
        cleaned = raw.strip().lower()
        # Try direct map
        for key, canonical in DatabasePipeline.PROCEDURE_TYPE_MAP.items():
            if key in cleaned:
                return canonical
        # Return original with title case if no match
        return raw.strip()

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
        """Initialize a scrape_history record for this run (deprecated, use _init_scrape_run_with_conn)."""
        async with self.pool.acquire() as conn:
            await self._init_scrape_run_with_conn(spider, conn)

    async def _init_scrape_run_with_conn(self, spider, conn):
        """Initialize a scrape_history record for this run using provided connection."""
        try:
            mode = getattr(spider, 'mode', 'scrape')
            category = getattr(spider, 'category', 'active')

            self.scrape_run_id = await conn.fetchval("""
                INSERT INTO scrape_history (mode, category, status)
                VALUES ($1, $2, 'running')
                RETURNING id
            """, mode, category)

            logger.info(f"✓ Started scrape run #{self.scrape_run_id} (mode={mode}, category={category})")
        except Exception as e:
            logger.warning(f"Could not create scrape_history record: {e}")
            # Non-fatal, continue without tracking

    async def _check_tender_change(self, tender_id: str, new_hash: str, conn) -> str:
        """
        Check if tender exists and if content has changed.

        Returns:
            'new' - Tender doesn't exist in database
            'updated' - Tender exists but content changed
            'unchanged' - Tender exists and content is the same
        """
        try:
            existing = await conn.fetchrow("""
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
        if not self.pool:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.error("❌ DATABASE_URL not set!")
                return item

            # Strip SQLAlchemy driver suffix (+asyncpg) for asyncpg.connect()
            database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

            try:
                self.pool = await asyncpg.create_pool(
                    database_url,
                    min_size=2,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("✓ DatabasePipeline: Connection pool created")
                # Initialize scrape run tracking
                async with self.pool.acquire() as conn:
                    await self._init_scrape_run_with_conn(spider, conn)
            except Exception as e:
                logger.error(f"❌ Failed to create connection pool: {e}")
                return item

        adapter = ItemAdapter(item)

        try:
            async with self.pool.acquire() as conn:
                if item.__class__.__name__ == 'TenderItem':
                    tender_id = adapter.get('tender_id', 'UNKNOWN')
                    logger.info(f"→ Processing tender: {tender_id}")

                    # Compute content hash for change detection
                    content_hash = self._compute_content_hash(adapter)
                    adapter['content_hash'] = content_hash

                    # Check if tender exists and if content changed
                    change_result = await self._check_tender_change(tender_id, content_hash, conn)

                    await self.insert_tender(adapter, change_result, conn)
                    logger.info(f"✓ Saved tender: {tender_id} ({change_result})")

                    # Insert related data (lots, bidders, amendments)
                    await self.insert_tender_lots(conn, tender_id, adapter.get('lots_data'))
                    await self.insert_tender_bidders(conn, tender_id, adapter.get('bidders_data'))
                    await self.insert_tender_amendments(conn, tender_id, adapter.get('amendments_data'))
                    # Insert documents captured on tender (fallback if DocumentItems not processed)
                    docs_data = adapter.get('documents_data')
                    if docs_data:
                        logger.info(f"Inserting {len(docs_data)} document(s) for tender {tender_id}")
                        for doc in docs_data:
                            # Skip if doc is not a dict (sometimes it's a string URL)
                            if not isinstance(doc, dict):
                                logger.warning(f"Skipping non-dict document: {type(doc)}")
                                continue
                            # Map 'url' to 'file_url' if needed (documents_data uses 'url')
                            if 'url' in doc and 'file_url' not in doc:
                                doc['file_url'] = doc['url']
                            # Ensure tender_id is set
                            if 'tender_id' not in doc:
                                doc['tender_id'] = tender_id
                            # Ensure required fields
                            doc.setdefault('doc_type', doc.get('doc_category') or 'document')
                            doc.setdefault('extraction_status', 'pending')
                            await self.insert_document(doc, conn)

                elif item.__class__.__name__ == 'DocumentItem':
                    doc_name = adapter.get('file_name', 'UNKNOWN')
                    logger.info(f"→ Processing document: {doc_name}")
                    await self.insert_document(adapter, conn)

                elif item.__class__.__name__ == 'LotAwardItem':
                    tender_id = adapter.get('tender_id', 'UNKNOWN')
                    award_num = adapter.get('award_number', 1)
                    logger.info(f"-> Processing lot award: {tender_id} #{award_num}")
                    await self.insert_lot_award(adapter, conn)
                    logger.info(f"Saved lot award: {tender_id} #{award_num}")

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

    def _to_decimal(self, value):
        """Convert value to Decimal for database insertion."""
        if value is None:
            return None
        try:
            from decimal import Decimal, InvalidOperation
            if isinstance(value, Decimal):
                return value
            if isinstance(value, (int, float)):
                return Decimal(str(value))
            if isinstance(value, str):
                # Remove currency symbols and whitespace
                clean_value = value.replace(',', '').replace(' ', '').strip()
                if not clean_value:
                    return None
                return Decimal(clean_value)
            return None
        except (InvalidOperation, ValueError, TypeError):
            return None

    async def insert_tender(self, item, change_result: str = 'new', conn=None):
        """
        Upsert tender into database with change tracking.

        Uses ON CONFLICT to update existing records while preserving history.

        Args:
            item: ItemAdapter with tender data
            change_result: 'new', 'updated', or 'unchanged'
            conn: asyncpg connection (acquired from pool)
        """
        # For unchanged tenders, update scrape_count, scraped_at, and backfill estimated values + EUR
        if change_result == 'unchanged':
            # Calculate EUR if MKD available
            MKD_TO_EUR = Decimal('61.5')
            _est_mkd = item.get('estimated_value_mkd')
            _est_eur = item.get('estimated_value_eur')
            if _est_mkd and not _est_eur:
                try:
                    _est_eur = (Decimal(str(_est_mkd)) / MKD_TO_EUR).quantize(Decimal('0.01'))
                except Exception:
                    _est_eur = None
            await conn.execute("""
                UPDATE tenders
                SET scrape_count = scrape_count + 1,
                    scraped_at = CURRENT_TIMESTAMP,
                    estimated_value_mkd = COALESCE($2, estimated_value_mkd),
                    estimated_value_eur = COALESCE($3, estimated_value_eur)
                WHERE tender_id = $1
            """, item.get('tender_id'), item.get('estimated_value_mkd'), _est_eur)
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

        # Auto-calculate EUR values from MKD (1 EUR ≈ 61.5 MKD)
        MKD_TO_EUR = Decimal('61.5')
        est_mkd = item.get('estimated_value_mkd')
        act_mkd = item.get('actual_value_mkd')
        est_eur = item.get('estimated_value_eur')
        act_eur = item.get('actual_value_eur')
        if est_mkd and not est_eur:
            try:
                est_eur = (Decimal(str(est_mkd)) / MKD_TO_EUR).quantize(Decimal('0.01'))
            except Exception:
                est_eur = None
        if act_mkd and not act_eur:
            try:
                act_eur = (Decimal(str(act_mkd)) / MKD_TO_EUR).quantize(Decimal('0.01'))
            except Exception:
                act_eur = None

        # Phase 5 fields - Incremental scraping
        content_hash = item.get('content_hash')
        source_category = item.get('source_category')

        # PHASE 2: Build raw_data_json from all scraped fields for debugging and data recovery
        raw_data = {
            'tender_id': item.get('tender_id'),
            'title': item.get('title'),
            'description': item.get('description'),
            'category': item.get('category'),
            'procuring_entity': item.get('procuring_entity'),
            'opening_date': item.get('opening_date'),
            'closing_date': item.get('closing_date'),
            'publication_date': item.get('publication_date'),
            'estimated_value_mkd': str(item.get('estimated_value_mkd')) if item.get('estimated_value_mkd') else None,
            'estimated_value_eur': str(item.get('estimated_value_eur')) if item.get('estimated_value_eur') else None,
            'actual_value_mkd': str(item.get('actual_value_mkd')) if item.get('actual_value_mkd') else None,
            'actual_value_eur': str(item.get('actual_value_eur')) if item.get('actual_value_eur') else None,
            'cpv_code': item.get('cpv_code'),
            'status': status,
            'winner': item.get('winner'),
            'source_url': item.get('source_url'),
            'procedure_type': self._normalize_procedure_type(item.get('procedure_type')),
            'contract_signing_date': item.get('contract_signing_date'),
            'contract_duration': item.get('contract_duration'),
            'contracting_entity_category': item.get('contracting_entity_category'),
            'procurement_holder': item.get('procurement_holder'),
            'bureau_delivery_date': item.get('bureau_delivery_date'),
            'contact_person': contact_person,
            'contact_email': contact_email,
            'contact_phone': contact_phone,
            'num_bidders': num_bidders,
            'security_deposit_mkd': str(security_deposit_mkd) if security_deposit_mkd else None,
            'performance_guarantee_mkd': str(performance_guarantee_mkd) if performance_guarantee_mkd else None,
            'payment_terms': payment_terms,
            'evaluation_method': evaluation_method,
            'has_lots': has_lots,
            'num_lots': num_lots,
            'bidders_data': item.get('bidders_data'),
            'lots_data': item.get('lots_data'),
            'documents_data': [doc if isinstance(doc, dict) else str(doc) for doc in (item.get('documents_data') or [])],
            'scraped_at': item.get('scraped_at'),
            'source_category': source_category,
            'raw_page_html': item.get('raw_page_html'),  # Full HTML for AI parsing
            'items_table_html': item.get('items_table_html'),  # Items table for AI
        }
        raw_data_json = json.dumps(raw_data, ensure_ascii=False, default=str)

        # Determine if this is a new tender (for first_scraped_at)
        is_new = change_result == 'new'

        await conn.execute("""
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
                content_hash, source_category, first_scraped_at, scrape_count, last_modified,
                raw_data_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43)
            ON CONFLICT (tender_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                winner = EXCLUDED.winner,
                estimated_value_mkd = COALESCE(EXCLUDED.estimated_value_mkd, tenders.estimated_value_mkd),
                estimated_value_eur = COALESCE(EXCLUDED.estimated_value_eur, tenders.estimated_value_eur),
                actual_value_mkd = COALESCE(EXCLUDED.actual_value_mkd, tenders.actual_value_mkd),
                actual_value_eur = COALESCE(EXCLUDED.actual_value_eur, tenders.actual_value_eur),
                procedure_type = EXCLUDED.procedure_type,
                opening_date = COALESCE(EXCLUDED.opening_date, tenders.opening_date),
                closing_date = COALESCE(EXCLUDED.closing_date, tenders.closing_date),
                publication_date = COALESCE(EXCLUDED.publication_date, tenders.publication_date),
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
                updated_at = CURRENT_TIMESTAMP,
                raw_data_json = EXCLUDED.raw_data_json
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
            est_eur,
            item.get('actual_value_mkd'),
            act_eur,
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
            datetime.utcnow() if change_result == 'updated' else None,  # last_modified
            raw_data_json  # $43 - PHASE 2: Store raw scraped data for debugging
        )

        logger.info(f"Tender saved ({change_result}): {item.get('tender_id')}")

    async def insert_document(self, item, conn=None):
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
            existing_by_hash = await conn.fetchval("""
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
        existing_by_url = await conn.fetchval("""
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

        # Insert new document with categorization fields and extracted metadata
        # Use ON CONFLICT DO NOTHING for both doc_id and tender_id+file_url unique constraints
        await conn.execute("""
            INSERT INTO documents (
                tender_id, doc_type, file_name, file_path, file_url,
                content_text, extraction_status, file_size_bytes,
                page_count, mime_type,
                doc_category, doc_version, upload_date, file_hash,
                specifications_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT DO NOTHING
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
            file_hash,                 # New field - for deduplication
            item.get('specifications_json')  # JSON with CPV codes, emails, phones, company names
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

    async def insert_lot_award(self, item, conn=None):
        """Insert lot-level award data into lot_awards table."""
        try:
            await conn.execute('''
                INSERT INTO lot_awards (
                    tender_id, award_number, lot_numbers, winner_name,
                    winner_tax_id, contract_value_mkd, contract_value_no_vat,
                    contract_date, contract_type, notification_url,
                    raw_data, source_url
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
                ON CONFLICT (tender_id, award_number) DO UPDATE SET
                    lot_numbers = EXCLUDED.lot_numbers,
                    winner_name = EXCLUDED.winner_name,
                    winner_tax_id = EXCLUDED.winner_tax_id,
                    contract_value_mkd = EXCLUDED.contract_value_mkd,
                    contract_value_no_vat = EXCLUDED.contract_value_no_vat,
                    contract_date = EXCLUDED.contract_date,
                    contract_type = EXCLUDED.contract_type,
                    notification_url = EXCLUDED.notification_url,
                    raw_data = EXCLUDED.raw_data,
                    source_url = EXCLUDED.source_url
            ''',
                item.get('tender_id'),
                item.get('award_number', 1),
                item.get('lot_numbers'),
                item.get('winner_name'),
                item.get('winner_tax_id'),
                self._to_decimal(item.get('contract_value_mkd')),
                self._to_decimal(item.get('contract_value_no_vat')),
                self._parse_date_string(item.get('contract_date')),
                item.get('contract_type'),
                item.get('notification_url'),
                item.get('raw_data'),
                item.get('source_url')
            )
        except Exception as e:
            logger.error(f"Failed to insert lot award: {e}")
            raise

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
                    ON CONFLICT (tender_id, company_name) DO UPDATE SET
                        bid_amount_mkd = COALESCE(EXCLUDED.bid_amount_mkd, tender_bidders.bid_amount_mkd),
                        bid_amount_eur = COALESCE(EXCLUDED.bid_amount_eur, tender_bidders.bid_amount_eur),
                        is_winner = COALESCE(EXCLUDED.is_winner, tender_bidders.is_winner),
                        rank = COALESCE(EXCLUDED.rank, tender_bidders.rank)
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


# ==============================================================================
# E-PAZAR PIPELINES (for e-pazar.gov.mk API spider)
# ==============================================================================

class EPazarValidationPipeline:
    """
    Validate e-Pazar tender data before database insertion.
    """

    def process_item(self, item, spider):
        """Validate e-pazar item data."""
        adapter = ItemAdapter(item)

        # Only validate EPazarApiItem
        if item.__class__.__name__ != 'EPazarApiItem':
            return item

        # Validate required fields
        tender_id = adapter.get('tender_id')
        if not tender_id:
            source_url = adapter.get('source_url', 'unknown')
            logger.error(f"EPazar validation failed: Missing tender_id from {source_url}")
            raise DropItem(f"Missing tender_id - skipping EPazar tender from {source_url}")

        # Title fallback logic
        title = adapter.get('title')
        if not title or len(str(title).strip()) < 3:
            fallback_title = (
                adapter.get('description') or
                adapter.get('contracting_authority') or
                f"E-Pazar Tender {tender_id}"
            )
            adapter['title'] = fallback_title
            logger.warning(f"Missing title for {tender_id}, using fallback: {fallback_title[:50]}")

        logger.info(f"EPazar validation passed: {tender_id}")
        return item


class EPazarDatabasePipeline:
    """
    Insert e-Pazar scraped tenders and contracts into PostgreSQL.

    Features:
    - Connection pool created once in open_spider() (not per-item)
    - UPSERT logic for duplicate handling
    - Separate epazar_tenders table
    """

    def __init__(self):
        self.pool = None
        self.stats = {
            'tenders_inserted': 0,
            'tenders_updated': 0,
            'documents_inserted': 0,
            'items_inserted': 0,
            'offers_inserted': 0,
            'errors': 0,
        }

    def open_spider(self, spider):
        """Initialize (pool created on first item to get event loop)."""
        logger.info("EPazarDatabasePipeline: Ready")

    async def _ensure_pool(self):
        """Create connection pool if not exists (called from async context)."""
        if self.pool is not None:
            return True

        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("❌ DATABASE_URL not set!")
            return False

        # Strip SQLAlchemy driver suffix
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

        try:
            self.pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("✓ EPazarDatabasePipeline: Connection pool created")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create connection pool: {e}")
            return False

    async def _close_spider_async(self, spider):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info(f"EPazarDatabasePipeline: Pool closed. Stats: {self.stats}")

    def close_spider(self, spider):
        return deferred_from_coro(self._close_spider_async(spider))

    async def process_item(self, item, spider):
        """Process e-pazar items asynchronously."""
        adapter = ItemAdapter(item)

        # Only process EPazarApiItem
        if item.__class__.__name__ != 'EPazarApiItem':
            return item

        # Ensure pool exists
        if not await self._ensure_pool():
            return item

        tender_id = adapter.get('tender_id', 'UNKNOWN')
        logger.info(f"→ Processing e-Pazar tender: {tender_id}")

        try:
            async with self.pool.acquire() as conn:
                await self._upsert_epazar_tender(adapter, conn)
                logger.info(f"✓ Saved e-Pazar tender: {tender_id}")

                # Insert documents if present
                docs_data = adapter.get('documents_data')
                if docs_data:
                    await self._insert_epazar_documents(tender_id, docs_data, conn)

                # Normalize items into epazar_items table
                items_data = adapter.get('items_data')
                if items_data:
                    await self._insert_epazar_items(tender_id, items_data, conn)

                # For signed contracts, insert the winning offer
                winner_name = adapter.get('winner_name')
                contract_value = adapter.get('contract_value_mkd')
                if winner_name and contract_value:
                    await self._insert_epazar_offer(
                        tender_id=tender_id,
                        supplier_name=winner_name,
                        supplier_id=adapter.get('winner_id'),
                        supplier_address=adapter.get('winner_address'),
                        supplier_city=adapter.get('winner_city'),
                        bid_amount=float(contract_value),
                        is_winner=True,
                        conn=conn
                    )

        except Exception as e:
            logger.error(f"❌ Failed to save e-Pazar item [{tender_id}]: {e}")
            logger.exception("Full traceback:")
            self.stats['errors'] += 1

        return item

    def _parse_date_string(self, date_str):
        """Convert date string to date object."""
        if not date_str or not isinstance(date_str, str):
            return None
        try:
            from datetime import date as date_type
            parts = date_str.split('-')
            if len(parts) >= 3:
                return date_type(int(parts[0]), int(parts[1]), int(parts[2][:2]))
        except Exception:
            return None
        return None

    async def _upsert_epazar_tender(self, adapter, conn):
        """Upsert e-pazar tender with ON CONFLICT handling."""
        tender_id = adapter.get('tender_id')

        # Parse dates
        publication_date = self._parse_date_string(adapter.get('publication_date'))
        closing_date = self._parse_date_string(adapter.get('closing_date') or adapter.get('deadline_date'))
        contract_date = self._parse_date_string(adapter.get('contract_date'))

        # Convert contracting_authority_id to string (API returns integer)
        ca_id = adapter.get('contracting_authority_id')
        contracting_authority_id = str(ca_id) if ca_id is not None else None

        # Check if exists
        existing = await conn.fetchval(
            "SELECT tender_id FROM epazar_tenders WHERE tender_id = $1",
            tender_id
        )

        if existing:
            # Parse raw_data and items_data for JSONB storage
            raw_data_json = None
            items_data_json = None
            raw_data = adapter.get('raw_data')
            items_data = adapter.get('items_data')

            if raw_data:
                try:
                    raw_data_json = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                except:
                    pass
            if items_data:
                try:
                    items_data_json = json.loads(items_data) if isinstance(items_data, str) else items_data
                except:
                    pass

            # UPDATE existing record (only columns that exist in the table)
            await conn.execute("""
                UPDATE epazar_tenders SET
                    title = COALESCE($2, title),
                    description = COALESCE($3, description),
                    contracting_authority = COALESCE($4, contracting_authority),
                    contracting_authority_id = COALESCE($5, contracting_authority_id),
                    estimated_value_mkd = COALESCE($6, estimated_value_mkd),
                    awarded_value_mkd = COALESCE($7, awarded_value_mkd),
                    procedure_type = COALESCE($8, procedure_type),
                    status = COALESCE($9, status),
                    publication_date = COALESCE($10, publication_date),
                    closing_date = COALESCE($11, closing_date),
                    contract_date = COALESCE($12, contract_date),
                    contract_number = COALESCE($13, contract_number),
                    source_url = COALESCE($14, source_url),
                    source_category = COALESCE($15, source_category),
                    content_hash = $16,
                    raw_data_json = COALESCE($17, raw_data_json),
                    items_data = COALESCE($18, items_data),
                    updated_at = CURRENT_TIMESTAMP
                WHERE tender_id = $1
            """,
                tender_id,
                adapter.get('title'),
                adapter.get('description'),
                adapter.get('contracting_authority'),
                contracting_authority_id,
                adapter.get('estimated_value_mkd'),
                adapter.get('contract_value_mkd'),  # Maps to awarded_value_mkd
                adapter.get('procurement_type'),  # Maps to procedure_type
                adapter.get('status'),
                publication_date,
                closing_date,
                contract_date,
                adapter.get('contract_number'),
                adapter.get('source_url'),
                adapter.get('source_category'),
                adapter.get('content_hash'),
                json.dumps(raw_data_json, ensure_ascii=False) if raw_data_json else None,
                json.dumps(items_data_json, ensure_ascii=False) if items_data_json else None,
            )
            self.stats['tenders_updated'] += 1
            logger.info(f"Updated e-Pazar tender: {tender_id}")
        else:
            # Parse raw_data and items_data for JSONB storage (for INSERT)
            raw_data_json = None
            items_data_json = None
            raw_data = adapter.get('raw_data')
            items_data = adapter.get('items_data')

            if raw_data:
                try:
                    raw_data_json = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                except:
                    pass
            if items_data:
                try:
                    items_data_json = json.loads(items_data) if isinstance(items_data, str) else items_data
                except:
                    pass

            # INSERT new record (only columns that exist in the table)
            await conn.execute("""
                INSERT INTO epazar_tenders (
                    tender_id, title, description,
                    contracting_authority, contracting_authority_id,
                    estimated_value_mkd, awarded_value_mkd,
                    procedure_type, status,
                    publication_date, closing_date, contract_date,
                    contract_number, source_url, source_category, content_hash,
                    raw_data_json, items_data,
                    language, scraped_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, 'mk', CURRENT_TIMESTAMP
                )
            """,
                tender_id,
                adapter.get('title'),
                adapter.get('description'),
                adapter.get('contracting_authority'),
                contracting_authority_id,
                adapter.get('estimated_value_mkd'),
                adapter.get('contract_value_mkd'),  # Maps to awarded_value_mkd
                adapter.get('procurement_type'),  # Maps to procedure_type
                adapter.get('status'),
                publication_date,
                closing_date,
                contract_date,
                adapter.get('contract_number'),
                adapter.get('source_url'),
                adapter.get('source_category'),
                adapter.get('content_hash'),
                json.dumps(raw_data_json, ensure_ascii=False) if raw_data_json else None,
                json.dumps(items_data_json, ensure_ascii=False) if items_data_json else None,
            )
            self.stats['tenders_inserted'] += 1
            logger.info(f"Inserted e-Pazar tender: {tender_id}")

    async def _insert_epazar_documents(self, tender_id: str, docs_data: str, conn):
        """Insert documents for an e-pazar tender."""
        try:
            docs = json.loads(docs_data)
            if not docs or not isinstance(docs, list):
                return

            inserted_count = 0
            for doc in docs:
                file_url = doc.get('file_url')
                if not file_url:
                    continue

                # Check if document already exists
                existing = await conn.fetchval(
                    "SELECT doc_id FROM epazar_documents WHERE tender_id = $1 AND file_url = $2",
                    tender_id, file_url
                )

                if not existing:
                    await conn.execute("""
                        INSERT INTO epazar_documents (
                            tender_id, doc_type, file_name, file_url, upload_date
                        ) VALUES ($1, $2, $3, $4, $5)
                    """,
                        tender_id,
                        doc.get('doc_type', 'document'),
                        doc.get('file_name'),
                        file_url,
                        self._parse_date_string(doc.get('upload_date'))
                    )
                    inserted_count += 1
                    self.stats['documents_inserted'] += 1

            if inserted_count > 0:
                logger.info(f"✓ Inserted {inserted_count} documents for tender {tender_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing documents JSON for {tender_id}: {e}")
        except Exception as e:
            logger.error(f"Error inserting documents for {tender_id}: {e}")

    async def _insert_epazar_items(self, tender_id: str, items_data: str, conn):
        """
        Normalize items from JSON into epazar_items table.
        This populates the proper normalized items table for better querying.
        """
        try:
            items = json.loads(items_data) if isinstance(items_data, str) else items_data
            if not items or not isinstance(items, list):
                return

            inserted_count = 0
            for item in items:
                line_number = item.get('line_number', 0)
                item_name = item.get('item_name', '').strip()

                if not item_name:
                    continue

                # Check if item already exists for this tender and line number
                existing = await conn.fetchval(
                    "SELECT item_id FROM epazar_items WHERE tender_id = $1 AND line_number = $2",
                    tender_id, line_number
                )

                if not existing:
                    # Insert new item with brand and attribute data
                    await conn.execute("""
                        INSERT INTO epazar_items (
                            tender_id, line_number, item_name, item_description,
                            quantity, unit, estimated_unit_price_mkd, estimated_total_price_mkd,
                            accepted_brands, product_attributes
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                        tender_id,
                        line_number,
                        item_name,
                        item.get('item_description'),
                        item.get('quantity'),
                        item.get('unit'),
                        item.get('estimated_unit_price_mkd'),
                        item.get('estimated_total_price_mkd'),
                        item.get('accepted_brands'),  # TEXT[] - list of brand names
                        json.dumps(item.get('product_attributes')) if item.get('product_attributes') else None  # JSONB
                    )
                    inserted_count += 1
                else:
                    # Update existing item with new brand/attribute data if available
                    brands = item.get('accepted_brands')
                    attrs = item.get('product_attributes')
                    if brands or attrs:
                        await conn.execute("""
                            UPDATE epazar_items SET
                                accepted_brands = COALESCE($3, accepted_brands),
                                product_attributes = COALESCE($4::jsonb, product_attributes),
                                updated_at = NOW()
                            WHERE tender_id = $1 AND line_number = $2
                        """,
                            tender_id,
                            line_number,
                            brands,
                            json.dumps(attrs) if attrs else None
                        )

            if inserted_count > 0:
                logger.info(f"✓ Inserted {inserted_count} items for tender {tender_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing items JSON for {tender_id}: {e}")
        except Exception as e:
            logger.error(f"Error inserting items for {tender_id}: {e}")

    async def _insert_epazar_offer(self, tender_id: str, supplier_name: str, supplier_id: int,
                                   supplier_address: str, supplier_city: str, bid_amount: float,
                                   is_winner: bool, conn):
        """Insert or update an offer/bid for an e-pazar tender."""
        try:
            # Check if offer already exists for this tender and supplier
            existing = await conn.fetchval(
                "SELECT offer_id FROM epazar_offers WHERE tender_id = $1 AND supplier_name = $2",
                tender_id, supplier_name
            )

            if existing:
                # Update existing offer
                await conn.execute("""
                    UPDATE epazar_offers SET
                        total_bid_mkd = COALESCE($3, total_bid_mkd),
                        is_winner = $4,
                        ranking = CASE WHEN $4 THEN 1 ELSE ranking END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE tender_id = $1 AND supplier_name = $2
                """, tender_id, supplier_name, bid_amount, is_winner)
            else:
                # Insert new offer
                await conn.execute("""
                    INSERT INTO epazar_offers (
                        tender_id, supplier_name, supplier_address, supplier_city,
                        total_bid_mkd, is_winner, ranking
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                    tender_id,
                    supplier_name,
                    supplier_address,
                    supplier_city,
                    bid_amount,
                    is_winner,
                    1 if is_winner else None
                )
                logger.info(f"✓ Inserted offer for tender {tender_id} from {supplier_name[:50]}...")

        except Exception as e:
            logger.error(f"Error inserting offer for {tender_id}: {e}")


# ============================================================================
# COMPANYWALL PIPELINES
# ============================================================================

class CompanyWallValidationPipeline:
    """Validate CompanyWall company data before database insertion."""

    def process_item(self, item, spider):
        if not isinstance(item, CompanyWallItem):
            return item

        adapter = ItemAdapter(item)

        # Must have a name
        name = adapter.get('name')
        if not name or len(name.strip()) < 2:
            raise DropItem(f"Missing company name: {adapter.get('source_url')}")

        # Must have at least one identifier
        if not any([adapter.get('embs'), adapter.get('edb'), adapter.get('companywall_id')]):
            raise DropItem(f"No identifier for company: {name}")

        # Validate EMBS format (5-8 digits)
        embs = adapter.get('embs')
        if embs and not re.match(r'^\d{5,8}$', str(embs)):
            logger.warning(f"Invalid EMBS format: {embs} for {name}")
            adapter['embs'] = None

        # Validate EDB format (10-15 digits)
        edb = adapter.get('edb')
        if edb and not re.match(r'^\d{10,15}$', str(edb)):
            logger.warning(f"Invalid EDB format: {edb} for {name}")
            adapter['edb'] = None

        return item


class CompanyWallDatabasePipeline:
    """
    Insert/update CompanyWall companies into mk_companies table.

    Matching hierarchy:
    1. companywall_id (exact)
    2. EMBS (exact)
    3. EDB (exact)
    4. Normalized name + city (fuzzy)
    """

    def __init__(self):
        self.pool = None
        self._pool_creating = False
        self.stats = {'new': 0, 'updated': 0, 'errors': 0}

    def open_spider(self, spider):
        logger.info("CompanyWallDatabasePipeline: Ready")

    async def _ensure_pool(self):
        if self.pool is not None:
            return True

        # Simple flag to prevent concurrent pool creation
        if self._pool_creating:
            # Wait for the other coroutine to finish creating the pool
            import asyncio
            for _ in range(50):  # Wait up to 5 seconds
                await asyncio.sleep(0.1)
                if self.pool is not None:
                    return True
            return False

        self._pool_creating = True

        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL not set!")
            self._pool_creating = False
            return False

        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

        try:
            self.pool = await asyncpg.create_pool(
                database_url, min_size=1, max_size=3, command_timeout=60
            )
            logger.info("CompanyWallDatabasePipeline: Connection pool created")
            return True
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            self._pool_creating = False
            return False

    async def _close_spider_async(self, spider):
        if self.pool:
            await self.pool.close()
            logger.info(f"CompanyWallDatabasePipeline closed. Stats: {self.stats}")

    def close_spider(self, spider):
        return deferred_from_coro(self._close_spider_async(spider))

    async def process_item(self, item, spider):
        if not isinstance(item, CompanyWallItem):
            return item

        if not await self._ensure_pool():
            return item

        adapter = ItemAdapter(item)

        try:
            async with self.pool.acquire() as conn:
                company_id = await self._find_existing(adapter, conn)

                if company_id:
                    await self._update_company(conn, company_id, adapter)
                    self.stats['updated'] += 1
                else:
                    await self._insert_company(conn, adapter)
                    self.stats['new'] += 1

                if (self.stats['new'] + self.stats['updated']) % 500 == 0:
                    logger.info(
                        f"CompanyWall DB stats: "
                        f"{self.stats['new']} new, "
                        f"{self.stats['updated']} updated, "
                        f"{self.stats['errors']} errors"
                    )

        except Exception as e:
            logger.error(f"DB error for {adapter.get('name', '?')}: {e}")
            self.stats['errors'] += 1

        return item

    async def _find_existing(self, adapter, conn):
        """Three-level match to find existing company."""
        # 1. Match by CompanyWall ID
        cw_id = adapter.get('companywall_id')
        if cw_id:
            result = await conn.fetchval(
                "SELECT company_id FROM mk_companies WHERE companywall_id = $1", cw_id
            )
            if result:
                return result

        # 2. Match by EMBS
        embs = adapter.get('embs')
        if embs:
            result = await conn.fetchval(
                "SELECT company_id FROM mk_companies WHERE embs = $1", embs
            )
            if result:
                return result

        # 3. Match by EDB
        edb = adapter.get('edb')
        if edb:
            result = await conn.fetchval(
                "SELECT company_id FROM mk_companies WHERE edb = $1", edb
            )
            if result:
                return result

        # 4. Match by normalized name + city
        name = adapter.get('name')
        city = adapter.get('city')
        if name and city:
            result = await conn.fetchval(
                """SELECT company_id FROM mk_companies
                   WHERE UPPER(TRIM(name)) = UPPER(TRIM($1))
                     AND UPPER(TRIM(city_mk)) = UPPER(TRIM($2))""",
                name, city
            )
            if result:
                return result

        return None

    async def _update_company(self, conn, company_id, adapter):
        """Update existing company. COALESCE preserves existing data."""
        await conn.execute("""
            UPDATE mk_companies SET
                embs = COALESCE($2, embs),
                edb = COALESCE($3, edb),
                companywall_id = COALESCE($4, companywall_id),
                status = COALESCE($5, status),
                legal_form = COALESCE($6, legal_form),
                founding_date = COALESCE($7, founding_date),
                address = COALESCE($8, address),
                city_mk = COALESCE($9, city_mk),
                municipality = COALESCE($10, municipality),
                postal_code = COALESCE($11, postal_code),
                region = COALESCE($12, region),
                phone = COALESCE($13, phone),
                email = COALESCE($14, email),
                website = COALESCE($15, website),
                nace_code = COALESCE($16, nace_code),
                nace_description = COALESCE($17, nace_description),
                owners = COALESCE($18::jsonb, owners),
                directors = COALESCE($19::jsonb, directors),
                revenue = COALESCE($20, revenue),
                profit = COALESCE($21, profit),
                num_employees = COALESCE($22, num_employees),
                financial_year = COALESCE($23, financial_year),
                avg_salary = COALESCE($24, avg_salary),
                tax_debtor = COALESCE($25, tax_debtor),
                court_proceedings = COALESCE($26, court_proceedings),
                bank_blocked = COALESCE($27, bank_blocked),
                credit_rating = COALESCE($28, credit_rating),
                source_url = $29,
                companywall_scraped_at = NOW(),
                raw_data_json = COALESCE($30::jsonb, raw_data_json),
                updated_at = NOW()
            WHERE company_id = $1
        """,
            company_id,
            adapter.get('embs'),
            adapter.get('edb'),
            adapter.get('companywall_id'),
            adapter.get('status'),
            adapter.get('legal_form'),
            self._parse_date(adapter.get('founding_date')),
            adapter.get('address'),
            adapter.get('city'),
            adapter.get('municipality'),
            adapter.get('postal_code'),
            adapter.get('region'),
            adapter.get('phone'),
            adapter.get('email'),
            adapter.get('website'),
            adapter.get('nace_code'),
            adapter.get('nace_description'),
            adapter.get('owners'),
            adapter.get('directors'),
            self._to_float(adapter.get('revenue')),
            self._to_float(adapter.get('profit')),
            self._to_int(adapter.get('num_employees')),
            self._to_int(adapter.get('financial_year')),
            self._to_float(adapter.get('avg_salary')),
            adapter.get('tax_debtor'),
            adapter.get('court_proceedings'),
            adapter.get('bank_blocked'),
            adapter.get('credit_rating'),
            adapter.get('source_url'),
            adapter.get('raw_data_json'),
        )

    async def _insert_company(self, conn, adapter):
        """Insert new company record."""
        await conn.execute("""
            INSERT INTO mk_companies (
                name, embs, edb, companywall_id, status, legal_form,
                founding_date, address, city_mk, municipality,
                postal_code, region, phone, email, website,
                nace_code, nace_description, owners, directors,
                revenue, profit, num_employees, financial_year, avg_salary,
                tax_debtor, court_proceedings, bank_blocked, credit_rating,
                source_url, companywall_scraped_at, email_source,
                raw_data_json, category_mk
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17, $18::jsonb, $19::jsonb,
                $20, $21, $22, $23, $24,
                $25, $26, $27, $28,
                $29, NOW(), 'companywall',
                $30::jsonb, $31
            )
        """,
            adapter.get('name'),
            adapter.get('embs'),
            adapter.get('edb'),
            adapter.get('companywall_id'),
            adapter.get('status'),
            adapter.get('legal_form'),
            self._parse_date(adapter.get('founding_date')),
            adapter.get('address'),
            adapter.get('city'),
            adapter.get('municipality'),
            adapter.get('postal_code'),
            adapter.get('region'),
            adapter.get('phone'),
            adapter.get('email'),
            adapter.get('website'),
            adapter.get('nace_code'),
            adapter.get('nace_description'),
            adapter.get('owners'),
            adapter.get('directors'),
            self._to_float(adapter.get('revenue')),
            self._to_float(adapter.get('profit')),
            self._to_int(adapter.get('num_employees')),
            self._to_int(adapter.get('financial_year')),
            self._to_float(adapter.get('avg_salary')),
            adapter.get('tax_debtor'),
            adapter.get('court_proceedings'),
            adapter.get('bank_blocked'),
            adapter.get('credit_rating'),
            adapter.get('source_url'),
            adapter.get('raw_data_json'),
            adapter.get('nace_description'),  # category_mk = NACE description
        )

    def _parse_date(self, date_str):
        """Convert YYYY-MM-DD string to date object."""
        if not date_str:
            return None
        try:
            from datetime import date as date_type
            parts = date_str.split('-')
            if len(parts) == 3:
                return date_type(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            pass
        return None

    def _to_float(self, val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _to_int(self, val):
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
