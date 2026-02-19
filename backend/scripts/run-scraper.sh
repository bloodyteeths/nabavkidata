#!/usr/bin/env bash

###############################################################################
# run-scraper.sh - Tender Scraper Execution Script
#
# Triggers the tender scraping job:
# - Runs the scraper management command
# - Logs output to file
# - Can be scheduled with cron
# - Handles errors and notifications
#
# Usage: ./scripts/run-scraper.sh [--source <source>] [--full]
#
# Examples:
#   ./scripts/run-scraper.sh                    # Run all scrapers
#   ./scripts/run-scraper.sh --source enarocanje # Run specific source
#   ./scripts/run-scraper.sh --full             # Full scrape (not incremental)
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/scraper_$(date +%Y%m%d_%H%M%S).log"
SOURCE=""
FULL_SCRAPE=false

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --source)
            SOURCE="$2"
            shift 2
            ;;
        --full)
            FULL_SCRAPE=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Setup logging
setup_logging() {
    mkdir -p "$LOG_DIR"
    log_info "Logging to: $LOG_FILE"
}

# Load environment variables
load_env() {
    if [ -f "$PROJECT_ROOT/backend/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/backend/.env" | xargs)
        log_info "Loaded environment variables"
    else
        log_error "backend/.env not found"
        exit 1
    fi
}

# Run scraper
run_scraper() {
    log_info "Starting scraper job..."

    cd "$PROJECT_ROOT/backend"

    # Activate virtual environment
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        log_error "Virtual environment not found"
        exit 1
    fi

    # Build scraper command
    local cmd="python manage.py scrape_tenders"

    if [ -n "$SOURCE" ]; then
        cmd="$cmd --source $SOURCE"
        log_info "Scraping source: $SOURCE"
    else
        log_info "Scraping all sources"
    fi

    if [ "$FULL_SCRAPE" = true ]; then
        cmd="$cmd --full"
        log_info "Running full scrape"
    else
        log_info "Running incremental scrape"
    fi

    # Execute scraper
    log_info "Executing: $cmd"

    if $cmd 2>&1 | tee -a "$LOG_FILE"; then
        log_info "Scraper completed successfully"
        return 0
    else
        log_error "Scraper failed with exit code $?"
        return 1
    fi
}

# Send notification on failure
send_notification() {
    local status=$1

    if [ "$status" -ne 0 ]; then
        log_error "Scraper failed, sending notification..."

        # Send email notification if configured
        if command -v mail &> /dev/null && [ -n "${ADMIN_EMAIL:-}" ]; then
            echo "Scraper job failed. Check logs at: $LOG_FILE" | mail -s "Scraper Failure Alert" "$ADMIN_EMAIL"
            log_info "Email notification sent to $ADMIN_EMAIL"
        fi
    fi
}

# Cleanup old logs
cleanup_logs() {
    log_info "Cleaning up old log files (keeping last 30 days)..."

    find "$LOG_DIR" -name "scraper_*.log" -mtime +30 -delete

    local remaining=$(find "$LOG_DIR" -name "scraper_*.log" | wc -l)
    log_info "Remaining log files: $remaining"
}

# Main execution
main() {
    setup_logging
    log_info "=== Scraper Job Started ==="
    log_info "Timestamp: $(date)"

    load_env

    local exit_code=0
    run_scraper || exit_code=$?

    send_notification $exit_code
    cleanup_logs

    log_info "=== Scraper Job Completed ==="
    log_info "Exit code: $exit_code"

    exit $exit_code
}

main "$@"
