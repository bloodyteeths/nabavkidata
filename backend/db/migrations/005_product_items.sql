-- Migration: Add product_items table for searchable product data
-- This enables searching for specific products like "paracetamol", "intraocular lens", etc.

-- Product items extracted from technical specifications
CREATE TABLE IF NOT EXISTS product_items (
    id SERIAL PRIMARY KEY,
    tender_id VARCHAR(100) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(doc_id) ON DELETE SET NULL,

    -- Product identification
    item_number INTEGER,
    lot_number INTEGER,
    name TEXT NOT NULL,                    -- Product name (primary search field)
    name_mk TEXT,                          -- Macedonian name
    name_en TEXT,                          -- English name

    -- Quantities and pricing
    quantity DECIMAL(15, 4),
    unit VARCHAR(50),                      -- piece, kg, liter, etc.
    unit_price DECIMAL(15, 2),
    total_price DECIMAL(15, 2),
    currency VARCHAR(10) DEFAULT 'MKD',

    -- Technical specifications (searchable JSON)
    specifications JSONB DEFAULT '{}',

    -- Classification
    cpv_code VARCHAR(20),
    category VARCHAR(100),                 -- medicines, medical_devices, equipment, etc.

    -- Supplier info (for awarded contracts)
    manufacturer VARCHAR(255),
    model VARCHAR(255),
    supplier VARCHAR(255),

    -- Search optimization
    search_vector TSVECTOR,                -- Full-text search vector

    -- Metadata
    raw_text TEXT,                         -- Original text for debugging
    extraction_confidence DECIMAL(3, 2),   -- 0.00 to 1.00
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for search
CREATE INDEX IF NOT EXISTS idx_product_items_tender_id ON product_items(tender_id);
CREATE INDEX IF NOT EXISTS idx_product_items_name ON product_items USING gin(to_tsvector('simple', name));
CREATE INDEX IF NOT EXISTS idx_product_items_search ON product_items USING gin(search_vector);
CREATE INDEX IF NOT EXISTS idx_product_items_cpv ON product_items(cpv_code);
CREATE INDEX IF NOT EXISTS idx_product_items_category ON product_items(category);
CREATE INDEX IF NOT EXISTS idx_product_items_specs ON product_items USING gin(specifications);

-- Trigger to update search_vector
CREATE OR REPLACE FUNCTION update_product_items_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector =
        setweight(to_tsvector('simple', COALESCE(NEW.name, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.name_mk, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.name_en, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.manufacturer, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(NEW.model, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(NEW.category, '')), 'C') ||
        setweight(to_tsvector('simple', COALESCE(NEW.raw_text, '')), 'D');
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER product_items_search_update
    BEFORE INSERT OR UPDATE ON product_items
    FOR EACH ROW
    EXECUTE FUNCTION update_product_items_search_vector();

-- Lot information table
CREATE TABLE IF NOT EXISTS tender_lots (
    id SERIAL PRIMARY KEY,
    tender_id VARCHAR(50) NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,

    lot_number INTEGER NOT NULL,
    title TEXT,
    description TEXT,

    -- Values
    estimated_value DECIMAL(15, 2),
    winning_value DECIMAL(15, 2),
    currency VARCHAR(10) DEFAULT 'MKD',

    -- Winner
    winner_name VARCHAR(255),
    winner_address TEXT,

    -- Classification
    cpv_code VARCHAR(20),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tender_id, lot_number)
);

CREATE INDEX IF NOT EXISTS idx_tender_lots_tender ON tender_lots(tender_id);

-- Add extracted_at column to documents if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'documents' AND column_name = 'extracted_at') THEN
        ALTER TABLE documents ADD COLUMN extracted_at TIMESTAMP;
    END IF;
END $$;

-- Add content_text column to documents if not exists (for full text search)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'documents' AND column_name = 'content_text') THEN
        ALTER TABLE documents ADD COLUMN content_text TEXT;
    END IF;
END $$;

-- Add specifications_json to documents
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'documents' AND column_name = 'specifications_json') THEN
        ALTER TABLE documents ADD COLUMN specifications_json JSONB;
    END IF;
END $$;

-- View for easy product search with tender info
CREATE OR REPLACE VIEW product_search AS
SELECT
    pi.id,
    pi.name,
    pi.name_mk,
    pi.name_en,
    pi.quantity,
    pi.unit,
    pi.unit_price,
    pi.total_price,
    pi.currency,
    pi.specifications,
    pi.cpv_code,
    pi.category,
    pi.manufacturer,
    pi.model,
    pi.lot_number,
    t.tender_id,
    t.title AS tender_title,
    t.procuring_entity,
    t.publication_date,
    t.closing_date,
    t.status,
    t.winner,
    t.actual_value_mkd,
    t.source_category
FROM product_items pi
JOIN tenders t ON pi.tender_id = t.tender_id;

-- Sample search function
CREATE OR REPLACE FUNCTION search_products(
    search_term TEXT,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
) RETURNS TABLE (
    id INTEGER,
    name TEXT,
    quantity DECIMAL,
    unit VARCHAR,
    unit_price DECIMAL,
    tender_id VARCHAR,
    tender_title TEXT,
    procuring_entity TEXT,
    winner TEXT,
    publication_date DATE,
    source_category VARCHAR,
    relevance REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pi.id,
        pi.name,
        pi.quantity,
        pi.unit,
        pi.unit_price,
        t.tender_id,
        t.title,
        t.procuring_entity,
        t.winner,
        t.publication_date,
        t.source_category,
        ts_rank(pi.search_vector, plainto_tsquery('simple', search_term)) AS relevance
    FROM product_items pi
    JOIN tenders t ON pi.tender_id = t.tender_id
    WHERE pi.search_vector @@ plainto_tsquery('simple', search_term)
       OR pi.name ILIKE '%' || search_term || '%'
       OR pi.name_mk ILIKE '%' || search_term || '%'
    ORDER BY relevance DESC, t.publication_date DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Search products with year filter (for historical analysis)
CREATE OR REPLACE FUNCTION search_products_by_year(
    search_term TEXT,
    from_year INTEGER,
    to_year INTEGER DEFAULT NULL,
    p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
    tender_id VARCHAR,
    year INTEGER,
    name TEXT,
    quantity DECIMAL,
    unit VARCHAR,
    unit_price DECIMAL,
    total_price DECIMAL,
    procuring_entity TEXT,
    winner TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.tender_id,
        EXTRACT(YEAR FROM t.publication_date)::INTEGER AS year,
        pi.name,
        pi.quantity,
        pi.unit,
        pi.unit_price,
        pi.total_price,
        t.procuring_entity,
        t.winner
    FROM product_items pi
    JOIN tenders t ON pi.tender_id = t.tender_id
    WHERE (pi.search_vector @@ plainto_tsquery('simple', search_term)
           OR pi.name ILIKE '%' || search_term || '%')
      AND EXTRACT(YEAR FROM t.publication_date) >= from_year
      AND (to_year IS NULL OR EXTRACT(YEAR FROM t.publication_date) <= to_year)
    ORDER BY t.publication_date DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE product_items IS 'Individual products/items extracted from tender technical specifications. Enables search for specific products like "paracetamol", "heart stent", etc.';
COMMENT ON TABLE tender_lots IS 'Lot information from tenders divided into parts';
COMMENT ON FUNCTION search_products IS 'Full-text search for products by name';
COMMENT ON FUNCTION search_products_by_year IS 'Search products with year filter for historical analysis';
