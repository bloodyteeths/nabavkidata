-- Migration: Specification Analysis for Corruption Detection (Phase 2.1)
-- Date: 2026-02-19
-- Purpose: Store specification rigging analysis results per tender document.
--          Captures brand-name detections, restrictive qualifications,
--          text complexity, and computed rigging probability.

-- ============================================================================
-- SPECIFICATION ANALYSIS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS specification_analysis (
    analysis_id SERIAL PRIMARY KEY,
    tender_id TEXT NOT NULL,
    doc_id UUID REFERENCES documents(doc_id) ON DELETE SET NULL,
    brand_names JSONB DEFAULT '[]',
    brand_exclusivity_score FLOAT DEFAULT 0,
    qualification_requirements JSONB DEFAULT '[]',
    qualification_restrictiveness FLOAT DEFAULT 0,
    complexity_score FLOAT,
    vocabulary_richness FLOAT,
    rigging_probability FLOAT,
    risk_factors JSONB DEFAULT '[]',
    analyzed_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_spec_analysis_tender ON specification_analysis(tender_id);
CREATE INDEX idx_spec_analysis_rigging ON specification_analysis(rigging_probability DESC);
CREATE INDEX idx_spec_analysis_doc ON specification_analysis(doc_id);
CREATE INDEX idx_spec_analysis_date ON specification_analysis(analyzed_at DESC);

-- GIN index for JSONB brand_names searches
CREATE INDEX idx_spec_analysis_brands ON specification_analysis USING GIN(brand_names);

-- Partial index for high-risk results (rigging_probability > 0.5)
CREATE INDEX idx_spec_analysis_high_risk ON specification_analysis(rigging_probability DESC)
    WHERE rigging_probability > 0.5;

-- Composite index for tender + date lookups
CREATE UNIQUE INDEX idx_spec_analysis_tender_doc ON specification_analysis(tender_id, doc_id);
