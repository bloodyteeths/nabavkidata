"""
Authentication Service for nabavkidata.com
Handles user authentication, password management, email verification, and rate limiting
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
from uuid import UUID
import secrets
import os

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import User
from schemas import UserCreate


# ============================================================================
# CONFIGURATION
# ============================================================================

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
EMAIL_VERIFICATION_EXPIRE_HOURS = 24
PASSWORD_RESET_EXPIRE_HOURS = 1
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15

# Password context for bcrypt hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory storage for rate limiting and tokens (use Redis in production)
login_attempts: Dict[str, list] = {}
verification_tokens: Dict[str, Dict] = {}
password_reset_tokens: Dict[str, Dict] = {}
refresh_tokens: Dict[str, Dict] = {}


# ============================================================================
# PASSWORD HASHING
# ============================================================================

def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against its hash

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT TOKEN MANAGEMENT
# ============================================================================

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Dictionary containing claims to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: UUID) -> str:
    """
    Create a JWT refresh token

    Args:
        user_id: User's unique identifier

    Returns:
        Encoded JWT refresh token string
    """
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Store refresh token for validation
    refresh_tokens[encoded_jwt] = {
        "user_id": str(user_id),
        "created_at": datetime.utcnow(),
        "expires_at": expire
    }

    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token

    Args:
        token: JWT token to verify

    Returns:
        Dictionary containing decoded token payload

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError(f"Token verification failed: {str(e)}")


def revoke_refresh_token(token: str) -> bool:
    """
    Revoke a refresh token

    Args:
        token: Refresh token to revoke

    Returns:
        True if token was revoked, False if not found
    """
    if token in refresh_tokens:
        del refresh_tokens[token]
        return True
    return False


# ============================================================================
# USER AUTHENTICATION
# ============================================================================

async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: Optional[str] = None
) -> User:
    """
    Register a new user

    Args:
        db: Database session
        email: User's email address
        password: Plain text password
        full_name: Optional full name

    Returns:
        Created User object

    Raises:
        ValueError: If email already exists
    """
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise ValueError("Email already registered")

    # Create new user
    hashed_password = hash_password(password)

    new_user = User(
        email=email.lower(),
        password_hash=hashed_password,
        full_name=full_name,
        subscription_tier="free",
        email_verified=False
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str
) -> Optional[User]:
    """
    Authenticate a user with email and password

    Args:
        db: Database session
        email: User's email address
        password: Plain text password

    Returns:
        User object if authentication successful, None otherwise
    """
    # Get user by email
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    user = result.scalar_one_or_none()

    if not user:
        return None

    # Verify password
    if not verify_password(password, user.password_hash):
        return None

    return user


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """
    Get user by ID

    Args:
        db: Database session
        user_id: User's unique identifier

    Returns:
        User object if found, None otherwise
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Get user by email

    Args:
        db: Database session
        email: User's email address

    Returns:
        User object if found, None otherwise
    """
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


# ============================================================================
# EMAIL VERIFICATION
# ============================================================================

def generate_verification_token(user_id: UUID, email: str) -> str:
    """
    Generate an email verification token

    Args:
        user_id: User's unique identifier
        email: User's email address

    Returns:
        Verification token string
    """
    token = secrets.token_urlsafe(32)

    verification_tokens[token] = {
        "user_id": str(user_id),
        "email": email.lower(),
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=EMAIL_VERIFICATION_EXPIRE_HOURS)
    }

    return token


async def verify_email(db: AsyncSession, token: str) -> bool:
    """
    Verify user's email with token

    Args:
        db: Database session
        token: Email verification token

    Returns:
        True if verification successful, False otherwise
    """
    token_data = verification_tokens.get(token)

    if not token_data:
        return False

    # Check if token expired
    if datetime.utcnow() > token_data["expires_at"]:
        del verification_tokens[token]
        return False

    # Update user's email_verified status
    user_id = UUID(token_data["user_id"])

    await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(email_verified=True, updated_at=datetime.utcnow())
    )
    await db.commit()

    # Remove used token
    del verification_tokens[token]

    return True


# ============================================================================
# PASSWORD RESET
# ============================================================================

async def request_password_reset(db: AsyncSession, email: str) -> Optional[str]:
    """
    Request password reset and generate reset token

    Args:
        db: Database session
        email: User's email address

    Returns:
        Password reset token if user exists, None otherwise
    """
    user = await get_user_by_email(db, email)

    if not user:
        # Don't reveal if email exists
        return None

    token = secrets.token_urlsafe(32)

    password_reset_tokens[token] = {
        "user_id": str(user.user_id),
        "email": email.lower(),
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=PASSWORD_RESET_EXPIRE_HOURS)
    }

    return token


async def reset_password(
    db: AsyncSession,
    token: str,
    new_password: str
) -> bool:
    """
    Reset user's password with reset token

    Args:
        db: Database session
        token: Password reset token
        new_password: New plain text password

    Returns:
        True if password reset successful, False otherwise
    """
    token_data = password_reset_tokens.get(token)

    if not token_data:
        return False

    # Check if token expired
    if datetime.utcnow() > token_data["expires_at"]:
        del password_reset_tokens[token]
        return False

    # Update user's password
    user_id = UUID(token_data["user_id"])
    new_password_hash = hash_password(new_password)

    await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(password_hash=new_password_hash, updated_at=datetime.utcnow())
    )
    await db.commit()

    # Remove used token
    del password_reset_tokens[token]

    return True


async def change_password(
    db: AsyncSession,
    user_id: UUID,
    current_password: str,
    new_password: str
) -> bool:
    """
    Change user's password (requires current password verification)

    Args:
        db: Database session
        user_id: User's unique identifier
        current_password: Current plain text password
        new_password: New plain text password

    Returns:
        True if password changed successfully, False otherwise
    """
    user = await get_user_by_id(db, user_id)

    if not user:
        return False

    # Verify current password
    if not verify_password(current_password, user.password_hash):
        return False

    # Update password
    new_password_hash = hash_password(new_password)

    await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(password_hash=new_password_hash, updated_at=datetime.utcnow())
    )
    await db.commit()

    return True


# ============================================================================
# RATE LIMITING / LOGIN ATTEMPTS
# ============================================================================

def check_login_attempts(email: str) -> bool:
    """
    Check if user has exceeded login attempt limit

    Args:
        email: User's email address

    Returns:
        True if user can attempt login, False if locked out
    """
    email_lower = email.lower()

    if email_lower not in login_attempts:
        return True

    attempts = login_attempts[email_lower]

    # Clean up old attempts (outside lockout window)
    cutoff_time = datetime.utcnow() - timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    attempts = [attempt for attempt in attempts if attempt["timestamp"] > cutoff_time]
    login_attempts[email_lower] = attempts

    # Count failed attempts within lockout window
    failed_attempts = [a for a in attempts if not a["success"]]

    if len(failed_attempts) >= MAX_LOGIN_ATTEMPTS:
        return False

    return True


def record_login_attempt(email: str, success: bool) -> None:
    """
    Record a login attempt for rate limiting

    Args:
        email: User's email address
        success: Whether login was successful
    """
    email_lower = email.lower()

    if email_lower not in login_attempts:
        login_attempts[email_lower] = []

    login_attempts[email_lower].append({
        "timestamp": datetime.utcnow(),
        "success": success
    })

    # If successful, clear failed attempts
    if success:
        login_attempts[email_lower] = [
            a for a in login_attempts[email_lower] if a["success"]
        ]


def get_lockout_time_remaining(email: str) -> Optional[int]:
    """
    Get remaining lockout time in seconds

    Args:
        email: User's email address

    Returns:
        Remaining seconds if locked out, None otherwise
    """
    email_lower = email.lower()

    if email_lower not in login_attempts:
        return None

    attempts = login_attempts[email_lower]
    cutoff_time = datetime.utcnow() - timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    failed_attempts = [
        a for a in attempts
        if not a["success"] and a["timestamp"] > cutoff_time
    ]

    if len(failed_attempts) < MAX_LOGIN_ATTEMPTS:
        return None

    # Get oldest failed attempt within window
    oldest_attempt = min(failed_attempts, key=lambda x: x["timestamp"])
    unlock_time = oldest_attempt["timestamp"] + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    remaining = (unlock_time - datetime.utcnow()).total_seconds()

    return int(remaining) if remaining > 0 else None


# ============================================================================
# TOKEN CLEANUP (Call periodically from background task)
# ============================================================================

def cleanup_expired_tokens() -> Dict[str, int]:
    """
    Remove expired tokens from in-memory storage
    Should be called periodically by a background task

    Returns:
        Dictionary with count of removed tokens by type
    """
    now = datetime.utcnow()
    removed = {
        "verification": 0,
        "password_reset": 0,
        "refresh": 0
    }

    # Clean verification tokens
    expired_verification = [
        token for token, data in verification_tokens.items()
        if data["expires_at"] < now
    ]
    for token in expired_verification:
        del verification_tokens[token]
        removed["verification"] += 1

    # Clean password reset tokens
    expired_reset = [
        token for token, data in password_reset_tokens.items()
        if data["expires_at"] < now
    ]
    for token in expired_reset:
        del password_reset_tokens[token]
        removed["password_reset"] += 1

    # Clean refresh tokens
    expired_refresh = [
        token for token, data in refresh_tokens.items()
        if data["expires_at"] < now
    ]
    for token in expired_refresh:
        del refresh_tokens[token]
        removed["refresh"] += 1

    return removed
