# Comprehensive RAG Test Suite

## Overview

The comprehensive RAG test suite (`test_comprehensive_rag.py`) validates that our RAG system NEVER returns "go to e-nabavki" type responses and ALWAYS provides actual data for user queries.

## Quick Start

```bash
cd /Users/tamsar/Downloads/nabavkidata
python3 ai/tests/test_comprehensive_rag.py
```

## Test Coverage (50+ Tests)

### Test Categories

1. **ANALYTICAL (10 tests)** - Statistical and aggregation queries
   - "Која институција објавува најмногу тендери?"
   - "Кој победува најчесто?"
   - "Колку тендери има вкупно?"
   - "Тендери по години?"
   - "Најголем буџет по институција?"
   - etc.

2. **PRICE (8 tests)** - Product pricing queries
   - "Колку чини лаптоп?"
   - "Просечна цена за инсулин?"
   - "Цена на хартија А4?"
   - "Price range за автомобили?"
   - etc.

3. **ENTITY (6 tests)** - Company/institution profiles
   - "Кажи ми за Град Скопје"
   - "Профил на Алкалоид"
   - "Министерство за здравство профил"
   - etc.

4. **TOP LISTS (6 tests)** - Rankings and sorted results
   - "Најголеми тендери"
   - "Top 10 по вредност"
   - "Најнови тендери"
   - etc.

5. **SEARCH (8 tests)** - Keyword-based tender searches
   - "Тендери за лекови"
   - "Набавки на компјутери"
   - "Градежни работи тендери"
   - etc.

6. **COMPETITION (4 tests)** - Competitive analysis
   - "Кој е конкурент на Алкалоид?"
   - "Market share analysis"
   - "Co-bidding patterns"
   - etc.

7. **CURRENT/ACTIVE (4 tests)** - Real-time data queries
   - "Активни тендери"
   - "Најнови огласи"
   - "Recent hospital tenders"
   - etc.

8. **EDGE CASES (4 tests)** - Security and robustness
   - Empty queries
   - SQL injection attempts
   - Very long queries
   - Special characters

## Validation Checks

Each test validates:

### 1. NO FORBIDDEN PATTERNS
Tests check that responses do NOT contain:
- `e-nabavki.gov.mk`
- "посети e-nabavki"
- "отиди на e-nabavki"
- "провери на сајт"
- "check website"
- "go to website"
- "немам пристап до"
- "не можам да пристапам"

### 2. ACTUAL DATA PROVIDED
For data queries, responses must contain:
- Numbers (tender counts, prices, IDs)
- Currency amounts (МКД, денари)
- Actual entity names
- Minimum length (100-200 chars depending on query)

### 3. GRACEFUL ERROR HANDLING
Edge cases should:
- Not crash the system
- Return appropriate error messages
- Be sanitized (SQL injection, XSS, etc.)

## Test Output

The test suite provides:

1. **Real-time progress** - Shows each test as it runs
2. **Summary by category** - Pass/fail breakdown per category
3. **Overall statistics** - Total pass rate
4. **Critical validation checks**:
   - ✅ No 'e-nabavki redirect' responses
   - ✅ Data queries return actual data
   - ✅ Edge cases handled gracefully
5. **Detailed failure reports** - Shows exactly what went wrong

## Example Output

```
================================================================================
COMPREHENSIVE RAG TEST SUITE
================================================================================
Total tests: 50

Tests by category:
  ANALYTICAL          : 10 tests
  COMPETITION         :  4 tests
  CURRENT             :  4 tests
  EDGE_CASE           :  4 tests
  ENTITY              :  6 tests
  PRICE               :  8 tests
  SEARCH              :  8 tests
  TOP_LISTS           :  6 tests
================================================================================

[  1/ 50] A001     Која институција објавува најмногу тендери?  ✅ PASS (0.8s, 1234 chars)
[  2/ 50] A002     Кој победува најчесто во тендери?            ✅ PASS (0.5s, 876 chars)
...

================================================================================
SUMMARY BY CATEGORY
================================================================================
ANALYTICAL          : 10/10 passed (100.0%) | Failed:  0 | Errors:  0
COMPETITION         :  4/ 4 passed (100.0%) | Failed:  0 | Errors:  0
CURRENT             :  4/ 4 passed (100.0%) | Failed:  0 | Errors:  0
EDGE_CASE           :  4/ 4 passed (100.0%) | Failed:  0 | Errors:  0
ENTITY              :  6/ 6 passed (100.0%) | Failed:  0 | Errors:  0
PRICE               :  8/ 8 passed (100.0%) | Failed:  0 | Errors:  0
SEARCH              :  8/ 8 passed (100.0%) | Failed:  0 | Errors:  0
TOP_LISTS           :  6/ 6 passed (100.0%) | Failed:  0 | Errors:  0

================================================================================
OVERALL SUMMARY
================================================================================
Total tests:              50
✅ PASSED:                50 (100.0%)
⚠️ FAILED:                 0 (0.0%)
❌ ERRORS:                0 (0.0%)
🚫 FORBIDDEN VIOLATIONS:  0

================================================================================
CRITICAL VALIDATION CHECKS
================================================================================
1. No 'e-nabavki redirect' responses: ✅ PASS (0 violations)
2. Data queries return actual data: ✅ PASS (42/42)
3. Edge cases handled gracefully: ✅ PASS (0 crashes)
```

## Test Structure

Each test case is defined as:

```python
{
    "id": "A001",                          # Unique test ID
    "category": "ANALYTICAL",              # Test category
    "description": "Која институција објавува најмногу тендери?",
    "tool": "get_top_tenders",             # Tool to call
    "args": {"sort_by": "date_desc", "limit": 100},
    "expect_data": True,                   # Should return data
    "expect_numbers": True,                # Should contain numbers
    "min_length": 200,                     # Minimum response length
}
```

## Adding New Tests

To add new tests:

1. Add to `COMPREHENSIVE_TEST_CASES` array
2. Assign unique ID (format: `CATEGORY###`)
3. Set appropriate validation criteria
4. Run test suite to verify

Example:

```python
{
    "id": "A011",
    "category": "ANALYTICAL",
    "description": "Your new test description",
    "tool": "appropriate_tool",
    "args": {"your": "args"},
    "expect_data": True,
    "expect_numbers": True,
    "min_length": 150,
}
```

## Integration with CI/CD

This test suite can be integrated into CI/CD pipelines:

```bash
# Run tests and check exit code
python3 ai/tests/test_comprehensive_rag.py
if [ $? -ne 0 ]; then
    echo "Tests failed!"
    exit 1
fi
```

## Troubleshooting

### Database Connection Issues
- Ensure `DATABASE_URL` environment variable is set
- Check database is accessible from your network

### Gemini API Issues
- Ensure `GEMINI_API_KEY` is set in environment
- Check API quota and limits

### Test Failures
- Check the "FAILURES DETAIL" section in output
- Look for forbidden pattern violations
- Verify minimum length requirements

## Related Files

- `/Users/tamsar/Downloads/nabavkidata/ai/tests/test_rag_local.py` - Simpler test suite (25 tests)
- `/Users/tamsar/Downloads/nabavkidata/ai/rag_query.py` - Main RAG implementation
- `/Users/tamsar/Downloads/nabavkidata/ai/tests/edge_case_prompts.py` - Edge case prompts
