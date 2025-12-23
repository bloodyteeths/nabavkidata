---
paths: scraper/**/*.py
---

# Scraper Development Rules

## Spider Parameters
- Use `year` for archive years 2008-2021 (Playwright modal)
- Use `year_filter` for 2022+ (server-side filter)
- Always set `force_full_scan=true` for backfills

## Memory Management
- Server has 3.8GB RAM total
- Max 2-3 concurrent Playwright scrapers
- Use `MEMUSAGE_LIMIT_MB=1200` for safety
- Each Playwright context uses ~500MB

## Filter Recovery
- Archive modal and date filter corrupt after ~80-100 pages
- Spider has automatic recovery that re-navigates
- Don't disable this behavior

## Document Processing
- PDFs are downloaded to `downloads/files/`
- Use Chandra for OCR extraction
- Clean up extracted PDFs to save disk space:
  ```bash
  rm downloads/files/*.pdf
  ```

## Database Writes
- Use `ON CONFLICT` for upserts
- Batch inserts for performance
- Check for duplicates by tender_id

## Error Handling
- Log errors but don't stop the spider
- Retry failed requests with exponential backoff
- Mark failed documents for later retry

## Testing
- Test on 2-3 pages before full run
- Use `max_listing_pages=5` for quick tests
- Check database after test run
