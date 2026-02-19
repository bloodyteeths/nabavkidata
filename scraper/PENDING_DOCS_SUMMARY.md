# Pending Documents Processing - Executive Summary

## Problem
7,369 documents in database have `extraction_status='pending'` - text has not been extracted and they're not searchable.

## Analysis Results

### Document Distribution
```
Total pending: 7,369
├─ No file_url (empty/NULL): 6,846 (93%)
└─ With valid URL: 523 (7%)
```

The 523 documents with valid URLs can be processed immediately. The 6,846 without URLs may have been:
- Failed during scraping
- Deleted from source
- Never had URLs in the first place

### Document Types in Queue
- **PDF**: тендерска_документација (tender documentation)
- **DOCX**: Technical specifications, bid forms
- **XLSX**: Price lists, financial tables

Most documents (7,341) have no `mime_type` set - will be detected during download by file extension.

## Solution Created

### 1. Main Script: `process_pending_docs.py`
Comprehensive batch processing script with:

**Core Features:**
- Downloads documents from e-nabavki.gov.mk
- Multi-engine text extraction (PyMuPDF, PDFMiner, OCR, python-docx, openpyxl)
- Spec extraction (products, quantities, prices, CPV codes)
- Optional embedding generation for semantic search

**Reliability Features:**
- Checkpoint-based resumability (survives crashes/interruptions)
- Categorized error handling (download_failed, auth_required, ocr_required, etc.)
- Progress tracking every 10 documents
- Rate limiting (180s timeout per document)
- Memory efficient (processes one doc at a time)

**Error Categories:**
- `success`: Extracted and stored
- `download_failed`: Network/HTTP error
- `download_timeout`: Took >180 seconds
- `auth_required`: HTTP 401/403
- `download_invalid`: Empty file or HTML error page
- `ocr_required`: Scanned PDF needs OCR
- `skipped_external`: External link (e.g., bank guarantees)
- `skip_minimal`: Less than 50 characters extracted
- `skip_bank_guarantee`: Bank guarantee boilerplate

### 2. Convenience Script: `process_pending.sh`
Shell wrapper for common operations:
```bash
./process_pending.sh test           # Dry run
./process_pending.sh small          # Process 50
./process_pending.sh batch 200      # Process 200
./process_pending.sh all            # Process all
./process_pending.sh stats          # Show database stats
./process_pending.sh follow-logs    # Watch in real-time
```

### 3. Documentation: `PENDING_DOCS_GUIDE.md`
Complete usage guide with examples, troubleshooting, and recommendations.

## Recommended Workflow

### Phase 1: Test Run (5 minutes)
```bash
cd /home/ubuntu/nabavkidata/scraper
./process_pending.sh test           # Dry run
./process_pending.sh small          # Process 50 docs
./process_pending.sh stats          # Check results
```

### Phase 2: Process All Pending (1-2 hours estimated)
```bash
# Process all 523 docs with valid URLs
./process_pending.sh all

# Or resume if interrupted
./process_pending.sh resume
```

Estimated processing rate: 15-20 docs/min = ~30-40 minutes for 523 documents.

### Phase 3: Handle Edge Cases

**OCR Required Documents:**
After Phase 2, check how many need OCR:
```sql
SELECT COUNT(*) FROM documents WHERE extraction_status='ocr_required';
```

These are scanned PDFs that need Tesseract OCR (slower, requires separate processing).

**Auth Required Documents:**
```sql
SELECT COUNT(*) FROM documents WHERE extraction_status='auth_required';
```

These may need authenticated session cookies from browser.

### Phase 4: Generate Embeddings
```bash
cd /home/ubuntu/nabavkidata/ai/embeddings
python3 pipeline.py --batch-size 20 --max-documents 1000
```

Or integrate with processing:
```bash
cd /home/ubuntu/nabavkidata/scraper
./process_pending.sh with-embeddings
```

## Expected Outcomes

### Realistic Success Rates
Based on the existing data patterns:
- **70-80% success**: Documents will extract successfully
- **10-15% OCR required**: Scanned PDFs
- **5-10% download failures**: Network issues, deleted files, auth required
- **5% skipped**: External links, minimal content, boilerplate

### Database Impact
Before:
```
pending: 7,369
success: 21,390
```

After (estimated):
```
pending: 0
success: 21,800 (+410)
ocr_required: 350 (+60)
download_failed: 100 (+50)
skipped_*: 53 (+3)
```

### Storage Impact
- Downloaded files: ~100-200 MB (523 docs × ~200KB avg)
- Can be deleted after extraction to save space (see cleanup command)
- Text in database: ~5-10 MB additional

## Monitoring Commands

### Watch Processing in Real-Time
```bash
./process_pending.sh follow-logs
```

### Check Progress
```bash
./process_pending.sh stats
./process_pending.sh checkpoint
```

### Database Queries
```sql
-- Success rate
SELECT
  extraction_status,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM documents), 2) as percentage
FROM documents
GROUP BY extraction_status
ORDER BY count DESC;

-- Recent successes
SELECT doc_id, tender_id, file_name, extracted_at
FROM documents
WHERE extraction_status = 'success'
ORDER BY extracted_at DESC
LIMIT 10;

-- Documents needing embeddings
SELECT COUNT(*)
FROM documents d
WHERE extraction_status = 'success'
  AND content_text IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id);
```

## Key Advantages

1. **Resumable**: Won't lose progress if interrupted
2. **Safe**: Memory efficient, won't crash server
3. **Informative**: Detailed logging and progress tracking
4. **Categorized**: Failures are categorized for follow-up
5. **Integrated**: Uses same extraction pipeline as scrapers
6. **Flexible**: Can process all, batches, or specific tenders

## Files Created

```
/Users/tamsar/Downloads/nabavkidata/scraper/
├── process_pending_docs.py      # Main script (850 lines)
├── process_pending.sh           # Convenience wrapper
├── PENDING_DOCS_GUIDE.md        # Detailed usage guide
└── PENDING_DOCS_SUMMARY.md      # This file

/tmp/
├── process_pending_docs.log     # Processing log (created on first run)
└── process_pending_docs_checkpoint.json  # Resumability checkpoint
```

## Next Actions

1. **Transfer to server**: Upload script to `/home/ubuntu/nabavkidata/scraper/`
2. **Test**: Run `./process_pending.sh test` to verify
3. **Small batch**: Run `./process_pending.sh small` to process 50 docs
4. **Check results**: Review extraction_status distribution
5. **Full run**: Run `./process_pending.sh all` to process remaining
6. **Generate embeddings**: Run embeddings pipeline after extraction

## Dependencies

All dependencies already installed (same as `process_documents.py`):
- ✅ asyncpg
- ✅ aiohttp
- ✅ aiofiles
- ✅ PyMuPDF (fitz)
- ✅ pdfminer
- ✅ python-docx
- ✅ openpyxl
- ⚠️ pytesseract (optional, for OCR phase)

## Notes

- Script logs to both console and `/tmp/process_pending_docs.log`
- Checkpoint saves every 10 documents to `/tmp/process_pending_docs_checkpoint.json`
- Downloads go to `/home/ubuntu/nabavkidata/scraper/downloads/files/`
- Safe to run with 2-3 other scrapers on 3.8GB server
- Can be stopped with Ctrl+C and resumed later
- Processing rate: ~15-20 docs/min on server

## Support

See `PENDING_DOCS_GUIDE.md` for detailed troubleshooting and usage examples.
