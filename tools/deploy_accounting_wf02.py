"""
Accounting Department - Collections & Follow-ups (WF-02) Builder & Deployer

Handles:
- Daily overdue invoice checking
- 5-stage reminder cadence (T-3, Due, T+3, T+7, T+14)
- Multi-channel reminders (Gmail + WhatsApp)
- Dispute handling via webhook
- Escalation to management
- Audit logging

Usage:
    python tools/deploy_accounting_wf02.py build
    python tools/deploy_accounting_wf02.py deploy
    python tools/deploy_accounting_wf02.py activate
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

sys.path.insert(0, str(Path(__file__).parent))
from credentials import CREDENTIALS

CRED_OPENROUTER = CREDENTIALS["openrouter"]
CRED_GMAIL = CREDENTIALS["gmail"]
CRED_AIRTABLE = CREDENTIALS["airtable"]
CRED_WHATSAPP_SEND = CREDENTIALS["whatsapp_send"]

AIRTABLE_BASE_ID = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
TABLE_INVOICES = os.getenv("ACCOUNTING_TABLE_INVOICES", "REPLACE_WITH_TABLE_ID")
TABLE_CUSTOMERS = os.getenv("ACCOUNTING_TABLE_CUSTOMERS", "REPLACE_WITH_TABLE_ID")
TABLE_TASKS = os.getenv("ACCOUNTING_TABLE_TASKS", "REPLACE_WITH_TABLE_ID")
TABLE_AUDIT_LOG = os.getenv("ACCOUNTING_TABLE_AUDIT_LOG", "REPLACE_WITH_TABLE_ID")

# Validate required environment variables
_required_vars = {
    "ACCOUNTING_AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
    "ACCOUNTING_TABLE_INVOICES": TABLE_INVOICES,
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
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════
# WF-02: COLLECTIONS & FOLLOW-UPS
# ══════════════════════════════════════════════════════════════

def build_nodes():
    """Build all nodes for WF-02: Collections & Follow-ups."""

    nodes = []

    # ── Trigger Nodes ─────────────────────────────────────────

    # 1. Daily 7AM Trigger (scheduleTrigger)
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {"field": "cronExpression", "expression": "0 7 * * *"}
                ]
            }
        },
        "id": uid(),
        "name": "Daily 7AM Trigger",
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

    # ── System Config ─────────────────────────────────────────

    # 3. System Config (set)
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
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 500],
        "typeVersion": 3.4,
    })

    # ── Invoice Retrieval ─────────────────────────────────────

    # 4. Read Open Invoices (airtable search)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "filterByFormula": "OR({Status}='Sent', {Status}='Partial', {Status}='Overdue')",
        },
        "id": uid(),
        "name": "Read Open Invoices",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 500],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 5. Has Invoices? (if)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.id }}",
                        "rightValue": "",
                        "operator": {
                            "type": "string",
                            "operation": "exists",
                            "singleValue": True,
                        },
                    },
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Has Invoices?",
        "type": "n8n-nodes-base.if",
        "position": [920, 500],
        "typeVersion": 2.2,
    })

    # 6. Loop Over Invoices (splitInBatches)
    nodes.append({
        "parameters": {
            "batchSize": 1,
            "options": {},
        },
        "id": uid(),
        "name": "Loop Over Invoices",
        "type": "n8n-nodes-base.splitInBatches",
        "position": [1160, 400],
        "typeVersion": 3,
    })

    # ── Customer Lookup & Stage Determination ─────────────────

    # 7. Lookup Customer (airtable search)
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
        "position": [1400, 500],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 8. Determine Reminder Stage (code)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const invoice = $input.first().json;\n"
                "const customer = $('Lookup Customer').first().json;\n"
                "\n"
                "const today = new Date();\n"
                "today.setHours(0, 0, 0, 0);\n"
                "\n"
                "const dueDate = new Date(invoice['Due Date']);\n"
                "dueDate.setHours(0, 0, 0, 0);\n"
                "\n"
                "const daysDiff = Math.floor((today - dueDate) / (1000 * 60 * 60 * 24));\n"
                "const nextReminder = invoice['Next Reminder Date'] ? new Date(invoice['Next Reminder Date']) : null;\n"
                "\n"
                "let reminderStage = 'no_action';\n"
                "let reminderTone = '';\n"
                "\n"
                "if (nextReminder && nextReminder > today) {\n"
                "  reminderStage = 'no_action';\n"
                "} else if (daysDiff <= -3 && daysDiff > -4) {\n"
                "  reminderStage = 't_minus_3';\n"
                "  reminderTone = 'friendly';\n"
                "} else if (daysDiff >= -1 && daysDiff <= 1) {\n"
                "  reminderStage = 'due_date';\n"
                "  reminderTone = 'reminder';\n"
                "} else if (daysDiff >= 2 && daysDiff <= 5) {\n"
                "  reminderStage = 't_plus_3';\n"
                "  reminderTone = 'firm';\n"
                "} else if (daysDiff >= 6 && daysDiff <= 10) {\n"
                "  reminderStage = 't_plus_7';\n"
                "  reminderTone = 'collections';\n"
                "} else if (daysDiff >= 11) {\n"
                "  reminderStage = 't_plus_14';\n"
                "  reminderTone = 'escalation';\n"
                "}\n"
                "\n"
                "// If already reminded at this stage, skip\n"
                "const reminderCount = parseInt(invoice['Reminder Count'] || '0');\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...invoice,\n"
                "    customerName: customer['Legal Name'] || customer['Trading Name'] || '',\n"
                "    customerEmail: customer['Email'] || '',\n"
                "    customerPhone: customer['Phone'] || '',\n"
                "    preferredChannel: customer['Preferred Channel'] || 'Email',\n"
                "    riskFlag: customer['Risk Flag'] || 'Low',\n"
                "    reminderStage: reminderStage,\n"
                "    reminderTone: reminderTone,\n"
                "    daysPastDue: daysDiff,\n"
                "    dueDate: invoice['Due Date'],\n"
                "    invoiceNumber: invoice['Invoice Number'],\n"
                "    total: invoice['Total'],\n"
                "    balanceDue: invoice['Balance Due'] || invoice['Total'],\n"
                "    reminderCount: reminderCount,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Determine Reminder Stage",
        "type": "n8n-nodes-base.code",
        "position": [1640, 500],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 9. Needs Reminder? (if)
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.reminderStage }}",
                        "rightValue": "no_action",
                        "operator": {
                            "type": "string",
                            "operation": "notEquals",
                        },
                    },
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Needs Reminder?",
        "type": "n8n-nodes-base.if",
        "position": [1880, 500],
        "typeVersion": 2.2,
    })

    # 10. Reminder Stage Router (switch)
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "outputKey": "t_minus_3",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.reminderStage }}",
                                    "rightValue": "t_minus_3",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                    },
                    {
                        "outputKey": "due_date",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.reminderStage }}",
                                    "rightValue": "due_date",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                    },
                    {
                        "outputKey": "t_plus_3",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.reminderStage }}",
                                    "rightValue": "t_plus_3",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                    },
                    {
                        "outputKey": "t_plus_7",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.reminderStage }}",
                                    "rightValue": "t_plus_7",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                    },
                    {
                        "outputKey": "t_plus_14",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.reminderStage }}",
                                    "rightValue": "t_plus_14",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ]
                        },
                    },
                ],
            },
            "options": {"fallbackOutput": "extra"},
        },
        "id": uid(),
        "name": "Reminder Stage Router",
        "type": "n8n-nodes-base.switch",
        "position": [2120, 500],
        "typeVersion": 3.2,
    })

    # ── Reminder Builder Nodes ────────────────────────────────

    # 11. Build Friendly Reminder (T-3)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const inv = $input.first().json;\n"
                "\n"
                "const html = `<!DOCTYPE html>\n"
                "<html><head><meta charset=\"utf-8\"></head>\n"
                "<body style=\"margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f4;\">\n"
                "  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;margin:0 auto;background-color:#ffffff;\">\n"
                "    <tr><td style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">\n"
                "      <h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">AnyVision Media</h1>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:30px 40px;\">\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Hi ${inv.customerName},</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Just a friendly heads up that invoice <strong>${inv.invoiceNumber}</strong> for <strong>R ${parseFloat(inv.balanceDue).toFixed(2)}</strong> is due on <strong>${inv.dueDate}</strong>.</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">If you've already arranged payment, please disregard this message.</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Need to discuss payment options? Just reply to this email.</p>\n"
                "      <p style=\"margin:24px 0 0;font-size:15px;color:#333;\">Best regards,<br><strong>AnyVision Media</strong><br><span style=\"color:#666;\">Accounts Department</span></p>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;\">\n"
                "      <p style=\"margin:0;font-size:11px;color:#999;\">AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com</p>\n"
                "    </td></tr>\n"
                "  </table>\n"
                "</body></html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...inv,\n"
                "    emailHtml: html,\n"
                "    emailSubject: `Upcoming: Invoice ${inv.invoiceNumber} due ${inv.dueDate}`,\n"
                "    whatsappMessage: `Hi ${inv.customerName}, friendly reminder that invoice ${inv.invoiceNumber} for R ${parseFloat(inv.balanceDue).toFixed(2)} is due on ${inv.dueDate}. Please disregard if already paid.`,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Friendly Reminder",
        "type": "n8n-nodes-base.code",
        "position": [2400, 200],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 12. Build Due Date Reminder (T+0)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const inv = $input.first().json;\n"
                "\n"
                "const html = `<!DOCTYPE html>\n"
                "<html><head><meta charset=\"utf-8\"></head>\n"
                "<body style=\"margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f4;\">\n"
                "  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;margin:0 auto;background-color:#ffffff;\">\n"
                "    <tr><td style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">\n"
                "      <h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">AnyVision Media</h1>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:30px 40px;\">\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Hi ${inv.customerName},</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">This is a reminder that invoice <strong>${inv.invoiceNumber}</strong> for <strong>R ${parseFloat(inv.balanceDue).toFixed(2)}</strong> is <strong>due today</strong> (${inv.dueDate}).</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Please arrange payment at your earliest convenience. If payment has already been made, kindly forward the proof of payment so we can update our records.</p>\n"
                "      <table cellpadding=\"0\" cellspacing=\"0\" style=\"margin:20px 0;\">\n"
                "        <tr><td style=\"padding:8px 16px;background-color:#f0f0f0;border-left:3px solid #FF6D5A;\">\n"
                "          <strong>Invoice:</strong> ${inv.invoiceNumber}<br>\n"
                "          <strong>Amount Due:</strong> R ${parseFloat(inv.balanceDue).toFixed(2)}<br>\n"
                "          <strong>Due Date:</strong> ${inv.dueDate}\n"
                "        </td></tr>\n"
                "      </table>\n"
                "      <p style=\"margin:24px 0 0;font-size:15px;color:#333;\">Kind regards,<br><strong>AnyVision Media</strong><br><span style=\"color:#666;\">Accounts Department</span></p>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;\">\n"
                "      <p style=\"margin:0;font-size:11px;color:#999;\">AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com</p>\n"
                "    </td></tr>\n"
                "  </table>\n"
                "</body></html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...inv,\n"
                "    emailHtml: html,\n"
                "    emailSubject: `Due Today: Invoice ${inv.invoiceNumber} - R ${parseFloat(inv.balanceDue).toFixed(2)}`,\n"
                "    whatsappMessage: `Hi ${inv.customerName}, invoice ${inv.invoiceNumber} for R ${parseFloat(inv.balanceDue).toFixed(2)} is due today (${inv.dueDate}). Please arrange payment or send proof if already paid. Thank you.`,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Due Date Reminder",
        "type": "n8n-nodes-base.code",
        "position": [2400, 400],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 13. Build Firm Reminder (T+3)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const inv = $input.first().json;\n"
                "\n"
                "const html = `<!DOCTYPE html>\n"
                "<html><head><meta charset=\"utf-8\"></head>\n"
                "<body style=\"margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f4;\">\n"
                "  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;margin:0 auto;background-color:#ffffff;\">\n"
                "    <tr><td style=\"padding:30px 40px 20px;border-bottom:3px solid #FF6D5A;\">\n"
                "      <h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">AnyVision Media</h1>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:30px 40px;\">\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Dear ${inv.customerName},</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Our records indicate that invoice <strong>${inv.invoiceNumber}</strong> for <strong>R ${parseFloat(inv.balanceDue).toFixed(2)}</strong> is now <strong>${Math.abs(inv.daysPastDue)} days overdue</strong>.</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">We understand that oversights happen, but we kindly request that you settle this outstanding amount as soon as possible.</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">If there are any issues with the invoice or if you require a payment arrangement, please contact us immediately so we can find a solution.</p>\n"
                "      <table cellpadding=\"0\" cellspacing=\"0\" style=\"margin:20px 0;\">\n"
                "        <tr><td style=\"padding:8px 16px;background-color:#fff3f0;border-left:3px solid #FF6D5A;\">\n"
                "          <strong>Invoice:</strong> ${inv.invoiceNumber}<br>\n"
                "          <strong>Amount Overdue:</strong> R ${parseFloat(inv.balanceDue).toFixed(2)}<br>\n"
                "          <strong>Due Date:</strong> ${inv.dueDate}<br>\n"
                "          <strong>Days Overdue:</strong> ${Math.abs(inv.daysPastDue)}\n"
                "        </td></tr>\n"
                "      </table>\n"
                "      <p style=\"margin:24px 0 0;font-size:15px;color:#333;\">Regards,<br><strong>AnyVision Media</strong><br><span style=\"color:#666;\">Accounts Department</span></p>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;\">\n"
                "      <p style=\"margin:0;font-size:11px;color:#999;\">AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com</p>\n"
                "    </td></tr>\n"
                "  </table>\n"
                "</body></html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...inv,\n"
                "    emailHtml: html,\n"
                "    emailSubject: `Overdue: Invoice ${inv.invoiceNumber} - ${Math.abs(inv.daysPastDue)} days past due`,\n"
                "    whatsappMessage: `Dear ${inv.customerName}, invoice ${inv.invoiceNumber} for R ${parseFloat(inv.balanceDue).toFixed(2)} is now ${Math.abs(inv.daysPastDue)} days overdue. Please arrange payment urgently or contact us to discuss. - AnyVision Media Accounts`,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Firm Reminder",
        "type": "n8n-nodes-base.code",
        "position": [2400, 600],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 14. Build Collections Notice (T+7)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const inv = $input.first().json;\n"
                "\n"
                "const html = `<!DOCTYPE html>\n"
                "<html><head><meta charset=\"utf-8\"></head>\n"
                "<body style=\"margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f4;\">\n"
                "  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;margin:0 auto;background-color:#ffffff;\">\n"
                "    <tr><td style=\"padding:30px 40px 20px;border-bottom:3px solid #cc0000;\">\n"
                "      <h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">AnyVision Media</h1>\n"
                "      <p style=\"margin:4px 0 0;font-size:12px;color:#cc0000;font-weight:bold;\">COLLECTIONS NOTICE</p>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:30px 40px;\">\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Dear ${inv.customerName},</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Despite previous reminders, invoice <strong>${inv.invoiceNumber}</strong> for <strong>R ${parseFloat(inv.balanceDue).toFixed(2)}</strong> remains unpaid and is now <strong>${Math.abs(inv.daysPastDue)} days overdue</strong>.</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">This invoice has been placed in our <strong>collections queue</strong>. To avoid further action, please make payment within the next 7 days.</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">If you are experiencing financial difficulties, we encourage you to contact us immediately to arrange a suitable payment plan.</p>\n"
                "      <table cellpadding=\"0\" cellspacing=\"0\" style=\"margin:20px 0;width:100%;\">\n"
                "        <tr><td style=\"padding:12px 16px;background-color:#fff0f0;border-left:4px solid #cc0000;\">\n"
                "          <strong>Invoice:</strong> ${inv.invoiceNumber}<br>\n"
                "          <strong>Amount Overdue:</strong> R ${parseFloat(inv.balanceDue).toFixed(2)}<br>\n"
                "          <strong>Original Due Date:</strong> ${inv.dueDate}<br>\n"
                "          <strong>Days Overdue:</strong> ${Math.abs(inv.daysPastDue)}<br>\n"
                "          <strong>Status:</strong> Collections Queue\n"
                "        </td></tr>\n"
                "      </table>\n"
                "      <p style=\"margin:24px 0 0;font-size:15px;color:#333;\">Regards,<br><strong>AnyVision Media</strong><br><span style=\"color:#666;\">Accounts Department</span></p>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;\">\n"
                "      <p style=\"margin:0;font-size:11px;color:#999;\">AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com</p>\n"
                "    </td></tr>\n"
                "  </table>\n"
                "</body></html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...inv,\n"
                "    emailHtml: html,\n"
                "    emailSubject: `COLLECTIONS: Invoice ${inv.invoiceNumber} - ${Math.abs(inv.daysPastDue)} days overdue`,\n"
                "    whatsappMessage: `COLLECTIONS NOTICE: ${inv.customerName}, invoice ${inv.invoiceNumber} for R ${parseFloat(inv.balanceDue).toFixed(2)} is ${Math.abs(inv.daysPastDue)} days overdue and has been placed in collections. Please contact us urgently. - AnyVision Media Accounts`,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Collections Notice",
        "type": "n8n-nodes-base.code",
        "position": [2400, 800],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 15. Build Escalation Notice (T+14)
    nodes.append({
        "parameters": {
            "jsCode": (
                "const inv = $input.first().json;\n"
                "\n"
                "const html = `<!DOCTYPE html>\n"
                "<html><head><meta charset=\"utf-8\"></head>\n"
                "<body style=\"margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f4;\">\n"
                "  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;margin:0 auto;background-color:#ffffff;\">\n"
                "    <tr><td style=\"padding:30px 40px 20px;border-bottom:3px solid #990000;\">\n"
                "      <h1 style=\"margin:0;font-size:22px;color:#1A1A2E;\">AnyVision Media</h1>\n"
                "      <p style=\"margin:4px 0 0;font-size:12px;color:#990000;font-weight:bold;\">FINAL NOTICE - MANAGEMENT ESCALATION</p>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:30px 40px;\">\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Dear ${inv.customerName},</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">This matter has been <strong>escalated to management</strong>. Invoice <strong>${inv.invoiceNumber}</strong> for <strong>R ${parseFloat(inv.balanceDue).toFixed(2)}</strong> is now <strong>${Math.abs(inv.daysPastDue)} days overdue</strong> and remains unpaid despite multiple reminders.</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">Please be advised that if payment is not received within <strong>7 days</strong> of this notice, we will be compelled to take <strong>further action</strong>, which may include suspending services, engaging a collections agency, or pursuing legal remedies.</p>\n"
                "      <p style=\"margin:0 0 16px;font-size:15px;color:#333;\">We strongly urge you to settle this account or contact us immediately to discuss a resolution.</p>\n"
                "      <table cellpadding=\"0\" cellspacing=\"0\" style=\"margin:20px 0;width:100%;\">\n"
                "        <tr><td style=\"padding:12px 16px;background-color:#ffe0e0;border-left:4px solid #990000;\">\n"
                "          <strong>Invoice:</strong> ${inv.invoiceNumber}<br>\n"
                "          <strong>Amount Overdue:</strong> R ${parseFloat(inv.balanceDue).toFixed(2)}<br>\n"
                "          <strong>Original Due Date:</strong> ${inv.dueDate}<br>\n"
                "          <strong>Days Overdue:</strong> ${Math.abs(inv.daysPastDue)}<br>\n"
                "          <strong>Status:</strong> Escalated to Management<br>\n"
                "          <strong>Reminders Sent:</strong> ${inv.reminderCount}\n"
                "        </td></tr>\n"
                "      </table>\n"
                "      <p style=\"margin:24px 0 0;font-size:15px;color:#333;\">Regards,<br><strong>AnyVision Media</strong><br><span style=\"color:#666;\">Management</span></p>\n"
                "    </td></tr>\n"
                "    <tr><td style=\"padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;\">\n"
                "      <p style=\"margin:0;font-size:11px;color:#999;\">AnyVision Media | Johannesburg, South Africa | accounts@anyvisionmedia.com</p>\n"
                "    </td></tr>\n"
                "  </table>\n"
                "</body></html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...inv,\n"
                "    emailHtml: html,\n"
                "    emailSubject: `FINAL NOTICE: Invoice ${inv.invoiceNumber} - Escalated to Management`,\n"
                "    emailCc: 'ian@anyvisionmedia.com',\n"
                "    whatsappMessage: `FINAL NOTICE: ${inv.customerName}, invoice ${inv.invoiceNumber} for R ${parseFloat(inv.balanceDue).toFixed(2)} is ${Math.abs(inv.daysPastDue)} days overdue. This has been escalated to management. Please contact us within 7 days to avoid further action. - AnyVision Media Management`,\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Escalation Notice",
        "type": "n8n-nodes-base.code",
        "position": [2400, 1000],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 16. Create Escalation Task (airtable create)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "columns": {
                "value": {
                    "Type": "Exception Review",
                    "Priority": "Urgent",
                    "Status": "Open",
                    "Description": "={{ 'Escalation: Invoice ' + $json.invoiceNumber + ' - ' + $json.customerName + '. R ' + $json.balanceDue + ' is ' + Math.abs($json.daysPastDue) + ' days overdue. ' + $json.reminderCount + ' reminders sent. Escalated to management.' }}",
                    "Related Record ID": "={{ $json.invoiceNumber }}",
                    "Related Table": "Invoices",
                    "Owner": "ian@anyvisionmedia.com",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [
                    {"id": "Type", "type": "string", "display": True, "displayName": "Type"},
                    {"id": "Priority", "type": "string", "display": True, "displayName": "Priority"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Description", "type": "string", "display": True, "displayName": "Description"},
                    {"id": "Related Record ID", "type": "string", "display": True, "displayName": "Related Record ID"},
                    {"id": "Related Table", "type": "string", "display": True, "displayName": "Related Table"},
                    {"id": "Owner", "type": "string", "display": True, "displayName": "Owner"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Escalation Task",
        "type": "n8n-nodes-base.airtable",
        "position": [2640, 1000],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Channel Routing & Sending ─────────────────────────────

    # 17. Check Channel Pref (if) - true = WhatsApp or Both, false = Email only
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": False, "leftValue": ""},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.preferredChannel }}",
                        "rightValue": "WhatsApp",
                        "operator": {
                            "type": "string",
                            "operation": "contains",
                        },
                    },
                ],
                "combinator": "or",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Check Channel Pref",
        "type": "n8n-nodes-base.if",
        "position": [2880, 500],
        "typeVersion": 2.2,
    })

    # 18. Send Reminder Email (gmail)
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.customerEmail }}",
            "subject": "={{ $json.emailSubject }}",
            "emailType": "html",
            "message": "={{ $json.emailHtml }}",
            "options": {
                "ccList": "={{ $json.emailCc || '' }}",
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Send Reminder Email",
        "type": "n8n-nodes-base.gmail",
        "position": [3120, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # 19. Send Reminder WhatsApp (httpRequest)
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
                '  "type": "text",\n'
                '  "text": {\n'
                '    "body": "{{ $json.whatsappMessage }}"\n'
                '  }\n'
                '}'
            ),
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Send Reminder WhatsApp",
        "type": "n8n-nodes-base.httpRequest",
        "position": [3120, 600],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_WHATSAPP_SEND},
        "onError": "continueRegularOutput",
    })

    # ── Invoice Updates ───────────────────────────────────────

    # 20. Update Invoice Reminder (airtable update)
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "columns": {
                "value": {
                    "Invoice ID": "={{ $('Determine Reminder Stage').first().json['Invoice ID'] }}",
                    "Reminder Count": "={{ parseInt($('Determine Reminder Stage').first().json.reminderCount || '0') + 1 }}",
                    "Last Reminder Date": "={{ $now.toFormat('yyyy-MM-dd') }}",
                    "Next Reminder Date": "={{ $now.plus(3, 'days').toFormat('yyyy-MM-dd') }}",
                    "Last Reminder Stage": "={{ $('Determine Reminder Stage').first().json.reminderStage }}",
                },
                "schema": [
                    {"id": "Invoice ID", "type": "string", "display": True, "displayName": "Invoice ID"},
                    {"id": "Reminder Count", "type": "number", "display": True, "displayName": "Reminder Count"},
                    {"id": "Last Reminder Date", "type": "string", "display": True, "displayName": "Last Reminder Date"},
                    {"id": "Next Reminder Date", "type": "string", "display": True, "displayName": "Next Reminder Date"},
                    {"id": "Last Reminder Stage", "type": "string", "display": True, "displayName": "Last Reminder Stage"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Invoice ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Invoice Reminder",
        "type": "n8n-nodes-base.airtable",
        "position": [3360, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 21. Update Invoice Status (airtable update) - set Overdue if past due
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "columns": {
                "value": {
                    "Invoice ID": "={{ $('Determine Reminder Stage').first().json['Invoice ID'] }}",
                    "Status": "Overdue",
                },
                "schema": [
                    {"id": "Invoice ID", "type": "string", "display": True, "displayName": "Invoice ID"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Invoice ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Invoice Status",
        "type": "n8n-nodes-base.airtable",
        "position": [2120, 800],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 22. Write Audit Log (airtable create) - REMINDER_SENT
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "columns": {
                "value": {
                    "Timestamp": "={{ $now.toISO() }}",
                    "Workflow Name": "WF-02 Collections & Follow-ups",
                    "Event Type": "REMINDER_SENT",
                    "Record Type": "Invoice",
                    "Record ID": "={{ $('Determine Reminder Stage').first().json.invoiceNumber }}",
                    "Action Taken": "={{ 'Sent ' + $('Determine Reminder Stage').first().json.reminderStage + ' reminder via ' + ($('Determine Reminder Stage').first().json.preferredChannel || 'Email') }}",
                    "Actor": "system",
                    "Result": "Success",
                    "Error Details": "",
                    "Metadata JSON": "={{ JSON.stringify({ stage: $('Determine Reminder Stage').first().json.reminderStage, tone: $('Determine Reminder Stage').first().json.reminderTone, daysPastDue: $('Determine Reminder Stage').first().json.daysPastDue, reminderCount: $('Determine Reminder Stage').first().json.reminderCount + 1, channel: $('Determine Reminder Stage').first().json.preferredChannel, customer: $('Determine Reminder Stage').first().json.customerName }) }}",
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
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Timestamp"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Audit Log",
        "type": "n8n-nodes-base.airtable",
        "position": [3600, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Dispute Handling Flow ─────────────────────────────────

    # 23. Dispute Webhook (webhook) - POST /accounting/dispute
    nodes.append({
        "parameters": {
            "path": "accounting/dispute",
            "httpMethod": "POST",
            "responseMode": "lastNode",
            "options": {},
        },
        "id": uid(),
        "name": "Dispute Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 1200],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # 23b. Dispute Auth Check
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
        "name": "Dispute Auth Check",
        "type": "n8n-nodes-base.code",
        "position": [400, 1200],
        "typeVersion": 2,
    })

    # 24. Handle Dispute (code) - parse dispute reason, assign owner
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "const body = input.body || input;\n"
                "\n"
                "const invoiceNumber = body.invoice_number || body.invoiceNumber || '';\n"
                "const reason = body.reason || body.dispute_reason || 'Not specified';\n"
                "const details = body.details || body.description || '';\n"
                "const customerName = body.customer_name || body.customerName || '';\n"
                "const customerEmail = body.customer_email || body.customerEmail || '';\n"
                "\n"
                "if (!invoiceNumber) {\n"
                "  throw new Error('Missing required field: invoice_number');\n"
                "}\n"
                "\n"
                "// Assign dispute owner based on reason category\n"
                "let disputeOwner = 'accounts@anyvisionmedia.com';\n"
                "let priority = 'Normal';\n"
                "\n"
                "const reasonLower = reason.toLowerCase();\n"
                "if (reasonLower.includes('overcharge') || reasonLower.includes('incorrect amount')) {\n"
                "  disputeOwner = 'accounts@anyvisionmedia.com';\n"
                "  priority = 'High';\n"
                "} else if (reasonLower.includes('service') || reasonLower.includes('quality')) {\n"
                "  disputeOwner = 'ian@anyvisionmedia.com';\n"
                "  priority = 'High';\n"
                "} else if (reasonLower.includes('duplicate')) {\n"
                "  disputeOwner = 'accounts@anyvisionmedia.com';\n"
                "  priority = 'Normal';\n"
                "} else if (reasonLower.includes('not received') || reasonLower.includes('wrong')) {\n"
                "  disputeOwner = 'accounts@anyvisionmedia.com';\n"
                "  priority = 'High';\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    invoiceNumber: invoiceNumber,\n"
                "    disputeReason: reason,\n"
                "    disputeDetails: details,\n"
                "    customerName: customerName,\n"
                "    customerEmail: customerEmail,\n"
                "    disputeOwner: disputeOwner,\n"
                "    priority: priority,\n"
                "    disputeDate: new Date().toISOString().split('T')[0],\n"
                "    status: 'Disputed',\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Handle Dispute",
        "type": "n8n-nodes-base.code",
        "position": [440, 1200],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # 25. Update Invoice Disputed (airtable update)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "filterByFormula": "{Invoice Number} = '{{ $json.invoiceNumber }}'",
        },
        "id": uid(),
        "name": "Find Invoice for Dispute",
        "type": "n8n-nodes-base.airtable",
        "position": [680, 1200],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "columns": {
                "value": {
                    "Invoice ID": "={{ $json['Invoice ID'] }}",
                    "Status": "Disputed",
                    "Dispute Reason": "={{ $('Handle Dispute').first().json.disputeReason + '. Details: ' + ($('Handle Dispute').first().json.disputeDetails || '') }}",
                    "Dispute Owner": "={{ $('Handle Dispute').first().json.disputeOwner }}",
                },
                "schema": [
                    {"id": "Invoice ID", "type": "string", "display": True, "displayName": "Invoice ID"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Dispute Reason", "type": "string", "display": True, "displayName": "Dispute Reason"},
                    {"id": "Dispute Owner", "type": "string", "display": True, "displayName": "Dispute Owner"},
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Invoice ID"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Invoice Disputed",
        "type": "n8n-nodes-base.airtable",
        "position": [920, 1200],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 26. Create Dispute Task (airtable create)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "columns": {
                "value": {
                    "Type": "Dispute Resolution",
                    "Priority": "={{ $('Handle Dispute').first().json.priority }}",
                    "Status": "Open",
                    "Description": "={{ 'Dispute: Invoice ' + $('Handle Dispute').first().json.invoiceNumber + ' - ' + $('Handle Dispute').first().json.customerName + '. Reason: ' + $('Handle Dispute').first().json.disputeReason + '. Details: ' + ($('Handle Dispute').first().json.disputeDetails || '') }}",
                    "Related Record ID": "={{ $('Handle Dispute').first().json.invoiceNumber }}",
                    "Related Table": "Invoices",
                    "Owner": "={{ $('Handle Dispute').first().json.disputeOwner }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [
                    {"id": "Type", "type": "string", "display": True, "displayName": "Type"},
                    {"id": "Priority", "type": "string", "display": True, "displayName": "Priority"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                    {"id": "Description", "type": "string", "display": True, "displayName": "Description"},
                    {"id": "Related Record ID", "type": "string", "display": True, "displayName": "Related Record ID"},
                    {"id": "Related Table", "type": "string", "display": True, "displayName": "Related Table"},
                    {"id": "Owner", "type": "string", "display": True, "displayName": "Owner"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Dispute Task",
        "type": "n8n-nodes-base.airtable",
        "position": [1160, 1200],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 27. Write Dispute Audit (airtable create) - DISPUTE_OPENED
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "columns": {
                "value": {
                    "Timestamp": "={{ $now.toISO() }}",
                    "Workflow Name": "WF-02 Collections & Follow-ups",
                    "Event Type": "DISPUTE_OPENED",
                    "Record Type": "Invoice",
                    "Record ID": "={{ $('Handle Dispute').first().json.invoiceNumber }}",
                    "Action Taken": "={{ 'Dispute opened: ' + $('Handle Dispute').first().json.disputeReason }}",
                    "Actor": "={{ $('Handle Dispute').first().json.customerEmail || 'customer' }}",
                    "Result": "Success",
                    "Error Details": "",
                    "Metadata JSON": "={{ JSON.stringify({ reason: $('Handle Dispute').first().json.disputeReason, owner: $('Handle Dispute').first().json.disputeOwner, priority: $('Handle Dispute').first().json.priority, customer: $('Handle Dispute').first().json.customerName }) }}",
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
                ],
                "mappingMode": "defineBelow",
                "matchingColumns": ["Timestamp"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Dispute Audit",
        "type": "n8n-nodes-base.airtable",
        "position": [1400, 1200],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── Summary ───────────────────────────────────────────────

    # 28. Build Summary (code) - aggregate all reminders sent
    nodes.append({
        "parameters": {
            "jsCode": (
                "const allItems = $input.all();\n"
                "\n"
                "let totalProcessed = 0;\n"
                "let remindersSent = 0;\n"
                "let escalations = 0;\n"
                "let skipped = 0;\n"
                "const summaryLines = [];\n"
                "\n"
                "for (const item of allItems) {\n"
                "  totalProcessed++;\n"
                "  const stage = item.json.reminderStage || item.json.lastReminderStage || 'unknown';\n"
                "  const inv = item.json.invoiceNumber || item.json['Invoice Number'] || 'N/A';\n"
                "\n"
                "  if (stage === 'no_action' || stage === 'unknown') {\n"
                "    skipped++;\n"
                "  } else {\n"
                "    remindersSent++;\n"
                "    if (stage === 't_plus_14') escalations++;\n"
                "    summaryLines.push(`${inv}: ${stage}`);\n"
                "  }\n"
                "}\n"
                "\n"
                "const summary = [\n"
                "  `Collections Run Complete - ${new Date().toISOString().split('T')[0]}`,\n"
                "  `Total Invoices Processed: ${totalProcessed}`,\n"
                "  `Reminders Sent: ${remindersSent}`,\n"
                "  `Escalations: ${escalations}`,\n"
                "  `Skipped (no action): ${skipped}`,\n"
                "  '',\n"
                "  'Details:',\n"
                "  ...summaryLines,\n"
                "].join('\\n');\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    summary: summary,\n"
                "    totalProcessed: totalProcessed,\n"
                "    remindersSent: remindersSent,\n"
                "    escalations: escalations,\n"
                "    skipped: skipped,\n"
                "    completedAt: new Date().toISOString(),\n"
                "  }\n"
                "};"
            ),
        },
        "id": uid(),
        "name": "Build Summary",
        "type": "n8n-nodes-base.code",
        "position": [1400, 300],
        "typeVersion": 2,
        "alwaysOutputData": True,
    })

    # ── Error Handling ────────────────────────────────────────

    # 29. Error Trigger
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 1500],
        "typeVersion": 1,
    })

    # 30. Error Notification (gmail)
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=ACCOUNTING ERROR - WF-02 Collections - {{ $json.execution.error.message }}",
            "message": (
                "=<h2>Accounting Department Error - WF-02 Collections</h2>\n"
                "<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n"
                "<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n"
                "<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n"
                "<p><strong>Time:</strong> {{ $now.toISO() }}</p>\n"
                '<p><a href="{{ $json.execution.url }}">View Execution</a></p>'
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 1500],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── Sticky Notes ──────────────────────────────────────────

    nodes.append({
        "parameters": {
            "content": (
                "## WF-02: Collections & Follow-ups\n\n"
                "**Daily 7AM Run:**\n"
                "1. Reads all open/overdue invoices from Airtable\n"
                "2. Loops through each invoice\n"
                "3. Looks up customer details\n"
                "4. Determines reminder stage based on days relative to due date\n"
                "5. Builds appropriate HTML email + WhatsApp message\n"
                "6. Sends via preferred channel\n"
                "7. Updates invoice reminder tracking\n"
                "8. Logs to audit trail\n\n"
                "**Stages:** T-3 (friendly) | Due (reminder) | T+3 (firm) | T+7 (collections) | T+14 (escalation)"
            ),
            "width": 1200,
            "height": 280,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 120],
        "typeVersion": 1,
    })

    nodes.append({
        "parameters": {
            "content": (
                "## Dispute Handling\n\n"
                "POST /accounting/dispute\n\n"
                "Accepts: {invoice_number, reason, details, customer_name, customer_email}\n\n"
                "1. Parses dispute and assigns owner based on reason\n"
                "2. Updates invoice status to Disputed\n"
                "3. Creates Dispute Resolution task\n"
                "4. Writes DISPUTE_OPENED audit log entry"
            ),
            "width": 1300,
            "height": 200,
        },
        "id": uid(),
        "name": "Sticky Note1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 1100],
        "typeVersion": 1,
    })

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
        "name": "Sticky Note2",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 1440],
        "typeVersion": 1,
    })

    return nodes


def build_connections():
    """Build connections for WF-02: Collections & Follow-ups."""
    return {
        "Daily 7AM Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]]
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]]
        },
        "System Config": {
            "main": [[{"node": "Read Open Invoices", "type": "main", "index": 0}]]
        },
        "Read Open Invoices": {
            "main": [[{"node": "Has Invoices?", "type": "main", "index": 0}]]
        },
        "Has Invoices?": {
            "main": [
                [{"node": "Loop Over Invoices", "type": "main", "index": 0}],
                [{"node": "Build Summary", "type": "main", "index": 0}],
            ]
        },
        "Loop Over Invoices": {
            "main": [
                [{"node": "Build Summary", "type": "main", "index": 0}],
                [{"node": "Lookup Customer", "type": "main", "index": 0}],
            ]
        },
        "Lookup Customer": {
            "main": [[{"node": "Determine Reminder Stage", "type": "main", "index": 0}]]
        },
        "Determine Reminder Stage": {
            "main": [[{"node": "Needs Reminder?", "type": "main", "index": 0}]]
        },
        "Needs Reminder?": {
            "main": [
                [{"node": "Reminder Stage Router", "type": "main", "index": 0}],
                [{"node": "Loop Over Invoices", "type": "main", "index": 0}],
            ]
        },
        "Reminder Stage Router": {
            "main": [
                [{"node": "Build Friendly Reminder", "type": "main", "index": 0}],
                [{"node": "Build Due Date Reminder", "type": "main", "index": 0}],
                [{"node": "Build Firm Reminder", "type": "main", "index": 0}],
                [{"node": "Build Collections Notice", "type": "main", "index": 0}],
                [{"node": "Build Escalation Notice", "type": "main", "index": 0}],
            ]
        },
        "Build Friendly Reminder": {
            "main": [[{"node": "Check Channel Pref", "type": "main", "index": 0}]]
        },
        "Build Due Date Reminder": {
            "main": [[{"node": "Check Channel Pref", "type": "main", "index": 0}]]
        },
        "Build Firm Reminder": {
            "main": [[{"node": "Check Channel Pref", "type": "main", "index": 0}]]
        },
        "Build Collections Notice": {
            "main": [[{"node": "Check Channel Pref", "type": "main", "index": 0}]]
        },
        "Build Escalation Notice": {
            "main": [[{"node": "Create Escalation Task", "type": "main", "index": 0}]]
        },
        "Create Escalation Task": {
            "main": [[{"node": "Check Channel Pref", "type": "main", "index": 0}]]
        },
        "Check Channel Pref": {
            "main": [
                [
                    {"node": "Send Reminder Email", "type": "main", "index": 0},
                    {"node": "Send Reminder WhatsApp", "type": "main", "index": 0},
                ],
                [{"node": "Send Reminder Email", "type": "main", "index": 0}],
            ]
        },
        "Send Reminder Email": {
            "main": [[{"node": "Update Invoice Reminder", "type": "main", "index": 0}]]
        },
        "Send Reminder WhatsApp": {
            "main": [[{"node": "Update Invoice Reminder", "type": "main", "index": 0}]]
        },
        "Update Invoice Reminder": {
            "main": [[{"node": "Write Audit Log", "type": "main", "index": 0}]]
        },
        "Update Invoice Status": {
            "main": [[{"node": "Loop Over Invoices", "type": "main", "index": 0}]]
        },
        "Write Audit Log": {
            "main": [[{"node": "Update Invoice Status", "type": "main", "index": 0}]]
        },
        "Dispute Webhook": {
            "main": [[{"node": "Dispute Auth Check", "type": "main", "index": 0}]]
        },
        "Dispute Auth Check": {
            "main": [[{"node": "Handle Dispute", "type": "main", "index": 0}]]
        },
        "Handle Dispute": {
            "main": [[{"node": "Find Invoice for Dispute", "type": "main", "index": 0}]]
        },
        "Find Invoice for Dispute": {
            "main": [[{"node": "Update Invoice Disputed", "type": "main", "index": 0}]]
        },
        "Update Invoice Disputed": {
            "main": [[{"node": "Create Dispute Task", "type": "main", "index": 0}]]
        },
        "Create Dispute Task": {
            "main": [[{"node": "Write Dispute Audit", "type": "main", "index": 0}]]
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]]
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW DEFINITIONS
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "wf02": {
        "name": "Accounting Dept - Collections & Follow-ups (WF-02)",
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
        "wf02": "wf02_collections.json",
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
    print("ACCOUNTING DEPARTMENT - WF-02 COLLECTIONS & FOLLOW-UPS")
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
        print("  - ACCOUNTING_TABLE_INVOICES")
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
    print("  2. Verify credential bindings (Airtable, Gmail, WhatsApp)")
    print("  3. Ensure Invoices table has: Status, Due Date, Reminder Count,")
    print("     Last Reminder Date, Next Reminder Date, Last Reminder Stage,")
    print("     Dispute Reason, Dispute Owner, Dispute Date fields")
    print("  4. Test with Manual Trigger on a few test invoices")
    print("  5. Test dispute webhook: POST /accounting/dispute")
    print("  6. Once verified, activate the Daily 7AM schedule trigger")
    print("  7. Monitor audit log for REMINDER_SENT and DISPUTE_OPENED events")


if __name__ == "__main__":
    main()
