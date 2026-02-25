# UX Journey Roadmap: "Stupid-Proof" Navigation Fixes

## Problem Statement
A company owner selling office supplies logs into NabavkiData and cannot accomplish basic goals without prior training. The platform is built for procurement experts who know CPV codes, company names, and navigation patterns.

## Journey Test Results (Feb 25, 2026)

| Goal | Task | Result | Roadblock |
|------|------|--------|-----------|
| 1 | Find tenders for my products | Had to navigate to Тендери manually | Dashboard has NO search box |
| 2 | Check market prices for A4 paper | "Нема резултати" on e-Pazar | Price check too strict, no fuzzy match |
| 3 | Find who else bids on my sector | Global leaderboard, 0 autocomplete | No sector-based competitor discovery |
| 4 | Set up alerts for new tenders | Form works but CPV requires numeric code | CPV picker exists but not obvious |
| 5 | Check industry trends | Works after entering "30" | Needs preset industry buttons |

---

## Phase 1 Fixes (COMPLETED - Feb 25, 2026)

### Fix 1: Dashboard Search Hero - DONE
- Added search box with 6 product chips to dashboard
- Redirects to `/tenders?search={query}`
- Commit: `c600517c`

### Fix 2: Competitor Sector Filter - DONE
- Added 8 CPV sector buttons to competitors page
- Backend accepts `cpv_prefix` parameter
- Each sector shows distinct top competitors

### Fix 3: e-Pazar Fuzzy Matching - DONE (partial)
- Implemented word-level AND matching (split search → match all words)
- Fixed SQL bind parameter bug in evaluation queries
- Added fallback links to Products and Tenders when no results

### Fix 4: Cross-Links - DONE
- Products → e-Pazar link added
- e-Pazar → Products/Tenders fallback links on empty results

### Fix 5: Trends Preset Buttons - DONE
- 8 industry preset buttons below CPV filter

---

## Phase 1 Backend Audit (Feb 25, 2026)

Tested all 5 components against live API with 10+ keywords each. Full test script: `backend/test_ux_components.py`

### Results Summary

| Component | Score | Verdict |
|-----------|-------|---------|
| Tender Search | **10/10** keywords return results | EXCELLENT |
| Competitor Sectors | **8/8** CPV sectors return 5+ competitors | EXCELLENT |
| e-Pazar Prices | **3/10** keywords return data | CRITICAL GAP |
| Trends/CPV | **8/8** sectors have 1000+ tenders | EXCELLENT |
| Products Catalog | **5/5** keywords return products | OK (quality issues) |

### Bug Found & Fixed During Audit

**e-Pazar 500 errors** on "тонер", "компјутер", "хартија": The fuzzy matching fix introduced new bind parameter names (`s_w0`, `lat_w0`) for the main query, but three downstream queries (evaluation prices, winning brands, sample item) still referenced old `:search` / `:search_latin` parameters. Fixed by creating `build_eval_conditions()` with separate param names (`ev_s_w0`, `ev_lat_w0`).

### Data Coverage Analysis

The price intelligence endpoint only queries `epazar_items` (7,150 items from 995 tenders). But `product_items` has **56x more data**:

| Keyword | epazar_items | product_items (w/ price) | Gap |
|---------|-------------|--------------------------|-----|
| хартија | 282 | **2,751** | 10x |
| дизел | 0 | **2,135** | infinite |
| бензин | 0 | **1,691** | infinite |
| гориво | 0 | **585** | infinite |
| компјутер | 96 | **338** | 3.5x |
| тонер | 189 | **212** | 1.1x |
| канцелариск | 19 | **137** | 7x |
| печатач | 0 | **52** | infinite |
| столиц | 4 | **40** | 10x |

**Root cause**: e-Pazar data comes from the e-pazar.mk marketplace scrape (995 tenders). Product_items comes from PDF extraction of tender documents (403K items, 81K with prices). The price intelligence endpoint ignores the larger dataset entirely.

### Products Quality Issues

- Default sort `date_desc` shows items WITHOUT prices first → user thinks no prices exist
- Low-confidence extractions (< 0.5) produce junk names like "3.1. Предмет на постапката"
- Some items are mis-categorized (e.g., "дизел" returns military vehicles at 6.5M MKD)

---

## Phase 2: Implementation Plan

### Fix 6: Price Intelligence Fallback to product_items (CRITICAL)
**File:** `backend/api/epazar.py` (price-intelligence endpoint)

**Problem:** 7/10 common product searches return 404 because epazar_items has only 7K items.

**Solution:** When epazar_items returns 0 results, query `product_items` as a fallback data source. This gives 56x more coverage.

**Implementation:**
1. After the existing `epazar_items` query returns 0, run a fallback query against `product_items`:
   ```sql
   SELECT COUNT(*) as total_items,
          MIN(unit_price) FILTER (WHERE unit_price > 0) as min_price,
          MAX(unit_price) FILTER (WHERE unit_price > 0) as max_price,
          AVG(unit_price) FILTER (WHERE unit_price > 0) as avg_price,
          PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price) FILTER (WHERE unit_price > 0) as median_price,
          MIN(unit) as common_unit
   FROM product_items
   WHERE {word_search_condition}
     AND unit_price > 0
     AND extraction_confidence >= 0.6
   ```
2. Return the same response shape but with `data_source: "product_items"` flag
3. Merge with tender winner data from `tenders.winner` for competition context
4. Add `data_source` field to response so frontend can show appropriate label

**Expected impact:** Coverage jumps from 3/10 → 9/10 keywords returning price data.

### Fix 7: Fuzzy Search Relaxation (HIGH)
**File:** `backend/api/epazar.py`

**Problem:** "хартија А4" returns 0 results because epazar_items uses "Фотокопирна хартија" (no "А4" in name). AND matching is too strict.

**Solution:** Two-tier search:
1. First try AND matching (all words must match)
2. If 0 results, relax to the longest word only (e.g., "хартија" from "хартија А4")
3. Return results with a note: "Покажуваме резултати за 'хартија' (нема точен резултат за 'хартија А4')"

**Implementation:**
1. After both epazar_items AND product_items fallback return 0:
   - Extract the longest word from the search query
   - Re-run the same query pipeline with just that word
   - Add `relaxed_search: true` and `original_query` to the response
2. Frontend shows a notice when `relaxed_search` is true

### Fix 8: Products Default Sort & Junk Filter (MEDIUM)
**File:** `backend/api/products.py`

**Problem:** Default sort shows items without prices first. Low-confidence extractions pollute results.

**Solution:**
1. Change default sort to prioritize items WITH prices: `price_desc` or a smart sort that puts priced items first
2. Filter out extraction_confidence < 0.5 by default (unless `include_low_confidence=true` param)
3. Filter out items matching junk patterns: name starts with "3.1." or name length < 5

**Implementation:**
1. Add `WHERE extraction_confidence >= 0.5` to base query
2. Add `AND LENGTH(name) >= 5 AND name NOT LIKE '3.%'` junk filter
3. Change default sort_by to a composite: `CASE WHEN unit_price > 0 THEN 0 ELSE 1 END, opening_date DESC`

### Fix 9: Products API Price Stats Summary (LOW)
**File:** `backend/api/products.py`

**Problem:** Products search returns raw items but no aggregate price stats. User has to mentally scan 20 items to understand the price range.

**Solution:** Add a `price_summary` object to the Products search response:
```json
{
  "price_summary": {
    "min_price": 150,
    "max_price": 2500,
    "avg_price": 420,
    "median_price": 350,
    "items_with_price": 2751,
    "common_unit": "Парче"
  }
}
```

**Implementation:**
1. Run a parallel aggregate query alongside the paginated results
2. Only include items with `extraction_confidence >= 0.6` in the stats
3. Frontend can display this as a price range card above the product list

---

## Phase 2 Priority Order

| # | Fix | Impact | Effort | Priority |
|---|-----|--------|--------|----------|
| 6 | Price intelligence fallback to product_items | 7 keywords go from 404→data | Backend only | **CRITICAL** |
| 7 | Fuzzy search relaxation (AND→longest word) | "хартија А4" finally works | Backend only | **HIGH** |
| 8 | Products junk filter + smart sort | Clean product browsing | Backend only | **MEDIUM** |
| 9 | Products price stats summary | Price context at a glance | Backend + Frontend | **LOW** |

## Deployment
- Frontend: `git push` triggers Vercel auto-deploy
- Backend: `rsync` to EC2 + `systemctl restart nabavkidata-api`
- Verify: Rerun `python3 backend/test_ux_components.py`
