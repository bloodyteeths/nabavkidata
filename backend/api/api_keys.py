"""
API Key Management Endpoints
Enterprise tier only - for programmatic access to the API
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
import secrets
import hashlib
import uuid

from database import get_db
from models import User, APIKey
from api.auth import get_current_user, get_current_active_user

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


# ============================================================================
# SCHEMAS
# ============================================================================

class APIKeyCreate(BaseModel):
    """Request to create a new API key"""
    name: str = Field(..., min_length=1, max_length=100, description="Name for this API key")
    scopes: List[str] = Field(default=["read"], description="Permissions: read, write")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration (optional)")


class APIKeyResponse(BaseModel):
    """API key info (without the actual key)"""
    key_id: str
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    request_count: int
    created_at: datetime


class APIKeyCreatedResponse(BaseModel):
    """Response when creating a new API key - includes the actual key (shown only once)"""
    key_id: str
    name: str
    api_key: str  # The actual key - only shown once!
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime]
    message: str = "Save this API key now. It won't be shown again."


class APIKeyListResponse(BaseModel):
    """List of API keys"""
    total: int
    keys: List[APIKeyResponse]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns (full_key, key_prefix, key_hash)
    """
    # Generate 32 random bytes = 256 bits of entropy
    random_bytes = secrets.token_bytes(32)

    # Create the full key with prefix
    key_suffix = secrets.token_urlsafe(32)
    full_key = f"nb_live_{key_suffix}"

    # Key prefix for display (first 12 chars)
    key_prefix = full_key[:12]

    # Hash for storage
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    return full_key, key_prefix, key_hash


def hash_api_key(api_key: str) -> str:
    """Hash an API key for lookup"""
    return hashlib.sha256(api_key.encode()).hexdigest()


async def verify_enterprise_tier(user: User) -> bool:
    """Check if user has Enterprise tier"""
    tier = getattr(user, 'subscription_tier', 'free').lower()
    return tier == 'enterprise'


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all API keys for the current user.

    Requires Enterprise tier.
    """
    # Check Enterprise tier
    if not await verify_enterprise_tier(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "API keys are only available for Enterprise tier",
                "upgrade_url": "/pricing"
            }
        )

    # Get all keys for user
    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == current_user.user_id)
        .order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    return APIKeyListResponse(
        total=len(keys),
        keys=[
            APIKeyResponse(
                key_id=str(k.key_id),
                name=k.name,
                key_prefix=k.key_prefix,
                scopes=k.scopes or ["read"],
                is_active=k.is_active,
                last_used_at=k.last_used_at,
                expires_at=k.expires_at,
                request_count=k.request_count,
                created_at=k.created_at
            )
            for k in keys
        ]
    )


@router.post("", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new API key.

    Requires Enterprise tier.
    The actual key is only shown once in the response - save it immediately!
    Maximum 5 active keys per user.
    """
    # Check Enterprise tier
    if not await verify_enterprise_tier(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "API keys are only available for Enterprise tier",
                "upgrade_url": "/pricing"
            }
        )

    # Check key limit (max 5 active keys)
    active_keys_result = await db.execute(
        select(APIKey)
        .where(
            and_(
                APIKey.user_id == current_user.user_id,
                APIKey.is_active == True
            )
        )
    )
    active_keys = active_keys_result.scalars().all()

    if len(active_keys) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 active API keys allowed. Revoke an existing key first."
        )

    # Validate scopes
    valid_scopes = {"read", "write"}
    for scope in key_data.scopes:
        if scope not in valid_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scope: {scope}. Valid scopes are: {', '.join(valid_scopes)}"
            )

    # Generate the key
    full_key, key_prefix, key_hash = generate_api_key()

    # Calculate expiration
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)

    # Create the key record
    new_key = APIKey(
        user_id=current_user.user_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=key_data.name,
        scopes=key_data.scopes,
        expires_at=expires_at
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return APIKeyCreatedResponse(
        key_id=str(new_key.key_id),
        name=new_key.name,
        api_key=full_key,
        key_prefix=key_prefix,
        scopes=new_key.scopes,
        expires_at=expires_at,
        message="Save this API key now. It won't be shown again."
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke (delete) an API key.

    The key will immediately stop working.
    """
    # Check Enterprise tier
    if not await verify_enterprise_tier(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API keys are only available for Enterprise tier"
        )

    # Find the key
    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key ID format")

    result = await db.execute(
        select(APIKey)
        .where(
            and_(
                APIKey.key_id == key_uuid,
                APIKey.user_id == current_user.user_id
            )
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Revoke it
    api_key.is_active = False
    api_key.revoked_at = datetime.utcnow()
    await db.commit()

    return {
        "message": "API key revoked successfully",
        "key_id": key_id
    }


# ============================================================================
# API KEY AUTHENTICATION (for use in other endpoints)
# ============================================================================

async def get_user_from_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Authenticate user via API key header.

    Use this as a dependency in endpoints that should accept API key auth.
    Returns None if no API key provided (allows fallback to JWT auth).
    """
    if not x_api_key:
        return None

    # Validate key format
    if not x_api_key.startswith("nb_live_"):
        return None

    # Hash and lookup
    key_hash = hash_api_key(x_api_key)

    result = await db.execute(
        select(APIKey)
        .where(
            and_(
                APIKey.key_hash == key_hash,
                APIKey.is_active == True
            )
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key"
        )

    # Check expiration
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired"
        )

    # Update last used and request count
    api_key.last_used_at = datetime.utcnow()
    api_key.request_count += 1
    await db.commit()

    # Get the user
    user_result = await db.execute(
        select(User).where(User.user_id == api_key.user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for API key"
        )

    return user


async def get_current_user_or_api_key(
    api_key_user: Optional[User] = Depends(get_user_from_api_key),
    jwt_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Authenticate via API key OR JWT token.

    API key takes precedence if provided.
    Use this for endpoints that should support both auth methods.
    """
    if api_key_user:
        return api_key_user

    if jwt_user:
        return jwt_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide X-API-Key header or Bearer token."
    )
