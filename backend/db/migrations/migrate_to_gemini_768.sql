-- ============================================================================
-- GEMINI MIGRATION: Vector Dimension Update (1536 → 768)
-- Date: 2025-11-23
-- ============================================================================
-- This migration updates the database schema to support Google Gemini
-- text-embedding-004 which uses 768-dimensional vectors instead of
-- OpenAI's 1536-dimensional vectors.
-- ============================================================================

-- Start transaction
BEGIN;

-- ============================================================================
-- STEP 1: Backup existing data (optional but recommended)
-- ============================================================================
-- Uncomment to create backup tables
-- CREATE TABLE embeddings_backup_20251123 AS SELECT * FROM embeddings;
-- CREATE TABLE user_interest_vectors_backup_20251123 AS SELECT * FROM user_interest_vectors;

-- ============================================================================
-- STEP 2: Drop existing vector indexes
-- ============================================================================
DROP INDEX IF EXISTS idx_embed_vector;

-- ============================================================================
-- STEP 3: Clear existing embeddings (incompatible dimension)
-- ============================================================================
-- WARNING: This deletes all existing embeddings
-- You will need to re-embed all documents after this migration
TRUNCATE TABLE embeddings CASCADE;
TRUNCATE TABLE user_interest_vectors CASCADE;

-- ============================================================================
-- STEP 4: Update embeddings table to 768 dimensions
-- ============================================================================
ALTER TABLE embeddings
ALTER COLUMN vector TYPE vector(768);

-- Update default embedding model
ALTER TABLE embeddings
ALTER COLUMN embedding_model SET DEFAULT 'text-embedding-004';

-- ============================================================================
-- STEP 5: Update user_interest_vectors table to 768 dimensions
-- ============================================================================
ALTER TABLE user_interest_vectors
ALTER COLUMN embedding TYPE vector(768);

-- ============================================================================
-- STEP 6: Recreate vector indexes for 768 dimensions
-- ============================================================================
CREATE INDEX idx_embed_vector
ON embeddings USING ivfflat (vector vector_cosine_ops)
WITH (lists = 100);

-- ============================================================================
-- STEP 7: Update system configuration
-- ============================================================================
UPDATE system_config
SET config_value = 'text-embedding-004'
WHERE config_key = 'embedding_model';

UPDATE system_config
SET config_value = 'gemini-2.5-flash'
WHERE config_key = 'default_llm';

UPDATE system_config
SET config_value = 'gemini-2.5-pro'
WHERE config_key = 'fallback_llm';

-- Add new config if not exists
INSERT INTO system_config (config_key, config_value, description)
VALUES ('vector_dimension', '768', 'Vector embedding dimension size')
ON CONFLICT (config_key) DO UPDATE
SET config_value = '768';

-- ============================================================================
-- STEP 8: Add migration record
-- ============================================================================
INSERT INTO system_config (config_key, config_value, description)
VALUES (
    'migration_gemini_768',
    CURRENT_TIMESTAMP::text,
    'Migration to Gemini 768-dimensional vectors completed'
);

-- Commit transaction
COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these after migration to verify:

-- Check embeddings table structure
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'embeddings' AND column_name = 'vector';

-- Check user_interest_vectors structure
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'user_interest_vectors' AND column_name = 'embedding';

-- Check system config
-- SELECT * FROM system_config WHERE config_key IN ('embedding_model', 'default_llm', 'fallback_llm', 'vector_dimension');

-- Check index exists
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'embeddings' AND indexname = 'idx_embed_vector';

-- ============================================================================
-- POST-MIGRATION TASKS
-- ============================================================================
-- 1. Re-embed all documents using new Gemini embeddings
-- 2. Rebuild user interest vectors
-- 3. Verify embedding generation works
-- 4. Test RAG query pipeline
-- ============================================================================
