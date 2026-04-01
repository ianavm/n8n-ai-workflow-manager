"""
Order-to-Invoice WhatsApp Automation - Workflow Builder & Deployer

Builds and deploys two n8n workflows for WhatsApp-driven order intake
and management approval with Xero quoting/invoicing.

Workflows:
    ORD-01: WhatsApp Order Intake (~38 nodes)
        - Receives customer WhatsApp messages
        - Guides through category -> size -> quantity menu flow
        - Creates Xero draft quote, sends PDF to management for approval

    ORD-02: Approval Handler (~27 nodes)
        - Receives management approve/reject via WhatsApp
        - Converts approved quotes to Xero invoices
        - AI-parses rejection feedback to revise quotes
        - Sends invoice PDF to customer

Usage:
    python tools/deploy_order_to_invoice.py build
    python tools/deploy_order_to_invoice.py build ord01
    python tools/deploy_order_to_invoice.py deploy
    python tools/deploy_order_to_invoice.py activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# ── Credential Constants ────────────────────────────────────
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_WHATSAPP_TRIGGER = {"id": "rUyqIX1gaBs3ae6Q", "name": "WhatsApp Trigger"}
CRED_WHATSAPP_SEND = {"id": "dCAz6MBXpOXvMJrq", "name": "WhatsApp Business Send"}
CRED_XERO = {"id": os.getenv("XERO_CRED_ID", "REPLACE_AFTER_SETUP"), "name": "Xero OAuth2"}

# ── Airtable + Config ──────────────────────────────────────
ORDER_BASE_ID = os.getenv("ORDER_AIRTABLE_BASE_ID", "app2ALQUP7CKEkHOz")
TABLE_SESSIONS = os.getenv("ORDER_TABLE_SESSIONS", "REPLACE_AFTER_SETUP")
TABLE_PRODUCTS = os.getenv("ORDER_TABLE_PRODUCTS", "REPLACE_AFTER_SETUP")
XERO_TENANT_ID = os.getenv("XERO_TENANT_ID", "REPLACE")
MGMT_PHONE = os.getenv("ORDER_MGMT_PHONE", "REPLACE")
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "REPLACE")


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

PARSE_MESSAGE_CODE = r"""
// Parse incoming WhatsApp message
const body = $input.first().json.body || $input.first().json;
const entry = body.entry?.[0];
const changes = entry?.changes?.[0];
const value = changes?.value;
const message = value?.messages?.[0];
const contact = value?.contacts?.[0];

if (!message) {
  return { json: { parseSuccess: false, reason: 'No message in payload' } };
}

const from = message.from;
const profileName = contact?.profile?.name || 'Unknown';
const phoneNumberId = value?.metadata?.phone_number_id || '';
const timestamp = message.timestamp;

let messageBody = '';
let messageType = message.type || 'text';
let interactiveReply = null;

if (messageType === 'text') {
  messageBody = message.text?.body || '';
} else if (messageType === 'interactive') {
  const interactive = message.interactive;
  if (interactive?.type === 'list_reply') {
    interactiveReply = { type: 'list_reply', id: interactive.list_reply.id, title: interactive.list_reply.title };
    messageBody = interactive.list_reply.title;
  } else if (interactive?.type === 'button_reply') {
    interactiveReply = { type: 'button_reply', id: interactive.button_reply.id, title: interactive.button_reply.title };
    messageBody = interactive.button_reply.title;
  }
}

return {
  json: {
    parseSuccess: true,
    from,
    profileName,
    phoneNumberId,
    timestamp,
    messageBody,
    messageType,
    interactiveReply,
    rawMessageId: message.id
  }
};
"""

WORKING_HOURS_CODE = r"""
const now = new Date();
const tz = 'Africa/Johannesburg';
const timeStr = now.toLocaleTimeString('en-GB', { timeZone: tz, hour12: false });
const dayOfWeek = now.toLocaleDateString('en-US', { timeZone: tz, weekday: 'short' });
const dayMap = { 'Mon': 1, 'Tue': 2, 'Wed': 3, 'Thu': 4, 'Fri': 5, 'Sat': 6, 'Sun': 0 };
const currentDay = dayMap[dayOfWeek] || 0;
const currentMinutes = parseInt(timeStr.split(':')[0]) * 60 + parseInt(timeStr.split(':')[1]);

let withinWorkingHours = false;
if (currentDay >= 1 && currentDay <= 5) {
  withinWorkingHours = currentMinutes >= 600 && currentMinutes < 1080;
} else if (currentDay === 6) {
  withinWorkingHours = currentMinutes >= 600 && currentMinutes < 960;
}

return { json: { ...$input.first().json, withinWorkingHours } };
"""

PROCESS_CATEGORY_CODE = r"""
const input = $input.first().json;
const reply = input.interactiveReply;
if (!reply || reply.type !== 'list_reply') {
  return { json: { ...input, parseError: 'Expected list reply for category' } };
}
const categoryMap = {
  'cat_polymailers': 'Polymailers',
  'cat_boxes': 'Boxes',
  'cat_tapes': 'Tapes'
};
const selectedCategory = categoryMap[reply.id] || reply.title;
return { json: { ...input, selectedCategory } };
"""

PROCESS_SIZE_CODE = r"""
const input = $input.first().json;
const reply = input.interactiveReply;
if (!reply || reply.type !== 'button_reply') {
  return { json: { ...input, parseError: 'Expected button reply for size' } };
}
const selectedSize = reply.title;
const sizeId = reply.id;
return { json: { ...input, selectedSize, sizeId } };
"""

PROCESS_QUANTITY_CODE = r"""
const input = $input.first().json;
const text = (input.messageBody || '').trim();
const qty = parseInt(text, 10);
if (isNaN(qty) || qty <= 0 || qty > 100000) {
  return { json: { ...input, quantityError: true, errorMsg: 'Please enter a valid quantity (1-100,000)' } };
}
return { json: { ...input, selectedQuantity: qty, quantityError: false } };
"""

PARSE_AI_MAPPING_CODE = r"""
const input = $input.first().json;
const aiResponse = input.choices?.[0]?.message?.content || input.message?.content || '';
let parsed;
try {
  const cleaned = aiResponse.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  return { json: { ...input, mappingError: true, errorMsg: 'AI mapping parse failed: ' + e.message } };
}
return {
  json: {
    xeroItemCode: parsed.xero_item_code || parsed.itemCode || '',
    xeroContactId: parsed.xero_contact_id || parsed.contactId || '',
    unitPrice: parsed.unit_price || parsed.unitPrice || 0,
    description: parsed.description || '',
    mappingError: false
  }
};
"""

PARSE_QUOTE_RESPONSE_CODE = r"""
const input = $input.first().json;
const quotes = input.Quotes || [input];
const quote = quotes[0] || input;
return {
  json: {
    quoteId: quote.QuoteID || '',
    quoteNumber: quote.QuoteNumber || '',
    total: quote.Total || 0,
    subtotal: quote.SubTotal || 0,
    taxTotal: quote.TotalTax || 0,
    status: quote.Status || 'DRAFT',
    contactName: quote.Contact?.Name || ''
  }
};
"""

RENAME_PDF_CODE = r"""
const input = $input.first();
const quoteNumber = $('Parse Quote Response').first().json.quoteNumber || 'Unknown';
if (input.binary && input.binary.data) {
  input.binary.data.fileName = 'Quote_' + quoteNumber + '.pdf';
}
return input;
"""

BUILD_APPROVAL_MSG_CODE = r"""
const session = $('Update Session Quote').first().json;
const quote = $('Parse Quote Response').first().json;
const msg = $('Parse Message').first().json;
const text = [
  '*New Order Quote*',
  '',
  'Customer: ' + (msg.profileName || 'Unknown'),
  'Phone: ' + (msg.from || ''),
  'Quote: ' + (quote.quoteNumber || ''),
  '',
  'Category: ' + (session.Selected_Category || session.selectedCategory || ''),
  'Size: ' + (session.Selected_Size || session.selectedSize || ''),
  'Quantity: ' + (session.Selected_Quantity || session.selectedQuantity || ''),
  'Total: R' + (quote.total || 0).toFixed(2),
  '',
  'Reply *APPROVE* to convert to invoice',
  'Reply *REJECT [reason]* to request changes',
].join('\n');

return { json: { approvalText: text, quoteNumber: quote.quoteNumber } };
"""

PARSE_DECISION_CODE = r"""
const input = $input.first().json;
const text = (input.messageBody || '').trim().toUpperCase();

let decision = 'vague';
let feedback = '';

if (text === 'APPROVE' || text === 'YES' || text === 'APPROVED' || text.startsWith('APPROVE')) {
  decision = 'approve';
} else if (text.startsWith('REJECT') || text.startsWith('NO ') || text === 'NO') {
  decision = 'reject';
  feedback = text.replace(/^(REJECT|NO)\s*/i, '').trim();
  if (!feedback) decision = 'vague';
}

return { json: { ...input, decision, feedback } };
"""

PARSE_INVOICE_RESPONSE_CODE = r"""
const input = $input.first().json;
const invoices = input.Invoices || [input];
const invoice = invoices[0] || input;
return {
  json: {
    invoiceId: invoice.InvoiceID || '',
    invoiceNumber: invoice.InvoiceNumber || '',
    total: invoice.Total || 0,
    status: invoice.Status || '',
    contactName: invoice.Contact?.Name || ''
  }
};
"""

RENAME_INVOICE_PDF_CODE = r"""
const input = $input.first();
const invoiceNumber = $('Parse Invoice Response').first().json.invoiceNumber || 'Unknown';
if (input.binary && input.binary.data) {
  input.binary.data.fileName = 'Invoice_' + invoiceNumber + '.pdf';
}
return input;
"""

PARSE_AI_FEEDBACK_CODE = r"""
const input = $input.first().json;
const aiResponse = input.choices?.[0]?.message?.content || '';
let parsed;
try {
  const cleaned = aiResponse.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  return { json: { action: 'unclear', errorMsg: 'Could not parse AI feedback: ' + e.message } };
}
return {
  json: {
    action: parsed.action || 'unclear',
    newQuantity: parsed.new_quantity || null,
    newPrice: parsed.new_price || null,
    newItemCode: parsed.new_item_code || null,
    explanation: parsed.explanation || 'Changes applied based on feedback'
  }
};
"""

LOG_PARSE_ERROR_CODE = r"""
// Terminal node - log parse error for debugging
const input = $input.first().json;
return {
  json: {
    logged: true,
    error: 'Message parse failed',
    reason: input.reason || 'Unknown',
    timestamp: new Date().toISOString()
  }
};
"""

LOG_AFTER_HOURS_CODE = r"""
// Terminal node - log after-hours message
const input = $input.first().json;
return {
  json: {
    logged: true,
    event: 'after_hours_message',
    from: input.from || '',
    messageBody: input.messageBody || '',
    timestamp: new Date().toISOString()
  }
};
"""

HANDLE_ERROR_CODE = r"""
// Global error handler
const error = $input.first().json;
return {
  json: {
    errorHandled: true,
    workflow: error.workflow?.name || 'Unknown',
    node: error.execution?.lastNodeExecuted || 'Unknown',
    message: error.execution?.error?.message || 'Unknown error',
    timestamp: new Date().toISOString()
  }
};
"""


# ======================================================================
# NODE BUILDER HELPERS
# ======================================================================

def build_whatsapp_trigger(name, position):
    """Build WhatsApp Trigger node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.whatsAppTrigger",
        "typeVersion": 1,
        "position": position,
        "webhookId": uid(),
        "parameters": {"updates": ["messages"]},
        "credentials": {"whatsAppTriggerApi": CRED_WHATSAPP_TRIGGER},
    }


def build_manual_trigger(name, position):
    """Build Manual Trigger node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": position,
        "parameters": {},
    }


def build_code_node(name, code, position, always_output=False):
    """Build Code node (v2)."""
    node = {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {
            "jsCode": code,
            "mode": "runOnceForAllItems",
        },
    }
    if always_output:
        node["alwaysOutputData"] = True
    return node


def build_if_node(name, condition_expr, position, negate=False):
    """Build If node (n8n v2.2 compatible).

    Uses unary boolean check with singleValue: True.
    """
    operation = "false" if negate else "true"
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "leftValue": condition_expr,
                        "operator": {
                            "type": "boolean",
                            "operation": operation,
                            "singleValue": True,
                        },
                    }
                ],
            },
        },
    }


def build_if_string_node(name, left_value, operation, right_value, position):
    """Build If node with string comparison (n8n v2.2 compatible)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "leftValue": left_value,
                        "rightValue": right_value,
                        "operator": {
                            "type": "string",
                            "operation": operation,
                        },
                    }
                ],
            },
        },
    }


def build_if_number_node(name, left_value, operation, right_value, position):
    """Build If node with number comparison (n8n v2.2 compatible)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": position,
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "leftValue": left_value,
                        "rightValue": right_value,
                        "operator": {
                            "type": "number",
                            "operation": operation,
                        },
                    }
                ],
            },
        },
    }


def build_switch_node(name, field_expr, rules, position, fallback_output=None):
    """Build Switch v3.2 node.

    rules: list of string values to match against field_expr.
    Each value gets its own output (0, 1, 2, ...).
    """
    values = []
    for rule_value in rules:
        values.append({
            "conditions": {
                "conditions": [
                    {
                        "leftValue": field_expr,
                        "rightValue": rule_value,
                        "operator": {"type": "string", "operation": "equals"},
                    }
                ],
            },
        })

    node = {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": position,
        "parameters": {
            "rules": {"values": values},
        },
    }
    if fallback_output is not None:
        node["parameters"]["options"] = {"fallbackOutput": fallback_output}
    return node


def build_http_request(name, method, url, position, body=None, headers=None,
                       response_format="json", credential=None):
    """Build HTTP Request node (v4.2)."""
    params = {
        "method": method,
        "url": url,
        "options": {"timeout": 30000},
    }
    if body:
        params["sendBody"] = True
        params["specifyBody"] = "json"
        params["jsonBody"] = body
    if headers:
        params["sendHeaders"] = True
        params["headerParameters"] = {"parameters": headers}
    if response_format == "file":
        params["options"]["response"] = {"response": {"responseFormat": "file"}}

    node = {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "parameters": params,
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    }
    if credential:
        node["credentials"] = credential
    return node


def build_airtable_search(name, table_id, filter_formula, position, always_output=True):
    """Build Airtable search node (v2.1)."""
    node = {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": position,
        "parameters": {
            "operation": "search",
            "application": ORDER_BASE_ID,
            "table": table_id,
            "filterByFormula": filter_formula,
            "options": {},
        },
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    }
    if always_output:
        node["alwaysOutputData"] = True
    return node


def build_airtable_create(name, table_id, fields_expr, position):
    """Build Airtable create node (v2.1). NEVER includes matchingColumns.

    CRITICAL: The ``columns`` parameter with ``mappingMode`` is REQUIRED for
    Airtable v2.1 create.  Without it the API request body has no ``fields``
    key and Airtable returns "Could not find field 'fields'".
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": position,
        "parameters": {
            "operation": "create",
            "application": ORDER_BASE_ID,
            "table": table_id,
            "columns": {
                "mappingMode": "defineBelow",
                "value": fields_expr,
            },
            "options": {},
        },
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    }


def build_airtable_update(name, table_id, fields_expr, matching_column, position):
    """Build Airtable update node (v2.1). Uses matchingColumns."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": position,
        "parameters": {
            "operation": "update",
            "application": ORDER_BASE_ID,
            "table": table_id,
            "columns": {"value": fields_expr},
            "matchingColumns": [matching_column],
            "options": {},
        },
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    }


def build_whatsapp_text(name, to_expr, text_expr, position):
    """Send WhatsApp text message via Meta Graph API HTTP Request."""
    body = json.dumps({
        "messaging_product": "whatsapp",
        "to": to_expr,
        "type": "text",
        "text": {"body": text_expr}
    })
    return build_http_request(
        name=name,
        method="POST",
        url=f"=https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        position=position,
        body=body,
        headers=[
            {"name": "Authorization", "value": "=Bearer {{ $env.WHATSAPP_ACCESS_TOKEN }}"},
            {"name": "Content-Type", "value": "application/json"},
        ],
    )


def build_whatsapp_list(name, to_expr, header_text, body_text, button_text,
                        sections, position):
    """Send WhatsApp interactive list message via Meta Graph API."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to_expr,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header_text},
            "body": {"text": body_text},
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
    }
    return build_http_request(
        name=name,
        method="POST",
        url=f"=https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        position=position,
        body=json.dumps(payload),
        headers=[
            {"name": "Authorization", "value": "=Bearer {{ $env.WHATSAPP_ACCESS_TOKEN }}"},
            {"name": "Content-Type", "value": "application/json"},
        ],
    )


def build_whatsapp_buttons(name, to_expr, body_text, buttons, position):
    """Send WhatsApp interactive reply buttons via Meta Graph API."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to_expr,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": buttons
            }
        }
    }
    return build_http_request(
        name=name,
        method="POST",
        url=f"=https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        position=position,
        body=json.dumps(payload),
        headers=[
            {"name": "Authorization", "value": "=Bearer {{ $env.WHATSAPP_ACCESS_TOKEN }}"},
            {"name": "Content-Type", "value": "application/json"},
        ],
    )


def build_whatsapp_document(name, to_expr, document_link, caption, position):
    """Send WhatsApp document (PDF) via Meta Graph API."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to_expr,
        "type": "document",
        "document": {
            "link": document_link,
            "caption": caption
        }
    }
    return build_http_request(
        name=name,
        method="POST",
        url=f"=https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        position=position,
        body=json.dumps(payload),
        headers=[
            {"name": "Authorization", "value": "=Bearer {{ $env.WHATSAPP_ACCESS_TOKEN }}"},
            {"name": "Content-Type", "value": "application/json"},
        ],
    )


def build_openrouter_request(name, system_prompt, user_prompt_expr, position):
    """Build HTTP Request to OpenRouter for AI processing."""
    body = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt_expr}
        ],
        "temperature": 0.2,
        "max_tokens": 1000,
    })
    return build_http_request(
        name=name,
        method="POST",
        url="https://openrouter.ai/api/v1/chat/completions",
        position=position,
        body=body,
        headers=[
            {"name": "Authorization", "value": "=Bearer {{ $env.OPENROUTER_API_KEY }}"},
            {"name": "Content-Type", "value": "application/json"},
        ],
    )


def build_xero_request(name, method, endpoint, position, body=None,
                        accept="application/json", response_format="json"):
    """Build HTTP Request to Xero API."""
    headers = [
        {"name": "Authorization", "value": "=Bearer {{ $credentials.xeroOAuth2Api.accessToken }}"},
        {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
        {"name": "Accept", "value": accept},
        {"name": "Content-Type", "value": "application/json"},
    ]
    return build_http_request(
        name=name,
        method=method,
        url=f"https://api.xero.com/api.xro/2.0/{endpoint}",
        position=position,
        body=json.dumps(body) if body else None,
        headers=headers,
        response_format=response_format,
        credential={"xeroOAuth2Api": CRED_XERO},
    )


def build_gmail_send(name, to, subject_expr, html_body_expr, position):
    """Build Gmail send node (v2.1)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": position,
        "parameters": {
            "sendTo": to,
            "subject": subject_expr,
            "emailType": "html",
            "message": html_body_expr,
            "options": {},
        },
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    }


def build_error_trigger(name, position):
    """Build Error Trigger node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": position,
        "parameters": {},
    }


def build_sticky_note(name, content, position, width=300, height=200):
    """Build Sticky Note node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": position,
        "parameters": {
            "content": content,
            "width": width,
            "height": height,
        },
    }


def build_no_op(name, position):
    """Build No Operation node (passthrough)."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": position,
        "parameters": {},
    }


# ======================================================================
# HELPER: Connection builder
# ======================================================================

def connect(nodes, from_name, to_name, from_output=0, to_input=0):
    """Create a connection entry between two named nodes.

    Returns a tuple (from_name, to_name, from_output, to_input) that
    can be collected and converted into n8n connection format.
    """
    return (from_name, to_name, from_output, to_input)


def build_connection_map(connections_list):
    """Convert a list of (from, to, from_output, to_input) tuples
    into n8n connections dict format."""
    conn_map = {}
    for from_name, to_name, from_output, to_input in connections_list:
        if from_name not in conn_map:
            conn_map[from_name] = {"main": []}
        main = conn_map[from_name]["main"]
        # Ensure we have enough output arrays
        while len(main) <= from_output:
            main.append([])
        main[from_output].append({
            "node": to_name,
            "type": "main",
            "index": to_input,
        })
    return conn_map


# ======================================================================
# ORD-01: WhatsApp Order Intake
# ======================================================================

def build_ord01_nodes():
    """Build all nodes for ORD-01: WhatsApp Order Intake."""
    nodes = []

    # ── Triggers ────────────────────────────────────────────
    nodes.append(build_whatsapp_trigger("WhatsApp Trigger", [200, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [200, 600]))

    # ── Parse & Validate ────────────────────────────────────
    nodes.append(build_code_node("Parse Message", PARSE_MESSAGE_CODE, [460, 500]))
    nodes.append(build_if_node("Valid?", "={{ $json.parseSuccess }}", [700, 500]))

    # ── Read Receipt (marks message as read) ────────────────
    read_receipt_body = json.dumps({
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "={{ $json.rawMessageId }}"
    })
    nodes.append(build_http_request(
        name="Send Read Receipt",
        method="POST",
        url=f"=https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        position=[940, 400],
        body=read_receipt_body,
        headers=[
            {"name": "Authorization", "value": "=Bearer {{ $env.WHATSAPP_ACCESS_TOKEN }}"},
            {"name": "Content-Type", "value": "application/json"},
        ],
    ))

    # ── Parse Error (false branch) ──────────────────────────
    nodes.append(build_code_node("Log Parse Error", LOG_PARSE_ERROR_CODE, [940, 700]))

    # ── Working Hours ───────────────────────────────────────
    nodes.append(build_code_node("Check Working Hours", WORKING_HOURS_CODE, [1180, 400]))
    nodes.append(build_if_node("Within Hours?", "={{ $json.withinWorkingHours }}", [1420, 400]))

    # ── After Hours Reply (false branch) ────────────────────
    nodes.append(build_whatsapp_text(
        name="Send After Hours Reply",
        to_expr="{{ $json.from }}",
        text_expr="Hi {{ $json.profileName }}! Our ordering hours are Mon-Fri 10:00-18:00 and Sat 10:00-16:00 (SAST). Please message us during business hours and we'll assist you promptly.",
        position=[1660, 600],
    ))
    nodes.append(build_code_node("Log After Hours", LOG_AFTER_HOURS_CODE, [1900, 600]))

    # ── Session Lookup ──────────────────────────────────────
    nodes.append(build_airtable_search(
        name="Find Active Session",
        table_id=TABLE_SESSIONS,
        filter_formula="=AND({Customer_Phone}='{{ $json.from }}', NOT(OR({State}='INVOICE_SENT', {State}='APPROVED', {State}='REJECTED')))",
        position=[1660, 300],
        always_output=True,
    ))

    nodes.append(build_if_string_node(
        name="Has Session?",
        left_value="={{ $json.Session_ID }}",
        operation="isNotEmpty",
        right_value="",
        position=[1900, 300],
    ))

    # ── Route by State (Switch) ─────────────────────────────
    nodes.append(build_switch_node(
        name="Route by State",
        field_expr="={{ $json.State }}",
        rules=["AWAITING_CATEGORY", "AWAITING_SIZE", "AWAITING_QUANTITY"],
        position=[2140, 200],
        fallback_output=3,
    ))

    # ── New Session (no active session found) ───────────────
    new_session_fields = json.dumps({
        "Session_ID": "={{ $('Parse Message').first().json.from }}_{{ DateTime.now().toFormat('yyyyMMddHHmmss') }}",
        "Customer_Phone": "={{ $('Parse Message').first().json.from }}",
        "Customer_Name": "={{ $('Parse Message').first().json.profileName }}",
        "State": "AWAITING_CATEGORY",
    })
    nodes.append(build_airtable_create(
        name="Create New Session",
        table_id=TABLE_SESSIONS,
        fields_expr=new_session_fields,
        position=[2140, 500],
    ))

    # ── Category Menu ───────────────────────────────────────
    category_sections = [
        {
            "title": "Product Categories",
            "rows": [
                {"id": "cat_polymailers", "title": "Polymailers", "description": "Poly mailer bags in various sizes"},
                {"id": "cat_boxes", "title": "Boxes", "description": "Shipping and packaging boxes"},
                {"id": "cat_tapes", "title": "Tapes", "description": "Packaging and sealing tapes"},
            ]
        }
    ]
    nodes.append(build_whatsapp_list(
        name="Send Category Menu",
        to_expr="{{ $('Parse Message').first().json.from }}",
        header_text="Product Categories",
        body_text="Welcome! Please select a product category to get started with your order.",
        button_text="Browse Products",
        sections=category_sections,
        position=[2380, 500],
    ))

    # ── Category Flow (Switch output 0: AWAITING_CATEGORY) ──
    nodes.append(build_code_node("Process Category Selection", PROCESS_CATEGORY_CODE, [2380, 100]))

    update_category_fields = json.dumps({
        "Session_ID": "={{ $json.Session_ID || $('Find Active Session').first().json.Session_ID }}",
        "Selected_Category": "={{ $json.selectedCategory }}",
        "State": "AWAITING_SIZE",
    })
    nodes.append(build_airtable_update(
        name="Update Session Category",
        table_id=TABLE_SESSIONS,
        fields_expr=update_category_fields,
        matching_column="Session_ID",
        position=[2620, 100],
    ))

    size_buttons = [
        {"type": "reply", "reply": {"id": "size_small", "title": "Small"}},
        {"type": "reply", "reply": {"id": "size_medium", "title": "Medium"}},
        {"type": "reply", "reply": {"id": "size_large", "title": "Large"}},
    ]
    nodes.append(build_whatsapp_buttons(
        name="Send Size Buttons",
        to_expr="{{ $('Parse Message').first().json.from }}",
        body_text="Great choice! Now select a size:",
        buttons=size_buttons,
        position=[2860, 100],
    ))

    # ── Size Flow (Switch output 1: AWAITING_SIZE) ──────────
    nodes.append(build_code_node("Process Size Selection", PROCESS_SIZE_CODE, [2380, -100]))

    update_size_fields = json.dumps({
        "Session_ID": "={{ $json.Session_ID || $('Find Active Session').first().json.Session_ID }}",
        "Selected_Size": "={{ $json.selectedSize }}",
        "State": "AWAITING_QUANTITY",
    })
    nodes.append(build_airtable_update(
        name="Update Session Size",
        table_id=TABLE_SESSIONS,
        fields_expr=update_size_fields,
        matching_column="Session_ID",
        position=[2620, -100],
    ))

    nodes.append(build_whatsapp_text(
        name="Send Quantity Prompt",
        to_expr="{{ $('Parse Message').first().json.from }}",
        text_expr="Perfect! Now please type the quantity you'd like to order (number only, e.g. 500):",
        position=[2860, -100],
    ))

    # ── Quantity Flow (Switch output 2: AWAITING_QUANTITY) ──
    nodes.append(build_code_node("Process Quantity", PROCESS_QUANTITY_CODE, [2380, -300]))

    update_qty_fields = json.dumps({
        "Session_ID": "={{ $json.Session_ID || $('Find Active Session').first().json.Session_ID }}",
        "Selected_Quantity": "={{ $json.selectedQuantity }}",
        "State": "QUOTING",
    })
    nodes.append(build_airtable_update(
        name="Update Session Quantity",
        table_id=TABLE_SESSIONS,
        fields_expr=update_qty_fields,
        matching_column="Session_ID",
        position=[2620, -300],
    ))

    # ── Product Catalog Lookup ──────────────────────────────
    nodes.append(build_airtable_search(
        name="Fetch Product Catalog",
        table_id=TABLE_PRODUCTS,
        filter_formula="=AND({Category}='{{ $('Process Quantity').first().json.selectedCategory || $('Find Active Session').first().json.Selected_Category }}', {Is_Active}=TRUE())",
        position=[2860, -300],
        always_output=True,
    ))

    # ── AI Mapping ──────────────────────────────────────────
    ai_mapping_system = (
        "You are a product mapping assistant. Given a customer's order selection "
        "(category, size, quantity) and a product catalog, return the best matching "
        "Xero item code and pricing. Respond ONLY with valid JSON:\n"
        '{"xero_item_code": "...", "xero_contact_id": "...", "unit_price": 0.00, '
        '"description": "..."}\n'
        "Use the product catalog data to find the closest match."
    )
    ai_mapping_user = (
        "Category: {{ $('Process Quantity').first().json.selectedCategory || "
        "$('Find Active Session').first().json.Selected_Category }}\n"
        "Size: {{ $('Process Size Selection').first().json.selectedSize || "
        "$('Find Active Session').first().json.Selected_Size }}\n"
        "Quantity: {{ $('Process Quantity').first().json.selectedQuantity || "
        "$('Find Active Session').first().json.Selected_Quantity }}\n"
        "Customer: {{ $('Parse Message').first().json.profileName }}\n"
        "Phone: {{ $('Parse Message').first().json.from }}\n"
        "Catalog: {{ JSON.stringify($('Fetch Product Catalog').first().json) }}"
    )
    nodes.append(build_openrouter_request(
        name="AI Map to Xero Item",
        system_prompt=ai_mapping_system,
        user_prompt_expr=ai_mapping_user,
        position=[3100, -300],
    ))

    nodes.append(build_code_node("Parse AI Mapping", PARSE_AI_MAPPING_CODE, [3340, -300]))

    # ── Create Xero Draft Quote ─────────────────────────────
    xero_quote_body = {
        "Quotes": [{
            "Contact": {"ContactID": "={{ $json.xeroContactId }}"},
            "LineItems": [{
                "ItemCode": "={{ $json.xeroItemCode }}",
                "Description": "={{ $json.description }}",
                "Quantity": "={{ $('Process Quantity').first().json.selectedQuantity }}",
                "UnitAmount": "={{ $json.unitPrice }}",
                "TaxType": "OUTPUT",
            }],
            "Status": "DRAFT",
            "Title": "=WhatsApp Order - {{ $('Parse Message').first().json.profileName }}",
            "Summary": "=Order via WhatsApp: {{ $('Process Quantity').first().json.selectedCategory || $('Find Active Session').first().json.Selected_Category }} - {{ $('Process Size Selection').first().json.selectedSize || $('Find Active Session').first().json.Selected_Size }} x {{ $('Process Quantity').first().json.selectedQuantity }}",
        }]
    }
    nodes.append(build_xero_request(
        name="Create Xero Draft Quote",
        method="POST",
        endpoint="Quotes",
        position=[3580, -300],
        body=xero_quote_body,
    ))

    nodes.append(build_code_node("Parse Quote Response", PARSE_QUOTE_RESPONSE_CODE, [3820, -300]))

    # ── Fetch Quote PDF ─────────────────────────────────────
    nodes.append(build_xero_request(
        name="Fetch Quote PDF",
        method="GET",
        endpoint="Quotes/={{ $json.quoteId }}",
        position=[4060, -300],
        accept="application/pdf",
        response_format="file",
    ))

    nodes.append(build_code_node("Rename PDF", RENAME_PDF_CODE, [4300, -300]))

    # ── Update Session with Quote ───────────────────────────
    update_quote_fields = json.dumps({
        "Session_ID": "={{ $('Find Active Session').first().json.Session_ID || $('Create New Session').first().json.Session_ID }}",
        "Xero_Quote_ID": "={{ $('Parse Quote Response').first().json.quoteId }}",
        "Xero_Quote_Number": "={{ $('Parse Quote Response').first().json.quoteNumber }}",
        "Quote_Total": "={{ $('Parse Quote Response').first().json.total }}",
        "State": "QUOTE_CREATED",
        "Approval_Status": "Pending",
    })
    nodes.append(build_airtable_update(
        name="Update Session Quote",
        table_id=TABLE_SESSIONS,
        fields_expr=update_quote_fields,
        matching_column="Session_ID",
        position=[4540, -300],
    ))

    nodes.append(build_code_node("Build Approval Message", BUILD_APPROVAL_MSG_CODE, [4780, -300]))

    # ── Send to Management ──────────────────────────────────
    # Note: For document sending, we use the Xero-hosted PDF link
    nodes.append(build_whatsapp_text(
        name="Send Quote Info to Mgmt",
        to_expr=MGMT_PHONE,
        text_expr="{{ $json.approvalText }}",
        position=[5020, -300],
    ))

    nodes.append(build_whatsapp_text(
        name="Send Approval Prompt to Mgmt",
        to_expr=MGMT_PHONE,
        text_expr="Quote {{ $('Parse Quote Response').first().json.quoteNumber }} - R{{ $('Parse Quote Response').first().json.total.toFixed(2) }}\n\nReply APPROVE or REJECT [reason]",
        position=[5260, -300],
    ))

    # ── Update to Pending Approval ──────────────────────────
    update_pending_fields = json.dumps({
        "Session_ID": "={{ $('Find Active Session').first().json.Session_ID || $('Create New Session').first().json.Session_ID }}",
        "State": "PENDING_APPROVAL",
    })
    nodes.append(build_airtable_update(
        name="Update Session Pending",
        table_id=TABLE_SESSIONS,
        fields_expr=update_pending_fields,
        matching_column="Session_ID",
        position=[5500, -300],
    ))

    # ── Confirmation to Customer ────────────────────────────
    nodes.append(build_whatsapp_text(
        name="Send Confirmation to Customer",
        to_expr="{{ $('Parse Message').first().json.from }}",
        text_expr="Thank you, {{ $('Parse Message').first().json.profileName }}! Your order has been received and a quote is being prepared. We'll send you the invoice shortly once it's approved.",
        position=[5500, -100],
    ))

    # ── Error Handler ───────────────────────────────────────
    nodes.append(build_error_trigger("Error Trigger", [200, 900]))
    nodes.append(build_code_node("Handle Error", HANDLE_ERROR_CODE, [460, 900]))

    # ── Sticky Notes ────────────────────────────────────────
    nodes.append(build_sticky_note(
        "Note: Intake",
        "## Step 1: Intake\nParse WhatsApp message, check working hours, find/create session.",
        [150, 300], width=280, height=180,
    ))
    nodes.append(build_sticky_note(
        "Note: Menu Flow",
        "## Step 2: Menu Flow\nCategory -> Size -> Quantity conversational flow via Switch routing.",
        [2100, -400], width=280, height=180,
    ))
    nodes.append(build_sticky_note(
        "Note: Quote & Approve",
        "## Step 3: Quote & Approve\nAI maps to Xero item, creates draft quote, sends PDF to management.",
        [3500, -400], width=280, height=180,
    ))

    return nodes


def build_ord01_connections(nodes):
    """Build connection map for ORD-01."""
    conns = [
        # Triggers -> Parse Message
        connect(nodes, "WhatsApp Trigger", "Parse Message"),
        connect(nodes, "Manual Trigger", "Parse Message"),

        # Parse Message -> Valid?
        connect(nodes, "Parse Message", "Valid?"),

        # Valid? true (output 0) -> Send Read Receipt
        connect(nodes, "Valid?", "Send Read Receipt", 0),
        # Valid? false (output 1) -> Log Parse Error
        connect(nodes, "Valid?", "Log Parse Error", 1),

        # Send Read Receipt -> Check Working Hours
        connect(nodes, "Send Read Receipt", "Check Working Hours"),

        # Check Working Hours -> Within Hours?
        connect(nodes, "Check Working Hours", "Within Hours?"),

        # Within Hours? true (output 0) -> Find Active Session
        connect(nodes, "Within Hours?", "Find Active Session", 0),
        # Within Hours? false (output 1) -> Send After Hours Reply
        connect(nodes, "Within Hours?", "Send After Hours Reply", 1),

        # Send After Hours Reply -> Log After Hours
        connect(nodes, "Send After Hours Reply", "Log After Hours"),

        # Find Active Session -> Has Session?
        connect(nodes, "Find Active Session", "Has Session?"),

        # Has Session? true (output 0) -> Route by State
        connect(nodes, "Has Session?", "Route by State", 0),
        # Has Session? false (output 1) -> Create New Session
        connect(nodes, "Has Session?", "Create New Session", 1),

        # Create New Session -> Send Category Menu
        connect(nodes, "Create New Session", "Send Category Menu"),

        # Route by State output 0 (AWAITING_CATEGORY) -> Process Category Selection
        connect(nodes, "Route by State", "Process Category Selection", 0),
        # Route by State output 1 (AWAITING_SIZE) -> Process Size Selection
        connect(nodes, "Route by State", "Process Size Selection", 1),
        # Route by State output 2 (AWAITING_QUANTITY) -> Process Quantity
        connect(nodes, "Route by State", "Process Quantity", 2),
        # Route by State output 3 (fallback) -> Create New Session
        connect(nodes, "Route by State", "Create New Session", 3),

        # Category flow
        connect(nodes, "Process Category Selection", "Update Session Category"),
        connect(nodes, "Update Session Category", "Send Size Buttons"),

        # Size flow
        connect(nodes, "Process Size Selection", "Update Session Size"),
        connect(nodes, "Update Session Size", "Send Quantity Prompt"),

        # Quantity flow
        connect(nodes, "Process Quantity", "Update Session Quantity"),
        connect(nodes, "Update Session Quantity", "Fetch Product Catalog"),
        connect(nodes, "Fetch Product Catalog", "AI Map to Xero Item"),
        connect(nodes, "AI Map to Xero Item", "Parse AI Mapping"),
        connect(nodes, "Parse AI Mapping", "Create Xero Draft Quote"),
        connect(nodes, "Create Xero Draft Quote", "Parse Quote Response"),
        connect(nodes, "Parse Quote Response", "Fetch Quote PDF"),
        connect(nodes, "Fetch Quote PDF", "Rename PDF"),
        connect(nodes, "Rename PDF", "Update Session Quote"),
        connect(nodes, "Update Session Quote", "Build Approval Message"),
        connect(nodes, "Build Approval Message", "Send Quote Info to Mgmt"),
        connect(nodes, "Send Quote Info to Mgmt", "Send Approval Prompt to Mgmt"),
        connect(nodes, "Send Approval Prompt to Mgmt", "Update Session Pending"),
        connect(nodes, "Update Session Pending", "Send Confirmation to Customer"),

        # Error handler
        connect(nodes, "Error Trigger", "Handle Error"),
    ]
    return build_connection_map(conns)


# ======================================================================
# ORD-02: Approval Handler
# ======================================================================

def build_ord02_nodes():
    """Build all nodes for ORD-02: Approval Handler."""
    nodes = []

    # ── Triggers ────────────────────────────────────────────
    nodes.append(build_whatsapp_trigger("WhatsApp Trigger Mgmt", [200, 400]))
    nodes.append(build_manual_trigger("Manual Trigger", [200, 600]))

    # ── Parse Management Message ────────────────────────────
    nodes.append(build_code_node("Parse Mgmt Message", PARSE_MESSAGE_CODE, [460, 500]))

    # ── Verify Management Number ────────────────────────────
    nodes.append(build_if_string_node(
        name="Is Mgmt Number?",
        left_value="={{ $json.from }}",
        operation="equals",
        right_value=MGMT_PHONE,
        position=[700, 500],
    ))

    # ── Find Pending Session ────────────────────────────────
    nodes.append(build_airtable_search(
        name="Find Pending Session",
        table_id=TABLE_SESSIONS,
        filter_formula="=AND({State}='PENDING_APPROVAL', {Approval_Status}='Pending')",
        position=[940, 400],
        always_output=True,
    ))

    # ── Has Pending Quote? ──────────────────────────────────
    nodes.append(build_if_string_node(
        name="Has Pending Quote?",
        left_value="={{ $json.Session_ID }}",
        operation="isNotEmpty",
        right_value="",
        position=[1180, 400],
    ))

    # ── Parse Decision ──────────────────────────────────────
    nodes.append(build_code_node("Parse Decision", PARSE_DECISION_CODE, [1420, 400]))

    # ── Decision Router (Switch) ────────────────────────────
    nodes.append(build_switch_node(
        name="Decision Router",
        field_expr="={{ $json.decision }}",
        rules=["approve", "reject"],
        position=[1660, 400],
        fallback_output=2,
    ))

    # ── No Pending Quote Reply ──────────────────────────────
    nodes.append(build_whatsapp_text(
        name="No Pending Quote Reply",
        to_expr=MGMT_PHONE,
        text_expr="No pending quotes found for approval at this time.",
        position=[1420, 700],
    ))

    # ────────────────────────────────────────────────────────
    # APPROVE BRANCH (Decision Router output 0)
    # ────────────────────────────────────────────────────────

    # Fresh Xero check
    nodes.append(build_xero_request(
        name="Fresh Xero Check",
        method="GET",
        endpoint="Quotes/={{ $('Find Pending Session').first().json.Xero_Quote_ID }}",
        position=[1900, 200],
    ))

    # Quote still draft?
    nodes.append(build_if_string_node(
        name="Quote Still Draft?",
        left_value="={{ $json.Quotes[0].Status }}",
        operation="equals",
        right_value="DRAFT",
        position=[2140, 200],
    ))

    # Convert to Invoice
    xero_invoice_body = {
        "Invoices": [{
            "Type": "ACCREC",
            "Contact": {"ContactID": "={{ $('Fresh Xero Check').first().json.Quotes[0].Contact.ContactID }}"},
            "LineItems": "={{ $('Fresh Xero Check').first().json.Quotes[0].LineItems }}",
            "Status": "AUTHORISED",
            "Reference": "=From Quote {{ $('Find Pending Session').first().json.Xero_Quote_Number }}",
            "DueDate": "={{ DateTime.now().plus({days: 30}).toFormat('yyyy-MM-dd') }}",
        }]
    }
    nodes.append(build_xero_request(
        name="Convert to Invoice",
        method="POST",
        endpoint="Invoices",
        position=[2380, 200],
        body=xero_invoice_body,
    ))

    # Parse Invoice Response
    nodes.append(build_code_node("Parse Invoice Response", PARSE_INVOICE_RESPONSE_CODE, [2620, 200]))

    # Fetch Invoice PDF
    nodes.append(build_xero_request(
        name="Fetch Invoice PDF",
        method="GET",
        endpoint="Invoices/={{ $json.invoiceId }}",
        position=[2860, 200],
        accept="application/pdf",
        response_format="file",
    ))

    # Rename Invoice PDF
    nodes.append(build_code_node("Rename Invoice PDF", RENAME_INVOICE_PDF_CODE, [3100, 200]))

    # Send Invoice to Customer via WhatsApp
    nodes.append(build_whatsapp_text(
        name="Send Invoice to Customer",
        to_expr="{{ $('Find Pending Session').first().json.Customer_Phone }}",
        text_expr="Hi {{ $('Find Pending Session').first().json.Customer_Name }}! Your invoice {{ $('Parse Invoice Response').first().json.invoiceNumber }} for R{{ $('Parse Invoice Response').first().json.total.toFixed(2) }} is ready. Payment details will follow shortly. Thank you for your order!",
        position=[3340, 200],
    ))

    # Update Session -> Approved
    update_approved_fields = json.dumps({
        "Session_ID": "={{ $('Find Pending Session').first().json.Session_ID }}",
        "State": "INVOICE_SENT",
        "Approval_Status": "Approved",
        "Xero_Invoice_ID": "={{ $('Parse Invoice Response').first().json.invoiceId }}",
        "Xero_Invoice_Number": "={{ $('Parse Invoice Response').first().json.invoiceNumber }}",
    })
    nodes.append(build_airtable_update(
        name="Update Session Approved",
        table_id=TABLE_SESSIONS,
        fields_expr=update_approved_fields,
        matching_column="Session_ID",
        position=[3580, 200],
    ))

    # Notify Management
    nodes.append(build_whatsapp_text(
        name="Notify Mgmt Approved",
        to_expr=MGMT_PHONE,
        text_expr="Invoice {{ $('Parse Invoice Response').first().json.invoiceNumber }} (R{{ $('Parse Invoice Response').first().json.total.toFixed(2) }}) has been sent to {{ $('Find Pending Session').first().json.Customer_Name }}.",
        position=[3580, 400],
    ))

    # ────────────────────────────────────────────────────────
    # REJECT BRANCH (Decision Router output 1)
    # ────────────────────────────────────────────────────────

    # Check Rejection Count
    nodes.append(build_if_number_node(
        name="Check Rejection Count",
        left_value="={{ $('Find Pending Session').first().json.Rejection_Count || 0 }}",
        operation="lt",
        right_value=3,
        position=[1900, 500],
    ))

    # AI Parse Feedback
    ai_feedback_system = (
        "You are an order management assistant. A manager has rejected a quote with feedback. "
        "Parse the feedback and determine what changes to make. Respond ONLY with valid JSON:\n"
        '{"action": "revise_quantity|revise_price|revise_item|unclear", '
        '"new_quantity": null, "new_price": null, "new_item_code": null, '
        '"explanation": "..."}\n'
        "Set the appropriate field based on the feedback."
    )
    ai_feedback_user = (
        "Rejection feedback: {{ $('Parse Decision').first().json.feedback }}\n"
        "Current quote: {{ $('Find Pending Session').first().json.Xero_Quote_Number }}\n"
        "Category: {{ $('Find Pending Session').first().json.Selected_Category }}\n"
        "Size: {{ $('Find Pending Session').first().json.Selected_Size }}\n"
        "Quantity: {{ $('Find Pending Session').first().json.Selected_Quantity }}\n"
        "Total: R{{ $('Find Pending Session').first().json.Quote_Total }}"
    )
    nodes.append(build_openrouter_request(
        name="AI Parse Feedback",
        system_prompt=ai_feedback_system,
        user_prompt_expr=ai_feedback_user,
        position=[2140, 500],
    ))

    # Parse AI Feedback
    nodes.append(build_code_node("Parse AI Feedback", PARSE_AI_FEEDBACK_CODE, [2380, 500]))

    # Update Xero Quote
    xero_update_body = {
        "Quotes": [{
            "QuoteID": "={{ $('Find Pending Session').first().json.Xero_Quote_ID }}",
            "LineItems": [{
                "ItemCode": "={{ $json.newItemCode || $('Find Pending Session').first().json.Xero_Item_Code || '' }}",
                "Quantity": "={{ $json.newQuantity || $('Find Pending Session').first().json.Selected_Quantity }}",
                "UnitAmount": "={{ $json.newPrice || '' }}",
            }],
            "Status": "DRAFT",
        }]
    }
    nodes.append(build_xero_request(
        name="Update Xero Quote",
        method="POST",
        endpoint="Quotes",
        position=[2620, 500],
        body=xero_update_body,
    ))

    # Fetch Updated PDF
    nodes.append(build_xero_request(
        name="Fetch Updated PDF",
        method="GET",
        endpoint="Quotes/={{ $('Find Pending Session').first().json.Xero_Quote_ID }}",
        position=[2860, 500],
        accept="application/pdf",
        response_format="file",
    ))

    # Re-send to Management
    nodes.append(build_whatsapp_text(
        name="Re-send to Management",
        to_expr=MGMT_PHONE,
        text_expr="Updated quote {{ $('Find Pending Session').first().json.Xero_Quote_Number }} based on your feedback: {{ $('Parse AI Feedback').first().json.explanation }}\n\nReply APPROVE or REJECT [reason]",
        position=[3100, 500],
    ))

    # Update Session Feedback
    update_feedback_fields = json.dumps({
        "Session_ID": "={{ $('Find Pending Session').first().json.Session_ID }}",
        "Rejection_Count": "={{ ($('Find Pending Session').first().json.Rejection_Count || 0) + 1 }}",
        "Approval_Status": "Pending",
        "Last_Feedback": "={{ $('Parse Decision').first().json.feedback }}",
    })
    nodes.append(build_airtable_update(
        name="Update Session Feedback",
        table_id=TABLE_SESSIONS,
        fields_expr=update_feedback_fields,
        matching_column="Session_ID",
        position=[3340, 500],
    ))

    # ────────────────────────────────────────────────────────
    # VAGUE / FALLBACK BRANCH (Decision Router output 2)
    # ────────────────────────────────────────────────────────

    nodes.append(build_whatsapp_text(
        name="Alert Staff Manual",
        to_expr=MGMT_PHONE,
        text_expr="Unclear response received. Please reply with:\n- *APPROVE* to convert the quote to an invoice\n- *REJECT [reason]* to request changes (e.g. REJECT reduce quantity to 200)",
        position=[1900, 700],
    ))

    # ── Max Rejections Branch (Check Rejection Count false) ─
    nodes.append(build_gmail_send(
        name="Send Alert Email",
        to=ALERT_EMAIL,
        subject_expr="=Order Quote Escalation - {{ $('Find Pending Session').first().json.Xero_Quote_Number }}",
        html_body_expr=(
            "=<h2>Quote Requires Manual Attention</h2>"
            "<p>Quote <strong>{{ $('Find Pending Session').first().json.Xero_Quote_Number }}</strong> "
            "has been rejected {{ $('Find Pending Session').first().json.Rejection_Count || 0 }} times.</p>"
            "<p>Customer: {{ $('Find Pending Session').first().json.Customer_Name }}</p>"
            "<p>Phone: {{ $('Find Pending Session').first().json.Customer_Phone }}</p>"
            "<p>Last feedback: {{ $('Parse Decision').first().json.feedback }}</p>"
            "<p>Please handle this order manually in Xero.</p>"
        ),
        position=[2140, 700],
    ))

    # ── Error Handler ───────────────────────────────────────
    nodes.append(build_error_trigger("Error Trigger", [200, 900]))
    nodes.append(build_code_node("Handle Error", HANDLE_ERROR_CODE, [460, 900]))

    # ── Sticky Note ─────────────────────────────────────────
    nodes.append(build_sticky_note(
        "Note: Approval Handler",
        "## Approval Handler\nManagement approves/rejects quotes via WhatsApp.\n"
        "- APPROVE -> Convert to invoice, send to customer\n"
        "- REJECT [reason] -> AI parses feedback, revises quote\n"
        "- Max 3 rejections before email escalation",
        [150, 300], width=300, height=220,
    ))

    return nodes


def build_ord02_connections(nodes):
    """Build connection map for ORD-02."""
    conns = [
        # Triggers -> Parse Mgmt Message
        connect(nodes, "WhatsApp Trigger Mgmt", "Parse Mgmt Message"),
        connect(nodes, "Manual Trigger", "Parse Mgmt Message"),

        # Parse Mgmt Message -> Is Mgmt Number?
        connect(nodes, "Parse Mgmt Message", "Is Mgmt Number?"),

        # Is Mgmt Number? true (output 0) -> Find Pending Session
        connect(nodes, "Is Mgmt Number?", "Find Pending Session", 0),
        # Is Mgmt Number? false (output 1) -> ignored (message from unknown number)

        # Find Pending Session -> Has Pending Quote?
        connect(nodes, "Find Pending Session", "Has Pending Quote?"),

        # Has Pending Quote? true (output 0) -> Parse Decision
        connect(nodes, "Has Pending Quote?", "Parse Decision", 0),
        # Has Pending Quote? false (output 1) -> No Pending Quote Reply
        connect(nodes, "Has Pending Quote?", "No Pending Quote Reply", 1),

        # Parse Decision -> Decision Router
        connect(nodes, "Parse Decision", "Decision Router"),

        # Decision Router output 0 (approve) -> Fresh Xero Check
        connect(nodes, "Decision Router", "Fresh Xero Check", 0),
        # Decision Router output 1 (reject) -> Check Rejection Count
        connect(nodes, "Decision Router", "Check Rejection Count", 1),
        # Decision Router output 2 (vague/fallback) -> Alert Staff Manual
        connect(nodes, "Decision Router", "Alert Staff Manual", 2),

        # ── Approve branch ──
        connect(nodes, "Fresh Xero Check", "Quote Still Draft?"),
        connect(nodes, "Quote Still Draft?", "Convert to Invoice", 0),
        # Quote not draft (output 1) -> alert (reuse Alert Staff Manual or no-op)
        connect(nodes, "Convert to Invoice", "Parse Invoice Response"),
        connect(nodes, "Parse Invoice Response", "Fetch Invoice PDF"),
        connect(nodes, "Fetch Invoice PDF", "Rename Invoice PDF"),
        connect(nodes, "Rename Invoice PDF", "Send Invoice to Customer"),
        connect(nodes, "Send Invoice to Customer", "Update Session Approved"),
        connect(nodes, "Update Session Approved", "Notify Mgmt Approved"),

        # ── Reject branch ──
        # Check Rejection Count true (< 3, output 0) -> AI Parse Feedback
        connect(nodes, "Check Rejection Count", "AI Parse Feedback", 0),
        # Check Rejection Count false (>= 3, output 1) -> Send Alert Email
        connect(nodes, "Check Rejection Count", "Send Alert Email", 1),

        connect(nodes, "AI Parse Feedback", "Parse AI Feedback"),
        connect(nodes, "Parse AI Feedback", "Update Xero Quote"),
        connect(nodes, "Update Xero Quote", "Fetch Updated PDF"),
        connect(nodes, "Fetch Updated PDF", "Re-send to Management"),
        connect(nodes, "Re-send to Management", "Update Session Feedback"),

        # Error handler
        connect(nodes, "Error Trigger", "Handle Error"),
    ]
    return build_connection_map(conns)


# ======================================================================
# WORKFLOW ASSEMBLY
# ======================================================================

WORKFLOW_BUILDERS = {
    "ord01": {
        "name": "ORD-01: WhatsApp Order Intake",
        "build_nodes": build_ord01_nodes,
        "build_connections": build_ord01_connections,
        "filename": "order_to_invoice_intake.json",
        "tags": [{"name": "client-project"}, {"name": "order-to-invoice"}],
    },
    "ord02": {
        "name": "ORD-02: Approval Handler",
        "build_nodes": build_ord02_nodes,
        "build_connections": build_ord02_connections,
        "filename": "order_to_invoice_approval.json",
        "tags": [{"name": "client-project"}, {"name": "order-to-invoice"}],
    },
}


def build_workflow(key):
    """Build a complete workflow JSON."""
    spec = WORKFLOW_BUILDERS[key]
    nodes = spec["build_nodes"]()
    connections = spec["build_connections"](nodes)

    return {
        "name": spec["name"],
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "tags": spec.get("tags", []),
    }


def save_workflow(key, workflow_data):
    """Save workflow JSON to file."""
    spec = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "client-projects"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec["filename"]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_data, f, indent=2, ensure_ascii=False)

    node_count = len(workflow_data["nodes"])
    print(f"  + {spec['name']:<40} -> {output_path.name} ({node_count} nodes)")
    return output_path


# ======================================================================
# n8n API HELPERS
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


def deploy_workflow(workflow_data):
    """Deploy workflow to n8n via API."""
    client = get_n8n_client()
    resp = client.create_workflow(workflow_data)
    return resp


def activate_workflow(workflow_id):
    """Activate a workflow by ID."""
    client = get_n8n_client()
    resp = client.activate_workflow(workflow_id)
    return resp


# ======================================================================
# CLI
# ======================================================================

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python tools/deploy_order_to_invoice.py <build|deploy|activate> [workflow_key]")
        print()
        print("Available workflows:")
        for key, spec in WORKFLOW_BUILDERS.items():
            print(f"  {key:<10} {spec['name']}")
        sys.exit(1)

    action = args[0]
    target = args[1] if len(args) > 1 else None

    keys = [target] if target and target in WORKFLOW_BUILDERS else list(WORKFLOW_BUILDERS.keys())

    if target and target not in WORKFLOW_BUILDERS:
        print(f"ERROR: Unknown workflow '{target}'. Available: {', '.join(WORKFLOW_BUILDERS.keys())}")
        sys.exit(1)

    print("=" * 60)
    print("ORDER-TO-INVOICE - WORKFLOW BUILDER")
    print("=" * 60)
    print()
    print(f"Action: {action}")
    print(f"Workflows: {', '.join(keys)}")
    print(f"Airtable Base: {ORDER_BASE_ID}")
    print(f"Sessions Table: {TABLE_SESSIONS}")
    print(f"Products Table: {TABLE_PRODUCTS}")
    print(f"Mgmt Phone: {MGMT_PHONE}")
    print()

    # Build
    print("Building workflows...")
    print("-" * 40)
    built = {}
    for key in keys:
        workflow = build_workflow(key)
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
        deployed_ids = {}
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

        # Save deployed IDs
        if deployed_ids:
            output_dir = Path(__file__).parent.parent / ".tmp"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "order_to_invoice_workflow_ids.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({
                    "deployed": deployed_ids,
                    "deployed_at": datetime.now().isoformat(),
                }, f, indent=2)
            print(f"Workflow IDs saved to: {output_path}")

    print()
    print("Next steps:")
    print("  1. Verify workflows in n8n UI")
    print("  2. Create Xero OAuth2 credential in n8n")
    print("  3. Set ORDER_TABLE_SESSIONS and ORDER_TABLE_PRODUCTS in .env")
    print("  4. Set ORDER_MGMT_PHONE and WHATSAPP_PHONE_NUMBER_ID in .env")
    print("  5. Manual trigger ORD-01 to test intake flow")
    print("  6. Activate ORD-01 first, then ORD-02")


if __name__ == "__main__":
    main()
