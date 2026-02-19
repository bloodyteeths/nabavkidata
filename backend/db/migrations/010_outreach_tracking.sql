-- Migration: 010_outreach_tracking.sql
-- Purpose: Track all leads and outreach status to prevent duplicate contacts

-- Main leads table with segmentation
CREATE TABLE IF NOT EXISTS outreach_leads (
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(500),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    company_name VARCHAR(500),
    job_title VARCHAR(255),

    -- Segmentation
    segment CHAR(1) NOT NULL DEFAULT 'C', -- A=tender, B=apollo, C=registry
    source VARCHAR(50) NOT NULL, -- 'enabavki', 'apollo', 'central_registry', 'serper'
    quality_score INT DEFAULT 50, -- 1-100

    -- Company data
    company_domain VARCHAR(255),
    company_industry VARCHAR(255),
    company_size VARCHAR(100),
    city VARCHAR(255),
    country VARCHAR(100) DEFAULT 'North Macedonia',

    -- Contact data
    linkedin_url TEXT,
    phone VARCHAR(100),

    -- Outreach tracking
    outreach_status VARCHAR(50) DEFAULT 'not_contacted',
    -- Values: not_contacted, email_1_sent, email_2_sent, email_3_sent,
    --         replied, converted, unsubscribed, bounced, complained

    first_contact_at TIMESTAMP,
    last_contact_at TIMESTAMP,
    total_emails_sent INT DEFAULT 0,

    -- Response tracking
    opened_count INT DEFAULT 0,
    clicked_count INT DEFAULT 0,
    replied_at TIMESTAMP,
    converted_at TIMESTAMP,
    unsubscribed_at TIMESTAMP,

    -- Source references
    supplier_id UUID REFERENCES suppliers(supplier_id),
    apollo_contact_id UUID,

    -- Metadata
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Individual email sends
CREATE TABLE IF NOT EXISTS outreach_emails (
    email_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES outreach_leads(lead_id) ON DELETE CASCADE,
    campaign_id UUID,

    email_sequence INT NOT NULL, -- 1, 2, 3
    subject TEXT,

    -- Tracking
    sent_at TIMESTAMP DEFAULT NOW(),
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    replied_at TIMESTAMP,

    -- Issues
    bounced BOOLEAN DEFAULT FALSE,
    bounce_reason TEXT,
    complained BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Campaign definitions
CREATE TABLE IF NOT EXISTS outreach_campaigns (
    campaign_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    segment CHAR(1) NOT NULL, -- A, B, C
    language VARCHAR(10) DEFAULT 'mk', -- mk, en, sr

    -- Email templates
    email_1_subject TEXT,
    email_1_body TEXT,
    email_2_subject TEXT,
    email_2_body TEXT,
    email_3_subject TEXT,
    email_3_body TEXT,

    -- Timing
    delay_days_1_to_2 INT DEFAULT 3,
    delay_days_2_to_3 INT DEFAULT 5,

    -- Status
    active BOOLEAN DEFAULT TRUE,
    leads_count INT DEFAULT 0,
    sent_count INT DEFAULT 0,
    opened_count INT DEFAULT 0,
    replied_count INT DEFAULT 0,
    converted_count INT DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_outreach_leads_email ON outreach_leads(email);
CREATE INDEX IF NOT EXISTS idx_outreach_leads_segment ON outreach_leads(segment);
CREATE INDEX IF NOT EXISTS idx_outreach_leads_status ON outreach_leads(outreach_status);
CREATE INDEX IF NOT EXISTS idx_outreach_leads_source ON outreach_leads(source);
CREATE INDEX IF NOT EXISTS idx_outreach_leads_quality ON outreach_leads(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_outreach_leads_company ON outreach_leads(company_name);

CREATE INDEX IF NOT EXISTS idx_outreach_emails_lead ON outreach_emails(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_emails_campaign ON outreach_emails(campaign_id);
CREATE INDEX IF NOT EXISTS idx_outreach_emails_sent ON outreach_emails(sent_at);

-- Function to update updated_at
CREATE OR REPLACE FUNCTION update_outreach_leads_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_outreach_leads_updated_at
    BEFORE UPDATE ON outreach_leads
    FOR EACH ROW
    EXECUTE FUNCTION update_outreach_leads_updated_at();

-- View for leads ready to contact
CREATE OR REPLACE VIEW leads_ready_for_outreach AS
SELECT
    ol.*,
    CASE
        WHEN outreach_status = 'not_contacted' THEN 1
        WHEN outreach_status = 'email_1_sent' AND last_contact_at < NOW() - INTERVAL '3 days' THEN 2
        WHEN outreach_status = 'email_2_sent' AND last_contact_at < NOW() - INTERVAL '5 days' THEN 3
        ELSE 0
    END as next_email_number
FROM outreach_leads ol
WHERE outreach_status NOT IN ('replied', 'converted', 'unsubscribed', 'bounced', 'complained', 'email_3_sent')
  AND (
      outreach_status = 'not_contacted'
      OR (outreach_status = 'email_1_sent' AND last_contact_at < NOW() - INTERVAL '3 days')
      OR (outreach_status = 'email_2_sent' AND last_contact_at < NOW() - INTERVAL '5 days')
  )
ORDER BY segment ASC, quality_score DESC;

-- Stats view
CREATE OR REPLACE VIEW outreach_stats AS
SELECT
    segment,
    source,
    COUNT(*) as total_leads,
    COUNT(CASE WHEN outreach_status = 'not_contacted' THEN 1 END) as not_contacted,
    COUNT(CASE WHEN outreach_status LIKE 'email_%' THEN 1 END) as contacted,
    COUNT(CASE WHEN outreach_status = 'replied' THEN 1 END) as replied,
    COUNT(CASE WHEN outreach_status = 'converted' THEN 1 END) as converted,
    COUNT(CASE WHEN outreach_status = 'unsubscribed' THEN 1 END) as unsubscribed,
    ROUND(AVG(quality_score), 1) as avg_quality_score
FROM outreach_leads
GROUP BY segment, source
ORDER BY segment, source;

COMMENT ON TABLE outreach_leads IS 'Central table for all outreach leads with deduplication and tracking';
COMMENT ON TABLE outreach_emails IS 'Individual email sends for tracking opens, clicks, replies';
COMMENT ON TABLE outreach_campaigns IS 'Campaign definitions with email templates per segment';
