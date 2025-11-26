# PHASE 3 & 4 EXECUTION ROADMAP

**Objective:** Complete comprehensive data model implementation and multi-category scraping
**Approach:** Parallel multi-agent execution for maximum efficiency
**Quality Standard:** Production-ready, tested, working system

---

## PHASE 3: COMPLETE IMPLEMENTATION

### Block 3A: Spider Enhancement (PARALLEL EXECUTION)
**Status:** 🔄 IN PROGRESS

#### Agent 1: Contact & Financial Field Extraction
**File:** `scraper/scraper/spiders/nabavki_spider.py`
**Tasks:**
- [ ] Add selectors for contact_person, contact_email, contact_phone
- [ ] Add selectors for security_deposit_mkd, performance_guarantee_mkd
- [ ] Add selectors for payment_terms, evaluation_method
- [ ] Test extraction on 3 sample tenders
**Estimated Time:** 45 minutes
**Output:** Updated extraction methods with new field selectors

#### Agent 2: Bidder & Lot Data Extraction
**File:** `scraper/scraper/spiders/nabavki_spider.py`
**Tasks:**
- [ ] Inspect tender pages for bidder tables
- [ ] Create `_extract_bidders()` method
- [ ] Create `_extract_lots()` method (if multi-lot tenders exist)
- [ ] Return as JSON arrays (bidders_data, lots_data)
**Estimated Time:** 60 minutes
**Output:** New extraction methods for related entities

#### Agent 3: Document Categorization Logic
**File:** `scraper/scraper/spiders/nabavki_spider.py`
**Tasks:**
- [ ] Analyze document filenames/URLs for patterns
- [ ] Create `_categorize_document()` helper function
- [ ] Map patterns to categories (technical_specs, financial_docs, award_decision, etc.)
- [ ] Add SHA-256 hash calculation
**Estimated Time:** 30 minutes
**Output:** Document categorization function

### Block 3B: Pipeline Enhancement (PARALLEL EXECUTION)
**Status:** ⏳ PENDING

#### Agent 4: Extended Tender Insertion
**File:** `scraper/scraper/pipelines.py`
**Tasks:**
- [ ] Update `insert_tender()` SQL to include 13 new fields
- [ ] Add field mapping for new columns
- [ ] Add NULL handling for optional fields
- [ ] Test with sample data
**Estimated Time:** 30 minutes
**Output:** Updated insert_tender() method

#### Agent 5: Related Tables Insertion
**File:** `scraper/scraper/pipelines.py`
**Tasks:**
- [ ] Create `insert_tender_lots()` method
- [ ] Create `insert_tender_bidders()` method
- [ ] Create `insert_tender_amendments()` method (if data available)
- [ ] Add transaction management for multi-table inserts
**Estimated Time:** 60 minutes
**Output:** New insertion methods for related tables

#### Agent 6: Document Enhancement
**File:** `scraper/scraper/pipelines.py`
**Tasks:**
- [ ] Update document INSERT to include doc_category, doc_version, upload_date, file_hash
- [ ] Add duplicate detection via file_hash
- [ ] Implement hash calculation in PDFDownloadPipeline
**Estimated Time:** 30 minutes
**Output:** Enhanced document pipeline

### Block 3C: Testing & Validation (SEQUENTIAL)
**Status:** ⏳ PENDING

#### Agent 7: Integration Testing
**Tasks:**
- [ ] Upload all updated files to EC2
- [ ] Run test scrape with CLOSESPIDER_ITEMCOUNT=3
- [ ] Verify data in all tables (tenders, tender_lots, tender_bidders, documents)
- [ ] Check trigger execution (procuring_entities, suppliers auto-updated)
- [ ] Validate data quality and completeness
**Estimated Time:** 45 minutes
**Output:** Test report with success metrics

---

## PHASE 4: MULTI-CATEGORY SCRAPING

### Block 4A: Site Analysis (PARALLEL EXECUTION)
**Status:** ⏳ PENDING

#### Agent 8: Discover Tender Categories
**Tasks:**
- [ ] Use Playwright to navigate e-nabavki.gov.mk
- [ ] Identify all tender category pages (awarded, cancelled, historical)
- [ ] Capture XHR requests for each category
- [ ] Document URL patterns and pagination logic
**Estimated Time:** 60 minutes
**Output:** Category mapping JSON with URLs and endpoints

#### Agent 9: Document Download Analysis
**Tasks:**
- [ ] Inspect tender detail pages for document sections
- [ ] Map document types to categories
- [ ] Test network interception for downloads
- [ ] Document download API endpoints
**Estimated Time:** 45 minutes
**Output:** Document extraction strategy

### Block 4B: Multi-Category Spider Implementation (PARALLEL EXECUTION)
**Status:** ⏳ PENDING

#### Agent 10: Awarded Tenders Spider
**Tasks:**
- [ ] Create separate spider or extend existing with category parameter
- [ ] Implement URL routing for awarded tenders
- [ ] Add specific selectors for awarded tender fields (actual_value, winner, contract_date)
- [ ] Test scraping awarded tenders
**Estimated Time:** 60 minutes
**Output:** Awarded tender scraping capability

#### Agent 11: Cancelled Tenders Spider
**Tasks:**
- [ ] Implement cancelled tender scraping logic
- [ ] Extract cancellation reason, cancellation_date
- [ ] Map status to 'cancelled'
**Estimated Time:** 45 minutes
**Output:** Cancelled tender scraping capability

#### Agent 12: Historical Data Backfill
**Tasks:**
- [ ] Implement date range filtering
- [ ] Add pagination logic for historical data (2020-2024)
- [ ] Optimize for large-scale scraping
**Estimated Time:** 60 minutes
**Output:** Historical tender scraping capability

### Block 4C: Enhanced Document Extraction (SEQUENTIAL)
**Status:** ⏳ PENDING

#### Agent 13: Network Interception
**Tasks:**
- [ ] Implement Playwright request interception
- [ ] Capture document download URLs
- [ ] Handle authentication/session tokens
- [ ] Test on multiple document types
**Estimated Time:** 60 minutes
**Output:** Robust document download mechanism

---

## PHASE 5: INCREMENTAL SCRAPING & AUTOMATION

### Block 5A: Change Detection (PARALLEL EXECUTION)
**Status:** ⏳ PENDING

#### Agent 14: Incremental Logic
**Tasks:**
- [ ] Add last_scraped timestamp tracking
- [ ] Implement change detection (compare scraped_at vs updated_at)
- [ ] Only process new/modified tenders
- [ ] Log tender_updated events
**Estimated Time:** 45 minutes
**Output:** Incremental scraping system

#### Agent 15: Cron Automation
**Tasks:**
- [ ] Create cron scripts for different categories
- [ ] Schedule: active tenders (3h), awarded (daily), historical (weekly)
- [ ] Add error handling and retries
- [ ] Set up logging and monitoring
**Estimated Time:** 45 minutes
**Output:** Automated scraping schedule

---

## EXECUTION PLAN

### Immediate (Next 2-3 Hours)
**Launch Agents 1-6 in PARALLEL** → Complete Phase 3 Spider & Pipeline
- Agents 1, 2, 3 work on spider extraction (parallel)
- Agents 4, 5, 6 work on pipeline insertion (parallel)
- Total wall time: ~60-90 minutes (instead of 4+ hours sequential)

### Next (After Agent 1-6 Complete)
**Launch Agent 7** → Testing & Validation
- Integration test to verify Phase 3 works end-to-end
- Total wall time: ~45 minutes

### Then (After Testing Passes)
**Launch Agents 8-9 in PARALLEL** → Phase 4 Analysis
- Discover tender categories and document patterns
- Total wall time: ~60 minutes

### Next (After Analysis Complete)
**Launch Agents 10-12 in PARALLEL** → Multi-Category Implementation
- Implement awarded, cancelled, historical scrapers
- Total wall time: ~60 minutes

### Finally
**Launch Agents 13-15 SEQUENTIALLY** → Polish & Automation
- Network interception, incremental scraping, cron setup
- Total wall time: ~2 hours

### TOTAL ESTIMATED TIME: 5-6 hours (vs 12+ hours sequential)

---

## QUALITY GATES

Each agent must pass these checks before proceeding:

### Code Quality
- [ ] No syntax errors
- [ ] Follows existing code style
- [ ] Includes error handling
- [ ] Has logging statements
- [ ] Backward compatible

### Functional Quality
- [ ] Tested on real data
- [ ] Handles edge cases (missing fields, empty values)
- [ ] No data loss
- [ ] Proper NULL handling

### Performance Quality
- [ ] No N+1 queries
- [ ] Uses batch operations where possible
- [ ] Memory efficient
- [ ] Proper connection pooling

---

## SUCCESS METRICS

### Phase 3 Complete
- [x] Database migration successful
- [x] 6 new tables functional
- [ ] Spider extracts 60+ fields per tender
- [ ] Pipeline inserts to all tables
- [ ] Test scrape shows data in tender_lots, tender_bidders, procuring_entities, suppliers
- [ ] Triggers auto-update entity/supplier stats

### Phase 4 Complete
- [ ] Can scrape awarded tenders
- [ ] Can scrape cancelled tenders
- [ ] Can backfill historical data (2020-2024)
- [ ] Documents categorized and deduplicated
- [ ] All tender types visible in database

### Phase 5 Complete
- [ ] Incremental scraping functional
- [ ] Cron jobs scheduled and running
- [ ] Only new/modified tenders processed
- [ ] Monitoring and alerts operational

---

## DELIVERABLES

### Code Files
1. Updated `scraper/scraper/spiders/nabavki_spider.py` (~500 lines added)
2. Updated `scraper/scraper/pipelines.py` (~400 lines added)
3. Cron scripts in `scraper/cron/`
4. Monitoring dashboard config

### Documentation
1. PHASE3_COMPLETION_REPORT.md
2. PHASE4_COMPLETION_REPORT.md
3. SCRAPER_USAGE_GUIDE.md
4. API_DOCUMENTATION.md (for new endpoints)

### Deployment Scripts
1. `deploy_phase3.sh` - One-click Phase 3 deployment
2. `deploy_phase4.sh` - One-click Phase 4 deployment
3. `setup_cron.sh` - Cron automation setup

---

**Roadmap Created:** 2025-11-24
**Estimated Completion:** 5-6 hours with parallel execution
**Quality Target:** Production-ready, fully tested, documented system
