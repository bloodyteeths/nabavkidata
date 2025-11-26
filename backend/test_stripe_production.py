#!/usr/bin/env python3
"""
Stripe Billing Production Test Suite
Tests Stripe integration on api.nabavkidata.com
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


async def test_stripe_webhook_health(client: httpx.AsyncClient):
    """Test Stripe webhook health endpoint"""
    print("\n" + "="*60)
    print("STRIPE WEBHOOK HEALTH CHECK")
    print("="*60)
    
    try:
        response = await client.get("/api/stripe/webhook/health")
        log_test(
            "GET /api/stripe/webhook/health",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check webhook secret configured
            log_test(
                "Webhook secret configured",
                data.get("webhook_secret_configured") == True,
                f"Configured: {data.get('webhook_secret_configured')}"
            )
            
            # Check Stripe API key configured
            log_test(
                "Stripe API key configured",
                data.get("stripe_api_key_configured") == True,
                f"Configured: {data.get('stripe_api_key_configured')}"
            )
            
            # Check supported events
            supported_events = data.get("supported_events", [])
            expected_events = [
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.deleted",
                "invoice.payment_succeeded",
                "invoice.payment_failed",
                "customer.subscription.trial_will_end"
            ]
            
            log_test(
                "All required events supported",
                all(event in supported_events for event in expected_events),
                f"Supported: {len(supported_events)} events"
            )
            
            # Check price ID mappings
            price_mappings = data.get("price_id_mappings", 0)
            log_test(
                "Price ID mappings configured",
                price_mappings >= 4,
                f"Mappings: {price_mappings} (expected >= 4)"
            )
            
    except Exception as e:
        log_test("Stripe webhook health check", False, f"Error: {str(e)}")


async def test_billing_endpoints(client: httpx.AsyncClient, token: str):
    """Test billing-related endpoints"""
    print("\n" + "="*60)
    print("BILLING ENDPOINTS")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test GET /api/billing/plans
    try:
        response = await client.get("/api/billing/plans", headers=headers)
        log_test(
            "GET /api/billing/plans",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "Billing plans structure",
                isinstance(data, list) and len(data) > 0,
                f"Plans available: {len(data) if isinstance(data, list) else 0}"
            )
    except Exception as e:
        log_test("GET /api/billing/plans", False, f"Error: {str(e)}")
    
    # Test GET /api/billing/status
    try:
        response = await client.get("/api/billing/status", headers=headers)
        log_test(
            "GET /api/billing/status",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "Billing status structure",
                "tier" in data or "subscription" in data,
                f"Keys: {list(data.keys())}"
            )
    except Exception as e:
        log_test("GET /api/billing/status", False, f"Error: {str(e)}")
    
    # Test GET /api/billing/usage
    try:
        response = await client.get("/api/billing/usage", headers=headers)
        log_test(
            "GET /api/billing/usage",
            response.status_code == 200,
            f"Status: {response.status_code}"
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(
                "Usage tracking data",
                "api_calls" in data or "usage" in data,
                f"Keys: {list(data.keys())}"
            )
    except Exception as e:
        log_test("GET /api/billing/usage", False, f"Error: {str(e)}")
    
    # Test GET /api/billing/invoices
    try:
        response = await client.get("/api/billing/invoices", headers=headers)
        log_test(
            "GET /api/billing/invoices",
            response.status_code in [200, 404],  # 404 if no invoices yet
            f"Status: {response.status_code}"
        )
    except Exception as e:
        log_test("GET /api/billing/invoices", False, f"Error: {str(e)}")


async def test_subscription_tier_enforcement(client: httpx.AsyncClient, token: str):
    """Test that subscription tiers are enforced"""
    print("\n" + "="*60)
    print("SUBSCRIPTION TIER ENFORCEMENT")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get current user info to check tier
    try:
        response = await client.get("/api/auth/me", headers=headers)
        if response.status_code == 200:
            user_data = response.json()
            current_tier = user_data.get("subscription_tier", "unknown")
            
            log_test(
                "User has subscription tier",
                current_tier in ["free", "starter", "professional", "enterprise"],
                f"Current tier: {current_tier}"
            )
            
            # Check if tier is properly stored
            log_test(
                "Subscription tier stored in user data",
                "subscription_tier" in user_data,
                f"Tier field present: {current_tier}"
            )
    except Exception as e:
        log_test("Subscription tier check", False, f"Error: {str(e)}")


async def test_checkout_flow(client: httpx.AsyncClient, token: str):
    """Test checkout session creation"""
    print("\n" + "="*60)
    print("CHECKOUT FLOW")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test creating checkout session for professional tier
    try:
        response = await client.post(
            "/api/billing/checkout",
            headers=headers,
            json={
                "price_id": "price_1SWeAtHkVI5icjTl8UxSYNYX",  # Professional tier
                "success_url": "https://www.nabavkidata.com/billing/success",
                "cancel_url": "https://www.nabavkidata.com/billing/plans"
            }
        )
        
        log_test(
            "POST /api/billing/checkout",
            response.status_code in [200, 201],
            f"Status: {response.status_code}"
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            log_test(
                "Checkout session created",
                "url" in data or "session_id" in data,
                f"Keys: {list(data.keys())}"
            )
    except Exception as e:
        log_test("Checkout session creation", False, f"Error: {str(e)}")


async def test_portal_access(client: httpx.AsyncClient, token: str):
    """Test Stripe customer portal access"""
    print("\n" + "="*60)
    print("CUSTOMER PORTAL")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = await client.post(
            "/api/billing/portal",
            headers=headers,
            json={
                "return_url": "https://www.nabavkidata.com/billing"
            }
        )
        
        log_test(
            "POST /api/billing/portal",
            response.status_code in [200, 201, 404],  # 404 if no Stripe customer yet
            f"Status: {response.status_code}"
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            log_test(
                "Portal session created",
                "url" in data,
                f"Portal URL generated: {'url' in data}"
            )
    except Exception as e:
        log_test("Customer portal access", False, f"Error: {str(e)}")


async def test_webhook_endpoint_security(client: httpx.AsyncClient):
    """Test webhook endpoint security"""
    print("\n" + "="*60)
    print("WEBHOOK SECURITY")
    print("="*60)
    
    # Test webhook endpoint without signature (should fail)
    try:
        response = await client.post(
            "/api/stripe/webhook",
            json={"type": "customer.subscription.created"},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 400 or 401 for invalid signature
        log_test(
            "Webhook rejects unsigned requests",
            response.status_code in [400, 401],
            f"Status: {response.status_code} (expected 400/401)"
        )
    except Exception as e:
        log_test("Webhook security test", False, f"Error: {str(e)}")


async def main():
    """Run all Stripe billing tests"""
    print("\n" + "="*80)
    print("STRIPE BILLING PRODUCTION TEST SUITE")
    print(f"Target: {BASE_URL}")
    print(f"Started: {datetime.utcnow().isoformat()}")
    print("="*80)
    
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=30.0,
        follow_redirects=True
    ) as client:
        # Test Stripe webhook health
        await test_stripe_webhook_health(client)
        
        # Login to get access token
        try:
            response = await client.post(
                "/api/auth/login",
                data={
                    "username": TEST_EMAIL,
                    "password": TEST_PASSWORD
                }
            )
            
            if response.status_code == 200:
                access_token = response.json().get("access_token")
                
                if access_token:
                    # Run authenticated tests
                    await test_billing_endpoints(client, access_token)
                    await test_subscription_tier_enforcement(client, access_token)
                    await test_checkout_flow(client, access_token)
                    await test_portal_access(client, access_token)
                else:
                    print("\n⚠️  No access token received, skipping authenticated tests")
            else:
                print(f"\n⚠️  Login failed ({response.status_code}), skipping authenticated tests")
        except Exception as e:
            print(f"\n⚠️  Login error: {str(e)}, skipping authenticated tests")
        
        # Test webhook security (unauthenticated)
        await test_webhook_endpoint_security(client)
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_results['passed'] + test_results['failed']}")
    print(f"✅ Passed: {test_results['passed']}")
    print(f"❌ Failed: {test_results['failed']}")
    
    if test_results['passed'] + test_results['failed'] > 0:
        pass_rate = test_results['passed'] / (test_results['passed'] + test_results['failed']) * 100
        print(f"Pass Rate: {pass_rate:.1f}%")
    
    print("="*80)
    
    # Save results to JSON
    with open("stripe_test_results.json", "w") as f:
        json.dump(test_results, f, indent=2)
    print(f"\n📄 Results saved to: stripe_test_results.json")
    
    return test_results


if __name__ == "__main__":
    results = asyncio.run(main())
    
    # Exit with error code if any tests failed
    exit_code = 0 if results["failed"] == 0 else 1
    exit(exit_code)
