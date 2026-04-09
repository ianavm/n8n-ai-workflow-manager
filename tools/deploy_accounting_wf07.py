"""
Accounting Department - Exception Handler (WF-07) Builder & Deployer

Builds the Exception Handler workflow that handles:
- Polling open tasks every 15 minutes during business hours
- Detecting overdue tasks and escalating them
- Webhook-based approval/rejection flow with token validation
- HTML response pages for approval confirmations
- Task lifecycle management (Open -> In Progress -> Escalated -> Completed)
- Audit logging of all approval actions

Usage:
    python tools/deploy_accounting_wf07.py build
    python tools/deploy_accounting_wf07.py deploy
    python tools/deploy_accounting_wf07.py activate
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
CRED_GOOGLE_SHEETS = {"id": "OkpDXxwI8WcUJp4P", "name": "Google Sheets account"}

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
# WF-07: EXCEPTION HANDLER
# ══════════════════════════════════════════════════════════════

def build_nodes():
    """Build all 24 nodes for the Exception Handler workflow."""
    nodes = []

    # ── 1. Task Poll Schedule (scheduleTrigger) ──

    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {"field": "cronExpression", "expression": "*/15 8-17 * * 1-5"}
                ]
            }
        },
        "id": uid(),
        "name": "Task Poll Schedule",
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

    # ── 3. Approval Webhook (webhook) ──

    nodes.append({
        "parameters": {
            "httpMethod": "GET",
            "path": "accounting/approve",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Approval Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 1200],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # ── 3b. Manual Approval Test Trigger ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Approval Test",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 1400],
        "typeVersion": 1,
    })

    # ── 3c. Sample Approval Data (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "// Simulates a webhook GET request with query params\n"
                "// Change token to match an actual Task's Approval Token in Airtable\n"
                "return {\n"
                "  json: {\n"
                "    query: {\n"
                "      token: 'test-token-' + Date.now(),\n"
                "      action: 'approve'\n"
                "    }\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Sample Approval Data",
        "type": "n8n-nodes-base.code",
        "position": [460, 1400],
        "typeVersion": 2,
    })

    # ── 4. System Config (set) ──

    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.toFormat('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                    {"id": uid(), "name": "aiModel", "value": "anthropic/claude-sonnet-4-20250514", "type": "string"},
                    {"id": uid(), "name": "defaultCurrency", "value": "ZAR", "type": "string"},
                    {"id": uid(), "name": "escalationEmail", "value": "ian@anyvisionmedia.com", "type": "string"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [460, 500],
        "typeVersion": 3.4,
    })

    # ── 5. Read Open Tasks (airtable search) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "filterByFormula": "OR({Status} = 'Open', {Status} = 'In Progress', {Status} = 'Escalated')",
        },
        "id": uid(),
        "name": "Read Open Tasks",
        "type": "n8n-nodes-base.airtable",
        "position": [700, 500],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 6. Has Tasks? (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $input.all().length }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Has Tasks?",
        "type": "n8n-nodes-base.if",
        "position": [940, 500],
        "typeVersion": 2,
    })

    # ── 7. Loop Over Tasks (splitInBatches) ──

    nodes.append({
        "parameters": {"batchSize": 1, "options": {}},
        "id": uid(),
        "name": "Loop Over Tasks",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1200, 400],
        "typeVersion": 3,
    })

    # ── 8. Check Overdue (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const task = $input.first().json;\n"
                "const now = new Date();\n"
                "const dueAt = task['Due At'] || task['Due Date'] || '';\n"
                "\n"
                "let isOverdue = false;\n"
                "let daysPastDue = 0;\n"
                "\n"
                "if (dueAt) {\n"
                "  const dueDate = new Date(dueAt);\n"
                "  if (!isNaN(dueDate.getTime())) {\n"
                "    isOverdue = now > dueDate;\n"
                "    daysPastDue = isOverdue ? Math.floor((now - dueDate) / 86400000) : 0;\n"
                "  }\n"
                "}\n"
                "\n"
                "// Only escalate if not already escalated\n"
                "const shouldEscalate = isOverdue && task['Status'] !== 'Escalated';\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...task,\n"
                "    isOverdue: isOverdue,\n"
                "    shouldEscalate: shouldEscalate,\n"
                "    daysPastDue: daysPastDue,\n"
                "    taskId: task['Task ID'] || '',\n"
                "    airtableRecordId: task['id'] || '',\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Check Overdue",
        "type": "n8n-nodes-base.code",
        "position": [1460, 400],
        "typeVersion": 2,
    })

    # ── 9. Is Overdue? (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.shouldEscalate }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Is Overdue?",
        "type": "n8n-nodes-base.if",
        "position": [1700, 400],
        "typeVersion": 2,
    })

    # ── 10. Escalate Task (airtable update) ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Task ID": "={{ $json['Task ID'] }}",
                    "Status": "Escalated",
                    "Priority": "Urgent",
                    "Resolution Notes": "=Auto-escalated: {{ $json.daysPastDue }} days past due at {{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}",
                },
                "matchingColumns": ["Task ID"],
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Escalate Task",
        "type": "n8n-nodes-base.airtable",
        "position": [1960, 300],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 11. Send Escalation Email (gmail) ──

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=ESCALATION: Overdue Task - {{ $json['Task Type'] || $json['Description'] || 'Unknown' }}",
            "emailType": "html",
            "message": (
                "=<h2 style='color:#ef4444;'>Task Escalation Notice</h2>"
                "<p>The following task has been automatically escalated due to being overdue.</p>"
                "<table style='border-collapse:collapse;width:100%;max-width:500px;'>"
                "<tr><td style='padding:8px;border:1px solid #ddd;background:#f8f8f8;'><strong>Task Type</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>{{ $json['Task Type'] || 'N/A' }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;background:#f8f8f8;'><strong>Description</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>{{ $json['Description'] || 'N/A' }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;background:#f8f8f8;'><strong>Priority</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;color:#ef4444;font-weight:bold;'>Urgent (Escalated)</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;background:#f8f8f8;'><strong>Due Date</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>{{ $json['Due At'] || $json['Due Date'] || 'N/A' }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;background:#f8f8f8;'><strong>Days Overdue</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;color:#ef4444;'>{{ $json.daysPastDue }} days</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;background:#f8f8f8;'><strong>Related Record</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>{{ $json['Related Invoice'] || $json['Related Bill'] || 'N/A' }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;background:#f8f8f8;'><strong>Assigned To</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;'>{{ $json['Assigned To'] || 'Unassigned' }}</td></tr>"
                "</table>"
                "<br>"
                "<p>Please review and take action on this task immediately.</p>"
                "<p style='font-size:11px;color:#999;'>AnyVision Media Accounting System</p>"
            ),
            "options": {
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Send Escalation Email",
        "type": "n8n-nodes-base.gmail",
        "position": [2220, 300],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── 12. Process Webhook Approval (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const query = $input.first().json.query || $input.first().json;\n"
                "const token = query.token || '';\n"
                "const action = query.action || '';\n"
                "\n"
                "if (!token || !action) {\n"
                "  return { json: { isValid: false, error: 'Missing token or action parameter' } };\n"
                "}\n"
                "\n"
                "if (!['approve', 'reject'].includes(action)) {\n"
                "  return { json: { isValid: false, error: 'Invalid action. Must be approve or reject.' } };\n"
                "}\n"
                "\n"
                "return { json: { isValid: true, token, action } };\n"
            ),
        },
        "id": uid(),
        "name": "Process Webhook Approval",
        "type": "n8n-nodes-base.code",
        "position": [460, 1200],
        "typeVersion": 2,
    })

    # ── 13. Token Valid? (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.isValid }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Token Valid?",
        "type": "n8n-nodes-base.if",
        "position": [700, 1200],
        "typeVersion": 2,
    })

    # ── 14. Respond Invalid Token (respondToWebhook) ──

    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": (
                "={{ JSON.stringify({"
                "  html: '<!DOCTYPE html><html><head><meta charset=utf-8>"
                "<style>body{font-family:Segoe UI,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f4f4f4;}"
                ".card{background:#fff;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);text-align:center;max-width:400px;}"
                "h1{color:#ef4444;margin:0 0 8px;}"
                "p{color:#666;margin:0;}</style></head>"
                "<body><div class=card>"
                "<h1>Invalid Request</h1>"
                "<p>' + ($json.error || 'The approval token is missing or invalid.') + '</p>"
                "<p style=margin-top:16px;font-size:12px;color:#999;>AnyVision Media Accounting</p>"
                "</div></body></html>'"
                "}) }}"
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Respond Invalid Token",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [960, 1600],
        "typeVersion": 1.1,
        "onError": "continueRegularOutput",
    })

    # ── 15. Lookup Task by Token (airtable search) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "filterByFormula": "={Approval Token} = '{{ $json.token }}'",
        },
        "id": uid(),
        "name": "Lookup Task by Token",
        "type": "n8n-nodes-base.airtable",
        "position": [960, 1100],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 16. Load Related Record (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const task = $input.first().json;\n"
                "const action = $('Process Webhook Approval').first().json.action;\n"
                "const token = $('Process Webhook Approval').first().json.token;\n"
                "\n"
                "if (!task || !task['Type']) {\n"
                "  return {\n"
                "    json: {\n"
                "      error: 'Task not found for the provided token',\n"
                "      token: token,\n"
                "      action: action,\n"
                "      routeKey: 'not_found',\n"
                "    }\n"
                "  };\n"
                "}\n"
                "\n"
                "const taskType = task['Type'] || '';\n"
                "let routeKey = 'reject';\n"
                "\n"
                "if (action === 'approve') {\n"
                "  if (taskType.toLowerCase().includes('invoice')) {\n"
                "    routeKey = 'approve_invoice';\n"
                "  } else if (taskType.toLowerCase().includes('bill')) {\n"
                "    routeKey = 'approve_bill';\n"
                "  } else {\n"
                "    routeKey = 'approve_invoice'; // default approval\n"
                "  }\n"
                "} else {\n"
                "  routeKey = 'reject';\n"
                "}\n"
                "\n"
                "// Determine related record ID and table\n"
                "let relatedRecordId = '';\n"
                "let relatedTable = 'Invoices';\n"
                "if (routeKey === 'approve_bill') {\n"
                "  relatedRecordId = task['Related Record ID'] || '';\n"
                "  relatedTable = 'Supplier Bills';\n"
                "} else {\n"
                "  relatedRecordId = task['Related Record ID'] || '';\n"
                "  relatedTable = 'Invoices';\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...task,\n"
                "    action: action,\n"
                "    token: token,\n"
                "    routeKey: routeKey,\n"
                "    taskId: task['Task ID'] || '',\n"
                "    airtableRecordId: task['id'] || '',\n"
                "    relatedInvoice: task['Related Invoice'] || '',\n"
                "    relatedBill: task['Related Bill'] || '',\n"
                "    relatedRecordId: relatedRecordId,\n"
                "    relatedTable: relatedTable,\n"
                "    taskDescription: task['Description'] || '',\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Load Related Record",
        "type": "n8n-nodes-base.code",
        "position": [1220, 1100],
        "typeVersion": 2,
    })

    # ── 17. Apply Decision Router (switch) ──

    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "outputKey": "approve_invoice",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.routeKey }}",
                                    "rightValue": "approve_invoice",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                    },
                    {
                        "outputKey": "approve_bill",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.routeKey }}",
                                    "rightValue": "approve_bill",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                    },
                    {
                        "outputKey": "reject",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.routeKey }}",
                                    "rightValue": "reject",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                    },
                ],
            },
            "options": {
                "fallbackOutput": "extra",
            },
        },
        "id": uid(),
        "name": "Apply Decision Router",
        "type": "n8n-nodes-base.switch",
        "position": [1480, 1100],
        "typeVersion": 3.2,
    })

    # ── 18. Execute Approval (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const data = $input.first().json;\n"
                "const action = data.action;\n"
                "const isApprove = action === 'approve';\n"
                "\n"
                "// Determine new status for the related record\n"
                "let newStatus = 'Rejected';\n"
                "if (isApprove) {\n"
                "  newStatus = 'Approved';\n"
                "}\n"
                "\n"
                "// Build the response HTML\n"
                "const html = `<!DOCTYPE html><html><head><meta charset=\"utf-8\">\n"
                "<style>body{font-family:'Segoe UI',sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f4f4f4;}\n"
                ".card{background:#fff;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);text-align:center;max-width:400px;}\n"
                ".icon{font-size:48px;margin-bottom:16px;}\n"
                "h1{color:${isApprove ? '#22c55e' : '#ef4444'};margin:0 0 8px;}\n"
                "p{color:#666;margin:0;}</style></head>\n"
                "<body><div class=\"card\">\n"
                "<div class=\"icon\">${isApprove ? '&#10004;' : '&#10006;'}</div>\n"
                "<h1>${isApprove ? 'Approved' : 'Rejected'}</h1>\n"
                "<p>${data.taskDescription || 'The record has been ' + action + 'd successfully.'}</p>\n"
                "<p style=\"margin-top:16px;font-size:12px;color:#999;\">AnyVision Media Accounting</p>\n"
                "</div></body></html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...data,\n"
                "    newStatus: newStatus,\n"
                "    responseHtml: html,\n"
                "    processedAt: new Date().toISOString(),\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Execute Approval",
        "type": "n8n-nodes-base.code",
        "position": [1740, 1100],
        "typeVersion": 2,
    })

    # ── 18b. Is Bill? (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.relatedTable }}",
                        "rightValue": "Supplier Bills",
                        "operator": {"type": "string", "operation": "equals"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Is Bill?",
        "type": "n8n-nodes-base.if",
        "position": [1870, 1100],
        "typeVersion": 2,
    })

    # ── 19. Update Invoice Record (airtable update) ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Invoice ID": "={{ $json.relatedRecordId }}",
                    "Status": "={{ $json.newStatus === 'Approved' ? 'Sent' : 'Cancelled' }}",
                },
                "matchingColumns": ["Invoice ID"],
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Invoice Record",
        "type": "n8n-nodes-base.airtable",
        "position": [2000, 1000],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── 19b. Update Bill Record (airtable update) ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIER_BILLS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Bill ID": "={{ $json.relatedRecordId }}",
                    "Approval Status": "={{ $json.newStatus }}",
                    "Approver": "ian@anyvisionmedia.com",
                    "Approved At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "matchingColumns": ["Bill ID"],
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Bill Record",
        "type": "n8n-nodes-base.airtable",
        "position": [2000, 1200],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── 20. Complete Task (airtable update) ──

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Task ID": "={{ $('Execute Approval').first().json.taskId }}",
                    "Status": "Completed",
                    "Completed At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                    "Resolution Notes": "={{ $('Execute Approval').first().json.action === 'approve' ? 'Approved' : 'Rejected' }} via webhook",
                },
                "matchingColumns": ["Task ID"],
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Complete Task",
        "type": "n8n-nodes-base.airtable",
        "position": [2260, 1100],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # ── 21. Respond Approval HTML (respondToWebhook) ──

    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ status: $('Execute Approval').first().json.action, message: $('Execute Approval').first().json.action === 'approve' ? 'Record approved successfully' : 'Record rejected', processedAt: $('Execute Approval').first().json.processedAt }) }}",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Approval HTML",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [2780, 1100],
        "typeVersion": 1.1,
        "onError": "continueRegularOutput",
    })

    # ── 22. Write Audit Log (airtable create) ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Timestamp": "={{ $now.toISO() }}",
                    "Workflow Name": "WF-07 Exception Handler",
                    "Event Type": "={{ $('Execute Approval').first().json.action === 'approve' ? 'BILL_APPROVED' : 'EXCEPTION' }}",
                    "Record Type": "Task",
                    "Record ID": "={{ $('Execute Approval').first().json.taskId || '' }}",
                    "Action Taken": "=Task {{ $('Execute Approval').first().json.action }}d. Related: {{ $('Execute Approval').first().json.relatedRecordId || 'N/A' }}",
                    "Actor": "ian@anyvisionmedia.com",
                    "Result": "Success",
                    "Error Details": "",
                    "Metadata JSON": "={{ JSON.stringify({ token: $('Execute Approval').first().json.token, action: $('Execute Approval').first().json.action, newStatus: $('Execute Approval').first().json.newStatus, processedAt: $('Execute Approval').first().json.processedAt }) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Audit Log",
        "type": "n8n-nodes-base.airtable",
        "position": [2520, 1100],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 23. Error Trigger ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 1600],
        "typeVersion": 1,
    })

    # ── 24. Error Notification (gmail) ──

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=ERROR: Accounting WF-07 Exception Handler - {{ $now.toFormat('yyyy-MM-dd HH:mm') }}",
            "emailType": "html",
            "message": (
                "=<h2 style='color:#FF6D5A;'>Workflow Error: Exception Handler (WF-07)</h2>"
                "<p><strong>Time:</strong> {{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}</p>"
                "<p><strong>Error:</strong> {{ $json.execution?.error?.message || 'Unknown error' }}</p>"
                "<p><strong>Node:</strong> {{ $json.execution?.lastNodeExecuted || 'Unknown' }}</p>"
                "<p><strong>Execution ID:</strong> {{ $json.execution?.id || 'N/A' }}</p>"
                "<hr>"
                "<p>The exception handler encountered an error. Task polling and approval processing may be affected.</p>"
                "<p>Please check the n8n execution log for details.</p>"
                "<p style='font-size:11px;color:#999;'>AnyVision Media Accounting System</p>"
            ),
            "options": {
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [460, 1600],
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_connections():
    """Build connections for the Exception Handler workflow."""
    return {
        # ── Task Poll Flow ──
        "Task Poll Schedule": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Read Open Tasks", "type": "main", "index": 0}]],
        },
        "Read Open Tasks": {
            "main": [[{"node": "Has Tasks?", "type": "main", "index": 0}]],
        },
        "Has Tasks?": {
            "main": [
                # True branch: process tasks
                [{"node": "Loop Over Tasks", "type": "main", "index": 0}],
                # False branch: do nothing
                [],
            ],
        },
        "Loop Over Tasks": {
            "main": [
                # Done branch (all batches processed) - no further action
                [],
                # Each batch
                [{"node": "Check Overdue", "type": "main", "index": 0}],
            ],
        },
        "Check Overdue": {
            "main": [[{"node": "Is Overdue?", "type": "main", "index": 0}]],
        },
        "Is Overdue?": {
            "main": [
                # True branch: escalate
                [{"node": "Escalate Task", "type": "main", "index": 0}],
                # False branch: skip back to loop
                [{"node": "Loop Over Tasks", "type": "main", "index": 0}],
            ],
        },
        "Escalate Task": {
            "main": [[{"node": "Send Escalation Email", "type": "main", "index": 0}]],
        },
        "Send Escalation Email": {
            "main": [[{"node": "Loop Over Tasks", "type": "main", "index": 0}]],
        },

        # ── Approval Webhook Flow ──
        "Approval Webhook": {
            "main": [[{"node": "Process Webhook Approval", "type": "main", "index": 0}]],
        },
        "Manual Approval Test": {
            "main": [[{"node": "Sample Approval Data", "type": "main", "index": 0}]],
        },
        "Sample Approval Data": {
            "main": [[{"node": "Process Webhook Approval", "type": "main", "index": 0}]],
        },
        "Process Webhook Approval": {
            "main": [[{"node": "Token Valid?", "type": "main", "index": 0}]],
        },
        "Token Valid?": {
            "main": [
                # True branch: lookup task
                [{"node": "Lookup Task by Token", "type": "main", "index": 0}],
                # False branch: respond with error
                [{"node": "Respond Invalid Token", "type": "main", "index": 0}],
            ],
        },
        "Lookup Task by Token": {
            "main": [[{"node": "Load Related Record", "type": "main", "index": 0}]],
        },
        "Load Related Record": {
            "main": [[{"node": "Apply Decision Router", "type": "main", "index": 0}]],
        },
        "Apply Decision Router": {
            "main": [
                # Output 0: approve_invoice
                [{"node": "Execute Approval", "type": "main", "index": 0}],
                # Output 1: approve_bill
                [{"node": "Execute Approval", "type": "main", "index": 0}],
                # Output 2: reject
                [{"node": "Execute Approval", "type": "main", "index": 0}],
                # Output 3: fallback (not_found) -> respond with error
                [{"node": "Respond Invalid Token", "type": "main", "index": 0}],
            ],
        },
        "Execute Approval": {
            "main": [[{"node": "Is Bill?", "type": "main", "index": 0}]],
        },
        "Is Bill?": {
            "main": [
                # True branch: update supplier bills table
                [{"node": "Update Bill Record", "type": "main", "index": 0}],
                # False branch: update invoices table
                [{"node": "Update Invoice Record", "type": "main", "index": 0}],
            ],
        },
        "Update Invoice Record": {
            "main": [[{"node": "Complete Task", "type": "main", "index": 0}]],
        },
        "Update Bill Record": {
            "main": [[{"node": "Complete Task", "type": "main", "index": 0}]],
        },
        "Complete Task": {
            "main": [[{"node": "Write Audit Log", "type": "main", "index": 0}]],
        },
        "Write Audit Log": {
            "main": [[{"node": "Respond Approval HTML", "type": "main", "index": 0}]],
        },

        # ── Error Handling ──
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW DEFINITIONS
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "wf07": {
        "name": "Accounting Dept - Exception Handler (WF-07)",
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
        "wf07": "wf07_exception_handling.json",
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
    print("ACCOUNTING DEPARTMENT - WF-07 EXCEPTION HANDLER")
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

    # Check QuickBooks credential config
    if "REPLACE" in CRED_QUICKBOOKS["id"]:
        print("WARNING: QuickBooks credential ID not configured!")
        print("  Set ACCOUNTING_QBO_CRED_ID in .env")
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
    print("  2. Verify credential bindings (Airtable, Gmail)")
    print("  3. Create test tasks in Airtable Tasks table with Approval Tokens")
    print("  4. Test task polling with Manual Trigger")
    print("  5. Test approval webhook: GET /accounting/approve?token=XXX&action=approve")
    print("  6. Test rejection webhook: GET /accounting/approve?token=XXX&action=reject")
    print("  7. Test invalid token: GET /accounting/approve?token=INVALID&action=approve")
    print("  8. Verify escalation emails are sent for overdue tasks")
    print("  9. Once verified, activate the 15-minute poll schedule")


if __name__ == "__main__":
    main()
