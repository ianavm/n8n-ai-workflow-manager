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

# ── Turnstile (Cloudflare bot challenge) ────────────────────
# Server-side secret baked into the Verify Turnstile HTTP Request node at
# deploy time. Must be present in .env or deploy fails closed.
TURNSTILE_SECRET: str = os.environ.get("CLOUDFLARE_TURNSTILE_SECRET", "")

# ── Airtable IDs ────────────────────────────────────────────
LEADS_BASE_ID = "apptjjBx34z9340tK"
LEADS_TABLE_ID = "tblwOPTPY85Tcj7NJ"

# Suppression list lives in the Lead Scraper base (separate from Leads base).
SUPPRESSION_BASE_ID = "app2ALQUP7CKEkHOz"
SUPPRESSION_TABLE_ID = "tbl0LtepawDzFYg4I"

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
    format_node_name: str,
    columns: List[str],
) -> Dict[str, Any]:
    """Build an Airtable CREATE node for the Leads table using defineBelow mapping.

    Fields are sourced from the upstream Format node via $() reference so that
    a suppression check (which replaces $json) can be inserted before this node
    without losing the original lead payload.
    """
    schema = [
        {
            "id": col,
            "type": "string",
            "display": True,
            "displayName": col,
            "required": False,
            "defaultMatch": False,
            "canBeUsedToMatch": True,
        }
        for col in columns
    ]
    value_map = {
        col: f"={{{{ $('{format_node_name}').first().json['{col}'] }}}}"
        for col in columns
    }

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": position,
        "parameters": {
            "operation": "create",
            "base": {
                "__rl": True,
                "mode": "list",
                "value": LEADS_BASE_ID,
                "cachedResultName": "AVM Marketing",
            },
            "table": {
                "__rl": True,
                "mode": "list",
                "value": LEADS_TABLE_ID,
                "cachedResultName": "Leads",
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": value_map,
                "schema": schema,
            },
            "options": {},
        },
        "credentials": {
            "airtableTokenApi": CRED_AIRTABLE,
        },
    }


def build_suppression_search_node(
    name: str,
    position: List[int],
    format_node_name: str,
) -> Dict[str, Any]:
    """Build an Airtable SEARCH node against the Email Suppression table.

    Looks up the normalized lookup email (lowercased + Gmail dot-stripped) from
    the upstream Format node. alwaysOutputData=true ensures an empty item flows
    through on 0 matches (so the downstream IF gate can evaluate). Errors fall
    through as "not suppressed" (fail open — never block a legitimate lead due
    to an Airtable outage).
    """
    formula = (
        f"=LOWER({{Email}}) = "
        f"LOWER('{{{{ $('{format_node_name}').first().json['_lookupEmail'] }}}}')"
    )

    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
        "position": position,
        "parameters": {
            "operation": "search",
            "base": {
                "__rl": True,
                "mode": "list",
                "value": SUPPRESSION_BASE_ID,
                "cachedResultName": "Lead Scraper - Johannesburg CRM",
            },
            "table": {
                "__rl": True,
                "mode": "list",
                "value": SUPPRESSION_TABLE_ID,
                "cachedResultName": "Email Suppression",
            },
            "filterByFormula": formula,
            "options": {
                "fields": ["Email"],
            },
        },
        "credentials": {
            "airtableTokenApi": CRED_AIRTABLE,
        },
    }


def build_not_suppressed_if_node(
    name: str,
    position: List[int],
) -> Dict[str, Any]:
    """Build an IF v2.2 gate that passes when the upstream search found no row.

    Output 0 (true) = no suppression row = clean lead (continue processing).
    Output 1 (false) = suppression row found = silently drop.
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "version": 2,
                    "leftValue": "",
                    "caseSensitive": True,
                    "typeValidation": "loose",
                },
                "combinator": "and",
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.id || '' }}",
                        "rightValue": "",
                        "operator": {
                            "type": "string",
                            "operation": "empty",
                            "singleValue": True,
                        },
                    }
                ],
            },
            "options": {},
        },
    }


def build_turnstile_verify_node(
    name: str,
    position: List[int],
    secret: str,
) -> Dict[str, Any]:
    """Build an HTTP Request node that verifies a Turnstile token with Cloudflare.

    Posts to https://challenges.cloudflare.com/turnstile/v0/siteverify with the
    server-side secret and the client-submitted token. Output shape:
        {success: bool, "error-codes": [...], ...}
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "parameters": {
            "method": "POST",
            "url": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            "sendBody": True,
            "contentType": "form-urlencoded",
            "bodyParameters": {
                "parameters": [
                    {"name": "secret", "value": secret},
                    {
                        "name": "response",
                        "value": "={{ $json.body.cf_turnstile_token || '' }}",
                    },
                ]
            },
            "options": {},
        },
    }


def build_turnstile_valid_if_node(
    name: str,
    position: List[int],
) -> Dict[str, Any]:
    """Build an IF v2.2 gate that checks Cloudflare siteverify returned success.

    Output 0 (true) = verified human = continue to Format.
    Output 1 (false) = verification failed or missing = respond 403.
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "version": 2,
                    "leftValue": "",
                    "caseSensitive": True,
                    "typeValidation": "loose",
                },
                "combinator": "and",
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.success }}",
                        "rightValue": "",
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                            "singleValue": True,
                        },
                    }
                ],
            },
            "options": {},
        },
    }


def build_turnstile_failed_respond_node(
    name: str,
    position: List[int],
) -> Dict[str, Any]:
    """respondToWebhook returning HTTP 403 when Turnstile verification fails."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": position,
        "parameters": {
            "respondWith": "json",
            "responseCode": 403,
            "responseBody": "={{ JSON.stringify({error: 'turnstile verification failed'}) }}",
            "options": {},
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


def build_lead_capture_connections(
    webhook: str,
    turnstile_verify: str,
    turnstile_valid: str,
    turnstile_failed: str,
    code: str,
    search: str,
    gate: str,
    airtable: str,
    gmail: str,
    respond: str,
) -> Dict[str, Any]:
    """Wire the 10-node lead capture chain with Turnstile + suppression gating.

    Flow:
      webhook -> turnstile_verify -> turnstile_valid
      turnstile_valid output 0 (true, verified human) -> code
      turnstile_valid output 1 (false, bot/invalid)   -> turnstile_failed (403)
      code -> search -> gate
      gate output 0 (true, not suppressed) -> airtable + gmail
      gate output 1 (false, suppressed)    -> respond (silent success)
      airtable -> respond
      gmail has no downstream (fire-and-forget)
    """
    return {
        webhook: {
            "main": [[{"node": turnstile_verify, "type": "main", "index": 0}]]
        },
        turnstile_verify: {
            "main": [[{"node": turnstile_valid, "type": "main", "index": 0}]]
        },
        turnstile_valid: {
            "main": [
                [{"node": code, "type": "main", "index": 0}],
                [{"node": turnstile_failed, "type": "main", "index": 0}],
            ]
        },
        code: {
            "main": [[{"node": search, "type": "main", "index": 0}]]
        },
        search: {
            "main": [[{"node": gate, "type": "main", "index": 0}]]
        },
        gate: {
            "main": [
                [
                    {"node": airtable, "type": "main", "index": 0},
                    {"node": gmail, "type": "main", "index": 0},
                ],
                [
                    {"node": respond, "type": "main", "index": 0},
                ],
            ]
        },
        airtable: {
            "main": [[{"node": respond, "type": "main", "index": 0}]]
        },
    }


# Columns written to the Leads table, in order. Must match the real schema
# in base apptjjBx34z9340tK / table tblwOPTPY85Tcj7NJ (reconstructed from
# live execution data — see execution 20615 for reference shape).
LEAD_COLUMNS: List[str] = [
    "Lead ID",
    "Contact Name",
    "Email",
    "Phone",
    "Company",
    "Source Channel",
    "Source URL",
    "UTM Source",
    "UTM Medium",
    "UTM Campaign",
    "First Touch Content",
    "Notes",
    "Status",
    "Source System",
    "Grade",
    "Created At",
]

WEBSITE_CONTACT_COLUMNS: List[str] = LEAD_COLUMNS
SEO_LEAD_COLUMNS: List[str] = LEAD_COLUMNS


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

NORMALIZE_EMAIL_JS = r"""
function normalizeLookupEmail(raw) {
  const lowered = String(raw || '').trim().toLowerCase();
  const atIdx = lowered.indexOf('@');
  if (atIdx <= 0) return lowered;
  const local = lowered.slice(0, atIdx);
  const domain = lowered.slice(atIdx + 1);
  if (domain === 'gmail.com' || domain === 'googlemail.com') {
    return local.replace(/\./g, '').replace(/\+.*$/, '') + '@gmail.com';
  }
  return lowered;
}
"""

# Webhook node v2 wraps incoming POST under $json.body. Fall back to $json
# for hand-crafted test payloads or legacy webhook versions.
UNWRAP_BODY_JS = r"""
const root = $input.first().json || {};
const body = (root && typeof root.body === 'object' && root.body) ? root.body : root;
"""

FORMAT_WEBSITE_CONTACT_CODE = r"""
// Format Website Contact Form submission for Airtable
""" + NORMALIZE_EMAIL_JS + UNWRAP_BODY_JS + r"""
const now = new Date();
const leadId = 'WEB-' + now.getTime().toString(36).toUpperCase();
const rawEmail = body.email || '';
const contactName = body.name
  || ((body.firstName || '') + ' ' + (body.lastName || '')).trim();

return [{
  json: {
    'Lead ID': leadId,
    'Contact Name': contactName,
    'Email': rawEmail,
    'Phone': body.phone || '',
    'Company': body.company || '',
    'Source Channel': 'Organic',
    'Source URL': body.page_url || '',
    'UTM Source': body.utm_source || '',
    'UTM Medium': body.utm_medium || '',
    'UTM Campaign': body.utm_campaign || '',
    'First Touch Content': body.interest || '',
    'Notes': body.message || '',
    'Status': 'New',
    // NOTE: 'Source System' is a singleSelect. Keep value matching the
    // existing choice set; old live workflow used 'SEO_Inbound' for both
    // website + SEO forms, so preserve that to avoid Airtable rejection.
    'Source System': 'SEO_Inbound',
    'Grade': 'Warm',
    'Created At': now.toISOString().slice(0, 10),
    // Internal key used by the suppression search node. Not mapped to Airtable.
    '_lookupEmail': normalizeLookupEmail(rawEmail),
  }
}];
"""

FORMAT_SEO_LEAD_CODE = r"""
// Format SEO Lead Capture submission for Airtable
""" + NORMALIZE_EMAIL_JS + UNWRAP_BODY_JS + r"""
const now = new Date();
const leadId = 'SEO-' + now.getTime().toString(36).toUpperCase();
const rawEmail = body.email || '';

// Determine source channel from utm_source
const utmSource = (body.utm_source || '').toLowerCase();
let sourceChannel = 'Organic';
if (utmSource.includes('ad') || utmSource.includes('cpc') || utmSource.includes('ppc')) {
  sourceChannel = 'Paid';
} else if (utmSource.includes('email') || utmSource.includes('newsletter')) {
  sourceChannel = 'Email';
} else if (utmSource.includes('referral')) {
  sourceChannel = 'Referral';
}

return [{
  json: {
    'Lead ID': leadId,
    'Contact Name': body.name || '',
    'Email': rawEmail,
    'Phone': body.phone || '',
    'Company': body.company || '',
    'Source Channel': sourceChannel,
    'Source URL': body.page_url || '',
    'UTM Source': body.utm_source || '',
    'UTM Medium': body.utm_medium || '',
    'UTM Campaign': body.utm_campaign || '',
    'First Touch Content': body.interest || '',
    'Notes': body.message || '',
    'Status': 'New',
    'Source System': 'SEO_Inbound',
    'Grade': 'Warm',
    'Created At': now.toISOString().slice(0, 10),
    // Internal key used by the suppression search node. Not mapped to Airtable.
    '_lookupEmail': normalizeLookupEmail(rawEmail),
  }
}];
"""

# ── Gmail HTML templates ────────────────────────────────────

GMAIL_WEBSITE_CONTACT_HTML = """<div style="font-family: Arial, sans-serif; max-width: 600px;">
  <h2 style="color: #FF6D5A;">New Website Lead</h2>
  <table style="width: 100%; border-collapse: collapse;">
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Name</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Contact Name'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Email</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Email'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Company</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Company'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Phone</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Phone'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Interest</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['First Touch Content'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Source</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['UTM Source'] }} / {{ $('Format Lead Data').first().json['UTM Medium'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Page</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format Lead Data').first().json['Source URL'] }}</td></tr>
  </table>
  <h3 style="color: #333; margin-top: 16px;">Message</h3>
  <p style="background: #f5f5f5; padding: 12px; border-radius: 4px;">{{ $('Format Lead Data').first().json['Notes'] }}</p>
  <p style="color: #999; font-size: 12px; margin-top: 16px;">Lead ID: {{ $('Format Lead Data').first().json['Lead ID'] }} | {{ $('Format Lead Data').first().json['Created At'] }}</p>
</div>"""

GMAIL_SEO_LEAD_HTML = """<div style="font-family: Arial, sans-serif; max-width: 600px;">
  <h2 style="color: #FF6D5A;">New SEO Lead</h2>
  <table style="width: 100%; border-collapse: collapse;">
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Name</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Contact Name'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Email</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Email'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Company</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Company'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Phone</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Phone'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Channel</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Source Channel'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">Page</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['Source URL'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">UTM Source</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['UTM Source'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">UTM Medium</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['UTM Medium'] }}</td></tr>
    <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #eee;">UTM Campaign</td>
        <td style="padding: 8px; border-bottom: 1px solid #eee;">{{ $('Format SEO Lead').first().json['UTM Campaign'] }}</td></tr>
  </table>
  <h3 style="color: #333; margin-top: 16px;">Message</h3>
  <p style="background: #f5f5f5; padding: 12px; border-radius: 4px;">{{ $('Format SEO Lead').first().json['Notes'] }}</p>
  <p style="color: #999; font-size: 12px; margin-top: 16px;">Lead ID: {{ $('Format SEO Lead').first().json['Lead ID'] }} | {{ $('Format SEO Lead').first().json['Created At'] }}</p>
</div>"""


# ======================================================================
# WORKFLOW BUILDERS
# ======================================================================

def _build_lead_form_workflow(
    *,
    workflow_name: str,
    webhook_path: str,
    format_name: str,
    format_code: str,
    columns: List[str],
    email_subject_expr: str,
    email_html: str,
) -> Dict[str, Any]:
    """Shared assembly for the Website Contact Form and SEO Lead Capture flows.

    Layout: Webhook → Verify Turnstile → Turnstile Valid? → [false → 403,
    true → Format → Check Suppression → Not Suppressed? → {Save, Email} → Respond]
    """
    if not TURNSTILE_SECRET:
        raise RuntimeError(
            "CLOUDFLARE_TURNSTILE_SECRET must be set in .env before deploying "
            "lead-capture workflows (required for Cloudflare siteverify)."
        )

    webhook = build_webhook_node(
        name="Webhook",
        path=webhook_path,
        position=[250, 300],
    )
    turnstile_verify = build_turnstile_verify_node(
        name="Verify Turnstile",
        position=[360, 180],
        secret=TURNSTILE_SECRET,
    )
    turnstile_valid = build_turnstile_valid_if_node(
        name="Turnstile Valid?",
        position=[470, 180],
    )
    turnstile_failed = build_turnstile_failed_respond_node(
        name="Turnstile Failed",
        position=[580, 60],
    )
    code = build_code_node(
        name=format_name,
        js_code=format_code,
        position=[580, 300],
    )
    search = build_suppression_search_node(
        name="Check Suppression",
        position=[800, 300],
        format_node_name=format_name,
    )
    gate = build_not_suppressed_if_node(
        name="Not Suppressed?",
        position=[1020, 300],
    )
    airtable = build_airtable_create_node(
        name="Save to Airtable",
        position=[1240, 250],
        format_node_name=format_name,
        columns=columns,
    )
    gmail = build_gmail_send_node(
        name="Email Notification",
        subject_expr=email_subject_expr,
        html_body=email_html,
        position=[1240, 450],
    )
    respond = build_respond_node(
        name="Respond Success",
        position=[1460, 250],
    )

    nodes = [
        webhook,
        turnstile_verify,
        turnstile_valid,
        turnstile_failed,
        code,
        search,
        gate,
        airtable,
        gmail,
        respond,
    ]
    connections = build_lead_capture_connections(
        webhook=webhook["name"],
        turnstile_verify=turnstile_verify["name"],
        turnstile_valid=turnstile_valid["name"],
        turnstile_failed=turnstile_failed["name"],
        code=code["name"],
        search=search["name"],
        gate=gate["name"],
        airtable=airtable["name"],
        gmail=gmail["name"],
        respond=respond["name"],
    )

    return build_workflow_json(
        name=workflow_name,
        nodes=nodes,
        connections=connections,
    )


def build_website_contact_form() -> Dict[str, Any]:
    """Build the Website Contact Form webhook workflow."""
    return _build_lead_form_workflow(
        workflow_name="AVM: Website Contact Form",
        webhook_path="website-contact-form",
        format_name="Format Lead Data",
        format_code=FORMAT_WEBSITE_CONTACT_CODE,
        columns=WEBSITE_CONTACT_COLUMNS,
        email_subject_expr=(
            "=NEW LEAD: {{ $('Format Lead Data').first().json['Contact Name'] }} "
            "from {{ $('Format Lead Data').first().json['Company'] }}"
        ),
        email_html=GMAIL_WEBSITE_CONTACT_HTML,
    )


def build_seo_lead_capture() -> Dict[str, Any]:
    """Build the SEO Lead Capture webhook workflow."""
    return _build_lead_form_workflow(
        workflow_name="AVM: SEO Lead Capture",
        webhook_path="seo-social/lead-capture",
        format_name="Format SEO Lead",
        format_code=FORMAT_SEO_LEAD_CODE,
        columns=SEO_LEAD_COLUMNS,
        email_subject_expr=(
            "=NEW LEAD (SEO): {{ $('Format SEO Lead').first().json['Contact Name'] }} "
            "from {{ $('Format SEO Lead').first().json['Company'] }}"
        ),
        email_html=GMAIL_SEO_LEAD_HTML,
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


TURNSTILE_SECRET_PLACEHOLDER = "__CLOUDFLARE_TURNSTILE_SECRET__"


def _redact_turnstile_for_commit(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the workflow with the real Turnstile secret replaced
    by a placeholder so the committed JSON does not leak the live secret.

    The deploy path does NOT use this — it sends the real secret to n8n.
    """
    if not TURNSTILE_SECRET:
        return workflow_data
    dumped = json.dumps(workflow_data)
    if TURNSTILE_SECRET in dumped:
        dumped = dumped.replace(TURNSTILE_SECRET, TURNSTILE_SECRET_PLACEHOLDER)
        return json.loads(dumped)
    return workflow_data


def save_workflow(key: str, workflow_data: Dict[str, Any]) -> Path:
    """Save workflow JSON to file (with Turnstile secret redacted)."""
    spec = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "lead-capture"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec["filename"]

    redacted = _redact_turnstile_for_commit(workflow_data)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(redacted, f, indent=2, ensure_ascii=False)

    node_count = len(redacted["nodes"])
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
