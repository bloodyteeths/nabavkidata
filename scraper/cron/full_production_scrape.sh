#\!/bin/bash
#
# FULL PRODUCTION SCRAPE SCRIPT
# Runs all scrapers sequentially to avoid connection/memory exhaustion
#

set -e

PROJECT_ROOT="/home/ubuntu/nabavkidata/scraper"
# No venv - using user-installed packages
SCRAPY_BIN="/usr/local/bin/scrapy"
PYTHON_BIN="/usr/bin/python3"
LOG_DIR="/var/log/nabavkidata"

export DATABASE_URL="postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@localhost:5432/nabavkidata"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date "+%Y-%m-%d %H:%M:%S")] $1" | tee -a "$LOG_DIR/full_production_scrape.log"
}

cd "$PROJECT_ROOT"

log "=========================================="
log "FULL PRODUCTION SCRAPE STARTED"
log "=========================================="

# Check if active spider is still running
while pgrep -f "scrapy crawl nabavki" > /dev/null; do
    log "E-Nabavki Active spider still running, waiting..."
    sleep 60
done

# Phase 2: Awarded tenders
log "=========================================="
log "Phase 2: E-Nabavki AWARDED tenders"
log "=========================================="
scrapy crawl nabavki -a categories=awarded >> "$LOG_DIR/nabavki_awarded_production.log" 2>&1
log "Awarded tenders scrape completed"

# Phase 3: Cancelled tenders
log "=========================================="
log "Phase 3: E-Nabavki CANCELLED tenders"
log "=========================================="
scrapy crawl nabavki -a categories=cancelled >> "$LOG_DIR/nabavki_cancelled_production.log" 2>&1
log "Cancelled tenders scrape completed"

# Phase 4: E-Pazar all categories
log "=========================================="
log "Phase 4: E-Pazar ALL categories"
log "=========================================="
scrapy crawl epazar_api -a category=all >> "$LOG_DIR/epazar_production.log" 2>&1
log "E-Pazar scrape completed"

# Phase 5: Document processing
log "=========================================="
log "Phase 5: Document Processing (PDFs)"
log "=========================================="
"$PROJECT_ROOT/cron/process_documents.sh" >> "$LOG_DIR/document_processing.log" 2>&1 || log "Document processing had issues"
log "Document processing completed"

log "=========================================="
log "FULL PRODUCTION SCRAPE COMPLETED\!"
log "=========================================="

# Show final stats
log "Final database stats:"
PGPASSWORD="9fagrPSDfQqBjrKZZLVrJY2Am" psql -h localhost -U nabavki_user -d nabavkidata -c "
SELECT 
    'E-Nabavki Tenders' as source, COUNT(*) as count FROM tenders
UNION ALL
SELECT 
    'E-Pazar Tenders', COUNT(*) FROM epazar_tenders
UNION ALL
SELECT 
    'Documents', COUNT(*) FROM documents;
" | tee -a "$LOG_DIR/full_production_scrape.log"

log "Script finished\!"
