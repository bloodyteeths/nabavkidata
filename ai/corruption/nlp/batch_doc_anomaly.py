"""
Batch Document Anomaly Detection

Runs as a cron job (daily) to detect document anomalies across tenders
and store results in document_anomalies and tender_doc_completeness tables.

Processes tenders that have documents, checks completeness, timing, and
file anomalies, then stores findings for fast API access.

Usage:
    # Process all tenders with documents (default batch size: 100)
    python batch_doc_anomaly.py

    # Limit to N tenders
    python batch_doc_anomaly.py --limit 500

    # Only process a specific institution
    python batch_doc_anomaly.py --institution "Министерство за финансии"

    # Set batch size
    python batch_doc_anomaly.py --batch-size 50

    # Only process tenders not yet analyzed
    python batch_doc_anomaly.py --new-only

    # Dry run (analyze but don't store)
    python batch_doc_anomaly.py --dry-run

Author: nabavkidata.com
License: Proprietary
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from typing import Dict, List, Optional

import asyncpg

# Load .env from multiple possible locations
try:
    from dotenv import load_dotenv
    env_paths = [
        os.path.join(os.path.dirname(__file__), "../../../.env"),
        os.path.join(os.path.dirname(__file__), "../../../../.env"),
        "/home/ubuntu/nabavkidata/.env",
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            break
except ImportError:
    pass  # dotenv not required if env vars are already set

logger = logging.getLogger(__name__)


class BatchDocAnomalyProcessor:
    """
    Batch processor for document anomaly detection.

    Iterates over tenders that have documents, runs the DocumentAnomalyDetector,
    and stores results in database tables.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        batch_size: int = 100,
    ):
        """
        Args:
            database_url: PostgreSQL connection string
            batch_size: Number of tenders to process per batch
        """
        self.database_url = database_url or os.getenv("DATABASE_URL", "")
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")
        # Strip SQLAlchemy dialect prefix if present
        self.database_url = self.database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        self.batch_size = batch_size
        self.pool: Optional[asyncpg.Pool] = None

        # Stats tracking
        self.stats = {
            'total_processed': 0,
            'total_anomalies_found': 0,
            'total_high_risk': 0,
            'errors': 0,
            'skipped': 0,
        }

    async def initialize(self):
        """Create connection pool."""
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=5,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
        logger.info("Database connection pool created")

    async def cleanup(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    async def ensure_tables(self):
        """Create tables if they don't exist (idempotent)."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS document_anomalies (
                    anomaly_id SERIAL PRIMARY KEY,
                    tender_id TEXT NOT NULL,
                    doc_id UUID REFERENCES documents(doc_id) ON DELETE SET NULL,
                    anomaly_type TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'medium',
                    description TEXT NOT NULL,
                    evidence JSONB DEFAULT '{}',
                    risk_contribution FLOAT DEFAULT 0,
                    detected_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tender_doc_completeness (
                    tender_id TEXT PRIMARY KEY,
                    total_documents INTEGER DEFAULT 0,
                    expected_documents INTEGER DEFAULT 0,
                    completeness_score FLOAT DEFAULT 0,
                    anomaly_count INTEGER DEFAULT 0,
                    timing_anomaly_score FLOAT DEFAULT 0,
                    overall_risk_contribution FLOAT DEFAULT 0,
                    computed_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Create indexes if not exists
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_anomaly_tender
                    ON document_anomalies(tender_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_anomaly_type
                    ON document_anomalies(anomaly_type)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_anomaly_severity
                    ON document_anomalies(severity)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_completeness_risk
                    ON tender_doc_completeness(overall_risk_contribution DESC)
            """)
            logger.info("Tables and indexes verified")

    async def get_tender_ids_to_process(
        self,
        limit: Optional[int] = None,
        institution: Optional[str] = None,
        new_only: bool = False,
    ) -> List[str]:
        """
        Get list of tender IDs that have documents and need processing.

        Args:
            limit: Maximum number of tenders to process
            institution: Filter by procuring entity name
            new_only: Only process tenders not yet in tender_doc_completeness

        Returns:
            List of tender_id strings
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT DISTINCT d.tender_id
                FROM documents d
                JOIN tenders t ON d.tender_id = t.tender_id
                WHERE 1=1
            """
            params = []
            param_count = 0

            if institution:
                param_count += 1
                query += f" AND t.procuring_entity ILIKE '%' || ${param_count} || '%'"
                params.append(institution)

            if new_only:
                query += """
                    AND d.tender_id NOT IN (
                        SELECT tender_id FROM tender_doc_completeness
                    )
                """

            query += " ORDER BY d.tender_id DESC"

            if limit:
                param_count += 1
                query += f" LIMIT ${param_count}"
                params.append(limit)

            rows = await conn.fetch(query, *params)
            return [r['tender_id'] for r in rows]

    async def process_tender(
        self,
        tender_id: str,
        dry_run: bool = False,
    ) -> Optional[dict]:
        """
        Process a single tender for document anomalies.

        Args:
            tender_id: The tender ID to process
            dry_run: If True, analyze but don't store results

        Returns:
            Analysis result dict, or None on error
        """
        from .doc_anomaly import DocumentAnomalyDetector

        detector = DocumentAnomalyDetector()

        try:
            result = await detector.analyze_tender_documents(self.pool, tender_id)

            if not dry_run:
                await self._store_results(tender_id, result)

            return result

        except Exception as e:
            logger.error(f"Error processing tender {tender_id}: {e}")
            self.stats['errors'] += 1
            return None

    async def _store_results(self, tender_id: str, result: dict):
        """
        Store anomaly detection results in the database.

        Clears previous anomalies for this tender before inserting new ones
        to ensure idempotent runs.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Delete previous anomalies for this tender
                await conn.execute(
                    "DELETE FROM document_anomalies WHERE tender_id = $1",
                    tender_id,
                )

                # Insert new anomalies
                anomalies = result.get('anomalies', [])
                for anomaly in anomalies:
                    # Extract doc_id from evidence if available
                    evidence = anomaly.get('evidence', {})
                    doc_id_str = evidence.get('doc_id')

                    await conn.execute("""
                        INSERT INTO document_anomalies
                            (tender_id, doc_id, anomaly_type, severity,
                             description, evidence, risk_contribution)
                        VALUES ($1, $2::uuid, $3, $4, $5, $6::jsonb, $7)
                    """,
                        tender_id,
                        doc_id_str,  # May be None
                        anomaly.get('type', 'unknown'),
                        anomaly.get('severity', 'medium'),
                        anomaly.get('description', ''),
                        json.dumps(evidence),
                        result.get('overall_risk_contribution', 0),
                    )

                # Get expected document count from completeness check
                completeness = await self._get_expected_doc_count(conn, tender_id)

                # Upsert tender_doc_completeness
                await conn.execute("""
                    INSERT INTO tender_doc_completeness
                        (tender_id, total_documents, expected_documents,
                         completeness_score, anomaly_count,
                         timing_anomaly_score, overall_risk_contribution,
                         computed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    ON CONFLICT (tender_id) DO UPDATE SET
                        total_documents = EXCLUDED.total_documents,
                        expected_documents = EXCLUDED.expected_documents,
                        completeness_score = EXCLUDED.completeness_score,
                        anomaly_count = EXCLUDED.anomaly_count,
                        timing_anomaly_score = EXCLUDED.timing_anomaly_score,
                        overall_risk_contribution = EXCLUDED.overall_risk_contribution,
                        computed_at = NOW()
                """,
                    tender_id,
                    result.get('total_documents', 0),
                    completeness,
                    result.get('completeness_score', 0),
                    result.get('anomaly_count', 0),
                    result.get('timing_anomaly_score', 0),
                    result.get('overall_risk_contribution', 0),
                )

    async def _get_expected_doc_count(self, conn, tender_id: str) -> int:
        """Get expected document count based on procedure type."""
        from .doc_anomaly import DocumentAnomalyDetector
        detector = DocumentAnomalyDetector()

        proc_type = await conn.fetchval(
            "SELECT procedure_type FROM tenders WHERE tender_id = $1",
            tender_id,
        )
        normalized = detector._normalize_procedure_type(proc_type)
        expected = detector.REQUIRED_DOCS.get(normalized, detector.REQUIRED_DOCS.get('open', []))
        return len(expected)

    async def run(
        self,
        limit: Optional[int] = None,
        institution: Optional[str] = None,
        new_only: bool = False,
        dry_run: bool = False,
    ):
        """
        Main entry point: process all applicable tenders in batches.

        Args:
            limit: Maximum number of tenders to process
            institution: Filter by institution name
            new_only: Only process tenders not yet analyzed
            dry_run: Analyze but don't store results
        """
        start_time = time.time()

        logger.info("Starting batch document anomaly detection")
        logger.info(
            f"  limit={limit}, institution={institution}, "
            f"new_only={new_only}, dry_run={dry_run}"
        )

        await self.initialize()

        if not dry_run:
            await self.ensure_tables()

        # Get tender IDs to process
        tender_ids = await self.get_tender_ids_to_process(
            limit=limit,
            institution=institution,
            new_only=new_only,
        )

        total = len(tender_ids)
        logger.info(f"Found {total} tenders to process")

        if total == 0:
            logger.info("No tenders to process, exiting")
            await self.cleanup()
            return

        # Process in batches
        for batch_start in range(0, total, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total)
            batch = tender_ids[batch_start:batch_end]

            logger.info(
                f"Processing batch {batch_start // self.batch_size + 1}: "
                f"tenders {batch_start + 1}-{batch_end} of {total}"
            )

            for tender_id in batch:
                result = await self.process_tender(tender_id, dry_run=dry_run)

                if result:
                    self.stats['total_processed'] += 1
                    anomaly_count = result.get('anomaly_count', 0)
                    self.stats['total_anomalies_found'] += anomaly_count

                    if result.get('overall_risk_contribution', 0) >= 50:
                        self.stats['total_high_risk'] += 1

                    if self.stats['total_processed'] % 50 == 0:
                        elapsed = time.time() - start_time
                        rate = self.stats['total_processed'] / elapsed
                        logger.info(
                            f"  Progress: {self.stats['total_processed']}/{total} "
                            f"({rate:.1f} tenders/sec), "
                            f"anomalies found: {self.stats['total_anomalies_found']}"
                        )

        elapsed = time.time() - start_time
        logger.info(f"Batch processing complete in {elapsed:.1f}s")
        logger.info(f"  Processed: {self.stats['total_processed']}")
        logger.info(f"  Anomalies found: {self.stats['total_anomalies_found']}")
        logger.info(f"  High risk tenders: {self.stats['total_high_risk']}")
        logger.info(f"  Errors: {self.stats['errors']}")

        await self.cleanup()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Batch document anomaly detection for procurement tenders"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of tenders to process"
    )
    parser.add_argument(
        "--institution", type=str, default=None,
        help="Filter by procuring entity name"
    )
    parser.add_argument(
        "--batch-size", type=int, default=100,
        help="Number of tenders per batch (default: 100)"
    )
    parser.add_argument(
        "--new-only", action="store_true",
        help="Only process tenders not yet in tender_doc_completeness"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Analyze but don't store results in database"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    processor = BatchDocAnomalyProcessor(
        batch_size=args.batch_size,
    )

    asyncio.run(
        processor.run(
            limit=args.limit,
            institution=args.institution,
            new_only=args.new_only,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
