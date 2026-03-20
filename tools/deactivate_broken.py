"""Deactivate broken workflows that are burning execution credits.

Temporarily deactivates workflows that fail on every trigger cycle.
Saves a reactivation manifest so they can be restored later with --reactivate.
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient
from config_loader import load_config

# Workflows to deactivate: ID -> (name, reason)
# Updated 2026-03-16: Airtable PAT expired, Google Places API key missing, Gmail cred not shared
BROKEN_WORKFLOWS = {
    "5XR7j7hQ8cdWpi1e": (
        "ORCH-01 Health Monitor",
        "Fails every 15 min - Airtable PAT expired (401 Invalid token) on cred K8t2NtJ89DLLh64j"
    ),
    "EiuQcBeQG7AVcbYE": (
        "CRM-01 Hourly Sync",
        "Fails every hour - Airtable PAT expired (401 Invalid token) on cred K8t2NtJ89DLLh64j"
    ),
    "uq4hnH0YHfhYOOzO": (
        "Lead Scraper",
        "Fails every 2 hours - Google Places 403 (googlePlacesApiKey = undefined in config)"
    ),
    "g2uPmEBbAEtz9YP4L8utG": (
        "Business Email Management",
        "Intermittent - Gmail cred EC2l4faLSdgePOM6 not shared with AVM project"
    ),
    "2extQxrmWCoGgXCp": (
        "Marketing All Workflows Combined",
        "Intermittent - Gmail cred EC2l4faLSdgePOM6 not shared with AVM project"
    ),
}

MANIFEST_PATH = Path(__file__).parent.parent / ".tmp" / "deactivated_manifest.json"


def deactivate_all(client):
    """Deactivate all broken workflows and save manifest."""
    print("=" * 60)
    print("DEACTIVATING BROKEN WORKFLOWS")
    print("=" * 60)

    print(f"\nWorkflows to deactivate ({len(BROKEN_WORKFLOWS)}):")
    for wf_id, (name, reason) in BROKEN_WORKFLOWS.items():
        print(f"  [{wf_id}] {name}")
        print(f"    Reason: {reason}")

    print()

    results = []
    for wf_id, (name, reason) in BROKEN_WORKFLOWS.items():
        print(f"Deactivating: {name} ({wf_id})...")
        try:
            client.deactivate_workflow(wf_id)
            results.append({
                "id": wf_id,
                "name": name,
                "reason": reason,
                "status": "deactivated",
                "deactivated_at": datetime.now().isoformat(),
            })
            print(f"  OK - deactivated")
        except Exception as e:
            error_msg = str(e)
            results.append({
                "id": wf_id,
                "name": name,
                "reason": reason,
                "status": "error",
                "error": error_msg,
                "deactivated_at": datetime.now().isoformat(),
            })
            print(f"  FAILED - {error_msg}")

    # Save manifest for reactivation
    manifest = {
        "created_at": datetime.now().isoformat(),
        "purpose": "Temporarily deactivated broken workflows to stop credit burn",
        "workflows": results,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nManifest saved to: {MANIFEST_PATH}")

    # Summary
    success_count = sum(1 for r in results if r["status"] == "deactivated")
    error_count = sum(1 for r in results if r["status"] == "error")
    print(f"\nResults: {success_count} deactivated, {error_count} errors")

    if error_count > 0:
        print("\nFailed workflows:")
        for r in results:
            if r["status"] == "error":
                print(f"  {r['name']}: {r['error']}")

    return results


def reactivate_all(client):
    """Reactivate workflows from the saved manifest."""
    print("=" * 60)
    print("REACTIVATING WORKFLOWS FROM MANIFEST")
    print("=" * 60)

    if not MANIFEST_PATH.exists():
        print(f"\nError: No manifest found at {MANIFEST_PATH}")
        print("Nothing to reactivate.")
        sys.exit(1)

    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    workflows = manifest.get("workflows", [])
    deactivated = [w for w in workflows if w["status"] == "deactivated"]

    if not deactivated:
        print("\nNo deactivated workflows in manifest.")
        return

    print(f"\nManifest created: {manifest.get('created_at', 'unknown')}")
    print(f"Workflows to reactivate: {len(deactivated)}")
    print()

    success_count = 0
    for wf in deactivated:
        wf_id = wf["id"]
        name = wf["name"]
        print(f"Reactivating: {name} ({wf_id})...")
        try:
            client.activate_workflow(wf_id)
            print(f"  OK - reactivated")
            success_count += 1
        except Exception as e:
            print(f"  FAILED - {e}")

    print(f"\nResults: {success_count}/{len(deactivated)} reactivated")

    if success_count == len(deactivated):
        # Remove manifest after full success
        MANIFEST_PATH.unlink()
        print(f"Manifest removed: {MANIFEST_PATH}")


def main():
    config = load_config()

    api_key = config['api_keys']['n8n']
    if not api_key:
        print("Error: N8N_API_KEY not found in environment variables.")
        sys.exit(1)

    base_url = config['n8n']['base_url']

    with N8nClient(base_url, api_key) as client:
        if "--reactivate" in sys.argv:
            reactivate_all(client)
        else:
            deactivate_all(client)


if __name__ == "__main__":
    main()
