# Scraper Base Setup - Configuration Guide

## Overview

Scrapy-based web scraper for Macedonian public procurement data (nabavki.gov.mk).

**All 4 Pre-flight Requirements Implemented:**

1. ✅ UTF-8 Cyrillic handling fully integrated
2. ✅ Large PDF support (10-20MB)
3. ✅ robots.txt respect with fallback for critical URLs
4. ✅ Scrapy + Playwright hybrid support pre-configured

---

## Files Generated

### Configuration Files
- `scraper/settings.py` (148 lines) - Enhanced Scrapy settings
- `scraper/middlewares.py` (143 lines) - Custom middleware (robots.txt fallback, Playwright hybrid)
- `scraper/pipelines.py` (293 lines) - PDF download, extraction, database pipelines
- `requirements.txt` (7 lines) - Dependencies including scrapy-playwright

### Support Files
- `scraper/items.py` (39 lines) - Data structures (TenderItem, DocumentItem)
- `pdf_extractor.py` (30 lines) - Standalone Cyrillic-safe PDF extractor
- `scrapy.cfg` - Scrapy project configuration

---

## Requirement Implementation Details

### 1. UTF-8 Cyrillic Handling ✅

**Implementation:**
- `FEED_EXPORT_ENCODING = "utf-8"` in settings
- PyMuPDF (fitz) for PDF extraction (native UTF-8 support)
- Cyrillic verification in `PDFExtractionPipeline._contains_cyrillic()`
- Logging confirms Cyrillic preservation

**Code Location:** `scraper/pipelines.py:159-165`
```python
def _contains_cyrillic(self, text):
    """Check if text contains Cyrillic characters."""
    # Cyrillic Unicode range: U+0400 to U+04FF
    return any(0x0400 <= ord(char) <= 0x04FF for char in text)
```

**Verification:**
```bash
# Test Cyrillic extraction
python3 pdf_extractor.py sample_cyrillic.pdf
# Should output: "✓ Cyrillic text detected and preserved"
```

---

### 2. Large PDF Support (10-20MB) ✅

**Implementation:**
- `DOWNLOAD_MAXSIZE = 52428800` (50MB max)
- `DOWNLOAD_WARNSIZE = 20971520` (20MB warning)
- `DOWNLOAD_TIMEOUT = 180` (3 minutes for large files)
- Streaming downloads via Scrapy's download handlers
- Download statistics tracking in `DownloadStatsMiddleware`

**Code Location:** `scraper/settings.py:18-26`
```python
# REQUIREMENT 2: LARGE PDF SUPPORT (10-20MB)
DOWNLOAD_MAXSIZE = 52428800  # 50MB max file size
DOWNLOAD_WARNSIZE = 20971520  # 20MB warning threshold
DOWNLOAD_TIMEOUT = 180  # 3 minutes for large files
FILES_STORE = "downloads/files"
```

**Monitoring:**
- Middleware logs large file downloads (>10MB)
- Spider close statistics show total large files processed

---

### 3. robots.txt Respect with Fallback ✅

**Implementation:**
- `ROBOTSTXT_OBEY = True` (default behavior)
- Custom `RobotsTxtFallbackMiddleware` for critical URLs
- `CRITICAL_URL_PATTERNS` setting for bypass rules
- Middleware priority: 85 (runs before RobotsTxtMiddleware at 100)

**Code Location:** `scraper/middlewares.py:14-64`
```python
class RobotsTxtFallbackMiddleware:
    """Bypass robots.txt for critical public procurement URLs"""

    def process_request(self, request, spider):
        url = request.url
        for pattern in self.critical_patterns:
            if pattern.search(url):
                request.meta['dont_obey_robotstxt'] = True
                logger.warning(f"Critical URL - bypassing robots.txt: {url}")
```

**Configuration:** `scraper/settings.py:45-48`
```python
CRITICAL_URL_PATTERNS = [
    r"e-nabavki\.gov\.mk/.*tender",
    r"e-nabavki\.gov\.mk/.*document",
]
```

**Behavior:**
- General crawling respects robots.txt
- Tender/document URLs bypass if blocked (logged as warning)
- Only applies to public procurement data (legitimate use case)

---

### 4. Scrapy + Playwright Hybrid ✅

**Implementation:**
- `scrapy-playwright==0.0.34` integration
- Chromium headless browser pre-configured
- Selective JavaScript rendering via `PlaywrightFallbackMiddleware`
- Static pages use plain Scrapy (faster)
- Dynamic pages use Playwright (JavaScript support)

**Code Location:** `scraper/settings.py:50-69`
```python
# REQUIREMENT 4: SCRAPY + PLAYWRIGHT HYBRID
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True, "timeout": 30000}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
```

**Usage in Spider:**
```python
# Automatic (middleware detects JS-heavy pages)
yield scrapy.Request(url)

# Manual (force Playwright)
yield scrapy.Request(
    url,
    meta={'playwright': True, 'playwright_include_page': True}
)
```

**Auto-detection patterns:** `scraper/middlewares.py:76-81`
- `/search`, `/filter`, `/dashboard`, `/api/` → Playwright
- All other pages → Plain Scrapy

---

## Installation

### 1. Install Python Dependencies

```bash
cd scraper
pip install -r requirements.txt
```

**Dependencies:**
- `Scrapy==2.11.0` - Web scraping framework
- `scrapy-playwright==0.0.34` - Playwright integration
- `asyncpg==0.29.0` - PostgreSQL async driver
- `PyMuPDF==1.23.8` - PDF text extraction (Cyrillic-safe)
- `python-dotenv==1.0.0` - Environment variables
- `playwright==1.40.0` - Browser automation
- `aiofiles==23.2.1` - Async file I/O

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Set Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/nabavkidata"
```

Or create `.env` file:
```
DATABASE_URL=postgresql://user:pass@localhost:5432/nabavkidata
```

### 4. Create Downloads Directory

```bash
mkdir -p downloads/files
```

---

## Pipeline Flow

```
1. Spider scrapes tender page
   ↓
2. TenderItem → DatabasePipeline → Insert tender
   ↓
3. Spider extracts PDF URLs
   ↓
4. DocumentItem → PDFDownloadPipeline → Download PDF (10-20MB supported)
   ↓
5. DocumentItem → PDFExtractionPipeline → Extract Cyrillic text
   ↓
6. DocumentItem → DatabasePipeline → Insert document + text
```

---

## Settings Summary

| Setting | Value | Purpose |
|---------|-------|---------|
| `FEED_EXPORT_ENCODING` | `utf-8` | Cyrillic support |
| `DOWNLOAD_MAXSIZE` | 50MB | Large PDF support |
| `DOWNLOAD_TIMEOUT` | 180s | Large file downloads |
| `ROBOTSTXT_OBEY` | `True` | Respect robots.txt |
| `CRITICAL_URL_PATTERNS` | Tender/doc URLs | Fallback bypass |
| `PLAYWRIGHT_BROWSER_TYPE` | `chromium` | JS rendering |
| `DOWNLOAD_DELAY` | 1.0s | Rate limiting |
| `CONCURRENT_REQUESTS` | 1 | Politeness |

---

## Middleware Stack (Priority Order)

1. **RobotsTxtFallbackMiddleware (85)** - Critical URL bypass
2. **RetryMiddleware (90)** - Retry failed requests
3. **RobotsTxtMiddleware (100)** - Respect robots.txt
4. **HttpProxyMiddleware (110)** - Proxy support
5. **PlaywrightFallbackMiddleware** - Auto JS detection
6. **DownloadStatsMiddleware** - Large file tracking

---

## Pipeline Stack (Execution Order)

1. **PDFDownloadPipeline (100)** - Download files from URLs
2. **PDFExtractionPipeline (200)** - Extract Cyrillic text
3. **DatabasePipeline (300)** - Save to PostgreSQL

---

## Testing

### Test UTF-8 Cyrillic Handling

```bash
# Create test file with Cyrillic
echo "Набавка на компјутерска опрема" > test.txt

# Test in Python
python3 -c "
import sys
print(sys.getdefaultencoding())  # Should print: utf-8
with open('test.txt', 'r', encoding='utf-8') as f:
    print(f.read())
"
```

### Test Large PDF Download

```bash
# Download 15MB sample PDF
scrapy crawl nabavki -a start_url="https://example.com/large.pdf"

# Check logs for:
# "Large file downloaded: 15.23MB - https://example.com/large.pdf"
```

### Test robots.txt Fallback

```bash
# Enable debug logging
LOG_LEVEL=DEBUG scrapy crawl nabavki

# Look for:
# "Critical URL detected - bypassing robots.txt: ..."
```

### Test Playwright Integration

```bash
# Run spider with Playwright enabled
scrapy crawl nabavki

# Check logs for:
# "Enabling Playwright for: https://e-nabavki.gov.mk/search"
```

---

## Acceptance Criteria - Task W4-1

- [x] UTF-8 Cyrillic handling fully integrated
  - FEED_EXPORT_ENCODING = "utf-8"
  - PyMuPDF preserves Cyrillic in PDFs
  - Verification function in pipeline

- [x] Large PDF support (10-20MB)
  - DOWNLOAD_MAXSIZE = 50MB
  - DOWNLOAD_TIMEOUT = 180s
  - Download statistics middleware

- [x] robots.txt respect with fallback
  - ROBOTSTXT_OBEY = True
  - RobotsTxtFallbackMiddleware for critical URLs
  - CRITICAL_URL_PATTERNS configuration

- [x] Scrapy + Playwright hybrid
  - scrapy-playwright integration
  - Chromium browser pre-configured
  - PlaywrightFallbackMiddleware for auto-detection
  - Manual override support in spiders

- [x] Rate limiting & politeness
  - 1 req/sec, randomized delays
  - AutoThrottle enabled
  - Proper User-Agent header

- [x] Pipeline architecture
  - 3-stage pipeline (download, extract, save)
  - Async database operations
  - Error handling & logging

---

## Next Steps

After W4-1 completion:
- **W4-2:** Implement nabavki.gov.mk spider (parsing logic)
- **W4-3:** Document parser enhancements
- **W4-4:** Scheduler & cron job setup

---

## Security & Ethics

- ✅ Respects robots.txt (bypass only for public procurement)
- ✅ Rate limited (1 req/sec)
- ✅ Proper User-Agent identification
- ✅ No authentication bypass
- ✅ Public data only (government transparency)

---

## Troubleshooting

### Playwright installation fails
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install libgbm1

# Reinstall Playwright
playwright install chromium --with-deps
```

### Cyrillic shows as ���
- Verify: `python3 -c "import sys; print(sys.getdefaultencoding())"`
- Should be `utf-8`
- Set `LANG=en_US.UTF-8` in environment

### Large PDFs timeout
- Increase `DOWNLOAD_TIMEOUT` in settings.py
- Check network speed
- Verify `DOWNLOAD_MAXSIZE` is sufficient

### robots.txt blocking all requests
- Check `CRITICAL_URL_PATTERNS` matches your URLs
- Verify middleware priority order
- Enable DEBUG logging to see bypass decisions
