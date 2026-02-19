-- Migration: API Keys for Enterprise tier
-- Date: 2025-12-18
-- Description: Adds API key management for Enterprise tier users

-- Create api_keys table
CREATE TABLE IF NOT EXISTS api_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,  -- SHA-256 hash of the actual key
    key_prefix VARCHAR(12) NOT NULL,  -- First 8 chars for display (e.g., "nb_live_ab")
    name VARCHAR(100) NOT NULL,  -- User-provided name
    scopes JSONB DEFAULT '["read"]'::jsonb,  -- Permissions: read, write, admin
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,  -- Optional expiration
    request_count INTEGER DEFAULT 0,
    rate_limit_per_minute INTEGER DEFAULT 60,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active) WHERE is_active = TRUE;

-- Comments
COMMENT ON TABLE api_keys IS 'API keys for programmatic access (Enterprise tier only)';
COMMENT ON COLUMN api_keys.key_hash IS 'SHA-256 hash of the actual API key - never store plaintext';
COMMENT ON COLUMN api_keys.key_prefix IS 'First 8 chars of key for identification in UI (e.g., nb_live_ab...)';
COMMENT ON COLUMN api_keys.scopes IS 'JSON array of permissions: read (search/export), write (alerts), admin (user management)';
