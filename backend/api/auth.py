"""
Authentication API Endpoints for nabavkidata.com
Handles user registration, login, password management, and profile updates
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import os
import httpx
from urllib.parse import urlencode
from collections import defaultdict
from time import time

import logging

from database import get_db
from models import User, AuditLog, UserSession
from pydantic import BaseModel
import hashlib
from schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    MessageResponse, ErrorResponse
)

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days

# Frontend URL for email links
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"{FRONTEND_URL}/api/auth/google/callback")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self):
        self.login_attempts: Dict[str, list] = defaultdict(list)
        self.password_reset_attempts: Dict[str, list] = defaultdict(list)
        self.registration_attempts: Dict[str, list] = defaultdict(list)

    def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
        attempt_type: str = "login"
    ) -> bool:
        """Check if identifier has exceeded rate limit"""
        now = time()

        # Select the appropriate storage
        if attempt_type == "login":
            attempts = self.login_attempts[identifier]
        elif attempt_type == "password_reset":
            attempts = self.password_reset_attempts[identifier]
        elif attempt_type == "registration":
            attempts = self.registration_attempts[identifier]
        else:
            attempts = []

        # Remove old attempts outside window
        attempts[:] = [t for t in attempts if now - t < window_seconds]

        # Check if limit exceeded
        if len(attempts) >= limit:
            return False

        # Add current attempt
        attempts.append(now)
        return True


rate_limiter = RateLimiter()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_verification_token() -> str:
    """Create random verification token"""
    return secrets.token_urlsafe(32)


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email"""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID"""
    result = await db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()


# ============================================================================
# SESSION MANAGEMENT (Single Device Enforcement)
# ============================================================================

def hash_token(token: str) -> str:
    """Create a hash of the token for storage"""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    db: AsyncSession,
    user_id: str,
    token: str,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None
) -> UserSession:
    """
    Create a new session for user, invalidating any existing active sessions.
    This enforces single-device login.
    """
    # Deactivate all existing sessions for this user
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id)
        .where(UserSession.is_active == True)
        .values(is_active=False)
    )

    # Create new session
    session = UserSession(
        user_id=user_id,
        token_hash=hash_token(token),
        device_info=device_info,
        ip_address=ip_address,
        is_active=True
    )
    db.add(session)
    await db.commit()

    return session


async def validate_session(db: AsyncSession, user_id: str, token: str) -> bool:
    """
    Validate that the token belongs to an active session.
    Returns False if session was invalidated (user logged in elsewhere).
    """
    token_hash = hash_token(token)
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .where(UserSession.token_hash == token_hash)
        .where(UserSession.is_active == True)
    )
    session = result.scalar_one_or_none()

    if session:
        # Update last activity
        session.last_activity = datetime.utcnow()
        await db.commit()
        return True

    return False


async def invalidate_session(db: AsyncSession, user_id: str, token: str):
    """Invalidate a specific session (for logout)"""
    token_hash = hash_token(token)
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id)
        .where(UserSession.token_hash == token_hash)
        .values(is_active=False)
    )
    await db.commit()


async def log_audit(
    db: AsyncSession,
    user_id: Optional[str],
    action: str,
    details: dict,
    ip_address: Optional[str] = None
):
    """Log audit event"""
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=ip_address
    )
    db.add(audit_log)
    await db.commit()


async def send_verification_email_task(email: str, token: str, name: str, background_tasks: BackgroundTasks):
    """Send email verification email via Mailersend (background task)"""
    from services.mailer import mailer_service

    async def send_email():
        try:
            result = await mailer_service.send_verification_email(email, token, name)
            if result:
                logger.info(f"Verification email sent to {email}")
            else:
                logger.error(f"Failed to send verification email to {email}")
        except Exception as e:
            logger.error(f"Error sending verification email to {email}: {e}")

    background_tasks.add_task(send_email)


async def send_password_reset_email_task(email: str, token: str, name: str, background_tasks: BackgroundTasks):
    """Send password reset email via Mailersend (background task)"""
    from services.mailer import mailer_service

    async def send_email():
        try:
            result = await mailer_service.send_password_reset_email(email, token, name)
            if result:
                logger.info(f"Password reset email sent to {email}")
            else:
                logger.error(f"Failed to send password reset email to {email}")
        except Exception as e:
            logger.error(f"Error sending password reset email to {email}: {e}")

    background_tasks.add_task(send_email)


# ============================================================================
# DEPENDENCIES
# ============================================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Session kicked exception (different from credentials_exception)
    session_kicked_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expired. You have been logged out because your account was accessed from another device.",
        headers={"WWW-Authenticate": "Bearer", "X-Session-Kicked": "true"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = await get_user_by_id(db, user_id=user_id)
    if user is None:
        raise credentials_exception

    # Validate session is still active (single device enforcement)
    session_valid = await validate_session(db, user_id, token)
    if not session_valid:
        raise session_kicked_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure user is active and email verified"""
    # TEMPORARY: Email verification disabled for testing
    # if not current_user.email_verified:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Email not verified. Please verify your email to continue."
    #     )
    return current_user


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user

    - Creates user account
    - Sends verification email
    - Returns success message
    """
    # Rate limiting
    client_ip = request.client.host
    if not rate_limiter.check_rate_limit(client_ip, limit=5, window_seconds=60, attempt_type="registration"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later."
        )

    # Check if user exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    hashed_password = get_password_hash(user_data.password)
    verification_token = create_verification_token()

    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        email_verified=True, # TEMPORARY: Auto-verify for testing
        subscription_tier="free"
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Send verification email
    await send_verification_email_task(user_data.email, verification_token, user_data.full_name or "User", background_tasks)

    # Log audit
    await log_audit(
        db,
        str(new_user.user_id),
        "user_registered",
        {"email": user_data.email},
        client_ip
    )

    return MessageResponse(
        message="Registration successful",
        detail="Please check your email to verify your account"
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Login user with email and password

    - Validates credentials
    - Returns access token and refresh token
    - Rate limited to 5 attempts per minute per IP
    """
    # Rate limiting
    client_ip = request.client.host if request else "unknown"
    if not rate_limiter.check_rate_limit(client_ip, limit=5, window_seconds=60, attempt_type="login"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )

    # Authenticate user
    user = await get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        await log_audit(
            db,
            None,
            "login_failed",
            {"email": form_data.username},
            client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    access_token = create_access_token(data={"sub": str(user.user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user.user_id)})

    # Create session (invalidates any existing sessions - single device enforcement)
    device_info = request.headers.get("User-Agent", "Unknown") if request else "Unknown"
    await create_session(
        db,
        str(user.user_id),
        access_token,
        device_info=device_info,
        ip_address=client_ip
    )

    # Log audit
    await log_audit(
        db,
        str(user.user_id),
        "user_login",
        {"email": user.email, "single_session_enforced": True},
        client_ip
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token

    - Validates refresh token
    - Issues new access token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = await get_user_by_id(db, user_id=user_id)
    if user is None:
        raise credentials_exception

    # Create new access token
    new_access_token = create_access_token(data={"sub": str(user.user_id)})

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout user

    - Invalidates refresh token (client-side implementation)
    - Logs audit event
    """
    # Log audit
    await log_audit(
        db,
        str(current_user.user_id),
        "user_logout",
        {"email": current_user.email},
        None
    )

    return MessageResponse(
        message="Logout successful",
        detail="Please remove tokens from client storage"
    )


# ============================================================================
# EMAIL VERIFICATION ENDPOINTS
# ============================================================================

@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify user email with token

    - Validates verification token
    - Marks email as verified
    """
    # TODO: Implement token storage and validation
    # For now, this is a placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email verification token validation not yet implemented"
    )


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    email: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Resend email verification

    - Generates new verification token
    - Sends verification email
    """
    user = await get_user_by_email(db, email)
    if not user:
        # Don't reveal if user exists
        return MessageResponse(
            message="If the email exists, a verification link has been sent"
        )

    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )

    # Generate new token
    verification_token = create_verification_token()

    # Send verification email
    await send_verification_email_task(email, verification_token, user.full_name or "User", background_tasks)

    return MessageResponse(
        message="Verification email sent",
        detail="Please check your email"
    )


# ============================================================================
# PASSWORD MANAGEMENT ENDPOINTS
# ============================================================================

class ForgotPasswordRequest(BaseModel):
    email: str


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset

    - Generates password reset token
    - Sends reset email
    - Rate limited to 3 attempts per hour per email
    """
    email = data.email

    # Rate limiting
    if not rate_limiter.check_rate_limit(email, limit=3, window_seconds=3600, attempt_type="password_reset"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Please try again later."
        )

    user = await get_user_by_email(db, email)
    if not user:
        # Don't reveal if user exists
        return MessageResponse(
            message="If the email exists, a password reset link has been sent"
        )

    # Generate reset token
    reset_token = create_verification_token()

    # Send reset email
    await send_password_reset_email_task(email, reset_token, user.full_name or "User", background_tasks)

    # Log audit
    await log_audit(
        db,
        str(user.user_id),
        "password_reset_requested",
        {"email": email},
        request.client.host
    )

    return MessageResponse(
        message="Password reset email sent",
        detail="Please check your email for reset instructions"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    token: str,
    new_password: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password with token

    - Validates reset token
    - Updates password
    """
    # TODO: Implement token storage and validation
    # For now, this is a placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset token validation not yet implemented"
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change password (authenticated users)

    - Validates current password
    - Updates to new password
    """
    # Verify current password
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )

    # Update password
    new_hash = get_password_hash(new_password)
    await db.execute(
        update(User)
        .where(User.user_id == current_user.user_id)
        .values(password_hash=new_hash, updated_at=datetime.utcnow())
    )
    await db.commit()

    # Log audit
    await log_audit(
        db,
        str(current_user.user_id),
        "password_changed",
        {"email": current_user.email},
        None
    )

    return MessageResponse(
        message="Password changed successfully",
        detail="Please login with your new password"
    )


# ============================================================================
# USER PROFILE ENDPOINTS
# ============================================================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile

    - Returns user information
    """
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_user_profile(
    full_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user profile

    - Updates user information
    - Returns updated user data
    """
    update_data = {}

    if full_name is not None:
        update_data["full_name"] = full_name

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_data["updated_at"] = datetime.utcnow()

    await db.execute(
        update(User)
        .where(User.user_id == current_user.user_id)
        .values(**update_data)
    )
    await db.commit()

    # Refresh user data
    await db.refresh(current_user)

    # Log audit
    await log_audit(
        db,
        str(current_user.user_id),
        "profile_updated",
        {"fields": list(update_data.keys())},
        None
    )

    return UserResponse.model_validate(current_user)


# ============================================================================
# GOOGLE OAUTH ENDPOINTS
# ============================================================================

@router.get("/google")
async def google_login():
    """
    Initiate Google OAuth login flow

    Redirects user to Google's OAuth consent screen
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured"
        )

    # Build Google OAuth URL
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"
    }

    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Google OAuth callback

    - Exchanges authorization code for tokens
    - Gets user info from Google
    - Creates or updates user account
    - Returns JWT tokens
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured"
        )

    try:
        # Exchange authorization code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": GOOGLE_REDIRECT_URI
                }
            )

            if token_response.status_code != 200:
                logger.error(f"Google token exchange failed: {token_response.text}")
                return RedirectResponse(
                    url=f"{FRONTEND_URL}/auth/login?error=google_auth_failed"
                )

            token_data = token_response.json()
            access_token = token_data.get("access_token")

            # Get user info from Google
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if user_info_response.status_code != 200:
                logger.error(f"Google user info failed: {user_info_response.text}")
                return RedirectResponse(
                    url=f"{FRONTEND_URL}/auth/login?error=google_auth_failed"
                )

            google_user = user_info_response.json()

        email = google_user.get("email")
        full_name = google_user.get("name")
        google_id = google_user.get("id")

        if not email:
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/login?error=email_required"
            )

        # Check if user exists
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            # Update existing user
            user.updated_at = datetime.utcnow()
            if not user.email_verified:
                user.email_verified = True  # Google emails are verified
            if not user.full_name and full_name:
                user.full_name = full_name
            await db.commit()

            # Log audit
            await log_audit(db, str(user.user_id), "google_login", {"email": email}, None)
        else:
            # Create new user
            import uuid
            user = User(
                user_id=uuid.uuid4(),
                email=email,
                password_hash="",  # No password for OAuth users
                full_name=full_name,
                email_verified=True,  # Google emails are verified
                subscription_tier="free",
                role="user",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            # Log audit
            await log_audit(db, str(user.user_id), "google_registration", {"email": email}, None)

        # Create JWT tokens
        jwt_access_token = create_access_token(data={"sub": str(user.user_id)})
        jwt_refresh_token = create_refresh_token(data={"sub": str(user.user_id)})

        # Create session (invalidates any existing sessions - single device enforcement)
        await create_session(
            db,
            str(user.user_id),
            jwt_access_token,
            device_info="Google OAuth Login",
            ip_address=None
        )

        # Redirect to frontend with tokens
        redirect_url = f"{FRONTEND_URL}/auth/callback?access_token={jwt_access_token}&refresh_token={jwt_refresh_token}"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"Google OAuth error: {str(e)}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/auth/login?error=google_auth_failed"
        )
