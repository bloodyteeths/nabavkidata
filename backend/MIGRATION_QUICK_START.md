# Migration Quick Start Guide

## Overview
This migration creates **all 22 missing tables** identified in the database audit.

---

## Quick Commands

### 1. Validate Migration
```bash
cd /Users/tamsar/Downloads/nabavkidata/backend
python3 validate_migration.py
```

**Expected Output:**
```
✅ VALIDATION PASSED: All required tables are covered!
Coverage:
  ✅ 22/22 audit-required tables
  ➕ 9 additional supporting tables
  📊 31 total tables in migration
```

---

### 2. Check Current Status
```bash
./run_migration.sh check
```

**Shows:**
- Current migration revision
- Migration history

---

### 3. Run Migration
```bash
# Set database connection (if not in environment)
export DATABASE_URL="postgresql://user:password@host:port/nabavkidata"

# Run migration with interactive prompt
./run_migration.sh upgrade

# OR run directly with alembic
alembic upgrade head
```

---

### 4. Verify Tables Created
```bash
psql $DATABASE_URL -c "\dt"
```

**Expected: 31 tables total**

---

### 5. Rollback (if needed)
```bash
./run_migration.sh downgrade
```

⚠️ **WARNING:** This deletes all data in migrated tables!

---

## Migration Files

| File | Purpose |
|------|---------|
| `alembic/versions/20251123_153004_*.py` | Fraud prevention tables (previous) |
| `alembic/versions/20251123_220000_*.py` | **Main migration (NEW)** |
| `alembic/env.py` | Alembic environment config |
| `alembic.ini` | Alembic settings |
| `run_migration.sh` | Helper script |
| `validate_migration.py` | Validation tool |

---

## Tables Created (22 Required + 9 Supporting)

### ✅ Required from Audit (22)
1. admin_audit_log
2. admin_settings
3. analysis_history
4. api_keys
5. billing_events
6. cpv_codes
7. entity_categories
8. fraud_events
9. message_threads
10. messages
11. notifications
12. personalization_settings
13. query_history
14. rate_limits *(from previous migration)*
15. refresh_tokens
16. saved_searches
17. subscription_usage
18. subscriptions
19. tender_documents
20. tender_entity_link
21. tenders
22. user_preferences

### ➕ Supporting Tables (9)
- users
- organizations
- documents *(alias for tender_documents)*
- embeddings
- alerts
- usage_tracking
- audit_log
- system_config
- fraud_detection *(from previous migration)*

---

## Post-Migration Tasks

### 1. Convert Vector Column (Important!)
```sql
-- Install pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Convert embeddings.vector to pgvector type
ALTER TABLE embeddings
ALTER COLUMN vector TYPE vector(1536)
USING vector::vector(1536);

-- Create vector index for fast similarity search
CREATE INDEX idx_embeddings_vector ON embeddings
USING ivfflat (vector vector_cosine_ops)
WITH (lists = 100);
```

### 2. Import CPV Codes
```bash
# Run CPV code import script (if available)
python scripts/import_cpv_codes.py
```

### 3. Add System Configuration
```sql
INSERT INTO system_config (config_key, config_value) VALUES
    ('embedding_model', 'text-embedding-004'),
    ('default_llm', 'gemini-pro'),
    ('free_tier_query_limit_daily', '5'),
    ('standard_tier_query_limit_monthly', '100'),
    ('pro_tier_query_limit_monthly', '500'),
    ('enterprise_tier_query_limit_monthly', '-1')
ON CONFLICT (config_key) DO NOTHING;
```

---

## Troubleshooting

### Error: "relation already exists"
**Solution:** Some tables may already exist. Check with:
```bash
alembic current
```

If stuck, you may need to:
```bash
alembic stamp head  # Mark current state as migrated
```

### Error: "could not connect to database"
**Solution:** Check DATABASE_URL:
```bash
echo $DATABASE_URL
# Should be: postgresql://user:pass@host:port/dbname
```

### Error: "No module named 'alembic'"
**Solution:** Install dependencies:
```bash
pip install alembic sqlalchemy psycopg2-binary
```

---

## Verification Queries

### Check All Tables Exist
```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'admin_audit_log', 'admin_settings', 'analysis_history',
    'api_keys', 'billing_events', 'cpv_codes', 'entity_categories',
    'fraud_events', 'message_threads', 'messages', 'notifications',
    'personalization_settings', 'query_history', 'rate_limits',
    'refresh_tokens', 'saved_searches', 'subscription_usage',
    'subscriptions', 'tender_documents', 'tender_entity_link',
    'tenders', 'user_preferences'
  )
ORDER BY table_name;
```

**Expected:** 22 rows

### Check Foreign Keys
```sql
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name;
```

### Check Indexes
```sql
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

**Expected:** 85+ indexes

---

## Migration Status

✅ **All 22 audit-required tables covered**
✅ **Migration syntax validated**
✅ **Foreign keys and indexes defined**
✅ **Downgrade function implemented**
✅ **Ready for production**

---

## Support

For detailed information, see:
- **MIGRATION_SUMMARY.md** - Full documentation
- **alembic/versions/20251123_220000_*.py** - Migration source code

---

**Last Updated:** 2025-11-23
**Migration ID:** 20251123_220000
**Status:** Ready for execution
