"""Add personalization tables

Revision ID: 20251126_personalization
Revises: 20251125_add_source_category_opendata
Create Date: 2025-11-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers
revision = '20251126_personalization'
down_revision = '20251125_add_source_category_opendata'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('pref_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('sectors', ARRAY(sa.String), server_default='{}'),
        sa.Column('cpv_codes', ARRAY(sa.String), server_default='{}'),
        sa.Column('entities', ARRAY(sa.String), server_default='{}'),
        sa.Column('min_budget', sa.Numeric(15, 2), nullable=True),
        sa.Column('max_budget', sa.Numeric(15, 2), nullable=True),
        sa.Column('exclude_keywords', ARRAY(sa.String), server_default='{}'),
        sa.Column('competitor_companies', ARRAY(sa.String), server_default='{}'),
        sa.Column('notification_frequency', sa.String(20), server_default='daily'),
        sa.Column('email_enabled', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_user_preferences_user_id', 'user_preferences', ['user_id'])

    # Create user_behavior table
    op.create_table(
        'user_behavior',
        sa.Column('behavior_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('tender_id', sa.String(100), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),  # view, click, save, share, search
        sa.Column('duration_seconds', sa.Integer, nullable=True),
        sa.Column('behavior_metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_user_behavior_user_id', 'user_behavior', ['user_id'])
    op.create_index('idx_user_behavior_created_at', 'user_behavior', ['created_at'])
    op.create_index('idx_user_behavior_action', 'user_behavior', ['action'])

    # Create user_interest_vectors table (for AI recommendations)
    # Note: Requires pgvector extension for VECTOR type
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.create_table(
        'user_interest_vectors',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('embedding', sa.LargeBinary, nullable=True),  # Store as bytes, convert to vector in app
        sa.Column('interaction_count', sa.Integer, server_default='0'),
        sa.Column('last_updated', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('version', sa.Integer, server_default='1')
    )

    # Create email_digests table
    op.create_table(
        'email_digests',
        sa.Column('digest_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('digest_date', sa.DateTime, nullable=False),
        sa.Column('digest_html', sa.Text, nullable=True),
        sa.Column('digest_text', sa.Text, nullable=True),
        sa.Column('tender_count', sa.Integer, server_default='0'),
        sa.Column('competitor_activity_count', sa.Integer, server_default='0'),
        sa.Column('sent', sa.Boolean, server_default='false'),
        sa.Column('sent_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_email_digests_user_id', 'email_digests', ['user_id'])
    op.create_index('idx_email_digests_digest_date', 'email_digests', ['digest_date'])

    # Create search_history table (NEW - for tracking searches)
    op.create_table(
        'search_history',
        sa.Column('search_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('query_text', sa.String(500), nullable=True),
        sa.Column('filters', JSONB, server_default='{}'),
        sa.Column('results_count', sa.Integer, nullable=True),
        sa.Column('clicked_tender_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_search_history_user_id', 'search_history', ['user_id'])
    op.create_index('idx_search_history_created_at', 'search_history', ['created_at'])

    # Create saved_searches table
    op.create_table(
        'saved_searches',
        sa.Column('search_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('query', sa.String(500), nullable=True),
        sa.Column('filters', JSONB, server_default='{}'),
        sa.Column('notify', sa.Boolean, server_default='false'),
        sa.Column('last_executed', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'))
    )
    op.create_index('idx_saved_searches_user_id', 'saved_searches', ['user_id'])


def downgrade():
    op.drop_table('saved_searches')
    op.drop_table('search_history')
    op.drop_table('email_digests')
    op.drop_table('user_interest_vectors')
    op.drop_table('user_behavior')
    op.drop_table('user_preferences')
