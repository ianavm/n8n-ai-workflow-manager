"""
Fix Lead Scraper - National expansion with 69 areas, 30 industries, 2-hour schedule, Page 2 enabled.

Changes:
1. Search Config: Expand from 24 Gauteng areas to 69 national areas (Cape Town, Durban, Pretoria, other metros)
2. Industries: Expand from 20 to 30 automation-friendly industries
3. Schedule: Change from weekly to every 2 hours (12 runs/day)
4. Page 2: Enable the disabled "Places Page 2" pagination node
5. Score Leads: Add new industries to automation fit scoring
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"

SEARCH_CONFIG_CODE = r"""
// Industry search queries - 30 automation-friendly businesses (national)
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
  'property management',
  'engineering firm',
  'architecture firm',
  'IT company',
  'software development',
  'event management',
  'travel agency',
  'private school',
  'freight forwarding',
  'manufacturing company',
  'food processing'
];

// Area rotation - 69 locations across South Africa
const areas = [
  // Johannesburg Metro (10)
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
  // East Rand (5)
  'Kempton Park, Gauteng, South Africa',
  'Germiston, Gauteng, South Africa',
  'Benoni, Gauteng, South Africa',
  'Boksburg, Gauteng, South Africa',
  'Springs, Gauteng, South Africa',
  // South Joburg (1)
  'Alberton, Gauteng, South Africa',
  // Vaal Triangle (2)
  'Vanderbijlpark, Gauteng, South Africa',
  'Vereeniging, Gauteng, South Africa',
  // West Rand (1)
  'Krugersdorp, Gauteng, South Africa',
  // Pretoria/Tshwane (13)
  'Centurion, Pretoria, South Africa',
  'Pretoria CBD, Pretoria, South Africa',
  'Hatfield, Pretoria, South Africa',
  'Menlyn, Pretoria, South Africa',
  'Brooklyn, Pretoria, South Africa',
  'Pretoria East, Pretoria, South Africa',
  'Lynnwood, Pretoria, South Africa',
  'Waterkloof, Pretoria, South Africa',
  'Montana, Pretoria, South Africa',
  'Silverton, Pretoria, South Africa',
  'Arcadia, Pretoria, South Africa',
  'Sunnyside, Pretoria, South Africa',
  'Irene, Pretoria, South Africa',
  // Cape Town Metro (15)
  'Cape Town CBD, Cape Town, South Africa',
  'Sea Point, Cape Town, South Africa',
  'Green Point, Cape Town, South Africa',
  'Camps Bay, Cape Town, South Africa',
  'Claremont, Cape Town, South Africa',
  'Constantia, Cape Town, South Africa',
  'Bellville, Cape Town, South Africa',
  'Durbanville, Cape Town, South Africa',
  'Stellenbosch, Western Cape, South Africa',
  'Paarl, Western Cape, South Africa',
  'Somerset West, Western Cape, South Africa',
  'Milnerton, Cape Town, South Africa',
  'Century City, Cape Town, South Africa',
  'Woodstock, Cape Town, South Africa',
  'Observatory, Cape Town, South Africa',
  // Durban Metro (12)
  'Durban CBD, Durban, South Africa',
  'Umhlanga, Durban, South Africa',
  'Ballito, KwaZulu-Natal, South Africa',
  'Pinetown, Durban, South Africa',
  'Westville, Durban, South Africa',
  'Hillcrest, KwaZulu-Natal, South Africa',
  'Kloof, KwaZulu-Natal, South Africa',
  'Durban North, Durban, South Africa',
  'Berea, Durban, South Africa',
  'Musgrave, Durban, South Africa',
  'La Lucia, Durban, South Africa',
  'Gateway, Umhlanga, South Africa',
  // Other metros (10)
  'Bloemfontein, Free State, South Africa',
  'Gqeberha, Eastern Cape, South Africa',
  'East London, Eastern Cape, South Africa',
  'Mbombela, Mpumalanga, South Africa',
  'Polokwane, Limpopo, South Africa',
  'Rustenburg, North West, South Africa',
  'Pietermaritzburg, KwaZulu-Natal, South Africa',
  'Richards Bay, KwaZulu-Natal, South Africa',
  'George, Western Cape, South Africa',
  'Kimberley, Northern Cape, South Africa'
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
  'recruitment', 'staffing', 'financial', 'property management',
  'engineering', 'architecture', 'IT', 'software', 'development'
];
const mediumFitIndustries = [
  'restaurant', 'retail', 'salon', 'fitness', 'gym', 'spa', 'hotel',
  'guest house', 'veterinary', 'vet', 'beauty', 'wellness',
  'event', 'travel', 'school', 'private school', 'food processing'
];
const lowFitIndustries = [
  'manufacturing', 'logistics', 'construction', 'contractor', 'plumbing',
  'electrician', 'hvac', 'landscaping', 'cleaning', 'automotive',
  'freight', 'forwarding'
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
      source: 'National Lead Scraper',
      datescraped: new Date().toISOString().split('T')[0]
    }
  });
}

return results.length > 0 ? results : [{ json: { _empty: true } }];
"""


def fix_workflow(wf):
    """Update Search Config, Score Leads, schedule, and enable Page 2."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}
    changes = 0

    # 1. Convert Search Config from Set to Code node with national coverage
    if "Search Config" in node_map:
        sc = node_map["Search Config"]
        old_type = sc["type"]
        sc["type"] = "n8n-nodes-base.code"
        sc["typeVersion"] = 2
        sc["parameters"] = {"jsCode": SEARCH_CONFIG_CODE.strip()}
        print(f"  [1] Search Config: {old_type} -> n8n-nodes-base.code")
        print(f"      - 30 industry queries x 69 areas = 2,070 search combinations")
        print(f"      - maxResults: 20 per page (40 with Page 2)")
        changes += 1
    else:
        print("  [1] Search Config: NOT FOUND")

    # 2. Update Score Leads with expanded automation fit scoring
    if "Score Leads" in node_map:
        sl = node_map["Score Leads"]
        sl["parameters"]["jsCode"] = SCORE_LEADS_CODE.strip()
        print("  [2] Score Leads: updated with 30-industry automation fit scoring")
        print("      - High fit (+20): real estate, law, medical, consulting, engineering, IT, etc.")
        print("      - Medium fit (+10): restaurant, retail, hotel, event, travel, school, etc.")
        print("      - Low fit (+5): construction, logistics, manufacturing, freight, etc.")
        changes += 1
    else:
        print("  [2] Score Leads: NOT FOUND")

    # 3. Enable "Places Page 2" pagination node
    for node in nodes:
        if node["name"] == "Places Page 2":
            if node.get("disabled"):
                node.pop("disabled", None)
                print("  [3] Places Page 2: ENABLED (was disabled)")
                print("      - Doubles results per run from 20 to 40")
                changes += 1
            else:
                print("  [3] Places Page 2: already enabled")
            break
    else:
        print("  [3] Places Page 2: NOT FOUND")

    # 4. Change schedule to every 2 hours
    for node in nodes:
        if node["type"] == "n8n-nodes-base.scheduleTrigger":
            old_params = json.dumps(node.get("parameters", {}))
            node["parameters"] = {
                "rule": {
                    "interval": [
                        {"field": "hours", "hoursInterval": 2}
                    ]
                }
            }
            print(f"  [4] Schedule Trigger: changed to every 2 hours (12 runs/day)")
            print(f"      - Was: {old_params[:80]}...")
            changes += 1
            break
    else:
        print("  [4] Schedule Trigger: NOT FOUND")

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
    print("  - 30 automation-friendly industry queries")
    print("  - 69 South African areas (JHB, CPT, DBN, PTA, other metros)")
    print("  - 40 results per search (Page 2 enabled)")
    print("  - Every 2 hours (12 runs/day)")
    print(f"\n  Daily capacity: ~480 raw leads/day")
    print(f"  After dedup (~60%): ~288 unique leads/day")


if __name__ == "__main__":
    main()
