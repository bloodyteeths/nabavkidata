"""
Billing API Endpoints for nabavkidata.com
Handles subscription management, Stripe integration, payment processing, fraud prevention, and usage limits
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from time import time
from decimal import Decimal
from pydantic import BaseModel
import os
import json
import stripe
import hmac
import hashlib
import logging

from database import get_db
from models import User, Subscription, UsageTracking, AuditLog
from api.auth import get_current_user, get_current_active_user
from services.billing_service import billing_service, PLAN_LIMITS, PRICE_IDS

# ============================================================================
# CONFIGURATION
# ============================================================================

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(
    prefix="/billing",
    tags=["Billing"]
)

# Free trial configuration
FREE_TRIAL_DAYS = 7

# Subscription plan definitions - matches Stripe products
# Free tier after trial expires - very limited
# Trial: 7 days with Pro features, credit-based (50 AI, 15 docs, 5 exports, 20 alerts)
# Start/Pro/Team: paid tiers with new pricing
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Бесплатен",
        "price_mkd": 0,
        "price_eur": 0,
        "stripe_price_id": None,
        "features": [
            "Основно пребарување",
            "3 AI прашања дневно",
            "Преглед на тендери",
            "Нема извоз"
        ],
        "limits": {
            "rag_queries_per_day": 3,
            "saved_alerts": 1,
            "export_results": False,
            "doc_extractions_per_day": 0,
            "competitor_alerts": 0,
            "ai_summary": False,
            "risk_analysis": False
        }
    },
    "trial": {
        "name": "Пробен период",
        "price_mkd": 0,
        "price_eur": 0,
        "stripe_price_id": None,
        "features": [
            "50 AI пораки (кредит)",
            "15 екстракции на документи",
            "5 извози",
            "20 известувања за конкуренти",
            "Про функции 7 дена"
        ],
        "limits": {
            "rag_queries_per_day": 50,  # Credit-based, not daily
            "saved_alerts": 20,
            "export_results": True,
            "doc_extractions_per_day": 15,
            "competitor_alerts": 20,
            "ai_summary": True,
            "risk_analysis": True
        }
    },
    "start": {
        "name": "Стартуј",
        "price_mkd": 1990,
        "price_eur": 39,
        "price_yearly_mkd": 19900,
        "price_yearly_eur": 390,
        "stripe_price_id": PRICE_IDS.get("start", {}).get("monthly"),
        "features": [
            "15 AI прашања дневно",
            "10 зачувани известувања",
            "CSV извоз",
            "5 известувања за конкуренти"
        ],
        "limits": {
            "rag_queries_per_day": 15,
            "saved_alerts": 10,
            "export_results": True,
            "doc_extractions_per_day": 5,
            "competitor_alerts": 5,
            "ai_summary": True,
            "risk_analysis": False
        }
    },
    "pro": {
        "name": "Про",
        "price_mkd": 5990,
        "price_eur": 99,
        "price_yearly_mkd": 59900,
        "price_yearly_eur": 990,
        "stripe_price_id": PRICE_IDS.get("pro", {}).get("monthly"),
        "features": [
            "50 AI прашања дневно",
            "50 зачувани известувања",
            "CSV и PDF извоз",
            "Анализа на ризик",
            "20 известувања за конкуренти"
        ],
        "limits": {
            "rag_queries_per_day": 50,
            "saved_alerts": 50,
            "export_results": True,
            "doc_extractions_per_day": 20,
            "competitor_alerts": 20,
            "ai_summary": True,
            "risk_analysis": True
        }
    },
    "team": {
        "name": "Тим",
        "price_mkd": 12990,
        "price_eur": 199,
        "price_yearly_mkd": 129900,
        "price_yearly_eur": 1990,
        "stripe_price_id": PRICE_IDS.get("team", {}).get("monthly"),
        "features": [
            "Неограничени AI прашања",
            "Неограничени известувања",
            "Неограничен извоз",
            "Основен API пристап",
            "До 5 членови на тим"
        ],
        "limits": {
            "rag_queries_per_day": -1,  # unlimited
            "saved_alerts": -1,  # unlimited
            "export_results": True,
            "doc_extractions_per_day": -1,
            "competitor_alerts": -1,
            "ai_summary": True,
            "risk_analysis": True,
            "api_access": True
        }
    },
    "enterprise": {
        "name": "Претпријатие",
        "price_mkd": 0,  # Custom pricing
        "price_eur": 0,
        "stripe_price_id": None,
        "features": [
            "Неограничен пристап",
            "Полн API пристап",
            "Посветен менаџер",
            "SLA гаранција"
        ],
        "limits": {
            "rag_queries_per_day": -1,
            "saved_alerts": -1,
            "export_results": True,
            "doc_extractions_per_day": -1,
            "competitor_alerts": -1,
            "ai_summary": True,
            "risk_analysis": True,
            "api_access": True
        }
    }
}


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class CheckoutRequest(BaseModel):
    tier: str
    interval: str = "monthly"  # monthly or yearly


class UpgradeRequest(BaseModel):
    new_tier: str
    interval: str = "monthly"  # monthly or yearly


class LimitCheckRequest(BaseModel):
    action_type: str  # rag_query, export, alert, api_call


# ============================================================================
# FRAUD PREVENTION
# ============================================================================

class FraudDetector:
    """Fraud detection for checkout and payment operations"""

    def __init__(self):
        self.suspicious_ips: Dict[str, list] = defaultdict(list)
        self.suspicious_emails: Dict[str, list] = defaultdict(list)
        self.suspicious_cards: Dict[str, list] = defaultdict(list)

    async def check_fraud_indicators(
        self,
        db: AsyncSession,
        user: User,
        ip_address: str
    ) -> Dict[str, Any]:
        """
        Check for fraud indicators before allowing checkout

        Returns:
            Dict with is_suspicious flag and reasons
        """
        reasons = []
        risk_score = 0

        # Check 1: Multiple failed payment attempts
        failed_payments = await self._check_failed_payments(db, user.user_id)
        if failed_payments > 3:
            reasons.append("Multiple failed payment attempts")
            risk_score += 30

        # Check 2: Account age (newly created accounts are riskier)
        account_age_hours = (datetime.utcnow() - user.created_at).total_seconds() / 3600
        if account_age_hours < 1:
            reasons.append("Account created less than 1 hour ago")
            risk_score += 40
        elif account_age_hours < 24:
            reasons.append("Account less than 24 hours old")
            risk_score += 20

        # Check 3: Email verification status
        if not user.email_verified:
            reasons.append("Email not verified")
            risk_score += 25

        # Check 4: Multiple checkouts from same IP
        ip_checkout_count = await self._check_ip_checkout_frequency(db, ip_address)
        if ip_checkout_count > 5:
            reasons.append("Multiple checkout attempts from this IP")
            risk_score += 35

        # Check 5: Rapid subscription changes
        subscription_changes = await self._check_subscription_changes(db, user.user_id)
        if subscription_changes > 3:
            reasons.append("Multiple subscription changes")
            risk_score += 25

        # Check 6: Disposable email detection
        if self._is_disposable_email(user.email):
            reasons.append("Disposable email address detected")
            risk_score += 50

        is_suspicious = risk_score >= 50

        return {
            "is_suspicious": is_suspicious,
            "risk_score": risk_score,
            "reasons": reasons,
            "action": "block" if risk_score >= 80 else "review" if is_suspicious else "allow"
        }

    async def _check_failed_payments(self, db: AsyncSession, user_id) -> int:
        """Count failed payment attempts in last 7 days"""
        week_ago = datetime.utcnow() - timedelta(days=7)
        result = await db.execute(
            select(func.count(AuditLog.audit_id))
            .where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.action == "payment_failed",
                    AuditLog.created_at >= week_ago
                )
            )
        )
        return result.scalar() or 0

    async def _check_ip_checkout_frequency(self, db: AsyncSession, ip_address: str) -> int:
        """Count checkout attempts from IP in last hour"""
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        result = await db.execute(
            select(func.count(AuditLog.audit_id))
            .where(
                and_(
                    AuditLog.ip_address == ip_address,
                    AuditLog.action == "checkout_created",
                    AuditLog.created_at >= hour_ago
                )
            )
        )
        return result.scalar() or 0

    async def _check_subscription_changes(self, db: AsyncSession, user_id) -> int:
        """Count subscription changes in last 30 days"""
        month_ago = datetime.utcnow() - timedelta(days=30)
        result = await db.execute(
            select(func.count(AuditLog.audit_id))
            .where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.action.in_(["subscription_created", "subscription_cancelled"]),
                    AuditLog.created_at >= month_ago
                )
            )
        )
        return result.scalar() or 0

    def _is_disposable_email(self, email: str) -> bool:
        """Check if email is from a disposable email service"""
        disposable_domains = [
            "tempmail.com", "10minutemail.com", "guerrillamail.com",
            "mailinator.com", "throwaway.email", "temp-mail.org",
            "fakeinbox.com", "getnada.com", "maildrop.cc"
        ]
        domain = email.split("@")[-1].lower()
        return domain in disposable_domains


fraud_detector = FraudDetector()


# ============================================================================
# RATE LIMITING
# ============================================================================

class CheckoutRateLimiter:
    """Rate limiter for checkout creation"""

    def __init__(self):
        self.attempts: Dict[str, list] = defaultdict(list)

    def check_rate_limit(
        self,
        user_id: str,
        limit: int = 5,
        window_seconds: int = 3600
    ) -> bool:
        """Check if user has exceeded checkout rate limit"""
        now = time()
        attempts = self.attempts[user_id]

        # Remove old attempts outside window
        attempts[:] = [t for t in attempts if now - t < window_seconds]

        # Check if limit exceeded
        if len(attempts) >= limit:
            return False

        # Add current attempt
        attempts.append(now)
        return True


checkout_rate_limiter = CheckoutRateLimiter()


class UsageRateLimiter:
    """Rate limiter for AI/RAG queries"""

    def __init__(self):
        self.query_attempts: Dict[str, list] = defaultdict(list)

    def check_query_rate_limit(
        self,
        user_id: str,
        limit: int = 10,
        window_seconds: int = 60
    ) -> bool:
        """Check if user has exceeded query rate limit (queries per minute)"""
        now = time()
        attempts = self.query_attempts[user_id]

        # Remove old attempts outside window
        attempts[:] = [t for t in attempts if now - t < window_seconds]

        # Check if limit exceeded
        if len(attempts) >= limit:
            return False

        # Add current attempt
        attempts.append(now)
        return True


usage_rate_limiter = UsageRateLimiter()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def get_user_subscription(db: AsyncSession, user_id: str) -> Optional[Subscription]:
    """Get active subscription for user"""
    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.user_id == user_id,
                Subscription.status.in_(["active", "trialing"])
            )
        )
        .order_by(Subscription.created_at.desc())
    )
    return result.scalar_one_or_none()


async def get_usage_stats(db: AsyncSession, user_id: str, period_start: datetime) -> Dict[str, int]:
    """Get usage statistics for current billing period"""
    result = await db.execute(
        select(UsageTracking.action_type)
        .where(
            and_(
                UsageTracking.user_id == user_id,
                UsageTracking.timestamp >= period_start
            )
        )
    )
    action_types = result.scalars().all()

    stats = {
        "rag_queries": 0,
        "exports": 0,
        "api_calls": 0,
        "alerts": 0,
        "total": len(action_types)
    }

    for action_type in action_types:
        if action_type == "rag_query":
            stats["rag_queries"] += 1
        elif action_type == "export":
            stats["exports"] += 1
        elif action_type == "api_call":
            stats["api_calls"] += 1
        elif action_type == "alert":
            stats["alerts"] += 1

    return stats


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


async def check_trial_eligibility(db: AsyncSession, user: User) -> bool:
    """Check if user is eligible for free trial"""
    # Check if user has ever had a paid subscription
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.user_id)
    )
    past_subscriptions = result.scalars().all()

    # If user has any past subscriptions, no trial
    if past_subscriptions:
        return False

    # Check if account is too old (trial only for new users)
    account_age_days = (datetime.utcnow() - user.created_at).days
    if account_age_days > 30:
        return False

    return True


async def is_in_trial_period(subscription: Subscription) -> bool:
    """Check if subscription is in trial period"""
    if not subscription or subscription.status != "trialing":
        return False

    # Check if still within 14-day trial
    if subscription.current_period_start:
        trial_end = subscription.current_period_start + timedelta(days=FREE_TRIAL_DAYS)
        return datetime.utcnow() < trial_end

    return False


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Stripe webhook signature"""
    if not STRIPE_WEBHOOK_SECRET:
        return True  # Skip verification in development

    try:
        stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
        return True
    except ValueError:
        return False
    except stripe.error.SignatureVerificationError:
        return False


# ============================================================================
# PLAN ENDPOINTS
# ============================================================================

@router.get("/plans")
async def get_subscription_plans():
    """
    Get all available subscription plans

    Returns:
        - List of plans with pricing and features
        - No authentication required

    Response: 200 OK
    """
    return {
        "plans": [
            {
                "tier": tier,
                **plan_data
            }
            for tier, plan_data in SUBSCRIPTION_PLANS.items()
        ],
        "trial_days": FREE_TRIAL_DAYS
    }


# ============================================================================
# SUBSCRIPTION STATUS ENDPOINTS
# ============================================================================

@router.get("/status")
async def get_billing_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive billing status for current user

    Security:
        - Requires authentication

    Returns:
        - Subscription details
        - Trial status with credits
        - Usage statistics
        - Payment status

    Response: 200 OK
    """
    # Get active subscription
    subscription = await get_user_subscription(db, str(current_user.user_id))

    # Determine billing period
    if subscription and subscription.current_period_start:
        period_start = subscription.current_period_start
        period_end = subscription.current_period_end
    else:
        # For free tier, use current month
        period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = period_start.month % 12 + 1
        year = period_start.year + (1 if next_month == 1 else 0)
        period_end = period_start.replace(month=next_month, year=year)

    # Get usage stats
    usage = await get_usage_stats(db, str(current_user.user_id), period_start)

    # Check trial status from users table (new trial system)
    tier = current_user.subscription_tier or "free"
    in_trial = False
    trial_days_remaining = 0
    trial_ends_at = None
    trial_credits = {}

    # Check if user is in active trial (from users table)
    if hasattr(current_user, 'trial_ends_at') and current_user.trial_ends_at:
        now = datetime.utcnow()
        if current_user.trial_ends_at > now:
            in_trial = True
            trial_days_remaining = (current_user.trial_ends_at - now).days
            trial_ends_at = current_user.trial_ends_at.isoformat()
            tier = "trial"  # Override tier if in trial

            # Get trial credits
            from sqlalchemy import text
            credits_result = await db.execute(
                text("""
                    SELECT credit_type, total_credits, used_credits
                    FROM trial_credits
                    WHERE user_id = :user_id AND expires_at > NOW()
                """),
                {"user_id": str(current_user.user_id)}
            )
            for row in credits_result:
                trial_credits[row[0]] = {
                    "total": row[1],
                    "used": row[2],
                    "remaining": row[1] - row[2]
                }

    # Get plan details
    plan = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS.get("free", {}))
    limits = plan.get("limits", {})

    # Check trial eligibility
    trial_eligible = await check_trial_eligibility(db, current_user)

    # For trial users, set daily limit based on credits
    daily_queries_limit = limits.get("rag_queries_per_day", 3)
    daily_queries_used = usage.get("rag_queries", 0)

    # If in trial, use credit-based limits
    if in_trial and trial_credits.get("ai_messages"):
        ai_credits = trial_credits["ai_messages"]
        daily_queries_limit = ai_credits["total"]
        daily_queries_used = ai_credits["used"]

    return {
        "tier": tier,
        "status": "trialing" if in_trial else (subscription.status if subscription else "free"),
        "plan": plan,
        "trial": {
            "eligible": trial_eligible,
            "active": in_trial,
            "days_remaining": trial_days_remaining,
            "ends_at": trial_ends_at,
            "credits": trial_credits if in_trial else None
        },
        "billing_period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat() if period_end else None
        },
        "usage": usage,
        "limits": limits,
        "daily_queries_used": daily_queries_used,
        "daily_queries_limit": daily_queries_limit,
        "is_blocked": daily_queries_used >= daily_queries_limit if daily_queries_limit > 0 else False,
        "subscription_id": str(subscription.subscription_id) if subscription else None,
        "cancel_at_period_end": subscription.cancel_at_period_end if subscription else False,
        "stripe_customer_id": current_user.stripe_customer_id
    }


# ============================================================================
# CHECKOUT ENDPOINTS
# ============================================================================

@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def create_checkout_session(
    checkout_data: CheckoutRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create Stripe checkout session for subscription with fraud prevention

    Security:
        - Requires authentication
        - Rate limited: 5 attempts per hour per user
        - Fraud detection checks

    Args:
        - tier: Subscription tier (starter, professional, enterprise)
        - interval: Billing interval (monthly, yearly)

    Returns:
        - Stripe checkout session URL

    Response: 201 Created, 400 Bad Request, 403 Forbidden, 409 Conflict, 429 Too Many Requests
    """
    tier = checkout_data.tier
    interval = checkout_data.interval
    user_id_str = str(current_user.user_id)
    ip_address = request.client.host if request.client else "unknown"

    # Rate limiting
    if not checkout_rate_limiter.check_rate_limit(user_id_str, limit=5, window_seconds=3600):
        await log_audit(
            db, user_id_str, "checkout_rate_limited",
            {"tier": tier, "interval": interval}, ip_address
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many checkout attempts. Please try again later."
        )

    # Fraud prevention checks
    fraud_check = await fraud_detector.check_fraud_indicators(db, current_user, ip_address)

    if fraud_check["is_suspicious"]:
        await log_audit(
            db, user_id_str, "checkout_fraud_detected",
            {
                "tier": tier,
                "risk_score": fraud_check["risk_score"],
                "reasons": fraud_check["reasons"]
            },
            ip_address
        )

        if fraud_check["action"] == "block":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Checkout blocked due to security concerns. Please contact support."
            )

    # Validate tier
    if tier not in ["starter", "professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription tier. Choose 'starter', 'professional', or 'enterprise'."
        )

    # Validate interval
    if interval not in ["monthly", "yearly"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid billing interval. Choose 'monthly' or 'yearly'."
        )

    # Check if user already has active subscription
    existing_subscription = await get_user_subscription(db, user_id_str)
    if existing_subscription and existing_subscription.tier == tier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have an active {tier} subscription."
        )

    # Get plan details
    plan = SUBSCRIPTION_PLANS.get(tier)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan"
        )

    # Check trial eligibility
    trial_eligible = await check_trial_eligibility(db, current_user)

    try:
        # Use billing service to create checkout session
        success_url = f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{FRONTEND_URL}/billing/cancel"

        # Create checkout session with trial if eligible
        checkout_session = await billing_service.create_checkout_session(
            user_id=user_id_str,
            email=current_user.email,
            tier=tier,
            interval=interval,
            success_url=success_url,
            cancel_url=cancel_url
        )

        # If trial eligible, add trial to the session
        if trial_eligible and checkout_session.get("session_id"):
            # Update Stripe session to include trial
            try:
                stripe.checkout.Session.modify(
                    checkout_session["session_id"],
                    subscription_data={
                        "trial_period_days": FREE_TRIAL_DAYS,
                        "metadata": {
                            "user_id": user_id_str,
                            "tier": tier,
                            "trial": "true"
                        }
                    }
                )
            except Exception as e:
                logger.warning(f"Could not add trial to session: {str(e)}")

    except Exception as e:
        logger.error(f"Checkout creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create checkout session: {str(e)}"
        )

    # Log audit
    await log_audit(
        db, user_id_str, "checkout_created",
        {
            "tier": tier,
            "interval": interval,
            "session_id": checkout_session.get("session_id"),
            "trial_eligible": trial_eligible,
            "fraud_score": fraud_check.get("risk_score", 0)
        },
        ip_address
    )

    return {
        "checkout_url": checkout_session.get("url"),
        "session_id": checkout_session.get("session_id"),
        "trial_eligible": trial_eligible,
        "trial_days": FREE_TRIAL_DAYS if trial_eligible else 0
    }


# ============================================================================
# CUSTOMER PORTAL ENDPOINTS
# ============================================================================

@router.post("/portal")
async def create_portal_session(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create Stripe customer portal session

    Security:
        - Requires authentication

    Returns:
        - Stripe customer portal URL for managing subscription

    Response: 200 OK, 400 Bad Request
    """
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer found. Please subscribe first."
        )

    try:
        return_url = f"{FRONTEND_URL}/billing"
        portal_session = await billing_service.create_billing_portal_session(
            customer_id=current_user.stripe_customer_id,
            return_url=return_url
        )

        return {
            "portal_url": portal_session.get("url")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create portal session: {str(e)}"
        )


# ============================================================================
# CANCELLATION ENDPOINTS
# ============================================================================

@router.post("/cancel")
async def cancel_subscription(
    immediate: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel user subscription

    Security:
        - Requires authentication
        - Users can only cancel their own subscription

    Args:
        - immediate: Cancel immediately vs. at period end (default: False)

    Returns:
        - Cancellation confirmation

    Response: 200 OK, 400 Bad Request, 404 Not Found
    """
    # Get active subscription
    subscription = await get_user_subscription(db, str(current_user.user_id))

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found."
        )

    if not subscription.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription configuration."
        )

    try:
        # Use billing service to cancel
        cancellation = await billing_service.cancel_subscription(
            subscription_id=subscription.stripe_subscription_id,
            at_period_end=not immediate
        )

        cancellation_type = "immediate" if immediate else "at_period_end"

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel subscription: {str(e)}"
        )

    # Update local subscription
    update_values = {
        "cancel_at_period_end": True if not immediate else False,
        "cancelled_at": datetime.utcnow()
    }
    if immediate:
        update_values["status"] = "canceled"

    await db.execute(
        update(Subscription)
        .where(Subscription.subscription_id == subscription.subscription_id)
        .values(**update_values)
    )

    # If immediate, downgrade user
    if immediate:
        await db.execute(
            update(User)
            .where(User.user_id == current_user.user_id)
            .values(subscription_tier="free")
        )

    await db.commit()

    # Log audit
    await log_audit(
        db, str(current_user.user_id), "subscription_cancel_requested",
        {"cancellation_type": cancellation_type, "tier": subscription.tier},
        None
    )

    return {
        "message": "Subscription cancelled successfully",
        "cancellation_type": cancellation_type,
        "access_until": subscription.current_period_end.isoformat() if subscription.current_period_end and not immediate else None
    }


@router.post("/upgrade")
async def upgrade_subscription(
    upgrade_data: UpgradeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upgrade or downgrade user subscription to a new tier

    Security:
        - Requires authentication
        - Users can only upgrade their own subscription

    Args:
        - new_tier: New subscription tier (starter, professional, enterprise)
        - interval: Billing interval (monthly, yearly)

    Returns:
        - Upgrade confirmation with proration details

    Response: 200 OK, 400 Bad Request, 404 Not Found
    """
    new_tier = upgrade_data.new_tier
    interval = upgrade_data.interval

    # Validate new tier
    if new_tier not in ["starter", "professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription tier. Choose 'starter', 'professional', or 'enterprise'."
        )

    # Validate interval
    if interval not in ["monthly", "yearly"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid billing interval. Choose 'monthly' or 'yearly'."
        )

    # Get active subscription
    subscription = await get_user_subscription(db, str(current_user.user_id))

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found. Please subscribe first."
        )

    if not subscription.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription configuration."
        )

    # Check if already on this tier
    if subscription.tier == new_tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You are already subscribed to the {new_tier} plan."
        )

    # Get new price ID
    new_price_id = SUBSCRIPTION_PLANS.get(new_tier, {}).get("stripe_price_id")
    if not new_price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Price ID not configured for {new_tier} plan."
        )

    try:
        # Use billing service to update subscription
        update_result = await billing_service.update_subscription(
            subscription_id=subscription.stripe_subscription_id,
            new_price_id=new_price_id
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to upgrade subscription: {str(e)}"
        )

    # Update local subscription
    await db.execute(
        update(Subscription)
        .where(Subscription.subscription_id == subscription.subscription_id)
        .values(
            tier=new_tier,
            updated_at=datetime.utcnow()
        )
    )

    # Update user tier
    await db.execute(
        update(User)
        .where(User.user_id == current_user.user_id)
        .values(subscription_tier=new_tier)
    )

    await db.commit()

    # Log audit
    await log_audit(
        db, str(current_user.user_id), "subscription_upgraded",
        {
            "old_tier": subscription.tier,
            "new_tier": new_tier,
            "interval": interval
        },
        None
    )

    # Determine if upgrade or downgrade
    tier_hierarchy = ["starter", "professional", "enterprise"]
    old_index = tier_hierarchy.index(subscription.tier) if subscription.tier in tier_hierarchy else -1
    new_index = tier_hierarchy.index(new_tier) if new_tier in tier_hierarchy else -1
    change_type = "upgrade" if new_index > old_index else "downgrade" if new_index < old_index else "change"

    return {
        "message": f"Subscription {change_type}d successfully",
        "old_tier": subscription.tier,
        "new_tier": new_tier,
        "change_type": change_type,
        "prorated": True,
        "next_billing_date": subscription.current_period_end.isoformat() if subscription.current_period_end else None
    }


# ============================================================================
# USAGE ENDPOINTS
# ============================================================================

@router.get("/usage")
async def get_usage_statistics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get usage statistics for current billing period

    Security:
        - Requires authentication
        - Users can only access their own usage stats

    Returns:
        - Usage statistics by action type
        - Current limits based on subscription tier
        - Percentage of quota used
        - Trial status

    Response: 200 OK
    """
    # Get active subscription
    subscription = await get_user_subscription(db, str(current_user.user_id))

    # Determine billing period start
    if subscription and subscription.current_period_start:
        period_start = subscription.current_period_start
    else:
        # For free tier, use current month
        period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get usage stats
    usage = await get_usage_stats(db, str(current_user.user_id), period_start)

    # Get current plan limits
    tier = subscription.tier if subscription else "free"
    plan = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS["free"])
    limits = plan.get("limits", {})

    # Calculate quotas
    rag_limit = limits.get("rag_queries_per_month", 5)
    rag_used = usage["rag_queries"]
    rag_remaining = max(0, rag_limit - rag_used) if rag_limit != -1 else -1
    rag_percentage = (rag_used / rag_limit * 100) if rag_limit > 0 else 0

    # Check trial status
    in_trial = await is_in_trial_period(subscription) if subscription else False
    trial_days_remaining = 0
    if in_trial and subscription and subscription.current_period_start:
        trial_end = subscription.current_period_start + timedelta(days=FREE_TRIAL_DAYS)
        trial_days_remaining = (trial_end - datetime.utcnow()).days

    return {
        "tier": tier,
        "period_start": period_start.isoformat(),
        "period_end": subscription.current_period_end.isoformat() if subscription and subscription.current_period_end else None,
        "trial": {
            "active": in_trial,
            "days_remaining": trial_days_remaining
        },
        "usage": usage,
        "limits": {
            "rag_queries": {
                "limit": rag_limit,
                "used": rag_used,
                "remaining": rag_remaining,
                "percentage": round(rag_percentage, 2),
                "unlimited": rag_limit == -1
            },
            "export_results": limits.get("export_results", False),
            "api_access": limits.get("api_access", False),
            "saved_alerts": {
                "limit": limits.get("saved_alerts", 1),
                "unlimited": limits.get("saved_alerts", 1) == -1
            }
        },
        "warnings": {
            "approaching_limit": rag_percentage >= 80 and rag_limit != -1,
            "limit_reached": rag_used >= rag_limit and rag_limit != -1
        }
    }


@router.post("/check-limit")
async def check_usage_limit(
    limit_check: LimitCheckRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if user can perform an action based on their subscription limits
    Used before AI queries, exports, etc.

    Security:
        - Requires authentication
        - Rate limited for AI queries

    Args:
        - action_type: Type of action (rag_query, export, alert, api_call)

    Returns:
        - allowed: Boolean indicating if action is allowed
        - reason: String explaining why if not allowed
        - usage: Current usage stats

    Response: 200 OK
    """
    action_type = limit_check.action_type
    user_id_str = str(current_user.user_id)

    # Get active subscription
    subscription = await get_user_subscription(db, user_id_str)

    # Determine billing period
    if subscription and subscription.current_period_start:
        period_start = subscription.current_period_start
    else:
        period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get current usage
    usage = await get_usage_stats(db, user_id_str, period_start)

    # Get plan limits
    tier = subscription.tier if subscription else "free"
    plan = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS["free"])
    limits = plan.get("limits", {})

    allowed = True
    reason = None

    # Check specific action type
    if action_type == "rag_query":
        # Check rate limiting (10 queries per minute)
        if not usage_rate_limiter.check_query_rate_limit(user_id_str, limit=10, window_seconds=60):
            allowed = False
            reason = "Rate limit exceeded. Maximum 10 queries per minute."
        else:
            # Check monthly limit
            rag_limit = limits.get("rag_queries_per_month", 5)
            if rag_limit != -1 and usage["rag_queries"] >= rag_limit:
                allowed = False
                reason = f"Monthly RAG query limit reached ({rag_limit} queries). Upgrade your plan for more queries."

    elif action_type == "export":
        if not limits.get("export_results", False):
            allowed = False
            reason = "Export feature not available in your plan. Upgrade to access exports."

    elif action_type == "api_call":
        if not limits.get("api_access", False):
            allowed = False
            reason = "API access not available in your plan. Upgrade to Enterprise for API access."

    elif action_type == "alert":
        alerts_limit = limits.get("alerts_per_day", 0)
        # For alerts, check daily usage
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_usage = await get_usage_stats(db, user_id_str, today_start)

        if alerts_limit != -1 and today_usage["alerts"] >= alerts_limit:
            allowed = False
            reason = f"Daily alert limit reached ({alerts_limit} alerts). Upgrade your plan for more alerts."

    # Check trial status
    in_trial = await is_in_trial_period(subscription) if subscription else False

    # If allowed, record the usage
    if allowed and action_type in ["rag_query", "export", "api_call", "alert"]:
        tracking = UsageTracking(
            user_id=current_user.user_id,
            action_type=action_type
        )
        db.add(tracking)
        await db.commit()

    return {
        "allowed": allowed,
        "reason": reason,
        "action_type": action_type,
        "usage": {
            "rag_queries": usage["rag_queries"],
            "limit": limits.get("rag_queries_per_month", 5),
            "remaining": max(0, limits.get("rag_queries_per_month", 5) - usage["rag_queries"]) if limits.get("rag_queries_per_month", 5) != -1 else -1
        },
        "tier": tier,
        "trial": {
            "active": in_trial
        },
        "upgrade_url": f"{FRONTEND_URL}/billing/plans" if not allowed else None
    }


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@router.post("/webhook")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhook events

    Security:
        - Webhook signature verification
        - No authentication required (verified via signature)

    Events handled:
        - customer.subscription.created
        - customer.subscription.updated
        - customer.subscription.deleted
        - customer.subscription.trial_will_end
        - invoice.payment_succeeded
        - invoice.payment_failed

    Response: 200 OK, 400 Bad Request
    """
    # Read payload once - body can only be read once!
    payload = await request.body()

    # Verify webhook signature and construct event
    if STRIPE_WEBHOOK_SECRET and stripe_signature:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload"
            )
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
    else:
        # Development mode - parse without verification
        try:
            event_data = json.loads(payload.decode('utf-8'))
            event = stripe.Event.construct_from(event_data, stripe.api_key)
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload"
            )

    logger.info(f"Received Stripe webhook: {event.type}")

    try:
        # Handle different event types
        if event.type == "customer.subscription.created":
            await handle_subscription_created(db, event.data.object)
        elif event.type == "customer.subscription.updated":
            await handle_subscription_updated(db, event.data.object)
        elif event.type == "customer.subscription.deleted":
            await handle_subscription_deleted(db, event.data.object)
        elif event.type == "customer.subscription.trial_will_end":
            await handle_trial_will_end(db, event.data.object)
        elif event.type == "invoice.payment_succeeded":
            await handle_payment_succeeded(db, event.data.object)
        elif event.type == "invoice.payment_failed":
            await handle_payment_failed(db, event.data.object)
        else:
            logger.info(f"Unhandled webhook event type: {event.type}")

        logger.info(f"Successfully processed webhook: {event.type}")
        return {"status": "success", "event_type": event.type}

    except Exception as e:
        logger.error(f"Error processing webhook {event.type}: {e}", exc_info=True)
        # Return 200 to prevent Stripe from retrying - log the error for investigation
        return {"status": "error", "event_type": event.type, "error": str(e)}


async def handle_subscription_created(db: AsyncSession, subscription_obj: Dict[str, Any]):
    """Handle subscription created event"""
    customer_id = subscription_obj["customer"]
    subscription_id = subscription_obj["id"]

    # Find user by Stripe customer ID
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"User not found for customer {customer_id}")
        return

    # Determine tier from subscription metadata
    tier = subscription_obj.get("metadata", {}).get("tier", "starter")

    # Determine if trial
    status = subscription_obj["status"]

    # Create subscription record
    new_subscription = Subscription(
        user_id=user.user_id,
        stripe_subscription_id=subscription_id,
        stripe_customer_id=customer_id,
        tier=tier,
        status=status,
        current_period_start=datetime.fromtimestamp(subscription_obj["current_period_start"]),
        current_period_end=datetime.fromtimestamp(subscription_obj["current_period_end"]),
        cancel_at_period_end=subscription_obj.get("cancel_at_period_end", False)
    )
    db.add(new_subscription)

    # Update user subscription tier
    await db.execute(
        update(User)
        .where(User.user_id == user.user_id)
        .values(subscription_tier=tier)
    )

    await db.commit()

    # Log audit
    await log_audit(
        db, str(user.user_id), "subscription_created",
        {"tier": tier, "subscription_id": subscription_id, "status": status},
        None
    )


async def handle_subscription_updated(db: AsyncSession, subscription_obj: Dict[str, Any]):
    """Handle subscription updated event"""
    subscription_id = subscription_obj["id"]

    # Find subscription
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning(f"Subscription not found: {subscription_id}")
        return

    # Update subscription
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .values(
            status=subscription_obj["status"],
            current_period_start=datetime.fromtimestamp(subscription_obj["current_period_start"]),
            current_period_end=datetime.fromtimestamp(subscription_obj["current_period_end"]),
            cancel_at_period_end=subscription_obj.get("cancel_at_period_end", False),
            cancelled_at=datetime.fromtimestamp(subscription_obj["canceled_at"]) if subscription_obj.get("canceled_at") else None
        )
    )

    # Update user tier if subscription is active
    if subscription_obj["status"] in ["active", "trialing"]:
        await db.execute(
            update(User)
            .where(User.user_id == subscription.user_id)
            .values(subscription_tier=subscription.tier)
        )

    await db.commit()


async def handle_subscription_deleted(db: AsyncSession, subscription_obj: Dict[str, Any]):
    """Handle subscription deleted/cancelled event"""
    subscription_id = subscription_obj["id"]

    # Find subscription
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return

    # Update subscription status
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .values(
            status="canceled",
            cancelled_at=datetime.utcnow()
        )
    )

    # Downgrade user to free tier
    await db.execute(
        update(User)
        .where(User.user_id == subscription.user_id)
        .values(subscription_tier="free")
    )

    await db.commit()

    # Log audit
    await log_audit(
        db, str(subscription.user_id), "subscription_cancelled",
        {"subscription_id": subscription_id},
        None
    )


async def handle_trial_will_end(db: AsyncSession, subscription_obj: Dict[str, Any]):
    """Handle trial ending soon (3 days before)"""
    subscription_id = subscription_obj["id"]

    # Find subscription
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        # Log for notification service to pick up
        await log_audit(
            db, str(subscription.user_id), "trial_ending_soon",
            {"subscription_id": subscription_id, "tier": subscription.tier},
            None
        )


async def handle_payment_succeeded(db: AsyncSession, invoice_obj: Dict[str, Any]):
    """Handle successful payment"""
    customer_id = invoice_obj["customer"]
    subscription_id = invoice_obj.get("subscription")

    if not subscription_id:
        return

    # Log audit
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()

    if user:
        await log_audit(
            db, str(user.user_id), "payment_succeeded",
            {
                "invoice_id": invoice_obj["id"],
                "amount": invoice_obj["amount_paid"] / 100,
                "currency": invoice_obj["currency"]
            },
            None
        )


async def handle_payment_failed(db: AsyncSession, invoice_obj: Dict[str, Any]):
    """Handle failed payment"""
    customer_id = invoice_obj["customer"]

    # Log audit
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()

    if user:
        await log_audit(
            db, str(user.user_id), "payment_failed",
            {
                "invoice_id": invoice_obj["id"],
                "amount": invoice_obj["amount_due"] / 100,
                "currency": invoice_obj["currency"]
            },
            None
        )


# ============================================================================
# INVOICE ENDPOINTS
# ============================================================================

@router.get("/invoices")
async def get_user_invoices(
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's invoice history

    Security:
        - Requires authentication
        - Users can only access their own invoices

    Args:
        - limit: Number of invoices to retrieve (default: 10, max: 100)

    Returns:
        - List of invoices with payment details

    Response: 200 OK, 400 Bad Request
    """
    if not current_user.stripe_customer_id:
        return {
            "invoices": [],
            "total": 0
        }

    if limit > 100:
        limit = 100

    try:
        invoices = stripe.Invoice.list(
            customer=current_user.stripe_customer_id,
            limit=limit
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to retrieve invoices: {str(e)}"
        )

    return {
        "invoices": [
            {
                "invoice_id": invoice.id,
                "amount": invoice.amount_paid / 100,
                "currency": invoice.currency.upper(),
                "status": invoice.status,
                "paid": invoice.paid,
                "created": datetime.fromtimestamp(invoice.created).isoformat(),
                "period_start": datetime.fromtimestamp(invoice.period_start).isoformat() if invoice.period_start else None,
                "period_end": datetime.fromtimestamp(invoice.period_end).isoformat() if invoice.period_end else None,
                "invoice_pdf": invoice.invoice_pdf,
                "hosted_invoice_url": invoice.hosted_invoice_url
            }
            for invoice in invoices.data
        ],
        "total": len(invoices.data)
    }


# ============================================================================
# PAYMENT METHOD ENDPOINTS
# ============================================================================

@router.get("/payment-methods")
async def get_payment_methods(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's saved payment methods

    Security:
        - Requires authentication
        - Users can only access their own payment methods

    Returns:
        - List of saved payment methods

    Response: 200 OK, 400 Bad Request
    """
    if not current_user.stripe_customer_id:
        return {
            "payment_methods": [],
            "total": 0
        }

    try:
        payment_methods = stripe.PaymentMethod.list(
            customer=current_user.stripe_customer_id,
            type="card"
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to retrieve payment methods: {str(e)}"
        )

    return {
        "payment_methods": [
            {
                "payment_method_id": pm.id,
                "type": pm.type,
                "card": {
                    "brand": pm.card.brand,
                    "last4": pm.card.last4,
                    "exp_month": pm.card.exp_month,
                    "exp_year": pm.card.exp_year
                },
                "created": datetime.fromtimestamp(pm.created).isoformat()
            }
            for pm in payment_methods.data
        ],
        "total": len(payment_methods.data)
    }


# ============================================================================
# CREDIT CONSUMPTION ENDPOINTS
# ============================================================================

class UseCreditsRequest(BaseModel):
    credit_type: str  # ai_messages, doc_extractions, exports, competitor_alerts


@router.post("/use-credit")
async def use_trial_credit(
    request_data: UseCreditsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Consume a trial credit for a specific action.
    Called by AI endpoints before performing the action.

    Credit types:
        - ai_messages: AI chat, tender summary, AI products extraction
        - doc_extractions: Document text extraction
        - exports: CSV/PDF exports
        - competitor_alerts: Setting up competitor tracking

    Returns:
        - allowed: Whether the action is allowed
        - remaining: Credits remaining after this action
        - upgrade_required: True if user needs to upgrade
    """
    from sqlalchemy import text

    user_id = str(current_user.user_id)
    tier = current_user.subscription_tier or "free"
    credit_type = request_data.credit_type

    # Check if user is in trial
    in_trial = False
    if hasattr(current_user, 'trial_ends_at') and current_user.trial_ends_at:
        if current_user.trial_ends_at > datetime.utcnow():
            in_trial = True

    if in_trial:
        # Check and consume trial credit
        result = await db.execute(
            text("""
                SELECT credit_id, total_credits, used_credits
                FROM trial_credits
                WHERE user_id = :user_id
                  AND credit_type = :credit_type
                  AND expires_at > NOW()
                FOR UPDATE
            """),
            {"user_id": user_id, "credit_type": credit_type}
        )
        credit_row = result.fetchone()

        if not credit_row:
            return {
                "allowed": False,
                "remaining": 0,
                "upgrade_required": True,
                "message": "Немате кредити за оваа функција. Надградете го вашиот план."
            }

        credit_id, total, used = credit_row
        remaining = total - used

        if remaining <= 0:
            return {
                "allowed": False,
                "remaining": 0,
                "upgrade_required": True,
                "message": "Ги искористивте сите кредити. Надградете го вашиот план."
            }

        # Consume credit
        await db.execute(
            text("""
                UPDATE trial_credits
                SET used_credits = used_credits + 1, updated_at = NOW()
                WHERE credit_id = :credit_id
            """),
            {"credit_id": credit_id}
        )
        await db.commit()

        return {
            "allowed": True,
            "remaining": remaining - 1,
            "upgrade_required": False,
            "message": None
        }
    else:
        # Non-trial user: check daily limits
        plan = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS.get("free", {}))
        limits = plan.get("limits", {})

        # Map credit type to limit key
        limit_map = {
            "ai_messages": "rag_queries_per_day",
            "doc_extractions": "doc_extractions_per_day",
            "exports": "export_results",  # Boolean
            "competitor_alerts": "competitor_alerts"
        }

        limit_key = limit_map.get(credit_type)
        if not limit_key:
            return {"allowed": True, "remaining": -1, "upgrade_required": False}

        limit_value = limits.get(limit_key, 0)

        # Unlimited
        if limit_value == -1:
            return {"allowed": True, "remaining": -1, "upgrade_required": False}

        # Boolean (like exports)
        if isinstance(limit_value, bool):
            return {
                "allowed": limit_value,
                "remaining": -1 if limit_value else 0,
                "upgrade_required": not limit_value,
                "message": None if limit_value else "Извозот не е достапен на вашиот план."
            }

        # Check daily usage
        period_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        usage = await get_usage_stats(db, user_id, period_start)

        usage_key_map = {
            "ai_messages": "rag_queries",
            "doc_extractions": "doc_extractions",
            "competitor_alerts": "competitor_alerts"
        }
        usage_key = usage_key_map.get(credit_type, "rag_queries")
        current_usage = usage.get(usage_key, 0)

        if current_usage >= limit_value:
            return {
                "allowed": False,
                "remaining": 0,
                "upgrade_required": True,
                "message": f"Дневниот лимит е достигнат ({limit_value}). Надградете за повеќе."
            }

        return {
            "allowed": True,
            "remaining": limit_value - current_usage - 1,
            "upgrade_required": False,
            "message": None
        }


@router.get("/check-feature/{feature}")
async def check_feature_access(
    feature: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if user has access to a specific feature.

    Features:
        - ai_summary: AI tender summary
        - risk_analysis: Corruption/risk analysis
        - export_csv: CSV export
        - export_pdf: PDF export
        - api_access: API access
        - competitor_alerts: Competitor tracking

    Returns:
        - allowed: Whether feature is accessible
        - tier_required: Minimum tier needed
        - upgrade_url: URL to upgrade page
    """
    tier = current_user.subscription_tier or "free"

    # Check trial
    in_trial = False
    if hasattr(current_user, 'trial_ends_at') and current_user.trial_ends_at:
        if current_user.trial_ends_at > datetime.utcnow():
            in_trial = True
            tier = "trial"

    plan = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS.get("free", {}))
    limits = plan.get("limits", {})

    # Feature to limit key mapping
    feature_map = {
        "ai_summary": "ai_summary",
        "risk_analysis": "risk_analysis",
        "export_csv": "export_results",
        "export_pdf": "export_results",
        "api_access": "api_access",
        "competitor_alerts": "competitor_alerts"
    }

    limit_key = feature_map.get(feature, feature)
    allowed = limits.get(limit_key, False)

    # For numeric limits, check if > 0
    if isinstance(allowed, int):
        allowed = allowed != 0

    # Determine minimum tier needed
    tier_required = None
    if not allowed:
        for check_tier in ["start", "pro", "team"]:
            check_plan = SUBSCRIPTION_PLANS.get(check_tier, {})
            check_limits = check_plan.get("limits", {})
            check_value = check_limits.get(limit_key, False)
            if isinstance(check_value, int):
                check_value = check_value != 0
            if check_value:
                tier_required = check_tier
                break

    return {
        "feature": feature,
        "allowed": allowed,
        "current_tier": tier,
        "tier_required": tier_required,
        "upgrade_url": f"/settings#plans" if not allowed else None
    }
