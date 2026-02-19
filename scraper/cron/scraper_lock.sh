#!/bin/bash
#
# Scraper Lock Utility
#
# This script provides a file-based locking mechanism to ensure only one
# scraper job runs at a time, preventing OOM crashes from overlapping jobs.
#
# Usage:
#   source /path/to/scraper_lock.sh
#   acquire_scraper_lock || exit 1
#   # ... your scraper code ...
#   release_scraper_lock
#

LOCK_FILE="/tmp/nabavkidata_scraper.lock"
LOCK_FD=200
LOCK_TIMEOUT=14400  # 4 hours in seconds

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Acquire lock with timeout
acquire_scraper_lock() {
    exec 200>"$LOCK_FILE"
    
    log "Attempting to acquire scraper lock..."
    
    # Try to acquire exclusive lock with timeout
    if flock -x -w "$LOCK_TIMEOUT" 200; then
        log "✓ Lock acquired successfully"
        echo $$ > "$LOCK_FILE"
        return 0
    else
        log "✗ Failed to acquire lock (another scraper is running)"
        return 1
    fi
}

# Release lock
release_scraper_lock() {
    if [ -n "$LOCK_FD" ]; then
        flock -u 200
        log "✓ Lock released"
    fi
}

# Ensure lock is released on exit
trap release_scraper_lock EXIT
