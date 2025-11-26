#!/bin/bash
#
# CRON SCRIPT: Scrape E-Nabavki Authenticated
#
# This script scrapes all categories from e-nabavki.gov.mk using authenticated access:
# - Active tenders
# - Awarded contracts
# - Cancelled tenders
#
# REQUIRES: NABAVKI_USERNAME and NABAVKI_PASSWORD environment variables
#           or set them in /home/ubuntu/nabavkidata/scraper/.env
#
# Recommended crontab entry (every 4 hours to match cookie expiry):
# 0 */4 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_nabavki.sh >> /var/log/nabavkidata/nabavki_$(date +\%Y\%m\%d).log 2>&1
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="/home/ubuntu/nabavkidata/venv"
LOG_DIR="/var/log/nabavkidata"
HEALTH_FILE="/home/ubuntu/nabavkidata/health.json"

# Load environment variables from .env file if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Database URL (fallback if not in .env)
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata}"

# Validate credentials
if [ -z "$NABAVKI_USERNAME" ] || [ -z "$NABAVKI_PASSWORD" ]; then
    echo "ERROR: NABAVKI_USERNAME and NABAVKI_PASSWORD must be set"
    echo "Set them in environment or $PROJECT_ROOT/.env"
    exit 1
fi

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting E-Nabavki authenticated scrape..."
log "Using username: $NABAVKI_USERNAME"

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Categories to scrape
CATEGORIES="active awarded cancelled"

RUN_START=$(date -Iseconds)
TOTAL_ERRORS=0
OVERALL_STATUS="success"

for CATEGORY in $CATEGORIES; do
    log "========================================"
    log "Scraping category: $CATEGORY"
    log "========================================"

    LOG_FILE="$LOG_DIR/scrapy_nabavki_${CATEGORY}_$(date +%Y%m%d_%H%M%S).log"

    scrapy crawl nabavki_auth \
        -a category=$CATEGORY \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE="$LOG_FILE" || {
        RC=$?
        log "WARNING: $CATEGORY scrape failed with exit code $RC"
        OVERALL_STATUS="partial_failure"
    }

    ERROR_COUNT=$(grep -i "ERROR" "$LOG_FILE" 2>/dev/null | wc -l || echo 0)
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERROR_COUNT))

    # Small delay between categories
    sleep 5
done

RUN_END=$(date -Iseconds)

if [ $TOTAL_ERRORS -gt 10 ]; then
    OVERALL_STATUS="failure"
fi

log "========================================"
log "E-Nabavki scrape completed"
log "Status: $OVERALL_STATUS"
log "Total errors: $TOTAL_ERRORS"
log "========================================"

# Copy health report from scraper to project root
if [ -f "/tmp/nabavki_auth_health.json" ]; then
    cp /tmp/nabavki_auth_health.json "$HEALTH_FILE"
    log "Health report saved to $HEALTH_FILE"
fi

# Deactivate virtual environment
deactivate 2>/dev/null || true

log "E-Nabavki scrape finished"
