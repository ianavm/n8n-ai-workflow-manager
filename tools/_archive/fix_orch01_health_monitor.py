"""Fix ORCH-01 Health Monitor workflow.

Error: "Could not get parameter: columns.matchingColumns" at Airtable update nodes.

The fix: Ensure all Airtable update nodes use the correct v2.1 parameter format
with matchingColumns INSIDE the columns dict, not at the top level.

Correct format:
  parameters.columns = {
    "matchingColumns": ["agentId"],
    "value": { "Status": "...", "Health Score": "..." }
  }
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient
from config_loader import load_config

WORKFLOW_ID = "5XR7j7hQ8cdWpi1e"
WORKFLOW_NAME = "ORCH-01 Health Monitor"

# Read-only fields that must be stripped before PUT
READONLY_FIELDS = [
    "id", "active", "createdAt", "updatedAt", "versionId",
    "activeVersionId", "versionCounter", "triggerCount", "shared",
    "activeVersion", "isArchived", "homeProject", "usedCredentials",
    "sharedWithProjects",
]


def fix_airtable_update_nodes(workflow):
    """Fix all Airtable update nodes to use correct matchingColumns format."""
    nodes = workflow.get("nodes", [])
    node_map = {n["name"]: n for n in nodes}

    fixed_nodes = []

    for node in nodes:
        node_type = node.get("type", "")
        params = node.get("parameters", {})
        operation = params.get("operation", "")

        # Only fix Airtable update operations
        if node_type != "n8n-nodes-base.airtable" or operation != "update":
            continue

        node_name = node["name"]
        print(f"\nChecking node: '{node_name}'")

        columns = params.get("columns", {})
        needs_fix = False

        # Case 1: matchingColumns at top level instead of inside columns
        if "matchingColumns" in params and "matchingColumns" not in columns:
            print(f"  Found top-level matchingColumns - moving into columns dict")
            matching = params.pop("matchingColumns")
            if isinstance(matching, str):
                matching = [matching]
            columns["matchingColumns"] = matching
            needs_fix = True

        # Case 2: columns exists but missing matchingColumns entirely
        if "matchingColumns" not in columns:
            print(f"  Missing matchingColumns in columns - adding default ['agentId']")
            columns["matchingColumns"] = ["agentId"]
            needs_fix = True

        # Case 3: matchingColumns is a string, not a list
        if isinstance(columns.get("matchingColumns"), str):
            print(f"  matchingColumns is string - converting to list")
            columns["matchingColumns"] = [columns["matchingColumns"]]
            needs_fix = True

        # Case 4: columns missing value dict (field mappings)
        if "value" not in columns:
            print(f"  Warning: columns.value is missing - node may need manual field mapping")

        # Ensure columns dict is set back
        params["columns"] = columns

        if needs_fix:
            fixed_nodes.append(node_name)
            print(f"  FIXED: {node_name}")
        else:
            print(f"  OK: already correct format")

    return fixed_nodes


def build_update_payload(workflow):
    """Build a minimal update payload with only the fields n8n accepts on PUT."""
    payload = {
        "name": workflow["name"],
        "nodes": workflow["nodes"],
        "connections": workflow["connections"],
        "settings": workflow.get("settings", {}),
    }
    # Only include non-None optional fields
    if workflow.get("tags"):
        payload["tags"] = workflow["tags"]
    return payload


def main():
    config = load_config()

    api_key = config['api_keys']['n8n']
    if not api_key:
        print("Error: N8N_API_KEY not found in environment variables.")
        sys.exit(1)

    base_url = config['n8n']['base_url']

    print("=" * 60)
    print(f"FIXING: {WORKFLOW_NAME}")
    print(f"ID: {WORKFLOW_ID}")
    print("=" * 60)

    with N8nClient(base_url, api_key) as client:
        # 1. Fetch workflow
        print(f"\nFetching workflow...")
        workflow = client.get_workflow(WORKFLOW_ID)
        print(f"  Got: {workflow.get('name', 'Unknown')} ({len(workflow.get('nodes', []))} nodes)")

        # 2. Fix Airtable update nodes
        fixed_nodes = fix_airtable_update_nodes(workflow)

        if not fixed_nodes:
            print("\nNo nodes needed fixing. Workflow already correct.")
            return

        # 3. Push patched workflow back
        print(f"\nPushing patched workflow ({len(fixed_nodes)} nodes fixed)...")
        payload = build_update_payload(workflow)
        client.update_workflow(WORKFLOW_ID, payload)

        # 4. Summary
        print(f"\n{'=' * 60}")
        print("FIX SUMMARY")
        print(f"{'=' * 60}")
        print(f"Workflow: {WORKFLOW_NAME} ({WORKFLOW_ID})")
        print(f"Nodes fixed: {len(fixed_nodes)}")
        for name in fixed_nodes:
            print(f"  - {name}")
        print(f"\nThe workflow is still inactive. Use deactivate_broken.py --reactivate")
        print(f"or manually activate after verifying the fix.")


if __name__ == "__main__":
    main()
