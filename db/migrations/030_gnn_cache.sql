-- Migration 030: GNN Graph Cache & Predictions Cache
-- Provides persistent caching for the GNN collusion inference pipeline.
-- The graph cache avoids rebuilding the co-bidding graph on every request.
-- The predictions cache stores per-company risk scores for fast lookups.
--
-- Run: psql -h $DB_HOST -U $DB_USER -d nabavkidata -f db/migrations/030_gnn_cache.sql

BEGIN;

-- Cache the serialized co-bidding graph (rebuilt daily by cron)
CREATE TABLE IF NOT EXISTS gnn_graph_cache (
    cache_key TEXT PRIMARY KEY,
    graph_data JSONB NOT NULL,
    node_count INTEGER,
    edge_count INTEGER,
    built_at TIMESTAMP DEFAULT NOW(),
    build_duration_seconds FLOAT
);

COMMENT ON TABLE gnn_graph_cache IS 'Cached co-bidding graph data for GNN inference. Rebuilt daily.';
COMMENT ON COLUMN gnn_graph_cache.cache_key IS 'Cache key, e.g. co_bidding_730d for 730-day window';
COMMENT ON COLUMN gnn_graph_cache.graph_data IS 'Serialized graph: nodes, edges, node_index, features';

-- Cache per-company GNN risk predictions
CREATE TABLE IF NOT EXISTS gnn_predictions_cache (
    company_name TEXT PRIMARY KEY,
    risk_probability FLOAT,
    risk_level TEXT,
    cluster_id TEXT,
    embedding FLOAT[] DEFAULT NULL,
    predicted_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE gnn_predictions_cache IS 'Per-company GNN collusion risk predictions. Updated after each model run.';
COMMENT ON COLUMN gnn_predictions_cache.risk_probability IS 'Probability of collusion involvement (0.0 - 1.0)';
COMMENT ON COLUMN gnn_predictions_cache.risk_level IS 'Derived risk level: low, medium, high, critical';
COMMENT ON COLUMN gnn_predictions_cache.cluster_id IS 'ID of the collusion cluster this company belongs to (nullable)';
COMMENT ON COLUMN gnn_predictions_cache.embedding IS 'GNN node embedding vector for similarity queries';

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_gnn_pred_risk ON gnn_predictions_cache(risk_probability DESC);
CREATE INDEX IF NOT EXISTS idx_gnn_pred_cluster ON gnn_predictions_cache(cluster_id);
CREATE INDEX IF NOT EXISTS idx_gnn_pred_level ON gnn_predictions_cache(risk_level);
CREATE INDEX IF NOT EXISTS idx_gnn_cache_built ON gnn_graph_cache(built_at DESC);

COMMIT;
