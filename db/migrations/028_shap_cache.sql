-- Migration 028: SHAP Value Cache Table
-- Stores pre-computed SHAP values for per-tender ML explanations.
-- Used by the /api/corruption/explain/{tender_id} endpoint.

CREATE TABLE IF NOT EXISTS ml_shap_cache (
    tender_id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    shap_values JSONB NOT NULL,
    base_value FLOAT,
    prediction FLOAT,
    computed_at TIMESTAMP DEFAULT NOW()
);

-- Index for cache invalidation queries (find stale entries)
CREATE INDEX IF NOT EXISTS idx_shap_cache_computed ON ml_shap_cache(computed_at);

-- Index for model-based lookups (e.g. when retraining a specific model)
CREATE INDEX IF NOT EXISTS idx_shap_cache_model ON ml_shap_cache(model_name);

COMMENT ON TABLE ml_shap_cache IS 'Caches SHAP values per tender for fast explainability lookups';
COMMENT ON COLUMN ml_shap_cache.shap_values IS 'JSONB dict of feature_name -> SHAP value (float)';
COMMENT ON COLUMN ml_shap_cache.base_value IS 'Expected model output (base rate before feature contributions)';
COMMENT ON COLUMN ml_shap_cache.prediction IS 'Model predicted probability for positive class';
