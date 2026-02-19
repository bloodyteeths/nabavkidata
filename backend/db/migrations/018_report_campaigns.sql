-- Migration: 018_report_campaigns.sql
-- Purpose: Report-first outreach campaign with PDF reports, events logging, and follow-ups
-- Date: 2025-12-24

-- ============================================================================
-- REPORT CAMPAIGNS - Main campaign definitions
-- ============================================================================

CREATE TABLE IF NOT EXISTS report_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'draft', -- draft, active, paused, completed

    -- Campaign settings
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Settings include:
    -- {
    --   "min_participations": 5,        -- Min tender participations in 12 months
    --   "min_wins": 2,                   -- Min wins in 12 months
    --   "lookback_days": 365,            -- Lookback period for stats
    --   "missed_tenders_days": 90,       -- Days to look for missed opportunities
    --   "attach_pdf_first_n": 20,        -- Attach PDF to first N emails
    --   "daily_limit": 100,              -- Max emails per day
    --   "hourly_limit": 20,              -- Max emails per hour
    --   "min_jitter_seconds": 30,        -- Min delay between sends
    --   "max_jitter_seconds": 180,       -- Max delay between sends
    --   "followup_1_days": 3,            -- Days before first follow-up
    --   "followup_2_days": 7,            -- Days before second follow-up
    --   "report_valid_days": 14          -- How long signed URL is valid
    -- }

    -- Stats
    total_targets INTEGER DEFAULT 0,
    emails_sent INTEGER DEFAULT 0,
    emails_opened INTEGER DEFAULT 0,
    emails_clicked INTEGER DEFAULT 0,
    replies_received INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    unsubscribes INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- ============================================================================
-- CAMPAIGN TARGETS - Companies targeted in a campaign
-- ============================================================================

CREATE TABLE IF NOT EXISTS campaign_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES report_campaigns(id) ON DELETE CASCADE,
    company_id UUID, -- References suppliers(supplier_id) if exists
    company_name VARCHAR(500) NOT NULL,
    company_tax_id VARCHAR(50),
    email VARCHAR(255) NOT NULL,

    -- Email variant for A/B testing
    subject_variant CHAR(1) NOT NULL DEFAULT 'A', -- A or B

    -- Report reference
    report_id UUID,

    -- Status tracking
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    -- Values: pending, report_generated, sent, delivered, opened, clicked, replied, converted, unsubscribed, bounced, failed

    -- Sequence tracking
    sequence_step INTEGER DEFAULT 0, -- 0=initial, 1=followup1, 2=followup2
    initial_sent_at TIMESTAMP,
    followup1_sent_at TIMESTAMP,
    followup2_sent_at TIMESTAMP,

    -- Delivery method
    pdf_attached BOOLEAN DEFAULT FALSE,

    -- Postmark tracking
    postmark_message_id VARCHAR(255),

    -- Stats from report generation
    stats JSONB,
    -- {
    --   "participations_12m": 45,
    --   "wins_12m": 12,
    --   "win_rate": 26.7,
    --   "total_value_mkd": 5000000,
    --   "top_cpvs": [{"code": "33000000", "name": "Medical", "count": 20}],
    --   "top_buyers": [{"name": "ФЗОМ", "count": 8}],
    --   "top_competitors": [{"name": "Competitor", "wins": 5}],
    --   "missed_opportunities": 15,
    --   "expected_tenders_30d": {"low": 3, "mid": 7, "high": 12}
    -- }

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_event_at TIMESTAMP
);

-- ============================================================================
-- GENERATED REPORTS - PDF reports for companies
-- ============================================================================

CREATE TABLE IF NOT EXISTS generated_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES report_campaigns(id) ON DELETE SET NULL,
    company_id UUID,
    company_name VARCHAR(500) NOT NULL,
    company_tax_id VARCHAR(50),

    -- Report content
    stats JSONB NOT NULL,
    missed_opportunities JSONB, -- Array of missed tender objects
    competitor_data JSONB,      -- Competitor analysis data
    buyer_data JSONB,           -- Buyer relationship data

    -- File storage
    pdf_path TEXT,              -- Local or S3 path
    pdf_size_bytes INTEGER,
    signed_url TEXT,            -- Pre-signed URL for download
    signed_url_expires_at TIMESTAMP,

    -- Generation metadata
    generation_time_ms INTEGER,
    report_version VARCHAR(20) DEFAULT 'v1',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- OUTREACH EVENTS - Detailed event logging for all email interactions
-- ============================================================================

CREATE TABLE IF NOT EXISTS outreach_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES report_campaigns(id) ON DELETE SET NULL,
    target_id UUID REFERENCES campaign_targets(id) ON DELETE SET NULL,
    email VARCHAR(255) NOT NULL,

    -- Event details
    event_type VARCHAR(50) NOT NULL,
    -- Values: sent, delivered, opened, clicked, bounced, complained, unsubscribed, replied, converted

    sequence_step INTEGER DEFAULT 0,

    -- Event payload from Postmark
    payload JSONB,
    -- For clicks: {"link": "https://..."}
    -- For bounces: {"type": "HardBounce", "description": "..."}

    -- Metadata
    postmark_message_id VARCHAR(255),
    ip_address VARCHAR(50),
    user_agent TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- UNSUBSCRIBES - Track unsubscribe requests with tokens
-- ============================================================================

CREATE TABLE IF NOT EXISTS campaign_unsubscribes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    company_id UUID,
    company_name VARCHAR(500),

    -- Token for verification
    token VARCHAR(64) NOT NULL,

    -- Source of unsubscribe
    source VARCHAR(50) NOT NULL, -- email_link, reply_stop, manual, postmark_complaint
    campaign_id UUID REFERENCES report_campaigns(id) ON DELETE SET NULL,

    reason TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- EMAIL ENRICHMENT QUEUE - For Gemini web search enrichment
-- ============================================================================

CREATE TABLE IF NOT EXISTS email_enrichment_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(500) NOT NULL,
    company_tax_id VARCHAR(50),
    company_id UUID,

    -- Search status
    status VARCHAR(30) NOT NULL DEFAULT 'pending', -- pending, searching, found, not_found, failed

    -- Search results
    emails_found JSONB, -- Array of {email, confidence, source}
    selected_email VARCHAR(255),
    search_attempts INTEGER DEFAULT 0,
    last_search_at TIMESTAMP,

    -- Error tracking
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INVOICE REQUESTS - Track companies that replied "INVOICE"
-- ============================================================================

CREATE TABLE IF NOT EXISTS invoice_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES report_campaigns(id) ON DELETE SET NULL,
    target_id UUID REFERENCES campaign_targets(id) ON DELETE SET NULL,

    email VARCHAR(255) NOT NULL,
    company_name VARCHAR(500),
    company_id UUID,

    -- Request details
    status VARCHAR(30) NOT NULL DEFAULT 'pending', -- pending, sent, paid, cancelled

    -- Invoice details
    invoice_number VARCHAR(50),
    invoice_amount_eur DECIMAL(10,2),
    invoice_sent_at TIMESTAMP,
    payment_received_at TIMESTAMP,

    -- Notes
    notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Report campaigns
CREATE INDEX IF NOT EXISTS idx_report_campaigns_status ON report_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_report_campaigns_created ON report_campaigns(created_at DESC);

-- Campaign targets
CREATE INDEX IF NOT EXISTS idx_campaign_targets_campaign ON campaign_targets(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_status ON campaign_targets(status);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_email ON campaign_targets(email);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_company ON campaign_targets(company_name);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_sequence ON campaign_targets(sequence_step);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_initial_sent ON campaign_targets(initial_sent_at);

-- Generated reports
CREATE INDEX IF NOT EXISTS idx_generated_reports_campaign ON generated_reports(campaign_id);
CREATE INDEX IF NOT EXISTS idx_generated_reports_company ON generated_reports(company_name);
CREATE INDEX IF NOT EXISTS idx_generated_reports_created ON generated_reports(created_at DESC);

-- Outreach events
CREATE INDEX IF NOT EXISTS idx_outreach_events_campaign ON outreach_events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_outreach_events_target ON outreach_events(target_id);
CREATE INDEX IF NOT EXISTS idx_outreach_events_email ON outreach_events(email);
CREATE INDEX IF NOT EXISTS idx_outreach_events_type ON outreach_events(event_type);
CREATE INDEX IF NOT EXISTS idx_outreach_events_created ON outreach_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outreach_events_postmark ON outreach_events(postmark_message_id);

-- Unsubscribes
CREATE INDEX IF NOT EXISTS idx_campaign_unsubscribes_email ON campaign_unsubscribes(email);
CREATE INDEX IF NOT EXISTS idx_campaign_unsubscribes_token ON campaign_unsubscribes(token);

-- Email enrichment queue
CREATE INDEX IF NOT EXISTS idx_email_enrichment_status ON email_enrichment_queue(status);
CREATE INDEX IF NOT EXISTS idx_email_enrichment_company ON email_enrichment_queue(company_name);

-- Invoice requests
CREATE INDEX IF NOT EXISTS idx_invoice_requests_campaign ON invoice_requests(campaign_id);
CREATE INDEX IF NOT EXISTS idx_invoice_requests_status ON invoice_requests(status);
CREATE INDEX IF NOT EXISTS idx_invoice_requests_email ON invoice_requests(email);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_report_campaign_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_report_campaigns_updated ON report_campaigns;
CREATE TRIGGER trigger_report_campaigns_updated
    BEFORE UPDATE ON report_campaigns
    FOR EACH ROW
    EXECUTE FUNCTION update_report_campaign_timestamp();

DROP TRIGGER IF EXISTS trigger_campaign_targets_updated ON campaign_targets;
CREATE TRIGGER trigger_campaign_targets_updated
    BEFORE UPDATE ON campaign_targets
    FOR EACH ROW
    EXECUTE FUNCTION update_report_campaign_timestamp();

DROP TRIGGER IF EXISTS trigger_email_enrichment_updated ON email_enrichment_queue;
CREATE TRIGGER trigger_email_enrichment_updated
    BEFORE UPDATE ON email_enrichment_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_report_campaign_timestamp();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Campaign overview stats
CREATE OR REPLACE VIEW campaign_stats_view AS
SELECT
    rc.id as campaign_id,
    rc.name,
    rc.status,
    rc.total_targets,
    COUNT(ct.id) as actual_targets,
    COUNT(CASE WHEN ct.status = 'sent' THEN 1 END) as sent,
    COUNT(CASE WHEN ct.status = 'delivered' THEN 1 END) as delivered,
    COUNT(CASE WHEN ct.status = 'opened' THEN 1 END) as opened,
    COUNT(CASE WHEN ct.status = 'clicked' THEN 1 END) as clicked,
    COUNT(CASE WHEN ct.status = 'replied' THEN 1 END) as replied,
    COUNT(CASE WHEN ct.status = 'converted' THEN 1 END) as converted,
    COUNT(CASE WHEN ct.status = 'unsubscribed' THEN 1 END) as unsubscribed,
    COUNT(CASE WHEN ct.status = 'bounced' THEN 1 END) as bounced,
    ROUND(100.0 * COUNT(CASE WHEN ct.status = 'opened' THEN 1 END) / NULLIF(COUNT(CASE WHEN ct.status IN ('sent', 'delivered', 'opened', 'clicked', 'replied', 'converted') THEN 1 END), 0), 1) as open_rate,
    ROUND(100.0 * COUNT(CASE WHEN ct.status = 'clicked' THEN 1 END) / NULLIF(COUNT(CASE WHEN ct.status = 'opened' THEN 1 END), 0), 1) as click_rate,
    rc.created_at,
    rc.started_at
FROM report_campaigns rc
LEFT JOIN campaign_targets ct ON rc.id = ct.campaign_id
GROUP BY rc.id, rc.name, rc.status, rc.total_targets, rc.created_at, rc.started_at;

-- Targets ready for follow-up
CREATE OR REPLACE VIEW targets_ready_for_followup AS
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
        ELSE 0
    END as next_followup
FROM campaign_targets ct
JOIN report_campaigns rc ON ct.campaign_id = rc.id
WHERE rc.status = 'active'
  AND ct.status NOT IN ('replied', 'converted', 'unsubscribed', 'bounced', 'failed')
  AND ct.sequence_step < 2;

-- Daily sending stats for rate limiting
CREATE OR REPLACE VIEW daily_sending_stats AS
SELECT
    DATE(created_at) as send_date,
    DATE_TRUNC('hour', created_at) as send_hour,
    COUNT(*) as emails_sent
FROM outreach_events
WHERE event_type = 'sent'
  AND created_at >= CURRENT_DATE
GROUP BY DATE(created_at), DATE_TRUNC('hour', created_at)
ORDER BY send_date DESC, send_hour DESC;

COMMENT ON TABLE report_campaigns IS 'Report-first outreach campaigns with PDF intelligence reports';
COMMENT ON TABLE campaign_targets IS 'Individual company targets within a campaign';
COMMENT ON TABLE generated_reports IS 'PDF reports generated for each company';
COMMENT ON TABLE outreach_events IS 'All email events (sends, opens, clicks, bounces, etc.)';
COMMENT ON TABLE campaign_unsubscribes IS 'Unsubscribe requests with verification tokens';
COMMENT ON TABLE email_enrichment_queue IS 'Queue for finding company emails via web search';
COMMENT ON TABLE invoice_requests IS 'Companies that requested invoices via email reply';
