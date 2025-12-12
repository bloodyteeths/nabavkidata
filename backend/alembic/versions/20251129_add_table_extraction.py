"""Add table extraction tables

Revision ID: 20251129_table_extraction
Revises: 20251126_personalization
Create Date: 2025-11-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers
revision = '20251129_table_extraction'
down_revision = '20251126_personalization'
branch_labels = None
depends_on = None


def upgrade():
    # Create extracted_tables table
    op.create_table(
        'extracted_tables',
        sa.Column('table_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('doc_id', UUID(as_uuid=True), nullable=True),  # Reference to documents table
        sa.Column('tender_id', sa.String(100), nullable=True),  # Reference to tenders
        sa.Column('page_number', sa.Integer, nullable=False),
        sa.Column('table_index', sa.Integer, nullable=False),  # Index on the page (0, 1, 2...)
        sa.Column('extraction_engine', sa.String(50), nullable=False),  # pdfplumber, camelot, tabula, pymupdf
        sa.Column('table_type', sa.String(50), nullable=True),  # items, bidders, specifications, financial, evaluation, unknown
        sa.Column('confidence_score', sa.Numeric(3, 2), nullable=True),  # 0.00 to 1.00
        sa.Column('row_count', sa.Integer, nullable=True),
        sa.Column('col_count', sa.Integer, nullable=True),
        sa.Column('raw_data', JSONB, nullable=False),  # Original extracted table data
        sa.Column('normalized_data', JSONB, nullable=True),  # Cleaned/normalized data
        sa.Column('column_mapping', JSONB, nullable=True),  # Original column names -> standardized names
        sa.Column('extraction_metadata', JSONB, server_default='{}'),  # Engine-specific metadata
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()'))
    )

    # Create indexes for efficient querying
    op.create_index('idx_extracted_tables_doc_id', 'extracted_tables', ['doc_id'])
    op.create_index('idx_extracted_tables_tender_id', 'extracted_tables', ['tender_id'])
    op.create_index('idx_extracted_tables_type', 'extracted_tables', ['table_type'])
    op.create_index('idx_extracted_tables_confidence', 'extracted_tables', ['confidence_score'])
    op.create_index('idx_extracted_tables_created_at', 'extracted_tables', ['created_at'])

    # Create extracted_items table (for procurement items)
    op.create_table(
        'extracted_items',
        sa.Column('item_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('table_id', UUID(as_uuid=True), sa.ForeignKey('extracted_tables.table_id', ondelete='CASCADE'), nullable=False),
        sa.Column('tender_id', sa.String(100), nullable=True),
        sa.Column('item_number', sa.String(50), nullable=True),  # Item number from document
        sa.Column('item_name', sa.Text, nullable=True),  # Item name/description
        sa.Column('quantity', sa.Numeric(15, 4), nullable=True),
        sa.Column('unit', sa.String(50), nullable=True),  # Unit of measure
        sa.Column('unit_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('total_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('cpv_code', sa.String(20), nullable=True),  # CPV classification code
        sa.Column('specifications', sa.Text, nullable=True),  # Technical specifications
        sa.Column('notes', sa.Text, nullable=True),  # Additional notes
        sa.Column('source_row_index', sa.Integer, nullable=True),  # Row index in original table
        sa.Column('extraction_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('raw_data', JSONB, nullable=True),  # Original row data
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()'))
    )

    # Create indexes for extracted_items
    op.create_index('idx_extracted_items_table_id', 'extracted_items', ['table_id'])
    op.create_index('idx_extracted_items_tender_id', 'extracted_items', ['tender_id'])
    op.create_index('idx_extracted_items_cpv_code', 'extracted_items', ['cpv_code'])
    op.create_index('idx_extracted_items_created_at', 'extracted_items', ['created_at'])

    # Create GIN index for JSONB columns (for fast JSON queries)
    op.create_index('idx_extracted_tables_raw_data_gin', 'extracted_tables', ['raw_data'], postgresql_using='gin')
    op.create_index('idx_extracted_items_raw_data_gin', 'extracted_items', ['raw_data'], postgresql_using='gin')

    # Create a view for easy access to items with table metadata
    op.execute("""
        CREATE VIEW v_extracted_items_with_tables AS
        SELECT
            ei.item_id,
            ei.tender_id,
            ei.item_number,
            ei.item_name,
            ei.quantity,
            ei.unit,
            ei.unit_price,
            ei.total_price,
            ei.cpv_code,
            ei.specifications,
            ei.notes,
            ei.extraction_confidence,
            et.table_id,
            et.doc_id,
            et.page_number,
            et.table_type,
            et.extraction_engine,
            et.confidence_score as table_confidence,
            ei.created_at
        FROM extracted_items ei
        JOIN extracted_tables et ON ei.table_id = et.table_id
        ORDER BY ei.created_at DESC;
    """)

    # Add trigger to update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_extracted_tables_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_update_extracted_tables_updated_at
        BEFORE UPDATE ON extracted_tables
        FOR EACH ROW
        EXECUTE FUNCTION update_extracted_tables_updated_at();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_extracted_items_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_update_extracted_items_updated_at
        BEFORE UPDATE ON extracted_items
        FOR EACH ROW
        EXECUTE FUNCTION update_extracted_items_updated_at();
    """)


def downgrade():
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trigger_update_extracted_items_updated_at ON extracted_items")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_extracted_tables_updated_at ON extracted_tables")
    op.execute("DROP FUNCTION IF EXISTS update_extracted_items_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS update_extracted_tables_updated_at()")

    # Drop view
    op.execute("DROP VIEW IF EXISTS v_extracted_items_with_tables")

    # Drop tables
    op.drop_table('extracted_items')
    op.drop_table('extracted_tables')
