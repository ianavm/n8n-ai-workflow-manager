"""
AVM Lead Capture - Webhook Workflow Builder & Deployer

Builds and deploys two webhook-driven lead capture workflows:
    1. Website Contact Form  — /website-contact-form
    2. SEO Lead Capture      — /seo-social/lead-capture

Both write to Airtable Leads table and send Gmail notifications.

Usage:
    python tools/deploy_lead_capture.py build      # Build JSONs to workflows/lead-capture/
    python tools/deploy_lead_capture.py deploy      # Build + Deploy (inactive)
    python tools/deploy_lead_capture.py activate    # Build + Deploy + Activate
"""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# ── Credential Constants ────────────────────────────────────
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}

# ── Airtable IDs ────────────────────────────────────────────
LEADS_BASE_ID = "apptjjBx34z9340tK"
LEADS_TABLE_ID = "tblwOPTPY85Tcj7NJ"

# ── Config ──────────────────────────────────────────────────
ALERT_EMAIL = "ian@anyvisionmedia.com"

# ── Workflow Registry ───────────────────────────────────────
WORKFLOW_BUILDERS: Dict[str, Dict[str, str]] = {
    "website_contact": {
        "name": "AVM: Website Contact Form",
        "filename": "website_contact_form.json",
    },
    "seo_lead": {
        "name": "AVM: SEO Lead Capture",
        "filename": "seo_lead_capture.json",
    },
}


def uid() -> str:
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ======================================================================
# SHARED NODE BUILDERS
# ======================================================================

def build_webhook_node(
    name: str,
    path: str,
    position: List[int],
) -> Dict[str, Any]:
    """Build a Webhook trigger node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": position,
        "webhookId": uid(),
        "parameters": {
            "path": path,
            "httpMethod": "POST",
            "responseMode": "responseNode",
        },
    }


def build_code_node(
    name: str,
    js_code: str,
    position: List[int],
) -> Dict[str, Any]:
    """Build a Code node with JavaScript."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {
            "jsCode": js_code,
        },
    }


def build_airtable_create_node(
    name: str,
    position: List[int],
) -> Dict[str, Any]:
    """Build an Airtable CREATE node for the Leads table."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": position,
        "parameters": {
            "operation": "create",
            "application": LEADS_BASE_ID,
            "table": LEADS_TABLE_ID,
            "columns": {
                "mappingMode": "autoMapInputData",
                "value": None,
            },
            "options": {},
        },
        "credentials": {
            "airtableTokenApi": CRED_AIRTABLE,
        },
    }


def build_gmail_send_node(
    name: str,
    subject_expr: str,
    html_body: str,
    position: List[int],
) -> Dict[str, Any]:
    """Build a Gmail send node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": position,
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": subject_expr,
            "message": html_body,
            "options": {},
        },
        "credentials": {
            "gmailOAuth2": CRED_GMAIL,
        },
    }


def build_respond_node(
    name: str,
    position: List[int],
) -> Dict[str, Any]:
    """Build a respondToWebhook node returning {success: true}."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": position,
        "parameters": {
            "respondWith": "json",
            "responseBody": '={{ JSON.stringify({success: true}) }}',
            "options": {},
        },
    }


def build_connections(node_names: List[str]) -> Dict[str, Any]:
    """Build linear connections: node0 -> node1 -> node2 -> ...

    After the code node, split into two parallel paths:
      code -> airtable -> respond
      code -> gmail
    This matches the 4-node chain: webhook -> code -> [airtable -> respond, gmail]
    """
    # For our 5-node chain: webhook -> code -> airtable -> respond
    #                                     \-> gmail
    # node_names = [webhook, code, airtable, gmail, respond]
    webhook, code, airtable, gmail, respond = node_names

    return {
        webhook: {
            "main": [[{"node": code, "type": "main", "index": 0}]]
        },
        code: {
            "main": [[
                {"node": airtable, "type": "main", "index": 0},
                {"node": gmail, "type": "main", "index": 0},
            ]]
        },
        airtable: {
            "main": [[{"node": respond, "type": "main", "index": 0}]]
        },
    }


def build_workflow_json(
    name: str,
    nodes: List[Dict[str, Any]],
    connections: Dict[str, Any],
) -> Dict[str, Any]:
    """Wrap nodes and connections into a complete n8n workflow JSON."""
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
        },
        "tags": [{"name": "lead-capture"}, {"name": "webhook"}],
    }


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

FORMAT_WEBSITE_CONTACT_CODE = r"""
// Format Website Contact Form submission for Airtable
const item = $input.first().json;
const now = new Date();
const leadId = 'WEB-' + now.getTime().toString(36).toUpperCase();

return [{
  json: {
    'Lead ID': leadId,
    'Email': item.email || '',
    'First Name': item.firstName || '',
    'Last Name': item.lastName || '',
    'Name': item.name || ((item.firstName || '') + ' ' + (item.lastName || '')).trim(),
    'Company': item.company || '',
    'Phone': item.phone || '',
    'Message': item.message || '',
    'Interest': item.interest || '',
    'Page URL': item.page_url || '',
    'UTM Source': item.utm_source || '',
    'UTM Medium': item.utm_medium || '',
    'UTM Campaign': item.utm_campaign || '',
    'UTM Term': item.utm_term || '',
    'UTM Content': item.utm_content || '',
    'Source': 'Website Contact Form',
    'Status': 'New',
    'Created At': now.toISOString(),
  }
}];
"""

FORMAT_SEO_LEAD_CODE = r"""
// Format SEO Lead Capture submission for Airtable
const item = $input.first().json;
const now = new Date();
const leadId = 'SEO-' + now.getTime().toString(36).toUpperCase();

// Determine source from utm_source
const utmSource = (item.utm_source || '').toLowerCase();
let source = 'Organic';
if (utmSource.includes('google') && utmSource.includes('ad')) {
  source = 'Google Ads';
} else if (utmSource.includes('meta') || utmSource.includes('facebook') || utmSource.includes('instagram')) {
  source = 'Meta Ads';
} else if (utmSource.includes('tiktok')) {
  source = 'TikTok Ads';
} else if (utmSource.includes('linkedin')) {
  source = 'LinkedIn Ads';
} else if (utmSource.includes('google')) {
  source = 'Google Organic';
} else if (utmSource.includes('bing')) {
  source = 'Bing Organic';
} else if (utmSource.includes('twitter') || utmSource.includes('x.com')) {
  source = 'Twitter/X';
} else if (utmSource.includes('email') || utmSource.includes('newsletter')) {
  source = 'Email';
} else if (utmSource) {
  source = item.utm_source;
}

return [{
  json: {
    'Lead ID': leadId,
    'Email': item.email || '',
    'Name': item.name || '',
    'Company': item.company || '',
    'Phone': item.phone || '',
    'Message': item.message || '',
    'Page URL': item.page_url || '',
    'UTM Source': item.utm_source || '',
    'UTM Medium': item.utm_medium || '',
    'UTM Campaign': item.utm_campaign || '',
    'Source': source,
    'Status': 'New',
    'Created At': now.toISOString(),
  }
}];
"""

# ── Gmail HTML templates ────────────────────────────────────

GMAIL_WEBSITE_CONTACT_HTML = """<div style="font-family: Arial, sans-serif; max-width: 600px;">
  <h2 style="color: #FF6D5A;">New Website Lead</h2>
  <table style="width: 100%; border-collapse: collapse;">
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Name</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Name'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Email</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Email'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Company</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Company'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Phone</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Phone'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Interest</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Interest'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Page URL</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Page URL'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">UTM Source</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['UTM Source'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">UTM Campaign</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['UTM Campaign'] }}</td></tr>
  </table>
  <h3 style="color: #333; margin-top: 16px;">Message</h3>
  <p style="background: #f5f5f5; padding: 12px; border-radius: 4px;">{{ $('Format Lead Data').first().json['Message'] }}</p>
  <p style="color: #999; font-size: 12px; margin-top: 16px;">Lead ID: {{ $('Format Lead Data').first().json['Lead ID'] }} | {{ $('Format Lead Data').first().json['Created At'] }}</p>
</div>"""

GMAIL_SEO_LEAD_HTML = """<div style="font-family: Arial, sans-serif; max-width: 600px;">
  <h2 style="color: #FF6D5A;">New SEO Lead</h2>
  <table style="width: 100%; border-collapse: collapse;">
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Name</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Name'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Email</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Email'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Company</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Company'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Phone</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Phone'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Source</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Source'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Page URL</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Page URL'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">UTM Source</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['UTM Source'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">UTM Medium</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['UTM Medium'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">UTM Campaign</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['UTM Campaign'] }}</td></tr>
  </table>
  <h3 style="color: #333; margin-top: 16px;">Message</h3>
  <p style="background: #f5f5f5; padding: 12px; border-radius: 4px;">{{ $('Format SEO Lead').first().json['Message'] }}</p>
  <p style="color: #999; font-size: 12px; margin-top: 16px;">Lead ID: {{ $('Format SEO Lead').first().json['Lead ID'] }} | {{ $('Format SEO Lead').first().json['Created At'] }}</p>
</div>"""


# ======================================================================
# WORKFLOW BUILDERS
# ======================================================================

def build_website_contact_form() -> Dict[str, Any]:
    """Build the Website Contact Form webhook workflow."""
    webhook = build_webhook_node(
        name="Webhook",
        path="website-contact-form",
        position=[250, 300],
    )
    code = build_code_node(
        name="Format Lead Data",
        js_code=FORMAT_WEBSITE_CONTACT_CODE,
        position=[470, 300],
    )
    airtable = build_airtable_create_node(
        name="Save to Airtable",
        position=[690, 250],
    )
    gmail = build_gmail_send_node(
        name="Email Notification",
        subject_expr="=NEW LEAD: {{ $json['Name'] }} from {{ $json['Company'] }}",
        html_body=GMAIL_WEBSITE_CONTACT_HTML,
        position=[690, 450],
    )
    respond = build_respond_node(
        name="Respond Success",
        position=[910, 250],
    )

    nodes = [webhook, code, airtable, gmail, respond]
    node_names = [n["name"] for n in nodes]
    connections = build_connections(node_names)

    return build_workflow_json(
        name="AVM: Website Contact Form",
        nodes=nodes,
        connections=connections,
    )


def build_seo_lead_capture() -> Dict[str, Any]:
    """Build the SEO Lead Capture webhook workflow."""
    webhook = build_webhook_node(
        name="Webhook",
        path="seo-social/lead-capture",
        position=[250, 300],
    )
    code = build_code_node(
        name="Format SEO Lead",
        js_code=FORMAT_SEO_LEAD_CODE,
        position=[470, 300],
    )
    airtable = build_airtable_create_node(
        name="Save to Airtable",
        position=[690, 250],
    )
    gmail = build_gmail_send_node(
        name="Email Notification",
        subject_expr="=NEW LEAD (SEO): {{ $json['Name'] }} from {{ $json['Company'] }}",
        html_body=GMAIL_SEO_LEAD_HTML,
        position=[690, 450],
    )
    respond = build_respond_node(
        name="Respond Success",
        position=[910, 250],
    )

    nodes = [webhook, code, airtable, gmail, respond]
    node_names = [n["name"] for n in nodes]
    connections = build_connections(node_names)

    return build_workflow_json(
        name="AVM: SEO Lead Capture",
        nodes=nodes,
        connections=connections,
    )


# ======================================================================
# DEPLOY HELPERS
# ======================================================================

def get_n8n_client():
    """Create N8nClient with credentials from env."""
    try:
        from tools.n8n_client import N8nClient
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from n8n_client import N8nClient

    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        raise ValueError("N8N_API_KEY not set in .env")
    return N8nClient(base_url=base_url, api_key=api_key)


def save_workflow(key: str, workflow_data: Dict[str, Any]) -> Path:
    """Save workflow JSON to file."""
    spec = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "lead-capture"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec["filename"]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_data, f, indent=2, ensure_ascii=False)

    node_count = len(workflow_data["nodes"])
    print(f"  + {spec['name']:<40} -> {output_path.name} ({node_count} nodes)")
    return output_path


def deploy_workflow(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
    """Deploy workflow to n8n via API."""
    client = get_n8n_client()
    return client.create_workflow(workflow_data)


def activate_workflow(workflow_id: str) -> Dict[str, Any]:
    """Activate a workflow by ID."""
    client = get_n8n_client()
    return client.activate_workflow(workflow_id)


# ======================================================================
# CLI
# ======================================================================

# Map keys to builder functions
BUILDERS = {
    "website_contact": build_website_contact_form,
    "seo_lead": build_seo_lead_capture,
}


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("build", "deploy", "activate"):
        print("Usage: python tools/deploy_lead_capture.py <build|deploy|activate>")
        print()
        print("Actions:")
        print("  build     Build workflow JSONs to workflows/lead-capture/")
        print("  deploy    Build + deploy to n8n (inactive)")
        print("  activate  Build + deploy + activate")
        print()
        print("Workflows:")
        for key, spec in WORKFLOW_BUILDERS.items():
            print(f"  {key:<20} {spec['name']}")
        sys.exit(1)

    action = args[0]

    print("=" * 60)
    print("AVM LEAD CAPTURE - WORKFLOW BUILDER")
    print("=" * 60)
    print()
    print(f"Action:    {action}")
    print(f"Leads DB:  {LEADS_BASE_ID} / {LEADS_TABLE_ID}")
    print()

    # Build
    print("Building workflows...")
    print("-" * 40)
    built: Dict[str, Dict[str, Any]] = {}
    for key, builder_fn in BUILDERS.items():
        workflow = builder_fn()
        save_workflow(key, workflow)
        built[key] = workflow
    print()

    if action == "build":
        print("Build complete. Run 'deploy' to push to n8n.")
        return

    # Deploy
    if action in ("deploy", "activate"):
        print("Deploying to n8n (inactive)...")
        print("-" * 40)
        deployed_ids: Dict[str, str] = {}
        for key, workflow in built.items():
            try:
                resp = deploy_workflow(workflow)
                wf_id = resp.get("id", "unknown")
                deployed_ids[key] = wf_id
                print(f"  + {WORKFLOW_BUILDERS[key]['name']:<40} -> {wf_id}")
            except Exception as e:
                print(f"  - {WORKFLOW_BUILDERS[key]['name']:<40} FAILED: {e}")
        print()

        # Activate
        if action == "activate" and deployed_ids:
            print("Activating workflows...")
            print("-" * 40)
            for key, wf_id in deployed_ids.items():
                try:
                    activate_workflow(wf_id)
                    print(f"  + {WORKFLOW_BUILDERS[key]['name']:<40} ACTIVE")
                except Exception as e:
                    print(f"  - {WORKFLOW_BUILDERS[key]['name']:<40} FAILED: {e}")
            print()

        # Save deployed IDs
        if deployed_ids:
            output_dir = Path(__file__).parent.parent / ".tmp"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "lead_capture_ids.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({
                    "deployed": deployed_ids,
                    "deployed_at": datetime.now().isoformat(),
                }, f, indent=2)
            print(f"Workflow IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Verify workflows in n8n UI")
    print("  2. Test webhook: POST to /webhook/website-contact-form")
    print("  3. Check Airtable Leads table for new records")
    print("  4. Confirm Gmail notification received")


if __name__ == "__main__":
    main()
