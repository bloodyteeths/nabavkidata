# Quick Start: Process 7,369 Pending Documents

## TL;DR
```bash
# On server
cd /home/ubuntu/nabavkidata/scraper

# Test (dry run)
./process_pending.sh test

# Process 50 documents
./process_pending.sh small

# Process all pending
./process_pending.sh all

# Watch progress
./process_pending.sh follow-logs
```

## One-Liner Commands

### Testing
```bash
# Dry run - see what would be processed
./process_pending.sh test

# Process just 50 docs
./process_pending.sh small
```

### Production
```bash
# Process all pending docs (~30-40 min)
./process_pending.sh all

# Resume if interrupted
./process_pending.sh resume
```

### Monitoring
```bash
# Show database stats
./process_pending.sh stats

# Watch logs in real-time
./process_pending.sh follow-logs

# Check checkpoint
./process_pending.sh checkpoint
```

### Specific Use Cases
```bash
# Process specific tender
./process_pending.sh tender 23178/2025

# Process 200 docs
./process_pending.sh batch 200

# Process with embeddings
./process_pending.sh with-embeddings
```

## What Happens

```
[Database] → [Download] → [Extract] → [Update DB]
   ↓            ↓            ↓           ↓
pending      PDF/DOCX    PyMuPDF     success
             files       PDFMiner    or
                        docx        failed
                        openpyxl    or
                                    ocr_required
```

## Expected Output

```
2025-12-22 10:15:30 [INFO] Found 523 documents to process
2025-12-22 10:15:32 [INFO] Downloaded: 23173_2025_e49b7f2a56bd.pdf (245.3 KB)
2025-12-22 10:15:33 [INFO] Extracted 12453 chars from .pdf, 3 CPV codes
2025-12-22 10:15:33 [INFO] Progress: 10/523 | Success: 8 | Failed: 2 | Rate: 15.3 docs/min

=== Processing Summary ===
Total Processed: 523
Success: 410 (78.4%)
Failed: 113
  - Download Failed: 30
  - Auth Required: 15
  - OCR Required: 60
  - Skipped: 8
Elapsed Time: 34.2 minutes
Processing Rate: 15.3 docs/min
```

## Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| `success` | Text extracted | Ready for embeddings |
| `download_failed` | Network error | Check network/logs |
| `auth_required` | HTTP 401/403 | May need auth cookies |
| `ocr_required` | Scanned PDF | Run OCR processing |
| `download_timeout` | >180s | Network issue |
| `skipped_external` | External link | Intentional skip |
| `skip_minimal` | <50 chars | Empty/useless doc |

## Files

| File | Purpose |
|------|---------|
| `process_pending_docs.py` | Main script |
| `process_pending.sh` | Convenience wrapper |
| `/tmp/process_pending_docs.log` | Processing log |
| `/tmp/process_pending_docs_checkpoint.json` | Resume checkpoint |
| `downloads/files/*.pdf` | Downloaded docs |

## Troubleshooting

### Script hangs
- Wait up to 180s (download timeout)
- Check logs: `./process_pending.sh logs`
- Network issue likely

### Out of memory
- Shouldn't happen (processes 1 doc at a time)
- Check other processes: `top` or `htop`

### Too many failures
- Check stats: `./process_pending.sh stats`
- Review logs for patterns
- May need OCR or auth handling

### Want to start over
```bash
./process_pending.sh clear-checkpoint
./process_pending.sh all
```

## Database Queries

```sql
-- Count pending
SELECT COUNT(*) FROM documents WHERE extraction_status='pending';

-- Recent successes
SELECT doc_id, tender_id, file_name, extracted_at
FROM documents WHERE extraction_status='success'
ORDER BY extracted_at DESC LIMIT 10;

-- Need embeddings
SELECT COUNT(*) FROM documents d
WHERE extraction_status='success'
  AND content_text IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id);
```

## Next Steps After Processing

1. **Check Results**
   ```bash
   ./process_pending.sh stats
   ```

2. **Generate Embeddings**
   ```bash
   cd /home/ubuntu/nabavkidata/ai/embeddings
   python3 pipeline.py --batch-size 20 --max-documents 1000
   ```

3. **Handle OCR Documents** (if needed)
   - Count: `SELECT COUNT(*) FROM documents WHERE extraction_status='ocr_required';`
   - Requires separate OCR processing script with Tesseract

4. **Cleanup** (optional)
   ```bash
   ./process_pending.sh cleanup-pdfs
   ```

## Help

- Detailed guide: `PENDING_DOCS_GUIDE.md`
- Summary: `PENDING_DOCS_SUMMARY.md`
- Script help: `./process_pending.sh help`
- Python help: `python3 process_pending_docs.py --help`

## Key Points

✅ Resumable - can stop/restart anytime
✅ Safe - memory efficient, won't crash
✅ Fast - ~15-20 docs/min
✅ Detailed - logs everything
✅ Smart - categorizes failures
✅ Integrated - uses existing extraction engines

## Estimated Time

- 523 docs with URLs: **30-40 minutes**
- Includes download, extraction, database update
- Rate: 15-20 docs/min
- Can run alongside 2-3 other scrapers on 3.8GB server
