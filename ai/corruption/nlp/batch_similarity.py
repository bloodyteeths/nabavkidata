"""
Batch Specification Similarity Computation

Runs as a cron job (weekly) to pre-compute specification similarity pairs
and institution reuse statistics. Results are stored in the database
for fast API queries.

Usage:
    # Process all tenders with embeddings (default: top-5 most similar per tender)
    python batch_similarity.py

    # Limit to specific number of tenders
    python batch_similarity.py --limit 1000

    # Only process a specific institution
    python batch_similarity.py --institution "Министерство за финансии"

    # Adjust minimum similarity threshold
    python batch_similarity.py --min-similarity 0.90

    # Dry run (compute but don't store)
    python batch_similarity.py --dry-run

Author: nabavkidata.com
License: Proprietary
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from typing import Dict, List, Optional

import asyncpg
from dotenv import load_dotenv

# Load .env from multiple possible locations
env_paths = [
    os.path.join(os.path.dirname(__file__), "../../../.env"),
    os.path.join(os.path.dirname(__file__), "../../../../.env"),
    "/home/ubuntu/nabavkidata/.env",
]
for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

logger = logging.getLogger(__name__)


class BatchSimilarityProcessor:
    """
    Batch processor for computing specification similarity pairs
    and institution reuse statistics.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        min_similarity: float = 0.85,
        top_k: int = 5,
        batch_size: int = 100,
    ):
        """
        Args:
            database_url: PostgreSQL connection string
            min_similarity: Minimum cosine similarity to store (0-1)
            top_k: Number of most similar tenders to find per tender
            batch_size: Number of tenders to process per batch
        """
        self.database_url = database_url or os.getenv("DATABASE_URL", "")
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")
        # Strip SQLAlchemy dialect prefix if present
        self.database_url = self.database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        )

        self.min_similarity = min_similarity
        self.top_k = top_k
        self.batch_size = batch_size
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create connection pool."""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=4,
                max_inactive_connection_lifetime=300,
                command_timeout=120,
            )
            logger.info("Database connection pool created")

    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")

    async def ensure_tables_exist(self):
        """Create the spec_similarity_pairs and institution_spec_reuse tables if missing."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS spec_similarity_pairs (
                    pair_id SERIAL PRIMARY KEY,
                    tender_id_1 TEXT NOT NULL,
                    tender_id_2 TEXT NOT NULL,
                    similarity_score FLOAT NOT NULL,
                    same_institution BOOLEAN DEFAULT FALSE,
                    same_winner BOOLEAN DEFAULT FALSE,
                    cross_institution BOOLEAN DEFAULT FALSE,
                    copied_fraction FLOAT,
                    detection_type TEXT,
                    detected_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(tender_id_1, tender_id_2)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS institution_spec_reuse (
                    institution TEXT PRIMARY KEY,
                    total_specs INTEGER DEFAULT 0,
                    unique_specs INTEGER DEFAULT 0,
                    reuse_rate FLOAT DEFAULT 0,
                    top_winner TEXT,
                    top_winner_pct FLOAT DEFAULT 0,
                    computed_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
            logger.info("Tables verified/created")

    async def get_tenders_with_embeddings(
        self,
        limit: Optional[int] = None,
        institution: Optional[str] = None,
    ) -> List[str]:
        """
        Get list of tender IDs that have embeddings.

        Args:
            limit: Maximum number of tenders
            institution: Filter by institution name

        Returns:
            List of tender IDs
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT DISTINCT e.tender_id
                FROM embeddings e
                JOIN tenders t ON e.tender_id = t.tender_id
            """
            params = []
            param_count = 0

            if institution:
                param_count += 1
                query += f" WHERE t.procuring_entity = ${param_count}"
                params.append(institution)

            query += " ORDER BY e.tender_id"

            if limit:
                param_count += 1
                query += f" LIMIT ${param_count}"
                params.append(limit)

            rows = await conn.fetch(query, *params)
            tender_ids = [r["tender_id"] for r in rows]
            logger.info(f"Found {len(tender_ids)} tenders with embeddings")
            return tender_ids

    async def compute_similarities_for_tender(
        self, tender_id: str
    ) -> List[Dict]:
        """
        Find top-K most similar tenders for a given tender using pgvector.

        Args:
            tender_id: The tender to find similarities for

        Returns:
            List of similarity dicts ready for database insertion
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH target_vector AS (
                    SELECT AVG(vector) as avg_vec
                    FROM embeddings
                    WHERE tender_id = $1
                ),
                target_info AS (
                    SELECT procuring_entity, winner
                    FROM tenders
                    WHERE tender_id = $1
                )
                SELECT
                    e2.tender_id as similar_tender_id,
                    1 - (AVG(e2.vector) <=> (SELECT avg_vec FROM target_vector)) as similarity_score,
                    t2.procuring_entity,
                    t2.winner,
                    (SELECT procuring_entity FROM target_info) as source_institution,
                    (SELECT winner FROM target_info) as source_winner
                FROM embeddings e2
                JOIN tenders t2 ON e2.tender_id = t2.tender_id
                WHERE e2.tender_id != $1
                GROUP BY e2.tender_id, t2.procuring_entity, t2.winner
                HAVING 1 - (AVG(e2.vector) <=> (SELECT avg_vec FROM target_vector)) >= $2
                ORDER BY similarity_score DESC
                LIMIT $3
                """,
                tender_id,
                self.min_similarity,
                self.top_k,
            )

            results = []
            for row in rows:
                sim_score = float(row["similarity_score"])
                same_inst = (
                    row["procuring_entity"] == row["source_institution"]
                    if row["source_institution"]
                    else False
                )
                same_winner = (
                    row["winner"] is not None
                    and row["source_winner"] is not None
                    and row["winner"] == row["source_winner"]
                )
                cross_inst = not same_inst

                # Classify detection type
                if cross_inst and sim_score >= 0.95:
                    detection_type = "clone"
                elif same_inst and sim_score >= 0.92:
                    detection_type = "reuse"
                else:
                    detection_type = "template"

                # Ensure canonical ordering (tender_id_1 < tender_id_2) to avoid duplicates
                t1 = min(tender_id, row["similar_tender_id"])
                t2 = max(tender_id, row["similar_tender_id"])

                results.append(
                    {
                        "tender_id_1": t1,
                        "tender_id_2": t2,
                        "similarity_score": round(sim_score, 4),
                        "same_institution": same_inst,
                        "same_winner": same_winner,
                        "cross_institution": cross_inst,
                        "detection_type": detection_type,
                    }
                )

            return results

    async def store_similarity_pairs(self, pairs: List[Dict]) -> int:
        """
        Store similarity pairs in the database.
        Uses UPSERT to handle duplicates.

        Args:
            pairs: List of similarity pair dicts

        Returns:
            Number of pairs stored/updated
        """
        if not pairs:
            return 0

        stored = 0
        async with self.pool.acquire() as conn:
            for pair in pairs:
                try:
                    await conn.execute(
                        """
                        INSERT INTO spec_similarity_pairs
                            (tender_id_1, tender_id_2, similarity_score,
                             same_institution, same_winner, cross_institution,
                             detection_type, detected_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                        ON CONFLICT (tender_id_1, tender_id_2)
                        DO UPDATE SET
                            similarity_score = EXCLUDED.similarity_score,
                            same_institution = EXCLUDED.same_institution,
                            same_winner = EXCLUDED.same_winner,
                            cross_institution = EXCLUDED.cross_institution,
                            detection_type = EXCLUDED.detection_type,
                            detected_at = NOW()
                        """,
                        pair["tender_id_1"],
                        pair["tender_id_2"],
                        pair["similarity_score"],
                        pair["same_institution"],
                        pair["same_winner"],
                        pair["cross_institution"],
                        pair["detection_type"],
                    )
                    stored += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to store pair {pair['tender_id_1']}-"
                        f"{pair['tender_id_2']}: {e}"
                    )

        return stored

    async def compute_institution_stats(self) -> int:
        """
        Compute specification reuse statistics for all institutions.

        Returns:
            Number of institutions processed
        """
        async with self.pool.acquire() as conn:
            # Get all institutions that have tenders with embeddings
            institutions = await conn.fetch(
                """
                SELECT DISTINCT t.procuring_entity as institution,
                       COUNT(DISTINCT e.tender_id) as total_specs
                FROM embeddings e
                JOIN tenders t ON e.tender_id = t.tender_id
                WHERE t.procuring_entity IS NOT NULL
                GROUP BY t.procuring_entity
                HAVING COUNT(DISTINCT e.tender_id) >= 2
                ORDER BY total_specs DESC
                """
            )

            logger.info(
                f"Computing reuse stats for {len(institutions)} institutions"
            )
            processed = 0

            for inst_row in institutions:
                institution = inst_row["institution"]
                total_specs = inst_row["total_specs"]

                try:
                    # Count reused pairs for this institution
                    reused = await conn.fetchval(
                        """
                        SELECT COUNT(*)
                        FROM spec_similarity_pairs
                        WHERE same_institution = TRUE
                          AND similarity_score >= 0.92
                          AND (tender_id_1 IN (
                              SELECT tender_id FROM tenders
                              WHERE procuring_entity = $1
                          ))
                        """,
                        institution,
                    )

                    reused_count = reused or 0

                    # Estimate unique specs
                    unique_specs = max(1, total_specs - reused_count)
                    reuse_rate = max(
                        0.0,
                        min(1.0, 1.0 - (unique_specs / total_specs)),
                    )

                    # Find top winner for this institution
                    top_winner_row = await conn.fetchrow(
                        """
                        SELECT winner, COUNT(*) as win_count
                        FROM tenders
                        WHERE procuring_entity = $1
                          AND winner IS NOT NULL
                          AND status IN ('awarded', 'completed')
                        GROUP BY winner
                        ORDER BY win_count DESC
                        LIMIT 1
                        """,
                        institution,
                    )

                    top_winner = (
                        top_winner_row["winner"]
                        if top_winner_row
                        else None
                    )
                    top_winner_pct = (
                        (top_winner_row["win_count"] / total_specs * 100)
                        if top_winner_row
                        else 0.0
                    )

                    # Upsert
                    await conn.execute(
                        """
                        INSERT INTO institution_spec_reuse
                            (institution, total_specs, unique_specs,
                             reuse_rate, top_winner, top_winner_pct, computed_at)
                        VALUES ($1, $2, $3, $4, $5, $6, NOW())
                        ON CONFLICT (institution)
                        DO UPDATE SET
                            total_specs = EXCLUDED.total_specs,
                            unique_specs = EXCLUDED.unique_specs,
                            reuse_rate = EXCLUDED.reuse_rate,
                            top_winner = EXCLUDED.top_winner,
                            top_winner_pct = EXCLUDED.top_winner_pct,
                            computed_at = NOW()
                        """,
                        institution,
                        total_specs,
                        unique_specs,
                        round(reuse_rate, 4),
                        top_winner,
                        round(top_winner_pct, 2),
                    )
                    processed += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to compute stats for '{institution}': {e}"
                    )

            logger.info(f"Computed reuse stats for {processed} institutions")
            return processed

    async def run(
        self,
        limit: Optional[int] = None,
        institution: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, int]:
        """
        Main entry point: compute similarity pairs and institution stats.

        Args:
            limit: Maximum number of tenders to process
            institution: Only process this institution's tenders
            dry_run: Compute but don't store results

        Returns:
            Statistics dict with counts
        """
        start_time = time.time()

        await self.connect()
        if not dry_run:
            await self.ensure_tables_exist()

        # Get tenders with embeddings
        tender_ids = await self.get_tenders_with_embeddings(
            limit=limit, institution=institution
        )

        if not tender_ids:
            logger.info("No tenders with embeddings found")
            await self.close()
            return {
                "tenders_processed": 0,
                "pairs_found": 0,
                "pairs_stored": 0,
                "institutions_processed": 0,
                "elapsed_seconds": 0,
            }

        total_pairs_found = 0
        total_pairs_stored = 0

        # Process in batches
        for batch_start in range(0, len(tender_ids), self.batch_size):
            batch = tender_ids[batch_start : batch_start + self.batch_size]
            batch_num = batch_start // self.batch_size + 1
            total_batches = (
                len(tender_ids) + self.batch_size - 1
            ) // self.batch_size

            logger.info(
                f"Processing batch {batch_num}/{total_batches} "
                f"({len(batch)} tenders)"
            )

            batch_pairs = []
            for tender_id in batch:
                try:
                    pairs = await self.compute_similarities_for_tender(
                        tender_id
                    )
                    batch_pairs.extend(pairs)
                    total_pairs_found += len(pairs)
                except Exception as e:
                    logger.warning(
                        f"Error computing similarities for {tender_id}: {e}"
                    )

            # Deduplicate by (tender_id_1, tender_id_2) within batch
            seen = set()
            unique_pairs = []
            for pair in batch_pairs:
                key = (pair["tender_id_1"], pair["tender_id_2"])
                if key not in seen:
                    seen.add(key)
                    unique_pairs.append(pair)

            if not dry_run and unique_pairs:
                stored = await self.store_similarity_pairs(unique_pairs)
                total_pairs_stored += stored

            logger.info(
                f"Batch {batch_num}: {len(unique_pairs)} unique pairs "
                f"found, {total_pairs_stored} total stored"
            )

        # Compute institution reuse stats
        institutions_processed = 0
        if not dry_run:
            institutions_processed = await self.compute_institution_stats()

        elapsed = round(time.time() - start_time, 1)
        await self.close()

        stats = {
            "tenders_processed": len(tender_ids),
            "pairs_found": total_pairs_found,
            "pairs_stored": total_pairs_stored,
            "institutions_processed": institutions_processed,
            "elapsed_seconds": elapsed,
        }

        logger.info(
            f"Batch similarity complete: {stats['tenders_processed']} tenders, "
            f"{stats['pairs_found']} pairs found, "
            f"{stats['pairs_stored']} stored, "
            f"{stats['institutions_processed']} institutions, "
            f"{elapsed}s elapsed"
        )

        return stats


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Batch specification similarity computation"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tenders to process",
    )
    parser.add_argument(
        "--institution",
        type=str,
        default=None,
        help="Only process this institution's tenders",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.85,
        help="Minimum similarity threshold (0-1, default 0.85)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of most similar tenders per tender (default 5)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Tenders per processing batch (default 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute but don't store results",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    processor = BatchSimilarityProcessor(
        min_similarity=args.min_similarity,
        top_k=args.top_k,
        batch_size=args.batch_size,
    )

    stats = await processor.run(
        limit=args.limit,
        institution=args.institution,
        dry_run=args.dry_run,
    )

    print("\n" + "=" * 60)
    print("BATCH SIMILARITY COMPUTATION COMPLETE")
    print("=" * 60)
    print(f"Tenders processed:      {stats['tenders_processed']}")
    print(f"Similarity pairs found: {stats['pairs_found']}")
    print(f"Pairs stored:           {stats['pairs_stored']}")
    print(f"Institutions processed: {stats['institutions_processed']}")
    print(f"Elapsed time:           {stats['elapsed_seconds']}s")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
