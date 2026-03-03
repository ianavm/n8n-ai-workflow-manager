"""
Accounting Department - Sales & Invoicing (WF-01) Builder & Deployer

Builds the Sales to Invoice workflow that handles:
- Validating customers and line items
- VAT/tax calculations (15% SA standard)
- Invoice creation in Xero
- PDF generation and sending via Gmail/WhatsApp
- Follow-up scheduling
- Audit logging

Usage:
    python tools/deploy_accounting_wf01.py build
    python tools/deploy_accounting_wf01.py deploy
    python tools/deploy_accounting_wf01.py activate
"""

import json
import sys
import uuid
import os
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from credentials import CREDENTIALS

# ── Credential Constants (from centralized module) ────────────
CRED_OPENROUTER = CREDENTIALS["openrouter"]
CRED_GMAIL = CREDENTIALS["gmail"]
CRED_AIRTABLE = CREDENTIALS["airtable"]
CRED_XERO = CREDENTIALS["xero"]
CRED_WHATSAPP_SEND = CREDENTIALS["whatsapp_send"]
CRED_GOOGLE_SHEETS = CREDENTIALS["google_sheets"]

# ── Airtable IDs ──────────────────────────────────────────────
AIRTABLE_BASE_ID = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
TABLE_CUSTOMERS = os.getenv("ACCOUNTING_TABLE_CUSTOMERS", "REPLACE_WITH_TABLE_ID")
TABLE_PRODUCTS = os.getenv("ACCOUNTING_TABLE_PRODUCTS_SERVICES", "REPLACE_WITH_TABLE_ID")
TABLE_INVOICES = os.getenv("ACCOUNTING_TABLE_INVOICES", "REPLACE_WITH_TABLE_ID")
TABLE_TASKS = os.getenv("ACCOUNTING_TABLE_TASKS", "REPLACE_WITH_TABLE_ID")
TABLE_AUDIT_LOG = os.getenv("ACCOUNTING_TABLE_AUDIT_LOG", "REPLACE_WITH_TABLE_ID")
TABLE_SYSTEM_CONFIG = os.getenv("ACCOUNTING_TABLE_SYSTEM_CONFIG", "REPLACE_WITH_TABLE_ID")


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════
# WF-01: SALES & INVOICING (AR)
# ══════════════════════════════════════════════════════════════

def build_nodes():
    """Build all 32 nodes for the Sales & Invoicing workflow."""
    nodes = []

    # ── 1. Hourly Invoice Check (scheduleTrigger) ──

    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 8-17 * * 1-5"}]
            }
        },
        "id": uid(),
        "name": "Hourly Invoice Check",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    # ── 2. Manual Trigger ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # ── 3. Invoice Request Webhook ──

    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "accounting/create-invoice",
            "options": {},
            "responseMode": "responseNode",
        },
        "id": uid(),
        "name": "Invoice Request Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 800],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # ── 3b. Webhook Auth Check ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const authHeader = $input.first().json.headers?.authorization || '';\n"
                "const expected = $env.WEBHOOK_AUTH_TOKEN;\n"
                "if (!expected || authHeader !== `Bearer ${expected}`) {\n"
                "  throw new Error('Unauthorized: invalid or missing Bearer token');\n"
                "}\n"
                "return $input.all();"
            ),
        },
        "id": uid(),
        "name": "Webhook Auth Check",
        "type": "n8n-nodes-base.code",
        "position": [400, 800],
        "typeVersion": 2,
    })

    # ── 4. System Config (set) ──

    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.format('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                    {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                    {"id": uid(), "name": "vatRate", "value": "0.15", "type": "string"},
                    {"id": uid(), "name": "invoicePrefix", "value": "AVM", "type": "string"},
                    {"id": uid(), "name": "defaultCurrency", "value": "ZAR", "type": "string"},
                    {"id": uid(), "name": "highValueThreshold", "value": "50000", "type": "string"},
                    {"id": uid(), "name": "xeroTenantId", "value": os.getenv("ACCOUNTING_XERO_TENANT_ID", ""), "type": "string"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [460, 600],
        "typeVersion": 3.4,
    })

    # ── 5. Read Draft Invoices (airtable search) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "filterByFormula": "{Status} = 'Draft'",
        },
        "id": uid(),
        "name": "Read Draft Invoices",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 600],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 6. Merge Sources (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const airtableItems = $input.all();\n"
                "let webhookData = null;\n"
                "try { webhookData = $('Invoice Request Webhook').first(); } catch(e) { /* webhook not triggered */ }\n"
                "\n"
                "const items = [];\n"
                "\n"
                "// Add Airtable draft invoices\n"
                "for (const item of airtableItems) {\n"
                "  if (item.json && item.json['Invoice ID']) {\n"
                "    items.push(item.json);\n"
                "  }\n"
                "}\n"
                "\n"
                "// Add webhook invoice request if present\n"
                "if (webhookData && webhookData.json && webhookData.json.body) {\n"
                "  const body = webhookData.json.body;\n"
                "  items.push({\n"
                "    'Invoice ID': `INV-${Date.now()}`,\n"
                "    'Customer ID': body.customer_id || '',\n"
                "    'Customer Name': body.customer_name || '',\n"
                "    'Line Items JSON': JSON.stringify(body.line_items || []),\n"
                "    'Source': body.source || 'Manual',\n"
                "    'Status': 'Draft',\n"
                "    isWebhook: true,\n"
                "  });\n"
                "}\n"
                "\n"
                "if (items.length === 0) {\n"
                "  return [{json: {totalItems: 0, source: 'none'}}];\n"
                "}\n"
                "return items.map(item => ({json: item}));\n"
            ),
        },
        "id": uid(),
        "name": "Merge Sources",
        "type": "n8n-nodes-base.code",
        "position": [900, 600],
        "typeVersion": 2,
    })

    # ── 7. Has Items? (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json['Invoice ID'] }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "isNotEmpty"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Has Items?",
        "type": "n8n-nodes-base.if",
        "position": [1120, 600],
        "typeVersion": 2,
    })

    # ── 8. Loop Over Invoices (splitInBatches) ──

    nodes.append({
        "parameters": {"batchSize": 1, "options": {}},
        "id": uid(),
        "name": "Loop Over Invoices",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1360, 500],
        "typeVersion": 3,
    })

    # ── 9. Lookup Customer (airtable search) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CUSTOMERS},
            "filterByFormula": "{Customer ID} = '{{ $json[\"Customer ID\"] }}'",
        },
        "id": uid(),
        "name": "Lookup Customer",
        "type": "n8n-nodes-base.airtable",
        "position": [1600, 500],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 10. Customer Exists? (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json['Customer Name'] }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "isNotEmpty"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Customer Exists?",
        "type": "n8n-nodes-base.if",
        "position": [1820, 500],
        "typeVersion": 2,
    })

    # ── 11. Create Customer (airtable create) ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CUSTOMERS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Customer ID": "={{ $json['Customer ID'] }}",
                    "Customer Name": "={{ $json['Customer Name'] }}",
                    "Email": "={{ $json.customerEmail || $json['Email'] || '' }}",
                    "Phone": "={{ $json.customerPhone || $json['Phone'] || '' }}",
                    "Preferred Channel": "Email",
                    "Status": "Active",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Customer",
        "type": "n8n-nodes-base.airtable",
        "position": [2060, 700],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 12. Merge Customer Data (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const invoice = $('Loop Over Invoices').first().json;\n"
                "const customerData = $input.first().json;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...invoice,\n"
                "    customerName: customerData['Customer Name'] || invoice['Customer Name'] || '',\n"
                "    customerEmail: customerData['Email'] || invoice['Email'] || '',\n"
                "    customerPhone: customerData['Phone'] || invoice['Phone'] || '',\n"
                "    preferredChannel: customerData['Preferred Channel'] || 'Email',\n"
                "    xeroContactId: customerData['Xero Contact ID'] || '',\n"
                "    customerId: customerData['Customer ID'] || invoice['Customer ID'] || '',\n"
                "    paymentTerms: customerData['Payment Terms'] || '30 days',\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Merge Customer Data",
        "type": "n8n-nodes-base.code",
        "position": [2300, 500],
        "typeVersion": 2,
    })

    # ── 13. Lookup Products (airtable search) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_PRODUCTS},
            "filterByFormula": "{Status} = 'Active'",
        },
        "id": uid(),
        "name": "Lookup Products",
        "type": "n8n-nodes-base.airtable",
        "position": [2520, 500],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 14. Calculate Tax (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const invoice = $input.first().json;\n"
                "const products = $('Lookup Products').all();\n"
                "const vatRate = parseFloat($('System Config').first().json.vatRate) || 0.15;\n"
                "\n"
                "const TAX_TYPE_MAP = {'STANDARD_15': 'OUTPUT2', 'ZERO_RATED': 'OUTPUTZERO', 'EXEMPT': 'EXEMPTOUTPUT'};\n"
                "\n"
                "const lineItemsRaw = invoice['Line Items JSON'] || invoice.line_items || '[]';\n"
                "let lineItems;\n"
                "try {\n"
                "  lineItems = typeof lineItemsRaw === 'string' ? JSON.parse(lineItemsRaw) : lineItemsRaw;\n"
                "} catch(e) {\n"
                "  lineItems = [];\n"
                "}\n"
                "\n"
                "let subtotal = 0;\n"
                "let totalVat = 0;\n"
                "const processedItems = [];\n"
                "const xeroLineItems = [];\n"
                "\n"
                "for (const item of lineItems) {\n"
                "  const product = products.find(p => p.json['Item Code'] === item.item_code || p.json['Item Code'] === item.code);\n"
                "  const unitPrice = item.unit_price || (product ? product.json['Unit Price'] : 0);\n"
                "  const qty = item.quantity || 1;\n"
                "  const vatCode = item.vat_rate_code || (product ? product.json['VAT Rate Code'] : 'STANDARD_15');\n"
                "  const taxType = TAX_TYPE_MAP[vatCode] || 'OUTPUT2';\n"
                "  \n"
                "  const lineSubtotal = unitPrice * qty;\n"
                "  const lineVatRate = vatCode === 'STANDARD_15' ? vatRate : 0;\n"
                "  const lineVat = lineSubtotal * lineVatRate;\n"
                "  \n"
                "  subtotal += lineSubtotal;\n"
                "  totalVat += lineVat;\n"
                "  \n"
                "  processedItems.push({\n"
                "    item_code: item.item_code || item.code,\n"
                "    description: item.description || (product ? product.json['Description'] : ''),\n"
                "    quantity: qty,\n"
                "    unit_price: unitPrice,\n"
                "    vat_rate_code: vatCode,\n"
                "    vat_rate: lineVatRate,\n"
                "    line_subtotal: lineSubtotal,\n"
                "    line_vat: lineVat,\n"
                "    line_total: lineSubtotal + lineVat,\n"
                "  });\n"
                "  \n"
                "  xeroLineItems.push({\n"
                "    ItemCode: item.item_code || item.code || (product ? product.json['Item Code'] : ''),\n"
                "    Description: item.description || (product ? product.json['Description'] : ''),\n"
                "    Quantity: qty,\n"
                "    UnitAmount: unitPrice,\n"
                "    TaxType: taxType,\n"
                "    AccountCode: (product ? product.json['Revenue Account Code'] : '') || '200',\n"
                "    LineAmount: lineSubtotal,\n"
                "  });\n"
                "}\n"
                "\n"
                "const total = subtotal + totalVat;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...invoice,\n"
                "    processedLineItems: processedItems,\n"
                "    lineItemsJson: JSON.stringify(xeroLineItems),\n"
                "    subtotal: Math.round(subtotal * 100) / 100,\n"
                "    vatAmount: Math.round(totalVat * 100) / 100,\n"
                "    total: Math.round(total * 100) / 100,\n"
                "    currency: 'ZAR',\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Calculate Tax",
        "type": "n8n-nodes-base.code",
        "position": [2740, 500],
        "typeVersion": 2,
    })

    # ── 15. Generate Invoice Number (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const invoice = $input.first().json;\n"
                "const prefix = $('System Config').first().json.invoicePrefix || 'AVM';\n"
                "const timestamp = Date.now().toString().slice(-6);\n"
                "const invoiceNumber = `${prefix}-${timestamp}`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...invoice,\n"
                "    invoiceNumber: invoiceNumber,\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Generate Invoice Number",
        "type": "n8n-nodes-base.code",
        "position": [2960, 500],
        "typeVersion": 2,
    })

    # ── 16. Check High Value (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.total }}",
                        "rightValue": "={{ $('System Config').first().json.highValueThreshold }}",
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Check High Value",
        "type": "n8n-nodes-base.if",
        "position": [3180, 500],
        "typeVersion": 2,
    })

    # ── 17. Create Approval Task (airtable create) ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Task ID": "={{ 'TASK-' + Date.now() }}",
                    "Type": "Invoice Approval",
                    "Priority": "High",
                    "Status": "Open",
                    "Description": "=High-value invoice {{ $json.invoiceNumber }} for {{ $json.customerName }} - R {{ $json.total }}. Requires manual approval before sending.",
                    "Related Record ID": "={{ $json.invoiceNumber }}",
                    "Related Table": "Invoices",
                    "Owner": "ian@anyvisionmedia.com",
                    "Approval Token": "={{ $json.invoiceNumber }}-{{ Date.now() }}",
                    "Created At": "={{ $now.format('yyyy-MM-dd') }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Approval Task",
        "type": "n8n-nodes-base.airtable",
        "position": [3420, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 18. Send Approval Email (gmail) ──

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=APPROVAL REQUIRED: Invoice {{ $json.invoiceNumber }} - R {{ $json.total }}",
            "emailType": "html",
            "message": (
                "=<h2>High-Value Invoice Approval Required</h2>"
                "<p>Invoice <strong>{{ $json.invoiceNumber }}</strong> for <strong>{{ $json.customerName }}</strong> "
                "requires your approval before sending.</p>"
                "<table style='border-collapse:collapse;width:100%;max-width:500px;'>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>Invoice #</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>{{ $json.invoiceNumber }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>Customer</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>{{ $json.customerName }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>Subtotal</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>R {{ $json.subtotal }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>VAT</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>R {{ $json.vatAmount }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;font-size:18px;'><strong>Total</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;font-size:18px;color:#FF6D5A;'><strong>R {{ $json.total }}</strong></td></tr>"
                "</table>"
                "<br><p>This invoice exceeds the high-value threshold of R 50,000.</p>"
                "<p>Please review and approve or reject in the Airtable Tasks table.</p>"
            ),
            "options": {
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Send Approval Email",
        "type": "n8n-nodes-base.gmail",
        "position": [3660, 300],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── 19. Update Status Pending (airtable update) ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Invoice ID": "={{ $json['Invoice ID'] || $json.invoiceId }}",
                    "Status": "Pending Approval",
                    "Invoice Number": "={{ $json.invoiceNumber }}",
                    "Subtotal": "={{ $json.subtotal }}",
                    "VAT Amount": "={{ $json.vatAmount }}",
                    "Total": "={{ $json.total }}",
                    "Updated At": "={{ $now.format('yyyy-MM-dd HH:mm:ss') }}",
                },
                "matchingColumns": ["Invoice ID"],
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Status Pending",
        "type": "n8n-nodes-base.airtable",
        "position": [3900, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 20. Create Invoice in Xero (httpRequest) ──

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://api.xero.com/api.xro/2.0/Invoices",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": "={{ $('System Config').first().json.xeroTenantId || '' }}"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                '={\n'
                '  "Type": "ACCREC",\n'
                '  "Contact": {"ContactID": "{{ $json.xeroContactId || \'\' }}"},\n'
                '  "Date": "{{ $json.issueDate || $now.format(\'yyyy-MM-dd\') }}",\n'
                '  "DueDate": "{{ $json.dueDate }}",\n'
                '  "InvoiceNumber": "{{ $json.invoiceNumber }}",\n'
                '  "Reference": "{{ $json.invoiceNumber }}",\n'
                '  "CurrencyCode": "ZAR",\n'
                '  "Status": "AUTHORISED",\n'
                '  "LineItems": {{ $json.lineItemsJson }}\n'
                '}'
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Create Invoice in Xero",
        "type": "n8n-nodes-base.httpRequest",
        "position": [3420, 700],
        "typeVersion": 4.2,
        "credentials": {"xeroOAuth2Api": CRED_XERO},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 5000,
    })

    # ── 21. Update Invoice Record (airtable update) ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Invoice ID": "={{ $json['Invoice ID'] || $json.invoiceId }}",
                    "Status": "Sent",
                    "Invoice Number": "={{ $json.invoiceNumber }}",
                    "Xero Invoice ID": "={{ $json.Invoices ? $json.Invoices[0].InvoiceID : '' }}",
                    "Subtotal": "={{ $json.subtotal }}",
                    "VAT Amount": "={{ $json.vatAmount }}",
                    "Total": "={{ $json.total }}",
                    "Sent At": "={{ $now.format('yyyy-MM-dd HH:mm:ss') }}",
                    "Issue Date": "={{ $json.issueDate || $now.format('yyyy-MM-dd') }}",
                    "Due Date": "={{ $json.dueDate || '' }}",
                },
                "matchingColumns": ["Invoice ID"],
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Invoice Record",
        "type": "n8n-nodes-base.airtable",
        "position": [3660, 700],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 22. Build Invoice HTML (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const inv = $input.first().json;\n"
                "const items = inv.processedLineItems || [];\n"
                "\n"
                "const lineItemsHtml = items.map(item => \n"
                "  `<tr>\n"
                "    <td style=\"padding:8px;border-bottom:1px solid #eee;\">${item.item_code}</td>\n"
                "    <td style=\"padding:8px;border-bottom:1px solid #eee;\">${item.description}</td>\n"
                "    <td style=\"padding:8px;border-bottom:1px solid #eee;text-align:center;\">${item.quantity}</td>\n"
                "    <td style=\"padding:8px;border-bottom:1px solid #eee;text-align:right;\">R ${item.unit_price.toFixed(2)}</td>\n"
                "    <td style=\"padding:8px;border-bottom:1px solid #eee;text-align:right;\">R ${item.line_vat.toFixed(2)}</td>\n"
                "    <td style=\"padding:8px;border-bottom:1px solid #eee;text-align:right;\">R ${item.line_total.toFixed(2)}</td>\n"
                "  </tr>`\n"
                ").join('\\n');\n"
                "\n"
                "const html = `<!DOCTYPE html>\n"
                "<html>\n"
                "<head><meta charset=\"utf-8\"></head>\n"
                "<body style=\"margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f4;\">\n"
                "  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;margin:0 auto;background-color:#ffffff;\">\n"
                "    <tr>\n"
                "      <td style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">\n"
                "        <h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">TAX INVOICE</h1>\n"
                "        <p style=\"margin:5px 0 0;color:#666;\">AnyVision Media</p>\n"
                "      </td>\n"
                "    </tr>\n"
                "    <tr>\n"
                "      <td style=\"padding:20px 40px;\">\n"
                "        <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">\n"
                "          <tr>\n"
                "            <td width=\"50%\" style=\"vertical-align:top;\">\n"
                "              <p style=\"margin:0;font-size:13px;color:#666;\">Bill To:</p>\n"
                "              <p style=\"margin:4px 0;font-size:15px;\"><strong>${inv.customerName || inv['Customer Name'] || ''}</strong></p>\n"
                "              <p style=\"margin:0;font-size:13px;color:#666;\">${inv.customerEmail || ''}</p>\n"
                "            </td>\n"
                "            <td width=\"50%\" style=\"vertical-align:top;text-align:right;\">\n"
                "              <p style=\"margin:0;font-size:13px;color:#666;\">Invoice #: <strong>${inv.invoiceNumber}</strong></p>\n"
                "              <p style=\"margin:4px 0;font-size:13px;color:#666;\">Date: ${inv.issueDate || inv['Issue Date'] || new Date().toISOString().split('T')[0]}</p>\n"
                "              <p style=\"margin:4px 0;font-size:13px;color:#666;\">Due: ${inv.dueDate || inv['Due Date'] || ''}</p>\n"
                "            </td>\n"
                "          </tr>\n"
                "        </table>\n"
                "      </td>\n"
                "    </tr>\n"
                "    <tr>\n"
                "      <td style=\"padding:0 40px 20px;\">\n"
                "        <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">\n"
                "          <tr style=\"background-color:#f8f8f8;\">\n"
                "            <th style=\"padding:10px 8px;text-align:left;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;\">Code</th>\n"
                "            <th style=\"padding:10px 8px;text-align:left;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;\">Description</th>\n"
                "            <th style=\"padding:10px 8px;text-align:center;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;\">Qty</th>\n"
                "            <th style=\"padding:10px 8px;text-align:right;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;\">Unit Price</th>\n"
                "            <th style=\"padding:10px 8px;text-align:right;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;\">VAT</th>\n"
                "            <th style=\"padding:10px 8px;text-align:right;font-size:12px;color:#666;border-bottom:2px solid #FF6D5A;\">Total</th>\n"
                "          </tr>\n"
                "          ${lineItemsHtml}\n"
                "        </table>\n"
                "      </td>\n"
                "    </tr>\n"
                "    <tr>\n"
                "      <td style=\"padding:0 40px 20px;\">\n"
                "        <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">\n"
                "          <tr><td style=\"text-align:right;padding:4px 8px;color:#666;\">Subtotal:</td><td style=\"text-align:right;padding:4px 8px;width:120px;\"><strong>R ${inv.subtotal.toFixed(2)}</strong></td></tr>\n"
                "          <tr><td style=\"text-align:right;padding:4px 8px;color:#666;\">VAT (15%):</td><td style=\"text-align:right;padding:4px 8px;\"><strong>R ${inv.vatAmount.toFixed(2)}</strong></td></tr>\n"
                "          <tr style=\"border-top:2px solid #FF6D5A;\"><td style=\"text-align:right;padding:8px;font-size:18px;\">Total Due:</td><td style=\"text-align:right;padding:8px;font-size:18px;color:#FF6D5A;\"><strong>R ${inv.total.toFixed(2)}</strong></td></tr>\n"
                "        </table>\n"
                "      </td>\n"
                "    </tr>\n"
                "    <tr>\n"
                "      <td style=\"padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;\">\n"
                "        <p style=\"margin:0 0 8px;font-size:14px;\"><strong>Payment Details:</strong></p>\n"
                "        <p style=\"margin:0;font-size:13px;color:#666;line-height:1.6;\">\n"
                "          Bank: [Bank Name]<br>\n"
                "          Account: [Account Number]<br>\n"
                "          Branch Code: [Branch Code]<br>\n"
                "          Reference: ${inv.invoiceNumber}\n"
                "        </p>\n"
                "      </td>\n"
                "    </tr>\n"
                "    <tr>\n"
                "      <td style=\"padding:20px 40px;background-color:#f8f8f8;\">\n"
                "        <p style=\"margin:0;font-size:11px;color:#999;line-height:1.5;\">\n"
                "          AnyVision Media | Johannesburg, South Africa<br>\n"
                "          accounts@anyvisionmedia.com | Terms: ${inv.paymentTerms || '30 days'}\n"
                "        </p>\n"
                "      </td>\n"
                "    </tr>\n"
                "  </table>\n"
                "</body>\n"
                "</html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...inv,\n"
                "    emailHtml: html,\n"
                "    emailSubject: 'Invoice ' + inv.invoiceNumber + ' from AnyVision Media - R ' + inv.total.toFixed(2),\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Build Invoice HTML",
        "type": "n8n-nodes-base.code",
        "position": [3900, 700],
        "typeVersion": 2,
    })

    # ── 23. Send Invoice Email (gmail) ──

    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.customerEmail }}",
            "subject": "=Invoice {{ $json.invoiceNumber }} from AnyVision Media",
            "emailType": "html",
            "message": "={{ $json.emailHtml }}",
            "options": {
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Send Invoice Email",
        "type": "n8n-nodes-base.gmail",
        "position": [4140, 700],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── 24. Check WhatsApp Pref (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.preferredChannel }}",
                        "rightValue": "WhatsApp",
                        "operator": {"type": "string", "operation": "equals"},
                    },
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.preferredChannel }}",
                        "rightValue": "Both",
                        "operator": {"type": "string", "operation": "equals"},
                    },
                ],
                "combinator": "or",
            },
        },
        "id": uid(),
        "name": "Check WhatsApp Pref",
        "type": "n8n-nodes-base.if",
        "position": [4380, 700],
        "typeVersion": 2,
    })

    # ── 25. Send Invoice WhatsApp (httpRequest) ──

    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://graph.facebook.com/v18.0/{{ $env.WHATSAPP_PHONE_ID }}/messages",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                '={\n'
                '  "messaging_product": "whatsapp",\n'
                '  "to": "{{ $json.customerPhone }}",\n'
                '  "type": "template",\n'
                '  "template": {\n'
                '    "name": "invoice_notification",\n'
                '    "language": {"code": "en"},\n'
                '    "components": [{\n'
                '      "type": "body",\n'
                '      "parameters": [\n'
                '        {"type": "text", "text": "{{ $json.customerName }}"},\n'
                '        {"type": "text", "text": "{{ $json.invoiceNumber }}"},\n'
                '        {"type": "text", "text": "R {{ $json.total }}"}\n'
                '      ]\n'
                '    }]\n'
                '  }\n'
                '}'
            ),
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Send Invoice WhatsApp",
        "type": "n8n-nodes-base.httpRequest",
        "position": [4620, 600],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_WHATSAPP_SEND},
    })

    # ── 26. Schedule Follow-up (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const inv = $input.first().json;\n"
                "const dueDate = new Date(inv.dueDate || inv['Due Date']);\n"
                "\n"
                "if (isNaN(dueDate.getTime())) {\n"
                "  return { json: { ...inv, nextReminderDate: null } };\n"
                "}\n"
                "\n"
                "// T-3: 3 days before due\n"
                "const tMinus3 = new Date(dueDate);\n"
                "tMinus3.setDate(tMinus3.getDate() - 3);\n"
                "\n"
                "const today = new Date();\n"
                "today.setHours(0, 0, 0, 0);\n"
                "\n"
                "// Find the next reminder date that's in the future\n"
                "const reminderDates = [\n"
                "  { days: -3, date: tMinus3 },\n"
                "  { days: 0, date: new Date(dueDate) },\n"
                "  { days: 3, date: new Date(dueDate.getTime() + 3 * 86400000) },\n"
                "  { days: 7, date: new Date(dueDate.getTime() + 7 * 86400000) },\n"
                "  { days: 14, date: new Date(dueDate.getTime() + 14 * 86400000) },\n"
                "];\n"
                "\n"
                "let nextReminder = null;\n"
                "for (const r of reminderDates) {\n"
                "  if (r.date >= today) {\n"
                "    nextReminder = r.date.toISOString().split('T')[0];\n"
                "    break;\n"
                "  }\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...inv,\n"
                "    nextReminderDate: nextReminder,\n"
                "    reminderCount: 0,\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Schedule Follow-up",
        "type": "n8n-nodes-base.code",
        "position": [4860, 700],
        "typeVersion": 2,
    })

    # ── 27. Update Reminder Schedule (airtable update) ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Invoice ID": "={{ $json['Invoice ID'] || $json.invoiceId }}",
                    "Next Reminder Date": "={{ $json.nextReminderDate }}",
                    "Reminder Count": "={{ $json.reminderCount }}",
                },
                "matchingColumns": ["Invoice ID"],
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Reminder Schedule",
        "type": "n8n-nodes-base.airtable",
        "position": [5100, 700],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 28. Write Audit Log (airtable create) ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Timestamp": "={{ $now.toISO() }}",
                    "Workflow Name": "WF-01 Sales Invoicing",
                    "Event Type": "INVOICE_CREATED",
                    "Record Type": "Invoice",
                    "Record ID": "={{ $json.invoiceNumber }}",
                    "Action Taken": "=Invoice {{ $json.invoiceNumber }} created for {{ $json.customerName || $json['Customer Name'] }} - R {{ $json.total }}",
                    "Actor": "system",
                    "Result": "Success",
                    "Error Details": "",
                    "Metadata JSON": "={{ JSON.stringify({ customer: $json.customerName || $json['Customer Name'], amount: $json.total, currency: 'ZAR' }) }}",
                    "Created At": "={{ $now.format('yyyy-MM-dd') }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Audit Log",
        "type": "n8n-nodes-base.airtable",
        "position": [5340, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 29. Back to Loop (noOp - connects back to Loop Over Invoices) ──
    # This is implicit via the connection from Write Audit Log -> Loop Over Invoices.
    # No separate node is needed; the connection handles the loop-back.
    # However, we include a NoOp for clarity in the canvas.

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Back to Loop",
        "type": "n8n-nodes-base.noOp",
        "position": [5560, 500],
        "typeVersion": 1,
    })

    # ── 30. Build Summary (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const items = $input.all();\n"
                "const config = $('System Config').first().json;\n"
                "\n"
                "let totalInvoiced = 0;\n"
                "let invoiceCount = 0;\n"
                "let pendingApproval = 0;\n"
                "let sentCount = 0;\n"
                "const summaryLines = [];\n"
                "\n"
                "for (const item of items) {\n"
                "  const inv = item.json;\n"
                "  if (inv && inv.invoiceNumber) {\n"
                "    invoiceCount++;\n"
                "    totalInvoiced += inv.total || 0;\n"
                "    if (inv.Status === 'Pending Approval') {\n"
                "      pendingApproval++;\n"
                "    } else {\n"
                "      sentCount++;\n"
                "    }\n"
                "    summaryLines.push(`${inv.invoiceNumber} - ${inv.customerName || 'Unknown'} - R ${(inv.total || 0).toFixed(2)} [${inv.Status || 'Processed'}]`);\n"
                "  }\n"
                "}\n"
                "\n"
                "const summaryHtml = `<h2>Invoice Processing Summary</h2>\n"
                "<p><strong>Date:</strong> ${config.todayDate}</p>\n"
                "<p><strong>Total Invoices Processed:</strong> ${invoiceCount}</p>\n"
                "<p><strong>Sent:</strong> ${sentCount} | <strong>Pending Approval:</strong> ${pendingApproval}</p>\n"
                "<p><strong>Total Invoiced:</strong> R ${totalInvoiced.toFixed(2)}</p>\n"
                "<hr>\n"
                "<ul>${summaryLines.map(l => '<li>' + l + '</li>').join('')}</ul>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    summaryHtml: summaryHtml,\n"
                "    invoiceCount: invoiceCount,\n"
                "    totalInvoiced: totalInvoiced,\n"
                "    sentCount: sentCount,\n"
                "    pendingApproval: pendingApproval,\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Build Summary",
        "type": "n8n-nodes-base.code",
        "position": [5800, 600],
        "typeVersion": 2,
    })

    # ── 31. Error Trigger ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 1100],
        "typeVersion": 1,
    })

    # ── 32. Error Notification (gmail) ──

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=ERROR: Accounting WF-01 Sales & Invoicing - {{ $now.format('yyyy-MM-dd HH:mm') }}",
            "emailType": "html",
            "message": (
                "=<h2 style='color:#FF6D5A;'>Workflow Error: Sales & Invoicing (WF-01)</h2>"
                "<p><strong>Time:</strong> {{ $now.format('yyyy-MM-dd HH:mm:ss') }}</p>"
                "<p><strong>Error:</strong> {{ $json.execution?.error?.message || 'Unknown error' }}</p>"
                "<p><strong>Node:</strong> {{ $json.execution?.lastNodeExecuted || 'Unknown' }}</p>"
                "<p><strong>Execution ID:</strong> {{ $json.execution?.id || 'N/A' }}</p>"
                "<hr>"
                "<p>Please check the n8n execution log for details.</p>"
            ),
            "options": {
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [460, 1100],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_connections():
    """Build connections for the Sales & Invoicing workflow."""
    return {
        "Hourly Invoice Check": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Invoice Request Webhook": {
            "main": [[{"node": "Webhook Auth Check", "type": "main", "index": 0}]],
        },
        "Webhook Auth Check": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Read Draft Invoices", "type": "main", "index": 0}]],
        },
        "Read Draft Invoices": {
            "main": [[{"node": "Merge Sources", "type": "main", "index": 0}]],
        },
        "Merge Sources": {
            "main": [[{"node": "Has Items?", "type": "main", "index": 0}]],
        },
        "Has Items?": {
            "main": [
                [{"node": "Loop Over Invoices", "type": "main", "index": 0}],
                [{"node": "Build Summary", "type": "main", "index": 0}],
            ],
        },
        "Loop Over Invoices": {
            "main": [
                [{"node": "Build Summary", "type": "main", "index": 0}],
                [{"node": "Lookup Customer", "type": "main", "index": 0}],
            ],
        },
        "Lookup Customer": {
            "main": [[{"node": "Customer Exists?", "type": "main", "index": 0}]],
        },
        "Customer Exists?": {
            "main": [
                [{"node": "Merge Customer Data", "type": "main", "index": 0}],
                [{"node": "Create Customer", "type": "main", "index": 0}],
            ],
        },
        "Create Customer": {
            "main": [[{"node": "Merge Customer Data", "type": "main", "index": 0}]],
        },
        "Merge Customer Data": {
            "main": [[{"node": "Lookup Products", "type": "main", "index": 0}]],
        },
        "Lookup Products": {
            "main": [[{"node": "Calculate Tax", "type": "main", "index": 0}]],
        },
        "Calculate Tax": {
            "main": [[{"node": "Generate Invoice Number", "type": "main", "index": 0}]],
        },
        "Generate Invoice Number": {
            "main": [[{"node": "Check High Value", "type": "main", "index": 0}]],
        },
        "Check High Value": {
            "main": [
                [{"node": "Create Approval Task", "type": "main", "index": 0}],
                [{"node": "Create Invoice in Xero", "type": "main", "index": 0}],
            ],
        },
        "Create Approval Task": {
            "main": [[{"node": "Send Approval Email", "type": "main", "index": 0}]],
        },
        "Send Approval Email": {
            "main": [[{"node": "Update Status Pending", "type": "main", "index": 0}]],
        },
        "Update Status Pending": {
            "main": [[{"node": "Write Audit Log", "type": "main", "index": 0}]],
        },
        "Create Invoice in Xero": {
            "main": [[{"node": "Update Invoice Record", "type": "main", "index": 0}]],
        },
        "Update Invoice Record": {
            "main": [[{"node": "Build Invoice HTML", "type": "main", "index": 0}]],
        },
        "Build Invoice HTML": {
            "main": [[{"node": "Send Invoice Email", "type": "main", "index": 0}]],
        },
        "Send Invoice Email": {
            "main": [[{"node": "Check WhatsApp Pref", "type": "main", "index": 0}]],
        },
        "Check WhatsApp Pref": {
            "main": [
                [{"node": "Send Invoice WhatsApp", "type": "main", "index": 0}],
                [{"node": "Schedule Follow-up", "type": "main", "index": 0}],
            ],
        },
        "Send Invoice WhatsApp": {
            "main": [[{"node": "Schedule Follow-up", "type": "main", "index": 0}]],
        },
        "Schedule Follow-up": {
            "main": [[{"node": "Update Reminder Schedule", "type": "main", "index": 0}]],
        },
        "Update Reminder Schedule": {
            "main": [[{"node": "Write Audit Log", "type": "main", "index": 0}]],
        },
        "Write Audit Log": {
            "main": [[{"node": "Back to Loop", "type": "main", "index": 0}]],
        },
        "Back to Loop": {
            "main": [[{"node": "Loop Over Invoices", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "wf01": {
        "name": "Accounting Dept - Sales & Invoicing (WF-01)",
        "build_nodes": lambda: build_nodes(),
        "build_connections": lambda: build_connections(),
    },
}


def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
    if wf_id not in WORKFLOW_DEFS:
        raise ValueError(f"Unknown workflow: {wf_id}. Valid: {', '.join(WORKFLOW_DEFS.keys())}")

    wf_def = WORKFLOW_DEFS[wf_id]

    nodes = wf_def["build_nodes"]()
    connections = wf_def["build_connections"]()

    return {
        "name": wf_def["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    filenames = {
        "wf01": "wf01_sales_invoicing.json",
    }

    output_dir = Path(__file__).parent.parent / "workflows" / "accounting-dept"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filenames[wf_id]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(wf_id, workflow):
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

def main():
    global AIRTABLE_BASE_ID

    parser = argparse.ArgumentParser(description="WF-01 Sales & Invoicing Builder")
    parser.add_argument("action", nargs="?", default="build", choices=["build", "deploy", "activate"])
    parser.add_argument("target", nargs="?", default="all")
    parser.add_argument("--client", help="Client ID from config.json (enables multi-tenant isolation)")
    parsed = parser.parse_args()

    action = parsed.action
    target = parsed.target

    # Multi-client override: load client-specific Airtable base
    if parsed.client:
        from client_config import get_client_config
        client_cfg = get_client_config(parsed.client)
        AIRTABLE_BASE_ID = client_cfg.get("airtable_base_id", AIRTABLE_BASE_ID)
        print(f"[Multi-tenant] Deploying for client: {client_cfg['name']}")
        print(f"[Multi-tenant] Airtable base: {AIRTABLE_BASE_ID}")

    print("=" * 60)
    print("ACCOUNTING DEPARTMENT - WF-01 SALES & INVOICING")
    print("=" * 60)

    # Determine which workflows to build
    valid_wfs = list(WORKFLOW_DEFS.keys())
    if target == "all":
        workflow_ids = valid_wfs
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Check Airtable config
    if "REPLACE" in AIRTABLE_BASE_ID:
        print()
        print("WARNING: Airtable IDs not configured!")
        print("  Set these env vars in .env:")
        print("  - ACCOUNTING_AIRTABLE_BASE_ID")
        print("  - ACCOUNTING_TABLE_CUSTOMERS")
        print("  - ACCOUNTING_TABLE_PRODUCTS_SERVICES")
        print("  - ACCOUNTING_TABLE_INVOICES")
        print("  - ACCOUNTING_TABLE_TASKS")
        print("  - ACCOUNTING_TABLE_AUDIT_LOG")
        print("  - ACCOUNTING_TABLE_SYSTEM_CONFIG")
        print()
        if action in ("deploy", "activate"):
            print("Cannot deploy with placeholder IDs. Aborting.")
            sys.exit(1)
        print("Continuing build with placeholder IDs (for preview only)...")
        print()

    # Check Xero credential config
    if "REPLACE" in CRED_XERO["id"]:
        print("WARNING: Xero credential ID not configured!")
        print("  Set ACCOUNTING_XERO_CRED_ID in .env")
        print()

    # Build workflows
    workflows = {}
    for wf_id in workflow_ids:
        print(f"\nBuilding {wf_id}...")
        workflow = build_workflow(wf_id)
        output_path = save_workflow(wf_id, workflow)
        workflows[wf_id] = workflow
        print_workflow_stats(wf_id, workflow)
        print(f"  Saved to: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # Deploy to n8n
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

            deployed_ids = {}

            for wf_id, workflow in workflows.items():
                print(f"\nDeploying {wf_id}...")

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
                    # Update existing
                    update_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.update_workflow(existing["id"], update_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Updated: {result.get('name')} (ID: {result.get('id')})")
                else:
                    # Create new — only send fields the n8n API accepts
                    create_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.create_workflow(create_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Created: {result.get('name')} (ID: {result.get('id')})")

                if action == "activate" and deployed_ids.get(wf_id):
                    print(f"  Activating {wf_id}...")
                    client.activate_workflow(deployed_ids[wf_id])
                    print(f"  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Workflows:")
    for wf_id in workflow_ids:
        wf_label = WORKFLOW_DEFS[wf_id]["name"]
        print(f"  {wf_id}: {wf_label}")

    print()
    print("Next steps:")
    print("  1. Open the workflow in n8n UI to verify node connections")
    print("  2. Verify credential bindings (Airtable, Gmail, Xero, WhatsApp)")
    print("  3. Set up Airtable tables (Customers, Products/Services, Invoices, Tasks, Audit Log)")
    print("  4. Configure Xero OAuth2 credentials in n8n")
    print("  5. Test with Manual Trigger -> check invoice creation flow")
    print("  6. Test webhook endpoint: POST /accounting/create-invoice")
    print("  7. Once verified, activate the hourly schedule trigger")


if __name__ == "__main__":
    main()
