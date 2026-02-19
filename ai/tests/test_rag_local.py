"""
Local RAG Tests - Tests RAG functions directly without API authentication
Run: cd /Users/tamsar/Downloads/nabavkidata && python3 ai/tests/test_rag_local.py
"""

import asyncio
import sys
import os
import time
from typing import List, Dict

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '../..'))

# Set required env vars - don't hardcode API keys
os.environ.setdefault('DATABASE_URL', os.getenv('DATABASE_URL'))
# GEMINI_API_KEY should be set in environment (e.g., from .env on EC2)

from rag_query import execute_tool, DATA_SOURCE_TOOLS
from db_pool import get_pool, get_connection


# Core edge case test prompts - subset for quick local testing
CORE_TEST_CASES = [
    # Analytical queries
    {"id": 1, "tool": "get_top_tenders", "args": {"sort_by": "value_desc", "limit": 5},
     "description": "Largest 5 tenders", "expect_results": True},
    {"id": 2, "tool": "get_top_tenders", "args": {"sort_by": "value_desc", "limit": 10, "year": 2024},
     "description": "Largest tenders in 2024", "expect_results": True},
    {"id": 3, "tool": "get_top_tenders", "args": {"sort_by": "date_desc", "limit": 10},
     "description": "Most recent tenders", "expect_results": True},
    {"id": 4, "tool": "get_top_tenders", "args": {"sort_by": "value_asc", "limit": 5},
     "description": "Smallest tenders", "expect_results": True},
    {"id": 5, "tool": "get_top_tenders", "args": {"status": "awarded", "limit": 5},
     "description": "Awarded tenders", "expect_results": True},
    {"id": 6, "tool": "get_top_tenders", "args": {"institution_type": "општина", "limit": 5},
     "description": "Municipality tenders", "expect_results": True},

    # Search queries
    {"id": 7, "tool": "search_tenders", "args": {"keywords": ["лекови"]},
     "description": "Drug tenders", "expect_results": True},
    {"id": 8, "tool": "search_tenders", "args": {"keywords": ["компјутери", "IT"]},
     "description": "IT tenders", "expect_results": True},
    {"id": 9, "tool": "search_tenders", "args": {"keywords": ["градежни работи"]},
     "description": "Construction tenders", "expect_results": True},

    # Product item queries
    {"id": 10, "tool": "search_product_items", "args": {"keywords": ["лаптоп"]},
     "description": "Laptop prices", "expect_results": True},
    {"id": 11, "tool": "search_product_items", "args": {"keywords": ["хартија А4"]},
     "description": "A4 paper prices", "expect_results": True},

    # Entity profile queries
    {"id": 12, "tool": "get_entity_profile", "args": {"entity_name": "Град Скопје"},
     "description": "City of Skopje profile", "expect_results": True},
    {"id": 13, "tool": "get_entity_profile", "args": {"entity_name": "Министерство за здравство"},
     "description": "Health ministry profile", "expect_results": True},

    # Competitor queries
    {"id": 14, "tool": "analyze_competitors", "args": {"analysis_type": "top_competitors"},
     "description": "Top competitors overall", "expect_results": True},
    {"id": 15, "tool": "analyze_competitors", "args": {"analysis_type": "win_rate", "company_name": "Алкалоид"},
     "description": "Win rates for Alkaloid", "expect_results": True},

    # Price statistics
    {"id": 16, "tool": "get_price_statistics", "args": {"keywords": ["инсулин"]},
     "description": "Insulin price stats", "expect_results": True},
    {"id": 17, "tool": "get_price_statistics", "args": {"keywords": ["тонер"]},
     "description": "Toner price stats", "expect_results": True},

    # Document search
    {"id": 18, "tool": "search_bid_documents", "args": {"keywords": ["рамковен договор"]},
     "description": "Framework agreements in docs", "expect_results": True},

    # Tender by ID
    {"id": 19, "tool": "get_tender_by_id", "args": {"tender_id": "21555/2021"},
     "description": "Specific tender by ID", "expect_results": True},
    {"id": 20, "tool": "get_tender_by_id", "args": {"tender_id": "00362/2019"},
     "description": "Another specific tender", "expect_results": True},

    # Edge cases - should handle gracefully
    {"id": 21, "tool": "search_tenders", "args": {"keywords": ["XYZ123QWERTY"]},
     "description": "Nonsense query", "expect_results": False},
    {"id": 22, "tool": "get_entity_profile", "args": {"entity_name": "XXXXXXXXXX"},
     "description": "Non-existent entity", "expect_results": False},
    {"id": 23, "tool": "get_tender_by_id", "args": {"tender_id": "99999999/9999"},
     "description": "Non-existent tender ID", "expect_results": False},

    # Short keywords
    {"id": 24, "tool": "search_tenders", "args": {"keywords": ["IT"]},
     "description": "Very short keyword", "expect_results": True},
    {"id": 25, "tool": "search_tenders", "args": {"keywords": ["а"]},
     "description": "Single char keyword", "expect_results": False},
]


async def run_test(conn, test: Dict) -> Dict:
    """Run a single test case"""
    start = time.time()
    try:
        result = await execute_tool(test["tool"], test["args"], conn)
        elapsed = time.time() - start

        # Check if we got results
        has_results = result and len(result) > 50 and "Не најдов" not in result and "Непознат" not in result

        # Determine pass/fail
        passed = has_results == test["expect_results"]

        return {
            "id": test["id"],
            "description": test["description"],
            "tool": test["tool"],
            "passed": passed,
            "expected_results": test["expect_results"],
            "got_results": has_results,
            "elapsed": elapsed,
            "result_length": len(result) if result else 0,
            "result_preview": result[:200] if result else ""
        }
    except Exception as e:
        return {
            "id": test["id"],
            "description": test["description"],
            "tool": test["tool"],
            "passed": False,
            "error": str(e),
            "elapsed": time.time() - start
        }


async def main():
    print("=" * 80)
    print("RAG LOCAL TESTS")
    print("Testing RAG tools directly (no API)")
    print("=" * 80)
    print()

    pool = await get_pool()

    results = []
    async with pool.acquire() as conn:
        for i, test in enumerate(CORE_TEST_CASES, 1):
            print(f"[{i:2d}/{len(CORE_TEST_CASES)}] {test['description']:40s}", end=" ")
            result = await run_test(conn, test)
            results.append(result)

            if result.get("passed"):
                print(f"✅ PASS ({result['elapsed']:.2f}s, {result['result_length']} chars)")
            elif result.get("error"):
                print(f"❌ ERROR: {result['error'][:50]}")
            else:
                print(f"⚠️ FAIL (expected={result['expected_results']}, got={result['got_results']})")

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r.get("passed"))
    failed = sum(1 for r in results if not r.get("passed") and not r.get("error"))
    errors = sum(1 for r in results if r.get("error"))

    print(f"✅ PASSED: {passed}/{len(results)}")
    print(f"⚠️ FAILED: {failed}/{len(results)}")
    print(f"❌ ERRORS: {errors}/{len(results)}")

    # Show failures
    failures = [r for r in results if not r.get("passed")]
    if failures:
        print()
        print("=" * 80)
        print("FAILURES DETAIL")
        print("=" * 80)
        for f in failures:
            print(f"\n[{f['id']}] {f['description']}")
            print(f"    Tool: {f['tool']}")
            if f.get("error"):
                print(f"    Error: {f['error']}")
            else:
                print(f"    Expected: {f.get('expected_results')}, Got: {f.get('got_results')}")
                print(f"    Preview: {f.get('result_preview', 'N/A')[:100]}")

    await pool.close()
    return results


if __name__ == "__main__":
    asyncio.run(main())
