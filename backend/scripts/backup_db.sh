#!/bin/bash
set -e

DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_DIR="/backups"
BACKUP_FILE="nabavkidata_${DATE}.sql"

echo "📦 Creating database backup: $BACKUP_FILE"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
docker-compose exec -T db pg_dump -U $DB_USER nabavkidata > $BACKUP_DIR/$BACKUP_FILE

# Compress
gzip $BACKUP_DIR/$BACKUP_FILE

# Keep only last 30 days of backups
find $BACKUP_DIR -name "nabavkidata_*.sql.gz" -mtime +30 -delete

echo "✅ Backup complete: ${BACKUP_FILE}.gz"
echo "📊 Backup size: $(du -h $BACKUP_DIR/${BACKUP_FILE}.gz | cut -f1)"
