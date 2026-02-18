-- Migration 028: Add confidence interval columns to tender_risk_scores
-- Date: 2026-02-19
-- Purpose: Store CRI bootstrap confidence intervals and uncertainty metadata
--          alongside the existing risk_score in tender_risk_scores.
--
-- New columns:
--   ci_lower          FLOAT   - Lower bound of 90% bootstrap CI (0-100 scale)
--   ci_upper          FLOAT   - Upper bound of 90% bootstrap CI (0-100 scale)
--   uncertainty       TEXT    - Classification: 'low', 'medium', 'high'
--   data_completeness FLOAT   - Fraction of 112 ML features with real values (0.0-1.0)
--
-- These columns are nullable so existing rows remain valid.
-- The API computes CI on-the-fly for the analysis endpoint, but these columns
-- allow batch jobs and the ML pipeline to persist pre-computed intervals.

-- ============================================================================
-- STEP 1: Add columns to tender_risk_scores
-- ============================================================================

ALTER TABLE tender_risk_scores
    ADD COLUMN IF NOT EXISTS ci_lower FLOAT,
    ADD COLUMN IF NOT EXISTS ci_upper FLOAT,
    ADD COLUMN IF NOT EXISTS uncertainty TEXT DEFAULT 'medium',
    ADD COLUMN IF NOT EXISTS data_completeness FLOAT;

-- Add CHECK constraint on uncertainty to enforce valid values
-- (use DO block to avoid error if constraint already exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'tender_risk_scores_uncertainty_check'
    ) THEN
        ALTER TABLE tender_risk_scores
            ADD CONSTRAINT tender_risk_scores_uncertainty_check
            CHECK (uncertainty IN ('low', 'medium', 'high'));
    END IF;
END $$;

-- Add CHECK constraint on data_completeness range
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'tender_risk_scores_data_completeness_check'
    ) THEN
        ALTER TABLE tender_risk_scores
            ADD CONSTRAINT tender_risk_scores_data_completeness_check
            CHECK (data_completeness IS NULL OR (data_completeness >= 0.0 AND data_completeness <= 1.0));
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Add index for uncertainty filtering
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_tender_risk_scores_uncertainty
    ON tender_risk_scores(uncertainty);

CREATE INDEX IF NOT EXISTS idx_tender_risk_scores_data_completeness
    ON tender_risk_scores(data_completeness)
    WHERE data_completeness IS NOT NULL;

-- ============================================================================
-- STEP 3: Add column comments
-- ============================================================================

COMMENT ON COLUMN tender_risk_scores.ci_lower IS
'Lower bound of 90% bootstrap confidence interval for the CRI score (0-100 scale)';

COMMENT ON COLUMN tender_risk_scores.ci_upper IS
'Upper bound of 90% bootstrap confidence interval for the CRI score (0-100 scale)';

COMMENT ON COLUMN tender_risk_scores.uncertainty IS
'Uncertainty classification: low (narrow CI + good data), medium, high (wide CI or sparse data)';

COMMENT ON COLUMN tender_risk_scores.data_completeness IS
'Fraction of 112 ML features with real (non-default) values. 0.0 = no data, 1.0 = fully populated';

-- ============================================================================
-- DONE
-- ============================================================================

SELECT 'Migration 028: Confidence Intervals - Completed Successfully' AS status;
