-- PHASE 3: Comprehensive Procurement Data Model
-- Migration: Add extended fields and new tables for complete tender lifecycle tracking
-- Date: 2025-11-24

BEGIN;

-- =====================================================
-- STEP 1: Extend tenders table with Phase 3 fields
-- =====================================================

ALTER TABLE tenders ADD COLUMN IF NOT EXISTS contact_person VARCHAR(255);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(100);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS num_bidders INTEGER;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS security_deposit_mkd NUMERIC(15, 2);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS performance_guarantee_mkd NUMERIC(15, 2);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS payment_terms TEXT;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS evaluation_method VARCHAR(200);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS award_criteria JSONB;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS has_lots BOOLEAN DEFAULT FALSE;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS num_lots INTEGER;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS amendment_count INTEGER DEFAULT 0;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS last_amendment_date DATE;

COMMENT ON COLUMN tenders.contact_person IS 'Primary contact person for tender inquiries';
COMMENT ON COLUMN tenders.contact_email IS 'Contact email for tender questions';
COMMENT ON COLUMN tenders.contact_phone IS 'Contact phone number';
COMMENT ON COLUMN tenders.num_bidders IS 'Total number of bidders/participants';
COMMENT ON COLUMN tenders.security_deposit_mkd IS 'Required security deposit in MKD';
COMMENT ON COLUMN tenders.performance_guarantee_mkd IS 'Required performance guarantee in MKD';
COMMENT ON COLUMN tenders.payment_terms IS 'Payment terms and conditions';
COMMENT ON COLUMN tenders.evaluation_method IS 'Tender evaluation methodology';
COMMENT ON COLUMN tenders.award_criteria IS 'JSON object with award criteria and weightings';
COMMENT ON COLUMN tenders.has_lots IS 'Whether tender has multiple lots';
COMMENT ON COLUMN tenders.num_lots IS 'Number of lots in tender';
COMMENT ON COLUMN tenders.amendment_count IS 'Number of amendments made to tender';
COMMENT ON COLUMN tenders.last_amendment_date IS 'Date of most recent amendment';

-- =====================================================
-- STEP 2: Create tender_lots table
-- =====================================================

CREATE TABLE IF NOT EXISTS tender_lots (
    lot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    lot_number VARCHAR(50),
    lot_title TEXT,
    lot_description TEXT,
    estimated_value_mkd NUMERIC(15, 2),
    estimated_value_eur NUMERIC(15, 2),
    actual_value_mkd NUMERIC(15, 2),
    actual_value_eur NUMERIC(15, 2),
    cpv_code VARCHAR(50),
    winner VARCHAR(500),
    quantity VARCHAR(200),
    unit VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tender_lots_tender_id ON tender_lots(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_lots_winner ON tender_lots(winner);

COMMENT ON TABLE tender_lots IS 'Individual lots/items within multi-lot tenders';
COMMENT ON COLUMN tender_lots.lot_number IS 'Lot number within tender (e.g., "1", "2A", etc.)';

-- =====================================================
-- STEP 3: Create tender_bidders table
-- =====================================================

CREATE TABLE IF NOT EXISTS tender_bidders (
    bidder_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    lot_id UUID REFERENCES tender_lots(lot_id) ON DELETE CASCADE,
    company_name VARCHAR(500) NOT NULL,
    company_tax_id VARCHAR(100),
    company_address TEXT,
    bid_amount_mkd NUMERIC(15, 2),
    bid_amount_eur NUMERIC(15, 2),
    is_winner BOOLEAN DEFAULT FALSE,
    rank INTEGER,
    disqualified BOOLEAN DEFAULT FALSE,
    disqualification_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tender_bidders_tender_id ON tender_bidders(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_bidders_lot_id ON tender_bidders(lot_id);
CREATE INDEX IF NOT EXISTS idx_tender_bidders_company_name ON tender_bidders(company_name);
CREATE INDEX IF NOT EXISTS idx_tender_bidders_is_winner ON tender_bidders(is_winner);
CREATE INDEX IF NOT EXISTS idx_tender_bidders_company_tax_id ON tender_bidders(company_tax_id);

COMMENT ON TABLE tender_bidders IS 'Bidders and participants in tenders';
COMMENT ON COLUMN tender_bidders.rank IS 'Ranking in evaluation (1=best offer)';
COMMENT ON COLUMN tender_bidders.disqualified IS 'Whether bidder was disqualified';

-- =====================================================
-- STEP 4: Create tender_amendments table
-- =====================================================

CREATE TABLE IF NOT EXISTS tender_amendments (
    amendment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    amendment_date DATE NOT NULL,
    amendment_type VARCHAR(100),
    field_changed VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    announcement_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tender_amendments_tender_id ON tender_amendments(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_amendments_date ON tender_amendments(amendment_date);
CREATE INDEX IF NOT EXISTS idx_tender_amendments_type ON tender_amendments(amendment_type);

COMMENT ON TABLE tender_amendments IS 'Modifications and amendments to tenders';
COMMENT ON COLUMN tender_amendments.amendment_type IS 'Type: deadline_extension, value_change, clarification, cancellation, etc.';

-- =====================================================
-- STEP 5: Create procuring_entities table
-- =====================================================

CREATE TABLE IF NOT EXISTS procuring_entities (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name VARCHAR(500) NOT NULL UNIQUE,
    entity_type VARCHAR(200),
    category VARCHAR(200),
    tax_id VARCHAR(100),
    address TEXT,
    city VARCHAR(200),
    contact_person VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(100),
    website TEXT,
    total_tenders INTEGER DEFAULT 0,
    total_value_mkd NUMERIC(20, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_procuring_entities_name ON procuring_entities(entity_name);
CREATE INDEX IF NOT EXISTS idx_procuring_entities_type ON procuring_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_procuring_entities_category ON procuring_entities(category);
CREATE INDEX IF NOT EXISTS idx_procuring_entities_city ON procuring_entities(city);

COMMENT ON TABLE procuring_entities IS 'Profile data for procuring entities/institutions';
COMMENT ON COLUMN procuring_entities.entity_type IS 'Type: ministry, municipality, public_company, etc.';
COMMENT ON COLUMN procuring_entities.total_tenders IS 'Total number of tenders published';
COMMENT ON COLUMN procuring_entities.total_value_mkd IS 'Total value of all tenders in MKD';

-- =====================================================
-- STEP 6: Create suppliers table
-- =====================================================

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(500) NOT NULL UNIQUE,
    tax_id VARCHAR(100) UNIQUE,
    company_type VARCHAR(200),
    address TEXT,
    city VARCHAR(200),
    contact_person VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(100),
    website TEXT,
    total_wins INTEGER DEFAULT 0,
    total_bids INTEGER DEFAULT 0,
    win_rate NUMERIC(5, 2),
    total_contract_value_mkd NUMERIC(20, 2),
    industries JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_suppliers_company_name ON suppliers(company_name);
CREATE INDEX IF NOT EXISTS idx_suppliers_tax_id ON suppliers(tax_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_city ON suppliers(city);
CREATE INDEX IF NOT EXISTS idx_suppliers_win_rate ON suppliers(win_rate);

COMMENT ON TABLE suppliers IS 'Profile data for suppliers/contractors';
COMMENT ON COLUMN suppliers.win_rate IS 'Win rate percentage (0-100)';
COMMENT ON COLUMN suppliers.total_contract_value_mkd IS 'Total value of won contracts in MKD';
COMMENT ON COLUMN suppliers.industries IS 'JSON array of CPV codes or industry categories';

-- =====================================================
-- STEP 7: Create tender_clarifications table
-- =====================================================

CREATE TABLE IF NOT EXISTS tender_clarifications (
    clarification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(100) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    question_date DATE,
    question_text TEXT NOT NULL,
    answer_date DATE,
    answer_text TEXT,
    is_public BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tender_clarifications_tender_id ON tender_clarifications(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_clarifications_question_date ON tender_clarifications(question_date);

COMMENT ON TABLE tender_clarifications IS 'Questions and clarifications for tenders';
COMMENT ON COLUMN tender_clarifications.is_public IS 'Whether Q&A is publicly visible';

-- =====================================================
-- STEP 8: Update documents table with categorization
-- =====================================================

ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_category VARCHAR(100);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_version VARCHAR(50);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS upload_date DATE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(doc_category);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);

COMMENT ON COLUMN documents.doc_category IS 'Category: technical_specs, financial_docs, award_decision, contract, etc.';
COMMENT ON COLUMN documents.doc_version IS 'Document version number';
COMMENT ON COLUMN documents.file_hash IS 'SHA-256 hash for duplicate detection';

-- =====================================================
-- STEP 9: Create materialized views for analytics
-- =====================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS tender_statistics AS
SELECT
    DATE_TRUNC('month', publication_date) AS month,
    status,
    procedure_type,
    COUNT(*) AS tender_count,
    SUM(estimated_value_mkd) AS total_estimated_mkd,
    SUM(actual_value_mkd) AS total_actual_mkd,
    AVG(num_bidders) AS avg_bidders
FROM tenders
WHERE publication_date IS NOT NULL
GROUP BY DATE_TRUNC('month', publication_date), status, procedure_type;

CREATE INDEX IF NOT EXISTS idx_tender_statistics_month ON tender_statistics(month);

COMMENT ON MATERIALIZED VIEW tender_statistics IS 'Aggregated tender statistics by month, status, and procedure type';

-- =====================================================
-- STEP 10: Create function to update entity/supplier stats
-- =====================================================

CREATE OR REPLACE FUNCTION update_entity_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update procuring entity stats
    INSERT INTO procuring_entities (entity_name, total_tenders, total_value_mkd)
    VALUES (NEW.procuring_entity, 1, COALESCE(NEW.estimated_value_mkd, 0))
    ON CONFLICT (entity_name)
    DO UPDATE SET
        total_tenders = procuring_entities.total_tenders + 1,
        total_value_mkd = procuring_entities.total_value_mkd + COALESCE(NEW.estimated_value_mkd, 0),
        updated_at = CURRENT_TIMESTAMP;

    -- Update supplier stats if winner exists
    IF NEW.winner IS NOT NULL AND NEW.winner != '' THEN
        INSERT INTO suppliers (company_name, total_wins, total_contract_value_mkd)
        VALUES (NEW.winner, 1, COALESCE(NEW.actual_value_mkd, 0))
        ON CONFLICT (company_name)
        DO UPDATE SET
            total_wins = suppliers.total_wins + 1,
            total_contract_value_mkd = suppliers.total_contract_value_mkd + COALESCE(NEW.actual_value_mkd, 0),
            updated_at = CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_entity_stats
AFTER INSERT ON tenders
FOR EACH ROW
EXECUTE FUNCTION update_entity_stats();

COMMENT ON FUNCTION update_entity_stats() IS 'Automatically update entity and supplier statistics when tenders are inserted';

COMMIT;

-- =====================================================
-- Verify migration
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE 'Phase 3 migration completed successfully!';
    RAISE NOTICE 'New tables created: tender_lots, tender_bidders, tender_amendments, procuring_entities, suppliers, tender_clarifications';
    RAISE NOTICE 'Extended tenders table with 13 new fields';
    RAISE NOTICE 'Added triggers for automatic stats updates';
END $$;
