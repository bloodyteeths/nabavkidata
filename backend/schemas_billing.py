"""
Billing and Subscription Pydantic Schemas for nabavkidata.com
Request/response validation for billing and subscription endpoints
"""
from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration"""
    active = "active"
    cancelled = "cancelled"
    expired = "expired"
    past_due = "past_due"


class PaymentStatus(str, Enum):
    """Payment status enumeration"""
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


class InvoiceStatus(str, Enum):
    """Invoice status enumeration"""
    draft = "draft"
    open = "open"
    paid = "paid"
    void = "void"
    uncollectible = "uncollectible"


class Currency(str, Enum):
    """Currency enumeration"""
    MKD = "MKD"
    EUR = "EUR"


class PaymentMethodType(str, Enum):
    """Payment method type enumeration"""
    card = "card"
    bank_transfer = "bank_transfer"
    paypal = "paypal"


class PlanName(str, Enum):
    """Plan name enumeration"""
    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    PREMIUM = "PREMIUM"


# ============================================================================
# SUBSCRIPTION PLAN SCHEMAS
# ============================================================================

class SubscriptionPlanResponse(BaseModel):
    """Subscription plan response schema"""
    plan_id: UUID
    name: str
    display_name: str
    description: Optional[str]
    price_mkd: Decimal
    price_eur: Decimal
    features_json: Dict[str, Any]
    is_active: bool
    monthly_query_limit: int
    max_alerts: int
    max_saved_searches: int
    api_access: bool
    priority_support: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionPlanListResponse(BaseModel):
    """List of subscription plans"""
    total: int
    plans: List[SubscriptionPlanResponse]


# ============================================================================
# USER SUBSCRIPTION SCHEMAS
# ============================================================================

class UserSubscriptionResponse(BaseModel):
    """User subscription response schema"""
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    plan: Optional[SubscriptionPlanResponse]
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime]
    current_period_start: datetime
    current_period_end: datetime
    auto_renew: bool
    cancel_at_period_end: bool
    cancelled_at: Optional[datetime]
    trial_start: Optional[datetime]
    trial_end: Optional[datetime]
    stripe_subscription_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserSubscriptionCreate(BaseModel):
    """Create user subscription schema"""
    plan_id: UUID = Field(..., description="Subscription plan ID")
    payment_method_id: Optional[str] = Field(None, description="Stripe payment method ID")
    trial_days: Optional[int] = Field(None, ge=0, le=90, description="Trial period in days")


class UserSubscriptionUpdate(BaseModel):
    """Update user subscription schema"""
    plan_id: Optional[UUID] = Field(None, description="New plan ID to upgrade/downgrade")
    auto_renew: Optional[bool] = Field(None, description="Enable/disable auto-renewal")
    cancel_at_period_end: Optional[bool] = Field(None, description="Cancel at period end")


# ============================================================================
# CHECKOUT SESSION SCHEMAS
# ============================================================================

class CreateCheckoutSession(BaseModel):
    """Create Stripe checkout session request"""
    plan_id: UUID = Field(..., description="Subscription plan ID")
    success_url: HttpUrl = Field(..., description="URL to redirect on success")
    cancel_url: HttpUrl = Field(..., description="URL to redirect on cancel")
    currency: Currency = Field(Currency.MKD, description="Payment currency")
    trial_days: Optional[int] = Field(None, ge=0, le=90, description="Trial period in days")


class CheckoutSessionResponse(BaseModel):
    """Stripe checkout session response"""
    session_id: str = Field(..., description="Stripe checkout session ID")
    checkout_url: str = Field(..., description="URL to redirect user to Stripe checkout")
    expires_at: datetime = Field(..., description="Session expiration timestamp")


# ============================================================================
# PAYMENT WEBHOOK SCHEMAS
# ============================================================================

class PaymentWebhook(BaseModel):
    """Stripe payment webhook event data"""
    event_id: str = Field(..., description="Stripe event ID")
    event_type: str = Field(..., description="Stripe event type")
    data: Dict[str, Any] = Field(..., description="Event data payload")
    created: int = Field(..., description="Event creation timestamp")


# ============================================================================
# PAYMENT SCHEMAS
# ============================================================================

class PaymentResponse(BaseModel):
    """Payment response schema"""
    payment_id: UUID
    user_id: UUID
    subscription_id: Optional[UUID]
    amount_mkd: Optional[Decimal]
    amount_eur: Optional[Decimal]
    currency: Currency
    status: PaymentStatus
    payment_method: PaymentMethodType
    stripe_payment_id: Optional[str]
    description: Optional[str]
    failure_code: Optional[str]
    failure_message: Optional[str]
    created_at: datetime
    paid_at: Optional[datetime]
    refunded_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaymentHistoryResponse(BaseModel):
    """Payment history response with pagination"""
    total: int
    page: int
    page_size: int
    payments: List[PaymentResponse]


class PaymentCreate(BaseModel):
    """Create payment request (for manual/admin payments)"""
    user_id: UUID
    subscription_id: Optional[UUID]
    amount_mkd: Optional[Decimal] = Field(None, ge=0)
    amount_eur: Optional[Decimal] = Field(None, ge=0)
    currency: Currency
    payment_method: PaymentMethodType
    description: Optional[str] = Field(None, max_length=500)

    @validator('amount_mkd', 'amount_eur')
    def validate_amounts(cls, v, values):
        """Ensure at least one amount is provided"""
        if 'currency' in values:
            currency = values['currency']
            if currency == Currency.MKD and not values.get('amount_mkd'):
                raise ValueError('amount_mkd is required for MKD currency')
            if currency == Currency.EUR and not values.get('amount_eur'):
                raise ValueError('amount_eur is required for EUR currency')
        return v


# ============================================================================
# INVOICE SCHEMAS
# ============================================================================

class InvoiceResponse(BaseModel):
    """Invoice response schema"""
    invoice_id: UUID
    user_id: UUID
    subscription_id: Optional[UUID]
    invoice_number: str
    amount_mkd: Optional[Decimal]
    amount_eur: Optional[Decimal]
    currency: Currency
    tax_amount: Decimal
    tax_percent: Decimal
    status: InvoiceStatus
    pdf_url: Optional[str]
    hosted_invoice_url: Optional[str]
    stripe_invoice_id: Optional[str]
    period_start: datetime
    period_end: datetime
    due_date: Optional[datetime]
    created_at: datetime
    paid_at: Optional[datetime]
    voided_at: Optional[datetime]

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    """Invoice list response with pagination"""
    total: int
    page: int
    page_size: int
    invoices: List[InvoiceResponse]


# ============================================================================
# PAYMENT METHOD SCHEMAS
# ============================================================================

class PaymentMethodResponse(BaseModel):
    """Payment method response schema"""
    method_id: UUID
    user_id: UUID
    type: PaymentMethodType
    last4: Optional[str]
    brand: Optional[str]
    exp_month: Optional[int]
    exp_year: Optional[int]
    bank_name: Optional[str]
    account_holder_name: Optional[str]
    paypal_email: Optional[str]
    is_default: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentMethodListResponse(BaseModel):
    """List of user payment methods"""
    total: int
    payment_methods: List[PaymentMethodResponse]


class PaymentMethodCreate(BaseModel):
    """Create payment method request"""
    stripe_payment_method_id: str = Field(..., description="Stripe payment method ID")
    is_default: bool = Field(False, description="Set as default payment method")


class PaymentMethodUpdate(BaseModel):
    """Update payment method request"""
    is_default: Optional[bool] = Field(None, description="Set as default payment method")
    is_active: Optional[bool] = Field(None, description="Activate/deactivate payment method")


# ============================================================================
# BILLING PORTAL SCHEMAS
# ============================================================================

class BillingPortalSessionRequest(BaseModel):
    """Create Stripe billing portal session request"""
    return_url: HttpUrl = Field(..., description="URL to redirect after portal session")


class BillingPortalSessionResponse(BaseModel):
    """Stripe billing portal session response"""
    session_url: str = Field(..., description="URL to redirect user to billing portal")
    return_url: str = Field(..., description="Return URL after session")


# ============================================================================
# USAGE TRACKING SCHEMAS
# ============================================================================

class UsageStatsResponse(BaseModel):
    """Usage statistics for current billing period"""
    subscription_id: UUID
    plan_name: str
    queries_used: int
    queries_limit: int
    alerts_used: int
    alerts_limit: int
    saved_searches_used: int
    saved_searches_limit: int
    current_period_start: datetime
    current_period_end: datetime


# ============================================================================
# GENERIC RESPONSE SCHEMAS
# ============================================================================

class MessageResponse(BaseModel):
    """Generic success message response"""
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    """Generic error response"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
