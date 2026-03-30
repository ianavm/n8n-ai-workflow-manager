-- ============================================================
-- Demo Client Seed: Portal login for Sipho Nkosi
-- Run against Supabase SQL Editor (service_role)
-- ============================================================
-- Creates a portal client user (client@testemail.com / Password123!)
-- and links it to the fa_clients record for Sipho Nkosi so the
-- client portal advisory pages show his data.
-- ============================================================

-- Fixed UUIDs for reproducibility
-- Auth user:      a0000000-0000-0000-0000-000000000002
-- Portal client:  b0000000-0000-0000-0000-000000000002
-- FA client (Sipho Nkosi): c0000000-0000-0000-0000-000000000001

BEGIN;

-- ────────────────────────────────────────────────────────────
-- 1. Create auth user (client@testemail.com)
-- ────────────────────────────────────────────────────────────
-- Password: Password123! (bcrypt hash)
INSERT INTO auth.users (
  instance_id,
  id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at,
  confirmation_token,
  recovery_token
) VALUES (
  '00000000-0000-0000-0000-000000000000',
  'a0000000-0000-0000-0000-000000000002',
  'authenticated',
  'authenticated',
  'client@testemail.com',
  crypt('Password123!', gen_salt('bf')),
  now(),
  '{"provider": "email", "providers": ["email"]}',
  '{"full_name": "Sipho Nkosi"}',
  now(),
  now(),
  '',
  ''
)
ON CONFLICT (id) DO UPDATE SET
  encrypted_password = crypt('Password123!', gen_salt('bf')),
  updated_at = now();

-- Ensure identity record exists (required by Supabase auth)
INSERT INTO auth.identities (
  id,
  user_id,
  provider_id,
  identity_data,
  provider,
  last_sign_in_at,
  created_at,
  updated_at
) VALUES (
  'a0000000-0000-0000-0000-000000000002',
  'a0000000-0000-0000-0000-000000000002',
  'a0000000-0000-0000-0000-000000000002',
  jsonb_build_object(
    'sub', 'a0000000-0000-0000-0000-000000000002',
    'email', 'client@testemail.com',
    'email_verified', true
  ),
  'email',
  now(),
  now(),
  now()
)
ON CONFLICT (provider_id, provider) DO NOTHING;

-- ────────────────────────────────────────────────────────────
-- 2. Create portal clients record
-- ────────────────────────────────────────────────────────────
INSERT INTO clients (
  id,
  auth_user_id,
  email,
  full_name,
  company_name,
  status,
  created_at,
  updated_at
) VALUES (
  'b0000000-0000-0000-0000-000000000002',
  'a0000000-0000-0000-0000-000000000002',
  'client@testemail.com',
  'Sipho Nkosi',
  NULL,
  'active',
  now(),
  now()
)
ON CONFLICT (id) DO UPDATE SET
  auth_user_id = EXCLUDED.auth_user_id,
  email = EXCLUDED.email,
  full_name = EXCLUDED.full_name,
  updated_at = now();

-- ────────────────────────────────────────────────────────────
-- 3. Link fa_clients (Sipho Nkosi) to the portal client
-- ────────────────────────────────────────────────────────────
-- This sets portal_client_id on the FA client record so that
-- RLS policies (fa_is_portal_client) grant the auth user access
-- to Sipho's advisory data through the client portal.
UPDATE fa_clients
SET
  portal_client_id = 'b0000000-0000-0000-0000-000000000002',
  updated_at = now()
WHERE id = 'c0000000-0000-0000-0000-000000000001';

-- ────────────────────────────────────────────────────────────
-- 4. Verify the linkage
-- ────────────────────────────────────────────────────────────
-- This query should return one row with Sipho's data:
-- SELECT
--   au.email AS auth_email,
--   c.full_name AS portal_name,
--   fc.first_name || ' ' || fc.last_name AS fa_name,
--   fc.pipeline_stage,
--   fc.portal_client_id
-- FROM auth.users au
-- JOIN clients c ON c.auth_user_id = au.id
-- JOIN fa_clients fc ON fc.portal_client_id = c.id
-- WHERE au.email = 'client@testemail.com';

COMMIT;
