"""
Search Tenders Scenario

This scenario simulates users searching for tenders using various
search queries, filters, and advanced search features.
"""

import random
from locust import task, TaskSet


class SearchTendersScenario(TaskSet):
    """
    Realistic search behavior for tender platform.
    Users typically:
    1. Enter search terms
    2. Refine with filters
    3. Try different search variations
    4. Use advanced search options
    """

    SEARCH_TERMS = [
        # Slovenian search terms
        "računalniki", "medicinska oprema", "storitve čiščenja",
        "pisarniški material", "avtomobili", "gradbena dela",
        "IT storitve", "svetovanje", "vzdrževanje", "energija",
        "programska oprema", "varovanje", "transport",
        "pohištvo", "električna energija", "plin",
        "telekomunikacije", "arhiviranje", "tiskanje",
        "laboratorijska oprema", "cestna infrastruktura"
    ]

    CATEGORIES = [
        "IT", "zdravstvo", "gradbeništvo", "storitve",
        "oprema", "svetovanje", "transport", "energija"
    ]

    PROCEDURE_TYPES = [
        "javno_narocilo", "narocilo_male_vrednosti",
        "konkurencni_dialog", "pogajanja"
    ]

    def on_start(self):
        """Initialize search scenario"""
        self.search_history = []
        self.last_search_term = None

    @task(25)
    def simple_search(self):
        """Perform simple keyword search"""
        search_term = random.choice(self.SEARCH_TERMS)
        self.last_search_term = search_term

        params = {
            "q": search_term,
            "page": 1,
            "limit": 20
        }

        with self.client.get(
            "/api/v1/tenders/search",
            params=params,
            name="/api/v1/tenders/search (simple)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    results = data.get("results", data.get("items", []))
                    self.search_history.append({
                        "term": search_term,
                        "count": len(results)
                    })
                    response.success()
                except Exception as e:
                    response.failure(f"Parse error: {str(e)}")
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(15)
    def search_with_filters(self):
        """Search with additional filters"""
        search_term = random.choice(self.SEARCH_TERMS)

        params = {
            "q": search_term,
            "page": 1,
            "limit": 20
        }

        # Add random filters
        if random.random() > 0.5:
            params["min_value"] = random.choice([1000, 5000, 10000, 50000])

        if random.random() > 0.5:
            params["status"] = random.choice(["active", "completed"])

        if random.random() > 0.7:
            params["category"] = random.choice(self.CATEGORIES)

        with self.client.get(
            "/api/v1/tenders/search",
            params=params,
            name="/api/v1/tenders/search (with filters)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(12)
    def advanced_search(self):
        """Perform advanced search with multiple criteria"""
        search_term = random.choice(self.SEARCH_TERMS)

        params = {
            "q": search_term,
            "min_value": random.choice([1000, 10000, 50000]),
            "max_value": random.choice([100000, 500000, 1000000]),
            "date_from": random.choice([
                "2023-01-01", "2023-06-01", "2024-01-01", "2024-06-01"
            ]),
            "date_to": "2024-12-31",
            "status": random.choice(["active", "completed", "all"]),
            "procedure_type": random.choice(self.PROCEDURE_TYPES),
            "sort": random.choice(["relevance", "date_desc", "value_desc"]),
            "page": 1,
            "limit": 20
        }

        with self.client.get(
            "/api/v1/tenders/search",
            params=params,
            name="/api/v1/tenders/search (advanced)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(8)
    def search_by_organization(self):
        """Search tenders by organization name"""
        org_terms = [
            "Ministrstvo", "Občina", "Bolnišnica", "Univerza",
            "Zdravstveni dom", "Zavod", "Center"
        ]

        org_term = random.choice(org_terms)

        params = {
            "organization": org_term,
            "page": 1,
            "limit": 20
        }

        with self.client.get(
            "/api/v1/tenders/search",
            params=params,
            name="/api/v1/tenders/search (by org)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(10)
    def paginate_search_results(self):
        """Navigate through search result pages"""
        if not self.last_search_term:
            self.last_search_term = random.choice(self.SEARCH_TERMS)

        page = random.randint(1, 5)

        params = {
            "q": self.last_search_term,
            "page": page,
            "limit": 20
        }

        with self.client.get(
            "/api/v1/tenders/search",
            params=params,
            name="/api/v1/tenders/search (pagination)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def empty_search(self):
        """Test search with no query (should return all)"""
        params = {
            "page": 1,
            "limit": 20,
            "sort": "date_desc"
        }

        with self.client.get(
            "/api/v1/tenders/search",
            params=params,
            name="/api/v1/tenders/search (empty)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(7)
    def autocomplete_search(self):
        """Test autocomplete/suggestion endpoint"""
        partial_term = random.choice(self.SEARCH_TERMS)[:3]

        params = {
            "q": partial_term,
            "limit": 10
        }

        with self.client.get(
            "/api/v1/tenders/autocomplete",
            params=params,
            name="/api/v1/tenders/autocomplete",
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:  # 404 acceptable if not implemented
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(3)
    def search_suggestions(self):
        """Get search suggestions based on popular terms"""
        with self.client.get(
            "/api/v1/search/suggestions",
            name="/api/v1/search/suggestions",
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
