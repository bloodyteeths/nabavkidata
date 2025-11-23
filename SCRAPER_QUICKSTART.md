# Scraper Quick Start Guide

Get the scraper system up and running in 5 minutes.

---

## Prerequisites

1. Python 3.8+ installed
2. PostgreSQL database running
3. Environment variables configured

---

## Step 1: Database Setup

Create the `scraping_jobs` table:

```sql
-- Connect to your database
psql $DATABASE_URL

-- Create scraping_jobs table
CREATE TABLE IF NOT EXISTS scraping_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    tenders_scraped INTEGER DEFAULT 0,
    documents_scraped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    error_message TEXT,
    spider_name VARCHAR(100),
    incremental BOOLEAN DEFAULT TRUE,
    last_scraped_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_status ON scraping_jobs(status);
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_started_at ON scraping_jobs(started_at DESC);

-- Verify
SELECT COUNT(*) FROM scraping_jobs;
```

---

## Step 2: Environment Variables

Add to your `.env` file:

```bash
# Database (required)
DATABASE_URL=postgresql://user:pass@localhost:5432/nabavkidata

# Email alerts (optional but recommended)
ADMIN_EMAIL=admin@nabavkidata.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@nabavkidata.com
FROM_NAME=Nabavkidata Scraper

# Frontend (optional)
FRONTEND_URL=http://localhost:3000
```

---

## Step 3: Install Dependencies

```bash
# Backend dependencies (if not already installed)
cd backend
pip install aiosmtplib

# Scraper dependencies
cd ../scraper
pip install aiohttp aiofiles asyncpg
```

---

## Step 4: Test the Scraper

### Option A: Run Manual Test Scrape
```bash
cd scraper
python scheduler.py run --max-pages 2

# Expected output:
# Starting scrape: spider=nabavki, incremental=True
# Job ID: 550e8400-...
# Status: completed
# Tenders scraped: 15
# Documents scraped: 42
```

### Option B: Start Backend API
```bash
cd backend
uvicorn main:app --reload

# In another terminal, test health endpoint:
curl http://localhost:8000/api/scraper/health
```

---

## Step 5: Verify Everything Works

### 1. Check Database
```sql
-- View scraping jobs
SELECT job_id, status, tenders_scraped, documents_scraped, completed_at
FROM scraping_jobs
ORDER BY started_at DESC
LIMIT 5;

-- Check for duplicates prevention
SELECT tender_id, file_url, COUNT(*)
FROM documents
GROUP BY tender_id, file_url
HAVING COUNT(*) > 1;
-- Should return 0 rows (no duplicates)
```

### 2. Test API Endpoints
```bash
# Health check (public)
curl http://localhost:8000/api/scraper/health

# Login as admin
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password"}' \
  | jq -r '.access_token')

# Get job history
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/scraper/jobs

# Trigger manual scrape
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"incremental": true, "max_pages": 1}' \
  http://localhost:8000/api/scraper/trigger
```

### 3. Check Logs
```bash
# Scraper logs
tail -f scraper/logs/scraper.log

# Look for:
# - "✓ Document saved" (successful saves)
# - "Skipping duplicate document" (duplicate prevention)
# - "Validation passed" (data validation)
# - "Download complete" (PDF downloads)
```

### 4. Test Email Alerts
```bash
# Force a scraper failure to test email
export DATABASE_URL="invalid://connection"
python scraper/scheduler.py run

# Check your ADMIN_EMAIL inbox for alert
# Should receive "[ALERT] Scraper Job Failed" email
```

---

## Common Issues & Solutions

### Issue: "scraping_jobs table not found"
**Solution:** Run the SQL from Step 1 to create the table

### Issue: "SMTP authentication failed"
**Solution:**
- Gmail: Use App Password, not regular password
- Enable "Less secure app access" if needed
- Or skip email alerts by not setting SMTP variables

### Issue: "Module aiohttp not found"
**Solution:**
```bash
pip install aiohttp aiofiles asyncpg aiosmtplib
```

### Issue: "Permission denied" on file download
**Solution:**
```bash
mkdir -p scraper/downloads/files
chmod 755 scraper/downloads/files
```

### Issue: PDF extraction fails
**Solution:**
```bash
# Install PyMuPDF
pip install pymupdf
```

---

## Quick Reference

### Run Scraper Manually
```bash
# Full scrape
python scraper/scheduler.py run --full

# Incremental scrape (only new)
python scraper/scheduler.py run --incremental

# Test mode (limit pages)
python scraper/scheduler.py run --max-pages 5

# View history
python scraper/scheduler.py history --limit 10
```

### API Endpoints
```bash
# Base URL
http://localhost:8000/api/scraper

# Public
GET /health

# Admin only
GET /jobs
GET /status
POST /trigger
```

### Monitoring
```bash
# Check health
curl http://localhost:8000/api/scraper/health | jq '.status'

# Watch for failures
watch -n 60 'curl -s http://localhost:8000/api/scraper/health | jq ".error_rate"'

# Monitor logs
tail -f scraper/logs/scraper.log | grep -E 'ERROR|WARNING|✓'
```

---

## Production Deployment

### 1. Set Up Cron Job
```bash
# Edit crontab
crontab -e

# Add scheduled scraping (every 6 hours)
0 */6 * * * cd /path/to/scraper && python scheduler.py run --incremental

# Or daily at 2 AM
0 2 * * * cd /path/to/scraper && python scheduler.py run --incremental
```

### 2. Set Up Systemd Service (Optional)
```ini
# /etc/systemd/system/nabavki-scraper.service
[Unit]
Description=Nabavki Scraper Service
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/scraper
Environment="DATABASE_URL=postgresql://..."
ExecStart=/usr/bin/python3 scheduler.py run --incremental
Restart=on-failure
RestartSec=300

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable nabavki-scraper
sudo systemctl start nabavki-scraper
sudo systemctl status nabavki-scraper
```

### 3. Set Up Monitoring
```bash
# Add to monitoring service (e.g., Uptime Robot, Pingdom)
URL: https://nabavkidata.com/api/scraper/health
Check: HTTP status 200 AND response contains "healthy"
Interval: 5 minutes
```

---

## Next Steps

1. **Test with real data:** Remove `--max-pages` limit
2. **Monitor for 24h:** Check health endpoint every hour
3. **Review logs:** Look for validation warnings or errors
4. **Set up alerts:** Configure email alerts or Slack integration
5. **Schedule automated runs:** Add to cron or systemd
6. **Monitor performance:** Track average job duration

---

## Troubleshooting Commands

```bash
# Check if scraper is running
ps aux | grep scheduler.py

# Kill stuck scraper
pkill -f scheduler.py

# Clear old jobs (optional)
psql $DATABASE_URL -c "DELETE FROM scraping_jobs WHERE started_at < NOW() - INTERVAL '30 days';"

# Check disk space (for PDFs)
du -sh scraper/downloads/files/

# Test database connection
psql $DATABASE_URL -c "SELECT 1;"

# Verify email configuration
python -c "
import os
print('SMTP_USER:', os.getenv('SMTP_USER', 'NOT SET'))
print('ADMIN_EMAIL:', os.getenv('ADMIN_EMAIL', 'NOT SET'))
"
```

---

## Performance Tips

1. **Large PDFs:** Increase `DOWNLOAD_TIMEOUT` in settings if needed
2. **Rate Limiting:** Adjust `DOWNLOAD_DELAY` in settings.py
3. **Concurrent Requests:** Keep at 1 to be polite to the server
4. **Database:** Add indexes on frequently queried fields
5. **Disk Space:** Clean old PDFs periodically if needed

---

## Getting Help

- **Documentation:** See `SCRAPER_IMPROVEMENTS_SUMMARY.md`
- **API Reference:** See `SCRAPER_API_REFERENCE.md`
- **Logs:** Check `scraper/logs/scraper.log`
- **Database:** Query `scraping_jobs` table for history

---

## Success Checklist

- [ ] Database table created
- [ ] Environment variables configured
- [ ] Dependencies installed
- [ ] Test scrape completed successfully
- [ ] Health endpoint returns "healthy"
- [ ] No duplicate documents in database
- [ ] Email alerts working (optional)
- [ ] API endpoints accessible
- [ ] Logs show no critical errors
- [ ] Ready for production!
