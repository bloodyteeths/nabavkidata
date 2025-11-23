"""
Fraud Prevention and Detection Models for nabavkidata.com
Handles fraud detection, rate limiting, and abuse prevention
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

from database import Base


class FraudDetection(Base):
    """
    Fraud detection tracking model
    Stores fingerprinting and tracking data for abuse detection
    """
    __tablename__ = "fraud_detection"

    detection_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)

    # IP tracking
    ip_address = Column(INET, nullable=False, index=True)
    ip_country = Column(String(100))
    ip_city = Column(String(255))
    is_vpn = Column(Boolean, default=False, index=True)
    is_proxy = Column(Boolean, default=False, index=True)
    is_tor = Column(Boolean, default=False, index=True)

    # Device fingerprinting
    device_fingerprint = Column(String(500), nullable=False, index=True)
    user_agent = Column(Text)
    browser = Column(String(100))
    os = Column(String(100))
    device_type = Column(String(50))  # mobile, desktop, tablet

    # Browser fingerprinting
    screen_resolution = Column(String(50))
    timezone = Column(String(100))
    language = Column(String(20))
    platform = Column(String(100))
    canvas_fingerprint = Column(String(500))
    webgl_fingerprint = Column(String(500))

    # Additional metadata
    detection_metadata = Column(JSONB, default={})

    # Risk scoring
    risk_score = Column(Integer, default=0)  # 0-100, higher = more suspicious
    is_suspicious = Column(Boolean, default=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FraudDetection(user_id={self.user_id}, ip={self.ip_address}, risk_score={self.risk_score})>"


class RateLimit(Base):
    """
    Rate limiting model
    Tracks query usage and enforces tier-based limits
    """
    __tablename__ = "rate_limits"

    limit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Query counts
    daily_query_count = Column(Integer, default=0, nullable=False)
    monthly_query_count = Column(Integer, default=0, nullable=False)
    total_query_count = Column(Integer, default=0, nullable=False)

    # Reset timestamps
    daily_reset_at = Column(DateTime, nullable=False)
    monthly_reset_at = Column(DateTime, nullable=False)

    # Trial tracking
    trial_start_date = Column(DateTime)
    trial_end_date = Column(DateTime)
    trial_queries_used = Column(Integer, default=0)

    # Subscription tracking
    subscription_tier = Column(String(50), default="free", nullable=False, index=True)

    # Block status
    is_blocked = Column(Boolean, default=False, nullable=False, index=True)
    block_reason = Column(Text)
    blocked_at = Column(DateTime)
    blocked_until = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<RateLimit(user_id={self.user_id}, tier={self.subscription_tier}, daily={self.daily_query_count}, is_blocked={self.is_blocked})>"

    @property
    def is_trial_expired(self):
        """Check if trial period has expired"""
        if not self.trial_end_date:
            return False
        return datetime.utcnow() > self.trial_end_date


class SuspiciousActivity(Base):
    """
    Suspicious activity log
    Records suspicious behaviors and patterns
    """
    __tablename__ = "suspicious_activities"

    activity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True, index=True)

    # Activity details
    activity_type = Column(String(100), nullable=False, index=True)  # duplicate_account, vpn_usage, rate_limit_exceeded, etc.
    severity = Column(String(20), default="low", index=True)  # low, medium, high, critical
    description = Column(Text)

    # Related data
    ip_address = Column(INET, index=True)
    device_fingerprint = Column(String(500))
    email = Column(String(255), index=True)

    # Evidence
    evidence = Column(JSONB, default={})

    # Action taken
    action_taken = Column(String(100))  # warned, blocked, flagged, none

    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime)
    is_resolved = Column(Boolean, default=False, index=True)

    def __repr__(self):
        return f"<SuspiciousActivity(type={self.activity_type}, severity={self.severity}, user_id={self.user_id})>"


class BlockedEmail(Base):
    """
    Blocked email domains and patterns
    Prevents temporary/disposable email services
    """
    __tablename__ = "blocked_emails"

    block_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Email pattern
    email_pattern = Column(String(255), nullable=False, unique=True, index=True)  # domain or pattern
    block_type = Column(String(50), default="disposable", index=True)  # disposable, spam, fraud, custom

    # Block details
    reason = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BlockedEmail(pattern={self.email_pattern}, type={self.block_type})>"


class BlockedIP(Base):
    """
    Blocked IP addresses and ranges
    Prevents access from suspicious IPs
    """
    __tablename__ = "blocked_ips"

    block_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # IP details
    ip_address = Column(INET, nullable=False, unique=True, index=True)
    ip_range_start = Column(INET)
    ip_range_end = Column(INET)

    # Block details
    reason = Column(Text)
    block_type = Column(String(50), default="manual", index=True)  # manual, automatic, vpn, proxy
    severity = Column(String(20), default="medium")

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Expiration
    expires_at = Column(DateTime)  # null = permanent

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    blocked_by = Column(String(255))  # admin user who blocked

    def __repr__(self):
        return f"<BlockedIP(ip={self.ip_address}, type={self.block_type}, is_active={self.is_active})>"

    @property
    def is_expired(self):
        """Check if block has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at


class DuplicateAccountDetection(Base):
    """
    Duplicate account detection
    Links accounts that appear to be from the same person
    """
    __tablename__ = "duplicate_account_detection"

    detection_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Primary user
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)

    # Duplicate user
    duplicate_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)

    # Matching criteria
    match_type = Column(String(100), nullable=False, index=True)  # email_similarity, ip_match, device_match, payment_match
    confidence_score = Column(Integer, default=0)  # 0-100

    # Evidence
    matching_attributes = Column(JSONB, default={})

    # Status
    is_confirmed = Column(Boolean, default=False, index=True)
    is_false_positive = Column(Boolean, default=False)

    # Action taken
    action_taken = Column(String(100))  # blocked, merged, flagged, none

    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    reviewed_at = Column(DateTime)
    reviewed_by = Column(String(255))  # admin user who reviewed

    def __repr__(self):
        return f"<DuplicateAccountDetection(user_id={self.user_id}, duplicate={self.duplicate_user_id}, match={self.match_type}, confidence={self.confidence_score})>"


class PaymentFingerprint(Base):
    """
    Payment method fingerprinting
    Tracks payment methods to detect duplicate accounts
    """
    __tablename__ = "payment_fingerprints"

    fingerprint_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)

    # Payment fingerprint (hashed card last 4 + exp date, or account hash)
    payment_hash = Column(String(500), nullable=False, index=True)
    payment_type = Column(String(50))  # card, bank_account, paypal

    # Card details (if card)
    card_brand = Column(String(50))
    card_last4 = Column(String(4))

    # Additional metadata
    fingerprint_metadata = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PaymentFingerprint(user_id={self.user_id}, type={self.payment_type})>"


# Indexes for better query performance
Index('idx_fraud_detection_user_ip', FraudDetection.user_id, FraudDetection.ip_address)
Index('idx_fraud_detection_device', FraudDetection.device_fingerprint, FraudDetection.created_at)
Index('idx_fraud_detection_suspicious', FraudDetection.is_suspicious, FraudDetection.risk_score)

Index('idx_rate_limits_tier_blocked', RateLimit.subscription_tier, RateLimit.is_blocked)

Index('idx_suspicious_activities_type_severity', SuspiciousActivity.activity_type, SuspiciousActivity.severity)
Index('idx_suspicious_activities_unresolved', SuspiciousActivity.is_resolved, SuspiciousActivity.detected_at)

Index('idx_duplicate_accounts_both_users', DuplicateAccountDetection.user_id, DuplicateAccountDetection.duplicate_user_id)
Index('idx_duplicate_accounts_unconfirmed', DuplicateAccountDetection.is_confirmed, DuplicateAccountDetection.confidence_score)

Index('idx_payment_fingerprints_hash', PaymentFingerprint.payment_hash)
