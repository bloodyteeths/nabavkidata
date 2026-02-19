# PHASE 0.0: Document Format & Quality Audit

**Generated:** 2025-12-01
**Status:** COMPLETE
**Author:** AI Data Agent

---

## Executive Summary

Comprehensive audit of **17,902 documents** across two systems (e-nabavki main + ePazar). The audit reveals significant extraction gaps and clear priorities for processing.

### Key Findings at a Glance

| Metric | Value | Status |
|--------|-------|--------|
| **Total Documents** | 17,902 | - |
| **Successfully Extracted** | 5,733 (32%) | ⚠️ LOW |
| **Pending Extraction** | 6,765 (38%) | Action needed |
| **Failed Extraction** | 2,589 (14%) | Retry needed |
| **Unusable (OTHER/Unknown)** | 6,009 (34%) | ❌ CRITICAL GAP |
| **Estimated Usable** | ~9,000 (50%) | After cleanup |

---

## 1. Document Sources

### Main Documents Table (e-nabavki)
- **Total:** 15,164 documents
- **With extracted text:** 5,689 (37.5%)
- **Without text:** 9,475 (62.5%)

### ePazar Documents Table
- **Total:** 2,738 documents
- **With extracted text:** 5 (0.2%)
- **Without text:** 2,733 (99.8%)

**Combined Total:** 17,902 documents

---

## 2. File Format Distribution (Main Documents)

| File Type | Count | % of Total | Extraction Rate | Avg Chars | Notes |
|-----------|-------|------------|-----------------|-----------|-------|
| **PDF** | 8,099 | 53.4% | 62.4% | 7,371 | Primary format |
| **DOCX** | 865 | 5.7% | 65.1% | 4,079 | Good extraction |
| **DOC** | 91 | 0.6% | 14.3% | 1,846 | Legacy format issues |
| **XLSX** | 42 | 0.3% | 43.0% | 4,901 | Table-rich |
| **XLS** | 58 | 0.4% | 43.0% | 4,901 | Legacy Excel |
| **OTHER** | 6,009 | 39.6% | 0.0% | 0 | **CRITICAL GAP** |

### Analysis of "OTHER" Documents (6,009)
These are documents with:
- `file_name = 'DownloadContractFile'` or similar generic names
- Missing file extensions
- URLs that don't indicate file type

**Action Required:** Need to detect actual file type by downloading and inspecting headers/magic bytes.

---

## 3. Extraction Status Breakdown

| Status | Count | % | Action |
|--------|-------|---|--------|
| **pending** | 6,431 | 42.4% | Run extraction pipeline |
| **success** | 5,728 | 37.8% | Done |
| **failed** | 2,585 | 17.1% | Retry with fallback |
| **auth_required** | 366 | 2.4% | Fix URLs (done for 561) |
| **skipped_external** | 36 | 0.2% | Bank docs - skip |
| **download_failed** | 16 | 0.1% | Retry download |
| **download_timeout** | 1 | 0.01% | Retry |
| **download_corrupted** | 1 | 0.01% | Skip |

---

## 4. PDF Analysis (8,099 documents)

### Text Extraction Quality

| Category | Count | % of PDFs | Avg Pages | Assessment |
|----------|-------|-----------|-----------|------------|
| **No text (<100 chars)** | 3,043 | 37.6% | 0.1 | Likely OCR needed or corrupt |
| **Full text (>10k chars)** | 1,424 | 17.6% | 21.6 | Rich content |
| **Medium text (2k-10k)** | 1,846 | 22.8% | 5.7 | Good content |
| **Light text (500-2k)** | 1,664 | 20.5% | 2.8 | Moderate content |
| **Minimal text (100-500)** | 122 | 1.5% | 3.7 | Possible OCR needed |

### Page Count Distribution

| Page Range | Count | Total Pages | Notes |
|------------|-------|-------------|-------|
| 1-5 pages | 3,248 | 9,692 | Most common - quick processing |
| 0 pages | 2,617 | 0 | Metadata issue or corrupt |
| 6-20 pages | 1,705 | 19,079 | Medium documents |
| 21-50 pages | 318 | 9,023 | Larger specs |
| 50+ pages | 80 | 8,619 | Large documents |
| Unknown | 131 | - | Need page count |

**Total PDF Pages:** ~46,413 pages

### Potential Scanned PDFs (Need OCR)
- **Count:** 135 documents
- **Criteria:** >5 pages AND <500 chars extracted
- **OCR Cost Impact:** ~135 documents × ~10 pages avg = ~1,350 pages

### PDF Extraction Success by Status

| Status | Count | % of PDFs |
|--------|-------|-----------|
| success | 5,152 | 63.6% |
| failed | 2,536 | 31.3% |
| auth_required | 316 | 3.9% |
| pending | 58 | 0.7% |
| skipped_external | 36 | 0.4% |

---

## 5. Word Document Analysis (956 documents)

| Format | Count | Success | Pending | Failed | Auth Required |
|--------|-------|---------|---------|--------|---------------|
| DOCX | 865 | 539 (62%) | 334 | 45 | 23 |
| DOC | 91 | 13 (14%) | 0 | 0 | 0 |

**Issues:**
- DOC (old format) has very low extraction rate (14.3%)
- 334 DOCX files still pending
- Need python-docx for DOCX, antiword/textract for DOC

---

## 6. Excel Document Analysis (100 documents)

| Format | Count | Success | Pending | Failed | Notes |
|--------|-------|---------|---------|--------|-------|
| XLSX | 42 | ~18 | ~20 | ~4 | Modern format |
| XLS | 58 | ~19 | ~33 | ~6 | Legacy format |

**Value:** Excel files often contain item/pricing tables - HIGH PRIORITY for extraction.

---

## 7. Document Categories

| Category | Count | % | Value for Extraction |
|----------|-------|---|---------------------|
| **contract** | 9,623 | 63.5% | HIGH - prices, terms |
| **bid** | 2,854 | 18.8% | CRITICAL - item prices |
| **other** | 1,358 | 9.0% | LOW |
| **technical_specs** | 646 | 4.3% | HIGH - specifications |
| **tender_docs** | 633 | 4.2% | MEDIUM - requirements |
| **document** | 37 | 0.2% | Unknown |
| **award_decision** | 5 | 0.03% | HIGH - winner info |

**Priority for Item/Price Extraction:**
1. bid (2,854) - CRITICAL
2. contract (9,623) - HIGH
3. technical_specs (646) - HIGH
4. tender_docs (633) - MEDIUM

---

## 8. ePazar Documents (2,738)

| Metric | Value |
|--------|-------|
| Total documents | 2,738 |
| With text extracted | 5 (0.2%) |
| Average chars | 5 |
| Extraction rate | **0.2%** |

**Status:** CRITICAL - Almost no ePazar documents have been extracted.

**Action Required:** Run full extraction on all 2,738 ePazar documents.

---

## 9. External/Skip Documents

| Type | Count | Action |
|------|-------|--------|
| **ohridskabanka.mk** | 36 | Skip (bank guarantees) |
| **Other external** | 0 | None identified |

---

## 10. Tables Detection

### Current State
| Metric | Value |
|--------|-------|
| Tables extracted | 66 |
| Documents with tables | 9 |

**Gap:** Only 9 documents have had tables extracted, but thousands contain tables.

### Estimated Tables in Documents
Based on document types and page counts:
- **Bid documents (2,854)**: ~80% likely have pricing tables = ~2,283 documents
- **Contracts (9,623)**: ~30% likely have item tables = ~2,887 documents
- **Technical specs (646)**: ~90% likely have spec tables = ~581 documents

**Estimated Total Documents with Tables:** ~5,751 documents
**Current Coverage:** 9/5,751 = **0.16%**

---

## 11. Extraction Feasibility Assessment

### By File Type

| Type | Total | Feasible | OCR Needed | Skip | Success Estimate |
|------|-------|----------|------------|------|------------------|
| PDF | 8,099 | 7,900 | ~135 | ~64 | 75-85% |
| DOCX | 865 | 865 | 0 | 0 | 90%+ |
| DOC | 91 | 50 | 0 | 41 | 50% (legacy) |
| XLSX | 42 | 42 | 0 | 0 | 85%+ |
| XLS | 58 | 58 | 0 | 0 | 80% |
| OTHER | 6,009 | ~3,000 | ? | ~3,000 | 50% (need detection) |

### Estimated Usable Documents After Filtering

| Category | Count | Notes |
|----------|-------|-------|
| **PDF (text-rich)** | ~5,000 | Already have good extraction |
| **PDF (OCR needed)** | ~135 | Will extract after OCR |
| **PDF (failed retry)** | ~1,500 | Estimate 60% success on retry |
| **Word documents** | ~850 | High success rate |
| **Excel documents** | ~90 | High value for tables |
| **OTHER (unknown)** | ~3,000 | Need file type detection |
| **ePazar** | ~2,500 | After extraction |
| **TOTAL USABLE** | **~13,075** | 73% of all documents |

---

## 12. Risks & Blockers

### Identified Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OTHER files unprocessable | Medium | HIGH | Detect file types, retry |
| Scanned PDFs need OCR | Low | Medium | Budget for OCR service |
| DOC format failures | High | Low | Convert to PDF/DOCX |
| ePazar timeout issues | Medium | Medium | Rate limiting, retries |
| Table detection failures | Medium | HIGH | LLM vision fallback |

### Blockers

1. **6,009 "OTHER" documents** - Need file type detection before processing
2. **2,733 ePazar documents** - Zero extraction, need immediate processing
3. **2,585 failed extractions** - Need retry with better error handling
4. **135+ scanned PDFs** - Need OCR service decision

---

## 13. Recommendations

### Immediate Actions (This Week)

1. **Run extraction on 6,431 pending documents**
   - Expected yield: ~4,000 with usable text

2. **Extract all 2,738 ePazar documents**
   - Estimated time: ~45 minutes
   - Script ready: `scripts/extract_epazar_documents.py`

3. **Detect file types for 6,009 "OTHER" documents**
   - Download sample, check magic bytes
   - Update file_name with correct extension

4. **Retry 2,585 failed extractions**
   - Use fallback engines
   - Expected additional yield: ~1,500

### Medium-Term Actions (This Month)

5. **Implement OCR for ~135 scanned PDFs**
   - Evaluate: Tesseract (free), Google Vision, AWS Textract
   - Budget impact: See Phase 0.1

6. **Run table detection on all extracted documents**
   - Estimate: 5,751 documents have tables
   - Current: Only 9 processed

7. **Convert DOC to DOCX for better extraction**
   - 91 documents, low volume

---

## 14. Success Metrics

### Phase 0.0 Completion Criteria

- [x] Document format breakdown complete
- [x] Extraction status analyzed
- [x] OCR requirement estimated (~135 PDFs)
- [x] Table presence estimated (~5,751 docs)
- [x] Usable document count estimated (~13,075)
- [x] Risks and blockers identified
- [x] Recommendations provided

### Target State After Remediation

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Text extraction rate | 32% | 75% | +43% |
| ePazar extraction | 0.2% | 90% | +90% |
| Table detection coverage | 0.16% | 50% | +50% |
| Failed/pending reduced | 60% | 15% | -45% |

---

## 15. Appendix: Sample Problem Documents

### Sample "OTHER" Documents (Need File Type Detection)
```
file_name: DownloadContractFile
file_url: (empty or generic)
extraction_status: pending
```
**Count:** 5,986 pending with this pattern

### Sample Failed PDFs (Need Retry)
```
file_name: *.pdf
extraction_status: failed
content_text: NULL
page_count: varies
```
**Count:** 2,536

### Sample ePazar Documents (Urgent)
```
table: epazar_documents
total: 2,738
extracted: 5
pending: 2,733
```

---

## Status: DONE

**Phase 0.0 Document Format & Quality Audit is COMPLETE.**

Next: Proceed to Phase 0.1 (Extraction Cost & Compute Plan) with this audit data.
