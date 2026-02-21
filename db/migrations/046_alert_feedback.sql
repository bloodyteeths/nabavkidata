-- Migration 046: Add user feedback columns to alert_matches
-- Allows users to rate match relevance (thumbs up/down)

ALTER TABLE alert_matches ADD COLUMN IF NOT EXISTS user_feedback VARCHAR(10)
  CHECK (user_feedback IN ('up', 'down'));
ALTER TABLE alert_matches ADD COLUMN IF NOT EXISTS feedback_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_alert_matches_feedback
  ON alert_matches(user_feedback) WHERE user_feedback IS NOT NULL;
