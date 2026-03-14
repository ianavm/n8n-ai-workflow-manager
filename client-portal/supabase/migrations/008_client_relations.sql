-- Migration 008: Client Relations Tables
-- Adds client health scores, interaction log, and renewal pipeline
-- Used by OPT-03 Churn Predictor and Client Relations Agent

-- client_health_scores: per-client health scoring
CREATE TABLE IF NOT EXISTS client_health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    score_date DATE NOT NULL,
    usage_score INTEGER DEFAULT 0 CHECK (usage_score BETWEEN 0 AND 100),
    payment_score INTEGER DEFAULT 0 CHECK (payment_score BETWEEN 0 AND 100),
    engagement_score INTEGER DEFAULT 0 CHECK (engagement_score BETWEEN 0 AND 100),
    support_score INTEGER DEFAULT 0 CHECK (support_score BETWEEN 0 AND 100),
    composite_score INTEGER DEFAULT 0 CHECK (composite_score BETWEEN 0 AND 100),
    risk_level TEXT DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, score_date)
);

-- client_interactions: CRM interaction log
CREATE TABLE IF NOT EXISTS client_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    interaction_type TEXT NOT NULL CHECK (interaction_type IN (
        'email', 'call', 'meeting', 'support_ticket',
        'portal_login', 'payment', 'renewal', 'onboarding'
    )),
    direction TEXT DEFAULT 'outbound' CHECK (direction IN ('inbound', 'outbound', 'system')),
    subject TEXT,
    summary TEXT,
    sentiment TEXT CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- renewal_pipeline: subscription renewal tracking
CREATE TABLE IF NOT EXISTS renewal_pipeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    current_plan TEXT,
    monthly_value DECIMAL(10,2),
    renewal_date DATE NOT NULL,
    days_until_renewal INTEGER,
    health_score INTEGER,
    risk_level TEXT DEFAULT 'low',
    status TEXT DEFAULT 'upcoming' CHECK (status IN (
        'upcoming', 'in_progress', 'renewed', 'churned', 'downgraded'
    )),
    last_contact_date DATE,
    next_action TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_health_scores_client
    ON client_health_scores(client_id, score_date DESC);
CREATE INDEX IF NOT EXISTS idx_health_scores_date
    ON client_health_scores(score_date DESC);
CREATE INDEX IF NOT EXISTS idx_health_scores_risk
    ON client_health_scores(risk_level) WHERE risk_level != 'low';

CREATE INDEX IF NOT EXISTS idx_interactions_client
    ON client_interactions(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_type
    ON client_interactions(interaction_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_renewal_client
    ON renewal_pipeline(client_id);
CREATE INDEX IF NOT EXISTS idx_renewal_date
    ON renewal_pipeline(renewal_date);
CREATE INDEX IF NOT EXISTS idx_renewal_status
    ON renewal_pipeline(status) WHERE status IN ('upcoming', 'in_progress');

-- Enable Row Level Security
ALTER TABLE client_health_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE renewal_pipeline ENABLE ROW LEVEL SECURITY;

-- Admin full access
CREATE POLICY admin_health_scores ON client_health_scores
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY admin_interactions ON client_interactions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY admin_renewal_pipeline ON renewal_pipeline
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- Service role bypass (for n8n webhook writes)
CREATE POLICY service_health_scores ON client_health_scores
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY service_interactions ON client_interactions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY service_renewal_pipeline ON renewal_pipeline
    FOR ALL USING (auth.role() = 'service_role');

-- Clients can read their own health scores and interactions
CREATE POLICY client_own_health_scores ON client_health_scores
    FOR SELECT USING (
        client_id IN (
            SELECT id FROM clients WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY client_own_interactions ON client_interactions
    FOR SELECT USING (
        client_id IN (
            SELECT id FROM clients WHERE auth_user_id = auth.uid()
        )
    );
