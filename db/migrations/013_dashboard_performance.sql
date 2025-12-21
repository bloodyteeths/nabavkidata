-- Migration: Dashboard performance optimization
-- Adds indexes for faster dashboard queries

-- Index for open tenders ordered by created_at (main dashboard query)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenders_status_created
ON tenders(status, created_at DESC)
WHERE status = 'open';

-- Index for competitor tracking by winner
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenders_winner_updated
ON tenders(updated_at DESC)
WHERE winner IS NOT NULL;

-- Partial index for open tenders with closing dates (deadline insights)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenders_open_closing
ON tenders(closing_date)
WHERE status = 'open' AND closing_date IS NOT NULL;
