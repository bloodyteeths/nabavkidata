#!/bin/bash
#
# CRON SCRIPT: Scrape Awarded Contracts (Winner Data)
#
# This script scrapes the contracts table from e-nabavki.gov.mk:
# - Awarded contracts with winner company names
# - Contract values and dates
# - Populates bidders_data JSON field
#
# Note: This uses Playwright and paginates through ~109K+ records
# The spider handles incremental updates automatically
#
# Recommended crontab entry (once daily at 5 AM):
# 0 5 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_contracts.sh >> /var/log/nabavkidata/contracts_$(date +\%Y\%m\%d).log 2>&1
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
# VENV_PATH not needed - packages installed globally
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

log "Starting Contracts (Winner) scrape..."

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

RUN_START=$(date -Iseconds)
LOG_FILE="$LOG_DIR/scrapy_contracts_$(date +%Y%m%d_%H%M%S).log"

# Run the contracts spider
# - max_pages limits pagination (default: 15000 pages = ~150K records)
# - For daily updates, limit to recent pages (new contracts appear first)
"$VENV_PATH/bin/scrapy" crawl contracts \
    -a max_pages=500 \
    -s LOG_LEVEL=INFO \
    -s LOG_FILE="$LOG_FILE" || {
    RC=$?
    log "WARNING: Contracts scrape failed with exit code $RC"
}

RUN_END=$(date -Iseconds)
ERROR_COUNT=$(grep -i "ERROR" "$LOG_FILE" 2>/dev/null | wc -l || echo 0)
ITEMS_SCRAPED=$(grep -i "scraped" "$LOG_FILE" 2>/dev/null | tail -1 || echo "unknown")

log "========================================"
log "Contracts scrape completed"
log "Log file: $LOG_FILE"
log "Errors: $ERROR_COUNT"
log "Items: $ITEMS_SCRAPED"
log "========================================"

# Deactivate virtual environment
deactivate 2>/dev/null || true

log "Contracts scrape finished"
