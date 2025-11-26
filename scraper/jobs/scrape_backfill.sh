#!/bin/bash
# Weekly historical backfill for trend data
# Runs every Sunday at 2 AM UTC

set -e

# Load environment
source /home/ubuntu/nabavkidata/venv/bin/activate
cd /home/ubuntu/nabavkidata/scraper

# Set logging
DATE=$(date +%Y%m%d)
LOG_FILE="logs/scrape_backfill_${DATE}.log"

# Calculate date range (last 7 days)
START_DATE=$(date -d '7 days ago' +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)
END_DATE=$(date +%Y-%m-%d)

echo "[$(date)] Starting historical backfill ($START_DATE to $END_DATE)..." | tee -a "$LOG_FILE"

# Run scraper for historical data
python3 << EOF | tee -a "$LOG_FILE"
import sys
import os
from datetime import datetime, timedelta
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Add project to path
sys.path.insert(0, '/home/ubuntu/nabavkidata/scraper')

from scraper.spiders.nabavki_spider import NabavkiSpider

# Configure settings
settings = get_project_settings()
settings.update({
    'LOG_FILE': '$LOG_FILE',
    'LOG_LEVEL': 'INFO',
    'ROBOTSTXT_OBEY': True,
    'CONCURRENT_REQUESTS': 16,
    'DOWNLOAD_DELAY': 0.5,
    'CLOSESPIDER_TIMEOUT': 7200,  # 2 hour timeout
    'CLOSESPIDER_ITEMCOUNT': 10000,  # Max 10k items per run
})

# Create and run crawler for date range
process = CrawlerProcess(settings)
process.crawl(
    NabavkiSpider,
    start_date='$START_DATE',
    end_date='$END_DATE'
)
process.start()

print(f"[{os.popen('date').read().strip()}] Historical backfill completed")
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date)] Historical backfill completed successfully" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ERROR: Historical backfill failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
