"""
Intelligence Layer - Workflow Builder & Deployer

Builds 3 intelligence workflows for cross-department analytics,
executive reporting, and prompt performance tracking.

Workflows:
    INTEL-01: Cross-Dept Correlator (Mon 06:00 SAST)
    INTEL-02: Executive Report (Monthly 1st 08:00 SAST)
    INTEL-03: Prompt Performance Tracker (Daily 23:00 SAST)

Usage:
    python tools/deploy_intelligence.py build              # Build all JSONs
    python tools/deploy_intelligence.py build intel01      # Build INTEL-01 only
    python tools/deploy_intelligence.py build intel02      # Build INTEL-02 only
    python tools/deploy_intelligence.py build intel03      # Build INTEL-03 only
    python tools/deploy_intelligence.py deploy             # Build + Deploy (inactive)
    python tools/deploy_intelligence.py activate           # Build + Deploy + Activate
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
CRED_N8N_API = {"id": "xymp9Nho08mRW2Wz", "name": "n8n API Key"}

# -- Airtable IDs ---------------------------------------------------------

ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "")
TABLE_KPI_SNAPSHOTS = os.getenv("ORCH_TABLE_KPI_SNAPSHOTS", "REPLACE_AFTER_SETUP")
TABLE_INTELLIGENCE_REPORTS = os.getenv("ORCH_TABLE_INTELLIGENCE_REPORTS", "REPLACE_AFTER_SETUP")
TABLE_PROMPT_PERFORMANCE = os.getenv("ORCH_TABLE_PROMPT_PERFORMANCE", "REPLACE_AFTER_SETUP")

# -- AI Config ------------------------------------------------------------

AI_MODEL = "anthropic/claude-sonnet-4-20250514"

# -- Helpers ---------------------------------------------------------------


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# INTEL-01: Cross-Dept Correlator
# ==================================================================

def build_intel01_nodes():
    """Build nodes for INTEL-01: Cross-Dept Correlator (Mon 06:00 SAST = 04:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (Mon 04:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 4 * * 1",
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

    # -- Set Date Range --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "cutoffDate",
                        "value": "={{ $now.minus({days: 28}).toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "reportDate",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Date Range",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [420, 300],
    })

    # -- Read KPI Snapshots (last 28 days) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_KPI_SNAPSHOTS, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Snapshot Date}, '{{ $json.cutoffDate }}')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read KPI Snapshots",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [640, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Compute Correlations (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Compute cross-department correlations from KPI snapshots
const snapshots = $input.all().map(i => i.json);

// Group by date, sum metrics across agents
const byDate = {};
const metrics = ['Content Published', 'Leads Generated', 'Emails Sent',
                 'Revenue ZAR', 'Messages Handled', 'Tickets Resolved',
                 'Success Rate', 'Token Usage'];

for (const snap of snapshots) {
  const date = snap['Snapshot Date'] || 'unknown';
  if (!byDate[date]) {
    byDate[date] = {};
    for (const m of metrics) byDate[date][m] = 0;
  }
  for (const m of metrics) {
    byDate[date][m] += parseFloat(snap[m] || 0);
  }
}

const dates = Object.keys(byDate).sort();
if (dates.length < 5) {
  return [{ json: { error: 'Insufficient data', dataPoints: dates.length, correlations: [] } }];
}

// Build time series
const series = {};
for (const m of metrics) {
  series[m] = dates.map(d => byDate[d][m]);
}

// Pearson correlation function
function pearson(x, y) {
  const n = Math.min(x.length, y.length);
  if (n < 3) return null;
  const mx = x.reduce((a, b) => a + b, 0) / n;
  const my = y.reduce((a, b) => a + b, 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) {
    num += (x[i] - mx) * (y[i] - my);
    dx += (x[i] - mx) ** 2;
    dy += (y[i] - my) ** 2;
  }
  dx = Math.sqrt(dx); dy = Math.sqrt(dy);
  if (dx === 0 || dy === 0) return null;
  return num / (dx * dy);
}

// All pairwise correlations
const correlations = [];
for (let i = 0; i < metrics.length; i++) {
  for (let j = i + 1; j < metrics.length; j++) {
    const r = pearson(series[metrics[i]], series[metrics[j]]);
    if (r !== null) {
      correlations.push({
        metricA: metrics[i],
        metricB: metrics[j],
        correlation: Math.round(r * 10000) / 10000,
        strength: Math.abs(r) > 0.7 ? 'strong' : Math.abs(r) > 0.4 ? 'moderate' : 'weak',
      });
    }
  }
}

correlations.sort((a, b) => b.correlation - a.correlation);

return [{
  json: {
    dataPoints: dates.length,
    totalSnapshots: snapshots.length,
    topPositive: correlations.slice(0, 5),
    topNegative: correlations.slice(-5).reverse(),
    allCorrelations: correlations,
    reportDate: $('Set Date Range').first().json.reportDate,
  }
}];"""
        },
        "id": uid(),
        "name": "Compute Correlations",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [860, 300],
    })

    # -- AI Narrate Insights (OpenRouter) --
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
  "max_tokens": 1200,
  "messages": [
    {{
      "role": "system",
      "content": "You are a business intelligence analyst for AnyVision Media, a South African digital media and AI automation agency. Analyze cross-department metric correlations and produce concise, actionable business insights. Use ZAR for currency. Be specific about what the correlations mean for business decisions."
    }},
    {{
      "role": "user",
      "content": "Analyze these cross-department correlations from the last 28 days and provide 3-5 key business insights:\\n\\nTop Positive Correlations:\\n" + JSON.stringify($json.topPositive, null, 2) + "\\n\\nTop Negative Correlations:\\n" + JSON.stringify($json.topNegative, null, 2) + "\\n\\nData points: " + $json.dataPoints + " days"
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Narrate Insights",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [1080, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Extract AI Response --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "insights",
                        "value": "={{ $json.choices[0].message.content }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "reportDate",
                        "value": "={{ $('Set Date Range').first().json.reportDate }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "dataPoints",
                        "value": "={{ $('Compute Correlations').first().json.dataPoints }}",
                        "type": "number",
                    },
                    {
                        "id": uid(),
                        "name": "topPositive",
                        "value": "={{ JSON.stringify($('Compute Correlations').first().json.topPositive) }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Extract AI Response",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [1300, 300],
    })

    # -- Write to Intelligence Reports --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_INTELLIGENCE_REPORTS, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Report Date": "={{ $json.reportDate }}",
                    "Report Type": "Cross-Dept Correlations",
                    "Insights": "={{ $json.insights }}",
                    "Data Points": "={{ $json.dataPoints }}",
                    "Raw Data": "={{ $json.topPositive }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Intelligence Report",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1520, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Email Insights --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=AVM Cross-Dept Correlations - {{ $('Set Date Range').first().json.reportDate }}",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 600px;">
<div style="background: #FF6D5A; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
<h2 style="margin: 0;">Cross-Department Correlations</h2>
<p style="margin: 5px 0 0 0; opacity: 0.9;">Weekly Intelligence Report - {{ $('Set Date Range').first().json.reportDate }}</p>
</div>
<div style="padding: 20px; background: #f9f9f9;">
<p><strong>Data points:</strong> {{ $('Extract AI Response').first().json.dataPoints }} days analyzed</p>
<hr style="border: 1px solid #eee;">
{{ $('Extract AI Response').first().json.insights }}
<hr style="border: 1px solid #eee;">
<p style="color: #888; font-size: 12px;">Generated by AVM Intelligence Engine | INTEL-01</p>
</div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Email Insights",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1740, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## INTEL-01: Cross-Dept Correlator\nRuns Mon 06:00 SAST. Reads 28 days of KPI snapshots,\ncomputes Pearson correlations between metrics,\nAI narrates insights, saves report + emails summary.",
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


def build_intel01_connections():
    """Build connections for INTEL-01."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Date Range", "type": "main", "index": 0}]]
        },
        "Set Date Range": {
            "main": [[{"node": "Read KPI Snapshots", "type": "main", "index": 0}]]
        },
        "Read KPI Snapshots": {
            "main": [[{"node": "Compute Correlations", "type": "main", "index": 0}]]
        },
        "Compute Correlations": {
            "main": [[{"node": "AI Narrate Insights", "type": "main", "index": 0}]]
        },
        "AI Narrate Insights": {
            "main": [[{"node": "Extract AI Response", "type": "main", "index": 0}]]
        },
        "Extract AI Response": {
            "main": [[{"node": "Write Intelligence Report", "type": "main", "index": 0}]]
        },
        "Write Intelligence Report": {
            "main": [[{"node": "Email Insights", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# INTEL-02: Executive Report
# ==================================================================

def build_intel02_nodes():
    """Build nodes for INTEL-02: Executive Report (Monthly 1st 08:00 SAST = 06:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (1st of month 06:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 6 1 * *",
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

    # -- Set Report Period --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "periodStart",
                        "value": "={{ $now.minus({days: 30}).toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "periodEnd",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "monthLabel",
                        "value": "={{ $now.minus({days: 1}).toFormat('MMMM yyyy') }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Report Period",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [420, 300],
    })

    # -- Read KPI Snapshots (30 days) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_KPI_SNAPSHOTS, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Snapshot Date}, '{{ $json.periodStart }}')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read KPI Snapshots",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [640, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Read Escalation Queue (30 days) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ESCALATION_QUEUE, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Created At}, '{{ $('Set Report Period').first().json.periodStart }}')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Escalation Queue",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [640, 420],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Read Decision Log (30 days) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_DECISION_LOG, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Decided At}, '{{ $('Set Report Period').first().json.periodStart }}')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Decision Log",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [640, 640],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Aggregate Data (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Aggregate monthly data for executive report
const kpiSnaps = $('Read KPI Snapshots').all().map(i => i.json);
const escalations = $('Read Escalation Queue').all().map(i => i.json);
const decisions = $('Read Decision Log').all().map(i => i.json);

// Aggregate KPI totals by agent
const agentTotals = {};
for (const snap of kpiSnaps) {
  const agent = snap['Agent ID'] || 'unknown';
  if (!agentTotals[agent]) {
    agentTotals[agent] = {
      contentPublished: 0, leadsGenerated: 0, emailsSent: 0,
      revenueZar: 0, messagesHandled: 0, ticketsResolved: 0,
      successRateSum: 0, tokenUsage: 0, count: 0,
    };
  }
  const t = agentTotals[agent];
  t.contentPublished += parseFloat(snap['Content Published'] || 0);
  t.leadsGenerated += parseFloat(snap['Leads Generated'] || 0);
  t.emailsSent += parseFloat(snap['Emails Sent'] || 0);
  t.revenueZar += parseFloat(snap['Revenue ZAR'] || 0);
  t.messagesHandled += parseFloat(snap['Messages Handled'] || 0);
  t.ticketsResolved += parseFloat(snap['Tickets Resolved'] || 0);
  t.successRateSum += parseFloat(snap['Success Rate'] || 0);
  t.tokenUsage += parseInt(snap['Token Usage'] || 0);
  t.count++;
}

// Compute averages
for (const agent of Object.keys(agentTotals)) {
  const t = agentTotals[agent];
  t.avgSuccessRate = t.count > 0 ? Math.round(t.successRateSum / t.count * 10) / 10 : 0;
}

// Escalation summary
const escalationsByStatus = {};
const escalationsBySeverity = {};
for (const e of escalations) {
  const status = e.Status || 'unknown';
  const severity = e.Severity || 'P3';
  escalationsByStatus[status] = (escalationsByStatus[status] || 0) + 1;
  escalationsBySeverity[severity] = (escalationsBySeverity[severity] || 0) + 1;
}

// Grand totals
let totalRevenue = 0, totalLeads = 0, totalContent = 0, totalEmails = 0, totalTokens = 0;
for (const t of Object.values(agentTotals)) {
  totalRevenue += t.revenueZar;
  totalLeads += t.leadsGenerated;
  totalContent += t.contentPublished;
  totalEmails += t.emailsSent;
  totalTokens += t.tokenUsage;
}

return [{
  json: {
    monthLabel: $('Set Report Period').first().json.monthLabel,
    agentTotals,
    totalRevenue: Math.round(totalRevenue * 100) / 100,
    totalLeads: Math.round(totalLeads),
    totalContent: Math.round(totalContent),
    totalEmails: Math.round(totalEmails),
    totalTokens,
    escalationCount: escalations.length,
    escalationsByStatus,
    escalationsBySeverity,
    decisionCount: decisions.length,
    kpiDataPoints: kpiSnaps.length,
  }
}];"""
        },
        "id": uid(),
        "name": "Aggregate Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 420],
    })

    # -- AI Generate Executive Summary (OpenRouter) --
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
      "content": "You are a C-suite executive report writer for AnyVision Media, a South African digital media and AI automation agency. Write a comprehensive but concise (max 800 words) monthly executive summary. Use ZAR for all currency. Include: department performance overview, financial highlights, client health, top wins, areas of concern, and 3 strategic recommendations. Format with clear headers. Be data-driven and specific."
    }},
    {{
      "role": "user",
      "content": "Generate the executive report for " + $json.monthLabel + ":\\n\\nAgent Performance:\\n" + JSON.stringify($json.agentTotals, null, 2) + "\\n\\nGrand Totals: Revenue R" + $json.totalRevenue + ", Leads: " + $json.totalLeads + ", Content: " + $json.totalContent + ", Emails: " + $json.totalEmails + ", Tokens: " + $json.totalTokens + "\\n\\nEscalations: " + $json.escalationCount + " total\\nBy severity: " + JSON.stringify($json.escalationsBySeverity) + "\\nBy status: " + JSON.stringify($json.escalationsByStatus) + "\\n\\nDecisions logged: " + $json.decisionCount
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Executive Summary",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [1100, 420],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Format HTML Email (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Format executive report as branded HTML email
const summary = $json.choices[0].message.content;
const data = $('Aggregate Data').first().json;

// Build agent performance table rows
const agentRows = Object.entries(data.agentTotals).map(([agent, t]) => {
  const name = agent.replace('agent_', '').replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase());
  return `<tr>
    <td style="padding: 8px; border-bottom: 1px solid #eee;">${name}</td>
    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">R${Math.round(t.revenueZar).toLocaleString()}</td>
    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${Math.round(t.leadsGenerated)}</td>
    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${Math.round(t.contentPublished)}</td>
    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">${t.avgSuccessRate}%</td>
  </tr>`;
}).join('');

const html = `<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
  <div style="background: #FF6D5A; color: white; padding: 24px; border-radius: 8px 8px 0 0;">
    <h1 style="margin: 0; font-size: 22px;">AVM Monthly Executive Report</h1>
    <p style="margin: 5px 0 0; opacity: 0.9; font-size: 14px;">${data.monthLabel}</p>
  </div>

  <div style="background: white; padding: 24px; border: 1px solid #e0e0e0;">
    <div style="display: flex; gap: 16px; margin-bottom: 24px;">
      <div style="flex: 1; background: #f7f7f7; padding: 16px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; font-weight: bold; color: #FF6D5A;">R${Math.round(data.totalRevenue).toLocaleString()}</div>
        <div style="font-size: 12px; color: #888;">Revenue</div>
      </div>
      <div style="flex: 1; background: #f7f7f7; padding: 16px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; font-weight: bold; color: #FF6D5A;">${data.totalLeads}</div>
        <div style="font-size: 12px; color: #888;">Leads</div>
      </div>
      <div style="flex: 1; background: #f7f7f7; padding: 16px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; font-weight: bold; color: #FF6D5A;">${data.totalContent}</div>
        <div style="font-size: 12px; color: #888;">Content</div>
      </div>
      <div style="flex: 1; background: #f7f7f7; padding: 16px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; font-weight: bold; color: #FF6D5A;">${data.escalationCount}</div>
        <div style="font-size: 12px; color: #888;">Escalations</div>
      </div>
    </div>

    <h3 style="color: #333; border-bottom: 2px solid #FF6D5A; padding-bottom: 8px;">Agent Performance</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
      <tr style="background: #f7f7f7;">
        <th style="padding: 8px; text-align: left;">Agent</th>
        <th style="padding: 8px; text-align: right;">Revenue</th>
        <th style="padding: 8px; text-align: right;">Leads</th>
        <th style="padding: 8px; text-align: right;">Content</th>
        <th style="padding: 8px; text-align: right;">Success %</th>
      </tr>
      ${agentRows}
    </table>

    <h3 style="color: #333; border-bottom: 2px solid #FF6D5A; padding-bottom: 8px; margin-top: 24px;">Executive Summary</h3>
    <div style="line-height: 1.6; color: #444;">${summary.replace(/\\n/g, '<br>')}</div>

    <hr style="border: 1px solid #eee; margin: 24px 0;">
    <p style="color: #888; font-size: 11px;">Generated by AVM Intelligence Engine | INTEL-02 | ${data.kpiDataPoints} data points analyzed</p>
  </div>
</div>`;

return [{ json: { html, subject: 'AVM Monthly Executive Report - ' + data.monthLabel } }];"""
        },
        "id": uid(),
        "name": "Format HTML Email",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 420],
    })

    # -- Send Executive Report Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "message": "={{ $json.html }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Executive Report",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1540, 420],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## INTEL-02: Executive Report\nRuns 1st of month 08:00 SAST.\nReads 30 days of KPIs + escalations + decisions.\nAI generates executive summary.\nBranded HTML email with performance table.",
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


def build_intel02_connections():
    """Build connections for INTEL-02."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Report Period", "type": "main", "index": 0}]]
        },
        "Set Report Period": {
            "main": [
                [
                    {"node": "Read KPI Snapshots", "type": "main", "index": 0},
                    {"node": "Read Escalation Queue", "type": "main", "index": 0},
                    {"node": "Read Decision Log", "type": "main", "index": 0},
                ]
            ]
        },
        "Read KPI Snapshots": {
            "main": [[{"node": "Aggregate Data", "type": "main", "index": 0}]]
        },
        "Read Escalation Queue": {
            "main": [[{"node": "Aggregate Data", "type": "main", "index": 0}]]
        },
        "Read Decision Log": {
            "main": [[{"node": "Aggregate Data", "type": "main", "index": 0}]]
        },
        "Aggregate Data": {
            "main": [[{"node": "AI Executive Summary", "type": "main", "index": 0}]]
        },
        "AI Executive Summary": {
            "main": [[{"node": "Format HTML Email", "type": "main", "index": 0}]]
        },
        "Format HTML Email": {
            "main": [[{"node": "Send Executive Report", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# INTEL-03: Prompt Performance Tracker
# ==================================================================

def build_intel03_nodes():
    """Build nodes for INTEL-03: Prompt Performance Tracker (daily 23:00 SAST = 21:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (21:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 21 * * *",
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

    # -- Set Time Window --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "since",
                        "value": "={{ $now.minus({hours: 24}).toISO() }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "reportDate",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Time Window",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [420, 300],
    })

    # -- Fetch Executions (n8n API) --
    nodes.append({
        "parameters": {
            "url": "https://ianimmelman89.app.n8n.cloud/api/v1/executions",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "limit", "value": "200"},
                    {"name": "status", "value": ""},
                ]
            },
            "sendHeaders": True,
            "headerParameters": {
                "parameters": []
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Executions",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [640, 300],
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
    })

    # -- Analyze Prompt Performance (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Analyze execution data for prompt performance
const executions = ($json.data || []).filter(e => {
  const startedAt = new Date(e.startedAt || 0);
  const since = new Date($('Set Time Window').first().json.since);
  return startedAt >= since;
});

// Track per-workflow performance
const workflowStats = {};

for (const exec of executions) {
  const wfId = exec.workflowId || 'unknown';
  const wfName = exec.workflowName || wfId;

  if (!workflowStats[wfId]) {
    workflowStats[wfId] = {
      name: wfName,
      total: 0,
      success: 0,
      failed: 0,
      totalDuration: 0,
    };
  }

  const s = workflowStats[wfId];
  s.total++;
  if (exec.status === 'success') {
    s.success++;
  } else if (exec.status === 'error' || exec.status === 'crashed') {
    s.failed++;
  }

  // Duration
  if (exec.startedAt && exec.stoppedAt) {
    const dur = new Date(exec.stoppedAt) - new Date(exec.startedAt);
    s.totalDuration += dur;
  }
}

// Compute stats and find underperformers
const results = [];
const underperformers = [];

for (const [wfId, s] of Object.entries(workflowStats)) {
  const successRate = s.total > 0 ? Math.round((s.success / s.total) * 100 * 10) / 10 : 0;
  const avgDuration = s.total > 0 ? Math.round(s.totalDuration / s.total / 1000) : 0;

  const entry = {
    workflowId: wfId,
    workflowName: s.name,
    totalExecutions: s.total,
    successCount: s.success,
    failedCount: s.failed,
    successRate,
    avgDurationSec: avgDuration,
    reportDate: $('Set Time Window').first().json.reportDate,
  };

  results.push(entry);

  if (successRate < 60 && s.total >= 3) {
    underperformers.push(entry);
  }
}

return [{
  json: {
    totalExecutions: executions.length,
    totalWorkflows: results.length,
    results,
    underperformers,
    hasUnderperformers: underperformers.length > 0,
    reportDate: $('Set Time Window').first().json.reportDate,
  }
}];"""
        },
        "id": uid(),
        "name": "Analyze Performance",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [860, 300],
    })

    # -- Split Results for Airtable --
    nodes.append({
        "parameters": {
            "jsCode": """// Split results into individual items for Airtable write
const results = $json.results || [];
return results.map(r => ({ json: r }));"""
        },
        "id": uid(),
        "name": "Split Results",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1080, 200],
    })

    # -- Write to Prompt Performance Table --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_PROMPT_PERFORMANCE, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Report Date": "={{ $json.reportDate }}",
                    "Workflow ID": "={{ $json.workflowId }}",
                    "Workflow Name": "={{ $json.workflowName }}",
                    "Total Executions": "={{ $json.totalExecutions }}",
                    "Success Count": "={{ $json.successCount }}",
                    "Failed Count": "={{ $json.failedCount }}",
                    "Success Rate": "={{ $json.successRate }}",
                    "Avg Duration Sec": "={{ $json.avgDurationSec }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Performance Data",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1300, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Check Underperformers (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $('Analyze Performance').first().json.hasUnderperformers }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Underperformers?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1080, 420],
    })

    # -- Create Escalation --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ESCALATION_QUEUE, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Title": "=Prompt/Workflow Performance Below 60% - {{ $('Analyze Performance').first().json.reportDate }}",
                    "Category": "workflow_failure",
                    "Severity": "P3",
                    "Description": "={{ $('Analyze Performance').first().json.underperformers.length }} workflow(s) with success rate below 60%. Review prompt configurations and error logs.",
                    "Recommended Action": "Review underperforming workflow prompts. Check execution error logs. Consider A/B testing alternative prompts.",
                    "Status": "open",
                    "Agent ID": "agent_orchestrator",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Escalation",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1300, 420],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## INTEL-03: Prompt Performance Tracker\nRuns daily 23:00 SAST. Fetches n8n executions (last 24h),\nanalyzes success rates per workflow, writes to Airtable,\nescalates if any workflow has < 60% success rate.",
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


def build_intel03_connections():
    """Build connections for INTEL-03."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Time Window", "type": "main", "index": 0}]]
        },
        "Set Time Window": {
            "main": [[{"node": "Fetch Executions", "type": "main", "index": 0}]]
        },
        "Fetch Executions": {
            "main": [[{"node": "Analyze Performance", "type": "main", "index": 0}]]
        },
        "Analyze Performance": {
            "main": [
                [
                    {"node": "Split Results", "type": "main", "index": 0},
                    {"node": "Has Underperformers?", "type": "main", "index": 0},
                ]
            ]
        },
        "Split Results": {
            "main": [[{"node": "Write Performance Data", "type": "main", "index": 0}]]
        },
        "Has Underperformers?": {
            "main": [
                [{"node": "Create Escalation", "type": "main", "index": 0}],
                [],
            ]
        },
    }


# ==================================================================
# WORKFLOW DEFINITIONS
# ==================================================================

WORKFLOW_DEFS = {
    "intel01": {
        "name": "Intelligence - Cross-Dept Correlator (INTEL-01)",
        "filename": "intel01_correlator.json",
        "build_nodes": build_intel01_nodes,
        "build_connections": build_intel01_connections,
    },
    "intel02": {
        "name": "Intelligence - Executive Report (INTEL-02)",
        "filename": "intel02_executive_report.json",
        "build_nodes": build_intel02_nodes,
        "build_connections": build_intel02_connections,
    },
    "intel03": {
        "name": "Intelligence - Prompt Performance Tracker (INTEL-03)",
        "filename": "intel03_prompt_tracker.json",
        "build_nodes": build_intel03_nodes,
        "build_connections": build_intel03_connections,
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
    output_dir = Path(__file__).parent.parent / "workflows" / "intelligence"
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
    print("INTELLIGENCE LAYER - WORKFLOW BUILDER")
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
    if "REPLACE" in TABLE_KPI_SNAPSHOTS:
        missing.append("ORCH_TABLE_KPI_SNAPSHOTS")
    if "REPLACE" in TABLE_INTELLIGENCE_REPORTS:
        missing.append("ORCH_TABLE_INTELLIGENCE_REPORTS")
    if "REPLACE" in TABLE_PROMPT_PERFORMANCE:
        missing.append("ORCH_TABLE_PROMPT_PERFORMANCE")

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
    print("  1. Create Airtable tables: Intelligence_Reports, Prompt_Performance")
    print("  2. Set env vars: ORCH_TABLE_INTELLIGENCE_REPORTS, ORCH_TABLE_PROMPT_PERFORMANCE")
    print("  3. Open each workflow in n8n UI to verify node connections")
    print("  4. Test INTEL-03 manually -> check execution analysis")
    print("  5. Test INTEL-01 manually -> check correlation report + email")
    print("  6. Wait for 1st of month for INTEL-02 or trigger manually")
    print("  7. Once verified, run with 'activate' to enable schedules")


if __name__ == "__main__":
    main()
