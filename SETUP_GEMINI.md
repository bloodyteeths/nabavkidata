# Gemini Migration Setup Guide

## Current Status

✅ **Code Migration:** Complete
✅ **Dependencies:** Installed
🔴 **Database Migration:** Pending
🔴 **API Key:** Needs configuration
🔴 **Re-embedding:** Required

---

## Quick Start (3 Steps)

### Step 1: Set Your Gemini API Key

1. Get your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

2. Update `.env.prod`:
   ```bash
   # Change this line:
   GEMINI_API_KEY=CHANGE_THIS_TO_YOUR_GEMINI_API_KEY

   # To your actual key:
   GEMINI_API_KEY=AIza... (your key here)
   ```

3. Verify it's set:
   ```bash
   grep GEMINI_API_KEY .env.prod
   ```

### Step 2: Run Database Migration

```bash
# Option A: Automatic (recommended)
./scripts/run_migration.sh

# Option B: Manual
psql $DATABASE_URL -f db/migrations/migrate_to_gemini_768.sql
```

**⚠️ WARNING:** This will truncate existing embeddings (they're incompatible).

### Step 3: Re-embed All Documents

```bash
python3 scripts/reembed_documents.py
```

This will regenerate all embeddings using Gemini (768 dimensions).

---

## Verification

### Test Gemini Connection
```bash
python3 scripts/verify_gemini.py
```

Should output:
```
✅ GEMINI_API_KEY: ********************xxx
✅ Generated embedding
✅ Vector dimension: 768
✅ All tests passed!
```

### Check Database
```sql
-- Check vector dimensions
SELECT array_length(vector::float[], 1) as dimension
FROM embeddings
LIMIT 1;
-- Should return: 768

-- Check embedding count
SELECT COUNT(*) FROM embeddings;
```

### Test RAG Query
```bash
cd backend
uvicorn main:app --reload
```

Then visit: `http://localhost:8000/rag/health`

Should return:
```json
{
  "status": "healthy",
  "rag_enabled": true,
  "gemini_configured": true,
  "model": "gemini-1.5-flash"
}
```

---

## What Changed

### Before (OpenAI)
- Model: GPT-4 + text-embedding-ada-002
- Dimensions: 1536
- Cost: ~$0.0001/1K tokens
- Library: `openai`, `tiktoken`

### After (Gemini)
- Model: Gemini 1.5 Flash + text-embedding-004
- Dimensions: 768
- Cost: ~$0.00002/1K tokens (80% cheaper)
- Library: `google-generativeai`

---

## Scripts Reference

### `scripts/verify_gemini.py`
Tests Gemini API connection and embedding generation.

```bash
python3 scripts/verify_gemini.py
```

### `scripts/run_migration.sh`
Runs database migration (vector dimension update).

```bash
./scripts/run_migration.sh
```

### `scripts/reembed_documents.py`
Re-embeds all documents with Gemini.

```bash
python3 scripts/reembed_documents.py
```

---

## Troubleshooting

### Error: "GEMINI_API_KEY not set"
**Solution:** Update `.env.prod` with your actual API key.

### Error: "Vector dimension mismatch"
**Solution:** Run the database migration:
```bash
./scripts/run_migration.sh
```

### Error: "Module 'google.generativeai' not found"
**Solution:** Install dependencies:
```bash
pip3 install google-generativeai
```

### Error: "No documents to embed"
**Solution:** Check if documents table has data:
```sql
SELECT COUNT(*) FROM documents WHERE content_text IS NOT NULL;
```

---

## Rollback (If Needed)

If you need to rollback to OpenAI:

```bash
# 1. Checkout old code
git stash
git checkout HEAD~1

# 2. Restore old dependencies
pip3 install -r backend/requirements.txt

# 3. Restore database (requires backup)
# psql $DATABASE_URL < backup.sql
```

---

## Production Deployment

### 1. Update Environment Variables

In your production environment (AWS, Vercel, etc.), set:

```bash
GEMINI_API_KEY=your-actual-key
GEMINI_MODEL=gemini-1.5-flash
GEMINI_FALLBACK_MODEL=gemini-1.5-pro
EMBEDDING_MODEL=text-embedding-004
VECTOR_DIMENSION=768
```

### 2. Run Migration

On your production database:
```bash
psql $PROD_DATABASE_URL -f db/migrations/migrate_to_gemini_768.sql
```

### 3. Deploy Code

```bash
# Deploy backend
vercel deploy --prod

# Or using your deployment method
git push production main
```

### 4. Re-embed Documents

```bash
# On production server
python3 scripts/reembed_documents.py
```

### 5. Monitor

- Check `/rag/health` endpoint
- Monitor Gemini API usage
- Track embedding generation times
- Verify RAG answer quality

---

## Cost Comparison

| Operation | OpenAI | Gemini | Savings |
|-----------|--------|--------|---------|
| **Embeddings** (1M tokens) | $0.10 | $0.02 | 80% |
| **Generation** (1M tokens) | $10.00 | $0.35 | 96.5% |
| **Storage** (per vector) | 1536 floats | 768 floats | 50% |

**Estimated monthly savings:** $500-$2000 depending on usage.

---

## Support

- [Gemini API Docs](https://ai.google.dev/docs)
- [Migration Summary](GEMINI_MIGRATION_COMPLETE.md)
- [Issues](https://github.com/anthropics/claude-code/issues)

---

## Checklist

- [ ] Set GEMINI_API_KEY in .env.prod
- [ ] Run database migration
- [ ] Re-embed all documents
- [ ] Test Gemini connection
- [ ] Verify RAG queries work
- [ ] Deploy to production
- [ ] Monitor API usage

**Status:** Ready to deploy once API key is set! 🚀
