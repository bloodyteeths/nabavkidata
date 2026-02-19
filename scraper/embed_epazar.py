#!/usr/bin/env python3
"""
Generate embeddings for e-Pazar tenders.

Builds searchable text from:
- Title
- Description
- Contracting authority
- Procedure type
- Category
- CPV code
- Aggregated item names and descriptions

Stores in embeddings table with tender_id = 'epazar_' + tender_id
Expected: ~900 tenders to process
"""
import argparse
import json
import logging
import os
import queue
import threading
import time
from typing import List, Dict, Tuple

import psycopg2
from psycopg2.extras import execute_values
from fastembed import TextEmbedding
from dotenv import load_dotenv
load_dotenv()


os.environ['OMP_NUM_THREADS'] = '8'
os.environ['TOKENIZERS_PARALLELISM'] = 'true'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/embed_epazar.log')
    ]
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
MODEL_NAME = 'BAAI/bge-base-en-v1.5'


def build_epazar_text(tender_data: Dict, items_text: str = '') -> str:
    """Build searchable text from epazar tender fields."""
    parts = []

    # Add tender ID with epazar_ prefix for consistency
    if tender_data.get('tender_id'):
        parts.append(f"epazar_{tender_data['tender_id']}")

    # Add title (most important)
    if tender_data.get('title'):
        parts.append(tender_data['title'])

    # Add description if available
    if tender_data.get('description'):
        desc = str(tender_data['description'])[:500]
        parts.append(desc)

    # Add contracting authority
    if tender_data.get('contracting_authority'):
        parts.append(tender_data['contracting_authority'])

    # Add procedure type
    if tender_data.get('procedure_type'):
        parts.append(tender_data['procedure_type'])

    # Add category
    if tender_data.get('category'):
        parts.append(tender_data['category'])

    # Add CPV code
    if tender_data.get('cpv_code'):
        parts.append(f"CPV: {tender_data['cpv_code']}")

    # Add aggregated items text
    if items_text:
        parts.append(items_text[:500])

    text = ' | '.join(parts)

    # Truncate to reasonable length
    return text[:1500] if text else ''


class AsyncDBWriter(threading.Thread):
    """Async writer for embeddings to avoid blocking on DB I/O."""
    def __init__(self):
        super().__init__(daemon=True)
        self.queue = queue.Queue(maxsize=100)
        self.stop_event = threading.Event()
        self.written = 0
        self.errors = 0

    def run(self):
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        conn.autocommit = False

        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                batch = self.queue.get(timeout=1)
                if batch is None:
                    break

                with conn.cursor() as cur:
                    execute_values(
                        cur,
                        """INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, vector, metadata)
                           VALUES %s ON CONFLICT DO NOTHING""",
                        batch,
                        template="(%s, NULL, %s, 0, %s::vector, %s::jsonb)"
                    )
                conn.commit()
                self.written += len(batch)

            except queue.Empty:
                continue
            except Exception as e:
                self.errors += 1
                logger.error(f"DB write error: {e}")
                try:
                    conn.rollback()
                except:
                    pass

        conn.close()

    def write(self, batch):
        self.queue.put(batch)

    def stop(self):
        self.stop_event.set()
        self.queue.put(None)
        self.join(timeout=60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', type=int, default=50, help='Embedding batch size')
    parser.add_argument('--limit', type=int, default=10000, help='Max tenders to process')
    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)

    logger.info(f"Loading model: {MODEL_NAME}")
    model = TextEmbedding(MODEL_NAME, threads=8)
    logger.info("Model loaded")

    # Get all epazar tender IDs that don't have embeddings yet
    logger.info("Fetching epazar tender IDs without embeddings...")
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=120)
    cur = conn.cursor()

    cur.execute("""
        SELECT e.tender_id
        FROM epazar_tenders e
        WHERE NOT EXISTS (
            SELECT 1 FROM embeddings emb
            WHERE emb.tender_id = 'epazar_' || e.tender_id
        )
        ORDER BY e.tender_id
        LIMIT %s
    """, (args.limit,))

    all_ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()

    total = len(all_ids)
    logger.info(f"Found {total:,} epazar tenders to embed")

    if total == 0:
        logger.info("Nothing to embed!")
        return

    # Start async writer
    writer = AsyncDBWriter()
    writer.start()

    start_time = time.time()
    processed = 0

    # Process in batches of 100 to keep memory usage low
    fetch_size = 100
    for batch_start in range(0, total, fetch_size):
        batch_ids = all_ids[batch_start:batch_start + fetch_size]

        # Fetch tender data with aggregated items
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()

        placeholders = ','.join(['%s'] * len(batch_ids))

        # Get tender data
        cur.execute(f"""
            SELECT
                e.tender_id,
                e.title,
                e.description,
                e.contracting_authority,
                e.procedure_type,
                e.category,
                e.cpv_code
            FROM epazar_tenders e
            WHERE e.tender_id IN ({placeholders})
        """, batch_ids)

        tender_rows = {r[0]: {
            'tender_id': r[0],
            'title': r[1],
            'description': r[2],
            'contracting_authority': r[3],
            'procedure_type': r[4],
            'category': r[5],
            'cpv_code': r[6]
        } for r in cur.fetchall()}

        # Get aggregated items for these tenders
        cur.execute(f"""
            SELECT
                i.tender_id,
                STRING_AGG(
                    COALESCE(i.item_name, '') || ' ' || COALESCE(i.item_description, ''),
                    ', '
                ) as items_text
            FROM epazar_items i
            WHERE i.tender_id IN ({placeholders})
            GROUP BY i.tender_id
        """, batch_ids)

        items_dict = {r[0]: r[1] for r in cur.fetchall()}

        cur.close()
        conn.close()

        # Build texts for embedding
        tender_data = []
        for tid in batch_ids:
            tender = tender_rows.get(tid)
            if not tender:
                continue

            items_text = items_dict.get(tid, '')
            text = build_epazar_text(tender, items_text)

            if text and len(text) > 20:
                # Store with 'epazar_' prefix for tender_id
                tender_data.append((f"epazar_{tid}", text[:1500], tender))

        if not tender_data:
            processed += len(batch_ids)
            continue

        # Generate embeddings in smaller batches
        for i in range(0, len(tender_data), args.batch_size):
            embed_batch = tender_data[i:i + args.batch_size]
            texts = [t[1] for t in embed_batch]

            embeddings = list(model.embed(texts))

            # Prepare DB batch
            db_batch = []
            for (prefixed_tid, text, tender), emb in zip(embed_batch, embeddings):
                emb_str = '[' + ','.join(map(str, emb.tolist())) + ']'
                metadata = json.dumps({
                    'source': 'epazar',
                    'contracting_authority': tender.get('contracting_authority'),
                    'category': tender.get('category'),
                    'procedure_type': tender.get('procedure_type')
                })
                db_batch.append((prefixed_tid, text[:500], emb_str, metadata))

            writer.write(db_batch)

        processed += len(batch_ids)

        # Progress reporting
        elapsed = time.time() - start_time
        rate = processed / (elapsed / 60) if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0
        pct = (processed / total) * 100

        if processed % 100 == 0 or processed >= total:
            logger.info(f"{processed:,}/{total:,} ({pct:.1f}%) | {rate:.0f}/min | ETA: {eta:.1f}min | Written: {writer.written}")

    # Finish
    logger.info("Waiting for DB writes to complete...")
    writer.stop()

    total_time = time.time() - start_time
    rate = writer.written / (total_time / 60) if total_time > 0 else 0

    logger.info("=" * 60)
    logger.info(f"DONE! {writer.written:,} embeddings in {total_time/60:.1f} min")
    logger.info(f"Rate: {rate:.0f}/min | Errors: {writer.errors}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
