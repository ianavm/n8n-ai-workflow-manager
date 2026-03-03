"""
Fix Lead Scraper - Rename "Fourways Business Scraper" to "Johannesburg Lead Scraper".

Patches the live n8n workflow to replace all "Fourways" references in:
1. Score Leads node (source field)
2. Aggregate Results node (email subject + body)
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"


def fix_workflow(wf):
    """Replace all Fourways references with Johannesburg Lead Scraper."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}
    changes = 0

    # Fix Score Leads node - source field
    if "Score Leads" in node_map:
        score_node = node_map["Score Leads"]
        code = score_node["parameters"]["jsCode"]
        old = "Google Maps Scraper - Fourways All Business"
        new = "Johannesburg Lead Scraper"
        if old in code:
            code = code.replace(old, new)
            score_node["parameters"]["jsCode"] = code
            print(f"  [1] Score Leads: source '{old}' -> '{new}'")
            changes += 1
        else:
            print("  [1] Score Leads: no Fourways source found (already updated?)")

    # Fix Aggregate Results node - subject + body
    if "Aggregate Results" in node_map:
        agg_node = node_map["Aggregate Results"]
        code = agg_node["parameters"]["jsCode"]

        replacements = [
            ("Fourways Business Scraper:", "Johannesburg Lead Scraper:"),
            ("Fourways All-Business Lead Scraper Complete", "Johannesburg Lead Scraper Complete"),
            ("Fourways All-Business Lead Scraper", "Johannesburg Lead Scraper"),
        ]

        for old, new in replacements:
            if old in code:
                code = code.replace(old, new)
                print(f"  [2] Aggregate Results: '{old}' -> '{new}'")
                changes += 1

        agg_node["parameters"]["jsCode"] = code

        if changes == 0:
            print("  [2] Aggregate Results: no Fourways references found (already updated?)")

    # Fix any remaining Fourways references in any node's jsCode
    for node in nodes:
        if "parameters" in node and "jsCode" in node.get("parameters", {}):
            code = node["parameters"]["jsCode"]
            if "Fourways" in code and node["name"] not in ("Score Leads", "Aggregate Results"):
                code = code.replace("Fourways", "Johannesburg")
                node["parameters"]["jsCode"] = code
                print(f"  [3] {node['name']}: replaced remaining Fourways references")
                changes += 1

    # Fix cachedResultName in Airtable nodes
    for node in nodes:
        params = node.get("parameters", {})
        base_config = params.get("base", {})
        if isinstance(base_config, dict) and base_config.get("cachedResultName") == "Lead Scraper - Fourways CRM":
            base_config["cachedResultName"] = "Lead Scraper - Johannesburg CRM"
            print(f"  [4] {node['name']}: cachedResultName -> 'Lead Scraper - Johannesburg CRM'")
            changes += 1

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
        print("\nNo Fourways references found - workflow is already up to date.")
        return

    print(f"\nApplying {changes} change(s) to live workflow...")
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


if __name__ == "__main__":
    main()
