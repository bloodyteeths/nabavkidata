#!/bin/bash
# Monitor scraper health and send alerts
# Runs every 5 minutes to check system status

set -e

LOG_DIR="/home/ubuntu/nabavkidata/scraper/logs"
ALERT_EMAIL="admin@nabavkidata.com"
HEALTH_LOG="$LOG_DIR/health_check.log"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$HEALTH_LOG"
}

# Function to send alert
send_alert() {
    local subject="$1"
    local message="$2"

    # Try to send email (requires mailutils or sendmail)
    if command -v mail &> /dev/null; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
    else
        log_message "WARNING: Cannot send email - mail command not found"
    fi

    log_message "ALERT: $subject - $message"
}

log_message "Starting health check..."

# Check 1: Last scrape timestamp
log_message "Checking last active scrape..."
LAST_SCRAPE=$(find "$LOG_DIR" -name "scrape_active_*.log" -mmin -360 2>/dev/null | wc -l)

if [ "$LAST_SCRAPE" -eq 0 ]; then
    send_alert "Scraper Alert: No Recent Scrapes" \
        "WARNING: No active scrape found in last 6 hours. Scraper may be down."
else
    log_message "OK: Recent scrape found"
fi

# Check 2: Error rate in recent logs
log_message "Checking error rate..."
RECENT_LOGS=$(find "$LOG_DIR" -name "scrape_active_*.log" -mmin -60 2>/dev/null | sort -r | head -1)

if [ -n "$RECENT_LOGS" ] && [ -f "$RECENT_LOGS" ]; then
    ERRORS=$(tail -100 "$RECENT_LOGS" 2>/dev/null | grep -i "error\|exception\|failed" | wc -l)

    if [ "$ERRORS" -gt 10 ]; then
        send_alert "Scraper Alert: High Error Rate" \
            "WARNING: $ERRORS errors found in recent logs ($RECENT_LOGS)"
    else
        log_message "OK: Error rate acceptable ($ERRORS errors)"
    fi
else
    log_message "WARNING: No recent logs found to check"
fi

# Check 3: Database connectivity
log_message "Checking database connectivity..."
source /home/ubuntu/nabavkidata/venv/bin/activate

DB_CHECK=$(python3 << 'EOF'
import asyncio
import asyncpg
import os
import sys

async def check_db():
    try:
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            print("ERROR: DATABASE_URL not set")
            return False

        conn = await asyncpg.connect(db_url, timeout=10)

        # Check tenders table
        result = await conn.fetchval('SELECT COUNT(*) FROM tenders')
        print(f"OK: Database connected, {result} tenders in database")

        await conn.close()
        return True

    except Exception as e:
        print(f"ERROR: Database connection failed: {e}")
        return False

success = asyncio.run(check_db())
sys.exit(0 if success else 1)
EOF
)

DB_EXIT=$?
log_message "$DB_CHECK"

if [ $DB_EXIT -ne 0 ]; then
    send_alert "Scraper Alert: Database Connection Failed" \
        "ERROR: Cannot connect to database. $DB_CHECK"
fi

# Check 4: Disk space
log_message "Checking disk space..."
DISK_USAGE=$(df -h /home/ubuntu | tail -1 | awk '{print $5}' | sed 's/%//')

if [ "$DISK_USAGE" -gt 90 ]; then
    send_alert "Scraper Alert: Low Disk Space" \
        "WARNING: Disk usage at ${DISK_USAGE}%. Please clean up old logs."
elif [ "$DISK_USAGE" -gt 80 ]; then
    log_message "WARNING: Disk usage at ${DISK_USAGE}%"
else
    log_message "OK: Disk usage at ${DISK_USAGE}%"
fi

# Check 5: Log directory size
log_message "Checking log directory size..."
LOG_SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
log_message "Log directory size: $LOG_SIZE"

# Check 6: Scraper process status
log_message "Checking for running scraper processes..."
SCRAPER_PROCS=$(pgrep -f "scrapy\|nabavki_spider" | wc -l)

if [ "$SCRAPER_PROCS" -gt 5 ]; then
    send_alert "Scraper Alert: Too Many Processes" \
        "WARNING: $SCRAPER_PROCS scraper processes running. Possible stuck jobs."
else
    log_message "OK: $SCRAPER_PROCS scraper processes running"
fi

log_message "Health check completed"
