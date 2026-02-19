-- ============================================================================
-- Migration 034: Specification Similarity Analysis Tables
-- Date: 2026-02-19
-- ============================================================================
-- Creates tables for storing pre-computed specification similarity pairs
-- and institution specification reuse statistics.
-- These tables are populated by the batch_similarity.py cron job and
-- queried by the /api/corruption/spec-similarity/* endpoints.
-- ============================================================================

BEGIN;

-- ============================================================================
-- Specification similarity pairs (pre-computed for dashboard)
-- ============================================================================
CREATE TABLE IF NOT EXISTS spec_similarity_pairs (
    pair_id SERIAL PRIMARY KEY,
    tender_id_1 TEXT NOT NULL,
    tender_id_2 TEXT NOT NULL,
    similarity_score FLOAT NOT NULL,
    same_institution BOOLEAN DEFAULT FALSE,
    same_winner BOOLEAN DEFAULT FALSE,
    cross_institution BOOLEAN DEFAULT FALSE,
    copied_fraction FLOAT,
    detection_type TEXT,  -- 'reuse', 'clone', 'template'
    detected_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tender_id_1, tender_id_2)
);

-- Index for querying by similarity score (high scores first)
CREATE INDEX IF NOT EXISTS idx_spec_sim_score
    ON spec_similarity_pairs(similarity_score DESC);

-- Index for cross-institution clone queries (strongest rigging signal)
CREATE INDEX IF NOT EXISTS idx_spec_sim_cross
    ON spec_similarity_pairs(cross_institution)
    WHERE cross_institution = TRUE;

-- Indexes for looking up pairs by tender ID
CREATE INDEX IF NOT EXISTS idx_spec_sim_tender1
    ON spec_similarity_pairs(tender_id_1);
CREATE INDEX IF NOT EXISTS idx_spec_sim_tender2
    ON spec_similarity_pairs(tender_id_2);

-- Index for detection type filtering
CREATE INDEX IF NOT EXISTS idx_spec_sim_type
    ON spec_similarity_pairs(detection_type);

-- ============================================================================
-- Institution specification reuse statistics
-- ============================================================================
CREATE TABLE IF NOT EXISTS institution_spec_reuse (
    institution TEXT PRIMARY KEY,
    total_specs INTEGER DEFAULT 0,
    unique_specs INTEGER DEFAULT 0,
    reuse_rate FLOAT DEFAULT 0,
    top_winner TEXT,
    top_winner_pct FLOAT DEFAULT 0,
    computed_at TIMESTAMP DEFAULT NOW()
);

-- Index for finding institutions with highest reuse rates
CREATE INDEX IF NOT EXISTS idx_inst_reuse_rate
    ON institution_spec_reuse(reuse_rate DESC);

COMMIT;
