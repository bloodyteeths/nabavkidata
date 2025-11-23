"""
Integration tests for admin operations.
Tests admin user management, tender moderation, analytics, and system monitoring.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from main import app
from models_auth import UserAuth, UserRole
from models import Tender
from models_billing import UserSubscription, Payment


class TestAdminOperations:
    """Test admin-only operations and endpoints"""

    def test_admin_user_management(self, client: TestClient, db: Session, admin_user: UserAuth):
        """Test admin user management operations"""

        # Login as admin
        login_response = client.post("/api/auth/login", json={
            "email": admin_user.email,
            "password": "AdminPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # List all users
        users_response = client.get("/api/admin/users", headers=headers)
        assert users_response.status_code == 200
        users = users_response.json()
        assert "users" in users
        assert "total" in users

        # Search users
        search_response = client.get(
            "/api/admin/users?search=test&page=1&page_size=10",
            headers=headers
        )
        assert search_response.status_code == 200

        # Get specific user
        test_user = db.query(UserAuth).filter(UserAuth.role == UserRole.user).first()
        if test_user:
            user_response = client.get(
                f"/api/admin/users/{test_user.user_id}",
                headers=headers
            )
            assert user_response.status_code == 200
            user_data = user_response.json()
            assert user_data["email"] == test_user.email

        # Update user role
        if test_user:
            update_data = {"role": "admin"}
            update_response = client.patch(
                f"/api/admin/users/{test_user.user_id}",
                json=update_data,
                headers=headers
            )
            assert update_response.status_code == 200

            # Verify role changed
            db.refresh(test_user)
            assert test_user.role == UserRole.admin

        # Suspend user
        if test_user:
            suspend_response = client.post(
                f"/api/admin/users/{test_user.user_id}/suspend",
                headers=headers
            )
            assert suspend_response.status_code == 200

            # Verify user suspended
            db.refresh(test_user)
            assert test_user.is_active is False

        # Reactivate user
        if test_user:
            activate_response = client.post(
                f"/api/admin/users/{test_user.user_id}/activate",
                headers=headers
            )
            assert activate_response.status_code == 200

            # Verify user activated
            db.refresh(test_user)
            assert test_user.is_active is True

    def test_tender_moderation(self, client: TestClient, db: Session, admin_user: UserAuth, test_tenders):
        """Test tender moderation and management"""

        # Login as admin
        login_response = client.post("/api/auth/login", json={
            "email": admin_user.email,
            "password": "AdminPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # List all tenders (including unpublished)
        tenders_response = client.get("/api/admin/tenders", headers=headers)
        assert tenders_response.status_code == 200
        tenders = tenders_response.json()
        assert "tenders" in tenders

        # Get tender for moderation
        tender = test_tenders[0]
        tender_response = client.get(
            f"/api/admin/tenders/{tender.tender_id}",
            headers=headers
        )
        assert tender_response.status_code == 200

        # Update tender status
        update_data = {"status": "closed"}
        update_response = client.patch(
            f"/api/admin/tenders/{tender.tender_id}",
            json=update_data,
            headers=headers
        )
        assert update_response.status_code == 200

        # Flag tender for review
        flag_data = {"reason": "Suspicious content"}
        flag_response = client.post(
            f"/api/admin/tenders/{tender.tender_id}/flag",
            json=flag_data,
            headers=headers
        )
        assert flag_response.status_code == 200

        # Approve tender
        approve_response = client.post(
            f"/api/admin/tenders/{tender.tender_id}/approve",
            headers=headers
        )
        assert approve_response.status_code == 200

        # Delete tender
        delete_response = client.delete(
            f"/api/admin/tenders/{tender.tender_id}",
            headers=headers
        )
        assert delete_response.status_code == 204

    def test_analytics_endpoints(self, client: TestClient, db: Session, admin_user: UserAuth):
        """Test admin analytics and reporting endpoints"""

        # Login as admin
        login_response = client.post("/api/auth/login", json={
            "email": admin_user.email,
            "password": "AdminPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get dashboard stats
        stats_response = client.get("/api/admin/analytics/dashboard", headers=headers)
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert "total_users" in stats
        assert "active_subscriptions" in stats
        assert "total_revenue" in stats
        assert "total_tenders" in stats

        # Get user growth analytics
        growth_response = client.get(
            "/api/admin/analytics/user-growth?period=30d",
            headers=headers
        )
        assert growth_response.status_code == 200
        growth = growth_response.json()
        assert "data" in growth

        # Get revenue analytics
        revenue_response = client.get(
            "/api/admin/analytics/revenue?period=30d",
            headers=headers
        )
        assert revenue_response.status_code == 200
        revenue = revenue_response.json()
        assert "total_revenue" in revenue
        assert "revenue_by_plan" in revenue

        # Get tender statistics
        tender_stats_response = client.get(
            "/api/admin/analytics/tenders",
            headers=headers
        )
        assert tender_stats_response.status_code == 200
        tender_stats = tender_stats_response.json()
        assert "total" in tender_stats
        assert "by_status" in tender_stats

        # Get user engagement metrics
        engagement_response = client.get(
            "/api/admin/analytics/engagement",
            headers=headers
        )
        assert engagement_response.status_code == 200
        engagement = engagement_response.json()
        assert "active_users" in engagement

    def test_system_monitoring(self, client: TestClient, db: Session, admin_user: UserAuth):
        """Test system monitoring and health check endpoints"""

        # Login as admin
        login_response = client.post("/api/auth/login", json={
            "email": admin_user.email,
            "password": "AdminPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get system health
        health_response = client.get("/api/admin/system/health", headers=headers)
        assert health_response.status_code == 200
        health = health_response.json()
        assert "database" in health
        assert "redis" in health or "cache" in health

        # Get system metrics
        metrics_response = client.get("/api/admin/system/metrics", headers=headers)
        assert metrics_response.status_code == 200
        metrics = metrics_response.json()
        assert "cpu_usage" in metrics or "memory_usage" in metrics

        # Get error logs
        logs_response = client.get(
            "/api/admin/system/logs?level=error&limit=50",
            headers=headers
        )
        assert logs_response.status_code == 200
        logs = logs_response.json()
        assert "logs" in logs

        # Get API usage statistics
        api_stats_response = client.get(
            "/api/admin/system/api-usage",
            headers=headers
        )
        assert api_stats_response.status_code == 200
        api_stats = api_stats_response.json()
        assert "total_requests" in api_stats or "endpoints" in api_stats

    def test_admin_access_control(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test that non-admin users cannot access admin endpoints"""

        # Login as regular user
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Try to access admin users endpoint
        users_response = client.get("/api/admin/users", headers=headers)
        assert users_response.status_code == 403

        # Try to access admin analytics
        analytics_response = client.get("/api/admin/analytics/dashboard", headers=headers)
        assert analytics_response.status_code == 403

        # Try to update user role
        update_response = client.patch(
            f"/api/admin/users/{test_user.user_id}",
            json={"role": "admin"},
            headers=headers
        )
        assert update_response.status_code == 403

    def test_bulk_operations(self, client: TestClient, db: Session, admin_user: UserAuth):
        """Test admin bulk operations"""

        # Login as admin
        login_response = client.post("/api/auth/login", json={
            "email": admin_user.email,
            "password": "AdminPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Bulk user update
        user_ids = [str(u.user_id) for u in db.query(UserAuth).limit(3).all()]
        bulk_update_data = {
            "user_ids": user_ids,
            "action": "verify"
        }
        bulk_response = client.post(
            "/api/admin/users/bulk-action",
            json=bulk_update_data,
            headers=headers
        )
        assert bulk_response.status_code == 200

        # Bulk tender update
        tender_ids = [str(t.tender_id) for t in db.query(Tender).limit(3).all()]
        if tender_ids:
            bulk_tender_data = {
                "tender_ids": tender_ids,
                "action": "archive"
            }
            bulk_tender_response = client.post(
                "/api/admin/tenders/bulk-action",
                json=bulk_tender_data,
                headers=headers
            )
            assert bulk_tender_response.status_code == 200

    def test_subscription_management(self, client: TestClient, db: Session, admin_user: UserAuth, test_subscription):
        """Test admin subscription management"""

        # Login as admin
        login_response = client.post("/api/auth/login", json={
            "email": admin_user.email,
            "password": "AdminPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # List all subscriptions
        subs_response = client.get("/api/admin/subscriptions", headers=headers)
        assert subs_response.status_code == 200
        subs = subs_response.json()
        assert "subscriptions" in subs

        # Get subscription details
        sub_response = client.get(
            f"/api/admin/subscriptions/{test_subscription.subscription_id}",
            headers=headers
        )
        assert sub_response.status_code == 200

        # Extend subscription
        extend_data = {"days": 30}
        extend_response = client.post(
            f"/api/admin/subscriptions/{test_subscription.subscription_id}/extend",
            json=extend_data,
            headers=headers
        )
        assert extend_response.status_code == 200

        # Cancel user subscription
        cancel_response = client.post(
            f"/api/admin/subscriptions/{test_subscription.subscription_id}/cancel",
            headers=headers
        )
        assert cancel_response.status_code == 200

    def test_audit_log(self, client: TestClient, db: Session, admin_user: UserAuth):
        """Test audit log functionality"""

        # Login as admin
        login_response = client.post("/api/auth/login", json={
            "email": admin_user.email,
            "password": "AdminPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get audit logs
        audit_response = client.get(
            "/api/admin/audit-logs?limit=50",
            headers=headers
        )
        assert audit_response.status_code == 200
        logs = audit_response.json()
        assert "logs" in logs

        # Filter audit logs by user
        user_logs_response = client.get(
            f"/api/admin/audit-logs?user_id={admin_user.user_id}",
            headers=headers
        )
        assert user_logs_response.status_code == 200

        # Filter audit logs by action
        action_logs_response = client.get(
            "/api/admin/audit-logs?action=login",
            headers=headers
        )
        assert action_logs_response.status_code == 200
