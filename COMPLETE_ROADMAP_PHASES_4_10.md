# COMPLETE ROADMAP: PHASES 4-10
## Data-Driven Implementation Strategy

**Philosophy:** No assumptions. Every feature backed by 3-4 real samples from e-nabavki.gov.mk
**Approach:** Inspect → Sample → Validate → Implement → Test
**Quality Standard:** Production-ready code based on actual website structure

---

## PHASE 4: MULTI-CATEGORY SCRAPING & REAL DATA VALIDATION

**Goal:** Scrape awarded, cancelled, and historical tenders based on REAL website structure

**Duration:** 1 week
**Agents:** 8 parallel agents
**Sample Size:** 3-4 tenders per category minimum

---

### STEP 4.1: Website Structure Discovery (Day 1, 4 hours)

#### Task 4.1.1: Map All Tender Categories
**Agent Task:**
1. Use Playwright to navigate e-nabavki.gov.mk homepage
2. Screenshot all navigation menus, tabs, dropdown filters
3. Click each menu item and document:
   - URL patterns
   - Angular route changes
   - XHR requests in Network tab
4. Create comprehensive site map with:
   - Active/Open tenders
   - Awarded tenders
   - Cancelled tenders
   - Archived/Historical tenders
   - Contract execution/Completed contracts
   - Tender modifications/Amendments
   - Any other categories discovered

**Output:** `E_NABAVKI_SITE_MAP.json` with all URLs, routes, and navigation paths

**Validation Checklist:**
- [ ] Navigated to homepage and inspected all menus
- [ ] Clicked every navigation option
- [ ] Documented URL for each category
- [ ] Captured XHR endpoints from Network tab
- [ ] Verified pagination works for each category
- [ ] Noted any JavaScript-based filtering/sorting

---

#### Task 4.1.2: Sample Awarded Tenders (3-4 samples)
**Agent Task:**
1. Navigate to awarded tenders page
2. Extract URLs of 3-4 DIFFERENT awarded tenders
3. For each tender:
   - Save full HTML to `/tmp/awarded_tender_{id}.html`
   - Screenshot the page
   - Extract ALL visible fields
   - Document bidder information layout
   - Check for winner announcement section
   - Look for bid amounts, rankings
4. Compare across all 3-4 samples:
   - Which fields are consistent?
   - Which are optional?
   - Are bidder tables structured the same way?
   - Do all have actual_value_mkd populated?

**Output:**
- `AWARDED_TENDERS_ANALYSIS.md` - Comparative analysis
- HTML samples saved
- Screenshots saved
- Field extraction report

**Validation Checklist:**
- [ ] Found 3-4 awarded tenders with DIFFERENT structures
- [ ] All have winner information
- [ ] All have award date/contract signing date
- [ ] Bidder tables identified (if present)
- [ ] Actual values (awarded amounts) extracted
- [ ] Compared differences between samples
- [ ] Documented edge cases

---

#### Task 4.1.3: Sample Cancelled Tenders (3-4 samples)
**Agent Task:**
1. Navigate to cancelled tenders page
2. Extract URLs of 3-4 cancelled tenders
3. For each tender:
   - Save HTML
   - Extract cancellation reason
   - Extract cancellation date
   - Check if bidder info visible before cancellation
4. Compare:
   - Cancellation reason format (text field? dropdown?)
   - Cancellation date location
   - Status field value

**Output:**
- `CANCELLED_TENDERS_ANALYSIS.md`
- HTML samples
- Field comparison table

**Validation Checklist:**
- [ ] Found 3-4 cancelled tenders
- [ ] Cancellation reason extracted
- [ ] Cancellation date identified
- [ ] Status field confirmed
- [ ] Documented differences

---

#### Task 4.1.4: Sample Historical Tenders (3-4 samples from different years)
**Agent Task:**
1. Find archive/historical section
2. Sample tenders from:
   - 2024
   - 2023
   - 2022
   - 2021 or 2020
3. Document:
   - Are old tenders structured differently?
   - Are fields missing in older tenders?
   - Is pagination different?
   - How many tenders per year?

**Output:**
- `HISTORICAL_TENDERS_ANALYSIS.md`
- Estimated total tender count per year

**Validation Checklist:**
- [ ] Sampled tenders from 3-4 different years
- [ ] Identified schema changes over time
- [ ] Calculated scraping scope (how many tenders)
- [ ] Verified data completeness

---

### STEP 4.2: Bidder Data Extraction (Day 2, 6 hours)

#### Task 4.2.1: Analyze Bidder Tables (3-4 awarded tenders)
**Agent Task:**
1. For EACH of the 3-4 awarded tender samples:
   - Inspect HTML structure of bidder/participant section
   - Identify table/list structure
   - Document column headers (Macedonian + English)
   - Extract sample bidder data
2. Create selector mapping:
   ```json
   {
     "bidder_table_selector": "...",
     "bidder_row_selector": "...",
     "columns": {
       "company_name": "...",
       "bid_amount": "...",
       "rank": "...",
       "is_winner": "..."
     }
   }
   ```
3. Test selectors on all 3-4 samples
4. Handle edge cases:
   - Single bidder (only winner)
   - Disqualified bidders
   - Missing bid amounts

**Output:**
- `BIDDER_EXTRACTION_STRATEGY.md`
- Tested selector mappings
- Edge case documentation

**Validation Checklist:**
- [ ] Bidder tables found in 3-4 samples
- [ ] Selectors work across all samples
- [ ] Handles single-bidder tenders
- [ ] Handles disqualified bidders
- [ ] Extracts all relevant fields

---

#### Task 4.2.2: Update Spider with Bidder Extraction
**Agent Task:**
1. Update `_extract_bidders()` with REAL selectors from analysis
2. Remove assumptions, use actual patterns found
3. Add logging for each extraction step
4. Test on all 3-4 samples

**Output:** Updated `nabavki_spider.py` with production-ready bidder extraction

---

### STEP 4.3: Lot Data Extraction (Day 2, 4 hours)

#### Task 4.3.1: Find Dividable Tenders (3-4 samples)
**Agent Task:**
1. Search for tenders with "Делива набавка: Да"
2. Extract 3-4 multi-lot tenders
3. For each:
   - Document lot table structure
   - Extract lot numbers, titles, values
   - Check if lots have separate bidders
   - Verify CPV codes per lot

**Output:**
- `LOT_EXTRACTION_STRATEGY.md`
- HTML samples of multi-lot tenders

**Validation Checklist:**
- [ ] Found 3-4 dividable tenders
- [ ] Lot tables analyzed
- [ ] Selectors tested across samples
- [ ] Lot-bidder relationship documented

---

#### Task 4.3.2: Update Spider with Lot Extraction
**Agent Task:**
1. Update `_extract_lots()` with REAL selectors
2. Test on all samples
3. Handle nested lot-bidder relationships

**Output:** Updated `nabavki_spider.py`

---

### STEP 4.4: Implement Multi-Category Spider (Day 3-4, 12 hours)

#### Task 4.4.1: Create Category-Based Scraping
**Agent Task:**
1. Add spider parameter for category:
   ```bash
   scrapy crawl nabavki -a category=awarded
   scrapy crawl nabavki -a category=cancelled
   scrapy crawl nabavki -a category=historical
   ```
2. Implement URL routing based on category
3. Add category-specific field extraction:
   - Awarded: winner, actual_value, contract_date, bidders
   - Cancelled: cancellation_reason, cancellation_date
   - Historical: no special handling, same as active
4. Update status mapping:
   - awarded → 'awarded'
   - cancelled → 'cancelled'
   - historical → 'closed' or 'awarded'

**Output:** Multi-category capable spider

---

#### Task 4.4.2: Test Each Category (3 tenders each)
**Agent Task:**
1. Run test scrapes:
   ```bash
   scrapy crawl nabavki -a category=awarded -s CLOSESPIDER_ITEMCOUNT=3
   scrapy crawl nabavki -a category=cancelled -s CLOSESPIDER_ITEMCOUNT=3
   scrapy crawl nabavki -a category=historical -s CLOSESPIDER_ITEMCOUNT=3
   ```
2. Verify:
   - Correct status mapping
   - Bidder data populated (awarded)
   - Cancellation reason populated (cancelled)
   - All fields extracted correctly

**Output:** Test report with success metrics

---

### STEP 4.5: Document Extraction Enhancement (Day 5, 6 hours)

#### Task 4.5.1: Analyze Document Sections (3-4 tenders)
**Agent Task:**
1. For 3-4 different tenders:
   - Inspect document attachment sections
   - Document how files are linked (direct links? download buttons? XHR?)
   - Check for document metadata (upload date, file size, description)
   - Test downloading 2-3 documents manually
2. Check Network tab for download XHR:
   - Endpoint URL pattern
   - Request method (GET/POST)
   - Required headers/cookies
   - Authentication needed?

**Output:**
- `DOCUMENT_DOWNLOAD_STRATEGY.md`
- Sample download URLs
- XHR request patterns

**Validation Checklist:**
- [ ] Analyzed documents in 3-4 tenders
- [ ] Download mechanism identified
- [ ] XHR patterns documented
- [ ] Tested manual downloads
- [ ] Checked for access restrictions

---

#### Task 4.5.2: Implement Network Interception
**Agent Task:**
1. Add Playwright request interception
2. Capture document download URLs
3. Handle redirects and authentication
4. Test on 3-4 tenders

**Output:** Enhanced document download pipeline

---

### STEP 4.6: Integration Testing & Deployment (Day 6-7, 8 hours)

#### Task 4.6.1: Full Category Testing
```bash
# Awarded tenders
scrapy crawl nabavki -a category=awarded -s CLOSESPIDER_ITEMCOUNT=10

# Cancelled tenders
scrapy crawl nabavki -a category=cancelled -s CLOSESPIDER_ITEMCOUNT=10

# Historical tenders (2023)
scrapy crawl nabavki -a category=historical -a year=2023 -s CLOSESPIDER_ITEMCOUNT=20
```

**Validation:**
- [ ] Bidders populated for awarded tenders
- [ ] Lots populated for dividable tenders
- [ ] Cancellation data for cancelled tenders
- [ ] Triggers executed (entity/supplier stats updated)
- [ ] Documents categorized correctly

---

#### Task 4.6.2: Database Verification
```sql
-- Check awarded tenders have bidders
SELECT t.tender_id, t.winner, COUNT(b.bidder_id) as bidder_count
FROM tenders t
LEFT JOIN tender_bidders b ON t.tender_id = b.tender_id
WHERE t.status = 'awarded'
GROUP BY t.tender_id, t.winner;

-- Check dividable tenders have lots
SELECT t.tender_id, t.has_lots, COUNT(l.lot_id) as lot_count
FROM tenders t
LEFT JOIN tender_lots l ON t.tender_id = l.tender_id
WHERE t.has_lots = TRUE
GROUP BY t.tender_id, t.has_lots;

-- Check supplier profiles updated
SELECT company_name, total_wins, total_bids, win_rate
FROM suppliers
ORDER BY total_wins DESC
LIMIT 10;
```

---

## PHASE 5: INCREMENTAL SCRAPING & CHANGE DETECTION (Week 2)

**Goal:** Only scrape new/modified tenders to reduce load

### STEP 5.1: Analyze Tender Change Patterns (Day 1, 4 hours)

#### Task 5.1.1: Sample Tender Lifecycle (5-7 tenders)
**Agent Task:**
1. Find 5-7 tenders at DIFFERENT lifecycle stages:
   - Newly published (< 1 day old)
   - Open with deadline approaching
   - Recently awarded
   - Recently cancelled
   - Modified/amended
2. For each, document:
   - What fields change during lifecycle?
   - Is there a "last modified" timestamp?
   - How to detect amendments?
3. Scrape same tender twice (1 hour apart):
   - Did anything change?
   - How to detect changes?

**Output:**
- `TENDER_LIFECYCLE_ANALYSIS.md`
- Change detection strategy

**Validation Checklist:**
- [ ] Sampled 5-7 tenders at different stages
- [ ] Identified modification timestamps
- [ ] Documented field changes during lifecycle
- [ ] Tested change detection approach

---

### STEP 5.2: Implement Incremental Logic (Day 2-3, 12 hours)

#### Task 5.2.1: Add Last-Scraped Tracking
```python
# In spider
def should_scrape_tender(self, tender_id, last_modified_date):
    """Check if tender needs re-scraping"""
    # Query last_scraped date from database
    # Compare with last_modified_date from listing page
    # Return True if new or modified
```

#### Task 5.2.2: Implement Change Detection
```sql
-- Add to tenders table
ALTER TABLE tenders ADD COLUMN last_modified DATE;
ALTER TABLE tenders ADD COLUMN scrape_count INTEGER DEFAULT 1;
```

#### Task 5.2.3: Test Incremental Mode
```bash
# First run: scrape all
scrapy crawl nabavki -a mode=full -s CLOSESPIDER_ITEMCOUNT=50

# Second run: only new/modified (should be 0-5)
scrapy crawl nabavki -a mode=incremental -s CLOSESPIDER_ITEMCOUNT=50
```

**Validation:**
- [ ] Incremental mode skips unchanged tenders
- [ ] Detects new tenders
- [ ] Detects modified tenders
- [ ] 80%+ reduction in scraping time

---

## PHASE 6: CRON AUTOMATION & SCHEDULING (Week 2)

**Goal:** Automated periodic scraping

### STEP 6.1: Create Cron Scripts (Day 4, 4 hours)

#### Script 1: Active Tenders (Every 3 hours)
```bash
#!/bin/bash
# /home/ubuntu/nabavkidata/scraper/cron/scrape_active.sh
cd /home/ubuntu/nabavkidata/scraper
source ../venv/bin/activate
export DATABASE_URL='...'
scrapy crawl nabavki -a category=active -a mode=incremental >> /var/log/nabavkidata/active_$(date +%Y%m%d_%H%M%S).log 2>&1
```

#### Script 2: Awarded Tenders (Daily at 2 AM)
```bash
#!/bin/bash
# scrape_awarded.sh
scrapy crawl nabavki -a category=awarded -a mode=incremental
```

#### Script 3: Historical Backfill (Weekly, Sundays 3 AM)
```bash
#!/bin/bash
# scrape_historical.sh
# Scrape one year at a time
YEAR=$(date -d "last year" +%Y)
scrapy crawl nabavki -a category=historical -a year=$YEAR -a mode=full
```

---

### STEP 6.2: Setup Crontab (Day 4, 2 hours)

```cron
# Active tenders every 3 hours
0 */3 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_active.sh

# Awarded tenders daily at 2 AM
0 2 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_awarded.sh

# Cancelled tenders daily at 3 AM
0 3 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_cancelled.sh

# Historical backfill weekly (Sunday 3 AM)
0 3 * * 0 /home/ubuntu/nabavkidata/scraper/cron/scrape_historical.sh

# Cleanup old logs (monthly)
0 4 1 * * find /var/log/nabavkidata -name "*.log" -mtime +30 -delete
```

---

## PHASE 7: API ENDPOINTS FOR NEW DATA (Week 3)

**Goal:** Expose new data via REST API

### STEP 7.1: Design API Endpoints (Day 1, 4 hours)

#### Analyze Real Data Needs
**Agent Task:**
1. Query database for real data:
   ```sql
   -- What supplier data exists?
   SELECT * FROM suppliers LIMIT 5;

   -- What entity data exists?
   SELECT * FROM procuring_entities LIMIT 5;

   -- Tender with bidders
   SELECT t.*, json_agg(b.*) as bidders
   FROM tenders t
   JOIN tender_bidders b ON t.tender_id = b.tender_id
   GROUP BY t.tender_id LIMIT 3;
   ```

2. Based on REAL data structure, design endpoints:
   - `/api/entities/{entity_id}` - Entity profile
   - `/api/suppliers/{supplier_id}` - Supplier profile
   - `/api/tenders/{tender_id}/bidders` - All bidders
   - `/api/tenders/{tender_id}/lots` - Lot breakdown
   - `/api/tenders/{tender_id}/amendments` - Change history
   - `/api/tenders/{tender_id}/documents` - Documents with categories
   - `/api/analytics/trends` - Aggregated statistics

**Output:**
- `API_SPECIFICATION.md` with real data examples
- OpenAPI/Swagger spec

---

### STEP 7.2: Implement Endpoints (Day 2-3, 12 hours)

Create endpoints in `/backend/api/` based on REAL data structure

Test with REAL tender IDs from database

---

## PHASE 8: FRONTEND INTEGRATION (Week 3-4)

**Goal:** Display enhanced data in UI

### STEP 8.1: Analyze Real User Needs (Day 1, 4 hours)

#### Sample Real Tender Pages
**Agent Task:**
1. Pick 3-4 REAL tenders from database (awarded, with bidders/lots)
2. For each, design mockup showing:
   - Contact information display
   - Bidder comparison table
   - Lot breakdown
   - Amendment timeline
   - Document categories
3. Create wireframes based on REAL data

**Output:**
- UI mockups with real data
- Feature priority list

---

### STEP 8.2: Implement UI Components (Day 2-5, 16 hours)

Based on real data and mockups, implement:
- Tender detail enhancements
- Entity profile pages
- Supplier profile pages
- Bidder comparison views
- Document categorization UI

---

## PHASE 9: AI PIPELINE & EMBEDDINGS (Week 4)

**Goal:** Connect enhanced data to AI/RAG system

### STEP 9.1: Analyze Real Document Content (Day 1, 4 hours)

#### Sample Document Text Extraction
**Agent Task:**
1. Extract text from 10-15 REAL downloaded PDFs
2. Analyze:
   - What's in technical_specs documents?
   - What's in financial_docs?
   - What's in award_decisions?
3. Design embedding strategy based on REAL content

**Output:**
- Document content analysis
- Embedding chunking strategy

---

### STEP 9.2: Implement Embedding Pipeline (Day 2-4, 12 hours)

Based on real document analysis:
- Trigger embeddings for new documents
- Chunk by category (different sizes for different types)
- Store in pgvector
- Test retrieval with real queries

---

## PHASE 10: MONITORING & OPTIMIZATION (Week 5)

**Goal:** Production monitoring and performance optimization

### STEP 10.1: Real Performance Analysis (Day 1-2, 8 hours)

#### Measure Real Scraping Performance
**Agent Task:**
1. Run full scrape and measure:
   - Time per tender category
   - Database insert performance
   - Memory usage patterns
   - Error rates
2. Analyze REAL bottlenecks (not assumptions)
3. Optimize based on measurements

**Output:**
- Performance report with real metrics
- Optimization plan based on data

---

### STEP 10.2: Setup Monitoring (Day 3-4, 8 hours)

Based on real performance data:
- Prometheus metrics
- Grafana dashboards
- Alert thresholds (based on real baseline)
- Error tracking

---

### STEP 10.3: Production Hardening (Day 5, 4 hours)

- Rate limiting (test with real site)
- Retry logic (based on real error patterns)
- Connection pooling (optimize for real load)
- Backup automation

---

## EXECUTION PRINCIPLES (ALL PHASES)

### 1. **Sample-First Approach**
```
❌ DON'T: Assume bidder table has 5 columns
✅ DO: Extract 3-4 awarded tenders, inspect actual table structure, document all variations
```

### 2. **Multi-Sample Validation**
```
❌ DON'T: Test selector on 1 tender
✅ DO: Test on 3-4 tenders with DIFFERENT structures, handle all edge cases found
```

### 3. **Real Data Documentation**
```
Every implementation MUST include:
- URLs of sample tenders used
- Screenshots of actual pages
- HTML snippets showing real structure
- Comparison table across samples
- Edge cases discovered
```

### 4. **Iterative Refinement**
```
1. Inspect 3-4 samples
2. Design solution
3. Test on samples
4. Find edge cases
5. Update solution
6. Test on 10+ different tenders
7. Deploy
```

---

## SAMPLE VALIDATION TEMPLATE

For every feature, create:

```markdown
## Feature: Bidder Extraction

### Samples Analyzed
1. Tender 12345/2024 - https://e-nabavki.gov.mk/... - 5 bidders, table format
2. Tender 12346/2024 - https://e-nabavki.gov.mk/... - 1 bidder, single div
3. Tender 12347/2024 - https://e-nabavki.gov.mk/... - 3 bidders, 1 disqualified
4. Tender 12348/2024 - https://e-nabavki.gov.mk/... - no bidders (active)

### Common Patterns Found
- 75% use table with class "bidder-table"
- 25% use div with ng-repeat
- Disqualified bidders have class "disqualified"
- Winner has checkmark icon

### Edge Cases
- Single bidder: no table, just text
- Active tenders: no bidder section at all
- Disqualified: need to parse reason from tooltip

### Implementation
[Code based on REAL patterns found above]

### Test Results
- Tested on 15 different tenders
- Success rate: 14/15 (93%)
- 1 failure: tender with unusual layout, logged as edge case
```

---

## DELIVERABLES PER PHASE

### Phase 4
- [ ] Site map with ALL discovered categories
- [ ] 3-4 HTML samples per category (awarded, cancelled, historical)
- [ ] Bidder extraction strategy doc (tested on 3-4 samples)
- [ ] Lot extraction strategy doc (tested on 3-4 samples)
- [ ] Updated spider with multi-category support
- [ ] Integration test report (10 tenders per category)

### Phase 5
- [ ] Tender lifecycle analysis (5-7 samples)
- [ ] Incremental scraping implementation
- [ ] Performance comparison (full vs incremental)
- [ ] Change detection validation report

### Phase 6
- [ ] Cron scripts for all categories
- [ ] Crontab configuration
- [ ] Logging and monitoring setup
- [ ] 1-week automation test report

### Phase 7
- [ ] API specification (based on real data)
- [ ] Implemented endpoints
- [ ] API test suite with real tender IDs
- [ ] Postman collection

### Phase 8
- [ ] UI mockups with real data
- [ ] Implemented frontend components
- [ ] User testing with 3-4 real tenders
- [ ] Screenshots of new features

### Phase 9
- [ ] Document content analysis (10-15 PDFs)
- [ ] Embedding pipeline
- [ ] RAG system integration
- [ ] Query test results

### Phase 10
- [ ] Performance analysis report (real metrics)
- [ ] Monitoring dashboards
- [ ] Alert configuration
- [ ] Production readiness checklist

---

## SUCCESS METRICS

### Quantitative
- **Data Coverage**: 95%+ of available fields extracted
- **Accuracy**: 98%+ field extraction accuracy (validated on 100 random samples)
- **Reliability**: 99.5%+ uptime for automated scraping
- **Performance**: <5 min for incremental scrape, <2 hours for full daily scrape
- **Completeness**: 100% of tender categories covered

### Qualitative
- **Zero assumptions**: Every feature backed by 3+ real samples
- **Edge case handling**: All discovered edge cases documented and handled
- **Real-world validation**: Tested on 100+ diverse tenders before production
- **Documentation**: Every decision includes links to sample tenders and screenshots

---

**Roadmap Created:** 2025-11-24
**Total Duration:** 5 weeks (Phases 4-10)
**Approach:** Sample-first, data-driven, multi-validation
**Quality Target:** Production-ready system based on real website structure
