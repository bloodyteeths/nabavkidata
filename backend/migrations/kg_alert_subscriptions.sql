-- KG Phase 4: anon email subscriptions for tender digests
-- Runs on: sudo -u postgres psql -d nabavkidata -f kg_alert_subscriptions.sql

CREATE TABLE IF NOT EXISTS kg.alert_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verify_token TEXT NOT NULL,
    unsubscribe_token TEXT NOT NULL,
    verified_at TIMESTAMPTZ,
    last_digest_sent_at TIMESTAMPTZ,
    unsubscribed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(email)
);

CREATE INDEX IF NOT EXISTS idx_kg_sub_verify_token ON kg.alert_subscriptions(verify_token) WHERE is_verified = FALSE;
CREATE INDEX IF NOT EXISTS idx_kg_sub_unsub_token ON kg.alert_subscriptions(unsubscribe_token);
CREATE INDEX IF NOT EXISTS idx_kg_sub_active ON kg.alert_subscriptions(email) WHERE is_verified = TRUE AND unsubscribed_at IS NULL;

COMMENT ON TABLE kg.alert_subscriptions IS 'Anonymous email subscriptions for Kyrgyzstan tender digests. Email-based, no auth required.';
