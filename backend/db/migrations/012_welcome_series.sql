-- Migration: Welcome Series Tracking
-- Created: 2025-12-18
-- Purpose: Track user onboarding email sequence

-- Welcome series progress tracking
CREATE TABLE IF NOT EXISTS welcome_series (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    current_step INT DEFAULT 0,  -- 0=registered, 1-6=emails sent
    started_at TIMESTAMP DEFAULT NOW(),
    last_email_at TIMESTAMP,
    next_email_at TIMESTAMP,     -- scheduled time for next email
    completed_at TIMESTAMP,      -- when series ended
    stopped_reason VARCHAR(50),  -- 'converted', 'unsubscribed', 'bounced', 'completed'

    -- Tracking
    email_1_sent_at TIMESTAMP,
    email_1_opened_at TIMESTAMP,
    email_2_sent_at TIMESTAMP,
    email_2_opened_at TIMESTAMP,
    email_3_sent_at TIMESTAMP,
    email_3_opened_at TIMESTAMP,
    email_4_sent_at TIMESTAMP,
    email_4_opened_at TIMESTAMP,
    email_5_sent_at TIMESTAMP,
    email_5_opened_at TIMESTAMP,
    email_6_sent_at TIMESTAMP,
    email_6_opened_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id)
);

-- Indexes for efficient queries
CREATE INDEX idx_welcome_series_next_email ON welcome_series(next_email_at)
    WHERE completed_at IS NULL AND stopped_reason IS NULL;
CREATE INDEX idx_welcome_series_user ON welcome_series(user_id);

-- View for users due for next welcome email
CREATE OR REPLACE VIEW users_due_welcome_email AS
SELECT
    ws.id as welcome_id,
    ws.user_id,
    ws.current_step,
    ws.next_email_at,
    u.email,
    u.full_name,
    u.subscription_tier,
    u.email_verified,
    u.created_at as user_created_at
FROM welcome_series ws
JOIN users u ON ws.user_id = u.user_id
WHERE ws.completed_at IS NULL
  AND ws.stopped_reason IS NULL
  AND ws.next_email_at <= NOW()
  AND u.email_verified = true
  AND u.subscription_tier = 'free'  -- Stop if they upgraded
ORDER BY ws.next_email_at ASC;

-- Function to start welcome series for new user
CREATE OR REPLACE FUNCTION start_welcome_series(p_user_id UUID)
RETURNS void AS $$
BEGIN
    INSERT INTO welcome_series (user_id, current_step, next_email_at)
    VALUES (p_user_id, 0, NOW())
    ON CONFLICT (user_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- Function to stop welcome series (on conversion)
CREATE OR REPLACE FUNCTION stop_welcome_series(p_user_id UUID, p_reason VARCHAR)
RETURNS void AS $$
BEGIN
    UPDATE welcome_series
    SET completed_at = NOW(),
        stopped_reason = p_reason,
        updated_at = NOW()
    WHERE user_id = p_user_id
      AND completed_at IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-stop series when user subscribes
CREATE OR REPLACE FUNCTION check_subscription_stop_welcome()
RETURNS TRIGGER AS $$
BEGIN
    -- If subscription becomes active and tier is not free, stop welcome series
    IF NEW.status = 'active' AND NEW.tier != 'free' THEN
        PERFORM stop_welcome_series(NEW.user_id, 'converted');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_subscription_stop_welcome ON subscriptions;
CREATE TRIGGER trigger_subscription_stop_welcome
    AFTER INSERT OR UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION check_subscription_stop_welcome();

-- Comment
COMMENT ON TABLE welcome_series IS 'Tracks 6-email welcome/onboarding series for new users';
