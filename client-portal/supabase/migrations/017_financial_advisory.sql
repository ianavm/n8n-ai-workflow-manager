-- ============================================================
-- Migration 017: Financial Advisory CRM
-- 16 tables, RLS policies, audit triggers, seed data, RPCs
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- 1. fa_firms — Multi-tenant advisory firm isolation
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_firms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_name TEXT NOT NULL,
  fsp_number TEXT UNIQUE,
  trading_name TEXT,
  registration_number TEXT,
  contact_email TEXT NOT NULL,
  contact_phone TEXT,
  physical_address JSONB,
  postal_address JSONB,
  logo_url TEXT,
  config JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE fa_firms ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 2. fa_product_types — Lookup (seeded below)
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_product_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN (
    'life_insurance', 'short_term_insurance', 'medical_aid',
    'retirement', 'investment', 'savings', 'estate_planning',
    'tax', 'debt', 'other'
  )),
  provider_options JSONB DEFAULT '[]',
  requires_license TEXT[] DEFAULT '{}',
  is_active BOOLEAN NOT NULL DEFAULT true,
  sort_order INTEGER DEFAULT 0
);

ALTER TABLE fa_product_types ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 3. fa_fee_structures — Lookup (seeded below)
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_fee_structures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL CHECK (type IN ('commission', 'fee_based', 'hybrid')),
  name TEXT NOT NULL,
  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true
);

ALTER TABLE fa_fee_structures ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 4. fa_advisers — Staff linked to auth.users
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_advisers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT NOT NULL,
  phone TEXT,
  license_number TEXT,
  fsp_number TEXT,
  specializations TEXT[] DEFAULT '{}',
  role TEXT NOT NULL DEFAULT 'adviser'
    CHECK (role IN ('adviser', 'compliance_officer', 'admin')),
  microsoft_user_id TEXT,
  outlook_calendar_id TEXT,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_advisers_firm ON fa_advisers(firm_id);
CREATE INDEX idx_fa_advisers_auth ON fa_advisers(auth_user_id);

ALTER TABLE fa_advisers ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 5. fa_clients — Full client profile
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  portal_client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
  -- Personal
  title TEXT CHECK (title IN ('Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'Adv')),
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  id_number TEXT,
  date_of_birth DATE,
  gender TEXT CHECK (gender IN ('male', 'female', 'other', 'prefer_not_to_say')),
  marital_status TEXT CHECK (marital_status IN (
    'single', 'married_in_community', 'married_out_community',
    'married_accrual', 'divorced', 'widowed', 'life_partner'
  )),
  nationality TEXT DEFAULT 'South African',
  -- Contact
  email TEXT NOT NULL,
  phone TEXT,
  mobile TEXT,
  physical_address JSONB,
  postal_address JSONB,
  -- Employment
  employer TEXT,
  occupation TEXT,
  industry TEXT,
  employment_status TEXT CHECK (employment_status IN (
    'employed', 'self_employed', 'unemployed', 'retired', 'student'
  )),
  gross_monthly_income INTEGER DEFAULT 0,
  net_monthly_income INTEGER DEFAULT 0,
  -- Financial (all in cents, ZAR)
  total_assets INTEGER DEFAULT 0,
  total_liabilities INTEGER DEFAULT 0,
  monthly_expenses INTEGER DEFAULT 0,
  monthly_surplus INTEGER DEFAULT 0,
  tax_number TEXT,
  tax_residency TEXT DEFAULT 'ZA',
  -- Risk
  risk_tolerance TEXT DEFAULT 'moderate'
    CHECK (risk_tolerance IN (
      'conservative', 'moderately_conservative', 'moderate',
      'moderately_aggressive', 'aggressive'
    )),
  risk_assessment_date TIMESTAMPTZ,
  investment_horizon TEXT CHECK (investment_horizon IN (
    'short_term', 'medium_term', 'long_term'
  )),
  -- FICA
  fica_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (fica_status IN ('pending', 'partial', 'verified', 'expired')),
  fica_verified_at TIMESTAMPTZ,
  fica_documents JSONB DEFAULT '[]',
  -- Pipeline
  pipeline_stage TEXT NOT NULL DEFAULT 'lead'
    CHECK (pipeline_stage IN (
      'lead', 'contacted', 'intake_complete', 'discovery_scheduled',
      'discovery_complete', 'analysis', 'presentation_scheduled',
      'presentation_complete', 'implementation', 'active', 'inactive'
    )),
  pipeline_updated_at TIMESTAMPTZ DEFAULT now(),
  health_score INTEGER DEFAULT 50,
  source TEXT,
  referred_by UUID REFERENCES fa_clients(id) ON DELETE SET NULL,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_clients_firm ON fa_clients(firm_id);
CREATE INDEX idx_fa_clients_pipeline ON fa_clients(firm_id, pipeline_stage);
CREATE INDEX idx_fa_clients_email ON fa_clients(email);
CREATE INDEX idx_fa_clients_portal ON fa_clients(portal_client_id);

ALTER TABLE fa_clients ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 6. fa_adviser_clients — Assignment junction
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_adviser_clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  adviser_id UUID NOT NULL REFERENCES fa_advisers(id) ON DELETE CASCADE,
  client_id UUID NOT NULL REFERENCES fa_clients(id) ON DELETE CASCADE,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'primary'
    CHECK (role IN ('primary', 'secondary', 'introduced_by')),
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (adviser_id, client_id)
);

ALTER TABLE fa_adviser_clients ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 7. fa_dependents
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_dependents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES fa_clients(id) ON DELETE CASCADE,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  relationship TEXT NOT NULL
    CHECK (relationship IN ('spouse', 'child', 'parent', 'sibling', 'other')),
  date_of_birth DATE,
  id_number TEXT,
  is_beneficiary BOOLEAN DEFAULT false,
  beneficiary_percentage NUMERIC(5,2),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_dependents_client ON fa_dependents(client_id);

ALTER TABLE fa_dependents ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 8. fa_client_products — Existing financial products
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_client_products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES fa_clients(id) ON DELETE CASCADE,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  product_type_id UUID REFERENCES fa_product_types(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  policy_number TEXT,
  product_name TEXT NOT NULL,
  category TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'lapsed', 'paid_up', 'claimed', 'cancelled', 'pending')),
  premium_amount INTEGER DEFAULT 0,
  premium_frequency TEXT CHECK (premium_frequency IN (
    'monthly', 'quarterly', 'annually', 'single_premium'
  )),
  cover_amount INTEGER DEFAULT 0,
  inception_date DATE,
  maturity_date DATE,
  review_date DATE,
  beneficiaries JSONB DEFAULT '[]',
  details JSONB DEFAULT '{}',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_products_client ON fa_client_products(client_id);

ALTER TABLE fa_client_products ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 9. fa_meetings — Two-meeting advice process
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_meetings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES fa_clients(id) ON DELETE CASCADE,
  adviser_id UUID NOT NULL REFERENCES fa_advisers(id) ON DELETE CASCADE,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  meeting_type TEXT NOT NULL
    CHECK (meeting_type IN ('discovery', 'presentation', 'review', 'follow_up', 'ad_hoc')),
  status TEXT NOT NULL DEFAULT 'scheduled'
    CHECK (status IN (
      'scheduled', 'confirmed', 'in_progress', 'completed',
      'cancelled', 'no_show', 'rescheduled'
    )),
  title TEXT NOT NULL,
  description TEXT,
  scheduled_at TIMESTAMPTZ NOT NULL,
  duration_minutes INTEGER NOT NULL DEFAULT 60,
  ended_at TIMESTAMPTZ,
  -- Microsoft integration
  outlook_event_id TEXT,
  teams_meeting_url TEXT,
  teams_meeting_id TEXT,
  -- Recording & transcript
  recording_url TEXT,
  recording_status TEXT DEFAULT 'none'
    CHECK (recording_status IN ('none', 'pending', 'processing', 'available', 'failed')),
  transcript_raw TEXT,
  transcript_status TEXT DEFAULT 'none'
    CHECK (transcript_status IN ('none', 'pending', 'processing', 'available', 'failed')),
  -- Location
  location_type TEXT NOT NULL DEFAULT 'online'
    CHECK (location_type IN ('online', 'in_person', 'phone')),
  location_details TEXT,
  -- Reminders
  reminder_24h_sent BOOLEAN NOT NULL DEFAULT false,
  reminder_1h_sent BOOLEAN NOT NULL DEFAULT false,
  -- Compliance
  disclosure_sent BOOLEAN NOT NULL DEFAULT false,
  disclosure_sent_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_meetings_client ON fa_meetings(client_id);
CREATE INDEX idx_fa_meetings_adviser ON fa_meetings(adviser_id);
CREATE INDEX idx_fa_meetings_scheduled ON fa_meetings(scheduled_at);
CREATE INDEX idx_fa_meetings_status ON fa_meetings(firm_id, status);

ALTER TABLE fa_meetings ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 10. fa_meeting_insights — AI-extracted analysis
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_meeting_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  meeting_id UUID NOT NULL UNIQUE REFERENCES fa_meetings(id) ON DELETE CASCADE,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  summary TEXT,
  priorities JSONB DEFAULT '[]',
  objections JSONB DEFAULT '[]',
  action_items JSONB DEFAULT '[]',
  compliance_flags JSONB DEFAULT '[]',
  research_needs JSONB DEFAULT '[]',
  client_sentiment TEXT CHECK (client_sentiment IN (
    'positive', 'neutral', 'concerned', 'negative'
  )),
  key_quotes JSONB DEFAULT '[]',
  next_steps TEXT,
  risk_tolerance_indicated TEXT,
  ai_model TEXT,
  ai_confidence NUMERIC(3,2),
  reviewed_by UUID REFERENCES fa_advisers(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE fa_meeting_insights ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 11. fa_tasks
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  client_id UUID REFERENCES fa_clients(id) ON DELETE CASCADE,
  meeting_id UUID REFERENCES fa_meetings(id) ON DELETE SET NULL,
  assigned_to UUID REFERENCES fa_advisers(id) ON DELETE SET NULL,
  created_by UUID,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'in_progress', 'waiting', 'completed', 'cancelled')),
  priority TEXT NOT NULL DEFAULT 'medium'
    CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
  source TEXT DEFAULT 'manual'
    CHECK (source IN ('meeting', 'manual', 'system', 'compliance', 'ai_extracted')),
  category TEXT,
  due_date TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_tasks_assigned ON fa_tasks(assigned_to);
CREATE INDEX idx_fa_tasks_client ON fa_tasks(client_id);
CREATE INDEX idx_fa_tasks_overdue ON fa_tasks(due_date)
  WHERE status NOT IN ('completed', 'cancelled');

ALTER TABLE fa_tasks ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 12. fa_documents
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  client_id UUID NOT NULL REFERENCES fa_clients(id) ON DELETE CASCADE,
  meeting_id UUID REFERENCES fa_meetings(id) ON DELETE SET NULL,
  uploaded_by UUID,
  uploaded_by_role TEXT CHECK (uploaded_by_role IN ('adviser', 'client', 'system')),
  file_name TEXT NOT NULL,
  file_type TEXT,
  file_size INTEGER,
  storage_path TEXT NOT NULL,
  storage_url TEXT,
  document_type TEXT NOT NULL
    CHECK (document_type IN (
      'id_document', 'proof_of_address', 'bank_statement', 'payslip',
      'tax_return', 'policy_schedule', 'record_of_advice', 'disclosure',
      'mandate', 'quotation', 'application_form', 'needs_analysis',
      'risk_assessment', 'meeting_summary', 'correspondence', 'other'
    )),
  classified_as TEXT,
  classification_confidence NUMERIC(3,2),
  is_signed BOOLEAN DEFAULT false,
  signed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_documents_client ON fa_documents(client_id);

ALTER TABLE fa_documents ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 13. fa_pricing — Versioned fee agreements (FAIS audit)
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_pricing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES fa_clients(id) ON DELETE CASCADE,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  adviser_id UUID NOT NULL REFERENCES fa_advisers(id) ON DELETE CASCADE,
  product_type TEXT,
  fee_structure_id UUID REFERENCES fa_fee_structures(id) ON DELETE SET NULL,
  fee_type TEXT NOT NULL
    CHECK (fee_type IN (
      'initial_commission', 'ongoing_commission', 'advice_fee',
      'flat_fee', 'hourly_fee', 'assets_under_management'
    )),
  amount INTEGER DEFAULT 0,
  percentage NUMERIC(5,2),
  description TEXT,
  -- Versioning
  version INTEGER NOT NULL DEFAULT 1,
  previous_version_id UUID REFERENCES fa_pricing(id) ON DELETE SET NULL,
  change_reason TEXT,
  -- Approval flow
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN (
      'draft', 'pending_approval', 'approved', 'accepted', 'rejected', 'superseded'
    )),
  approved_by UUID REFERENCES fa_advisers(id) ON DELETE SET NULL,
  approved_at TIMESTAMPTZ,
  accepted_by_client BOOLEAN DEFAULT false,
  accepted_at TIMESTAMPTZ,
  locked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_pricing_client ON fa_pricing(client_id);

ALTER TABLE fa_pricing ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 14. fa_consent_records — POPIA + FAIS
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_consent_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES fa_clients(id) ON DELETE CASCADE,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  consent_type TEXT NOT NULL
    CHECK (consent_type IN (
      'popia_processing', 'popia_marketing', 'popia_third_party',
      'fais_disclosure', 'fais_needs_analysis', 'fais_record_of_advice',
      'recording_consent', 'electronic_communication', 'terms_of_engagement'
    )),
  granted BOOLEAN NOT NULL,
  granted_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  revoked_reason TEXT,
  ip_address TEXT,
  user_agent TEXT,
  method TEXT CHECK (method IN ('electronic', 'written', 'verbal')),
  document_id UUID REFERENCES fa_documents(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_consent_client ON fa_consent_records(client_id);
CREATE INDEX idx_fa_consent_expiry ON fa_consent_records(expires_at)
  WHERE revoked_at IS NULL AND granted = true;

ALTER TABLE fa_consent_records ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 15. fa_communications — All channel logging
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_communications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES fa_clients(id) ON DELETE CASCADE,
  firm_id UUID NOT NULL REFERENCES fa_firms(id) ON DELETE CASCADE,
  adviser_id UUID REFERENCES fa_advisers(id) ON DELETE SET NULL,
  meeting_id UUID REFERENCES fa_meetings(id) ON DELETE SET NULL,
  channel TEXT NOT NULL
    CHECK (channel IN ('email', 'whatsapp', 'teams', 'phone', 'sms', 'in_person', 'portal')),
  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  subject TEXT,
  content TEXT,
  content_html TEXT,
  -- Email specifics
  outlook_message_id TEXT,
  email_from TEXT,
  email_to TEXT[],
  -- WhatsApp specifics
  whatsapp_message_id TEXT,
  whatsapp_template TEXT,
  -- Status
  status TEXT NOT NULL DEFAULT 'sent'
    CHECK (status IN ('draft', 'queued', 'sent', 'delivered', 'read', 'failed', 'bounced')),
  sent_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_comms_client ON fa_communications(client_id, created_at DESC);

ALTER TABLE fa_communications ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────
-- 16. fa_audit_log — Immutable append-only
-- ────────────────────────────────────────────────────────────
CREATE TABLE fa_audit_log (
  id BIGSERIAL PRIMARY KEY,
  firm_id UUID REFERENCES fa_firms(id) ON DELETE SET NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  action TEXT NOT NULL
    CHECK (action IN (
      'created', 'updated', 'deleted', 'viewed', 'exported',
      'consent_granted', 'consent_revoked',
      'fee_changed', 'fee_accepted', 'fee_locked',
      'meeting_booked', 'meeting_completed', 'meeting_cancelled',
      'document_uploaded', 'document_signed',
      'compliance_report_generated', 'weekly_report_generated'
    )),
  old_value JSONB,
  new_value JSONB,
  performed_by UUID,
  performed_by_type TEXT CHECK (performed_by_type IN (
    'adviser', 'client', 'system', 'n8n_workflow'
  )),
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fa_audit_entity ON fa_audit_log(entity_type, entity_id);
CREATE INDEX idx_fa_audit_firm ON fa_audit_log(firm_id, created_at DESC);

ALTER TABLE fa_audit_log ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- HELPER FUNCTIONS FOR RLS
-- ============================================================

-- Returns the firm_id for the current authenticated user
CREATE OR REPLACE FUNCTION fa_get_user_firm_id()
RETURNS UUID AS $$
  SELECT COALESCE(
    -- Check fa_advisers first
    (SELECT firm_id FROM fa_advisers
     WHERE auth_user_id = (SELECT auth.uid()) LIMIT 1),
    -- Then check portal clients linked to fa_clients
    (SELECT fc.firm_id FROM fa_clients fc
     JOIN clients c ON c.id = fc.portal_client_id
     WHERE c.auth_user_id = (SELECT auth.uid()) LIMIT 1)
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Check if current user is an adviser
CREATE OR REPLACE FUNCTION fa_is_adviser()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM fa_advisers
    WHERE auth_user_id = (SELECT auth.uid()) AND active = true
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Check if current user is the portal client for a given fa_client_id
CREATE OR REPLACE FUNCTION fa_is_portal_client(p_client_id UUID)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM fa_clients fc
    JOIN clients c ON c.id = fc.portal_client_id
    WHERE fc.id = p_client_id AND c.auth_user_id = (SELECT auth.uid())
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Check if current user is an admin_user (backwards compat)
CREATE OR REPLACE FUNCTION fa_is_admin()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM admin_users
    WHERE auth_user_id = (SELECT auth.uid())
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;


-- ============================================================
-- RLS POLICIES
-- ============================================================

-- ── fa_firms ───────────────────────────────────────────────
CREATE POLICY "advisers_firms_select" ON fa_firms FOR SELECT
  USING (id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "admin_firms_all" ON fa_firms FOR ALL
  USING (fa_is_admin());

-- ── fa_product_types (public read) ─────────────────────────
CREATE POLICY "anyone_product_types_select" ON fa_product_types FOR SELECT
  USING (true);
CREATE POLICY "admin_product_types_all" ON fa_product_types FOR ALL
  USING (fa_is_admin());

-- ── fa_fee_structures (public read) ────────────────────────
CREATE POLICY "anyone_fee_structures_select" ON fa_fee_structures FOR SELECT
  USING (true);
CREATE POLICY "admin_fee_structures_all" ON fa_fee_structures FOR ALL
  USING (fa_is_admin());

-- ── fa_advisers ────────────────────────────────────────────
CREATE POLICY "advisers_own_firm" ON fa_advisers FOR SELECT
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "admin_advisers_all" ON fa_advisers FOR ALL
  USING (fa_is_admin());

-- ── fa_clients ─────────────────────────────────────────────
CREATE POLICY "advisers_clients_select" ON fa_clients FOR SELECT
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "advisers_clients_insert" ON fa_clients FOR INSERT
  WITH CHECK (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "advisers_clients_update" ON fa_clients FOR UPDATE
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_clients_own" ON fa_clients FOR SELECT
  USING (fa_is_portal_client(id));
CREATE POLICY "portal_clients_update_own" ON fa_clients FOR UPDATE
  USING (fa_is_portal_client(id));

-- ── fa_adviser_clients ─────────────────────────────────────
CREATE POLICY "advisers_assignments_select" ON fa_adviser_clients FOR SELECT
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "advisers_assignments_insert" ON fa_adviser_clients FOR INSERT
  WITH CHECK (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "advisers_assignments_update" ON fa_adviser_clients FOR UPDATE
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "advisers_assignments_delete" ON fa_adviser_clients FOR DELETE
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());

-- ── fa_dependents ──────────────────────────────────────────
CREATE POLICY "advisers_dependents_all" ON fa_dependents FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_dependents_select" ON fa_dependents FOR SELECT
  USING (fa_is_portal_client(client_id));
CREATE POLICY "portal_dependents_insert" ON fa_dependents FOR INSERT
  WITH CHECK (fa_is_portal_client(client_id));
CREATE POLICY "portal_dependents_update" ON fa_dependents FOR UPDATE
  USING (fa_is_portal_client(client_id));

-- ── fa_client_products ─────────────────────────────────────
CREATE POLICY "advisers_products_all" ON fa_client_products FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_products_select" ON fa_client_products FOR SELECT
  USING (fa_is_portal_client(client_id));

-- ── fa_meetings ────────────────────────────────────────────
CREATE POLICY "advisers_meetings_all" ON fa_meetings FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_meetings_select" ON fa_meetings FOR SELECT
  USING (fa_is_portal_client(client_id));

-- ── fa_meeting_insights ────────────────────────────────────
CREATE POLICY "advisers_insights_all" ON fa_meeting_insights FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_insights_select" ON fa_meeting_insights FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM fa_meetings m
    WHERE m.id = fa_meeting_insights.meeting_id
    AND fa_is_portal_client(m.client_id)
  ));

-- ── fa_tasks ───────────────────────────────────────────────
CREATE POLICY "advisers_tasks_all" ON fa_tasks FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_tasks_select" ON fa_tasks FOR SELECT
  USING (fa_is_portal_client(client_id));
CREATE POLICY "portal_tasks_update" ON fa_tasks FOR UPDATE
  USING (fa_is_portal_client(client_id));

-- ── fa_documents ───────────────────────────────────────────
CREATE POLICY "advisers_documents_all" ON fa_documents FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_documents_select" ON fa_documents FOR SELECT
  USING (fa_is_portal_client(client_id));
CREATE POLICY "portal_documents_insert" ON fa_documents FOR INSERT
  WITH CHECK (fa_is_portal_client(client_id));

-- ── fa_pricing ─────────────────────────────────────────────
CREATE POLICY "advisers_pricing_all" ON fa_pricing FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_pricing_select" ON fa_pricing FOR SELECT
  USING (fa_is_portal_client(client_id));
CREATE POLICY "portal_pricing_accept" ON fa_pricing FOR UPDATE
  USING (fa_is_portal_client(client_id));

-- ── fa_consent_records ─────────────────────────────────────
CREATE POLICY "advisers_consent_all" ON fa_consent_records FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_consent_select" ON fa_consent_records FOR SELECT
  USING (fa_is_portal_client(client_id));

-- ── fa_communications ──────────────────────────────────────
CREATE POLICY "advisers_comms_all" ON fa_communications FOR ALL
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
CREATE POLICY "portal_comms_select" ON fa_communications FOR SELECT
  USING (fa_is_portal_client(client_id));

-- ── fa_audit_log (advisers read, admins read) ──────────────
CREATE POLICY "advisers_audit_select" ON fa_audit_log FOR SELECT
  USING (firm_id = fa_get_user_firm_id() OR fa_is_admin());
-- INSERT allowed for service role only (triggers + n8n)


-- ============================================================
-- AUDIT TRIGGER FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION fa_audit_trigger_fn()
RETURNS TRIGGER AS $$
DECLARE
  v_performer_type TEXT;
BEGIN
  -- Determine performer type
  IF EXISTS (SELECT 1 FROM fa_advisers WHERE auth_user_id = (SELECT auth.uid())) THEN
    v_performer_type := 'adviser';
  ELSIF EXISTS (SELECT 1 FROM clients WHERE auth_user_id = (SELECT auth.uid())) THEN
    v_performer_type := 'client';
  ELSE
    v_performer_type := 'system';
  END IF;

  INSERT INTO fa_audit_log (
    firm_id, entity_type, entity_id, action,
    old_value, new_value, performed_by, performed_by_type
  ) VALUES (
    COALESCE(NEW.firm_id, OLD.firm_id),
    TG_TABLE_NAME,
    COALESCE(NEW.id, OLD.id)::UUID,
    CASE TG_OP
      WHEN 'INSERT' THEN 'created'
      WHEN 'UPDATE' THEN 'updated'
      WHEN 'DELETE' THEN 'deleted'
    END,
    CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) END,
    CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN to_jsonb(NEW) END,
    (SELECT auth.uid()),
    v_performer_type
  );

  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Apply audit trigger to mutable tables
CREATE TRIGGER fa_audit_clients
  AFTER INSERT OR UPDATE OR DELETE ON fa_clients
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_dependents
  AFTER INSERT OR UPDATE OR DELETE ON fa_dependents
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_products
  AFTER INSERT OR UPDATE OR DELETE ON fa_client_products
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_meetings
  AFTER INSERT OR UPDATE OR DELETE ON fa_meetings
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_insights
  AFTER INSERT OR UPDATE OR DELETE ON fa_meeting_insights
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_tasks
  AFTER INSERT OR UPDATE OR DELETE ON fa_tasks
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_documents
  AFTER INSERT OR UPDATE OR DELETE ON fa_documents
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_pricing
  AFTER INSERT OR UPDATE OR DELETE ON fa_pricing
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_consent
  AFTER INSERT OR UPDATE OR DELETE ON fa_consent_records
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();

CREATE TRIGGER fa_audit_comms
  AFTER INSERT OR UPDATE OR DELETE ON fa_communications
  FOR EACH ROW EXECUTE FUNCTION fa_audit_trigger_fn();


-- ============================================================
-- RPC FUNCTIONS
-- ============================================================

-- Dashboard aggregation for a client
CREATE OR REPLACE FUNCTION fa_get_client_dashboard(p_client_id UUID)
RETURNS JSONB AS $$
  SELECT jsonb_build_object(
    'upcoming_meetings', (
      SELECT count(*) FROM fa_meetings
      WHERE client_id = p_client_id
        AND status IN ('scheduled', 'confirmed')
        AND scheduled_at > now()
    ),
    'pending_tasks', (
      SELECT count(*) FROM fa_tasks
      WHERE client_id = p_client_id
        AND status IN ('pending', 'in_progress')
    ),
    'active_products', (
      SELECT count(*) FROM fa_client_products
      WHERE client_id = p_client_id AND status = 'active'
    ),
    'unread_comms', (
      SELECT count(*) FROM fa_communications
      WHERE client_id = p_client_id
        AND direction = 'outbound'
        AND status = 'sent'
    ),
    'pipeline_stage', (
      SELECT pipeline_stage FROM fa_clients WHERE id = p_client_id
    ),
    'health_score', (
      SELECT health_score FROM fa_clients WHERE id = p_client_id
    )
  );
$$ LANGUAGE sql SECURITY DEFINER;

-- Pipeline summary for adviser dashboard
CREATE OR REPLACE FUNCTION fa_get_pipeline_summary(p_firm_id UUID)
RETURNS TABLE (stage TEXT, client_count BIGINT) AS $$
  SELECT pipeline_stage, count(*)
  FROM fa_clients
  WHERE firm_id = p_firm_id
  GROUP BY pipeline_stage;
$$ LANGUAGE sql SECURITY DEFINER;

-- Compliance summary for compliance dashboard
CREATE OR REPLACE FUNCTION fa_get_compliance_summary(p_firm_id UUID)
RETURNS JSONB AS $$
  SELECT jsonb_build_object(
    'total_clients', (
      SELECT count(*) FROM fa_clients
      WHERE firm_id = p_firm_id AND pipeline_stage != 'inactive'
    ),
    'missing_popia', (
      SELECT count(*) FROM fa_clients c
      WHERE c.firm_id = p_firm_id
        AND NOT EXISTS (
          SELECT 1 FROM fa_consent_records cr
          WHERE cr.client_id = c.id
            AND cr.consent_type = 'popia_processing'
            AND cr.granted = true
            AND cr.revoked_at IS NULL
        )
    ),
    'missing_fais_disclosure', (
      SELECT count(*) FROM fa_clients c
      WHERE c.firm_id = p_firm_id
        AND c.pipeline_stage NOT IN ('lead', 'contacted', 'inactive')
        AND NOT EXISTS (
          SELECT 1 FROM fa_consent_records cr
          WHERE cr.client_id = c.id
            AND cr.consent_type = 'fais_disclosure'
            AND cr.granted = true
        )
    ),
    'expired_consent', (
      SELECT count(*) FROM fa_consent_records
      WHERE firm_id = p_firm_id
        AND expires_at < now()
        AND revoked_at IS NULL
        AND granted = true
    ),
    'overdue_tasks', (
      SELECT count(*) FROM fa_tasks
      WHERE firm_id = p_firm_id
        AND due_date < now()
        AND status NOT IN ('completed', 'cancelled')
    ),
    'unverified_fica', (
      SELECT count(*) FROM fa_clients
      WHERE firm_id = p_firm_id
        AND fica_status != 'verified'
        AND pipeline_stage NOT IN ('lead', 'contacted', 'inactive')
    )
  );
$$ LANGUAGE sql SECURITY DEFINER;


-- ============================================================
-- SEED DATA
-- ============================================================

-- Product types (South African financial products)
INSERT INTO fa_product_types (name, category, provider_options, requires_license, sort_order) VALUES
  ('Life Insurance', 'life_insurance', '["Old Mutual","Sanlam","Discovery Life","Liberty","Momentum","BrightRock","FNB Life"]', '{Cat I}', 1),
  ('Income Protection', 'life_insurance', '["BrightRock","Discovery Life","Sanlam","Liberty","Momentum"]', '{Cat I}', 2),
  ('Disability Cover', 'life_insurance', '["Sanlam","Old Mutual","Discovery Life","Liberty"]', '{Cat I}', 3),
  ('Funeral Cover', 'life_insurance', '["Avbob","Old Mutual","Sanlam","Metropolitan","Hollard"]', '{Cat I}', 4),
  ('Short-Term Insurance', 'short_term_insurance', '["Santam","Hollard","OUTsurance","Discovery Insure","MiWay","King Price"]', '{Cat I.13}', 5),
  ('Medical Aid', 'medical_aid', '["Discovery Health","Bonitas","Momentum Health","Medihelp","GEMS"]', '{Cat I.13A}', 6),
  ('Gap Cover', 'medical_aid', '["Zestlife","Turnberry","Sirago","Resolution Health"]', '{Cat I.13A}', 7),
  ('Retirement Annuity', 'retirement', '["Allan Gray","Coronation","Old Mutual","Sanlam","10X Investments","Ninety One"]', '{Cat II}', 8),
  ('Preservation Fund', 'retirement', '["Allan Gray","Coronation","Old Mutual","Sanlam","Ninety One"]', '{Cat II}', 9),
  ('Living Annuity', 'retirement', '["Allan Gray","Coronation","Old Mutual","Sanlam","Ninety One"]', '{Cat II}', 10),
  ('Unit Trust', 'investment', '["Allan Gray","Coronation","Ninety One","Stanlib","Old Mutual","Satrix"]', '{Cat II}', 11),
  ('Tax-Free Savings', 'savings', '["Allan Gray","Coronation","Old Mutual","Sanlam","Satrix","10X"]', '{Cat II}', 12),
  ('Endowment', 'savings', '["Old Mutual","Sanlam","Liberty","Momentum"]', '{Cat I}', 13),
  ('Will & Estate Plan', 'estate_planning', '["Capital Legacy","Sanlam Trust","Old Mutual Trust","Standard Trust"]', '{}', 14),
  ('Debt Management', 'debt', '["DebtBusters","National Debt Advisors","Meerkat"]', '{}', 15);

-- Fee structures
INSERT INTO fa_fee_structures (type, name, description) VALUES
  ('commission', 'Initial Commission', 'One-time commission on product sale, paid by product provider'),
  ('commission', 'Ongoing Commission', 'Recurring trail commission paid by product provider'),
  ('fee_based', 'Flat Advice Fee', 'Fixed fee for financial planning advice'),
  ('fee_based', 'Hourly Advice Fee', 'Fee charged per hour of advisory service'),
  ('fee_based', 'AUM-Based Fee', 'Annual fee as percentage of assets under management'),
  ('hybrid', 'Hybrid Commission + Fee', 'Combination of commission income and advice fees');
