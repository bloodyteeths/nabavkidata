-- Migration 024: Add reviewed_at timestamp to corruption_flags
-- Tracks when flags were reviewed for audit trail

ALTER TABLE corruption_flags ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_corruption_flags_reviewed_at ON corruption_flags(reviewed_at DESC);
