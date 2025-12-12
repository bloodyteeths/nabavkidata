# Office Document Extraction Pipeline for Nabavkidata

## Overview

Comprehensive Word (DOCX, DOC) and Excel (XLSX, XLS) document extraction system designed specifically for Macedonian tender documents. Extracts structured data including Bill of Quantities (BOQ), price lists, technical specifications, and bidder information.

## Features

### Supported Formats
- **Word Documents**: `.docx`, `.doc`
- **Excel Spreadsheets**: `.xlsx`, `.xls`

### Extraction Capabilities

1. **Table Detection & Classification**
   - Automatically identifies table types: items, specifications, bidders, pricing, evaluation
   - Handles multi-sheet Excel workbooks
   - Processes multiple tables per document

2. **Intelligent Column Mapping**
   - Recognizes Macedonian headers: количина, цена, назив, опис, единица
   - Recognizes English headers: quantity, price, description, unit
   - Flexible pattern matching for variations

3. **Structured Item Extraction**
   - Item number/ID
   - Item name/description
   - Quantity and unit of measure
   - Unit price and total price
   - Technical specifications
   - Metadata (source, confidence, etc.)

4. **Number Parsing**
   - Handles Macedonian number format: `1.234,56`
   - Handles English number format: `1,234.56`
   - Strips currency symbols: МКД, ден, EUR, €, $

## Installation

```bash
# Install required dependencies
pip install python-docx openpyxl xlrd pandas
```

## Usage

### 1. Extract from a Single Document

```python
from ai.office_extraction import extract_from_office_document

# Extract from Word or Excel file
result = extract_from_office_document('/path/to/document.xlsx')

print(f"Tables found: {result['metadata']['table_count']}")
print(f"Items extracted: {result['metadata']['item_count']}")

# Access extracted items
for item in result['items']:
    print(f"{item['item_name']}: {item['quantity']} x {item['unit_price']}")
```

### 2. Batch Processing from Database

Process all pending Office documents from the database:

```bash
# Process all pending Office documents
python ai/batch_office_extraction.py --all-pending

# Process only Excel files
python ai/batch_office_extraction.py --all-pending --file-type xlsx

# Process with limit
python ai/batch_office_extraction.py --all-pending --limit 100
```

### 3. Batch Processing from Directory

Process all Office documents in a directory:

```bash
# Process all Office files in directory
python ai/batch_office_extraction.py --directory scraper/downloads/files/

# Process only DOCX files
python ai/batch_office_extraction.py --directory scraper/downloads/files/ --file-type docx

# Limit to first 50 files
python ai/batch_office_extraction.py --directory scraper/downloads/files/ --limit 50
```

### 4. Process Single File

```bash
python ai/batch_office_extraction.py \
  --file document.xlsx \
  --tender-id 12345_2025
```

## Architecture

### Core Modules

#### 1. `office_extraction.py`

Main extraction module with three core classes:

**WordExtractor**
- Extracts tables and text from Word documents
- Uses `python-docx` library
- Classifies tables based on column names
- Confidence: 0.85

**ExcelExtractor**
- Extracts sheets from Excel workbooks
- Supports both `.xlsx` (openpyxl) and `.xls` (xlrd)
- Handles multi-sheet documents
- Automatic header detection
- Confidence: 0.90

**OfficeItemExtractor**
- Parses structured items from tables
- Intelligent column mapping using regex patterns
- Number parsing with format detection
- Item validation and filtering

#### 2. `batch_office_extraction.py`

Batch processing system with:
- Database integration (asyncpg)
- Concurrent processing
- Progress tracking and statistics
- Error handling and logging
- Automatic tender_id extraction from filenames

#### 3. `test_office_extraction.py`

Comprehensive test suite that:
- Creates realistic sample documents in Macedonian
- Tests Excel BOQ extraction
- Tests Word table extraction
- Validates number parsing
- Demonstrates full pipeline

## Database Integration

### Schema Requirements

The batch processor expects these tables:

```sql
-- Documents table
CREATE TABLE documents (
    doc_id SERIAL PRIMARY KEY,
    tender_id VARCHAR(50),
    file_path TEXT,
    file_name TEXT,
    extraction_status VARCHAR(20) DEFAULT 'pending',
    content_text TEXT,
    specifications_json JSONB,
    processed_at TIMESTAMP
);

-- Product items table
CREATE TABLE product_items (
    item_id SERIAL PRIMARY KEY,
    tender_id VARCHAR(50),
    name TEXT,
    quantity NUMERIC,
    unit VARCHAR(50),
    unit_price NUMERIC,
    total_price NUMERIC,
    specifications TEXT,
    extraction_method VARCHAR(50),
    extraction_confidence NUMERIC,
    metadata JSONB
);
```

### Automatic Storage

When using `batch_office_extraction.py`, extracted items are automatically stored:

```python
# Items are inserted into product_items table
# Document status updated to 'success'
# Metadata stored in specifications_json
```

## Column Mapping Patterns

### Macedonian Patterns

| Pattern | Standard Name | Example Headers |
|---------|---------------|-----------------|
| `р\.?\s*бр\|реден` | item_number | Р.Бр., Реден број, Ред. број |
| `назив\|опис\|производ` | item_name | Назив, Опис, Производ, Артикл |
| `количина\|кол\.?` | quantity | Количина, Кол., Количество |
| `единица\|мера` | unit | Единица, Мера, Ед. мера, Јединица |
| `единечна.*цена` | unit_price | Единечна цена, Ед. цена |
| `вкупн\|тотал` | total_price | Вкупна цена, Вкупно, Тотал |
| `спец\|тех.*барањ` | specifications | Спецификација, Технички барања |

### English Patterns

| Pattern | Standard Name | Example Headers |
|---------|---------------|-----------------|
| `^item$\|^no\.?$` | item_number | Item, No., #, Line |
| `desc\|name\|product` | item_name | Description, Name, Product |
| `^qty$\|quantity` | quantity | Qty, Quantity, Amount |
| `^unit$\|measure` | unit | Unit, Measure, UOM |
| `unit.*price\|rate` | unit_price | Unit Price, Rate |
| `^total$\|sum` | total_price | Total, Sum, Value |

## Table Classification

Tables are automatically classified based on column patterns:

- **items**: Contains quantity, price, unit, item name
- **bidders**: Contains company names, tax numbers
- **specifications**: Contains technical requirements
- **evaluation**: Contains scores, ratings
- **unknown**: Cannot be classified (still extracted)

## Output Format

### Result Dictionary

```python
{
    'tables': [
        ExtractedOfficeTable(
            data=pd.DataFrame(...),
            source_type='excel',
            sheet_name='Предмер и предрачка',
            table_index=0,
            confidence=0.90,
            table_type='items',
            metadata={'rows': 50, 'cols': 7}
        )
    ],
    'items': [
        {
            'item_name': 'Компјутер Lenovo ThinkCentre M720',
            'item_number': '1',
            'quantity': 50.0,
            'unit': 'парче',
            'unit_price': 35000.0,
            'total_price': 1750000.0,
            'specifications': 'Intel i5, 8GB RAM, 256GB SSD',
            'extraction_source': 'excel',
            'source_sheet': 'Предмер и предрачка',
            'table_index': 0,
            'confidence': 0.90,
            'table_type': 'items'
        }
    ],
    'text': 'Document text content...',
    'metadata': {
        'file_type': '.xlsx',
        'file_path': '/path/to/file.xlsx',
        'file_name': 'file.xlsx',
        'table_count': 2,
        'item_count': 50,
        'text_length': 1234
    }
}
```

## Testing

### Run Test Suite

```bash
python ai/test_office_extraction.py
```

This creates sample documents and tests:
- Excel BOQ extraction (8 items)
- Word table extraction (7 items)
- Macedonian column detection
- Number format parsing
- Total value calculation

### Expected Output

```
FINAL TEST SUMMARY
======================================================================
Excel File:
  Tables: 2
  Items: 8

Word File:
  Tables: 1
  Items: 7

Total Items Extracted: 15
```

## Current Status (2025-11-29)

### Document Inventory

Based on database audit:

- **DOCX**: 865 files (301 pending, 34.8%)
- **DOC**: 91 files (33 pending, 36.3%)
- **XLSX**: 42 files (42 pending, 100%)
- **XLS**: 58 files (11 pending, 19%)

**Total Office Documents**: 1,056
**Total Pending**: 387 (36.6%)

### Known Issues

1. **HTML Files Disguised as Office Files**
   - Some downloaded `.xls` and `.docx` files are actually HTML
   - Error: "Expected BOF record" (Excel) or "Package not found" (Word)
   - Solution: These will be skipped by the batch processor

2. **Old Binary DOC Format**
   - `.doc` files (Office 97-2003) have limited support
   - Recommend converting to `.docx` if possible

## Performance

### Benchmarks

- **Excel extraction**: ~0.1-0.5 seconds per file
- **Word extraction**: ~0.2-0.8 seconds per file
- **Database storage**: ~0.05 seconds per item
- **Batch processing**: ~50-100 documents per minute

### Optimization Tips

1. Use `--limit` to process in batches
2. Filter by `--file-type` for targeted processing
3. Monitor logs for errors and adjust patterns
4. Run during off-peak hours for large batches

## Command Line Reference

```bash
# Full command with all options
python ai/batch_office_extraction.py \
  --all-pending \
  --file-type xlsx \
  --limit 100 \
  --db-host localhost \
  --db-name nabavkidata \
  --db-user postgres \
  --db-password postgres
```

### Options

- `--file PATH`: Process single file
- `--directory PATH`: Process all files in directory
- `--all-pending`: Process pending documents from database
- `--tender-id ID`: Specify tender ID for single file
- `--file-type TYPE`: Filter by extension (docx|doc|xlsx|xls)
- `--limit N`: Maximum number to process
- `--db-host HOST`: Database host (default: localhost)
- `--db-name NAME`: Database name (default: nabavkidata)
- `--db-user USER`: Database user (default: postgres)
- `--db-password PASS`: Database password (default: postgres)

## Integration Examples

### With Existing Pipeline

```python
# In your scraper or processing pipeline
from ai.office_extraction import extract_from_office_document

async def process_tender_document(doc_path, tender_id):
    # Extract data
    result = extract_from_office_document(doc_path)

    # Store items in database
    for item in result['items']:
        await db.execute("""
            INSERT INTO product_items (tender_id, name, quantity, ...)
            VALUES ($1, $2, $3, ...)
        """, tender_id, item['item_name'], item['quantity'], ...)
```

### With Embeddings Pipeline

```python
# Create embeddings from extracted items
from ai.embeddings import create_embedding

for item in result['items']:
    text = f"{item['item_name']} {item['specifications']}"
    embedding = await create_embedding(text)
    # Store embedding...
```

## Troubleshooting

### Issue: No tables extracted

**Cause**: Document structure not recognized
**Solution**: Check column names with `--debug` mode (add logging)

### Issue: Items extracted but no prices

**Cause**: Number format not parsed correctly
**Solution**: Verify number format (Macedonian vs English)

### Issue: Duplicate items in database

**Cause**: Same document processed multiple times
**Solution**: Check `ON CONFLICT DO NOTHING` in SQL

### Issue: Database connection error

**Cause**: Incorrect credentials or host
**Solution**: Verify `--db-*` parameters

## Next Steps

1. **HTML-to-Excel Converter**: Handle disguised HTML files
2. **OCR Integration**: Extract from scanned/image-based documents
3. **Smart Merging**: Combine data from multiple sheets
4. **Validation Rules**: Verify quantity × unit_price = total_price
5. **Currency Conversion**: Handle EUR, USD in addition to MKD

## Support

For issues or questions:
1. Check logs in console output
2. Verify database schema matches requirements
3. Test with sample documents first
4. Review error messages in batch summary

## License

Internal tool for Nabavkidata project.

## Author

Created: 2025-11-29
Version: 1.0.0
