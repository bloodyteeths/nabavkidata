"""
Test script for pricing API endpoint
Tests the actual FastAPI endpoint with authentication
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

# Set required env vars if not present
if not os.getenv('SECRET_KEY'):
    os.environ['SECRET_KEY'] = 'test-secret-key-for-validation-only'

from fastapi.testclient import TestClient
from sqlalchemy import text
from database import get_db, AsyncSessionLocal
import sys
sys.path.insert(0, '.')


async def create_test_user():
    """Create a test user for authentication"""
    from models import User
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async with AsyncSessionLocal() as db:
        # Check if test user exists
        result = await db.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": "test@nabavkidata.com"}
        )
        existing = result.fetchone()

        if existing:
            print(f"✓ Test user already exists: {existing[0]}")
            return str(existing[0])

        # Create test user
        user = User(
            email="test@nabavkidata.com",
            password_hash=pwd_context.hash("testpassword123"),
            full_name="Test User",
            role="user",
            subscription_tier="premium",  # Premium to access all features
            email_verified=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"✓ Created test user: {user.user_id}")
        return str(user.user_id)


async def get_auth_token():
    """Get authentication token for test user"""
    from main import app

    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@nabavkidata.com",
            "password": "testpassword123"
        }
    )

    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✓ Obtained auth token")
        return token
    else:
        print(f"❌ Failed to get auth token: {response.status_code} {response.text}")
        return None


async def test_pricing_endpoint():
    """Test the pricing API endpoint"""
    print("\n" + "="*80)
    print("TESTING PRICING API ENDPOINT")
    print("="*80)

    # Create test user
    await create_test_user()

    # Get auth token
    token = await get_auth_token()
    if not token:
        print("❌ Cannot test without auth token")
        return

    from main import app
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Get sample CPV codes
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT cpv_code, COUNT(*) as count
            FROM tenders
            WHERE cpv_code IS NOT NULL
              AND cpv_code != ''
              AND publication_date IS NOT NULL
            GROUP BY cpv_code
            HAVING COUNT(*) >= 5
            ORDER BY COUNT(*) DESC
            LIMIT 3
        """))
        cpv_codes = result.fetchall()

    if not cpv_codes:
        print("❌ No CPV codes found for testing")
        return

    print(f"\n✓ Found {len(cpv_codes)} CPV codes for testing")

    # Test 1: Monthly grouping
    print("\n[1] Testing monthly price history endpoint...")
    test_cpv = cpv_codes[0][0]
    print(f"    CPV Code: {test_cpv}")

    response = client.get(
        f"/api/ai/price-history/{test_cpv}",
        params={"months": 24, "group_by": "month"},
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Monthly endpoint returned successfully")
        print(f"  - CPV Code: {data['cpv_code']}")
        print(f"  - Description: {data.get('cpv_description', 'N/A')}")
        print(f"  - Time Range: {data['time_range']}")
        print(f"  - Total Tenders: {data['total_tenders']}")
        print(f"  - Data Points: {len(data['data_points'])}")
        print(f"  - Trend: {data['trend']} ({data['trend_pct']:+.2f}%)")

        if data['data_points']:
            print("\n  Sample data points (first 3):")
            for point in data['data_points'][:3]:
                print(f"    - {point['period']}: {point['tender_count']} tenders, "
                      f"Avg Estimated: {point['avg_estimated'] or 'N/A'}, "
                      f"Avg Actual: {point['avg_actual'] or 'N/A'}, "
                      f"Discount: {point['avg_discount_pct'] or 'N/A'}%")
    else:
        print(f"❌ Monthly endpoint failed: {response.status_code}")
        print(f"   Response: {response.text}")

    # Test 2: Quarterly grouping
    print("\n[2] Testing quarterly price history endpoint...")

    response = client.get(
        f"/api/ai/price-history/{test_cpv}",
        params={"months": 36, "group_by": "quarter"},
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Quarterly endpoint returned successfully")
        print(f"  - Data Points: {len(data['data_points'])}")

        if data['data_points']:
            print("\n  Quarterly data points:")
            for point in data['data_points']:
                print(f"    - {point['period']}: {point['tender_count']} tenders")
    else:
        print(f"❌ Quarterly endpoint failed: {response.status_code}")
        print(f"   Response: {response.text}")

    # Test 3: Different CPV codes
    print("\n[3] Testing with different CPV codes...")
    for cpv_code, count in cpv_codes[1:]:
        response = client.get(
            f"/api/ai/price-history/{cpv_code}",
            params={"months": 12},
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ {cpv_code}: {data['total_tenders']} tenders, {len(data['data_points'])} periods, trend: {data['trend']}")
        else:
            print(f"❌ {cpv_code}: Failed with {response.status_code}")

    # Test 4: Edge cases
    print("\n[4] Testing edge cases...")

    # Invalid CPV code
    response = client.get(
        "/api/ai/price-history/INVALID",
        headers=headers
    )
    if response.status_code == 400:
        print("✓ Invalid CPV code rejected correctly")
    else:
        print(f"⚠ Invalid CPV code should return 400, got {response.status_code}")

    # Non-existent CPV code
    response = client.get(
        "/api/ai/price-history/99999999",
        headers=headers
    )
    if response.status_code == 200:
        data = response.json()
        if data['total_tenders'] == 0:
            print("✓ Non-existent CPV code returns empty data")
        else:
            print(f"⚠ Non-existent CPV code returned data: {data['total_tenders']} tenders")
    else:
        print(f"⚠ Non-existent CPV code should return 200, got {response.status_code}")

    # Test 5: Health check
    print("\n[5] Testing pricing health endpoint...")
    response = client.get("/api/ai/pricing-health")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Health endpoint: {data['status']}")
        print(f"  - Service: {data['service']}")
    else:
        print(f"❌ Health endpoint failed: {response.status_code}")

    print("\n" + "="*80)
    print("✓ ALL API TESTS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_pricing_endpoint())
