"""Integration tests for complete data flow"""
import pytest
import asyncpg
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_scraper_to_api_flow():
    """Test: Scraper → DB → API → Response"""
    # Verify scraped data in DB
    conn = await asyncpg.connect("postgresql://dev:devpass@localhost:5432/nabavkidata")

    tenders = await conn.fetch("SELECT * FROM tenders LIMIT 1")
    assert len(tenders) > 0, "No tenders in database"

    tender_id = tenders[0]['tender_id']
    await conn.close()

    # Test API returns scraped data
    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get(f"/api/v1/tenders/{tender_id}")
        assert response.status_code == 200
        data = response.json()
        assert data['tender_id'] == tender_id

@pytest.mark.asyncio
async def test_auth_to_ai_flow():
    """Test: Auth → AI Query → Response with sources"""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # Register
        reg = await client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "Test123!",
            "full_name": "Test User"
        })
        assert reg.status_code == 200
        token = reg.json()['access_token']

        # AI Query
        ai_resp = await client.post(
            "/api/v1/ai/ask",
            json={"question": "What are IT tenders?"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert ai_resp.status_code == 200
        assert 'answer' in ai_resp.json()
        assert 'sources' in ai_resp.json()

@pytest.mark.asyncio
async def test_billing_upgrade_flow():
    """Test: Register → Upgrade → Stripe Checkout"""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # Register
        reg = await client.post("/api/v1/auth/register", json={
            "email": "billing@example.com",
            "password": "Test123!",
            "full_name": "Billing Test"
        })
        token = reg.json()['access_token']

        # Create checkout
        checkout = await client.post(
            "/api/v1/billing/checkout",
            json={"tier": "standard"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert checkout.status_code == 200
        assert 'url' in checkout.json()
        assert 'stripe.com' in checkout.json()['url']
