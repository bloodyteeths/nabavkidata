-- Migration: Add Saved Searches Support to Alerts Table
-- Date: 2025-12-21
-- Purpose: Extend alerts table to support flexible saved search filters

-- ============================================================================
-- ALTER ALERTS TABLE
-- ============================================================================

-- Add columns for saved searches if they don't exist
DO $$
BEGIN
    -- Add name column (rename alert_name if it exists)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'alerts' AND column_name = 'name') THEN
        ALTER TABLE alerts ADD COLUMN name VARCHAR(255);
        -- Copy data from alert_name if it exists
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'alerts' AND column_name = 'alert_name') THEN
            UPDATE alerts SET name = alert_name WHERE alert_name IS NOT NULL;
        END IF;
    END IF;

    -- Add filters JSONB column for flexible search criteria
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'alerts' AND column_name = 'filters') THEN
        ALTER TABLE alerts ADD COLUMN filters JSONB DEFAULT '{}'::jsonb;
    END IF;

    -- Add frequency column for notification frequency
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'alerts' AND column_name = 'frequency') THEN
        ALTER TABLE alerts ADD COLUMN frequency VARCHAR(20) DEFAULT 'daily';
    END IF;

    -- Add last_triggered column to track when alert was last executed
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'alerts' AND column_name = 'last_triggered') THEN
        ALTER TABLE alerts ADD COLUMN last_triggered TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- ============================================================================
-- CREATE INDEX ON FILTERS
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_alerts_filters ON alerts USING GIN(filters);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN alerts.name IS 'User-friendly name for the saved search';
COMMENT ON COLUMN alerts.filters IS 'JSONB object containing flexible search criteria (query, category, cpv_code, etc.)';
COMMENT ON COLUMN alerts.frequency IS 'Notification frequency: instant, daily, weekly';
COMMENT ON COLUMN alerts.last_triggered IS 'Timestamp when this alert was last executed/checked';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

SELECT 'Migration 015: Saved Searches Support - Completed Successfully' AS status;
