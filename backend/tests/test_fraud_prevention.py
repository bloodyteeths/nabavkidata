"""
Unit Tests for Fraud Prevention System
Tests fraud detection, rate limiting, and duplicate account detection
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from services.fraud_prevention import (
    detect_email_similarity,
    levenshtein_distance,
    calculate_risk_score,
    parse_user_agent,
    is_email_allowed,
    check_rate_limit,
    initialize_rate_limit,
    increment_query_count,
    TIER_LIMITS
)


# ============================================================================
# EMAIL SIMILARITY TESTS
# ============================================================================

def test_email_similarity_identical():
    """Test identical emails"""
    is_similar, score = detect_email_similarity("test@gmail.com", "test@gmail.com")
    assert is_similar is True
    assert score == 100


def test_email_similarity_plus_alias():
    """Test email with + alias"""
    is_similar, score = detect_email_similarity("test@gmail.com", "test+1@gmail.com")
    assert is_similar is True
    assert score == 95


def test_email_similarity_number_suffix():
    """Test email with number suffix"""
    is_similar, score = detect_email_similarity("test@gmail.com", "test1@gmail.com")
    assert is_similar is True
    assert score >= 80


def test_email_similarity_different_domains():
    """Test emails with different domains"""
    is_similar, score = detect_email_similarity("test@gmail.com", "test@yahoo.com")
    assert is_similar is False
    assert score == 0


def test_email_similarity_completely_different():
    """Test completely different emails"""
    is_similar, score = detect_email_similarity("alice@gmail.com", "bob@gmail.com")
    assert is_similar is False


# ============================================================================
# LEVENSHTEIN DISTANCE TESTS
# ============================================================================

def test_levenshtein_distance_identical():
    """Test identical strings"""
    distance = levenshtein_distance("test", "test")
    assert distance == 0


def test_levenshtein_distance_single_char():
    """Test single character difference"""
    distance = levenshtein_distance("test", "best")
    assert distance == 1


def test_levenshtein_distance_insertion():
    """Test insertion"""
    distance = levenshtein_distance("test", "test1")
    assert distance == 1


def test_levenshtein_distance_deletion():
    """Test deletion"""
    distance = levenshtein_distance("test1", "test")
    assert distance == 1


# ============================================================================
# USER AGENT PARSING TESTS
# ============================================================================

def test_parse_user_agent_chrome():
    """Test Chrome user agent parsing"""
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    browser, os, device_type = parse_user_agent(ua)

    assert browser == "Chrome"
    assert os == "macOS"
    assert device_type == "desktop"


def test_parse_user_agent_firefox():
    """Test Firefox user agent parsing"""
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    browser, os, device_type = parse_user_agent(ua)

    assert browser == "Firefox"
    assert os == "Windows"
    assert device_type == "desktop"


def test_parse_user_agent_mobile():
    """Test mobile user agent parsing"""
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
    browser, os, device_type = parse_user_agent(ua)

    assert os == "iOS"
    assert device_type == "mobile"


def test_parse_user_agent_android():
    """Test Android user agent parsing"""
    ua = "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
    browser, os, device_type = parse_user_agent(ua)

    assert browser == "Chrome"
    assert os == "Android"
    assert device_type == "mobile"


# ============================================================================
# RISK SCORE TESTS
# ============================================================================

def test_risk_score_clean():
    """Test risk score for clean user"""
    score = calculate_risk_score(
        is_vpn=False,
        is_proxy=False,
        is_tor=False
    )
    assert score == 0


def test_risk_score_vpn():
    """Test risk score with VPN"""
    score = calculate_risk_score(
        is_vpn=True,
        is_proxy=False,
        is_tor=False
    )
    assert score == 30


def test_risk_score_tor():
    """Test risk score with Tor"""
    score = calculate_risk_score(
        is_vpn=False,
        is_proxy=False,
        is_tor=True
    )
    assert score == 50


def test_risk_score_missing_fingerprint():
    """Test risk score with missing fingerprint data"""
    score = calculate_risk_score(
        is_vpn=False,
        is_proxy=False,
        is_tor=False,
        additional_data={}
    )
    assert score >= 10


def test_risk_score_max_cap():
    """Test risk score doesn't exceed 100"""
    score = calculate_risk_score(
        is_vpn=True,
        is_proxy=True,
        is_tor=True,
        additional_data={}
    )
    assert score <= 100


# ============================================================================
# RATE LIMITING TESTS (async tests require pytest-asyncio)
# ============================================================================

@pytest.mark.asyncio
async def test_initialize_rate_limit_free(db_session):
    """Test rate limit initialization for free tier"""
    user_id = uuid4()

    rate_limit = await initialize_rate_limit(
        db=db_session,
        user_id=user_id,
        subscription_tier="free"
    )

    assert rate_limit.user_id == user_id
    assert rate_limit.subscription_tier == "free"
    assert rate_limit.daily_query_count == 0
    assert rate_limit.trial_start_date is not None
    assert rate_limit.trial_end_date is not None

    # Check trial period is 14 days
    trial_days = (rate_limit.trial_end_date - rate_limit.trial_start_date).days
    assert trial_days == TIER_LIMITS["free"]["trial_days"]


@pytest.mark.asyncio
async def test_initialize_rate_limit_paid(db_session):
    """Test rate limit initialization for paid tier"""
    user_id = uuid4()

    rate_limit = await initialize_rate_limit(
        db=db_session,
        user_id=user_id,
        subscription_tier="professional"
    )

    assert rate_limit.subscription_tier == "professional"
    assert rate_limit.trial_start_date is None
    assert rate_limit.trial_end_date is None


@pytest.mark.asyncio
async def test_increment_query_count(db_session):
    """Test query count increment"""
    user_id = uuid4()

    rate_limit = await initialize_rate_limit(
        db=db_session,
        user_id=user_id,
        subscription_tier="free"
    )

    initial_count = rate_limit.daily_query_count

    await increment_query_count(db_session, user_id)

    # Refresh
    await db_session.refresh(rate_limit)

    assert rate_limit.daily_query_count == initial_count + 1
    assert rate_limit.monthly_query_count == 1
    assert rate_limit.total_query_count == 1


# ============================================================================
# TIER LIMITS TESTS
# ============================================================================

def test_tier_limits_structure():
    """Test tier limits configuration"""
    assert "free" in TIER_LIMITS
    assert "starter" in TIER_LIMITS
    assert "professional" in TIER_LIMITS
    assert "enterprise" in TIER_LIMITS

    for tier_name, limits in TIER_LIMITS.items():
        assert "daily_queries" in limits
        assert "monthly_queries" in limits
        assert "trial_days" in limits
        assert "allow_vpn" in limits


def test_free_tier_limits():
    """Test free tier limits"""
    free_limits = TIER_LIMITS["free"]

    assert free_limits["daily_queries"] == 3
    assert free_limits["trial_days"] == 14
    assert free_limits["allow_vpn"] is False


def test_enterprise_tier_unlimited():
    """Test enterprise tier has unlimited queries"""
    enterprise_limits = TIER_LIMITS["enterprise"]

    assert enterprise_limits["daily_queries"] == -1
    assert enterprise_limits["monthly_queries"] == -1


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_fraud_check_flow_clean_user(db_session, mock_user):
    """Test complete fraud check flow for clean user"""
    from services.fraud_prevention import perform_fraud_check

    is_allowed, reason, details = await perform_fraud_check(
        db=db_session,
        user=mock_user,
        ip_address="192.168.1.1",
        device_fingerprint="clean_device_123",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/91.0",
        check_type="query"
    )

    assert is_allowed is True
    assert reason is None
    assert details is not None
    assert "tier" in details
    assert "daily_used" in details


@pytest.mark.asyncio
async def test_fraud_check_flow_vpn_free_tier(db_session, mock_user):
    """Test fraud check blocks VPN on free tier"""
    from services.fraud_prevention import perform_fraud_check

    # Set user to free tier
    mock_user.subscription_tier = "free"

    is_allowed, reason, details = await perform_fraud_check(
        db=db_session,
        user=mock_user,
        ip_address="192.168.1.1",
        device_fingerprint="vpn_device_123",
        user_agent="Mozilla/5.0 (VPN) Chrome/91.0",  # VPN keyword
        check_type="query"
    )

    assert is_allowed is False
    assert "VPN" in reason or "vpn" in reason.lower()


@pytest.mark.asyncio
async def test_fraud_check_rate_limit_exceeded(db_session, mock_user):
    """Test fraud check blocks when rate limit exceeded"""
    from services.fraud_prevention import perform_fraud_check, increment_query_count

    # Set user to free tier
    mock_user.subscription_tier = "free"

    # Initialize and max out queries
    await initialize_rate_limit(db_session, mock_user.user_id, "free")

    for _ in range(3):
        await increment_query_count(db_session, mock_user.user_id)

    # Try one more query
    is_allowed, reason, details = await perform_fraud_check(
        db=db_session,
        user=mock_user,
        ip_address="192.168.1.1",
        device_fingerprint="device_123",
        user_agent="Mozilla/5.0 Chrome/91.0",
        check_type="query"
    )

    assert is_allowed is False
    assert "limit" in reason.lower()
    assert details.get("redirect_to") == "/pricing"


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
async def db_session():
    """Mock database session"""
    # In real tests, use a test database
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def mock_user():
    """Mock user for testing"""
    from models import User

    user = User(
        user_id=uuid4(),
        email="test@example.com",
        password_hash="hashed_password",
        subscription_tier="free"
    )

    return user


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
