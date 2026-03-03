"""
Fix Business Email Management Automation - Skip replies with ticket/enquiry numbers.

When an incoming email contains a ticket number, enquiry number, reference number,
or case number, the workflow should NOT auto-reply (prevents reply loops with
ticketing systems). Additionally, if the sender is a known lead, their follow-up
sequence is stopped by setting Follow Up Stage = 0 in Airtable.

New nodes added:
1. "Check Reference Number" (Code) - regex scan for ticket/enquiry patterns
2. "Has Reference Number?" (IF) - branches on the flag
3. "Update Lead - Stop Follow Up" (Airtable) - sets Follow Up Stage = 0
4. "Skip - Not Ticket Reply" (NoOp) - false branch endpoint

Modified nodes:
- "Reply Needed?" IF node - added has_reference_number == false condition

Connection rewiring:
- Parse AI Response no longer connects directly to "Reply Needed?"
- Instead: Parse AI Response -> Check Reference Number -> Reply Needed?
- Also: Check Reference Number -> Has Reference Number? -> Update Lead / Skip

Usage:
    python tools/fix_ticket_reply_filter.py
"""

import sys
import json
import uuid

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


WORKFLOW_ID = "g2uPmEBbAEtz9YP4L8utG"

# Lead Scraper Airtable (for cross-workflow follow-up stop)
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"
AIRTABLE_CRED_ID = "7TtMl7ZnJFpC4RGk"
AIRTABLE_CRED_NAME = "Lead Scraper Airtable"

# JavaScript code for the Check Reference Number node
CHECK_REF_CODE = r"""
const items = $input.all();

// Ticket / enquiry / reference number patterns (case-insensitive)
const TICKET_PATTERNS = [
  /\bTKT[-#]?\s*\d+/i,
  /\bTICKET\s*[#:]?\s*\d+/i,
  /\bTICKET\s+NUMBER\s*:?\s*\w+/i,
  /\bREF\s*[-:]\s*#?\s*[A-Z0-9]{3,}/i,
  /\bREFERENCE\s*(NUMBER|NO\.?|#)\s*:?\s*[A-Z0-9-]+/i,
  /\bENQ[-#]?\s*\d+/i,
  /\bENQUIRY\s*(NUMBER|NO\.?|#)\s*:?\s*\w+/i,
  /\bCASE\s*(ID|NUMBER|NO\.?|#)\s*:?\s*[A-Z0-9-]+/i,
  /\bINCIDENT\s*(ID|NUMBER|NO\.?|#)\s*:?\s*[A-Z0-9-]+/i,
  /\bSR[-#]\s*\d+/i,
  /\bINC[-#]\s*\d+/i,
  /\b[A-Z]{2,4}-\d{5,}\b/,
];

return items.map(item => {
  const subject = (item.json.original_subject || '').toUpperCase();
  const body = (item.json.original_body || '').substring(0, 2000).toUpperCase();
  const textToCheck = subject + ' ' + body;

  let has_reference_number = false;
  let matched_pattern = '';

  for (const pattern of TICKET_PATTERNS) {
    const match = textToCheck.match(pattern);
    if (match) {
      has_reference_number = true;
      matched_pattern = match[0];
      break;
    }
  }

  return {
    json: {
      ...item.json,
      has_reference_number,
      matched_reference_pattern: matched_pattern
    }
  };
});
"""


def uid():
    return str(uuid.uuid4())


def fix_workflow(wf):
    """Add ticket/enquiry reply detection and filtering."""
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # ── FIX 1: Add "Check Reference Number" Code node ──
    print("  [1] Adding 'Check Reference Number' code node...")
    check_ref_node = {
        "parameters": {
            "jsCode": CHECK_REF_CODE.strip()
        },
        "id": uid(),
        "name": "Check Reference Number",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 1520]
    }
    nodes.append(check_ref_node)

    # ── FIX 2: Add condition to "Reply Needed?" IF node ──
    print("  [2] Adding has_reference_number condition to 'Reply Needed?' IF node...")
    reply_needed = node_map["Reply Needed?"]
    reply_needed["parameters"]["conditions"]["conditions"].append({
        "id": uid(),
        "leftValue": "={{ $json.has_reference_number }}",
        "rightValue": False,
        "operator": {
            "type": "boolean",
            "operation": "false"
        }
    })

    # ── FIX 3: Add "Has Reference Number?" IF node ──
    print("  [3] Adding 'Has Reference Number?' IF node...")
    has_ref_node = {
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
                        "leftValue": "={{ $json.has_reference_number }}",
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
        "name": "Has Reference Number?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [1248, 1680]
    }
    nodes.append(has_ref_node)

    # ── FIX 4: Add "Update Lead - Stop Follow Up" Airtable node ──
    print("  [4] Adding 'Update Lead - Stop Follow Up' Airtable node...")
    update_lead_node = {
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
                    "Email": "={{ $json.sender }}",
                    "Follow Up Stage": 0,
                    "Status": "Ticket Reply - Do Not Follow Up"
                },
                "schema": [
                    {"id": "Email", "type": "string", "display": True,
                     "displayName": "Email"},
                    {"id": "Follow Up Stage", "type": "number", "display": True,
                     "displayName": "Follow Up Stage"},
                    {"id": "Status", "type": "string", "display": True,
                     "displayName": "Status"}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Update Lead - Stop Follow Up",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1504, 1648],
        "credentials": {
            "airtableTokenApi": {
                "id": AIRTABLE_CRED_ID,
                "name": AIRTABLE_CRED_NAME
            }
        },
        "onError": "continueRegularOutput"
    }
    nodes.append(update_lead_node)

    # ── FIX 5: Add "Skip - Not Ticket Reply" NoOp node ──
    print("  [5] Adding 'Skip - Not Ticket Reply' no-op node...")
    skip_node = {
        "parameters": {},
        "id": uid(),
        "name": "Skip - Not Ticket Reply",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [1504, 1780]
    }
    nodes.append(skip_node)

    # ── FIX 6: Rewire connections ──
    print("  [6] Rewiring connections...")

    # Remove the direct Parse AI Response -> Reply Needed? connection
    # and replace with Parse AI Response -> Check Reference Number
    parse_outputs = connections.get("Parse AI Response", {"main": [[]]})["main"][0]
    for i, conn in enumerate(parse_outputs):
        if conn["node"] == "Reply Needed?":
            parse_outputs[i] = {
                "node": "Check Reference Number",
                "type": "main",
                "index": 0
            }
            print("    Redirected Parse AI Response -> Check Reference Number (was -> Reply Needed?)")
            break

    # Check Reference Number -> Reply Needed? AND Has Reference Number?
    connections["Check Reference Number"] = {
        "main": [[
            {"node": "Reply Needed?", "type": "main", "index": 0},
            {"node": "Has Reference Number?", "type": "main", "index": 0}
        ]]
    }

    # Has Reference Number? -> true: Update Lead, false: Skip
    connections["Has Reference Number?"] = {
        "main": [
            [{"node": "Update Lead - Stop Follow Up", "type": "main", "index": 0}],
            [{"node": "Skip - Not Ticket Reply", "type": "main", "index": 0}]
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

    # Idempotency check
    node_names = [n["name"] for n in wf["nodes"]]
    if "Check Reference Number" in node_names:
        print("  WARNING: Workflow already has 'Check Reference Number' node. Skipping to avoid double-patching.")
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

    print("\n=== DONE ===")
    print("New flow for ticket/enquiry reply detection:")
    print("  Parse AI Response -> Check Reference Number -> Reply Needed?")
    print("                                              -> Has Reference Number?")
    print("    -> YES: Update Lead - Stop Follow Up (Airtable: Follow Up Stage=0)")
    print("    -> NO:  Skip - Not Ticket Reply (no-op)")
    print("\nReply Needed? now also checks: has_reference_number == false")


if __name__ == "__main__":
    main()
