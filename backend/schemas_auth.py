"""
Authentication Pydantic Schemas for nabavkidata.com
Request/response validation for authentication endpoints
"""
from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration for API responses"""
    user = "user"
    admin = "admin"
    superadmin = "superadmin"


# ============================================================================
# REGISTRATION SCHEMAS
# ============================================================================

class UserRegister(BaseModel):
    """User registration schema with password validation"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    confirm_password: str = Field(..., min_length=8, max_length=100, description="Password confirmation")
    full_name: Optional[str] = Field(None, max_length=255, description="User full name")

    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password: min 8 chars, uppercase, lowercase, number"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v

    @root_validator
    def validate_passwords_match(cls, values):
        """Ensure password and confirm_password match"""
        password = values.get('password')
        confirm_password = values.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise ValueError('Passwords do not match')
        return values


# ============================================================================
# LOGIN SCHEMAS
# ============================================================================

class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


# ============================================================================
# USER RESPONSE SCHEMAS
# ============================================================================

class UserResponse(BaseModel):
    """User response schema (excludes password)"""
    user_id: UUID
    email: str
    full_name: Optional[str]
    is_verified: bool
    is_active: bool
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================================
# TOKEN SCHEMAS
# ============================================================================

class TokenResponse(BaseModel):
    """JWT token response schema"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Request schema for refreshing access token"""
    refresh_token: str = Field(..., description="Valid refresh token")


class RefreshTokenResponse(BaseModel):
    """Response schema for refreshed tokens"""
    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


# ============================================================================
# PASSWORD RESET SCHEMAS
# ============================================================================

class PasswordResetRequest(BaseModel):
    """Password reset request schema"""
    email: EmailStr = Field(..., description="Email address for password reset")


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema"""
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")
    confirm_password: str = Field(..., min_length=8, max_length=100, description="Confirm new password")

    @validator('new_password')
    def validate_password_strength(cls, v):
        """Validate password: min 8 chars, uppercase, lowercase, number"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v

    @root_validator
    def validate_passwords_match(cls, values):
        """Ensure new_password and confirm_password match"""
        new_password = values.get('new_password')
        confirm_password = values.get('confirm_password')
        if new_password and confirm_password and new_password != confirm_password:
            raise ValueError('Passwords do not match')
        return values


# ============================================================================
# EMAIL VERIFICATION SCHEMAS
# ============================================================================

class EmailVerifyRequest(BaseModel):
    """Email verification request schema"""
    token: str = Field(..., min_length=1, description="Email verification token")


class ResendVerificationRequest(BaseModel):
    """Request schema for resending verification email"""
    email: EmailStr = Field(..., description="Email address to resend verification")


# ============================================================================
# PASSWORD CHANGE SCHEMAS
# ============================================================================

class ChangePassword(BaseModel):
    """Change password schema for authenticated users"""
    old_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")
    confirm_password: str = Field(..., min_length=8, max_length=100, description="Confirm new password")

    @validator('new_password')
    def validate_password_strength(cls, v):
        """Validate password: min 8 chars, uppercase, lowercase, number"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v

    @root_validator
    def validate_passwords_match(cls, values):
        """Ensure new_password and confirm_password match"""
        new_password = values.get('new_password')
        confirm_password = values.get('confirm_password')
        old_password = values.get('old_password')
        if new_password and confirm_password and new_password != confirm_password:
            raise ValueError('New passwords do not match')
        if old_password and new_password and old_password == new_password:
            raise ValueError('New password must be different from old password')
        return values


# ============================================================================
# GENERIC RESPONSE SCHEMAS
# ============================================================================

class MessageResponse(BaseModel):
    """Generic success message response"""
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    """Generic error response"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
