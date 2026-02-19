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
VENV_PATH="/home/ubuntu/nabavkidata/venv"
LOG_DIR="/var/log/nabavkidata"

# Database URL
export DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set in environment}"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting cancelled tenders scrape..."

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run scraper
RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_cancelled_$(date +%Y%m%d_%H%M%S).log"

log "Running scrapy crawl nabavki -a category=cancelled"

scrapy crawl nabavki \
    -a category=cancelled \
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
