-- Migration 026: Client achievements for activation tracking
-- Tracks onboarding milestones and triggers upgrade prompts

CREATE TABLE IF NOT EXISTS client_achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    achievement_key TEXT NOT NULL,
    achieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(client_id, achievement_key)
);

CREATE INDEX IF NOT EXISTS idx_achievements_client ON client_achievements(client_id);

ALTER TABLE client_achievements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "client_own_achievements_select" ON client_achievements
    FOR SELECT USING (client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid()));

CREATE POLICY "admin_all_achievements" ON client_achievements
    FOR ALL USING (EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid()));

CREATE POLICY "service_achievements" ON client_achievements
    FOR ALL USING (auth.role() = 'service_role');

-- Insert the "account_created" achievement for all existing clients
-- (new clients get it via the signup flow)
INSERT INTO client_achievements (client_id, achievement_key)
SELECT id, 'account_created'
FROM clients
WHERE NOT EXISTS (
    SELECT 1 FROM client_achievements ca
    WHERE ca.client_id = clients.id AND ca.achievement_key = 'account_created'
)
ON CONFLICT (client_id, achievement_key) DO NOTHING;
