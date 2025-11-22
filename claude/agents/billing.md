# Billing & Stripe Agent
## nabavkidata.com - Subscription & Payment Integration

---

## AGENT PROFILE

**Agent ID**: `billing`
**Role**: Stripe subscription integration and payment processing
**Priority**: 4
**Execution Stage**: Integration (depends on Backend)
**Language**: Python (FastAPI) or TypeScript (Node.js)
**Framework**: Stripe SDK, Webhooks
**Dependencies**: Backend Agent (requires user system and API)

---

## PURPOSE

Implement a complete subscription billing system that:
- Manages 4 subscription tiers (Free, Standard €99/mo, Pro €395/mo, Enterprise €1495/mo)
- Handles Stripe Checkout for upgrades/downgrades
- Processes webhook events (subscription created, updated, cancelled, payment failed)
- Enforces tier-based feature limits in Backend
- Provides customer portal access for self-service billing
- Tracks revenue and subscription metrics

**Your billing system ensures nabavkidata.com generates sustainable revenue.**

---

## CORE RESPONSIBILITIES

### 1. Stripe Product & Price Setup
- ✅ Create 4 Stripe Products (Free, Standard, Pro, Enterprise)
- ✅ Create recurring Prices for each (monthly billing)
- ✅ Set up price IDs in configuration
- ✅ Support promotional pricing (coupons, discounts)

### 2. Checkout Flow
- ✅ Create Stripe Checkout Sessions from Backend API
- ✅ Redirect users to Stripe-hosted checkout page
- ✅ Handle successful checkout redirect
- ✅ Update user subscription in database on success
- ✅ Handle failed/cancelled checkouts

### 3. Webhook Processing
- ✅ Receive Stripe webhook events
- ✅ Verify webhook signatures (security)
- ✅ Handle events:
  - `checkout.session.completed` → Activate subscription
  - `customer.subscription.updated` → Update tier
  - `customer.subscription.deleted` → Cancel subscription (downgrade to Free)
  - `invoice.payment_succeeded` → Record payment
  - `invoice.payment_failed` → Send dunning emails
- ✅ Idempotent processing (handle duplicate events)

### 4. Subscription Management
- ✅ Allow users to upgrade/downgrade plans
- ✅ Prorate charges when changing plans
- ✅ Cancel subscriptions (immediate or end of period)
- ✅ Generate Customer Portal links (Stripe-hosted)
- ✅ Handle trial periods (optional 14-day free trial)

### 5. Usage Enforcement
- ✅ Integrate with Backend middleware to enforce limits:
  - Free: 5 AI queries/day, 1 alert
  - Standard: 100 AI queries/day, 10 alerts
  - Pro: 500 AI queries/day, 50 alerts
  - Enterprise: Unlimited
- ✅ Block actions when quota exceeded
- ✅ Display upgrade prompts

### 6. Revenue Tracking
- ✅ Store subscription events in `audit_log`
- ✅ Track MRR (Monthly Recurring Revenue)
- ✅ Generate billing reports
- ✅ Monitor churn rate

---

## INPUTS

### From Backend Agent
- User authentication system
- Database schema (`subscriptions`, `users`, `audit_log` tables)
- API framework (FastAPI or Express)

### Configuration
**File**: `backend/.env` (Billing section)
```env
# Stripe Keys
STRIPE_SECRET_KEY=sk_test_51ABC...
STRIPE_PUBLISHABLE_KEY=pk_test_51ABC...
STRIPE_WEBHOOK_SECRET=whsec_xyz...

# Stripe Product/Price IDs
STRIPE_PRICE_STANDARD=price_1ABC...
STRIPE_PRICE_PRO=price_1DEF...
STRIPE_PRICE_ENTERPRISE=price_1GHI...

# Frontend URLs
FRONTEND_URL=http://localhost:3000
SUCCESS_URL=http://localhost:3000/billing/success
CANCEL_URL=http://localhost:3000/billing/cancel
```

---

## OUTPUTS

### Code Deliverables

#### 1. Stripe Service Module

**`backend/billing/stripe_service.py`** - Stripe SDK wrapper
```python
import os
import stripe
from typing import Optional, Dict

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

STRIPE_PRICES = {
    "standard": os.getenv("STRIPE_PRICE_STANDARD"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE")
}

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

class StripeService:
    """Stripe integration for subscriptions"""

    @staticmethod
    def create_checkout_session(
        user_id: str,
        user_email: str,
        tier: str
    ) -> Dict:
        """
        Create a Stripe Checkout Session for subscription upgrade.

        Args:
            user_id: Internal user ID
            user_email: User's email
            tier: Subscription tier (standard, pro, enterprise)

        Returns:
            Checkout session with URL to redirect user
        """
        if tier not in STRIPE_PRICES:
            raise ValueError(f"Invalid tier: {tier}")

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price": STRIPE_PRICES[tier],
                    "quantity": 1
                }],
                mode="subscription",
                success_url=f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{FRONTEND_URL}/billing/cancel",
                customer_email=user_email,
                client_reference_id=user_id,  # Link to our user
                metadata={
                    "user_id": user_id,
                    "tier": tier
                },
                subscription_data={
                    "metadata": {
                        "user_id": user_id
                    }
                },
                allow_promotion_codes=True  # Enable coupon codes
            )

            return {
                "session_id": session.id,
                "url": session.url
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")

    @staticmethod
    def create_customer_portal_session(customer_id: str) -> Dict:
        """
        Create Customer Portal session for self-service billing.

        Allows users to:
        - Update payment method
        - View invoices
        - Cancel subscription
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{FRONTEND_URL}/account"
            )

            return {
                "url": session.url
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")

    @staticmethod
    def cancel_subscription(subscription_id: str, immediate: bool = False) -> Dict:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            immediate: If True, cancel now. If False, cancel at period end.
        """
        try:
            if immediate:
                subscription = stripe.Subscription.delete(subscription_id)
            else:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )

            return {
                "status": subscription.status,
                "cancelled_at": subscription.canceled_at,
                "cancel_at_period_end": subscription.cancel_at_period_end
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")

    @staticmethod
    def get_subscription(subscription_id: str) -> Dict:
        """Retrieve subscription details"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)

            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")
```

#### 2. Webhook Handler

**`backend/webhooks/stripe.py`** - Process Stripe webhook events
```python
import os
import stripe
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import logging

from database import get_db
from models import User, Subscription, AuditLog
from datetime import datetime

router = APIRouter()

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
logger = logging.getLogger(__name__)

@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle Stripe webhook events.

    Security: Verify webhook signature to prevent fake events.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle event types
    event_type = event["type"]
    event_data = event["data"]["object"]

    logger.info(f"Received webhook: {event_type}", extra={"event_id": event["id"]})

    try:
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(event_data, db)

        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(event_data, db)

        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(event_data, db)

        elif event_type == "invoice.payment_succeeded":
            await handle_payment_succeeded(event_data, db)

        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(event_data, db)

        else:
            logger.info(f"Unhandled event type: {event_type}")

        await db.commit()

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"status": "success"}


async def handle_checkout_completed(session: Dict, db: AsyncSession):
    """
    User completed checkout - activate subscription.

    Steps:
    1. Extract user_id from metadata
    2. Create/update subscription record
    3. Update user's subscription_tier
    4. Log event
    """
    user_id = session.get("metadata", {}).get("user_id")
    subscription_id = session.get("subscription")
    customer_id = session.get("customer")

    if not user_id:
        logger.error("No user_id in checkout session metadata")
        return

    # Get subscription details from Stripe
    subscription = stripe.Subscription.retrieve(subscription_id)
    tier = map_stripe_price_to_tier(subscription["items"]["data"][0]["price"]["id"])

    # Update user
    await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(
            subscription_tier=tier,
            stripe_customer_id=customer_id
        )
    )

    # Create subscription record
    new_sub = Subscription(
        user_id=user_id,
        stripe_subscription_id=subscription_id,
        stripe_customer_id=customer_id,
        tier=tier,
        status="active",
        current_period_start=datetime.fromtimestamp(subscription["current_period_start"]),
        current_period_end=datetime.fromtimestamp(subscription["current_period_end"])
    )
    db.add(new_sub)

    # Log event
    audit = AuditLog(
        user_id=user_id,
        action="subscription_activated",
        details={"tier": tier, "subscription_id": subscription_id}
    )
    db.add(audit)

    logger.info(f"Subscription activated for user {user_id}: {tier}")


async def handle_subscription_updated(subscription: Dict, db: AsyncSession):
    """Handle subscription changes (upgrade/downgrade/cancel scheduled)"""
    subscription_id = subscription["id"]
    status = subscription["status"]

    # Update subscription record
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .values(
            status=status,
            current_period_end=datetime.fromtimestamp(subscription["current_period_end"]),
            cancel_at_period_end=subscription.get("cancel_at_period_end", False)
        )
    )

    logger.info(f"Subscription updated: {subscription_id} -> {status}")


async def handle_subscription_deleted(subscription: Dict, db: AsyncSession):
    """Subscription cancelled - downgrade to Free"""
    subscription_id = subscription["id"]

    # Find subscription
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    sub = result.scalar_one_or_none()

    if not sub:
        logger.error(f"Subscription not found: {subscription_id}")
        return

    # Downgrade user to Free tier
    await db.execute(
        update(User)
        .where(User.user_id == sub.user_id)
        .values(subscription_tier="free")
    )

    # Update subscription status
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .values(status="cancelled", cancelled_at=datetime.utcnow())
    )

    logger.info(f"Subscription cancelled for user {sub.user_id}")


async def handle_payment_succeeded(invoice: Dict, db: AsyncSession):
    """Payment succeeded - record in audit log"""
    customer_id = invoice["customer"]
    amount = invoice["amount_paid"] / 100  # Convert cents to euros

    # Find user
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()

    if user:
        audit = AuditLog(
            user_id=user.user_id,
            action="payment_succeeded",
            details={"amount_eur": amount, "invoice_id": invoice["id"]}
        )
        db.add(audit)

    logger.info(f"Payment succeeded: €{amount}")


async def handle_payment_failed(invoice: Dict, db: AsyncSession):
    """Payment failed - send dunning email"""
    customer_id = invoice["customer"]

    # Find user
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # TODO: Send email notification
        logger.warning(f"Payment failed for user {user.user_id}")

        audit = AuditLog(
            user_id=user.user_id,
            action="payment_failed",
            details={"invoice_id": invoice["id"]}
        )
        db.add(audit)


def map_stripe_price_to_tier(price_id: str) -> str:
    """Map Stripe Price ID to internal tier name"""
    price_map = {
        os.getenv("STRIPE_PRICE_STANDARD"): "standard",
        os.getenv("STRIPE_PRICE_PRO"): "pro",
        os.getenv("STRIPE_PRICE_ENTERPRISE"): "enterprise"
    }
    return price_map.get(price_id, "free")
```

#### 3. Billing API Endpoints

**`backend/api/billing.py`** - Billing routes
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from middleware.auth import get_current_user
from models import User
from billing.stripe_service import StripeService

router = APIRouter()

class CheckoutRequest(BaseModel):
    tier: str  # standard, pro, enterprise

@router.post("/checkout")
async def create_checkout(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create Stripe Checkout Session"""
    if request.tier not in ["standard", "pro", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid tier")

    if current_user.subscription_tier == request.tier:
        raise HTTPException(status_code=400, detail="Already on this plan")

    try:
        session = StripeService.create_checkout_session(
            user_id=str(current_user.user_id),
            user_email=current_user.email,
            tier=request.tier
        )

        return session

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portal")
async def create_portal_session(
    current_user: User = Depends(get_current_user)
):
    """Create Customer Portal session"""
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No active subscription")

    try:
        session = StripeService.create_customer_portal_session(
            customer_id=current_user.stripe_customer_id
        )

        return session

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans")
async def get_plans():
    """Return available subscription plans"""
    return {
        "plans": [
            {
                "id": "free",
                "name": "Free",
                "price_eur": 0,
                "features": [
                    "5 AI queries per day",
                    "1 alert",
                    "Basic tender search"
                ]
            },
            {
                "id": "standard",
                "name": "Standard",
                "price_eur": 99,
                "features": [
                    "100 AI queries per day",
                    "10 alerts",
                    "Advanced search filters",
                    "Email support"
                ]
            },
            {
                "id": "pro",
                "name": "Pro",
                "price_eur": 395,
                "features": [
                    "500 AI queries per day",
                    "50 alerts",
                    "API access",
                    "Priority support",
                    "Custom reports"
                ]
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "price_eur": 1495,
                "features": [
                    "Unlimited AI queries",
                    "Unlimited alerts",
                    "Dedicated account manager",
                    "Custom integrations",
                    "SLA guarantee"
                ]
            }
        ]
    }
```

#### 4. Database Models

**`backend/models.py`** - Add Subscription model
```python
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Subscription(Base):
    __tablename__ = "subscriptions"

    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True)
    stripe_customer_id = Column(String(255))
    tier = Column(String(50))  # free, standard, pro, enterprise
    status = Column(String(50))  # active, cancelled, past_due
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    cancelled_at = Column(DateTime)
    created_at = Column(DateTime, server_default="CURRENT_TIMESTAMP")
```

#### 5. Testing

**`backend/tests/test_billing.py`**
```python
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_create_checkout():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login first
        login_response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        token = login_response.json()["access_token"]

        # Create checkout
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"tier": "standard"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert "url" in response.json()
        assert response.json()["url"].startswith("https://checkout.stripe.com")


@pytest.mark.asyncio
async def test_get_plans():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/billing/plans")

        assert response.status_code == 200
        plans = response.json()["plans"]
        assert len(plans) == 4
        assert plans[0]["id"] == "free"
        assert plans[1]["price_eur"] == 99
```

### Documentation Deliverables

**`backend/billing/README.md`** - Stripe setup guide
**`backend/billing/TESTING.md`** - How to test with Stripe CLI
**`backend/billing/audit_report.md`** - Self-audit report

---

## VALIDATION CHECKLIST

Before handoff:
- [ ] Stripe products and prices created in Stripe Dashboard
- [ ] Checkout session creates successfully and redirects to Stripe
- [ ] Webhook endpoint accessible (use ngrok for local testing)
- [ ] Webhook signature verification works
- [ ] `checkout.session.completed` event activates subscription
- [ ] `customer.subscription.deleted` event downgrades user to Free
- [ ] Customer Portal link generation works
- [ ] Tier enforcement blocks Free user after 5 AI queries
- [ ] Tests pass: `pytest backend/tests/test_billing.py`
- [ ] No hardcoded Stripe keys (environment variables)
- [ ] Webhook events logged in audit_log table
- [ ] Idempotent webhook processing (duplicate events handled)

---

## INTEGRATION POINTS

### Handoff to Frontend Agent
**Required**: Frontend needs to call `/billing/checkout` and redirect user to Stripe URL

**Frontend Integration**:
```typescript
// frontend/lib/api.ts
export const createCheckout = async (tier: string) => {
  const response = await api.post('/billing/checkout', { tier })
  window.location.href = response.data.url  // Redirect to Stripe
}
```

### Handoff from Backend Agent
**Required**: Backend must have user authentication and tier enforcement middleware

---

## SUCCESS CRITERIA

- ✅ All 4 subscription tiers configured in Stripe
- ✅ Checkout flow functional end-to-end
- ✅ Webhooks process all critical events correctly
- ✅ Tier limits enforced (Free user blocked after quota)
- ✅ Customer Portal accessible for billing self-service
- ✅ Subscription status synced between Stripe and database
- ✅ Payment failures logged and handled
- ✅ Tests pass (>80% coverage)
- ✅ Zero hardcoded secrets
- ✅ Audit report ✅ READY

---

**END OF BILLING AGENT DEFINITION**
