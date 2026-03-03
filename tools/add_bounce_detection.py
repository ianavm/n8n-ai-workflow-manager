"""
Add bounce detection to the Follow-Up Sequence workflow.

Before running follow-ups each day, the workflow will:
1. Search Gmail for bounce-back / delivery failure emails
2. Extract the bounced recipient email addresses
3. Update those leads in Airtable: Status="Bounced", Follow Up Stage=0
4. Then proceed with normal follow-ups (which will skip Stage=0 leads)

Usage:
    python tools/add_bounce_detection.py
"""

import sys
import json
import uuid
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx

FU_WORKFLOW_ID = Path(__file__).parent.parent / ".tmp" / "follow_up_workflow_id.txt"

CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "7TtMl7ZnJFpC4RGk", "name": "Lead Scraper Airtable"}

AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"


# Code node that extracts bounced email addresses from Gmail bounce notifications
EXTRACT_BOUNCES_CODE = "\n".join([
    "const items = $input.all();",
    "const bouncedEmails = [];",
    "",
    "for (const item of items) {",
    "  const snippet = (item.json.snippet || '').toLowerCase();",
    "  const subject = (item.json.subject || item.json.Subject || '').toLowerCase();",
    "  const body = item.json.textPlain || item.json.text || item.json.snippet || '';",
    "",
    "  // Extract the original recipient from bounce message",
    "  // Common patterns in bounce notifications:",
    "  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g;",
    "  const allEmails = body.match(emailRegex) || [];",
    "",
    "  // Filter out system emails (mailer-daemon, postmaster, etc)",
    "  const recipientEmails = allEmails.filter(e => {",
    "    const lower = e.toLowerCase();",
    "    return !lower.includes('mailer-daemon') &&",
    "           !lower.includes('postmaster') &&",
    "           !lower.includes('googlemail') &&",
    "           !lower.includes('google.com') &&",
    "           !lower.includes('anyvisionmedia') &&",
    "           !lower.includes('ian@');",
    "  });",
    "",
    "  for (const email of recipientEmails) {",
    "    if (!bouncedEmails.includes(email)) {",
    "      bouncedEmails.push(email);",
    "    }",
    "  }",
    "}",
    "",
    "if (bouncedEmails.length === 0) return [];",
    "",
    "return bouncedEmails.map(email => ({",
    "  json: { bouncedEmail: email }",
    "}));",
])


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    workflow_id = FU_WORKFLOW_ID.read_text().strip()
    print(f"Follow-Up Workflow ID: {workflow_id}")

    with httpx.Client(timeout=60) as client:
        resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers)
        wf = resp.json()

        # === ADD NEW NODES ===

        # 1. Check Bounced Emails (Gmail search for bounce notifications)
        check_bounces_id = str(uuid.uuid4())
        check_bounces_node = {
            "parameters": {
                "operation": "getAll",
                "returnAll": False,
                "limit": 50,
                "filters": {
                    "q": "from:mailer-daemon OR from:postmaster OR subject:\"delivery status\" OR subject:\"mail delivery failed\" OR subject:\"undeliverable\" newer_than:2d",
                    "labelIds": ["INBOX"]
                },
                "options": {}
            },
            "id": check_bounces_id,
            "name": "Check Bounced Emails",
            "type": "n8n-nodes-base.gmail",
            "position": [460, 540],
            "typeVersion": 2.1,
            "credentials": {"gmailOAuth2": CRED_GMAIL},
            "onError": "continueRegularOutput",
            "alwaysOutputData": True
        }

        # 2. Extract Bounced Addresses (Code node)
        extract_bounces_id = str(uuid.uuid4())
        extract_bounces_node = {
            "parameters": {"jsCode": EXTRACT_BOUNCES_CODE},
            "id": extract_bounces_id,
            "name": "Extract Bounced Addresses",
            "type": "n8n-nodes-base.code",
            "position": [700, 540],
            "typeVersion": 2,
            "alwaysOutputData": True,
            "onError": "continueRegularOutput"
        }

        # 3. Has Bounces? (IF node)
        has_bounces_id = str(uuid.uuid4())
        has_bounces_node = {
            "parameters": {
                "conditions": {
                    "options": {"version": 2, "typeValidation": "strict", "caseSensitive": True},
                    "combinator": "and",
                    "conditions": [{
                        "id": str(uuid.uuid4()),
                        "operator": {"type": "string", "operation": "exists", "singleValue": True},
                        "leftValue": "={{ $json.bouncedEmail }}",
                        "rightValue": ""
                    }]
                },
                "options": {}
            },
            "id": has_bounces_id,
            "name": "Has Bounces?",
            "type": "n8n-nodes-base.if",
            "position": [940, 540],
            "typeVersion": 2.2
        }

        # 4. Flag Bounced Leads (Airtable update - set Stage=0, Status=Bounced)
        flag_bounced_id = str(uuid.uuid4())
        flag_bounced_node = {
            "parameters": {
                "operation": "update",
                "base": {
                    "__rl": True, "mode": "list",
                    "value": AIRTABLE_BASE_ID,
                    "cachedResultName": "Lead Scraper - Johannesburg CRM"
                },
                "table": {
                    "__rl": True, "mode": "list",
                    "value": AIRTABLE_TABLE_ID,
                    "cachedResultName": "Leads"
                },
                "columns": {
                    "value": {
                        "Follow Up Stage": "=0",
                        "Status": "Bounced",
                        "Next Follow Up Date": "",
                        "Email": "={{ $json.bouncedEmail }}"
                    },
                    "schema": [
                        {"id": "Follow Up Stage", "type": "number", "display": True, "displayName": "Follow Up Stage"},
                        {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                        {"id": "Next Follow Up Date", "type": "string", "display": True, "displayName": "Next Follow Up Date"},
                        {"id": "Email", "type": "string", "display": True, "displayName": "Email"}
                    ],
                    "mappingMode": "defineBelow",
                    "matchingColumns": ["Email"]
                },
                "options": {}
            },
            "id": flag_bounced_id,
            "name": "Flag Bounced Leads",
            "type": "n8n-nodes-base.airtable",
            "position": [1180, 500],
            "typeVersion": 2.1,
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
            "onError": "continueRegularOutput"
        }

        # Add nodes
        wf["nodes"].extend([
            check_bounces_node,
            extract_bounces_node,
            has_bounces_node,
            flag_bounced_node
        ])
        print("Added 4 bounce detection nodes")

        # === REWIRE CONNECTIONS ===
        # Currently: Schedule Trigger -> Fetch Due Follow-Ups
        #            Manual Trigger -> Fetch Due Follow-Ups
        #
        # New flow:  Schedule Trigger -> Check Bounced Emails -> Extract -> Has Bounces?
        #                                                                   /        \
        #                                                          [yes] Flag Bounced   [no]
        #                                                                   \        /
        #                                                              Fetch Due Follow-Ups
        #            Manual Trigger -> Fetch Due Follow-Ups (unchanged for quick testing)

        # Schedule Trigger now goes to Check Bounced Emails first
        wf["connections"]["Schedule Trigger"] = {
            "main": [[{"node": "Check Bounced Emails", "type": "main", "index": 0}]]
        }

        # Check Bounced Emails -> Extract Bounced Addresses
        wf["connections"]["Check Bounced Emails"] = {
            "main": [[{"node": "Extract Bounced Addresses", "type": "main", "index": 0}]]
        }

        # Extract -> Has Bounces?
        wf["connections"]["Extract Bounced Addresses"] = {
            "main": [[{"node": "Has Bounces?", "type": "main", "index": 0}]]
        }

        # Has Bounces? -> [true] Flag Bounced, [false] Fetch Due Follow-Ups
        wf["connections"]["Has Bounces?"] = {
            "main": [
                [{"node": "Flag Bounced Leads", "type": "main", "index": 0}],
                [{"node": "Fetch Due Follow-Ups", "type": "main", "index": 0}]
            ]
        }

        # Flag Bounced Leads -> Fetch Due Follow-Ups (continue to normal flow)
        wf["connections"]["Flag Bounced Leads"] = {
            "main": [[{"node": "Fetch Due Follow-Ups", "type": "main", "index": 0}]]
        }

        print("Rewired connections for bounce detection")

        # === DEPLOY ===
        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/deactivate", headers=headers)
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{workflow_id}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        client.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=headers)

        # Verify
        resp = client.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers)
        final = resp.json()
        func_nodes = [n for n in final["nodes"] if "stickyNote" not in n["type"]]
        print(f"\nDeployed. Active: {final.get('active')}")
        print(f"Nodes: {len(func_nodes)} functional + {len(final['nodes']) - len(func_nodes)} notes")

        # Print bounce detection flow
        print("\nBounce detection flow:")
        print("  Schedule Trigger -> Check Bounced Emails -> Extract Bounced Addresses -> Has Bounces?")
        print("    [yes] -> Flag Bounced Leads (Stage=0, Status=Bounced) -> Fetch Due Follow-Ups")
        print("    [no]  -> Fetch Due Follow-Ups")
        print("  Bounced leads are excluded from future follow-ups (Stage=0 filtered out)")


if __name__ == "__main__":
    main()
