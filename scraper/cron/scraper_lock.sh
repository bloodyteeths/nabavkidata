#!/bin/bash
#
# Scraper Lock Utility
#
# Provides a file-based locking mechanism to ensure only one
# scraper job runs at a time, preventing OOM crashes from overlapping jobs.
#
# Features:
#   - 5-minute wait timeout (cron will retry next interval)
#   - 3-hour max hold time (auto-kills stuck lock holders)
#   - Orphaned Chromium cleanup on stale lock kill
#
# Usage:
#   source /path/to/scraper_lock.sh
#   acquire_scraper_lock || exit 1
#   # ... your scraper code ...
#   release_scraper_lock
#

LOCK_FILE="/tmp/nabavkidata_scraper.lock"
LOCK_FD=200
LOCK_TIMEOUT=300         # 5 minutes wait to acquire (was 4 hours)
MAX_LOCK_AGE=10800       # 3 hours max hold time - kill holder if exceeded

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Kill a stale lock holder that has been running too long
kill_stale_lock_holder() {
    if [ ! -f "$LOCK_FILE" ]; then
        return 1  # No lock file
    fi

    local holder_pid
    holder_pid=$(cat "$LOCK_FILE" 2>/dev/null | head -1)

    # Check if PID is a number and is running
    if [ -z "$holder_pid" ] || ! [[ "$holder_pid" =~ ^[0-9]+$ ]]; then
        return 1
    fi

    if ! kill -0 "$holder_pid" 2>/dev/null; then
        log "Lock holder PID $holder_pid is dead, lock is stale"
        return 0  # PID is dead, flock will handle it
    fi

    # PID is alive -- check how long it has been running
    local elapsed
    elapsed=$(ps -o etimes= -p "$holder_pid" 2>/dev/null | tr -d ' ')
    if [ -z "$elapsed" ]; then
        return 1
    fi

    if [ "$elapsed" -gt "$MAX_LOCK_AGE" ]; then
        local cmd
        cmd=$(ps -o args= -p "$holder_pid" 2>/dev/null | head -c 120)
        log "STALE LOCK: PID $holder_pid running for ${elapsed}s (max ${MAX_LOCK_AGE}s): $cmd"
        log "Killing stale lock holder..."
        kill -TERM "$holder_pid" 2>/dev/null
        sleep 5
        if kill -0 "$holder_pid" 2>/dev/null; then
            log "Force killing PID $holder_pid"
            kill -9 "$holder_pid" 2>/dev/null
        fi
        # Kill orphaned Playwright/Chromium processes
        pkill -f "chromium.*--headless" 2>/dev/null || true
        sleep 2
        return 0  # Stale holder killed, retry lock
    fi

    return 1  # Lock holder is alive and within time limit
}

# Acquire lock with timeout
acquire_scraper_lock() {
    # First, check for stale lock holders
    kill_stale_lock_holder

    exec 200>"$LOCK_FILE"

    log "Attempting to acquire scraper lock..."

    # Try to acquire exclusive lock with timeout
    if flock -x -w "$LOCK_TIMEOUT" 200; then
        log "Lock acquired successfully"
        echo $$ > "$LOCK_FILE"
        return 0
    else
        log "Failed to acquire lock (another scraper is running)"
        return 1
    fi
}

# Release lock
release_scraper_lock() {
    if [ -n "$LOCK_FD" ]; then
        flock -u 200
        log "Lock released"
    fi
}

# Ensure lock is released on exit
trap release_scraper_lock EXIT
