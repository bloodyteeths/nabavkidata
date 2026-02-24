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

# Env vars loaded by run-cron.sh from backend/.env
# Fallback: try loading from root .env if vars not set
if [ -z "$GEMINI_API_KEY" ] && [ -f "$NABAVKI_DIR/backend/.env" ]; then
    set -a
    source "$NABAVKI_DIR/backend/.env"
    set +a
fi
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
/usr/bin/python3 embeddings/pipeline.py --batch-size=20 --max-documents=500

echo "$(date): Auto-embeddings pipeline completed"
