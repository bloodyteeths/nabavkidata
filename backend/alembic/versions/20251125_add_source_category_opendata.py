"""Add source_category to tenders and create opendata_stats table

Revision ID: 20251125_opendata
Revises: 20251124_add_missing_tender_fields
Create Date: 2025-11-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20251125_opendata'
down_revision = '20251124_add_missing_tender_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add source_category column to tenders table
    op.add_column('tenders', sa.Column('source_category', sa.String(50), nullable=True, server_default='active'))
    op.create_index('ix_tenders_source_category', 'tenders', ['source_category'])

    # Create opendata_stats table for PowerBI aggregate statistics
    op.create_table(
        'opendata_stats',
        sa.Column('stat_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('category', sa.String(50), nullable=False, index=True),
        sa.Column('stat_key', sa.String(200), nullable=False),
        sa.Column('stat_value', postgresql.JSONB, nullable=False),
        sa.Column('source_report_id', sa.String(100), nullable=True),
        sa.Column('fetched_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    op.create_index('ix_opendata_stats_category', 'opendata_stats', ['category'])
    op.create_index('ix_opendata_stats_fetched_at', 'opendata_stats', ['fetched_at'])


def downgrade():
    op.drop_table('opendata_stats')
    op.drop_index('ix_tenders_source_category', 'tenders')
    op.drop_column('tenders', 'source_category')
