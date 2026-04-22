-- ============================================================
-- Migration 031: CRM Module (Client-Facing Lead-Gen / Outreach Dashboard)
-- Date: 2026-04-22
-- Multi-tenant via client_id -> clients(id); AVM staff via admin_users
-- RLS pattern mirrors migration 020 (acct_*)
-- Scope: Phase-1 of plan at C:\Users\ianim\.claude\plans\you-are-acting-as-cozy-wigderson.md
-- ============================================================


-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

CREATE OR REPLACE FUNCTION crm_is_admin()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid())
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION crm_get_client_id()
RETURNS UUID AS $$
  SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()) LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;


-- ============================================================
-- 1. crm_config — Per-client CRM configuration + branding override
-- ============================================================
CREATE TABLE crm_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL UNIQUE REFERENCES clients(id) ON DELETE CASCADE,

  -- Sending identity
  sender_name TEXT,
  sender_email TEXT,
  sender_signature TEXT,

  -- Branding override (per-client accent on KPIs / charts)
  accent_color TEXT,  -- hex, e.g. '#FF6D5A'; NULL = inherit portal default

  -- Score weighting (0-100 each; stored as pct, summed client-side)
  score_weight_icp_fit INTEGER NOT NULL DEFAULT 40 CHECK (score_weight_icp_fit BETWEEN 0 AND 100),
  score_weight_signals INTEGER NOT NULL DEFAULT 30 CHECK (score_weight_signals BETWEEN 0 AND 100),
  score_weight_recency INTEGER NOT NULL DEFAULT 20 CHECK (score_weight_recency BETWEEN 0 AND 100),
  score_weight_completeness INTEGER NOT NULL DEFAULT 10 CHECK (score_weight_completeness BETWEEN 0 AND 100),

  -- Default timezone (IANA, e.g. 'Africa/Johannesburg')
  timezone TEXT NOT NULL DEFAULT 'Africa/Johannesburg',

  -- Airtable reconcile (optional)
  airtable_base_id TEXT,
  airtable_companies_table TEXT,
  airtable_leads_table TEXT,
  airtable_sync_enabled BOOLEAN NOT NULL DEFAULT FALSE,

  -- n8n workflow IDs (populated post-deploy)
  workflow_ids JSONB NOT NULL DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE crm_config ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 2. crm_stages — Per-client kanban stages (ordered)
-- ============================================================
CREATE TABLE crm_stages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  key TEXT NOT NULL,            -- slug, e.g. 'new', 'researched'
  label TEXT NOT NULL,          -- display, e.g. 'New'
  order_index INTEGER NOT NULL,
  is_won BOOLEAN NOT NULL DEFAULT FALSE,
  is_lost BOOLEAN NOT NULL DEFAULT FALSE,
  color TEXT,                   -- hex for column accent
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (client_id, key)
);

CREATE INDEX idx_crm_stages_client_order ON crm_stages (client_id, order_index);

ALTER TABLE crm_stages ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 3. crm_companies — Accounts / organisations being prospected
-- ============================================================
CREATE TABLE crm_companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  name TEXT NOT NULL,
  domain TEXT,
  industry TEXT,
  country TEXT,
  size_band TEXT,        -- e.g. '1-10', '11-50', '51-200', '201-500', '501-1000', '1000+'
  revenue_band TEXT,     -- e.g. '<1M', '1-10M', '10-50M', '50-250M', '250M+'
  linkedin_url TEXT,
  website TEXT,
  logo_url TEXT,
  hq_city TEXT,
  meta JSONB NOT NULL DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_crm_companies_client ON crm_companies (client_id);
CREATE INDEX idx_crm_companies_client_industry ON crm_companies (client_id, industry);
CREATE INDEX idx_crm_companies_client_country ON crm_companies (client_id, country);
CREATE INDEX idx_crm_companies_domain ON crm_companies (domain);

ALTER TABLE crm_companies ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 4. crm_contacts — People at companies
-- ============================================================
CREATE TABLE crm_contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  company_id UUID REFERENCES crm_companies(id) ON DELETE SET NULL,

  first_name TEXT,
  last_name TEXT,
  title TEXT,
  email TEXT,
  phone TEXT,
  linkedin_url TEXT,
  avatar_url TEXT,
  meta JSONB NOT NULL DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_crm_contacts_client ON crm_contacts (client_id);
CREATE INDEX idx_crm_contacts_company ON crm_contacts (company_id);
CREATE INDEX idx_crm_contacts_email ON crm_contacts (email);

ALTER TABLE crm_contacts ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 5. crm_leads — The central entity: contact × company × stage × score
-- ============================================================
CREATE TABLE crm_leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  company_id UUID REFERENCES crm_companies(id) ON DELETE SET NULL,
  contact_id UUID REFERENCES crm_contacts(id) ON DELETE SET NULL,

  stage_key TEXT NOT NULL DEFAULT 'new',
  score INTEGER CHECK (score BETWEEN 0 AND 100),
  status_tags TEXT[] NOT NULL DEFAULT '{}',   -- free-form pill labels
  tags TEXT[] NOT NULL DEFAULT '{}',

  owner_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
  source TEXT,                -- 'apollo', 'apify', 'manual_csv', 'places', ...
  source_campaign TEXT,

  next_action TEXT,
  next_action_at TIMESTAMPTZ,
  last_touch_at TIMESTAMPTZ,

  deal_value_zar NUMERIC(14,2),
  deal_probability INTEGER CHECK (deal_probability BETWEEN 0 AND 100),
  closed_at TIMESTAMPTZ,

  meta JSONB NOT NULL DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_crm_leads_client_stage ON crm_leads (client_id, stage_key);
CREATE INDEX idx_crm_leads_client_created ON crm_leads (client_id, created_at DESC);
CREATE INDEX idx_crm_leads_client_score ON crm_leads (client_id, score DESC);
CREATE INDEX idx_crm_leads_company ON crm_leads (company_id);
CREATE INDEX idx_crm_leads_contact ON crm_leads (contact_id);
CREATE INDEX idx_crm_leads_owner ON crm_leads (owner_admin_id);

ALTER TABLE crm_leads ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 6. crm_activities — Timeline events (one append-only log per lead)
-- ============================================================
CREATE TABLE crm_activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  lead_id UUID NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,

  kind TEXT NOT NULL CHECK (kind IN (
    'created', 'enriched', 'researched', 'scored',
    'stage_changed', 'owner_changed',
    'emailed', 'opened', 'clicked', 'replied',
    'call_scheduled', 'call_completed',
    'note_added', 'tag_added', 'tag_removed',
    'won', 'lost'
  )),
  meta JSONB NOT NULL DEFAULT '{}',
  actor_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_crm_activities_lead_date ON crm_activities (lead_id, created_at DESC);
CREATE INDEX idx_crm_activities_client_kind_date ON crm_activities (client_id, kind, created_at DESC);

ALTER TABLE crm_activities ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 7. crm_email_templates — Reusable outreach templates
-- ============================================================
CREATE TABLE crm_email_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN (
    'cold_outreach', 'follow_up', 'post_meeting', 'nurture', 'other'
  )),
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  variables TEXT[] NOT NULL DEFAULT '{}',  -- e.g. '{first_name,company,pain_point}'
  is_default BOOLEAN NOT NULL DEFAULT FALSE,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_crm_email_templates_client ON crm_email_templates (client_id);

ALTER TABLE crm_email_templates ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 8. crm_email_messages — Outbound/inbound messages per lead
-- ============================================================
CREATE TABLE crm_email_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  lead_id UUID NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
  template_id UUID REFERENCES crm_email_templates(id) ON DELETE SET NULL,

  direction TEXT NOT NULL CHECK (direction IN ('out', 'in')),
  send_mode TEXT CHECK (send_mode IN ('mailto', 'gmail_draft', 'gmail_send')),
  provider_message_id TEXT,
  to_email TEXT,
  from_email TEXT,

  subject TEXT NOT NULL,
  body TEXT NOT NULL,

  sent_at TIMESTAMPTZ,
  opened_at TIMESTAMPTZ,
  first_clicked_at TIMESTAMPTZ,
  replied_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_crm_messages_lead_date ON crm_email_messages (lead_id, created_at DESC);
CREATE INDEX idx_crm_messages_client_sent ON crm_email_messages (client_id, sent_at DESC);
CREATE INDEX idx_crm_messages_provider ON crm_email_messages (provider_message_id);

ALTER TABLE crm_email_messages ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 9. crm_research_reports — AI-generated per-lead research
-- ============================================================
CREATE TABLE crm_research_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  lead_id UUID NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,

  summary TEXT,
  sections JSONB NOT NULL DEFAULT '{}',  -- {what_going_well:[...], opportunities:[...], gaps:[...], angle:'...', ...}
  doc_url TEXT,
  pdf_url TEXT,

  model TEXT,
  tokens_in INTEGER,
  tokens_out INTEGER,
  cost_usd NUMERIC(10,4),

  version INTEGER NOT NULL DEFAULT 1,
  is_current BOOLEAN NOT NULL DEFAULT TRUE,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_crm_research_lead ON crm_research_reports (lead_id, created_at DESC);
CREATE INDEX idx_crm_research_client ON crm_research_reports (client_id, created_at DESC);
CREATE INDEX idx_crm_research_current ON crm_research_reports (lead_id) WHERE is_current;

ALTER TABLE crm_research_reports ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 10. crm_imports — CSV import jobs (audit + retryability)
-- ============================================================
CREATE TABLE crm_imports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  filename TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending', 'parsing', 'ingesting', 'completed', 'failed'
  )),
  rows_total INTEGER,
  rows_ingested INTEGER NOT NULL DEFAULT 0,
  rows_failed INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  field_mapping JSONB NOT NULL DEFAULT '{}',  -- csv_col -> lead/contact/company field

  created_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX idx_crm_imports_client_created ON crm_imports (client_id, created_at DESC);

ALTER TABLE crm_imports ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- RLS POLICIES — mirrors migration 020 pattern exactly
-- Two policies per table: admins_all_X (AVM staff) + clients_own_X (tenant)
-- Writes are admin-only for Phase 1 (keeps client view read-safe)
-- ============================================================

-- crm_config
CREATE POLICY "admins_all_crm_config" ON crm_config
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_config" ON crm_config
  FOR SELECT USING (client_id = crm_get_client_id());

-- crm_stages
CREATE POLICY "admins_all_crm_stages" ON crm_stages
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_stages" ON crm_stages
  FOR SELECT USING (client_id = crm_get_client_id());

-- crm_companies
CREATE POLICY "admins_all_crm_companies" ON crm_companies
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_companies" ON crm_companies
  FOR SELECT USING (client_id = crm_get_client_id());

-- crm_contacts
CREATE POLICY "admins_all_crm_contacts" ON crm_contacts
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_contacts" ON crm_contacts
  FOR SELECT USING (client_id = crm_get_client_id());

-- crm_leads
CREATE POLICY "admins_all_crm_leads" ON crm_leads
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_leads_select" ON crm_leads
  FOR SELECT USING (client_id = crm_get_client_id());
-- Phase-1: clients may update stage only (Kanban drag); further writes via admin / API
CREATE POLICY "clients_own_crm_leads_update_stage" ON crm_leads
  FOR UPDATE USING (client_id = crm_get_client_id())
  WITH CHECK (client_id = crm_get_client_id());

-- crm_activities (append-only from app; clients read own)
CREATE POLICY "admins_all_crm_activities" ON crm_activities
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_activities" ON crm_activities
  FOR SELECT USING (client_id = crm_get_client_id());

-- crm_email_templates
CREATE POLICY "admins_all_crm_email_templates" ON crm_email_templates
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_email_templates" ON crm_email_templates
  FOR SELECT USING (client_id = crm_get_client_id());

-- crm_email_messages
CREATE POLICY "admins_all_crm_email_messages" ON crm_email_messages
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_email_messages" ON crm_email_messages
  FOR SELECT USING (client_id = crm_get_client_id());
CREATE POLICY "clients_own_crm_email_messages_insert" ON crm_email_messages
  FOR INSERT WITH CHECK (client_id = crm_get_client_id());

-- crm_research_reports
CREATE POLICY "admins_all_crm_research" ON crm_research_reports
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());
CREATE POLICY "clients_own_crm_research" ON crm_research_reports
  FOR SELECT USING (client_id = crm_get_client_id());

-- crm_imports (admin-only; no client access)
CREATE POLICY "admins_all_crm_imports" ON crm_imports
  FOR ALL USING (crm_is_admin()) WITH CHECK (crm_is_admin());


-- ============================================================
-- TRIGGERS — updated_at maintenance
-- ============================================================

CREATE OR REPLACE FUNCTION crm_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_crm_config_updated BEFORE UPDATE ON crm_config
  FOR EACH ROW EXECUTE FUNCTION crm_set_updated_at();
CREATE TRIGGER trg_crm_companies_updated BEFORE UPDATE ON crm_companies
  FOR EACH ROW EXECUTE FUNCTION crm_set_updated_at();
CREATE TRIGGER trg_crm_contacts_updated BEFORE UPDATE ON crm_contacts
  FOR EACH ROW EXECUTE FUNCTION crm_set_updated_at();
CREATE TRIGGER trg_crm_leads_updated BEFORE UPDATE ON crm_leads
  FOR EACH ROW EXECUTE FUNCTION crm_set_updated_at();
CREATE TRIGGER trg_crm_email_templates_updated BEFORE UPDATE ON crm_email_templates
  FOR EACH ROW EXECUTE FUNCTION crm_set_updated_at();


-- ============================================================
-- ACTIVITY AUTO-LOG — stage changes emit a crm_activities row
-- ============================================================

CREATE OR REPLACE FUNCTION crm_log_stage_change()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.stage_key IS DISTINCT FROM OLD.stage_key THEN
    INSERT INTO crm_activities (client_id, lead_id, kind, meta)
    VALUES (NEW.client_id, NEW.id, 'stage_changed',
            jsonb_build_object('from', OLD.stage_key, 'to', NEW.stage_key));
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_crm_leads_stage_change AFTER UPDATE ON crm_leads
  FOR EACH ROW EXECUTE FUNCTION crm_log_stage_change();


-- ============================================================
-- SEED: default stage set + default templates per existing client
-- (Admins can override per client post-seed.)
-- ============================================================

-- Default stages (applied to every existing client; new clients get these via app bootstrap)
INSERT INTO crm_stages (client_id, key, label, order_index, is_won, is_lost, color)
SELECT c.id, s.key, s.label, s.order_index, s.is_won, s.is_lost, s.color
FROM clients c
CROSS JOIN (VALUES
  ('new',            'New',            1, FALSE, FALSE, '#64748B'),
  ('enriched',       'Enriched',       2, FALSE, FALSE, '#38BDF8'),
  ('researched',     'Researched',     3, FALSE, FALSE, '#8B5CF6'),
  ('outreach_sent',  'Outreach Sent',  4, FALSE, FALSE, '#FF6D5A'),
  ('replied',        'Replied',        5, FALSE, FALSE, '#F59E0B'),
  ('meeting_booked', 'Meeting Booked', 6, FALSE, FALSE, '#2DD4BF'),
  ('closed_won',     'Closed Won',     7, TRUE,  FALSE, '#10B981'),
  ('closed_lost',    'Closed Lost',    8, FALSE, TRUE,  '#EF4444')
) AS s(key, label, order_index, is_won, is_lost, color)
ON CONFLICT (client_id, key) DO NOTHING;

-- Default templates
INSERT INTO crm_email_templates (client_id, name, category, subject, body, variables, is_default)
SELECT c.id, t.name, t.category, t.subject, t.body, t.variables, t.is_default
FROM clients c
CROSS JOIN (VALUES
  (
    'Cold Intro — AI Automation', 'cold_outreach',
    'Quick idea for {{company}}',
    E'Hi {{first_name}},\n\nNoticed {{company}} is doing {{pain_point}} — we help teams like yours automate the manual parts without ripping out what works.\n\nWorth a 15-minute look? I can send a before/after from a similar business.\n\n— {{sender_name}}',
    '{first_name,company,pain_point,sender_name}',
    TRUE
  ),
  (
    'Cold Intro — Dashboard/CRM', 'cold_outreach',
    'A cleaner view of {{company}}''s pipeline',
    E'Hi {{first_name}},\n\nMost teams we work with have the data — they just don''t have one place to see it. We built a dashboard that pulls {{pain_point}} into a single view.\n\n5-minute walkthrough if you''re curious?\n\n— {{sender_name}}',
    '{first_name,company,pain_point,sender_name}',
    FALSE
  ),
  (
    'Cold Intro — Voice Agent', 'cold_outreach',
    '{{company}} + an AI voice agent',
    E'Hi {{first_name}},\n\nWhat if {{company}} could qualify every inbound call in 30 seconds without a person picking up? We deploy AI voice agents that do exactly that — and hand warm leads straight to your team.\n\nDemo link below if you want to hear one live.\n\n— {{sender_name}}',
    '{first_name,company,sender_name}',
    FALSE
  ),
  (
    'Follow-Up #1', 'follow_up',
    'Re: Quick idea for {{company}}',
    E'Hi {{first_name}},\n\nFloating this back up in case it got buried. Happy to keep it async if that''s easier — I can send a 2-minute Loom instead of a call.\n\n— {{sender_name}}',
    '{first_name,company,sender_name}',
    FALSE
  ),
  (
    'Follow-Up #2 — Value Add', 'follow_up',
    'A teardown for {{company}}',
    E'Hi {{first_name}},\n\nIn case the cold pitch didn''t land — here''s a free teardown we wrote on {{company}}''s public funnel: {{custom_note}}.\n\nNo ask. If anything in there is useful, let me know.\n\n— {{sender_name}}',
    '{first_name,company,custom_note,sender_name}',
    FALSE
  ),
  (
    'Post-Call Thank You', 'post_meeting',
    'Great speaking with you, {{first_name}}',
    E'Hi {{first_name}},\n\nThanks for the time today. Quick recap of what we discussed:\n\n- {{custom_note}}\n\nI''ll send the proposal by {{meeting_link}}. Reach out if anything else comes up before then.\n\n— {{sender_name}}',
    '{first_name,custom_note,meeting_link,sender_name}',
    FALSE
  )
) AS t(name, category, subject, body, variables, is_default)
ON CONFLICT DO NOTHING;

-- One crm_config row per existing client (idempotent)
INSERT INTO crm_config (client_id)
SELECT id FROM clients
ON CONFLICT (client_id) DO NOTHING;


-- ============================================================
-- END migration 031
-- ============================================================
