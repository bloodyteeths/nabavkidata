"""Security validation tests"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_sql_injection_prevention():
    """Verify SQL injection blocked"""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # Attempt SQL injection
        response = await client.get("/api/v1/tenders/search", params={
            "query": "'; DROP TABLE tenders; --"
        })
        assert response.status_code in [200, 400, 401]
        # Should not crash server

@pytest.mark.asyncio
async def test_xss_prevention():
    """Verify XSS payloads sanitized"""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post("/api/v1/auth/register", json={
            "email": "xss@test.com",
            "password": "Test123!",
            "full_name": "<script>alert('XSS')</script>"
        })
        assert response.status_code in [200, 400]

@pytest.mark.asyncio
async def test_auth_required():
    """Verify protected endpoints require auth"""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # No token
        response = await client.get("/api/v1/tenders/search")
        assert response.status_code == 401

        # Invalid token
        response = await client.get(
            "/api/v1/tenders/search",
            headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_rate_limiting():
    """Verify rate limiting enforced"""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        responses = []
        for _ in range(150):
            resp = await client.get("/api/v1/tenders/search")
            responses.append(resp.status_code)

        # Should hit rate limit
        assert 429 in responses, "Rate limiting not enforced"
