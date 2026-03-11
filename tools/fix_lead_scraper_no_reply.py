"""
Fix Lead Scraper - Detect lead replies, auto-read them, flag as "Replied".

Problem: When a lead replies to our outreach email, the system doesn't detect it.
The lead stays as "Email Sent" and could receive follow-ups. Ian also has to
manually read/dismiss these reply emails.

Fix:
1. Add "Check Lead Replies" Gmail node to fetch unread replies (not bounces/unsubs)
2. Add "Extract Reply Senders" Code node to get sender email addresses
3. Add "Flag Replied Leads" Airtable update (Status = "Replied")
4. Add "Get Reply Message IDs" + "Mark Replies Read" to auto-read them
5. Add "Replied" to Filter New Leads exclusions
6. Wire into the existing bounce/unsub detection chain
"""

import sys
import json
import uuid

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "uq4hnH0YHfhYOOzO"
GMAIL_CRED_ID = "2IuycrTIgWJZEjBE"
GMAIL_CRED_NAME = "Gmail account AVM Tutorial"
AIRTABLE_CRED_ID = "7TtMl7ZnJFpC4RGk"
AIRTABLE_CRED_NAME = "Lead Scraper Airtable"
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"


def uid():
    return str(uuid.uuid4())


def fix_workflow(wf):
    """Add reply detection, auto-read, and Airtable flagging."""
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # Current flow (after our autoread fix):
    # Schedule Trigger -> Check Bounced Emails -> Extract Bounced Addresses -> Has Bounces?
    #   Has Bounces? (true) -> Flag Bounced Leads -> Check Unsubscribe Replies + Get Bounce Message IDs -> Mark Bounces Read
    #   Has Bounces? (false) -> Check Unsubscribe Replies
    # Check Unsubscribe Replies -> Extract Unsubscribe Emails -> Has Unsubscribes?
    #   Has Unsubscribes? (true) -> Flag Unsubscribed Leads -> Search Config + Get Unsub Message IDs -> Mark Unsubs Read
    #   Has Unsubscribes? (false) -> Search Config
    #
    # We'll insert reply checking BEFORE Search Config:
    #   Has Unsubscribes? (true) -> Flag Unsubscribed Leads -> Check Lead Replies (instead of Search Config)
    #   Has Unsubscribes? (false) -> Check Lead Replies (instead of Search Config)
    #   Check Lead Replies -> ... -> Search Config

    # Position reference:
    # Flag Unsubscribed Leads is at ~[2128, 32]
    # Search Config is at [448, 400]
    # We'll place new nodes between them (above the main scraping row)

    # =============================================
    # 1. "Check Lead Replies" - Gmail getAll
    # =============================================
    # Search for unread replies that are NOT bounces and NOT unsubscribes
    check_replies_node = {
        "parameters": {
            "operation": "getAll",
            "filters": {
                "labelIds": ["INBOX"],
                "q": "is:unread newer_than:7d -from:me -from:mailer-daemon -from:postmaster -subject:\"delivery status\" -subject:\"mail delivery failed\" -subject:\"undeliverable\" -subject:\"Workflow ERROR\" -subject:\"Lead Scraper\" -(unsubscribe OR \"opt out\" OR \"remove me\" OR \"stop emailing\" OR \"take me off\" OR \"do not contact\")"
            }
        },
        "id": uid(),
        "name": "Check Lead Replies",
        "type": "n8n-nodes-base.gmail",
        "position": [2368, 64],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "webhookId": uid(),
        "credentials": {
            "gmailOAuth2": {
                "id": GMAIL_CRED_ID,
                "name": GMAIL_CRED_NAME
            }
        },
        "onError": "continueRegularOutput"
    }

    # =============================================
    # 2. "Extract Reply Senders" - Code node
    # =============================================
    extract_replies_node = {
        "parameters": {
            "jsCode": (
                "const items = $input.all();\n"
                "const replySenders = [];\n"
                "const messageIds = [];\n"
                "\n"
                "for (const item of items) {\n"
                "  const from = (item.json.from || '').toLowerCase();\n"
                "  const id = item.json.id;\n"
                "\n"
                "  // Skip our own emails\n"
                "  if (from.includes('anyvisionmedia') || from.includes('ian@')) continue;\n"
                "  if (!id) continue;\n"
                "\n"
                "  // Extract sender email\n"
                "  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g;\n"
                "  const fromEmails = from.match(emailRegex) || [];\n"
                "  const senderEmail = fromEmails.find(e =>\n"
                "    !e.includes('anyvisionmedia') && !e.includes('ian@') &&\n"
                "    !e.includes('noreply') && !e.includes('no-reply') &&\n"
                "    !e.includes('mailer-daemon') && !e.includes('postmaster') &&\n"
                "    !e.includes('google.com') && !e.includes('googlemail')\n"
                "  );\n"
                "\n"
                "  if (senderEmail && !replySenders.includes(senderEmail)) {\n"
                "    replySenders.push(senderEmail);\n"
                "    messageIds.push(id);\n"
                "  }\n"
                "}\n"
                "\n"
                "if (replySenders.length === 0) return [];\n"
                "\n"
                "return replySenders.map((email, i) => ({\n"
                "  json: { replyEmail: email, messageId: messageIds[i] }\n"
                "}));"
            )
        },
        "id": uid(),
        "name": "Extract Reply Senders",
        "type": "n8n-nodes-base.code",
        "position": [2608, 64],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput"
    }

    # =============================================
    # 3. "Has Replies?" - If node
    # =============================================
    has_replies_node = {
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
                        "leftValue": "={{ $json.replyEmail }}",
                        "rightValue": ""
                    }
                ]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Has Replies?",
        "type": "n8n-nodes-base.if",
        "position": [2848, 64],
        "typeVersion": 2.2
    }

    # =============================================
    # 4. "Flag Replied Leads" - Airtable update
    # =============================================
    flag_replied_node = {
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
                    "Status": "Replied",
                    "Follow Up Stage": "=0",
                    "Next Follow Up Date": "",
                    "Email": "={{ $json.replyEmail }}"
                },
                "schema": [
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Follow Up Stage", "type": "number", "display": True, "displayName": "Follow Up Stage"},
                    {"id": "Next Follow Up Date", "type": "string", "display": True, "displayName": "Next Follow Up Date"},
                    {"id": "Email", "type": "string", "display": True, "displayName": "Email"}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Flag Replied Leads",
        "type": "n8n-nodes-base.airtable",
        "position": [3088, 32],
        "typeVersion": 2.1,
        "credentials": {
            "airtableTokenApi": {
                "id": AIRTABLE_CRED_ID,
                "name": AIRTABLE_CRED_NAME
            }
        },
        "onError": "continueRegularOutput"
    }

    # =============================================
    # 5. "Mark Replies Read" - Gmail markAsRead
    # =============================================
    mark_replies_read_node = {
        "parameters": {
            "operation": "markAsRead",
            "messageId": "={{ $json.messageId }}"
        },
        "id": uid(),
        "name": "Mark Replies Read",
        "type": "n8n-nodes-base.gmail",
        "position": [3088, 168],
        "typeVersion": 2.1,
        "credentials": {
            "gmailOAuth2": {
                "id": GMAIL_CRED_ID,
                "name": GMAIL_CRED_NAME
            }
        },
        "onError": "continueRegularOutput"
    }

    # Add all new nodes
    nodes.extend([
        check_replies_node,
        extract_replies_node,
        has_replies_node,
        flag_replied_node,
        mark_replies_read_node
    ])

    # =============================================
    # 6. Rewire connections
    # =============================================

    # --- Redirect unsub paths to Check Lead Replies instead of Search Config ---

    # Has Unsubscribes? currently: true -> Flag Unsubscribed Leads, false -> Search Config
    # Change false path to -> Check Lead Replies
    unsub_conns = connections.get("Has Unsubscribes?", {}).get("main", [[], []])
    if len(unsub_conns) >= 2:
        # Replace Search Config target in false path with Check Lead Replies
        unsub_conns[1] = [{"node": "Check Lead Replies", "type": "main", "index": 0}]
    connections["Has Unsubscribes?"] = {"main": unsub_conns}

    # Flag Unsubscribed Leads currently -> Search Config (+ Get Unsub Message IDs)
    # Change Search Config target to Check Lead Replies
    unsub_flag_conns = connections.get("Flag Unsubscribed Leads", {}).get("main", [[]])[0]
    new_unsub_flag_targets = []
    for target in unsub_flag_conns:
        if target["node"] == "Search Config":
            new_unsub_flag_targets.append({"node": "Check Lead Replies", "type": "main", "index": 0})
        else:
            new_unsub_flag_targets.append(target)
    connections["Flag Unsubscribed Leads"] = {"main": [new_unsub_flag_targets]}

    # --- Wire up the reply detection chain ---

    connections["Check Lead Replies"] = {
        "main": [[{"node": "Extract Reply Senders", "type": "main", "index": 0}]]
    }

    connections["Extract Reply Senders"] = {
        "main": [[{"node": "Has Replies?", "type": "main", "index": 0}]]
    }

    # Has Replies? true -> Flag Replied Leads + Mark Replies Read (parallel)
    # Has Replies? false -> Search Config
    connections["Has Replies?"] = {
        "main": [
            [
                {"node": "Flag Replied Leads", "type": "main", "index": 0},
                {"node": "Mark Replies Read", "type": "main", "index": 0}
            ],
            [
                {"node": "Search Config", "type": "main", "index": 0}
            ]
        ]
    }

    # Flag Replied Leads -> Search Config
    connections["Flag Replied Leads"] = {
        "main": [[{"node": "Search Config", "type": "main", "index": 0}]]
    }

    # Mark Replies Read is terminal (runs parallel with Flag Replied)
    connections["Mark Replies Read"] = {"main": [[]]}

    # =============================================
    # 7. Add "Replied" to Filter New Leads exclusions
    # =============================================
    filter_node = node_map.get("Filter New Leads")
    if filter_node:
        conditions = filter_node["parameters"]["conditions"]["conditions"]
        # Check if "Replied" exclusion already exists
        has_replied = any(
            c.get("rightValue") == "Replied" and
            c.get("operator", {}).get("operation") == "notEquals"
            for c in conditions
        )
        if not has_replied:
            conditions.append({
                "id": uid(),
                "operator": {
                    "type": "string",
                    "operation": "notEquals"
                },
                "leftValue": "={{ $json.status }}",
                "rightValue": "Replied"
            })
            print("  Added 'Replied' exclusion to Filter New Leads")

    print(f"Added 5 nodes: Check Lead Replies, Extract Reply Senders, Has Replies?, Flag Replied Leads, Mark Replies Read")
    print(f"Total nodes: {len(nodes)}")

    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    action = sys.argv[1] if len(sys.argv) > 1 else "preview"

    print("=" * 60)
    print("LEAD SCRAPER FIX - Detect replies, auto-read, prevent re-contact")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        print(f"\n[FETCH] Getting workflow {WORKFLOW_ID}...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        wf = fix_workflow(wf)

        if action == "preview":
            print("\nPreview mode - no changes pushed. Use 'deploy' to push.")
            out_path = "workflows/lead-scraper/workflow_v2_places_api.json"
            with open(out_path, "w") as f:
                json.dump(wf, f, indent=2)
            print(f"Saved preview to {out_path}")

        elif action == "deploy":
            print("\n[DEPLOY] Pushing to n8n...")
            update_payload = {
                "name": wf["name"],
                "nodes": wf["nodes"],
                "connections": wf["connections"],
                "settings": wf.get("settings", {"executionOrder": "v1"})
            }
            put_resp = client.put(
                f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
                headers=headers,
                json=update_payload
            )
            put_resp.raise_for_status()
            print("  Deployed successfully!")

            print("[ACTIVATE] Enabling workflow...")
            act_resp = client.post(
                f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate",
                headers=headers
            )
            act_resp.raise_for_status()
            print("  Activated!")

        else:
            print(f"Unknown action: {action}. Use 'preview' or 'deploy'.")


if __name__ == "__main__":
    main()
