-- Migration 026: Add data completeness flag to mv_flagged_tenders
-- Adds has_winner boolean so the UI can badge tenders with incomplete data
-- (112K opentender imports lack winner info, making some flags unreliable)

-- ============================================================================
-- STEP 1: Recreate mv_flagged_tenders with has_winner column
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS mv_flagged_tenders CASCADE;

CREATE MATERIALIZED VIEW mv_flagged_tenders AS
SELECT
    t.tender_id,
    t.title,
    t.procuring_entity,
    t.winner,
    t.estimated_value_mkd,
    t.status,
    (t.winner IS NOT NULL) as has_winner,
    COUNT(DISTINCT cf.flag_id) as total_flags,
    COALESCE(trs.risk_score, 0) as risk_score,
    COALESCE(trs.risk_level, 'minimal') as risk_level,
    COALESCE(
        MAX(
            CASE cf.severity
                WHEN 'critical' THEN 4
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 1
                ELSE 0
            END
        ),
        0
    ) as severity_rank,
    COALESCE(
        CASE MAX(
            CASE cf.severity
                WHEN 'critical' THEN 4
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 1
                ELSE 0
            END
        )
            WHEN 4 THEN 'critical'
            WHEN 3 THEN 'high'
            WHEN 2 THEN 'medium'
            WHEN 1 THEN 'low'
            ELSE 'medium'
        END,
        'medium'
    ) as max_severity,
    ARRAY_AGG(DISTINCT cf.flag_type) FILTER (WHERE cf.flag_type IS NOT NULL) as flag_types
FROM tenders t
INNER JOIN corruption_flags cf ON t.tender_id = cf.tender_id
    AND cf.false_positive = FALSE
LEFT JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
GROUP BY
    t.tender_id,
    t.title,
    t.procuring_entity,
    t.winner,
    t.estimated_value_mkd,
    t.status,
    trs.risk_score,
    trs.risk_level
HAVING COUNT(DISTINCT cf.flag_id) > 0;

-- Indexes for mv_flagged_tenders
CREATE UNIQUE INDEX idx_mv_flagged_tenders_tender_id
    ON mv_flagged_tenders(tender_id);

CREATE INDEX idx_mv_flagged_tenders_risk_score
    ON mv_flagged_tenders(risk_score DESC);

CREATE INDEX idx_mv_flagged_tenders_severity
    ON mv_flagged_tenders(max_severity);

CREATE INDEX idx_mv_flagged_tenders_has_winner
    ON mv_flagged_tenders(has_winner);

-- ============================================================================
-- STEP 2: Update refresh function to match new view
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_corruption_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_flagged_tenders;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_corruption_stats;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 3: Refresh the view with new schema
-- ============================================================================

REFRESH MATERIALIZED VIEW CONCURRENTLY mv_corruption_stats;
