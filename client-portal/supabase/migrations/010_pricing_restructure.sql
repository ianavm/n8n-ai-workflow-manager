-- ============================================
-- AnyVision Media -- Pricing & Monetization Restructure
-- Migration 010: Lite tier, add-ons, overages, setup fees
-- ============================================

-- ============================================
-- 1. ADD LITE PLAN (low-friction entry tier)
-- ============================================

INSERT INTO plans (name, slug, description, price_monthly, price_yearly, sort_order, limits, features)
VALUES (
    'Lite',
    'lite',
    'Automate your first process',
    199900,        -- R1,999.00
    1999000,       -- R19,990.00 (2 months free)
    0,
    '{"workflows": 2, "messages": 500, "agents": 0, "leads": 50, "departments": 1}',
    '["2 Workflows", "500 Messages/mo", "50 Leads/mo", "1 Department", "Email Support (72h)", "Basic Dashboard"]'
);

-- ============================================
-- 2. UPDATE EXISTING PLANS (add department limits + value messaging)
-- ============================================

UPDATE plans SET
    limits = '{"workflows": 5, "messages": 2000, "agents": 1, "leads": 200, "departments": 2}',
    features = '["5 Workflows", "2,000 Messages/mo", "1 AI Agent", "200 Leads/mo", "2 Departments", "Email Support (48h)", "Standard Reports", "Client Portal Access"]',
    description = 'Your first AI department'
WHERE slug = 'starter';

UPDATE plans SET
    limits = '{"workflows": 15, "messages": 10000, "agents": 5, "leads": 1000, "departments": 4}',
    features = '["15 Workflows", "10,000 Messages/mo", "5 AI Agents", "1,000 Leads/mo", "4 Departments", "Priority Support (24h)", "Advanced Reports", "API Access", "Self-Healing Ops", "1h Onboarding Call"]',
    description = 'Scale without scaling headcount'
WHERE slug = 'growth';

UPDATE plans SET
    limits = '{"workflows": -1, "messages": 100000, "agents": -1, "leads": -1, "departments": -1}',
    features = '["Unlimited Workflows", "100,000 Messages/mo", "Unlimited AI Agents", "Unlimited Leads", "All Departments", "Dedicated Support (4h)", "Custom Reports", "API Access", "Custom Integrations", "Quarterly Business Review"]',
    description = 'Your complete AI workforce'
WHERE slug = 'enterprise';

-- ============================================
-- 3. ADD-ONS TABLE (modular upsell engine)
-- ============================================

CREATE TABLE addons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    price_monthly INTEGER NOT NULL,           -- cents
    category TEXT NOT NULL DEFAULT 'department'
        CHECK (category IN ('department', 'resources', 'support')),
    limits_bonus JSONB NOT NULL DEFAULT '{}', -- merged into plan limits when active
    features JSONB NOT NULL DEFAULT '[]',     -- display features list
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. SUBSCRIPTION ADD-ONS (join table)
CREATE TABLE subscription_addons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    addon_id UUID NOT NULL REFERENCES addons(id),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'canceled')),
    payfast_token TEXT,
    payfast_subscription_id TEXT,
    activated_at TIMESTAMPTZ DEFAULT now(),
    deactivated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sub_addons_subscription ON subscription_addons (subscription_id);
CREATE INDEX idx_sub_addons_addon ON subscription_addons (addon_id);
CREATE INDEX idx_sub_addons_status ON subscription_addons (status);

-- Only one active instance of each add-on per subscription
CREATE UNIQUE INDEX idx_sub_addons_unique_active
    ON subscription_addons (subscription_id, addon_id)
    WHERE status = 'active';

-- ============================================
-- 5. EXTEND USAGE RECORDS (overage tracking)
-- ============================================

ALTER TABLE usage_records
    ADD COLUMN IF NOT EXISTS overage_messages INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS overage_leads INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS overage_amount_cents INTEGER DEFAULT 0;

-- ============================================
-- 6. SETUP FEES TABLE (one-time payments)
-- ============================================

CREATE TABLE setup_fees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    service_type TEXT NOT NULL,                -- 'guided_onboarding', 'department_setup', 'custom_workflow', 'data_migration', 'custom_integration', 'full_setup'
    description TEXT,
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'paid', 'waived', 'refunded')),
    payfast_payment_id TEXT,
    invoice_id UUID REFERENCES invoices(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    paid_at TIMESTAMPTZ
);

CREATE INDEX idx_setup_fees_client ON setup_fees (client_id);
CREATE INDEX idx_setup_fees_status ON setup_fees (status);

-- ============================================
-- 7. ROW-LEVEL SECURITY
-- ============================================

ALTER TABLE addons ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_addons ENABLE ROW LEVEL SECURITY;
ALTER TABLE setup_fees ENABLE ROW LEVEL SECURITY;

-- Add-ons: everyone can read (public catalog)
CREATE POLICY "addons_public_read" ON addons
    FOR SELECT USING (true);

-- Subscription add-ons: clients see own, admins see all
CREATE POLICY "sub_addons_own" ON subscription_addons
    FOR SELECT USING (
        subscription_id IN (
            SELECT id FROM subscriptions
            WHERE client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
        )
    );

CREATE POLICY "admins_all_sub_addons" ON subscription_addons
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- Setup fees: clients see own, admins see all
CREATE POLICY "setup_fees_own" ON setup_fees
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_all_setup_fees" ON setup_fees
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- ============================================
-- 8. HELPER FUNCTIONS
-- ============================================

-- Get active add-ons for a subscription (with addon details)
CREATE OR REPLACE FUNCTION get_subscription_addons(p_subscription_id UUID)
RETURNS TABLE (
    addon_id UUID,
    addon_name TEXT,
    addon_slug TEXT,
    addon_description TEXT,
    price_monthly INTEGER,
    category TEXT,
    limits_bonus JSONB,
    features JSONB,
    activated_at TIMESTAMPTZ
) AS $$
    SELECT
        a.id,
        a.name,
        a.slug,
        a.description,
        a.price_monthly,
        a.category,
        a.limits_bonus,
        a.features,
        sa.activated_at
    FROM subscription_addons sa
    JOIN addons a ON a.id = sa.addon_id
    WHERE sa.subscription_id = p_subscription_id
      AND sa.status = 'active'
      AND a.is_active = true
    ORDER BY a.sort_order;
$$ LANGUAGE sql SECURITY DEFINER;

-- Get merged limits (plan + active add-ons) for a client
CREATE OR REPLACE FUNCTION get_client_merged_limits(p_client_id UUID)
RETURNS JSONB AS $$
DECLARE
    base_limits JSONB;
    addon_bonus JSONB;
    merged JSONB;
    sub_id UUID;
BEGIN
    -- Get base plan limits
    SELECT p.limits, s.id INTO base_limits, sub_id
    FROM subscriptions s
    JOIN plans p ON p.id = s.plan_id
    WHERE s.client_id = p_client_id
      AND s.status IN ('active', 'trialing', 'past_due')
    ORDER BY s.created_at DESC
    LIMIT 1;

    IF base_limits IS NULL THEN
        RETURN '{}'::JSONB;
    END IF;

    merged := base_limits;

    -- Merge each active add-on's limits_bonus
    FOR addon_bonus IN
        SELECT a.limits_bonus
        FROM subscription_addons sa
        JOIN addons a ON a.id = sa.addon_id
        WHERE sa.subscription_id = sub_id
          AND sa.status = 'active'
          AND a.is_active = true
    LOOP
        -- For each key in the bonus, add to merged (unless -1 = unlimited)
        SELECT jsonb_object_agg(
            key,
            CASE
                WHEN (merged->>key)::int = -1 THEN -1
                WHEN (addon_bonus->>key) IS NOT NULL
                    THEN (COALESCE((merged->>key)::int, 0) + (addon_bonus->>key)::int)
                ELSE COALESCE((merged->>key)::int, 0)
            END
        ) INTO merged
        FROM jsonb_each_text(merged);
    END LOOP;

    RETURN merged;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- 9. SEED ADD-ONS
-- ============================================

INSERT INTO addons (name, slug, description, price_monthly, category, limits_bonus, features, sort_order) VALUES
(
    'SEO Growth Pack',
    'seo-growth-pack',
    '9 SEO workflows: keyword research, content production, publishing, engagement monitoring, audits, analytics',
    399900,
    'department',
    '{"workflows": 9, "messages": 2000, "leads": 500}',
    '["Keyword Research & SERP Tracking", "Daily Content Production", "9-Platform Publishing", "Engagement Monitoring (30min)", "Weekly SEO Audits", "Analytics & Reporting"]',
    1
),
(
    'Paid Ads Manager',
    'paid-ads-manager',
    '8 ad workflows: Google + Meta + TikTok strategy, deployment, optimization, reporting with safety caps',
    499900,
    'department',
    '{"workflows": 8, "messages": 1000}',
    '["Google Ads + Meta Ads + TikTok", "AI Strategy Generation", "Automated Creative & Copy", "Real-time Optimization", "Safety Caps (R2K/day)", "Multi-touch Attribution", "Weekly Performance Reports"]',
    2
),
(
    'WhatsApp Multi-Agent',
    'whatsapp-multi-agent',
    'Conversational AI: multi-agent system, GPT-4 analysis, auto-routing, appointment booking',
    299900,
    'department',
    '{"agents": 3, "messages": 5000}',
    '["Multi-Agent Conversations", "GPT-4 Analysis & Routing", "Appointment Booking", "Lead Capture", "Contact Label System", "24h Conversation Window"]',
    3
),
(
    'Advanced Analytics',
    'advanced-analytics',
    'KPI engine, executive reporting, custom dashboards, Google Slides decks',
    199900,
    'department',
    '{}',
    '["KPI Dashboard Engine", "Executive Weekly Reports", "Custom Dashboards", "Google Slides Decks", "Trend Analysis", "Cross-Department Insights"]',
    4
),
(
    'Self-Healing Ops',
    'self-healing-ops',
    'Orchestrator + health monitoring + auto-fix + escalation engine for 24/7 reliability',
    249900,
    'department',
    '{}',
    '["24/7 Error Monitoring", "AI Error Classification", "Auto-Recovery (retry, restart)", "Health Dashboards", "Escalation Alerts", "Cost-Optimized (regex-first)"]',
    5
),
(
    'Xero Accounting Suite',
    'xero-accounting',
    'Full 7-workflow accounting: invoicing, collections, reconciliation, month-end, supplier bills',
    249900,
    'department',
    '{"workflows": 7, "messages": 1000}',
    '["Sales Invoicing -> Xero", "Automated Collections (3/7/14 day)", "Payment Reconciliation", "Supplier Bill Processing", "Month-End Close", "15% VAT Handling", "Auto-approve < R10K"]',
    6
),
(
    'Document Intelligence',
    'document-intelligence',
    'Email intake, OCR, AI classification, property matching, auto-filing to Google Drive',
    199900,
    'department',
    '{"workflows": 4}',
    '["Email Attachment Capture", "PDF OCR Extraction", "AI Document Classification", "Property Matching", "Auto-Filing (Google Drive)", "Review Queue for Low-Confidence"]',
    7
),
(
    'Dedicated Support',
    'dedicated-support',
    '4h response time, Slack channel, monthly review call with dedicated account manager',
    299900,
    'support',
    '{}',
    '["4h Response Time", "Private Slack Channel", "Monthly Review Call", "Dedicated Account Manager", "Priority Feature Requests"]',
    8
),
(
    'Extra Message Pack (5K)',
    'extra-messages-5k',
    'Additional 5,000 messages per month for high-volume automation',
    149900,
    'resources',
    '{"messages": 5000}',
    '["5,000 Extra Messages/mo", "WhatsApp + Email + SMS", "Rolls Over Monthly"]',
    9
),
(
    'Extra Lead Pack (500)',
    'extra-leads-500',
    'Additional 500 leads per month for scaling lead generation',
    99900,
    'resources',
    '{"leads": 500}',
    '["500 Extra Leads/mo", "Lead Scraper + SEO Leads", "Full Scoring & Enrichment"]',
    10
);
