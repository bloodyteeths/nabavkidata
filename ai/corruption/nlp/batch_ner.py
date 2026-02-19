#!/usr/bin/env python3
"""
Batch NER Processing Script

Processes tender documents in batches to extract named entities
(people, organizations, monetary amounts, dates, legal references, etc.)
and stores them in the entity_mentions table.

Usage:
    # Process 100 documents using regex only (fast, free)
    python -m ai.corruption.nlp.batch_ner --limit 100

    # Process with LLM for better person/org extraction
    python -m ai.corruption.nlp.batch_ner --limit 50 --use-llm

    # Process specific tender
    python -m ai.corruption.nlp.batch_ner --tender-id "12345/2024"

    # Reprocess (overwrite existing entities)
    python -m ai.corruption.nlp.batch_ner --limit 100 --reprocess

    # Filter by document type
    python -m ai.corruption.nlp.batch_ner --limit 100 --doc-type "award_decision"

    # Run from project root on server:
    cd /home/ubuntu/nabavkidata
    python -m ai.corruption.nlp.batch_ner --limit 1000

Author: nabavkidata.com
License: Proprietary
"""

import os
import sys
import time
import asyncio
import argparse
import logging
from typing import List, Optional, Tuple

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Also add backend to path for db_pool import
backend_root = os.path.join(project_root, 'backend')
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from ai.corruption.nlp.ner_extractor import MacedonianNERExtractor, ExtractionResult
from ai.corruption.nlp.entity_store import EntityStore

logger = logging.getLogger(__name__)


# ============================================================================
# BATCH PROCESSOR
# ============================================================================

class BatchNERProcessor:
    """
    Processes documents in batches for NER extraction.

    Fetches documents from the database, runs entity extraction,
    and stores results. Tracks progress and reports statistics.
    """

    def __init__(
        self,
        batch_size: int = 20,
        use_llm: bool = False,
        reprocess: bool = False,
    ):
        self.batch_size = batch_size
        self.use_llm = use_llm
        self.reprocess = reprocess
        self.extractor = MacedonianNERExtractor()
        self.store = EntityStore()

        # Statistics
        self.stats = {
            'total_docs': 0,
            'processed_docs': 0,
            'skipped_docs': 0,
            'failed_docs': 0,
            'total_entities': 0,
            'by_type': {},
            'start_time': None,
            'end_time': None,
        }

    async def get_pool(self):
        """Get asyncpg pool - import here to avoid circular imports."""
        try:
            from db_pool import get_asyncpg_pool
            return await get_asyncpg_pool()
        except ImportError:
            # Try backend path
            sys.path.insert(0, os.path.join(project_root, 'backend'))
            from db_pool import get_asyncpg_pool
            return await get_asyncpg_pool()

    async def fetch_documents(
        self,
        pool,
        limit: int = 100,
        tender_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        offset: int = 0,
    ) -> list:
        """
        Fetch documents that need NER processing.

        Returns documents with extracted text that haven't been processed yet
        (unless reprocess=True).
        """
        async with pool.acquire() as conn:
            query = """
                SELECT d.doc_id, d.tender_id, d.doc_type, d.content_text,
                       d.file_name, LENGTH(d.content_text) as text_length
                FROM documents d
                WHERE d.content_text IS NOT NULL
                  AND d.extraction_status = 'success'
                  AND LENGTH(d.content_text) > 50
            """
            params = []
            param_count = 0

            if not self.reprocess:
                extraction_method = 'both' if self.use_llm else 'regex'
                param_count += 1
                query += f"""
                    AND NOT EXISTS (
                        SELECT 1 FROM ner_processing_log npl
                        WHERE npl.doc_id = d.doc_id
                          AND npl.extraction_method = ${param_count}
                    )
                """
                params.append(extraction_method)

            if tender_id:
                param_count += 1
                query += f" AND d.tender_id = ${param_count}"
                params.append(tender_id)

            if doc_type:
                param_count += 1
                query += f" AND d.doc_type = ${param_count}"
                params.append(doc_type)

            query += " ORDER BY d.uploaded_at DESC"
            query += f" LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
            params.extend([limit, offset])

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def count_pending_documents(
        self,
        pool,
        tender_id: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> int:
        """Count documents that still need NER processing."""
        async with pool.acquire() as conn:
            query = """
                SELECT COUNT(*)
                FROM documents d
                WHERE d.content_text IS NOT NULL
                  AND d.extraction_status = 'success'
                  AND LENGTH(d.content_text) > 50
            """
            params = []
            param_count = 0

            if not self.reprocess:
                extraction_method = 'both' if self.use_llm else 'regex'
                param_count += 1
                query += f"""
                    AND NOT EXISTS (
                        SELECT 1 FROM ner_processing_log npl
                        WHERE npl.doc_id = d.doc_id
                          AND npl.extraction_method = ${param_count}
                    )
                """
                params.append(extraction_method)

            if tender_id:
                param_count += 1
                query += f" AND d.tender_id = ${param_count}"
                params.append(tender_id)

            if doc_type:
                param_count += 1
                query += f" AND d.doc_type = ${param_count}"
                params.append(doc_type)

            return await conn.fetchval(query, *params) or 0

    async def process_document(
        self,
        pool,
        doc: dict,
    ) -> Tuple[int, Optional[str]]:
        """
        Process a single document for NER extraction.

        Returns:
            Tuple of (entity_count, error_message_or_none)
        """
        doc_id = doc['doc_id']
        tender_id = doc['tender_id']
        text = doc['content_text']

        start_time = time.time()

        try:
            # Extract entities
            result = await self.extractor.extract_entities(
                text,
                use_llm=self.use_llm,
            )

            if result.error:
                logger.warning(
                    f"Extraction warning for doc {doc_id}: {result.error}"
                )

            if not result.entities:
                # No entities found - still log as processed
                processing_time_ms = int((time.time() - start_time) * 1000)
                async with pool.acquire() as conn:
                    try:
                        extraction_method = 'both' if self.use_llm else 'regex'
                        await conn.execute("""
                            INSERT INTO ner_processing_log (
                                doc_id, tender_id, extraction_method,
                                entity_count, processing_time_ms
                            ) VALUES ($1, $2, $3, 0, $4)
                            ON CONFLICT (doc_id, extraction_method) DO UPDATE SET
                                entity_count = 0,
                                processing_time_ms = $4,
                                processed_at = NOW()
                        """, doc_id, tender_id, extraction_method, processing_time_ms)
                    except Exception as e:
                        logger.warning(f"Failed to log empty NER result: {e}")
                return 0, None

            # Delete existing entities if reprocessing
            if self.reprocess:
                await self.store.delete_entities_for_doc(pool, doc_id)

            # Store entities
            processing_time_ms = int((time.time() - start_time) * 1000)
            count = await self.store.store_entities(
                pool, tender_id, doc_id, result.entities,
                processing_time_ms=processing_time_ms,
            )

            # Update stats
            for entity in result.entities:
                self.stats['by_type'][entity.type] = (
                    self.stats['by_type'].get(entity.type, 0) + 1
                )

            return count, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to process doc {doc_id}: {error_msg}")

            # Log the failure
            try:
                async with pool.acquire() as conn:
                    extraction_method = 'both' if self.use_llm else 'regex'
                    await conn.execute("""
                        INSERT INTO ner_processing_log (
                            doc_id, tender_id, extraction_method,
                            entity_count, processing_time_ms, error
                        ) VALUES ($1, $2, $3, 0, 0, $4)
                        ON CONFLICT (doc_id, extraction_method) DO UPDATE SET
                            error = $4,
                            processed_at = NOW()
                    """, doc_id, tender_id, extraction_method, error_msg[:500])
            except Exception:
                pass

            return 0, error_msg

    async def run(
        self,
        limit: int = 100,
        tender_id: Optional[str] = None,
        doc_type: Optional[str] = None,
    ):
        """
        Run batch NER processing.

        Args:
            limit: Maximum documents to process
            tender_id: Optional - process only this tender's documents
            doc_type: Optional - filter by document type
        """
        self.stats['start_time'] = time.time()

        pool = await self.get_pool()

        # Count pending
        pending = await self.count_pending_documents(pool, tender_id, doc_type)
        actual_limit = min(limit, pending)

        logger.info(
            f"NER Batch Processing: {pending} documents pending, "
            f"processing up to {actual_limit} "
            f"(batch_size={self.batch_size}, use_llm={self.use_llm})"
        )

        if actual_limit == 0:
            logger.info("No documents to process. Exiting.")
            return self.stats

        processed = 0
        offset = 0

        while processed < actual_limit:
            batch_limit = min(self.batch_size, actual_limit - processed)

            # Fetch batch
            docs = await self.fetch_documents(
                pool, limit=batch_limit,
                tender_id=tender_id, doc_type=doc_type,
            )

            if not docs:
                logger.info("No more documents to process.")
                break

            self.stats['total_docs'] += len(docs)

            # Process each document
            for doc in docs:
                count, error = await self.process_document(pool, doc)

                if error:
                    self.stats['failed_docs'] += 1
                elif count == 0:
                    self.stats['skipped_docs'] += 1
                else:
                    self.stats['processed_docs'] += 1
                    self.stats['total_entities'] += count

                processed += 1

                # Progress log every 10 docs
                if processed % 10 == 0:
                    elapsed = time.time() - self.stats['start_time']
                    rate = processed / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Progress: {processed}/{actual_limit} docs "
                        f"({rate:.1f} docs/sec), "
                        f"{self.stats['total_entities']} entities extracted"
                    )

            # Small delay between batches to avoid overwhelming the DB
            if self.use_llm:
                await asyncio.sleep(1.0)  # Rate limit for API
            else:
                await asyncio.sleep(0.1)

        self.stats['end_time'] = time.time()
        elapsed = self.stats['end_time'] - self.stats['start_time']

        logger.info(
            f"\n{'='*60}\n"
            f"NER Batch Processing Complete\n"
            f"{'='*60}\n"
            f"Time: {elapsed:.1f}s\n"
            f"Documents: {self.stats['processed_docs']} processed, "
            f"{self.stats['skipped_docs']} skipped (no entities), "
            f"{self.stats['failed_docs']} failed\n"
            f"Total entities: {self.stats['total_entities']}\n"
            f"By type: {self.stats['by_type']}\n"
            f"{'='*60}"
        )

        return self.stats


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='Batch NER processing for tender documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process 100 documents (regex only)
  python -m ai.corruption.nlp.batch_ner --limit 100

  # Process with Gemini LLM for better name extraction
  python -m ai.corruption.nlp.batch_ner --limit 50 --use-llm

  # Process specific tender
  python -m ai.corruption.nlp.batch_ner --tender-id "12345/2024"

  # Reprocess documents (overwrite existing entities)
  python -m ai.corruption.nlp.batch_ner --limit 100 --reprocess

  # Filter by document type
  python -m ai.corruption.nlp.batch_ner --doc-type "award_decision"
        """
    )

    parser.add_argument(
        '--limit', type=int, default=100,
        help='Maximum number of documents to process (default: 100)'
    )
    parser.add_argument(
        '--batch-size', type=int, default=20,
        help='Documents per batch (default: 20)'
    )
    parser.add_argument(
        '--tender-id', type=str, default=None,
        help='Process only documents for this tender ID'
    )
    parser.add_argument(
        '--doc-type', type=str, default=None,
        help='Filter by document type (e.g., award_decision, tender_docs)'
    )
    parser.add_argument(
        '--use-llm', action='store_true',
        help='Use Gemini API for person/org extraction (slower, costs credits)'
    )
    parser.add_argument(
        '--reprocess', action='store_true',
        help='Reprocess documents that were already processed'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


async def main():
    args = parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Suppress noisy loggers
    logging.getLogger('asyncpg').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)

    logger.info(
        f"Starting NER batch processing: "
        f"limit={args.limit}, batch_size={args.batch_size}, "
        f"use_llm={args.use_llm}, reprocess={args.reprocess}"
    )

    processor = BatchNERProcessor(
        batch_size=args.batch_size,
        use_llm=args.use_llm,
        reprocess=args.reprocess,
    )

    stats = await processor.run(
        limit=args.limit,
        tender_id=args.tender_id,
        doc_type=args.doc_type,
    )

    # Print summary to stdout
    print(f"\nProcessed: {stats['processed_docs']} documents")
    print(f"Entities: {stats['total_entities']}")
    print(f"By type: {stats['by_type']}")
    if stats['failed_docs'] > 0:
        print(f"Failed: {stats['failed_docs']} documents")

    return stats


if __name__ == '__main__':
    asyncio.run(main())
