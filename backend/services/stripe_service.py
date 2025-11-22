"""
Stripe Service for handling payment processing and subscription management.
"""
import os
import logging
from typing import Optional, Dict, List, Any
import stripe
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Price IDs from environment
PRICE_IDS = {
    "basic": os.getenv("STRIPE_PRICE_BASIC"),
    "professional": os.getenv("STRIPE_PRICE_PROFESSIONAL"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE"),
}


class StripeServiceError(Exception):
    """Base exception for Stripe service errors."""
    pass


class StripeWebhookError(Exception):
    """Exception for webhook processing errors."""
    pass


async def create_checkout_session(
    user_id: int,
    plan_id: str,
    success_url: str,
    cancel_url: str,
    metadata: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Create a Stripe Checkout session for subscription purchase.

    Args:
        user_id: Internal user ID
        plan_id: Plan identifier (basic, professional, enterprise)
        success_url: URL to redirect on successful payment
        cancel_url: URL to redirect on cancelled payment
        metadata: Optional metadata to attach to the session

    Returns:
        dict: Checkout session data including session ID and URL

    Raises:
        StripeServiceError: If session creation fails
    """
    try:
        price_id = PRICE_IDS.get(plan_id)
        if not price_id:
            raise StripeServiceError(f"Invalid plan_id: {plan_id}")

        session_metadata = {"user_id": str(user_id), "plan_id": plan_id}
        if metadata:
            session_metadata.update(metadata)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=session_metadata,
            client_reference_id=str(user_id),
            allow_promotion_codes=True,
            billing_address_collection="auto",
        )

        logger.info(f"Created checkout session {session.id} for user {user_id}")

        return {
            "session_id": session.id,
            "url": session.url,
            "status": session.status,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise StripeServiceError(f"Failed to create checkout session: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def create_customer(user_id: int, email: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Create a Stripe customer.

    Args:
        user_id: Internal user ID
        email: Customer email address
        metadata: Optional metadata to attach to the customer

    Returns:
        str: Stripe customer ID

    Raises:
        StripeServiceError: If customer creation fails
    """
    try:
        customer_metadata = {"user_id": str(user_id)}
        if metadata:
            customer_metadata.update(metadata)

        customer = stripe.Customer.create(
            email=email,
            metadata=customer_metadata,
        )

        logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
        return customer.id

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating customer: {str(e)}")
        raise StripeServiceError(f"Failed to create customer: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating customer: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def create_subscription(
    customer_id: str,
    price_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    trial_period_days: Optional[int] = None
) -> dict:
    """
    Create a subscription for a customer.

    Args:
        customer_id: Stripe customer ID
        price_id: Stripe price ID
        metadata: Optional metadata to attach to the subscription
        trial_period_days: Optional trial period in days

    Returns:
        dict: Subscription data

    Raises:
        StripeServiceError: If subscription creation fails
    """
    try:
        subscription_params = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "payment_behavior": "default_incomplete",
            "payment_settings": {"save_default_payment_method": "on_subscription"},
            "expand": ["latest_invoice.payment_intent"],
        }

        if metadata:
            subscription_params["metadata"] = metadata

        if trial_period_days:
            subscription_params["trial_period_days"] = trial_period_days

        subscription = stripe.Subscription.create(**subscription_params)

        logger.info(f"Created subscription {subscription.id} for customer {customer_id}")

        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret
            if subscription.latest_invoice and subscription.latest_invoice.payment_intent
            else None,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating subscription: {str(e)}")
        raise StripeServiceError(f"Failed to create subscription: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating subscription: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def cancel_subscription(subscription_id: str, immediately: bool = False) -> bool:
    """
    Cancel a subscription.

    Args:
        subscription_id: Stripe subscription ID
        immediately: If True, cancel immediately; otherwise cancel at period end

    Returns:
        bool: True if cancellation was successful

    Raises:
        StripeServiceError: If cancellation fails
    """
    try:
        if immediately:
            subscription = stripe.Subscription.delete(subscription_id)
            logger.info(f"Immediately cancelled subscription {subscription_id}")
        else:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            logger.info(f"Scheduled subscription {subscription_id} for cancellation at period end")

        return True

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error cancelling subscription: {str(e)}")
        raise StripeServiceError(f"Failed to cancel subscription: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error cancelling subscription: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def get_subscription_status(subscription_id: str) -> str:
    """
    Get the status of a subscription.

    Args:
        subscription_id: Stripe subscription ID

    Returns:
        str: Subscription status (active, canceled, past_due, etc.)

    Raises:
        StripeServiceError: If retrieval fails
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        logger.info(f"Retrieved status for subscription {subscription_id}: {subscription.status}")
        return subscription.status

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving subscription: {str(e)}")
        raise StripeServiceError(f"Failed to retrieve subscription: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving subscription: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def create_payment_intent(
    amount: int,
    currency: str,
    customer_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Create a payment intent for one-time payments.

    Args:
        amount: Amount in smallest currency unit (e.g., cents)
        currency: Three-letter ISO currency code
        customer_id: Stripe customer ID
        metadata: Optional metadata to attach to the payment intent

    Returns:
        dict: Payment intent data including client secret

    Raises:
        StripeServiceError: If payment intent creation fails
    """
    try:
        intent_params = {
            "amount": amount,
            "currency": currency,
            "customer": customer_id,
            "automatic_payment_methods": {"enabled": True},
        }

        if metadata:
            intent_params["metadata"] = metadata

        intent = stripe.PaymentIntent.create(**intent_params)

        logger.info(f"Created payment intent {intent.id} for customer {customer_id}")

        return {
            "payment_intent_id": intent.id,
            "client_secret": intent.client_secret,
            "status": intent.status,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating payment intent: {str(e)}")
        raise StripeServiceError(f"Failed to create payment intent: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating payment intent: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def handle_webhook(payload: bytes, signature: str) -> dict:
    """
    Handle Stripe webhook events.

    Args:
        payload: Raw request body
        signature: Stripe signature header

    Returns:
        dict: Event processing result

    Raises:
        StripeWebhookError: If webhook processing fails
    """
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )

        event_type = event["type"]
        event_data = event["data"]["object"]

        logger.info(f"Processing webhook event: {event_type}")

        # Handle different event types
        if event_type == "checkout.session.completed":
            return await _handle_checkout_completed(event_data)

        elif event_type == "customer.subscription.updated":
            return await _handle_subscription_updated(event_data)

        elif event_type == "customer.subscription.deleted":
            return await _handle_subscription_deleted(event_data)

        elif event_type == "invoice.payment_succeeded":
            return await _handle_payment_succeeded(event_data)

        elif event_type == "invoice.payment_failed":
            return await _handle_payment_failed(event_data)

        else:
            logger.warning(f"Unhandled webhook event type: {event_type}")
            return {"status": "unhandled", "event_type": event_type}

    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {str(e)}")
        raise StripeWebhookError("Invalid signature")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise StripeWebhookError(f"Webhook processing failed: {str(e)}")


async def _handle_checkout_completed(session_data: dict) -> dict:
    """Handle checkout.session.completed event."""
    logger.info(f"Checkout completed for session {session_data.get('id')}")

    # TODO: Update database with subscription info
    # - Get user_id from metadata
    # - Update user's subscription_id and stripe_customer_id
    # - Set subscription status to active

    return {
        "status": "processed",
        "event_type": "checkout.session.completed",
        "session_id": session_data.get("id"),
    }


async def _handle_subscription_updated(subscription_data: dict) -> dict:
    """Handle customer.subscription.updated event."""
    logger.info(f"Subscription updated: {subscription_data.get('id')}")

    # TODO: Update database with new subscription status
    # - Get subscription_id
    # - Update status, current_period_end, etc.

    return {
        "status": "processed",
        "event_type": "customer.subscription.updated",
        "subscription_id": subscription_data.get("id"),
    }


async def _handle_subscription_deleted(subscription_data: dict) -> dict:
    """Handle customer.subscription.deleted event."""
    logger.info(f"Subscription deleted: {subscription_data.get('id')}")

    # TODO: Update database
    # - Mark subscription as cancelled
    # - Downgrade user to free tier

    return {
        "status": "processed",
        "event_type": "customer.subscription.deleted",
        "subscription_id": subscription_data.get("id"),
    }


async def _handle_payment_succeeded(invoice_data: dict) -> dict:
    """Handle invoice.payment_succeeded event."""
    logger.info(f"Payment succeeded for invoice {invoice_data.get('id')}")

    # TODO: Update database
    # - Record successful payment
    # - Update subscription status if needed
    # - Send confirmation email

    return {
        "status": "processed",
        "event_type": "invoice.payment_succeeded",
        "invoice_id": invoice_data.get("id"),
    }


async def _handle_payment_failed(invoice_data: dict) -> dict:
    """Handle invoice.payment_failed event."""
    logger.error(f"Payment failed for invoice {invoice_data.get('id')}")

    # TODO: Update database
    # - Record failed payment
    # - Update subscription status to past_due
    # - Send payment failure notification

    return {
        "status": "processed",
        "event_type": "invoice.payment_failed",
        "invoice_id": invoice_data.get("id"),
    }


async def get_invoices(customer_id: str, limit: int = 10) -> list:
    """
    Get invoices for a customer.

    Args:
        customer_id: Stripe customer ID
        limit: Maximum number of invoices to retrieve

    Returns:
        list: List of invoice data

    Raises:
        StripeServiceError: If retrieval fails
    """
    try:
        invoices = stripe.Invoice.list(customer=customer_id, limit=limit)

        logger.info(f"Retrieved {len(invoices.data)} invoices for customer {customer_id}")

        return [
            {
                "id": invoice.id,
                "amount_due": invoice.amount_due,
                "amount_paid": invoice.amount_paid,
                "currency": invoice.currency,
                "status": invoice.status,
                "created": invoice.created,
                "invoice_pdf": invoice.invoice_pdf,
                "hosted_invoice_url": invoice.hosted_invoice_url,
            }
            for invoice in invoices.data
        ]

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving invoices: {str(e)}")
        raise StripeServiceError(f"Failed to retrieve invoices: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving invoices: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def get_payment_methods(customer_id: str) -> list:
    """
    Get payment methods for a customer.

    Args:
        customer_id: Stripe customer ID

    Returns:
        list: List of payment method data

    Raises:
        StripeServiceError: If retrieval fails
    """
    try:
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type="card",
        )

        logger.info(f"Retrieved {len(payment_methods.data)} payment methods for customer {customer_id}")

        return [
            {
                "id": pm.id,
                "type": pm.type,
                "card": {
                    "brand": pm.card.brand,
                    "last4": pm.card.last4,
                    "exp_month": pm.card.exp_month,
                    "exp_year": pm.card.exp_year,
                } if pm.card else None,
            }
            for pm in payment_methods.data
        ]

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving payment methods: {str(e)}")
        raise StripeServiceError(f"Failed to retrieve payment methods: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving payment methods: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def attach_payment_method(customer_id: str, payment_method_id: str) -> bool:
    """
    Attach a payment method to a customer.

    Args:
        customer_id: Stripe customer ID
        payment_method_id: Stripe payment method ID

    Returns:
        bool: True if successful

    Raises:
        StripeServiceError: If attachment fails
    """
    try:
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id,
        )

        logger.info(f"Attached payment method {payment_method_id} to customer {customer_id}")
        return True

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error attaching payment method: {str(e)}")
        raise StripeServiceError(f"Failed to attach payment method: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error attaching payment method: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")


async def set_default_payment_method(customer_id: str, payment_method_id: str) -> bool:
    """
    Set the default payment method for a customer.

    Args:
        customer_id: Stripe customer ID
        payment_method_id: Stripe payment method ID

    Returns:
        bool: True if successful

    Raises:
        StripeServiceError: If update fails
    """
    try:
        stripe.Customer.modify(
            customer_id,
            invoice_settings={
                "default_payment_method": payment_method_id,
            },
        )

        logger.info(f"Set default payment method {payment_method_id} for customer {customer_id}")
        return True

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error setting default payment method: {str(e)}")
        raise StripeServiceError(f"Failed to set default payment method: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error setting default payment method: {str(e)}")
        raise StripeServiceError(f"Unexpected error: {str(e)}")
