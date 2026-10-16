-- 037_ops_focus.sql — Phase 4: operator focus system (16 Oct 2026)
-- Port of BidFinder's focus / hot_signal / lead_watch / weekly shortlist.
--
-- Focus items are derived from LIVE state on every call; these tables only hold
-- human decisions (done/snoozed), the one-send-per-key ledger, the daily digest
-- guard, lead watches and the weekly hand-picked client shortlists.
-- Nothing here sends anything by itself: a human presses Send.
-- Idempotent: safe to re-run.
BEGIN;

CREATE TABLE IF NOT EXISTS focus_item_state (
  key VARCHAR(200) PRIMARY KEY, kind VARCHAR(40) NOT NULL,
  status VARCHAR(10) NOT NULL DEFAULT 'open' CHECK (status IN ('open','done','snoozed')),
  done_at TIMESTAMPTZ, done_via VARCHAR(10) CHECK (done_via IS NULL OR done_via IN ('ui','link','send')),
  done_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
  snoozed_until DATE, title_snapshot TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_focus_item_state_status ON focus_item_state(status, done_at DESC);

-- One Postmark send per dedupe_key, ever (claim-then-send; claim row deleted on failure).
CREATE TABLE IF NOT EXISTS ops_sent_emails (
  id BIGSERIAL PRIMARY KEY, dedupe_key VARCHAR(200) NOT NULL, kind VARCHAR(40) NOT NULL,
  to_email VARCHAR(255) NOT NULL CHECK (to_email = lower(to_email)),
  subject TEXT, body_text TEXT, message_id VARCHAR(100),
  channel VARCHAR(10) NOT NULL CHECK (channel IN ('postmark','manual')),
  sent_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE UNIQUE INDEX IF NOT EXISTS ux_ops_sent_postmark_key ON ops_sent_emails(dedupe_key) WHERE channel = 'postmark';
CREATE INDEX IF NOT EXISTS idx_ops_sent_to ON ops_sent_emails(to_email, sent_at DESC);

CREATE TABLE IF NOT EXISTS ops_digest_log (
  digest_date DATE PRIMARY KEY, sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  item_count INTEGER NOT NULL, message_ok BOOLEAN NOT NULL);

CREATE TABLE IF NOT EXISTS lead_watches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) NOT NULL CHECK (email = lower(email)),
  person_name TEXT, company_name VARCHAR(500),
  user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
  lead_id UUID REFERENCES bid_service_leads(id) ON DELETE SET NULL,
  source VARCHAR(20) NOT NULL DEFAULT 'manual' CHECK (source IN ('lead','prospect','manual')),
  keywords TEXT[] NOT NULL DEFAULT '{}', cpv_prefixes TEXT[] NOT NULL DEFAULT '{}',
  min_value_mkd NUMERIC(15,2), max_value_mkd NUMERIC(15,2),
  min_days_to_close SMALLINT NOT NULL DEFAULT 5,
  cadence_days SMALLINT[] NOT NULL DEFAULT '{3,7,14}', cadence_repeat_days SMALLINT NOT NULL DEFAULT 21,
  anchor_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), follow_up_due DATE,
  touch_count SMALLINT NOT NULL DEFAULT 0, last_touched_at TIMESTAMPTZ,
  replied_at TIMESTAMPTZ, paused_until DATE, active BOOLEAN NOT NULL DEFAULT TRUE, notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE UNIQUE INDEX IF NOT EXISTS ux_lead_watches_email ON lead_watches(email);
CREATE INDEX IF NOT EXISTS idx_lead_watches_due ON lead_watches(follow_up_due) WHERE active AND replied_at IS NULL;

CREATE TABLE IF NOT EXISTS lead_watch_shown (
  watch_id UUID NOT NULL REFERENCES lead_watches(id) ON DELETE CASCADE,
  tender_id VARCHAR(100) NOT NULL, shown_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  channel VARCHAR(10) NOT NULL DEFAULT 'sent' CHECK (channel = 'sent'),
  PRIMARY KEY (watch_id, tender_id));

CREATE TABLE IF NOT EXISTS client_shortlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  week_start DATE NOT NULL,
  status VARCHAR(10) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','skipped')),
  subject TEXT NOT NULL, intro_text TEXT NOT NULL,
  built_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), sent_at TIMESTAMPTZ, sent_message_id VARCHAR(100),
  sent_by UUID REFERENCES users(user_id) ON DELETE SET NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_client_shortlists_user_week UNIQUE (user_id, week_start));
CREATE INDEX IF NOT EXISTS idx_client_shortlists_week ON client_shortlists(week_start, status);

CREATE TABLE IF NOT EXISTS client_shortlist_items (
  shortlist_id UUID NOT NULL REFERENCES client_shortlists(id) ON DELETE CASCADE,
  tender_id VARCHAR(100) NOT NULL, rank SMALLINT NOT NULL, reason TEXT,
  picked BOOLEAN NOT NULL DEFAULT FALSE, note TEXT CHECK (note IS NULL OR char_length(note) <= 300),
  PRIMARY KEY (shortlist_id, tender_id));

DO $$ BEGIN
  IF to_regclass('public.user_behavior') IS NOT NULL THEN
    CREATE INDEX IF NOT EXISTS idx_user_behavior_action_created ON user_behavior(action, created_at DESC);
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_concierge_log_tender ON concierge_log(user_id, tender_id, created_at DESC);

COMMIT;
