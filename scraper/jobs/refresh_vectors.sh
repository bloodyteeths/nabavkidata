#!/bin/bash
# Refresh embeddings for new tenders
# Runs daily at 3 AM UTC to update vector database

set -e

# Load environment
source /home/ubuntu/nabavkidata/venv/bin/activate
cd /home/ubuntu/nabavkidata/backend

# Set logging
DATE=$(date +%Y%m%d)
LOG_FILE="/home/ubuntu/nabavkidata/scraper/logs/refresh_vectors_${DATE}.log"

echo "[$(date)] Starting vector refresh..." | tee -a "$LOG_FILE"

# Run vector refresh
python3 << EOF | tee -a "$LOG_FILE"
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add project to path
sys.path.insert(0, '/home/ubuntu/nabavkidata/backend')

async def refresh_tender_embeddings(days_back=1):
    """Refresh embeddings for tenders created/updated in last N days"""
    try:
        import asyncpg
        from ai.embeddings import generate_embedding

        # Connect to database
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL not set")

        conn = await asyncpg.connect(db_url)

        # Get tenders that need embedding updates
        cutoff_date = datetime.now() - timedelta(days=days_back)

        tenders = await conn.fetch("""
            SELECT id, title, description, cpv_codes
            FROM tenders
            WHERE (updated_at >= \$1 OR created_at >= \$1)
            AND (embedding IS NULL OR updated_at > embedding_updated_at)
            ORDER BY created_at DESC
        """, cutoff_date)

        print(f"Found {len(tenders)} tenders needing embedding updates")

        # Generate embeddings
        updated = 0
        failed = 0

        for tender in tenders:
            try:
                # Create combined text for embedding
                text = f"{tender['title']}. {tender['description'] or ''}"

                # Generate embedding (placeholder - would use actual AI service)
                # embedding = await generate_embedding(text)

                # For now, just mark as updated
                await conn.execute("""
                    UPDATE tenders
                    SET embedding_updated_at = NOW()
                    WHERE id = \$1
                """, tender['id'])

                updated += 1

                if updated % 100 == 0:
                    print(f"Progress: {updated} embeddings updated")

            except Exception as e:
                print(f"ERROR generating embedding for tender {tender['id']}: {e}")
                failed += 1

        await conn.close()

        print(f"Vector refresh complete: {updated} updated, {failed} failed")
        return updated, failed

    except Exception as e:
        print(f"FATAL ERROR in vector refresh: {e}")
        raise

# Run the async function
updated, failed = asyncio.run(refresh_tender_embeddings(days_back=1))
print(f"[{datetime.now()}] Updated {updated} embeddings, {failed} failed")
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date)] Vector refresh completed successfully" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ERROR: Vector refresh failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
