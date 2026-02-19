#!/usr/bin/env python3
"""
Parallel embeddings using multiple workers.
Each worker processes a batch of tenders independently.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List

import psycopg2
from fastembed import TextEmbedding

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [Worker %(process)d] %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
MODEL_NAME = 'BAAI/bge-base-en-v1.5'


def build_text(data) -> str:
    """Build searchable text from tender data."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            return data[:2000]

    parts = []
    if data.get('tender_id'):
        parts.append(f"Тендер: {data['tender_id']}")
    if data.get('title'):
        parts.append(f"Наслов: {data['title']}")
    if data.get('description'):
        parts.append(f"Опис: {data['description'][:1000]}")
    if data.get('procuring_entity'):
        parts.append(f"Договорен орган: {data['procuring_entity']}")
    if data.get('winner'):
        parts.append(f"Добитник: {data['winner']}")
    if data.get('estimated_value_mkd'):
        parts.append(f"Вредност: {data['estimated_value_mkd']} МКД")
    if data.get('cpv_code'):
        parts.append(f"CPV: {data['cpv_code']}")

    return '\n'.join(parts) if parts else str(data)[:2000]


def process_batch(worker_id: int, tender_ids: List[str], batch_size: int = 50):
    """Process a batch of tenders in a single worker."""
    logger.info(f"Worker {worker_id} starting with {len(tender_ids)} tenders")

    # Load model
    model = TextEmbedding(MODEL_NAME)

    conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
    cur = conn.cursor()

    processed = 0
    embedded = 0

    for i in range(0, len(tender_ids), batch_size):
        batch_ids = tender_ids[i:i + batch_size]

        # Get tender data
        placeholders = ','.join(['%s'] * len(batch_ids))
        cur.execute(f"""
            SELECT tender_id, raw_data_json
            FROM tenders
            WHERE tender_id IN ({placeholders})
            AND raw_data_json IS NOT NULL
        """, batch_ids)

        rows = cur.fetchall()
        if not rows:
            continue

        # Build texts
        texts = []
        valid_tenders = []
        for tender_id, raw_json in rows:
            text = build_text(raw_json)
            if text and len(text) > 20:
                texts.append(text)
                valid_tenders.append(tender_id)

        if not texts:
            continue

        # Generate embeddings
        try:
            embeddings = list(model.embed(texts))

            # Store embeddings
            for tender_id, text, emb in zip(valid_tenders, texts, embeddings):
                vector_str = '[' + ','.join(map(str, emb.tolist())) + ']'
                cur.execute("""
                    INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, vector, metadata)
                    VALUES (%s, NULL, %s, 0, %s::vector, %s::jsonb)
                    ON CONFLICT DO NOTHING
                """, (tender_id, text[:500], vector_str, json.dumps({'source': 'tender'})))

            conn.commit()
            embedded += len(valid_tenders)

        except Exception as e:
            logger.error(f"Worker {worker_id} embedding error: {e}")
            conn.rollback()

        processed += len(batch_ids)

        if processed % 500 == 0:
            logger.info(f"Worker {worker_id}: {processed}/{len(tender_ids)} processed, {embedded} embedded")

    cur.close()
    conn.close()

    logger.info(f"Worker {worker_id} done: {embedded} embeddings created")
    return embedded


def get_tenders_to_embed(limit: int = 300000) -> List[str]:
    """Get tender IDs that need embeddings."""
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
    cur = conn.cursor()

    cur.execute("""
        SELECT t.tender_id
        FROM tenders t
        WHERE t.raw_data_json IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM embeddings e
            WHERE e.tender_id = t.tender_id
            AND e.doc_id IS NULL
        )
        ORDER BY t.created_at DESC
        LIMIT %s
    """, (limit,))

    tender_ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    return tender_ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--limit', type=int, default=300000, help='Max tenders to process')
    args = parser.parse_args()

    logger.info(f"Getting tenders to embed...")
    tender_ids = get_tenders_to_embed(args.limit)
    logger.info(f"Found {len(tender_ids)} tenders needing embeddings")

    if not tender_ids:
        logger.info("No tenders to embed!")
        return

    # Split among workers
    num_workers = min(args.workers, len(tender_ids))
    batch_size = len(tender_ids) // num_workers
    batches = []
    for i in range(num_workers):
        start = i * batch_size
        end = start + batch_size if i < num_workers - 1 else len(tender_ids)
        batches.append(tender_ids[start:end])

    logger.info(f"Starting {num_workers} workers...")
    start_time = time.time()

    total_embedded = 0
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(process_batch, i + 1, batch): i
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            try:
                embedded = future.result()
                total_embedded += embedded
            except Exception as e:
                logger.error(f"Worker failed: {e}")

    elapsed = time.time() - start_time
    rate = total_embedded / (elapsed / 60) if elapsed > 0 else 0

    logger.info("=" * 50)
    logger.info(f"DONE! {total_embedded} embeddings in {elapsed:.1f}s ({rate:.1f}/min)")
    logger.info("=" * 50)


if __name__ == '__main__':
    main()
