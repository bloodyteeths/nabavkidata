"""
Role-Based Access Control (RBAC) Middleware for nabavkidata.com
Provides JWT authentication and role-based authorization
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List, Callable
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from models import User
from database import get_db


# Security scheme
security = HTTPBearer()


# User Role Enum
class UserRole(str, Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    PREMIUM = "premium"
    PRO = "pro"
    FREE = "free"
    GUEST = "guest"


# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


# ============================================================================
# JWT TOKEN UTILITIES
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Payload data to encode
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# USER AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract and validate current user from JWT token

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    # Decode token
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token expiration
    exp = payload.get("exp")
    if exp is None or datetime.utcnow() > datetime.fromtimestamp(exp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify that the current user is active and verified

    Args:
        current_user: Current authenticated user

    Returns:
        User object if active

    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email to access this resource.",
        )

    return current_user


# ============================================================================
# ROLE-BASED ACCESS CONTROL
# ============================================================================

def map_subscription_to_role(subscription_tier: str) -> UserRole:
    """
    Map subscription tier to UserRole enum

    Args:
        subscription_tier: Subscription tier from database

    Returns:
        UserRole enum value
    """
    role_mapping = {
        "admin": UserRole.ADMIN,
        "premium": UserRole.PREMIUM,
        "pro": UserRole.PRO,
        "free": UserRole.FREE,
    }
    return role_mapping.get(subscription_tier.lower(), UserRole.GUEST)


class RoleChecker:
    """
    Callable dependency class for role-based access control

    Usage:
        @router.get("/admin", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
        async def admin_endpoint():
            pass
    """

    def __init__(self, allowed_roles: List[UserRole]):
        """
        Initialize role checker

        Args:
            allowed_roles: List of roles allowed to access the endpoint
        """
        self.allowed_roles = allowed_roles

    async def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        """
        Check if current user has required role

        Args:
            current_user: Current authenticated user

        Returns:
            User object if authorized

        Raises:
            HTTPException: If user doesn't have required role
        """
        user_role = map_subscription_to_role(current_user.subscription_tier)

        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in self.allowed_roles]}. Your role: {user_role.value}",
            )

        return current_user


def require_role(*roles: UserRole) -> Callable:
    """
    Decorator function for role-based access control

    Args:
        *roles: Variable number of UserRole enums allowed to access

    Returns:
        RoleChecker instance

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_endpoint():
            pass

        @router.get("/premium", dependencies=[Depends(require_role(UserRole.PREMIUM, UserRole.PRO))])
        async def premium_endpoint():
            pass
    """
    return RoleChecker(list(roles))


# ============================================================================
# ADMIN-ONLY DEPENDENCY
# ============================================================================

async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency to require admin role

    Args:
        current_user: Current authenticated user

    Returns:
        User object if admin

    Raises:
        HTTPException: If user is not admin
    """
    user_role = map_subscription_to_role(current_user.subscription_tier)

    if user_role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


# ============================================================================
# OPTIONAL AUTHENTICATION
# ============================================================================

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Extract user from token if provided, otherwise return None
    Useful for endpoints that work for both authenticated and anonymous users

    Args:
        credentials: Optional HTTP Bearer credentials
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
