"""Stripe subscription integration"""
import os
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

PRICES = {
    "standard": os.getenv("STRIPE_PRICE_STANDARD", "price_standard"),
    "pro": os.getenv("STRIPE_PRICE_PRO", "price_pro"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise")
}

def create_checkout_session(user_id: str, email: str, tier: str) -> dict:
    """Create Stripe checkout session"""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": PRICES[tier], "quantity": 1}],
        mode="subscription",
        success_url=f"{os.getenv('FRONTEND_URL')}/billing/success",
        cancel_url=f"{os.getenv('FRONTEND_URL')}/billing/cancel",
        customer_email=email,
        client_reference_id=user_id,
        metadata={"user_id": user_id, "tier": tier}
    )
    return {"session_id": session.id, "url": session.url}

def create_portal_session(customer_id: str) -> dict:
    """Create customer portal session"""
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{os.getenv('FRONTEND_URL')}/account"
    )
    return {"url": session.url}
