-- Phase 5 Migration: Incremental Scraping & Change Detection
--
-- This migration adds fields needed for incremental scraping:
-- - last_modified: When the tender was last changed on the source website
-- - scrape_count: How many times this tender has been scraped
-- - content_hash: SHA-256 hash of tender content for change detection
-- - first_scraped_at: When this tender was first discovered
-- - source_category: Which listing category the tender came from (Phase 4)

-- Add incremental scraping fields to tenders table
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS last_modified TIMESTAMP;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS scrape_count INTEGER DEFAULT 1;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS first_scraped_at TIMESTAMP;
ALTER TABLE tenders ADD COLUMN IF NOT EXISTS source_category VARCHAR(50);

-- Set first_scraped_at to scraped_at for existing records
UPDATE tenders SET first_scraped_at = scraped_at WHERE first_scraped_at IS NULL;

-- Create index on content_hash for efficient change detection lookups
CREATE INDEX IF NOT EXISTS idx_tenders_content_hash ON tenders(content_hash);

-- Create index on last_modified for filtering recently changed tenders
CREATE INDEX IF NOT EXISTS idx_tenders_last_modified ON tenders(last_modified);

-- Create index on source_category for category-based queries
CREATE INDEX IF NOT EXISTS idx_tenders_source_category ON tenders(source_category);

-- Create composite index for incremental scraping queries
CREATE INDEX IF NOT EXISTS idx_tenders_incremental ON tenders(status, last_modified, scraped_at);

-- Add comments for documentation
COMMENT ON COLUMN tenders.last_modified IS 'Timestamp when tender was last modified on source website';
COMMENT ON COLUMN tenders.scrape_count IS 'Number of times this tender has been scraped';
COMMENT ON COLUMN tenders.content_hash IS 'SHA-256 hash of tender content for change detection';
COMMENT ON COLUMN tenders.first_scraped_at IS 'Timestamp when tender was first discovered';
COMMENT ON COLUMN tenders.source_category IS 'Category listing where tender was found (active, awarded, cancelled, etc.)';

-- Create scrape_history table for tracking scrape runs
CREATE TABLE IF NOT EXISTS scrape_history (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    mode VARCHAR(20) NOT NULL DEFAULT 'full',  -- 'full' or 'incremental'
    category VARCHAR(50),  -- which category was scraped
    tenders_found INTEGER DEFAULT 0,
    tenders_new INTEGER DEFAULT 0,
    tenders_updated INTEGER DEFAULT 0,
    tenders_unchanged INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    duration_seconds REAL,
    status VARCHAR(20) DEFAULT 'running',  -- 'running', 'completed', 'failed'
    error_message TEXT,
    metadata JSONB  -- for storing additional stats
);

-- Create index on scrape_history for recent runs
CREATE INDEX IF NOT EXISTS idx_scrape_history_started ON scrape_history(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_history_status ON scrape_history(status);

COMMENT ON TABLE scrape_history IS 'Tracks each scraping run for monitoring and debugging';
