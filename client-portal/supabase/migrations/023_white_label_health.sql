-- ============================================================
-- Migration 023: White-Label Branding + Health Scoring Enhancements
-- Date: 2026-04-04
-- ============================================================

-- White-label columns on clients
ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS logo_url TEXT,
  ADD COLUMN IF NOT EXISTS brand_color TEXT DEFAULT '#6C63FF',
  ADD COLUMN IF NOT EXISTS custom_domain TEXT,
  ADD COLUMN IF NOT EXISTS favicon_url TEXT,
  ADD COLUMN IF NOT EXISTS dashboard_config JSONB DEFAULT '{}';

-- Enhance health scores with transparency
ALTER TABLE client_health_scores
  ADD COLUMN IF NOT EXISTS score_details JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS trend TEXT DEFAULT 'stable' CHECK (trend IN ('improving', 'stable', 'declining')),
  ADD COLUMN IF NOT EXISTS days_at_risk INTEGER DEFAULT 0;

-- Health alerts
CREATE TABLE IF NOT EXISTS health_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL CHECK (alert_type IN ('score_drop', 'payment_overdue', 'usage_decline', 'engagement_drop', 'support_escalation')),
  severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  message TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_health_alerts_client ON health_alerts(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_alerts_unresolved ON health_alerts(severity) WHERE resolved_at IS NULL;
ALTER TABLE health_alerts ENABLE ROW LEVEL SECURITY;

-- Health interventions
CREATE TABLE IF NOT EXISTS health_interventions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  health_alert_id UUID REFERENCES health_alerts(id) ON DELETE SET NULL,
  intervention_type TEXT NOT NULL CHECK (intervention_type IN ('email', 'call', 'task', 'offer', 'meeting')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'completed', 'ignored', 'failed')),
  result TEXT,
  notes TEXT,
  assigned_to UUID REFERENCES admin_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_health_interventions_client ON health_interventions(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_interventions_status ON health_interventions(status) WHERE status = 'pending';
ALTER TABLE health_interventions ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "client_own_health_alerts" ON health_alerts FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_health_alerts_all" ON health_alerts FOR ALL USING (acct_is_admin());
CREATE POLICY "service_health_alerts_write" ON health_alerts FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "admin_health_interventions_all" ON health_interventions FOR ALL USING (acct_is_admin());
CREATE POLICY "service_health_interventions_write" ON health_interventions FOR ALL USING (auth.role() = 'service_role');

-- Updated_at trigger
CREATE TRIGGER trg_health_interventions_updated
  BEFORE UPDATE ON health_interventions FOR EACH ROW EXECUTE FUNCTION mkt_set_updated_at();

-- RPC: get client health details
CREATE OR REPLACE FUNCTION get_client_health_details(p_client_id UUID)
RETURNS JSONB AS $$
DECLARE
  v_latest JSONB;
  v_history JSONB;
  v_alerts JSONB;
BEGIN
  SELECT jsonb_build_object(
    'composite_score', composite_score, 'usage_score', usage_score,
    'payment_score', payment_score, 'engagement_score', engagement_score,
    'support_score', support_score, 'risk_level', risk_level,
    'trend', trend, 'days_at_risk', days_at_risk,
    'score_details', score_details, 'score_date', score_date
  ) INTO v_latest
  FROM client_health_scores WHERE client_id = p_client_id
  ORDER BY score_date DESC LIMIT 1;

  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'date', score_date, 'composite', composite_score,
    'usage', usage_score, 'payment', payment_score,
    'engagement', engagement_score, 'support', support_score,
    'risk_level', risk_level
  ) ORDER BY score_date), '[]'::jsonb) INTO v_history
  FROM client_health_scores
  WHERE client_id = p_client_id AND score_date >= CURRENT_DATE - 90;

  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'id', id, 'alert_type', alert_type, 'severity', severity,
    'message', message, 'metadata', metadata, 'created_at', created_at
  ) ORDER BY created_at DESC), '[]'::jsonb) INTO v_alerts
  FROM health_alerts WHERE client_id = p_client_id AND resolved_at IS NULL;

  RETURN jsonb_build_object('current', COALESCE(v_latest, '{}'::jsonb), 'history', v_history, 'alerts', v_alerts);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;
