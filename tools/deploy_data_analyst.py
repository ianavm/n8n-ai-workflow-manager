"""
AVM Data Analyst - Workflow Builder & Deployer

Builds 3 data analysis workflows for on-demand queries, daily trend
dashboards, and monthly report automation.

Workflows:
    DATA-01: On-Demand Query Agent   (Webhook) - Natural language to SQL via AI
    DATA-02: Daily Trend Dashboard   (Daily 06:30 SAST = 04:30 UTC)
    DATA-03: Monthly Report Auto     (1st of month 09:00 SAST = 07:00 UTC)

Usage:
    python tools/deploy_data_analyst.py build              # Build all JSONs
    python tools/deploy_data_analyst.py build data01       # Build DATA-01 only
    python tools/deploy_data_analyst.py deploy             # Build + Deploy (inactive)
    python tools/deploy_data_analyst.py activate           # Build + Deploy + Activate
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

# -- Airtable IDs --
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "appTCh0EeXQp0XqzW")
TABLE_DATA_ANALYSIS = os.getenv("DATA_TABLE_ANALYSIS", "REPLACE_AFTER_SETUP")
TABLE_KPI_SNAPSHOTS = os.getenv("ORCH_TABLE_KPI_SNAPSHOTS", "REPLACE_AFTER_SETUP")

# -- Supabase Config --
SUPABASE_URL = os.getenv("SUPABASE_URL", "REPLACE_AFTER_SETUP")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "REPLACE_AFTER_SETUP")

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"


def uid():
    return str(uuid.uuid4())


def airtable_ref(base, table):
    return {"base": {"__rl": True, "value": base, "mode": "id"},
            "table": {"__rl": True, "value": table, "mode": "id"}}


# ======================================================================
# DATA-01: On-Demand Query Agent (Webhook)
# ======================================================================

def build_data01_nodes():
    nodes = []

    # 1. Webhook
    nodes.append({"parameters": {"path": "data-query", "responseMode": "responseNode", "options": {}},
                   "id": uid(), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                   "position": [220, 300], "webhookId": uid()})

    # 2. Parse Query (Code)
    nodes.append({"parameters": {"jsCode": """const body = $input.first().json.body || $input.first().json;
return { json: {
  question: body.question || body.query || '',
  requested_by: body.requested_by || 'anonymous',
  query_id: 'QRY-' + Date.now().toString(36).toUpperCase(),
  requested_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Parse Query", "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [440, 300]})

    # 3. AI Translate to SQL (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 800,
  "messages": [
    {"role": "system", "content": "Translate this natural language question into a PostgreSQL query for the Supabase database. Tables available: clients (id, name, email, company, plan, status, created_at), client_health_scores (id, client_id, health_score, revenue_at_risk, churn_probability, last_interaction, scored_at), agent_status (id, agent_id, agent_name, status, health_score, last_heartbeat), orchestrator_alerts (id, alert_type, severity, message, resolved, created_at). Use parameterized queries only. NEVER use DROP, DELETE, UPDATE, or ALTER. Return JSON: {sql: string, explanation: string, safe: bool}. Set safe=false if the query could modify data."},
    {"role": "user", "content": "{{ $json.question }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Translate to SQL",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [660, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 4. Parse SQL (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let result = {};
try { result = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { result = {sql: '', explanation: 'Parse failed', safe: false}; }
const meta = $('Parse Query').first().json;
return { json: {
  query_id: meta.query_id,
  question: meta.question,
  requested_by: meta.requested_by,
  sql: result.sql || '',
  explanation: result.explanation || '',
  safe: result.safe !== false,
}};"""},
                   "id": uid(), "name": "Parse SQL",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [880, 300]})

    # 5. Safety Check (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.safe }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "equals"}}]}, "options": {}},
                   "id": uid(), "name": "Is Safe Query",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1100, 300]})

    # 6. Execute Query (Supabase REST API)
    nodes.append({"parameters": {
        "method": "POST",
        "url": "=" + SUPABASE_URL + "/rest/v1/rpc/raw_sql",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": "={\"query\": \"{{ $('Parse SQL').first().json.sql }}\"}",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "apikey", "value": SUPABASE_ANON_KEY},
            {"name": "Authorization", "value": "Bearer " + SUPABASE_ANON_KEY},
            {"name": "Content-Type", "value": "application/json"},
        ]},
        "options": {}},
                   "id": uid(), "name": "Execute Query",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [1320, 200]})

    # 7. AI Format Results (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1000,
  "messages": [
    {"role": "system", "content": "Format these SQL query results into a clear, human-readable summary. Include key numbers, trends, and actionable insights. Use bullet points for clarity."},
    {"role": "user", "content": "Original question: {{ $('Parse SQL').first().json.question }}\\nSQL: {{ $('Parse SQL').first().json.sql }}\\nResults: {{ JSON.stringify($json).substring(0, 3000) }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Format Results",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [1540, 200], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 8. Extract Summary (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const summary = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : 'No summary available.';
const meta = $('Parse SQL').first().json;
return { json: {
  query_id: meta.query_id,
  question: meta.question,
  sql: meta.sql,
  explanation: meta.explanation,
  summary,
  answered_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Extract Summary",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1760, 200]})

    # 9. Write to Data Analysis (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DATA_ANALYSIS),
        "columns": {"value": {
            "query_id": "={{ $json.query_id }}",
            "question": "={{ $json.question }}",
            "sql_query": "={{ $json.sql }}",
            "summary": "={{ $json.summary.substring(0, 2000) }}",
            "requested_by": "={{ $('Parse Query').first().json.requested_by }}",
            "status": "Completed",
            "created_at": "={{ $json.answered_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Analysis",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [1980, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 10. Respond with Results
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": "={{ JSON.stringify({success: true, query_id: $('Extract Summary').first().json.query_id, question: $('Extract Summary').first().json.question, summary: $('Extract Summary').first().json.summary, sql: $('Extract Summary').first().json.sql}) }}",
        "options": {}},
                   "id": uid(), "name": "Respond Results",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [2200, 300]})

    # 11. Respond Unsafe
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": "={{ JSON.stringify({success: false, query_id: $('Parse SQL').first().json.query_id, error: 'Query flagged as unsafe', explanation: $('Parse SQL').first().json.explanation}) }}",
        "options": {}},
                   "id": uid(), "name": "Respond Unsafe",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [1320, 420]})

    return nodes


def build_data01_connections(nodes):
    return {
        "Webhook": {"main": [[{"node": "Parse Query", "type": "main", "index": 0}]]},
        "Parse Query": {"main": [[{"node": "AI Translate to SQL", "type": "main", "index": 0}]]},
        "AI Translate to SQL": {"main": [[{"node": "Parse SQL", "type": "main", "index": 0}]]},
        "Parse SQL": {"main": [[{"node": "Is Safe Query", "type": "main", "index": 0}]]},
        "Is Safe Query": {"main": [
            [{"node": "Execute Query", "type": "main", "index": 0}],
            [{"node": "Respond Unsafe", "type": "main", "index": 0}],
        ]},
        "Execute Query": {"main": [[{"node": "AI Format Results", "type": "main", "index": 0}]]},
        "AI Format Results": {"main": [[{"node": "Extract Summary", "type": "main", "index": 0}]]},
        "Extract Summary": {"main": [[{"node": "Write Analysis", "type": "main", "index": 0}]]},
        "Write Analysis": {"main": [[{"node": "Respond Results", "type": "main", "index": 0}]]},
    }


# ======================================================================
# DATA-02: Daily Trend Dashboard (Daily 06:30 SAST = 04:30 UTC)
# ======================================================================

def build_data02_nodes():
    nodes = []

    # 1. Schedule Trigger (daily 04:30 UTC = 06:30 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "30 4 * * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Query KPI Snapshots (Airtable - last 30 days)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(ORCH_BASE_ID, TABLE_KPI_SNAPSHOTS),
        "filterByFormula": "=IS_AFTER({snapshot_date}, DATEADD(TODAY(), -30, 'days'))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Query KPI Snapshots",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [440, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Compute Trends (Code)
    nodes.append({"parameters": {"jsCode": """const items = $('Query KPI Snapshots').all();
const now = new Date();

// Sort by date
const sorted = items.map(i => i.json).sort((a, b) => new Date(a.snapshot_date || a.createdTime || '') - new Date(b.snapshot_date || b.createdTime || ''));

// Compute basic stats
const totalSnapshots = sorted.length;

// Group by week for WoW comparison
const thisWeek = sorted.filter(s => {
  const d = new Date(s.snapshot_date || s.createdTime || '');
  return (now - d) < 7 * 86400000;
});
const lastWeek = sorted.filter(s => {
  const d = new Date(s.snapshot_date || s.createdTime || '');
  return (now - d) >= 7 * 86400000 && (now - d) < 14 * 86400000;
});

// Extract numeric KPIs (health_score, execution_count, error_count)
const avgField = (arr, field) => {
  const vals = arr.map(s => parseFloat(s[field])).filter(v => !isNaN(v));
  return vals.length > 0 ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10 : 0;
};

const thisWeekHealth = avgField(thisWeek, 'health_score');
const lastWeekHealth = avgField(lastWeek, 'health_score');
const healthWoW = lastWeekHealth > 0 ? Math.round((thisWeekHealth - lastWeekHealth) / lastWeekHealth * 1000) / 10 : 0;

// 7-day moving average (last 7 entries)
const last7 = sorted.slice(-7);
const movingAvgHealth = avgField(last7, 'health_score');

// Month over month
const thisMonth = sorted.filter(s => {
  const d = new Date(s.snapshot_date || s.createdTime || '');
  return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
});
const lastMonth = sorted.filter(s => {
  const d = new Date(s.snapshot_date || s.createdTime || '');
  const lm = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return d.getMonth() === lm.getMonth() && d.getFullYear() === lm.getFullYear();
});
const thisMonthHealth = avgField(thisMonth, 'health_score');
const lastMonthHealth = avgField(lastMonth, 'health_score');
const healthMoM = lastMonthHealth > 0 ? Math.round((thisMonthHealth - lastMonthHealth) / lastMonthHealth * 1000) / 10 : 0;

return { json: {
  total_snapshots: totalSnapshots,
  this_week_avg_health: thisWeekHealth,
  last_week_avg_health: lastWeekHealth,
  health_wow_change: healthWoW,
  moving_avg_7d_health: movingAvgHealth,
  this_month_avg_health: thisMonthHealth,
  health_mom_change: healthMoM,
  trend_date: now.toISOString(),
  data_summary: sorted.slice(-7).map(s => (s.snapshot_date || s.createdTime || '').split('T')[0] + ': health=' + (s.health_score || 'N/A')).join('; '),
}};"""},
                   "id": uid(), "name": "Compute Trends",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [660, 300]})

    # 4. AI Insights (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1000,
  "messages": [
    {"role": "system", "content": "Analyze KPI trends for AnyVision Media's automation platform. Provide actionable insights, highlight concerns, and suggest optimizations. Be concise with bullet points."},
    {"role": "user", "content": "Daily Trend Analysis:\\n- Total data points: {{ $json.total_snapshots }}\\n- This week avg health: {{ $json.this_week_avg_health }}\\n- Last week avg health: {{ $json.last_week_avg_health }}\\n- WoW change: {{ $json.health_wow_change }}%\\n- 7-day moving avg: {{ $json.moving_avg_7d_health }}\\n- This month avg: {{ $json.this_month_avg_health }}\\n- MoM change: {{ $json.health_mom_change }}%\\n- Recent data: {{ $json.data_summary }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Trend Insights",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [880, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 5. Extract Insights (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const insights = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : 'No insights available.';
const trends = $('Compute Trends').first().json;
return { json: { ...trends, ai_insights: insights }};"""},
                   "id": uid(), "name": "Extract Insights",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1100, 300]})

    # 6. Write Trend Data (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DATA_ANALYSIS),
        "columns": {"value": {
            "query_id": "=TREND-{{ $now.toFormat('yyyy-MM-dd') }}",
            "question": "Daily Trend Dashboard",
            "summary": "={{ $json.ai_insights.substring(0, 2000) }}",
            "sql_query": "=Health WoW: {{ $json.health_wow_change }}%, MoM: {{ $json.health_mom_change }}%, 7d Avg: {{ $json.moving_avg_7d_health }}",
            "status": "Completed",
            "created_at": "={{ $json.trend_date }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Trend Data",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [1320, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 7. Email Daily Trends (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=Daily Trends: Health {{ $('Compute Trends').first().json.this_week_avg_health }} ({{ $('Compute Trends').first().json.health_wow_change > 0 ? '+' : '' }}{{ $('Compute Trends').first().json.health_wow_change }}% WoW)",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Daily Trend Dashboard</h2></div>
<div style="padding:20px">
<table style="width:100%;border-collapse:collapse">
<tr><td style="padding:8px;border-bottom:1px solid #eee"><b>This Week Avg Health</b></td><td style="padding:8px;border-bottom:1px solid #eee">{{ $('Compute Trends').first().json.this_week_avg_health }}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee"><b>Last Week Avg Health</b></td><td style="padding:8px;border-bottom:1px solid #eee">{{ $('Compute Trends').first().json.last_week_avg_health }}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee"><b>WoW Change</b></td><td style="padding:8px;border-bottom:1px solid #eee">{{ $('Compute Trends').first().json.health_wow_change }}%</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee"><b>7-Day Moving Avg</b></td><td style="padding:8px;border-bottom:1px solid #eee">{{ $('Compute Trends').first().json.moving_avg_7d_health }}</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid #eee"><b>MoM Change</b></td><td style="padding:8px;border-bottom:1px solid #eee">{{ $('Compute Trends').first().json.health_mom_change }}%</td></tr>
</table>
<h3>AI Insights</h3>
<div style="white-space:pre-wrap">{{ $('Extract Insights').first().json.ai_insights }}</div>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Data Analyst - Daily Trends</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Email Daily Trends",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "position": [1540, 300], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_data02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Query KPI Snapshots", "type": "main", "index": 0}]]},
        "Query KPI Snapshots": {"main": [[{"node": "Compute Trends", "type": "main", "index": 0}]]},
        "Compute Trends": {"main": [[{"node": "AI Trend Insights", "type": "main", "index": 0}]]},
        "AI Trend Insights": {"main": [[{"node": "Extract Insights", "type": "main", "index": 0}]]},
        "Extract Insights": {"main": [[{"node": "Write Trend Data", "type": "main", "index": 0}]]},
        "Write Trend Data": {"main": [[{"node": "Email Daily Trends", "type": "main", "index": 0}]]},
    }


# ======================================================================
# DATA-03: Monthly Report Automation (1st of month 09:00 SAST = 07:00 UTC)
# ======================================================================

def build_data03_nodes():
    nodes = []

    # 1. Schedule Trigger (1st of month 07:00 UTC = 09:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 7 1 * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Fetch KPI Data (Airtable - last 30 days)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(ORCH_BASE_ID, TABLE_KPI_SNAPSHOTS),
        "filterByFormula": "=IS_AFTER({snapshot_date}, DATEADD(TODAY(), -30, 'days'))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Fetch KPI Data",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [440, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Fetch Financial Data (Xero P&L via HTTP)
    nodes.append({"parameters": {
        "method": "GET",
        "url": "https://api.xero.com/api.xro/2.0/Reports/ProfitAndLoss?fromDate={{ $now.minus({months:1}).toFormat('yyyy-MM-dd') }}&toDate={{ $now.toFormat('yyyy-MM-dd') }}",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "xeroOAuth2Api",
        "options": {}},
                   "id": uid(), "name": "Fetch Xero P&L",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [440, 420]})

    # 4. Aggregate Monthly Data (Code)
    nodes.append({"parameters": {"jsCode": """const kpiItems = $('Fetch KPI Data').all();
const xeroResp = $('Fetch Xero P&L').first().json;

// Aggregate KPIs
const kpis = kpiItems.map(i => i.json);
const avgHealth = kpis.length > 0 ? Math.round(kpis.reduce((sum, k) => sum + (parseFloat(k.health_score) || 0), 0) / kpis.length * 10) / 10 : 0;
const totalExecutions = kpis.reduce((sum, k) => sum + (parseInt(k.execution_count) || 0), 0);
const totalErrors = kpis.reduce((sum, k) => sum + (parseInt(k.error_count) || 0), 0);
const errorRate = totalExecutions > 0 ? Math.round(totalErrors / totalExecutions * 1000) / 10 : 0;

// Extract Xero P&L summary
let revenue = 'N/A';
let expenses = 'N/A';
let netProfit = 'N/A';
try {
  const reports = xeroResp.Reports || [];
  if (reports.length > 0) {
    const rows = reports[0].Rows || [];
    for (const section of rows) {
      if (section.Title === 'Income' && section.Rows) {
        const totRow = section.Rows.find(r => r.RowType === 'SummaryRow');
        if (totRow) revenue = totRow.Cells?.[1]?.Value || 'N/A';
      }
      if (section.Title === 'Less Operating Expenses' && section.Rows) {
        const totRow = section.Rows.find(r => r.RowType === 'SummaryRow');
        if (totRow) expenses = totRow.Cells?.[1]?.Value || 'N/A';
      }
      if (section.RowType === 'Section' && section.Title === 'Net Profit') {
        const totRow = (section.Rows || []).find(r => r.RowType === 'SummaryRow');
        if (totRow) netProfit = totRow.Cells?.[1]?.Value || 'N/A';
      }
    }
  }
} catch(e) { /* Xero parsing failed - use N/A defaults */ }

const reportMonth = new Date();
reportMonth.setMonth(reportMonth.getMonth() - 1);

return { json: {
  report_month: reportMonth.toISOString().substring(0, 7),
  avg_health_score: avgHealth,
  total_executions: totalExecutions,
  total_errors: totalErrors,
  error_rate_pct: errorRate,
  kpi_data_points: kpis.length,
  revenue, expenses, net_profit: netProfit,
  generated_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Aggregate Monthly Data",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [700, 300]})

    # 5. AI Generate Monthly Report (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 2000,
  "messages": [
    {"role": "system", "content": "Generate a comprehensive monthly report for AnyVision Media. Include: Executive Summary, Operations Performance, Financial Overview, Key Achievements, Areas of Concern, Recommendations for Next Month. Use ZAR (R) for all currency. Format as clean HTML for email."},
    {"role": "user", "content": "Monthly Report for {{ $json.report_month }}:\\n\\nOperations:\\n- Avg Health Score: {{ $json.avg_health_score }}/100\\n- Total Workflow Executions: {{ $json.total_executions }}\\n- Total Errors: {{ $json.total_errors }} ({{ $json.error_rate_pct }}% error rate)\\n- Data Points: {{ $json.kpi_data_points }}\\n\\nFinancials (from Xero):\\n- Revenue: R{{ $json.revenue }}\\n- Expenses: R{{ $json.expenses }}\\n- Net Profit: R{{ $json.net_profit }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Generate Report",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [940, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 6. Extract Report (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const report = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : 'Report generation failed.';
const meta = $('Aggregate Monthly Data').first().json;
return { json: {
  report_month: meta.report_month,
  report_content: report,
  avg_health: meta.avg_health_score,
  total_executions: meta.total_executions,
  error_rate: meta.error_rate_pct,
  revenue: meta.revenue,
  net_profit: meta.net_profit,
  generated_at: meta.generated_at,
}};"""},
                   "id": uid(), "name": "Extract Report",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1160, 300]})

    # 7. Write Monthly Report (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DATA_ANALYSIS),
        "columns": {"value": {
            "query_id": "=MONTHLY-{{ $json.report_month }}",
            "question": "=Monthly Report {{ $json.report_month }}",
            "summary": "={{ $json.report_content.substring(0, 2000) }}",
            "sql_query": "=Health: {{ $json.avg_health }}, Executions: {{ $json.total_executions }}, Errors: {{ $json.error_rate }}%, Revenue: R{{ $json.revenue }}",
            "status": "Completed",
            "created_at": "={{ $json.generated_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Monthly Report",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [1380, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 8. Email Monthly Report (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=AnyVision Media Monthly Report - {{ $('Extract Report').first().json.report_month }}",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:700px">
<div style="background:#FF6D5A;padding:20px;text-align:center">
<h1 style="color:white;margin:0">AnyVision Media</h1>
<h2 style="color:white;margin:5px 0 0 0">Monthly Report - {{ $('Extract Report').first().json.report_month }}</h2>
</div>
<div style="padding:20px">
<table style="width:100%;border-collapse:collapse;margin-bottom:20px">
<tr style="background:#f8f8f8"><td style="padding:10px;border:1px solid #eee"><b>Health Score</b></td><td style="padding:10px;border:1px solid #eee">{{ $('Extract Report').first().json.avg_health }}/100</td></tr>
<tr><td style="padding:10px;border:1px solid #eee"><b>Executions</b></td><td style="padding:10px;border:1px solid #eee">{{ $('Extract Report').first().json.total_executions }}</td></tr>
<tr style="background:#f8f8f8"><td style="padding:10px;border:1px solid #eee"><b>Error Rate</b></td><td style="padding:10px;border:1px solid #eee">{{ $('Extract Report').first().json.error_rate }}%</td></tr>
<tr><td style="padding:10px;border:1px solid #eee"><b>Revenue</b></td><td style="padding:10px;border:1px solid #eee">R{{ $('Extract Report').first().json.revenue }}</td></tr>
<tr style="background:#f8f8f8"><td style="padding:10px;border:1px solid #eee"><b>Net Profit</b></td><td style="padding:10px;border:1px solid #eee">R{{ $('Extract Report').first().json.net_profit }}</td></tr>
</table>
<div>{{ $('Extract Report').first().json.report_content }}</div>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Data Analyst - Monthly Report Automation</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Email Monthly Report",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "position": [1600, 300], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_data03_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Fetch KPI Data", "type": "main", "index": 0},
            {"node": "Fetch Xero P&L", "type": "main", "index": 0},
        ]]},
        "Fetch KPI Data": {"main": [[{"node": "Aggregate Monthly Data", "type": "main", "index": 0}]]},
        "Fetch Xero P&L": {"main": [[{"node": "Aggregate Monthly Data", "type": "main", "index": 0}]]},
        "Aggregate Monthly Data": {"main": [[{"node": "AI Generate Report", "type": "main", "index": 0}]]},
        "AI Generate Report": {"main": [[{"node": "Extract Report", "type": "main", "index": 0}]]},
        "Extract Report": {"main": [[{"node": "Write Monthly Report", "type": "main", "index": 0}]]},
        "Write Monthly Report": {"main": [[{"node": "Email Monthly Report", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "data01": {"name": "DATA-01 On-Demand Query Agent", "build_nodes": build_data01_nodes,
               "build_connections": build_data01_connections,
               "filename": "data01_on_demand_query_agent.json", "tags": ["data", "query", "webhook"]},
    "data02": {"name": "DATA-02 Daily Trend Dashboard", "build_nodes": build_data02_nodes,
               "build_connections": build_data02_connections,
               "filename": "data02_daily_trend_dashboard.json", "tags": ["data", "trends", "daily"]},
    "data03": {"name": "DATA-03 Monthly Report Automation", "build_nodes": build_data03_nodes,
               "build_connections": build_data03_connections,
               "filename": "data03_monthly_report_automation.json", "tags": ["data", "report", "monthly"]},
}


def build_workflow_json(key):
    builder = WORKFLOW_BUILDERS[key]
    nodes = builder["build_nodes"]()
    connections = builder["build_connections"](nodes)
    return {
        "name": builder["name"], "nodes": nodes, "connections": connections, "active": False,
        "settings": {"executionOrder": "v1", "saveManualExecutions": True,
                     "callerPolicy": "workflowsFromSameOwner"},
        "tags": builder["tags"],
        "meta": {"templateCredsSetupCompleted": True, "builder": "deploy_data_analyst.py",
                 "built_at": datetime.now().isoformat()},
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "data-analyst"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / builder["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)
    node_count = len(workflow_json["nodes"])
    print(f"  + {builder['name']:<40} ({node_count} nodes) -> {output_path}")
    return output_path


def print_workflow_stats(workflow_json, key):
    builder = WORKFLOW_BUILDERS[key]
    nodes = workflow_json["nodes"]
    print(f"\n  {builder['name']}:")
    print(f"    Nodes: {len(nodes)}")
    for n in nodes:
        print(f"      - {n['name']} ({n['type']})")


def deploy_workflow(key, workflow_json, activate=False):
    from n8n_client import N8nClient
    api_key = os.getenv("N8N_API_KEY")
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    client = N8nClient(base_url, api_key, timeout=30)
    builder = WORKFLOW_BUILDERS[key]
    deploy_payload = {k: v for k, v in workflow_json.items() if k not in ("tags", "meta", "active")}
    resp = client.create_workflow(deploy_payload)
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
        print("AVM Data Analyst - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_data_analyst.py build              # Build all")
        print("  python tools/deploy_data_analyst.py build data01       # Build one")
        print("  python tools/deploy_data_analyst.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_data_analyst.py activate           # Build + Deploy + Activate")
        print()
        print("Workflows:")
        for key, builder in WORKFLOW_BUILDERS.items():
            print(f"  {key:<12} {builder['name']}")
        sys.exit(0)

    action = sys.argv[1].lower()
    target = sys.argv[2].lower() if len(sys.argv) > 2 else "all"

    if target == "all":
        keys = list(WORKFLOW_BUILDERS.keys())
    elif target in WORKFLOW_BUILDERS:
        keys = [target]
    else:
        print(f"Unknown workflow: {target}")
        print(f"Valid: {', '.join(WORKFLOW_BUILDERS.keys())}")
        sys.exit(1)

    print("=" * 60)
    print("AVM DATA ANALYST - WORKFLOW BUILDER")
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
            print_workflow_stats(wf_json, key)
        print()
        print("Build complete. Inspect workflows in: workflows/data-analyst/")

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
