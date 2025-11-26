# Scraper Automation Infrastructure

Complete automation layer for EC2 with cron jobs, monitoring, and health checks.

## Overview

This automation infrastructure provides:

- **Automated scraping** - 4x daily active tenders, daily awards, weekly backfill
- **Document processing** - Every 15 minutes
- **Vector refresh** - Daily embedding updates
- **Health monitoring** - Every 5 minutes with alerts
- **Log management** - Daily rotation and compression
- **Database backups** - Daily backups with retention policy

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CRON SCHEDULER                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Active       │  │ Awards       │  │ Backfill     │ │
│  │ Scraper      │  │ Scraper      │  │ Scraper      │ │
│  │ 4x daily     │  │ Daily        │  │ Weekly       │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │          │
│         └─────────────────┴─────────────────┘          │
│                         │                              │
│                         ▼                              │
│              ┌──────────────────────┐                  │
│              │   PostgreSQL DB      │                  │
│              └──────────────────────┘                  │
│                         │                              │
│         ┌───────────────┴───────────────┐              │
│         ▼                               ▼              │
│  ┌──────────────┐              ┌──────────────┐       │
│  │ Document     │              │ Vector       │       │
│  │ Processor    │              │ Refresh      │       │
│  │ Every 15min  │              │ Daily        │       │
│  └──────────────┘              └──────────────┘       │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Health       │  │ Log          │  │ Database     │ │
│  │ Checks       │  │ Rotation     │  │ Backup       │ │
│  │ Every 5min   │  │ Daily        │  │ Daily        │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Schedule Overview

| Job                  | Frequency              | Time (UTC) | Purpose                          |
|----------------------|------------------------|------------|----------------------------------|
| Active tenders       | 4x daily              | 04:00, 10:00, 16:00, 22:00 | Capture new postings |
| Awards               | Daily                 | 06:00      | Competitor intelligence          |
| Historical backfill  | Weekly (Sunday)       | 02:00      | Trend data                       |
| Document processing  | Every 15 minutes      | */15       | Process document queue           |
| Vector refresh       | Daily                 | 03:00      | Update embeddings                |
| Health check         | Every 5 minutes       | */5        | Monitor system status            |
| Log rotation         | Daily                 | 01:00      | Prevent disk fill                |
| Database backup      | Daily                 | 05:00      | Data protection                  |

## Directory Structure

```
/home/ubuntu/nabavkidata/scraper/
├── jobs/                          # Automation scripts
│   ├── scrape_active.sh          # Active tenders scraper
│   ├── scrape_awards.sh          # Awards scraper
│   ├── scrape_backfill.sh        # Historical backfill
│   ├── process_documents.sh      # Document processor
│   ├── refresh_vectors.sh        # Vector/embedding refresh
│   ├── health_check.sh           # Health monitoring
│   ├── rotate_logs.sh            # Log rotation
│   └── backup_db.sh              # Database backup
│
├── logs/                          # Log files
│   ├── scrape_active_*.log       # Active scrape logs
│   ├── scrape_awards_*.log       # Awards scrape logs
│   ├── scrape_backfill_*.log     # Backfill logs
│   ├── process_documents_*.log   # Document processing logs
│   ├── refresh_vectors_*.log     # Vector refresh logs
│   ├── health_check.log          # Health check logs
│   ├── rotate.log                # Log rotation logs
│   ├── backup_*.log              # Backup logs
│   └── cron_*.log                # Cron execution logs
│
└── deployment/                    # Deployment tools
    ├── deploy_automation.sh       # Main deployment script
    ├── monitor_dashboard.py       # Monitoring dashboard
    ├── crontab_additions.txt      # Cron job definitions
    └── AUTOMATION_README.md       # This file

/home/ubuntu/backups/              # Database backups
└── nabavkidata_*.sql.gz          # Compressed backups
```

## Installation

### Step 1: Upload Files to EC2

```bash
# From your local machine
scp -i ~/.ssh/nabavki-key.pem -r scraper/jobs ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/
scp -i ~/.ssh/nabavki-key.pem -r scraper/deployment ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/
```

### Step 2: SSH to EC2

```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
```

### Step 3: Run Deployment Script

```bash
cd /home/ubuntu/nabavkidata/scraper/deployment
chmod +x deploy_automation.sh
./deploy_automation.sh
```

The deployment script will:
1. Create necessary directories
2. Set permissions on job scripts
3. Backup existing crontab
4. Install new cron jobs
5. Verify environment and database connection
6. Test job scripts

## Verification

### View Installed Cron Jobs

```bash
crontab -l
```

### Test Individual Jobs

```bash
# Test active scraper
/home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh

# Test health check
/home/ubuntu/nabavkidata/scraper/jobs/health_check.sh

# Test log rotation
/home/ubuntu/nabavkidata/scraper/jobs/rotate_logs.sh
```

### Monitor Logs

```bash
# View active scrape logs
tail -f /home/ubuntu/nabavkidata/scraper/logs/cron_active.log

# View all recent logs
ls -lht /home/ubuntu/nabavkidata/scraper/logs/ | head -20

# View cron execution in system logs
grep CRON /var/log/syslog | tail -20
```

### Run Monitoring Dashboard

```bash
# Make dashboard executable
chmod +x /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py

# Run dashboard
python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py
```

Example output:

```
================================================================================
NABAVKIDATA SCRAPER MONITORING DASHBOARD
================================================================================
Timestamp: 2025-11-24 12:00:00 UTC

DATABASE STATISTICS
--------------------------------------------------------------------------------
Total Tenders:        15,234
Scraped Today:        142
Scraped This Week:    1,056
Active Tenders:       856
Recent Awards (7d):   234

TENDER STATUS BREAKDOWN
--------------------------------------------------------------------------------
  open                      856
  awarded                   678
  closed                    543
  cancelled                  45

DOCUMENT PROCESSING
--------------------------------------------------------------------------------
Total Documents:      3,456
  Completed:          3,200
  Pending:            156
  Processing:         12
  Failed:             88
Success Rate (7d):    92.45%

HEALTH INDICATORS
--------------------------------------------------------------------------------
  Scraping Activity:  ✓ Active
  Document Queue:     ✓ Healthy
  Success Rate:       ✓ Good
```

## Monitoring and Alerts

### Health Check System

The health check runs every 5 minutes and monitors:

1. **Last scrape timestamp** - Alerts if no scrape in 6 hours
2. **Error rate** - Alerts if >10 errors in recent logs
3. **Database connectivity** - Alerts if connection fails
4. **Disk space** - Alerts if >90% full
5. **Process count** - Alerts if too many stuck processes

### Email Alerts

Configure email alerts by setting up `mail` or `sendmail`:

```bash
# Install mailutils
sudo apt-get install mailutils

# Configure email (interactive)
sudo dpkg-reconfigure postfix
```

Update alert email in health_check.sh:
```bash
ALERT_EMAIL="your-email@example.com"
```

### Monitoring Database Growth

```bash
# Watch database growth in real-time
watch -n 5 'psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"'

# Check database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('nabavkidata'))"
```

## Log Management

### Log Rotation Policy

- **Compression**: Logs older than 7 days are compressed with gzip
- **Deletion**: Compressed logs older than 30 days are deleted
- **Retention**: 7 days of active logs + 30 days of compressed logs = 37 days total

### Manual Log Management

```bash
# View log sizes
du -sh /home/ubuntu/nabavkidata/scraper/logs/*

# Manually compress old logs
find /home/ubuntu/nabavkidata/scraper/logs -name "*.log" -mtime +7 -exec gzip {} \;

# Delete very old compressed logs
find /home/ubuntu/nabavkidata/scraper/logs -name "*.log.gz" -mtime +60 -delete
```

## Database Backup

### Backup Policy

- **Frequency**: Daily at 5 AM UTC
- **Retention**: 7 days of backups
- **Location**: `/home/ubuntu/backups/`
- **Format**: Compressed SQL dumps (`.sql.gz`)

### Manual Backup

```bash
# Create manual backup
/home/ubuntu/nabavkidata/scraper/jobs/backup_db.sh

# List backups
ls -lh /home/ubuntu/backups/

# Restore from backup
gunzip -c /home/ubuntu/backups/nabavkidata_20251124.sql.gz | psql $DATABASE_URL
```

### Optional: S3 Offsite Backup

Set environment variable to enable S3 uploads:

```bash
export AWS_S3_BACKUP_BUCKET="nabavkidata-backups"
```

## Troubleshooting

### Cron Jobs Not Running

```bash
# Check cron service status
sudo systemctl status cron

# Restart cron service
sudo systemctl restart cron

# Check for syntax errors in crontab
crontab -l | grep -v "^#" | grep .
```

### Environment Variables Not Available

Cron jobs don't inherit shell environment. Add to crontab:

```bash
# Edit crontab
crontab -e

# Add at the top
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
DATABASE_URL=postgresql://user:pass@host/db
```

### Job Script Failures

```bash
# Run with bash -x for debugging
bash -x /home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh

# Check permissions
ls -l /home/ubuntu/nabavkidata/scraper/jobs/

# Check virtual environment
source /home/ubuntu/nabavkidata/venv/bin/activate
which python3
python3 --version
```

### Database Connection Issues

```bash
# Test connection manually
source /home/ubuntu/nabavkidata/venv/bin/activate
python3 -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect(os.getenv('DATABASE_URL')))"

# Check DATABASE_URL
echo $DATABASE_URL

# Test with psql
psql $DATABASE_URL -c "SELECT version()"
```

### High Disk Usage

```bash
# Check disk usage
df -h

# Find large files
du -sh /home/ubuntu/nabavkidata/scraper/logs/*
du -sh /home/ubuntu/backups/*

# Clean up manually
/home/ubuntu/nabavkidata/scraper/jobs/rotate_logs.sh
```

## Maintenance

### Updating Job Scripts

```bash
# Edit job script
nano /home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh

# Test changes
bash /home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh

# Cron will use updated version automatically
```

### Modifying Schedule

```bash
# Edit crontab
crontab -e

# Modify timing, e.g., change active scrapes to 2x daily
0 6,18 * * * /home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh
```

### Adding New Jobs

```bash
# Create new job script
nano /home/ubuntu/nabavkidata/scraper/jobs/my_new_job.sh

# Make executable
chmod +x /home/ubuntu/nabavkidata/scraper/jobs/my_new_job.sh

# Add to crontab
crontab -e
# Add line: 0 12 * * * /home/ubuntu/nabavkidata/scraper/jobs/my_new_job.sh
```

## Performance Optimization

### Scraper Performance

Tune these settings in job scripts:

```python
settings.update({
    'CONCURRENT_REQUESTS': 16,      # Increase for more parallelism
    'DOWNLOAD_DELAY': 0.5,          # Decrease for faster scraping
    'CLOSESPIDER_ITEMCOUNT': 10000, # Increase to scrape more per run
})
```

### Database Performance

```sql
-- Create indexes for faster queries
CREATE INDEX idx_tenders_scraped_at ON tenders(scraped_at DESC);
CREATE INDEX idx_tenders_status ON tenders(status);
CREATE INDEX idx_tenders_closing_date ON tenders(closing_date);
CREATE INDEX idx_documents_status ON documents(status);
```

### Log Storage Optimization

```bash
# More aggressive compression (after 3 days instead of 7)
find /home/ubuntu/nabavkidata/scraper/logs -name "*.log" -mtime +3 -exec gzip {} \;

# Keep compressed logs for shorter period (14 days instead of 30)
find /home/ubuntu/nabavkidata/scraper/logs -name "*.log.gz" -mtime +14 -delete
```

## Security Considerations

1. **Database credentials**: Never log DATABASE_URL or credentials
2. **Email alerts**: Use secure SMTP with authentication
3. **Backup storage**: Encrypt backups if storing sensitive data
4. **Log access**: Restrict log directory permissions

```bash
# Secure log directory
chmod 750 /home/ubuntu/nabavkidata/scraper/logs
chown ubuntu:ubuntu /home/ubuntu/nabavkidata/scraper/logs

# Secure backup directory
chmod 700 /home/ubuntu/backups
```

## Monitoring Dashboards

### Quick Stats Command

```bash
# Create alias for quick stats
echo "alias scraper-stats='python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py'" >> ~/.bashrc
source ~/.bashrc

# Run
scraper-stats
```

### Continuous Monitoring

```bash
# Watch dashboard with auto-refresh every 30 seconds
watch -n 30 python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py
```

## Support

For issues or questions:

1. Check logs: `/home/ubuntu/nabavkidata/scraper/logs/`
2. Run health check: `/home/ubuntu/nabavkidata/scraper/jobs/health_check.sh`
3. View monitoring dashboard: `monitor_dashboard.py`
4. Check system logs: `grep CRON /var/log/syslog`

## License

Copyright (c) 2025 Nabavkidata. All rights reserved.
