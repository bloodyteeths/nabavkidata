-- 034_bid_jobs.sql — Phase 2 of the done-for-you bid service (Oct 2026)
-- One bid_job per (client, tender). Payment by invoice; an admin marks it paid.
-- Tender documents are scraped (tables tenders/documents) — clients upload only
-- their own company documents (client_documents). Deliverables are uploaded by
-- admins (bid_job_files). Phase 3 AI drafting plugs in at status 'preparing'.
-- All timestamps are TIMESTAMPTZ: the API serialises them with an offset and
-- the frontend renders them in Europe/Skopje.

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS calendar_token VARCHAR(64);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_calendar_token
    ON users(calendar_token) WHERE calendar_token IS NOT NULL;

CREATE TABLE IF NOT EXISTS bid_jobs (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- RESTRICT: a client with bid jobs (success-fee receivables + audit trail)
    -- cannot be hard-deleted by accident; api/admin.py refuses with 409.
    user_id            UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    tender_id          VARCHAR(100) NOT NULL,   -- tenders.tender_id (no FK: scraper upserts tenders)
    status             VARCHAR(30) NOT NULL DEFAULT 'requested'
                       CHECK (status IN ('requested','payment_required','preparing','ready',
                                         'changes_requested','approved','submitted',
                                         'won','lost','cancelled')),
    prep_fee_mkd       INTEGER,                 -- snapshot of users.prep_fee_mkd at begin; admin may change until paid
    success_fee_pct    NUMERIC(5,2),            -- snapshot of users.success_fee_pct at begin
    free               BOOLEAN NOT NULL DEFAULT FALSE,
    invoice_number     VARCHAR(50),
    invoice_issued_at  TIMESTAMPTZ,
    invoice_file_path  TEXT,                    -- invoice PDF (relative to BID_FILES_DIR), never returned
    invoice_file_name  VARCHAR(255),
    paid_at            TIMESTAMPTZ,
    assigned_to        UUID REFERENCES users(user_id) ON DELETE SET NULL,
    admin_notes        TEXT,
    client_note        TEXT,
    published_at       TIMESTAMPTZ,
    publish_count      INTEGER NOT NULL DEFAULT 0,
    reopen_count       INTEGER NOT NULL DEFAULT 0,
    approved_at        TIMESTAMPTZ,
    submitted_at       TIMESTAMPTZ,
    outcome            VARCHAR(20) CHECK (outcome IN ('won','lost','cancelled')),
    outcome_at         TIMESTAMPTZ,
    cancelled_at       TIMESTAMPTZ,
    cancelled_by       VARCHAR(10) CHECK (cancelled_by IN ('client','admin')),
    cancel_reason      TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_bid_jobs_user_tender UNIQUE (user_id, tender_id)
);
CREATE INDEX IF NOT EXISTS idx_bid_jobs_status ON bid_jobs(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_bid_jobs_user ON bid_jobs(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_bid_jobs_tender ON bid_jobs(tender_id);
CREATE INDEX IF NOT EXISTS idx_bid_jobs_assigned ON bid_jobs(assigned_to) WHERE assigned_to IS NOT NULL;

CREATE TABLE IF NOT EXISTS bid_job_files (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id           UUID NOT NULL REFERENCES bid_jobs(id) ON DELETE CASCADE,
    kind             VARCHAR(20) NOT NULL DEFAULT 'drugo'
                     CHECK (kind IN ('tehnicka','finansiska','izjava','checklist','drugo')),
    title            VARCHAR(300) NOT NULL,
    storage_path     TEXT NOT NULL,            -- relative to BID_FILES_DIR, never returned by the API
    original_name    VARCHAR(255) NOT NULL,
    mime             VARCHAR(150),
    size_bytes       BIGINT NOT NULL DEFAULT 0,
    client_visible   BOOLEAN NOT NULL DEFAULT FALSE,
    approval_status  VARCHAR(20) NOT NULL DEFAULT 'pending'
                     CHECK (approval_status IN ('pending','approved','changes_requested')),
    client_comment   TEXT,
    reviewed_at      TIMESTAMPTZ,
    uploaded_by      UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bid_job_files_job ON bid_job_files(job_id, created_at);

CREATE TABLE IF NOT EXISTS client_documents (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category         VARCHAR(30) NOT NULL DEFAULT 'drugo'
                     CHECK (category IN ('tekovna_sostojba','danocno_uverenie','ddv_registracija',
                                         'kazneno_potvrda','iso_sertifikat','drug_sertifikat',
                                         'referenca','boni_finansiski','cv_personal','drugo')),
    title            VARCHAR(300) NOT NULL,
    storage_path     TEXT NOT NULL,
    original_name    VARCHAR(255) NOT NULL,
    mime             VARCHAR(150),
    size_bytes       BIGINT NOT NULL DEFAULT 0,
    expires_on       DATE,
    uploaded_by_role VARCHAR(10) NOT NULL DEFAULT 'client' CHECK (uploaded_by_role IN ('client','admin')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_client_documents_user ON client_documents(user_id, category);
CREATE INDEX IF NOT EXISTS idx_client_documents_expiry ON client_documents(expires_on) WHERE expires_on IS NOT NULL;

CREATE TABLE IF NOT EXISTS bid_messages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- the client who owns the thread
    job_id            UUID REFERENCES bid_jobs(id) ON DELETE CASCADE,           -- NULL = general thread
    sender_role       VARCHAR(10) NOT NULL CHECK (sender_role IN ('client','admin')),
    sender_user_id    UUID REFERENCES users(user_id) ON DELETE SET NULL,
    body              TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 5000),
    read_by_client_at TIMESTAMPTZ,
    read_by_admin_at  TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bid_messages_thread ON bid_messages(user_id, job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_bid_messages_unread_client
    ON bid_messages(user_id) WHERE sender_role = 'admin' AND read_by_client_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_bid_messages_unread_admin
    ON bid_messages(user_id) WHERE sender_role = 'client' AND read_by_admin_at IS NULL;

CREATE TABLE IF NOT EXISTS bid_job_events (
    id             BIGSERIAL PRIMARY KEY,
    job_id         UUID NOT NULL REFERENCES bid_jobs(id) ON DELETE CASCADE,
    kind           VARCHAR(10) NOT NULL CHECK (kind IN ('audit','notify')),
    event          VARCHAR(120) NOT NULL,
    actor_role     VARCHAR(10) CHECK (actor_role IN ('client','admin','system')),
    actor_user_id  UUID REFERENCES users(user_id) ON DELETE SET NULL,
    detail         JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bid_job_events_job ON bid_job_events(job_id, created_at);
-- Notification dedupe: one row per (job, notification key), ever.
CREATE UNIQUE INDEX IF NOT EXISTS ux_bid_job_events_notify
    ON bid_job_events(job_id, event) WHERE kind = 'notify';

COMMIT;
