"""
Unified Relationship Graph Engine (Phase 4.1)

Builds and analyzes entity relationship graphs from public procurement data
to detect corruption patterns such as:
- Network gatekeepers (high betweenness centrality)
- Revolving doors (entities on both buyer and supplier sides)
- Suspicious clusters (dense communities of co-bidding companies)
- Value concentration (supplier dependency)

Components:
- RelationshipGraph: In-memory graph engine using NetworkX
- RelationshipExtractor: Async SQL-based edge extraction from tender data
- batch_graph_build: CLI script for nightly graph rebuild

Author: nabavkidata.com
License: Proprietary
"""

from .relationship_graph import RelationshipGraph
from .relationship_extractor import RelationshipExtractor

__all__ = ['RelationshipGraph', 'RelationshipExtractor']
