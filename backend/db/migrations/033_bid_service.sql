-- 033_bid_service.sql — done-for-you bid-writing service (14 Oct 2026)
--
-- NabavkiData stops selling self-serve plans and becomes the engine behind a
-- bid-writing + tender-monitoring service (BidFinder model, see
-- tenderuk/docs/PLATFORM_REPURPOSE_PLAYBOOK.md).
--
-- account_type is a NEW axis, independent of role:
--   free           — legacy self-serve users (grandfathered, no new ones)
--   prospect       — came in through the /usluga form, not yet a paying client
--   managed_client — invoice paid (or free_drafting granted) — we write their bids
--
-- Payment is by invoice (фактура), not card: an admin marks the invoice paid,
-- which promotes prospect -> managed_client.

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS account_type VARCHAR(20) NOT NULL DEFAULT 'free';
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_account_type_check;
ALTER TABLE users ADD CONSTRAINT users_account_type_check
    CHECK (account_type IN ('free', 'prospect', 'managed_client'));
ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(500);
ALTER TABLE users ADD COLUMN IF NOT EXISTS prep_fee_mkd INTEGER NOT NULL DEFAULT 30000;
ALTER TABLE users ADD COLUMN IF NOT EXISTS success_fee_pct NUMERIC(5,2) NOT NULL DEFAULT 5.00;
ALTER TABLE users ADD COLUMN IF NOT EXISTS free_drafting BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_agreed_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS agreement_version VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_users_account_type ON users(account_type);

CREATE TABLE IF NOT EXISTS bid_service_leads (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email            VARCHAR(255) NOT NULL,
    company_name     VARCHAR(500) NOT NULL,
    lead_person      VARCHAR(500),
    phone            VARCHAR(100),
    wants_to_win     TEXT,
    tender_id        VARCHAR(100),          -- tenders.tender_id, e.g. '17400/2026'
    source           VARCHAR(50),           -- usluga | tender_card | paywall | email
    user_id          UUID REFERENCES users(user_id) ON DELETE SET NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'new'
                     CHECK (status IN ('new', 'contacted', 'qualified', 'client', 'rejected')),
    admin_notes      TEXT,
    -- what we already know about them from award history (filled at intake)
    history          JSONB,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bsl_status ON bid_service_leads(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bsl_email ON bid_service_leads(LOWER(email));

COMMIT;
