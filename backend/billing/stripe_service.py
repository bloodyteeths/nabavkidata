"""
Stripe Subscription Integration for nabavkidata.com
Supports dual currency: MKD (card only) and EUR (card + SEPA)

Pricing:
- Starter: 1,990 MKD / €39 per month
- Professional: 5,990 MKD / €99 per month
- Enterprise: 12,990 MKD / €199 per month

Environment Variables:
- STRIPE_SECRET_KEY: Stripe secret API key
- STRIPE_WEBHOOK_SECRET: Webhook signing secret
- STRIPE_MKD_STARTER_MONTHLY: Price ID for Starter plan in MKD
- STRIPE_EUR_PROFESSIONAL_YEARLY: Price ID for Professional plan yearly in EUR
- etc.
"""
import os
import stripe
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Legacy price IDs (backward compatibility)
PRICES = {
    "starter": os.getenv("STRIPE_PRICE_STANDARD", "price_standard"),
    "professional": os.getenv("STRIPE_PRICE_PRO", "price_pro"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise")
}

# Dual currency price IDs
# Format: STRIPE_{CURRENCY}_{TIER}_{INTERVAL}
PRICE_IDS = {
    "mkd": {
        "starter": {
            "monthly": os.getenv("STRIPE_MKD_STARTER_MONTHLY"),
            "yearly": os.getenv("STRIPE_MKD_STARTER_YEARLY"),
        },
        "professional": {
            "monthly": os.getenv("STRIPE_MKD_PROFESSIONAL_MONTHLY"),
            "yearly": os.getenv("STRIPE_MKD_PROFESSIONAL_YEARLY"),
        },
        "enterprise": {
            "monthly": os.getenv("STRIPE_MKD_ENTERPRISE_MONTHLY"),
            "yearly": os.getenv("STRIPE_MKD_ENTERPRISE_YEARLY"),
        },
    },
    "eur": {
        "starter": {
            "monthly": os.getenv("STRIPE_EUR_STARTER_MONTHLY"),
            "yearly": os.getenv("STRIPE_EUR_STARTER_YEARLY"),
        },
        "professional": {
            "monthly": os.getenv("STRIPE_EUR_PROFESSIONAL_MONTHLY"),
            "yearly": os.getenv("STRIPE_EUR_PROFESSIONAL_YEARLY"),
        },
        "enterprise": {
            "monthly": os.getenv("STRIPE_EUR_ENTERPRISE_MONTHLY"),
            "yearly": os.getenv("STRIPE_EUR_ENTERPRISE_YEARLY"),
        },
    },
}


def get_price_id(tier: str, currency: str = "mkd", interval: str = "monthly") -> Optional[str]:
    """Get Stripe price ID for tier, currency, and interval"""
    return PRICE_IDS.get(currency.lower(), {}).get(tier.lower(), {}).get(interval.lower())


def get_payment_methods(currency: str) -> List[str]:
    """Get allowed payment methods for a currency"""
    if currency.lower() == "mkd":
        return ["card"]
    elif currency.lower() == "eur":
        return ["card", "sepa_debit"]
    return ["card"]


def create_checkout_session(
    user_id: str,
    email: str,
    tier: str,
    currency: str = "mkd",
    interval: str = "monthly",
    trial_days: int = 0
) -> dict:
    """
    Create Stripe checkout session with currency support

    Args:
        user_id: User's UUID
        email: User's email
        tier: Subscription tier (starter, professional, enterprise)
        currency: Payment currency (mkd or eur)
        interval: Billing interval (monthly or yearly)
        trial_days: Number of trial days (0 = no trial)

    Returns:
        Dict with session_id and checkout URL
    """
    price_id = get_price_id(tier, currency, interval)
    if not price_id:
        # Fallback to legacy pricing
        price_id = PRICES.get(tier)
        if not price_id:
            raise ValueError(f"No price configured for {tier}/{currency}/{interval}")

    payment_methods = get_payment_methods(currency)

    # Build checkout session params
    session_params = {
        "payment_method_types": payment_methods,
        "line_items": [{"price": price_id, "quantity": 1}],
        "mode": "subscription",
        "success_url": f"{os.getenv('FRONTEND_URL')}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{os.getenv('FRONTEND_URL')}/billing/cancel",
        "customer_email": email,
        "client_reference_id": user_id,
        "metadata": {
            "user_id": user_id,
            "tier": tier,
            "currency": currency,
            "interval": interval,
        },
        "subscription_data": {
            "metadata": {
                "user_id": user_id,
                "tier": tier,
            }
        },
        "allow_promotion_codes": True,
        "billing_address_collection": "required",
        "tax_id_collection": {"enabled": True},
    }

    # Add trial if specified
    if trial_days > 0:
        session_params["subscription_data"]["trial_period_days"] = trial_days
        session_params["subscription_data"]["metadata"]["trial"] = "true"

    # For SEPA, set payment method options
    if "sepa_debit" in payment_methods:
        session_params["payment_method_options"] = {
            "sepa_debit": {
                "mandate_options": {
                    "reference_prefix": "NABAVKI",
                }
            }
        }

    session = stripe.checkout.Session.create(**session_params)

    logger.info(f"Created checkout session {session.id} for {email} ({tier}/{currency})")

    return {
        "session_id": session.id,
        "url": session.url,
        "currency": currency,
        "tier": tier,
    }


def create_portal_session(customer_id: str, return_url: Optional[str] = None) -> dict:
    """Create customer portal session for subscription management"""
    if not return_url:
        return_url = f"{os.getenv('FRONTEND_URL')}/account"

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url
    )
    return {"url": session.url}


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Stripe webhook signature"""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not set, skipping signature verification")
        return True

    try:
        stripe.Webhook.construct_event(payload, signature, webhook_secret)
        return True
    except stripe.error.SignatureVerificationError:
        return False
