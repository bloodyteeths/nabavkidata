#!/bin/bash
# Cron script for daily email campaigns
# Schedule: 0 8 * * * (8 AM UTC = 9 AM Skopje in winter)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Postmark API token
: "${POSTMARK_API_TOKEN:?POSTMARK_API_TOKEN is not set. Export it or source .env.production. No default: the old hardcoded token was revoked and callers failed with a silent HTTP 401.}"

# Activate virtual environment
source venv/bin/activate

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
