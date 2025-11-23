"""
Stripe Billing Service for subscription management
"""
import os
import logging
from typing import Optional, Dict, Any
import stripe

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')

# Plan configuration
PLAN_LIMITS = {
    'free': {
        'max_alerts': int(os.getenv('STRIPE_FREE_MAX_ALERTS', '3')),
        'name': 'Free',
        'features': ['Up to 3 alerts per day', 'Basic tender notifications']
    },
    'starter': {
        'max_alerts': int(os.getenv('STRIPE_STARTER_MAX_ALERTS', '5')),
        'name': 'Starter',
        'features': ['Up to 5 alerts per day', 'Email notifications', 'Basic filters']
    },
    'professional': {
        'max_alerts': int(os.getenv('STRIPE_PROFESSIONAL_MAX_ALERTS', '20')),
        'name': 'Professional',
        'features': ['Up to 20 alerts per day', 'Advanced filters', 'Priority support', 'Export capabilities']
    },
    'enterprise': {
        'max_alerts': int(os.getenv('STRIPE_ENTERPRISE_MAX_ALERTS', '999999')),
        'name': 'Enterprise',
        'features': ['Unlimited alerts', 'All features', '24/7 support', 'Custom integrations', 'Dedicated account manager']
    }
}

# Price IDs from environment
PRICE_IDS = {
    'free': {
        'monthly': os.getenv('STRIPE_FREE_MONTHLY'),
        'yearly': os.getenv('STRIPE_FREE_YEARLY')
    },
    'starter': {
        'monthly': os.getenv('STRIPE_STARTER_MONTHLY'),
        'yearly': os.getenv('STRIPE_STARTER_YEARLY')
    },
    'professional': {
        'monthly': os.getenv('STRIPE_PROFESSIONAL_MONTHLY'),
        'yearly': os.getenv('STRIPE_PROFESSIONAL_YEARLY')
    },
    'enterprise': {
        'monthly': os.getenv('STRIPE_ENTERPRISE_MONTHLY'),
        'yearly': os.getenv('STRIPE_ENTERPRISE_YEARLY')
    }
}


class BillingService:
    """Service for managing Stripe billing and subscriptions"""

    def __init__(self):
        self.stripe = stripe
        self.currency = os.getenv('STRIPE_CURRENCY', 'eur')

    def get_plan_limits(self, tier: str) -> Dict[str, Any]:
        """Get plan limits and features for a subscription tier"""
        return PLAN_LIMITS.get(tier.lower(), PLAN_LIMITS['free'])

    def get_price_id(self, tier: str, interval: str = 'monthly') -> Optional[str]:
        """Get Stripe price ID for a plan tier and billing interval"""
        tier_lower = tier.lower()
        if tier_lower not in PRICE_IDS:
            return None
        return PRICE_IDS[tier_lower].get(interval.lower())

    async def create_checkout_session(
        self,
        user_id: str,
        email: str,
        tier: str,
        interval: str = 'monthly',
        success_url: str = None,
        cancel_url: str = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout session for subscription purchase

        Args:
            user_id: User's UUID
            email: User's email
            tier: Subscription tier (starter, professional, enterprise)
            interval: Billing interval (monthly or yearly)
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment cancelled

        Returns:
            Dict containing checkout session details
        """
        try:
            price_id = self.get_price_id(tier, interval)
            if not price_id:
                raise ValueError(f"Invalid tier or interval: {tier}/{interval}")

            # Default URLs
            if not success_url:
                success_url = os.getenv('FRONTEND_URL', 'http://localhost:3000') + '/billing/success?session_id={CHECKOUT_SESSION_ID}'
            if not cancel_url:
                cancel_url = os.getenv('FRONTEND_URL', 'http://localhost:3000') + '/billing/cancel'

            # Create checkout session
            session = self.stripe.checkout.Session.create(
                customer_email=email,
                client_reference_id=user_id,
                mode='subscription',
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                locale='auto',  # Auto-detect user's language (Stripe doesn't support Macedonian)
                metadata={
                    'user_id': user_id,
                    'tier': tier,
                    'interval': interval
                },
                subscription_data={
                    'metadata': {
                        'user_id': user_id,
                        'tier': tier
                    }
                },
                allow_promotion_codes=True,
                billing_address_collection='required',
                tax_id_collection={'enabled': True}
            )

            logger.info(f"Created checkout session {session.id} for user {user_id}")

            return {
                'session_id': session.id,
                'url': session.url,
                'status': 'created'
            }

        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            raise

    async def create_billing_portal_session(
        self,
        customer_id: str,
        return_url: str = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe billing portal session for subscription management

        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after portal session

        Returns:
            Dict containing portal session URL
        """
        try:
            if not return_url:
                return_url = os.getenv('FRONTEND_URL', 'http://localhost:3000') + '/settings'

            session = self.stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )

            logger.info(f"Created billing portal session for customer {customer_id}")

            return {
                'url': session.url,
                'status': 'created'
            }

        except Exception as e:
            logger.error(f"Error creating billing portal session: {str(e)}")
            raise

    async def get_subscription_status(self, subscription_id: str) -> Dict[str, Any]:
        """Get current subscription status from Stripe"""
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)

            return {
                'id': subscription.id,
                'status': subscription.status,
                'current_period_start': subscription.current_period_start,
                'current_period_end': subscription.current_period_end,
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'canceled_at': subscription.canceled_at,
                'customer_id': subscription.customer,
                'plan': subscription.items.data[0].price.id if subscription.items.data else None
            }

        except Exception as e:
            logger.error(f"Error retrieving subscription: {str(e)}")
            raise

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True
    ) -> Dict[str, Any]:
        """
        Cancel a subscription

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of billing period. If False, cancel immediately.

        Returns:
            Dict containing cancellation status
        """
        try:
            if at_period_end:
                subscription = self.stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
                status = 'scheduled_for_cancellation'
            else:
                subscription = self.stripe.Subscription.delete(subscription_id)
                status = 'canceled'

            logger.info(f"Canceled subscription {subscription_id} (at_period_end={at_period_end})")

            return {
                'subscription_id': subscription.id,
                'status': status,
                'cancel_at': subscription.current_period_end if at_period_end else None
            }

        except Exception as e:
            logger.error(f"Error canceling subscription: {str(e)}")
            raise

    async def update_subscription(
        self,
        subscription_id: str,
        new_price_id: str
    ) -> Dict[str, Any]:
        """
        Update subscription to a new plan

        Args:
            subscription_id: Stripe subscription ID
            new_price_id: New Stripe price ID

        Returns:
            Dict containing updated subscription details
        """
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)

            updated_subscription = self.stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior='create_prorations'
            )

            logger.info(f"Updated subscription {subscription_id} to price {new_price_id}")

            return {
                'subscription_id': updated_subscription.id,
                'status': 'updated',
                'new_price': new_price_id
            }

        except Exception as e:
            logger.error(f"Error updating subscription: {str(e)}")
            raise

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> stripe.Event:
        """
        Construct and verify Stripe webhook event

        Args:
            payload: Raw request body
            sig_header: Stripe signature header

        Returns:
            Verified Stripe event
        """
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        if not webhook_secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET not configured")

        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return event
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            raise


# Global billing service instance
billing_service = BillingService()
