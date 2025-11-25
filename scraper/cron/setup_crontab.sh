#!/bin/bash
#
# SETUP SCRIPT: Install Crontab Entries
#
# Run this script once to set up the automated scraping schedule
#
# Usage: ./setup_crontab.sh
#

set -e

CRON_DIR="/home/ubuntu/nabavkidata/scraper/cron"
LOG_DIR="/var/log/nabavkidata"

echo "Setting up nabavkidata cron jobs..."

# Create log directory
sudo mkdir -p "$LOG_DIR"
sudo chown ubuntu:ubuntu "$LOG_DIR"

# Make scripts executable
chmod +x "$CRON_DIR"/*.sh

# Create crontab entries
# Using a heredoc to define all cron entries
CRON_ENTRIES="
# ============================================
# NABAVKIDATA SCRAPER AUTOMATION
# ============================================

# Active tenders - scrape every hour (24/7)
0 * * * * $CRON_DIR/scrape_active.sh >> $LOG_DIR/active_\$(date +\\%Y\\%m\\%d).log 2>&1

# Log cleanup - monthly on the 1st at 4 AM
0 4 1 * * $CRON_DIR/cleanup_logs.sh >> $LOG_DIR/cleanup.log 2>&1

# ============================================
# NOTE: Awarded/Cancelled/Historical categories
# are not available on the public portal.
# These jobs are disabled until routes are found.
# ============================================
# Awarded tenders daily at 2 AM (DISABLED)
# 0 2 * * * $CRON_DIR/scrape_awarded.sh
# Cancelled tenders daily at 3 AM (DISABLED)
# 0 3 * * * $CRON_DIR/scrape_cancelled.sh
# Historical backfill weekly Sunday 3 AM (DISABLED)
# 0 3 * * 0 $CRON_DIR/scrape_historical.sh
"

# Get existing crontab (if any)
EXISTING_CRONTAB=$(crontab -l 2>/dev/null || echo "")

# Check if nabavkidata entries already exist
if echo "$EXISTING_CRONTAB" | grep -q "NABAVKIDATA SCRAPER"; then
    echo "Nabavkidata cron entries already exist. To update, first run:"
    echo "  crontab -l | grep -v 'nabavkidata' | crontab -"
    echo "Then run this script again."
    exit 0
fi

# Append new entries to existing crontab
(echo "$EXISTING_CRONTAB"; echo "$CRON_ENTRIES") | crontab -

echo "Cron jobs installed successfully!"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "Log files will be written to: $LOG_DIR"
