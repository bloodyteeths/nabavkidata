"""
Admin Operations Scenario

This scenario simulates administrative operations including
data synchronization, cache management, user management, and system operations.
"""

import random
from locust import task, TaskSet


class AdminOperationsScenario(TaskSet):
    """
    Realistic admin behavior for platform management.
    Admins typically:
    1. Login with admin credentials
    2. Monitor system status
    3. Perform data synchronization
    4. Manage users and permissions
    5. Execute maintenance tasks
    """

    ADMIN_OPERATIONS = [
        "sync_tenders",
        "refresh_cache",
        "update_statistics",
        "clean_old_data",
        "reindex_search",
        "optimize_database",
        "generate_reports",
        "backup_data"
    ]

    REPORT_TYPES = [
        "daily_summary",
        "weekly_analytics",
        "monthly_statistics",
        "user_activity",
        "system_performance",
        "data_quality",
        "error_logs"
    ]

    def on_start(self):
        """Initialize admin scenario with login"""
        self.admin_token = None
        self.admin_login()

    def admin_login(self):
        """Login as admin user"""
        # Try different admin accounts
        admin_accounts = [
            ("admin@nabavki.si", "admin_password_123"),
            ("superadmin@nabavki.si", "super_admin_pass"),
            (f"admin_{random.randint(1, 5)}@example.com", "test_admin_pass")
        ]

        email, password = random.choice(admin_accounts)

        payload = {
            "email": email,
            "password": password
        }

        response = self.client.post(
            "/api/v1/auth/login",
            json=payload,
            name="/api/v1/auth/login (admin)"
        )

        if response.status_code == 200:
            try:
                data = response.json()
                self.admin_token = data.get("access_token")
            except:
                self.admin_token = None

    def get_admin_headers(self):
        """Get admin authorization headers"""
        if self.admin_token:
            return {"Authorization": f"Bearer {self.admin_token}"}
        return {}

    @task(15)
    def sync_tenders(self):
        """Trigger tender data synchronization"""
        if not self.admin_token:
            self.admin_login()

        payload = {
            "source": random.choice(["enarocanje", "all", "incremental"]),
            "force": random.choice([True, False])
        }

        with self.client.post(
            "/api/v1/admin/sync/tenders",
            json=payload,
            headers=self.get_admin_headers(),
            name="/api/v1/admin/sync/tenders",
            catch_response=True
        ) as response:
            if response.status_code in [200, 202, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(10)
    def refresh_cache(self):
        """Refresh system cache"""
        if not self.admin_token:
            self.admin_login()

        cache_types = ["all", "tenders", "statistics", "search"]
        cache_type = random.choice(cache_types)

        with self.client.post(
            f"/api/v1/admin/cache/refresh",
            json={"type": cache_type},
            headers=self.get_admin_headers(),
            name="/api/v1/admin/cache/refresh",
            catch_response=True
        ) as response:
            if response.status_code in [200, 202, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(12)
    def get_system_status(self):
        """Check system status and health"""
        if not self.admin_token:
            self.admin_login()

        with self.client.get(
            "/api/v1/admin/status",
            headers=self.get_admin_headers(),
            name="/api/v1/admin/status",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(8)
    def list_users(self):
        """List all users with pagination"""
        if not self.admin_token:
            self.admin_login()

        params = {
            "page": random.randint(1, 10),
            "limit": random.choice([20, 50, 100]),
            "sort": random.choice(["created_desc", "email_asc"])
        }

        with self.client.get(
            "/api/v1/admin/users",
            params=params,
            headers=self.get_admin_headers(),
            name="/api/v1/admin/users",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def update_user_permissions(self):
        """Update user permissions"""
        if not self.admin_token:
            self.admin_login()

        user_id = random.randint(1, 1000)
        payload = {
            "role": random.choice(["user", "premium", "admin"]),
            "permissions": random.sample(
                ["read", "write", "delete", "admin"],
                k=random.randint(1, 3)
            )
        }

        with self.client.patch(
            f"/api/v1/admin/users/{user_id}/permissions",
            json=payload,
            headers=self.get_admin_headers(),
            name="/api/v1/admin/users/[id]/permissions",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 403, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(10)
    def generate_report(self):
        """Generate system reports"""
        if not self.admin_token:
            self.admin_login()

        report_type = random.choice(self.REPORT_TYPES)
        payload = {
            "type": report_type,
            "period": random.choice(["daily", "weekly", "monthly"]),
            "format": random.choice(["pdf", "csv", "json"])
        }

        with self.client.post(
            "/api/v1/admin/reports/generate",
            json=payload,
            headers=self.get_admin_headers(),
            name="/api/v1/admin/reports/generate",
            catch_response=True
        ) as response:
            if response.status_code in [200, 202, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(7)
    def view_audit_logs(self):
        """View system audit logs"""
        if not self.admin_token:
            self.admin_login()

        params = {
            "page": random.randint(1, 20),
            "limit": 50,
            "action": random.choice([None, "login", "create", "update", "delete"]),
            "user_id": random.choice([None, random.randint(1, 100)])
        }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        with self.client.get(
            "/api/v1/admin/audit-logs",
            params=params,
            headers=self.get_admin_headers(),
            name="/api/v1/admin/audit-logs",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(6)
    def update_system_settings(self):
        """Update system configuration settings"""
        if not self.admin_token:
            self.admin_login()

        settings = {
            "maintenance_mode": random.choice([True, False]),
            "sync_interval": random.choice([3600, 7200, 86400]),
            "max_search_results": random.choice([100, 500, 1000]),
            "cache_ttl": random.choice([300, 600, 1800])
        }

        with self.client.patch(
            "/api/v1/admin/settings",
            json=settings,
            headers=self.get_admin_headers(),
            name="/api/v1/admin/settings",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(8)
    def view_statistics(self):
        """View detailed system statistics"""
        if not self.admin_token:
            self.admin_login()

        stats_type = random.choice([
            "overview",
            "performance",
            "users",
            "tenders",
            "api_usage"
        ])

        with self.client.get(
            f"/api/v1/admin/statistics/{stats_type}",
            headers=self.get_admin_headers(),
            name="/api/v1/admin/statistics/[type]",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(4)
    def reindex_search(self):
        """Trigger search index rebuild"""
        if not self.admin_token:
            self.admin_login()

        payload = {
            "index_type": random.choice(["tenders", "organizations", "all"]),
            "full_rebuild": random.choice([True, False])
        }

        with self.client.post(
            "/api/v1/admin/search/reindex",
            json=payload,
            headers=self.get_admin_headers(),
            name="/api/v1/admin/search/reindex",
            catch_response=True
        ) as response:
            if response.status_code in [200, 202, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(3)
    def cleanup_old_data(self):
        """Clean up old/expired data"""
        if not self.admin_token:
            self.admin_login()

        payload = {
            "older_than_days": random.choice([30, 90, 180, 365]),
            "data_type": random.choice([
                "expired_tenders",
                "old_logs",
                "temp_files",
                "sessions"
            ]),
            "dry_run": random.choice([True, False])
        }

        with self.client.post(
            "/api/v1/admin/cleanup",
            json=payload,
            headers=self.get_admin_headers(),
            name="/api/v1/admin/cleanup",
            catch_response=True
        ) as response:
            if response.status_code in [200, 202, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def monitor_jobs(self):
        """Monitor background jobs status"""
        if not self.admin_token:
            self.admin_login()

        with self.client.get(
            "/api/v1/admin/jobs",
            params={"status": random.choice([None, "pending", "running", "completed", "failed"])},
            headers=self.get_admin_headers(),
            name="/api/v1/admin/jobs",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 403]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
