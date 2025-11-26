# Scraper Automation Infrastructure - File Index

Complete index of all automation files with descriptions and usage.

## Overview

**Total Files**: 17 (16 automation + 1 summary)
**Total Lines**: ~3,538 lines of code and documentation
**Created**: 2025-11-24
**Status**: Production Ready

## Directory Structure

```
nabavkidata/
├── AGENT_E_AUTOMATION_COMPLETE.md     # Main summary document
└── scraper/
    ├── jobs/                          # 8 automation job scripts
    │   ├── scrape_active.sh
    │   ├── scrape_awards.sh
    │   ├── scrape_backfill.sh
    │   ├── process_documents.sh
    │   ├── refresh_vectors.sh
    │   ├── health_check.sh
    │   ├── rotate_logs.sh
    │   └── backup_db.sh
    │
    └── deployment/                    # 8 deployment & monitoring tools
        ├── deploy_automation.sh
        ├── verify_automation.sh
        ├── monitor_dashboard.py
        ├── crontab_additions.txt
        ├── AUTOMATION_README.md
        ├── EC2_DEPLOYMENT_GUIDE.md
        ├── DEPLOYMENT_CHECKLIST.md
        ├── QUICK_REFERENCE.md
        └── INDEX.md                   # This file
```

## Job Scripts (8 files)

### 1. scrape_active.sh
**Location**: `/scraper/jobs/scrape_active.sh`
**Size**: ~60 lines
**Purpose**: Scrape active/open tenders
**Schedule**: 4x daily (04:00, 10:00, 16:00, 22:00 UTC)
**Duration**: 15-30 minutes
**Dependencies**: Scrapy, DATABASE_URL

**What it does**:
- Activates Python virtual environment
- Runs Scrapy spider with status_filter='open'
- Captures new tender postings
- Updates existing tenders with changes
- Logs all activity to timestamped log file

**Logs**: `/scraper/logs/scrape_active_YYYYMMDD_HHMMSS.log`

### 2. scrape_awards.sh
**Location**: `/scraper/jobs/scrape_awards.sh`
**Size**: ~55 lines
**Purpose**: Scrape awarded tenders for competitor intelligence
**Schedule**: Daily at 06:00 UTC
**Duration**: 10-20 minutes
**Dependencies**: Scrapy, DATABASE_URL

**What it does**:
- Scrapes tenders with status='awarded'
- Captures award information
- Tracks competitor wins
- Provides market intelligence data

**Logs**: `/scraper/logs/scrape_awards_YYYYMMDD.log`

### 3. scrape_backfill.sh
**Location**: `/scraper/jobs/scrape_backfill.sh`
**Size**: ~70 lines
**Purpose**: Weekly historical backfill for trend analysis
**Schedule**: Sunday at 02:00 UTC
**Duration**: 1-2 hours
**Dependencies**: Scrapy, DATABASE_URL

**What it does**:
- Scrapes last 7 days of historical data
- Fills gaps in data collection
- Updates historical records
- Provides trend analysis data
- Has 2-hour timeout protection
- Limits to 10,000 items per run

**Logs**: `/scraper/logs/scrape_backfill_YYYYMMDD.log`

### 4. process_documents.sh
**Location**: `/scraper/jobs/process_documents.sh`
**Size**: ~95 lines
**Purpose**: Process document download queue
**Schedule**: Every 15 minutes
**Duration**: 2-5 minutes
**Dependencies**: asyncpg, DATABASE_URL

**What it does**:
- Queries pending documents from database
- Downloads document files (batch of 10)
- Parses/extracts content
- Updates document status (completed/failed)
- Handles errors gracefully

**Logs**: `/scraper/logs/process_documents_YYYYMMDD_HHMMSS.log`

### 5. refresh_vectors.sh
**Location**: `/scraper/jobs/refresh_vectors.sh`
**Size**: ~85 lines
**Purpose**: Refresh embeddings for new tenders
**Schedule**: Daily at 03:00 UTC
**Duration**: 10-20 minutes
**Dependencies**: asyncpg, AI service, DATABASE_URL

**What it does**:
- Finds tenders created/updated in last day
- Generates embeddings for tender text
- Updates vector database
- Enables AI-powered search
- Processes in batches

**Logs**: `/scraper/logs/refresh_vectors_YYYYMMDD.log`

### 6. health_check.sh
**Location**: `/scraper/jobs/health_check.sh`
**Size**: ~140 lines
**Purpose**: Monitor system health and send alerts
**Schedule**: Every 5 minutes
**Duration**: <1 minute
**Dependencies**: asyncpg, mail (optional)

**What it does**:
- Checks last scrape timestamp (alerts if >6 hours)
- Monitors error rate in logs (alerts if >10 errors)
- Tests database connectivity
- Checks disk space (alerts if >90%)
- Monitors process count (alerts if >5 scrapers)
- Logs all health metrics

**Logs**: `/scraper/logs/health_check.log`

**Alerts**:
- Email notifications (if mail configured)
- Log entries for all issues

### 7. rotate_logs.sh
**Location**: `/scraper/jobs/rotate_logs.sh`
**Size**: ~55 lines
**Purpose**: Rotate and compress old logs
**Schedule**: Daily at 01:00 UTC
**Duration**: 2-5 minutes
**Dependencies**: gzip, find

**What it does**:
- Compresses logs older than 7 days (gzip)
- Deletes compressed logs older than 30 days
- Deletes empty log files
- Reports disk space saved
- Keeps rotation log itself small (last 1000 lines)

**Retention Policy**:
- Active logs: 7 days
- Compressed logs: 30 days
- Total retention: 37 days

**Logs**: `/scraper/logs/rotate.log`

### 8. backup_db.sh
**Location**: `/scraper/jobs/backup_db.sh`
**Size**: ~80 lines
**Purpose**: Daily database backups
**Schedule**: Daily at 05:00 UTC
**Duration**: 3-10 minutes
**Dependencies**: pg_dump, gzip, DATABASE_URL

**What it does**:
- Dumps critical database tables
- Compresses backup (gzip)
- Stores in `/home/ubuntu/backups/`
- Deletes backups older than 7 days
- Optional S3 upload for offsite backup
- Reports backup size

**Tables backed up**:
- tenders
- documents
- users
- subscriptions
- saved_searches

**Logs**: `/scraper/logs/backup_YYYYMMDD_HHMMSS.log`

## Deployment Tools (8 files)

### 9. deploy_automation.sh
**Location**: `/scraper/deployment/deploy_automation.sh`
**Size**: ~175 lines
**Purpose**: Main deployment script
**Usage**: `./deploy_automation.sh`

**What it does**:
- Creates directory structure
- Sets permissions on job scripts
- Backs up existing crontab
- Installs new cron jobs
- Verifies environment
- Tests database connection
- Runs health check test
- Displays installation summary

**Steps**:
1. Create directories
2. Set permissions
3. Backup crontab
4. Install cron jobs
5. Verify environment
6. Test database
7. Test scripts
8. Show summary

### 10. verify_automation.sh
**Location**: `/scraper/deployment/verify_automation.sh`
**Size**: ~425 lines
**Purpose**: Comprehensive verification
**Usage**: `./verify_automation.sh`

**What it checks** (12 categories):
1. Directory structure
2. Job script permissions
3. Cron job installation
4. Environment variables
5. Database connectivity
6. Script syntax validation
7. Log file status
8. Disk space
9. Process status
10. Health check functionality
11. Backup system
12. Monitoring dashboard

**Exit codes**:
- 0: All checks passed
- 1: One or more checks failed

### 11. monitor_dashboard.py
**Location**: `/scraper/deployment/monitor_dashboard.py`
**Size**: ~320 lines
**Purpose**: Real-time monitoring dashboard
**Usage**: `python3 monitor_dashboard.py`

**Displays**:
- Database statistics (totals, today, week, active)
- Tender status breakdown
- Document processing stats
- Top CPV codes
- High-value open tenders
- Log file statistics
- Cron job status
- Health indicators

**Features**:
- Color-coded output (green/yellow/red)
- Formatted numbers and sizes
- System health summary
- Recent activity tracking

### 12. crontab_additions.txt
**Location**: `/scraper/deployment/crontab_additions.txt`
**Size**: ~35 lines
**Purpose**: Cron job definitions
**Usage**: Loaded by deploy_automation.sh

**Contains**:
- All 8 cron job schedules
- Comments explaining each job
- Proper log redirection
- Error handling (2>&1)

**Format**:
```
# Comment
MIN HOUR DOM MON DOW /path/to/script.sh >> /path/to/log 2>&1
```

### 13. AUTOMATION_README.md
**Location**: `/scraper/deployment/AUTOMATION_README.md`
**Size**: ~650 lines
**Purpose**: Complete system documentation

**Sections**:
- Overview
- Architecture
- Schedule reference
- Directory structure
- Installation instructions
- Verification procedures
- Monitoring and alerts
- Log management
- Database backup
- Troubleshooting
- Maintenance
- Performance optimization
- Security considerations

### 14. EC2_DEPLOYMENT_GUIDE.md
**Location**: `/scraper/deployment/EC2_DEPLOYMENT_GUIDE.md`
**Size**: ~550 lines
**Purpose**: Step-by-step deployment guide

**Sections**:
- Prerequisites
- Deployment steps (1-10)
- Post-deployment verification
- Troubleshooting
- Monitoring commands
- Maintenance tasks
- Rollback procedure
- Success criteria

### 15. DEPLOYMENT_CHECKLIST.md
**Location**: `/scraper/deployment/DEPLOYMENT_CHECKLIST.md`
**Size**: ~450 lines
**Purpose**: Interactive deployment checklist

**Sections**:
- Pre-deployment checklist
- Deployment steps
- Post-deployment verification
- 24-hour monitoring
- Week 1 monitoring
- Troubleshooting checklist
- Rollback procedure
- Success criteria
- Sign-off section

### 16. QUICK_REFERENCE.md
**Location**: `/scraper/deployment/QUICK_REFERENCE.md`
**Size**: ~320 lines
**Purpose**: Quick command reference

**Sections**:
- Essential commands
- Monitoring commands
- Cron management
- Log management
- Manual job execution
- Schedule reference
- Troubleshooting quick fixes
- Performance tuning
- Backup & recovery
- Emergency procedures
- Useful aliases

### 17. INDEX.md
**Location**: `/scraper/deployment/INDEX.md`
**Purpose**: This file - complete file index

## Summary Document

### AGENT_E_AUTOMATION_COMPLETE.md
**Location**: `/AGENT_E_AUTOMATION_COMPLETE.md`
**Size**: ~950 lines
**Purpose**: Executive summary of entire automation project

**Contents**:
- Executive summary
- Deliverables overview
- Technical implementation
- Deployment process
- Key features
- Performance characteristics
- Security measures
- Testing & validation
- Success metrics
- Files delivered
- Agent sign-off

## Usage Scenarios

### First-Time Deployment

1. Read: `EC2_DEPLOYMENT_GUIDE.md`
2. Follow: `DEPLOYMENT_CHECKLIST.md`
3. Run: `deploy_automation.sh`
4. Run: `verify_automation.sh`
5. Monitor: `monitor_dashboard.py`

### Daily Operations

1. Check: `monitor_dashboard.py`
2. View logs as needed
3. Use: `QUICK_REFERENCE.md` for commands

### Troubleshooting

1. Check: `QUICK_REFERENCE.md` quick fixes
2. Review: `AUTOMATION_README.md` troubleshooting
3. Check logs in `/scraper/logs/`
4. Run: `verify_automation.sh`

### Maintenance

1. Weekly: Review dashboard
2. Monthly: Check `AUTOMATION_README.md` maintenance section
3. As needed: Update schedules in crontab

## File Categories

### Executable Scripts (11 files)
- 8 job scripts (.sh)
- 2 deployment scripts (.sh)
- 1 monitoring script (.py)

### Configuration (1 file)
- crontab_additions.txt

### Documentation (5 files)
- AUTOMATION_README.md
- EC2_DEPLOYMENT_GUIDE.md
- DEPLOYMENT_CHECKLIST.md
- QUICK_REFERENCE.md
- INDEX.md (this file)

### Summary (1 file)
- AGENT_E_AUTOMATION_COMPLETE.md

## Quick Start

```bash
# 1. Deploy
scp -i ~/.ssh/nabavki-key.pem -r scraper/jobs scraper/deployment ubuntu@3.120.26.153:/home/ubuntu/nabavkidata/scraper/
ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
cd /home/ubuntu/nabavkidata/scraper/deployment
./deploy_automation.sh

# 2. Verify
./verify_automation.sh

# 3. Monitor
python3 monitor_dashboard.py
```

## Support & Documentation

| Need | See File |
|------|----------|
| Quick commands | QUICK_REFERENCE.md |
| Step-by-step deployment | EC2_DEPLOYMENT_GUIDE.md |
| Complete documentation | AUTOMATION_README.md |
| Deployment checklist | DEPLOYMENT_CHECKLIST.md |
| System overview | AGENT_E_AUTOMATION_COMPLETE.md |
| File descriptions | INDEX.md (this file) |

## Version History

- **v1.0** (2025-11-24): Initial release
  - 8 job scripts
  - 8 deployment tools
  - Complete documentation
  - Production ready

## License

Copyright (c) 2025 Nabavkidata. All rights reserved.

---

**Created by**: Agent E - Automation Layer & Cron Job Engineer
**Date**: 2025-11-24
**Status**: Production Ready
