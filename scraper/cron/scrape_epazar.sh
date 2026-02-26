#!/bin/bash
#
# CRON SCRIPT: Scrape E-Pazar Tenders
#
# This script scrapes all categories from e-pazar.gov.mk:
# - Active tenders (823+)
# - Completed tenders (813+)
# - Signed contracts (1116+)
#
# Run once daily (e-pazar updates less frequently than e-nabavki)
#
# Recommended crontab entry:
# 0 6 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_epazar.sh >> /var/log/nabavkidata/epazar_$(date +\%Y\%m\%d).log 2>&1
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

log "Starting E-Pazar scrape (all categories)..."

# Activate virtual environment

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run scraper for all categories
RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_epazar_$(date +%Y%m%d_%H%M%S).log"

log "Running /usr/local/bin/scrapy crawl epazar_api -a category=all"

# Disable set -e so we capture the exit code instead of dying
set +e
/usr/local/bin/scrapy crawl epazar_api \
    -a category=all \
    -s LOG_LEVEL=INFO \
    -s LOG_FILE="$LOG_FILE"
RC=$?
set -e
RUN_END=$(date -Iseconds)
ERROR_COUNT=$(grep -i "ERROR" "$LOG_FILE" | wc -l || true)
STATUS="success"
if [ $RC -ne 0 ]; then
    STATUS="failure"
    log "E-Pazar scrape failed with exit code $RC"
else
    log "E-Pazar scrape completed successfully"
fi

# Write health JSON if write_health.py exists
if [ -f "$SCRIPT_DIR/write_health.py" ]; then
    /usr/bin/python3 "$SCRIPT_DIR/write_health.py" \
      --status "$STATUS" \
      --dataset epazar \
      --log-file "$LOG_FILE" \
      --started "$RUN_START" \
      --finished "$RUN_END" \
      --error-count "$ERROR_COUNT" \
      --exit-code "$RC" || true
fi

# Deactivate virtual environment

log "E-Pazar scrape finished"
