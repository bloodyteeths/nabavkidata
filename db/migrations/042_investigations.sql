-- Migration 042: Investigation Case Management Tables
-- Date: 2026-02-19
-- Purpose: Create tables for managing corruption investigation cases,
--          tracking attached tenders/entities, collecting evidence,
--          and maintaining an activity audit trail.
--
-- Used by:
--   - ai/corruption/investigation/case_manager.py (CaseManager)
--   - ai/corruption/investigation/evidence_linker.py (EvidenceLinker)
--   - backend/api/corruption.py (Phase 4.2 investigation endpoints)

-- ============================================================================
-- STEP 1: Investigation Cases - Core case tracking table
-- ============================================================================

CREATE TABLE IF NOT EXISTS investigation_cases (
    case_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'review', 'closed', 'archived')),
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    assigned_to TEXT,
    created_by TEXT,
    total_risk_value NUMERIC(18,2) DEFAULT 0,
    tender_count INTEGER DEFAULT 0,
    entity_count INTEGER DEFAULT 0,
    evidence_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE investigation_cases IS
'Corruption investigation cases for tracking and managing investigations.
Each case groups related tenders, entities, and evidence for coordinated review.
Migration 042.';

-- ============================================================================
-- STEP 2: Case Tenders - Tenders attached to investigation cases
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_tenders (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES investigation_cases(case_id) ON DELETE CASCADE,
    tender_id TEXT NOT NULL,
    role TEXT DEFAULT 'suspect'
        CHECK (role IN ('suspect', 'reference', 'control')),
    notes TEXT,
    added_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(case_id, tender_id)
);

COMMENT ON TABLE case_tenders IS
'Tenders attached to investigation cases. Role indicates the tender''s purpose
in the investigation: suspect (under investigation), reference (for comparison),
or control (baseline). Migration 042.';

-- ============================================================================
-- STEP 3: Case Entities - Companies/institutions attached to cases
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_entities (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES investigation_cases(case_id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'company'
        CHECK (entity_type IN ('company', 'institution', 'person')),
    entity_name TEXT,
    role TEXT DEFAULT 'suspect'
        CHECK (role IN ('suspect', 'witness', 'victim', 'reference')),
    added_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(case_id, entity_id, entity_type)
);

COMMENT ON TABLE case_entities IS
'Entities (companies, institutions, persons) attached to investigation cases.
Role describes their involvement: suspect, witness, victim, or reference.
Migration 042.';

-- ============================================================================
-- STEP 4: Case Evidence - Evidence items collected for cases
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_evidence (
    evidence_id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES investigation_cases(case_id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL
        CHECK (evidence_type IN ('flag', 'anomaly', 'relationship', 'document', 'manual')),
    source_module TEXT,
    source_id TEXT,
    description TEXT NOT NULL,
    severity TEXT DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    metadata JSONB DEFAULT '{}',
    added_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE case_evidence IS
'Evidence items collected for investigation cases. Each item tracks its type,
source module (corruption, collusion, temporal, etc.), and severity.
Migration 042.';

-- ============================================================================
-- STEP 5: Case Notes - Analyst notes and observations
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_notes (
    note_id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES investigation_cases(case_id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE case_notes IS
'Analyst notes and observations on investigation cases.
Free-form text entries for documenting findings and reasoning.
Migration 042.';

-- ============================================================================
-- STEP 6: Case Activity Log - Audit trail of all actions
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_activity_log (
    log_id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES investigation_cases(case_id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    actor TEXT,
    old_value TEXT,
    new_value TEXT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE case_activity_log IS
'Audit trail of all actions taken on investigation cases.
Tracks status changes, tender/entity additions, evidence collection, etc.
Migration 042.';

-- ============================================================================
-- STEP 7: Indexes for efficient querying
-- ============================================================================

-- Investigation cases indexes
CREATE INDEX idx_cases_status ON investigation_cases(status);
CREATE INDEX idx_cases_priority ON investigation_cases(priority);
CREATE INDEX idx_cases_created ON investigation_cases(created_at DESC);
CREATE INDEX idx_cases_assigned ON investigation_cases(assigned_to)
    WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_cases_updated ON investigation_cases(updated_at DESC);

-- Case tenders indexes
CREATE INDEX idx_case_tenders_case ON case_tenders(case_id);
CREATE INDEX idx_case_tenders_tender ON case_tenders(tender_id);

-- Case entities indexes
CREATE INDEX idx_case_entities_case ON case_entities(case_id);
CREATE INDEX idx_case_entities_entity ON case_entities(entity_id, entity_type);

-- Case evidence indexes
CREATE INDEX idx_case_evidence_case ON case_evidence(case_id);
CREATE INDEX idx_case_evidence_type ON case_evidence(evidence_type);
CREATE INDEX idx_case_evidence_severity ON case_evidence(severity);
CREATE INDEX idx_case_evidence_metadata ON case_evidence USING GIN(metadata);

-- Case notes indexes
CREATE INDEX idx_case_notes_case ON case_notes(case_id);

-- Case activity log indexes
CREATE INDEX idx_case_activity_case ON case_activity_log(case_id);
CREATE INDEX idx_case_activity_time ON case_activity_log(created_at DESC);
CREATE INDEX idx_case_activity_action ON case_activity_log(action);

-- ============================================================================
-- STEP 8: Verify migration
-- ============================================================================

SELECT 'Migration 042: Investigation Case Management - Completed Successfully' AS status;
