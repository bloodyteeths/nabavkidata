#!/usr/bin/env python3
"""
Fast local embeddings using fastembed.
Lightweight, no heavy dependencies.
"""
import argparse
import asyncio
import json
import logging
import os
import time
from typing import List

import asyncpg
from fastembed import TextEmbedding

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/embed_fast.log')
    ]
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)

# 768-dim model to match DB vector column
MODEL_NAME = 'BAAI/bge-base-en-v1.5'


def build_text_from_json(data) -> str:
    """Build searchable text from tender raw_data_json."""
    if isinstance(data, str):
        data = json.loads(data)

    parts = []
    if data.get('tender_id'):
        parts.append(f"Тендер: {data['tender_id']}")
    if data.get('title'):
        parts.append(f"Наслов: {data['title']}")
    if data.get('description'):
        parts.append(f"Опис: {data['description']}")
    if data.get('procuring_entity'):
        parts.append(f"Договорен орган: {data['procuring_entity']}")
    if data.get('winner'):
        parts.append(f"Добитник: {data['winner']}")
    if data.get('estimated_value_mkd'):
        parts.append(f"Вредност: {data['estimated_value_mkd']} МКД")
    if data.get('cpv_code'):
        parts.append(f"CPV: {data['cpv_code']}")
    if data.get('status'):
        parts.append(f"Статус: {data['status']}")

    return '\n'.join(parts)


async def get_tenders_to_embed(conn, limit: int) -> List[dict]:
    """Get tenders that need embeddings."""
    rows = await conn.fetch("""
        SELECT t.tender_id, t.raw_data_json
        FROM tenders t
        WHERE t.raw_data_json IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM embeddings e
              WHERE e.tender_id = t.tender_id
              AND e.doc_id IS NULL
          )
        ORDER BY t.created_at DESC
        LIMIT $1
    """, limit)
    return [dict(r) for r in rows]


async def store_embeddings(conn, batch: List[tuple]):
    """Store batch of embeddings."""
    await conn.executemany("""
        INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, vector, metadata)
        VALUES ($1, NULL, $2, 0, $3::vector, $4::jsonb)
        ON CONFLICT DO NOTHING
    """, batch)


async def embed_tenders(model, batch_size: int = 100, max_tenders: int = 10000):
    """Generate embeddings for tenders."""
    conn = await asyncpg.connect(DATABASE_URL, timeout=120, command_timeout=120)

    tenders = await get_tenders_to_embed(conn, max_tenders)
    logger.info(f"Found {len(tenders)} tenders to embed")

    if not tenders:
        await conn.close()
        return

    total_embedded = 0
    start_time = time.time()

    # Process in batches
    for i in range(0, len(tenders), batch_size):
        batch = tenders[i:i + batch_size]

        # Build texts
        texts = []
        tender_ids = []
        for t in batch:
            text = build_text_from_json(t['raw_data_json'])
            if len(text) > 20:
                texts.append(text[:2000])
                tender_ids.append(t['tender_id'])

        if not texts:
            continue

        # Generate embeddings in batch
        embeddings = list(model.embed(texts))

        # Prepare for DB insert
        db_batch = []
        for tid, text, emb in zip(tender_ids, texts, embeddings):
            emb_str = '[' + ','.join(str(float(x)) for x in emb) + ']'
            metadata = json.dumps({'source': 'local', 'model': MODEL_NAME})
            db_batch.append((tid, text, emb_str, metadata))

        # Store in DB
        await store_embeddings(conn, db_batch)

        total_embedded += len(db_batch)
        elapsed = time.time() - start_time
        rate = total_embedded / elapsed * 60 if elapsed > 0 else 0

        if total_embedded % 1000 == 0 or i + batch_size >= len(tenders):
            logger.info(f"Embedded {total_embedded}/{len(tenders)} ({rate:.0f}/min)")

    await conn.close()

    total_time = time.time() - start_time
    final_rate = total_embedded / total_time * 60 if total_time > 0 else 0
    logger.info(f"Done! {total_embedded} tenders in {total_time:.1f}s ({final_rate:.0f}/min)")


def main():
    parser = argparse.ArgumentParser(description='Fast local embeddings')
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--max-tenders', type=int, default=10000)
    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)

    logger.info(f"Loading model: {MODEL_NAME}")
    model = TextEmbedding(MODEL_NAME)
    logger.info("Model loaded")

    asyncio.run(embed_tenders(model, args.batch_size, args.max_tenders))


if __name__ == '__main__':
    main()
