# Document Content Endpoint

## Overview
Endpoint for retrieving full document content with metadata without requiring file download.

## Endpoint Details

**URL:** `GET /api/documents/{doc_id}/content`

**Authentication:** Required (JWT Bearer Token)

**Parameters:**
- `doc_id` (path parameter, UUID): Document identifier

## Response Schema

```json
{
  "doc_id": "12ca5425-8b5d-461b-b170-35d4b54ca79d",
  "file_name": "technical_specs.pdf",
  "file_type": "pdf",
  "content_text": "Full extracted text content...",
  "content_preview": "First 500 characters...",
  "word_count": 450,
  "has_tables": true,
  "extraction_status": "success",
  "file_url": "https://e-nabavki.gov.mk/File/Download...",
  "tender_id": "20450/2025",
  "created_at": "2025-12-02T10:30:00Z"
}
```

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `doc_id` | UUID | Unique document identifier |
| `file_name` | string | Original filename |
| `file_type` | string | Detected file type: `pdf`, `word`, `excel`, `other` |
| `content_text` | string | Full extracted text from document |
| `content_preview` | string | First 500 characters (for quick preview) |
| `word_count` | integer | Number of words in content |
| `has_tables` | boolean | Whether document contains table-like structures |
| `extraction_status` | string | Status: `success`, `pending`, `failed` |
| `file_url` | string | Download URL for original file |
| `tender_id` | string | Associated tender ID |
| `created_at` | datetime | Upload timestamp |

## Features

### Table Detection
Automatically detects if document contains tabular data by checking for:
- Pipe-separated tables: `| col1 | col2 | col3 |`
- Tab-separated data: `col1\tcol2\tcol3`
- Numbered rows with columns: `1. Item Name    Quantity    Price`

### File Type Detection
Determines file type from:
1. File extension (`.pdf`, `.docx`, `.xlsx`, etc.)
2. MIME type if extension missing
3. Fallback to `other` if unrecognized

### Content Processing
- Extracts full text from `documents.content_text` field
- Generates preview (first 500 chars)
- Calculates word count automatically
- Handles null/empty content gracefully

## Usage Examples

### cURL
```bash
curl -X GET "https://api.nabavkidata.com/api/documents/12ca5425-8b5d-461b-b170-35d4b54ca79d/content" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### JavaScript (Frontend)
```javascript
const response = await fetch(`/api/documents/${docId}/content`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const content = await response.json();

console.log(content.content_preview);  // First 500 chars
console.log(content.word_count);       // Number of words
console.log(content.has_tables);       // Table detection
```

### Python
```python
import requests

response = requests.get(
    f"https://api.nabavkidata.com/api/documents/{doc_id}/content",
    headers={"Authorization": f"Bearer {token}"}
)
content = response.json()

print(content['content_text'])    # Full text
print(content['word_count'])      # Word count
```

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 404 Not Found
```json
{
  "detail": "Document not found"
}
```

## Performance

- **Target:** <500ms response time
- **Expected:** ~100-200ms (single DB query)
- **Database:** PostgreSQL with UUID index
- **Caching:** Not implemented (consider for future)

## Integration

### Frontend Integration
The endpoint is consumed by:
- `DocumentViewer` component (`/frontend/components/tenders/DocumentViewer.tsx`)
- API client method: `api.getDocumentContent(docId)`

### Backend Files
- **Endpoint:** `/backend/api/documents.py` (lines 122-203)
- **Schema:** `/backend/schemas.py` (lines 178-193)
- **Model:** `/backend/models.py` (Document model)

## Security Considerations

1. **Authentication Required:** All requests must include valid JWT token
2. **Authorization:** Only authenticated users can access document content
3. **Data Validation:** UUID validation prevents SQL injection
4. **Rate Limiting:** Subject to global API rate limits

## Future Enhancements

### Phase 2.2: AI Document Summarization
Extended response will include:
```json
{
  ...existing_fields,
  "ai_summary": "Brief summary in Macedonian...",
  "key_requirements": ["Requirement 1", "Requirement 2"],
  "items_mentioned": [
    {
      "name": "Product name",
      "quantity": "100",
      "unit": "pieces",
      "notes": "Additional notes"
    }
  ]
}
```

## Database Schema

### documents table
```sql
CREATE TABLE documents (
    doc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tender_id VARCHAR(100) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    file_name VARCHAR(500),
    file_url TEXT,
    content_text TEXT,  -- Full extracted text
    extraction_status VARCHAR(50) DEFAULT 'pending',
    mime_type VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Other fields...
);

CREATE INDEX idx_documents_doc_id ON documents(doc_id);
CREATE INDEX idx_documents_tender_id ON documents(tender_id);
```

## Testing

### Test Document
- **ID:** `12ca5425-8b5d-461b-b170-35d4b54ca79d`
- **Tender:** `20450/2025`
- **Content Length:** 2,772 characters
- **Status:** `success`

### Sample Response
```json
{
  "doc_id": "12ca5425-8b5d-461b-b170-35d4b54ca79d",
  "file_name": "20450_2025_c6989c26e2f3e3ccf15d8505d01ca4c1.pdf",
  "file_type": "pdf",
  "content_text": "Техничка понуда\nСогласни сме да ги понудиме следниве Услуги...",
  "content_preview": "Техничка понуда\nСогласни сме да ги понудиме следниве Услуги: Предмет на набавка – Одржување и сервисирање...",
  "word_count": 450,
  "has_tables": true,
  "extraction_status": "success",
  "file_url": "https://e-nabavki.gov.mk/File/DownloadPublicFile?fileId=b969860f-55d1-4de6-8c6e-65c02970194d",
  "tender_id": "20450/2025",
  "created_at": "2025-11-25T10:30:00Z"
}
```

## Related Documentation
- [UI Refactor Roadmap](/docs/UI_REFACTOR_ROADMAP.md)
- [Enhanced Tender Endpoint](/backend/api/ENHANCED_ENDPOINT_README.md)
- [API Authentication](/backend/middleware/rbac.py)
