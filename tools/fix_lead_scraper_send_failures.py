"""
Fix Lead Scraper - Handle email send failures.

Problem: When Gmail fails to send (invalid email, mailbox not found, etc.),
the workflow still marks the lead as "Email Sent" with a follow-up date,
causing repeated attempts to contact invalid addresses.

Root cause: Send Outreach Email has onError=continueRegularOutput, and
Update Lead Status blindly sets Status="Email Sent" regardless of outcome.

Fixes:
1. Add "Check Send Success" If node after Send Outreach Email
2. Success path -> existing Update Lead Status (Status = "Email Sent")
3. Failure path -> new "Flag Send Failed" Airtable update (Status = "Send Failed")
4. Add "Send Failed" and "Email Sent" to Filter New Leads exclusions
"""

import sys
import json
import uuid

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"


def uid():
    return str(uuid.uuid4())


def fix_workflow(wf):
    """Add send failure handling to the email pipeline."""
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # ── FIX 1: Add "Check Send Success" If node after Send Outreach Email ──
    print("  [1] Adding Check Send Success node...")

    # Gmail success returns an 'id' field (the message ID)
    # Gmail failure with continueRegularOutput returns error info, no 'id'
    check_send_node = {
        "parameters": {
            "conditions": {
                "options": {
                    "version": 2,
                    "caseSensitive": True,
                    "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [
                    {
                        "id": uid(),
                        "operator": {
                            "type": "string",
                            "operation": "exists",
                            "singleValue": True
                        },
                        "leftValue": "={{ $json.id }}",
                        "rightValue": ""
                    }
                ]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Check Send Success",
        "type": "n8n-nodes-base.if",
        "position": [
            4256,  # Between Send Outreach Email (4032) and Update Lead Status
            64
        ],
        "typeVersion": 2.2,
        "alwaysOutputData": True
    }
    nodes.append(check_send_node)

    # ── FIX 2: Add "Flag Send Failed" Airtable update node ──
    print("  [2] Adding Flag Send Failed node...")

    flag_failed_node = {
        "parameters": {
            "operation": "update",
            "base": {
                "__rl": True,
                "mode": "list",
                "value": AIRTABLE_BASE_ID,
                "cachedResultName": "Lead Scraper - Johannesburg CRM"
            },
            "table": {
                "__rl": True,
                "mode": "list",
                "value": AIRTABLE_TABLE_ID,
                "cachedResultName": "Leads"
            },
            "columns": {
                "value": {
                    "Status": "Send Failed",
                    "Follow Up Stage": "=0",
                    "Next Follow Up Date": "",
                    "Notes": "={{ 'Send failed: ' + ($json.message || $json.error || 'unknown error') }}",
                    "Email": "={{ $('Format Email').item.json.leadEmail }}"
                },
                "schema": [
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Follow Up Stage", "type": "number", "display": True, "displayName": "Follow Up Stage"},
                    {"id": "Next Follow Up Date", "type": "string", "display": True, "displayName": "Next Follow Up Date"},
                    {"id": "Notes", "type": "string", "display": True, "displayName": "Notes"},
                    {"id": "Email", "type": "string", "display": True, "displayName": "Email"}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Flag Send Failed",
        "type": "n8n-nodes-base.airtable",
        "position": [
            4480,
            200  # Below the success path
        ],
        "typeVersion": 2.1,
        "credentials": node_map["Update Lead Status"]["credentials"],
        "onError": "continueRegularOutput"
    }
    nodes.append(flag_failed_node)

    # ── FIX 3: Reposition Update Lead Status to make room ──
    print("  [3] Repositioning nodes...")
    node_map["Update Lead Status"]["position"] = [4480, 64]

    # ── FIX 4: Rewire connections ──
    print("  [4] Rewiring connections...")

    # Old: Send Outreach Email -> Update Lead Status
    # New: Send Outreach Email -> Check Send Success
    #      Check Send Success [true/0] -> Update Lead Status
    #      Check Send Success [false/1] -> Flag Send Failed
    connections["Send Outreach Email"] = {
        "main": [[
            {"node": "Check Send Success", "type": "main", "index": 0}
        ]]
    }

    connections["Check Send Success"] = {
        "main": [
            # Output 0 (true = has message ID = success)
            [{"node": "Update Lead Status", "type": "main", "index": 0}],
            # Output 1 (false = no message ID = failure)
            [{"node": "Flag Send Failed", "type": "main", "index": 0}]
        ]
    }

    # Flag Send Failed has no downstream (ends here)
    # Remove any auto-created connection for it
    connections.pop("Flag Send Failed", None)

    # ── FIX 5: Update Filter New Leads to also exclude "Send Failed" and "Email Sent" ──
    print("  [5] Updating Filter New Leads to exclude Send Failed and Email Sent...")
    filter_node = node_map["Filter New Leads"]
    conditions = filter_node["parameters"]["conditions"]["conditions"]

    # Check what's already excluded
    excluded_statuses = set()
    for cond in conditions:
        op = cond.get("operator", {})
        if op.get("operation") == "notEquals" and "status" in str(cond.get("leftValue", "")).lower():
            excluded_statuses.add(cond.get("rightValue", ""))

    # Add "Send Failed" if not already excluded
    if "Send Failed" not in excluded_statuses:
        conditions.append({
            "id": uid(),
            "operator": {
                "type": "string",
                "operation": "notEquals"
            },
            "leftValue": "={{ $json.status }}",
            "rightValue": "Send Failed"
        })
        print("    -> Added: status != 'Send Failed'")

    # Add "Email Sent" if not already excluded (prevents re-emailing existing leads)
    if "Email Sent" not in excluded_statuses:
        conditions.append({
            "id": uid(),
            "operator": {
                "type": "string",
                "operation": "notEquals"
            },
            "leftValue": "={{ $json.status }}",
            "rightValue": "Email Sent"
        })
        print("    -> Added: status != 'Email Sent'")

    print(f"    -> Filter now excludes: {excluded_statuses | {'Send Failed', 'Email Sent'}}")

    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    print("=" * 60)
    print("LEAD SCRAPER FIX - Handle Email Send Failures")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        # 1. Fetch current workflow
        print("\n[FETCH] Getting current workflow...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} (nodes: {len(wf['nodes'])})")

        # 2. Apply fixes
        print("\n[FIX] Applying send failure handling...")
        wf = fix_workflow(wf)

        # 3. Save locally
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "lead_scraper_fixed_send_failures.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] Saved to {output_path}")

        # 4. Deploy
        print("\n[DEPLOY] Pushing to n8n...")
        update_payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=update_payload
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"  Deployed: {result['name']} (ID: {result['id']})")
        print(f"  Active: {result.get('active')}")

    print("\n" + "=" * 60)
    print("FIX DEPLOYED SUCCESSFULLY")
    print("=" * 60)
    print("\nChanges made:")
    print("  1. Added 'Check Send Success' If node after Send Outreach Email")
    print("     - Checks for Gmail message ID (present on success)")
    print("  2. Added 'Flag Send Failed' Airtable node on failure path")
    print("     - Sets Status='Send Failed', Follow Up Stage=0, clears Next Follow Up Date")
    print("     - Records error message in Notes field")
    print("  3. Success path still goes to Update Lead Status (Email Sent)")
    print("  4. Filter New Leads now excludes: Bounced, Unsubscribed, Do Not Contact,")
    print("     Send Failed, and Email Sent")


if __name__ == "__main__":
    main()
