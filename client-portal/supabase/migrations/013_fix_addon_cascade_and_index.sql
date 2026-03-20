-- Migration 013: Fix addon FK cascade + add missing Stripe index
-- Fixes: subscription_addons.addon_id should CASCADE on delete
-- Adds: index on subscription_addons.stripe_subscription_id for webhook lookups

-- Fix CASCADE on addon foreign key
ALTER TABLE subscription_addons
    DROP CONSTRAINT IF EXISTS subscription_addons_addon_id_fkey;

ALTER TABLE subscription_addons
    ADD CONSTRAINT subscription_addons_addon_id_fkey
        FOREIGN KEY (addon_id) REFERENCES addons(id) ON DELETE CASCADE;

-- Add partial index for Stripe subscription lookups
CREATE INDEX IF NOT EXISTS idx_sub_addons_stripe
    ON subscription_addons (stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;
