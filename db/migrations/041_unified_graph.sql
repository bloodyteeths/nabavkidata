-- Migration 041: Unified Relationship Graph Tables
-- Purpose: Store entity relationship edges and centrality metrics for graph-based corruption analysis
-- Date: 2026-02-19
-- Phase: 4.1 - Unified Relationship Graph Engine

BEGIN;

-- =====================================================
-- Unified Edges Table
-- Stores all relationship edges between entities (companies, institutions, people)
-- Edge types: co_bidding, buyer_supplier, repeat_partnership, value_concentration
-- =====================================================

CREATE TABLE IF NOT EXISTS unified_edges (
    edge_id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'company',  -- company, institution, person
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT 'company',
    edge_type TEXT NOT NULL,  -- co_bidding, buyer_supplier, repeat_partnership, value_concentration
    weight FLOAT DEFAULT 1.0,
    tender_count INTEGER DEFAULT 0,
    total_value NUMERIC(18,2) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_id, target_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_unified_edges_source ON unified_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_unified_edges_target ON unified_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_unified_edges_type ON unified_edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_unified_edges_weight ON unified_edges(weight DESC);
CREATE INDEX IF NOT EXISTS idx_unified_edges_source_target ON unified_edges(source_id, target_id);

COMMENT ON TABLE unified_edges IS 'Unified relationship graph edges between entities (companies, institutions, people)';
COMMENT ON COLUMN unified_edges.source_id IS 'Source entity identifier (company name or institution name)';
COMMENT ON COLUMN unified_edges.source_type IS 'Type of source entity: company, institution, or person';
COMMENT ON COLUMN unified_edges.target_id IS 'Target entity identifier (company name or institution name)';
COMMENT ON COLUMN unified_edges.target_type IS 'Type of target entity: company, institution, or person';
COMMENT ON COLUMN unified_edges.edge_type IS 'Relationship type: co_bidding, buyer_supplier, repeat_partnership, value_concentration';
COMMENT ON COLUMN unified_edges.weight IS 'Edge weight (higher = stronger relationship)';
COMMENT ON COLUMN unified_edges.tender_count IS 'Number of tenders involved in this relationship';
COMMENT ON COLUMN unified_edges.total_value IS 'Total contract value (MKD) across this relationship';
COMMENT ON COLUMN unified_edges.metadata IS 'Additional edge metadata as JSON (e.g., common tenders, concentration ratio)';

-- =====================================================
-- Entity Centrality Cache Table
-- Cached graph centrality metrics, rebuilt nightly by batch_graph_build.py
-- =====================================================

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
);

CREATE INDEX IF NOT EXISTS idx_centrality_pagerank ON entity_centrality_cache(pagerank DESC);
CREATE INDEX IF NOT EXISTS idx_centrality_betweenness ON entity_centrality_cache(betweenness DESC);
CREATE INDEX IF NOT EXISTS idx_centrality_community ON entity_centrality_cache(community_id);
CREATE INDEX IF NOT EXISTS idx_centrality_entity_type ON entity_centrality_cache(entity_type);
CREATE INDEX IF NOT EXISTS idx_centrality_degree ON entity_centrality_cache(degree DESC);

COMMENT ON TABLE entity_centrality_cache IS 'Cached centrality metrics from graph analysis, rebuilt nightly by batch_graph_build.py';
COMMENT ON COLUMN entity_centrality_cache.entity_id IS 'Entity identifier (company name or institution name)';
COMMENT ON COLUMN entity_centrality_cache.entity_type IS 'Entity type: company or institution';
COMMENT ON COLUMN entity_centrality_cache.pagerank IS 'PageRank centrality score (higher = more connected/important)';
COMMENT ON COLUMN entity_centrality_cache.betweenness IS 'Betweenness centrality score (higher = more bridge/gatekeeper role)';
COMMENT ON COLUMN entity_centrality_cache.degree IS 'Total degree (number of connections)';
COMMENT ON COLUMN entity_centrality_cache.in_degree IS 'In-degree (incoming connections in directed graph)';
COMMENT ON COLUMN entity_centrality_cache.out_degree IS 'Out-degree (outgoing connections in directed graph)';
COMMENT ON COLUMN entity_centrality_cache.community_id IS 'Detected community/cluster ID from Louvain algorithm';

COMMIT;
