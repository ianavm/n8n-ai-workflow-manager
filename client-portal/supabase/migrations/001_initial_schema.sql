-- ============================================
-- AnyVision Media — Client Portal Database Schema
-- ============================================

-- 1. ADMIN/EMPLOYEE USERS (must be created before clients for FK)
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID UNIQUE NOT NULL,  -- references auth.users(id)
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee' CHECK (role IN ('owner', 'employee')),
    created_at TIMESTAMPTZ DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- 2. CLIENTS (portal users)
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID UNIQUE NOT NULL,  -- references auth.users(id)
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    company_name TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'inactive')),
    api_key UUID UNIQUE DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    created_by UUID REFERENCES admin_users(id)
);

CREATE INDEX idx_clients_auth_user ON clients (auth_user_id);
CREATE INDEX idx_clients_api_key ON clients (api_key);
CREATE INDEX idx_clients_status ON clients (status);

-- 3. WORKFLOWS (per client)
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'error')),
    external_id TEXT,
    platform TEXT DEFAULT 'n8n',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_workflows_client ON workflows (client_id);

-- 4. STAT EVENTS (unified event log)
CREATE TABLE stat_events (
    id BIGSERIAL PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES workflows(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'message_received', 'message_sent', 'lead_created', 'workflow_crash'
    )),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_stat_events_client_type_date ON stat_events (client_id, event_type, created_at DESC);
CREATE INDEX idx_stat_events_created_at ON stat_events (created_at DESC);
CREATE INDEX idx_stat_events_type ON stat_events (event_type);

-- 5. WORKFLOW EXECUTIONS (for uptime/success tracking)
CREATE TABLE workflow_executions (
    id BIGSERIAL PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('success', 'failure')),
    error_message TEXT,
    executed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_executions_client_date ON workflow_executions (client_id, executed_at DESC);
CREATE INDEX idx_executions_workflow ON workflow_executions (workflow_id);

-- 6. CLIENT NOTES (admin internal comments)
CREATE TABLE client_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    admin_id UUID NOT NULL REFERENCES admin_users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_notes_client ON client_notes (client_id, created_at DESC);

-- 7. ACTIVITY LOG (audit trail)
CREATE TABLE activity_log (
    id BIGSERIAL PRIMARY KEY,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('admin', 'client', 'system', 'api')),
    actor_id UUID,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id UUID,
    details JSONB DEFAULT '{}',
    ip_address TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_activity_log_date ON activity_log (created_at DESC);
CREATE INDEX idx_activity_log_actor ON activity_log (actor_type, actor_id);

-- ============================================
-- ROW-LEVEL SECURITY
-- ============================================

ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE stat_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;

-- Clients can only see their own record
CREATE POLICY "clients_own_data" ON clients
    FOR SELECT USING (auth_user_id = auth.uid());

-- Clients can see their own workflows
CREATE POLICY "clients_own_workflows" ON workflows
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

-- Clients can see their own stats
CREATE POLICY "clients_own_stats" ON stat_events
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

-- Clients can see their own executions
CREATE POLICY "clients_own_executions" ON workflow_executions
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

-- Admin users can see their own record
CREATE POLICY "admins_own_data" ON admin_users
    FOR SELECT USING (auth_user_id = auth.uid());

-- Admins have full access to all tables
CREATE POLICY "admins_all_clients" ON clients
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_workflows" ON workflows
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_stats" ON stat_events
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_executions" ON workflow_executions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_notes" ON client_notes
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_activity" ON activity_log
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to get client stats summary for a date range
CREATE OR REPLACE FUNCTION get_client_stats(
    p_client_id UUID,
    p_start_date TIMESTAMPTZ DEFAULT now() - interval '30 days',
    p_end_date TIMESTAMPTZ DEFAULT now()
)
RETURNS TABLE (
    event_type TEXT,
    total_count BIGINT
) AS $$
    SELECT event_type, COUNT(*) as total_count
    FROM stat_events
    WHERE client_id = p_client_id
      AND created_at BETWEEN p_start_date AND p_end_date
    GROUP BY event_type;
$$ LANGUAGE sql SECURITY DEFINER;

-- Function to get daily stats for trend charts
CREATE OR REPLACE FUNCTION get_daily_stats(
    p_client_id UUID,
    p_event_type TEXT,
    p_start_date TIMESTAMPTZ DEFAULT now() - interval '30 days',
    p_end_date TIMESTAMPTZ DEFAULT now()
)
RETURNS TABLE (
    day DATE,
    count BIGINT
) AS $$
    SELECT date_trunc('day', created_at)::date as day, COUNT(*) as count
    FROM stat_events
    WHERE client_id = p_client_id
      AND event_type = p_event_type
      AND created_at BETWEEN p_start_date AND p_end_date
    GROUP BY day
    ORDER BY day;
$$ LANGUAGE sql SECURITY DEFINER;

-- Function to get workflow uptime/success rate
CREATE OR REPLACE FUNCTION get_uptime_stats(
    p_client_id UUID,
    p_start_date TIMESTAMPTZ DEFAULT now() - interval '30 days',
    p_end_date TIMESTAMPTZ DEFAULT now()
)
RETURNS TABLE (
    total_executions BIGINT,
    successful BIGINT,
    failed BIGINT,
    success_rate NUMERIC
) AS $$
    SELECT
        COUNT(*) as total_executions,
        COUNT(*) FILTER (WHERE status = 'success') as successful,
        COUNT(*) FILTER (WHERE status = 'failure') as failed,
        ROUND(
            COUNT(*) FILTER (WHERE status = 'success')::numeric / GREATEST(COUNT(*), 1) * 100,
            2
        ) as success_rate
    FROM workflow_executions
    WHERE client_id = p_client_id
      AND executed_at BETWEEN p_start_date AND p_end_date;
$$ LANGUAGE sql SECURITY DEFINER;
