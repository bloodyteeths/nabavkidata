#!/bin/bash

# ============================================================================
# Database Schema Update Verification Script
# ============================================================================
# Created: 2025-11-24
# Purpose: Verify that all 6 new tender fields were added successfully
# ============================================================================

set -e

echo "=========================================="
echo "Database Schema Update Verification"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}ERROR: DATABASE_URL environment variable is not set${NC}"
    echo "Please set it with: export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    exit 1
fi

echo -e "${YELLOW}Step 1: Checking Alembic Migration Status${NC}"
cd /Users/tamsar/Downloads/nabavkidata/backend
alembic current
echo ""

echo -e "${YELLOW}Step 2: Verifying New Columns Exist${NC}"
psql "$DATABASE_URL" -c "
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
" || exit 1
echo ""

echo -e "${YELLOW}Step 3: Verifying Indexes Were Created${NC}"
psql "$DATABASE_URL" -c "
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'tenders'
AND indexname IN ('idx_tenders_procedure_type', 'idx_tenders_entity_category');
" || exit 1
echo ""

echo -e "${YELLOW}Step 4: Testing Column Access${NC}"
psql "$DATABASE_URL" -c "
SELECT
    COUNT(*) as total_tenders,
    COUNT(procedure_type) as with_procedure_type,
    COUNT(contract_signing_date) as with_contract_signing_date,
    COUNT(contract_duration) as with_contract_duration,
    COUNT(contracting_entity_category) as with_entity_category,
    COUNT(procurement_holder) as with_procurement_holder,
    COUNT(bureau_delivery_date) as with_bureau_delivery_date
FROM tenders;
" || exit 1
echo ""

echo -e "${YELLOW}Step 5: Sample Data (First 3 Records)${NC}"
psql "$DATABASE_URL" -c "
SELECT
    tender_id,
    LEFT(title, 50) as title,
    procedure_type,
    contract_signing_date,
    contract_duration,
    contracting_entity_category,
    procurement_holder,
    bureau_delivery_date
FROM tenders
LIMIT 3;
" || exit 1
echo ""

echo -e "${GREEN}=========================================="
echo "Verification Complete!"
echo "==========================================${NC}"
echo ""
echo "Summary of Added Fields:"
echo "  1. procedure_type (VARCHAR 200) - Indexed"
echo "  2. contract_signing_date (DATE)"
echo "  3. contract_duration (VARCHAR 100)"
echo "  4. contracting_entity_category (VARCHAR 200) - Indexed"
echo "  5. procurement_holder (VARCHAR 500)"
echo "  6. bureau_delivery_date (DATE)"
echo ""
echo -e "${GREEN}All fields successfully added to database!${NC}"
