"""
Graph Cache Manager

Caches the co-bidding graph in PostgreSQL JSONB tables (gnn_graph_cache,
gnn_predictions_cache).  Rebuilt daily by cron; the API reads the cached
version for fast inference.

The cache stores:
- Serialized graph: node list, edge list, node_index mapping, node features
- Per-company risk predictions
- Cluster membership

Usage:
    from graph_cache import build_and_cache_graph, get_cached_graph

    pool = await get_asyncpg_pool()
    graph_dict = await get_cached_graph(pool)
    # or force rebuild:
    graph_dict = await build_and_cache_graph(pool)
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Default parameters that match the training pipeline
DEFAULT_TIME_WINDOW_DAYS = 730
DEFAULT_MIN_CO_BIDS = 2
DEFAULT_MIN_BIDS_PER_COMPANY = 3
CACHE_KEY = f"co_bidding_{DEFAULT_TIME_WINDOW_DAYS}d"
CACHE_TTL_HOURS = 25  # Slightly longer than the 24h cron interval


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def build_and_cache_graph(
    pool,
    time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
    min_co_bids: int = DEFAULT_MIN_CO_BIDS,
    min_bids_per_company: int = DEFAULT_MIN_BIDS_PER_COMPANY,
) -> Dict[str, Any]:
    """
    Build co-bidding graph from tender_bidders table and cache in DB.

    This is intended to be called from a daily cron job.  It builds the
    graph, serializes it to JSON, and stores it in gnn_graph_cache.

    Args:
        pool: asyncpg connection pool
        time_window_days: How many days of data to include
        min_co_bids: Minimum co-occurrences to create an edge
        min_bids_per_company: Minimum bids to include a company

    Returns:
        Dictionary with graph metadata (node_count, edge_count, built_at, etc.)
    """
    start = time.monotonic()

    try:
        from ai.corruption.ml_models.graph_builder import GraphBuilder
    except ImportError:
        # Fallback for when running from backend/ directory
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from ai.corruption.ml_models.graph_builder import GraphBuilder

    builder = GraphBuilder(pool)
    graph = await builder.build_co_bidding_graph(
        min_co_bids=min_co_bids,
        time_window_days=time_window_days,
        min_bids_per_company=min_bids_per_company,
        include_edge_features=False,  # lighter for cache
        include_labels=False,
    )

    node_count = graph.num_nodes()
    edge_count = graph.num_edges()

    # Serialize to a JSON-friendly dict
    serialized = _serialize_graph(graph)

    duration = time.monotonic() - start

    # Store in DB
    cache_key = f"co_bidding_{time_window_days}d"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO gnn_graph_cache (cache_key, graph_data, node_count, edge_count, built_at, build_duration_seconds)
            VALUES ($1, $2::jsonb, $3, $4, NOW(), $5)
            ON CONFLICT (cache_key) DO UPDATE SET
                graph_data = EXCLUDED.graph_data,
                node_count = EXCLUDED.node_count,
                edge_count = EXCLUDED.edge_count,
                built_at = NOW(),
                build_duration_seconds = EXCLUDED.build_duration_seconds
            """,
            cache_key,
            json.dumps(serialized),
            node_count,
            edge_count,
            duration,
        )

    logger.info(
        f"Graph cached: {node_count} nodes, {edge_count} edges in {duration:.1f}s "
        f"(key={cache_key})"
    )

    return {
        "cache_key": cache_key,
        "node_count": node_count,
        "edge_count": edge_count,
        "built_at": datetime.utcnow().isoformat(),
        "build_duration_seconds": round(duration, 2),
    }


async def get_cached_graph(
    pool,
    cache_key: str = CACHE_KEY,
    max_age_hours: int = CACHE_TTL_HOURS,
) -> Optional[Dict[str, Any]]:
    """
    Load cached graph from DB.  Returns None if cache is missing or stale.

    Falls back to building the graph if the cache is older than max_age_hours.

    Args:
        pool: asyncpg connection pool
        cache_key: The cache key to look up
        max_age_hours: Maximum acceptable cache age in hours

    Returns:
        Deserialized graph dict, or None if not available.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT graph_data, node_count, edge_count, built_at
            FROM gnn_graph_cache
            WHERE cache_key = $1
              AND built_at >= NOW() - $2::interval
            """,
            cache_key,
            timedelta(hours=max_age_hours),
        )

    if row is None:
        logger.info(f"Graph cache miss or stale (key={cache_key})")
        return None

    graph_data = row["graph_data"]
    if isinstance(graph_data, str):
        graph_data = json.loads(graph_data)

    logger.info(
        f"Graph cache hit: {row['node_count']} nodes, "
        f"{row['edge_count']} edges, built {row['built_at']}"
    )

    return graph_data


async def cache_predictions(
    pool,
    predictions: List[Dict[str, Any]],
    cluster_map: Optional[Dict[str, str]] = None,
) -> int:
    """
    Store per-company risk predictions in gnn_predictions_cache.

    Args:
        pool: asyncpg connection pool
        predictions: List of dicts with company_name, probability, risk_level, etc.
        cluster_map: Optional mapping from company_name -> cluster_id

    Returns:
        Number of rows upserted
    """
    if not predictions:
        return 0

    cluster_map = cluster_map or {}
    count = 0

    async with pool.acquire() as conn:
        # Use a transaction for batch insert
        async with conn.transaction():
            for pred in predictions:
                company = pred.get("company_name", "")
                prob = float(pred.get("probability", 0.0))
                level = pred.get("risk_level", "low")
                cluster_id = cluster_map.get(company)
                embedding = pred.get("embedding")

                # Convert numpy array to list if needed
                if embedding is not None:
                    if isinstance(embedding, np.ndarray):
                        embedding = embedding.tolist()

                await conn.execute(
                    """
                    INSERT INTO gnn_predictions_cache
                        (company_name, risk_probability, risk_level, cluster_id, embedding, predicted_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (company_name) DO UPDATE SET
                        risk_probability = EXCLUDED.risk_probability,
                        risk_level = EXCLUDED.risk_level,
                        cluster_id = EXCLUDED.cluster_id,
                        embedding = EXCLUDED.embedding,
                        predicted_at = NOW()
                    """,
                    company,
                    prob,
                    level,
                    cluster_id,
                    embedding,
                )
                count += 1

    logger.info(f"Cached {count} prediction rows")
    return count


async def get_cached_predictions(
    pool,
    company_name: Optional[str] = None,
    min_probability: float = 0.0,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """
    Read cached predictions from DB.

    Args:
        pool: asyncpg connection pool
        company_name: Filter to a single company (exact match)
        min_probability: Minimum risk probability
        limit: Max results

    Returns:
        List of prediction dicts
    """
    if company_name:
        row = await pool.fetchrow(
            "SELECT * FROM gnn_predictions_cache WHERE company_name = $1",
            company_name,
        )
        if row:
            return [dict(row)]
        return []

    rows = await pool.fetch(
        """
        SELECT company_name, risk_probability, risk_level, cluster_id, predicted_at
        FROM gnn_predictions_cache
        WHERE risk_probability >= $1
        ORDER BY risk_probability DESC
        LIMIT $2
        """,
        min_probability,
        limit,
    )
    return [dict(r) for r in rows]


async def get_cache_status(pool) -> Dict[str, Any]:
    """Return metadata about the current cache state."""
    graph_row = await pool.fetchrow(
        """
        SELECT cache_key, node_count, edge_count, built_at, build_duration_seconds
        FROM gnn_graph_cache
        ORDER BY built_at DESC LIMIT 1
        """
    )
    pred_row = await pool.fetchrow(
        """
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE risk_level = 'high' OR risk_level = 'critical') as high_risk,
               MAX(predicted_at) as last_predicted
        FROM gnn_predictions_cache
        """
    )

    return {
        "graph": dict(graph_row) if graph_row else None,
        "predictions": dict(pred_row) if pred_row else None,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _serialize_graph(graph) -> Dict[str, Any]:
    """
    Serialize a BidderGraph to a JSON-safe dict.

    We keep:
      - node_index: {name -> int}
      - nodes: [{name, node_type, features, metadata}]
      - edges: [{source, target, weight, edge_type}]
      - node_features: [[float, ...], ...] (2-D list)
      - metadata: graph-level metadata
    """
    nodes = []
    for n in graph.nodes:
        nodes.append({
            "node_id": n.node_id,
            "name": n.name,
            "node_type": n.node_type,
            "features": {k: _to_native(v) for k, v in n.features.items()},
            "metadata": {k: _to_native(v) for k, v in n.metadata.items()},
        })

    edges = []
    for e in graph.edges:
        edges.append({
            "source": int(e.source),
            "target": int(e.target),
            "edge_type": e.edge_type,
            "weight": float(e.weight),
        })

    # Store raw node features as a 2-D list for numpy reconstruction
    nf = graph.node_features
    if isinstance(nf, np.ndarray) and nf.size > 0:
        node_features_list = nf.tolist()
    else:
        node_features_list = []

    return {
        "node_index": graph.node_index,
        "nodes": nodes,
        "edges": edges,
        "node_features": node_features_list,
        "metadata": {k: _to_native(v) for k, v in graph.metadata.items()},
    }


def _to_native(value):
    """Convert numpy scalars / dates to JSON-serializable Python types."""
    if isinstance(value, (np.floating, np.float32, np.float64)):
        return float(value)
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return int(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    return value
