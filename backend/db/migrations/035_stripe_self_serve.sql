-- 035_stripe_self_serve.sql — Phase 2b of the done-for-you bid service (14 Oct 2026)
-- Self-serve card payment of the prep fee (Stripe Checkout, card saved for the
-- success fee), offline success-fee authorisation, and detected client wins.
-- No unique index on LOWER(users.email): existing duplicates would break it.

BEGIN;
-- users: card mandate + success-fee authorisation (stripe_customer_id exists since 001; reused)
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_mandate_pm_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_card_brand VARCHAR(30);
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_card_last4 VARCHAR(4);
ALTER TABLE users ADD COLUMN IF NOT EXISTS success_fee_authorised_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS success_fee_authorised_via VARCHAR(10);
ALTER TABLE users ADD COLUMN IF NOT EXISTS success_fee_authorised_ref VARCHAR(120);
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_sfa_via_check;
ALTER TABLE users ADD CONSTRAINT users_sfa_via_check
  CHECK (success_fee_authorised_via IS NULL OR success_fee_authorised_via IN ('card','offline'));
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- bid_jobs: how it was paid
ALTER TABLE bid_jobs ADD COLUMN IF NOT EXISTS paid_via VARCHAR(10);
ALTER TABLE bid_jobs DROP CONSTRAINT IF EXISTS bid_jobs_paid_via_check;
ALTER TABLE bid_jobs ADD CONSTRAINT bid_jobs_paid_via_check
  CHECK (paid_via IS NULL OR paid_via IN ('stripe','invoice','free'));
ALTER TABLE bid_jobs ADD COLUMN IF NOT EXISTS stripe_checkout_session_id VARCHAR(255);
ALTER TABLE bid_jobs ADD COLUMN IF NOT EXISTS stripe_payment_intent_id VARCHAR(255);
ALTER TABLE bid_jobs ADD COLUMN IF NOT EXISTS invoice_requested_at TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS ux_bid_jobs_checkout_session
  ON bid_jobs(stripe_checkout_session_id) WHERE stripe_checkout_session_id IS NOT NULL;
UPDATE bid_jobs SET paid_via='invoice' WHERE paid_at IS NOT NULL AND paid_via IS NULL;
UPDATE bid_jobs SET paid_via='free' WHERE free AND paid_via IS NULL;

CREATE TABLE IF NOT EXISTS client_wins (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
  job_id                UUID REFERENCES bid_jobs(id) ON DELETE SET NULL,
  tender_id             VARCHAR(100) NOT NULL,
  tender_title          TEXT,
  procuring_entity      TEXT,
  matched_name          VARCHAR(500),          -- winner name as it appears in our award data
  match_score           NUMERIC(4,3),          -- 0..1; 1.000 when admin-created from outcome=won
  contract_value_mkd    NUMERIC(15,2),         -- total, as found
  value_source          VARCHAR(10) CHECK (value_source IN ('bid','actual','estimated','admin')),
  contract_months       INTEGER,
  first_year_value_mkd  NUMERIC(15,2),
  success_fee_pct       NUMERIC(5,2),
  prep_fee_credit_mkd   INTEGER NOT NULL DEFAULT 0,
  success_fee_mkd       INTEGER,               -- whole MKD, no cap
  status                VARCHAR(12) NOT NULL DEFAULT 'suspected'
                        CHECK (status IN ('suspected','confirmed','dismissed','invoiced')),
  detected_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  admin_notified_at     TIMESTAMPTZ,
  confirmed_at          TIMESTAMPTZ,
  confirmed_by          UUID REFERENCES users(user_id) ON DELETE SET NULL,
  notice_sent_at        TIMESTAMPTZ,
  charge_not_before     TIMESTAMPTZ,           -- notice_sent_at + 7 days
  stripe_invoice_id     VARCHAR(255),
  invoice_number        VARCHAR(50),
  invoiced_at           TIMESTAMPTZ,
  dismissed_at          TIMESTAMPTZ,
  notes                 TEXT,
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_client_wins_user_tender UNIQUE (user_id, tender_id)
);
CREATE INDEX IF NOT EXISTS idx_client_wins_status ON client_wins(status, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_client_wins_job ON client_wins(job_id);
COMMIT;
