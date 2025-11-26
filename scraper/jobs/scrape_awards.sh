#!/bin/bash
# Scrape awarded tenders for competitor intelligence
# Runs daily at 6 AM UTC

set -e

# Load environment
source /home/ubuntu/nabavkidata/venv/bin/activate
cd /home/ubuntu/nabavkidata/scraper

# Set logging
DATE=$(date +%Y%m%d)
LOG_FILE="logs/scrape_awards_${DATE}.log"

echo "[$(date)] Starting awards scrape..." | tee -a "$LOG_FILE"

# Run scraper for awarded tenders
python3 << EOF | tee -a "$LOG_FILE"
import sys
import os
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
})

# Create and run crawler for awarded tenders
process = CrawlerProcess(settings)
process.crawl(NabavkiSpider, status_filter='awarded')
process.start()

print(f"[{os.popen('date').read().strip()}] Awards scrape completed")
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date)] Awards scrape completed successfully" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ERROR: Awards scrape failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
