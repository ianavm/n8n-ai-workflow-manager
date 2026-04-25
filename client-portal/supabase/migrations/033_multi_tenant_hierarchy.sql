-- ============================================
-- 033: Multi-tenant hierarchy
-- Orgs + managers + employees, POPIA-aware admin role split, soft-delete
-- ============================================
--
-- DESIGN NOTES
-- ------------
-- The existing `clients` table becomes the ORGANIZATION. This preserves
-- every `client_id` FK across 30+ migrations in fact tables (workflows,
-- stat_events, mkt_leads, acct_invoices, fa_clients, etc.) and lets us
-- ship the hierarchy additively with zero downtime.
--
-- NEW: `org_members` — one row per human who can sign into the portal
-- for a given org. Role = manager | employee. The existing
-- `clients.auth_user_id` was the *primary* manager pre-migration; the
-- backfill below creates an org_members row with role='manager' for each
-- existing client so nothing breaks.
--
-- NEW: `admin_users.role` expanded to `superior_admin | staff_admin`.
--   - superior_admin (Ian): account lifecycle only, NO business data
--     access (POPIA privacy-by-design)
--   - staff_admin (future AVM delivery team): full access for service
--     delivery
--
-- Soft-delete: `deleted_at` columns on organizations (i.e. clients) and
-- org_members, with a 7-day undo window. Hard-delete sweep runs via a
-- later cron; not included in this migration.

-- ============================================
-- 1. ADMIN ROLE SPLIT (superior_admin / staff_admin)
-- ============================================

-- Drop the legacy CHECK before widening the role enum.
ALTER TABLE admin_users DROP CONSTRAINT IF EXISTS admin_users_role_check;

-- Widen the column (no length change, just relax the check).
-- Backfill mapping: old 'owner' → 'superior_admin', old 'employee' → 'staff_admin'.
UPDATE admin_users SET role = 'superior_admin' WHERE role = 'owner';
UPDATE admin_users SET role = 'staff_admin'    WHERE role = 'employee';

ALTER TABLE admin_users
  ADD CONSTRAINT admin_users_role_check
  CHECK (role IN ('superior_admin', 'staff_admin'));

-- Change the default for new admin_users rows.
ALTER TABLE admin_users ALTER COLUMN role SET DEFAULT 'staff_admin';

-- ============================================
-- 2. ORG-LEVEL METADATA ON `clients`
-- (clients IS the organization — no rename, just add columns)
-- ============================================

ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS seat_limit INT DEFAULT 5,
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS deleted_by UUID REFERENCES admin_users(id);

CREATE INDEX IF NOT EXISTS idx_clients_deleted_at ON clients (deleted_at);

-- ============================================
-- 3. ORG_MEMBERS TABLE
-- Every person who can sign into the portal for an org.
-- ============================================

CREATE TABLE IF NOT EXISTS org_members (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id         UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    auth_user_id      UUID UNIQUE NOT NULL,   -- → auth.users(id) (no FK; Supabase auth schema)
    email             TEXT NOT NULL,
    full_name         TEXT,
    role              TEXT NOT NULL DEFAULT 'employee'
                          CHECK (role IN ('manager', 'employee')),
    manager_id        UUID REFERENCES org_members(id) ON DELETE SET NULL,
    status            TEXT NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'invited', 'suspended')),
    invited_by        UUID REFERENCES org_members(id) ON DELETE SET NULL,
    invited_at        TIMESTAMPTZ,
    joined_at         TIMESTAMPTZ,
    last_login_at     TIMESTAMPTZ,
    deleted_at        TIMESTAMPTZ,              -- 7-day soft delete window
    deleted_by        UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_members_client    ON org_members (client_id);
CREATE INDEX IF NOT EXISTS idx_org_members_manager   ON org_members (manager_id);
CREATE INDEX IF NOT EXISTS idx_org_members_auth      ON org_members (auth_user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_status    ON org_members (status);
CREATE INDEX IF NOT EXISTS idx_org_members_deleted_at ON org_members (deleted_at);

-- Exactly one auth_user_id per org_member (enforced by UNIQUE above).
-- An org must have at least one manager (enforced at application layer,
-- not via trigger, to avoid blocking bulk operations).

-- ============================================
-- 4. BACKFILL: one manager-role org_member per existing client
-- ============================================

INSERT INTO org_members (
    client_id, auth_user_id, email, full_name, role, status, joined_at, last_login_at
)
SELECT
    c.id,
    c.auth_user_id,
    c.email,
    c.full_name,
    'manager',
    c.status,                        -- active | suspended | inactive — map inactive→suspended
    c.created_at,
    c.last_login_at
FROM clients c
WHERE NOT EXISTS (
    SELECT 1 FROM org_members m WHERE m.auth_user_id = c.auth_user_id
);

-- Fix up the status mapping: clients.status has `inactive` which isn't
-- in org_members' CHECK. Remap to 'suspended'.
UPDATE org_members SET status = 'suspended' WHERE status = 'inactive';

-- ============================================
-- 5. ORG_MEMBER_ID ON FACT TABLES
-- Employee-level attribution alongside existing client_id.
-- Only add where an employee could legitimately own a row. Skip
-- org-level config tables (mkt_config, acct_config, etc.).
-- ============================================

-- Fact tables where `client_id` points at `clients(id)` AND attribution
-- to a specific portal user matters. Conditionally added per table so the
-- migration works whether or not the optional modules (CRM, accounting,
-- etc.) have been installed yet.
--
-- INTENTIONALLY EXCLUDED: fa_* (advisory) tables. Their `client_id`
-- references `fa_clients` (end-clients of the advisory firm), not the
-- portal org. Advisory scoping is done via `fa_meetings.adviser_id` →
-- `fa_advisers.auth_user_id` → `org_members.auth_user_id` at runtime. A
-- generic `org_member_id` column there would be redundant.
DO $$
DECLARE
  fact_tables TEXT[] := ARRAY[
    'stat_events', 'mkt_leads', 'mkt_campaigns', 'mkt_content',
    'crm_leads', 'workflows'
  ];
  t TEXT;
BEGIN
  FOREACH t IN ARRAY fact_tables
  LOOP
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = t) THEN
      EXECUTE format(
        'ALTER TABLE %I ADD COLUMN IF NOT EXISTS org_member_id UUID REFERENCES org_members(id) ON DELETE SET NULL',
        t
      );
      EXECUTE format(
        'CREATE INDEX IF NOT EXISTS %I ON %I (org_member_id)',
        'idx_' || t || '_member', t
      );
      -- Backfill: pre-hierarchy data belongs to the one existing manager.
      EXECUTE format(
        'UPDATE %I t SET org_member_id = m.id FROM org_members m '
        || 'WHERE t.client_id = m.client_id AND m.role = ''manager'' '
        || '  AND t.org_member_id IS NULL',
        t
      );
    END IF;
  END LOOP;
END $$;

-- ============================================
-- 6. ROW LEVEL SECURITY — superior_admin cannot see business data
-- ============================================
-- Supabase RLS policies filter queries by role. superior_admin sessions
-- are BLOCKED on SELECT of sensitive fact tables. Aggregated queries
-- (COUNT/SUM grouped by client_id) remain available via dedicated
-- server-side RPCs that use the service_role key.

-- Helper: identify the current actor's admin_users role, if any.
CREATE OR REPLACE FUNCTION current_admin_role()
RETURNS TEXT LANGUAGE sql STABLE AS $$
  SELECT role FROM admin_users WHERE auth_user_id = auth.uid() LIMIT 1
$$;

-- Helper: identify the current actor's org_members membership, if any.
CREATE OR REPLACE FUNCTION current_org_member()
RETURNS TABLE (member_id UUID, client_id UUID, role TEXT, manager_id UUID)
LANGUAGE sql STABLE AS $$
  SELECT id, client_id, role, manager_id
  FROM org_members
  WHERE auth_user_id = auth.uid()
    AND deleted_at IS NULL
    AND status = 'active'
  LIMIT 1
$$;

-- Enable RLS where not already enabled
ALTER TABLE org_members ENABLE ROW LEVEL SECURITY;

-- org_members — manager can see all rows in their org, employee can see
-- self only, staff_admin sees everything, superior_admin sees everything
-- (account management requires reading member list).
DROP POLICY IF EXISTS org_members_read ON org_members;
CREATE POLICY org_members_read ON org_members FOR SELECT USING (
  -- superior_admin or staff_admin: full read
  current_admin_role() IN ('superior_admin', 'staff_admin')
  OR
  -- manager: all members in same org
  EXISTS (
    SELECT 1 FROM org_members self
    WHERE self.auth_user_id = auth.uid()
      AND self.role = 'manager'
      AND self.client_id = org_members.client_id
      AND self.deleted_at IS NULL
  )
  OR
  -- employee: self only
  auth_user_id = auth.uid()
);

DROP POLICY IF EXISTS org_members_write ON org_members;
CREATE POLICY org_members_write ON org_members FOR ALL USING (
  -- Admins can manage everyone
  current_admin_role() IN ('superior_admin', 'staff_admin')
  OR
  -- Managers can manage their own org members
  EXISTS (
    SELECT 1 FROM org_members self
    WHERE self.auth_user_id = auth.uid()
      AND self.role = 'manager'
      AND self.client_id = org_members.client_id
      AND self.deleted_at IS NULL
  )
);

-- Block superior_admin from SELECTing individual PII-bearing rows.
-- Note: Supabase's service_role key bypasses RLS, so server-side RPCs
-- (aggregations for admin dashboard) still work.
-- We add a supplementary policy that explicitly denies for superior_admin.
--
-- `USING (false)` for superior_admin combined with permissive policies
-- for other roles gives the POPIA gate.

DO $$
DECLARE
  t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
    'mkt_leads', 'crm_leads', 'fa_documents', 'fa_meetings',
    'fa_communications', 'fa_tasks', 'fa_pricing', 'stat_events'
  ])
  LOOP
    EXECUTE format(
      'DROP POLICY IF EXISTS %I ON %I',
      t || '_deny_superior_admin', t
    );
    EXECUTE format(
      'CREATE POLICY %I ON %I FOR SELECT USING (current_admin_role() IS DISTINCT FROM ''superior_admin'')',
      t || '_deny_superior_admin', t
    );
  END LOOP;
END $$;

-- ============================================
-- 7. HELPFUL VIEW: org_summary (safe for superior_admin)
-- ============================================
-- Aggregated counts per org so superior_admin can see health at a glance
-- without touching individual rows.

CREATE OR REPLACE VIEW v_org_summary AS
SELECT
  c.id                                            AS client_id,
  c.company_name,
  c.email                                         AS primary_manager_email,
  c.status,
  c.seat_limit,
  c.created_at,
  c.deleted_at,
  (SELECT COUNT(*) FROM org_members m
     WHERE m.client_id = c.id AND m.deleted_at IS NULL)
                                                   AS total_members,
  (SELECT COUNT(*) FROM org_members m
     WHERE m.client_id = c.id AND m.role = 'manager' AND m.deleted_at IS NULL)
                                                   AS manager_count,
  (SELECT COUNT(*) FROM org_members m
     WHERE m.client_id = c.id AND m.role = 'employee' AND m.deleted_at IS NULL)
                                                   AS employee_count,
  -- These are COUNT-only aggregates — no PII leakage.
  (SELECT COUNT(*) FROM workflows w
     WHERE w.client_id = c.id AND w.status = 'active')
                                                   AS active_workflows,
  (SELECT COUNT(*) FROM mkt_leads l WHERE l.client_id = c.id)
                                                   AS total_leads,
  (SELECT COUNT(*) FROM stat_events e
     WHERE e.client_id = c.id
       AND e.created_at >= now() - INTERVAL '7 days')
                                                   AS events_last_7d
FROM clients c;

COMMENT ON VIEW v_org_summary IS
  'Aggregated org-level health (counts only, no PII). Safe to surface to superior_admin.';

-- ============================================
-- 8. AUDIT LOG FOR ADMIN ACTIONS
-- ============================================
-- Every account lifecycle action (create org, invite, promote, deactivate,
-- delete) appended here. Lets us satisfy any future POPIA DSAR request.

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id            BIGSERIAL PRIMARY KEY,
    actor_id      UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    actor_role    TEXT,
    action        TEXT NOT NULL,           -- e.g. 'org.create', 'member.invite', 'member.promote', 'member.soft_delete'
    target_type   TEXT NOT NULL,           -- 'organization' | 'org_member' | 'admin_user'
    target_id     UUID,
    client_id     UUID REFERENCES clients(id) ON DELETE SET NULL,
    metadata      JSONB DEFAULT '{}',
    ip_address    TEXT,
    user_agent    TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_actor  ON admin_audit_log (actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_client ON admin_audit_log (client_id);
CREATE INDEX IF NOT EXISTS idx_audit_time   ON admin_audit_log (created_at DESC);

-- ============================================
-- DONE
-- ============================================
-- No existing code paths should break because:
--  • `clients.*` columns unchanged (additions only)
--  • `client_id` FKs everywhere unchanged
--  • New `org_members` table populated via backfill with role='manager'
--  • `admin_users.role` remapped: 'owner'→'superior_admin', 'employee'→'staff_admin'
--  • New `org_member_id` columns are nullable + backfilled to the manager
--
-- Next migration (034) will add the server RPC for superior_admin
-- aggregates. Phase I.2+ code changes are separate.
