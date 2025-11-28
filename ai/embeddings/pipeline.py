"""
Embeddings Pipeline - Auto-trigger embedding generation after scraping

Features:
- Automatic trigger after scraping completes
- Process only new documents without embeddings
- Batch processing for efficiency
- Error handling and retry logic
- Integration with scraper pipeline
"""
import os
import sys
import logging
import asyncio
import asyncpg
from typing import List, Dict, Optional
from datetime import datetime

# Load environment variables from .env file
from dotenv import load_dotenv
# Try multiple .env locations
env_paths = [
    os.path.join(os.path.dirname(__file__), '../../.env'),
    os.path.join(os.path.dirname(__file__), '../../../.env'),
    '/home/ubuntu/nabavkidata/.env',
]
for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from embeddings import EmbeddingsPipeline

logger = logging.getLogger(__name__)


class AutoEmbeddingPipeline:
    """
    Automatically generate embeddings for new documents

    Integrates with scraper to process documents after scraping
    """

    def __init__(self, database_url: Optional[str] = None):
        database_url = database_url or os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL not set")

        # Convert SQLAlchemy URL format to asyncpg format
        # asyncpg doesn't understand postgresql+asyncpg://
        self.database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

        self.embeddings_pipeline = EmbeddingsPipeline(database_url=database_url)
        self.conn = None

    async def connect(self):
        """Establish database connection"""
        if not self.conn:
            self.conn = await asyncpg.connect(self.database_url)
            logger.info("Connected to database")

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info("Database connection closed")

    async def get_documents_without_embeddings(
        self,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get documents that need embeddings

        Args:
            limit: Maximum number of documents to retrieve

        Returns:
            List of document records
        """
        query = """
            SELECT
                d.doc_id,
                d.tender_id,
                d.content_text,
                d.file_name,
                t.title as tender_title,
                t.category as tender_category
            FROM documents d
            JOIN tenders t ON d.tender_id = t.tender_id
            WHERE d.extraction_status = 'success'
            AND d.content_text IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id
            )
            ORDER BY d.uploaded_at DESC NULLS LAST
        """

        if limit:
            query += f" LIMIT {limit}"

        rows = await self.conn.fetch(query)

        documents = [
            {
                'doc_id': row['doc_id'],
                'tender_id': row['tender_id'],
                'text': row['content_text'],
                'metadata': {
                    'file_name': row['file_name'],
                    'tender_title': row['tender_title'],
                    'tender_category': row['tender_category']
                }
            }
            for row in rows
        ]

        logger.info(f"Found {len(documents)} documents without embeddings")
        return documents

    async def get_recent_documents(
        self,
        since: datetime,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get documents created since a specific time

        Args:
            since: Timestamp to filter from
            limit: Maximum number of documents

        Returns:
            List of document records
        """
        query = """
            SELECT
                d.doc_id,
                d.tender_id,
                d.content_text,
                d.file_name,
                t.title as tender_title,
                t.category as tender_category
            FROM documents d
            JOIN tenders t ON d.tender_id = t.tender_id
            WHERE d.extraction_status = 'success'
            AND d.content_text IS NOT NULL
            AND d.uploaded_at >= $1
            AND NOT EXISTS (
                SELECT 1 FROM embeddings e WHERE e.doc_id = d.doc_id
            )
            ORDER BY d.uploaded_at DESC NULLS LAST
        """

        params = [since]
        if limit:
            query += f" LIMIT ${len(params) + 1}"
            params.append(limit)

        rows = await self.conn.fetch(query, *params)

        documents = [
            {
                'doc_id': row['doc_id'],
                'tender_id': row['tender_id'],
                'text': row['content_text'],
                'metadata': {
                    'file_name': row['file_name'],
                    'tender_title': row['tender_title'],
                    'tender_category': row['tender_category']
                }
            }
            for row in rows
        ]

        logger.info(
            f"Found {len(documents)} documents created since {since}"
        )
        return documents

    async def process_pending_documents(
        self,
        batch_size: int = 10,
        max_documents: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Process all documents that need embeddings

        Args:
            batch_size: Process documents in batches
            max_documents: Maximum total documents to process

        Returns:
            Statistics: {total_processed, total_embeddings, errors}
        """
        logger.info("Starting auto-embedding pipeline...")

        await self.connect()

        try:
            # Get documents without embeddings
            documents = await self.get_documents_without_embeddings(
                limit=max_documents
            )

            if not documents:
                logger.info("No documents to process")
                return {
                    'total_processed': 0,
                    'total_embeddings': 0,
                    'errors': 0
                }

            total_embeddings = 0
            errors = 0

            # Process in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]

                logger.info(
                    f"Processing batch {i // batch_size + 1} "
                    f"({len(batch)} documents)"
                )

                # Process batch
                batch_results = await self.embeddings_pipeline.process_documents_batch(
                    batch
                )

                # Count embeddings
                for doc_id, embed_ids in batch_results.items():
                    if embed_ids:
                        total_embeddings += len(embed_ids)
                    else:
                        errors += 1
                        logger.warning(f"Failed to embed document: {doc_id}")

            logger.info(
                f"✓ Auto-embedding complete: {len(documents)} documents, "
                f"{total_embeddings} embeddings, {errors} errors"
            )

            return {
                'total_processed': len(documents),
                'total_embeddings': total_embeddings,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"Auto-embedding pipeline failed: {e}")
            raise

        finally:
            await self.close()

    async def process_after_scrape(
        self,
        job_id: str,
        batch_size: int = 10
    ) -> Dict[str, int]:
        """
        Process documents after a scraping job completes

        Args:
            job_id: Scraping job ID
            batch_size: Documents per batch

        Returns:
            Processing statistics
        """
        logger.info(f"Processing embeddings after scrape job: {job_id}")

        await self.connect()

        try:
            # Get scraping job details
            job = await self.conn.fetchrow("""
                SELECT started_at, completed_at
                FROM scraping_jobs
                WHERE job_id = $1
            """, job_id)

            if not job:
                raise ValueError(f"Scraping job not found: {job_id}")

            # Get documents created during this job
            documents = await self.get_recent_documents(
                since=job['started_at']
            )

            if not documents:
                logger.info("No new documents to process")
                return {
                    'total_processed': 0,
                    'total_embeddings': 0,
                    'errors': 0
                }

            await self.close()  # Close before processing

            # Process documents
            return await self.process_pending_documents(
                batch_size=batch_size,
                max_documents=len(documents)
            )

        except Exception as e:
            logger.error(f"Post-scrape embedding failed: {e}")
            raise


async def trigger_auto_embeddings(
    batch_size: int = 10,
    max_documents: Optional[int] = None
) -> Dict[str, int]:
    """
    Convenience function to trigger auto-embedding pipeline

    Usage:
        stats = await trigger_auto_embeddings(batch_size=20, max_documents=100)
        print(f"Processed {stats['total_processed']} documents")

    Args:
        batch_size: Documents per batch
        max_documents: Maximum documents to process

    Returns:
        Processing statistics
    """
    pipeline = AutoEmbeddingPipeline()
    return await pipeline.process_pending_documents(
        batch_size=batch_size,
        max_documents=max_documents
    )


async def trigger_after_scrape(job_id: str) -> Dict[str, int]:
    """
    Trigger embeddings after scraping job

    Usage:
        stats = await trigger_after_scrape('550e8400-e29b-41d4-a716-446655440000')

    Args:
        job_id: Scraping job ID

    Returns:
        Processing statistics
    """
    pipeline = AutoEmbeddingPipeline()
    return await pipeline.process_after_scrape(job_id)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Auto-embedding pipeline for tender documents'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Documents per batch'
    )
    parser.add_argument(
        '--max-documents',
        type=int,
        help='Maximum documents to process'
    )
    parser.add_argument(
        '--job-id',
        type=str,
        help='Scraping job ID to process'
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )

    # Run pipeline
    if args.job_id:
        logger.info(f"Triggering embeddings for job: {args.job_id}")
        stats = asyncio.run(trigger_after_scrape(args.job_id))
    else:
        logger.info("Triggering auto-embeddings for pending documents")
        stats = asyncio.run(
            trigger_auto_embeddings(
                batch_size=args.batch_size,
                max_documents=args.max_documents
            )
        )

    print("\n" + "=" * 60)
    print("AUTO-EMBEDDING PIPELINE COMPLETED")
    print("=" * 60)
    print(f"Documents processed: {stats['total_processed']}")
    print(f"Embeddings created: {stats['total_embeddings']}")
    print(f"Errors: {stats['errors']}")
    print("=" * 60)
