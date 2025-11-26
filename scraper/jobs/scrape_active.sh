#!/bin/bash
# Scrape active/open tenders
# Runs 4 times daily to capture new postings and deadline changes

set -e

# Load environment
source /home/ubuntu/nabavkidata/venv/bin/activate
cd /home/ubuntu/nabavkidata/scraper

# Set logging
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/scrape_active_${TIMESTAMP}.log"

echo "[$(date)] Starting active tenders scrape..." | tee -a "$LOG_FILE"

# Run scraper for active/open tenders
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
    'RETRY_ENABLED': True,
    'RETRY_TIMES': 3,
})

# Create and run crawler
process = CrawlerProcess(settings)
process.crawl(NabavkiSpider, status_filter='open')
process.start()

print(f"[{os.popen('date').read().strip()}] Active tenders scrape completed")
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date)] Active tenders scrape completed successfully" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ERROR: Active tenders scrape failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
