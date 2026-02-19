#!/bin/bash
# Friday Dec 19, 2025 - 7 AM Email Campaign
# Sends Hormozi-style story email to ~7,268 contacts

cd /Users/tamsar/Downloads/nabavkidata/backend
LOG_FILE="/Users/tamsar/Downloads/nabavkidata/backend/scripts/campaign_$(date +%Y%m%d_%H%M%S).log"

echo "Starting campaign at $(date)" | tee -a "$LOG_FILE"
python3 scripts/send_followup_friday.py 2>&1 | tee -a "$LOG_FILE"
echo "Campaign finished at $(date)" | tee -a "$LOG_FILE"
