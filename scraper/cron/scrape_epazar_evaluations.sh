#!/bin/bash
# Scrape e-pazar evaluation reports from finished tenders
# Runs daily at 18:00 to capture newly closed tenders
# Cron: 0 18 * * * /home/ubuntu/nabavkidata/scraper/cron/scrape_epazar_evaluations.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/nabavkidata"
LOG_FILE="$LOG_DIR/epazar_evaluation_$(date +%Y%m%d).log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

echo "========================================" >> "$LOG_FILE"
echo "E-Pazar Evaluation Scrape: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# Run evaluation extractor
# --discover: Find evaluation report URLs from finished tenders
# --limit 50: Process up to 50 tenders per run
python3 epazar_evaluation_extractor.py --discover --limit 50 >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Evaluation scrape completed successfully" >> "$LOG_FILE"
else
    echo "Evaluation scrape failed with exit code: $EXIT_CODE" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
echo "Finished at: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Cleanup old logs (keep 30 days)
find "$LOG_DIR" -name "epazar_evaluation_*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
