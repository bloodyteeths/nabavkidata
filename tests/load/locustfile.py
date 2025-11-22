"""
Locust Load Testing Suite for Nabavki Data Platform

This file contains comprehensive load testing scenarios for the procurement data platform.
It simulates realistic user behaviors including browsing, searching, authentication, and RAG chat interactions.

Usage:
    # Smoke test
    locust -f locustfile.py --users 10 --spawn-rate 2 --run-time 2m --tags smoke

    # Load test
    locust -f locustfile.py --users 100 --spawn-rate 10 --run-time 10m --tags load

    # Stress test
    locust -f locustfile.py --users 500 --spawn-rate 50 --run-time 15m --tags stress

    # Spike test
    locust -f locustfile.py --users 1000 --spawn-rate 100 --run-time 5m --tags spike
"""

import random
import time
from locust import HttpUser, TaskSet, task, tag, between, events
from locust.contrib.fasthttp import FastHttpUser
import json


# Configuration
API_BASE_URL = "/api/v1"
FRONTEND_BASE_URL = ""

# Sample data for realistic testing
SEARCH_TERMS = [
    "računalniki",
    "medicinska oprema",
    "storitve čiščenja",
    "pisarniški material",
    "avtomobili",
    "gradbena dela",
    "IT storitve",
    "svetovanje",
    "vzdrževanje",
    "energija"
]

TENDER_IDS = list(range(1, 1001))  # Assume 1000 tenders in database

RAG_QUERIES = [
    "Katere so največje javne naročilnice v zadnjem letu?",
    "Pokaži trende v IT naročilih",
    "Kdo so najpogostejši dobavitelji?",
    "Kakšna je povprečna vrednost naročil za medicino?",
    "Prikaži statistiko po regijah",
    "Kateri postopki so najpogostejši?",
    "Kako se je trg spremenil zadnjih 6 mesecev?",
    "Prikaži anomalije v cenah",
    "Katere institucije izdajo največ naročil?",
    "Analiziraj konkurenco v gradbeništvu"
]

ADMIN_OPERATIONS = [
    "sync_tenders",
    "refresh_cache",
    "update_statistics",
    "clean_old_data",
    "reindex_search"
]


class BrowseTasks(TaskSet):
    """Task set for casual browsing users"""

    @tag('smoke', 'load', 'stress', 'spike')
    @task(10)
    def browse_homepage(self):
        """Load the homepage"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Homepage returned {response.status_code}")

    @tag('smoke', 'load', 'stress', 'spike')
    @task(15)
    def browse_tenders_list(self):
        """Browse paginated tender listings"""
        page = random.randint(1, 50)
        limit = random.choice([10, 20, 50])

        with self.client.get(
            f"{API_BASE_URL}/tenders",
            params={"page": page, "limit": limit},
            name=f"{API_BASE_URL}/tenders?page=[page]&limit=[limit]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "items" in data and isinstance(data["items"], list):
                        response.success()
                    else:
                        response.failure("Invalid response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Tenders list returned {response.status_code}")

    @tag('smoke', 'load', 'stress', 'spike')
    @task(20)
    def view_tender_details(self):
        """View details of a specific tender"""
        tender_id = random.choice(TENDER_IDS)

        with self.client.get(
            f"{API_BASE_URL}/tenders/{tender_id}",
            name=f"{API_BASE_URL}/tenders/[id]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "id" in data and "title" in data:
                        response.success()
                    else:
                        response.failure("Missing required fields")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 404:
                response.success()  # 404 is acceptable for random IDs
            else:
                response.failure(f"Tender details returned {response.status_code}")

    @tag('load', 'stress')
    @task(5)
    def view_statistics(self):
        """View platform statistics"""
        with self.client.get(
            f"{API_BASE_URL}/statistics",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Statistics returned {response.status_code}")


class SearchTasks(TaskSet):
    """Task set for users performing searches"""

    @tag('smoke', 'load', 'stress', 'spike')
    @task(20)
    def search_tenders(self):
        """Search for tenders using various filters"""
        search_term = random.choice(SEARCH_TERMS)
        params = {
            "q": search_term,
            "page": random.randint(1, 10),
            "limit": 20
        }

        # Add random filters
        if random.random() > 0.5:
            params["min_value"] = random.choice([1000, 5000, 10000, 50000])

        if random.random() > 0.5:
            params["status"] = random.choice(["active", "completed", "cancelled"])

        with self.client.get(
            f"{API_BASE_URL}/tenders/search",
            params=params,
            name=f"{API_BASE_URL}/tenders/search?q=[term]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "results" in data or "items" in data:
                        response.success()
                    else:
                        response.failure("Invalid search response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Search returned {response.status_code}")

    @tag('load', 'stress')
    @task(10)
    def filter_by_organization(self):
        """Filter tenders by organization"""
        with self.client.get(
            f"{API_BASE_URL}/organizations",
            params={"limit": 50},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Organizations returned {response.status_code}")

    @tag('load', 'stress')
    @task(8)
    def advanced_search(self):
        """Perform advanced search with multiple filters"""
        params = {
            "q": random.choice(SEARCH_TERMS),
            "min_value": random.choice([1000, 10000, 50000]),
            "max_value": random.choice([100000, 500000, 1000000]),
            "date_from": "2023-01-01",
            "date_to": "2024-12-31",
            "sort": random.choice(["date_desc", "value_desc", "relevance"]),
            "limit": 20
        }

        with self.client.get(
            f"{API_BASE_URL}/tenders/search",
            params=params,
            name=f"{API_BASE_URL}/tenders/search (advanced)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Advanced search returned {response.status_code}")


class AuthenticatedTasks(TaskSet):
    """Task set for authenticated users"""

    def on_start(self):
        """Login when user starts"""
        self.login()

    def login(self):
        """Perform login"""
        response = self.client.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "email": f"test_user_{random.randint(1, 100)}@example.com",
                "password": "test_password_123"
            },
            name=f"{API_BASE_URL}/auth/login"
        )

        if response.status_code == 200:
            try:
                data = response.json()
                self.token = data.get("access_token")
            except (json.JSONDecodeError, KeyError):
                self.token = None
        else:
            self.token = None

    def get_auth_headers(self):
        """Get authentication headers"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @tag('load', 'stress')
    @task(15)
    def query_rag_chat(self):
        """Query the RAG chat system"""
        query = random.choice(RAG_QUERIES)

        with self.client.post(
            f"{API_BASE_URL}/rag/query",
            json={"query": query},
            headers=self.get_auth_headers(),
            name=f"{API_BASE_URL}/rag/query",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "answer" in data or "response" in data:
                        response.success()
                    else:
                        response.failure("Invalid RAG response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Unauthorized - token may have expired")
                self.login()  # Re-login
            else:
                response.failure(f"RAG query returned {response.status_code}")

    @tag('load', 'stress')
    @task(10)
    def save_favorite_tender(self):
        """Save a tender to favorites"""
        tender_id = random.choice(TENDER_IDS)

        with self.client.post(
            f"{API_BASE_URL}/users/favorites",
            json={"tender_id": tender_id},
            headers=self.get_auth_headers(),
            name=f"{API_BASE_URL}/users/favorites",
            catch_response=True
        ) as response:
            if response.status_code in [200, 201, 401]:
                response.success()
            else:
                response.failure(f"Save favorite returned {response.status_code}")

    @tag('load', 'stress')
    @task(8)
    def get_user_profile(self):
        """Get user profile"""
        with self.client.get(
            f"{API_BASE_URL}/users/me",
            headers=self.get_auth_headers(),
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self.login()
                response.success()
            else:
                response.failure(f"User profile returned {response.status_code}")


class AdminTasks(TaskSet):
    """Task set for admin operations"""

    def on_start(self):
        """Login as admin when user starts"""
        self.admin_login()

    def admin_login(self):
        """Perform admin login"""
        response = self.client.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "email": "admin@example.com",
                "password": "admin_password_123"
            },
            name=f"{API_BASE_URL}/auth/login (admin)"
        )

        if response.status_code == 200:
            try:
                data = response.json()
                self.token = data.get("access_token")
            except (json.JSONDecodeError, KeyError):
                self.token = None
        else:
            self.token = None

    def get_auth_headers(self):
        """Get admin authentication headers"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @tag('stress')
    @task(5)
    def trigger_admin_operation(self):
        """Trigger various admin operations"""
        operation = random.choice(ADMIN_OPERATIONS)

        with self.client.post(
            f"{API_BASE_URL}/admin/operations/{operation}",
            headers=self.get_auth_headers(),
            name=f"{API_BASE_URL}/admin/operations/[operation]",
            catch_response=True
        ) as response:
            if response.status_code in [200, 202, 401, 403]:
                response.success()
            else:
                response.failure(f"Admin operation returned {response.status_code}")


# User classes with different behaviors
class BrowseUser(HttpUser):
    """Casual browsing user - most common user type"""
    tasks = [BrowseTasks]
    wait_time = between(2, 8)  # 2-8 seconds between requests
    weight = 50  # 50% of users


class SearchUser(HttpUser):
    """User focused on searching - medium frequency"""
    tasks = [SearchTasks]
    wait_time = between(3, 10)  # 3-10 seconds between searches
    weight = 30  # 30% of users


class AuthenticatedUser(HttpUser):
    """Authenticated user using advanced features"""
    tasks = [AuthenticatedTasks]
    wait_time = between(5, 15)  # 5-15 seconds between requests
    weight = 15  # 15% of users


class AdminUser(HttpUser):
    """Admin user performing administrative tasks"""
    tasks = [AdminTasks]
    wait_time = between(10, 30)  # 10-30 seconds between operations
    weight = 5  # 5% of users


# Event hooks for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("=" * 60)
    print("Load Test Starting")
    print(f"Host: {environment.host}")
    print(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("=" * 60)
    print("Load Test Completed")
    print("=" * 60)
