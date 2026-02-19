-- Migration 038: Adversarial Robustness Analysis
-- Stores per-tender adversarial robustness metrics for ML predictions
-- Part of Phase 3.3: Adversarial Robustness for Corruption Detection

CREATE TABLE IF NOT EXISTS adversarial_analysis (
    analysis_id SERIAL PRIMARY KEY,
    tender_id TEXT NOT NULL UNIQUE,
    model_name TEXT DEFAULT 'xgboost',
    robustness_score FLOAT,            -- 0-1, higher is more robust
    robustness_level TEXT,             -- 'robust', 'moderate', 'fragile'
    robustness_margin FLOAT,           -- L2 norm of minimum perturbation to flip
    vulnerable_features JSONB DEFAULT '[]',  -- top features that can flip prediction
    is_boundary_case BOOLEAN DEFAULT FALSE,  -- within 0.1 of decision boundary
    prediction FLOAT,                  -- model's corruption probability
    adversarial_resistance FLOAT,      -- 0-1, resistance to small perturbations
    recommendations JSONB DEFAULT '[]', -- actionable recommendations
    analyzed_at TIMESTAMP DEFAULT NOW()
);

-- Index for finding fragile predictions quickly
CREATE INDEX IF NOT EXISTS idx_adversarial_robustness
    ON adversarial_analysis(robustness_level);

-- Index for boundary cases (partial index for efficiency)
CREATE INDEX IF NOT EXISTS idx_adversarial_boundary
    ON adversarial_analysis(is_boundary_case) WHERE is_boundary_case = TRUE;

-- Index for lookup by tender_id (already covered by UNIQUE but explicit for clarity)
CREATE INDEX IF NOT EXISTS idx_adversarial_tender
    ON adversarial_analysis(tender_id);

-- Index for sorting by robustness score (for the fragile predictions endpoint)
CREATE INDEX IF NOT EXISTS idx_adversarial_score
    ON adversarial_analysis(robustness_score ASC);

-- Comment on table
COMMENT ON TABLE adversarial_analysis IS
    'Stores adversarial robustness analysis for ML corruption detection predictions. '
    'Each row represents how robust a particular prediction is against adversarial '
    'feature perturbation -- fragile predictions may need manual review.';
