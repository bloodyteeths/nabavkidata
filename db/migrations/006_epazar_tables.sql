-- ============================================================================
-- Migration 006: e-Pazar Tables for Electronic Marketplace Procurement Data
-- Created: 2025-11-25
-- Description: Add tables for e-pazar.gov.mk data including items, offers,
--              awarded items, and e-pazar specific tenders
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. E-PAZAR TENDERS TABLE (Separate from main tenders for marketplace data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS epazar_tenders (
    tender_id VARCHAR(100) PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,

    -- Contracting Authority
    contracting_authority VARCHAR(500),
    contracting_authority_id VARCHAR(100),

    -- Values
    estimated_value_mkd NUMERIC(15, 2),
    estimated_value_eur NUMERIC(15, 2),
    awarded_value_mkd NUMERIC(15, 2),
    awarded_value_eur NUMERIC(15, 2),

    -- Procedure & Status
    procedure_type VARCHAR(200),
    status VARCHAR(50) DEFAULT 'active', -- active, awarded, cancelled, closed

    -- Dates
    publication_date DATE,
    closing_date DATE,
    award_date DATE,
    contract_date DATE,

    -- Contract Details
    contract_number VARCHAR(100),
    contract_duration VARCHAR(200),

    -- Classification
    cpv_code VARCHAR(50),
    category VARCHAR(255),

    -- Source
    source_url TEXT,
    source_category VARCHAR(50) DEFAULT 'epazar',
    language VARCHAR(10) DEFAULT 'mk',

    -- Metadata
    scraped_at TIMESTAMP,
    content_hash VARCHAR(64), -- SHA-256 for change detection
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_epazar_tenders_status ON epazar_tenders(status);
CREATE INDEX IF NOT EXISTS idx_epazar_tenders_closing_date ON epazar_tenders(closing_date);
CREATE INDEX IF NOT EXISTS idx_epazar_tenders_publication_date ON epazar_tenders(publication_date);
CREATE INDEX IF NOT EXISTS idx_epazar_tenders_contracting_authority ON epazar_tenders(contracting_authority);
CREATE INDEX IF NOT EXISTS idx_epazar_tenders_cpv_code ON epazar_tenders(cpv_code);
CREATE INDEX IF NOT EXISTS idx_epazar_tenders_category ON epazar_tenders(category);

-- Full-text search on title and description
CREATE INDEX IF NOT EXISTS idx_epazar_tenders_search ON epazar_tenders USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, '')));

-- ============================================================================
-- 2. ITEMS TABLE (Bill of Quantities - BOQ)
-- ============================================================================
CREATE TABLE IF NOT EXISTS epazar_items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES epazar_tenders(tender_id) ON DELETE CASCADE,

    -- Item Details
    line_number INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    item_description TEXT,
    item_code VARCHAR(100),
    cpv_code VARCHAR(50),

    -- Quantity & Units
    quantity NUMERIC(15, 4) NOT NULL,
    unit VARCHAR(50),

    -- Estimated Prices (from tender)
    estimated_unit_price_mkd NUMERIC(15, 4),
    estimated_unit_price_eur NUMERIC(15, 4),
    estimated_total_price_mkd NUMERIC(15, 2),
    estimated_total_price_eur NUMERIC(15, 2),

    -- Specifications (flexible JSON storage)
    specifications JSONB,

    -- Delivery
    delivery_date DATE,
    delivery_location TEXT,

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_epazar_items_tender_id ON epazar_items(tender_id);
CREATE INDEX IF NOT EXISTS idx_epazar_items_line_number ON epazar_items(tender_id, line_number);
CREATE INDEX IF NOT EXISTS idx_epazar_items_cpv_code ON epazar_items(cpv_code);
CREATE INDEX IF NOT EXISTS idx_epazar_items_name ON epazar_items USING GIN (to_tsvector('simple', item_name));

-- ============================================================================
-- 3. OFFERS TABLE (Supplier Bids)
-- ============================================================================
CREATE TABLE IF NOT EXISTS epazar_offers (
    offer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES epazar_tenders(tender_id) ON DELETE CASCADE,

    -- Supplier Info
    supplier_name VARCHAR(500) NOT NULL,
    supplier_tax_id VARCHAR(100),
    supplier_address TEXT,
    supplier_city VARCHAR(200),
    supplier_contact_email VARCHAR(255),
    supplier_contact_phone VARCHAR(100),

    -- Offer Details
    offer_number VARCHAR(100),
    offer_date TIMESTAMP,

    -- Total Bid Amount
    total_bid_mkd NUMERIC(15, 2) NOT NULL,
    total_bid_eur NUMERIC(15, 2),

    -- Evaluation
    evaluation_score NUMERIC(5, 2),
    ranking INTEGER,
    is_winner BOOLEAN DEFAULT FALSE,

    -- Status
    offer_status VARCHAR(50) DEFAULT 'submitted', -- submitted, evaluated, rejected, awarded, disqualified
    rejection_reason TEXT,
    disqualified BOOLEAN DEFAULT FALSE,
    disqualification_date DATE,

    -- Documents Submitted (list of document names/references)
    documents_submitted JSONB,

    -- Metadata
    notes JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_epazar_offers_tender_id ON epazar_offers(tender_id);
CREATE INDEX IF NOT EXISTS idx_epazar_offers_supplier_name ON epazar_offers(supplier_name);
CREATE INDEX IF NOT EXISTS idx_epazar_offers_supplier_tax_id ON epazar_offers(supplier_tax_id);
CREATE INDEX IF NOT EXISTS idx_epazar_offers_is_winner ON epazar_offers(is_winner) WHERE is_winner = TRUE;
CREATE INDEX IF NOT EXISTS idx_epazar_offers_ranking ON epazar_offers(ranking) WHERE ranking IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_epazar_offers_status ON epazar_offers(offer_status);

-- ============================================================================
-- 4. OFFER ITEMS TABLE (Item-level Bids)
-- ============================================================================
CREATE TABLE IF NOT EXISTS epazar_offer_items (
    offer_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id UUID NOT NULL REFERENCES epazar_offers(offer_id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES epazar_items(item_id) ON DELETE CASCADE,

    -- Item-level Pricing
    quantity NUMERIC(15, 4) NOT NULL,
    unit_price_mkd NUMERIC(15, 4) NOT NULL,
    unit_price_eur NUMERIC(15, 4),
    total_price_mkd NUMERIC(15, 2) NOT NULL,
    total_price_eur NUMERIC(15, 2),

    -- Item-level Evaluation
    item_score NUMERIC(5, 2),
    status VARCHAR(50) DEFAULT 'offered', -- offered, accepted, rejected
    notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_epazar_offer_items_offer_id ON epazar_offer_items(offer_id);
CREATE INDEX IF NOT EXISTS idx_epazar_offer_items_item_id ON epazar_offer_items(item_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_epazar_offer_items_unique ON epazar_offer_items(offer_id, item_id);

-- ============================================================================
-- 5. AWARDED ITEMS TABLE (Contract/Delivery Tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS epazar_awarded_items (
    awarded_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES epazar_tenders(tender_id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES epazar_items(item_id) ON DELETE CASCADE,
    offer_id UUID REFERENCES epazar_offers(offer_id) ON DELETE SET NULL,

    -- Supplier (redundant for query performance)
    supplier_name VARCHAR(500) NOT NULL,
    supplier_tax_id VARCHAR(100),

    -- Contract Terms
    contract_item_number VARCHAR(50),
    contracted_quantity NUMERIC(15, 4) NOT NULL,
    contracted_unit_price_mkd NUMERIC(15, 4) NOT NULL,
    contracted_total_mkd NUMERIC(15, 2) NOT NULL,
    contracted_unit_price_eur NUMERIC(15, 4),
    contracted_total_eur NUMERIC(15, 2),

    -- Delivery Info
    planned_delivery_date DATE,
    actual_delivery_date DATE,
    delivery_location TEXT,

    -- Performance Tracking
    received_quantity NUMERIC(15, 4),
    quality_score NUMERIC(3, 1), -- 1-5 scale
    quality_notes TEXT,
    on_time BOOLEAN,

    -- Financial
    billed_amount_mkd NUMERIC(15, 2),
    paid_amount_mkd NUMERIC(15, 2),
    payment_date DATE,

    -- Status
    status VARCHAR(50) DEFAULT 'pending', -- pending, delivered, accepted, rejected, invoiced, paid
    completion_date DATE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_epazar_awarded_items_tender_id ON epazar_awarded_items(tender_id);
CREATE INDEX IF NOT EXISTS idx_epazar_awarded_items_item_id ON epazar_awarded_items(item_id);
CREATE INDEX IF NOT EXISTS idx_epazar_awarded_items_supplier_name ON epazar_awarded_items(supplier_name);
CREATE INDEX IF NOT EXISTS idx_epazar_awarded_items_status ON epazar_awarded_items(status);
CREATE INDEX IF NOT EXISTS idx_epazar_awarded_items_delivery_date ON epazar_awarded_items(planned_delivery_date);

-- ============================================================================
-- 6. E-PAZAR DOCUMENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS epazar_documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES epazar_tenders(tender_id) ON DELETE CASCADE,

    -- Document Info
    doc_type VARCHAR(100), -- tender_docs, technical_specs, clarification, bid_doc, award_decision, cancellation_decision, contract
    doc_category VARCHAR(100), -- specification, administrative, financial, technical, legal
    file_name VARCHAR(500),
    file_path TEXT,
    file_url TEXT,

    -- Content
    content_text TEXT,
    extraction_status VARCHAR(50) DEFAULT 'pending', -- pending, success, failed

    -- File Metadata
    file_size_bytes INTEGER,
    page_count INTEGER,
    mime_type VARCHAR(100),
    file_hash VARCHAR(64), -- SHA-256 for duplicate detection

    -- Dates
    upload_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_epazar_documents_tender_id ON epazar_documents(tender_id);
CREATE INDEX IF NOT EXISTS idx_epazar_documents_doc_type ON epazar_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_epazar_documents_extraction_status ON epazar_documents(extraction_status);

-- ============================================================================
-- 7. E-PAZAR SUPPLIERS PROFILE TABLE (Cached supplier info)
-- ============================================================================
CREATE TABLE IF NOT EXISTS epazar_suppliers (
    supplier_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic Info
    company_name VARCHAR(500) NOT NULL,
    tax_id VARCHAR(100) UNIQUE,
    company_type VARCHAR(200),

    -- Contact
    address TEXT,
    city VARCHAR(200),
    contact_person VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(100),
    website TEXT,

    -- Statistics (aggregated)
    total_offers INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    win_rate NUMERIC(5, 2),
    total_contract_value_mkd NUMERIC(20, 2),
    avg_bid_amount_mkd NUMERIC(15, 2),

    -- Categories/Industries
    industries JSONB, -- Array of CPV codes or categories

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_epazar_suppliers_company_name ON epazar_suppliers(company_name);
CREATE INDEX IF NOT EXISTS idx_epazar_suppliers_tax_id ON epazar_suppliers(tax_id);
CREATE INDEX IF NOT EXISTS idx_epazar_suppliers_city ON epazar_suppliers(city);

-- ============================================================================
-- 8. SCRAPING JOB TRACKING FOR E-PAZAR
-- ============================================================================
CREATE TABLE IF NOT EXISTS epazar_scraping_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'running', -- running, completed, failed

    -- Counts
    tenders_scraped INTEGER DEFAULT 0,
    items_scraped INTEGER DEFAULT 0,
    offers_scraped INTEGER DEFAULT 0,
    documents_scraped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,

    -- Error Info
    error_message TEXT,
    error_details JSONB,

    -- Config
    spider_name VARCHAR(100) DEFAULT 'epazar',
    incremental BOOLEAN DEFAULT TRUE,
    category VARCHAR(50), -- active, awarded, cancelled, all

    -- Progress
    last_page_scraped INTEGER,
    total_pages INTEGER,
    last_tender_id VARCHAR(100),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_epazar_scraping_jobs_status ON epazar_scraping_jobs(status);
CREATE INDEX IF NOT EXISTS idx_epazar_scraping_jobs_started_at ON epazar_scraping_jobs(started_at);

-- ============================================================================
-- 9. TRIGGER FOR UPDATING SUPPLIER STATS
-- ============================================================================
CREATE OR REPLACE FUNCTION update_epazar_supplier_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update supplier statistics when offer is inserted/updated
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        -- Upsert supplier
        INSERT INTO epazar_suppliers (company_name, tax_id, address, city)
        VALUES (NEW.supplier_name, NEW.supplier_tax_id, NEW.supplier_address, NEW.supplier_city)
        ON CONFLICT (company_name) DO UPDATE SET
            tax_id = COALESCE(EXCLUDED.tax_id, epazar_suppliers.tax_id),
            address = COALESCE(EXCLUDED.address, epazar_suppliers.address),
            city = COALESCE(EXCLUDED.city, epazar_suppliers.city),
            updated_at = CURRENT_TIMESTAMP;

        -- Update aggregated stats
        UPDATE epazar_suppliers SET
            total_offers = (
                SELECT COUNT(*) FROM epazar_offers WHERE supplier_name = NEW.supplier_name
            ),
            total_wins = (
                SELECT COUNT(*) FROM epazar_offers WHERE supplier_name = NEW.supplier_name AND is_winner = TRUE
            ),
            total_contract_value_mkd = (
                SELECT COALESCE(SUM(total_bid_mkd), 0) FROM epazar_offers
                WHERE supplier_name = NEW.supplier_name AND is_winner = TRUE
            ),
            avg_bid_amount_mkd = (
                SELECT AVG(total_bid_mkd) FROM epazar_offers WHERE supplier_name = NEW.supplier_name
            ),
            win_rate = CASE
                WHEN (SELECT COUNT(*) FROM epazar_offers WHERE supplier_name = NEW.supplier_name) > 0
                THEN (SELECT COUNT(*) FROM epazar_offers WHERE supplier_name = NEW.supplier_name AND is_winner = TRUE)::NUMERIC /
                     (SELECT COUNT(*) FROM epazar_offers WHERE supplier_name = NEW.supplier_name)::NUMERIC * 100
                ELSE 0
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE company_name = NEW.supplier_name;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_update_epazar_supplier_stats ON epazar_offers;
CREATE TRIGGER trigger_update_epazar_supplier_stats
    AFTER INSERT OR UPDATE ON epazar_offers
    FOR EACH ROW
    EXECUTE FUNCTION update_epazar_supplier_stats();

-- ============================================================================
-- 10. COMMENTS FOR DOCUMENTATION
-- ============================================================================
COMMENT ON TABLE epazar_tenders IS 'E-Pazar electronic marketplace tenders with full metadata';
COMMENT ON TABLE epazar_items IS 'Bill of Quantities (BOQ) items for each tender';
COMMENT ON TABLE epazar_offers IS 'Supplier bids/offers on tenders';
COMMENT ON TABLE epazar_offer_items IS 'Item-level pricing within each offer';
COMMENT ON TABLE epazar_awarded_items IS 'Awarded contract items with delivery tracking';
COMMENT ON TABLE epazar_documents IS 'Tender documents including specs, decisions, contracts';
COMMENT ON TABLE epazar_suppliers IS 'Cached supplier profiles with aggregated statistics';
COMMENT ON TABLE epazar_scraping_jobs IS 'Job tracking for e-pazar spider runs';

COMMIT;
