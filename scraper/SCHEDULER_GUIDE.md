# Scheduler & Cron Setup Guide

## Overview

Automated scraping scheduler with:
- **Periodic scraping** (hourly, daily, weekly)
- **Incremental updates** (only new/changed tenders)
- **Job history tracking** (database-backed)
- **Error handling & retry**
- **Health monitoring**
- **Cron job management**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cron Jobs (System)                       │
├─────────────────────────────────────────────────────────────┤
│  Hourly:  Incremental scrape                                │
│  Daily:   Full scrape (backup)                              │
│  Weekly:  Deep scrape (historical data)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              ScraperScheduler (scheduler.py)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ScrapingHistory                                     │  │
│  │    - Track job start/completion                      │  │
│  │    - Store statistics in DB (scraping_jobs table)    │  │
│  │    - Get last scrape time                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  IncrementalScraper                                  │  │
│  │    - Check existing tender IDs                       │  │
│  │    - Determine what needs scraping                   │  │
│  │    - Only scrape new/updated tenders                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Scrapy Spider (nabavki_spider.py)                   │  │
│  │    - Scrape tender listings                          │  │
│  │    - Extract tender details                          │  │
│  │    - Download & parse documents                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Database (PostgreSQL)                               │  │
│  │    - Store tenders, documents                        │  │
│  │    - Track scraping_jobs history                     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│            Health Check (health_check.py)                   │
├─────────────────────────────────────────────────────────────┤
│  - Check last successful scrape                             │
│  - Calculate error rate                                     │
│  - Alert on failures                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Files

### 1. scheduler.py (488 lines)

**Main scheduler implementation:**

**Classes:**
- `ScrapingHistory` - Track job history in database
- `IncrementalScraper` - Handle incremental scraping logic
- `ScraperScheduler` - Main scheduler coordinator

**CLI Commands:**
```bash
python scheduler.py run --incremental
python scheduler.py run --full
python scheduler.py history --limit 20
```

### 2. cron/scraper.cron (37 lines)

**Cron job configuration:**
- Hourly incremental scrape
- Daily full scrape (2 AM)
- Weekly deep scrape (Sunday 3 AM)
- Log rotation (Monday 4 AM)
- Health check (daily 6 AM)

### 3. cron/install.sh (96 lines)

**Cron installation script:**
- Validates DATABASE_URL
- Updates paths in cron file
- Backs up existing crontab
- Installs new cron jobs

### 4. scripts/health_check.py (118 lines)

**Health monitoring script:**
- Checks last successful scrape
- Calculates error rate
- Measures average job duration
- Exits with error code if unhealthy

---

## Database Schema

### scraping_jobs Table

```sql
CREATE TABLE scraping_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL,           -- 'running', 'completed', 'failed'
    tenders_scraped INTEGER DEFAULT 0,
    documents_scraped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    error_message TEXT,
    spider_name VARCHAR(100),
    incremental BOOLEAN DEFAULT TRUE,
    last_scraped_date TIMESTAMP
);
```

**Purpose:** Track all scraping jobs for monitoring and analysis.

---

## Setup

### 1. Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install cron postgresql-client

# macOS
# Cron is pre-installed
```

### 2. Install Python Dependencies

```bash
cd scraper
pip install -r requirements.txt
```

### 3. Set Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/nabavkidata"
```

Or create `.env` file:
```
DATABASE_URL=postgresql://user:pass@localhost:5432/nabavkidata
```

### 4. Test Scheduler Manually

```bash
# Run incremental scrape
python scheduler.py run --incremental

# View history
python scheduler.py history

# Check health
python scripts/health_check.py
```

### 5. Install Cron Jobs

```bash
cd cron
./install.sh
```

Follow prompts to:
- Enter DATABASE_URL
- Confirm installation
- Verify cron jobs

### 6. Verify Installation

```bash
# Check installed cron jobs
crontab -l

# Should show:
# 0 * * * * cd /path/to/scraper && python scheduler.py run --incremental ...
# 0 2 * * * cd /path/to/scraper && python scheduler.py run --full ...
# ...
```

---

## Usage

### Manual Scraping

**Incremental scrape** (only new/updated tenders):
```bash
python scheduler.py run --incremental
```

**Full scrape** (all tenders):
```bash
python scheduler.py run --full
```

**Limited scrape** (for testing):
```bash
python scheduler.py run --incremental --max-pages 5
```

### View History

**Recent jobs:**
```bash
python scheduler.py history
```

**Last 50 jobs:**
```bash
python scheduler.py history --limit 50
```

**Output:**
```
============================================
SCRAPING JOB HISTORY
============================================

Job ID: a1b2c3d4-...
  Started: 2024-11-22 10:00:15
  Completed: 2024-11-22 10:15:42
  Status: completed
  Spider: nabavki
  Incremental: True
  Tenders: 47
  Documents: 123
  Errors: 0

Job ID: e5f6g7h8-...
  Started: 2024-11-22 09:00:12
  Completed: 2024-11-22 09:18:35
  Status: completed
  Spider: nabavki
  Incremental: True
  Tenders: 52
  Documents: 145
  Errors: 1
```

### Health Check

**Check scraper health:**
```bash
python scripts/health_check.py
```

**Output:**
```
============================================
SCRAPER HEALTH CHECK
============================================
Timestamp: 2024-11-22 12:00:00 UTC

Last successful scrape: 2024-11-22 11:00:15
  (1.0 hours ago)
  Tenders: 47
  Documents: 123

Recent jobs (last 10):
  Failed: 1
  Error rate: 10.0%

Average job duration: 14.5 minutes

✓ Status: HEALTHY
============================================
```

---

## Scraping Schedules

### Hourly Incremental Scrape

**Schedule:** Every hour (0 * * * *)
**Command:** `python scheduler.py run --incremental`
**Purpose:** Catch new tenders quickly
**Log:** `logs/scraper_hourly.log`

**Behavior:**
- Only scrapes tenders published/updated since last scrape
- Fast execution (~5-15 minutes)
- Minimal server load

### Daily Full Scrape

**Schedule:** Every day at 2 AM (0 2 * * *)
**Command:** `python scheduler.py run --full`
**Purpose:** Ensure data consistency, catch missed tenders
**Log:** `logs/scraper_daily.log`

**Behavior:**
- Scrapes all active tenders
- Longer execution (~30-60 minutes)
- Backup against incremental scraping issues

### Weekly Deep Scrape

**Schedule:** Sunday at 3 AM (0 3 * * 0)
**Command:** `python scheduler.py run --full --max-pages 1000`
**Purpose:** Comprehensive data refresh, historical data
**Log:** `logs/scraper_weekly.log`

**Behavior:**
- Scrapes up to 1000 pages
- Includes closed/archived tenders
- Longest execution (~2-4 hours)

---

## Incremental Scraping Logic

### How It Works

```python
last_scrape_time = get_last_successful_scrape_time()  # e.g., 2024-11-22 10:00:00

for tender in discovered_tenders:
    if tender.is_new:
        scrape(tender)  # New tender
    elif tender.updated_at > last_scrape_time:
        scrape(tender)  # Updated since last scrape
    else:
        skip(tender)     # Already up-to-date
```

### Benefits

- **Faster execution** - Only process changed data
- **Reduced server load** - Fewer requests to source website
- **Lower bandwidth** - Skip unchanged documents
- **Real-time updates** - Hourly scraping catches changes quickly

### Fallback

If incremental scraping misses data:
- Daily full scrape catches everything
- Weekly deep scrape ensures completeness

---

## Job Tracking

### Job Lifecycle

1. **Start job:**
   ```sql
   INSERT INTO scraping_jobs (started_at, status, spider_name, incremental)
   VALUES (NOW(), 'running', 'nabavki', true)
   RETURNING job_id
   ```

2. **Run spider:**
   - Scrape tenders
   - Parse documents
   - Store in database

3. **Complete job:**
   ```sql
   UPDATE scraping_jobs SET
       completed_at = NOW(),
       status = 'completed',
       tenders_scraped = 47,
       documents_scraped = 123,
       errors_count = 0
   WHERE job_id = '...'
   ```

### Statistics Tracked

- `started_at` - Job start time
- `completed_at` - Job end time
- `status` - 'running', 'completed', 'failed'
- `tenders_scraped` - Number of tenders processed
- `documents_scraped` - Number of documents downloaded
- `errors_count` - Number of errors encountered
- `error_message` - Error details (if failed)

---

## Error Handling

### Retry Logic

Built into Scrapy:
```python
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]
```

### Error Recovery

**If spider crashes:**
- Job marked as 'failed' in database
- Error message stored
- Next scheduled run will retry

**If individual tender fails:**
- Spider continues with other tenders
- Error logged
- Tender retried in next scrape

### Monitoring

Health check detects:
- No successful scrapes in 24 hours → Alert
- Error rate > 50% → Alert
- Jobs taking > 1 hour → Warning

---

## Logs

### Log Files

```
logs/
├── scraper_hourly.log   # Hourly incremental scrapes
├── scraper_daily.log    # Daily full scrapes
├── scraper_weekly.log   # Weekly deep scrapes
└── health_check.log     # Health check results
```

### Log Format

```
2024-11-22 10:00:15 [scheduler] INFO: Starting scrape: spider=nabavki, incremental=True
2024-11-22 10:00:16 [scheduler] INFO: Last scrape: 2024-11-22 09:00:12
2024-11-22 10:00:20 [nabavki] INFO: Parsing listing page: https://...
2024-11-22 10:00:25 [nabavki] INFO: Found 47 tender links
2024-11-22 10:15:40 [scheduler] INFO: Completed job a1b2c3d4: completed, 47 tenders, 123 documents
```

### View Logs

**Real-time monitoring:**
```bash
tail -f logs/scraper_hourly.log
```

**Recent errors:**
```bash
grep ERROR logs/scraper_hourly.log | tail -20
```

**Job summaries:**
```bash
grep "Completed job" logs/scraper_hourly.log
```

### Log Rotation

**Automatic:** Old logs deleted weekly (Monday 4 AM)
```bash
# Cron job
find logs -name "*.log" -mtime +30 -delete
```

**Manual rotation:**
```bash
cd logs
gzip scraper_hourly.log
mv scraper_hourly.log.gz archive/
touch scraper_hourly.log
```

---

## Health Monitoring

### Health Metrics

**Last successful scrape:**
- Green: < 2 hours ago
- Yellow: 2-24 hours ago
- Red: > 24 hours ago

**Error rate (last 10 jobs):**
- Green: < 20%
- Yellow: 20-50%
- Red: > 50%

**Job duration:**
- Green: < 30 minutes
- Yellow: 30-60 minutes
- Red: > 1 hour

### Alerting

**Manual alerts:**
```bash
# Check health and send email on failure
python scripts/health_check.py || echo "Scraper unhealthy" | mail -s "Alert" admin@example.com
```

**Automated monitoring:**
Add to cron:
```cron
0 6 * * * cd /path/to/scraper && python scripts/health_check.py || curl https://healthchecks.io/ping/your-uuid
```

---

## Troubleshooting

### Cron jobs not running

**Check cron service:**
```bash
# Ubuntu/Debian
sudo service cron status

# macOS
sudo launchctl list | grep cron
```

**Check crontab:**
```bash
crontab -l
```

**Check cron logs:**
```bash
# Ubuntu/Debian
grep CRON /var/log/syslog

# macOS
grep cron /var/log/system.log
```

### Scraper failing

**Check logs:**
```bash
tail -100 logs/scraper_hourly.log
```

**Run manually to see errors:**
```bash
python scheduler.py run --incremental
```

**Common issues:**
- DATABASE_URL not set → Set environment variable
- Scrapy dependencies missing → `pip install -r requirements.txt`
- Permission denied → `chmod +x scripts/health_check.py`

### Database connection errors

**Test connection:**
```bash
python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('$DATABASE_URL'))"
```

**Check DATABASE_URL:**
```bash
echo $DATABASE_URL
```

**Verify PostgreSQL running:**
```bash
pg_isready -h localhost -p 5432
```

---

## Uninstalling

### Remove Cron Jobs

**Option 1: Remove all cron jobs**
```bash
crontab -r
```

**Option 2: Edit crontab manually**
```bash
crontab -e
# Delete scraper-related lines
```

### Restore Backup

```bash
# Find backup
ls -la logs/crontab_backup_*

# Restore
crontab logs/crontab_backup_20241122_100000.txt
```

---

## Performance

### Resource Usage

**Hourly incremental scrape:**
- Duration: 5-15 minutes
- CPU: Low (5-10%)
- Memory: ~200MB
- Network: ~10MB download

**Daily full scrape:**
- Duration: 30-60 minutes
- CPU: Medium (10-20%)
- Memory: ~500MB
- Network: ~100MB download

**Weekly deep scrape:**
- Duration: 2-4 hours
- CPU: Medium (15-25%)
- Memory: ~1GB
- Network: ~500MB download

### Optimization

**Reduce scraping frequency:**
```cron
# Every 2 hours instead of hourly
0 */2 * * * ...
```

**Limit pages scraped:**
```bash
python scheduler.py run --incremental --max-pages 50
```

**Adjust concurrency:**
Edit `settings.py`:
```python
CONCURRENT_REQUESTS = 2  # Increase for faster scraping
DOWNLOAD_DELAY = 0.5     # Decrease for faster scraping (be respectful!)
```

---

## Summary

**Automated scraping system with:**

✅ **Periodic scraping** (hourly, daily, weekly)
✅ **Incremental updates** (only new/changed data)
✅ **Job tracking** (database-backed history)
✅ **Error handling** (retry logic, graceful failures)
✅ **Health monitoring** (automatic alerts)
✅ **Cron management** (easy installation)
✅ **Comprehensive logging** (rotation, real-time monitoring)

**Schedule:**
- Hourly: Incremental scrape (catch new tenders)
- Daily: Full scrape (ensure consistency)
- Weekly: Deep scrape (historical data)

**Monitoring:**
- Health checks (daily)
- Job history tracking
- Error rate analysis
- Duration monitoring
