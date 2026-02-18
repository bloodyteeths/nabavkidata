-- Migration 027: Stripe Connect for referral payouts
-- Adds Connect account fields to users and transfer tracking to payouts

-- Stripe Connect fields on users
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_connect_id VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_connect_status VARCHAR(30) DEFAULT NULL;
-- NULL = not started, 'pending' = onboarding started, 'active' = verified, 'restricted' = needs action

-- Transfer tracking on payouts
ALTER TABLE referral_payouts ADD COLUMN IF NOT EXISTS stripe_transfer_id VARCHAR(255) UNIQUE;
ALTER TABLE referral_payouts ADD COLUMN IF NOT EXISTS payout_method VARCHAR(20) DEFAULT 'manual';
-- 'manual' = bank transfer, 'stripe' = via Stripe Connect transfer
