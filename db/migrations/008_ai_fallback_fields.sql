-- Migration: Add AI fallback fields for comprehensive tender data access
-- Date: 2025-11-26
-- Purpose: Enable AI assistant to answer any question about tenders by providing
--          multiple data access layers: structured tables → raw JSON → document links

-- ==============================================================================
-- 1. Add raw_data_json to tenders for AI fallback
-- ==============================================================================
-- This stores the complete scraped JSON data from e-nabavki.gov.mk
-- AI can search this when structured fields don't have the answer

ALTER TABLE tenders
ADD COLUMN IF NOT EXISTS raw_data_json JSONB;

COMMENT ON COLUMN tenders.raw_data_json IS
'Complete raw JSON from scraping. AI fallback when structured fields insufficient.';

-- ==============================================================================
-- 2. Add source_document_url to product_items
-- ==============================================================================
-- Links products back to their source document for traceability

ALTER TABLE product_items
ADD COLUMN IF NOT EXISTS source_document_url TEXT;

ALTER TABLE product_items
ADD COLUMN IF NOT EXISTS extraction_method TEXT DEFAULT 'financial_bid';

COMMENT ON COLUMN product_items.source_document_url IS
'URL of the source document (bid PDF) where this product was extracted from';

COMMENT ON COLUMN product_items.extraction_method IS
'Method used: financial_bid, technical_spec, ocr, manual';

-- ==============================================================================
-- 3. Create tender_conditions table for evaluation criteria, guarantees, etc.
-- ==============================================================================
-- Stores conditions/requirements that AI needs to answer questions like:
-- - What are the evaluation criteria?
-- - Are there any guarantees or deposits required?
-- - What documents are required?

CREATE TABLE IF NOT EXISTS tender_conditions (
    condition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id TEXT NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,

    -- Condition type categorization
    condition_type TEXT NOT NULL CHECK (condition_type IN (
        'evaluation_criteria',   -- Критериуми за евалуација
        'bid_guarantee',         -- Гаранција за понуда
        'performance_guarantee', -- Гаранција за квалитетно извршување
        'warranty',              -- Гарантен рок
        'delivery_terms',        -- Услови за испорака
        'payment_terms',         -- Начин на плаќање
        'required_documents',    -- Потребни документи
        'technical_requirements', -- Технички барања
        'eligibility',           -- Услови за учество
        'other'
    )),

    -- Condition content
    condition_text TEXT NOT NULL,      -- Full text of the condition
    condition_value TEXT,              -- Extracted value (e.g., "5%", "30 days", "Најниска цена")
    condition_amount NUMERIC,          -- Numeric amount if applicable

    -- Source tracking
    extracted_from TEXT,               -- 'web_page', 'document_{id}', 'bid_form'
    extraction_confidence NUMERIC DEFAULT 0.5,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups by tender
CREATE INDEX IF NOT EXISTS idx_tender_conditions_tender_id
ON tender_conditions(tender_id);

CREATE INDEX IF NOT EXISTS idx_tender_conditions_type
ON tender_conditions(condition_type);

-- Full text search on condition text
ALTER TABLE tender_conditions
ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE INDEX IF NOT EXISTS idx_tender_conditions_search
ON tender_conditions USING gin(search_vector);

-- ==============================================================================
-- 4. Add document content storage for AI search
-- ==============================================================================
-- Store extracted text from documents for full-text search

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS content_text TEXT;

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS content_text_search tsvector;

CREATE INDEX IF NOT EXISTS idx_documents_content_search
ON documents USING gin(content_text_search);

COMMENT ON COLUMN documents.content_text IS
'Full text extracted from document for AI search';

-- ==============================================================================
-- 5. Create CPV code lookup table (for AI to explain CPV codes)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS cpv_codes (
    cpv_code TEXT PRIMARY KEY,
    description_mk TEXT,      -- Macedonian description
    description_en TEXT,      -- English description
    parent_code TEXT,         -- Parent CPV code (first 2-6 digits)
    level INT,                -- Hierarchy level (1-5)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE cpv_codes IS
'CPV code reference table. AI can explain what a CPV code means.';

-- Insert some common CPV codes used in Macedonian procurement
INSERT INTO cpv_codes (cpv_code, description_mk, description_en, level) VALUES
    ('33000000', 'Медицинска опрема, лекови и производи за лична нега', 'Medical equipments, pharmaceuticals and personal care products', 2),
    ('33600000', 'Фармацевтски производи', 'Pharmaceutical products', 3),
    ('45000000', 'Градежни работи', 'Construction work', 2),
    ('45200000', 'Работи за целосна или делумна изградба и инженерски работи', 'Works for complete or part construction and civil engineering work', 3),
    ('79000000', 'Деловни услуги: право, маркетинг, консултации', 'Business services: law, marketing, consulting', 2),
    ('79340000', 'Услуги за рекламирање и маркетинг', 'Advertising and marketing services', 3),
    ('09310000', 'Електрична енергија', 'Electricity', 3),
    ('50420000', 'Услуги за поправка и одржување на медицинска опрема', 'Repair and maintenance services of medical equipment', 3)
ON CONFLICT (cpv_code) DO NOTHING;

-- ==============================================================================
-- 6. Update triggers for search vectors
-- ==============================================================================

-- Trigger for tender_conditions search vector
CREATE OR REPLACE FUNCTION update_condition_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('simple', COALESCE(NEW.condition_text, '') || ' ' || COALESCE(NEW.condition_value, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_condition_search_vector ON tender_conditions;
CREATE TRIGGER trigger_condition_search_vector
    BEFORE INSERT OR UPDATE ON tender_conditions
    FOR EACH ROW EXECUTE FUNCTION update_condition_search_vector();

-- Trigger for documents content search vector
CREATE OR REPLACE FUNCTION update_document_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_text_search := to_tsvector('simple', COALESCE(NEW.content_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_document_search_vector ON documents;
CREATE TRIGGER trigger_document_search_vector
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_document_search_vector();

-- ==============================================================================
-- DONE
-- ==============================================================================

SELECT 'Migration 008_ai_fallback_fields completed successfully' AS status;
