"""
Cross-Tender Specification Similarity Analysis

Detects copy-paste and suspiciously similar specifications across tenders.
Uses document embeddings for fast similarity search, then detailed text
comparison for high-similarity pairs.

Patterns detected:
1. Same institution re-using specifications (lazy but not necessarily corrupt)
2. Different institutions with near-identical specs (supplier-authored)
3. Specifications matching a previous winner's proposal

Uses pgvector cosine similarity on existing 768-dim Gemini embeddings
and Python's difflib.SequenceMatcher for detailed text comparison.

Author: nabavkidata.com
License: Proprietary
"""

import logging
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """
    Normalize text for comparison.
    Removes extra whitespace, normalizes unicode, lowercases.
    """
    if not text:
        return ""
    # Normalize unicode (NFC form)
    text = unicodedata.normalize("NFC", text)
    # Collapse whitespace (spaces, tabs, newlines) to single space
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing
    text = text.strip()
    # Lowercase for comparison
    text = text.lower()
    return text


def _extract_meaningful_sections(text: str, min_length: int = 50) -> List[str]:
    """
    Extract meaningful sections from document text, filtering out
    boilerplate headers, page numbers, and very short lines.
    """
    if not text:
        return []

    # Split by double newlines or numbered section headers
    sections = re.split(r"\n{2,}|\r\n{2,}", text)

    meaningful = []
    for section in sections:
        section = section.strip()
        # Skip very short sections (page numbers, headers)
        if len(section) < min_length:
            continue
        # Skip sections that are mostly numbers/punctuation
        alpha_ratio = sum(1 for c in section if c.isalpha()) / max(len(section), 1)
        if alpha_ratio < 0.3:
            continue
        meaningful.append(section)

    return meaningful


class SpecSimilarityAnalyzer:
    """
    Analyzes specification similarity across tenders using
    pgvector embeddings and text diffing.
    """

    async def find_similar_specs(
        self,
        pool: asyncpg.Pool,
        tender_id: str,
        threshold: float = 0.85,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find specifications most similar to a given tender's specification.
        Uses pgvector cosine similarity on existing embeddings.

        Args:
            pool: asyncpg connection pool
            tender_id: The tender ID to find similar specs for
            threshold: Minimum similarity score (0-1), default 0.85
            limit: Maximum number of results

        Returns:
            List of dicts with keys:
            - similar_tender_id: tender ID of the similar spec
            - similarity_score: cosine similarity (0-1)
            - same_institution: whether same procuring entity
            - same_winner: whether same winner
            - similar_title: title of the similar tender
            - similar_institution: procuring entity of similar tender
            - similar_winner: winner of similar tender
        """
        async with pool.acquire() as conn:
            # First get the average embedding for this tender's documents
            # We average all chunk embeddings for the tender to get a single vector
            rows = await conn.fetch(
                """
                WITH target_vector AS (
                    SELECT AVG(vector) as avg_vec
                    FROM embeddings
                    WHERE tender_id = $1
                ),
                target_tender AS (
                    SELECT procuring_entity, winner
                    FROM tenders
                    WHERE tender_id = $1
                )
                SELECT
                    e2.tender_id as similar_tender_id,
                    1 - (AVG(e2.vector) <=> (SELECT avg_vec FROM target_vector)) as similarity_score,
                    t2.title as similar_title,
                    t2.procuring_entity as similar_institution,
                    t2.winner as similar_winner,
                    (t2.procuring_entity = (SELECT procuring_entity FROM target_tender)) as same_institution,
                    (t2.winner IS NOT NULL
                     AND t2.winner = (SELECT winner FROM target_tender)
                     AND (SELECT winner FROM target_tender) IS NOT NULL) as same_winner
                FROM embeddings e2
                JOIN tenders t2 ON e2.tender_id = t2.tender_id
                WHERE e2.tender_id != $1
                  AND EXISTS (SELECT 1 FROM embeddings WHERE tender_id = $1)
                GROUP BY e2.tender_id, t2.title, t2.procuring_entity, t2.winner
                HAVING 1 - (AVG(e2.vector) <=> (SELECT avg_vec FROM target_vector)) >= $2
                ORDER BY similarity_score DESC
                LIMIT $3
                """,
                tender_id,
                threshold,
                limit,
            )

            results = []
            for row in rows:
                results.append(
                    {
                        "similar_tender_id": row["similar_tender_id"],
                        "similarity_score": round(float(row["similarity_score"]), 4),
                        "same_institution": row["same_institution"] or False,
                        "same_winner": row["same_winner"] or False,
                        "similar_title": row["similar_title"],
                        "similar_institution": row["similar_institution"],
                        "similar_winner": row["similar_winner"],
                    }
                )

            logger.info(
                f"Found {len(results)} similar specs for tender {tender_id} "
                f"(threshold={threshold})"
            )
            return results

    async def detect_copy_paste(self, text1: str, text2: str) -> Dict[str, Any]:
        """
        Detailed text diff between two specifications.
        Uses sequence matching to find copied sections.

        Args:
            text1: First specification text
            text2: Second specification text

        Returns:
            Dict with:
            - similarity_ratio: overall 0-1 similarity
            - copied_sections: list of {text, length} for copied blocks
            - copied_fraction: fraction of text1 that's copied from text2
            - is_suspicious: True if > 60% copied
        """
        norm1 = _normalize_text(text1)
        norm2 = _normalize_text(text2)

        if not norm1 or not norm2:
            return {
                "similarity_ratio": 0.0,
                "copied_sections": [],
                "copied_fraction": 0.0,
                "is_suspicious": False,
            }

        # Use SequenceMatcher for detailed comparison
        matcher = SequenceMatcher(None, norm1, norm2, autojunk=False)
        similarity_ratio = matcher.ratio()

        # Find matching blocks (copied sections)
        copied_sections = []
        total_copied_chars = 0

        for block in matcher.get_matching_blocks():
            # block is (i, j, size) -- position in text1, text2, and length
            if block.size >= 30:  # Only report blocks of 30+ chars
                copied_text = norm1[block.a : block.a + block.size]
                copied_sections.append(
                    {
                        "text": copied_text[:200],  # Truncate for API response
                        "length": block.size,
                    }
                )
                total_copied_chars += block.size

        copied_fraction = total_copied_chars / max(len(norm1), 1)

        return {
            "similarity_ratio": round(similarity_ratio, 4),
            "copied_sections": sorted(
                copied_sections, key=lambda x: x["length"], reverse=True
            )[:20],  # Top 20 longest copied sections
            "copied_fraction": round(copied_fraction, 4),
            "is_suspicious": copied_fraction > 0.60,
        }

    async def find_cross_institution_clones(
        self,
        pool: asyncpg.Pool,
        min_similarity: float = 0.92,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Find spec pairs from DIFFERENT institutions that are nearly identical.
        This is the strongest indicator of supplier-authored specifications.

        Uses pgvector cosine similarity between averaged tender embeddings,
        then filters to different institutions only.

        Args:
            pool: asyncpg connection pool
            min_similarity: Minimum cosine similarity (0-1), default 0.92
            limit: Maximum number of pairs to return

        Returns:
            List of dicts with keys:
            - tender_id_1, tender_id_2
            - institution_1, institution_2
            - winner_1, winner_2
            - similarity: cosine similarity score
            - common_winner: True if same winner for both
            - title_1, title_2
        """
        async with pool.acquire() as conn:
            # First check if we have pre-computed pairs in the cache table
            try:
                cached = await conn.fetch(
                    """
                    SELECT
                        sp.tender_id_1, sp.tender_id_2, sp.similarity_score,
                        sp.same_winner, sp.same_institution,
                        t1.procuring_entity as institution_1,
                        t2.procuring_entity as institution_2,
                        t1.winner as winner_1, t2.winner as winner_2,
                        t1.title as title_1, t2.title as title_2
                    FROM spec_similarity_pairs sp
                    JOIN tenders t1 ON sp.tender_id_1 = t1.tender_id
                    JOIN tenders t2 ON sp.tender_id_2 = t2.tender_id
                    WHERE sp.cross_institution = TRUE
                      AND sp.similarity_score >= $1
                    ORDER BY sp.similarity_score DESC
                    LIMIT $2
                    """,
                    min_similarity,
                    limit,
                )
                if cached:
                    return [
                        {
                            "tender_id_1": r["tender_id_1"],
                            "tender_id_2": r["tender_id_2"],
                            "institution_1": r["institution_1"],
                            "institution_2": r["institution_2"],
                            "winner_1": r["winner_1"],
                            "winner_2": r["winner_2"],
                            "similarity": round(float(r["similarity_score"]), 4),
                            "common_winner": r["same_winner"] or False,
                            "title_1": r["title_1"],
                            "title_2": r["title_2"],
                        }
                        for r in cached
                    ]
            except asyncpg.UndefinedTableError:
                logger.warning(
                    "spec_similarity_pairs table not found, computing on the fly"
                )

            # Compute on the fly if no cached data
            # This is expensive -- limit to a reasonable set
            rows = await conn.fetch(
                """
                WITH tender_vectors AS (
                    SELECT
                        e.tender_id,
                        AVG(e.vector) as avg_vec,
                        t.procuring_entity,
                        t.winner,
                        t.title
                    FROM embeddings e
                    JOIN tenders t ON e.tender_id = t.tender_id
                    GROUP BY e.tender_id, t.procuring_entity, t.winner, t.title
                )
                SELECT
                    tv1.tender_id as tender_id_1,
                    tv2.tender_id as tender_id_2,
                    tv1.procuring_entity as institution_1,
                    tv2.procuring_entity as institution_2,
                    tv1.winner as winner_1,
                    tv2.winner as winner_2,
                    tv1.title as title_1,
                    tv2.title as title_2,
                    1 - (tv1.avg_vec <=> tv2.avg_vec) as similarity,
                    (tv1.winner IS NOT NULL
                     AND tv1.winner = tv2.winner) as common_winner
                FROM tender_vectors tv1
                CROSS JOIN tender_vectors tv2
                WHERE tv1.tender_id < tv2.tender_id
                  AND tv1.procuring_entity != tv2.procuring_entity
                  AND 1 - (tv1.avg_vec <=> tv2.avg_vec) >= $1
                ORDER BY similarity DESC
                LIMIT $2
                """,
                min_similarity,
                limit,
            )

            results = [
                {
                    "tender_id_1": r["tender_id_1"],
                    "tender_id_2": r["tender_id_2"],
                    "institution_1": r["institution_1"],
                    "institution_2": r["institution_2"],
                    "winner_1": r["winner_1"],
                    "winner_2": r["winner_2"],
                    "similarity": round(float(r["similarity"]), 4),
                    "common_winner": r["common_winner"] or False,
                    "title_1": r["title_1"],
                    "title_2": r["title_2"],
                }
                for r in rows
            ]

            logger.info(
                f"Found {len(results)} cross-institution clone pairs "
                f"(min_similarity={min_similarity})"
            )
            return results

    async def compute_institution_spec_reuse_rate(
        self,
        pool: asyncpg.Pool,
        institution: str,
    ) -> Dict[str, Any]:
        """
        For a given institution, compute how often they reuse specifications.
        High reuse rate + always same winner = strong rigging indicator.

        Args:
            pool: asyncpg connection pool
            institution: Name of the procuring entity

        Returns:
            Dict with:
            - institution: institution name
            - total_specs: total number of tenders with embeddings
            - unique_specs: count of unique specifications (based on clustering)
            - reuse_rate: fraction of specs that are reused (0-1)
            - top_winner: most frequent winner
            - top_winner_pct: percentage of wins for the top winner
        """
        async with pool.acquire() as conn:
            # First check cached stats
            try:
                cached = await conn.fetchrow(
                    """
                    SELECT * FROM institution_spec_reuse
                    WHERE institution = $1
                    """,
                    institution,
                )
                if cached:
                    return {
                        "institution": cached["institution"],
                        "total_specs": cached["total_specs"],
                        "unique_specs": cached["unique_specs"],
                        "reuse_rate": round(float(cached["reuse_rate"]), 4),
                        "top_winner": cached["top_winner"],
                        "top_winner_pct": round(
                            float(cached["top_winner_pct"]), 2
                        ),
                    }
            except asyncpg.UndefinedTableError:
                pass

            # Compute on the fly
            # Get all tender vectors for this institution
            tender_vectors = await conn.fetch(
                """
                SELECT
                    e.tender_id,
                    AVG(e.vector) as avg_vec,
                    t.winner
                FROM embeddings e
                JOIN tenders t ON e.tender_id = t.tender_id
                WHERE t.procuring_entity = $1
                GROUP BY e.tender_id, t.winner
                ORDER BY e.tender_id
                """,
                institution,
            )

            total_specs = len(tender_vectors)
            if total_specs == 0:
                return {
                    "institution": institution,
                    "total_specs": 0,
                    "unique_specs": 0,
                    "reuse_rate": 0.0,
                    "top_winner": None,
                    "top_winner_pct": 0.0,
                }

            # Count unique specs using pairwise similarity within institution
            # Two specs are "the same" if similarity > 0.92
            reuse_threshold = 0.92
            similar_pairs = await conn.fetch(
                """
                WITH inst_vectors AS (
                    SELECT
                        e.tender_id,
                        AVG(e.vector) as avg_vec
                    FROM embeddings e
                    JOIN tenders t ON e.tender_id = t.tender_id
                    WHERE t.procuring_entity = $1
                    GROUP BY e.tender_id
                )
                SELECT COUNT(*) as pair_count
                FROM inst_vectors iv1
                CROSS JOIN inst_vectors iv2
                WHERE iv1.tender_id < iv2.tender_id
                  AND 1 - (iv1.avg_vec <=> iv2.avg_vec) >= $2
                """,
                institution,
                reuse_threshold,
            )

            reused_pair_count = similar_pairs[0]["pair_count"] if similar_pairs else 0

            # Estimate unique specs: total - reused pairs (simplified)
            # A more accurate approach would use connected components, but this
            # gives a reasonable approximation
            if reused_pair_count > 0:
                # Rough estimate: unique ~= total - reused_pairs
                # (not exact but reasonable for dashboard purposes)
                unique_specs = max(1, total_specs - reused_pair_count)
            else:
                unique_specs = total_specs

            reuse_rate = 1.0 - (unique_specs / total_specs) if total_specs > 0 else 0.0
            reuse_rate = max(0.0, min(1.0, reuse_rate))

            # Find top winner
            winner_counts: Dict[str, int] = {}
            for tv in tender_vectors:
                w = tv["winner"]
                if w:
                    winner_counts[w] = winner_counts.get(w, 0) + 1

            if winner_counts:
                top_winner = max(winner_counts, key=winner_counts.get)
                top_winner_pct = (
                    winner_counts[top_winner] / total_specs * 100
                )
            else:
                top_winner = None
                top_winner_pct = 0.0

            result = {
                "institution": institution,
                "total_specs": total_specs,
                "unique_specs": unique_specs,
                "reuse_rate": round(reuse_rate, 4),
                "top_winner": top_winner,
                "top_winner_pct": round(top_winner_pct, 2),
            }

            logger.info(
                f"Institution spec reuse for '{institution}': "
                f"{total_specs} total, {unique_specs} unique, "
                f"reuse_rate={reuse_rate:.2%}"
            )
            return result

    async def get_tender_document_text(
        self,
        pool: asyncpg.Pool,
        tender_id: str,
    ) -> Optional[str]:
        """
        Get concatenated document text for a tender.
        Used for detailed copy-paste analysis.

        Args:
            pool: asyncpg connection pool
            tender_id: The tender ID

        Returns:
            Concatenated text from all extracted documents, or None
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT content_text
                FROM documents
                WHERE tender_id = $1
                  AND extraction_status = 'success'
                  AND content_text IS NOT NULL
                ORDER BY doc_id
                """,
                tender_id,
            )

            if not rows:
                return None

            return "\n\n".join(row["content_text"] for row in rows)
