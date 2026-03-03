"""
Fix Lead Follow-Up Sequence - Add safety net filter to exclude ticket reply leads.

Expands the Airtable filterByFormula on the "Fetch Due Follow-Ups" node to also
exclude leads with statuses that indicate they should not receive follow-ups:
- "Ticket Reply - Do Not Follow Up" (set by fix_ticket_reply_filter.py)
- "Converted - Do Not Follow Up" (set by fix_interested_reply.py)
- "Bounced" (set by bounce detection)

This is a safety net: fix_ticket_reply_filter.py already sets Follow Up Stage = 0
which is excluded by the existing >= 1 filter, but explicit Status checks add
defense in depth.

Usage:
    python tools/fix_followup_ticket_filter.py
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "3SAKeUWGkMHiNlEf"

NEW_FILTER = (
    "AND("
    "IS_BEFORE({Next Follow Up Date}, DATEADD(TODAY(), 1, 'days')), "
    "{Follow Up Stage} >= 1, "
    "{Follow Up Stage} <= 4, "
    "{Status} != 'Ticket Reply - Do Not Follow Up', "
    "{Status} != 'Converted - Do Not Follow Up', "
    "{Status} != 'Bounced'"
    ")"
)


def main():
    config = load_config()
    base_url = config["n8n"]["base_url"].rstrip("/")
    api_key = config["api_keys"]["n8n"]

    headers = {
        "X-N8N-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    # Fetch workflow
    print(f"Fetching workflow {WORKFLOW_ID}...")
    resp = httpx.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers, timeout=30)
    resp.raise_for_status()
    wf = resp.json()
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    # Save backup before making changes
    import os
    os.makedirs(".tmp", exist_ok=True)
    backup_path = f".tmp/followup_backup_{WORKFLOW_ID}.json"
    with open(backup_path, "w") as f:
        json.dump(wf, f, indent=2)
    print(f"  Backup saved to {backup_path}")

    # Find and update the Fetch Due Follow-Ups node
    updated = False
    for node in wf["nodes"]:
        if node["name"] == "Fetch Due Follow-Ups":
            old_filter = node["parameters"].get("options", {}).get("filterByFormula", "")
            print(f"  Old filter: {old_filter}")

            # Check if already patched
            if "Ticket Reply" in old_filter:
                print("  WARNING: Filter already contains 'Ticket Reply' exclusion. Skipping.")
                return

            node["parameters"]["options"]["filterByFormula"] = NEW_FILTER
            print(f"  New filter: {NEW_FILTER}")
            updated = True
            break

    if not updated:
        print("  ERROR: Could not find 'Fetch Due Follow-Ups' node!")
        return

    # Push to n8n
    print("Pushing updated workflow to n8n...")

    # Deactivate first
    httpx.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=headers, timeout=30)

    update_payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    resp = httpx.put(
        f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
        headers=headers,
        json=update_payload,
        timeout=30
    )
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    result = resp.json()
    print(f"  Workflow updated: {result.get('name')}")

    # Reactivate
    resp = httpx.post(
        f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate",
        headers=headers,
        timeout=30
    )
    if resp.status_code < 400:
        print("  Workflow reactivated!")
    else:
        print(f"  Activation response: {resp.status_code}")

    # Verify
    resp = httpx.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers, timeout=30)
    final = resp.json()
    for node in final["nodes"]:
        if node["name"] == "Fetch Due Follow-Ups":
            live_filter = node["parameters"].get("options", {}).get("filterByFormula", "")
            print(f"\n  Verified live filter: {live_filter}")
            break

    print("\n=== DONE ===")
    print("Follow-up workflow now excludes leads with these statuses:")
    print("  - 'Ticket Reply - Do Not Follow Up'")
    print("  - 'Converted - Do Not Follow Up'")
    print("  - 'Bounced'")


if __name__ == "__main__":
    main()
