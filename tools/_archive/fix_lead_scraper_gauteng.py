"""
Expand Lead Scraper area rotation to cover all of Gauteng province.

Replaces the previous area list (Joburg suburbs + Cape Town/Durban) with
23 Gauteng-specific locations for comprehensive provincial coverage.

Handles both states:
- If Search Config is still a Set node: converts to Code node with area rotation
- If Search Config is already a Code node: replaces the areas array

Usage:
    python tools/fix_lead_scraper_gauteng.py
"""

import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "uq4hnH0YHfhYOOzO"

GAUTENG_AREAS = [
    # Johannesburg Metro
    "Johannesburg CBD, Johannesburg, South Africa",
    "Sandton, Johannesburg, South Africa",
    "Fourways, Johannesburg, South Africa",
    "Randburg, Johannesburg, South Africa",
    "Bryanston, Johannesburg, South Africa",
    "Midrand, Gauteng, South Africa",
    "Rosebank, Johannesburg, South Africa",
    "Roodepoort, Johannesburg, South Africa",
    "Soweto, Johannesburg, South Africa",
    "Bedfordview, Johannesburg, South Africa",
    # East Rand
    "Kempton Park, Gauteng, South Africa",
    "Germiston, Gauteng, South Africa",
    "Benoni, Gauteng, South Africa",
    "Boksburg, Gauteng, South Africa",
    "Springs, Gauteng, South Africa",
    # South of Joburg
    "Alberton, Gauteng, South Africa",
    # Pretoria / Tshwane Metro
    "Centurion, Pretoria, South Africa",
    "Pretoria CBD, Pretoria, South Africa",
    "Hatfield, Pretoria, South Africa",
    "Menlyn, Pretoria, South Africa",
    "Brooklyn, Pretoria, South Africa",
    # Vaal Triangle
    "Vanderbijlpark, Gauteng, South Africa",
    "Vereeniging, Gauteng, South Africa",
    # West Rand
    "Krugersdorp, Gauteng, South Africa",
]

# Code node JS for Search Config (same template as add_area_rotation.py)
SEARCH_CONFIG_CODE = """
// Area rotation list - Gauteng Province ({area_count} areas)
const areas = {areas_json};

// Read current area index from workflow static data
const staticData = $getWorkflowStaticData('global');
let areaIndex = staticData.areaIndex || 0;
let currentArea = areas[areaIndex] || areas[0];

let consecutiveEmptyRuns = staticData.consecutiveEmptyRuns || 0;

return {{
  json: {{
    searchQuery: 'businesses',
    location: currentArea,
    areaIndex: areaIndex,
    totalAreas: areas.length,
    maxResults: 20,
    senderName: 'Ian Immelman',
    senderCompany: 'AnyVision Media',
    senderTitle: 'Director',
    senderEmail: 'ian@anyvisionmedia.com',
    googlePlacesApiKey: '{api_key}',
    consecutiveEmptyRuns: consecutiveEmptyRuns
  }}
}};
""".strip()

AREA_CHECK_CODE = """
// Check if we should rotate areas
const config = $('Search Config').first().json;
const newLeadCount = $('Filter New Leads').all().length;

const staticData = $getWorkflowStaticData('global');
let consecutiveEmptyRuns = staticData.consecutiveEmptyRuns || 0;
let areaIndex = staticData.areaIndex || 0;

const areas = {areas_json};

if (newLeadCount === 0) {{
  consecutiveEmptyRuns++;
}} else {{
  consecutiveEmptyRuns = 0;
}}

// If 2 consecutive runs with no new leads, rotate to next area
let rotated = false;
if (consecutiveEmptyRuns >= 2) {{
  areaIndex = (areaIndex + 1) % areas.length;
  consecutiveEmptyRuns = 0;
  rotated = true;
}}

// Save state
staticData.areaIndex = areaIndex;
staticData.consecutiveEmptyRuns = consecutiveEmptyRuns;

const nextArea = areas[areaIndex];
""".strip()


def replace_areas_in_jscode(code, new_areas_json):
    """Replace an existing JS areas array in code with the new one."""
    # Match: const areas = [...];
    pattern = r'const areas\s*=\s*\[.*?\];'
    replacement = f'const areas = {new_areas_json};'
    new_code, count = re.subn(pattern, replacement, code, flags=re.DOTALL)
    return new_code, count


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = config["n8n"]["base_url"].rstrip("/")
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    areas_json = json.dumps(GAUTENG_AREAS)

    with httpx.Client(timeout=60) as client:
        # Fetch workflow
        print(f"Fetching workflow {WORKFLOW_ID}...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        # === MODIFY SEARCH CONFIG ===
        places_api_key = ""
        for i, node in enumerate(wf["nodes"]):
            if node["name"] == "Search Config":
                if node["type"] == "n8n-nodes-base.set":
                    # Still a Set node -> extract API key and convert to Code
                    print("  Search Config is a Set node -> converting to Code node")
                    for assignment in node["parameters"]["assignments"]["assignments"]:
                        if assignment["name"] == "googlePlacesApiKey":
                            places_api_key = assignment["value"]
                            break

                    code = SEARCH_CONFIG_CODE.format(
                        areas_json=areas_json,
                        api_key=places_api_key,
                        area_count=len(GAUTENG_AREAS)
                    )
                    wf["nodes"][i] = {
                        "parameters": {"jsCode": code},
                        "id": node["id"],
                        "name": "Search Config",
                        "type": "n8n-nodes-base.code",
                        "position": node["position"],
                        "typeVersion": 2
                    }
                    print(f"  Converted Set -> Code with {len(GAUTENG_AREAS)} Gauteng areas")

                elif node["type"] == "n8n-nodes-base.code":
                    # Already a Code node -> replace areas array in jsCode
                    print("  Search Config is already a Code node -> replacing areas list")
                    old_code = node["parameters"]["jsCode"]

                    # Extract API key from existing code
                    key_match = re.search(r"googlePlacesApiKey:\s*'([^']*)'", old_code)
                    if key_match:
                        places_api_key = key_match.group(1)

                    new_code, count = replace_areas_in_jscode(old_code, areas_json)
                    if count > 0:
                        node["parameters"]["jsCode"] = new_code
                        print(f"  Replaced {count} areas array(s) in Search Config")
                    else:
                        # Fallback: regenerate entire code
                        code = SEARCH_CONFIG_CODE.format(
                            areas_json=areas_json,
                            api_key=places_api_key,
                            area_count=len(GAUTENG_AREAS)
                        )
                        node["parameters"]["jsCode"] = code
                        print("  Regenerated Search Config code with Gauteng areas")
                break

        if not places_api_key:
            print("  WARNING: Could not extract Google Places API key. Using env var reference.")
            places_api_key = "{{ $env.GOOGLE_PLACES_API_KEY }}"

        # === MODIFY AGGREGATE RESULTS ===
        for node in wf["nodes"]:
            if node["name"] == "Aggregate Results":
                old_code = node["parameters"]["jsCode"]

                # Check if area rotation code already exists
                if "const areas" in old_code:
                    new_code, count = replace_areas_in_jscode(old_code, areas_json)
                    if count > 0:
                        node["parameters"]["jsCode"] = new_code
                        print(f"  Updated {count} areas array(s) in Aggregate Results")
                    else:
                        print("  WARNING: Could not find areas array in Aggregate Results")
                else:
                    # Area rotation code not yet added -> inject it
                    area_check = AREA_CHECK_CODE.format(areas_json=areas_json)

                    if "return {" in old_code:
                        return_idx = old_code.rfind("return {")
                        before_return = old_code[:return_idx]
                        return_part = old_code[return_idx:]

                        area_info_code = "\n".join([
                            "// Build summary with area info",
                            "const areaInfo = rotated",
                            '  ? `<p style="color:#FF6D5A;font-weight:bold;">AREA ROTATED: Moving from ${config.location} to ${nextArea} (no new leads in 2 runs)</p>`',
                            "  : `<p>Current area: ${config.location} (${consecutiveEmptyRuns} empty run${consecutiveEmptyRuns !== 1 ? 's' : ''})</p>`;",
                            "",
                        ])
                        new_code = before_return + "\n\n" + area_check + "\n\n" + area_info_code + return_part
                    else:
                        new_code = old_code + "\n\n" + area_check

                    node["parameters"]["jsCode"] = new_code
                    print("  Injected area rotation check into Aggregate Results")
                break

        # === DEPLOY ===
        print("Deploying updated workflow...")
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=headers)

        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()

        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=headers)

        # === VERIFY ===
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        final = resp.json()
        print(f"\nDeployed. Active: {final.get('active')}")

        for node in final["nodes"]:
            if node["name"] == "Search Config":
                print(f"  Search Config type: {node['type']}")
                code = node["parameters"].get("jsCode", "")
                if "areas" in code:
                    print(f"  Areas configured: {len(GAUTENG_AREAS)}")
                    for j, area in enumerate(GAUTENG_AREAS):
                        print(f"    [{j}] {area}")
                break

        print("\n=== DONE ===")
        print(f"Lead scraper now covers {len(GAUTENG_AREAS)} Gauteng areas.")
        print("Area rotation: after 2 consecutive runs with 0 new leads, rotates to next area.")


if __name__ == "__main__":
    main()
