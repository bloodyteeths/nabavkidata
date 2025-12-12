# UI Data Visibility Audit

**Generated:** 2025-12-02
**Status:** COMPLETE
**Issue:** Only ~20% of data is being displayed in UI, giving impression of no data

---

## Executive Summary

The database contains rich data that is NOT being displayed in the UI. The problem is:
1. Many fields in `raw_data_json` are not mapped to structured columns
2. UI only displays structured columns, ignoring `raw_data_json`
3. Bidder/pricing data exists but requires separate API calls
4. Documents exist but content isn't surfaced in UI

**Solution:** Use AI to dynamically extract and display data from `raw_data_json` when structured fields are empty.

---

## 1. Database Field Population Audit

### 1.1 Tenders Table (4,762 tenders)

| Field | Populated | Fill Rate | Notes |
|-------|-----------|-----------|-------|
| title | 4,762 | 100% | Always present |
| procuring_entity | 4,748 | 99.7% | Nearly complete |
| status | 4,762 | 100% | Always present |
| publication_date | 4,452 | 93.5% | Good coverage |
| estimated_value_mkd | 3,814 | 80.1% | Good coverage |
| actual_value_mkd | 2,037 | 42.8% | Only awarded tenders |
| winner | 2,028 | 42.6% | Only awarded tenders |
| **description** | **1,389** | **29.2%** | LOW - MAJOR GAP |
| cpv_code | 1,544 | 32.4% | LOW |
| opening_date | 1,195 | 25.1% | LOW |
| closing_date | 343 | 7.2% | CRITICAL GAP |
| num_bidders | 309 | 6.5% | CRITICAL GAP |
| raw_data_json | 3,584 | 75.3% | Contains unmapped data |
| items_data | 0 | 0% | NOT POPULATED |
| all_bidders_json | 0 | 0% | NOT POPULATED |
| lowest_bid_mkd | 0 | 0% | NOT POPULATED |
| highest_bid_mkd | 0 | 0% | NOT POPULATED |

### 1.2 EPazar Tenders Table (838 tenders)

| Field | Populated | Fill Rate | Notes |
|-------|-----------|-----------|-------|
| title | 838 | 100% | Always present |
| contracting_authority | 838 | 100% | Always present |
| status | 838 | 100% | Always present |
| awarded_value_mkd | 654 | 78% | Good coverage |
| description | 439 | 52% | Moderate |
| estimated_value_mkd | 0 | 0% | NOT POPULATED |
| cpv_code | 0 | 0% | NOT POPULATED |
| raw_data_json | 543 | 65% | Contains unmapped data |
| items_data | 838 | 100% | Has items! |

### 1.3 Tender Bidders Table (18,462 bidders)

| Metric | Value |
|--------|-------|
| Total bidders | 18,462 |
| With company_name | 18,462 (100%) |
| With bid_amount_mkd | 17,025 (92%) |
| Marked as winner | 17,025 (92%) |
| Unique tenders with bidders | 3,498 |

**KEY INSIGHT:** We have 18,462 bidder records with pricing data for 3,498 tenders, but this is NOT being displayed!

### 1.4 Documents Table (15,528 documents)

| Metric | Value |
|--------|-------|
| Total documents | 15,528 |
| With extracted content | 6,042 (39%) |
| Extraction success | 5,832 (38%) |
| Unique tenders with docs | 3,858 |

---

## 2. Data in raw_data_json NOT Being Used

### 2.1 Available Keys in raw_data_json

```
bidders_data          (2,337 tenders - bidder info!)
documents_data        (3,584 tenders - doc metadata)
lots_data             (20 tenders - lot breakdowns)
items_table_html      (0 - needs extraction)
payment_terms         (46 tenders)
contact_person        (varies)
contact_email         (varies)
contact_phone         (varies)
```

### 2.2 Critical Hidden Data

**Bidders Data Comparison:**
- 2,337 tenders have `bidders_data` in `raw_data_json`
- Only 3,498 unique tenders in `tender_bidders` table
- **OVERLAP:** Many bidders are ONLY in raw_data_json!

**This means UI is missing bidder pricing data that exists in the database!**

---

## 3. UI vs Database Gap Analysis

### 3.1 What UI Currently Shows

The frontend `Tender` interface expects:
- title, description, procuring_entity
- estimated_value_mkd, actual_value_mkd
- dates (opening, closing, publication)
- cpv_code, status, winner
- bidders[] array (from raw_data_json)
- lots[] array (from raw_data_json)

### 3.2 What UI is MISSING

| Data Category | DB Location | UI Display | Gap |
|---------------|-------------|------------|-----|
| Bidder prices | tender_bidders, raw_data_json.bidders_data | Partial | API call needed, not always made |
| Document content | documents.content_text | Not shown | 6,042 docs with text! |
| Lot details | raw_data_json.lots_data | Not shown | 20+ tenders have lot breakdowns |
| Contact info | raw_data_json | Not shown | Available but not displayed |
| Payment terms | raw_data_json.payment_terms | Not shown | 46 tenders have this |
| Item specifications | documents + AI extraction | Not shown | Requires AI processing |

---

## 4. Root Causes of "Empty Fields"

### 4.1 Structured Fields Never Populated
Some fields exist in schema but scraper doesn't populate them:
- `items_data` - Always NULL
- `all_bidders_json` - Always NULL
- `lowest_bid_mkd`, `highest_bid_mkd` - Always NULL
- `closing_date` - Only 7.2% populated

### 4.2 Data in raw_data_json Not Extracted
Scraper saves complete data to `raw_data_json` but doesn't parse it into structured fields:
- bidders_data (2,337 tenders)
- documents_data (3,584 tenders)
- contact info (varies)

### 4.3 UI Doesn't Fetch Related Data
- Documents require separate `/api/tenders/{id}/documents` call
- Bidders require separate `/api/tenders/by-id/{num}/{year}/bidders` call
- These calls may not be made or may fail silently

---

## 5. Solution: AI-Powered Data Display

### 5.1 New Backend Endpoint

Create `/api/tenders/{id}/ai-enhanced` that:
1. Returns structured fields if available
2. Falls back to AI extraction from `raw_data_json` if structured fields empty
3. Extracts data from document content if available

```python
@router.get("/tenders/{tender_id}/ai-enhanced")
async def get_ai_enhanced_tender(tender_id: str, db: AsyncSession):
    tender = await get_tender(tender_id)

    # If description is empty, extract from raw_data_json or documents
    if not tender.description:
        tender.description = await ai_extract_description(tender)

    # If no bidders in response, extract from raw_data_json
    if not tender.bidders:
        tender.bidders = extract_bidders_from_raw_json(tender.raw_data_json)

    # If no items, extract from documents
    if not tender.items:
        tender.items = await ai_extract_items(tender_id)

    return tender
```

### 5.2 AI Extraction Functions

```python
def extract_bidders_from_raw_json(raw_json: dict) -> list:
    """Extract bidders from raw_data_json.bidders_data"""
    if not raw_json or 'bidders_data' not in raw_json:
        return []

    bidders = []
    for b in raw_json.get('bidders_data', []):
        bidders.append({
            'company_name': b.get('company_name') or b.get('bidder_name'),
            'bid_amount_mkd': b.get('bid_amount_mkd') or b.get('amount'),
            'is_winner': b.get('is_winner', False),
            'rank': b.get('rank')
        })
    return bidders

async def ai_extract_description(tender) -> str:
    """Use AI to generate description from available data"""
    # Combine title + raw_json content + document excerpts
    context = build_context(tender)

    prompt = f"""
    Generate a concise description for this tender based on available data:
    {context}
    """

    response = await gemini.generate(prompt)
    return response.text
```

### 5.3 UI Changes

1. **Call AI-enhanced endpoint** instead of basic tender endpoint
2. **Show "AI-extracted" badge** when data comes from AI
3. **Display bidders inline** on tender detail page
4. **Show document summaries** using existing content_text

---

## 6. Immediate Actions (Quick Wins)

### 6.1 Backend Changes

1. **Populate structured fields from raw_data_json** (one-time migration):
```sql
-- Migrate bidders_data from raw_data_json to tender_bidders
-- Migrate description from raw_data_json if empty
UPDATE tenders
SET description = raw_data_json->>'description'
WHERE description IS NULL
  AND raw_data_json->>'description' IS NOT NULL;
```

2. **Calculate lowest/highest bid** from tender_bidders:
```sql
UPDATE tenders t
SET lowest_bid_mkd = (
    SELECT MIN(bid_amount_mkd) FROM tender_bidders tb
    WHERE tb.tender_id = t.tender_id
),
highest_bid_mkd = (
    SELECT MAX(bid_amount_mkd) FROM tender_bidders tb
    WHERE tb.tender_id = t.tender_id
)
WHERE EXISTS (SELECT 1 FROM tender_bidders WHERE tender_id = t.tender_id);
```

### 6.2 Frontend Changes

1. **Always fetch bidders** when loading tender detail page
2. **Display raw_data_json.bidders_data** if tender_bidders empty
3. **Show document count** with link to documents tab
4. **Add "Data Sources" section** showing what data is available

---

## 7. Full Refactor Plan

### Phase 1: Data Migration (Immediate)
- [ ] Migrate bidders_data from raw_data_json to tender_bidders table
- [ ] Calculate and populate lowest_bid_mkd, highest_bid_mkd
- [ ] Populate description from raw_data_json where empty
- [ ] Extract contact info from raw_data_json

### Phase 2: API Enhancement (Week 1)
- [ ] Create `/api/tenders/{id}/ai-enhanced` endpoint
- [ ] Add bidder aggregation to tender detail response
- [ ] Include document summary in tender response
- [ ] Add data completeness score to each tender

### Phase 3: UI Enhancement (Week 1-2)
- [ ] Show bidders directly on tender detail page
- [ ] Display "Data available" indicators
- [ ] Add AI-extracted badge for generated content
- [ ] Show document snippets with tender

### Phase 4: AI Extraction (Week 2-3)
- [ ] Implement AI description generation
- [ ] Implement AI item extraction from documents
- [ ] Implement AI pricing analysis
- [ ] Cache AI extractions to reduce costs

---

## 8. Expected Impact

| Metric | Current | After Fix |
|--------|---------|-----------|
| Fields with data visible | ~20% | ~80% |
| Tenders showing bidders | ~10% | ~70% |
| Tenders with descriptions | 29% | ~90% |
| Data completeness perception | Low | High |

---

## 9. API Endpoint Changes Summary

### New Endpoints Needed

1. `GET /api/tenders/{id}/ai-enhanced` - Returns tender with AI-filled gaps
2. `GET /api/tenders/{id}/completeness` - Returns data completeness score
3. `GET /api/tenders/{id}/smart-summary` - AI-generated summary of all available data

### Existing Endpoints to Modify

1. `GET /api/tenders/{id}` - Include bidders inline if available
2. `GET /api/tenders` - Include bidder count in list response
3. `GET /api/tenders/by-id/{num}/{year}/bidders` - Already exists, ensure UI calls it

---

## 10. Conclusion

**The database has the data. The problem is display logic.**

Key findings:
- 18,462 bidder records exist but aren't displayed
- 6,042 documents with extracted content exist but aren't shown
- raw_data_json contains 2,337+ tenders worth of bidder data
- ~75% of tenders have raw_data_json with additional fields

**Priority fix:** Display bidder data that already exists in the database.

**Second priority:** Use AI to fill empty fields from raw_data_json and documents.
