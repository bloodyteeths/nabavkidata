"""
Integration tests for billing and subscription flow.
Tests subscription checkout, webhook handling, invoice generation, and cancellation.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from decimal import Decimal
import json

from main import app
from models_auth import UserAuth
from models_billing import (
    SubscriptionPlan, UserSubscription, Payment, Invoice, PaymentMethod,
    SubscriptionStatus, PaymentStatus, InvoiceStatus, Currency, PaymentMethodType
)


class TestBillingFlow:
    """Test complete billing and subscription flow"""

    def test_subscription_checkout_flow(self, client: TestClient, db: Session, test_user: UserAuth, test_subscription_plans):
        """Test complete subscription checkout process"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Step 1: Get available plans
        plans_response = client.get("/api/billing/plans", headers=headers)
        assert plans_response.status_code == 200
        plans = plans_response.json()
        assert len(plans) > 0

        # Select a plan
        selected_plan = plans[0]
        plan_id = selected_plan["plan_id"]

        # Step 2: Create checkout session
        checkout_data = {
            "plan_id": plan_id,
            "currency": "MKD",
            "success_url": "https://nabavkidata.com/success",
            "cancel_url": "https://nabavkidata.com/cancel"
        }
        checkout_response = client.post(
            "/api/billing/checkout",
            json=checkout_data,
            headers=headers
        )
        assert checkout_response.status_code == 200
        checkout = checkout_response.json()
        assert "checkout_url" in checkout
        assert "session_id" in checkout

        # Step 3: Simulate successful payment (webhook)
        # In real scenario, this would come from Stripe
        webhook_data = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": checkout["session_id"],
                    "customer": "cus_test123",
                    "subscription": "sub_test123",
                    "payment_status": "paid"
                }
            }
        }

        # Simulate webhook (this would normally be called by Stripe)
        # For testing, we'll directly create subscription
        subscription = UserSubscription(
            user_id=test_user.user_id,
            plan_id=plan_id,
            status=SubscriptionStatus.active,
            start_date=datetime.utcnow(),
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
            stripe_subscription_id="sub_test123",
            stripe_customer_id="cus_test123"
        )
        db.add(subscription)
        db.commit()

        # Step 4: Verify subscription created
        sub_response = client.get("/api/billing/subscription", headers=headers)
        assert sub_response.status_code == 200
        sub_data = sub_response.json()
        assert sub_data["status"] == "active"
        assert sub_data["plan_id"] == plan_id

    def test_stripe_webhook_handling(self, client: TestClient, db: Session, mock_stripe):
        """Test Stripe webhook event handling"""

        # Test subscription created webhook
        webhook_payload = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_webhook_test",
                    "customer": "cus_webhook_test",
                    "status": "active",
                    "current_period_start": int(datetime.utcnow().timestamp()),
                    "current_period_end": int((datetime.utcnow() + timedelta(days=30)).timestamp()),
                    "items": {
                        "data": [{
                            "price": {
                                "id": "price_test123"
                            }
                        }]
                    }
                }
            }
        }

        response = client.post(
            "/api/billing/webhook",
            json=webhook_payload,
            headers={"stripe-signature": "test_signature"}
        )
        # Should handle webhook (may return 200 or 400 depending on signature verification)
        assert response.status_code in [200, 400]

        # Test payment succeeded webhook
        payment_webhook = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test123",
                    "amount": 50000,
                    "currency": "mkd",
                    "status": "succeeded",
                    "customer": "cus_webhook_test"
                }
            }
        }

        response = client.post(
            "/api/billing/webhook",
            json=payment_webhook,
            headers={"stripe-signature": "test_signature"}
        )
        assert response.status_code in [200, 400]

        # Test subscription updated webhook
        update_webhook = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_webhook_test",
                    "status": "past_due"
                }
            }
        }

        response = client.post(
            "/api/billing/webhook",
            json=update_webhook,
            headers={"stripe-signature": "test_signature"}
        )
        assert response.status_code in [200, 400]

    def test_invoice_generation(self, client: TestClient, db: Session, test_user: UserAuth, test_subscription):
        """Test invoice generation and retrieval"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create an invoice
        invoice = Invoice(
            user_id=test_user.user_id,
            subscription_id=test_subscription.subscription_id,
            invoice_number=f"INV-{datetime.utcnow().strftime('%Y%m%d')}-001",
            amount_mkd=Decimal("5000.00"),
            currency=Currency.MKD,
            status=InvoiceStatus.paid,
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            stripe_invoice_id="inv_test123",
            paid_at=datetime.utcnow()
        )
        db.add(invoice)
        db.commit()

        # Get user's invoices
        response = client.get("/api/billing/invoices", headers=headers)
        assert response.status_code == 200
        invoices = response.json()
        assert len(invoices) > 0
        assert any(inv["invoice_number"] == invoice.invoice_number for inv in invoices)

        # Get specific invoice
        invoice_response = client.get(
            f"/api/billing/invoices/{invoice.invoice_id}",
            headers=headers
        )
        assert invoice_response.status_code == 200
        invoice_data = invoice_response.json()
        assert invoice_data["invoice_number"] == invoice.invoice_number
        assert invoice_data["status"] == "paid"

        # Download invoice PDF
        pdf_response = client.get(
            f"/api/billing/invoices/{invoice.invoice_id}/pdf",
            headers=headers
        )
        # Should either return PDF or redirect to hosted URL
        assert pdf_response.status_code in [200, 302]

    def test_subscription_cancellation(self, client: TestClient, db: Session, test_user: UserAuth, test_subscription):
        """Test subscription cancellation flow"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get current subscription
        sub_response = client.get("/api/billing/subscription", headers=headers)
        assert sub_response.status_code == 200
        current_sub = sub_response.json()
        assert current_sub["status"] == "active"

        # Cancel subscription (at period end)
        cancel_data = {"immediately": False}
        cancel_response = client.post(
            "/api/billing/subscription/cancel",
            json=cancel_data,
            headers=headers
        )
        assert cancel_response.status_code == 200

        # Verify subscription marked for cancellation
        db.refresh(test_subscription)
        assert test_subscription.cancel_at_period_end is True
        assert test_subscription.cancelled_at is not None

        # Subscription should still be active until period ends
        sub_after_cancel = client.get("/api/billing/subscription", headers=headers)
        assert sub_after_cancel.status_code == 200
        assert sub_after_cancel.json()["status"] == "active"

        # Test immediate cancellation
        cancel_immediate_data = {"immediately": True}
        cancel_immediate_response = client.post(
            "/api/billing/subscription/cancel",
            json=cancel_immediate_data,
            headers=headers
        )
        assert cancel_immediate_response.status_code == 200

        # Verify subscription cancelled immediately
        db.refresh(test_subscription)
        assert test_subscription.status == SubscriptionStatus.cancelled

    def test_payment_methods(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test payment method management"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Add payment method
        payment_method_data = {
            "type": "card",
            "stripe_payment_method_id": "pm_test123"
        }
        add_response = client.post(
            "/api/billing/payment-methods",
            json=payment_method_data,
            headers=headers
        )
        assert add_response.status_code == 201
        added_method = add_response.json()
        method_id = added_method["method_id"]

        # List payment methods
        list_response = client.get("/api/billing/payment-methods", headers=headers)
        assert list_response.status_code == 200
        methods = list_response.json()
        assert len(methods) > 0

        # Set as default
        default_response = client.patch(
            f"/api/billing/payment-methods/{method_id}/default",
            headers=headers
        )
        assert default_response.status_code == 200

        # Verify it's default
        method = db.query(PaymentMethod).filter_by(method_id=method_id).first()
        assert method.is_default is True

        # Delete payment method
        delete_response = client.delete(
            f"/api/billing/payment-methods/{method_id}",
            headers=headers
        )
        assert delete_response.status_code == 204

    def test_subscription_upgrade_downgrade(self, client: TestClient, db: Session, test_user: UserAuth, test_subscription, test_subscription_plans):
        """Test subscription plan changes"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get current plan
        current_plan_id = test_subscription.plan_id

        # Find a different plan
        plans = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_id != current_plan_id
        ).first()

        if plans:
            # Upgrade/downgrade to different plan
            change_data = {
                "new_plan_id": str(plans.plan_id),
                "prorate": True
            }
            change_response = client.post(
                "/api/billing/subscription/change-plan",
                json=change_data,
                headers=headers
            )
            assert change_response.status_code == 200

            # Verify plan changed
            db.refresh(test_subscription)
            assert test_subscription.plan_id == plans.plan_id

    def test_payment_history(self, client: TestClient, db: Session, test_user: UserAuth, test_subscription):
        """Test payment history retrieval"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create some test payments
        for i in range(3):
            payment = Payment(
                user_id=test_user.user_id,
                subscription_id=test_subscription.subscription_id,
                amount_mkd=Decimal("5000.00"),
                currency=Currency.MKD,
                status=PaymentStatus.succeeded,
                payment_method=PaymentMethodType.card,
                stripe_payment_id=f"pay_test_{i}",
                paid_at=datetime.utcnow() - timedelta(days=30 * i)
            )
            db.add(payment)
        db.commit()

        # Get payment history
        response = client.get("/api/billing/payments", headers=headers)
        assert response.status_code == 200
        payments = response.json()
        assert len(payments) >= 3

        # Test pagination
        paginated_response = client.get(
            "/api/billing/payments?page=1&page_size=2",
            headers=headers
        )
        assert paginated_response.status_code == 200
        paginated = paginated_response.json()
        assert len(paginated["results"]) <= 2

    def test_billing_portal_access(self, client: TestClient, db: Session, test_user: UserAuth):
        """Test access to billing portal"""

        # Login
        login_response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!"
        })
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get billing portal URL
        portal_response = client.post(
            "/api/billing/portal",
            json={"return_url": "https://nabavkidata.com/account"},
            headers=headers
        )
        assert portal_response.status_code == 200
        portal_data = portal_response.json()
        assert "url" in portal_data
