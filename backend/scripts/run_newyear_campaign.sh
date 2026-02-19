#!/bin/bash
# New Year 2026 Follow-up Campaign
# Scheduled: Feb 17, 2026 at 07:00 UTC (08:00 Macedonia time)
# Sends follow-up to ~7,000 contacts from Dec 2025 campaigns

cd /home/ubuntu/nabavkidata/backend
export $(grep -v '^#' .env | xargs)

# Log file with timestamp
LOGFILE="/home/ubuntu/nabavkidata/logs/newyear_$(date +%Y%m%d_%H%M%S).log"
mkdir -p /home/ubuntu/nabavkidata/logs

echo "Starting new year follow-up campaign at $(date)" >> $LOGFILE
python3 scripts/send_followup_newyear.py --live >> $LOGFILE 2>&1
echo "Campaign completed at $(date)" >> $LOGFILE
