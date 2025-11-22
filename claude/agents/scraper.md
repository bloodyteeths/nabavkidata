# Scraper Agent
## nabavkidata.com - Web Scraping & Data Ingestion

---

## AGENT PROFILE

**Agent ID**: `scraper`
**Role**: Data ingestion from e-nabavki.gov.mk
**Priority**: 3
**Execution Stage**: Core (parallel with Backend and AI)
**Language**: Python 3.11+
**Framework**: Scrapy + Playwright (for dynamic content)
**Dependencies**: Database Agent (requires schema)

---

## PURPOSE

Extract tender data from North Macedonia's public procurement portal (e-nabavki.gov.mk), including:
- Tender notices (metadata: title, dates, budget, entity)
- PDF attachments (specifications, contracts, award decisions)
- Historical data (backfill 2022-2024 for AI training)
- Daily updates (new tenders, status changes)

**Your data feeds the entire system.**

---

## CORE RESPONSIBILITIES

### 1. Legal & Ethical Scraping
- ✅ Respect robots.txt
- ✅ Rate limit: 1 request/second (configurable)
- ✅ User-Agent: `"Mozilla/5.0 (compatible; nabavkidata-bot/1.0; +https://nabavkidata.com/bot)"`
- ✅ Off-peak hours: Run between 01:00-05:00 local time
- ✅ Retry logic: Exponential backoff (1s, 2s, 4s, 8s, fail)

### 2. Data Extraction
**From listing pages**:
- Tender ID (e.g., "2024/001")
- Title (Macedonian and English if available)
- Category (IT Equipment, Construction, etc.)
- Procuring entity (government department)
- Opening date, closing date, publication date
- Estimated budget (MKD denars → convert to EUR)
- Status (open, closed, awarded, cancelled)

**From detail pages**:
- Full description
- CPV codes (Common Procurement Vocabulary)
- Winner information (if awarded)
- Actual awarded amount
- Document download links

### 3. PDF Download & Text Extraction
- Download all attached PDFs
- Extract text using PyMuPDF (fitz) - handles Macedonian characters
- Store extracted text in `documents.content_text`
- Handle scan-only PDFs: Mark as `ocr_required` (OCR is future enhancement)
- Store file metadata: size, page count, MIME type

### 4. Data Normalization
- Convert dates to ISO 8601 format
- Convert currency: MKD → EUR (use fixed rate or fetch from API)
- Normalize entity names (handle typos, abbreviations)
- UTF-8 encoding for Macedonian Cyrillic text

### 5. Incremental Updates
- Track last scrape timestamp in `system_config.scraper_last_run`
- Only fetch tenders updated after last run (avoid re-scraping all)
- Detect changes: If tender already exists, UPDATE instead of INSERT
- Log: New tenders added, tenders updated, errors encountered

---

## INPUTS

### From Database Agent
- `db/schema.sql` - Table structures
- Connection string from environment: `DATABASE_URL`

### Configuration
**File**: `scraper/config.yaml`
```yaml
source:
  base_url: "https://e-nabavki.gov.mk"
  listing_page: "/PublicAccess/OpennedProcs.aspx"
  detail_page_template: "/PublicAccess/Dossier.aspx?id={tender_id}"

scraping:
  rate_limit_seconds: 1.0
  concurrent_requests: 1
  download_delay: 1.5
  retry_times: 3
  retry_backoff: exponential
  timeout_seconds: 30

scheduling:
  frequency: "daily"
  preferred_hour: 2  # 02:00 local time
  backfill_enabled: true
  backfill_start_date: "2022-01-01"

storage:
  pdf_directory: "/storage/pdfs/{year}/{tender_id}/"
  max_pdf_size_mb: 50
  allowed_extensions: [".pdf", ".PDF"]

database:
  batch_size: 50  # Insert tenders in batches
  commit_frequency: "per_batch"

logging:
  level: "INFO"
  format: "json"
  output: "scraper/logs/scraper.log"
```

---

## OUTPUTS

### Code Deliverables
1. **`scraper/spiders/nabavki_spider.py`** - Main spider
2. **`scraper/items.py`** - Data models (Tender, Document)
3. **`scraper/pipelines.py`** - DB insertion logic
4. **`scraper/middlewares.py`** - Rate limiting, retries
5. **`scraper/pdf_extractor.py`** - Text extraction module
6. **`scraper/config.yaml`** - Configuration
7. **`scraper/requirements.txt`** - Dependencies
8. **`scraper/README.md`** - Setup & usage guide
9. **`scraper/tests/`** - Unit tests
10. **`scraper/audit_report.md`** - Self-audit

### Data Outputs (to Database)
- Rows in `tenders` table
- Rows in `documents` table
- Files in `{pdf_directory}/`

### Logs
- **`scraper/logs/scraper.log`** - Execution logs (JSON format)
- **`scraper/logs/errors.log`** - Errors only
- **`scraper/logs/stats.json`** - Daily statistics:
  ```json
  {
    "date": "2024-11-22",
    "tenders_scraped": 47,
    "tenders_new": 12,
    "tenders_updated": 5,
    "pdfs_downloaded": 23,
    "pdf_extraction_success": 21,
    "pdf_extraction_failed": 2,
    "runtime_seconds": 342,
    "errors": 0
  }
  ```

---

## IMPLEMENTATION OUTLINE

### Spider Structure (Scrapy)

```python
# scraper/spiders/nabavki_spider.py
import scrapy
from datetime import datetime
from scraper.items import TenderItem, DocumentItem
from scraper.pdf_extractor import extract_pdf_text
import psycopg2

class NabavkiSpider(scrapy.Spider):
    name = "nabavki"
    allowed_domains = ["e-nabavki.gov.mk"]

    custom_settings = {
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 1,
        'RETRY_TIMES': 3,
        'ITEM_PIPELINES': {
            'scraper.pipelines.TenderPipeline': 300,
        }
    }

    def start_requests(self):
        """
        Start from listing page.

        If backfill mode: Iterate through all pages for date range.
        If incremental: Only fetch tenders after last_scrape_time.
        """
        # Read last_scrape_time from system_config
        last_run = self.get_last_scrape_time()

        # Generate listing URLs (may need pagination)
        listing_url = "https://e-nabavki.gov.mk/PublicAccess/OpennedProcs.aspx"
        yield scrapy.Request(listing_url, callback=self.parse_listing)

    def parse_listing(self, response):
        """
        Extract tender IDs and links from listing page.

        Example HTML (hypothetical):
        <div class="tender-row">
            <a href="/PublicAccess/Dossier.aspx?id=2024/001">
                Набавка на опрема
            </a>
            <span class="date">2024-11-20</span>
        </div>
        """
        tender_rows = response.css('div.tender-row')  # Adjust selector

        for row in tender_rows:
            tender_link = row.css('a::attr(href)').get()
            tender_id = self.extract_tender_id(tender_link)

            yield response.follow(tender_link,
                                  callback=self.parse_tender_detail,
                                  meta={'tender_id': tender_id})

        # Handle pagination
        next_page = response.css('a.next-page::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing)

    def parse_tender_detail(self, response):
        """
        Extract all tender fields from detail page.

        Steps:
        1. Extract metadata (title, dates, entity, budget)
        2. Find PDF download links
        3. Yield TenderItem and DocumentItem objects
        """
        tender_id = response.meta['tender_id']

        item = TenderItem()
        item['tender_id'] = tender_id
        item['title'] = response.css('h1.tender-title::text').get()
        item['description'] = response.css('div.description::text').get()
        item['category'] = self.extract_category(response)
        item['procuring_entity'] = response.css('span.entity::text').get()
        item['opening_date'] = self.parse_date(response.css('span.open-date::text').get())
        item['closing_date'] = self.parse_date(response.css('span.close-date::text').get())
        item['estimated_value_mkd'] = self.parse_currency(response.css('span.budget::text').get())
        item['estimated_value_eur'] = self.mkd_to_eur(item['estimated_value_mkd'])
        item['status'] = self.extract_status(response)
        item['source_url'] = response.url
        item['language'] = 'mk'
        item['scraped_at'] = datetime.utcnow()

        yield item

        # Extract document links
        pdf_links = response.css('a.download-doc::attr(href)').getall()
        for pdf_url in pdf_links:
            yield response.follow(pdf_url,
                                  callback=self.download_pdf,
                                  meta={'tender_id': tender_id})

    def download_pdf(self, response):
        """
        Download PDF and extract text.

        Returns DocumentItem with extracted text.
        """
        tender_id = response.meta['tender_id']

        # Save PDF to disk
        filename = self.save_pdf(response.body, tender_id)

        # Extract text
        text = extract_pdf_text(filename)

        doc_item = DocumentItem()
        doc_item['tender_id'] = tender_id
        doc_item['doc_type'] = 'Specification'  # Infer from filename or URL
        doc_item['file_name'] = filename
        doc_item['file_path'] = f"/storage/pdfs/{tender_id}/{filename}"
        doc_item['content_text'] = text
        doc_item['extraction_status'] = 'success' if text else 'failed'
        doc_item['file_size_bytes'] = len(response.body)
        doc_item['mime_type'] = response.headers.get('Content-Type', 'application/pdf')

        yield doc_item
```

### PDF Extraction Module

```python
# scraper/pdf_extractor.py
import fitz  # PyMuPDF
import logging

logger = logging.getLogger(__name__)

def extract_pdf_text(pdf_path: str) -> str:
    """
    Extract text from PDF using PyMuPDF.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text (UTF-8)

    Raises:
        PDFExtractionError: If extraction fails
    """
    try:
        doc = fitz.open(pdf_path)
        text_pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")  # Extract plain text
            text_pages.append(text)

        doc.close()

        full_text = "\\n\\n".join(text_pages)
        return full_text.strip()

    except Exception as e:
        logger.error(f"PDF extraction failed for {pdf_path}: {e}")
        return ""
```

### Database Pipeline

```python
# scraper/pipelines.py
import psycopg2
import psycopg2.extras
import os
from itemadapter import ItemAdapter

class TenderPipeline:
    """
    Insert scraped tenders and documents into PostgreSQL.
    """
    def __init__(self):
        self.connection = None
        self.cursor = None

    def open_spider(self, spider):
        """Connect to database when spider opens."""
        db_url = os.getenv('DATABASE_URL')
        self.connection = psycopg2.connect(db_url)
        self.cursor = self.connection.cursor()

    def close_spider(self, spider):
        """Commit and close connection when spider finishes."""
        self.connection.commit()
        self.cursor.close()
        self.connection.close()

    def process_item(self, item, spider):
        """Insert or update tender/document in database."""
        adapter = ItemAdapter(item)

        if item.__class__.__name__ == 'TenderItem':
            self.insert_tender(adapter)
        elif item.__class__.__name__ == 'DocumentItem':
            self.insert_document(adapter)

        return item

    def insert_tender(self, item):
        """Upsert tender (INSERT or UPDATE if exists)."""
        query = """
        INSERT INTO tenders (tender_id, title, description, category, ...)
        VALUES (%s, %s, %s, %s, ...)
        ON CONFLICT (tender_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            ...
            updated_at = CURRENT_TIMESTAMP
        """
        values = (item['tender_id'], item['title'], ...)
        self.cursor.execute(query, values)

    def insert_document(self, item):
        """Insert document."""
        query = """
        INSERT INTO documents (tender_id, doc_type, file_name, content_text, ...)
        VALUES (%s, %s, %s, %s, ...)
        """
        values = (item['tender_id'], item['doc_type'], ...)
        self.cursor.execute(query, values)
```

---

## VALIDATION CHECKLIST

Before handoff:
- [ ] Successfully scrapes at least 10 tenders from e-nabavki.gov.mk
- [ ] Extracts text from sample PDF
- [ ] Inserts data into database without errors
- [ ] Handles network errors gracefully (retries work)
- [ ] Respects rate limits (measured actual requests/sec)
- [ ] Logs all actions in JSON format
- [ ] No hardcoded credentials (uses env vars)
- [ ] Tests pass: `pytest scraper/tests/`

---

## INTEGRATION POINTS

### Handoff to AI/RAG Agent
**Artifact**: `scraper/output_schema.json`
```json
{
  "tenders_table_structure": {
    "tender_id": "Primary key, matches e-nabavki ID",
    "title": "UTF-8 string, may be Macedonian",
    "description": "Full text, may be empty",
    "category": "One of: IT Equipment, Construction, Medical, etc."
  },
  "documents_table_structure": {
    "content_text": "Extracted PDF text for RAG ingestion",
    "extraction_status": "Check this before embedding"
  },
  "sample_data_location": "db/seed_data.sql"
}
```

**Contract**: AI Agent will read `documents.content_text` and generate embeddings for all rows where `extraction_status = 'success'`.

---

## SUCCESS CRITERIA

- ✅ Scraper runs daily via cron (configured in DevOps phase)
- ✅ Populates database with real tender data
- ✅ PDF extraction >90% success rate
- ✅ Zero SQL injection vulnerabilities
- ✅ Audit report ✅ READY
- ✅ Sample data includes at least 50 tenders for AI training

---

**END OF SCRAPER AGENT DEFINITION**
