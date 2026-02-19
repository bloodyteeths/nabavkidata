-- Migration 033: Named Entity Recognition - Entity Mentions
-- Date: 2026-02-19
-- Purpose: Store extracted named entities (people, organizations, monetary amounts,
--          dates, legal references, tax IDs) from tender documents.
--          Supports conflict-of-interest detection by cross-referencing person
--          mentions across buyer and supplier documents.

-- ============================================================================
-- ENTITY MENTIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_mentions (
    mention_id SERIAL PRIMARY KEY,
    tender_id TEXT NOT NULL,
    doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
    entity_text TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- PERSON, ORG, MONEY, DATE, GPE, TAX_ID, LEGAL_REF, IBAN
    normalized_text TEXT,       -- after resolution/normalization
    start_offset INTEGER,
    end_offset INTEGER,
    confidence FLOAT DEFAULT 1.0,
    extraction_method TEXT DEFAULT 'regex',  -- 'regex' or 'llm'
    context TEXT,              -- surrounding text (50 chars each side)
    extracted_at TIMESTAMP DEFAULT NOW()
);

-- Ensure entity_type is valid
ALTER TABLE entity_mentions
    ADD CONSTRAINT chk_entity_type
    CHECK (entity_type IN ('PERSON', 'ORG', 'MONEY', 'DATE', 'GPE', 'TAX_ID', 'LEGAL_REF', 'IBAN'));

-- Ensure extraction_method is valid
ALTER TABLE entity_mentions
    ADD CONSTRAINT chk_extraction_method
    CHECK (extraction_method IN ('regex', 'llm'));

COMMENT ON TABLE entity_mentions IS 'Named entities extracted from tender documents via regex and Gemini LLM';
COMMENT ON COLUMN entity_mentions.entity_type IS 'PERSON=individual names, ORG=organizations, MONEY=monetary amounts, DATE=dates, GPE=geographic entities, TAX_ID=EMBS/EDB identifiers, LEGAL_REF=law references, IBAN=bank accounts';
COMMENT ON COLUMN entity_mentions.normalized_text IS 'Normalized entity text after deduplication, transliteration, and suffix removal';
COMMENT ON COLUMN entity_mentions.context IS 'Surrounding text snippet (up to 50 chars each side) for human review';

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX idx_entity_tender ON entity_mentions(tender_id);
CREATE INDEX idx_entity_doc ON entity_mentions(doc_id);
CREATE INDEX idx_entity_type ON entity_mentions(entity_type);
CREATE INDEX idx_entity_normalized ON entity_mentions(normalized_text);
CREATE INDEX idx_entity_method ON entity_mentions(extraction_method);
CREATE INDEX idx_entity_text_gin ON entity_mentions USING gin(to_tsvector('simple', entity_text));
CREATE INDEX idx_entity_tender_type ON entity_mentions(tender_id, entity_type);

-- Composite index for conflict detection queries
CREATE INDEX idx_entity_person_normalized ON entity_mentions(normalized_text, entity_type)
    WHERE entity_type = 'PERSON';

-- ============================================================================
-- NER PROCESSING STATUS TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS ner_processing_log (
    log_id SERIAL PRIMARY KEY,
    doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
    tender_id TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT NOW(),
    extraction_method TEXT DEFAULT 'regex',  -- 'regex', 'llm', 'both'
    entity_count INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    error TEXT,
    UNIQUE(doc_id, extraction_method)
);

CREATE INDEX idx_ner_log_doc ON ner_processing_log(doc_id);
CREATE INDEX idx_ner_log_tender ON ner_processing_log(tender_id);

COMMENT ON TABLE ner_processing_log IS 'Tracks which documents have been processed by NER to avoid reprocessing';

-- ============================================================================
-- CONFLICT OF INTEREST DETECTION VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_potential_conflicts AS
WITH person_mentions AS (
    -- Get all PERSON entity mentions with their tender context
    SELECT
        em.normalized_text AS person_name,
        em.tender_id,
        t.procuring_entity,
        t.winner,
        em.doc_id,
        em.confidence,
        em.extraction_method
    FROM entity_mentions em
    JOIN tenders t ON em.tender_id = t.tender_id
    WHERE em.entity_type = 'PERSON'
      AND em.normalized_text IS NOT NULL
      AND em.normalized_text != ''
),
-- Find persons who appear in tenders with different procuring entities
cross_institution AS (
    SELECT
        pm1.person_name,
        pm1.procuring_entity AS institution,
        pm2.winner AS company,
        ARRAY_AGG(DISTINCT pm1.tender_id) AS institution_tenders,
        ARRAY_AGG(DISTINCT pm2.tender_id) AS company_tenders,
        COUNT(DISTINCT pm1.tender_id) AS institution_mention_count,
        COUNT(DISTINCT pm2.tender_id) AS company_mention_count,
        AVG(pm1.confidence) AS avg_confidence
    FROM person_mentions pm1
    JOIN person_mentions pm2
        ON pm1.person_name = pm2.person_name
        AND pm1.tender_id != pm2.tender_id
    WHERE pm1.procuring_entity IS NOT NULL
      AND pm2.winner IS NOT NULL
      AND pm1.procuring_entity != pm2.winner
    GROUP BY pm1.person_name, pm1.procuring_entity, pm2.winner
    HAVING COUNT(DISTINCT pm1.tender_id) >= 2
       OR COUNT(DISTINCT pm2.tender_id) >= 2
)
SELECT
    person_name,
    institution,
    company,
    institution_tenders,
    company_tenders,
    institution_mention_count + company_mention_count AS mention_count,
    ROUND(avg_confidence::numeric, 2) AS avg_confidence
FROM cross_institution
ORDER BY mention_count DESC, avg_confidence DESC;

COMMENT ON VIEW v_potential_conflicts IS 'Persons appearing in documents from both buyer institutions and winning companies - potential conflict of interest indicators';

-- ============================================================================
-- ENTITY STATISTICS VIEW
-- ============================================================================

CREATE OR REPLACE VIEW v_entity_stats AS
SELECT
    entity_type,
    COUNT(*) AS total_mentions,
    COUNT(DISTINCT normalized_text) AS unique_entities,
    COUNT(DISTINCT tender_id) AS tenders_with_entities,
    COUNT(DISTINCT doc_id) AS documents_processed,
    ROUND(AVG(confidence)::numeric, 2) AS avg_confidence
FROM entity_mentions
GROUP BY entity_type
ORDER BY total_mentions DESC;

COMMENT ON VIEW v_entity_stats IS 'Aggregate statistics for extracted entities by type';
