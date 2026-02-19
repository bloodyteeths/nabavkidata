#!/bin/bash
#
# CRON SCRIPT: Cleanup Old Logs
#
# Removes log files older than 30 days
#
# Recommended crontab entry:
# 0 4 1 * * /home/ubuntu/nabavkidata/scraper/cron/cleanup_logs.sh >> /var/log/nabavkidata/cleanup.log 2>&1
#

set -e

LOG_DIR="/var/log/nabavkidata"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting log cleanup..."

# Count files before cleanup
BEFORE_COUNT=$(find "$LOG_DIR" -name "*.log" -mtime +30 | wc -l)
log "Found $BEFORE_COUNT log files older than 30 days"

# Remove old log files
find "$LOG_DIR" -name "*.log" -mtime +30 -delete

log "Log cleanup completed"
