-- Migration 043: Counterfactual Explanations Cache
-- Purpose: Store DiCE-style counterfactual explanations for tender risk scores
-- Date: 2026-02-19
-- Phase: 4.3 - Computational Counterfactual Explanations

CREATE TABLE IF NOT EXISTS counterfactual_explanations (
    id SERIAL PRIMARY KEY,
    tender_id TEXT NOT NULL,
    original_score FLOAT NOT NULL,
    counterfactual_features JSONB NOT NULL,  -- {feature: {from, to, description}}
    counterfactual_score FLOAT NOT NULL,
    distance FLOAT NOT NULL,
    feasibility_score FLOAT NOT NULL,
    num_changes INTEGER NOT NULL,
    generated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_counterfactuals_tender ON counterfactual_explanations(tender_id);
CREATE INDEX IF NOT EXISTS idx_counterfactuals_score ON counterfactual_explanations(original_score DESC);

COMMENT ON TABLE counterfactual_explanations IS 'Cached counterfactual explanations for tender risk scores (DiCE-style). Phase 4.3.';
COMMENT ON COLUMN counterfactual_explanations.tender_id IS 'Reference to the tender this counterfactual explains';
COMMENT ON COLUMN counterfactual_explanations.original_score IS 'The original CRI risk score (0-100) at generation time';
COMMENT ON COLUMN counterfactual_explanations.counterfactual_features IS 'JSON dict of changed features: {feature_name: {from, to, description}}';
COMMENT ON COLUMN counterfactual_explanations.counterfactual_score IS 'Predicted risk score after applying counterfactual changes';
COMMENT ON COLUMN counterfactual_explanations.distance IS 'Normalized L1 distance from original feature vector (lower = fewer changes)';
COMMENT ON COLUMN counterfactual_explanations.feasibility_score IS 'How feasible the proposed changes are (0=infeasible, 1=easy)';
COMMENT ON COLUMN counterfactual_explanations.num_changes IS 'Number of features changed in this counterfactual';
COMMENT ON COLUMN counterfactual_explanations.generated_at IS 'Timestamp when this counterfactual was generated';
