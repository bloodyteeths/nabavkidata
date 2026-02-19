# E-Pazar Embeddings Generator

## Overview
Script to generate vector embeddings for e-Pazar tenders and store them in the `embeddings` table for semantic search.

## Files
- `embed_epazar.py` - Main script to generate embeddings
- `test_epazar_embedding.py` - Test script to preview how text is built

## What It Does

1. **Fetches e-Pazar tenders** without embeddings (currently ~900 tenders)
2. **Builds searchable text** from:
   - Tender ID (with `epazar_` prefix)
   - Title
   - Description
   - Contracting authority
   - Procedure type
   - Category
   - CPV code
   - Aggregated item names and descriptions
3. **Generates embeddings** using FastEmbed (BAAI/bge-base-en-v1.5)
4. **Stores in embeddings table** with:
   - `tender_id` = `'epazar_' || tender_id` (e.g., `epazar_EPAZAR-774`)
   - `doc_id` = NULL (tender-level embedding, not document)
   - `chunk_index` = 0
   - `metadata` = JSON with source, contracting_authority, category, procedure_type

## Usage

### Basic usage (process all e-Pazar tenders)
```bash
cd /home/ubuntu/nabavkidata/scraper
python3 embed_epazar.py
```

### With options
```bash
# Custom batch size
python3 embed_epazar.py --batch-size 100

# Limit number of tenders
python3 embed_epazar.py --limit 100

# Both
python3 embed_epazar.py --batch-size 50 --limit 500
```

### Test text generation (preview)
```bash
python3 test_epazar_embedding.py
```

## Parameters
- `--batch-size` - Number of texts to embed at once (default: 50)
- `--limit` - Maximum number of tenders to process (default: 10000)

## Performance
- Expected rate: 50-100 embeddings/minute
- For 900 tenders: ~10-20 minutes
- Uses 8 threads for embedding generation
- Async DB writes to avoid blocking

## Database Schema

### Input: `epazar_tenders` table
- `tender_id` (PK)
- `title`
- `description`
- `contracting_authority`
- `procedure_type`
- `category`
- `cpv_code`

### Input: `epazar_items` table (joined)
- `tender_id` (FK)
- `item_name`
- `item_description`

### Output: `embeddings` table
- `embed_id` (PK, UUID)
- `tender_id` = `'epazar_' || tender_id`
- `doc_id` = NULL
- `chunk_text` (first 500 chars)
- `chunk_index` = 0
- `vector` (768-dim)
- `metadata` (JSONB)

## Example Text Construction

For tender EPAZAR-774:
```
epazar_EPAZAR-774 | средства за хигиена | Апелационен суд Скопје | Стоки | epazar_active | Сјај за машинско миење на садови, Вреќи за отпад, Тоалетна хартија - ролна...
```

## Checking Progress

### Count tenders without embeddings
```sql
SELECT COUNT(*)
FROM epazar_tenders e
WHERE NOT EXISTS (
    SELECT 1 FROM embeddings emb
    WHERE emb.tender_id = 'epazar_' || e.tender_id
);
```

### Count epazar embeddings
```sql
SELECT COUNT(*)
FROM embeddings
WHERE tender_id LIKE 'epazar_%';
```

### View sample epazar embeddings
```sql
SELECT
    tender_id,
    LEFT(chunk_text, 100) as preview,
    metadata->>'contracting_authority' as authority,
    created_at
FROM embeddings
WHERE tender_id LIKE 'epazar_%'
ORDER BY created_at DESC
LIMIT 5;
```

## Logs
- Output: `logs/embed_epazar.log`
- Shows progress, rate, ETA, and errors

## Notes
- Uses same model as regular tenders: BAAI/bge-base-en-v1.5 (768 dimensions)
- Stores with `epazar_` prefix to distinguish from regular tenders
- Skip logic: If embedding already exists for a tender, it's skipped
- Handles tenders with no items (uses tender metadata only)
- Thread-safe async DB writes for performance
