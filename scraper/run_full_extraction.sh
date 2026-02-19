#!/bin/bash
#
# Run full item extraction from all contracts
# This script processes contracts in batches until all are done
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source environment
source /home/ubuntu/nabavkidata/backend/venv/bin/activate
export $(grep GEMINI_API_KEY .env | xargs)

LOG_DIR="/var/log/nabavkidata"
mkdir -p "$LOG_DIR"

BATCH_SIZE=100
PAUSE_BETWEEN_BATCHES=30

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "========================================="
log "STARTING FULL CONTRACT ITEM EXTRACTION"
log "========================================="

BATCH=1
TOTAL_ITEMS=0

while true; do
    log ""
    log "=== Batch $BATCH (processing $BATCH_SIZE contracts) ==="

    LOG_FILE="$LOG_DIR/contract_extraction_batch_${BATCH}_$(date +%Y%m%d_%H%M%S).log"

    # Run extraction
    python3 extract_items_from_contracts.py --limit $BATCH_SIZE 2>&1 | tee "$LOG_FILE"

    # Check results
    ITEMS_EXTRACTED=$(grep -c "Saved.*items for tender" "$LOG_FILE" 2>/dev/null || echo 0)
    CONTRACTS_PROCESSED=$(grep "Processing contract" "$LOG_FILE" | wc -l)

    log "Batch $BATCH: Processed $CONTRACTS_PROCESSED contracts"

    # Check if we found any contracts to process
    if grep -q "Found 0 contracts to process" "$LOG_FILE"; then
        log "No more contracts to process - extraction complete!"
        break
    fi

    # Check if very few contracts remain
    if [ "$CONTRACTS_PROCESSED" -lt 10 ]; then
        log "Only $CONTRACTS_PROCESSED contracts remaining - finishing up"
    fi

    BATCH=$((BATCH + 1))

    # Pause between batches to avoid API rate limits
    log "Pausing ${PAUSE_BETWEEN_BATCHES}s before next batch..."
    sleep $PAUSE_BETWEEN_BATCHES
done

log ""
log "========================================="
log "EXTRACTION COMPLETE"
log "========================================="
log "Total batches: $BATCH"

# Show final stats
log ""
log "=== Final Database Stats ==="
PGPASSWORD="$DB_PASS" psql \
    -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
    -U nabavki_user -d nabavkidata \
    -c "SELECT extraction_method, COUNT(*) as items, COUNT(DISTINCT tender_id) as tenders FROM product_items GROUP BY extraction_method ORDER BY items DESC;"

log "Full extraction finished"
