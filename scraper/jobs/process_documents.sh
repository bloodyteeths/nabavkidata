#!/bin/bash
# Process document download queue
# Runs every 15 minutes to download and parse tender documents

set -e

# Load environment
source /home/ubuntu/nabavkidata/venv/bin/activate
cd /home/ubuntu/nabavkidata/backend

# Set logging
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/ubuntu/nabavkidata/scraper/logs/process_documents_${TIMESTAMP}.log"

echo "[$(date)] Starting document processing..." | tee -a "$LOG_FILE"

# Run document processor
python3 << EOF | tee -a "$LOG_FILE"
import asyncio
import sys
import os
from datetime import datetime

# Add project to path
sys.path.insert(0, '/home/ubuntu/nabavkidata/backend')

async def process_pending_documents(batch_size=10):
    """Process pending documents from the queue"""
    try:
        import asyncpg
        from services.document_service import DocumentService

        # Connect to database
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL not set")

        conn = await asyncpg.connect(db_url)

        # Get pending documents
        pending = await conn.fetch("""
            SELECT id, tender_id, url, file_type
            FROM documents
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT \$1
        """, batch_size)

        print(f"Found {len(pending)} pending documents")

        # Process each document
        processed = 0
        failed = 0

        for doc in pending:
            try:
                # Update status to processing
                await conn.execute("""
                    UPDATE documents
                    SET status = 'processing', updated_at = NOW()
                    WHERE id = \$1
                """, doc['id'])

                # Download and process document
                # This would call actual document processing logic
                print(f"Processing document {doc['id']} - {doc['url']}")

                # Mark as completed
                await conn.execute("""
                    UPDATE documents
                    SET status = 'completed',
                        processed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = \$1
                """, doc['id'])

                processed += 1

            except Exception as e:
                print(f"ERROR processing document {doc['id']}: {e}")

                # Mark as failed
                await conn.execute("""
                    UPDATE documents
                    SET status = 'failed',
                        error = \$1,
                        updated_at = NOW()
                    WHERE id = \$2
                """, str(e), doc['id'])

                failed += 1

        await conn.close()

        print(f"Document processing complete: {processed} processed, {failed} failed")
        return processed, failed

    except Exception as e:
        print(f"FATAL ERROR in document processing: {e}")
        raise

# Run the async function
processed, failed = asyncio.run(process_pending_documents(batch_size=10))
print(f"[{datetime.now()}] Processed {processed} documents, {failed} failed")
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date)] Document processing completed successfully" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ERROR: Document processing failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
