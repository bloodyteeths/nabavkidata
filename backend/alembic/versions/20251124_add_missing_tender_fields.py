"""Add missing tender fields

Revision ID: 20251124_addfields
Revises: 20251123_220000
Create Date: 2025-11-24

This migration adds 6 new fields to the tenders table:
1. procedure_type - VARCHAR(200) - Вид на постапка
2. contract_signing_date - DATE - Датум на склучување
3. contract_duration - VARCHAR(100) - Времетраење (e.g., "12 месеци")
4. contracting_entity_category - VARCHAR(200) - Категорија на договорен орган
5. procurement_holder - VARCHAR(500) - Носител на набавката
6. bureau_delivery_date - DATE - Датум на доставување

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251124_addfields'
down_revision = '20251123_220000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new columns to tenders table"""

    # Add new columns
    op.add_column('tenders', sa.Column('procedure_type', sa.String(200), nullable=True))
    op.add_column('tenders', sa.Column('contract_signing_date', sa.Date(), nullable=True))
    op.add_column('tenders', sa.Column('contract_duration', sa.String(100), nullable=True))
    op.add_column('tenders', sa.Column('contracting_entity_category', sa.String(200), nullable=True))
    op.add_column('tenders', sa.Column('procurement_holder', sa.String(500), nullable=True))
    op.add_column('tenders', sa.Column('bureau_delivery_date', sa.Date(), nullable=True))

    # Create indexes for frequently queried fields
    op.create_index('idx_tenders_procedure_type', 'tenders', ['procedure_type'])
    op.create_index('idx_tenders_entity_category', 'tenders', ['contracting_entity_category'])


def downgrade() -> None:
    """Remove new columns from tenders table"""

    # Drop indexes first
    op.drop_index('idx_tenders_entity_category', 'tenders')
    op.drop_index('idx_tenders_procedure_type', 'tenders')

    # Drop columns
    op.drop_column('tenders', 'bureau_delivery_date')
    op.drop_column('tenders', 'procurement_holder')
    op.drop_column('tenders', 'contracting_entity_category')
    op.drop_column('tenders', 'contract_duration')
    op.drop_column('tenders', 'contract_signing_date')
    op.drop_column('tenders', 'procedure_type')
