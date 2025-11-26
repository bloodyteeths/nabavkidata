# Field Mapping Summary - Visual Overview

## 🔴 CRITICAL ISSUES

### 1. Contact Information - 100% HIDDEN
```
Database (1,107 records)          API                    UI
├─ contact_person (100%) ──────→ NOT EXPOSED ────────→ ❌ NOT SHOWN
├─ contact_email (100%)  ──────→ NOT EXPOSED ────────→ ❌ NOT SHOWN
└─ contact_phone (80%)   ──────→ NOT EXPOSED ────────→ ❌ NOT SHOWN
```
**Impact:** Users cannot contact procurement officers. This is gold data being wasted.

### 2. Bidder Information - COMPLETELY HIDDEN
```
tender_bidders table (72 records)
├─ company_name      ──────→ API endpoint exists ────→ ❌ NO UI TAB
├─ bid_amount_mkd    ──────→ /bidders/{id}      ────→ ❌ NO UI TAB
├─ rank              ──────→ ✅ Exposed         ────→ ❌ NO UI TAB
└─ is_winner         ──────→ ✅ Exposed         ────→ ❌ NO UI TAB
```
**Impact:** Competitive intelligence is hidden. Users can't see who's bidding.

### 3. Supplier Profiles - ENTIRE SYSTEM HIDDEN
```
suppliers table (60 companies)
├─ company_name          ──────→ ✅ /api/suppliers/   ────→ ❌ NO /suppliers PAGE
├─ win_rate (80% pop.)   ──────→ ✅ API exposed       ────→ ❌ NO UI
├─ total_contract_value  ──────→ ✅ API exposed       ────→ ❌ NO UI
└─ industries            ──────→ ✅ API exposed       ────→ ❌ NO UI
```
**Impact:** Competitor analytics system exists but is invisible.

### 4. Lots System - BROKEN
```
tenders.has_lots = TRUE (many records)
        ↓
tender_lots table = 0 records (EMPTY!)
        ↓
/tenders/{id}/lots API = returns []
        ↓
UI = nothing to show
```
**Impact:** Scraper not extracting lot breakdowns despite DB schema being ready.

### 5. Product Search - BROKEN
```
product_items table = 0 records (EMPTY!)
        ↓
/products page exists
        ↓
Search returns nothing
```
**Impact:** BOQ item search is non-functional. Document extraction not working.

---

## ✅ WELL-MAPPED FIELDS (Working Correctly)

### Regular Tenders (Basic Info)
```
Database                     API                          UI Display
├─ title              ────→ ✅ tender.title        ────→ ✅ TenderCard H1
├─ description        ────→ ✅ tender.description  ────→ ✅ Card preview
├─ category           ────→ ✅ tender.category     ────→ ✅ Badge
├─ status             ────→ ✅ tender.status       ────→ ✅ Badge
├─ procuring_entity   ────→ ✅ tender.proc_entity  ────→ ✅ Card meta
├─ estimated_value    ────→ ✅ tender.est_value    ────→ ✅ Card meta
├─ closing_date       ────→ ✅ tender.closing_date ────→ ✅ Card meta
└─ source_url         ────→ ✅ tender.source_url   ────→ ✅ "Open Source" btn
```

### E-Pazar System (Excellent Coverage)
```
Database                     API                          UI Display
├─ epazar_tenders     ────→ ✅ /api/epazar/       ────→ ✅ /epazar page
├─ epazar_items       ────→ ✅ tender.items[]     ────→ ✅ Items table
├─ epazar_offers      ────→ ✅ tender.offers[]    ────→ ✅ Offers cards
├─ epazar_awarded     ────→ ✅ tender.awarded[]   ────→ ✅ Awarded table
└─ epazar_documents   ────→ ✅ tender.documents[] ────→ ✅ Documents list
```

---

## ⚠️ PARTIALLY MAPPED (API Exposed, UI Missing)

### High-Value Fields Missing from UI

| Field | DB Pop. | In API | In UI | Why Important |
|-------|---------|--------|-------|---------------|
| `procedure_type` | 100% | ✅ Yes | ❌ No | Filter/search by procedure type |
| `publication_date` | 60% | ✅ Yes | ❌ No | Shows tender freshness |
| `actual_value_mkd` | 20% | ✅ Yes | ❌ No | Compare estimate vs awarded value |
| `winner` | 10% | ✅ Yes | ❌ No | Shows who won awarded tenders |
| `*_eur` values | 30-40% | ✅ Yes | ❌ No | EUR currency display |
| `contract_duration` | 5% | ✅ Yes | ❌ No | Contract term length |
| `contracting_entity_category` | 80% | ✅ Yes | ❌ No | Ministry/Municipality/etc. |

---

## 📊 COVERAGE STATISTICS

### Overall Field Visibility

```
┌─────────────────────────────────────────────────────────┐
│ TENDERS TABLE (49 columns)                              │
├─────────────────────────────────────────────────────────┤
│ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░ 24% visible in UI   │
│ ████████████░░░░░░░░░░░░░░░░░░░░░░ 37% in API          │
│ ██████████████████████████████████ 100% in DB          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ E-PAZAR TENDERS (26 columns)                            │
├─────────────────────────────────────────────────────────┤
│ ███████████████████████████░░░░░░░ 73% visible in UI   │
│ ████████████████████████████████░░ 92% in API          │
│ ██████████████████████████████████ 100% in DB          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ SUPPLIERS TABLE (16 columns)                            │
├─────────────────────────────────────────────────────────┤
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0% visible in UI    │
│ ██████████████████████████████████ 100% in API         │
│ ██████████████████████████████████ 100% in DB          │
└─────────────────────────────────────────────────────────┘
              API exists but NO UI at all!

┌─────────────────────────────────────────────────────────┐
│ TENDER_BIDDERS TABLE (12 columns, 72 records)          │
├─────────────────────────────────────────────────────────┤
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0% visible in UI    │
│ ██████████████████████████████████ 100% in API         │
│ ██████████████████████████████████ 100% in DB          │
└─────────────────────────────────────────────────────────┘
              API endpoint works but NO UI tab!
```

---

## 🎯 QUICK WINS (High ROI, Low Effort)

### 1. Add Contact Section to Tender Details
**Effort:** 1-2 hours
**Impact:** HIGH
**Code Change:**
```typescript
// In /app/tenders/[id]/page.tsx
{tender.contact_person && (
  <Card>
    <CardHeader>
      <CardTitle>Контакт</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="space-y-2">
        {tender.contact_person && (
          <div className="flex items-center gap-2">
            <User className="h-4 w-4" />
            <span>{tender.contact_person}</span>
          </div>
        )}
        {tender.contact_email && (
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            <a href={`mailto:${tender.contact_email}`}>
              {tender.contact_email}
            </a>
          </div>
        )}
        {tender.contact_phone && (
          <div className="flex items-center gap-2">
            <Phone className="h-4 w-4" />
            <span>{tender.contact_phone}</span>
          </div>
        )}
      </div>
    </CardContent>
  </Card>
)}
```

### 2. Display Procedure Type
**Effort:** 30 minutes
**Impact:** MEDIUM
**Code Change:**
```typescript
// In TenderCard.tsx
{tender.procedure_type && (
  <Badge variant="outline" className="text-xs">
    {tender.procedure_type}
  </Badge>
)}
```

### 3. Add Bidders Tab
**Effort:** 2-3 hours
**Impact:** HIGH
**Code Change:**
```typescript
// In /app/tenders/[id]/page.tsx
<TabsTrigger value="bidders">
  <Users className="h-4 w-4 mr-2" />
  Понудувачи
</TabsTrigger>

<TabsContent value="bidders">
  <BiddersTable tenderId={tenderId} />
</TabsContent>
```

### 4. Show Publication Date
**Effort:** 15 minutes
**Impact:** LOW-MEDIUM
**Code Change:**
```typescript
// In tender detail dates section
{tender.publication_date && (
  <div className="flex items-start gap-2">
    <Calendar className="h-4 w-4" />
    <div>
      <p className="text-xs font-medium">Објавен</p>
      <p className="text-sm">{formatDate(tender.publication_date)}</p>
    </div>
  </div>
)}
```

---

## 📋 MEDIUM-TERM IMPROVEMENTS

### 1. Build Supplier Analytics Page
**Effort:** 1-2 days
**Impact:** HIGH
**Requirements:**
- New route: `/app/suppliers/page.tsx`
- API already exists: `/api/suppliers/*`
- Features:
  - Supplier search
  - Win rate leaderboard
  - Contract value totals
  - Industry breakdown

### 2. Build Entity Analytics Page
**Effort:** 1-2 days
**Impact:** MEDIUM
**Requirements:**
- New route: `/app/entities/page.tsx`
- API already exists: `/api/entities/*`
- Features:
  - Procurement by ministry/municipality
  - Spending trends
  - Category preferences

### 3. Fix Lot Extraction in Scraper
**Effort:** 1-2 days
**Impact:** HIGH
**Requirements:**
- Update scraper to extract lot breakdown
- Parse lot table from tender pages
- Populate `tender_lots` table
- Add "Lots" tab to UI

### 4. Fix Product Item Extraction
**Effort:** 2-3 days
**Impact:** MEDIUM
**Requirements:**
- Implement PDF table parsing
- Extract BOQ items from documents
- Populate `product_items` table
- Make `/products` search functional

---

## 🔍 DATA QUALITY ISSUES

### Empty Tables (DB Schema Ready, No Data)

| Table | Schema Status | Scraper Status | Impact |
|-------|--------------|---------------|--------|
| `tender_lots` | ✅ Ready | ❌ Not extracting | Lot breakdown missing |
| `product_items` | ✅ Ready | ❌ Not extracting | Product search broken |
| `tender_amendments` | ✅ Ready | ❌ Not tracking | Change history missing |

### Inconsistent Data

| Field | Issue | Records Affected |
|-------|-------|-----------------|
| `has_lots` | TRUE but `tender_lots` empty | Many tenders |
| `num_lots` | Always 0 despite `has_lots=TRUE` | All |
| `num_bidders` | Populated for 56 but `tender_bidders` has 72 | Mismatch |

---

## 💡 RECOMMENDED PRIORITY ORDER

### Sprint 1 (Week 1) - Quick Wins
1. ✅ Add contact information section
2. ✅ Show procedure type badges
3. ✅ Display publication date
4. ✅ Add EUR currency toggle

### Sprint 2 (Week 2) - Competitive Intelligence
5. ✅ Add bidders tab to tender details
6. ✅ Build supplier analytics page
7. ✅ Add winner display for awarded tenders

### Sprint 3 (Week 3) - Fix Data Extraction
8. ✅ Fix lot extraction in scraper
9. ✅ Implement product item extraction
10. ✅ Add lots tab to tender details

### Sprint 4 (Week 4) - Entity Analytics
11. ✅ Build entity/institution analytics page
12. ✅ Add entity filters and search
13. ✅ Create procurement patterns dashboard

---

## 📊 ROI ANALYSIS

### High ROI Improvements

| Feature | Effort | User Value | Data Exists | ROI Score |
|---------|--------|-----------|-------------|-----------|
| Contact info display | Low | Very High | ✅ 100% | ⭐⭐⭐⭐⭐ |
| Bidders tab | Medium | Very High | ✅ Yes (72) | ⭐⭐⭐⭐⭐ |
| Supplier analytics | Medium | High | ✅ Yes (60) | ⭐⭐⭐⭐ |
| Procedure type filter | Low | Medium | ✅ 100% | ⭐⭐⭐⭐ |
| Publication date | Low | Low | ✅ 60% | ⭐⭐⭐ |

### Low ROI Improvements (Do Later)

| Feature | Effort | User Value | Data Exists | ROI Score |
|---------|--------|-----------|-------------|-----------|
| Amendment tracking | High | Low | ❌ No data | ⭐ |
| Quality scoring (E-Pazar) | Medium | Low | ❌ 2% only | ⭐ |
| Payment tracking | Medium | Low | ❌ No data | ⭐ |

---

**Next Steps:**
1. Review this mapping with the team
2. Prioritize which hidden fields to expose
3. Fix scraper for empty tables (lots, products)
4. Build supplier and entity analytics pages

---

Generated: 2025-11-25
Database: nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com
