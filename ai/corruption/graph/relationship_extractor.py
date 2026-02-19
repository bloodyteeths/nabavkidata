"""
Relationship Extractor

Extracts entity relationship edges from the PostgreSQL procurement database.
Produces edge dicts suitable for RelationshipGraph construction.

Edge Types Extracted:
1. co_bidding - Companies that bid on the same tenders (from tender_bidders)
2. buyer_supplier - Institution -> winning company (from tenders)
3. repeat_partnership - Buyer-supplier pairs with 3+ contracts
4. value_concentration - Buyer-supplier pairs where supplier gets >50% of buyer's total value

Author: nabavkidata.com
License: Proprietary
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)


class RelationshipExtractor:
    """
    Async SQL-based edge extractor for the unified relationship graph.

    Queries the tender_bidders and tenders tables to extract four types of
    entity relationships. Each edge is returned as a dict compatible with
    RelationshipGraph.

    Usage:
        pool = await asyncpg.create_pool(dsn=...)
        extractor = RelationshipExtractor()
        edges = await extractor.extract_edges(pool)
        graph = RelationshipGraph(edges)
    """

    # Minimum co-bid count to create a co_bidding edge
    MIN_CO_BIDS = 2

    # Minimum contracts to flag as repeat_partnership
    MIN_REPEAT_CONTRACTS = 3

    # Minimum value concentration ratio (supplier gets >50% of buyer's total)
    MIN_CONCENTRATION_RATIO = 0.50

    # Minimum buyer total value (MKD) to evaluate concentration
    # Avoids flagging tiny buyers with only 1-2 contracts
    MIN_BUYER_VALUE_FOR_CONCENTRATION = 1_000_000

    async def extract_edges(self, pool: asyncpg.Pool) -> List[Dict[str, Any]]:
        """
        Extract all relationship edges from the database.

        Runs four SQL queries to extract co_bidding, buyer_supplier,
        repeat_partnership, and value_concentration edges.

        Args:
            pool: asyncpg connection pool

        Returns:
            List of edge dicts ready for RelationshipGraph
        """
        all_edges: List[Dict[str, Any]] = []
        start_time = datetime.utcnow()

        logger.info("Starting relationship extraction...")

        # Extract each edge type
        co_bidding_edges = await self._extract_co_bidding_edges(pool)
        logger.info(f"Extracted {len(co_bidding_edges)} co_bidding edges")
        all_edges.extend(co_bidding_edges)

        buyer_supplier_edges = await self._extract_buyer_supplier_edges(pool)
        logger.info(f"Extracted {len(buyer_supplier_edges)} buyer_supplier edges")
        all_edges.extend(buyer_supplier_edges)

        repeat_edges = await self._extract_repeat_partnership_edges(pool)
        logger.info(f"Extracted {len(repeat_edges)} repeat_partnership edges")
        all_edges.extend(repeat_edges)

        concentration_edges = await self._extract_value_concentration_edges(pool)
        logger.info(f"Extracted {len(concentration_edges)} value_concentration edges")
        all_edges.extend(concentration_edges)

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Relationship extraction complete: {len(all_edges)} total edges "
            f"in {elapsed:.1f}s"
        )

        return all_edges

    async def _extract_co_bidding_edges(self, pool: asyncpg.Pool) -> List[Dict[str, Any]]:
        """
        Extract co-bidding edges: companies that bid on the same tenders.

        Uses the tender_bidders table to find pairs of companies that
        submitted bids on the same tender at least MIN_CO_BIDS times.

        Returns edges: company <-> company (undirected, stored as source < target)
        """
        query = """
            WITH co_bids AS (
                SELECT
                    LEAST(tb1.company_name, tb2.company_name) AS company_a,
                    GREATEST(tb1.company_name, tb2.company_name) AS company_b,
                    COUNT(DISTINCT tb1.tender_id) AS co_bid_count,
                    array_agg(DISTINCT tb1.tender_id ORDER BY tb1.tender_id) AS common_tenders,
                    SUM(COALESCE(t.actual_value_mkd, t.estimated_value_mkd, 0)) AS total_value,
                    MIN(t.publication_date) AS first_seen,
                    MAX(t.publication_date) AS last_seen
                FROM tender_bidders tb1
                JOIN tender_bidders tb2
                    ON tb1.tender_id = tb2.tender_id
                    AND tb1.company_name < tb2.company_name
                JOIN tenders t ON tb1.tender_id = t.tender_id
                WHERE t.status IN ('awarded', 'closed', 'completed')
                  AND tb1.company_name IS NOT NULL
                  AND tb2.company_name IS NOT NULL
                  AND LENGTH(TRIM(tb1.company_name)) > 0
                  AND LENGTH(TRIM(tb2.company_name)) > 0
                GROUP BY
                    LEAST(tb1.company_name, tb2.company_name),
                    GREATEST(tb1.company_name, tb2.company_name)
                HAVING COUNT(DISTINCT tb1.tender_id) >= $1
            )
            SELECT
                company_a,
                company_b,
                co_bid_count,
                common_tenders[1:5] AS sample_tenders,
                total_value,
                first_seen,
                last_seen
            FROM co_bids
            ORDER BY co_bid_count DESC
        """

        edges = []
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, self.MIN_CO_BIDS)

            for row in rows:
                sample_tenders = row["sample_tenders"] if row["sample_tenders"] else []
                edges.append({
                    "source_id": row["company_a"],
                    "source_type": "company",
                    "target_id": row["company_b"],
                    "target_type": "company",
                    "edge_type": "co_bidding",
                    "weight": float(row["co_bid_count"]),
                    "tender_count": row["co_bid_count"],
                    "total_value": float(row["total_value"] or 0),
                    "metadata": {
                        "sample_tenders": list(sample_tenders),
                        "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
                        "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                    },
                })

        return edges

    async def _extract_buyer_supplier_edges(self, pool: asyncpg.Pool) -> List[Dict[str, Any]]:
        """
        Extract buyer-supplier edges: institution -> winning company.

        Uses the tenders table, grouping by (procuring_entity, winner) to find
        all institution-company award relationships.

        Returns edges: institution -> company (directed)
        """
        query = """
            SELECT
                t.procuring_entity AS institution,
                t.winner AS company,
                COUNT(*) AS contract_count,
                SUM(COALESCE(t.actual_value_mkd, t.estimated_value_mkd, 0)) AS total_value,
                MIN(t.publication_date) AS first_seen,
                MAX(t.publication_date) AS last_seen,
                array_agg(DISTINCT t.tender_id ORDER BY t.tender_id) AS tender_ids
            FROM tenders t
            WHERE t.status IN ('awarded', 'closed', 'completed')
              AND t.winner IS NOT NULL
              AND LENGTH(TRIM(t.winner)) > 0
              AND t.procuring_entity IS NOT NULL
              AND LENGTH(TRIM(t.procuring_entity)) > 0
            GROUP BY t.procuring_entity, t.winner
            ORDER BY contract_count DESC
        """

        edges = []
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)

            for row in rows:
                tender_ids = row["tender_ids"] if row["tender_ids"] else []
                edges.append({
                    "source_id": row["institution"],
                    "source_type": "institution",
                    "target_id": row["company"],
                    "target_type": "company",
                    "edge_type": "buyer_supplier",
                    "weight": float(row["contract_count"]),
                    "tender_count": row["contract_count"],
                    "total_value": float(row["total_value"] or 0),
                    "metadata": {
                        "sample_tenders": list(tender_ids[:5]),
                        "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
                        "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                    },
                })

        return edges

    async def _extract_repeat_partnership_edges(self, pool: asyncpg.Pool) -> List[Dict[str, Any]]:
        """
        Extract repeat partnership edges: buyer-supplier pairs with 3+ contracts.

        These are a subset of buyer_supplier edges where the relationship
        is recurring, which may indicate favoritism or pre-arrangement.

        Returns edges: institution -> company (directed)
        """
        query = """
            SELECT
                t.procuring_entity AS institution,
                t.winner AS company,
                COUNT(*) AS contract_count,
                SUM(COALESCE(t.actual_value_mkd, t.estimated_value_mkd, 0)) AS total_value,
                AVG(COALESCE(t.actual_value_mkd, t.estimated_value_mkd, 0)) AS avg_value,
                MIN(t.publication_date) AS first_seen,
                MAX(t.publication_date) AS last_seen,
                array_agg(t.tender_id ORDER BY t.publication_date) AS tender_ids,
                -- Calculate what percentage of this buyer's tenders go to this supplier
                COUNT(*)::float / NULLIF(
                    (SELECT COUNT(*) FROM tenders t2
                     WHERE t2.procuring_entity = t.procuring_entity
                       AND t2.status IN ('awarded', 'closed', 'completed')
                       AND t2.winner IS NOT NULL), 0
                ) AS share_of_buyer_tenders
            FROM tenders t
            WHERE t.status IN ('awarded', 'closed', 'completed')
              AND t.winner IS NOT NULL
              AND LENGTH(TRIM(t.winner)) > 0
              AND t.procuring_entity IS NOT NULL
              AND LENGTH(TRIM(t.procuring_entity)) > 0
            GROUP BY t.procuring_entity, t.winner
            HAVING COUNT(*) >= $1
            ORDER BY contract_count DESC
        """

        edges = []
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, self.MIN_REPEAT_CONTRACTS)

            for row in rows:
                tender_ids = row["tender_ids"] if row["tender_ids"] else []
                share = float(row["share_of_buyer_tenders"]) if row["share_of_buyer_tenders"] else 0
                edges.append({
                    "source_id": row["institution"],
                    "source_type": "institution",
                    "target_id": row["company"],
                    "target_type": "company",
                    "edge_type": "repeat_partnership",
                    "weight": float(row["contract_count"]),
                    "tender_count": row["contract_count"],
                    "total_value": float(row["total_value"] or 0),
                    "metadata": {
                        "avg_contract_value": round(float(row["avg_value"] or 0), 2),
                        "share_of_buyer_tenders": round(share, 4),
                        "sample_tenders": list(tender_ids[:5]),
                        "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
                        "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                    },
                })

        return edges

    async def _extract_value_concentration_edges(self, pool: asyncpg.Pool) -> List[Dict[str, Any]]:
        """
        Extract value concentration edges: supplier gets >50% of buyer's total contract value.

        Identifies cases where a single supplier dominates a buyer's procurement spending.
        Only considers buyers with total value above MIN_BUYER_VALUE_FOR_CONCENTRATION
        to avoid flagging trivially small institutions.

        Returns edges: institution -> company (directed)
        """
        query = """
            WITH buyer_totals AS (
                SELECT
                    t.procuring_entity,
                    SUM(COALESCE(t.actual_value_mkd, t.estimated_value_mkd, 0)) AS buyer_total_value,
                    COUNT(*) AS buyer_total_contracts
                FROM tenders t
                WHERE t.status IN ('awarded', 'closed', 'completed')
                  AND t.winner IS NOT NULL
                  AND t.procuring_entity IS NOT NULL
                  AND LENGTH(TRIM(t.procuring_entity)) > 0
                GROUP BY t.procuring_entity
                HAVING SUM(COALESCE(t.actual_value_mkd, t.estimated_value_mkd, 0)) >= $1
            ),
            supplier_shares AS (
                SELECT
                    t.procuring_entity AS institution,
                    t.winner AS company,
                    COUNT(*) AS contract_count,
                    SUM(COALESCE(t.actual_value_mkd, t.estimated_value_mkd, 0)) AS supplier_value,
                    bt.buyer_total_value,
                    bt.buyer_total_contracts,
                    SUM(COALESCE(t.actual_value_mkd, t.estimated_value_mkd, 0)) /
                        NULLIF(bt.buyer_total_value, 0) AS concentration_ratio,
                    MIN(t.publication_date) AS first_seen,
                    MAX(t.publication_date) AS last_seen,
                    array_agg(t.tender_id ORDER BY t.publication_date) AS tender_ids
                FROM tenders t
                JOIN buyer_totals bt ON t.procuring_entity = bt.procuring_entity
                WHERE t.status IN ('awarded', 'closed', 'completed')
                  AND t.winner IS NOT NULL
                  AND LENGTH(TRIM(t.winner)) > 0
                GROUP BY t.procuring_entity, t.winner, bt.buyer_total_value, bt.buyer_total_contracts
            )
            SELECT *
            FROM supplier_shares
            WHERE concentration_ratio >= $2
            ORDER BY concentration_ratio DESC, supplier_value DESC
        """

        edges = []
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                self.MIN_BUYER_VALUE_FOR_CONCENTRATION,
                self.MIN_CONCENTRATION_RATIO,
            )

            for row in rows:
                tender_ids = row["tender_ids"] if row["tender_ids"] else []
                concentration = float(row["concentration_ratio"]) if row["concentration_ratio"] else 0
                edges.append({
                    "source_id": row["institution"],
                    "source_type": "institution",
                    "target_id": row["company"],
                    "target_type": "company",
                    "edge_type": "value_concentration",
                    "weight": round(concentration * 10, 2),  # Scale 0-10 for weight
                    "tender_count": row["contract_count"],
                    "total_value": float(row["supplier_value"] or 0),
                    "metadata": {
                        "concentration_ratio": round(concentration, 4),
                        "supplier_value": round(float(row["supplier_value"] or 0), 2),
                        "buyer_total_value": round(float(row["buyer_total_value"] or 0), 2),
                        "buyer_total_contracts": row["buyer_total_contracts"],
                        "sample_tenders": list(tender_ids[:5]),
                        "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
                        "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                    },
                })

        return edges
