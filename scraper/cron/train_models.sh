#!/bin/bash
#
# Weekly Model Retraining Script for Corruption Detection
#
# This script:
# 1. Runs the training pipeline with latest data
# 2. Compares new model performance with previous best
# 3. Deploys new model if performance improved
# 4. Runs predictions on new tenders
# 5. Sends email notification with results
#
# Schedule: Weekly on Sunday at 3 AM UTC
# Crontab: 0 3 * * 0 /home/ubuntu/nabavkidata/scraper/cron/train_models.sh >> /var/log/nabavkidata/train_models.log 2>&1
#
# Author: NabavkiData
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="/var/log/nabavkidata"
MODELS_DIR="$PROJECT_ROOT/ai/corruption/ml_models/trained"
BACKUP_DIR="$PROJECT_ROOT/ai/corruption/ml_models/backup"
LOCK_FILE="/tmp/train_models.lock"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Database URL from environment or .env file
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Logging
LOG_FILE="$LOG_DIR/train_models_$TIMESTAMP.log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Cleanup function
cleanup() {
    rm -f "$LOCK_FILE"
    log "Lock file removed"
}
trap cleanup EXIT

# Check for existing process
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        error "Training already running (PID: $PID). Exiting."
        exit 1
    fi
    log "Removing stale lock file"
    rm -f "$LOCK_FILE"
fi

# Create lock file
echo $$ > "$LOCK_FILE"

log "======================================"
log "Starting Weekly Model Training"
log "======================================"
log "Project Root: $PROJECT_ROOT"
log "Models Dir: $MODELS_DIR"
log "Timestamp: $TIMESTAMP"

# Activate virtual environment

# Create directories
mkdir -p "$MODELS_DIR"
mkdir -p "$BACKUP_DIR"

# Backup previous models
if [ -d "$MODELS_DIR" ] && [ "$(ls -A $MODELS_DIR)" ]; then
    log "Backing up previous models to $BACKUP_DIR/$TIMESTAMP"
    mkdir -p "$BACKUP_DIR/$TIMESTAMP"
    cp -r "$MODELS_DIR/"* "$BACKUP_DIR/$TIMESTAMP/" || true
fi

# Get previous best F1 score
PREV_BEST_F1=0
if [ -f "$MODELS_DIR/training_report.json" ]; then
    PREV_BEST_F1=$(python3 -c "
import json
try:
    with open('$MODELS_DIR/training_report.json') as f:
        report = json.load(f)
        best = report.get('best_model', {})
        print(best.get('test_f1', 0))
except:
    print(0)
")
    log "Previous best F1 score: $PREV_BEST_F1"
fi

# Run training pipeline
log "Starting training pipeline..."
cd "$PROJECT_ROOT"

TRAIN_OUTPUT=$(python3 -m ai.corruption.ml_models.train_pipeline \
    --output-dir "$MODELS_DIR" \
    --models all \
    --verbose 2>&1) || {
    error "Training pipeline failed"
    echo "$TRAIN_OUTPUT"

    # Restore previous models
    if [ -d "$BACKUP_DIR/$TIMESTAMP" ]; then
        log "Restoring previous models"
        rm -rf "$MODELS_DIR"/*
        cp -r "$BACKUP_DIR/$TIMESTAMP/"* "$MODELS_DIR/" || true
    fi

    # Send failure notification
    if [ -n "$ALERT_EMAIL" ]; then
        echo "Model training failed at $TIMESTAMP. Check logs at $LOG_FILE" | \
            mail -s "NabavkiData: Model Training FAILED" "$ALERT_EMAIL"
    fi

    exit 1
}

echo "$TRAIN_OUTPUT"

# Get new best F1 score
NEW_BEST_F1=0
if [ -f "$MODELS_DIR/training_report.json" ]; then
    NEW_BEST_F1=$(python3 -c "
import json
try:
    with open('$MODELS_DIR/training_report.json') as f:
        report = json.load(f)
        best = report.get('best_model', {})
        print(best.get('test_f1', 0))
except:
    print(0)
")
fi

log "New best F1 score: $NEW_BEST_F1"

# Compare performance
IMPROVED=$(python3 -c "
prev = float('$PREV_BEST_F1')
new = float('$NEW_BEST_F1')
improvement = new - prev
print('yes' if improvement >= -0.01 else 'no')  # Allow 1% regression
print(f'{improvement:.4f}')
" | head -n 1)

IMPROVEMENT_DELTA=$(python3 -c "
prev = float('$PREV_BEST_F1')
new = float('$NEW_BEST_F1')
print(f'{(new - prev) * 100:.2f}')
")

if [ "$IMPROVED" = "yes" ]; then
    log "Model performance acceptable (F1 change: ${IMPROVEMENT_DELTA}%)"

    # Clean old backups (keep last 4 weeks)
    log "Cleaning old backups..."
    cd "$BACKUP_DIR"
    ls -dt */ 2>/dev/null | tail -n +5 | xargs rm -rf || true

else
    log "Model performance degraded significantly (F1 change: ${IMPROVEMENT_DELTA}%)"
    log "Restoring previous models..."

    rm -rf "$MODELS_DIR"/*
    cp -r "$BACKUP_DIR/$TIMESTAMP/"* "$MODELS_DIR/" || true

    log "Previous models restored"
fi

# Run predictions on new tenders
log "Running predictions on new tenders..."
cd "$PROJECT_ROOT"

PREDICT_OUTPUT=$(python3 -m ai.corruption.ml_models.predict_pipeline \
    --models-dir "$MODELS_DIR" \
    --limit 5000 \
    --batch-size 100 \
    --incremental \
    --verbose 2>&1) || {
    error "Prediction pipeline failed (non-fatal)"
    echo "$PREDICT_OUTPUT"
}

echo "$PREDICT_OUTPUT"

# Extract prediction summary
PREDICTIONS_PROCESSED=0
HIGH_RISK_COUNT=0
CRITICAL_COUNT=0

if echo "$PREDICT_OUTPUT" | grep -q "Total Processed"; then
    PREDICTIONS_PROCESSED=$(echo "$PREDICT_OUTPUT" | grep "Total Processed" | awk '{print $NF}')
    HIGH_RISK_COUNT=$(echo "$PREDICT_OUTPUT" | grep "High Risk" | awk '{print $NF}')
    CRITICAL_COUNT=$(echo "$PREDICT_OUTPUT" | grep "Critical" | awk '{print $NF}')
fi

# Generate summary
SUMMARY="
Weekly Model Training Summary - $TIMESTAMP
==========================================

Training Results:
- Previous Best F1: $PREV_BEST_F1
- New Best F1: $NEW_BEST_F1
- Improvement: ${IMPROVEMENT_DELTA}%
- Status: $([ "$IMPROVED" = "yes" ] && echo "DEPLOYED" || echo "REVERTED")

Prediction Results:
- Tenders Processed: $PREDICTIONS_PROCESSED
- High Risk Found: $HIGH_RISK_COUNT
- Critical Found: $CRITICAL_COUNT

Log File: $LOG_FILE
Models Directory: $MODELS_DIR
"

log "$SUMMARY"

# Send email notification
if [ -n "$ALERT_EMAIL" ]; then
    STATUS=$([ "$IMPROVED" = "yes" ] && echo "SUCCESS" || echo "REVERTED")
    echo "$SUMMARY" | mail -s "NabavkiData: Model Training $STATUS" "$ALERT_EMAIL"
    log "Email notification sent to $ALERT_EMAIL"
fi

# Write status file for monitoring
cat > "$MODELS_DIR/last_training_status.json" << EOF
{
    "timestamp": "$TIMESTAMP",
    "status": "$([ "$IMPROVED" = "yes" ] && echo "success" || echo "reverted")",
    "previous_f1": $PREV_BEST_F1,
    "new_f1": $NEW_BEST_F1,
    "improvement_pct": $IMPROVEMENT_DELTA,
    "predictions_processed": $PREDICTIONS_PROCESSED,
    "high_risk_count": $HIGH_RISK_COUNT,
    "critical_count": $CRITICAL_COUNT,
    "log_file": "$LOG_FILE"
}
EOF

log "======================================"
log "Training Complete"
log "======================================"

exit 0
