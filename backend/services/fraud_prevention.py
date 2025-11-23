"""
Comprehensive Fraud Prevention System for nabavkidata.com
Handles fraud detection, rate limiting, duplicate account detection, and abuse prevention
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from uuid import UUID
import hashlib
import re
import ipaddress
import logging

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import User
from models_fraud import (
    FraudDetection, RateLimit, SuspiciousActivity, BlockedEmail,
    BlockedIP, DuplicateAccountDetection, PaymentFingerprint
)

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Subscription tier limits
TIER_LIMITS = {
    "free": {
        "daily_queries": 3,
        "monthly_queries": 90,
        "trial_days": 14,
        "allow_vpn": False,
        "max_trial_queries": 3  # 3 queries per day for 14 days
    },
    "starter": {
        "daily_queries": 5,
        "monthly_queries": 150,
        "trial_days": 0,
        "allow_vpn": True,
        "max_trial_queries": None
    },
    "professional": {
        "daily_queries": 20,
        "monthly_queries": 600,
        "trial_days": 0,
        "allow_vpn": True,
        "max_trial_queries": None
    },
    "enterprise": {
        "daily_queries": -1,  # unlimited
        "monthly_queries": -1,  # unlimited
        "trial_days": 0,
        "allow_vpn": True,
        "max_trial_queries": None
    }
}

# Risk scoring thresholds
RISK_THRESHOLDS = {
    "low": 0,
    "medium": 30,
    "high": 60,
    "critical": 80
}

# Temporary/disposable email domains (common ones)
DISPOSABLE_EMAIL_DOMAINS = [
    "tempmail.com", "guerrillamail.com", "10minutemail.com", "throwaway.email",
    "mailinator.com", "temp-mail.org", "fakeinbox.com", "yopmail.com",
    "maildrop.cc", "mintemail.com", "sharklasers.com", "spam4.me",
    "trashmail.com", "getnada.com", "mohmal.com", "emailondeck.com",
    "temp-mail.io", "dispostable.com", "mytemp.email", "tempail.com"
]

# VPN/Proxy detection keywords in user agent
VPN_KEYWORDS = ["vpn", "proxy", "tunnel", "tor", "anonymizer"]


# ============================================================================
# FRAUD DETECTION
# ============================================================================

async def track_user_fingerprint(
    db: AsyncSession,
    user_id: UUID,
    ip_address: str,
    device_fingerprint: str,
    user_agent: str,
    additional_data: Optional[Dict] = None
) -> FraudDetection:
    """
    Track user's device and browser fingerprint for fraud detection

    Args:
        db: Database session
        user_id: User's unique identifier
        ip_address: User's IP address
        device_fingerprint: Device fingerprint hash
        user_agent: Browser user agent string
        additional_data: Additional fingerprinting data

    Returns:
        FraudDetection object
    """
    # Parse user agent
    browser, os, device_type = parse_user_agent(user_agent)

    # Check if IP is VPN/Proxy/Tor
    is_vpn, is_proxy, is_tor = await check_vpn_proxy(ip_address, user_agent)

    # Calculate risk score
    risk_score = calculate_risk_score(
        is_vpn=is_vpn,
        is_proxy=is_proxy,
        is_tor=is_tor,
        additional_data=additional_data
    )

    # Create or update fraud detection record
    fraud_detection = FraudDetection(
        user_id=user_id,
        ip_address=ip_address,
        is_vpn=is_vpn,
        is_proxy=is_proxy,
        is_tor=is_tor,
        device_fingerprint=device_fingerprint,
        user_agent=user_agent,
        browser=browser,
        os=os,
        device_type=device_type,
        screen_resolution=additional_data.get("screen_resolution") if additional_data else None,
        timezone=additional_data.get("timezone") if additional_data else None,
        language=additional_data.get("language") if additional_data else None,
        platform=additional_data.get("platform") if additional_data else None,
        canvas_fingerprint=additional_data.get("canvas_fingerprint") if additional_data else None,
        webgl_fingerprint=additional_data.get("webgl_fingerprint") if additional_data else None,
        detection_metadata=additional_data or {},
        risk_score=risk_score,
        is_suspicious=risk_score >= RISK_THRESHOLDS["high"]
    )

    db.add(fraud_detection)
    await db.commit()
    await db.refresh(fraud_detection)

    # Log suspicious activity if high risk
    if risk_score >= RISK_THRESHOLDS["high"]:
        await log_suspicious_activity(
            db=db,
            user_id=user_id,
            activity_type="high_risk_fingerprint",
            severity="high" if risk_score < RISK_THRESHOLDS["critical"] else "critical",
            description=f"High risk score detected: {risk_score}",
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            evidence={
                "risk_score": risk_score,
                "is_vpn": is_vpn,
                "is_proxy": is_proxy,
                "is_tor": is_tor
            }
        )

    return fraud_detection


def parse_user_agent(user_agent: str) -> Tuple[str, str, str]:
    """
    Parse user agent string to extract browser, OS, and device type

    Args:
        user_agent: Browser user agent string

    Returns:
        Tuple of (browser, os, device_type)
    """
    user_agent_lower = user_agent.lower()

    # Detect browser
    if "firefox" in user_agent_lower:
        browser = "Firefox"
    elif "chrome" in user_agent_lower and "edg" not in user_agent_lower:
        browser = "Chrome"
    elif "safari" in user_agent_lower and "chrome" not in user_agent_lower:
        browser = "Safari"
    elif "edg" in user_agent_lower:
        browser = "Edge"
    elif "opera" in user_agent_lower or "opr" in user_agent_lower:
        browser = "Opera"
    else:
        browser = "Unknown"

    # Detect OS
    if "windows" in user_agent_lower:
        os = "Windows"
    elif "mac" in user_agent_lower or "darwin" in user_agent_lower:
        os = "macOS"
    elif "linux" in user_agent_lower:
        os = "Linux"
    elif "android" in user_agent_lower:
        os = "Android"
    elif "ios" in user_agent_lower or "iphone" in user_agent_lower or "ipad" in user_agent_lower:
        os = "iOS"
    else:
        os = "Unknown"

    # Detect device type
    if "mobile" in user_agent_lower or "android" in user_agent_lower or "iphone" in user_agent_lower:
        device_type = "mobile"
    elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
        device_type = "tablet"
    else:
        device_type = "desktop"

    return browser, os, device_type


async def check_vpn_proxy(ip_address: str, user_agent: str) -> Tuple[bool, bool, bool]:
    """
    Check if IP address or user agent indicates VPN/Proxy/Tor usage

    Args:
        ip_address: User's IP address
        user_agent: Browser user agent string

    Returns:
        Tuple of (is_vpn, is_proxy, is_tor)
    """
    is_vpn = False
    is_proxy = False
    is_tor = False

    # Check user agent for VPN keywords
    user_agent_lower = user_agent.lower()
    for keyword in VPN_KEYWORDS:
        if keyword in user_agent_lower:
            is_vpn = True
            break

    # Check for Tor (you would typically use a Tor exit node list here)
    # For now, we'll use a simple check
    if "tor" in user_agent_lower:
        is_tor = True

    # Check if IP is a known proxy (simplified - in production use a proper service)
    # You could integrate with services like IPHub, IP2Proxy, etc.

    return is_vpn, is_proxy, is_tor


def calculate_risk_score(
    is_vpn: bool = False,
    is_proxy: bool = False,
    is_tor: bool = False,
    additional_data: Optional[Dict] = None
) -> int:
    """
    Calculate fraud risk score (0-100)

    Args:
        is_vpn: Whether VPN is detected
        is_proxy: Whether proxy is detected
        is_tor: Whether Tor is detected
        additional_data: Additional factors

    Returns:
        Risk score (0-100, higher = more suspicious)
    """
    score = 0

    # VPN/Proxy/Tor usage
    if is_tor:
        score += 50  # Tor is highly suspicious for free tier
    elif is_vpn:
        score += 30
    elif is_proxy:
        score += 25

    # Additional factors from additional_data
    if additional_data:
        # Missing critical fingerprinting data
        if not additional_data.get("canvas_fingerprint"):
            score += 10
        if not additional_data.get("timezone"):
            score += 5

    return min(score, 100)  # Cap at 100


# ============================================================================
# EMAIL VALIDATION
# ============================================================================

async def is_email_allowed(db: AsyncSession, email: str) -> Tuple[bool, Optional[str]]:
    """
    Check if email is allowed (not temporary/disposable)

    Args:
        db: Database session
        email: Email address to check

    Returns:
        Tuple of (is_allowed, block_reason)
    """
    email_lower = email.lower()
    domain = email_lower.split("@")[1] if "@" in email_lower else ""

    # Check against built-in disposable email list
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return False, f"Temporary email domain not allowed: {domain}"

    # Check database for blocked patterns
    result = await db.execute(
        select(BlockedEmail).where(
            and_(
                BlockedEmail.is_active == True,
                or_(
                    BlockedEmail.email_pattern == domain,
                    BlockedEmail.email_pattern == email_lower
                )
            )
        )
    )
    blocked = result.scalar_one_or_none()

    if blocked:
        return False, f"Email blocked: {blocked.reason or 'Blocked domain'}"

    return True, None


def detect_email_similarity(email1: str, email2: str) -> Tuple[bool, int]:
    """
    Detect if two emails are suspiciously similar (e.g., test@gmail.com vs test1@gmail.com)

    Args:
        email1: First email address
        email2: Second email address

    Returns:
        Tuple of (is_similar, similarity_score)
    """
    email1_lower = email1.lower()
    email2_lower = email2.lower()

    # Same email
    if email1_lower == email2_lower:
        return True, 100

    # Extract local and domain parts
    try:
        local1, domain1 = email1_lower.split("@")
        local2, domain2 = email2_lower.split("@")
    except ValueError:
        return False, 0

    # Different domains = not similar
    if domain1 != domain2:
        return False, 0

    # Remove + aliases (e.g., test+1@gmail.com -> test@gmail.com)
    local1_base = local1.split("+")[0]
    local2_base = local2.split("+")[0]

    if local1_base == local2_base:
        return True, 95

    # Check for single character differences (test vs test1)
    if len(local1_base) > 3 and len(local2_base) > 3:
        # Remove trailing numbers
        local1_no_numbers = re.sub(r'\d+$', '', local1_base)
        local2_no_numbers = re.sub(r'\d+$', '', local2_base)

        if local1_no_numbers == local2_no_numbers and local1_no_numbers:
            return True, 85

    # Check Levenshtein distance for short emails
    if len(local1_base) <= 10 and len(local2_base) <= 10:
        distance = levenshtein_distance(local1_base, local2_base)
        if distance <= 2:
            similarity = 100 - (distance * 20)
            return True, similarity

    return False, 0


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings

    Args:
        s1: First string
        s2: Second string

    Returns:
        Edit distance
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


# ============================================================================
# DUPLICATE ACCOUNT DETECTION
# ============================================================================

async def detect_duplicate_accounts(
    db: AsyncSession,
    user_id: UUID,
    email: str,
    ip_address: str,
    device_fingerprint: str
) -> List[DuplicateAccountDetection]:
    """
    Detect potential duplicate accounts based on multiple criteria

    Args:
        db: Database session
        user_id: Current user's ID
        email: User's email
        ip_address: User's IP address
        device_fingerprint: Device fingerprint

    Returns:
        List of duplicate account detections
    """
    duplicates = []

    # Get all users
    result = await db.execute(
        select(User).where(User.user_id != user_id)
    )
    all_users = result.scalars().all()

    for other_user in all_users:
        # Check email similarity
        is_similar, similarity_score = detect_email_similarity(email, other_user.email)
        if is_similar and similarity_score >= 80:
            duplicate = await create_duplicate_detection(
                db=db,
                user_id=user_id,
                duplicate_user_id=other_user.user_id,
                match_type="email_similarity",
                confidence_score=similarity_score,
                matching_attributes={
                    "email1": email,
                    "email2": other_user.email,
                    "similarity_score": similarity_score
                }
            )
            duplicates.append(duplicate)

    # Check IP address matches
    result = await db.execute(
        select(FraudDetection).where(
            and_(
                FraudDetection.user_id != user_id,
                FraudDetection.ip_address == ip_address
            )
        ).distinct(FraudDetection.user_id)
    )
    ip_matches = result.scalars().all()

    for match in ip_matches:
        duplicate = await create_duplicate_detection(
            db=db,
            user_id=user_id,
            duplicate_user_id=match.user_id,
            match_type="ip_match",
            confidence_score=70,
            matching_attributes={
                "ip_address": str(ip_address),
                "matched_at": datetime.utcnow().isoformat()
            }
        )
        duplicates.append(duplicate)

    # Check device fingerprint matches
    result = await db.execute(
        select(FraudDetection).where(
            and_(
                FraudDetection.user_id != user_id,
                FraudDetection.device_fingerprint == device_fingerprint
            )
        ).distinct(FraudDetection.user_id)
    )
    device_matches = result.scalars().all()

    for match in device_matches:
        duplicate = await create_duplicate_detection(
            db=db,
            user_id=user_id,
            duplicate_user_id=match.user_id,
            match_type="device_match",
            confidence_score=80,
            matching_attributes={
                "device_fingerprint": device_fingerprint,
                "matched_at": datetime.utcnow().isoformat()
            }
        )
        duplicates.append(duplicate)

    return duplicates


async def create_duplicate_detection(
    db: AsyncSession,
    user_id: UUID,
    duplicate_user_id: UUID,
    match_type: str,
    confidence_score: int,
    matching_attributes: Dict
) -> DuplicateAccountDetection:
    """
    Create a duplicate account detection record

    Args:
        db: Database session
        user_id: Primary user ID
        duplicate_user_id: Duplicate user ID
        match_type: Type of match
        confidence_score: Confidence score (0-100)
        matching_attributes: Matching attributes

    Returns:
        DuplicateAccountDetection object
    """
    # Check if already exists
    result = await db.execute(
        select(DuplicateAccountDetection).where(
            and_(
                DuplicateAccountDetection.user_id == user_id,
                DuplicateAccountDetection.duplicate_user_id == duplicate_user_id,
                DuplicateAccountDetection.match_type == match_type
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    duplicate = DuplicateAccountDetection(
        user_id=user_id,
        duplicate_user_id=duplicate_user_id,
        match_type=match_type,
        confidence_score=confidence_score,
        matching_attributes=matching_attributes,
        is_confirmed=False,
        is_false_positive=False
    )

    db.add(duplicate)
    await db.commit()
    await db.refresh(duplicate)

    return duplicate


# ============================================================================
# RATE LIMITING
# ============================================================================

async def initialize_rate_limit(
    db: AsyncSession,
    user_id: UUID,
    subscription_tier: str = "free"
) -> RateLimit:
    """
    Initialize rate limit tracking for a new user

    Args:
        db: Database session
        user_id: User's unique identifier
        subscription_tier: User's subscription tier

    Returns:
        RateLimit object
    """
    now = datetime.utcnow()

    # Set trial dates for free tier
    trial_start = now if subscription_tier == "free" else None
    trial_end = now + timedelta(days=TIER_LIMITS["free"]["trial_days"]) if subscription_tier == "free" else None

    rate_limit = RateLimit(
        user_id=user_id,
        subscription_tier=subscription_tier,
        daily_query_count=0,
        monthly_query_count=0,
        total_query_count=0,
        daily_reset_at=now + timedelta(days=1),
        monthly_reset_at=now + timedelta(days=30),
        trial_start_date=trial_start,
        trial_end_date=trial_end,
        trial_queries_used=0,
        is_blocked=False
    )

    db.add(rate_limit)
    await db.commit()
    await db.refresh(rate_limit)

    return rate_limit


async def get_rate_limit(db: AsyncSession, user_id: UUID) -> Optional[RateLimit]:
    """
    Get rate limit for a user

    Args:
        db: Database session
        user_id: User's unique identifier

    Returns:
        RateLimit object or None
    """
    result = await db.execute(
        select(RateLimit).where(RateLimit.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def check_rate_limit(
    db: AsyncSession,
    user_id: UUID,
    user: User
) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Check if user has exceeded rate limits

    Args:
        db: Database session
        user_id: User's unique identifier
        user: User object

    Returns:
        Tuple of (is_allowed, block_reason, limit_info)
    """
    # Get or create rate limit
    rate_limit = await get_rate_limit(db, user_id)
    if not rate_limit:
        rate_limit = await initialize_rate_limit(
            db=db,
            user_id=user_id,
            subscription_tier=user.subscription_tier
        )

    # Check if user is blocked
    if rate_limit.is_blocked:
        if rate_limit.blocked_until and datetime.utcnow() < rate_limit.blocked_until:
            return False, rate_limit.block_reason, {
                "blocked_until": rate_limit.blocked_until.isoformat()
            }
        else:
            # Unblock if temporary block expired
            rate_limit.is_blocked = False
            rate_limit.block_reason = None
            rate_limit.blocked_until = None
            await db.commit()

    # Update subscription tier if changed
    if rate_limit.subscription_tier != user.subscription_tier:
        rate_limit.subscription_tier = user.subscription_tier
        await db.commit()

    tier = user.subscription_tier.lower()
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS["free"])

    # Check trial expiration for free tier
    if tier == "free":
        if rate_limit.is_trial_expired:
            # Block user and require upgrade
            rate_limit.is_blocked = True
            rate_limit.block_reason = "Free trial expired. Please upgrade to continue using the service."
            rate_limit.blocked_at = datetime.utcnow()
            await db.commit()

            return False, rate_limit.block_reason, {
                "trial_end_date": rate_limit.trial_end_date.isoformat(),
                "redirect_to": "/pricing"
            }

    # Reset counters if needed
    now = datetime.utcnow()
    if now >= rate_limit.daily_reset_at:
        rate_limit.daily_query_count = 0
        rate_limit.daily_reset_at = now + timedelta(days=1)
        await db.commit()

    if now >= rate_limit.monthly_reset_at:
        rate_limit.monthly_query_count = 0
        rate_limit.monthly_reset_at = now + timedelta(days=30)
        await db.commit()

    # Check limits (enterprise has unlimited)
    if tier != "enterprise":
        daily_limit = tier_config["daily_queries"]

        if rate_limit.daily_query_count >= daily_limit:
            return False, f"Daily query limit reached ({daily_limit} queries per day). Upgrade your plan for more queries.", {
                "daily_limit": daily_limit,
                "daily_used": rate_limit.daily_query_count,
                "reset_at": rate_limit.daily_reset_at.isoformat(),
                "redirect_to": "/pricing"
            }

    # Build limit info
    limit_info = {
        "tier": tier,
        "daily_limit": tier_config["daily_queries"],
        "daily_used": rate_limit.daily_query_count,
        "daily_remaining": max(0, tier_config["daily_queries"] - rate_limit.daily_query_count) if tier != "enterprise" else -1,
        "daily_reset_at": rate_limit.daily_reset_at.isoformat(),
        "trial_end_date": rate_limit.trial_end_date.isoformat() if rate_limit.trial_end_date else None
    }

    return True, None, limit_info


async def increment_query_count(db: AsyncSession, user_id: UUID) -> None:
    """
    Increment query count for a user

    Args:
        db: Database session
        user_id: User's unique identifier
    """
    rate_limit = await get_rate_limit(db, user_id)
    if rate_limit:
        rate_limit.daily_query_count += 1
        rate_limit.monthly_query_count += 1
        rate_limit.total_query_count += 1

        # For free tier, also track trial queries
        if rate_limit.subscription_tier == "free":
            rate_limit.trial_queries_used += 1

        await db.commit()


# ============================================================================
# IP BLOCKING
# ============================================================================

async def is_ip_blocked(db: AsyncSession, ip_address: str) -> Tuple[bool, Optional[str]]:
    """
    Check if IP address is blocked

    Args:
        db: Database session
        ip_address: IP address to check

    Returns:
        Tuple of (is_blocked, block_reason)
    """
    result = await db.execute(
        select(BlockedIP).where(
            and_(
                BlockedIP.ip_address == ip_address,
                BlockedIP.is_active == True
            )
        )
    )
    blocked = result.scalar_one_or_none()

    if blocked:
        # Check if block has expired
        if blocked.is_expired:
            blocked.is_active = False
            await db.commit()
            return False, None

        return True, blocked.reason or "IP address is blocked"

    return False, None


async def block_ip(
    db: AsyncSession,
    ip_address: str,
    reason: str,
    block_type: str = "manual",
    expires_at: Optional[datetime] = None,
    blocked_by: Optional[str] = None
) -> BlockedIP:
    """
    Block an IP address

    Args:
        db: Database session
        ip_address: IP address to block
        reason: Reason for blocking
        block_type: Type of block
        expires_at: Expiration date (None = permanent)
        blocked_by: Admin who blocked the IP

    Returns:
        BlockedIP object
    """
    blocked_ip = BlockedIP(
        ip_address=ip_address,
        reason=reason,
        block_type=block_type,
        is_active=True,
        expires_at=expires_at,
        blocked_by=blocked_by
    )

    db.add(blocked_ip)
    await db.commit()
    await db.refresh(blocked_ip)

    return blocked_ip


# ============================================================================
# SUSPICIOUS ACTIVITY LOGGING
# ============================================================================

async def log_suspicious_activity(
    db: AsyncSession,
    activity_type: str,
    severity: str,
    description: str,
    user_id: Optional[UUID] = None,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    device_fingerprint: Optional[str] = None,
    evidence: Optional[Dict] = None,
    action_taken: Optional[str] = None
) -> SuspiciousActivity:
    """
    Log suspicious activity

    Args:
        db: Database session
        activity_type: Type of suspicious activity
        severity: Severity level (low, medium, high, critical)
        description: Description of the activity
        user_id: User ID (if applicable)
        email: Email address (if applicable)
        ip_address: IP address
        device_fingerprint: Device fingerprint
        evidence: Evidence dictionary
        action_taken: Action taken in response

    Returns:
        SuspiciousActivity object
    """
    activity = SuspiciousActivity(
        user_id=user_id,
        activity_type=activity_type,
        severity=severity,
        description=description,
        ip_address=ip_address,
        device_fingerprint=device_fingerprint,
        email=email,
        evidence=evidence or {},
        action_taken=action_taken,
        is_resolved=False
    )

    db.add(activity)
    await db.commit()
    await db.refresh(activity)

    logger.warning(
        f"Suspicious activity detected: {activity_type} | "
        f"Severity: {severity} | User: {user_id} | "
        f"Description: {description}"
    )

    return activity


# ============================================================================
# PAYMENT FINGERPRINTING
# ============================================================================

async def track_payment_fingerprint(
    db: AsyncSession,
    user_id: UUID,
    payment_type: str,
    card_brand: Optional[str] = None,
    card_last4: Optional[str] = None,
    additional_data: Optional[Dict] = None
) -> PaymentFingerprint:
    """
    Track payment method fingerprint

    Args:
        db: Database session
        user_id: User's unique identifier
        payment_type: Type of payment method
        card_brand: Card brand (if card)
        card_last4: Last 4 digits of card (if card)
        additional_data: Additional metadata

    Returns:
        PaymentFingerprint object
    """
    # Create payment hash
    if payment_type == "card" and card_last4:
        payment_hash = hashlib.sha256(f"{card_brand}:{card_last4}".encode()).hexdigest()
    else:
        payment_hash = hashlib.sha256(f"{payment_type}:{user_id}".encode()).hexdigest()

    fingerprint = PaymentFingerprint(
        user_id=user_id,
        payment_hash=payment_hash,
        payment_type=payment_type,
        card_brand=card_brand,
        card_last4=card_last4,
        fingerprint_metadata=additional_data or {}
    )

    db.add(fingerprint)
    await db.commit()
    await db.refresh(fingerprint)

    return fingerprint


async def detect_payment_duplicates(
    db: AsyncSession,
    payment_hash: str,
    current_user_id: UUID
) -> List[PaymentFingerprint]:
    """
    Detect duplicate payment methods across accounts

    Args:
        db: Database session
        payment_hash: Payment hash to check
        current_user_id: Current user's ID to exclude

    Returns:
        List of matching payment fingerprints from other users
    """
    result = await db.execute(
        select(PaymentFingerprint).where(
            and_(
                PaymentFingerprint.payment_hash == payment_hash,
                PaymentFingerprint.user_id != current_user_id
            )
        )
    )
    return result.scalars().all()


# ============================================================================
# COMPREHENSIVE FRAUD CHECK
# ============================================================================

async def perform_fraud_check(
    db: AsyncSession,
    user: User,
    ip_address: str,
    device_fingerprint: str,
    user_agent: str,
    check_type: str = "query",
    additional_data: Optional[Dict] = None
) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Perform comprehensive fraud check before allowing an action

    Args:
        db: Database session
        user: User object
        ip_address: User's IP address
        device_fingerprint: Device fingerprint
        user_agent: Browser user agent
        check_type: Type of check (query, registration, payment)
        additional_data: Additional data for checks

    Returns:
        Tuple of (is_allowed, block_reason, details)
    """
    details = {}

    # 1. Check if IP is blocked
    ip_blocked, ip_reason = await is_ip_blocked(db, ip_address)
    if ip_blocked:
        return False, f"Access denied: {ip_reason}", {"redirect_to": "/blocked"}

    # 2. Check email validity (for registration)
    if check_type == "registration":
        email_allowed, email_reason = await is_email_allowed(db, user.email)
        if not email_allowed:
            return False, email_reason, {"redirect_to": "/register"}

    # 3. Track fingerprint and check for fraud
    fraud_detection = await track_user_fingerprint(
        db=db,
        user_id=user.user_id,
        ip_address=ip_address,
        device_fingerprint=device_fingerprint,
        user_agent=user_agent,
        additional_data=additional_data
    )

    # 4. Check VPN/Proxy for free tier
    if user.subscription_tier == "free":
        tier_config = TIER_LIMITS["free"]
        if not tier_config["allow_vpn"]:
            if fraud_detection.is_vpn or fraud_detection.is_proxy or fraud_detection.is_tor:
                await log_suspicious_activity(
                    db=db,
                    user_id=user.user_id,
                    activity_type="vpn_usage_free_tier",
                    severity="medium",
                    description="VPN/Proxy usage detected on free tier",
                    ip_address=ip_address,
                    device_fingerprint=device_fingerprint,
                    evidence={
                        "is_vpn": fraud_detection.is_vpn,
                        "is_proxy": fraud_detection.is_proxy,
                        "is_tor": fraud_detection.is_tor
                    },
                    action_taken="blocked"
                )
                return False, "VPN/Proxy usage is not allowed on the free tier. Please upgrade or disable your VPN.", {
                    "redirect_to": "/pricing"
                }

    # 5. Check rate limits (for queries)
    if check_type == "query":
        rate_allowed, rate_reason, rate_info = await check_rate_limit(db, user.user_id, user)
        if not rate_allowed:
            return False, rate_reason, rate_info

        details.update(rate_info)

        # Increment query count
        await increment_query_count(db, user.user_id)

    # 6. Detect duplicate accounts (for registration)
    if check_type == "registration":
        duplicates = await detect_duplicate_accounts(
            db=db,
            user_id=user.user_id,
            email=user.email,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint
        )

        # If high confidence duplicates found, log and potentially block
        high_confidence_duplicates = [d for d in duplicates if d.confidence_score >= 80]
        if high_confidence_duplicates:
            await log_suspicious_activity(
                db=db,
                user_id=user.user_id,
                activity_type="duplicate_account_detected",
                severity="high",
                description=f"Found {len(high_confidence_duplicates)} potential duplicate accounts",
                email=user.email,
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                evidence={
                    "duplicate_count": len(high_confidence_duplicates),
                    "duplicates": [
                        {
                            "user_id": str(d.duplicate_user_id),
                            "match_type": d.match_type,
                            "confidence": d.confidence_score
                        }
                        for d in high_confidence_duplicates
                    ]
                },
                action_taken="flagged"
            )

            details["duplicate_warning"] = f"Found {len(high_confidence_duplicates)} similar accounts"

    return True, None, details


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def get_user_fraud_summary(db: AsyncSession, user_id: UUID) -> Dict:
    """
    Get fraud detection summary for a user

    Args:
        db: Database session
        user_id: User's unique identifier

    Returns:
        Dictionary with fraud detection summary
    """
    # Get rate limit
    rate_limit = await get_rate_limit(db, user_id)

    # Get recent fraud detections
    result = await db.execute(
        select(FraudDetection)
        .where(FraudDetection.user_id == user_id)
        .order_by(FraudDetection.created_at.desc())
        .limit(10)
    )
    fraud_detections = result.scalars().all()

    # Get suspicious activities
    result = await db.execute(
        select(SuspiciousActivity)
        .where(SuspiciousActivity.user_id == user_id)
        .order_by(SuspiciousActivity.detected_at.desc())
        .limit(10)
    )
    suspicious_activities = result.scalars().all()

    # Get duplicate accounts
    result = await db.execute(
        select(DuplicateAccountDetection)
        .where(DuplicateAccountDetection.user_id == user_id)
        .order_by(DuplicateAccountDetection.detected_at.desc())
    )
    duplicates = result.scalars().all()

    return {
        "rate_limit": {
            "tier": rate_limit.subscription_tier if rate_limit else None,
            "daily_used": rate_limit.daily_query_count if rate_limit else 0,
            "is_blocked": rate_limit.is_blocked if rate_limit else False,
            "block_reason": rate_limit.block_reason if rate_limit else None,
            "trial_expired": rate_limit.is_trial_expired if rate_limit else False
        },
        "fraud_detections_count": len(fraud_detections),
        "latest_risk_score": fraud_detections[0].risk_score if fraud_detections else 0,
        "suspicious_activities_count": len(suspicious_activities),
        "duplicate_accounts_count": len(duplicates),
        "has_vpn_usage": any(fd.is_vpn for fd in fraud_detections),
        "unique_ips": len(set(fd.ip_address for fd in fraud_detections)),
        "unique_devices": len(set(fd.device_fingerprint for fd in fraud_detections))
    }
