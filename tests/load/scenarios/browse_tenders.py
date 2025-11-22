"""
Browse Tenders Scenario

This scenario simulates users browsing through tender listings,
viewing pagination, filtering results, and viewing tender details.
"""

import random
from locust import task, TaskSet


class BrowseTendersScenario(TaskSet):
    """
    Realistic browsing behavior for tender listings.
    Users typically:
    1. Land on homepage
    2. Browse through paginated listings
    3. Apply various filters
    4. View tender details
    5. Navigate between pages
    """

    def on_start(self):
        """Initialize scenario state"""
        self.current_page = 1
        self.items_per_page = 20
        self.viewed_tenders = []

    @task(20)
    def browse_homepage(self):
        """Browse the main tender listing page"""
        params = {
            "page": self.current_page,
            "limit": self.items_per_page
        }

        with self.client.get(
            "/api/v1/tenders",
            params=params,
            name="/api/v1/tenders (browse)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    items = data.get("items", [])
                    total = data.get("total", 0)

                    # Store tender IDs for later viewing
                    for item in items:
                        if "id" in item:
                            self.viewed_tenders.append(item["id"])

                    response.success()
                except Exception as e:
                    response.failure(f"Failed to parse response: {str(e)}")
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(15)
    def view_next_page(self):
        """Navigate to next page"""
        self.current_page += 1

        # Reset to page 1 after browsing too far
        if self.current_page > 20:
            self.current_page = 1

        params = {
            "page": self.current_page,
            "limit": self.items_per_page
        }

        with self.client.get(
            "/api/v1/tenders",
            params=params,
            name="/api/v1/tenders (next page)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(25)
    def view_tender_details(self):
        """View details of a previously browsed tender"""
        if not self.viewed_tenders:
            # Fallback to random tender if none stored
            tender_id = random.randint(1, 1000)
        else:
            tender_id = random.choice(self.viewed_tenders[-50:])  # Recent tenders

        with self.client.get(
            f"/api/v1/tenders/{tender_id}",
            name="/api/v1/tenders/[id] (details)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Verify essential fields
                    required_fields = ["id", "title", "description"]
                    if all(field in data for field in required_fields):
                        response.success()
                    else:
                        response.failure("Missing required fields")
                except Exception as e:
                    response.failure(f"Parse error: {str(e)}")
            elif response.status_code == 404:
                response.success()  # 404 is acceptable
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(10)
    def filter_by_status(self):
        """Apply status filter to tender listings"""
        status = random.choice(["active", "completed", "cancelled", "draft"])

        params = {
            "status": status,
            "page": 1,
            "limit": self.items_per_page
        }

        with self.client.get(
            "/api/v1/tenders",
            params=params,
            name="/api/v1/tenders (filter status)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(8)
    def filter_by_value_range(self):
        """Filter tenders by value range"""
        value_ranges = [
            (1000, 10000),
            (10000, 50000),
            (50000, 100000),
            (100000, 500000),
            (500000, 1000000),
        ]

        min_value, max_value = random.choice(value_ranges)

        params = {
            "min_value": min_value,
            "max_value": max_value,
            "page": 1,
            "limit": self.items_per_page
        }

        with self.client.get(
            "/api/v1/tenders",
            params=params,
            name="/api/v1/tenders (filter value)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def filter_by_date_range(self):
        """Filter tenders by publication date"""
        date_ranges = [
            ("2024-01-01", "2024-03-31"),
            ("2024-04-01", "2024-06-30"),
            ("2024-07-01", "2024-09-30"),
            ("2024-10-01", "2024-12-31"),
        ]

        date_from, date_to = random.choice(date_ranges)

        params = {
            "date_from": date_from,
            "date_to": date_to,
            "page": 1,
            "limit": self.items_per_page
        }

        with self.client.get(
            "/api/v1/tenders",
            params=params,
            name="/api/v1/tenders (filter date)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(7)
    def sort_tenders(self):
        """Sort tender listings by different criteria"""
        sort_options = [
            "date_desc",
            "date_asc",
            "value_desc",
            "value_asc",
            "title_asc",
            "deadline_asc"
        ]

        sort_by = random.choice(sort_options)

        params = {
            "sort": sort_by,
            "page": 1,
            "limit": self.items_per_page
        }

        with self.client.get(
            "/api/v1/tenders",
            params=params,
            name="/api/v1/tenders (sort)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(3)
    def change_page_size(self):
        """Change number of items per page"""
        self.items_per_page = random.choice([10, 20, 50, 100])

        params = {
            "page": 1,
            "limit": self.items_per_page
        }

        with self.client.get(
            "/api/v1/tenders",
            params=params,
            name="/api/v1/tenders (change limit)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
