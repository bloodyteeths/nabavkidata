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

# Contracts/Winners - scrape daily at 5 AM (uses Playwright)
0 5 * * * $CRON_DIR/scrape_contracts.sh >> $LOG_DIR/contracts_\$(date +\\%Y\\%m\\%d).log 2>&1

# E-Pazar products - scrape daily at 6 AM
0 6 * * * $CRON_DIR/scrape_epazar.sh >> $LOG_DIR/epazar_\$(date +\\%Y\\%m\\%d).log 2>&1

# Document processing - run every 4 hours to extract PDFs
0 */4 * * * $CRON_DIR/process_documents.sh >> $LOG_DIR/docs_\$(date +\\%Y\\%m\\%d).log 2>&1

# Log cleanup - monthly on the 1st at 4 AM
0 4 1 * * $CRON_DIR/cleanup_logs.sh >> $LOG_DIR/cleanup.log 2>&1
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
