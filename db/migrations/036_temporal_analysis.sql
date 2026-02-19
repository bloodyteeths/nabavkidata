-- Migration: 036_temporal_analysis.sql
-- Date: 2026-02-19
-- Purpose: Create entity_temporal_profiles table for storing pre-computed
--          temporal risk analysis per institution/company.
--
-- Used by:
--   - ai/corruption/ml_models/batch_temporal.py (batch computation, weekly cron)
--   - backend/api/corruption.py (API endpoints for temporal analysis)
--
-- The TemporalAnalyzer computes rolling risk averages, trend slopes,
-- CUSUM-based change point detection, and trajectory classification
-- for each entity (institution or company) with 5+ tenders.

-- ============================================================================
-- STEP 1: Create entity_temporal_profiles table
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_temporal_profiles (
    profile_id SERIAL PRIMARY KEY,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('institution', 'company')),
    temporal_features JSONB NOT NULL DEFAULT '{}',
    trajectory TEXT CHECK (trajectory IN (
        'escalating', 'stable_high', 'stable_low',
        'declining', 'volatile', 'new_pattern',
        'moderate', 'insufficient_data'
    )),
    trajectory_confidence FLOAT DEFAULT 0.0,
    trajectory_description TEXT,
    trajectory_recommendation TEXT,
    change_points JSONB DEFAULT '[]',
    last_change_point_date DATE,
    risk_trend_slope FLOAT,
    risk_volatility FLOAT,
    summary_stats JSONB DEFAULT '{}',
    tender_count INTEGER DEFAULT 0,
    period_start DATE,
    period_end DATE,
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(entity_name, entity_type)
);

COMMENT ON TABLE entity_temporal_profiles IS
'Pre-computed temporal risk profiles for institutions and companies.
Built by batch_temporal.py (weekly cron). Each row contains rolling averages,
risk trend slopes, CUSUM change points, and trajectory classification.
Migration 036.';

COMMENT ON COLUMN entity_temporal_profiles.temporal_features IS
'JSONB with 15 temporal features: rolling_avg_risk_30d/90d/365d, risk_trend_slope,
risk_volatility, risk_acceleration, seasonality_score, days_since_last_flag,
flag_frequency_30d/90d, single_bidder_rate_30d/90d, avg_bidders_trend,
value_concentration, procurement_pace';

COMMENT ON COLUMN entity_temporal_profiles.trajectory IS
'Classified risk trajectory: escalating, stable_high, stable_low,
declining, volatile, new_pattern, moderate, insufficient_data';

COMMENT ON COLUMN entity_temporal_profiles.change_points IS
'JSONB array of CUSUM-detected change points. Each element:
{date, direction, magnitude, confidence, before_avg, after_avg}';

-- ============================================================================
-- STEP 2: Create indexes for common query patterns
-- ============================================================================

-- Filter by trajectory type (e.g. "show all escalating entities")
CREATE INDEX idx_temporal_trajectory
    ON entity_temporal_profiles(trajectory);

-- Rank by risk trend slope (steepest escalation first)
CREATE INDEX idx_temporal_trend
    ON entity_temporal_profiles(risk_trend_slope DESC);

-- Filter by entity type
CREATE INDEX idx_temporal_entity_type
    ON entity_temporal_profiles(entity_type);

-- Composite: type + trajectory for filtered listings
CREATE INDEX idx_temporal_type_trajectory
    ON entity_temporal_profiles(entity_type, trajectory);

-- Composite: type + trend for "most escalating" queries
CREATE INDEX idx_temporal_type_trend
    ON entity_temporal_profiles(entity_type, risk_trend_slope DESC);

-- Find entities with recent change points
CREATE INDEX idx_temporal_last_change
    ON entity_temporal_profiles(last_change_point_date DESC NULLS LAST);

-- Full-text search on entity name
CREATE INDEX idx_temporal_entity_name_trgm
    ON entity_temporal_profiles USING gin(entity_name gin_trgm_ops);

-- Volatility ranking
CREATE INDEX idx_temporal_volatility
    ON entity_temporal_profiles(risk_volatility DESC NULLS LAST);

-- JSONB index for change_points queries
CREATE INDEX idx_temporal_change_points_gin
    ON entity_temporal_profiles USING gin(change_points);

-- ============================================================================
-- STEP 3: Done
-- ============================================================================

SELECT 'Migration 036: Temporal Analysis Profiles - Completed Successfully' AS status;
