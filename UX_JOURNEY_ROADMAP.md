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

## Fix 1: Dashboard Search Hero (CRITICAL)
**File:** `frontend/app/dashboard/page.tsx`

**What:** Add a prominent search box at the top of the dashboard that routes to /tenders with the query. Include 4-5 popular search chips below.

**Why:** First thing a company owner wants to do is search for their products. Currently they see a spinner → generic recommendations → dead end.

**Implementation:**
- Add search bar between header and stats grid
- On submit, redirect to `/tenders?search={query}`
- Add example chips: "канцелариски", "медицинска опрема", "ИТ услуги", "градежни работи", "храна"

---

## Fix 2: Competitor Sector Filter (HIGH)
**File:** `frontend/app/competitors/page.tsx`

**What:** Add CPV-based sector filter to the top competitors tab, so users can see "who bids in MY industry" instead of a global leaderboard.

**Why:** The current competitors page shows АЛКАЛОИД (#1 globally) which is irrelevant to an office supplies seller. User needs "who bids on CPV 30 tenders."

**Implementation:**
- Add CPV code autocomplete filter above the top competitors list (reuse existing pattern from trends page)
- Pass `cpv_prefix` parameter to the backend `getCompetitorAnalysis` API
- Add quick-select industry chips: "33 Медицинска", "45 Градежни", "30 Канцелариска", "72 ИТ"
- Backend already supports CPV filtering on `tender_bidders` table

---

## Fix 3: e-Pazar Price Check Fuzzy Matching (CRITICAL)
**File:** `backend/api/epazar.py` (price-intelligence endpoint)

**What:** Improve the price check search to use fuzzy/partial matching so "хартија А4" returns results even if the exact item name doesn't exist.

**Why:** User types "хартија А4" → "Нема резултати". The data exists but under slightly different names ("Хартија А4 80гр", "хартија за копирање А4", etc.)

**Implementation:**
- Change ILIKE query from exact match to partial word matching
- Split search into words and match ALL words with AND logic
- Add fallback: if no results, try matching individual words
- Add product suggestions when partial match found

---

## Fix 4: Cross-Link Price Pages (MEDIUM)
**Files:** `frontend/app/dashboard/page.tsx`, `frontend/app/products/page.tsx`, `frontend/app/epazar/page.tsx`

**What:** Add contextual links between related pages so users can discover price information from anywhere.

**Implementation:**
- Dashboard quick-actions already link to /products (done in previous session)
- Products page: Add "Провери пазарна цена на е-Пазар" link when viewing a product
- e-Pazar page: Add "Погледни сите тендери за овој производ" link to /tenders
- Both price pages: Link to each other with explanation of difference

---

## Fix 5: Trends Page CPV Preset Buttons (LOW)
**File:** `frontend/app/trends/page.tsx`

**What:** Add preset industry buttons below the CPV input so users don't have to know their CPV code number.

**Why:** The placeholder already says "30 (канцелариска опрема)" but users still have to type. Quick buttons solve this.

**Implementation:**
- Add row of buttons: "Медицинска (33)", "Градежни (45)", "Канцелариска (30)", "ИТ услуги (72)", "Транспорт (34)", "Храна (15)"
- On click, populate CPV filter and auto-apply

---

## Priority Order
1. Fix 1 - Dashboard search (30 min, instant value)
2. Fix 3 - e-Pazar fuzzy search (45 min, critical for price discovery)
3. Fix 2 - Competitor sector filter (45 min, high value)
4. Fix 5 - Trends preset buttons (15 min, low effort high clarity)
5. Fix 4 - Cross-links (20 min, connective tissue)

## Deployment
- Frontend: `npx vercel --prod` from frontend/
- Backend: `rsync` to EC2 + `systemctl restart nabavkidata-api`
- Verify: Playwright journey test rerun
