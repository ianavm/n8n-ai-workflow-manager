"""
Fix INTEL-06 Regulatory Alert - Empty Tavily API key.

The workflow crashes at "Tavily Search Regulatory" HTTP Request node with:
    invalid syntax
because the request body contains "api_key": "" (empty string).

Since we cannot confirm a Tavily credential exists in n8n, the safest fix is:
1. Deactivate the workflow to prevent recurring failures.
2. Print clear instructions for creating the Tavily credential.
3. Once the credential is created, a follow-up script or manual edit can
   switch the node to credential-based auth and reactivate.

Usage:
    python tools/fix_intel06_regulatory.py
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient


WORKFLOW_ID = "sbEwotSVpnyqrQtG"

STRIP_KEYS = {"id", "active", "createdAt", "updatedAt", "versionId"}


def build_client(config):
    """Create N8nClient from config."""
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def inspect_tavily_node(wf):
    """Find and inspect the Tavily HTTP Request node. Returns (node, details)."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}

    tavily_name = "Tavily Search Regulatory"
    if tavily_name not in node_map:
        # Try partial match
        for name in node_map:
            if "tavily" in name.lower() or "regulatory" in name.lower():
                tavily_name = name
                break
        else:
            return None, "Tavily node not found in workflow"

    node = node_map[tavily_name]
    params = node.get("parameters", {})

    details = {
        "name": tavily_name,
        "type": node.get("type", "unknown"),
        "method": params.get("method", "GET"),
        "url": params.get("url", ""),
        "authentication": params.get("authentication", "none"),
    }

    # Check for embedded api_key in body
    body_type = params.get("specifyBody", "")
    if body_type == "json":
        json_body = params.get("jsonBody", "")
        details["body_type"] = "json"
        details["json_body_preview"] = json_body[:200] if json_body else "(empty)"
        if "api_key" in json_body:
            details["has_embedded_api_key"] = True
            # Check if the key value is empty
            try:
                parsed = json.loads(json_body)
                api_key_val = parsed.get("api_key", "")
                details["api_key_empty"] = not bool(api_key_val)
            except (json.JSONDecodeError, TypeError):
                details["api_key_empty"] = "parse_error"
    elif params.get("bodyParametersJson"):
        details["body_type"] = "bodyParametersJson"
        details["body_preview"] = str(params["bodyParametersJson"])[:200]

    return node, details


def main():
    config = load_config()

    print("=" * 60)
    print("INTEL-06 FIX - Tavily Empty API Key")
    print("=" * 60)

    with build_client(config) as client:
        # 1. Fetch
        print(f"\n[FETCH] Getting workflow {WORKFLOW_ID}...")
        wf = client.get_workflow(WORKFLOW_ID)
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")
        print(f"  Active: {wf.get('active', False)}")

        # 2. Inspect the Tavily node
        print("\n[INSPECT] Examining Tavily Search node...")
        node, details = inspect_tavily_node(wf)

        if node is None:
            print(f"  ERROR: {details}")
            print("  Cannot proceed - node not found.")
            sys.exit(1)

        print(f"  Node name: {details['name']}")
        print(f"  Node type: {details['type']}")
        print(f"  Method: {details['method']}")
        print(f"  URL: {details.get('url', 'N/A')}")
        print(f"  Auth: {details.get('authentication', 'none')}")
        if "body_type" in details:
            print(f"  Body type: {details['body_type']}")
        if details.get("has_embedded_api_key"):
            print(f"  Has embedded api_key: YES")
            print(f"  API key is empty: {details.get('api_key_empty', 'unknown')}")

        # 3. Deactivate the workflow
        print("\n[DEACTIVATE] Disabling workflow to prevent recurring failures...")
        if wf.get("active", False):
            client.deactivate_workflow(WORKFLOW_ID)
            print("  Workflow deactivated successfully.")
        else:
            print("  Workflow is already inactive.")

        # 4. Save local backup
        from pathlib import Path

        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        backup_path = output_dir / "intel06_regulatory_pre_fix.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[BACKUP] Saved snapshot to {backup_path}")

    # 5. Print instructions
    print("\n" + "=" * 60)
    print("WORKFLOW DEACTIVATED - Manual steps required:")
    print("=" * 60)
    print("""
To fix this workflow permanently:

1. Get a Tavily API key:
   - Sign up at https://tavily.com
   - Copy your API key from the dashboard

2. Create an n8n credential:
   - In n8n, go to Credentials -> Add Credential
   - Type: "Header Auth"
   - Name: "Tavily API Key"
   - Header Name: "Authorization"
   - Header Value: "Bearer <your-tavily-api-key>"
   (Or use the body-based auth that Tavily expects:
    keep api_key in the JSON body but set it to the real key)

3. Update the "Tavily Search Regulatory" node:
   Option A (body-based, Tavily default):
     - Edit the node's JSON body
     - Replace "api_key": "" with "api_key": "your-actual-key"
     - Better: use an n8n expression referencing an env var or credential

   Option B (credential-based, more secure):
     - Set Authentication to "Predefined Credential Type"
     - Select the Header Auth credential you created
     - Remove "api_key" from the JSON body

4. Reactivate the workflow:
   - Toggle the workflow active in n8n UI
   - Or run: python -c "
     import sys; sys.path.insert(0, 'tools')
     from config_loader import load_config
     from n8n_client import N8nClient
     c = load_config()
     client = N8nClient(c['n8n']['base_url'], c['api_keys']['n8n'])
     client.activate_workflow('""" + WORKFLOW_ID + """')
     "

5. Add TAVILY_API_KEY to .env for future deploy scripts.
""")

    print("Workflow ID:", WORKFLOW_ID)
    print("Status: INACTIVE (safe - no more crashes)")


if __name__ == "__main__":
    main()
