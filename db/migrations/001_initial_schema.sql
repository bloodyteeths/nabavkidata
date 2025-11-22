-- Migration 001: Initial Schema
-- Purpose: Create all core tables for nabavkidata.com
-- Date: 2024-11-22
-- Reversible: Yes (see 001_rollback.sql)

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    subscription_tier VARCHAR(50) DEFAULT 'free' CHECK (subscription_tier IN ('free', 'standard', 'pro', 'enterprise')),
    stripe_customer_id VARCHAR(255),
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tier ON users(subscription_tier);

-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    org_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(500) NOT NULL,
    org_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    stripe_subscription_id VARCHAR(255) UNIQUE,
    stripe_customer_id VARCHAR(255),
    tier VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- Tenders table
CREATE TABLE IF NOT EXISTS tenders (
    tender_id VARCHAR(100) PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    category VARCHAR(255),
    procuring_entity VARCHAR(500),
    opening_date DATE,
    closing_date DATE,
    publication_date DATE,
    estimated_value_mkd NUMERIC(15, 2),
    estimated_value_eur NUMERIC(15, 2),
    actual_value_mkd NUMERIC(15, 2),
    actual_value_eur NUMERIC(15, 2),
    cpv_code VARCHAR(50),
    status VARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'awarded', 'cancelled')),
    winner VARCHAR(500),
    source_url TEXT,
    language VARCHAR(10) DEFAULT 'mk',
    scraped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tenders_category ON tenders(category);
CREATE INDEX idx_tenders_status ON tenders(status);
CREATE INDEX idx_tenders_opening_date ON tenders(opening_date);
CREATE INDEX idx_tenders_closing_date ON tenders(closing_date);
CREATE INDEX idx_tenders_cpv ON tenders(cpv_code);
CREATE INDEX idx_tenders_entity ON tenders(procuring_entity);

-- Full-text search index for Macedonian text
CREATE INDEX idx_tenders_title_trgm ON tenders USING gin(title gin_trgm_ops);
CREATE INDEX idx_tenders_desc_trgm ON tenders USING gin(description gin_trgm_ops);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    doc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tender_id VARCHAR(100) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    doc_type VARCHAR(100),
    file_name VARCHAR(500),
    file_path TEXT,
    file_url TEXT,
    content_text TEXT,
    extraction_status VARCHAR(50) DEFAULT 'pending' CHECK (extraction_status IN ('pending', 'success', 'failed', 'ocr_required')),
    file_size_bytes INTEGER,
    page_count INTEGER,
    mime_type VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_tender ON documents(tender_id);
CREATE INDEX idx_documents_status ON documents(extraction_status);

-- Embeddings table (for RAG)
CREATE TABLE IF NOT EXISTS embeddings (
    embed_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
    tender_id VARCHAR(100) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    vector VECTOR(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_embeddings_doc ON embeddings(doc_id);
CREATE INDEX idx_embeddings_tender ON embeddings(tender_id);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);

-- Query history table
CREATE TABLE IF NOT EXISTS query_history (
    query_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    answer TEXT,
    sources JSONB,
    confidence NUMERIC(3, 2),
    query_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_user ON query_history(user_id);
CREATE INDEX idx_query_created ON query_history(created_at);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    filters JSONB,
    frequency VARCHAR(50) DEFAULT 'daily' CHECK (frequency IN ('instant', 'daily', 'weekly')),
    is_active BOOLEAN DEFAULT TRUE,
    last_triggered TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alerts_user ON alerts(user_id);
CREATE INDEX idx_alerts_active ON alerts(is_active);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    alert_id UUID REFERENCES alerts(alert_id) ON DELETE CASCADE,
    tender_id VARCHAR(100) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_read ON notifications(is_read);

-- Usage tracking table
CREATE TABLE IF NOT EXISTS usage_tracking (
    tracking_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    metadata JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_user ON usage_tracking(user_id);
CREATE INDEX idx_usage_action ON usage_tracking(action_type);
CREATE INDEX idx_usage_timestamp ON usage_tracking(timestamp);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_created ON audit_log(created_at);

-- System config table
CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(255) PRIMARY KEY,
    config_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Migration complete
INSERT INTO system_config (config_key, config_value) VALUES ('schema_version', '001');
INSERT INTO system_config (config_key, config_value) VALUES ('migration_date', CURRENT_TIMESTAMP::TEXT);
