"""Fix all broken Code nodes in AVM Overview workflow.

The n8n MCP partial update stripped typeVersion and jsCode from 108 Code nodes.
This script patches them all and pushes the full workflow back via the n8n API.
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient

WORKFLOW_ID = "Zp1gCxlgYtXA9lJO"

# Mock code templates by node function pattern
MOCK_CODE = {
    # --- Read operations return arrays ---
    "read": """// Mock: {name}
return [{{ json: {{ id: 'rec_mock', fields: {{ Status: 'Active', _source: '{name}' }}, _mock: true }} }}];""",

    # --- Write/Create/Log/Save/Update operations return single object ---
    "write": """// Mock: {name}
return {{ json: {{ id: 'rec_mock', fields: {{ Status: 'OK', _source: '{name}' }}, _mock: true }} }};""",

    # --- Compute/Analyze/Aggregate/Format/Parse/Score/Filter/Split/Decide/Route/Match/Validate/Extract/Detect/Scan ---
    "compute": """// Mock: {name}
const items = $input.all();
return items.length > 0 ? items : [{{ json: {{ result: 'ok', _source: '{name}', _mock: true }} }}];""",
}

def classify_node(name):
    lower = name.lower()
    # Read-like operations
    if any(k in lower for k in ['read ', 'fetch ', 'search ']):
        return "read"
    # Write-like operations
    if any(k in lower for k in ['write ', 'create ', 'log ', 'save ', 'update ', 'escalate ']):
        return "write"
    # Everything else (compute, analyze, format, parse, etc.)
    return "compute"

def main():
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    client = N8nClient(base_url=base_url, api_key=api_key)

    # Fetch current workflow
    print(f"Fetching workflow {WORKFLOW_ID}...")
    wf = client.get_workflow(WORKFLOW_ID)
    nodes = wf["nodes"]

    fixed = 0
    for node in nodes:
        if node["type"] == "n8n-nodes-base.code":
            params = node.get("parameters", {})
            needs_fix = not node.get("typeVersion") or not params.get("jsCode")

            if needs_fix:
                category = classify_node(node["name"])
                code = MOCK_CODE[category].format(name=node["name"])

                node["typeVersion"] = 2
                node["parameters"] = {"jsCode": code}
                # Remove any leftover Airtable credential refs
                if "credentials" in node:
                    creds = node["credentials"]
                    if "airtableTokenApi" in creds or "airtableOAuth2Api" in creds:
                        del node["credentials"]
                fixed += 1

    print(f"Fixed {fixed} broken Code nodes")

    if fixed == 0:
        print("Nothing to fix!")
        return

    # Push back via API
    print("Pushing updated workflow...")
    result = client.update_workflow(WORKFLOW_ID, {
        "nodes": nodes,
        "connections": wf["connections"],
        "name": wf["name"],
    })
    print(f"Success! Workflow updated: {result.get('name', 'unknown')}")
    print(f"Total nodes: {len(result.get('nodes', []))}")

    # Verify
    verify = client.get_workflow(WORKFLOW_ID)
    broken_after = sum(
        1 for n in verify["nodes"]
        if n["type"] == "n8n-nodes-base.code"
        and (not n.get("typeVersion") or not n.get("parameters", {}).get("jsCode"))
    )
    print(f"Verification: {broken_after} broken Code nodes remaining")

if __name__ == "__main__":
    main()
