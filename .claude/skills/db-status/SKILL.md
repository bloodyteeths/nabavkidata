---
name: db-status
description: Check database status for nabavkidata - tender counts by year, document extraction progress, embedding counts, scraper progress. Use when user asks about data status, counts, or progress.
allowed-tools: Bash
---

# Database Status Skill

Quick queries to check system health and data status.

## Connection
```bash
ssh ubuntu@46.224.89.197 "PGPASSWORD='N4bavk1H3tzn3r2026!Secure' psql -h localhost -U nabavki_user -d nabavkidata"
```

Or directly on server:
```bash
PGPASSWORD='N4bavk1H3tzn3r2026!Secure' psql -h localhost -U nabavki_user -d nabavkidata
```

## Common Queries

### Tender counts by year
```sql
SELECT SUBSTRING(tender_id FROM '[0-9]+/([0-9]+)') as year, COUNT(*)
FROM tenders GROUP BY year ORDER BY year DESC;
```

### Document extraction status
```sql
SELECT extraction_status, COUNT(*) FROM documents GROUP BY extraction_status;
```

### Embedding counts
```sql
SELECT COUNT(*) FROM embeddings;
```

### Documents needing embeddings
```sql
SELECT COUNT(*) FROM documents d
WHERE content_text IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id);
```

### Tender status breakdown
```sql
SELECT status, COUNT(*) FROM tenders GROUP BY status ORDER BY count DESC;
```

### Recent scraper activity
```sql
SELECT DATE(created_at) as date, COUNT(*)
FROM tenders
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at) ORDER BY date DESC;
```

### E-Pazar status
```sql
SELECT status, COUNT(*) FROM epazar_tenders GROUP BY status;
```

### Corruption flags summary
```sql
SELECT flag_type, COUNT(*), SUM(CASE WHEN false_positive THEN 1 ELSE 0 END) as false_positives
FROM corruption_flags GROUP BY flag_type;
```
