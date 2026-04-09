"""
Accounting Department - Payments & Reconciliation (WF-03) Builder & Deployer

Handles:
- Stripe payment webhooks
- PayFast ITN (Instant Transaction Notification) webhooks
- Daily bank import from QuickBooks
- Payment matching (exact + AI fuzzy)
- Partial/overpayment handling
- Receipt sending
- Audit logging

Usage:
    python tools/deploy_accounting_wf03.py build
    python tools/deploy_accounting_wf03.py deploy
    python tools/deploy_accounting_wf03.py activate
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

# ── Credential Constants (from centralized module) ────────────

sys.path.insert(0, str(Path(__file__).parent))
from credentials import CREDENTIALS

CRED_OPENROUTER = CREDENTIALS["openrouter"]
CRED_GMAIL = CREDENTIALS["gmail"]
CRED_AIRTABLE = CREDENTIALS["airtable"]
CRED_QUICKBOOKS = CREDENTIALS["quickbooks"]
CRED_STRIPE = {"id": os.getenv("ACCOUNTING_STRIPE_CRED_ID", "REPLACE"), "name": "Stripe API AVM"}

QBO_COMPANY_ID = os.getenv("ACCOUNTING_QBO_COMPANY_ID", "REPLACE_WITH_TENANT_ID")

# ── Airtable IDs ──────────────────────────────────────────────

AIRTABLE_BASE_ID = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
TABLE_INVOICES = os.getenv("ACCOUNTING_TABLE_INVOICES", "REPLACE_WITH_TABLE_ID")
TABLE_PAYMENTS = os.getenv("ACCOUNTING_TABLE_PAYMENTS", "REPLACE_WITH_TABLE_ID")
TABLE_CUSTOMERS = os.getenv("ACCOUNTING_TABLE_CUSTOMERS", "REPLACE_WITH_TABLE_ID")
TABLE_TASKS = os.getenv("ACCOUNTING_TABLE_TASKS", "REPLACE_WITH_TABLE_ID")
TABLE_AUDIT_LOG = os.getenv("ACCOUNTING_TABLE_AUDIT_LOG", "REPLACE_WITH_TABLE_ID")

# Validate required environment variables
_required_vars = {
    "ACCOUNTING_QBO_COMPANY_ID": QBO_COMPANY_ID,
    "ACCOUNTING_AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
    "ACCOUNTING_TABLE_INVOICES": TABLE_INVOICES,
    "ACCOUNTING_TABLE_PAYMENTS": TABLE_PAYMENTS,
    "ACCOUNTING_TABLE_CUSTOMERS": TABLE_CUSTOMERS,
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


# ══════════════════════════════════════════════════════════════
# WF-03: PAYMENTS & RECONCILIATION - NODES
# ══════════════════════════════════════════════════════════════

def build_nodes():
    """Build all 26 nodes for the Payments & Reconciliation workflow."""
    nodes = []

    # ── 1. Stripe Payment Webhook ─────────────────────────────
    nodes.append({
        "parameters": {
            "path": "accounting/stripe-webhook",
            "httpMethod": "POST",
            "responseMode": "lastNode",
            "options": {},
        },
        "id": uid(),
        "name": "Stripe Payment Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 300],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # ── 2. PayFast ITN Webhook ────────────────────────────────
    nodes.append({
        "parameters": {
            "path": "accounting/payfast-itn",
            "httpMethod": "POST",
            "responseMode": "lastNode",
            "options": {},
        },
        "id": uid(),
        "name": "PayFast ITN Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 500],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # ── 2b. Verify Stripe Signature ────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const crypto = require('crypto');\n"
                "const input = $input.first().json;\n"
                "const sig = input.headers?.['stripe-signature'] || '';\n"
                "const secret = '';\n"
                "\n"
                "if (!secret) {\n"
                "  throw new Error('STRIPE_WEBHOOK_SECRET not configured in n8n environment');\n"
                "}\n"
                "if (!sig) {\n"
                "  throw new Error('Missing Stripe signature header');\n"
                "}\n"
                "\n"
                "// Parse Stripe signature: t=timestamp,v1=signature\n"
                "const parts = {};\n"
                "sig.split(',').forEach(part => {\n"
                "  const [key, val] = part.split('=');\n"
                "  parts[key] = val;\n"
                "});\n"
                "\n"
                "const timestamp = parts['t'];\n"
                "const receivedSig = parts['v1'];\n"
                "\n"
                "if (!timestamp || !receivedSig) {\n"
                "  throw new Error('Invalid Stripe signature format');\n"
                "}\n"
                "\n"
                "// Verify: HMAC-SHA256 of timestamp.payload\n"
                "const payload = JSON.stringify(input.body || input);\n"
                "const signedPayload = `${timestamp}.${payload}`;\n"
                "const expected = crypto.createHmac('sha256', secret)\n"
                "  .update(signedPayload)\n"
                "  .digest('hex');\n"
                "\n"
                "if (expected !== receivedSig) {\n"
                "  throw new Error('Stripe signature verification failed');\n"
                "}\n"
                "\n"
                "// Check timestamp is within 5 minutes to prevent replay attacks\n"
                "const tolerance = 300; // 5 minutes\n"
                "const now = Math.floor(Date.now() / 1000);\n"
                "if (Math.abs(now - parseInt(timestamp)) > tolerance) {\n"
                "  throw new Error('Stripe webhook timestamp too old (possible replay)');\n"
                "}\n"
                "\n"
                "return $input.all();"
            ),
        },
        "id": uid(),
        "name": "Verify Stripe Signature",
        "type": "n8n-nodes-base.code",
        "position": [400, 300],
        "typeVersion": 2,
    })

    # ── 3. Daily Bank Import (Schedule) ───────────────────────
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 6 * * *",
                    }
                ]
            },
        },
        "id": uid(),
        "name": "Daily Bank Import",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 700],
        "typeVersion": 1.2,
    })

    # ── 4. Manual Trigger ─────────────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 900],
        "typeVersion": 1,
    })

    # ── 5. System Config ──────────────────────────────────────
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
                        "name": "defaultCurrency",
                        "value": "ZAR",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "vatRate",
                        "value": "0.15",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "qboCompanyId",
                        "value": os.getenv("ACCOUNTING_QBO_COMPANY_ID", ""),
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [500, 700],
        "typeVersion": 3.4,
    })

    # ── 6. Validate PayFast Signature ─────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const body = input.body || input;\n"
                "\n"
                "// PayFast ITN signature validation\n"
                "// 1. Get all posted params except signature\n"
                "const params = {};\n"
                "const skipFields = ['signature'];\n"
                "for (const [key, value] of Object.entries(body)) {\n"
                "  if (!skipFields.includes(key) && value !== '') {\n"
                "    params[key] = value;\n"
                "  }\n"
                "}\n"
                "\n"
                "// 2. Sort alphabetically and URL-encode\n"
                "const sortedKeys = Object.keys(params).sort();\n"
                "const paramString = sortedKeys.map(key => \n"
                "  `${key}=${encodeURIComponent(params[key]).replace(/%20/g, '+')}`\n"
                ").join('&');\n"
                "\n"
                "// 3. Add passphrase from n8n environment variable\n"
                "const passphrase = 'Alisamazing0904';\n"
                "const stringToHash = passphrase ? `${paramString}&passphrase=${encodeURIComponent(passphrase)}` : paramString;\n"
                "\n"
                "// 4. MD5 hash\n"
                "const crypto = require('crypto');\n"
                "const calculatedSignature = crypto.createHash('md5').update(stringToHash).digest('hex');\n"
                "\n"
                "const isValid = calculatedSignature === body.signature;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...body,\n"
                "    isValid: isValid,\n"
                "    calculatedSignature: calculatedSignature,\n"
                "    receivedSignature: body.signature || '',\n"
                "    paymentStatus: body.payment_status,\n"
                "    amount: parseFloat(body.amount_gross || body.amount_net || '0'),\n"
                "    reference: body.m_payment_id || body.pf_payment_id || '',\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Validate PayFast Signature",
        "type": "n8n-nodes-base.code",
        "position": [500, 500],
        "typeVersion": 2,
    })

    # ── 7. PayFast Signature Valid? ───────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.isValid }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                        },
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "PayFast Signature Valid?",
        "type": "n8n-nodes-base.if",
        "position": [750, 500],
        "typeVersion": 2,
    })

    # ── 8. Log Invalid PayFast ────────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "list"},
            "table": {"__rl": True, "value": TABLE_AUDIT_LOG, "mode": "list"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Event Type": "PAYFAST_INVALID_SIGNATURE",
                    "Details": "={{ 'Invalid PayFast ITN signature. Received: ' + $json.receivedSignature + ', Calculated: ' + $json.calculatedSignature }}",
                    "Timestamp": "={{ $now.toISO() }}",
                    "Source": "PayFast ITN",
                    "Status": "Warning",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Invalid PayFast",
        "type": "n8n-nodes-base.airtable",
        "position": [1000, 620],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 9. Normalize Payment Data ─────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const body = input.body || input;\n"
                "\n"
                "// Check if this came from System Config (schedule/manual trigger) with no actual payment data\n"
                "// System Config sets todayDate, companyName, etc. but no payment fields\n"
                "if (!body.body && !body.amount && !body.payment_intent && !body.m_payment_id\n"
                "    && !body.pf_payment_id && !body.amount_gross && !body.type\n"
                "    && (body.todayDate || body.companyName)) {\n"
                "  // No payment data available - this was a scheduled/manual trigger without webhook data\n"
                "  // TODO: In production, this path should call the QuickBooks Banking API\n"
                "  // to fetch recent bank transactions before normalizing\n"
                "  return [{json: {_noPayment: true, reason: 'No payment data - bank import not yet configured'}}];\n"
                "}\n"
                "\n"
                "let normalized;\n"
                "\n"
                "// Detect source\n"
                "if (body.type === 'payment_intent.succeeded' || body.object === 'event') {\n"
                "  // Stripe webhook\n"
                "  const pi = body.data ? body.data.object : body;\n"
                "  normalized = {\n"
                "    amount: (pi.amount || 0) / 100, // Stripe uses cents\n"
                "    currency: (pi.currency || 'zar').toUpperCase(),\n"
                "    reference: pi.metadata ? (pi.metadata.invoice_number || pi.id) : pi.id,\n"
                "    method: 'Stripe',\n"
                "    gatewayTransactionId: pi.id,\n"
                "    payerEmail: pi.receipt_email || (pi.charges ? pi.charges.data[0].billing_details.email : ''),\n"
                "    payerName: pi.metadata ? pi.metadata.customer_name : '',\n"
                "    dateReceived: new Date().toISOString().split('T')[0],\n"
                "  };\n"
                "} else if (body.pf_payment_id || body.payment_status) {\n"
                "  // PayFast ITN\n"
                "  normalized = {\n"
                "    amount: parseFloat(body.amount_gross || '0'),\n"
                "    currency: 'ZAR',\n"
                "    reference: body.m_payment_id || body.custom_str1 || '',\n"
                "    method: 'PayFast',\n"
                "    gatewayTransactionId: body.pf_payment_id,\n"
                "    payerEmail: body.email_address || '',\n"
                "    payerName: `${body.name_first || ''} ${body.name_last || ''}`.trim(),\n"
                "    dateReceived: new Date().toISOString().split('T')[0],\n"
                "  };\n"
                "} else {\n"
                "  // Manual/bank import\n"
                "  normalized = {\n"
                "    amount: parseFloat(body.amount || '0'),\n"
                "    currency: body.currency || 'ZAR',\n"
                "    reference: body.reference || body.description || '',\n"
                "    method: body.method || 'EFT',\n"
                "    gatewayTransactionId: body.transaction_id || '',\n"
                "    payerEmail: body.payer_email || '',\n"
                "    payerName: body.payer_name || '',\n"
                "    dateReceived: body.date || new Date().toISOString().split('T')[0],\n"
                "  };\n"
                "}\n"
                "\n"
                "normalized.paymentId = `PAY-${Date.now()}`;\n"
                "\n"
                "return { json: normalized };"
            ),
        },
        "id": uid(),
        "name": "Normalize Payment Data",
        "type": "n8n-nodes-base.code",
        "position": [1000, 400],
        "typeVersion": 2,
    })

    # ── 10. Create Payment Record ─────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "list"},
            "table": {"__rl": True, "value": TABLE_PAYMENTS, "mode": "list"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Payment ID": "={{ $json.paymentId }}",
                    "Amount": "={{ $json.amount }}",
                    "Currency": "={{ $json.currency }}",
                    "Reference": "={{ $json.reference }}",
                    "Method": "={{ $json.method }}",
                    "Gateway Transaction ID": "={{ $json.gatewayTransactionId }}",
                    "Payer Email": "={{ $json.payerEmail }}",
                    "Payer Name": "={{ $json.payerName }}",
                    "Date Received": "={{ $json.dateReceived }}",
                    "Reconciliation Status": "Unmatched",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Payment Record",
        "type": "n8n-nodes-base.airtable",
        "position": [1250, 400],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 11. Search Open Invoices ──────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "list"},
            "table": {"__rl": True, "value": TABLE_INVOICES, "mode": "list"},
            "filterByFormula": "OR({Status}='Sent', {Status}='Partial', {Status}='Overdue')",
            "options": {
                "fields": [
                    "Invoice ID",
                    "Invoice Number",
                    "Customer ID",
                    "Customer Name",
                    "Total",
                    "Amount Paid",
                    "Balance Due",
                    "Status",
                    "Due Date",
                ],
            },
        },
        "id": uid(),
        "name": "Search Open Invoices",
        "type": "n8n-nodes-base.airtable",
        "position": [1500, 400],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 12. Exact Match Attempt ───────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const payment = $('Create Payment Record').first().json;\n"
                "const invoices = $input.all().map(i => i.json ? i : {json: i});\n"
                "const reference = (payment.reference || '').toUpperCase();\n"
                "const amount = payment.amount;\n"
                "\n"
                "let matchedInvoice = null;\n"
                "let matchType = 'none';\n"
                "\n"
                "// 1. Try exact invoice number match in reference\n"
                "for (const inv of invoices) {\n"
                "  const invNum = (inv.json['Invoice Number'] || '').toUpperCase();\n"
                "  if (invNum && reference.includes(invNum)) {\n"
                "    const invTotal = parseFloat(inv.json['Balance Due'] || inv.json['Total'] || 0);\n"
                "    if (Math.abs(amount - invTotal) < 0.50) {\n"
                "      matchedInvoice = inv.json;\n"
                "      matchType = 'exact';\n"
                "      break;\n"
                "    } else {\n"
                "      matchedInvoice = inv.json;\n"
                "      matchType = 'reference_match_amount_differs';\n"
                "      break;\n"
                "    }\n"
                "  }\n"
                "}\n"
                "\n"
                "// 2. If no reference match, try exact amount match (only if unique)\n"
                "if (!matchedInvoice) {\n"
                "  const amountMatches = invoices.filter(inv => {\n"
                "    const invTotal = parseFloat(inv.json['Balance Due'] || inv.json['Total'] || 0);\n"
                "    return Math.abs(amount - invTotal) < 0.50;\n"
                "  });\n"
                "  if (amountMatches.length === 1) {\n"
                "    matchedInvoice = amountMatches[0].json;\n"
                "    matchType = 'amount_match';\n"
                "  }\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...payment,\n"
                "    matchFound: !!matchedInvoice,\n"
                "    matchType: matchType,\n"
                "    matchedInvoiceId: matchedInvoice ? matchedInvoice['Invoice ID'] : null,\n"
                "    matchedInvoiceNumber: matchedInvoice ? matchedInvoice['Invoice Number'] : null,\n"
                "    matchedCustomerId: matchedInvoice ? matchedInvoice['Customer ID'] : null,\n"
                "    matchedCustomerName: matchedInvoice ? matchedInvoice['Customer Name'] : null,\n"
                "    matchedInvoiceTotal: matchedInvoice ? parseFloat(matchedInvoice['Total'] || 0) : 0,\n"
                "    matchedBalanceDue: matchedInvoice ? parseFloat(matchedInvoice['Balance Due'] || matchedInvoice['Total'] || 0) : 0,\n"
                "    openInvoiceCount: invoices.length,\n"
                "    openInvoiceSummary: invoices.slice(0, 10).map(i => ({\n"
                "      id: i.json['Invoice ID'],\n"
                "      number: i.json['Invoice Number'],\n"
                "      customer: i.json['Customer Name'],\n"
                "      total: i.json['Total'],\n"
                "      balance: i.json['Balance Due'],\n"
                "    })),\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Exact Match Attempt",
        "type": "n8n-nodes-base.code",
        "position": [1750, 400],
        "typeVersion": 2,
    })

    # ── 13. Match Found? ──────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.matchFound }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                        },
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Match Found?",
        "type": "n8n-nodes-base.if",
        "position": [2000, 400],
        "typeVersion": 2,
    })

    # ── 14. Fuzzy Match via AI ────────────────────────────────
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
                '  "model": "anthropic/claude-sonnet-4-20250514",\n'
                '  "max_tokens": 500,\n'
                '  "temperature": 0,\n'
                '  "messages": [\n'
                '    {"role": "system", "content": "You are a payment reconciliation assistant. Match a payment to the most likely invoice. Return JSON only: {matched_invoice_id, matched_invoice_number, confidence: 0-1, reasoning: string}. If no match, set confidence to 0."},\n'
                '    {"role": "user", "content": "Payment: R{{ $json.amount }} from {{ $json.payerName || $json.payerEmail }}, reference: {{ $json.reference }}, method: {{ $json.method }}.\\n\\nOpen invoices:\\n{{ JSON.stringify($json.openInvoiceSummary) }}"}\n'
                '  ]\n'
                '}'
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Fuzzy Match via AI",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2250, 550],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # ── 15. Parse AI Match ────────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const payment = $('Exact Match Attempt').first().json;\n"
                "\n"
                "let match;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  match = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch(e) {\n"
                "  match = { matched_invoice_id: null, confidence: 0, reasoning: 'Failed to parse AI response' };\n"
                "}\n"
                "\n"
                "// Look up matched invoice details for balance/total fields\n"
                "const matchedInvoiceId = match.matched_invoice_id || null;\n"
                "const matchedInvoiceNumber = match.matched_invoice_number || null;\n"
                "let matchedBalanceDue = 0;\n"
                "let matchedInvoiceTotal = 0;\n"
                "let matchedCustomerId = null;\n"
                "let matchedCustomerName = null;\n"
                "\n"
                "if (matchedInvoiceId || matchedInvoiceNumber) {\n"
                "  const invoices = $('Search Open Invoices').all();\n"
                "  const matchedInvoice = invoices.find(i =>\n"
                "    i.json['Invoice ID'] === matchedInvoiceId || i.json['Invoice Number'] === matchedInvoiceNumber\n"
                "  );\n"
                "  if (matchedInvoice) {\n"
                "    matchedBalanceDue = parseFloat(matchedInvoice.json['Balance Due'] || matchedInvoice.json['Total'] || 0);\n"
                "    matchedInvoiceTotal = parseFloat(matchedInvoice.json['Total'] || 0);\n"
                "    matchedCustomerId = matchedInvoice.json['Customer ID'] || null;\n"
                "    matchedCustomerName = matchedInvoice.json['Customer Name'] || null;\n"
                "  }\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...payment,\n"
                "    matchFound: match.confidence > 0.5,\n"
                "    matchType: 'ai_fuzzy',\n"
                "    matchConfidence: match.confidence,\n"
                "    matchReasoning: match.reasoning || '',\n"
                "    matchedInvoiceId: matchedInvoiceId,\n"
                "    matchedInvoiceNumber: matchedInvoiceNumber,\n"
                "    matchedBalanceDue: matchedBalanceDue,\n"
                "    matchedInvoiceTotal: matchedInvoiceTotal,\n"
                "    matchedCustomerId: matchedCustomerId,\n"
                "    matchedCustomerName: matchedCustomerName,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Parse AI Match",
        "type": "n8n-nodes-base.code",
        "position": [2500, 550],
        "typeVersion": 2,
    })

    # ── 16. Auto-Match OK? ────────────────────────────────────
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.matchConfidence }}",
                        "rightValue": 0.8,
                        "operator": {
                            "type": "number",
                            "operation": "gt",
                        },
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Auto-Match OK?",
        "type": "n8n-nodes-base.if",
        "position": [2750, 550],
        "typeVersion": 2,
    })

    # ── 17. Create Manual Review Task ─────────────────────────
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "list"},
            "table": {"__rl": True, "value": TABLE_TASKS, "mode": "list"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Task Type": "Manual Reconciliation",
                    "Status": "Open",
                    "Priority": "High",
                    "Title": "={{ 'Reconcile payment ' + $json.paymentId + ' - R' + $json.amount }}",
                    "Description": "={{ 'Payment of R' + $json.amount + ' from ' + ($json.payerName || $json.payerEmail || 'Unknown') + ' via ' + $json.method + '. Reference: ' + ($json.reference || 'None') + '. AI confidence: ' + ($json.matchConfidence || 0) + '. Reasoning: ' + ($json.matchReasoning || 'N/A') }}",
                    "Payment ID": "={{ $json.paymentId }}",
                    "Created Date": "={{ $now.toISO() }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Manual Review Task",
        "type": "n8n-nodes-base.airtable",
        "position": [3000, 700],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 18. Handle Partial/Over ───────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const data = $input.first().json;\n"
                "const paymentAmount = data.amount;\n"
                "const balanceDue = data.matchedBalanceDue;\n"
                "\n"
                "let status, newBalance, newAmountPaid, invoiceStatus;\n"
                "\n"
                "if (Math.abs(paymentAmount - balanceDue) < 0.50) {\n"
                "  status = 'exact';\n"
                "  newBalance = 0;\n"
                "  newAmountPaid = data.matchedInvoiceTotal;\n"
                "  invoiceStatus = 'Paid';\n"
                "} else if (paymentAmount < balanceDue) {\n"
                "  status = 'partial';\n"
                "  newBalance = Math.round((balanceDue - paymentAmount) * 100) / 100;\n"
                "  newAmountPaid = Math.round((data.matchedInvoiceTotal - newBalance) * 100) / 100;\n"
                "  invoiceStatus = 'Partial';\n"
                "} else {\n"
                "  status = 'overpayment';\n"
                "  newBalance = 0;\n"
                "  newAmountPaid = data.matchedInvoiceTotal;\n"
                "  invoiceStatus = 'Paid';\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...data,\n"
                "    paymentType: status,\n"
                "    newBalanceDue: newBalance,\n"
                "    newAmountPaid: newAmountPaid,\n"
                "    overpaymentAmount: status === 'overpayment' ? Math.round((paymentAmount - balanceDue) * 100) / 100 : 0,\n"
                "    invoiceStatus: invoiceStatus,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Handle Partial/Over",
        "type": "n8n-nodes-base.code",
        "position": [2250, 250],
        "typeVersion": 2,
    })

    # ── 19. Post Payment to QuickBooks ──────────────────────────────
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://quickbooks.api.intuit.com/v3/company/  # TODO: Update to QuickBooks endpoint. Was: api.xero.com/api.xro/2.0/Payments",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "quickBooksOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "qbo-company-id", "value": "={{ $('System Config').first().json.qboCompanyId || '' }}"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                '={\n'
                '  "Invoice": {\n'
                '    "InvoiceNumber": "{{ $json.matchedInvoiceNumber }}"\n'
                '  },\n'
                '  "Account": {\n'
                '    "Code": "090"\n'
                '  },\n'
                '  "Date": "{{ $json.dateReceived }}",\n'
                '  "Amount": {{ $json.amount }},\n'
                '  "Reference": "{{ $json.paymentId }} - {{ $json.method }}"\n'
                '}'
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Post Payment to QuickBooks",
        "type": "n8n-nodes-base.httpRequest",
        "position": [2500, 250],
        "typeVersion": 4.2,
        "credentials": {"quickBooksOAuth2Api": CRED_QUICKBOOKS},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # ── 20. Update Invoice Status ─────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "list"},
            "table": {"__rl": True, "value": TABLE_INVOICES, "mode": "list"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Invoice ID": "={{ $json.matchedInvoiceId }}",
                    "Status": "={{ $json.invoiceStatus }}",
                    "Amount Paid": "={{ $json.newAmountPaid }}",
                    "Balance Due": "={{ $json.newBalanceDue }}",
                    "Last Payment Date": "={{ $json.dateReceived }}",
                    "Last Payment Method": "={{ $json.method }}",
                },
                "matchingColumns": ["Invoice ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Invoice Status",
        "type": "n8n-nodes-base.airtable",
        "position": [2750, 250],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 21. Update Payment Status ─────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "list"},
            "table": {"__rl": True, "value": TABLE_PAYMENTS, "mode": "list"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Payment ID": "={{ $json.paymentId }}",
                    "Reconciliation Status": "Matched",
                    "Matched Invoice": "={{ $json.matchedInvoiceNumber }}",
                    "Match Type": "={{ $json.matchType }}",
                    "Payment Type": "={{ $json.paymentType }}",
                    "QuickBooks Payment ID": "={{ $json.qboPaymentId || '' }}",
                    "Reconciled Date": "={{ $now.toISO() }}",
                },
                "matchingColumns": ["Payment ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Payment Status",
        "type": "n8n-nodes-base.airtable",
        "position": [3000, 250],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 22. Build Receipt HTML ────────────────────────────────
    nodes.append({
        "parameters": {
            "jsCode": (
                "const data = $input.first().json;\n"
                "\n"
                "const html = `<!DOCTYPE html>\n"
                "<html>\n"
                "<head><meta charset=\"utf-8\"></head>\n"
                "<body style=\"margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f4;\">\n"
                "  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;margin:0 auto;background-color:#ffffff;\">\n"
                "    <tr>\n"
                "      <td style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">\n"
                "        <h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">PAYMENT RECEIPT</h1>\n"
                "        <p style=\"margin:5px 0 0;color:#666;\">AnyVision Media</p>\n"
                "      </td>\n"
                "    </tr>\n"
                "    <tr>\n"
                "      <td style=\"padding:30px 40px;\">\n"
                "        <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">\n"
                "          Hi ${data.matchedCustomerName || 'Customer'},\n"
                "        </p>\n"
                "        <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">\n"
                "          Thank you for your payment. This confirms we have received:\n"
                "        </p>\n"
                "        <table width=\"100%\" style=\"margin:20px 0;border-collapse:collapse;\">\n"
                "          <tr><td style=\"padding:8px;color:#666;\">Amount Received:</td><td style=\"padding:8px;text-align:right;\"><strong>R ${data.amount.toFixed(2)}</strong></td></tr>\n"
                "          <tr><td style=\"padding:8px;color:#666;\">Payment Method:</td><td style=\"padding:8px;text-align:right;\">${data.method}</td></tr>\n"
                "          <tr><td style=\"padding:8px;color:#666;\">Date:</td><td style=\"padding:8px;text-align:right;\">${data.dateReceived}</td></tr>\n"
                "          <tr><td style=\"padding:8px;color:#666;\">Invoice:</td><td style=\"padding:8px;text-align:right;\">${data.matchedInvoiceNumber || 'N/A'}</td></tr>\n"
                "          <tr style=\"border-top:1px solid #eee;\"><td style=\"padding:8px;color:#666;\">Remaining Balance:</td><td style=\"padding:8px;text-align:right;\"><strong>R ${(data.newBalanceDue || 0).toFixed(2)}</strong></td></tr>\n"
                "        </table>\n"
                "        ${data.paymentType === 'partial' ? '<p style=\"color:#FF6D5A;font-size:14px;\">Note: This is a partial payment. The remaining balance is shown above.</p>' : ''}\n"
                "        ${data.paymentType === 'overpayment' ? '<p style=\"color:#FF6D5A;font-size:14px;\">Note: An overpayment of R ' + data.overpaymentAmount.toFixed(2) + ' was detected. This will be applied as a credit.</p>' : ''}\n"
                "      </td>\n"
                "    </tr>\n"
                "    <tr>\n"
                "      <td style=\"padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;\">\n"
                "        <p style=\"margin:0;font-size:11px;color:#999;\">AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com</p>\n"
                "      </td>\n"
                "    </tr>\n"
                "  </table>\n"
                "</body>\n"
                "</html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...data,\n"
                "    receiptHtml: html,\n"
                "    receiptSubject: 'Payment Receipt - ' + (data.matchedInvoiceNumber || 'AnyVision Media'),\n"
                "    customerEmail: data.payerEmail || '',\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Receipt HTML",
        "type": "n8n-nodes-base.code",
        "position": [3250, 250],
        "typeVersion": 2,
    })

    # ── 23. Send Receipt Email ────────────────────────────────
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.customerEmail }}",
            "subject": "={{ $json.receiptSubject }}",
            "emailType": "html",
            "message": "={{ $json.receiptHtml }}",
            "options": {
                "senderName": "AnyVision Media Accounts",
                "replyTo": "accounts@anyvisionmedia.com",
            },
        },
        "id": uid(),
        "name": "Send Receipt Email",
        "type": "n8n-nodes-base.gmail",
        "position": [3500, 250],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── 24. Write Audit Log ───────────────────────────────────
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": AIRTABLE_BASE_ID, "mode": "list"},
            "table": {"__rl": True, "value": TABLE_AUDIT_LOG, "mode": "list"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Event Type": "PAYMENT_RECONCILED",
                    "Payment ID": "={{ $json.paymentId }}",
                    "Invoice Number": "={{ $json.matchedInvoiceNumber || '' }}",
                    "Amount": "={{ $json.amount }}",
                    "Method": "={{ $json.method }}",
                    "Match Type": "={{ $json.matchType }}",
                    "Payment Type": "={{ $json.paymentType }}",
                    "Customer": "={{ $json.matchedCustomerName || $json.payerName || '' }}",
                    "Details": "={{ 'Payment R' + $json.amount + ' via ' + $json.method + ' matched to ' + ($json.matchedInvoiceNumber || 'N/A') + ' (' + $json.matchType + '). Status: ' + $json.invoiceStatus }}",
                    "Timestamp": "={{ $now.toISO() }}",
                    "Source": "WF-03 Auto Reconciliation",
                    "Status": "Success",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Audit Log",
        "type": "n8n-nodes-base.airtable",
        "position": [3750, 250],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 25. Error Trigger ─────────────────────────────────────
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 1100],
        "typeVersion": 1,
    })

    # ── 26. Error Notification ────────────────────────────────
    nodes.append({
        "parameters": {
            "sendTo": "accounts@anyvisionmedia.com",
            "subject": "=WF-03 Error: Payments & Reconciliation - {{ $json.workflow.name }}",
            "emailType": "html",
            "message": (
                "=<h2>WF-03 Payments & Reconciliation Error</h2>"
                "<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>"
                "<p><strong>Node:</strong> {{ $json.execution.error.node.name }}</p>"
                "<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>"
                "<p><strong>Time:</strong> {{ $now.toISO() }}</p>"
                "<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>"
            ),
            "options": {
                "senderName": "AVM Workflow Monitor",
            },
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [500, 1100],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


# ══════════════════════════════════════════════════════════════
# WF-03: PAYMENTS & RECONCILIATION - CONNECTIONS
# ══════════════════════════════════════════════════════════════

def build_connections():
    """Build connections for the Payments & Reconciliation workflow."""
    connections = {
        "Stripe Payment Webhook": {
            "main": [[{"node": "Verify Stripe Signature", "type": "main", "index": 0}]],
        },
        "Verify Stripe Signature": {
            "main": [[{"node": "Normalize Payment Data", "type": "main", "index": 0}]],
        },
        "PayFast ITN Webhook": {
            "main": [[{"node": "Validate PayFast Signature", "type": "main", "index": 0}]],
        },
        "Validate PayFast Signature": {
            "main": [[{"node": "PayFast Signature Valid?", "type": "main", "index": 0}]],
        },
        "PayFast Signature Valid?": {
            "main": [
                [{"node": "Normalize Payment Data", "type": "main", "index": 0}],  # true - valid
                [{"node": "Log Invalid PayFast", "type": "main", "index": 0}],  # false - invalid
            ],
        },
        "Daily Bank Import": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Normalize Payment Data", "type": "main", "index": 0}]],
        },
        "Normalize Payment Data": {
            "main": [[{"node": "Create Payment Record", "type": "main", "index": 0}]],
        },
        "Create Payment Record": {
            "main": [[{"node": "Search Open Invoices", "type": "main", "index": 0}]],
        },
        "Search Open Invoices": {
            "main": [[{"node": "Exact Match Attempt", "type": "main", "index": 0}]],
        },
        "Exact Match Attempt": {
            "main": [[{"node": "Match Found?", "type": "main", "index": 0}]],
        },
        "Match Found?": {
            "main": [
                [{"node": "Handle Partial/Over", "type": "main", "index": 0}],  # true - match found
                [{"node": "Fuzzy Match via AI", "type": "main", "index": 0}],  # false - no match
            ],
        },
        "Fuzzy Match via AI": {
            "main": [[{"node": "Parse AI Match", "type": "main", "index": 0}]],
        },
        "Parse AI Match": {
            "main": [[{"node": "Auto-Match OK?", "type": "main", "index": 0}]],
        },
        "Auto-Match OK?": {
            "main": [
                [{"node": "Handle Partial/Over", "type": "main", "index": 0}],  # true - confidence > 0.8
                [{"node": "Create Manual Review Task", "type": "main", "index": 0}],  # false - low confidence
            ],
        },
        "Handle Partial/Over": {
            "main": [[{"node": "Post Payment to QuickBooks", "type": "main", "index": 0}]],
        },
        "Post Payment to QuickBooks": {
            "main": [[{"node": "Update Invoice Status", "type": "main", "index": 0}]],
        },
        "Update Invoice Status": {
            "main": [[{"node": "Update Payment Status", "type": "main", "index": 0}]],
        },
        "Update Payment Status": {
            "main": [[{"node": "Build Receipt HTML", "type": "main", "index": 0}]],
        },
        "Build Receipt HTML": {
            "main": [[{"node": "Send Receipt Email", "type": "main", "index": 0}]],
        },
        "Send Receipt Email": {
            "main": [[{"node": "Write Audit Log", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }

    return connections


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "wf03": {
        "name": "Accounting Dept - Payments & Reconciliation (WF-03)",
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
        "wf03": "wf03_payments_reconciliation.json",
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
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    # Add tools dir to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("ACCOUNTING DEPARTMENT - WF-03 PAYMENTS & RECONCILIATION")
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
        print("  - ACCOUNTING_TABLE_INVOICES")
        print("  - ACCOUNTING_TABLE_PAYMENTS")
        print("  - ACCOUNTING_TABLE_CUSTOMERS")
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
    print("  2. Verify credential bindings (OpenRouter, Airtable, Gmail, QuickBooks)")
    print("  3. Configure Stripe webhook to point to /accounting/stripe-webhook")
    print("  4. Configure PayFast ITN URL to point to /accounting/payfast-itn")
    print("  5. Test with Manual Trigger -> check Airtable for payment records")
    print("  6. Once verified, activate schedule triggers and webhooks")


if __name__ == "__main__":
    main()
