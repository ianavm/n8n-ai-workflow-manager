"""
Accounting Department - Supplier Bills AP (WF-04) Builder & Deployer

Handles:
- Email inbox monitoring for supplier invoices
- AI-powered document extraction (OCR via OpenRouter)
- Supplier validation and creation
- Expense categorization
- Approval routing (auto-approve < R10k, manual > R10k)
- Bill creation in QuickBooks
- Payment scheduling
- Audit logging

Usage:
    python tools/deploy_accounting_wf04.py build
    python tools/deploy_accounting_wf04.py deploy
    python tools/deploy_accounting_wf04.py activate
"""

import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# ── Credential Constants ──────────────────────────────────────

CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_QUICKBOOKS = {"id": os.getenv("ACCOUNTING_QBO_CRED_ID", "REPLACE"), "name": "QuickBooks OAuth2 AVM"}

QBO_COMPANY_ID = os.getenv("ACCOUNTING_QBO_COMPANY_ID", "REPLACE_WITH_TENANT_ID")

# ── Airtable IDs ──────────────────────────────────────────────

AIRTABLE_BASE_ID = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
TABLE_SUPPLIERS = os.getenv("ACCOUNTING_TABLE_SUPPLIERS", "REPLACE_WITH_TABLE_ID")
TABLE_SUPPLIER_BILLS = os.getenv("ACCOUNTING_TABLE_SUPPLIER_BILLS", "REPLACE_WITH_TABLE_ID")
TABLE_TASKS = os.getenv("ACCOUNTING_TABLE_TASKS", "REPLACE_WITH_TABLE_ID")
TABLE_AUDIT_LOG = os.getenv("ACCOUNTING_TABLE_AUDIT_LOG", "REPLACE_WITH_TABLE_ID")

# Validate required environment variables
_required_vars = {
    "ACCOUNTING_QBO_COMPANY_ID": QBO_COMPANY_ID,
    "ACCOUNTING_AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
    "ACCOUNTING_TABLE_SUPPLIERS": TABLE_SUPPLIERS,
    "ACCOUNTING_TABLE_SUPPLIER_BILLS": TABLE_SUPPLIER_BILLS,
    "ACCOUNTING_TABLE_TASKS": TABLE_TASKS,
    "ACCOUNTING_TABLE_AUDIT_LOG": TABLE_AUDIT_LOG,
}
_missing = [k for k, v in _required_vars.items() if isinstance(v, str) and "REPLACE_" in v.upper()]
if _missing:
    print(f"ERROR: These environment variables must be set before deploying:")
    for var in _missing:
        print(f"  - {var}")
    print(f"\nCopy .env.template to .env and fill in the values.")
    sys.exit(1)


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ── AI Prompts ────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are an accounts payable document processor. Extract the following fields from this supplier invoice/bill email.

Return JSON only, no markdown:
{
  "supplier_name": "Company name of the supplier",
  "invoice_number": "Supplier's invoice number",
  "bill_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD (estimate if not shown: bill_date + 30 days)",
  "subtotal": 0.00,
  "vat_amount": 0.00,
  "total_amount": 0.00,
  "line_items": [{"description": "", "amount": 0.00}],
  "supplier_email": "sender email if available",
  "currency": "ZAR",
  "confidence": 0.0-1.0
}

Rules:
- If VAT is 15% of subtotal, extract separately
- If only total is shown, estimate subtotal = total / 1.15 and VAT = total - subtotal
- Set confidence based on how clearly the data was extractable
- If a field is missing, use null"""

CATEGORIZATION_PROMPT = """Categorize this supplier expense into ONE of these categories:
- Software
- Hosting
- Marketing
- Office
- Professional Services
- Travel
- Equipment
- Other

Return JSON only: {{"category": "Category Name", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

Supplier: {supplier_name}
Description: {description}
Amount: R {amount}"""


# ══════════════════════════════════════════════════════════════
# WF-04: SUPPLIER BILLS AP (30 NODES)
# ══════════════════════════════════════════════════════════════

def build_nodes():
    """Build all 30 nodes for WF-04: Supplier Bills AP."""

    nodes = []

    # ── 1. Hourly Email Check (scheduleTrigger) ───────────────
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {"field": "cronExpression", "expression": "0 8-17 * * 1-5"}
                ]
            }
        },
        "id": uid(),
        "name": "Hourly Email Check",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 500],
        "typeVersion": 1.2,
    })

    # ── 2. Manual Trigger ─────────────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 700],
        "typeVersion": 1,
    })

    # ── 3. System Config (set) ────────────────────────────────
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "todayDate",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "companyName",
                        "value": "AnyVision Media",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "aiModel",
                        "value": "anthropic/claude-sonnet-4-20250514",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "autoApproveThreshold",
                        "value": "10000",
                        "type": "number",
                    },
                    {
                        "id": uid(),
                        "name": "qboCompanyId",
                        "value": QBO_COMPANY_ID,
                        "type": "string",
                    },
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 500],
        "typeVersion": 3.4,
    })

    # ── 4. Read Accounts Inbox (gmail) ────────────────────────
    nodes.append({
        "parameters": {
            "operation": "getAll",
            "returnAll": False,
            "limit": 20,
            "filters": {
                "q": "is:unread has:attachment label:Bills",
                "readStatus": "unread",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Read Accounts Inbox",
        "type": "n8n-nodes-base.gmail",
        "position": [680, 500],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "alwaysOutputData": True,
    })

    # ── 5. Has Bills? (if) ────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $input.all().length }}",
                        "rightValue": 0,
                        "operator": {
                            "type": "number",
                            "operation": "gt",
                        },
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Has Bills?",
        "type": "n8n-nodes-base.if",
        "position": [920, 500],
        "typeVersion": 2,
    })

    # ── 6. Loop Over Bills (splitInBatches) ───────────────────
    nodes.append({
        "parameters": {
            "batchSize": 1,
            "options": {},
        },
        "id": uid(),
        "name": "Loop Over Bills",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1160, 400],
        "typeVersion": 3,
    })

    # ── 7. Extract Email Data (code) ──────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const email = $input.first().json;\n"
                "\n"
                "const sender = email.from || email.sender || '';\n"
                "const subject = email.subject || '';\n"
                "const body = (email.text || email.snippet || '').substring(0, 3000);\n"
                "const attachments = email.attachments || [];\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    emailId: email.id,\n"
                "    sender: sender,\n"
                "    subject: subject,\n"
                "    bodyText: body,\n"
                "    hasAttachment: attachments.length > 0,\n"
                "    attachmentCount: attachments.length,\n"
                "    receivedAt: email.date || new Date().toISOString(),\n"
                "    extractionInput: `From: ${sender}\\nSubject: ${subject}\\n\\n${body}`,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Extract Email Data",
        "type": "n8n-nodes-base.code",
        "position": [1400, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── 8. AI Document Extraction (httpRequest - OpenRouter) ──
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                '={\n'
                '  "model": "{{ $("System Config").item.json.aiModel }}",\n'
                '  "messages": [\n'
                '    {"role": "system", "content": '
                + json.dumps(EXTRACTION_PROMPT)
                + '},\n'
                '    {"role": "user", "content": {{ JSON.stringify($json.extractionInput) }}}\n'
                '  ],\n'
                '  "temperature": 0.1,\n'
                '  "max_tokens": 2000\n'
                '}'
            ),
            "options": {"timeout": 60000},
        },
        "id": uid(),
        "name": "AI Document Extraction",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1640, 400],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 5000,
    })

    # ── 9. Parse Extraction (code) ────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const emailData = $('Extract Email Data').first().json;\n"
                "\n"
                "let extracted;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  extracted = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch(e) {\n"
                "  extracted = {\n"
                "    supplier_name: emailData.sender.split('<')[0].trim() || 'Unknown',\n"
                "    invoice_number: 'UNKNOWN',\n"
                "    bill_date: new Date().toISOString().split('T')[0],\n"
                "    due_date: null,\n"
                "    subtotal: 0,\n"
                "    vat_amount: 0,\n"
                "    total_amount: 0,\n"
                "    confidence: 0,\n"
                "  };\n"
                "}\n"
                "\n"
                "// Calculate due date if missing\n"
                "if (!extracted.due_date && extracted.bill_date) {\n"
                "  const billDate = new Date(extracted.bill_date);\n"
                "  billDate.setDate(billDate.getDate() + 30);\n"
                "  extracted.due_date = billDate.toISOString().split('T')[0];\n"
                "}\n"
                "\n"
                "// Validate/recalculate amounts\n"
                "if (extracted.total_amount && !extracted.subtotal) {\n"
                "  extracted.subtotal = Math.round(extracted.total_amount / 1.15 * 100) / 100;\n"
                "  extracted.vat_amount = Math.round((extracted.total_amount - extracted.subtotal) * 100) / 100;\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...emailData,\n"
                "    ...extracted,\n"
                "    billId: `BILL-${Date.now()}`,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Parse Extraction",
        "type": "n8n-nodes-base.code",
        "position": [1880, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── 10. Lookup Supplier (airtable search) ─────────────────
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIERS},
            "filterByFormula": "OR({Supplier ID} = '{{ $json.supplier_name }}', {Email} = '{{ $json.supplier_email }}')",
        },
        "id": uid(),
        "name": "Lookup Supplier",
        "type": "n8n-nodes-base.airtable",
        "position": [2120, 400],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 11. Supplier Exists? (if) ─────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $input.all().length }}",
                        "rightValue": 0,
                        "operator": {
                            "type": "number",
                            "operation": "gt",
                        },
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Supplier Exists?",
        "type": "n8n-nodes-base.if",
        "position": [2360, 400],
        "typeVersion": 2,
    })

    # ── 12. Create Supplier (airtable create) ─────────────────
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIERS},
            "columns": {
                "value": {
                    "Supplier ID": "={{ $('Parse Extraction').first().json.supplier_name }}",
                    "Email": "={{ $('Parse Extraction').first().json.supplier_email || '' }}",
                    "Payment Terms": "30 days",
                    "Active": True,
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [
                    {"id": "Supplier ID", "type": "string", "display": True, "displayName": "Supplier ID"},
                    {"id": "Email", "type": "string", "display": True, "displayName": "Email"},
                    {"id": "Payment Terms", "type": "string", "display": True, "displayName": "Payment Terms"},
                    {"id": "Active", "type": "boolean", "display": True, "displayName": "Active"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Supplier",
        "type": "n8n-nodes-base.airtable",
        "position": [2600, 560],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 13. Merge Supplier Data (code) ────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const extraction = $('Parse Extraction').first().json;\n"
                "const supplierInput = $input.first().json;\n"
                "\n"
                "// Determine if supplier came from lookup or create\n"
                "const supplierId = supplierInput.id || supplierInput['Supplier ID'] || `SUP-${Date.now()}`;\n"
                "const supplierName = supplierInput['Supplier Name'] || extraction.supplier_name;\n"
                "const supplierPaymentTerms = supplierInput['Default Payment Terms'] || '30 days';\n"
                "const isKnownSupplier = !!supplierInput['Supplier Name'];\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...extraction,\n"
                "    supplierId: supplierId,\n"
                "    supplierName: supplierName,\n"
                "    supplierPaymentTerms: supplierPaymentTerms,\n"
                "    isKnownSupplier: isKnownSupplier,\n"
                "    supplierAirtableId: supplierInput.id || null,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Merge Supplier Data",
        "type": "n8n-nodes-base.code",
        "position": [2840, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── 14. AI Categorize Expense (httpRequest - OpenRouter) ──
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                '={\n'
                '  "model": "{{ $("System Config").item.json.aiModel }}",\n'
                '  "messages": [\n'
                '    {"role": "system", "content": "You categorize supplier expenses. Return JSON only."},\n'
                '    {"role": "user", "content": "Categorize this supplier expense into ONE of these categories:\\n'
                '- Software\\n- Hosting\\n- Marketing\\n- Office\\n- Professional Services\\n'
                '- Travel\\n- Equipment\\n- Other\\n\\n'
                'Return JSON only: {\\\"category\\\": \\\"Category Name\\\", \\\"confidence\\\": 0.0-1.0, \\\"reasoning\\\": \\\"brief explanation\\\"}\\n\\n'
                'Supplier: {{ $json.supplierName }}\\n'
                'Description: {{ $json.subject || \\\"Supplier invoice\\\" }}\\n'
                'Amount: R {{ $json.total_amount }}"}\n'
                '  ],\n'
                '  "temperature": 0.1,\n'
                '  "max_tokens": 500\n'
                '}'
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Categorize Expense",
        "type": "n8n-nodes-base.httpRequest",
        "position": [3080, 400],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # ── 15. Parse Category (code) ─────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const prevData = $('Merge Supplier Data').first().json;\n"
                "\n"
                "let category = 'Other';\n"
                "let categoryConfidence = 0;\n"
                "let categoryReasoning = '';\n"
                "\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  const parsed = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "  category = parsed.category || 'Other';\n"
                "  categoryConfidence = parsed.confidence || 0;\n"
                "  categoryReasoning = parsed.reasoning || '';\n"
                "} catch(e) {\n"
                "  category = 'Other';\n"
                "  categoryConfidence = 0;\n"
                "  categoryReasoning = 'AI parsing failed, defaulting to Other';\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...prevData,\n"
                "    expenseCategory: category,\n"
                "    categoryConfidence: categoryConfidence,\n"
                "    categoryReasoning: categoryReasoning,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Parse Category",
        "type": "n8n-nodes-base.code",
        "position": [3320, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── 16. Create Bill Record (airtable create) ──────────────
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIER_BILLS},
            "columns": {
                "value": {
                    "Bill ID": "={{ $json.billId }}",
                    "Supplier Name": "={{ $json.supplierName }}",
                    "Bill Number": "={{ $json.invoice_number }}",
                    "Bill Date": "={{ $json.bill_date }}",
                    "Due Date": "={{ $json.due_date }}",
                    "Subtotal": "={{ $json.subtotal }}",
                    "VAT Amount": "={{ $json.vat_amount }}",
                    "Total Amount": "={{ $json.total_amount }}",
                    "Category": "={{ $json.expenseCategory }}",
                    "Approval Status": "Pending",
                    "Payment Status": "Unpaid",
                    "OCR Raw JSON": "={{ JSON.stringify({ emailId: $json.emailId, confidence: $json.confidence }) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [
                    {"id": "Bill ID", "type": "string", "display": True, "displayName": "Bill ID"},
                    {"id": "Supplier Name", "type": "string", "display": True, "displayName": "Supplier Name"},
                    {"id": "Bill Number", "type": "string", "display": True, "displayName": "Bill Number"},
                    {"id": "Bill Date", "type": "string", "display": True, "displayName": "Bill Date"},
                    {"id": "Due Date", "type": "string", "display": True, "displayName": "Due Date"},
                    {"id": "Subtotal", "type": "number", "display": True, "displayName": "Subtotal"},
                    {"id": "VAT Amount", "type": "number", "display": True, "displayName": "VAT Amount"},
                    {"id": "Total Amount", "type": "number", "display": True, "displayName": "Total Amount"},
                    {"id": "Category", "type": "string", "display": True, "displayName": "Category"},
                    {"id": "Approval Status", "type": "string", "display": True, "displayName": "Approval Status"},
                    {"id": "Payment Status", "type": "string", "display": True, "displayName": "Payment Status"},
                    {"id": "OCR Raw JSON", "type": "string", "display": True, "displayName": "OCR Raw JSON"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Bill Record",
        "type": "n8n-nodes-base.airtable",
        "position": [3560, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 17. Check Auto Approve (if) ──────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $('Parse Category').first().json.total_amount }}",
                        "rightValue": "={{ $('System Config').first().json.autoApproveThreshold }}",
                        "operator": {
                            "type": "number",
                            "operation": "lt",
                        },
                    },
                    {
                        "id": uid(),
                        "leftValue": "={{ $('Parse Category').first().json.isKnownSupplier }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                        },
                    },
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Check Auto Approve",
        "type": "n8n-nodes-base.if",
        "position": [3800, 400],
        "typeVersion": 2,
    })

    # ── 18. Auto Approve Bill (airtable update) ──────────────
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIER_BILLS},
            "columns": {
                "value": {
                    "Bill ID": "={{ $('Parse Category').first().json.billId }}",
                    "Approval Status": "Auto Approved",
                    "Approved At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                    "Approver": "system (auto-approve < R10k)",
                },
                "schema": [
                    {"id": "Bill ID", "type": "string", "display": True, "displayName": "Bill ID"},
                    {"id": "Approval Status", "type": "string", "display": True, "displayName": "Approval Status"},
                    {"id": "Approved At", "type": "string", "display": True, "displayName": "Approved At"},
                    {"id": "Approver", "type": "string", "display": True, "displayName": "Approver"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Bill ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Auto Approve Bill",
        "type": "n8n-nodes-base.airtable",
        "position": [4040, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 19. Create Approval Task (airtable create) ───────────
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "columns": {
                "value": {
                    "Task ID": "={{ 'TASK-' + Date.now() }}",
                    "Type": "Bill Approval",
                    "Description": "=Bill {{ $('Parse Category').first().json.invoice_number }} from {{ $('Parse Category').first().json.supplierName }} - R{{ $('Parse Category').first().json.total_amount }} requires manual approval (amount >= R10,000).",
                    "Status": "Open",
                    "Priority": "High",
                    "Owner": "ian@anyvisionmedia.com",
                    "Related Record ID": "={{ $('Parse Category').first().json.billId }}",
                    "Related Table": "Supplier Bills",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [
                    {"id": "Task ID", "type": "string", "display": True, "displayName": "Task ID"},
                    {"id": "Type", "type": "string", "display": True, "displayName": "Type"},
                    {"id": "Description", "type": "string", "display": True, "displayName": "Description"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Priority", "type": "string", "display": True, "displayName": "Priority"},
                    {"id": "Owner", "type": "string", "display": True, "displayName": "Owner"},
                    {"id": "Related Record ID", "type": "string", "display": True, "displayName": "Related Record ID"},
                    {"id": "Related Table", "type": "string", "display": True, "displayName": "Related Table"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Approval Task",
        "type": "n8n-nodes-base.airtable",
        "position": [4040, 560],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 20. Send Approval Email (gmail) ───────────────────────
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=APPROVAL REQUIRED: Bill from {{ $('Parse Category').first().json.supplierName }} - R{{ $('Parse Category').first().json.total_amount }}",
            "emailType": "html",
            "message": (
                "=<h2>Bill Approval Required</h2>\n"
                "<table border='1' cellpadding='8' cellspacing='0' style='border-collapse: collapse;'>\n"
                "<tr><td><strong>Supplier</strong></td><td>{{ $('Parse Category').first().json.supplierName }}</td></tr>\n"
                "<tr><td><strong>Invoice #</strong></td><td>{{ $('Parse Category').first().json.invoice_number }}</td></tr>\n"
                "<tr><td><strong>Bill Date</strong></td><td>{{ $('Parse Category').first().json.bill_date }}</td></tr>\n"
                "<tr><td><strong>Due Date</strong></td><td>{{ $('Parse Category').first().json.due_date }}</td></tr>\n"
                "<tr><td><strong>Subtotal</strong></td><td>R {{ $('Parse Category').first().json.subtotal }}</td></tr>\n"
                "<tr><td><strong>VAT</strong></td><td>R {{ $('Parse Category').first().json.vat_amount }}</td></tr>\n"
                "<tr><td><strong>Total</strong></td><td>R {{ $('Parse Category').first().json.total_amount }}</td></tr>\n"
                "<tr><td><strong>Category</strong></td><td>{{ $('Parse Category').first().json.expenseCategory }}</td></tr>\n"
                "<tr><td><strong>AI Confidence</strong></td><td>{{ $('Parse Category').first().json.confidence }}</td></tr>\n"
                "</table>\n"
                "<br>\n"
                "<p>This bill requires manual approval because the amount exceeds R10,000.</p>\n"
                "<p>Please review and respond to approve or reject this bill.</p>"
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Send Approval Email",
        "type": "n8n-nodes-base.gmail",
        "position": [4280, 560],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── 21. Update Bill Awaiting (airtable update) ────────────
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIER_BILLS},
            "columns": {
                "value": {
                    "Bill ID": "={{ $('Parse Category').first().json.billId }}",
                    "Approval Status": "Awaiting Approval",
                },
                "schema": [
                    {"id": "Bill ID", "type": "string", "display": True, "displayName": "Bill ID"},
                    {"id": "Approval Status", "type": "string", "display": True, "displayName": "Approval Status"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Bill ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Bill Awaiting",
        "type": "n8n-nodes-base.airtable",
        "position": [4520, 560],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 22. Create Bill in QuickBooks (httpRequest) ─────────────────
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://quickbooks.api.intuit.com/v3/company/  # TODO: Update to QuickBooks endpoint. Was: api.xero.com/api.xro/2.0/Invoices",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "quickBooksOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "qbo-company-id", "value": "={{ $('System Config').first().json.qboCompanyId || '' }}"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                '={\n'
                '  "Type": "ACCPAY",\n'
                '  "Contact": {"Name": "{{ $("Parse Category").item.json.supplierName }}"},\n'
                '  "Date": "{{ $("Parse Category").item.json.bill_date }}",\n'
                '  "DueDate": "{{ $("Parse Category").item.json.due_date }}",\n'
                '  "InvoiceNumber": "{{ $("Parse Category").item.json.invoice_number }}",\n'
                '  "CurrencyCode": "ZAR",\n'
                '  "Status": "AUTHORISED",\n'
                '  "LineItems": [{"Description": "{{ $("Parse Category").item.json.supplierName }} - {{ $("Parse Category").item.json.invoice_number }}", "Quantity": 1, "UnitAmount": {{ $("Parse Category").item.json.subtotal }}, "TaxAmount": {{ $("Parse Category").item.json.vat_amount }}, "AccountCode": "400"}]\n'
                '}'
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Create Bill in QuickBooks",
        "type": "n8n-nodes-base.httpRequest",
        "position": [4280, 300],
        "typeVersion": 4.2,
        "credentials": {"quickBooksOAuth2Api": CRED_QUICKBOOKS},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 5000,
    })

    # ── 23. Update Bill QuickBooks ID (airtable update) ────────────
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIER_BILLS},
            "columns": {
                "value": {
                    "Bill ID": "={{ $('Parse Category').first().json.billId }}",
                    "QuickBooks Bill ID": "={{ $json.Invoices ? $json.Invoices[0].InvoiceID : ($json.InvoiceID || '') }}",
                    "QuickBooks Status": "={{ $json.Invoices ? $json.Invoices[0].Status : ($json.Status || 'ERROR') }}",
                    "Synced to QuickBooks At": "={{ $now.toISO() }}",
                },
                "schema": [
                    {"id": "Bill ID", "type": "string", "display": True, "displayName": "Bill ID"},
                    {"id": "QuickBooks Bill ID", "type": "string", "display": True, "displayName": "QuickBooks Bill ID"},
                    {"id": "QuickBooks Status", "type": "string", "display": True, "displayName": "QuickBooks Status"},
                    {"id": "Synced to QuickBooks At", "type": "string", "display": True, "displayName": "Synced to QuickBooks At"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Bill ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Bill QuickBooks ID",
        "type": "n8n-nodes-base.airtable",
        "position": [4520, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 24. Schedule Payment (code) ───────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const billData = $('Parse Extraction').first().json;\n"
                "const supplierData = $('Merge Supplier Data').first().json;\n"
                "const data = $input.first().json;\n"
                "const dueDate = billData.due_date;\n"
                "const paymentTerms = supplierData.paymentTerms || supplierData['Payment Terms'] || '30';\n"
                "const supplierTerms = supplierData.supplierPaymentTerms || paymentTerms + ' days';\n"
                "\n"
                "let paymentDate;\n"
                "const dueDateParsed = new Date(dueDate || data['Due Date']);\n"
                "\n"
                "if (isNaN(dueDateParsed.getTime())) {\n"
                "  const today = new Date();\n"
                "  today.setDate(today.getDate() + 30);\n"
                "  paymentDate = today.toISOString().split('T')[0];\n"
                "} else {\n"
                "  paymentDate = dueDateParsed.toISOString().split('T')[0];\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...data,\n"
                "    scheduledPaymentDate: paymentDate,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Schedule Payment",
        "type": "n8n-nodes-base.code",
        "position": [4760, 300],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── 25. Update Payment Schedule (airtable update) ─────────
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIER_BILLS},
            "columns": {
                "value": {
                    "Bill ID": "={{ $('Parse Category').first().json.billId }}",
                    "Payment Status": "Scheduled",
                    "Scheduled Payment Date": "={{ $json.scheduledPaymentDate }}",
                },
                "schema": [
                    {"id": "Bill ID", "type": "string", "display": True, "displayName": "Bill ID"},
                    {"id": "Payment Status", "type": "string", "display": True, "displayName": "Payment Status"},
                    {"id": "Scheduled Payment Date", "type": "string", "display": True, "displayName": "Scheduled Payment Date"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Bill ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Payment Schedule",
        "type": "n8n-nodes-base.airtable",
        "position": [5000, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 26. Mark Email Processed (gmail - remove UNREAD label) ──
    nodes.append({
        "parameters": {
            "resource": "message",
            "operation": "removeLabels",
            "messageId": "={{ $('Extract Email Data').first().json.emailId }}",
            "labelIds": ["UNREAD"],
            "options": {},
        },
        "id": uid(),
        "name": "Mark Email Processed",
        "type": "n8n-nodes-base.gmail",
        "position": [5240, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # ── 27. Write Audit Log (airtable create) ─────────────────
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "columns": {
                "value": {
                    "Timestamp": "={{ $now.toISO() }}",
                    "Workflow Name": "WF-04 Supplier Bills AP",
                    "Event Type": "BILL_CREATED",
                    "Record Type": "Supplier Bill",
                    "Record ID": "={{ $('Parse Category').first().json.billId }}",
                    "Action Taken": "=Bill {{ $('Parse Category').first().json.invoice_number }} from {{ $('Parse Category').first().json.supplierName }} - R{{ $('Parse Category').first().json.total_amount }}",
                    "Actor": "system",
                    "Result": "Success",
                    "Error Details": "",
                    "Metadata JSON": "={{ JSON.stringify({ supplier: $('Parse Category').first().json.supplierName, amount: $('Parse Category').first().json.total_amount, category: $('Parse Category').first().json.expenseCategory, confidence: $('Parse Category').first().json.confidence }) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [
                    {"id": "Timestamp", "type": "string", "display": True, "displayName": "Timestamp"},
                    {"id": "Workflow Name", "type": "string", "display": True, "displayName": "Workflow Name"},
                    {"id": "Event Type", "type": "string", "display": True, "displayName": "Event Type"},
                    {"id": "Record Type", "type": "string", "display": True, "displayName": "Record Type"},
                    {"id": "Record ID", "type": "string", "display": True, "displayName": "Record ID"},
                    {"id": "Action Taken", "type": "string", "display": True, "displayName": "Action Taken"},
                    {"id": "Actor", "type": "string", "display": True, "displayName": "Actor"},
                    {"id": "Result", "type": "string", "display": True, "displayName": "Result"},
                    {"id": "Error Details", "type": "string", "display": True, "displayName": "Error Details"},
                    {"id": "Metadata JSON", "type": "string", "display": True, "displayName": "Metadata JSON"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Audit Log",
        "type": "n8n-nodes-base.airtable",
        "position": [5480, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 28. Build Summary (code) ──────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const items = $input.all();\n"
                "\n"
                "let totalBills = 0;\n"
                "let totalAmount = 0;\n"
                "let autoApproved = 0;\n"
                "let pendingApproval = 0;\n"
                "let suppliers = new Set();\n"
                "let categories = {};\n"
                "\n"
                "for (const item of items) {\n"
                "  const data = item.json;\n"
                "  if (data.billId || data['Bill ID']) {\n"
                "    totalBills++;\n"
                "    totalAmount += parseFloat(data.total_amount || data['Total Amount'] || 0);\n"
                "    suppliers.add(data.supplierName || data['Supplier Name'] || 'Unknown');\n"
                "    const cat = data.expenseCategory || data['Expense Category'] || 'Other';\n"
                "    categories[cat] = (categories[cat] || 0) + 1;\n"
                "    if (data.approvalStatus === 'Auto Approved' || data['Approval Status'] === 'Auto Approved') {\n"
                "      autoApproved++;\n"
                "    } else {\n"
                "      pendingApproval++;\n"
                "    }\n"
                "  }\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    summary: {\n"
                "      totalBills: totalBills,\n"
                "      totalAmount: Math.round(totalAmount * 100) / 100,\n"
                "      autoApproved: autoApproved,\n"
                "      pendingApproval: pendingApproval,\n"
                "      uniqueSuppliers: suppliers.size,\n"
                "      categories: categories,\n"
                "      processedAt: new Date().toISOString(),\n"
                "    }\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Summary",
        "type": "n8n-nodes-base.code",
        "position": [920, 700],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── 29. Error Trigger ─────────────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 1000],
        "typeVersion": 1,
    })

    # ── 30. Error Notification (gmail) ────────────────────────
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=ACCOUNTING ERROR - WF-04 Supplier Bills: {{ $json.execution.error.message }}",
            "message": (
                "=<h2>Accounting Department Error - WF-04 Supplier Bills AP</h2>\n"
                "<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n"
                "<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n"
                "<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n"
                "<p><strong>Timestamp:</strong> {{ $now.toISO() }}</p>\n"
                '<p><a href="{{ $json.execution.url }}">View Execution</a></p>\n'
                "<hr>\n"
                "<p>Please investigate and resolve this error. Supplier bill processing may be interrupted.</p>"
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 1000],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_connections():
    """Build connections for WF-04: Supplier Bills AP."""
    return {
        "Hourly Email Check": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]]
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]]
        },
        "System Config": {
            "main": [[{"node": "Read Accounts Inbox", "type": "main", "index": 0}]]
        },
        "Read Accounts Inbox": {
            "main": [[{"node": "Has Bills?", "type": "main", "index": 0}]]
        },
        "Has Bills?": {
            "main": [
                [{"node": "Loop Over Bills", "type": "main", "index": 0}],
                [{"node": "Build Summary", "type": "main", "index": 0}],
            ]
        },
        "Loop Over Bills": {
            "main": [
                [{"node": "Build Summary", "type": "main", "index": 0}],
                [{"node": "Extract Email Data", "type": "main", "index": 0}],
            ]
        },
        "Extract Email Data": {
            "main": [[{"node": "AI Document Extraction", "type": "main", "index": 0}]]
        },
        "AI Document Extraction": {
            "main": [[{"node": "Parse Extraction", "type": "main", "index": 0}]]
        },
        "Parse Extraction": {
            "main": [[{"node": "Lookup Supplier", "type": "main", "index": 0}]]
        },
        "Lookup Supplier": {
            "main": [[{"node": "Supplier Exists?", "type": "main", "index": 0}]]
        },
        "Supplier Exists?": {
            "main": [
                [{"node": "Merge Supplier Data", "type": "main", "index": 0}],
                [{"node": "Create Supplier", "type": "main", "index": 0}],
            ]
        },
        "Create Supplier": {
            "main": [[{"node": "Merge Supplier Data", "type": "main", "index": 0}]]
        },
        "Merge Supplier Data": {
            "main": [[{"node": "AI Categorize Expense", "type": "main", "index": 0}]]
        },
        "AI Categorize Expense": {
            "main": [[{"node": "Parse Category", "type": "main", "index": 0}]]
        },
        "Parse Category": {
            "main": [[{"node": "Create Bill Record", "type": "main", "index": 0}]]
        },
        "Create Bill Record": {
            "main": [[{"node": "Check Auto Approve", "type": "main", "index": 0}]]
        },
        "Check Auto Approve": {
            "main": [
                [{"node": "Auto Approve Bill", "type": "main", "index": 0}],
                [{"node": "Create Approval Task", "type": "main", "index": 0}],
            ]
        },
        "Auto Approve Bill": {
            "main": [[{"node": "Create Bill in QuickBooks", "type": "main", "index": 0}]]
        },
        "Create Approval Task": {
            "main": [[{"node": "Send Approval Email", "type": "main", "index": 0}]]
        },
        "Send Approval Email": {
            "main": [[{"node": "Update Bill Awaiting", "type": "main", "index": 0}]]
        },
        "Update Bill Awaiting": {
            "main": [[{"node": "Mark Email Processed", "type": "main", "index": 0}]]
        },
        "Create Bill in QuickBooks": {
            "main": [[{"node": "Update Bill QuickBooks ID", "type": "main", "index": 0}]]
        },
        "Update Bill QuickBooks ID": {
            "main": [[{"node": "Schedule Payment", "type": "main", "index": 0}]]
        },
        "Schedule Payment": {
            "main": [[{"node": "Update Payment Schedule", "type": "main", "index": 0}]]
        },
        "Update Payment Schedule": {
            "main": [[{"node": "Mark Email Processed", "type": "main", "index": 0}]]
        },
        "Mark Email Processed": {
            "main": [[{"node": "Write Audit Log", "type": "main", "index": 0}]]
        },
        "Write Audit Log": {
            "main": [[{"node": "Loop Over Bills", "type": "main", "index": 0}]]
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]]
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW DEFINITIONS
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "wf04": {
        "name": "Accounting Dept - Supplier Bills AP (WF-04)",
        "build_nodes": lambda: build_nodes(),
        "build_connections": lambda: build_connections(),
    },
}


# ══════════════════════════════════════════════════════════════
# BUILD / SAVE / STATS
# ══════════════════════════════════════════════════════════════

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
        "wf04": "wf04_supplier_bills.json",
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

    # Node type breakdown
    type_counts = {}
    for n in func_nodes:
        t = n["type"].replace("n8n-nodes-base.", "")
        type_counts[t] = type_counts.get(t, 0) + 1
    print("  Node types:")
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    # Add tools dir to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("ACCOUNTING DEPARTMENT - WF-04 SUPPLIER BILLS AP")
    print("=" * 60)

    # Determine which workflows to build
    valid_wfs = list(WORKFLOW_DEFS.keys())

    if action not in ("build", "deploy", "activate"):
        print(f"ERROR: Unknown action '{action}'. Use: build, deploy, activate")
        sys.exit(1)

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
        print("  Set these env vars in your .env file:")
        print("  - ACCOUNTING_AIRTABLE_BASE_ID")
        print("  - ACCOUNTING_TABLE_SUPPLIERS")
        print("  - ACCOUNTING_TABLE_SUPPLIER_BILLS")
        print("  - ACCOUNTING_TABLE_TASKS")
        print("  - ACCOUNTING_TABLE_AUDIT_LOG")
        print()
        if action in ("deploy", "activate"):
            print("Cannot deploy with placeholder IDs. Aborting.")
            sys.exit(1)
        print("Continuing build with placeholder IDs (for preview only)...")
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
                    # Create new
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
    print("  2. Verify credential bindings (Airtable, Gmail, QuickBooks OAuth2, OpenRouter)")
    print("  3. Create Gmail label 'Bills' and 'Processed' if not existing")
    print("  4. Test with Manual Trigger using a sample supplier invoice email")
    print("  5. Verify QuickBooks bill creation in QuickBooks dashboard")
    print("  6. Check Airtable for bill record, audit log, and supplier entries")
    print("  7. Test approval flow: send an invoice > R10,000 to trigger manual approval")
    print("  8. Once verified, activate schedule trigger for business hours monitoring")


if __name__ == "__main__":
    main()
