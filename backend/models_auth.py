"""
Authentication Models for nabavkidata.com
Extends existing User model with auth-specific models
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid
import enum

from database import Base


class UserRole(str, enum.Enum):
    """User role enumeration for RBAC"""
    user = "user"
    admin = "admin"
    superadmin = "superadmin"
    # Legacy subscription-based roles (for compatibility)
    free = "free"
    starter = "starter"
    professional = "professional"
    enterprise = "enterprise"


class UserAuth(Base):
    """
    Extended User model for authentication
    Extends the existing users table with additional auth fields
    """
    __tablename__ = "users_auth"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))

    # Authentication fields
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.user, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Additional security fields
    failed_login_attempts = Column(String(50), default=0)
    locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    email_verifications = relationship("EmailVerification", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    login_attempts = relationship("LoginAttempt", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserAuth(user_id={self.user_id}, email={self.email}, role={self.role})>"


class EmailVerification(Base):
    """
    Email verification tokens
    Stores tokens sent to users for email verification
    """
    __tablename__ = "email_verifications"

    verification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)

    # Token lifecycle
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # IP tracking
    ip_address = Column(INET, nullable=True)

    # Relationship
    user = relationship("UserAuth", back_populates="email_verifications")

    def __repr__(self):
        return f"<EmailVerification(email={self.email}, is_used={self.is_used})>"

    @property
    def is_expired(self):
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self):
        """Check if token is valid (not used and not expired)"""
        return not self.is_used and not self.is_expired


class PasswordReset(Base):
    """
    Password reset tokens
    Stores tokens for password reset requests
    """
    __tablename__ = "password_resets"

    reset_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)

    # Token lifecycle
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # IP tracking
    ip_address = Column(INET, nullable=True)

    # Relationship
    user = relationship("UserAuth", back_populates="password_resets")

    def __repr__(self):
        return f"<PasswordReset(email={self.email}, is_used={self.is_used})>"

    @property
    def is_expired(self):
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self):
        """Check if token is valid (not used and not expired)"""
        return not self.is_used and not self.is_expired


class RefreshToken(Base):
    """
    Refresh tokens for JWT authentication
    Allows users to get new access tokens without re-authenticating
    """
    __tablename__ = "refresh_tokens"

    token_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users_auth.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)

    # Token lifecycle
    is_revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    # Device/session tracking
    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_name = Column(String(255), nullable=True)

    # Relationship
    user = relationship("UserAuth", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(user_id={self.user_id}, is_revoked={self.is_revoked})>"

    @property
    def is_expired(self):
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self):
        """Check if token is valid (not revoked and not expired)"""
        return not self.is_revoked and not self.is_expired


class LoginAttempt(Base):
    """
    Login attempt tracking for rate limiting and security
    Tracks both successful and failed login attempts
    """
    __tablename__ = "login_attempts"

    attempt_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users_auth.user_id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String(255), nullable=False, index=True)

    # Attempt details
    was_successful = Column(Boolean, nullable=False)
    failure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Request tracking
    ip_address = Column(INET, nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)

    # Relationship
    user = relationship("UserAuth", back_populates="login_attempts")

    def __repr__(self):
        status = "SUCCESS" if self.was_successful else "FAILED"
        return f"<LoginAttempt(email={self.email}, status={status})>"
