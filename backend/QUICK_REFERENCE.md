# Quick Reference - Database Schema Update

## New Fields Added (6 Total)

| Field | Type | Macedonian | Example |
|-------|------|------------|---------|
| `procedure_type` | VARCHAR(200) | Вид на постапка | "Отворена постапка" |
| `contract_signing_date` | DATE | Датум на склучување | 2025-03-15 |
| `contract_duration` | VARCHAR(100) | Времетраење | "12 месеци" |
| `contracting_entity_category` | VARCHAR(200) | Категорија на договорен орган | "Централна влада" |
| `procurement_holder` | VARCHAR(500) | Носител на набавката | "Министерство за образование" |
| `bureau_delivery_date` | DATE | Датум на доставување | 2025-02-28 |

## Quick Deploy (One-Liner)

```bash
# Alembic (Recommended)
cd /Users/tamsar/Downloads/nabavkidata/backend && alembic upgrade head

# Or use interactive script
cd /Users/tamsar/Downloads/nabavkidata/backend && ./DEPLOYMENT_COMMANDS.sh deploy
```

## Quick Verify

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend && ./verify_schema_update.sh
```

## Quick Test

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend && python3 test_new_fields.py
```

## Quick Rollback

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend && alembic downgrade -1
```

## API Usage

### Create Tender
```bash
curl -X POST http://localhost:8000/api/tenders \
  -H "Content-Type: application/json" \
  -d '{
    "tender_id": "T-2025-001",
    "title": "Example Tender",
    "procedure_type": "Отворена постапка",
    "contract_signing_date": "2025-03-15",
    "contract_duration": "12 месеци",
    "contracting_entity_category": "Централна влада",
    "procurement_holder": "Example Ministry",
    "bureau_delivery_date": "2025-02-28"
  }'
```

### Search with Filters
```bash
curl -X POST http://localhost:8000/api/tenders/search \
  -H "Content-Type: application/json" \
  -d '{
    "procedure_type": "Отворена постапка",
    "contracting_entity_category": "Централна влада",
    "page": 1,
    "page_size": 20
  }'
```

## Files Modified

| File | Purpose | Lines Changed |
|------|---------|---------------|
| `models.py` | SQLAlchemy ORM | +7 lines (57-63) |
| `schemas.py` | Pydantic validation | +18 lines |
| `api/tenders.py` | API filters | +9 lines (150-158) |

## Files Created

| File | Purpose |
|------|---------|
| `alembic/versions/20251124_add_missing_tender_fields.py` | Database migration |
| `migrations/add_missing_tender_fields.sql` | Direct SQL migration |
| `verify_schema_update.sh` | Verification script |
| `test_new_fields.py` | Test suite |
| `SCHEMA_UPDATE_README.md` | Full documentation |
| `DEPLOYMENT_COMMANDS.sh` | Interactive deployment |
| `QUICK_REFERENCE.md` | This file |

## SQL Quick Check

```sql
-- Check columns exist
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'tenders'
AND column_name IN (
    'procedure_type',
    'contract_signing_date',
    'contract_duration',
    'contracting_entity_category',
    'procurement_holder',
    'bureau_delivery_date'
);

-- Check indexes
SELECT indexname FROM pg_indexes
WHERE tablename = 'tenders'
AND indexname LIKE 'idx_tenders_%';

-- Sample data
SELECT
    procedure_type,
    contract_signing_date,
    contracting_entity_category
FROM tenders
LIMIT 5;
```

## Common Commands

```bash
# Set database URL
export DATABASE_URL='postgresql://user:pass@host:port/dbname'

# Check current migration
cd /Users/tamsar/Downloads/nabavkidata/backend && alembic current

# Apply migration
cd /Users/tamsar/Downloads/nabavkidata/backend && alembic upgrade head

# Rollback migration
cd /Users/tamsar/Downloads/nabavkidata/backend && alembic downgrade -1

# Verify schema
cd /Users/tamsar/Downloads/nabavkidata/backend && ./verify_schema_update.sh

# Run tests
cd /Users/tamsar/Downloads/nabavkidata/backend && python3 test_new_fields.py

# Interactive deployment
cd /Users/tamsar/Downloads/nabavkidata/backend && ./DEPLOYMENT_COMMANDS.sh
```

## Troubleshooting

### Migration fails
```bash
# Check current state
alembic current

# Check database connection
psql $DATABASE_URL -c "SELECT 1;"

# Review migration history
alembic history --verbose
```

### Columns not visible
```bash
# Refresh database schema
psql $DATABASE_URL -c "\d+ tenders"

# Check if migration applied
alembic current
```

### API errors
```bash
# Restart backend server
# Check schemas are imported correctly
python3 -c "from schemas import TenderBase; print(TenderBase.__fields__.keys())"
```

## Support Files

- **Full Documentation:** `/Users/tamsar/Downloads/nabavkidata/backend/SCHEMA_UPDATE_README.md`
- **Summary:** `/Users/tamsar/Downloads/nabavkidata/SCHEMA_UPGRADE_SUMMARY.md`
- **Migration:** `/Users/tamsar/Downloads/nabavkidata/backend/alembic/versions/20251124_add_missing_tender_fields.py`
- **Tests:** `/Users/tamsar/Downloads/nabavkidata/backend/test_new_fields.py`

---

**Created:** 2025-11-24
**Agent:** D - Database Model & Schema Upgrade Engineer
**Status:** Ready for Deployment
