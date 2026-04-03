"""
ACCT-06: Supplier Bill Intake

Scans Gmail for supplier bills, accepts portal uploads, runs configurable
OCR extraction (Azure / Google / AI / manual), matches suppliers, and
auto-approves small bills from known suppliers.

Node count: ~26 functional nodes

Usage:
    python tools/deploy_acct_v2_wf06.py build       # Build workflow JSON
    python tools/deploy_acct_v2_wf06.py deploy       # Build + Deploy (inactive)
    python tools/deploy_acct_v2_wf06.py activate      # Build + Deploy + Activate
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── Environment ─────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Ensure tools/ is on the path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from acct_helpers import (
    OPENROUTER_MODEL,
    PORTAL_URL,
    SUPABASE_KEY,
    SUPABASE_URL,
    audit_log_code,
    build_workflow_json,
    code_node,
    conn,
    if_node,
    manual_trigger,
    noop_node,
    openrouter_ai,
    portal_status_webhook,
    respond_webhook,
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

WORKFLOW_NAME = "ACCT-06 Supplier Bill Intake"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILE = "wf06_bill_intake.json"


# ================================================================
# NODE BUILDERS
# ================================================================


def build_nodes() -> list[dict]:
    """Build all ~26 nodes for WF-06 Supplier Bill Intake."""
    nodes: list[dict] = []

    # ── 1. Schedule Trigger — hourly 8-17 M-F ──────────────────
    nodes.append(
        schedule_trigger(
            name="Scan Inbox Schedule",
            cron="0 8-17 * * 1-5",
            position=[200, 300],
        )
    )

    # ── 2. Webhook Trigger — portal bill upload ─────────────────
    nodes.append(
        webhook_trigger(
            name="Portal Bill Upload",
            path="accounting/upload-bill",
            position=[200, 600],
            method="POST",
            response_mode="responseNode",
        )
    )

    # ── 3. Manual Trigger ───────────────────────────────────────
    nodes.append(manual_trigger(position=[200, 900]))

    # ── 4. Load Config ──────────────────────────────────────────
    nodes.append(
        supabase_select(
            name="Load Config",
            table="acct_config",
            select="*",
            filters="active=eq.true",
            position=[500, 300],
            single=True,
        )
    )

    # ── 5. Scan Gmail for Bills ─────────────────────────────────
    scan_gmail_js = r"""
// Fetch recent emails from Gmail via REST (schedule path only).
// The previous node provides config with known supplier emails.
const config = $input.first().json;
const supplierEmails = (config.known_supplier_emails || '').split(',').map(e => e.trim()).filter(Boolean);

// Build a Gmail search query for recent bills with attachments
const afterDate = new Date(Date.now() - 60 * 60 * 1000).toISOString().split('T')[0];
const fromFilter = supplierEmails.length > 0
  ? `from:(${supplierEmails.join(' OR ')})`
  : 'label:bills OR subject:invoice OR subject:bill OR subject:statement';

return [{
  json: {
    searchQuery: `${fromFilter} after:${afterDate} has:attachment`,
    supplierEmails,
    config,
  }
}];
"""
    nodes.append(
        code_node(
            name="Build Gmail Query",
            js_code=scan_gmail_js,
            position=[500, 100],
        )
    )

    # ── 6. Gmail Search HTTP ────────────────────────────────────
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://gmail.googleapis.com/gmail/v1/users/me/messages?q={{ encodeURIComponent($json.searchQuery) }}&maxResults=20",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "gmailOAuth2",
            "options": {
                "response": {"response": {"responseFormat": "json"}},
            },
        },
        "id": uid(),
        "name": "Gmail Search Bills",
        "type": "n8n-nodes-base.httpRequest",
        "position": [700, 100],
        "typeVersion": 4.2,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
    })

    # ── 7. Parse Email Results ──────────────────────────────────
    parse_emails_js = r"""
// Convert Gmail search results into individual bill items.
// For webhook path, the body already has {client_id, attachment_url, supplier_email}.
const input = $input.first().json;

// Webhook path — single bill upload
if (input.client_id && input.attachment_url) {
  return [{
    json: {
      source: 'portal_upload',
      client_id: input.client_id,
      attachment_url: input.attachment_url,
      supplier_email: input.supplier_email || null,
      subject: 'Portal Upload',
      received_at: new Date().toISOString(),
    }
  }];
}

// Schedule path — Gmail messages list
const messages = input.messages || [];
if (messages.length === 0) {
  return [{ json: { _empty: true } }];
}

return messages.map(msg => ({
  json: {
    source: 'email_scan',
    gmail_message_id: msg.id,
    client_id: null,
    attachment_url: null,
    supplier_email: null,
    subject: null,
    received_at: new Date().toISOString(),
  }
}));
"""
    nodes.append(
        code_node(
            name="Parse Email Results",
            js_code=parse_emails_js,
            position=[900, 300],
        )
    )

    # ── 8. Skip if Empty ────────────────────────────────────────
    nodes.append(
        if_node(
            name="Has Bills?",
            left_value="{{ $json._empty }}",
            operator_type="boolean",
            operation="notTrue",
            position=[1100, 300],
        )
    )

    # ── 9. Create Bill Record ───────────────────────────────────
    create_bill_js = r"""
// Prepare a new supplier bill record for Supabase insert.
const item = $input.first().json;
return [{
  json: {
    client_id: item.client_id || null,
    source: item.source,
    supplier_email: item.supplier_email,
    attachment_url: item.attachment_url,
    gmail_message_id: item.gmail_message_id || null,
    email_subject: item.subject,
    received_at: item.received_at,
    status: 'uploaded',
    extraction_confidence: 0,
    ocr_provider: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Bill Record",
            js_code=create_bill_js,
            position=[1300, 200],
        )
    )

    nodes.append(
        supabase_insert(
            name="Insert Bill Record",
            table="acct_supplier_bills",
            position=[1500, 200],
            return_rep=True,
        )
    )

    # ── 10. Load OCR Config ─────────────────────────────────────
    load_ocr_js = r"""
// Merge bill record with config to determine OCR provider.
const bill = $input.first().json;
const config = $('Load Config').first().json;
const ocrProvider = config.ocr_provider || 'ai';

return [{
  json: {
    ...bill,
    ocr_provider: ocrProvider,
    auto_approve_threshold: parseFloat(config.auto_approve_bills_below || '10000'),
  }
}];
"""
    nodes.append(
        code_node(
            name="Merge Config + Bill",
            js_code=load_ocr_js,
            position=[1700, 200],
        )
    )

    # ── 11. OCR Adapter Switch ──────────────────────────────────
    nodes.append(
        switch_node(
            name="OCR Provider Switch",
            rules=[
                {"leftValue": "={{ $json.ocr_provider }}", "rightValue": "azure_doc_ai", "output": "Azure"},
                {"leftValue": "={{ $json.ocr_provider }}", "rightValue": "google_doc_ai", "output": "Google"},
                {"leftValue": "={{ $json.ocr_provider }}", "rightValue": "ai", "output": "AI"},
                {"leftValue": "={{ $json.ocr_provider }}", "rightValue": "none", "output": "Manual"},
            ],
            position=[1900, 200],
        )
    )

    # ── 12a. Azure Document Intelligence ────────────────────────
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.azure_endpoint || 'https://REPLACE.cognitiveservices.azure.com' }}/formrecognizer/documentModels/prebuilt-invoice:analyze?api-version=2023-07-31",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Ocp-Apim-Subscription-Key", "value": "={{ $json.azure_key || '' }}"},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={{ JSON.stringify({ urlSource: $json.attachment_url }) }}',
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "id": uid(),
        "name": "Azure Doc AI",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2200, 0],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # ── 12b. Google Document AI ─────────────────────────────────
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json.google_docai_endpoint || 'https://REPLACE-documentai.googleapis.com/v1/projects/PROJECT/locations/LOCATION/processors/PROCESSOR:process' }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={{ JSON.stringify({ rawDocument: { content: $json.attachment_url, mimeType: "application/pdf" } }) }}',
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "id": uid(),
        "name": "Google Doc AI",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2200, 200],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # ── 12c. AI Extraction (OpenRouter Claude) ──────────────────
    ai_system = (
        "You are a financial document extraction specialist. "
        "Extract structured data from supplier bills/invoices. "
        "Return ONLY valid JSON with these fields: "
        "supplier_name, bill_number, bill_date (YYYY-MM-DD), "
        "due_date (YYYY-MM-DD), subtotal, vat_amount, total_amount, "
        "currency (default ZAR), category (one of: office_supplies, "
        "professional_services, software, utilities, marketing, "
        "travel, equipment, other), line_items (array of {description, "
        "quantity, unit_price, amount}). If a field cannot be found, "
        "set it to null."
    )
    ai_user = (
        "Extract bill data from this supplier document. "
        "Supplier email: {{ $json.supplier_email || 'unknown' }}. "
        "Email subject: {{ $json.email_subject || 'N/A' }}. "
        "Attachment URL: {{ $json.attachment_url || 'N/A' }}."
    )
    nodes.append(
        openrouter_ai(
            name="AI Extract Bill Data",
            system_prompt=ai_system,
            user_prompt_expr=ai_user,
            max_tokens=2000,
            cred=CRED_OPENROUTER,
            position=[2200, 400],
        )
    )

    # ── 12d. Manual Entry NoOp ──────────────────────────────────
    nodes.append(
        noop_node(name="Manual Entry (NoOp)", position=[2200, 600])
    )

    # ── 13. Parse OCR Results ───────────────────────────────────
    parse_ocr_js = r"""
// Normalize extraction results from any OCR provider.
// Calculate confidence score as % of expected fields found.
const bill = $('Merge Config + Bill').first().json;
const raw = $input.first().json;

const EXPECTED_FIELDS = ['supplier_name', 'total_amount', 'bill_date', 'bill_number', 'due_date', 'subtotal', 'vat_amount'];

let extracted = {};

// AI path: parse from OpenRouter response
if (raw.choices && raw.choices[0]) {
  try {
    const content = raw.choices[0].message.content;
    // Strip markdown code fences if present
    const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    extracted = JSON.parse(cleaned);
  } catch (e) {
    extracted = { _parse_error: e.message };
  }
}
// Azure path
else if (raw.analyzeResult) {
  const doc = (raw.analyzeResult.documents || [])[0] || {};
  const fields = doc.fields || {};
  extracted = {
    supplier_name: fields.VendorName?.content || null,
    bill_number: fields.InvoiceId?.content || null,
    bill_date: fields.InvoiceDate?.content || null,
    due_date: fields.DueDate?.content || null,
    subtotal: fields.SubTotal?.content ? parseFloat(fields.SubTotal.content) : null,
    vat_amount: fields.TotalTax?.content ? parseFloat(fields.TotalTax.content) : null,
    total_amount: fields.InvoiceTotal?.content ? parseFloat(fields.InvoiceTotal.content) : null,
    currency: fields.CurrencyCode?.content || 'ZAR',
    category: null,
    line_items: (fields.Items?.values || []).map(li => ({
      description: li.fields?.Description?.content || '',
      quantity: li.fields?.Quantity?.content || 1,
      unit_price: li.fields?.UnitPrice?.content || 0,
      amount: li.fields?.Amount?.content || 0,
    })),
  };
}
// Google path
else if (raw.document) {
  const entities = raw.document.entities || [];
  const fieldMap = {};
  for (const ent of entities) {
    fieldMap[ent.type] = ent.mentionText || ent.normalizedValue?.text || null;
  }
  extracted = {
    supplier_name: fieldMap.supplier_name || null,
    bill_number: fieldMap.invoice_id || null,
    bill_date: fieldMap.invoice_date || null,
    due_date: fieldMap.due_date || null,
    subtotal: fieldMap.net_amount ? parseFloat(fieldMap.net_amount) : null,
    vat_amount: fieldMap.total_tax_amount ? parseFloat(fieldMap.total_tax_amount) : null,
    total_amount: fieldMap.total_amount ? parseFloat(fieldMap.total_amount) : null,
    currency: fieldMap.currency || 'ZAR',
    category: null,
    line_items: [],
  };
}
// Manual / NoOp path
else {
  extracted = {
    supplier_name: null, bill_number: null, bill_date: null,
    due_date: null, subtotal: null, vat_amount: null,
    total_amount: null, currency: 'ZAR', category: null, line_items: [],
  };
}

// Calculate confidence (0-100)
let found = 0;
for (const field of EXPECTED_FIELDS) {
  if (extracted[field] !== null && extracted[field] !== undefined && extracted[field] !== '') {
    found++;
  }
}
const confidence = Math.round((found / EXPECTED_FIELDS.length) * 100);

return [{
  json: {
    id: bill.id,
    client_id: bill.client_id,
    auto_approve_threshold: bill.auto_approve_threshold,
    supplier_email: bill.supplier_email,
    ocr_provider: bill.ocr_provider,
    ...extracted,
    extraction_confidence: confidence,
    ocr_raw: JSON.stringify(raw).substring(0, 5000),
  }
}];
"""
    nodes.append(
        code_node(
            name="Parse OCR Results",
            js_code=parse_ocr_js,
            position=[2500, 200],
        )
    )

    # ── 14. Update Bill with Extracted Data ─────────────────────
    update_extracted_js = r"""
// Prepare update payload for the bill record with extraction data.
const item = $input.first().json;
return [{
  json: {
    id: item.id,
    updatePayload: {
      supplier_name: item.supplier_name,
      bill_number: item.bill_number,
      bill_date: item.bill_date,
      due_date: item.due_date,
      subtotal: item.subtotal,
      vat_amount: item.vat_amount,
      total_amount: item.total_amount,
      currency: item.currency || 'ZAR',
      category: item.category,
      line_items: item.line_items ? JSON.stringify(item.line_items) : null,
      extraction_confidence: item.extraction_confidence,
      ocr_provider: item.ocr_provider,
      ocr_raw: item.ocr_raw,
      status: 'extracted',
      updated_at: new Date().toISOString(),
    },
    // Pass through for downstream nodes
    client_id: item.client_id,
    supplier_name: item.supplier_name,
    supplier_email: item.supplier_email,
    total_amount: item.total_amount,
    extraction_confidence: item.extraction_confidence,
    auto_approve_threshold: item.auto_approve_threshold,
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Extracted Update",
            js_code=update_extracted_js,
            position=[2700, 200],
        )
    )

    nodes.append(
        supabase_update(
            name="Update Bill Extracted",
            table="acct_supplier_bills",
            match_col="id",
            position=[2900, 200],
        )
    )

    # ── 15. Match Supplier ──────────────────────────────────────
    match_supplier_js = r"""
// Fuzzy-match supplier by email or name against acct_suppliers.
const item = $input.first().json;
const bill = $('Prepare Extracted Update').first().json;

return [{
  json: {
    ...bill,
    bill_id: bill.id,
    _searchEmail: bill.supplier_email || '',
    _searchName: (bill.supplier_name || '').toLowerCase().trim(),
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Supplier Search",
            js_code=match_supplier_js,
            position=[3100, 200],
        )
    )

    nodes.append(
        supabase_select(
            name="Lookup Suppliers",
            table="acct_suppliers",
            select="id,name,email,external_id",
            position=[3300, 200],
        )
    )

    match_result_js = r"""
// Match supplier from lookup results.
const searchData = $('Prepare Supplier Search').first().json;
const suppliers = $input.all().map(i => i.json);
const email = searchData._searchEmail.toLowerCase();
const name = searchData._searchName;

let matched = null;

// Exact email match
if (email) {
  matched = suppliers.find(s => (s.email || '').toLowerCase() === email);
}

// Fuzzy name match (contains)
if (!matched && name && name.length > 2) {
  matched = suppliers.find(s => {
    const sName = (s.name || '').toLowerCase();
    return sName.includes(name) || name.includes(sName);
  });
}

return [{
  json: {
    ...searchData,
    supplier_id: matched ? matched.id : null,
    supplier_external_id: matched ? matched.external_id : null,
    supplier_matched: !!matched,
  }
}];
"""
    nodes.append(
        code_node(
            name="Match Supplier Result",
            js_code=match_result_js,
            position=[3500, 200],
        )
    )

    # ── 16. Supplier Found? ─────────────────────────────────────
    nodes.append(
        if_node(
            name="Supplier Found?",
            left_value="{{ $json.supplier_matched }}",
            operator_type="boolean",
            operation="true",
            position=[3700, 200],
        )
    )

    # ── 17a. Link Supplier ID ───────────────────────────────────
    link_supplier_js = r"""
// Update bill with matched supplier_id.
const item = $input.first().json;
return [{
  json: {
    id: item.bill_id,
    updatePayload: {
      supplier_id: item.supplier_id,
      updated_at: new Date().toISOString(),
    },
    // Pass through
    bill_id: item.bill_id,
    client_id: item.client_id,
    supplier_id: item.supplier_id,
    supplier_external_id: item.supplier_external_id,
    supplier_matched: true,
    total_amount: item.total_amount,
    extraction_confidence: item.extraction_confidence,
    auto_approve_threshold: item.auto_approve_threshold,
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Link Supplier",
            js_code=link_supplier_js,
            position=[3900, 100],
        )
    )

    nodes.append(
        supabase_update(
            name="Link Supplier to Bill",
            table="acct_supplier_bills",
            match_col="id",
            position=[4100, 100],
        )
    )

    # ── 17b. Create Stub Supplier ───────────────────────────────
    stub_supplier_js = r"""
// Create a stub supplier record for unknown supplier.
const item = $input.first().json;
return [{
  json: {
    name: item.supplier_name || 'Unknown Supplier',
    email: item.supplier_email || null,
    status: 'pending_review',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    _bill_id: item.bill_id,
    _client_id: item.client_id,
    _total_amount: item.total_amount,
    _extraction_confidence: item.extraction_confidence,
    _auto_approve_threshold: item.auto_approve_threshold,
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Stub Supplier",
            js_code=stub_supplier_js,
            position=[3900, 400],
        )
    )

    nodes.append(
        supabase_insert(
            name="Create Stub Supplier",
            table="acct_suppliers",
            position=[4100, 400],
            return_rep=True,
        )
    )

    link_stub_js = r"""
// Link the newly created stub supplier back to the bill.
const newSupplier = $input.first().json;
const prev = $('Prepare Stub Supplier').first().json;
return [{
  json: {
    id: prev._bill_id,
    updatePayload: {
      supplier_id: newSupplier.id,
      updated_at: new Date().toISOString(),
    },
    bill_id: prev._bill_id,
    client_id: prev._client_id,
    supplier_id: newSupplier.id,
    supplier_external_id: null,
    supplier_matched: false,
    total_amount: prev._total_amount,
    extraction_confidence: prev._extraction_confidence,
    auto_approve_threshold: prev._auto_approve_threshold,
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Link Stub",
            js_code=link_stub_js,
            position=[4300, 400],
        )
    )

    nodes.append(
        supabase_update(
            name="Link Stub to Bill",
            table="acct_supplier_bills",
            match_col="id",
            position=[4500, 400],
        )
    )

    # ── 18. Auto-Approve Check ──────────────────────────────────
    auto_approve_js = r"""
// Check if bill qualifies for auto-approval:
// - total_amount < config threshold
// - supplier is known (has external_id)
const item = $input.first().json;
const amount = parseFloat(item.total_amount) || 0;
const threshold = parseFloat(item.auto_approve_threshold) || 10000;
const knownSupplier = item.supplier_matched && !!item.supplier_external_id;

return [{
  json: {
    ...item,
    can_auto_approve: amount > 0 && amount < threshold && knownSupplier,
    approval_reason: amount <= 0
      ? 'no_amount'
      : amount >= threshold
        ? `amount_exceeds_threshold_${threshold}`
        : !knownSupplier
          ? 'unknown_supplier'
          : 'auto_approved',
  }
}];
"""
    nodes.append(
        code_node(
            name="Auto-Approve Check",
            js_code=auto_approve_js,
            position=[4700, 200],
        )
    )

    # ── 19. Can Auto-Approve? ───────────────────────────────────
    nodes.append(
        if_node(
            name="Can Auto-Approve?",
            left_value="{{ $json.can_auto_approve }}",
            operator_type="boolean",
            operation="true",
            position=[4900, 200],
        )
    )

    # ── 20a. Auto-Approve Bill ──────────────────────────────────
    approve_js = r"""
// Mark bill as approved by system.
const item = $input.first().json;
return [{
  json: {
    id: item.bill_id,
    updatePayload: {
      status: 'approved',
      approver: 'system_auto',
      approval_reason: item.approval_reason,
      approved_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    bill_id: item.bill_id,
    client_id: item.client_id,
    extraction_confidence: item.extraction_confidence,
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Auto-Approve",
            js_code=approve_js,
            position=[5100, 100],
        )
    )

    nodes.append(
        supabase_update(
            name="Update Bill Approved",
            table="acct_supplier_bills",
            match_col="id",
            position=[5300, 100],
        )
    )

    # ── 20b. Needs Manual Review ────────────────────────────────
    review_js = r"""
// Mark bill as awaiting review and create approval task.
const item = $input.first().json;
return [{
  json: {
    id: item.bill_id,
    updatePayload: {
      status: 'awaiting_review',
      approval_reason: item.approval_reason,
      updated_at: new Date().toISOString(),
    },
    // Task to create
    _task: {
      client_id: item.client_id,
      entity_type: 'supplier_bill',
      entity_id: item.bill_id,
      task_type: 'bill_approval',
      title: `Review supplier bill #${item.bill_id}`,
      description: `Bill requires manual approval. Reason: ${item.approval_reason}. Amount: ${item.total_amount || 'unknown'}`,
      status: 'pending',
      priority: 'normal',
      created_at: new Date().toISOString(),
    },
    bill_id: item.bill_id,
    client_id: item.client_id,
    extraction_confidence: item.extraction_confidence,
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Awaiting Review",
            js_code=review_js,
            position=[5100, 350],
        )
    )

    nodes.append(
        supabase_update(
            name="Update Bill Awaiting",
            table="acct_supplier_bills",
            match_col="id",
            position=[5300, 300],
        )
    )

    # Insert approval task
    create_task_js = r"""
// Extract the task object for insertion.
const item = $('Prepare Awaiting Review').first().json;
return [{ json: item._task }];
"""
    nodes.append(
        code_node(
            name="Prepare Approval Task",
            js_code=create_task_js,
            position=[5300, 450],
        )
    )

    nodes.append(
        supabase_insert(
            name="Create Approval Task",
            table="acct_tasks",
            position=[5500, 450],
            return_rep=True,
        )
    )

    # ── 21. Low Confidence Check ────────────────────────────────
    nodes.append(
        if_node(
            name="Low Confidence?",
            left_value="{{ $json.extraction_confidence }}",
            operator_type="number",
            operation="lt",
            right_value="70",
            position=[5500, 200],
        )
    )

    # ── 22. Create Exception Review Task ────────────────────────
    exception_js = r"""
// Create an exception review task for low-confidence extractions.
const item = $input.first().json;
return [{
  json: {
    client_id: item.client_id,
    entity_type: 'supplier_bill',
    entity_id: item.bill_id,
    task_type: 'exception_review',
    title: `Low-confidence bill extraction #${item.bill_id}`,
    description: `Extraction confidence: ${item.extraction_confidence}%. Manual review required.`,
    status: 'pending',
    priority: 'high',
    created_at: new Date().toISOString(),
  }
}];
"""
    nodes.append(
        code_node(
            name="Prepare Exception Task",
            js_code=exception_js,
            position=[5700, 100],
        )
    )

    nodes.append(
        supabase_insert(
            name="Create Exception Task",
            table="acct_tasks",
            position=[5900, 100],
            return_rep=True,
        )
    )

    # ── 23. Portal Status Webhook ───────────────────────────────
    nodes.append(
        portal_status_webhook(
            name="Portal: Bill Extracted",
            action="bill_extracted",
            position=[5900, 300],
        )
    )

    # ── 24. Audit Log — BILL_UPLOADED ───────────────────────────
    nodes.append(
        audit_log_code(
            name="Audit: Bill Uploaded",
            event_type="BILL_UPLOADED",
            entity_type="supplier_bill",
            actor="n8n_wf06",
            position=[1500, 450],
        )
    )

    nodes.append(
        supabase_insert(
            name="Insert Audit Upload",
            table="acct_audit_log",
            position=[1700, 450],
            return_rep=False,
        )
    )

    # ── 25. Audit Log — BILL_EXTRACTED ──────────────────────────
    nodes.append(
        audit_log_code(
            name="Audit: Bill Extracted",
            event_type="BILL_EXTRACTED",
            entity_type="supplier_bill",
            actor="n8n_wf06",
            position=[5900, 500],
        )
    )

    nodes.append(
        supabase_insert(
            name="Insert Audit Extracted",
            table="acct_audit_log",
            position=[6100, 500],
            return_rep=False,
        )
    )

    # ── 26. Respond to Webhook ──────────────────────────────────
    nodes.append(
        respond_webhook(
            name="Respond Webhook",
            position=[6100, 300],
        )
    )

    return nodes


# ================================================================
# CONNECTIONS
# ================================================================


def build_connections() -> dict:
    """Build the connection map for all nodes."""
    return {
        # Triggers → Load Config / Parse
        "Scan Inbox Schedule": {"main": [[conn("Load Config")]]},
        "Manual Trigger": {"main": [[conn("Load Config")]]},
        "Portal Bill Upload": {"main": [[conn("Parse Email Results")]]},

        # Config → Gmail scan
        "Load Config": {"main": [[conn("Build Gmail Query")]]},
        "Build Gmail Query": {"main": [[conn("Gmail Search Bills")]]},
        "Gmail Search Bills": {"main": [[conn("Parse Email Results")]]},

        # Parse → filter empty → create bill
        "Parse Email Results": {"main": [[conn("Has Bills?")]]},
        "Has Bills?": {
            "main": [
                [conn("Prepare Bill Record")],  # true — has bills
                [],                              # false — no bills, stop
            ]
        },

        # Create bill → audit → OCR
        "Prepare Bill Record": {"main": [[conn("Insert Bill Record")]]},
        "Insert Bill Record": {
            "main": [
                [conn("Merge Config + Bill"), conn("Audit: Bill Uploaded")],
            ]
        },
        "Audit: Bill Uploaded": {"main": [[conn("Insert Audit Upload")]]},

        # OCR adapter
        "Merge Config + Bill": {"main": [[conn("OCR Provider Switch")]]},
        "OCR Provider Switch": {
            "main": [
                [conn("Azure Doc AI")],       # output 0: Azure
                [conn("Google Doc AI")],       # output 1: Google
                [conn("AI Extract Bill Data")],  # output 2: AI
                [conn("Manual Entry (NoOp)")],   # output 3: Manual
                [],                              # fallback
            ]
        },

        # All OCR outputs → Parse OCR Results
        "Azure Doc AI": {"main": [[conn("Parse OCR Results")]]},
        "Google Doc AI": {"main": [[conn("Parse OCR Results")]]},
        "AI Extract Bill Data": {"main": [[conn("Parse OCR Results")]]},
        "Manual Entry (NoOp)": {"main": [[conn("Parse OCR Results")]]},

        # Parse → Update extracted → Match supplier
        "Parse OCR Results": {"main": [[conn("Prepare Extracted Update")]]},
        "Prepare Extracted Update": {"main": [[conn("Update Bill Extracted")]]},
        "Update Bill Extracted": {"main": [[conn("Prepare Supplier Search")]]},

        # Supplier matching
        "Prepare Supplier Search": {"main": [[conn("Lookup Suppliers")]]},
        "Lookup Suppliers": {"main": [[conn("Match Supplier Result")]]},
        "Match Supplier Result": {"main": [[conn("Supplier Found?")]]},

        # Supplier found branching
        "Supplier Found?": {
            "main": [
                [conn("Prepare Link Supplier")],   # true — matched
                [conn("Prepare Stub Supplier")],    # false — create stub
            ]
        },

        # Link existing supplier → auto-approve
        "Prepare Link Supplier": {"main": [[conn("Link Supplier to Bill")]]},
        "Link Supplier to Bill": {"main": [[conn("Auto-Approve Check")]]},

        # Create stub supplier → link stub → auto-approve
        "Prepare Stub Supplier": {"main": [[conn("Create Stub Supplier")]]},
        "Create Stub Supplier": {"main": [[conn("Prepare Link Stub")]]},
        "Prepare Link Stub": {"main": [[conn("Link Stub to Bill")]]},
        "Link Stub to Bill": {"main": [[conn("Auto-Approve Check")]]},

        # Auto-approve branching
        "Auto-Approve Check": {"main": [[conn("Can Auto-Approve?")]]},
        "Can Auto-Approve?": {
            "main": [
                [conn("Prepare Auto-Approve")],   # true — auto approve
                [conn("Prepare Awaiting Review")],  # false — needs review
            ]
        },

        # Auto-approve path → low confidence check
        "Prepare Auto-Approve": {"main": [[conn("Update Bill Approved")]]},
        "Update Bill Approved": {"main": [[conn("Low Confidence?")]]},

        # Awaiting review path → update + create task → low confidence check
        "Prepare Awaiting Review": {
            "main": [[conn("Update Bill Awaiting"), conn("Prepare Approval Task")]],
        },
        "Update Bill Awaiting": {"main": [[conn("Low Confidence?")]]},
        "Prepare Approval Task": {"main": [[conn("Create Approval Task")]]},

        # Low confidence check
        "Low Confidence?": {
            "main": [
                [conn("Prepare Exception Task")],  # true — low confidence
                [conn("Portal: Bill Extracted"), conn("Audit: Bill Extracted"), conn("Respond Webhook")],  # false — good confidence
            ]
        },

        # Exception task → portal + audit + respond
        "Prepare Exception Task": {"main": [[conn("Create Exception Task")]]},
        "Create Exception Task": {
            "main": [
                [conn("Portal: Bill Extracted"), conn("Audit: Bill Extracted"), conn("Respond Webhook")],
            ]
        },

        # Audit extracted
        "Audit: Bill Extracted": {"main": [[conn("Insert Audit Extracted")]]},
    }


# ================================================================
# BUILD & SAVE
# ================================================================


def build_workflow() -> dict:
    """Build the complete workflow JSON."""
    nodes = build_nodes()
    connections = build_connections()
    return build_workflow_json(WORKFLOW_NAME, nodes, connections)


def save_workflow(workflow: dict) -> Path:
    """Save workflow JSON to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILE
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2)
    return output_path


def print_stats(workflow: dict) -> None:
    """Print workflow statistics."""
    nodes = workflow.get("nodes", [])
    node_types: dict[str, int] = {}
    for n in nodes:
        t = n.get("type", "unknown")
        node_types[t] = node_types.get(t, 0) + 1

    print(f"  Nodes: {len(nodes)}")
    for t, count in sorted(node_types.items()):
        print(f"    {t}: {count}")

    conns = workflow.get("connections", {})
    total_links = sum(
        len(targets)
        for outputs in conns.values()
        for main in outputs.get("main", [])
        for targets in [main]
    )
    print(f"  Connections: {total_links} links across {len(conns)} source nodes")


# ================================================================
# CLI
# ================================================================


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "build"

    if action not in ("build", "deploy", "activate"):
        print(f"ERROR: Unknown action '{action}'. Use: build, deploy, activate")
        sys.exit(1)

    print("=" * 60)
    print(f"  {WORKFLOW_NAME}")
    print("=" * 60)

    # ── Build ───────────────────────────────────────────────────
    print("\nBuilding workflow...")
    workflow = build_workflow()
    output_path = save_workflow(workflow)
    print_stats(workflow)
    print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # ── Deploy / Activate ───────────────────────────────────────
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

        # Check if workflow already exists
        existing = None
        try:
            for wf in client.list_workflows():
                if wf["name"] == workflow["name"]:
                    existing = wf
                    break
        except Exception:
            pass

        deploy_payload = {
            "name": workflow["name"],
            "nodes": workflow["nodes"],
            "connections": workflow["connections"],
            "settings": workflow["settings"],
        }

        if existing:
            result = client.update_workflow(existing["id"], deploy_payload)
            deployed_id = result.get("id")
            print(f"  Updated: {result.get('name')} (ID: {deployed_id})")
        else:
            result = client.create_workflow(deploy_payload)
            deployed_id = result.get("id")
            print(f"  Created: {result.get('name')} (ID: {deployed_id})")

        if action == "activate" and deployed_id:
            print("  Activating...")
            client.activate_workflow(deployed_id)
            print("  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Open the workflow in n8n UI to verify node connections")
    print("  2. Verify credential bindings (Gmail OAuth2, OpenRouter)")
    print("  3. Ensure Supabase tables exist: acct_config, acct_supplier_bills,")
    print("     acct_suppliers, acct_tasks, acct_audit_log")
    print("  4. Set acct_config.ocr_provider to 'ai', 'azure_doc_ai',")
    print("     'google_doc_ai', or 'none'")
    print("  5. Set acct_config.auto_approve_bills_below (default 10000 ZAR)")
    print("  6. Test with Manual Trigger first")
    print("  7. Test webhook: POST /accounting/upload-bill")
    print("     Body: {client_id, attachment_url, supplier_email}")


if __name__ == "__main__":
    main()
