-- Migration: 019_multi_country.sql
-- Purpose: Multi-country schema for cross-border expansion (6 Balkan + 42 EU countries)
-- Date: 2025-12-26
-- Description: Add countries, data_sources tables and country_code to tenders for international expansion
-- Author: Claude Code
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. COUNTRIES TABLE - Registry of all countries in the platform
-- ============================================================================

CREATE TABLE IF NOT EXISTS countries (
    country_code VARCHAR(2) PRIMARY KEY, -- ISO 3166-1 alpha-2 code (e.g., 'MK', 'AL', 'RS')
    country_name VARCHAR(200) NOT NULL,
    country_name_local VARCHAR(200), -- Local language name (e.g., Македонија, Shqipëria)
    country_name_en VARCHAR(200) NOT NULL, -- English name for display

    -- Regional Classification
    region VARCHAR(50) NOT NULL, -- balkans, eu, other
    sub_region VARCHAR(100), -- western_balkans, southern_europe, etc.
    is_eu_member BOOLEAN DEFAULT FALSE,

    -- Procurement System Details
    procurement_portal_url TEXT, -- Main procurement portal URL
    ted_coverage BOOLEAN DEFAULT FALSE, -- Covered by TED (Tenders Electronic Daily)
    ocds_available BOOLEAN DEFAULT FALSE, -- OCDS data available
    api_available BOOLEAN DEFAULT FALSE, -- Has public API

    -- Platform Status
    scraper_enabled BOOLEAN DEFAULT FALSE, -- Actively scraping this country
    data_quality_score NUMERIC(3, 2), -- 0-5 scale, data completeness/quality
    status VARCHAR(30) DEFAULT 'planned', -- planned, development, beta, active, paused, deprecated

    -- Statistics (cached, updated by triggers)
    total_tenders INTEGER DEFAULT 0,
    total_value_eur NUMERIC(20, 2) DEFAULT 0,
    last_scrape_at TIMESTAMP,

    -- Localization
    default_language VARCHAR(10) DEFAULT 'en', -- ISO 639-1 code
    supported_languages JSONB, -- ["mk", "en", "sq"]
    currency_code VARCHAR(3), -- ISO 4217 code (MKD, EUR, ALL, etc.)

    -- Display & Priority
    display_order INTEGER DEFAULT 999, -- Lower numbers appear first
    is_featured BOOLEAN DEFAULT FALSE, -- Show on homepage
    is_active BOOLEAN DEFAULT TRUE, -- Show in country selector

    -- Metadata
    notes TEXT,
    config JSONB, -- Country-specific configuration
    -- Example config:
    -- {
    --   "timezone": "Europe/Skopje",
    --   "date_format": "DD.MM.YYYY",
    --   "vat_rate": 18,
    --   "fiscal_year": "calendar"
    -- }

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for countries table
CREATE INDEX IF NOT EXISTS idx_countries_region ON countries(region);
CREATE INDEX IF NOT EXISTS idx_countries_status ON countries(status);
CREATE INDEX IF NOT EXISTS idx_countries_scraper_enabled ON countries(scraper_enabled) WHERE scraper_enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_countries_is_active ON countries(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_countries_display_order ON countries(display_order);

COMMENT ON TABLE countries IS 'Registry of countries covered by the platform with procurement system metadata';
COMMENT ON COLUMN countries.ted_coverage IS 'Whether this country publishes to EU TED (Tenders Electronic Daily)';
COMMENT ON COLUMN countries.ocds_available IS 'Open Contracting Data Standard availability';
COMMENT ON COLUMN countries.data_quality_score IS 'Quality score 0-5 based on completeness, timeliness, accuracy';

-- ============================================================================
-- 2. DATA SOURCES TABLE - Track different data sources per country
-- ============================================================================

CREATE TABLE IF NOT EXISTS data_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code VARCHAR(2) NOT NULL REFERENCES countries(country_code) ON DELETE CASCADE,

    -- Source Details
    source_name VARCHAR(200) NOT NULL, -- e.g., "e-nabavki.gov.mk", "TED", "OCDS API"
    source_type VARCHAR(50) NOT NULL, -- website, api, ted, ocds, manual, import
    source_category VARCHAR(50), -- national_portal, marketplace, regional_portal

    -- Connection Details
    base_url TEXT NOT NULL, -- Base URL for scraping/API
    api_endpoint TEXT, -- API endpoint if applicable
    api_version VARCHAR(50),
    requires_auth BOOLEAN DEFAULT FALSE,

    -- Technical Configuration
    scraper_class VARCHAR(200), -- Python class name for scraper (e.g., "nabavki_spider.NabavkiSpider")
    scraper_config JSONB, -- Scraper-specific configuration
    -- Example scraper_config:
    -- {
    --   "rate_limit": 2,
    --   "concurrent_requests": 3,
    --   "use_playwright": true,
    --   "categories": ["active", "awarded", "cancelled"],
    --   "pagination_type": "page_number",
    --   "selectors": {...}
    -- }

    -- Schedule & Status
    is_active BOOLEAN DEFAULT TRUE,
    scrape_frequency VARCHAR(50), -- hourly, every_3_hours, daily, weekly, manual
    priority INTEGER DEFAULT 50, -- 0-100, higher = more important

    -- Performance Metrics
    avg_scrape_duration_seconds INTEGER,
    success_rate NUMERIC(5, 2), -- Percentage
    last_scrape_at TIMESTAMP,
    last_success_at TIMESTAMP,
    last_error_at TIMESTAMP,
    last_error_message TEXT,
    consecutive_failures INTEGER DEFAULT 0,

    -- Statistics
    total_scrapes INTEGER DEFAULT 0,
    total_tenders_scraped INTEGER DEFAULT 0,
    total_documents_scraped INTEGER DEFAULT 0,

    -- Data Coverage
    coverage_start_date DATE, -- Earliest tender date available
    coverage_end_date DATE, -- Latest tender date (NULL = current)
    estimated_total_tenders INTEGER, -- Rough estimate of total available tenders

    -- Metadata
    description TEXT,
    notes TEXT,
    contact_info JSONB, -- Contact information for data provider

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for data_sources table
CREATE INDEX IF NOT EXISTS idx_data_sources_country ON data_sources(country_code);
CREATE INDEX IF NOT EXISTS idx_data_sources_type ON data_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_data_sources_active ON data_sources(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_data_sources_priority ON data_sources(priority DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_data_sources_unique ON data_sources(country_code, source_name);

COMMENT ON TABLE data_sources IS 'Registry of data sources (scrapers, APIs, imports) for each country';
COMMENT ON COLUMN data_sources.scraper_class IS 'Python class for Scrapy spider or importer';
COMMENT ON COLUMN data_sources.consecutive_failures IS 'Alert when > 3 for investigation';

-- ============================================================================
-- 3. ADD COUNTRY_CODE TO TENDERS TABLE
-- ============================================================================

-- Add country_code column with default 'MK' (Macedonia) for existing data
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS country_code VARCHAR(2) DEFAULT 'MK';

-- Add source_id to track which data source this tender came from
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS source_id UUID;

-- Update constraint after adding column
ALTER TABLE tenders DROP CONSTRAINT IF EXISTS tenders_country_code_fkey;
ALTER TABLE tenders ADD CONSTRAINT tenders_country_code_fkey
    FOREIGN KEY (country_code) REFERENCES countries(country_code) ON DELETE RESTRICT;

ALTER TABLE tenders DROP CONSTRAINT IF EXISTS tenders_source_id_fkey;
ALTER TABLE tenders ADD CONSTRAINT tenders_source_id_fkey
    FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE SET NULL;

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_tenders_country_code ON tenders(country_code);
CREATE INDEX IF NOT EXISTS idx_tenders_source_id ON tenders(source_id);
CREATE INDEX IF NOT EXISTS idx_tenders_country_status ON tenders(country_code, status);
CREATE INDEX IF NOT EXISTS idx_tenders_country_date ON tenders(country_code, publication_date);

COMMENT ON COLUMN tenders.country_code IS 'ISO 3166-1 alpha-2 country code for tender origin';
COMMENT ON COLUMN tenders.source_id IS 'Reference to data_sources table indicating scraper/API source';

-- ============================================================================
-- 4. ADD COUNTRY_CODE TO EPAZAR_TENDERS TABLE
-- ============================================================================

-- e-Pazar is Macedonia-specific but add for consistency
ALTER TABLE epazar_tenders ADD COLUMN IF NOT EXISTS country_code VARCHAR(2) DEFAULT 'MK';
ALTER TABLE epazar_tenders ADD COLUMN IF NOT EXISTS source_id UUID;

ALTER TABLE epazar_tenders DROP CONSTRAINT IF EXISTS epazar_tenders_country_code_fkey;
ALTER TABLE epazar_tenders ADD CONSTRAINT epazar_tenders_country_code_fkey
    FOREIGN KEY (country_code) REFERENCES countries(country_code) ON DELETE RESTRICT;

ALTER TABLE epazar_tenders DROP CONSTRAINT IF EXISTS epazar_tenders_source_id_fkey;
ALTER TABLE epazar_tenders ADD CONSTRAINT epazar_tenders_source_id_fkey
    FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_epazar_tenders_country_code ON epazar_tenders(country_code);
CREATE INDEX IF NOT EXISTS idx_epazar_tenders_source_id ON epazar_tenders(source_id);

-- ============================================================================
-- 5. INSERT INITIAL COUNTRY DATA
-- ============================================================================

-- Macedonia (North Macedonia) - Primary country, already has data
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ocds_available, api_available,
    scraper_enabled, data_quality_score, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active,
    config
) VALUES (
    'MK', 'Северна Македонија', 'Северна Македонија', 'North Macedonia',
    'balkans', 'western_balkans', FALSE,
    'https://e-nabavki.gov.mk', FALSE, FALSE,
    TRUE, 4.5, 'active',
    'mk', '["mk", "en"]', 'MKD',
    1, TRUE, TRUE,
    '{
        "timezone": "Europe/Skopje",
        "date_format": "DD.MM.YYYY",
        "vat_rate": 18,
        "fiscal_year": "calendar",
        "epazar_url": "https://e-pazar.gov.mk"
    }'::jsonb
) ON CONFLICT (country_code) DO UPDATE SET
    scraper_enabled = TRUE,
    status = 'active',
    is_featured = TRUE,
    updated_at = CURRENT_TIMESTAMP;

-- Balkan Countries (Immediate expansion targets)

-- Albania
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'AL', 'Албанија', 'Shqipëria', 'Albania',
    'balkans', 'western_balkans', FALSE,
    'https://app.map.gov.al', TRUE, TRUE, TRUE,
    FALSE, 'planned',
    'sq', '["sq", "en"]', 'ALL',
    2, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- Serbia
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'RS', 'Србија', 'Србија', 'Serbia',
    'balkans', 'western_balkans', FALSE,
    'https://portal.ujn.gov.rs', TRUE, FALSE, FALSE,
    FALSE, 'planned',
    'sr', '["sr", "en"]', 'RSD',
    3, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- Bosnia and Herzegovina
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'BA', 'Босна и Херцеговина', 'Bosna i Hercegovina', 'Bosnia and Herzegovina',
    'balkans', 'western_balkans', FALSE,
    'https://ejn.gov.ba', TRUE, FALSE, FALSE,
    FALSE, 'planned',
    'bs', '["bs", "hr", "sr", "en"]', 'BAM',
    4, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- Montenegro
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'ME', 'Црна Гора', 'Crna Gora', 'Montenegro',
    'balkans', 'western_balkans', FALSE,
    'https://ejn.gov.me', TRUE, FALSE, FALSE,
    FALSE, 'planned',
    'sr', '["sr", "en"]', 'EUR',
    5, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- Kosovo
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'XK', 'Косово', 'Kosova', 'Kosovo',
    'balkans', 'western_balkans', FALSE,
    'https://e-prokurimi.rks-gov.net', TRUE, FALSE, FALSE,
    FALSE, 'planned',
    'sq', '["sq", "sr", "en"]', 'EUR',
    6, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- EU Countries (TED Coverage) - High priority neighbors

-- Greece
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'GR', 'Грција', 'Ελλάδα', 'Greece',
    'eu', 'southern_europe', TRUE,
    'https://www.promitheus.gov.gr', TRUE, FALSE, FALSE,
    FALSE, 'planned',
    'el', '["el", "en"]', 'EUR',
    10, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- Bulgaria
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'BG', 'Бугарија', 'България', 'Bulgaria',
    'eu', 'eastern_europe', TRUE,
    'https://www.aop.bg', TRUE, FALSE, FALSE,
    FALSE, 'planned',
    'bg', '["bg", "en"]', 'BGN',
    11, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- Croatia
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'HR', 'Хрватска', 'Hrvatska', 'Croatia',
    'eu', 'southern_europe', TRUE,
    'https://eojn.nn.hr', TRUE, FALSE, FALSE,
    FALSE, 'planned',
    'hr', '["hr", "en"]', 'EUR',
    12, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- Slovenia
INSERT INTO countries (
    country_code, country_name, country_name_local, country_name_en,
    region, sub_region, is_eu_member,
    procurement_portal_url, ted_coverage, ocds_available, api_available,
    scraper_enabled, status,
    default_language, supported_languages, currency_code,
    display_order, is_featured, is_active
) VALUES (
    'SI', 'Словенија', 'Slovenija', 'Slovenia',
    'eu', 'southern_europe', TRUE,
    'https://www.enarocanje.si', TRUE, FALSE, FALSE,
    FALSE, 'planned',
    'sl', '["sl", "en"]', 'EUR',
    13, TRUE, TRUE
) ON CONFLICT (country_code) DO NOTHING;

-- Add remaining EU countries (for TED coverage)
-- These will be marked as planned, not featured, lower priority

INSERT INTO countries (country_code, country_name, country_name_en, region, is_eu_member, ted_coverage, status, default_language, currency_code, display_order, is_featured, is_active) VALUES
('AT', 'Австрија', 'Austria', 'eu', TRUE, TRUE, 'planned', 'de', 'EUR', 20, FALSE, TRUE),
('BE', 'Белгија', 'Belgium', 'eu', TRUE, TRUE, 'planned', 'nl', 'EUR', 21, FALSE, TRUE),
('CY', 'Кипар', 'Cyprus', 'eu', TRUE, TRUE, 'planned', 'el', 'EUR', 22, FALSE, TRUE),
('CZ', 'Чешка', 'Czech Republic', 'eu', TRUE, TRUE, 'planned', 'cs', 'CZK', 23, FALSE, TRUE),
('DE', 'Германија', 'Germany', 'eu', TRUE, TRUE, 'planned', 'de', 'EUR', 24, FALSE, TRUE),
('DK', 'Данска', 'Denmark', 'eu', TRUE, TRUE, 'planned', 'da', 'DKK', 25, FALSE, TRUE),
('EE', 'Естонија', 'Estonia', 'eu', TRUE, TRUE, 'planned', 'et', 'EUR', 26, FALSE, TRUE),
('ES', 'Шпанија', 'Spain', 'eu', TRUE, TRUE, 'planned', 'es', 'EUR', 27, FALSE, TRUE),
('FI', 'Финска', 'Finland', 'eu', TRUE, TRUE, 'planned', 'fi', 'EUR', 28, FALSE, TRUE),
('FR', 'Франција', 'France', 'eu', TRUE, TRUE, 'planned', 'fr', 'EUR', 29, FALSE, TRUE),
('HU', 'Унгарија', 'Hungary', 'eu', TRUE, TRUE, 'planned', 'hu', 'HUF', 30, FALSE, TRUE),
('IE', 'Ирска', 'Ireland', 'eu', TRUE, TRUE, 'planned', 'en', 'EUR', 31, FALSE, TRUE),
('IT', 'Италија', 'Italy', 'eu', TRUE, TRUE, 'planned', 'it', 'EUR', 32, FALSE, TRUE),
('LT', 'Литванија', 'Lithuania', 'eu', TRUE, TRUE, 'planned', 'lt', 'EUR', 33, FALSE, TRUE),
('LU', 'Луксембург', 'Luxembourg', 'eu', TRUE, TRUE, 'planned', 'fr', 'EUR', 34, FALSE, TRUE),
('LV', 'Латвија', 'Latvia', 'eu', TRUE, TRUE, 'planned', 'lv', 'EUR', 35, FALSE, TRUE),
('MT', 'Малта', 'Malta', 'eu', TRUE, TRUE, 'planned', 'mt', 'EUR', 36, FALSE, TRUE),
('NL', 'Холандија', 'Netherlands', 'eu', TRUE, TRUE, 'planned', 'nl', 'EUR', 37, FALSE, TRUE),
('PL', 'Полска', 'Poland', 'eu', TRUE, TRUE, 'planned', 'pl', 'PLN', 38, FALSE, TRUE),
('PT', 'Португалија', 'Portugal', 'eu', TRUE, TRUE, 'planned', 'pt', 'EUR', 39, FALSE, TRUE),
('RO', 'Романија', 'Romania', 'eu', TRUE, TRUE, 'planned', 'ro', 'RON', 40, FALSE, TRUE),
('SE', 'Шведска', 'Sweden', 'eu', TRUE, TRUE, 'planned', 'sv', 'SEK', 41, FALSE, TRUE),
('SK', 'Словачка', 'Slovakia', 'eu', TRUE, TRUE, 'planned', 'sk', 'EUR', 42, FALSE, TRUE)
ON CONFLICT (country_code) DO NOTHING;

-- ============================================================================
-- 6. INSERT INITIAL DATA SOURCES
-- ============================================================================

-- Macedonia - e-nabavki.gov.mk
INSERT INTO data_sources (
    country_code, source_name, source_type, source_category,
    base_url, scraper_class, is_active, scrape_frequency, priority,
    scraper_config, description
) VALUES (
    'MK', 'e-nabavki.gov.mk', 'website', 'national_portal',
    'https://e-nabavki.gov.mk', 'nabavki_spider.NabavkiSpider',
    TRUE, 'every_3_hours', 100,
    '{
        "rate_limit": 2,
        "concurrent_requests": 2,
        "use_playwright": true,
        "categories": ["active", "awarded", "cancelled"],
        "pagination_type": "page_number",
        "max_listing_pages": 4000
    }'::jsonb,
    'Primary Macedonian public procurement portal'
) ON CONFLICT (country_code, source_name) DO UPDATE SET
    is_active = TRUE,
    priority = 100,
    updated_at = CURRENT_TIMESTAMP;

-- Macedonia - e-pazar.gov.mk
INSERT INTO data_sources (
    country_code, source_name, source_type, source_category,
    base_url, scraper_class, is_active, scrape_frequency, priority,
    scraper_config, description
) VALUES (
    'MK', 'e-pazar.gov.mk', 'website', 'marketplace',
    'https://e-pazar.gov.mk', 'epazar_api_spider.EPazarApiSpider',
    TRUE, 'daily', 90,
    '{
        "rate_limit": 3,
        "concurrent_requests": 3,
        "use_playwright": false,
        "categories": ["active", "awarded"]
    }'::jsonb,
    'Macedonian electronic marketplace for low-value procurement'
) ON CONFLICT (country_code, source_name) DO NOTHING;

-- EU-wide TED (Tenders Electronic Daily)
INSERT INTO data_sources (
    country_code, source_name, source_type, source_category,
    base_url, api_endpoint, scraper_class, is_active, scrape_frequency, priority,
    scraper_config, description
) VALUES (
    'MK', 'TED - Tenders Electronic Daily', 'api', 'regional_portal',
    'https://ted.europa.eu', 'https://ted.europa.eu/api/v3.0',
    'ted_spider.TEDSpider',
    FALSE, 'daily', 80,
    '{
        "api_version": "3.0",
        "country_filter": ["MK"],
        "rate_limit": 10,
        "concurrent_requests": 5
    }'::jsonb,
    'EU-wide tender publication portal (for cross-border tenders)'
) ON CONFLICT (country_code, source_name) DO NOTHING;

-- Albania - APP.MAP
INSERT INTO data_sources (
    country_code, source_name, source_type, source_category,
    base_url, api_endpoint, scraper_class, is_active, scrape_frequency, priority,
    scraper_config, description
) VALUES (
    'AL', 'APP.MAP - Albania Procurement', 'api', 'national_portal',
    'https://app.map.gov.al', 'https://app.map.gov.al/api',
    'albania_spider.AlbaniaSpider',
    FALSE, 'daily', 85,
    '{
        "api_available": true,
        "ocds_format": true,
        "rate_limit": 5,
        "concurrent_requests": 3
    }'::jsonb,
    'Albanian Public Procurement Agency portal with OCDS API'
) ON CONFLICT (country_code, source_name) DO NOTHING;

-- Serbia - Portal UJN
INSERT INTO data_sources (
    country_code, source_name, source_type, source_category,
    base_url, scraper_class, is_active, scrape_frequency, priority,
    scraper_config, description
) VALUES (
    'RS', 'Portal UJN', 'website', 'national_portal',
    'https://portal.ujn.gov.rs', 'serbia_spider.SerbiaSpider',
    FALSE, 'daily', 85,
    '{
        "rate_limit": 2,
        "concurrent_requests": 2,
        "use_playwright": true,
        "pagination_type": "page_number"
    }'::jsonb,
    'Serbian Public Procurement Office portal'
) ON CONFLICT (country_code, source_name) DO NOTHING;

-- ============================================================================
-- 7. UPDATE EXISTING TENDERS WITH MACEDONIA COUNTRY CODE AND SOURCE
-- ============================================================================

-- Get the source_id for e-nabavki.gov.mk
DO $$
DECLARE
    nabavki_source_id UUID;
BEGIN
    -- Get the source_id for e-nabavki
    SELECT source_id INTO nabavki_source_id
    FROM data_sources
    WHERE country_code = 'MK' AND source_name = 'e-nabavki.gov.mk'
    LIMIT 1;

    -- Update existing tenders
    IF nabavki_source_id IS NOT NULL THEN
        UPDATE tenders
        SET source_id = nabavki_source_id
        WHERE country_code = 'MK' AND source_id IS NULL;

        RAISE NOTICE 'Updated % tenders with e-nabavki source_id', (
            SELECT COUNT(*) FROM tenders WHERE source_id = nabavki_source_id
        );
    END IF;
END $$;

-- ============================================================================
-- 8. CREATE MATERIALIZED VIEW FOR COUNTRY STATISTICS
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS country_statistics AS
SELECT
    c.country_code,
    c.country_name_en,
    c.region,
    c.status,
    COUNT(DISTINCT t.tender_id) AS total_tenders,
    COUNT(DISTINCT CASE WHEN t.status = 'awarded' THEN t.tender_id END) AS awarded_tenders,
    COUNT(DISTINCT CASE WHEN t.status = 'open' THEN t.tender_id END) AS open_tenders,
    SUM(t.estimated_value_eur) AS total_estimated_eur,
    SUM(t.actual_value_eur) AS total_actual_eur,
    COUNT(DISTINCT t.procuring_entity) AS unique_procuring_entities,
    COUNT(DISTINCT t.winner) AS unique_winners,
    MIN(t.publication_date) AS earliest_tender_date,
    MAX(t.publication_date) AS latest_tender_date,
    COUNT(DISTINCT DATE_TRUNC('month', t.publication_date)) AS months_with_data
FROM countries c
LEFT JOIN tenders t ON c.country_code = t.country_code
GROUP BY c.country_code, c.country_name_en, c.region, c.status;

CREATE UNIQUE INDEX IF NOT EXISTS idx_country_statistics_country_code ON country_statistics(country_code);
CREATE INDEX IF NOT EXISTS idx_country_statistics_region ON country_statistics(region);

COMMENT ON MATERIALIZED VIEW country_statistics IS 'Aggregated tender statistics by country';

-- ============================================================================
-- 9. CREATE FUNCTION TO UPDATE COUNTRY STATISTICS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_country_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update country total_tenders count
    UPDATE countries
    SET
        total_tenders = (
            SELECT COUNT(*)
            FROM tenders
            WHERE country_code = NEW.country_code
        ),
        total_value_eur = (
            SELECT COALESCE(SUM(estimated_value_eur), 0)
            FROM tenders
            WHERE country_code = NEW.country_code
        ),
        updated_at = CURRENT_TIMESTAMP
    WHERE country_code = NEW.country_code;

    -- Update data source statistics
    IF NEW.source_id IS NOT NULL THEN
        UPDATE data_sources
        SET
            total_tenders_scraped = (
                SELECT COUNT(*)
                FROM tenders
                WHERE source_id = NEW.source_id
            ),
            last_success_at = CURRENT_TIMESTAMP,
            consecutive_failures = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_id = NEW.source_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic stats updates
DROP TRIGGER IF EXISTS trigger_update_country_stats ON tenders;
CREATE TRIGGER trigger_update_country_stats
    AFTER INSERT ON tenders
    FOR EACH ROW
    EXECUTE FUNCTION update_country_stats();

COMMENT ON FUNCTION update_country_stats() IS 'Automatically update country and data source statistics when tenders are inserted';

-- ============================================================================
-- 10. CREATE HELPER FUNCTIONS FOR MULTI-COUNTRY QUERIES
-- ============================================================================

-- Function to get active countries
CREATE OR REPLACE FUNCTION get_active_countries()
RETURNS TABLE (
    country_code VARCHAR(2),
    country_name_en VARCHAR(200),
    total_tenders INTEGER,
    is_featured BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT c.country_code, c.country_name_en, c.total_tenders, c.is_featured
    FROM countries c
    WHERE c.is_active = TRUE AND c.status IN ('active', 'beta')
    ORDER BY c.display_order, c.country_name_en;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_active_countries() IS 'Get list of active countries for country selector';

-- ============================================================================
-- MIGRATION VERIFICATION
-- ============================================================================

DO $$
DECLARE
    country_count INTEGER;
    source_count INTEGER;
    mk_tender_count INTEGER;
BEGIN
    -- Count countries
    SELECT COUNT(*) INTO country_count FROM countries;
    SELECT COUNT(*) INTO source_count FROM data_sources;
    SELECT COUNT(*) INTO mk_tender_count FROM tenders WHERE country_code = 'MK';

    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Migration 019 - Multi-Country Schema - COMPLETED';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Countries added: %', country_count;
    RAISE NOTICE 'Data sources configured: %', source_count;
    RAISE NOTICE 'Macedonian tenders tagged: %', mk_tender_count;
    RAISE NOTICE '------------------------------------------------------------';
    RAISE NOTICE 'New tables:';
    RAISE NOTICE '  - countries (country registry with procurement metadata)';
    RAISE NOTICE '  - data_sources (scraper/API source tracking)';
    RAISE NOTICE '------------------------------------------------------------';
    RAISE NOTICE 'Schema changes:';
    RAISE NOTICE '  - Added country_code to tenders (default: MK)';
    RAISE NOTICE '  - Added source_id to tenders';
    RAISE NOTICE '  - Added country_code to epazar_tenders';
    RAISE NOTICE '  - Created country_statistics materialized view';
    RAISE NOTICE '------------------------------------------------------------';
    RAISE NOTICE 'Coverage:';
    RAISE NOTICE '  - 6 Balkan countries (MK, AL, RS, BA, ME, XK)';
    RAISE NOTICE '  - 4 neighboring EU countries (GR, BG, HR, SI)';
    RAISE NOTICE '  - 22 additional EU countries (via TED)';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Build country selector UI component';
    RAISE NOTICE '  2. Add country filter to search/browse endpoints';
    RAISE NOTICE '  3. Develop Albania scraper (OCDS API available)';
    RAISE NOTICE '  4. Implement TED API integration for EU-wide coverage';
    RAISE NOTICE '  5. Create country landing pages for SEO';
    RAISE NOTICE '============================================================';
END $$;

COMMIT;
