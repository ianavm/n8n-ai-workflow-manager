-- Migration 016: Security Hardening
-- Date: 2026-03-25
-- Fixes: WhatsApp INSERT policy, auth.uid() optimization, renewal_pipeline access,
--        admin_users INSERT deny, clients_self_update restriction, FK cascades
-- Source: Full security audit 2026-03-25

-- ============================================
-- FIX C-2: WhatsApp INSERT policy (was WITH CHECK (true))
-- ============================================
DROP POLICY IF EXISTS "service_insert_whatsapp" ON whatsapp_connections;
CREATE POLICY "service_insert_whatsapp" ON whatsapp_connections
    FOR INSERT WITH CHECK (auth.role() = 'service_role');

-- ============================================
-- FIX H-1: Optimize auth.uid() -> (SELECT auth.uid())
-- Prevents per-row function evaluation on large tables
-- ============================================

-- 001_initial_schema policies
DROP POLICY IF EXISTS "clients_own_data" ON clients;
CREATE POLICY "clients_own_data" ON clients
    FOR SELECT USING (auth_user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS "clients_own_workflows" ON workflows;
CREATE POLICY "clients_own_workflows" ON workflows
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "clients_own_stats" ON stat_events;
CREATE POLICY "clients_own_stats" ON stat_events
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "clients_own_executions" ON workflow_executions;
CREATE POLICY "clients_own_executions" ON workflow_executions
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admins_own_data" ON admin_users;
CREATE POLICY "admins_own_data" ON admin_users
    FOR SELECT USING (auth_user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS "admins_all_clients" ON clients;
CREATE POLICY "admins_all_clients" ON clients
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admins_all_workflows" ON workflows;
CREATE POLICY "admins_all_workflows" ON workflows
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admins_all_stats" ON stat_events;
CREATE POLICY "admins_all_stats" ON stat_events
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admins_all_executions" ON workflow_executions;
CREATE POLICY "admins_all_executions" ON workflow_executions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admins_all_notes" ON client_notes;
CREATE POLICY "admins_all_notes" ON client_notes
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admins_all_activity" ON activity_log;
CREATE POLICY "admins_all_activity" ON activity_log
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

-- 004_signup_fields policies
DROP POLICY IF EXISTS "clients_self_update" ON clients;
-- Recreated below with column restrictions (M-3)

-- 005_agent_profiles policies
DROP POLICY IF EXISTS "client_own_agent_profiles" ON agent_profiles;
CREATE POLICY "client_own_agent_profiles" ON agent_profiles
    FOR SELECT USING (client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid())));

DROP POLICY IF EXISTS "client_update_agent_profiles" ON agent_profiles;
CREATE POLICY "client_update_agent_profiles" ON agent_profiles
    FOR UPDATE USING (client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid())))
    WITH CHECK (client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid())));

DROP POLICY IF EXISTS "admin_all_agent_profiles" ON agent_profiles;
CREATE POLICY "admin_all_agent_profiles" ON agent_profiles
    FOR ALL USING (EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid())));

-- 006_billing_schema policies
DROP POLICY IF EXISTS "client_own_subscriptions" ON subscriptions;
CREATE POLICY "client_own_subscriptions" ON subscriptions
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_all_subscriptions" ON subscriptions;
CREATE POLICY "admin_all_subscriptions" ON subscriptions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "client_own_invoices" ON invoices;
CREATE POLICY "client_own_invoices" ON invoices
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_all_invoices" ON invoices;
CREATE POLICY "admin_all_invoices" ON invoices
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "client_own_payment_methods" ON payment_methods;
CREATE POLICY "client_own_payment_methods" ON payment_methods
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_all_payment_methods" ON payment_methods;
CREATE POLICY "admin_all_payment_methods" ON payment_methods
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "client_own_usage" ON usage_records;
CREATE POLICY "client_own_usage" ON usage_records
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_all_usage" ON usage_records;
CREATE POLICY "admin_all_usage" ON usage_records
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

-- 007_orchestrator_dashboard policies
DROP POLICY IF EXISTS "admin_agent_status" ON agent_status;
CREATE POLICY "admin_agent_status" ON agent_status
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_orchestrator_alerts" ON orchestrator_alerts;
CREATE POLICY "admin_orchestrator_alerts" ON orchestrator_alerts
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_kpi_snapshots" ON kpi_snapshots;
CREATE POLICY "admin_kpi_snapshots" ON kpi_snapshots
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

-- 008_client_relations policies
DROP POLICY IF EXISTS "admin_health_scores" ON client_health_scores;
CREATE POLICY "admin_health_scores" ON client_health_scores
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_interactions" ON client_interactions;
CREATE POLICY "admin_interactions" ON client_interactions
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_renewal_pipeline" ON renewal_pipeline;
CREATE POLICY "admin_renewal_pipeline" ON renewal_pipeline
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "client_own_health_scores" ON client_health_scores;
CREATE POLICY "client_own_health_scores" ON client_health_scores
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "client_own_interactions" ON client_interactions;
CREATE POLICY "client_own_interactions" ON client_interactions
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

-- 010_pricing_restructure policies
DROP POLICY IF EXISTS "client_own_subscription_addons" ON subscription_addons;
CREATE POLICY "client_own_subscription_addons" ON subscription_addons
    FOR SELECT USING (
        subscription_id IN (
            SELECT id FROM subscriptions
            WHERE client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
        )
    );

DROP POLICY IF EXISTS "admin_all_subscription_addons" ON subscription_addons;
CREATE POLICY "admin_all_subscription_addons" ON subscription_addons
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "client_own_setup_fees" ON setup_fees;
CREATE POLICY "client_own_setup_fees" ON setup_fees
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_all_setup_fees" ON setup_fees;
CREATE POLICY "admin_all_setup_fees" ON setup_fees
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

-- 014_whatsapp_connections policies
DROP POLICY IF EXISTS "client_own_whatsapp" ON whatsapp_connections;
CREATE POLICY "client_own_whatsapp" ON whatsapp_connections
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "client_update_whatsapp" ON whatsapp_connections;
CREATE POLICY "client_update_whatsapp" ON whatsapp_connections
    FOR UPDATE USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    )
    WITH CHECK (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

DROP POLICY IF EXISTS "admin_all_whatsapp" ON whatsapp_connections;
CREATE POLICY "admin_all_whatsapp" ON whatsapp_connections
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = (SELECT auth.uid()))
    );

-- ============================================
-- FIX H-2: Add client SELECT on renewal_pipeline
-- ============================================
CREATE POLICY "client_own_renewal_pipeline" ON renewal_pipeline
    FOR SELECT USING (
        client_id IN (SELECT id FROM clients WHERE auth_user_id = (SELECT auth.uid()))
    );

-- ============================================
-- FIX H-3: Explicit INSERT deny on admin_users
-- Prevents privilege escalation via direct Supabase client
-- ============================================
CREATE POLICY "deny_client_insert_admin" ON admin_users
    FOR INSERT WITH CHECK (false);

-- ============================================
-- FIX M-3: Restrict clients_self_update to safe columns
-- Prevents clients from changing their own status, api_key, email_verified
-- ============================================
CREATE POLICY "clients_self_update" ON clients
    FOR UPDATE USING (auth_user_id = (SELECT auth.uid()))
    WITH CHECK (
        auth_user_id = (SELECT auth.uid())
        AND status IS NOT DISTINCT FROM (SELECT c.status FROM clients c WHERE c.auth_user_id = (SELECT auth.uid()))
        AND api_key IS NOT DISTINCT FROM (SELECT c.api_key FROM clients c WHERE c.auth_user_id = (SELECT auth.uid()))
        AND email_verified IS NOT DISTINCT FROM (SELECT c.email_verified FROM clients c WHERE c.auth_user_id = (SELECT auth.uid()))
    );

-- ============================================
-- FIX M-4: FK cascade on client_notes.admin_id
-- Allows admin deletion without orphaning notes
-- ============================================
ALTER TABLE client_notes ALTER COLUMN admin_id DROP NOT NULL;
ALTER TABLE client_notes DROP CONSTRAINT IF EXISTS client_notes_admin_id_fkey;
ALTER TABLE client_notes ADD CONSTRAINT client_notes_admin_id_fkey
    FOREIGN KEY (admin_id) REFERENCES admin_users(id) ON DELETE SET NULL;

-- ============================================
-- FIX M-5: Explicit ON DELETE RESTRICT on subscriptions.plan_id
-- Prevents accidental plan deletion while subscriptions reference it
-- ============================================
ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_plan_id_fkey;
ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_plan_id_fkey
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE RESTRICT;
