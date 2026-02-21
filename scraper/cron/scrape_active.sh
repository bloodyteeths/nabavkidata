#!/bin/bash
#
# CRON SCRIPT: Scrape Active Tenders
#
# This script scrapes active tenders from e-nabavki.gov.mk
# Run every 3 hours to catch new tender postings
#
# Recommended crontab entry:
# 0 */3 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_active.sh >> /var/log/nabavkidata/active_$(date +\%Y\%m\%d).log 2>&1
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/nabavkidata"

# Database URL
export DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set in environment}"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Source locking mechanism (prevents zombie scrapers from piling up)
source "$SCRIPT_DIR/scraper_lock.sh"

# Acquire lock (exit if another scraper is running)
acquire_scraper_lock || exit 0

log "Starting active tenders scrape..."

# Activate virtual environment

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run scraper
RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_active_$(date +%Y%m%d_%H%M%S).log"

log "Running /home/ubuntu/.local/bin/scrapy crawl nabavki -a category=active"

/home/ubuntu/.local/bin/scrapy crawl nabavki \
    -a category=active \
    -s LOG_LEVEL=INFO \
    -s LOG_FILE="$LOG_FILE"

RC=$?
RUN_END=$(date -Iseconds)
ERROR_COUNT=$(grep -i "ERROR" "$LOG_FILE" | wc -l || true)
STATUS="success"
if [ $RC -ne 0 ]; then
    STATUS="failure"
    log "Scrape failed with exit code $RC"
else
    log "Active tenders scrape completed"
fi

# Write health JSON
/usr/bin/python3 "$SCRIPT_DIR/write_health.py" \
  --status "$STATUS" \
  --dataset active \
  --log-file "$LOG_FILE" \
  --started "$RUN_START" \
  --finished "$RUN_END" \
  --error-count "$ERROR_COUNT" \
  --exit-code "$RC" || true

# Deactivate virtual environment
