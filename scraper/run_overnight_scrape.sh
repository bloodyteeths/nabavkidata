#!/bin/bash
#
# OVERNIGHT AUTONOMOUS SCRAPING
# Started: $(date)
#
# This script monitors OpenTender import, then runs parallel e-nabavki scraping
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="logs/overnight_$(date +%Y%m%d_%H%M).log"
mkdir -p logs

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== OVERNIGHT SCRAPING STARTED ==="

# Activate virtual environment
if [ -f "../backend/venv/bin/activate" ]; then
    source ../backend/venv/bin/activate
    log "Virtual environment activated"
else
    log "ERROR: Virtual environment not found"
    exit 1
fi

export DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set in environment}"

# Function to get DB count
get_count() {
    PGPASSWORD="$DB_PASS" psql -h localhost -U nabavki_user -d nabavkidata -t -c "SELECT COUNT(*) FROM tenders;" 2>/dev/null | tr -d ' '
}

# Wait for OpenTender import to complete
log "Waiting for OpenTender import to complete..."
LAST_COUNT=0
STABLE_CHECKS=0

while true; do
    CURRENT_COUNT=$(get_count)
    log "Current tender count: $CURRENT_COUNT"

    if [ "$CURRENT_COUNT" == "$LAST_COUNT" ]; then
        STABLE_CHECKS=$((STABLE_CHECKS + 1))
        if [ $STABLE_CHECKS -ge 3 ]; then
            log "Database count stable for 3 checks. OpenTender import likely complete."
            break
        fi
    else
        STABLE_CHECKS=0
    fi

    LAST_COUNT=$CURRENT_COUNT
    sleep 120  # Check every 2 minutes
done

log "OpenTender import complete. Total tenders: $(get_count)"
log ""
log "=== STARTING PARALLEL E-NABAVKI SCRAPING ==="

# Run parallel scraper
./run_parallel_scrape.sh 2>&1 | tee -a "$LOG_FILE"

log ""
log "=== SCRAPING COMPLETE ==="
log "Final tender count: $(get_count)"
log "Finished: $(date)"
