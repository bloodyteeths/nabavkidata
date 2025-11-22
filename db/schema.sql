-- ============================================================================
-- Tender Intelligence SaaS - PostgreSQL Database Schema
-- Domain: nabavkidata.com
-- Purpose: Unified database for tender data, users, subscriptions, and AI embeddings
-- Version: 1.0
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";  -- For vector similarity search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- For fuzzy text search

-- ============================================================================
-- USERS & AUTHENTICATION
-- ============================================================================

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    plan_tier VARCHAR(50) DEFAULT 'Free' CHECK (plan_tier IN ('Free', 'Standard', 'Pro', 'Enterprise')),
    stripe_customer_id VARCHAR(255) UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_stripe_customer ON users(stripe_customer_id);
CREATE INDEX idx_users_plan_tier ON users(plan_tier);

COMMENT ON TABLE users IS 'User accounts with authentication and subscription info';
COMMENT ON COLUMN users.plan_tier IS 'Subscription tier: Free (default), Standard (€99/mo), Pro (€395/mo), Enterprise (€1495/mo)';

-- ============================================================================
-- ORGANIZATIONS (for Enterprise multi-seat accounts)
-- ============================================================================

CREATE TABLE organizations (
    org_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    owner_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    stripe_subscription_id VARCHAR(255),
    max_seats INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_org_owner ON organizations(owner_user_id);

COMMENT ON TABLE organizations IS 'Enterprise organizations with multiple user seats';

-- Link users to organizations
ALTER TABLE users ADD COLUMN org_id UUID REFERENCES organizations(org_id) ON DELETE SET NULL;
CREATE INDEX idx_users_org ON users(org_id);

-- ============================================================================
-- SUBSCRIPTIONS
-- ============================================================================

CREATE TABLE subscriptions (
    sub_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    org_id UUID REFERENCES organizations(org_id) ON DELETE CASCADE,
    plan VARCHAR(50) NOT NULL CHECK (plan IN ('Free', 'Standard', 'Pro', 'Enterprise')),
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'canceled', 'past_due', 'trialing', 'incomplete')),
    stripe_sub_id VARCHAR(255) UNIQUE,
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT user_or_org_required CHECK (user_id IS NOT NULL OR org_id IS NOT NULL)
);

CREATE INDEX idx_sub_user ON subscriptions(user_id);
CREATE INDEX idx_sub_org ON subscriptions(org_id);
CREATE INDEX idx_sub_stripe ON subscriptions(stripe_sub_id);
CREATE INDEX idx_sub_status ON subscriptions(status);

COMMENT ON TABLE subscriptions IS 'Stripe subscription tracking for users and organizations';

-- ============================================================================
-- TENDERS (Core entity)
-- ============================================================================

CREATE TABLE tenders (
    tender_id VARCHAR(100) PRIMARY KEY,  -- e.g., "2023/47" from e-nabavki
    title TEXT NOT NULL,
    description TEXT,
    category VARCHAR(255),
    procuring_entity VARCHAR(500),
    procuring_entity_code VARCHAR(100),
    opening_date DATE,
    closing_date DATE,
    publication_date DATE,
    estimated_value_eur NUMERIC(15, 2),
    estimated_value_mkd NUMERIC(15, 2),
    awarded_value_eur NUMERIC(15, 2),
    awarded_value_mkd NUMERIC(15, 2),
    winner VARCHAR(500),
    winner_tax_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'awarded', 'cancelled')),
    cpv_code VARCHAR(50),  -- Common Procurement Vocabulary code
    source_url TEXT,
    language VARCHAR(10) DEFAULT 'mk',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tenders_category ON tenders(category);
CREATE INDEX idx_tenders_status ON tenders(status);
CREATE INDEX idx_tenders_closing_date ON tenders(closing_date);
CREATE INDEX idx_tenders_opening_date ON tenders(opening_date);
CREATE INDEX idx_tenders_procuring_entity ON tenders(procuring_entity);
CREATE INDEX idx_tenders_cpv ON tenders(cpv_code);
CREATE INDEX idx_tenders_winner ON tenders(winner);

-- Full-text search index for Macedonian and English
CREATE INDEX idx_tenders_title_trgm ON tenders USING gin (title gin_trgm_ops);
CREATE INDEX idx_tenders_description_trgm ON tenders USING gin (description gin_trgm_ops);

COMMENT ON TABLE tenders IS 'Public procurement tenders scraped from e-nabavki.gov.mk';
COMMENT ON COLUMN tenders.tender_id IS 'Official tender ID from source portal';

-- ============================================================================
-- DOCUMENTS (PDFs and attachments)
-- ============================================================================

CREATE TABLE documents (
    doc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tender_id VARCHAR(100) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    doc_type VARCHAR(100),  -- e.g., "Specification", "Contract", "Award Decision"
    file_name VARCHAR(500),
    file_path TEXT,  -- Local or cloud storage path
    file_url TEXT,   -- Original source URL
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    content_text TEXT,  -- Extracted text from PDF
    content_length INTEGER,
    extraction_status VARCHAR(50) DEFAULT 'pending' CHECK (extraction_status IN ('pending', 'success', 'failed', 'ocr_required')),
    page_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_docs_tender ON documents(tender_id);
CREATE INDEX idx_docs_type ON documents(doc_type);
CREATE INDEX idx_docs_extraction_status ON documents(extraction_status);

COMMENT ON TABLE documents IS 'PDF documents and attachments associated with tenders';
COMMENT ON COLUMN documents.content_text IS 'Full text extracted from document for search and RAG';

-- ============================================================================
-- EMBEDDINGS (for RAG vector search)
-- ============================================================================

CREATE TABLE embeddings (
    embed_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tender_id VARCHAR(100) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,  -- Order of chunk within document
    vector VECTOR(1536),  -- OpenAI ada-002 or similar (1536 dimensions)
    metadata JSONB,  -- Additional context: page number, section, etc.
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-ada-002',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_embed_tender ON embeddings(tender_id);
CREATE INDEX idx_embed_doc ON embeddings(doc_id);
CREATE INDEX idx_embed_vector ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);

COMMENT ON TABLE embeddings IS 'Vector embeddings for semantic search and RAG pipeline';
COMMENT ON COLUMN embeddings.vector IS 'High-dimensional embedding vector for similarity search';
COMMENT ON COLUMN embeddings.metadata IS 'JSON metadata: {page: 5, section: "Technical Requirements", ...}';

-- ============================================================================
-- AI QUERY HISTORY (for analytics and usage tracking)
-- ============================================================================

CREATE TABLE query_history (
    query_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT,
    retrieved_chunks INTEGER,  -- Number of chunks retrieved
    llm_model VARCHAR(100),    -- e.g., "gemini-pro", "gpt-4"
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    response_time_ms INTEGER,
    feedback_score INTEGER CHECK (feedback_score BETWEEN 1 AND 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_user ON query_history(user_id);
CREATE INDEX idx_query_created ON query_history(created_at);

COMMENT ON TABLE query_history IS 'Log of all AI assistant queries for analytics and usage enforcement';

-- ============================================================================
-- ALERTS (User-defined tender notifications)
-- ============================================================================

CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    alert_name VARCHAR(255),
    criteria_type VARCHAR(50) NOT NULL CHECK (criteria_type IN ('category', 'keyword', 'entity', 'value_threshold', 'cpv_code')),
    criteria_value TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    notification_method VARCHAR(50) DEFAULT 'email' CHECK (notification_method IN ('email', 'in_app', 'both')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alerts_user ON alerts(user_id);
CREATE INDEX idx_alerts_active ON alerts(is_active);

COMMENT ON TABLE alerts IS 'User-defined alert criteria for new tender notifications';

-- ============================================================================
-- NOTIFICATIONS (In-app and email notifications)
-- ============================================================================

CREATE TABLE notifications (
    note_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    alert_id UUID REFERENCES alerts(alert_id) ON DELETE SET NULL,
    tender_id VARCHAR(100) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) DEFAULT 'tender_match' CHECK (notification_type IN ('tender_match', 'system', 'billing')),
    is_read BOOLEAN DEFAULT FALSE,
    sent_via_email BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_notif_user ON notifications(user_id);
CREATE INDEX idx_notif_read ON notifications(is_read);
CREATE INDEX idx_notif_created ON notifications(created_at);

COMMENT ON TABLE notifications IS 'User notifications for tender matches and system messages';

-- ============================================================================
-- USAGE TRACKING (for tier enforcement)
-- ============================================================================

CREATE TABLE usage_tracking (
    usage_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL CHECK (resource_type IN ('ai_query', 'api_call', 'export', 'search')),
    count INTEGER DEFAULT 1,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_user_date ON usage_tracking(user_id, date);
CREATE INDEX idx_usage_resource ON usage_tracking(resource_type, date);

-- Ensure one row per user/resource/date
CREATE UNIQUE INDEX idx_usage_unique ON usage_tracking(user_id, resource_type, date);

COMMENT ON TABLE usage_tracking IS 'Daily usage counters for enforcing subscription tier limits';

-- ============================================================================
-- AUDIT LOG (for security and compliance)
-- ============================================================================

CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id TEXT,
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_created ON audit_log(created_at);

COMMENT ON TABLE audit_log IS 'Security audit trail for all important system actions';

-- ============================================================================
-- SYSTEM CONFIGURATION
-- ============================================================================

CREATE TABLE system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID REFERENCES users(user_id)
);

COMMENT ON TABLE system_config IS 'System-wide configuration settings';

-- Insert default configurations
INSERT INTO system_config (config_key, config_value, description) VALUES
    ('scraper_last_run', '2024-01-01T00:00:00Z', 'Last successful scraper execution'),
    ('embedding_model', 'text-embedding-ada-002', 'Current embedding model in use'),
    ('default_llm', 'gemini-pro', 'Default LLM for AI assistant'),
    ('fallback_llm', 'gpt-4', 'Fallback LLM if primary fails'),
    ('free_tier_query_limit_daily', '5', 'Free tier daily query limit'),
    ('standard_tier_query_limit_monthly', '100', 'Standard tier monthly query limit'),
    ('pro_tier_query_limit_monthly', '500', 'Pro tier monthly query limit'),
    ('enterprise_tier_query_limit_monthly', '-1', 'Enterprise tier monthly query limit (-1 = unlimited)');

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orgs_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subs_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tenders_updated_at BEFORE UPDATE ON tenders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_docs_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alerts_updated_at BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- MATERIALIZED VIEWS (for performance)
-- ============================================================================

-- Tender summary statistics
CREATE MATERIALIZED VIEW tender_statistics AS
SELECT
    category,
    COUNT(*) as total_tenders,
    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tenders,
    AVG(estimated_value_eur) as avg_estimated_value,
    AVG(awarded_value_eur) as avg_awarded_value,
    DATE_TRUNC('month', publication_date) as month
FROM tenders
GROUP BY category, DATE_TRUNC('month', publication_date);

CREATE INDEX idx_tender_stats_category ON tender_statistics(category);
CREATE INDEX idx_tender_stats_month ON tender_statistics(month);

-- Refresh function (call this periodically)
CREATE OR REPLACE FUNCTION refresh_tender_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY tender_statistics;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SAMPLE DATA VALIDATION FUNCTIONS
-- ============================================================================

-- Validate email format
CREATE OR REPLACE FUNCTION is_valid_email(email TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$';
END;
$$ LANGUAGE plpgsql;

-- Check user query limit
CREATE OR REPLACE FUNCTION check_user_query_limit(p_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_plan_tier VARCHAR(50);
    v_queries_today INTEGER;
    v_limit INTEGER;
BEGIN
    -- Get user's plan
    SELECT plan_tier INTO v_plan_tier FROM users WHERE user_id = p_user_id;

    -- Get today's query count
    SELECT COALESCE(count, 0) INTO v_queries_today
    FROM usage_tracking
    WHERE user_id = p_user_id
        AND resource_type = 'ai_query'
        AND date = CURRENT_DATE;

    -- Determine limit based on plan
    CASE v_plan_tier
        WHEN 'Free' THEN v_limit := 5;
        WHEN 'Standard' THEN v_limit := 100;
        WHEN 'Pro' THEN v_limit := 500;
        WHEN 'Enterprise' THEN RETURN TRUE;  -- Unlimited
        ELSE v_limit := 0;
    END CASE;

    RETURN v_queries_today < v_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GRANTS (for application user)
-- ============================================================================

-- Create application role (to be used by backend API)
-- CREATE ROLE nabavkidata_app WITH LOGIN PASSWORD 'change_me_in_production';
-- GRANT CONNECT ON DATABASE nabavkidata TO nabavkidata_app;
-- GRANT USAGE ON SCHEMA public TO nabavkidata_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nabavkidata_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nabavkidata_app;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================

COMMENT ON DATABASE CURRENT_DATABASE() IS 'Tender Intelligence SaaS Platform - nabavkidata.com';
