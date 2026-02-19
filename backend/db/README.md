# Database Setup - nabavkidata.com

## Prerequisites

- PostgreSQL 14 or higher
- pgvector extension
- pg_trgm extension (for full-text search)

## Installation

### 1. Install PostgreSQL

**macOS**:
```bash
brew install postgresql@16
brew services start postgresql@16
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install postgresql-16 postgresql-contrib
sudo systemctl start postgresql
```

### 2. Install pgvector Extension

```bash
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### 3. Create Database

```bash
createdb nabavkidata
```

### 4. Enable Extensions

```bash
psql nabavkidata -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql nabavkidata -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
psql nabavkidata -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
```

### 5. Run Migrations

```bash
psql nabavkidata < db/migrations/001_initial_schema.sql
```

### 6. Load Seed Data (Development Only)

```bash
psql nabavkidata < db/seed_data.sql
```

## Verification

```bash
psql nabavkidata -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
```

Expected output: 12 tables (users, organizations, subscriptions, tenders, documents, embeddings, query_history, alerts, notifications, usage_tracking, audit_log, system_config)

## Connection String

**Development**:
```
postgresql://localhost:5432/nabavkidata
```

**Production** (use environment variable):
```bash
export DATABASE_URL="postgresql://user:password@host:5432/nabavkidata"
```

## Schema Version

Check current schema version:
```bash
psql nabavkidata -c "SELECT config_value FROM system_config WHERE config_key='schema_version';"
```

## Rollback

To rollback the schema:
```bash
psql nabavkidata < db/migrations/001_rollback.sql
```

## Backup

```bash
pg_dump nabavkidata > backup_$(date +%Y%m%d).sql
```

## Restore

```bash
psql nabavkidata < backup_YYYYMMDD.sql
```

## Common Queries

### Count tenders by status
```sql
SELECT status, COUNT(*) FROM tenders GROUP BY status;
```

### Check embeddings
```sql
SELECT COUNT(*) FROM embeddings;
```

### User subscription tiers
```sql
SELECT subscription_tier, COUNT(*) FROM users GROUP BY subscription_tier;
```
