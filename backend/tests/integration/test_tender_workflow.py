"""
Integration tests for tender workflow.
Tests tender search, filtering, details, RAG queries, and personalization.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from decimal import Decimal

from main import app
from models import Tender, TenderStatus
from models_auth import UserAuth
from models_user_personalization import UserPreference, SavedSearch, TenderAlert


class TestTenderWorkflow:
    """Test complete tender workflow from search to personalization"""

    def test_tender_search_and_filter(self, client: TestClient, db: Session, test_user: UserAuth, test_tenders):
        """Test tender search with various filters"""

        # Login first
        login_data = {
            "email": test_user.email,
            "password": "TestPass123!"
        }
        login_response = client.post("/api/auth/login", json=login_data)
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Test basic search
        response = client.get("/api/tenders/search?q=infrastructure", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0

        # Test search with status filter
        response = client.get(
            "/api/tenders/search?status=active",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        for tender in data["results"]:
            assert tender["status"] == "active"

        # Test search with date range filter
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        end_date = datetime.utcnow().isoformat()
        response = client.get(
            f"/api/tenders/search?start_date={start_date}&end_date={end_date}",
            headers=headers
        )
        assert response.status_code == 200

        # Test search with budget filter
        response = client.get(
            "/api/tenders/search?min_budget=100000&max_budget=1000000",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        for tender in data["results"]:
            budget = float(tender.get("budget_mkd", 0))
            assert 100000 <= budget <= 1000000

        # Test pagination
        response = client.get(
            "/api/tenders/search?page=1&page_size=10",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1
        assert len(data["results"]) <= 10

        # Test sorting
        response = client.get(
            "/api/tenders/search?sort_by=published_date&sort_order=desc",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        # Verify results are sorted by date descending
        dates = [result["published_date"] for result in data["results"]]
        assert dates == sorted(dates, reverse=True)

    def test_tender_details(self, client: TestClient, db: Session, test_user: UserAuth, test_tenders):
        """Test retrieving tender details"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get a tender ID
        tender = test_tenders[0]

        # Test get tender details
        response = client.get(f"/api/tenders/{tender.tender_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["tender_id"] == str(tender.tender_id)
        assert data["title"] == tender.title
        assert "description" in data
        assert "status" in data
        assert "published_date" in data

        # Test get non-existent tender
        import uuid
        fake_id = uuid.uuid4()
        response = client.get(f"/api/tenders/{fake_id}", headers=headers)
        assert response.status_code == 404

    def test_rag_queries_on_tenders(self, client: TestClient, db: Session, test_user: UserAuth, mock_openai):
        """Test RAG (Retrieval Augmented Generation) queries on tenders"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Test simple RAG query
        query_data = {
            "question": "What are the requirements for infrastructure tenders?",
            "context_limit": 5
        }
        response = client.post("/api/rag/query", json=query_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)

        # Test RAG query with tender context
        tender_query_data = {
            "question": "Summarize this tender",
            "tender_ids": [str(tid) for tid in [t.tender_id for t in db.query(Tender).limit(2).all()]]
        }
        response = client.post("/api/rag/query", json=tender_query_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data

        # Test semantic search
        semantic_query = {
            "query": "construction projects with large budgets",
            "limit": 10
        }
        response = client.post("/api/rag/semantic-search", json=semantic_query, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) <= 10

    def test_tender_personalization(self, client: TestClient, db: Session, test_user: UserAuth, test_tenders):
        """Test tender personalization features"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Set user preferences
        preferences_data = {
            "categories": ["infrastructure", "technology"],
            "min_budget": 50000,
            "max_budget": 5000000,
            "regions": ["Skopje", "Bitola"]
        }
        pref_response = client.put(
            "/api/personalization/preferences",
            json=preferences_data,
            headers=headers
        )
        assert pref_response.status_code == 200

        # Get personalized recommendations
        rec_response = client.get("/api/personalization/recommendations", headers=headers)
        assert rec_response.status_code == 200
        rec_data = rec_response.json()
        assert "recommendations" in rec_data
        assert len(rec_data["recommendations"]) > 0

        # Verify recommendations match preferences
        for tender in rec_data["recommendations"]:
            budget = float(tender.get("budget_mkd", 0))
            if budget > 0:
                assert preferences_data["min_budget"] <= budget <= preferences_data["max_budget"]

    def test_saved_searches(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test saved search functionality"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create saved search
        saved_search_data = {
            "name": "Infrastructure Projects",
            "query": "infrastructure",
            "filters": {
                "status": "active",
                "min_budget": 100000,
                "categories": ["construction"]
            },
            "notify": True
        }
        create_response = client.post(
            "/api/personalization/saved-searches",
            json=saved_search_data,
            headers=headers
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert "search_id" in created
        search_id = created["search_id"]

        # List saved searches
        list_response = client.get("/api/personalization/saved-searches", headers=headers)
        assert list_response.status_code == 200
        searches = list_response.json()
        assert len(searches) > 0
        assert any(s["search_id"] == search_id for s in searches)

        # Execute saved search
        execute_response = client.get(
            f"/api/personalization/saved-searches/{search_id}/execute",
            headers=headers
        )
        assert execute_response.status_code == 200
        results = execute_response.json()
        assert "results" in results

        # Update saved search
        update_data = {
            "name": "Updated Infrastructure Projects",
            "notify": False
        }
        update_response = client.patch(
            f"/api/personalization/saved-searches/{search_id}",
            json=update_data,
            headers=headers
        )
        assert update_response.status_code == 200

        # Delete saved search
        delete_response = client.delete(
            f"/api/personalization/saved-searches/{search_id}",
            headers=headers
        )
        assert delete_response.status_code == 204

        # Verify deleted
        list_after = client.get("/api/personalization/saved-searches", headers=headers)
        searches_after = list_after.json()
        assert not any(s["search_id"] == search_id for s in searches_after)

    def test_tender_alerts(self, client: TestClient, db: Session, test_user: UserAuth, test_tenders):
        """Test tender alert functionality"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create tender alert
        alert_data = {
            "name": "High Value Tenders",
            "criteria": {
                "min_budget": 500000,
                "categories": ["infrastructure", "technology"],
                "keywords": ["software", "development"]
            },
            "frequency": "daily"
        }
        create_response = client.post(
            "/api/personalization/alerts",
            json=alert_data,
            headers=headers
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert "alert_id" in created
        alert_id = created["alert_id"]

        # List alerts
        list_response = client.get("/api/personalization/alerts", headers=headers)
        assert list_response.status_code == 200
        alerts = list_response.json()
        assert len(alerts) > 0

        # Get matching tenders for alert
        matches_response = client.get(
            f"/api/personalization/alerts/{alert_id}/matches",
            headers=headers
        )
        assert matches_response.status_code == 200
        matches = matches_response.json()
        assert "matches" in matches

        # Disable alert
        disable_response = client.patch(
            f"/api/personalization/alerts/{alert_id}",
            json={"enabled": False},
            headers=headers
        )
        assert disable_response.status_code == 200

        # Delete alert
        delete_response = client.delete(
            f"/api/personalization/alerts/{alert_id}",
            headers=headers
        )
        assert delete_response.status_code == 204

    def test_tender_advanced_filters(self, client: TestClient, db: Session, test_user: UserAuth, test_tenders):
        """Test advanced tender filtering capabilities"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Test multi-category filter
        response = client.get(
            "/api/tenders/search?categories=construction,technology",
            headers=headers
        )
        assert response.status_code == 200

        # Test contractor filter
        response = client.get(
            "/api/tenders/search?contractor=CompanyXYZ",
            headers=headers
        )
        assert response.status_code == 200

        # Test deadline filter
        deadline = (datetime.utcnow() + timedelta(days=30)).isoformat()
        response = client.get(
            f"/api/tenders/search?deadline_before={deadline}",
            headers=headers
        )
        assert response.status_code == 200

        # Test combined filters
        response = client.get(
            "/api/tenders/search?status=active&min_budget=100000&categories=construction&sort_by=budget_mkd&sort_order=desc",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
