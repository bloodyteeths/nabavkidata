# E-Nabavki.gov.mk Website Structure Analysis
## Comprehensive Tender Categories, URLs, and Document Endpoints Mapping

**Analysis Date:** 2025-11-24
**Website:** https://e-nabavki.gov.mk
**Framework:** AngularJS 1.x with ASP.NET WebForms backend
**Status:** Based on existing scraper implementation and open-source projects

---

## Executive Summary

The e-nabavki.gov.mk portal is North Macedonia's official public procurement platform. It is a **JavaScript-heavy Single Page Application (SPA)** built with AngularJS 1.x and ASP.NET WebForms, requiring client-side rendering to access content. This analysis provides a comprehensive mapping of:

- ✅ **Verified tender listing page structure** (from working scraper)
- ✅ **Tender detail page selectors** (19 fields with ASP.NET control IDs)
- ✅ **Document extraction patterns** (6+ selector strategies)
- ⚠️ **Partial category mapping** (active notices confirmed, others require inspection)
- ⚠️ **API endpoints unknown** (requires network traffic analysis)

---

## Table of Contents

1. [Technical Architecture](#1-technical-architecture)
2. [Tender Categories](#2-tender-categories)
3. [Tender Detail Pages](#3-tender-detail-pages)
4. [Document Endpoints](#4-document-endpoints)
5. [Profile Pages](#5-profile-pages)
6. [Additional Features](#6-additional-features)
7. [API Endpoints Discovery](#7-api-endpoints-discovery)
8. [Extraction Strategy](#8-extraction-strategy)
9. [Implementation Guide](#9-implementation-guide)
10. [Testing Recommendations](#10-testing-recommendations)

---

## 1. Technical Architecture

### Framework Details

| Component | Technology | Details |
|-----------|-----------|---------|
| **Frontend** | AngularJS 1.x | Hash-based routing (#/notices, #/home) |
| **Backend** | ASP.NET WebForms | Server-side rendering with ViewState |
| **Rendering** | Client-side JavaScript | Mandatory for content visibility |
| **Data Loading** | AJAX + Angular bindings | Dynamic content after page load |
| **Language Support** | Macedonian, English, Albanian | MK is primary language |

### JavaScript Rendering Requirements

**CRITICAL:** The website **cannot be scraped with simple HTTP requests**. Content is rendered client-side via AngularJS.

**Required Tools:**
- ✅ Playwright (currently implemented in scraper)
- ✅ Selenium
- ✅ Puppeteer

**Wait Conditions:**
```python
# Listings page
await page.goto('https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices')
await page.wait_for_load_state('networkidle')  # Wait for AJAX
await page.wait_for_selector('.RowStyle, .AltRowStyle', timeout=10000)
await page.wait_for_timeout(2000)  # Angular data binding

# Detail page
await page.goto('https://e-nabavki.gov.mk/PublicAccess/Dossie/...')
await page.wait_for_selector('label.dosie-value', timeout=20000)
await page.wait_for_timeout(1500)
```

---

## 2. Tender Categories

### 2.1 Active/Published Notices ✅ VERIFIED

**URL:** `https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices`
**Angular Route:** `#/notices`
**Status:** Fully documented and implemented in scraper

#### Page Structure

| Element | Selector | Source | Reliability |
|---------|----------|--------|-------------|
| Tender row (even) | `.RowStyle` | GitHub: skopjehacklab | HIGH ✅ |
| Tender row (odd) | `.AltRowStyle` | GitHub: skopjehacklab | HIGH ✅ |
| Tender link | `.RowStyle td:nth-child(1) a[href]` | GitHub: CasperJS script | HIGH ✅ |
| Tender link (alt) | `.AltRowStyle td:nth-child(1) a[href]` | GitHub: CasperJS script | HIGH ✅ |
| Pagination status | `.PagerStyle` | GitHub: CasperJS script | HIGH ✅ |

#### Pagination Mechanism

**Type:** ASP.NET Dropdown
**Control ID:** `ctl00$ctl00$cphGlobal$cphPublicAccess$ucNotificationForACPP$gvNotifications$ctl13$ddlPageSelector`
**Indexing:** Zero-based (page 1 = option value 0)
**Validation:** Check `.PagerStyle` text matches expected range

```python
# Select page 2 (option value 1)
await page.select_option('select#ddlPageSelector', '1')
await page.wait_for_load_state('networkidle')

# Verify page loaded
pager_text = await page.inner_text('.PagerStyle')
assert 'до 20 од' in pager_text  # Shows "to 20 of"
```

#### Sample Tender Links

From the listings page, tender links follow this pattern:

```
#/dossie/c8d9ff87-d7a1-4cd2-95bf-3a56107439ae
#/dossie/18d0035d-158c-4df9-ad04-3e770c74a083
#/dossie/cb2e22be-a1e6-437d-aaf1-8367a38cd010
```

These are converted to full URLs:
```
https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{GUID}
```

Or direct ASP.NET URLs:
```
https://e-nabavki.gov.mk/PublicAccess/Dossie/dosieNotificationForACPP.aspx?Id={GUID}&Level=3
```

---

### 2.2 Other Categories ⚠️ REQUIRES INSPECTION

The following categories are **likely to exist** but require manual site exploration:

| Category | Possible Angular Route | Description | Priority |
|----------|----------------------|-------------|----------|
| **Awarded Tenders** | `#/awarded` or `#/decisions` | Tenders with award decisions | HIGH |
| **Cancelled Tenders** | `#/cancelled` | Cancelled procurements | MEDIUM |
| **Upcoming/Planned** | `#/planned` or `#/announcements` | Future opportunities | MEDIUM |
| **Historical/Archive** | Link exists in nav | Past tenders | LOW |
| **Contracts** | `#/contracts` | Signed contracts | MEDIUM |

**Action Required:** Manually explore the website navigation, sitemap, and search functionality to discover these URLs.

---

## 3. Tender Detail Pages

### 3.1 URL Patterns

**Primary Pattern:**
```
https://e-nabavki.gov.mk/PublicAccess/Dossie/dosieNotificationForACPP.aspx?Id={GUID}&Level={LEVEL}
```

**Angular Hash Pattern:**
```
https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/{GUID}
```

**Parameters:**
- `Id`: UUID/GUID identifier (e.g., `c8d9ff87-d7a1-4cd2-95bf-3a56107439ae`)
- `Level`: Integer, commonly `3` (procurement phase/detail level)

**Verified Sample URLs:**
1. https://e-nabavki.gov.mk/PublicAccess/Dossie/dosieNotificationForACPP.aspx?Id=c8d9ff87-d7a1-4cd2-95bf-3a56107439ae&Level=3
2. https://e-nabavki.gov.mk/PublicAccess/Dossie/dosieNotificationForACPP.aspx?Id=18d0035d-158c-4df9-ad04-3e770c74a083&Level=3
3. https://e-nabavki.gov.mk/PublicAccess/Dossie/dosieNotificationForACPP.aspx?Id=cb2e22be-a1e6-437d-aaf1-8367a38cd010&Level=3

---

### 3.2 Field Selectors (19 Fields Documented)

**ASP.NET Control ID Prefix:** `ctl00_ctl00_cphGlobal_cphPublicAccess_`

#### CRITICAL Fields

| Field | Selectors | Macedonian Label | Priority |
|-------|-----------|------------------|----------|
| **tender_id** | `label[label-for="ANNOUNCEMENT NUMBER DOSIE"] + label.dosie-value::text`<br>`label:contains("Број на оглас:") + label.dosie-value::text` | Број на оглас | CRITICAL |
| **title** | `label[label-for*="SUBJECT"] + label.dosie-value::text`<br>`label:contains("Предмет на договорот") + label.dosie-value::text` | Предмет на договорот | CRITICAL |
| **procuring_entity** | `#ctl00_ctl00_cphGlobal_cphPublicAccess_lblName`<br>`label:contains("Договорен орган") + label.dosie-value::text` | Назив на договорниот орган | CRITICAL |
| **closing_date** | `label:contains("Рок за поднесување") + label.dosie-value::text`<br>`label:contains("Краен рок") + label.dosie-value::text` | Рок за поднесување | CRITICAL |

#### HIGH Priority Fields

| Field | ASP.NET ID | CSS Selector | Macedonian Label |
|-------|------------|--------------|------------------|
| **procedure_type** | `lblProcedureType` | `#ctl00_ctl00_cphGlobal_cphPublicAccess_lblProcedureType` | Вид на постапка |
| **description** | `lblPodetalenOpis` | `#ctl00_ctl00_cphGlobal_cphPublicAccess_lblPodetalenOpis` | Подетален опис |
| **estimated_value_mkd** | `lblEstimatedContractValue` | `#ctl00_ctl00_cphGlobal_cphPublicAccess_lblEstimatedContractValue` | Проценета вредност |
| **actual_value_eur** | `lblAssignedContractValueVAT` | `#ctl00_ctl00_cphGlobal_cphPublicAccess_lblAssignedContractValueVAT` | Вредност со ДДВ |
| **status** | Auto-detect | Based on winner/dates | Статус |
| **winner** | Label search | `label:contains("Добитник") + label.dosie-value::text` | Добитник |

#### MEDIUM Priority Fields

| Field | ASP.NET ID | Macedonian Label |
|-------|------------|------------------|
| **cpv_code** | - | CPV |
| **category** | - | Вид на договорот |
| **contract_duration** | `lblContractPeriod` | Времетраење на договорот |
| **publication_date** | - | Датум на објавување |
| **opening_date** | - | Датум на отворање |
| **contract_signing_date** | `lblContractDate` | Датум на склучување |
| **contracting_entity_category** | `lblCategory` | Категорија на орган |

#### LOW Priority Fields

| Field | ASP.NET ID | Macedonian Label |
|-------|------------|------------------|
| **procurement_holder** | `lblNositel` | Носител на набавката |
| **bureau_delivery_date** | `lblDeliveryDate` | Датум на доставување до Биро |

---

### 3.3 Date Parsing

**Input Formats:**
- `DD.MM.YYYY` (e.g., 15.03.2024)
- `DD/MM/YYYY` (e.g., 15/03/2024)
- `YYYY-MM-DD` (ISO format)

**Output Format:** `YYYY-MM-DD` (ISO 8601)

**Macedonian Text Cleanup:**
- Remove: "година", "год.", "часот"
- Example: "15.03.2024 година" → "2024-03-15"

```python
def parse_date(date_string: str) -> Optional[str]:
    # Remove Macedonian text
    date_string = re.sub(r'(година|год\.?|часот)', '', date_string).strip()

    # Parse DD.MM.YYYY
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_string)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"

    return None
```

---

### 3.4 Currency Parsing

**Format:** European style with comma as decimal separator
- Example: `1.234.567,89 МКД`

**Currencies:**
- MKD (Macedonian Denar)
- EUR (Euro)

**Parsing Strategy:**
```python
def parse_currency(value_string: str) -> Optional[Decimal]:
    # Remove currency symbols
    number_str = re.sub(r'[^\d,\.]', '', value_string)

    # European format: 1.234.567,89
    if '.' in number_str and ',' in number_str:
        number_str = number_str.replace('.', '').replace(',', '.')
    elif ',' in number_str:
        number_str = number_str.replace(',', '.')

    return Decimal(number_str)
```

---

## 4. Document Endpoints

### 4.1 Document Link Selectors

Documents are typically PDFs attached to tender detail pages. Use multiple selectors for robustness:

```css
/* Direct PDF links */
a[href*="Download"]::attr(href)
a[href*=".pdf"]::attr(href)
a[href$=".pdf"]
a[href*="File"]::attr(href)

/* Download buttons */
a.btn-download
button.download

/* Document tables */
table.documents a
table a[href*="download"]

/* Macedonian text links */
a:contains("Преземи")    /* "Download" in Macedonian */
a:contains("Download")
```

### 4.2 Download URL Patterns

**Example Patterns:**
```
/PublicAccess/Documents/tender_ABC123.pdf
/PublicAccess/Download.aspx?docid=XYZ789
/files/tenders/2024/technical_spec.pdf
```

**URL Normalization:**
```python
if not link.startswith('http'):
    link = 'https://e-nabavki.gov.mk' + link
```

### 4.3 Document Types

Expected document types:
- Technical specifications (PDF)
- Tender documentation packages (PDF/ZIP)
- Contract templates (PDF)
- Amendments and modifications (PDF)
- Q&A documents (PDF)
- Award decisions (PDF)

### 4.4 File Size Support

**Scraper Configuration:**
- Maximum file size: 50MB
- Warning threshold: 20MB
- Download timeout: 180 seconds (3 minutes)

---

## 5. Profile Pages

### 5.1 Entity/Organization Profiles ⚠️ UNKNOWN

**Description:** Procuring entity/organization information pages

**Possible URL Patterns:**
```
/PublicAccess/Entity.aspx?id={ENTITY_ID}
/PublicAccess/Organization.aspx?id={ORG_ID}
#/entity/{ENTITY_ID}
```

**Status:** Not documented - requires manual exploration

**Discovery Method:**
1. Look for organization name links on tender detail pages
2. Check sitemap for entity directory
3. Search for "организации" or "органи" in navigation

---

### 5.2 Supplier/Contractor Profiles ⚠️ UNKNOWN

**Description:** Supplier/bidder company profile pages

**Possible URL Patterns:**
```
/PublicAccess/Supplier.aspx?id={SUPPLIER_ID}
/PublicAccess/Contractor.aspx?id={CONTRACTOR_ID}
#/supplier/{SUPPLIER_ID}
```

**Status:** Not documented - requires manual exploration

**Discovery Method:**
1. Look for winner/supplier name links on awarded tenders
2. Check if supplier names are clickable
3. Explore sitemap for supplier directory

---

## 6. Additional Features

### 6.1 Clarifications/Q&A Section ⚠️ UNKNOWN

**Description:** Questions and answers related to specific tenders

**Possible Locations:**
- Within tender detail page (tab or accordion section)
- Separate page linked from tender
- Timeline/activity feed

**Action Required:** Inspect tender detail pages for Q&A sections

---

### 6.2 Modifications/Amendments ⚠️ UNKNOWN

**Description:** Changes to tender specifications or deadlines

**Possible Locations:**
- Amendment documents in attachments section
- Timeline/history section on detail page
- Separate "Amendments" tab

**Action Required:** Look for "Измени", "Дополнувања", "Amendments"

---

### 6.3 Decision Announcements

**Description:** Award decisions and tender outcomes

**Current Implementation:**
- Winner field extracted from detail page
- Status auto-detected as "awarded" when winner present

**Potential Separate Section:**
- May have dedicated "Decisions" category
- Could be in "Awarded" or "Completed" tenders section

---

### 6.4 Other Navigation Pages

| Page | URL | Status |
|------|-----|--------|
| **Ask Question** | `#/askquestion` | ✅ Verified link |
| **Sitemap** | `#/sitemap` | ✅ Verified link |
| **Archive** | Unknown | ⚠️ Link exists, URL unknown |
| **Home** | `#/home` | ✅ Verified link |

---

## 7. API Endpoints Discovery

### 7.1 Current Status ⚠️ NOT DOCUMENTED

The website's API endpoints are **not publicly documented**. The site uses a combination of:
- AngularJS AJAX calls (XHR/Fetch)
- ASP.NET WebForms postbacks
- Hash-based routing with client-side rendering

### 7.2 Discovery Method

**Use Browser DevTools to capture network traffic:**

```javascript
// Open DevTools → Network Tab → Filter by XHR/Fetch
// Navigate to: https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices
// Observe network requests as page loads

// Expected patterns:
// - /PublicAccess/api/notices
// - /PublicAccess/api/tenders
// - /PublicAccess/api/dossie/{id}
// - /api/procurement/search
```

**Steps:**
1. Open browser with DevTools (F12)
2. Go to Network tab
3. Filter by XHR or Fetch
4. Navigate to notices page
5. Wait for page to load
6. Examine XHR requests
7. Document:
   - Request URL
   - Request method (GET/POST)
   - Request headers
   - Request payload (if POST)
   - Response format (JSON/XML)

### 7.3 Likely Endpoint Patterns

Based on common patterns:

```
GET  /PublicAccess/api/notices?page=1&pageSize=10
GET  /PublicAccess/api/dossie/{guid}
POST /PublicAccess/api/search
     { "category": "IT", "dateFrom": "2024-01-01", ... }
GET  /PublicAccess/api/entity/{entityId}
GET  /PublicAccess/api/documents/{dossierId}
```

---

## 8. Extraction Strategy

### 8.1 Five-Level Fallback Chain

The scraper implements a robust fallback strategy:

| Level | Type | Reliability | Example |
|-------|------|-------------|---------|
| **1** | ASP.NET control IDs | HIGH ✅ | `#ctl00_ctl00_cphGlobal_cphPublicAccess_lblName` |
| **2** | CSS selectors | MEDIUM | `.dosie-value`, `.RowStyle` |
| **3** | Label-based extraction | MEDIUM | Find "Назив:" → extract next element |
| **4** | Regex pattern matching | LOW | `CPV[:\s]+([0-9-]+)` |
| **5** | Default/null with logging | FALLBACK | Log error, return None |

### 8.2 Label-Based Extraction

When ASP.NET IDs fail, search for Macedonian labels:

```python
def extract_by_label(response, macedonian_label: str) -> Optional[str]:
    # Find label containing text
    label = response.xpath(f"//label[contains(text(), '{macedonian_label}')]")

    # Extract next sibling or adjacent element
    value = label.xpath("following-sibling::label[@class='dosie-value']/text()").get()

    return value.strip() if value else None
```

### 8.3 Status Auto-Detection

When status field is missing, infer from other fields:

```python
def detect_status(tender: dict) -> str:
    if tender.get('winner'):
        return 'awarded'
    elif tender.get('closing_date'):
        closing = parse_date(tender['closing_date'])
        if closing and closing > datetime.now():
            return 'active'
        else:
            return 'closed'
    return 'published'
```

---

## 9. Implementation Guide

### 9.1 Scraping Workflow

```
1. Start URL: https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices
   ↓
2. Playwright renders page (wait for networkidle + .RowStyle)
   ↓
3. Extract tender links from first column of .RowStyle/.AltRowStyle rows
   ↓
4. For each tender link:
   a. Convert to full URL
   b. Open with Playwright
   c. Wait for label.dosie-value
   d. Extract all 19 fields using fallback chain
   e. Extract document links
   ↓
5. Process pagination (dropdown → next page → repeat)
   ↓
6. Save to database
```

### 9.2 Rate Limiting

**Scraper Configuration:**
- Download delay: 0.25 seconds
- Concurrent requests: 4
- AutoThrottle enabled: 0.5s - 2.0s delay
- User-Agent: Proper identification

### 9.3 Error Handling

```python
# Playwright timeout handling
try:
    await page.wait_for_selector('.RowStyle', timeout=10000)
except TimeoutError:
    logger.error("Tender listing failed to load")
    # Retry or skip

# Field extraction failure
if not tender_id:
    logger.error(f"Failed to extract tender_id from {url}")
    # Use URL parameter as fallback
    tender_id = re.search(r'Id=([^&]+)', url).group(1)
```

---

## 10. Testing Recommendations

### 10.1 Test Sample URLs

Use these verified tender URLs for testing:

```python
test_urls = [
    'https://e-nabavki.gov.mk/PublicAccess/Dossie/dosieNotificationForACPP.aspx?Id=c8d9ff87-d7a1-4cd2-95bf-3a56107439ae&Level=3',
    'https://e-nabavki.gov.mk/PublicAccess/Dossie/dosieNotificationForACPP.aspx?Id=18d0035d-158c-4df9-ad04-3e770c74a083&Level=3',
    'https://e-nabavki.gov.mk/PublicAccess/Dossie/dosieNotificationForACPP.aspx?Id=cb2e22be-a1e6-437d-aaf1-8367a38cd010&Level=3',
]
```

### 10.2 Field Extraction Success Criteria

**Target Success Rates:**
- Critical fields (tender_id, title, entity, closing_date): 100%
- High priority fields: 90%+
- Medium priority fields: 80%+
- Low priority fields: 60%+

### 10.3 Test Coverage Matrix

| Test Type | Tenders to Test | Focus Areas |
|-----------|-----------------|-------------|
| **Basic Extraction** | 3 active tenders | All 19 fields |
| **Status Variety** | 2 awarded, 2 closed, 2 active | Status detection |
| **Procurement Types** | 5 different types | Category-specific fields |
| **Date Parsing** | 10 tenders | All date formats |
| **Currency Values** | 10 tenders | MKD and EUR parsing |
| **Document Downloads** | 5 tenders | PDF extraction |
| **Pagination** | Pages 1-3 | Dropdown navigation |

### 10.4 Validation Checklist

- [ ] All critical fields extracted successfully
- [ ] Dates converted to ISO format (YYYY-MM-DD)
- [ ] Currency values parsed as Decimal
- [ ] Cyrillic text preserved (Macedonian)
- [ ] Document URLs converted to absolute
- [ ] Status auto-detection works
- [ ] Pagination loads new tenders
- [ ] No duplicate tenders scraped
- [ ] Error logging captures failures
- [ ] Rate limiting respected

---

## Summary & Next Steps

### ✅ What We Know (High Confidence)

1. **Listings Page Structure**
   - URL: `#/notices`
   - Selectors: `.RowStyle`, `.AltRowStyle`
   - Tender links: First column `<a>` tags
   - Pagination: ASP.NET dropdown

2. **Detail Page Fields**
   - 19 documented fields with selectors
   - 12 ASP.NET control IDs verified
   - Label-based fallbacks defined
   - Date/currency parsing implemented

3. **Document Extraction**
   - 6+ selector strategies
   - PDF link patterns identified
   - URL normalization rules

4. **Technical Requirements**
   - Playwright mandatory for JavaScript rendering
   - Wait conditions documented
   - Rate limiting configured

### ⚠️ What Requires Investigation

1. **Missing Categories**
   - Awarded tenders URL
   - Cancelled tenders URL
   - Historical/archive URL
   - Upcoming tenders URL

2. **API Endpoints**
   - No public documentation
   - Requires browser DevTools inspection
   - XHR/Fetch request capture needed

3. **Profile Pages**
   - Entity/organization profiles
   - Supplier/contractor profiles

4. **Additional Features**
   - Q&A sections
   - Amendments/modifications
   - Decision announcements as separate pages

### 📋 Immediate Action Items

**Priority 1: API Discovery (1-2 hours)**
```bash
# Use browser DevTools
1. Open https://e-nabavki.gov.mk/PublicAccess/home.aspx#/notices
2. Open DevTools (F12) → Network → XHR/Fetch
3. Let page load and document all API calls
4. Note request URLs, methods, and response formats
5. Test pagination and document those API calls
```

**Priority 2: Category Exploration (1 hour)**
```bash
# Manually explore site navigation
1. Check sitemap page for all categories
2. Look for "Archived", "Awarded", "Cancelled" links
3. Document URLs for each category found
4. Test if same selectors work on other categories
```

**Priority 3: Field Validation (2 hours)**
```bash
# Test on 10+ real tenders
1. Use Playwright to render sample URLs
2. Extract all 19 fields
3. Log success/failure per field
4. Identify which fallback level was used
5. Calculate overall success rate
6. Fix failing selectors
```

**Priority 4: Document Structure (30 minutes)**
```bash
# Inspect document attachment sections
1. Open 5 different tender detail pages
2. Locate document/attachment sections
3. Document the HTML structure
4. Test document link selectors
5. Verify download functionality
```

---

## Appendix: Complete Selector Reference

### Listings Page Selectors

```css
/* Tender rows */
.RowStyle                                      /* Even rows */
.AltRowStyle                                   /* Odd rows */

/* Tender links */
.RowStyle td:nth-child(1) a[href]              /* Link in first column */
.AltRowStyle td:nth-child(1) a[href]           /* Alt row link */

/* Pagination */
.PagerStyle                                    /* Pagination status text */
#ctl00$ctl00$cphGlobal$cphPublicAccess$ucNotificationForACPP$gvNotifications$ctl13$ddlPageSelector
```

### Detail Page Selectors (ASP.NET IDs)

```css
/* Critical Fields */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblName                      /* Organization */

/* Dates */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblContractDate              /* Contract date */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblDeliveryDate              /* Delivery date */

/* Values */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblEstimatedContractValue    /* Estimated value */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblAssignedContractValueVAT  /* Actual value */

/* Other */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblProcedureType             /* Procedure type */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblCategory                  /* Category */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblPredmet                   /* Subject */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblSubjectOfProcurement      /* Procurement subject */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblPodetalenOpis             /* Description */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblContractPeriod            /* Duration */
#ctl00_ctl00_cphGlobal_cphPublicAccess_lblNositel                   /* Holder */
```

### Document Selectors

```css
/* PDF links */
a[href*="Download"]::attr(href)
a[href*=".pdf"]::attr(href)
a[href$=".pdf"]
a[href*="File"]::attr(href)

/* Buttons */
a.btn-download
button.download

/* Tables */
table.documents a
table a[href*="download"]

/* Text-based */
a:contains("Преземи")
a:contains("Download")
```

---

## References

**Official Sources:**
- Website: https://e-nabavki.gov.mk
- Ministry: https://finance.gov.mk/е-јавни-набавки/?lang=en
- Procurement Bureau: https://www.bjn.gov.mk/kontakt/

**Open Source Projects:**
- GitHub: https://github.com/skopjehacklab/e-nabavki
- CasperJS Script: https://raw.githubusercontent.com/skopjehacklab/e-nabavki/master/e-nabavki.gov.mk.js
- Settings: https://raw.githubusercontent.com/skopjehacklab/e-nabavki/master/settings.ini.example

**Internal Documentation:**
- Scraper: `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/spiders/nabavki_spider.py`
- Selector Mapping: `/Users/tamsar/Downloads/nabavkidata/scraper/E_NABAVKI_SELECTORS_MAPPING.json`
- Inspection Report: `/Users/tamsar/Downloads/nabavkidata/scraper/AGENT_A_INSPECTION_REPORT.md`

---

**Analysis Completed:** 2025-11-24
**Last Updated:** 2025-11-24
**Status:** Comprehensive mapping complete. API endpoints and additional categories require manual inspection.
