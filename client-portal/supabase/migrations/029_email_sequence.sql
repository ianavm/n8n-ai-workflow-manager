-- Migration 029: Email sequence tracking + RPC for pending emails
-- See tools/deploy_onboarding_emails.py for the n8n workflow

CREATE TABLE IF NOT EXISTS email_sequence_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    email_key TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    opened_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_email_seq_client ON email_sequence_events(client_id, email_key);

ALTER TABLE email_sequence_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "admin_all_email_seq" ON email_sequence_events
    FOR ALL USING (EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid()));

CREATE POLICY "service_email_seq" ON email_sequence_events
    FOR ALL USING (auth.role() = 'service_role');

-- RPC function: find clients who need onboarding emails
CREATE OR REPLACE FUNCTION get_pending_onboarding_emails()
RETURNS TABLE (
    client_id UUID,
    email TEXT,
    first_name TEXT,
    company_name TEXT,
    email_key TEXT,
    extra JSONB
) AS $$
BEGIN
  -- Email 2: day1_checklist (24h after signup, onboarding not complete)
  RETURN QUERY
  SELECT c.id, c.email, split_part(c.full_name, ' ', 1) AS first_name,
         c.company_name, 'day1_checklist'::TEXT AS email_key, '{}'::JSONB AS extra
  FROM clients c
  WHERE c.created_at < now() - interval '24 hours'
    AND c.created_at > now() - interval '48 hours'
    AND c.onboarding_completed_at IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM email_sequence_events e
      WHERE e.client_id = c.id AND e.email_key = 'day1_checklist'
    );

  -- Email 4: day3_nudge (72h, no integration)
  RETURN QUERY
  SELECT c.id, c.email, split_part(c.full_name, ' ', 1), c.company_name,
         'day3_nudge'::TEXT, '{}'::JSONB
  FROM clients c
  WHERE c.created_at < now() - interval '72 hours'
    AND c.created_at > now() - interval '96 hours'
    AND NOT EXISTS (
      SELECT 1 FROM oauth_connections oc WHERE oc.client_id = c.id AND oc.status = 'connected'
    )
    AND NOT EXISTS (
      SELECT 1 FROM email_sequence_events e WHERE e.client_id = c.id AND e.email_key = 'day3_nudge'
    );

  -- Email 6: day7_value
  RETURN QUERY
  SELECT c.id, c.email, split_part(c.full_name, ' ', 1), c.company_name,
         'day7_value'::TEXT,
         jsonb_build_object(
           'leads', COALESCE((SELECT count(*) FROM stat_events se WHERE se.client_id = c.id AND se.event_type = 'lead_created'), 0),
           'hours_saved', 0,
           'workflows_run', COALESCE((SELECT count(*) FROM stat_events se WHERE se.client_id = c.id AND se.event_type IN ('workflow_success', 'message_sent')), 0),
           'messages_sent', COALESCE((SELECT count(*) FROM stat_events se WHERE se.client_id = c.id AND se.event_type = 'message_sent'), 0)
         )
  FROM clients c
  WHERE c.created_at < now() - interval '7 days'
    AND c.created_at > now() - interval '8 days'
    AND NOT EXISTS (
      SELECT 1 FROM email_sequence_events e WHERE e.client_id = c.id AND e.email_key = 'day7_value'
    );

  -- Email 7: trial_ending (5 days before trial end)
  RETURN QUERY
  SELECT c.id, c.email, split_part(c.full_name, ' ', 1), c.company_name,
         'trial_ending'::TEXT, '{}'::JSONB
  FROM clients c
  JOIN subscriptions s ON s.client_id = c.id
  WHERE s.status = 'trialing'
    AND s.trial_end BETWEEN now() + interval '4 days' AND now() + interval '6 days'
    AND NOT EXISTS (
      SELECT 1 FROM email_sequence_events e WHERE e.client_id = c.id AND e.email_key = 'trial_ending'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
