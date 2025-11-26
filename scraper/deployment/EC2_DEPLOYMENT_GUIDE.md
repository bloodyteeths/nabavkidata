# EC2 Deployment Guide for Scraper Automation

Step-by-step guide for deploying the automation infrastructure to EC2.

## Prerequisites

- EC2 instance IP: `3.120.26.153`
- SSH key: `~/.ssh/nabavki-key.pem`
- Database URL configured on EC2
- Python virtual environment set up

## Deployment Steps

### Step 1: Prepare Local Files

From your local machine (in the project root):

```bash
# Navigate to project root
cd /Users/tamsar/Downloads/nabavkidata

# Verify all job scripts exist
ls -la scraper/jobs/*.sh

# Verify deployment scripts exist
ls -la scraper/deployment/
```

Expected output:
```
scraper/jobs/
  - scrape_active.sh
  - scrape_awards.sh
  - scrape_backfill.sh
  - process_documents.sh
  - refresh_vectors.sh
  - health_check.sh
  - rotate_logs.sh
  - backup_db.sh

scraper/deployment/
  - deploy_automation.sh
  - monitor_dashboard.py
  - crontab_additions.txt
  - AUTOMATION_README.md
  - EC2_DEPLOYMENT_GUIDE.md
```

### Step 2: Upload Files to EC2

```bash
# Upload job scripts
scp -i ~/.ssh/nabavki-key.pem scraper/jobs/*.sh \
    ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/jobs/

# Upload deployment files
scp -i ~/.ssh/nabavki-key.pem scraper/deployment/* \
    ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/deployment/
```

Verify upload:
```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153 "ls -la /home/ubuntu/nabavkidata/scraper/jobs/"
```

### Step 3: Connect to EC2

```bash
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
```

### Step 4: Verify Environment

Once connected to EC2:

```bash
# Check current directory structure
ls -la /home/ubuntu/nabavkidata/

# Verify virtual environment exists
ls -la /home/ubuntu/nabavkidata/venv/

# Activate virtual environment
source /home/ubuntu/nabavkidata/venv/bin/activate

# Check Python packages
pip list | grep -E "scrapy|asyncpg|beautifulsoup"

# Verify DATABASE_URL is set
echo $DATABASE_URL
# If not set, add to .bashrc or .env file
```

### Step 5: Set Environment Variables

```bash
# Edit .bashrc to add environment variables
nano ~/.bashrc

# Add these lines at the end:
export DATABASE_URL="postgresql://user:password@host:5432/nabavkidata"
export PATH="/home/ubuntu/nabavkidata/venv/bin:$PATH"

# Save and reload
source ~/.bashrc

# Verify
echo $DATABASE_URL
```

### Step 6: Test Database Connection

```bash
# Activate virtual environment
source /home/ubuntu/nabavkidata/venv/bin/activate

# Test connection
python3 << 'EOF'
import asyncio
import asyncpg
import os

async def test():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    count = await conn.fetchval('SELECT COUNT(*) FROM tenders')
    print(f'✓ Connected! Found {count} tenders')
    await conn.close()

asyncio.run(test())
EOF
```

Expected output:
```
✓ Connected! Found 15234 tenders
```

### Step 7: Run Deployment Script

```bash
# Navigate to deployment directory
cd /home/ubuntu/nabavkidata/scraper/deployment

# Make deployment script executable
chmod +x deploy_automation.sh

# Run deployment
./deploy_automation.sh
```

The script will:
1. Create directories (jobs, logs, backups)
2. Set permissions on job scripts
3. Backup existing crontab
4. Install new cron jobs
5. Verify environment
6. Test database connection
7. Run health check

Expected output:
```
==========================================
NABAVKIDATA SCRAPER AUTOMATION DEPLOYMENT
==========================================

Step 1: Creating directory structure...
[SUCCESS] Directories created

Step 2: Setting permissions on job scripts...
[SUCCESS] Job scripts are executable

Step 3: Backing up existing crontab...
[SUCCESS] Crontab backed up to /tmp/crontab_backup_20251124_120000.txt

Step 4: Checking for existing automation jobs...

Step 5: Installing cron jobs...
[SUCCESS] Cron jobs installed successfully

Step 6: Verifying environment...
[SUCCESS] Virtual environment found
[SUCCESS] DATABASE_URL is set

Step 7: Testing database connection...
Database connected successfully: 15234 tenders found
[SUCCESS] Database connection successful

Step 8: Testing job scripts (dry run)...
[SUCCESS] Health check script works

Step 9: Installed cron jobs:
==========================================
# NABAVKIDATA SCRAPER AUTOMATION
0 4,10,16,22 * * * /home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh
...
==========================================

==========================================
DEPLOYMENT COMPLETE!
==========================================
```

### Step 8: Verify Cron Jobs

```bash
# View all cron jobs
crontab -l

# Check for scraper jobs
crontab -l | grep nabavkidata

# Expected: 8 cron jobs for automation
```

### Step 9: Test Individual Jobs

```bash
# Test active scraper (this will actually run a scrape)
/home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh

# Monitor output
tail -f /home/ubuntu/nabavkidata/scraper/logs/scrape_active_*.log

# Test health check (safe to run)
/home/ubuntu/nabavkidata/scraper/jobs/health_check.sh

# Check health log
cat /home/ubuntu/nabavkidata/scraper/logs/health_check.log
```

### Step 10: Run Monitoring Dashboard

```bash
# Make dashboard executable
chmod +x /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py

# Run dashboard
python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py
```

Expected output:
```
================================================================================
NABAVKIDATA SCRAPER MONITORING DASHBOARD
================================================================================
Timestamp: 2025-11-24 12:00:00 UTC

DATABASE STATISTICS
--------------------------------------------------------------------------------
Total Tenders:        15,234
Scraped Today:        142
...
```

## Post-Deployment Verification

### 1. Check Cron Logs

Wait for next scheduled run (or manually trigger):

```bash
# View cron execution in system logs
grep CRON /var/log/syslog | tail -20

# View scraper-specific cron logs
tail -f /home/ubuntu/nabavkidata/scraper/logs/cron_active.log
```

### 2. Monitor First Automated Run

```bash
# Active scraper runs at 04:00, 10:00, 16:00, 22:00 UTC
# Wait for next scheduled time, or test manually:

/home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh

# In another terminal, monitor logs:
tail -f /home/ubuntu/nabavkidata/scraper/logs/scrape_active_*.log
```

### 3. Verify Database Growth

```bash
# Check tender count before
psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"

# Wait for scrape to complete

# Check tender count after
psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"

# Should see increase
```

### 4. Check Health Monitoring

```bash
# Health check runs every 5 minutes
# Wait 5 minutes, then check log

cat /home/ubuntu/nabavkidata/scraper/logs/health_check.log

# Should see recent entries like:
# [2025-11-24 12:05:00] Starting health check...
# [2025-11-24 12:05:01] OK: Recent scrape found
# [2025-11-24 12:05:02] OK: Error rate acceptable
```

### 5. Monitor Disk Usage

```bash
# Check disk space
df -h /home/ubuntu

# Check log directory size
du -sh /home/ubuntu/nabavkidata/scraper/logs/

# Check backup directory size
du -sh /home/ubuntu/backups/
```

## Troubleshooting

### Issue: Cron Jobs Not Running

```bash
# Check cron service
sudo systemctl status cron

# Restart cron
sudo systemctl restart cron

# Check for errors in syslog
grep CRON /var/log/syslog | grep -i error
```

### Issue: Environment Variables Not Found

Cron doesn't inherit shell environment. Solution:

```bash
# Option 1: Add to crontab directly
crontab -e

# Add at the top:
DATABASE_URL=postgresql://user:pass@host/db
PATH=/home/ubuntu/nabavkidata/venv/bin:/usr/local/bin:/usr/bin:/bin

# Option 2: Source environment in job scripts
# Already included in scripts:
source /home/ubuntu/nabavkidata/venv/bin/activate
```

### Issue: Permission Denied

```bash
# Fix permissions on job scripts
chmod +x /home/ubuntu/nabavkidata/scraper/jobs/*.sh

# Fix ownership
sudo chown -R ubuntu:ubuntu /home/ubuntu/nabavkidata/scraper/

# Verify
ls -la /home/ubuntu/nabavkidata/scraper/jobs/
```

### Issue: Database Connection Failed

```bash
# Test connection manually
source /home/ubuntu/nabavkidata/venv/bin/activate
python3 << 'EOF'
import asyncio
import asyncpg
import os

async def test():
    try:
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'), timeout=10)
        print('✓ Connection successful')
        await conn.close()
    except Exception as e:
        print(f'✗ Connection failed: {e}')

asyncio.run(test())
EOF
```

### Issue: Scraper Not Finding Spider

```bash
# Verify scraper directory structure
ls -la /home/ubuntu/nabavkidata/scraper/scraper/spiders/

# Check scrapy.cfg
cat /home/ubuntu/nabavkidata/scraper/scrapy.cfg

# Test scrapy directly
cd /home/ubuntu/nabavkidata/scraper
source /home/ubuntu/nabavkidata/venv/bin/activate
scrapy list
```

### Issue: Logs Not Being Created

```bash
# Check log directory exists and is writable
ls -ld /home/ubuntu/nabavkidata/scraper/logs/
mkdir -p /home/ubuntu/nabavkidata/scraper/logs/
chmod 755 /home/ubuntu/nabavkidata/scraper/logs/

# Run job with debug output
bash -x /home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh
```

## Monitoring Commands Reference

```bash
# Quick Status Check
python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py

# View All Cron Jobs
crontab -l

# Recent Cron Executions
grep CRON /var/log/syslog | tail -20

# Active Scrape Logs
tail -f /home/ubuntu/nabavkidata/scraper/logs/cron_active.log

# Health Check Logs
tail -f /home/ubuntu/nabavkidata/scraper/logs/health_check.log

# Database Tender Count
psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"

# Watch Database Growth
watch -n 5 'psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"'

# Recent Log Files
ls -lht /home/ubuntu/nabavkidata/scraper/logs/ | head -20

# Disk Usage
df -h /home/ubuntu
du -sh /home/ubuntu/nabavkidata/scraper/logs/
du -sh /home/ubuntu/backups/

# Running Processes
ps aux | grep -E "scrapy|python"

# Check Last Scrape Time
stat /home/ubuntu/nabavkidata/scraper/logs/scrape_active_*.log | grep Modify | tail -1
```

## Maintenance Tasks

### Weekly Maintenance

```bash
# Review logs for errors
grep -i error /home/ubuntu/nabavkidata/scraper/logs/*.log | tail -50

# Check disk usage
df -h

# Review backup status
ls -lh /home/ubuntu/backups/

# Run monitoring dashboard
python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py
```

### Monthly Maintenance

```bash
# Review and optimize database
psql $DATABASE_URL -c "VACUUM ANALYZE tenders"

# Check for stuck processes
ps aux | grep scrapy

# Review cron job timings
crontab -l

# Clean up old logs manually (if needed)
find /home/ubuntu/nabavkidata/scraper/logs -name "*.log.gz" -mtime +60 -delete
```

## Rollback Procedure

If you need to remove automation:

```bash
# Remove cron jobs
crontab -e
# Delete all lines between "NABAVKIDATA SCRAPER AUTOMATION" markers

# Or restore from backup
crontab /tmp/crontab_backup_YYYYMMDD_HHMMSS.txt

# Verify removal
crontab -l | grep nabavkidata
```

## Next Steps

1. **Monitor for 24 hours** - Ensure all scheduled jobs run successfully
2. **Review logs daily** - Check for errors or issues
3. **Adjust schedules** - Optimize timing based on data needs
4. **Set up alerts** - Configure email notifications
5. **Document findings** - Note any issues or optimizations

## Support Resources

- Automation README: `/home/ubuntu/nabavkidata/scraper/deployment/AUTOMATION_README.md`
- Job Scripts: `/home/ubuntu/nabavkidata/scraper/jobs/`
- Logs: `/home/ubuntu/nabavkidata/scraper/logs/`
- Monitoring: `monitor_dashboard.py`

## Success Criteria

Deployment is successful when:

- [ ] All 8 cron jobs are installed
- [ ] Health check runs every 5 minutes
- [ ] Active scraper runs on schedule (4x daily)
- [ ] Database connection works from all jobs
- [ ] Logs are being created
- [ ] Monitoring dashboard shows data
- [ ] No errors in health check logs
- [ ] Database tender count is increasing

## Contact

For deployment issues, check:
1. System logs: `/var/log/syslog`
2. Application logs: `/home/ubuntu/nabavkidata/scraper/logs/`
3. Health status: Run `health_check.sh`
