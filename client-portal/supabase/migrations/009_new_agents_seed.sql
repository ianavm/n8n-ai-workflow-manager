-- Migration 009: Seed all 25 agents into agent_status table
-- Actual DB schema: agent_id, agent_name, department, status, health_score, workflow_ids (jsonb), error_count
-- Status check constraint: active, degraded, down, inactive

INSERT INTO agent_status (agent_id, agent_name, department, status, health_score, workflow_ids, error_count) VALUES
    -- Tier 1: Executive
    ('agent_orchestrator', 'Central Orchestrator', 'Orchestrator', 'active', 100, '["ORCH-01","ORCH-02","ORCH-03","ORCH-04"]'::jsonb, 0),
    ('agent_chief', 'Executive Intelligence Agent', 'Executive', 'active', 100, '["ORCH-03","ORCH-04","INTEL-02"]'::jsonb, 0),

    -- Tier 2: Revenue & Growth
    ('agent_finance', 'Finance & Accounting Agent', 'Finance', 'active', 100, '["ACC-WF01","ACC-WF02","ACC-WF03","ACC-WF04","ACC-WF05","ACC-WF06","ACC-WF07","FIN-08","FIN-09"]'::jsonb, 0),
    ('agent_marketing', 'Marketing AI Agent', 'Marketing', 'active', 100, '["MKT-01","MKT-02","MKT-03","MKT-04","MKT-05","MKT-06"]'::jsonb, 0),
    ('agent_growth_organic', 'Content & SEO Agent', 'Marketing', 'active', 100, '["SEO-WF05","SEO-WF06","SEO-WF07","SEO-WF08","SEO-WF09","SEO-WF10","SEO-WF11","SEO-SCORE"]'::jsonb, 0),
    ('agent_growth_paid', 'Advertising Agent', 'Marketing', 'active', 100, '["ADS-01","ADS-02","ADS-03","ADS-04","ADS-05","ADS-06","ADS-07","ADS-08"]'::jsonb, 0),
    ('agent_pipeline', 'Lead Pipeline Agent', 'Sales', 'active', 100, '["BRIDGE-01","BRIDGE-02","BRIDGE-03","BRIDGE-04"]'::jsonb, 0),

    -- Tier 3: Client-Facing
    ('agent_client_success', 'Client Relations Agent', 'Client Relations', 'active', 100, '["CR-01","CR-02","CR-03","CR-04"]'::jsonb, 0),
    ('agent_support', 'Customer Support Agent', 'Support', 'active', 100, '["SUP-01","SUP-02","SUP-03","SUP-04"]'::jsonb, 0),
    ('agent_whatsapp', 'WhatsApp Communication Agent', 'WhatsApp', 'inactive', 0, '["WA-01","WA-02","WA-03"]'::jsonb, 0),

    -- Tier 4: Infrastructure
    ('agent_sentinel', 'Systems Health Agent', 'DevOps', 'active', 100, '["OPT-01","OPT-02","OPT-03"]'::jsonb, 0),
    ('agent_engineer', 'Platform Engineering Agent', 'Engineering', 'active', 100, '[]'::jsonb, 0),
    ('agent_devops', 'DevOps Coordinator', 'DevOps', 'active', 100, '["DEVOPS-01","DEVOPS-02","DEVOPS-03"]'::jsonb, 0),

    -- Tier 5: Intelligence & Analysis
    ('agent_content', 'Content Creation Agent', 'Content', 'active', 100, '["CONTENT-01","CONTENT-02"]'::jsonb, 0),
    ('agent_intelligence', 'Analytics & Optimization', 'Intelligence', 'active', 100, '["INTEL-01","INTEL-02","INTEL-03"]'::jsonb, 0),
    ('agent_market_intel', 'Market Intelligence Agent', 'Intelligence', 'active', 100, '["INTEL-04","INTEL-05","INTEL-06"]'::jsonb, 0),
    ('agent_knowledge_mgr', 'Knowledge Management Agent', 'Intelligence', 'active', 100, '["KM-01","KM-02","KM-03"]'::jsonb, 0),
    ('agent_data_analyst', 'Data Intelligence Agent', 'Intelligence', 'active', 100, '["DATA-01","DATA-02","DATA-03"]'::jsonb, 0),

    -- Tier 6: Quality & Governance
    ('agent_qa', 'Quality Assurance Agent', 'Quality', 'active', 100, '["QA-01","QA-02","QA-03"]'::jsonb, 0),
    ('agent_brand_guardian', 'Brand Consistency Agent', 'Quality', 'active', 100, '["BRAND-01","BRAND-02","BRAND-03"]'::jsonb, 0),
    ('agent_compliance', 'Compliance Auditor Agent', 'Governance', 'active', 100, '["COMPLY-01","COMPLY-02","COMPLY-03"]'::jsonb, 0),

    -- Tier 7: Specialist / Utility
    ('agent_financial_intel', 'Financial Intelligence Agent', 'Finance', 'active', 100, '["FINTEL-01","FINTEL-02","FINTEL-03","FINTEL-04"]'::jsonb, 0),
    ('agent_crm_sync', 'CRM Unification Agent', 'Operations', 'active', 100, '["CRM-01","CRM-02","CRM-03"]'::jsonb, 0),
    ('agent_booking', 'Booking Assistant Agent', 'Operations', 'active', 100, '["BOOK-01","BOOK-02","BOOK-03"]'::jsonb, 0),
    ('agent_data_curator', 'Data Quality Agent', 'Operations', 'active', 100, '["CURE-01","CURE-02","CURE-03"]'::jsonb, 0)
ON CONFLICT (agent_id) DO NOTHING;
