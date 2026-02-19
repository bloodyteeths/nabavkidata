# Migration 019 - Multi-Country Schema Quick Reference

## Tables Created

### `countries` Table
```sql
country_code VARCHAR(2) PRIMARY KEY  -- MK, AL, RS, etc.
country_name VARCHAR(200)
country_name_local VARCHAR(200)      -- Македонија, Shqipëria
country_name_en VARCHAR(200)         -- North Macedonia, Albania
region VARCHAR(50)                   -- balkans, eu
is_eu_member BOOLEAN
procurement_portal_url TEXT
ted_coverage BOOLEAN                 -- TED available
ocds_available BOOLEAN               -- OCDS data available
api_available BOOLEAN
scraper_enabled BOOLEAN              -- Actively scraping
status VARCHAR(30)                   -- planned, active, beta
total_tenders INTEGER                -- Cached count
total_value_eur NUMERIC(20,2)        -- Cached sum
currency_code VARCHAR(3)             -- MKD, EUR, ALL
```

### `data_sources` Table
```sql
source_id UUID PRIMARY KEY
country_code VARCHAR(2) FK           -- References countries
source_name VARCHAR(200)             -- "e-nabavki.gov.mk"
source_type VARCHAR(50)              -- website, api, ted
base_url TEXT
scraper_class VARCHAR(200)           -- "nabavki_spider.NabavkiSpider"
scraper_config JSONB                 -- Spider settings
is_active BOOLEAN
scrape_frequency VARCHAR(50)         -- hourly, daily, weekly
priority INTEGER                     -- 0-100
success_rate NUMERIC(5,2)
consecutive_failures INTEGER
total_tenders_scraped INTEGER
```

## Columns Added

### `tenders` Table
```sql
ALTER TABLE tenders ADD country_code VARCHAR(2) DEFAULT 'MK';
ALTER TABLE tenders ADD source_id UUID;
```

### `epazar_tenders` Table
```sql
ALTER TABLE epazar_tenders ADD country_code VARCHAR(2) DEFAULT 'MK';
ALTER TABLE epazar_tenders ADD source_id UUID;
```

## Materialized View

### `country_statistics`
```sql
country_code
country_name_en
total_tenders
awarded_tenders
open_tenders
total_estimated_eur
total_actual_eur
unique_procuring_entities
unique_winners
earliest_tender_date
latest_tender_date
```

Refresh daily:
```sql
REFRESH MATERIALIZED VIEW country_statistics;
```

## Functions

### Get Active Countries
```sql
SELECT * FROM get_active_countries();
-- Returns: country_code, country_name_en, total_tenders, is_featured
```

### Update Stats (Automatic)
Trigger `update_country_stats()` fires on INSERT to tenders.

## Initial Data

### Countries (32 total)

**Active:**
- MK (North Macedonia) - scraper_enabled=TRUE, status='active'

**Featured Balkans (planned):**
- AL (Albania) - OCDS API available
- RS (Serbia)
- BA (Bosnia and Herzegovina)
- ME (Montenegro)
- XK (Kosovo)

**Featured EU Neighbors (planned):**
- GR (Greece) - TED
- BG (Bulgaria) - TED
- HR (Croatia) - TED
- SI (Slovenia) - TED

**Other EU (22 countries):**
AT, BE, CY, CZ, DE, DK, EE, ES, FI, FR, HU, IE, IT, LT, LU, LV, MT, NL, PL, PT, RO, SE, SK

### Data Sources (5 configured)

1. **e-nabavki.gov.mk** (MK) - Active, priority 100
2. **e-pazar.gov.mk** (MK) - Active, priority 90
3. **TED API** (EU) - Planned, priority 80
4. **APP.MAP** (AL) - Planned, OCDS available
5. **Portal UJN** (RS) - Planned

## Key Indexes

```sql
idx_tenders_country_code
idx_tenders_source_id
idx_tenders_country_status          -- (country_code, status)
idx_tenders_country_date            -- (country_code, publication_date)
idx_countries_region
idx_countries_scraper_enabled
idx_data_sources_country
idx_data_sources_active
```

## Common Queries

### Get tenders by country
```sql
SELECT * FROM tenders
WHERE country_code = 'MK' AND status = 'open'
ORDER BY publication_date DESC
LIMIT 50;
```

### Get country stats
```sql
SELECT * FROM country_statistics
WHERE country_code = 'MK';
```

### Get active scrapers
```sql
SELECT country_code, source_name, last_success_at, consecutive_failures
FROM data_sources
WHERE is_active = TRUE
ORDER BY priority DESC;
```

### Check scraper health
```sql
SELECT ds.country_code, c.country_name_en, ds.source_name,
       ds.consecutive_failures, ds.success_rate, ds.last_error_at
FROM data_sources ds
JOIN countries c ON ds.country_code = c.country_code
WHERE ds.is_active = TRUE AND ds.consecutive_failures > 3;
```

## Rollback

See MULTI_COUNTRY_MIGRATION_GUIDE.md for full rollback script.

Quick rollback:
```sql
BEGIN;
DROP TRIGGER IF EXISTS trigger_update_country_stats ON tenders;
DROP FUNCTION IF EXISTS update_country_stats();
DROP FUNCTION IF EXISTS get_active_countries();
DROP MATERIALIZED VIEW IF EXISTS country_statistics;
ALTER TABLE tenders DROP COLUMN country_code, DROP COLUMN source_id;
ALTER TABLE epazar_tenders DROP COLUMN country_code, DROP COLUMN source_id;
DROP TABLE data_sources CASCADE;
DROP TABLE countries CASCADE;
COMMIT;
```

## Next Steps

1. Run migration: `psql -f db/migrations/019_multi_country.sql`
2. Update backend models (Country, DataSource)
3. Add country filter to API endpoints
4. Build country selector UI component
5. Create country landing pages
6. Develop Albania scraper (OCDS API)
7. Integrate TED API for EU coverage

## Files

- **Migration:** `/Users/tamsar/Downloads/nabavkidata/db/migrations/019_multi_country.sql`
- **Guide:** `/Users/tamsar/Downloads/nabavkidata/MULTI_COUNTRY_MIGRATION_GUIDE.md`
- **Quick Ref:** This file
