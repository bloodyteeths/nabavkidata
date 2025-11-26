# Scraper Automation Deployment Checklist

Use this checklist when deploying automation infrastructure to EC2.

## Pre-Deployment Checklist

### Local Machine Setup

- [ ] All files are in correct locations
  - [ ] 8 job scripts in `/scraper/jobs/`
  - [ ] 7 deployment files in `/scraper/deployment/`
  - [ ] All scripts are executable (`chmod +x`)

- [ ] SSH access configured
  - [ ] SSH key exists: `~/.ssh/nabavki-key.pem`
  - [ ] Key has correct permissions: `chmod 400 ~/.ssh/nabavki-key.pem`
  - [ ] Can connect: `ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153`

- [ ] Files verified locally
  - [ ] All scripts have proper shebang (`#!/bin/bash` or `#!/usr/bin/env python3`)
  - [ ] No syntax errors in bash scripts
  - [ ] Python scripts have proper imports

### EC2 Environment

- [ ] EC2 instance running
  - [ ] IP: 3.120.26.153
  - [ ] SSH access working
  - [ ] User: ubuntu

- [ ] Project directory exists
  - [ ] `/home/ubuntu/nabavkidata/` exists
  - [ ] `/home/ubuntu/nabavkidata/scraper/` exists
  - [ ] `/home/ubuntu/nabavkidata/backend/` exists

- [ ] Python environment ready
  - [ ] Virtual environment at `/home/ubuntu/nabavkidata/venv/`
  - [ ] Scrapy installed
  - [ ] asyncpg installed
  - [ ] All required dependencies installed

- [ ] Database configured
  - [ ] DATABASE_URL environment variable set
  - [ ] Database accessible from EC2
  - [ ] Required tables exist (tenders, documents, users)
  - [ ] Test connection works

## Deployment Steps

### Step 1: Upload Files

```bash
# From local machine, in project root
cd /Users/tamsar/Downloads/nabavkidata
```

- [ ] Upload job scripts
  ```bash
  scp -i ~/.ssh/nabavki-key.pem scraper/jobs/*.sh \
      ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/jobs/
  ```

- [ ] Upload deployment files
  ```bash
  scp -i ~/.ssh/nabavki-key.pem scraper/deployment/* \
      ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/deployment/
  ```

- [ ] Verify upload
  ```bash
  ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153 \
      "ls -la /home/ubuntu/nabavkidata/scraper/jobs/ && \
       ls -la /home/ubuntu/nabavkidata/scraper/deployment/"
  ```

### Step 2: Connect to EC2

- [ ] SSH to server
  ```bash
  ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
  ```

- [ ] Navigate to deployment directory
  ```bash
  cd /home/ubuntu/nabavkidata/scraper/deployment
  ```

### Step 3: Set Environment Variables

- [ ] Check if DATABASE_URL is set
  ```bash
  echo $DATABASE_URL
  ```

- [ ] If not set, add to .bashrc
  ```bash
  echo 'export DATABASE_URL="postgresql://user:pass@host:5432/nabavkidata"' >> ~/.bashrc
  echo 'export PATH="/home/ubuntu/nabavkidata/venv/bin:$PATH"' >> ~/.bashrc
  source ~/.bashrc
  ```

- [ ] Verify environment
  ```bash
  echo $DATABASE_URL  # Should show connection string
  which python3       # Should show venv path
  ```

### Step 4: Test Database Connection

- [ ] Activate virtual environment
  ```bash
  source /home/ubuntu/nabavkidata/venv/bin/activate
  ```

- [ ] Test connection
  ```bash
  python3 << 'EOF'
  import asyncio
  import asyncpg
  import os

  async def test():
      conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
      count = await conn.fetchval('SELECT COUNT(*) FROM tenders')
      print(f'Connected! Found {count} tenders')
      await conn.close()

  asyncio.run(test())
  EOF
  ```

- [ ] Verify output shows: "Connected! Found X tenders"

### Step 5: Run Deployment Script

- [ ] Make deployment script executable
  ```bash
  chmod +x deploy_automation.sh
  ```

- [ ] Run deployment
  ```bash
  ./deploy_automation.sh
  ```

- [ ] Review output for errors
  - [ ] All directories created
  - [ ] Job scripts are executable
  - [ ] Crontab backed up
  - [ ] Cron jobs installed
  - [ ] Environment verified
  - [ ] Database connection successful

### Step 6: Run Verification Script

- [ ] Make verification script executable
  ```bash
  chmod +x verify_automation.sh
  ```

- [ ] Run verification
  ```bash
  ./verify_automation.sh
  ```

- [ ] Check results
  - [ ] All checks passed (or only warnings)
  - [ ] No failed checks
  - [ ] Exit code is 0

Expected output:
```
✓ PASSED: X
✗ FAILED: 0
⚠ WARNINGS: Y
```

## Post-Deployment Verification

### Immediate Checks

- [ ] View installed cron jobs
  ```bash
  crontab -l
  ```
  - [ ] Should show 8 nabavkidata jobs
  - [ ] Comment header present
  - [ ] All paths correct

- [ ] Check directory structure
  ```bash
  ls -la /home/ubuntu/nabavkidata/scraper/jobs/
  ls -la /home/ubuntu/nabavkidata/scraper/logs/
  ls -la /home/ubuntu/backups/
  ```

- [ ] Verify permissions
  ```bash
  ls -l /home/ubuntu/nabavkidata/scraper/jobs/*.sh
  ```
  - [ ] All scripts should be executable (-rwx)

### Test Individual Jobs

- [ ] Test health check (safe to run)
  ```bash
  /home/ubuntu/nabavkidata/scraper/jobs/health_check.sh
  ```
  - [ ] No errors
  - [ ] Log created in `/home/ubuntu/nabavkidata/scraper/logs/health_check.log`

- [ ] Test log rotation (safe to run)
  ```bash
  /home/ubuntu/nabavkidata/scraper/jobs/rotate_logs.sh
  ```
  - [ ] No errors
  - [ ] Log created

- [ ] OPTIONAL: Test active scraper (this will run a real scrape)
  ```bash
  /home/ubuntu/nabavkidata/scraper/jobs/scrape_active.sh
  ```
  - [ ] Scraper runs
  - [ ] Log created
  - [ ] No critical errors
  - [ ] Database updated

### Monitor First Automated Runs

- [ ] Wait for next health check (every 5 minutes)
  ```bash
  tail -f /home/ubuntu/nabavkidata/scraper/logs/health_check.log
  ```
  - [ ] Health check runs automatically
  - [ ] No errors reported

- [ ] Wait for next document processing (every 15 minutes)
  ```bash
  tail -f /home/ubuntu/nabavkidata/scraper/logs/cron_docs.log
  ```
  - [ ] Document processor runs
  - [ ] Processes pending documents

- [ ] Check cron execution in system logs
  ```bash
  grep CRON /var/log/syslog | tail -20
  ```
  - [ ] Shows cron executing jobs
  - [ ] No errors

### Monitoring Dashboard

- [ ] Make dashboard executable
  ```bash
  chmod +x /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py
  ```

- [ ] Run dashboard
  ```bash
  python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py
  ```

- [ ] Verify dashboard shows:
  - [ ] Database statistics
  - [ ] Tender counts
  - [ ] Document processing stats
  - [ ] Health indicators
  - [ ] Log file stats

### 24-Hour Monitoring

After 24 hours, verify:

- [ ] Active scraper ran 4 times (04:00, 10:00, 16:00, 22:00 UTC)
  ```bash
  ls -lt /home/ubuntu/nabavkidata/scraper/logs/scrape_active_*.log | head -4
  ```

- [ ] Awards scraper ran 1 time (06:00 UTC)
  ```bash
  ls -lt /home/ubuntu/nabavkidata/scraper/logs/scrape_awards_*.log | head -1
  ```

- [ ] Database backup was created (05:00 UTC)
  ```bash
  ls -lt /home/ubuntu/backups/nabavkidata_*.sql.gz | head -1
  ```

- [ ] Log rotation ran (01:00 UTC)
  ```bash
  cat /home/ubuntu/nabavkidata/scraper/logs/rotate.log | tail -20
  ```

- [ ] Vector refresh ran (03:00 UTC)
  ```bash
  ls -lt /home/ubuntu/nabavkidata/scraper/logs/refresh_vectors_*.log | head -1
  ```

- [ ] Health checks running every 5 minutes
  ```bash
  wc -l /home/ubuntu/nabavkidata/scraper/logs/health_check.log
  # Should be ~288 lines per day (24*60/5)
  ```

- [ ] Document processing running every 15 minutes
  ```bash
  ls -lt /home/ubuntu/nabavkidata/scraper/logs/process_documents_*.log | head -10
  ```

### Database Verification

- [ ] Check database growth
  ```bash
  psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"
  ```
  - [ ] Tender count increased

- [ ] Check recent scrapes
  ```bash
  psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders WHERE scraped_at >= CURRENT_DATE"
  ```
  - [ ] Shows today's scrapes

- [ ] Verify no duplicate data
  ```bash
  psql $DATABASE_URL -c "SELECT tender_id, COUNT(*) FROM tenders GROUP BY tender_id HAVING COUNT(*) > 1"
  ```
  - [ ] No duplicates (or handled appropriately)

### Log Analysis

- [ ] Check for errors in logs
  ```bash
  grep -i error /home/ubuntu/nabavkidata/scraper/logs/*.log | tail -50
  ```
  - [ ] No critical errors
  - [ ] Any errors are expected/handled

- [ ] Check disk usage
  ```bash
  df -h /home/ubuntu
  du -sh /home/ubuntu/nabavkidata/scraper/logs/
  du -sh /home/ubuntu/backups/
  ```
  - [ ] Disk usage acceptable (<80%)
  - [ ] Log size manageable
  - [ ] Backup size reasonable

### Performance Check

- [ ] Monitor resource usage
  ```bash
  top -b -n 1 | head -20
  ```
  - [ ] CPU usage reasonable
  - [ ] Memory usage acceptable

- [ ] Check running processes
  ```bash
  ps aux | grep -E "scrapy|python" | grep -v grep
  ```
  - [ ] No stuck processes
  - [ ] Process count reasonable (<5)

## Week 1 Monitoring

After one week, verify:

- [ ] Sunday backfill ran (02:00 UTC Sunday)
  ```bash
  ls -lt /home/ubuntu/nabavkidata/scraper/logs/scrape_backfill_*.log | head -1
  ```

- [ ] All daily jobs ran 7 times
- [ ] Log rotation is working (old logs compressed)
  ```bash
  find /home/ubuntu/nabavkidata/scraper/logs -name "*.log.gz" | wc -l
  ```

- [ ] Backup retention working (only 7 days kept)
  ```bash
  find /home/ubuntu/backups -name "*.sql.gz" | wc -l
  # Should be ≤7
  ```

- [ ] Database growth is steady
  ```bash
  psql $DATABASE_URL -c "SELECT DATE(scraped_at), COUNT(*) FROM tenders WHERE scraped_at >= CURRENT_DATE - 7 GROUP BY DATE(scraped_at) ORDER BY DATE(scraped_at)"
  ```

- [ ] No alerts triggered (or alerts are valid)

## Troubleshooting Checklist

If something goes wrong:

### Cron Not Running

- [ ] Check cron service
  ```bash
  sudo systemctl status cron
  ```

- [ ] Restart cron
  ```bash
  sudo systemctl restart cron
  ```

- [ ] Check syslog for errors
  ```bash
  grep CRON /var/log/syslog | grep -i error | tail -20
  ```

### Job Failures

- [ ] Check job logs
  ```bash
  tail -100 /home/ubuntu/nabavkidata/scraper/logs/[job_name].log
  ```

- [ ] Run job manually with debug
  ```bash
  bash -x /home/ubuntu/nabavkidata/scraper/jobs/[job_name].sh
  ```

- [ ] Check permissions
  ```bash
  ls -l /home/ubuntu/nabavkidata/scraper/jobs/[job_name].sh
  ```

### Database Issues

- [ ] Test connection
  ```bash
  psql $DATABASE_URL -c "SELECT 1"
  ```

- [ ] Check DATABASE_URL
  ```bash
  echo $DATABASE_URL
  ```

- [ ] Verify in crontab
  ```bash
  crontab -l | grep DATABASE_URL
  ```

### Disk Space Issues

- [ ] Check disk usage
  ```bash
  df -h
  ```

- [ ] Clean old logs manually
  ```bash
  /home/ubuntu/nabavkidata/scraper/jobs/rotate_logs.sh
  ```

- [ ] Delete old backups
  ```bash
  find /home/ubuntu/backups -name "*.sql.gz" -mtime +7 -delete
  ```

## Rollback Procedure

If you need to remove automation:

- [ ] Backup current crontab
  ```bash
  crontab -l > /tmp/crontab_current.txt
  ```

- [ ] Remove automation jobs
  ```bash
  crontab -e
  # Delete all nabavkidata jobs
  ```

- [ ] Or restore original crontab
  ```bash
  crontab /tmp/crontab_backup_[TIMESTAMP].txt
  ```

- [ ] Verify removal
  ```bash
  crontab -l | grep nabavkidata
  # Should show nothing
  ```

- [ ] Kill any running scrapers
  ```bash
  pkill -f scrapy
  ```

## Success Criteria

Deployment is successful when:

- [ ] All 8 cron jobs installed
- [ ] All verification checks pass
- [ ] Health check runs every 5 minutes
- [ ] Active scraper runs on schedule (4x daily)
- [ ] No critical errors in logs
- [ ] Database growing steadily
- [ ] Backups being created daily
- [ ] Logs being rotated
- [ ] Monitoring dashboard works
- [ ] Disk usage stable
- [ ] No stuck processes

## Final Sign-Off

- [ ] Deployment completed successfully
- [ ] All verification steps passed
- [ ] 24-hour monitoring completed
- [ ] No critical issues found
- [ ] Documentation reviewed
- [ ] Team notified

**Deployed by**: _________________
**Date**: _________________
**Time**: _________________
**Notes**: _________________

---

## Quick Commands Reference

```bash
# Status check
python3 /home/ubuntu/nabavkidata/scraper/deployment/monitor_dashboard.py

# View cron jobs
crontab -l

# Check logs
tail -f /home/ubuntu/nabavkidata/scraper/logs/cron_active.log

# Run verification
/home/ubuntu/nabavkidata/scraper/deployment/verify_automation.sh

# Database count
psql $DATABASE_URL -c "SELECT COUNT(*) FROM tenders"

# Disk usage
df -h /home/ubuntu
```

## Support Resources

- **Full Documentation**: `AUTOMATION_README.md`
- **Deployment Guide**: `EC2_DEPLOYMENT_GUIDE.md`
- **Quick Reference**: `QUICK_REFERENCE.md`
- **Verification Script**: `verify_automation.sh`
- **Monitoring Dashboard**: `monitor_dashboard.py`

---

**Remember**: Always test in a non-production environment first if possible!
