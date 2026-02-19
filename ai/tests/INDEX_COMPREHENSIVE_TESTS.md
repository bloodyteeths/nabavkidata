# Comprehensive RAG Test Suite - Index

## Quick Navigation

### 🚀 Getting Started
- **[QUICK_START.md](QUICK_START.md)** - Start here! Quick guide to running tests

### 📖 Documentation
- **[README_COMPREHENSIVE_TESTS.md](README_COMPREHENSIVE_TESTS.md)** - Full documentation
- **[TEST_SUITE_SUMMARY.md](TEST_SUITE_SUMMARY.md)** - Summary with examples

### 🧪 Test Files
- **[test_comprehensive_rag.py](test_comprehensive_rag.py)** - Main test suite (50 tests)
- **[validate_test_suite.py](validate_test_suite.py)** - Structure validation

---

## File Descriptions

### test_comprehensive_rag.py (29 KB)
**Main test suite with 50 comprehensive test cases**

Contains:
- 50 test cases across 8 categories
- 11 forbidden pattern checks (no e-nabavki redirects)
- 3 data indicator checks (actual data verification)
- Full validation logic
- Detailed reporting

Run:
```bash
python3 ai/tests/test_comprehensive_rag.py
```

### validate_test_suite.py (5.2 KB)
**Validation script to verify test suite structure**

Checks:
- All 50 tests are present
- Category distribution is correct
- Forbidden patterns are configured
- Data indicators are configured
- Validation functions exist

Run:
```bash
python3 ai/tests/validate_test_suite.py
```

### README_COMPREHENSIVE_TESTS.md (7.4 KB)
**Full documentation and usage guide**

Includes:
- Test category descriptions
- Validation criteria explained
- Example test cases
- Troubleshooting guide
- Integration with CI/CD

### TEST_SUITE_SUMMARY.md (7.5 KB)
**Summary, examples, and validation criteria**

Includes:
- Test distribution table
- Example test cases from each category
- Forbidden patterns list
- Data indicators list
- Expected output examples

### QUICK_START.md (6.4 KB)
**Quick start guide and troubleshooting**

Includes:
- Quick run commands
- Test category overview
- Expected output
- Common troubleshooting
- Adding new tests

---

## Test Coverage Overview

| Category | Tests | Description |
|----------|-------|-------------|
| **ANALYTICAL** | 10 | Statistics, aggregations, trends |
| **PRICE** | 8 | Product pricing, price statistics |
| **ENTITY** | 6 | Company/institution profiles |
| **TOP_LISTS** | 6 | Rankings and sorted results |
| **SEARCH** | 8 | Keyword-based tender searches |
| **COMPETITION** | 4 | Competitive analysis, win rates |
| **CURRENT** | 4 | Real-time/recent data queries |
| **EDGE_CASE** | 4 | Security tests, robustness |
| **TOTAL** | **50** | **Complete coverage** |

---

## Common Use Cases

### I want to run the tests
→ See [QUICK_START.md](QUICK_START.md)

### I want to understand what's being tested
→ See [TEST_SUITE_SUMMARY.md](TEST_SUITE_SUMMARY.md)

### I want to add new tests
→ See [README_COMPREHENSIVE_TESTS.md](README_COMPREHENSIVE_TESTS.md) - "Adding New Tests" section

### I want to validate the test suite structure
→ Run `validate_test_suite.py`

### I need troubleshooting help
→ See [QUICK_START.md](QUICK_START.md) - "Troubleshooting" section

### I want to see all test cases
→ See [TEST_SUITE_SUMMARY.md](TEST_SUITE_SUMMARY.md) or run the test with verbose output

---

## Validation Criteria

### ✅ Each Test Verifies:

1. **No e-nabavki redirects** (11 forbidden patterns)
   - e-nabavki.gov.mk
   - "посети e-nabavki" / "visit e-nabavki"
   - "отиди на" / "go to" redirects
   - "check website" / "провери на сајт"
   - "немам пристап" / "don't have access"
   - etc.

2. **Actual data returned** (3 data indicators)
   - Numbers (counts, IDs, years)
   - Currency (МКД, денари, mkd)
   - Multi-digit numbers (values, prices)

3. **Response quality**
   - Not empty
   - Meets minimum length (100-200 chars)
   - Contains relevant information

4. **Security**
   - SQL injection handled
   - XSS handled
   - Edge cases don't crash

---

## Quick Reference

### Run Tests
```bash
cd /Users/tamsar/Downloads/nabavkidata
python3 ai/tests/test_comprehensive_rag.py
```

### Validate Structure
```bash
python3 ai/tests/validate_test_suite.py
```

### Check Test Count
```bash
grep -c '"id":' ai/tests/test_comprehensive_rag.py
# Should output: 50
```

### View Forbidden Patterns
```bash
grep -A 15 "FORBIDDEN_PATTERNS" ai/tests/test_comprehensive_rag.py
```

---

## Success Metrics

A successful test run shows:
- ✅ 50/50 tests passed
- ✅ 0 forbidden pattern violations
- ✅ All data queries return actual data (42/42)
- ✅ All edge cases handled gracefully (0 crashes)

---

## File Locations

All files are in:
```
/Users/tamsar/Downloads/nabavkidata/ai/tests/
```

Related files:
- `/ai/rag_query.py` - RAG implementation being tested
- `/ai/tests/test_rag_local.py` - Simpler test suite (25 tests)
- `/ai/tests/edge_case_prompts.py` - Edge case prompt examples

---

## Next Steps

1. **Fix rag_query.py** - Resolve syntax error on line 2730
2. **Run validation** - `python3 ai/tests/validate_test_suite.py`
3. **Run tests** - `python3 ai/tests/test_comprehensive_rag.py`
4. **Review failures** - Check "FAILURES DETAIL" section if any
5. **Iterate** - Fix issues and re-run

---

## Support

For issues or questions:
1. Check [QUICK_START.md](QUICK_START.md) troubleshooting section
2. Review [README_COMPREHENSIVE_TESTS.md](README_COMPREHENSIVE_TESTS.md) documentation
3. Validate structure with `validate_test_suite.py`
4. Check test output "FAILURES DETAIL" section

---

**Created:** 2025-12-19
**Location:** `/Users/tamsar/Downloads/nabavkidata/ai/tests/`
**Status:** ✅ Complete and ready to use
