# Price Extraction Improvements for spec_extractor.py

## Problem Statement
Only 0% of technical_specs documents had prices extracted, despite containing price data. The extractor was failing to recognize and parse Macedonian number formats and price column headers.

## Root Causes Identified

1. **Inadequate Price Patterns**: The PRICE_PATTERNS regex were too restrictive
   - Didn't match common Macedonian column headers like "Единечна цена", "Вкупна цена"
   - Required currency suffix, but table cells often contain just numbers
   - Missing variations like "ед. цена", "вкупно"

2. **Poor Number Format Handling**: Macedonian format (2.000,00) wasn't properly parsed
   - Period (.) used as thousands separator
   - Comma (,) used as decimal separator
   - Old parser had simplistic logic that failed on edge cases

3. **Incomplete Column Identification**: _identify_columns() had gaps
   - "единечна" alone didn't match "Единечна цена" in lowercase comparison
   - Missing common abbreviations like "ед. цена", "вкупно"
   - No fallback for abbreviated or empty headers

4. **Inconsistent Parsing**: Two different price parsers in the codebase
   - _extract_prices() had basic logic
   - parse_price() in _extract_item_from_row() was better but not reused

## Improvements Implemented

### 1. Enhanced PRICE_PATTERNS (lines 167-184)

**Before:**
```python
PRICE_PATTERNS = [
    r'(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{1,2})?)\s*(?:ден|МКД|MKD)',
    r'(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{1,2})?)\s*(?:EUR|евро)',
    r'[Цц]ена[:\s]+(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{1,2})?)',
    r'[Pp]rice[:\s]+(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{1,2})?)',
]
```

**After:**
```python
PRICE_PATTERNS = [
    # Price with currency suffix: "2.000,00 ден" or "2.000,00 МКД"
    r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s*(?:ден|денари|МКД|MKD)',
    # Price with EUR
    r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s*(?:EUR|евро|€)',
    # Price after "цена:" label
    r'[Цц]ена[:\s]+(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)',
    r'[Pp]rice[:\s]+(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)',
    # Unit price patterns
    r'[Ее]динечна\s+цена[:\s]*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)',
    r'[Ее]д\.?\s*цена[:\s]*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)',
    # Total price patterns
    r'[Вв]купна\s+цена[:\s]*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)',
    r'[Вв]купно[:\s]*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)',
    # Standalone price number
    r'(\d{1,3}(?:[.,]\d{3})+(?:,\d{1,2})?)\s*(?=\s|$)',
]
```

**Impact:** Catches many more price formats in both text and table contexts.

### 2. Comprehensive Macedonian Number Parser (lines 468-547)

New method `_parse_macedonian_number()` with intelligent format detection:

```python
def _parse_macedonian_number(self, value: str) -> Optional[Decimal]:
    """
    Parse Macedonian/European number format to Decimal.

    Examples:
    - "2.000,00" -> Decimal("2000.00")
    - "19.399,00" -> Decimal("19399.00")
    - "1.234.567,89" -> Decimal("1234567.89")
    - "500" -> Decimal("500")
    - "500,50" -> Decimal("500.50")
    """
```

**Features:**
- Handles mixed dot/comma separators intelligently
- Extracts numeric portion from text with trailing currency/units
- Validates against empty values, placeholders (-, н/а)
- Sanity checks for reasonable price ranges
- Removes whitespace including non-breaking spaces

**Logic:**
1. If has both dots and commas: Macedonian format (dots=thousands, comma=decimal)
2. If only comma: decimal separator
3. If only dot(s):
   - Multiple dots = thousands separator
   - Single dot with 3 digits after = thousands (1.000 -> 1000)
   - Single dot with ≤2 digits after = could be decimal (context-dependent)

### 3. Improved Column Identification (lines 673-762)

**Enhanced column_patterns:**
```python
'unit_price': [
    'единечна цена', 'единична цена', 'единечна', 'единична',
    'ед. цена', 'ед.цена', 'един. цена', 'unit price', 'price per unit',
    'цена по единица', 'цена/ед'
],
'total_price_no_vat': [
    'вкупна цена', 'вкупно', 'вкупна', 'total price', 'total',
    'без ддв', 'total without vat', 'цена без', 'вкупно без ддв',
    'total w/o vat', 'укупна цена'
],
```

**Improved Fallbacks:**
1. Generic price column detection (any column with "цена"/"price")
2. Smart assignment based on column order
3. Detection of abbreviated headers ("ед.", "јед.")
4. Position-based inference (price after quantity column)

**Validation:**
- Requires 'name' column minimum
- Warns if no price columns found (but still processes)
- Logs identified price columns for debugging

### 4. Enhanced _extract_prices Method (lines 428-466)

**Improvements:**
- Uses centralized `_parse_macedonian_number()` parser
- Looks ahead 2 lines for multiline item descriptions
- Deduplicates prices across lines
- Returns up to 2 prices sorted (unit < total)

### 5. Unified price parsing in _extract_item_from_row (lines 764-825)

**Before:** Inline parse_price function with basic logic

**After:** Delegates to `_parse_macedonian_number()` after removing currency:
```python
def parse_price(val: str) -> Optional[Decimal]:
    if not val:
        return None
    # Remove currency suffix before parsing
    val = val.strip().replace(' ', '')
    val = val.replace('ден', '').replace('денари', '').replace('МКД', '').replace('MKD', '').strip()
    val = val.replace('EUR', '').replace('евро', '').replace('€', '').strip()
    # Use the centralized parser
    return self._parse_macedonian_number(val)
```

### 6. Better Logging and Diagnostics

Added comprehensive logging:
- Table header identification (DEBUG level)
- Column mapping results (DEBUG level)
- Individual price parsing (DEBUG level with before/after values)
- Price extraction statistics (INFO level)
- Warnings for tables without price columns

**Example log output:**
```
DEBUG: Identifying columns from header: ['Назив на ставка', 'Количина', 'Единечна цена', 'Вкупна цена']
DEBUG: Table 0: Column mapping: {'name': 0, 'quantity': 1, 'unit_price': 2, 'total_price_no_vat': 3}
DEBUG: Parsed unit_price: '1.210,00' -> 1210.00
DEBUG: Parsed total_price_no_vat: '6.504.960,00' -> 6504960.00
INFO: Extracted 15 items from 3 tables. Prices: unit=12/15 (80.0%), total=14/15 (93.3%)
```

## Expected Impact

### Before:
- Price extraction: 0%
- No diagnostic information
- Silent failures on Macedonian formats

### After (Expected):
- Price extraction: 50-80% (realistic target given document variety)
- Detailed logging for troubleshooting
- Handles standard Macedonian procurement document formats
- Graceful degradation (extracts items even without prices)

## Test Coverage

Created `test_price_extraction.py` with:
1. Number parser tests (11 test cases)
2. Column identification tests (4 header formats)
3. End-to-end table extraction test

Run with: `python test_price_extraction.py`

## Macedonian Format Examples Handled

| Input           | Parsed Value | Description                          |
|-----------------|--------------|--------------------------------------|
| 2.000,00        | 2000.00      | Standard format with decimals        |
| 19.399,00       | 19399.00     | Typical price                        |
| 1.234.567,89    | 1234567.89   | Large number with multiple thousands |
| 500             | 500          | Simple integer                       |
| 500,50          | 500.50       | Decimal with comma                   |
| 1.000           | 1000         | Thousands separator only             |
| 2.000,00 ден    | 2000.00      | With currency suffix                 |

## Files Modified

1. `/Users/tamsar/Downloads/nabavkidata/scraper/spec_extractor.py`
   - Lines 20: Added `InvalidOperation` import
   - Lines 167-184: Enhanced PRICE_PATTERNS
   - Lines 428-466: Improved _extract_prices method
   - Lines 468-547: New _parse_macedonian_number method
   - Lines 588-597: Added table/column logging
   - Lines 609-624: Price extraction statistics
   - Lines 650-762: Enhanced _identify_columns with better patterns and validation
   - Lines 773-802: Added price parsing logging

## Files Created

1. `/Users/tamsar/Downloads/nabavkidata/scraper/test_price_extraction.py`
   - Comprehensive test suite for price extraction
   - Tests number parsing, column identification, and table extraction

## Recommendations

1. **Monitor Logs**: Check extraction logs to see which documents still fail
2. **Iterate**: Add new patterns based on real-world document variations
3. **Database Query**: After deployment, run:
   ```sql
   SELECT
     COUNT(*) as total_items,
     COUNT(unit_price) as items_with_unit_price,
     COUNT(total_price) as items_with_total_price,
     ROUND(100.0 * COUNT(unit_price) / COUNT(*), 1) as unit_price_pct,
     ROUND(100.0 * COUNT(total_price) / COUNT(*), 1) as total_price_pct
   FROM product_items
   WHERE extraction_source = 'technical_specs';
   ```

4. **Edge Cases**: Keep a collection of problematic documents for regression testing

## Next Steps

1. Run test suite to verify changes
2. Deploy to production
3. Monitor extraction rates
4. Collect failing examples
5. Iterate on patterns as needed
