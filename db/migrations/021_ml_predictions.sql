-- Migration 021: ML Predictions Table
-- Purpose: Store ML model prediction results for corruption detection
-- Date: 2025-12-26

-- ============================================================================
-- ML PREDICTIONS - Stores individual prediction results from ensemble model
-- ============================================================================

CREATE TABLE IF NOT EXISTS ml_predictions (
    id SERIAL PRIMARY KEY,
    tender_id VARCHAR(100) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,

    -- Prediction results
    risk_score NUMERIC(5,2) NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('minimal', 'low', 'medium', 'high', 'critical')),
    confidence NUMERIC(4,3) CHECK (confidence >= 0 AND confidence <= 1),

    -- Individual model scores (stored as JSONB for flexibility)
    model_scores JSONB DEFAULT '{}',

    -- Feature importance / SHAP values (optional, can be large)
    feature_importance JSONB,

    -- Top contributing features (for quick display)
    top_features JSONB,

    -- Model metadata
    model_version VARCHAR(50),
    ensemble_type VARCHAR(50) DEFAULT 'stacking',

    -- Timestamps
    predicted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint: one active prediction per tender per model version
    CONSTRAINT unique_tender_model_prediction UNIQUE(tender_id, model_version)
);

-- Indexes for ml_predictions
CREATE INDEX IF NOT EXISTS idx_ml_predictions_tender_id ON ml_predictions(tender_id);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_risk_score ON ml_predictions(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_risk_level ON ml_predictions(risk_level);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_predicted_at ON ml_predictions(predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_model_version ON ml_predictions(model_version);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_confidence ON ml_predictions(confidence DESC);

-- GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_ml_predictions_model_scores ON ml_predictions USING GIN(model_scores);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_top_features ON ml_predictions USING GIN(top_features);

-- Composite index for filtering high-risk predictions
CREATE INDEX IF NOT EXISTS idx_ml_predictions_level_score ON ml_predictions(risk_level, risk_score DESC);

-- ============================================================================
-- ML PREDICTION BATCHES - Track batch prediction runs
-- ============================================================================

CREATE TABLE IF NOT EXISTS ml_prediction_batches (
    batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Batch metadata
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),

    -- Statistics
    total_tenders INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    high_risk_count INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,

    -- Error tracking
    error_message TEXT,
    failed_tender_ids TEXT[],

    -- Model info
    model_version VARCHAR(50),

    -- Summary statistics
    avg_score NUMERIC(5,2),
    median_score NUMERIC(5,2),
    score_distribution JSONB
);

CREATE INDEX IF NOT EXISTS idx_ml_prediction_batches_status ON ml_prediction_batches(status);
CREATE INDEX IF NOT EXISTS idx_ml_prediction_batches_started_at ON ml_prediction_batches(started_at DESC);

-- ============================================================================
-- FUNCTION: Get latest prediction for a tender
-- ============================================================================

CREATE OR REPLACE FUNCTION get_latest_ml_prediction(p_tender_id VARCHAR(100))
RETURNS TABLE (
    risk_score NUMERIC,
    risk_level VARCHAR,
    confidence NUMERIC,
    model_scores JSONB,
    top_features JSONB,
    predicted_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        mp.risk_score,
        mp.risk_level,
        mp.confidence,
        mp.model_scores,
        mp.top_features,
        mp.predicted_at
    FROM ml_predictions mp
    WHERE mp.tender_id = p_tender_id
    ORDER BY mp.predicted_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEW: Recent high-risk predictions
-- ============================================================================

CREATE OR REPLACE VIEW recent_high_risk_predictions AS
SELECT
    mp.id,
    mp.tender_id,
    mp.risk_score,
    mp.risk_level,
    mp.confidence,
    mp.model_scores,
    mp.top_features,
    mp.predicted_at,
    t.title,
    t.procuring_entity,
    t.winner,
    t.estimated_value_mkd,
    t.status
FROM ml_predictions mp
JOIN tenders t ON mp.tender_id = t.tender_id
WHERE mp.risk_level IN ('high', 'critical')
  AND mp.predicted_at > NOW() - INTERVAL '30 days'
ORDER BY mp.risk_score DESC, mp.predicted_at DESC;

COMMENT ON VIEW recent_high_risk_predictions IS 'Recent high-risk ML predictions with tender details';

-- ============================================================================
-- TABLE COMMENTS
-- ============================================================================

COMMENT ON TABLE ml_predictions IS 'Stores ML model prediction results for corruption risk detection';
COMMENT ON TABLE ml_prediction_batches IS 'Tracks batch prediction runs for auditing and monitoring';
COMMENT ON FUNCTION get_latest_ml_prediction IS 'Returns the most recent ML prediction for a given tender';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

SELECT 'Migration 021: ML Predictions Tables - Completed Successfully' AS status;
