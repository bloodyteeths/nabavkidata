#!/bin/bash
cd /home/ubuntu/nabavkidata/backend
# venv removed - using system python
export $(grep -v '^#' .env | xargs)

# Log file with timestamp
LOGFILE="/home/ubuntu/nabavkidata/logs/followup_$(date +%Y%m%d_%H%M%S).log"
mkdir -p /home/ubuntu/nabavkidata/logs

echo "Starting personalized follow-up campaign at $(date)" >> $LOGFILE
python3 scripts/send_followup_personalized.py --live --delay 5 --limit 700 >> $LOGFILE 2>&1
echo "Campaign completed at $(date)" >> $LOGFILE
