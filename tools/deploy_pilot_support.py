"""
Pilot Support Workflows - Builder & Deployer

Builds pilot-specific support workflows:
    PILOT-01: Weekly Feedback Survey (Friday 14:00 SAST)
    PILOT-02: WhatsApp Connection Sync (Supabase -> Airtable, every 15min)

Usage:
    python tools/deploy_pilot_support.py build
    python tools/deploy_pilot_support.py deploy
    python tools/deploy_pilot_support.py activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from credentials import CREDENTIALS

# -- Credentials --
CRED_GMAIL = CREDENTIALS["gmail_oauth2"]
CRED_AIRTABLE = CREDENTIALS["airtable_whatsapp"]

# -- Airtable IDs --
WHATSAPP_BASE_ID = "appzcZpiIZ6QPtJXT"
TABLE_AGENTS = "tblHCkr9weKQAHZoB"

# -- Config --
ALERT_EMAIL = "ian@anyvisionmedia.com"
FEEDBACK_FORM_URL = os.getenv("PILOT_FEEDBACK_FORM_URL", "https://forms.gle/REPLACE_WITH_REAL_FORM")
SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""))
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def uid():
    return str(uuid.uuid4())


# ==================================================================
# PILOT-01: WEEKLY FEEDBACK SURVEY
# ==================================================================

def build_pilot01_nodes():
    """Build nodes for Weekly Feedback Survey workflow."""
    nodes = []

    # Schedule: Friday 14:00 SAST (12:00 UTC)
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 12 * * 5"}]
            }
        },
        "id": uid(),
        "name": "Friday 14:00 SAST",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # Read active pilot agents from Airtable
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": WHATSAPP_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_AGENTS, "mode": "id"},
            "filterByFormula": "=AND({is_active}, {bot_type}='real_estate')",
        },
        "id": uid(),
        "name": "Get Active Agents",
        "type": "n8n-nodes-base.airtable",
        "position": [440, 400],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # Split into items (one per agent)
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Split Agents",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [680, 400],
        "typeVersion": 3,
    })

    # Send feedback email to each agent
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.fields.notification_email || $json.fields.email }}",
            "subject": "=WhatsApp AI Pilot - Weekly Feedback (Week {{ Math.ceil(($now.diff($now.startOf('month'), 'days').days) / 7) }})",
            "emailType": "html",
            "message": (
                "=<h2>Hi {{ $json.fields.agent_name }},</h2>"
                "<p>Thanks for being part of the WhatsApp AI pilot! We'd love your feedback "
                "to help us improve the experience.</p>"
                "<p>This quick survey takes less than 2 minutes:</p>"
                "<table cellpadding='0' cellspacing='0' style='margin:20px 0;'>"
                "<tr><td style='background-color:#FF6D5A;border-radius:6px;padding:12px 28px;'>"
                f"<a href='{FEEDBACK_FORM_URL}' style='color:#fff;text-decoration:none;font-size:15px;font-weight:600;'>"
                "Take the Survey</a></td></tr></table>"
                "<p style='color:#888;font-size:13px;'>Your feedback directly shapes how we build this product. "
                "Thank you!</p>"
                "<p>Best,<br>Ian Immelman<br>AnyVision Media</p>"
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Send Feedback Email",
        "type": "n8n-nodes-base.gmail",
        "position": [920, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "continueOnFail": True,
    })

    # Log send
    nodes.append({
        "parameters": {
            "jsCode": (
                "const agent = $('Split Agents').first().json.fields || {};\n"
                "return {\n"
                "  json: {\n"
                "    status: 'feedback_sent',\n"
                "    agent_name: agent.agent_name || 'unknown',\n"
                "    email: agent.notification_email || agent.email || 'unknown',\n"
                "    sent_at: new Date().toISOString(),\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Log Send",
        "type": "n8n-nodes-base.code",
        "position": [1160, 400],
        "typeVersion": 2,
    })

    # Summary email to Ian
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=Pilot Feedback Survey Sent - {{ $('Get Active Agents').all().length }} agents",
            "emailType": "text",
            "message": (
                "=Weekly feedback survey sent to all active pilot agents.\n\n"
                "Agents contacted: {{ $('Get Active Agents').all().length }}\n"
                f"Form URL: {FEEDBACK_FORM_URL}\n\n"
                "Check Google Sheets for responses by Monday."
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Notify Ian",
        "type": "n8n-nodes-base.gmail",
        "position": [1160, 600],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "continueOnFail": True,
    })

    # Sticky note
    nodes.append({
        "parameters": {
            "content": "## PILOT-01: Weekly Feedback Survey\n\n**Schedule:** Friday 14:00 SAST\n**Purpose:** Send feedback form to all active pilot agents. Summary email to Ian.",
            "height": 160, "width": 420,
        },
        "id": "pilot01-note",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note",
    })

    return nodes


def build_pilot01_connections():
    return {
        "Friday 14:00 SAST": {
            "main": [[{"node": "Get Active Agents", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "Get Active Agents", "type": "main", "index": 0}]],
        },
        "Get Active Agents": {
            "main": [[{"node": "Split Agents", "type": "main", "index": 0}]],
        },
        "Split Agents": {
            "main": [
                [{"node": "Send Feedback Email", "type": "main", "index": 0}],
                [{"node": "Notify Ian", "type": "main", "index": 0}],
            ],
        },
        "Send Feedback Email": {
            "main": [[{"node": "Log Send", "type": "main", "index": 0}]],
        },
        "Log Send": {
            "main": [[{"node": "Split Agents", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# PILOT-02: WHATSAPP CONNECTION SYNC (Supabase -> Airtable)
# ==================================================================

SYNC_CODE = """// Sync whatsapp_connections from Supabase to Airtable Agents table
// Input: Supabase whatsapp_connections rows with status='connected'
const connections = $input.all();
const results = [];

for (const conn of connections) {
  const data = conn.json;
  if (data.status !== 'connected' || !data.phone_number_id) continue;

  results.push({
    json: {
      phone_number_id: data.phone_number_id,
      display_phone: data.display_phone_number || '',
      business_name: data.business_name || '',
      client_id: data.client_id,
      waba_id: data.waba_id || '',
    }
  });
}

if (results.length === 0) {
  return [{ json: { skip: true, message: 'No new connections to sync' } }];
}

return results;"""


def build_pilot02_nodes():
    """Build nodes for WhatsApp Connection Sync workflow."""
    nodes = []

    # Schedule: Every 15 minutes
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "*/15 * * * *"}]
            }
        },
        "id": uid(),
        "name": "Every 15min",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # Fetch connected WhatsApp connections from Supabase
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": f"{SUPABASE_URL}/rest/v1/whatsapp_connections?status=eq.connected&select=*",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": f"{SUPABASE_SERVICE_KEY}"},
                ]
            },
            "options": {"timeout": 10000},
        },
        "id": uid(),
        "name": "Fetch Connections",
        "type": "n8n-nodes-base.httpRequest",
        "position": [440, 400],
        "typeVersion": 4.2,
        "continueOnFail": True,
    })

    # Parse and filter
    nodes.append({
        "parameters": {
            "jsCode": SYNC_CODE,
        },
        "id": uid(),
        "name": "Parse Connections",
        "type": "n8n-nodes-base.code",
        "position": [680, 400],
        "typeVersion": 2,
    })

    # Check if skip (loose validation: undefined != true, so real items pass to false branch)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "typeValidation": "loose"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.skip }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "equals"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Connections?",
        "type": "n8n-nodes-base.if",
        "position": [920, 400],
        "typeVersion": 2.2,
    })

    # Search Airtable for matching agent by whatsapp_number
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": WHATSAPP_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_AGENTS, "mode": "id"},
            "filterByFormula": "=OR({whatsapp_number}='{{ $json.display_phone }}', {whatsapp_number}='{{ $json.phone_number_id }}')",
        },
        "id": uid(),
        "name": "Find Agent",
        "type": "n8n-nodes-base.airtable",
        "position": [1160, 300],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # Update agent with phone_number_id (match on record ID from Find Agent)
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": WHATSAPP_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_AGENTS, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "id": "={{ $('Find Agent').first().json.id }}",
                    "whatsapp_phone_number_id": "={{ $('Parse Connections').first().json.phone_number_id }}",
                    "waba_id": "={{ $('Parse Connections').first().json.waba_id }}",
                },
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Agent",
        "type": "n8n-nodes-base.airtable",
        "position": [1400, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "continueOnFail": True,
    })

    # Sticky
    nodes.append({
        "parameters": {
            "content": "## PILOT-02: WhatsApp Connection Sync\n\n**Schedule:** Every 15 min\n**Purpose:** Sync Supabase whatsapp_connections (from portal Embedded Signup) to Airtable Agents table so the Multi-Agent workflow picks up new agents.",
            "height": 180, "width": 440,
        },
        "id": "pilot02-note",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note",
    })

    return nodes


def build_pilot02_connections():
    return {
        "Every 15min": {
            "main": [[{"node": "Fetch Connections", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "Fetch Connections", "type": "main", "index": 0}]],
        },
        "Fetch Connections": {
            "main": [[{"node": "Parse Connections", "type": "main", "index": 0}]],
        },
        "Parse Connections": {
            "main": [[{"node": "Has Connections?", "type": "main", "index": 0}]],
        },
        # Has Connections? true (skip=true) -> stop, false (has data) -> Find Agent
        "Has Connections?": {
            "main": [
                [],
                [{"node": "Find Agent", "type": "main", "index": 0}],
            ],
        },
        "Find Agent": {
            "main": [[{"node": "Update Agent", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# WORKFLOW DEFINITIONS & BUILD INFRASTRUCTURE
# ==================================================================

WORKFLOW_DEFS = {
    "pilot01": {
        "name": "Pilot Support - Weekly Feedback Survey (PILOT-01)",
        "build_nodes": build_pilot01_nodes,
        "build_connections": build_pilot01_connections,
        "filename": "pilot01_weekly_feedback.json",
    },
    "pilot02": {
        "name": "Pilot Support - WhatsApp Connection Sync (PILOT-02)",
        "build_nodes": build_pilot02_nodes,
        "build_connections": build_pilot02_connections,
        "filename": "pilot02_whatsapp_sync.json",
    },
}


def build_workflow(wf_id):
    wf_def = WORKFLOW_DEFS[wf_id]
    return {
        "name": wf_def["name"],
        "nodes": wf_def["build_nodes"](),
        "connections": wf_def["build_connections"](),
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    output_dir = Path(__file__).parent.parent / "workflows" / "pilot-support"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / WORKFLOW_DEFS[wf_id]["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    return output_path


def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    print("=" * 60)
    print("PILOT SUPPORT - WORKFLOW BUILDER")
    print("=" * 60)

    valid_wfs = list(WORKFLOW_DEFS.keys())
    workflow_ids = valid_wfs if target == "all" else [target] if target in valid_wfs else None

    if not workflow_ids:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    workflows = {}
    for wf_id in workflow_ids:
        print(f"\nBuilding {wf_id}...")
        workflow = build_workflow(wf_id)
        output_path = save_workflow(wf_id, workflow)
        workflows[wf_id] = workflow
        func_nodes = [n for n in workflow["nodes"] if n["type"] != "n8n-nodes-base.stickyNote"]
        print(f"  Name: {workflow['name']}")
        print(f"  Nodes: {len(func_nodes)} functional")
        print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    if action in ("deploy", "activate"):
        from n8n_client import N8nClient

        api_key = os.getenv("N8N_API_KEY")
        base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

        if not api_key:
            print("ERROR: N8N_API_KEY not set in .env")
            sys.exit(1)

        print(f"\nConnecting to {base_url}...")
        client = N8nClient(base_url=base_url, api_key=api_key)

        for wf_id, workflow in workflows.items():
            print(f"\nDeploying {wf_id}...")
            result = client.create_workflow(workflow)
            wf_n8n_id = result.get("id", "unknown")
            print(f"  Deployed: {wf_n8n_id}")

            if action == "activate":
                client.activate_workflow(wf_n8n_id)
                print(f"  Activated: {wf_n8n_id}")

    print("\nDone!")


if __name__ == "__main__":
    main()
