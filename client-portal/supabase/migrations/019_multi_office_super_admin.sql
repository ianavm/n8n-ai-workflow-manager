-- ============================================================
-- Migration 019: Multi-Office Support + Per-Adviser Dashboards
-- Adds super_admin role, cross-office RPCs, adviser dashboard
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- 1. Add super_admin role to fa_advisers
-- ────────────────────────────────────────────────────────────
ALTER TABLE fa_advisers DROP CONSTRAINT IF EXISTS fa_advisers_role_check;
ALTER TABLE fa_advisers ADD CONSTRAINT fa_advisers_role_check
  CHECK (role IN ('adviser', 'compliance_officer', 'admin', 'office_manager', 'super_admin'));

-- ────────────────────────────────────────────────────────────
-- 2. Super admin check helper
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fa_is_super_admin() RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM fa_advisers
    WHERE auth_user_id = (SELECT auth.uid())
    AND role = 'super_admin' AND active = true
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ────────────────────────────────────────────────────────────
-- 3. Per-adviser dashboard RPC
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fa_get_adviser_dashboard(p_adviser_id UUID)
RETURNS JSONB AS $$
  SELECT jsonb_build_object(
    'my_clients', (SELECT count(*) FROM fa_adviser_clients WHERE adviser_id = p_adviser_id),
    'upcoming_meetings', (SELECT count(*) FROM fa_meetings WHERE adviser_id = p_adviser_id AND status IN ('scheduled','confirmed') AND scheduled_at > now()),
    'pending_tasks', (SELECT count(*) FROM fa_tasks WHERE assigned_to = p_adviser_id AND status IN ('pending','in_progress')),
    'overdue_tasks', (SELECT count(*) FROM fa_tasks WHERE assigned_to = p_adviser_id AND due_date < now() AND status NOT IN ('completed','cancelled')),
    'meetings_this_week', (SELECT count(*) FROM fa_meetings WHERE adviser_id = p_adviser_id AND scheduled_at > date_trunc('week', now()) AND scheduled_at < date_trunc('week', now()) + interval '7 days'),
    'meetings_completed_this_month', (SELECT count(*) FROM fa_meetings WHERE adviser_id = p_adviser_id AND status = 'completed' AND ended_at > date_trunc('month', now())),
    'pipeline_summary', (
      SELECT jsonb_object_agg(pipeline_stage, cnt) FROM (
        SELECT fc.pipeline_stage, count(*) as cnt
        FROM fa_clients fc
        JOIN fa_adviser_clients fac ON fac.client_id = fc.id
        WHERE fac.adviser_id = p_adviser_id
        GROUP BY fc.pipeline_stage
      ) sub
    )
  );
$$ LANGUAGE sql SECURITY DEFINER;

-- ────────────────────────────────────────────────────────────
-- 4. Cross-office summary RPC (super_admin only)
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fa_get_all_offices_summary()
RETURNS TABLE (
  firm_id UUID,
  firm_name TEXT,
  total_advisers BIGINT,
  total_clients BIGINT,
  active_clients BIGINT,
  meetings_this_month BIGINT,
  compliance_score BIGINT
) AS $$
  SELECT
    f.id,
    f.firm_name,
    (SELECT count(*) FROM fa_advisers WHERE firm_id = f.id AND active = true),
    (SELECT count(*) FROM fa_clients WHERE firm_id = f.id),
    (SELECT count(*) FROM fa_clients WHERE firm_id = f.id AND pipeline_stage NOT IN ('lead','inactive')),
    (SELECT count(*) FROM fa_meetings WHERE firm_id = f.id AND created_at > date_trunc('month', now())),
    -- compliance score: percentage of clients with POPIA consent
    CASE
      WHEN (SELECT count(*) FROM fa_clients WHERE firm_id = f.id AND pipeline_stage != 'inactive') = 0 THEN 100
      ELSE (
        SELECT (count(DISTINCT cr.client_id) * 100) / GREATEST(count(DISTINCT c.id), 1)
        FROM fa_clients c
        LEFT JOIN fa_consent_records cr ON cr.client_id = c.id AND cr.consent_type = 'popia_processing' AND cr.granted = true AND cr.revoked_at IS NULL
        WHERE c.firm_id = f.id AND c.pipeline_stage != 'inactive'
      )
    END
  FROM fa_firms f
  ORDER BY f.firm_name;
$$ LANGUAGE sql SECURITY DEFINER;
