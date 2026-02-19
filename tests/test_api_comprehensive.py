#!/usr/bin/env python3
"""
Comprehensive API Testing Script for nabavkidata.com
Agent C - API Testing Engineer

Tests all endpoints across 7 categories:
1. Authentication Endpoints
2. Billing Endpoints
3. RAG Endpoints
4. Admin Endpoints
5. Scraper Endpoints
6. Fraud Endpoints
7. Personalization Endpoints
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import sys

# Configuration
API_BASE_URL = "https://api.nabavkidata.com"
# API_BASE_URL = "http://localhost:8000"  # Use this if testing locally

# Test user credentials
TEST_USER_EMAIL = "test-enterprise@nabavkidata.com"
TEST_USER_PASSWORD = "TestEnterprise2024!"

# Results tracking
test_results = []
auth_token = None


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def log_test(category: str, endpoint: str, method: str, status_code: int,
             response_time: float, success: bool, response_body: any = None,
             error: str = None):
    """Log test result"""
    result = {
        "category": category,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "response_time_ms": round(response_time * 1000, 2),
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
        "response_sample": str(response_body)[:200] if response_body else None,
        "error": error
    }
    test_results.append(result)

    # Console output
    status_icon = f"{Colors.GREEN}✓{Colors.RESET}" if success else f"{Colors.RED}✗{Colors.RESET}"
    print(f"{status_icon} [{category}] {method} {endpoint} - {status_code} ({response_time*1000:.0f}ms)")
    if error:
        print(f"  {Colors.RED}Error: {error}{Colors.RESET}")


def test_endpoint(category: str, method: str, endpoint: str,
                  headers: Dict = None, json_data: Dict = None,
                  params: Dict = None, expected_status: int = 200) -> Tuple[bool, any]:
    """Generic endpoint test function"""
    url = f"{API_BASE_URL}{endpoint}"

    try:
        start_time = time.time()

        if method == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=json_data, params=params, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=json_data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=json_data, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response_time = time.time() - start_time

        try:
            response_body = response.json()
        except:
            response_body = response.text

        success = response.status_code == expected_status

        log_test(category, endpoint, method, response.status_code,
                response_time, success, response_body)

        return success, response_body

    except requests.exceptions.RequestException as e:
        response_time = time.time() - start_time
        log_test(category, endpoint, method, 0, response_time, False, error=str(e))
        return False, None


def get_auth_headers() -> Dict:
    """Get authorization headers with token"""
    if auth_token:
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    return {"Content-Type": "application/json"}


# ============================================================================
# CATEGORY 1: AUTHENTICATION ENDPOINTS
# ============================================================================

def test_authentication():
    """Test authentication endpoints"""
    global auth_token

    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Authentication Endpoints ==={Colors.RESET}")

    # 1. POST /api/auth/login
    success, response = test_endpoint(
        "Authentication", "POST", "/api/auth/login",
        json_data={
            "username": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
    )

    if success and response:
        auth_token = response.get("access_token")
        print(f"{Colors.GREEN}✓ Authentication successful - token obtained{Colors.RESET}")

    # 2. GET /api/auth/me
    test_endpoint(
        "Authentication", "GET", "/api/auth/me",
        headers=get_auth_headers()
    )

    # 3. Test with invalid credentials (expect 401)
    test_endpoint(
        "Authentication", "POST", "/api/auth/login",
        json_data={
            "username": "invalid@test.com",
            "password": "wrongpassword"
        },
        expected_status=401
    )

    # 4. Test without token (expect 401)
    test_endpoint(
        "Authentication", "GET", "/api/auth/me",
        expected_status=401
    )


# ============================================================================
# CATEGORY 2: BILLING ENDPOINTS
# ============================================================================

def test_billing():
    """Test billing endpoints"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Billing Endpoints ==={Colors.RESET}")

    # 1. GET /api/billing/plans (public)
    test_endpoint("Billing", "GET", "/api/billing/plans")

    # 2. GET /api/billing/status (authenticated)
    test_endpoint(
        "Billing", "GET", "/api/billing/status",
        headers=get_auth_headers()
    )

    # 3. GET /api/billing/usage (authenticated)
    test_endpoint(
        "Billing", "GET", "/api/billing/usage",
        headers=get_auth_headers()
    )

    # 4. POST /api/billing/check-limit (authenticated)
    test_endpoint(
        "Billing", "POST", "/api/billing/check-limit",
        headers=get_auth_headers(),
        json_data={"action_type": "rag_query"}
    )

    # 5. GET /api/billing/invoices (authenticated)
    test_endpoint(
        "Billing", "GET", "/api/billing/invoices",
        headers=get_auth_headers()
    )

    # 6. GET /api/billing/payment-methods (authenticated)
    test_endpoint(
        "Billing", "GET", "/api/billing/payment-methods",
        headers=get_auth_headers()
    )

    # 7. Test upgrade endpoint (may fail if no subscription)
    test_endpoint(
        "Billing", "POST", "/api/billing/upgrade",
        headers=get_auth_headers(),
        json_data={"new_tier": "professional", "interval": "monthly"},
        expected_status=[200, 404, 400]  # May not have subscription to upgrade
    )


# ============================================================================
# CATEGORY 3: RAG ENDPOINTS
# ============================================================================

def test_rag():
    """Test RAG/AI endpoints"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing RAG Endpoints ==={Colors.RESET}")

    # 1. GET /api/rag/health (public)
    test_endpoint("RAG", "GET", "/api/rag/health")

    # 2. POST /api/rag/query (authenticated)
    test_endpoint(
        "RAG", "POST", "/api/rag/query",
        headers=get_auth_headers(),
        json_data={
            "question": "What are the latest construction tenders?",
            "top_k": 5
        }
    )

    # 3. POST /api/rag/query/stream (authenticated)
    # Note: streaming endpoint, just test it responds
    test_endpoint(
        "RAG", "POST", "/api/rag/query/stream",
        headers=get_auth_headers(),
        json_data={
            "question": "Tell me about IT equipment tenders",
            "top_k": 3
        }
    )

    # 4. POST /api/rag/search (authenticated)
    test_endpoint(
        "RAG", "POST", "/api/rag/search",
        headers=get_auth_headers(),
        json_data={
            "query": "medical supplies",
            "top_k": 10
        }
    )

    # 5. POST /api/rag/embed/document (authenticated) - NEW with auth
    test_endpoint(
        "RAG", "POST", "/api/rag/embed/document",
        headers=get_auth_headers(),
        json_data={
            "tender_id": "TEST-001",
            "doc_id": "DOC-TEST-001",
            "text": "This is a test document for embedding.",
            "metadata": {"test": True}
        }
    )


# ============================================================================
# CATEGORY 4: ADMIN ENDPOINTS
# ============================================================================

def test_admin():
    """Test admin endpoints (may require admin role)"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Admin Endpoints ==={Colors.RESET}")

    # 1. GET /admin/users (admin required, expect 403 for non-admin)
    test_endpoint(
        "Admin", "GET", "/admin/users",
        headers=get_auth_headers(),
        expected_status=[200, 403]
    )

    # 2. GET /admin/stats (admin required)
    test_endpoint(
        "Admin", "GET", "/admin/stats",
        headers=get_auth_headers(),
        expected_status=[200, 403, 404]
    )

    # 3. GET /admin/dashboard (admin required)
    test_endpoint(
        "Admin", "GET", "/admin/dashboard",
        headers=get_auth_headers(),
        expected_status=[200, 403]
    )

    # 4. GET /admin/vectors/health - NEW endpoint
    test_endpoint(
        "Admin", "GET", "/admin/vectors/health",
        headers=get_auth_headers(),
        expected_status=[200, 403]
    )


# ============================================================================
# CATEGORY 5: SCRAPER ENDPOINTS
# ============================================================================

def test_scraper():
    """Test scraper endpoints"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Scraper Endpoints ==={Colors.RESET}")

    # 1. GET /api/scraper/health (public) - NEW
    test_endpoint("Scraper", "GET", "/api/scraper/health")

    # 2. GET /api/scraper/jobs (admin required) - NEW
    test_endpoint(
        "Scraper", "GET", "/api/scraper/jobs",
        headers=get_auth_headers(),
        expected_status=[200, 403]
    )

    # 3. GET /api/scraper/status (admin required)
    test_endpoint(
        "Scraper", "GET", "/api/scraper/status",
        headers=get_auth_headers(),
        expected_status=[200, 403]
    )


# ============================================================================
# CATEGORY 6: FRAUD ENDPOINTS
# ============================================================================

def test_fraud():
    """Test fraud prevention endpoints"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Fraud Endpoints ==={Colors.RESET}")

    # 1. GET /api/fraud/events (authenticated)
    test_endpoint(
        "Fraud", "GET", "/api/fraud/events",
        headers=get_auth_headers(),
        expected_status=[200, 404]
    )

    # 2. POST /api/fraud/check (authenticated)
    test_endpoint(
        "Fraud", "POST", "/api/fraud/check",
        headers=get_auth_headers(),
        json_data={
            "ip_address": "127.0.0.1",
            "user_agent": "Test Agent",
            "check_type": "query",
            "fingerprint_data": {
                "device_fingerprint": "test-fingerprint",
                "browser": "Chrome",
                "os": "Linux"
            }
        }
    )

    # 3. GET /api/fraud/rate-limit (authenticated)
    test_endpoint(
        "Fraud", "GET", "/api/fraud/rate-limit",
        headers=get_auth_headers(),
        expected_status=[200, 404]
    )

    # 4. GET /api/fraud/tier-limits (public)
    test_endpoint("Fraud", "GET", "/api/fraud/tier-limits")


# ============================================================================
# CATEGORY 7: PERSONALIZATION ENDPOINTS
# ============================================================================

def test_personalization():
    """Test personalization endpoints"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Personalization Endpoints ==={Colors.RESET}")

    # 1. GET /api/personalization/digests - NEW
    test_endpoint(
        "Personalization", "GET", "/api/personalization/digests",
        headers=get_auth_headers(),
        expected_status=[200, 404]
    )

    # 2. GET /api/personalization/dashboard
    test_endpoint(
        "Personalization", "GET", "/api/personalization/dashboard",
        headers=get_auth_headers(),
        expected_status=[200, 404]
    )

    # 3. GET /api/personalization/insights
    test_endpoint(
        "Personalization", "GET", "/api/personalization/insights",
        headers=get_auth_headers(),
        expected_status=[200, 404]
    )


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

def test_rate_limiting():
    """Test rate limiting by making rapid requests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Rate Limiting ==={Colors.RESET}")

    print("Making 15 rapid requests to test rate limiting...")
    for i in range(15):
        success, _ = test_endpoint(
            "Rate Limiting", "GET", "/api/billing/plans",
            expected_status=[200, 429]
        )
        if not success:
            print(f"{Colors.YELLOW}Rate limit hit after {i+1} requests{Colors.RESET}")
            break
        time.sleep(0.1)


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_error_handling():
    """Test error handling for common scenarios"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Error Handling ==={Colors.RESET}")

    # 1. Test 404 - non-existent endpoint
    test_endpoint(
        "Error Handling", "GET", "/api/nonexistent",
        expected_status=404
    )

    # 2. Test 401 - unauthorized
    test_endpoint(
        "Error Handling", "GET", "/api/auth/me",
        expected_status=401
    )

    # 3. Test 422 - invalid data
    test_endpoint(
        "Error Handling", "POST", "/api/rag/query",
        headers=get_auth_headers(),
        json_data={"invalid": "data"},
        expected_status=422
    )


# ============================================================================
# GENERATE REPORT
# ============================================================================

def generate_report():
    """Generate comprehensive test report"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}API TEST RESULTS SUMMARY{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

    # Statistics
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r['success'])
    failed_tests = total_tests - passed_tests
    avg_response_time = sum(r['response_time_ms'] for r in test_results) / total_tests if total_tests > 0 else 0

    print(f"Total Tests: {total_tests}")
    print(f"{Colors.GREEN}Passed: {passed_tests}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed_tests}{Colors.RESET}")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    print(f"Average Response Time: {avg_response_time:.0f}ms\n")

    # Category breakdown
    categories = {}
    for result in test_results:
        cat = result['category']
        if cat not in categories:
            categories[cat] = {'passed': 0, 'failed': 0, 'total': 0}
        categories[cat]['total'] += 1
        if result['success']:
            categories[cat]['passed'] += 1
        else:
            categories[cat]['failed'] += 1

    print(f"{Colors.BOLD}Results by Category:{Colors.RESET}")
    for cat, stats in sorted(categories.items()):
        success_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        color = Colors.GREEN if success_rate >= 80 else Colors.YELLOW if success_rate >= 50 else Colors.RED
        print(f"  {cat}: {color}{stats['passed']}/{stats['total']} passed ({success_rate:.0f}%){Colors.RESET}")

    # Failed tests detail
    failed = [r for r in test_results if not r['success']]
    if failed:
        print(f"\n{Colors.BOLD}{Colors.RED}Failed Tests Details:{Colors.RESET}")
        for result in failed:
            print(f"  ✗ [{result['category']}] {result['method']} {result['endpoint']}")
            print(f"    Status: {result['status_code']}, Time: {result['response_time_ms']}ms")
            if result['error']:
                print(f"    Error: {result['error']}")

    # Write detailed report to file
    report_file = "API_TEST_RESULTS.md"
    with open(report_file, 'w') as f:
        f.write("# API Test Results\n\n")
        f.write(f"**Generated:** {datetime.utcnow().isoformat()}Z\n\n")
        f.write(f"**API Base URL:** {API_BASE_URL}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- **Total Tests:** {total_tests}\n")
        f.write(f"- **Passed:** {passed_tests} ({passed_tests/total_tests*100:.1f}%)\n")
        f.write(f"- **Failed:** {failed_tests} ({failed_tests/total_tests*100:.1f}%)\n")
        f.write(f"- **Average Response Time:** {avg_response_time:.0f}ms\n\n")

        f.write("## Results by Category\n\n")
        for cat, stats in sorted(categories.items()):
            success_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            status = "✅" if success_rate >= 80 else "⚠️" if success_rate >= 50 else "❌"
            f.write(f"### {status} {cat}\n\n")
            f.write(f"- Passed: {stats['passed']}/{stats['total']} ({success_rate:.0f}%)\n")
            f.write(f"- Failed: {stats['failed']}\n\n")

        f.write("## Detailed Test Results\n\n")
        for result in test_results:
            status_icon = "✅" if result['success'] else "❌"
            f.write(f"### {status_icon} {result['method']} {result['endpoint']}\n\n")
            f.write(f"- **Category:** {result['category']}\n")
            f.write(f"- **Status Code:** {result['status_code']}\n")
            f.write(f"- **Response Time:** {result['response_time_ms']}ms\n")
            f.write(f"- **Success:** {result['success']}\n")
            if result['error']:
                f.write(f"- **Error:** {result['error']}\n")
            if result['response_sample']:
                f.write(f"- **Response Sample:**\n```\n{result['response_sample']}\n```\n")
            f.write("\n")

        f.write("## Recommendations\n\n")
        if failed_tests > 0:
            f.write("### Failed Endpoints\n\n")
            for result in failed:
                f.write(f"- `{result['method']} {result['endpoint']}` - Status {result['status_code']}")
                if result['error']:
                    f.write(f" - {result['error']}")
                f.write("\n")
            f.write("\n")

        f.write("### Performance\n\n")
        slow_endpoints = [r for r in test_results if r['response_time_ms'] > 2000]
        if slow_endpoints:
            f.write("Endpoints with response time > 2s:\n\n")
            for result in slow_endpoints:
                f.write(f"- `{result['method']} {result['endpoint']}` - {result['response_time_ms']}ms\n")
        else:
            f.write("✅ All endpoints responded within 2 seconds.\n")

    print(f"\n{Colors.GREEN}✓ Detailed report written to: {report_file}{Colors.RESET}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main test execution"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}API Testing Suite - Agent C{Colors.RESET}")
    print(f"{Colors.BOLD}nabavkidata.com Comprehensive API Tests{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
    print(f"API Base URL: {Colors.BLUE}{API_BASE_URL}{Colors.RESET}")
    print(f"Test User: {Colors.BLUE}{TEST_USER_EMAIL}{Colors.RESET}\n")

    try:
        # Run test suites
        test_authentication()
        test_billing()
        test_rag()
        test_admin()
        test_scraper()
        test_fraud()
        test_personalization()
        test_rate_limiting()
        test_error_handling()

        # Generate report
        generate_report()

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.RESET}")
        generate_report()
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        generate_report()
        sys.exit(1)


if __name__ == "__main__":
    main()
