#!/bin/bash
#
# RECENT BACKFILL: Scrape 2022-2024 Data from Default View
#
# This script performs a backfill of recent years (2022-2024) that are NOT in the archive
# but ARE in the default view. It uses REVERSE pagination to start from the oldest data
# (last page) and work backwards towards the newest data.
#
# The default view has ~110k tenders sorted newest first.
# 2022-2024 data is at the END of the pagination (pages 8000-11000+)
#
# Usage:
#   ./scrape_recent_backfill.sh                    # Full reverse backfill
#   ./scrape_recent_backfill.sh --max-pages 500   # Limit to 500 pages
#   ./scrape_recent_backfill.sh --status          # Check progress
#
# Recommended: Run with nohup or screen/tmux
#   nohup ./scrape_recent_backfill.sh >> /var/log/nabavkidata/recent_backfill.log 2>&1 &
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/nabavkidata"
PROGRESS_FILE="/tmp/recent_backfill_progress.json"

# Batch settings
PAGES_PER_BATCH=100           # Listing pages per batch
PAUSE_BETWEEN_BATCHES=60      # Seconds to wait between batches
MAX_BATCHES=100               # Default: 100 batches * 100 pages = 10000 pages (~100k tenders)

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

# Progress tracking
save_progress() {
    local batch=$1
    local pages_scraped=$2
    local status=$3
    local tenders_scraped=$4
    echo "{\"batch\": $batch, \"pages_scraped\": $pages_scraped, \"status\": \"$status\", \"tenders_scraped\": $tenders_scraped, \"last_updated\": \"$(date -Iseconds)\"}" > "$PROGRESS_FILE"
}

load_progress() {
    if [ -f "$PROGRESS_FILE" ]; then
        cat "$PROGRESS_FILE"
    else
        echo '{"batch": 0, "pages_scraped": 0, "status": "not_started", "tenders_scraped": 0}'
    fi
}

show_status() {
    log "=== Recent Backfill Status ==="
    if [ -f "$PROGRESS_FILE" ]; then
        cat "$PROGRESS_FILE" | python3 -m json.tool
    else
        log "No backfill in progress"
    fi

    # Show database counts by year
    log ""
    log "=== Database Tender Counts by Year ==="
    PGPASSWORD="$DB_PASS" psql \
        -h localhost \
        -U nabavki_user -d nabavkidata \
        -c "SELECT EXTRACT(YEAR FROM publication_date) as year, COUNT(*) as count FROM tenders WHERE publication_date IS NOT NULL GROUP BY year ORDER BY year DESC;"
    exit 0
}

# Handle arguments
MAX_PAGES_OVERRIDE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --status)
            show_status
            ;;
        --max-pages)
            MAX_PAGES_OVERRIDE="$2"
            shift 2
            ;;
        *)
            log "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [ -n "$MAX_PAGES_OVERRIDE" ]; then
    MAX_BATCHES=$(( (MAX_PAGES_OVERRIDE + PAGES_PER_BATCH - 1) / PAGES_PER_BATCH ))
    log "Limiting to $MAX_PAGES_OVERRIDE pages ($MAX_BATCHES batches)"
fi

# Acquire lock
acquire_scraper_lock || {
    log "Another scraper is running. Exiting."
    exit 0
}

log "========================================="
log "RECENT BACKFILL STARTING (REVERSE PAGINATION)"
log "========================================="
log "Mode: Reverse pagination (oldest data first)"
log "Category: awarded (default view, no year selection)"
log "Pages per batch: $PAGES_PER_BATCH"
log "Max batches: $MAX_BATCHES"
log "Progress file: $PROGRESS_FILE"
log "========================================="

# Activate virtual environment

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Track totals
TOTAL_TENDERS=0
TOTAL_PAGES=0
START_TIME=$(date +%s)
ZERO_COUNT=0

for batch in $(seq 1 $MAX_BATCHES); do
    log ""
    log "========================================="
    log "BATCH $batch / $MAX_BATCHES"
    log "Scraping with reverse pagination (batch of $PAGES_PER_BATCH pages)"
    log "========================================="

    LOG_FILE="$LOG_DIR/recent_backfill_batch_${batch}_$(date +%Y%m%d_%H%M%S).log"

    BATCH_START=$(date +%s)

    # Run scraper with REVERSE pagination
    # reverse=True starts from last page and goes backwards
    /usr/local/bin/scrapy crawl nabavki \
        -a category=awarded \
        -a reverse=True \
        -a max_listing_pages=$PAGES_PER_BATCH \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE="$LOG_FILE" \
        -s CONCURRENT_REQUESTS=1 \
        -s DOWNLOAD_DELAY=0.5 \
        -s MEMUSAGE_LIMIT_MB=1536 \
        -s MEMUSAGE_WARNING_MB=1200 || {
        RC=$?
        log "WARNING: Batch $batch finished with exit code $RC"
    }

    BATCH_END=$(date +%s)
    BATCH_DURATION=$((BATCH_END - BATCH_START))

    # Count tenders scraped in this batch
    BATCH_TENDERS=$(grep -c "Successfully extracted tender" "$LOG_FILE" 2>/dev/null || echo 0)
    TOTAL_TENDERS=$((TOTAL_TENDERS + BATCH_TENDERS))
    TOTAL_PAGES=$((TOTAL_PAGES + PAGES_PER_BATCH))

    log "Batch $batch completed in ${BATCH_DURATION}s - $BATCH_TENDERS tenders scraped (total: $TOTAL_TENDERS)"

    # Save progress
    save_progress $batch $TOTAL_PAGES "in_progress" $TOTAL_TENDERS

    # Check if we're done (no new tenders found)
    if [ "$BATCH_TENDERS" -eq 0 ]; then
        log "No new tenders found in batch $batch"
        ZERO_COUNT=$((ZERO_COUNT + 1))
        if [ "$ZERO_COUNT" -ge 3 ]; then
            log "3 consecutive batches with no new tenders - backfill complete"
            break
        fi
    else
        ZERO_COUNT=0
    fi

    # Check database growth every 5 batches
    if [ $((batch % 5)) -eq 0 ]; then
        log ""
        log "=== Progress Check (Batch $batch) ==="
        PGPASSWORD="$DB_PASS" psql \
            -h localhost \
            -U nabavki_user -d nabavkidata \
            -c "SELECT EXTRACT(YEAR FROM publication_date) as year, COUNT(*) FROM tenders WHERE publication_date IS NOT NULL GROUP BY year ORDER BY year DESC;" 2>/dev/null || true
    fi

    # Pause between batches
    if [ $batch -lt $MAX_BATCHES ]; then
        log "Pausing ${PAUSE_BETWEEN_BATCHES}s before next batch..."
        sleep $PAUSE_BETWEEN_BATCHES
    fi
done

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))

log ""
log "========================================="
log "RECENT BACKFILL COMPLETE"
log "========================================="
log "Total batches: $batch"
log "Total pages scraped: $TOTAL_PAGES"
log "Total tenders scraped: $TOTAL_TENDERS"
log "Duration: ${HOURS}h ${MINUTES}m"
log "========================================="

# Final progress save
save_progress $batch $TOTAL_PAGES "completed" $TOTAL_TENDERS

# Show final database stats
log ""
log "=== Final Database Stats ==="
PGPASSWORD="$DB_PASS" psql \
    -h localhost \
    -U nabavki_user -d nabavkidata \
    -c "SELECT EXTRACT(YEAR FROM publication_date) as year, COUNT(*) FROM tenders WHERE publication_date IS NOT NULL GROUP BY year ORDER BY year DESC;"

# Deactivate virtual environment

log "Recent backfill finished"
