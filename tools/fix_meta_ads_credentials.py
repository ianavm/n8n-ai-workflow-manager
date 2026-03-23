"""
Fix Meta Ads credentials in ADS workflows -- 2026-03-22

Patches all ADS workflows with real Meta Ads credential IDs and
account IDs. Also sets continueOnFail on Google/TikTok nodes so
the Meta-only path works independently.

Prerequisites:
    1. Create facebookGraphApi credential in n8n UI
    2. Set in .env:
       META_ADS_ACCOUNT_ID=act_XXXXXXXXX
       N8N_CRED_META_ADS=<credential_id_from_n8n>

Usage:
    python tools/fix_meta_ads_credentials.py
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


# ── Environment ────────────────────────────────────────────
META_CRED_ID = os.getenv("N8N_CRED_META_ADS", "")
META_ACCOUNT_ID = os.getenv("META_ADS_ACCOUNT_ID", "")

# Workflow IDs
WF_ADS_03 = "KAkjBo273HOMbVEP"  # Campaign Builder
WF_ADS_04 = "3U4ZXsWW7255zoFm"  # Performance Monitor


def build_client(config):
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def normalize_account_id(raw_id):
    """Ensure account ID has act_ prefix exactly once."""
    if raw_id.startswith("act_"):
        return raw_id
    return f"act_{raw_id}"


# ─────────────────────────────────────────────────────────────
# FIX 1: Patch ADS-04 Performance Monitor
# ─────────────────────────────────────────────────────────────

def fix_ads04_meta_credential(client):
    """Patch Meta Ads Get Insights node with real credential + endpoint."""
    print("\n" + "=" * 60)
    print("FIX 1: Patch ADS-04 Performance Monitor (Meta credential)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_04)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changed = False
    account_id = normalize_account_id(META_ACCOUNT_ID)

    # Patch Meta Ads Get Insights node
    meta_node = node_map.get("Meta Ads Get Insights")
    if meta_node:
        old_cred_id = meta_node.get("credentials", {}).get("facebookGraphApi", {}).get("id", "")
        print(f"  Meta node current cred: {old_cred_id}")

        meta_node["credentials"]["facebookGraphApi"] = {
            "id": META_CRED_ID,
            "name": "Meta Ads Graph API"
        }

        old_endpoint = meta_node.get("parameters", {}).get("node", "")
        new_endpoint = f"={account_id}/insights"
        meta_node["parameters"]["node"] = new_endpoint
        print(f"  Endpoint: {old_endpoint} -> {new_endpoint}")
        print(f"  Credential: {old_cred_id} -> {META_CRED_ID}")
        changed = True
    else:
        print("  WARNING: 'Meta Ads Get Insights' node not found")

    # Set continueOnFail on Google Ads + TikTok nodes
    for node_name in ["Google Ads Get Campaigns", "TikTok Ads Get Insights",
                      "Google Ads Get Report", "Fetch Google Ads"]:
        node = node_map.get(node_name)
        if node:
            node["onError"] = "continueRegularOutput"
            print(f"  Set continueOnFail: {node_name}")
            changed = True

    # Also check for any facebookGraphApi nodes by type
    for node in wf["nodes"]:
        if (node["type"] == "n8n-nodes-base.facebookGraphApi"
                and node["name"] != "Meta Ads Get Insights"):
            old_id = node.get("credentials", {}).get("facebookGraphApi", {}).get("id", "")
            if old_id == "REPLACE_AFTER_SETUP" or not old_id:
                node["credentials"]["facebookGraphApi"] = {
                    "id": META_CRED_ID,
                    "name": "Meta Ads Graph API"
                }
                print(f"  Also patched: {node['name']}")
                changed = True

    if not changed:
        print("  No changes needed")
        return True

    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    result = client.update_workflow(WF_ADS_04, payload)
    print(f"  Deployed: {result['name']} (active: {result.get('active')})")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 2: Patch ADS-03 Campaign Builder
# ─────────────────────────────────────────────────────────────

def fix_ads03_meta_credential(client):
    """Patch Create Meta Campaign node with real credential + endpoint."""
    print("\n" + "=" * 60)
    print("FIX 2: Patch ADS-03 Campaign Builder (Meta credential)")
    print("=" * 60)

    wf = client.get_workflow(WF_ADS_03)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changed = False
    account_id = normalize_account_id(META_ACCOUNT_ID)

    # Patch Create Meta Campaign node
    meta_node = node_map.get("Create Meta Campaign")
    if meta_node:
        old_cred_id = meta_node.get("credentials", {}).get("facebookGraphApi", {}).get("id", "")
        print(f"  Meta node current cred: {old_cred_id}")

        meta_node["credentials"]["facebookGraphApi"] = {
            "id": META_CRED_ID,
            "name": "Meta Ads Graph API"
        }

        old_endpoint = meta_node.get("parameters", {}).get("node", "")
        new_endpoint = f"={account_id}/campaigns"
        meta_node["parameters"]["node"] = new_endpoint
        print(f"  Endpoint: {old_endpoint} -> {new_endpoint}")
        print(f"  Credential: {old_cred_id} -> {META_CRED_ID}")
        changed = True
    else:
        print("  WARNING: 'Create Meta Campaign' node not found")

    # Set continueOnFail on Google Ads + TikTok nodes
    for node_name in ["Create Google Campaign", "Google Ads Create Campaign",
                      "Create TikTok Campaign", "TikTok Create Campaign"]:
        node = node_map.get(node_name)
        if node:
            node["onError"] = "continueRegularOutput"
            print(f"  Set continueOnFail: {node_name}")
            changed = True

    # Also check for any facebookGraphApi nodes by type
    for node in wf["nodes"]:
        if (node["type"] == "n8n-nodes-base.facebookGraphApi"
                and node["name"] != "Create Meta Campaign"):
            old_id = node.get("credentials", {}).get("facebookGraphApi", {}).get("id", "")
            if old_id == "REPLACE_AFTER_SETUP" or not old_id:
                node["credentials"]["facebookGraphApi"] = {
                    "id": META_CRED_ID,
                    "name": "Meta Ads Graph API"
                }
                print(f"  Also patched: {node['name']}")
                changed = True

    if not changed:
        print("  No changes needed")
        return True

    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    result = client.update_workflow(WF_ADS_03, payload)
    print(f"  Deployed: {result['name']} (active: {result.get('active')})")
    return True


# ─────────────────────────────────────────────────────────────
# FIX 3: Scan all ADS workflows for stale placeholders
# ─────────────────────────────────────────────────────────────

ALL_ADS_WORKFLOWS = {
    "LZ2ZXwra1ep3IEQH": "ADS-01 Strategy Generator",
    "Ygvv6yGVqqOGDYgV": "ADS-02 Copy & Creative Generator",
    "KAkjBo273HOMbVEP": "ADS-03 Campaign Builder",
    "3U4ZXsWW7255zoFm": "ADS-04 Performance Monitor",
    "cwdYl8T8GRSmrWjp": "ADS-05 Optimization Engine",
    "uU3OLLP5vtLpD5uM": "ADS-06 Creative Recycler",
    "h3YGMAPAcCx3Y51G": "ADS-07 Attribution Engine",
    "6cDCfVjuAcZQKStK": "ADS-08 Reporting Dashboard",
}


def scan_all_ads_for_placeholders(client):
    """Check all ADS workflows for any remaining REPLACE_AFTER_SETUP placeholders."""
    print("\n" + "=" * 60)
    print("FIX 3: Scan all ADS workflows for remaining placeholders")
    print("=" * 60)

    issues = []
    for wf_id, wf_name in ALL_ADS_WORKFLOWS.items():
        # Skip ADS-03 and ADS-04 (already patched)
        if wf_id in (WF_ADS_03, WF_ADS_04):
            continue

        try:
            wf = client.get_workflow(wf_id)
        except Exception as e:
            print(f"  ERROR: {wf_name} ({wf_id}) -> {e}")
            issues.append(f"{wf_name}: workflow not accessible")
            continue

        wf_json = json.dumps(wf["nodes"])
        if "REPLACE_AFTER_SETUP" in wf_json:
            count = wf_json.count("REPLACE_AFTER_SETUP")
            print(f"  {wf_name}: {count} placeholder(s) found")

            # Patch any facebookGraphApi credentials
            changed = False
            for node in wf["nodes"]:
                creds = node.get("credentials", {})
                fb_cred = creds.get("facebookGraphApi", {})
                if fb_cred.get("id") == "REPLACE_AFTER_SETUP":
                    creds["facebookGraphApi"] = {
                        "id": META_CRED_ID,
                        "name": "Meta Ads Graph API"
                    }
                    print(f"    Patched: {node['name']} (facebookGraphApi)")
                    changed = True

                # Fix endpoint placeholders
                params = node.get("parameters", {})
                endpoint = params.get("node", "")
                if "REPLACE" in str(endpoint):
                    account_id = normalize_account_id(META_ACCOUNT_ID)
                    if "insights" in endpoint.lower():
                        params["node"] = f"={account_id}/insights"
                    elif "campaigns" in endpoint.lower():
                        params["node"] = f"={account_id}/campaigns"
                    print(f"    Fixed endpoint: {node['name']}")
                    changed = True

            if changed:
                payload = {
                    "name": wf["name"],
                    "nodes": wf["nodes"],
                    "connections": wf["connections"],
                    "settings": wf.get("settings", {"executionOrder": "v1"}),
                }
                client.update_workflow(wf_id, payload)
                print(f"    Deployed: {wf_name}")
        else:
            print(f"  {wf_name}: clean (no placeholders)")

    if issues:
        print(f"\n  {len(issues)} issue(s) found:")
        for issue in issues:
            print(f"    - {issue}")
        return False
    return True


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    config = load_config()

    print("=" * 60)
    print("FIX META ADS CREDENTIALS -- 2026-03-22")
    print("=" * 60)

    # Validate env vars
    if not META_CRED_ID or META_CRED_ID == "REPLACE_AFTER_SETUP":
        print("\nERROR: N8N_CRED_META_ADS not set in .env")
        print("  1. Create facebookGraphApi credential in n8n UI")
        print("  2. Add N8N_CRED_META_ADS=<id> to .env")
        sys.exit(1)

    if not META_ACCOUNT_ID or META_ACCOUNT_ID == "act_your_account_id":
        print("\nERROR: META_ADS_ACCOUNT_ID not set in .env")
        print("  Add META_ADS_ACCOUNT_ID=act_XXXXXXXXX to .env")
        sys.exit(1)

    account_id = normalize_account_id(META_ACCOUNT_ID)
    print(f"\n  Meta credential ID: {META_CRED_ID}")
    print(f"  Meta account ID:    {account_id}")

    results = {}

    with build_client(config) as client:
        # 1. Patch ADS-04 (Performance Monitor)
        try:
            results["ads04_meta"] = fix_ads04_meta_credential(client)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["ads04_meta"] = False

        # 2. Patch ADS-03 (Campaign Builder)
        try:
            results["ads03_meta"] = fix_ads03_meta_credential(client)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["ads03_meta"] = False

        # 3. Scan remaining workflows
        try:
            results["scan_all"] = scan_all_ads_for_placeholders(client)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["scan_all"] = False

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, success in results.items():
        status = "OK" if success else "NEEDS ATTENTION"
        print(f"  {name}: {status}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n  {len(failed)} item(s) need attention.")
    else:
        print("\n  All Meta Ads credentials patched successfully!")
        print("\n  Next steps:")
        print("    1. Manual-trigger ADS-04 to test Meta API connection")
        print("    2. Activate Phase 1: ADS-08, ADS-07, ADS-04")


if __name__ == "__main__":
    main()
