#!/bin/bash
#
# CRON SCRIPT: Scrape Active Tenders
#
# Scrapes active tenders from e-nabavki.gov.mk
# Schedule: every 4 hours (0 0,4,8,12,16,20 * * *)
#
# Safety: CLOSESPIDER_TIMEOUT (2h) + bash timeout (2.5h) + scraper_lock (3h max hold)
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
acquire_scraper_lock || exit 75

log "Starting active tenders scrape..."

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run scraper
RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_active_$(date +%Y%m%d_%H%M%S).log"

log "Running scrapy crawl nabavki -a category=active"

# timeout: 2.5h hard kill as fallback for CLOSESPIDER_TIMEOUT
timeout --signal=TERM --kill-after=60 9000 \
/usr/local/bin/scrapy crawl nabavki \
    -a category=active \
    -s LOG_LEVEL=INFO \
    -s LOG_FILE="$LOG_FILE" \
    -s MEMUSAGE_ENABLED=True \
    -s MEMUSAGE_LIMIT_MB=1200 \
    -s MEMUSAGE_WARNING_MB=900 \
    -s CONCURRENT_REQUESTS=2 \
    -s PLAYWRIGHT_MAX_PAGES_PER_CONTEXT=4 \
    -s CLOSESPIDER_TIMEOUT=7200

RC=$?

# Clean up orphaned Playwright/Chromium processes from this run
pkill -f "chromium.*--headless" 2>/dev/null || true

RUN_END=$(date -Iseconds)
ERROR_COUNT=$(grep -i "ERROR" "$LOG_FILE" 2>/dev/null | wc -l || true)

if [ $RC -eq 124 ]; then
    STATUS="timeout"
    log "Scrape timed out after 2.5 hours (hard kill)"
elif [ $RC -ne 0 ]; then
    STATUS="failure"
    log "Scrape failed with exit code $RC"
else
    STATUS="success"
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
