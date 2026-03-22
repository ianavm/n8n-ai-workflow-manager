"""
Fix Business Email Management Automation - Add interested prospect reply handling.

When a prospect replies expressing interest:
1. AI classifies with is_interested_reply = true
2. Sends a "thank you for your reply" email
3. Applies DNT (Do Not Touch) label (Label_9) so they're never auto-processed again
4. Updates lead status in Google Sheets to "Converted"
"""

import sys
import json
import uuid

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "g2uPmEBbAEtz9YP4L8utG"


def uid():
    return str(uuid.uuid4())


def fix_workflow(wf):
    """Apply interested reply detection + DNT handling."""
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # ── FIX 1: Update AI Agent system prompt to detect interested replies ──
    print("  [1] Updating AI Agent system prompt to detect interested replies...")
    ai_agent = node_map["AI Agent"]
    old_system = ai_agent["parameters"]["options"]["systemMessage"]

    # Add is_interested_reply field to the JSON output format in the system prompt
    old_json_block = '"escalation_needed": true or false\n}'
    new_json_block = (
        '"escalation_needed": true or false,\n'
        '  "is_interested_reply": true or false\n}'
    )
    old_system = old_system.replace(old_json_block, new_json_block)

    # Add detection rules for interested replies
    interested_rules = (
        "\n\n## Interested Reply Detection Rules\n"
        "Set is_interested_reply to TRUE if ALL of these apply:\n"
        "- The email appears to be a REPLY to a previous outreach/cold email from AnyVision Media\n"
        "- The sender expresses positive interest (wants to learn more, schedule a call, get pricing, "
        "says 'interested', 'sounds good', 'tell me more', 'let's chat', etc.)\n"
        "- The sender is NOT from AnyVision Media itself\n\n"
        "Set is_interested_reply to FALSE for:\n"
        "- First-time inbound emails (not replies to our outreach)\n"
        "- Negative responses ('not interested', 'unsubscribe', 'remove me')\n"
        "- Automated responses / out-of-office replies\n"
        "- Spam or irrelevant emails"
    )
    old_system += interested_rules
    ai_agent["parameters"]["options"]["systemMessage"] = old_system

    # ── FIX 2: Update Parse AI Response to extract is_interested_reply ──
    print("  [2] Updating Parse AI Response to extract is_interested_reply...")
    parse_node = node_map["Parse AI Response"]
    old_code = parse_node["parameters"]["jsCode"]

    # Add is_interested_reply to the output JSON
    old_line = "      ticket_number: 'TKT-' + Date.now()"
    new_line = (
        "      is_interested_reply: parsed.is_interested_reply || false,\n"
        "      ticket_number: 'TKT-' + Date.now()"
    )
    old_code = old_code.replace(old_line, new_line)
    parse_node["parameters"]["jsCode"] = old_code

    # ── FIX 3: Add "Is Interested Reply?" If node ──
    print("  [3] Adding 'Is Interested Reply?' check node...")
    interested_check_node = {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict"
                },
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.is_interested_reply }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "true"
                        }
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": uid(),
        "name": "Is Interested Reply?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [1248, 2340]
    }
    nodes.append(interested_check_node)

    # ── FIX 4: Add "Send Thank You" Gmail reply node ──
    print("  [4] Adding 'Send Thank You' Gmail reply node...")
    thank_you_message = (
        "Hi {{ $json.sender_name }},\\n\\n"
        "Thank you so much for getting back to us! We really appreciate your interest.\\n\\n"
        "I'll be in touch shortly to discuss how AnyVision Media can help you further. "
        "In the meantime, if you have any questions, feel free to reply to this email.\\n\\n"
        "Looking forward to connecting!\\n\\n"
        "Best regards,\\n"
        "Ian Immelman\\n"
        "AnyVision Media\\n"
        "ian@anyvisionmedia.com"
    )
    thank_you_node = {
        "parameters": {
            "operation": "reply",
            "messageId": "={{ $json.original_message_id }}",
            "message": thank_you_message,
            "options": {}
        },
        "id": uid(),
        "name": "Send Thank You",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1504, 2288],
        "credentials": {
            "gmailOAuth2": {
                "id": "EC2l4faLSdgePOM6",
                "name": "Gmail AVM Tutorial"
            }
        }
    }
    nodes.append(thank_you_node)

    # ── FIX 5: Add "Apply DNT Label" Gmail node ──
    print("  [5] Adding 'Apply DNT Label' node (Label_9)...")
    dnt_label_node = {
        "parameters": {
            "operation": "addLabels",
            "messageId": "={{ $('Send Thank You').first().json.id || $json.original_message_id }}",
            "labelIds": ["Label_9"]
        },
        "id": uid(),
        "name": "Apply DNT Label",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1760, 2288],
        "credentials": {
            "gmailOAuth2": {
                "id": "EC2l4faLSdgePOM6",
                "name": "Gmail AVM Tutorial"
            }
        }
    }
    nodes.append(dnt_label_node)

    # ── FIX 6: Add "Update Lead Status" Google Sheets node ──
    print("  [6] Adding 'Update Lead Status' Google Sheets node...")
    update_lead_node = {
        "parameters": {
            "operation": "update",
            "documentId": {
                "mode": "id",
                "value": "1G2P9gYuPKtqhDkkJaTVLbuA_yxj_IqTI7vuCfhFLklM"
            },
            "sheetName": {
                "mode": "name",
                "value": "Leads"
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "email": "={{ $json.sender }}",
                    "status": "Converted - Do Not Follow Up"
                }
            },
            "options": {
                "cellFormat": "USER_ENTERED",
                "handlingExtraData": "ignoreIt"
            },
            "dataMode": "autoMapInputData"
        },
        "id": uid(),
        "name": "Update Lead Status",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2032, 2288],
        "credentials": {
            "googleSheetsOAuth2Api": {
                "id": "OkpDXxwI8WcUJp4P",
                "name": "Google Sheets AVM Tutorial"
            }
        }
    }
    nodes.append(update_lead_node)

    # ── FIX 7: Add "Not Interested Reply" NoOp node ──
    print("  [7] Adding 'Not Interested Reply' no-op node...")
    not_interested_node = {
        "parameters": {},
        "id": uid(),
        "name": "Not Interested Reply",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [1504, 2432]
    }
    nodes.append(not_interested_node)

    # ── FIX 8: Wire up connections ──
    print("  [8] Wiring connections...")

    # Parse AI Response -> Is Interested Reply? (add as additional output)
    parse_connections = connections.get("Parse AI Response", {"main": [[]]})
    parse_connections["main"][0].append({
        "node": "Is Interested Reply?",
        "type": "main",
        "index": 0
    })
    connections["Parse AI Response"] = parse_connections

    # Is Interested Reply? -> true: Send Thank You, false: Not Interested Reply
    connections["Is Interested Reply?"] = {
        "main": [
            [{"node": "Send Thank You", "type": "main", "index": 0}],
            [{"node": "Not Interested Reply", "type": "main", "index": 0}]
        ]
    }

    # Send Thank You -> Apply DNT Label
    connections["Send Thank You"] = {
        "main": [
            [{"node": "Apply DNT Label", "type": "main", "index": 0}]
        ]
    }

    # Apply DNT Label -> Update Lead Status
    connections["Apply DNT Label"] = {
        "main": [
            [{"node": "Update Lead Status", "type": "main", "index": 0}]
        ]
    }

    print("  All fixes applied successfully!")
    return wf


def main():
    config = load_config()
    base_url = config["n8n"]["base_url"].rstrip("/")
    api_key = config["api_keys"]["n8n"]

    headers = {
        "X-N8N-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    # Fetch live workflow
    print(f"Fetching workflow {WORKFLOW_ID}...")
    resp = httpx.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers, timeout=30)
    resp.raise_for_status()
    wf = resp.json()
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    # Check if already patched
    node_names = [n["name"] for n in wf["nodes"]]
    if "Is Interested Reply?" in node_names:
        print("  WARNING: Workflow already has 'Is Interested Reply?' node. Skipping to avoid double-patching.")
        print("  Re-fetch from backup if you need to re-apply.")
        return

    # Save backup
    backup_path = f"workflows/business_email_mgmt_backup_{WORKFLOW_ID}.json"
    with open(backup_path, "w") as f:
        json.dump(wf, f, indent=2)
    print(f"  Backup saved to {backup_path}")

    # Apply fixes
    wf = fix_workflow(wf)

    # Save patched JSON locally
    local_path = "workflows/business_email_mgmt_automation.json"
    with open(local_path, "w") as f:
        json.dump(wf, f, indent=2)
    print(f"  Patched JSON saved to {local_path}")

    # Push to n8n
    print("Pushing patched workflow to n8n...")
    # Only send the fields n8n expects for update
    update_payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {"executionOrder": "v1"},
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
    print(f"  Workflow updated: {result.get('name')} (v{result.get('versionId', 'unknown')})")

    # Ensure it stays active
    print("Ensuring workflow is active...")
    resp = httpx.post(
        f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate",
        headers=headers,
        timeout=30
    )
    if resp.status_code < 400:
        print("  Workflow is active!")
    else:
        print(f"  Activation response: {resp.status_code} - {resp.text}")
        print("  (Workflow may already be active)")

    print("\n=== DONE ===")
    print("New flow for interested prospect replies:")
    print("  Parse AI Response -> Is Interested Reply?")
    print("    -> YES: Send Thank You -> Apply DNT Label (Label_9) -> Update Lead Status")
    print("    -> NO:  Not Interested Reply (no-op)")


if __name__ == "__main__":
    main()
