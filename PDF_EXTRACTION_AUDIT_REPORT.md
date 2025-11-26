# PDF EXTRACTION AUDIT REPORT

**Date:** 2025-11-26
**Purpose:** Analyze how products/services are written in tender PDFs and audit our extraction system
**Samples Analyzed:** 14 PDFs across different tender categories and values (from 7 MKD to 158M MKD)

---

## EXECUTIVE SUMMARY

After analyzing **14 tender PDFs** (medical, construction, marketing, road works, lab reagents, services - both contracts and bids), we found:

### CRITICAL FINDINGS:

1. **Bid PDFs (Финансиска понуда) contain STRUCTURED product data** - These are the GOLD MINE
2. **Contract PDFs contain legal text** - Less useful for product extraction
3. **Cyrillic encoding is problematic** - Some PDFs use corrupted encoding (medical_awarded_contract.pdf)
4. **Table extraction varies** - PyMuPDF works well, but table structure is often misaligned

---

## DOCUMENT TYPES ANALYZED

### Type 1: Financial Bid (Финансиска понуда) - **HIGH VALUE**

These documents have a CONSISTENT STRUCTURE with tables containing:
- **Шифра** (CPV Code)
- **Назив на ставка** (Item Name) - **THIS IS THE PRODUCT/SERVICE**
- **Мерна единица** (Unit of measure)
- **Количина** (Quantity)
- **Единечна цена** (Unit price)
- **Вкупна цена** (Total price without VAT)
- **ДДВ** (VAT)
- **Цена со ДДВ** (Price with VAT)

**Example from medical_bid.pdf:**
```
Шифра: 33652100-6
Назив: Набавка на L01ЕA03, Nilotinib, 200mg, капсула
Мерна единица: Капсула
Количина: 5.376,00
Единечна цена: 1.210,00
Вкупна цена: 6.504.960,00 ден
```

**Example from construction_bid.pdf:**
```
Шифра: 45111300-1
Назив: Демонтажа на постоечка алуминиумска дограма, во објект на АКЛ Охрид
Мерна единица: Парче
Количина: 37,00
Единечна цена: 5.996,25
Вкупна цена: 221.861,25 ден
```

### Type 2: Contract Document (Договор) - **MEDIUM VALUE**

Contains:
- Contract parties (Договорни страни)
- Contract value (Вредност на договорот)
- Subject of contract (Предмет на договорот)
- Payment terms (Начин на плаќање)
- Guarantees (Гаранции)
- Legal clauses

**Problem:** Often uses scanned images or corrupted Cyrillic encoding.

---

## PDF PARSER AUDIT RESULTS

### Full Analysis of 14 PDFs

| PDF File | Tender | Value MKD | Engine | Tables | Cyrillic | Product Table |
|----------|--------|-----------|--------|--------|----------|---------------|
| construction_large_bid.pdf | 17470/2025 | 158M | pymupdf | 1 | ✅ 994 | ✅ YES |
| marketing_bid.pdf | 12853/2025 | 118M | pymupdf | 4 | ✅ 3363 | ✅ YES |
| road_construction_bid.pdf | 18084/2025 | 82M | pymupdf | 1 | ✅ 1065 | ✅ YES |
| medical_equipment_bid.pdf | 16654/2025 | 47M | pymupdf | 5 | ✅ 4436 | ✅ YES |
| lab_reagents_bid.pdf | 15097/2025 | 34M | pymupdf | 9 | ✅ 9495 | ✅ YES |
| marketing_bid2.pdf | 12853/2025 | 118M | pymupdf | 4 | ✅ 3364 | ✅ YES |
| medical_bid.pdf | 12525/2025 | ~6M | pymupdf | 1 | ✅ 1156 | ✅ YES |
| construction_bid.pdf | 12653/2025 | ~1M | pymupdf | 5 | ✅ 3154 | ✅ YES |
| services_bid.pdf | 07834/2025 | 7 | pymupdf | 1 | ✅ 794 | ✅ YES |
| medicines_open.pdf | 18715/2025 | 35M | pymupdf | 3 | ✅ 1455 | ❌ Notice doc |
| aircraft_insurance.pdf | 20608/2025 | 86M | pymupdf | 2 | ✅ 945 | ❌ Notice doc |
| medical_contract.pdf | 12525/2025 | ~6M | pymupdf | 6 | ❌ Corrupt | ⚠️ Encoding |
| construction_contract.pdf | 12653/2025 | ~1M | tesseract | 0 | ❌ OCR | ⚠️ Quality |
| services_contract.pdf | 07834/2025 | ~7 | tesseract | 0 | ❌ OCR | ⚠️ Quality |

### Key Statistics:
- **9/14 PDFs (64%)** have extractable product tables
- **11/14 PDFs (79%)** have good Cyrillic text extraction with PyMuPDF
- **All Bid documents (Bids/DownloadBidFile)** have clean structured tables
- **Contract documents** have encoding/OCR issues

### Key Insights:

1. **BID files (Bids/DownloadBidFile) are MOST VALUABLE** - Clean, structured, extractable
2. **CONTRACT files (File/DownloadContractFile) are secondary** - Legal text, encoding issues
3. **PyMuPDF works best** for digital PDFs with embedded text
4. **Tesseract fallback needed** for scanned documents but quality varies

---

## PRODUCT DATA STRUCTURE

From analyzed PDFs, products/services follow this schema:

```json
{
  "cpv_code": "33652100-6",           // CPV classification code
  "product_name": "L01ЕA03, Nilotinib, 200mg, капсула",
  "description": "Набавка на L01ЕA03, Nilotinib...",
  "unit": "Капсула",                  // Мерна единица
  "quantity": 5376.00,                // Количина
  "unit_price_mkd": 1210.00,          // Единечна цена
  "total_price_mkd": 6504960.00,      // Вкупна цена без ДДВ
  "vat_amount_mkd": 325248.00,        // ДДВ
  "total_with_vat_mkd": 6830208.00,   // Цена со ДДВ
  "lot_number": 1,                    // If applicable
  "tender_id": "12525/2025"           // Parent tender
}
```

---

## KEY FIELDS FOR AI ASSISTANT

For the AI to answer user questions, we need these fields extracted:

### 1. Products/Services (Items Table)
- Product name (Назив на ставка)
- CPV code (Шифра)
- Quantity (Количина)
- Unit (Мерна единица)
- Unit price (Единечна цена)
- Total price (Вкупна цена)

### 2. Evaluation Criteria (Критериуми за евалуација)
- Found in tender documentation, usually:
  - "Најниска цена" (Lowest price)
  - "Економски најповолна понуда" (Most economically advantageous)
  - Weighted criteria with percentages

### 3. Guarantees/Deposits (Гаранции/Депозити)
- Bid guarantee (Гаранција за понуда)
- Performance guarantee (Гаранција за квалитетно извршување)
- Warranty period (Гарантен рок)

### 4. Conditions/Requirements (Услови/Барања)
- Delivery terms (Услови за испорака)
- Payment terms (Начин на плаќање)
- Technical specifications (Технички спецификации)
- Required documents (Потребни документи)

---

## RECOMMENDED EXTRACTION PATTERNS

### Pattern 1: Financial Bid Table Parser

```python
# Regex patterns for Macedonian bid documents
HEADER_PATTERN = r'(Шифра|Назив на ставка|Мерна единица|Количина|Единечна цена|Вкупна цена)'
CPV_PATTERN = r'(\d{8}-\d)'
AMOUNT_PATTERN = r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:ден|денари)?'

# Table column mapping
COLUMN_MAP = {
    'Шифра': 'cpv_code',
    'Назив на ставка': 'product_name',
    'Мерна единица': 'unit',
    'Количина': 'quantity',
    'Единечна цена': 'unit_price',
    'Вкупна цена': 'total_price',
    'ДДВ': 'vat_amount',
    'Цена со ДДВ': 'total_with_vat'
}
```

### Pattern 2: Contract Value Parser

```python
# Extract contract values from legal text
VALUE_PATTERNS = [
    r'вкупна(?:та)?\s+вредност\s+(?:на договорот\s+)?изнесува\s+([\d\.,]+)\s*(?:ден|денари)',
    r'вредност\s+без\s+ДДВ\s*[:=]?\s*([\d\.,]+)',
    r'вредност\s+со\s+ДДВ\s*[:=]?\s*([\d\.,]+)',
]
```

---

## DATABASE SCHEMA UPDATES NEEDED

### 1. Add raw_data_json column to tenders table
```sql
ALTER TABLE tenders ADD COLUMN raw_data_json JSONB;
-- Store complete scraped data for AI fallback
```

### 2. Add document_url column to product_items table
```sql
ALTER TABLE product_items ADD COLUMN source_document_url TEXT;
ALTER TABLE product_items ADD COLUMN extraction_method TEXT; -- 'table', 'text', 'ocr'
```

### 3. Add tender_conditions table (for AI queries)
```sql
CREATE TABLE tender_conditions (
    condition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id TEXT REFERENCES tenders(tender_id),
    condition_type TEXT, -- 'evaluation', 'guarantee', 'delivery', 'payment', 'documents'
    condition_text TEXT,
    condition_value TEXT,
    extracted_from TEXT, -- document_id or 'web_page'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## AI SEARCH PRIORITY ORDER

When user asks about a tender, AI should search in this order:

1. **Structured tables** (product_items, tender_conditions) - Fastest, most reliable
2. **Raw JSON column** (raw_data_json) - Complete data, needs parsing
3. **Document text** (documents.content_text) - Full text search
4. **Source URL** (tender.source_url) - Fetch fresh data if needed
5. **PDF files** - Last resort, download and read

---

## ACTION ITEMS

### Immediate (Before Production Scrape):

1. [ ] **Add raw_data_json column** - Store all scraped JSON for AI fallback
2. [ ] **Improve spec_extractor.py** - Add Macedonian bid table parser
3. [ ] **Add document_url to product_items** - Link products to source documents
4. [ ] **Store document URLs** - Currently storing file_url but not preserving original links

### Next Phase:

1. [ ] **Create tender_conditions table** - Extract evaluation criteria, guarantees
2. [ ] **Vectorize product names** - For semantic search
3. [ ] **Add AI search endpoint** - Multi-tier search as described above

---

## SAMPLE EXTRACTED DATA FROM 14 PDFs

### 1. Large School Construction (17470/2025) - 158M MKD
**Products:**
| Item | CPV | Quantity | Total Price |
|------|-----|----------|-------------|
| Градежни работи (Construction works) | 45214200-2 | 1 | 84,513,856.00 MKD |
| Електрика (Electrical) | 45214200-2 | 1 | 20,595,005.68 MKD |
| Машинство (Mechanical) | 45214200-2 | 1 | 18,203,050.00 MKD |
| ВОДОВОД И КАНАЛИЗАЦИЈА (Plumbing) | 45214200-2 | 1 | 8,221,220.00 MKD |
**Total:** 131,533,131.68 MKD (without VAT)

### 2. Marketing Services (12853/2025) - 118M MKD
**Products:**
| Item | CPV | Quantity | Total Price |
|------|-----|----------|-------------|
| УСЛУГИ ЗА КРЕАТИВНИ РЕШЕНИЈА (Creative services) | 79342200-5 | 1 | 2,152,980.00 MKD |
| УСЛУГИ ЗА МЕДИЈАЗАКУП И КАМПАЊИ (Media buying) | 79341400-0 | 1 | 699,000.00 MKD |
| Продукција на видеоматеријали (Video production) | 92111200-4 | 1 | 1,153,550.00 MKD |

### 3. Road Reconstruction (18084/2025) - 82M MKD
**Products:**
| Phase | CPV | Total Price |
|-------|-----|-------------|
| Маршал Тито (Фаза 1) | 45113000-2 | 17,085,830.00 MKD |
| Маршал Тито (Фаза 2) | 45113000-2 | 15,179,145.00 MKD |
| Маршал Тито (Фаза 3) | 45113000-2 | 22,118,106.00 MKD |
| Фаза Водовод (Water) | 45113000-2 | 10,193,965.08 MKD |
| Фаза Електрика (Electric) | 45113000-2 | 5,420,261.90 MKD |
**Total:** 69,997,307.98 MKD (without VAT)

### 4. Medical Equipment Service (16654/2025) - 47M MKD
**Products (Multiple lots by equipment manufacturer):**
| Manufacturer | CPV | Unit Price |
|--------------|-----|------------|
| Апарати производ на CA-MI | 50422000-9 | 3,500.00 MKD/hour |
| Апарати производ на MEM-O-MATIC | 50422000-9 | 3,500.00 MKD/hour |

### 5. Lab Reagents (15097/2025) - 34M MKD
**Products (Multiple lots - detailed items):**
| Item | CPV | Quantity | Unit | Unit Price |
|------|-----|----------|------|------------|
| Пластични епрувети за една употреба | 33192500-7 | 10,000 | Парче | 0.75 MKD |
| Четкици за чистење епрувети | - | - | - | - |

### 6. Medical Tender (12525/2025) - 6M MKD
**Product:** L01ЕA03, Nilotinib, 200mg, капсула
**CPV:** 33652100-6
**Quantity:** 5,376 capsules
**Unit Price:** 1,210.00 MKD
**Total:** 6,504,960.00 MKD (without VAT)

### 7. Construction Tender (12653/2025) - 1M MKD
**Product:** Демонтажа на постоечка алуминиумска дограма
**CPV:** 45111300-1
**Quantity:** 37 pieces
**Unit Price:** 5,996.25 MKD
**Total:** 221,861.25 MKD (without VAT)

### 8. Services Tender (07834/2025) - 7 MKD
**Product:** Коефициент (маржа) за дистрибуција на електрична енергија
**CPV:** 09310000-5
**Type:** Service margin (percentage)
**Value:** 7.00 MKD (7% margin)

---

## CONCLUSION

Our PDF parser WORKS but the **spec_extractor.py needs improvement** to properly parse:

1. **Macedonian table headers** (Шифра, Назив на ставка, etc.)
2. **European number format** (1.234.567,89)
3. **Multi-line product descriptions**

The **BID documents (Финансиска понуда)** are the primary source for product data, not contract documents.

**Recommendation:** Focus extraction on `Bids/DownloadBidFile` URLs first, these have the cleanest structured data.

---

*Report generated: 2025-11-26*
