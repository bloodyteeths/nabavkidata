# Scraper Automation Quick Reference Card

Fast reference for common operations and troubleshooting.

## Essential Commands

### Deployment

```bash
# Upload to EC2
scp -i ~/.ssh/nabavki-key.pem -r scraper/jobs scraper/deployment ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/

# Connect to EC2
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153

# Deploy automation
cd /home/ubuntu/nabavkidata/scraper/deployment
./deploy_automation.sh

# Verify deployment
./verify_automation.sh
```

### Monitoring

```bash
# Dashboard
python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py

# Quick stats
psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"

# Recent logs
ls -lht /home/ubuntu/nabavkidata/scraper/logs/ | head

# Active processes
ps aux | grep scrapy

# Disk usage
df -h /home/ubuntu
```

### Cron Management

```bash
# View all jobs
crontab -l

# Edit jobs
crontab -e

# Remove all automation
crontab -l | grep -v "nabavkidata" | crontab -

# Restore backup
crontab /tmp/crontab_backup_TIMESTAMP.txt

# Check execution
grep CRON /var/log/syslog | tail -20
```

### Log Management

```bash
# View specific logs
tail -f /home/ubuntu/nabavkidata/scraper/logs/cron_active.log
tail -f /home/ubuntu/nabavkidata/scraper/logs/health_check.log

# Find errors
grep -i error /home/ubuntu/nabavkidata/scraper/logs/*.log | tail -50

# Log sizes
du -sh /home/ubuntu/nabavkidata/scraper/logs/*

# Manual rotation
/home/ubuntu/nabavkidata/scraper/jobs/rotate_logs.sh
```

### Manual Job Execution

```bash
# Active scraper
/home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh

# Awards scraper
/home/ubuntu/nabavkidata/scraper/jobs/scrape_awards.sh

# Health check
/home/ubuntu/nabavkidata/scraper/jobs/health_check.sh

# Backup
/home/ubuntu/nabavkidata/scraper/jobs/backup_db.sh

# Log rotation
/home/ubuntu/nabavkidata/scraper/jobs/rotate_logs.sh
```

## Schedule Reference

| Time (UTC) | Job                | Frequency    |
|------------|-------------------|--------------|
| 01:00      | Log rotation      | Daily        |
| 02:00      | Backfill          | Weekly (Sun) |
| 03:00      | Vector refresh    | Daily        |
| 04:00      | Active scrape     | Daily        |
| 05:00      | Database backup   | Daily        |
| 06:00      | Awards scrape     | Daily        |
| 10:00      | Active scrape     | Daily        |
| 16:00      | Active scrape     | Daily        |
| 22:00      | Active scrape     | Daily        |
| */5        | Health check      | Continuous   |
| */15       | Documents         | Continuous   |

## File Locations

```
/home/ubuntu/nabavkidata/scraper/
├── jobs/                    # Automation scripts
├── logs/                    # All log files
└── deployment/              # Deployment tools

/home/ubuntu/backups/        # Database backups
```

## Troubleshooting Quick Fixes

### Cron not running
```bash
sudo systemctl restart cron
```

### Environment not found
```bash
source /home/ubuntu/nabavkidata/venv/bin/activate
export DATABASE_URL="postgresql://..."
```

### Permission denied
```bash
chmod +x /home/ubuntu/nabavkidata/scraper/jobs/*.sh
```

### Database connection failed
```bash
echo $DATABASE_URL  # Verify set
psql $DATABASE_URL -c "SELECT 1"  # Test connection
```

### Disk full
```bash
/home/ubuntu/nabavkidata/scraper/jobs/rotate_logs.sh
find /home/ubuntu/nabavkidata/scraper/logs -name "*.log.gz" -mtime +30 -delete
```

### Too many processes
```bash
pkill -f scrapy  # Kill all scrapers
ps aux | grep scrapy  # Verify killed
```

## Health Check Alerts

Alert triggers:
- No scrape in 6 hours
- >10 errors in recent logs
- Database connection failed
- Disk usage >90%
- >5 scraper processes running

## Performance Tuning

### Faster scraping
Edit job scripts, increase:
```python
'CONCURRENT_REQUESTS': 32,  # Default: 16
'DOWNLOAD_DELAY': 0.25,     # Default: 0.5
```

### Slower scraping (be polite)
```python
'CONCURRENT_REQUESTS': 8,
'DOWNLOAD_DELAY': 1.0,
```

### More aggressive log rotation
```bash
# Edit rotate_logs.sh, change:
-mtime +7  # to +3 (compress after 3 days)
-mtime +30 # to +14 (delete after 14 days)
```

## Backup & Recovery

### Manual backup
```bash
/home/ubuntu/nabavkidata/scraper/jobs/backup_db.sh
```

### List backups
```bash
ls -lh /home/ubuntu/backups/
```

### Restore backup
```bash
gunzip -c /home/ubuntu/backups/nabavkidata_TIMESTAMP.sql.gz | psql $DATABASE_URL
```

### S3 backup (optional)
```bash
export AWS_S3_BACKUP_BUCKET="my-bucket"
# Backup script will auto-upload
```

## Database Queries

### Quick stats
```sql
-- Total tenders
SELECT COUNT(*) FROM tenders;

-- Today's scrapes
SELECT COUNT(*) FROM tenders WHERE scraped_at >= CURRENT_DATE;

-- Active tenders
SELECT COUNT(*) FROM tenders WHERE status = 'open' AND closing_date >= CURRENT_DATE;

-- Status breakdown
SELECT status, COUNT(*) FROM tenders GROUP BY status;

-- Recent awards
SELECT COUNT(*) FROM tenders WHERE status = 'awarded' AND scraped_at >= NOW() - INTERVAL '7 days';
```

### Performance
```sql
-- Create indexes
CREATE INDEX idx_tenders_scraped_at ON tenders(scraped_at DESC);
CREATE INDEX idx_tenders_status ON tenders(status);

-- Vacuum
VACUUM ANALYZE tenders;

-- Database size
SELECT pg_size_pretty(pg_database_size('nabavkidata'));
```

## Emergency Procedures

### Stop all automation
```bash
# Remove all cron jobs
crontab -r

# Kill running scrapers
pkill -f scrapy
```

### Restart automation
```bash
# Restore crontab
crontab /tmp/crontab_backup_TIMESTAMP.txt

# Or reinstall
cd /home/ubuntu/nabavkidata/scraper/deployment
./deploy_automation.sh
```

### Clear logs
```bash
# Compress all logs
find /home/ubuntu/nabavkidata/scraper/logs -name "*.log" -exec gzip {} \;

# Delete old compressed
find /home/ubuntu/nabavkidata/scraper/logs -name "*.log.gz" -mtime +7 -delete
```

## Useful Aliases

Add to `~/.bashrc`:

```bash
# Scraper shortcuts
alias scraper-status='python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py'
alias scraper-logs='cd /home/ubuntu/nabavkidata/scraper/logs'
alias scraper-jobs='cd /home/ubuntu/nabavkidata/scraper/jobs'
alias scraper-cron='crontab -l | grep nabavkidata'
alias scraper-health='/home/ubuntu/nabavkidata/scraper/jobs/health_check.sh'

# Database shortcuts
alias db-count='psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"'
alias db-stats='psql $DATABASE_URL -c "SELECT status, COUNT(*) FROM tenders GROUP BY status"'
alias db-size='psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size(current_database()))"'
```

Then: `source ~/.bashrc`

## Contact & Support

- **Logs**: `/home/ubuntu/nabavkidata/scraper/logs/`
- **Documentation**: `/home/ubuntu/nabavkidata/scraper/deployment/AUTOMATION_README.md`
- **Deployment Guide**: `/home/ubuntu/nabavkidata/scraper/deployment/EC2_DEPLOYMENT_GUIDE.md`
- **Verify Script**: `/home/ubuntu/nabavkidata/scraper/deployment/verify_automation.sh`

## Version Info

- **Created**: 2025-11-24
- **Automation Version**: 1.0
- **Target EC2**: 3.120.26.153
- **Cron Jobs**: 8 automated tasks
