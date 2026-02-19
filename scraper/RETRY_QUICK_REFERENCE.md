# Retry Failed Documents - Quick Reference

## Quick Start

```bash
# 1. Install Tesseract (one time)
sudo apt-get install tesseract-ocr tesseract-ocr-mkd tesseract-ocr-eng
pip install pytesseract pillow

# 2. Test with dry run
python3 retry_failed_docs.py --dry-run --limit 5

# 3. Start with OCR (highest success rate)
python3 retry_failed_docs.py --status ocr_required --limit 100
```

## Common Commands

```bash
# Retry OCR required documents (70-90% success rate)
python3 retry_failed_docs.py --status ocr_required --limit 100

# Retry download failures (40-60% success rate)
python3 retry_failed_docs.py --status download_failed --limit 50

# Retry all generic failures
python3 retry_failed_docs.py --status failed --limit 500

# Retry everything (prioritizes OCR first)
python3 retry_failed_docs.py --all --limit 500

# Retry specific tender
python3 retry_failed_docs.py --tender-id 12345/2025

# Dry run (no database changes)
python3 retry_failed_docs.py --dry-run --limit 10
```

## Current Failures

| Type | Count | Success Rate |
|------|-------|--------------|
| `failed` | 3,060 | 40-60% |
| `download_failed` | 308 | 40-60% |
| `ocr_required` | 290 | 70-90% |
| `download_timeout` | 12 | 40-60% |

**Total**: 3,670 failures → Expected recovery: 1,555-2,289 (42-62%)

## Check Progress

```bash
# Check failure statistics
PGPASSWORD='<REDACTED>' psql \
  -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
  -U nabavki_user -d nabavkidata \
  -c "SELECT extraction_status, COUNT(*) FROM documents
      WHERE extraction_status IN ('failed', 'ocr_required', 'download_failed', 'download_timeout', 'permanently_failed')
      GROUP BY extraction_status;"

# Check overall success rate
PGPASSWORD='<REDACTED>' psql \
  -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
  -U nabavki_user -d nabavkidata \
  -c "SELECT
        COUNT(*) FILTER (WHERE extraction_status = 'success') as success,
        COUNT(*) FILTER (WHERE extraction_status IN ('failed', 'permanently_failed')) as failed,
        ROUND(100.0 * COUNT(*) FILTER (WHERE extraction_status = 'success') / COUNT(*), 1) as pct
      FROM documents WHERE file_url IS NOT NULL;"
```

## Recommended Workflow

### Phase 1: OCR (290 docs) - Start Here!
```bash
python3 retry_failed_docs.py --status ocr_required --limit 100
python3 retry_failed_docs.py --status ocr_required --limit 100
python3 retry_failed_docs.py --status ocr_required --limit 100
```
Expected: 203-261 recoveries

### Phase 2: Downloads (320 docs)
```bash
python3 retry_failed_docs.py --status download_failed --limit 100
python3 retry_failed_docs.py --status download_timeout --limit 20
python3 retry_failed_docs.py --status download_failed --limit 200
```
Expected: 128-192 recoveries

### Phase 3: Generic Failures (3,060 docs)
```bash
# Run in batches of 500
python3 retry_failed_docs.py --status failed --limit 500
# Repeat 6 times until complete
```
Expected: 1,224-1,836 recoveries

## Output Example

```
================================================================================
Processing document 10: Техничка спецификација.docx
Tender: 22347/2025, Status: ocr_required
Strategy: ocr - Document requires OCR (scanned PDF)
================================================================================
Forcing OCR extraction for: 22347_2025_bec2979eb430.docx
OCR extracted 4523 chars
✓ Document processed successfully

Progress: 10 documents attempted
  ✓ Success: 8 (80.0%)
    - OCR success: 7
    - Re-download success: 1
  ✗ Failed: 1
  ⊗ Permanently failed: 0
  ⊘ Skipped: 1
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Tesseract not available" | `sudo apt-get install tesseract-ocr tesseract-ocr-mkd` |
| OCR too slow | Normal (30-60s per doc), process in small batches |
| "Download failed: HTTP 404" | File removed from server, marked as permanently_failed |
| Out of memory | Reduce batch size: `--limit 50` |

## Files

- **Script**: `/Users/tamsar/Downloads/nabavkidata/scraper/retry_failed_docs.py`
- **Full Guide**: `/Users/tamsar/Downloads/nabavkidata/scraper/RETRY_FAILED_DOCS_GUIDE.md`
- **Summary**: `/Users/tamsar/Downloads/nabavkidata/scraper/RETRY_SCRIPT_SUMMARY.md`
- **Tests**: `/Users/tamsar/Downloads/nabavkidata/scraper/test_retry_script.py`

## Need Help?

```bash
python3 retry_failed_docs.py --help
```
