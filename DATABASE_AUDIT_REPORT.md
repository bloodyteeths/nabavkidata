# DATABASE LAYER AUDIT REPORT
**Database:** nabavkidata
**Host:** nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com
**Audit Date:** 2025-11-27
**Total Database Size:** 95 MB

---

## 1. TABLE INVENTORY

### Total Tables: 48

| Table Name | Row Count | Size | Status |
|------------|-----------|------|--------|
| mk_companies | 46,994 | 31 MB | Active |
| epazar_items | 10,135 | 2.9 MB | Active |
| documents | 2,298 | 37 MB | Active |
| epazar_documents | 1,908 | 600 KB | Active |
| tenders | 1,778 | 5.2 MB | Active |
| product_items | 1,399 | 1008 KB | Active |
| tender_bidders | 1,003 | 576 KB | Active |
| epazar_tenders | 745 | 1.2 MB | Active |
| contacts | 710 | 608 KB | Active |
| procuring_entities | 560 | 400 KB | Active |
| epazar_offers | 373 | 1.6 MB | Active |
| suppliers | 356 | 456 KB | Active |
| audit_log | 351 | 168 KB | Active |
| scrape_history | 57 | 64 KB | Active |
| epazar_suppliers | 50 | 160 KB | Active |
| user_sessions | 24 | 64 KB | Active |
| users | 20 | 80 KB | Active |
| blocked_emails | 20 | 96 KB | Active |
| cpv_codes | 8 | 32 KB | Active |
| system_config | 2 | 32 KB | Active |
| user_preferences | 2 | 64 KB | Active |
| tender_statistics | 2 | 32 KB | Active |
| alembic_version | 1 | 24 KB | Active |

**Empty Tables (0 rows):**
- suspicious_activities
- tender_amendments
- usage_tracking
- saved_searches
- organizations
- user_behavior
- search_history
- epazar_offer_items
- tender_lots
- blocked_ips
- email_digests
- user_interest_vectors
- fraud_detection
- embeddings
- query_history
- subscriptions
- duplicate_account_detection
- alerts
- payment_fingerprints
- tender_clarifications
- epazar_scraping_jobs
- rate_limits
- notifications
- epazar_awarded_items
- tender_conditions

---

## 2. FIELD FILL RATES

### 2.1 TENDERS Table (1,778 rows)

**Columns with <50% Fill Rate:**

| Column Name | Fill Rate | Non-Null Count | Issues |
|-------------|-----------|----------------|---------|
| performance_guarantee_mkd | 0.00% | 0 | Never populated |
| dossier_id | 0.00% | 0 | Never populated |
| tender_uuid | 0.00% | 0 | Never populated |
| estimated_value_eur | 0.00% | 0 | Never populated |
| award_criteria | 0.00% | 0 | Never populated |
| security_deposit_mkd | 0.00% | 0 | Never populated |
| num_bidders | 0.11% | 2 | Rarely populated |
| actual_value_eur | 0.11% | 2 | Rarely populated |
| closing_date | 16.65% | 296 | Low fill rate |
| winner | 33.30% | 592 | Only for awarded tenders |
| actual_value_mkd | 33.41% | 594 | Only for awarded tenders |
| contract_signing_date | 33.41% | 594 | Only for awarded tenders |
| payment_terms | 44.71% | 795 | Medium fill rate |

**Well-Populated Columns (>95%):**
- tender_id, title, status, source_url, procuring_entity, category, procedure_type (100%)
- publication_date (99.89%)

**Medium Fill Rate (50-95%):**
- estimated_value_mkd (50.34%)
- delivery_location (56.86%)
- contract_duration (61.42%)
- opening_date (64.74%)
- evaluation_method (66.59%)
- cpv_code (66.70%)
- description (66.70%)
- contact_person/email/phone (67.27%)

### 2.2 EPAZAR_TENDERS Table (745 rows)

**Columns with <50% Fill Rate:**

| Column Name | Fill Rate | Non-Null Count | Issues |
|-------------|-----------|----------------|---------|
| cpv_code | 0.00% | 0 | Never populated |
| awarded_value_eur | 0.00% | 0 | Never populated |
| estimated_value_eur | 0.00% | 0 | Never populated |
| estimated_value_mkd | 0.00% | 0 | Never populated |
| award_date | 0.00% | 0 | Never populated |
| contract_duration | 0.00% | 0 | Never populated |
| contract_date | 1.07% | 8 | Rarely populated |
| awarded_value_mkd | 1.48% | 11 | Rarely populated |

**Well-Populated Columns (>95%):**
- All core fields: tender_id, title, source_url, category, contract_number, status, procedure_type, contracting_authority, contracting_authority_id (100%)
- description (98.52%)
- closing_date (98.52%)
- publication_date (99.46%)

### 2.3 EPAZAR_ITEMS Table (10,135 rows)

**Columns with <50% Fill Rate:**

| Column Name | Fill Rate | Non-Null Count | Issues |
|-------------|-----------|----------------|---------|
| cpv_code | 0.00% | 0 | Never populated |
| estimated_total_price_eur | 0.00% | 0 | Never populated |
| estimated_total_price_mkd | 0.00% | 0 | Never populated |
| estimated_unit_price_eur | 0.00% | 0 | Never populated |
| estimated_unit_price_mkd | 0.00% | 0 | Never populated |
| notes | 0.00% | 0 | Never populated |
| delivery_location | 0.00% | 0 | Never populated |
| delivery_date | 0.00% | 0 | Never populated |
| specifications | 0.00% | 0 | Never populated |
| item_code | 0.00% | 0 | Never populated |
| item_description | 24.89% | 2,523 | Low fill rate |

**Well-Populated Columns (100%):**
- line_number, item_name, item_id, quantity, tender_id, unit

### 2.4 DOCUMENTS Table (2,298 rows)

**Fill Rates:**

| Column Name | Fill Rate | Non-Null Count | Status |
|-------------|-----------|----------------|---------|
| specifications_json | 57.01% | 1,310 | Medium |
| mime_type | 77.11% | 1,772 | Good |
| file_size_bytes | 77.46% | 1,780 | Good |
| page_count | 83.59% | 1,921 | Good |
| file_path | 84.42% | 1,940 | Good |
| content_text | 85.12% | 1,956 | Good |
| file_url | 86.21% | 1,981 | Good |
| doc_id, tender_id, file_name, extraction_status, doc_type | 100% | 2,298 | Excellent |

### 2.5 PRODUCT_ITEMS Table (1,399 rows)

**Critical Issues - Most Fields Empty:**

| Column Name | Fill Rate | Non-Null Count | Issues |
|-------------|-----------|----------------|---------|
| manufacturer | 0.00% | 0 | Never populated |
| supplier | 0.00% | 0 | Never populated |
| category | 0.00% | 0 | Never populated |
| cpv_code | 0.00% | 0 | Never populated |
| model | 0.00% | 0 | Never populated |
| unit_price | 0.07% | 1 | Essentially empty |
| quantity | 11.58% | 162 | Very low |

**Well-Populated:**
- specifications (100%)
- id, name (100%)

---

## 3. DATA QUALITY

### 3.1 Data Integrity - EXCELLENT

**No Issues Found:**
- Zero duplicate tender_ids in both tenders and epazar_tenders tables
- Zero orphaned records (all foreign keys valid)
- Zero invalid date sequences (closing before opening)
- Zero negative values in financial fields

### 3.2 Minor Data Quality Issues

**Tenders with actual_value but no winner:** 4 records
- These may be data entry errors or incomplete records

### 3.3 Date Ranges

**TENDERS Table:**
- Publication Date: 2022-12-30 to 2025-11-26 (3 years)
- Opening Date: 2025-11-26 to 2026-01-15
- Closing Date: 2025-11-26 to 2026-01-15

**EPAZAR_TENDERS Table:**
- Publication Date: 2022-03-10 to 2025-11-26 (3+ years)
- Closing Date: 2022-03-14 to 2025-12-01

### 3.4 Document Extraction Status

| Status | Count | Percentage |
|--------|-------|------------|
| success | 1,956 | 85.12% |
| pending | 339 | 14.75% |
| download_failed | 1 | 0.04% |
| failed | 1 | 0.04% |
| skipped_external | 1 | 0.04% |

**Analysis:** Document extraction is working well with 85% success rate. 339 documents are still pending extraction.

---

## 4. SCHEMA ANALYSIS

### 4.1 Foreign Key Constraints (40 total)

**Key Relationships:**

**User-related (11 constraints):**
- alerts, audit_log, email_digests, fraud_detection → users
- notifications, payment_fingerprints, query_history → users
- rate_limits, saved_searches, search_history → users
- subscriptions, suspicious_activities, usage_tracking → users
- user_behavior, user_interest_vectors, user_preferences → users
- user_sessions → users
- duplicate_account_detection (2) → users

**Tender-related (9 constraints):**
- documents → tenders
- embeddings → tenders
- notifications → tenders
- product_items → tenders
- tender_amendments → tenders
- tender_bidders → tenders
- tender_clarifications → tenders
- tender_conditions → tenders
- tender_lots → tenders

**Epazar-related (6 constraints):**
- epazar_documents → epazar_tenders
- epazar_items → epazar_tenders
- epazar_offers → epazar_tenders
- epazar_awarded_items → epazar_tenders, epazar_items, epazar_offers
- epazar_offer_items → epazar_offers, epazar_items

**Other:**
- product_items → documents
- embeddings → documents
- tender_bidders → tender_lots
- notifications → alerts

### 4.2 Indexes (142 total)

**Well-Indexed Tables:**
- tenders: 16 indexes (status, category, opening/closing dates, cpv_code, etc.)
- epazar_tenders: 8 indexes (status, category, dates, search)
- documents: 6 indexes (tender_id, category, hash, content_search)
- users: 10 indexes (email, auth, subscription)
- mk_companies: 7 indexes including trigram for fuzzy search

**Special Indexes:**
- Full-text search: tenders, epazar_tenders, product_items, epazar_items
- Vector search: embeddings (ivfflat for cosine similarity)
- Trigram: mk_companies (for fuzzy name matching)

### 4.3 Missing Indexes - RECOMMENDATIONS

**High Priority:**
1. `CREATE INDEX idx_tenders_publication_date ON tenders(publication_date);`
   - Frequently used for date range queries

2. `CREATE INDEX idx_tenders_estimated_value ON tenders(estimated_value_mkd);`
   - Used for value-based filtering and statistics

3. `CREATE INDEX idx_tenders_actual_value ON tenders(actual_value_mkd);`
   - Used for awarded tender analysis

**Medium Priority:**
4. `CREATE INDEX idx_tender_bidders_company_tax_id ON tender_bidders(company_tax_id);`
   - Would help with company-based queries

5. `CREATE INDEX idx_documents_uploaded_at ON documents(uploaded_at);`
   - Useful for chronological queries

---

## 5. STATISTICS

### 5.1 Tender Status Distribution

**TENDERS Table:**
| Status | Count | Percentage |
|--------|-------|------------|
| open | 1,178 | 66.25% |
| awarded | 594 | 33.41% |
| closed | 6 | 0.34% |

**EPAZAR_TENDERS Table:**
| Status | Count | Percentage |
|--------|-------|------------|
| active | 556 | 74.63% |
| completed | 164 | 22.01% |
| awarded | 14 | 1.88% |
| signed | 11 | 1.48% |

### 5.2 Category Distribution

**TENDERS (by type):**
- Stoki (Goods): 1,035 (58.2%)
- Uslugi (Services): 611 (34.4%)
- Raboti (Works): 132 (7.4%)

### 5.3 Procedure Type Distribution

| Procedure Type | Count | Percentage |
|----------------|-------|------------|
| Poednostavena otvorena postapka | 756 | 42.5% |
| Nabavki od mala vrednost | 639 | 36.0% |
| Otvorena postapka | 347 | 19.5% |
| Oglas za vospostavuvanje na kvalifikacijski sistem | 35 | 2.0% |
| Postapka so pregovaranje so prethodno objavuvanje | 1 | 0.1% |

### 5.4 Top CPV Codes (from tenders)

| CPV Code | Description | Count |
|----------|-------------|-------|
| 50000000-5 | Transport services | 62 |
| 45000000-7 | Construction work | 58 |
| 09000000-3 | Petroleum products, fuel, electricity | 53 |
| 30000000-9 | Office and computing machinery | 33 |
| 30200000-1 | Computer equipment and supplies | 24 |
| 31000000-6 | Electrical machinery, apparatus | 22 |
| 79000000-4 | Business services | 21 |
| 33000000-0 | Medical equipment | 20 |

**Note:** Only 8 CPV codes are defined in the cpv_codes reference table, but 1,186 tenders (66.7%) have CPV codes assigned.

### 5.5 Value Statistics

**TENDERS Table:**
- Estimated Value (MKD):
  - Min: 35,400
  - Max: 495,600,000
  - Average: 7,787,049
- Actual Value (MKD):
  - Min: 348.10
  - Max: 495,600,000
  - Average: 3,020,649

**EPAZAR_TENDERS Table:**
- Awarded Value (MKD): Only 11 records (1.48%)
  - Min: 2,835
  - Max: 91,804
  - Average: 20,594

**TENDER_BIDDERS:**
- Bid Amount (MKD):
  - Min: 348.10
  - Max: 495,600,000
  - Average: 3,344,460
  - All 1,003 bids have values

### 5.6 Entity Distribution

**Unique Counts:**
- Procuring entities: 559
- Contracting authorities (epazar): 106
- Unique supplier companies: 356
- Unique bidder companies: 346
- Epazar suppliers: 50

**Top 5 Procuring Entities (TENDERS):**
1. AD za proizvodstvo na elektricna energija ELEKTRANI NA SEVERNA MAKEDONIJA: 82 tenders
2. JZU Gradska opsta bolnica "8-mi Septemvri" Skopje: 56 tenders
3. Narodna banka na Republika Severna Makedonija: 28 tenders
4. Grad Skopje: 17 tenders
5. JZU Univerzitetska Klinika za nevrohirurgija: 17 tenders

**Top 5 Contracting Authorities (EPAZAR):**
1. Masinski fakultet Skopje: 109 tenders
2. Agencija za razuznavanje na RSM: 88 tenders
3. Naroden pravobranitel: 69 tenders
4. Ministerstvo za digitalna transformacija: 35 tenders
5. Prirodno-matematicki fakultet: 30 tenders

### 5.7 Bidding Statistics

**Winner Analysis:**
- Tenders with bidders: 590
- Total bidders: 1,003
- Bidders marked as winners: 1,003 (100% - likely all are winner records)
- Disqualified bidders: 0

**Top Bidding Companies:**
All top 20 companies have 100% win rate, suggesting the tender_bidders table only stores winning bids, not all bids.

Top companies:
1. Drustvo za promet i uslugi BIOTEK DOO: 27 wins
2. Drustvo za promet i uslugi ALKALOID KONS: 15 wins
3. Trgovsko drustvo SINPEKS DOO: 13 wins

### 5.8 User & System Activity

**Users:**
- Total users: 20
- Registration period: 2025-11-23 to 2025-11-27 (4 days old system)
- Active sessions: 24
- Audit log entries: 351

**Scraping Activity:**
- Total scrape jobs: 57
- Completed: 20 (Average duration: 22 minutes)
- Running/Stuck: 37 (need cleanup)
- Total tenders scraped: 1,776 new + 726 updated
- Date range: 2025-11-26 to 2025-11-27 (very recent)

---

## 6. KEY FINDINGS & RECOMMENDATIONS

### 6.1 Critical Issues

1. **EPAZAR_TENDERS Missing Financial Data**
   - 0% fill rate for estimated_value_mkd/eur
   - 0% fill rate for CPV codes
   - Only 1.48% have awarded values
   - **Impact:** Cannot perform value-based analysis on epazar tenders
   - **Recommendation:** Fix scraper to extract these fields

2. **EPAZAR_ITEMS Missing Pricing**
   - 0% fill rate for all price fields (unit and total)
   - 0% fill rate for CPV codes
   - **Impact:** Cannot calculate tender values from items
   - **Recommendation:** Fix scraper to extract pricing information

3. **PRODUCT_ITEMS Severely Underpopulated**
   - 0% fill rate for category, cpv_code, manufacturer, model, supplier
   - 0.07% fill rate for unit_price
   - 11.58% fill rate for quantity
   - **Impact:** Limited usefulness for product analysis
   - **Recommendation:** Improve extraction algorithms or mark as low-priority feature

4. **EUR Currency Conversion Not Working**
   - 0% fill rate for estimated_value_eur and actual_value_eur in tenders
   - 0% fill rate for all EUR fields in epazar
   - **Recommendation:** Implement currency conversion logic

5. **Stuck Scraping Jobs**
   - 37 jobs marked as "running" but likely stuck
   - **Recommendation:** Implement timeout/cleanup mechanism

### 6.2 Data Quality Strengths

1. **Excellent Referential Integrity**
   - Zero orphaned records
   - Zero duplicate primary keys
   - All foreign keys valid

2. **Good Core Data Population**
   - 100% fill rate for essential fields (titles, IDs, dates)
   - 85% document extraction success rate
   - No invalid date sequences or negative values

3. **Comprehensive Indexing**
   - 142 indexes across all tables
   - Full-text search enabled
   - Vector search for similarity

### 6.3 Performance Optimization Recommendations

**Add Missing Indexes:**
```sql
CREATE INDEX idx_tenders_publication_date ON tenders(publication_date);
CREATE INDEX idx_tenders_estimated_value ON tenders(estimated_value_mkd);
CREATE INDEX idx_tenders_actual_value ON tenders(actual_value_mkd);
```

**Cleanup Recommendations:**
```sql
-- Mark stuck scraping jobs as failed
UPDATE scrape_history
SET status = 'failed',
    error_message = 'Timeout - marked as failed by cleanup job',
    completed_at = NOW()
WHERE status = 'running'
AND started_at < NOW() - INTERVAL '2 hours';
```

### 6.4 Scraper Fixes Needed

**Priority 1 - Critical:**
1. Fix epazar_tenders scraper to extract:
   - estimated_value_mkd
   - CPV codes
   - Contract values

2. Fix epazar_items scraper to extract:
   - Unit prices
   - Total prices
   - CPV codes

**Priority 2 - Important:**
3. Implement EUR currency conversion
4. Add scraping job timeout mechanism
5. Improve product_items extraction quality

### 6.5 Schema Improvements

**Consider Adding:**
1. Composite indexes for common query patterns:
   ```sql
   CREATE INDEX idx_tenders_status_date ON tenders(status, publication_date);
   CREATE INDEX idx_epazar_tenders_status_date ON epazar_tenders(status, closing_date);
   ```

2. Partial indexes for active records:
   ```sql
   CREATE INDEX idx_tenders_open ON tenders(publication_date)
   WHERE status = 'open';
   ```

### 6.6 Data Completeness Summary

**Excellent (>90% fill rate):**
- Core tender information (IDs, titles, entities, statuses)
- Document metadata
- Audit and user data

**Good (70-90% fill rate):**
- Document content extraction
- Tender dates
- Contact information

**Poor (<50% fill rate):**
- Financial data in epazar tables
- Product specifications
- CPV codes in epazar
- EUR currency values
- Contract signing details

---

## 7. CONCLUSION

The database is **structurally sound** with excellent referential integrity and comprehensive indexing. However, there are **critical data population issues** in the epazar scraping pipeline that prevent meaningful financial analysis of those tenders.

**Overall Health Score: 70/100**
- Schema Design: 95/100
- Data Integrity: 100/100
- Data Completeness: 55/100
- Indexing: 85/100
- Performance: 75/100

**Immediate Actions Required:**
1. Fix epazar scrapers to capture financial data
2. Implement EUR currency conversion
3. Add missing performance indexes
4. Clean up stuck scraping jobs
5. Improve or deprecate product_items extraction
