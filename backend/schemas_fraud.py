"""
Pydantic Schemas for Fraud Prevention System
Request/Response models for fraud detection and rate limiting
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from datetime import datetime
from uuid import UUID


# ============================================================================
# FRAUD DETECTION SCHEMAS
# ============================================================================

class FingerprintData(BaseModel):
    """Browser and device fingerprint data"""
    device_fingerprint: str = Field(..., description="Device fingerprint hash")
    screen_resolution: Optional[str] = Field(None, description="Screen resolution (e.g., 1920x1080)")
    timezone: Optional[str] = Field(None, description="User timezone")
    language: Optional[str] = Field(None, description="Browser language")
    platform: Optional[str] = Field(None, description="Platform/OS")
    canvas_fingerprint: Optional[str] = Field(None, description="Canvas fingerprint")
    webgl_fingerprint: Optional[str] = Field(None, description="WebGL fingerprint")

    class Config:
        json_schema_extra = {
            "example": {
                "device_fingerprint": "a1b2c3d4e5f6...",
                "screen_resolution": "1920x1080",
                "timezone": "Europe/Skopje",
                "language": "mk-MK",
                "platform": "MacIntel",
                "canvas_fingerprint": "canvas_hash_123",
                "webgl_fingerprint": "webgl_hash_456"
            }
        }


class FraudCheckRequest(BaseModel):
    """Request for fraud check"""
    ip_address: str = Field(..., description="User's IP address")
    user_agent: str = Field(..., description="Browser user agent string")
    fingerprint_data: FingerprintData
    check_type: str = Field(default="query", description="Type of check: query, registration, payment")

    class Config:
        json_schema_extra = {
            "example": {
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
                "fingerprint_data": {
                    "device_fingerprint": "a1b2c3d4e5f6...",
                    "screen_resolution": "1920x1080",
                    "timezone": "Europe/Skopje"
                },
                "check_type": "query"
            }
        }


class FraudCheckResponse(BaseModel):
    """Response from fraud check"""
    is_allowed: bool = Field(..., description="Whether action is allowed")
    block_reason: Optional[str] = Field(None, description="Reason for blocking (if blocked)")
    redirect_to: Optional[str] = Field(None, description="URL to redirect to (if blocked)")
    details: Optional[Dict] = Field(None, description="Additional details")
    risk_score: Optional[int] = Field(None, description="Risk score (0-100)")

    class Config:
        json_schema_extra = {
            "example": {
                "is_allowed": True,
                "block_reason": None,
                "redirect_to": None,
                "details": {
                    "tier": "free",
                    "daily_limit": 3,
                    "daily_used": 1,
                    "daily_remaining": 2
                },
                "risk_score": 15
            }
        }


class FraudDetectionResponse(BaseModel):
    """Fraud detection record response"""
    detection_id: UUID
    user_id: UUID
    ip_address: str
    is_vpn: bool
    is_proxy: bool
    is_tor: bool
    device_fingerprint: str
    browser: Optional[str]
    os: Optional[str]
    device_type: Optional[str]
    risk_score: int
    is_suspicious: bool
    created_at: datetime
    last_seen: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "detection_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "ip_address": "192.168.1.1",
                "is_vpn": False,
                "is_proxy": False,
                "is_tor": False,
                "device_fingerprint": "a1b2c3d4e5f6...",
                "browser": "Chrome",
                "os": "macOS",
                "device_type": "desktop",
                "risk_score": 15,
                "is_suspicious": False,
                "created_at": "2024-01-01T00:00:00Z",
                "last_seen": "2024-01-01T12:00:00Z"
            }
        }


# ============================================================================
# RATE LIMITING SCHEMAS
# ============================================================================

class RateLimitResponse(BaseModel):
    """Rate limit status response"""
    user_id: UUID
    subscription_tier: str
    daily_query_count: int
    daily_limit: int
    daily_remaining: int
    monthly_query_count: int
    total_query_count: int
    trial_end_date: Optional[datetime]
    trial_expired: bool
    is_blocked: bool
    block_reason: Optional[str]
    daily_reset_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "subscription_tier": "free",
                "daily_query_count": 1,
                "daily_limit": 3,
                "daily_remaining": 2,
                "monthly_query_count": 15,
                "total_query_count": 45,
                "trial_end_date": "2024-01-15T00:00:00Z",
                "trial_expired": False,
                "is_blocked": False,
                "block_reason": None,
                "daily_reset_at": "2024-01-02T00:00:00Z"
            }
        }


class QueryLimitExceeded(BaseModel):
    """Response when query limit is exceeded"""
    error: str = "Rate limit exceeded"
    message: str
    limit_type: str = Field(..., description="daily or monthly")
    current_count: int
    limit: int
    reset_at: datetime
    redirect_to: str = "/pricing"

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Rate limit exceeded",
                "message": "Daily query limit reached (3 queries per day). Upgrade your plan for more queries.",
                "limit_type": "daily",
                "current_count": 3,
                "limit": 3,
                "reset_at": "2024-01-02T00:00:00Z",
                "redirect_to": "/pricing"
            }
        }


# ============================================================================
# SUSPICIOUS ACTIVITY SCHEMAS
# ============================================================================

class SuspiciousActivityResponse(BaseModel):
    """Suspicious activity record response"""
    activity_id: UUID
    user_id: Optional[UUID]
    activity_type: str
    severity: str
    description: str
    ip_address: Optional[str]
    email: Optional[str]
    action_taken: Optional[str]
    detected_at: datetime
    is_resolved: bool

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "activity_id": "123e4567-e89b-12d3-a456-426614174002",
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "activity_type": "vpn_usage_free_tier",
                "severity": "medium",
                "description": "VPN/Proxy usage detected on free tier",
                "ip_address": "192.168.1.1",
                "email": "user@example.com",
                "action_taken": "blocked",
                "detected_at": "2024-01-01T12:00:00Z",
                "is_resolved": False
            }
        }


class SuspiciousActivityList(BaseModel):
    """List of suspicious activities"""
    activities: List[SuspiciousActivityResponse]
    total_count: int
    unresolved_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "activities": [],
                "total_count": 5,
                "unresolved_count": 2
            }
        }


# ============================================================================
# DUPLICATE ACCOUNT SCHEMAS
# ============================================================================

class DuplicateAccountResponse(BaseModel):
    """Duplicate account detection response"""
    detection_id: UUID
    user_id: UUID
    duplicate_user_id: UUID
    match_type: str
    confidence_score: int
    matching_attributes: Dict
    is_confirmed: bool
    detected_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "detection_id": "123e4567-e89b-12d3-a456-426614174003",
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "duplicate_user_id": "123e4567-e89b-12d3-a456-426614174004",
                "match_type": "email_similarity",
                "confidence_score": 85,
                "matching_attributes": {
                    "email1": "test@gmail.com",
                    "email2": "test1@gmail.com"
                },
                "is_confirmed": False,
                "detected_at": "2024-01-01T12:00:00Z"
            }
        }


class DuplicateAccountList(BaseModel):
    """List of duplicate account detections"""
    duplicates: List[DuplicateAccountResponse]
    total_count: int
    high_confidence_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "duplicates": [],
                "total_count": 3,
                "high_confidence_count": 1
            }
        }


# ============================================================================
# BLOCKED RESOURCES SCHEMAS
# ============================================================================

class BlockedEmailCreate(BaseModel):
    """Create blocked email pattern"""
    email_pattern: str = Field(..., description="Email domain or pattern to block")
    block_type: str = Field(default="disposable", description="Type of block")
    reason: Optional[str] = Field(None, description="Reason for blocking")

    class Config:
        json_schema_extra = {
            "example": {
                "email_pattern": "tempmail.com",
                "block_type": "disposable",
                "reason": "Temporary email service"
            }
        }


class BlockedEmailResponse(BaseModel):
    """Blocked email response"""
    block_id: UUID
    email_pattern: str
    block_type: str
    reason: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BlockedIPCreate(BaseModel):
    """Create blocked IP"""
    ip_address: str = Field(..., description="IP address to block")
    reason: str = Field(..., description="Reason for blocking")
    block_type: str = Field(default="manual", description="Type of block")
    expires_at: Optional[datetime] = Field(None, description="Expiration date (null = permanent)")

    class Config:
        json_schema_extra = {
            "example": {
                "ip_address": "192.168.1.100",
                "reason": "Suspicious activity detected",
                "block_type": "automatic",
                "expires_at": "2024-12-31T23:59:59Z"
            }
        }


class BlockedIPResponse(BaseModel):
    """Blocked IP response"""
    block_id: UUID
    ip_address: str
    reason: Optional[str]
    block_type: str
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# FRAUD SUMMARY SCHEMAS
# ============================================================================

class UserFraudSummary(BaseModel):
    """Comprehensive fraud summary for a user"""
    user_id: UUID
    rate_limit: Dict
    fraud_detections_count: int
    latest_risk_score: int
    suspicious_activities_count: int
    duplicate_accounts_count: int
    has_vpn_usage: bool
    unique_ips: int
    unique_devices: int
    overall_risk_level: str = Field(..., description="low, medium, high, critical")

    @validator('overall_risk_level', always=True)
    def calculate_overall_risk(cls, v, values):
        """Calculate overall risk level based on various factors"""
        risk_score = values.get('latest_risk_score', 0)
        suspicious_count = values.get('suspicious_activities_count', 0)
        duplicate_count = values.get('duplicate_accounts_count', 0)

        if risk_score >= 80 or suspicious_count >= 5 or duplicate_count >= 3:
            return "critical"
        elif risk_score >= 60 or suspicious_count >= 3 or duplicate_count >= 2:
            return "high"
        elif risk_score >= 30 or suspicious_count >= 1 or duplicate_count >= 1:
            return "medium"
        else:
            return "low"

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "rate_limit": {
                    "tier": "free",
                    "daily_used": 1,
                    "is_blocked": False,
                    "trial_expired": False
                },
                "fraud_detections_count": 5,
                "latest_risk_score": 15,
                "suspicious_activities_count": 0,
                "duplicate_accounts_count": 0,
                "has_vpn_usage": False,
                "unique_ips": 2,
                "unique_devices": 1,
                "overall_risk_level": "low"
            }
        }


# ============================================================================
# TIER INFORMATION SCHEMAS
# ============================================================================

class TierLimits(BaseModel):
    """Subscription tier limits"""
    tier: str
    daily_queries: int
    monthly_queries: int
    trial_days: int
    allow_vpn: bool
    features: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "tier": "free",
                "daily_queries": 3,
                "monthly_queries": 90,
                "trial_days": 14,
                "allow_vpn": False,
                "features": ["Basic search", "3 queries per day", "14-day trial"]
            }
        }


class AllTierLimits(BaseModel):
    """All subscription tiers with limits"""
    free: TierLimits
    starter: TierLimits
    professional: TierLimits
    enterprise: TierLimits

    class Config:
        json_schema_extra = {
            "example": {
                "free": {
                    "tier": "free",
                    "daily_queries": 3,
                    "monthly_queries": 90,
                    "trial_days": 14,
                    "allow_vpn": False,
                    "features": ["Basic search", "3 queries per day", "14-day trial"]
                },
                "starter": {
                    "tier": "starter",
                    "daily_queries": 5,
                    "monthly_queries": 150,
                    "trial_days": 0,
                    "allow_vpn": True,
                    "features": ["Advanced search", "5 queries per day", "VPN allowed"]
                },
                "professional": {
                    "tier": "professional",
                    "daily_queries": 20,
                    "monthly_queries": 600,
                    "trial_days": 0,
                    "allow_vpn": True,
                    "features": ["Premium search", "20 queries per day", "Priority support"]
                },
                "enterprise": {
                    "tier": "enterprise",
                    "daily_queries": -1,
                    "monthly_queries": -1,
                    "trial_days": 0,
                    "allow_vpn": True,
                    "features": ["Unlimited queries", "Dedicated support", "API access"]
                }
            }
        }


# ============================================================================
# PAYMENT FINGERPRINT SCHEMAS
# ============================================================================

class PaymentFingerprintCreate(BaseModel):
    """Create payment fingerprint"""
    payment_type: str = Field(..., description="Type of payment method")
    card_brand: Optional[str] = Field(None, description="Card brand (if card)")
    card_last4: Optional[str] = Field(None, description="Last 4 digits (if card)")

    class Config:
        json_schema_extra = {
            "example": {
                "payment_type": "card",
                "card_brand": "Visa",
                "card_last4": "4242"
            }
        }


class PaymentFingerprintResponse(BaseModel):
    """Payment fingerprint response"""
    fingerprint_id: UUID
    user_id: UUID
    payment_type: str
    card_brand: Optional[str]
    card_last4: Optional[str]
    created_at: datetime
    last_used: datetime

    class Config:
        from_attributes = True
