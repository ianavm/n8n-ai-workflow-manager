-- ============================================
-- 034: support_tickets shadow table
-- ============================================
-- Tickets live primarily in Airtable (Support base) and are synced into
-- this shadow table by an n8n workflow for fast portal queries.
-- Schema matches /api/admin/support upsert payload exactly.
-- ============================================

CREATE TABLE IF NOT EXISTS support_tickets (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id                TEXT UNIQUE NOT NULL,           -- Airtable record ID
    client_id                UUID REFERENCES clients(id) ON DELETE SET NULL,
    client_email             TEXT,
    subject                  TEXT,
    department               TEXT,                            -- e.g. "Customer_Support"
    priority                 TEXT NOT NULL DEFAULT 'P3'
                              CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    status                   TEXT NOT NULL DEFAULT 'Open'
                              CHECK (status IN ('Open', 'In Progress', 'Pending', 'Resolved', 'Closed')),
    ai_summary               TEXT,
    ai_suggested_resolution  TEXT,
    sla_due_at               TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at              TIMESTAMPTZ,
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status     ON support_tickets (status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_priority   ON support_tickets (priority);
CREATE INDEX IF NOT EXISTS idx_support_tickets_client     ON support_tickets (client_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON support_tickets (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_sla_due    ON support_tickets (sla_due_at) WHERE status NOT IN ('Resolved', 'Closed');

ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY;

-- Both admin tiers can read; superior_admin sees the ticket meta but the
-- POPIA-deny policy for body content can be added later if needed (subject /
-- AI summary may contain client PII). Phase-1: allow both.
CREATE POLICY "admins_read_support_tickets" ON support_tickets
  FOR SELECT USING (current_admin_role() IN ('superior_admin', 'staff_admin'));

CREATE POLICY "admins_write_support_tickets" ON support_tickets
  FOR ALL USING (current_admin_role() IN ('superior_admin', 'staff_admin'))
  WITH CHECK (current_admin_role() IN ('superior_admin', 'staff_admin'));

-- Clients see only their own tickets (matched by client_email or client_id).
CREATE POLICY "clients_own_support_tickets" ON support_tickets
  FOR SELECT USING (
    client_id = (SELECT id FROM clients WHERE auth_user_id = auth.uid() LIMIT 1)
    OR client_email = (SELECT email FROM clients WHERE auth_user_id = auth.uid() LIMIT 1)
  );

-- POPIA gate: superior_admin sees ticket meta (counts, statuses, SLAs) but
-- not the per-ticket bodies / PII fields. Replace the read policy with a
-- restricted projection if/when needed; for now business_data_redacted
-- handling lives in the API layer.

-- updated_at trigger
CREATE OR REPLACE FUNCTION support_tickets_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_support_tickets_updated
  BEFORE UPDATE ON support_tickets
  FOR EACH ROW EXECUTE FUNCTION support_tickets_set_updated_at();
