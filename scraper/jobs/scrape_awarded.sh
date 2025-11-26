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
VENV_PATH="/home/ubuntu/nabavkidata/venv"
LOG_DIR="/var/log/nabavkidata"

# Database URL
export DATABASE_URL="postgresql+asyncpg://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting awarded contracts scrape..."

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Run scraper
RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_awarded_$(date +%Y%m%d_%H%M%S).log"

log "Running scrapy crawl nabavki -a category=awarded"

scrapy crawl nabavki \
    -a category=awarded \
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
