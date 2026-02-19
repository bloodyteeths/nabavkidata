-- Migration 020: Tender Verification System
-- Supports the verification spider for flagged tender re-scraping and web enrichment

-- Table for storing verification results
CREATE TABLE IF NOT EXISTS tender_verifications (
    id SERIAL PRIMARY KEY,
    tender_id VARCHAR(100) NOT NULL UNIQUE REFERENCES tenders(tender_id) ON DELETE CASCADE,
    verified_at TIMESTAMP NOT NULL DEFAULT NOW(),
    source_url TEXT,

    -- Scraped data from e-nabavki
    scraped_data JSONB DEFAULT '{}',

    -- Discrepancies between DB and scraped data
    discrepancies JSONB DEFAULT '[]',

    -- Missing data that was filled
    missing_filled JSONB DEFAULT '[]',

    -- Web search context (Gemini enrichment)
    web_context JSONB,

    -- Corruption indicators from web search
    corruption_indicators JSONB DEFAULT '[]',

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for quick lookups
CREATE INDEX IF NOT EXISTS idx_tender_verifications_tender_id
    ON tender_verifications(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_verifications_verified_at
    ON tender_verifications(verified_at DESC);
CREATE INDEX IF NOT EXISTS idx_tender_verifications_has_indicators
    ON tender_verifications((jsonb_array_length(corruption_indicators) > 0));

-- Add web verification columns to corruption_flags if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'corruption_flags' AND column_name = 'web_verified'
    ) THEN
        ALTER TABLE corruption_flags ADD COLUMN web_verified BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'corruption_flags' AND column_name = 'web_context'
    ) THEN
        ALTER TABLE corruption_flags ADD COLUMN web_context JSONB;
    END IF;
END $$;

-- View for high-risk verified tenders
CREATE OR REPLACE VIEW high_risk_verified_tenders AS
SELECT
    tv.tender_id,
    t.title,
    t.procuring_entity,
    t.winner,
    t.estimated_value_mkd,
    t.actual_value_mkd,
    cf.anomaly_score,
    cf.flags,
    tv.discrepancies,
    tv.corruption_indicators,
    tv.web_context,
    tv.verified_at
FROM tender_verifications tv
JOIN tenders t ON t.tender_id = tv.tender_id
LEFT JOIN corruption_flags cf ON cf.tender_id = tv.tender_id
WHERE jsonb_array_length(tv.corruption_indicators) > 0
   OR jsonb_array_length(tv.discrepancies) > 0
   OR cf.anomaly_score > 0.7
ORDER BY cf.anomaly_score DESC NULLS LAST, tv.verified_at DESC;

-- Summary stats function
CREATE OR REPLACE FUNCTION get_verification_stats()
RETURNS TABLE (
    total_verified BIGINT,
    with_discrepancies BIGINT,
    with_missing_filled BIGINT,
    with_corruption_indicators BIGINT,
    high_risk_count BIGINT,
    last_verification TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE jsonb_array_length(discrepancies) > 0),
        COUNT(*) FILTER (WHERE jsonb_array_length(missing_filled) > 0),
        COUNT(*) FILTER (WHERE jsonb_array_length(corruption_indicators) > 0),
        COUNT(*) FILTER (WHERE cf.anomaly_score > 0.7),
        MAX(verified_at)
    FROM tender_verifications tv
    LEFT JOIN corruption_flags cf ON cf.tender_id = tv.tender_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE tender_verifications IS 'Stores results from verification spider that re-scrapes flagged tenders';
COMMENT ON VIEW high_risk_verified_tenders IS 'High-risk tenders that have been verified with discrepancies or corruption indicators';
