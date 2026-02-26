#!/bin/bash
#
# CRON SCRIPT: Scrape Awarded Contracts
#
# Scrapes awarded contracts from e-nabavki.gov.mk
# Schedule: daily at 5 AM UTC
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

# Source locking mechanism
source "$SCRIPT_DIR/scraper_lock.sh"

# Acquire lock (exit if another scraper is running)
acquire_scraper_lock || exit 75

log "Starting awarded contracts scrape..."

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run scraper
RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_awarded_$(date +%Y%m%d_%H%M%S).log"

# Scrape first 50 pages (~500 tenders = ~1 week of awards)
MAX_PAGES=50

log "Running scrapy crawl nabavki -a category=awarded -a max_listing_pages=$MAX_PAGES"

# timeout: 2.5h hard kill as fallback for CLOSESPIDER_TIMEOUT
# Disable set -e so we capture the exit code instead of dying
set +e
timeout --signal=TERM --kill-after=60 9000 \
/usr/local/bin/scrapy crawl nabavki \
    -a category=awarded \
    -a max_listing_pages=$MAX_PAGES \
    -s LOG_LEVEL=INFO \
    -s LOG_FILE="$LOG_FILE" \
    -s MEMUSAGE_ENABLED=True \
    -s MEMUSAGE_LIMIT_MB=1536 \
    -s MEMUSAGE_WARNING_MB=1200 \
    -s CONCURRENT_REQUESTS=2 \
    -s DOWNLOAD_DELAY=0.3 \
    -s CLOSESPIDER_TIMEOUT=7200
RC=$?
set -e

# Clean up orphaned Playwright/Chromium processes
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
    log "Awarded contracts scrape completed"
fi

# Write health JSON
python3 "$SCRIPT_DIR/write_health.py" \
  --status "$STATUS" \
  --dataset awarded \
  --log-file "$LOG_FILE" \
  --started "$RUN_START" \
  --finished "$RUN_END" \
  --error-count "$ERROR_COUNT" \
  --exit-code "$RC" || true
