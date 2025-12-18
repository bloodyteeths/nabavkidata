-- Migration: Tender Alerts and Match Tracking System (Phase 6.1)
-- Date: 2025-12-18
-- Purpose: Create tables for the alerts matching engine

-- ============================================================================
-- TENDER ALERTS - User-defined alert criteria
-- ============================================================================

CREATE TABLE IF NOT EXISTS tender_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN (
        'keyword', 'cpv', 'entity', 'competitor', 'budget', 'combined'
    )),
    criteria JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    notification_channels TEXT[] DEFAULT ARRAY['email', 'in_app'],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for tender_alerts
CREATE INDEX IF NOT EXISTS idx_tender_alerts_user_id ON tender_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_tender_alerts_active ON tender_alerts(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_tender_alerts_type ON tender_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_tender_alerts_created_at ON tender_alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tender_alerts_criteria ON tender_alerts USING GIN(criteria);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_tender_alerts_user_active ON tender_alerts(user_id, is_active);

-- ============================================================================
-- ALERT MATCHES - Tracks tender matches for each alert
-- ============================================================================

CREATE TABLE IF NOT EXISTS alert_matches (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id UUID NOT NULL REFERENCES tender_alerts(alert_id) ON DELETE CASCADE,
    tender_id VARCHAR(100) NOT NULL,
    tender_source VARCHAR(20) DEFAULT 'e-nabavki',
    match_score NUMERIC(5,2) NOT NULL CHECK (match_score >= 0 AND match_score <= 100),
    match_reasons TEXT[] NOT NULL DEFAULT '{}',
    is_read BOOLEAN DEFAULT false,
    notified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_alert_tender UNIQUE(alert_id, tender_id)
);

-- Indexes for alert_matches
CREATE INDEX IF NOT EXISTS idx_alert_matches_alert_id ON alert_matches(alert_id);
CREATE INDEX IF NOT EXISTS idx_alert_matches_tender_id ON alert_matches(tender_id);
CREATE INDEX IF NOT EXISTS idx_alert_matches_is_read ON alert_matches(is_read) WHERE is_read = false;
CREATE INDEX IF NOT EXISTS idx_alert_matches_created_at ON alert_matches(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_matches_score ON alert_matches(match_score DESC);
CREATE INDEX IF NOT EXISTS idx_alert_matches_notified ON alert_matches(notified_at) WHERE notified_at IS NULL;

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_alert_matches_alert_unread ON alert_matches(alert_id, is_read) WHERE is_read = false;
CREATE INDEX IF NOT EXISTS idx_alert_matches_alert_created ON alert_matches(alert_id, created_at DESC);

-- ============================================================================
-- TABLE COMMENTS
-- ============================================================================

COMMENT ON TABLE tender_alerts IS 'User-defined alert criteria for matching tenders';
COMMENT ON TABLE alert_matches IS 'Records of tenders that matched user alerts';

COMMENT ON COLUMN tender_alerts.alert_type IS 'Type: keyword, cpv, entity, competitor, budget, combined';
COMMENT ON COLUMN tender_alerts.criteria IS 'JSONB with: keywords[], cpv_codes[], entities[], budget_min, budget_max, competitors[]';
COMMENT ON COLUMN tender_alerts.notification_channels IS 'Array of channels: email, in_app';

COMMENT ON COLUMN alert_matches.match_score IS 'Score 0-100 indicating match strength';
COMMENT ON COLUMN alert_matches.match_reasons IS 'Array of human-readable match reasons';
COMMENT ON COLUMN alert_matches.notified_at IS 'Timestamp when notification was sent (NULL if pending)';

-- ============================================================================
-- FUNCTION: Update alert timestamp on modification
-- ============================================================================

CREATE OR REPLACE FUNCTION update_tender_alert_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tender_alerts_update_timestamp ON tender_alerts;
CREATE TRIGGER tender_alerts_update_timestamp
    BEFORE UPDATE ON tender_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_tender_alert_timestamp();

-- ============================================================================
-- VIEW: Unread matches with alert and tender info
-- ============================================================================

CREATE OR REPLACE VIEW unread_alert_matches AS
SELECT
    am.match_id,
    am.alert_id,
    ta.name as alert_name,
    ta.user_id,
    am.tender_id,
    am.tender_source,
    am.match_score,
    am.match_reasons,
    am.created_at as matched_at,
    t.title as tender_title,
    t.procuring_entity,
    t.estimated_value_mkd,
    t.closing_date,
    t.status as tender_status
FROM alert_matches am
JOIN tender_alerts ta ON am.alert_id = ta.alert_id
LEFT JOIN tenders t ON am.tender_id = t.tender_id
WHERE am.is_read = false
ORDER BY am.created_at DESC;

COMMENT ON VIEW unread_alert_matches IS 'View of unread matches with alert and tender details';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

SELECT 'Migration 013: Tender Alerts Tables - Completed Successfully' AS status;
