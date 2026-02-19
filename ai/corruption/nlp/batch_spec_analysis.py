#!/usr/bin/env python3
"""
Batch Specification Analysis for Cron

Processes tender documents that have extracted text but have not yet been
analyzed for specification rigging patterns. Stores results in the
specification_analysis table.

Usage:
    # Process up to 500 documents
    python3 batch_spec_analysis.py --limit 500

    # Only analyze high-value tenders (estimated value > 1M MKD)
    python3 batch_spec_analysis.py --limit 200 --high-value-only

    # Dry run (analyze but don't persist)
    python3 batch_spec_analysis.py --limit 10 --dry-run

Designed to run as a cron job:
    0 3 * * * cd /home/ubuntu/nabavkidata/ai/corruption/nlp && python3 batch_spec_analysis.py --limit 500 >> /var/log/nabavkidata/spec_analysis.log 2>&1

Author: nabavkidata.com
License: Proprietary
"""

import os
import sys
import json
import math
import asyncio
import logging
import argparse
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from spec_analyzer import SpecificationAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('batch_spec_analysis')


async def get_pool():
    """Get or create the database connection pool."""
    try:
        from db_pool import get_pool as _get_pool
        return await _get_pool()
    except ImportError:
        import asyncpg
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        dsn = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        return await asyncpg.create_pool(
            dsn,
            min_size=2,
            max_size=5,
            command_timeout=60,
        )


async def fetch_unanalyzed_documents(
    pool,
    limit: int = 500,
    high_value_only: bool = False,
) -> list:
    """
    Fetch documents with extracted text that haven't been analyzed yet.

    Args:
        pool: asyncpg connection pool.
        limit: Maximum documents to fetch.
        high_value_only: If True, only fetch documents for tenders with
            estimated value > 1,000,000 MKD.

    Returns:
        List of records with doc_id, tender_id, content_text, cpv_code.
    """
    high_value_clause = ""
    if high_value_only:
        high_value_clause = """
            AND t.estimated_value_mkd > 1000000
        """

    query = f"""
        SELECT
            d.doc_id,
            d.tender_id,
            d.content_text,
            t.cpv_code
        FROM documents d
        JOIN tenders t ON d.tender_id = t.tender_id
        WHERE d.extraction_status = 'success'
          AND d.content_text IS NOT NULL
          AND LENGTH(d.content_text) > 100
          AND NOT EXISTS (
              SELECT 1 FROM specification_analysis sa
              WHERE sa.doc_id = d.doc_id
          )
          {high_value_clause}
        ORDER BY t.publication_date DESC NULLS LAST
        LIMIT $1
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, limit)

    logger.info(f"Found {len(rows)} unanalyzed documents (limit={limit}, high_value_only={high_value_only})")
    return rows


async def store_analysis_result(pool, result: dict, doc_id) -> bool:
    """
    Store a single analysis result in the specification_analysis table.

    Args:
        pool: asyncpg connection pool.
        result: Analysis result dict from SpecificationAnalyzer.
        doc_id: The document ID (UUID).

    Returns:
        True if stored successfully, False otherwise.
    """
    query = """
        INSERT INTO specification_analysis (
            tender_id, doc_id, brand_names, brand_exclusivity_score,
            qualification_requirements, qualification_restrictiveness,
            complexity_score, vocabulary_richness, rigging_probability,
            risk_factors, analyzed_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        ON CONFLICT (tender_id, doc_id) DO UPDATE SET
            brand_names = EXCLUDED.brand_names,
            brand_exclusivity_score = EXCLUDED.brand_exclusivity_score,
            qualification_requirements = EXCLUDED.qualification_requirements,
            qualification_restrictiveness = EXCLUDED.qualification_restrictiveness,
            complexity_score = EXCLUDED.complexity_score,
            vocabulary_richness = EXCLUDED.vocabulary_richness,
            rigging_probability = EXCLUDED.rigging_probability,
            risk_factors = EXCLUDED.risk_factors,
            analyzed_at = NOW()
    """

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                query,
                result['tender_id'],
                doc_id,
                json.dumps(result['brand_names_detected']),
                result['brand_exclusivity_score'],
                json.dumps(result['qualification_requirements']),
                result['qualification_restrictiveness'],
                result['complexity_score'],
                result['vocabulary_richness'],
                result['rigging_probability'],
                json.dumps(result['risk_factors']),
            )
        return True
    except Exception as e:
        logger.error(f"Failed to store analysis for {result['tender_id']}: {e}")
        return False


async def run_batch(
    limit: int = 500,
    high_value_only: bool = False,
    dry_run: bool = False,
    batch_size: int = 50,
):
    """
    Main batch processing loop.

    Args:
        limit: Maximum total documents to process.
        high_value_only: Only analyze high-value tenders.
        dry_run: If True, analyze but don't store results.
        batch_size: Number of documents per batch (for memory management).
    """
    start_time = datetime.utcnow()
    logger.info(
        f"Starting batch specification analysis: limit={limit}, "
        f"high_value_only={high_value_only}, dry_run={dry_run}"
    )

    pool = await get_pool()

    # Verify the specification_analysis table exists
    try:
        async with pool.acquire() as conn:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'specification_analysis'
                )
            """)
            if not exists:
                logger.error(
                    "Table 'specification_analysis' does not exist. "
                    "Run migration 032_spec_analysis.sql first."
                )
                return
    except Exception as e:
        logger.error(f"Cannot check table existence: {e}")
        return

    # Fetch unanalyzed documents
    documents = await fetch_unanalyzed_documents(pool, limit, high_value_only)

    if not documents:
        logger.info("No unanalyzed documents found. Exiting.")
        return

    analyzer = SpecificationAnalyzer(use_gemini_fallback=True)

    total = len(documents)
    processed = 0
    stored = 0
    errors = 0
    high_risk_count = 0

    # Process in batches to manage memory
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = documents[batch_start:batch_end]
        batch_num = (batch_start // batch_size) + 1
        total_batches = math.ceil(total / batch_size)

        logger.info(
            f"Processing batch {batch_num}/{total_batches} "
            f"({batch_start + 1}-{batch_end} of {total})"
        )

        for row in batch:
            try:
                doc_id = row['doc_id']
                tender_id = row['tender_id']
                content_text = row['content_text']
                cpv_code = row.get('cpv_code')

                # Run analysis
                result = await analyzer.analyze_specification(
                    content_text=content_text,
                    tender_id=tender_id,
                    cpv_code=cpv_code,
                )

                processed += 1

                if result['rigging_probability'] > 0.5:
                    high_risk_count += 1
                    logger.info(
                        f"HIGH RISK: {tender_id} - rigging_probability={result['rigging_probability']:.3f}, "
                        f"brands={len(result['brand_names_detected'])}, "
                        f"risk_factors={len(result['risk_factors'])}"
                    )

                # Store result (unless dry run)
                if not dry_run:
                    success = await store_analysis_result(pool, result, doc_id)
                    if success:
                        stored += 1
                    else:
                        errors += 1
                else:
                    # In dry run, just log the result summary
                    logger.debug(
                        f"DRY RUN: {tender_id} - rigging={result['rigging_probability']:.3f}, "
                        f"brands={len(result['brand_names_detected'])}, "
                        f"quals={len(result['qualification_requirements'])}"
                    )

            except Exception as e:
                errors += 1
                logger.error(f"Error analyzing document {row.get('doc_id', '?')}: {e}")

        # Log progress after each batch
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        rate = processed / elapsed if elapsed > 0 else 0
        logger.info(
            f"Progress: {processed}/{total} processed, {stored} stored, "
            f"{errors} errors, {high_risk_count} high-risk, "
            f"{rate:.1f} docs/sec"
        )

    # Final summary
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(
        f"Batch complete: {processed} processed, {stored} stored, "
        f"{errors} errors, {high_risk_count} high-risk tenders, "
        f"elapsed={elapsed:.1f}s"
    )


def main():
    parser = argparse.ArgumentParser(
        description='Batch specification rigging analysis for tender documents'
    )
    parser.add_argument(
        '--limit', type=int, default=500,
        help='Maximum number of documents to process (default: 500)'
    )
    parser.add_argument(
        '--high-value-only', action='store_true',
        help='Only analyze tenders with estimated value > 1M MKD'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Analyze documents but do not store results'
    )
    parser.add_argument(
        '--batch-size', type=int, default=50,
        help='Documents per batch (default: 50)'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    asyncio.run(run_batch(
        limit=args.limit,
        high_value_only=args.high_value_only,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    ))


if __name__ == '__main__':
    main()
