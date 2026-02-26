"""
Stripe Webhook Handler for nabavkidata.com
Handles all Stripe webhook events for subscription management, payments, and billing

Events handled:
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- invoice.payment_succeeded
- invoice.payment_failed
- customer.subscription.trial_will_end

Author: Stripe Integration Team
Created: 2025-11-23
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, text
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
import stripe
import logging
import json

from database import get_db
from models import User, Subscription
from api.clawd_monitor import notify_clawd

# ============================================================================
# CONFIGURATION
# ============================================================================

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Router configuration
router = APIRouter(
    prefix="/stripe",
    tags=["Stripe Webhooks"]
)

# Stripe Price ID to Tier Mapping
PRICE_ID_TO_TIER = {
    # Free tier (no price ID)
    "price_1SWeAqHkVI5icjTlYgQujATs": "free",

    # Starter tier
    "price_1SWeAsHkVI5icjTl9GZ8Ciui": "starter",

    # Professional tier
    "price_1SWeAtHkVI5icjTl8UxSYNYX": "professional",

    # Enterprise tier
    "price_1SWeAvHkVI5icjTlF8eFK8kh": "enterprise",
}

# Tier to Price ID mapping (reverse lookup)
TIER_TO_PRICE_ID = {v: k for k, v in PRICE_ID_TO_TIER.items() if v != "free"}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Stripe webhook signature for security

    Args:
        payload: Raw webhook payload bytes
        signature: Stripe-Signature header value

    Returns:
        bool: True if signature is valid, False otherwise

    Security:
        NEVER accepts webhooks without proper signature verification.
        STRIPE_WEBHOOK_SECRET must be configured in production.
    """
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("SECURITY: STRIPE_WEBHOOK_SECRET not configured - rejecting webhook. "
                    "Set this in production to accept Stripe webhooks.")
        return False  # SECURITY: Never accept unverified webhooks

    try:
        stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
        logger.info("Webhook signature verified successfully")
        return True
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        return False
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        return False


def get_tier_from_subscription(subscription_obj: Dict[str, Any]) -> str:
    """
    Extract subscription tier from Stripe subscription object

    Args:
        subscription_obj: Stripe subscription object

    Returns:
        str: Subscription tier (free, starter, professional, enterprise)
    """
    # First check metadata
    tier = subscription_obj.get("metadata", {}).get("tier")
    if tier:
        logger.info(f"Found tier in metadata: {tier}")
        return tier.lower()

    # Then check subscription items for price ID
    items = subscription_obj.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        if price_id and price_id in PRICE_ID_TO_TIER:
            tier = PRICE_ID_TO_TIER[price_id]
            logger.info(f"Mapped price_id {price_id} to tier: {tier}")
            return tier

    # Default to starter if we can't determine
    logger.warning("Could not determine tier from subscription, defaulting to 'starter'")
    return "starter"


async def get_user_by_customer_id(db: AsyncSession, customer_id: str) -> Optional[User]:
    """
    Get user by Stripe customer ID

    Args:
        db: Database session
        customer_id: Stripe customer ID

    Returns:
        User object or None
    """
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    return result.scalar_one_or_none()


async def get_subscription_by_stripe_id(db: AsyncSession, stripe_subscription_id: str) -> Optional[Subscription]:
    """
    Get subscription by Stripe subscription ID

    Args:
        db: Database session
        stripe_subscription_id: Stripe subscription ID

    Returns:
        Subscription object or None
    """
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
    )
    return result.scalar_one_or_none()


async def update_user_tier(db: AsyncSession, user_id, tier: str):
    """
    Update user's subscription tier in the database

    Args:
        db: Database session
        user_id: User ID (UUID)
        tier: New subscription tier
    """
    await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(subscription_tier=tier)
    )
    logger.info(f"Updated user {user_id} to tier: {tier}")


# ============================================================================
# REFERRAL COMMISSION
# ============================================================================

async def _process_referral_commission(db: AsyncSession, user: User, invoice_obj: Dict[str, Any]):
    """Credit 20% commission to referrer if this user was referred and has an active conversion."""
    try:
        invoice_id = invoice_obj["id"]
        amount_paid_cents = invoice_obj["amount_paid"]  # Already in cents from Stripe
        currency = invoice_obj["currency"].upper()

        if amount_paid_cents <= 0:
            return

        # Check idempotency - was this invoice already processed?
        existing = await db.execute(
            text("SELECT 1 FROM referral_earnings WHERE invoice_id = :inv"),
            {"inv": invoice_id}
        )
        if existing.fetchone():
            return

        # Check if user has an active referral conversion
        conv_result = await db.execute(
            text("""
                SELECT conversion_id, referrer_id
                FROM referral_conversions
                WHERE referred_user_id = :uid AND status = 'active'
            """),
            {"uid": str(user.user_id)}
        )
        conv = conv_result.fetchone()
        if not conv:
            return

        conversion_id, referrer_id = conv[0], conv[1]

        # Calculate 20% commission
        commission_cents = amount_paid_cents * 20 // 100
        if commission_cents <= 0:
            return

        await db.execute(
            text("""
                INSERT INTO referral_earnings
                    (referrer_id, referred_user_id, conversion_id, invoice_id, amount_cents, currency)
                VALUES (:referrer, :referred, :conv, :inv, :amount, :currency)
            """),
            {
                "referrer": str(referrer_id),
                "referred": str(user.user_id),
                "conv": str(conversion_id),
                "inv": invoice_id,
                "amount": commission_cents,
                "currency": currency
            }
        )
        await db.commit()

        logger.info(
            f"Referral commission: {commission_cents} cents {currency} "
            f"credited to {referrer_id} from user {user.user_id} (invoice {invoice_id})"
        )

    except Exception as e:
        logger.error(f"Error processing referral commission: {e}", exc_info=True)
        # Don't raise - referral failure shouldn't break payment processing


# ============================================================================
# WEBHOOK EVENT HANDLERS
# ============================================================================

async def handle_subscription_created(db: AsyncSession, subscription_obj: Dict[str, Any]):
    """
    Handle customer.subscription.created event

    Creates a new subscription record and updates user's tier

    Args:
        db: Database session
        subscription_obj: Stripe subscription object
    """
    try:
        customer_id = subscription_obj["customer"]
        subscription_id = subscription_obj["id"]

        logger.info(f"Processing subscription.created: {subscription_id} for customer: {customer_id}")

        # Find user by Stripe customer ID
        user = await get_user_by_customer_id(db, customer_id)
        if not user:
            # Fallback: find user by metadata user_id (customer_id may not be stored yet)
            user_id_from_meta = subscription_obj.get("metadata", {}).get("user_id")
            if user_id_from_meta:
                result = await db.execute(
                    select(User).where(User.user_id == user_id_from_meta)
                )
                user = result.scalar_one_or_none()
                if user:
                    await db.execute(
                        update(User)
                        .where(User.user_id == user.user_id)
                        .values(stripe_customer_id=customer_id)
                    )
                    logger.info(f"Found user {user_id_from_meta} via metadata fallback")

        if not user:
            logger.warning(f"User not found for customer_id: {customer_id}")
            return

        # Determine subscription tier
        tier = get_tier_from_subscription(subscription_obj)

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

        # Update user's subscription tier
        await update_user_tier(db, user.user_id, tier)

        # Activate pending referral conversion if this is a paid subscription
        if tier in ("starter", "start", "professional", "pro", "enterprise", "team"):
            await db.execute(
                text("""
                    UPDATE referral_conversions
                    SET status = 'active', stripe_subscription_id = :sub_id,
                        converted_at = NOW(), updated_at = NOW()
                    WHERE referred_user_id = :uid AND status = 'pending'
                """),
                {"uid": str(user.user_id), "sub_id": subscription_id}
            )

        await db.commit()

        logger.info(f"Successfully created subscription for user {user.user_id} with tier: {tier}")

    except Exception as e:
        logger.error(f"Error handling subscription.created: {e}", exc_info=True)
        await db.rollback()
        raise


async def handle_subscription_updated(db: AsyncSession, subscription_obj: Dict[str, Any]):
    """
    Handle customer.subscription.updated event

    Updates subscription details including status, period dates, and tier changes

    Args:
        db: Database session
        subscription_obj: Stripe subscription object
    """
    try:
        subscription_id = subscription_obj["id"]

        logger.info(f"Processing subscription.updated: {subscription_id}")

        # Find existing subscription
        subscription = await get_subscription_by_stripe_id(db, subscription_id)
        if not subscription:
            logger.warning(f"Subscription not found: {subscription_id}")
            # Try to create it if it doesn't exist
            await handle_subscription_created(db, subscription_obj)
            return

        # Determine new tier (in case of plan change)
        new_tier = get_tier_from_subscription(subscription_obj)
        old_tier = subscription.tier

        # Update subscription record
        await db.execute(
            update(Subscription)
            .where(Subscription.stripe_subscription_id == subscription_id)
            .values(
                tier=new_tier,
                status=subscription_obj["status"],
                current_period_start=datetime.fromtimestamp(subscription_obj["current_period_start"]),
                current_period_end=datetime.fromtimestamp(subscription_obj["current_period_end"]),
                cancel_at_period_end=subscription_obj.get("cancel_at_period_end", False),
                cancelled_at=datetime.fromtimestamp(subscription_obj["canceled_at"]) if subscription_obj.get("canceled_at") else None
            )
        )

        # Update user tier if subscription is active or trialing
        if subscription_obj["status"] in ["active", "trialing"]:
            await update_user_tier(db, subscription.user_id, new_tier)
            logger.info(f"Updated user {subscription.user_id} tier from {old_tier} to {new_tier}")

        # If subscription is canceled or past_due, consider downgrading
        elif subscription_obj["status"] in ["canceled", "unpaid"]:
            await update_user_tier(db, subscription.user_id, "free")
            logger.info(f"Downgraded user {subscription.user_id} to free tier due to status: {subscription_obj['status']}")

        await db.commit()

        logger.info(f"Successfully updated subscription {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling subscription.updated: {e}", exc_info=True)
        await db.rollback()
        raise


async def handle_subscription_deleted(db: AsyncSession, subscription_obj: Dict[str, Any]):
    """
    Handle customer.subscription.deleted event

    Cancels subscription and downgrades user to free tier

    Args:
        db: Database session
        subscription_obj: Stripe subscription object
    """
    try:
        subscription_id = subscription_obj["id"]

        logger.info(f"Processing subscription.deleted: {subscription_id}")

        # Find subscription
        subscription = await get_subscription_by_stripe_id(db, subscription_id)
        if not subscription:
            logger.warning(f"Subscription not found for deletion: {subscription_id}")
            return

        # Update subscription status to canceled
        await db.execute(
            update(Subscription)
            .where(Subscription.stripe_subscription_id == subscription_id)
            .values(
                status="canceled",
                cancelled_at=datetime.utcnow()
            )
        )

        # Downgrade user to free tier
        await update_user_tier(db, subscription.user_id, "free")

        # Deactivate referral conversion so no more commissions accrue
        await db.execute(
            text("""
                UPDATE referral_conversions
                SET status = 'inactive', updated_at = NOW()
                WHERE referred_user_id = :uid AND status = 'active'
            """),
            {"uid": str(subscription.user_id)}
        )

        await db.commit()

        logger.info(f"Successfully deleted subscription {subscription_id} and downgraded user to free tier")

        # Notify Clawd VA
        user = await get_user_by_customer_id(db, subscription_obj["customer"])
        if user:
            await notify_clawd("subscription_cancelled", {"email": user.email})

    except Exception as e:
        logger.error(f"Error handling subscription.deleted: {e}", exc_info=True)
        await db.rollback()
        raise


async def handle_invoice_payment_succeeded(db: AsyncSession, invoice_obj: Dict[str, Any]):
    """
    Handle invoice.payment_succeeded event

    Confirms successful payment and ensures subscription is active

    Args:
        db: Database session
        invoice_obj: Stripe invoice object
    """
    try:
        customer_id = invoice_obj["customer"]
        subscription_id = invoice_obj.get("subscription")
        invoice_id = invoice_obj["id"]
        amount_paid = invoice_obj["amount_paid"] / 100  # Convert from cents
        currency = invoice_obj["currency"].upper()

        logger.info(f"Processing invoice.payment_succeeded: {invoice_id} for customer: {customer_id}")

        # Find user
        user = await get_user_by_customer_id(db, customer_id)
        if not user:
            logger.warning(f"User not found for customer_id: {customer_id}")
            return

        # If this is for a subscription, update subscription status
        if subscription_id:
            subscription = await get_subscription_by_stripe_id(db, subscription_id)
            if subscription:
                # Get tier from subscription
                tier = subscription.tier

                # Ensure subscription is active and user has correct tier
                await db.execute(
                    update(Subscription)
                    .where(Subscription.stripe_subscription_id == subscription_id)
                    .values(status="active")
                )

                await update_user_tier(db, user.user_id, tier)

                logger.info(f"Payment succeeded for subscription {subscription_id}, ensured active status")

        await db.commit()

        # Process referral commission (20% to referrer if applicable)
        await _process_referral_commission(db, user, invoice_obj)

        logger.info(f"Successfully processed payment of {amount_paid} {currency} for user {user.user_id}")

        # Notify Clawd VA
        await notify_clawd("payment_success", {"email": user.email, "amount": amount_paid, "currency": currency})

    except Exception as e:
        logger.error(f"Error handling invoice.payment_succeeded: {e}", exc_info=True)
        await db.rollback()
        raise


async def handle_invoice_payment_failed(db: AsyncSession, invoice_obj: Dict[str, Any]):
    """
    Handle invoice.payment_failed event

    Handles failed payments by marking subscription as past_due
    and potentially downgrading to free tier after grace period

    Args:
        db: Database session
        invoice_obj: Stripe invoice object
    """
    try:
        customer_id = invoice_obj["customer"]
        subscription_id = invoice_obj.get("subscription")
        invoice_id = invoice_obj["id"]
        amount_due = invoice_obj["amount_due"] / 100  # Convert from cents
        currency = invoice_obj["currency"].upper()
        attempt_count = invoice_obj.get("attempt_count", 0)

        logger.warning(f"Processing invoice.payment_failed: {invoice_id} for customer: {customer_id}")

        # Find user
        user = await get_user_by_customer_id(db, customer_id)
        if not user:
            logger.warning(f"User not found for customer_id: {customer_id}")
            return

        # If this is for a subscription, handle the failure
        if subscription_id:
            subscription = await get_subscription_by_stripe_id(db, subscription_id)
            if subscription:
                # Update subscription status to past_due
                await db.execute(
                    update(Subscription)
                    .where(Subscription.stripe_subscription_id == subscription_id)
                    .values(status="past_due")
                )

                # If this is the final attempt (typically 4th attempt), downgrade to free
                # Stripe typically retries 4 times before giving up
                if attempt_count >= 4:
                    await update_user_tier(db, user.user_id, "free")
                    logger.warning(f"Payment failed after {attempt_count} attempts, downgrading user {user.user_id} to free tier")
                else:
                    logger.warning(f"Payment failed (attempt {attempt_count}/4) for user {user.user_id}, keeping current tier but marking past_due")

        await db.commit()

        logger.info(f"Processed failed payment of {amount_due} {currency} for user {user.user_id}")

        # Notify Clawd VA
        await notify_clawd("payment_failed", {"email": user.email, "amount": amount_due, "currency": currency})

    except Exception as e:
        logger.error(f"Error handling invoice.payment_failed: {e}", exc_info=True)
        await db.rollback()
        raise


async def handle_subscription_trial_will_end(db: AsyncSession, subscription_obj: Dict[str, Any]):
    """
    Handle customer.subscription.trial_will_end event

    Notification that trial is ending soon (typically 3 days before)
    Can be used to send reminder emails to users

    Args:
        db: Database session
        subscription_obj: Stripe subscription object
    """
    try:
        subscription_id = subscription_obj["id"]
        customer_id = subscription_obj["customer"]
        trial_end = subscription_obj.get("trial_end")

        logger.info(f"Processing subscription.trial_will_end: {subscription_id}")

        # Find user
        user = await get_user_by_customer_id(db, customer_id)
        if not user:
            logger.warning(f"User not found for customer_id: {customer_id}")
            return

        # Find subscription
        subscription = await get_subscription_by_stripe_id(db, subscription_id)
        if not subscription:
            logger.warning(f"Subscription not found: {subscription_id}")
            return

        # Calculate days until trial ends
        if trial_end:
            trial_end_date = datetime.fromtimestamp(trial_end)
            days_remaining = (trial_end_date - datetime.utcnow()).days

            logger.info(f"Trial ending in {days_remaining} days for user {user.user_id} (email: {user.email})")

            # Here you could trigger an email notification service
            # Example: await send_trial_ending_email(user.email, days_remaining, subscription.tier)

        # No database changes needed for this event, it's just a notification
        logger.info(f"Trial ending notification logged for subscription {subscription_id}")

    except Exception as e:
        logger.error(f"Error handling subscription.trial_will_end: {e}", exc_info=True)
        # Don't raise for notification events
        pass


# ============================================================================
# STRIPE CONNECT ACCOUNT UPDATES
# ============================================================================

async def handle_account_updated(db: AsyncSession, account_obj: Dict[str, Any]):
    """Handle account.updated event for Stripe Connect accounts."""
    try:
        account_id = account_obj["id"]
        charges_enabled = account_obj.get("charges_enabled", False)
        payouts_enabled = account_obj.get("payouts_enabled", False)
        requirements = account_obj.get("requirements", {})
        currently_due = requirements.get("currently_due", [])

        logger.info(f"Connect account.updated: {account_id} charges={charges_enabled} payouts={payouts_enabled}")

        # Determine new status
        if charges_enabled and payouts_enabled:
            new_status = "active"
        elif currently_due:
            new_status = "restricted"
        else:
            new_status = "pending"

        # Update user's connect status
        result = await db.execute(
            text("UPDATE users SET stripe_connect_status = :st WHERE stripe_connect_id = :cid RETURNING user_id"),
            {"st": new_status, "cid": account_id}
        )
        row = result.fetchone()
        if row:
            await db.commit()
            logger.info(f"Updated Connect status to '{new_status}' for account {account_id} (user {row[0]})")
        else:
            logger.warning(f"No user found for Connect account {account_id}")

    except Exception as e:
        logger.error(f"Error handling account.updated: {e}", exc_info=True)


# ============================================================================
# WEBHOOK ENDPOINT
# ============================================================================

@router.post("/webhook")
async def stripe_webhook_handler(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db)
):
    """
    Main Stripe webhook endpoint

    Handles all Stripe webhook events with proper signature verification

    Security:
        - Webhook signature verification required
        - No authentication required (verified via Stripe signature)

    Events Handled:
        - customer.subscription.created: New subscription created
        - customer.subscription.updated: Subscription modified (plan change, status change, etc.)
        - customer.subscription.deleted: Subscription cancelled
        - invoice.payment_succeeded: Payment successful
        - invoice.payment_failed: Payment failed
        - customer.subscription.trial_will_end: Trial ending soon notification

    Returns:
        dict: Success status and event type

    Raises:
        HTTPException: 400 for invalid signature or payload
    """
    # Get raw payload
    payload = await request.body()

    # Verify webhook signature
    if stripe_signature:
        if not verify_webhook_signature(payload, stripe_signature):
            logger.error("Webhook signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
    else:
        logger.warning("No stripe-signature header provided")
        if STRIPE_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing stripe-signature header"
            )

    # Parse event
    try:
        event_dict = await request.json()
        event = stripe.Event.construct_from(event_dict, stripe.api_key)
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload"
        )
    except Exception as e:
        logger.error(f"Error parsing webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error parsing webhook payload"
        )

    # Log event
    logger.info(f"Received Stripe webhook event: {event.type} (ID: {event.id})")

    # Handle different event types
    try:
        if event.type == "customer.subscription.created":
            await handle_subscription_created(db, event.data.object)

        elif event.type == "customer.subscription.updated":
            await handle_subscription_updated(db, event.data.object)

        elif event.type == "customer.subscription.deleted":
            await handle_subscription_deleted(db, event.data.object)

        elif event.type == "invoice.payment_succeeded":
            await handle_invoice_payment_succeeded(db, event.data.object)

        elif event.type == "invoice.payment_failed":
            await handle_invoice_payment_failed(db, event.data.object)

        elif event.type == "customer.subscription.trial_will_end":
            await handle_subscription_trial_will_end(db, event.data.object)

        elif event.type == "account.updated":
            await handle_account_updated(db, event.data.object)

        else:
            # Log unhandled event types for future implementation
            logger.info(f"Unhandled event type: {event.type}")

        logger.info(f"Successfully processed webhook event: {event.type}")

        return {
            "status": "success",
            "event_type": event.type,
            "event_id": event.id,
            "processed_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error processing webhook event {event.type}: {e}", exc_info=True)
        # Return 200 to prevent Stripe from retrying on application errors
        # But log the error for investigation
        return {
            "status": "error",
            "event_type": event.type,
            "event_id": event.id,
            "error": str(e),
            "processed_at": datetime.utcnow().isoformat()
        }


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/webhook/health")
async def webhook_health_check():
    """
    Health check endpoint for Stripe webhook integration

    Returns:
        dict: Webhook configuration status
    """
    return {
        "status": "healthy",
        "webhook_secret_configured": bool(STRIPE_WEBHOOK_SECRET),
        "stripe_api_key_configured": bool(STRIPE_SECRET_KEY),
        "supported_events": [
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.payment_succeeded",
            "invoice.payment_failed",
            "customer.subscription.trial_will_end"
        ],
        "price_id_mappings": len(PRICE_ID_TO_TIER),
        "timestamp": datetime.utcnow().isoformat()
    }
