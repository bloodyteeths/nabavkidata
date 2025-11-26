# Field Extraction Quick Reference

**For Agent A:** Use this as a checklist when identifying selectors from e-nabavki.gov.mk

---

## Critical Fields (MUST extract successfully)

### tender_id
**Priority:** CRITICAL
**Macedonian labels:** Број, Референца, ID
**English labels:** Number, Reference, ID
**Expected format:** String (alphanumeric, may contain slashes/dashes)
**Extraction sources:**
- [ ] URL parameter (check ?id=, ?tenderid=, ?tender=)
- [ ] Page heading/subheading
- [ ] Table row labeled "Број" or "Reference"
- [ ] Breadcrumb navigation
- [ ] Meta tags

### title
**Priority:** CRITICAL
**Macedonian labels:** Назив, Име на набавка
**English labels:** Title, Procurement Name
**Expected format:** Text (often multi-line)
**Extraction sources:**
- [ ] Main heading (h1, h2)
- [ ] Page title
- [ ] Table row labeled "Назив"
- [ ] Summary section

### procuring_entity
**Priority:** HIGH
**Macedonian labels:** Нарачател, Договорен орган
**English labels:** Contracting Authority, Procuring Entity
**Expected format:** Organization name
**Extraction sources:**
- [ ] Entity info section
- [ ] Table row labeled "Нарачател"
- [ ] Sidebar or header
- [ ] Contact information section

### closing_date
**Priority:** HIGH
**Macedonian labels:** Затворање, Краен рок, Рок за поднесување
**English labels:** Closing, Deadline, Submission Deadline
**Expected format:** Date (various formats)
**Extraction sources:**
- [ ] Dates section
- [ ] Table row labeled "Краен рок"
- [ ] Important dates panel
- [ ] Status section

---

## Important Fields (Should extract if available)

### description
**Macedonian labels:** Опис, Предмет на набавка
**English labels:** Description, Subject
**Expected format:** Long text
**Extraction sources:**
- [ ] Main content area
- [ ] Description section
- [ ] Summary/overview

### category
**Macedonian labels:** Категорија, Тип
**English labels:** Category, Type
**Expected format:** String
**Extraction sources:**
- [ ] Category badge/tag
- [ ] Classification section
- [ ] Metadata area
- [ ] Keyword analysis (fallback)

### cpv_code
**Macedonian labels:** CPV, CPV Код
**English labels:** CPV, CPV Code
**Expected format:** Numbers with dashes (e.g., 45000000-7)
**Extraction sources:**
- [ ] Classification section
- [ ] CPV section
- [ ] Metadata table

### opening_date
**Macedonian labels:** Отворање, Датум на отворање
**English labels:** Opening, Opening Date
**Expected format:** Date
**Extraction sources:**
- [ ] Dates section
- [ ] Timeline
- [ ] Important dates

### publication_date
**Macedonian labels:** Објавено, Датум на објава
**English labels:** Published, Publication Date
**Expected format:** Date
**Extraction sources:**
- [ ] Header metadata
- [ ] Dates section
- [ ] Footer

---

## Financial Fields

### estimated_value_mkd
**Macedonian labels:** Проценета вредност (МКД), Вредност МКД
**English labels:** Estimated Value (MKD), Value MKD
**Expected format:** Number with MKD/денари
**Extraction sources:**
- [ ] Financial section
- [ ] Budget information
- [ ] Value table (look for MKD row)

### estimated_value_eur
**Macedonian labels:** Проценета вредност (ЕУР), Вредност ЕУР
**English labels:** Estimated Value (EUR), Value EUR
**Expected format:** Number with EUR/€
**Extraction sources:**
- [ ] Financial section
- [ ] Value table (look for EUR row)

### awarded_value_mkd
**Macedonian labels:** Доделена вредност (МКД), Вредност на договор МКД
**English labels:** Awarded Value (MKD), Contract Value MKD
**Expected format:** Number with MKD/денари
**Extraction sources:**
- [ ] Award decision section
- [ ] Contract information
- [ ] Results section

### awarded_value_eur
**Macedonian labels:** Доделена вредност (ЕУР), Вредност на договор ЕУР
**English labels:** Awarded Value (EUR), Contract Value EUR
**Expected format:** Number with EUR/€
**Extraction sources:**
- [ ] Award decision section
- [ ] Contract information
- [ ] Results section

---

## Outcome Fields

### status
**Macedonian labels:** Статус, Состојба
**English labels:** Status, State
**Expected values:** отворен, затворен, доделен, откажан
**Extraction sources:**
- [ ] Status badge/indicator
- [ ] Page header
- [ ] Sidebar
- [ ] Automatic detection (fallback)

### winner
**Macedonian labels:** Добитник, Избран понудувач, Договорен оператор
**English labels:** Winner, Selected Bidder, Contractor
**Expected format:** Company name
**Extraction sources:**
- [ ] Award section
- [ ] Results section
- [ ] Contract information
- [ ] Winner announcement

---

## NEW Fields (To be added)

### procedure_type
**Macedonian labels:** Вид на постапка, Тип на постапка
**English labels:** Procedure Type, Type of Procedure
**Expected format:** String (e.g., "Отворена постапка", "Ограничена постапка")
**Extraction sources:**
- [ ] Procedure information section
- [ ] Metadata table
- [ ] Classification area

### contract_signing_date
**Macedonian labels:** Датум на потпишување, Договор потпишан
**English labels:** Signing Date, Contract Signed
**Expected format:** Date
**Extraction sources:**
- [ ] Contract section
- [ ] Award decision
- [ ] Important dates

### contract_duration
**Macedonian labels:** Траење на договор, Период
**English labels:** Contract Duration, Period
**Expected format:** String (e.g., "12 месеци", "2 години")
**Extraction sources:**
- [ ] Contract details
- [ ] Duration section
- [ ] Terms section

### contracting_entity_category
**Macedonian labels:** Категорија на орган, Тип на нарачател
**English labels:** Entity Category, Authority Type
**Expected format:** String (e.g., "Локална самоуправа", "Министерство")
**Extraction sources:**
- [ ] Entity information
- [ ] Classification section
- [ ] Organization details

### procurement_holder
**Macedonian labels:** Носител на постапка, Раководител
**English labels:** Procurement Holder, Manager
**Expected format:** Person name or department
**Extraction sources:**
- [ ] Contact information
- [ ] Responsible person section
- [ ] Procedure details

### bureau_delivery_date
**Macedonian labels:** Датум на доставување до биро, Доставено до биро
**English labels:** Bureau Delivery Date, Delivered to Bureau
**Expected format:** Date
**Extraction sources:**
- [ ] Administrative dates
- [ ] Process timeline
- [ ] Procedural information

---

## Extraction Testing Checklist

For each field, verify:

### 1. Primary Selector Works
```python
# Test in Scrapy shell
response.css('YOUR_SELECTOR::text').get()
```

### 2. Label-based Fallback
```python
# Search for Macedonian label
"Назив" in response.text
# Should find the label, then extract adjacent value
```

### 3. Multiple Tenders
- [ ] Test on at least 3 different tender pages
- [ ] Test on different procurement types
- [ ] Test on different statuses (open, closed, awarded)

### 4. Edge Cases
- [ ] Missing optional fields
- [ ] Different date formats
- [ ] Different number formats
- [ ] Multiple currencies
- [ ] Very long text fields
- [ ] Special characters in text

---

## Common Patterns to Look For

### Tables
```html
<table>
  <tr>
    <td>Назив:</td>
    <td>Value here</td>
  </tr>
</table>
```
**Selector pattern:** Look for td pairs, use label matching

### Definition Lists
```html
<dl>
  <dt>Нарачател:</dt>
  <dd>Value here</dd>
</dl>
```
**Selector pattern:** `dt:contains("Label") + dd::text`

### Divs with Classes
```html
<div class="tender-info">
  <div class="label">Број:</div>
  <div class="value">ABC-123</div>
</div>
```
**Selector pattern:** `div.value::text` with context

### Spans in Rows
```html
<div class="row">
  <span class="label">Краен рок:</span>
  <span class="value">15.03.2024</span>
</div>
```
**Selector pattern:** `span.value::text`

---

## Document Link Patterns

Look for these patterns when extracting documents:

### Direct PDF Links
```html
<a href="/files/tender123.pdf">Преземи</a>
```
**Selector:** `a[href$=".pdf"]::attr(href)`

### Download Buttons
```html
<a class="btn-download" href="...">Download Document</a>
```
**Selector:** `a.btn-download::attr(href)`

### Document Tables
```html
<table class="documents">
  <tr>
    <td>Technical Specification</td>
    <td><a href="...">Download</a></td>
  </tr>
</table>
```
**Selector:** `table.documents a::attr(href)`

### Icon Links
```html
<a href="/doc.pdf"><i class="icon-pdf"></i> Document Name</a>
```
**Selector:** `a:has(i.icon-pdf)::attr(href)`

---

## Validation After Extraction

For each page tested, verify:

### Data Quality
- [ ] tender_id is unique and valid
- [ ] title is meaningful (not empty, not default)
- [ ] dates are in correct format (YYYY-MM-DD)
- [ ] dates follow logical order (publication <= opening <= closing)
- [ ] currency values are positive numbers
- [ ] status is one of: open, closed, awarded, cancelled, draft

### Completeness
- [ ] All critical fields extracted
- [ ] At least 70% of important fields extracted
- [ ] Document links found (if available)

### Edge Cases
- [ ] Handles missing optional fields gracefully
- [ ] Handles different date formats
- [ ] Handles currency with different separators
- [ ] Handles Macedonian Cyrillic text correctly

---

## Selector Update Template

When updating `extractors.py`, use this format:

```python
'FIELD_NAME': [
    # Level 1: Primary CSS (from your inspection)
    {'type': 'css', 'selector': 'ACTUAL_CSS_SELECTOR::text', 'priority': 1},

    # Level 1b: Alternative CSS (if multiple possible structures)
    {'type': 'css', 'selector': 'ALTERNATIVE_CSS::text', 'priority': 1},

    # Level 2: XPath (alternative approach)
    {'type': 'xpath', 'selector': '//ACTUAL_XPATH/text()', 'priority': 2},

    # Level 3: Label-based (Macedonian first, then English)
    {'type': 'label', 'macedonian': 'MACEDONIAN_LABEL', 'english': 'ENGLISH_LABEL', 'priority': 3},

    # Level 4: Regex (last resort before default)
    {'type': 'regex', 'pattern': r'PATTERN_HERE', 'priority': 4},

    # Level 5: Default
    {'type': 'default', 'value': None, 'log_level': 'WARNING'},
],
```

---

## Example: Real Selector Update

**Before (placeholder):**
```python
'closing_date': [
    {'type': 'css', 'selector': 'span.closing-date::text', 'priority': 1},
    ...
]
```

**After (real selectors from inspection):**
```python
'closing_date': [
    # Primary: Found in tender details table
    {'type': 'css', 'selector': 'table.tender-info tr:contains("Краен рок") td.value::text', 'priority': 1},

    # Alternative: Sometimes in dates section
    {'type': 'css', 'selector': 'div.important-dates span.deadline::text', 'priority': 1},

    # XPath alternative
    {'type': 'xpath', 'selector': '//tr[contains(., "Краен рок")]/td[@class="value"]/text()', 'priority': 2},

    # Label-based fallback
    {'type': 'label', 'macedonian': 'Краен рок', 'english': 'Deadline', 'priority': 3},
    {'type': 'label', 'macedonian': 'Рок за поднесување', 'english': 'Submission Deadline', 'priority': 3},

    # Default
    {'type': 'default', 'value': None, 'log_level': 'WARNING'},
],
```

---

## Next Steps

1. **Inspect e-nabavki.gov.mk tender detail pages** using browser DevTools
2. **Document actual HTML structure** (take screenshots/notes)
3. **Identify CSS selectors** for each field
4. **Update `extractors.py`** with real selectors
5. **Test on multiple tenders** (at least 10)
6. **Verify extraction statistics** (aim for >80% success on critical fields)
7. **Iterate and refine** selectors as needed

---

**Remember:** The architecture is designed to be resilient. Even if some selectors fail, the fallback chain will try alternatives. Focus on getting the most common structure first, then test edge cases.
