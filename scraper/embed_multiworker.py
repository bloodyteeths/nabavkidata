#!/usr/bin/env python3
"""
Multi-worker parallel embeddings for maximum speed.
Each worker has its own model instance and DB connection.
Splits work across N processes.

Expected: 600-1000/min with 4 workers
"""
import argparse
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List

import psycopg2
from psycopg2.extras import execute_values
from fastembed import TextEmbedding
from dotenv import load_dotenv
load_dotenv()


os.environ['TOKENIZERS_PARALLELISM'] = 'false'  # Avoid deadlock with multiprocessing

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [W%(process)d] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/embed_multiworker.log')
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


def process_worker(worker_id: int, tender_ids: List[str], batch_size: int = 100) -> dict:
    """Worker process - each has own model and DB connection."""
    # Set thread count per worker (lower when running multiple workers)
    os.environ['OMP_NUM_THREADS'] = '2'

    logger.info(f"Worker {worker_id} starting with {len(tender_ids):,} tenders")

    # Load model (each worker has its own)
    model = TextEmbedding(MODEL_NAME, threads=2)

    # DB connection
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)

    start_time = time.time()
    embedded = 0
    errors = 0

    # Process in chunks
    chunk_size = 1000
    for chunk_start in range(0, len(tender_ids), chunk_size):
        chunk_ids = tender_ids[chunk_start:chunk_start + chunk_size]

        # Fetch data
        with conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(chunk_ids))
            cur.execute(f"""
                SELECT tender_id, raw_data_json
                FROM tenders
                WHERE tender_id IN ({placeholders})
            """, chunk_ids)
            rows = {r[0]: r[1] for r in cur.fetchall()}

        # Build texts
        tender_data = []
        for tid in chunk_ids:
            raw_json = rows.get(tid)
            if raw_json:
                text = build_text(raw_json)
                if text and len(text) > 20:
                    tender_data.append((tid, text[:1500]))

        if not tender_data:
            continue

        # Embed in batches
        for i in range(0, len(tender_data), batch_size):
            batch = tender_data[i:i + batch_size]
            texts = [t[1] for t in batch]

            try:
                embeddings = list(model.embed(texts))

                db_batch = []
                for (tid, text), emb in zip(batch, embeddings):
                    emb_str = '[' + ','.join(map(str, emb.tolist())) + ']'
                    metadata = json.dumps({'source': 'multiworker', 'worker': worker_id})
                    db_batch.append((tid, text[:500], emb_str, metadata))

                with conn.cursor() as cur:
                    execute_values(
                        cur,
                        """INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, vector, metadata)
                           VALUES %s ON CONFLICT DO NOTHING""",
                        db_batch,
                        template="(%s, NULL, %s, 0, %s::vector, %s::jsonb)"
                    )
                conn.commit()
                embedded += len(db_batch)

            except Exception as e:
                errors += 1
                logger.error(f"Worker {worker_id} error: {e}")
                try:
                    conn.rollback()
                except:
                    pass

        # Progress
        total_done = chunk_start + len(chunk_ids)
        if total_done % 5000 == 0:
            elapsed = time.time() - start_time
            rate = embedded / (elapsed / 60) if elapsed > 0 else 0
            logger.info(f"Worker {worker_id}: {total_done:,}/{len(tender_ids):,} | {rate:.0f}/min")

    conn.close()

    elapsed = time.time() - start_time
    rate = embedded / (elapsed / 60) if elapsed > 0 else 0
    logger.info(f"Worker {worker_id} DONE: {embedded:,} in {elapsed/60:.1f}min ({rate:.0f}/min)")

    return {'worker': worker_id, 'embedded': embedded, 'errors': errors, 'time': elapsed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--batch-size', type=int, default=100, help='Embedding batch size per worker')
    parser.add_argument('--limit', type=int, default=300000, help='Max tenders to process')
    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)

    # Get all tender IDs needing embeddings
    logger.info("Fetching tender IDs...")
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

    # Split among workers
    num_workers = min(args.workers, max(1, total // 100))
    batch_per_worker = total // num_workers
    worker_batches = []

    for i in range(num_workers):
        start = i * batch_per_worker
        end = start + batch_per_worker if i < num_workers - 1 else total
        worker_batches.append(all_ids[start:end])

    logger.info("=" * 60)
    logger.info(f"STARTING {num_workers} WORKERS")
    logger.info(f"Total: {total:,} | Per worker: ~{batch_per_worker:,}")
    logger.info("=" * 60)

    start_time = time.time()
    total_embedded = 0
    total_errors = 0

    # Run workers in parallel
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(process_worker, i + 1, batch, args.batch_size): i
            for i, batch in enumerate(worker_batches)
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                total_embedded += result['embedded']
                total_errors += result['errors']
            except Exception as e:
                logger.error(f"Worker failed: {e}")

    total_time = time.time() - start_time
    rate = total_embedded / (total_time / 60) if total_time > 0 else 0

    logger.info("=" * 60)
    logger.info(f"ALL DONE! {total_embedded:,} embeddings in {total_time/60:.1f} min")
    logger.info(f"Combined rate: {rate:.0f}/min | Errors: {total_errors}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
