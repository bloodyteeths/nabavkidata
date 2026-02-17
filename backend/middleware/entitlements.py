"""
Entitlements Middleware for nabavkidata.com
Provides tier-based feature gating and usage limit enforcement

Usage:
    from middleware.entitlements import require_module, check_usage_limit

    @router.get("/analytics", dependencies=[Depends(require_module(ModuleName.ANALYTICS))])
    async def get_analytics():
        pass

    @router.post("/rag")
    async def rag_query(user: User = Depends(get_current_active_user)):
        await check_usage_limit(user, "rag_queries", db)
        ...
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from datetime import datetime, date
from typing import Optional, Dict, Any, Callable
import logging

from models import User
from database import get_db
from middleware.rbac import get_current_active_user
from config.plans import (
    ModuleName,
    AccessLevel,
    PlanTier,
    get_plan,
    get_plan_modules,
    get_plan_limits,
    has_module_access,
    get_module_access_level,
    get_daily_limit,
    get_monthly_limit,
    is_unlimited,
    TRIAL_DAYS,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENTITLEMENT CHECKER
# ============================================================================

class EntitlementChecker:
    """
    Callable dependency for checking module access based on subscription tier
    """

    def __init__(
        self,
        module: ModuleName,
        required_level: AccessLevel = AccessLevel.LIMITED,
        check_trial_credits: bool = False
    ):
        """
        Initialize entitlement checker

        Args:
            module: Module to check access for
            required_level: Minimum access level required (default: LIMITED)
            check_trial_credits: Whether to check trial credits before allowing access
        """
        self.module = module
        self.required_level = required_level
        self.check_trial_credits = check_trial_credits

    async def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """
        Check if user has required module access

        Args:
            current_user: Authenticated user
            db: Database session

        Returns:
            User object if authorized

        Raises:
            HTTPException: If access denied
        """
        tier = await self._get_effective_tier(current_user, db)
        access_level = get_module_access_level(tier, self.module)

        # Check access level hierarchy
        level_hierarchy = {
            AccessLevel.NONE: 0,
            AccessLevel.LIMITED: 1,
            AccessLevel.FULL: 2,
            AccessLevel.UNLIMITED: 3,
        }

        user_level = level_hierarchy.get(access_level, 0)
        required = level_hierarchy.get(self.required_level, 1)

        if user_level < required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=self._get_upgrade_message(tier, self.module)
            )

        return current_user

    async def _get_effective_tier(self, user: User, db: AsyncSession) -> str:
        """Get user's effective tier (considering trial status)"""
        # Check if user is in trial
        if hasattr(user, 'trial_ends_at') and user.trial_ends_at:
            if user.trial_ends_at > datetime.utcnow():
                return PlanTier.TRIAL.value

        # Get from subscription or user tier
        tier = user.subscription_tier or "free"
        return tier.lower()

    def _get_upgrade_message(self, current_tier: str, module: ModuleName) -> str:
        """Generate upgrade suggestion message"""
        module_to_tier = {
            ModuleName.ANALYTICS: "starter",
            ModuleName.RISK_ANALYSIS: "professional",
            ModuleName.COMPETITOR_TRACKING: "starter",
            ModuleName.EXPORT_PDF: "professional",
            ModuleName.API_ACCESS: "enterprise",
            ModuleName.TEAM_MANAGEMENT: "enterprise",
        }
        suggested_tier = module_to_tier.get(module, "professional")
        return f"Оваа функција бара {suggested_tier.upper()} план. Надградете го вашиот план за пристап."


def require_module(
    module: ModuleName,
    required_level: AccessLevel = AccessLevel.LIMITED
) -> Callable:
    """
    Dependency factory for module access control

    Args:
        module: Module to require access for
        required_level: Minimum access level required

    Returns:
        EntitlementChecker instance

    Usage:
        @router.get("/analytics", dependencies=[Depends(require_module(ModuleName.ANALYTICS))])
        async def get_analytics():
            pass
    """
    return EntitlementChecker(module, required_level)


# ============================================================================
# USAGE LIMIT CHECKING
# ============================================================================

async def get_usage_count(
    db: AsyncSession,
    user_id: str,
    counter_type: str,
    period_type: str = "daily"
) -> int:
    """
    Get current usage count for a counter

    Args:
        db: Database session
        user_id: User's UUID
        counter_type: Type of counter (rag_queries, exports, etc.)
        period_type: daily or monthly

    Returns:
        Current count (0 if no counter exists)
    """
    if period_type == "daily":
        period_start = date.today()
    else:
        period_start = date.today().replace(day=1)

    result = await db.execute(
        text("""
            SELECT count FROM usage_counters
            WHERE user_id = :user_id
              AND counter_type = :counter_type
              AND period_type = :period_type
              AND period_start = :period_start
        """),
        {
            "user_id": user_id,
            "counter_type": counter_type,
            "period_type": period_type,
            "period_start": period_start,
        }
    )
    row = result.fetchone()
    return row[0] if row else 0


async def check_usage_limit(
    user: User,
    counter_type: str,
    db: AsyncSession,
    increment: bool = True
) -> Dict[str, Any]:
    """
    Check if user is within usage limits and optionally increment counter

    Args:
        user: User object
        counter_type: Type of counter to check
        db: Database session
        increment: Whether to increment the counter if within limits

    Returns:
        Dict with allowed, remaining, limit info

    Raises:
        HTTPException: If limit exceeded
    """
    tier = user.subscription_tier or "free"

    # Check daily limit first
    daily_limit = get_daily_limit(tier, counter_type)
    if daily_limit is not None:
        daily_count = await get_usage_count(db, str(user.user_id), counter_type, "daily")
        if daily_count >= daily_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Дневниот лимит е достигнат",
                    "message": f"Достигнат е дневниот лимит од {daily_limit} за {counter_type}",
                    "limit": daily_limit,
                    "used": daily_count,
                    "reset": "утре",
                    "upgrade_url": "/plans"
                }
            )

    # Check monthly limit
    monthly_limit = get_monthly_limit(tier, counter_type)
    if monthly_limit is not None:
        monthly_count = await get_usage_count(db, str(user.user_id), counter_type, "monthly")
        if monthly_count >= monthly_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Месечниот лимит е достигнат",
                    "message": f"Достигнат е месечниот лимит од {monthly_limit} за {counter_type}",
                    "limit": monthly_limit,
                    "used": monthly_count,
                    "reset": "следниот месец",
                    "upgrade_url": "/plans"
                }
            )

    # Increment counter if requested
    if increment:
        await increment_usage(db, str(user.user_id), counter_type, daily_limit, monthly_limit)

    # Calculate remaining
    daily_remaining = (daily_limit - daily_count - 1) if daily_limit else None
    monthly_remaining = (monthly_limit - monthly_count - 1) if monthly_limit else None

    return {
        "allowed": True,
        "daily": {
            "limit": daily_limit,
            "used": daily_count + (1 if increment else 0),
            "remaining": daily_remaining,
        } if daily_limit else None,
        "monthly": {
            "limit": monthly_limit,
            "used": monthly_count + (1 if increment else 0),
            "remaining": monthly_remaining,
        } if monthly_limit else None,
        "unlimited": daily_limit is None and monthly_limit is None,
    }


async def increment_usage(
    db: AsyncSession,
    user_id: str,
    counter_type: str,
    daily_limit: Optional[int] = None,
    monthly_limit: Optional[int] = None
) -> None:
    """
    Increment usage counters for a user

    Args:
        db: Database session
        user_id: User's UUID
        counter_type: Type of counter
        daily_limit: Daily limit value (for creating new counters)
        monthly_limit: Monthly limit value
    """
    today = date.today()
    month_start = today.replace(day=1)

    # Increment or create daily counter
    await db.execute(
        text("""
            INSERT INTO usage_counters (user_id, counter_type, period_type, period_start, count, limit_value)
            VALUES (:user_id, :counter_type, 'daily', :period_start, 1, :limit_value)
            ON CONFLICT (user_id, counter_type, period_type, period_start)
            DO UPDATE SET count = usage_counters.count + 1, updated_at = NOW()
        """),
        {
            "user_id": user_id,
            "counter_type": counter_type,
            "period_start": today,
            "limit_value": daily_limit,
        }
    )

    # Increment or create monthly counter
    await db.execute(
        text("""
            INSERT INTO usage_counters (user_id, counter_type, period_type, period_start, count, limit_value)
            VALUES (:user_id, :counter_type, 'monthly', :period_start, 1, :limit_value)
            ON CONFLICT (user_id, counter_type, period_type, period_start)
            DO UPDATE SET count = usage_counters.count + 1, updated_at = NOW()
        """),
        {
            "user_id": user_id,
            "counter_type": counter_type,
            "period_start": month_start,
            "limit_value": monthly_limit,
        }
    )

    await db.commit()


async def get_remaining_quota(
    user: User,
    counter_type: str,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Get remaining quota for a specific counter type

    Args:
        user: User object
        counter_type: Type of counter
        db: Database session

    Returns:
        Dict with remaining quota info
    """
    tier = user.subscription_tier or "free"

    daily_limit = get_daily_limit(tier, counter_type)
    monthly_limit = get_monthly_limit(tier, counter_type)

    daily_count = await get_usage_count(db, str(user.user_id), counter_type, "daily")
    monthly_count = await get_usage_count(db, str(user.user_id), counter_type, "monthly")

    return {
        "counter_type": counter_type,
        "tier": tier,
        "daily": {
            "limit": daily_limit,
            "used": daily_count,
            "remaining": (daily_limit - daily_count) if daily_limit else None,
            "unlimited": daily_limit is None,
        },
        "monthly": {
            "limit": monthly_limit,
            "used": monthly_count,
            "remaining": (monthly_limit - monthly_count) if monthly_limit else None,
            "unlimited": monthly_limit is None,
        },
    }


# ============================================================================
# TRIAL CREDIT CHECKING
# ============================================================================

async def check_trial_credit(
    user: User,
    credit_type: str,
    db: AsyncSession,
    use_credit: bool = True
) -> Dict[str, Any]:
    """
    Check if user has trial credits available

    Args:
        user: User object
        credit_type: Type of credit (ai_messages, document_extractions, etc.)
        db: Database session
        use_credit: Whether to consume a credit if available

    Returns:
        Dict with credit status

    Raises:
        HTTPException: If no credits available
    """
    # Check if user is in trial
    if not hasattr(user, 'trial_ends_at') or not user.trial_ends_at:
        return {"in_trial": False, "credits": None}

    if user.trial_ends_at < datetime.utcnow():
        return {"in_trial": False, "trial_expired": True, "credits": None}

    # Get trial credits
    result = await db.execute(
        text("""
            SELECT total_credits, used_credits, expires_at
            FROM trial_credits
            WHERE user_id = :user_id
              AND credit_type = :credit_type
              AND expires_at > NOW()
        """),
        {"user_id": str(user.user_id), "credit_type": credit_type}
    )
    row = result.fetchone()

    if not row:
        return {"in_trial": True, "credits": None}

    total, used, expires = row
    remaining = total - used

    if remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Кредитите за пробниот период се потрошени",
                "message": f"Ги искористивте сите {total} кредити за {credit_type}",
                "upgrade_url": "/plans",
            }
        )

    # Use credit if requested
    if use_credit:
        await db.execute(
            text("""
                UPDATE trial_credits
                SET used_credits = used_credits + 1, updated_at = NOW()
                WHERE user_id = :user_id AND credit_type = :credit_type
            """),
            {"user_id": str(user.user_id), "credit_type": credit_type}
        )
        await db.commit()
        remaining -= 1

    return {
        "in_trial": True,
        "credits": {
            "type": credit_type,
            "total": total,
            "used": used + (1 if use_credit else 0),
            "remaining": remaining,
            "expires_at": expires.isoformat() if expires else None,
        }
    }


# ============================================================================
# CONVENIENCE DECORATORS
# ============================================================================

# Pre-built checkers for common modules
require_analytics = require_module(ModuleName.ANALYTICS)
require_risk_analysis = require_module(ModuleName.RISK_ANALYSIS)
require_competitor_tracking = require_module(ModuleName.COMPETITOR_TRACKING)
require_api_access = require_module(ModuleName.API_ACCESS, AccessLevel.LIMITED)
require_export_pdf = require_module(ModuleName.EXPORT_PDF)
require_team_management = require_module(ModuleName.TEAM_MANAGEMENT)


async def require_paid_plan(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Require user to have any paid plan (not free)

    Raises:
        HTTPException: If user is on free plan
    """
    tier = (current_user.subscription_tier or "free").lower()
    if tier in ("free", "trial"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Оваа функција бара платен план. Надградете за пристап."
        )
    return current_user
