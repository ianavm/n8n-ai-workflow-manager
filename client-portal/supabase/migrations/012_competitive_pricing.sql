-- ============================================
-- AnyVision Media -- Competitive International Pricing
-- Migration 012: Lower USD/EUR/GBP to undercut market + GBP add-ons
-- Strategy: ~25-30% below typical US/EU SaaS pricing
-- ============================================

-- ============================================
-- 1. USD PLAN PRICE ADJUSTMENTS
-- ============================================
-- Old: $99 / $349 / $799 / $1,799
-- New: $79 / $249 / $599 / $1,299

UPDATE plans SET price_monthly = 7900,   price_yearly = 79000   WHERE slug = 'lite-usd';
UPDATE plans SET price_monthly = 24900,  price_yearly = 249000  WHERE slug = 'starter-usd';
UPDATE plans SET price_monthly = 59900,  price_yearly = 599000  WHERE slug = 'growth-usd';
UPDATE plans SET price_monthly = 129900, price_yearly = 1299000 WHERE slug = 'enterprise-usd';

-- ============================================
-- 2. EUR PLAN PRICE ADJUSTMENTS
-- ============================================
-- Old: EUR 89 / EUR 299 / EUR 699 / EUR 1,599
-- New: EUR 69 / EUR 229 / EUR 549 / EUR 1,199

UPDATE plans SET price_monthly = 6900,   price_yearly = 69000   WHERE slug = 'lite-eur';
UPDATE plans SET price_monthly = 22900,  price_yearly = 229000  WHERE slug = 'starter-eur';
UPDATE plans SET price_monthly = 54900,  price_yearly = 549000  WHERE slug = 'growth-eur';
UPDATE plans SET price_monthly = 119900, price_yearly = 1199000 WHERE slug = 'enterprise-eur';

-- ============================================
-- 3. GBP PLAN PRICE ADJUSTMENTS
-- ============================================
-- Old: GBP 79 / GBP 279 / GBP 649 / GBP 1,499
-- New: GBP 59 / GBP 199 / GBP 479 / GBP 999

UPDATE plans SET price_monthly = 5900,  price_yearly = 59000   WHERE slug = 'lite-gbp';
UPDATE plans SET price_monthly = 19900, price_yearly = 199000  WHERE slug = 'starter-gbp';
UPDATE plans SET price_monthly = 47900, price_yearly = 479000  WHERE slug = 'growth-gbp';
UPDATE plans SET price_monthly = 99900, price_yearly = 999000  WHERE slug = 'enterprise-gbp';

-- ============================================
-- 4. USD ADD-ON PRICE ADJUSTMENTS (~25% reduction)
-- ============================================
-- Competitive positioning to match lowered plan prices

UPDATE addons SET price_monthly = 16900 WHERE slug = 'seo-growth-pack-usd';          -- was $219 -> $169
UPDATE addons SET price_monthly = 21900 WHERE slug = 'paid-ads-manager-usd';          -- was $279 -> $219
UPDATE addons SET price_monthly = 12900 WHERE slug = 'whatsapp-multi-agent-usd';      -- was $169 -> $129
UPDATE addons SET price_monthly = 7900  WHERE slug = 'advanced-analytics-usd';        -- was $109 -> $79
UPDATE addons SET price_monthly = 9900  WHERE slug = 'self-healing-ops-usd';          -- was $139 -> $99
UPDATE addons SET price_monthly = 9900  WHERE slug = 'xero-accounting-usd';           -- was $139 -> $99
UPDATE addons SET price_monthly = 7900  WHERE slug = 'document-intelligence-usd';     -- was $109 -> $79
UPDATE addons SET price_monthly = 12900 WHERE slug = 'dedicated-support-usd';         -- was $169 -> $129
UPDATE addons SET price_monthly = 5900  WHERE slug = 'extra-messages-5k-usd';         -- was $79  -> $59
UPDATE addons SET price_monthly = 3500  WHERE slug = 'extra-leads-500-usd';           -- was $49  -> $35

-- ============================================
-- 5. EUR ADD-ON PRICE ADJUSTMENTS (~25% reduction)
-- ============================================

UPDATE addons SET price_monthly = 14900 WHERE slug = 'seo-growth-pack-eur';           -- was EUR 199 -> EUR 149
UPDATE addons SET price_monthly = 19900 WHERE slug = 'paid-ads-manager-eur';          -- was EUR 249 -> EUR 199
UPDATE addons SET price_monthly = 11900 WHERE slug = 'whatsapp-multi-agent-eur';      -- was EUR 149 -> EUR 119
UPDATE addons SET price_monthly = 6900  WHERE slug = 'advanced-analytics-eur';        -- was EUR 99  -> EUR 69
UPDATE addons SET price_monthly = 8900  WHERE slug = 'self-healing-ops-eur';          -- was EUR 129 -> EUR 89
UPDATE addons SET price_monthly = 8900  WHERE slug = 'xero-accounting-eur';           -- was EUR 129 -> EUR 89
UPDATE addons SET price_monthly = 6900  WHERE slug = 'document-intelligence-eur';     -- was EUR 99  -> EUR 69
UPDATE addons SET price_monthly = 11900 WHERE slug = 'dedicated-support-eur';         -- was EUR 149 -> EUR 119
UPDATE addons SET price_monthly = 4900  WHERE slug = 'extra-messages-5k-eur';         -- was EUR 69  -> EUR 49
UPDATE addons SET price_monthly = 2900  WHERE slug = 'extra-leads-500-eur';           -- was EUR 39  -> EUR 29

-- ============================================
-- 6. GBP ADD-ONS (NEW — missing from migration 011)
-- ============================================
-- Priced at ~75% of USD prices (reflects GBP purchasing power)

INSERT INTO addons (name, slug, description, price_monthly, category, limits_bonus, features, sort_order) VALUES
('SEO Growth Pack', 'seo-growth-pack-gbp', '9 SEO workflows: keyword research, content production, publishing, engagement monitoring, audits, analytics', 15900, 'department', '{"workflows": 9, "messages": 2000, "leads": 500}', '["Keyword Research & SERP Tracking", "Daily Content Production", "9-Platform Publishing", "Engagement Monitoring (30min)", "Weekly SEO Audits", "Analytics & Reporting"]', 1),
('Paid Ads Manager', 'paid-ads-manager-gbp', '8 ad workflows: Google + Meta + TikTok strategy, deployment, optimization, reporting with safety caps', 19900, 'department', '{"workflows": 8, "messages": 1000}', '["Google Ads + Meta Ads + TikTok", "AI Strategy Generation", "Automated Creative & Copy", "Real-time Optimization", "Multi-touch Attribution", "Weekly Performance Reports"]', 2),
('WhatsApp Multi-Agent', 'whatsapp-multi-agent-gbp', 'Conversational AI: multi-agent system, GPT-4 analysis, auto-routing, appointment booking', 11900, 'department', '{"agents": 3, "messages": 5000}', '["Multi-Agent Conversations", "GPT-4 Analysis & Routing", "Appointment Booking", "Lead Capture", "Contact Label System"]', 3),
('Advanced Analytics', 'advanced-analytics-gbp', 'KPI engine, executive reporting, custom dashboards, Google Slides decks', 7900, 'department', '{}', '["KPI Dashboard Engine", "Executive Weekly Reports", "Custom Dashboards", "Trend Analysis"]', 4),
('Self-Healing Ops', 'self-healing-ops-gbp', 'Orchestrator + health monitoring + auto-fix + escalation engine', 9900, 'department', '{}', '["24/7 Error Monitoring", "AI Error Classification", "Auto-Recovery", "Health Dashboards", "Escalation Alerts"]', 5),
('Xero Accounting Suite', 'xero-accounting-gbp', 'Full 7-workflow accounting: invoicing, collections, reconciliation, month-end, supplier bills', 9900, 'department', '{"workflows": 7, "messages": 1000}', '["Sales Invoicing", "Automated Collections", "Payment Reconciliation", "Month-End Close", "Supplier Bill Processing"]', 6),
('Document Intelligence', 'document-intelligence-gbp', 'Email intake, OCR, AI classification, property matching, auto-filing', 7900, 'department', '{"workflows": 4}', '["Email Attachment Capture", "PDF OCR Extraction", "AI Document Classification", "Auto-Filing"]', 7),
('Dedicated Support', 'dedicated-support-gbp', '4h response time, Slack channel, monthly review call', 11900, 'support', '{}', '["4h Response Time", "Private Slack Channel", "Monthly Review Call", "Priority Feature Requests"]', 8),
('Extra Message Pack (5K)', 'extra-messages-5k-gbp', 'Additional 5,000 messages per month', 5900, 'resources', '{"messages": 5000}', '["5,000 Extra Messages/mo"]', 9),
('Extra Lead Pack (500)', 'extra-leads-500-gbp', 'Additional 500 leads per month', 3500, 'resources', '{"leads": 500}', '["500 Extra Leads/mo"]', 10);
