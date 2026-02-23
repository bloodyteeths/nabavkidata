#!/bin/bash
#
# CRON SCRIPT: Scrape Awarded Contracts (Winner Data)
#
# Scrapes the contracts table from e-nabavki.gov.mk:
# - Awarded contracts with winner company names
# - Contract values and dates
# - Populates bidders_data JSON field
#
# Schedule: daily at 9 AM UTC
#
# Safety: CLOSESPIDER_TIMEOUT (2h) + bash timeout (2.5h) + scraper_lock (3h max hold)
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/nabavkidata"

# Load environment variables from .env file if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Database URL (fallback if not in .env)
export DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set in environment}"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Source locking mechanism (prevents overlapping with other scrapers)
source "$SCRIPT_DIR/scraper_lock.sh"

# Acquire lock (exit if another scraper is running)
acquire_scraper_lock || exit 75

log "Starting Contracts (Winner) scrape..."

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_contracts_$(date +%Y%m%d_%H%M%S).log"

# timeout: 2.5h hard kill as fallback for CLOSESPIDER_TIMEOUT
timeout --signal=TERM --kill-after=60 9000 \
/home/ubuntu/.local/bin/scrapy crawl contracts \
    -a max_pages=500 \
    -s LOG_LEVEL=INFO \
    -s LOG_FILE="$LOG_FILE" \
    -s MEMUSAGE_ENABLED=True \
    -s MEMUSAGE_LIMIT_MB=1536 \
    -s MEMUSAGE_WARNING_MB=1200 \
    -s CLOSESPIDER_TIMEOUT=7200

RC=$?

# Clean up orphaned Playwright/Chromium processes
pkill -f "chromium.*--headless" 2>/dev/null || true

RUN_END=$(date -Iseconds)
ERROR_COUNT=$(grep -i "ERROR" "$LOG_FILE" 2>/dev/null | wc -l || echo 0)
ITEMS_SCRAPED=$(grep -i "scraped" "$LOG_FILE" 2>/dev/null | tail -1 || echo "unknown")

if [ $RC -eq 124 ]; then
    STATUS="timeout"
    log "Scrape timed out after 2.5 hours (hard kill)"
elif [ $RC -ne 0 ]; then
    STATUS="failure"
    log "WARNING: Contracts scrape failed with exit code $RC"
else
    STATUS="success"
    log "Contracts scrape completed"
fi

log "========================================"
log "Contracts scrape finished"
log "Log file: $LOG_FILE"
log "Errors: $ERROR_COUNT"
log "Items: $ITEMS_SCRAPED"
log "========================================"

# Write health JSON
if [ -f "$SCRIPT_DIR/write_health.py" ]; then
    /usr/bin/python3 "$SCRIPT_DIR/write_health.py" \
      --status "$STATUS" \
      --dataset contracts \
      --log-file "$LOG_FILE" \
      --started "$RUN_START" \
      --finished "$RUN_END" \
      --error-count "$ERROR_COUNT" \
      --exit-code "$RC" || true
fi
