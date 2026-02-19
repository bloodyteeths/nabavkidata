"""
Authentication Flow Scenario

This scenario simulates user authentication flows including
registration, login, profile management, and authenticated operations.
"""

import random
from locust import task, TaskSet, events


class AuthFlowScenario(TaskSet):
    """
    Realistic authentication behavior.
    Users typically:
    1. Register account
    2. Login
    3. Access protected resources
    4. Manage profile
    5. Logout
    """

    def on_start(self):
        """Initialize authentication scenario"""
        self.user_id = random.randint(1, 10000)
        self.email = f"test_user_{self.user_id}@example.com"
        self.password = "test_password_123"
        self.token = None
        self.refresh_token = None
        self.login_attempts = 0

    def get_auth_headers(self):
        """Get authorization headers"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(20)
    def login(self):
        """User login"""
        payload = {
            "email": self.email,
            "password": self.password
        }

        with self.client.post(
            "/api/v1/auth/login",
            json=payload,
            name="/api/v1/auth/login",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    self.login_attempts += 1
                    response.success()
                except Exception as e:
                    response.failure(f"Parse error: {str(e)}")
            elif response.status_code == 401:
                # Expected for test users that don't exist
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def register(self):
        """User registration"""
        unique_id = random.randint(1, 1000000)
        payload = {
            "email": f"new_user_{unique_id}@example.com",
            "password": "secure_password_123",
            "full_name": f"Test User {unique_id}",
            "organization": random.choice([
                "Test Company", "Demo Organization", None
            ])
        }

        with self.client.post(
            "/api/v1/auth/register",
            json=payload,
            name="/api/v1/auth/register",
            catch_response=True
        ) as response:
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    # Optionally store token if registration auto-logs in
                    if "access_token" in data:
                        self.token = data["access_token"]
                    response.success()
                except Exception as e:
                    response.failure(f"Parse error: {str(e)}")
            elif response.status_code == 400:
                # Email might already exist
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(15)
    def get_current_user(self):
        """Get current user profile"""
        if not self.token:
            self.login()

        with self.client.get(
            "/api/v1/users/me",
            headers=self.get_auth_headers(),
            name="/api/v1/users/me",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "email" in data or "id" in data:
                        response.success()
                    else:
                        response.failure("Missing user data")
                except Exception as e:
                    response.failure(f"Parse error: {str(e)}")
            elif response.status_code == 401:
                # Token expired or invalid
                self.token = None
                self.login()
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(8)
    def update_profile(self):
        """Update user profile"""
        if not self.token:
            self.login()

        payload = {
            "full_name": f"Updated User {random.randint(1, 1000)}",
            "preferences": {
                "language": random.choice(["sl", "en"]),
                "notifications": random.choice([True, False])
            }
        }

        with self.client.patch(
            "/api/v1/users/me",
            json=payload,
            headers=self.get_auth_headers(),
            name="/api/v1/users/me (update)",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(10)
    def refresh_access_token(self):
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            return

        payload = {
            "refresh_token": self.refresh_token
        }

        with self.client.post(
            "/api/v1/auth/refresh",
            json=payload,
            name="/api/v1/auth/refresh",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.token = data.get("access_token")
                    response.success()
                except Exception as e:
                    response.failure(f"Parse error: {str(e)}")
            elif response.status_code in [401, 404]:
                # Endpoint might not exist or token expired
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(12)
    def get_favorites(self):
        """Get user's favorite tenders"""
        if not self.token:
            self.login()

        with self.client.get(
            "/api/v1/users/favorites",
            headers=self.get_auth_headers(),
            name="/api/v1/users/favorites",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(10)
    def add_favorite(self):
        """Add tender to favorites"""
        if not self.token:
            self.login()

        tender_id = random.randint(1, 1000)
        payload = {
            "tender_id": tender_id
        }

        with self.client.post(
            "/api/v1/users/favorites",
            json=payload,
            headers=self.get_auth_headers(),
            name="/api/v1/users/favorites (add)",
            catch_response=True
        ) as response:
            if response.status_code in [200, 201, 401]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def remove_favorite(self):
        """Remove tender from favorites"""
        if not self.token:
            self.login()

        tender_id = random.randint(1, 1000)

        with self.client.delete(
            f"/api/v1/users/favorites/{tender_id}",
            headers=self.get_auth_headers(),
            name="/api/v1/users/favorites/[id] (remove)",
            catch_response=True
        ) as response:
            if response.status_code in [200, 204, 401, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(7)
    def get_search_history(self):
        """Get user's search history"""
        if not self.token:
            self.login()

        with self.client.get(
            "/api/v1/users/search-history",
            headers=self.get_auth_headers(),
            name="/api/v1/users/search-history",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(3)
    def logout(self):
        """User logout"""
        if not self.token:
            return

        with self.client.post(
            "/api/v1/auth/logout",
            headers=self.get_auth_headers(),
            name="/api/v1/auth/logout",
            catch_response=True
        ) as response:
            if response.status_code in [200, 204, 401, 404]:
                self.token = None
                self.refresh_token = None
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(2)
    def change_password(self):
        """Change user password"""
        if not self.token:
            self.login()

        payload = {
            "old_password": self.password,
            "new_password": f"new_password_{random.randint(1, 1000)}"
        }

        with self.client.post(
            "/api/v1/auth/change-password",
            json=payload,
            headers=self.get_auth_headers(),
            name="/api/v1/auth/change-password",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
