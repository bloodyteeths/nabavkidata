#!/bin/bash
#
# CRON SCRIPT: Scrape Awarded Contracts
#
# This script scrapes awarded contracts from e-nabavki.gov.mk
# Run daily at 4 AM to collect new awarded contracts
#
# Recommended crontab entry:
# 0 4 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_awarded.sh >> /var/log/nabavkidata/awarded_$(date +\%Y\%m\%d).log 2>&1
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="/home/ubuntu/nabavkidata/backend/venv"
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
acquire_scraper_lock || exit 0


log "Starting awarded contracts scrape..."

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run scraper
RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_awarded_$(date +%Y%m%d_%H%M%S).log"

# Scrape first 200 pages (~2000 tenders = ~3 weeks of awards)
# Ensures we catch up on any backlog from weekends
MAX_PAGES=200

log "Running scrapy crawl nabavki -a category=awarded -a max_listing_pages=$MAX_PAGES"

"$VENV_PATH/bin/scrapy" crawl nabavki \
    -a category=awarded \
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

# Deactivate virtual environment
deactivate 2>/dev/null || true
