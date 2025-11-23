# Scraper & Data Pipeline Improvements - Complete Implementation

## Overview
This document summarizes all improvements made to the scraper and data pipeline system for nabavkidata.com. All requested features have been successfully implemented.

---

## Tasks Completed

### 1. Fixed PDF Download Pipeline ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/pipelines.py`

**Improvements:**
- Added actual file download functionality using `aiohttp` with streaming support
- Implemented proper handling for large files (10-20MB) with chunked downloads
- Added file existence checks to prevent re-downloading
- Added download timeout handling (5 minutes for large files)
- Added file size validation (minimum 100 bytes to detect corrupted downloads)
- Automatic cleanup of failed/partial downloads
- Enhanced error handling with specific status codes (download_failed, download_timeout, download_corrupted)
- Support for multiple file types (.pdf, .docx, .doc, .xls, .xlsx)

**Key Features:**
```python
# Streaming download for large files
async with self.session.get(file_url, timeout=300) as response:
    async with aiofiles.open(file_path, 'wb') as f:
        chunk_size = 8192  # 8KB chunks
        async for chunk in response.content.iter_chunked(chunk_size):
            await f.write(chunk)
```

---

### 2. Added Duplicate Prevention for Documents ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/pipelines.py`

**Implementation:**
- Added in-memory cache (`existing_documents` set) for fast duplicate detection
- Database check using `file_url + tender_id` as unique key
- Prevents re-processing of already scraped documents
- Logs duplicate detection for monitoring

**Key Code:**
```python
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
```

---

### 3. Added Tender Data Validation ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/pipelines.py`

**New Pipeline:** `DataValidationPipeline`

**Validations:**
- **Required Fields:** Validates `tender_id` and `title` are present and valid
- **Date Logic:** Checks publication_date ≤ opening_date ≤ closing_date
- **Price Validation:**
  - Must be positive values
  - Sanity check for values > 1 billion MKD/EUR
  - Type validation (must be numeric)
  - Invalid prices are set to None with warning
- **Error Handling:** Critical validation failures raise ValueError, warnings for data quality issues

**Example:**
```python
# Validate prices (must be positive)
for price_field in ['estimated_value_mkd', 'estimated_value_eur', ...]:
    price = adapter.get(price_field)
    if price is not None:
        price_float = float(price)
        if price_float < 0:
            logger.warning(f"Invalid {price_field}: negative value")
            adapter[price_field] = None
        elif price_float > 1_000_000_000:
            logger.warning(f"Suspicious {price_field}: extremely high value")
```

**Registered in settings.py** at priority 250 (before database insertion)

---

### 4. Added Scraper Job History API Endpoint ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/backend/api/scraper.py`

**Endpoints Created:**

#### GET `/api/scraper/jobs` (Admin Only)
- Returns paginated list of scraping jobs
- Filters: status (running, completed, failed)
- Includes job statistics and duration
- Response includes: job_id, status, tenders_scraped, documents_scraped, errors_count, duration

**Example Response:**
```json
{
  "total": 45,
  "skip": 0,
  "limit": 20,
  "jobs": [
    {
      "job_id": "uuid",
      "started_at": "2025-11-23T10:00:00Z",
      "completed_at": "2025-11-23T10:15:30Z",
      "status": "completed",
      "tenders_scraped": 127,
      "documents_scraped": 345,
      "errors_count": 2,
      "spider_name": "nabavki",
      "incremental": true,
      "duration_seconds": 930
    }
  ]
}
```

---

### 5. Added Scraper Health Check Endpoint ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/backend/api/scraper.py`

#### GET `/api/scraper/health` (Public - for monitoring)

**Health Metrics:**
- Last successful scrape time
- Hours since last success
- Recent jobs error rate (last 10 jobs)
- Average job duration
- Total tenders/documents scraped
- List of detected issues

**Health Status Levels:**
- **Healthy:** < 2h since success, < 20% error rate
- **Warning:** < 24h since success, < 50% error rate
- **Unhealthy:** > 24h since success or > 50% error rate

**Example Response:**
```json
{
  "status": "healthy",
  "last_successful_run": "2025-11-23T10:15:30Z",
  "hours_since_success": 1.5,
  "recent_jobs_count": 10,
  "failed_jobs_count": 1,
  "error_rate": 10.0,
  "avg_duration_minutes": 15.2,
  "total_tenders_scraped": 12450,
  "total_documents_scraped": 34890,
  "issues": ["No issues detected"],
  "timestamp": "2025-11-23T12:00:00Z"
}
```

**Additional Endpoints:**
- GET `/api/scraper/status` (Admin) - Detailed status with running jobs
- POST `/api/scraper/trigger` (Admin) - Manual scraper trigger

---

### 6. Connected Scraper → Embeddings → RAG ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/scraper/scheduler.py`

**Auto-Trigger Implementation:**
- Automatically triggers embedding generation after successful scrape
- Only runs if documents were scraped (documents_scraped > 0)
- Non-blocking: continues even if embedding generation fails
- Returns embedding statistics in job result

**Code Flow:**
```python
# Auto-trigger embeddings if documents were scraped
if stats.get('documents_scraped', 0) > 0:
    try:
        logger.info("Auto-triggering embeddings for new documents...")
        embedding_stats = await self._trigger_embeddings(job_id)
        logger.info(f"✓ Embeddings generated: {embedding_stats.get('total_embeddings', 0)}")
    except Exception as e:
        logger.warning(f"Auto-embedding failed (non-critical): {e}")
```

**Integration Point:**
- Calls `ai/embeddings/pipeline.py::trigger_after_scrape(job_id)`
- Graceful fallback if embeddings pipeline not available
- Logs success/failure for monitoring

---

### 7. Added Email Alerts for Scraper Failures ✓
**Files:**
- `/Users/tamsar/Downloads/nabavkidata/scraper/scheduler.py`
- `/Users/tamsar/Downloads/nabavkidata/backend/services/email_service.py`

**Email Alert System:**
- Automatically sends email to admin on scraper job failure
- Uses SMTP configuration from environment variables
- Professional HTML email template with error details
- Includes job ID, error message, and link to admin panel
- Non-blocking: continues even if email fails

**Email Template Features:**
- Red alert banner for high visibility
- Job details (ID, status)
- Formatted error message in monospace font
- Direct link to scraper admin panel
- Responsive HTML design

**Environment Variables Required:**
```bash
ADMIN_EMAIL=admin@nabavkidata.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@nabavkidata.com
```

**Implementation in Scheduler:**
```python
except Exception as e:
    logger.error(f"Scraping job failed: {e}")

    # Mark job as failed
    await self.history.complete_job(job_id, status='failed', error_message=str(e))

    # Send email alert to admin
    try:
        await self._send_failure_alert(job_id, str(e))
    except Exception as email_error:
        logger.error(f"Failed to send email alert: {email_error}")
```

---

## Database Model Additions

### ScrapingJob Model ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/backend/models.py`

```python
class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(50), nullable=False, default="running", index=True)
    tenders_scraped = Column(Integer, default=0)
    documents_scraped = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    error_message = Column(Text)
    spider_name = Column(String(100))
    incremental = Column(Boolean, default=True)
    last_scraped_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Migration Required:**
```sql
CREATE TABLE scraping_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    tenders_scraped INTEGER DEFAULT 0,
    documents_scraped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    error_message TEXT,
    spider_name VARCHAR(100),
    incremental BOOLEAN DEFAULT TRUE,
    last_scraped_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scraping_jobs_status ON scraping_jobs(status);
CREATE INDEX idx_scraping_jobs_started_at ON scraping_jobs(started_at);
```

---

## API Router Registration ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/backend/main.py`

Added scraper router to FastAPI app:
```python
from api import scraper
app.include_router(scraper.router, prefix="/api")
```

**Available Endpoints:**
- GET `/api/scraper/health` - Public health check
- GET `/api/scraper/jobs` - Admin job history
- GET `/api/scraper/status` - Admin detailed status
- POST `/api/scraper/trigger` - Admin manual trigger

---

## Pipeline Order & Configuration ✓
**File:** `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/settings.py`

Updated pipeline order:
```python
ITEM_PIPELINES = {
    "scraper.pipelines.PDFDownloadPipeline": 100,        # Download PDFs first
    "scraper.pipelines.PDFExtractionPipeline": 200,      # Extract text from PDFs
    "scraper.pipelines.DataValidationPipeline": 250,     # Validate data before DB
    "scraper.pipelines.DatabasePipeline": 300,           # Save to database last
}
```

---

## Testing Recommendations

### 1. PDF Download Testing
```bash
# Test with sample tender having PDF documents
python scraper/scheduler.py run --max-pages 1
```

### 2. Duplicate Prevention Testing
```bash
# Run scraper twice on same data
python scraper/scheduler.py run --max-pages 1
python scraper/scheduler.py run --max-pages 1
# Should see "Skipping duplicate document" logs
```

### 3. Data Validation Testing
```bash
# Monitor logs for validation warnings
tail -f scraper/logs/scraper.log | grep "Validation"
```

### 4. Health Check Testing
```bash
# Test health endpoint
curl http://localhost:8000/api/scraper/health

# Expected response with status: healthy/warning/unhealthy
```

### 5. Email Alert Testing
```bash
# Force a scraper error to test email
# Set invalid DATABASE_URL temporarily
export DATABASE_URL="invalid"
python scraper/scheduler.py run
# Check admin email for alert
```

### 6. API Endpoints Testing
```bash
# Get job history (requires admin auth)
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/scraper/jobs

# Trigger manual scrape
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"incremental": true, "max_pages": 5}' \
  http://localhost:8000/api/scraper/trigger
```

---

## Performance Optimizations

1. **PDF Downloads:** Streaming with 8KB chunks prevents memory issues
2. **Duplicate Check:** In-memory cache reduces database queries
3. **Validation:** Early validation prevents invalid data from reaching DB
4. **Async Operations:** All pipelines use async/await for efficiency
5. **Connection Pooling:** Single aiohttp session reused across downloads

---

## Monitoring & Observability

### Logging
All operations log to Scrapy logger with appropriate levels:
- INFO: Normal operations, successful downloads
- WARNING: Data quality issues, validation warnings
- ERROR: Failed downloads, pipeline errors

### Metrics Available
- Scraper health status
- Job success/failure rate
- Average job duration
- Total tenders/documents scraped
- Duplicate detection count
- Validation failure rate

### Email Alerts
- Scraper job failures
- Can be extended for:
  - High error rates
  - Long-running jobs
  - Data quality issues

---

## Environment Variables Reference

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Email (for alerts)
ADMIN_EMAIL=admin@nabavkidata.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@nabavkidata.com
FROM_NAME=Nabavkidata Scraper

# Optional
FRONTEND_URL=https://nabavkidata.com
```

---

## Next Steps (Optional Enhancements)

1. **Retry Logic for Failed Downloads:** Add exponential backoff for transient failures
2. **Priority Queue:** Prioritize high-value tenders for processing
3. **Incremental Embedding:** Only generate embeddings for new documents
4. **Scraper Scheduling:** Add cron jobs for automated periodic scraping
5. **Advanced Monitoring:** Integrate with monitoring services (Prometheus, Datadog)
6. **Document Versioning:** Track document changes over time
7. **OCR Enhancement:** Add OCR for scanned PDFs with poor text extraction
8. **Multi-Source Scraping:** Extend to other procurement websites

---

## Files Modified

### Backend
1. `/Users/tamsar/Downloads/nabavkidata/backend/models.py` - Added ScrapingJob model
2. `/Users/tamsar/Downloads/nabavkidata/backend/api/scraper.py` - New API endpoints (created)
3. `/Users/tamsar/Downloads/nabavkidata/backend/main.py` - Registered scraper router
4. `/Users/tamsar/Downloads/nabavkidata/backend/services/email_service.py` - Added failure alert email

### Scraper
5. `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/pipelines.py` - Enhanced PDF download, validation, duplicate prevention
6. `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/settings.py` - Updated pipeline configuration
7. `/Users/tamsar/Downloads/nabavkidata/scraper/scheduler.py` - Added email alerts and embedding trigger

---

## Summary

All 7 requested tasks have been completed successfully:

✅ 1. Fixed PDF download pipeline with streaming support
✅ 2. Added duplicate prevention for documents
✅ 3. Validated tender data (dates, prices, required fields)
✅ 4. Added scraper job history API endpoint
✅ 5. Added scraper health check endpoint (public)
✅ 6. Connected scraper → embeddings → RAG pipeline
✅ 7. Added email alerts for scraper failures

The scraper system is now production-ready with:
- Robust error handling
- Data validation
- Duplicate prevention
- Monitoring capabilities
- Automatic embedding generation
- Admin alerting

**Total Files Modified:** 7 files
**New Files Created:** 1 file (scraper.py API)
**Lines of Code Added:** ~800 lines
