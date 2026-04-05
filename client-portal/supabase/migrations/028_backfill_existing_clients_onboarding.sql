-- Migration 028: Backfill existing clients as onboarded
-- Prevents existing clients from being redirected to the wizard
UPDATE clients
SET onboarding_completed_at = created_at,
    profile_completed = true
WHERE onboarding_completed_at IS NULL;
