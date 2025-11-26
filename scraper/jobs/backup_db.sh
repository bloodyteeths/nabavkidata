#!/bin/bash
# Database backup for data protection
# Runs daily at 5 AM UTC

set -e

BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/ubuntu/nabavkidata/scraper/logs/backup_${DATE}.log"

echo "[$(date)] Starting database backup..." | tee -a "$LOG_FILE"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Get database URL from environment
source /home/ubuntu/nabavkidata/venv/bin/activate

# Extract database connection details
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL not set" | tee -a "$LOG_FILE"
    exit 1
fi

echo "Backup destination: $BACKUP_DIR/nabavkidata_${DATE}.sql.gz" | tee -a "$LOG_FILE"

# Backup critical tables
echo "Backing up database tables..." | tee -a "$LOG_FILE"

pg_dump "$DATABASE_URL" \
    --table=tenders \
    --table=documents \
    --table=users \
    --table=subscriptions \
    --table=saved_searches \
    --format=plain \
    --no-owner \
    --no-privileges \
    --file="$BACKUP_DIR/nabavkidata_${DATE}.sql" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Database backup failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

# Compress backup
echo "Compressing backup..." | tee -a "$LOG_FILE"
gzip "$BACKUP_DIR/nabavkidata_${DATE}.sql"

# Get backup size
BACKUP_SIZE=$(du -h "$BACKUP_DIR/nabavkidata_${DATE}.sql.gz" | cut -f1)
echo "Backup size: $BACKUP_SIZE" | tee -a "$LOG_FILE"

# Keep only last 7 days of backups
echo "Cleaning old backups (keeping last 7 days)..." | tee -a "$LOG_FILE"
find "$BACKUP_DIR" -name "nabavkidata_*.sql.gz" -mtime +7 -delete

# Count remaining backups
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "nabavkidata_*.sql.gz" | wc -l)
echo "Total backups retained: $BACKUP_COUNT" | tee -a "$LOG_FILE"

# Calculate total backup storage
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "Total backup storage: $TOTAL_SIZE" | tee -a "$LOG_FILE"

echo "[$(date)] Database backup completed successfully: nabavkidata_${DATE}.sql.gz" | tee -a "$LOG_FILE"

# Optional: Upload to S3 for offsite backup
if [ -n "$AWS_S3_BACKUP_BUCKET" ]; then
    echo "Uploading backup to S3..." | tee -a "$LOG_FILE"
    if command -v aws &> /dev/null; then
        aws s3 cp "$BACKUP_DIR/nabavkidata_${DATE}.sql.gz" \
            "s3://$AWS_S3_BACKUP_BUCKET/backups/nabavkidata_${DATE}.sql.gz" 2>&1 | tee -a "$LOG_FILE"
        echo "S3 upload completed" | tee -a "$LOG_FILE"
    else
        echo "WARNING: AWS CLI not installed, skipping S3 upload" | tee -a "$LOG_FILE"
    fi
fi
