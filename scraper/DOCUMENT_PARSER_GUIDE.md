# Document Parser Guide - Multi-Engine Resilient Extraction

## Overview

Extremely resilient PDF document parser with:
- **3 extraction engines** (PyMuPDF, PDFMiner, Tesseract OCR)
- **Automatic engine selection** based on PDF characteristics
- **Table structure detection**
- **CPV code extraction** (multiple patterns)
- **Company name extraction** from award decisions
- **Cyrillic-safe** throughout

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           ResilientDocumentParser                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  1. PDFAnalyzer                                  │  │
│  │     - Analyze PDF characteristics                │  │
│  │     - Recommend extraction engine                │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  2. MultiEngineExtractor                         │  │
│  │     ├─ PyMuPDF    (fast, Cyrillic-safe)         │  │
│  │     ├─ PDFMiner   (complex layouts)              │  │
│  │     └─ Tesseract  (scanned PDFs, OCR)           │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  3. TableExtractor                               │  │
│  │     - Detect table structures                    │  │
│  │     - Extract tabular data                       │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  4. CPVExtractor                                 │  │
│  │     - Extract CPV codes (4 patterns)             │  │
│  │     - Validate format                            │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  5. CompanyExtractor                             │  │
│  │     - Extract company names (7 patterns)         │  │
│  │     - Macedonian + English legal forms           │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  ExtractionResult                                │  │
│  │     - text, engine_used, page_count              │  │
│  │     - tables, cpv_codes, company_names           │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Features

### 1. Multi-Engine Extraction with Auto-Selection

**Three extraction engines:**

1. **PyMuPDF (fitz)** - DEFAULT
   - Fastest
   - Best for text-based PDFs
   - Native Cyrillic support
   - Handles most PDFs well

2. **PDFMiner** - FALLBACK #1
   - Better layout analysis
   - Complex multi-column layouts
   - Better for forms/structured documents

3. **Tesseract OCR** - FALLBACK #2
   - For scanned PDFs (images)
   - Optical character recognition
   - Macedonian + English language support
   - Slower but handles image-only PDFs

**Automatic Selection Algorithm:**

```python
def select_engine(pdf):
    analysis = analyze_pdf(pdf)

    if analysis.is_scanned:
        return 'tesseract'  # Image-based PDF
    elif analysis.has_complex_layout:
        return 'pdfminer'   # Multi-column, forms
    else:
        return 'pymupdf'    # Standard text PDF

    # If recommended engine fails, try others automatically
```

**Location:** `document_parser.py:117-150`

---

### 2. Table Structure Detection

**Extracts tabular data from PDFs:**

**Detection strategy:**
- Analyze text block positions
- Identify grid-like patterns
- Group aligned text (rows/columns)
- Extract as structured data

**Output format:**
```python
tables = [
    [  # Table 1
        ['Header 1', 'Header 2', 'Header 3'],   # Row 1
        ['Cell 1-1', 'Cell 1-2', 'Cell 1-3'],   # Row 2
        ['Cell 2-1', 'Cell 2-2', 'Cell 2-3'],   # Row 3
    ],
    [  # Table 2
        # ... more rows
    ]
]
```

**Location:** `document_parser.py:295-364`

**Use cases:**
- Extract pricing tables
- Bidder comparison tables
- Technical specification tables

---

### 3. CPV Code Extraction

**CPV (Common Procurement Vocabulary) codes** identify procurement categories.

**Format:** `12345678-9` (8 digits + check digit)

**4 extraction patterns:**

```python
CPV_PATTERNS = [
    r'\b(\d{8})-?(\d)\b',              # Standalone: 45000000-7
    r'CPV[:\s]+(\d{8})-?(\d)',         # English: CPV: 45000000-7
    r'CPV[:\s]*код[:\s]*(\d{8})-?(\d)', # Macedonian: CPV код: 45000000-7
    r'[Кк]од[:\s]+(\d{8})-?(\d)',      # Код: 45000000-7
]
```

**Location:** `document_parser.py:374-422`

**Validation:**
- Must be 9 digits (8 + check digit)
- Format validated before return

**Example extraction:**
```
Input text:
  "Набавка на опрема, CPV код: 45000000-7 и 48000000-8"

Output:
  ['45000000-7', '48000000-8']
```

---

### 4. Company Name Extraction

**Extracts company names from award decisions.**

**7 extraction patterns:**

**Macedonian patterns:**
```python
# Winner: Компанија ДОО
r'[Дд]обитник[:\s]+([А-ЯЃЌЉЊЏШЧЖА-Ја-я\s\-\.]+(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД))'

# Awarded to: Компанија ДООЕЛ
r'[Дд]оделен[а-я]*\s+на[:\s]+([А-ЯЃЌЉЊЏШЧЖА-Ја-я\s\-\.]+(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД))'

# Company: Компанија АД
r'[Кк]омпанија[:\s]+([А-ЯЃЌЉЊЏШЧЖА-Ја-я\s\-\.]+(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД))'
```

**English patterns:**
```python
# Winner: Company LLC
r'[Ww]inner[:\s]+([A-Z][A-Za-z\s\-\.]+(?:LLC|Ltd|Inc|Corp|Co))'

# Awarded to: Company Inc
r'[Aa]warded\s+to[:\s]+([A-Z][A-Za-z\s\-\.]+(?:LLC|Ltd|Inc|Corp|Co))'

# Contractor: Company Ltd
r'[Cc]ontractor[:\s]+([A-Z][A-Za-z\s\-\.]+(?:LLC|Ltd|Inc|Corp|Co))'
```

**Generic pattern:**
```python
# Any company with legal form
r'([А-ЯЃЌЉЊЏШЧЖA-Z][А-ЯЃЌЉЊЏШЧЖа-яA-Za-z\s\-\.]{3,50}(?:ДООЕЛ|ДОО|АД|LLC|Ltd))'
```

**Location:** `document_parser.py:435-501`

**Legal forms recognized:**
- **Macedonian:** ДООЕЛ, ДОО, АД, ДПТУ, ООД
- **English:** LLC, Ltd, Inc, Corp, Co

**Validation:**
- Length: 5-200 characters
- Must contain legal form
- Cleaned and normalized

**Example extraction:**
```
Input text:
  "Добитник: Технолошки Решенија ДООЕЛ Скопје"

Output:
  ['Технолошки Решенија ДООЕЛ Скопје']
```

---

## Usage

### Basic Usage

```python
from document_parser import parse_pdf

# Parse PDF
result = parse_pdf('tender_document.pdf')

# Access extracted data
print(f"Text: {result.text[:100]}...")
print(f"Engine used: {result.engine_used}")
print(f"Pages: {result.page_count}")
print(f"Tables: {len(result.tables)}")
print(f"CPV codes: {result.cpv_codes}")
print(f"Companies: {result.company_names}")
```

### Advanced Usage

```python
from document_parser import ResilientDocumentParser

parser = ResilientDocumentParser()
result = parser.parse_document('award_decision.pdf')

# Access individual components
if result.has_tables:
    for i, table in enumerate(result.tables):
        print(f"Table {i}:")
        for row in table:
            print(row)

# CPV codes
for cpv in result.cpv_codes:
    print(f"Procurement category: {cpv}")

# Winner companies
for company in result.company_names:
    print(f"Company: {company}")
```

### Engine-Specific Extraction

```python
from document_parser import MultiEngineExtractor

extractor = MultiEngineExtractor()

# Force specific engine
text, metadata = extractor.extract_with_pymupdf('document.pdf')
text, metadata = extractor.extract_with_pdfminer('complex.pdf')
text, metadata = extractor.extract_with_tesseract('scanned.pdf')

# Automatic selection (recommended)
text, engine, metadata = extractor.extract_auto('document.pdf')
```

---

## Integration with Scrapy Pipeline

**Automatic integration** in `pipelines.py`:

```python
class PDFExtractionPipeline:
    async def process_item(self, item, spider):
        from document_parser import parse_pdf

        result = parse_pdf(item['file_path'])

        # Store in item
        item['content_text'] = result.text
        item['page_count'] = result.page_count
        item['extraction_status'] = 'success'

        # Log extracted metadata
        logger.info(f"CPV codes: {result.cpv_codes}")
        logger.info(f"Companies: {result.company_names}")

        return item
```

**Location:** `scraper/pipelines.py:85-153`

---

## Engine Selection Decision Tree

```
PDF Document
    |
    ├─ Is scanned (images only)?
    │   └─ YES → Tesseract OCR
    │
    ├─ Has complex layout (multi-column, forms)?
    │   └─ YES → PDFMiner
    │
    └─ Standard text PDF?
        └─ YES → PyMuPDF (default)

If selected engine fails:
    Try next engine in fallback chain
    PyMuPDF → PDFMiner → Tesseract
```

---

## PDF Analysis

**Analyzes PDF to determine characteristics:**

```python
from document_parser import PDFAnalyzer

analysis = PDFAnalyzer.analyze_pdf('document.pdf')

print(analysis)
# {
#     'page_count': 15,
#     'has_text': True,
#     'text_percentage': 85.3,
#     'is_scanned': False,
#     'has_complex_layout': False,
#     'recommended_engine': 'pymupdf'
# }
```

**Analysis metrics:**
- `page_count` - Number of pages
- `has_text` - Contains extractable text
- `text_percentage` - Approximate text coverage
- `is_scanned` - Likely scanned/image-based
- `has_complex_layout` - Multi-column or forms
- `recommended_engine` - Best engine for this PDF

**Location:** `document_parser.py:41-115`

---

## Resilience Features

### 1. Automatic Fallback Chain

**If PyMuPDF fails → try PDFMiner → try Tesseract**

```python
engines = ['pymupdf', 'pdfminer', 'tesseract']

for engine in engines:
    try:
        text, metadata = extract_with_engine(engine, pdf_path)
        if len(text) > 50:  # Minimum threshold
            return text  # Success
    except:
        continue  # Try next engine

raise Exception("All engines failed")
```

**Location:** `document_parser.py:261-292`

### 2. Graceful Degradation

**Never crashes** - returns empty result on failure:

```python
try:
    result = parse_pdf('corrupted.pdf')
except:
    # Returns ExtractionResult with empty data
    result = ExtractionResult(
        text="",
        engine_used="failed",
        page_count=0,
        tables=[],
        cpv_codes=[],
        company_names=[],
        metadata={'error': 'Extraction failed'}
    )
```

**Location:** `document_parser.py:547-571`

### 3. Multi-Pattern Extraction

**CPV codes:** 4 patterns (handles variations)
**Company names:** 7 patterns (Macedonian + English)

**Ensures extraction even if document format varies**

### 4. Cyrillic Preservation

**All engines preserve Cyrillic:**
- PyMuPDF: Native UTF-8 support
- PDFMiner: Unicode-aware
- Tesseract: Macedonian language model (`mkd`)

---

## Dependencies

```
PyMuPDF==1.23.8          # Primary engine
pdfminer.six==20221105   # Fallback engine
pytesseract==0.3.10      # OCR engine
Pillow==10.1.0           # Image processing for OCR
```

**System requirements:**
- Tesseract OCR with Macedonian language pack:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install tesseract-ocr tesseract-ocr-mkd

  # macOS
  brew install tesseract tesseract-lang
  ```

---

## Performance

| Engine | Speed | Quality | Use Case |
|--------|-------|---------|----------|
| PyMuPDF | Fast (1-2s) | Excellent | Standard PDFs |
| PDFMiner | Medium (3-5s) | Good | Complex layouts |
| Tesseract | Slow (10-30s) | Variable | Scanned PDFs |

**Optimization:**
- Automatic selection minimizes processing time
- Only uses OCR when necessary
- Parallel processing possible

---

## Testing

### Test All Engines

```python
from document_parser import MultiEngineExtractor

extractor = MultiEngineExtractor()

# Test PyMuPDF
text1, meta1 = extractor.extract_with_pymupdf('test.pdf')
print(f"PyMuPDF: {len(text1)} chars")

# Test PDFMiner
text2, meta2 = extractor.extract_with_pdfminer('test.pdf')
print(f"PDFMiner: {len(text2)} chars")

# Test Tesseract (if available)
if TESSERACT_AVAILABLE:
    text3, meta3 = extractor.extract_with_tesseract('scanned.pdf')
    print(f"Tesseract: {len(text3)} chars")
```

### Test CPV Extraction

```python
from document_parser import CPVExtractor

text = """
Набавка на опрема, CPV код: 45000000-7
Дополнително: 48000000-8 и 30200000-1
"""

cpv_codes = CPVExtractor.extract_cpv_codes(text)
print(cpv_codes)
# ['30200000-1', '45000000-7', '48000000-8']
```

### Test Company Extraction

```python
from document_parser import CompanyExtractor

text = """
Добитник: Технолошки Решенија ДООЕЛ Скопје
Awarded to: Tech Solutions LLC
"""

companies = CompanyExtractor.extract_companies(text)
print(companies)
# ['Tech Solutions LLC', 'Технолошки Решенија ДООЕЛ Скопје']
```

---

## Troubleshooting

### Tesseract not available

**Error:** `ImportError: Tesseract not available`

**Solution:**
```bash
# Install Tesseract
sudo apt-get install tesseract-ocr tesseract-ocr-mkd

# Install Python package
pip install pytesseract Pillow
```

### OCR returns empty text

**Problem:** Scanned PDF produces no text

**Solutions:**
1. Check image quality (low resolution → poor OCR)
2. Verify Macedonian language pack installed
3. Try higher resolution: `pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))`

### Extraction too slow

**Problem:** Large PDFs take minutes

**Solutions:**
1. Use PyMuPDF instead of OCR (if not scanned)
2. Process only first N pages for preview
3. Run extraction in background task

### CPV codes not found

**Problem:** Valid CPV codes not extracted

**Solutions:**
1. Check pattern variations (with/without hyphen)
2. Add custom pattern to `CPV_PATTERNS`
3. Verify code format (must be 8+1 digits)

---

## Summary

**Extremely resilient document parser with:**

✅ **3 extraction engines** (automatic selection)
✅ **Table detection** (structured data extraction)
✅ **CPV code extraction** (4 patterns, validated)
✅ **Company name extraction** (7 patterns, bilingual)
✅ **Automatic fallback** (never fails completely)
✅ **Cyrillic-safe** (all engines)
✅ **Graceful degradation** (empty result on failure)

**Survives:**
- Scanned PDFs (OCR)
- Complex layouts (PDFMiner)
- Corrupted PDFs (fallback chain)
- Missing metadata (pattern-based extraction)
- Format variations (multiple patterns)
