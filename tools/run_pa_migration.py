"""Run Property Analyzer migration via Supabase Management API."""
import requests
import sys
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
PROJECT = os.getenv("SUPABASE_PROJECT_REF", "qfvsqjsrlnxjplqefhon")
URL = f"https://api.supabase.com/v1/projects/{PROJECT}/database/query"
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def run_sql(label, sql):
    r = requests.post(URL, headers=headers, json={"query": sql})
    if r.status_code in (200, 201):
        print(f"  OK: {label}")
        return True
    else:
        print(f"  FAIL: {label} -> {r.status_code}: {r.text[:300]}")
        return False

print("=== Property Analyzer Migration ===\n")

# 1. property_analysis_runs
run_sql("property_analysis_runs", """
CREATE TABLE property_analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    run_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'uploading', 'parsing', 'geocoding', 'enriching',
        'researching', 'scoring', 'reporting', 'completed', 'failed'
    )),
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'jpg', 'png', 'jpeg')),
    file_url TEXT,
    file_size_bytes INTEGER,
    strategy_preset TEXT NOT NULL DEFAULT 'balanced' CHECK (strategy_preset IN (
        'conservative', 'balanced', 'aggressive', 'rental_yield', 'capital_growth'
    )),
    investor_assumptions JSONB DEFAULT '{}',
    scoring_weights JSONB DEFAULT '{"document_completeness":0.15,"location_amenities":0.20,"crime_safety":0.20,"market_growth":0.20,"deal_financial":0.20,"risk_red_flags":0.05}',
    overall_score NUMERIC(5,2),
    confidence_score NUMERIC(5,2),
    verdict TEXT CHECK (verdict IN ('strong_buy', 'buy', 'hold', 'caution', 'avoid')),
    error_message TEXT,
    processing_time_ms INTEGER,
    n8n_execution_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
""")

run_sql("runs indexes", """
CREATE INDEX idx_pa_runs_admin ON property_analysis_runs (admin_user_id, created_at DESC);
CREATE INDEX idx_pa_runs_status ON property_analysis_runs (status);
CREATE INDEX idx_pa_runs_run_id ON property_analysis_runs (run_id);
""")

# 2. pa_extracted_facts
run_sql("pa_extracted_facts", """
CREATE TABLE pa_extracted_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    property_address TEXT, suburb TEXT, city TEXT,
    province TEXT DEFAULT 'Gauteng', postal_code TEXT, erf_number TEXT,
    title_deed_number TEXT,
    property_type TEXT CHECK (property_type IN (
        'freehold', 'sectional_title', 'estate', 'agricultural',
        'commercial', 'industrial', 'mixed_use', 'vacant_land'
    )),
    zoning TEXT,
    stand_size_sqm NUMERIC(10,2), building_size_sqm NUMERIC(10,2),
    bedrooms INTEGER, bathrooms NUMERIC(3,1), garages INTEGER,
    parking_bays INTEGER, pool BOOLEAN DEFAULT false, garden BOOLEAN DEFAULT false,
    asking_price_zar NUMERIC(14,2), municipal_valuation_zar NUMERIC(14,2),
    monthly_levy_zar NUMERIC(10,2), monthly_rates_zar NUMERIC(10,2),
    special_levy_zar NUMERIC(10,2),
    section_number TEXT, participation_quota NUMERIC(6,4),
    exclusive_use_areas TEXT, body_corporate_name TEXT,
    has_title_deed BOOLEAN DEFAULT false, has_rates_clearance BOOLEAN DEFAULT false,
    has_levy_clearance BOOLEAN DEFAULT false, has_compliance_certs BOOLEAN DEFAULT false,
    has_building_plans BOOLEAN DEFAULT false, has_hoa_rules BOOLEAN DEFAULT false,
    has_valuation_report BOOLEAN DEFAULT false, has_offer_to_purchase BOOLEAN DEFAULT false,
    seller_name TEXT,
    seller_type TEXT CHECK (seller_type IN ('private', 'estate_agent', 'bank', 'auction', 'developer')),
    estate_agent TEXT,
    raw_extracted_json JSONB, extraction_confidence NUMERIC(5,2),
    created_at TIMESTAMPTZ DEFAULT now()
);
""")
run_sql("facts index", "CREATE UNIQUE INDEX idx_pa_facts_run ON pa_extracted_facts (run_id);")

# 3. pa_geocode
run_sql("pa_geocode", """
CREATE TABLE pa_geocode (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    normalized_address TEXT NOT NULL,
    latitude NUMERIC(10,7), longitude NUMERIC(10,7),
    geocode_confidence NUMERIC(5,2),
    geocode_source TEXT DEFAULT 'nominatim' CHECK (geocode_source IN ('nominatim', 'google', 'manual')),
    suburb_normalized TEXT, municipality TEXT, ward_number TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
""")
run_sql("geocode index", "CREATE UNIQUE INDEX idx_pa_geocode_run ON pa_geocode (run_id);")

# 4. pa_enrichment_data
run_sql("pa_enrichment_data", """
CREATE TABLE pa_enrichment_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    source TEXT NOT NULL, category TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    fetched_at TIMESTAMPTZ DEFAULT now(), cache_expires_at TIMESTAMPTZ,
    confidence NUMERIC(5,2), error TEXT
);
""")
run_sql("enrichment index", "CREATE INDEX idx_pa_enrichment_run ON pa_enrichment_data (run_id, source);")

# 5. pa_scores
run_sql("pa_scores", """
CREATE TABLE pa_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    document_completeness NUMERIC(5,2), location_amenities NUMERIC(5,2),
    crime_safety NUMERIC(5,2), market_growth NUMERIC(5,2),
    deal_financial NUMERIC(5,2), risk_red_flags NUMERIC(5,2),
    overall_score NUMERIC(5,2) NOT NULL, confidence NUMERIC(5,2) NOT NULL,
    subscore_details JSONB NOT NULL DEFAULT '{}',
    pros JSONB DEFAULT '[]', cons JSONB DEFAULT '[]',
    red_flags JSONB DEFAULT '[]', unknowns JSONB DEFAULT '[]',
    verdict TEXT NOT NULL CHECK (verdict IN ('strong_buy', 'buy', 'hold', 'caution', 'avoid')),
    verdict_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
""")
run_sql("scores index", "CREATE UNIQUE INDEX idx_pa_scores_run ON pa_scores (run_id);")

# 6. pa_sources
run_sql("pa_sources", """
CREATE TABLE pa_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('document', 'api', 'web', 'database', 'calculation')),
    source_name TEXT NOT NULL, source_url TEXT,
    retrieved_at TIMESTAMPTZ DEFAULT now(),
    reliability TEXT DEFAULT 'medium' CHECK (reliability IN ('high', 'medium', 'low')),
    snippet TEXT
);
""")
run_sql("sources index", "CREATE INDEX idx_pa_sources_run ON pa_sources (run_id);")

# 7. RLS
run_sql("enable RLS", """
ALTER TABLE property_analysis_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_extracted_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_geocode ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_enrichment_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_sources ENABLE ROW LEVEL SECURITY;
""")

# 8. RLS policies
tables = [
    ("property_analysis_runs", "admins_pa_runs"),
    ("pa_extracted_facts", "admins_pa_facts"),
    ("pa_geocode", "admins_pa_geocode"),
    ("pa_enrichment_data", "admins_pa_enrichment"),
    ("pa_scores", "admins_pa_scores"),
    ("pa_sources", "admins_pa_sources"),
]
for tbl, name in tables:
    run_sql(f"policy {name}", f"""
CREATE POLICY "{name}" ON {tbl}
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );
""")

# 9. Storage bucket
run_sql("storage bucket", """
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('property-docs', 'property-docs', false, 10485760)
ON CONFLICT (id) DO NOTHING;
""")

# 10. Storage policies
run_sql("storage upload policy", """
CREATE POLICY "admins_upload_property_docs" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'property-docs'
        AND EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );
""")

run_sql("storage read policy", """
CREATE POLICY "admins_read_property_docs" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'property-docs'
        AND EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );
""")

# Verify
r = requests.post(URL, headers=headers, json={"query": "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'pa_%' OR tablename='property_analysis_runs' ORDER BY tablename;"})
print(f"\n=== Verification ===")
if r.status_code in (200, 201):
    for row in r.json():
        print(f"  Table: {row.get('tablename', row)}")
else:
    print(f"  Verify failed: {r.status_code}")

print("\n--- Migration complete ---")
