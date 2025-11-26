#!/bin/bash
# PHASE 3 DEPLOYMENT SCRIPT
# Uploads all updated files to EC2 and runs integration test

set -e  # Exit on error

EC2_HOST="ubuntu@63.180.169.49"
SSH_KEY="~/.ssh/nabavki-key.pem"
PROJECT_DIR="/home/ubuntu/nabavkidata"

echo "=========================================="
echo "PHASE 3 DEPLOYMENT"
echo "=========================================="

# Upload backend models
echo ""
echo "[1/4] Uploading backend models..."
scp -i $SSH_KEY backend/models.py $EC2_HOST:$PROJECT_DIR/backend/
echo "✓ Backend models uploaded"

# Upload scraper items
echo ""
echo "[2/4] Uploading scraper items..."
scp -i $SSH_KEY scraper/scraper/items.py $EC2_HOST:$PROJECT_DIR/scraper/scraper/
echo "✓ Scraper items uploaded"

# Upload spider
echo ""
echo "[3/4] Uploading spider..."
scp -i $SSH_KEY scraper/scraper/spiders/nabavki_spider.py $EC2_HOST:$PROJECT_DIR/scraper/scraper/spiders/
echo "✓ Spider uploaded"

# Upload pipelines
echo ""
echo "[4/4] Uploading pipelines..."
scp -i $SSH_KEY scraper/scraper/pipelines.py $EC2_HOST:$PROJECT_DIR/scraper/scraper/
echo "✓ Pipelines uploaded"

echo ""
echo "=========================================="
echo "✓ ALL FILES UPLOADED SUCCESSFULLY"
echo "=========================================="

# Run integration test
echo ""
echo "Running integration test (3 tenders)..."
echo "=========================================="

ssh -i $SSH_KEY $EC2_HOST "cd $PROJECT_DIR/scraper && source ../venv/bin/activate && export DATABASE_URL='postgresql+asyncpg://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata' && scrapy crawl nabavki -s CLOSESPIDER_ITEMCOUNT=3 -s LOG_LEVEL=INFO 2>&1 | tail -100"

echo ""
echo "=========================================="
echo "✓ PHASE 3 DEPLOYMENT COMPLETE"
echo "=========================================="
