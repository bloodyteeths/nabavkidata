#!/bin/bash
#
# PARALLEL SCRAPER - Maximum Speed on M1 MacBook Pro (32GB)
#
# This script runs 4 parallel workers to scrape all years (2019-2025)
# Expected completion: 24-48 hours for ~130,000 tenders
#
# Usage:
#   chmod +x run_parallel_scrape.sh
#   ./run_parallel_scrape.sh
#
# Monitor:
#   tail -f logs/*.log | grep -E "(Successfully|ERROR)"
#

set -e

# Configuration
export DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set in environment}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment - use scraper's own venv
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "../backend/venv/bin/activate" ]; then
    source ../backend/venv/bin/activate
else
    echo "ERROR: Virtual environment not found"
    exit 1
fi

# Export the venv path for subshells
export SCRAPY_VENV="$SCRIPT_DIR/venv"

# Create logs directory
mkdir -p logs

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║     PARALLEL TENDER SCRAPER - M1 MacBook Pro Optimized       ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  Workers: 4 parallel processes                                ║"
echo "║  Years: 2019-2025 (default + archive)                        ║"
echo "║  Expected: ~130,000 tenders in 24-48 hours                   ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Started: $(date)"
echo ""

# Worker 1: 2025 (default view) + 2021 (archive)
echo "[Worker 1] Starting: 2025, 2021"
(
    source "$SCRAPY_VENV/bin/activate"
    echo "[Worker 1] Scraping 2025..."
    scrapy crawl nabavki -a category=awarded -a year_filter=2025 \
        -a max_listing_pages=3000 -a force_full_scan=true \
        -s CONCURRENT_REQUESTS=4 -s DOWNLOAD_DELAY=0.15 \
        -s MEMUSAGE_LIMIT_MB=6000 \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE=logs/worker1_2025_$(date +%Y%m%d_%H%M).log 2>&1

    echo "[Worker 1] Scraping 2021 (archive)..."
    scrapy crawl nabavki -a category=awarded -a year=2021 \
        -a max_listing_pages=3000 -a force_full_scan=true \
        -s CONCURRENT_REQUESTS=2 -s DOWNLOAD_DELAY=0.3 \
        -s MEMUSAGE_LIMIT_MB=6000 \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE=logs/worker1_2021_$(date +%Y%m%d_%H%M).log 2>&1

    echo "[Worker 1] Complete!"
) &
WORKER1_PID=$!

# Worker 2: 2024 (default view) + 2020 (archive)
echo "[Worker 2] Starting: 2024, 2020"
(
    source "$SCRAPY_VENV/bin/activate"
    sleep 5  # Stagger start to avoid initial collision
    echo "[Worker 2] Scraping 2024..."
    scrapy crawl nabavki -a category=awarded -a year_filter=2024 \
        -a max_listing_pages=3000 -a force_full_scan=true \
        -s CONCURRENT_REQUESTS=4 -s DOWNLOAD_DELAY=0.15 \
        -s MEMUSAGE_LIMIT_MB=6000 \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE=logs/worker2_2024_$(date +%Y%m%d_%H%M).log 2>&1

    echo "[Worker 2] Scraping 2020 (archive)..."
    scrapy crawl nabavki -a category=awarded -a year=2020 \
        -a max_listing_pages=3000 -a force_full_scan=true \
        -s CONCURRENT_REQUESTS=2 -s DOWNLOAD_DELAY=0.3 \
        -s MEMUSAGE_LIMIT_MB=6000 \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE=logs/worker2_2020_$(date +%Y%m%d_%H%M).log 2>&1

    echo "[Worker 2] Complete!"
) &
WORKER2_PID=$!

# Worker 3: 2023 (default view) + 2019 (archive)
echo "[Worker 3] Starting: 2023, 2019"
(
    source "$SCRAPY_VENV/bin/activate"
    sleep 10  # Stagger start
    echo "[Worker 3] Scraping 2023..."
    scrapy crawl nabavki -a category=awarded -a year_filter=2023 \
        -a max_listing_pages=3000 -a force_full_scan=true \
        -s CONCURRENT_REQUESTS=4 -s DOWNLOAD_DELAY=0.15 \
        -s MEMUSAGE_LIMIT_MB=6000 \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE=logs/worker3_2023_$(date +%Y%m%d_%H%M).log 2>&1

    echo "[Worker 3] Scraping 2019 (archive)..."
    scrapy crawl nabavki -a category=awarded -a year=2019 \
        -a max_listing_pages=3000 -a force_full_scan=true \
        -s CONCURRENT_REQUESTS=2 -s DOWNLOAD_DELAY=0.3 \
        -s MEMUSAGE_LIMIT_MB=6000 \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE=logs/worker3_2019_$(date +%Y%m%d_%H%M).log 2>&1

    echo "[Worker 3] Complete!"
) &
WORKER3_PID=$!

# Worker 4: 2022 (default view only)
echo "[Worker 4] Starting: 2022"
(
    source "$SCRAPY_VENV/bin/activate"
    sleep 15  # Stagger start
    echo "[Worker 4] Scraping 2022..."
    scrapy crawl nabavki -a category=awarded -a year_filter=2022 \
        -a max_listing_pages=3000 -a force_full_scan=true \
        -s CONCURRENT_REQUESTS=4 -s DOWNLOAD_DELAY=0.15 \
        -s MEMUSAGE_LIMIT_MB=6000 \
        -s LOG_LEVEL=INFO \
        -s LOG_FILE=logs/worker4_2022_$(date +%Y%m%d_%H%M).log 2>&1

    echo "[Worker 4] Complete!"
) &
WORKER4_PID=$!

echo ""
echo "Workers started:"
echo "  Worker 1 (2025, 2021): PID $WORKER1_PID"
echo "  Worker 2 (2024, 2020): PID $WORKER2_PID"
echo "  Worker 3 (2023, 2019): PID $WORKER3_PID"
echo "  Worker 4 (2022):       PID $WORKER4_PID"
echo ""
echo "Monitor progress:"
echo "  tail -f logs/*.log | grep -E '(Successfully|ERROR|Progress)'"
echo ""
echo "Check database counts:"
echo "  PGPASSWORD='xxx' psql -h nabavkidata-db... -c 'SELECT EXTRACT(YEAR FROM publication_date), COUNT(*) FROM tenders GROUP BY 1 ORDER BY 1 DESC;'"
echo ""

# Wait for all workers to complete
wait $WORKER1_PID $WORKER2_PID $WORKER3_PID $WORKER4_PID

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    ALL WORKERS COMPLETE                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo "Finished: $(date)"
echo ""

# Final count
echo "Final database counts:"
PGPASSWORD="$DB_PASS" psql \
    -h localhost \
    -U nabavki_user -d nabavkidata -c "
SELECT EXTRACT(YEAR FROM publication_date) as year, COUNT(*) as count
FROM tenders WHERE publication_date IS NOT NULL
GROUP BY year ORDER BY year DESC;"
