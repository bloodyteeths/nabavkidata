#!/bin/bash
#
# CRON SCRIPT: Gemini AI Product Item Extraction
#
# Extracts product items (names, quantities, prices) from documents
# that have been text-extracted but not yet processed by Gemini.
#
# This fills the gap between document text extraction (process_documents.sh)
# and the product_items table that powers price intelligence.
#
# Schedule: every 2 hours (offset from doc extraction)
# Processes 200 docs per run (~100 docs/hour at 0.5s delay)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Lock to prevent duplicate instances
LOCKFILE="/tmp/extract_product_items.lock"
MAX_LOCK_AGE=7200  # 2 hours max

if [ -f "$LOCKFILE" ]; then
    OTHER_PID=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$OTHER_PID" ] && [[ "$OTHER_PID" =~ ^[0-9]+$ ]] && kill -0 "$OTHER_PID" 2>/dev/null; then
        ELAPSED=$(ps -o etimes= -p "$OTHER_PID" 2>/dev/null | tr -d ' ')
        if [ -n "$ELAPSED" ] && [ "$ELAPSED" -gt "$MAX_LOCK_AGE" ]; then
            log "STALE: Extraction PID $OTHER_PID running for ${ELAPSED}s, killing..."
            kill -TERM "$OTHER_PID" 2>/dev/null
            sleep 5
            kill -0 "$OTHER_PID" 2>/dev/null && kill -9 "$OTHER_PID" 2>/dev/null
            rm -f "$LOCKFILE"
        else
            log "Another extraction is running (PID $OTHER_PID, ${ELAPSED:-?}s), skipping."
            exit 0
        fi
    else
        log "Stale lock (PID $OTHER_PID not running), removing."
        rm -f "$LOCKFILE"
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f '$LOCKFILE'" EXIT

cd "$PROJECT_ROOT"

# Load environment
source .env 2>/dev/null || true
export DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"

log "Starting Gemini product item extraction..."

# Process 200 docs per run, 2 workers to throttle API calls
timeout --signal=TERM --kill-after=30 6000 \
    /usr/bin/python3 extract_all_items.py --limit 200 --workers 2 || {
    RC=$?
    log "WARNING: Extraction exited with code $RC"
}

log "Product item extraction completed"
