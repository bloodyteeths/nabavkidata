-- ============================================================================
-- Scraping Jobs Table Migration
-- Creates table for tracking scraper job history and status
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create scraping_jobs table
CREATE TABLE IF NOT EXISTS scraping_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    tenders_scraped INTEGER DEFAULT 0 CHECK (tenders_scraped >= 0),
    documents_scraped INTEGER DEFAULT 0 CHECK (documents_scraped >= 0),
    errors_count INTEGER DEFAULT 0 CHECK (errors_count >= 0),
    error_message TEXT,
    spider_name VARCHAR(100),
    incremental BOOLEAN DEFAULT TRUE,
    last_scraped_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_status
    ON scraping_jobs(status);

CREATE INDEX IF NOT EXISTS idx_scraping_jobs_started_at
    ON scraping_jobs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_scraping_jobs_completed_at
    ON scraping_jobs(completed_at DESC)
    WHERE completed_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_scraping_jobs_spider_name
    ON scraping_jobs(spider_name);

-- Add comments for documentation
COMMENT ON TABLE scraping_jobs IS 'Tracks scraper job execution history and status';
COMMENT ON COLUMN scraping_jobs.job_id IS 'Unique identifier for scraping job';
COMMENT ON COLUMN scraping_jobs.started_at IS 'Timestamp when job started';
COMMENT ON COLUMN scraping_jobs.completed_at IS 'Timestamp when job completed (NULL if still running)';
COMMENT ON COLUMN scraping_jobs.status IS 'Job status: running, completed, or failed';
COMMENT ON COLUMN scraping_jobs.tenders_scraped IS 'Number of tenders successfully scraped';
COMMENT ON COLUMN scraping_jobs.documents_scraped IS 'Number of documents successfully scraped';
COMMENT ON COLUMN scraping_jobs.errors_count IS 'Number of errors encountered during scraping';
COMMENT ON COLUMN scraping_jobs.error_message IS 'Error message if job failed';
COMMENT ON COLUMN scraping_jobs.spider_name IS 'Name of spider that ran (e.g., nabavki)';
COMMENT ON COLUMN scraping_jobs.incremental IS 'Whether this was an incremental scrape (only new items)';
COMMENT ON COLUMN scraping_jobs.last_scraped_date IS 'Timestamp of last item scraped';

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE ON scraping_jobs TO scraper_user;
-- GRANT SELECT ON scraping_jobs TO api_user;

-- Verify table creation
SELECT
    tablename,
    tableowner,
    hasindexes,
    hasrules,
    hastriggers
FROM pg_tables
WHERE tablename = 'scraping_jobs';

-- Show indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'scraping_jobs';

-- ============================================================================
-- Sample Queries for Testing
-- ============================================================================

-- Insert test job (for testing only)
/*
INSERT INTO scraping_jobs (
    started_at,
    status,
    spider_name,
    incremental
) VALUES (
    NOW(),
    'running',
    'nabavki',
    TRUE
) RETURNING job_id;
*/

-- Get recent jobs
/*
SELECT
    job_id,
    started_at,
    completed_at,
    status,
    tenders_scraped,
    documents_scraped,
    errors_count,
    EXTRACT(EPOCH FROM (completed_at - started_at)) AS duration_seconds
FROM scraping_jobs
ORDER BY started_at DESC
LIMIT 10;
*/

-- Get job statistics
/*
SELECT
    status,
    COUNT(*) AS job_count,
    AVG(tenders_scraped) AS avg_tenders,
    AVG(documents_scraped) AS avg_documents,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_duration_seconds
FROM scraping_jobs
WHERE completed_at IS NOT NULL
GROUP BY status;
*/

-- Find recent failures
/*
SELECT
    job_id,
    started_at,
    error_message,
    tenders_scraped,
    documents_scraped
FROM scraping_jobs
WHERE status = 'failed'
ORDER BY started_at DESC
LIMIT 5;
*/

-- Calculate error rate (last 24 hours)
/*
SELECT
    COUNT(*) FILTER (WHERE status = 'failed') * 100.0 /
        NULLIF(COUNT(*), 0) AS error_rate_percent,
    COUNT(*) AS total_jobs,
    COUNT(*) FILTER (WHERE status = 'completed') AS successful_jobs,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed_jobs,
    COUNT(*) FILTER (WHERE status = 'running') AS running_jobs
FROM scraping_jobs
WHERE started_at > NOW() - INTERVAL '24 hours';
*/

-- ============================================================================
-- Cleanup Queries (Optional)
-- ============================================================================

-- Delete old jobs (older than 90 days)
/*
DELETE FROM scraping_jobs
WHERE started_at < NOW() - INTERVAL '90 days';
*/

-- Archive completed jobs (move to archive table)
/*
CREATE TABLE scraping_jobs_archive AS
SELECT * FROM scraping_jobs
WHERE status IN ('completed', 'failed')
  AND started_at < NOW() - INTERVAL '90 days';

DELETE FROM scraping_jobs
WHERE job_id IN (SELECT job_id FROM scraping_jobs_archive);
*/

-- ============================================================================
-- Rollback (if needed)
-- ============================================================================

-- Drop table and indexes
/*
DROP TABLE IF EXISTS scraping_jobs CASCADE;
*/
