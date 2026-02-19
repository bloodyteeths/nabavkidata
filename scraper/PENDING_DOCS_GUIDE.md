# Pending Documents Processing Guide

## Overview

Script to process the 7,369 documents with `extraction_status='pending'` in the database. The script downloads documents, extracts text using multiple engines (PyMuPDF, PDFMiner, Tesseract OCR for PDFs; python-docx for Word; openpyxl for Excel), and optionally generates embeddings for semantic search.

## Current Status (as of analysis)

```
Total documents with extraction_status='pending': 7,369
- 6,846 have no file_url (empty or NULL)
- 523 have valid URLs to download and process
```

## Document Types in Pending Queue

Most pending documents have no mime_type set (will be detected during download):
- PDFs: тендерска_документација, образец_техничка_понуда
- DOCX: Technical specifications, forms
- XLSX: Spreadsheets with pricing/specs

## Features

### Resumability
- Uses checkpoint file at `/tmp/process_pending_docs_checkpoint.json`
- Tracks processed document IDs
- Can be stopped with Ctrl+C and resumed later
- Checkpoint saves every 10 documents

### Error Handling
Documents are categorized by failure type:
- `download_failed`: HTTP error, network issue
- `download_timeout`: Download exceeded 180 seconds
- `auth_required`: HTTP 401/403 (requires authentication)
- `download_invalid`: Downloaded HTML error page or file too small
- `ocr_required`: PDF is scanned image, text extraction failed
- `skipped_external`: External link (e.g., ohridskabanka.mk)
- `skip_minimal`: Extracted less than 50 characters
- `skip_bank_guarantee`: Bank guarantee boilerplate
- `success`: Successfully extracted and stored

### Progress Tracking
- Shows stats every 10 documents
- Logs to both console and `/tmp/process_pending_docs.log`
- Displays processing rate (docs/min)
- Final summary with breakdown by status

### Batch Processing
- Configurable batch sizes
- Memory efficient (processes one doc at a time)
- Can process specific tenders or all pending docs

## Usage Examples

### 1. Dry Run (Check What Would Be Processed)
```bash
cd /home/ubuntu/nabavkidata/scraper
python3 process_pending_docs.py --dry-run --limit 100
```

### 2. Process 100 Documents
```bash
python3 process_pending_docs.py --limit 100
```

### 3. Process All Pending Documents
```bash
python3 process_pending_docs.py --all
```

This processes in batches of 100 until no more pending documents remain.

### 4. Resume from Checkpoint
```bash
# If script was stopped, resume without reprocessing
python3 process_pending_docs.py --resume --all
```

### 5. Process Specific Tender
```bash
python3 process_pending_docs.py --tender-id 23178/2025
```

### 6. Clear Checkpoint and Start Fresh
```bash
python3 process_pending_docs.py --clear-checkpoint --all
```

### 7. With Embeddings Generation
```bash
python3 process_pending_docs.py --limit 100 --generate-embeddings
```

This generates embeddings for successfully extracted documents (batches of 100).

### 8. Process with Offset (Skip First N)
```bash
python3 process_pending_docs.py --offset 500 --limit 100
```

## Output Examples

### Progress Output
```
2025-12-22 10:15:30 [INFO] Processing f0794a19-cbde-499e-b810-139fa9b9bbfd: тендерска_документација_23173-2025_20251222080030.pdf (tender 23173/2025)
2025-12-22 10:15:32 [INFO] Downloaded: 23173_2025_e49b7f2a56bd.pdf (245.3 KB)
2025-12-22 10:15:33 [INFO] Extracted 12453 chars from .pdf, 3 CPV codes, 2 companies
2025-12-22 10:15:33 [INFO] Inserted 5 product items for tender 23173/2025
2025-12-22 10:15:33 [INFO] Progress: 10/100 | Success: 8 | Failed: 2 | Rate: 15.3 docs/min
```

### Final Summary
```
=== Processing Summary ===
Total Processed: 100
Success: 78 (78.0%)
Failed: 22
  - Download Failed: 5
  - Auth Required: 3
  - OCR Required: 12
  - Skipped (external/empty): 2
Elapsed Time: 6.5 minutes
Processing Rate: 15.4 docs/min
==========================
```

## Database Statistics

Check current status distribution:
```sql
SELECT extraction_status, COUNT(*)
FROM documents
GROUP BY extraction_status
ORDER BY COUNT(*) DESC;
```

Check pending documents with URLs:
```sql
SELECT COUNT(*)
FROM documents
WHERE extraction_status = 'pending'
  AND file_url IS NOT NULL
  AND file_url <> '';
```

Check documents missing embeddings:
```sql
SELECT COUNT(*)
FROM documents d
WHERE extraction_status = 'success'
  AND content_text IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id);
```

## Recommendations

### Phase 1: Process Documents with URLs (523 docs)
```bash
# Start with a small test batch
python3 process_pending_docs.py --limit 50

# If successful, process all pending docs with URLs
python3 process_pending_docs.py --all
```

### Phase 2: Handle OCR Required Documents
Documents marked as `ocr_required` are scanned PDFs that need Tesseract OCR. These require:
1. Tesseract installation on server
2. More processing time (OCR is slow)
3. Potentially different extraction script

Check count:
```sql
SELECT COUNT(*) FROM documents WHERE extraction_status = 'ocr_required';
```

### Phase 3: Generate Embeddings
After extraction, generate embeddings for semantic search:
```bash
cd /home/ubuntu/nabavkidata/ai/embeddings
python3 pipeline.py --batch-size 20 --max-documents 1000
```

Or use the integrated embeddings flag:
```bash
cd /home/ubuntu/nabavkidata/scraper
python3 process_pending_docs.py --all --generate-embeddings
```

## Memory Management

The script is designed to be memory efficient:
- Processes one document at a time
- HTTP session with 180s timeout
- Async I/O for concurrent operations
- Downloaded PDFs can be deleted after extraction (see CLAUDE.md)

Safe to run on 3.8GB server with 2-3 other processes.

## Monitoring

### View Logs
```bash
tail -f /tmp/process_pending_docs.log
```

### Check Checkpoint
```bash
cat /tmp/process_pending_docs_checkpoint.json | python3 -m json.tool
```

### Monitor Progress in Database
```sql
-- Watch success count increase
SELECT extraction_status, COUNT(*)
FROM documents
GROUP BY extraction_status;

-- Recent successes
SELECT doc_id, tender_id, file_name, extracted_at
FROM documents
WHERE extraction_status = 'success'
ORDER BY extracted_at DESC
LIMIT 10;
```

## Troubleshooting

### Script Hangs on Download
- Timeout is 180 seconds per download
- If consistently timing out, check network/VPN
- Document will be marked as `download_timeout`

### Out of Memory
- Script processes one doc at a time, should not OOM
- If it does, check for other memory-intensive processes
- Consider reducing batch size in embeddings generation

### Many OCR Required
- Normal for scanned documents
- Requires Tesseract OCR (not currently in extraction pipeline)
- Consider separate OCR processing script for these

### Authentication Errors
- Some documents may require login session
- Marked as `auth_required`
- May need to extract cookies from browser session

## Integration with Existing Pipeline

This script complements the existing `process_documents.py`:
- `process_documents.py`: Processes documents as they're scraped
- `process_pending_docs.py`: Batch processes backlog of pending documents

Both use the same extraction engines and database schema.

## Next Steps

1. Test with small batch: `--limit 50`
2. Review results in database
3. Process all pending: `--all`
4. Handle OCR documents separately if needed
5. Generate embeddings for extracted documents
6. Schedule periodic runs to clear backlog

## Files Created

- `/Users/tamsar/Downloads/nabavkidata/scraper/process_pending_docs.py` - Main script
- `/tmp/process_pending_docs.log` - Processing log
- `/tmp/process_pending_docs_checkpoint.json` - Resumability checkpoint
- `/home/ubuntu/nabavkidata/scraper/downloads/files/` - Downloaded documents

## Dependencies

All dependencies already present (same as `process_documents.py`):
- asyncpg
- aiohttp
- aiofiles
- PyMuPDF (fitz)
- pdfminer
- python-docx
- openpyxl
- pytesseract (optional, for OCR)
