-- ============================================================
-- Migration 018: Financial Advisory Storage Bucket
-- Private bucket for client documents (50MB max, PDF/images/Office)
-- ============================================================

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'fa-documents',
  'fa-documents',
  false,
  52428800,
  ARRAY[
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  ]
);

-- Advisers: full access within their firm
CREATE POLICY "advisers_fa_docs_all" ON storage.objects FOR ALL
  USING (bucket_id = 'fa-documents' AND fa_is_adviser())
  WITH CHECK (bucket_id = 'fa-documents' AND fa_is_adviser());

-- Portal clients: read documents in their own folder
CREATE POLICY "clients_fa_docs_read" ON storage.objects FOR SELECT
  USING (
    bucket_id = 'fa-documents'
    AND (storage.foldername(name))[1] IN (
      SELECT fc.id::text FROM fa_clients fc
      JOIN clients c ON c.id = fc.portal_client_id
      WHERE c.auth_user_id = (SELECT auth.uid())
    )
  );

-- Portal clients: upload documents to their own folder
CREATE POLICY "clients_fa_docs_upload" ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'fa-documents'
    AND (storage.foldername(name))[1] IN (
      SELECT fc.id::text FROM fa_clients fc
      JOIN clients c ON c.id = fc.portal_client_id
      WHERE c.auth_user_id = (SELECT auth.uid())
    )
  );

-- Admin users: full access
CREATE POLICY "admin_fa_docs_all" ON storage.objects FOR ALL
  USING (bucket_id = 'fa-documents' AND fa_is_admin())
  WITH CHECK (bucket_id = 'fa-documents' AND fa_is_admin());
