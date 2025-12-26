"""
Collusion Cluster Detector

Detects collusion networks in public procurement using:
1. GNN embeddings + clustering (HDBSCAN, spectral)
2. Community detection (Louvain, Label Propagation)
3. Pattern-based detection (bid rotation, cover bidding)

Output: List of suspected collusion clusters with evidence and confidence scores.

Detection Methods:
- Structural: Dense subgraphs, cliques, community detection
- Behavioral: Bid rotation patterns, cover bidding, winner taketurns
- Embedding: GNN embeddings clustered to find similar companies

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

# Optional imports
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    from sklearn.cluster import SpectralClustering, DBSCAN, KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import community as community_louvain
    LOUVAIN_AVAILABLE = True
except ImportError:
    LOUVAIN_AVAILABLE = False

try:
    from hdbscan import HDBSCAN
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class CollusionEvidence:
    """Evidence supporting a collusion detection."""
    evidence_type: str  # 'structural', 'behavioral', 'embedding', 'pattern'
    description: str
    score: float  # 0-100
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'evidence_type': self.evidence_type,
            'description': self.description,
            'score': round(self.score, 2),
            'details': self.details
        }


@dataclass
class CollusionCluster:
    """
    A detected collusion cluster.

    Attributes:
        cluster_id: Unique identifier
        companies: List of company names in the cluster
        confidence: Overall confidence score (0-100)
        detection_method: How the cluster was detected
        evidence: List of evidence items
        pattern_type: Type of collusion pattern detected
        risk_level: 'low', 'medium', 'high', 'critical'
        common_tenders: Tenders where these companies bid together
        common_institutions: Institutions where they operate
        metadata: Additional information
    """
    cluster_id: str
    companies: List[str]
    confidence: float
    detection_method: str
    evidence: List[CollusionEvidence]
    pattern_type: str  # 'bid_rotation', 'cover_bidding', 'market_allocation', 'bid_suppression'
    risk_level: str
    common_tenders: List[str] = field(default_factory=list)
    common_institutions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cluster_id': self.cluster_id,
            'companies': self.companies,
            'confidence': round(self.confidence, 2),
            'detection_method': self.detection_method,
            'evidence': [e.to_dict() for e in self.evidence],
            'pattern_type': self.pattern_type,
            'risk_level': self.risk_level,
            'common_tenders': self.common_tenders[:10],  # Limit for output
            'common_institutions': self.common_institutions,
            'num_companies': len(self.companies),
            'metadata': self.metadata
        }


class CollusionClusterDetector:
    """
    Detects collusion clusters using multiple methods.

    Methods:
    1. Community Detection: Louvain, Label Propagation on co-bidding graph
    2. Embedding Clustering: Cluster GNN embeddings with HDBSCAN/Spectral
    3. Pattern Detection: Bid rotation, cover bidding patterns
    4. Structural Analysis: Dense subgraphs, cliques

    Usage:
        detector = CollusionClusterDetector(pool)
        clusters = await detector.detect_all(graph, embeddings)
        for cluster in clusters:
            print(f"Cluster {cluster.cluster_id}: {cluster.companies}")
            print(f"Confidence: {cluster.confidence}%")
            print(f"Pattern: {cluster.pattern_type}")
    """

    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize collusion detector.

        Args:
            pool: AsyncPG connection pool for database queries
        """
        self.pool = pool
        self.cluster_id_counter = 0
        logger.info("CollusionClusterDetector initialized")

    # =========================================================================
    # Main Detection Methods
    # =========================================================================

    async def detect_all(
        self,
        graph,  # BidderGraph from graph_builder
        embeddings: Optional[np.ndarray] = None,
        min_cluster_size: int = 3,
        min_confidence: float = 50.0
    ) -> List[CollusionCluster]:
        """
        Run all detection methods and combine results.

        Args:
            graph: BidderGraph object from graph_builder
            embeddings: Optional GNN embeddings [num_nodes, dim]
            min_cluster_size: Minimum companies in a cluster
            min_confidence: Minimum confidence to report

        Returns:
            List of CollusionCluster objects sorted by confidence
        """
        all_clusters = []

        # 1. Community Detection
        community_clusters = await self.detect_communities(graph, min_cluster_size)
        all_clusters.extend(community_clusters)
        logger.info(f"Community detection found {len(community_clusters)} clusters")

        # 2. Embedding-based Clustering
        if embeddings is not None:
            embedding_clusters = await self.detect_from_embeddings(
                graph, embeddings, min_cluster_size
            )
            all_clusters.extend(embedding_clusters)
            logger.info(f"Embedding clustering found {len(embedding_clusters)} clusters")

        # 3. Pattern Detection
        pattern_clusters = await self.detect_bid_patterns(graph, min_cluster_size)
        all_clusters.extend(pattern_clusters)
        logger.info(f"Pattern detection found {len(pattern_clusters)} clusters")

        # 4. Dense Subgraph Detection
        dense_clusters = await self.detect_dense_subgraphs(graph, min_cluster_size)
        all_clusters.extend(dense_clusters)
        logger.info(f"Dense subgraph detection found {len(dense_clusters)} clusters")

        # Merge overlapping clusters
        merged_clusters = self._merge_overlapping_clusters(all_clusters)

        # Filter by confidence and validate
        validated_clusters = []
        for cluster in merged_clusters:
            if cluster.confidence >= min_confidence:
                # Enrich with database information
                cluster = await self._enrich_cluster(cluster)
                validated_clusters.append(cluster)

        # Sort by confidence
        validated_clusters.sort(key=lambda c: c.confidence, reverse=True)

        logger.info(f"Total detected clusters: {len(validated_clusters)}")
        return validated_clusters

    async def detect_communities(
        self,
        graph,
        min_cluster_size: int = 3
    ) -> List[CollusionCluster]:
        """
        Detect communities using Louvain and Label Propagation.

        Args:
            graph: BidderGraph object
            min_cluster_size: Minimum cluster size

        Returns:
            List of CollusionCluster objects
        """
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available for community detection")
            return []

        G = graph.to_networkx()
        if G is None or len(G) < min_cluster_size:
            return []

        clusters = []

        # Louvain community detection
        if LOUVAIN_AVAILABLE:
            try:
                partition = community_louvain.best_partition(G, resolution=1.2)
                communities = defaultdict(list)
                for node, comm_id in partition.items():
                    communities[comm_id].append(node)

                for comm_id, nodes in communities.items():
                    if len(nodes) >= min_cluster_size:
                        companies = [graph.nodes[n].name for n in nodes if n < len(graph.nodes)]

                        # Calculate internal density
                        subgraph = G.subgraph(nodes)
                        density = nx.density(subgraph)

                        if density > 0.3:  # Only report dense communities
                            confidence = min(100, density * 100 + len(nodes) * 5)

                            evidence = [
                                CollusionEvidence(
                                    evidence_type='structural',
                                    description=f"Dense community with {len(nodes)} companies",
                                    score=confidence,
                                    details={
                                        'density': round(density, 3),
                                        'modularity': community_louvain.modularity(partition, G)
                                    }
                                )
                            ]

                            cluster = CollusionCluster(
                                cluster_id=self._generate_cluster_id(),
                                companies=companies,
                                confidence=confidence,
                                detection_method='louvain_community',
                                evidence=evidence,
                                pattern_type='bid_clustering',
                                risk_level=self._calculate_risk_level(confidence)
                            )
                            clusters.append(cluster)

            except Exception as e:
                logger.warning(f"Louvain detection failed: {e}")

        # Label Propagation
        try:
            lp_communities = list(nx.community.label_propagation_communities(G))

            for comm in lp_communities:
                if len(comm) >= min_cluster_size:
                    nodes = list(comm)
                    companies = [graph.nodes[n].name for n in nodes if n < len(graph.nodes)]

                    subgraph = G.subgraph(nodes)
                    density = nx.density(subgraph)

                    if density > 0.3:
                        confidence = min(100, density * 80 + len(nodes) * 3)

                        evidence = [
                            CollusionEvidence(
                                evidence_type='structural',
                                description=f"Label propagation community: {len(nodes)} companies",
                                score=confidence,
                                details={'density': round(density, 3)}
                            )
                        ]

                        cluster = CollusionCluster(
                            cluster_id=self._generate_cluster_id(),
                            companies=companies,
                            confidence=confidence,
                            detection_method='label_propagation',
                            evidence=evidence,
                            pattern_type='bid_clustering',
                            risk_level=self._calculate_risk_level(confidence)
                        )
                        clusters.append(cluster)

        except Exception as e:
            logger.warning(f"Label propagation failed: {e}")

        return clusters

    async def detect_from_embeddings(
        self,
        graph,
        embeddings: np.ndarray,
        min_cluster_size: int = 3
    ) -> List[CollusionCluster]:
        """
        Cluster GNN embeddings to find similar companies.

        Args:
            graph: BidderGraph object
            embeddings: Node embeddings [num_nodes, dim]
            min_cluster_size: Minimum cluster size

        Returns:
            List of CollusionCluster objects
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available for embedding clustering")
            return []

        clusters = []

        # Normalize embeddings
        scaler = StandardScaler()
        embeddings_scaled = scaler.fit_transform(embeddings)

        # HDBSCAN (density-based, finds natural clusters)
        if HDBSCAN_AVAILABLE:
            try:
                clusterer = HDBSCAN(
                    min_cluster_size=min_cluster_size,
                    min_samples=2,
                    metric='euclidean'
                )
                labels = clusterer.fit_predict(embeddings_scaled)

                unique_labels = set(labels) - {-1}  # -1 is noise

                for label in unique_labels:
                    indices = np.where(labels == label)[0]

                    if len(indices) >= min_cluster_size:
                        companies = [
                            graph.nodes[i].name
                            for i in indices
                            if i < len(graph.nodes)
                        ]

                        # Calculate cluster cohesion
                        cluster_embeddings = embeddings_scaled[indices]
                        centroid = cluster_embeddings.mean(axis=0)
                        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
                        cohesion = 1.0 / (1.0 + distances.mean())

                        confidence = min(100, cohesion * 80 + len(indices) * 2)

                        evidence = [
                            CollusionEvidence(
                                evidence_type='embedding',
                                description=f"Companies with similar GNN embeddings",
                                score=confidence,
                                details={
                                    'cohesion': round(cohesion, 3),
                                    'avg_distance': round(distances.mean(), 3)
                                }
                            )
                        ]

                        cluster = CollusionCluster(
                            cluster_id=self._generate_cluster_id(),
                            companies=companies,
                            confidence=confidence,
                            detection_method='hdbscan_embedding',
                            evidence=evidence,
                            pattern_type='similar_behavior',
                            risk_level=self._calculate_risk_level(confidence)
                        )
                        clusters.append(cluster)

            except Exception as e:
                logger.warning(f"HDBSCAN clustering failed: {e}")

        # Spectral Clustering (for smaller graphs)
        if len(embeddings) <= 5000:
            try:
                # Determine optimal number of clusters
                best_score = -1
                best_labels = None
                best_k = 2

                for k in range(2, min(10, len(embeddings) // min_cluster_size)):
                    spectral = SpectralClustering(
                        n_clusters=k,
                        affinity='nearest_neighbors',
                        n_neighbors=min(10, len(embeddings) - 1),
                        random_state=42
                    )
                    labels = spectral.fit_predict(embeddings_scaled)

                    if len(set(labels)) > 1:
                        score = silhouette_score(embeddings_scaled, labels)
                        if score > best_score:
                            best_score = score
                            best_labels = labels
                            best_k = k

                if best_labels is not None and best_score > 0.3:
                    for label in range(best_k):
                        indices = np.where(best_labels == label)[0]

                        if len(indices) >= min_cluster_size:
                            companies = [
                                graph.nodes[i].name
                                for i in indices
                                if i < len(graph.nodes)
                            ]

                            confidence = min(100, best_score * 100)

                            evidence = [
                                CollusionEvidence(
                                    evidence_type='embedding',
                                    description=f"Spectral cluster with high silhouette score",
                                    score=confidence,
                                    details={
                                        'silhouette_score': round(best_score, 3),
                                        'n_clusters': best_k
                                    }
                                )
                            ]

                            cluster = CollusionCluster(
                                cluster_id=self._generate_cluster_id(),
                                companies=companies,
                                confidence=confidence,
                                detection_method='spectral_clustering',
                                evidence=evidence,
                                pattern_type='similar_behavior',
                                risk_level=self._calculate_risk_level(confidence)
                            )
                            clusters.append(cluster)

            except Exception as e:
                logger.warning(f"Spectral clustering failed: {e}")

        return clusters

    async def detect_bid_patterns(
        self,
        graph,
        min_cluster_size: int = 3
    ) -> List[CollusionCluster]:
        """
        Detect collusion patterns: bid rotation, cover bidding, etc.

        Args:
            graph: BidderGraph object
            min_cluster_size: Minimum cluster size

        Returns:
            List of CollusionCluster objects
        """
        clusters = []

        # Get all company names from graph
        company_names = [n.name for n in graph.nodes if n.node_type == 'bidder']

        if len(company_names) < min_cluster_size:
            return []

        # 1. Bid Rotation Detection
        rotation_clusters = await self._detect_bid_rotation(company_names, min_cluster_size)
        clusters.extend(rotation_clusters)

        # 2. Cover Bidding Detection
        cover_clusters = await self._detect_cover_bidding(company_names, min_cluster_size)
        clusters.extend(cover_clusters)

        # 3. Market Allocation Detection
        allocation_clusters = await self._detect_market_allocation(company_names, min_cluster_size)
        clusters.extend(allocation_clusters)

        return clusters

    async def _detect_bid_rotation(
        self,
        companies: List[str],
        min_cluster_size: int
    ) -> List[CollusionCluster]:
        """
        Detect bid rotation: companies take turns winning.

        Pattern: Company A wins, then B, then C, then A again, in sequence.
        """
        query = """
            WITH company_wins AS (
                SELECT
                    t.tender_id,
                    t.winner,
                    t.publication_date,
                    t.procuring_entity,
                    array_agg(tb.company_name ORDER BY tb.company_name) as bidders
                FROM tenders t
                JOIN tender_bidders tb ON t.tender_id = tb.tender_id
                WHERE t.winner = ANY($1::text[])
                  AND t.status IN ('awarded', 'completed')
                  AND t.publication_date >= CURRENT_DATE - INTERVAL '24 months'
                GROUP BY t.tender_id, t.winner, t.publication_date, t.procuring_entity
                ORDER BY t.publication_date
            ),
            sequential_wins AS (
                SELECT
                    winner,
                    bidders,
                    procuring_entity,
                    publication_date,
                    LAG(winner) OVER (
                        PARTITION BY bidders
                        ORDER BY publication_date
                    ) as prev_winner,
                    LEAD(winner) OVER (
                        PARTITION BY bidders
                        ORDER BY publication_date
                    ) as next_winner
                FROM company_wins
            )
            SELECT
                bidders,
                array_agg(DISTINCT winner) as winners,
                COUNT(*) as total_tenders,
                COUNT(DISTINCT winner) as distinct_winners,
                array_agg(DISTINCT procuring_entity) as institutions
            FROM sequential_wins
            WHERE array_length(bidders, 1) >= $2
            GROUP BY bidders
            HAVING COUNT(DISTINCT winner) >= 2
               AND COUNT(*) >= 4
               AND COUNT(DISTINCT winner)::float / COUNT(*) > 0.3
        """

        clusters = []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, companies, min_cluster_size)

            for row in rows:
                bidders = list(row['bidders'])
                winners = list(row['winners'])
                total = row['total_tenders']
                distinct_winners = row['distinct_winners']

                # Calculate rotation score
                # Higher if wins are evenly distributed among bidders
                win_distribution = distinct_winners / len(bidders)
                rotation_score = win_distribution * 100

                if rotation_score >= 40:
                    confidence = min(100, rotation_score + total * 2)

                    evidence = [
                        CollusionEvidence(
                            evidence_type='behavioral',
                            description=f"Bid rotation pattern: {distinct_winners} winners among {len(bidders)} bidders in {total} tenders",
                            score=confidence,
                            details={
                                'total_tenders': total,
                                'distinct_winners': distinct_winners,
                                'win_distribution': round(win_distribution, 2)
                            }
                        )
                    ]

                    cluster = CollusionCluster(
                        cluster_id=self._generate_cluster_id(),
                        companies=bidders,
                        confidence=confidence,
                        detection_method='bid_rotation_analysis',
                        evidence=evidence,
                        pattern_type='bid_rotation',
                        risk_level=self._calculate_risk_level(confidence),
                        common_institutions=list(row['institutions'])
                    )
                    clusters.append(cluster)

        return clusters

    async def _detect_cover_bidding(
        self,
        companies: List[str],
        min_cluster_size: int
    ) -> List[CollusionCluster]:
        """
        Detect cover bidding: companies submit artificially high bids
        to ensure a designated winner.

        Pattern: Same losers always bid significantly higher than winner.
        """
        query = """
            WITH bid_data AS (
                SELECT
                    tb.tender_id,
                    tb.company_name,
                    tb.bid_amount_mkd,
                    tb.is_winner,
                    t.actual_value_mkd,
                    t.winner
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE tb.company_name = ANY($1::text[])
                  AND t.status IN ('awarded', 'completed')
                  AND tb.bid_amount_mkd > 0
                  AND t.actual_value_mkd > 0
            ),
            bid_ratios AS (
                SELECT
                    tender_id,
                    company_name,
                    bid_amount_mkd,
                    actual_value_mkd,
                    is_winner,
                    winner,
                    bid_amount_mkd / actual_value_mkd as bid_ratio
                FROM bid_data
            ),
            cover_patterns AS (
                SELECT
                    company_name as cover_bidder,
                    winner as designated_winner,
                    COUNT(*) as occurrences,
                    AVG(bid_ratio) as avg_bid_ratio,
                    STDDEV(bid_ratio) as stddev_ratio
                FROM bid_ratios
                WHERE is_winner = FALSE
                  AND bid_ratio > 1.1  -- Bid at least 10% higher
                  AND winner IS NOT NULL
                GROUP BY company_name, winner
                HAVING COUNT(*) >= 3
            )
            SELECT
                designated_winner,
                array_agg(cover_bidder) as cover_bidders,
                SUM(occurrences) as total_occurrences,
                AVG(avg_bid_ratio) as overall_avg_ratio
            FROM cover_patterns
            WHERE avg_bid_ratio > 1.15
              AND stddev_ratio < 0.3  -- Consistent overbidding
            GROUP BY designated_winner
            HAVING array_length(array_agg(cover_bidder), 1) >= $2 - 1
        """

        clusters = []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, companies, min_cluster_size)

            for row in rows:
                designated_winner = row['designated_winner']
                cover_bidders = list(row['cover_bidders'])
                all_companies = [designated_winner] + cover_bidders

                confidence = min(100, (row['overall_avg_ratio'] - 1) * 200 + row['total_occurrences'] * 3)

                evidence = [
                    CollusionEvidence(
                        evidence_type='behavioral',
                        description=f"Cover bidding: {len(cover_bidders)} companies consistently bid {((row['overall_avg_ratio']-1)*100):.0f}% higher than winner",
                        score=confidence,
                        details={
                            'designated_winner': designated_winner,
                            'avg_overbid_ratio': round(row['overall_avg_ratio'], 2),
                            'total_occurrences': row['total_occurrences']
                        }
                    )
                ]

                cluster = CollusionCluster(
                    cluster_id=self._generate_cluster_id(),
                    companies=all_companies,
                    confidence=confidence,
                    detection_method='cover_bidding_analysis',
                    evidence=evidence,
                    pattern_type='cover_bidding',
                    risk_level=self._calculate_risk_level(confidence)
                )
                clusters.append(cluster)

        return clusters

    async def _detect_market_allocation(
        self,
        companies: List[str],
        min_cluster_size: int
    ) -> List[CollusionCluster]:
        """
        Detect market allocation: companies divide geographic or
        institutional markets.

        Pattern: Companies only win at specific institutions, never competing directly.
        """
        query = """
            WITH company_institution_wins AS (
                SELECT
                    t.winner,
                    t.procuring_entity,
                    COUNT(*) as wins
                FROM tenders t
                WHERE t.winner = ANY($1::text[])
                  AND t.status IN ('awarded', 'completed')
                  AND t.publication_date >= CURRENT_DATE - INTERVAL '24 months'
                GROUP BY t.winner, t.procuring_entity
                HAVING COUNT(*) >= 2
            ),
            institution_winners AS (
                SELECT
                    procuring_entity,
                    array_agg(winner ORDER BY wins DESC) as winners,
                    array_agg(wins ORDER BY wins DESC) as win_counts
                FROM company_institution_wins
                GROUP BY procuring_entity
                HAVING COUNT(DISTINCT winner) >= 2
            ),
            potential_allocs AS (
                SELECT
                    w1.winner as company_a,
                    w2.winner as company_b,
                    COUNT(DISTINCT i1.procuring_entity) FILTER (WHERE i1.procuring_entity != i2.procuring_entity) as separate_institutions,
                    COUNT(DISTINCT i1.procuring_entity) FILTER (WHERE i1.procuring_entity = i2.procuring_entity) as shared_institutions
                FROM company_institution_wins w1
                JOIN company_institution_wins w2 ON w1.winner < w2.winner
                LEFT JOIN institution_winners i1 ON w1.winner = ANY(i1.winners)
                LEFT JOIN institution_winners i2 ON w2.winner = ANY(i2.winners)
                GROUP BY w1.winner, w2.winner
            )
            SELECT *
            FROM potential_allocs
            WHERE separate_institutions > 0
              AND shared_institutions = 0
        """

        clusters = []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, companies)

            # Build clusters from pairs
            allocation_graph = defaultdict(set)
            for row in rows:
                allocation_graph[row['company_a']].add(row['company_b'])
                allocation_graph[row['company_b']].add(row['company_a'])

            # Find connected components (companies that allocate markets together)
            visited = set()
            for start_company in allocation_graph:
                if start_company in visited:
                    continue

                component = []
                stack = [start_company]
                while stack:
                    company = stack.pop()
                    if company in visited:
                        continue
                    visited.add(company)
                    component.append(company)
                    stack.extend(allocation_graph[company] - visited)

                if len(component) >= min_cluster_size:
                    confidence = min(100, len(component) * 20 + 40)

                    evidence = [
                        CollusionEvidence(
                            evidence_type='behavioral',
                            description=f"Market allocation: {len(component)} companies winning at separate institutions",
                            score=confidence,
                            details={'num_companies': len(component)}
                        )
                    ]

                    cluster = CollusionCluster(
                        cluster_id=self._generate_cluster_id(),
                        companies=component,
                        confidence=confidence,
                        detection_method='market_allocation_analysis',
                        evidence=evidence,
                        pattern_type='market_allocation',
                        risk_level=self._calculate_risk_level(confidence)
                    )
                    clusters.append(cluster)

        return clusters

    async def detect_dense_subgraphs(
        self,
        graph,
        min_cluster_size: int = 3,
        min_density: float = 0.5
    ) -> List[CollusionCluster]:
        """
        Find dense subgraphs (cliques and near-cliques).

        Args:
            graph: BidderGraph object
            min_cluster_size: Minimum cluster size
            min_density: Minimum edge density

        Returns:
            List of CollusionCluster objects
        """
        if not NETWORKX_AVAILABLE:
            return []

        G = graph.to_networkx()
        if G is None or len(G) < min_cluster_size:
            return []

        clusters = []

        # Find all cliques
        cliques = list(nx.find_cliques(G))

        for clique in cliques:
            if len(clique) >= min_cluster_size:
                companies = [graph.nodes[n].name for n in clique if n < len(graph.nodes)]

                # Cliques are complete graphs (density = 1.0)
                confidence = min(100, 70 + len(clique) * 5)

                evidence = [
                    CollusionEvidence(
                        evidence_type='structural',
                        description=f"Complete clique of {len(clique)} companies (all bid together)",
                        score=confidence,
                        details={
                            'clique_size': len(clique),
                            'density': 1.0
                        }
                    )
                ]

                cluster = CollusionCluster(
                    cluster_id=self._generate_cluster_id(),
                    companies=companies,
                    confidence=confidence,
                    detection_method='clique_detection',
                    evidence=evidence,
                    pattern_type='bid_clustering',
                    risk_level=self._calculate_risk_level(confidence)
                )
                clusters.append(cluster)

        # Find k-cores (nodes with at least k neighbors within the subgraph)
        for k in range(3, min(10, len(G) // 2)):
            try:
                k_core = nx.k_core(G, k=k)
                if len(k_core) >= min_cluster_size:
                    density = nx.density(k_core)
                    if density >= min_density:
                        companies = [
                            graph.nodes[n].name
                            for n in k_core.nodes()
                            if n < len(graph.nodes)
                        ]

                        confidence = min(100, density * 80 + k * 10)

                        evidence = [
                            CollusionEvidence(
                                evidence_type='structural',
                                description=f"{k}-core subgraph with {len(k_core)} companies",
                                score=confidence,
                                details={
                                    'k_value': k,
                                    'density': round(density, 3)
                                }
                            )
                        ]

                        cluster = CollusionCluster(
                            cluster_id=self._generate_cluster_id(),
                            companies=companies,
                            confidence=confidence,
                            detection_method='k_core_detection',
                            evidence=evidence,
                            pattern_type='bid_clustering',
                            risk_level=self._calculate_risk_level(confidence)
                        )
                        clusters.append(cluster)

            except Exception as e:
                logger.debug(f"k-core detection for k={k} failed: {e}")
                break

        return clusters

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _generate_cluster_id(self) -> str:
        """Generate unique cluster ID."""
        self.cluster_id_counter += 1
        return f"CL-{datetime.utcnow().strftime('%Y%m%d')}-{self.cluster_id_counter:04d}"

    def _calculate_risk_level(self, confidence: float) -> str:
        """Calculate risk level from confidence score."""
        if confidence >= 80:
            return 'critical'
        elif confidence >= 60:
            return 'high'
        elif confidence >= 40:
            return 'medium'
        else:
            return 'low'

    def _merge_overlapping_clusters(
        self,
        clusters: List[CollusionCluster],
        overlap_threshold: float = 0.6
    ) -> List[CollusionCluster]:
        """
        Merge clusters with significant overlap.

        Args:
            clusters: List of clusters to merge
            overlap_threshold: Jaccard similarity threshold for merging

        Returns:
            Merged list of clusters
        """
        if len(clusters) <= 1:
            return clusters

        # Sort by confidence
        clusters = sorted(clusters, key=lambda c: c.confidence, reverse=True)

        merged = []
        used = set()

        for i, cluster in enumerate(clusters):
            if i in used:
                continue

            # Find overlapping clusters
            companies_set = set(cluster.companies)
            to_merge = [cluster]

            for j, other in enumerate(clusters[i+1:], start=i+1):
                if j in used:
                    continue

                other_set = set(other.companies)
                intersection = companies_set & other_set
                union = companies_set | other_set

                jaccard = len(intersection) / len(union) if union else 0

                if jaccard >= overlap_threshold:
                    to_merge.append(other)
                    companies_set = union
                    used.add(j)

            # Merge clusters
            if len(to_merge) == 1:
                merged.append(cluster)
            else:
                merged_cluster = self._merge_cluster_list(to_merge)
                merged.append(merged_cluster)

            used.add(i)

        return merged

    def _merge_cluster_list(self, clusters: List[CollusionCluster]) -> CollusionCluster:
        """Merge multiple clusters into one."""
        all_companies = set()
        all_evidence = []
        all_tenders = []
        all_institutions = []
        detection_methods = set()
        pattern_types = set()

        for cluster in clusters:
            all_companies.update(cluster.companies)
            all_evidence.extend(cluster.evidence)
            all_tenders.extend(cluster.common_tenders)
            all_institutions.extend(cluster.common_institutions)
            detection_methods.add(cluster.detection_method)
            pattern_types.add(cluster.pattern_type)

        # Take highest confidence
        max_confidence = max(c.confidence for c in clusters)

        return CollusionCluster(
            cluster_id=self._generate_cluster_id(),
            companies=list(all_companies),
            confidence=max_confidence,
            detection_method=', '.join(detection_methods),
            evidence=all_evidence,
            pattern_type=', '.join(pattern_types),
            risk_level=self._calculate_risk_level(max_confidence),
            common_tenders=list(set(all_tenders)),
            common_institutions=list(set(all_institutions)),
            metadata={'merged_from': len(clusters)}
        )

    async def _enrich_cluster(self, cluster: CollusionCluster) -> CollusionCluster:
        """
        Enrich cluster with additional database information.

        Adds:
        - Common tenders
        - Common institutions
        - Total contract value
        - Win statistics
        """
        query = """
            WITH cluster_companies AS (
                SELECT unnest($1::text[]) as company_name
            ),
            company_activity AS (
                SELECT
                    tb.tender_id,
                    t.procuring_entity,
                    t.title,
                    t.actual_value_mkd,
                    t.publication_date,
                    array_agg(tb.company_name) as bidders,
                    array_agg(tb.company_name) FILTER (WHERE tb.is_winner) as winners
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE tb.company_name IN (SELECT company_name FROM cluster_companies)
                  AND t.publication_date >= CURRENT_DATE - INTERVAL '24 months'
                GROUP BY tb.tender_id, t.procuring_entity, t.title, t.actual_value_mkd, t.publication_date
                HAVING COUNT(DISTINCT tb.company_name) >= 2
            )
            SELECT
                array_agg(DISTINCT tender_id) as common_tenders,
                array_agg(DISTINCT procuring_entity) as institutions,
                SUM(COALESCE(actual_value_mkd, 0)) as total_value,
                COUNT(*) as num_tenders
            FROM company_activity
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, cluster.companies)

            if row:
                cluster.common_tenders = list(row['common_tenders'] or [])[:10]
                cluster.common_institutions = list(row['institutions'] or [])
                cluster.metadata['total_contract_value_mkd'] = float(row['total_value'] or 0)
                cluster.metadata['num_common_tenders'] = row['num_tenders']

        return cluster

    async def save_clusters_to_db(self, clusters: List[CollusionCluster]) -> int:
        """
        Save detected clusters to company_relationships table.

        Args:
            clusters: List of clusters to save

        Returns:
            Number of relationships saved
        """
        count = 0

        async with self.pool.acquire() as conn:
            for cluster in clusters:
                companies = cluster.companies

                # Create relationships between all pairs
                for i, company_a in enumerate(companies):
                    for company_b in companies[i+1:]:
                        try:
                            await conn.execute("""
                                INSERT INTO company_relationships (
                                    company_a, company_b, relationship_type,
                                    confidence, evidence, source
                                )
                                VALUES ($1, $2, 'bid_cluster', $3, $4, 'gnn_detection')
                                ON CONFLICT (company_a, company_b, relationship_type)
                                DO UPDATE SET
                                    confidence = GREATEST(company_relationships.confidence, $3),
                                    evidence = $4,
                                    discovered_at = CURRENT_TIMESTAMP
                            """, company_a, company_b, int(cluster.confidence),
                            json.dumps(cluster.to_dict()), 'database')

                            count += 1

                        except Exception as e:
                            logger.warning(f"Failed to save relationship {company_a}-{company_b}: {e}")

        logger.info(f"Saved {count} company relationships to database")
        return count


# =============================================================================
# Convenience Functions
# =============================================================================

async def detect_collusion_clusters(
    pool: asyncpg.Pool,
    graph=None,
    embeddings: Optional[np.ndarray] = None,
    min_cluster_size: int = 3,
    min_confidence: float = 50.0,
    save_to_db: bool = True
) -> List[CollusionCluster]:
    """
    Convenience function to run full collusion detection pipeline.

    Args:
        pool: Database connection pool
        graph: Pre-built BidderGraph (or will be built)
        embeddings: Pre-computed GNN embeddings (optional)
        min_cluster_size: Minimum companies per cluster
        min_confidence: Minimum confidence threshold
        save_to_db: Save detected clusters to database

    Returns:
        List of CollusionCluster objects
    """
    detector = CollusionClusterDetector(pool)

    # Build graph if not provided
    if graph is None:
        from .graph_builder import GraphBuilder
        builder = GraphBuilder(pool)
        graph = await builder.build_co_bidding_graph(
            min_co_bids=2,
            time_window_days=730
        )

    # Run detection
    clusters = await detector.detect_all(
        graph=graph,
        embeddings=embeddings,
        min_cluster_size=min_cluster_size,
        min_confidence=min_confidence
    )

    # Save to database
    if save_to_db and clusters:
        await detector.save_clusters_to_db(clusters)

    return clusters


def export_clusters_to_json(
    clusters: List[CollusionCluster],
    output_path: str
):
    """Export clusters to JSON file."""
    data = {
        'generated_at': datetime.utcnow().isoformat(),
        'num_clusters': len(clusters),
        'clusters': [c.to_dict() for c in clusters]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported {len(clusters)} clusters to {output_path}")
