"""
ACCT-04 Collections & Follow-ups (Plug-and-Play Accounting v2)

Daily at 07:00 SAST: finds overdue invoices, determines reminder tier,
sends tiered emails (friendly / firm / escalation), updates invoice state,
logs collection activity, and creates escalation tasks when needed.

Webhook handler: receives POP-received events from the portal and updates
the invoice accordingly.

Node count: ~30 functional nodes

Usage:
    python tools/deploy_acct_v2_wf04.py build      # Save JSON locally
    python tools/deploy_acct_v2_wf04.py deploy      # Push to n8n Cloud
    python tools/deploy_acct_v2_wf04.py activate    # Enable triggers
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────
_TOOLS_DIR = Path(__file__).parent
_PROJECT_ROOT = _TOOLS_DIR.parent
sys.path.insert(0, str(_TOOLS_DIR))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from acct_helpers import (
    uid,
    schedule_trigger,
    manual_trigger,
    webhook_trigger,
    supabase_select,
    supabase_insert,
    supabase_update,
    portal_status_webhook,
    code_node,
    set_node,
    if_node,
    switch_node,
    gmail_send,
    build_workflow_json,
    conn,
    respond_webhook,
    SUPABASE_URL,
    SUPABASE_KEY,
    PORTAL_URL,
    N8N_WEBHOOK_SECRET,
)
from credentials import CREDENTIALS

CRED_GMAIL = CREDENTIALS["gmail"]

# ── Constants ─────────────────────────────────────────────────
WORKFLOW_NAME = "ACCT-04 Collections & Follow-ups"
OUTPUT_DIR = _PROJECT_ROOT / "workflows" / "accounting-v2"
OUTPUT_FILE = "wf04_collections.json"


# ==============================================================
# NODE BUILDERS
# ==============================================================

def _build_nodes() -> list[dict[str, Any]]:
    """Build all ~30 nodes for WF04."""
    nodes: list[dict[str, Any]] = []

    # ── Sticky note ───────────────────────────────────────────
    nodes.append({
        "parameters": {
            "content": (
                "## ACCT-04 Collections & Follow-ups\n"
                "Daily 07:00 SAST: overdue invoice scan, tiered reminders,\n"
                "escalation tasks.  Webhook: POP-received from portal."
            ),
            "width": 460,
            "height": 100,
            "color": 5,
        },
        "id": uid(),
        "name": "Note - Overview",
        "type": "n8n-nodes-base.stickyNote",
        "position": [180, 60],
        "typeVersion": 1,
    })

    # ── 1. Schedule Trigger (daily 07:00 SAST = 05:00 UTC) ───
    nodes.append(schedule_trigger(
        "Daily 07:00 SAST", "0 5 * * *", [220, 300],
    ))

    # ── 2. Manual Trigger ─────────────────────────────────────
    nodes.append(manual_trigger([220, 500]))

    # ── 3. Webhook Trigger (POP received from portal) ─────────
    nodes.append(webhook_trigger(
        "Webhook - Collection Action",
        "accounting/collection-action",
        [220, 720],
    ))

    # ──────────────────────────────────────────────────────────
    # SCHEDULE / MANUAL PATH
    # ──────────────────────────────────────────────────────────

    # ── 4. Load Config ────────────────────────────────────────
    nodes.append(supabase_select(
        "Load Config",
        "acct_config",
        select="*",
        filters="",
        position=[480, 400],
        single=True,
    ))

    # ── 5. Find Overdue Invoices ──────────────────────────────
    # status IN (sent, payment_pending, overdue) AND due_date <= today AND balance_due > 0
    nodes.append(code_node(
        "Find Overdue Invoices",
        js_code=_js_find_overdue(),
        position=[720, 400],
    ))

    # ── 6. Has Overdue? ───────────────────────────────────────
    nodes.append(if_node(
        "Has Overdue?",
        left_value="{{ $json.overdueCount }}",
        operator_type="number",
        operation="gt",
        right_value="0",
        position=[960, 400],
    ))

    # ── 7. Loop Over Invoices (splitInBatches) ────────────────
    nodes.append({
        "parameters": {"batchSize": 1, "options": {}},
        "id": uid(),
        "name": "Loop Over Invoices",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1200, 400],
        "typeVersion": 3,
    })

    # ── 8. Fetch Customer ─────────────────────────────────────
    nodes.append(code_node(
        "Fetch Customer",
        js_code=_js_fetch_customer(),
        position=[1440, 500],
    ))

    # ── 9. Determine Reminder Tier ────────────────────────────
    nodes.append(code_node(
        "Determine Reminder Tier",
        js_code=_js_determine_tier(),
        position=[1680, 500],
    ))

    # ── 10. Should Send Reminder? ─────────────────────────────
    nodes.append(if_node(
        "Should Send Reminder?",
        left_value="{{ $json.shouldSend }}",
        operator_type="boolean",
        operation="true",
        position=[1920, 500],
    ))

    # ── 11. Select Template (Switch on tier) ──────────────────
    nodes.append(switch_node(
        "Select Template",
        rules=[
            {"leftValue": "={{ $json.tier }}", "rightValue": "1", "output": "friendly"},
            {"leftValue": "={{ $json.tier }}", "rightValue": "2", "output": "firm"},
            {"leftValue": "={{ $json.tier }}", "rightValue": "3", "output": "escalation"},
        ],
        position=[2160, 500],
    ))

    # ── 12-14. Build Reminder Emails (one per tier) ───────────
    nodes.append(code_node(
        "Build Friendly Email",
        js_code=_js_build_email("friendly"),
        position=[2400, 300],
    ))

    nodes.append(code_node(
        "Build Firm Email",
        js_code=_js_build_email("firm"),
        position=[2400, 540],
    ))

    nodes.append(code_node(
        "Build Escalation Email",
        js_code=_js_build_email("escalation"),
        position=[2400, 780],
    ))

    # ── 15. Merge Email Outputs ───────────────────────────────
    # Using a code node that just passes through (simpler than Merge for 3 inputs)
    nodes.append(code_node(
        "Merge Email Output",
        js_code="return $input.all();",
        position=[2640, 540],
    ))

    # ── 16. Send Reminder Email ───────────────────────────────
    nodes.append(gmail_send(
        "Send Reminder Email",
        to_expr="{{ $json.customerEmail }}",
        subject_expr="{{ $json.emailSubject }}",
        html_expr="{{ $json.emailHtml }}",
        cred=CRED_GMAIL,
        position=[2880, 540],
    ))

    # ── 17. Prep Update Payload ───────────────────────────────
    nodes.append(code_node(
        "Prep Invoice Update",
        js_code=_js_prep_invoice_update(),
        position=[3120, 540],
    ))

    # ── 18. Update Invoice ────────────────────────────────────
    nodes.append(supabase_update(
        "Update Invoice",
        "acct_invoices",
        match_col="id",
        position=[3360, 540],
    ))

    # ── 19. Log Collection (portal webhook) ───────────────────
    nodes.append(code_node(
        "Prep Collection Log",
        js_code=_js_prep_collection_log(),
        position=[3600, 440],
    ))

    nodes.append(portal_status_webhook(
        "Log Collection",
        action="collection_logged",
        position=[3840, 440],
    ))

    # ── 20. Check Escalation ──────────────────────────────────
    nodes.append(if_node(
        "Check Escalation",
        left_value="{{ $json.daysOverdue }}",
        operator_type="number",
        operation="gte",
        right_value="{{ $json.escalationAfterDays }}",
        position=[3600, 700],
    ))

    # ── 21. Create Escalation Task ────────────────────────────
    nodes.append(code_node(
        "Prep Escalation Task",
        js_code=_js_prep_escalation_task(),
        position=[3840, 660],
    ))

    nodes.append(portal_status_webhook(
        "Create Escalation Task",
        action="task_created",
        position=[4080, 660],
    ))

    # ── 22. Audit Log ─────────────────────────────────────────
    nodes.append(code_node(
        "Prep Audit Log",
        js_code=_js_prep_audit_log(),
        position=[3840, 880],
    ))

    nodes.append(portal_status_webhook(
        "Audit Log",
        action="audit_log",
        position=[4080, 880],
    ))

    # ── 23. Status Update (portal webhook) ────────────────────
    nodes.append(portal_status_webhook(
        "Status Update",
        action="invoice_updated",
        position=[4320, 540],
    ))

    # ── 24. Loop back ─────────────────────────────────────────
    # (No-op to feed back into splitInBatches)
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Next Invoice",
        "type": "n8n-nodes-base.noOp",
        "position": [4560, 540],
        "typeVersion": 1,
    })

    # ── 25. No Overdue (no-op) ────────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "No Overdue Invoices",
        "type": "n8n-nodes-base.noOp",
        "position": [1200, 660],
        "typeVersion": 1,
    })

    # ── 26. Skip Reminder (no-op — tier already sent) ─────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Skip Reminder",
        "type": "n8n-nodes-base.noOp",
        "position": [2160, 740],
        "typeVersion": 1,
    })

    # ──────────────────────────────────────────────────────────
    # WEBHOOK PATH (POP received)
    # ──────────────────────────────────────────────────────────

    # ── W1. Validate Webhook ──────────────────────────────────
    nodes.append(code_node(
        "Validate Webhook",
        js_code=_js_validate_webhook(),
        position=[480, 720],
    ))

    # ── W2. Update Invoice POP ────────────────────────────────
    nodes.append(code_node(
        "Prep POP Update",
        js_code=_js_prep_pop_update(),
        position=[720, 720],
    ))

    nodes.append(supabase_update(
        "Update Invoice POP",
        "acct_invoices",
        match_col="id",
        position=[960, 720],
    ))

    # ── W3. Log POP Received ──────────────────────────────────
    nodes.append(code_node(
        "Prep POP Log",
        js_code=_js_prep_pop_log(),
        position=[1200, 720],
    ))

    nodes.append(portal_status_webhook(
        "Log POP Received",
        action="collection_logged",
        position=[1440, 720],
    ))

    # ── W4. Create Review Task if needed ──────────────────────
    nodes.append(code_node(
        "Prep POP Review Task",
        js_code=_js_prep_pop_review_task(),
        position=[1680, 720],
    ))

    nodes.append(portal_status_webhook(
        "Create POP Review Task",
        action="task_created",
        position=[1920, 720],
    ))

    # ── W5. Respond Webhook ───────────────────────────────────
    nodes.append(respond_webhook(
        "Respond Webhook",
        position=[2160, 720],
    ))

    return nodes


# ==============================================================
# CONNECTIONS
# ==============================================================

def _build_connections() -> dict[str, Any]:
    """Build the full connection map."""
    return {
        # ── Triggers → Load Config ────────────────────────────
        "Daily 07:00 SAST": {
            "main": [[conn("Load Config")]]
        },
        "Manual Trigger": {
            "main": [[conn("Load Config")]]
        },

        # ── Schedule path ─────────────────────────────────────
        "Load Config": {
            "main": [[conn("Find Overdue Invoices")]]
        },
        "Find Overdue Invoices": {
            "main": [[conn("Has Overdue?")]]
        },
        "Has Overdue?": {
            "main": [
                # True — has overdue
                [conn("Loop Over Invoices")],
                # False — nothing to do
                [conn("No Overdue Invoices")],
            ]
        },

        # splitInBatches v3: output 0 = done, output 1 = each item
        "Loop Over Invoices": {
            "main": [
                [],  # done — no further action
                [conn("Fetch Customer")],  # each invoice
            ]
        },
        "Fetch Customer": {
            "main": [[conn("Determine Reminder Tier")]]
        },
        "Determine Reminder Tier": {
            "main": [[conn("Should Send Reminder?")]]
        },
        "Should Send Reminder?": {
            "main": [
                # True — send reminder
                [conn("Select Template")],
                # False — skip
                [conn("Skip Reminder")],
            ]
        },
        "Skip Reminder": {
            "main": [[conn("Loop Over Invoices")]]
        },

        # Switch outputs: friendly=0, firm=1, escalation=2, fallback=3
        "Select Template": {
            "main": [
                [conn("Build Friendly Email")],
                [conn("Build Firm Email")],
                [conn("Build Escalation Email")],
                [],  # fallback — shouldn't happen
            ]
        },

        # All three email builders → merge
        "Build Friendly Email": {
            "main": [[conn("Merge Email Output")]]
        },
        "Build Firm Email": {
            "main": [[conn("Merge Email Output")]]
        },
        "Build Escalation Email": {
            "main": [[conn("Merge Email Output")]]
        },

        "Merge Email Output": {
            "main": [[conn("Send Reminder Email")]]
        },
        "Send Reminder Email": {
            "main": [[conn("Prep Invoice Update")]]
        },
        "Prep Invoice Update": {
            "main": [[conn("Update Invoice")]]
        },
        "Update Invoice": {
            "main": [[
                conn("Prep Collection Log"),
                conn("Check Escalation"),
                conn("Prep Audit Log"),
            ]]
        },

        # Collection log path
        "Prep Collection Log": {
            "main": [[conn("Log Collection")]]
        },
        "Log Collection": {
            "main": [[conn("Status Update")]]
        },
        "Status Update": {
            "main": [[conn("Next Invoice")]]
        },

        # Escalation check path
        "Check Escalation": {
            "main": [
                # True — needs escalation
                [conn("Prep Escalation Task")],
                # False — no escalation needed
                [],
            ]
        },
        "Prep Escalation Task": {
            "main": [[conn("Create Escalation Task")]]
        },

        # Audit log path
        "Prep Audit Log": {
            "main": [[conn("Audit Log")]]
        },

        # Loop back
        "Next Invoice": {
            "main": [[conn("Loop Over Invoices")]]
        },

        # ── Webhook path (POP received) ──────────────────────
        "Webhook - Collection Action": {
            "main": [[conn("Validate Webhook")]]
        },
        "Validate Webhook": {
            "main": [[conn("Prep POP Update")]]
        },
        "Prep POP Update": {
            "main": [[conn("Update Invoice POP")]]
        },
        "Update Invoice POP": {
            "main": [[conn("Prep POP Log")]]
        },
        "Prep POP Log": {
            "main": [[conn("Log POP Received")]]
        },
        "Log POP Received": {
            "main": [[conn("Prep POP Review Task")]]
        },
        "Prep POP Review Task": {
            "main": [[conn("Create POP Review Task")]]
        },
        "Create POP Review Task": {
            "main": [[conn("Respond Webhook")]]
        },
    }


# ==============================================================
# JAVASCRIPT CODE (per node)
# ==============================================================

def _js_find_overdue() -> str:
    return f"""\
// Fetch overdue invoices from Supabase
const config = $input.first().json;

const today = new Date().toISOString().split('T')[0];

// Query: status IN (sent, payment_pending, overdue) AND due_date <= today AND balance_due > 0
const url = '{SUPABASE_URL}/rest/v1/acct_invoices'
  + '?select=*'
  + '&status=in.(sent,payment_pending,overdue)'
  + '&due_date=lte.' + today
  + '&balance_due=gt.0'
  + '&order=due_date.asc';

const resp = await fetch(url, {{
  method: 'GET',
  headers: {{
    'apikey': '{SUPABASE_KEY}',
    'Authorization': 'Bearer {SUPABASE_KEY}',
    'Accept': 'application/json',
  }},
}});

if (!resp.ok) {{
  throw new Error('Supabase query failed: ' + resp.status + ' ' + (await resp.text()));
}}

const invoices = await resp.json();

if (invoices.length === 0) {{
  return [{{ json: {{ overdueCount: 0, invoices: [], config }} }}];
}}

// Pass config along for later use
return [{{ json: {{
  overdueCount: invoices.length,
  invoices,
  config,
  reminderCadenceDays: config.reminder_cadence_days || [-3, 0, 3, 7, 14],
  escalationAfterDays: config.escalation_after_days || 30,
}} }}];
"""


def _js_fetch_customer() -> str:
    return f"""\
// Fetch the customer record for the current invoice
const invoice = $input.first().json;
const customerId = invoice.customer_id;

if (!customerId) {{
  return [{{ json: {{ ...invoice, customer: null, customerEmail: null, customerName: 'Unknown' }} }}];
}}

const url = '{SUPABASE_URL}/rest/v1/acct_customers'
  + '?select=*'
  + '&id=eq.' + customerId;

const resp = await fetch(url, {{
  method: 'GET',
  headers: {{
    'apikey': '{SUPABASE_KEY}',
    'Authorization': 'Bearer {SUPABASE_KEY}',
    'Accept': 'application/vnd.pgrst.object+json',
  }},
}});

let customer = null;
let customerEmail = null;
let customerName = 'Valued Customer';

if (resp.ok) {{
  customer = await resp.json();
  customerEmail = customer.email || customer.billing_email || null;
  customerName = customer.name || customer.company_name || 'Valued Customer';
}}

return [{{ json: {{
  ...invoice,
  customer,
  customerEmail,
  customerName,
}} }}];
"""


def _js_determine_tier() -> str:
    return """\
// Determine reminder tier based on days overdue vs cadence
const item = $input.first().json;
const now = new Date();
const dueDate = new Date(item.due_date);
const daysOverdue = Math.floor((now - dueDate) / (1000 * 60 * 60 * 24));

// Default cadence: [-3, 0, 3, 7, 14]
const cadence = item.reminderCadenceDays
  || $('Find Overdue Invoices').first().json.reminderCadenceDays
  || [-3, 0, 3, 7, 14];

const escalationAfterDays = item.escalationAfterDays
  || $('Find Overdue Invoices').first().json.escalationAfterDays
  || 30;

// Determine tier:
//   tier 1 = friendly  (0-3 days overdue)
//   tier 2 = firm      (4-14 days overdue)
//   tier 3 = escalation (14+ days overdue)
let tier = 1;
if (daysOverdue >= 14) {
  tier = 3;
} else if (daysOverdue >= 4) {
  tier = 2;
}

const currentReminderCount = parseInt(item.reminder_count || '0', 10);

// Only send if this tier hasn't been sent yet
const shouldSend = tier > currentReminderCount;

return [{
  json: {
    ...item,
    daysOverdue,
    tier,
    tierLabel: tier === 1 ? 'friendly' : tier === 2 ? 'firm' : 'escalation',
    shouldSend,
    currentReminderCount,
    escalationAfterDays,
  }
}];
"""


def _js_build_email(tier: str) -> str:
    """Return JS that builds HTML email for the given tier."""
    if tier == "friendly":
        return _js_email_friendly()
    if tier == "firm":
        return _js_email_firm()
    return _js_email_escalation()


def _js_email_friendly() -> str:
    return r"""
const item = $input.first().json;
const balanceFmt = parseFloat(item.balance_due || 0).toLocaleString('en-ZA', {minimumFractionDigits: 2});

const html = `<div style="font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
  <div style="padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;">
    <h1 style="margin:0;font-size:22px;color:#1A1A2E;">AnyVision Media</h1>
  </div>
  <div style="padding:30px 40px;">
    <p style="margin:0 0 16px;font-size:15px;color:#333;">Hi ${item.customerName},</p>
    <p style="margin:0 0 16px;font-size:15px;color:#333;">
      Just a friendly heads up that invoice <strong>${item.invoice_number || item.id}</strong> for
      <strong>R ${balanceFmt}</strong> is due on <strong>${item.due_date}</strong>.
    </p>
    <p style="margin:0 0 16px;font-size:15px;color:#333;">
      If you've already arranged payment, please disregard this message.
    </p>
    <p style="margin:0 0 16px;font-size:15px;color:#333;">
      Need to discuss payment options? Just reply to this email and we'll be happy to help.
    </p>
    <p style="margin:24px 0 0;font-size:15px;color:#333;">
      Best regards,<br><strong>AnyVision Media</strong><br>
      <span style="color:#666;">Accounts Department</span>
    </p>
  </div>
  <div style="padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;">
    <p style="margin:0;font-size:11px;color:#999;line-height:1.5;">
      AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com
    </p>
  </div>
</div>`;

return [{
  json: {
    ...item,
    emailSubject: `Friendly Reminder: Invoice ${item.invoice_number || item.id} Due`,
    emailHtml: html,
  }
}];
"""


def _js_email_firm() -> str:
    return r"""
const item = $input.first().json;
const balanceFmt = parseFloat(item.balance_due || 0).toLocaleString('en-ZA', {minimumFractionDigits: 2});

const html = `<div style="font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
  <div style="padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;">
    <h1 style="margin:0;font-size:22px;color:#1A1A2E;">AnyVision Media</h1>
  </div>
  <div style="padding:30px 40px;">
    <p style="margin:0 0 16px;font-size:15px;color:#333;">Dear ${item.customerName},</p>
    <p style="margin:0 0 16px;font-size:15px;color:#333;">
      This is a reminder that payment of <strong>R ${balanceFmt}</strong> for invoice
      <strong>${item.invoice_number || item.id}</strong> is now <strong>${item.daysOverdue} days overdue</strong>.
    </p>
    <p style="margin:0 0 16px;font-size:15px;color:#333;">
      We understand that payments can sometimes be delayed. Please arrange payment as soon as possible,
      or contact us if you are experiencing any difficulties.
    </p>
    <div style="margin:16px 0;padding:16px;background:#FFF3CD;border-left:3px solid #FF6D5A;">
      <p style="margin:0;font-size:14px;color:#856404;">
        <strong>Invoice:</strong> ${item.invoice_number || item.id}<br>
        <strong>Amount Due:</strong> R ${balanceFmt}<br>
        <strong>Original Due Date:</strong> ${item.due_date}<br>
        <strong>Days Overdue:</strong> ${item.daysOverdue}
      </p>
    </div>
    <p style="margin:16px 0 0;font-size:15px;color:#333;">
      Please send proof of payment to
      <a href="mailto:accounts@anyvisionmedia.com" style="color:#FF6D5A;">accounts@anyvisionmedia.com</a>.
    </p>
    <p style="margin:24px 0 0;font-size:15px;color:#333;">
      Regards,<br><strong>AnyVision Media</strong><br>
      <span style="color:#666;">Accounts Department</span>
    </p>
  </div>
  <div style="padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;">
    <p style="margin:0;font-size:11px;color:#999;line-height:1.5;">
      AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com
    </p>
  </div>
</div>`;

return [{
  json: {
    ...item,
    emailSubject: `Payment Reminder: Invoice ${item.invoice_number || item.id} — ${item.daysOverdue} Days Overdue`,
    emailHtml: html,
  }
}];
"""


def _js_email_escalation() -> str:
    return r"""
const item = $input.first().json;
const balanceFmt = parseFloat(item.balance_due || 0).toLocaleString('en-ZA', {minimumFractionDigits: 2});

const html = `<div style="font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
  <div style="padding:30px 40px 20px;border-bottom:3px solid #dc2626;">
    <h1 style="margin:0;font-size:22px;color:#1A1A2E;">AnyVision Media</h1>
    <p style="margin:5px 0 0;font-size:12px;color:#dc2626;text-transform:uppercase;letter-spacing:1px;">Overdue Account Notice</p>
  </div>
  <div style="padding:30px 40px;">
    <p style="margin:0 0 16px;font-size:15px;color:#333;">Dear ${item.customerName},</p>
    <p style="margin:0 0 16px;font-size:15px;color:#333;">
      Despite previous reminders, your account remains <strong>${item.daysOverdue} days overdue</strong>.
      The outstanding amount of <strong>R ${balanceFmt}</strong> for invoice
      <strong>${item.invoice_number || item.id}</strong> requires your immediate attention.
    </p>
    <div style="margin:16px 0;padding:16px;background:#FEE2E2;border-left:3px solid #dc2626;">
      <p style="margin:0;font-size:14px;color:#991B1B;">
        <strong>OVERDUE SUMMARY</strong><br><br>
        <strong>Invoice:</strong> ${item.invoice_number || item.id}<br>
        <strong>Amount Due:</strong> R ${balanceFmt}<br>
        <strong>Original Due Date:</strong> ${item.due_date}<br>
        <strong>Days Overdue:</strong> ${item.daysOverdue}<br>
        <strong>Previous Reminders Sent:</strong> ${item.currentReminderCount}
      </p>
    </div>
    <p style="margin:16px 0;font-size:15px;color:#333;">
      Please arrange immediate payment to avoid further action. If there are any issues preventing
      payment, please contact us urgently so we can discuss a resolution.
    </p>
    <p style="margin:0 0 16px;font-size:15px;color:#333;">
      Payment can be made via EFT using reference <strong>${item.invoice_number || item.id}</strong>, or by
      contacting us at <a href="mailto:accounts@anyvisionmedia.com" style="color:#FF6D5A;">accounts@anyvisionmedia.com</a>.
    </p>
    <p style="margin:24px 0 0;font-size:15px;color:#333;">
      Regards,<br><strong>AnyVision Media</strong><br>
      <span style="color:#666;">Accounts Department</span>
    </p>
  </div>
  <div style="padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;">
    <p style="margin:0;font-size:11px;color:#999;line-height:1.5;">
      AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com<br>
      This is an automated reminder. If payment has already been made, please disregard.
    </p>
  </div>
</div>`;

return [{
  json: {
    ...item,
    emailSubject: `URGENT: Invoice ${item.invoice_number || item.id} — ${item.daysOverdue} Days Overdue`,
    emailHtml: html,
  }
}];
"""


def _js_prep_invoice_update() -> str:
    return """\
// Prepare the Supabase PATCH payload for the invoice
const item = $input.first().json;
const now = new Date().toISOString();

// Calculate next reminder date based on cadence
const cadence = item.reminderCadenceDays
  || $('Find Overdue Invoices').first().json.reminderCadenceDays
  || [-3, 0, 3, 7, 14];
const newCount = item.tier;  // tier IS the new reminder_count
const nextCadenceIdx = cadence.findIndex(d => d > item.daysOverdue);
let nextReminderAt = null;
if (nextCadenceIdx !== -1) {
  const nextDays = cadence[nextCadenceIdx];
  const due = new Date(item.due_date);
  due.setDate(due.getDate() + nextDays);
  nextReminderAt = due.toISOString().split('T')[0];
}

const newStatus = item.daysOverdue > 0 ? 'overdue' : item.status;

return [{
  json: {
    id: item.id,
    updatePayload: {
      reminder_count: newCount,
      last_reminder_at: now,
      next_reminder_at: nextReminderAt,
      status: newStatus,
      updated_at: now,
    },
    // Pass through for downstream nodes
    invoiceId: item.id,
    invoiceNumber: item.invoice_number || item.id,
    customerId: item.customer_id,
    customerName: item.customerName,
    customerEmail: item.customerEmail,
    balanceDue: item.balance_due,
    daysOverdue: item.daysOverdue,
    tier: item.tier,
    tierLabel: item.tierLabel,
    escalationAfterDays: item.escalationAfterDays,
    newStatus,
  }
}];
"""


def _js_prep_collection_log() -> str:
    return """\
// Prepare portal webhook payload for collection log
const item = $input.first().json;
return [{
  json: {
    invoice_id: item.invoiceId || item.id,
    invoice_number: item.invoiceNumber || item.invoice_number,
    customer_id: item.customerId || item.customer_id,
    customer_name: item.customerName,
    tier: item.tier,
    tier_label: item.tierLabel,
    channel: 'email',
    status: 'reminder_sent',
    days_overdue: item.daysOverdue || item.daysOverdue,
    amount_due: item.balanceDue || item.balance_due,
    timestamp: new Date().toISOString(),
  }
}];
"""


def _js_prep_escalation_task() -> str:
    return """\
// Prepare escalation task for portal
const item = $input.first().json;
return [{
  json: {
    type: 'dispute_resolution',
    priority: 'high',
    title: `Escalation: Invoice ${item.invoiceNumber || item.invoice_number} — ${item.daysOverdue} days overdue`,
    description: `Customer ${item.customerName} owes R ${item.balanceDue || item.balance_due} (${item.daysOverdue} days overdue). All reminder tiers exhausted.`,
    invoice_id: item.invoiceId || item.id,
    customer_id: item.customerId || item.customer_id,
    assigned_to: 'accounts_manager',
    due_date: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    timestamp: new Date().toISOString(),
  }
}];
"""


def _js_prep_audit_log() -> str:
    return """\
// Prepare audit log entry
const item = $input.first().json;
return [{
  json: {
    client_id: item.customerId || item.customer_id,
    event_type: 'INVOICE_OVERDUE',
    entity_type: 'invoice',
    entity_id: item.invoiceId || item.id,
    action: 'collection_reminder_sent',
    actor: 'n8n_wf04_collections',
    result: 'success',
    metadata: {
      tier: item.tier,
      tier_label: item.tierLabel,
      days_overdue: item.daysOverdue,
      balance_due: item.balanceDue || item.balance_due,
      source: 'n8n',
    },
  }
}];
"""


def _js_validate_webhook() -> str:
    return """\
// Validate incoming webhook payload
const body = $input.first().json;

const invoiceId = body.invoice_id || body.invoiceId;
const popUrl = body.pop_url || body.popUrl;
const clientId = body.client_id || body.clientId;

if (!invoiceId) {
  throw new Error('Missing required field: invoice_id');
}

return [{
  json: {
    invoice_id: invoiceId,
    pop_url: popUrl || null,
    client_id: clientId || null,
    action: body.action || 'pop_received',
    timestamp: new Date().toISOString(),
  }
}];
"""


def _js_prep_pop_update() -> str:
    return """\
// Prepare Supabase PATCH for POP received
const item = $input.first().json;
const now = new Date().toISOString();

return [{
  json: {
    id: item.invoice_id,
    updatePayload: {
      pop_received: true,
      pop_url: item.pop_url,
      pop_received_at: now,
      status: 'pop_received',
      updated_at: now,
    },
    invoice_id: item.invoice_id,
    client_id: item.client_id,
    pop_url: item.pop_url,
  }
}];
"""


def _js_prep_pop_log() -> str:
    return """\
// Prepare collection log for POP received
const item = $input.first().json;
return [{
  json: {
    invoice_id: item.invoice_id,
    client_id: item.client_id,
    status: 'pop_received',
    channel: 'portal',
    pop_url: item.pop_url,
    timestamp: new Date().toISOString(),
  }
}];
"""


def _js_prep_pop_review_task() -> str:
    return """\
// Create a review task for the received POP
const item = $input.first().json;
return [{
  json: {
    type: 'pop_review',
    priority: 'medium',
    title: `Review POP: Invoice ${item.invoice_id}`,
    description: `Proof of payment received for invoice ${item.invoice_id}. Please verify and allocate.`,
    invoice_id: item.invoice_id,
    client_id: item.client_id,
    pop_url: item.pop_url,
    assigned_to: 'accounts',
    due_date: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    status: 'ok',
    message: 'POP received and logged successfully',
    timestamp: new Date().toISOString(),
  }
}];
"""


# ==============================================================
# ASSEMBLY
# ==============================================================

def build_workflow() -> dict[str, Any]:
    """Assemble the complete workflow JSON."""
    nodes = _build_nodes()
    connections = _build_connections()
    return build_workflow_json(WORKFLOW_NAME, nodes, connections)


def save_workflow(workflow: dict[str, Any]) -> Path:
    """Save workflow JSON to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILE
    output_path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    return output_path


def print_stats(workflow: dict[str, Any]) -> None:
    """Print workflow statistics."""
    nodes = workflow["nodes"]
    functional = [n for n in nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    print(f"\n  Workflow: {workflow['name']}")
    print(f"  Nodes:    {len(nodes)} total ({len(functional)} functional)")
    print(f"  Connections: {len(workflow['connections'])} sources")

    # Count by type
    type_counts: dict[str, int] = {}
    for n in functional:
        t = n["type"].replace("n8n-nodes-base.", "")
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")


# ==============================================================
# CLI
# ==============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ACCT-04 Collections & Follow-ups — Builder & Deployer",
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="build",
        choices=["build", "deploy", "activate"],
    )
    parsed = parser.parse_args()
    action: str = parsed.action

    print("=" * 60)
    print("ACCT-04 COLLECTIONS & FOLLOW-UPS")
    print("=" * 60)

    # ── Build ─────────────────────────────────────────────────
    print("\nBuilding workflow...")
    workflow = build_workflow()
    output_path = save_workflow(workflow)
    print_stats(workflow)
    print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # ── Deploy / Activate ─────────────────────────────────────
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
            print(f"  ERROR: Cannot connect: {health.get('error')}")
            sys.exit(1)
        print("  Connected!")

        # Check for existing workflow by name
        existing = None
        try:
            all_wfs = client.list_workflows()
            for wf in all_wfs:
                if wf["name"] == workflow["name"]:
                    existing = wf
                    break
        except Exception:
            pass

        api_payload = {
            "name": workflow["name"],
            "nodes": workflow["nodes"],
            "connections": workflow["connections"],
            "settings": workflow["settings"],
        }

        if existing:
            wf_id = existing["id"]
            print(f"\n  Updating existing workflow: {wf_id}")
            client.update_workflow(wf_id, api_payload)
        else:
            print("\n  Creating new workflow...")
            result = client.create_workflow(api_payload)
            wf_id = result["id"]
            print(f"  Created with ID: {wf_id}")

        if action == "activate":
            print(f"\n  Activating workflow {wf_id}...")
            client.activate_workflow(wf_id)
            print("  Workflow is now ACTIVE!")
        else:
            print(f"\n  Deployed as INACTIVE. Run with 'activate' to enable.")

    print("\nDone!")


if __name__ == "__main__":
    main()
