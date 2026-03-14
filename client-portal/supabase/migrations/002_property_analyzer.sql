-- ============================================
-- Property Analyzer Schema
-- ============================================

-- 1. ANALYSIS RUNS (master record per analysis)
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
    scoring_weights JSONB DEFAULT '{
        "document_completeness": 0.15,
        "location_amenities": 0.20,
        "crime_safety": 0.20,
        "market_growth": 0.20,
        "deal_financial": 0.20,
        "risk_red_flags": 0.05
    }',
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

CREATE INDEX idx_pa_runs_admin ON property_analysis_runs (admin_user_id, created_at DESC);
CREATE INDEX idx_pa_runs_status ON property_analysis_runs (status);
CREATE INDEX idx_pa_runs_run_id ON property_analysis_runs (run_id);

-- 2. EXTRACTED FACTS (parsed from document)
CREATE TABLE pa_extracted_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    property_address TEXT,
    suburb TEXT,
    city TEXT,
    province TEXT DEFAULT 'Gauteng',
    postal_code TEXT,
    erf_number TEXT,
    title_deed_number TEXT,
    property_type TEXT CHECK (property_type IN (
        'freehold', 'sectional_title', 'estate', 'agricultural',
        'commercial', 'industrial', 'mixed_use', 'vacant_land'
    )),
    zoning TEXT,
    stand_size_sqm NUMERIC(10,2),
    building_size_sqm NUMERIC(10,2),
    bedrooms INTEGER,
    bathrooms NUMERIC(3,1),
    garages INTEGER,
    parking_bays INTEGER,
    pool BOOLEAN DEFAULT false,
    garden BOOLEAN DEFAULT false,
    asking_price_zar NUMERIC(14,2),
    municipal_valuation_zar NUMERIC(14,2),
    monthly_levy_zar NUMERIC(10,2),
    monthly_rates_zar NUMERIC(10,2),
    special_levy_zar NUMERIC(10,2),
    section_number TEXT,
    participation_quota NUMERIC(6,4),
    exclusive_use_areas TEXT,
    body_corporate_name TEXT,
    has_title_deed BOOLEAN DEFAULT false,
    has_rates_clearance BOOLEAN DEFAULT false,
    has_levy_clearance BOOLEAN DEFAULT false,
    has_compliance_certs BOOLEAN DEFAULT false,
    has_building_plans BOOLEAN DEFAULT false,
    has_hoa_rules BOOLEAN DEFAULT false,
    has_valuation_report BOOLEAN DEFAULT false,
    has_offer_to_purchase BOOLEAN DEFAULT false,
    seller_name TEXT,
    seller_type TEXT CHECK (seller_type IN ('private', 'estate_agent', 'bank', 'auction', 'developer')),
    estate_agent TEXT,
    raw_extracted_json JSONB,
    extraction_confidence NUMERIC(5,2),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX idx_pa_facts_run ON pa_extracted_facts (run_id);

-- 3. GEOCODE RESULTS
CREATE TABLE pa_geocode (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    normalized_address TEXT NOT NULL,
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    geocode_confidence NUMERIC(5,2),
    geocode_source TEXT DEFAULT 'nominatim' CHECK (geocode_source IN ('nominatim', 'google', 'manual')),
    suburb_normalized TEXT,
    municipality TEXT,
    ward_number TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX idx_pa_geocode_run ON pa_geocode (run_id);

-- 4. ENRICHMENT DATA (external data gathered)
CREATE TABLE pa_enrichment_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    fetched_at TIMESTAMPTZ DEFAULT now(),
    cache_expires_at TIMESTAMPTZ,
    confidence NUMERIC(5,2),
    error TEXT
);

CREATE INDEX idx_pa_enrichment_run ON pa_enrichment_data (run_id, source);

-- 5. SCORES
CREATE TABLE pa_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    document_completeness NUMERIC(5,2),
    location_amenities NUMERIC(5,2),
    crime_safety NUMERIC(5,2),
    market_growth NUMERIC(5,2),
    deal_financial NUMERIC(5,2),
    risk_red_flags NUMERIC(5,2),
    overall_score NUMERIC(5,2) NOT NULL,
    confidence NUMERIC(5,2) NOT NULL,
    subscore_details JSONB NOT NULL DEFAULT '{}',
    pros JSONB DEFAULT '[]',
    cons JSONB DEFAULT '[]',
    red_flags JSONB DEFAULT '[]',
    unknowns JSONB DEFAULT '[]',
    verdict TEXT NOT NULL CHECK (verdict IN ('strong_buy', 'buy', 'hold', 'caution', 'avoid')),
    verdict_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX idx_pa_scores_run ON pa_scores (run_id);

-- 6. SOURCES / CITATIONS
CREATE TABLE pa_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES property_analysis_runs(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'document', 'api', 'web', 'database', 'calculation'
    )),
    source_name TEXT NOT NULL,
    source_url TEXT,
    retrieved_at TIMESTAMPTZ DEFAULT now(),
    reliability TEXT DEFAULT 'medium' CHECK (reliability IN ('high', 'medium', 'low')),
    snippet TEXT
);

CREATE INDEX idx_pa_sources_run ON pa_sources (run_id);

-- ============================================
-- ROW-LEVEL SECURITY
-- ============================================

ALTER TABLE property_analysis_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_extracted_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_geocode ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_enrichment_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE pa_sources ENABLE ROW LEVEL SECURITY;

-- Admin full access
CREATE POLICY "admins_pa_runs" ON property_analysis_runs
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_pa_facts" ON pa_extracted_facts
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_pa_geocode" ON pa_geocode
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_pa_enrichment" ON pa_enrichment_data
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_pa_scores" ON pa_scores
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "admins_pa_sources" ON pa_sources
    FOR ALL USING (
        EXISTS (SELECT 1 FROM admin_users WHERE auth_user_id = auth.uid())
    );

-- Service role bypass for n8n webhook writes (service role bypasses RLS by default)
-- No additional policies needed - service role key has full access.

-- ============================================
-- Supabase Storage Bucket (run via dashboard or API)
-- INSERT INTO storage.buckets (id, name, public) VALUES ('property-docs', 'property-docs', false);
-- ============================================
