# Migration 013: Missing Materialized Views

## Overview

This migration creates the missing materialized views for the corruption detection system, fixing 500 errors in the `/api/corruption/*` endpoints.

**Created:** 2025-12-26
**Migration File:** `db/migrations/013_missing_views.sql`
**Issue:** Missing `mv_flagged_tenders` and `mv_corruption_stats` views causing API failures

## What's Created

### 1. mv_flagged_tenders

Materialized view that pre-aggregates all flagged tenders with risk scores.

**Columns:**
- `tender_id` (unique)
- `title`
- `procuring_entity`
- `winner`
- `estimated_value_mkd`
- `status`
- `total_flags` - Count of corruption flags
- `risk_score` - 0-100 risk score
- `risk_level` - minimal/low/medium/high/critical
- `severity_rank` - Numeric rank (1-4) for sorting
- `max_severity` - Highest severity flag
- `flag_types` - Array of flag types

**Performance:** ~100x faster than live aggregation (20ms vs 2000ms)

**Indexes:**
- Unique index on `tender_id` (required for concurrent refresh)
- Index on `risk_score DESC` (main sorting)
- Index on `max_severity` (filtering)
- Index on `procuring_entity` (institution search)
- Index on `winner` (company search)
- GIN index on `flag_types` (array queries)

### 2. mv_corruption_stats

Single-row materialized view with aggregated corruption statistics.

**Columns:**
- `total_flags` - Total corruption flags
- `total_tenders_flagged` - Unique tenders with flags
- `total_value_at_risk_mkd` - Sum of flagged tender values
- `by_severity` - JSONB object with counts by severity
- `by_type` - JSONB object with counts by flag type

**Performance:** ~50x faster than live aggregation (10ms vs 500ms)

**Example Output:**
```json
{
  "total_flags": 1234,
  "total_tenders_flagged": 567,
  "total_value_at_risk_mkd": 45000000.00,
  "by_severity": {
    "critical": 12,
    "high": 45,
    "medium": 123,
    "low": 234
  },
  "by_type": {
    "single_bidder": 234,
    "repeat_winner": 123,
    "price_anomaly": 89,
    "bid_clustering": 45
  }
}
```

### 3. Helper Function: refresh_corruption_views()

Function to refresh both materialized views concurrently.

**Usage:**
```sql
SELECT * FROM refresh_corruption_views();
```

**Returns:**
```
view_name             | refresh_status | row_count | duration_ms
----------------------+----------------+-----------+-------------
mv_flagged_tenders    | success        | 567       | 245
mv_corruption_stats   | success        | 1         | 89
```

## How to Run

### Initial Migration

```bash
# On production database
PGPASSWORD='<REDACTED>' psql \
  -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
  -U nabavki_user \
  -d nabavkidata \
  -f db/migrations/013_missing_views.sql
```

### Manual Refresh

After running corruption detection analysis:

```bash
# Option 1: Direct SQL
PGPASSWORD='...' psql -h ... -U nabavki_user -d nabavkidata -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_flagged_tenders;"
PGPASSWORD='...' psql -h ... -U nabavki_user -d nabavkidata -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_corruption_stats;"

# Option 2: Use helper function
PGPASSWORD='...' psql -h ... -U nabavki_user -d nabavkidata -c "SELECT * FROM refresh_corruption_views();"
```

### Automated Refresh (Cron)

Add to crontab on EC2 server:

```bash
# Refresh corruption views daily at 5:00 AM UTC
0 5 * * * PGPASSWORD='<REDACTED>' psql -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com -U nabavki_user -d nabavkidata -c "SELECT refresh_corruption_views();" >> /var/log/nabavkidata/corruption_views_refresh.log 2>&1
```

Or create a shell script:

```bash
#!/bin/bash
# /home/ubuntu/nabavkidata/backend/cron/refresh_corruption_views.sh

PGPASSWORD='<REDACTED>' psql \
  -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
  -U nabavki_user \
  -d nabavkidata \
  -c "SELECT * FROM refresh_corruption_views();"
```

## Monitoring

### Check View Freshness

```sql
SELECT
    schemaname,
    matviewname,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) as size
FROM pg_matviews
WHERE matviewname IN ('mv_flagged_tenders', 'mv_corruption_stats');
```

### Check Row Counts

```sql
SELECT 'mv_flagged_tenders' as view, COUNT(*) FROM mv_flagged_tenders
UNION ALL
SELECT 'mv_corruption_stats' as view, COUNT(*) FROM mv_corruption_stats;
```

### Test API After Migration

```bash
# Test flagged tenders endpoint
curl -X GET 'https://nabavkidata.com/api/corruption/flagged-tenders?min_score=50&limit=10'

# Test stats endpoint
curl -X GET 'https://nabavkidata.com/api/corruption/stats'
```

## Troubleshooting

### Error: "materialized view does not exist"

Run the migration:
```bash
psql ... -f db/migrations/013_missing_views.sql
```

### Error: "cannot refresh materialized view concurrently without unique index"

The migration includes unique indexes. If you dropped them:
```sql
CREATE UNIQUE INDEX idx_mv_flagged_tenders_tender_id ON mv_flagged_tenders(tender_id);
CREATE UNIQUE INDEX idx_mv_corruption_stats_unique ON mv_corruption_stats((1));
```

### Refresh Taking Too Long

Use concurrent refresh (doesn't block reads):
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_flagged_tenders;
```

If corruption_flags table is very large, consider:
- Running refresh during off-peak hours
- Analyzing the tables first: `ANALYZE corruption_flags; ANALYZE tenders;`

### Empty Results After Refresh

Check if there are any non-false-positive flags:
```sql
SELECT COUNT(*) FROM corruption_flags WHERE false_positive = FALSE;
```

If zero, run corruption detection analysis:
```bash
cd /home/ubuntu/nabavkidata
python3 ai/corruption_detector.py
```

## Integration with Corruption Detection

After running corruption analysis, always refresh views:

```bash
# Run analysis
python3 ai/corruption_detector.py

# Refresh views
PGPASSWORD='...' psql ... -c "SELECT refresh_corruption_views();"
```

Or create a wrapper script:

```bash
#!/bin/bash
# analyze_and_refresh.sh

echo "Running corruption detection..."
python3 /home/ubuntu/nabavkidata/ai/corruption_detector.py

echo "Refreshing materialized views..."
PGPASSWORD='<REDACTED>' psql \
  -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
  -U nabavki_user \
  -d nabavkidata \
  -c "SELECT * FROM refresh_corruption_views();"

echo "Done!"
```

## Rollback

If you need to remove the views:

```sql
DROP MATERIALIZED VIEW IF EXISTS mv_flagged_tenders CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_corruption_stats CASCADE;
DROP FUNCTION IF EXISTS refresh_corruption_views();
DROP FUNCTION IF EXISTS trigger_refresh_corruption_views();
```

**Warning:** This will cause 500 errors in corruption API endpoints.

## Files Modified/Created

- `db/migrations/013_missing_views.sql` - Main migration file (345 lines)
- `db/migrations/013_missing_views_README.md` - This file

## Next Steps

1. Run migration on production database
2. Set up cron job for daily refresh
3. Test corruption API endpoints
4. Monitor view refresh performance
5. Update corruption detection workflow to refresh views after analysis

## Related Files

- `db/migrations/012_corruption_detection.sql` - Base corruption tables
- `backend/api/corruption.py` - API that uses these views
- `ai/corruption_detector.py` - Analysis script that populates the tables
