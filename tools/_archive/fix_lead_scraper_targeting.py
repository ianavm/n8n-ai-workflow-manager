"""
Fix Lead Scraper - Broaden targeting to automation-friendly businesses.

Changes:
1. Search Config: Convert from static Set node ("dentists", max 6) to Code node
   with industry query rotation + area rotation across 24 JHB/Gauteng locations.
2. Score Leads: Add industry-based automation fit scoring on top of contact
   completeness scoring.
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"

SEARCH_CONFIG_CODE = r"""
// Industry search queries - rotate through automation-friendly businesses
const queries = [
  'real estate agency',
  'law firm',
  'dental practice',
  'medical practice',
  'accounting firm',
  'insurance broker',
  'marketing agency',
  'consulting firm',
  'recruitment agency',
  'financial advisor',
  'salon spa',
  'gym fitness',
  'restaurant',
  'retail store',
  'construction company',
  'logistics company',
  'automotive dealer',
  'hotel guest house',
  'veterinary clinic',
  'property management'
];

// Area rotation - 24 Johannesburg/Gauteng/Pretoria locations
const areas = [
  'Johannesburg CBD, Johannesburg, South Africa',
  'Sandton, Johannesburg, South Africa',
  'Fourways, Johannesburg, South Africa',
  'Randburg, Johannesburg, South Africa',
  'Bryanston, Johannesburg, South Africa',
  'Midrand, Gauteng, South Africa',
  'Rosebank, Johannesburg, South Africa',
  'Roodepoort, Johannesburg, South Africa',
  'Soweto, Johannesburg, South Africa',
  'Bedfordview, Johannesburg, South Africa',
  'Kempton Park, Gauteng, South Africa',
  'Germiston, Gauteng, South Africa',
  'Benoni, Gauteng, South Africa',
  'Boksburg, Gauteng, South Africa',
  'Springs, Gauteng, South Africa',
  'Alberton, Gauteng, South Africa',
  'Centurion, Pretoria, South Africa',
  'Pretoria CBD, Pretoria, South Africa',
  'Hatfield, Pretoria, South Africa',
  'Menlyn, Pretoria, South Africa',
  'Brooklyn, Pretoria, South Africa',
  'Vanderbijlpark, Gauteng, South Africa',
  'Vereeniging, Gauteng, South Africa',
  'Krugersdorp, Gauteng, South Africa'
];

const staticData = $getWorkflowStaticData('global');
let queryIndex = staticData.queryIndex || 0;
let areaIndex = staticData.areaIndex || 0;

// Advance to next industry query each run
queryIndex = (queryIndex + 1) % queries.length;

// When we've cycled through all queries, advance to next area
if (queryIndex === 0) {
  areaIndex = (areaIndex + 1) % areas.length;
}

// Save state for next run
staticData.queryIndex = queryIndex;
staticData.areaIndex = areaIndex;

const currentQuery = queries[queryIndex];
const currentArea = areas[areaIndex];

return {
  json: {
    searchQuery: currentQuery,
    location: currentArea,
    queryIndex: queryIndex,
    areaIndex: areaIndex,
    totalQueries: queries.length,
    totalAreas: areas.length,
    maxResults: 20,
    senderName: 'Ian Immelman',
    senderCompany: 'AnyVision Media',
    senderTitle: 'Director',
    senderEmail: 'ian@anyvisionmedia.com',
    googlePlacesApiKey: $env.GOOGLE_PLACES_API_KEY
  }
};
"""

SCORE_LEADS_CODE = r"""
const items = $input.all();
const seen = new Set();
const results = [];

const highFitIndustries = [
  'real estate', 'law', 'legal', 'attorney', 'medical', 'dental', 'clinic',
  'consulting', 'agency', 'marketing', 'insurance', 'accounting', 'finance',
  'recruitment', 'staffing', 'financial', 'property management'
];
const mediumFitIndustries = [
  'restaurant', 'retail', 'salon', 'fitness', 'gym', 'spa', 'hotel',
  'guest house', 'veterinary', 'vet', 'beauty', 'wellness'
];
const lowFitIndustries = [
  'manufacturing', 'logistics', 'construction', 'contractor', 'plumbing',
  'electrician', 'hvac', 'landscaping', 'cleaning', 'automotive'
];

for (const item of items) {
  const email = (item.json.emails || item.json.email || '').toString().toLowerCase().trim();
  if (!email || seen.has(email)) continue;
  seen.add(email);

  const industry = (item.json.industry || '').toLowerCase();
  const businessName = (item.json.businessName || '').toLowerCase();
  const combined = industry + ' ' + businessName;

  // Contact completeness score
  let score = 0;
  if (email) score += 20;
  if (item.json.phone) score += 15;
  if (item.json.businessName) score += 15;
  if (item.json.address) score += 10;
  if (item.json.rating > 0) score += 10;
  if (item.json.linkedin || item.json.facebook || item.json.instagram) score += 10;
  if (item.json.website) score += 10;
  if (item.json.phone && email) score += 10;

  // Automation fit scoring
  let automationFit = 'low';
  const matchAny = (list, text) => list.some(t => text.includes(t));

  if (matchAny(highFitIndustries, combined)) {
    automationFit = 'high';
    score += 20;
  } else if (matchAny(mediumFitIndustries, combined)) {
    automationFit = 'medium';
    score += 10;
  } else {
    score += 5;
  }

  results.push({
    json: {
      ...item.json,
      email: email,
      leadScore: Math.min(score, 100),
      automationFit: automationFit,
      status: 'New',
      source: 'Johannesburg Lead Scraper',
      datescraped: new Date().toISOString().split('T')[0]
    }
  });
}

return results.length > 0 ? results : [{ json: { _empty: true } }];
"""


def fix_workflow(wf):
    """Update Search Config and Score Leads nodes."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}
    changes = 0

    # 1. Convert Search Config from Set to Code node
    if "Search Config" in node_map:
        sc = node_map["Search Config"]
        old_type = sc["type"]
        sc["type"] = "n8n-nodes-base.code"
        sc["typeVersion"] = 2
        sc["parameters"] = {"jsCode": SEARCH_CONFIG_CODE.strip()}
        print(f"  [1] Search Config: {old_type} -> n8n-nodes-base.code")
        print(f"      - 20 industry queries x 24 areas = 480 search combinations")
        print(f"      - maxResults: 20 (was 6)")
        changes += 1
    else:
        print("  [1] Search Config: NOT FOUND")

    # 2. Update Score Leads with automation fit scoring
    if "Score Leads" in node_map:
        sl = node_map["Score Leads"]
        sl["parameters"]["jsCode"] = SCORE_LEADS_CODE.strip()
        print("  [2] Score Leads: added industry-based automation fit scoring")
        print("      - High fit (+20): real estate, law, medical, consulting, etc.")
        print("      - Medium fit (+10): restaurant, retail, salon, hotel, etc.")
        print("      - Low fit (+5): construction, logistics, manufacturing, etc.")
        changes += 1
    else:
        print("  [2] Score Leads: NOT FOUND")

    return changes


def main():
    config = load_config()
    base_url = config["n8n"]["base_url"]
    api_key = config["api_keys"]["n8n"]

    headers = {
        "X-N8N-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    print(f"Fetching workflow {WORKFLOW_ID}...")
    r = httpx.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers, timeout=30)
    r.raise_for_status()
    wf = r.json()
    print(f"  Workflow: {wf['name']} ({len(wf['nodes'])} nodes)")

    changes = fix_workflow(wf)

    if changes == 0:
        print("\nNo changes needed.")
        return

    print(f"\nPushing {changes} change(s) to live workflow...")
    update_payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    r = httpx.put(
        f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
        headers=headers,
        json=update_payload,
        timeout=30,
    )
    r.raise_for_status()
    print("Done! Workflow updated successfully.")
    print("\nThe scraper will now rotate through:")
    print("  - 20 automation-friendly industry queries")
    print("  - 24 Johannesburg/Gauteng/Pretoria areas")
    print("  - 20 results per search (was 6)")


if __name__ == "__main__":
    main()
