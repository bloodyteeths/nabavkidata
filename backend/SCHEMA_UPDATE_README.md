# Database Schema Update - Missing Tender Fields

**Date:** 2025-11-24
**Status:** Ready for deployment
**Impact:** Adds 6 new columns to `tenders` table

## Overview

This update adds 6 missing fields to the tender tracking system to capture additional procurement information from the Bureau of Public Procurement.

## New Fields Added

| Field Name | Type | Length | Indexed | Description (MK) | Description (EN) |
|------------|------|--------|---------|------------------|------------------|
| `procedure_type` | VARCHAR | 200 | Yes | Вид на постапка | Procedure Type |
| `contract_signing_date` | DATE | - | No | Датум на склучување | Contract Signing Date |
| `contract_duration` | VARCHAR | 100 | No | Времетраење | Contract Duration |
| `contracting_entity_category` | VARCHAR | 200 | Yes | Категорија на договорен орган | Contracting Entity Category |
| `procurement_holder` | VARCHAR | 500 | No | Носител на набавката | Procurement Holder |
| `bureau_delivery_date` | DATE | - | No | Датум на доставување | Bureau Delivery Date |

## Deployment Options

### Option 1: Using Alembic Migration (Recommended)

This is the recommended approach as it maintains migration history.

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend

# Check current migration status
alembic current

# Apply the migration
alembic upgrade head

# Verify migration was applied
alembic current
```

### Option 2: Direct SQL Execution

Use this if you need immediate database update without Alembic.

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend

# Execute the SQL migration
psql $DATABASE_URL -f migrations/add_missing_tender_fields.sql
```

## Verification

After deploying, run the verification script:

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend

# Make sure DATABASE_URL is set
export DATABASE_URL='postgresql://user:pass@host:port/dbname'

# Run verification
./verify_schema_update.sh
```

Or verify manually:

```sql
-- Check columns exist
\d+ tenders

-- Check indexes
\di+ idx_tenders_procedure_type
\di+ idx_tenders_entity_category

-- Test query
SELECT
    procedure_type,
    contract_signing_date,
    contract_duration,
    contracting_entity_category,
    procurement_holder,
    bureau_delivery_date
FROM tenders
LIMIT 1;
```

## Files Modified

### 1. SQLAlchemy Model
- **File:** `/Users/tamsar/Downloads/nabavkidata/backend/models.py`
- **Changes:** Added 6 new column definitions to `Tender` class
- **Lines:** 57-63

### 2. Pydantic Schemas
- **File:** `/Users/tamsar/Downloads/nabavkidata/backend/schemas.py`
- **Changes:**
  - Added fields to `TenderBase` (lines 34-40)
  - Added fields to `TenderUpdate` (lines 67-73)
  - Added filter fields to `TenderSearchRequest` (lines 275-279)

### 3. Alembic Migration
- **File:** `/Users/tamsar/Downloads/nabavkidata/backend/alembic/versions/20251124_add_missing_tender_fields.py`
- **Revision ID:** `20251124_addfields`
- **Parent Revision:** `20251123_220000`

### 4. Direct SQL Script
- **File:** `/Users/tamsar/Downloads/nabavkidata/backend/migrations/add_missing_tender_fields.sql`
- **Purpose:** Alternative to Alembic for direct database updates

### 5. Verification Script
- **File:** `/Users/tamsar/Downloads/nabavkidata/backend/verify_schema_update.sh`
- **Purpose:** Automated verification of schema changes

## API Impact

### Existing Endpoints

All existing API endpoints will continue to work. The new fields are optional (nullable).

### New Filtering Capabilities

The `TenderSearchRequest` schema now supports filtering by:

```python
# Filter by procedure type
{
    "procedure_type": "Отворена постапка"
}

# Filter by contracting entity category
{
    "contracting_entity_category": "Централна влада"
}

# Filter by contract signing date range
{
    "contract_signing_date_from": "2025-01-01",
    "contract_signing_date_to": "2025-12-31"
}
```

### Response Format

Tender responses will now include the new fields:

```json
{
    "tender_id": "T-2025-001",
    "title": "Набавка на канцелариски материјал",
    "procedure_type": "Отворена постапка",
    "contract_signing_date": "2025-03-15",
    "contract_duration": "12 месеци",
    "contracting_entity_category": "Централна влада",
    "procurement_holder": "Министерство за образование",
    "bureau_delivery_date": "2025-02-28",
    ...
}
```

## Rollback Instructions

If you need to rollback this migration:

### Using Alembic

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend
alembic downgrade -1
```

### Using SQL

```sql
BEGIN;

-- Drop indexes
DROP INDEX IF EXISTS idx_tenders_entity_category;
DROP INDEX IF EXISTS idx_tenders_procedure_type;

-- Drop columns
ALTER TABLE tenders DROP COLUMN IF EXISTS bureau_delivery_date;
ALTER TABLE tenders DROP COLUMN IF EXISTS procurement_holder;
ALTER TABLE tenders DROP COLUMN IF EXISTS contracting_entity_category;
ALTER TABLE tenders DROP COLUMN IF EXISTS contract_duration;
ALTER TABLE tenders DROP COLUMN IF EXISTS contract_signing_date;
ALTER TABLE tenders DROP COLUMN IF EXISTS procedure_type;

COMMIT;
```

## Next Steps

After deploying this schema update:

1. **Update Scraper**: Modify the tender scraping logic to extract and populate these new fields
2. **Update Frontend**: Add UI components to display the new fields in tender detail pages
3. **Update Search UI**: Add filter controls for `procedure_type` and `contracting_entity_category`
4. **Data Migration**: Backfill existing tenders with data from the Bureau website if available

## Testing

```bash
# Run backend tests
cd /Users/tamsar/Downloads/nabavkidata/backend
pytest tests/ -v

# Test API endpoint
curl -X POST http://localhost:8000/api/tenders/search \
  -H "Content-Type: application/json" \
  -d '{
    "procedure_type": "Отворена постапка",
    "page": 1,
    "page_size": 10
  }'
```

## Support

For issues or questions, contact the database team or refer to:
- SQLAlchemy docs: https://docs.sqlalchemy.org/
- Alembic docs: https://alembic.sqlalchemy.org/
- PostgreSQL docs: https://www.postgresql.org/docs/

---

**Migration Author:** Agent D - Database Model & Schema Upgrade Engineer
**Review Status:** Pending
**Deployment Status:** Ready
