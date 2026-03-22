"""
Fix Business Email Management Automation - Opt-out bypass + reply loop.

Bugs fixed:
1. DNT label applied to wrong message (sent reply instead of incoming email)
2. No sender-level opt-out check (new threads bypass per-message label check)
3. Double auto-reply (Reply Needed + Is Interested Reply fire in parallel)
4. Duplicate Is No-Reply? connection (runs twice per email)
5. No opt-out/bounce detection (unsubscribe/remove me emails still get replies)
6. No thread reply limit (auto-reply loop when client replies back)
7. Mark original email as read after Create Reply

Usage:
    python tools/fix_email_optout_loop.py
"""

import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "g2uPmEBbAEtz9YP4L8utG"

# Google Sheets credentials (same as existing nodes)
GSHEETS_CRED_ID = "OkpDXxwI8WcUJp4P"
GSHEETS_CRED_NAME = "Google Sheets AVM Tutorial"
LEADS_SHEET_ID = "1G2P9gYuPKtqhDkkJaTVLbuA_yxj_IqTI7vuCfhFLklM"


def uid():
    return str(uuid.uuid4())


def fix_workflow(wf):
    """Apply all opt-out bypass and reply loop fixes."""
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # =====================================================================
    # FIX 1: Correct DNT Label target (apply to incoming email, not sent reply)
    # =====================================================================
    print("  [1] Fixing Apply DNT Label -> target original incoming email...")
    if "Apply DNT Label" in node_map:
        dnt_node = node_map["Apply DNT Label"]
        dnt_node["parameters"]["messageId"] = "={{ $json.original_message_id }}"
        print("      messageId changed to $json.original_message_id")
    else:
        print("      WARNING: Apply DNT Label node not found")

    # =====================================================================
    # FIX 2: Prevent double auto-reply (add conditions to Reply Needed?)
    # =====================================================================
    print("  [2] Adding is_interested_reply + is_opt_out guards to Reply Needed?...")
    if "Reply Needed?" in node_map:
        reply_needed = node_map["Reply Needed?"]
        conditions = reply_needed["parameters"]["conditions"]["conditions"]

        # Check if already patched
        existing_ids = [c.get("id", "") for c in conditions]

        if "guard-interested-reply" not in existing_ids:
            conditions.append({
                "id": "guard-interested-reply",
                "leftValue": "={{ $json.is_interested_reply }}",
                "rightValue": False,
                "operator": {
                    "type": "boolean",
                    "operation": "false"
                }
            })
            print("      Added: is_interested_reply == false")

        if "guard-opt-out" not in existing_ids:
            conditions.append({
                "id": "guard-opt-out",
                "leftValue": "={{ $json.is_opt_out }}",
                "rightValue": False,
                "operator": {
                    "type": "boolean",
                    "operation": "false"
                }
            })
            print("      Added: is_opt_out == false")
    else:
        print("      WARNING: Reply Needed? node not found")

    # =====================================================================
    # FIX 3A: Update AI Agent system prompt - add is_opt_out detection
    # =====================================================================
    print("  [3A] Updating AI Agent system prompt with opt-out detection...")
    if "AI Agent" in node_map:
        ai_agent = node_map["AI Agent"]
        system_msg = ai_agent["parameters"]["options"]["systemMessage"]

        # Add is_opt_out to JSON output format (after is_interested_reply)
        if '"is_opt_out"' not in system_msg:
            system_msg = system_msg.replace(
                '"is_interested_reply": true or false\n}',
                '"is_interested_reply": true or false,\n  "is_opt_out": true or false\n}'
            )
            print("      Added is_opt_out field to JSON schema")

        # Add opt-out detection rules (after interested reply rules)
        if "Opt-Out / Unsubscribe Detection" not in system_msg:
            opt_out_rules = (
                "\n\n## Opt-Out / Unsubscribe Detection Rules\n"
                "Set is_opt_out to TRUE if ANY of these apply:\n"
                "- Sender says: 'unsubscribe', 'stop emailing', 'remove me', "
                "'opt out', 'do not contact', 'take me off your list', "
                "'not interested please stop', 'cease communication'\n"
                "- The email is a bounce/delivery failure: 'address not found', "
                "'delivery failed', 'mailbox full', 'user unknown', "
                "'undeliverable', 'mailer-daemon', 'postmaster'\n"
                "- The sender explicitly asks to not receive further emails\n\n"
                "When is_opt_out is TRUE, you MUST also set:\n"
                "- action_required: false\n"
                "- suggested_response: null\n"
                "- is_interested_reply: false\n"
                "- department: 'Spam_Irrelevant' (for bounces) or keep original dept (for opt-outs)"
            )
            system_msg += opt_out_rules
            print("      Added opt-out detection rules")

        ai_agent["parameters"]["options"]["systemMessage"] = system_msg
    else:
        print("      WARNING: AI Agent node not found")

    # =====================================================================
    # FIX 3B: Update Parse AI Response - extract is_opt_out
    # =====================================================================
    print("  [3B] Updating Parse AI Response to extract is_opt_out...")
    if "Parse AI Response" in node_map:
        parse_node = node_map["Parse AI Response"]
        code = parse_node["parameters"]["jsCode"]

        if "is_opt_out" not in code:
            code = code.replace(
                "      is_interested_reply: parsed.is_interested_reply || false,",
                "      is_opt_out: parsed.is_opt_out || false,\n"
                "      is_interested_reply: parsed.is_interested_reply || false,"
            )
            parse_node["parameters"]["jsCode"] = code
            print("      Added is_opt_out extraction")
        else:
            print("      is_opt_out already present in Parse AI Response")
    else:
        print("      WARNING: Parse AI Response node not found")

    # =====================================================================
    # FIX 3C: Add opt-out handling nodes
    # =====================================================================
    print("  [3C] Adding opt-out handling nodes...")

    # Is Opt-Out? IF node
    if "Is Opt-Out?" not in node_map:
        opt_out_check = {
            "parameters": {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict"
                    },
                    "conditions": [
                        {
                            "id": "opt-out-check-001",
                            "leftValue": "={{ $json.is_opt_out }}",
                            "rightValue": True,
                            "operator": {
                                "type": "boolean",
                                "operation": "true"
                            }
                        }
                    ]
                },
                "options": {}
            },
            "id": uid(),
            "name": "Is Opt-Out?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [1248, 2600]
        }
        nodes.append(opt_out_check)
        node_map["Is Opt-Out?"] = opt_out_check
        print("      Added 'Is Opt-Out?' IF node")

    # Apply Opt-Out DNT (Gmail: add Label_9)
    if "Apply Opt-Out DNT" not in node_map:
        opt_out_dnt = {
            "parameters": {
                "operation": "addLabels",
                "messageId": "={{ $json.original_message_id }}",
                "labelIds": ["Label_9"]
            },
            "id": uid(),
            "name": "Apply Opt-Out DNT",
            "type": "n8n-nodes-base.gmail",
            "typeVersion": 2.1,
            "position": [1504, 2552],
            "credentials": {}
        }
        nodes.append(opt_out_dnt)
        node_map["Apply Opt-Out DNT"] = opt_out_dnt
        print("      Added 'Apply Opt-Out DNT' Gmail node")

    # Mark Opt-Out Read
    if "Mark Opt-Out Read" not in node_map:
        mark_opt_out = {
            "parameters": {
                "operation": "markAsRead",
                "messageId": "={{ $json.original_message_id }}"
            },
            "id": uid(),
            "name": "Mark Opt-Out Read",
            "type": "n8n-nodes-base.gmail",
            "typeVersion": 2.1,
            "position": [1760, 2552],
            "credentials": {}
        }
        nodes.append(mark_opt_out)
        node_map["Mark Opt-Out Read"] = mark_opt_out
        print("      Added 'Mark Opt-Out Read' Gmail node")

    # Not Opt-Out (NoOp)
    if "Not Opt-Out" not in node_map:
        not_opt_out = {
            "parameters": {},
            "id": uid(),
            "name": "Not Opt-Out",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [1504, 2700]
        }
        nodes.append(not_opt_out)
        node_map["Not Opt-Out"] = not_opt_out
        print("      Added 'Not Opt-Out' NoOp node")

    # Wire opt-out connections
    connections["Is Opt-Out?"] = {
        "main": [
            [{"node": "Apply Opt-Out DNT", "type": "main", "index": 0}],
            [{"node": "Not Opt-Out", "type": "main", "index": 0}]
        ]
    }
    connections["Apply Opt-Out DNT"] = {
        "main": [
            [{"node": "Mark Opt-Out Read", "type": "main", "index": 0}]
        ]
    }

    # =====================================================================
    # FIX 3D: Add is_opt_out guard to Is Interested Reply?
    # =====================================================================
    print("  [3D] Adding is_opt_out guard to Is Interested Reply?...")
    if "Is Interested Reply?" in node_map:
        interested_node = node_map["Is Interested Reply?"]
        int_conditions = interested_node["parameters"]["conditions"]["conditions"]
        int_ids = [c.get("id", "") for c in int_conditions]

        if "guard-opt-out-interested" not in int_ids:
            int_conditions.append({
                "id": "guard-opt-out-interested",
                "leftValue": "={{ $json.is_opt_out }}",
                "rightValue": False,
                "operator": {
                    "type": "boolean",
                    "operation": "false"
                }
            })
            print("      Added: is_opt_out == false")
    else:
        print("      WARNING: Is Interested Reply? node not found")

    # =====================================================================
    # FIX 4: Thread reply limit - detect our signature in quoted thread
    # =====================================================================
    print("  [4] Adding thread reply limit (signature detection) to Reply Needed?...")
    if "Reply Needed?" in node_map:
        reply_needed = node_map["Reply Needed?"]
        conditions = reply_needed["parameters"]["conditions"]["conditions"]
        existing_ids = [c.get("id", "") for c in conditions]

        # Check if email body contains our auto-reply signature
        # This means we already replied in this thread -> don't reply again
        if "thread-loop-guard-1" not in existing_ids:
            conditions.append({
                "id": "thread-loop-guard-1",
                "leftValue": "={{ $json.original_body }}",
                "rightValue": "AnyVision Media Team",
                "operator": {
                    "type": "string",
                    "operation": "notContains"
                }
            })
            print("      Added: body notContains 'AnyVision Media Team'")

        if "thread-loop-guard-2" not in existing_ids:
            conditions.append({
                "id": "thread-loop-guard-2",
                "leftValue": "={{ $json.original_body }}",
                "rightValue": "Ian Immelman\nAnyVision Media",
                "operator": {
                    "type": "string",
                    "operation": "notContains"
                }
            })
            print("      Added: body notContains 'Ian Immelman\\nAnyVision Media'")
    else:
        print("      WARNING: Reply Needed? node not found")

    # =====================================================================
    # FIX 5: Sender-level DNT check (Google Sheets lookup)
    # =====================================================================
    print("  [5] Adding sender-level DNT check (Google Sheets lookup)...")

    # We need to extract the sender email BEFORE the lookup.
    # The Gmail Trigger output has 'from' field. We'll add nodes between
    # "Has DNT Label?" FALSE -> new lookup -> "Prepare Email Data"

    # Lookup Sender Status (Google Sheets)
    if "Lookup Sender Status" not in node_map:
        lookup_node = {
            "parameters": {
                "operation": "read",
                "documentId": {
                    "mode": "id",
                    "value": LEADS_SHEET_ID
                },
                "sheetName": {
                    "mode": "name",
                    "value": "Leads"
                },
                "filtersUI": {
                    "values": [
                        {
                            "lookupColumn": "email",
                            "lookupValue": "={{ $json.from }}"
                        }
                    ]
                },
                "options": {}
            },
            "id": uid(),
            "name": "Lookup Sender Status",
            "type": "n8n-nodes-base.googleSheets",
            "typeVersion": 4.5,
            "position": [464, 520],
            "credentials": {
                "googleSheetsOAuth2Api": {
                    "id": GSHEETS_CRED_ID,
                    "name": GSHEETS_CRED_NAME
                }
            },
            "onError": "continueRegularOutput"
        }
        nodes.append(lookup_node)
        node_map["Lookup Sender Status"] = lookup_node
        print("      Added 'Lookup Sender Status' Google Sheets node")

    # Is Sender DNT? (check if status contains "Do Not Follow Up")
    if "Is Sender DNT?" not in node_map:
        sender_dnt_check = {
            "parameters": {
                "conditions": {
                    "options": {
                        "caseSensitive": False,
                        "leftValue": "",
                        "typeValidation": "loose"
                    },
                    "conditions": [
                        {
                            "id": "sender-dnt-status-check",
                            "leftValue": "={{ $json.status || '' }}",
                            "rightValue": "Do Not Follow Up",
                            "operator": {
                                "type": "string",
                                "operation": "contains"
                            }
                        }
                    ]
                },
                "options": {}
            },
            "id": uid(),
            "name": "Is Sender DNT?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [672, 520]
        }
        nodes.append(sender_dnt_check)
        node_map["Is Sender DNT?"] = sender_dnt_check
        print("      Added 'Is Sender DNT?' IF node")

    # Skip - Sender Blocked (NoOp)
    if "Skip - Sender Blocked" not in node_map:
        skip_blocked = {
            "parameters": {},
            "id": uid(),
            "name": "Skip - Sender Blocked",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [880, 608]
        }
        nodes.append(skip_blocked)
        node_map["Skip - Sender Blocked"] = skip_blocked
        print("      Added 'Skip - Sender Blocked' NoOp node")

    # Rewire: Has DNT Label? FALSE -> Lookup Sender Status -> Is Sender DNT?
    # Currently: Has DNT Label? FALSE -> Prepare Email Data
    # New:       Has DNT Label? FALSE -> Lookup Sender Status -> Is Sender DNT?
    #            Is Sender DNT? TRUE -> Skip - Sender Blocked
    #            Is Sender DNT? FALSE -> Prepare Email Data
    if "Has DNT Label?" in connections:
        dnt_conns = connections["Has DNT Label?"]["main"]
        # dnt_conns[0] = TRUE (skip), dnt_conns[1] = FALSE (process)
        if len(dnt_conns) >= 2:
            dnt_conns[1] = [{"node": "Lookup Sender Status", "type": "main", "index": 0}]
            print("      Rewired: Has DNT Label? FALSE -> Lookup Sender Status")

    connections["Lookup Sender Status"] = {
        "main": [
            [{"node": "Is Sender DNT?", "type": "main", "index": 0}]
        ]
    }
    connections["Is Sender DNT?"] = {
        "main": [
            [{"node": "Skip - Sender Blocked", "type": "main", "index": 0}],
            [{"node": "Prepare Email Data", "type": "main", "index": 0}]
        ]
    }
    print("      Wired: Is Sender DNT? TRUE -> Skip, FALSE -> Prepare Email Data")

    # =====================================================================
    # FIX 6: Remove duplicate Is No-Reply? connection
    # =====================================================================
    print("  [6] Removing duplicate Is No-Reply? connection...")
    if "Parse AI Response" in connections:
        parse_outputs = connections["Parse AI Response"]["main"][0]
        # Find and remove duplicates of Is No-Reply?
        seen_nodes = set()
        cleaned = []
        for conn in parse_outputs:
            key = conn["node"]
            if key == "Is No-Reply?" and key in seen_nodes:
                print(f"      Removed duplicate connection to '{key}'")
                continue
            seen_nodes.add(key)
            cleaned.append(conn)
        connections["Parse AI Response"]["main"][0] = cleaned

    # Also add the Is Opt-Out? connection if not already there
    parse_outputs = connections["Parse AI Response"]["main"][0]
    has_opt_out_conn = any(c["node"] == "Is Opt-Out?" for c in parse_outputs)
    if not has_opt_out_conn:
        parse_outputs.append({
            "node": "Is Opt-Out?",
            "type": "main",
            "index": 0
        })
        print("      Added connection: Parse AI Response -> Is Opt-Out?")

    # =====================================================================
    # FIX 7: Mark original email as read after Create Reply
    # =====================================================================
    print("  [7] Adding Mark Replied Read after Create Reply...")
    if "Mark Replied Read" not in node_map:
        mark_replied = {
            "parameters": {
                "operation": "markAsRead",
                "messageId": "={{ $('Parse AI Response').first().json.original_message_id }}"
            },
            "id": uid(),
            "name": "Mark Replied Read",
            "type": "n8n-nodes-base.gmail",
            "typeVersion": 2.1,
            "position": [1760, 1472],
            "credentials": {}
        }
        nodes.append(mark_replied)
        node_map["Mark Replied Read"] = mark_replied
        print("      Added 'Mark Replied Read' Gmail node")

    # Wire: Create Reply -> Mark Replied Read
    connections["Create Reply"] = {
        "main": [
            [{"node": "Mark Replied Read", "type": "main", "index": 0}]
        ]
    }
    print("      Wired: Create Reply -> Mark Replied Read")

    # =====================================================================
    # Summary
    # =====================================================================
    print("\n  All 7 fixes applied:")
    print("    [1] DNT label now targets incoming email (not sent reply)")
    print("    [2] Reply Needed? guards: is_interested_reply==false, is_opt_out==false")
    print("    [3] Opt-out detection: AI prompt + Parse + Is Opt-Out? branch")
    print("    [4] Thread loop guard: body notContains our signature")
    print("    [5] Sender-level DNT: Google Sheets lookup before processing")
    print("    [6] Removed duplicate Is No-Reply? connection")
    print("    [7] Mark Replied Read after Create Reply")

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

    # Idempotency check
    node_names = [n["name"] for n in wf["nodes"]]
    if "Is Opt-Out?" in node_names and "Lookup Sender Status" in node_names:
        print("  WARNING: Workflow already has opt-out fix nodes. Skipping to avoid double-patching.")
        print("  To re-apply, restore from backup first.")
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

    # Ensure active
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
    print("Fixes applied:")
    print("  1. DNT label -> correct target (incoming email)")
    print("  2. No double auto-reply (interested reply guard)")
    print("  3. Opt-out/bounce detection (AI + new nodes)")
    print("  4. Thread loop guard (signature detection)")
    print("  5. Sender-level DNT check (Google Sheets)")
    print("  6. Duplicate connection removed")
    print("  7. Mark as read after auto-reply")
    print("\nVerify by sending test emails:")
    print("  - 'Please unsubscribe me' -> should get DNT, no reply")
    print("  - Reply to an auto-reply -> should NOT get another auto-reply")
    print("  - New business inquiry -> should still get classified + auto-replied")


if __name__ == "__main__":
    main()
