-- ============================================
-- AnyVision Media — Billing & Subscription Schema
-- Migration 006: Payment gate for SaaS clients
-- Processor: PayFast (ZAR, South Africa)
-- ============================================

-- 1. PLANS (product catalog)
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    price_monthly INTEGER NOT NULL,         -- cents (R5,999 = 599900)
    price_yearly INTEGER NOT NULL,          -- cents (R59,990 = 5999000)
    currency TEXT NOT NULL DEFAULT 'ZAR',
    limits JSONB NOT NULL DEFAULT '{}',     -- {"workflows": 3, "messages": 1000, "agents": 1, "leads": 100}
    features JSONB NOT NULL DEFAULT '[]',   -- ["3 Workflows", "1,000 Messages/mo", ...]
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. SUBSCRIPTIONS (one active per client)
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES plans(id),
    payfast_token TEXT,                     -- PayFast subscription token for recurring
    payfast_subscription_id TEXT,           -- PayFast subscription reference
    status TEXT NOT NULL DEFAULT 'trialing' CHECK (status IN (
        'trialing', 'active', 'past_due', 'canceled', 'unpaid', 'paused'
    )),
    billing_interval TEXT NOT NULL DEFAULT 'monthly' CHECK (billing_interval IN ('monthly', 'yearly')),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    trial_start TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_subscriptions_client ON subscriptions (client_id);
CREATE INDEX idx_subscriptions_status ON subscriptions (status);
CREATE INDEX idx_subscriptions_payfast ON subscriptions (payfast_subscription_id);

-- Only one active/trialing subscription per client
CREATE UNIQUE INDEX idx_subscriptions_active ON subscriptions (client_id)
    WHERE status IN ('active', 'trialing', 'past_due');

-- 3. INVOICES (payment history)
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    payfast_payment_id TEXT UNIQUE,         -- PayFast m_payment_id
    invoice_number TEXT,                    -- e.g. 'AVM-2026-0001'
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'open', 'paid', 'void', 'uncollectible'
    )),
    amount_due INTEGER NOT NULL,            -- cents (excl. VAT)
    amount_paid INTEGER DEFAULT 0,          -- cents
    vat_amount INTEGER DEFAULT 0,           -- 15% VAT in cents
    currency TEXT NOT NULL DEFAULT 'ZAR',
    description TEXT,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_invoices_client ON invoices (client_id, created_at DESC);
CREATE INDEX idx_invoices_payfast ON invoices (payfast_payment_id);

-- 4. PAYMENT METHODS (display only — sensitive data stays in PayFast)
CREATE TABLE payment_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    type TEXT NOT NULL DEFAULT 'card',      -- 'card', 'eft'
    card_brand TEXT,                        -- 'visa', 'mastercard'
    card_last4 TEXT,                        -- '4242'
    card_exp_month INTEGER,
    card_exp_year INTEGER,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_payment_methods_client ON payment_methods (client_id);

-- 5. USAGE RECORDS (monthly rollups for feature gating)
CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,             -- First of month
    period_end DATE NOT NULL,               -- Last of month
    messages_used INTEGER DEFAULT 0,
    leads_used INTEGER DEFAULT 0,
    workflows_count INTEGER DEFAULT 0,
    agents_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (client_id, period_start)
);

CREATE INDEX idx_usage_client_period ON usage_records (client_id, period_start DESC);

-- ============================================
-- ROW-LEVEL SECURITY
-- ============================================

ALTER TABLE plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_methods ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY;

-- Plans: everyone can read (public catalog)
CREATE POLICY "plans_public_read" ON plans
    FOR SELECT USING (true);

-- Subscriptions: clients see own, admins see all
CREATE POLICY "subscriptions_own" ON subscriptions
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_subscriptions" ON subscriptions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- Invoices: clients see own, admins see all
CREATE POLICY "invoices_own" ON invoices
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_invoices" ON invoices
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- Payment methods: clients see own, admins see all
CREATE POLICY "payment_methods_own" ON payment_methods
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_payment_methods" ON payment_methods
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- Usage records: clients see own, admins see all
CREATE POLICY "usage_own" ON usage_records
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_usage" ON usage_records
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Get current active subscription for a client (with plan details)
CREATE OR REPLACE FUNCTION get_client_subscription(p_client_id UUID)
RETURNS TABLE (
    subscription_id UUID,
    plan_name TEXT,
    plan_slug TEXT,
    plan_description TEXT,
    status TEXT,
    billing_interval TEXT,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN,
    limits JSONB,
    features JSONB,
    price_monthly INTEGER,
    price_yearly INTEGER
) AS $$
    SELECT
        s.id,
        p.name,
        p.slug,
        p.description,
        s.status,
        s.billing_interval,
        s.current_period_start,
        s.current_period_end,
        s.trial_end,
        s.cancel_at_period_end,
        p.limits,
        p.features,
        p.price_monthly,
        p.price_yearly
    FROM subscriptions s
    JOIN plans p ON p.id = s.plan_id
    WHERE s.client_id = p_client_id
      AND s.status IN ('active', 'trialing', 'past_due')
    ORDER BY s.created_at DESC
    LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER;

-- Get current month usage for a client
CREATE OR REPLACE FUNCTION get_client_usage(p_client_id UUID)
RETURNS TABLE (
    messages_used INTEGER,
    leads_used INTEGER,
    workflows_count INTEGER,
    agents_count INTEGER
) AS $$
    SELECT
        COALESCE(u.messages_used, 0),
        COALESCE(u.leads_used, 0),
        COALESCE(u.workflows_count, 0),
        COALESCE(u.agents_count, 0)
    FROM usage_records u
    WHERE u.client_id = p_client_id
      AND u.period_start = date_trunc('month', now())::date
    LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER;

-- Generate next invoice number
CREATE OR REPLACE FUNCTION generate_invoice_number()
RETURNS TEXT AS $$
DECLARE
    next_num INTEGER;
    year_str TEXT;
BEGIN
    year_str := to_char(now(), 'YYYY');
    SELECT COALESCE(MAX(
        CAST(SUBSTRING(invoice_number FROM 'AVM-\d{4}-(\d+)') AS INTEGER)
    ), 0) + 1
    INTO next_num
    FROM invoices
    WHERE invoice_number LIKE 'AVM-' || year_str || '-%';

    RETURN 'AVM-' || year_str || '-' || LPAD(next_num::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- SEED DATA: Pricing Plans
-- ============================================

INSERT INTO plans (name, slug, description, price_monthly, price_yearly, sort_order, limits, features) VALUES
(
    'Starter',
    'starter',
    'Perfect for small businesses getting started with AI automation',
    599900,     -- R5,999.00
    5999000,    -- R59,990.00 (2 months free)
    1,
    '{"workflows": 3, "messages": 1000, "agents": 1, "leads": 100}',
    '["3 Workflows", "1,000 Messages/mo", "1 AI Agent", "100 Leads/mo", "Email Support (48h)", "Basic Reports"]'
),
(
    'Growth',
    'growth',
    'For growing businesses scaling their operations',
    1499900,    -- R14,999.00
    14999000,   -- R149,990.00 (2 months free)
    2,
    '{"workflows": 10, "messages": 10000, "agents": 3, "leads": 1000}',
    '["10 Workflows", "10,000 Messages/mo", "3 AI Agents", "1,000 Leads/mo", "Priority Support (24h)", "Advanced Reports", "API Access"]'
),
(
    'Enterprise',
    'enterprise',
    'Full-scale AI transformation for established businesses',
    2999900,    -- R29,999.00
    29999000,   -- R299,990.00 (2 months free)
    3,
    '{"workflows": -1, "messages": 100000, "agents": 10, "leads": -1}',
    '["Unlimited Workflows", "100,000 Messages/mo", "10 AI Agents", "Unlimited Leads", "Dedicated Support (4h)", "Custom Reports", "API Access", "Custom Integrations"]'
);
