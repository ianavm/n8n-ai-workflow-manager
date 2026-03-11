"""
Deploy Global Email Suppression System.

Creates a sub-workflow on n8n that checks the Email Suppression table in Airtable
before any email is sent. Then patches ALL active email-sending workflows to call
this sub-workflow before their Gmail send nodes.

Architecture:
  1. Sub-workflow "Email Suppression Check" (Execute Workflow Trigger)
     - Input: email address
     - Searches Email Suppression table (Airtable)
     - Returns: { suppressed: true/false, reason: "..." }

  2. Each email-sending workflow gets 2 new nodes before every Gmail send:
     - "Check Suppression" (Execute Sub-Workflow) -> calls the sub-workflow
     - "Is Suppressed?" (If node) -> blocks send if suppressed=true

  3. Lead Scraper opt-out detection also writes to the global suppression table

Airtable:
  - Base: app2ALQUP7CKEkHOz (Lead Scraper base)
  - Table: tbl0LtepawDzFYg4I (Email Suppression)

Active workflows to patch:
  - uq4hnH0YHfhYOOzO  Lead Scraper (+ write opt-outs to suppression table)
  - CWQ9zjCTaf56RBe6  Accounting WF-02 Collections -> Send Reminder Email
  - twSg4SfNdlmdITHj  Accounting WF-01 Invoicing -> Send Invoice Email, Send Approval Email
  - ygwBtSysINRWHJxB  Accounting WF-03 Payments -> Send Receipt Email
"""

import sys
import json
import uuid

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx


# ── CONFIG ──────────────────────────────────────────────────────────────────
AIRTABLE_BASE = "app2ALQUP7CKEkHOz"
SUPPRESSION_TABLE = "tbl0LtepawDzFYg4I"
CRED_AIRTABLE = "7TtMl7ZnJFpC4RGk"  # Lead Scraper Airtable PAT

# Workflows to patch: { workflow_id: [list of Gmail send node names to protect] }
WORKFLOWS_TO_PATCH = {
    "CWQ9zjCTaf56RBe6": ["Send Reminder Email"],
    "twSg4SfNdlmdITHj": ["Send Invoice Email", "Send Approval Email"],
    "ygwBtSysINRWHJxB": ["Send Receipt Email"],
}

LEAD_SCRAPER_ID = "uq4hnH0YHfhYOOzO"


# ── SUB-WORKFLOW BUILDER ────────────────────────────────────────────────────
def build_suppression_subworkflow():
    """Build the Email Suppression Check sub-workflow."""
    return {
        "name": "Email Suppression Check",
        "nodes": [
            {
                "parameters": {
                    "inputSource": "passthrough"
                },
                "id": str(uuid.uuid4()),
                "name": "Execute Workflow Trigger",
                "type": "n8n-nodes-base.executeWorkflowTrigger",
                "position": [200, 300],
                "typeVersion": 1.1
            },
            {
                "parameters": {
                    "operation": "search",
                    "base": {
                        "__rl": True,
                        "mode": "list",
                        "value": AIRTABLE_BASE,
                        "cachedResultName": "Lead Scraper - Johannesburg CRM"
                    },
                    "table": {
                        "__rl": True,
                        "mode": "list",
                        "value": SUPPRESSION_TABLE,
                        "cachedResultName": "Email Suppression"
                    },
                    "filterByFormula": "=LOWER({Email}) = LOWER('{{ $json.email }}')",
                    "options": {
                        "fields": ["Email", "Status"]
                    }
                },
                "id": str(uuid.uuid4()),
                "name": "Search Suppression List",
                "type": "n8n-nodes-base.airtable",
                "position": [440, 300],
                "typeVersion": 2.1,
                "alwaysOutputData": True,
                "credentials": {
                    "airtableTokenApi": {
                        "id": CRED_AIRTABLE,
                        "name": "Lead Scraper Airtable"
                    }
                },
                "onError": "continueRegularOutput"
            },
            {
                "parameters": {
                    "jsCode": (
                        "const items = $input.all();\n"
                        "const email = $('Execute Workflow Trigger').first().json.email || '';\n"
                        "// Check if any records came back from suppression table\n"
                        "const hasRecords = items.length > 0 && items[0].json.id;\n"
                        "if (hasRecords) {\n"
                        "  const status = items[0].json.fields?.Status || items[0].json.Status || 'Suppressed';\n"
                        "  return [{ json: { email, suppressed: true, reason: status } }];\n"
                        "}\n"
                        "return [{ json: { email, suppressed: false, reason: '' } }];"
                    )
                },
                "id": str(uuid.uuid4()),
                "name": "Check Result",
                "type": "n8n-nodes-base.code",
                "position": [680, 300],
                "typeVersion": 2,
                "alwaysOutputData": True
            }
        ],
        "connections": {
            "Execute Workflow Trigger": {
                "main": [[{"node": "Search Suppression List", "type": "main", "index": 0}]]
            },
            "Search Suppression List": {
                "main": [[{"node": "Check Result", "type": "main", "index": 0}]]
            }
        },
        "settings": {"executionOrder": "v1"}
    }


# ── PATCH WORKFLOW WITH SUPPRESSION CHECK ───────────────────────────────────
def patch_workflow_with_suppression(wf, send_node_names, subworkflow_id):
    """Insert suppression check + gate before each Gmail send node."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}
    connections = wf["connections"]

    for send_name in send_node_names:
        if send_name not in node_map:
            print(f"    !! Node '{send_name}' not found, skipping")
            continue

        send_node = node_map[send_name]
        send_x, send_y = send_node["position"]

        check_name = f"Check Suppression ({send_name})"
        gate_name = f"Not Suppressed? ({send_name})"

        # Skip if already patched
        if check_name in node_map:
            print(f"    -> '{send_name}' already patched, skipping")
            continue

        # ── Create "Check Suppression" node (Execute Sub-Workflow) ──
        check_node = {
            "parameters": {
                "source": "database",
                "workflowId": {
                    "__rl": True,
                    "mode": "list",
                    "value": subworkflow_id,
                    "cachedResultName": "Email Suppression Check"
                }
            },
            "id": str(uuid.uuid4()),
            "name": check_name,
            "type": "n8n-nodes-base.executeWorkflow",
            "position": [send_x, send_y],
            "typeVersion": 1.2,
            "alwaysOutputData": True,
            "onError": "continueRegularOutput"
        }

        # ── Create "Not Suppressed?" gate node ──
        gate_node = {
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
                            "operator": {
                                "type": "boolean",
                                "operation": "false"
                            },
                            "leftValue": "={{ $json.suppressed }}",
                            "rightValue": ""
                        }
                    ]
                },
                "options": {}
            },
            "id": str(uuid.uuid4()),
            "name": gate_name,
            "type": "n8n-nodes-base.if",
            "position": [send_x + 220, send_y],
            "typeVersion": 2.2
        }

        # Shift the send node right by 460px
        send_node["position"] = [send_x + 460, send_y]

        # Add nodes
        nodes.append(check_node)
        nodes.append(gate_node)
        node_map[check_name] = check_node
        node_map[gate_name] = gate_node

        # ── Rewire connections ──
        # Find what connects TO the send node and redirect to check node
        for src_name, src_conns in connections.items():
            if "main" not in src_conns:
                continue
            for output_idx, output_list in enumerate(src_conns["main"]):
                for conn in output_list:
                    if conn["node"] == send_name:
                        conn["node"] = check_name
                        print(f"    -> {src_name} -> {check_name}")

        # Check Suppression -> Not Suppressed?
        connections[check_name] = {
            "main": [[{"node": gate_name, "type": "main", "index": 0}]]
        }

        # Not Suppressed? true -> Send, false -> dropped
        connections[gate_name] = {
            "main": [
                [{"node": send_name, "type": "main", "index": 0}],
                []  # suppressed = dropped
            ]
        }

        print(f"    -> {check_name} -> {gate_name} -> {send_name}")

    return wf


# ── PATCH LEAD SCRAPER TO WRITE TO SUPPRESSION TABLE ───────────────────────
def patch_lead_scraper_suppression_write(wf):
    """Add an Airtable create node after Flag Unsubscribed Leads to also
    write to the global Email Suppression table."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}
    connections = wf["connections"]

    # Skip if already patched
    if "Write to Suppression List" in node_map:
        print("    -> Already patched, skipping")
        return wf

    flag_node = node_map.get("Flag Unsubscribed Leads")
    if not flag_node:
        print("    !! Flag Unsubscribed Leads not found")
        return wf

    flag_x, flag_y = flag_node["position"]

    # Create the new node
    write_node = {
        "parameters": {
            "operation": "upsert",
            "base": {
                "__rl": True,
                "mode": "list",
                "value": AIRTABLE_BASE,
                "cachedResultName": "Lead Scraper - Johannesburg CRM"
            },
            "table": {
                "__rl": True,
                "mode": "list",
                "value": SUPPRESSION_TABLE,
                "cachedResultName": "Email Suppression"
            },
            "columns": {
                "value": {
                    "Email": "={{ $json.unsubEmail }}",
                    "Status": "={{ $json.optOutStatus || 'Unsubscribed' }}",
                    "Source Workflow": "Lead Scraper",
                    "Date Added": "={{ new Date().toISOString().split('T')[0] }}"
                },
                "schema": [
                    {"id": "Email", "type": "string", "display": True, "displayName": "Email", "defaultMatch": False, "canBeUsedToMatch": True},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Source Workflow", "type": "string", "display": True, "displayName": "Source Workflow"},
                    {"id": "Date Added", "type": "string", "display": True, "displayName": "Date Added"}
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Email"]
            },
            "options": {}
        },
        "id": str(uuid.uuid4()),
        "name": "Write to Suppression List",
        "type": "n8n-nodes-base.airtable",
        "position": [flag_x + 240, flag_y + 80],
        "typeVersion": 2.1,
        "credentials": {
            "airtableTokenApi": {
                "id": CRED_AIRTABLE,
                "name": "Lead Scraper Airtable"
            }
        },
        "onError": "continueRegularOutput"
    }

    nodes.append(write_node)
    node_map["Write to Suppression List"] = write_node

    # Wire: Flag Unsubscribed Leads -> also connects to Write to Suppression List
    if "Flag Unsubscribed Leads" in connections:
        existing = connections["Flag Unsubscribed Leads"]["main"][0]
        existing.append({"node": "Write to Suppression List", "type": "main", "index": 0})
    else:
        connections["Flag Unsubscribed Leads"] = {
            "main": [[{"node": "Write to Suppression List", "type": "main", "index": 0}]]
        }

    # Also write bounced emails to suppression
    if "Flag Bounced Leads" in node_map and "Write Bounced to Suppression" not in node_map:
        bounce_node = node_map["Flag Bounced Leads"]
        bx, by = bounce_node["position"]

        bounce_write = {
            "parameters": {
                "operation": "upsert",
                "base": {
                    "__rl": True,
                    "mode": "list",
                    "value": AIRTABLE_BASE,
                    "cachedResultName": "Lead Scraper - Johannesburg CRM"
                },
                "table": {
                    "__rl": True,
                    "mode": "list",
                    "value": SUPPRESSION_TABLE,
                    "cachedResultName": "Email Suppression"
                },
                "columns": {
                    "value": {
                        "Email": "={{ $json.bouncedEmail }}",
                        "Status": "Bounced",
                        "Source Workflow": "Lead Scraper",
                        "Date Added": "={{ new Date().toISOString().split('T')[0] }}"
                    },
                    "schema": [
                        {"id": "Email", "type": "string", "display": True, "displayName": "Email", "defaultMatch": False, "canBeUsedToMatch": True},
                        {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                        {"id": "Source Workflow", "type": "string", "display": True, "displayName": "Source Workflow"},
                        {"id": "Date Added", "type": "string", "display": True, "displayName": "Date Added"}
                    ],
                    "mappingMode": "defineBelow",
                    "matchingColumns": ["Email"]
                },
                "options": {}
            },
            "id": str(uuid.uuid4()),
            "name": "Write Bounced to Suppression",
            "type": "n8n-nodes-base.airtable",
            "position": [bx + 240, by + 80],
            "typeVersion": 2.1,
            "credentials": {
                "airtableTokenApi": {
                    "id": CRED_AIRTABLE,
                    "name": "Lead Scraper Airtable"
                }
            },
            "onError": "continueRegularOutput"
        }

        nodes.append(bounce_write)
        node_map["Write Bounced to Suppression"] = bounce_write

        if "Flag Bounced Leads" in connections:
            existing = connections["Flag Bounced Leads"]["main"][0]
            existing.append({"node": "Write Bounced to Suppression", "type": "main", "index": 0})

    print("    -> Write to Suppression List (after opt-out detection)")
    print("    -> Write Bounced to Suppression (after bounce detection)")

    return wf


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = "https://ianimmelman89.app.n8n.cloud"
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    print("=" * 60)
    print("GLOBAL EMAIL SUPPRESSION SYSTEM")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:

        # ── STEP 1: Create sub-workflow ──
        print("\n[1/4] Creating Email Suppression Check sub-workflow...")
        subwf = build_suppression_subworkflow()
        resp = client.post(
            f"{base_url}/api/v1/workflows",
            headers=headers,
            json=subwf
        )
        resp.raise_for_status()
        sub_result = resp.json()
        subworkflow_id = sub_result["id"]
        print(f"  Created: {sub_result['name']} (ID: {subworkflow_id})")

        # Activate it
        resp = client.post(
            f"{base_url}/api/v1/workflows/{subworkflow_id}/activate",
            headers=headers
        )
        resp.raise_for_status()
        print(f"  Activated: {resp.json().get('active')}")

        # ── STEP 2: Patch Lead Scraper ──
        print(f"\n[2/4] Patching Lead Scraper to write opt-outs to suppression table...")
        resp = client.get(f"{base_url}/api/v1/workflows/{LEAD_SCRAPER_ID}", headers=headers)
        resp.raise_for_status()
        ls_wf = resp.json()
        print(f"  Got: {ls_wf['name']} ({len(ls_wf['nodes'])} nodes)")

        ls_wf = patch_lead_scraper_suppression_write(ls_wf)

        update_payload = {
            "name": ls_wf["name"],
            "nodes": ls_wf["nodes"],
            "connections": ls_wf["connections"],
            "settings": ls_wf.get("settings", {"executionOrder": "v1"})
        }
        resp = client.put(
            f"{base_url}/api/v1/workflows/{LEAD_SCRAPER_ID}",
            headers=headers,
            json=update_payload
        )
        resp.raise_for_status()
        print(f"  Deployed: {resp.json()['name']} ({len(resp.json()['nodes'])} nodes)")

        # Re-activate
        resp = client.post(f"{base_url}/api/v1/workflows/{LEAD_SCRAPER_ID}/activate", headers=headers)
        resp.raise_for_status()
        print(f"  Active: {resp.json().get('active')}")

        # ── STEP 3: Patch accounting workflows ──
        print(f"\n[3/4] Patching {len(WORKFLOWS_TO_PATCH)} accounting workflows...")

        for wf_id, send_nodes in WORKFLOWS_TO_PATCH.items():
            resp = client.get(f"{base_url}/api/v1/workflows/{wf_id}", headers=headers)
            resp.raise_for_status()
            wf = resp.json()
            print(f"\n  Patching: {wf['name']} ({len(wf['nodes'])} nodes)")
            print(f"  Protecting nodes: {send_nodes}")

            wf = patch_workflow_with_suppression(wf, send_nodes, subworkflow_id)

            update_payload = {
                "name": wf["name"],
                "nodes": wf["nodes"],
                "connections": wf["connections"],
                "settings": wf.get("settings", {"executionOrder": "v1"})
            }
            resp = client.put(
                f"{base_url}/api/v1/workflows/{wf_id}",
                headers=headers,
                json=update_payload
            )
            resp.raise_for_status()
            result = resp.json()
            print(f"  Deployed: {result['name']} ({len(result['nodes'])} nodes)")

            # Re-activate if was active
            resp = client.post(f"{base_url}/api/v1/workflows/{wf_id}/activate", headers=headers)
            resp.raise_for_status()
            print(f"  Active: {resp.json().get('active')}")

        # ── STEP 4: Save config ──
        print(f"\n[4/4] Saving suppression system config...")
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)

        suppression_config = {
            "subworkflow_id": subworkflow_id,
            "airtable_base": AIRTABLE_BASE,
            "suppression_table": SUPPRESSION_TABLE,
            "patched_workflows": {
                LEAD_SCRAPER_ID: "Lead Scraper (writes opt-outs + bounces)",
                **{wf_id: f"Protected nodes: {nodes}" for wf_id, nodes in WORKFLOWS_TO_PATCH.items()}
            }
        }
        config_path = output_dir / "email_suppression_config.json"
        with open(config_path, "w") as f:
            json.dump(suppression_config, f, indent=2)
        print(f"  Saved config to {config_path}")

    print("\n" + "=" * 60)
    print("GLOBAL EMAIL SUPPRESSION DEPLOYED")
    print("=" * 60)
    print(f"\nSub-workflow: Email Suppression Check (ID: {subworkflow_id})")
    print(f"Suppression table: {SUPPRESSION_TABLE} in base {AIRTABLE_BASE}")
    print(f"\nPatched workflows:")
    print(f"  Lead Scraper     -> writes opt-outs + bounces to suppression table")
    print(f"  Accounting WF-01 -> Send Invoice Email, Send Approval Email")
    print(f"  Accounting WF-02 -> Send Reminder Email")
    print(f"  Accounting WF-03 -> Send Receipt Email")
    print(f"\nHow it works:")
    print(f"  1. When anyone unsubscribes/bounces via Lead Scraper, their email")
    print(f"     is added to the global Email Suppression table")
    print(f"  2. Before ANY email is sent by any patched workflow, it calls")
    print(f"     the sub-workflow to check the suppression table")
    print(f"  3. If the email is found -> email is BLOCKED (not sent)")
    print(f"  4. If the email is not found -> email proceeds normally")
    print(f"\nTo protect future workflows:")
    print(f"  Use subworkflow_id='{subworkflow_id}' with the")
    print(f"  patch_workflow_with_suppression() function in deploy scripts")


if __name__ == "__main__":
    main()
