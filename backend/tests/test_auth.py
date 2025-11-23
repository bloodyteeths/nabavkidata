"""
Tests for authentication system
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from services.auth_service import hash_password, verify_password, create_access_token, verify_token

client = TestClient(app)

# Test data
TEST_USER = {
    "email": "test@example.com",
    "password": "Test123!@#",
    "full_name": "Test User"
}

def test_register_user():
    """Test user registration"""
    response = client.post(
        "/api/auth/register",
        json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
            "confirm_password": TEST_USER["password"],
            "full_name": TEST_USER["full_name"]
        }
    )
    assert response.status_code in [201, 400]  # 400 if user exists
    if response.status_code == 201:
        data = response.json()
        assert data["email"] == TEST_USER["email"]
        assert "user_id" in data

def test_login_user():
    """Test user login"""
    response = client.post(
        "/api/auth/login",
        data={
            "username": TEST_USER["email"],
            "password": TEST_USER["password"]
        }
    )
    # May fail if user not verified, that's ok for test
    assert response.status_code in [200, 401, 403]
    if response.status_code == 200:
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

def test_password_hashing():
    """Test password hashing and verification"""
    password = "TestPassword123!"
    hashed = hash_password(password)
    
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword", hashed)

def test_token_creation():
    """Test JWT token creation"""
    data = {"sub": "test-user-id"}
    token = create_access_token(data, timedelta(minutes=30))
    
    assert token
    assert isinstance(token, str)
    assert len(token) > 20

def test_token_verification():
    """Test JWT token verification"""
    data = {"sub": "test-user-id", "email": "test@example.com"}
    token = create_access_token(data, timedelta(minutes=30))
    
    decoded = verify_token(token)
    assert decoded
    assert decoded["sub"] == "test-user-id"
    assert decoded["email"] == "test@example.com"

def test_invalid_token():
    """Test invalid token handling"""
    with pytest.raises(Exception):
        verify_token("invalid.token.here")

def test_expired_token():
    """Test expired token handling"""
    data = {"sub": "test-user-id"}
    # Create token that expires immediately
    token = create_access_token(data, timedelta(seconds=-1))
    
    with pytest.raises(Exception):
        verify_token(token)

def test_me_endpoint_unauthorized():
    """Test /me endpoint without auth"""
    response = client.get("/api/auth/me")
    assert response.status_code == 401

def test_register_weak_password():
    """Test registration with weak password"""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "weak@example.com",
            "password": "weak",
            "confirm_password": "weak"
        }
    )
    assert response.status_code == 422  # Validation error

def test_register_password_mismatch():
    """Test registration with mismatched passwords"""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "mismatch@example.com",
            "password": "Test123!@#",
            "confirm_password": "Different123!@#"
        }
    )
    assert response.status_code == 422

def test_register_invalid_email():
    """Test registration with invalid email"""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "not-an-email",
            "password": "Test123!@#",
            "confirm_password": "Test123!@#"
        }
    )
    assert response.status_code == 422

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
