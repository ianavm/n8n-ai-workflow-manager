"""
ACCT-03: Invoice Sending & Notifications

Sends approved invoices via email (and optionally WhatsApp), updates status
to 'sent', schedules the first payment reminder based on config cadence,
and logs the event through the portal webhook pipeline.

Triggers:
    1. Webhook POST /accounting/send-invoice  (portal "Send" button)
    2. Schedule: hourly 9-17 Mon-Fri          (auto-send approved unsent)
    3. Manual trigger                         (testing)

Node count: ~20 functional + sticky notes

Usage:
    python tools/deploy_acct_v2_wf03.py build      # Build JSON only
    python tools/deploy_acct_v2_wf03.py deploy      # Build + deploy (inactive)
    python tools/deploy_acct_v2_wf03.py activate    # Build + deploy + activate
"""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add tools dir to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from acct_helpers import (
    uid,
    schedule_trigger,
    manual_trigger,
    webhook_trigger,
    supabase_select,
    supabase_update,
    portal_status_webhook,
    code_node,
    if_node,
    switch_node,
    gmail_send,
    build_workflow_json,
    conn,
    SUPABASE_URL,
    SUPABASE_KEY,
    PORTAL_URL,
    N8N_WEBHOOK_SECRET,
)
from credentials import CREDENTIALS

CRED_GMAIL = CREDENTIALS["gmail"]

# ── Constants ──────────────────────────────────────────────────
WORKFLOW_NAME = "ACCT-03 Invoice Sending & Notifications"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILENAME = "wf03_invoice_sending.json"


# ================================================================
# NODE BUILDERS
# ================================================================


def build_nodes() -> list[dict]:
    """Build all nodes for ACCT-03."""
    nodes: list[dict] = []

    # ── Sticky Notes ──────────────────────────────────────────
    nodes.append({
        "parameters": {
            "content": (
                "## ACCT-03: Invoice Sending & Notifications\n"
                "Sends approved invoices via email/WhatsApp.\n"
                "Schedules first payment reminder, logs to portal."
            ),
            "width": 500,
            "height": 100,
            "color": 4,
        },
        "id": uid(),
        "name": "Note - Overview",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 60],
        "typeVersion": 1,
    })

    nodes.append({
        "parameters": {
            "content": (
                "### WhatsApp Branch\n"
                "Only fires when customer.preferred_channel\n"
                "is 'whatsapp' or 'both'."
            ),
            "width": 300,
            "height": 80,
            "color": 3,
        },
        "id": uid(),
        "name": "Note - WhatsApp",
        "type": "n8n-nodes-base.stickyNote",
        "position": [1360, 700],
        "typeVersion": 1,
    })

    # ── 1. Webhook Trigger ────────────────────────────────────
    nodes.append(webhook_trigger(
        name="Webhook - Send Invoice",
        path="accounting/send-invoice",
        position=[200, 300],
    ))

    # ── 2. Schedule Trigger (hourly 9-17 Mon-Fri) ─────────────
    #    Cron: minute 0, hours 9-17, any day-of-month, any month, Mon-Fri
    nodes.append(schedule_trigger(
        name="Schedule - Hourly Check",
        cron="0 9-17 * * 1-5",
        position=[200, 500],
    ))

    # ── 3. Manual Trigger ─────────────────────────────────────
    nodes.append(manual_trigger(position=[200, 700]))

    # ── 4. Merge Trigger Context ──────────────────────────────
    #    Webhook sends {invoice_id, client_id}.
    #    Schedule/manual need to query for approved-but-unsent.
    merge_js = r"""
// Webhook path provides invoice_id + client_id directly.
// Schedule path needs to query for unsent invoices (handled downstream).
const input = $input.first().json;
const fromWebhook = !!(input.invoice_id);

return [{
  json: {
    invoice_id: input.invoice_id || null,
    client_id: input.client_id || null,
    fromWebhook,
  }
}];
"""
    nodes.append(code_node(
        name="Merge Trigger Context",
        js_code=merge_js,
        position=[460, 300],
    ))

    # ── 5. Load Config ────────────────────────────────────────
    #    Fetch client accounting config (reminder cadence, etc.)
    nodes.append(supabase_select(
        name="Load Config",
        table="acct_config",
        select="*",
        filters="={{  $json.client_id ? 'client_id=eq.' + $json.client_id : 'limit=1' }}",
        position=[700, 300],
        single=True,
    ))

    # ── 6. Fetch Invoice(s) ──────────────────────────────────
    #    If from webhook, fetch by id + status=approved.
    #    If from schedule, fetch all status=approved & sent_at is null.
    fetch_invoice_js = r"""
const ctx = $('Merge Trigger Context').first().json;
const config = $input.first().json;

// Build Supabase REST filter
let filters;
if (ctx.fromWebhook && ctx.invoice_id) {
  filters = `id=eq.${ctx.invoice_id}&status=eq.approved`;
} else {
  filters = 'status=eq.approved&sent_at=is.null&order=created_at.asc&limit=10';
}

const SUPABASE_URL = '""" + SUPABASE_URL + r"""';
const SUPABASE_KEY = '""" + SUPABASE_KEY + r"""';

const url = `${SUPABASE_URL}/rest/v1/acct_invoices?select=*&${filters}`;

const resp = await this.helpers.httpRequest({
  method: 'GET',
  url,
  headers: {
    apikey: SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
  },
  returnFullResponse: false,
  json: true,
});

const invoices = Array.isArray(resp) ? resp : [resp];

if (invoices.length === 0) {
  return [{ json: { _noInvoices: true, count: 0 } }];
}

return invoices.map(inv => ({
  json: {
    ...inv,
    _config: config,
    _fromWebhook: ctx.fromWebhook,
  }
}));
"""
    nodes.append(code_node(
        name="Fetch Invoice(s)",
        js_code=fetch_invoice_js,
        position=[940, 300],
    ))

    # ── 7. Has Invoice? ──────────────────────────────────────
    nodes.append(if_node(
        name="Has Invoice?",
        left_value="={{ $json._noInvoices }}",
        operator_type="boolean",
        operation="notEquals",
        right_value="true",
        position=[1160, 300],
    ))

    # ── 8. Fetch Customer ────────────────────────────────────
    fetch_customer_js = r"""
const invoice = $input.first().json;
const customerId = invoice.customer_id;

const SUPABASE_URL = '""" + SUPABASE_URL + r"""';
const SUPABASE_KEY = '""" + SUPABASE_KEY + r"""';

const url = `${SUPABASE_URL}/rest/v1/acct_customers?select=*&id=eq.${customerId}`;

const resp = await this.helpers.httpRequest({
  method: 'GET',
  url,
  headers: {
    apikey: SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
    Accept: 'application/vnd.pgrst.object+json',
  },
  returnFullResponse: false,
  json: true,
});

return [{
  json: {
    invoice,
    customer: resp,
  }
}];
"""
    nodes.append(code_node(
        name="Fetch Customer",
        js_code=fetch_customer_js,
        position=[1400, 200],
    ))

    # ── 9. Check Channel ─────────────────────────────────────
    nodes.append(switch_node(
        name="Check Channel",
        rules=[
            {
                "leftValue": "={{ $json.customer.preferred_channel }}",
                "rightValue": "email",
                "output": "email",
            },
            {
                "leftValue": "={{ $json.customer.preferred_channel }}",
                "rightValue": "whatsapp",
                "output": "whatsapp",
            },
            {
                "leftValue": "={{ $json.customer.preferred_channel }}",
                "rightValue": "both",
                "output": "both",
            },
        ],
        position=[1640, 200],
    ))

    # ── 10. Build Email HTML ─────────────────────────────────
    build_email_js = r"""
const data = $input.first().json;
const inv = data.invoice;
const cust = data.customer;

// Format amount from cents to Rands
function formatZAR(cents) {
  const rands = (cents || 0) / 100;
  return rands.toLocaleString('en-ZA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Build line items HTML
const lineItems = (inv.line_items || []);
let lineItemsHtml = '';
for (const item of lineItems) {
  const qty = item.quantity || 1;
  const unitPrice = (item.unit_price_cents || 0);
  const vatAmt = (item.vat_cents || 0);
  const lineTotal = (item.total_cents || (unitPrice * qty + vatAmt));
  lineItemsHtml += `
    <tr>
      <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px;">${item.code || ''}</td>
      <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px;">${item.description || ''}</td>
      <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px;text-align:center;">${qty}</td>
      <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px;text-align:right;">R ${formatZAR(unitPrice)}</td>
      <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px;text-align:right;">R ${formatZAR(vatAmt)}</td>
      <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px;text-align:right;">R ${formatZAR(lineTotal)}</td>
    </tr>`;
}

const subtotal = formatZAR(inv.subtotal_cents || 0);
const vatAmount = formatZAR(inv.vat_cents || 0);
const total = formatZAR(inv.total_cents || 0);

const issueDate = inv.issue_date
  ? new Date(inv.issue_date).toLocaleDateString('en-ZA')
  : new Date().toLocaleDateString('en-ZA');
const dueDate = inv.due_date
  ? new Date(inv.due_date).toLocaleDateString('en-ZA')
  : 'On receipt';

// Build full email HTML (inline template matching templates/accounting_invoice.html)
const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;background-color:#f4f4f4;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background-color:#ffffff;">
    <tr>
      <td style="padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td><h1 style="margin:0;font-size:22px;color:#1A1A2E;">TAX INVOICE</h1></td>
            <td style="text-align:right;"><span style="font-size:14px;color:#666;">AnyVision Media</span></td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 40px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="vertical-align:top;">
              <p style="margin:0;font-size:12px;color:#999;text-transform:uppercase;">Bill To</p>
              <p style="margin:4px 0;font-size:15px;"><strong>${cust.name || cust.company_name || ''}</strong></p>
              <p style="margin:0;font-size:13px;color:#666;">${cust.email || ''}</p>
              <p style="margin:0;font-size:13px;color:#666;">${cust.address || ''}</p>
              <p style="margin:0;font-size:13px;color:#666;">VAT: ${cust.vat_number || 'N/A'}</p>
            </td>
            <td width="50%" style="vertical-align:top;text-align:right;">
              <p style="margin:0;font-size:13px;color:#666;">Invoice #: <strong>${inv.invoice_number || inv.id}</strong></p>
              <p style="margin:4px 0;font-size:13px;color:#666;">Date: ${issueDate}</p>
              <p style="margin:4px 0;font-size:13px;color:#666;">Due: <strong>${dueDate}</strong></p>
              <p style="margin:4px 0;font-size:13px;color:#666;">Terms: ${inv.payment_terms || 'Net 30'}</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:0 40px 20px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          <tr style="background-color:#f8f8f8;">
            <th style="padding:10px 8px;text-align:left;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;">Code</th>
            <th style="padding:10px 8px;text-align:left;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;">Description</th>
            <th style="padding:10px 8px;text-align:center;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;">Qty</th>
            <th style="padding:10px 8px;text-align:right;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;">Unit Price</th>
            <th style="padding:10px 8px;text-align:right;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;">VAT</th>
            <th style="padding:10px 8px;text-align:right;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;">Total</th>
          </tr>
          ${lineItemsHtml}
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:0 40px 20px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="text-align:right;padding:4px 8px;color:#666;">Subtotal:</td>
            <td style="text-align:right;padding:4px 8px;width:120px;"><strong>R ${subtotal}</strong></td>
          </tr>
          <tr>
            <td style="text-align:right;padding:4px 8px;color:#666;">VAT (15%):</td>
            <td style="text-align:right;padding:4px 8px;"><strong>R ${vatAmount}</strong></td>
          </tr>
          <tr style="border-top:2px solid #FF6D5A;">
            <td style="text-align:right;padding:8px;font-size:18px;">Total Due:</td>
            <td style="text-align:right;padding:8px;font-size:18px;color:#FF6D5A;"><strong>R ${total}</strong></td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;">
        <p style="margin:0 0 8px;font-size:14px;"><strong>Payment Options:</strong></p>
        <p style="margin:0;font-size:13px;color:#666;line-height:1.6;">
          <strong>EFT:</strong><br>
          Bank: ${inv.bank_name || 'FNB'}<br>
          Account: ${inv.bank_account || 'See invoice'}<br>
          Branch Code: ${inv.bank_branch || '250655'}<br>
          Reference: ${inv.invoice_number || inv.id}
        </p>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 40px;background-color:#f8f8f8;">
        <p style="margin:0;font-size:11px;color:#999;line-height:1.5;">
          AnyVision Media | Johannesburg, South Africa<br>
          accounts@anyvisionmedia.com<br>
          Please use the invoice number as your payment reference.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>`;

return [{
  json: {
    ...data,
    emailHtml: html,
    emailSubject: `Invoice ${inv.invoice_number || inv.id} from AnyVision Media — R ${total} due ${dueDate}`,
    emailTo: cust.email,
  }
}];
"""
    nodes.append(code_node(
        name="Build Email HTML",
        js_code=build_email_js,
        position=[1900, 100],
    ))

    # ── 11. Send Email ───────────────────────────────────────
    nodes.append(gmail_send(
        name="Send Email",
        to_expr="={{ $json.emailTo }}",
        subject_expr="={{ $json.emailSubject }}",
        html_expr="={{ $json.emailHtml }}",
        cred=CRED_GMAIL,
        position=[2140, 100],
    ))

    # ── 12. Build WhatsApp Message ───────────────────────────
    wa_msg_js = r"""
const data = $input.first().json;
const inv = data.invoice;
const cust = data.customer;

function formatZAR(cents) {
  const rands = (cents || 0) / 100;
  return rands.toLocaleString('en-ZA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const total = formatZAR(inv.total_cents || 0);
const dueDate = inv.due_date
  ? new Date(inv.due_date).toLocaleDateString('en-ZA')
  : 'On receipt';

const message = [
  `*Invoice ${inv.invoice_number || inv.id}*`,
  `From: AnyVision Media`,
  ``,
  `Hi ${cust.name || cust.company_name || 'there'},`,
  ``,
  `Your invoice for *R ${total}* is due on *${dueDate}*.`,
  ``,
  `Please use reference: ${inv.invoice_number || inv.id}`,
  ``,
  `Questions? Reply to this message or email accounts@anyvisionmedia.com`,
].join('\n');

return [{
  json: {
    ...data,
    waMessage: message,
    waPhone: cust.phone || cust.whatsapp_number || null,
  }
}];
"""
    nodes.append(code_node(
        name="Build WhatsApp Message",
        js_code=wa_msg_js,
        position=[1900, 400],
    ))

    # ── 13. Send WhatsApp ────────────────────────────────────
    #    HTTP Request to WhatsApp Business API (placeholder URL).
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.waPhone ? 'https://graph.facebook.com/v19.0/PHONE_NUMBER_ID/messages' : '' }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Authorization", "value": "Bearer WHATSAPP_TOKEN_PLACEHOLDER"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={{ JSON.stringify({ messaging_product: "whatsapp", to: $json.waPhone, type: "text", text: { body: $json.waMessage } }) }}',
            "options": {
                "response": {"response": {"responseFormat": "json"}},
                "timeout": 15000,
            },
        },
        "id": uid(),
        "name": "Send WhatsApp",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2140, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # ── 14. Merge Send Results ───────────────────────────────
    #    Collect results from email and/or WhatsApp branches
    #    so we proceed to status update regardless of channel.
    merge_results_js = r"""
// Grab the full context from Build Email HTML or Build WhatsApp Message
// whichever path(s) executed. Use the richest upstream reference.
const emailData = $('Build Email HTML').first()?.json;
const waData = $('Build WhatsApp Message').first()?.json;
const data = emailData || waData;

if (!data) {
  return [{ json: { error: 'No send data available' } }];
}

return [{
  json: {
    invoice_id: data.invoice.id,
    customer_id: data.invoice.customer_id,
    client_id: data.invoice._config?.client_id || data.invoice.client_id,
    invoice_number: data.invoice.invoice_number || data.invoice.id,
    total_cents: data.invoice.total_cents,
    due_date: data.invoice.due_date,
    customer_email: data.customer.email,
    customer_name: data.customer.name || data.customer.company_name,
    preferred_channel: data.customer.preferred_channel || 'email',
    reminder_cadence_days: data.invoice._config?.reminder_cadence_days || [-3, 0, 3, 7, 14],
  }
}];
"""
    nodes.append(code_node(
        name="Merge Send Results",
        js_code=merge_results_js,
        position=[2380, 250],
    ))

    # ── 15. Update Invoice Status ────────────────────────────
    update_status_js = r"""
const data = $input.first().json;

return [{
  json: {
    id: data.invoice_id,
    updatePayload: {
      status: 'sent',
      sent_at: new Date().toISOString(),
    }
  }
}];
"""
    nodes.append(code_node(
        name="Prepare Status Update",
        js_code=update_status_js,
        position=[2600, 250],
    ))

    nodes.append(supabase_update(
        name="Update Invoice Status",
        table="acct_invoices",
        match_col="id",
        position=[2820, 250],
    ))

    # ── 16. Schedule First Reminder ──────────────────────────
    schedule_reminder_js = r"""
const data = $('Merge Send Results').first().json;
const cadence = data.reminder_cadence_days || [-3, 0, 3, 7, 14];
const dueDate = data.due_date ? new Date(data.due_date) : null;

if (!dueDate) {
  return [{
    json: {
      id: data.invoice_id,
      updatePayload: { next_reminder_at: null }
    }
  }];
}

// First cadence entry = days offset from due_date (negative = before)
const firstOffset = cadence[0] || 0;
const reminderDate = new Date(dueDate);
reminderDate.setDate(reminderDate.getDate() + firstOffset);

// Don't schedule in the past
const now = new Date();
const nextReminder = reminderDate > now ? reminderDate : now;

return [{
  json: {
    id: data.invoice_id,
    updatePayload: {
      next_reminder_at: nextReminder.toISOString(),
      reminder_cadence_index: 0,
    }
  }
}];
"""
    nodes.append(code_node(
        name="Schedule First Reminder",
        js_code=schedule_reminder_js,
        position=[3040, 250],
    ))

    nodes.append(supabase_update(
        name="Update Reminder Schedule",
        table="acct_invoices",
        match_col="id",
        position=[3260, 250],
    ))

    # ── 17. Log Collection Entry ─────────────────────────────
    nodes.append(portal_status_webhook(
        name="Log Collection Entry",
        action="collection_logged",
        position=[3480, 150],
    ))

    # ── 18. Status Update - Invoice Sent ─────────────────────
    nodes.append(portal_status_webhook(
        name="Status - Invoice Sent",
        action="invoice_sent",
        position=[3480, 350],
    ))

    # ── 19. Audit Log ────────────────────────────────────────
    audit_prep_js = r"""
const data = $('Merge Send Results').first().json;

return [{
  json: {
    action: 'audit_log',
    data: {
      client_id: data.client_id,
      event_type: 'INVOICE_SENT',
      entity_type: 'invoice',
      entity_id: data.invoice_id,
      actor: 'n8n-acct-03',
      result: 'success',
      metadata: {
        invoice_number: data.invoice_number,
        customer_email: data.customer_email,
        channel: data.preferred_channel,
        total_cents: data.total_cents,
        source: 'n8n',
      }
    }
  }
}];
"""
    nodes.append(code_node(
        name="Prepare Audit Log",
        js_code=audit_prep_js,
        position=[3700, 250],
    ))

    nodes.append(portal_status_webhook(
        name="Audit Log - Invoice Sent",
        action="audit_log",
        position=[3920, 250],
    ))

    # ── 20. Respond Webhook ──────────────────────────────────
    respond_js = r"""
const data = $('Merge Send Results').first().json;

return [{
  json: {
    success: true,
    message: `Invoice ${data.invoice_number} sent successfully`,
    invoice_id: data.invoice_id,
    channel: data.preferred_channel,
    sent_at: new Date().toISOString(),
  }
}];
"""
    nodes.append(code_node(
        name="Prepare Response",
        js_code=respond_js,
        position=[4140, 250],
    ))

    nodes.append({
        "parameters": {
            "respondWith": "json",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Webhook",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [4360, 250],
        "typeVersion": 1.1,
    })

    return nodes


# ================================================================
# CONNECTIONS
# ================================================================


def build_connections() -> dict:
    """Build connections for ACCT-03."""
    return {
        # ── Triggers → Merge Trigger Context ─────────────────
        "Webhook - Send Invoice": {
            "main": [[conn("Merge Trigger Context")]]
        },
        "Schedule - Hourly Check": {
            "main": [[conn("Merge Trigger Context")]]
        },
        "Manual Trigger": {
            "main": [[conn("Merge Trigger Context")]]
        },

        # ── Main pipeline ────────────────────────────────────
        "Merge Trigger Context": {
            "main": [[conn("Load Config")]]
        },
        "Load Config": {
            "main": [[conn("Fetch Invoice(s)")]]
        },
        "Fetch Invoice(s)": {
            "main": [[conn("Has Invoice?")]]
        },

        # ── Has Invoice? → True: Fetch Customer, False: nothing
        "Has Invoice?": {
            "main": [
                [conn("Fetch Customer")],   # True
                [],                          # False
            ]
        },

        # ── Customer → Channel Switch ────────────────────────
        "Fetch Customer": {
            "main": [[conn("Check Channel")]]
        },

        # ── Check Channel outputs ────────────────────────────
        #    0=email, 1=whatsapp, 2=both, 3=fallback (default=email)
        "Check Channel": {
            "main": [
                [conn("Build Email HTML")],                                     # email
                [conn("Build WhatsApp Message")],                               # whatsapp
                [conn("Build Email HTML"), conn("Build WhatsApp Message")],      # both
                [conn("Build Email HTML")],                                     # fallback
            ]
        },

        # ── Email path ───────────────────────────────────────
        "Build Email HTML": {
            "main": [[conn("Send Email")]]
        },
        "Send Email": {
            "main": [[conn("Merge Send Results")]]
        },

        # ── WhatsApp path ────────────────────────────────────
        "Build WhatsApp Message": {
            "main": [[conn("Send WhatsApp")]]
        },
        "Send WhatsApp": {
            "main": [[conn("Merge Send Results")]]
        },

        # ── Post-send pipeline ───────────────────────────────
        "Merge Send Results": {
            "main": [[conn("Prepare Status Update")]]
        },
        "Prepare Status Update": {
            "main": [[conn("Update Invoice Status")]]
        },
        "Update Invoice Status": {
            "main": [[conn("Schedule First Reminder")]]
        },
        "Schedule First Reminder": {
            "main": [[conn("Update Reminder Schedule")]]
        },

        # ── Fan-out: portal webhooks + audit ─────────────────
        "Update Reminder Schedule": {
            "main": [[
                conn("Log Collection Entry"),
                conn("Status - Invoice Sent"),
                conn("Prepare Audit Log"),
                conn("Prepare Response"),
            ]]
        },

        # ── Audit chain ─────────────────────────────────────
        "Prepare Audit Log": {
            "main": [[conn("Audit Log - Invoice Sent")]]
        },

        # ── Webhook response ─────────────────────────────────
        "Prepare Response": {
            "main": [[conn("Respond Webhook")]]
        },
    }


# ================================================================
# BUILD, DEPLOY, ACTIVATE
# ================================================================


def build() -> dict:
    """Assemble the complete workflow JSON."""
    nodes = build_nodes()
    connections = build_connections()
    return build_workflow_json(WORKFLOW_NAME, nodes, connections)


def save(workflow: dict) -> Path:
    """Save workflow JSON to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILENAME

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_stats(workflow: dict) -> None:
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])
    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


def main() -> None:
    args = sys.argv[1:]
    action = args[0] if args else "build"

    if action not in ("build", "deploy", "activate"):
        print(f"Usage: python {Path(__file__).name} [build|deploy|activate]")
        sys.exit(1)

    print("=" * 60)
    print("ACCT-03 INVOICE SENDING & NOTIFICATIONS")
    print("=" * 60)

    # ── Build ─────────────────────────────────────────────────
    print("\nBuilding workflow...")
    workflow = build()
    output_path = save(workflow)
    print_stats(workflow)
    print(f"  Saved to: {output_path}")

    if action == "build":
        print("\n" + "=" * 60)
        print("BUILD COMPLETE")
        print("=" * 60)
        print("\nRun with 'deploy' to push to n8n (inactive).")
        print("Run with 'activate' to push and activate.")
        return

    # ── Deploy ────────────────────────────────────────────────
    from config_loader import load_config
    from n8n_client import N8nClient

    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = config["n8n"]["base_url"]

    print(f"\nConnecting to {base_url}...")

    with N8nClient(
        base_url,
        api_key,
        timeout=config["n8n"].get("timeout_seconds", 30),
        cache_dir=config["paths"]["cache_dir"],
    ) as client:
        health = client.health_check()
        if not health["connected"]:
            print(f"  ERROR: Cannot connect to n8n: {health.get('error')}")
            sys.exit(1)
        print("  Connected!")

        # Check for existing workflow by name
        existing = None
        try:
            all_wfs = client.list_workflows()
            for wf in all_wfs:
                if wf["name"] == WORKFLOW_NAME:
                    existing = wf
                    break
        except Exception:
            pass

        payload = {
            "name": workflow["name"],
            "nodes": workflow["nodes"],
            "connections": workflow["connections"],
            "settings": workflow["settings"],
        }

        if existing:
            result = client.update_workflow(existing["id"], payload)
            wf_id = result.get("id")
            print(f"  Updated: {result.get('name')} (ID: {wf_id})")
        else:
            result = client.create_workflow(payload)
            wf_id = result.get("id")
            print(f"  Created: {result.get('name')} (ID: {wf_id})")

        # ── Activate ──────────────────────────────────────────
        if action == "activate" and wf_id:
            print(f"  Activating {WORKFLOW_NAME}...")
            client.activate_workflow(wf_id)
            print("  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"\n  Workflow ID: {wf_id}")
    print(f"  Status: {'active' if action == 'activate' else 'inactive'}")
    print()
    print("Next steps:")
    print("  1. Open workflow in n8n UI to verify node connections")
    print("  2. Test with manual trigger first")
    print("  3. Test webhook: POST /accounting/send-invoice {invoice_id, client_id}")
    print("  4. Verify email delivery and WhatsApp (if configured)")
    print("  5. Check portal audit log for INVOICE_SENT event")
    print("  6. Confirm next_reminder_at set on invoice record")


if __name__ == "__main__":
    main()
