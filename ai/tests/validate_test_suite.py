"""
Quick validation script to verify the comprehensive test suite structure
Run: python3 ai/tests/validate_test_suite.py
"""

import re
from collections import Counter, defaultdict

# Read the test file
test_file = '/Users/tamsar/Downloads/nabavkidata/ai/tests/test_comprehensive_rag.py'
with open(test_file, 'r') as f:
    content = f.read()

print("=" * 80)
print("COMPREHENSIVE RAG TEST SUITE - VALIDATION")
print("=" * 80)
print()

# Count test cases
test_count = content.count('"id":')
print(f"✅ Total test cases: {test_count}")

# Check minimum requirement
if test_count >= 50:
    print(f"   ✓ Meets requirement (50+ tests)")
else:
    print(f"   ✗ Below requirement (need 50+ tests)")

# Extract categories
categories = re.findall(r'"category":\s*"(\w+)"', content)
cat_counts = Counter(categories)

print()
print("Test distribution by category:")
print("-" * 80)

category_requirements = {
    "ANALYTICAL": 10,
    "PRICE": 8,
    "ENTITY": 6,
    "TOP_LISTS": 6,
    "SEARCH": 8,
    "COMPETITION": 4,
    "CURRENT": 4,
    "EDGE_CASE": 4,
}

all_met = True
for cat, required in sorted(category_requirements.items()):
    actual = cat_counts.get(cat, 0)
    status = "✓" if actual >= required else "✗"
    print(f"  {status} {cat:20s}: {actual:2d}/{required:2d} tests", end="")
    if actual >= required:
        print(" ✅")
    else:
        print(f" ⚠️ (need {required - actual} more)")
        all_met = False

print()
if all_met:
    print("✅ All category requirements met!")
else:
    print("⚠️ Some categories need more tests")

# Extract forbidden patterns
print()
print("Forbidden patterns check:")
print("-" * 80)
forbidden_section = re.search(r'FORBIDDEN_PATTERNS = \[(.*?)\]', content, re.DOTALL)
if forbidden_section:
    patterns = re.findall(r'r\'([^\']+)\'', forbidden_section.group(1))
    print(f"✅ Total forbidden patterns: {len(patterns)}")
    print()
    print("Checking for:")
    checks = [
        ("e-nabavki redirects", r'e-nabavki'),
        ("website redirects", r'website'),
        ("access denial patterns", r'пристап|access'),
        ("go to / visit patterns", r'отиди|посети|visit|go to'),
    ]

    for check_name, check_pattern in checks:
        matched = [p for p in patterns if re.search(check_pattern, p, re.IGNORECASE)]
        if matched:
            print(f"  ✓ {check_name}: {len(matched)} patterns")
        else:
            print(f"  ⚠️ {check_name}: No patterns found")

# Data indicator patterns
print()
print("Data indicator patterns check:")
print("-" * 80)
data_section = re.search(r'DATA_INDICATORS = \[(.*?)\]', content, re.DOTALL)
if data_section:
    patterns = re.findall(r'r\'([^\']+)\'', data_section.group(1))
    print(f"✅ Total data indicator patterns: {len(patterns)}")
    for p in patterns:
        print(f"  - {p}")

# Check validation functions
print()
print("Validation functions check:")
print("-" * 80)
functions = [
    ("check_forbidden_patterns", "Checks for redirect patterns"),
    ("check_data_indicators", "Checks for actual data"),
    ("validate_response", "Overall response validation"),
]

for func_name, desc in functions:
    if f"def {func_name}" in content:
        print(f"  ✓ {func_name:30s} - {desc}")
    else:
        print(f"  ✗ {func_name:30s} - MISSING")

# Check test structure
print()
print("Test case structure validation:")
print("-" * 80)

required_fields = ["id", "category", "description", "tool", "args", "expect_data", "min_length"]
sample_test = re.search(r'\{[^}]*"id":\s*"A001"[^}]*\}', content, re.DOTALL)

if sample_test:
    test_text = sample_test.group(0)
    print("Sample test case (A001):")
    for field in required_fields:
        if f'"{field}"' in test_text:
            print(f"  ✓ {field}")
        else:
            print(f"  ⚠️ {field} - optional or missing")

# Check documentation
print()
print("Documentation check:")
print("-" * 80)

doc_items = [
    ('Module docstring', r'"""[\s\S]*?Comprehensive RAG Test Suite'),
    ('Run command', r'Run:.*python3.*test_comprehensive_rag.py'),
    ('Requirements list', r'REQUIREMENTS:'),
    ('Category descriptions', r'Categories tested:'),
]

for doc_name, pattern in doc_items:
    if re.search(pattern, content):
        print(f"  ✓ {doc_name}")
    else:
        print(f"  ⚠️ {doc_name} - not found")

# Final summary
print()
print("=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

validation_items = [
    (test_count >= 50, f"Total tests: {test_count}/50+"),
    (all_met, "All categories meet requirements"),
    (len(patterns) >= 10, f"Forbidden patterns: {len(patterns)}"),
    ("def validate_response" in content, "Validation functions present"),
    (test_count == 50, f"Exact test count matches: {test_count}"),
]

passed = sum(1 for check, _ in validation_items if check)
total = len(validation_items)

for check, desc in validation_items:
    status = "✅" if check else "⚠️"
    print(f"{status} {desc}")

print()
print(f"Overall: {passed}/{total} validation checks passed")

if passed == total:
    print()
    print("🎉 TEST SUITE VALIDATION COMPLETE - ALL CHECKS PASSED! 🎉")
else:
    print()
    print("⚠️ Some validation checks need attention")

print()
print("=" * 80)
print(f"File: {test_file}")
print(f"Size: {len(content):,} bytes ({len(content)//1024} KB)")
print("=" * 80)
