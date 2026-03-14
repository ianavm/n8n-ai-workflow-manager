-- ============================================
-- Add self-signup support fields and policies
-- ============================================

-- Add phone_number to clients table
ALTER TABLE clients ADD COLUMN IF NOT EXISTS phone_number TEXT;

-- Add email_verified tracking (mirrors auth.users.email_confirmed_at)
ALTER TABLE clients ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT false;

-- Allow clients to update their own record (for settings page)
CREATE POLICY "clients_self_update" ON clients
    FOR UPDATE USING (auth_user_id = auth.uid())
    WITH CHECK (auth_user_id = auth.uid());
