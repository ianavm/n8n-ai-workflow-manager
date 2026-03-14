-- Migration 007: Orchestrator Dashboard Tables
-- Adds agent_status and orchestrator_alerts for real-time portal display
-- Used by the Central Orchestrator (ORCH-01 to ORCH-04)

-- Agent status tracking (updated by ORCH-01 health monitor every 15 min)
CREATE TABLE IF NOT EXISTS agent_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT UNIQUE NOT NULL,
    agent_name TEXT NOT NULL,
    department TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'degraded', 'down', 'maintenance')),
    health_score INTEGER NOT NULL DEFAULT 100
        CHECK (health_score >= 0 AND health_score <= 100),
    workflows_monitored INTEGER DEFAULT 0,
    last_heartbeat TIMESTAMPTZ DEFAULT now(),
    kpi_summary JSONB DEFAULT '{}'::jsonb,
    error_summary JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Orchestrator alerts (P1-P4 severity, auto-created by ORCH-01)
CREATE TABLE IF NOT EXISTS orchestrator_alerts (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'P3'
        CHECK (severity IN ('P1', 'P2', 'P3', 'P4')),
    category TEXT NOT NULL DEFAULT 'general'
        CHECK (category IN (
            'workflow_failure', 'data_anomaly', 'budget_exceeded',
            'sla_breach', 'manual_required', 'security_alert',
            'client_churn_risk', 'general'
        )),
    title TEXT NOT NULL,
    description TEXT,
    recommended_action TEXT,
    status TEXT DEFAULT 'open'
        CHECK (status IN ('open', 'acknowledged', 'resolved', 'dismissed')),
    resolved_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

-- KPI daily snapshots (written by ORCH-03 daily)
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    agent_id TEXT NOT NULL,
    revenue_zar NUMERIC(12,2) DEFAULT 0,
    leads_generated INTEGER DEFAULT 0,
    content_published INTEGER DEFAULT 0,
    emails_sent INTEGER DEFAULT 0,
    messages_handled INTEGER DEFAULT 0,
    tickets_resolved INTEGER DEFAULT 0,
    success_rate NUMERIC(5,1) DEFAULT 0,
    token_usage INTEGER DEFAULT 0,
    anomalies JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(snapshot_date, agent_id)
);

-- Indexes for dashboard queries
CREATE INDEX IF NOT EXISTS idx_agent_status_agent_id ON agent_status(agent_id);
CREATE INDEX IF NOT EXISTS idx_orchestrator_alerts_status ON orchestrator_alerts(status) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_orchestrator_alerts_severity ON orchestrator_alerts(severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_kpi_snapshots_date ON kpi_snapshots(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_kpi_snapshots_agent ON kpi_snapshots(agent_id, snapshot_date DESC);

-- RLS policies
ALTER TABLE agent_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE orchestrator_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE kpi_snapshots ENABLE ROW LEVEL SECURITY;

-- Admin can read/write all
CREATE POLICY admin_agent_status ON agent_status
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY admin_orchestrator_alerts ON orchestrator_alerts
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY admin_kpi_snapshots ON kpi_snapshots
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- Service role bypass (for n8n webhook writes)
CREATE POLICY service_agent_status ON agent_status
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY service_orchestrator_alerts ON orchestrator_alerts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY service_kpi_snapshots ON kpi_snapshots
    FOR ALL USING (auth.role() = 'service_role');

-- Seed initial agent status records
INSERT INTO agent_status (agent_id, agent_name, department, status, health_score, workflows_monitored) VALUES
    ('agent_marketing', 'Marketing AI Agent', 'Marketing', 'active', 100, 16),
    ('agent_content', 'Content Creation Agent', 'Content', 'active', 100, 3),
    ('agent_finance', 'Finance & Accounting Agent', 'Finance', 'active', 100, 7),
    ('agent_client_relations', 'Client Relations Agent', 'Client Relations', 'active', 100, 0),
    ('agent_support', 'Customer Support Agent', 'Customer Support', 'active', 100, 0),
    ('agent_whatsapp', 'WhatsApp Communication Agent', 'WhatsApp', 'maintenance', 0, 0),
    ('agent_orchestrator', 'Central Orchestrator', 'Orchestrator', 'active', 100, 0)
ON CONFLICT (agent_id) DO NOTHING;
