"""
Pytest configuration and fixtures for integration tests.
Provides test database setup, mock services, and data factories.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from unittest.mock import Mock, patch

from main import app
from database import Base, get_db
from models import Tender, TenderStatus
from models_auth import UserAuth, EmailVerification, UserRole
from models_billing import (
    SubscriptionPlan, UserSubscription, Payment, Invoice,
    SubscriptionStatus, Currency, PaymentStatus, InvoiceStatus, PaymentMethodType
)
from services.auth_service import AuthService
from services.email_service import EmailService
from services.stripe_service import StripeService


# Test database URL (use in-memory SQLite for fast tests)
TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/nabavkidata_test"


@pytest.fixture(scope="session")
def engine():
    """Create test database engine"""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db(engine):
    """Create a new database session for each test"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Rollback and cleanup after each test
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def client(db):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# Mock Services

@pytest.fixture
def mock_email_service(monkeypatch):
    """Mock email service to prevent actual email sending"""
    mock = Mock(spec=EmailService)
    mock.send_verification_email.return_value = True
    mock.send_password_reset_email.return_value = True
    mock.send_welcome_email.return_value = True

    monkeypatch.setattr("services.email_service.EmailService.send_verification_email", mock.send_verification_email)
    monkeypatch.setattr("services.email_service.EmailService.send_password_reset_email", mock.send_password_reset_email)

    return mock


@pytest.fixture
def mock_stripe(monkeypatch):
    """Mock Stripe service for payment testing"""
    mock = Mock(spec=StripeService)
    mock.create_checkout_session.return_value = {
        "id": "cs_test_123",
        "url": "https://checkout.stripe.com/test"
    }
    mock.create_customer.return_value = {"id": "cus_test_123"}
    mock.create_subscription.return_value = {"id": "sub_test_123"}

    monkeypatch.setattr("services.stripe_service.StripeService", lambda: mock)

    return mock


@pytest.fixture
def mock_openai(monkeypatch):
    """Mock OpenAI service for RAG testing"""
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="This is a test response from RAG"))]

    mock = Mock()
    mock.chat.completions.create.return_value = mock_response

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: mock)

    return mock


# Test User Fixtures

@pytest.fixture
def test_user(db: Session) -> UserAuth:
    """Create a test user"""
    auth_service = AuthService()

    user = UserAuth(
        user_id=uuid.uuid4(),
        email="testuser@example.com",
        hashed_password=auth_service.hash_password("TestPass123!"),
        full_name="Test User",
        is_verified=True,
        is_active=True,
        role=UserRole.user
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@pytest.fixture
def admin_user(db: Session) -> UserAuth:
    """Create an admin user"""
    auth_service = AuthService()

    user = UserAuth(
        user_id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password=auth_service.hash_password("AdminPass123!"),
        full_name="Admin User",
        is_verified=True,
        is_active=True,
        role=UserRole.admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# Test Tender Fixtures

@pytest.fixture
def test_tenders(db: Session):
    """Create test tenders"""
    tenders = []

    for i in range(10):
        tender = Tender(
            tender_id=uuid.uuid4(),
            title=f"Test Tender {i}",
            description=f"Description for test tender {i}",
            status=TenderStatus.active if i % 2 == 0 else TenderStatus.closed,
            budget_mkd=Decimal(str(100000 * (i + 1))),
            published_date=datetime.utcnow() - timedelta(days=i),
            deadline=datetime.utcnow() + timedelta(days=30 - i),
            category="infrastructure" if i % 3 == 0 else "technology",
            contracting_authority=f"Authority {i}"
        )
        tenders.append(tender)
        db.add(tender)

    db.commit()
    for tender in tenders:
        db.refresh(tender)

    return tenders


# Subscription and Billing Fixtures

@pytest.fixture
def test_subscription_plans(db: Session):
    """Create test subscription plans"""
    plans_data = [
        {
            "name": "basic",
            "display_name": "Basic Plan",
            "description": "Basic features for small businesses",
            "price_mkd": Decimal("2000.00"),
            "price_eur": Decimal("35.00"),
            "monthly_query_limit": 100,
            "max_alerts": 5,
            "max_saved_searches": 10
        },
        {
            "name": "professional",
            "display_name": "Professional Plan",
            "description": "Advanced features for growing businesses",
            "price_mkd": Decimal("5000.00"),
            "price_eur": Decimal("85.00"),
            "monthly_query_limit": 500,
            "max_alerts": 20,
            "max_saved_searches": 50,
            "api_access": True
        },
        {
            "name": "enterprise",
            "display_name": "Enterprise Plan",
            "description": "Full features for large organizations",
            "price_mkd": Decimal("10000.00"),
            "price_eur": Decimal("170.00"),
            "monthly_query_limit": -1,  # Unlimited
            "max_alerts": -1,
            "max_saved_searches": -1,
            "api_access": True,
            "priority_support": True
        }
    ]

    plans = []
    for plan_data in plans_data:
        plan = SubscriptionPlan(
            plan_id=uuid.uuid4(),
            **plan_data
        )
        plans.append(plan)
        db.add(plan)

    db.commit()
    for plan in plans:
        db.refresh(plan)

    return plans


@pytest.fixture
def test_subscription(db: Session, test_user: UserAuth, test_subscription_plans):
    """Create a test subscription for a user"""
    plan = test_subscription_plans[0]  # Basic plan

    subscription = UserSubscription(
        subscription_id=uuid.uuid4(),
        user_id=test_user.user_id,
        plan_id=plan.plan_id,
        status=SubscriptionStatus.active,
        start_date=datetime.utcnow(),
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        stripe_subscription_id="sub_test_123",
        stripe_customer_id="cus_test_123"
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return subscription


# Authentication Helpers

@pytest.fixture
def auth_headers(client: TestClient, test_user: UserAuth):
    """Get authentication headers for test user"""
    login_response = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "TestPass123!"
    })
    access_token = login_response.json()["access_token"]

    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_headers(client: TestClient, admin_user: UserAuth):
    """Get authentication headers for admin user"""
    login_response = client.post("/api/auth/login", json={
        "email": admin_user.email,
        "password": "AdminPass123!"
    })
    access_token = login_response.json()["access_token"]

    return {"Authorization": f"Bearer {access_token}"}


# Cleanup Fixtures

@pytest.fixture(autouse=True)
def cleanup_database(db: Session):
    """Cleanup database after each test"""
    yield

    # Clean up all tables in reverse order of dependencies
    db.query(Payment).delete()
    db.query(Invoice).delete()
    db.query(UserSubscription).delete()
    db.query(SubscriptionPlan).delete()
    db.query(EmailVerification).delete()
    db.query(Tender).delete()
    db.query(UserAuth).delete()

    db.commit()
