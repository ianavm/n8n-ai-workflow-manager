-- ============================================================
-- Migration 021: Multi-Tenant Marketing Automation Module
-- Date: 2026-04-04
-- 11 tables, RLS policies, RPCs, indexes, triggers
-- Multi-tenant via client_id -> clients(id)
-- All monetary amounts stored in cents (INTEGER)
-- ============================================================


-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Check if current user is an admin (creates if not exists from 020)
CREATE OR REPLACE FUNCTION acct_is_admin()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid())
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Get client_id for current authenticated portal user (creates if not exists from 020)
CREATE OR REPLACE FUNCTION acct_get_client_id()
RETURNS UUID AS $$
  SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()) LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- updated_at trigger function
CREATE OR REPLACE FUNCTION mkt_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ────────────────────────────────────────────────────────────
-- 1. mkt_config — Per-client marketing configuration
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL UNIQUE REFERENCES clients(id) ON DELETE CASCADE,

  -- Company context for AI
  company_name TEXT,
  industry TEXT,
  target_audience JSONB NOT NULL DEFAULT '{}',
  brand_voice JSONB NOT NULL DEFAULT '{}',

  -- Platforms
  platforms_enabled TEXT[] NOT NULL DEFAULT '{}',

  -- Budget caps (cents)
  budget_monthly_cap INTEGER NOT NULL DEFAULT 0,
  budget_alert_threshold NUMERIC(3,2) NOT NULL DEFAULT 0.80,

  -- Ad platform config (per-platform IDs)
  ad_platform_config JSONB NOT NULL DEFAULT '{}',

  -- n8n credential IDs (per-platform, resolved at runtime)
  n8n_credentials JSONB NOT NULL DEFAULT '{}',

  -- Blotato accounts config
  blotato_accounts JSONB NOT NULL DEFAULT '{}',

  -- Content settings
  content_config JSONB NOT NULL DEFAULT '{
    "auto_approve": false,
    "ai_model": "anthropic/claude-sonnet-4-20250514",
    "posting_times": {"weekday": "10:00", "weekend": "12:00"}
  }',

  -- Lead pipeline
  lead_pipeline_stages JSONB NOT NULL DEFAULT '["new","contacted","qualified","booked","proposal","won","lost"]',
  lead_assignment_mode TEXT NOT NULL DEFAULT 'round_robin'
    CHECK (lead_assignment_mode IN ('round_robin', 'manual', 'auto_score')),

  -- Messaging
  whatsapp_enabled BOOLEAN NOT NULL DEFAULT false,
  email_sender_config JSONB NOT NULL DEFAULT '{}',

  -- n8n workflow IDs (populated after deployment)
  workflow_ids JSONB NOT NULL DEFAULT '{}',

  -- Module toggles
  modules_enabled JSONB NOT NULL DEFAULT '{
    "campaigns": true,
    "content": true,
    "leads": true,
    "conversations": false,
    "reports": true
  }',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE mkt_config ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 2. mkt_campaigns — Campaign records
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  name TEXT NOT NULL,
  platform TEXT NOT NULL
    CHECK (platform IN ('google_ads', 'meta_ads', 'tiktok_ads', 'linkedin_ads', 'multi_platform')),
  campaign_type TEXT NOT NULL
    CHECK (campaign_type IN ('awareness', 'traffic', 'engagement', 'leads', 'conversions', 'sales', 'app_install')),
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'pending_review', 'approved', 'active', 'paused', 'completed', 'archived')),

  -- Budget (cents)
  budget_total INTEGER NOT NULL DEFAULT 0,
  budget_daily INTEGER NOT NULL DEFAULT 0,
  budget_spent INTEGER NOT NULL DEFAULT 0,

  -- Targeting
  targeting JSONB NOT NULL DEFAULT '{}',

  -- Dates
  start_date DATE,
  end_date DATE,

  -- External platform reference
  platform_campaign_id TEXT,
  platform_metadata JSONB DEFAULT '{}',

  -- Cached performance
  performance_summary JSONB DEFAULT '{}',

  notes TEXT,
  created_by TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_campaigns_client_status ON mkt_campaigns(client_id, status);
CREATE INDEX idx_mkt_campaigns_client_platform ON mkt_campaigns(client_id, platform);
CREATE INDEX idx_mkt_campaigns_client_date ON mkt_campaigns(client_id, start_date);
CREATE INDEX idx_mkt_campaigns_platform_id ON mkt_campaigns(platform_campaign_id) WHERE platform_campaign_id IS NOT NULL;

ALTER TABLE mkt_campaigns ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 3. mkt_ads — Individual ads within campaigns
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_ads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  campaign_id UUID NOT NULL REFERENCES mkt_campaigns(id) ON DELETE CASCADE,

  name TEXT NOT NULL,
  ad_type TEXT NOT NULL
    CHECK (ad_type IN ('image', 'video', 'carousel', 'text', 'responsive', 'shopping')),
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'active', 'paused', 'rejected', 'completed')),

  headline TEXT,
  primary_text TEXT,
  description TEXT,
  call_to_action TEXT,
  media_urls TEXT[] DEFAULT '{}',
  landing_page_url TEXT,

  -- External platform reference
  platform_ad_id TEXT,
  platform_metadata JSONB DEFAULT '{}',

  -- Cached performance
  performance JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_ads_campaign ON mkt_ads(campaign_id);
CREATE INDEX idx_mkt_ads_client_status ON mkt_ads(client_id, status);

ALTER TABLE mkt_ads ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 4. mkt_content — Content items (ideas, scripts, captions)
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_content (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  title TEXT NOT NULL,
  content_type TEXT NOT NULL
    CHECK (content_type IN ('post', 'reel', 'story', 'video_script', 'blog', 'newsletter', 'ad_copy', 'idea')),
  status TEXT NOT NULL DEFAULT 'idea'
    CHECK (status IN ('idea', 'draft', 'review', 'approved', 'scheduled', 'posted', 'failed', 'archived')),

  body TEXT,
  hook TEXT,
  hashtags TEXT[] DEFAULT '{}',
  media_urls TEXT[] DEFAULT '{}',

  ai_generated BOOLEAN NOT NULL DEFAULT false,
  ai_model TEXT,
  ai_prompt TEXT,

  target_platforms TEXT[] DEFAULT '{}',
  campaign_id UUID REFERENCES mkt_campaigns(id) ON DELETE SET NULL,

  approved_by TEXT,
  approved_at TIMESTAMPTZ,
  notes TEXT,
  created_by TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_content_client_status ON mkt_content(client_id, status);
CREATE INDEX idx_mkt_content_client_type ON mkt_content(client_id, content_type);
CREATE INDEX idx_mkt_content_campaign ON mkt_content(campaign_id) WHERE campaign_id IS NOT NULL;

ALTER TABLE mkt_content ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 5. mkt_content_calendar — Scheduled posts
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_content_calendar (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  content_id UUID NOT NULL REFERENCES mkt_content(id) ON DELETE CASCADE,

  platform TEXT NOT NULL
    CHECK (platform IN ('facebook', 'instagram', 'linkedin', 'twitter', 'tiktok', 'youtube', 'threads', 'bluesky', 'pinterest')),
  scheduled_date DATE NOT NULL,
  scheduled_time TIME NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'Africa/Johannesburg',

  status TEXT NOT NULL DEFAULT 'scheduled'
    CHECK (status IN ('scheduled', 'queued', 'posting', 'posted', 'failed', 'cancelled')),

  blotato_post_id TEXT,
  platform_post_id TEXT,
  post_url TEXT,
  error_message TEXT,
  posted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_calendar_client_date ON mkt_content_calendar(client_id, scheduled_date);
CREATE INDEX idx_mkt_calendar_client_status ON mkt_content_calendar(client_id, status);
CREATE INDEX idx_mkt_calendar_content ON mkt_content_calendar(content_id);

ALTER TABLE mkt_content_calendar ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 6. mkt_leads — Lead pipeline
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  first_name TEXT,
  last_name TEXT,
  email TEXT,
  phone TEXT,
  company TEXT,

  source TEXT NOT NULL DEFAULT 'manual'
    CHECK (source IN ('manual', 'google_ads', 'meta_ads', 'tiktok_ads', 'linkedin_ads', 'website', 'referral', 'whatsapp', 'lead_scraper', 'other')),
  source_detail TEXT,
  campaign_id UUID REFERENCES mkt_campaigns(id) ON DELETE SET NULL,

  stage TEXT NOT NULL DEFAULT 'new',
  score INTEGER NOT NULL DEFAULT 0,
  assigned_agent TEXT,
  tags TEXT[] DEFAULT '{}',
  custom_fields JSONB DEFAULT '{}',

  -- UTM tracking
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,

  -- Conversion
  conversion_value INTEGER NOT NULL DEFAULT 0,
  converted_at TIMESTAMPTZ,
  lost_reason TEXT,

  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_leads_client_stage ON mkt_leads(client_id, stage);
CREATE INDEX idx_mkt_leads_client_source ON mkt_leads(client_id, source);
CREATE INDEX idx_mkt_leads_client_email ON mkt_leads(client_id, email);
CREATE INDEX idx_mkt_leads_client_agent ON mkt_leads(client_id, assigned_agent);
CREATE INDEX idx_mkt_leads_campaign ON mkt_leads(campaign_id) WHERE campaign_id IS NOT NULL;

ALTER TABLE mkt_leads ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 7. mkt_lead_activities — Lead interaction log (append-only)
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_lead_activities (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  lead_id UUID NOT NULL REFERENCES mkt_leads(id) ON DELETE CASCADE,

  activity_type TEXT NOT NULL
    CHECK (activity_type IN ('note', 'email_sent', 'email_received', 'call', 'whatsapp', 'meeting', 'stage_change', 'score_change', 'form_submit', 'page_visit', 'ad_click', 'system')),
  title TEXT,
  notes TEXT,
  metadata JSONB DEFAULT '{}',
  actor TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_lead_activities_lead ON mkt_lead_activities(lead_id, created_at DESC);
CREATE INDEX idx_mkt_lead_activities_client ON mkt_lead_activities(client_id, created_at DESC);

ALTER TABLE mkt_lead_activities ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 8. mkt_conversations — Unified message threads
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  lead_id UUID REFERENCES mkt_leads(id) ON DELETE SET NULL,

  channel TEXT NOT NULL
    CHECK (channel IN ('whatsapp', 'email', 'sms', 'instagram_dm', 'facebook_messenger')),
  external_thread_id TEXT,
  subject TEXT,

  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'replied', 'waiting', 'closed', 'spam')),
  assigned_agent TEXT,
  last_message_at TIMESTAMPTZ,
  unread_count INTEGER NOT NULL DEFAULT 0,
  tags TEXT[] DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_conversations_client_status ON mkt_conversations(client_id, status);
CREATE INDEX idx_mkt_conversations_lead ON mkt_conversations(lead_id) WHERE lead_id IS NOT NULL;
CREATE INDEX idx_mkt_conversations_thread ON mkt_conversations(client_id, channel, external_thread_id);

ALTER TABLE mkt_conversations ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 9. mkt_messages — Individual messages within conversations
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_messages (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  conversation_id UUID NOT NULL REFERENCES mkt_conversations(id) ON DELETE CASCADE,

  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  content TEXT NOT NULL,
  content_type TEXT NOT NULL DEFAULT 'text'
    CHECK (content_type IN ('text', 'image', 'video', 'audio', 'document', 'template')),
  media_url TEXT,

  ai_generated BOOLEAN NOT NULL DEFAULT false,
  human_override BOOLEAN NOT NULL DEFAULT false,
  ai_draft TEXT,

  external_message_id TEXT,
  delivered_at TIMESTAMPTZ,
  read_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_messages_conversation ON mkt_messages(conversation_id, created_at);
CREATE INDEX idx_mkt_messages_client ON mkt_messages(client_id, created_at DESC);

ALTER TABLE mkt_messages ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 10. mkt_performance — Daily performance snapshots
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_performance (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES mkt_campaigns(id) ON DELETE CASCADE,
  ad_id UUID REFERENCES mkt_ads(id) ON DELETE SET NULL,

  date DATE NOT NULL,
  platform TEXT NOT NULL,

  -- Core metrics
  impressions INTEGER NOT NULL DEFAULT 0,
  clicks INTEGER NOT NULL DEFAULT 0,
  spend INTEGER NOT NULL DEFAULT 0,
  conversions INTEGER NOT NULL DEFAULT 0,
  conversion_value INTEGER NOT NULL DEFAULT 0,
  leads_generated INTEGER NOT NULL DEFAULT 0,

  -- Calculated metrics
  ctr NUMERIC(6,4) DEFAULT 0,
  cpc INTEGER DEFAULT 0,
  cpl INTEGER DEFAULT 0,
  cpa INTEGER DEFAULT 0,
  roas NUMERIC(8,4) DEFAULT 0,

  -- Engagement metrics
  reach INTEGER DEFAULT 0,
  frequency NUMERIC(4,2) DEFAULT 0,
  video_views INTEGER DEFAULT 0,
  engagement INTEGER DEFAULT 0,

  -- Raw API response
  raw_data JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Prevent duplicate syncs
  UNIQUE(campaign_id, ad_id, date, platform)
);

CREATE INDEX idx_mkt_performance_client_date ON mkt_performance(client_id, date DESC);
CREATE INDEX idx_mkt_performance_campaign_date ON mkt_performance(campaign_id, date DESC);
CREATE INDEX idx_mkt_performance_client_platform ON mkt_performance(client_id, platform, date);

ALTER TABLE mkt_performance ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 11. mkt_tasks — Follow-ups and action items
-- ────────────────────────────────────────────────────────────
CREATE TABLE mkt_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  title TEXT NOT NULL,
  description TEXT,
  type TEXT NOT NULL
    CHECK (type IN ('follow_up', 'content_review', 'campaign_action', 'report_review', 'budget_alert', 'lead_action', 'general')),
  priority TEXT NOT NULL DEFAULT 'medium'
    CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'in_progress', 'completed', 'cancelled')),

  assignee TEXT,
  due_date DATE,
  related_entity_type TEXT
    CHECK (related_entity_type IN ('campaign', 'content', 'lead', 'conversation', 'ad')),
  related_entity_id UUID,

  completed_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mkt_tasks_client_status ON mkt_tasks(client_id, status);
CREATE INDEX idx_mkt_tasks_client_assignee ON mkt_tasks(client_id, assignee, status);
CREATE INDEX idx_mkt_tasks_client_due ON mkt_tasks(client_id, due_date) WHERE status IN ('open', 'in_progress');

ALTER TABLE mkt_tasks ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================================

-- ── mkt_config ────────────────────────────────────────────
CREATE POLICY "client_own_mkt_config" ON mkt_config FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_config_all" ON mkt_config FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_mkt_config_write" ON mkt_config FOR ALL
  USING (auth.role() = 'service_role');

-- ── mkt_campaigns ─────────────────────────────────────────
CREATE POLICY "client_own_mkt_campaigns" ON mkt_campaigns FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_campaigns_all" ON mkt_campaigns FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_mkt_campaigns_write" ON mkt_campaigns FOR ALL
  USING (auth.role() = 'service_role');

-- ── mkt_ads ───────────────────────────────────────────────
CREATE POLICY "client_own_mkt_ads" ON mkt_ads FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_ads_all" ON mkt_ads FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_mkt_ads_write" ON mkt_ads FOR ALL
  USING (auth.role() = 'service_role');

-- ── mkt_content ───────────────────────────────────────────
CREATE POLICY "client_own_mkt_content" ON mkt_content FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_content_all" ON mkt_content FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_mkt_content_write" ON mkt_content FOR ALL
  USING (auth.role() = 'service_role');

-- ── mkt_content_calendar ──────────────────────────────────
CREATE POLICY "client_own_mkt_calendar" ON mkt_content_calendar FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_calendar_all" ON mkt_content_calendar FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_mkt_calendar_write" ON mkt_content_calendar FOR ALL
  USING (auth.role() = 'service_role');

-- ── mkt_leads ─────────────────────────────────────────────
CREATE POLICY "client_own_mkt_leads" ON mkt_leads FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_leads_all" ON mkt_leads FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_mkt_leads_write" ON mkt_leads FOR ALL
  USING (auth.role() = 'service_role');

-- ── mkt_lead_activities (append-only: SELECT + INSERT only) ──
CREATE POLICY "client_own_mkt_lead_activities" ON mkt_lead_activities FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_lead_activities_select" ON mkt_lead_activities FOR SELECT
  USING (acct_is_admin());
CREATE POLICY "service_mkt_lead_activities_insert" ON mkt_lead_activities FOR INSERT
  WITH CHECK (auth.role() = 'service_role');
CREATE POLICY "admin_mkt_lead_activities_insert" ON mkt_lead_activities FOR INSERT
  WITH CHECK (acct_is_admin());

-- ── mkt_conversations ─────────────────────────────────────
CREATE POLICY "client_own_mkt_conversations" ON mkt_conversations FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_conversations_all" ON mkt_conversations FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_mkt_conversations_write" ON mkt_conversations FOR ALL
  USING (auth.role() = 'service_role');

-- ── mkt_messages (append-only: SELECT + INSERT only) ──────
CREATE POLICY "client_own_mkt_messages" ON mkt_messages FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_messages_select" ON mkt_messages FOR SELECT
  USING (acct_is_admin());
CREATE POLICY "service_mkt_messages_insert" ON mkt_messages FOR INSERT
  WITH CHECK (auth.role() = 'service_role');
CREATE POLICY "admin_mkt_messages_insert" ON mkt_messages FOR INSERT
  WITH CHECK (acct_is_admin());

-- ── mkt_performance (append-only: SELECT + INSERT/UPDATE for sync) ──
CREATE POLICY "client_own_mkt_performance" ON mkt_performance FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_performance_select" ON mkt_performance FOR SELECT
  USING (acct_is_admin());
CREATE POLICY "service_mkt_performance_write" ON mkt_performance FOR ALL
  USING (auth.role() = 'service_role');

-- ── mkt_tasks ─────────────────────────────────────────────
CREATE POLICY "client_own_mkt_tasks" ON mkt_tasks FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_mkt_tasks_all" ON mkt_tasks FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_mkt_tasks_write" ON mkt_tasks FOR ALL
  USING (auth.role() = 'service_role');


-- ============================================================
-- RPC FUNCTIONS (SECURITY DEFINER — bypass RLS for aggregation)
-- ============================================================

-- ── Marketing Dashboard KPIs ─────────────────────────────
CREATE OR REPLACE FUNCTION mkt_get_dashboard_kpis(p_client_id UUID)
RETURNS JSONB AS $$
DECLARE
  v_result JSONB;
  v_period_start DATE := date_trunc('month', CURRENT_DATE)::DATE;
BEGIN
  SELECT jsonb_build_object(
    'total_spend_month', COALESCE(
      (SELECT SUM(spend) FROM mkt_performance
       WHERE client_id = p_client_id AND date >= v_period_start), 0),
    'total_spend_all', COALESCE(
      (SELECT SUM(budget_spent) FROM mkt_campaigns
       WHERE client_id = p_client_id AND status NOT IN ('draft', 'archived')), 0),
    'leads_generated_month', COALESCE(
      (SELECT COUNT(*) FROM mkt_leads
       WHERE client_id = p_client_id AND created_at >= v_period_start), 0),
    'leads_generated_today', COALESCE(
      (SELECT COUNT(*) FROM mkt_leads
       WHERE client_id = p_client_id AND created_at >= CURRENT_DATE), 0),
    'active_campaigns', COALESCE(
      (SELECT COUNT(*) FROM mkt_campaigns
       WHERE client_id = p_client_id AND status = 'active'), 0),
    'avg_cpl', COALESCE(
      (SELECT CASE WHEN SUM(leads_generated) > 0
        THEN SUM(spend) / SUM(leads_generated) ELSE 0 END
       FROM mkt_performance
       WHERE client_id = p_client_id AND date >= v_period_start), 0),
    'avg_cpa', COALESCE(
      (SELECT CASE WHEN SUM(conversions) > 0
        THEN SUM(spend) / SUM(conversions) ELSE 0 END
       FROM mkt_performance
       WHERE client_id = p_client_id AND date >= v_period_start), 0),
    'total_roas', COALESCE(
      (SELECT CASE WHEN SUM(spend) > 0
        THEN ROUND(SUM(conversion_value)::NUMERIC / SUM(spend)::NUMERIC, 2) ELSE 0 END
       FROM mkt_performance
       WHERE client_id = p_client_id AND date >= v_period_start), 0),
    'conversion_rate', COALESCE(
      (SELECT CASE WHEN SUM(clicks) > 0
        THEN ROUND(SUM(conversions)::NUMERIC / SUM(clicks)::NUMERIC * 100, 2) ELSE 0 END
       FROM mkt_performance
       WHERE client_id = p_client_id AND date >= v_period_start), 0),
    'scheduled_posts', COALESCE(
      (SELECT COUNT(*) FROM mkt_content_calendar
       WHERE client_id = p_client_id AND status = 'scheduled'), 0),
    'pipeline_value', COALESCE(
      (SELECT SUM(conversion_value) FROM mkt_leads
       WHERE client_id = p_client_id AND stage NOT IN ('lost')), 0),
    'open_tasks', COALESCE(
      (SELECT COUNT(*) FROM mkt_tasks
       WHERE client_id = p_client_id AND status IN ('open', 'in_progress')), 0),
    'unread_conversations', COALESCE(
      (SELECT SUM(unread_count) FROM mkt_conversations
       WHERE client_id = p_client_id AND status != 'closed'), 0)
  ) INTO v_result;

  RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ── Campaign Performance (time-series) ────────────────────
CREATE OR REPLACE FUNCTION mkt_get_campaign_performance(
  p_campaign_id UUID,
  p_days INTEGER DEFAULT 30
)
RETURNS JSONB AS $$
BEGIN
  RETURN (
    SELECT COALESCE(jsonb_agg(day_data ORDER BY day_data->>'date'), '[]'::jsonb)
    FROM (
      SELECT jsonb_build_object(
        'date', date,
        'impressions', SUM(impressions),
        'clicks', SUM(clicks),
        'spend', SUM(spend),
        'conversions', SUM(conversions),
        'leads', SUM(leads_generated),
        'ctr', CASE WHEN SUM(impressions) > 0
          THEN ROUND(SUM(clicks)::NUMERIC / SUM(impressions)::NUMERIC * 100, 2) ELSE 0 END,
        'cpc', CASE WHEN SUM(clicks) > 0
          THEN SUM(spend) / SUM(clicks) ELSE 0 END
      ) AS day_data
      FROM mkt_performance
      WHERE campaign_id = p_campaign_id
        AND date >= CURRENT_DATE - p_days
      GROUP BY date
    ) sub
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ── Lead Pipeline Summary ─────────────────────────────────
CREATE OR REPLACE FUNCTION mkt_get_lead_pipeline_summary(p_client_id UUID)
RETURNS JSONB AS $$
BEGIN
  RETURN (
    SELECT COALESCE(jsonb_agg(stage_data), '[]'::jsonb)
    FROM (
      SELECT jsonb_build_object(
        'stage', stage,
        'count', COUNT(*),
        'total_value', COALESCE(SUM(conversion_value), 0),
        'avg_score', COALESCE(ROUND(AVG(score)::NUMERIC, 1), 0)
      ) AS stage_data
      FROM mkt_leads
      WHERE client_id = p_client_id
      GROUP BY stage
      ORDER BY
        CASE stage
          WHEN 'new' THEN 1
          WHEN 'contacted' THEN 2
          WHEN 'qualified' THEN 3
          WHEN 'booked' THEN 4
          WHEN 'proposal' THEN 5
          WHEN 'won' THEN 6
          WHEN 'lost' THEN 7
          ELSE 8
        END
    ) sub
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ── Content Calendar Range ────────────────────────────────
CREATE OR REPLACE FUNCTION mkt_get_content_calendar_range(
  p_client_id UUID,
  p_start DATE,
  p_end DATE
)
RETURNS JSONB AS $$
BEGIN
  RETURN (
    SELECT COALESCE(jsonb_agg(cal_entry ORDER BY cal_entry->>'scheduled_date', cal_entry->>'scheduled_time'), '[]'::jsonb)
    FROM (
      SELECT jsonb_build_object(
        'id', cc.id,
        'content_id', cc.content_id,
        'title', c.title,
        'content_type', c.content_type,
        'platform', cc.platform,
        'scheduled_date', cc.scheduled_date,
        'scheduled_time', cc.scheduled_time,
        'status', cc.status,
        'post_url', cc.post_url
      ) AS cal_entry
      FROM mkt_content_calendar cc
      JOIN mkt_content c ON c.id = cc.content_id
      WHERE cc.client_id = p_client_id
        AND cc.scheduled_date BETWEEN p_start AND p_end
    ) sub
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ============================================================
-- UPDATED_AT TRIGGERS
-- ============================================================

CREATE TRIGGER trg_mkt_config_updated
  BEFORE UPDATE ON mkt_config FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();
CREATE TRIGGER trg_mkt_campaigns_updated
  BEFORE UPDATE ON mkt_campaigns FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();
CREATE TRIGGER trg_mkt_ads_updated
  BEFORE UPDATE ON mkt_ads FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();
CREATE TRIGGER trg_mkt_content_updated
  BEFORE UPDATE ON mkt_content FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();
CREATE TRIGGER trg_mkt_calendar_updated
  BEFORE UPDATE ON mkt_content_calendar FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();
CREATE TRIGGER trg_mkt_leads_updated
  BEFORE UPDATE ON mkt_leads FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();
CREATE TRIGGER trg_mkt_conversations_updated
  BEFORE UPDATE ON mkt_conversations FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();
CREATE TRIGGER trg_mkt_tasks_updated
  BEFORE UPDATE ON mkt_tasks FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();


-- ============================================================
-- ENABLE REALTIME (for live portal updates)
-- ============================================================

ALTER PUBLICATION supabase_realtime ADD TABLE mkt_campaigns;
ALTER PUBLICATION supabase_realtime ADD TABLE mkt_leads;
ALTER PUBLICATION supabase_realtime ADD TABLE mkt_content_calendar;
ALTER PUBLICATION supabase_realtime ADD TABLE mkt_conversations;
ALTER PUBLICATION supabase_realtime ADD TABLE mkt_tasks;
