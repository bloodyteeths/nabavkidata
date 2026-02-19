-- Migration 044: Corruption Alert Pipeline Tables
-- Date: 2026-02-19
-- Purpose: Create tables for the real-time corruption alert pipeline (Phase 4.4).
--          Users can subscribe to alert rules and receive notifications when
--          tenders match their configured criteria.
--
-- Tables:
--   corruption_alert_subscriptions - User subscriptions to alert rules
--   corruption_alert_log           - Generated alerts for users
--   corruption_alert_state         - Pipeline state tracking (last evaluation timestamp)
--
-- Used by:
--   - ai/corruption/alerts/corruption_alerter.py (CorruptionAlerter)
--   - ai/corruption/alerts/evaluate_triggers.py (cron script)
--   - backend/api/corruption.py (Phase 4.4 alert endpoints)

-- ============================================================================
-- STEP 1: Alert Subscriptions - What each user wants to be alerted about
-- ============================================================================

CREATE TABLE IF NOT EXISTS corruption_alert_subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN (
        'high_risk_score',
        'single_bidder_high_value',
        'watched_entity',
        'multiple_flags',
        'repeat_pattern',
        'escalating_risk'
    )),
    rule_config JSONB DEFAULT '{}',
    severity_filter TEXT CHECK (severity_filter IS NULL OR severity_filter IN ('low', 'medium', 'high', 'critical')),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE corruption_alert_subscriptions IS
'User subscriptions to corruption alert rules. Each subscription defines a rule type,
optional configuration (e.g., thresholds, watched entities), and severity filter.
Phase 4.4 migration 044.';

COMMENT ON COLUMN corruption_alert_subscriptions.rule_type IS
'Type of alert rule: high_risk_score, single_bidder_high_value, watched_entity,
multiple_flags, repeat_pattern, escalating_risk';

COMMENT ON COLUMN corruption_alert_subscriptions.rule_config IS
'JSON configuration for the rule. Examples:
  high_risk_score: {"threshold": 80}
  single_bidder_high_value: {"value_threshold": 10000000}
  watched_entity: {"watched_entities": ["Company A", "Institution B"]}
  multiple_flags: {"flag_threshold": 4}
  repeat_pattern: {"repeat_threshold": 5}
  escalating_risk: {}';

COMMENT ON COLUMN corruption_alert_subscriptions.severity_filter IS
'Minimum severity level to trigger alert. NULL means all severities.
E.g., "high" means only high and critical alerts are delivered.';

-- ============================================================================
-- STEP 2: Alert Log - Generated alerts delivered to users
-- ============================================================================

CREATE TABLE IF NOT EXISTS corruption_alert_log (
    alert_id SERIAL PRIMARY KEY,
    subscription_id INTEGER REFERENCES corruption_alert_subscriptions(subscription_id) ON DELETE SET NULL,
    user_id TEXT NOT NULL,
    tender_id TEXT,
    rule_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    title TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE corruption_alert_log IS
'Generated corruption alerts for users. Each row represents one alert
triggered by a subscription rule matching a tender. Phase 4.4 migration 044.';

COMMENT ON COLUMN corruption_alert_log.details IS
'JSON details about the alert trigger. Contains rule-specific data like
risk_score, matched entities, flag counts, etc.';

-- ============================================================================
-- STEP 3: Alert State - Pipeline state tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS corruption_alert_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE corruption_alert_state IS
'Alert pipeline state tracking. Stores key-value pairs like the last
evaluation timestamp to enable incremental processing. Phase 4.4 migration 044.';

-- Seed initial state: last_evaluation starts at epoch so first run processes
-- all existing tenders with risk scores
INSERT INTO corruption_alert_state (key, value)
VALUES ('last_evaluation', '2020-01-01T00:00:00')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- STEP 4: Indexes for corruption_alert_subscriptions
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_alert_subs_user
    ON corruption_alert_subscriptions(user_id);

CREATE INDEX IF NOT EXISTS idx_alert_subs_active
    ON corruption_alert_subscriptions(active) WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_alert_subs_rule_type
    ON corruption_alert_subscriptions(rule_type);

-- Composite: find active subscriptions for a specific user
CREATE INDEX IF NOT EXISTS idx_alert_subs_user_active
    ON corruption_alert_subscriptions(user_id, active) WHERE active = TRUE;

-- ============================================================================
-- STEP 5: Indexes for corruption_alert_log
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_alert_log_user
    ON corruption_alert_log(user_id);

CREATE INDEX IF NOT EXISTS idx_alert_log_unread
    ON corruption_alert_log(user_id, read) WHERE read = FALSE;

CREATE INDEX IF NOT EXISTS idx_alert_log_created
    ON corruption_alert_log(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_log_severity
    ON corruption_alert_log(severity);

CREATE INDEX IF NOT EXISTS idx_alert_log_tender
    ON corruption_alert_log(tender_id);

CREATE INDEX IF NOT EXISTS idx_alert_log_rule_type
    ON corruption_alert_log(rule_type);

-- Deduplication index: prevent duplicate alerts for same user+tender+rule
CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_log_dedup
    ON corruption_alert_log(user_id, tender_id, rule_type);

-- Composite: user alerts ordered by creation date (for paginated listing)
CREATE INDEX IF NOT EXISTS idx_alert_log_user_created
    ON corruption_alert_log(user_id, created_at DESC);

-- ============================================================================
-- STEP 6: Verification
-- ============================================================================

SELECT 'Migration 044: Corruption Alert Pipeline Tables - Completed Successfully' AS status;

SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as total_size
FROM pg_tables
WHERE tablename IN (
    'corruption_alert_subscriptions',
    'corruption_alert_log',
    'corruption_alert_state'
)
ORDER BY tablename;
