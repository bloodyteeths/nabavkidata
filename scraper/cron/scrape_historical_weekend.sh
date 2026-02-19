#!/bin/bash
#
# WEEKEND HISTORICAL BACKFILL
#
# Runs historical backfill ONLY on weekends (Saturday/Sunday) to avoid
# blocking active tender scraping during business hours.
#
# This script is safe to add to crontab - it will skip execution on weekdays.
#
# Crontab entry (run every 2 hours on weekends):
# 0 */2 * * 6,0 /home/ubuntu/nabavkidata/scraper/cron/scrape_historical_weekend.sh >> /var/log/nabavkidata/historical_weekend.log 2>&1
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/nabavkidata"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if it's a weekend (Saturday=6, Sunday=0)
DAY_OF_WEEK=$(date +%u)
if [ "$DAY_OF_WEEK" -lt 6 ]; then
    log "Not a weekend (day=$DAY_OF_WEEK), skipping historical backfill"
    exit 0
fi

log "Weekend detected, running historical backfill batch..."

# Run one batch of historical backfill (will respect lock mechanism)
# Using --resume to continue from where we left off
"$SCRIPT_DIR/scrape_historical_backfill.sh" --resume

log "Weekend historical batch completed"
