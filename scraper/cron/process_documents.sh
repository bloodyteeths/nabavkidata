#!/bin/bash
#
# CRON SCRIPT: Process Tender Documents (PDF Extraction)
#
# This script processes pending documents from the database:
# 1. Downloads PDFs from e-nabavki.gov.mk
# 2. Extracts text and product data using financial_bid_extractor
# 3. Populates product_items table with extracted products
#
# Schedule: every 4 hours at :30 (30 2,6,10,14,18,22 * * *)
#
# Safety: lock max-age (4h) + per-phase timeout (1h)
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/nabavkidata"
FILES_STORE="/home/ubuntu/nabavkidata/scraper/downloads/files"

# Database URL
export DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set in environment}"
export FILES_STORE="$FILES_STORE"

# Ensure directories exist
mkdir -p "$LOG_DIR"
mkdir -p "$FILES_STORE"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Prevent duplicate instances with max-age protection
LOCKFILE="/tmp/process_documents.lock"
MAX_LOCK_AGE=14400  # 4 hours max for document processing

if [ -f "$LOCKFILE" ]; then
    OTHER_PID=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$OTHER_PID" ] && [[ "$OTHER_PID" =~ ^[0-9]+$ ]] && kill -0 "$OTHER_PID" 2>/dev/null; then
        # PID is alive -- check how long it has been running
        ELAPSED=$(ps -o etimes= -p "$OTHER_PID" 2>/dev/null | tr -d ' ')
        if [ -n "$ELAPSED" ] && [ "$ELAPSED" -gt "$MAX_LOCK_AGE" ]; then
            log "STALE: Document processor PID $OTHER_PID running for ${ELAPSED}s (max ${MAX_LOCK_AGE}s), killing..."
            kill -TERM "$OTHER_PID" 2>/dev/null
            sleep 5
            if kill -0 "$OTHER_PID" 2>/dev/null; then
                kill -9 "$OTHER_PID" 2>/dev/null
            fi
            rm -f "$LOCKFILE"
        else
            log "Another document processor is running (PID $OTHER_PID, ${ELAPSED:-?}s), skipping."
            exit 0
        fi
    else
        log "Stale lock found (PID $OTHER_PID not running), removing."
        rm -f "$LOCKFILE"
    fi
fi
echo $$ > "$LOCKFILE"
trap "rm -f '$LOCKFILE'" EXIT

log "Starting document processing..."
log "FILES_STORE: $FILES_STORE"

# Change to scraper directory
cd /home/ubuntu/nabavkidata/scraper

# Process documents in batches
BATCH_SIZE=200

log "========================================"
log "Phase 1: Processing Bid Documents"
log "========================================"

timeout --signal=TERM --kill-after=30 3600 \
/usr/bin/python3 -c "
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
" || log "WARNING: Phase 1 failed or timed out"

log "========================================"
log "Phase 2: Processing Contract Documents"
log "========================================"

timeout --signal=TERM --kill-after=30 3600 \
/usr/bin/python3 -c "
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
" || log "WARNING: Phase 2 failed or timed out"

log "========================================"
log "Phase 3: Processing Other Documents"
log "========================================"

timeout --signal=TERM --kill-after=30 3600 \
/usr/bin/python3 -c "
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
" || log "WARNING: Phase 3 failed or timed out"

log "========================================"
log "Phase 4: PDF Metadata Extraction (Backfill)"
log "========================================"

# Run the backfill script to extract CPV codes, emails, phones from PDFs
timeout --signal=TERM --kill-after=30 3600 \
/usr/bin/python3 backfill_pdf_extraction.py 200 || {
    RC=$?
    log "WARNING: PDF backfill failed with exit code $RC"
}

log "========================================"
log "Phase 5: Cleanup Downloaded PDFs"
log "========================================"

# Delete successfully processed PDFs to save disk space
CLEANED=0
for f in "$FILES_STORE"/*.pdf "$FILES_STORE"/*.docx "$FILES_STORE"/*.xlsx; do
    [ -f "$f" ] && rm -f "$f" && CLEANED=$((CLEANED + 1))
done
log "Cleaned up $CLEANED files from $FILES_STORE"

log "Document processing completed"
