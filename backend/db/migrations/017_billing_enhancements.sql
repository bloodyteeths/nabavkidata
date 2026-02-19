-- Migration 017: Billing Enhancements
-- Adds webhook idempotency, usage counters, trial credits, and invoice requests
--
-- Requirements:
-- - Webhook signature verification with idempotency
-- - Usage counters with daily/monthly reset
-- - Trial credits for 7-day Pro trial
-- - EUR invoice flow for SEPA payments

BEGIN;

-- ============================================================================
-- WEBHOOK IDEMPOTENCY
-- ============================================================================

-- Store processed Stripe webhook events to prevent duplicate processing
CREATE TABLE IF NOT EXISTS webhook_events (
    event_id VARCHAR(255) PRIMARY KEY,  -- Stripe event ID (evt_xxx)
    event_type VARCHAR(100) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB,
    status VARCHAR(20) DEFAULT 'processed',  -- processed, failed, skipped
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_type ON webhook_events(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_events_processed_at ON webhook_events(processed_at);

-- Cleanup old webhook events (keep 90 days)
-- Run via cron: DELETE FROM webhook_events WHERE processed_at < NOW() - INTERVAL '90 days';


-- ============================================================================
-- USAGE COUNTERS
-- ============================================================================

-- Track usage per user with daily/monthly reset periods
CREATE TABLE IF NOT EXISTS usage_counters (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    counter_type VARCHAR(50) NOT NULL,  -- rag_queries, exports, document_extractions, etc.
    period_type VARCHAR(10) NOT NULL,   -- daily, monthly
    period_start DATE NOT NULL,         -- Start of the counting period
    count INTEGER NOT NULL DEFAULT 0,
    limit_value INTEGER,                -- NULL = unlimited
    last_reset_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, counter_type, period_type, period_start)
);

CREATE INDEX IF NOT EXISTS idx_usage_counters_user ON usage_counters(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_counters_period ON usage_counters(period_start);
CREATE INDEX IF NOT EXISTS idx_usage_counters_type ON usage_counters(counter_type);

-- Function to get or create usage counter
CREATE OR REPLACE FUNCTION get_or_create_usage_counter(
    p_user_id UUID,
    p_counter_type VARCHAR(50),
    p_period_type VARCHAR(10),
    p_limit_value INTEGER DEFAULT NULL
) RETURNS usage_counters AS $$
DECLARE
    v_period_start DATE;
    v_counter usage_counters;
BEGIN
    -- Calculate period start
    IF p_period_type = 'daily' THEN
        v_period_start := CURRENT_DATE;
    ELSIF p_period_type = 'monthly' THEN
        v_period_start := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    ELSE
        RAISE EXCEPTION 'Invalid period_type: %', p_period_type;
    END IF;

    -- Try to get existing counter
    SELECT * INTO v_counter
    FROM usage_counters
    WHERE user_id = p_user_id
      AND counter_type = p_counter_type
      AND period_type = p_period_type
      AND period_start = v_period_start;

    -- Create if doesn't exist
    IF NOT FOUND THEN
        INSERT INTO usage_counters (user_id, counter_type, period_type, period_start, count, limit_value)
        VALUES (p_user_id, p_counter_type, p_period_type, v_period_start, 0, p_limit_value)
        RETURNING * INTO v_counter;
    END IF;

    RETURN v_counter;
END;
$$ LANGUAGE plpgsql;

-- Function to increment usage counter (returns true if allowed, false if limit reached)
CREATE OR REPLACE FUNCTION increment_usage_counter(
    p_user_id UUID,
    p_counter_type VARCHAR(50),
    p_period_type VARCHAR(10),
    p_increment INTEGER DEFAULT 1
) RETURNS BOOLEAN AS $$
DECLARE
    v_counter usage_counters;
    v_period_start DATE;
BEGIN
    -- Calculate period start
    IF p_period_type = 'daily' THEN
        v_period_start := CURRENT_DATE;
    ELSE
        v_period_start := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    END IF;

    -- Get counter
    SELECT * INTO v_counter
    FROM usage_counters
    WHERE user_id = p_user_id
      AND counter_type = p_counter_type
      AND period_type = p_period_type
      AND period_start = v_period_start
    FOR UPDATE;

    -- Check limit
    IF v_counter.limit_value IS NOT NULL AND v_counter.count + p_increment > v_counter.limit_value THEN
        RETURN FALSE;
    END IF;

    -- Increment
    UPDATE usage_counters
    SET count = count + p_increment,
        updated_at = NOW()
    WHERE id = v_counter.id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- TRIAL CREDITS
-- ============================================================================

-- Store trial credits for 7-day Pro trial
CREATE TABLE IF NOT EXISTS trial_credits (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    credit_type VARCHAR(50) NOT NULL,  -- ai_messages, document_extractions, exports, competitor_alerts
    total_credits INTEGER NOT NULL,
    used_credits INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, credit_type)
);

CREATE INDEX IF NOT EXISTS idx_trial_credits_user ON trial_credits(user_id);
CREATE INDEX IF NOT EXISTS idx_trial_credits_expires ON trial_credits(expires_at);

-- Function to use trial credit (returns remaining credits, -1 if no credits left)
CREATE OR REPLACE FUNCTION use_trial_credit(
    p_user_id UUID,
    p_credit_type VARCHAR(50),
    p_amount INTEGER DEFAULT 1
) RETURNS INTEGER AS $$
DECLARE
    v_credit trial_credits;
    v_remaining INTEGER;
BEGIN
    -- Get credit record
    SELECT * INTO v_credit
    FROM trial_credits
    WHERE user_id = p_user_id
      AND credit_type = p_credit_type
      AND expires_at > NOW()
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN -1;
    END IF;

    -- Check if enough credits
    IF v_credit.used_credits + p_amount > v_credit.total_credits THEN
        RETURN -1;
    END IF;

    -- Use credit
    UPDATE trial_credits
    SET used_credits = used_credits + p_amount,
        updated_at = NOW()
    WHERE id = v_credit.id
    RETURNING (total_credits - used_credits) INTO v_remaining;

    RETURN v_remaining;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- INVOICE REQUESTS (EUR/SEPA flow)
-- ============================================================================

-- Store invoice requests for EUR SEPA payments
CREATE TABLE IF NOT EXISTS invoice_requests (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    stripe_invoice_id VARCHAR(255),
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'eur',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, sent, paid, failed, cancelled
    company_name VARCHAR(255),
    company_address TEXT,
    tax_id VARCHAR(50),
    billing_email VARCHAR(255),
    notes TEXT,
    due_date DATE,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_requests_user ON invoice_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_invoice_requests_status ON invoice_requests(status);


-- ============================================================================
-- SUBSCRIPTIONS TABLE ENHANCEMENTS
-- ============================================================================

-- Add currency and price ID tracking to subscriptions
DO $$
BEGIN
    -- Add currency column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'subscriptions' AND column_name = 'currency') THEN
        ALTER TABLE subscriptions ADD COLUMN currency VARCHAR(3) DEFAULT 'mkd';
    END IF;

    -- Add stripe_price_id column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'subscriptions' AND column_name = 'stripe_price_id') THEN
        ALTER TABLE subscriptions ADD COLUMN stripe_price_id VARCHAR(255);
    END IF;

    -- Add interval column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'subscriptions' AND column_name = 'billing_interval') THEN
        ALTER TABLE subscriptions ADD COLUMN billing_interval VARCHAR(10) DEFAULT 'monthly';
    END IF;
END $$;


-- ============================================================================
-- USERS TABLE ENHANCEMENTS
-- ============================================================================

-- Add trial tracking fields to users
DO $$
BEGIN
    -- Add trial_started_at column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'trial_started_at') THEN
        ALTER TABLE users ADD COLUMN trial_started_at TIMESTAMPTZ;
    END IF;

    -- Add trial_ends_at column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'trial_ends_at') THEN
        ALTER TABLE users ADD COLUMN trial_ends_at TIMESTAMPTZ;
    END IF;

    -- Add trial_expired column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'trial_expired') THEN
        ALTER TABLE users ADD COLUMN trial_expired BOOLEAN DEFAULT FALSE;
    END IF;

    -- Add preferred_currency column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'preferred_currency') THEN
        ALTER TABLE users ADD COLUMN preferred_currency VARCHAR(3) DEFAULT 'mkd';
    END IF;
END $$;


-- ============================================================================
-- SUBSCRIPTION TIER MAPPING VIEW
-- ============================================================================

-- View for easy tier lookup with limits
CREATE OR REPLACE VIEW subscription_tier_limits AS
SELECT
    u.user_id,
    u.email,
    COALESCE(s.tier, u.subscription_tier, 'free') as tier,
    COALESCE(s.status, 'free') as status,
    s.current_period_start,
    s.current_period_end,
    u.trial_started_at,
    u.trial_ends_at,
    u.trial_expired,
    CASE
        WHEN u.trial_ends_at IS NOT NULL AND u.trial_ends_at > NOW() THEN TRUE
        ELSE FALSE
    END as is_in_trial,
    CASE
        WHEN COALESCE(s.tier, u.subscription_tier) = 'enterprise' THEN NULL  -- unlimited
        WHEN COALESCE(s.tier, u.subscription_tier) = 'team' THEN NULL
        WHEN COALESCE(s.tier, u.subscription_tier) = 'pro' THEN 50
        WHEN COALESCE(s.tier, u.subscription_tier) = 'start' THEN 15
        ELSE 3
    END as daily_rag_limit,
    CASE
        WHEN COALESCE(s.tier, u.subscription_tier) IN ('enterprise', 'team') THEN TRUE
        ELSE FALSE
    END as has_api_access
FROM users u
LEFT JOIN subscriptions s ON u.user_id = s.user_id
    AND s.status IN ('active', 'trialing')
    AND (s.current_period_end IS NULL OR s.current_period_end > NOW());


-- ============================================================================
-- AUDIT LOG ENHANCEMENTS
-- ============================================================================

-- Add billing-specific audit events index
CREATE INDEX IF NOT EXISTS idx_audit_log_billing_events
ON audit_log(action)
WHERE action IN (
    'checkout_created',
    'subscription_created',
    'subscription_cancelled',
    'subscription_upgraded',
    'payment_succeeded',
    'payment_failed',
    'trial_started',
    'trial_ended',
    'trial_credit_used'
);


COMMIT;

-- ============================================================================
-- NOTES
-- ============================================================================
--
-- Cron jobs to add:
-- 1. Reset daily counters:
--    UPDATE usage_counters SET count = 0, last_reset_at = NOW()
--    WHERE period_type = 'daily' AND period_start < CURRENT_DATE;
--
-- 2. Expire trials:
--    UPDATE users SET trial_expired = TRUE, subscription_tier = 'free'
--    WHERE trial_ends_at < NOW() AND trial_expired = FALSE;
--
-- 3. Cleanup old webhook events:
--    DELETE FROM webhook_events WHERE processed_at < NOW() - INTERVAL '90 days';
