-- ============================================================
-- Migration 032: Client-Self-Serve CSV Imports for CRM
-- Date: 2026-04-22
-- Lets portal clients upload a CSV of their existing CRM and
-- ingest companies / contacts / leads into the new schema.
-- Depends on: 031_crm_module.sql
-- ============================================================


-- ============================================================
-- 1. Storage bucket for raw CSV uploads (private; RLS on objects)
-- ============================================================
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'crm-imports',
  'crm-imports',
  FALSE,
  10485760, -- 10 MB cap
  ARRAY['text/csv', 'application/vnd.ms-excel', 'text/plain']
)
ON CONFLICT (id) DO UPDATE SET
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;


-- Storage-level RLS: clients can upload / read only under their own client_id/ prefix.
-- Paths are enforced: {client_id}/{import_id}/{filename}
DROP POLICY IF EXISTS "crm_imports_client_insert" ON storage.objects;
CREATE POLICY "crm_imports_client_insert" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'crm-imports'
    AND (storage.foldername(name))[1] = (
      SELECT id::text FROM clients WHERE auth_user_id = (SELECT auth.uid()) LIMIT 1
    )
  );

DROP POLICY IF EXISTS "crm_imports_client_read" ON storage.objects;
CREATE POLICY "crm_imports_client_read" ON storage.objects
  FOR SELECT TO authenticated
  USING (
    bucket_id = 'crm-imports'
    AND (
      (storage.foldername(name))[1] = (
        SELECT id::text FROM clients WHERE auth_user_id = (SELECT auth.uid()) LIMIT 1
      )
      OR EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    )
  );

DROP POLICY IF EXISTS "crm_imports_admin_all" ON storage.objects;
CREATE POLICY "crm_imports_admin_all" ON storage.objects
  FOR ALL TO authenticated
  USING (
    bucket_id = 'crm-imports'
    AND EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
  )
  WITH CHECK (
    bucket_id = 'crm-imports'
    AND EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
  );


-- ============================================================
-- 2. Open up client-side INSERT/UPDATE on core tables so clients
--    can ingest their own data. RLS continues to enforce tenancy.
-- ============================================================

-- crm_imports — client can create / read / update their own import jobs
CREATE POLICY "clients_own_crm_imports_select" ON crm_imports
  FOR SELECT USING (client_id = crm_get_client_id());

CREATE POLICY "clients_own_crm_imports_insert" ON crm_imports
  FOR INSERT WITH CHECK (client_id = crm_get_client_id());

CREATE POLICY "clients_own_crm_imports_update" ON crm_imports
  FOR UPDATE USING (client_id = crm_get_client_id())
  WITH CHECK (client_id = crm_get_client_id());

-- crm_companies — client can INSERT their own; updates stay admin-only for now
CREATE POLICY "clients_own_crm_companies_insert" ON crm_companies
  FOR INSERT WITH CHECK (client_id = crm_get_client_id());

-- crm_contacts — same
CREATE POLICY "clients_own_crm_contacts_insert" ON crm_contacts
  FOR INSERT WITH CHECK (client_id = crm_get_client_id());

-- crm_leads — client INSERT for import-generated rows
CREATE POLICY "clients_own_crm_leads_insert" ON crm_leads
  FOR INSERT WITH CHECK (client_id = crm_get_client_id());


-- ============================================================
-- 3. Helper: natural-key columns for idempotent imports
-- ============================================================

-- Upsert-friendly unique indexes (partial so NULLs don't collide).
-- Already have domain index on crm_companies; add a per-tenant unique for canonical domain.
CREATE UNIQUE INDEX IF NOT EXISTS ux_crm_companies_client_domain
  ON crm_companies (client_id, lower(domain))
  WHERE domain IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_crm_contacts_client_email
  ON crm_contacts (client_id, lower(email))
  WHERE email IS NOT NULL;


-- ============================================================
-- 4. Mark the imports trigger: auto-stamp import meta on new rows
--    so we can trace every ingested row back to its source import.
-- ============================================================

-- Optional free-form meta column already exists on crm_leads/companies/contacts.
-- Client API writes { "import_id": "<uuid>" } into .meta on ingest.


-- ============================================================
-- END migration 032
-- ============================================================
