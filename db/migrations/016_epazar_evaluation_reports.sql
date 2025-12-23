-- Migration: Add evaluation report extraction support for e-pazar
-- This captures ALL data from evaluationReport.pdf files

-- 1. New table to store evaluation reports
CREATE TABLE IF NOT EXISTS epazar_evaluation_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(50) NOT NULL REFERENCES epazar_tenders(tender_id) ON DELETE CASCADE,

    -- PDF source
    pdf_url TEXT NOT NULL,
    pdf_filename VARCHAR(255),
    pdf_downloaded_at TIMESTAMP,

    -- Header info from PDF
    tender_number VARCHAR(100),
    contracting_authority TEXT,
    tender_type VARCHAR(100),  -- Стоки, Услуги, Работи
    tender_subject TEXT,
    publication_date DATE,
    evaluation_date DATE,

    -- All bidders who submitted offers (array of names)
    bidders_list TEXT[],

    -- Rejected/cancelled sections
    rejected_offers JSONB,        -- Отфрлени понуди по делови
    rejected_bidders JSONB,       -- Одбиени понудувачи
    cancelled_parts JSONB,        -- Поништени делови
    parts_without_offers JSONB,   -- Делови за кои нема понуда

    -- Signatures
    commission_members JSONB,     -- Array of {name, signed_at}
    responsible_person JSONB,     -- {name, signed_at}

    -- Raw data
    raw_text TEXT,                -- Full extracted text
    raw_json JSONB,               -- Full structured extraction

    -- Extraction metadata
    extraction_method VARCHAR(50) DEFAULT 'pymupdf',  -- pymupdf, gemini, manual
    extraction_status VARCHAR(50) DEFAULT 'pending',  -- pending, success, partial, failed
    extraction_error TEXT,
    extraction_confidence NUMERIC(3,2),
    page_count INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(tender_id)
);

-- 2. Add missing columns to epazar_offer_items for per-item winner data
ALTER TABLE epazar_offer_items
ADD COLUMN IF NOT EXISTS offered_brand VARCHAR(255),
ADD COLUMN IF NOT EXISTS offered_brand_details TEXT,
ADD COLUMN IF NOT EXISTS offered_specifications JSONB,
ADD COLUMN IF NOT EXISTS offered_specifications_text TEXT,
ADD COLUMN IF NOT EXISTS line_number INTEGER,
ADD COLUMN IF NOT EXISTS item_subject TEXT,
ADD COLUMN IF NOT EXISTS product_name TEXT,
ADD COLUMN IF NOT EXISTS winner_name TEXT,
ADD COLUMN IF NOT EXISTS unit VARCHAR(50),
ADD COLUMN IF NOT EXISTS extraction_source VARCHAR(50) DEFAULT 'api',  -- api, evaluation_pdf
ADD COLUMN IF NOT EXISTS report_id UUID REFERENCES epazar_evaluation_reports(report_id);

-- 3. Add columns to epazar_items for required brands/specs from evaluation
ALTER TABLE epazar_items
ADD COLUMN IF NOT EXISTS required_brands TEXT[],
ADD COLUMN IF NOT EXISTS required_brands_text TEXT,
ADD COLUMN IF NOT EXISTS required_specifications_text TEXT,
ADD COLUMN IF NOT EXISTS evaluation_extracted BOOLEAN DEFAULT FALSE;

-- 4. Add evaluation report tracking to epazar_tenders
ALTER TABLE epazar_tenders
ADD COLUMN IF NOT EXISTS has_evaluation_report BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS evaluation_report_url TEXT,
ADD COLUMN IF NOT EXISTS evaluation_report_extracted BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS evaluation_extraction_status VARCHAR(50),
ADD COLUMN IF NOT EXISTS evaluation_extraction_error TEXT;

-- 5. Create table for all bidders per tender (not just winners)
CREATE TABLE IF NOT EXISTS epazar_bidders (
    bidder_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(50) NOT NULL REFERENCES epazar_tenders(tender_id) ON DELETE CASCADE,
    bidder_name TEXT NOT NULL,
    bidder_full_name TEXT,
    is_winner BOOLEAN DEFAULT FALSE,
    is_rejected BOOLEAN DEFAULT FALSE,
    is_disqualified BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT,
    source VARCHAR(50) DEFAULT 'evaluation_pdf',
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(tender_id, bidder_name)
);

-- 6. Create table for per-item evaluation details (comprehensive)
CREATE TABLE IF NOT EXISTS epazar_item_evaluations (
    evaluation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES epazar_evaluation_reports(report_id) ON DELETE CASCADE,
    tender_id VARCHAR(50) NOT NULL REFERENCES epazar_tenders(tender_id) ON DELETE CASCADE,
    item_id UUID REFERENCES epazar_items(item_id),

    -- Line info
    line_number INTEGER NOT NULL,

    -- What buyer requested
    item_subject TEXT,              -- Предмет на набавка
    product_name TEXT,              -- Име на производ
    required_brands TEXT[],         -- Барани производители (array)
    required_brands_raw TEXT,       -- Raw text: "Fairy,Gloss"
    required_specs JSONB,           -- Барани детални спецификации (structured)
    required_specs_raw TEXT,        -- Raw text of specs

    -- What winner offered
    offered_brand TEXT,             -- Понуден производител
    offered_specs JSONB,            -- Понудени детални спецификации (structured)
    offered_specs_raw TEXT,         -- Raw text of offered specs

    -- Pricing
    unit VARCHAR(100),              -- Ед. мерка
    quantity NUMERIC(15,4),         -- Кол.
    unit_price_without_vat NUMERIC(15,4),  -- Ед. цена без ДДВ
    total_without_vat NUMERIC(15,4),       -- Вкупно без ДДВ

    -- Winner
    winner_name TEXT,               -- Понудувач
    winner_full_name TEXT,

    -- Status
    is_awarded BOOLEAN DEFAULT TRUE,
    is_cancelled BOOLEAN DEFAULT FALSE,
    cancellation_reason TEXT,

    -- Raw data for this row
    raw_row_data JSONB,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(tender_id, line_number)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_epazar_eval_reports_tender ON epazar_evaluation_reports(tender_id);
CREATE INDEX IF NOT EXISTS idx_epazar_eval_reports_status ON epazar_evaluation_reports(extraction_status);
CREATE INDEX IF NOT EXISTS idx_epazar_item_evals_tender ON epazar_item_evaluations(tender_id);
CREATE INDEX IF NOT EXISTS idx_epazar_item_evals_report ON epazar_item_evaluations(report_id);
CREATE INDEX IF NOT EXISTS idx_epazar_item_evals_brand ON epazar_item_evaluations(offered_brand);
CREATE INDEX IF NOT EXISTS idx_epazar_bidders_tender ON epazar_bidders(tender_id);
CREATE INDEX IF NOT EXISTS idx_epazar_tenders_eval_status ON epazar_tenders(evaluation_extraction_status);

-- Fix source_url to include /details
UPDATE epazar_tenders
SET source_url = source_url || '/details'
WHERE source_url IS NOT NULL
AND source_url NOT LIKE '%/details';

COMMENT ON TABLE epazar_evaluation_reports IS 'Stores extracted data from e-pazar evaluationReport.pdf files';
COMMENT ON TABLE epazar_item_evaluations IS 'Per-item evaluation details including winner brand, price, specs from PDF';
COMMENT ON TABLE epazar_bidders IS 'All bidders per tender (not just winners)';
