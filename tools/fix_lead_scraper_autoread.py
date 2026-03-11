"""
Fix Lead Scraper - Auto-mark bounce and unsubscribe emails as read.

Problem: When bounce notifications (mailer-daemon) or unsubscribe replies arrive,
the workflow detects them and flags leads in Airtable, but the Gmail messages
themselves stay unread, forcing Ian to manually read/dismiss them.

Fix:
1. Add "Get Bounce Message IDs" Code node after "Flag Bounced Leads"
2. Add "Mark Bounces Read" Gmail markAsRead node
3. Add "Get Unsub Message IDs" Code node after "Flag Unsubscribed Leads"
4. Add "Mark Unsubs Read" Gmail markAsRead node
5. Rewire connections so the mark-as-read nodes run before continuing the flow
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


def uid():
    return str(uuid.uuid4())


def fix_workflow(wf):
    """Add auto-read for bounce and unsubscribe Gmail messages."""
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # --- Node positions (place near existing nodes) ---
    # Flag Bounced Leads is at [1168, 32]
    # Check Unsubscribe Replies is at [1408, 64]
    # Flag Unsubscribed Leads is at [2128, 32]
    # Search Config is at [448, 400]

    # =============================================
    # 1. Add "Get Bounce Message IDs" Code node
    # =============================================
    get_bounce_ids_node = {
        "parameters": {
            "jsCode": (
                "// Get original bounce notification emails and extract their Gmail IDs\n"
                "const bounceEmails = $('Check Bounced Emails').all();\n"
                "const results = bounceEmails\n"
                "  .filter(item => item.json.id)\n"
                "  .map(item => ({ json: { messageId: item.json.id } }));\n"
                "return results.length > 0 ? results : [{ json: { _noMessages: true } }];"
            )
        },
        "id": uid(),
        "name": "Get Bounce Message IDs",
        "type": "n8n-nodes-base.code",
        "position": [1168, -120],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput"
    }

    # =============================================
    # 2. Add "Mark Bounces Read" Gmail node
    # =============================================
    mark_bounces_read_node = {
        "parameters": {
            "operation": "markAsRead",
            "messageId": "={{ $json.messageId }}"
        },
        "id": uid(),
        "name": "Mark Bounces Read",
        "type": "n8n-nodes-base.gmail",
        "position": [1408, -120],
        "typeVersion": 2.1,
        "credentials": {
            "gmailOAuth2": {
                "id": GMAIL_CRED_ID,
                "name": GMAIL_CRED_NAME
            }
        },
        "onError": "continueRegularOutput"
    }

    # =============================================
    # 3. Add "Get Unsub Message IDs" Code node
    # =============================================
    get_unsub_ids_node = {
        "parameters": {
            "jsCode": (
                "// Get original unsubscribe reply emails and extract their Gmail IDs\n"
                "const unsubEmails = $('Check Unsubscribe Replies').all();\n"
                "const results = unsubEmails\n"
                "  .filter(item => item.json.id)\n"
                "  .map(item => ({ json: { messageId: item.json.id } }));\n"
                "return results.length > 0 ? results : [{ json: { _noMessages: true } }];"
            )
        },
        "id": uid(),
        "name": "Get Unsub Message IDs",
        "type": "n8n-nodes-base.code",
        "position": [2128, -120],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput"
    }

    # =============================================
    # 4. Add "Mark Unsubs Read" Gmail node
    # =============================================
    mark_unsubs_read_node = {
        "parameters": {
            "operation": "markAsRead",
            "messageId": "={{ $json.messageId }}"
        },
        "id": uid(),
        "name": "Mark Unsubs Read",
        "type": "n8n-nodes-base.gmail",
        "position": [2368, -120],
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
        get_bounce_ids_node,
        mark_bounces_read_node,
        get_unsub_ids_node,
        mark_unsubs_read_node
    ])

    # =============================================
    # 5. Rewire connections
    # =============================================

    # --- Bounce path ---
    # BEFORE: Flag Bounced Leads -> Check Unsubscribe Replies
    # AFTER:  Flag Bounced Leads -> Get Bounce Message IDs -> Mark Bounces Read
    #         Flag Bounced Leads -> Check Unsubscribe Replies (parallel)

    # Currently Flag Bounced Leads connects to Check Unsubscribe Replies
    # Keep that connection AND add the mark-as-read branch
    existing_bounce_targets = connections.get("Flag Bounced Leads", {}).get("main", [[]])[0]
    connections["Flag Bounced Leads"] = {
        "main": [
            [
                *existing_bounce_targets,
                {
                    "node": "Get Bounce Message IDs",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    connections["Get Bounce Message IDs"] = {
        "main": [
            [
                {
                    "node": "Mark Bounces Read",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    # Mark Bounces Read is a terminal node (no downstream needed)
    connections["Mark Bounces Read"] = {"main": [[]]}

    # --- Unsubscribe path ---
    # BEFORE: Flag Unsubscribed Leads -> Search Config
    # AFTER:  Flag Unsubscribed Leads -> Search Config (keep)
    #         Flag Unsubscribed Leads -> Get Unsub Message IDs -> Mark Unsubs Read (add)

    existing_unsub_targets = connections.get("Flag Unsubscribed Leads", {}).get("main", [[]])[0]
    connections["Flag Unsubscribed Leads"] = {
        "main": [
            [
                *existing_unsub_targets,
                {
                    "node": "Get Unsub Message IDs",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    connections["Get Unsub Message IDs"] = {
        "main": [
            [
                {
                    "node": "Mark Unsubs Read",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    # Mark Unsubs Read is a terminal node
    connections["Mark Unsubs Read"] = {"main": [[]]}

    print(f"Added 4 nodes: Get Bounce Message IDs, Mark Bounces Read, Get Unsub Message IDs, Mark Unsubs Read")
    print(f"Total nodes: {len(nodes)}")

    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    action = sys.argv[1] if len(sys.argv) > 1 else "preview"

    print("=" * 60)
    print("LEAD SCRAPER FIX - Auto-read bounce & unsubscribe emails")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        # Fetch live workflow
        print(f"\n[FETCH] Getting workflow {WORKFLOW_ID}...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        # Apply fix
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
