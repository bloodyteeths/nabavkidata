-- Migration: 029_active_learning.sql
-- Date: 2026-02-19
-- Purpose: Active learning schema for CRI weight calibration
--
-- Adds:
--   1. corruption_reviews - Enhanced analyst review table for active learning
--   2. cri_weight_history - Tracks CRI weight changes over time
--   3. active_learning_queue - Prioritized queue of tenders for human review

-- ============================================================================
-- STEP 1: corruption_reviews - Enhanced reviews table
-- ============================================================================

CREATE TABLE IF NOT EXISTS corruption_reviews (
    review_id SERIAL PRIMARY KEY,
    tender_id TEXT NOT NULL,
    flag_id INTEGER,
    analyst_verdict TEXT NOT NULL CHECK (analyst_verdict IN (
        'confirmed_fraud', 'likely_fraud', 'uncertain', 'false_positive', 'not_reviewed'
    )),
    confidence INTEGER CHECK (confidence BETWEEN 1 AND 5),
    evidence_notes TEXT,
    reviewer_id TEXT,
    reviewed_at TIMESTAMP DEFAULT NOW(),
    review_source TEXT DEFAULT 'manual' CHECK (review_source IN (
        'manual', 'active_learning', 'bulk_review'
    ))
);

CREATE INDEX IF NOT EXISTS idx_reviews_tender ON corruption_reviews(tender_id);
CREATE INDEX IF NOT EXISTS idx_reviews_verdict ON corruption_reviews(analyst_verdict);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON corruption_reviews(reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON corruption_reviews(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_source ON corruption_reviews(review_source);

COMMENT ON TABLE corruption_reviews IS
'Enhanced analyst review table for active learning weight calibration.
Each row is one analyst verdict on a tender (or specific flag).
Used by weight_calibration.py to retrain CRI weights.
Migration 029.';

-- ============================================================================
-- STEP 2: cri_weight_history - Weight change tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS cri_weight_history (
    history_id SERIAL PRIMARY KEY,
    weights JSONB NOT NULL,
    num_reviews_used INTEGER,
    avg_agreement_rate FLOAT,
    computed_at TIMESTAMP DEFAULT NOW(),
    applied BOOLEAN DEFAULT FALSE,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_cwh_applied ON cri_weight_history(applied) WHERE applied = TRUE;
CREATE INDEX IF NOT EXISTS idx_cwh_computed ON cri_weight_history(computed_at DESC);

COMMENT ON TABLE cri_weight_history IS
'Tracks CRI weight calibration history. Each row stores a full weight dictionary
computed from accumulated analyst reviews. Only one row should have applied=TRUE
at a time (the currently active weights). Migration 029.';

-- ============================================================================
-- STEP 3: active_learning_queue - Prioritized review queue
-- ============================================================================

CREATE TABLE IF NOT EXISTS active_learning_queue (
    queue_id SERIAL PRIMARY KEY,
    tender_id TEXT NOT NULL UNIQUE,
    priority_score FLOAT NOT NULL,
    selection_reason TEXT NOT NULL CHECK (selection_reason IN (
        'boundary', 'disagreement', 'novel'
    )),
    selected_at TIMESTAMP DEFAULT NOW(),
    reviewed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_alq_priority
    ON active_learning_queue(priority_score DESC) WHERE NOT reviewed;
CREATE INDEX IF NOT EXISTS idx_alq_tender
    ON active_learning_queue(tender_id);
CREATE INDEX IF NOT EXISTS idx_alq_reviewed
    ON active_learning_queue(reviewed);

COMMENT ON TABLE active_learning_queue IS
'Active learning queue of tenders prioritized for human review.
Selection strategies: boundary (near CRI threshold), disagreement (rule vs ML mismatch),
novel (unusual flag combinations). Refreshed weekly by cron. Migration 029.';

-- ============================================================================
-- DONE
-- ============================================================================

SELECT 'Migration 029: Active Learning Schema - Completed Successfully' AS status;
