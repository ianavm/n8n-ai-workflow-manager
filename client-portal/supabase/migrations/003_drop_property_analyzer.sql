-- 003_drop_property_analyzer.sql
-- Remove Property Analyzer feature: tables, RLS policies, and storage

-- Drop RLS policies
DROP POLICY IF EXISTS "admins_pa_sources" ON pa_sources;
DROP POLICY IF EXISTS "admins_pa_scores" ON pa_scores;
DROP POLICY IF EXISTS "admins_pa_enrichment" ON pa_enrichment_data;
DROP POLICY IF EXISTS "admins_pa_geocode" ON pa_geocode;
DROP POLICY IF EXISTS "admins_pa_facts" ON pa_extracted_facts;
DROP POLICY IF EXISTS "admins_pa_runs" ON property_analysis_runs;

-- Drop tables (child tables first for FK constraints)
DROP TABLE IF EXISTS pa_sources CASCADE;
DROP TABLE IF EXISTS pa_scores CASCADE;
DROP TABLE IF EXISTS pa_enrichment_data CASCADE;
DROP TABLE IF EXISTS pa_geocode CASCADE;
DROP TABLE IF EXISTS pa_extracted_facts CASCADE;
DROP TABLE IF EXISTS property_analysis_runs CASCADE;

-- Clean up storage bucket
DELETE FROM storage.objects WHERE bucket_id = 'property-docs';
DELETE FROM storage.buckets WHERE id = 'property-docs';
