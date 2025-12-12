"""Add item_bids table for linking bidders to items with prices

Revision ID: 20251129_item_bids
Revises: 20251129_table_extraction
Create Date: 2025-11-29

This table is CRITICAL for answering queries like:
- "Who bid what price for surgical drapes?"
- "What did Company X offer for item Y?"
- "Which bidder had the lowest price per item?"
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '20251129_item_bids'
down_revision = '20251129_table_extraction'
branch_labels = None
depends_on = None


def upgrade():
    # Create item_bids table
    op.create_table(
        'item_bids',
        sa.Column('bid_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tender_id', sa.String(100), sa.ForeignKey('tenders.tender_id', ondelete='CASCADE'), nullable=False),
        sa.Column('lot_id', UUID(as_uuid=True), sa.ForeignKey('tender_lots.lot_id', ondelete='SET NULL'), nullable=True),
        sa.Column('item_id', sa.Integer, sa.ForeignKey('product_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bidder_id', UUID(as_uuid=True), sa.ForeignKey('tender_bidders.bidder_id', ondelete='CASCADE'), nullable=False),

        # Bidder info (denormalized for query performance)
        sa.Column('company_name', sa.String(500), nullable=True),
        sa.Column('company_tax_id', sa.String(100), nullable=True),

        # Bid details per item
        sa.Column('quantity_offered', sa.Numeric(15, 4), nullable=True),
        sa.Column('unit_price_mkd', sa.Numeric(15, 2), nullable=True),
        sa.Column('total_price_mkd', sa.Numeric(15, 2), nullable=True),
        sa.Column('unit_price_eur', sa.Numeric(15, 2), nullable=True),

        # Additional bid attributes
        sa.Column('delivery_days', sa.Integer, nullable=True),
        sa.Column('warranty_months', sa.Integer, nullable=True),
        sa.Column('brand_model', sa.String(500), nullable=True),
        sa.Column('country_of_origin', sa.String(100), nullable=True),

        # Evaluation
        sa.Column('is_compliant', sa.Boolean, server_default='true'),
        sa.Column('is_winner', sa.Boolean, server_default='false'),
        sa.Column('rank', sa.Integer, nullable=True),
        sa.Column('evaluation_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('disqualification_reason', sa.Text, nullable=True),

        # Extraction metadata
        sa.Column('extraction_source', sa.String(50), nullable=True),  # 'document', 'api', 'manual', 'table'
        sa.Column('extraction_confidence', sa.Float, nullable=True),
        sa.Column('source_document_id', UUID(as_uuid=True), nullable=True),
        sa.Column('source_table_id', UUID(as_uuid=True), nullable=True),  # Link to extracted_tables
        sa.Column('source_page_number', sa.Integer, nullable=True),
        sa.Column('raw_data', JSONB, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Create unique constraint (one bid per item per bidder)
    op.create_unique_constraint(
        'uq_item_bids_item_bidder',
        'item_bids',
        ['item_id', 'bidder_id']
    )

    # Indexes for common queries
    op.create_index('idx_item_bids_tender', 'item_bids', ['tender_id'])
    op.create_index('idx_item_bids_item', 'item_bids', ['item_id'])
    op.create_index('idx_item_bids_bidder', 'item_bids', ['bidder_id'])
    op.create_index('idx_item_bids_company', 'item_bids', ['company_name'])
    op.create_index('idx_item_bids_price', 'item_bids', ['unit_price_mkd'])
    op.create_index('idx_item_bids_lot', 'item_bids', ['lot_id'])
    op.create_index('idx_item_bids_source_table', 'item_bids', ['source_table_id'])

    # Partial index for winners only (for fast winner queries)
    op.execute("""
        CREATE INDEX idx_item_bids_winner
        ON item_bids(is_winner)
        WHERE is_winner = TRUE;
    """)

    # GIN index for JSONB raw_data
    op.create_index('idx_item_bids_raw_data_gin', 'item_bids', ['raw_data'], postgresql_using='gin')

    # Create trigger for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_item_bids_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER item_bids_updated_at
        BEFORE UPDATE ON item_bids
        FOR EACH ROW
        EXECUTE FUNCTION update_item_bids_updated_at();
    """)

    # Create useful views for common queries

    # View 1: Item bids with full context (item details, bidder details)
    op.execute("""
        CREATE VIEW v_item_bids_full AS
        SELECT
            ib.bid_id,
            ib.tender_id,
            ib.lot_id,
            ib.item_id,
            ib.bidder_id,

            -- Item details
            pi.name as item_name,
            pi.name_mk as item_name_mk,
            pi.quantity as item_quantity,
            pi.unit as item_unit,
            pi.cpv_code,
            pi.category,

            -- Bid details
            ib.company_name,
            ib.company_tax_id,
            ib.quantity_offered,
            ib.unit_price_mkd,
            ib.total_price_mkd,
            ib.unit_price_eur,
            ib.brand_model,
            ib.country_of_origin,
            ib.delivery_days,
            ib.warranty_months,

            -- Evaluation
            ib.is_compliant,
            ib.is_winner,
            ib.rank,
            ib.evaluation_score,
            ib.disqualification_reason,

            -- Tender details
            t.title as tender_title,
            t.contracting_authority,
            t.status as tender_status,
            t.publication_date,

            -- Metadata
            ib.extraction_source,
            ib.extraction_confidence,
            ib.created_at

        FROM item_bids ib
        JOIN product_items pi ON ib.item_id = pi.id
        JOIN tenders t ON ib.tender_id = t.tender_id
        LEFT JOIN tender_bidders tb ON ib.bidder_id = tb.bidder_id;
    """)

    # View 2: Bid comparison per item (shows all bids for each item side-by-side)
    op.execute("""
        CREATE VIEW v_item_bid_comparison AS
        SELECT
            pi.id as item_id,
            pi.tender_id,
            pi.name as item_name,
            pi.quantity as required_quantity,
            pi.unit,

            -- Aggregate bid statistics
            COUNT(ib.bid_id) as total_bids,
            MIN(ib.unit_price_mkd) as min_price,
            MAX(ib.unit_price_mkd) as max_price,
            AVG(ib.unit_price_mkd) as avg_price,
            STDDEV(ib.unit_price_mkd) as price_stddev,

            -- Winner info
            MAX(CASE WHEN ib.is_winner THEN ib.company_name END) as winner_name,
            MAX(CASE WHEN ib.is_winner THEN ib.unit_price_mkd END) as winner_price,

            -- Lowest bidder info
            (
                SELECT company_name
                FROM item_bids
                WHERE item_id = pi.id
                ORDER BY unit_price_mkd ASC
                LIMIT 1
            ) as lowest_bidder,

            -- All bids as JSON array
            json_agg(
                json_build_object(
                    'company_name', ib.company_name,
                    'unit_price_mkd', ib.unit_price_mkd,
                    'is_winner', ib.is_winner,
                    'rank', ib.rank,
                    'brand_model', ib.brand_model
                ) ORDER BY ib.unit_price_mkd
            ) as all_bids

        FROM product_items pi
        LEFT JOIN item_bids ib ON pi.id = ib.item_id
        GROUP BY pi.id, pi.tender_id, pi.name, pi.quantity, pi.unit;
    """)

    # View 3: Company performance per item category
    op.execute("""
        CREATE VIEW v_company_item_performance AS
        SELECT
            ib.company_name,
            pi.category,
            COUNT(DISTINCT ib.item_id) as items_bid_on,
            COUNT(DISTINCT CASE WHEN ib.is_winner THEN ib.item_id END) as items_won,
            ROUND(
                100.0 * COUNT(DISTINCT CASE WHEN ib.is_winner THEN ib.item_id END) /
                NULLIF(COUNT(DISTINCT ib.item_id), 0),
                2
            ) as win_rate_percent,
            AVG(ib.unit_price_mkd) as avg_unit_price,
            MIN(ib.unit_price_mkd) as min_unit_price,
            MAX(ib.unit_price_mkd) as max_unit_price,
            SUM(CASE WHEN ib.is_winner THEN ib.total_price_mkd ELSE 0 END) as total_value_won
        FROM item_bids ib
        JOIN product_items pi ON ib.item_id = pi.id
        WHERE pi.category IS NOT NULL
        GROUP BY ib.company_name, pi.category
        HAVING COUNT(DISTINCT ib.item_id) >= 3
        ORDER BY items_won DESC, win_rate_percent DESC;
    """)


def downgrade():
    # Drop views
    op.execute("DROP VIEW IF EXISTS v_company_item_performance")
    op.execute("DROP VIEW IF EXISTS v_item_bid_comparison")
    op.execute("DROP VIEW IF EXISTS v_item_bids_full")

    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS item_bids_updated_at ON item_bids")
    op.execute("DROP FUNCTION IF EXISTS update_item_bids_updated_at()")

    # Drop table
    op.drop_table('item_bids')
