"""
Deploy onboarding email sequence workflow to n8n.

This workflow sends 7 behavioral emails over 14 days to guide new clients
from signup to activation. Built as an n8n workflow (dogfooding the platform).

Trigger: Schedule (runs every hour) + Webhook (for immediate welcome email)
Dependencies: Gmail credential, Supabase HTTP access

Usage:
    python tools/deploy_onboarding_emails.py build    # Save JSON locally
    python tools/deploy_onboarding_emails.py deploy   # Push to n8n
    python tools/deploy_onboarding_emails.py activate  # Enable triggers
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add tools to path for n8n_client import
sys.path.insert(0, str(Path(__file__).parent))
from n8n_client import N8nClient

# Constants
WORKFLOW_NAME = "Onboarding Email Sequence"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "onboarding"
OUTPUT_FILE = OUTPUT_DIR / "onboarding_email_sequence.json"

# Credentials (n8n internal IDs)
CRED_GMAIL = "HG94m0noRMluzCEi"  # Gmail OAuth credential
PORTAL_URL = os.getenv("NEXT_PUBLIC_APP_URL", "https://portal.anyvisionmedia.com")
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SENDER_NAME = "Ian from AnyVision"
SENDER_EMAIL = "ian@anyvisionmedia.com"


def build_nodes() -> list[dict]:
    """Build all n8n nodes for the email sequence workflow."""
    nodes: list[dict] = []

    # --- Trigger: Schedule (every hour) ---
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "hours", "hoursInterval": 1}]
            }
        },
        "name": "Every Hour",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [0, 0],
    })

    # --- Webhook trigger (for immediate welcome email) ---
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "onboarding-email-trigger",
            "responseMode": "responseNode",
        },
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [0, 300],
    })

    # --- Respond to webhook ---
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": '={"success": true}',
            "options": {},
        },
        "name": "Respond OK",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [400, 300],
    })

    # --- Query Supabase for pending emails (scheduled path) ---
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/rpc/get_pending_onboarding_emails",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": SUPABASE_SERVICE_KEY},
                    {"name": "Authorization", "value": f"Bearer {SUPABASE_SERVICE_KEY}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "options": {"redirect": {"redirect": {"followRedirects": True}}},
        },
        "name": "Query Pending Emails",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [300, 0],
    })

    # --- Code node: Determine which emails to send ---
    nodes.append({
        "parameters": {
            "jsCode": """
// This node processes both scheduled and webhook-triggered emails.
// Scheduled: receives list of clients from Supabase RPC
// Webhook: receives single client_id + email_key

const items = $input.all();
const results = [];

for (const item of items) {
  const data = item.json;

  // Webhook path: immediate email
  if (data.body && data.body.email_key) {
    results.push({
      json: {
        client_id: data.body.client_id,
        email: data.body.email,
        first_name: data.body.first_name,
        email_key: data.body.email_key,
        company_name: data.body.company_name || '',
        extra: data.body.extra || {},
      }
    });
    continue;
  }

  // Scheduled path: process each pending email
  if (Array.isArray(data)) {
    for (const row of data) {
      results.push({ json: row });
    }
  } else if (data.client_id) {
    results.push({ json: data });
  }
}

return results.length > 0 ? results : [{ json: { _skip: true } }];
"""
        },
        "name": "Process Email Queue",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [600, 150],
    })

    # --- IF: Skip if no emails ---
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json._skip }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "notTrue"},
                    }
                ],
                "combinator": "and",
            }
        },
        "name": "Has Emails?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [850, 150],
    })

    # --- Code node: Build email HTML ---
    nodes.append({
        "parameters": {
            "jsCode": f"""
const item = $input.first().json;
const emailKey = item.email_key;
const firstName = item.first_name || 'there';
const companyName = item.company_name || '';
const portalUrl = '{PORTAL_URL}';
const extra = item.extra || {{}};

// Email templates (subject + body)
const templates = {{
  'welcome': {{
    subject: `Welcome to AnyVision, ${{firstName}}`,
    body: `<h2 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 16px">Welcome to AnyVision, ${{firstName}}!</h2>
<p style="font-size:14px;color:#8B95A9;line-height:1.7">You've taken the first step toward automating your business with AI. Your <span style="background:rgba(108,99,255,0.15);color:#6C63FF;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600">30-day free trial</span> is now active.</p>
<p style="font-size:14px;color:#8B95A9;line-height:1.7"><strong style="color:#B0B8C8">Complete your setup in 3 minutes:</strong></p>
<div style="text-align:center;margin:24px 0"><a href="${{portalUrl}}/portal/onboarding" style="display:inline-block;padding:14px 32px;border-radius:12px;text-decoration:none;font-size:15px;font-weight:600;color:#fff;background:linear-gradient(135deg,#FF6D5A,#FF8A6B)">Complete Your Setup</a></div>
<p style="font-size:13px;color:#8B95A9">Questions? Just reply to this email. — Ian</p>`
  }},
  'day1_checklist': {{
    subject: '3 steps to get your business on autopilot',
    body: `<h2 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 16px">Quick setup, ${{firstName}} — 3 steps left</h2>
<p style="font-size:14px;color:#8B95A9;line-height:1.7">You signed up yesterday but haven't finished setup yet. Most clients complete it in <strong style="color:#B0B8C8">under 3 minutes</strong>.</p>
<div style="text-align:center;margin:24px 0"><a href="${{portalUrl}}/portal/onboarding" style="display:inline-block;padding:14px 32px;border-radius:12px;text-decoration:none;font-size:15px;font-weight:600;color:#fff;background:linear-gradient(135deg,#FF6D5A,#FF8A6B)">Resume Setup</a></div>`
  }},
  'first_connection': {{
    subject: "You're connected! Here's what happens next",
    body: `<h2 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 16px">You're connected, ${{firstName}}!</h2>
<p style="font-size:14px;color:#8B95A9;line-height:1.7">Your <strong style="color:#B0B8C8">${{extra.connected_tool || 'integration'}}</strong> is now linked. Data is syncing and automations are activating.</p>
<div style="text-align:center;margin:24px 0"><a href="${{portalUrl}}/portal" style="display:inline-block;padding:14px 32px;border-radius:12px;text-decoration:none;font-size:15px;font-weight:600;color:#fff;background:linear-gradient(135deg,#FF6D5A,#FF8A6B)">View Your Dashboard</a></div>`
  }},
  'day3_nudge': {{
    subject: 'Connect your tools in 60 seconds',
    body: `<h2 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 16px">One step away, ${{firstName}}</h2>
<p style="font-size:14px;color:#8B95A9;line-height:1.7">You haven't connected any tools yet. Clients who connect in their first week are <strong style="color:#fff">4x more likely to see real results</strong>.</p>
<div style="text-align:center;margin:24px 0"><a href="${{portalUrl}}/portal/connections" style="display:inline-block;padding:14px 32px;border-radius:12px;text-decoration:none;font-size:15px;font-weight:600;color:#fff;background:linear-gradient(135deg,#FF6D5A,#FF8A6B)">Connect a Tool Now</a></div>`
  }},
  'first_win': {{
    subject: 'Your first automation just ran!',
    body: `<h2 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 16px">It's working, ${{firstName}}!</h2>
<p style="font-size:14px;color:#8B95A9;line-height:1.7">Your automation just ran successfully. This task would have taken you 15-30 minutes manually. Over a month, that's 8+ hours saved.</p>
<div style="text-align:center;margin:24px 0"><a href="${{portalUrl}}/portal/workflows" style="display:inline-block;padding:14px 32px;border-radius:12px;text-decoration:none;font-size:15px;font-weight:600;color:#fff;background:linear-gradient(135deg,#FF6D5A,#FF8A6B)">View Your Workflows</a></div>`
  }},
  'day7_value': {{
    subject: `Week 1: ${{extra.leads || 0}} leads, ${{extra.hours_saved || 0}} hours saved`,
    body: `<h2 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 16px">Your first week, ${{firstName}}</h2>
<p style="font-size:14px;color:#8B95A9;line-height:1.7">Here's what your automations achieved in 7 days: <strong style="color:#00D4AA">${{extra.leads || 0}} leads</strong>, <strong style="color:#6C63FF">${{extra.hours_saved || 0}} hours saved</strong>, <strong style="color:#FF6D5A">${{extra.workflows_run || 0}} workflows run</strong>.</p>
<div style="text-align:center;margin:24px 0"><a href="${{portalUrl}}/portal" style="display:inline-block;padding:14px 32px;border-radius:12px;text-decoration:none;font-size:15px;font-weight:600;color:#fff;background:linear-gradient(135deg,#FF6D5A,#FF8A6B)">See Full Dashboard</a></div>
<p style="font-size:13px;color:#4B5563;text-align:center">23 days left in your trial. <a href="${{portalUrl}}/portal/billing" style="color:#6C63FF;text-decoration:none">View plans →</a></p>`
  }},
  'trial_ending': {{
    subject: 'Your trial ends in 5 days',
    body: `<h2 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 16px">${{firstName}}, your trial ends in 5 days</h2>
<p style="font-size:14px;color:#8B95A9;line-height:1.7">When your trial ends: all workflows pause, lead capture stops, campaign monitoring stops, and reporting freezes.</p>
<p style="font-size:14px;color:#8B95A9;line-height:1.7"><strong style="color:#fff">Keep everything running from R1,999/month.</strong></p>
<div style="text-align:center;margin:24px 0"><a href="${{portalUrl}}/portal/billing" style="display:inline-block;padding:14px 32px;border-radius:12px;text-decoration:none;font-size:15px;font-weight:600;color:#fff;background:linear-gradient(135deg,#FF6D5A,#FF8A6B)">Choose Your Plan</a></div>
<p style="font-size:13px;color:#4B5563;text-align:center">Not ready? Your data is preserved for 30 days after trial ends.</p>`
  }}
}};

const template = templates[emailKey];
if (!template) {{
  return [{{ json: {{ _skip: true, reason: 'unknown email_key: ' + emailKey }} }}];
}}

// Wrap in base layout
const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>${{template.subject}}</title></head>
<body style="margin:0;padding:0;background:#0A0F1C;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<div style="max-width:560px;margin:0 auto;padding:40px 20px">
<div style="text-align:center;margin-bottom:32px"><span style="font-size:18px;font-weight:700;color:#fff;letter-spacing:1px">AnyVision<span style="color:#FF6D5A">.</span></span></div>
<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:32px">${{template.body}}</div>
<div style="text-align:center;padding:24px 0 0"><p style="font-size:11px;color:#4B5563;line-height:1.6">AnyVision Media &middot; AI-Powered Business Automation<br><a href="https://www.anyvisionmedia.com" style="color:#6B7280;text-decoration:underline">anyvisionmedia.com</a></p><p style="font-size:11px;color:#4B5563"><a href="${{portalUrl}}/portal/settings" style="color:#6B7280;text-decoration:underline">Unsubscribe</a> &middot; <a href="https://www.anyvisionmedia.com/terms" style="color:#6B7280;text-decoration:underline">Privacy Policy</a></p></div>
</div></body></html>`;

return [{{
  json: {{
    ...item,
    subject: template.subject,
    html: html,
    to: item.email,
  }}
}}];
"""
        },
        "name": "Build Email HTML",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 150],
    })

    # --- Send email via Gmail ---
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.to }}",
            "subject": "={{ $json.subject }}",
            "message": "={{ $json.html }}",
            "options": {
                "senderName": SENDER_NAME,
            },
        },
        "name": "Send Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1350, 150],
        "credentials": {
            "gmailOAuth2": {"id": CRED_GMAIL, "name": "Gmail AnyVision"},
        },
    })

    # --- Log to Supabase ---
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/email_sequence_events",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "apikey", "value": SUPABASE_SERVICE_KEY},
                    {"name": "Authorization", "value": f"Bearer {SUPABASE_SERVICE_KEY}"},
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Prefer", "value": "return=minimal"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={{ JSON.stringify({ client_id: $json.client_id, email_key: $json.email_key, metadata: { subject: $json.subject } }) }}',
            "options": {},
        },
        "name": "Log Email Sent",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [1600, 150],
        "continueOnFail": True,
    })

    return nodes


def build_connections() -> dict:
    """Build connections between nodes."""
    return {
        "Every Hour": {"main": [
            [{"node": "Query Pending Emails", "type": "main", "index": 0}]
        ]},
        "Webhook Trigger": {"main": [
            [{"node": "Process Email Queue", "type": "main", "index": 0},
             {"node": "Respond OK", "type": "main", "index": 0}]
        ]},
        "Query Pending Emails": {"main": [
            [{"node": "Process Email Queue", "type": "main", "index": 0}]
        ]},
        "Process Email Queue": {"main": [
            [{"node": "Has Emails?", "type": "main", "index": 0}]
        ]},
        "Has Emails?": {"main": [
            [{"node": "Build Email HTML", "type": "main", "index": 0}],
            [],  # false branch (no emails)
        ]},
        "Build Email HTML": {"main": [
            [{"node": "Send Email", "type": "main", "index": 0}]
        ]},
        "Send Email": {"main": [
            [{"node": "Log Email Sent", "type": "main", "index": 0}]
        ]},
    }


def build_workflow() -> dict:
    """Build the complete workflow JSON."""
    return {
        "name": WORKFLOW_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "tags": [],
    }


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python deploy_onboarding_emails.py [build|deploy|activate]")
        sys.exit(1)

    command = sys.argv[1].lower()
    workflow = build_workflow()

    if command == "build":
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(workflow, indent=2))
        print(f"Built {WORKFLOW_NAME} -> {OUTPUT_FILE}")
        print(f"  Nodes: {len(workflow['nodes'])}")

    elif command == "deploy":
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(workflow, indent=2))

        base_url = os.getenv("N8N_BASE_URL", "")
        api_key = os.getenv("N8N_API_KEY", "")
        if not base_url or not api_key:
            print("ERROR: N8N_BASE_URL and N8N_API_KEY required in .env")
            sys.exit(1)

        client = N8nClient(base_url, api_key)
        result = client.create_workflow(workflow)
        wf_id = result.get("id", "unknown")
        print(f"Deployed {WORKFLOW_NAME} -> {wf_id}")

    elif command == "activate":
        base_url = os.getenv("N8N_BASE_URL", "")
        api_key = os.getenv("N8N_API_KEY", "")
        if not base_url or not api_key:
            print("ERROR: N8N_BASE_URL and N8N_API_KEY required in .env")
            sys.exit(1)

        client = N8nClient(base_url, api_key)
        workflows = client.list_workflows()
        for wf in workflows:
            if wf.get("name") == WORKFLOW_NAME:
                client.activate_workflow(wf["id"])
                print(f"Activated {WORKFLOW_NAME} (ID: {wf['id']})")
                return
        print(f"ERROR: Workflow '{WORKFLOW_NAME}' not found. Deploy first.")
        sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
