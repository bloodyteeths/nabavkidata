-- Migration 037: Causal Analysis Tables
-- Stores estimated causal effects of procurement design choices on corruption probability
-- and actionable policy recommendations derived from those estimates.
--
-- Part of Phase 3.2: Causal Inference for Procurement Policy Recommendations

BEGIN;

-- =============================================================================
-- Causal Estimates Table
-- Stores the Average Treatment Effect (ATE) of procurement design choices
-- on corruption probability, computed via propensity score matching.
-- =============================================================================
CREATE TABLE IF NOT EXISTS causal_estimates (
    estimate_id SERIAL PRIMARY KEY,
    treatment_name TEXT NOT NULL,
    treatment_description TEXT,
    ate FLOAT NOT NULL,                -- Average Treatment Effect
    ci_lower FLOAT,                    -- 95% CI lower bound
    ci_upper FLOAT,                    -- 95% CI upper bound
    p_value FLOAT,                     -- Permutation test p-value
    n_treated INTEGER,                 -- Number of treated units
    n_control INTEGER,                 -- Number of control units
    n_matched INTEGER,                 -- Number of matched pairs
    interpretation TEXT,               -- Human-readable interpretation
    recommendation TEXT,               -- Actionable recommendation
    method TEXT DEFAULT 'propensity_score_matching',
    confounders_used TEXT[],           -- List of confounders controlled for
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(treatment_name)
);

COMMENT ON TABLE causal_estimates IS 'Stores Average Treatment Effect estimates from propensity score matching analysis of procurement design choices';
COMMENT ON COLUMN causal_estimates.ate IS 'Average Treatment Effect: change in corruption probability due to treatment';
COMMENT ON COLUMN causal_estimates.ci_lower IS '95% bootstrap confidence interval lower bound';
COMMENT ON COLUMN causal_estimates.ci_upper IS '95% bootstrap confidence interval upper bound';
COMMENT ON COLUMN causal_estimates.n_matched IS 'Number of matched treated-control pairs after propensity score matching';

-- =============================================================================
-- Policy Recommendations Table
-- Stores actionable recommendations generated from causal estimates,
-- optionally scoped to a specific institution.
-- =============================================================================
CREATE TABLE IF NOT EXISTS policy_recommendations (
    rec_id SERIAL PRIMARY KEY,
    institution TEXT,                   -- NULL for global recommendations
    recommendation TEXT NOT NULL,
    estimated_impact FLOAT,            -- Estimated percentage change in corruption probability
    confidence TEXT,                    -- 'high', 'medium', 'low'
    evidence JSONB,                    -- Supporting data (ATE, sample sizes, etc.)
    treatment_name TEXT REFERENCES causal_estimates(treatment_name) ON DELETE CASCADE,
    generated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policy_rec_institution ON policy_recommendations(institution);
CREATE INDEX IF NOT EXISTS idx_policy_rec_treatment ON policy_recommendations(treatment_name);
CREATE INDEX IF NOT EXISTS idx_policy_rec_confidence ON policy_recommendations(confidence);

COMMENT ON TABLE policy_recommendations IS 'Actionable policy recommendations derived from causal inference analysis, optionally scoped to institutions';
COMMENT ON COLUMN policy_recommendations.estimated_impact IS 'Estimated percentage point change in corruption probability if recommendation is adopted';

COMMIT;
