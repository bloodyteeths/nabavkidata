-- 036_concierge.sql — Tender Q&A concierge (15 Oct 2026)
-- Daily question counter (usage_counters, counter_type='concierge') and a turn log.
-- Idempotent: safe to re-run.
BEGIN;

CREATE TABLE IF NOT EXISTS usage_counters (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    counter_type VARCHAR(50) NOT NULL,  -- rag_queries, exports, document_extractions, concierge, etc.
    period_type VARCHAR(10) NOT NULL,   -- daily, monthly
    period_start DATE NOT NULL,         -- Start of the counting period
    count INTEGER NOT NULL DEFAULT 0,
    limit_value INTEGER,                -- NULL = unlimited
    last_reset_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, counter_type, period_type, period_start)
);

CREATE INDEX IF NOT EXISTS idx_usage_counters_user ON usage_counters(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_counters_period ON usage_counters(period_start);
CREATE UNIQUE INDEX IF NOT EXISTS ux_usage_counters_key
    ON usage_counters(user_id, counter_type, period_type, period_start);

CREATE TABLE IF NOT EXISTS concierge_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    tender_id VARCHAR(100),
    question TEXT NOT NULL,
    answer TEXT,
    refused BOOLEAN NOT NULL DEFAULT FALSE,
    reason VARCHAR(20),
    lang VARCHAR(5),
    model VARCHAR(60),
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_concierge_log_created ON concierge_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_concierge_log_user ON concierge_log(user_id, created_at DESC);

COMMIT;
