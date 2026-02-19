-- Migration 045: Anonymous Whistleblower Portal Tables
-- Date: 2026-02-19
-- Phase: 4.5 - Anonymous Whistleblower Portal
--
-- Creates tables for:
-- 1. whistleblower_tips - Anonymous corruption tips with triage results
-- 2. tip_status_updates - Audit trail of status changes
--
-- Security notes:
-- - No IP addresses or user-agent strings are stored
-- - Tracking codes are cryptographically random (WB-XXXX-XXXX)
-- - Public-facing queries only use tracking_code, never tip_id

-- ============================================================================
-- Whistleblower Tips Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS whistleblower_tips (
    tip_id SERIAL PRIMARY KEY,
    tracking_code TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT 'other',  -- bid_rigging, bribery, conflict_of_interest, fraud, other
    description TEXT NOT NULL,
    evidence_urls JSONB DEFAULT '[]',

    -- Triage results (populated automatically by TipTriageEngine)
    triage_score FLOAT DEFAULT 0,
    urgency TEXT DEFAULT 'low',  -- low, medium, high, critical
    matched_tender_ids JSONB DEFAULT '[]',
    matched_entity_ids JSONB DEFAULT '[]',
    extracted_entities JSONB DEFAULT '[]',
    triage_details JSONB DEFAULT '{}',

    -- Management
    status TEXT NOT NULL DEFAULT 'new',  -- new, reviewing, investigating, verified, dismissed, linked
    linked_case_id INTEGER,

    -- Metadata (no identifying information stored for anonymity)
    submitted_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- Tip Status Updates (Audit Trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tip_status_updates (
    update_id SERIAL PRIMARY KEY,
    tip_id INTEGER NOT NULL REFERENCES whistleblower_tips(tip_id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT NOT NULL,
    note TEXT,
    updated_by TEXT DEFAULT 'system',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Public lookup by tracking code (anonymous status check)
CREATE INDEX IF NOT EXISTS idx_tips_tracking ON whistleblower_tips(tracking_code);

-- Admin filtering indexes
CREATE INDEX IF NOT EXISTS idx_tips_status ON whistleblower_tips(status);
CREATE INDEX IF NOT EXISTS idx_tips_category ON whistleblower_tips(category);
CREATE INDEX IF NOT EXISTS idx_tips_triage ON whistleblower_tips(triage_score DESC);
CREATE INDEX IF NOT EXISTS idx_tips_submitted ON whistleblower_tips(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_tips_urgency ON whistleblower_tips(urgency);

-- Status update audit trail
CREATE INDEX IF NOT EXISTS idx_tip_updates_tip ON tip_status_updates(tip_id);
CREATE INDEX IF NOT EXISTS idx_tip_updates_time ON tip_status_updates(updated_at DESC);

-- ============================================================================
-- Add foreign key to investigation_cases if the table exists
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'investigation_cases') THEN
        BEGIN
            ALTER TABLE whistleblower_tips
                ADD CONSTRAINT fk_tips_linked_case
                FOREIGN KEY (linked_case_id)
                REFERENCES investigation_cases(case_id)
                ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            -- Constraint already exists, skip
            NULL;
        END;
    END IF;
END $$;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE whistleblower_tips IS 'Anonymous corruption tips submitted through the whistleblower portal';
COMMENT ON TABLE tip_status_updates IS 'Status change history and audit trail for whistleblower tips';
COMMENT ON COLUMN whistleblower_tips.tracking_code IS 'Public tracking code for anonymous status checks (format: WB-XXXX-XXXX)';
COMMENT ON COLUMN whistleblower_tips.triage_score IS 'ML-computed credibility/priority score (0-100, higher = more credible/urgent)';
COMMENT ON COLUMN whistleblower_tips.urgency IS 'Urgency classification: low, medium, high, critical';
COMMENT ON COLUMN whistleblower_tips.matched_tender_ids IS 'Tender IDs found in database matching entities extracted from tip text';
COMMENT ON COLUMN whistleblower_tips.matched_entity_ids IS 'Company/institution names matched against procurement database';
COMMENT ON COLUMN whistleblower_tips.extracted_entities IS 'Named entities (companies, people, institutions) extracted from tip text';
COMMENT ON COLUMN whistleblower_tips.triage_details IS 'Full triage analysis: category_analysis, suggested_actions, detail_richness, specificity_score';
COMMENT ON COLUMN whistleblower_tips.linked_case_id IS 'Foreign key to investigation_cases when tip is linked to a formal investigation';
COMMENT ON COLUMN tip_status_updates.updated_by IS 'Who made the change: system (automated) or admin (manual review)';
