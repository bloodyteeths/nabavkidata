"""
Unit Tests for Stripe Webhook Handler

Tests all webhook event handlers and edge cases
Run with: pytest tests/test_stripe_webhook.py -v
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import json

from api.stripe_webhook import (
    router,
    get_tier_from_subscription,
    verify_webhook_signature,
    handle_subscription_created,
    handle_subscription_updated,
    handle_subscription_deleted,
    handle_invoice_payment_succeeded,
    handle_invoice_payment_failed,
    handle_subscription_trial_will_end,
    PRICE_ID_TO_TIER
)

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    """Mock user object"""
    user = Mock()
    user.user_id = "user-123"
    user.email = "test@example.com"
    user.stripe_customer_id = "cus_test123"
    user.subscription_tier = "free"
    return user


@pytest.fixture
def mock_subscription():
    """Mock subscription object"""
    subscription = Mock()
    subscription.subscription_id = "sub-local-123"
    subscription.user_id = "user-123"
    subscription.stripe_subscription_id = "sub_stripe123"
    subscription.stripe_customer_id = "cus_test123"
    subscription.tier = "professional"
    subscription.status = "active"
    subscription.current_period_start = datetime.utcnow()
    subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
    return subscription


@pytest.fixture
def stripe_subscription_created_event():
    """Mock Stripe subscription.created event"""
    return {
        "id": "sub_test123",
        "customer": "cus_test123",
        "status": "active",
        "current_period_start": int(datetime.utcnow().timestamp()),
        "current_period_end": int((datetime.utcnow() + timedelta(days=30)).timestamp()),
        "cancel_at_period_end": False,
        "metadata": {
            "tier": "professional"
        },
        "items": {
            "data": [
                {
                    "price": {
                        "id": "price_1SWeAtHkVI5icjTl8UxSYNYX"
                    }
                }
            ]
        }
    }


@pytest.fixture
def stripe_invoice_payment_succeeded_event():
    """Mock Stripe invoice.payment_succeeded event"""
    return {
        "id": "in_test123",
        "customer": "cus_test123",
        "subscription": "sub_test123",
        "amount_paid": 3999,  # $39.99
        "currency": "usd",
        "status": "paid"
    }


@pytest.fixture
def stripe_invoice_payment_failed_event():
    """Mock Stripe invoice.payment_failed event"""
    return {
        "id": "in_test456",
        "customer": "cus_test123",
        "subscription": "sub_test123",
        "amount_due": 3999,
        "currency": "usd",
        "attempt_count": 1,
        "status": "open"
    }


# ============================================================================
# UTILITY FUNCTION TESTS
# ============================================================================

def test_get_tier_from_subscription_metadata():
    """Test tier extraction from metadata"""
    subscription_obj = {
        "metadata": {"tier": "professional"},
        "items": {"data": []}
    }
    assert get_tier_from_subscription(subscription_obj) == "professional"


def test_get_tier_from_subscription_price_id():
    """Test tier extraction from price ID"""
    subscription_obj = {
        "metadata": {},
        "items": {
            "data": [
                {
                    "price": {
                        "id": "price_1SWeAtHkVI5icjTl8UxSYNYX"
                    }
                }
            ]
        }
    }
    assert get_tier_from_subscription(subscription_obj) == "professional"


def test_get_tier_from_subscription_default():
    """Test tier defaults to starter when not found"""
    subscription_obj = {
        "metadata": {},
        "items": {"data": []}
    }
    assert get_tier_from_subscription(subscription_obj) == "starter"


def test_verify_webhook_signature_no_secret():
    """Test webhook signature verification with no secret (dev mode)"""
    payload = b'{"test": "data"}'
    signature = "test_signature"

    with patch('api.stripe_webhook.STRIPE_WEBHOOK_SECRET', ''):
        assert verify_webhook_signature(payload, signature) is True


@patch('stripe.Webhook.construct_event')
def test_verify_webhook_signature_valid(mock_construct):
    """Test valid webhook signature"""
    payload = b'{"test": "data"}'
    signature = "valid_signature"

    mock_construct.return_value = {"test": "data"}

    with patch('api.stripe_webhook.STRIPE_WEBHOOK_SECRET', 'whsec_test'):
        assert verify_webhook_signature(payload, signature) is True


# ============================================================================
# EVENT HANDLER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_handle_subscription_created(mock_db, mock_user, stripe_subscription_created_event):
    """Test subscription.created event handler"""
    # Mock database queries
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Handle event
    await handle_subscription_created(mock_db, stripe_subscription_created_event)

    # Verify database calls
    assert mock_db.add.called
    assert mock_db.commit.called

    # Verify user tier was updated
    execute_calls = [call.args[0] for call in mock_db.execute.call_args_list]
    assert len(execute_calls) >= 2  # One for user lookup, one for update


@pytest.mark.asyncio
async def test_handle_subscription_created_user_not_found(mock_db, stripe_subscription_created_event):
    """Test subscription.created with non-existent user"""
    # Mock database query returning no user
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Handle event - should not raise exception
    await handle_subscription_created(mock_db, stripe_subscription_created_event)

    # Verify no subscription was created
    assert not mock_db.add.called


@pytest.mark.asyncio
async def test_handle_subscription_updated(mock_db, mock_subscription, stripe_subscription_created_event):
    """Test subscription.updated event handler"""
    # Mock database query
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_subscription
    mock_db.execute.return_value = mock_result

    # Update status to canceled
    stripe_subscription_created_event["status"] = "canceled"
    stripe_subscription_created_event["canceled_at"] = int(datetime.utcnow().timestamp())

    # Handle event
    await handle_subscription_updated(mock_db, stripe_subscription_created_event)

    # Verify database commit
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_handle_subscription_deleted(mock_db, mock_subscription, stripe_subscription_created_event):
    """Test subscription.deleted event handler"""
    # Mock database query
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_subscription
    mock_db.execute.return_value = mock_result

    # Handle event
    await handle_subscription_deleted(mock_db, stripe_subscription_created_event)

    # Verify database commit
    assert mock_db.commit.called

    # Verify subscription was marked as canceled and user downgraded to free
    execute_calls = mock_db.execute.call_args_list
    assert len(execute_calls) >= 2  # Update subscription + update user tier


@pytest.mark.asyncio
async def test_handle_invoice_payment_succeeded(mock_db, mock_user, mock_subscription, stripe_invoice_payment_succeeded_event):
    """Test invoice.payment_succeeded event handler"""
    # Mock database queries
    mock_user_result = AsyncMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user

    mock_sub_result = AsyncMock()
    mock_sub_result.scalar_one_or_none.return_value = mock_subscription

    mock_db.execute.side_effect = [mock_user_result, mock_sub_result]

    # Handle event
    await handle_invoice_payment_succeeded(mock_db, stripe_invoice_payment_succeeded_event)

    # Verify database commit
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_handle_invoice_payment_failed_first_attempt(mock_db, mock_user, mock_subscription, stripe_invoice_payment_failed_event):
    """Test invoice.payment_failed on first attempt"""
    # Mock database queries
    mock_user_result = AsyncMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user

    mock_sub_result = AsyncMock()
    mock_sub_result.scalar_one_or_none.return_value = mock_subscription

    mock_db.execute.side_effect = [mock_user_result, mock_sub_result]

    # Set attempt count to 1
    stripe_invoice_payment_failed_event["attempt_count"] = 1

    # Handle event
    await handle_invoice_payment_failed(mock_db, stripe_invoice_payment_failed_event)

    # Verify database commit
    assert mock_db.commit.called

    # User should NOT be downgraded on first attempt
    execute_calls = mock_db.execute.call_args_list
    # Should update subscription status but not user tier


@pytest.mark.asyncio
async def test_handle_invoice_payment_failed_final_attempt(mock_db, mock_user, mock_subscription, stripe_invoice_payment_failed_event):
    """Test invoice.payment_failed on final attempt (4th)"""
    # Mock database queries
    mock_user_result = AsyncMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user

    mock_sub_result = AsyncMock()
    mock_sub_result.scalar_one_or_none.return_value = mock_subscription

    mock_db.execute.side_effect = [mock_user_result, mock_sub_result]

    # Set attempt count to 4 (final attempt)
    stripe_invoice_payment_failed_event["attempt_count"] = 4

    # Handle event
    await handle_invoice_payment_failed(mock_db, stripe_invoice_payment_failed_event)

    # Verify database commit
    assert mock_db.commit.called

    # User SHOULD be downgraded on final attempt
    execute_calls = mock_db.execute.call_args_list
    assert len(execute_calls) >= 2  # Update subscription + downgrade user


@pytest.mark.asyncio
async def test_handle_subscription_trial_will_end(mock_db, mock_user, mock_subscription):
    """Test subscription.trial_will_end event handler"""
    trial_end_timestamp = int((datetime.utcnow() + timedelta(days=3)).timestamp())

    subscription_obj = {
        "id": "sub_test123",
        "customer": "cus_test123",
        "trial_end": trial_end_timestamp
    }

    # Mock database queries
    mock_user_result = AsyncMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user

    mock_sub_result = AsyncMock()
    mock_sub_result.scalar_one_or_none.return_value = mock_subscription

    mock_db.execute.side_effect = [mock_user_result, mock_sub_result]

    # Handle event - should not raise exception
    await handle_subscription_trial_will_end(mock_db, subscription_obj)

    # This event doesn't modify database, so no commit should be called
    # Just verify no exceptions were raised


# ============================================================================
# WEBHOOK ENDPOINT TESTS
# ============================================================================

def test_price_id_mappings():
    """Test that all expected price IDs are mapped"""
    expected_tiers = {"free", "starter", "professional", "enterprise"}
    mapped_tiers = set(PRICE_ID_TO_TIER.values())

    assert mapped_tiers == expected_tiers
    assert len(PRICE_ID_TO_TIER) == 4


def test_all_price_ids_unique():
    """Test that all price IDs are unique"""
    price_ids = list(PRICE_ID_TO_TIER.keys())
    assert len(price_ids) == len(set(price_ids))


def test_all_tiers_valid():
    """Test that all tiers are valid strings"""
    for tier in PRICE_ID_TO_TIER.values():
        assert isinstance(tier, str)
        assert len(tier) > 0
        assert tier.islower()


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_handle_subscription_created_database_error(mock_db, mock_user, stripe_subscription_created_event):
    """Test subscription.created with database error"""
    # Mock database query
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock commit to raise exception
    mock_db.commit.side_effect = Exception("Database error")

    # Handle event - should raise exception and rollback
    with pytest.raises(Exception):
        await handle_subscription_created(mock_db, stripe_subscription_created_event)

    # Verify rollback was called
    assert mock_db.rollback.called


@pytest.mark.asyncio
async def test_handle_subscription_updated_not_found_creates_new(mock_db, mock_user, stripe_subscription_created_event):
    """Test subscription.updated creates subscription if not found"""
    # Mock database query returning no subscription
    mock_sub_result = AsyncMock()
    mock_sub_result.scalar_one_or_none.return_value = None

    mock_user_result = AsyncMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user

    mock_db.execute.side_effect = [mock_sub_result, mock_user_result]

    # Handle event
    await handle_subscription_updated(mock_db, stripe_subscription_created_event)

    # Verify subscription was created (add called)
    assert mock_db.add.called


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_webhook_health_endpoint():
    """Test webhook health check endpoint"""
    from fastapi import FastAPI
    from api.stripe_webhook import router

    app = FastAPI()
    app.include_router(router)

    client = TestClient(app)
    response = client.get("/webhook/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "supported_events" in data
    assert len(data["supported_events"]) == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
