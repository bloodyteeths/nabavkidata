"""
Fraud Prevention API Endpoints
Provides endpoints for fraud detection and rate limiting
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from database import get_db
from models import User
from schemas_fraud import (
    FraudCheckRequest, FraudCheckResponse, RateLimitResponse,
    SuspiciousActivityList, DuplicateAccountList, UserFraudSummary,
    AllTierLimits, TierLimits, BlockedEmailCreate, BlockedEmailResponse,
    BlockedIPCreate, BlockedIPResponse
)
from services.fraud_prevention import (
    perform_fraud_check, get_rate_limit, get_user_fraud_summary,
    is_email_allowed, is_ip_blocked, block_ip, TIER_LIMITS
)

# You'll need to import your auth dependency
# from api.auth import get_current_user

router = APIRouter(prefix="/api/fraud", tags=["Fraud Prevention"])


# ============================================================================
# FRAUD CHECK ENDPOINTS
# ============================================================================

@router.post("/check", response_model=FraudCheckResponse)
async def check_fraud(
    request: FraudCheckRequest,
    current_user: User = Depends(get_current_user),  # Replace with your auth dependency
    db: AsyncSession = Depends(get_db)
):
    """
    Perform comprehensive fraud check for a user action

    This endpoint checks:
    - IP blocking status
    - Email validity (for registration)
    - VPN/Proxy usage (for free tier)
    - Rate limits
    - Duplicate accounts

    Returns whether the action is allowed and provides detailed information.
    """
    try:
        # Convert fingerprint data to dict
        additional_data = request.fingerprint_data.model_dump()

        # Perform fraud check
        is_allowed, block_reason, details = await perform_fraud_check(
            db=db,
            user=current_user,
            ip_address=request.ip_address,
            device_fingerprint=request.fingerprint_data.device_fingerprint,
            user_agent=request.user_agent,
            check_type=request.check_type,
            additional_data=additional_data
        )

        # Get risk score from details if available
        risk_score = details.get("latest_risk_score") if details else None
        redirect_to = details.get("redirect_to") if details and not is_allowed else None

        return FraudCheckResponse(
            is_allowed=is_allowed,
            block_reason=block_reason,
            redirect_to=redirect_to,
            details=details,
            risk_score=risk_score
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fraud check failed: {str(e)}"
        )


# ============================================================================
# RATE LIMIT ENDPOINTS
# ============================================================================

@router.get("/rate-limit", response_model=RateLimitResponse)
async def get_user_rate_limit(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current rate limit status for the authenticated user

    Returns:
    - Current query counts
    - Daily/monthly limits
    - Trial information
    - Block status
    """
    rate_limit = await get_rate_limit(db, current_user.user_id)

    if not rate_limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rate limit not found"
        )

    tier_config = TIER_LIMITS.get(rate_limit.subscription_tier.lower(), TIER_LIMITS["free"])
    daily_limit = tier_config["daily_queries"]
    daily_remaining = max(0, daily_limit - rate_limit.daily_query_count) if daily_limit > 0 else -1

    return RateLimitResponse(
        user_id=current_user.user_id,
        subscription_tier=rate_limit.subscription_tier,
        daily_query_count=rate_limit.daily_query_count,
        daily_limit=daily_limit,
        daily_remaining=daily_remaining,
        monthly_query_count=rate_limit.monthly_query_count,
        total_query_count=rate_limit.total_query_count,
        trial_end_date=rate_limit.trial_end_date,
        trial_expired=rate_limit.is_trial_expired,
        is_blocked=rate_limit.is_blocked,
        block_reason=rate_limit.block_reason,
        daily_reset_at=rate_limit.daily_reset_at
    )


@router.get("/tier-limits", response_model=AllTierLimits)
async def get_tier_limits():
    """
    Get information about all subscription tier limits

    Public endpoint that shows what each tier offers
    """
    tier_info = {}

    for tier_name, limits in TIER_LIMITS.items():
        features = []

        if limits["daily_queries"] == -1:
            features.append("Unlimited queries")
        else:
            features.append(f"{limits['daily_queries']} queries per day")

        if limits["trial_days"] > 0:
            features.append(f"{limits['trial_days']}-day trial")

        if limits["allow_vpn"]:
            features.append("VPN/Proxy allowed")

        tier_info[tier_name] = TierLimits(
            tier=tier_name,
            daily_queries=limits["daily_queries"],
            monthly_queries=limits["monthly_queries"],
            trial_days=limits["trial_days"],
            allow_vpn=limits["allow_vpn"],
            features=features
        )

    return AllTierLimits(**tier_info)


# ============================================================================
# USER FRAUD SUMMARY ENDPOINTS
# ============================================================================

@router.get("/summary", response_model=UserFraudSummary)
async def get_fraud_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive fraud detection summary for the current user

    Includes:
    - Rate limit status
    - Fraud detection counts
    - Risk scores
    - Suspicious activity counts
    - Duplicate account detections
    """
    summary = await get_user_fraud_summary(db, current_user.user_id)

    return UserFraudSummary(
        user_id=current_user.user_id,
        **summary
    )


# ============================================================================
# EMAIL VALIDATION ENDPOINTS
# ============================================================================

@router.post("/validate-email")
async def validate_email(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate if an email is allowed (not temporary/disposable)

    Public endpoint for registration form validation
    """
    is_allowed, reason = await is_email_allowed(db, email)

    return {
        "email": email,
        "is_allowed": is_allowed,
        "reason": reason
    }


# ============================================================================
# IP VALIDATION ENDPOINTS
# ============================================================================

@router.post("/validate-ip")
async def validate_ip(
    ip_address: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Check if an IP address is blocked

    Can be used by middleware or registration forms
    """
    is_blocked_result, reason = await is_ip_blocked(db, ip_address)

    return {
        "ip_address": ip_address,
        "is_blocked": is_blocked_result,
        "reason": reason
    }


# ============================================================================
# ADMIN ENDPOINTS (require admin role)
# ============================================================================

@router.post("/admin/block-ip", response_model=BlockedIPResponse)
async def admin_block_ip(
    block_data: BlockedIPCreate,
    current_user: User = Depends(get_current_user),  # Add admin check
    db: AsyncSession = Depends(get_db)
):
    """
    Block an IP address (admin only)

    Requires admin role
    """
    # TODO: Add admin role check
    # if current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="Admin access required")

    blocked_ip = await block_ip(
        db=db,
        ip_address=block_data.ip_address,
        reason=block_data.reason,
        block_type=block_data.block_type,
        expires_at=block_data.expires_at,
        blocked_by=current_user.email
    )

    return blocked_ip


@router.get("/admin/suspicious-activities", response_model=SuspiciousActivityList)
async def get_suspicious_activities(
    limit: int = 50,
    unresolved_only: bool = True,
    current_user: User = Depends(get_current_user),  # Add admin check
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of suspicious activities (admin only)

    Requires admin role
    """
    # TODO: Add admin role check and implement query
    pass


@router.get("/admin/user-fraud/{user_id}", response_model=UserFraudSummary)
async def get_user_fraud_admin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),  # Add admin check
    db: AsyncSession = Depends(get_db)
):
    """
    Get fraud summary for any user (admin only)

    Requires admin role
    """
    # TODO: Add admin role check

    summary = await get_user_fraud_summary(db, user_id)

    return UserFraudSummary(
        user_id=user_id,
        **summary
    )


# ============================================================================
# HELPER FUNCTIONS FOR INTEGRATION
# ============================================================================

def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request

    Checks X-Forwarded-For header first (for proxies/load balancers)
    Falls back to direct client IP
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Get first IP in chain
        return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request"""
    return request.headers.get("User-Agent", "unknown")


# Example middleware function (add to your main.py)
"""
from fastapi import Request
from services.fraud_prevention import is_ip_blocked

@app.middleware("http")
async def fraud_prevention_middleware(request: Request, call_next):
    # Skip for certain paths
    if request.url.path.startswith("/api/docs") or request.url.path.startswith("/api/health"):
        return await call_next(request)

    # Get client IP
    client_ip = get_client_ip(request)

    # Check if IP is blocked
    async with get_db() as db:
        is_blocked, reason = await is_ip_blocked(db, client_ip)

        if is_blocked:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Access Denied",
                    "message": reason or "Your IP address has been blocked",
                    "redirect_to": "/blocked"
                }
            )

    # Continue with request
    response = await call_next(request)
    return response
"""
