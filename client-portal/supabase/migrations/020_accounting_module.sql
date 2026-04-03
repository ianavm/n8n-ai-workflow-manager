-- ============================================================
-- Migration 020: Plug-and-Play Accounting & Invoicing Module
-- Date: 2026-04-03
-- 11 tables, RLS policies, RPCs, indexes, helper functions
-- Multi-tenant via client_id -> clients(id)
-- All monetary amounts stored in cents (INTEGER) to prevent floating-point errors
-- ============================================================


-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Check if current user is an admin
CREATE OR REPLACE FUNCTION acct_is_admin()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid())
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Get client_id for the current authenticated portal user
CREATE OR REPLACE FUNCTION acct_get_client_id()
RETURNS UUID AS $$
  SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()) LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;


-- ────────────────────────────────────────────────────────────
-- 1. acct_config — Per-client accounting configuration
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL UNIQUE REFERENCES clients(id) ON DELETE CASCADE,

  -- Company details
  company_legal_name TEXT,
  company_trading_name TEXT,
  company_registration TEXT,
  company_vat_number TEXT,
  company_address JSONB DEFAULT '{}',
  company_bank_details JSONB DEFAULT '{}',  -- {bank_name, account_number, branch_code, swift, account_type}
  company_logo_url TEXT,

  -- Tax & currency
  default_currency TEXT NOT NULL DEFAULT 'ZAR',
  vat_rate NUMERIC(5,4) NOT NULL DEFAULT 0.1500,  -- 15% South Africa

  -- Invoice settings
  invoice_prefix TEXT NOT NULL DEFAULT 'INV',
  invoice_next_number INTEGER NOT NULL DEFAULT 1001,
  default_payment_terms TEXT NOT NULL DEFAULT '30 days',

  -- Thresholds (in cents)
  auto_approve_bills_below INTEGER NOT NULL DEFAULT 1000000,   -- R10,000
  high_value_threshold INTEGER NOT NULL DEFAULT 5000000,       -- R50,000
  payment_match_tolerance NUMERIC(5,2) NOT NULL DEFAULT 50.00, -- % tolerance for AI matching

  -- Collection settings
  reminder_cadence_days INTEGER[] NOT NULL DEFAULT '{-3,0,3,7,14}',
  escalation_after_days INTEGER NOT NULL DEFAULT 14,

  -- Integration adapters (swappable per client)
  accounting_software TEXT NOT NULL DEFAULT 'none'
    CHECK (accounting_software IN ('quickbooks', 'xero', 'sage', 'zoho', 'dynamics', 'none')),
  accounting_software_config JSONB NOT NULL DEFAULT '{}',

  payment_gateway TEXT NOT NULL DEFAULT 'none'
    CHECK (payment_gateway IN ('stripe', 'payfast', 'yoco', 'peach', 'paygate', 'manual', 'none')),
  payment_gateway_config JSONB NOT NULL DEFAULT '{}',

  ocr_provider TEXT NOT NULL DEFAULT 'ai'
    CHECK (ocr_provider IN ('azure_doc_ai', 'google_doc_ai', 'dext', 'hubdoc', 'ai', 'none')),
  ocr_config JSONB NOT NULL DEFAULT '{}',

  comms_email TEXT NOT NULL DEFAULT 'gmail'
    CHECK (comms_email IN ('gmail', 'outlook', 'none')),
  comms_chat TEXT NOT NULL DEFAULT 'none'
    CHECK (comms_chat IN ('whatsapp', 'telegram', 'slack', 'teams', 'none')),
  comms_config JSONB NOT NULL DEFAULT '{}',

  file_storage TEXT NOT NULL DEFAULT 'none'
    CHECK (file_storage IN ('google_drive', 'onedrive', 'sharepoint', 's3', 'dropbox', 'supabase', 'none')),
  file_storage_config JSONB NOT NULL DEFAULT '{}',

  -- Module toggles
  modules_enabled JSONB NOT NULL DEFAULT '{
    "invoicing": true,
    "collections": true,
    "payments": true,
    "bills": true,
    "reporting": true,
    "approvals": true,
    "exceptions": true,
    "supplier_payments": true
  }',

  -- n8n workflow IDs (populated after deployment)
  workflow_ids JSONB NOT NULL DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE acct_config ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 2. acct_customers — AR counterparties (client's customers)
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  legal_name TEXT NOT NULL,
  trading_name TEXT,
  email TEXT,
  phone TEXT,
  billing_address TEXT,
  vat_number TEXT,
  payment_terms TEXT NOT NULL DEFAULT '30 days',
  credit_limit INTEGER NOT NULL DEFAULT 0,  -- cents
  risk_flag TEXT NOT NULL DEFAULT 'low'
    CHECK (risk_flag IN ('low', 'medium', 'high')),
  preferred_channel TEXT NOT NULL DEFAULT 'email'
    CHECK (preferred_channel IN ('email', 'whatsapp', 'both')),
  external_id TEXT,  -- ID in accounting software
  active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_acct_customers_client ON acct_customers(client_id);
CREATE INDEX idx_acct_customers_email ON acct_customers(client_id, email);
CREATE INDEX idx_acct_customers_active ON acct_customers(client_id, active);

ALTER TABLE acct_customers ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 3. acct_suppliers — AP counterparties (client's suppliers)
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_suppliers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  vat_number TEXT,
  bank_details_hash TEXT,  -- hashed for security, raw never stored
  default_category TEXT,
  payment_terms TEXT NOT NULL DEFAULT '30 days',
  external_id TEXT,
  active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_acct_suppliers_client ON acct_suppliers(client_id);
CREATE INDEX idx_acct_suppliers_active ON acct_suppliers(client_id, active);

ALTER TABLE acct_suppliers ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 4. acct_products — Service/product catalog
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  item_code TEXT NOT NULL,
  description TEXT NOT NULL,
  unit_price INTEGER NOT NULL DEFAULT 0,  -- cents
  vat_rate_code TEXT NOT NULL DEFAULT 'standard_15'
    CHECK (vat_rate_code IN ('standard_15', 'zero_rated', 'exempt', 'custom')),
  custom_vat_rate NUMERIC(5,4),  -- only when vat_rate_code = 'custom'
  revenue_account_code TEXT,
  cost_account_code TEXT,
  active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE(client_id, item_code)
);

CREATE INDEX idx_acct_products_client ON acct_products(client_id);

ALTER TABLE acct_products ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 5. acct_invoices — Core invoicing (AR)
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  customer_id UUID REFERENCES acct_customers(id) ON DELETE SET NULL,

  invoice_number TEXT NOT NULL,
  reference TEXT,  -- PO number or external ref
  issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
  due_date DATE NOT NULL,

  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN (
      'draft', 'approved', 'sent', 'viewed',
      'payment_pending', 'partially_paid', 'paid',
      'overdue', 'disputed', 'cancelled'
    )),

  -- Amounts in cents
  subtotal INTEGER NOT NULL DEFAULT 0,
  vat_amount INTEGER NOT NULL DEFAULT 0,
  total INTEGER NOT NULL DEFAULT 0,
  amount_paid INTEGER NOT NULL DEFAULT 0,
  balance_due INTEGER GENERATED ALWAYS AS (total - amount_paid) STORED,

  currency TEXT NOT NULL DEFAULT 'ZAR',
  line_items JSONB NOT NULL DEFAULT '[]',
  -- line_items format: [{item_code, description, qty, unit_price, vat_rate, line_total}]

  pdf_url TEXT,
  payment_link TEXT,
  external_id TEXT,  -- accounting software invoice ID
  source TEXT NOT NULL DEFAULT 'manual'
    CHECK (source IN ('manual', 'portal', 'api', 'contract', 'recurring')),

  -- Collection tracking
  reminder_count INTEGER NOT NULL DEFAULT 0,
  last_reminder_at TIMESTAMPTZ,
  next_reminder_at TIMESTAMPTZ,

  -- Dispute
  dispute_reason TEXT,
  dispute_owner TEXT,

  notes TEXT,
  created_by TEXT,
  sent_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE(client_id, invoice_number)
);

CREATE INDEX idx_acct_invoices_client_status ON acct_invoices(client_id, status);
CREATE INDEX idx_acct_invoices_client_due ON acct_invoices(client_id, due_date);
CREATE INDEX idx_acct_invoices_customer ON acct_invoices(customer_id);
CREATE INDEX idx_acct_invoices_overdue ON acct_invoices(client_id, status, due_date)
  WHERE status IN ('sent', 'payment_pending', 'overdue');

ALTER TABLE acct_invoices ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 6. acct_payments — Payment records
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  invoice_id UUID REFERENCES acct_invoices(id) ON DELETE SET NULL,

  amount INTEGER NOT NULL,  -- cents
  date_received DATE NOT NULL DEFAULT CURRENT_DATE,
  method TEXT NOT NULL
    CHECK (method IN ('eft', 'stripe', 'payfast', 'yoco', 'cash', 'credit_card', 'debit_order', 'other')),
  reference_text TEXT,     -- bank reference / gateway transaction ID
  gateway_transaction_id TEXT,

  reconciliation_status TEXT NOT NULL DEFAULT 'received'
    CHECK (reconciliation_status IN (
      'received', 'matching', 'matched', 'partial',
      'unmatched', 'reconciled', 'overpayment'
    )),
  match_confidence NUMERIC(5,2),  -- AI confidence 0-100
  matched_by TEXT,  -- 'auto', 'ai', 'manual'

  pop_url TEXT,   -- proof of payment file URL
  receipt_sent BOOLEAN NOT NULL DEFAULT false,
  external_id TEXT,  -- accounting software payment ID

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_acct_payments_client ON acct_payments(client_id);
CREATE INDEX idx_acct_payments_invoice ON acct_payments(client_id, invoice_id);
CREATE INDEX idx_acct_payments_status ON acct_payments(client_id, reconciliation_status);
CREATE INDEX idx_acct_payments_unmatched ON acct_payments(client_id, reconciliation_status)
  WHERE reconciliation_status IN ('received', 'matching', 'unmatched');

ALTER TABLE acct_payments ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 7. acct_supplier_bills — Accounts payable
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_supplier_bills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  supplier_id UUID REFERENCES acct_suppliers(id) ON DELETE SET NULL,

  bill_number TEXT,
  bill_date DATE,
  due_date DATE,

  -- Amounts in cents
  subtotal INTEGER NOT NULL DEFAULT 0,
  vat_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,

  category TEXT,
  cost_center TEXT,

  -- Document / OCR
  attachment_url TEXT,
  ocr_raw JSONB,  -- raw OCR output for debugging
  extraction_confidence NUMERIC(5,2),  -- 0-100

  status TEXT NOT NULL DEFAULT 'uploaded'
    CHECK (status IN (
      'uploaded', 'extracted', 'awaiting_review',
      'approved', 'scheduled', 'paid', 'rejected'
    )),

  -- Approval
  approver TEXT,
  approved_at TIMESTAMPTZ,
  rejection_reason TEXT,

  -- Payment
  payment_status TEXT NOT NULL DEFAULT 'unpaid'
    CHECK (payment_status IN ('unpaid', 'scheduled', 'paid')),
  payment_date DATE,
  payment_reference TEXT,

  external_id TEXT,  -- accounting software bill ID
  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_acct_bills_client_status ON acct_supplier_bills(client_id, status);
CREATE INDEX idx_acct_bills_client_due ON acct_supplier_bills(client_id, due_date);
CREATE INDEX idx_acct_bills_supplier ON acct_supplier_bills(supplier_id);
CREATE INDEX idx_acct_bills_approval ON acct_supplier_bills(client_id, status)
  WHERE status IN ('uploaded', 'extracted', 'awaiting_review');

ALTER TABLE acct_supplier_bills ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 8. acct_tasks — Approval queue / human action items
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  type TEXT NOT NULL
    CHECK (type IN (
      'invoice_approval', 'bill_approval', 'payment_reconciliation',
      'dispute_resolution', 'exception_review', 'month_end_task',
      'bank_detail_change', 'general'
    )),
  priority TEXT NOT NULL DEFAULT 'medium'
    CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'in_progress', 'completed', 'escalated', 'cancelled')),

  title TEXT NOT NULL,
  description TEXT,
  owner TEXT,  -- assigned user email

  -- Linkage to related entity
  related_entity_type TEXT
    CHECK (related_entity_type IN ('invoice', 'bill', 'payment', 'customer', 'supplier')),
  related_entity_id UUID,

  -- Approval
  approval_token TEXT UNIQUE,  -- for email-based approve/reject links
  approval_action TEXT,  -- 'approved', 'rejected'
  approval_reason TEXT,

  -- Resolution
  resolution_notes TEXT,
  resolved_by TEXT,

  due_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  escalated_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_acct_tasks_client_status ON acct_tasks(client_id, status);
CREATE INDEX idx_acct_tasks_open ON acct_tasks(client_id, status, priority)
  WHERE status IN ('open', 'in_progress');
CREATE INDEX idx_acct_tasks_entity ON acct_tasks(related_entity_type, related_entity_id);
CREATE UNIQUE INDEX idx_acct_tasks_token ON acct_tasks(approval_token) WHERE approval_token IS NOT NULL;

ALTER TABLE acct_tasks ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 9. acct_audit_log — Immutable audit trail
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_audit_log (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  event_type TEXT NOT NULL,
  -- Event types: INVOICE_CREATED, INVOICE_SENT, INVOICE_APPROVED, INVOICE_PAID,
  -- INVOICE_OVERDUE, INVOICE_DISPUTED, INVOICE_CANCELLED,
  -- PAYMENT_RECEIVED, PAYMENT_MATCHED, PAYMENT_UNMATCHED,
  -- BILL_UPLOADED, BILL_EXTRACTED, BILL_APPROVED, BILL_REJECTED, BILL_PAID,
  -- CUSTOMER_CREATED, CUSTOMER_UPDATED, SUPPLIER_CREATED, SUPPLIER_UPDATED,
  -- TASK_CREATED, TASK_ESCALATED, TASK_COMPLETED,
  -- WORKFLOW_STARTED, WORKFLOW_COMPLETED, WORKFLOW_FAILED,
  -- CONFIG_UPDATED, REPORT_GENERATED, EXCEPTION_RAISED

  entity_type TEXT,  -- 'invoice', 'bill', 'payment', 'customer', 'supplier', 'task', 'workflow'
  entity_id UUID,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,  -- 'system', 'n8n_wf02', user email, etc.
  result TEXT NOT NULL DEFAULT 'success'
    CHECK (result IN ('success', 'failed', 'partial')),
  error_details TEXT,
  old_value JSONB,
  new_value JSONB,
  metadata JSONB NOT NULL DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- No UPDATE or DELETE policies — append-only
CREATE INDEX idx_acct_audit_client_time ON acct_audit_log(client_id, created_at DESC);
CREATE INDEX idx_acct_audit_entity ON acct_audit_log(client_id, entity_type, entity_id);
CREATE INDEX idx_acct_audit_event ON acct_audit_log(client_id, event_type);

ALTER TABLE acct_audit_log ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 10. acct_workflow_status — Real-time workflow lifecycle
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_workflow_status (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

  workflow_module TEXT NOT NULL,
  -- Modules: wf01_master_data, wf02_invoicing, wf03_sending, wf04_collections,
  -- wf05_payments, wf06_bill_intake, wf07_supplier_payments, wf08_approvals,
  -- wf09_reporting, wf10_exceptions

  execution_id TEXT,  -- n8n execution ID
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN (
      'running', 'completed', 'waiting_for_human',
      'failed', 'retrying', 'escalated'
    )),
  step_name TEXT,        -- current step e.g. 'ai_extraction', 'sending_email'
  entity_type TEXT,
  entity_id UUID,
  progress_pct INTEGER,  -- 0-100
  message TEXT,
  error_details TEXT,

  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_acct_wfstatus_client ON acct_workflow_status(client_id, updated_at DESC);
CREATE INDEX idx_acct_wfstatus_active ON acct_workflow_status(client_id, status)
  WHERE status IN ('running', 'waiting_for_human', 'retrying');

ALTER TABLE acct_workflow_status ENABLE ROW LEVEL SECURITY;


-- ────────────────────────────────────────────────────────────
-- 11. acct_collections — Collection activity per invoice
-- ────────────────────────────────────────────────────────────
CREATE TABLE acct_collections (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  invoice_id UUID NOT NULL REFERENCES acct_invoices(id) ON DELETE CASCADE,

  status TEXT NOT NULL DEFAULT 'scheduled'
    CHECK (status IN (
      'scheduled', 'sent', 'awaiting_response',
      'pop_received', 'under_review', 'escalated', 'resolved'
    )),
  channel TEXT NOT NULL DEFAULT 'email'
    CHECK (channel IN ('email', 'whatsapp', 'phone', 'sms')),
  template_used TEXT,  -- which reminder template was sent
  reminder_tier INTEGER NOT NULL DEFAULT 1,  -- 1=friendly, 2=firm, 3=escalation

  sent_at TIMESTAMPTZ,
  response_at TIMESTAMPTZ,
  pop_url TEXT,
  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_acct_collections_invoice ON acct_collections(client_id, invoice_id);
CREATE INDEX idx_acct_collections_status ON acct_collections(client_id, status);

ALTER TABLE acct_collections ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- RLS POLICIES
-- ============================================================

-- ── acct_config ────────────────────────────────────────────
CREATE POLICY "client_own_config" ON acct_config FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_config_all" ON acct_config FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_config_write" ON acct_config FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

-- ── acct_customers ─────────────────────────────────────────
CREATE POLICY "client_own_customers" ON acct_customers FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_customers_all" ON acct_customers FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_customers_write" ON acct_customers FOR ALL
  USING (auth.role() = 'service_role');

-- ── acct_suppliers ─────────────────────────────────────────
CREATE POLICY "client_own_suppliers" ON acct_suppliers FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_suppliers_all" ON acct_suppliers FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_suppliers_write" ON acct_suppliers FOR ALL
  USING (auth.role() = 'service_role');

-- ── acct_products ──────────────────────────────────────────
CREATE POLICY "client_own_products" ON acct_products FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_products_all" ON acct_products FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_products_write" ON acct_products FOR ALL
  USING (auth.role() = 'service_role');

-- ── acct_invoices ──────────────────────────────────────────
CREATE POLICY "client_own_invoices" ON acct_invoices FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_invoices_all" ON acct_invoices FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_invoices_write" ON acct_invoices FOR ALL
  USING (auth.role() = 'service_role');

-- ── acct_payments ──────────────────────────────────────────
CREATE POLICY "client_own_payments" ON acct_payments FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_payments_all" ON acct_payments FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_payments_write" ON acct_payments FOR ALL
  USING (auth.role() = 'service_role');

-- ── acct_supplier_bills ────────────────────────────────────
CREATE POLICY "admin_bills_select" ON acct_supplier_bills FOR SELECT
  USING (acct_is_admin());
CREATE POLICY "admin_bills_all" ON acct_supplier_bills FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_bills_write" ON acct_supplier_bills FOR ALL
  USING (auth.role() = 'service_role');
-- Note: clients do NOT see supplier bills — admin/internal only

-- ── acct_tasks ─────────────────────────────────────────────
CREATE POLICY "admin_tasks_select" ON acct_tasks FOR SELECT
  USING (acct_is_admin());
CREATE POLICY "admin_tasks_all" ON acct_tasks FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_tasks_write" ON acct_tasks FOR ALL
  USING (auth.role() = 'service_role');

-- ── acct_audit_log (append-only: SELECT for admin, INSERT for service) ──
CREATE POLICY "admin_audit_select" ON acct_audit_log FOR SELECT
  USING (acct_is_admin());
CREATE POLICY "service_audit_insert" ON acct_audit_log FOR INSERT
  WITH CHECK (auth.role() = 'service_role');
-- No UPDATE or DELETE policies — immutable

-- ── acct_workflow_status ───────────────────────────────────
CREATE POLICY "client_own_wfstatus" ON acct_workflow_status FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_wfstatus_all" ON acct_workflow_status FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_wfstatus_write" ON acct_workflow_status FOR ALL
  USING (auth.role() = 'service_role');

-- ── acct_collections ───────────────────────────────────────
CREATE POLICY "client_own_collections" ON acct_collections FOR SELECT
  USING (client_id = acct_get_client_id() OR acct_is_admin());
CREATE POLICY "admin_collections_all" ON acct_collections FOR ALL
  USING (acct_is_admin());
CREATE POLICY "service_collections_write" ON acct_collections FOR ALL
  USING (auth.role() = 'service_role');


-- ============================================================
-- RPCs (SECURITY DEFINER — bypass RLS for aggregation)
-- ============================================================

-- ── Invoice number generator (atomic increment) ───────────
CREATE OR REPLACE FUNCTION acct_generate_invoice_number(p_client_id UUID)
RETURNS TEXT AS $$
DECLARE
  v_prefix TEXT;
  v_number INTEGER;
BEGIN
  UPDATE acct_config
  SET invoice_next_number = invoice_next_number + 1,
      updated_at = now()
  WHERE client_id = p_client_id
  RETURNING invoice_prefix, invoice_next_number - 1
  INTO v_prefix, v_number;

  IF v_prefix IS NULL THEN
    RAISE EXCEPTION 'No accounting config found for client %', p_client_id;
  END IF;

  RETURN v_prefix || '-' || LPAD(v_number::TEXT, 6, '0');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ── Dashboard KPIs ────────────────────────────────────────
CREATE OR REPLACE FUNCTION acct_get_dashboard_kpis(p_client_id UUID)
RETURNS JSONB AS $$
DECLARE
  v_result JSONB;
BEGIN
  SELECT jsonb_build_object(
    'total_receivables', COALESCE(
      (SELECT SUM(balance_due) FROM acct_invoices
       WHERE client_id = p_client_id AND status NOT IN ('paid', 'cancelled', 'draft')), 0),
    'total_payables', COALESCE(
      (SELECT SUM(total_amount) FROM acct_supplier_bills
       WHERE client_id = p_client_id AND payment_status = 'unpaid'), 0),
    'overdue_invoices', COALESCE(
      (SELECT COUNT(*) FROM acct_invoices
       WHERE client_id = p_client_id AND status = 'overdue'), 0),
    'overdue_amount', COALESCE(
      (SELECT SUM(balance_due) FROM acct_invoices
       WHERE client_id = p_client_id AND status = 'overdue'), 0),
    'invoices_sent_today', COALESCE(
      (SELECT COUNT(*) FROM acct_invoices
       WHERE client_id = p_client_id AND sent_at >= CURRENT_DATE), 0),
    'cash_received_today', COALESCE(
      (SELECT SUM(amount) FROM acct_payments
       WHERE client_id = p_client_id AND date_received = CURRENT_DATE), 0),
    'cash_received_month', COALESCE(
      (SELECT SUM(amount) FROM acct_payments
       WHERE client_id = p_client_id
       AND date_received >= date_trunc('month', CURRENT_DATE)), 0),
    'pending_approvals', COALESCE(
      (SELECT COUNT(*) FROM acct_tasks
       WHERE client_id = p_client_id AND status = 'open'), 0),
    'bills_awaiting_approval', COALESCE(
      (SELECT COUNT(*) FROM acct_supplier_bills
       WHERE client_id = p_client_id AND status IN ('extracted', 'awaiting_review')), 0),
    'reconciliation_pending', COALESCE(
      (SELECT COUNT(*) FROM acct_payments
       WHERE client_id = p_client_id AND reconciliation_status IN ('received', 'matching', 'unmatched')), 0),
    'workflow_failures', COALESCE(
      (SELECT COUNT(*) FROM acct_workflow_status
       WHERE client_id = p_client_id AND status = 'failed'
       AND started_at >= CURRENT_DATE - INTERVAL '7 days'), 0),
    'bills_due_this_week', COALESCE(
      (SELECT SUM(total_amount) FROM acct_supplier_bills
       WHERE client_id = p_client_id AND payment_status = 'unpaid'
       AND due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'), 0)
  ) INTO v_result;

  RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ── Aged Receivables ──────────────────────────────────────
CREATE OR REPLACE FUNCTION acct_get_aged_receivables(p_client_id UUID)
RETURNS JSONB AS $$
BEGIN
  RETURN (
    SELECT jsonb_build_object(
      'current', COALESCE(SUM(CASE WHEN due_date >= CURRENT_DATE THEN balance_due END), 0),
      'days_30', COALESCE(SUM(CASE WHEN due_date < CURRENT_DATE AND due_date >= CURRENT_DATE - 30 THEN balance_due END), 0),
      'days_60', COALESCE(SUM(CASE WHEN due_date < CURRENT_DATE - 30 AND due_date >= CURRENT_DATE - 60 THEN balance_due END), 0),
      'days_90', COALESCE(SUM(CASE WHEN due_date < CURRENT_DATE - 60 AND due_date >= CURRENT_DATE - 90 THEN balance_due END), 0),
      'days_120_plus', COALESCE(SUM(CASE WHEN due_date < CURRENT_DATE - 90 THEN balance_due END), 0),
      'total', COALESCE(SUM(balance_due), 0)
    )
    FROM acct_invoices
    WHERE client_id = p_client_id
      AND status NOT IN ('paid', 'cancelled', 'draft')
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ── Aged Payables ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION acct_get_aged_payables(p_client_id UUID)
RETURNS JSONB AS $$
BEGIN
  RETURN (
    SELECT jsonb_build_object(
      'current', COALESCE(SUM(CASE WHEN due_date >= CURRENT_DATE THEN total_amount END), 0),
      'days_30', COALESCE(SUM(CASE WHEN due_date < CURRENT_DATE AND due_date >= CURRENT_DATE - 30 THEN total_amount END), 0),
      'days_60', COALESCE(SUM(CASE WHEN due_date < CURRENT_DATE - 30 AND due_date >= CURRENT_DATE - 60 THEN total_amount END), 0),
      'days_90', COALESCE(SUM(CASE WHEN due_date < CURRENT_DATE - 60 AND due_date >= CURRENT_DATE - 90 THEN total_amount END), 0),
      'days_120_plus', COALESCE(SUM(CASE WHEN due_date < CURRENT_DATE - 90 THEN total_amount END), 0),
      'total', COALESCE(SUM(total_amount), 0)
    )
    FROM acct_supplier_bills
    WHERE client_id = p_client_id
      AND payment_status = 'unpaid'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ── Cashflow Summary (monthly) ────────────────────────────
CREATE OR REPLACE FUNCTION acct_get_cashflow_summary(p_client_id UUID, p_months INTEGER DEFAULT 6)
RETURNS JSONB AS $$
BEGIN
  RETURN (
    SELECT COALESCE(jsonb_agg(month_data ORDER BY month_data->>'month'), '[]'::jsonb)
    FROM (
      SELECT jsonb_build_object(
        'month', to_char(m.month_start, 'YYYY-MM'),
        'income', COALESCE((
          SELECT SUM(amount) FROM acct_payments
          WHERE client_id = p_client_id
            AND date_received >= m.month_start
            AND date_received < m.month_start + INTERVAL '1 month'
        ), 0),
        'expenses', COALESCE((
          SELECT SUM(total_amount) FROM acct_supplier_bills
          WHERE client_id = p_client_id
            AND payment_status = 'paid'
            AND payment_date >= m.month_start
            AND payment_date < m.month_start + INTERVAL '1 month'
        ), 0),
        'invoiced', COALESCE((
          SELECT SUM(total) FROM acct_invoices
          WHERE client_id = p_client_id
            AND issue_date >= m.month_start
            AND issue_date < m.month_start + INTERVAL '1 month'
            AND status != 'cancelled'
        ), 0)
      ) AS month_data
      FROM generate_series(
        date_trunc('month', CURRENT_DATE) - (p_months - 1) * INTERVAL '1 month',
        date_trunc('month', CURRENT_DATE),
        INTERVAL '1 month'
      ) AS m(month_start)
    ) sub
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ── Reconciliation Stats ──────────────────────────────────
CREATE OR REPLACE FUNCTION acct_get_reconciliation_stats(p_client_id UUID)
RETURNS JSONB AS $$
BEGIN
  RETURN (
    SELECT jsonb_build_object(
      'matched', COALESCE(SUM(CASE WHEN reconciliation_status = 'matched' THEN 1 END), 0),
      'partial', COALESCE(SUM(CASE WHEN reconciliation_status = 'partial' THEN 1 END), 0),
      'unmatched', COALESCE(SUM(CASE WHEN reconciliation_status = 'unmatched' THEN 1 END), 0),
      'overpayment', COALESCE(SUM(CASE WHEN reconciliation_status = 'overpayment' THEN 1 END), 0),
      'pending', COALESCE(SUM(CASE WHEN reconciliation_status IN ('received', 'matching') THEN 1 END), 0),
      'reconciled', COALESCE(SUM(CASE WHEN reconciliation_status = 'reconciled' THEN 1 END), 0),
      'total', COUNT(*),
      'unmatched_amount', COALESCE(SUM(CASE WHEN reconciliation_status = 'unmatched' THEN amount END), 0)
    )
    FROM acct_payments
    WHERE client_id = p_client_id
      AND date_received >= CURRENT_DATE - INTERVAL '30 days'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;


-- ============================================================
-- UPDATED_AT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION acct_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_acct_config_updated
  BEFORE UPDATE ON acct_config FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();
CREATE TRIGGER trg_acct_customers_updated
  BEFORE UPDATE ON acct_customers FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();
CREATE TRIGGER trg_acct_suppliers_updated
  BEFORE UPDATE ON acct_suppliers FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();
CREATE TRIGGER trg_acct_products_updated
  BEFORE UPDATE ON acct_products FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();
CREATE TRIGGER trg_acct_invoices_updated
  BEFORE UPDATE ON acct_invoices FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();
CREATE TRIGGER trg_acct_payments_updated
  BEFORE UPDATE ON acct_payments FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();
CREATE TRIGGER trg_acct_bills_updated
  BEFORE UPDATE ON acct_supplier_bills FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();
CREATE TRIGGER trg_acct_tasks_updated
  BEFORE UPDATE ON acct_tasks FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();
CREATE TRIGGER trg_acct_wfstatus_updated
  BEFORE UPDATE ON acct_workflow_status FOR EACH ROW EXECUTE FUNCTION acct_set_updated_at();


-- ============================================================
-- ENABLE REALTIME (for live portal updates)
-- ============================================================

ALTER PUBLICATION supabase_realtime ADD TABLE acct_invoices;
ALTER PUBLICATION supabase_realtime ADD TABLE acct_workflow_status;
ALTER PUBLICATION supabase_realtime ADD TABLE acct_tasks;
ALTER PUBLICATION supabase_realtime ADD TABLE acct_payments;
