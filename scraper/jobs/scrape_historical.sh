#!/bin/bash
# Scrape historical/realized contracts using authenticated spider
# Requires login credentials to access archive data

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_ROOT}/logs"
HEALTH_DIR="${PROJECT_ROOT}/health"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/historical_${TIMESTAMP}.log"
HEALTH_FILE="${HEALTH_DIR}/historical_health.json"

# Ensure directories exist
mkdir -p "$LOG_DIR" "$HEALTH_DIR"

# Activate virtual environment
cd "$PROJECT_ROOT"
if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "$(date): Starting historical tenders scrape (authenticated)" | tee -a "$LOG_FILE"

# Run authenticated spider for historical tenders
cd "$PROJECT_ROOT/scraper"
scrapy crawl nabavki_auth -a category=historical -L INFO 2>&1 | tee -a "$LOG_FILE"

SCRAPE_STATUS=$?

# Generate health JSON
END_TIME=$(date -Iseconds)
TENDERS_SCRAPED=$(grep -c "Successfully extracted" "$LOG_FILE" 2>/dev/null || echo "0")
ERRORS=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")

cat > "$HEALTH_FILE" << EOF
{
    "job": "scrape_historical",
    "category": "historical",
    "authenticated": true,
    "status": $([ $SCRAPE_STATUS -eq 0 ] && echo '"success"' || echo '"failed"'),
    "exit_code": $SCRAPE_STATUS,
    "timestamp": "$END_TIME",
    "tenders_scraped": $TENDERS_SCRAPED,
    "errors_count": $ERRORS,
    "log_file": "$LOG_FILE"
}
EOF

echo "$(date): Historical tenders scrape complete. Status: $SCRAPE_STATUS" | tee -a "$LOG_FILE"
echo "Health file: $HEALTH_FILE"

exit $SCRAPE_STATUS
