# Document AI Summarization Implementation

**Date:** 2025-12-02
**Phase:** 2.2 - Backend AI Document Summarization
**Status:** ✅ COMPLETE

---

## Overview

Implemented AI-powered document summarization for the `/api/documents/{doc_id}/content` endpoint using Google Gemini 2.0 Flash. This feature automatically extracts:
- Brief summaries in Macedonian (2-3 sentences)
- Key requirements from procurement documents
- Products/items mentioned with quantities

---

## Implementation Components

### 1. Database Schema Changes

**Migration File:** `/backend/alembic/versions/20251202_add_document_ai_fields.py`

**New Columns Added to `documents` table:**

| Column | Type | Purpose |
|--------|------|---------|
| `ai_summary` | TEXT | Cached AI-generated summary |
| `key_requirements` | JSONB | Array of extracted requirements |
| `items_mentioned` | JSONB | Array of products/items with quantities |
| `content_hash` | VARCHAR(64) | SHA-256 hash for cache invalidation |
| `ai_extracted_at` | TIMESTAMP | Last AI extraction timestamp |

**Index:** `idx_documents_content_hash` for fast cache lookups

**Manual Migration SQL:** `/backend/run_migration.sql`

```sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS key_requirements JSONB;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS items_mentioned JSONB;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_extracted_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
```

---

### 2. ORM Model Updates

**File:** `/backend/models.py` (Lines 119-124)

```python
# AI Extraction fields (Phase 2.2)
ai_summary = Column(Text)
key_requirements = Column(JSONB)
items_mentioned = Column(JSONB)
content_hash = Column(String(64))
ai_extracted_at = Column(DateTime)
```

---

### 3. Pydantic Schema Updates

**File:** `/backend/schemas.py`

**DocumentBase Schema** (Lines 156-159):
```python
# AI Extraction fields (Phase 2.2)
ai_summary: Optional[str] = None
key_requirements: Optional[List[str]] = None
items_mentioned: Optional[List[Dict[str, Any]]] = None
```

**DocumentContentResponse Schema** (Lines 197-200):
```python
# AI Extraction fields (Phase 2.2)
ai_summary: Optional[str] = None
key_requirements: Optional[List[str]] = None
items_mentioned: Optional[List[Dict[str, Any]]] = None
```

---

### 4. API Implementation

**File:** `/backend/api/documents.py`

#### Gemini Configuration (Lines 28-35)
```python
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = bool(os.getenv('GEMINI_API_KEY'))
    if GEMINI_AVAILABLE:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
except ImportError:
    GEMINI_AVAILABLE = False
```

#### Core Functions

**1. `summarize_document_with_ai(content_text: str)` (Lines 42-160)**
- Uses Gemini 2.0 Flash model
- Generates summaries in Macedonian
- Extracts key requirements (max 10)
- Identifies items with quantities (max 20)
- Temperature: 0.2 for consistency
- Max output tokens: 2000
- Context window: 8000 characters

**2. `compute_content_hash(content_text: str)` (Lines 163-167)**
- SHA-256 hash computation
- Used for cache invalidation

#### Enhanced Endpoint (Lines 273-406)

**URL:** `GET /api/documents/{doc_id}/content`

**Query Parameters:**
- `generate_ai_summary` (boolean, default: `true`) - Generate AI summary if not cached

**Response Structure:**
```json
{
  "doc_id": "uuid",
  "file_name": "Technical_Specifications.pdf",
  "file_type": "pdf",
  "content_text": "Full extracted document text...",
  "content_preview": "First 500 characters...",
  "word_count": 1234,
  "has_tables": true,
  "extraction_status": "completed",
  "file_url": "https://...",
  "tender_id": "12345/2025",
  "created_at": "2025-12-02T10:00:00Z",

  "ai_summary": "Овој документ опишува технички спецификации...",
  "key_requirements": [
    "ISO 13485 сертификација",
    "CE означување",
    "Валидна увозна лиценца"
  ],
  "items_mentioned": [
    {
      "name": "CT Scanner 64-слајса",
      "quantity": "2",
      "unit": "парчиња",
      "notes": "Со детектор од 0.5mm"
    }
  ]
}
```

---

## Key Features

### 1. Intelligent Caching
- Stores AI results in database
- Uses content hash to detect changes
- Only regenerates when:
  - No cached summary exists
  - Content has been modified (hash mismatch)
  - User explicitly requests regeneration

### 2. Smart Extraction
- **Summaries:** 2-3 sentences in Macedonian describing document purpose
- **Requirements:** Up to 10 most important procurement requirements
- **Items:** Products/services with quantities, units, and notes (max 20)

### 3. Error Handling
- Graceful degradation if AI unavailable
- Fallback messages in Macedonian
- Continues operation even if AI fails
- Non-blocking async calls

### 4. Performance Optimization
- Async/await for non-blocking operations
- Database caching reduces API costs
- Content truncation to 8000 chars
- Single database round-trip for updates

---

## Gemini Prompt Design

**Language:** Macedonian for summaries
**Temperature:** 0.2 (low for consistency)
**Max Tokens:** 2000
**Context:** First 8000 characters of document

**Prompt Structure:**
```
Анализирај го следниот документ од јавна набавка и обезбеди:

1. Кратко резиме (2-3 реченици на македонски јазик)
2. Список на клучни барања/услови (максимум 10 најважни)
3. Список на производи/услуги споменати (со количини)

Врати резултат во JSON формат: {...}
```

**Output Format:**
```json
{
  "summary": "Резиме на 2-3 реченици...",
  "key_requirements": ["Барање 1", "Барање 2"],
  "items_mentioned": [
    {
      "name": "Производ",
      "quantity": "10",
      "unit": "парчиња",
      "notes": "Белешка"
    }
  ]
}
```

---

## Configuration

**Environment Variables:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | - | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Model to use |

**Current Configuration:**
- API Key: `YOUR_GEMINI_API_KEY` (provided in task)
- Model: `gemini-2.0-flash` (configurable)

---

## Cost & Rate Limiting

**Estimated Costs (Gemini 2.0 Flash):**
- Input: ~$0.000015 per 1K tokens (8000 chars = ~2K tokens)
- Output: ~$0.000060 per 1K tokens (2000 tokens max)
- **Cost per document:** ~$0.00015 (15 hundredths of a cent)

**Caching Benefits:**
- First request: Calls Gemini (~$0.00015)
- Subsequent requests: Free (reads from database)
- Only regenerates when content changes

**Rate Limiting:**
- Gemini API: 60 requests/minute (free tier)
- With caching: Effectively unlimited for existing documents
- Async implementation prevents blocking

---

## Usage Examples

### Basic Request
```bash
curl -X GET "https://api.nabavkidata.com/api/documents/{doc_id}/content" \
  -H "Authorization: Bearer {token}"
```

### Disable AI Summary
```bash
curl -X GET "https://api.nabavkidata.com/api/documents/{doc_id}/content?generate_ai_summary=false" \
  -H "Authorization: Bearer {token}"
```

### Force Regeneration
Delete the cached summary in database, then request again:
```sql
UPDATE documents SET ai_summary = NULL, content_hash = NULL WHERE doc_id = '{doc_id}';
```

---

## Testing

### Manual Testing

1. **Test AI summarization:**
```bash
# Get document with AI summary
curl -X GET "http://localhost:8000/api/documents/{doc_id}/content" \
  -H "Authorization: Bearer {token}"
```

2. **Test caching:**
```bash
# First request - calls Gemini
# Second request - reads from cache (instant)
```

3. **Test cache invalidation:**
```sql
-- Update document content
UPDATE documents SET content_text = 'New content...' WHERE doc_id = '{doc_id}';

-- Next API call will regenerate summary
```

### Unit Tests (To Be Added)

```python
async def test_summarize_document():
    content = "Test procurement document content..."
    result = await summarize_document_with_ai(content)
    assert "summary" in result
    assert "key_requirements" in result
    assert "items_mentioned" in result

async def test_content_hash():
    hash1 = compute_content_hash("content")
    hash2 = compute_content_hash("content")
    assert hash1 == hash2

    hash3 = compute_content_hash("different")
    assert hash1 != hash3
```

---

## Deployment Checklist

- [x] Code implementation complete
- [x] Models updated
- [x] Schemas updated
- [x] API endpoint enhanced
- [ ] Database migration applied
- [ ] Environment variables configured
- [ ] Frontend integration tested
- [ ] Load testing completed
- [ ] Monitoring alerts configured

---

## Integration with Frontend

**Frontend Component:** `/frontend/components/tenders/DocumentViewer.tsx`

The frontend DocumentViewer component already supports displaying:
- `ai_summary` - Shows in highlighted card with sparkles icon
- `key_requirements` - Displays as bulleted list
- `items_mentioned` - Shows as colored badges

**API Client Method:** `/frontend/lib/api.ts`
```typescript
async getDocumentContent(docId: string) {
  const response = await fetch(`${API_URL}/documents/${docId}/content`);
  return response.json();
}
```

**No frontend changes needed** - Already implemented in Phase 2.3

---

## Monitoring & Observability

**Metrics to Track:**
- AI summary generation success rate
- Cache hit rate
- Average response time
- Gemini API errors
- Cost per month

**Logging:**
```python
print(f"AI document summarization failed: {e}")  # Line 154
print(f"Failed to generate AI summary: {e}")     # Line 388
```

**Recommended Improvements:**
- Add structured logging (JSON format)
- Track cache hit/miss rates
- Monitor Gemini API latency
- Alert on high error rates

---

## Known Limitations

1. **Content Length:** Only first 8000 characters analyzed
2. **Language:** Summaries only in Macedonian
3. **Document Types:** Works best with text-heavy documents (PDF, DOCX)
4. **Tables:** May not fully capture complex table data
5. **Images:** Cannot analyze image content

---

## Future Enhancements

1. **Batch Processing:** Summarize multiple documents in parallel
2. **Multi-language:** Support English summaries
3. **Longer Documents:** Implement chunking for documents >8000 chars
4. **Table Extraction:** Enhanced table parsing with structured output
5. **Background Jobs:** Queue AI processing for large documents
6. **User Feedback:** Allow users to rate/improve summaries
7. **Custom Prompts:** User-defined extraction templates

---

## Troubleshooting

### Issue: AI summary not generating

**Check:**
1. Is `GEMINI_API_KEY` set?
```bash
echo $GEMINI_API_KEY
```

2. Is document content available?
```sql
SELECT content_text FROM documents WHERE doc_id = '{doc_id}';
```

3. Check API logs for errors

### Issue: Summaries in wrong language

**Solution:** Verify Gemini prompt includes "на македонски јазик"

### Issue: High API costs

**Solution:**
- Verify caching is working (check `content_hash` column)
- Reduce context window size
- Switch to smaller model if needed

---

## References

- **Gemini API Docs:** https://ai.google.dev/docs
- **Gemini Pricing:** https://ai.google.dev/pricing
- **Project Roadmap:** `/docs/UI_REFACTOR_ROADMAP.md`
- **Frontend Component:** `/frontend/components/tenders/DocumentViewer.tsx`

---

## Contact

**Implementation Date:** 2025-12-02
**Implemented By:** Claude (AI Assistant)
**Task Reference:** Phase 2.2 of UI Refactor Roadmap
