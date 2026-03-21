-- ============================================
-- WhatsApp Connections — Per-client WhatsApp Business API config
-- Required by: /portal/whatsapp page + /api/portal/whatsapp route
-- ============================================

CREATE TABLE whatsapp_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    waba_id TEXT,                    -- WhatsApp Business Account ID
    phone_number_id TEXT,            -- Meta phone number ID for Cloud API
    display_phone_number TEXT,       -- Human-readable phone (+27 82 123 4567)
    business_name TEXT,              -- Verified business name from Meta
    access_token TEXT,               -- Encrypted at rest by Supabase
    status TEXT NOT NULL DEFAULT 'not_connected'
        CHECK (status IN ('not_connected', 'pending', 'connected', 'error')),
    connected_at TIMESTAMPTZ,
    coexistence_enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_whatsapp_connections_client ON whatsapp_connections(client_id);
CREATE INDEX idx_whatsapp_connections_status ON whatsapp_connections(status);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_whatsapp_connections_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_whatsapp_connections_updated_at
    BEFORE UPDATE ON whatsapp_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_whatsapp_connections_updated_at();

-- ============================================
-- ROW-LEVEL SECURITY
-- ============================================

ALTER TABLE whatsapp_connections ENABLE ROW LEVEL SECURITY;

-- Clients see only their own connection
CREATE POLICY "clients_own_whatsapp" ON whatsapp_connections
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

-- Clients can update their own connection (toggle coexistence, disconnect)
CREATE POLICY "clients_update_whatsapp" ON whatsapp_connections
    FOR UPDATE USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    )
    WITH CHECK (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

-- Admins have full access
CREATE POLICY "admins_all_whatsapp" ON whatsapp_connections
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- Service role can insert (used by /api/portal/whatsapp route)
CREATE POLICY "service_insert_whatsapp" ON whatsapp_connections
    FOR INSERT WITH CHECK (true);
