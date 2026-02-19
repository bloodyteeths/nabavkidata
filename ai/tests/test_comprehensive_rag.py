"""
Comprehensive RAG Test Suite - Validates RAG never returns "go to e-nabavki" responses

This test suite ensures that:
1. EVERY query type users might ask is tested
2. We NEVER return "go to e-nabavki" or redirect-type responses
3. We ALWAYS return actual data for data queries
4. Edge cases are handled gracefully

Run: cd /Users/tamsar/Downloads/nabavkidata && python3 ai/tests/test_comprehensive_rag.py

Categories tested:
- ANALYTICAL (10 tests): Statistics, aggregations, trends
- PRICE (8 tests): Product pricing queries
- ENTITY (6 tests): Company/institution profiles
- TOP LISTS (6 tests): Rankings and sorted results
- SEARCH (8 tests): Keyword-based tender searches
- COMPETITION (4 tests): Competitive analysis
- CURRENT/ACTIVE (4 tests): Real-time data queries
- EDGE CASES (4 tests): Security and robustness
"""

import asyncio
import sys
import os
import time
import re
from typing import List, Dict
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()


# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '../..'))

# Set required env vars
os.environ.setdefault('DATABASE_URL', os.getenv('DATABASE_URL'))

from rag_query import execute_tool, DATA_SOURCE_TOOLS
from db_pool import get_pool, get_connection


# ============================================================================
# FORBIDDEN PATTERNS - These should NEVER appear in responses
# ============================================================================
FORBIDDEN_PATTERNS = [
    r'e-nabavki\.gov\.mk',
    r'посети.*e-nabavki',
    r'отиди на.*e-nabavki',
    r'провери на.*сајт',
    r'check.*website',
    r'go to.*website',
    r'visit.*e-nabavki',
    r'немам пристап до',
    r'не можам да пристапам',
    r'cannot access',
    r"don't have access",
]

# Patterns that indicate we're providing actual data (good!)
DATA_INDICATORS = [
    r'\d+',  # Numbers
    r'МКД|денари|mkd',  # Currency
    r'^\d{2,}',  # Multi-digit numbers (counts, IDs, etc.)
]


# ============================================================================
# TEST CASES - 50+ comprehensive tests
# ============================================================================

COMPREHENSIVE_TEST_CASES = [
    # ========================================================================
    # ANALYTICAL QUERIES (10 tests)
    # ========================================================================
    {
        "id": "A001",
        "category": "ANALYTICAL",
        "description": "Која институција објавува најмногу тендери?",
        "tool": "get_top_tenders",
        "args": {"sort_by": "date_desc", "limit": 100},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "A002",
        "category": "ANALYTICAL",
        "description": "Кој победува најчесто во тендери?",
        "tool": "analyze_competitors",
        "args": {"analysis_type": "top_competitors"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "A003",
        "category": "ANALYTICAL",
        "description": "Колку тендери има вкупно?",
        "tool": "get_top_tenders",
        "args": {"sort_by": "value_desc", "limit": 50},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "A004",
        "category": "ANALYTICAL",
        "description": "Тендери по години breakdown",
        "tool": "get_top_tenders",
        "args": {"sort_by": "date_desc", "limit": 100},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "A005",
        "category": "ANALYTICAL",
        "description": "Најголем буџет по институција",
        "tool": "get_top_tenders",
        "args": {"sort_by": "value_desc", "limit": 20},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "A006",
        "category": "ANALYTICAL",
        "description": "Најмали тендери (по вредност)",
        "tool": "get_top_tenders",
        "args": {"sort_by": "value_asc", "limit": 10},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "A007",
        "category": "ANALYTICAL",
        "description": "Тендери од општини",
        "tool": "get_top_tenders",
        "args": {"institution_type": "општина", "limit": 20},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "A008",
        "category": "ANALYTICAL",
        "description": "Тендери од министерства",
        "tool": "get_top_tenders",
        "args": {"institution_type": "министерство", "limit": 20},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "A009",
        "category": "ANALYTICAL",
        "description": "Доделени тендери (awarded)",
        "tool": "get_top_tenders",
        "args": {"status": "awarded", "limit": 15},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "A010",
        "category": "ANALYTICAL",
        "description": "Тендери во 2024 година",
        "tool": "get_top_tenders",
        "args": {"year": 2024, "limit": 20},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },

    # ========================================================================
    # PRICE QUERIES (8 tests)
    # ========================================================================
    {
        "id": "P001",
        "category": "PRICE",
        "description": "Колку чини лаптоп?",
        "tool": "search_product_items",
        "args": {"keywords": ["лаптоп"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "P002",
        "category": "PRICE",
        "description": "Просечна цена за инсулин",
        "tool": "get_price_statistics",
        "args": {"keywords": ["инсулин"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "P003",
        "category": "PRICE",
        "description": "Цена на хартија А4",
        "tool": "search_product_items",
        "args": {"keywords": ["хартија", "А4"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "P004",
        "category": "PRICE",
        "description": "Колку чини тонер?",
        "tool": "get_price_statistics",
        "args": {"keywords": ["тонер"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "P005",
        "category": "PRICE",
        "description": "Просечна цена на компјутери",
        "tool": "search_product_items",
        "args": {"keywords": ["компјутер", "PC"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "P006",
        "category": "PRICE",
        "description": "Цени на медицинска опрема",
        "tool": "search_product_items",
        "args": {"keywords": ["медицинска опрема"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "P007",
        "category": "PRICE",
        "description": "Единечна цена на ракавици",
        "tool": "search_product_items",
        "args": {"keywords": ["ракавици"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "P008",
        "category": "PRICE",
        "description": "Price range за автомобили",
        "tool": "get_price_statistics",
        "args": {"keywords": ["автомобил", "возило"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },

    # ========================================================================
    # ENTITY PROFILE QUERIES (6 tests)
    # ========================================================================
    {
        "id": "E001",
        "category": "ENTITY",
        "description": "Кажи ми за Град Скопје",
        "tool": "get_entity_profile",
        "args": {"entity_name": "Град Скопје"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "E002",
        "category": "ENTITY",
        "description": "Профил на Алкалоид",
        "tool": "get_entity_profile",
        "args": {"entity_name": "Алкалоид"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "E003",
        "category": "ENTITY",
        "description": "Министерство за здравство профил",
        "tool": "get_entity_profile",
        "args": {"entity_name": "Министерство за здравство"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "E004",
        "category": "ENTITY",
        "description": "Општина Битола активности",
        "tool": "get_entity_profile",
        "args": {"entity_name": "Општина Битола"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "E005",
        "category": "ENTITY",
        "description": "Buyer profile - Клинички центар",
        "tool": "get_entity_profile",
        "args": {"entity_name": "Клинички центар", "entity_type": "buyer"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "E006",
        "category": "ENTITY",
        "description": "Supplier auto-detect profile",
        "tool": "get_entity_profile",
        "args": {"entity_name": "Технокомерц", "entity_type": "auto"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },

    # ========================================================================
    # TOP LISTS / RANKINGS (6 tests)
    # ========================================================================
    {
        "id": "T001",
        "category": "TOP_LISTS",
        "description": "Најголеми тендери (top)",
        "tool": "get_top_tenders",
        "args": {"sort_by": "value_desc", "limit": 10},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "T002",
        "category": "TOP_LISTS",
        "description": "Top 10 по вредност",
        "tool": "get_top_tenders",
        "args": {"sort_by": "value_desc", "limit": 10},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "T003",
        "category": "TOP_LISTS",
        "description": "Најнови 20 тендери",
        "tool": "get_top_tenders",
        "args": {"sort_by": "date_desc", "limit": 20},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "T004",
        "category": "TOP_LISTS",
        "description": "Top 5 smallest tenders",
        "tool": "get_top_tenders",
        "args": {"sort_by": "value_asc", "limit": 5},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "T005",
        "category": "TOP_LISTS",
        "description": "Top hospital tenders",
        "tool": "get_top_tenders",
        "args": {"institution_type": "болница", "limit": 10},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "T006",
        "category": "TOP_LISTS",
        "description": "Top winners by win rate",
        "tool": "analyze_competitors",
        "args": {"analysis_type": "win_rate"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },

    # ========================================================================
    # SEARCH QUERIES (8 tests)
    # ========================================================================
    {
        "id": "S001",
        "category": "SEARCH",
        "description": "Тендери за лекови",
        "tool": "search_tenders",
        "args": {"keywords": ["лекови"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 200,
    },
    {
        "id": "S002",
        "category": "SEARCH",
        "description": "Набавки на компјутери",
        "tool": "search_tenders",
        "args": {"keywords": ["компјутери", "IT"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "S003",
        "category": "SEARCH",
        "description": "Градежни работи тендери",
        "tool": "search_tenders",
        "args": {"keywords": ["градежни работи", "изградба"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "S004",
        "category": "SEARCH",
        "description": "Канцелариски материјали",
        "tool": "search_tenders",
        "args": {"keywords": ["канцелариски материјали"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "S005",
        "category": "SEARCH",
        "description": "Medical equipment search",
        "tool": "search_tenders",
        "args": {"keywords": ["медицинска опрема"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "S006",
        "category": "SEARCH",
        "description": "Vehicle procurement",
        "tool": "search_tenders",
        "args": {"keywords": ["возила", "автомобили"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "S007",
        "category": "SEARCH",
        "description": "Fuel tenders (гориво)",
        "tool": "search_tenders",
        "args": {"keywords": ["гориво"]},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "S008",
        "category": "SEARCH",
        "description": "IT equipment with date filter",
        "tool": "search_tenders",
        "args": {"keywords": ["IT"], "date_from": "2023-01-01"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },

    # ========================================================================
    # COMPETITION ANALYSIS (4 tests)
    # ========================================================================
    {
        "id": "C001",
        "category": "COMPETITION",
        "description": "Кој е конкурент на Алкалоид?",
        "tool": "analyze_competitors",
        "args": {"analysis_type": "head_to_head", "company_name": "Алкалоид"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "C002",
        "category": "COMPETITION",
        "description": "Market share analysis",
        "tool": "analyze_competitors",
        "args": {"analysis_type": "market_share"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "C003",
        "category": "COMPETITION",
        "description": "Co-bidding patterns (кои заедно учествуваат)",
        "tool": "analyze_competitors",
        "args": {"analysis_type": "co_bidding"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "C004",
        "category": "COMPETITION",
        "description": "Win rate for specific company",
        "tool": "analyze_competitors",
        "args": {"analysis_type": "win_rate", "company_name": "Технокомерц"},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },

    # ========================================================================
    # CURRENT/ACTIVE QUERIES (4 tests - web search OK for these)
    # ========================================================================
    {
        "id": "CR001",
        "category": "CURRENT",
        "description": "Активни тендери (recent as proxy)",
        "tool": "get_top_tenders",
        "args": {"sort_by": "date_desc", "limit": 10},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "CR002",
        "category": "CURRENT",
        "description": "Најнови огласи",
        "tool": "get_top_tenders",
        "args": {"sort_by": "date_desc", "limit": 15},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },
    {
        "id": "CR003",
        "category": "CURRENT",
        "description": "Recent tenders from hospitals",
        "tool": "get_top_tenders",
        "args": {"institution_type": "болница", "sort_by": "date_desc", "limit": 10},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 100,
    },
    {
        "id": "CR004",
        "category": "CURRENT",
        "description": "Latest awarded tenders",
        "tool": "get_top_tenders",
        "args": {"status": "awarded", "sort_by": "date_desc", "limit": 10},
        "expect_data": True,
        "expect_numbers": True,
        "min_length": 150,
    },

    # ========================================================================
    # EDGE CASES (4 tests - security and robustness)
    # ========================================================================
    {
        "id": "EDGE001",
        "category": "EDGE_CASE",
        "description": "Empty keyword array",
        "tool": "search_tenders",
        "args": {"keywords": []},
        "expect_data": False,
        "expect_numbers": False,
        "min_length": 0,
    },
    {
        "id": "EDGE002",
        "category": "EDGE_CASE",
        "description": "SQL injection attempt (should be sanitized)",
        "tool": "search_tenders",
        "args": {"keywords": ["'; DROP TABLE tenders; --"]},
        "expect_data": False,
        "expect_numbers": False,
        "min_length": 0,
    },
    {
        "id": "EDGE003",
        "category": "EDGE_CASE",
        "description": "Very long query string",
        "tool": "search_tenders",
        "args": {"keywords": ["A" * 500]},
        "expect_data": False,
        "expect_numbers": False,
        "min_length": 0,
    },
    {
        "id": "EDGE004",
        "category": "EDGE_CASE",
        "description": "Special characters query",
        "tool": "search_tenders",
        "args": {"keywords": ["<script>alert('test')</script>"]},
        "expect_data": False,
        "expect_numbers": False,
        "min_length": 0,
    },
]


# ============================================================================
# TEST VALIDATION FUNCTIONS
# ============================================================================

def check_forbidden_patterns(text: str) -> List[str]:
    """Check if response contains forbidden redirect patterns"""
    violations = []
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append(pattern)
    return violations


def check_data_indicators(text: str) -> bool:
    """Check if response contains actual data (numbers, etc.)"""
    for pattern in DATA_INDICATORS:
        if re.search(pattern, text):
            return True
    return False


def validate_response(result: str, test: Dict) -> Dict:
    """Validate a single test response"""
    validation = {
        "has_content": bool(result and len(result) > 0),
        "meets_min_length": len(result) >= test.get("min_length", 100) if result else False,
        "has_forbidden_patterns": check_forbidden_patterns(result) if result else [],
        "has_data_indicators": check_data_indicators(result) if result else False,
        "has_numbers": bool(re.search(r'\d+', result)) if result else False,
        "result_length": len(result) if result else 0,
    }

    # Determine if test passed
    if test.get("expect_data"):
        # For data queries: must have content, no forbidden patterns, have data indicators
        validation["passed"] = (
            validation["has_content"] and
            len(validation["has_forbidden_patterns"]) == 0 and
            validation["has_data_indicators"] and
            validation["meets_min_length"]
        )
    else:
        # For edge cases: should handle gracefully (not crash)
        validation["passed"] = True  # Just don't crash

    return validation


# ============================================================================
# TEST RUNNER
# ============================================================================

async def run_test(conn, test: Dict) -> Dict:
    """Run a single test case"""
    start = time.time()
    try:
        result = await execute_tool(test["tool"], test["args"], conn)
        elapsed = time.time() - start

        validation = validate_response(result, test)

        return {
            **test,
            **validation,
            "elapsed": elapsed,
            "result_preview": result[:300] if result else "",
            "error": None,
        }
    except Exception as e:
        return {
            **test,
            "passed": False,
            "error": str(e),
            "elapsed": time.time() - start,
            "has_content": False,
            "has_forbidden_patterns": [],
            "result_length": 0,
        }


async def main():
    print("=" * 80)
    print("COMPREHENSIVE RAG TEST SUITE")
    print("=" * 80)
    print(f"Total tests: {len(COMPREHENSIVE_TEST_CASES)}")
    print()

    # Count by category
    by_category = defaultdict(int)
    for test in COMPREHENSIVE_TEST_CASES:
        by_category[test["category"]] += 1

    print("Tests by category:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat:20s}: {count:2d} tests")
    print()
    print("=" * 80)
    print()

    pool = await get_pool()
    results = []

    async with pool.acquire() as conn:
        for i, test in enumerate(COMPREHENSIVE_TEST_CASES, 1):
            print(f"[{i:3d}/{len(COMPREHENSIVE_TEST_CASES)}] {test['id']:8s} {test['description'][:45]:45s}", end=" ")
            result = await run_test(conn, test)
            results.append(result)

            if result.get("error"):
                print(f"❌ ERROR: {result['error'][:30]}")
            elif result.get("passed"):
                print(f"✅ PASS ({result['elapsed']:.1f}s, {result['result_length']} chars)")
            else:
                print(f"⚠️ FAIL")
                # Show why it failed
                if result.get("has_forbidden_patterns"):
                    print(f"         └─ Forbidden pattern: {result['has_forbidden_patterns'][0]}")
                elif not result.get("has_data_indicators") and test.get("expect_data"):
                    print(f"         └─ Missing data indicators")
                elif not result.get("meets_min_length"):
                    print(f"         └─ Too short ({result['result_length']} < {test.get('min_length')})")

    # ========================================================================
    # SUMMARY BY CATEGORY
    # ========================================================================
    print()
    print("=" * 80)
    print("SUMMARY BY CATEGORY")
    print("=" * 80)

    category_stats = defaultdict(lambda: {"passed": 0, "failed": 0, "errors": 0, "total": 0})

    for result in results:
        cat = result["category"]
        category_stats[cat]["total"] += 1
        if result.get("error"):
            category_stats[cat]["errors"] += 1
        elif result.get("passed"):
            category_stats[cat]["passed"] += 1
        else:
            category_stats[cat]["failed"] += 1

    for cat in sorted(category_stats.keys()):
        stats = category_stats[cat]
        pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"{cat:20s}: {stats['passed']:2d}/{stats['total']:2d} passed ({pass_rate:5.1f}%) | "
              f"Failed: {stats['failed']:2d} | Errors: {stats['errors']:2d}")

    # ========================================================================
    # OVERALL SUMMARY
    # ========================================================================
    print()
    print("=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    failed = sum(1 for r in results if not r.get("passed") and not r.get("error"))
    errors = sum(1 for r in results if r.get("error"))
    forbidden_violations = sum(1 for r in results if r.get("has_forbidden_patterns"))

    print(f"Total tests:              {total}")
    print(f"✅ PASSED:                {passed} ({passed/total*100:.1f}%)")
    print(f"⚠️ FAILED:                 {failed} ({failed/total*100:.1f}%)")
    print(f"❌ ERRORS:                {errors} ({errors/total*100:.1f}%)")
    print(f"🚫 FORBIDDEN VIOLATIONS:  {forbidden_violations}")

    # ========================================================================
    # CRITICAL CHECKS
    # ========================================================================
    print()
    print("=" * 80)
    print("CRITICAL VALIDATION CHECKS")
    print("=" * 80)

    # Check 1: No e-nabavki redirects
    redirect_count = sum(1 for r in results if r.get("has_forbidden_patterns"))
    print(f"1. No 'e-nabavki redirect' responses: ", end="")
    if redirect_count == 0:
        print("✅ PASS (0 violations)")
    else:
        print(f"❌ FAIL ({redirect_count} violations)")

    # Check 2: Data queries return actual data
    data_tests = [r for r in results if r.get("expect_data")]
    data_with_indicators = sum(1 for r in data_tests if r.get("has_data_indicators"))
    print(f"2. Data queries return actual data: ", end="")
    if data_with_indicators == len(data_tests):
        print(f"✅ PASS ({data_with_indicators}/{len(data_tests)})")
    else:
        print(f"⚠️ PARTIAL ({data_with_indicators}/{len(data_tests)})")

    # Check 3: No crashes on edge cases
    edge_cases = [r for r in results if r["category"] == "EDGE_CASE"]
    edge_errors = sum(1 for r in edge_cases if r.get("error"))
    print(f"3. Edge cases handled gracefully: ", end="")
    if edge_errors == 0:
        print(f"✅ PASS (0 crashes)")
    else:
        print(f"❌ FAIL ({edge_errors} crashes)")

    # ========================================================================
    # FAILURES DETAIL
    # ========================================================================
    failures = [r for r in results if not r.get("passed")]
    if failures:
        print()
        print("=" * 80)
        print(f"FAILURES DETAIL ({len(failures)} failures)")
        print("=" * 80)
        for f in failures:
            print(f"\n[{f['id']}] {f['description']}")
            print(f"    Category: {f['category']}")
            print(f"    Tool: {f['tool']}")
            if f.get("error"):
                print(f"    Error: {f['error']}")
            else:
                if f.get("has_forbidden_patterns"):
                    print(f"    ❌ Forbidden patterns: {f['has_forbidden_patterns']}")
                if not f.get("has_data_indicators") and f.get("expect_data"):
                    print(f"    ⚠️ Missing data indicators")
                if not f.get("meets_min_length"):
                    print(f"    ⚠️ Too short: {f['result_length']} < {f.get('min_length')}")
                print(f"    Preview: {f.get('result_preview', 'N/A')[:150]}")

    # ========================================================================
    # FORBIDDEN PATTERN VIOLATIONS
    # ========================================================================
    violations = [r for r in results if r.get("has_forbidden_patterns")]
    if violations:
        print()
        print("=" * 80)
        print(f"🚫 FORBIDDEN PATTERN VIOLATIONS ({len(violations)})")
        print("=" * 80)
        for v in violations:
            print(f"\n[{v['id']}] {v['description']}")
            print(f"    Patterns: {v['has_forbidden_patterns']}")
            print(f"    Preview: {v.get('result_preview', 'N/A')[:200]}")

    await pool.close()

    print()
    print("=" * 80)
    print("TEST RUN COMPLETE")
    print("=" * 80)

    return results


if __name__ == "__main__":
    asyncio.run(main())
