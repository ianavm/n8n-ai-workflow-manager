-- ============================================
-- AnyVision Media -- Multi-Currency Pricing
-- Migration 011: USD + EUR plan rows for US/EU markets
-- Pricing: Competitive vs US/EU SaaS market (slightly below average)
-- ============================================

-- ============================================
-- 1. ADD STRIPE FIELDS TO SUBSCRIPTIONS
-- ============================================

ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
    ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;

CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe
    ON subscriptions (stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;

-- ============================================
-- 2. ADD STRIPE FIELDS TO INVOICES
-- ============================================

ALTER TABLE invoices
    ADD COLUMN IF NOT EXISTS stripe_payment_intent_id TEXT,
    ADD COLUMN IF NOT EXISTS stripe_invoice_id TEXT;

-- ============================================
-- 3. ADD STRIPE FIELDS TO SUBSCRIPTION_ADDONS
-- ============================================

ALTER TABLE subscription_addons
    ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;

-- ============================================
-- 4. USD PLANS (US Market — slightly below US SaaS average)
-- ============================================
-- US SaaS benchmarks: Entry $99-199, Mid $299-499, Growth $799-1299, Enterprise $2000+
-- Our positioning: slightly below to be competitive as a new entrant

INSERT INTO plans (name, slug, description, price_monthly, price_yearly, currency, sort_order, limits, features) VALUES
(
    'Lite',
    'lite-usd',
    'Automate your first process',
    9900,          -- $99/mo
    99000,         -- $990/yr (save 17%)
    'USD',
    0,
    '{"workflows": 2, "messages": 500, "agents": 0, "leads": 50, "departments": 1}',
    '["2 Workflows", "500 Messages/mo", "50 Leads/mo", "1 Department", "Email Support (72h)", "Basic Dashboard"]'
),
(
    'Starter',
    'starter-usd',
    'Your first AI department',
    34900,         -- $349/mo
    349000,        -- $3,490/yr
    'USD',
    1,
    '{"workflows": 5, "messages": 2000, "agents": 1, "leads": 200, "departments": 2}',
    '["5 Workflows", "2,000 Messages/mo", "1 AI Agent", "200 Leads/mo", "2 Departments", "Email Support (48h)", "Standard Reports", "Client Portal Access"]'
),
(
    'Growth',
    'growth-usd',
    'Scale without scaling headcount',
    79900,         -- $799/mo
    799000,        -- $7,990/yr
    'USD',
    2,
    '{"workflows": 15, "messages": 10000, "agents": 5, "leads": 1000, "departments": 4}',
    '["15 Workflows", "10,000 Messages/mo", "5 AI Agents", "1,000 Leads/mo", "4 Departments", "Priority Support (24h)", "Advanced Reports", "API Access", "Self-Healing Ops", "1h Onboarding Call"]'
),
(
    'Enterprise',
    'enterprise-usd',
    'Your complete AI workforce',
    179900,        -- $1,799/mo
    1799000,       -- $17,990/yr
    'USD',
    3,
    '{"workflows": -1, "messages": 100000, "agents": -1, "leads": -1, "departments": -1}',
    '["Unlimited Workflows", "100,000 Messages/mo", "Unlimited AI Agents", "Unlimited Leads", "All Departments", "Dedicated Support (4h)", "Custom Reports", "API Access", "Custom Integrations", "Quarterly Business Review"]'
);

-- ============================================
-- 5. EUR PLANS (EU Market — slightly below EU SaaS average)
-- ============================================
-- EU SaaS benchmarks: Entry EUR 79-149, Mid EUR 249-449, Growth EUR 699-1199, Enterprise EUR 1800+
-- Our positioning: competitive for an AI automation platform

INSERT INTO plans (name, slug, description, price_monthly, price_yearly, currency, sort_order, limits, features) VALUES
(
    'Lite',
    'lite-eur',
    'Automate your first process',
    8900,          -- EUR 89/mo
    89000,         -- EUR 890/yr (save 17%)
    'EUR',
    0,
    '{"workflows": 2, "messages": 500, "agents": 0, "leads": 50, "departments": 1}',
    '["2 Workflows", "500 Messages/mo", "50 Leads/mo", "1 Department", "Email Support (72h)", "Basic Dashboard"]'
),
(
    'Starter',
    'starter-eur',
    'Your first AI department',
    29900,         -- EUR 299/mo
    299000,        -- EUR 2,990/yr
    'EUR',
    1,
    '{"workflows": 5, "messages": 2000, "agents": 1, "leads": 200, "departments": 2}',
    '["5 Workflows", "2,000 Messages/mo", "1 AI Agent", "200 Leads/mo", "2 Departments", "Email Support (48h)", "Standard Reports", "Client Portal Access"]'
),
(
    'Growth',
    'growth-eur',
    'Scale without scaling headcount',
    69900,         -- EUR 699/mo
    699000,        -- EUR 6,990/yr
    'EUR',
    2,
    '{"workflows": 15, "messages": 10000, "agents": 5, "leads": 1000, "departments": 4}',
    '["15 Workflows", "10,000 Messages/mo", "5 AI Agents", "1,000 Leads/mo", "4 Departments", "Priority Support (24h)", "Advanced Reports", "API Access", "Self-Healing Ops", "1h Onboarding Call"]'
),
(
    'Enterprise',
    'enterprise-eur',
    'Your complete AI workforce',
    159900,        -- EUR 1,599/mo
    1599000,       -- EUR 15,990/yr
    'EUR',
    3,
    '{"workflows": -1, "messages": 100000, "agents": -1, "leads": -1, "departments": -1}',
    '["Unlimited Workflows", "100,000 Messages/mo", "Unlimited AI Agents", "Unlimited Leads", "All Departments", "Dedicated Support (4h)", "Custom Reports", "API Access", "Custom Integrations", "Quarterly Business Review"]'
);

-- ============================================
-- 6. GBP PLANS (UK Market)
-- ============================================

INSERT INTO plans (name, slug, description, price_monthly, price_yearly, currency, sort_order, limits, features) VALUES
(
    'Lite',
    'lite-gbp',
    'Automate your first process',
    7900,          -- GBP 79/mo
    79000,         -- GBP 790/yr
    'GBP',
    0,
    '{"workflows": 2, "messages": 500, "agents": 0, "leads": 50, "departments": 1}',
    '["2 Workflows", "500 Messages/mo", "50 Leads/mo", "1 Department", "Email Support (72h)", "Basic Dashboard"]'
),
(
    'Starter',
    'starter-gbp',
    'Your first AI department',
    27900,         -- GBP 279/mo
    279000,        -- GBP 2,790/yr
    'GBP',
    1,
    '{"workflows": 5, "messages": 2000, "agents": 1, "leads": 200, "departments": 2}',
    '["5 Workflows", "2,000 Messages/mo", "1 AI Agent", "200 Leads/mo", "2 Departments", "Email Support (48h)", "Standard Reports", "Client Portal Access"]'
),
(
    'Growth',
    'growth-gbp',
    'Scale without scaling headcount',
    64900,         -- GBP 649/mo
    649000,        -- GBP 6,490/yr
    'GBP',
    2,
    '{"workflows": 15, "messages": 10000, "agents": 5, "leads": 1000, "departments": 4}',
    '["15 Workflows", "10,000 Messages/mo", "5 AI Agents", "1,000 Leads/mo", "4 Departments", "Priority Support (24h)", "Advanced Reports", "API Access", "Self-Healing Ops", "1h Onboarding Call"]'
),
(
    'Enterprise',
    'enterprise-gbp',
    'Your complete AI workforce',
    149900,        -- GBP 1,499/mo
    1499000,       -- GBP 14,990/yr
    'GBP',
    3,
    '{"workflows": -1, "messages": 100000, "agents": -1, "leads": -1, "departments": -1}',
    '["Unlimited Workflows", "100,000 Messages/mo", "Unlimited AI Agents", "Unlimited Leads", "All Departments", "Dedicated Support (4h)", "Custom Reports", "API Access", "Custom Integrations", "Quarterly Business Review"]'
);

-- ============================================
-- 7. USD/EUR/GBP ADD-ONS
-- ============================================
-- Clone each ZAR add-on with currency-appropriate pricing

-- Helper: Create multi-currency add-on variants
-- USD add-ons (roughly ZAR price / 18, rounded to nearest $X9)
INSERT INTO addons (name, slug, description, price_monthly, category, limits_bonus, features, sort_order) VALUES
('SEO Growth Pack', 'seo-growth-pack-usd', '9 SEO workflows: keyword research, content production, publishing, engagement monitoring, audits, analytics', 21900, 'department', '{"workflows": 9, "messages": 2000, "leads": 500}', '["Keyword Research & SERP Tracking", "Daily Content Production", "9-Platform Publishing", "Engagement Monitoring (30min)", "Weekly SEO Audits", "Analytics & Reporting"]', 1),
('Paid Ads Manager', 'paid-ads-manager-usd', '8 ad workflows: Google + Meta + TikTok strategy, deployment, optimization, reporting with safety caps', 27900, 'department', '{"workflows": 8, "messages": 1000}', '["Google Ads + Meta Ads + TikTok", "AI Strategy Generation", "Automated Creative & Copy", "Real-time Optimization", "Multi-touch Attribution", "Weekly Performance Reports"]', 2),
('WhatsApp Multi-Agent', 'whatsapp-multi-agent-usd', 'Conversational AI: multi-agent system, GPT-4 analysis, auto-routing, appointment booking', 16900, 'department', '{"agents": 3, "messages": 5000}', '["Multi-Agent Conversations", "GPT-4 Analysis & Routing", "Appointment Booking", "Lead Capture", "Contact Label System"]', 3),
('Advanced Analytics', 'advanced-analytics-usd', 'KPI engine, executive reporting, custom dashboards, Google Slides decks', 10900, 'department', '{}', '["KPI Dashboard Engine", "Executive Weekly Reports", "Custom Dashboards", "Trend Analysis"]', 4),
('Self-Healing Ops', 'self-healing-ops-usd', 'Orchestrator + health monitoring + auto-fix + escalation engine', 13900, 'department', '{}', '["24/7 Error Monitoring", "AI Error Classification", "Auto-Recovery", "Health Dashboards", "Escalation Alerts"]', 5),
('Xero Accounting Suite', 'xero-accounting-usd', 'Full 7-workflow accounting: invoicing, collections, reconciliation, month-end, supplier bills', 13900, 'department', '{"workflows": 7, "messages": 1000}', '["Sales Invoicing", "Automated Collections", "Payment Reconciliation", "Month-End Close", "Supplier Bill Processing"]', 6),
('Document Intelligence', 'document-intelligence-usd', 'Email intake, OCR, AI classification, property matching, auto-filing', 10900, 'department', '{"workflows": 4}', '["Email Attachment Capture", "PDF OCR Extraction", "AI Document Classification", "Auto-Filing"]', 7),
('Dedicated Support', 'dedicated-support-usd', '4h response time, Slack channel, monthly review call', 16900, 'support', '{}', '["4h Response Time", "Private Slack Channel", "Monthly Review Call", "Priority Feature Requests"]', 8),
('Extra Message Pack (5K)', 'extra-messages-5k-usd', 'Additional 5,000 messages per month', 7900, 'resources', '{"messages": 5000}', '["5,000 Extra Messages/mo"]', 9),
('Extra Lead Pack (500)', 'extra-leads-500-usd', 'Additional 500 leads per month', 4900, 'resources', '{"leads": 500}', '["500 Extra Leads/mo"]', 10);

-- EUR add-ons
INSERT INTO addons (name, slug, description, price_monthly, category, limits_bonus, features, sort_order) VALUES
('SEO Growth Pack', 'seo-growth-pack-eur', '9 SEO workflows: keyword research, content production, publishing, engagement monitoring, audits, analytics', 19900, 'department', '{"workflows": 9, "messages": 2000, "leads": 500}', '["Keyword Research & SERP Tracking", "Daily Content Production", "9-Platform Publishing", "Engagement Monitoring (30min)", "Weekly SEO Audits", "Analytics & Reporting"]', 1),
('Paid Ads Manager', 'paid-ads-manager-eur', '8 ad workflows: Google + Meta + TikTok strategy, deployment, optimization, reporting with safety caps', 24900, 'department', '{"workflows": 8, "messages": 1000}', '["Google Ads + Meta Ads + TikTok", "AI Strategy Generation", "Automated Creative & Copy", "Real-time Optimization", "Multi-touch Attribution", "Weekly Performance Reports"]', 2),
('WhatsApp Multi-Agent', 'whatsapp-multi-agent-eur', 'Conversational AI: multi-agent system, GPT-4 analysis, auto-routing, appointment booking', 14900, 'department', '{"agents": 3, "messages": 5000}', '["Multi-Agent Conversations", "GPT-4 Analysis & Routing", "Appointment Booking", "Lead Capture", "Contact Label System"]', 3),
('Advanced Analytics', 'advanced-analytics-eur', 'KPI engine, executive reporting, custom dashboards', 9900, 'department', '{}', '["KPI Dashboard Engine", "Executive Weekly Reports", "Custom Dashboards", "Trend Analysis"]', 4),
('Self-Healing Ops', 'self-healing-ops-eur', 'Orchestrator + health monitoring + auto-fix + escalation engine', 12900, 'department', '{}', '["24/7 Error Monitoring", "AI Error Classification", "Auto-Recovery", "Health Dashboards", "Escalation Alerts"]', 5),
('Xero Accounting Suite', 'xero-accounting-eur', 'Full 7-workflow accounting: invoicing, collections, reconciliation, month-end, supplier bills', 12900, 'department', '{"workflows": 7, "messages": 1000}', '["Sales Invoicing", "Automated Collections", "Payment Reconciliation", "Month-End Close", "Supplier Bill Processing"]', 6),
('Document Intelligence', 'document-intelligence-eur', 'Email intake, OCR, AI classification, property matching, auto-filing', 9900, 'department', '{"workflows": 4}', '["Email Attachment Capture", "PDF OCR Extraction", "AI Document Classification", "Auto-Filing"]', 7),
('Dedicated Support', 'dedicated-support-eur', '4h response time, Slack channel, monthly review call', 14900, 'support', '{}', '["4h Response Time", "Private Slack Channel", "Monthly Review Call", "Priority Feature Requests"]', 8),
('Extra Message Pack (5K)', 'extra-messages-5k-eur', 'Additional 5,000 messages per month', 6900, 'resources', '{"messages": 5000}', '["5,000 Extra Messages/mo"]', 9),
('Extra Lead Pack (500)', 'extra-leads-500-eur', 'Additional 500 leads per month', 3900, 'resources', '{"leads": 500}', '["500 Extra Leads/mo"]', 10);
