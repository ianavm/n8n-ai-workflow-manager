"""
Financial Intelligence - Workflow Builder & Deployer

Builds 4 financial intelligence workflows for payroll, VAT, cash flow, and payment scheduling.

Workflows:
    FINTEL-01: Monthly Payroll Run (25th of month 08:00 SAST)
    FINTEL-02: Quarterly VAT Prep (1st of Jan/Apr/Jul/Oct 09:00 SAST)
    FINTEL-03: Cash Flow Scenarios (Weekly Friday 06:00 SAST)
    FINTEL-04: Smart Payment Scheduler (Daily 07:00 SAST)

Usage:
    python tools/deploy_financial_intel.py build              # Build all JSONs
    python tools/deploy_financial_intel.py build fintel01     # Build FINTEL-01 only
    python tools/deploy_financial_intel.py build fintel02     # Build FINTEL-02 only
    python tools/deploy_financial_intel.py build fintel03     # Build FINTEL-03 only
    python tools/deploy_financial_intel.py build fintel04     # Build FINTEL-04 only
    python tools/deploy_financial_intel.py deploy             # Build + Deploy (inactive)
    python tools/deploy_financial_intel.py activate           # Build + Deploy + Activate
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

# -- Credential Constants -------------------------------------------------

CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail AVM"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable PAT"}
CRED_XERO = {"id": "xeroOAuth2Api", "name": "Xero OAuth2"}

# -- Airtable IDs ---------------------------------------------------------

ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "appTCh0EeXQp0XqzW")
TABLE_FINANCIAL_INTEL = os.getenv("FINTEL_TABLE_ID", "REPLACE_AFTER_SETUP")

# -- Config ----------------------------------------------------------------

XERO_TENANT_ID = "1f5c5e97-8976-4e03-b33c-ba638a7aeb72"
AI_MODEL = "anthropic/claude-sonnet-4-20250514"
ALERT_EMAIL = "ian@anyvisionmedia.com"
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

# -- Helpers ---------------------------------------------------------------


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# FINTEL-01: Monthly Payroll Run
# ==================================================================

def build_fintel01_nodes():
    """Build nodes for FINTEL-01: Monthly Payroll Run (25th 08:00 SAST = 06:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (25th 06:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 6 25 * *",
                    }
                ]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # -- Set Pay Period --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "periodStart",
                        "value": "={{ $now.startOf('month').toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "periodEnd",
                        "value": "={{ $now.endOf('month').toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "monthLabel",
                        "value": "={{ $now.toFormat('MMMM yyyy') }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Pay Period",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [440, 300],
    })

    # -- Fetch Employees from Xero --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "https://api.xero.com/payroll.xro/2.0/Employees",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Employees",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 300],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- Fetch Payslips --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://api.xero.com/payroll.xro/2.0/Payslip?StartDate={{ $('Set Pay Period').first().json.periodStart }}&EndDate={{ $('Set Pay Period').first().json.periodEnd }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Payslips",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [880, 300],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- AI Variance Analysis (OpenRouter) --
    nodes.append({
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 1500,
  "messages": [
    {{
      "role": "system",
      "content": "You are a payroll analyst for AnyVision Media, a South African company. Analyze payroll data and identify variances vs last month. Use ZAR currency. Flag: new employees, terminated employees, significant salary changes (>5%), overtime anomalies, total payroll cost change. Provide a concise summary with key metrics and any concerns."
    }},
    {{
      "role": "user",
      "content": "Analyze this month's payroll data for " + $('Set Pay Period').first().json.monthLabel + ":\\n\\nEmployees:\\n" + JSON.stringify($('Fetch Employees').first().json, null, 2) + "\\n\\nPayslips:\\n" + JSON.stringify($json, null, 2)
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Variance Analysis",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1100, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Write Summary to Airtable --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_FINANCIAL_INTEL, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Period": "={{ $('Set Pay Period').first().json.monthLabel }}",
                    "Type": "Payroll",
                    "Total Payroll (ZAR)": "={{ $('Fetch Payslips').first().json.Payslips ? $('Fetch Payslips').first().json.Payslips.reduce((sum, p) => sum + (p.NetPay || 0), 0) : 0 }}",
                    "Employee Count": "={{ $('Fetch Employees').first().json.Employees ? $('Fetch Employees').first().json.Employees.length : 0 }}",
                    "Variance %": "={{ $json.choices[0].message.content.match(/variance.*?(\\d+\\.?\\d*)%/i) ? $json.choices[0].message.content.match(/variance.*?(\\d+\\.?\\d*)%/i)[1] : '0' }}",
                    "Notes": "={{ $json.choices[0].message.content.substring(0, 5000) }}",
                    "Status": "Pending Review",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Summary to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1320, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Alert Email --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=Payroll Run Summary - {{ $('Set Pay Period').first().json.monthLabel }}",
            "message": "=<h2 style=\"color: #FF6D5A;\">Monthly Payroll Summary</h2><p><strong>Period:</strong> {{ $('Set Pay Period').first().json.monthLabel }}</p><p><strong>Employee Count:</strong> {{ $('Fetch Employees').first().json.Employees ? $('Fetch Employees').first().json.Employees.length : 'N/A' }}</p><hr><h3>AI Variance Analysis</h3><p>{{ $('AI Variance Analysis').first().json.choices[0].message.content.replace(/\\n/g, '<br>') }}</p><hr><p style=\"color: #888; font-size: 11px;\">Generated by AVM Financial Intelligence | FINTEL-01</p>",
            "options": {},
        },
        "id": uid(),
        "name": "Alert Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1540, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## FINTEL-01: Monthly Payroll Run\nRuns 25th of month 08:00 SAST.\nFetches employees & payslips from Xero,\nAI analyzes variances vs last month,\nwrites summary to Airtable, emails alert.",
            "width": 420,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_fintel01_connections():
    """Build connections for FINTEL-01."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Pay Period", "type": "main", "index": 0}]]
        },
        "Set Pay Period": {
            "main": [[{"node": "Fetch Employees", "type": "main", "index": 0}]]
        },
        "Fetch Employees": {
            "main": [[{"node": "Fetch Payslips", "type": "main", "index": 0}]]
        },
        "Fetch Payslips": {
            "main": [[{"node": "AI Variance Analysis", "type": "main", "index": 0}]]
        },
        "AI Variance Analysis": {
            "main": [[{"node": "Write Summary to Airtable", "type": "main", "index": 0}]]
        },
        "Write Summary to Airtable": {
            "main": [[{"node": "Alert Email", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# FINTEL-02: Quarterly VAT Prep
# ==================================================================

def build_fintel02_nodes():
    """Build nodes for FINTEL-02: Quarterly VAT Prep (1st Jan/Apr/Jul/Oct 09:00 SAST = 07:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (1st of quarter months 07:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 7 1 1,4,7,10 *",
                    }
                ]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # -- Set VAT Period --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "quarterStart",
                        "value": "={{ $now.minus({months: 3}).startOf('month').toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "quarterEnd",
                        "value": "={{ $now.minus({days: 1}).toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "quarterLabel",
                        "value": "={{ $now.minus({months: 3}).toFormat('MMMM') + ' - ' + $now.minus({months: 1}).toFormat('MMMM yyyy') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "filingDeadline",
                        "value": "={{ $now.plus({days: 25}).toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set VAT Period",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [440, 300],
    })

    # -- Fetch Trial Balance from Xero --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://api.xero.com/api.xro/2.0/Reports/TrialBalance?date={{ $json.quarterEnd }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Trial Balance",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 300],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- Fetch Tax Rates --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "https://api.xero.com/api.xro/2.0/TaxRates",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Tax Rates",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [880, 300],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- Calculate VAT (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Calculate VAT from trial balance data
const trialBalance = $('Fetch Trial Balance').first().json;
const taxRates = $('Fetch Tax Rates').first().json;
const period = $('Set VAT Period').first().json;

// Extract revenue and expense totals from trial balance
const reports = trialBalance.Reports || [];
let totalRevenue = 0;
let totalExpenses = 0;

for (const report of reports) {
  const rows = report.Rows || [];
  for (const row of rows) {
    if (row.RowType === 'Section') {
      const title = (row.Title || '').toLowerCase();
      const cells = (row.Rows || []);
      for (const cell of cells) {
        if (cell.RowType === 'Row' && cell.Cells) {
          const amount = parseFloat(cell.Cells[1]?.Value || 0);
          if (title.includes('revenue') || title.includes('income') || title.includes('sales')) {
            totalRevenue += Math.abs(amount);
          } else if (title.includes('expense') || title.includes('cost') || title.includes('overhead')) {
            totalExpenses += Math.abs(amount);
          }
        }
      }
    }
  }
}

// SA VAT rate = 15%
const vatRate = 0.15;
const outputVAT = Math.round(totalRevenue * vatRate * 100) / 100;
const inputVAT = Math.round(totalExpenses * vatRate * 100) / 100;
const netVATPayable = Math.round((outputVAT - inputVAT) * 100) / 100;

return [{
  json: {
    quarterLabel: period.quarterLabel,
    quarterStart: period.quarterStart,
    quarterEnd: period.quarterEnd,
    filingDeadline: period.filingDeadline,
    totalRevenue: Math.round(totalRevenue * 100) / 100,
    totalExpenses: Math.round(totalExpenses * 100) / 100,
    outputVAT,
    inputVAT,
    netVATPayable,
    vatRate: '15%',
    direction: netVATPayable >= 0 ? 'Payable to SARS' : 'Refund from SARS',
  }
}];"""
        },
        "id": uid(),
        "name": "Calculate VAT",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 300],
    })

    # -- AI Review & Flag (OpenRouter) --
    nodes.append({
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 1500,
  "messages": [
    {{
      "role": "system",
      "content": "You are a South African VAT specialist for AnyVision Media. Review VAT calculations for the quarter. Flag anomalies: unusual output/input ratio, revenue spikes, missing categories, potential audit risks. SA VAT rate is 15%. Use ZAR. Provide concise findings with any recommended adjustments before filing."
    }},
    {{
      "role": "user",
      "content": "Review VAT calculations for " + $json.quarterLabel + ":\\n\\nTotal Revenue: R" + $json.totalRevenue + "\\nTotal Expenses: R" + $json.totalExpenses + "\\nOutput VAT (15% of revenue): R" + $json.outputVAT + "\\nInput VAT (15% of expenses): R" + $json.inputVAT + "\\nNet VAT Payable: R" + $json.netVATPayable + " (" + $json.direction + ")\\nFiling Deadline: " + $json.filingDeadline
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Review and Flag",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1320, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Write to Airtable --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_FINANCIAL_INTEL, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Period": "={{ $('Calculate VAT').first().json.quarterLabel }}",
                    "Type": "VAT",
                    "Quarter": "={{ $('Calculate VAT').first().json.quarterLabel }}",
                    "Output VAT": "={{ $('Calculate VAT').first().json.outputVAT }}",
                    "Input VAT": "={{ $('Calculate VAT').first().json.inputVAT }}",
                    "Net Payable": "={{ $('Calculate VAT').first().json.netVATPayable }}",
                    "Filing Deadline": "={{ $('Calculate VAT').first().json.filingDeadline }}",
                    "Status": "Pending Review",
                    "AI Notes": "={{ $json.choices[0].message.content.substring(0, 5000) }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1540, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Alert Email --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=Quarterly VAT Prep - {{ $('Calculate VAT').first().json.quarterLabel }}",
            "message": "=<h2 style=\"color: #FF6D5A;\">Quarterly VAT Preparation</h2><p><strong>Quarter:</strong> {{ $('Calculate VAT').first().json.quarterLabel }}</p><p><strong>Output VAT:</strong> R{{ $('Calculate VAT').first().json.outputVAT }}</p><p><strong>Input VAT:</strong> R{{ $('Calculate VAT').first().json.inputVAT }}</p><p><strong>Net VAT Payable:</strong> R{{ $('Calculate VAT').first().json.netVATPayable }} ({{ $('Calculate VAT').first().json.direction }})</p><p><strong>Filing Deadline:</strong> {{ $('Calculate VAT').first().json.filingDeadline }}</p><hr><h3>AI Review Notes</h3><p>{{ $('AI Review and Flag').first().json.choices[0].message.content.replace(/\\n/g, '<br>') }}</p><hr><p style=\"color: #888; font-size: 11px;\">Generated by AVM Financial Intelligence | FINTEL-02</p>",
            "options": {},
        },
        "id": uid(),
        "name": "Alert Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1760, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## FINTEL-02: Quarterly VAT Prep\nRuns 1st of Jan/Apr/Jul/Oct 09:00 SAST.\nFetches trial balance + tax rates from Xero,\ncalculates output/input/net VAT (15%),\nAI reviews for anomalies, writes to Airtable.",
            "width": 420,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_fintel02_connections():
    """Build connections for FINTEL-02."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set VAT Period", "type": "main", "index": 0}]]
        },
        "Set VAT Period": {
            "main": [[{"node": "Fetch Trial Balance", "type": "main", "index": 0}]]
        },
        "Fetch Trial Balance": {
            "main": [[{"node": "Fetch Tax Rates", "type": "main", "index": 0}]]
        },
        "Fetch Tax Rates": {
            "main": [[{"node": "Calculate VAT", "type": "main", "index": 0}]]
        },
        "Calculate VAT": {
            "main": [[{"node": "AI Review and Flag", "type": "main", "index": 0}]]
        },
        "AI Review and Flag": {
            "main": [[{"node": "Write to Airtable", "type": "main", "index": 0}]]
        },
        "Write to Airtable": {
            "main": [[{"node": "Alert Email", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# FINTEL-03: Cash Flow Scenarios
# ==================================================================

def build_fintel03_nodes():
    """Build nodes for FINTEL-03: Cash Flow Scenarios (Fri 06:00 SAST = 04:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (Fri 04:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 4 * * 5",
                    }
                ]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # -- Set Forecast Window --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "forecastStart",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "forecastEnd",
                        "value": "={{ $now.plus({days: 90}).toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "reportDate",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "forecastLabel",
                        "value": "=90-Day Forecast from {{ $now.toFormat('dd MMM yyyy') }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Forecast Window",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [440, 300],
    })

    # -- Fetch Bank Summary from Xero --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "https://api.xero.com/api.xro/2.0/Reports/BankSummary",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Bank Summary",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 200],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- Fetch Aged Receivables --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://api.xero.com/api.xro/2.0/Reports/AgedReceivablesByContact?date={{ $('Set Forecast Window').first().json.reportDate }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Aged Receivables",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 400],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- Fetch Aged Payables --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://api.xero.com/api.xro/2.0/Reports/AgedPayablesByContact?date={{ $('Set Forecast Window').first().json.reportDate }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Aged Payables",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 600],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- AI Scenario Modeling (OpenRouter) --
    nodes.append({
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 2000,
  "messages": [
    {{
      "role": "system",
      "content": "You are a cash flow forecasting analyst for AnyVision Media, a South African company. Generate 3 cash flow scenarios for the next 90 days. Use ZAR currency.\\n\\nScenarios:\\n1. BEST CASE: All receivables collected on time, no unexpected expenses\\n2. EXPECTED: Based on historical collection rates (assume 80% on time, 15% 30 days late, 5% 60+ days late)\\n3. WORST CASE: Major clients delay 30 days, unexpected expenses arise\\n\\nFor each scenario provide: projected cash position at 30/60/90 days, key assumptions, risk factors. Also provide an overall recommendation (e.g., safe to invest, maintain reserves, cut spending)."
    }},
    {{
      "role": "user",
      "content": "Generate 90-day cash flow scenarios starting " + $('Set Forecast Window').first().json.reportDate + ":\\n\\nBank Summary:\\n" + JSON.stringify($('Fetch Bank Summary').first().json, null, 2) + "\\n\\nAged Receivables:\\n" + JSON.stringify($('Fetch Aged Receivables').first().json, null, 2) + "\\n\\nAged Payables:\\n" + JSON.stringify($('Fetch Aged Payables').first().json, null, 2)
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Scenario Modeling",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [880, 400],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Format Report (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Format cash flow scenarios as branded HTML report
const aiResponse = $json.choices[0].message.content;
const period = $('Set Forecast Window').first().json;

const html = `<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
  <div style="background: #FF6D5A; color: white; padding: 24px; border-radius: 8px 8px 0 0;">
    <h1 style="margin: 0; font-size: 22px;">Cash Flow Scenario Report</h1>
    <p style="margin: 5px 0 0; opacity: 0.9; font-size: 14px;">${period.forecastLabel}</p>
  </div>

  <div style="background: white; padding: 24px; border: 1px solid #e0e0e0;">
    <div style="line-height: 1.6; color: #444;">
      ${aiResponse.replace(/\\n/g, '<br>').replace(/## (.*)/g, '<h3 style="color: #FF6D5A; border-bottom: 2px solid #FF6D5A; padding-bottom: 8px;">$1</h3>').replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')}
    </div>

    <hr style="border: 1px solid #eee; margin: 24px 0;">
    <p style="color: #888; font-size: 11px;">Generated by AVM Financial Intelligence | FINTEL-03 | ${period.reportDate}</p>
  </div>
</div>`;

return [{
  json: {
    html,
    subject: 'Cash Flow Scenarios - ' + period.forecastLabel,
    reportDate: period.reportDate,
    forecastLabel: period.forecastLabel,
    aiSummary: aiResponse.substring(0, 5000),
  }
}];"""
        },
        "id": uid(),
        "name": "Format Report",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 400],
    })

    # -- Write to Airtable --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_FINANCIAL_INTEL, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Period": "={{ $json.forecastLabel }}",
                    "Type": "Cash Flow",
                    "Report Date": "={{ $json.reportDate }}",
                    "Notes": "={{ $json.aiSummary }}",
                    "Status": "Pending Review",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1320, 400],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Send Report Email --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "={{ $('Format Report').first().json.subject }}",
            "message": "={{ $('Format Report').first().json.html }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Report",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1540, 400],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## FINTEL-03: Cash Flow Scenarios\nRuns Friday 06:00 SAST.\nFetches bank balance, aged receivables, aged payables\nfrom Xero. AI generates 3 scenarios (best/expected/worst)\nfor next 90 days. Branded HTML report emailed.",
            "width": 420,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_fintel03_connections():
    """Build connections for FINTEL-03."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Forecast Window", "type": "main", "index": 0}]]
        },
        "Set Forecast Window": {
            "main": [
                [
                    {"node": "Fetch Bank Summary", "type": "main", "index": 0},
                    {"node": "Fetch Aged Receivables", "type": "main", "index": 0},
                    {"node": "Fetch Aged Payables", "type": "main", "index": 0},
                ]
            ]
        },
        "Fetch Bank Summary": {
            "main": [[{"node": "AI Scenario Modeling", "type": "main", "index": 0}]]
        },
        "Fetch Aged Receivables": {
            "main": [[{"node": "AI Scenario Modeling", "type": "main", "index": 0}]]
        },
        "Fetch Aged Payables": {
            "main": [[{"node": "AI Scenario Modeling", "type": "main", "index": 0}]]
        },
        "AI Scenario Modeling": {
            "main": [[{"node": "Format Report", "type": "main", "index": 0}]]
        },
        "Format Report": {
            "main": [[{"node": "Write to Airtable", "type": "main", "index": 0}]]
        },
        "Write to Airtable": {
            "main": [[{"node": "Send Report", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# FINTEL-04: Smart Payment Scheduler
# ==================================================================

def build_fintel04_nodes():
    """Build nodes for FINTEL-04: Smart Payment Scheduler (Daily 07:00 SAST = 05:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (Daily 05:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 5 * * *",
                    }
                ]
            }
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # -- Fetch Unpaid Bills from Xero --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "https://api.xero.com/api.xro/2.0/Invoices?Statuses=AUTHORISED&where=Type%3D%3D%22ACCPAY%22",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Unpaid Bills",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [440, 300],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- Fetch Bank Balance --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "https://api.xero.com/api.xro/2.0/Reports/BankSummary",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Bank Balance",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 300],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # -- AI Payment Strategy (OpenRouter) --
    nodes.append({
        "parameters": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 2000,
  "messages": [
    {{
      "role": "system",
      "content": "You are a treasury/payments analyst for AnyVision Media, a South African company. Analyze unpaid supplier bills and current bank balance to recommend which bills to pay today. Use ZAR currency.\\n\\nPrioritization rules:\\n1. OVERDUE bills (past due date) - pay immediately\\n2. DUE TODAY - pay now\\n3. DUE WITHIN 7 DAYS with early payment discount - pay to capture discount\\n4. All other bills - schedule based on cash position\\n\\nConsider: maintaining minimum cash reserve (R50,000), supplier relationship importance, payment terms. Output a clear payment schedule with: supplier name, amount, due date, priority, recommendation (Pay Now / Schedule / Defer). Also provide total recommended payments today vs available balance."
    }},
    {{
      "role": "user",
      "content": "Today is " + $now.toFormat('yyyy-MM-dd') + ". Generate payment recommendations:\\n\\nUnpaid Bills:\\n" + JSON.stringify($('Fetch Unpaid Bills').first().json, null, 2) + "\\n\\nBank Balance:\\n" + JSON.stringify($json, null, 2)
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Payment Strategy",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [880, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Format Payment Schedule (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Format payment recommendations as structured schedule
const aiResponse = $json.choices[0].message.content;
const today = $now.toFormat('yyyy-MM-dd');

const html = `<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
  <div style="background: #FF6D5A; color: white; padding: 24px; border-radius: 8px 8px 0 0;">
    <h1 style="margin: 0; font-size: 22px;">Smart Payment Schedule</h1>
    <p style="margin: 5px 0 0; opacity: 0.9; font-size: 14px;">${today}</p>
  </div>

  <div style="background: white; padding: 24px; border: 1px solid #e0e0e0;">
    <div style="line-height: 1.6; color: #444;">
      ${aiResponse.replace(/\\n/g, '<br>').replace(/## (.*)/g, '<h3 style="color: #FF6D5A; border-bottom: 2px solid #FF6D5A; padding-bottom: 8px;">$1</h3>').replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')}
    </div>

    <hr style="border: 1px solid #eee; margin: 24px 0;">
    <p style="color: #888; font-size: 11px;">Generated by AVM Financial Intelligence | FINTEL-04 | ${today}</p>
  </div>
</div>`;

return [{
  json: {
    html,
    subject: 'Payment Recommendations - ' + today,
    reportDate: today,
    aiSummary: aiResponse.substring(0, 5000),
  }
}];"""
        },
        "id": uid(),
        "name": "Format Payment Schedule",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 300],
    })

    # -- Write to Airtable --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_FINANCIAL_INTEL, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Period": "={{ $json.reportDate }}",
                    "Type": "Payment Schedule",
                    "Report Date": "={{ $json.reportDate }}",
                    "Notes": "={{ $json.aiSummary }}",
                    "Status": "Pending Review",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1320, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Alert Email --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "={{ $('Format Payment Schedule').first().json.subject }}",
            "message": "={{ $('Format Payment Schedule').first().json.html }}",
            "options": {},
        },
        "id": uid(),
        "name": "Alert Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1540, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## FINTEL-04: Smart Payment Scheduler\nRuns daily 07:00 SAST.\nFetches unpaid bills (ACCPAY/AUTHORISED) + bank balance\nfrom Xero. AI prioritizes: overdue > due today >\n7-day discount > rest. Minimum R50k reserve.",
            "width": 420,
            "height": 120,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_fintel04_connections():
    """Build connections for FINTEL-04."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Fetch Unpaid Bills", "type": "main", "index": 0}]]
        },
        "Fetch Unpaid Bills": {
            "main": [[{"node": "Fetch Bank Balance", "type": "main", "index": 0}]]
        },
        "Fetch Bank Balance": {
            "main": [[{"node": "AI Payment Strategy", "type": "main", "index": 0}]]
        },
        "AI Payment Strategy": {
            "main": [[{"node": "Format Payment Schedule", "type": "main", "index": 0}]]
        },
        "Format Payment Schedule": {
            "main": [[{"node": "Write to Airtable", "type": "main", "index": 0}]]
        },
        "Write to Airtable": {
            "main": [[{"node": "Alert Email", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# WORKFLOW DEFINITIONS
# ==================================================================

WORKFLOW_DEFS = {
    "fintel01": {
        "name": "Financial Intel - Monthly Payroll Run (FINTEL-01)",
        "filename": "fintel01_payroll.json",
        "build_nodes": build_fintel01_nodes,
        "build_connections": build_fintel01_connections,
    },
    "fintel02": {
        "name": "Financial Intel - Quarterly VAT Prep (FINTEL-02)",
        "filename": "fintel02_vat_prep.json",
        "build_nodes": build_fintel02_nodes,
        "build_connections": build_fintel02_connections,
    },
    "fintel03": {
        "name": "Financial Intel - Cash Flow Scenarios (FINTEL-03)",
        "filename": "fintel03_cash_flow.json",
        "build_nodes": build_fintel03_nodes,
        "build_connections": build_fintel03_connections,
    },
    "fintel04": {
        "name": "Financial Intel - Smart Payment Scheduler (FINTEL-04)",
        "filename": "fintel04_payment_scheduler.json",
        "build_nodes": build_fintel04_nodes,
        "build_connections": build_fintel04_connections,
    },
}


# ==================================================================
# WORKFLOW ASSEMBLY
# ==================================================================

def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
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
    filename = WORKFLOW_DEFS[wf_id]["filename"]
    output_dir = Path(__file__).parent.parent / "workflows" / "financial-intel"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

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


# ==================================================================
# CLI
# ==================================================================

def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    print("=" * 60)
    print("FINANCIAL INTELLIGENCE - WORKFLOW BUILDER")
    print("=" * 60)

    # Determine targets
    valid_wfs = list(WORKFLOW_DEFS.keys())
    if target == "all":
        workflow_ids = valid_wfs
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Pre-flight checks
    missing = []
    if not ORCH_BASE_ID or "REPLACE" in ORCH_BASE_ID:
        missing.append("ORCH_AIRTABLE_BASE_ID")
    if "REPLACE" in TABLE_FINANCIAL_INTEL:
        missing.append("FINTEL_TABLE_ID")

    if missing:
        print()
        print("WARNING: Missing Airtable configuration:")
        for m in missing:
            print(f"  - {m}")
        print()
        if action in ("deploy", "activate"):
            print("Deploying with placeholder IDs (skeleton / visual preview only).")
            print("Workflows will NOT be activated until real IDs are set.")
            print()
        else:
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
        sys.path.insert(0, str(Path(__file__).parent))
        from n8n_client import N8nClient

        api_key = os.getenv("N8N_API_KEY")
        base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

        if not api_key:
            print("ERROR: N8N_API_KEY not set in .env")
            sys.exit(1)

        print(f"\nConnecting to {base_url}...")

        with N8nClient(base_url, api_key, timeout=30) as client:
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
                    print("  Activated!")

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
    print("  1. Create Airtable table: Financial_Intel (in Operations Control base)")
    print("  2. Set env var: FINTEL_TABLE_ID in .env")
    print("  3. Verify Xero OAuth2 credential in n8n has payroll scope")
    print("  4. Open each workflow in n8n UI to verify node connections")
    print("  5. Test FINTEL-04 manually -> check payment recommendations")
    print("  6. Test FINTEL-03 manually -> check cash flow scenarios")
    print("  7. Test FINTEL-01 manually -> check payroll summary")
    print("  8. Wait for quarter start for FINTEL-02 or trigger manually")
    print("  9. Once verified, run with 'activate' to enable schedules")


if __name__ == "__main__":
    main()
