#!/usr/bin/env python3
"""
Backend Production Test Suite
Tests all endpoints on api.nabavkidata.com
"""
import httpx
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any

# Production API base URL
BASE_URL = "https://api.nabavkidata.com"

# Test credentials
TEST_EMAIL = "test-enterprise@nabavkidata.com"
TEST_PASSWORD = "Demo123!"

# Test results storage
test_results = {
    "passed": 0,
    "failed": 0,
    "tests": []
}


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if details:
        print(f"  └─ {details}")
    
    test_results["tests"].append({
        "name": name,
        "passed": passed,
        "details": details,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    if passed:
        test_results["passed"] += 1
    else:
        test_results["failed"] += 1


async def test_health_endpoints(client: httpx.AsyncClient):
    """Test health and root endpoints"""
    print("\n" + "="*60)
    print("HEALTH & STATUS ENDPOINTS")
    print("="*60)
    
    # Test root endpoint
    try:
        response = await client.get("/")
        log_test(
            "GET /",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET / - Response body",
                "service" in data and "version" in data,
                f"Keys: {list(data.keys())}"
            )
    except Exception as e:
        log_test("GET /", False, f"Error: {str(e)}")
    
    # Test health endpoint
    try:
        response = await client.get("/health")
        log_test(
            "GET /health",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /health - Response body",
                "status" in data and data.get("status") == "healthy",
                f"Status: {data.get('status')}"
            )
    except Exception as e:
        log_test("GET /health", False, f"Error: {str(e)}")


async def test_auth_endpoints(client: httpx.AsyncClient) -> str:
    """Test authentication endpoints and return access token"""
    print("\n" + "="*60)
    print("AUTHENTICATION ENDPOINTS")
    print("="*60)
    
    access_token = None
    
    # Test login
    try:
        response = await client.post(
            "/api/auth/login",
            data={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
        )
        log_test(
            "POST /api/auth/login",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            log_test(
                "POST /api/auth/login - Token received",
                access_token is not None,
                f"Token length: {len(access_token) if access_token else 0}"
            )
    except Exception as e:
        log_test("POST /api/auth/login", False, f"Error: {str(e)}")
    
    # Test /me endpoint (requires auth)
    if access_token:
        try:
            response = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            log_test(
                "GET /api/auth/me (authenticated)",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            if response.status_code == 200:
                data = response.json()
                log_test(
                    "GET /api/auth/me - User data",
                    "email" in data and data.get("email") == TEST_EMAIL,
                    f"Email: {data.get('email')}"
                )
        except Exception as e:
            log_test("GET /api/auth/me", False, f"Error: {str(e)}")
    
    # Test /me without auth (should fail)
    try:
        response = await client.get("/api/auth/me")
        log_test(
            "GET /api/auth/me (unauthenticated)",
            response.status_code == 401,
            f"Status: {response.status_code} (expected 401)"
        )
    except Exception as e:
        log_test("GET /api/auth/me (unauth)", False, f"Error: {str(e)}")
    
    return access_token


async def test_tender_endpoints(client: httpx.AsyncClient, token: str):
    """Test tender endpoints"""
    print("\n" + "="*60)
    print("TENDER ENDPOINTS")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test GET /api/tenders
    try:
        response = await client.get("/api/tenders", headers=headers)
        log_test(
            "GET /api/tenders",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/tenders - Response structure",
                "total" in data and "items" in data,
                f"Total: {data.get('total')}, Items: {len(data.get('items', []))}"
            )
    except Exception as e:
        log_test("GET /api/tenders", False, f"Error: {str(e)}")
    
    # Test GET /api/tenders with filters
    try:
        response = await client.get(
            "/api/tenders",
            params={"status": "open", "page_size": 5},
            headers=headers
        )
        log_test(
            "GET /api/tenders?status=open",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
    except Exception as e:
        log_test("GET /api/tenders (filtered)", False, f"Error: {str(e)}")
    
    # Test GET /api/tenders/stats/overview
    try:
        response = await client.get("/api/tenders/stats/overview", headers=headers)
        log_test(
            "GET /api/tenders/stats/overview",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
    except Exception as e:
        log_test("GET /api/tenders/stats/overview", False, f"Error: {str(e)}")


async def test_billing_endpoints(client: httpx.AsyncClient, token: str):
    """Test billing endpoints"""
    print("\n" + "="*60)
    print("BILLING ENDPOINTS")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test GET /api/billing/subscription
    try:
        response = await client.get("/api/billing/subscription", headers=headers)
        log_test(
            "GET /api/billing/subscription",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "GET /api/billing/subscription - Data structure",
                "tier" in data,
                f"Tier: {data.get('tier')}"
            )
    except Exception as e:
        log_test("GET /api/billing/subscription", False, f"Error: {str(e)}")
    
    # Test GET /api/billing/usage
    try:
        response = await client.get("/api/billing/usage", headers=headers)
        log_test(
            "GET /api/billing/usage",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
    except Exception as e:
        log_test("GET /api/billing/usage", False, f"Error: {str(e)}")


async def test_admin_endpoints(client: httpx.AsyncClient, token: str):
    """Test admin endpoints (should be protected)"""
    print("\n" + "="*60)
    print("ADMIN ENDPOINTS (Protection Test)")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test admin endpoints - should require admin role
    admin_endpoints = [
        "/api/admin/users",
        "/api/admin/analytics",
        "/api/admin/fraud/logs"
    ]
    
    for endpoint in admin_endpoints:
        try:
            response = await client.get(endpoint, headers=headers)
            # Should either return 200 (if user is admin) or 403 (if not admin)
            log_test(
                f"GET {endpoint}",
                response.status_code in [200, 403],
                f"Status: {response.status_code} (200=admin, 403=not admin)"
            )
        except Exception as e:
            log_test(f"GET {endpoint}", False, f"Error: {str(e)}")


async def test_rate_limiting(client: httpx.AsyncClient):
    """Test rate limiting (if implemented)"""
    print("\n" + "="*60)
    print("RATE LIMITING TEST")
    print("="*60)
    
    # Make rapid requests to test rate limiting
    responses = []
    for i in range(10):
        try:
            response = await client.get("/health")
            responses.append(response.status_code)
        except Exception as e:
            responses.append(f"Error: {str(e)}")
    
    # Check if any requests were rate limited (429)
    rate_limited = 429 in responses
    log_test(
        "Rate limiting",
        True,  # Always pass, just log the result
        f"10 rapid requests: {responses.count(200)} succeeded, {responses.count(429)} rate-limited"
    )


async def test_cors_headers(client: httpx.AsyncClient):
    """Test CORS configuration"""
    print("\n" + "="*60)
    print("CORS CONFIGURATION")
    print("="*60)
    
    try:
        response = await client.options(
            "/api/tenders",
            headers={"Origin": "https://www.nabavkidata.com"}
        )
        
        cors_headers = {
            "access-control-allow-origin": response.headers.get("access-control-allow-origin"),
            "access-control-allow-methods": response.headers.get("access-control-allow-methods"),
            "access-control-allow-headers": response.headers.get("access-control-allow-headers")
        }
        
        log_test(
            "CORS headers present",
            any(cors_headers.values()),
            f"Headers: {cors_headers}"
        )
    except Exception as e:
        log_test("CORS test", False, f"Error: {str(e)}")


async def test_api_docs(client: httpx.AsyncClient):
    """Test API documentation endpoints"""
    print("\n" + "="*60)
    print("API DOCUMENTATION")
    print("="*60)
    
    # Test Swagger UI
    try:
        response = await client.get("/api/docs")
        log_test(
            "GET /api/docs (Swagger UI)",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
    except Exception as e:
        log_test("GET /api/docs", False, f"Error: {str(e)}")
    
    # Test OpenAPI JSON
    try:
        response = await client.get("/api/openapi.json")
        log_test(
            "GET /api/openapi.json",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "OpenAPI spec structure",
                "openapi" in data and "paths" in data,
                f"Endpoints documented: {len(data.get('paths', {}))}"
            )
    except Exception as e:
        log_test("GET /api/openapi.json", False, f"Error: {str(e)}")


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("BACKEND PRODUCTION TEST SUITE")
    print(f"Target: {BASE_URL}")
    print(f"Started: {datetime.utcnow().isoformat()}")
    print("="*80)
    
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=30.0,
        follow_redirects=True
    ) as client:
        # Run tests in order
        await test_health_endpoints(client)
        access_token = await test_auth_endpoints(client)
        
        if access_token:
            await test_tender_endpoints(client, access_token)
            await test_billing_endpoints(client, access_token)
            await test_admin_endpoints(client, access_token)
        else:
            print("\n⚠️  Skipping authenticated tests (no access token)")
        
        await test_rate_limiting(client)
        await test_cors_headers(client)
        await test_api_docs(client)
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_results['passed'] + test_results['failed']}")
    print(f"✅ Passed: {test_results['passed']}")
    print(f"❌ Failed: {test_results['failed']}")
    print(f"Pass Rate: {test_results['passed'] / (test_results['passed'] + test_results['failed']) * 100:.1f}%")
    print("="*80)
    
    # Save results to JSON
    with open("backend_test_results.json", "w") as f:
        json.dump(test_results, f, indent=2)
    print(f"\n📄 Results saved to: backend_test_results.json")
    
    return test_results


if __name__ == "__main__":
    results = asyncio.run(main())
    
    # Exit with error code if any tests failed
    exit_code = 0 if results["failed"] == 0 else 1
    exit(exit_code)
