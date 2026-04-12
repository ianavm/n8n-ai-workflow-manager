-- Add login tracking columns to clients and admin_users tables
ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS last_login_ip TEXT,
  ADD COLUMN IF NOT EXISTS last_login_device TEXT;

ALTER TABLE admin_users
  ADD COLUMN IF NOT EXISTS last_login_ip TEXT,
  ADD COLUMN IF NOT EXISTS last_login_device TEXT;

-- Allow clients to read their own login metadata
-- (existing RLS policies already cover SELECT on clients for own row)
