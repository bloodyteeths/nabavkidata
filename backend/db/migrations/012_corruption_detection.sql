-- Migration: Corruption Detection and Risk Scoring System
-- Date: 2025-12-17
-- Purpose: Add tables for tracking corruption flags, company relationships, and tender risk scores

-- ============================================================================
-- CORRUPTION FLAGS - Individual corruption indicators per tender
-- ============================================================================

CREATE TABLE IF NOT EXISTS corruption_flags (
    flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    flag_type VARCHAR(100) NOT NULL CHECK (flag_type IN (
        'single_bidder',
        'repeat_winner',
        'price_anomaly',
        'bid_clustering',
        'short_deadline',
        'high_amendments',
        'spec_rigging',
        'related_companies'
    )),
    severity VARCHAR(20) DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    evidence JSONB,
    description TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed BOOLEAN DEFAULT FALSE,
    reviewed_by UUID,
    review_notes TEXT,
    false_positive BOOLEAN DEFAULT FALSE
);

-- Indexes for corruption_flags
CREATE INDEX IF NOT EXISTS idx_corruption_flags_tender_id ON corruption_flags(tender_id);
CREATE INDEX IF NOT EXISTS idx_corruption_flags_flag_type ON corruption_flags(flag_type);
CREATE INDEX IF NOT EXISTS idx_corruption_flags_severity ON corruption_flags(severity);
CREATE INDEX IF NOT EXISTS idx_corruption_flags_score ON corruption_flags(score DESC);
CREATE INDEX IF NOT EXISTS idx_corruption_flags_detected_at ON corruption_flags(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_corruption_flags_reviewed ON corruption_flags(reviewed) WHERE reviewed = FALSE;
CREATE INDEX IF NOT EXISTS idx_corruption_flags_false_positive ON corruption_flags(false_positive) WHERE false_positive = FALSE;
CREATE INDEX IF NOT EXISTS idx_corruption_flags_evidence ON corruption_flags USING GIN(evidence);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_corruption_flags_tender_reviewed ON corruption_flags(tender_id, reviewed);
CREATE INDEX IF NOT EXISTS idx_corruption_flags_type_severity ON corruption_flags(flag_type, severity);

-- ============================================================================
-- COMPANY RELATIONSHIPS - Tracks relationships that may indicate collusion
-- ============================================================================

CREATE TABLE IF NOT EXISTS company_relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_a VARCHAR(500) NOT NULL,
    company_b VARCHAR(500) NOT NULL,
    relationship_type VARCHAR(100) NOT NULL CHECK (relationship_type IN (
        'same_owner',
        'same_address',
        'same_director',
        'parent_subsidiary',
        'shared_contact',
        'sequential_tax_id',
        'bid_cluster'
    )),
    confidence INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    evidence JSONB,
    source VARCHAR(100) CHECK (source IN ('database', 'web_search', 'registry')),
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_company_relationship UNIQUE(company_a, company_b, relationship_type)
);

-- Indexes for company_relationships
CREATE INDEX IF NOT EXISTS idx_company_relationships_company_a ON company_relationships(company_a);
CREATE INDEX IF NOT EXISTS idx_company_relationships_company_b ON company_relationships(company_b);
CREATE INDEX IF NOT EXISTS idx_company_relationships_type ON company_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_company_relationships_confidence ON company_relationships(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_company_relationships_source ON company_relationships(source);
CREATE INDEX IF NOT EXISTS idx_company_relationships_discovered_at ON company_relationships(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_company_relationships_verified ON company_relationships(verified);
CREATE INDEX IF NOT EXISTS idx_company_relationships_evidence ON company_relationships USING GIN(evidence);

-- Composite indexes for bidirectional lookups
CREATE INDEX IF NOT EXISTS idx_company_relationships_both_companies ON company_relationships(company_a, company_b);
CREATE INDEX IF NOT EXISTS idx_company_relationships_type_confidence ON company_relationships(relationship_type, confidence DESC);

-- ============================================================================
-- TENDER RISK SCORES - Aggregated risk scores per tender
-- ============================================================================

CREATE TABLE IF NOT EXISTS tender_risk_scores (
    tender_id VARCHAR(100) PRIMARY KEY REFERENCES tenders(tender_id) ON DELETE CASCADE,
    risk_score INTEGER NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('minimal', 'low', 'medium', 'high', 'critical')),
    flag_count INTEGER DEFAULT 0 CHECK (flag_count >= 0),
    last_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    flags_summary JSONB
);

-- Indexes for tender_risk_scores
CREATE INDEX IF NOT EXISTS idx_tender_risk_scores_risk_score ON tender_risk_scores(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_tender_risk_scores_risk_level ON tender_risk_scores(risk_level);
CREATE INDEX IF NOT EXISTS idx_tender_risk_scores_flag_count ON tender_risk_scores(flag_count DESC);
CREATE INDEX IF NOT EXISTS idx_tender_risk_scores_last_analyzed ON tender_risk_scores(last_analyzed DESC);
CREATE INDEX IF NOT EXISTS idx_tender_risk_scores_flags_summary ON tender_risk_scores USING GIN(flags_summary);

-- Composite index for filtering high-risk tenders
CREATE INDEX IF NOT EXISTS idx_tender_risk_scores_level_score ON tender_risk_scores(risk_level, risk_score DESC);

-- ============================================================================
-- TABLE COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE corruption_flags IS 'Stores individual corruption indicators detected in tenders';
COMMENT ON TABLE company_relationships IS 'Tracks relationships between companies that may indicate collusion';
COMMENT ON TABLE tender_risk_scores IS 'Aggregated risk scores and summaries per tender';

-- ============================================================================
-- HIGH-RISK TENDERS VIEW - Easy access to problematic tenders
-- ============================================================================

CREATE OR REPLACE VIEW high_risk_tenders AS
SELECT
    trs.tender_id,
    trs.risk_score,
    trs.risk_level,
    trs.flag_count,
    trs.last_analyzed,
    t.title,
    t.buyer_name,
    t.published_date,
    t.estimated_value,
    t.estimated_currency,
    array_agg(DISTINCT cf.flag_type) FILTER (WHERE cf.flag_type IS NOT NULL) as flag_types,
    array_agg(DISTINCT cf.severity) FILTER (WHERE cf.severity IS NOT NULL) as severities,
    trs.flags_summary
FROM tender_risk_scores trs
JOIN tenders t ON trs.tender_id = t.tender_id
LEFT JOIN corruption_flags cf ON trs.tender_id = cf.tender_id AND cf.false_positive = FALSE
WHERE trs.risk_level IN ('high', 'critical')
GROUP BY trs.tender_id, trs.risk_score, trs.risk_level, trs.flag_count, trs.last_analyzed,
         t.title, t.buyer_name, t.published_date, t.estimated_value, t.estimated_currency,
         trs.flags_summary
ORDER BY trs.risk_score DESC;

COMMENT ON VIEW high_risk_tenders IS 'View of tenders with high or critical risk levels, including flag details';

-- ============================================================================
-- FUNCTION: Update Tender Risk Score
-- ============================================================================

CREATE OR REPLACE FUNCTION update_tender_risk_score(p_tender_id VARCHAR(100))
RETURNS void AS $$
DECLARE
    v_risk_score INTEGER;
    v_flag_count INTEGER;
    v_risk_level VARCHAR(20);
    v_flags_summary JSONB;
BEGIN
    -- Calculate average score from all non-false-positive flags
    SELECT
        COALESCE(ROUND(AVG(score)), 0),
        COUNT(*),
        jsonb_agg(
            jsonb_build_object(
                'flag_type', flag_type,
                'severity', severity,
                'score', score,
                'detected_at', detected_at
            ) ORDER BY score DESC
        )
    INTO v_risk_score, v_flag_count, v_flags_summary
    FROM corruption_flags
    WHERE tender_id = p_tender_id
      AND false_positive = FALSE;

    -- Determine risk level based on score
    v_risk_level := CASE
        WHEN v_risk_score >= 80 THEN 'critical'
        WHEN v_risk_score >= 60 THEN 'high'
        WHEN v_risk_score >= 40 THEN 'medium'
        WHEN v_risk_score >= 20 THEN 'low'
        ELSE 'minimal'
    END;

    -- Insert or update the risk score
    INSERT INTO tender_risk_scores (tender_id, risk_score, risk_level, flag_count, flags_summary, last_analyzed)
    VALUES (p_tender_id, v_risk_score, v_risk_level, v_flag_count, v_flags_summary, CURRENT_TIMESTAMP)
    ON CONFLICT (tender_id)
    DO UPDATE SET
        risk_score = EXCLUDED.risk_score,
        risk_level = EXCLUDED.risk_level,
        flag_count = EXCLUDED.flag_count,
        flags_summary = EXCLUDED.flags_summary,
        last_analyzed = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_tender_risk_score IS 'Recalculates and updates the risk score for a tender based on its corruption flags';

-- ============================================================================
-- TRIGGER: Auto-update Risk Scores on Flag Changes
-- ============================================================================

CREATE OR REPLACE FUNCTION trigger_update_tender_risk_score()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM update_tender_risk_score(OLD.tender_id);
        RETURN OLD;
    ELSE
        PERFORM update_tender_risk_score(NEW.tender_id);
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS corruption_flags_risk_score_update ON corruption_flags;
CREATE TRIGGER corruption_flags_risk_score_update
    AFTER INSERT OR UPDATE OR DELETE ON corruption_flags
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_tender_risk_score();

COMMENT ON TRIGGER corruption_flags_risk_score_update ON corruption_flags IS 'Automatically updates tender risk scores when corruption flags are modified';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

SELECT 'Migration 012: Corruption Detection Tables - Completed Successfully' AS status;
