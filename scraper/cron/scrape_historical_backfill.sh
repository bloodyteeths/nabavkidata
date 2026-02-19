#!/bin/bash
#
# HISTORICAL BACKFILL: Scrape 5 Years of Tender Data (Year by Year)
#
# This script performs a full historical backfill of awarded contracts from e-nabavki.gov.mk
# It scrapes YEAR BY YEAR using the archive year selector to get historical data.
# Runs in batches to prevent OOM crashes and respects the scraper lock mechanism.
#
# Target: ~100,000 historical tenders (2020-2024)
#
# Usage:
#   ./scrape_historical_backfill.sh              # Full backfill (2024 -> 2020)
#   ./scrape_historical_backfill.sh --year 2023  # Scrape specific year only
#   ./scrape_historical_backfill.sh --resume     # Resume from last progress
#   ./scrape_historical_backfill.sh --status     # Check progress
#
# Recommended: Run with nohup or screen/tmux
#   nohup ./scrape_historical_backfill.sh >> /var/log/nabavkidata/historical_backfill.log 2>&1 &
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="/home/ubuntu/nabavkidata/backend/venv"
LOG_DIR="/var/log/nabavkidata"
PROGRESS_FILE="/tmp/historical_backfill_progress.json"

# Years to scrape (most recent first)
# NOTE: The e-nabavki archive only has years 2008-2021
# Current year (2025) and recent years (2022-2024) are NOT in the archive
# They are already visible in the default view
YEARS_TO_SCRAPE="2021 2020 2019 2018 2017 2016 2015 2014 2013 2012 2011 2010 2009 2008"

# Batch settings - optimized for throughput while preventing OOM
# Each listing page has ~10 tenders, so 200 pages = ~2000 tenders per batch
PAGES_PER_BATCH=200           # Listing pages per batch
PAUSE_BETWEEN_BATCHES=10      # Seconds to wait between batches (let memory settle)
MAX_BATCHES_PER_YEAR=150      # Max batches per year (~30000 pages = ~300k tenders)

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

# Progress tracking - now includes year
save_progress() {
    local year=$1
    local batch=$2
    local start_page=$3
    local status=$4
    local tenders_scraped=$5
    echo "{\"year\": $year, \"batch\": $batch, \"start_page\": $start_page, \"status\": \"$status\", \"tenders_scraped\": $tenders_scraped, \"last_updated\": \"$(date -Iseconds)\"}" > "$PROGRESS_FILE"
}

load_progress() {
    if [ -f "$PROGRESS_FILE" ]; then
        cat "$PROGRESS_FILE"
    else
        echo '{"year": 2024, "batch": 0, "start_page": 1, "status": "not_started", "tenders_scraped": 0}'
    fi
}

show_status() {
    log "=== Historical Backfill Status ==="
    if [ -f "$PROGRESS_FILE" ]; then
        cat "$PROGRESS_FILE" | python3 -m json.tool
    else
        log "No backfill in progress"
    fi

    # Show database counts by year
    log ""
    log "=== Database Tender Counts by Year ==="
    PGPASSWORD="$DB_PASS" psql \
        -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
        -U nabavki_user -d nabavkidata \
        -c "SELECT EXTRACT(YEAR FROM publication_date) as year, COUNT(*) as count FROM tenders WHERE publication_date IS NOT NULL GROUP BY year ORDER BY year DESC;"

    log ""
    log "=== Total by Source Category ==="
    PGPASSWORD="$DB_PASS" psql \
        -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
        -U nabavki_user -d nabavkidata \
        -c "SELECT source_category, COUNT(*) FROM tenders GROUP BY source_category ORDER BY count DESC;"
    exit 0
}

# Scrape a single year
scrape_year() {
    local YEAR=$1
    local START_PAGE=${2:-1}
    local START_BATCH=${3:-1}

    log ""
    log "######################################################"
    log "# STARTING YEAR: $YEAR"
    log "######################################################"
    log ""

    local YEAR_TENDERS=0
    local ZERO_COUNT=0

    for batch in $(seq $START_BATCH $MAX_BATCHES_PER_YEAR); do
        # Calculate start page for this batch
        BATCH_START_PAGE=$((START_PAGE + (batch - START_BATCH) * PAGES_PER_BATCH))

        log ""
        log "========================================="
        log "YEAR $YEAR - BATCH $batch / $MAX_BATCHES_PER_YEAR"
        log "Scraping pages $BATCH_START_PAGE to $((BATCH_START_PAGE + PAGES_PER_BATCH - 1))"
        log "========================================="

        LOG_FILE="$LOG_DIR/historical_${YEAR}_batch_${batch}_$(date +%Y%m%d_%H%M%S).log"

        BATCH_START=$(date +%s)

        # Run scraper with year parameter for historical data
        /home/ubuntu/.local/bin/scrapy crawl nabavki \
            -a category=awarded \
            -a year=$YEAR \
            -a start_page=$BATCH_START_PAGE \
            -a max_listing_pages=$PAGES_PER_BATCH \
            -s LOG_LEVEL=INFO \
            -s LOG_FILE="$LOG_FILE" \
            -s CONCURRENT_REQUESTS=2 \
            -s DOWNLOAD_DELAY=0.3 \
            -s MEMUSAGE_LIMIT_MB=1536 \
            -s MEMUSAGE_WARNING_MB=1200 || {
            RC=$?
            log "WARNING: Year $YEAR Batch $batch finished with exit code $RC"
        }

        BATCH_END=$(date +%s)
        BATCH_DURATION=$((BATCH_END - BATCH_START))

        # Count tenders scraped in this batch
        BATCH_TENDERS=$(grep -c "Successfully extracted tender" "$LOG_FILE" 2>/dev/null || echo 0)
        YEAR_TENDERS=$((YEAR_TENDERS + BATCH_TENDERS))
        TOTAL_TENDERS=$((TOTAL_TENDERS + BATCH_TENDERS))

        log "Year $YEAR Batch $batch completed in ${BATCH_DURATION}s - $BATCH_TENDERS tenders (year total: $YEAR_TENDERS, grand total: $TOTAL_TENDERS)"

        # Save progress
        save_progress $YEAR $batch $BATCH_START_PAGE "in_progress" $TOTAL_TENDERS

        # Check if we're done with this year (no new tenders found)
        if [ "$BATCH_TENDERS" -eq 0 ]; then
            log "No new tenders found in batch $batch for year $YEAR"
            ZERO_COUNT=$((ZERO_COUNT + 1))
            if [ "$ZERO_COUNT" -ge 3 ]; then
                log "3 consecutive batches with no new tenders - year $YEAR complete"
                break
            fi
        else
            ZERO_COUNT=0
        fi

        # Check database growth every 5 batches
        if [ $((batch % 5)) -eq 0 ]; then
            log ""
            log "=== Progress Check (Year $YEAR, Batch $batch) ==="
            PGPASSWORD="$DB_PASS" psql \
                -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
                -U nabavki_user -d nabavkidata \
                -c "SELECT EXTRACT(YEAR FROM publication_date) as year, COUNT(*) FROM tenders WHERE publication_date IS NOT NULL GROUP BY year ORDER BY year DESC;" 2>/dev/null || true
        fi

        # Pause between batches to let memory settle
        if [ $batch -lt $MAX_BATCHES_PER_YEAR ]; then
            log "Pausing ${PAUSE_BETWEEN_BATCHES}s before next batch..."
            sleep $PAUSE_BETWEEN_BATCHES
        fi
    done

    log ""
    log "========================================="
    log "YEAR $YEAR COMPLETE"
    log "Tenders scraped for $YEAR: $YEAR_TENDERS"
    log "========================================="

    return 0
}

# Handle arguments
RESUME_MODE=false
SINGLE_YEAR=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --resume)
            RESUME_MODE=true
            shift
            ;;
        --status)
            show_status
            ;;
        --year)
            SINGLE_YEAR="$2"
            shift 2
            ;;
        *)
            log "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Get starting year, batch, and page
START_YEAR=2024
START_BATCH=1
START_PAGE=1
TOTAL_TENDERS=0

if [ "$RESUME_MODE" = true ]; then
    progress=$(load_progress)
    START_YEAR=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('year', 2024))")
    START_BATCH=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('batch', 0) + 1)")
    START_PAGE=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('start_page', 1) + $PAGES_PER_BATCH)")
    TOTAL_TENDERS=$(echo "$progress" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tenders_scraped', 0))")
    log "Resuming from year $START_YEAR, batch $START_BATCH, page $START_PAGE (total so far: $TOTAL_TENDERS)"
fi

if [ -n "$SINGLE_YEAR" ]; then
    YEARS_TO_SCRAPE="$SINGLE_YEAR"
    log "Scraping single year: $SINGLE_YEAR"
fi

# Acquire lock
acquire_scraper_lock || {
    log "Another scraper is running. Exiting."
    exit 0
}

log "========================================="
log "HISTORICAL BACKFILL STARTING (YEAR BY YEAR)"
log "========================================="
log "Years to scrape: $YEARS_TO_SCRAPE"
log "Pages per batch: $PAGES_PER_BATCH"
log "Max batches per year: $MAX_BATCHES_PER_YEAR"
log "Progress file: $PROGRESS_FILE"
log "========================================="

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Track totals
START_TIME=$(date +%s)
SKIP_UNTIL_YEAR=true

# If resuming, we need to skip years until we reach the resume year
if [ "$RESUME_MODE" = true ]; then
    for year in $YEARS_TO_SCRAPE; do
        if [ "$year" = "$START_YEAR" ]; then
            SKIP_UNTIL_YEAR=false
            # Resume this year from where we left off
            scrape_year $year $START_PAGE $START_BATCH
        elif [ "$SKIP_UNTIL_YEAR" = false ]; then
            # Subsequent years start fresh
            scrape_year $year 1 1
        fi
    done
else
    # Fresh start - scrape all years
    for year in $YEARS_TO_SCRAPE; do
        scrape_year $year 1 1
    done
fi

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))

log ""
log "========================================="
log "HISTORICAL BACKFILL COMPLETE"
log "========================================="
log "Years scraped: $YEARS_TO_SCRAPE"
log "Total tenders scraped: $TOTAL_TENDERS"
log "Duration: ${HOURS}h ${MINUTES}m"
log "========================================="

# Final progress save
save_progress 2020 0 1 "completed" $TOTAL_TENDERS

# Show final database stats
log ""
log "=== Final Database Stats ==="
PGPASSWORD="$DB_PASS" psql \
    -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
    -U nabavki_user -d nabavkidata \
    -c "SELECT EXTRACT(YEAR FROM publication_date) as year, COUNT(*) FROM tenders WHERE publication_date IS NOT NULL GROUP BY year ORDER BY year DESC;"

# Deactivate virtual environment
deactivate 2>/dev/null || true

log "Historical backfill finished"
