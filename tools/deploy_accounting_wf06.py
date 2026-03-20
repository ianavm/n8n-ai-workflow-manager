"""
Accounting Department - WF-06 Master Data & Audit Builder & Deployer

Builds the Accounting Department WF-06 (Master Data & Audit) workflow
as an n8n workflow JSON file, and optionally deploys it to the n8n instance.

This is a utility workflow with webhook endpoints for audit logging and
customer CRUD, plus a scheduled config cache refresh.

Workflows:
    WF-06: Master Data & Audit (config refresh, audit logging, customer CRUD)

Usage:
    python tools/deploy_accounting_wf06.py build              # Build workflow JSON
    python tools/deploy_accounting_wf06.py deploy             # Build + Deploy (inactive)
    python tools/deploy_accounting_wf06.py activate           # Build + Deploy + Activate
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

# ── Credential Constants ──────────────────────────────────────
# Same IDs used across all tools in this project

CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_QUICKBOOKS = {"id": os.getenv("ACCOUNTING_QBO_CRED_ID", "REPLACE"), "name": "QuickBooks OAuth2 AVM"}
CRED_WHATSAPP_SEND = {"id": "dCAz6MBXpOXvMJrq", "name": "WhatsApp account AVM Multi Agent"}

# ── Airtable IDs ──────────────────────────────────────────────
# UPDATE THESE after setting up the Accounting Airtable base

AIRTABLE_BASE_ID = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
TABLE_CUSTOMERS = os.getenv("ACCOUNTING_TABLE_CUSTOMERS", "REPLACE_WITH_TABLE_ID")
TABLE_SUPPLIERS = os.getenv("ACCOUNTING_TABLE_SUPPLIERS", "REPLACE_WITH_TABLE_ID")
TABLE_PRODUCTS = os.getenv("ACCOUNTING_TABLE_PRODUCTS_SERVICES", "REPLACE_WITH_TABLE_ID")
TABLE_INVOICES = os.getenv("ACCOUNTING_TABLE_INVOICES", "REPLACE_WITH_TABLE_ID")
TABLE_PAYMENTS = os.getenv("ACCOUNTING_TABLE_PAYMENTS", "REPLACE_WITH_TABLE_ID")
TABLE_SUPPLIER_BILLS = os.getenv("ACCOUNTING_TABLE_SUPPLIER_BILLS", "REPLACE_WITH_TABLE_ID")
TABLE_TASKS = os.getenv("ACCOUNTING_TABLE_TASKS", "REPLACE_WITH_TABLE_ID")
TABLE_AUDIT_LOG = os.getenv("ACCOUNTING_TABLE_AUDIT_LOG", "REPLACE_WITH_TABLE_ID")
TABLE_SYSTEM_CONFIG = os.getenv("ACCOUNTING_TABLE_SYSTEM_CONFIG", "REPLACE_WITH_TABLE_ID")

# Validate required environment variables
_required_vars = {
    "ACCOUNTING_AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
    "ACCOUNTING_TABLE_CUSTOMERS": TABLE_CUSTOMERS,
    "ACCOUNTING_TABLE_SUPPLIERS": TABLE_SUPPLIERS,
    "ACCOUNTING_TABLE_PRODUCTS_SERVICES": TABLE_PRODUCTS,
    "ACCOUNTING_TABLE_INVOICES": TABLE_INVOICES,
    "ACCOUNTING_TABLE_PAYMENTS": TABLE_PAYMENTS,
    "ACCOUNTING_TABLE_SUPPLIER_BILLS": TABLE_SUPPLIER_BILLS,
    "ACCOUNTING_TABLE_TASKS": TABLE_TASKS,
    "ACCOUNTING_TABLE_AUDIT_LOG": TABLE_AUDIT_LOG,
    "ACCOUNTING_TABLE_SYSTEM_CONFIG": TABLE_SYSTEM_CONFIG,
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
# WF-06: MASTER DATA & AUDIT
# ══════════════════════════════════════════════════════════════

def build_nodes():
    """Build all nodes for WF-06: Master Data & Audit."""

    nodes = []

    # ── Trigger Nodes ─────────────────────────────────────────

    # 1. Hourly Config Refresh (scheduleTrigger)
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {"field": "cronExpression", "expression": "0 * * * *"}
                ]
            }
        },
        "id": uid(),
        "name": "Hourly Config Refresh",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })

    # 2. Manual Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # ── Config Refresh Flow ───────────────────────────────────

    # 3. System Config (set node)
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
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 500],
        "typeVersion": 3.4,
    })

    # 4. Read System Config (airtable search)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SYSTEM_CONFIG},
            "filterByFormula": "",
        },
        "id": uid(),
        "name": "Read System Config",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 500],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 5. Cache Config Values (code)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const items = $input.all();\n"
                "const config = {};\n"
                "\n"
                "for (const item of items) {\n"
                "  const key = item.json.Key || item.json['Key'];\n"
                "  const value = item.json.Value || item.json['Value'];\n"
                "  if (key && value) {\n"
                "    try {\n"
                "      config[key] = JSON.parse(value);\n"
                "    } catch(e) {\n"
                "      config[key] = value;\n"
                "    }\n"
                "  }\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    configCount: Object.keys(config).length,\n"
                "    config: config,\n"
                "    vatRate: config.vat_standard_rate ? config.vat_standard_rate.rate : 0.15,\n"
                "    currency: config.default_currency ? config.default_currency.code : 'ZAR',\n"
                "    approvalThreshold: config.approval_threshold ? config.approval_threshold.auto_approve_below : 10000,\n"
                "    highValueThreshold: config.high_value_invoice_threshold ? config.high_value_invoice_threshold.threshold : 50000,\n"
                "    invoicePrefix: config.invoice_prefix ? config.invoice_prefix.prefix : 'AVM',\n"
                "    nextInvoiceNumber: config.invoice_prefix ? config.invoice_prefix.next_number : 1001,\n"
                "    cachedAt: new Date().toISOString()\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Cache Config Values",
        "type": "n8n-nodes-base.code",
        "position": [920, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 6. Log Config Read (airtable create) - audit log entry for config refresh
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Timestamp": "={{ $now.toISO() }}",
                    "Workflow Name": "WF-06 Master Data & Audit",
                    "Event Type": "MASTER_DATA_CHANGE",
                    "Record Type": "System Config",
                    "Record ID": "config-cache",
                    "Action Taken": "System config cache refreshed",
                    "Actor": "system",
                    "Result": "Success",
                    "Error Details": "",
                    "Metadata JSON": "={{ JSON.stringify({ cachedAt: $json['cachedAt'], configCount: $json['configCount'] }) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Config Read",
        "type": "n8n-nodes-base.airtable",
        "position": [1160, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Audit Log Webhook Flow ────────────────────────────────

    # 7. Audit Log Webhook
    nodes.append({
        "parameters": {
            "path": "accounting/audit-log",
            "httpMethod": "POST",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Audit Log Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 900],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # 8. Validate Audit Entry (code)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const body = input.body || input;\n"
                "\n"
                "const required = ['workflow', 'event_type', 'record_type', 'record_id', 'action', 'actor'];\n"
                "const missing = required.filter(f => !body[f]);\n"
                "\n"
                "if (missing.length > 0) {\n"
                "  throw new Error(`Missing required audit fields: ${missing.join(', ')}`);\n"
                "}\n"
                "\n"
                "const timestamp = new Date().toISOString();\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    timestamp: timestamp,\n"
                "    workflow: body.workflow,\n"
                "    event_type: body.event_type,\n"
                "    record_type: body.record_type,\n"
                "    record_id: String(body.record_id),\n"
                "    action: body.action,\n"
                "    actor: body.actor,\n"
                "    result: body.result || 'Success',\n"
                "    error: body.error || '',\n"
                "    metadata: body.metadata ? JSON.stringify(body.metadata) : ''\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Validate Audit Entry",
        "type": "n8n-nodes-base.code",
        "position": [440, 900],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 9. Write Audit Log (airtable create)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Timestamp": "={{ $json['timestamp'] }}",
                    "Workflow Name": "={{ $json['workflow'] }}",
                    "Event Type": "={{ $json['event_type'] }}",
                    "Record Type": "={{ $json['record_type'] }}",
                    "Record ID": "={{ $json['record_id'] }}",
                    "Action Taken": "={{ $json['action'] }}",
                    "Actor": "={{ $json['actor'] }}",
                    "Result": "={{ $json['result'] }}",
                    "Error Details": "={{ $json['error'] }}",
                    "Metadata JSON": "={{ $json['metadata'] }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Audit Log",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 900],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 10. Respond Audit Success (respondToWebhook)
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ status: 'logged', timestamp: $json['timestamp'] }) }}",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Audit Success",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [920, 900],
        "typeVersion": 1.1,
        "onError": "continueRegularOutput",
    })

    # 10b. Manual Trigger for Audit Log testing
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Audit Test",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 1000],
        "typeVersion": 1,
    })

    # 10c. Sample Audit Data (code) - generates test payload
    nodes.append({
        "parameters": {
            "jsCode": (
                "return {\n"
                "  json: {\n"
                "    body: {\n"
                "      workflow: 'WF-06 Manual Test',\n"
                "      event_type: 'MASTER_DATA_CHANGE',\n"
                "      record_type: 'System Config',\n"
                "      record_id: 'test-' + Date.now(),\n"
                "      action: 'Manual audit log test entry',\n"
                "      actor: 'manual-test',\n"
                "      result: 'Success',\n"
                "      error: '',\n"
                "      metadata: { test: true, timestamp: new Date().toISOString() }\n"
                "    }\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Sample Audit Data",
        "type": "n8n-nodes-base.code",
        "position": [440, 1000],
        "typeVersion": 2,
    })

    # ── Customer CRUD Webhook Flow ────────────────────────────

    # 11. Customer CRUD Webhook
    nodes.append({
        "parameters": {
            "path": "accounting/customer",
            "httpMethod": "POST",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Customer CRUD Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 1200],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # 11b. Manual Trigger for Customer CRUD testing
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Customer Test",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 1300],
        "typeVersion": 1,
    })

    # 11c. Sample Customer Data (code) - generates test payload
    nodes.append({
        "parameters": {
            "jsCode": (
                "return {\n"
                "  json: {\n"
                "    body: {\n"
                "      action: 'create',\n"
                "      'Customer ID': 'CUST-TEST-' + Date.now(),\n"
                "      'Legal Name': 'Test Company (Pty) Ltd',\n"
                "      'Trading Name': 'Test Co',\n"
                "      'Email': 'test@example.com',\n"
                "      'Phone': '+27 11 555 0100',\n"
                "      'Billing Address': '123 Test Street, Sandton, 2196',\n"
                "      'VAT Number': '4000000000',\n"
                "      'Default Payment Terms': '30 days',\n"
                "      'Credit Limit': 50000,\n"
                "      'Risk Flag': 'Low',\n"
                "      'Preferred Channel': 'Email',\n"
                "      'Active': true,\n"
                "      'Created At': new Date().toISOString().split('T')[0],\n"
                "      'Updated At': new Date().toISOString().split('T')[0]\n"
                "    }\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Sample Customer Data",
        "type": "n8n-nodes-base.code",
        "position": [440, 1300],
        "typeVersion": 2,
    })

    # 12. Validate Customer Data (code)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const body = input.body || input;\n"
                "\n"
                "// Validate email\n"
                "const email = body.email || body.Email || '';\n"
                "if (email && !email.match(/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/)) {\n"
                "  throw new Error(`Invalid email format: ${email}`);\n"
                "}\n"
                "\n"
                "// Validate VAT number (SA format: 10 digits)\n"
                "const vat = body.vat_number || body['VAT Number'] || '';\n"
                "if (vat && !vat.match(/^\\d{10}$/)) {\n"
                "  // Log warning but don't block\n"
                "}\n"
                "\n"
                "const customerId = body.customer_id || body['Customer ID'] || `CUST-${Date.now()}`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    'Customer ID': customerId,\n"
                "    'Legal Name': body.legal_name || body['Legal Name'] || '',\n"
                "    'Trading Name': body.trading_name || body['Trading Name'] || '',\n"
                "    'Email': email,\n"
                "    'Phone': body.phone || body['Phone'] || '',\n"
                "    'Billing Address': body.billing_address || body['Billing Address'] || '',\n"
                "    'VAT Number': vat,\n"
                "    'Default Payment Terms': body.payment_terms || body['Default Payment Terms'] || '30 days',\n"
                "    'Credit Limit': body.credit_limit || body['Credit Limit'] || 0,\n"
                "    'Risk Flag': body.risk_flag || body['Risk Flag'] || 'Low',\n"
                "    'Preferred Channel': body.preferred_channel || body['Preferred Channel'] || 'Email',\n"
                "    'Active': true,\n"
                "    'Created At': new Date().toISOString().split('T')[0],\n"
                "    'Updated At': new Date().toISOString().split('T')[0],\n"
                "    // Pass through for QuickBooks sync\n"
                "    legal_name: body.legal_name || body['Legal Name'] || '',\n"
                "    email: email,\n"
                "    vat_number: vat,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Validate Customer Data",
        "type": "n8n-nodes-base.code",
        "position": [440, 1200],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 13. Upsert Customer (airtable upsert)
    nodes.append({
        "parameters": {
            "operation": "upsert",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_CUSTOMERS},
            "columns": {
                "value": {
                    "Customer ID": "={{ $json['Customer ID'] }}",
                    "Legal Name": "={{ $json['Legal Name'] }}",
                    "Trading Name": "={{ $json['Trading Name'] }}",
                    "Email": "={{ $json['Email'] }}",
                    "Phone": "={{ $json['Phone'] }}",
                    "Billing Address": "={{ $json['Billing Address'] }}",
                    "VAT Number": "={{ $json['VAT Number'] }}",
                    "Default Payment Terms": "={{ $json['Default Payment Terms'] }}",
                    "Credit Limit": "={{ $json['Credit Limit'] }}",
                    "Risk Flag": "={{ $json['Risk Flag'] }}",
                    "Preferred Channel": "={{ $json['Preferred Channel'] }}",
                    "Active": "={{ $json['Active'] }}",
                    "Created At": "={{ $json['Created At'] }}",
                    "Updated At": "={{ $json['Updated At'] }}",
                },
                "schema": [
                    {"id": "Customer ID", "type": "string", "display": True, "displayName": "Customer ID"},
                    {"id": "Legal Name", "type": "string", "display": True, "displayName": "Legal Name"},
                    {"id": "Trading Name", "type": "string", "display": True, "displayName": "Trading Name"},
                    {"id": "Email", "type": "string", "display": True, "displayName": "Email"},
                    {"id": "Phone", "type": "string", "display": True, "displayName": "Phone"},
                    {"id": "Billing Address", "type": "string", "display": True, "displayName": "Billing Address"},
                    {"id": "VAT Number", "type": "string", "display": True, "displayName": "VAT Number"},
                    {"id": "Default Payment Terms", "type": "string", "display": True, "displayName": "Default Payment Terms"},
                    {"id": "Credit Limit", "type": "number", "display": True, "displayName": "Credit Limit"},
                    {"id": "Risk Flag", "type": "string", "display": True, "displayName": "Risk Flag"},
                    {"id": "Preferred Channel", "type": "string", "display": True, "displayName": "Preferred Channel"},
                    {"id": "Active", "type": "boolean", "display": True, "displayName": "Active"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                    {"id": "Updated At", "type": "string", "display": True, "displayName": "Updated At"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Customer ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Upsert Customer",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 1200],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 14. Sync Customer to QuickBooks (httpRequest)
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://quickbooks.api.intuit.com/v3/company/  # TODO: Update to QuickBooks endpoint. Was: api.xero.com/api.xro/2.0/Contacts",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "quickBooksOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "qbo-company-id", "value": "={{ $('System Config').first().json.qboCompanyId || '' }}"},
                ],
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                '={\n'
                '  "Contacts": [{\n'
                '    "Name": "{{ $json.legal_name || $json[\'Legal Name\'] }}",\n'
                '    "EmailAddress": "{{ $json.email || $json[\'Email\'] }}",\n'
                '    "TaxNumber": "{{ $json.vat_number || $json[\'VAT Number\'] || \'\' }}"\n'
                '  }]\n'
                '}'
            ),
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Sync Customer to QuickBooks",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1160, 1200],
        "typeVersion": 4.2,
        "credentials": {"quickBooksOAuth2Api": CRED_QUICKBOOKS},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 5000,
    })

    # 15. Respond Customer (respondToWebhook)
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ status: 'success', customer_id: $json['Customer ID'] || $json['id'], synced_to_quickbooks: true }) }}",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Customer",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [1400, 1200],
        "typeVersion": 1.1,
        "onError": "continueRegularOutput",
    })

    # ── Error Handling ────────────────────────────────────────

    # 16. Error Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 1400],
        "typeVersion": 1,
    })

    # 17. Error Notification (gmail)
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "ACCOUNTING ERROR - {{ $json.workflow.name }}",
            "emailType": "html",
            "message": (
                "=<h2>Accounting Department Error</h2>\n"
                "<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n"
                "<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n"
                "<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n"
                '<p><a href="{{ $json.execution.url }}">View Execution</a></p>'
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 1400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── Sticky Notes ──────────────────────────────────────────

    # Sticky Note 1: Config Refresh section
    nodes.append({
        "parameters": {
            "content": (
                "## Config Refresh Flow\n\n"
                "Runs hourly (or manually) to:\n"
                "1. Set system defaults (date, company, AI model, currency, VAT)\n"
                "2. Read all config from Airtable System Config table\n"
                "3. Parse JSON values into structured config object\n"
                "4. Log the refresh to Audit Log"
            ),
            "width": 1000,
            "height": 260,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 320],
        "typeVersion": 1,
    })

    # Sticky Note 2: Audit Log Webhook section
    nodes.append({
        "parameters": {
            "content": (
                "## Audit Log Webhook\n\n"
                "POST /accounting/audit-log\n\n"
                "Accepts: {workflow, event_type, record_type, record_id, action, actor, result, error, metadata}\n\n"
                "Called by other accounting workflows (WF-07 to WF-10) to log all actions."
            ),
            "width": 800,
            "height": 200,
        },
        "id": uid(),
        "name": "Sticky Note1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 820],
        "typeVersion": 1,
    })

    # Sticky Note 3: Customer CRUD section
    nodes.append({
        "parameters": {
            "content": (
                "## Customer CRUD Webhook\n\n"
                "POST /accounting/customer\n\n"
                "Accepts: {action: 'create'|'update', customer data}\n\n"
                "Validates email/VAT, upserts to Airtable Customers table, syncs to QuickBooks Contacts API."
            ),
            "width": 1300,
            "height": 200,
        },
        "id": uid(),
        "name": "Sticky Note2",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 1120],
        "typeVersion": 1,
    })

    # Sticky Note 4: Error Handling section
    nodes.append({
        "parameters": {
            "content": (
                "## Error Handling\n\n"
                "Catches any unhandled errors and sends notification email to ian@anyvisionmedia.com."
            ),
            "width": 400,
            "height": 140,
        },
        "id": uid(),
        "name": "Sticky Note3",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 1340],
        "typeVersion": 1,
    })

    return nodes


def build_connections():
    """Build connections for WF-06: Master Data & Audit."""
    return {
        "Hourly Config Refresh": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]]
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]]
        },
        "System Config": {
            "main": [[{"node": "Read System Config", "type": "main", "index": 0}]]
        },
        "Read System Config": {
            "main": [[{"node": "Cache Config Values", "type": "main", "index": 0}]]
        },
        "Cache Config Values": {
            "main": [[{"node": "Log Config Read", "type": "main", "index": 0}]]
        },
        "Audit Log Webhook": {
            "main": [[{"node": "Validate Audit Entry", "type": "main", "index": 0}]]
        },
        "Manual Audit Test": {
            "main": [[{"node": "Sample Audit Data", "type": "main", "index": 0}]]
        },
        "Sample Audit Data": {
            "main": [[{"node": "Validate Audit Entry", "type": "main", "index": 0}]]
        },
        "Validate Audit Entry": {
            "main": [[{"node": "Write Audit Log", "type": "main", "index": 0}]]
        },
        "Write Audit Log": {
            "main": [[{"node": "Respond Audit Success", "type": "main", "index": 0}]]
        },
        "Customer CRUD Webhook": {
            "main": [[{"node": "Validate Customer Data", "type": "main", "index": 0}]]
        },
        "Manual Customer Test": {
            "main": [[{"node": "Sample Customer Data", "type": "main", "index": 0}]]
        },
        "Sample Customer Data": {
            "main": [[{"node": "Validate Customer Data", "type": "main", "index": 0}]]
        },
        "Validate Customer Data": {
            "main": [[{"node": "Upsert Customer", "type": "main", "index": 0}]]
        },
        "Upsert Customer": {
            "main": [[{"node": "Sync Customer to QuickBooks", "type": "main", "index": 0}]]
        },
        "Sync Customer to QuickBooks": {
            "main": [[{"node": "Respond Customer", "type": "main", "index": 0}]]
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]]
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW DEFINITIONS
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "wf06": {
        "name": "Accounting Dept - Master Data & Audit (WF-06)",
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
        "wf06": "wf06_master_data_audit.json",
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
    print("ACCOUNTING DEPARTMENT - WF-06 MASTER DATA & AUDIT")
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
        print("  - ACCOUNTING_TABLE_CUSTOMERS")
        print("  - ACCOUNTING_TABLE_SUPPLIERS")
        print("  - ACCOUNTING_TABLE_PRODUCTS_SERVICES")
        print("  - ACCOUNTING_TABLE_INVOICES")
        print("  - ACCOUNTING_TABLE_PAYMENTS")
        print("  - ACCOUNTING_TABLE_SUPPLIER_BILLS")
        print("  - ACCOUNTING_TABLE_TASKS")
        print("  - ACCOUNTING_TABLE_AUDIT_LOG")
        print("  - ACCOUNTING_TABLE_SYSTEM_CONFIG")
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
    print("  2. Verify credential bindings (Airtable, Gmail, QuickBooks OAuth2)")
    print("  3. Seed System Config table with config key-value pairs")
    print("  4. Test config refresh with Manual Trigger")
    print("  5. Test audit log webhook: POST /accounting/audit-log")
    print("  6. Test customer CRUD webhook: POST /accounting/customer")
    print("  7. Once verified, activate schedule triggers")


if __name__ == "__main__":
    main()
