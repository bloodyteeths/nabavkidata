-- Migration 022: Enrich mk_companies with CompanyWall.com.mk data
-- Adds: EMBS, EDB, legal form, status, founding date, financials,
--        ownership, risk indicators, CompanyWall ID

-- Core identifiers
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS embs VARCHAR(20);
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS edb VARCHAR(20);
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS companywall_id VARCHAR(20);

-- Status & legal
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active';
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS legal_form VARCHAR(50);
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS founding_date DATE;

-- Location enrichment
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS municipality VARCHAR(200);
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS postal_code VARCHAR(10);
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS region VARCHAR(100);

-- Industry
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS nace_code VARCHAR(20);
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS nace_description VARCHAR(500);

-- People
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS owners JSONB;
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS directors JSONB;

-- Financials
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS revenue NUMERIC(18,2);
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS profit NUMERIC(18,2);
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS num_employees INTEGER;
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS financial_year INTEGER;
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS avg_salary NUMERIC(12,2);

-- Risk indicators
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS tax_debtor BOOLEAN DEFAULT FALSE;
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS court_proceedings BOOLEAN DEFAULT FALSE;
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS bank_blocked BOOLEAN DEFAULT FALSE;
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS credit_rating VARCHAR(10);

-- Metadata
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS companywall_scraped_at TIMESTAMP;
ALTER TABLE mk_companies ADD COLUMN IF NOT EXISTS raw_data_json JSONB;

-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_mk_companies_embs
    ON mk_companies(embs) WHERE embs IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mk_companies_edb
    ON mk_companies(edb) WHERE edb IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mk_companies_companywall_id
    ON mk_companies(companywall_id) WHERE companywall_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mk_companies_status_col
    ON mk_companies(status);
CREATE INDEX IF NOT EXISTS idx_mk_companies_nace
    ON mk_companies(nace_code) WHERE nace_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mk_companies_legal_form
    ON mk_companies(legal_form) WHERE legal_form IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mk_companies_region
    ON mk_companies(region) WHERE region IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mk_companies_credit_rating
    ON mk_companies(credit_rating) WHERE credit_rating IS NOT NULL;
