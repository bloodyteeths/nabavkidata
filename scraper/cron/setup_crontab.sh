#!/bin/bash
#
# SETUP SCRIPT: Install Crontab Entries
#
# Run this script once to set up the automated scraping schedule.
# Schedule is designed so no two Playwright scrapers overlap (3.8GB RAM server).
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
CRON_ENTRIES="
# ============================================
# NABAVKIDATA CRON JOBS
# ============================================
# RULE: Only 1 Playwright scraper at a time (3.8GB RAM)
# All scraper scripts use scraper_lock.sh + CLOSESPIDER_TIMEOUT
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/ubuntu/.local/bin

# ============================================================================
# SYSTEM MONITORING
# ============================================================================

# Memory watchdog + staleness detection - every 5 min
*/5 * * * * $CRON_DIR/memory_watchdog.sh >> $LOG_DIR/watchdog.log 2>&1

# ============================================================================
# SCRAPERS (Playwright - max 1 at a time, staggered schedule)
# ============================================================================

# Active tenders - every 4 hours
0 0,4,8,12,16,20 * * * /opt/clawd/run-cron.sh scrape-active $CRON_DIR/scrape_active.sh >> $LOG_DIR/active_scrape.log 2>&1

# Awarded contracts - daily at 2 AM (safe gap: active 00:00 done ~02:00, next at 04:00)
0 2 * * * /opt/clawd/run-cron.sh scrape-awarded $CRON_DIR/scrape_awarded.sh >> $LOG_DIR/awarded_scrape.log 2>&1

# Contracts/Winners - daily at 6 AM (safe gap: active 04:00 done ~06:00, next at 08:00)
0 6 * * * /opt/clawd/run-cron.sh scrape-contracts $CRON_DIR/scrape_contracts.sh >> $LOG_DIR/contracts_scrape.log 2>&1

# Cancelled tenders - daily at 10 AM (safe gap: active 08:00 done ~10:00, next at 12:00)
0 10 * * * /opt/clawd/run-cron.sh scrape-cancelled $CRON_DIR/scrape_cancelled.sh >> $LOG_DIR/cancelled_scrape.log 2>&1

# E-Pazar products - daily at 6 AM (API-based, no Playwright conflict)
0 6 * * * /opt/clawd/run-cron.sh scrape-epazar $CRON_DIR/scrape_epazar.sh >> $LOG_DIR/epazar_scrape.log 2>&1

# E-Pazar evaluation reports - daily at 6 PM
0 18 * * * /opt/clawd/run-cron.sh scrape-epazar-evals $CRON_DIR/scrape_epazar_evaluations.sh >> $LOG_DIR/epazar_evaluation.log 2>&1

# ============================================================================
# DOCUMENT PROCESSING & EMBEDDINGS (no Playwright, own locks)
# ============================================================================

# Document text extraction - every hour at :30
30 * * * * /opt/clawd/run-cron.sh doc-extract $CRON_DIR/process_documents.sh >> $LOG_DIR/doc_extract.log 2>&1

# Auto-generate embeddings - every 4 hours (offset from scrapers to avoid DB connection exhaustion)
0 1,5,9,13,17,21 * * * /opt/clawd/run-cron.sh auto-embeddings $CRON_DIR/auto_embeddings.sh >> $LOG_DIR/embeddings.log 2>&1

# ============================================================================
# ML & ANALYSIS
# ============================================================================

# Corruption analysis - daily at 3 AM
0 3 * * * /opt/clawd/run-cron.sh analyze-corruption $CRON_DIR/analyze_corruption.sh >> $LOG_DIR/corruption_cron.log 2>&1

# Refresh materialized views - daily at 5 AM
0 5 * * * /opt/clawd/run-cron.sh refresh-views $CRON_DIR/refresh_corruption_views.sh >> $LOG_DIR/views_refresh.log 2>&1

# ============================================================================
# EMAIL & ALERTS
# ============================================================================

# Daily digest at 8 AM UTC
0 8 * * * /opt/clawd/run-cron.sh email-digest-daily \"cd /home/ubuntu/nabavkidata/backend && python3 crons/email_digest.py daily\" >> $LOG_DIR/daily_digest.log 2>&1

# Weekly digest on Monday at 8 AM UTC
0 8 * * 1 /opt/clawd/run-cron.sh email-digest-weekly \"cd /home/ubuntu/nabavkidata/backend && python3 crons/email_digest.py weekly\" >> $LOG_DIR/weekly_digest.log 2>&1

# Instant alerts every 15 min
*/15 * * * * /opt/clawd/run-cron.sh instant-alerts \"cd /home/ubuntu/nabavkidata/backend && python3 crons/instant_alerts.py\" >> $LOG_DIR/instant_alerts.log 2>&1

# User interest vectors - daily at 2 AM
0 2 * * * /opt/clawd/run-cron.sh user-interest-update \"cd /home/ubuntu/nabavkidata/backend && python3 crons/user_interest_update.py\" >> $LOG_DIR/interest_update.log 2>&1

# Welcome series - hourly
0 * * * * /opt/clawd/run-cron.sh welcome-series $CRON_DIR/../backend/scripts/run_welcome_series.sh >> $LOG_DIR/welcome_series.log 2>&1

# Cold outreach drip - every 30 min
*/30 * * * * /opt/clawd/run-cron.sh cold-outreach \"cd /home/ubuntu/nabavkidata/backend && python3 crons/cold_outreach_drip.py --limit 250\" >> $LOG_DIR/cold_outreach.log 2>&1

# ============================================================================
# MAINTENANCE
# ============================================================================

# Close expired tenders - daily at midnight
0 0 * * * /opt/clawd/run-cron.sh close-expired-tenders \"cd /home/ubuntu/nabavkidata && python3 backend/crons/close_expired_tenders.py\" >> $LOG_DIR/close_expired.log 2>&1

# Close expired e-pazar - daily at 6:30 AM
30 6 * * * /opt/clawd/run-cron.sh close-expired-epazar \"cd /home/ubuntu/nabavkidata && python3 backend/crons/close_expired_epazar_tenders.py\" >> $LOG_DIR/close_expired_epazar.log 2>&1

# Log cleanup - daily at 4 AM
0 4 * * * /opt/clawd/run-cron.sh cleanup-logs $CRON_DIR/cleanup_logs.sh >> $LOG_DIR/cleanup.log 2>&1

# ============================================================================
# BILLING
# ============================================================================

# Reset daily usage counters at 00:05
5 0 * * * /opt/clawd/run-cron.sh billing-reset-daily \"cd /home/ubuntu/nabavkidata && python3 backend/crons/billing_crons.py reset_daily\" >> $LOG_DIR/billing_daily_reset.log 2>&1

# Reset monthly usage counters on 1st of month
5 0 1 * * /opt/clawd/run-cron.sh billing-reset-monthly \"cd /home/ubuntu/nabavkidata && python3 backend/crons/billing_crons.py reset_monthly\" >> $LOG_DIR/billing_monthly_reset.log 2>&1

# Expire trials - hourly at :30
30 * * * * /opt/clawd/run-cron.sh billing-expire-trials \"cd /home/ubuntu/nabavkidata && python3 backend/crons/billing_crons.py expire_trials\" >> $LOG_DIR/billing_expire_trials.log 2>&1

# Cleanup old webhook events - Sunday 3 AM
0 3 * * 0 /opt/clawd/run-cron.sh billing-cleanup-webhooks \"cd /home/ubuntu/nabavkidata && python3 backend/crons/billing_crons.py cleanup_webhooks\" >> $LOG_DIR/billing_cleanup.log 2>&1

# ============================================================================
# SYSTEM (not Clawd-wrapped)
# ============================================================================

# Clean old downloaded files - hourly
0 * * * * find /home/ubuntu/nabavkidata/scraper/downloads/files -name \"*.pdf\" -mmin +120 -delete 2>/dev/null
0 * * * * find /home/ubuntu/nabavkidata/scraper/downloads/files -name \"*.docx\" -mmin +120 -delete 2>/dev/null
0 * * * * find /home/ubuntu/nabavkidata/scraper/downloads/files -name \"*.xls*\" -mmin +120 -delete 2>/dev/null
"

# Get existing crontab (if any)
EXISTING_CRONTAB=$(crontab -l 2>/dev/null || echo "")

# Check if nabavkidata entries already exist
if echo "$EXISTING_CRONTAB" | grep -q "NABAVKIDATA"; then
    echo "Nabavkidata cron entries already exist. To update, first run:"
    echo "  crontab -l | grep -v 'nabavkidata\|NABAVKIDATA\|scrape_\|memory_watchdog\|process_documents\|auto_embeddings\|close_expired\|billing_\|email_digest\|instant_alerts\|cold_outreach\|welcome_series\|user_interest\|cleanup_logs\|analyze_corruption\|refresh_corruption\|epazar' | crontab -"
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
