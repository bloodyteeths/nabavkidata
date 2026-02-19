# Failed Document Extraction Retry Guide

## Overview

The `retry_failed_docs.py` script intelligently retries extraction for 3,670 failed documents across four failure categories:

| Failure Type | Count | Percentage | Cause |
|--------------|-------|------------|-------|
| `failed` | 3,060 | 83.4% | Generic extraction failures (missing files, unsupported formats, extraction errors) |
| `download_failed` | 308 | 8.4% | HTTP errors, network issues during download |
| `ocr_required` | 290 | 7.9% | Scanned PDFs without extractable text |
| `download_timeout` | 12 | 0.3% | Download exceeded timeout limit |

## How It Works

### Intelligent Retry Strategy

The script analyzes each failure type and applies the appropriate recovery strategy:

1. **OCR Required** (`ocr_required`)
   - File exists locally but contains no extractable text (scanned PDF)
   - Strategy: Force Tesseract OCR extraction with Macedonian language support
   - Requires: `tesseract-ocr` and `pytesseract` installed

2. **Download Failures** (`download_failed`, `download_timeout`)
   - Download failed due to network issues, timeouts, or HTTP errors
   - Strategy: Retry download with exponential backoff (3 attempts)
   - Timeout increased to 10 minutes for slow downloads

3. **Generic Failures** (`failed`)
   - Extraction failed for various reasons
   - Strategy 1: If file exists locally → retry extraction with all engines (PyMuPDF, PDFMiner, Tesseract)
   - Strategy 2: If file missing → re-download then extract
   - Strategy 3: If extraction produces <50 chars → fallback to OCR

### Key Features

- **Multi-engine extraction**: PyMuPDF → PDFMiner → Tesseract OCR fallback
- **Exponential backoff**: Retries with increasing delays (1s, 2s, 4s)
- **OCR support**: Tesseract with Macedonian (`mkd`) and English (`eng`) languages
- **Permanent failure detection**: Marks documents that can't be recovered after max retries
- **Dry run mode**: Test without database updates
- **Progress tracking**: Live statistics during processing

## Installation

### Install Tesseract OCR (for scanned documents)

**On Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-mkd tesseract-ocr-eng
```

**On macOS:**
```bash
brew install tesseract tesseract-lang
```

### Install Python dependencies:
```bash
pip install pytesseract pillow
```

### Verify installation:
```bash
python3 -c "import pytesseract; print('Tesseract available')"
tesseract --list-langs  # Should show 'mkd' and 'eng'
```

## Usage Examples

### 1. Start with OCR Required (Highest Success Rate)

OCR-required documents have the highest success rate because they're already downloaded:

```bash
cd /home/ubuntu/nabavkidata/scraper
python3 retry_failed_docs.py --status ocr_required --limit 100
```

Expected results:
- Success rate: 70-90% (if Tesseract is properly configured)
- Processing time: ~30-60 seconds per document (OCR is slow)
- Output: Extracted Macedonian text from scanned PDFs

### 2. Retry Download Failures

Documents that failed to download due to network issues:

```bash
python3 retry_failed_docs.py --status download_failed --limit 50
```

Expected results:
- Success rate: 40-60% (some URLs may be permanently broken)
- Processing time: ~10-20 seconds per document
- Will mark permanently failed if HTTP 404/410

### 3. Retry All Failures (Comprehensive)

Process all failure types (prioritizes OCR-required first):

```bash
python3 retry_failed_docs.py --all --limit 500
```

### 4. Retry Specific Tender

Retry all failed documents for a specific tender:

```bash
python3 retry_failed_docs.py --tender-id 12345/2025
```

### 5. Dry Run (Test Mode)

Test the script without making database changes:

```bash
python3 retry_failed_docs.py --dry-run --status ocr_required --limit 10
```

Output shows what would happen without actually updating the database.

## Recommended Workflow

### Phase 1: OCR Required (290 documents)
```bash
# Process in batches to monitor progress
python3 retry_failed_docs.py --status ocr_required --limit 100
python3 retry_failed_docs.py --status ocr_required --limit 100
python3 retry_failed_docs.py --status ocr_required --limit 100
```

**Expected outcome**: 200-260 successful extractions (70-90% success rate)

### Phase 2: Download Failures (320 documents)
```bash
# Retry downloads with better error handling
python3 retry_failed_docs.py --status download_failed --limit 100
python3 retry_failed_docs.py --status download_timeout --limit 20
python3 retry_failed_docs.py --status download_failed --limit 200
```

**Expected outcome**: 128-192 successful downloads and extractions (40-60% success rate)

### Phase 3: Generic Failures (3,060 documents)
```bash
# Process in larger batches (these are faster - no OCR needed)
python3 retry_failed_docs.py --status failed --limit 500
python3 retry_failed_docs.py --status failed --limit 500
python3 retry_failed_docs.py --status failed --limit 500
# ... continue in batches
```

**Expected outcome**: 1,224-1,836 successful extractions (40-60% success rate)

### Phase 4: Check Results
```bash
# Check updated statistics
PGPASSWORD='...' psql -h ... -U nabavki_user -d nabavkidata -c "
SELECT extraction_status, COUNT(*) as count
FROM documents
GROUP BY extraction_status
ORDER BY count DESC;"
```

## Output and Statistics

During processing, you'll see live statistics:

```
================================================================================
Processing document 10: Техничка спецификација.docx
Tender: 22347/2025, Status: ocr_required
Strategy: ocr - Document requires OCR (scanned PDF)
================================================================================
Forcing OCR extraction for: 22347_2025_bec2979eb430.docx
OCR extracted 4523 chars from 22347_2025_bec2979eb430.docx
Extraction successful: 4523 chars using tesseract_ocr
✓ Document processed successfully

Progress: 10 documents attempted
  ✓ Success: 8 (80.0%)
    - OCR success: 7
    - Re-download success: 1
  ✗ Failed: 1
  ⊗ Permanently failed: 0
  ⊘ Skipped: 1
```

Final results show comprehensive statistics:

```
================================================================================
FINAL RESULTS
================================================================================
Progress: 100 documents attempted
  ✓ Success: 72 (72.0%)
    - OCR success: 58
    - Re-download success: 14
  ✗ Failed: 15
  ⊗ Permanently failed: 8
  ⊘ Skipped: 5
```

## Troubleshooting

### Issue: "Tesseract not available"
**Solution**: Install Tesseract OCR (see Installation section above)

### Issue: "Download failed: HTTP 404"
**Reason**: Document URL is broken or file was removed from e-nabavki.gov.mk
**Action**: Script automatically marks as `permanently_failed`

### Issue: OCR extraction too slow
**Solution**:
- OCR is inherently slow (30-60s per document)
- Process in smaller batches (limit 50-100)
- Run multiple instances in parallel (careful with server load)

### Issue: "Extraction failed - insufficient text"
**Reason**: Document is corrupt, empty, or unsupported format
**Action**: Script marks as `permanently_failed`

### Issue: Out of memory errors
**Solution**:
- Process smaller batches (--limit 50)
- OCR can be memory-intensive for large PDFs
- Monitor server RAM usage

## Performance Tips

1. **Batch Processing**: Process 100-200 documents per run for manageable batches
2. **Prioritize OCR**: Start with `ocr_required` (highest success rate, already downloaded)
3. **Off-peak Hours**: Run during low-traffic hours to avoid server load
4. **Parallel Processing**: Can run multiple instances for different failure types
5. **Monitor Progress**: Check logs and statistics after each batch

## Monitoring

### Check remaining failures:
```bash
PGPASSWORD='...' psql -h ... -U nabavki_user -d nabavkidata -c "
SELECT extraction_status, COUNT(*)
FROM documents
WHERE extraction_status IN ('failed', 'ocr_required', 'download_failed', 'download_timeout', 'permanently_failed')
GROUP BY extraction_status;"
```

### Check extraction success rate:
```bash
PGPASSWORD='...' psql -h ... -U nabavki_user -d nabavkidata -c "
SELECT
  COUNT(*) FILTER (WHERE extraction_status = 'success') as success,
  COUNT(*) FILTER (WHERE extraction_status IN ('failed', 'ocr_required', 'download_failed', 'permanently_failed')) as failed,
  ROUND(100.0 * COUNT(*) FILTER (WHERE extraction_status = 'success') / COUNT(*), 2) as success_rate_pct
FROM documents
WHERE file_url IS NOT NULL AND file_url != '';"
```

### Check OCR extraction statistics:
```bash
PGPASSWORD='...' psql -h ... -U nabavki_user -d nabavkidata -c "
SELECT COUNT(*)
FROM documents
WHERE content_text LIKE '%tesseract%';"
```

## Expected Overall Results

After running all retries across 3,670 failed documents:

| Metric | Expected Result |
|--------|-----------------|
| Total Success | 1,600 - 2,300 (44-63%) |
| OCR Successes | 200 - 260 from OCR-required |
| Download Recoveries | 120 - 190 from download failures |
| Extraction Recoveries | 1,200 - 1,800 from generic failures |
| Permanently Failed | 1,300 - 2,000 (36-56%) |

### Success Rate by Type

- **OCR Required**: 70-90% success (best outcome)
- **Download Failures**: 40-60% success (network-dependent)
- **Generic Failures**: 40-60% success (varies by issue)

## Log Files

Processing logs are written to stdout. To capture logs:

```bash
python3 retry_failed_docs.py --status ocr_required --limit 100 2>&1 | tee retry_ocr_$(date +%Y%m%d_%H%M%S).log
```

## Cron Job (Scheduled Retry)

To automatically retry failures weekly:

```bash
# Add to crontab
0 2 * * 0 cd /home/ubuntu/nabavkidata/scraper && python3 retry_failed_docs.py --all --limit 200 >> /var/log/nabavkidata/retry_failed.log 2>&1
```

## Support

For issues or questions:
1. Check logs for specific error messages
2. Verify Tesseract installation for OCR issues
3. Check database connectivity for timeout errors
4. Monitor server resources (RAM, disk space)
