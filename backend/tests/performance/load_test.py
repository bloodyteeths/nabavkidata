"""Load testing with Locust"""
from locust import HttpUser, task, between

class NabavkiUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """Login once"""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest@example.com",
            "password": "Test123!"
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]

    @task(5)
    def search_tenders(self):
        """Search tenders - most common action"""
        self.client.get(
            "/api/v1/tenders/search",
            params={"status": "open", "page": 1},
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(2)
    def view_tender(self):
        """View tender details"""
        self.client.get(
            "/api/v1/tenders/2024/001",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def ask_ai(self):
        """AI query - resource intensive"""
        self.client.post(
            "/api/v1/ai/ask",
            json={"question": "Largest IT tenders?"},
            headers={"Authorization": f"Bearer {self.token}"}
        )

# Run: locust -f load_test.py --host=http://localhost:8000 --users 100 --spawn-rate 10
