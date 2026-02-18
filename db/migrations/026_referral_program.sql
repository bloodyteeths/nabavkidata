-- Migration 026: Referral Program
-- Date: 2026-02-18
-- Purpose: Add referral tracking tables for affiliate-style commissions (20% recurring)

BEGIN;

-- 1. Add referred_by column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by UUID REFERENCES users(user_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);

-- 2. Referral codes table (one code per user)
CREATE TABLE IF NOT EXISTS referral_codes (
    code_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    code VARCHAR(20) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code);

-- 3. Referral conversions (tracks referred user -> referrer relationship)
CREATE TABLE IF NOT EXISTS referral_conversions (
    conversion_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referrer_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    referred_user_id UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    stripe_subscription_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'inactive', 'cancelled')),
    converted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_referral_conversions_referrer ON referral_conversions(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referral_conversions_status ON referral_conversions(status);

-- 4. Referral earnings (one row per commission credit, keyed by Stripe invoice_id for idempotency)
CREATE TABLE IF NOT EXISTS referral_earnings (
    earning_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referrer_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    referred_user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    conversion_id UUID NOT NULL REFERENCES referral_conversions(conversion_id) ON DELETE CASCADE,
    invoice_id VARCHAR(255) NOT NULL UNIQUE,
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_referral_earnings_referrer ON referral_earnings(referrer_id);

-- 5. Referral payouts (admin manually pays out via bank transfer)
CREATE TABLE IF NOT EXISTS referral_payouts (
    payout_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'completed', 'rejected')),
    bank_name VARCHAR(255),
    account_holder VARCHAR(255),
    iban VARCHAR(50),
    admin_notes TEXT,
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    paid_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_referral_payouts_user ON referral_payouts(user_id);
CREATE INDEX IF NOT EXISTS idx_referral_payouts_status ON referral_payouts(status);

COMMIT;
