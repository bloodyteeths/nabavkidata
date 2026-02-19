-- Migration: 023_cold_outreach_drip.sql
-- Purpose: Extend outreach system for 5-step cold drip sequences with mk_companies integration
-- Date: 2026-02-16

-- ============================================================================
-- EXTEND outreach_campaigns FOR 5-STEP SEQUENCES
-- ============================================================================

ALTER TABLE outreach_campaigns
  ADD COLUMN IF NOT EXISTS email_4_subject TEXT,
  ADD COLUMN IF NOT EXISTS email_4_body TEXT,
  ADD COLUMN IF NOT EXISTS email_5_subject TEXT,
  ADD COLUMN IF NOT EXISTS email_5_body TEXT,
  ADD COLUMN IF NOT EXISTS delay_days_3_to_4 INT DEFAULT 7,
  ADD COLUMN IF NOT EXISTS delay_days_4_to_5 INT DEFAULT 7;

-- ============================================================================
-- LINK outreach_leads TO mk_companies
-- ============================================================================

ALTER TABLE outreach_leads
  ADD COLUMN IF NOT EXISTS mk_company_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_outreach_leads_mk_company ON outreach_leads(mk_company_id);

-- ============================================================================
-- UPDATE leads_ready_for_outreach VIEW (replace existing from migration 010)
-- Now supports 5 steps instead of 3
-- ============================================================================

DROP VIEW IF EXISTS leads_ready_for_outreach;
CREATE VIEW leads_ready_for_outreach AS
SELECT
    ol.*,
    CASE
        WHEN outreach_status = 'not_contacted' THEN 1
        WHEN outreach_status = 'email_1_sent' AND last_contact_at < NOW() - INTERVAL '3 days' THEN 2
        WHEN outreach_status = 'email_2_sent' AND last_contact_at < NOW() - INTERVAL '4 days' THEN 3
        WHEN outreach_status = 'email_3_sent' AND last_contact_at < NOW() - INTERVAL '7 days' THEN 4
        WHEN outreach_status = 'email_4_sent' AND last_contact_at < NOW() - INTERVAL '7 days' THEN 5
        ELSE 0
    END as next_email_number
FROM outreach_leads ol
WHERE outreach_status NOT IN ('replied', 'converted', 'unsubscribed', 'bounced', 'complained', 'email_5_sent')
  AND (
      outreach_status = 'not_contacted'
      OR (outreach_status = 'email_1_sent' AND last_contact_at < NOW() - INTERVAL '3 days')
      OR (outreach_status = 'email_2_sent' AND last_contact_at < NOW() - INTERVAL '4 days')
      OR (outreach_status = 'email_3_sent' AND last_contact_at < NOW() - INTERVAL '7 days')
      OR (outreach_status = 'email_4_sent' AND last_contact_at < NOW() - INTERVAL '7 days')
  )
ORDER BY segment ASC, quality_score DESC;

-- ============================================================================
-- UPDATE outreach_stats VIEW to reflect new statuses
-- ============================================================================

DROP VIEW IF EXISTS outreach_stats;
CREATE VIEW outreach_stats AS
SELECT
    segment,
    source,
    COUNT(*) as total_leads,
    COUNT(CASE WHEN outreach_status = 'not_contacted' THEN 1 END) as not_contacted,
    COUNT(CASE WHEN outreach_status LIKE 'email_%' THEN 1 END) as contacted,
    COUNT(CASE WHEN outreach_status = 'email_5_sent' THEN 1 END) as sequence_completed,
    COUNT(CASE WHEN outreach_status = 'replied' THEN 1 END) as replied,
    COUNT(CASE WHEN outreach_status = 'converted' THEN 1 END) as converted,
    COUNT(CASE WHEN outreach_status = 'unsubscribed' THEN 1 END) as unsubscribed,
    COUNT(CASE WHEN outreach_status = 'bounced' THEN 1 END) as bounced,
    ROUND(AVG(quality_score), 1) as avg_quality_score
FROM outreach_leads
GROUP BY segment, source
ORDER BY segment, source;

-- ============================================================================
-- EXTEND campaign_targets FOR 5 FOLLOW-UPS
-- ============================================================================

ALTER TABLE campaign_targets
  ADD COLUMN IF NOT EXISTS followup3_sent_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS followup4_sent_at TIMESTAMP;

-- Update targets_ready_for_followup view for 5 steps
DROP VIEW IF EXISTS targets_ready_for_followup;
CREATE VIEW targets_ready_for_followup AS
SELECT
    ct.*,
    rc.settings,
    CASE
        WHEN ct.sequence_step = 0
             AND ct.status IN ('delivered', 'opened')
             AND ct.initial_sent_at < NOW() - INTERVAL '3 days'
        THEN 1
        WHEN ct.sequence_step = 1
             AND ct.status IN ('delivered', 'opened', 'clicked')
             AND ct.followup1_sent_at < NOW() - INTERVAL '4 days'
        THEN 2
        WHEN ct.sequence_step = 2
             AND ct.status IN ('delivered', 'opened', 'clicked')
             AND ct.followup2_sent_at < NOW() - INTERVAL '7 days'
        THEN 3
        WHEN ct.sequence_step = 3
             AND ct.status IN ('delivered', 'opened', 'clicked')
             AND ct.followup3_sent_at < NOW() - INTERVAL '7 days'
        THEN 4
        ELSE 0
    END as next_followup
FROM campaign_targets ct
JOIN report_campaigns rc ON ct.campaign_id = rc.id
WHERE rc.status = 'active'
  AND ct.status NOT IN ('replied', 'converted', 'unsubscribed', 'bounced', 'failed')
  AND ct.sequence_step < 4;
