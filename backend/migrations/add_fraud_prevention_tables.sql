-- ============================================================================
-- Fraud Prevention System Database Tables
-- Creates all tables needed for fraud detection, rate limiting, and abuse prevention
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- FRAUD DETECTION TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fraud_detection (
    detection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- IP tracking
    ip_address INET NOT NULL,
    ip_country VARCHAR(100),
    ip_city VARCHAR(255),
    is_vpn BOOLEAN DEFAULT FALSE,
    is_proxy BOOLEAN DEFAULT FALSE,
    is_tor BOOLEAN DEFAULT FALSE,

    -- Device fingerprinting
    device_fingerprint VARCHAR(500) NOT NULL,
    user_agent TEXT,
    browser VARCHAR(100),
    os VARCHAR(100),
    device_type VARCHAR(50),

    -- Browser fingerprinting
    screen_resolution VARCHAR(50),
    timezone VARCHAR(100),
    language VARCHAR(20),
    platform VARCHAR(100),
    canvas_fingerprint VARCHAR(500),
    webgl_fingerprint VARCHAR(500),

    -- Additional metadata
    detection_metadata JSONB DEFAULT '{}',

    -- Risk scoring
    risk_score INTEGER DEFAULT 0 CHECK (risk_score >= 0 AND risk_score <= 100),
    is_suspicious BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fraud_detection
CREATE INDEX IF NOT EXISTS idx_fraud_detection_user_id ON fraud_detection(user_id);
CREATE INDEX IF NOT EXISTS idx_fraud_detection_ip_address ON fraud_detection(ip_address);
CREATE INDEX IF NOT EXISTS idx_fraud_detection_device ON fraud_detection(device_fingerprint);
CREATE INDEX IF NOT EXISTS idx_fraud_detection_created_at ON fraud_detection(created_at);
CREATE INDEX IF NOT EXISTS idx_fraud_detection_is_vpn ON fraud_detection(is_vpn);
CREATE INDEX IF NOT EXISTS idx_fraud_detection_is_suspicious ON fraud_detection(is_suspicious);
CREATE INDEX IF NOT EXISTS idx_fraud_detection_user_ip ON fraud_detection(user_id, ip_address);
CREATE INDEX IF NOT EXISTS idx_fraud_detection_device_time ON fraud_detection(device_fingerprint, created_at);
CREATE INDEX IF NOT EXISTS idx_fraud_detection_suspicious_score ON fraud_detection(is_suspicious, risk_score);

-- ============================================================================
-- RATE LIMITS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS rate_limits (
    limit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Query counts
    daily_query_count INTEGER DEFAULT 0 NOT NULL,
    monthly_query_count INTEGER DEFAULT 0 NOT NULL,
    total_query_count INTEGER DEFAULT 0 NOT NULL,

    -- Reset timestamps
    daily_reset_at TIMESTAMP NOT NULL,
    monthly_reset_at TIMESTAMP NOT NULL,

    -- Trial tracking
    trial_start_date TIMESTAMP,
    trial_end_date TIMESTAMP,
    trial_queries_used INTEGER DEFAULT 0,

    -- Subscription tracking
    subscription_tier VARCHAR(50) DEFAULT 'free' NOT NULL,

    -- Block status
    is_blocked BOOLEAN DEFAULT FALSE NOT NULL,
    block_reason TEXT,
    blocked_at TIMESTAMP,
    blocked_until TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for rate_limits
CREATE INDEX IF NOT EXISTS idx_rate_limits_user_id ON rate_limits(user_id);
CREATE INDEX IF NOT EXISTS idx_rate_limits_subscription_tier ON rate_limits(subscription_tier);
CREATE INDEX IF NOT EXISTS idx_rate_limits_is_blocked ON rate_limits(is_blocked);
CREATE INDEX IF NOT EXISTS idx_rate_limits_tier_blocked ON rate_limits(subscription_tier, is_blocked);

-- ============================================================================
-- SUSPICIOUS ACTIVITIES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS suspicious_activities (
    activity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,

    -- Activity details
    activity_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) DEFAULT 'low' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT,

    -- Related data
    ip_address INET,
    device_fingerprint VARCHAR(500),
    email VARCHAR(255),

    -- Evidence
    evidence JSONB DEFAULT '{}',

    -- Action taken
    action_taken VARCHAR(100),

    -- Timestamps
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    is_resolved BOOLEAN DEFAULT FALSE
);

-- Indexes for suspicious_activities
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_user_id ON suspicious_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_activity_type ON suspicious_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_severity ON suspicious_activities(severity);
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_detected_at ON suspicious_activities(detected_at);
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_is_resolved ON suspicious_activities(is_resolved);
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_type_severity ON suspicious_activities(activity_type, severity);
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_unresolved ON suspicious_activities(is_resolved, detected_at);
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_email ON suspicious_activities(email);
CREATE INDEX IF NOT EXISTS idx_suspicious_activities_ip ON suspicious_activities(ip_address);

-- ============================================================================
-- BLOCKED EMAILS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS blocked_emails (
    block_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Email pattern
    email_pattern VARCHAR(255) UNIQUE NOT NULL,
    block_type VARCHAR(50) DEFAULT 'disposable',

    -- Block details
    reason TEXT,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for blocked_emails
CREATE INDEX IF NOT EXISTS idx_blocked_emails_pattern ON blocked_emails(email_pattern);
CREATE INDEX IF NOT EXISTS idx_blocked_emails_is_active ON blocked_emails(is_active);
CREATE INDEX IF NOT EXISTS idx_blocked_emails_block_type ON blocked_emails(block_type);

-- ============================================================================
-- BLOCKED IPS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS blocked_ips (
    block_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- IP details
    ip_address INET UNIQUE NOT NULL,
    ip_range_start INET,
    ip_range_end INET,

    -- Block details
    reason TEXT,
    block_type VARCHAR(50) DEFAULT 'manual',
    severity VARCHAR(20) DEFAULT 'medium',

    -- Status
    is_active BOOLEAN DEFAULT TRUE NOT NULL,

    -- Expiration
    expires_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    blocked_by VARCHAR(255)
);

-- Indexes for blocked_ips
CREATE INDEX IF NOT EXISTS idx_blocked_ips_ip_address ON blocked_ips(ip_address);
CREATE INDEX IF NOT EXISTS idx_blocked_ips_is_active ON blocked_ips(is_active);
CREATE INDEX IF NOT EXISTS idx_blocked_ips_block_type ON blocked_ips(block_type);
CREATE INDEX IF NOT EXISTS idx_blocked_ips_expires_at ON blocked_ips(expires_at);

-- ============================================================================
-- DUPLICATE ACCOUNT DETECTION TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS duplicate_account_detection (
    detection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Primary user
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Duplicate user
    duplicate_user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Matching criteria
    match_type VARCHAR(100) NOT NULL,
    confidence_score INTEGER DEFAULT 0 CHECK (confidence_score >= 0 AND confidence_score <= 100),

    -- Evidence
    matching_attributes JSONB DEFAULT '{}',

    -- Status
    is_confirmed BOOLEAN DEFAULT FALSE,
    is_false_positive BOOLEAN DEFAULT FALSE,

    -- Action taken
    action_taken VARCHAR(100),

    -- Timestamps
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    reviewed_at TIMESTAMP,
    reviewed_by VARCHAR(255),

    -- Ensure no duplicate detections
    UNIQUE(user_id, duplicate_user_id, match_type)
);

-- Indexes for duplicate_account_detection
CREATE INDEX IF NOT EXISTS idx_duplicate_accounts_user_id ON duplicate_account_detection(user_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_accounts_duplicate_user_id ON duplicate_account_detection(duplicate_user_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_accounts_match_type ON duplicate_account_detection(match_type);
CREATE INDEX IF NOT EXISTS idx_duplicate_accounts_detected_at ON duplicate_account_detection(detected_at);
CREATE INDEX IF NOT EXISTS idx_duplicate_accounts_is_confirmed ON duplicate_account_detection(is_confirmed);
CREATE INDEX IF NOT EXISTS idx_duplicate_accounts_both_users ON duplicate_account_detection(user_id, duplicate_user_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_accounts_unconfirmed ON duplicate_account_detection(is_confirmed, confidence_score);

-- ============================================================================
-- PAYMENT FINGERPRINTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS payment_fingerprints (
    fingerprint_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Payment fingerprint (hashed)
    payment_hash VARCHAR(500) NOT NULL,
    payment_type VARCHAR(50),

    -- Card details (if card)
    card_brand VARCHAR(50),
    card_last4 VARCHAR(4),

    -- Additional metadata
    fingerprint_metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for payment_fingerprints
CREATE INDEX IF NOT EXISTS idx_payment_fingerprints_user_id ON payment_fingerprints(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_fingerprints_hash ON payment_fingerprints(payment_hash);
CREATE INDEX IF NOT EXISTS idx_payment_fingerprints_type ON payment_fingerprints(payment_type);

-- ============================================================================
-- TRIGGER FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for rate_limits
DROP TRIGGER IF EXISTS update_rate_limits_updated_at ON rate_limits;
CREATE TRIGGER update_rate_limits_updated_at
    BEFORE UPDATE ON rate_limits
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for blocked_emails
DROP TRIGGER IF EXISTS update_blocked_emails_updated_at ON blocked_emails;
CREATE TRIGGER update_blocked_emails_updated_at
    BEFORE UPDATE ON blocked_emails
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for blocked_ips
DROP TRIGGER IF EXISTS update_blocked_ips_updated_at ON blocked_ips;
CREATE TRIGGER update_blocked_ips_updated_at
    BEFORE UPDATE ON blocked_ips
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to update last_seen on fraud_detection
CREATE OR REPLACE FUNCTION update_last_seen_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_seen = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for fraud_detection
DROP TRIGGER IF EXISTS update_fraud_detection_last_seen ON fraud_detection;
CREATE TRIGGER update_fraud_detection_last_seen
    BEFORE UPDATE ON fraud_detection
    FOR EACH ROW
    EXECUTE FUNCTION update_last_seen_column();

-- ============================================================================
-- SEED DATA - Common Disposable Email Domains
-- ============================================================================

INSERT INTO blocked_emails (email_pattern, block_type, reason, is_active)
VALUES
    ('tempmail.com', 'disposable', 'Temporary email service', TRUE),
    ('guerrillamail.com', 'disposable', 'Temporary email service', TRUE),
    ('10minutemail.com', 'disposable', 'Temporary email service', TRUE),
    ('throwaway.email', 'disposable', 'Temporary email service', TRUE),
    ('mailinator.com', 'disposable', 'Temporary email service', TRUE),
    ('temp-mail.org', 'disposable', 'Temporary email service', TRUE),
    ('fakeinbox.com', 'disposable', 'Temporary email service', TRUE),
    ('yopmail.com', 'disposable', 'Temporary email service', TRUE),
    ('maildrop.cc', 'disposable', 'Temporary email service', TRUE),
    ('mintemail.com', 'disposable', 'Temporary email service', TRUE),
    ('sharklasers.com', 'disposable', 'Temporary email service', TRUE),
    ('spam4.me', 'disposable', 'Temporary email service', TRUE),
    ('trashmail.com', 'disposable', 'Temporary email service', TRUE),
    ('getnada.com', 'disposable', 'Temporary email service', TRUE),
    ('mohmal.com', 'disposable', 'Temporary email service', TRUE),
    ('emailondeck.com', 'disposable', 'Temporary email service', TRUE),
    ('temp-mail.io', 'disposable', 'Temporary email service', TRUE),
    ('dispostable.com', 'disposable', 'Temporary email service', TRUE),
    ('mytemp.email', 'disposable', 'Temporary email service', TRUE),
    ('tempail.com', 'disposable', 'Temporary email service', TRUE)
ON CONFLICT (email_pattern) DO NOTHING;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE fraud_detection IS 'Tracks user fingerprints and detects fraudulent behavior';
COMMENT ON TABLE rate_limits IS 'Enforces rate limits based on subscription tiers';
COMMENT ON TABLE suspicious_activities IS 'Logs suspicious activities and potential fraud attempts';
COMMENT ON TABLE blocked_emails IS 'List of blocked email domains and patterns (disposable emails, etc.)';
COMMENT ON TABLE blocked_ips IS 'List of blocked IP addresses and ranges';
COMMENT ON TABLE duplicate_account_detection IS 'Detects and tracks duplicate accounts from the same user';
COMMENT ON TABLE payment_fingerprints IS 'Tracks payment methods to detect duplicate accounts using same payment';

-- ============================================================================
-- GRANT PERMISSIONS (adjust based on your user setup)
-- ============================================================================

-- Grant permissions to application user (replace 'nabavkidata_app' with your app user)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON fraud_detection TO nabavkidata_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON rate_limits TO nabavkidata_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON suspicious_activities TO nabavkidata_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON blocked_emails TO nabavkidata_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON blocked_ips TO nabavkidata_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON duplicate_account_detection TO nabavkidata_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON payment_fingerprints TO nabavkidata_app;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '✓ Fraud Prevention System tables created successfully!';
    RAISE NOTICE '✓ Created tables:';
    RAISE NOTICE '  - fraud_detection';
    RAISE NOTICE '  - rate_limits';
    RAISE NOTICE '  - suspicious_activities';
    RAISE NOTICE '  - blocked_emails';
    RAISE NOTICE '  - blocked_ips';
    RAISE NOTICE '  - duplicate_account_detection';
    RAISE NOTICE '  - payment_fingerprints';
    RAISE NOTICE '✓ Seeded 20 common disposable email domains';
END $$;
