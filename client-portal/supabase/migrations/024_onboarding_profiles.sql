-- Migration 024: Add progressive profiling columns to clients table
-- Supports the new frictionless onboarding flow (Phase 1)

ALTER TABLE clients ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS company_size TEXT
  CHECK (company_size IS NULL OR company_size IN ('solo', '2-10', '11-50', '51-200', '200+'));
ALTER TABLE clients ADD COLUMN IF NOT EXISTS primary_need TEXT
  CHECK (primary_need IS NULL OR primary_need IN ('marketing', 'accounting', 'advisory', 'all'));
ALTER TABLE clients ADD COLUMN IF NOT EXISTS signup_method TEXT NOT NULL DEFAULT 'email'
  CHECK (signup_method IN ('email', 'google_sso', 'magic_link'));
ALTER TABLE clients ADD COLUMN IF NOT EXISTS profile_completed BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;
