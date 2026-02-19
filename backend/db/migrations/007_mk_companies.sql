-- Migration: Import Macedonia company database
-- Purpose: Store 47K companies for email enrichment

-- Create companies table
CREATE TABLE IF NOT EXISTS mk_companies (
    company_id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    phone VARCHAR(100),
    address TEXT,
    city_mk VARCHAR(200),
    city_en VARCHAR(200),
    website TEXT,
    category_mk VARCHAR(300),
    category_en VARCHAR(300),

    -- Email enrichment fields
    email VARCHAR(255),
    email_source VARCHAR(100),  -- 'yellow_pages', 'google', 'website', 'manual'
    email_found_at TIMESTAMP,
    email_search_attempted BOOLEAN DEFAULT FALSE,
    email_search_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_mk_companies_name ON mk_companies(name);
CREATE INDEX IF NOT EXISTS idx_mk_companies_city ON mk_companies(city_en);
CREATE INDEX IF NOT EXISTS idx_mk_companies_category ON mk_companies(category_en);
CREATE INDEX IF NOT EXISTS idx_mk_companies_email ON mk_companies(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mk_companies_no_email ON mk_companies(email_search_attempted) WHERE email IS NULL AND email_search_attempted = FALSE;

-- Full text search on company name
CREATE INDEX IF NOT EXISTS idx_mk_companies_name_trgm ON mk_companies USING gin(name gin_trgm_ops);
