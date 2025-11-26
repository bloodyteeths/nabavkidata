# Phase 5 & 6 Progress Report: Incremental Scraping & Automation

**Date:** 2025-11-24
**Status:** Phase 5 Complete, Phase 6 Complete (Limited)

---

## Phase 5: Incremental Scraping & Change Detection

### Summary

Successfully implemented incremental scraping with content hash-based change detection to optimize scraping efficiency.

### Database Changes

**Migration:** `db/migrations/004_phase5_incremental_scraping.sql`

New fields added to `tenders` table:
- `last_modified` - Timestamp when tender was last modified
- `scrape_count` - Number of times tender has been scraped
- `content_hash` - SHA-256 hash for change detection
- `first_scraped_at` - When tender was first discovered
- `source_category` - Category listing where tender was found

New table: `scrape_history`
- Tracks each scrape run with statistics
- Fields: `started_at`, `completed_at`, `mode`, `category`, `tenders_found`, `tenders_new`, `tenders_updated`, `tenders_unchanged`, `errors`, `duration_seconds`, `status`

### Spider Changes

**File:** `scraper/scraper/spiders/nabavki_spider.py`

- Added `mode` parameter support: `scrape` (default), `discover`, `incremental`, `full`
- Added `tenders_skipped` stat tracking
- Updated docstring with new modes

### Pipeline Changes

**File:** `scraper/scraper/pipelines.py`

New methods in `DatabasePipeline`:
- `_compute_content_hash()` - Generates SHA-256 hash of tender content
- `_check_tender_change()` - Compares hash to detect changes
- `_init_scrape_run()` - Creates scrape_history record
- Updated `insert_tender()` to handle change tracking
- Updated `close_spider()` to finalize scrape_history

### Test Results

```
Test Run 1:
  - Tenders scraped: 7
  - All fields populated correctly:
    - source_category: 'active'
    - content_hash: SHA-256 populated
    - scrape_count: 1

Test Run 2:
  - Tenders scraped: 7 (same tenders)
  - scrape_count: 2 -> 3 (incremented)
  - content_hash: unchanged (correct)
```

---

## Phase 6: Cron Automation

### Summary

Created automation scripts for scheduled scraping. Only active tenders scraping is enabled since awarded/cancelled/historical routes are not available on the public portal.

### Scripts Created

**Directory:** `scraper/cron/`

1. **`scrape_active.sh`** - Scrapes active tenders
   - Recommended schedule: Every 3 hours
   - Cron: `0 */3 * * *`

2. **`cleanup_logs.sh`** - Removes logs older than 30 days
   - Recommended schedule: Monthly
   - Cron: `0 4 1 * *`

3. **`setup_crontab.sh`** - Installs cron entries
   - Run once to set up automation

### Crontab Configuration

```cron
# Active tenders - scrape every 3 hours
0 */3 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_active.sh >> /var/log/nabavkidata/active_$(date +\%Y\%m\%d).log 2>&1

# Log cleanup - monthly on the 1st at 4 AM
0 4 1 * * /home/ubuntu/nabavkidata/scraper/cron/cleanup_logs.sh >> /var/log/nabavkidata/cleanup.log 2>&1
```

### Disabled Jobs (Routes Not Available)

The following scrape jobs are disabled because the routes don't exist on the public portal:
- Awarded tenders (`scrape_awarded.sh`)
- Cancelled tenders (`scrape_cancelled.sh`)
- Historical tenders (`scrape_historical.sh`)

---

## Site Structure Findings

### PublicAccess Portal (PublicAccess/home.aspx)

**Working Routes:**
- `#/notices` - Active tenders (97 rows) ✓
- `#/home` - Home page
- `#/sitemap` - Site map
- `#/askquestion` - FAQ

**Non-Existent Routes (redirect to home):**
- `#/awarded`
- `#/cancelled`
- `#/archive`
- `#/historical`
- `#/contracts`
- `#/planned`

### InstitutionGridData Portal

- `#/ciContractsGrid/` - Awarded contracts route EXISTS but **times out** (90+ seconds)
- May require authentication or different approach
- Page structure is different from PublicAccess portal

---

## Deployment

### Deploy Commands

```bash
# Deploy cron scripts to EC2
scp -i ~/.ssh/nabavki-key.pem -r scraper/cron ubuntu@18.197.185.30:/home/ubuntu/nabavkidata/scraper/

# SSH to EC2 and setup crontab
ssh -i ~/.ssh/nabavki-key.pem ubuntu@18.197.185.30
cd /home/ubuntu/nabavkidata/scraper/cron
chmod +x *.sh
./setup_crontab.sh
```

### Verify Cron Installation

```bash
crontab -l
```

---

## Next Steps

1. **EmbeddingPipeline** - Add automatic embedding generation after tender insertion
2. **Phase 7 (API Endpoints)** - Create REST API for new data fields
3. **Phase 8 (Frontend)** - Display enhanced data in UI
4. **Investigate InstitutionGridData** - May need authenticated access

---

**Report Generated:** 2025-11-24
**Phases Completed:** 5, 6 (Limited)
