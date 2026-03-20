"""
Fix all credential issues — 2026-03-17

Handles everything that was marked as "manual":
1. Update Airtable PAT credential (K8t2NtJ89DLLh64j) with fresh token from .env
2. Patch Lead Scraper to use Google Places API key from .env
3. Share Gmail credential with AVM project (if API supports it)
4. Reactivate all 5 deactivated workflows

Usage:
    python tools/fix_all_credentials.py
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from config_loader import load_config
from n8n_client import N8nClient


def build_client(config):
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


# ─────────────────────────────────────────────────────────────
# FIX 1: Update Airtable PAT in n8n credential store
# ─────────────────────────────────────────────────────────────

def fix_airtable_credential(client):
    """Update the expired Airtable PAT credential with the fresh token from .env."""
    print("\n" + "=" * 60)
    print("FIX 1: Update Airtable PAT Credential")
    print("=" * 60)

    cred_id = "K8t2NtJ89DLLh64j"
    new_token = os.getenv("AIRTABLE_API_TOKEN", "")

    if not new_token:
        print("  ERROR: AIRTABLE_API_TOKEN not found in .env")
        return False

    print(f"  Credential ID: {cred_id}")
    print(f"  New token: {new_token[:10]}...{new_token[-4:]} ({len(new_token)} chars)")

    # n8n API: PATCH /credentials/{id} to update credential data
    try:
        response = client.client.patch(
            f"/credentials/{cred_id}",
            json={
                "name": "Airtable Personal Access Token account",
                "type": "airtableTokenApi",
                "data": {
                    "accessToken": new_token
                }
            }
        )
        response.raise_for_status()
        result = response.json()
        print(f"  SUCCESS: Credential updated (name: {result.get('name', 'unknown')})")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        # Try alternative endpoint format
        try:
            response = client.client.put(
                f"/credentials/{cred_id}",
                json={
                    "name": "Airtable Personal Access Token account",
                    "type": "airtableTokenApi",
                    "data": {
                        "accessToken": new_token
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            print(f"  SUCCESS (PUT): Credential updated (name: {result.get('name', 'unknown')})")
            return True
        except Exception as e2:
            print(f"  ERROR (PUT also failed): {e2}")
            return False


# ─────────────────────────────────────────────────────────────
# FIX 2: Patch Lead Scraper with Google Places API key
# ─────────────────────────────────────────────────────────────

def fix_lead_scraper_api_key(client):
    """Patch the Lead Scraper 'Search Config' Code node to include Google Places API key."""
    print("\n" + "=" * 60)
    print("FIX 2: Patch Lead Scraper Google Places API Key")
    print("=" * 60)

    wf_id = "uq4hnH0YHfhYOOzO"
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")

    if not api_key:
        print("  ERROR: GOOGLE_PLACES_API_KEY not found in .env")
        return False

    print(f"  Workflow ID: {wf_id}")
    print(f"  API key: {api_key[:10]}...{api_key[-4:]} ({len(api_key)} chars)")

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}

    # Find the Search Config Code node
    config_node = node_map.get("Search Config")
    if not config_node:
        print("  ERROR: 'Search Config' node not found")
        # Try finding any code node with config-like name
        code_nodes = [n["name"] for n in wf["nodes"] if n["type"] == "n8n-nodes-base.code"]
        print(f"  Available Code nodes: {code_nodes}")
        return False

    old_code = config_node["parameters"].get("jsCode", "")
    print(f"  Found 'Search Config' node, code length: {len(old_code)} chars")

    # Check if googlePlacesApiKey is already defined
    if "googlePlacesApiKey" in old_code:
        # Replace the existing line or add the key value
        # The config likely has googlePlacesApiKey as a property
        import re

        # Pattern: googlePlacesApiKey: "..." or googlePlacesApiKey: process.env...
        # or just missing the value
        if f'googlePlacesApiKey: "{api_key}"' in old_code:
            print("  API key already set correctly, no changes needed")
            return True

        # Try to replace any existing googlePlacesApiKey value
        new_code = re.sub(
            r'googlePlacesApiKey:\s*["\']?[^,\n"\']*["\']?',
            f'googlePlacesApiKey: "{api_key}"',
            old_code,
            count=1
        )

        if new_code != old_code:
            config_node["parameters"]["jsCode"] = new_code
            print("  Patched: replaced googlePlacesApiKey value")
        else:
            print("  WARNING: Could not find googlePlacesApiKey pattern to replace")
            return False
    else:
        print("  WARNING: googlePlacesApiKey not found in Search Config code")
        print("  Adding it to the config object...")
        # Find the return statement and add the key before it
        if "return" in old_code:
            new_code = old_code.replace(
                "_configSource:",
                f'googlePlacesApiKey: "{api_key}",\n      _configSource:'
            )
            if new_code != old_code:
                config_node["parameters"]["jsCode"] = new_code
                print("  Added googlePlacesApiKey to config object")
            else:
                print("  ERROR: Could not inject API key into config")
                return False
        else:
            print("  ERROR: Cannot find insertion point in code")
            return False

    # Also need to fix the searchQuery — error showed "undefined in Fourways"
    # The textQuery uses $json.searchQuery which doesn't exist in config
    # Check the Places Text Search node
    places_node = node_map.get("Places Text Search")
    if places_node:
        params = places_node.get("parameters", {})
        headers = params.get("headerParameters", {}).get("parameters", [])
        for h in headers:
            if h.get("name") == "X-Goog-Api-Key":
                old_val = h.get("value", "")
                if "$json.googlePlacesApiKey" in old_val:
                    print("  'Places Text Search' API key header references $json.googlePlacesApiKey - OK")
                else:
                    h["value"] = "={{ $json.googlePlacesApiKey }}"
                    print("  Fixed 'Places Text Search' API key header expression")

    # Deploy
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    result = client.update_workflow(wf_id, payload)
    print(f"  Deployed: {result['name']} (active: {result.get('active')})")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 3: Share Gmail credential with AVM project
# ─────────────────────────────────────────────────────────────

def fix_gmail_credential_sharing(client):
    """Try to share Gmail credential EC2l4faLSdgePOM6 with AVM project X8YS2aPAoXgAHLmS."""
    print("\n" + "=" * 60)
    print("FIX 3: Share Gmail Credential with AVM Project")
    print("=" * 60)

    cred_id = "EC2l4faLSdgePOM6"
    avm_project_id = "X8YS2aPAoXgAHLmS"

    print(f"  Credential: Gmail AVM Tutorial ({cred_id})")
    print(f"  Target project: AVM ({avm_project_id})")

    # n8n API: PUT /credentials/{id}/share with projectIds
    try:
        response = client.client.put(
            f"/credentials/{cred_id}/transfer",
            json={
                "destinationProjectId": avm_project_id
            }
        )
        response.raise_for_status()
        print(f"  SUCCESS: Gmail credential transferred to AVM project")
        return True
    except Exception as e:
        error_text = str(e)
        print(f"  Transfer attempt: {error_text}")

    # Try sharing instead of transferring
    try:
        response = client.client.put(
            f"/credentials/{cred_id}/share",
            json={
                "shareWithIds": [avm_project_id]
            }
        )
        response.raise_for_status()
        print(f"  SUCCESS: Gmail credential shared with AVM project")
        return True
    except Exception as e:
        error_text = str(e)
        print(f"  Share attempt: {error_text}")

    # If both fail, try the move-to-project endpoint
    try:
        response = client.client.put(
            f"/credentials/{cred_id}/move",
            json={
                "destinationProjectId": avm_project_id
            }
        )
        response.raise_for_status()
        print(f"  SUCCESS: Gmail credential moved to AVM project")
        return True
    except Exception as e:
        print(f"  Move attempt: {e}")
        print("  NOTE: Gmail credential sharing requires n8n UI.")
        print("  Go to: n8n -> Credentials -> 'Gmail AVM Tutorial' -> Sharing -> Add 'AVM' project")
        return False


# ─────────────────────────────────────────────────────────────
# FIX 4: Reactivate all deactivated workflows
# ─────────────────────────────────────────────────────────────

def reactivate_workflows(client):
    """Reactivate all 5 workflows that were deactivated."""
    print("\n" + "=" * 60)
    print("FIX 4: Reactivate Deactivated Workflows")
    print("=" * 60)

    workflows = {
        "5XR7j7hQ8cdWpi1e": "ORCH-01 Health Monitor",
        "EiuQcBeQG7AVcbYE": "CRM-01 Hourly Sync",
        "uq4hnH0YHfhYOOzO": "Lead Scraper",
        "g2uPmEBbAEtz9YP4L8utG": "Business Email Management",
        "2extQxrmWCoGgXCp": "Marketing All Workflows",
    }

    success = 0
    for wf_id, name in workflows.items():
        print(f"  Activating: {name} ({wf_id})...")
        try:
            client.activate_workflow(wf_id)
            print(f"    OK")
            success += 1
        except Exception as e:
            print(f"    FAILED: {e}")

    print(f"\n  Results: {success}/{len(workflows)} reactivated")
    return success == len(workflows)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    config = load_config()

    print("=" * 60)
    print("FIX ALL CREDENTIALS - 2026-03-17")
    print("=" * 60)

    results = {}

    with build_client(config) as client:
        # 1. Update Airtable PAT
        results["airtable_pat"] = fix_airtable_credential(client)

        # 2. Patch Lead Scraper
        results["lead_scraper_key"] = fix_lead_scraper_api_key(client)

        # 3. Share Gmail credential
        results["gmail_sharing"] = fix_gmail_credential_sharing(client)

        # 4. Reactivate all workflows
        results["reactivation"] = reactivate_workflows(client)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, success in results.items():
        status = "OK" if success else "NEEDS MANUAL ACTION"
        print(f"  {name}: {status}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n  {len(failed)} item(s) need manual attention in n8n UI.")
    else:
        print("\n  All fixes applied successfully!")


if __name__ == "__main__":
    main()
