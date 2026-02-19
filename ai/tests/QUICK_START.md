# Comprehensive RAG Test Suite - Quick Start Guide

## What This Test Suite Does

Tests that our RAG system **NEVER** tells users to "go to e-nabavki.gov.mk" and **ALWAYS** provides actual data from our database.

## Files Created

```
/Users/tamsar/Downloads/nabavkidata/ai/tests/
├── test_comprehensive_rag.py       (29 KB) - Main test suite with 50 tests
├── validate_test_suite.py          (5 KB)  - Validation script
├── README_COMPREHENSIVE_TESTS.md   (7 KB)  - Full documentation
├── TEST_SUITE_SUMMARY.md           (7 KB)  - Summary and examples
└── QUICK_START.md                  (this file)
```

## Run the Tests

```bash
cd /Users/tamsar/Downloads/nabavkidata
python3 ai/tests/test_comprehensive_rag.py
```

**Note:** Before running, ensure `rag_query.py` has no syntax errors (currently has error on line 2730).

## Validate Test Suite Structure

```bash
python3 ai/tests/validate_test_suite.py
```

This checks that:
- ✅ All 50 test cases are present
- ✅ All 8 categories have the required number of tests
- ✅ Forbidden patterns are configured
- ✅ Data indicators are configured
- ✅ Validation functions exist

## Test Categories (50 Total)

| Category | Tests | Example Query |
|----------|-------|---------------|
| ANALYTICAL | 10 | "Која институција објавува најмногу тендери?" |
| PRICE | 8 | "Колку чини лаптоп?" |
| ENTITY | 6 | "Кажи ми за Град Скопје" |
| TOP_LISTS | 6 | "Најголеми тендери" |
| SEARCH | 8 | "Тендери за лекови" |
| COMPETITION | 4 | "Кој е конкурент на Алкалоид?" |
| CURRENT | 4 | "Активни тендери" |
| EDGE_CASE | 4 | SQL injection, XSS, empty queries |

## What Gets Tested

### ✅ Each Test Verifies:

1. **No e-nabavki redirects** - Response must NOT contain:
   - `e-nabavki.gov.mk`
   - "посети e-nabavki"
   - "отиди на e-nabavki"
   - "check website"
   - etc. (11 forbidden patterns total)

2. **Actual data returned** - Response must contain:
   - Numbers (counts, IDs, years)
   - Currency (МКД, денари)
   - Entity names
   - Minimum 100-200 characters

3. **Graceful error handling** - Edge cases should not crash

## Expected Output

```
================================================================================
COMPREHENSIVE RAG TEST SUITE
================================================================================
Total tests: 50

Tests by category:
  ANALYTICAL          : 10 tests
  PRICE               :  8 tests
  ENTITY              :  6 tests
  TOP_LISTS           :  6 tests
  SEARCH              :  8 tests
  COMPETITION         :  4 tests
  CURRENT             :  4 tests
  EDGE_CASE           :  4 tests
================================================================================

[  1/ 50] A001     Која институција објавува најмногу тендери?  ✅ PASS (0.8s)
[  2/ 50] A002     Кој победува најчесто во тендери?            ✅ PASS (0.5s)
...
[50/ 50] EDGE004   Special characters query                    ✅ PASS (0.2s)

================================================================================
CRITICAL VALIDATION CHECKS
================================================================================
1. No 'e-nabavki redirect' responses: ✅ PASS (0 violations)
2. Data queries return actual data: ✅ PASS (42/42)
3. Edge cases handled gracefully: ✅ PASS (0 crashes)
```

## Key Test Examples

### Analytical Query
```python
# Test: "Која институција објавува најмногу тендери?"
# Tool: get_top_tenders
# Must return: Actual institution names with counts
# Must NOT: Tell user to visit e-nabavki
```

### Price Query
```python
# Test: "Колку чини лаптоп?"
# Tool: search_product_items
# Must return: Actual laptop prices in MKD
# Must NOT: Redirect to external website
```

### Entity Profile
```python
# Test: "Кажи ми за Град Скопје"
# Tool: get_entity_profile
# Must return: Statistics, tender history, categories
# Must NOT: Say "I don't have access to this data"
```

### Edge Case
```python
# Test: SQL injection attempt
# Tool: search_tenders
# Args: {"keywords": ["'; DROP TABLE tenders; --"]}
# Must: Handle gracefully without crashing or executing SQL
```

## Troubleshooting

### Test won't run
**Problem:** `rag_query.py` has syntax error on line 2730
**Solution:** Fix the syntax error first, then run tests

### Database connection failed
**Problem:** `DATABASE_URL` not set
**Solution:** Set environment variable:
```bash
export DATABASE_URL="postgresql://user:pass@host:port/db"
```

### Gemini API errors
**Problem:** `GEMINI_API_KEY` not set
**Solution:** Set environment variable:
```bash
export GEMINI_API_KEY="your-api-key"
```

### Test failures
**Check:** Look at "FAILURES DETAIL" section in output
**Common issues:**
- Forbidden pattern detected (e-nabavki redirect found)
- Response too short (missing data)
- No data indicators (missing numbers/prices)

## Adding New Tests

To add a new test:

```python
{
    "id": "A011",                    # Unique ID (Category + number)
    "category": "ANALYTICAL",        # One of 8 categories
    "description": "Your test description",
    "tool": "get_top_tenders",       # Tool to test
    "args": {"your": "args"},        # Tool arguments
    "expect_data": True,             # Should return data
    "expect_numbers": True,          # Should contain numbers
    "min_length": 150,               # Minimum response length
}
```

Add to `COMPREHENSIVE_TEST_CASES` array in `test_comprehensive_rag.py`.

## Success Metrics

A successful test run shows:
- ✅ 50/50 tests passed
- ✅ 0 forbidden pattern violations
- ✅ All data queries return actual data
- ✅ All edge cases handled gracefully

## Documentation

For more details, see:
- **README_COMPREHENSIVE_TESTS.md** - Full documentation
- **TEST_SUITE_SUMMARY.md** - Summary and examples
- **validate_test_suite.py** - Structure validation

## Quick Validation

```bash
# Check test suite structure
python3 ai/tests/validate_test_suite.py

# Should show:
# ✅ Total tests: 50/50+
# ✅ All categories meet requirements
# ✅ Validation functions present
```

## Contact / Issues

If tests fail unexpectedly:
1. Check database connection
2. Check Gemini API key
3. Look at failure details in output
4. Verify `rag_query.py` has no syntax errors
5. Check forbidden patterns section for violations
