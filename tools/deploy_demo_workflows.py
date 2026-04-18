"""
AVM Demo Workflows — three social-media automation demos.

Builds and deploys three webhook/trigger-driven workflows designed as
30-60 second video demos:

    1. DEMO: Missed Call Money Back
         Twilio StatusCallback webhook -> if missed, auto-SMS the caller,
         log to Airtable, alert owner on Telegram.

    2. DEMO: 5-Minute Lead Responder
         Website form webhook -> Airtable lead row + SMS to lead + Gmail
         auto-reply + Telegram owner alert, all within seconds.

    3. DEMO: Inbox Autopilot
         Gmail trigger -> Claude classifies (URGENT/CLIENT/SALES/BILLING/NOISE)
         via OpenRouter -> star + Telegram for urgent, draft reply for
         client/sales, archive for noise. Every email logged to Airtable.

All three use credentials already present in n8n (no new creds needed):
    - Twilio      YzAgDJdx5ZaKbbar   (type: twilioApi)
    - Airtable    ZyBrcAO6fps7YB3u   (type: airtableTokenApi)
    - Gmail       2IuycrTIgWJZEjBE   (type: gmailOAuth2)
    - Telegram    Ha3Ewmk9ofbvWyZ9   (type: telegramApi)
    - OpenRouter  HPAZMuVNbPKnCLx0   (type: openRouterApi)

Required env (deployment will still succeed with placeholders but runtime
execution will fail until set):
    SOCIAL_BUILDS_BASE_ID        Social Media Builds base id
    DEMO_MCB_TABLE               from setup_social_media_builds_base.py
    DEMO_IA_TABLE                from setup_social_media_builds_base.py
    DEMO_LEAD_TABLE              from setup_social_media_builds_base.py
    TWILIO_WHATSAPP_FROM         Twilio WhatsApp sender (sandbox or prod)
    TELEGRAM_OWNER_CHAT_ID       owner's Telegram chat id
    AUTOMATION_SENDERS           comma-list of own addresses (loop guard)

Usage:
    python tools/deploy_demo_workflows.py build     # Build JSONs only
    python tools/deploy_demo_workflows.py deploy    # Build + deploy (inactive)
    python tools/deploy_demo_workflows.py activate  # Build + deploy + activate
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


# ── Credential Constants ────────────────────────────────────────────────────

CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_TWILIO = {"id": "YzAgDJdx5ZaKbbar", "name": "Twilio"}
CRED_TELEGRAM = {"id": "Ha3Ewmk9ofbvWyZ9", "name": "Telegram AVMCRMBot"}
# OpenRouter 2WC is the credential known to work for the production email
# mgmt workflow; the other OpenRouter creds in this account are stale.
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}


# ── Airtable IDs ────────────────────────────────────────────────────────────
#
# All three demo workflows write to the dedicated "Social Media Builds" base
# so they stay isolated from live business data. The existing Leads table in
# the Marketing base is NOT touched by these demos — SL_Leads in the new base
# is a schema-compatible clone.

DEMO_BASE_ID = os.getenv(
    "SOCIAL_BUILDS_BASE_ID",
    # Fall back to Marketing base only if the new base hasn't been created.
    os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK"),
)
MCB_TABLE_ID = os.getenv("DEMO_MCB_TABLE", "tblMCB_PLACEHOLDER__RUN_SETUP_FIRST")
IA_TABLE_ID = os.getenv("DEMO_IA_TABLE", "tblIA_PLACEHOLDER__RUN_SETUP_FIRST")
LEAD_TABLE_ID = os.getenv("DEMO_LEAD_TABLE", "tblSL_PLACEHOLDER__RUN_SETUP_FIRST")


# ── Runtime Config (safe placeholders; real values loaded at execution) ─────

# Demo workflows send via Twilio WhatsApp (not SMS) because US A2P 10DLC
# registration is required for SMS and takes days to weeks. The sandbox
# number is free and instant.
# Default is Twilio's shared WhatsApp Sandbox number; confirm yours in
# Console > Messaging > Try it out > Send a WhatsApp message.
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "+14155238886")
# Kept for backwards compatibility / future real-SMS switch.
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", TWILIO_WHATSAPP_FROM)
TELEGRAM_OWNER_CHAT_ID = os.getenv("TELEGRAM_OWNER_CHAT_ID", "")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "ian@anyvisionmedia.com")
AUTOMATION_SENDERS = os.getenv("AUTOMATION_SENDERS", "ian@anyvisionmedia.com")

# Business hours (Africa/Johannesburg) used to pick SMS copy in Workflow 3.
BUSINESS_HOURS_START = int(os.getenv("BUSINESS_HOURS_START", "8"))
BUSINESS_HOURS_END = int(os.getenv("BUSINESS_HOURS_END", "18"))


# ── Workflow Registry ──────────────────────────────────────────────────────

WORKFLOW_BUILDERS: dict[str, dict[str, str]] = {
    "missed_call": {
        "name": "DEMO: Missed Call Money Back",
        "filename": "demo_missed_call_money_back.json",
    },
    "speed_to_lead": {
        "name": "DEMO: 5-Minute Lead Responder",
        "filename": "demo_5_minute_lead_responder.json",
    },
    "inbox_autopilot": {
        "name": "DEMO: Inbox Autopilot",
        "filename": "demo_inbox_autopilot.json",
    },
}


def uid() -> str:
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ============================================================================
# GENERIC NODE BUILDERS
# ============================================================================


def webhook_node(name: str, path: str, position: list[int]) -> dict[str, Any]:
    """POST webhook trigger with response-node mode.

    ``responseMode=responseNode`` in n8n requires onError=continueRegularOutput
    so the Respond node always gets a chance to answer Twilio / Typeform even
    if an upstream node errors.
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": position,
        "webhookId": uid(),
        "onError": "continueRegularOutput",
        "parameters": {
            "path": path,
            "httpMethod": "POST",
            "responseMode": "responseNode",
            "options": {},
        },
    }


def code_node(name: str, js: str, position: list[int]) -> dict[str, Any]:
    """Standard JS Code node (runOnceForAllItems)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {"jsCode": js},
    }


def if_node(name: str, expr: str, position: list[int]) -> dict[str, Any]:
    """Single-condition IF node (truthy check). True branch = output 0.

    The runtime validator wants conditions.options.leftValue to exist as a
    default even when we supply a per-condition leftValue, so we seed it
    with an empty string.
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
                    "caseSensitive": True,
                    "typeValidation": "loose",
                    "leftValue": "",
                },
                "combinator": "and",
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": expr,
                        "rightValue": "",
                        "operator": {
                            "type": "string",
                            "operation": "notEmpty",
                            "singleValue": True,
                        },
                    }
                ],
            },
            "options": {},
        },
    }


def respond_node(name: str, position: list[int], body: str = '={{ JSON.stringify({success: true}) }}') -> dict[str, Any]:
    """respondToWebhook returning JSON."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": position,
        "parameters": {
            "respondWith": "json",
            "responseBody": body,
            "options": {},
        },
    }


def twilio_whatsapp_node(
    name: str,
    to_expr: str,
    message_expr: str,
    position: list[int],
) -> dict[str, Any]:
    """Twilio WhatsApp send via the sandbox (or a production WA sender).

    ``toWhatsapp: true`` on n8n's Twilio node prepends ``whatsapp:`` to both
    the from and to numbers at send time, so we keep plain E.164 values here.
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.twilio",
        "typeVersion": 1,
        "onError": "continueRegularOutput",
        "position": position,
        "parameters": {
            "resource": "sms",
            "operation": "send",
            "from": TWILIO_WHATSAPP_FROM,
            "to": to_expr,
            "toWhatsapp": True,
            "message": message_expr,
            "options": {},
        },
        "credentials": {"twilioApi": CRED_TWILIO},
    }


# Alias retained so existing call sites keep compiling during the WA pivot.
twilio_sms_node = twilio_whatsapp_node


def telegram_alert_node(
    name: str,
    text_expr: str,
    position: list[int],
) -> dict[str, Any]:
    """Telegram sendMessage to owner chat."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "onError": "continueRegularOutput",
        "position": position,
        "parameters": {
            "resource": "message",
            "operation": "sendMessage",
            "chatId": TELEGRAM_OWNER_CHAT_ID,
            "text": text_expr,
            "additionalFields": {
                "parse_mode": "HTML",
                "disable_notification": False,
            },
        },
        "credentials": {"telegramApi": CRED_TELEGRAM},
    }


def airtable_create_node(
    name: str,
    table_id: str,
    source_node: str,
    columns: list[str],
    position: list[int],
    base_id: str = DEMO_BASE_ID,
) -> dict[str, Any]:
    """Airtable CREATE with defineBelow mapping from an upstream source node."""
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
        col: f"={{{{ $('{source_node}').first().json['{col}'] }}}}"
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
            "base": {"__rl": True, "mode": "id", "value": base_id},
            "table": {"__rl": True, "mode": "id", "value": table_id},
            "columns": {
                "mappingMode": "defineBelow",
                "value": value_map,
                "schema": schema,
            },
            "options": {},
        },
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    }


def airtable_search_node(
    name: str,
    table_id: str,
    formula: str,
    position: list[int],
    base_id: str = DEMO_BASE_ID,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Airtable SEARCH by filterByFormula, always emits at least one item."""
    options: dict[str, Any] = {}
    if fields:
        options["fields"] = fields
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
            "base": {"__rl": True, "mode": "id", "value": base_id},
            "table": {"__rl": True, "mode": "id", "value": table_id},
            "filterByFormula": formula,
            "options": options,
        },
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    }


def workflow_envelope(
    name: str,
    nodes: list[dict[str, Any]],
    connections: dict[str, Any],
    tags: list[str],
) -> dict[str, Any]:
    """Wrap nodes and connections in a complete n8n workflow JSON."""
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
        },
        "tags": [{"name": t} for t in tags],
    }


# ============================================================================
# WORKFLOW 3 — MISSED CALL MONEY BACK
# ============================================================================

MCB_PARSE_CALL_JS = r"""
// Parse Twilio Voice StatusCallback payload (or a manual test POST).
// Webhook v2 wraps POST body under $json.body.
const root = $input.first().json || {};
const body = (root && typeof root.body === 'object' && root.body) ? root.body : root;

const rawStatus = String(body.CallStatus || body.DialCallStatus || body.call_status || '').toLowerCase().trim();
const missedStatuses = ['no-answer', 'busy', 'failed', 'canceled', 'cancelled'];
const isMissed = missedStatuses.includes(rawStatus);

const fromPhone = String(body.From || body.from || '').trim();
const toPhone = String(body.To || body.to || '').trim();
const callSid = String(body.CallSid || body.call_sid || '').trim();

// Johannesburg hours — Date.toLocaleString with a timezone returns the wall-clock
// in that zone, so parsing its hour gives us SAST regardless of server TZ.
const now = new Date();
const sastParts = now.toLocaleString('en-GB', {
  timeZone: 'Africa/Johannesburg',
  hour: '2-digit',
  hour12: false,
});
const sastHour = parseInt(sastParts, 10);
const businessHoursStart = 8;
const businessHoursEnd = 18;
const inBusinessHours = sastHour >= businessHoursStart && sastHour < businessHoursEnd;
const callWindow = inBusinessHours ? 'business-hours' : 'after-hours';

const callId = 'MCB-' + now.getTime().toString(36).toUpperCase();

return [{
  json: {
    'Call ID': callId,
    'From Phone': fromPhone,
    'To Phone': toPhone,
    'Call Status': rawStatus || 'unknown',
    'Call Window': callWindow,
    'Call SID': callSid,
    'Received At': now.toISOString(),
    _isMissed: isMissed,
    _inBusinessHours: inBusinessHours,
  }
}];
"""


MCB_COMPOSE_SMS_JS = r"""
// Compose the reply WhatsApp message. If there is already a row in
// MCB_Missed_Calls for this phone number, treat it as a repeat caller and
// send a softer follow-up.
const parsed = $('Parse Call').first().json;
const search = $input.first().json || {};
const isRepeat = !!(search && search.id);

const inHours = parsed._inBusinessHours;
let body;
if (isRepeat) {
  body = "Hey again — thanks for calling back. What's the best way to help you? "
       + "Happy to sort it over WhatsApp or book a quick call.";
} else if (inHours) {
  body = "Hey! Sorry I missed your call — I'm on a job right now. "
       + "What can I help you with? I'll WhatsApp you back in 10 min.";
} else {
  body = "Hey! Sorry I missed your call — we're closed right now. "
       + "What can I help you with? I'll reply first thing tomorrow.";
}

return [{
  json: Object.assign({}, parsed, {
    'Is Repeat Caller': isRepeat,
    'SMS Body': body,
    'Status': 'SMS Sent',
  })
}];
"""


def build_missed_call() -> dict[str, Any]:
    """Assemble the Missed Call Money Back workflow."""

    webhook = webhook_node(
        name="Webhook",
        path="demo/missed-call",
        position=[240, 320],
    )
    parse = code_node(
        name="Parse Call",
        js=MCB_PARSE_CALL_JS,
        position=[460, 320],
    )
    is_missed = if_node(
        name="Is Missed?",
        expr="={{ $json._isMissed ? 'yes' : '' }}",
        position=[680, 320],
    )
    # Repeat caller lookup — filterByFormula on From Phone.
    repeat_search = airtable_search_node(
        name="Repeat Caller?",
        table_id=MCB_TABLE_ID,
        formula=(
            "={{ \"{From Phone} = '\" + $('Parse Call').first().json['From Phone'] + \"'\" }}"
        ),
        position=[900, 240],
        fields=["From Phone"],
    )
    compose = code_node(
        name="Compose SMS",
        js=MCB_COMPOSE_SMS_JS,
        position=[1120, 240],
    )
    send_sms = twilio_whatsapp_node(
        name="Send WhatsApp",
        to_expr="={{ $json['From Phone'] }}",
        message_expr="={{ $json['SMS Body'] }}",
        position=[1340, 160],
    )
    log_call = airtable_create_node(
        name="Log Call",
        table_id=MCB_TABLE_ID,
        source_node="Compose SMS",
        columns=[
            "Call ID",
            "From Phone",
            "To Phone",
            "Call Status",
            "Call Window",
            "Is Repeat Caller",
            "SMS Body",
            "Status",
            "Received At",
        ],
        position=[1340, 320],
    )
    alert_owner = telegram_alert_node(
        name="Alert Owner",
        text_expr=(
            "=<b>Missed call</b>\n"
            "From: {{ $json['From Phone'] }}\n"
            "Window: {{ $json['Call Window'] }}\n"
            "Repeat: {{ $json['Is Repeat Caller'] ? 'yes' : 'no' }}\n"
            "WhatsApp sent \u2705"
        ),
        position=[1340, 480],
    )
    respond_ok = respond_node("Respond OK", [1560, 320])
    respond_skip = respond_node("Respond (not missed)", [900, 480])

    nodes = [
        webhook,
        parse,
        is_missed,
        repeat_search,
        compose,
        send_sms,
        log_call,
        alert_owner,
        respond_ok,
        respond_skip,
    ]

    connections = {
        webhook["name"]: {"main": [[{"node": parse["name"], "type": "main", "index": 0}]]},
        parse["name"]: {"main": [[{"node": is_missed["name"], "type": "main", "index": 0}]]},
        is_missed["name"]: {
            "main": [
                [{"node": repeat_search["name"], "type": "main", "index": 0}],
                [{"node": respond_skip["name"], "type": "main", "index": 0}],
            ]
        },
        repeat_search["name"]: {"main": [[{"node": compose["name"], "type": "main", "index": 0}]]},
        compose["name"]: {
            "main": [
                [
                    {"node": send_sms["name"], "type": "main", "index": 0},
                    {"node": log_call["name"], "type": "main", "index": 0},
                    {"node": alert_owner["name"], "type": "main", "index": 0},
                ]
            ]
        },
        log_call["name"]: {"main": [[{"node": respond_ok["name"], "type": "main", "index": 0}]]},
    }

    return workflow_envelope(
        name=WORKFLOW_BUILDERS["missed_call"]["name"],
        nodes=nodes,
        connections=connections,
        tags=["demo", "twilio", "missed-call"],
    )


# ============================================================================
# WORKFLOW 1 — 5-MINUTE LEAD RESPONDER
# ============================================================================

SL_FORMAT_LEAD_JS = r"""
// Normalize the form payload into a lead row, a personalized SMS, and a
// personalized reply-email body.
const root = $input.first().json || {};
const body = (root && typeof root.body === 'object' && root.body) ? root.body : root;

const now = new Date();
const leadId = 'SL-' + now.getTime().toString(36).toUpperCase();

const firstName = (body.first_name || body.firstName || '').trim();
const lastName = (body.last_name || body.lastName || '').trim();
const fullName = (body.name || (firstName + ' ' + lastName).trim() || '').trim();
const givenName = firstName || (fullName.split(' ')[0] || 'there');

const rawEmail = String(body.email || '').trim();
const rawPhone = String(body.phone || '').trim();

// Light E.164-ish phone normalization — keep only digits and a leading +.
const digitsOnly = rawPhone.replace(/[^\d+]/g, '');
let phone = digitsOnly;
if (phone && !phone.startsWith('+')) {
  // Treat leading zero as local South African and swap to +27.
  if (phone.startsWith('0')) {
    phone = '+27' + phone.slice(1);
  } else {
    phone = '+' + phone;
  }
}

const company = (body.company || '').trim();
const message = (body.message || body.notes || '').trim();

const smsBody = "Hi " + givenName + ", this is Ian from AnyVision Media. "
              + "Got your enquiry — can I call you in 10 min, or is WhatsApp easier?";

const emailSubject = "Got your enquiry, " + givenName + " — quick next steps";
const emailHtml = (
  '<div style="font-family:Arial,sans-serif;max-width:600px;">'
  + '<p>Hi ' + givenName + ',</p>'
  + '<p>Thanks for reaching out — I\'ve got your enquiry and will be in touch '
  + 'personally within the hour.</p>'
  + '<p>If it\'s urgent, reply to this email or WhatsApp me on the number '
  + 'you just gave us and I\'ll jump the queue.</p>'
  + '<p>\u2014 Ian<br>AnyVision Media</p>'
  + '<p style="color:#999;font-size:12px;">Ref: ' + leadId + '</p>'
  + '</div>'
);

return [{
  json: {
    'Lead ID': leadId,
    'Contact Name': fullName,
    'Email': rawEmail,
    'Phone': phone,
    'Company': company,
    'Source Channel': 'Organic',
    'Source URL': body.page_url || '',
    'UTM Source': body.utm_source || '',
    'UTM Medium': body.utm_medium || '',
    'UTM Campaign': body.utm_campaign || '',
    'First Touch Content': body.interest || '',
    'Notes': message,
    'Status': 'New',
    'Source System': 'SEO_Inbound',
    'Grade': 'Warm',
    'Created At': now.toISOString().slice(0, 10),
    _sms_body: smsBody,
    _email_subject: emailSubject,
    _email_html: emailHtml,
    _given_name: givenName,
  }
}];
"""


def build_speed_to_lead() -> dict[str, Any]:
    """Assemble the 5-Minute Lead Responder workflow."""

    webhook = webhook_node(
        name="Webhook",
        path="demo/speed-to-lead",
        position=[240, 320],
    )
    format_lead = code_node(
        name="Format Lead",
        js=SL_FORMAT_LEAD_JS,
        position=[460, 320],
    )

    lead_columns = [
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
    save_lead = airtable_create_node(
        name="Save Lead",
        table_id=LEAD_TABLE_ID,
        source_node="Format Lead",
        columns=lead_columns,
        position=[700, 160],
    )

    sms_lead = twilio_whatsapp_node(
        name="WhatsApp the Lead",
        to_expr="={{ $('Format Lead').first().json['Phone'] }}",
        message_expr="={{ $('Format Lead').first().json._sms_body }}",
        position=[700, 320],
    )

    reply_email = {
        "id": uid(),
        "name": "Auto-Reply to Lead",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [700, 480],
        "parameters": {
            "resource": "message",
            "operation": "send",
            "sendTo": "={{ $('Format Lead').first().json['Email'] }}",
            "subject": "={{ $('Format Lead').first().json._email_subject }}",
            "emailType": "html",
            "message": "={{ $('Format Lead').first().json._email_html }}",
            "options": {},
        },
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    }

    alert_owner = telegram_alert_node(
        name="Alert Owner",
        text_expr=(
            "=<b>NEW LEAD</b> \U0001F525\n"
            "Name: {{ $('Format Lead').first().json['Contact Name'] }}\n"
            "Email: {{ $('Format Lead').first().json['Email'] }}\n"
            "Phone: {{ $('Format Lead').first().json['Phone'] }}\n"
            "Company: {{ $('Format Lead').first().json['Company'] }}\n"
            "Msg: {{ $('Format Lead').first().json['Notes'] }}"
        ),
        position=[700, 640],
    )

    respond = respond_node("Respond Success", [960, 320])

    nodes = [webhook, format_lead, save_lead, sms_lead, reply_email, alert_owner, respond]

    connections = {
        webhook["name"]: {"main": [[{"node": format_lead["name"], "type": "main", "index": 0}]]},
        format_lead["name"]: {
            "main": [
                [
                    {"node": save_lead["name"], "type": "main", "index": 0},
                    {"node": sms_lead["name"], "type": "main", "index": 0},
                    {"node": reply_email["name"], "type": "main", "index": 0},
                    {"node": alert_owner["name"], "type": "main", "index": 0},
                ]
            ]
        },
        save_lead["name"]: {"main": [[{"node": respond["name"], "type": "main", "index": 0}]]},
    }

    return workflow_envelope(
        name=WORKFLOW_BUILDERS["speed_to_lead"]["name"],
        nodes=nodes,
        connections=connections,
        tags=["demo", "lead-capture", "webhook"],
    )


# ============================================================================
# WORKFLOW 2 — INBOX AUTOPILOT
# ============================================================================

IA_SYSTEM_MESSAGE = (
    "You are an email triage assistant for a solo business owner at AnyVision "
    "Media. For each incoming email, classify it into exactly one of the "
    "following categories:\n\n"
    "- URGENT: immediate attention needed (server down, upset client, hot deal "
    "closing, time-sensitive bank/legal notice)\n"
    "- CLIENT: existing client or project communication (not urgent)\n"
    "- SALES: a prospect reaching out, cold pitch from a vendor that could "
    "matter, or a reply in an ongoing sales conversation\n"
    "- BILLING: invoices, receipts, payment confirmations, statements\n"
    "- NOISE: newsletters, marketing, LinkedIn/social notifications, shipping "
    "updates, automated system mail\n\n"
    "Respond with a JSON object ONLY. No prose, no markdown, no code fences. "
    "Schema:\n"
    '{\n'
    '  "category": "URGENT|CLIENT|SALES|BILLING|NOISE",\n'
    '  "summary": "one-line summary <= 120 chars",\n'
    '  "suggested_reply": "plain-text reply suitable as a draft (empty string '
    'if category is URGENT, BILLING, or NOISE)"\n'
    '}'
)


def build_ia_prepare_js() -> str:
    """Prepare Email Data JS with AUTOMATION_SENDERS baked in (n8n Cloud blocks $env)."""
    senders = [s.strip().lower() for s in AUTOMATION_SENDERS.split(",") if s.strip()]
    senders_literal = json.dumps(senders)
    return (
        """
// Prepare email data for classification. Skip automation senders so we never
// classify our own outbound mail (prevents reply-to-self loops).
const AUTOMATION_SENDERS = """ + senders_literal + r""";
const msg = $input.first().json || {};

// n8n Gmail Trigger v1.3 outputs header fields with capital-case keys
// (From, Subject, To). Check capital first, then fall back to lowercase
// for manual/test payloads.
const rawFrom = String(
  msg.From || msg.from || (msg.headers && (msg.headers.From || msg.headers.from)) || ''
).toLowerCase();
const bareMatch = rawFrom.match(/<([^>]+)>/);
const bareFrom = (bareMatch ? bareMatch[1] : rawFrom).trim();

const subject = String(
  msg.Subject || msg.subject || (msg.headers && (msg.headers.Subject || msg.headers.subject)) || ''
).trim();
const snippet = String(msg.snippet || msg.text || msg.textPlain || '').trim().slice(0, 2000);
const messageId = msg.id || (msg.headers && msg.headers['message-id']) || '';
const threadId = msg.threadId || '';

const isAutomation = AUTOMATION_SENDERS.some(s => bareFrom.includes(s));

const prompt = (
  'FROM: ' + bareFrom + '\n'
  + 'SUBJECT: ' + subject + '\n\n'
  + 'BODY:\n' + snippet + '\n\n'
  + 'Return JSON only.'
);

return [{
  json: {
    original_message_id: messageId,
    thread_id: threadId,
    from: bareFrom,
    subject: subject,
    snippet: snippet,
    is_automation_sender: isAutomation,
    classificationPrompt: prompt,
  }
}];
"""
    )


IA_PARSE_RESPONSE_JS = r"""
// Parse the JSON out of the AI Agent response.
const input = $input.first().json || {};
let raw = input.output || input.text || input.content || input.message || '';

// The agent sometimes wraps JSON in ```json fences; strip them.
raw = String(raw).trim()
  .replace(/^```(?:json)?\s*/i, '')
  .replace(/\s*```\s*$/i, '')
  .trim();

let parsed = { category: 'NOISE', summary: '', suggested_reply: '' };
try {
  parsed = JSON.parse(raw);
} catch (e) {
  // Fallback: crude category sniff so we never hard-fail.
  const upper = raw.toUpperCase();
  if (upper.includes('URGENT')) parsed.category = 'URGENT';
  else if (upper.includes('CLIENT')) parsed.category = 'CLIENT';
  else if (upper.includes('SALES')) parsed.category = 'SALES';
  else if (upper.includes('BILLING')) parsed.category = 'BILLING';
  parsed.summary = raw.slice(0, 120);
  parsed.suggested_reply = '';
}

const prep = $('Prepare Email Data').first().json;
const category = String(parsed.category || 'NOISE').toUpperCase();
const now = new Date();

return [{
  json: {
    'Log ID': 'IA-' + now.getTime().toString(36).toUpperCase(),
    'Message ID': prep.original_message_id,
    'From': prep.from,
    'Subject': prep.subject,
    'Category': category,
    'Summary': String(parsed.summary || '').slice(0, 500),
    'Suggested Reply': String(parsed.suggested_reply || '').slice(0, 2000),
    'Urgent Flagged': category === 'URGENT',
    'Processed At': now.toISOString(),
    _thread_id: prep.thread_id,
    _action: '', // filled by the category branch
  }
}];
"""


def build_inbox_autopilot() -> dict[str, Any]:
    """Assemble the Inbox Autopilot workflow."""

    gmail_trigger = {
        "id": uid(),
        "name": "Gmail Trigger",
        "type": "n8n-nodes-base.gmailTrigger",
        "typeVersion": 1.3,
        "position": [200, 400],
        "parameters": {
            "filters": {"readStatus": "unread"},
            "options": {},
        },
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    }

    prepare = code_node(
        name="Prepare Email Data",
        js=build_ia_prepare_js(),
        position=[440, 400],
    )
    is_auto = if_node(
        name="Skip Automation?",
        expr="={{ $json.is_automation_sender ? 'yes' : '' }}",
        position=[660, 400],
    )
    skip_noop = {
        "id": uid(),
        "name": "Skip (Own Email)",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [660, 600],
        "parameters": {},
    }

    ai_agent = {
        "id": uid(),
        "name": "AI Agent",
        "type": "@n8n/n8n-nodes-langchain.agent",
        "typeVersion": 3.1,
        "position": [880, 400],
        "parameters": {
            "promptType": "define",
            "text": "={{ $json.classificationPrompt }}",
            "options": {
                "systemMessage": IA_SYSTEM_MESSAGE,
                "maxIterations": 1,
                "returnIntermediateSteps": False,
            },
        },
    }
    chat_model = {
        "id": uid(),
        "name": "OpenRouter Chat Model",
        "type": "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
        "typeVersion": 1,
        "position": [880, 600],
        "parameters": {
            "model": "anthropic/claude-sonnet-4",
            "options": {"temperature": 0.2},
        },
        "credentials": {"openRouterApi": CRED_OPENROUTER},
    }

    parse = code_node(
        name="Parse AI Response",
        js=IA_PARSE_RESPONSE_JS,
        position=[1120, 400],
    )

    # Switch by category (v3.4 uses rules.values and supports outputKey).
    switch_categories = [
        ("URGENT", "Urgent"),
        ("CLIENT", "Client"),
        ("SALES", "Sales"),
        ("BILLING", "Billing"),
        ("NOISE", "Noise"),
    ]
    switch_rules = []
    for category_value, output_key in switch_categories:
        switch_rules.append(
            {
                "outputKey": output_key,
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict",
                    },
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": uid(),
                            "leftValue": "={{ $json.Category }}",
                            "rightValue": category_value,
                            "operator": {
                                "type": "string",
                                "operation": "equals",
                            },
                        }
                    ],
                },
            }
        )
    switch_node = {
        "id": uid(),
        "name": "Route by Category",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.4,
        "position": [1360, 400],
        "parameters": {
            "rules": {"values": switch_rules},
            "options": {"fallbackOutput": "extra"},
        },
    }

    # URGENT: star the message (addLabels STARRED) + alert owner.
    star_urgent = {
        "id": uid(),
        "name": "Star Urgent",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1600, 80],
        "parameters": {
            "resource": "message",
            "operation": "addLabels",
            "messageId": "={{ $json['Message ID'] }}",
            "labelIds": ["STARRED"],
        },
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    }
    urgent_telegram = telegram_alert_node(
        name="Alert Owner (Urgent)",
        text_expr=(
            "=<b>\u26a0\ufe0f URGENT email</b>\n"
            "From: {{ $json['From'] }}\n"
            "Subject: {{ $json['Subject'] }}\n"
            "{{ $json['Summary'] }}"
        ),
        position=[1600, 240],
    )

    # CLIENT / SALES: create Gmail draft reply in the thread.
    draft_client = {
        "id": uid(),
        "name": "Draft Reply (Client)",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1600, 400],
        "parameters": {
            "resource": "draft",
            "operation": "create",
            "subject": "=Re: {{ $json['Subject'] }}",
            "emailType": "text",
            "message": "={{ $json['Suggested Reply'] }}",
            "options": {
                "threadId": "={{ $json._thread_id }}",
                "sendTo": "={{ $json['From'] }}",
            },
        },
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    }
    draft_sales = {
        "id": uid(),
        "name": "Draft Reply (Sales)",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1600, 560],
        "parameters": {
            "resource": "draft",
            "operation": "create",
            "subject": "=Re: {{ $json['Subject'] }}",
            "emailType": "text",
            "message": "={{ $json['Suggested Reply'] }}",
            "options": {
                "threadId": "={{ $json._thread_id }}",
                "sendTo": "={{ $json['From'] }}",
            },
        },
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    }

    # BILLING: just log (no Gmail action).
    billing_noop = {
        "id": uid(),
        "name": "Billing (Log Only)",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [1600, 720],
        "parameters": {},
    }

    # NOISE: archive (remove INBOX label + mark read).
    archive_noise = {
        "id": uid(),
        "name": "Archive Noise",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1600, 880],
        "parameters": {
            "resource": "message",
            "operation": "removeLabels",
            "messageId": "={{ $json['Message ID'] }}",
            "labelIds": ["INBOX", "UNREAD"],
        },
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    }

    # FALLBACK (extra output) — treat like noise.
    fallback_noop = {
        "id": uid(),
        "name": "Fallback (Log Only)",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [1600, 1040],
        "parameters": {},
    }

    # Set the Action string per branch before logging. Using Set nodes to keep
    # each branch independent; the Code node pattern would need branch-aware
    # state.
    def set_action(name: str, pos: list[int], action: str) -> dict[str, Any]:
        return {
            "id": uid(),
            "name": name,
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": pos,
            "parameters": {
                "mode": "manual",
                "duplicateItem": False,
                "assignments": {
                    "assignments": [
                        {
                            "id": uid(),
                            "name": "Action",
                            "value": action,
                            "type": "string",
                        }
                    ]
                },
                "includeOtherFields": True,
                "options": {},
            },
        }

    set_urgent = set_action("Set Action (Urgent)", [1840, 160], "Starred")
    set_client = set_action("Set Action (Client)", [1840, 400], "Draft Created")
    set_sales = set_action("Set Action (Sales)", [1840, 560], "Draft Created")
    set_billing = set_action("Set Action (Billing)", [1840, 720], "Logged Only")
    set_noise = set_action("Set Action (Noise)", [1840, 880], "Archived")
    set_fallback = set_action("Set Action (Fallback)", [1840, 1040], "Logged Only")

    # Single Airtable log node — all branches converge here.
    log_cols = [
        "Log ID",
        "Message ID",
        "From",
        "Subject",
        "Category",
        "Summary",
        "Suggested Reply",
        "Action",
        "Urgent Flagged",
        "Processed At",
    ]
    log_inbox = airtable_create_node(
        name="Log Email",
        table_id=IA_TABLE_ID,
        source_node="$node",  # placeholder — override below to use $json directly
        columns=log_cols,
        position=[2080, 560],
    )
    # Override: reference the current item's fields (each branch's Set node
    # passed Action through via includeOtherFields=true), so we need $json,
    # not $('Set Action (X)').
    log_value_map = {col: f"={{{{ $json['{col}'] }}}}" for col in log_cols}
    log_schema = [
        {
            "id": col,
            "type": "string",
            "display": True,
            "displayName": col,
            "required": False,
            "defaultMatch": False,
            "canBeUsedToMatch": True,
        }
        for col in log_cols
    ]
    log_inbox["parameters"]["columns"]["value"] = log_value_map
    log_inbox["parameters"]["columns"]["schema"] = log_schema

    nodes = [
        gmail_trigger,
        prepare,
        is_auto,
        skip_noop,
        ai_agent,
        chat_model,
        parse,
        switch_node,
        star_urgent,
        urgent_telegram,
        draft_client,
        draft_sales,
        billing_noop,
        archive_noise,
        fallback_noop,
        set_urgent,
        set_client,
        set_sales,
        set_billing,
        set_noise,
        set_fallback,
        log_inbox,
    ]

    connections = {
        gmail_trigger["name"]: {"main": [[{"node": prepare["name"], "type": "main", "index": 0}]]},
        prepare["name"]: {"main": [[{"node": is_auto["name"], "type": "main", "index": 0}]]},
        is_auto["name"]: {
            "main": [
                [{"node": skip_noop["name"], "type": "main", "index": 0}],
                [{"node": ai_agent["name"], "type": "main", "index": 0}],
            ]
        },
        ai_agent["name"]: {"main": [[{"node": parse["name"], "type": "main", "index": 0}]]},
        parse["name"]: {"main": [[{"node": switch_node["name"], "type": "main", "index": 0}]]},
        switch_node["name"]: {
            "main": [
                [  # URGENT -> star + telegram
                    {"node": star_urgent["name"], "type": "main", "index": 0},
                    {"node": urgent_telegram["name"], "type": "main", "index": 0},
                ],
                [{"node": draft_client["name"], "type": "main", "index": 0}],  # CLIENT
                [{"node": draft_sales["name"], "type": "main", "index": 0}],   # SALES
                [{"node": billing_noop["name"], "type": "main", "index": 0}],  # BILLING
                [{"node": archive_noise["name"], "type": "main", "index": 0}], # NOISE
                [{"node": fallback_noop["name"], "type": "main", "index": 0}], # extra
            ]
        },
        # OpenRouter Chat Model wires into the AI Agent as ai_languageModel.
        chat_model["name"]: {
            "ai_languageModel": [
                [{"node": ai_agent["name"], "type": "ai_languageModel", "index": 0}]
            ]
        },
        # Each branch -> its Set node -> Log Email (convergence).
        star_urgent["name"]: {"main": [[{"node": set_urgent["name"], "type": "main", "index": 0}]]},
        urgent_telegram["name"]: {"main": [[]]},  # fire-and-forget, don't double-log
        draft_client["name"]: {"main": [[{"node": set_client["name"], "type": "main", "index": 0}]]},
        draft_sales["name"]: {"main": [[{"node": set_sales["name"], "type": "main", "index": 0}]]},
        billing_noop["name"]: {"main": [[{"node": set_billing["name"], "type": "main", "index": 0}]]},
        archive_noise["name"]: {"main": [[{"node": set_noise["name"], "type": "main", "index": 0}]]},
        fallback_noop["name"]: {"main": [[{"node": set_fallback["name"], "type": "main", "index": 0}]]},

        set_urgent["name"]: {"main": [[{"node": log_inbox["name"], "type": "main", "index": 0}]]},
        set_client["name"]: {"main": [[{"node": log_inbox["name"], "type": "main", "index": 0}]]},
        set_sales["name"]: {"main": [[{"node": log_inbox["name"], "type": "main", "index": 0}]]},
        set_billing["name"]: {"main": [[{"node": log_inbox["name"], "type": "main", "index": 0}]]},
        set_noise["name"]: {"main": [[{"node": log_inbox["name"], "type": "main", "index": 0}]]},
        set_fallback["name"]: {"main": [[{"node": log_inbox["name"], "type": "main", "index": 0}]]},
    }

    return workflow_envelope(
        name=WORKFLOW_BUILDERS["inbox_autopilot"]["name"],
        nodes=nodes,
        connections=connections,
        tags=["demo", "gmail", "ai", "inbox-triage"],
    )


# ============================================================================
# DEPLOY HELPERS
# ============================================================================


def get_n8n_client():
    """Create N8nClient from env."""
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


def save_workflow(key: str, workflow_data: dict[str, Any]) -> Path:
    """Write built workflow JSON to workflows/demo-workflows/."""
    spec = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "demo-workflows"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_data, f, indent=2, ensure_ascii=False)
    node_count = len(workflow_data["nodes"])
    print(f"  + {spec['name']:<40} -> {output_path.name} ({node_count} nodes)")
    return output_path


def deploy_workflow(workflow_data: dict[str, Any]) -> dict[str, Any]:
    """POST to n8n to create the workflow (inactive).

    n8n cloud rejects both ``active`` and ``tags`` as read-only on POST, so
    we strip them from the create payload. Tags can be applied via the UI
    after creation.
    """
    client = get_n8n_client()
    body = dict(workflow_data)
    body.pop("active", None)
    body.pop("tags", None)
    return client.create_workflow(body)


def activate_workflow(workflow_id: str) -> dict[str, Any]:
    client = get_n8n_client()
    return client.activate_workflow(workflow_id)


# ============================================================================
# CLI
# ============================================================================

BUILDERS = {
    "missed_call": build_missed_call,
    "speed_to_lead": build_speed_to_lead,
    "inbox_autopilot": build_inbox_autopilot,
}


def print_preflight() -> None:
    """Print a checklist of env values required for runtime execution."""
    print("Preflight — runtime requirements:")
    checks: list[tuple[str, str]] = [
        ("SOCIAL_BUILDS_BASE_ID", DEMO_BASE_ID),
        ("DEMO_MCB_TABLE", MCB_TABLE_ID),
        ("DEMO_IA_TABLE", IA_TABLE_ID),
        ("DEMO_LEAD_TABLE", LEAD_TABLE_ID),
        ("TWILIO_WHATSAPP_FROM", TWILIO_WHATSAPP_FROM),
        ("TELEGRAM_OWNER_CHAT_ID", TELEGRAM_OWNER_CHAT_ID),
        ("AUTOMATION_SENDERS", AUTOMATION_SENDERS),
    ]
    for key, value in checks:
        bad = (
            not value
            or "PLACEHOLDER" in str(value)
            or value in ("+10000000000",)
        )
        mark = "WARN" if bad else "OK  "
        display = value if value and "PLACEHOLDER" not in str(value) else "<not set>"
        print(f"  [{mark}] {key:<32} {display}")
    print()


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("build", "deploy", "activate"):
        print("Usage: python tools/deploy_demo_workflows.py <build|deploy|activate>")
        print()
        print("Actions:")
        print("  build     Build workflow JSONs to workflows/demo-workflows/")
        print("  deploy    Build + deploy to n8n (inactive)")
        print("  activate  Build + deploy + activate")
        print()
        print("Workflows:")
        for key, spec in WORKFLOW_BUILDERS.items():
            print(f"  {key:<20} {spec['name']}")
        sys.exit(1)

    action = args[0]

    print("=" * 62)
    print("AVM DEMO WORKFLOWS — BUILDER & DEPLOYER")
    print("=" * 62)
    print(f"Action:   {action}")
    print(f"Base:     {DEMO_BASE_ID}")
    print()
    print_preflight()

    print("Building workflows...")
    print("-" * 40)
    built: dict[str, dict[str, Any]] = {}
    for key, builder_fn in BUILDERS.items():
        workflow = builder_fn()
        save_workflow(key, workflow)
        built[key] = workflow
    print()

    if action == "build":
        print("Build complete. Run 'deploy' to push to n8n (inactive).")
        return

    print("Deploying to n8n (inactive)...")
    print("-" * 40)
    deployed_ids: dict[str, str] = {}
    for key, workflow in built.items():
        try:
            resp = deploy_workflow(workflow)
            wf_id = resp.get("id", "unknown")
            deployed_ids[key] = wf_id
            print(f"  + {WORKFLOW_BUILDERS[key]['name']:<40} -> {wf_id}")
        except Exception as e:
            print(f"  - {WORKFLOW_BUILDERS[key]['name']:<40} FAILED: {e}")
    print()

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

    if deployed_ids:
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "demo_workflows_ids.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "deployed": deployed_ids,
                    "deployed_at": datetime.now().isoformat(),
                    "webhook_base": os.getenv(
                        "N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud"
                    ),
                },
                f,
                indent=2,
            )
        print(f"Workflow IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Open each workflow in n8n UI and visually verify wiring")
    print("  2. Confirm TWILIO_WHATSAPP_FROM is your Twilio sandbox number")
    print("     and the receiving phone has texted the sandbox join code")
    print("  3. Smoke test Missed Call:")
    print("       curl -X POST $N8N_BASE_URL/webhook/demo/missed-call \\")
    print('         -H "Content-Type: application/x-www-form-urlencoded" \\')
    print('         -d "From=+27821234567&To=+27109876543&CallStatus=no-answer"')
    print("  4. Smoke test Speed-to-Lead:")
    print("       curl -X POST $N8N_BASE_URL/webhook/demo/speed-to-lead \\")
    print('         -H "Content-Type: application/json" \\')
    print('         -d \'{"name":"Test","email":"you@test.com","phone":"0821234567","message":"hello"}\'')
    print("  5. For Inbox Autopilot: activate, send yourself an unread email, watch execution")


if __name__ == "__main__":
    main()
