-- Migration: 025_corruption_v2.sql
-- Date: 2026-02-18
-- Purpose: Expand corruption detection from 5 to 15 flag types
-- New flag types: procedure_type, identical_bids, professional_loser,
--   contract_splitting, short_decision, strategic_disqualification,
--   contract_value_growth, bid_rotation, threshold_manipulation, late_amendment
--
-- Changes:
--   0. Update CHECK constraint to allow all 15 flag types
--   1. Add index on corruption_flags(flag_type) for faster filtering
--   2. Drop and recreate mv_corruption_stats to include all 15 flag types
--   3. Drop and recreate mv_flagged_tenders (same logic, but ensures clean state)
--   4. Recreate refresh_corruption_views() function
--   5. Initial refresh

-- ============================================================================
-- STEP 1: Add index on corruption_flags(flag_type)
-- ============================================================================

-- Step 0: Update CHECK constraint to allow all 15 flag types
ALTER TABLE corruption_flags DROP CONSTRAINT IF EXISTS corruption_flags_flag_type_check;
ALTER TABLE corruption_flags ADD CONSTRAINT corruption_flags_flag_type_check
CHECK (flag_type IN (
    'single_bidder', 'repeat_winner', 'price_anomaly', 'bid_clustering', 'short_deadline',
    'high_amendments', 'spec_rigging', 'related_companies',
    'procedure_type', 'identical_bids', 'professional_loser', 'contract_splitting',
    'short_decision', 'strategic_disqualification', 'contract_value_growth',
    'bid_rotation', 'threshold_manipulation', 'late_amendment'
));

CREATE INDEX IF NOT EXISTS idx_corruption_flags_flag_type
    ON corruption_flags(flag_type);

-- ============================================================================
-- STEP 2: Recreate mv_corruption_stats
-- ============================================================================
-- The old view dynamically aggregates by_type from whatever flag_type values
-- exist in the table. However, the API needs ALL 15 types in the response
-- even if some have zero counts. We rebuild the view to guarantee all 15.

DROP MATERIALIZED VIEW IF EXISTS mv_corruption_stats CASCADE;

CREATE MATERIALIZED VIEW mv_corruption_stats AS
WITH flag_counts AS (
    SELECT
        COUNT(DISTINCT cf.flag_id) as total_flags,
        COUNT(DISTINCT cf.tender_id) as total_tenders_flagged,
        -- Breakdown by severity
        COUNT(DISTINCT cf.flag_id) FILTER (WHERE cf.severity = 'critical') as critical_count,
        COUNT(DISTINCT cf.flag_id) FILTER (WHERE cf.severity = 'high') as high_count,
        COUNT(DISTINCT cf.flag_id) FILTER (WHERE cf.severity = 'medium') as medium_count,
        COUNT(DISTINCT cf.flag_id) FILTER (WHERE cf.severity = 'low') as low_count
    FROM corruption_flags cf
    WHERE cf.false_positive = FALSE
),
-- Count each of the 15 flag types explicitly so the API always gets all keys
flag_type_counts AS (
    SELECT
        cf.flag_type,
        COUNT(DISTINCT cf.flag_id) as flag_count
    FROM corruption_flags cf
    WHERE cf.false_positive = FALSE
    GROUP BY cf.flag_type
),
-- Merge with the canonical list of 15 flag types, defaulting missing ones to 0
all_flag_types AS (
    SELECT
        ft.flag_type,
        COALESCE(ftc.flag_count, 0) as flag_count
    FROM (
        VALUES
            ('single_bidder'),
            ('repeat_winner'),
            ('price_anomaly'),
            ('bid_clustering'),
            ('short_deadline'),
            ('procedure_type'),
            ('identical_bids'),
            ('professional_loser'),
            ('contract_splitting'),
            ('short_decision'),
            ('strategic_disqualification'),
            ('contract_value_growth'),
            ('bid_rotation'),
            ('threshold_manipulation'),
            ('late_amendment')
    ) AS ft(flag_type)
    LEFT JOIN flag_type_counts ftc ON ft.flag_type = ftc.flag_type
),
flag_types_agg AS (
    SELECT
        jsonb_object_agg(flag_type, flag_count) as by_type
    FROM all_flag_types
),
value_at_risk AS (
    SELECT
        COALESCE(SUM(DISTINCT t.estimated_value_mkd), 0) as total_value
    FROM tenders t
    WHERE EXISTS (
        SELECT 1 FROM corruption_flags cf
        WHERE cf.tender_id = t.tender_id
        AND cf.false_positive = FALSE
    )
)
SELECT
    fc.total_flags,
    fc.total_tenders_flagged,
    var.total_value as total_value_at_risk_mkd,
    jsonb_build_object(
        'critical', fc.critical_count,
        'high', fc.high_count,
        'medium', fc.medium_count,
        'low', fc.low_count
    ) as by_severity,
    COALESCE(fta.by_type, '{}'::jsonb) as by_type
FROM flag_counts fc
CROSS JOIN flag_types_agg fta
CROSS JOIN value_at_risk var;

-- Unique index for CONCURRENTLY refresh support (single-row view)
CREATE UNIQUE INDEX idx_mv_corruption_stats_unique
    ON mv_corruption_stats((1));

COMMENT ON MATERIALIZED VIEW mv_corruption_stats IS
'Aggregated corruption detection statistics with all 15 flag types.
Single-row view. Refreshed daily at 5 AM UTC or after analysis runs.
Migration 025: expanded from 5 to 15 flag types.';

-- ============================================================================
-- STEP 3: Recreate mv_flagged_tenders
-- ============================================================================
-- The view itself aggregates dynamically by tender_id and does not hardcode
-- flag types, so it already handles new types. We recreate it to ensure
-- indexes are consistent and to pick up any schema changes.

DROP MATERIALIZED VIEW IF EXISTS mv_flagged_tenders CASCADE;

CREATE MATERIALIZED VIEW mv_flagged_tenders AS
SELECT
    t.tender_id,
    t.title,
    t.procuring_entity,
    t.winner,
    t.estimated_value_mkd,
    t.status,
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

CREATE INDEX idx_mv_flagged_tenders_max_severity
    ON mv_flagged_tenders(max_severity);

CREATE INDEX idx_mv_flagged_tenders_risk_level_score
    ON mv_flagged_tenders(risk_level, risk_score DESC);

CREATE INDEX idx_mv_flagged_tenders_procuring_entity
    ON mv_flagged_tenders(procuring_entity);

CREATE INDEX idx_mv_flagged_tenders_winner
    ON mv_flagged_tenders(winner);

CREATE INDEX idx_mv_flagged_tenders_flag_types
    ON mv_flagged_tenders USING GIN(flag_types);

COMMENT ON MATERIALIZED VIEW mv_flagged_tenders IS
'Pre-aggregated view of tenders with corruption flags (supports 15 flag types).
Refreshed daily at 5 AM UTC. Use REFRESH MATERIALIZED VIEW CONCURRENTLY to update.
Migration 025: recreated to support expanded corruption detection.';

-- ============================================================================
-- STEP 4: Recreate refresh_corruption_views() function
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_corruption_views()
RETURNS TABLE(
    view_name TEXT,
    refresh_status TEXT,
    row_count BIGINT,
    duration_ms INTEGER
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    v_row_count BIGINT;
BEGIN
    -- Refresh mv_flagged_tenders
    start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_flagged_tenders;
    end_time := clock_timestamp();

    SELECT COUNT(*) INTO v_row_count FROM mv_flagged_tenders;

    RETURN QUERY SELECT
        'mv_flagged_tenders'::TEXT,
        'success'::TEXT,
        v_row_count,
        EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER;

    -- Refresh mv_corruption_stats
    start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_corruption_stats;
    end_time := clock_timestamp();

    SELECT COUNT(*) INTO v_row_count FROM mv_corruption_stats;

    RETURN QUERY SELECT
        'mv_corruption_stats'::TEXT,
        'success'::TEXT,
        v_row_count,
        EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER;

EXCEPTION WHEN OTHERS THEN
    RETURN QUERY SELECT
        'error'::TEXT,
        SQLERRM::TEXT,
        0::BIGINT,
        0::INTEGER;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_corruption_views IS
'Refreshes all corruption detection materialized views concurrently.
Returns refresh status and timing for each view. Safe to run during peak hours.
Updated in migration 025 to support 15 flag types.';

-- ============================================================================
-- STEP 5: Initial refresh (non-concurrent since views were just recreated)
-- ============================================================================

SELECT 'Migration 025: Performing initial refresh of materialized views...' as status;

REFRESH MATERIALIZED VIEW mv_flagged_tenders;
REFRESH MATERIALIZED VIEW mv_corruption_stats;

-- Show results
SELECT 'Migration 025: Corruption Detection v2 - Completed Successfully' AS status;

SELECT
    'mv_flagged_tenders' as view_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size('mv_flagged_tenders')) as total_size
FROM mv_flagged_tenders
UNION ALL
SELECT
    'mv_corruption_stats' as view_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size('mv_corruption_stats')) as total_size
FROM mv_corruption_stats;
