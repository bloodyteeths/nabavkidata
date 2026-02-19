# Comprehensive RAG Test Suite - Summary

## Created Files

### 1. `/Users/tamsar/Downloads/nabavkidata/ai/tests/test_comprehensive_rag.py`
**Main test suite - 50 comprehensive test cases**

Size: 27 KB (28,598 bytes)

### 2. `/Users/tamsar/Downloads/nabavkidata/ai/tests/README_COMPREHENSIVE_TESTS.md`
**Documentation and usage guide**

### 3. `/Users/tamsar/Downloads/nabavkidata/ai/tests/validate_test_suite.py`
**Validation script to verify test suite structure**

---

## Test Suite Coverage: 50 Tests

### Distribution by Category

| Category | Tests | Description |
|----------|-------|-------------|
| **ANALYTICAL** | 10 | Statistical queries, aggregations, trends |
| **PRICE** | 8 | Product pricing queries, price statistics |
| **ENTITY** | 6 | Company/institution profiles |
| **TOP_LISTS** | 6 | Rankings and sorted results |
| **SEARCH** | 8 | Keyword-based tender searches |
| **COMPETITION** | 4 | Competitive analysis, win rates, market share |
| **CURRENT** | 4 | Real-time/recent data queries |
| **EDGE_CASE** | 4 | Security tests, robustness validation |

---

## Validation Criteria

### ✅ Each Test Checks:

1. **Response is not empty** - Must have actual content
2. **No forbidden patterns** - NO redirects to e-nabavki or "go elsewhere"
3. **Contains data indicators** - Numbers, prices, entity names
4. **Meets minimum length** - 100-200 chars depending on query type
5. **Handles errors gracefully** - No crashes on edge cases

### 🚫 Forbidden Patterns (11 patterns)

Tests ensure responses NEVER contain:
- `e-nabavki.gov.mk` - Direct site references
- `посети.*e-nabavki` - "Visit e-nabavki" in Macedonian
- `отиди на.*e-nabavki` - "Go to e-nabavki" in Macedonian
- `провери на.*сајт` - "Check on website" in Macedonian
- `check.*website` - "Check website" in English
- `go to.*website` - "Go to website" redirects
- `visit.*e-nabavki` - "Visit e-nabavki" redirects
- `немам пристап до` - "I don't have access to"
- `не можам да пристапам` - "I cannot access"
- `cannot access` - Access denial in English
- `don't have access` - Access denial patterns

### ✅ Data Indicators (3 patterns)

Responses MUST contain:
- `\d+` - Any numbers (counts, IDs, years)
- `МКД|денари|mkd` - Currency amounts
- `^\d{2,}` - Multi-digit numbers (values, counts)

---

## Example Test Cases

### ANALYTICAL
```python
{
    "id": "A001",
    "description": "Која институција објавува најмногу тендери?",
    "tool": "get_top_tenders",
    "args": {"sort_by": "date_desc", "limit": 100},
    "expect_data": True,
    "expect_numbers": True,
    "min_length": 200,
}
```

### PRICE
```python
{
    "id": "P001",
    "description": "Колку чини лаптоп?",
    "tool": "search_product_items",
    "args": {"keywords": ["лаптоп"]},
    "expect_data": True,
    "expect_numbers": True,
    "min_length": 150,
}
```

### ENTITY
```python
{
    "id": "E001",
    "description": "Кажи ми за Град Скопје",
    "tool": "get_entity_profile",
    "args": {"entity_name": "Град Скопје"},
    "expect_data": True,
    "expect_numbers": True,
    "min_length": 200,
}
```

### EDGE_CASE
```python
{
    "id": "EDGE002",
    "description": "SQL injection attempt (should be sanitized)",
    "tool": "search_tenders",
    "args": {"keywords": ["'; DROP TABLE tenders; --"]},
    "expect_data": False,
    "expect_numbers": False,
    "min_length": 0,
}
```

---

## How to Run

### Basic Run
```bash
cd /Users/tamsar/Downloads/nabavkidata
python3 ai/tests/test_comprehensive_rag.py
```

### Validate Test Suite Structure
```bash
python3 ai/tests/validate_test_suite.py
```

### Prerequisites
1. Database connection configured (`DATABASE_URL` env var)
2. Gemini API key set (`GEMINI_API_KEY` env var)
3. Python 3.9+ with required packages

---

## Test Output Example

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
[50/ 50] EDGE004   Special characters query                    ✅ PASS (0.2s, 45 chars)

================================================================================
SUMMARY BY CATEGORY
================================================================================
ANALYTICAL          : 10/10 passed (100.0%) | Failed:  0 | Errors:  0
PRICE               :  8/ 8 passed (100.0%) | Failed:  0 | Errors:  0
ENTITY              :  6/ 6 passed (100.0%) | Failed:  0 | Errors:  0
...

================================================================================
CRITICAL VALIDATION CHECKS
================================================================================
1. No 'e-nabavki redirect' responses: ✅ PASS (0 violations)
2. Data queries return actual data: ✅ PASS (42/42)
3. Edge cases handled gracefully: ✅ PASS (0 crashes)
```

---

## Key Features

### 1. Comprehensive Coverage
- Tests EVERY type of query users might ask
- Covers all RAG tools (search_tenders, get_price_statistics, analyze_competitors, etc.)
- Includes edge cases and security tests

### 2. Anti-Redirect Validation
- **PRIMARY GOAL**: Ensure we NEVER tell users to "go to e-nabavki"
- Checks 11 forbidden patterns in multiple languages
- Fails test if any redirect pattern detected

### 3. Data Quality Validation
- Ensures responses contain actual data (not just empty responses)
- Checks for numbers, prices, entity names
- Validates minimum response length

### 4. Security Testing
- SQL injection attempts
- XSS attempts
- Very long inputs
- Empty inputs
- Special characters

### 5. Detailed Reporting
- Real-time progress during test run
- Category-based summaries
- Detailed failure reports with exact reasons
- Forbidden pattern violation reports

---

## Success Criteria

The test suite ensures:

✅ **NO "go to e-nabavki" responses** - Critical requirement
✅ **Actual data returned** - For all data queries
✅ **Graceful error handling** - No crashes on edge cases
✅ **Complete coverage** - All query types tested
✅ **Security validated** - Input sanitization works

---

## Future Enhancements

Potential additions:
1. Performance benchmarks (response time thresholds)
2. More edge cases (Unicode, emoji, very long Macedonian text)
3. Integration with CI/CD pipeline
4. Automated regression testing
5. Coverage reports

---

## Validation Results

**Test Suite Structure Validation: ✅ PASSED**

- ✅ Total tests: 50/50
- ✅ All categories meet requirements
- ✅ Forbidden patterns: 11 configured
- ✅ Validation functions present
- ✅ Complete test coverage

**File Size:** 27 KB
**Lines of Code:** ~900 lines
**Configuration:** Production-ready

---

## Contact

For issues or questions about the test suite, check:
- README_COMPREHENSIVE_TESTS.md (detailed documentation)
- validate_test_suite.py (structure validation)
- test_rag_local.py (simpler test suite for reference)
