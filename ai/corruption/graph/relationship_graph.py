"""
Unified Relationship Graph Engine

Core in-memory graph engine for entity relationship analysis in public procurement.
Uses NetworkX internally for all graph operations.

Supported operations:
- Neighborhood extraction (BFS within N hops)
- Shortest path (Dijkstra)
- PageRank centrality
- Betweenness centrality
- Community detection (Louvain-like)
- Gatekeeper detection
- Revolving door detection

Author: nabavkidata.com
License: Proprietary
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict, deque

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    import community as community_louvain
    LOUVAIN_AVAILABLE = True
except ImportError:
    LOUVAIN_AVAILABLE = False

logger = logging.getLogger(__name__)


class RelationshipGraph:
    """
    In-memory relationship graph engine built on NetworkX.

    Supports heterogeneous edges (co_bidding, buyer_supplier, repeat_partnership,
    value_concentration) between entities (companies, institutions).

    All methods are synchronous since the graph is fully in-memory.

    Usage:
        edges = [
            {"source_id": "CompanyA", "target_id": "CompanyB", "edge_type": "co_bidding", "weight": 5.0, "metadata": {}},
            {"source_id": "InstitutionX", "target_id": "CompanyA", "edge_type": "buyer_supplier", "weight": 3.0, "metadata": {}},
        ]
        graph = RelationshipGraph(edges)
        neighborhood = graph.get_neighborhood("CompanyA", hops=2)
        pr = graph.compute_pagerank()
    """

    def __init__(self, edges: List[Dict[str, Any]]):
        """
        Initialize the relationship graph from a list of edge dicts.

        Args:
            edges: List of edge dicts, each with keys:
                - source_id (str): Source entity identifier
                - target_id (str): Target entity identifier
                - edge_type (str): Relationship type
                - weight (float): Edge weight (higher = stronger)
                - metadata (dict): Additional edge data
        """
        if not NETWORKX_AVAILABLE:
            raise ImportError("networkx is required for RelationshipGraph. Install with: pip install networkx")

        self._graph = nx.MultiDiGraph()
        self._undirected_graph = nx.Graph()
        self._node_types: Dict[str, str] = {}
        self._edge_list = edges

        self._build_graph(edges)
        logger.info(
            f"RelationshipGraph initialized: {self._graph.number_of_nodes()} nodes, "
            f"{self._graph.number_of_edges()} edges"
        )

    def _build_graph(self, edges: List[Dict[str, Any]]) -> None:
        """Build the internal NetworkX graph structures from edge list."""
        for edge in edges:
            source = edge.get("source_id", "")
            target = edge.get("target_id", "")
            edge_type = edge.get("edge_type", "unknown")
            weight = float(edge.get("weight", 1.0))
            metadata = edge.get("metadata", {})
            source_type = edge.get("source_type", "company")
            target_type = edge.get("target_type", "company")
            tender_count = edge.get("tender_count", 0)
            total_value = float(edge.get("total_value", 0))

            if not source or not target:
                continue

            # Track node types
            if source not in self._node_types:
                self._node_types[source] = source_type
            if target not in self._node_types:
                self._node_types[target] = target_type

            # Add to directed multigraph (preserves all edge types)
            self._graph.add_edge(
                source, target,
                key=edge_type,
                edge_type=edge_type,
                weight=weight,
                metadata=metadata,
                tender_count=tender_count,
                total_value=total_value,
            )

            # Add to undirected graph (for community detection and undirected analysis)
            # If edge already exists, accumulate weight
            if self._undirected_graph.has_edge(source, target):
                existing_weight = self._undirected_graph[source][target].get("weight", 0)
                self._undirected_graph[source][target]["weight"] = existing_weight + weight
                # Append edge type to set
                existing_types = self._undirected_graph[source][target].get("edge_types", set())
                existing_types.add(edge_type)
                self._undirected_graph[source][target]["edge_types"] = existing_types
            else:
                self._undirected_graph.add_edge(
                    source, target,
                    weight=weight,
                    edge_types={edge_type},
                )

    def get_neighborhood(self, entity_id: str, hops: int = 2) -> Dict[str, Any]:
        """
        Get the subgraph around an entity within N hops using BFS.

        Args:
            entity_id: The central entity to explore from
            hops: Number of hops (1 = direct connections, 2 = friends-of-friends, etc.)

        Returns:
            Dict with keys:
                - center: The center entity_id
                - nodes: List of node dicts (id, type, depth)
                - edges: List of edge dicts (source, target, edge_type, weight)
                - node_count: Total nodes in subgraph
                - edge_count: Total edges in subgraph
        """
        if entity_id not in self._graph:
            return {
                "center": entity_id,
                "nodes": [],
                "edges": [],
                "node_count": 0,
                "edge_count": 0,
            }

        # BFS to find all nodes within N hops
        visited: Dict[str, int] = {entity_id: 0}  # node -> depth
        queue = deque([(entity_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth >= hops:
                continue

            # Get neighbors from both directed graph (successors + predecessors)
            neighbors = set(self._graph.successors(current)) | set(self._graph.predecessors(current))
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited[neighbor] = depth + 1
                    queue.append((neighbor, depth + 1))

        # Extract nodes
        nodes = []
        node_set = set(visited.keys())
        for node_id, depth in visited.items():
            nodes.append({
                "id": node_id,
                "type": self._node_types.get(node_id, "unknown"),
                "depth": depth,
            })

        # Extract edges between nodes in subgraph
        edges = []
        seen_edges: Set[Tuple[str, str, str]] = set()
        for source, target, key, data in self._graph.edges(keys=True, data=True):
            if source in node_set and target in node_set:
                edge_key = (source, target, key)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": source,
                        "target": target,
                        "edge_type": data.get("edge_type", "unknown"),
                        "weight": data.get("weight", 1.0),
                        "tender_count": data.get("tender_count", 0),
                        "total_value": data.get("total_value", 0),
                        "metadata": data.get("metadata", {}),
                    })

        return {
            "center": entity_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def get_connections(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all direct connections for an entity.

        Args:
            entity_id: The entity to get connections for

        Returns:
            List of connection dicts, each with:
                - connected_entity: The other entity's ID
                - connected_entity_type: The other entity's type
                - direction: 'outgoing', 'incoming', or 'bidirectional'
                - edges: List of edges between them (can have multiple edge types)
        """
        if entity_id not in self._graph:
            return []

        # Collect connections grouped by connected entity
        connections: Dict[str, Dict[str, Any]] = {}

        # Outgoing edges
        for _, target, data in self._graph.out_edges(entity_id, data=True):
            if target not in connections:
                connections[target] = {
                    "connected_entity": target,
                    "connected_entity_type": self._node_types.get(target, "unknown"),
                    "direction": "outgoing",
                    "edges": [],
                }
            connections[target]["edges"].append({
                "edge_type": data.get("edge_type", "unknown"),
                "weight": data.get("weight", 1.0),
                "tender_count": data.get("tender_count", 0),
                "total_value": data.get("total_value", 0),
                "metadata": data.get("metadata", {}),
            })

        # Incoming edges
        for source, _, data in self._graph.in_edges(entity_id, data=True):
            if source not in connections:
                connections[source] = {
                    "connected_entity": source,
                    "connected_entity_type": self._node_types.get(source, "unknown"),
                    "direction": "incoming",
                    "edges": [],
                }
            else:
                # Already has outgoing edge, mark as bidirectional
                connections[source]["direction"] = "bidirectional"

            connections[source]["edges"].append({
                "edge_type": data.get("edge_type", "unknown"),
                "weight": data.get("weight", 1.0),
                "tender_count": data.get("tender_count", 0),
                "total_value": data.get("total_value", 0),
                "metadata": data.get("metadata", {}),
            })

        # Sort by total weight descending
        result = list(connections.values())
        result.sort(key=lambda c: sum(e["weight"] for e in c["edges"]), reverse=True)
        return result

    def shortest_path(self, source_id: str, target_id: str) -> Dict[str, Any]:
        """
        Find the shortest path between two entities using Dijkstra's algorithm.
        Uses inverse weight (1/weight) so stronger connections = shorter distance.

        Args:
            source_id: Starting entity
            target_id: Destination entity

        Returns:
            Dict with keys:
                - found: Whether a path exists
                - path: Ordered list of entity IDs on the path
                - edges: List of edges along the path
                - total_weight: Sum of edge weights along path
                - hop_count: Number of hops
        """
        if source_id not in self._graph or target_id not in self._graph:
            return {
                "found": False,
                "path": [],
                "edges": [],
                "total_weight": 0,
                "hop_count": 0,
                "error": "One or both entities not found in graph",
            }

        # Build a simple weighted graph for path finding
        # Use the undirected graph so paths can traverse any direction
        simple_g = nx.Graph()
        for u, v, data in self._undirected_graph.edges(data=True):
            w = data.get("weight", 1.0)
            # Invert weight: stronger connection = shorter distance
            distance = 1.0 / max(w, 0.001)
            if simple_g.has_edge(u, v):
                # Keep shorter distance (stronger connection)
                if distance < simple_g[u][v]["distance"]:
                    simple_g[u][v]["distance"] = distance
                    simple_g[u][v]["weight"] = w
            else:
                simple_g.add_edge(u, v, distance=distance, weight=w)

        try:
            path = nx.dijkstra_path(simple_g, source_id, target_id, weight="distance")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {
                "found": False,
                "path": [],
                "edges": [],
                "total_weight": 0,
                "hop_count": 0,
            }

        # Build edge list along the path
        edges = []
        total_weight = 0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            # Get all edges between u and v from the directed multigraph
            path_edges = []
            # Check both directions in directed graph
            for src, tgt in [(u, v), (v, u)]:
                if self._graph.has_edge(src, tgt):
                    for key, data in self._graph[src][tgt].items():
                        path_edges.append({
                            "source": src,
                            "target": tgt,
                            "edge_type": data.get("edge_type", key),
                            "weight": data.get("weight", 1.0),
                            "tender_count": data.get("tender_count", 0),
                            "total_value": data.get("total_value", 0),
                        })

            # Pick the strongest edge for the path weight
            if path_edges:
                strongest = max(path_edges, key=lambda e: e["weight"])
                total_weight += strongest["weight"]
                edges.append({
                    "source": u,
                    "target": v,
                    "all_edges": path_edges,
                    "strongest_edge_type": strongest["edge_type"],
                    "strongest_weight": strongest["weight"],
                })

        return {
            "found": True,
            "path": path,
            "edges": edges,
            "total_weight": round(total_weight, 4),
            "hop_count": len(path) - 1,
        }

    def compute_pagerank(self, damping: float = 0.85, iterations: int = 100) -> Dict[str, float]:
        """
        Compute PageRank centrality for all nodes.

        Uses the directed multigraph structure, so edge direction matters.
        Companies frequently awarded contracts by many institutions will have higher PageRank.

        Args:
            damping: Damping factor (default 0.85)
            iterations: Maximum iterations (default 100)

        Returns:
            Dict mapping entity_id -> PageRank score
        """
        if self._graph.number_of_nodes() == 0:
            return {}

        # Convert multigraph to simple digraph for PageRank
        # Collapse multi-edges by summing weights
        simple_g = nx.DiGraph()
        for u, v, data in self._graph.edges(data=True):
            w = data.get("weight", 1.0)
            if simple_g.has_edge(u, v):
                simple_g[u][v]["weight"] += w
            else:
                simple_g.add_edge(u, v, weight=w)

        try:
            pr = nx.pagerank(
                simple_g,
                alpha=damping,
                max_iter=iterations,
                weight="weight",
            )
            return {k: round(v, 8) for k, v in pr.items()}
        except nx.PowerIterationFailedConvergence:
            logger.warning("PageRank did not converge, returning partial results with tol=1e-4")
            pr = nx.pagerank(
                simple_g,
                alpha=damping,
                max_iter=iterations * 2,
                tol=1e-4,
                weight="weight",
            )
            return {k: round(v, 8) for k, v in pr.items()}

    def compute_betweenness_centrality(self) -> Dict[str, float]:
        """
        Compute betweenness centrality for all nodes.

        Betweenness measures how often a node lies on shortest paths between other nodes.
        Entities with high betweenness are "gatekeepers" or "bridges" in the network.

        For large graphs (>5000 nodes), uses sampling for performance.

        Returns:
            Dict mapping entity_id -> betweenness centrality score
        """
        if self._undirected_graph.number_of_nodes() == 0:
            return {}

        n_nodes = self._undirected_graph.number_of_nodes()

        # For large graphs, use sampling to keep computation tractable
        k = None
        if n_nodes > 5000:
            k = min(500, n_nodes)
            logger.info(f"Large graph ({n_nodes} nodes), sampling k={k} for betweenness")
        elif n_nodes > 1000:
            k = min(200, n_nodes)
            logger.info(f"Medium graph ({n_nodes} nodes), sampling k={k} for betweenness")

        bc = nx.betweenness_centrality(
            self._undirected_graph,
            k=k,
            weight="weight",
            normalized=True,
        )
        return {k_: round(v, 8) for k_, v in bc.items()}

    def detect_gatekeepers(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        Detect network gatekeepers -- entities with highest betweenness centrality.

        Gatekeepers bridge different parts of the network and may play
        brokering roles in procurement corruption.

        Args:
            top_n: Number of top gatekeepers to return

        Returns:
            List of dicts with entity_id, entity_type, betweenness, degree, connections
        """
        bc = self.compute_betweenness_centrality()
        if not bc:
            return []

        # Sort by betweenness descending
        sorted_bc = sorted(bc.items(), key=lambda x: x[1], reverse=True)[:top_n]

        gatekeepers = []
        for entity_id, betweenness in sorted_bc:
            if betweenness <= 0:
                continue

            degree = self._undirected_graph.degree(entity_id)
            # Get edge type breakdown
            edge_type_counts: Dict[str, int] = defaultdict(int)
            for _, _, data in self._graph.out_edges(entity_id, data=True):
                edge_type_counts[data.get("edge_type", "unknown")] += 1
            for _, _, data in self._graph.in_edges(entity_id, data=True):
                edge_type_counts[data.get("edge_type", "unknown")] += 1

            gatekeepers.append({
                "entity_id": entity_id,
                "entity_type": self._node_types.get(entity_id, "unknown"),
                "betweenness": round(betweenness, 6),
                "degree": degree,
                "edge_type_breakdown": dict(edge_type_counts),
            })

        return gatekeepers

    def detect_revolving_doors(self) -> List[Dict[str, Any]]:
        """
        Detect entities that appear on both buyer and supplier sides of buyer_supplier edges.

        "Revolving door" entities might be individuals or companies that serve as both
        procuring entities and suppliers, which can indicate conflicts of interest.

        Returns:
            List of dicts with entity_id, buyer_count, supplier_count, overlap_tenders
        """
        # Collect who appears as buyer (source of buyer_supplier) and supplier (target of buyer_supplier)
        buyers: Dict[str, int] = defaultdict(int)
        suppliers: Dict[str, int] = defaultdict(int)
        buyer_values: Dict[str, float] = defaultdict(float)
        supplier_values: Dict[str, float] = defaultdict(float)

        for source, target, data in self._graph.edges(data=True):
            if data.get("edge_type") != "buyer_supplier":
                continue

            buyers[source] += 1
            suppliers[target] += 1
            buyer_values[source] += data.get("total_value", 0)
            supplier_values[target] += data.get("total_value", 0)

        # Find entities that appear on both sides
        buyer_set = set(buyers.keys())
        supplier_set = set(suppliers.keys())
        revolving_doors = buyer_set & supplier_set

        results = []
        for entity_id in revolving_doors:
            results.append({
                "entity_id": entity_id,
                "entity_type": self._node_types.get(entity_id, "unknown"),
                "buyer_edge_count": buyers[entity_id],
                "supplier_edge_count": suppliers[entity_id],
                "total_buyer_value": round(buyer_values[entity_id], 2),
                "total_supplier_value": round(supplier_values[entity_id], 2),
                "risk_indicator": "Entity appears as both buyer and supplier in procurement network",
            })

        # Sort by combined count descending
        results.sort(
            key=lambda r: r["buyer_edge_count"] + r["supplier_edge_count"],
            reverse=True,
        )
        return results

    def detect_communities(self, resolution: float = 1.0) -> List[Dict[str, Any]]:
        """
        Detect communities/clusters using Louvain algorithm or fallback label propagation.

        Higher resolution parameter produces more, smaller communities.

        Args:
            resolution: Resolution parameter for Louvain (default 1.0)
                        Higher values = more communities, lower = fewer

        Returns:
            List of community dicts, each with:
                - community_id: Integer community identifier
                - members: List of entity IDs in the community
                - member_count: Number of members
                - internal_edge_count: Edges within the community
                - edge_types: Breakdown of edge types within community
        """
        if self._undirected_graph.number_of_nodes() == 0:
            return []

        # Try Louvain first (better quality), fall back to label propagation
        partition: Dict[str, int] = {}
        method_used = "unknown"

        if LOUVAIN_AVAILABLE:
            try:
                partition = community_louvain.best_partition(
                    self._undirected_graph,
                    weight="weight",
                    resolution=resolution,
                    random_state=42,
                )
                method_used = "louvain"
            except Exception as e:
                logger.warning(f"Louvain community detection failed: {e}, falling back to label propagation")

        if not partition:
            # Fallback: label propagation (always available in NetworkX)
            try:
                communities_generator = nx.algorithms.community.label_propagation_communities(
                    self._undirected_graph
                )
                for i, comm in enumerate(communities_generator):
                    for node in comm:
                        partition[node] = i
                method_used = "label_propagation"
            except Exception as e:
                logger.error(f"Label propagation also failed: {e}")
                return []

        # Group nodes by community
        community_members: Dict[int, List[str]] = defaultdict(list)
        for node, comm_id in partition.items():
            community_members[comm_id].append(node)

        # Build community details
        communities = []
        for comm_id, members in community_members.items():
            member_set = set(members)

            # Count internal edges and edge types
            internal_edge_count = 0
            edge_type_counts: Dict[str, int] = defaultdict(int)

            for u, v, data in self._graph.edges(data=True):
                if u in member_set and v in member_set:
                    internal_edge_count += 1
                    edge_type_counts[data.get("edge_type", "unknown")] += 1

            communities.append({
                "community_id": comm_id,
                "members": sorted(members),
                "member_count": len(members),
                "internal_edge_count": internal_edge_count,
                "edge_types": dict(edge_type_counts),
                "detection_method": method_used,
            })

        # Sort by member count descending
        communities.sort(key=lambda c: c["member_count"], reverse=True)
        return communities

    def get_node_community_map(self, resolution: float = 1.0) -> Dict[str, int]:
        """
        Get a mapping of entity_id -> community_id.

        Useful for bulk-writing community assignments to the database.

        Args:
            resolution: Resolution parameter for Louvain

        Returns:
            Dict mapping entity_id -> community_id
        """
        if self._undirected_graph.number_of_nodes() == 0:
            return {}

        if LOUVAIN_AVAILABLE:
            try:
                return community_louvain.best_partition(
                    self._undirected_graph,
                    weight="weight",
                    resolution=resolution,
                    random_state=42,
                )
            except Exception as e:
                logger.warning(f"Louvain failed: {e}")

        # Fallback
        partition = {}
        try:
            for i, comm in enumerate(
                nx.algorithms.community.label_propagation_communities(self._undirected_graph)
            ):
                for node in comm:
                    partition[node] = i
        except Exception as e:
            logger.error(f"Community detection failed entirely: {e}")

        return partition

    def get_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics for the graph.

        Returns:
            Dict with:
                - node_count: Total number of nodes
                - edge_count: Total number of edges (in directed multigraph)
                - unique_edge_count: Unique edges (in undirected graph)
                - density: Graph density
                - connected_components: Number of connected components
                - largest_component_size: Size of largest connected component
                - node_type_counts: Breakdown by node type
                - edge_type_counts: Breakdown by edge type
                - avg_degree: Average node degree
        """
        n_nodes = self._graph.number_of_nodes()
        n_edges = self._graph.number_of_edges()
        n_undirected_edges = self._undirected_graph.number_of_edges()

        # Node type breakdown
        node_type_counts: Dict[str, int] = defaultdict(int)
        for _, ntype in self._node_types.items():
            node_type_counts[ntype] += 1

        # Edge type breakdown
        edge_type_counts: Dict[str, int] = defaultdict(int)
        for _, _, data in self._graph.edges(data=True):
            edge_type_counts[data.get("edge_type", "unknown")] += 1

        # Connected components (use undirected graph)
        if n_nodes > 0:
            components = list(nx.connected_components(self._undirected_graph))
            n_components = len(components)
            largest_component = max(len(c) for c in components) if components else 0
        else:
            n_components = 0
            largest_component = 0

        # Density
        density = nx.density(self._undirected_graph) if n_nodes > 1 else 0

        # Average degree
        if n_nodes > 0:
            degrees = [d for _, d in self._undirected_graph.degree()]
            avg_degree = sum(degrees) / len(degrees)
        else:
            avg_degree = 0

        return {
            "node_count": n_nodes,
            "edge_count": n_edges,
            "unique_edge_count": n_undirected_edges,
            "density": round(density, 6),
            "connected_components": n_components,
            "largest_component_size": largest_component,
            "node_type_counts": dict(node_type_counts),
            "edge_type_counts": dict(edge_type_counts),
            "avg_degree": round(avg_degree, 2),
        }

    def get_node_type(self, entity_id: str) -> str:
        """Get the type of a node."""
        return self._node_types.get(entity_id, "unknown")

    def has_node(self, entity_id: str) -> bool:
        """Check if entity exists in graph."""
        return entity_id in self._graph

    def node_count(self) -> int:
        """Get total node count."""
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        """Get total edge count."""
        return self._graph.number_of_edges()
