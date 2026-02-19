#!/usr/bin/env python3
"""
Local embeddings using sentence-transformers.
Runs on M1 Max GPU - FREE, no API tokens needed.

Models options:
- paraphrase-multilingual-MiniLM-L12-v2: Good for Macedonian (384 dims)
- multilingual-e5-large: Best quality (1024 dims)
- all-MiniLM-L6-v2: Fastest (384 dims, English-focused)
"""
import argparse
import asyncio
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

import asyncpg
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/embed_local.log')
    ]
)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)

# Model - multilingual works best for Macedonian
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'


def load_model():
    """Load sentence transformer model (uses MPS on M1)."""
    logger.info(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    # Try to use MPS (Apple Silicon GPU)
    try:
        import torch
        if torch.backends.mps.is_available():
            model = model.to('mps')
            logger.info("Using MPS (Apple Silicon GPU)")
        else:
            logger.info("MPS not available, using CPU")
    except:
        logger.info("Using CPU")
    return model


def build_text_from_json(data: dict) -> str:
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
    query = """
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
    """
    rows = await conn.fetch(query, limit)
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
    conn = await asyncpg.connect(DATABASE_URL)

    # Get tenders to embed
    tenders = await get_tenders_to_embed(conn, max_tenders)
    logger.info(f"Found {len(tenders)} tenders to embed")

    if not tenders:
        await conn.close()
        return

    total_embedded = 0
    start_time = time.time()

    # Process in batches for efficiency
    for i in range(0, len(tenders), batch_size):
        batch = tenders[i:i + batch_size]

        # Build texts
        texts = []
        tender_ids = []
        for t in batch:
            text = build_text_from_json(t['raw_data_json'])
            if len(text) > 20:
                texts.append(text[:2000])  # Limit text length
                tender_ids.append(t['tender_id'])

        if not texts:
            continue

        # Generate embeddings in batch (GPU accelerated)
        embeddings = model.encode(texts, show_progress_bar=False)

        # Prepare for DB insert
        db_batch = []
        for tid, text, emb in zip(tender_ids, texts, embeddings):
            # Convert numpy array to pgvector string format
            emb_str = '[' + ','.join(str(float(x)) for x in emb) + ']'
            metadata = json.dumps({'source': 'local', 'model': MODEL_NAME})
            db_batch.append((tid, text, emb_str, metadata))

        # Store in DB
        await store_embeddings(conn, db_batch)

        total_embedded += len(db_batch)
        elapsed = time.time() - start_time
        rate = total_embedded / elapsed * 60 if elapsed > 0 else 0

        if total_embedded % 1000 == 0 or total_embedded == len(tenders):
            logger.info(f"Embedded {total_embedded}/{len(tenders)} tenders ({rate:.0f}/min)")

    await conn.close()

    total_time = time.time() - start_time
    logger.info(f"Done! Embedded {total_embedded} tenders in {total_time:.1f}s ({total_embedded/total_time*60:.0f}/min)")


def main():
    parser = argparse.ArgumentParser(description='Local embeddings using sentence-transformers')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for GPU')
    parser.add_argument('--max-tenders', type=int, default=10000, help='Max tenders to embed')
    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)

    # Load model
    model = load_model()

    # Run embedding
    asyncio.run(embed_tenders(model, args.batch_size, args.max_tenders))


if __name__ == '__main__':
    main()
