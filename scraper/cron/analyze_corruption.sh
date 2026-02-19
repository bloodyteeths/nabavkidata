#!/bin/bash
# ============================================================================
# Corruption Detection Cron Job
# Runs daily to analyze tenders for corruption indicators
# Schedule: 0 3 * * * (3 AM daily)
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="/var/log/nabavkidata"
LOG_FILE="$LOG_DIR/corruption_analysis.log"
LOCK_FILE="/tmp/corruption_analysis.lock"

# Load database credentials from environment
if [ -f "$PROJECT_DIR/backend/.env.production" ]; then
    set -a
    source "$PROJECT_DIR/backend/.env.production"
    set +a
fi

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Analysis already running (PID: $PID)" >> "$LOG_FILE"
        exit 0
    fi
fi

echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log "============================================================"
log "Starting corruption detection analysis"
log "============================================================"

cd "$PROJECT_DIR/ai"

# Activate virtual environment if it exists
if [ -f "$PROJECT_DIR/backend/venv/bin/activate" ]; then
    
fi

# Run corruption analysis
log "Running full corruption analysis..."

python3 corruption_detector.py analyze 2>&1 | while read line; do
    log "$line"
done

ANALYSIS_EXIT_CODE=${PIPESTATUS[0]}

if [ $ANALYSIS_EXIT_CODE -eq 0 ]; then
    log "✓ Corruption analysis completed successfully"

    # Refresh materialized views so API serves fresh data
    log "Refreshing corruption materialized views..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT:-5432}" \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        -c "SELECT * FROM refresh_corruption_views();" 2>&1 | while read line; do
        log "  $line"
    done
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log "✓ Materialized views refreshed successfully"
    else
        log "WARNING: View refresh failed - API may serve stale data"
    fi

    # Get stats
    log "Fetching analysis statistics..."
    STATS=$(python3 corruption_detector.py stats 2>/dev/null | head -1)
    log "Stats: $STATS"
else
    log "✗ Corruption analysis failed with exit code: $ANALYSIS_EXIT_CODE"
fi

# Write health file
HEALTH_FILE="$LOG_DIR/corruption_health.json"
cat > "$HEALTH_FILE" << EOF
{
    "last_run": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
    "status": "$([ $ANALYSIS_EXIT_CODE -eq 0 ] && echo 'success' || echo 'failed')",
    "exit_code": $ANALYSIS_EXIT_CODE
}
EOF

log "============================================================"
log "Corruption analysis finished"
log "============================================================"

exit $ANALYSIS_EXIT_CODE
