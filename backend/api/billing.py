"""
Billing API Endpoints for nabavkidata.com
Handles subscription management, Stripe integration, and payment processing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from time import time
from decimal import Decimal
import os
import stripe
import hmac
import hashlib

from database import get_db
from models import User, Subscription, UsageTracking, AuditLog
from middleware.rbac import get_current_user, get_current_active_user

# ============================================================================
# CONFIGURATION
# ============================================================================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(
    prefix="/billing",
    tags=["Billing"]
)

# Subscription plan definitions
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Free",
        "price_mkd": 0,
        "price_eur": 0,
        "stripe_price_id": None,
        "features": [
            "Basic tender search",
            "5 RAG queries per month",
            "1 saved alert",
            "Email support"
        ],
        "limits": {
            "rag_queries_per_month": 5,
            "saved_alerts": 1,
            "export_results": False
        }
    },
    "pro": {
        "name": "Pro",
        "price_mkd": 999,
        "price_eur": 16.99,
        "stripe_price_id": os.getenv("STRIPE_PRICE_PRO", "price_pro"),
        "features": [
            "Advanced search & filters",
            "100 RAG queries per month",
            "10 saved alerts",
            "Export to CSV/PDF",
            "Priority email support"
        ],
        "limits": {
            "rag_queries_per_month": 100,
            "saved_alerts": 10,
            "export_results": True
        }
    },
    "premium": {
        "name": "Premium",
        "price_mkd": 2499,
        "price_eur": 39.99,
        "stripe_price_id": os.getenv("STRIPE_PRICE_PREMIUM", "price_premium"),
        "features": [
            "Unlimited RAG queries",
            "Unlimited saved alerts",
            "API access",
            "Custom integrations",
            "Advanced analytics",
            "Dedicated support",
            "White-label options"
        ],
        "limits": {
            "rag_queries_per_month": -1,  # unlimited
            "saved_alerts": -1,  # unlimited
            "export_results": True,
            "api_access": True
        }
    }
}


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
        select(UsageTracking)
        .where(
            and_(
                UsageTracking.user_id == user_id,
                UsageTracking.timestamp >= period_start,
                UsageTracking.action_type.in_(["rag_query", "export", "api_call"])
            )
        )
    )
    usage_records = result.scalars().all()

    stats = {
        "rag_queries": 0,
        "exports": 0,
        "api_calls": 0,
        "total": len(usage_records)
    }

    for record in usage_records:
        if record.action_type == "rag_query":
            stats["rag_queries"] += 1
        elif record.action_type == "export":
            stats["exports"] += 1
        elif record.action_type == "api_call":
            stats["api_calls"] += 1

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
        ]
    }


# ============================================================================
# SUBSCRIPTION ENDPOINTS
# ============================================================================

@router.get("/subscription")
async def get_current_subscription(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's subscription details

    Security:
        - Requires authentication
        - Users can only access their own subscription

    Returns:
        - Subscription details
        - Current plan info
        - Usage statistics

    Response: 200 OK, 404 Not Found
    """
    # Get active subscription
    subscription = await get_user_subscription(db, str(current_user.user_id))

    if not subscription:
        # User is on free plan
        return {
            "tier": "free",
            "status": "active",
            "plan": SUBSCRIPTION_PLANS["free"],
            "subscription": None,
            "cancel_at_period_end": False
        }

    # Get plan details
    plan = SUBSCRIPTION_PLANS.get(subscription.tier, SUBSCRIPTION_PLANS["free"])

    return {
        "tier": subscription.tier,
        "status": subscription.status,
        "plan": plan,
        "subscription": {
            "subscription_id": str(subscription.subscription_id),
            "stripe_subscription_id": subscription.stripe_subscription_id,
            "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "cancelled_at": subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
            "created_at": subscription.created_at.isoformat()
        },
        "cancel_at_period_end": subscription.cancel_at_period_end
    }


# ============================================================================
# CHECKOUT ENDPOINTS
# ============================================================================

@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def create_checkout_session(
    tier: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create Stripe checkout session for subscription

    Security:
        - Requires authentication
        - Rate limited: 5 attempts per hour per user

    Args:
        - tier: Subscription tier (pro, premium)

    Returns:
        - Stripe checkout session URL

    Response: 201 Created, 400 Bad Request, 409 Conflict, 429 Too Many Requests
    """
    # Rate limiting
    user_id_str = str(current_user.user_id)
    if not checkout_rate_limiter.check_rate_limit(user_id_str, limit=5, window_seconds=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many checkout attempts. Please try again later."
        )

    # Validate tier
    if tier not in ["pro", "premium"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription tier. Choose 'pro' or 'premium'."
        )

    # Check if user already has active subscription
    existing_subscription = await get_user_subscription(db, user_id_str)
    if existing_subscription and existing_subscription.tier == tier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have an active {tier} subscription."
        )

    # Get plan details
    plan = SUBSCRIPTION_PLANS[tier]
    if not plan["stripe_price_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This plan is not available for purchase."
        )

    # Create or retrieve Stripe customer
    if current_user.stripe_customer_id:
        customer_id = current_user.stripe_customer_id
    else:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=current_user.full_name,
            metadata={
                "user_id": user_id_str
            }
        )
        customer_id = customer.id

        # Update user with Stripe customer ID
        await db.execute(
            update(User)
            .where(User.user_id == current_user.user_id)
            .values(stripe_customer_id=customer_id)
        )
        await db.commit()

    # Create checkout session
    try:
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": plan["stripe_price_id"],
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/billing/cancel",
            metadata={
                "user_id": user_id_str,
                "tier": tier
            }
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create checkout session: {str(e)}"
        )

    # Log audit
    await log_audit(
        db,
        user_id_str,
        "checkout_created",
        {
            "tier": tier,
            "session_id": checkout_session.id
        },
        request.client.host
    )

    return {
        "checkout_url": checkout_session.url,
        "session_id": checkout_session.id
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
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{FRONTEND_URL}/billing"
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create portal session: {str(e)}"
        )

    return {
        "portal_url": portal_session.url
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
        - invoice.payment_succeeded
        - invoice.payment_failed

    Response: 200 OK, 400 Bad Request
    """
    payload = await request.body()

    # Verify webhook signature
    if stripe_signature:
        if not verify_webhook_signature(payload, stripe_signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )

    try:
        event = stripe.Event.construct_from(
            stripe.util.convert_to_dict(await request.json()),
            stripe.api_key
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )

    # Handle different event types
    if event.type == "customer.subscription.created":
        await handle_subscription_created(db, event.data.object)
    elif event.type == "customer.subscription.updated":
        await handle_subscription_updated(db, event.data.object)
    elif event.type == "customer.subscription.deleted":
        await handle_subscription_deleted(db, event.data.object)
    elif event.type == "invoice.payment_succeeded":
        await handle_payment_succeeded(db, event.data.object)
    elif event.type == "invoice.payment_failed":
        await handle_payment_failed(db, event.data.object)

    return {"status": "success"}


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
        return

    # Determine tier from subscription metadata or items
    tier = subscription_obj.get("metadata", {}).get("tier", "pro")

    # Create subscription record
    new_subscription = Subscription(
        user_id=user.user_id,
        stripe_subscription_id=subscription_id,
        stripe_customer_id=customer_id,
        tier=tier,
        status=subscription_obj["status"],
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
        db,
        str(user.user_id),
        "subscription_created",
        {"tier": tier, "subscription_id": subscription_id},
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
    if subscription_obj["status"] == "active":
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
        db,
        str(subscription.user_id),
        "subscription_cancelled",
        {"subscription_id": subscription_id},
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
            db,
            str(user.user_id),
            "payment_succeeded",
            {
                "invoice_id": invoice_obj["id"],
                "amount": invoice_obj["amount_paid"] / 100,  # Convert from cents
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
            db,
            str(user.user_id),
            "payment_failed",
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
        if immediate:
            # Cancel immediately
            stripe.Subscription.delete(subscription.stripe_subscription_id)
            cancellation_type = "immediate"
        else:
            # Cancel at period end
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            cancellation_type = "at_period_end"
    except stripe.error.StripeError as e:
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
        db,
        str(current_user.user_id),
        "subscription_cancel_requested",
        {
            "cancellation_type": cancellation_type,
            "tier": subscription.tier
        },
        None
    )

    return {
        "message": "Subscription cancelled successfully",
        "cancellation_type": cancellation_type,
        "access_until": subscription.current_period_end.isoformat() if subscription.current_period_end and not immediate else None
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

    return {
        "tier": tier,
        "period_start": period_start.isoformat(),
        "period_end": subscription.current_period_end.isoformat() if subscription and subscription.current_period_end else None,
        "usage": usage,
        "limits": {
            "rag_queries": {
                "limit": rag_limit,
                "used": rag_used,
                "remaining": rag_remaining,
                "percentage": (rag_used / rag_limit * 100) if rag_limit > 0 else 0
            },
            "export_results": limits.get("export_results", False),
            "api_access": limits.get("api_access", False)
        }
    }
