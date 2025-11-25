# Production Readiness Roadmap for Nabavkidata

**Date**: November 25, 2025
**Status**: Pre-Production (Critical Issues Found)

---

## Executive Summary

Database audit reveals critical data quality issues that must be resolved before production deployment. The system is collecting data but with significant gaps in key fields.

### Current Database State

| Table | Records | Status |
|-------|---------|--------|
| tenders | 214 | Test data |
| documents | 15 | Low volume |
| tender_bidders | 16 | Sparse |
| tender_lots | 0 | Not populated |
| product_items | 62 | Garbage data |
| users | 17 | Test users |
| epazar_* | 0 | Tables don't exist! |

### Tender Distribution by Status
- Open: 149
- Cancelled: 38
- Awarded: 27

---

## CRITICAL ISSUES

### 1. Field Fill Rate Analysis

| Field | Fill Rate | Severity | Action Required |
|-------|-----------|----------|-----------------|
| tender_id | 100% | OK | - |
| title | 100% | OK | - |
| procuring_entity | 100% | OK | - |
| status | 100% | OK | - |
| procedure_type | 82% | OK | - |
| closing_date | 70% | WARN | Review XPath selectors |
| estimated_value_mkd | 27% | FAIL | Fix currency extraction |
| opening_date | **0%** | **CRITICAL** | Fix XPath selector - currently broken! |
| description | 5% | FAIL | Fix description extraction |
| cpv_code | 5% | FAIL | Fix CPV extraction |
| winner | 5% | FAIL | Only for awarded tenders |

### 2. Product Items Quality Issue

Current product_items table contains **garbage data**:
- "540,00" (should be a product name)
- "000,00"
- "600,00"
- "I.2 Се согласуваме со начинот..."

**Root Cause**: The spec_extractor is pulling numbers/prices instead of actual product names from tender documents.

### 3. E-Pazar Integration Not Complete

- Migration `006_epazar_tables.sql` exists but **NOT RUN**
- Spider `epazar_spider.py` exists but cannot save data
- Frontend pages exist but will show empty data

---

## PHASE 1: Critical Fixes (Must Do Before Reset)

### 1.1 Run E-Pazar Database Migration
```bash
# On EC2
cd /home/ubuntu/nabavkidata
source venv/bin/activate
psql "$DATABASE_URL" -f db/migrations/006_epazar_tables.sql
```

### 1.2 Fix opening_date XPath Extraction

**File**: `scraper/scraper/spiders/nabavki_spider.py`

The XPath selectors for `opening_date` are not matching the actual page structure. Need to:
1. Run the scraper in debug mode on a single tender
2. Capture the actual HTML structure
3. Update XPath in `_extract_date()` method

Current selectors (lines 943-946):
```python
'opening_date': [
    '//label[@label-for="OPENING DATE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
    '//label[@label-for="BID OPENING DATE DOSIE"]/following-sibling::label[contains(@class, "dosie-value")][1]/text()',
],
```

### 1.3 Fix Product Name Extraction

**File**: `scraper/document_parser.py` or extraction logic

The extractor needs to identify actual product names from tender specifications, not random numbers/prices.

### 1.4 Fix Description Extraction

Low fill rate (5%) suggests XPath selectors are not matching. Need to review `description` extraction logic.

### 1.5 Fix CPV Code Extraction

CPV codes are essential for product categorization. Currently 5% fill rate.

---

## PHASE 2: Data Reset & Test Scrape

### 2.1 Clean Test Data
```bash
# On EC2 - CAUTION: This deletes all data
psql "$DATABASE_URL" << 'EOF'
TRUNCATE TABLE product_items CASCADE;
TRUNCATE TABLE tender_bidders CASCADE;
TRUNCATE TABLE tender_lots CASCADE;
TRUNCATE TABLE documents CASCADE;
TRUNCATE TABLE tenders CASCADE;
-- Keep users table
EOF
```

### 2.2 Run Test Scrape (10 per category)

```bash
# Test scrape - limited to 10 tenders per category
cd /home/ubuntu/nabavkidata/scraper
source ../venv/bin/activate

# Active tenders
scrapy crawl nabavki -a category=active -a max_items=10 -L INFO

# Awarded tenders
scrapy crawl nabavki -a category=awarded -a max_items=10 -L INFO

# Cancelled tenders
scrapy crawl nabavki -a category=cancelled -a max_items=10 -L INFO
```

### 2.3 Validate Field Fill Rates

After test scrape, run validation query:
```sql
SELECT
    COUNT(*) as total,
    COUNT(opening_date) as opening_date_filled,
    COUNT(NULLIF(description, '')) as description_filled,
    COUNT(estimated_value_mkd) as est_value_filled,
    COUNT(NULLIF(cpv_code, '')) as cpv_filled
FROM tenders;
```

**Target Fill Rates**:
- opening_date: >95%
- description: >80%
- estimated_value_mkd: >80%
- cpv_code: >70%

---

## PHASE 3: E-Pazar Integration Test

### 3.1 Test E-Pazar Spider
```bash
scrapy crawl epazar -a category=active -a max_items=10 -L INFO
```

### 3.2 Validate E-Pazar Data
```sql
SELECT
    (SELECT COUNT(*) FROM epazar_tenders) as tenders,
    (SELECT COUNT(*) FROM epazar_items) as items,
    (SELECT COUNT(*) FROM epazar_offers) as offers;
```

---

## PHASE 4: Full Production Scrape

### 4.1 Prerequisites Checklist
- [ ] E-Pazar migration run
- [ ] opening_date extraction fixed (>95% fill rate)
- [ ] description extraction fixed (>80% fill rate)
- [ ] Product name extraction fixed
- [ ] Test scrape validated
- [ ] EC2 has sufficient disk space
- [ ] Database has sufficient capacity
- [ ] Monitoring/alerts configured

### 4.2 Production Scrape Commands

```bash
# Full scrape - all categories, all pages
# Estimated time: 4-8 hours depending on volume

# E-Nabavki tenders
scrapy crawl nabavki -a category=active -L INFO &
scrapy crawl nabavki -a category=awarded -L INFO &
scrapy crawl nabavki -a category=cancelled -L INFO &

# E-Pazar marketplace
scrapy crawl epazar -a category=all -L INFO &
```

### 4.3 Post-Scrape Validation

```sql
-- Comprehensive data quality check
SELECT
    'tenders' as table_name,
    COUNT(*) as total,
    ROUND(COUNT(opening_date)::numeric / COUNT(*) * 100, 1) as opening_date_pct,
    ROUND(COUNT(NULLIF(description, ''))::numeric / COUNT(*) * 100, 1) as description_pct,
    ROUND(COUNT(estimated_value_mkd)::numeric / COUNT(*) * 100, 1) as est_value_pct,
    ROUND(COUNT(NULLIF(cpv_code, ''))::numeric / COUNT(*) * 100, 1) as cpv_pct
FROM tenders;
```

---

## PHASE 5: Frontend & API Verification

### 5.1 API Endpoints to Test
- [ ] `GET /api/tenders` - List tenders with filters
- [ ] `GET /api/tenders/{id}` - Tender detail
- [ ] `GET /api/products/search` - Product search
- [ ] `GET /api/epazar/tenders` - E-Pazar listings
- [ ] `GET /api/analytics/stats` - Dashboard stats

### 5.2 Frontend Pages to Verify
- [ ] `/dashboard` - Stats cards show data
- [ ] `/tenders` - Tender list with filters
- [ ] `/tenders/{id}` - Tender detail page
- [ ] `/products` - Product search works
- [ ] `/epazar` - E-Pazar listings show
- [ ] `/competitors` - Competitor analysis

---

## Git Status - Uncommitted Changes

The following changes need to be committed:

### Modified Files
- `backend/api/__init__.py` - Added products router
- `backend/api/products.py` - NEW: Product search API
- `backend/main.py` - Registered products router
- `backend/models.py` - Added ProductItem model
- `backend/schemas.py` - Added product search schemas
- `frontend/app/products/page.tsx` - NEW: Product search UI
- `frontend/config/navigation.ts` - Added Products nav link
- `frontend/lib/api.ts` - Added product search API methods

### New Untracked Files
- `PRODUCTION_READINESS_ROADMAP.md` (this file)
- Various analysis/report markdown files

### Recommended Commit
```bash
git add backend/api/products.py backend/api/__init__.py backend/main.py \
        backend/models.py backend/schemas.py \
        frontend/app/products/page.tsx frontend/config/navigation.ts \
        frontend/lib/api.ts

git commit -m "feat: Add product-level search across tender documents

- Add ProductItem model for granular product search
- Create /api/products/search endpoint with filters
- Add product aggregations for price analysis
- Create frontend Products page with search UI
- Add navigation link for Products page"
```

---

## Immediate Action Items

1. **NOW**: Commit and push current changes
2. **NOW**: Run e-Pazar database migration
3. **FIX**: Debug and fix opening_date XPath selectors
4. **FIX**: Fix product name extraction from spec_extractor
5. **TEST**: Reset data and run test scrape (10 per category)
6. **VALIDATE**: Check field fill rates meet targets
7. **DEPLOY**: Start full production scrape

---

## Estimated Timeline

| Phase | Duration | Blocker |
|-------|----------|---------|
| Phase 1: Critical Fixes | 2-4 hours | XPath debugging |
| Phase 2: Data Reset & Test | 1-2 hours | None |
| Phase 3: E-Pazar Test | 1 hour | Migration |
| Phase 4: Full Scrape | 4-8 hours | Fixes validated |
| Phase 5: Verification | 1-2 hours | Scrape complete |

**Total**: ~10-16 hours of active work

---

## Notes

- The spider pagination is working (confirmed earlier)
- Document download is working but needs more testing
- Email service (MailerSend) is configured
- Stripe subscription is ready
- Admin panel is functional

The main blockers are **data quality issues** that must be resolved before we can trust the scraped data for production use.
