#!/bin/bash
# Rotate and compress old logs to prevent disk fill
# Runs daily at 1 AM UTC

set -e

LOG_DIR="/home/ubuntu/nabavkidata/scraper/logs"
ROTATE_LOG="$LOG_DIR/rotate.log"

echo "[$(date)] Starting log rotation..." | tee -a "$ROTATE_LOG"

cd "$LOG_DIR"

# Count current log files
TOTAL_LOGS=$(find . -name "*.log" -type f | wc -l)
echo "Total log files: $TOTAL_LOGS" | tee -a "$ROTATE_LOG"

# Compress logs older than 7 days
echo "Compressing logs older than 7 days..." | tee -a "$ROTATE_LOG"
COMPRESSED=0

find . -name "*.log" -type f -mtime +7 -print0 | while IFS= read -r -d '' file; do
    if [ -f "$file" ]; then
        gzip "$file"
        COMPRESSED=$((COMPRESSED + 1))
        echo "Compressed: $file" | tee -a "$ROTATE_LOG"
    fi
done

echo "Compressed $COMPRESSED log files" | tee -a "$ROTATE_LOG"

# Delete compressed logs older than 30 days
echo "Deleting compressed logs older than 30 days..." | tee -a "$ROTATE_LOG"
DELETED=$(find . -name "*.log.gz" -type f -mtime +30 -delete -print | wc -l)
echo "Deleted $DELETED compressed log files" | tee -a "$ROTATE_LOG"

# Delete empty log files
echo "Deleting empty log files..." | tee -a "$ROTATE_LOG"
EMPTY_DELETED=$(find . -name "*.log" -type f -empty -delete -print | wc -l)
echo "Deleted $EMPTY_DELETED empty log files" | tee -a "$ROTATE_LOG"

# Calculate disk space saved
SPACE_USED=$(du -sh . | cut -f1)
echo "Log directory size after rotation: $SPACE_USED" | tee -a "$ROTATE_LOG"

# Keep rotation log itself small (only last 1000 lines)
if [ -f "$ROTATE_LOG" ]; then
    tail -1000 "$ROTATE_LOG" > "$ROTATE_LOG.tmp" && mv "$ROTATE_LOG.tmp" "$ROTATE_LOG"
fi

echo "[$(date)] Log rotation completed successfully" | tee -a "$ROTATE_LOG"
