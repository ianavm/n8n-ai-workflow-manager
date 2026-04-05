-- Migration 027: Self-service OAuth connections for integration hub
-- Clients connect their own Google Ads, Meta, QuickBooks, etc.

CREATE TABLE IF NOT EXISTS oauth_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN (
        'google_ads', 'meta_ads', 'quickbooks', 'google_workspace',
        'tiktok_ads', 'linkedin_ads', 'whatsapp_business'
    )),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'connected', 'expired', 'revoked', 'error'
    )),
    provider_account_id TEXT,
    provider_account_name TEXT,
    provider_metadata JSONB DEFAULT '{}',
    scopes TEXT[] DEFAULT '{}',
    last_refreshed_at TIMESTAMPTZ,
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    connected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(client_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_oauth_connections_client ON oauth_connections(client_id);

ALTER TABLE oauth_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "client_own_oauth_select" ON oauth_connections
    FOR SELECT USING (client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid()));

CREATE POLICY "admin_all_oauth" ON oauth_connections
    FOR ALL USING (EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid()));

CREATE POLICY "service_oauth" ON oauth_connections
    FOR ALL USING (auth.role() = 'service_role');

-- Auto-update timestamp trigger
CREATE TRIGGER trg_oauth_connections_updated
    BEFORE UPDATE ON oauth_connections FOR EACH ROW
    EXECUTE FUNCTION update_onboarding_updated_at();
