#!/bin/bash
# Daily PostgreSQL backup for nabavkidata (Hetzner local DB)
# Runs as cron: 0 3 * * * /home/ubuntu/nabavkidata/scripts/backup_db.sh >> /var/log/nabavkidata/backup.log 2>&1
set -euo pipefail

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/home/ubuntu/backups/daily"
BACKUP_FILE="nabavkidata_${DATE}.dump"
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# pg_dump as postgres user, pipe to file owned by ubuntu
sudo -u postgres pg_dump -d nabavkidata \
    --format=custom \
    --compress=6 \
    --no-owner \
    > "$BACKUP_DIR/$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup complete: $BACKUP_FILE ($SIZE)"

# Remove backups older than KEEP_DAYS
DELETED=$(find "$BACKUP_DIR" -name "nabavkidata_*.dump" -mtime +$KEEP_DAYS -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date)] Cleaned up $DELETED old backups"
fi

# Show remaining backups
echo "[$(date)] Current backups:"
ls -lh "$BACKUP_DIR"/nabavkidata_*.dump 2>/dev/null || echo "  (none)"
