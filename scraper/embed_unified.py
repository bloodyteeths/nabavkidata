#!/usr/bin/env python3
"""
Unified embedding workflow for ALL data in database.
Covers: tenders, documents, epazar data.
Uses multi-worker processing with connection pooling.

Safe to run alongside OCDS import (uses max 6 connections out of 80).
"""
import argparse
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple

import psycopg2
from fastembed import TextEmbedding
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [Worker %(process)d] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/embed_unified.log')
    ]
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
MODEL_NAME = 'BAAI/bge-base-en-v1.5'


def build_tender_text(data) -> str:
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


def build_document_text(content: str, metadata: dict = None) -> str:
    """Build text from document content."""
    parts = []
    if metadata:
        if metadata.get('title'):
            parts.append(f"Документ: {metadata['title']}")
        if metadata.get('tender_id'):
            parts.append(f"Тендер: {metadata['tender_id']}")
    parts.append(content[:3000])
    return '\n'.join(parts)


def build_epazar_text(data: dict) -> str:
    """Build text from epazar tender."""
    parts = []
    if data.get('tender_id'):
        parts.append(f"Е-Пазар тендер: {data['tender_id']}")
    if data.get('title'):
        parts.append(f"Наслов: {data['title']}")
    if data.get('description'):
        parts.append(f"Опис: {data['description'][:1000]}")
    if data.get('buyer_name'):
        parts.append(f"Купувач: {data['buyer_name']}")
    if data.get('estimated_value'):
        parts.append(f"Вредност: {data['estimated_value']} МКД")
    return '\n'.join(parts)


def process_tender_batch(worker_id: int, tender_ids: List[str], batch_size: int = 50) -> int:
    """Process a batch of tenders in a single worker."""
    logger.info(f"Worker {worker_id}: Processing {len(tender_ids)} tenders")

    model = TextEmbedding(MODEL_NAME)
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
    cur = conn.cursor()

    embedded = 0

    for i in range(0, len(tender_ids), batch_size):
        batch_ids = tender_ids[i:i + batch_size]
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

        texts = []
        valid_ids = []
        for tender_id, raw_json in rows:
            text = build_tender_text(raw_json)
            if text and len(text) > 20:
                texts.append(text)
                valid_ids.append(tender_id)

        if not texts:
            continue

        try:
            embeddings = list(model.embed(texts))

            for tid, text, emb in zip(valid_ids, texts, embeddings):
                vector_str = '[' + ','.join(map(str, emb.tolist())) + ']'
                cur.execute("""
                    INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, vector, metadata)
                    VALUES (%s, NULL, %s, 0, %s::vector, %s::jsonb)
                    ON CONFLICT DO NOTHING
                """, (tid, text[:500], vector_str, json.dumps({'source': 'unified', 'type': 'tender'})))

            conn.commit()
            embedded += len(valid_ids)

        except Exception as e:
            logger.error(f"Worker {worker_id}: Error - {e}")
            conn.rollback()

        if embedded % 500 == 0 and embedded > 0:
            logger.info(f"Worker {worker_id}: {embedded} tenders embedded")

    cur.close()
    conn.close()
    logger.info(f"Worker {worker_id}: Done - {embedded} tenders")
    return embedded


def process_document_batch(worker_id: int, doc_ids: List[int], batch_size: int = 20) -> int:
    """Process documents."""
    logger.info(f"Worker {worker_id}: Processing {len(doc_ids)} documents")

    model = TextEmbedding(MODEL_NAME)
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
    cur = conn.cursor()

    embedded = 0

    for i in range(0, len(doc_ids), batch_size):
        batch_ids = doc_ids[i:i + batch_size]
        placeholders = ','.join(['%s'] * len(batch_ids))

        cur.execute(f"""
            SELECT doc_id, tender_id, file_name, content_text
            FROM documents
            WHERE doc_id IN ({placeholders})
            AND content_text IS NOT NULL
        """, batch_ids)

        rows = cur.fetchall()
        if not rows:
            continue

        texts = []
        valid_docs = []
        for doc_id, tender_id, file_name, content in rows:
            text = build_document_text(content, {'tender_id': tender_id, 'title': file_name})
            if text and len(text) > 50:
                texts.append(text)
                valid_docs.append((doc_id, tender_id))

        if not texts:
            continue

        try:
            embeddings = list(model.embed(texts))

            for (doc_id, tender_id), text, emb in zip(valid_docs, texts, embeddings):
                vector_str = '[' + ','.join(map(str, emb.tolist())) + ']'
                cur.execute("""
                    INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, vector, metadata)
                    VALUES (%s, %s, %s, 0, %s::vector, %s::jsonb)
                    ON CONFLICT DO NOTHING
                """, (tender_id, doc_id, text[:500], vector_str, json.dumps({'source': 'unified', 'type': 'document'})))

            conn.commit()
            embedded += len(valid_docs)

        except Exception as e:
            logger.error(f"Worker {worker_id}: Doc error - {e}")
            conn.rollback()

    cur.close()
    conn.close()
    logger.info(f"Worker {worker_id}: Done - {embedded} documents")
    return embedded


def process_epazar_batch(worker_id: int, epazar_ids: List[int], batch_size: int = 50) -> int:
    """Process epazar tenders."""
    logger.info(f"Worker {worker_id}: Processing {len(epazar_ids)} epazar items")

    model = TextEmbedding(MODEL_NAME)
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
    cur = conn.cursor()

    embedded = 0

    for i in range(0, len(epazar_ids), batch_size):
        batch_ids = epazar_ids[i:i + batch_size]
        placeholders = ','.join(['%s'] * len(batch_ids))

        cur.execute(f"""
            SELECT id, tender_id, title, description, buyer_name, estimated_value
            FROM epazar_tenders
            WHERE id IN ({placeholders})
        """, batch_ids)

        rows = cur.fetchall()
        if not rows:
            continue

        texts = []
        valid_items = []
        for row in rows:
            data = {
                'tender_id': row[1],
                'title': row[2],
                'description': row[3],
                'buyer_name': row[4],
                'estimated_value': row[5]
            }
            text = build_epazar_text(data)
            if text and len(text) > 20:
                texts.append(text)
                valid_items.append((row[0], row[1]))  # (id, tender_id)

        if not texts:
            continue

        try:
            embeddings = list(model.embed(texts))

            for (epazar_id, tender_id), text, emb in zip(valid_items, texts, embeddings):
                vector_str = '[' + ','.join(map(str, emb.tolist())) + ']'
                # Use special tender_id format for epazar
                epazar_tender_id = f"epazar_{tender_id or epazar_id}"
                cur.execute("""
                    INSERT INTO embeddings (tender_id, doc_id, chunk_text, chunk_index, vector, metadata)
                    VALUES (%s, NULL, %s, 0, %s::vector, %s::jsonb)
                    ON CONFLICT DO NOTHING
                """, (epazar_tender_id, text[:500], vector_str, json.dumps({'source': 'unified', 'type': 'epazar', 'epazar_id': epazar_id})))

            conn.commit()
            embedded += len(valid_items)

        except Exception as e:
            logger.error(f"Worker {worker_id}: Epazar error - {e}")
            conn.rollback()

    cur.close()
    conn.close()
    logger.info(f"Worker {worker_id}: Done - {embedded} epazar")
    return embedded


def get_missing_tender_ids(limit: int = 300000) -> List[str]:
    """Get tender IDs missing embeddings."""
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

    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return ids


def get_missing_document_ids() -> List[int]:
    """Get document IDs missing embeddings."""
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
    cur = conn.cursor()

    cur.execute("""
        SELECT d.doc_id
        FROM documents d
        WHERE d.content_text IS NOT NULL
        AND LENGTH(d.content_text) > 50
        AND NOT EXISTS (
            SELECT 1 FROM embeddings e
            WHERE e.doc_id = d.doc_id
        )
    """)

    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return ids


def get_missing_epazar_ids() -> List[int]:
    """Get epazar tender IDs missing embeddings."""
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
    cur = conn.cursor()

    cur.execute("""
        SELECT et.id
        FROM epazar_tenders et
        WHERE NOT EXISTS (
            SELECT 1 FROM embeddings e
            WHERE e.tender_id = 'epazar_' || COALESCE(et.tender_id, et.id::text)
        )
    """)

    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return ids


def split_into_batches(items: list, num_workers: int) -> List[list]:
    """Split items into batches for workers."""
    if not items:
        return []
    batch_size = max(1, len(items) // num_workers)
    batches = []
    for i in range(num_workers):
        start = i * batch_size
        end = start + batch_size if i < num_workers - 1 else len(items)
        if start < len(items):
            batches.append(items[start:end])
    return batches


def run_parallel(process_func, items: list, item_type: str, num_workers: int = 4):
    """Run embedding in parallel."""
    if not items:
        logger.info(f"No {item_type} to embed")
        return 0

    batches = split_into_batches(items, num_workers)
    logger.info(f"Processing {len(items)} {item_type} with {len(batches)} workers")

    total = 0
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=len(batches)) as executor:
        futures = {
            executor.submit(process_func, i + 1, batch): i
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            try:
                count = future.result()
                total += count
            except Exception as e:
                logger.error(f"Worker failed: {e}")

    elapsed = time.time() - start_time
    rate = total / (elapsed / 60) if elapsed > 0 else 0
    logger.info(f"Completed {total} {item_type} in {elapsed:.1f}s ({rate:.0f}/min)")

    return total


def main():
    parser = argparse.ArgumentParser(description='Unified embeddings for all data')
    parser.add_argument('--workers', type=int, default=4, help='Number of workers (default: 4, safe with OCDS import)')
    parser.add_argument('--tenders', action='store_true', help='Embed tenders')
    parser.add_argument('--documents', action='store_true', help='Embed documents')
    parser.add_argument('--epazar', action='store_true', help='Embed epazar data')
    parser.add_argument('--all', action='store_true', help='Embed all data types')
    parser.add_argument('--limit', type=int, default=300000, help='Max tenders to process')
    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)

    # If no specific type, do all
    if not (args.tenders or args.documents or args.epazar):
        args.all = True

    logger.info("=" * 60)
    logger.info("UNIFIED EMBEDDING WORKFLOW")
    logger.info(f"Workers: {args.workers} (DB max: 80, safe limit)")
    logger.info("=" * 60)

    start_time = time.time()
    total_embedded = 0

    # 1. Tenders (bulk of the work)
    if args.all or args.tenders:
        logger.info("\n--- TENDERS ---")
        tender_ids = get_missing_tender_ids(args.limit)
        logger.info(f"Found {len(tender_ids)} tenders missing embeddings")
        if tender_ids:
            total_embedded += run_parallel(
                process_tender_batch,
                tender_ids,
                "tenders",
                args.workers
            )

    # 2. Documents (small batch)
    if args.all or args.documents:
        logger.info("\n--- DOCUMENTS ---")
        doc_ids = get_missing_document_ids()
        logger.info(f"Found {len(doc_ids)} documents missing embeddings")
        if doc_ids:
            # Use fewer workers for small batch
            doc_workers = min(args.workers, max(1, len(doc_ids) // 20))
            total_embedded += run_parallel(
                process_document_batch,
                doc_ids,
                "documents",
                doc_workers
            )

    # 3. Epazar
    if args.all or args.epazar:
        logger.info("\n--- EPAZAR ---")
        epazar_ids = get_missing_epazar_ids()
        logger.info(f"Found {len(epazar_ids)} epazar items missing embeddings")
        if epazar_ids:
            epazar_workers = min(args.workers, max(1, len(epazar_ids) // 100))
            total_embedded += run_parallel(
                process_epazar_batch,
                epazar_ids,
                "epazar",
                epazar_workers
            )

    total_time = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info(f"DONE! Total: {total_embedded} embeddings in {total_time:.1f}s")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
