"""Add AI summary fields to documents table

Revision ID: 20251202_add_document_ai_fields
Revises:
Create Date: 2025-12-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '20251202_add_document_ai_fields'
down_revision = None  # Update this if you have previous migrations
branch_labels = None
depends_on = None


def upgrade():
    """Add AI summary fields to documents table"""

    # Add ai_summary column for cached AI summaries
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS ai_summary TEXT;
    """)

    # Add key_requirements JSON column for extracted requirements
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS key_requirements JSONB;
    """)

    # Add items_mentioned JSON column for extracted items
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS items_mentioned JSONB;
    """)

    # Add content_hash for cache invalidation
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
    """)

    # Add ai_extracted_at timestamp
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS ai_extracted_at TIMESTAMP;
    """)

    # Add index on content_hash for fast lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_content_hash
        ON documents(content_hash);
    """)

    # Add comments
    op.execute("""
        COMMENT ON COLUMN documents.ai_summary IS
        'AI-generated summary of document content (cached)';
    """)

    op.execute("""
        COMMENT ON COLUMN documents.key_requirements IS
        'JSON array of extracted requirements from document';
    """)

    op.execute("""
        COMMENT ON COLUMN documents.items_mentioned IS
        'JSON array of products/items found in document with quantities';
    """)

    op.execute("""
        COMMENT ON COLUMN documents.content_hash IS
        'SHA-256 hash of content_text for cache invalidation';
    """)


def downgrade():
    """Remove AI summary fields from documents table"""

    op.execute("DROP INDEX IF EXISTS idx_documents_content_hash")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS ai_extracted_at")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS content_hash")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS items_mentioned")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS key_requirements")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS ai_summary")
