# PHASE 0.1: Production Database State Audit Report

**Audit Date:** 2025-11-25
**Database:** nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com
**Schema Version:** 001

---

## Executive Summary

### Overall Health: CAUTION - Multiple Critical Issues Identified

**Quick Stats:**
- Total Tenders: 214
- Total Users: 17
- Active Scraping Jobs: 38 running, 26 completed
- Tables Present: 37/37 (100%)

**CRITICAL ISSUES IDENTIFIED:**
1. Product items contain garbage data (extracted table headers, not actual products)
2. 95% of tenders missing detailed descriptions
3. 94% of tenders missing CPV codes
4. All E-Pazar tables are empty (0 data despite scraping infrastructure)
5. 38 scraping jobs stuck in "running" status (never completed)
6. Opening dates completely missing (0% fill rate)

---

## 1. All Tables Inventory

### Tables Present: 37 Tables

| Table Name | Row Count | Status |
|-----------|-----------|---------|
| **Core Tender Data** |
| tenders | 214 | Active |
| documents | 15 | Low volume |
| product_items | 62 | Data quality issue |
| tender_bidders | 16 | Low volume |
| tender_lots | 0 | Empty |
| tender_amendments | 0 | Empty |
| tender_clarifications | 0 | Empty |
| **Entity Management** |
| procuring_entities | 158 | Active |
| suppliers | 11 | Low volume |
| contacts | 22 | Active |
| organizations | 0 | Empty |
| **E-Pazar Tables (All Empty)** |
| epazar_tenders | 0 | CRITICAL: Empty |
| epazar_items | 0 | CRITICAL: Empty |
| epazar_offers | 0 | CRITICAL: Empty |
| epazar_offer_items | 0 | CRITICAL: Empty |
| epazar_awarded_items | 0 | CRITICAL: Empty |
| epazar_documents | 0 | CRITICAL: Empty |
| epazar_suppliers | 0 | CRITICAL: Empty |
| epazar_scraping_jobs | 0 | CRITICAL: Empty |
| **User & Subscription** |
| users | 17 | Active |
| subscriptions | 0 | Empty |
| alerts | 0 | Empty |
| notifications | 0 | Empty |
| **Search & AI** |
| embeddings | 3 | Low volume |
| query_history | 0 | Empty |
| **Operations & Security** |
| scrape_history | 63 | Active |
| audit_log | 124 | Active |
| blocked_emails | 20 | Active |
| blocked_ips | 0 | Empty |
| duplicate_account_detection | 0 | Empty |
| fraud_detection | 0 | Empty |
| payment_fingerprints | 0 | Empty |
| rate_limits | 0 | Empty |
| suspicious_activities | 0 | Empty |
| usage_tracking | 0 | Empty |
| **System** |
| system_config | 2 | Active |
| alembic_version | 1 | Active |

### Missing Tables: NONE
All expected tables are present in the schema.

---

## 2. Tenders Table Field Fill Rates

### Overall Statistics
- **Total Tenders:** 214
- **Date Range:** 2025-11-19 to 2025-11-25 (6 days of data)
- **Source Categories:** active (149), cancelled (38), awarded (27)

### Field Fill Rates

| Field | Total Count | Non-Empty Count | Fill Rate | Status |
|-------|-------------|-----------------|-----------|---------|
| **Core Identifiers** |
| tender_id | 214 | 214 | 100.00% | ✓ Excellent |
| title | 214 | 214 | 100.00% | ✓ Excellent |
| procuring_entity | 214 | 214 | 100.00% | ✓ Excellent |
| source_url | 214 | 214 | 100.00% | ✓ Excellent |
| source_category | 214 | 214 | 100.00% | ✓ Excellent |
| status | 214 | 214 | 100.00% | ✓ Excellent |
| **Dates** |
| publication_date | 149 | 149 | 69.63% | ⚠ Fair |
| closing_date | 149 | 149 | 69.63% | ⚠ Fair |
| opening_date | 0 | 0 | 0.00% | ✗ CRITICAL |
| **Descriptive Data** |
| description | 11 | 11 | 5.14% | ✗ CRITICAL |
| cpv_code | 11 | 11 | 5.14% | ✗ CRITICAL |
| procedure_type | 176 | 176 | 82.24% | ✓ Good |
| winner | 11 | 11 | 5.14% | ⚠ Expected (only awarded) |
| **Financial Data** |
| estimated_value_mkd | 57 | 57 | 26.64% | ✗ Poor |
| estimated_value_eur | 0 | 0 | 0.00% | ✗ Missing |
| actual_value_mkd | 27 | 27 | 12.62% | ⚠ Expected (only awarded) |
| actual_value_eur | 0 | 0 | 0.00% | ✗ Missing |
| **Contact Information** |
| contact_person | 214 | 214 | 100.00% | ✓ Excellent |
| contact_email | 11 | 11 | 5.14% | ✗ CRITICAL |
| contact_phone | 11 | 11 | 5.14% | ✗ CRITICAL |
| **Metadata** |
| num_bidders | 214 | 214 | 100.00% | ✓ Present (avg: 0.11) |
| has_lots | 214 | 214 | 100.00% | ✓ Present (6 true) |
| num_lots | 214 | 214 | 100.00% | ✓ Present (all 0) |

### Procedure Type Distribution
- **Набавки од мала вредност** (Small Value Procurement): 96 tenders (44.8%)
- **Поедноставена отворена постапка** (Simplified Open Procedure): 59 tenders (27.6%)
- **Отворена постапка** (Open Procedure): 21 tenders (9.8%)
- **No procedure type:** 38 tenders (17.8%)

### Status Distribution
- **open:** 149 tenders (69.6%)
- **cancelled:** 38 tenders (17.8%)
- **awarded:** 27 tenders (12.6%)

### Critical Finding: Data Quality Issues

**PROBLEM:** Most tenders have very sparse data - only basic fields populated:
- Only 5% have descriptions
- Only 5% have CPV codes
- Only 5% have contact emails/phones
- 0% have opening dates
- 0% have EUR currency values

**Root Cause Analysis:** Appears that only "awarded" tenders (27/214 = 12.6%) have detailed extraction, while "active" and "cancelled" tenders only get basic metadata scraped.

---

## 3. Documents Table Analysis

### Summary Statistics
- **Total Documents:** 15
- **Tenders with Documents:** 5 unique tenders
- **Average Documents per Tender:** 3 documents

### Extraction Status Breakdown
| Status | Count | Percentage |
|--------|-------|------------|
| success | 5 | 33.3% |
| failed | 5 | 33.3% |
| ocr_required | 5 | 33.3% |
| pending | 0 | 0% |

### Document Types
- **document:** 15 (100%)

### Sample Documents
Most common pattern:
- "Листа на овластени потписници на електронски гаранции 2018.pdf" - FAILED status
- "document_[hash].pdf" - Mixed success/ocr_required

**CRITICAL ISSUE:** 66.7% of documents either failed extraction or require OCR but haven't been processed.

---

## 4. Product Items Quality Check

### Statistics
- **Total Product Items:** 62
- **Tenders with Products:** 2 unique tenders
- **Average Products per Tender:** 31 items
- **Extraction Confidence:** 100% (all items have 1.00 confidence)

### Sample Product Names (CRITICAL DATA QUALITY ISSUE)

**PROBLEM: Product items contain garbage data, not actual products!**

Examples of what's stored as "products":
1. "I.4 Со поднесување на оваа понуда, во целост ги прифаќаме условите предвидени во тендерската документација"
2. "I.3 Нашата понуда важи за период утврден во тендерската документација"
3. "I.2 Се согласуваме со начинот и рокот на плаќање утврден во тендерската документација"
4. "266,00" (just a number)
5. "540,00" (just a number)
6. "700,00" (just a number)

**Root Cause:** The PDF extraction is picking up:
- Form field labels and legal text
- Random numbers from tables
- Headers and footers
- NOT actual product/item specifications

**Impact:** The product_items table is completely unusable for its intended purpose of tracking what items are being procured.

**Unit Field Issues:** Units contain garbage like "Со", "Нашата", "Се", "Го" (parts of the text, not measurement units)

**Missing Data:**
- No unit_price values
- No total_price values
- No meaningful product names

**Recommendation:** Complete rewrite of PDF extraction logic needed, or switch to structured data source.

---

## 5. Tender Bidders Analysis

### Statistics
- **Total Bidders:** 16
- **Tenders with Bidders:** 11
- **Unique Companies:** 11
- **Average Bidders per Tender:** 1.45

### Bidder Distribution
Most tenders have 1 bidder (7 tenders), some have 2 bidders (4 tenders).

### Sample Bidder Data
All bidders shown are marked as winners (is_winner = true):
- "Друштво за промет и услуги АВИЦЕНА ДОО експорт-импорт Скопје" - 390,000.00 MKD
- "Друштво за производство и промет ТОСАМА ТРЕЈД ДОО Марино, Илинден" - 8,700.00 MKD
- "Друштво за промет и услуги АЛКАЛОИД КОНС увоз извоз ДООЕЛ Скопје" - 6,504,960.00 MKD

**Data Quality:** Good - Company names are complete and accurate, bid amounts present.

**Issue:** Low coverage - only 11/214 tenders (5.1%) have bidder information.

---

## 6. Tender Lots Analysis

### Statistics
- **Total Lots:** 0 (EMPTY TABLE)
- **Lots per Tender:** N/A

**CRITICAL:** Despite the tenders table showing 6 tenders with `has_lots = true`, the tender_lots table is completely empty. This indicates a broken relationship or missing extraction logic for lot-based tenders.

---

## 7. E-Pazar Tables Check

**STATUS: ALL EMPTY - CRITICAL ISSUE**

| Table | Row Count | Expected Data |
|-------|-----------|---------------|
| epazar_tenders | 0 | E-Pazar tender listings |
| epazar_items | 0 | Items from E-Pazar tenders |
| epazar_offers | 0 | Supplier offers |
| epazar_offer_items | 0 | Individual offer items |
| epazar_awarded_items | 0 | Awarded items |
| epazar_documents | 0 | E-Pazar documents |
| epazar_suppliers | 0 | E-Pazar supplier registry |
| epazar_scraping_jobs | 0 | E-Pazar scraping job history |

**Analysis:**
- Schema exists and is well-designed
- Foreign keys and indexes properly configured
- BUT: No data whatsoever
- No scraping jobs logged in epazar_scraping_jobs

**Possible Causes:**
1. E-Pazar scraping not yet implemented
2. E-Pazar scraper exists but never run
3. E-Pazar scraper runs but fails silently
4. E-Pazar integrated into main tenders table instead

**Impact:** If E-Pazar is a required data source, this is a blocking issue for production.

---

## 8. Users & Alerts

### Users Statistics
- **Total Users:** 17
- **Verified Users:** 4 (23.5%)
- **Admin Users:** 1
- **Subscription Tiers:**
  - Free: 15 users (88.2%)
  - Enterprise: 1 user (5.9%)
  - Standard: 0 users
  - Pro: 0 users

### Sample Users
Most recent registrations:
- test-enterprise@nabavkidata.com (enterprise, verified)
- test@sara.com (free, verified)
- test@test.mk (free, verified)
- email@test.com (free, NOT verified)

### Alerts
- **Total Search Alerts:** 0
- **Notifications:** 0

**Issue:** No users have set up search alerts, suggesting:
1. Feature not promoted/visible
2. Feature not working
3. Early stage, users haven't engaged yet

---

## 9. Scraping Jobs Analysis

### Overall Statistics
- **Total Jobs:** 63
- **Successful:** 0 (0%)
- **Failed:** 0 (0%)
- **Running:** 38 (60.3%)
- **Completed:** 25 (39.7%)

**CRITICAL ISSUE:** 38 jobs stuck in "running" status, many started hours or days ago and never completed.

### Jobs by Category
| Category | Status | Jobs | New Tenders | Errors | Avg Duration |
|----------|--------|------|-------------|--------|--------------|
| active | completed | 21 | 1,820 | 8 | 781 sec (13 min) |
| active | running | 23 | 0 | 0 | - |
| awarded | completed | 4 | 20 | 5 | 61 sec |
| awarded | running | 11 | 0 | 0 | - |
| cancelled | completed | 1 | 9 | 0 | 46 sec |
| cancelled | running | 3 | 0 | 0 | - |

### Recent Scraping Activity (Last 15 Jobs)

**Most Recent Successful Scrapes:**
- **Active tenders:** 901 new tenders scraped (2025-11-25 15:13 - 17:30, 2.3 hours, 1 error)
- **Active tenders:** 885 new tenders scraped (2025-11-25 14:13 - 16:12, 2 hours, 5 errors)
- **Awarded tenders:** 3 new tenders (69 seconds, 1 error)
- **Awarded tenders:** 8 new tenders (73 seconds, 1 error)
- **Cancelled tenders:** 9 new tenders (46 seconds, 0 errors)

### Critical Findings

1. **Zombie Jobs:** 38 jobs never completed, oldest from hours ago, blocking resources
2. **High Error Rate:** Even completed jobs show errors (1-5 errors per job)
3. **Long Durations:** Active tender scraping takes 13+ minutes on average
4. **Total Tenders Scraped:** 1,849 tenders discovered across all completed jobs
5. **Database Has Only 214:** Massive discrepancy (1,849 found vs 214 stored = 88.4% missing!)

**WHERE ARE THE MISSING 1,635 TENDERS?**

Possible explanations:
1. Deduplication removing most tenders
2. Validation failures rejecting tenders
3. Scraper finding duplicates across pages
4. Database purging old tenders
5. Bug in insert logic

**Action Required:** Investigate scraping logic to find why so few tenders make it to the database.

---

## 10. Supporting Tables Analysis

### Procuring Entities
- **Total:** 158 unique entities
- **With Tax ID:** 0 (0%)
- **With Email:** 0 (0%)
- **Top Entity:** "Електрани на Северна Македонија" (8 tenders)

**Data Quality Issue:** No tax IDs or contact emails extracted for any entity.

### Suppliers
- **Total:** 11 unique suppliers
- **Total Wins:** 11 (each supplier won 1 tender)
- **Total Bids:** 0 tracked
- **Win Rate:** Not calculated (no bid data)

**Issue:** Suppliers table only tracks winners, not all bidders. Should be populated from tender_bidders.

### Contacts
- **Total:** 22 contacts
- **Unique Emails:** 11
- **All Status:** "new" (none processed)
- **All Type:** "procuring_entity"

Sample contacts extracted from awarded tenders, all with valid emails.

### Embeddings
- **Total:** 3 embeddings
- **Documents with Embeddings:** 0 linked to documents

**Issue:** Orphaned embeddings - not linked to any document.

### Blocked Emails
- **Total:** 20 blocked addresses

### Audit Log
- **Total Entries:** 124 audit events

---

## Critical Issues Summary (Red Flags Blocking Production)

### SEVERITY: CRITICAL (Must Fix Before Production)

1. **Product Items Contain Garbage Data**
   - Impact: Core functionality broken
   - Product extraction pulling form text instead of actual items
   - 100% of product data is unusable
   - Action: Rewrite PDF extraction or use structured data source

2. **Missing 1,635 Tenders (88% Data Loss)**
   - Impact: Massive data loss
   - Scraper reports finding 1,849 tenders
   - Database only has 214 tenders
   - Action: Debug tender insertion/validation logic

3. **38 Zombie Scraping Jobs**
   - Impact: Resource leak, unclear system state
   - 38 jobs stuck in "running" status forever
   - May be blocking new scrapes or consuming resources
   - Action: Implement job timeout/cleanup logic

4. **All E-Pazar Tables Empty**
   - Impact: Missing entire data source
   - 8 tables exist but have zero data
   - If E-Pazar is required, this blocks production
   - Action: Implement E-Pazar scraping or remove tables

5. **95% of Tenders Missing Detailed Data**
   - Impact: Poor user experience
   - Only awarded tenders get full extraction
   - Active/cancelled tenders missing: description, CPV codes, contacts
   - Action: Implement full extraction for all tender types

### SEVERITY: HIGH (Fix Soon)

6. **Opening Dates 100% Missing**
   - Impact: Can't show tender timelines properly
   - Action: Add opening_date extraction logic

7. **EUR Values 100% Missing**
   - Impact: International users can't see EUR amounts
   - Action: Add currency conversion or extract EUR from source

8. **Contact Information 95% Missing**
   - Impact: Users can't contact procuring entities
   - Only 11/214 tenders have contact email/phone
   - Action: Extract contacts for all tenders

9. **Tender Lots Table Empty Despite has_lots=true**
   - Impact: Broken data relationship
   - 6 tenders marked as having lots, but no lots in database
   - Action: Implement lot extraction or fix has_lots flag

### SEVERITY: MEDIUM (Nice to Have)

10. **No Search Alerts Created**
    - Impact: Feature unused
    - Action: Promote feature or investigate if broken

11. **Low Document Extraction Success Rate**
    - 66% of documents failed or need OCR
    - Action: Improve document processing pipeline

12. **No Tax IDs for Procuring Entities**
    - Impact: Can't uniquely identify entities
    - Action: Add tax ID extraction

---

## Recommendations

### Immediate Actions (Before Production Launch)

1. **Fix Product Extraction**
   - Review PDF parsing logic in `/Users/tamsar/Downloads/nabavkidata/scraper/`
   - Implement proper table detection
   - Validate extracted items before insertion
   - Add data quality checks

2. **Debug Tender Data Loss**
   - Add logging to track tender insertion
   - Check validation rules
   - Review deduplication logic
   - Find where 1,635 tenders are being filtered out

3. **Clean Up Zombie Jobs**
   - Add cron job to timeout stale scraping jobs
   - Implement job heartbeat/health checks
   - Mark old "running" jobs as "failed" or "timeout"

4. **Complete Tender Data Extraction**
   - Extract detailed fields for ALL tender types (not just awarded)
   - Prioritize: description, CPV codes, opening_date, contact info

5. **E-Pazar Decision**
   - If needed: Implement scraping immediately
   - If not needed: Remove tables from schema
   - Document decision

### Medium-Term Improvements

6. Implement lot extraction for multi-lot tenders
7. Add EUR currency conversion
8. Extract procuring entity tax IDs
9. Improve document OCR pipeline
10. Promote search alerts feature to users

### Data Quality Monitoring

- Set up automated daily data quality reports
- Track fill rates for critical fields
- Monitor scraping job completion rates
- Alert on data anomalies (like 88% data loss!)

---

## Conclusion

The database infrastructure is well-designed with proper schemas, indexes, and relationships. However, **critical data quality and extraction issues** prevent this from being production-ready:

- Only 12% of data is fully extracted (awarded tenders)
- 88% data loss between scraping and database
- Product extraction completely broken
- Multiple subsystems empty or non-functional

**Estimated Time to Production-Ready:** 2-3 weeks of focused development to address critical issues.

**Next Steps:** Prioritize fixing product extraction and tender data loss before proceeding with any feature development.
