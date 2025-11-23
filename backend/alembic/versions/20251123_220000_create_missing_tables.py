"""Create missing tables

Revision ID: 20251123_220000
Revises: 20251123_153004
Create Date: 2025-11-23 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '20251123_220000'
down_revision = '20251123_153004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================================
    # USERS & AUTHENTICATION TABLES
    # ============================================================================

    # Create users table
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('subscription_tier', sa.String(50), default='free', nullable=False),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('email_verified', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('trial_started_at', sa.DateTime(), nullable=True),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('is_trial_expired', sa.Boolean(), default=False, nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_stripe_customer_id', 'users', ['stripe_customer_id'])
    op.create_index('ix_users_subscription_tier', 'users', ['subscription_tier'])
    op.create_index('ix_users_trial_ends_at', 'users', ['trial_ends_at'])
    op.create_index('ix_users_is_trial_expired', 'users', ['is_trial_expired'])
    op.create_index('ix_users_org_id', 'users', ['org_id'])

    # Create refresh_tokens table (for JWT refresh tokens)
    op.create_table(
        'refresh_tokens',
        sa.Column('token_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(500), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_token', 'refresh_tokens', ['token'])
    op.create_index('ix_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'])

    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('key_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(255), unique=True, nullable=False),
        sa.Column('key_prefix', sa.String(20), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])
    op.create_index('ix_api_keys_is_active', 'api_keys', ['is_active'])

    # Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('pref_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('language', sa.String(10), default='mk', nullable=False),
        sa.Column('timezone', sa.String(50), default='Europe/Skopje', nullable=False),
        sa.Column('email_notifications', sa.Boolean(), default=True, nullable=False),
        sa.Column('in_app_notifications', sa.Boolean(), default=True, nullable=False),
        sa.Column('theme', sa.String(20), default='light', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'])

    # Create personalization_settings table
    op.create_table(
        'personalization_settings',
        sa.Column('setting_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('favorite_categories', postgresql.JSONB, nullable=True),
        sa.Column('favorite_cpv_codes', postgresql.JSONB, nullable=True),
        sa.Column('favorite_entities', postgresql.JSONB, nullable=True),
        sa.Column('dashboard_widgets', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_personalization_settings_user_id', 'personalization_settings', ['user_id'])

    # ============================================================================
    # ORGANIZATIONS
    # ============================================================================

    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('org_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('org_type', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_organizations_name', 'organizations', ['name'])

    # Add foreign key constraint to users.org_id
    op.create_foreign_key(
        'fk_users_org_id',
        'users', 'organizations',
        ['org_id'], ['org_id'],
        ondelete='SET NULL'
    )

    # ============================================================================
    # TENDERS & DOCUMENTS
    # ============================================================================

    # Create tenders table
    op.create_table(
        'tenders',
        sa.Column('tender_id', sa.String(100), primary_key=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(255), nullable=True),
        sa.Column('procuring_entity', sa.String(500), nullable=True),
        sa.Column('opening_date', sa.Date(), nullable=True),
        sa.Column('closing_date', sa.Date(), nullable=True),
        sa.Column('publication_date', sa.Date(), nullable=True),
        sa.Column('estimated_value_mkd', sa.Numeric(15, 2), nullable=True),
        sa.Column('estimated_value_eur', sa.Numeric(15, 2), nullable=True),
        sa.Column('actual_value_mkd', sa.Numeric(15, 2), nullable=True),
        sa.Column('actual_value_eur', sa.Numeric(15, 2), nullable=True),
        sa.Column('cpv_code', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), default='open', nullable=False),
        sa.Column('winner', sa.String(500), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('language', sa.String(10), default='mk', nullable=False),
        sa.Column('scraped_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_tenders_category', 'tenders', ['category'])
    op.create_index('ix_tenders_status', 'tenders', ['status'])
    op.create_index('ix_tenders_opening_date', 'tenders', ['opening_date'])
    op.create_index('ix_tenders_closing_date', 'tenders', ['closing_date'])
    op.create_index('ix_tenders_cpv_code', 'tenders', ['cpv_code'])

    # Create tender_documents table (renamed from documents to match audit)
    op.create_table(
        'tender_documents',
        sa.Column('doc_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tender_id', sa.String(100), sa.ForeignKey('tenders.tender_id', ondelete='CASCADE'), nullable=False),
        sa.Column('doc_type', sa.String(100), nullable=True),
        sa.Column('file_name', sa.String(500), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('file_url', sa.Text(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('extraction_status', sa.String(50), default='pending', nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_tender_documents_tender_id', 'tender_documents', ['tender_id'])
    op.create_index('ix_tender_documents_extraction_status', 'tender_documents', ['extraction_status'])

    # Create documents table (for backward compatibility, view of tender_documents)
    op.create_table(
        'documents',
        sa.Column('doc_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tender_id', sa.String(100), sa.ForeignKey('tenders.tender_id', ondelete='CASCADE'), nullable=False),
        sa.Column('doc_type', sa.String(100), nullable=True),
        sa.Column('file_name', sa.String(500), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('file_url', sa.Text(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('extraction_status', sa.String(50), default='pending', nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_documents_tender_id', 'documents', ['tender_id'])
    op.create_index('ix_documents_extraction_status', 'documents', ['extraction_status'])

    # Create tender_entity_link table (junction table for many-to-many relationships)
    op.create_table(
        'tender_entity_link',
        sa.Column('link_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tender_id', sa.String(100), sa.ForeignKey('tenders.tender_id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('relationship_type', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_tender_entity_link_tender_id', 'tender_entity_link', ['tender_id'])
    op.create_index('ix_tender_entity_link_entity_id', 'tender_entity_link', ['entity_id'])
    op.create_unique_constraint('uq_tender_entity', 'tender_entity_link', ['tender_id', 'entity_id', 'entity_type'])

    # Create entity_categories table
    op.create_table(
        'entity_categories',
        sa.Column('category_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('entity_categories.category_id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_entity_categories_name', 'entity_categories', ['name'])
    op.create_index('ix_entity_categories_parent_id', 'entity_categories', ['parent_id'])

    # Create cpv_codes table (Common Procurement Vocabulary)
    op.create_table(
        'cpv_codes',
        sa.Column('cpv_code', sa.String(50), primary_key=True),
        sa.Column('description_mk', sa.Text(), nullable=True),
        sa.Column('description_en', sa.Text(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('parent_code', sa.String(50), sa.ForeignKey('cpv_codes.cpv_code', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_cpv_codes_level', 'cpv_codes', ['level'])
    op.create_index('ix_cpv_codes_parent_code', 'cpv_codes', ['parent_code'])

    # ============================================================================
    # AI & EMBEDDINGS
    # ============================================================================

    # Create embeddings table
    op.create_table(
        'embeddings',
        sa.Column('embed_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('doc_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.doc_id', ondelete='CASCADE'), nullable=True),
        sa.Column('tender_id', sa.String(100), sa.ForeignKey('tenders.tender_id', ondelete='CASCADE'), nullable=True),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=True),
        sa.Column('vector', postgresql.ARRAY(sa.Float()), nullable=True),  # Will be converted to pgvector later
        sa.Column('chunk_metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_embeddings_doc_id', 'embeddings', ['doc_id'])
    op.create_index('ix_embeddings_tender_id', 'embeddings', ['tender_id'])

    # Create query_history table
    op.create_table(
        'query_history',
        sa.Column('query_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('sources', postgresql.JSONB, nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('query_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_query_history_user_id', 'query_history', ['user_id'])
    op.create_index('ix_query_history_created_at', 'query_history', ['created_at'])

    # Create analysis_history table
    op.create_table(
        'analysis_history',
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('tender_id', sa.String(100), sa.ForeignKey('tenders.tender_id', ondelete='CASCADE'), nullable=True),
        sa.Column('analysis_type', sa.String(100), nullable=False),
        sa.Column('results', postgresql.JSONB, nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_analysis_history_user_id', 'analysis_history', ['user_id'])
    op.create_index('ix_analysis_history_tender_id', 'analysis_history', ['tender_id'])
    op.create_index('ix_analysis_history_analysis_type', 'analysis_history', ['analysis_type'])

    # ============================================================================
    # SUBSCRIPTIONS & BILLING
    # ============================================================================

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), unique=True, nullable=True),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('tier', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), default=False, nullable=False),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_stripe_subscription_id', 'subscriptions', ['stripe_subscription_id'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])

    # Create billing_events table
    op.create_table(
        'billing_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.subscription_id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('stripe_event_id', sa.String(255), unique=True, nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_billing_events_user_id', 'billing_events', ['user_id'])
    op.create_index('ix_billing_events_subscription_id', 'billing_events', ['subscription_id'])
    op.create_index('ix_billing_events_event_type', 'billing_events', ['event_type'])
    op.create_index('ix_billing_events_stripe_event_id', 'billing_events', ['stripe_event_id'])

    # Create subscription_usage table
    op.create_table(
        'subscription_usage',
        sa.Column('usage_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.subscription_id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Integer(), default=1, nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_subscription_usage_subscription_id', 'subscription_usage', ['subscription_id'])
    op.create_index('ix_subscription_usage_user_id', 'subscription_usage', ['user_id'])
    op.create_index('ix_subscription_usage_period', 'subscription_usage', ['period_start', 'period_end'])

    # ============================================================================
    # ALERTS & NOTIFICATIONS
    # ============================================================================

    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('filters', postgresql.JSONB, nullable=True),
        sa.Column('frequency', sa.String(50), default='daily', nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_triggered', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_alerts_user_id', 'alerts', ['user_id'])
    op.create_index('ix_alerts_is_active', 'alerts', ['is_active'])

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alerts.alert_id', ondelete='CASCADE'), nullable=True),
        sa.Column('tender_id', sa.String(100), sa.ForeignKey('tenders.tender_id', ondelete='CASCADE'), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), default=False, nullable=False),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])

    # ============================================================================
    # MESSAGING
    # ============================================================================

    # Create message_threads table
    op.create_table(
        'message_threads',
        sa.Column('thread_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('status', sa.String(50), default='open', nullable=False),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_message_threads_user_id', 'message_threads', ['user_id'])
    op.create_index('ix_message_threads_status', 'message_threads', ['status'])

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('message_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('thread_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('message_threads.thread_id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_system_message', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_messages_thread_id', 'messages', ['thread_id'])
    op.create_index('ix_messages_sender_id', 'messages', ['sender_id'])

    # ============================================================================
    # SAVED SEARCHES
    # ============================================================================

    # Create saved_searches table
    op.create_table(
        'saved_searches',
        sa.Column('search_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('search_criteria', postgresql.JSONB, nullable=False),
        sa.Column('is_alert', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_saved_searches_user_id', 'saved_searches', ['user_id'])
    op.create_index('ix_saved_searches_is_alert', 'saved_searches', ['is_alert'])

    # ============================================================================
    # USAGE & AUDIT
    # ============================================================================

    # Create usage_tracking table
    op.create_table(
        'usage_tracking',
        sa.Column('tracking_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('tracking_metadata', postgresql.JSONB, nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_usage_tracking_user_id', 'usage_tracking', ['user_id'])
    op.create_index('ix_usage_tracking_action_type', 'usage_tracking', ['action_type'])
    op.create_index('ix_usage_tracking_timestamp', 'usage_tracking', ['timestamp'])

    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('details', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', postgresql.INET, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_audit_log_user_id', 'audit_log', ['user_id'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])

    # ============================================================================
    # ADMIN & FRAUD PREVENTION
    # ============================================================================

    # Create admin_settings table
    op.create_table(
        'admin_settings',
        sa.Column('setting_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('setting_key', sa.String(255), unique=True, nullable=False),
        sa.Column('setting_value', sa.Text(), nullable=True),
        sa.Column('setting_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_admin_settings_setting_key', 'admin_settings', ['setting_key'])

    # Create admin_audit_log table
    op.create_table(
        'admin_audit_log',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('admin_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('target_type', sa.String(100), nullable=True),
        sa.Column('target_id', sa.String(255), nullable=True),
        sa.Column('changes', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', postgresql.INET, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_admin_audit_log_admin_user_id', 'admin_audit_log', ['admin_user_id'])
    op.create_index('ix_admin_audit_log_action', 'admin_audit_log', ['action'])
    op.create_index('ix_admin_audit_log_created_at', 'admin_audit_log', ['created_at'])

    # Create fraud_events table
    op.create_table(
        'fraud_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('severity', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ip_address', postgresql.INET, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('is_resolved', sa.Boolean(), default=False, nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_fraud_events_user_id', 'fraud_events', ['user_id'])
    op.create_index('ix_fraud_events_event_type', 'fraud_events', ['event_type'])
    op.create_index('ix_fraud_events_severity', 'fraud_events', ['severity'])
    op.create_index('ix_fraud_events_is_resolved', 'fraud_events', ['is_resolved'])

    # ============================================================================
    # SYSTEM CONFIGURATION
    # ============================================================================

    # Create system_config table
    op.create_table(
        'system_config',
        sa.Column('config_key', sa.String(255), primary_key=True),
        sa.Column('config_value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse order to respect foreign key constraints
    op.drop_table('system_config')
    op.drop_table('fraud_events')
    op.drop_table('admin_audit_log')
    op.drop_table('admin_settings')
    op.drop_table('audit_log')
    op.drop_table('usage_tracking')
    op.drop_table('saved_searches')
    op.drop_table('messages')
    op.drop_table('message_threads')
    op.drop_table('notifications')
    op.drop_table('alerts')
    op.drop_table('subscription_usage')
    op.drop_table('billing_events')
    op.drop_table('subscriptions')
    op.drop_table('analysis_history')
    op.drop_table('query_history')
    op.drop_table('embeddings')
    op.drop_table('cpv_codes')
    op.drop_table('entity_categories')
    op.drop_table('tender_entity_link')
    op.drop_table('documents')
    op.drop_table('tender_documents')
    op.drop_table('tenders')
    op.drop_table('organizations')
    op.drop_table('personalization_settings')
    op.drop_table('user_preferences')
    op.drop_table('api_keys')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
