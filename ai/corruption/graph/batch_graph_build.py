"""
Batch Graph Builder

CLI script to rebuild the unified relationship graph nightly.
Extracts edges from the procurement database, computes centrality metrics
and community assignments, and upserts results into PostgreSQL cache tables.

Usage:
    # Full rebuild (extract edges, compute metrics, write to DB)
    python batch_graph_build.py

    # Skip edge extraction (reuse existing unified_edges table)
    python batch_graph_build.py --skip-extraction

    # Only compute and update centrality (no edge write)
    python batch_graph_build.py --centrality-only

    # Custom Louvain resolution
    python batch_graph_build.py --resolution 1.5

    # Dry run (compute metrics but do not write to DB)
    python batch_graph_build.py --dry-run

Cron example (daily at 5:30 AM UTC):
    30 5 * * * cd /home/ubuntu/nabavkidata/ai/corruption/graph && python3 batch_graph_build.py >> /var/log/nabavkidata/batch_graph_build.log 2>&1

Author: nabavkidata.com
License: Proprietary
"""

import os
import sys
import json
import logging
import asyncio
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
load_dotenv()


# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.relationship_extractor import RelationshipExtractor
from graph.relationship_graph import RelationshipGraph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL"),
)

# Batch upsert size
UPSERT_BATCH_SIZE = 500


async def ensure_tables_exist(conn) -> None:
    """Ensure the unified_edges and entity_centrality_cache tables exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS unified_edges (
            edge_id SERIAL PRIMARY KEY,
            source_id TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'company',
            target_id TEXT NOT NULL,
            target_type TEXT NOT NULL DEFAULT 'company',
            edge_type TEXT NOT NULL,
            weight FLOAT DEFAULT 1.0,
            tender_count INTEGER DEFAULT 0,
            total_value NUMERIC(18,2) DEFAULT 0,
            metadata JSONB DEFAULT '{}',
            first_seen TIMESTAMP DEFAULT NOW(),
            last_seen TIMESTAMP DEFAULT NOW(),
            UNIQUE(source_id, target_id, edge_type)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_centrality_cache (
            entity_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL DEFAULT 'company',
            entity_name TEXT,
            pagerank FLOAT DEFAULT 0,
            betweenness FLOAT DEFAULT 0,
            degree INTEGER DEFAULT 0,
            in_degree INTEGER DEFAULT 0,
            out_degree INTEGER DEFAULT 0,
            community_id INTEGER,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    logger.info("Tables verified/created")


async def upsert_edges(conn, edges: List[Dict[str, Any]]) -> int:
    """
    Upsert edges into the unified_edges table.

    Uses INSERT ... ON CONFLICT to update existing edges with new weights
    and metadata.

    Args:
        conn: asyncpg connection
        edges: List of edge dicts from RelationshipExtractor

    Returns:
        Number of edges upserted
    """
    if not edges:
        return 0

    upserted = 0

    for i in range(0, len(edges), UPSERT_BATCH_SIZE):
        batch = edges[i:i + UPSERT_BATCH_SIZE]

        # Build batch values
        for edge in batch:
            metadata_json = json.dumps(edge.get("metadata", {}))
            await conn.execute(
                """
                INSERT INTO unified_edges
                    (source_id, source_type, target_id, target_type, edge_type,
                     weight, tender_count, total_value, metadata, last_seen)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW())
                ON CONFLICT (source_id, target_id, edge_type) DO UPDATE SET
                    weight = EXCLUDED.weight,
                    tender_count = EXCLUDED.tender_count,
                    total_value = EXCLUDED.total_value,
                    metadata = EXCLUDED.metadata,
                    source_type = EXCLUDED.source_type,
                    target_type = EXCLUDED.target_type,
                    last_seen = NOW()
                """,
                edge["source_id"],
                edge.get("source_type", "company"),
                edge["target_id"],
                edge.get("target_type", "company"),
                edge["edge_type"],
                edge.get("weight", 1.0),
                edge.get("tender_count", 0),
                float(edge.get("total_value", 0)),
                metadata_json,
            )
            upserted += 1

        logger.info(f"  Upserted edges batch: {min(i + UPSERT_BATCH_SIZE, len(edges))}/{len(edges)}")

    return upserted


async def upsert_centrality(
    conn,
    pagerank: Dict[str, float],
    betweenness: Dict[str, float],
    communities: Dict[str, int],
    node_types: Dict[str, str],
    graph: RelationshipGraph,
) -> int:
    """
    Upsert centrality metrics into entity_centrality_cache.

    Args:
        conn: asyncpg connection
        pagerank: Dict of entity_id -> pagerank score
        betweenness: Dict of entity_id -> betweenness score
        communities: Dict of entity_id -> community_id
        node_types: Dict of entity_id -> entity_type
        graph: The RelationshipGraph (for degree computation)

    Returns:
        Number of entities upserted
    """
    all_entities = set(pagerank.keys()) | set(betweenness.keys())
    if not all_entities:
        return 0

    upserted = 0
    entities_list = sorted(all_entities)

    for i in range(0, len(entities_list), UPSERT_BATCH_SIZE):
        batch = entities_list[i:i + UPSERT_BATCH_SIZE]

        for entity_id in batch:
            pr = pagerank.get(entity_id, 0)
            bc = betweenness.get(entity_id, 0)
            comm = communities.get(entity_id)
            etype = node_types.get(entity_id, "company")

            # Compute degree from the internal graph
            degree = 0
            in_deg = 0
            out_deg = 0
            if graph.has_node(entity_id):
                degree = graph._undirected_graph.degree(entity_id)
                in_deg = graph._graph.in_degree(entity_id)
                out_deg = graph._graph.out_degree(entity_id)

            await conn.execute(
                """
                INSERT INTO entity_centrality_cache
                    (entity_id, entity_type, entity_name, pagerank, betweenness,
                     degree, in_degree, out_degree, community_id, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                ON CONFLICT (entity_id) DO UPDATE SET
                    entity_type = EXCLUDED.entity_type,
                    entity_name = EXCLUDED.entity_name,
                    pagerank = EXCLUDED.pagerank,
                    betweenness = EXCLUDED.betweenness,
                    degree = EXCLUDED.degree,
                    in_degree = EXCLUDED.in_degree,
                    out_degree = EXCLUDED.out_degree,
                    community_id = EXCLUDED.community_id,
                    updated_at = NOW()
                """,
                entity_id,
                etype,
                entity_id,  # entity_name = entity_id (name is the identifier)
                pr,
                bc,
                degree,
                in_deg,
                out_deg,
                comm,
            )
            upserted += 1

        logger.info(
            f"  Upserted centrality batch: "
            f"{min(i + UPSERT_BATCH_SIZE, len(entities_list))}/{len(entities_list)}"
        )

    return upserted


async def load_edges_from_db(pool: asyncpg.Pool) -> List[Dict[str, Any]]:
    """Load existing edges from the unified_edges table."""
    query = """
        SELECT source_id, source_type, target_id, target_type,
               edge_type, weight, tender_count, total_value, metadata
        FROM unified_edges
    """
    edges = []
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
        for row in rows:
            metadata = row["metadata"]
            if isinstance(metadata, str):
                metadata = json.loads(metadata) if metadata else {}
            elif metadata is None:
                metadata = {}

            edges.append({
                "source_id": row["source_id"],
                "source_type": row["source_type"],
                "target_id": row["target_id"],
                "target_type": row["target_type"],
                "edge_type": row["edge_type"],
                "weight": float(row["weight"] or 1.0),
                "tender_count": row["tender_count"] or 0,
                "total_value": float(row["total_value"] or 0),
                "metadata": metadata,
            })

    logger.info(f"Loaded {len(edges)} edges from unified_edges table")
    return edges


async def run_batch(
    skip_extraction: bool = False,
    centrality_only: bool = False,
    dry_run: bool = False,
    resolution: float = 1.0,
) -> Dict[str, Any]:
    """
    Run the full batch graph build pipeline.

    Steps:
        1. Extract edges from procurement data (unless skip_extraction)
        2. Build in-memory RelationshipGraph
        3. Compute PageRank, betweenness centrality, communities
        4. Upsert edges to unified_edges table (unless centrality_only)
        5. Upsert centrality to entity_centrality_cache table

    Args:
        skip_extraction: If True, load edges from unified_edges table instead of re-extracting
        centrality_only: If True, skip edge upsert (only update centrality cache)
        dry_run: If True, compute metrics but do not write to DB
        resolution: Louvain community detection resolution parameter

    Returns:
        Dict with summary statistics
    """
    if not DATABASE_URL:
        logger.error("DATABASE_URL not set. Export it or set in environment.")
        return {"error": "DATABASE_URL not set"}

    start_time = datetime.utcnow()
    stats: Dict[str, Any] = {
        "started_at": start_time.isoformat(),
        "skip_extraction": skip_extraction,
        "centrality_only": centrality_only,
        "dry_run": dry_run,
    }

    logger.info("=" * 70)
    logger.info("BATCH GRAPH BUILD - Phase 4.1 Unified Relationship Graph")
    logger.info("=" * 70)

    # Connect to database
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5, command_timeout=300)
    logger.info("Database pool created")

    try:
        # Ensure tables exist
        async with pool.acquire() as conn:
            await ensure_tables_exist(conn)

        # Step 1: Extract or load edges
        if skip_extraction or centrality_only:
            logger.info("Step 1: Loading existing edges from unified_edges...")
            edges = await load_edges_from_db(pool)
        else:
            logger.info("Step 1: Extracting edges from procurement data...")
            extractor = RelationshipExtractor()
            edges = await extractor.extract_edges(pool)

        stats["total_edges_extracted"] = len(edges)

        if not edges:
            logger.warning("No edges extracted. Nothing to build.")
            stats["error"] = "No edges extracted"
            return stats

        # Step 2: Build graph
        logger.info(f"Step 2: Building in-memory RelationshipGraph from {len(edges)} edges...")
        graph = RelationshipGraph(edges)
        graph_stats = graph.get_stats()
        stats["graph_stats"] = graph_stats
        logger.info(
            f"  Graph built: {graph_stats['node_count']} nodes, "
            f"{graph_stats['edge_count']} edges, "
            f"{graph_stats['connected_components']} components"
        )

        # Step 3a: Compute PageRank
        logger.info("Step 3a: Computing PageRank...")
        t0 = datetime.utcnow()
        pagerank = graph.compute_pagerank()
        pr_time = (datetime.utcnow() - t0).total_seconds()
        stats["pagerank_time_sec"] = round(pr_time, 2)
        logger.info(f"  PageRank computed in {pr_time:.1f}s for {len(pagerank)} nodes")

        # Top 5 PageRank entities
        top_pr = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:5]
        logger.info("  Top 5 PageRank:")
        for entity_id, score in top_pr:
            logger.info(f"    {entity_id}: {score:.6f}")

        # Step 3b: Compute betweenness centrality
        logger.info("Step 3b: Computing betweenness centrality...")
        t0 = datetime.utcnow()
        betweenness = graph.compute_betweenness_centrality()
        bc_time = (datetime.utcnow() - t0).total_seconds()
        stats["betweenness_time_sec"] = round(bc_time, 2)
        logger.info(f"  Betweenness computed in {bc_time:.1f}s for {len(betweenness)} nodes")

        # Top 5 betweenness entities (gatekeepers)
        top_bc = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:5]
        logger.info("  Top 5 Gatekeepers (Betweenness):")
        for entity_id, score in top_bc:
            logger.info(f"    {entity_id}: {score:.6f}")

        # Step 3c: Detect communities
        logger.info(f"Step 3c: Detecting communities (resolution={resolution})...")
        t0 = datetime.utcnow()
        community_map = graph.get_node_community_map(resolution=resolution)
        comm_time = (datetime.utcnow() - t0).total_seconds()
        stats["community_time_sec"] = round(comm_time, 2)
        n_communities = len(set(community_map.values())) if community_map else 0
        stats["n_communities"] = n_communities
        logger.info(f"  Detected {n_communities} communities in {comm_time:.1f}s")

        # Step 4: Upsert edges to DB
        if not dry_run and not centrality_only:
            logger.info(f"Step 4: Upserting {len(edges)} edges to unified_edges...")
            async with pool.acquire() as conn:
                n_upserted = await upsert_edges(conn, edges)
            stats["edges_upserted"] = n_upserted
            logger.info(f"  Upserted {n_upserted} edges")
        else:
            reason = "dry_run" if dry_run else "centrality_only"
            logger.info(f"Step 4: Skipping edge upsert ({reason})")
            stats["edges_upserted"] = 0

        # Step 5: Upsert centrality to DB
        if not dry_run:
            logger.info("Step 5: Upserting centrality metrics...")
            node_types = {node: graph.get_node_type(node) for node in pagerank}
            async with pool.acquire() as conn:
                n_centrality = await upsert_centrality(
                    conn, pagerank, betweenness, community_map, node_types, graph
                )
            stats["centrality_upserted"] = n_centrality
            logger.info(f"  Upserted {n_centrality} entity centrality records")
        else:
            logger.info("Step 5: Skipping centrality upsert (dry_run)")
            stats["centrality_upserted"] = 0

        # Summary
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        stats["total_time_sec"] = round(elapsed, 2)
        stats["completed_at"] = datetime.utcnow().isoformat()
        stats["success"] = True

        logger.info("=" * 70)
        logger.info(f"BATCH COMPLETE in {elapsed:.1f}s")
        logger.info(f"  Edges: {len(edges)} extracted, {stats.get('edges_upserted', 0)} upserted")
        logger.info(f"  Nodes: {graph_stats['node_count']}")
        logger.info(f"  Communities: {n_communities}")
        logger.info(f"  Centrality records: {stats.get('centrality_upserted', 0)}")
        logger.info("=" * 70)

        return stats

    except Exception as e:
        logger.error(f"Batch graph build failed: {e}", exc_info=True)
        stats["error"] = str(e)
        stats["success"] = False
        return stats

    finally:
        await pool.close()
        logger.info("Database pool closed")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Batch rebuild the unified relationship graph and centrality cache."
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip edge extraction, load from existing unified_edges table",
    )
    parser.add_argument(
        "--centrality-only",
        action="store_true",
        help="Only recompute and update centrality metrics (no edge write)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute metrics but do not write to database",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=1.0,
        help="Louvain community detection resolution (default: 1.0, higher = more communities)",
    )

    args = parser.parse_args()

    result = asyncio.run(run_batch(
        skip_extraction=args.skip_extraction,
        centrality_only=args.centrality_only,
        dry_run=args.dry_run,
        resolution=args.resolution,
    ))

    # Print final stats as JSON
    print(json.dumps(result, indent=2, default=str))

    # Exit with error code if failed
    if not result.get("success", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
