"""
AVM Data Curator - Workflow Builder & Deployer

Builds 3 data quality workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance.

Workflows:
    CURE-01: Nightly Dedup Scan      (Daily 01:00 SAST = 23:00 UTC) - Detect duplicates across key tables
    CURE-02: Weekly Quality Report   (Sunday 05:00 SAST = 03:00 UTC) - Aggregate quality metrics
    CURE-03: Monthly Schema Audit    (1st 03:00 SAST = 01:00 UTC) - Detect schema drift

Usage:
    python tools/deploy_data_curator.py build              # Build all workflow JSONs
    python tools/deploy_data_curator.py build cure01        # Build CURE-01 only
    python tools/deploy_data_curator.py build cure02        # Build CURE-02 only
    python tools/deploy_data_curator.py build cure03        # Build CURE-03 only
    python tools/deploy_data_curator.py deploy              # Build + Deploy (inactive)
    python tools/deploy_data_curator.py activate            # Build + Deploy + Activate
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
TABLE_DATA_QUALITY = os.getenv("CURATOR_TABLE_DATA_QUALITY", "REPLACE_AFTER_SETUP")

# Target tables for dedup scanning
LEAD_BASE_ID = os.getenv("LEAD_AIRTABLE_BASE_ID", "app2ALQUP7CKEkHOz")
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")

# -- Config --
AI_MODEL = "anthropic/claude-sonnet-4-20250514"
ALERT_EMAIL = "ian@anyvisionmedia.com"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
AIRTABLE_META_API = "https://api.airtable.com/v0/meta/bases"


def uid():
    return str(uuid.uuid4())


def airtable_ref(base, table):
    return {"base": {"__rl": True, "value": base, "mode": "id"},
            "table": {"__rl": True, "value": table, "mode": "id"}}


# ======================================================================
# CURE-01: Nightly Dedup Scan (Daily 01:00 SAST = 23:00 UTC)
# ======================================================================

def build_cure01_nodes():
    nodes = []

    # 1. Schedule Trigger (23:00 UTC = 01:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 23 * * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                   "position": [220, 300]})

    # 2. Set Target Tables (Code)
    nodes.append({"parameters": {"jsCode": """// Define tables to scan for duplicates
const targets = [
  {
    base_id: '""" + LEAD_BASE_ID + """',
    table_id: '""" + os.getenv("LEAD_TABLE_CRM", "REPLACE_AFTER_SETUP") + """',
    table_name: 'CRM_Unified',
    dedup_field: 'email'
  },
  {
    base_id: '""" + LEAD_BASE_ID + """',
    table_id: '""" + os.getenv("LEAD_TABLE_LEADS", "REPLACE_AFTER_SETUP") + """',
    table_name: 'Leads',
    dedup_field: 'email'
  },
  {
    base_id: '""" + MARKETING_BASE_ID + """',
    table_id: '""" + os.getenv("MARKETING_TABLE_CONTACTS", "REPLACE_AFTER_SETUP") + """',
    table_name: 'Contacts',
    dedup_field: 'email'
  }
];
return targets.map(t => ({json: t}));"""},
                   "id": uid(), "name": "Set Target Tables",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [440, 300]})

    # 3. Fetch All Records from Target Table (Airtable)
    nodes.append({"parameters": {"operation": "search",
        "base": {"__rl": True, "value": "={{ $json.base_id }}", "mode": "id"},
        "table": {"__rl": True, "value": "={{ $json.table_id }}", "mode": "id"},
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Fetch Table Records",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [660, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 4. Detect Duplicates (Code)
    nodes.append({"parameters": {"jsCode": """const records = $input.all();
const targetInfo = $('Set Target Tables').item.json;
const dedupField = targetInfo.dedup_field;
const tableName = targetInfo.table_name;

// Normalize and group by dedup field
const groups = {};
let totalRecords = 0;
let emptyFieldCount = 0;

for (const item of records) {
  totalRecords++;
  const raw = item.json[dedupField] || item.json.fields?.[dedupField] || '';
  if (!raw) { emptyFieldCount++; continue; }
  const normalized = String(raw).toLowerCase().trim();
  if (!groups[normalized]) groups[normalized] = [];
  groups[normalized].push({
    record_id: item.json.id || item.json.record_id || 'unknown',
    raw_value: raw,
  });
}

const duplicates = Object.entries(groups)
  .filter(([_, recs]) => recs.length > 1)
  .map(([key, recs]) => ({
    value: key,
    count: recs.length,
    record_ids: recs.map(r => r.record_id),
  }));

const totalDuplicateRecords = duplicates.reduce((sum, d) => sum + d.count - 1, 0);

return { json: {
  table_name: tableName,
  base_id: targetInfo.base_id,
  table_id: targetInfo.table_id,
  dedup_field: dedupField,
  total_records: totalRecords,
  empty_field_count: emptyFieldCount,
  duplicate_groups: duplicates.length,
  duplicate_records: totalDuplicateRecords,
  duplicate_rate_pct: totalRecords > 0 ? Math.round((totalDuplicateRecords / totalRecords) * 10000) / 100 : 0,
  top_duplicates: duplicates.slice(0, 10),
  scanned_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Detect Duplicates",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [880, 300]})

    # 5. Write Dedup Results to Data_Quality (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DATA_QUALITY),
        "columns": {"value": {
            "scan_id": "=DEDUP-{{ $json.table_name }}-{{ $now.toFormat('yyyyMMdd') }}",
            "scan_type": "Dedup Scan",
            "table_name": "={{ $json.table_name }}",
            "total_records": "={{ $json.total_records }}",
            "issues_found": "={{ $json.duplicate_records }}",
            "issue_rate_pct": "={{ $json.duplicate_rate_pct }}",
            "details": "={{ JSON.stringify({duplicate_groups: $json.duplicate_groups, top_duplicates: $json.top_duplicates, empty_fields: $json.empty_field_count}) }}",
            "scanned_at": "={{ $json.scanned_at }}",
            "status": "={{ $json.duplicate_records > 20 ? 'Alert' : 'OK' }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Dedup Results",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1100, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 6. Check if duplicates > 20 (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $('Detect Duplicates').item.json.duplicate_records }}", "rightValue": 20,
         "operator": {"type": "number", "operation": "gt"}}],
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"}}},
                   "id": uid(), "name": "Too Many Duplicates",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2,
                   "position": [1320, 300]})

    # 7. Alert Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=DATA ALERT: {{ $('Detect Duplicates').item.json.duplicate_records }} duplicates in {{ $('Detect Duplicates').item.json.table_name }}",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#DC3545;padding:15px;text-align:center"><h2 style="color:white;margin:0">Duplicate Data Alert</h2></div>
<div style="padding:20px">
<p><b>Table:</b> {{ $('Detect Duplicates').item.json.table_name }}</p>
<p><b>Dedup Field:</b> {{ $('Detect Duplicates').item.json.dedup_field }}</p>
<p><b>Total Records:</b> {{ $('Detect Duplicates').item.json.total_records }}</p>
<p><b>Duplicate Records:</b> {{ $('Detect Duplicates').item.json.duplicate_records }}</p>
<p><b>Duplicate Rate:</b> {{ $('Detect Duplicates').item.json.duplicate_rate_pct }}%</p>
<h3>Top Duplicates</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
<tr style="background:#FF6D5A;color:white;"><th>Value</th><th>Count</th></tr>
{{ $('Detect Duplicates').item.json.top_duplicates.map(d => '<tr><td>' + d.value + '</td><td>' + d.count + '</td></tr>').join('') }}
</table>
<p style="color:red;font-weight:bold">Action required: Review and merge duplicate records.</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Data Curator - Nightly Dedup Scan</div>
</div>""",
        "options": {}},
                   "id": uid(), "name": "Alert Duplicates Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1540, 200], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 8. Summary Log (Set)
    nodes.append({"parameters": {
        "mode": "manual", "duplicateItem": False,
        "assignments": {"assignments": [
            {"id": uid(), "name": "status", "value": "Dedup scan complete", "type": "string"},
            {"id": uid(), "name": "scanned_at", "value": "={{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}", "type": "string"},
        ]}},
                   "id": uid(), "name": "Scan Summary",
                   "type": "n8n-nodes-base.set", "typeVersion": 3.4,
                   "position": [1540, 420]})

    return nodes


def build_cure01_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Set Target Tables", "type": "main", "index": 0}]]},
        "Set Target Tables": {"main": [[{"node": "Fetch Table Records", "type": "main", "index": 0}]]},
        "Fetch Table Records": {"main": [[{"node": "Detect Duplicates", "type": "main", "index": 0}]]},
        "Detect Duplicates": {"main": [[{"node": "Write Dedup Results", "type": "main", "index": 0}]]},
        "Write Dedup Results": {"main": [[{"node": "Too Many Duplicates", "type": "main", "index": 0}]]},
        "Too Many Duplicates": {"main": [
            [{"node": "Alert Duplicates Email", "type": "main", "index": 0}],
            [{"node": "Scan Summary", "type": "main", "index": 0}],
        ]},
    }


# ======================================================================
# CURE-02: Weekly Quality Report (Sunday 05:00 SAST = 03:00 UTC)
# ======================================================================

def build_cure02_nodes():
    nodes = []

    # 1. Schedule Trigger (Sunday 03:00 UTC = 05:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 3 * * 0"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                   "position": [220, 300]})

    # 2. Read Data_Quality Scan Results (last 7 days)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(ORCH_BASE_ID, TABLE_DATA_QUALITY),
        "filterByFormula": "=IS_AFTER({scanned_at}, DATEADD(TODAY(), -7, 'days'))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Weekly Scans",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [440, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Aggregate Quality Metrics (Code)
    nodes.append({"parameters": {"jsCode": """const scans = $input.all();
const tableMetrics = {};
let totalIssues = 0;
let totalRecords = 0;
let alertCount = 0;

for (const item of scans) {
  const s = item.json;
  const tableName = s.table_name || 'Unknown';
  if (!tableMetrics[tableName]) {
    tableMetrics[tableName] = {
      table_name: tableName,
      scan_count: 0,
      total_issues: 0,
      total_records: 0,
      worst_rate: 0,
      latest_status: 'OK',
    };
  }
  const tm = tableMetrics[tableName];
  tm.scan_count++;
  const issues = parseInt(s.issues_found || 0);
  const records = parseInt(s.total_records || 0);
  const rate = parseFloat(s.issue_rate_pct || 0);
  tm.total_issues += issues;
  tm.total_records = Math.max(tm.total_records, records);
  if (rate > tm.worst_rate) tm.worst_rate = rate;
  if (s.status === 'Alert') { tm.latest_status = 'Alert'; alertCount++; }
  totalIssues += issues;
  totalRecords += records;
}

const tables = Object.values(tableMetrics);
const degrading = tables.filter(t => t.worst_rate > 5);

return { json: {
  week_ending: new Date().toISOString().split('T')[0],
  total_scans: scans.length,
  total_issues: totalIssues,
  total_records: totalRecords,
  alert_count: alertCount,
  overall_rate_pct: totalRecords > 0 ? Math.round((totalIssues / totalRecords) * 10000) / 100 : 0,
  tables: tables,
  degrading_tables: degrading.map(t => t.table_name),
  scan_data_summary: JSON.stringify(tables),
}};"""},
                   "id": uid(), "name": "Aggregate Quality Metrics",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [660, 300]})

    # 4. AI Quality Assessment (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1000,
  "messages": [
    {"role": "system", "content": "You are a data quality analyst for AnyVision Media. Analyze weekly data quality metrics across Airtable tables. Identify tables with degrading quality, recommend specific actions. Output JSON: {overall_grade: A/B/C/D/F, summary: string, table_assessments: [{table_name, grade, trend: improving/stable/degrading, recommendation}], priority_actions: [{action, table, urgency: high/medium/low}]}"},
    {"role": "user", "content": "Weekly data quality report ending {{ $json.week_ending }}:\\nTotal scans: {{ $json.total_scans }}\\nTotal issues: {{ $json.total_issues }}\\nOverall issue rate: {{ $json.overall_rate_pct }}%\\nAlerts: {{ $json.alert_count }}\\nDegrading tables: {{ JSON.stringify($json.degrading_tables) }}\\nTable metrics: {{ $json.scan_data_summary }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Quality Assessment",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [880, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 5. Extract Assessment (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let ai = {};
try { ai = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { ai = {overall_grade: 'N/A', summary: 'Parse failed'}; }
const metrics = $('Aggregate Quality Metrics').first().json;
return { json: {
  scan_id: 'QR-' + metrics.week_ending.replace(/-/g, ''),
  scan_type: 'Weekly Quality Report',
  overall_grade: ai.overall_grade || 'N/A',
  ai_summary: ai.summary || '',
  table_assessments: ai.table_assessments || [],
  priority_actions: ai.priority_actions || [],
  total_scans: metrics.total_scans,
  total_issues: metrics.total_issues,
  overall_rate_pct: metrics.overall_rate_pct,
  alert_count: metrics.alert_count,
  week_ending: metrics.week_ending,
}};"""},
                   "id": uid(), "name": "Extract Assessment",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [1100, 300]})

    # 6. Write Weekly Report to Data_Quality (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DATA_QUALITY),
        "columns": {"value": {
            "scan_id": "={{ $json.scan_id }}",
            "scan_type": "Weekly Quality Report",
            "table_name": "All Tables",
            "total_records": "={{ $json.total_scans }}",
            "issues_found": "={{ $json.total_issues }}",
            "issue_rate_pct": "={{ $json.overall_rate_pct }}",
            "details": "={{ JSON.stringify({grade: $json.overall_grade, assessments: $json.table_assessments, actions: $json.priority_actions}) }}",
            "scanned_at": "={{ $now.toISO() }}",
            "status": "={{ $json.overall_grade }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Weekly Report",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1320, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 7. Email Quality Report (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=Weekly Data Quality Report - Grade: {{ $('Extract Assessment').first().json.overall_grade }} ({{ $('Extract Assessment').first().json.week_ending }})",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Weekly Data Quality Report</h2></div>
<div style="padding:20px">
<h3>Overall Grade: {{ $('Extract Assessment').first().json.overall_grade }}</h3>
<p><b>Week Ending:</b> {{ $('Extract Assessment').first().json.week_ending }}</p>
<p><b>Scans Run:</b> {{ $('Extract Assessment').first().json.total_scans }} | <b>Issues Found:</b> {{ $('Extract Assessment').first().json.total_issues }} | <b>Alerts:</b> {{ $('Extract Assessment').first().json.alert_count }}</p>
<h3>Summary</h3>
<p>{{ $('Extract Assessment').first().json.ai_summary }}</p>
<h3>Table Assessments</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
<tr style="background:#FF6D5A;color:white;"><th>Table</th><th>Grade</th><th>Trend</th><th>Recommendation</th></tr>
{{ $('Extract Assessment').first().json.table_assessments.map(t => '<tr><td>' + t.table_name + '</td><td>' + t.grade + '</td><td>' + t.trend + '</td><td>' + t.recommendation + '</td></tr>').join('') || '<tr><td colspan="4">No assessments</td></tr>' }}
</table>
<h3>Priority Actions</h3>
<ul>{{ $('Extract Assessment').first().json.priority_actions.map(a => '<li>[' + a.urgency + '] ' + a.table + ': ' + a.action + '</li>').join('') || '<li>No actions needed</li>' }}</ul>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Data Curator - Weekly Quality Report</div>
</div>""",
        "options": {}},
                   "id": uid(), "name": "Email Quality Report",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1540, 300], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_cure02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Read Weekly Scans", "type": "main", "index": 0}]]},
        "Read Weekly Scans": {"main": [[{"node": "Aggregate Quality Metrics", "type": "main", "index": 0}]]},
        "Aggregate Quality Metrics": {"main": [[{"node": "AI Quality Assessment", "type": "main", "index": 0}]]},
        "AI Quality Assessment": {"main": [[{"node": "Extract Assessment", "type": "main", "index": 0}]]},
        "Extract Assessment": {"main": [[{"node": "Write Weekly Report", "type": "main", "index": 0}]]},
        "Write Weekly Report": {"main": [[{"node": "Email Quality Report", "type": "main", "index": 0}]]},
    }


# ======================================================================
# CURE-03: Monthly Schema Audit (1st of month 03:00 SAST = 01:00 UTC)
# ======================================================================

def build_cure03_nodes():
    nodes = []

    # 1. Schedule Trigger (1st of month 01:00 UTC = 03:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 1 1 * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                   "position": [220, 300]})

    # 2. Set Bases to Audit (Code)
    nodes.append({"parameters": {"jsCode": """// Define Airtable bases to audit
const bases = [
  { base_id: '""" + ORCH_BASE_ID + """', base_name: 'Operations Control' },
  { base_id: '""" + LEAD_BASE_ID + """', base_name: 'Lead Scraper' },
  { base_id: '""" + MARKETING_BASE_ID + """', base_name: 'Marketing' },
];
return bases.map(b => ({json: b}));"""},
                   "id": uid(), "name": "Set Bases to Audit",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [440, 300]})

    # 3. Fetch Base Schema (httpRequest v4.2 - Airtable Meta API)
    nodes.append({"parameters": {
        "method": "GET",
        "url": "={{ '" + AIRTABLE_META_API + "/' + $json.base_id + '/tables' }}",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "airtableTokenApi",
        "options": {"timeout": 30000}},
                   "id": uid(), "name": "Fetch Base Schema",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [660, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 4. Analyze Schema (Code)
    nodes.append({"parameters": {"jsCode": """const schemaResp = $input.first().json;
const baseInfo = $('Set Bases to Audit').item.json;
const tables = schemaResp.tables || [];

const tableAudit = tables.map(t => {
  const fields = t.fields || [];
  const fieldTypes = {};
  for (const f of fields) {
    const type = f.type || 'unknown';
    fieldTypes[type] = (fieldTypes[type] || 0) + 1;
  }
  return {
    table_name: t.name,
    table_id: t.id,
    field_count: fields.length,
    field_types: fieldTypes,
    field_names: fields.map(f => f.name),
    has_primary: fields.some(f => f.id === t.primaryFieldId),
  };
});

// Expected schema baselines (update these as tables are added)
const expectedTables = {
  'Operations Control': ['Agent_Registry', 'Events', 'KPI_Snapshots', 'Escalation_Queue', 'Decision_Log'],
  'Lead Scraper': ['Leads', 'Email Suppression'],
  'Marketing': ['Content Calendar', 'Keywords', 'Content Topics'],
};

const expected = expectedTables[baseInfo.base_name] || [];
const actual = tableAudit.map(t => t.table_name);
const missingTables = expected.filter(e => !actual.includes(e));
const unexpectedTables = actual.filter(a => !expected.includes(a) && expected.length > 0);

return { json: {
  base_name: baseInfo.base_name,
  base_id: baseInfo.base_id,
  total_tables: tables.length,
  table_audit: tableAudit,
  missing_tables: missingTables,
  unexpected_tables: unexpectedTables,
  drift_detected: missingTables.length > 0 || unexpectedTables.length > 0,
  audited_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Analyze Schema",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [880, 300]})

    # 5. Write Audit Results to Data_Quality (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DATA_QUALITY),
        "columns": {"value": {
            "scan_id": "=SCHEMA-{{ $json.base_name.replace(/ /g, '_') }}-{{ $now.toFormat('yyyyMM') }}",
            "scan_type": "Schema Audit",
            "table_name": "={{ $json.base_name }}",
            "total_records": "={{ $json.total_tables }}",
            "issues_found": "={{ $json.missing_tables.length + $json.unexpected_tables.length }}",
            "issue_rate_pct": "={{ $json.total_tables > 0 ? Math.round((($json.missing_tables.length + $json.unexpected_tables.length) / $json.total_tables) * 100) : 0 }}",
            "details": "={{ JSON.stringify({tables: $json.table_audit.map(t => ({name: t.table_name, fields: t.field_count})), missing: $json.missing_tables, unexpected: $json.unexpected_tables}) }}",
            "scanned_at": "={{ $json.audited_at }}",
            "status": "={{ $json.drift_detected ? 'Alert' : 'OK' }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Audit Results",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1100, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 6. Check for Drift (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $('Analyze Schema').item.json.drift_detected }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "equals"}}],
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"}}},
                   "id": uid(), "name": "Drift Detected",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2,
                   "position": [1320, 300]})

    # 7. Alert on Schema Drift (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=SCHEMA DRIFT: {{ $('Analyze Schema').item.json.base_name }} - {{ $('Analyze Schema').item.json.missing_tables.length }} missing, {{ $('Analyze Schema').item.json.unexpected_tables.length }} unexpected",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FFA500;padding:15px;text-align:center"><h2 style="color:white;margin:0">Schema Drift Detected</h2></div>
<div style="padding:20px">
<p><b>Base:</b> {{ $('Analyze Schema').item.json.base_name }}</p>
<p><b>Total Tables:</b> {{ $('Analyze Schema').item.json.total_tables }}</p>
<h3>Missing Expected Tables</h3>
<ul>{{ $('Analyze Schema').item.json.missing_tables.map(t => '<li style="color:red">' + t + '</li>').join('') || '<li>None</li>' }}</ul>
<h3>Unexpected Tables</h3>
<ul>{{ $('Analyze Schema').item.json.unexpected_tables.map(t => '<li style="color:orange">' + t + '</li>').join('') || '<li>None</li>' }}</ul>
<h3>Current Tables</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
<tr style="background:#FF6D5A;color:white;"><th>Table</th><th>Fields</th></tr>
{{ $('Analyze Schema').item.json.table_audit.map(t => '<tr><td>' + t.table_name + '</td><td>' + t.field_count + '</td></tr>').join('') }}
</table>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Data Curator - Monthly Schema Audit</div>
</div>""",
        "options": {}},
                   "id": uid(), "name": "Alert Schema Drift",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1540, 200], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_cure03_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Set Bases to Audit", "type": "main", "index": 0}]]},
        "Set Bases to Audit": {"main": [[{"node": "Fetch Base Schema", "type": "main", "index": 0}]]},
        "Fetch Base Schema": {"main": [[{"node": "Analyze Schema", "type": "main", "index": 0}]]},
        "Analyze Schema": {"main": [[{"node": "Write Audit Results", "type": "main", "index": 0}]]},
        "Write Audit Results": {"main": [[{"node": "Drift Detected", "type": "main", "index": 0}]]},
        "Drift Detected": {"main": [
            [{"node": "Alert Schema Drift", "type": "main", "index": 0}],
            [],
        ]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "cure01": {"name": "CURE-01 Nightly Dedup Scan", "build_nodes": build_cure01_nodes,
               "build_connections": build_cure01_connections,
               "filename": "cure01_nightly_dedup_scan.json", "tags": ["data-curator", "dedup", "nightly"]},
    "cure02": {"name": "CURE-02 Weekly Quality Report", "build_nodes": build_cure02_nodes,
               "build_connections": build_cure02_connections,
               "filename": "cure02_weekly_quality_report.json", "tags": ["data-curator", "quality", "weekly"]},
    "cure03": {"name": "CURE-03 Monthly Schema Audit", "build_nodes": build_cure03_nodes,
               "build_connections": build_cure03_connections,
               "filename": "cure03_monthly_schema_audit.json", "tags": ["data-curator", "schema", "monthly"]},
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
        "meta": {"templateCredsSetupCompleted": True, "builder": "deploy_data_curator.py",
                 "built_at": datetime.now().isoformat()},
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "data-curator"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / builder["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)
    node_count = len(workflow_json["nodes"])
    print(f"  + {builder['name']:<40} ({node_count} nodes) -> {output_path}")
    return output_path


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
        print("AVM Data Curator - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_data_curator.py build              # Build all")
        print("  python tools/deploy_data_curator.py build cure01       # Build one")
        print("  python tools/deploy_data_curator.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_data_curator.py activate           # Build + Deploy + Activate")
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
    print("AVM DATA CURATOR - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/data-curator/")

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
