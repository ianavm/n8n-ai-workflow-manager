-- ============================================================
-- Migration 022: Add marketing usage counters to usage_records
-- Date: 2026-04-04
-- ============================================================

ALTER TABLE usage_records
  ADD COLUMN IF NOT EXISTS campaigns_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS posts_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS marketing_leads_used INTEGER NOT NULL DEFAULT 0;
