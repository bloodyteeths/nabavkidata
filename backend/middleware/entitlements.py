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
from services.entitlements_service import (
    effective_tier,
    has_client_perks,
    perks_required_detail,
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
        """Perks belong to managed clients and admins only (no trial override)."""
        return effective_tier(user)

    def _get_upgrade_message(self, current_tier: str, module: ModuleName) -> dict:
        """403 detail for the PaywallModal, which now sells the bid service."""
        return perks_required_detail(module.value)


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
    tier = effective_tier(user)

    # Check daily limit first
    daily_limit = get_daily_limit(tier, counter_type)
    if daily_limit == 0:
        # Zero means the counter is a client perk, not an exhausted quota.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=perks_required_detail(counter_type),
        )
    if daily_limit is not None:
        daily_count = await get_usage_count(db, str(user.user_id), counter_type, "daily")
        if daily_count >= daily_limit:
            # Friendly counter type names
            counter_names = {
                "rag_queries": "AI прашања",
                "price_views": "ценовни прегледи",
                "document_views": "прегледи на документи",
                "exports": "извоз",
                "alerts": "известувања",
            }
            friendly_name = counter_names.get(counter_type, counter_type)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Дневниот лимит е достигнат",
                    "message": f"Ги искористивте сите {daily_limit} {friendly_name} за денес.",
                    "hint": "Оваа можност е вклучена за клиентите за кои подготвуваме понуди.",
                    "limit": daily_limit,
                    "used": daily_count,
                    "reset": "утре",
                    "upgrade_url": "/settings#plans",
                    "trial_available": False,
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
    tier = effective_tier(user)

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
    # Self-serve trials are retired (bid service, 14 Oct 2026): perks follow
    # account_type, never trial credits.
    return {"in_trial": False, "credits": None}


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


# ============================================================================
# PRICE VIEW QUOTA
# ============================================================================

async def check_price_view_quota(
    user: Optional[User],
    db: AsyncSession,
    increment: bool = True,
) -> Dict[str, Any]:
    """
    Check if user has remaining daily price view quota.

    Counting strategy: 1 price view = 1 search page or 1 tender detail view.

    Args:
        user: User object (None for anonymous)
        db: Database session
        increment: Whether to consume a view if quota available

    Returns:
        Dict with has_quota, remaining, limit, used
    """
    # Anonymous users get no price views
    if not user:
        return {"has_quota": False, "remaining": 0, "limit": 0, "used": 0}

    tier = effective_tier(user)
    daily_limit = get_daily_limit(tier, "price_views")

    # None means unlimited
    if daily_limit is None:
        return {"has_quota": True, "remaining": None, "limit": None, "used": 0}

    # Zero means no access
    if daily_limit == 0:
        return {"has_quota": False, "remaining": 0, "limit": 0, "used": 0}

    daily_count = await get_usage_count(db, str(user.user_id), "price_views", "daily")

    if daily_count >= daily_limit:
        return {
            "has_quota": False,
            "remaining": 0,
            "limit": daily_limit,
            "used": daily_count,
        }

    # Increment counter if requested
    if increment:
        await increment_usage(db, str(user.user_id), "price_views", daily_limit, None)

    remaining = daily_limit - daily_count - (1 if increment else 0)
    return {
        "has_quota": True,
        "remaining": remaining,
        "limit": daily_limit,
        "used": daily_count + (1 if increment else 0),
    }


async def require_paid_plan(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Require client perks (managed client or admin).

    Raises:
        HTTPException: If the user is not a client we write bids for
    """
    if not has_client_perks(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=perks_required_detail(),
        )
    return current_user


async def require_client_perks(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Dependency for routes that are a client perk (AI chat, RAG, exports...)."""
    if not has_client_perks(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=perks_required_detail(),
        )
    return current_user
