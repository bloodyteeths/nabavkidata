-- Migration 040: Conformal Prediction Calibration Tables
-- Purpose: Store conformal prediction parameters, calibration checks, and calibrated predictions
-- Date: 2026-02-19

-- ============================================================================
-- CONFORMAL CALIBRATION - Stores fitted conformal predictor parameters
-- ============================================================================

CREATE TABLE IF NOT EXISTS conformal_calibration (
    calibration_id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    alpha FLOAT NOT NULL,  -- miscoverage rate (e.g., 0.10 = 90% coverage)
    quantile_threshold FLOAT,  -- nonconformity score quantile
    platt_a FLOAT,  -- Platt scaling sigmoid slope parameter
    platt_b FLOAT,  -- Platt scaling sigmoid intercept parameter
    calibration_set_size INTEGER,
    ece FLOAT,  -- Expected Calibration Error at fit time
    mce FLOAT,  -- Maximum Calibration Error at fit time
    is_well_calibrated BOOLEAN DEFAULT FALSE,
    fitted_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(model_name, alpha)
);

COMMENT ON TABLE conformal_calibration IS
    'Stores fitted conformal prediction parameters for risk score calibration';
COMMENT ON COLUMN conformal_calibration.alpha IS
    'Miscoverage rate: 0.10 means 90% coverage guarantee';
COMMENT ON COLUMN conformal_calibration.quantile_threshold IS
    'Nonconformity score quantile used for prediction set construction';
COMMENT ON COLUMN conformal_calibration.platt_a IS
    'Platt scaling sigmoid slope: P(y=1|f) = sigmoid(a*f + b)';
COMMENT ON COLUMN conformal_calibration.platt_b IS
    'Platt scaling sigmoid intercept: P(y=1|f) = sigmoid(a*f + b)';

-- ============================================================================
-- CALIBRATION CHECKS - Tracks calibration quality over time
-- ============================================================================

CREATE TABLE IF NOT EXISTS calibration_checks (
    check_id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    ece FLOAT,  -- Expected Calibration Error
    mce FLOAT,  -- Maximum Calibration Error
    coverage_actual FLOAT,  -- Actual empirical coverage
    coverage_target FLOAT,  -- Target coverage (1 - alpha)
    n_samples INTEGER,
    drift_detected BOOLEAN DEFAULT FALSE,
    checked_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cal_checks_date
    ON calibration_checks(checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_cal_checks_model
    ON calibration_checks(model_name, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_cal_checks_drift
    ON calibration_checks(drift_detected, checked_at DESC);

COMMENT ON TABLE calibration_checks IS
    'Tracks calibration quality metrics over time for drift detection';
COMMENT ON COLUMN calibration_checks.ece IS
    'Expected Calibration Error: weighted average bin-level |accuracy - confidence|';
COMMENT ON COLUMN calibration_checks.drift_detected IS
    'True when ECE exceeds the acceptable threshold, signaling need for recalibration';

-- ============================================================================
-- CALIBRATED PREDICTIONS - Stores calibrated risk scores per tender
-- ============================================================================

CREATE TABLE IF NOT EXISTS calibrated_predictions (
    tender_id TEXT PRIMARY KEY,
    raw_score FLOAT,  -- Original uncalibrated model output (0-1)
    calibrated_probability FLOAT,  -- Platt-scaled calibrated probability (0-1)
    prediction_lower FLOAT,  -- Lower bound of conformal prediction set
    prediction_upper FLOAT,  -- Upper bound of conformal prediction set
    set_width FLOAT,  -- Width of prediction set (upper - lower)
    model_name TEXT,
    calibrated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cal_pred_prob
    ON calibrated_predictions(calibrated_probability DESC);
CREATE INDEX IF NOT EXISTS idx_cal_pred_model
    ON calibrated_predictions(model_name);
CREATE INDEX IF NOT EXISTS idx_cal_pred_date
    ON calibrated_predictions(calibrated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cal_pred_width
    ON calibrated_predictions(set_width DESC);

COMMENT ON TABLE calibrated_predictions IS
    'Stores calibrated risk predictions with conformal prediction intervals per tender';
COMMENT ON COLUMN calibrated_predictions.raw_score IS
    'Original uncalibrated model probability output in [0, 1]';
COMMENT ON COLUMN calibrated_predictions.calibrated_probability IS
    'Platt-scaled probability: calibrated_prob=0.7 means 70% of similar tenders are flagged';
COMMENT ON COLUMN calibrated_predictions.prediction_lower IS
    'Lower bound of conformal prediction interval with coverage guarantee';
COMMENT ON COLUMN calibrated_predictions.prediction_upper IS
    'Upper bound of conformal prediction interval with coverage guarantee';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

SELECT 'Migration 040: Conformal Prediction Calibration Tables - Completed Successfully' AS status;
