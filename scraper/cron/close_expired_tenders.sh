#!/bin/bash
# Close expired tenders - runs daily at 00:00
# Updates tenders with status='open' where closing_date has passed

set -e

# Load environment
source /home/ubuntu/.bashrc

LOG_FILE="/var/log/nabavkidata/close_expired_tenders.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting close_expired_tenders job" >> "$LOG_FILE"

# Database connection
DB_HOST="nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com"
DB_NAME="nabavkidata"
DB_USER="nabavki_user"

# Run the update query
RESULT=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
UPDATE tenders
SET status = 'closed',
    updated_at = NOW()
WHERE status = 'open'
  AND closing_date IS NOT NULL
  AND closing_date < CURRENT_DATE
RETURNING tender_id;
")

# Count updated rows
COUNT=$(echo "$RESULT" | grep -c '[0-9]' || echo "0")

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] Closed $COUNT expired tenders" >> "$LOG_FILE"

# Log some of the updated tender IDs (first 10)
if [ "$COUNT" -gt 0 ]; then
    echo "[$TIMESTAMP] Sample updated tender IDs:" >> "$LOG_FILE"
    echo "$RESULT" | head -10 >> "$LOG_FILE"
fi

echo "[$TIMESTAMP] Job completed successfully" >> "$LOG_FILE"
