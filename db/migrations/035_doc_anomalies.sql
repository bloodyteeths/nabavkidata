-- Migration 035: Document Anomaly Detection Tables
-- Date: 2026-02-19
-- Purpose: Add tables for tracking document anomalies detected by the
--          DocumentAnomalyDetector (ai/corruption/nlp/doc_anomaly.py).
--          Stores individual anomalies per tender/document and aggregate
--          completeness statistics per tender.

BEGIN;

-- ============================================================================
-- DOCUMENT ANOMALIES - Individual anomalies detected in tender documents
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_anomalies (
    anomaly_id SERIAL PRIMARY KEY,
    tender_id TEXT NOT NULL,
    doc_id UUID REFERENCES documents(doc_id) ON DELETE SET NULL,
    anomaly_type TEXT NOT NULL,
        -- 'missing_doc', 'timing_coordination', 'size_anomaly',
        -- 'metadata_tampering', 'empty_file'
    severity TEXT NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT NOT NULL,
    evidence JSONB DEFAULT '{}',
    risk_contribution FLOAT DEFAULT 0,
    detected_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE document_anomalies IS
    'Individual document anomalies detected by the DocumentAnomalyDetector. '
    'Each row represents one anomaly (missing doc, timing issue, size issue, etc.) '
    'for a specific tender or document.';

COMMENT ON COLUMN document_anomalies.anomaly_type IS
    'Type of anomaly: missing_doc, timing_coordination, size_anomaly, metadata_tampering, empty_file';
COMMENT ON COLUMN document_anomalies.severity IS
    'Severity level: low, medium, high, critical';
COMMENT ON COLUMN document_anomalies.evidence IS
    'JSONB with structured evidence data (file names, sizes, dates, etc.)';
COMMENT ON COLUMN document_anomalies.risk_contribution IS
    'Contribution of this anomaly to the overall risk score (0-100)';

-- Indexes for document_anomalies
CREATE INDEX IF NOT EXISTS idx_doc_anomaly_tender
    ON document_anomalies(tender_id);
CREATE INDEX IF NOT EXISTS idx_doc_anomaly_type
    ON document_anomalies(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_doc_anomaly_severity
    ON document_anomalies(severity);
CREATE INDEX IF NOT EXISTS idx_doc_anomaly_detected
    ON document_anomalies(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_doc_anomaly_doc_id
    ON document_anomalies(doc_id) WHERE doc_id IS NOT NULL;

-- ============================================================================
-- TENDER DOC COMPLETENESS - Aggregate document health per tender
-- ============================================================================

CREATE TABLE IF NOT EXISTS tender_doc_completeness (
    tender_id TEXT PRIMARY KEY,
    total_documents INTEGER DEFAULT 0,
    expected_documents INTEGER DEFAULT 0,
    completeness_score FLOAT DEFAULT 0,
    anomaly_count INTEGER DEFAULT 0,
    timing_anomaly_score FLOAT DEFAULT 0,
    overall_risk_contribution FLOAT DEFAULT 0,
    computed_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE tender_doc_completeness IS
    'Aggregate document completeness and anomaly statistics per tender. '
    'Populated by the batch_doc_anomaly.py cron job.';

COMMENT ON COLUMN tender_doc_completeness.completeness_score IS
    'Score from 0 to 1 indicating what fraction of required documents are present';
COMMENT ON COLUMN tender_doc_completeness.timing_anomaly_score IS
    'Score from 0 to 1 indicating severity of timing anomalies';
COMMENT ON COLUMN tender_doc_completeness.overall_risk_contribution IS
    'Combined risk contribution from all document anomalies (0-100)';

-- Index for querying worst completeness
CREATE INDEX IF NOT EXISTS idx_doc_completeness_risk
    ON tender_doc_completeness(overall_risk_contribution DESC);
CREATE INDEX IF NOT EXISTS idx_doc_completeness_score
    ON tender_doc_completeness(completeness_score ASC);
CREATE INDEX IF NOT EXISTS idx_doc_completeness_computed
    ON tender_doc_completeness(computed_at DESC);

COMMIT;

-- ============================================================================
-- VERIFY MIGRATION
-- ============================================================================

SELECT 'Migration 035: Document Anomaly Detection Tables - Completed' AS status;
