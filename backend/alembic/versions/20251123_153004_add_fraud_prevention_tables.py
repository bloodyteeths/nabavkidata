"""Add fraud prevention tables

Revision ID: 20251123_153004
Revises:
Create Date: 2025-11-23 15:30:04.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '20251123_153004'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create fraud_detection table
    op.create_table(
        'fraud_detection',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('device_fingerprint', sa.String(255), nullable=True),
        sa.Column('browser_fingerprint', sa.String(255), nullable=True),
        sa.Column('email_hash', sa.String(255), nullable=True),
        sa.Column('is_vpn', sa.Boolean(), default=False, nullable=False),
        sa.Column('is_proxy', sa.Boolean(), default=False, nullable=False),
        sa.Column('is_suspicious', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_fraud_detection_user_id', 'fraud_detection', ['user_id'])
    op.create_index('ix_fraud_detection_email_hash', 'fraud_detection', ['email_hash'])
    op.create_index('ix_fraud_detection_is_suspicious', 'fraud_detection', ['is_suspicious'])
    op.create_index('ix_fraud_detection_created_at', 'fraud_detection', ['created_at'])

    # Create rate_limits table
    op.create_table(
        'rate_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('ai_queries_today', sa.Integer(), default=0, nullable=False),
        sa.Column('reset_at', sa.DateTime(), nullable=False),
        sa.Column('last_query_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_rate_limits_user_id', 'rate_limits', ['user_id'])
    op.create_index('ix_rate_limits_reset_at', 'rate_limits', ['reset_at'])

    # Add new columns to users table
    op.add_column('users', sa.Column('trial_started_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('is_trial_expired', sa.Boolean(), default=False, nullable=False, server_default='false'))
    op.add_column('users', sa.Column('stripe_subscription_id', sa.String(255), nullable=True))

    # Add indexes for trial-related columns
    op.create_index('ix_users_trial_ends_at', 'users', ['trial_ends_at'])
    op.create_index('ix_users_is_trial_expired', 'users', ['is_trial_expired'])


def downgrade() -> None:
    # Remove indexes from users table
    op.drop_index('ix_users_is_trial_expired', table_name='users')
    op.drop_index('ix_users_trial_ends_at', table_name='users')

    # Remove columns from users table
    op.drop_column('users', 'stripe_subscription_id')
    op.drop_column('users', 'is_trial_expired')
    op.drop_column('users', 'trial_ends_at')
    op.drop_column('users', 'trial_started_at')

    # Drop rate_limits table
    op.drop_index('ix_rate_limits_reset_at', table_name='rate_limits')
    op.drop_index('ix_rate_limits_user_id', table_name='rate_limits')
    op.drop_table('rate_limits')

    # Drop fraud_detection table
    op.drop_index('ix_fraud_detection_created_at', table_name='fraud_detection')
    op.drop_index('ix_fraud_detection_is_suspicious', table_name='fraud_detection')
    op.drop_index('ix_fraud_detection_email_hash', table_name='fraud_detection')
    op.drop_index('ix_fraud_detection_user_id', table_name='fraud_detection')
    op.drop_table('fraud_detection')
