"""
Accounting Department - Month-End Close (WF-05) Builder & Deployer

Builds the Month-End Close workflow that handles:
- Last business day detection (skip weekends)
- Reading open invoices, bills, payments, and audit logs
- Building aged receivables and aged payables reports
- Reconciliation checks for discrepancies
- AI-generated executive summary via OpenRouter
- Management pack HTML report with brand styling
- Google Sheets monthly dashboard update
- Email delivery of management pack and close confirmation
- Audit logging of month-end close event

Usage:
    python tools/deploy_accounting_wf05.py build
    python tools/deploy_accounting_wf05.py deploy
    python tools/deploy_accounting_wf05.py activate
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

# ── Google Sheets IDs ────────────────────────────────────────
GOOGLE_SHEETS_DASHBOARD_ID = os.getenv("ACCOUNTING_GOOGLE_SHEETS_DASHBOARD_ID", "REPLACE_WITH_SHEET_ID")
GOOGLE_SHEETS_DASHBOARD_TAB = os.getenv("ACCOUNTING_GOOGLE_SHEETS_DASHBOARD_TAB", "Monthly Dashboard")

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
    "ACCOUNTING_GOOGLE_SHEETS_DASHBOARD_ID": GOOGLE_SHEETS_DASHBOARD_ID,
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
# WF-05: MONTH-END CLOSE
# ══════════════════════════════════════════════════════════════

def build_nodes():
    """Build all 24 nodes for the Month-End Close workflow."""
    nodes = []

    # ── 1. Month End Schedule (scheduleTrigger) ──

    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {"field": "cronExpression", "expression": "0 8 28-31 * *"}
                ]
            }
        },
        "id": uid(),
        "name": "Month End Schedule",
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

    # ── 3. System Config (set) ──

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
                    {"id": uid(), "name": "vatRate", "value": "0.15", "type": "string"},
                    {"id": uid(), "name": "reportRecipient", "value": "ian@anyvisionmedia.com", "type": "string"},
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

    # ── 4. Check Last Business Day (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const today = new Date();\n"
                "const year = today.getFullYear();\n"
                "const month = today.getMonth();\n"
                "const lastDay = new Date(year, month + 1, 0);\n"
                "let lastBusinessDay = new Date(lastDay);\n"
                "\n"
                "while (lastBusinessDay.getDay() === 0 || lastBusinessDay.getDay() === 6) {\n"
                "  lastBusinessDay.setDate(lastBusinessDay.getDate() - 1);\n"
                "}\n"
                "\n"
                "// If triggered manually, always proceed (bypass date check)\n"
                "const isManual = $('Manual Trigger').isExecuted;\n"
                "const isLastBusinessDay = isManual || today.getDate() === lastBusinessDay.getDate();\n"
                "const monthName = today.toLocaleString('en-ZA', { month: 'long', year: 'numeric' });\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    isLastBusinessDay: isLastBusinessDay,\n"
                "    todayDate: today.toISOString().split('T')[0],\n"
                "    monthName: monthName,\n"
                "    lastBusinessDay: lastBusinessDay.toISOString().split('T')[0],\n"
                "    monthStart: `${year}-${String(month + 1).padStart(2, '0')}-01`,\n"
                "    monthEnd: lastDay.toISOString().split('T')[0],\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Check Last Business Day",
        "type": "n8n-nodes-base.code",
        "position": [700, 500],
        "typeVersion": 2,
    })

    # ── 5. Is Last Business Day? (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.isLastBusinessDay }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Is Last Business Day?",
        "type": "n8n-nodes-base.if",
        "position": [940, 500],
        "typeVersion": 2,
    })

    # ── 6. Read All Open Invoices (airtable search) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_INVOICES},
            "filterByFormula": "AND({Status} != 'Paid', {Status} != 'Cancelled')",
        },
        "id": uid(),
        "name": "Read All Open Invoices",
        "type": "n8n-nodes-base.airtable",
        "position": [1200, 400],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 7. Read All Open Bills (airtable search) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SUPPLIER_BILLS},
            "filterByFormula": "{Payment Status} != 'Paid'",
        },
        "id": uid(),
        "name": "Read All Open Bills",
        "type": "n8n-nodes-base.airtable",
        "position": [1460, 400],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 8. Read Payments This Month (airtable search - all records) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_PAYMENTS},
            "filterByFormula": "{Payment ID} != ''",
        },
        "id": uid(),
        "name": "Read Payments This Month",
        "type": "n8n-nodes-base.airtable",
        "position": [1720, 400],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 9. Read Audit Log This Month (airtable search - all records) ──

    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "filterByFormula": "{Timestamp} != ''",
        },
        "id": uid(),
        "name": "Read Audit Log This Month",
        "type": "n8n-nodes-base.airtable",
        "position": [1980, 400],
        "typeVersion": 2.1,
        "alwaysOutputData": True,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 10. Build Aged Receivables (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const invoices = $('Read All Open Invoices').all();\n"
                "const today = new Date();\n"
                "const buckets = { current: [], days_31_60: [], days_61_90: [], days_91_120: [], days_120_plus: [] };\n"
                "let totalAR = 0;\n"
                "\n"
                "for (const inv of invoices) {\n"
                "  const dueDate = new Date(inv.json['Due Date']);\n"
                "  const daysPast = Math.floor((today - dueDate) / 86400000);\n"
                "  const balance = parseFloat(inv.json['Balance Due'] || inv.json['Total'] || 0);\n"
                "  totalAR += balance;\n"
                "  \n"
                "  const record = { invoiceNumber: inv.json['Invoice Number'], customer: inv.json['Customer Name'], balance, daysPast };\n"
                "  \n"
                "  if (daysPast <= 30) buckets.current.push(record);\n"
                "  else if (daysPast <= 60) buckets.days_31_60.push(record);\n"
                "  else if (daysPast <= 90) buckets.days_61_90.push(record);\n"
                "  else if (daysPast <= 120) buckets.days_91_120.push(record);\n"
                "  else buckets.days_120_plus.push(record);\n"
                "}\n"
                "\n"
                "const summary = {\n"
                "  current: buckets.current.reduce((s, r) => s + r.balance, 0),\n"
                "  days_31_60: buckets.days_31_60.reduce((s, r) => s + r.balance, 0),\n"
                "  days_61_90: buckets.days_61_90.reduce((s, r) => s + r.balance, 0),\n"
                "  days_91_120: buckets.days_91_120.reduce((s, r) => s + r.balance, 0),\n"
                "  days_120_plus: buckets.days_120_plus.reduce((s, r) => s + r.balance, 0),\n"
                "};\n"
                "\n"
                "return { json: { agedReceivables: buckets, arSummary: summary, totalAR, invoiceCount: invoices.length } };\n"
            ),
        },
        "id": uid(),
        "name": "Build Aged Receivables",
        "type": "n8n-nodes-base.code",
        "position": [2240, 400],
        "typeVersion": 2,
    })

    # ── 11. Build Aged Payables (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const bills = $('Read All Open Bills').all();\n"
                "const today = new Date();\n"
                "const buckets = { current: [], days_31_60: [], days_61_90: [], days_91_120: [], days_120_plus: [] };\n"
                "let totalAP = 0;\n"
                "\n"
                "for (const bill of bills) {\n"
                "  const dueDate = new Date(bill.json['Due Date']);\n"
                "  const daysPast = Math.floor((today - dueDate) / 86400000);\n"
                "  const balance = parseFloat(bill.json['Balance Due'] || bill.json['Total'] || 0);\n"
                "  totalAP += balance;\n"
                "  \n"
                "  const record = { billNumber: bill.json['Bill Number'], supplier: bill.json['Supplier Name'], balance, daysPast };\n"
                "  \n"
                "  if (daysPast <= 30) buckets.current.push(record);\n"
                "  else if (daysPast <= 60) buckets.days_31_60.push(record);\n"
                "  else if (daysPast <= 90) buckets.days_61_90.push(record);\n"
                "  else if (daysPast <= 120) buckets.days_91_120.push(record);\n"
                "  else buckets.days_120_plus.push(record);\n"
                "}\n"
                "\n"
                "const summary = {\n"
                "  current: buckets.current.reduce((s, r) => s + r.balance, 0),\n"
                "  days_31_60: buckets.days_31_60.reduce((s, r) => s + r.balance, 0),\n"
                "  days_61_90: buckets.days_61_90.reduce((s, r) => s + r.balance, 0),\n"
                "  days_91_120: buckets.days_91_120.reduce((s, r) => s + r.balance, 0),\n"
                "  days_120_plus: buckets.days_120_plus.reduce((s, r) => s + r.balance, 0),\n"
                "};\n"
                "\n"
                "return { json: { agedPayables: buckets, apSummary: summary, totalAP, billCount: bills.length } };\n"
            ),
        },
        "id": uid(),
        "name": "Build Aged Payables",
        "type": "n8n-nodes-base.code",
        "position": [2500, 400],
        "typeVersion": 2,
    })

    # ── 12. Reconciliation Check (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const dateInfo = $('Check Last Business Day').first().json;\n"
                "const monthStart = new Date(dateInfo.monthStart);\n"
                "const monthEnd = new Date(dateInfo.monthEnd + 'T23:59:59');\n"
                "\n"
                "// Filter payments and audit logs to current month\n"
                "const allPayments = $('Read Payments This Month').all();\n"
                "const payments = allPayments.filter(p => {\n"
                "  const d = new Date(p.json['Date Received']);\n"
                "  return !isNaN(d.getTime()) && d >= monthStart && d <= monthEnd;\n"
                "});\n"
                "const allLogs = $('Read Audit Log This Month').all();\n"
                "const auditLogs = allLogs.filter(l => {\n"
                "  const d = new Date(l.json['Created At']);\n"
                "  return !isNaN(d.getTime()) && d >= monthStart && d <= monthEnd;\n"
                "});\n"
                "\n"
                "const invoices = $('Read All Open Invoices').all();\n"
                "const arData = $('Build Aged Receivables').first().json;\n"
                "const apData = $('Build Aged Payables').first().json;\n"
                "\n"
                "const discrepancies = [];\n"
                "\n"
                "// Check 1: Payments without matching invoices\n"
                "for (const pmt of payments) {\n"
                "  const invoiceRef = pmt.json['Invoice Number'] || pmt.json['Reference'] || '';\n"
                "  if (invoiceRef) {\n"
                "    const matchingInvoice = invoices.find(inv => \n"
                "      inv.json['Invoice Number'] === invoiceRef\n"
                "    );\n"
                "    if (!matchingInvoice) {\n"
                "      discrepancies.push({\n"
                "        type: 'ORPHANED_PAYMENT',\n"
                "        description: `Payment ${pmt.json['Payment ID'] || 'unknown'} references invoice ${invoiceRef} which was not found in open invoices`,\n"
                "        amount: parseFloat(pmt.json['Amount'] || 0),\n"
                "        reference: invoiceRef,\n"
                "      });\n"
                "    }\n"
                "  }\n"
                "}\n"
                "\n"
                "// Check 2: Invoices overdue by 120+ days (potential write-offs)\n"
                "const overdue120 = arData.agedReceivables.days_120_plus || [];\n"
                "for (const inv of overdue120) {\n"
                "  discrepancies.push({\n"
                "    type: 'OVERDUE_120_PLUS',\n"
                "    description: `Invoice ${inv.invoiceNumber} for ${inv.customer} is ${inv.daysPast} days overdue - consider write-off`,\n"
                "    amount: inv.balance,\n"
                "    reference: inv.invoiceNumber,\n"
                "  });\n"
                "}\n"
                "\n"
                "// Check 3: Bills overdue by 120+ days\n"
                "const overdueAP120 = apData.agedPayables.days_120_plus || [];\n"
                "for (const bill of overdueAP120) {\n"
                "  discrepancies.push({\n"
                "    type: 'OVERDUE_BILL_120_PLUS',\n"
                "    description: `Bill ${bill.billNumber} for ${bill.supplier} is ${bill.daysPast} days overdue - urgent payment required`,\n"
                "    amount: bill.balance,\n"
                "    reference: bill.billNumber,\n"
                "  });\n"
                "}\n"
                "\n"
                "// Build summary stats\n"
                "const totalPaymentsReceived = payments.reduce((s, p) => s + parseFloat(p.json['Amount'] || 0), 0);\n"
                "const netPosition = arData.totalAR - apData.totalAP;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    hasDiscrepancies: discrepancies.length > 0,\n"
                "    discrepancyCount: discrepancies.length,\n"
                "    discrepancies: discrepancies,\n"
                "    totalPaymentsReceived: totalPaymentsReceived,\n"
                "    paymentCount: payments.length,\n"
                "    totalAR: arData.totalAR,\n"
                "    totalAP: apData.totalAP,\n"
                "    netPosition: netPosition,\n"
                "    arSummary: arData.arSummary,\n"
                "    apSummary: apData.apSummary,\n"
                "    invoiceCount: arData.invoiceCount,\n"
                "    billCount: apData.billCount,\n"
                "    auditLogCount: auditLogs.length,\n"
                "    agedReceivables: arData.agedReceivables,\n"
                "    agedPayables: apData.agedPayables,\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Reconciliation Check",
        "type": "n8n-nodes-base.code",
        "position": [2760, 400],
        "typeVersion": 2,
    })

    # ── 13. Has Discrepancies? (if) ──

    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "id": uid(),
                        "leftValue": "={{ $json.hasDiscrepancies }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Has Discrepancies?",
        "type": "n8n-nodes-base.if",
        "position": [3020, 400],
        "typeVersion": 2,
    })

    # ── 14. Create Reconciliation Tasks (airtable create) ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_TASKS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Task ID": "={{ 'TASK-' + Date.now() }}",
                    "Type": "Month End Task",
                    "Priority": "High",
                    "Status": "Open",
                    "Description": "=Month-End Reconciliation: {{ $json.discrepancyCount }} discrepancies found. Issues: {{ $json.discrepancies.map(d => d.type + ': ' + d.description).join(' | ') }}",
                    "Owner": "ian@anyvisionmedia.com",
                    "Due At": "={{ $now.plus(2, 'days').toFormat('yyyy-MM-dd') }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Reconciliation Tasks",
        "type": "n8n-nodes-base.airtable",
        "position": [3280, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 15. Build Management Pack (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const data = $('Reconciliation Check').first().json;\n"
                "const config = $('System Config').first().json;\n"
                "const dateInfo = $('Check Last Business Day').first().json;\n"
                "\n"
                "// Helper to format currency\n"
                "const fmt = (v) => `R ${(v || 0).toFixed(2).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',')}`;\n"
                "\n"
                "// Build AR aging rows\n"
                "const arBuckets = [\n"
                "  { label: 'Current (0-30 days)', amount: data.arSummary.current },\n"
                "  { label: '31-60 days', amount: data.arSummary.days_31_60 },\n"
                "  { label: '61-90 days', amount: data.arSummary.days_61_90 },\n"
                "  { label: '91-120 days', amount: data.arSummary.days_91_120 },\n"
                "  { label: '120+ days', amount: data.arSummary.days_120_plus },\n"
                "];\n"
                "const arRows = arBuckets.map(b => \n"
                "  `<tr><td style=\"padding:8px;border:1px solid #ddd;\">${b.label}</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${fmt(b.amount)}</td></tr>`\n"
                ").join('');\n"
                "\n"
                "// Build AP aging rows\n"
                "const apBuckets = [\n"
                "  { label: 'Current (0-30 days)', amount: data.apSummary.current },\n"
                "  { label: '31-60 days', amount: data.apSummary.days_31_60 },\n"
                "  { label: '61-90 days', amount: data.apSummary.days_61_90 },\n"
                "  { label: '91-120 days', amount: data.apSummary.days_91_120 },\n"
                "  { label: '120+ days', amount: data.apSummary.days_120_plus },\n"
                "];\n"
                "const apRows = apBuckets.map(b => \n"
                "  `<tr><td style=\"padding:8px;border:1px solid #ddd;\">${b.label}</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${fmt(b.amount)}</td></tr>`\n"
                ").join('');\n"
                "\n"
                "// Build exceptions list\n"
                "const discrepancies = data.discrepancies || [];\n"
                "const exceptionRows = discrepancies.length > 0 \n"
                "  ? discrepancies.map(d => \n"
                "      `<tr><td style=\"padding:8px;border:1px solid #ddd;\">${d.type}</td><td style=\"padding:8px;border:1px solid #ddd;\">${d.description}</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${fmt(d.amount)}</td></tr>`\n"
                "    ).join('')\n"
                "  : '<tr><td colspan=\"3\" style=\"padding:8px;border:1px solid #ddd;text-align:center;color:#22c55e;\">No exceptions found</td></tr>';\n"
                "\n"
                "const html = `<!DOCTYPE html>\n"
                "<html>\n"
                "<head><meta charset=\"utf-8\"><title>Month-End Management Pack</title></head>\n"
                "<body style=\"margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f4f4f4;\">\n"
                "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:800px;margin:20px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);\">\n"
                "\n"
                "  <!-- Header -->\n"
                "  <tr><td style=\"padding:30px 40px;background:#FF6D5A;color:#fff;\">\n"
                "    <h1 style=\"margin:0;font-size:24px;\">Month-End Management Pack</h1>\n"
                "    <p style=\"margin:8px 0 0;font-size:14px;opacity:0.9;\">${dateInfo.monthName} | ${config.companyName}</p>\n"
                "  </td></tr>\n"
                "\n"
                "  <!-- Executive Summary -->\n"
                "  <tr><td style=\"padding:30px 40px;\">\n"
                "    <h2 style=\"color:#FF6D5A;margin:0 0 16px;border-bottom:2px solid #FF6D5A;padding-bottom:8px;\">Executive Summary</h2>\n"
                "    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">\n"
                "      <tr>\n"
                "        <td style=\"padding:12px;background:#f8f8f8;border-radius:6px;text-align:center;width:25%;\">\n"
                "          <p style=\"margin:0;font-size:12px;color:#666;\">Total Receivables</p>\n"
                "          <p style=\"margin:4px 0 0;font-size:20px;color:#1A1A2E;font-weight:bold;\">${fmt(data.totalAR)}</p>\n"
                "        </td>\n"
                "        <td style=\"width:8px;\"></td>\n"
                "        <td style=\"padding:12px;background:#f8f8f8;border-radius:6px;text-align:center;width:25%;\">\n"
                "          <p style=\"margin:0;font-size:12px;color:#666;\">Total Payables</p>\n"
                "          <p style=\"margin:4px 0 0;font-size:20px;color:#1A1A2E;font-weight:bold;\">${fmt(data.totalAP)}</p>\n"
                "        </td>\n"
                "        <td style=\"width:8px;\"></td>\n"
                "        <td style=\"padding:12px;background:#f8f8f8;border-radius:6px;text-align:center;width:25%;\">\n"
                "          <p style=\"margin:0;font-size:12px;color:#666;\">Net Position</p>\n"
                "          <p style=\"margin:4px 0 0;font-size:20px;color:${data.netPosition >= 0 ? '#22c55e' : '#ef4444'};font-weight:bold;\">${fmt(data.netPosition)}</p>\n"
                "        </td>\n"
                "        <td style=\"width:8px;\"></td>\n"
                "        <td style=\"padding:12px;background:#f8f8f8;border-radius:6px;text-align:center;width:25%;\">\n"
                "          <p style=\"margin:0;font-size:12px;color:#666;\">Cash Received</p>\n"
                "          <p style=\"margin:4px 0 0;font-size:20px;color:#22c55e;font-weight:bold;\">${fmt(data.totalPaymentsReceived)}</p>\n"
                "        </td>\n"
                "      </tr>\n"
                "    </table>\n"
                "  </td></tr>\n"
                "\n"
                "  <!-- Aged Receivables -->\n"
                "  <tr><td style=\"padding:0 40px 30px;\">\n"
                "    <h2 style=\"color:#FF6D5A;margin:0 0 16px;border-bottom:2px solid #FF6D5A;padding-bottom:8px;\">Aged Receivables</h2>\n"
                "    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">\n"
                "      <tr style=\"background:#FF6D5A;color:#fff;\">\n"
                "        <th style=\"padding:10px 8px;text-align:left;\">Aging Bucket</th>\n"
                "        <th style=\"padding:10px 8px;text-align:right;\">Amount</th>\n"
                "      </tr>\n"
                "      ${arRows}\n"
                "      <tr style=\"background:#f0f0f0;font-weight:bold;\">\n"
                "        <td style=\"padding:10px 8px;border:1px solid #ddd;\">Total (${data.invoiceCount} invoices)</td>\n"
                "        <td style=\"padding:10px 8px;border:1px solid #ddd;text-align:right;color:#FF6D5A;\">${fmt(data.totalAR)}</td>\n"
                "      </tr>\n"
                "    </table>\n"
                "  </td></tr>\n"
                "\n"
                "  <!-- Aged Payables -->\n"
                "  <tr><td style=\"padding:0 40px 30px;\">\n"
                "    <h2 style=\"color:#FF6D5A;margin:0 0 16px;border-bottom:2px solid #FF6D5A;padding-bottom:8px;\">Aged Payables</h2>\n"
                "    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">\n"
                "      <tr style=\"background:#FF6D5A;color:#fff;\">\n"
                "        <th style=\"padding:10px 8px;text-align:left;\">Aging Bucket</th>\n"
                "        <th style=\"padding:10px 8px;text-align:right;\">Amount</th>\n"
                "      </tr>\n"
                "      ${apRows}\n"
                "      <tr style=\"background:#f0f0f0;font-weight:bold;\">\n"
                "        <td style=\"padding:10px 8px;border:1px solid #ddd;\">Total (${data.billCount} bills)</td>\n"
                "        <td style=\"padding:10px 8px;border:1px solid #ddd;text-align:right;color:#FF6D5A;\">${fmt(data.totalAP)}</td>\n"
                "      </tr>\n"
                "    </table>\n"
                "  </td></tr>\n"
                "\n"
                "  <!-- Cash Flow Snapshot -->\n"
                "  <tr><td style=\"padding:0 40px 30px;\">\n"
                "    <h2 style=\"color:#FF6D5A;margin:0 0 16px;border-bottom:2px solid #FF6D5A;padding-bottom:8px;\">Cash Flow Snapshot</h2>\n"
                "    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Payments Received This Month</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${fmt(data.totalPaymentsReceived)}</td></tr>\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Number of Payments</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${data.paymentCount}</td></tr>\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Outstanding Receivables</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${fmt(data.totalAR)}</td></tr>\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Outstanding Payables</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${fmt(data.totalAP)}</td></tr>\n"
                "      <tr style=\"background:#f0f0f0;font-weight:bold;\"><td style=\"padding:8px;border:1px solid #ddd;\">Net Position (AR - AP)</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;color:${data.netPosition >= 0 ? '#22c55e' : '#ef4444'};\">${fmt(data.netPosition)}</td></tr>\n"
                "    </table>\n"
                "  </td></tr>\n"
                "\n"
                "  <!-- Exceptions -->\n"
                "  <tr><td style=\"padding:0 40px 30px;\">\n"
                "    <h2 style=\"color:#FF6D5A;margin:0 0 16px;border-bottom:2px solid #FF6D5A;padding-bottom:8px;\">Exceptions &amp; Discrepancies (${data.discrepancyCount})</h2>\n"
                "    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">\n"
                "      <tr style=\"background:#FF6D5A;color:#fff;\">\n"
                "        <th style=\"padding:10px 8px;text-align:left;\">Type</th>\n"
                "        <th style=\"padding:10px 8px;text-align:left;\">Description</th>\n"
                "        <th style=\"padding:10px 8px;text-align:right;\">Amount</th>\n"
                "      </tr>\n"
                "      ${exceptionRows}\n"
                "    </table>\n"
                "  </td></tr>\n"
                "\n"
                "  <!-- Monthly Totals -->\n"
                "  <tr><td style=\"padding:0 40px 30px;\">\n"
                "    <h2 style=\"color:#FF6D5A;margin:0 0 16px;border-bottom:2px solid #FF6D5A;padding-bottom:8px;\">Monthly Totals</h2>\n"
                "    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;\">\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Open Invoices</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${data.invoiceCount}</td></tr>\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Open Bills</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${data.billCount}</td></tr>\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Payments Received</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${data.paymentCount}</td></tr>\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Audit Log Entries</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;\">${data.auditLogCount}</td></tr>\n"
                "      <tr><td style=\"padding:8px;border:1px solid #ddd;\">Discrepancies Found</td><td style=\"padding:8px;border:1px solid #ddd;text-align:right;color:${data.discrepancyCount > 0 ? '#ef4444' : '#22c55e'};\">${data.discrepancyCount}</td></tr>\n"
                "    </table>\n"
                "  </td></tr>\n"
                "\n"
                "  <!-- Footer -->\n"
                "  <tr><td style=\"padding:20px 40px;background:#f8f8f8;border-top:1px solid #eee;\">\n"
                "    <p style=\"margin:0;font-size:11px;color:#999;line-height:1.5;\">\n"
                "      ${config.companyName} | Month-End Close Report | Generated ${dateInfo.todayDate}<br>\n"
                "      This is an automated report generated by the AnyVision Media Accounting System.\n"
                "    </p>\n"
                "  </td></tr>\n"
                "\n"
                "</table>\n"
                "</body></html>`;\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...data,\n"
                "    managementPackHtml: html,\n"
                "    monthName: dateInfo.monthName,\n"
                "    todayDate: dateInfo.todayDate,\n"
                "    monthStart: dateInfo.monthStart,\n"
                "    monthEnd: dateInfo.monthEnd,\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Build Management Pack",
        "type": "n8n-nodes-base.code",
        "position": [3540, 400],
        "typeVersion": 2,
    })

    # ── 16. AI Executive Summary (httpRequest - OpenRouter) ──

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
                '  "model": "{{ $(\'System Config\').first().json.aiModel }}",\n'
                '  "messages": [\n'
                '    {\n'
                '      "role": "system",\n'
                '      "content": "You are a South African financial analyst for AnyVision Media. Provide a concise executive summary of the month-end financial data. Use ZAR currency. Focus on key risks, cash flow health, and action items. Keep it under 300 words."\n'
                '    },\n'
                '    {\n'
                '      "role": "user",\n'
                '      "content": "Month-End Financial Summary for {{ $json.monthName }}:\\n\\nAccounts Receivable: R {{ $json.totalAR }} ({{ $json.invoiceCount }} open invoices)\\nAR Aging: Current R {{ $json.arSummary.current }}, 31-60 R {{ $json.arSummary.days_31_60 }}, 61-90 R {{ $json.arSummary.days_61_90 }}, 91-120 R {{ $json.arSummary.days_91_120 }}, 120+ R {{ $json.arSummary.days_120_plus }}\\n\\nAccounts Payable: R {{ $json.totalAP }} ({{ $json.billCount }} open bills)\\nAP Aging: Current R {{ $json.apSummary.current }}, 31-60 R {{ $json.apSummary.days_31_60 }}, 61-90 R {{ $json.apSummary.days_61_90 }}, 91-120 R {{ $json.apSummary.days_91_120 }}, 120+ R {{ $json.apSummary.days_120_plus }}\\n\\nCash Received This Month: R {{ $json.totalPaymentsReceived }} ({{ $json.paymentCount }} payments)\\nNet Position: R {{ $json.netPosition }}\\nDiscrepancies: {{ $json.discrepancyCount }}\\n\\nPlease provide an executive summary with key observations and recommended actions."\n'
                '    }\n'
                '  ],\n'
                '  "max_tokens": 800,\n'
                '  "temperature": 0.3\n'
                '}'
            ),
            "options": {"timeout": 60000},
        },
        "id": uid(),
        "name": "AI Executive Summary",
        "type": "n8n-nodes-base.httpRequest",
        "position": [3800, 400],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 5000,
    })

    # ── 17. Parse AI Summary (code) ──

    nodes.append({
        "parameters": {
            "jsCode": (
                "const response = $input.first().json;\n"
                "const prevData = $('Build Management Pack').first().json;\n"
                "\n"
                "let summaryText = 'AI summary not available.';\n"
                "\n"
                "try {\n"
                "  if (response.choices && response.choices.length > 0) {\n"
                "    summaryText = response.choices[0].message.content || summaryText;\n"
                "  } else if (response.error) {\n"
                "    summaryText = `AI summary generation failed: ${response.error.message || 'Unknown error'}`;\n"
                "  }\n"
                "} catch (e) {\n"
                "  summaryText = `AI summary parsing failed: ${e.message}`;\n"
                "}\n"
                "\n"
                "return {\n"
                "  json: {\n"
                "    ...prevData,\n"
                "    aiSummary: summaryText,\n"
                "    aiModel: response.model || 'unknown',\n"
                "    aiTokensUsed: response.usage ? response.usage.total_tokens : 0,\n"
                "  }\n"
                "};\n"
            ),
        },
        "id": uid(),
        "name": "Parse AI Summary",
        "type": "n8n-nodes-base.code",
        "position": [4060, 400],
        "typeVersion": 2,
    })

    # ── 18. Write to Google Sheets (googleSheets) ──

    nodes.append({
        "parameters": {
            "operation": "append",
            "documentId": {"__rl": True, "mode": "list", "value": GOOGLE_SHEETS_DASHBOARD_ID},
            "sheetName": {"__rl": True, "mode": "list", "value": GOOGLE_SHEETS_DASHBOARD_TAB},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Month": "={{ $json.monthName }}",
                    "Close Date": "={{ $json.todayDate }}",
                    "Total AR": "={{ $json.totalAR }}",
                    "Total AP": "={{ $json.totalAP }}",
                    "Net Position": "={{ $json.netPosition }}",
                    "Cash Received": "={{ $json.totalPaymentsReceived }}",
                    "Open Invoices": "={{ $json.invoiceCount }}",
                    "Open Bills": "={{ $json.billCount }}",
                    "Discrepancies": "={{ $json.discrepancyCount }}",
                    "AI Summary": "={{ $json.aiSummary }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write to Google Sheets",
        "type": "n8n-nodes-base.googleSheets",
        "position": [4320, 400],
        "typeVersion": 4.5,
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "onError": "continueRegularOutput",
    })

    # ── 19. Send Management Pack (gmail) ──

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Month-End Management Pack - {{ $('Parse AI Summary').first().json.monthName }}",
            "emailType": "html",
            "message": (
                "={{ $('Parse AI Summary').first().json.managementPackHtml }}"
            ),
            "options": {
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Send Management Pack",
        "type": "n8n-nodes-base.gmail",
        "position": [4580, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── 20. Update Month End Status (airtable create) ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_SYSTEM_CONFIG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Key": "last_month_end_close",
                    "Value": "={{ JSON.stringify({ date: $('Parse AI Summary').first().json.todayDate, month: $('Parse AI Summary').first().json.monthName, totalAR: $('Parse AI Summary').first().json.totalAR, totalAP: $('Parse AI Summary').first().json.totalAP, netPosition: $('Parse AI Summary').first().json.netPosition, discrepancies: $('Parse AI Summary').first().json.discrepancyCount }) }}",
                    "Updated At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Month End Status",
        "type": "n8n-nodes-base.airtable",
        "position": [4840, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 21. Write Audit Log (airtable create) ──

    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "list", "value": TABLE_AUDIT_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Timestamp": "={{ $now.toISO() }}",
                    "Workflow Name": "WF-05 Month End Close",
                    "Event Type": "MONTH_END_CLOSE",
                    "Record Type": "Month End",
                    "Record ID": "={{ $('Parse AI Summary').first().json.monthName }}",
                    "Action Taken": "=Month-end close completed for {{ $('Parse AI Summary').first().json.monthName }}. AR: R {{ $('Parse AI Summary').first().json.totalAR }}, AP: R {{ $('Parse AI Summary').first().json.totalAP }}",
                    "Actor": "system",
                    "Result": "Success",
                    "Error Details": "",
                    "Metadata JSON": "={{ JSON.stringify({ month: $('Parse AI Summary').first().json.monthName, totalAR: $('Parse AI Summary').first().json.totalAR, totalAP: $('Parse AI Summary').first().json.totalAP, netPosition: $('Parse AI Summary').first().json.netPosition, discrepancies: $('Parse AI Summary').first().json.discrepancyCount }) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd') }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Audit Log",
        "type": "n8n-nodes-base.airtable",
        "position": [5100, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # ── 22. Send Close Confirmation (gmail) ──

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Month-End Close Complete - {{ $('Parse AI Summary').first().json.monthName }}",
            "emailType": "html",
            "message": (
                "=<h2 style='color:#22c55e;'>Month-End Close Completed Successfully</h2>"
                "<p><strong>Period:</strong> {{ $('Parse AI Summary').first().json.monthName }}</p>"
                "<p><strong>Close Date:</strong> {{ $('Parse AI Summary').first().json.todayDate }}</p>"
                "<hr>"
                "<table style='border-collapse:collapse;width:100%;max-width:400px;'>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>Total AR</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;text-align:right;'>R {{ $('Parse AI Summary').first().json.totalAR }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>Total AP</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;text-align:right;'>R {{ $('Parse AI Summary').first().json.totalAP }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>Net Position</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;text-align:right;color:#FF6D5A;'><strong>R {{ $('Parse AI Summary').first().json.netPosition }}</strong></td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>Cash Received</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;text-align:right;'>R {{ $('Parse AI Summary').first().json.totalPaymentsReceived }}</td></tr>"
                "<tr><td style='padding:8px;border:1px solid #ddd;'><strong>Discrepancies</strong></td>"
                "<td style='padding:8px;border:1px solid #ddd;text-align:right;'>{{ $('Parse AI Summary').first().json.discrepancyCount }}</td></tr>"
                "</table>"
                "<br>"
                "<p><strong>AI Executive Summary:</strong></p>"
                "<blockquote style='border-left:3px solid #FF6D5A;padding:10px 16px;margin:10px 0;background:#f8f8f8;'>"
                "{{ $('Parse AI Summary').first().json.aiSummary }}"
                "</blockquote>"
                "<br>"
                "<p style='font-size:12px;color:#999;'>Management pack has been emailed separately. Google Sheets dashboard updated.</p>"
                "<p style='font-size:11px;color:#999;'>AnyVision Media Accounting System</p>"
            ),
            "options": {
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Send Close Confirmation",
        "type": "n8n-nodes-base.gmail",
        "position": [5360, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # ── 23. Error Trigger ──

    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 900],
        "typeVersion": 1,
    })

    # ── 24. Error Notification (gmail) ──

    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=ERROR: Accounting WF-05 Month-End Close - {{ $now.toFormat('yyyy-MM-dd HH:mm') }}",
            "emailType": "html",
            "message": (
                "=<h2 style='color:#FF6D5A;'>Workflow Error: Month-End Close (WF-05)</h2>"
                "<p><strong>Time:</strong> {{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}</p>"
                "<p><strong>Error:</strong> {{ $json.execution?.error?.message || 'Unknown error' }}</p>"
                "<p><strong>Node:</strong> {{ $json.execution?.lastNodeExecuted || 'Unknown' }}</p>"
                "<p><strong>Execution ID:</strong> {{ $json.execution?.id || 'N/A' }}</p>"
                "<hr>"
                "<p>The month-end close process failed. Please check the n8n execution log and re-run manually once the issue is resolved.</p>"
                "<p style='font-size:11px;color:#999;'>AnyVision Media Accounting System</p>"
            ),
            "options": {
                "appendAttribution": False,
            },
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [460, 900],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_connections():
    """Build connections for the Month-End Close workflow."""
    return {
        "Month End Schedule": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Check Last Business Day", "type": "main", "index": 0}]],
        },
        "Check Last Business Day": {
            "main": [[{"node": "Is Last Business Day?", "type": "main", "index": 0}]],
        },
        "Is Last Business Day?": {
            "main": [
                # True branch: proceed with month-end close
                [{"node": "Read All Open Invoices", "type": "main", "index": 0}],
                # False branch: do nothing (no connection)
                [],
            ],
        },
        "Read All Open Invoices": {
            "main": [[{"node": "Read All Open Bills", "type": "main", "index": 0}]],
        },
        "Read All Open Bills": {
            "main": [[{"node": "Read Payments This Month", "type": "main", "index": 0}]],
        },
        "Read Payments This Month": {
            "main": [[{"node": "Read Audit Log This Month", "type": "main", "index": 0}]],
        },
        "Read Audit Log This Month": {
            "main": [[{"node": "Build Aged Receivables", "type": "main", "index": 0}]],
        },
        "Build Aged Receivables": {
            "main": [[{"node": "Build Aged Payables", "type": "main", "index": 0}]],
        },
        "Build Aged Payables": {
            "main": [[{"node": "Reconciliation Check", "type": "main", "index": 0}]],
        },
        "Reconciliation Check": {
            "main": [[{"node": "Has Discrepancies?", "type": "main", "index": 0}]],
        },
        "Has Discrepancies?": {
            "main": [
                # True branch: create reconciliation tasks then continue
                [{"node": "Create Reconciliation Tasks", "type": "main", "index": 0}],
                # False branch: skip directly to Build Management Pack
                [{"node": "Build Management Pack", "type": "main", "index": 0}],
            ],
        },
        "Create Reconciliation Tasks": {
            "main": [[{"node": "Build Management Pack", "type": "main", "index": 0}]],
        },
        "Build Management Pack": {
            "main": [[{"node": "AI Executive Summary", "type": "main", "index": 0}]],
        },
        "AI Executive Summary": {
            "main": [[{"node": "Parse AI Summary", "type": "main", "index": 0}]],
        },
        "Parse AI Summary": {
            "main": [[{"node": "Write to Google Sheets", "type": "main", "index": 0}]],
        },
        "Write to Google Sheets": {
            "main": [[{"node": "Send Management Pack", "type": "main", "index": 0}]],
        },
        "Send Management Pack": {
            "main": [[{"node": "Update Month End Status", "type": "main", "index": 0}]],
        },
        "Update Month End Status": {
            "main": [[{"node": "Write Audit Log", "type": "main", "index": 0}]],
        },
        "Write Audit Log": {
            "main": [[{"node": "Send Close Confirmation", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW DEFINITIONS
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "wf05": {
        "name": "Accounting Dept - Month End Close (WF-05)",
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
        "wf05": "wf05_month_end_close.json",
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
    print("ACCOUNTING DEPARTMENT - WF-05 MONTH-END CLOSE")
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
    print("  2. Verify credential bindings (Airtable, Gmail, Google Sheets, OpenRouter)")
    print("  3. Configure Google Sheets document ID for monthly dashboard")
    print("  4. Test with Manual Trigger on a non-month-end day (will skip)")
    print("  5. Test with Manual Trigger on last business day of month")
    print("  6. Review the management pack email output")
    print("  7. Verify Google Sheets dashboard row was appended")
    print("  8. Once verified, activate the month-end schedule trigger")


if __name__ == "__main__":
    main()
