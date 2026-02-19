#!/bin/bash
#
# CRON SCRIPT: Scrape Cancelled Tenders
#
# This script scrapes cancelled tenders from e-nabavki.gov.mk
# Run daily at 5 AM to collect new cancellations
#
# Recommended crontab entry:
# 0 5 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_cancelled.sh >> /var/log/nabavkidata/cancelled_$(date +\%Y\%m\%d).log 2>&1
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="/home/ubuntu/nabavkidata/backend/venv"
LOG_DIR="/var/log/nabavkidata"

# Scraper settings
MAX_PAGES=100  # Increased to catch more cancellations

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
acquire_scraper_lock || exit 0


log "Starting cancelled tenders scrape..."

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run scraper
RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_cancelled_$(date +%Y%m%d_%H%M%S).log"

log "Running scrapy crawl nabavki -a category=cancelled"

/home/ubuntu/.local/bin/scrapy crawl nabavki \
    -a category=cancelled \
    -a max_listing_pages=$MAX_PAGES \
    -s LOG_LEVEL=INFO \
    -s LOG_FILE="$LOG_FILE" \
    -s MEMUSAGE_LIMIT_MB=1536 \
    -s MEMUSAGE_WARNING_MB=1200 \
    -s CONCURRENT_REQUESTS=2 \
    -s DOWNLOAD_DELAY=0.3

RC=$?
RUN_END=$(date -Iseconds)
ERROR_COUNT=$(grep -i "ERROR" "$LOG_FILE" | wc -l || true)
STATUS="success"
if [ $RC -ne 0 ]; then
    STATUS="failure"
    log "Scrape failed with exit code $RC"
else
    log "Cancelled tenders scrape completed"
fi

# Write health JSON
python3 "$SCRIPT_DIR/write_health.py" \
  --status "$STATUS" \
  --dataset cancelled \
  --log-file "$LOG_FILE" \
  --started "$RUN_START" \
  --finished "$RUN_END" \
  --error-count "$ERROR_COUNT" \
  --exit-code "$RC" || true

# Deactivate virtual environment
deactivate 2>/dev/null || true
