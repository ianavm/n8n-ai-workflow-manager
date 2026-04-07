"""
ACCT-02 Invoice Creation Engine — Builder & Deployer

Builds the Invoice Creation Engine workflow that handles:
- Processing draft invoices from Supabase on an hourly schedule (M-F 8-17)
- Accepting webhook requests from the client portal
- Customer lookup and tax calculation (VAT from acct_config)
- Atomic invoice number generation via Supabase RPC
- High-value invoice approval routing
- Accounting software adapter (QuickBooks/Xero/Sage/none)
- Status updates and audit logging via portal webhooks

All amounts are in cents (integer). VAT rate from acct_config.vat_rate.

Usage:
    python tools/deploy_acct_wf02.py build
    python tools/deploy_acct_wf02.py deploy
    python tools/deploy_acct_wf02.py activate
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))

from acct_helpers import (
    PORTAL_URL,
    SUPABASE_KEY,
    SUPABASE_URL,
    build_workflow_json,
    code_node,
    conn,
    if_node,
    manual_trigger,
    noop_node,
    portal_status_webhook,
    respond_webhook,
    schedule_trigger,
    supabase_rpc,
    supabase_select,
    supabase_update,
    switch_node,
    uid,
    webhook_trigger,
)


# ══════════════════════════════════════════════════════════════
# NODE BUILDERS
# ══════════════════════════════════════════════════════════════


def build_nodes() -> list[dict]:
    """Build all ~28 nodes for the Invoice Creation Engine workflow."""
    nodes: list[dict] = []

    # ── 1. Hourly Draft Check (scheduleTrigger) ──
    nodes.append(
        schedule_trigger(
            name="Hourly Draft Check",
            cron="0 8-17 * * 1-5",
            position=[200, 400],
        )
    )

    # ── 2. Manual Trigger ──
    nodes.append(manual_trigger(position=[200, 600]))

    # ── 3. Invoice Webhook ──
    nodes.append(
        webhook_trigger(
            name="Invoice Webhook",
            path="accounting/create-invoice",
            position=[200, 800],
            method="POST",
            response_mode="responseNode",
        )
    )

    # ── 4. Load Client Config ──
    nodes.append(
        supabase_select(
            name="Load Client Config",
            table="acct_config",
            select="*",
            filters="limit=1",
            position=[460, 400],
            single=True,
        )
    )

    # ── 5. Read Draft Invoices ──
    nodes.append(
        supabase_select(
            name="Read Draft Invoices",
            table="acct_invoices",
            select="*",
            filters="status=eq.draft&order=created_at.asc",
            position=[700, 400],
        )
    )

    # ── 6. Merge Sources ──
    nodes.append(
        code_node(
            name="Merge Sources",
            js_code=(
                "// Combine scheduled draft invoices with any webhook payload\n"
                "const config = $('Load Client Config').first().json;\n"
                "const draftItems = $input.all().filter(i => i.json && i.json.id);\n"
                "\n"
                "let webhookData = null;\n"
                "try { webhookData = $('Invoice Webhook').first(); } catch(e) { /* not triggered */ }\n"
                "\n"
                "const items = [];\n"
                "\n"
                "// Add draft invoices from Supabase\n"
                "for (const item of draftItems) {\n"
                "  items.push({ ...item.json, _config: config });\n"
                "}\n"
                "\n"
                "// Add webhook invoice request if present\n"
                "if (webhookData && webhookData.json && webhookData.json.body) {\n"
                "  const body = webhookData.json.body;\n"
                "  items.push({\n"
                "    id: body.id || `wh-${Date.now()}`,\n"
                "    client_id: body.client_id || config.client_id,\n"
                "    customer_id: body.customer_id,\n"
                "    line_items: body.line_items || [],\n"
                "    notes: body.notes || '',\n"
                "    due_date: body.due_date || null,\n"
                "    status: 'draft',\n"
                "    source: 'webhook',\n"
                "    _config: config,\n"
                "  });\n"
                "}\n"
                "\n"
                "if (items.length === 0) {\n"
                "  return [{ json: { _empty: true, _config: config, totalItems: 0 } }];\n"
                "}\n"
                "return items.map(item => ({ json: item }));\n"
            ),
            position=[940, 600],
        )
    )

    # ── 7. Has Items? ──
    nodes.append(
        if_node(
            name="Has Items?",
            left_value="{{ $json._empty }}",
            operator_type="boolean",
            operation="notTrue",
            position=[1160, 600],
        )
    )

    # ── 8. Loop Over Invoices (splitInBatches) ──
    nodes.append({
        "parameters": {"batchSize": 1, "options": {}},
        "id": uid(),
        "name": "Loop Over Invoices",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1400, 500],
        "typeVersion": 3,
    })

    # ── 9. Lookup Customer ──
    nodes.append(
        code_node(
            name="Lookup Customer",
            js_code=(
                "// Build Supabase query for the customer\n"
                "const invoice = $input.first().json;\n"
                "const customerId = invoice.customer_id;\n"
                "\n"
                "if (!customerId) {\n"
                "  return [{ json: { ...invoice, _customer: null, _customerFound: false } }];\n"
                "}\n"
                "\n"
                "// Pass through — the next HTTP node does the actual lookup\n"
                "return [{ json: { ...invoice, _lookupCustomerId: customerId } }];\n"
            ),
            position=[1600, 500],
        )
    )

    # ── 10. Fetch Customer ──
    nodes.append(
        supabase_select(
            name="Fetch Customer",
            table="acct_customers",
            select="*",
            filters="id=eq.{{ $json._lookupCustomerId }}",
            position=[1820, 500],
            single=True,
        )
    )

    # ── 11. Merge Customer Into Invoice ──
    nodes.append(
        code_node(
            name="Merge Customer Into Invoice",
            js_code=(
                "const customer = $input.first().json;\n"
                "const invoice = $('Lookup Customer').first().json;\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    ...invoice,\n"
                "    _customer: customer || {},\n"
                "    _customerFound: !!(customer && customer.id),\n"
                "    customer_name: customer.name || customer.company_name || '',\n"
                "    customer_email: customer.email || '',\n"
                "  }\n"
                "}];\n"
            ),
            position=[2060, 500],
        )
    )

    # ── 12. Calculate Tax ──
    nodes.append(
        code_node(
            name="Calculate Tax",
            js_code=(
                "// Compute line_items totals, subtotal, VAT, total — all in cents\n"
                "const invoice = $input.first().json;\n"
                "const config = invoice._config || {};\n"
                "const vatRate = parseFloat(config.vat_rate) || 0.15;\n"
                "\n"
                "let lineItemsRaw = invoice.line_items || '[]';\n"
                "let lineItems;\n"
                "try {\n"
                "  lineItems = typeof lineItemsRaw === 'string' ? JSON.parse(lineItemsRaw) : lineItemsRaw;\n"
                "} catch(e) {\n"
                "  lineItems = [];\n"
                "}\n"
                "\n"
                "let subtotal_cents = 0;\n"
                "let vat_cents = 0;\n"
                "const processed = [];\n"
                "\n"
                "for (const item of lineItems) {\n"
                "  const qty = parseInt(item.quantity) || 1;\n"
                "  // unit_price_cents: price in cents (integer)\n"
                "  const unitPriceCents = parseInt(item.unit_price_cents) || 0;\n"
                "  const isVatable = item.vat_exempt !== true;\n"
                "  \n"
                "  const lineSubtotal = unitPriceCents * qty;\n"
                "  const lineVat = isVatable ? Math.round(lineSubtotal * vatRate) : 0;\n"
                "  const lineTotal = lineSubtotal + lineVat;\n"
                "  \n"
                "  subtotal_cents += lineSubtotal;\n"
                "  vat_cents += lineVat;\n"
                "  \n"
                "  processed.push({\n"
                "    description: item.description || '',\n"
                "    item_code: item.item_code || '',\n"
                "    quantity: qty,\n"
                "    unit_price_cents: unitPriceCents,\n"
                "    vat_exempt: !isVatable,\n"
                "    line_subtotal_cents: lineSubtotal,\n"
                "    line_vat_cents: lineVat,\n"
                "    line_total_cents: lineTotal,\n"
                "  });\n"
                "}\n"
                "\n"
                "const total_cents = subtotal_cents + vat_cents;\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    ...invoice,\n"
                "    processed_line_items: processed,\n"
                "    subtotal_cents,\n"
                "    vat_cents,\n"
                "    total_cents,\n"
                "    vat_rate: vatRate,\n"
                "    currency: 'ZAR',\n"
                "  }\n"
                "}];\n"
            ),
            position=[2300, 500],
        )
    )

    # ── 13. Generate Invoice Number (Supabase RPC) ──
    nodes.append(
        code_node(
            name="Prepare RPC Params",
            js_code=(
                "const invoice = $input.first().json;\n"
                "const clientId = invoice.client_id || invoice._config?.client_id || '';\n"
                "return [{ json: { p_client_id: clientId, _invoice: invoice } }];\n"
            ),
            position=[2520, 500],
        )
    )

    nodes.append(
        supabase_rpc(
            name="Generate Invoice Number",
            function_name="acct_generate_invoice_number",
            position=[2740, 500],
        )
    )

    # ── 14. Attach Invoice Number ──
    nodes.append(
        code_node(
            name="Attach Invoice Number",
            js_code=(
                "const rpcResult = $input.first().json;\n"
                "const invoice = $('Prepare RPC Params').first().json._invoice;\n"
                "const invoiceNumber = rpcResult.invoice_number || rpcResult || `INV-${Date.now()}`;\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    ...invoice,\n"
                "    invoice_number: typeof invoiceNumber === 'string' ? invoiceNumber : String(invoiceNumber),\n"
                "  }\n"
                "}];\n"
            ),
            position=[2960, 500],
        )
    )

    # ── 15. Check High Value ──
    nodes.append(
        code_node(
            name="Check High Value",
            js_code=(
                "const invoice = $input.first().json;\n"
                "const config = invoice._config || {};\n"
                "// Default threshold: R50,000 = 5000000 cents\n"
                "const threshold = parseInt(config.high_value_threshold) || 5000000;\n"
                "const isHighValue = invoice.total_cents > threshold;\n"
                "\n"
                "return [{ json: { ...invoice, _isHighValue: isHighValue, _threshold: threshold } }];\n"
            ),
            position=[3180, 500],
        )
    )

    nodes.append(
        if_node(
            name="Is High Value?",
            left_value="{{ $json._isHighValue }}",
            operator_type="boolean",
            operation="true",
            position=[3400, 500],
        )
    )

    # ── 16. High Value: Create Approval Task ──
    nodes.append(
        code_node(
            name="Prepare Approval Task",
            js_code=(
                "const inv = $input.first().json;\n"
                "const totalRands = (inv.total_cents / 100).toFixed(2);\n"
                "return [{\n"
                "  json: {\n"
                "    action: 'task_created',\n"
                "    data: {\n"
                "      client_id: inv.client_id,\n"
                "      invoice_id: inv.id,\n"
                "      invoice_number: inv.invoice_number,\n"
                "      customer_name: inv.customer_name,\n"
                "      total_cents: inv.total_cents,\n"
                "      total_display: `R ${totalRands}`,\n"
                "      task_type: 'high_value_approval',\n"
                "      priority: 'high',\n"
                "      description: `High-value invoice ${inv.invoice_number} for ${inv.customer_name} - R ${totalRands} requires approval`,\n"
                "    }\n"
                "  }\n"
                "}];\n"
            ),
            position=[3640, 300],
        )
    )

    nodes.append(
        portal_status_webhook(
            name="Portal: Task Created",
            action="task_created",
            position=[3880, 300],
        )
    )

    # ── 17. High value: update invoice as pending_approval ──
    nodes.append(
        code_node(
            name="Set Pending Approval",
            js_code=(
                "const inv = $('Prepare Approval Task').first().json.data;\n"
                "return [{\n"
                "  json: {\n"
                "    id: inv.invoice_id,\n"
                "    updatePayload: {\n"
                "      status: 'pending_approval',\n"
                "      invoice_number: inv.invoice_number,\n"
                "      subtotal_cents: $('Check High Value').first().json.subtotal_cents,\n"
                "      vat_cents: $('Check High Value').first().json.vat_cents,\n"
                "      total_cents: inv.total_cents,\n"
                "      updated_at: new Date().toISOString(),\n"
                "    }\n"
                "  }\n"
                "}];\n"
            ),
            position=[4120, 300],
        )
    )

    nodes.append(
        supabase_update(
            name="Update Invoice Pending",
            table="acct_invoices",
            match_col="id",
            position=[4360, 300],
        )
    )

    # ── 18. Normal: Accounting Software Adapter ──
    nodes.append(
        code_node(
            name="Prepare Adapter",
            js_code=(
                "const inv = $input.first().json;\n"
                "const config = inv._config || {};\n"
                "const software = (config.accounting_software || 'none').toLowerCase();\n"
                "return [{ json: { ...inv, _accounting_software: software } }];\n"
            ),
            position=[3640, 700],
        )
    )

    nodes.append(
        switch_node(
            name="Accounting Software",
            rules=[
                {"leftValue": "={{ $json._accounting_software }}", "rightValue": "quickbooks", "output": "quickbooks"},
                {"leftValue": "={{ $json._accounting_software }}", "rightValue": "xero", "output": "xero"},
                {"leftValue": "={{ $json._accounting_software }}", "rightValue": "sage", "output": "sage"},
            ],
            position=[3880, 700],
        )
    )

    # QuickBooks HTTP Request
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json._config.quickbooks_api_url || 'https://quickbooks.api.intuit.com/v3/company/' + ($json._config.qbo_company_id || '') + '/invoice' }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Accept", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({"
                "  Line: $json.processed_line_items.map(li => ({"
                "    Amount: li.line_subtotal_cents / 100,"
                "    Description: li.description,"
                "    DetailType: 'SalesItemLineDetail',"
                "    SalesItemLineDetail: { Qty: li.quantity, UnitPrice: li.unit_price_cents / 100 }"
                "  })),"
                "  CustomerRef: { value: $json._customer?.external_id || '' },"
                "  DocNumber: $json.invoice_number,"
                "  CurrencyRef: { value: 'ZAR' }"
                "}) }}"
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Sync QuickBooks",
        "type": "n8n-nodes-base.httpRequest",
        "position": [4140, 500],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # Xero HTTP Request
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json._config.xero_api_url || 'https://api.xero.com/api.xro/2.0/Invoices' }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Accept", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({"
                "  Type: 'ACCREC',"
                "  Contact: { ContactID: $json._customer?.external_id || '' },"
                "  InvoiceNumber: $json.invoice_number,"
                "  CurrencyCode: 'ZAR',"
                "  LineItems: $json.processed_line_items.map(li => ({"
                "    Description: li.description,"
                "    Quantity: li.quantity,"
                "    UnitAmount: li.unit_price_cents / 100,"
                "    TaxType: li.vat_exempt ? 'EXEMPTOUTPUT' : 'OUTPUT2'"
                "  }))"
                "}) }}"
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Sync Xero",
        "type": "n8n-nodes-base.httpRequest",
        "position": [4140, 700],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # Sage HTTP Request
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $json._config.sage_api_url || 'https://api.accounting.sage.com/v3.1/sales_invoices' }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Accept", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({"
                "  contact_id: $json._customer?.external_id || '',"
                "  reference: $json.invoice_number,"
                "  currency: 'ZAR',"
                "  invoice_lines: $json.processed_line_items.map(li => ({"
                "    description: li.description,"
                "    quantity: li.quantity,"
                "    unit_price: li.unit_price_cents / 100"
                "  }))"
                "}) }}"
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Sync Sage",
        "type": "n8n-nodes-base.httpRequest",
        "position": [4140, 900],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # None: skip sync
    nodes.append(noop_node(name="Skip Sync", position=[4140, 1100]))

    # ── 19. Merge After Adapter ──
    nodes.append(
        code_node(
            name="Merge After Adapter",
            js_code=(
                "const item = $input.first().json;\n"
                "// Extract external ID from whichever adapter responded\n"
                "const externalId = item.Id || item.InvoiceID || item.id || null;\n"
                "const prevInvoice = (() => {\n"
                "  try { return $('Prepare Adapter').first().json; } catch(e) { return {}; }\n"
                "})();\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    ...prevInvoice,\n"
                "    external_id: externalId,\n"
                "    sync_status: externalId ? 'synced' : 'local_only',\n"
                "  }\n"
                "}];\n"
            ),
            position=[4400, 700],
        )
    )

    # ── 20. Update Invoice Record ──
    nodes.append(
        code_node(
            name="Prepare Invoice Update",
            js_code=(
                "const inv = $input.first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    id: inv.id,\n"
                "    updatePayload: {\n"
                "      status: 'approved',\n"
                "      invoice_number: inv.invoice_number,\n"
                "      subtotal_cents: inv.subtotal_cents,\n"
                "      vat_cents: inv.vat_cents,\n"
                "      total_cents: inv.total_cents,\n"
                "      external_id: inv.external_id,\n"
                "      sync_status: inv.sync_status,\n"
                "      processed_line_items: inv.processed_line_items,\n"
                "      updated_at: new Date().toISOString(),\n"
                "    }\n"
                "  }\n"
                "}];\n"
            ),
            position=[4640, 700],
        )
    )

    nodes.append(
        supabase_update(
            name="Update Invoice Record",
            table="acct_invoices",
            match_col="id",
            position=[4880, 700],
        )
    )

    # ── 21. Status Update: invoice_created ──
    nodes.append(
        code_node(
            name="Prepare Status Update",
            js_code=(
                "const inv = $('Prepare Invoice Update').first().json;\n"
                "const totalRands = ((inv.updatePayload.total_cents || 0) / 100).toFixed(2);\n"
                "return [{\n"
                "  json: {\n"
                "    client_id: $('Merge After Adapter').first().json.client_id,\n"
                "    invoice_id: inv.id,\n"
                "    invoice_number: inv.updatePayload.invoice_number,\n"
                "    total_display: `R ${totalRands}`,\n"
                "    status: inv.updatePayload.status,\n"
                "  }\n"
                "}];\n"
            ),
            position=[5120, 600],
        )
    )

    nodes.append(
        portal_status_webhook(
            name="Portal: Invoice Created",
            action="invoice_created",
            position=[5360, 600],
        )
    )

    # ── 22. Audit Log: INVOICE_CREATED ──
    nodes.append(
        code_node(
            name="Prepare Audit Log",
            js_code=(
                "const inv = $('Prepare Invoice Update').first().json;\n"
                "const source = $('Merge After Adapter').first().json;\n"
                "return [{\n"
                "  json: {\n"
                "    client_id: source.client_id,\n"
                "    entity_type: 'invoice',\n"
                "    entity_id: inv.id,\n"
                "    event_type: 'INVOICE_CREATED',\n"
                "    action: 'invoice_created',\n"
                "    actor: 'system',\n"
                "    result: 'success',\n"
                "    metadata: {\n"
                "      invoice_number: inv.updatePayload.invoice_number,\n"
                "      total_cents: inv.updatePayload.total_cents,\n"
                "      sync_status: inv.updatePayload.sync_status,\n"
                "      source: 'n8n',\n"
                "    }\n"
                "  }\n"
                "}];\n"
            ),
            position=[5600, 600],
        )
    )

    nodes.append(
        portal_status_webhook(
            name="Portal: Audit Log",
            action="audit_log",
            position=[5840, 600],
        )
    )

    # ── 23. Back to Loop ──
    nodes.append(noop_node(name="Back to Loop", position=[6060, 500]))

    # ── 24. Respond Webhook ──
    nodes.append(
        respond_webhook(
            name="Respond Webhook",
            position=[6300, 800],
        )
    )

    # ── 25. Build Summary ──
    nodes.append(
        code_node(
            name="Build Summary",
            js_code=(
                "const items = $input.all();\n"
                "\n"
                "let totalProcessed = 0;\n"
                "let totalCents = 0;\n"
                "let approvedCount = 0;\n"
                "let pendingApprovalCount = 0;\n"
                "const summaryLines = [];\n"
                "\n"
                "for (const item of items) {\n"
                "  const inv = item.json;\n"
                "  if (inv && inv.invoice_number) {\n"
                "    totalProcessed++;\n"
                "    totalCents += inv.total_cents || 0;\n"
                "    if (inv._isHighValue) {\n"
                "      pendingApprovalCount++;\n"
                "    } else {\n"
                "      approvedCount++;\n"
                "    }\n"
                "    const rands = ((inv.total_cents || 0) / 100).toFixed(2);\n"
                "    summaryLines.push(`${inv.invoice_number} - ${inv.customer_name || 'Unknown'} - R ${rands}`);\n"
                "  }\n"
                "}\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    success: true,\n"
                "    total_processed: totalProcessed,\n"
                "    total_invoiced_cents: totalCents,\n"
                "    total_invoiced_display: `R ${(totalCents / 100).toFixed(2)}`,\n"
                "    approved: approvedCount,\n"
                "    pending_approval: pendingApprovalCount,\n"
                "    invoices: summaryLines,\n"
                "    completed_at: new Date().toISOString(),\n"
                "  }\n"
                "}];\n"
            ),
            position=[6540, 600],
        )
    )

    return nodes


# ══════════════════════════════════════════════════════════════
# CONNECTIONS
# ══════════════════════════════════════════════════════════════


def build_connections() -> dict:
    """Build connections for the Invoice Creation Engine workflow."""
    return {
        # Triggers -> Load Config
        "Hourly Draft Check": {
            "main": [[conn("Load Client Config")]],
        },
        "Manual Trigger": {
            "main": [[conn("Load Client Config")]],
        },
        "Invoice Webhook": {
            "main": [[conn("Load Client Config")]],
        },
        # Config -> Drafts -> Merge -> Check
        "Load Client Config": {
            "main": [[conn("Read Draft Invoices")]],
        },
        "Read Draft Invoices": {
            "main": [[conn("Merge Sources")]],
        },
        "Merge Sources": {
            "main": [[conn("Has Items?")]],
        },
        # Has Items: true -> Loop, false -> Build Summary
        "Has Items?": {
            "main": [
                [conn("Loop Over Invoices")],
                [conn("Build Summary")],
            ],
        },
        # Loop: output 0 = done, output 1 = each item
        "Loop Over Invoices": {
            "main": [
                [conn("Build Summary")],
                [conn("Lookup Customer")],
            ],
        },
        # Customer lookup chain
        "Lookup Customer": {
            "main": [[conn("Fetch Customer")]],
        },
        "Fetch Customer": {
            "main": [[conn("Merge Customer Into Invoice")]],
        },
        "Merge Customer Into Invoice": {
            "main": [[conn("Calculate Tax")]],
        },
        # Tax -> Invoice Number -> High Value Check
        "Calculate Tax": {
            "main": [[conn("Prepare RPC Params")]],
        },
        "Prepare RPC Params": {
            "main": [[conn("Generate Invoice Number")]],
        },
        "Generate Invoice Number": {
            "main": [[conn("Attach Invoice Number")]],
        },
        "Attach Invoice Number": {
            "main": [[conn("Check High Value")]],
        },
        "Check High Value": {
            "main": [[conn("Is High Value?")]],
        },
        # Is High Value: true -> approval, false -> adapter
        "Is High Value?": {
            "main": [
                [conn("Prepare Approval Task")],
                [conn("Prepare Adapter")],
            ],
        },
        # High-value approval path
        "Prepare Approval Task": {
            "main": [[conn("Portal: Task Created")]],
        },
        "Portal: Task Created": {
            "main": [[conn("Set Pending Approval")]],
        },
        "Set Pending Approval": {
            "main": [[conn("Update Invoice Pending")]],
        },
        "Update Invoice Pending": {
            "main": [[conn("Back to Loop")]],
        },
        # Normal path: accounting software adapter
        "Prepare Adapter": {
            "main": [[conn("Accounting Software")]],
        },
        # Switch outputs: 0=quickbooks, 1=xero, 2=sage, 3=fallback(none)
        "Accounting Software": {
            "main": [
                [conn("Sync QuickBooks")],
                [conn("Sync Xero")],
                [conn("Sync Sage")],
                [conn("Skip Sync")],
            ],
        },
        # All adapter outputs merge
        "Sync QuickBooks": {
            "main": [[conn("Merge After Adapter")]],
        },
        "Sync Xero": {
            "main": [[conn("Merge After Adapter")]],
        },
        "Sync Sage": {
            "main": [[conn("Merge After Adapter")]],
        },
        "Skip Sync": {
            "main": [[conn("Merge After Adapter")]],
        },
        # Post-adapter: update -> status -> audit -> loop back
        "Merge After Adapter": {
            "main": [[conn("Prepare Invoice Update")]],
        },
        "Prepare Invoice Update": {
            "main": [[conn("Update Invoice Record")]],
        },
        "Update Invoice Record": {
            "main": [[conn("Prepare Status Update")]],
        },
        "Prepare Status Update": {
            "main": [[conn("Portal: Invoice Created")]],
        },
        "Portal: Invoice Created": {
            "main": [[conn("Prepare Audit Log")]],
        },
        "Prepare Audit Log": {
            "main": [[conn("Portal: Audit Log")]],
        },
        "Portal: Audit Log": {
            "main": [[conn("Back to Loop")]],
        },
        # Loop back
        "Back to Loop": {
            "main": [[conn("Loop Over Invoices")]],
        },
        # Summary also feeds the webhook response
        "Build Summary": {
            "main": [[conn("Respond Webhook")]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY
# ══════════════════════════════════════════════════════════════

WORKFLOW_NAME = "ACCT-02 Invoice Creation Engine"
OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"
OUTPUT_FILENAME = "wf02_invoice_creation.json"


def build_workflow() -> dict:
    """Assemble the complete workflow JSON."""
    return build_workflow_json(
        name=WORKFLOW_NAME,
        nodes=build_nodes(),
        connections=build_connections(),
    )


def save_workflow(workflow: dict) -> Path:
    """Save workflow JSON to file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILENAME

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(workflow: dict) -> None:
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])

    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(description="WF02 Invoice Creation Engine")
    parser.add_argument(
        "action",
        nargs="?",
        default="build",
        choices=["build", "deploy", "activate"],
    )
    parsed = parser.parse_args()
    action = parsed.action

    print("=" * 60)
    print("ACCT-02 INVOICE CREATION ENGINE")
    print("=" * 60)

    # Build
    print("\nBuilding workflow...")
    workflow = build_workflow()
    output_path = save_workflow(workflow)
    print_workflow_stats(workflow)
    print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # Deploy / Activate
    if action in ("deploy", "activate"):
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

            # Check if workflow already exists (by name)
            existing = None
            try:
                all_wfs = client.list_workflows()
                for wf in all_wfs:
                    if wf["name"] == workflow["name"]:
                        existing = wf
                        break
            except Exception:
                pass

            if existing:
                update_payload = {
                    "name": workflow["name"],
                    "nodes": workflow["nodes"],
                    "connections": workflow["connections"],
                    "settings": workflow["settings"],
                }
                result = client.update_workflow(existing["id"], update_payload)
                wf_id = result.get("id")
                print(f"  Updated: {result.get('name')} (ID: {wf_id})")
            else:
                create_payload = {
                    "name": workflow["name"],
                    "nodes": workflow["nodes"],
                    "connections": workflow["connections"],
                    "settings": workflow["settings"],
                }
                result = client.create_workflow(create_payload)
                wf_id = result.get("id")
                print(f"  Created: {result.get('name')} (ID: {wf_id})")

            if action == "activate" and wf_id:
                print(f"  Activating...")
                client.activate_workflow(wf_id)
                print(f"  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Open the workflow in n8n UI to verify node connections")
    print("  2. Create Supabase tables: acct_config, acct_invoices, acct_customers")
    print("  3. Create Supabase RPC function: acct_generate_invoice_number")
    print("  4. Configure accounting software credentials (QuickBooks/Xero/Sage)")
    print("  5. Set portal webhook secret (N8N_WEBHOOK_SECRET)")
    print("  6. Test with Manual Trigger -> check draft invoice processing")
    print("  7. Test webhook: POST /accounting/create-invoice")
    print("  8. Once verified, activate the hourly schedule trigger")


if __name__ == "__main__":
    main()
