-- Migration 025: Onboarding wizard progress tracking
-- Stores per-client wizard state so users can resume across sessions/devices

CREATE TABLE IF NOT EXISTS onboarding_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL UNIQUE REFERENCES clients(id) ON DELETE CASCADE,
    current_step INTEGER NOT NULL DEFAULT 1,
    step_data JSONB NOT NULL DEFAULT '{}',
    completed_steps INTEGER[] NOT NULL DEFAULT '{}',
    skipped_steps INTEGER[] NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_progress_client ON onboarding_progress(client_id);

ALTER TABLE onboarding_progress ENABLE ROW LEVEL SECURITY;

-- Clients can read/update their own onboarding progress
CREATE POLICY "client_own_onboarding_select" ON onboarding_progress
    FOR SELECT USING (client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid()));

CREATE POLICY "client_own_onboarding_update" ON onboarding_progress
    FOR UPDATE USING (client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid()));

-- Admins can see all onboarding progress
CREATE POLICY "admin_all_onboarding" ON onboarding_progress
    FOR ALL USING (EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid()));

-- Service role can do everything (API routes)
CREATE POLICY "service_onboarding" ON onboarding_progress
    FOR ALL USING (auth.role() = 'service_role');

-- Auto-update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_onboarding_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_onboarding_progress_updated
    BEFORE UPDATE ON onboarding_progress FOR EACH ROW
    EXECUTE FUNCTION update_onboarding_updated_at();
