#!/bin/bash
#
# Parallel Document Extraction
# Runs multiple extraction processes for different document categories
#
# Usage: ./parallel_extract.sh [num_workers] [docs_per_worker]
#

set -e

NUM_WORKERS=${1:-2}
DOCS_PER_WORKER=${2:-1000}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="/home/ubuntu/nabavkidata/backend/venv"
LOG_DIR="/tmp"

echo "[$(date)] Starting parallel extraction with $NUM_WORKERS workers, $DOCS_PER_WORKER docs each"

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Define document categories to process in parallel
# Each worker processes a different category for better distribution
CATEGORIES=("contract" "technical_specs" "award_decision" "tender_docs" "other")

pids=()

for i in $(seq 1 $NUM_WORKERS); do
    # Rotate through categories
    cat_idx=$(( (i - 1) % ${#CATEGORIES[@]} ))
    category="${CATEGORIES[$cat_idx]}"

    log_file="$LOG_DIR/extract_worker_${i}.log"

    echo "[$(date)] Starting worker $i for category: $category"

    # Run extraction in background
    python3 "$SCRIPT_DIR/process_documents.py" \
        --limit $DOCS_PER_WORKER \
        --doc-categories "$category" \
        > "$log_file" 2>&1 &

    pids+=($!)

    # Small delay to avoid race conditions
    sleep 2
done

echo "[$(date)] All $NUM_WORKERS workers started. PIDs: ${pids[*]}"
echo "[$(date)] Monitoring logs in $LOG_DIR/extract_worker_*.log"

# Wait for all workers
wait "${pids[@]}"

echo "[$(date)] All workers completed"

# Show summary
total=0
for i in $(seq 1 $NUM_WORKERS); do
    log_file="$LOG_DIR/extract_worker_${i}.log"
    count=$(grep -c 'Updated document' "$log_file" 2>/dev/null || echo 0)
    echo "Worker $i: $count documents extracted"
    total=$((total + count))
done

echo "Total extracted: $total documents"
