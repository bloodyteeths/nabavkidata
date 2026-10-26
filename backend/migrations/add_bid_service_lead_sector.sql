-- /usluga lead form: capture the sector and make the requirement explicit.
--
-- Why: two Google leads (22.10 and 23.10.2026) arrived with wants_to_win and
-- tender_id both empty and the company field holding only a personal name, so
-- there was nothing to reply to. The form now requires both the sector and what
-- they want to win; this column holds the sector.
--
-- Safe to re-run.
ALTER TABLE bid_service_leads ADD COLUMN IF NOT EXISTS sector varchar(120);

COMMENT ON COLUMN bid_service_leads.sector IS
  'Industry the lead bids in, required on the public /usluga form (not on the compact tender-card form).';
