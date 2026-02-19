# E-Pazar Embeddings Implementation Summary

## Overview
Created script to generate vector embeddings for 900 e-Pazar tenders that currently have no embeddings.

## Files Created

### 1. `/Users/tamsar/Downloads/nabavkidata/scraper/embed_epazar.py`
Main script to generate embeddings for e-Pazar tenders.

**Key Features:**
- Fetches e-Pazar tenders without embeddings
- Builds searchable text from tender fields + aggregated items
- Generates 768-dim embeddings using BAAI/bge-base-en-v1.5
- Stores with `tender_id` = `'epazar_' || tender_id` prefix
- Async DB writes for performance
- Expected rate: 50-100 embeddings/minute

**Text Construction:**
```
epazar_{tender_id} | {title} | {description} | {contracting_authority} |
{procedure_type} | {category} | CPV: {cpv_code} | {aggregated_items}
```

**Usage:**
```bash
# Process all 900 tenders
python3 embed_epazar.py

# Custom batch size
python3 embed_epazar.py --batch-size 100

# Limit processing
python3 embed_epazar.py --limit 500
```

### 2. `/Users/tamsar/Downloads/nabavkidata/scraper/test_epazar_embedding.py`
Test script to preview how text is constructed for embeddings.

**Usage:**
```bash
python3 test_epazar_embedding.py
```

**Example Output:**
```
Tender ID: EPAZAR-774
Embedding ID: epazar_EPAZAR-774
Text length: 481 chars
Text preview:
epazar_EPAZAR-774 | средства за хигиена | Апелационен суд Скопје |
Стоки | epazar_active | Сјај за машинско миење на садови,
Вреќи за отпад, Тоалетна хартија - ролна...
```

### 3. `/Users/tamsar/Downloads/nabavkidata/scraper/check_epazar_embeddings.sql`
SQL queries to validate embedding status before/after running the script.

**Usage:**
```bash
psql -h nabavkidata-db... -U nabavki_user -d nabavkidata -f check_epazar_embeddings.sql
```

### 4. `/Users/tamsar/Downloads/nabavkidata/scraper/EPAZAR_EMBEDDING_README.md`
Complete documentation with examples, database schema, and troubleshooting.

## Database Structure

### Input Tables
1. **epazar_tenders** (900 records)
   - tender_id (PK)
   - title, description
   - contracting_authority
   - procedure_type, category, cpv_code

2. **epazar_items** (joined)
   - tender_id (FK)
   - item_name, item_description

### Output Table
**embeddings**
- tender_id: `'epazar_' || tender_id` (e.g., `epazar_EPAZAR-774`)
- doc_id: NULL (tender-level, not document)
- chunk_text: First 500 chars of constructed text
- chunk_index: 0
- vector: 768-dimensional embedding
- metadata: JSON with source, contracting_authority, category, procedure_type

## Current Status (Validated)
```
Total e-Pazar tenders:               900
e-Pazar tenders WITH embeddings:     0
e-Pazar tenders WITHOUT embeddings:  900
Total e-Pazar embeddings:            0
```

## Execution Plan

### Local Testing (Optional)
```bash
cd /Users/tamsar/Downloads/nabavkidata/scraper

# Preview text construction
python3 test_epazar_embedding.py

# Test with small batch
python3 embed_epazar.py --limit 10
```

### Server Deployment
```bash
# SSH to server
ssh -i ~/.ssh/nabavki-key.pem ubuntu@18.197.185.30

# Navigate to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run the script
python3 embed_epazar.py

# Or with screen for long-running process
screen -S epazar_embed
python3 embed_epazar.py
# Ctrl+A, D to detach
```

### Monitoring Progress
```bash
# Watch logs
tail -f logs/embed_epazar.log

# Check database
psql -h ... -f check_epazar_embeddings.sql
```

## Expected Timeline
- **900 tenders** at **50-100/min** = **9-18 minutes**
- With async DB writes and 8-thread embedding

## Post-Execution Validation

### 1. Check counts
```sql
SELECT COUNT(*) FROM embeddings WHERE tender_id LIKE 'epazar_%';
-- Expected: 900
```

### 2. Check sample embeddings
```sql
SELECT
    tender_id,
    LEFT(chunk_text, 100),
    metadata->>'contracting_authority',
    created_at
FROM embeddings
WHERE tender_id LIKE 'epazar_%'
ORDER BY created_at DESC
LIMIT 10;
```

### 3. Test semantic search
```sql
-- Find similar tenders to a query embedding
SELECT
    tender_id,
    chunk_text,
    metadata->>'contracting_authority'
FROM embeddings
WHERE tender_id LIKE 'epazar_%'
ORDER BY vector <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
```

## Integration with Existing System

The e-Pazar embeddings will work with the existing RAG system:

1. **Search queries** can now match e-Pazar tenders
2. **Tender ID prefix** (`epazar_`) distinguishes from regular tenders
3. **Metadata filtering** allows filtering by:
   - source = 'epazar'
   - contracting_authority
   - category
   - procedure_type

## Comparison with Regular Tenders

| Feature | Regular Tenders | e-Pazar Tenders |
|---------|----------------|-----------------|
| ID Format | `12345/2024` | `epazar_EPAZAR-774` |
| Model | BAAI/bge-base-en-v1.5 | BAAI/bge-base-en-v1.5 |
| Vector Dims | 768 | 768 |
| Source Data | tenders.raw_data_json | epazar_tenders + epazar_items |
| Text Fields | tender_id, title, description, procuring_entity, winner, cpv_code | tender_id, title, description, contracting_authority, procedure_type, category, cpv_code, items |

## Dependencies
- psycopg2
- fastembed
- Python 3.8+

## Notes
- Script is idempotent (ON CONFLICT DO NOTHING)
- Safe to re-run if interrupted
- Uses same vector index as regular tenders
- Macedonian language text (Cyrillic script)
