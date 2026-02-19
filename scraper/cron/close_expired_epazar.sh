#!/bin/bash
# Close expired e-pazar tenders - runs daily at 01:00
# Updates epazar_tenders with status='active' where closing_date has passed

set -e

# Load environment
source /home/ubuntu/.bashrc

LOG_FILE="/var/log/nabavkidata/close_expired_epazar.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting close_expired_epazar job" >> "$LOG_FILE"

# Database connection
DB_HOST="nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com"
DB_NAME="nabavkidata"
DB_USER="nabavki_user"

# Run the update query
RESULT=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
UPDATE epazar_tenders
SET status = 'closed',
    updated_at = NOW()
WHERE status = 'active'
  AND closing_date IS NOT NULL
  AND closing_date < CURRENT_DATE
RETURNING id;
")

# Count updated rows
COUNT=$(echo "$RESULT" | grep -c '[0-9]' || echo "0")

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] Closed $COUNT expired e-pazar tenders" >> "$LOG_FILE"

# Log some of the updated IDs (first 10)
if [ "$COUNT" -gt 0 ]; then
    echo "[$TIMESTAMP] Sample updated e-pazar tender IDs:" >> "$LOG_FILE"
    echo "$RESULT" | head -10 >> "$LOG_FILE"
fi

# Get current status distribution
STATS=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT status, COUNT(*) as count
FROM epazar_tenders
GROUP BY status
ORDER BY count DESC;
")

echo "[$TIMESTAMP] Current e-pazar tender status distribution:" >> "$LOG_FILE"
echo "$STATS" >> "$LOG_FILE"

echo "[$TIMESTAMP] Job completed successfully" >> "$LOG_FILE"
