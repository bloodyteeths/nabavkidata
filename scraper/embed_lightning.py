#!/usr/bin/env python3
"""
Lightning-fast embeddings - fixed version.
- Pre-fetches all tender IDs in one query (fast)
- Keyset pagination for data fetch
- Async DB writes
- 8-thread ONNX inference

Expected: 300-500/min
"""
import argparse
import json
import logging
import os
import queue
import threading
import time
from typing import List

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
        logging.FileHandler('logs/embed_lightning.log')
    ]
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
MODEL_NAME = 'BAAI/bge-base-en-v1.5'


def build_text(data) -> str:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            return data[:1500]

    parts = []
    for key in ['tender_id', 'title', 'description', 'procuring_entity', 'winner', 'cpv_code']:
        val = data.get(key)
        if val:
            if key == 'description':
                val = str(val)[:800]
            parts.append(str(val))
    return ' | '.join(parts) if parts else str(data)[:1500]


class AsyncDBWriter(threading.Thread):
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
                logger.error(f"DB error: {e}")
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
    parser.add_argument('--batch-size', type=int, default=100, help='Embedding batch')
    parser.add_argument('--limit', type=int, default=300000, help='Max tenders')
    parser.add_argument('--fetch-size', type=int, default=1000, help='DB fetch size')
    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)

    logger.info(f"Loading model: {MODEL_NAME}")
    model = TextEmbedding(MODEL_NAME, threads=8)
    logger.info("Model loaded")

    # FAST: Get all tender IDs needing embeddings in ONE query
    logger.info("Fetching tender IDs (one-time query)...")
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=120)
    cur = conn.cursor()

    cur.execute("""
        SELECT t.tender_id
        FROM tenders t
        WHERE t.raw_data_json IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM embeddings e
            WHERE e.tender_id = t.tender_id AND e.doc_id IS NULL
        )
        ORDER BY t.tender_id
        LIMIT %s
    """, (args.limit,))

    all_ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()

    total = len(all_ids)
    logger.info(f"Found {total:,} tenders to embed")

    if total == 0:
        logger.info("Nothing to embed!")
        return

    # Start async writer
    writer = AsyncDBWriter()
    writer.start()

    start_time = time.time()
    processed = 0

    # Process in fetch-size batches
    for batch_start in range(0, total, args.fetch_size):
        batch_ids = all_ids[batch_start:batch_start + args.fetch_size]

        # Fetch data for this batch
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()

        placeholders = ','.join(['%s'] * len(batch_ids))
        cur.execute(f"""
            SELECT tender_id, raw_data_json
            FROM tenders
            WHERE tender_id IN ({placeholders})
        """, batch_ids)

        rows = {r[0]: r[1] for r in cur.fetchall()}
        cur.close()
        conn.close()

        # Build texts
        tender_data = []
        for tid in batch_ids:
            raw_json = rows.get(tid)
            if raw_json:
                text = build_text(raw_json)
                if text and len(text) > 20:
                    tender_data.append((tid, text[:1500]))

        if not tender_data:
            processed += len(batch_ids)
            continue

        # Embed in smaller batches
        for i in range(0, len(tender_data), args.batch_size):
            embed_batch = tender_data[i:i + args.batch_size]
            texts = [t[1] for t in embed_batch]

            embeddings = list(model.embed(texts))

            db_batch = []
            for (tid, text), emb in zip(embed_batch, embeddings):
                emb_str = '[' + ','.join(map(str, emb.tolist())) + ']'
                metadata = json.dumps({'source': 'lightning'})
                db_batch.append((tid, text[:500], emb_str, metadata))

            writer.write(db_batch)

        processed += len(batch_ids)

        # Progress
        elapsed = time.time() - start_time
        rate = processed / (elapsed / 60) if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0
        pct = (processed / total) * 100

        if processed % 5000 == 0 or processed >= total:
            logger.info(f"{processed:,}/{total:,} ({pct:.1f}%) | {rate:.0f}/min | ETA: {eta:.0f}min")

    # Finish
    logger.info("Waiting for DB writes...")
    writer.stop()

    total_time = time.time() - start_time
    rate = writer.written / (total_time / 60) if total_time > 0 else 0

    logger.info("=" * 60)
    logger.info(f"DONE! {writer.written:,} embeddings in {total_time/60:.1f} min")
    logger.info(f"Rate: {rate:.0f}/min | Errors: {writer.errors}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
