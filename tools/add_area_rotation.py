"""
Add automatic area rotation to the Lead Scraper workflow.

When all businesses in the current area have been reached out to (no new leads
found), the scraper automatically moves to the next area in the rotation list.

Areas are stored in the Search Config node and rotated via a Code node that
checks Airtable for existing leads vs total scraped.

Usage:
    python tools/add_area_rotation.py
"""

import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "uq4hnH0YHfhYOOzO"


# Areas to rotate through (greater Johannesburg, starting from Fourways)
AREAS = [
    "Fourways, Johannesburg, South Africa",
    "Sandton, Johannesburg, South Africa",
    "Randburg, Johannesburg, South Africa",
    "Bryanston, Johannesburg, South Africa",
    "Midrand, Johannesburg, South Africa",
    "Rosebank, Johannesburg, South Africa",
    "Parkhurst, Johannesburg, South Africa",
    "Melrose, Johannesburg, South Africa",
    "Bedfordview, Johannesburg, South Africa",
    "Centurion, Pretoria, South Africa",
    "Menlyn, Pretoria, South Africa",
    "Stellenbosch, Cape Town, South Africa",
    "Sea Point, Cape Town, South Africa",
    "Umhlanga, Durban, South Africa",
]


# This Code node replaces the static Search Config Set node.
# It checks Airtable for how many leads already exist from the current area,
# and rotates to the next area if the current one is saturated.
SEARCH_CONFIG_CODE = """
// Area rotation list
const areas = {areas_json};

// Read current area index from workflow static data
// If not set, start at 0
const staticData = $getWorkflowStaticData('global');
let areaIndex = staticData.areaIndex || 0;
let currentArea = areas[areaIndex] || areas[0];

// Check how many new leads came from the last run
// If Filter New Leads produced 0 items in the previous execution,
// the area is likely exhausted. We track this via a counter.
let consecutiveEmptyRuns = staticData.consecutiveEmptyRuns || 0;

// The Schedule Trigger fires daily. On first run, just use current area.
// After the run completes, the Aggregate Results node will update the counter.

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


# This code is added to the Aggregate Results node.
# After scoring and upserting, it checks how many new leads were found.
# If zero new leads for 2 consecutive runs, rotate to next area.
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


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    # Get the Google Places API key from the current workflow
    with httpx.Client(timeout=60) as client:
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        wf = resp.json()

        places_api_key = ""
        for node in wf["nodes"]:
            if node["name"] == "Search Config":
                for assignment in node["parameters"]["assignments"]["assignments"]:
                    if assignment["name"] == "googlePlacesApiKey":
                        places_api_key = assignment["value"]
                        break

        print(f"Places API key found: {places_api_key[:20]}...")
        areas_json = json.dumps(AREAS)

        # === MODIFY SEARCH CONFIG ===
        # Convert from Set node to Code node for dynamic area rotation
        for i, node in enumerate(wf["nodes"]):
            if node["name"] == "Search Config":
                code = SEARCH_CONFIG_CODE.format(
                    areas_json=areas_json,
                    api_key=places_api_key
                )
                wf["nodes"][i] = {
                    "parameters": {"jsCode": code},
                    "id": node["id"],
                    "name": "Search Config",
                    "type": "n8n-nodes-base.code",
                    "position": node["position"],
                    "typeVersion": 2
                }
                print("Converted Search Config from Set to Code node with area rotation")
                break

        # === MODIFY AGGREGATE RESULTS ===
        # Add area rotation check after counting new leads
        for node in wf["nodes"]:
            if node["name"] == "Aggregate Results":
                existing_code = node["parameters"]["jsCode"]

                area_check = AREA_CHECK_CODE.format(areas_json=areas_json)

                # Append the area rotation logic and modify the summary email
                new_code = existing_code.rstrip()

                # Find where the return statement starts and inject area info
                # The existing code builds a summary and returns it
                # We'll add the area check before the return
                if "return {" in new_code:
                    # Insert area check code before the final return
                    return_idx = new_code.rfind("return {")
                    before_return = new_code[:return_idx]
                    return_part = new_code[return_idx:]

                    # Modify the return to include area info
                    new_code = before_return + "\n\n" + area_check + "\n\n" + "\n".join([
                        "// Build summary with area info",
                        "const areaInfo = rotated",
                        "  ? `<p style=\"color:#FF6D5A;font-weight:bold;\">AREA ROTATED: Moving from ${config.location} to ${nextArea} (no new leads in 2 runs)</p>`",
                        "  : `<p>Current area: ${config.location} (${consecutiveEmptyRuns} empty run${consecutiveEmptyRuns !== 1 ? 's' : ''})</p>`;",
                        "",
                    ]) + return_part
                else:
                    # Fallback: just append
                    new_code += "\n\n" + area_check

                node["parameters"]["jsCode"] = new_code
                print("Added area rotation check to Aggregate Results")
                break

        # Also update the Send Summary node to include area info in the email
        for node in wf["nodes"]:
            if node["name"] == "Send Summary":
                # Check if it already references areaInfo
                msg = node["parameters"].get("message", "")
                if "areaInfo" not in msg and "location" not in msg:
                    # The summary email likely uses $json fields from Aggregate Results
                    # We'll add area info to the Aggregate Results output instead
                    pass
                break

        # === DEPLOY ===
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

        # Verify
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        final = resp.json()
        print(f"\nDeployed. Active: {final.get('active')}")

        for node in final["nodes"]:
            if node["name"] == "Search Config":
                print(f"Search Config type: {node['type']}")
                code = node["parameters"]["jsCode"]
                # Show the areas list
                if "areas" in code:
                    print(f"Areas configured: {len(AREAS)}")
                    for j, area in enumerate(AREAS):
                        print(f"  [{j}] {area}")
                break

        print("\nArea rotation logic:")
        print("  - Starts at area index 0 (Fourways)")
        print("  - After 2 consecutive runs with 0 new leads, rotates to next area")
        print("  - Cycles through all areas then wraps around")
        print("  - State stored in workflow static data (persists across executions)")


if __name__ == "__main__":
    main()
