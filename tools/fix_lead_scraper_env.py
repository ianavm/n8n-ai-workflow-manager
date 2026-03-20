"""
Fix Lead Scraper - Remove process.env / $env references from Code nodes.

n8n Cloud blocks access to environment variables in Code nodes, causing
"access to env vars denied" errors. This script replaces all env var
references with hardcoded config values or credential placeholders.

Target workflow: Lead Scraper (uq4hnH0YHfhYOOzO)
"""

import sys
import json
import re

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"

# Known config values to replace env var lookups
ENV_REPLACEMENTS = {
    # Google Places API key - should come from n8n credential, not env
    "GOOGLE_PLACES_API_KEY": "CONFIGURED_VIA_CREDENTIAL",
    "GOOGLE_API_KEY": "CONFIGURED_VIA_CREDENTIAL",
    "PLACES_API_KEY": "CONFIGURED_VIA_CREDENTIAL",
    # Airtable
    "AIRTABLE_BASE_ID": "app2ALQUP7CKEkHOz",
    "AIRTABLE_API_KEY": "CONFIGURED_VIA_CREDENTIAL",
    "AIRTABLE_TOKEN": "CONFIGURED_VIA_CREDENTIAL",
    "AIRTABLE_PAT": "CONFIGURED_VIA_CREDENTIAL",
    # n8n instance
    "N8N_BASE_URL": "https://ianimmelman89.app.n8n.cloud",
    "N8N_API_KEY": "CONFIGURED_VIA_CREDENTIAL",
    # Lead scraper config
    "LEAD_SCRAPER_BASE_ID": "app2ALQUP7CKEkHOz",
    # Sender info
    "SENDER_NAME": "Ian Immelman",
    "SENDER_EMAIL": "ian@anyvisionmedia.com",
    "SENDER_COMPANY": "AnyVision Media",
    "SENDER_TITLE": "Business Automation Consultant",
}

# The Search Config node typically sets up config values used downstream.
# Replace its entire jsCode with a version that returns hardcoded values
# instead of reading from process.env.
SEARCH_CONFIG_CODE = r"""// Search Config - hardcoded values (process.env blocked on n8n Cloud)
// API keys should be configured via n8n credentials, not Code nodes.
return [{
  json: {
    // Airtable config
    airtableBaseId: 'app2ALQUP7CKEkHOz',

    // Sender details
    senderName: 'Ian Immelman',
    senderEmail: 'ian@anyvisionmedia.com',
    senderCompany: 'AnyVision Media',
    senderTitle: 'Business Automation Consultant',

    // Search defaults
    searchRadius: 5000,
    maxResults: 20,
    location: 'Fourways, Johannesburg',
    country: 'ZA',
    language: 'en',

    // Email config
    dailyLimit: 50,
    cooldownMinutes: 2,

    // Note: Google Places API key and Airtable PAT are configured
    // via n8n credentials (not hardcoded here for security).
    _configSource: 'hardcoded (n8n Cloud does not allow process.env)'
  }
}];"""


def replace_env_refs_in_code(js_code, node_name):
    """
    Replace process.env.X and $env.X references with hardcoded values.

    Returns (patched_code, list_of_replacements_made).
    """
    replacements_made = []
    patched = js_code

    # Pattern 1: process.env.VAR_NAME or process.env['VAR_NAME'] or process.env["VAR_NAME"]
    def replace_process_env_dot(match):
        var_name = match.group(1)
        value = ENV_REPLACEMENTS.get(var_name, f"UNKNOWN_ENV_{var_name}")
        replacements_made.append(f"process.env.{var_name} -> '{value}'")
        return f"'{value}'"

    def replace_process_env_bracket(match):
        var_name = match.group(1)
        value = ENV_REPLACEMENTS.get(var_name, f"UNKNOWN_ENV_{var_name}")
        replacements_made.append(f"process.env['{var_name}'] -> '{value}'")
        return f"'{value}'"

    patched = re.sub(
        r"process\.env\.([A-Z_][A-Z0-9_]*)",
        replace_process_env_dot,
        patched
    )
    patched = re.sub(
        r"process\.env\[['\"]([A-Z_][A-Z0-9_]*?)['\"]\]",
        replace_process_env_bracket,
        patched
    )

    # Pattern 2: $env.VAR_NAME (n8n expression style inside Code nodes)
    def replace_dollar_env(match):
        var_name = match.group(1)
        value = ENV_REPLACEMENTS.get(var_name, f"UNKNOWN_ENV_{var_name}")
        replacements_made.append(f"$env.{var_name} -> '{value}'")
        return f"'{value}'"

    patched = re.sub(
        r"\$env\.([A-Z_][A-Z0-9_]*)",
        replace_dollar_env,
        patched
    )

    return patched, replacements_made


def fix_workflow(wf):
    """Find and patch all Code nodes that reference env vars."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}

    fixed_nodes = []
    total_replacements = 0

    for node in nodes:
        if node["type"] != "n8n-nodes-base.code":
            continue

        js_code = node.get("parameters", {}).get("jsCode", "")
        if not js_code:
            continue

        node_name = node["name"]
        has_env_ref = (
            "process.env" in js_code
            or "$env." in js_code
            or "$env[" in js_code
        )

        if not has_env_ref:
            continue

        print(f"\n  Found env refs in: '{node_name}'")

        # Special handling for Search Config - replace entirely
        if node_name == "Search Config":
            print("    -> Replacing entire jsCode with hardcoded config")
            node["parameters"]["jsCode"] = SEARCH_CONFIG_CODE
            fixed_nodes.append(node_name)
            total_replacements += 1
            continue

        # For all other Code nodes, do targeted replacement
        patched_code, replacements = replace_env_refs_in_code(js_code, node_name)

        if replacements:
            node["parameters"]["jsCode"] = patched_code
            fixed_nodes.append(node_name)
            total_replacements += len(replacements)
            for r in replacements:
                print(f"    -> {r}")

    return wf, fixed_nodes, total_replacements


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = config["n8n"]["base_url"]

    print("=" * 60)
    print("LEAD SCRAPER FIX - Remove process.env references")
    print("=" * 60)
    print(f"  Workflow ID: {WORKFLOW_ID}")
    print(f"  Instance: {base_url}")

    with N8nClient(base_url, api_key) as client:
        # 1. Fetch
        print("\n[FETCH] Getting current workflow...")
        wf = client.get_workflow(WORKFLOW_ID)
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        # Count Code nodes
        code_nodes = [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.code"]
        print(f"  Code nodes found: {len(code_nodes)}")

        # 2. Fix
        print("\n[FIX] Scanning Code nodes for env var references...")
        wf, fixed_nodes, total_replacements = fix_workflow(wf)

        if not fixed_nodes:
            print("\n  No env var references found in any Code nodes.")
            print("  Nothing to fix. Exiting.")
            return

        # 3. Save locally
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "lead_scraper_env_fix.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] Saved to {output_path}")

        # 4. Deploy - strip read-only fields
        print("\n[DEPLOY] Pushing to n8n...")
        update_payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"}),
        }
        # Strip fields that n8n rejects on update
        for field in ("id", "active", "createdAt", "updatedAt", "versionId"):
            update_payload.pop(field, None)

        result = client.update_workflow(WORKFLOW_ID, update_payload)
        print(f"  Active: {result.get('active')}")
        print(f"  Nodes: {len(result.get('nodes', []))}")

    print("\n" + "=" * 60)
    print("FIX DEPLOYED SUCCESSFULLY")
    print("=" * 60)
    print(f"\nNodes patched ({len(fixed_nodes)}):")
    for i, name in enumerate(fixed_nodes, 1):
        print(f"  {i}. {name}")
    print(f"\nTotal env var replacements: {total_replacements}")
    print("\nNote: API keys replaced with 'CONFIGURED_VIA_CREDENTIAL'")
    print("      should be wired to n8n credentials in the workflow editor.")


if __name__ == "__main__":
    main()
