"""
ACCT-05: Payment Capture & Reconciliation

Receives payments from Stripe/PayFast/Yoco ITN or manual entry, normalizes
to a standard format, matches against open invoices (exact then AI fuzzy),
applies payment, updates invoice status, sends receipt, syncs to accounting
software, and logs everything.

Triggers:
    1. Webhook POST /accounting/payment-received  (gateway ITN / manual)
    2. Webhook POST /accounting/manual-payment     (portal manual entry)
    3. Schedule daily 06:00                        (bank reconciliation)
    4. Manual trigger                              (testing)

Node count: ~28 functional + sticky notes

Usage:
    python tools/deploy_acct_v2_wf05.py build
    python tools/deploy_acct_v2_wf05.py deploy
    python tools/deploy_acct_v2_wf05.py activate
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── Load environment ───────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# ── Add tools/ to path for sibling imports ─────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from acct_helpers import (
    OPENROUTER_MODEL,
    PORTAL_URL,
    SUPABASE_KEY,
    SUPABASE_URL,
    N8N_WEBHOOK_SECRET,
    build_workflow_json,
    code_node,
    conn,
    gmail_send,
    if_node,
    manual_trigger,
    noop_node,
    openrouter_ai,
    portal_status_webhook,
    schedule_trigger,
    set_node,
    supabase_insert,
    supabase_select,
    supabase_update,
    switch_node,
    uid,
    webhook_trigger,
)
from credentials import CREDENTIALS

CRED_GMAIL = CREDENTIALS["gmail"]
CRED_OPENROUTER = CREDENTIALS["openrouter"]

# ── Workflow metadata ──────────────────────────────────────────
WORKFLOW_NAME = "ACCT-05 Payment Capture & Reconciliation"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILE = "wf05_payments.json"


# ====================================================================
# JAVASCRIPT CODE SNIPPETS
# ====================================================================

NORMALIZE_PAYMENT_JS = r"""
// Normalize gateway-specific payload to standard payment format.
// Supports Stripe, PayFast, Yoco webhooks and manual portal entry.
const raw = $input.first().json;
const body = raw.body || raw;

let amount = 0;        // cents
let referenceText = '';
let method = 'unknown';
let gatewayTransactionId = '';
let clientId = '';
let currency = 'ZAR';
let gateway = 'manual';

// ── Stripe ──────────────────────────────────────────────
if (body.type && body.type.startsWith('payment_intent')) {
  const obj = body.data?.object || {};
  amount = obj.amount || 0;
  referenceText = obj.metadata?.invoice_ref || obj.description || '';
  method = obj.payment_method_types?.[0] || 'card';
  gatewayTransactionId = obj.id || '';
  clientId = obj.metadata?.client_id || '';
  currency = (obj.currency || 'zar').toUpperCase();
  gateway = 'stripe';
}
// ── PayFast ─────────────────────────────────────────────
else if (body.pf_payment_id) {
  amount = Math.round(parseFloat(body.amount_gross || '0') * 100);
  referenceText = body.m_payment_id || body.custom_str1 || '';
  method = 'payfast';
  gatewayTransactionId = body.pf_payment_id;
  clientId = body.custom_str2 || '';
  currency = 'ZAR';
  gateway = 'payfast';
}
// ── Yoco ────────────────────────────────────────────────
else if (body.payload?.metadata || body.type === 'payment.succeeded') {
  const payload = body.payload || body;
  amount = payload.amount || 0;
  referenceText = payload.metadata?.invoiceRef || payload.metadata?.reference || '';
  method = 'yoco';
  gatewayTransactionId = payload.id || '';
  clientId = payload.metadata?.clientId || '';
  currency = (payload.currency || 'ZAR').toUpperCase();
  gateway = 'yoco';
}
// ── Manual portal entry ─────────────────────────────────
else {
  amount = Math.round(parseFloat(body.amount || '0') * 100);
  referenceText = body.reference || body.reference_text || '';
  method = body.method || 'manual';
  gatewayTransactionId = body.transaction_id || '';
  clientId = body.client_id || '';
  currency = (body.currency || 'ZAR').toUpperCase();
  gateway = 'manual';
}

return [{
  json: {
    amount,
    amount_display: (amount / 100).toFixed(2),
    reference_text: referenceText,
    method,
    gateway_transaction_id: gatewayTransactionId,
    client_id: clientId,
    currency,
    gateway,
    received_at: new Date().toISOString(),
  }
}];
"""

VALIDATE_PAYMENT_JS = r"""
// Validate normalized payment data.
const p = $input.first().json;
const errors = [];

if (!p.amount || p.amount <= 0) {
  errors.push('Amount must be greater than 0');
}
if (!p.reference_text && !p.gateway_transaction_id) {
  errors.push('Payment must have a reference or gateway transaction ID');
}

const isValid = errors.length === 0;

return [{
  json: {
    ...p,
    is_valid: isValid,
    validation_errors: errors,
  }
}];
"""

PREPARE_PAYMENT_INSERT_JS = r"""
// Build Supabase insert payload for acct_payments.
const p = $input.first().json;

return [{
  json: {
    client_id: p.client_id || null,
    amount: p.amount,
    currency: p.currency,
    reference_text: p.reference_text,
    method: p.method,
    gateway: p.gateway,
    gateway_transaction_id: p.gateway_transaction_id,
    reconciliation_status: 'received',
    received_at: p.received_at,
    metadata: {
      amount_display: p.amount_display,
    },
  }
}];
"""

EXACT_MATCH_JS = r"""
// Search for invoice matching the payment reference or exact amount.
const payment = $('Validate Payment').first().json;
const insertedPayment = $input.first().json;
const paymentId = Array.isArray(insertedPayment)
  ? insertedPayment[0]?.id
  : insertedPayment.id;

// Fetch open invoices via expression (passed as items from prior select)
const invoices = $('Fetch Open Invoices').first().json;
const invoiceList = Array.isArray(invoices) ? invoices : [invoices];

let matchedInvoice = null;
let matchMethod = '';

// 1) Exact reference match: invoice_number contains payment reference
if (payment.reference_text) {
  const ref = payment.reference_text.toUpperCase().trim();
  matchedInvoice = invoiceList.find(inv => {
    const invNum = (inv.invoice_number || '').toUpperCase().trim();
    return invNum && (invNum === ref || ref.includes(invNum) || invNum.includes(ref));
  });
  if (matchedInvoice) matchMethod = 'exact_reference';
}

// 2) Exact amount match (only if single open invoice with that amount)
if (!matchedInvoice && payment.amount > 0) {
  const amountMatches = invoiceList.filter(inv => {
    const balanceDue = (inv.total_amount || 0) - (inv.amount_paid || 0);
    return balanceDue === payment.amount;
  });
  if (amountMatches.length === 1) {
    matchedInvoice = amountMatches[0];
    matchMethod = 'exact_amount';
  }
}

return [{
  json: {
    payment_id: paymentId,
    payment_amount: payment.amount,
    payment_reference: payment.reference_text,
    payment_client_id: payment.client_id,
    payment_gateway: payment.gateway,
    payment_method: payment.method,
    payment_received_at: payment.received_at,
    amount_display: payment.amount_display,
    has_exact_match: !!matchedInvoice,
    match_method: matchMethod,
    match_confidence: matchedInvoice ? 100 : 0,
    matched_invoice: matchedInvoice || null,
    matched_invoice_id: matchedInvoice?.id || null,
    matched_invoice_number: matchedInvoice?.invoice_number || null,
    open_invoices_for_ai: matchedInvoice
      ? []
      : invoiceList.slice(0, 20).map(inv => ({
          id: inv.id,
          invoice_number: inv.invoice_number,
          client_id: inv.client_id,
          client_name: inv.client_name || '',
          total_amount: inv.total_amount,
          amount_paid: inv.amount_paid || 0,
          balance_due: (inv.total_amount || 0) - (inv.amount_paid || 0),
          due_date: inv.due_date,
          description: inv.description || '',
        })),
  }
}];
"""

PREPARE_AI_PROMPT_JS = r"""
// Build AI prompt for fuzzy invoice matching.
const data = $input.first().json;

const invoiceTable = data.open_invoices_for_ai
  .map(inv => `- ${inv.invoice_number}: ${inv.client_name}, R${(inv.balance_due / 100).toFixed(2)} due, "${inv.description || 'N/A'}"`)
  .join('\n');

const prompt = `Match this payment to the most likely invoice.

PAYMENT:
- Amount: R${data.amount_display}
- Reference: "${data.payment_reference}"
- Client ID: "${data.payment_client_id}"
- Method: ${data.payment_method}

OPEN INVOICES:
${invoiceTable}

Respond ONLY with valid JSON (no markdown):
{
  "matched_invoice_id": "<id or null>",
  "matched_invoice_number": "<number or null>",
  "confidence": <0-100>,
  "reasoning": "<brief explanation>"
}`;

return [{
  json: {
    ...data,
    aiPrompt: prompt,
  }
}];
"""

PARSE_AI_RESPONSE_JS = r"""
// Parse AI fuzzy match response.
const data = $('Prepare AI Prompt').first().json;
const aiRaw = $input.first().json;

let aiContent = '';
try {
  aiContent = aiRaw.choices?.[0]?.message?.content || '';
} catch (e) {
  aiContent = '';
}

let parsed = { matched_invoice_id: null, matched_invoice_number: null, confidence: 0, reasoning: 'AI parse failed' };
try {
  // Strip markdown code fences if present
  const cleaned = aiContent.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  parsed = JSON.parse(cleaned);
} catch (e) {
  // Attempt regex extraction
  const idMatch = aiContent.match(/"matched_invoice_id"\s*:\s*"([^"]+)"/);
  const confMatch = aiContent.match(/"confidence"\s*:\s*(\d+)/);
  if (idMatch) parsed.matched_invoice_id = idMatch[1];
  if (confMatch) parsed.confidence = parseInt(confMatch[1], 10);
}

// Look up matched invoice details from the open invoices list
let matchedInvoice = null;
if (parsed.matched_invoice_id) {
  matchedInvoice = data.open_invoices_for_ai.find(
    inv => inv.id === parsed.matched_invoice_id
  ) || null;
}

return [{
  json: {
    ...data,
    has_exact_match: false,
    match_method: 'ai_fuzzy',
    match_confidence: parsed.confidence || 0,
    matched_invoice_id: parsed.matched_invoice_id,
    matched_invoice_number: parsed.matched_invoice_number || matchedInvoice?.invoice_number || null,
    matched_invoice: matchedInvoice,
    ai_reasoning: parsed.reasoning || '',
  }
}];
"""

APPLY_PAYMENT_JS = r"""
// Calculate new payment status and amounts.
const data = $input.first().json;
const invoice = data.matched_invoice;

if (!invoice) {
  return [{ json: { ...data, apply_error: 'No matched invoice' } }];
}

const totalAmount = invoice.total_amount || 0;
const previouslyPaid = invoice.amount_paid || 0;
const paymentAmount = data.payment_amount;
const newAmountPaid = previouslyPaid + paymentAmount;
const newBalanceDue = totalAmount - newAmountPaid;

let invoiceStatus = 'partially_paid';
let reconciliationStatus = 'matched';

if (newBalanceDue <= 0) {
  invoiceStatus = 'paid';
}
if (newBalanceDue < 0) {
  reconciliationStatus = 'overpayment';
}

return [{
  json: {
    ...data,
    new_amount_paid: newAmountPaid,
    new_balance_due: Math.max(newBalanceDue, 0),
    overpayment_amount: newBalanceDue < 0 ? Math.abs(newBalanceDue) : 0,
    invoice_status: invoiceStatus,
    reconciliation_status: reconciliationStatus,
  }
}];
"""

PREPARE_INVOICE_UPDATE_JS = r"""
// Build Supabase PATCH payload for the invoice.
const data = $input.first().json;

return [{
  json: {
    id: data.matched_invoice_id,
    updatePayload: {
      amount_paid: data.new_amount_paid,
      status: data.invoice_status,
      last_payment_at: data.payment_received_at,
      updated_at: new Date().toISOString(),
    },
  }
}];
"""

PREPARE_PAYMENT_UPDATE_JS = r"""
// Build Supabase PATCH payload for the payment record.
const data = $('Apply Payment').first().json;

return [{
  json: {
    id: data.payment_id,
    updatePayload: {
      reconciliation_status: data.reconciliation_status,
      invoice_id: data.matched_invoice_id,
      match_confidence: data.match_confidence,
      matched_by: data.match_method,
      matched_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  }
}];
"""

BUILD_RECEIPT_HTML_JS = r"""
// Build payment receipt email HTML.
const data = $('Apply Payment').first().json;

const amountRands = (data.payment_amount / 100).toFixed(2);
const balanceRands = (data.new_balance_due / 100).toFixed(2);
const invoiceNum = data.matched_invoice_number || 'N/A';
const clientName = data.matched_invoice?.client_name || 'Valued Client';
const paidDate = new Date(data.payment_received_at).toLocaleDateString('en-ZA', {
  year: 'numeric', month: 'long', day: 'numeric'
});

const html = `
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #FF6D5A; padding: 20px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 24px;">Payment Receipt</h1>
  </div>
  <div style="padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
    <p>Dear ${clientName},</p>
    <p>Thank you for your payment. Here are the details:</p>
    <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
      <tr style="border-bottom: 1px solid #e5e7eb;">
        <td style="padding: 8px 0; font-weight: bold;">Invoice</td>
        <td style="padding: 8px 0; text-align: right;">${invoiceNum}</td>
      </tr>
      <tr style="border-bottom: 1px solid #e5e7eb;">
        <td style="padding: 8px 0; font-weight: bold;">Amount Received</td>
        <td style="padding: 8px 0; text-align: right;">R ${amountRands}</td>
      </tr>
      <tr style="border-bottom: 1px solid #e5e7eb;">
        <td style="padding: 8px 0; font-weight: bold;">Payment Method</td>
        <td style="padding: 8px 0; text-align: right;">${data.payment_method}</td>
      </tr>
      <tr style="border-bottom: 1px solid #e5e7eb;">
        <td style="padding: 8px 0; font-weight: bold;">Date</td>
        <td style="padding: 8px 0; text-align: right;">${paidDate}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; font-weight: bold;">Balance Due</td>
        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: ${data.new_balance_due > 0 ? '#dc2626' : '#16a34a'};">R ${balanceRands}</td>
      </tr>
    </table>
    ${data.new_balance_due <= 0
      ? '<p style="color: #16a34a; font-weight: bold;">This invoice is now fully paid. Thank you!</p>'
      : '<p>Please note a balance remains on this invoice.</p>'}
    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
    <p style="color: #6b7280; font-size: 12px;">AnyVision Media (Pty) Ltd<br/>This is an automated receipt.</p>
  </div>
</div>
`;

// Look up client email from the invoice
const recipientEmail = data.matched_invoice?.client_email || '';

return [{
  json: {
    ...data,
    receipt_html: html,
    recipient_email: recipientEmail,
    receipt_subject: 'Payment Receipt - ' + invoiceNum,
  }
}];
"""

PREPARE_QBO_SYNC_JS = r"""
// Prepare accounting software sync payload.
// Switch output determines which adapter runs.
const data = $('Apply Payment').first().json;

// Default to 'none' if no accounting software configured
const acctSoftware = data.matched_invoice?.accounting_software || 'none';

return [{
  json: {
    accounting_software: acctSoftware,
    payment_id: data.payment_id,
    invoice_id: data.matched_invoice_id,
    amount: data.payment_amount,
    currency: data.matched_invoice?.currency || 'ZAR',
    reference: data.payment_reference,
    method: data.payment_method,
    date: data.payment_received_at,
  }
}];
"""

PREPARE_UNMATCHED_TASK_JS = r"""
// Build a manual reconciliation task for unmatched payments.
const data = $input.first().json;

return [{
  json: {
    client_id: data.payment_client_id,
    task_type: 'manual_reconciliation',
    title: 'Unmatched payment requires manual reconciliation',
    description: `Payment of R${data.amount_display} received via ${data.payment_gateway} with reference "${data.payment_reference}". AI match confidence: ${data.match_confidence}%. Please match manually.`,
    priority: 'high',
    status: 'open',
    entity_type: 'payment',
    entity_id: data.payment_id,
    metadata: {
      payment_amount: data.payment_amount,
      payment_reference: data.payment_reference,
      payment_method: data.payment_method,
      gateway: data.payment_gateway,
      ai_reasoning: data.ai_reasoning || '',
    },
  }
}];
"""

PREPARE_OVERPAYMENT_TASK_JS = r"""
// Build a review task for overpayment.
const data = $('Apply Payment').first().json;

if (data.overpayment_amount <= 0) {
  return [{ json: { skip_task: true } }];
}

const overRands = (data.overpayment_amount / 100).toFixed(2);

return [{
  json: {
    client_id: data.payment_client_id,
    task_type: 'overpayment_review',
    title: 'Overpayment detected - review required',
    description: `Invoice ${data.matched_invoice_number} overpaid by R${overRands}. Original balance: R${((data.matched_invoice?.total_amount || 0) / 100).toFixed(2)}. Payment: R${data.amount_display}.`,
    priority: 'medium',
    status: 'open',
    entity_type: 'payment',
    entity_id: data.payment_id,
    metadata: {
      overpayment_amount: data.overpayment_amount,
      invoice_id: data.matched_invoice_id,
      invoice_number: data.matched_invoice_number,
    },
  }
}];
"""

AUDIT_RECEIVED_JS = r"""
// Audit log: PAYMENT_RECEIVED
const p = $('Validate Payment').first().json;
const insertResult = $('Insert Payment Record').first().json;
const paymentId = Array.isArray(insertResult) ? insertResult[0]?.id : insertResult.id;

return [{
  json: {
    client_id: p.client_id,
    event_type: 'PAYMENT_RECEIVED',
    entity_type: 'payment',
    entity_id: paymentId,
    action: 'payment_received',
    actor: 'system',
    result: 'success',
    metadata: {
      source: 'n8n',
      amount: p.amount,
      gateway: p.gateway,
      reference: p.reference_text,
    },
  }
}];
"""

AUDIT_MATCHED_JS = r"""
// Audit log: PAYMENT_MATCHED
const data = $('Apply Payment').first().json;

return [{
  json: {
    client_id: data.payment_client_id,
    event_type: 'PAYMENT_MATCHED',
    entity_type: 'payment',
    entity_id: data.payment_id,
    action: 'payment_matched',
    actor: 'system',
    result: 'success',
    metadata: {
      source: 'n8n',
      invoice_id: data.matched_invoice_id,
      invoice_number: data.matched_invoice_number,
      match_method: data.match_method,
      confidence: data.match_confidence,
      new_status: data.invoice_status,
    },
  }
}];
"""

AUDIT_UNMATCHED_JS = r"""
// Audit log: PAYMENT_UNMATCHED
const data = $input.first().json;

return [{
  json: {
    client_id: data.payment_client_id,
    event_type: 'PAYMENT_UNMATCHED',
    entity_type: 'payment',
    entity_id: data.payment_id,
    action: 'payment_unmatched',
    actor: 'system',
    result: 'warning',
    metadata: {
      source: 'n8n',
      reference: data.payment_reference,
      amount: data.payment_amount,
      ai_confidence: data.match_confidence,
    },
  }
}];
"""

BANK_RECON_JS = r"""
// Daily bank reconciliation: fetch unmatched payments and attempt re-matching.
// This is a simplified trigger - actual bank statement import would be an
// additional integration. For now, re-process any 'received' payments.
return [{
  json: {
    trigger: 'bank_reconciliation',
    run_at: new Date().toISOString(),
    action: 'reprocess_unmatched',
  }
}];
"""

PREPARE_WEBHOOK_RESPONSE_JS = r"""
// Build webhook response payload.
const data = $input.first().json;

return [{
  json: {
    success: true,
    payment_id: data.payment_id || data.entity_id || null,
    status: data.reconciliation_status || data.event_type || 'processed',
    message: 'Payment processed successfully',
    timestamp: new Date().toISOString(),
  }
}];
"""

PREPARE_STATUS_RECEIVED_JS = r"""
// Portal status: payment_received
const p = $('Validate Payment').first().json;
const insertResult = $('Insert Payment Record').first().json;
const paymentId = Array.isArray(insertResult) ? insertResult[0]?.id : insertResult.id;

return [{
  json: {
    payment_id: paymentId,
    client_id: p.client_id,
    amount: p.amount,
    gateway: p.gateway,
    reference: p.reference_text,
    status: 'received',
  }
}];
"""

PREPARE_STATUS_MATCHED_JS = r"""
// Portal status: payment_matched
const data = $('Apply Payment').first().json;

return [{
  json: {
    payment_id: data.payment_id,
    client_id: data.payment_client_id,
    invoice_id: data.matched_invoice_id,
    invoice_number: data.matched_invoice_number,
    amount: data.payment_amount,
    invoice_status: data.invoice_status,
    match_method: data.match_method,
    confidence: data.match_confidence,
    status: 'matched',
  }
}];
"""


# ====================================================================
# NODE BUILDERS
# ====================================================================

def build_nodes() -> list[dict]:
    """Build all ~28 functional nodes for ACCT-05."""
    nodes: list[dict] = []

    # ── Sticky Notes ───────────────────────────────────────────
    nodes.append({
        "parameters": {
            "content": (
                "## ACCT-05: Payment Capture & Reconciliation\n"
                "Receives payments via webhook (Stripe/PayFast/Yoco/manual),\n"
                "normalizes, matches to invoices (exact + AI fuzzy),\n"
                "applies payment, sends receipt, syncs accounting software."
            ),
            "width": 560,
            "height": 140,
            "color": 4,
        },
        "id": uid(),
        "name": "Note - Overview",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 40],
        "typeVersion": 1,
    })

    nodes.append({
        "parameters": {
            "content": (
                "### Matching Logic\n"
                "1. Exact reference match (invoice_number vs reference)\n"
                "2. Exact amount match (single invoice with matching balance)\n"
                "3. AI fuzzy match via OpenRouter/Claude (confidence >= 70%)\n"
                "4. Unmatched → manual reconciliation task"
            ),
            "width": 440,
            "height": 120,
            "color": 6,
        },
        "id": uid(),
        "name": "Note - Matching",
        "type": "n8n-nodes-base.stickyNote",
        "position": [1200, 40],
        "typeVersion": 1,
    })

    # ── 1. Webhook: Payment Received (gateway ITN) ─────────────
    nodes.append(webhook_trigger(
        name="Webhook Payment Received",
        path="accounting/payment-received",
        position=[200, 300],
    ))

    # ── 2. Webhook: Manual Payment (portal) ────────────────────
    nodes.append(webhook_trigger(
        name="Webhook Manual Payment",
        path="accounting/manual-payment",
        position=[200, 500],
    ))

    # ── 3. Schedule: Daily Bank Recon ──────────────────────────
    nodes.append(schedule_trigger(
        name="Daily Bank Recon",
        cron="0 6 * * *",
        position=[200, 700],
    ))

    # ── 4. Manual Trigger ──────────────────────────────────────
    nodes.append(manual_trigger(position=[200, 900]))

    # ── 5. Bank Recon Prep ─────────────────────────────────────
    nodes.append(code_node(
        name="Bank Recon Prep",
        js_code=BANK_RECON_JS,
        position=[440, 700],
    ))

    # ── 6. Fetch Unmatched Payments ────────────────────────────
    nodes.append(supabase_select(
        name="Fetch Unmatched Payments",
        table="acct_payments",
        select="*",
        filters="reconciliation_status=eq.received&order=received_at.asc&limit=50",
        position=[680, 700],
    ))

    # ── 7. Normalize Payment ───────────────────────────────────
    nodes.append(code_node(
        name="Normalize Payment",
        js_code=NORMALIZE_PAYMENT_JS,
        position=[480, 400],
    ))

    # ── 8. Validate Payment ────────────────────────────────────
    nodes.append(code_node(
        name="Validate Payment",
        js_code=VALIDATE_PAYMENT_JS,
        position=[680, 400],
    ))

    # ── 9. Payment Valid? ──────────────────────────────────────
    nodes.append(if_node(
        name="Payment Valid?",
        left_value="={{ $json.is_valid }}",
        operator_type="boolean",
        operation="true",
        position=[880, 400],
    ))

    # ── 10. Prepare Payment Insert ─────────────────────────────
    nodes.append(code_node(
        name="Prepare Payment Insert",
        js_code=PREPARE_PAYMENT_INSERT_JS,
        position=[1080, 300],
    ))

    # ── 11. Insert Payment Record ──────────────────────────────
    nodes.append(supabase_insert(
        name="Insert Payment Record",
        table="acct_payments",
        position=[1280, 300],
    ))

    # ── 12. Status: Payment Received ───────────────────────────
    nodes.append(code_node(
        name="Prep Status Received",
        js_code=PREPARE_STATUS_RECEIVED_JS,
        position=[1480, 160],
    ))

    nodes.append(portal_status_webhook(
        name="Status Payment Received",
        action="payment_received",
        position=[1680, 160],
    ))

    # ── 13. Audit: Payment Received ────────────────────────────
    nodes.append(code_node(
        name="Audit Received Prep",
        js_code=AUDIT_RECEIVED_JS,
        position=[1480, 20],
    ))

    nodes.append(supabase_insert(
        name="Audit Log Received",
        table="acct_audit_log",
        position=[1680, 20],
        return_rep=False,
    ))

    # ── 14. Fetch Open Invoices ────────────────────────────────
    nodes.append(supabase_select(
        name="Fetch Open Invoices",
        table="acct_invoices",
        select="id,invoice_number,client_id,client_name,client_email,total_amount,amount_paid,balance_due,due_date,description,accounting_software,currency",
        filters="status=in.(sent,partially_paid,overdue)",
        position=[1480, 400],
    ))

    # ── 15. Exact Match ────────────────────────────────────────
    nodes.append(code_node(
        name="Exact Match",
        js_code=EXACT_MATCH_JS,
        position=[1720, 400],
    ))

    # ── 16. Found Exact Match? ─────────────────────────────────
    nodes.append(if_node(
        name="Found Exact Match?",
        left_value="={{ $json.has_exact_match }}",
        operator_type="boolean",
        operation="true",
        position=[1960, 400],
    ))

    # ── 17. Prepare AI Prompt (no exact match) ─────────────────
    nodes.append(code_node(
        name="Prepare AI Prompt",
        js_code=PREPARE_AI_PROMPT_JS,
        position=[2200, 600],
    ))

    # ── 18. AI Fuzzy Match ─────────────────────────────────────
    nodes.append(openrouter_ai(
        name="AI Fuzzy Match",
        system_prompt=(
            "You are a payment reconciliation assistant for AnyVision Media. "
            "Match incoming payments to open invoices based on reference text, "
            "amounts, and client information. Respond ONLY with valid JSON."
        ),
        user_prompt_expr="Match this payment",
        max_tokens=500,
        cred=CRED_OPENROUTER,
        position=[2440, 600],
    ))

    # ── 19. Parse AI Response ──────────────────────────────────
    nodes.append(code_node(
        name="Parse AI Response",
        js_code=PARSE_AI_RESPONSE_JS,
        position=[2680, 600],
    ))

    # ── 20. Match Confidence Check ─────────────────────────────
    nodes.append(if_node(
        name="Match Confidence >= 70%?",
        left_value="={{ $json.match_confidence }}",
        operator_type="number",
        operation="gte",
        right_value="70",
        position=[2920, 600],
    ))

    # ── 21. Apply Payment (matched path - both exact & AI) ────
    nodes.append(code_node(
        name="Apply Payment",
        js_code=APPLY_PAYMENT_JS,
        position=[2200, 300],
    ))

    # ── 22. Update Invoice ─────────────────────────────────────
    nodes.append(code_node(
        name="Prepare Invoice Update",
        js_code=PREPARE_INVOICE_UPDATE_JS,
        position=[2440, 200],
    ))

    nodes.append(supabase_update(
        name="Update Invoice",
        table="acct_invoices",
        position=[2640, 200],
    ))

    # ── 23. Update Payment Record ──────────────────────────────
    nodes.append(code_node(
        name="Prepare Payment Update",
        js_code=PREPARE_PAYMENT_UPDATE_JS,
        position=[2440, 400],
    ))

    nodes.append(supabase_update(
        name="Update Payment Record",
        table="acct_payments",
        position=[2640, 400],
    ))

    # ── 24. Send Receipt ───────────────────────────────────────
    nodes.append(code_node(
        name="Build Receipt HTML",
        js_code=BUILD_RECEIPT_HTML_JS,
        position=[2880, 200],
    ))

    nodes.append(gmail_send(
        name="Send Receipt Email",
        to_expr="={{ $json.recipient_email }}",
        subject_expr="={{ $json.receipt_subject }}",
        html_expr="={{ $json.receipt_html }}",
        cred=CRED_GMAIL,
        position=[3120, 200],
    ))

    # ── 25. Accounting Software Sync ───────────────────────────
    nodes.append(code_node(
        name="Prep Acct Sync",
        js_code=PREPARE_QBO_SYNC_JS,
        position=[2880, 400],
    ))

    nodes.append(switch_node(
        name="Acct Software Switch",
        rules=[
            {
                "leftValue": "={{ $json.accounting_software }}",
                "rightValue": "quickbooks",
                "output": "quickbooks",
            },
            {
                "leftValue": "={{ $json.accounting_software }}",
                "rightValue": "xero",
                "output": "xero",
            },
        ],
        position=[3120, 400],
    ))

    nodes.append(noop_node(
        name="QBO Sync Placeholder",
        position=[3360, 320],
    ))

    nodes.append(noop_node(
        name="Xero Sync Placeholder",
        position=[3360, 440],
    ))

    nodes.append(noop_node(
        name="No Acct Software",
        position=[3360, 560],
    ))

    # ── 26. Overpayment Task ───────────────────────────────────
    nodes.append(code_node(
        name="Prep Overpayment Task",
        js_code=PREPARE_OVERPAYMENT_TASK_JS,
        position=[3360, 100],
    ))

    overpay_if = if_node(
        name="Has Overpayment?",
        left_value="={{ $json.skip_task }}",
        operator_type="boolean",
        operation="notTrue",
        position=[3560, 100],
    )
    nodes.append(overpay_if)

    nodes.append(supabase_insert(
        name="Insert Overpayment Task",
        table="acct_tasks",
        position=[3760, 60],
    ))

    # ── 27. Unmatched Path ─────────────────────────────────────
    nodes.append(code_node(
        name="Prep Unmatched Task",
        js_code=PREPARE_UNMATCHED_TASK_JS,
        position=[3160, 800],
    ))

    nodes.append(supabase_insert(
        name="Insert Unmatched Task",
        table="acct_tasks",
        position=[3400, 800],
    ))

    # ── 28. Update Payment as Unmatched ────────────────────────
    nodes.append(code_node(
        name="Prep Payment Unmatched Update",
        js_code=r"""
// Update payment record to 'unmatched'.
const data = $('Prep Unmatched Task').first().json;

return [{
  json: {
    id: data.entity_id,
    updatePayload: {
      reconciliation_status: 'unmatched',
      match_confidence: data.metadata?.ai_confidence || 0,
      matched_by: 'none',
      updated_at: new Date().toISOString(),
    },
  }
}];
""",
        position=[3400, 940],
    ))

    nodes.append(supabase_update(
        name="Update Payment Unmatched",
        table="acct_payments",
        position=[3640, 940],
    ))

    # ── 29. Audit: Payment Matched ─────────────────────────────
    nodes.append(code_node(
        name="Audit Matched Prep",
        js_code=AUDIT_MATCHED_JS,
        position=[3360, -60],
    ))

    nodes.append(supabase_insert(
        name="Audit Log Matched",
        table="acct_audit_log",
        position=[3560, -60],
        return_rep=False,
    ))

    # ── 30. Status: Payment Matched ────────────────────────────
    nodes.append(code_node(
        name="Prep Status Matched",
        js_code=PREPARE_STATUS_MATCHED_JS,
        position=[3560, -180],
    ))

    nodes.append(portal_status_webhook(
        name="Status Payment Matched",
        action="payment_matched",
        position=[3760, -180],
    ))

    # ── 31. Audit: Payment Unmatched ───────────────────────────
    nodes.append(code_node(
        name="Audit Unmatched Prep",
        js_code=AUDIT_UNMATCHED_JS,
        position=[3640, 1080],
    ))

    nodes.append(supabase_insert(
        name="Audit Log Unmatched",
        table="acct_audit_log",
        position=[3880, 1080],
        return_rep=False,
    ))

    # ── 32. Respond Webhooks ───────────────────────────────────
    nodes.append(code_node(
        name="Prep Webhook Response Matched",
        js_code=PREPARE_WEBHOOK_RESPONSE_JS,
        position=[3760, -300],
    ))

    from acct_helpers import respond_webhook
    nodes.append(respond_webhook(
        name="Respond Webhook Matched",
        position=[3960, -300],
    ))

    nodes.append(code_node(
        name="Prep Webhook Response Unmatched",
        js_code=r"""
// Webhook response for unmatched payment.
const data = $input.first().json;
return [{
  json: {
    success: true,
    payment_id: data.entity_id || null,
    status: 'unmatched',
    message: 'Payment received but could not be matched. Manual reconciliation task created.',
    timestamp: new Date().toISOString(),
  }
}];
""",
        position=[3880, 1220],
    ))

    nodes.append(respond_webhook(
        name="Respond Webhook Unmatched",
        position=[4100, 1220],
    ))

    # ── 33. Validation Failed Response ─────────────────────────
    nodes.append(code_node(
        name="Prep Validation Error Response",
        js_code=r"""
// Webhook response for validation failure.
const data = $input.first().json;
return [{
  json: {
    success: false,
    errors: data.validation_errors || ['Payment validation failed'],
    message: 'Payment rejected due to validation errors',
    timestamp: new Date().toISOString(),
  }
}];
""",
        position=[1080, 600],
    ))

    nodes.append(respond_webhook(
        name="Respond Webhook Validation Error",
        position=[1280, 600],
    ))

    return nodes


def build_connections() -> dict:
    """Build all connections for ACCT-05."""
    return {
        # ── Triggers → Normalize ──────────────────────────────
        "Webhook Payment Received": {
            "main": [[conn("Normalize Payment")]]
        },
        "Webhook Manual Payment": {
            "main": [[conn("Normalize Payment")]]
        },
        "Manual Trigger": {
            "main": [[conn("Normalize Payment")]]
        },

        # ── Schedule → Bank Recon ─────────────────────────────
        "Daily Bank Recon": {
            "main": [[conn("Bank Recon Prep")]]
        },
        "Bank Recon Prep": {
            "main": [[conn("Fetch Unmatched Payments")]]
        },
        "Fetch Unmatched Payments": {
            "main": [[conn("Normalize Payment")]]
        },

        # ── Normalize → Validate → Branch ────────────────────
        "Normalize Payment": {
            "main": [[conn("Validate Payment")]]
        },
        "Validate Payment": {
            "main": [[conn("Payment Valid?")]]
        },
        "Payment Valid?": {
            "main": [
                # True: valid payment
                [conn("Prepare Payment Insert")],
                # False: validation failed
                [conn("Prep Validation Error Response")],
            ]
        },

        # ── Validation failed response ────────────────────────
        "Prep Validation Error Response": {
            "main": [[conn("Respond Webhook Validation Error")]]
        },

        # ── Insert payment → parallel: status + audit + match ─
        "Prepare Payment Insert": {
            "main": [[conn("Insert Payment Record")]]
        },
        "Insert Payment Record": {
            "main": [[
                conn("Prep Status Received"),
                conn("Audit Received Prep"),
                conn("Fetch Open Invoices"),
            ]]
        },

        # ── Status & Audit (fire-and-forget) ──────────────────
        "Prep Status Received": {
            "main": [[conn("Status Payment Received")]]
        },
        "Audit Received Prep": {
            "main": [[conn("Audit Log Received")]]
        },

        # ── Invoice matching pipeline ─────────────────────────
        "Fetch Open Invoices": {
            "main": [[conn("Exact Match")]]
        },
        "Exact Match": {
            "main": [[conn("Found Exact Match?")]]
        },
        "Found Exact Match?": {
            "main": [
                # True: exact match found → apply payment
                [conn("Apply Payment")],
                # False: no exact match → try AI
                [conn("Prepare AI Prompt")],
            ]
        },

        # ── AI Fuzzy Match path ───────────────────────────────
        "Prepare AI Prompt": {
            "main": [[conn("AI Fuzzy Match")]]
        },
        "AI Fuzzy Match": {
            "main": [[conn("Parse AI Response")]]
        },
        "Parse AI Response": {
            "main": [[conn("Match Confidence >= 70%?")]]
        },
        "Match Confidence >= 70%?": {
            "main": [
                # True: AI matched with high confidence
                [conn("Apply Payment")],
                # False: unmatched
                [conn("Prep Unmatched Task")],
            ]
        },

        # ── Apply Payment → parallel updates ──────────────────
        "Apply Payment": {
            "main": [[
                conn("Prepare Invoice Update"),
                conn("Prepare Payment Update"),
                conn("Build Receipt HTML"),
                conn("Prep Acct Sync"),
                conn("Prep Overpayment Task"),
                conn("Audit Matched Prep"),
                conn("Prep Status Matched"),
            ]]
        },

        # ── Invoice update ────────────────────────────────────
        "Prepare Invoice Update": {
            "main": [[conn("Update Invoice")]]
        },

        # ── Payment record update ─────────────────────────────
        "Prepare Payment Update": {
            "main": [[conn("Update Payment Record")]]
        },

        # ── Receipt email ─────────────────────────────────────
        "Build Receipt HTML": {
            "main": [[conn("Send Receipt Email")]]
        },
        "Send Receipt Email": {
            "main": [[conn("Prep Webhook Response Matched")]]
        },

        # ── Accounting software sync ──────────────────────────
        "Prep Acct Sync": {
            "main": [[conn("Acct Software Switch")]]
        },
        "Acct Software Switch": {
            "main": [
                [conn("QBO Sync Placeholder")],      # quickbooks
                [conn("Xero Sync Placeholder")],      # xero
                [conn("No Acct Software")],            # fallback
            ]
        },

        # ── Overpayment check ─────────────────────────────────
        "Prep Overpayment Task": {
            "main": [[conn("Has Overpayment?")]]
        },
        "Has Overpayment?": {
            "main": [
                # True: has overpayment
                [conn("Insert Overpayment Task")],
                # False: no overpayment
                [],
            ]
        },

        # ── Audit & Status: matched ──────────────────────────
        "Audit Matched Prep": {
            "main": [[conn("Audit Log Matched")]]
        },
        "Prep Status Matched": {
            "main": [[conn("Status Payment Matched")]]
        },

        # ── Matched webhook response ──────────────────────────
        "Prep Webhook Response Matched": {
            "main": [[conn("Respond Webhook Matched")]]
        },

        # ── Unmatched path ────────────────────────────────────
        "Prep Unmatched Task": {
            "main": [[
                conn("Insert Unmatched Task"),
                conn("Prep Payment Unmatched Update"),
                conn("Audit Unmatched Prep"),
            ]]
        },
        "Prep Payment Unmatched Update": {
            "main": [[conn("Update Payment Unmatched")]]
        },
        "Audit Unmatched Prep": {
            "main": [[conn("Audit Log Unmatched")]]
        },
        "Insert Unmatched Task": {
            "main": [[conn("Prep Webhook Response Unmatched")]]
        },
        "Prep Webhook Response Unmatched": {
            "main": [[conn("Respond Webhook Unmatched")]]
        },
    }


# ====================================================================
# WORKFLOW ASSEMBLY
# ====================================================================

def build_workflow() -> dict:
    """Assemble the complete workflow JSON."""
    nodes = build_nodes()
    connections = build_connections()
    return build_workflow_json(WORKFLOW_NAME, nodes, connections)


# ====================================================================
# FILE I/O
# ====================================================================

def save_workflow(workflow_data: dict) -> Path:
    """Save workflow JSON to the output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILE

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_data, f, indent=2, ensure_ascii=False)

    node_count = len(workflow_data["nodes"])
    print(f"  + {WORKFLOW_NAME:<45} -> {OUTPUT_FILE} ({node_count} nodes)")
    return output_path


# ====================================================================
# n8n API HELPERS
# ====================================================================

def get_n8n_client():
    """Create N8nClient with credentials from env."""
    try:
        from n8n_client import N8nClient
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from n8n_client import N8nClient

    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        raise ValueError("N8N_API_KEY not set in .env")
    return N8nClient(base_url=base_url, api_key=api_key)


def deploy_to_n8n(workflow_data: dict) -> dict:
    """Deploy workflow to n8n via API (inactive)."""
    client = get_n8n_client()
    return client.create_workflow(workflow_data)


def activate_on_n8n(workflow_id: str) -> dict:
    """Activate a workflow by ID."""
    client = get_n8n_client()
    return client.activate_workflow(workflow_id)


# ====================================================================
# CLI
# ====================================================================

def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("build", "deploy", "activate"):
        print("Usage: python tools/deploy_acct_v2_wf05.py <build|deploy|activate>")
        print()
        print("Actions:")
        print("  build     Build JSON and save to workflows/accounting-v2/")
        print("  deploy    Build + push to n8n (inactive)")
        print("  activate  Build + push + activate on n8n")
        sys.exit(1)

    action = args[0]

    print("=" * 60)
    print("ACCT-05: PAYMENT CAPTURE & RECONCILIATION")
    print("=" * 60)
    print()
    print(f"Action:    {action}")
    print(f"Output:    {OUTPUT_DIR / OUTPUT_FILE}")
    print(f"Supabase:  {SUPABASE_URL}")
    print(f"Portal:    {PORTAL_URL}")
    print(f"AI Model:  {OPENROUTER_MODEL}")
    print()

    # ── Build ──────────────────────────────────────────────────
    print("Building workflow...")
    print("-" * 40)
    workflow = build_workflow()
    save_workflow(workflow)
    print()

    if action == "build":
        print("Build complete. Run 'deploy' to push to n8n.")
        return

    # ── Deploy ─────────────────────────────────────────────────
    deployed_id = None
    if action in ("deploy", "activate"):
        print("Deploying to n8n (inactive)...")
        print("-" * 40)
        try:
            resp = deploy_to_n8n(workflow)
            deployed_id = resp.get("id", "unknown")
            print(f"  + {WORKFLOW_NAME:<45} -> {deployed_id}")
        except Exception as e:
            print(f"  - {WORKFLOW_NAME:<45} FAILED: {e}")
            sys.exit(1)
        print()

    # ── Activate ───────────────────────────────────────────────
    if action == "activate" and deployed_id:
        print("Activating workflow...")
        print("-" * 40)
        try:
            activate_on_n8n(deployed_id)
            print(f"  + {WORKFLOW_NAME:<45} ACTIVE")
        except Exception as e:
            print(f"  - {WORKFLOW_NAME:<45} FAILED: {e}")
        print()

    # ── Save deployed ID ───────────────────────────────────────
    if deployed_id:
        tmp_dir = Path(__file__).parent.parent / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        id_path = tmp_dir / "acct_v2_wf05_id.json"
        with open(id_path, "w", encoding="utf-8") as f:
            json.dump({
                "workflow_id": deployed_id,
                "workflow_name": WORKFLOW_NAME,
                "deployed_at": datetime.now().isoformat(),
            }, f, indent=2)
        print(f"Workflow ID saved to: {id_path}")

    print()
    print("Next steps:")
    print("  1. Verify workflow in n8n UI")
    print("  2. Ensure acct_payments, acct_invoices, acct_tasks,")
    print("     acct_audit_log tables exist in Supabase")
    print("  3. Configure Stripe/PayFast/Yoco webhook URLs to point")
    print(f"     to: <n8n-url>/webhook/accounting/payment-received")
    print("  4. Replace QBO/Xero sync placeholders with real HTTP nodes")
    print("  5. Test with manual trigger first, then activate webhooks")


if __name__ == "__main__":
    main()
