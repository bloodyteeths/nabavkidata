#!/bin/bash
#
# CRON SCRIPT: Process Tender Documents (PDF Extraction)
#
# This script processes pending documents from the database:
# 1. Downloads PDFs from e-nabavki.gov.mk
# 2. Extracts text and product data using financial_bid_extractor
# 3. Populates product_items table with extracted products
#
# Recommended crontab entry (every 2 hours):
# 0 */2 * * * /home/ubuntu/nabavkidata/scraper/cron/process_documents.sh >> /var/log/nabavkidata/documents_$(date +\%Y\%m\%d).log 2>&1
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="/home/ubuntu/nabavkidata/venv"
LOG_DIR="/var/log/nabavkidata"
FILES_STORE="/home/ubuntu/nabavkidata/scraper/downloads/files"

# Database URL
export DATABASE_URL="postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata"
export FILES_STORE="$FILES_STORE"

# Ensure directories exist
mkdir -p "$LOG_DIR"
mkdir -p "$FILES_STORE"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting document processing..."
log "FILES_STORE: $FILES_STORE"

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Process documents in batches
# Start with bid documents (most valuable) then others
BATCH_SIZE=50

log "========================================"
log "Phase 1: Processing Bid Documents"
log "========================================"

python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from process_documents import DocumentProcessor
from pathlib import Path
import os

async def process_bid_docs():
    processor = DocumentProcessor(
        database_url=os.environ['DATABASE_URL'],
        files_store=Path(os.environ['FILES_STORE'])
    )
    await processor.connect()

    # Get bid documents first (most valuable)
    rows = await processor.conn.fetch('''
        SELECT doc_id, tender_id, file_url, file_name, file_path, extraction_status
        FROM documents
        WHERE file_url LIKE '%DownloadBidFile%'
          AND (extraction_status = 'pending' OR extraction_status IS NULL)
        ORDER BY doc_id
        LIMIT \$1
    ''', $BATCH_SIZE)

    print(f'Found {len(rows)} pending bid documents')

    success = 0
    failed = 0
    for doc in rows:
        doc_dict = dict(doc)
        if await processor.process_document(doc_dict):
            success += 1
        else:
            failed += 1

    print(f'Bid documents: {success} success, {failed} failed')
    await processor.close()
    return success, failed

asyncio.run(process_bid_docs())
"

log "========================================"
log "Phase 2: Processing Contract Documents"
log "========================================"

python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from process_documents import DocumentProcessor
from pathlib import Path
import os

async def process_contract_docs():
    processor = DocumentProcessor(
        database_url=os.environ['DATABASE_URL'],
        files_store=Path(os.environ['FILES_STORE'])
    )
    await processor.connect()

    # Get contract documents
    rows = await processor.conn.fetch('''
        SELECT doc_id, tender_id, file_url, file_name, file_path, extraction_status
        FROM documents
        WHERE file_url LIKE '%DownloadContractFile%'
          AND (extraction_status = 'pending' OR extraction_status IS NULL)
        ORDER BY doc_id
        LIMIT \$1
    ''', $BATCH_SIZE)

    print(f'Found {len(rows)} pending contract documents')

    success = 0
    failed = 0
    for doc in rows:
        doc_dict = dict(doc)
        if await processor.process_document(doc_dict):
            success += 1
        else:
            failed += 1

    print(f'Contract documents: {success} success, {failed} failed')
    await processor.close()
    return success, failed

asyncio.run(process_contract_docs())
"

log "========================================"
log "Phase 3: Processing Other Documents"
log "========================================"

python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from process_documents import DocumentProcessor
from pathlib import Path
import os

async def process_other_docs():
    processor = DocumentProcessor(
        database_url=os.environ['DATABASE_URL'],
        files_store=Path(os.environ['FILES_STORE'])
    )
    await processor.connect()

    # Get other e-nabavki documents (excluding external bank docs)
    rows = await processor.conn.fetch('''
        SELECT doc_id, tender_id, file_url, file_name, file_path, extraction_status
        FROM documents
        WHERE file_url LIKE '%e-nabavki%'
          AND file_url NOT LIKE '%ohridskabanka%'
          AND file_url NOT LIKE '%DownloadBidFile%'
          AND file_url NOT LIKE '%DownloadContractFile%'
          AND (extraction_status = 'pending' OR extraction_status IS NULL)
        ORDER BY doc_id
        LIMIT \$1
    ''', $BATCH_SIZE)

    print(f'Found {len(rows)} pending other documents')

    success = 0
    failed = 0
    for doc in rows:
        doc_dict = dict(doc)
        if await processor.process_document(doc_dict):
            success += 1
        else:
            failed += 1

    print(f'Other documents: {success} success, {failed} failed')
    await processor.close()
    return success, failed

asyncio.run(process_other_docs())
"

log "========================================"
log "Phase 4: PDF Metadata Extraction (Backfill)"
log "========================================"

# Run the backfill script to extract CPV codes, emails, phones from PDFs
# This processes documents that have file_path but no specifications_json
python3 backfill_pdf_extraction.py 200 || {
    RC=$?
    log "WARNING: PDF backfill failed with exit code $RC"
}

# Deactivate virtual environment
deactivate 2>/dev/null || true

log "Document processing completed"
