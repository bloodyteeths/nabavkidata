# Database DSN Format Fix - Complete

## Problem Identified

**Error:** `asyncpg.exceptions.InvalidCatalogNameError: database "postgresql+asyncpg" does not exist`

**Root Cause:**
- Backend uses SQLAlchemy with asyncpg driver: `postgresql+asyncpg://...` (SQLAlchemy syntax)
- RAG modules use raw asyncpg: `await asyncpg.connect(database_url)` (NOT SQLAlchemy)
- asyncpg library does NOT understand the `+asyncpg` driver suffix
- When asyncpg sees `postgresql+asyncpg://...`, it incorrectly parses `postgresql+asyncpg` as the database name!

## Solution Applied

Added URL format conversion in all classes that use `asyncpg.connect()`:

```python
# Convert SQLAlchemy URL format to asyncpg format
# asyncpg doesn't understand postgresql+asyncpg://
self.database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
```

This conversion:
- Strips the SQLAlchemy-specific `+asyncpg` driver suffix
- Maintains compatibility with both formats (already `postgresql://` URLs pass through unchanged)
- Ensures asyncpg receives the correct connection string format

## Files Modified

### 1. `/ai/embeddings.py`
**Class:** `VectorStore.__init__()`
- **Line:** 348-351
- **Change:** Added URL conversion before storing `self.database_url`

### 2. `/ai/rag_query.py` 
**Classes:**
- `PersonalizationScorer.__init__()` (Lines 289-292)
- `ConversationManager.__init__()` (Lines 688-692)
- **Change:** Added URL conversion in both classes before storing `self.database_url`

### 3. `/ai/embeddings/pipeline.py`
**Class:** `AutoEmbeddingPipeline.__init__()`
- **Line:** 39-41
- **Change:** Added URL conversion before storing `self.database_url`

## Verification

All asyncpg.connect() calls now use converted URLs:
- `ai/embeddings.py:357` - Uses `self.database_url` (converted in __init__)
- `ai/rag_query.py:298` - Uses `self.database_url` (converted in __init__)
- `ai/rag_query.py:698` - Uses `self.database_url` (converted in __init__)
- `ai/embeddings/pipeline.py:49` - Uses `self.database_url` (converted in __init__)

## Testing

Conversion handles both URL formats correctly:
- `postgresql+asyncpg://user:pass@host/db` → `postgresql://user:pass@host/db` ✓
- `postgresql://user:pass@host/db` → `postgresql://user:pass@host/db` ✓ (unchanged)

## Impact

This fix ensures:
1. RAG pipeline can connect to PostgreSQL using the same DATABASE_URL as backend
2. No need for separate environment variables
3. Consistent configuration across all application components
4. Proper connection string format for asyncpg library

## Next Steps

The DATABASE_URL environment variable should be set as:
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host:port/database"
```

The RAG modules will automatically convert it to the correct format for asyncpg.
