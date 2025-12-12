# PHASE A.0: Bad Document Detection

**Generated:** 2025-12-01
**Status:** COMPLETE
**Author:** AI Agent

---

## Executive Summary

Identified **752 documents** to mark as `skip_unusable` and **458 duplicates** to flag. Additionally, **6,007 documents** need file type detection before processing.

### Bad Document Summary

| Category | Count | Action | Status |
|----------|-------|--------|--------|
| Empty content (0 chars) | 83 | Mark skip_empty | NEW |
| Very short (<100 chars) | 14 | Mark skip_minimal | NEW |
| External bank (ohridskabanka) | 36 | Mark skip_external_bank | Already skipped |
| Bank guarantee content | 154 | Mark skip_bank_guarantee | NEW |
| Duplicate content | 458 | Mark as duplicate | NEW |
| Generic file names | 6,007 | Need type detection | PENDING |
| **TOTAL TO SKIP** | **745** | Various | - |

---

## 1. Document Content Analysis

### 1.1 Content Length Distribution

| Content Status | Count | % | Assessment |
|----------------|-------|---|------------|
| NULL content | 6,857 | 45.2% | Not yet extracted |
| Has content (>100) | 5,675 | 37.4% | Usable |
| Empty (0 chars) | 2,618 | 17.3% | May need retry or skip |
| Short (50-100) | 14 | 0.1% | Skip - too little data |

### 1.2 Already Extracted but Empty

| Issue | Count | Recommended Action |
|-------|-------|-------------------|
| success status but NULL/empty content | 83 | Mark skip_empty |
| success status but <100 chars | 14 | Mark skip_minimal |
| **TOTAL** | **97** | Skip from extraction |

---

## 2. External/Bank Documents

### 2.1 ohridskabanka.mk Documents

**Already Identified and Skipped:** 36 documents

These are bank guarantee documents hosted on external bank server. Not relevant for tender item/price extraction.

**Status:** Already `skipped_external` ✅

### 2.2 Bank Guarantee Content

**Documents containing bank guarantee patterns:** 154

Pattern detection:
```sql
content_text ILIKE '%банкарска гаранција%'
OR content_text ILIKE '%bank guarantee%'
```

**Status:** Should be marked `skip_bank_guarantee`

---

## 3. Duplicate Documents

### 3.1 Duplicate Content Analysis

| Metric | Value |
|--------|-------|
| Documents with content | 5,675 |
| Unique content (MD5) | 5,217 |
| **Duplicate copies** | **458** |

### 3.2 Top Duplicate Groups

| MD5 Hash | Copies | Notes |
|----------|--------|-------|
| d18e983156... | 33 | Same document uploaded 33 times |
| 84565ee36d... | 5 | Likely template |
| 4af79089e8... | 4 | Template/boilerplate |
| ccdf7d2e4e... | 4 | Template/boilerplate |
| 0df25dff61... | 4 | Template/boilerplate |

**Total duplicate groups:** ~100 groups with 458 extra copies

**Action:** Keep one copy, mark others as `duplicate_of_{original_doc_id}`

---

## 4. Generic/Unknown File Types

### 4.1 Documents Needing Type Detection

| File Name Pattern | Count | Issue |
|-------------------|-------|-------|
| DownloadContractFile | 5,990 | No extension, unknown type |
| DownloadDoc.aspx | 17 | No extension, unknown type |
| **TOTAL** | **6,007** | Need file type detection |

### 4.2 Detection Strategy

```python
def detect_file_type(doc):
    """Detect actual file type from content or headers"""
    # 1. Check magic bytes
    magic_signatures = {
        b'%PDF': 'pdf',
        b'PK\x03\x04': 'zip/docx/xlsx',
        b'\xd0\xcf\x11\xe0': 'doc/xls (OLE)',
    }

    # 2. Download first 4 bytes
    response = requests.get(doc.file_url, stream=True)
    magic = response.raw.read(4)

    for sig, file_type in magic_signatures.items():
        if magic.startswith(sig):
            return file_type

    # 3. Check Content-Type header
    content_type = response.headers.get('Content-Type', '')
    if 'pdf' in content_type:
        return 'pdf'
    elif 'word' in content_type:
        return 'docx'
    elif 'excel' in content_type:
        return 'xlsx'

    return 'unknown'
```

**Status:** Needs implementation before extraction

---

## 5. Boilerplate/Irrelevant Content

### 5.1 Patterns Detected

| Pattern | Count | Action |
|---------|-------|--------|
| Contains session/login text | 12 | Skip |
| Only numbers/dates | 0 | Skip |
| Only header/footer | 0 | Skip |

### 5.2 Total Boilerplate

**Total:** 12 documents

**Action:** Mark as `skip_boilerplate`

---

## 6. Summary: Documents to Skip

### 6.1 Complete Skip List

| Category | Count | Status Code |
|----------|-------|-------------|
| Empty content (extracted=success, content empty) | 83 | skip_empty |
| Very short content (<100 chars) | 14 | skip_minimal |
| External bank (ohridskabanka) | 36 | skip_external_bank (already) |
| Bank guarantee content | 154 | skip_bank_guarantee |
| Boilerplate/session | 12 | skip_boilerplate |
| **SUBTOTAL TO SKIP** | **299** | - |
| **Duplicates (mark, don't skip)** | **458** | duplicate |
| **TOTAL FLAGGED** | **757** | - |

### 6.2 Documents Requiring Action Before Extraction

| Category | Count | Action Needed |
|----------|-------|---------------|
| Generic file names | 6,007 | File type detection |
| Failed extraction | 2,585 | Retry with different method |
| Auth required | 366 | Fix URLs (561 done) |

---

## 7. SQL Commands to Mark Bad Documents

### 7.1 Mark Empty Documents

```sql
-- Mark successfully extracted but empty documents
UPDATE documents
SET extraction_status = 'skip_empty'
WHERE extraction_status = 'success'
  AND (content_text IS NULL OR LENGTH(content_text) = 0);
-- Expected: 83 rows
```

### 7.2 Mark Very Short Documents

```sql
-- Mark documents with minimal content
UPDATE documents
SET extraction_status = 'skip_minimal'
WHERE extraction_status = 'success'
  AND content_text IS NOT NULL
  AND LENGTH(content_text) < 100;
-- Expected: 14 rows
```

### 7.3 Mark Bank Guarantee Documents

```sql
-- Mark bank guarantee documents
UPDATE documents
SET extraction_status = 'skip_bank_guarantee'
WHERE (content_text ILIKE '%банкарска гаранција%'
       OR content_text ILIKE '%bank guarantee%')
  AND extraction_status NOT LIKE 'skip%';
-- Expected: ~154 rows
```

### 7.4 Mark Boilerplate Documents

```sql
-- Mark session/boilerplate documents
UPDATE documents
SET extraction_status = 'skip_boilerplate'
WHERE (content_text ILIKE '%session%' OR content_text ILIKE '%логирање%')
  AND extraction_status NOT LIKE 'skip%';
-- Expected: 12 rows
```

### 7.5 Flag Duplicate Documents

```sql
-- Create table for duplicate tracking
CREATE TABLE IF NOT EXISTS document_duplicates (
    doc_id UUID PRIMARY KEY REFERENCES documents(doc_id),
    original_doc_id UUID,
    content_hash VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Find and flag duplicates (keep first occurrence)
WITH duplicates AS (
    SELECT
        doc_id,
        MD5(content_text) as content_hash,
        ROW_NUMBER() OVER (PARTITION BY MD5(content_text) ORDER BY uploaded_at, doc_id) as rn
    FROM documents
    WHERE content_text IS NOT NULL AND LENGTH(content_text) > 100
)
INSERT INTO document_duplicates (doc_id, original_doc_id, content_hash)
SELECT
    d.doc_id,
    (SELECT doc_id FROM duplicates WHERE content_hash = d.content_hash AND rn = 1) as original,
    d.content_hash
FROM duplicates d
WHERE d.rn > 1;
-- Expected: 458 rows
```

---

## 8. Implementation Status

### 8.1 Immediate Actions (Do Now)

- [x] Identified empty documents: 83
- [x] Identified short documents: 14
- [x] Identified bank guarantees: 154
- [x] Identified duplicates: 458
- [x] Identified boilerplate: 12

### 8.2 Before Running Extraction

1. **Run SQL commands** to mark skip_* documents
2. **Implement file type detection** for 6,007 generic files
3. **Create duplicate tracking table**

### 8.3 Estimated Extraction Volume After Filtering

| Category | Count | Change |
|----------|-------|--------|
| Total documents | 15,164 | - |
| Mark as skip | -299 | -2.0% |
| Mark as duplicate | -458 | -3.0% |
| Generic (need detection) | -6,007 | TBD |
| **Estimated extractable** | **~8,400 - 14,400** | Depends on generic |

---

## 9. Risks & Blockers

### 9.1 Identified Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Bank guarantees still extracted | Low | Low | Run SQL before extraction |
| Duplicates waste LLM tokens | Medium | Medium | Create duplicate table first |
| Generic files can't be typed | Medium | HIGH | Download and check magic bytes |

### 9.2 Blockers

1. **6,007 generic files** - Must detect type before extraction
   - **Resolution:** Create file type detection script
   - **Effort:** 2-4 hours of processing time

---

## 10. Bad Document Detection Script

### 10.1 Python Implementation

```python
# scripts/detect_bad_documents.py

import asyncio
import asyncpg
import hashlib
import re

DATABASE_URL = "postgresql://nabavki_user:password@host/nabavkidata"

async def mark_bad_documents():
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # 1. Mark empty documents
        empty_count = await conn.execute("""
            UPDATE documents
            SET extraction_status = 'skip_empty'
            WHERE extraction_status = 'success'
              AND (content_text IS NULL OR LENGTH(content_text) = 0)
        """)
        print(f"Marked {empty_count} empty documents")

        # 2. Mark short documents
        short_count = await conn.execute("""
            UPDATE documents
            SET extraction_status = 'skip_minimal'
            WHERE extraction_status = 'success'
              AND content_text IS NOT NULL
              AND LENGTH(content_text) < 100
        """)
        print(f"Marked {short_count} short documents")

        # 3. Mark bank guarantees
        bank_count = await conn.execute("""
            UPDATE documents
            SET extraction_status = 'skip_bank_guarantee'
            WHERE (content_text ILIKE '%банкарска гаранција%'
                   OR content_text ILIKE '%bank guarantee%')
              AND extraction_status NOT LIKE 'skip%'
        """)
        print(f"Marked {bank_count} bank guarantee documents")

        # 4. Mark boilerplate
        boiler_count = await conn.execute("""
            UPDATE documents
            SET extraction_status = 'skip_boilerplate'
            WHERE (content_text ILIKE '%session%' OR content_text ILIKE '%логирање%')
              AND extraction_status NOT LIKE 'skip%'
        """)
        print(f"Marked {boiler_count} boilerplate documents")

        print("Bad document marking complete!")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(mark_bad_documents())
```

---

## 11. Summary

### Phase A.0 Completion Criteria

- [x] Empty documents identified (83)
- [x] Short documents identified (14)
- [x] Bank guarantees identified (154 + 36 already skipped)
- [x] Duplicates identified (458)
- [x] Boilerplate identified (12)
- [x] SQL commands prepared
- [x] Python script drafted
- [x] Risks documented

### Documents Excluded from Extraction

| Status | Count | Reason |
|--------|-------|--------|
| skip_empty | 83 | No usable content |
| skip_minimal | 14 | Too short |
| skip_external_bank | 36 | External bank server |
| skip_bank_guarantee | 154 | Bank guarantee (not relevant) |
| skip_boilerplate | 12 | Session/login text |
| duplicate | 458 | Same content exists |
| **TOTAL EXCLUDED** | **757** | 5% of documents |

### Remaining for Extraction

| Category | Count |
|----------|-------|
| Already extracted (usable) | 5,675 - 97 = 5,578 |
| Pending (valid) | ~5,500 |
| Failed (retry) | ~2,000 |
| Generic (after detection) | ~4,000 (estimate) |
| **TOTAL EXTRACTABLE** | **~12,000 - 13,000** |

---

## Status: DONE

**Phase A.0 Bad Document Detection is COMPLETE.**

**Key Finding:** ~757 documents (5%) should be marked unusable, saving extraction costs and improving data quality.

**Next Steps:**
1. Run SQL commands to mark bad documents
2. Implement file type detection for 6,007 generic files
3. Proceed to Phase 1 (Quick Wins)
