#!/bin/bash
# Cron script for daily email campaigns
# Schedule: 0 8 * * * (8 AM UTC = 9 AM Skopje in winter)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Postmark API token
export POSTMARK_API_TOKEN="33d10a6c-0906-42c6-ab14-441ad12b9e2a"

# Activate virtual environment
# venv removed - using system python

# Send all leads (10k/month limit)
SEGMENT_A_LIMIT=2500
SEGMENT_B_LIMIT=3500
SEGMENT_C_LIMIT=5000

LOG_FILE="/var/log/nabavkidata/email_campaign_$(date +%Y%m%d).log"
mkdir -p /var/log/nabavkidata

echo "========================================" >> "$LOG_FILE"
echo "Email Campaign - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Segment A - Active tender participants
echo "Running Segment A campaign..." >> "$LOG_FILE"
python3 scripts/email_campaigns.py --segment A --send --limit $SEGMENT_A_LIMIT >> "$LOG_FILE" 2>&1

# Segment B - IT Decision makers
echo "Running Segment B campaign..." >> "$LOG_FILE"
python3 scripts/email_campaigns.py --segment B --send --limit $SEGMENT_B_LIMIT >> "$LOG_FILE" 2>&1

# Segment C - General companies
echo "Running Segment C campaign..." >> "$LOG_FILE"
python3 scripts/email_campaigns.py --segment C --send --limit $SEGMENT_C_LIMIT >> "$LOG_FILE" 2>&1

echo "Campaign complete at $(date)" >> "$LOG_FILE"
