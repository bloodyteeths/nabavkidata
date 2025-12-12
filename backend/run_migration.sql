-- Add AI summary fields to documents table
-- Migration: 20251202_add_document_ai_fields

-- Add ai_summary column for cached AI summaries
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS ai_summary TEXT;

-- Add key_requirements JSON column for extracted requirements
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS key_requirements JSONB;

-- Add items_mentioned JSON column for extracted items
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS items_mentioned JSONB;

-- Add content_hash for cache invalidation
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);

-- Add ai_extracted_at timestamp
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS ai_extracted_at TIMESTAMP;

-- Add index on content_hash for fast lookups
CREATE INDEX IF NOT EXISTS idx_documents_content_hash
ON documents(content_hash);

-- Add comments
COMMENT ON COLUMN documents.ai_summary IS
'AI-generated summary of document content (cached)';

COMMENT ON COLUMN documents.key_requirements IS
'JSON array of extracted requirements from document';

COMMENT ON COLUMN documents.items_mentioned IS
'JSON array of products/items found in document with quantities';

COMMENT ON COLUMN documents.content_hash IS
'SHA-256 hash of content_text for cache invalidation';

-- Verify
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'documents' 
AND column_name IN ('ai_summary', 'key_requirements', 'items_mentioned', 'content_hash', 'ai_extracted_at')
ORDER BY column_name;
