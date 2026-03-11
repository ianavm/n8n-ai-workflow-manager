"""
AVM Autonomous Operations - Finance Agent Workflow Builder & Deployer

Builds 2 finance agent workflows for cash flow forecasting and anomaly detection.

Workflows:
    FIN-08: Cash Flow Forecast (Fri 16:00 SAST) - Fetch Xero P&L + invoices, AI 30/60/90 day forecast
    FIN-09: Anomaly Detector (Daily 07:00 SAST) - Detect unusual transactions, duplicates, high-value vendors

Usage:
    python tools/deploy_finance_agent.py build              # Build all JSONs
    python tools/deploy_finance_agent.py build fin08         # Build FIN-08 only
    python tools/deploy_finance_agent.py deploy             # Build + Deploy (inactive)
    python tools/deploy_finance_agent.py activate           # Build + Deploy + Activate
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

# -- Credential Constants --
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail AVM"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable PAT"}
CRED_N8N_API = {"id": "xymp9Nho08mRW2Wz", "name": "n8n API Key"}
CRED_XERO = {"id": "YOUR_XERO_CRED_ID", "name": "Xero OAuth2"}  # placeholder

# -- Airtable IDs --
ACCOUNTING_BASE_ID = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "")
TABLE_INVOICES = os.getenv("ACCOUNTING_TABLE_INVOICES", "")
TABLE_PAYMENTS = os.getenv("ACCOUNTING_TABLE_PAYMENTS", "")
TABLE_CASH_FLOW_FORECASTS = os.getenv("ACCOUNTING_TABLE_CASH_FLOW_FORECASTS", "")

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"
XERO_TENANT_ID = "1f5c5e97-8976-4e03-b33c-ba638a7aeb72"


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

FIN08_FETCH_XERO_PL_CODE = r"""
// Fetch Xero Profit & Loss report via HTTP
// This node prepares the request params for the downstream HTTP node
const today = new Date();
const fromDate = new Date(today);
fromDate.setDate(fromDate.getDate() - 90);

const formatDate = (d) => d.toISOString().split('T')[0];

return {
  json: {
    fromDate: formatDate(fromDate),
    toDate: formatDate(today),
    periods: 3,
    timeframe: 'MONTH',
    endpoint: 'https://api.xero.com/api.xro/2.0/Reports/ProfitAndLoss',
    queryParams: `?fromDate=${formatDate(fromDate)}&toDate=${formatDate(today)}&periods=3&timeframe=MONTH`,
    fetchedAt: today.toISOString(),
  }
};
""".strip()

FIN08_SUMMARIZE_INVOICES_CODE = r"""
// Fetch upcoming invoices from Airtable and summarize for forecast
const invoiceItems = $('Read Upcoming Invoices').all();

const summary = {
  totalInvoices: invoiceItems.length,
  totalOwed: 0,
  totalDue30: 0,
  totalDue60: 0,
  totalDue90: 0,
  invoicesByStatus: {},
  topDebtors: [],
};

const today = new Date();
const debtorTotals = {};

for (const item of invoiceItems) {
  const d = item.json;
  const amount = parseFloat(d.Amount || d['Amount Due'] || d.Total || 0);
  const status = d.Status || 'Unknown';
  const dueDate = d['Due Date'] ? new Date(d['Due Date']) : null;
  const contact = d.Contact || d.Customer || d['Client Name'] || 'Unknown';

  summary.totalOwed += amount;
  summary.invoicesByStatus[status] = (summary.invoicesByStatus[status] || 0) + 1;

  // Bucket by days until due
  if (dueDate) {
    const daysUntilDue = Math.ceil((dueDate - today) / (1000 * 60 * 60 * 24));
    if (daysUntilDue <= 30) summary.totalDue30 += amount;
    else if (daysUntilDue <= 60) summary.totalDue60 += amount;
    else if (daysUntilDue <= 90) summary.totalDue90 += amount;
  }

  // Track debtor totals
  debtorTotals[contact] = (debtorTotals[contact] || 0) + amount;
}

// Top 5 debtors
summary.topDebtors = Object.entries(debtorTotals)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 5)
  .map(([name, total]) => ({ name, total: Math.round(total * 100) / 100 }));

summary.totalOwed = Math.round(summary.totalOwed * 100) / 100;
summary.totalDue30 = Math.round(summary.totalDue30 * 100) / 100;
summary.totalDue60 = Math.round(summary.totalDue60 * 100) / 100;
summary.totalDue90 = Math.round(summary.totalDue90 * 100) / 100;

return { json: summary };
""".strip()

FIN09_FETCH_TRANSACTIONS_CODE = r"""
// Prepare Xero bank transaction request parameters
const today = new Date();
const fromDate = new Date(today);
fromDate.setDate(fromDate.getDate() - 7);

const formatDate = (d) => d.toISOString().split('T')[0];

return {
  json: {
    fromDate: formatDate(fromDate),
    toDate: formatDate(today),
    endpoint: 'https://api.xero.com/api.xro/2.0/BankTransactions',
    queryParams: `?where=Date>=DateTime(${fromDate.getFullYear()},${fromDate.getMonth()+1},${fromDate.getDate()})&order=Date DESC`,
    fetchedAt: today.toISOString(),
  }
};
""".strip()

FIN09_ANALYZE_ANOMALIES_CODE = r"""
// Analyze transactions for anomalies: unusual amounts, duplicates, new high-value vendors
const transactions = $('Fetch Xero Transactions').first().json;

// Parse transactions from Xero response (or use mock data if empty)
const txnList = (transactions.BankTransactions || transactions.data || []);

const anomalies = [];
const vendorTotals = {};
const seen = new Set();

for (const txn of txnList) {
  const amount = Math.abs(parseFloat(txn.Total || txn.Amount || 0));
  const vendor = txn.Contact?.Name || txn.Reference || 'Unknown';
  const date = txn.Date || txn.DateString || '';
  const txnId = txn.BankTransactionID || '';

  // Track vendor spending
  vendorTotals[vendor] = (vendorTotals[vendor] || 0) + amount;

  // Check for duplicates (same amount + vendor within the batch)
  const dupeKey = `${vendor}_${amount.toFixed(2)}`;
  if (seen.has(dupeKey)) {
    anomalies.push({
      type: 'duplicate',
      severity: 'Warning',
      vendor,
      amount,
      date,
      description: `Possible duplicate: R${amount.toFixed(2)} to ${vendor}`,
    });
  }
  seen.add(dupeKey);

  // Unusual amount: over R50,000 single transaction
  if (amount > 50000) {
    anomalies.push({
      type: 'high_value',
      severity: 'Critical',
      vendor,
      amount,
      date,
      description: `High-value transaction: R${amount.toFixed(2)} to ${vendor}`,
    });
  } else if (amount > 20000) {
    anomalies.push({
      type: 'elevated_value',
      severity: 'Warning',
      vendor,
      amount,
      date,
      description: `Elevated transaction: R${amount.toFixed(2)} to ${vendor}`,
    });
  }
}

// New high-value vendors (>R100k total in period)
for (const [vendor, total] of Object.entries(vendorTotals)) {
  if (total > 100000) {
    anomalies.push({
      type: 'high_value_vendor',
      severity: 'Warning',
      vendor,
      amount: total,
      date: '',
      description: `High cumulative spend: R${total.toFixed(2)} to ${vendor} in period`,
    });
  }
}

// Determine overall severity
let overallSeverity = 'Normal';
if (anomalies.some(a => a.severity === 'Critical')) overallSeverity = 'Critical';
else if (anomalies.some(a => a.severity === 'Warning')) overallSeverity = 'Warning';

return {
  json: {
    overallSeverity,
    anomalyCount: anomalies.length,
    anomalies,
    transactionCount: txnList.length,
    vendorCount: Object.keys(vendorTotals).length,
    analyzedAt: new Date().toISOString(),
  }
};
""".strip()


# ======================================================================
# FIN-08: Cash Flow Forecast
# ======================================================================

def build_fin08_nodes():
    """Build nodes for FIN-08: Cash Flow Forecast (Fri 16:00 SAST = 14:00 UTC)."""
    nodes = []

    # 1. Schedule Trigger (Fri 16:00 SAST = 14:00 UTC)
    nodes.append({
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 14 * * 5"}]}
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Prepare Xero P&L Request (Code node)
    nodes.append({
        "parameters": {"jsCode": FIN08_FETCH_XERO_PL_CODE},
        "id": uid(),
        "name": "Prepare Xero P&L",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [460, 200],
    })

    # 3. Fetch Xero P&L (HTTP Request to Xero API)
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://api.xero.com/api.xro/2.0/Reports/ProfitAndLoss{{ $json.queryParams }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                    {"name": "Accept", "value": "application/json"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Xero P&L",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [700, 200],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # 4. Read Upcoming Invoices (Airtable search - outstanding invoices within 90 days)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ACCOUNTING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_INVOICES, "mode": "id"},
            "filterByFormula": "=AND({Status} != 'Paid', IS_BEFORE({Due Date}, DATEADD(TODAY(), 90, 'days')))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Upcoming Invoices",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [460, 420],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 5. Summarize Invoice Data (Code node)
    nodes.append({
        "parameters": {"jsCode": FIN08_SUMMARIZE_INVOICES_CODE},
        "id": uid(),
        "name": "Summarize Invoices",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [700, 420],
    })

    # 6. AI Forecast (OpenRouter - Claude Sonnet)
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514",
  "max_tokens": 2000,
  "messages": [
    {
      "role": "system",
      "content": "You are the AVM Finance Intelligence Agent. Generate a 30/60/90 day cash flow forecast based on Xero P&L data and outstanding invoices. Include: 1) Current cash position summary, 2) Expected inflows by period (30/60/90 days), 3) Expected outflows by period, 4) Net cash position forecast per period, 5) Risk flags (concentration risk, overdue receivables, seasonal patterns). Format with clear tables. Currency is ZAR (R). Keep under 600 words."
    },
    {
      "role": "user",
      "content": "Xero Profit & Loss (last 3 months):\\n{{ JSON.stringify($('Fetch Xero P&L').first().json) }}\\n\\nOutstanding Invoices Summary:\\nTotal owed: R{{ $('Summarize Invoices').first().json.totalOwed }}\\nDue within 30 days: R{{ $('Summarize Invoices').first().json.totalDue30 }}\\nDue 31-60 days: R{{ $('Summarize Invoices').first().json.totalDue60 }}\\nDue 61-90 days: R{{ $('Summarize Invoices').first().json.totalDue90 }}\\nTop debtors: {{ JSON.stringify($('Summarize Invoices').first().json.topDebtors) }}\\n\\nGenerate 30/60/90 day cash flow forecast."
    }
  ]
}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Cash Flow Forecast",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [960, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # 7. Save Forecast to Airtable (create record in Cash_Flow_Forecasts table)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ACCOUNTING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CASH_FLOW_FORECASTS, "mode": "id"},
            "columns": {
                "value": {
                    "Forecast Date": "={{ $now.format('yyyy-MM-dd') }}",
                    "Forecast Period": "30/60/90 day",
                    "Total Receivable": "={{ $('Summarize Invoices').first().json.totalOwed }}",
                    "Due 30 Days": "={{ $('Summarize Invoices').first().json.totalDue30 }}",
                    "Due 60 Days": "={{ $('Summarize Invoices').first().json.totalDue60 }}",
                    "Due 90 Days": "={{ $('Summarize Invoices').first().json.totalDue90 }}",
                    "AI Forecast": "={{ $json.choices[0].message.content }}",
                    "Status": "Generated",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Save Forecast",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1200, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 8. Send Summary Email
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=AVM Cash Flow Forecast - {{ $now.format('yyyy-MM-dd') }}",
            "emailType": "html",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<div style="background: #FF6D5A; padding: 20px; text-align: center;">
<h1 style="color: white; margin: 0;">Cash Flow Forecast</h1>
<p style="color: white; margin: 5px 0;">30 / 60 / 90 Day Outlook</p>
</div>
<div style="padding: 20px;">
<h2 style="color: #333;">AI Forecast</h2>
<div style="background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 20px; white-space: pre-wrap;">{{ $('AI Cash Flow Forecast').first().json.choices[0].message.content }}</div>
<h2 style="color: #333;">Receivables Summary</h2>
<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
<tr style="background: #f0f0f0;"><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Outstanding</strong></td><td style="padding: 8px; border: 1px solid #ddd; text-align: right;">R{{ $('Summarize Invoices').first().json.totalOwed }}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Due within 30 days</td><td style="padding: 8px; border: 1px solid #ddd; text-align: right;">R{{ $('Summarize Invoices').first().json.totalDue30 }}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Due 31-60 days</td><td style="padding: 8px; border: 1px solid #ddd; text-align: right;">R{{ $('Summarize Invoices').first().json.totalDue60 }}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Due 61-90 days</td><td style="padding: 8px; border: 1px solid #ddd; text-align: right;">R{{ $('Summarize Invoices').first().json.totalDue90 }}</td></tr>
</table>
<h2 style="color: #333;">Top Debtors</h2>
<ul>{{ $('Summarize Invoices').first().json.topDebtors.map(d => '<li>' + d.name + ': R' + d.total + '</li>').join('') }}</ul>
</div>
<div style="background: #f0f0f0; padding: 15px; text-align: center; font-size: 12px; color: #666;">
Generated by AVM Finance Agent | {{ $now.format('yyyy-MM-dd HH:mm') }}
</div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Send Forecast Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1440, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_fin08_connections(nodes):
    """Build connections for FIN-08."""
    return {
        "Schedule Trigger": {"main": [
            [
                {"node": "Prepare Xero P&L", "type": "main", "index": 0},
                {"node": "Read Upcoming Invoices", "type": "main", "index": 0},
            ],
        ]},
        "Prepare Xero P&L": {"main": [[{"node": "Fetch Xero P&L", "type": "main", "index": 0}]]},
        "Read Upcoming Invoices": {"main": [[{"node": "Summarize Invoices", "type": "main", "index": 0}]]},
        "Fetch Xero P&L": {"main": [[{"node": "AI Cash Flow Forecast", "type": "main", "index": 0}]]},
        "Summarize Invoices": {"main": [[{"node": "AI Cash Flow Forecast", "type": "main", "index": 0}]]},
        "AI Cash Flow Forecast": {"main": [[{"node": "Save Forecast", "type": "main", "index": 0}]]},
        "Save Forecast": {"main": [[{"node": "Send Forecast Email", "type": "main", "index": 0}]]},
    }


# ======================================================================
# FIN-09: Anomaly Detector
# ======================================================================

def build_fin09_nodes():
    """Build nodes for FIN-09: Anomaly Detector (Daily 07:00 SAST = 05:00 UTC)."""
    nodes = []

    # 1. Schedule Trigger (Daily 07:00 SAST = 05:00 UTC)
    nodes.append({
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 5 * * *"}]}
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Prepare Xero Transaction Request (Code node)
    nodes.append({
        "parameters": {"jsCode": FIN09_FETCH_TRANSACTIONS_CODE},
        "id": uid(),
        "name": "Prepare Txn Request",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [460, 300],
    })

    # 3. Fetch Xero Transactions (HTTP Request)
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": "=https://api.xero.com/api.xro/2.0/BankTransactions{{ $json.queryParams }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "xeroOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "xero-tenant-id", "value": XERO_TENANT_ID},
                    {"name": "Accept", "value": "application/json"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Xero Transactions",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [700, 300],
        "credentials": {"xeroOAuth2Api": CRED_XERO},
    })

    # 4. Analyze Anomalies (Code node)
    nodes.append({
        "parameters": {"jsCode": FIN09_ANALYZE_ANOMALIES_CODE},
        "id": uid(),
        "name": "Analyze Anomalies",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [940, 300],
    })

    # 5. Switch: Normal / Warning / Critical
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.overallSeverity }}",
                                    "rightValue": "Critical",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "Critical",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.overallSeverity }}",
                                    "rightValue": "Warning",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "Warning",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.overallSeverity }}",
                                    "rightValue": "Normal",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "Normal",
                    },
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Severity Switch",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [1180, 300],
    })

    # 6. Log Normal (Airtable create - just log, no alert)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ACCOUNTING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_PAYMENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Check Date": "={{ $now.format('yyyy-MM-dd') }}",
                    "Status": "Normal",
                    "Anomaly Count": "=0",
                    "Transactions Scanned": "={{ $('Analyze Anomalies').first().json.transactionCount }}",
                    "Notes": "No anomalies detected. All transactions within normal parameters.",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Normal",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1440, 500],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 7. Log Warning (Airtable create)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ACCOUNTING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_PAYMENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Check Date": "={{ $now.format('yyyy-MM-dd') }}",
                    "Status": "Warning",
                    "Anomaly Count": "={{ $('Analyze Anomalies').first().json.anomalyCount }}",
                    "Transactions Scanned": "={{ $('Analyze Anomalies').first().json.transactionCount }}",
                    "Notes": "={{ $('Analyze Anomalies').first().json.anomalies.map(a => a.description).join('; ') }}",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Warning",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1440, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 8. Send Warning Email
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=AVM Finance Alert (Warning) - {{ $now.format('yyyy-MM-dd') }}",
            "emailType": "html",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<div style="background: #FFA500; padding: 20px; text-align: center;">
<h1 style="color: white; margin: 0;">Finance Anomaly Alert</h1>
<p style="color: white; margin: 5px 0;">Severity: WARNING</p>
</div>
<div style="padding: 20px;">
<h2 style="color: #333;">Anomalies Detected</h2>
<p><strong>{{ $('Analyze Anomalies').first().json.anomalyCount }}</strong> anomalies found in <strong>{{ $('Analyze Anomalies').first().json.transactionCount }}</strong> transactions.</p>
<ul>{{ $('Analyze Anomalies').first().json.anomalies.map(a => '<li style="margin-bottom: 8px;"><strong>[' + a.severity + ']</strong> ' + a.description + '</li>').join('') }}</ul>
</div>
<div style="background: #f0f0f0; padding: 15px; text-align: center; font-size: 12px; color: #666;">
Generated by AVM Finance Agent | {{ $now.format('yyyy-MM-dd HH:mm') }}
</div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Send Warning Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1680, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # 9. Log Critical (Airtable create - escalation record)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ACCOUNTING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_PAYMENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Check Date": "={{ $now.format('yyyy-MM-dd') }}",
                    "Status": "Critical",
                    "Anomaly Count": "={{ $('Analyze Anomalies').first().json.anomalyCount }}",
                    "Transactions Scanned": "={{ $('Analyze Anomalies').first().json.transactionCount }}",
                    "Notes": "=ESCALATION: {{ $('Analyze Anomalies').first().json.anomalies.map(a => a.description).join('; ') }}",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Critical",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1440, 100],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 10. Send Urgent Email
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=URGENT: AVM Finance Anomaly (Critical) - {{ $now.format('yyyy-MM-dd') }}",
            "emailType": "html",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<div style="background: #DC3545; padding: 20px; text-align: center;">
<h1 style="color: white; margin: 0;">CRITICAL Finance Alert</h1>
<p style="color: white; margin: 5px 0;">Immediate Attention Required</p>
</div>
<div style="padding: 20px;">
<h2 style="color: #DC3545;">Critical Anomalies Detected</h2>
<p><strong>{{ $('Analyze Anomalies').first().json.anomalyCount }}</strong> anomalies found in <strong>{{ $('Analyze Anomalies').first().json.transactionCount }}</strong> transactions.</p>
<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
<tr style="background: #f8d7da;"><th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Type</th><th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Vendor</th><th style="padding: 8px; border: 1px solid #ddd; text-align: right;">Amount</th><th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Details</th></tr>
{{ $('Analyze Anomalies').first().json.anomalies.map(a => '<tr><td style="padding: 8px; border: 1px solid #ddd;">' + a.type + '</td><td style="padding: 8px; border: 1px solid #ddd;">' + a.vendor + '</td><td style="padding: 8px; border: 1px solid #ddd; text-align: right;">R' + (a.amount || 0).toFixed(2) + '</td><td style="padding: 8px; border: 1px solid #ddd;">' + a.description + '</td></tr>').join('') }}
</table>
<p style="color: #DC3545; font-weight: bold;">Please review these transactions immediately.</p>
</div>
<div style="background: #f0f0f0; padding: 15px; text-align: center; font-size: 12px; color: #666;">
Generated by AVM Finance Agent | {{ $now.format('yyyy-MM-dd HH:mm') }}
</div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Send Urgent Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1680, 100],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_fin09_connections(nodes):
    """Build connections for FIN-09."""
    return {
        "Schedule Trigger": {"main": [[{"node": "Prepare Txn Request", "type": "main", "index": 0}]]},
        "Prepare Txn Request": {"main": [[{"node": "Fetch Xero Transactions", "type": "main", "index": 0}]]},
        "Fetch Xero Transactions": {"main": [[{"node": "Analyze Anomalies", "type": "main", "index": 0}]]},
        "Analyze Anomalies": {"main": [[{"node": "Severity Switch", "type": "main", "index": 0}]]},
        "Severity Switch": {"main": [
            [{"node": "Log Critical", "type": "main", "index": 0}],
            [{"node": "Log Warning", "type": "main", "index": 0}],
            [{"node": "Log Normal", "type": "main", "index": 0}],
        ]},
        "Log Normal": {"main": []},
        "Log Warning": {"main": [[{"node": "Send Warning Email", "type": "main", "index": 0}]]},
        "Log Critical": {"main": [[{"node": "Send Urgent Email", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "fin08": {
        "name": "FIN-08 Cash Flow Forecast",
        "build_nodes": build_fin08_nodes,
        "build_connections": build_fin08_connections,
        "filename": "fin08_cash_flow_forecast.json",
        "tags": ["finance", "cash-flow", "forecast", "auto-ops"],
    },
    "fin09": {
        "name": "FIN-09 Anomaly Detector",
        "build_nodes": build_fin09_nodes,
        "build_connections": build_fin09_connections,
        "filename": "fin09_anomaly_detector.json",
        "tags": ["finance", "anomaly", "detection", "auto-ops"],
    },
}


def build_workflow_json(key):
    """Build a complete n8n workflow JSON for a given workflow key."""
    builder = WORKFLOW_BUILDERS[key]
    nodes = builder["build_nodes"]()
    connections = builder["build_connections"](nodes)

    return {
        "name": builder["name"],
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "tags": builder["tags"],
        "meta": {
            "templateCredsSetupCompleted": True,
            "builder": "deploy_finance_agent.py",
            "built_at": datetime.now().isoformat(),
        },
    }


def save_workflow(key, workflow_json):
    """Save workflow JSON to disk."""
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "finance-agent"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / builder["filename"]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)

    node_count = len(workflow_json["nodes"])
    print(f"  + {builder['name']:<40} ({node_count} nodes) -> {output_path}")
    return output_path


def deploy_workflow(key, workflow_json, activate=False):
    """Deploy workflow to n8n Cloud."""
    from n8n_client import N8nClient

    client = N8nClient()
    builder = WORKFLOW_BUILDERS[key]

    # Create workflow
    resp = client.create_workflow(workflow_json)
    if resp and "id" in resp:
        wf_id = resp["id"]
        print(f"  + {builder['name']:<40} Deployed -> {wf_id}")

        if activate:
            import time
            time.sleep(2)
            client.activate_workflow(wf_id)
            print(f"    Activated: {wf_id}")

        return wf_id
    else:
        print(f"  - {builder['name']:<40} FAILED to deploy")
        return None


def main():
    if len(sys.argv) < 2:
        print("AVM Finance Agent - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_finance_agent.py build              # Build all")
        print("  python tools/deploy_finance_agent.py build fin08        # Build one")
        print("  python tools/deploy_finance_agent.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_finance_agent.py activate           # Build + Deploy + Activate")
        print()
        print("Workflows:")
        for key, builder in WORKFLOW_BUILDERS.items():
            print(f"  {key:<12} {builder['name']}")
        sys.exit(0)

    action = sys.argv[1].lower()
    target = sys.argv[2].lower() if len(sys.argv) > 2 else "all"

    # Determine which workflows to build
    if target == "all":
        keys = list(WORKFLOW_BUILDERS.keys())
    elif target in WORKFLOW_BUILDERS:
        keys = [target]
    else:
        print(f"Unknown workflow: {target}")
        print(f"Valid: {', '.join(WORKFLOW_BUILDERS.keys())}")
        sys.exit(1)

    print("=" * 60)
    print("AVM FINANCE AGENT - WORKFLOW BUILDER")
    print("=" * 60)
    print()
    print(f"Action: {action}")
    print(f"Workflows: {', '.join(keys)}")
    print()

    if action == "build":
        print("Building workflow JSONs...")
        print("-" * 40)
        for key in keys:
            wf_json = build_workflow_json(key)
            save_workflow(key, wf_json)
        print()
        print("Build complete. Inspect workflows in: workflows/finance-agent/")

    elif action in ("deploy", "activate"):
        do_activate = action == "activate"
        print(f"Building and deploying ({'+ activating' if do_activate else 'inactive'})...")
        print("-" * 40)

        deployed_ids = {}
        for key in keys:
            wf_json = build_workflow_json(key)
            save_workflow(key, wf_json)
            wf_id = deploy_workflow(key, wf_json, activate=do_activate)
            if wf_id:
                deployed_ids[key] = wf_id

        print()
        if deployed_ids:
            print("Deployed Workflow IDs:")
            for key, wf_id in deployed_ids.items():
                print(f"  {key}: {wf_id}")

    else:
        print(f"Unknown action: {action}")
        print("Valid: build, deploy, activate")
        sys.exit(1)


if __name__ == "__main__":
    main()
