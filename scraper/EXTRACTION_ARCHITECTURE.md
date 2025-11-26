# Tender Detail Extraction Architecture

**Author:** Agent B - Tender Detail Extraction Logic Architect
**Date:** 2025-11-24
**Status:** Architecture Complete - Awaiting Real Selectors from Agent A

---

## Table of Contents

1. [Overview](#overview)
2. [Design Philosophy](#design-philosophy)
3. [Field Extraction Strategy](#field-extraction-strategy)
4. [Core Components](#core-components)
5. [Fields Extracted](#fields-extracted)
6. [Multi-Tier Fallback System](#multi-tier-fallback-system)
7. [Date Parsing](#date-parsing)
8. [Currency Parsing](#currency-parsing)
9. [Status Detection](#status-detection)
10. [Document Extraction](#document-extraction)
11. [Data Validation](#data-validation)
12. [Error Handling](#error-handling)
13. [Monitoring & Statistics](#monitoring--statistics)
14. [Integration Guide](#integration-guide)

---

## Overview

The extraction architecture is designed to extract tender data from **e-nabavki.gov.mk** tender detail pages with maximum resilience to website structure changes.

**Key Features:**
- 5-level fallback chain for every field
- Multi-format date and currency parsing
- Intelligent status detection
- Automatic document classification
- Comprehensive validation
- Extraction success tracking

---

## Design Philosophy

### Resilience Over Performance

The architecture prioritizes **resilience** over speed. Each field has multiple extraction strategies, ensuring data continues to flow even if the website structure changes.

### Fail Gracefully

If a field cannot be extracted:
1. Try all fallback strategies
2. Log the failure with appropriate severity
3. Continue extracting other fields
4. Never crash the spider

### Observe Everything

Track extraction success rates for every field to detect structure changes early.

---

## Field Extraction Strategy

### 5-Level Fallback Chain

Every field extraction follows this pattern:

```
Level 1: Primary CSS Selector (fastest, most specific)
    ↓ (if fails)
Level 2: XPath Alternative (different DOM approach)
    ↓ (if fails)
Level 3: Label-based Extraction (find "Назив:" then extract adjacent value)
    ↓ (if fails)
Level 4: Regex Pattern Matching (content-based, structure-independent)
    ↓ (if fails)
Level 5: Default/Null Handling (log failure, return default)
```

### Example: Title Field

```python
'title': [
    # Level 1: Primary CSS
    {'type': 'css', 'selector': 'h1.tender-title::text', 'priority': 1},

    # Level 2: XPath Alternative
    {'type': 'xpath', 'selector': '//h1/text()', 'priority': 2},

    # Level 3: Label-based (Macedonian & English)
    {'type': 'label', 'macedonian': 'Назив', 'english': 'Title', 'priority': 3},

    # Level 4: Regex
    {'type': 'regex', 'pattern': r'(?:Назив|Title)[:\s]+(.+?)(?:<|$)', 'priority': 4},

    # Level 5: Default
    {'type': 'default', 'value': None, 'log_level': 'ERROR'},
]
```

---

## Core Components

### 1. `TenderExtractor`

Main extraction orchestrator. Manages field extraction, validation, and statistics.

**Key Methods:**
- `extract_field(response, field_name)` - Extract single field with fallbacks
- `extract_all_fields(response)` - Extract all fields from page
- `extract_documents(response, tender_id)` - Extract document links
- `get_statistics()` - Get extraction statistics
- `log_statistics()` - Log comprehensive stats

### 2. `DateParser`

Robust date parser supporting multiple formats.

**Supported Formats:**
- `dd.mm.yyyy` (15.03.2024)
- `dd/mm/yyyy` (15/03/2024)
- `yyyy-mm-dd` (2024-03-15)
- `dd-mm-yyyy` (15-03-2024)
- Macedonian month names ("15 март 2024")
- Relative dates ("денес", "вчера")

**Key Methods:**
- `parse(date_string)` - Parse any date format

### 3. `CurrencyParser`

Multi-format currency value parser.

**Supported Formats:**
- European: `1.234.567,89` or `1 234 567,89`
- US: `1,234,567.89`
- Mixed: `1.234.567` or `1,234,567`
- Currency symbols: MKD, денари, EUR, €
- Ranges: `"100,000 - 200,000 MKD"` (extracts first value)

**Key Methods:**
- `parse(value_string, currency)` - Parse currency value

### 4. `StatusDetector`

Intelligent tender status detection using multiple signals.

**Status Values:**
- `open` - Actively accepting bids
- `closed` - Deadline passed, no winner
- `awarded` - Winner announced
- `cancelled` - Tender cancelled
- `draft` - Not yet published

**Detection Strategy:**
1. Check explicit status field
2. Check winner field presence
3. Check awarded values
4. Compare closing date with today
5. Keyword analysis in page text
6. Default to 'open'

**Key Methods:**
- `detect(tender_data, page_text)` - Detect status from signals

### 5. `DocumentExtractor`

Extract and classify documents from tender pages.

**Document Types:**
- `tender_document` - Main tender documentation
- `technical_spec` - Technical specifications
- `amendment` - Amendments and addenda
- `award` - Award decision notices
- `contract` - Signed contracts
- `other` - Miscellaneous documents

**Key Methods:**
- `extract_documents(response, tender_id)` - Extract all documents
- Auto-classification based on filename/link text

### 6. `ExtractionStats`

Track extraction success/failure for monitoring.

**Tracks:**
- Total extractions
- Per-field success/failure counts
- Fallback level usage distribution
- Success rates

**Key Methods:**
- `record_success(field, level)` - Record successful extraction
- `record_failure(field)` - Record failed extraction
- `get_success_rate(field)` - Calculate success rate
- `log_statistics()` - Log comprehensive report

---

## Fields Extracted

### Core Fields (Existing)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tender_id` | String | Yes | Unique tender identifier |
| `title` | Text | Yes | Tender title |
| `description` | Text | No | Tender description |
| `category` | String | No | Tender category (IT, Construction, etc.) |
| `procuring_entity` | String | No | Contracting authority name |
| `cpv_code` | String | No | Common Procurement Vocabulary code |

### Date Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `opening_date` | Date | No | Tender opening date |
| `closing_date` | Date | No | Submission deadline |
| `publication_date` | Date | No | Publication date |

### Financial Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `estimated_value_mkd` | Decimal | No | Estimated value in MKD |
| `estimated_value_eur` | Decimal | No | Estimated value in EUR |
| `awarded_value_mkd` | Decimal | No | Awarded value in MKD |
| `awarded_value_eur` | Decimal | No | Awarded value in EUR |

### Outcome Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | String | No | Tender status (open/closed/awarded/cancelled) |
| `winner` | String | No | Winning bidder name |

### NEW Fields (Added)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `procedure_type` | String | No | Procurement procedure type |
| `contract_signing_date` | Date | No | Contract signature date |
| `contract_duration` | String | No | Contract duration/period |
| `contracting_entity_category` | String | No | Type/category of contracting authority |
| `procurement_holder` | String | No | Person/entity managing the procurement |
| `bureau_delivery_date` | Date | No | Date delivered to procurement bureau |

### Metadata Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_url` | String | Yes | Source page URL |
| `language` | String | Yes | Content language (default: 'mk') |
| `scraped_at` | DateTime | Yes | Extraction timestamp |

---

## Multi-Tier Fallback System

### Extractor Types

#### 1. CSS Selector
```python
{'type': 'css', 'selector': 'span.tender-id::text', 'priority': 1}
```
Fast, specific, breaks when HTML structure changes.

#### 2. XPath
```python
{'type': 'xpath', 'selector': '//span[@class="tender-id"]/text()', 'priority': 2}
```
Alternative DOM traversal approach.

#### 3. Label-based
```python
{'type': 'label', 'macedonian': 'Назив', 'english': 'Title', 'priority': 3}
```
Finds label text, extracts adjacent value. Resilient to structure changes.

**Patterns tried:**
- `Label: Value` (inline)
- `<td>Label</td><td>Value</td>` (table)
- `<div>Label</div><div>Value</div>` (divs)

#### 4. Regex
```python
{'type': 'regex', 'pattern': r'Назив[:\s]+(.+?)(?:<|$)', 'priority': 4}
```
Content-based extraction. Most resilient but slowest.

#### 5. URL Parameter
```python
{'type': 'url_param', 'param_names': ['id', 'tenderid'], 'priority': 1}
```
Extract from URL query string.

#### 6. Keyword Analysis
```python
{'type': 'keyword_analysis', 'priority': 4}
```
Content-based classification (for category field).

#### 7. Default
```python
{'type': 'default', 'value': None, 'log_level': 'ERROR'}
```
Fallback when all strategies fail.

---

## Date Parsing

### Supported Formats

```python
# Standard formats
15.03.2024      # dd.mm.yyyy (most common)
15/03/2024      # dd/mm/yyyy
2024-03-15      # yyyy-mm-dd (ISO)
15-03-2024      # dd-mm-yyyy

# Macedonian month names
15 март 2024    # day month year
15 септември 2024

# Relative dates
денес           # today
вчера           # yesterday
```

### Usage

```python
from extractors import DateParser

parser = DateParser()
date_obj = parser.parse("15.03.2024")  # Returns date(2024, 3, 15)
date_obj = parser.parse("15 март 2024")  # Returns date(2024, 3, 15)
```

### Validation

- Dates must be between 2000-2050
- Invalid dates return `None`
- Logs debug message for unparseable dates

---

## Currency Parsing

### Supported Formats

```python
# European format (Macedonia standard)
1.234.567,89    # Dot for thousands, comma for decimal
1 234 567,89    # Space for thousands

# US format
1,234,567.89    # Comma for thousands, dot for decimal

# No decimal
1.234.567       # European thousands
1,234,567       # US thousands

# With currency symbols
1.234.567,89 MKD
1.234.567,89 денари
€1,234,567.89

# Ranges
100,000 - 200,000 MKD    # Extracts first value: 100,000
```

### Smart Format Detection

The parser automatically detects whether comma or dot is the decimal separator:

1. If both present: last separator is decimal
2. If only one: position determines meaning
   - Last 2-3 digits → decimal separator
   - More digits → thousands separator

### Usage

```python
from extractors import CurrencyParser

parser = CurrencyParser()
value = parser.parse("1.234.567,89 MKD", currency='MKD')
# Returns Decimal('1234567.89')
```

### Validation

- Values must be positive
- Values > 10 billion trigger warning
- Returns `Decimal` for precision
- Handles ranges by extracting first value

---

## Status Detection

### Detection Logic

```python
# Priority order:
1. Explicit status field (if present)
2. Winner field present → 'awarded'
3. Awarded values present → 'awarded'
4. Closing date in past → 'closed'
5. Keyword analysis (отворен, затворен, etc.)
6. Default → 'open'
```

### Keywords

**Macedonian & English:**

| Status | Keywords |
|--------|----------|
| open | отворен, активен, open, active, објавен |
| closed | затворен, истечен, closed, expired, завршен |
| awarded | доделен, awarded, договор потпишан, contract signed, избран |
| cancelled | откажан, поништен, cancelled, canceled, annulled |
| draft | нацрт, draft, во подготовка, in preparation |

### Usage

```python
from extractors import StatusDetector

detector = StatusDetector()
status = detector.detect(tender_data, page_text)
# Returns: 'open', 'closed', 'awarded', 'cancelled', or 'draft'
```

---

## Document Extraction

### Document Types

Auto-classified based on filename and link text:

| Type | Keywords |
|------|----------|
| tender_document | тендер, tender, набавка, procurement, јавен оглас, public notice |
| technical_spec | технич, technical, спецификација, specification, барања, requirements |
| amendment | измен, amendment, допол, addend, дополнение, annex |
| award | одлука, decision, доделување, award, избор, selection |
| contract | договор, contract, потпишан, signed |
| other | (default for unclassified) |

### Extraction Strategy

Tries multiple selectors:
```python
# Direct file links
'a[href$=".pdf"]::attr(href)'
'a[href$=".doc"]::attr(href)'

# Download links
'a:contains("Преземи")::attr(href)'
'a:contains("Download")::attr(href)'

# Container classes
'div.documents a::attr(href)'
'div.attachments a::attr(href)'
```

### Output Format

```python
{
    'tender_id': 'ABC-123',
    'file_url': 'https://e-nabavki.gov.mk/files/doc.pdf',
    'file_name': 'technical_spec.pdf',
    'doc_type': 'technical_spec',
    'link_text': 'Преземи техничка спецификација',
    'link_title': 'Technical Specification',
}
```

---

## Data Validation

### Validation Rules

#### Required Fields
- `tender_id` - MUST be present (ERROR if missing)
- `title` - MUST be present and >= 3 characters (ERROR if missing)

#### Date Logic
- `publication_date <= opening_date` (WARNING if violated)
- `opening_date <= closing_date` (WARNING if violated)

#### Currency Values
- Must be positive (WARNING if negative)
- Must be < 10 billion (WARNING if excessive)
- Must be numeric (WARNING if not)

#### Field Lengths
- `title` >= 3 characters

### Validation Logging

```python
# ERROR - stops processing
logger.error("VALIDATION ERROR: Missing required field 'tender_id'")

# WARNING - continues processing
logger.warning("VALIDATION WARNING: opening_date > closing_date")
```

---

## Error Handling

### Extraction Errors

Each extraction level is wrapped in try/except:

```python
try:
    result = self._apply_extractor(response, config, field_name)
    if result:
        return result  # Success!
except Exception as e:
    logger.debug(f"{field_name}: Extractor level {level} failed - {e}")
    continue  # Try next fallback
```

### Critical Field Failures

If critical fields fail:
```python
if field in critical_fields and success_rate < 80:
    logger.error(
        f"STRUCTURE CHANGE ALERT: '{field}' extraction rate is {rate:.1f}% "
        f"(expected >80%). Website structure may have changed!"
    )
```

### Graceful Degradation

- Missing non-critical fields → Continue with NULL
- Missing critical fields → Log ERROR but don't crash
- Invalid data formats → Log WARNING, set to NULL
- Parse errors → Log DEBUG, try next strategy

---

## Monitoring & Statistics

### Tracked Metrics

Per field:
- Total extraction attempts
- Successful extractions
- Failed extractions
- Success rate (%)
- Fallback level distribution

### Statistics Report

Generated on spider close:

```
================================================================================
EXTRACTION STATISTICS
================================================================================
Total tenders processed: 150

Field-by-field success rates:
--------------------------------------------------------------------------------
  [EXCELLENT] tender_id                    100.00% (150/150)
    Fallback distribution: L1:150
  [EXCELLENT] title                         98.67% (148/150)
    Fallback distribution: L1:145, L2:3
  [GOOD    ] closing_date                   85.33% (128/150)
    Fallback distribution: L1:120, L3:8
  [WARNING ] cpv_code                       65.33% (98/150)
    Fallback distribution: L1:90, L3:5, L4:3
  [CRITICAL] procedure_type                 35.33% (53/150)
    Fallback distribution: L3:40, L4:13

STRUCTURE CHANGE ALERT: 'closing_date' extraction rate is 85.3%
(expected >80%). Website structure may have changed!
================================================================================
```

### Alert Thresholds

| Rate | Status | Action |
|------|--------|--------|
| ≥ 90% | EXCELLENT | Normal operation |
| 70-89% | GOOD | Monitor |
| 50-69% | WARNING | Investigate |
| < 50% | CRITICAL | Alert + Investigate |

For critical fields (tender_id, title, procuring_entity, closing_date):
- Alert if rate < 80%

---

## Integration Guide

### 1. Import the Extractor

```python
from scraper.extractors import TenderExtractor
```

### 2. Initialize in Spider

```python
class NabavkiSpider(scrapy.Spider):
    name = "nabavki"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extractor = TenderExtractor()
```

### 3. Use in Parse Method

```python
def parse_tender_detail(self, response):
    # Extract all fields
    tender_data = self.extractor.extract_all_fields(response)

    # Extract documents
    documents = self.extractor.extract_documents(
        response,
        tender_data['tender_id']
    )

    # Yield tender item
    yield TenderItem(tender_data)

    # Yield document items
    for doc in documents:
        yield DocumentItem(doc)
```

### 4. Log Statistics on Close

```python
def closed(self, reason):
    self.extractor.log_statistics()
```

### Complete Example

```python
import scrapy
from scraper.items import TenderItem, DocumentItem
from scraper.extractors import TenderExtractor

class NabavkiSpider(scrapy.Spider):
    name = "nabavki"
    allowed_domains = ["e-nabavki.gov.mk"]
    start_urls = ["https://e-nabavki.gov.mk/PublicAccess/Tenders.aspx"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extractor = TenderExtractor()

    def parse(self, response):
        # Extract tender links
        tender_links = response.css('a.tender-link::attr(href)').getall()

        for link in tender_links:
            yield response.follow(link, callback=self.parse_tender_detail)

    def parse_tender_detail(self, response):
        # Extract all fields with multi-tier fallbacks
        tender_data = self.extractor.extract_all_fields(response)

        # Extract documents
        documents = self.extractor.extract_documents(
            response,
            tender_data['tender_id']
        )

        # Yield items
        yield TenderItem(tender_data)

        for doc in documents:
            yield DocumentItem(doc)

    def closed(self, reason):
        # Log extraction statistics
        self.extractor.log_statistics()
```

---

## Next Steps

### For Agent A (Page Structure Analyst):

1. **Inspect e-nabavki.gov.mk tender detail pages**
2. **Identify actual CSS selectors for each field**
3. **Update `FIELD_EXTRACTORS` configuration** in `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/extractors.py`
4. **Test extraction on real pages**
5. **Adjust selectors as needed**

### Selector Update Pattern

Replace placeholder selectors with real ones:

```python
# BEFORE (placeholder):
'title': [
    {'type': 'css', 'selector': 'h1.tender-title::text', 'priority': 1},
    ...
]

# AFTER (real selectors from Agent A):
'title': [
    {'type': 'css', 'selector': 'div#mainContent h2.title::text', 'priority': 1},
    {'type': 'css', 'selector': 'span.procurement-title::text', 'priority': 1},
    ...
]
```

### Testing Checklist

- [ ] Test on 10+ real tender pages
- [ ] Verify all critical fields extract successfully
- [ ] Check date parsing for various formats
- [ ] Check currency parsing for MKD and EUR
- [ ] Verify document extraction and classification
- [ ] Review extraction statistics
- [ ] Test fallback chains (simulate structure changes)

---

## Architecture Benefits

### 1. Resilience
- Survives website redesigns
- Multiple fallback strategies per field
- Continues on partial failures

### 2. Maintainability
- Clear separation of concerns
- Single responsibility components
- Easy to add new fields

### 3. Observability
- Comprehensive logging
- Extraction success tracking
- Early detection of structure changes

### 4. Accuracy
- Multi-format parsers
- Data validation
- Smart defaults

### 5. Extensibility
- Easy to add new fields
- Easy to add new extractor types
- Modular architecture

---

## File Locations

| File | Purpose |
|------|---------|
| `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/extractors.py` | Main extraction architecture |
| `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/items.py` | Scrapy item definitions (updated with new fields) |
| `/Users/tamsar/Downloads/nabavkidata/scraper/scraper/spiders/nabavki_spider.py` | Spider (to be updated by Agent A) |
| `/Users/tamsar/Downloads/nabavkidata/EXTRACTION_ARCHITECTURE.md` | This documentation |

---

## Questions or Issues?

Contact Agent B or review:
- Source code: `extractors.py` (heavily commented)
- Spider example: `nabavki_spider.py` (existing implementation)
- Database schema: `/Users/tamsar/Downloads/nabavkidata/db/schema.sql`

---

**Status:** Ready for Agent A to provide real selectors from e-nabavki.gov.mk
