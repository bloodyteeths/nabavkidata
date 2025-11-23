"""
Billing and Subscription Models for nabavkidata.com
Handles subscription plans, user subscriptions, payments, invoices, and payment methods
"""
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Boolean, Enum as SQLEnum, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from database import Base


class SubscriptionStatus(enum.Enum):
    """Subscription status enumeration"""
    active = "active"
    cancelled = "cancelled"
    expired = "expired"
    past_due = "past_due"


class PaymentStatus(enum.Enum):
    """Payment status enumeration"""
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


class InvoiceStatus(enum.Enum):
    """Invoice status enumeration"""
    draft = "draft"
    open = "open"
    paid = "paid"
    void = "void"
    uncollectible = "uncollectible"


class Currency(enum.Enum):
    """Currency enumeration"""
    MKD = "MKD"
    EUR = "EUR"


class PaymentMethodType(enum.Enum):
    """Payment method type enumeration"""
    card = "card"
    bank_transfer = "bank_transfer"
    paypal = "paypal"


class SubscriptionPlan(Base):
    """
    Subscription plan model
    Defines available subscription tiers with pricing and features
    """
    __tablename__ = "subscription_plans"

    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Pricing
    price_mkd = Column(Numeric(10, 2), nullable=False)
    price_eur = Column(Numeric(10, 2), nullable=False)

    # Plan configuration
    features_json = Column(JSONB, nullable=False, default={})
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Stripe integration
    stripe_price_id_mkd = Column(String(255))
    stripe_price_id_eur = Column(String(255))
    stripe_product_id = Column(String(255))

    # Limits and quotas
    monthly_query_limit = Column(Integer, nullable=False, default=100)
    max_alerts = Column(Integer, nullable=False, default=5)
    max_saved_searches = Column(Integer, nullable=False, default=10)
    api_access = Column(Boolean, default=False, nullable=False)
    priority_support = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    subscriptions = relationship("UserSubscription", back_populates="plan")

    def __repr__(self):
        return f"<SubscriptionPlan(name={self.name}, price_mkd={self.price_mkd}, is_active={self.is_active})>"


class UserSubscription(Base):
    """
    User subscription model
    Tracks user's subscription status and billing cycle
    """
    __tablename__ = "user_subscriptions"

    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.plan_id"), nullable=False, index=True)

    # Subscription status
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.active, nullable=False, index=True)

    # Billing cycle
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)

    # Renewal settings
    auto_renew = Column(Boolean, default=True, nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)

    # Trial information
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)

    # Stripe integration
    stripe_subscription_id = Column(String(255), unique=True, index=True)
    stripe_customer_id = Column(String(255), index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserSubscription(user_id={self.user_id}, plan={self.plan_id}, status={self.status})>"

    @property
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status == SubscriptionStatus.active and datetime.utcnow() < self.current_period_end

    @property
    def is_trial(self):
        """Check if subscription is in trial period"""
        if not self.trial_start or not self.trial_end:
            return False
        return self.trial_start <= datetime.utcnow() <= self.trial_end


class Payment(Base):
    """
    Payment model
    Records all payment transactions
    """
    __tablename__ = "payments"

    payment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("user_subscriptions.subscription_id", ondelete="SET NULL"), index=True)

    # Payment details
    amount_mkd = Column(Numeric(10, 2), nullable=True)
    amount_eur = Column(Numeric(10, 2), nullable=True)
    currency = Column(SQLEnum(Currency), nullable=False)

    # Status and method
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.pending, nullable=False, index=True)
    payment_method = Column(SQLEnum(PaymentMethodType), nullable=False)

    # Stripe integration
    stripe_payment_id = Column(String(255), unique=True, index=True)
    stripe_payment_intent_id = Column(String(255), unique=True, index=True)
    stripe_charge_id = Column(String(255))

    # Payment metadata
    description = Column(Text)
    payment_metadata = Column(JSONB, default={})

    # Failure information
    failure_code = Column(String(100))
    failure_message = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)

    # Relationships
    subscription = relationship("UserSubscription", back_populates="payments")

    def __repr__(self):
        return f"<Payment(payment_id={self.payment_id}, status={self.status}, amount={self.amount_mkd or self.amount_eur} {self.currency.value})>"


class Invoice(Base):
    """
    Invoice model
    Stores invoice information for subscriptions and payments
    """
    __tablename__ = "invoices"

    invoice_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("user_subscriptions.subscription_id", ondelete="SET NULL"), index=True)

    # Invoice details
    invoice_number = Column(String(100), unique=True, nullable=False, index=True)
    amount_mkd = Column(Numeric(10, 2), nullable=True)
    amount_eur = Column(Numeric(10, 2), nullable=True)
    currency = Column(SQLEnum(Currency), nullable=False)

    # Tax information
    tax_amount = Column(Numeric(10, 2), default=0)
    tax_percent = Column(Numeric(5, 2), default=0)

    # Status
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.draft, nullable=False, index=True)

    # PDF and links
    pdf_url = Column(Text)
    hosted_invoice_url = Column(Text)
    invoice_pdf_path = Column(Text)

    # Stripe integration
    stripe_invoice_id = Column(String(255), unique=True, index=True)

    # Invoice period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Due date
    due_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    voided_at = Column(DateTime, nullable=True)

    # Relationships
    subscription = relationship("UserSubscription", back_populates="invoices")

    def __repr__(self):
        return f"<Invoice(invoice_number={self.invoice_number}, status={self.status}, amount={self.amount_mkd or self.amount_eur} {self.currency.value})>"


class PaymentMethod(Base):
    """
    Payment method model
    Stores user's saved payment methods
    """
    __tablename__ = "payment_methods"

    method_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)

    # Method details
    type = Column(SQLEnum(PaymentMethodType), nullable=False)

    # Card information (for card type)
    last4 = Column(String(4))
    brand = Column(String(50))
    exp_month = Column(Integer)
    exp_year = Column(Integer)

    # Bank account information (for bank_transfer type)
    bank_name = Column(String(255))
    account_holder_name = Column(String(255))

    # PayPal information (for paypal type)
    paypal_email = Column(String(255))

    # Settings
    is_default = Column(Boolean, default=False, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Stripe integration
    stripe_payment_method_id = Column(String(255), unique=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<PaymentMethod(type={self.type}, last4={self.last4}, is_default={self.is_default})>"
