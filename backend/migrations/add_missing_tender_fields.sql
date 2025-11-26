-- ============================================================================
-- Add Missing Tender Fields to Database
-- ============================================================================
-- Created: 2025-11-24
-- Purpose: Add 6 new fields to tenders table for enhanced tender tracking
--
-- Fields being added:
-- 1. procedure_type - VARCHAR(200) - Вид на постапка
-- 2. contract_signing_date - DATE - Датум на склучување
-- 3. contract_duration - VARCHAR(100) - Времетраење (e.g., "12 месеци")
-- 4. contracting_entity_category - VARCHAR(200) - Категорија на договорен орган
-- 5. procurement_holder - VARCHAR(500) - Носител на набавката
-- 6. bureau_delivery_date - DATE - Датум на доставување
-- ============================================================================

BEGIN;

-- Add new columns to tenders table
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS procedure_type VARCHAR(200);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS contract_signing_date DATE;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS contract_duration VARCHAR(100);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS contracting_entity_category VARCHAR(200);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS procurement_holder VARCHAR(500);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS bureau_delivery_date DATE;

-- Add indexes for frequently queried fields
CREATE INDEX IF NOT EXISTS idx_tenders_procedure_type ON tenders(procedure_type);
CREATE INDEX IF NOT EXISTS idx_tenders_entity_category ON tenders(contracting_entity_category);

-- Add comments for documentation (PostgreSQL specific)
COMMENT ON COLUMN tenders.procedure_type IS 'Вид на постапка (Procedure Type) - e.g., "Отворена постапка", "Ограничена постапка"';
COMMENT ON COLUMN tenders.contract_signing_date IS 'Датум на склучување на договор (Contract Signing Date)';
COMMENT ON COLUMN tenders.contract_duration IS 'Времетраење на договорот (Contract Duration) - e.g., "12 месеци", "24 месеци"';
COMMENT ON COLUMN tenders.contracting_entity_category IS 'Категорија на договорен орган (Contracting Entity Category)';
COMMENT ON COLUMN tenders.procurement_holder IS 'Име на носителот на набавката (Procurement Holder Name)';
COMMENT ON COLUMN tenders.bureau_delivery_date IS 'Датум на доставување до Бирото (Bureau Delivery Date)';

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Check that columns were added successfully
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'tenders'
AND column_name IN (
    'procedure_type',
    'contract_signing_date',
    'contract_duration',
    'contracting_entity_category',
    'procurement_holder',
    'bureau_delivery_date'
)
ORDER BY column_name;

-- Check indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'tenders'
AND indexname IN ('idx_tenders_procedure_type', 'idx_tenders_entity_category');

-- Sample data query (will return NULL for new columns until data is populated)
SELECT
    tender_id,
    title,
    procedure_type,
    contract_signing_date,
    contract_duration,
    contracting_entity_category,
    procurement_holder,
    bureau_delivery_date
FROM tenders
LIMIT 5;
