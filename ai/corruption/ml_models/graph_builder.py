"""
Graph Builder for Collusion Detection GNN

Builds bipartite and unipartite graphs from the tender_bidders table for
Graph Neural Network analysis. Exports graphs in PyTorch Geometric format.

Graph Types:
1. Bidder-Tender Bipartite Graph: Companies connected to tenders they bid on
2. Co-Bidding Graph: Companies connected if they bid on same tenders
3. Bidder-Buyer Graph: Companies connected to institutions they bid at

Edge Types:
- bid_on: Company submitted bid on tender
- co_bid: Two companies bid on same tender
- won: Company won the tender
- lost: Company bid but lost

Node Features:
- Companies: win rate, total bids, avg bid amount, etc.
- Tenders: value, num bidders, category, etc.

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import asyncpg
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json

# Try importing PyTorch Geometric (optional - for export)
try:
    import torch
    from torch_geometric.data import Data, HeteroData
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    Data = None
    HeteroData = None

# Try importing NetworkX for graph analysis
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """Represents a node in the graph."""
    node_id: int
    node_type: str  # 'bidder', 'tender', 'buyer'
    name: str
    features: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Represents an edge in the graph."""
    source: int
    target: int
    edge_type: str  # 'bid_on', 'co_bid', 'won', 'lost'
    weight: float = 1.0
    features: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BidderGraph:
    """
    Container for bidder graph data.

    Attributes:
        nodes: List of graph nodes (bidders, tenders, buyers)
        edges: List of graph edges
        node_index: Mapping from name to node_id
        node_features: NumPy array of node features [num_nodes, num_features]
        edge_index: NumPy array of edges [2, num_edges]
        edge_attr: NumPy array of edge features [num_edges, num_edge_features]
        node_labels: Optional node labels for classification
        edge_labels: Optional edge labels for link prediction
        metadata: Graph-level metadata
    """
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    node_index: Dict[str, int]
    node_features: np.ndarray
    edge_index: np.ndarray
    edge_attr: np.ndarray
    node_labels: Optional[np.ndarray] = None
    edge_labels: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_pyg_data(self) -> Optional['Data']:
        """Convert to PyTorch Geometric Data object."""
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch/PyG not available. Install torch and torch_geometric.")
            return None

        return Data(
            x=torch.tensor(self.node_features, dtype=torch.float32),
            edge_index=torch.tensor(self.edge_index, dtype=torch.long),
            edge_attr=torch.tensor(self.edge_attr, dtype=torch.float32) if self.edge_attr.size > 0 else None,
            y=torch.tensor(self.node_labels, dtype=torch.long) if self.node_labels is not None else None,
            num_nodes=len(self.nodes)
        )

    def to_pyg_hetero_data(self) -> Optional['HeteroData']:
        """Convert to PyTorch Geometric HeteroData for heterogeneous graphs."""
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch/PyG not available.")
            return None

        data = HeteroData()

        # Group nodes by type
        node_types = defaultdict(list)
        for node in self.nodes:
            node_types[node.node_type].append(node)

        # Add node features per type
        for node_type, nodes in node_types.items():
            features = np.array([list(n.features.values()) for n in nodes], dtype=np.float32)
            data[node_type].x = torch.tensor(features, dtype=torch.float32)
            data[node_type].num_nodes = len(nodes)

        # Group edges by type
        edge_types = defaultdict(list)
        for edge in self.edges:
            src_type = self.nodes[edge.source].node_type
            dst_type = self.nodes[edge.target].node_type
            edge_types[(src_type, edge.edge_type, dst_type)].append(edge)

        # Add edges per type
        for (src_type, rel, dst_type), edges in edge_types.items():
            edge_index = torch.tensor(
                [[e.source for e in edges], [e.target for e in edges]],
                dtype=torch.long
            )
            data[src_type, rel, dst_type].edge_index = edge_index

            if edges and edges[0].features:
                edge_attr = torch.tensor(
                    [list(e.features.values()) for e in edges],
                    dtype=torch.float32
                )
                data[src_type, rel, dst_type].edge_attr = edge_attr

        return data

    def to_networkx(self) -> Optional['nx.Graph']:
        """Convert to NetworkX graph for analysis."""
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available. Install networkx.")
            return None

        G = nx.Graph()

        # Add nodes with features
        for node in self.nodes:
            # Combine features and metadata, prefixing metadata keys to avoid conflicts
            node_attrs = {
                'name': node.name,
                'node_type': node.node_type,
            }
            # Add features
            for k, v in node.features.items():
                node_attrs[k] = v
            # Add metadata with prefix to avoid conflicts
            for k, v in node.metadata.items():
                node_attrs[f'meta_{k}'] = v

            G.add_node(node.node_id, **node_attrs)

        # Add edges
        for edge in self.edges:
            edge_attrs = {
                'edge_type': edge.edge_type,
                'weight': edge.weight,
            }
            # Add features
            for k, v in edge.features.items():
                edge_attrs[k] = v
            # Add metadata with prefix
            for k, v in edge.metadata.items():
                edge_attrs[f'meta_{k}'] = v

            G.add_edge(edge.source, edge.target, **edge_attrs)

        return G

    def get_node_by_name(self, name: str) -> Optional[GraphNode]:
        """Get node by name."""
        node_id = self.node_index.get(name)
        if node_id is not None:
            return self.nodes[node_id]
        return None

    def get_neighbors(self, node_id: int) -> List[int]:
        """Get neighbor node IDs."""
        neighbors = []
        for edge in self.edges:
            if edge.source == node_id:
                neighbors.append(edge.target)
            elif edge.target == node_id:
                neighbors.append(edge.source)
        return neighbors

    def num_nodes(self) -> int:
        return len(self.nodes)

    def num_edges(self) -> int:
        return len(self.edges)


class GraphBuilder:
    """
    Builds graphs from tender_bidders database table for GNN analysis.

    Supports multiple graph types:
    1. Co-bidding graph (companies connected if they bid together)
    2. Bidder-tender bipartite graph (companies connected to tenders)
    3. Temporal graph (edges weighted by time proximity)

    Usage:
        builder = GraphBuilder(pool)
        graph = await builder.build_co_bidding_graph(
            min_co_bids=3,
            time_window_days=365
        )
        pyg_data = graph.to_pyg_data()
    """

    # Feature dimensions
    BIDDER_FEATURES = [
        'total_bids', 'total_wins', 'win_rate', 'avg_bid_amount_log',
        'num_institutions', 'num_categories', 'avg_bidders_in_tenders',
        'single_bidder_rate', 'co_bid_diversity', 'days_active'
    ]

    TENDER_FEATURES = [
        'estimated_value_log', 'actual_value_log', 'num_bidders',
        'deadline_days', 'has_winner', 'is_single_bidder',
        'year', 'month', 'category_encoded'
    ]

    EDGE_FEATURES = [
        'co_bid_count', 'co_bid_rate', 'time_proximity',
        'same_winner_rate', 'bid_amount_similarity', 'sequential_wins'
    ]

    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize graph builder.

        Args:
            pool: AsyncPG connection pool
        """
        self.pool = pool
        logger.info("GraphBuilder initialized")

    # =========================================================================
    # Main Graph Building Methods
    # =========================================================================

    async def build_co_bidding_graph(
        self,
        min_co_bids: int = 2,
        time_window_days: int = 730,  # 2 years
        min_bids_per_company: int = 3,
        include_edge_features: bool = True,
        include_labels: bool = False
    ) -> BidderGraph:
        """
        Build a co-bidding graph where companies are connected if they
        bid on the same tenders together.

        Args:
            min_co_bids: Minimum co-occurrences to create edge
            time_window_days: Only consider tenders within this window
            min_bids_per_company: Minimum bids to include a company
            include_edge_features: Calculate detailed edge features
            include_labels: Include collusion labels if available

        Returns:
            BidderGraph with company nodes and co-bidding edges
        """
        logger.info(f"Building co-bidding graph (min_co_bids={min_co_bids}, window={time_window_days}d)")

        # Step 1: Get active companies
        companies = await self._get_active_companies(
            time_window_days=time_window_days,
            min_bids=min_bids_per_company
        )
        logger.info(f"Found {len(companies)} active companies")

        if len(companies) < 2:
            return self._empty_graph()

        # Step 2: Build node index
        node_index = {c['company_name']: i for i, c in enumerate(companies)}

        # Step 3: Get co-bidding pairs
        co_bids = await self._get_co_bidding_pairs(
            companies=list(node_index.keys()),
            time_window_days=time_window_days,
            min_co_bids=min_co_bids
        )
        logger.info(f"Found {len(co_bids)} co-bidding pairs")

        # Step 4: Build nodes with features
        nodes = []
        for i, company in enumerate(companies):
            features = self._extract_company_features(company)
            node = GraphNode(
                node_id=i,
                node_type='bidder',
                name=company['company_name'],
                features=features,
                metadata={
                    'tax_id': company.get('company_tax_id'),
                    'total_bids': company['total_bids'],
                    'total_wins': company['total_wins']
                }
            )
            nodes.append(node)

        # Step 5: Build edges
        edges = []
        for pair in co_bids:
            src_idx = node_index.get(pair['company_a'])
            dst_idx = node_index.get(pair['company_b'])

            if src_idx is None or dst_idx is None:
                continue

            edge_features = {}
            if include_edge_features:
                edge_features = await self._calculate_edge_features(
                    pair['company_a'],
                    pair['company_b'],
                    time_window_days
                )

            edge = GraphEdge(
                source=src_idx,
                target=dst_idx,
                edge_type='co_bid',
                weight=float(pair['co_bid_count']),
                features=edge_features,
                metadata={
                    'co_bid_count': pair['co_bid_count'],
                    'common_tenders': pair.get('common_tenders', [])[:5]
                }
            )
            edges.append(edge)

        # Step 6: Build feature arrays
        node_features = np.array(
            [[n.features.get(f, 0.0) for f in self.BIDDER_FEATURES] for n in nodes],
            dtype=np.float32
        )

        edge_index = np.array(
            [[e.source for e in edges], [e.target for e in edges]],
            dtype=np.int64
        )

        edge_attr = np.array(
            [[e.features.get(f, 0.0) for f in self.EDGE_FEATURES] for e in edges],
            dtype=np.float32
        ) if edges and include_edge_features else np.array([], dtype=np.float32)

        # Step 7: Get labels if available
        node_labels = None
        if include_labels:
            node_labels = await self._get_collusion_labels(list(node_index.keys()))

        graph = BidderGraph(
            nodes=nodes,
            edges=edges,
            node_index=node_index,
            node_features=node_features,
            edge_index=edge_index,
            edge_attr=edge_attr,
            node_labels=node_labels,
            metadata={
                'graph_type': 'co_bidding',
                'num_nodes': len(nodes),
                'num_edges': len(edges),
                'time_window_days': time_window_days,
                'min_co_bids': min_co_bids,
                'created_at': datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Built co-bidding graph: {len(nodes)} nodes, {len(edges)} edges")
        return graph

    async def build_bipartite_graph(
        self,
        time_window_days: int = 730,
        min_bids_per_company: int = 2,
        min_bidders_per_tender: int = 1,
        include_buyers: bool = False
    ) -> BidderGraph:
        """
        Build a bipartite graph with company nodes and tender nodes.

        Args:
            time_window_days: Only consider tenders within this window
            min_bids_per_company: Minimum bids to include a company
            min_bidders_per_tender: Minimum bidders to include a tender
            include_buyers: Also include buyer (institution) nodes

        Returns:
            BidderGraph with company and tender nodes
        """
        logger.info(f"Building bipartite graph (window={time_window_days}d)")

        # Get companies
        companies = await self._get_active_companies(
            time_window_days=time_window_days,
            min_bids=min_bids_per_company
        )

        # Get tenders
        tenders = await self._get_active_tenders(
            time_window_days=time_window_days,
            min_bidders=min_bidders_per_tender
        )

        # Get buyers if requested
        buyers = []
        if include_buyers:
            buyers = await self._get_active_buyers(time_window_days)

        logger.info(f"Found {len(companies)} companies, {len(tenders)} tenders, {len(buyers)} buyers")

        # Build node index (companies first, then tenders, then buyers)
        node_index = {}
        nodes = []
        current_idx = 0

        # Company nodes
        for company in companies:
            node_index[company['company_name']] = current_idx
            features = self._extract_company_features(company)
            nodes.append(GraphNode(
                node_id=current_idx,
                node_type='bidder',
                name=company['company_name'],
                features=features
            ))
            current_idx += 1

        # Tender nodes
        for tender in tenders:
            node_index[tender['tender_id']] = current_idx
            features = self._extract_tender_features(tender)
            nodes.append(GraphNode(
                node_id=current_idx,
                node_type='tender',
                name=tender['tender_id'],
                features=features,
                metadata={'title': tender.get('title')}
            ))
            current_idx += 1

        # Buyer nodes
        for buyer in buyers:
            node_index[buyer['procuring_entity']] = current_idx
            features = self._extract_buyer_features(buyer)
            nodes.append(GraphNode(
                node_id=current_idx,
                node_type='buyer',
                name=buyer['procuring_entity'],
                features=features
            ))
            current_idx += 1

        # Get bid relationships
        bids = await self._get_bid_edges(
            companies=[c['company_name'] for c in companies],
            tenders=[t['tender_id'] for t in tenders],
            time_window_days=time_window_days
        )

        # Build edges
        edges = []
        for bid in bids:
            company_idx = node_index.get(bid['company_name'])
            tender_idx = node_index.get(bid['tender_id'])

            if company_idx is None or tender_idx is None:
                continue

            edge_type = 'won' if bid['is_winner'] else 'bid_on'

            edge = GraphEdge(
                source=company_idx,
                target=tender_idx,
                edge_type=edge_type,
                weight=1.0,
                features={
                    'bid_amount_log': np.log10(float(bid['bid_amount_mkd']) + 1) if bid['bid_amount_mkd'] else 0,
                    'is_winner': 1.0 if bid['is_winner'] else 0.0,
                    'rank': float(bid['rank']) if bid['rank'] else 0.0
                }
            )
            edges.append(edge)

        # Add buyer edges if included
        if include_buyers:
            buyer_edges = await self._get_buyer_edges(
                tenders=[t['tender_id'] for t in tenders]
            )
            for edge_data in buyer_edges:
                tender_idx = node_index.get(edge_data['tender_id'])
                buyer_idx = node_index.get(edge_data['procuring_entity'])
                if tender_idx is not None and buyer_idx is not None:
                    edges.append(GraphEdge(
                        source=tender_idx,
                        target=buyer_idx,
                        edge_type='procured_by',
                        weight=1.0
                    ))

        # Build arrays
        node_features = np.zeros((len(nodes), len(self.BIDDER_FEATURES)), dtype=np.float32)
        for i, node in enumerate(nodes):
            if node.node_type == 'bidder':
                for j, f in enumerate(self.BIDDER_FEATURES):
                    node_features[i, j] = node.features.get(f, 0.0)

        edge_index = np.array(
            [[e.source for e in edges], [e.target for e in edges]],
            dtype=np.int64
        )

        edge_attr = np.array(
            [[e.features.get(f, 0.0) for f in ['bid_amount_log', 'is_winner', 'rank']] for e in edges],
            dtype=np.float32
        ) if edges else np.array([], dtype=np.float32)

        return BidderGraph(
            nodes=nodes,
            edges=edges,
            node_index=node_index,
            node_features=node_features,
            edge_index=edge_index,
            edge_attr=edge_attr,
            metadata={
                'graph_type': 'bipartite',
                'num_nodes': len(nodes),
                'num_edges': len(edges),
                'num_companies': len(companies),
                'num_tenders': len(tenders),
                'num_buyers': len(buyers),
                'created_at': datetime.utcnow().isoformat()
            }
        )

    async def build_temporal_graph(
        self,
        time_window_days: int = 730,
        temporal_decay: float = 0.5,
        min_co_bids: int = 2
    ) -> BidderGraph:
        """
        Build a co-bidding graph with temporal decay on edge weights.
        More recent co-bidding relationships have higher weights.

        Args:
            time_window_days: Time window for data
            temporal_decay: Decay factor (0.5 means half-life)
            min_co_bids: Minimum co-occurrences

        Returns:
            BidderGraph with temporally-weighted edges
        """
        # Build base graph
        graph = await self.build_co_bidding_graph(
            min_co_bids=min_co_bids,
            time_window_days=time_window_days,
            include_edge_features=True
        )

        # Apply temporal decay to edge weights
        now = datetime.utcnow()
        for edge in graph.edges:
            # Get most recent co-bid date
            recent_date = edge.metadata.get('most_recent_date')
            if recent_date:
                days_ago = (now - recent_date).days
                decay = temporal_decay ** (days_ago / 365.0)
                edge.weight *= decay
                edge.features['temporal_weight'] = decay

        graph.metadata['temporal_decay'] = temporal_decay
        return graph

    # =========================================================================
    # Database Query Methods
    # =========================================================================

    async def _get_active_companies(
        self,
        time_window_days: int,
        min_bids: int
    ) -> List[Dict]:
        """Get companies with sufficient bidding activity."""
        query = """
            WITH company_stats AS (
                SELECT
                    tb.company_name,
                    tb.company_tax_id,
                    COUNT(DISTINCT tb.tender_id) as total_bids,
                    COUNT(DISTINCT tb.tender_id) FILTER (WHERE tb.is_winner) as total_wins,
                    COUNT(DISTINCT t.procuring_entity) as num_institutions,
                    COUNT(DISTINCT t.category) as num_categories,
                    AVG(tb.bid_amount_mkd) as avg_bid_amount,
                    AVG(t.num_bidders) as avg_bidders_in_tenders,
                    MIN(t.publication_date) as first_bid_date,
                    MAX(t.publication_date) as last_bid_date,
                    COUNT(*) FILTER (WHERE t.num_bidders = 1) as single_bidder_count
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE t.publication_date >= CURRENT_DATE - $1::interval
                  AND t.status IN ('awarded', 'closed', 'completed')
                GROUP BY tb.company_name, tb.company_tax_id
                HAVING COUNT(DISTINCT tb.tender_id) >= $2
            )
            SELECT
                company_name,
                company_tax_id,
                total_bids,
                total_wins,
                CASE WHEN total_bids > 0 THEN total_wins::float / total_bids ELSE 0 END as win_rate,
                num_institutions,
                num_categories,
                avg_bid_amount,
                avg_bidders_in_tenders,
                first_bid_date,
                last_bid_date,
                single_bidder_count,
                CASE WHEN total_bids > 0
                     THEN single_bidder_count::float / total_bids
                     ELSE 0 END as single_bidder_rate,
                COALESCE((last_bid_date - first_bid_date), 0) as days_active
            FROM company_stats
            ORDER BY total_bids DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, timedelta(days=time_window_days), min_bids)
            return [dict(row) for row in rows]

    async def _get_active_tenders(
        self,
        time_window_days: int,
        min_bidders: int
    ) -> List[Dict]:
        """Get tenders with bidding data."""
        query = """
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.num_bidders,
                t.publication_date,
                t.closing_date,
                t.status,
                t.winner,
                t.category,
                EXTRACT(days FROM (t.closing_date - t.publication_date)) as deadline_days
            FROM tenders t
            WHERE t.publication_date >= CURRENT_DATE - $1::interval
              AND t.status IN ('awarded', 'closed', 'completed')
              AND t.num_bidders >= $2
            ORDER BY t.publication_date DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, timedelta(days=time_window_days), min_bidders)
            return [dict(row) for row in rows]

    async def _get_active_buyers(self, time_window_days: int) -> List[Dict]:
        """Get active procuring entities."""
        query = """
            SELECT
                t.procuring_entity,
                COUNT(*) as total_tenders,
                SUM(t.estimated_value_mkd) as total_value,
                AVG(t.num_bidders) as avg_bidders,
                COUNT(*) FILTER (WHERE t.num_bidders = 1) as single_bidder_count
            FROM tenders t
            WHERE t.publication_date >= CURRENT_DATE - $1::interval
              AND t.status IN ('awarded', 'closed', 'completed')
            GROUP BY t.procuring_entity
            ORDER BY total_tenders DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, timedelta(days=time_window_days))
            return [dict(row) for row in rows]

    async def _get_co_bidding_pairs(
        self,
        companies: List[str],
        time_window_days: int,
        min_co_bids: int
    ) -> List[Dict]:
        """Get pairs of companies that bid on same tenders."""
        query = """
            WITH company_tenders AS (
                SELECT
                    tb.company_name,
                    tb.tender_id
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE t.publication_date >= CURRENT_DATE - $1::interval
                  AND tb.company_name = ANY($2::text[])
            )
            SELECT
                ct1.company_name as company_a,
                ct2.company_name as company_b,
                COUNT(*) as co_bid_count,
                array_agg(ct1.tender_id ORDER BY ct1.tender_id) as common_tenders
            FROM company_tenders ct1
            JOIN company_tenders ct2
                ON ct1.tender_id = ct2.tender_id
                AND ct1.company_name < ct2.company_name
            GROUP BY ct1.company_name, ct2.company_name
            HAVING COUNT(*) >= $3
            ORDER BY co_bid_count DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, timedelta(days=time_window_days), companies, min_co_bids)
            return [dict(row) for row in rows]

    async def _get_bid_edges(
        self,
        companies: List[str],
        tenders: List[str],
        time_window_days: int
    ) -> List[Dict]:
        """Get bid relationships between companies and tenders."""
        query = """
            SELECT
                tb.company_name,
                tb.tender_id,
                tb.bid_amount_mkd,
                tb.is_winner,
                tb.rank
            FROM tender_bidders tb
            WHERE tb.company_name = ANY($1::text[])
              AND tb.tender_id = ANY($2::text[])
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, companies, tenders)
            return [dict(row) for row in rows]

    async def _get_buyer_edges(self, tenders: List[str]) -> List[Dict]:
        """Get tender-buyer relationships."""
        query = """
            SELECT tender_id, procuring_entity
            FROM tenders
            WHERE tender_id = ANY($1::text[])
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, tenders)
            return [dict(row) for row in rows]

    async def _calculate_edge_features(
        self,
        company_a: str,
        company_b: str,
        time_window_days: int
    ) -> Dict[str, float]:
        """Calculate detailed features for a co-bidding edge."""
        query = """
            WITH common_tenders AS (
                SELECT
                    tb1.tender_id,
                    tb1.is_winner as a_won,
                    tb2.is_winner as b_won,
                    tb1.bid_amount_mkd as a_bid,
                    tb2.bid_amount_mkd as b_bid,
                    t.publication_date
                FROM tender_bidders tb1
                JOIN tender_bidders tb2 ON tb1.tender_id = tb2.tender_id
                JOIN tenders t ON tb1.tender_id = t.tender_id
                WHERE tb1.company_name = $1
                  AND tb2.company_name = $2
                  AND t.publication_date >= CURRENT_DATE - $3::interval
            ),
            a_stats AS (
                SELECT COUNT(DISTINCT tender_id) as total_bids
                FROM tender_bidders
                WHERE company_name = $1
            ),
            b_stats AS (
                SELECT COUNT(DISTINCT tender_id) as total_bids
                FROM tender_bidders
                WHERE company_name = $2
            )
            SELECT
                COUNT(*) as co_bid_count,
                COUNT(*) / GREATEST(
                    (SELECT total_bids FROM a_stats),
                    (SELECT total_bids FROM b_stats),
                    1
                )::float as co_bid_rate,
                AVG(CASE
                    WHEN a_bid > 0 AND b_bid > 0
                    THEN 1 - ABS(a_bid - b_bid) / GREATEST(a_bid, b_bid)
                    ELSE 0
                END) as bid_amount_similarity,
                SUM(CASE WHEN a_won OR b_won THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) as same_winner_rate,
                MAX(publication_date) as most_recent_date,
                COALESCE(MAX(publication_date) - MIN(publication_date), 0) as time_span_days
            FROM common_tenders
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, company_a, company_b, timedelta(days=time_window_days))

            if not row:
                return {f: 0.0 for f in self.EDGE_FEATURES}

            return {
                'co_bid_count': float(row['co_bid_count'] or 0),
                'co_bid_rate': float(row['co_bid_rate'] or 0),
                'time_proximity': 1.0,  # Will be computed with temporal decay
                'same_winner_rate': float(row['same_winner_rate'] or 0),
                'bid_amount_similarity': float(row['bid_amount_similarity'] or 0),
                'sequential_wins': 0.0  # TODO: Implement sequential win detection
            }

    async def _get_collusion_labels(self, companies: List[str]) -> Optional[np.ndarray]:
        """
        Get collusion labels from company_relationships table.
        Returns 1 for companies flagged in bid_cluster relationships.
        """
        query = """
            SELECT DISTINCT company_a as company_name
            FROM company_relationships
            WHERE relationship_type = 'bid_cluster'
              AND company_a = ANY($1::text[])
            UNION
            SELECT DISTINCT company_b
            FROM company_relationships
            WHERE relationship_type = 'bid_cluster'
              AND company_b = ANY($1::text[])
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, companies)
            flagged = {row['company_name'] for row in rows}

        labels = np.array([1 if c in flagged else 0 for c in companies], dtype=np.int64)
        return labels

    # =========================================================================
    # Feature Extraction Helpers
    # =========================================================================

    def _extract_company_features(self, company: Dict) -> Dict[str, float]:
        """Extract normalized features from company data."""
        avg_bid = company.get('avg_bid_amount') or 0
        return {
            'total_bids': float(company.get('total_bids') or 0),
            'total_wins': float(company.get('total_wins') or 0),
            'win_rate': float(company.get('win_rate') or 0),
            'avg_bid_amount_log': np.log10(float(avg_bid) + 1),
            'num_institutions': float(company.get('num_institutions') or 0),
            'num_categories': float(company.get('num_categories') or 0),
            'avg_bidders_in_tenders': float(company.get('avg_bidders_in_tenders') or 0),
            'single_bidder_rate': float(company.get('single_bidder_rate') or 0),
            'co_bid_diversity': 0.0,  # Computed at graph level
            'days_active': float(company.get('days_active') or 0)
        }

    def _extract_tender_features(self, tender: Dict) -> Dict[str, float]:
        """Extract features from tender data."""
        est_value = float(tender.get('estimated_value_mkd', 0) or 0)
        act_value = float(tender.get('actual_value_mkd', 0) or 0)
        pub_date = tender.get('publication_date')

        return {
            'estimated_value_log': np.log10(est_value + 1) if est_value > 0 else 0,
            'actual_value_log': np.log10(act_value + 1) if act_value > 0 else 0,
            'num_bidders': float(tender.get('num_bidders', 0)),
            'deadline_days': float(tender.get('deadline_days', 0) or 0),
            'has_winner': 1.0 if tender.get('winner') else 0.0,
            'is_single_bidder': 1.0 if tender.get('num_bidders') == 1 else 0.0,
            'year': float(pub_date.year) if pub_date else 0,
            'month': float(pub_date.month) if pub_date else 0,
            'category_encoded': 0.0  # Would need category encoding
        }

    def _extract_buyer_features(self, buyer: Dict) -> Dict[str, float]:
        """Extract features from buyer data."""
        total_value = float(buyer.get('total_value', 0) or 0)
        return {
            'total_tenders': float(buyer.get('total_tenders', 0)),
            'total_value_log': np.log10(total_value + 1) if total_value > 0 else 0,
            'avg_bidders': float(buyer.get('avg_bidders', 0) or 0),
            'single_bidder_rate': float(buyer.get('single_bidder_count', 0)) / max(buyer.get('total_tenders', 1), 1)
        }

    def _empty_graph(self) -> BidderGraph:
        """Return an empty graph."""
        return BidderGraph(
            nodes=[],
            edges=[],
            node_index={},
            node_features=np.array([], dtype=np.float32),
            edge_index=np.array([[], []], dtype=np.int64),
            edge_attr=np.array([], dtype=np.float32),
            metadata={'graph_type': 'empty', 'num_nodes': 0, 'num_edges': 0}
        )

    # =========================================================================
    # Graph Analysis Methods (using NetworkX)
    # =========================================================================

    async def compute_graph_statistics(self, graph: BidderGraph) -> Dict[str, Any]:
        """
        Compute various graph statistics using NetworkX.

        Returns:
            Dictionary with graph metrics
        """
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available for graph statistics")
            return {}

        G = graph.to_networkx()
        if G is None or len(G) == 0:
            return {}

        stats = {
            'num_nodes': G.number_of_nodes(),
            'num_edges': G.number_of_edges(),
            'density': nx.density(G),
            'is_connected': nx.is_connected(G) if G.number_of_nodes() > 0 else False
        }

        # Connected components
        if G.number_of_nodes() > 0:
            components = list(nx.connected_components(G))
            stats['num_components'] = len(components)
            stats['largest_component_size'] = max(len(c) for c in components)

        # Degree statistics
        degrees = [d for n, d in G.degree()]
        if degrees:
            stats['avg_degree'] = np.mean(degrees)
            stats['max_degree'] = max(degrees)
            stats['degree_std'] = np.std(degrees)

        # Clustering coefficient
        try:
            stats['avg_clustering'] = nx.average_clustering(G)
        except Exception:
            stats['avg_clustering'] = 0.0

        # Centrality measures (sample if graph is large)
        if G.number_of_nodes() <= 1000:
            try:
                betweenness = nx.betweenness_centrality(G)
                stats['max_betweenness'] = max(betweenness.values()) if betweenness else 0
                stats['avg_betweenness'] = np.mean(list(betweenness.values())) if betweenness else 0
            except Exception:
                pass

        return stats

    async def find_dense_subgraphs(
        self,
        graph: BidderGraph,
        min_size: int = 3,
        min_density: float = 0.5
    ) -> List[List[str]]:
        """
        Find dense subgraphs that might indicate collusion clusters.

        Args:
            graph: The co-bidding graph
            min_size: Minimum cluster size
            min_density: Minimum edge density within cluster

        Returns:
            List of company name lists forming dense subgraphs
        """
        if not NETWORKX_AVAILABLE:
            return []

        G = graph.to_networkx()
        if G is None or len(G) < min_size:
            return []

        dense_subgraphs = []

        # Find cliques (complete subgraphs)
        for clique in nx.find_cliques(G):
            if len(clique) >= min_size:
                # Get company names
                names = [graph.nodes[i].name for i in clique]
                dense_subgraphs.append(names)

        # Sort by size (largest first)
        dense_subgraphs.sort(key=len, reverse=True)

        return dense_subgraphs


# =============================================================================
# Utility Functions
# =============================================================================

async def build_graph_from_db(
    pool: asyncpg.Pool,
    graph_type: str = 'co_bidding',
    **kwargs
) -> BidderGraph:
    """
    Convenience function to build a graph from database.

    Args:
        pool: Database connection pool
        graph_type: One of 'co_bidding', 'bipartite', 'temporal'
        **kwargs: Additional arguments passed to the builder method

    Returns:
        BidderGraph
    """
    builder = GraphBuilder(pool)

    if graph_type == 'co_bidding':
        return await builder.build_co_bidding_graph(**kwargs)
    elif graph_type == 'bipartite':
        return await builder.build_bipartite_graph(**kwargs)
    elif graph_type == 'temporal':
        return await builder.build_temporal_graph(**kwargs)
    else:
        raise ValueError(f"Unknown graph type: {graph_type}")


def save_graph(graph: BidderGraph, path: str):
    """Save graph to file (supports .pt for PyTorch, .gpickle for NetworkX)."""
    import pickle

    if path.endswith('.pt') and TORCH_AVAILABLE:
        import torch
        data = graph.to_pyg_data()
        torch.save(data, path)
    elif path.endswith('.gpickle') and NETWORKX_AVAILABLE:
        G = graph.to_networkx()
        nx.write_gpickle(G, path)
    else:
        # Save as pickle
        with open(path, 'wb') as f:
            pickle.dump(graph, f)

    logger.info(f"Saved graph to {path}")


def load_graph(path: str) -> BidderGraph:
    """Load graph from file."""
    import pickle

    with open(path, 'rb') as f:
        graph = pickle.load(f)

    logger.info(f"Loaded graph from {path}")
    return graph
