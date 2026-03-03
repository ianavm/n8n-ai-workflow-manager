"""
Deploy script: Property Analyzer - Plausibility Analysis

Builds n8n workflow JSON for the property viability analysis pipeline.
Pattern: build_nodes() -> build_connections() -> CLI (build/deploy/activate)

Revision notes:
  - Fixed: Webhook response mode (was blocking connection 30-60s)
  - Fixed: Error Handler (was using fetch + referencing unreachable nodes)
  - Fixed: Processing time tracking (request_start was never set)
  - Fixed: Node position overlaps
  - Added: Image vision extraction (JPG/PNG via Claude Sonnet vision)
  - Added: Download failure handling (continueOnFail + check)
  - Added: Strategy-specific scoring weight adjustments
  - Added: LLM extraction field validation
  - Removed: Respond Webhook node (not needed with default response mode)

Usage:
    python tools/deploy_property_analyzer.py build
    python tools/deploy_property_analyzer.py deploy
    python tools/deploy_property_analyzer.py activate
"""

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from credentials import CREDENTIALS

CRED_OPENROUTER = CREDENTIALS["openrouter"]

OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "property-analyzer"

WORKFLOW_NAME = "Property Analyzer - Plausibility Analysis"


def uid():
    return str(uuid.uuid4())


# ============================================================
# LLM Extraction System Prompt
# ============================================================

EXTRACTION_SYSTEM_PROMPT = """You are an expert South African property document analyzer.
Extract structured facts from the provided property document text.

Return ONLY valid JSON matching this schema (use null for unknown fields):
{
  "property_address": string|null,
  "suburb": string|null,
  "city": string|null,
  "province": string|null,
  "postal_code": string|null,
  "erf_number": string|null,
  "title_deed_number": string|null,
  "property_type": "freehold"|"sectional_title"|"estate"|"agricultural"|"commercial"|"industrial"|"mixed_use"|"vacant_land"|null,
  "zoning": string|null,
  "stand_size_sqm": number|null,
  "building_size_sqm": number|null,
  "bedrooms": number|null,
  "bathrooms": number|null,
  "garages": number|null,
  "parking_bays": number|null,
  "pool": boolean,
  "garden": boolean,
  "asking_price_zar": number|null,
  "municipal_valuation_zar": number|null,
  "monthly_levy_zar": number|null,
  "monthly_rates_zar": number|null,
  "special_levy_zar": number|null,
  "section_number": string|null,
  "participation_quota": number|null,
  "exclusive_use_areas": string|null,
  "body_corporate_name": string|null,
  "has_title_deed": boolean,
  "has_rates_clearance": boolean,
  "has_levy_clearance": boolean,
  "has_compliance_certs": boolean,
  "has_building_plans": boolean,
  "has_hoa_rules": boolean,
  "has_valuation_report": boolean,
  "has_offer_to_purchase": boolean,
  "seller_name": string|null,
  "seller_type": "private"|"estate_agent"|"bank"|"auction"|"developer"|null,
  "estate_agent": string|null,
  "extraction_confidence": number (0-100)
}

SA-specific notes:
- ERF = stand number in the deeds registry
- Sectional title = equivalent to condominium/strata
- Levies = body corporate monthly charges
- Rates = municipal property tax
- Voetstoots = sold as-is (auction term)
- All monetary values in ZAR (South African Rand)
"""


# ============================================================
# Scoring Engine (JavaScript for n8n Code node)
# ============================================================

SCORING_ENGINE_JS = r"""
// Property Analyzer Scoring Engine v1.1
// Runs inside n8n Code node

const facts = $input.first().json.extracted_facts || {};
const geocode = $input.first().json.geocode || {};
const amenities = $input.first().json.amenities || {};
const config = $input.first().json.config || {};
const strategyPreset = config.strategy_preset || 'balanced';

// Strategy-specific weight adjustments
const STRATEGY_WEIGHTS = {
  balanced: {
    document_completeness: 0.15,
    location_amenities: 0.20,
    crime_safety: 0.20,
    market_growth: 0.20,
    deal_financial: 0.20,
    risk_red_flags: 0.05
  },
  conservative: {
    document_completeness: 0.15,
    location_amenities: 0.20,
    crime_safety: 0.20,
    market_growth: 0.15,
    deal_financial: 0.15,
    risk_red_flags: 0.15
  },
  aggressive: {
    document_completeness: 0.10,
    location_amenities: 0.15,
    crime_safety: 0.15,
    market_growth: 0.23,
    deal_financial: 0.25,
    risk_red_flags: 0.02
  },
  rental_yield: {
    document_completeness: 0.10,
    location_amenities: 0.20,
    crime_safety: 0.20,
    market_growth: 0.15,
    deal_financial: 0.30,
    risk_red_flags: 0.05
  },
  capital_growth: {
    document_completeness: 0.10,
    location_amenities: 0.20,
    crime_safety: 0.15,
    market_growth: 0.30,
    deal_financial: 0.15,
    risk_red_flags: 0.10
  }
};

const weights = STRATEGY_WEIGHTS[strategyPreset] || STRATEGY_WEIGHTS.balanced;

// Helper
function clamp(val, min, max) { return Math.max(min, Math.min(max, val)); }

// ---- 1. Document Completeness (0-100) ----
function scoreDocumentCompleteness(f) {
  let score = 0;
  const factors = [];
  const checks = [
    ['has_title_deed', 15, 'Title deed present'],
    ['has_rates_clearance', 15, 'Rates clearance certificate'],
    ['has_compliance_certs', 15, 'Compliance certificates'],
    ['has_valuation_report', 15, 'Valuation report included'],
    ['has_building_plans', 10, 'Building plans available'],
    ['has_offer_to_purchase', 15, 'Offer to purchase document'],
  ];

  if (f.property_type === 'sectional_title') {
    checks.push(['has_levy_clearance', 10, 'Levy clearance certificate']);
    checks.push(['has_hoa_rules', 5, 'HOA/Body corporate rules']);
  } else {
    checks[0][1] += 5;
    checks[1][1] += 5;
    checks[2][1] += 5;
  }

  for (const [field, pts, label] of checks) {
    const present = f[field] === true;
    score += present ? pts : 0;
    factors.push({
      name: label,
      impact: present ? 'positive' : 'negative',
      points: present ? pts : 0,
      max_points: pts,
      reason: present ? 'Document present' : 'Document missing',
      source: 'document'
    });
  }

  if (f.extraction_confidence > 90) {
    score += 5;
    factors.push({ name: 'High extraction confidence', impact: 'positive', points: 5, max_points: 5, reason: `Confidence: ${f.extraction_confidence}%`, source: 'extraction' });
  }

  if (!f.property_type) {
    score -= 10;
    factors.push({ name: 'Property type unknown', impact: 'negative', points: -10, max_points: 0, reason: 'Could not determine property type', source: 'extraction' });
  }

  return {
    score: clamp(score, 0, 100),
    weight: weights.document_completeness,
    weighted_score: clamp(score, 0, 100) * weights.document_completeness,
    confidence: f.extraction_confidence || 50,
    factors,
    summary: `${factors.filter(f => f.impact === 'positive').length} of ${checks.length} key documents present`
  };
}

// ---- 2. Location & Amenities (0-100) ----
function scoreLocationAmenities(am) {
  if (!am || Object.keys(am).length === 0) {
    return {
      score: 50, weight: weights.location_amenities, weighted_score: 50 * weights.location_amenities,
      confidence: 20, factors: [{ name: 'No amenity data', impact: 'neutral', points: 50, max_points: 100, reason: 'Enrichment data unavailable; using neutral estimate', source: 'degraded' }],
      summary: 'No amenity data available'
    };
  }

  let score = 0;
  const factors = [];
  const categories = [
    { key: 'schools', maxPts: 15, thresholds: [[3, 15], [1, 10]], label: 'Schools nearby' },
    { key: 'hospitals', maxPts: 15, thresholds: [[2, 15], [1, 10]], label: 'Hospitals/clinics' },
    { key: 'shopping', maxPts: 10, thresholds: [[2, 10], [1, 7]], label: 'Shopping' },
    { key: 'public_transport', maxPts: 15, thresholds: [[3, 15], [1, 10]], label: 'Public transport' },
    { key: 'parks', maxPts: 10, thresholds: [[2, 10], [1, 7]], label: 'Parks' },
    { key: 'banks', maxPts: 5, thresholds: [[1, 5]], label: 'Banks' },
    { key: 'pharmacies', maxPts: 5, thresholds: [[1, 5]], label: 'Pharmacies' },
    { key: 'restaurants', maxPts: 5, thresholds: [[2, 5], [1, 3]], label: 'Restaurants' },
    { key: 'fuel_stations', maxPts: 5, thresholds: [[1, 5]], label: 'Fuel stations' },
    { key: 'gyms', maxPts: 5, thresholds: [[1, 5]], label: 'Gyms' },
  ];

  for (const cat of categories) {
    const items = am[cat.key] || [];
    let pts = 0;
    for (const [threshold, points] of cat.thresholds) {
      if (items.length >= threshold) { pts = points; break; }
    }
    score += pts;
    factors.push({
      name: cat.label, impact: pts > 0 ? 'positive' : 'negative',
      points: pts, max_points: cat.maxPts,
      reason: `${items.length} found within radius`,
      source: 'overpass_api'
    });
  }

  const normalized = clamp(Math.round(score / 90 * 100), 0, 100);
  return {
    score: normalized, weight: weights.location_amenities,
    weighted_score: normalized * weights.location_amenities,
    confidence: 80, factors,
    summary: `${factors.filter(f => f.impact === 'positive').length} of ${categories.length} amenity categories well-served`
  };
}

// ---- 3. Crime & Safety (0-100) ----
function scoreCrimeSafety() {
  return {
    score: 50, weight: weights.crime_safety,
    weighted_score: 50 * weights.crime_safety,
    confidence: 15,
    factors: [{ name: 'Crime data pending', impact: 'neutral', points: 50, max_points: 100, reason: 'SAPS crime data integration pending (Phase 2)', source: 'degraded' }],
    summary: 'Crime data not yet integrated - using neutral estimate'
  };
}

// ---- 4. Market & Growth (0-100) ----
function scoreMarketGrowth() {
  return {
    score: 50, weight: weights.market_growth,
    weighted_score: 50 * weights.market_growth,
    confidence: 15,
    factors: [{ name: 'Market data pending', impact: 'neutral', points: 50, max_points: 100, reason: 'FNB HPI / market data integration pending (Phase 2)', source: 'degraded' }],
    summary: 'Market trend data not yet integrated - using neutral estimate'
  };
}

// ---- 5. Deal Financial Plausibility (0-100) ----
function scoreDealFinancial(f) {
  if (!f.asking_price_zar) {
    return {
      score: 50, weight: weights.deal_financial,
      weighted_score: 50 * weights.deal_financial,
      confidence: 15,
      factors: [{ name: 'No asking price', impact: 'neutral', points: 50, max_points: 100, reason: 'Cannot assess financial viability without price', source: 'degraded' }],
      summary: 'Price unknown - cannot assess deal financials'
    };
  }

  let score = 0;
  const factors = [];

  if (f.municipal_valuation_zar && f.municipal_valuation_zar > 0) {
    const ratio = f.asking_price_zar / f.municipal_valuation_zar;
    let pts;
    if (ratio < 0.9) { pts = 25; }
    else if (ratio <= 1.1) { pts = 20; }
    else if (ratio <= 1.3) { pts = 15; }
    else { pts = 5; }
    score += pts;
    factors.push({ name: 'Price vs valuation', impact: pts >= 20 ? 'positive' : pts >= 15 ? 'neutral' : 'negative', points: pts, max_points: 25, reason: `Ratio: ${ratio.toFixed(2)}x municipal valuation`, source: 'calculation' });
  } else {
    score += 12;
    factors.push({ name: 'Price vs valuation', impact: 'neutral', points: 12, max_points: 25, reason: 'Municipal valuation unknown', source: 'degraded' });
  }

  if (f.building_size_sqm && f.building_size_sqm > 0) {
    const ppsm = f.asking_price_zar / f.building_size_sqm;
    let pts;
    if (ppsm < 15000) { pts = 20; }
    else if (ppsm <= 25000) { pts = 15; }
    else { pts = 8; }
    score += pts;
    factors.push({ name: 'Price per sqm', impact: pts >= 15 ? 'positive' : 'neutral', points: pts, max_points: 20, reason: `R${Math.round(ppsm).toLocaleString()}/m2`, source: 'calculation' });
  }

  const monthlyRent = config.investor_assumptions?.estimated_monthly_rental_zar;
  const monthlyCosts = (f.monthly_levy_zar || 0) + (f.monthly_rates_zar || 0);
  if (monthlyRent && monthlyRent > 0 && monthlyCosts > 0) {
    const costRatio = monthlyCosts / monthlyRent;
    let pts;
    if (costRatio < 0.3) { pts = 20; }
    else if (costRatio <= 0.5) { pts = 15; }
    else { pts = 5; }
    score += pts;
    factors.push({ name: 'Costs vs rental income', impact: pts >= 15 ? 'positive' : 'negative', points: pts, max_points: 20, reason: `Monthly costs are ${Math.round(costRatio * 100)}% of estimated rent`, source: 'calculation' });
  }

  const finalScore = clamp(Math.round(score / 65 * 100), 0, 100);
  return {
    score: finalScore, weight: weights.deal_financial,
    weighted_score: finalScore * weights.deal_financial,
    confidence: f.municipal_valuation_zar ? 70 : 40,
    factors,
    summary: `Financial assessment based on ${factors.length} available metrics`
  };
}

// ---- 6. Risk & Red Flags (0-100, 100 = no risks) ----
function scoreRiskRedFlags(f) {
  let score = 100;
  const factors = [];
  const redFlags = [];

  const checks = [
    [!f.has_title_deed, 20, 'Missing title deed', 'high'],
    [!f.has_rates_clearance, 15, 'Missing rates clearance certificate', 'high'],
    [f.seller_type === 'bank' || f.seller_type === 'auction', 10, 'Bank/auction sale (potential distress indicator)', 'medium'],
    [f.special_levy_zar && f.special_levy_zar > 0, 10, 'Active special levy', 'medium'],
    [f.asking_price_zar && f.municipal_valuation_zar && f.asking_price_zar > 2 * f.municipal_valuation_zar, 20, 'Price exceeds 2x municipal valuation', 'high'],
    [f.extraction_confidence && f.extraction_confidence < 50, 15, 'Low document extraction confidence', 'medium'],
  ];

  for (const [condition, penalty, desc, severity] of checks) {
    if (condition) {
      score -= penalty;
      factors.push({ name: desc, impact: 'negative', points: -penalty, max_points: 0, reason: desc, source: 'analysis' });
      redFlags.push({ text: desc, severity, source: 'automated_analysis' });
    }
  }

  score = clamp(score, 0, 100);
  return {
    score, weight: weights.risk_red_flags,
    weighted_score: score * weights.risk_red_flags,
    confidence: 75,
    factors,
    summary: redFlags.length === 0 ? 'No significant red flags detected' : `${redFlags.length} risk factor(s) identified`,
    _red_flags: redFlags
  };
}

// ---- Compute all subscores ----
const docScore = scoreDocumentCompleteness(facts);
const locScore = scoreLocationAmenities(amenities);
const crimeScore = scoreCrimeSafety();
const marketScore = scoreMarketGrowth();
const dealScore = scoreDealFinancial(facts);
const riskScore = scoreRiskRedFlags(facts);

const subscores = {
  document_completeness: docScore,
  location_amenities: locScore,
  crime_safety: crimeScore,
  market_growth: marketScore,
  deal_financial: dealScore,
  risk_red_flags: riskScore
};

const overallScore = Math.round(
  docScore.weighted_score +
  locScore.weighted_score +
  crimeScore.weighted_score +
  marketScore.weighted_score +
  dealScore.weighted_score +
  riskScore.weighted_score
);

const extractionConf = facts.extraction_confidence || 50;
const geocodeConf = geocode.geocode_confidence || 30;
const sourcesAvailable = [docScore, locScore, crimeScore, marketScore, dealScore].filter(s => s.confidence > 30).length;
const totalSources = 5;
let confidence = Math.round(extractionConf * 0.3 + geocodeConf * 0.2 + (sourcesAvailable / totalSources) * 50);
confidence = clamp(confidence, 15, 100);

let verdict;
const hasCritical = riskScore._red_flags.some(f => f.severity === 'critical');
if (hasCritical) { verdict = 'caution'; }
else if (overallScore >= 80 && confidence >= 60) { verdict = 'strong_buy'; }
else if (overallScore >= 65 && confidence >= 50) { verdict = 'buy'; }
else if (overallScore >= 50 && confidence >= 40) { verdict = 'hold'; }
else if (overallScore >= 35) { verdict = 'caution'; }
else { verdict = 'avoid'; }

const verdictLabels = { strong_buy: 'Strong Buy', buy: 'Buy', hold: 'Hold', caution: 'Caution', avoid: 'Avoid' };

const pros = [];
const cons = [];
for (const [key, detail] of Object.entries(subscores)) {
  for (const f of detail.factors) {
    if (f.impact === 'positive' && f.points > 5) {
      pros.push({ text: f.reason, source: f.source, category: key });
    }
    if (f.impact === 'negative' && f.points < -5) {
      cons.push({ text: f.reason, source: f.source, category: key });
    }
  }
}

const unknowns = [];
if (!facts.asking_price_zar) unknowns.push({ text: 'Confirm asking price / reserve price', category: 'financial', requires_human_check: true });
if (!facts.has_rates_clearance) unknowns.push({ text: 'Confirm rates clearance status', category: 'legal', requires_human_check: true });
if (!facts.has_title_deed) unknowns.push({ text: 'Confirm title deed and ownership', category: 'legal', requires_human_check: true });
if (facts.property_type === 'sectional_title' && !facts.has_levy_clearance) unknowns.push({ text: 'Confirm body corporate financials and levy clearance', category: 'legal', requires_human_check: true });
unknowns.push({ text: 'Confirm current occupancy status', category: 'occupancy', requires_human_check: true });
unknowns.push({ text: 'Confirm structural condition / defects', category: 'physical', requires_human_check: true });
unknowns.push({ text: 'Verify rental comps for the area', category: 'financial', requires_human_check: true });

const failedSources = [crimeScore, marketScore].filter(s => s.confidence <= 20).map(s => s.summary);
const degraded = failedSources.length > 0;

return [{
  json: {
    overall_score: overallScore,
    confidence,
    verdict,
    verdict_summary: `${verdictLabels[verdict]} (Score: ${overallScore}/100, Confidence: ${confidence}%). Strategy: ${strategyPreset}.${degraded ? ' Note: Some data sources unavailable; scores may improve with more data.' : ''}`,
    subscores,
    pros,
    cons,
    red_flags: riskScore._red_flags,
    unknowns,
    scoring_metadata: {
      strategy_preset: strategyPreset,
      weights_used: weights,
      data_sources_available: ['document', 'overpass_api'],
      data_sources_failed: failedSources.length > 0 ? ['saps_crime', 'fnb_hpi', 'statssa'] : [],
      degradation_applied: degraded,
      degradation_reason: degraded ? 'Crime, market, and economic data sources not yet integrated' : null
    }
  }
}];
"""


# ============================================================
# Node builders
# ============================================================

def build_nodes():
    nodes = []
    y = 0

    # ---- 1a. Webhook trigger ----
    nodes.append({
        "parameters": {
            "path": "property-analyzer/analyze",
            "httpMethod": "POST",
            "options": {}
        },
        "id": uid(),
        "name": "Analysis Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [0, y],
        "webhookId": uid(),
    })

    # ---- 1b. Manual trigger ----
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Test Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [0, y + 200],
    })

    # ---- 1c. Set test data ----
    nodes.append({
        "parameters": {
            "mode": "raw",
            "jsonOutput": json.dumps({
                "body": {
                    "run_id": "PA-TEST-000001",
                    "db_run_id": "00000000-0000-0000-0000-000000000000",
                    "file_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
                    "file_type": "pdf",
                    "file_name": "test-property-brochure.pdf",
                    "config": {
                        "strategy_preset": "balanced",
                        "investor_assumptions": {
                            "deposit_pct": 10,
                            "interest_rate_pct": 11.75,
                            "loan_term_years": 20,
                            "estimated_monthly_rental_zar": None,
                        },
                        "scoring_weights": {
                            "document_completeness": 0.15,
                            "location_amenities": 0.20,
                            "crime_safety": 0.20,
                            "market_growth": 0.20,
                            "deal_financial": 0.20,
                            "risk_red_flags": 0.05,
                        },
                    },
                    "callback_url": "https://portal.anyvisionmedia.com/api/property-analyzer/webhook",
                    "callback_secret": "TEST_SECRET_REPLACE_ME",
                }
            }),
            "options": {}
        },
        "id": uid(),
        "name": "Set Test Data",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [220, y + 200],
    })

    # ---- 2. Normalize Input ----
    nodes.append({
        "parameters": {
            "jsCode": """// Works for both webhook trigger and manual test trigger
const input = $input.first().json;
const body = input.body || input;

// Store callback info in staticData for error handler access
// (Error Trigger runs in separate context, can't reference upstream nodes)
const staticData = $getWorkflowStaticData('global');
staticData.callback_url = body.callback_url || '';
staticData.callback_secret = body.callback_secret || '';
staticData.run_id = body.run_id || '';
staticData.request_start = Date.now();

return [{ json: { body: { ...body, request_start: Date.now() } } }];
"""
        },
        "id": uid(),
        "name": "Normalize Input",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [220, y],
    })

    # ---- 3. Update status -> parsing ----
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.body.callback_url }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $json.body.callback_secret }}"},
                    {"name": "Content-Type", "value": "application/json"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={ "run_id": "{{ $json.body.run_id }}", "status": "parsing" }',
            "options": {"timeout": 10000}
        },
        "id": uid(),
        "name": "Update Status Parsing",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [440, y],
        "onError": "continueRegularOutput",
    })

    # ---- 4. Download File ----
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "={{ $('Normalize Input').first().json.body.file_url }}",
            "options": {
                "response": {"response": {"responseFormat": "file"}},
                "allowUnauthorizedCerts": True,
            }
        },
        "id": uid(),
        "name": "Download File",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, y],
        "continueOnFail": True,
    })

    # ---- 4a. Check Download ----
    nodes.append({
        "parameters": {
            "jsCode": """const input = $input.first().json;
const webhookData = $('Normalize Input').first().json.body;

const hasBinary = Object.keys($input.first().binary || {}).length > 0;
const hasError = input.error || input.code >= 400;

if (!hasBinary || hasError) {
  const errorMsg = input.error?.message || input.message || 'File download failed - the signed URL may have expired';
  try {
    await this.helpers.httpRequest({
      method: 'POST',
      url: webhookData.callback_url,
      headers: {
        'Authorization': 'Bearer ' + webhookData.callback_secret,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        run_id: webhookData.run_id,
        status: 'failed',
        error_message: errorMsg
      })
    });
  } catch (e) { /* callback failed too */ }

  throw new Error(errorMsg);
}

return [{ json: { download_ok: true, file_type: webhookData.file_type }, binary: $input.first().binary }];
"""
        },
        "id": uid(),
        "name": "Check Download",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, y],
    })

    # ---- 4b. Is Image? ----
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $('Normalize Input').first().json.body.file_type }}",
                        "rightValue": "pdf",
                        "operator": {"type": "string", "operation": "notEquals"}
                    },
                    {
                        "leftValue": "={{ $('Normalize Input').first().json.body.file_type }}",
                        "rightValue": "docx",
                        "operator": {"type": "string", "operation": "notEquals"}
                    }
                ],
                "combinator": "and"
            }
        },
        "id": uid(),
        "name": "Is Image?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [1100, y],
    })

    # ---- IMAGE PATH (true branch) ----

    system_prompt_for_vision = json.dumps(EXTRACTION_SYSTEM_PROMPT)
    nodes.append({
        "parameters": {
            "jsCode": f"""// Build vision LLM request for image-based property documents
const binaryData = await this.helpers.getBinaryDataBuffer(0, 'data');
const base64 = binaryData.toString('base64');
const fileType = $('Normalize Input').first().json.body.file_type || 'jpeg';
const mimeType = fileType === 'png' ? 'image/png' : 'image/jpeg';

const systemPrompt = {system_prompt_for_vision};

return [{{
  json: {{
    model: 'anthropic/claude-sonnet-4-20250514',
    messages: [
      {{ role: 'system', content: systemPrompt }},
      {{
        role: 'user',
        content: [
          {{
            type: 'image_url',
            image_url: {{ url: 'data:' + mimeType + ';base64,' + base64 }}
          }},
          {{
            type: 'text',
            text: 'Extract all property facts from this property document image. Return ONLY the JSON object.'
          }}
        ]
      }}
    ],
    max_tokens: 4000,
    temperature: 0.1
  }}
}}];
"""
        },
        "id": uid(),
        "name": "Build Vision Request",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, y + 200],
    })

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json) }}",
            "options": {"timeout": 60000}
        },
        "id": uid(),
        "name": "Vision LLM Extract",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1320, y + 200],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000,
    })

    # ---- DOCUMENT PATH (false branch) ----

    nodes.append({
        "parameters": {"operation": "text", "options": {}},
        "id": uid(),
        "name": "Extract From File",
        "type": "n8n-nodes-base.extractFromFile",
        "typeVersion": 1,
        "position": [1320, y],
    })

    nodes.append({
        "parameters": {
            "jsCode": """
const extractedItem = $input.first();
let textContent = extractedItem.json.data || extractedItem.json.text || '';

if (!textContent || textContent.trim().length < 20) {
  textContent = '[No text could be extracted from this document. It may be a scanned image or contain only graphics.]';
}

textContent = textContent.replace(/[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]/g, ' ');

if (textContent.length > 30000) {
  textContent = textContent.substring(0, 30000) + '\\n[TRUNCATED]';
}

return [{ json: { text_content: textContent, text_length: textContent.length } }];
"""
        },
        "id": uid(),
        "name": "Extract Text",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1540, y],
    })

    system_prompt_escaped = json.dumps(EXTRACTION_SYSTEM_PROMPT)
    nodes.append({
        "parameters": {
            "jsCode": f"""
const textContent = $json.text_content || '';
const systemPrompt = {system_prompt_escaped};

return [{{
  json: {{
    model: 'anthropic/claude-sonnet-4-20250514',
    messages: [
      {{ role: 'system', content: systemPrompt }},
      {{ role: 'user', content: 'Extract property facts from the following document text:\\n\\n' + textContent }}
    ],
    max_tokens: 4000,
    temperature: 0.1,
    response_format: {{ type: 'json_object' }}
  }}
}}];
"""
        },
        "id": uid(),
        "name": "Build LLM Request",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1760, y],
    })

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json) }}",
            "options": {"timeout": 60000}
        },
        "id": uid(),
        "name": "LLM Extract Facts",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1980, y],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000,
    })

    # ---- MERGED PATH ----

    nodes.append({
        "parameters": {
            "jsCode": """
const llmResponse = $input.first().json;
const prevData = $('Normalize Input').first().json.body;

let extracted;
try {
  const content = llmResponse.choices[0].message.content;
  let jsonStr = content;
  if (jsonStr.includes('```')) {
    jsonStr = jsonStr.replace(/```json?\\n?/g, '').replace(/```/g, '').trim();
  }
  extracted = JSON.parse(jsonStr);
} catch (e) {
  extracted = {
    property_address: null, suburb: null, city: null, province: 'Gauteng',
    extraction_confidence: 10,
  };
}

// Field validation
const VALID_PROPERTY_TYPES = ['freehold', 'sectional_title', 'estate', 'agricultural', 'commercial', 'industrial', 'mixed_use', 'vacant_land'];
const VALID_SELLER_TYPES = ['private', 'estate_agent', 'bank', 'auction', 'developer'];

if (extracted.property_type && !VALID_PROPERTY_TYPES.includes(extracted.property_type)) {
  extracted.property_type = null;
}
if (extracted.seller_type && !VALID_SELLER_TYPES.includes(extracted.seller_type)) {
  extracted.seller_type = null;
}

if (typeof extracted.extraction_confidence === 'number') {
  extracted.extraction_confidence = Math.max(0, Math.min(100, extracted.extraction_confidence));
} else {
  extracted.extraction_confidence = 30;
}

const numericFields = ['asking_price_zar', 'municipal_valuation_zar', 'monthly_levy_zar', 'monthly_rates_zar', 'special_levy_zar', 'stand_size_sqm', 'building_size_sqm'];
for (const field of numericFields) {
  if (extracted[field] != null && (typeof extracted[field] !== 'number' || extracted[field] < 0)) {
    extracted[field] = null;
  }
}

const boolFields = ['pool', 'garden', 'has_title_deed', 'has_rates_clearance', 'has_levy_clearance', 'has_compliance_certs', 'has_building_plans', 'has_hoa_rules', 'has_valuation_report', 'has_offer_to_purchase'];
for (const field of boolFields) {
  extracted[field] = extracted[field] === true;
}

const parts = [extracted.property_address, extracted.suburb, extracted.city, extracted.province].filter(Boolean);
const address_for_geocode = parts.join(', ') || 'Unknown, South Africa';

return [{
  json: {
    extracted_facts: extracted,
    address_for_geocode,
    run_id: prevData.run_id,
    config: prevData.config,
    callback_url: prevData.callback_url,
    callback_secret: prevData.callback_secret,
    request_start: prevData.request_start,
  }
}];
"""
        },
        "id": uid(),
        "name": "Validate Extraction",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2200, y],
    })

    # ---- Geocoding ----

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.callback_url }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $json.callback_secret }}"},
                    {"name": "Content-Type", "value": "application/json"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={ "run_id": "{{ $json.run_id }}", "status": "geocoding", "extracted_facts": {{ JSON.stringify($json.extracted_facts) }} }',
            "options": {"timeout": 10000}
        },
        "id": uid(),
        "name": "Update Status Geocoding",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2420, y],
        "onError": "continueRegularOutput",
    })

    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://nominatim.openstreetmap.org/search?q={{ encodeURIComponent($('Validate Extraction').first().json.address_for_geocode) }}&format=json&countrycodes=za&limit=1",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "User-Agent", "value": "AnyVisionPropertyAnalyzer/1.0 (ian@anyvisionmedia.com)"}
                ]
            },
            "options": {"timeout": 10000}
        },
        "id": uid(),
        "name": "Nominatim Geocode",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2640, y],
        "onError": "continueRegularOutput",
    })

    nodes.append({
        "parameters": {
            "jsCode": """
const geoResults = $input.first().json;
const prev = $('Validate Extraction').first().json;
const results = Array.isArray(geoResults) ? geoResults : [];

let geocode;
if (results.length > 0) {
  const r = results[0];
  geocode = {
    normalized_address: r.display_name || prev.address_for_geocode,
    latitude: parseFloat(r.lat),
    longitude: parseFloat(r.lon),
    geocode_confidence: Math.min(100, parseFloat(r.importance || 0.5) * 100),
    geocode_source: 'nominatim',
    suburb_normalized: prev.extracted_facts.suburb,
    municipality: null,
    ward_number: null
  };
} else {
  geocode = {
    normalized_address: prev.address_for_geocode,
    latitude: null, longitude: null,
    geocode_confidence: 0,
    geocode_source: 'nominatim',
    suburb_normalized: null, municipality: null, ward_number: null
  };
}

return [{ json: { ...prev, geocode } }];
"""
        },
        "id": uid(),
        "name": "Process Geocode",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2860, y],
    })

    # ---- Enrichment ----

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.callback_url }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $json.callback_secret }}"},
                    {"name": "Content-Type", "value": "application/json"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={ "run_id": "{{ $json.run_id }}", "status": "enriching", "geocode": {{ JSON.stringify($json.geocode) }} }',
            "options": {"timeout": 10000}
        },
        "id": uid(),
        "name": "Update Status Enriching",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [3080, y],
        "onError": "continueRegularOutput",
    })

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://overpass-api.de/api/interpreter",
            "sendBody": True,
            "contentType": "raw",
            "rawContentType": "text/plain",
            "body": """={{ (() => {
const lat = $('Process Geocode').first().json.geocode.latitude;
const lon = $('Process Geocode').first().json.geocode.longitude;
if (!lat || !lon) return 'out:json;';
return `
[out:json][timeout:25];
(
  node["amenity"="school"](around:2000,${lat},${lon});
  node["amenity"="hospital"](around:5000,${lat},${lon});
  node["amenity"="clinic"](around:5000,${lat},${lon});
  node["shop"="supermarket"](around:2000,${lat},${lon});
  node["shop"="mall"](around:3000,${lat},${lon});
  node["amenity"="restaurant"](around:2000,${lat},${lon});
  node["leisure"="park"](around:1000,${lat},${lon});
  node["public_transport"="station"](around:1000,${lat},${lon});
  node["highway"="bus_stop"](around:1000,${lat},${lon});
  node["amenity"="bank"](around:2000,${lat},${lon});
  node["amenity"="pharmacy"](around:2000,${lat},${lon});
  node["amenity"="fuel"](around:3000,${lat},${lon});
  node["leisure"="fitness_centre"](around:3000,${lat},${lon});
);
out body;`;
})() }}""",
            "options": {"timeout": 30000}
        },
        "id": uid(),
        "name": "Overpass POI Query",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [3300, y],
        "onError": "continueRegularOutput",
    })

    nodes.append({
        "parameters": {
            "jsCode": """
const overpassData = $input.first().json;
const prev = $('Process Geocode').first().json;
const lat = prev.geocode.latitude;
const lon = prev.geocode.longitude;

function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLon/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function categorize(tags) {
  if (tags.amenity === 'school') return 'schools';
  if (tags.amenity === 'hospital' || tags.amenity === 'clinic') return 'hospitals';
  if (tags.shop === 'supermarket' || tags.shop === 'mall') return 'shopping';
  if (tags.amenity === 'restaurant') return 'restaurants';
  if (tags.leisure === 'park') return 'parks';
  if (tags.public_transport === 'station' || tags.highway === 'bus_stop') return 'public_transport';
  if (tags.amenity === 'bank') return 'banks';
  if (tags.amenity === 'pharmacy') return 'pharmacies';
  if (tags.amenity === 'fuel') return 'fuel_stations';
  if (tags.leisure === 'fitness_centre') return 'gyms';
  return null;
}

const amenities = {
  schools: [], hospitals: [], shopping: [], restaurants: [], parks: [],
  public_transport: [], banks: [], pharmacies: [], fuel_stations: [], gyms: []
};

const elements = overpassData?.elements || [];
for (const el of elements) {
  if (!el.tags || !el.lat) continue;
  const cat = categorize(el.tags);
  if (!cat) continue;
  const dist = lat && lon ? haversine(lat, lon, el.lat, el.lon) : 999;
  amenities[cat].push({
    name: el.tags.name || el.tags.amenity || el.tags.shop || 'Unnamed',
    type: cat,
    distance_km: Math.round(dist * 100) / 100,
    lat: el.lat, lon: el.lon,
    osm_id: String(el.id)
  });
}

for (const key of Object.keys(amenities)) {
  amenities[key].sort((a, b) => a.distance_km - b.distance_km);
}

return [{ json: { ...prev, amenities, total_pois: elements.length } }];
"""
        },
        "id": uid(),
        "name": "Process POI Results",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3520, y],
    })

    # ---- Scoring ----

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.callback_url }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $json.callback_secret }}"},
                    {"name": "Content-Type", "value": "application/json"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={ "run_id": "{{ $json.run_id }}", "status": "scoring", "enrichment": [{ "source": "overpass", "category": "amenities", "data": {{ JSON.stringify($json.amenities) }}, "confidence": {{ $json.geocode.latitude ? 80 : 0 }} }] }""",
            "options": {"timeout": 10000}
        },
        "id": uid(),
        "name": "Update Status Scoring",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [3740, y],
        "onError": "continueRegularOutput",
    })

    nodes.append({
        "parameters": {"jsCode": SCORING_ENGINE_JS},
        "id": uid(),
        "name": "Compute Scores",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3960, y],
    })

    # ---- Final ----

    nodes.append({
        "parameters": {
            "jsCode": """
const scores = $input.first().json;
const prev = $('Process POI Results').first().json;

const enrichment = [{
  source: 'overpass', category: 'amenities',
  data: prev.amenities, confidence: prev.geocode.latitude ? 80 : 0
}];

const sources = [
  { source_type: 'document', source_name: 'Uploaded property document', reliability: 'high' },
  { source_type: 'api', source_name: 'Nominatim Geocoding (OpenStreetMap)', source_url: 'https://nominatim.openstreetmap.org', reliability: 'high' },
  { source_type: 'api', source_name: 'Overpass API (OpenStreetMap POIs)', source_url: 'https://overpass-api.de', reliability: 'high' },
  { source_type: 'api', source_name: 'OpenRouter / Claude Sonnet', source_url: 'https://openrouter.ai', reliability: 'high' },
  { source_type: 'calculation', source_name: 'Scoring Engine v1.1', reliability: 'high' },
];

const staticData = $getWorkflowStaticData('global');
const requestStart = prev.request_start || staticData.request_start || Date.now();
const processingTimeMs = Date.now() - requestStart;

return [{
  json: {
    run_id: prev.run_id,
    callback_url: prev.callback_url,
    callback_secret: prev.callback_secret,
    scores, enrichment, sources,
    extracted_facts: prev.extracted_facts,
    geocode: prev.geocode,
    processing_time_ms: processingTimeMs,
  }
}];
"""
        },
        "id": uid(),
        "name": "Build Final Payload",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [4180, y],
    })

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.callback_url }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "=Bearer {{ $json.callback_secret }}"},
                    {"name": "Content-Type", "value": "application/json"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={{ JSON.stringify({
  run_id: $json.run_id,
  status: 'completed',
  extracted_facts: $json.extracted_facts,
  geocode: $json.geocode,
  enrichment: $json.enrichment,
  scores: $json.scores,
  sources: $json.sources,
  processing_time_ms: $json.processing_time_ms,
  n8n_execution_id: $execution.id
}) }}""",
            "options": {"timeout": 15000}
        },
        "id": uid(),
        "name": "Send Completed",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [4400, y],
        "onError": "continueRegularOutput",
    })

    # ---- Error handling ----

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": [2200, y + 400],
    })

    nodes.append({
        "parameters": {
            "jsCode": """
const error = $input.first().json;

// Read callback info from staticData (set by Normalize Input node)
const staticData = $getWorkflowStaticData('global');
const callbackUrl = staticData.callback_url;
const callbackSecret = staticData.callback_secret;
const runId = staticData.run_id;

if (callbackUrl && callbackSecret && runId) {
  try {
    await this.helpers.httpRequest({
      method: 'POST',
      url: callbackUrl,
      headers: {
        'Authorization': 'Bearer ' + callbackSecret,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        run_id: runId,
        status: 'failed',
        error_message: error.message || 'Unknown workflow error',
        n8n_execution_id: $execution.id
      })
    });
  } catch (e) {
    // Callback failed too
  }
}

return [{ json: { error: true, message: error.message, run_id: runId } }];
"""
        },
        "id": uid(),
        "name": "Error Handler",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2420, y + 400],
    })

    return nodes


def build_connections():
    return {
        "Analysis Webhook": {
            "main": [[{"node": "Normalize Input", "type": "main", "index": 0}]]
        },
        "Manual Test Trigger": {
            "main": [[{"node": "Set Test Data", "type": "main", "index": 0}]]
        },
        "Set Test Data": {
            "main": [[{"node": "Normalize Input", "type": "main", "index": 0}]]
        },
        "Normalize Input": {
            "main": [[{"node": "Update Status Parsing", "type": "main", "index": 0}]]
        },
        "Update Status Parsing": {
            "main": [[{"node": "Download File", "type": "main", "index": 0}]]
        },
        "Download File": {
            "main": [[{"node": "Check Download", "type": "main", "index": 0}]]
        },
        "Check Download": {
            "main": [[{"node": "Is Image?", "type": "main", "index": 0}]]
        },
        "Is Image?": {
            "main": [
                [{"node": "Build Vision Request", "type": "main", "index": 0}],
                [{"node": "Extract From File", "type": "main", "index": 0}],
            ]
        },
        "Build Vision Request": {
            "main": [[{"node": "Vision LLM Extract", "type": "main", "index": 0}]]
        },
        "Vision LLM Extract": {
            "main": [[{"node": "Validate Extraction", "type": "main", "index": 0}]]
        },
        "Extract From File": {
            "main": [[{"node": "Extract Text", "type": "main", "index": 0}]]
        },
        "Extract Text": {
            "main": [[{"node": "Build LLM Request", "type": "main", "index": 0}]]
        },
        "Build LLM Request": {
            "main": [[{"node": "LLM Extract Facts", "type": "main", "index": 0}]]
        },
        "LLM Extract Facts": {
            "main": [[{"node": "Validate Extraction", "type": "main", "index": 0}]]
        },
        "Validate Extraction": {
            "main": [[{"node": "Update Status Geocoding", "type": "main", "index": 0}]]
        },
        "Update Status Geocoding": {
            "main": [[{"node": "Nominatim Geocode", "type": "main", "index": 0}]]
        },
        "Nominatim Geocode": {
            "main": [[{"node": "Process Geocode", "type": "main", "index": 0}]]
        },
        "Process Geocode": {
            "main": [[{"node": "Update Status Enriching", "type": "main", "index": 0}]]
        },
        "Update Status Enriching": {
            "main": [[{"node": "Overpass POI Query", "type": "main", "index": 0}]]
        },
        "Overpass POI Query": {
            "main": [[{"node": "Process POI Results", "type": "main", "index": 0}]]
        },
        "Process POI Results": {
            "main": [[{"node": "Update Status Scoring", "type": "main", "index": 0}]]
        },
        "Update Status Scoring": {
            "main": [[{"node": "Compute Scores", "type": "main", "index": 0}]]
        },
        "Compute Scores": {
            "main": [[{"node": "Build Final Payload", "type": "main", "index": 0}]]
        },
        "Build Final Payload": {
            "main": [[{"node": "Send Completed", "type": "main", "index": 0}]]
        },
        "Error Trigger": {
            "main": [[{"node": "Error Handler", "type": "main", "index": 0}]]
        },
    }


def build_workflow():
    return {
        "name": WORKFLOW_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "tags": [{"name": "property-analyzer"}],
    }


def strip_readonly(workflow: dict) -> dict:
    """Remove read-only fields that n8n API rejects on create/update."""
    for field in ("active", "id", "tags", "createdAt", "updatedAt", "versionId"):
        workflow.pop(field, None)
    return workflow


def find_existing_workflow(base_url, headers, name):
    """Search for an existing workflow by name. Returns workflow ID or None."""
    import httpx
    try:
        r = httpx.get(f"{base_url}/api/v1/workflows", headers=headers, timeout=15)
        r.raise_for_status()
        for wf in r.json().get("data", []):
            if wf.get("name") == name:
                return wf["id"]
    except Exception:
        pass
    return None


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "build"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "property_analyzer.json"

    if action == "build":
        workflow = build_workflow()
        output_path.write_text(json.dumps(workflow, indent=2))
        print(f"Built -> {output_path}")
        print(f"  Nodes: {len(workflow['nodes'])}")
        print(f"  Connections: {len(workflow['connections'])}")

    elif action in ("deploy", "activate"):
        import httpx

        workflow = build_workflow()
        output_path.write_text(json.dumps(workflow, indent=2))

        base_url = os.getenv("N8N_BASE_URL")
        api_key = os.getenv("N8N_API_KEY")
        if not base_url or not api_key:
            print("ERROR: N8N_BASE_URL and N8N_API_KEY required in .env")
            sys.exit(1)

        headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
        payload = strip_readonly(dict(workflow))

        existing_id = find_existing_workflow(base_url, headers, WORKFLOW_NAME)

        if existing_id:
            r = httpx.put(
                f"{base_url}/api/v1/workflows/{existing_id}",
                json=payload, headers=headers, timeout=30,
            )
            r.raise_for_status()
            wf_id = existing_id
            print(f"Updated existing workflow -> {wf_id}")
        else:
            r = httpx.post(
                f"{base_url}/api/v1/workflows",
                json=payload, headers=headers, timeout=30,
            )
            r.raise_for_status()
            wf_id = r.json().get("id", "unknown")
            print(f"Created new workflow -> {wf_id}")

        print(f"  JSON saved -> {output_path}")
        print(f"  Nodes: {len(workflow['nodes'])}")

        if action == "activate":
            r2 = httpx.post(
                f"{base_url}/api/v1/workflows/{wf_id}/activate",
                headers=headers, timeout=30,
            )
            r2.raise_for_status()
            print(f"  Activated -> workflow ID: {wf_id}")
        else:
            print(f"  Status: INACTIVE (use 'activate' to enable triggers)")

    else:
        print(f"Usage: python {sys.argv[0]} [build|deploy|activate]")
        sys.exit(1)


if __name__ == "__main__":
    main()
