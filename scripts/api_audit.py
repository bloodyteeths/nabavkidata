#!/usr/bin/env python3
"""
API Audit Script for nabavkidata.com
Tests all endpoints and analyzes data completeness
"""

import requests
import json
from collections import defaultdict
from datetime import datetime

BASE_URL = "http://46.224.89.197:8000"

def test_endpoint(method, path, expected_status=200, **kwargs):
    """Test a single endpoint"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10, **kwargs)
        elif method == "POST":
            resp = requests.post(url, timeout=10, **kwargs)

        status_ok = resp.status_code == expected_status

        try:
            data = resp.json()
        except:
            data = resp.text

        return {
            "status": resp.status_code,
            "ok": status_ok,
            "data": data,
            "error": None
        }
    except Exception as e:
        return {
            "status": 0,
            "ok": False,
            "data": None,
            "error": str(e)
        }

def analyze_missing_fields(items, field_list=None):
    """Analyze which fields are missing/null in a list of items"""
    if not items:
        return {}

    missing_counts = defaultdict(int)
    total = len(items)

    # Get all fields from first item if not provided
    if field_list is None:
        field_list = items[0].keys() if items else []

    for item in items:
        for field in field_list:
            if field not in item or item[field] is None or item[field] == "":
                missing_counts[field] += 1

    # Convert to percentages
    return {k: f"{v}/{total} ({v/total*100:.1f}%)" for k, v in missing_counts.items() if v > 0}

def main():
    results = []

    print("=" * 80)
    print("NABAVKIDATA API AUDIT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Base URL: {BASE_URL}")
    print("=" * 80)

    # Test 1: Health endpoint
    print("\n[1] Testing /health")
    result = test_endpoint("GET", "/health")
    results.append(("GET /health", result["status"], result["ok"], [], "", ""))
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")

    # Test 2: API health endpoint
    print("\n[2] Testing /api/health")
    result = test_endpoint("GET", "/api/health")
    results.append(("GET /api/health", result["status"], result["ok"], [], "", ""))
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")

    # Test 3: Tenders list
    print("\n[3] Testing /api/tenders")
    result = test_endpoint("GET", "/api/tenders", params={"page": 1, "page_size": 20})
    missing_fields = []
    if result["ok"] and "items" in result["data"]:
        items = result["data"]["items"]
        print(f"✓ Status {result['status']} - Returned {len(items)} items")
        missing = analyze_missing_fields(items)
        missing_fields = list(missing.keys())
        if missing:
            print(f"  Missing/null fields: {missing}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/tenders", result["status"], result["ok"], missing_fields, "", "Low"))

    # Test 4: Tenders stats/overview
    print("\n[4] Testing /api/tenders/stats/overview")
    result = test_endpoint("GET", "/api/tenders/stats/overview")
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
        print(f"  Total tenders: {result['data'].get('total_tenders', 'N/A')}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/tenders/stats/overview", result["status"], result["ok"], [], "", ""))

    # Test 5: Tenders stats/recent
    print("\n[5] Testing /api/tenders/stats/recent")
    result = test_endpoint("GET", "/api/tenders/stats/recent", params={"limit": 5})
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
        print(f"  Count: {result['data'].get('count', 'N/A')}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/tenders/stats/recent", result["status"], result["ok"], [], "", ""))

    # Test 6: Single tender by ID
    print("\n[6] Testing /api/tenders/{id}")
    result = test_endpoint("GET", "/api/tenders/21178%2F2025")
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/tenders/{id}", result["status"], result["ok"], [], "", ""))

    # Test 7: Tender documents
    print("\n[7] Testing /api/tenders/{id}/documents")
    result = test_endpoint("GET", "/api/tenders/21178%2F2025/documents")
    if result["status"] == 404:
        print(f"ℹ Status {result['status']} - No documents (expected for some tenders)")
        results.append(("GET /api/tenders/{id}/documents", result["status"], True, [], "No documents", "Low"))
    elif result["ok"]:
        print(f"✓ Status {result['status']} - OK")
        results.append(("GET /api/tenders/{id}/documents", result["status"], result["ok"], [], "", ""))
    else:
        print(f"✗ Status {result['status']} - FAILED")
        results.append(("GET /api/tenders/{id}/documents", result["status"], result["ok"], [], result.get("error", ""), "Medium"))

    # Test 8: Tender search (POST)
    print("\n[8] Testing POST /api/tenders/search")
    result = test_endpoint("POST", "/api/tenders/search",
                          json={"query": "набавка", "page": 1, "page_size": 5},
                          headers={"Content-Type": "application/json"})
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
        print(f"  Total results: {result['data'].get('total', 'N/A')}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("POST /api/tenders/search", result["status"], result["ok"], [], "", ""))

    # Test 9: e-Pazar tenders
    print("\n[9] Testing /api/epazar/tenders")
    result = test_endpoint("GET", "/api/epazar/tenders", params={"page": 1, "page_size": 10})
    missing_fields = []
    if result["ok"] and "items" in result["data"]:
        items = result["data"]["items"]
        print(f"✓ Status {result['status']} - Returned {len(items)} items")
        missing = analyze_missing_fields(items)
        missing_fields = list(missing.keys())
        if missing:
            print(f"  Missing/null fields: {missing}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/epazar/tenders", result["status"], result["ok"], missing_fields, "", "Low"))

    # Test 10: e-Pazar single tender
    print("\n[10] Testing /api/epazar/tenders/{id}")
    result = test_endpoint("GET", "/api/epazar/tenders/EPAZAR-901")
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/epazar/tenders/{id}", result["status"], result["ok"], [], "", ""))

    # Test 11: e-Pazar tender items
    print("\n[11] Testing /api/epazar/tenders/{id}/items")
    result = test_endpoint("GET", "/api/epazar/tenders/EPAZAR-901/items")
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
        print(f"  Items: {len(result['data']) if isinstance(result['data'], list) else 'N/A'}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/epazar/tenders/{id}/items", result["status"], result["ok"], [], "", ""))

    # Test 12: e-Pazar tender documents
    print("\n[12] Testing /api/epazar/tenders/{id}/documents")
    result = test_endpoint("GET", "/api/epazar/tenders/EPAZAR-901/documents")
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/epazar/tenders/{id}/documents", result["status"], result["ok"], [], "", ""))

    # Test 13: e-Pazar stats
    print("\n[13] Testing /api/epazar/stats/overview")
    result = test_endpoint("GET", "/api/epazar/stats/overview")
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
        print(f"  Total tenders: {result['data'].get('total_tenders', 'N/A')}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/epazar/stats/overview", result["status"], result["ok"], [], "", ""))

    # Test 14: Suppliers
    print("\n[14] Testing /api/suppliers")
    result = test_endpoint("GET", "/api/suppliers", params={"page": 1, "page_size": 10})
    missing_fields = []
    if result["ok"] and "items" in result["data"]:
        items = result["data"]["items"]
        print(f"✓ Status {result['status']} - Returned {len(items)} items")
        missing = analyze_missing_fields(items)
        missing_fields = list(missing.keys())
        if missing:
            print(f"  Missing/null fields: {missing}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/suppliers", result["status"], result["ok"], missing_fields, "Many contact fields missing", "Medium"))

    # Test 15: Entities
    print("\n[15] Testing /api/entities")
    result = test_endpoint("GET", "/api/entities", params={"page": 1, "page_size": 10})
    missing_fields = []
    if result["ok"] and "items" in result["data"]:
        items = result["data"]["items"]
        print(f"✓ Status {result['status']} - Returned {len(items)} items")
        missing = analyze_missing_fields(items)
        missing_fields = list(missing.keys())
        if missing:
            print(f"  Missing/null fields: {missing}")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/entities", result["status"], result["ok"], missing_fields, "Many entity details missing", "Medium"))

    # Test 16: Analytics - tenders stats
    print("\n[16] Testing /api/analytics/tenders/stats")
    result = test_endpoint("GET", "/api/analytics/tenders/stats")
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/analytics/tenders/stats", result["status"], result["ok"], [], "", ""))

    # Test 17: Analytics - entities stats
    print("\n[17] Testing /api/analytics/entities/stats")
    result = test_endpoint("GET", "/api/analytics/entities/stats")
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/analytics/entities/stats", result["status"], result["ok"], [], "", ""))

    # Test 18: Analytics - trends
    print("\n[18] Testing /api/analytics/trends")
    result = test_endpoint("GET", "/api/analytics/trends", params={"period": "7d"})
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/analytics/trends", result["status"], result["ok"], [], "", ""))

    # Test 19: e-Pazar suppliers
    print("\n[19] Testing /api/epazar/suppliers")
    result = test_endpoint("GET", "/api/epazar/suppliers", params={"page": 1, "page_size": 5})
    if result["ok"]:
        print(f"✓ Status {result['status']} - OK")
    else:
        print(f"✗ Status {result['status']} - FAILED")
    results.append(("GET /api/epazar/suppliers", result["status"], result["ok"], [], "", ""))

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Endpoint':<45} {'Status':<8} {'OK':<6} {'Missing Fields':<30} {'Issues':<25} {'Severity':<10}")
    print("-" * 140)

    for endpoint, status, ok, missing, issues, severity in results:
        ok_str = "✓" if ok else "✗"
        missing_str = ", ".join(missing[:3]) + ("..." if len(missing) > 3 else "") if missing else "-"
        print(f"{endpoint:<45} {status:<8} {ok_str:<6} {missing_str:<30} {issues:<25} {severity:<10}")

    # Overall stats
    total = len(results)
    passed = sum(1 for _, _, ok, _, _, _ in results if ok)
    failed = total - passed

    print("\n" + "=" * 80)
    print(f"TOTAL: {total} | PASSED: {passed} | FAILED: {failed}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    print("=" * 80)

if __name__ == "__main__":
    main()
