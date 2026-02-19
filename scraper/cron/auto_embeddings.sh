#!/bin/bash
# Auto-Embeddings Cron Job
# PHASE 3: Runs every 4 hours to generate embeddings for new documents
#
# Add to crontab with: crontab -e
# 0 */4 * * * /home/ubuntu/nabavkidata/scraper/cron/auto_embeddings.sh >> /var/log/embeddings.log 2>&1

set -e

# Configuration
NABAVKI_DIR="/home/ubuntu/nabavkidata"
AI_DIR="$NABAVKI_DIR/ai"
LOG_FILE="/var/log/embeddings.log"

# Load environment variables
source "$NABAVKI_DIR/.env"
export GEMINI_API_KEY DATABASE_URL

# Check required variables
if [ -z "$GEMINI_API_KEY" ]; then
    echo "$(date): ERROR - GEMINI_API_KEY not set"
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "$(date): ERROR - DATABASE_URL not set"
    exit 1
fi

echo "$(date): Starting auto-embeddings pipeline..."

cd "$AI_DIR"

# Run embeddings pipeline (batch of 20, max 500 docs per run)
"$VENV_PATH/bin/python" embeddings/pipeline.py --batch-size=20 --max-documents=500

echo "$(date): Auto-embeddings pipeline completed"
