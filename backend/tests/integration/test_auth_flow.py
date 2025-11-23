"""
Integration tests for complete authentication flow.
Tests user registration, email verification, login, token refresh, and logout.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid

from main import app
from models_auth import UserAuth, EmailVerification, PasswordReset, RefreshToken, LoginAttempt, UserRole

from services.email_service import EmailService


class TestAuthFlow:
    """Test complete authentication flow from registration to logout"""

    def test_complete_auth_flow(self, client: TestClient, db: Session, mock_email_service):
        """Test complete flow: register -> verify email -> login -> refresh -> logout"""

        # Step 1: Register new user
        register_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User"
        }
        response = client.post("/api/auth/register", json=register_data)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == register_data["email"]
        assert data["is_verified"] is False

        # Verify user created in database
        user = db.query(UserAuth).filter_by(email=register_data["email"]).first()
        assert user is not None
        assert user.is_verified is False

        # Verify email verification token created
        verification = db.query(EmailVerification).filter_by(user_id=user.user_id).first()
        assert verification is not None
        assert verification.is_valid is True

        # Step 2: Verify email
        verify_response = client.post(f"/api/auth/verify-email?token={verification.token}")
        assert verify_response.status_code == 200

        # Verify user is now verified
        db.refresh(user)
        assert user.is_verified is True

        # Step 3: Login
        login_data = {
            "email": register_data["email"],
            "password": register_data["password"]
        }
        login_response = client.post("/api/auth/login", json=login_data)
        assert login_response.status_code == 200
        login_data_response = login_response.json()
        assert "access_token" in login_data_response
        assert "refresh_token" in login_data_response
        assert login_data_response["token_type"] == "bearer"

        access_token = login_data_response["access_token"]
        refresh_token = login_data_response["refresh_token"]

        # Verify refresh token stored in database
        stored_token = db.query(RefreshToken).filter_by(token=refresh_token).first()
        assert stored_token is not None
        assert stored_token.is_valid is True

        # Verify login attempt recorded
        login_attempt = db.query(LoginAttempt).filter_by(email=register_data["email"]).first()
        assert login_attempt is not None
        assert login_attempt.was_successful is True

        # Step 4: Access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        me_response = client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["email"] == register_data["email"]

        # Step 5: Refresh access token
        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()
        assert "access_token" in refresh_data
        new_access_token = refresh_data["access_token"]
        assert new_access_token != access_token

        # Step 6: Logout
        logout_response = client.post(
            "/api/auth/logout",
            headers=headers,
            json={"refresh_token": refresh_token}
        )
        assert logout_response.status_code == 200

        # Verify refresh token is revoked
        db.refresh(stored_token)
        assert stored_token.is_revoked is True

    def test_password_reset_flow(self, client: TestClient, db: Session, test_user: UserAuth, mock_email_service):
        """Test complete password reset flow"""

        # Step 1: Request password reset
        reset_request_data = {"email": test_user.email}
        response = client.post("/api/auth/forgot-password", json=reset_request_data)
        assert response.status_code == 200

        # Verify reset token created
        reset_token_db = db.query(PasswordReset).filter_by(user_id=test_user.user_id).first()
        assert reset_token_db is not None
        assert reset_token_db.is_valid is True

        # Step 2: Reset password using token
        new_password = "NewSecurePass456!"
        reset_data = {
            "token": reset_token_db.token,
            "new_password": new_password
        }
        reset_response = client.post("/api/auth/reset-password", json=reset_data)
        assert reset_response.status_code == 200

        # Verify token is now used
        db.refresh(reset_token_db)
        assert reset_token_db.is_used is True

        # Step 3: Login with new password
        login_data = {
            "email": test_user.email,
            "password": new_password
        }
        login_response = client.post("/api/auth/login", json=login_data)
        assert login_response.status_code == 200

        # Step 4: Verify old password doesn't work
        old_login_data = {
            "email": test_user.email,
            "password": "OldPassword123!"
        }
        old_login_response = client.post("/api/auth/login", json=old_login_data)
        assert old_login_response.status_code == 401

    def test_role_based_access_control(self, client: TestClient, db: Session):
        """Test role-based access control for admin endpoints"""

        # Create regular user
        user_data = {
            "email": "regularuser@example.com",
            "password": "UserPass123!",
            "full_name": "Regular User"
        }
        user_response = client.post("/api/auth/register", json=user_data)
        assert user_response.status_code == 201

        # Verify email (simulate)
        user = db.query(UserAuth).filter_by(email=user_data["email"]).first()
        user.is_verified = True
        db.commit()

        # Login as regular user
        login_response = client.post("/api/auth/login", json=user_data)
        user_token = login_response.json()["access_token"]

        # Try to access admin endpoint
        admin_headers = {"Authorization": f"Bearer {user_token}"}
        admin_response = client.get("/api/admin/users", headers=admin_headers)
        assert admin_response.status_code == 403

        # Create admin user
        admin_data = {
            "email": "admin@example.com",
            "password": "AdminPass123!",
            "full_name": "Admin User"
        }
        admin_reg_response = client.post("/api/auth/register", json=admin_data)
        assert admin_reg_response.status_code == 201

        # Set user as admin
        admin_user = db.query(UserAuth).filter_by(email=admin_data["email"]).first()
        admin_user.is_verified = True
        admin_user.role = UserRole.admin
        db.commit()

        # Login as admin
        admin_login_response = client.post("/api/auth/login", json=admin_data)
        admin_token = admin_login_response.json()["access_token"]

        # Access admin endpoint
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        admin_response = client.get("/api/admin/users", headers=admin_headers)
        assert admin_response.status_code == 200

    def test_token_expiration(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test access token and refresh token expiration"""

        # Login to get tokens
        login_data = {
            "email": test_user.email,
            "password": "TestPass123!"
        }
        login_response = client.post("/api/auth/login", json=login_data)
        tokens = login_response.json()

        # Create expired refresh token
        expired_token = RefreshToken(
            user_id=test_user.user_id,
            token="expired_token_12345",
            expires_at=datetime.utcnow() - timedelta(days=1),
            ip_address="127.0.0.1"
        )
        db.add(expired_token)
        db.commit()

        # Try to use expired refresh token
        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "expired_token_12345"}
        )
        assert refresh_response.status_code == 401

        # Try to revoke expired token
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        logout_response = client.post(
            "/api/auth/logout",
            headers=headers,
            json={"refresh_token": "expired_token_12345"}
        )
        # Should handle expired token gracefully

    def test_multiple_login_sessions(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test user can have multiple active sessions"""

        login_data = {
            "email": test_user.email,
            "password": "TestPass123!"
        }

        # Login from first device
        login1 = client.post("/api/auth/login", json=login_data)
        tokens1 = login1.json()

        # Login from second device
        login2 = client.post("/api/auth/login", json=login_data)
        tokens2 = login2.json()

        # Both sessions should be valid
        assert tokens1["refresh_token"] != tokens2["refresh_token"]

        # Verify both can access protected endpoints
        headers1 = {"Authorization": f"Bearer {tokens1['access_token']}"}
        headers2 = {"Authorization": f"Bearer {tokens2['access_token']}"}

        response1 = client.get("/api/auth/me", headers=headers1)
        response2 = client.get("/api/auth/me", headers=headers2)

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Logout first session
        client.post(
            "/api/auth/logout",
            headers=headers1,
            json={"refresh_token": tokens1["refresh_token"]}
        )

        # Second session should still work
        response2_after = client.get("/api/auth/me", headers=headers2)
        assert response2_after.status_code == 200

    def test_failed_login_attempts(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test failed login attempt tracking and rate limiting"""

        wrong_login_data = {
            "email": test_user.email,
            "password": "WrongPassword123!"
        }

        # Make multiple failed login attempts
        for i in range(3):
            response = client.post("/api/auth/login", json=wrong_login_data)
            assert response.status_code == 401

        # Verify failed attempts are logged
        failed_attempts = db.query(LoginAttempt).filter_by(
            email=test_user.email,
            was_successful=False
        ).count()
        assert failed_attempts >= 3

    def test_email_verification_token_expiry(self, client: TestClient, db: Session):
        """Test email verification token expiration"""

        # Register new user
        register_data = {
            "email": "expiry@example.com",
            "password": "TestPass123!",
            "full_name": "Expiry Test"
        }
        client.post("/api/auth/register", json=register_data)

        user = db.query(UserAuth).filter_by(email=register_data["email"]).first()
        verification = db.query(EmailVerification).filter_by(user_id=user.user_id).first()

        # Manually expire token
        verification.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        # Try to verify with expired token
        verify_response = client.post(f"/api/auth/verify-email?token={verification.token}")
        assert verify_response.status_code == 400 or verify_response.status_code == 401

    def test_password_reset_token_expiry(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test password reset token expiration"""

        # Request password reset
        client.post("/api/auth/forgot-password", json={"email": test_user.email})

        reset_token = db.query(PasswordReset).filter_by(user_id=test_user.user_id).first()

        # Manually expire token
        reset_token.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        # Try to reset password with expired token
        reset_data = {
            "token": reset_token.token,
            "new_password": "NewPassword123!"
        }
        reset_response = client.post("/api/auth/reset-password", json=reset_data)
        assert reset_response.status_code == 400 or reset_response.status_code == 401

    def test_duplicate_email_registration(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test that duplicate email registration is prevented"""

        duplicate_data = {
            "email": test_user.email,
            "password": "AnotherPass123!",
            "full_name": "Duplicate User"
        }

        response = client.post("/api/auth/register", json=duplicate_data)
        assert response.status_code == 400 or response.status_code == 409
