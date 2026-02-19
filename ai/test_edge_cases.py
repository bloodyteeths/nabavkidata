#!/usr/bin/env python3
"""
30 Edge Case Tests for RAG System

Tests cover:
1. Product searches (5 cases)
2. Price queries (5 cases)
3. Winner analysis (5 cases)
4. Bidder/competitor analysis (5 cases)
5. Time-based queries (4 cases)
6. Institution queries (3 cases)
7. Edge cases - language, typos, complex (3 cases)

Each test is evaluated for:
- Response received (not error)
- Contains real data (numbers, names)
- Response time
- No hallucination indicators
"""

import asyncio
import os
import time
import json
import re
from datetime import datetime
from typing import Dict, List, Tuple

# Set environment
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL')
os.environ['GEMINI_API_KEY'] = 'YOUR_GEMINI_API_KEY'

from rag_query import LLMDrivenAgent

# =============================================================================
# 30 EDGE CASE TEST QUERIES
# =============================================================================

EDGE_CASES = [
    # =========================================================================
    # PRODUCT SEARCHES (5 cases)
    # =========================================================================
    {
        "id": 1,
        "category": "product_search",
        "query": "тендери за лаптопи",
        "expected": ["лаптоп", "компјутер", "преносен"],
        "description": "Basic laptop tender search"
    },
    {
        "id": 2,
        "category": "product_search",
        "query": "канцелариски материјали",
        "expected": ["хартија", "тонер", "материјал"],
        "description": "Office supplies search"
    },
    {
        "id": 3,
        "category": "product_search",
        "query": "медицинска опрема",
        "expected": ["медицин", "здравств", "болниц"],
        "description": "Medical equipment search"
    },
    {
        "id": 4,
        "category": "product_search",
        "query": "градежни работи",
        "expected": ["градеж", "изградба", "реконструкција"],
        "description": "Construction works search"
    },
    {
        "id": 5,
        "category": "product_search",
        "query": "софтвер и IT услуги",
        "expected": ["софтвер", "систем", "IT", "информатичк"],
        "description": "Software and IT services"
    },

    # =========================================================================
    # PRICE QUERIES (5 cases)
    # =========================================================================
    {
        "id": 6,
        "category": "price_query",
        "query": "колку чини лаптоп во јавни набавки?",
        "expected": ["МКД", "цена", "просечн"],
        "description": "Laptop price query"
    },
    {
        "id": 7,
        "category": "price_query",
        "query": "просечна цена за тонер за печатач",
        "expected": ["МКД", "цена", "тонер"],
        "description": "Toner price query"
    },
    {
        "id": 8,
        "category": "price_query",
        "query": "цени на канцелариски столици",
        "expected": ["МКД", "цена", "стол"],
        "description": "Office chair prices"
    },
    {
        "id": 9,
        "category": "price_query",
        "query": "минимална и максимална цена за монитори",
        "expected": ["МКД", "минимал", "максимал"],
        "description": "Monitor price range"
    },
    {
        "id": 10,
        "category": "price_query",
        "query": "споредба на цени за канцелариски материјали по институции",
        "expected": ["МКД", "институци", "цена"],
        "description": "Price comparison by institution"
    },

    # =========================================================================
    # WINNER ANALYSIS (5 cases)
    # =========================================================================
    {
        "id": 11,
        "category": "winner_analysis",
        "query": "кој најчесто победува на IT тендери?",
        "expected": ["победник", "компанија", "ДООЕЛ", "win"],
        "description": "Top IT tender winner"
    },
    {
        "id": 12,
        "category": "winner_analysis",
        "query": "win rate на Алкалоид",
        "expected": ["%", "стапка", "победи", "Алкалоид"],
        "description": "Alkaloid win rate"
    },
    {
        "id": 13,
        "category": "winner_analysis",
        "query": "победници на тендери за храна",
        "expected": ["победник", "храна", "добавувач"],
        "description": "Food tender winners"
    },
    {
        "id": 14,
        "category": "winner_analysis",
        "query": "кој доби најголемиот тендер во 2024?",
        "expected": ["МКД", "вредност", "компанија"],
        "description": "Biggest 2024 tender winner"
    },
    {
        "id": 15,
        "category": "winner_analysis",
        "query": "market share во CPV 33 медицински производи",
        "expected": ["%", "удел", "пазар", "компанија"],
        "description": "Medical products market share"
    },

    # =========================================================================
    # BIDDER/COMPETITOR ANALYSIS (5 cases)
    # =========================================================================
    {
        "id": 16,
        "category": "competitor_analysis",
        "query": "кои се главни конкуренти за IT опрема?",
        "expected": ["конкурент", "компанија", "понудувач"],
        "description": "IT equipment competitors"
    },
    {
        "id": 17,
        "category": "competitor_analysis",
        "query": "колку понудувачи имаше на последните IT тендери?",
        "expected": ["понудувач", "број", "тендер"],
        "description": "Number of IT bidders"
    },
    {
        "id": 18,
        "category": "competitor_analysis",
        "query": "споредба: А1 vs Телеком Македонија",
        "expected": ["А1", "Телеком", "споредба"],
        "description": "A1 vs Telekom comparison"
    },
    {
        "id": 19,
        "category": "competitor_analysis",
        "query": "кои компании најчесто се натпреваруваат заедно?",
        "expected": ["компанија", "тендер", "заедно"],
        "description": "Companies bidding together"
    },
    {
        "id": 20,
        "category": "competitor_analysis",
        "query": "топ 5 добавувачи на канцелариски материјали",
        "expected": ["добавувач", "компанија", "канцелариск"],
        "description": "Top 5 office supply vendors"
    },

    # =========================================================================
    # TIME-BASED QUERIES (4 cases)
    # =========================================================================
    {
        "id": 21,
        "category": "time_query",
        "query": "тендери за компјутери од Q1 2024",
        "expected": ["2024", "компјутер", "тендер"],
        "description": "Q1 2024 computer tenders"
    },
    {
        "id": 22,
        "category": "time_query",
        "query": "активни тендери од последните 30 дена",
        "expected": ["активен", "тендер"],
        "description": "Active tenders last 30 days"
    },
    {
        "id": 23,
        "category": "time_query",
        "query": "IT набавки во ноември 2024",
        "expected": ["2024", "ноември", "IT"],
        "description": "November 2024 IT procurement"
    },
    {
        "id": 24,
        "category": "time_query",
        "query": "тендери објавени минатата недела",
        "expected": ["тендер", "објав"],
        "description": "Tenders from last week"
    },

    # =========================================================================
    # INSTITUTION QUERIES (3 cases)
    # =========================================================================
    {
        "id": 25,
        "category": "institution_query",
        "query": "тендери на Министерство за здравство",
        "expected": ["здравство", "Министерство", "тендер"],
        "description": "Ministry of Health tenders"
    },
    {
        "id": 26,
        "category": "institution_query",
        "query": "набавки на Општина Центар",
        "expected": ["Центар", "општина", "набавка"],
        "description": "Municipality Centar procurement"
    },
    {
        "id": 27,
        "category": "institution_query",
        "query": "кој е најголем купувач на IT опрема?",
        "expected": ["институција", "набавувач", "IT"],
        "description": "Biggest IT buyer"
    },

    # =========================================================================
    # EDGE CASES - LANGUAGE, TYPOS, COMPLEX (3 cases)
    # =========================================================================
    {
        "id": 28,
        "category": "edge_case",
        "query": "laptops tenders Macedonia",
        "expected": ["laptop", "тендер", "компјутер"],
        "description": "English query"
    },
    {
        "id": 29,
        "category": "edge_case",
        "query": "хируршки драперии и медицински материјали за болници",
        "expected": ["медицин", "болниц", "хируршк"],
        "description": "Complex medical query"
    },
    {
        "id": 30,
        "category": "edge_case",
        "query": "препорака за цена на компјутери за државна институција",
        "expected": ["цена", "препорака", "компјутер"],
        "description": "Price recommendation query"
    },
]


# =============================================================================
# TEST RUNNER
# =============================================================================

class TestResult:
    def __init__(self, test_id: int, query: str):
        self.test_id = test_id
        self.query = query
        self.success = False
        self.response = ""
        self.response_time = 0.0
        self.has_data = False
        self.expected_found = []
        self.expected_missing = []
        self.error = None
        self.warnings = []

    def to_dict(self) -> Dict:
        return {
            "id": self.test_id,
            "query": self.query,
            "success": self.success,
            "response_time": self.response_time,
            "has_data": self.has_data,
            "expected_found": self.expected_found,
            "expected_missing": self.expected_missing,
            "error": self.error,
            "warnings": self.warnings,
            "response_preview": self.response[:500] if self.response else ""
        }


async def run_single_test(agent: LLMDrivenAgent, test_case: Dict) -> TestResult:
    """Run a single test case"""
    result = TestResult(test_case["id"], test_case["query"])

    print(f"\n[Test {test_case['id']:02d}] {test_case['description']}")
    print(f"   Query: {test_case['query'][:60]}...")

    try:
        start_time = time.time()
        response = await agent.answer_question(test_case["query"])
        result.response_time = time.time() - start_time
        result.response = response
        result.success = True

        # Check for expected keywords
        response_lower = response.lower()
        for expected in test_case["expected"]:
            if expected.lower() in response_lower:
                result.expected_found.append(expected)
            else:
                result.expected_missing.append(expected)

        # Check if response has actual data (numbers, company names)
        has_numbers = bool(re.search(r'\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?\s*(?:МКД|MKD|%)', response))
        has_companies = bool(re.search(r'(?:ДООЕЛ|ДОО|АД|ООД|Друштво)', response, re.IGNORECASE))
        has_tender_ids = bool(re.search(r'\d{4,6}/\d{4}', response))

        result.has_data = has_numbers or has_companies or has_tender_ids

        # Check for hallucination indicators
        hallucination_phrases = [
            "не можам да потврдам",
            "немам информации",
            "не располагам со",
            "измислени податоци"
        ]
        for phrase in hallucination_phrases:
            if phrase in response_lower:
                result.warnings.append(f"Possible uncertainty: '{phrase}'")

        # Check for "not found" responses
        not_found_phrases = [
            "не најдов",
            "нема податоци",
            "не се пронајдени"
        ]
        for phrase in not_found_phrases:
            if phrase in response_lower:
                result.warnings.append(f"No data found: '{phrase}'")

        # Report
        status = "✓ PASS" if result.has_data and len(result.expected_found) > 0 else "⚠ WEAK" if result.success else "✗ FAIL"
        print(f"   {status} ({result.response_time:.1f}s) - Found: {result.expected_found}, Missing: {result.expected_missing}")

        if result.warnings:
            for w in result.warnings:
                print(f"   ⚠ {w}")

    except Exception as e:
        result.error = str(e)
        result.success = False
        print(f"   ✗ ERROR: {e}")

    return result


async def run_all_tests() -> Dict:
    """Run all 30 edge case tests"""
    print("=" * 70)
    print("RAG SYSTEM EDGE CASE TESTING - 30 Test Cases")
    print("=" * 70)

    agent = LLMDrivenAgent()
    results = []

    start_time = time.time()

    for test_case in EDGE_CASES:
        result = await run_single_test(agent, test_case)
        results.append(result)

        # Small delay between tests to avoid rate limiting
        await asyncio.sleep(1)

    total_time = time.time() - start_time

    # Generate summary
    passed = sum(1 for r in results if r.success and r.has_data and len(r.expected_found) > 0)
    weak = sum(1 for r in results if r.success and (not r.has_data or len(r.expected_found) == 0))
    failed = sum(1 for r in results if not r.success)

    avg_time = sum(r.response_time for r in results) / len(results)

    summary = {
        "total_tests": len(results),
        "passed": passed,
        "weak": weak,
        "failed": failed,
        "pass_rate": f"{passed/len(results)*100:.1f}%",
        "avg_response_time": f"{avg_time:.1f}s",
        "total_time": f"{total_time:.1f}s",
        "timestamp": datetime.now().isoformat()
    }

    # Category breakdown
    categories = {}
    for r in results:
        cat = next((t["category"] for t in EDGE_CASES if t["id"] == r.test_id), "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0, "failed": 0}
        categories[cat]["total"] += 1
        if r.success and r.has_data:
            categories[cat]["passed"] += 1
        else:
            categories[cat]["failed"] += 1

    summary["by_category"] = categories

    # Failed tests detail
    failed_tests = [r.to_dict() for r in results if not r.success or not r.has_data]

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Passed: {passed} ({passed/len(results)*100:.1f}%)")
    print(f"Weak: {weak} ({weak/len(results)*100:.1f}%)")
    print(f"Failed: {failed} ({failed/len(results)*100:.1f}%)")
    print(f"Average Response Time: {avg_time:.1f}s")
    print(f"Total Time: {total_time:.1f}s")

    print("\nBy Category:")
    for cat, stats in categories.items():
        pct = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({pct:.0f}%)")

    if failed_tests:
        print(f"\n⚠ FAILED/WEAK TESTS ({len(failed_tests)}):")
        for ft in failed_tests:
            print(f"  [{ft['id']:02d}] {ft['query'][:50]}...")
            if ft['error']:
                print(f"       Error: {ft['error'][:100]}")
            if ft['warnings']:
                print(f"       Warnings: {ft['warnings']}")

    return {
        "summary": summary,
        "results": [r.to_dict() for r in results],
        "failed_tests": failed_tests
    }


if __name__ == "__main__":
    report = asyncio.run(run_all_tests())

    # Save report
    with open("/tmp/edge_case_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nReport saved to: /tmp/edge_case_test_report.json")
