# E-Nabavki.gov.mk Scraping Strategy - Visual Flowchart

**Quick Visual Reference for Development Team**

---

## Scraping Flow Diagram

```
START: Daily Cron Job (00:00 UTC)
  │
  ├─> Load Start URL
  │   https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices
  │
  ├─> Page Detection
  │   ├─ Check if JavaScript required
  │   ├─ Detect: Angular SPA (hash routing)
  │   └─ Decision: Use Playwright ✓
  │
  ├─> Playwright Browser Launch
  │   ├─ Chromium headless
  │   ├─ Wait for network idle
  │   └─ Execute JavaScript
  │
  ├─> Extract Tender Links
  │   │
  │   ├─ Try Strategy 1: div.tender-item a
  │   ├─ Try Strategy 2: tr.tender-row a
  │   ├─ Try Strategy 3: a[href*="tender"]
  │   ├─ Try Strategy 4: table.tenders a
  │   └─ Found links? → Continue | Not found? → Try next strategy
  │
  ├─> For Each Tender Link
  │   │
  │   ├─> Navigate to Detail Page
  │   │   └─ URL: /TenderDetails.aspx?id=XXXXX
  │   │
  │   ├─> Extract Fields (Multi-Fallback)
  │   │   │
  │   │   ├─ tender_id
  │   │   │  ├─ Try URL: ?id=([^&]+)
  │   │   │  ├─ Try URL: /tender/([^/?]+)
  │   │   │  ├─ Try Page: span.tender-id::text
  │   │   │  └─ Fallback: MD5 hash of URL
  │   │   │
  │   │   ├─ title
  │   │   │  ├─ Try CSS: h1.tender-title::text
  │   │   │  ├─ Try CSS: h1::text
  │   │   │  ├─ Try XPath: //h1/text()
  │   │   │  ├─ Try Label: "Назив"
  │   │   │  └─ Try Label: "Title"
  │   │   │
  │   │   ├─ procuring_entity
  │   │   │  ├─ Try CSS: div.procuring-entity::text
  │   │   │  ├─ Try Label: "Нарачател"
  │   │   │  └─ Try Label: "Procuring Entity"
  │   │   │
  │   │   ├─ closing_date
  │   │   │  ├─ Try Label: "Затворање"
  │   │   │  ├─ Try Label: "Deadline"
  │   │   │  └─ Parse: DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD
  │   │   │
  │   │   ├─ estimated_value_mkd
  │   │   │  ├─ Try Label: "Проценета (МКД)"
  │   │   │  └─ Parse: 1.234.567,89 → 1234567.89
  │   │   │
  │   │   ├─ category
  │   │   │  └─ Detect Keywords: компјутер→IT, градеж→Construction
  │   │   │
  │   │   ├─ status
  │   │   │  └─ Detect Keywords: отворен→open, затворен→closed
  │   │   │
  │   │   └─ cpv_code, description, winner, etc.
  │   │      └─ Similar multi-fallback strategies
  │   │
  │   ├─> Extract Document Links
  │   │   │
  │   │   ├─ Find: a[href$=".pdf"]
  │   │   ├─ Find: a[href$=".doc"]
  │   │   ├─ Find: a:contains("Преземи")  # "Download" in Macedonian
  │   │   └─ Found documents? → Continue to download
  │   │
  │   ├─> Download Documents
  │   │   │
  │   │   ├─ Download PDF (supports up to 50MB)
  │   │   ├─ Timeout: 180 seconds
  │   │   ├─ Save to: downloads/files/{tender_id}_{doc_name}.pdf
  │   │   └─ Success? → Continue | Failed? → Log and continue
  │   │
  │   ├─> Extract Text from PDFs
  │   │   │
  │   │   ├─ Use PyMuPDF (fitz)
  │   │   ├─ Extract all text
  │   │   ├─ Verify Cyrillic: Check U+0400 to U+04FF range
  │   │   └─ Store extracted_text
  │   │
  │   ├─> Track Extraction Success
  │   │   │
  │   │   ├─ For each field:
  │   │   │  └─ Value found? → successful_extractions++
  │   │   │  └─ Value missing? → failed_fields++
  │   │   │
  │   │   └─ Calculate success rate per field
  │   │
  │   ├─> Save to Database
  │   │   │
  │   │   ├─ Insert into tenders table
  │   │   ├─ Insert into documents table
  │   │   ├─ Update scraped_at timestamp
  │   │   └─ Commit transaction
  │   │
  │   └─> Next Tender
  │
  ├─> Check Pagination
  │   │
  │   ├─ Try: a.next::attr(href)
  │   ├─ Try: a:contains("Следно")  # "Next" in Macedonian
  │   ├─ Try: a:contains("»")
  │   │
  │   └─ Next page found? → Go back to "Extract Tender Links"
  │
  ├─> Spider Closed
  │   │
  │   ├─ Calculate Final Statistics
  │   │  ├─ Total tenders processed: XXX
  │   │  ├─ Field success rates:
  │   │  │  ├─ tender_id: 95.2%
  │   │  │  ├─ title: 92.1%
  │   │  │  ├─ procuring_entity: 88.9%
  │   │  │  └─ ...
  │   │  │
  │   │  └─ Check for structure changes:
  │   │     └─ Critical field <80%? → ALERT! Structure change detected
  │   │
  │   ├─ Log Statistics
  │   ├─ Send Email Report
  │   └─ Close Browser
  │
  └─> END
```

---

## Multi-Fallback Extraction Strategy

```
Field Extraction Process:

START → Field Needed (e.g., "title")
  │
  ├─ Try Selector 1: CSS (h1.tender-title::text)
  │  ├─ Found? → RETURN value ✓
  │  └─ Not found? → Continue
  │
  ├─ Try Selector 2: CSS (h1::text)
  │  ├─ Found? → RETURN value ✓
  │  └─ Not found? → Continue
  │
  ├─ Try Selector 3: CSS (div.title::text)
  │  ├─ Found? → RETURN value ✓
  │  └─ Not found? → Continue
  │
  ├─ Try Selector 4: XPath (//h1/text())
  │  ├─ Found? → RETURN value ✓
  │  └─ Not found? → Continue
  │
  ├─ Try Selector 5: Label-based ("Назив")
  │  ├─ Search for: "Назив: Value"
  │  ├─ Search in: <td>Назив</td><td>Value</td>
  │  ├─ Search in: <div>Назив</div><div>Value</div>
  │  ├─ Found? → RETURN value ✓
  │  └─ Not found? → Continue
  │
  ├─ Try Selector 6: Label-based ("Title")
  │  ├─ Found? → RETURN value ✓
  │  └─ Not found? → Continue
  │
  └─ All Selectors Failed
     ├─ Log Warning: "title: All selectors failed"
     ├─ Track in failed_fields['title']++
     └─ RETURN None
```

---

## Error Handling Flow

```
Error Detection:

HTTP Error (4xx, 5xx)
  ├─ Retry count < 3?
  │  ├─ Yes → Wait 2 seconds → Retry
  │  └─ No → Log error → Continue to next tender
  │
Timeout Error
  ├─ Large PDF download timeout?
  │  ├─ Yes → Log warning → Continue (non-critical)
  │  └─ No → Check network → Retry
  │
Extraction Error (field not found)
  ├─ Critical field? (tender_id, title, entity)
  │  ├─ Yes → Try all fallback selectors
  │  │  └─ Still failed? → Log error → Continue with NULL
  │  └─ No → Log warning → Continue with NULL
  │
JavaScript Error
  ├─ Playwright page crash?
  │  ├─ Yes → Restart browser → Retry page
  │  └─ No → Log error → Continue
  │
Database Error
  ├─ Duplicate tender_id?
  │  └─ Update existing record → Continue
  ├─ Connection error?
  │  └─ Retry 3 times → Fail gracefully
  │
Structure Change Detected (success rate <80%)
  ├─ Send email alert to admin
  ├─ Log detailed extraction statistics
  └─ Continue scraping (graceful degradation)
```

---

## Data Flow Architecture

```
┌───────────────────────────────────────────────────────┐
│               E-NABAVKI.GOV.MK                         │
│  https://e-nabavki.gov.mk/PublicAccess/home.aspx      │
└─────────────────┬─────────────────────────────────────┘
                  │
                  │ Scrapy + Playwright
                  │ (1 req/sec, polite crawling)
                  ↓
┌───────────────────────────────────────────────────────┐
│             NABAVKI SPIDER                             │
│  - Multi-fallback extraction                          │
│  - Cyrillic text handling                             │
│  - PDF download & extraction                          │
│  - Success rate tracking                              │
└─────────────────┬─────────────────────────────────────┘
                  │
                  ↓
         ┌────────┴────────┐
         │                 │
         ↓                 ↓
┌─────────────────┐  ┌──────────────────┐
│  TenderItem     │  │  DocumentItem    │
│  - tender_id    │  │  - tender_id     │
│  - title        │  │  - file_url      │
│  - entity       │  │  - doc_type      │
│  - dates        │  │  - extracted_text│
│  - values       │  │                  │
│  - status       │  │                  │
└────────┬────────┘  └────────┬─────────┘
         │                    │
         └────────┬───────────┘
                  │
                  ↓
┌───────────────────────────────────────────────────────┐
│           PIPELINE PROCESSING                          │
│  1. PDFDownloadPipeline (priority 100)                │
│     → Download PDFs to downloads/files/               │
│  2. PDFExtractionPipeline (priority 200)              │
│     → Extract text with PyMuPDF                       │
│     → Verify Cyrillic preservation                    │
│  3. DatabasePipeline (priority 300)                   │
│     → Insert/update PostgreSQL                        │
└─────────────────┬─────────────────────────────────────┘
                  │
                  ↓
┌───────────────────────────────────────────────────────┐
│           POSTGRESQL DATABASE                          │
│  - tenders table (metadata)                           │
│  - documents table (PDFs + text)                      │
│  - document_chunks table (RAG embeddings)             │
└─────────────────┬─────────────────────────────────────┘
                  │
                  ↓
┌───────────────────────────────────────────────────────┐
│           FASTAPI BACKEND                              │
│  /api/tenders                 - List/search           │
│  /api/tenders/{id}            - Get details           │
│  /api/rag/query               - AI chat               │
│  /api/admin/scraper/trigger   - Manual run            │
│  /api/admin/scraper/status    - Monitor status        │
└─────────────────┬─────────────────────────────────────┘
                  │
                  ↓
┌───────────────────────────────────────────────────────┐
│           NEXT.JS FRONTEND                             │
│  /tenders         - Tender explorer                   │
│  /tenders/[id]    - Tender details                    │
│  /dashboard       - Personalized dashboard            │
│  /chat            - AI assistant                      │
│  /competitors     - Competitor analysis               │
│  /admin           - Admin panel (scraper control)     │
└───────────────────────────────────────────────────────┘
```

---

## Monitoring Dashboard (Conceptual)

```
┌─────────────────────────────────────────────────────────┐
│  NABAVKIDATA.COM - SCRAPER MONITORING DASHBOARD         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Last Successful Run: 2024-11-24 00:15:32 UTC          │
│  Next Scheduled Run: 2024-11-25 00:00:00 UTC           │
│  Status: ✓ HEALTHY                                     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  TODAY'S STATISTICS                                     │
│  ├─ Tenders Scraped: 47                                │
│  ├─ New Tenders: 12                                    │
│  ├─ Updated Tenders: 35                                │
│  ├─ PDFs Downloaded: 156                               │
│  ├─ Total Runtime: 23 minutes                          │
│  └─ Average Speed: 2.04 tenders/minute                 │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  FIELD EXTRACTION SUCCESS RATES                         │
│  ├─ ✓ tender_id:         100.0% (47/47)   [EXCELLENT]  │
│  ├─ ✓ title:              97.9% (46/47)   [EXCELLENT]  │
│  ├─ ✓ procuring_entity:   91.5% (43/47)   [GOOD]       │
│  ├─ ✓ closing_date:       85.1% (40/47)   [GOOD]       │
│  ├─ ⚠ category:           76.6% (36/47)   [ACCEPTABLE] │
│  ├─ ⚠ cpv_code:           68.1% (32/47)   [LOW]        │
│  └─ ⚠ estimated_value:    63.8% (30/47)   [LOW]        │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  ERRORS & WARNINGS (Last 24 Hours)                      │
│  ├─ HTTP 404 Not Found: 3                              │
│  ├─ Timeout Errors: 1                                  │
│  ├─ PDF Download Failures: 2                           │
│  └─ ⚠ No critical errors                               │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  DATA QUALITY                                           │
│  ├─ Cyrillic Verification: ✓ PASSED (all documents)    │
│  ├─ Duplicate Tenders: 0                               │
│  ├─ Invalid Dates: 2 (auto-corrected)                  │
│  └─ Missing Critical Fields: 0                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  DATABASE STATISTICS                                    │
│  ├─ Total Tenders: 12,456                              │
│  ├─ Open Tenders: 347                                  │
│  ├─ Closed Tenders: 11,892                             │
│  ├─ Awarded Tenders: 10,234                            │
│  ├─ Total Documents: 45,678                            │
│  └─ Storage Used: 12.4 GB                              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  ACTIONS                                                │
│  ├─ [Run Now]  Trigger Manual Scrape                   │
│  ├─ [View Logs]  See Detailed Logs                     │
│  ├─ [Export Data]  Download CSV/JSON                   │
│  └─ [Settings]  Configure Scraper                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Decision Tree: When to Alert Admin

```
Extraction Success Rate Check:

tender_id < 95%?
  └─> YES → 🔴 CRITICAL ALERT
  └─> NO → Continue

title < 85%?
  └─> YES → 🟠 WARNING ALERT
  └─> NO → Continue

procuring_entity < 80%?
  └─> YES → 🟠 WARNING ALERT
  └─> NO → Continue

Any critical field < 50%?
  └─> YES → 🔴 CRITICAL ALERT + PAUSE SCRAPER
  └─> NO → Continue

Error Rate:

HTTP Errors > 10% of requests?
  └─> YES → 🟠 WARNING ALERT
  └─> NO → Continue

Timeout Errors > 20% of PDFs?
  └─> YES → 🟡 INFO ALERT (check network)
  └─> NO → Continue

Consecutive Failures:

Failed to scrape 3 times in a row?
  └─> YES → 🔴 CRITICAL ALERT + PAUSE SCRAPER
  └─> NO → Continue

Data Freshness:

No new tenders in 48 hours?
  └─> YES → 🟠 WARNING ALERT (scraper stopped?)
  └─> NO → All Good ✓
```

---

## Quick Command Reference

```bash
# Start scraper (default URLs)
scrapy crawl nabavki

# Scrape specific URL
scrapy crawl nabavki -a start_url="https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices"

# Save to JSON
scrapy crawl nabavki -o output.json

# Debug mode (verbose logging)
scrapy crawl nabavki -L DEBUG

# Test mode (limit to 10 items)
scrapy crawl nabavki -s CLOSESPIDER_ITEMCOUNT=10

# Run tests
python tests/test_spider_resilience.py

# Check extraction statistics
tail -f scrapy_log.txt | grep "EXTRACTION STATISTICS" -A 20

# Monitor scraper status (backend API)
curl http://localhost:8000/api/admin/scraper/status

# Trigger manual scrape (backend API)
curl -X POST http://localhost:8000/api/admin/scraper/trigger
```

---

## Priority Flowchart for Next Steps

```
START: Audit Complete
  │
  ├─> Step 1: API Discovery (HIGH PRIORITY)
  │   ├─ Open browser to #/notices
  │   ├─ Open DevTools → Network tab
  │   ├─ Filter: XHR/Fetch
  │   ├─ Document all JSON endpoints
  │   └─ Decision:
  │      ├─ API Found? → Use API (10x faster) ✓
  │      └─ No API? → Use Playwright scraper (current)
  │
  ├─> Step 2: Live Scraper Test (HIGH PRIORITY)
  │   ├─ Run: scrapy crawl nabavki -o test.json
  │   ├─ Check extraction success rates
  │   └─ Decision:
  │      ├─ Success >80%? → Proceed to deployment ✓
  │      └─ Success <80%? → Debug selectors
  │
  ├─> Step 3: Production Deployment (MEDIUM PRIORITY)
  │   ├─ Setup cron job (daily at 00:00)
  │   ├─ Configure error alerts (email)
  │   ├─ Database integration
  │   └─ Monitoring dashboard
  │
  ├─> Step 4: Optimization (LOW PRIORITY)
  │   ├─ Incremental scraping (only new tenders)
  │   ├─ Performance tuning
  │   └─ Frontend integration testing
  │
  └─> END: Production Ready ✓
```

---

**Visual flowcharts for quick reference during development**
**See full audit in E_NABAVKI_TENDER_NOTICES_AUDIT.md**
