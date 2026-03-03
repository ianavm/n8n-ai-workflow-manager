"""
Add bounce and unsubscribe suppression to the Lead Scraper workflow.

Prevents re-contacting bounced or opted-out contacts by:
1. Detecting bounce notifications from Gmail before scraping
2. Detecting unsubscribe replies from Gmail before scraping
3. Flagging bounced/unsubscribed leads in Airtable (Status + Follow Up Stage=0)
4. Enhancing Filter New Leads with explicit suppression status checks
5. Fixing Airtable upsert operation (create -> upsert)
6. Updating email footer with clearer unsubscribe instructions

The suppression runs BEFORE scraping so Status is updated before upsert.

Usage:
    python tools/fix_lead_scraper_suppression.py
"""

import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
import httpx


# === CONSTANTS ===
WORKFLOW_ID = "uq4hnH0YHfhYOOzO"
AIRTABLE_BASE_ID = "app2ALQUP7CKEkHOz"
AIRTABLE_TABLE_ID = "tblOsuh298hB9WWrA"
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "7TtMl7ZnJFpC4RGk", "name": "Lead Scraper Airtable"}


def uid():
    return str(uuid.uuid4())


# === GMAIL SEARCH QUERIES ===

BOUNCE_SEARCH_QUERY = (
    '(from:mailer-daemon OR from:postmaster OR subject:"delivery status" '
    'OR subject:"mail delivery failed" OR subject:"undeliverable") '
    '-from:me '
    '-subject:"Workflow ERROR" '
    '-subject:"Lead Scraper Report" '
    'is:unread newer_than:7d'
)

UNSUBSCRIBE_SEARCH_QUERY = (
    '("unsubscribe" OR "opt out" OR "remove me" OR "stop emailing" '
    'OR "take me off" OR "do not contact" OR "not interested") '
    '-from:me '
    '-from:anyvisionmedia '
    '-subject:"Workflow ERROR" '
    '-subject:"Lead Scraper Report" '
    'is:unread newer_than:7d'
)


# === JAVASCRIPT CODE BLOCKS ===

# Reuse refined bounce extraction from fix_bounce_filter.py
EXTRACT_BOUNCES_CODE = "\n".join([
    "const items = $input.all();",
    "const bouncedEmails = [];",
    "",
    "for (const item of items) {",
    "  const body = item.json.textPlain || item.json.text || item.json.snippet || '';",
    "  const from = (item.json.from || '').toLowerCase();",
    "",
    "  // Skip emails that are from ourselves",
    "  if (from.includes('anyvisionmedia') || from.includes('ian@')) continue;",
    "",
    "  // Extract email addresses from the bounce message body",
    "  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g;",
    "  const allEmails = body.match(emailRegex) || [];",
    "",
    "  // Filter out system/internal emails - only keep the original recipient",
    "  const recipientEmails = allEmails.filter(e => {",
    "    const lower = e.toLowerCase();",
    "    return !lower.includes('mailer-daemon') &&",
    "           !lower.includes('postmaster') &&",
    "           !lower.includes('googlemail') &&",
    "           !lower.includes('google.com') &&",
    "           !lower.includes('gmail.com') &&",
    "           !lower.includes('anyvisionmedia') &&",
    "           !lower.includes('ian@') &&",
    "           !lower.includes('noreply') &&",
    "           !lower.includes('no-reply');",
    "  });",
    "",
    "  for (const email of recipientEmails) {",
    "    if (!bouncedEmails.includes(email.toLowerCase())) {",
    "      bouncedEmails.push(email.toLowerCase());",
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

EXTRACT_UNSUBS_CODE = "\n".join([
    "const items = $input.all();",
    "const unsubEmails = [];",
    "",
    "for (const item of items) {",
    "  const from = (item.json.from || '').toLowerCase();",
    "  const subject = (item.json.subject || '').toLowerCase();",
    "  const body = (item.json.textPlain || item.json.text || item.json.snippet || '').toLowerCase();",
    "",
    "  // Skip emails from ourselves",
    "  if (from.includes('anyvisionmedia') || from.includes('ian@')) continue;",
    "",
    "  // Verify body/subject actually contains opt-out language",
    "  const optOutTerms = ['unsubscribe', 'opt out', 'remove me', 'stop emailing',",
    "    'take me off', 'do not contact', 'not interested', 'cease communication',",
    "    'no longer interested', 'stop sending'];",
    "  const hasOptOut = optOutTerms.some(term =>",
    "    subject.includes(term) || body.includes(term)",
    "  );",
    "  if (!hasOptOut) continue;",
    "",
    "  // Extract sender email",
    "  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g;",
    "  const fromEmails = from.match(emailRegex) || [];",
    "  const senderEmail = fromEmails.find(e =>",
    "    !e.includes('anyvisionmedia') && !e.includes('ian@') &&",
    "    !e.includes('noreply') && !e.includes('no-reply') &&",
    "    !e.includes('mailer-daemon') && !e.includes('postmaster')",
    "  );",
    "",
    "  if (senderEmail && !unsubEmails.includes(senderEmail)) {",
    "    unsubEmails.push(senderEmail);",
    "  }",
    "}",
    "",
    "if (unsubEmails.length === 0) return [];",
    "",
    "return unsubEmails.map(email => ({",
    "  json: { unsubEmail: email }",
    "}));",
])


# === NODE BUILDERS ===

def build_bounce_detection_nodes():
    """Build the 4 bounce detection nodes."""

    check_bounces = {
        "parameters": {
            "operation": "getAll",
            "returnAll": False,
            "limit": 50,
            "filters": {
                "q": BOUNCE_SEARCH_QUERY,
                "labelIds": ["INBOX"]
            },
            "options": {"readStatus": "unread"}
        },
        "id": uid(),
        "name": "Check Bounced Emails",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 60],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
        "alwaysOutputData": True
    }

    extract_bounces = {
        "parameters": {"jsCode": EXTRACT_BOUNCES_CODE},
        "id": uid(),
        "name": "Extract Bounced Addresses",
        "type": "n8n-nodes-base.code",
        "position": [680, 60],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput"
    }

    has_bounces = {
        "parameters": {
            "conditions": {
                "options": {
                    "version": 2,
                    "caseSensitive": True,
                    "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [{
                    "id": uid(),
                    "operator": {
                        "type": "string",
                        "operation": "exists",
                        "singleValue": True
                    },
                    "leftValue": "={{ $json.bouncedEmail }}",
                    "rightValue": ""
                }]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Has Bounces?",
        "type": "n8n-nodes-base.if",
        "position": [920, 60],
        "typeVersion": 2.2
    }

    flag_bounced = {
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
        "id": uid(),
        "name": "Flag Bounced Leads",
        "type": "n8n-nodes-base.airtable",
        "position": [1160, 20],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput"
    }

    return [check_bounces, extract_bounces, has_bounces, flag_bounced]


def build_unsubscribe_detection_nodes():
    """Build the 4 unsubscribe detection nodes."""

    check_unsubs = {
        "parameters": {
            "operation": "getAll",
            "returnAll": False,
            "limit": 50,
            "filters": {
                "q": UNSUBSCRIBE_SEARCH_QUERY,
                "labelIds": ["INBOX"]
            },
            "options": {"readStatus": "unread"}
        },
        "id": uid(),
        "name": "Check Unsubscribe Replies",
        "type": "n8n-nodes-base.gmail",
        "position": [1400, 60],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
        "alwaysOutputData": True
    }

    extract_unsubs = {
        "parameters": {"jsCode": EXTRACT_UNSUBS_CODE},
        "id": uid(),
        "name": "Extract Unsubscribe Emails",
        "type": "n8n-nodes-base.code",
        "position": [1640, 60],
        "typeVersion": 2,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput"
    }

    has_unsubs = {
        "parameters": {
            "conditions": {
                "options": {
                    "version": 2,
                    "caseSensitive": True,
                    "typeValidation": "strict"
                },
                "combinator": "and",
                "conditions": [{
                    "id": uid(),
                    "operator": {
                        "type": "string",
                        "operation": "exists",
                        "singleValue": True
                    },
                    "leftValue": "={{ $json.unsubEmail }}",
                    "rightValue": ""
                }]
            },
            "options": {}
        },
        "id": uid(),
        "name": "Has Unsubscribes?",
        "type": "n8n-nodes-base.if",
        "position": [1880, 60],
        "typeVersion": 2.2
    }

    flag_unsub = {
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
                    "Status": "Unsubscribed",
                    "Next Follow Up Date": "",
                    "Email": "={{ $json.unsubEmail }}"
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
        "id": uid(),
        "name": "Flag Unsubscribed Leads",
        "type": "n8n-nodes-base.airtable",
        "position": [2120, 20],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput"
    }

    return [check_unsubs, extract_unsubs, has_unsubs, flag_unsub]


# === MAIN FIX FUNCTION ===

def fix_workflow(wf):
    """Apply all suppression fixes to the workflow."""
    nodes = wf["nodes"]
    connections = wf["connections"]
    node_map = {n["name"]: n for n in nodes}

    # ── IDEMPOTENCY CHECK ──
    if "Check Bounced Emails" in node_map:
        print("  WARNING: Suppression nodes already exist. Skipping.")
        return wf

    # ── PHASE 1a: Add bounce detection nodes ──
    print("  [1] Adding bounce detection nodes...")
    bounce_nodes = build_bounce_detection_nodes()
    nodes.extend(bounce_nodes)

    # ── PHASE 1b: Add unsubscribe detection nodes ──
    print("  [2] Adding unsubscribe detection nodes...")
    unsub_nodes = build_unsubscribe_detection_nodes()
    nodes.extend(unsub_nodes)

    # ── Add sticky note documenting suppression ──
    suppression_note = {
        "parameters": {
            "content": (
                "## PRE-PROCESSING: Suppression Checks\n\n"
                "**Bounce Detection:** Searches Gmail for delivery failures "
                "(mailer-daemon, postmaster) from the last 7 days. "
                "Marks bounced leads: Status=Bounced, Stage=0.\n\n"
                "**Unsubscribe Detection:** Searches Gmail for opt-out replies "
                "(unsubscribe, opt out, remove me, stop emailing). "
                "Marks leads: Status=Unsubscribed, Stage=0.\n\n"
                "Both run BEFORE scraping so suppressed leads are "
                "excluded from email outreach."
            ),
            "height": 220,
            "width": 440
        },
        "id": uid(),
        "name": "Note - Suppression",
        "type": "n8n-nodes-base.stickyNote",
        "position": [400, -120],
        "typeVersion": 1
    }
    nodes.append(suppression_note)
    print("  [3] Added suppression documentation note")

    # ── PHASE 2: Rewire connections ──
    # Serial flow: Schedule Trigger -> bounce chain -> unsub chain -> Search Config
    # Manual Trigger -> Search Config (unchanged, skips suppression for quick testing)
    print("  [4] Rewiring connections for suppression chain...")

    # Schedule Trigger now starts bounce detection
    connections["Schedule Trigger"] = {
        "main": [[{"node": "Check Bounced Emails", "type": "main", "index": 0}]]
    }

    # Bounce detection chain
    connections["Check Bounced Emails"] = {
        "main": [[{"node": "Extract Bounced Addresses", "type": "main", "index": 0}]]
    }
    connections["Extract Bounced Addresses"] = {
        "main": [[{"node": "Has Bounces?", "type": "main", "index": 0}]]
    }
    # Has Bounces? [true] -> Flag Bounced, [false] -> Check Unsubscribe Replies
    connections["Has Bounces?"] = {
        "main": [
            [{"node": "Flag Bounced Leads", "type": "main", "index": 0}],
            [{"node": "Check Unsubscribe Replies", "type": "main", "index": 0}]
        ]
    }
    # Flag Bounced -> Check Unsubscribe Replies (continue to unsub check)
    connections["Flag Bounced Leads"] = {
        "main": [[{"node": "Check Unsubscribe Replies", "type": "main", "index": 0}]]
    }

    # Unsubscribe detection chain
    connections["Check Unsubscribe Replies"] = {
        "main": [[{"node": "Extract Unsubscribe Emails", "type": "main", "index": 0}]]
    }
    connections["Extract Unsubscribe Emails"] = {
        "main": [[{"node": "Has Unsubscribes?", "type": "main", "index": 0}]]
    }
    # Has Unsubscribes? [true] -> Flag Unsubscribed, [false] -> Search Config
    connections["Has Unsubscribes?"] = {
        "main": [
            [{"node": "Flag Unsubscribed Leads", "type": "main", "index": 0}],
            [{"node": "Search Config", "type": "main", "index": 0}]
        ]
    }
    # Flag Unsubscribed -> Search Config (continue to main scraping flow)
    connections["Flag Unsubscribed Leads"] = {
        "main": [[{"node": "Search Config", "type": "main", "index": 0}]]
    }

    # Manual Trigger -> Search Config (keep unchanged for quick testing)
    connections["Manual Trigger"] = {
        "main": [[{"node": "Search Config", "type": "main", "index": 0}]]
    }

    # ── PHASE 3: Enhance Filter New Leads ──
    print("  [5] Enhancing Filter New Leads with suppression checks...")
    filter_node = node_map.get("Filter New Leads")
    if filter_node:
        filter_node["parameters"]["conditions"] = {
            "options": {
                "version": 2,
                "leftValue": "",
                "caseSensitive": True,
                "typeValidation": "strict"
            },
            "combinator": "and",
            "conditions": [
                {
                    "id": uid(),
                    "operator": {
                        "type": "boolean",
                        "operation": "true",
                        "singleValue": True
                    },
                    "leftValue": "={{ $json.isNew }}",
                    "rightValue": ""
                },
                {
                    "id": uid(),
                    "operator": {
                        "type": "string",
                        "operation": "exists",
                        "singleValue": True
                    },
                    "leftValue": "={{ $json.email }}",
                    "rightValue": ""
                },
                {
                    "id": uid(),
                    "operator": {
                        "type": "string",
                        "operation": "notEquals"
                    },
                    "leftValue": "={{ $json.status }}",
                    "rightValue": "Bounced"
                },
                {
                    "id": uid(),
                    "operator": {
                        "type": "string",
                        "operation": "notEquals"
                    },
                    "leftValue": "={{ $json.status }}",
                    "rightValue": "Unsubscribed"
                },
                {
                    "id": uid(),
                    "operator": {
                        "type": "string",
                        "operation": "notEquals"
                    },
                    "leftValue": "={{ $json.status }}",
                    "rightValue": "Do Not Contact"
                }
            ]
        }
    else:
        print("    WARNING: Filter New Leads node not found!")

    # ── PHASE 4: Fix Airtable upsert operation ──
    print("  [6] Fixing Airtable upsert operation...")
    crm_node = None
    for name in ["Upsert to Airtable", "Create in Airtable"]:
        if name in node_map:
            crm_node = node_map[name]
            break

    if crm_node:
        # Ensure operation is "upsert" (not "create")
        old_op = crm_node["parameters"].get("operation", "unknown")
        crm_node["parameters"]["operation"] = "upsert"
        print(f"    Changed operation: {old_op} -> upsert")

        # Ensure matchingColumns is set
        crm_node["parameters"]["columns"]["matchingColumns"] = ["Email"]

        # Ensure Status is NOT in upsert columns (preserve existing status)
        columns_value = crm_node["parameters"]["columns"]["value"]
        if "Status" in columns_value:
            del columns_value["Status"]
            print("    Removed Status from upsert columns (preserves existing)")

        # Add Contact Name if missing
        if "Contact Name" not in columns_value:
            columns_value["Contact Name"] = "={{ $json.contactName }}"
            # Add to schema too
            schema = crm_node["parameters"]["columns"].get("schema", [])
            has_contact = any(s["id"] == "Contact Name" for s in schema)
            if not has_contact:
                schema.append({
                    "id": "Contact Name", "type": "string", "display": True,
                    "removed": False, "required": False,
                    "displayName": "Contact Name", "defaultMatch": False,
                    "canBeUsedToMatch": True
                })
            print("    Added Contact Name to upsert columns")

        # Ensure correct Airtable IDs
        crm_node["parameters"]["base"]["value"] = AIRTABLE_BASE_ID
        crm_node["parameters"]["table"]["value"] = AIRTABLE_TABLE_ID
    else:
        print("    WARNING: Airtable CRM node not found!")

    # ── PHASE 5: Update email footer ──
    print("  [7] Updating email footer with clearer unsubscribe text...")
    format_node = node_map.get("Format Email")
    if format_node:
        code = format_node["parameters"]["jsCode"]
        old_footers = [
            'You received this because your business was listed on Google Maps. Reply &quot;unsubscribe&quot; to be removed.',
            'You received this because your business was listed publicly on Google. Reply &quot;unsubscribe&quot; to be removed.',
        ]
        new_footer = (
            'This email was sent because your business is publicly listed on Google. '
            'If you do not wish to receive further communication, simply reply with '
            'the word &quot;unsubscribe&quot; and you will be permanently removed within 24 hours.'
        )
        replaced = False
        for old in old_footers:
            if old in code:
                code = code.replace(old, new_footer)
                replaced = True
                break
        if replaced:
            format_node["parameters"]["jsCode"] = code
            print("    Updated unsubscribe footer text")
        else:
            print("    Footer text not found (may have been updated already)")
    else:
        print("    WARNING: Format Email node not found!")

    # ── Summary ──
    func_nodes = [n for n in nodes if "stickyNote" not in n.get("type", "")]
    print(f"\n  Final: {len(func_nodes)} functional nodes, {len(nodes) - len(func_nodes)} notes")
    print(f"  Connections: {len(connections)} entries")

    return wf


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    print("=" * 60)
    print("LEAD SCRAPER SUPPRESSION FIX")
    print("Add bounce + unsubscribe detection")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        # 1. Fetch live workflow
        print("\n[FETCH] Getting current workflow...")
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        resp.raise_for_status()
        wf = resp.json()
        print(f"  Got: {wf['name']} (nodes: {len(wf['nodes'])})")

        # 2. Save backup
        backup_dir = Path(__file__).parent.parent / "workflows" / "lead-scraper"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / "workflow_backup_pre_suppression.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"  Backup saved: {backup_path}")

        # 3. Apply fixes
        print("\n[FIX] Applying suppression fixes...")
        wf = fix_workflow(wf)

        # 4. Save patched version locally
        patched_path = backup_dir / "workflow_v2_with_suppression.json"
        with open(patched_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] Saved patched workflow: {patched_path}")

        # 5. Deploy
        print("\n[DEPLOY] Pushing to n8n...")
        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/deactivate", headers=headers)
        print("  Deactivated workflow")

        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        print("  Pushed updated workflow")

        client.post(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}/activate", headers=headers)
        print("  Reactivated workflow")

        # 6. Verify
        resp = client.get(f"{base_url}/api/v1/workflows/{WORKFLOW_ID}", headers=headers)
        final = resp.json()
        func_nodes = [n for n in final["nodes"] if "stickyNote" not in n.get("type", "")]
        print(f"\n  Deployed: {final['name']}")
        print(f"  Active: {final.get('active')}")
        print(f"  Nodes: {len(func_nodes)} functional + {len(final['nodes']) - len(func_nodes)} notes")

    print("\n" + "=" * 60)
    print("SUPPRESSION FIX DEPLOYED SUCCESSFULLY")
    print("=" * 60)
    print("\nNew suppression flow:")
    print("  Schedule Trigger")
    print("    -> Check Bounced Emails -> Extract -> Has Bounces?")
    print("       [yes] -> Flag Bounced Leads (Status=Bounced, Stage=0)")
    print("       [both] -> Check Unsubscribe Replies -> Extract -> Has Unsubs?")
    print("          [yes] -> Flag Unsubscribed (Status=Unsubscribed, Stage=0)")
    print("          [both] -> Search Config -> ... normal scraping flow ...")
    print("\nFilter New Leads now also blocks: Bounced, Unsubscribed, Do Not Contact")
    print("Airtable upsert operation fixed: create -> upsert")
    print("Email footer updated with clearer unsubscribe instructions")


if __name__ == "__main__":
    main()
