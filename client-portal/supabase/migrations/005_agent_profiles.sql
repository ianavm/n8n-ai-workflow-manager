-- Agent profiles for WhatsApp AI toggle dashboard
CREATE TABLE agent_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  agent_id TEXT NOT NULL UNIQUE,
  agent_name TEXT NOT NULL,
  phone_number TEXT,
  email TEXT,
  is_online BOOLEAN DEFAULT false,
  manual_override TEXT CHECK (manual_override IN ('online', 'offline')),
  manual_override_expiry TIMESTAMPTZ,
  business_hours_start TEXT DEFAULT '08:00',
  business_hours_end TEXT DEFAULT '17:00',
  timezone TEXT DEFAULT 'Africa/Johannesburg',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_agent_profiles_client ON agent_profiles(client_id);

ALTER TABLE agent_profiles ENABLE ROW LEVEL SECURITY;

-- Clients see only their own agents
CREATE POLICY "clients_own_agents" ON agent_profiles
  FOR SELECT USING (client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid()));

-- Clients can update their own agents (toggle only)
CREATE POLICY "clients_update_agents" ON agent_profiles
  FOR UPDATE USING (client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid()))
  WITH CHECK (client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid()));

-- Admins have full access
CREATE POLICY "admins_all_agents" ON agent_profiles
  FOR ALL USING (EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid()));
