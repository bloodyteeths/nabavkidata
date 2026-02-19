-- Migration 039: AutoML Pipeline & Model Registry
-- Adds tables for model versioning, optimization tracking, and data drift monitoring
-- Part of Phase 3.4: Automated hyperparameter optimization and model management

-- ============================================================================
-- Model Registry: Track model versions, hyperparameters, and performance
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_registry (
    version_id TEXT PRIMARY KEY,           -- uuid-based version identifier
    model_name TEXT NOT NULL,              -- e.g. 'xgboost', 'random_forest'
    model_path TEXT NOT NULL,              -- filesystem path to the joblib file
    hyperparameters JSONB NOT NULL,        -- full hyperparameter dict
    metrics JSONB NOT NULL,               -- {auc_roc, precision, recall, f1, accuracy}
    training_data_hash TEXT,              -- hash of training data for reproducibility
    training_samples INTEGER,             -- number of training samples used
    training_duration_seconds FLOAT,      -- wall-clock time for training
    is_active BOOLEAN DEFAULT FALSE,      -- only one active model per model_name
    created_at TIMESTAMP DEFAULT NOW(),
    notes TEXT                            -- human-readable notes about this version
);

CREATE INDEX IF NOT EXISTS idx_model_registry_name
    ON model_registry(model_name);

-- Partial index: fast lookup of the active model per name
CREATE UNIQUE INDEX IF NOT EXISTS idx_model_registry_active
    ON model_registry(model_name, is_active) WHERE is_active = TRUE;

-- ============================================================================
-- Optimization Runs: Track Optuna hyperparameter search sessions
-- ============================================================================
CREATE TABLE IF NOT EXISTS optimization_runs (
    run_id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,              -- which model type was optimized
    n_trials INTEGER,                     -- number of Optuna trials executed
    best_params JSONB,                    -- best hyperparameters found
    best_score FLOAT,                     -- best objective score (AUC-ROC)
    all_scores JSONB,                     -- [{trial, params, score}, ...]
    duration_seconds FLOAT,               -- total optimization wall-clock time
    triggered_by TEXT DEFAULT 'manual',   -- 'manual', 'drift', 'schedule'
    completed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_optimization_runs_model
    ON optimization_runs(model_name);

CREATE INDEX IF NOT EXISTS idx_optimization_runs_completed
    ON optimization_runs(completed_at DESC);

-- ============================================================================
-- Data Drift Log: Track feature distribution changes over time
-- ============================================================================
CREATE TABLE IF NOT EXISTS data_drift_log (
    drift_id SERIAL PRIMARY KEY,
    feature_psi JSONB NOT NULL,           -- {feature_name: psi_value}
    overall_drift FLOAT,                  -- mean PSI across all features
    drift_level TEXT,                     -- 'none', 'moderate', 'significant'
    should_retrain BOOLEAN DEFAULT FALSE, -- whether retraining is recommended
    checked_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_drift_log_checked
    ON data_drift_log(checked_at DESC);
