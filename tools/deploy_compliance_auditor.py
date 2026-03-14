"""
AVM Compliance Auditor - Workflow Builder & Deployer

Builds 3 compliance workflows for monthly scans, ad policy checks,
and POPIA (Protection of Personal Information Act) audits.

Workflows:
    COMPLY-01: Monthly Compliance Scan  (1st of month 07:00 SAST = 05:00 UTC)
    COMPLY-02: Ad Policy Check          (Wed 09:00 SAST = 07:00 UTC)
    COMPLY-03: POPIA Audit              (15th of month 08:00 SAST = 06:00 UTC)

Usage:
    python tools/deploy_compliance_auditor.py build              # Build all JSONs
    python tools/deploy_compliance_auditor.py build comply01     # Build COMPLY-01 only
    python tools/deploy_compliance_auditor.py deploy             # Build + Deploy (inactive)
    python tools/deploy_compliance_auditor.py activate           # Build + Deploy + Activate
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
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
LEAD_BASE_ID = os.getenv("LEAD_AIRTABLE_BASE_ID", "app2ALQUP7CKEkHOz")
TABLE_COMPLIANCE_AUDIT = os.getenv("COMPLIANCE_TABLE_AUDIT", "REPLACE_AFTER_SETUP")
TABLE_EMAIL_SUPPRESSION = os.getenv("EMAIL_SUPPRESSION_TABLE_ID", "tbl0LtepawDzFYg4I")
TABLE_DECISION_LOG = os.getenv("ORCH_TABLE_DECISION_LOG", "REPLACE_AFTER_SETUP")
TABLE_CONTENT_CALENDAR = os.getenv("MARKETING_TABLE_CONTENT_CALENDAR", "REPLACE_AFTER_SETUP")

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"


def uid():
    return str(uuid.uuid4())


def airtable_ref(base, table):
    return {"base": {"__rl": True, "value": base, "mode": "id"},
            "table": {"__rl": True, "value": table, "mode": "id"}}


# ======================================================================
# COMPLY-01: Monthly Compliance Scan (1st of month 07:00 SAST = 05:00 UTC)
# ======================================================================

def build_comply01_nodes():
    nodes = []

    # 1. Schedule Trigger (1st of month 05:00 UTC = 07:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 5 1 * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Set Scan Scope
    nodes.append({"parameters": {"assignments": {"assignments": [
        {"id": uid(), "name": "scan_id", "value": "=COMPLY-{{ $now.toFormat('yyyy-MM') }}", "type": "string"},
        {"id": uid(), "name": "departments", "value": "accounting,marketing,seo-social,lead-scraper,support", "type": "string"},
        {"id": uid(), "name": "scan_date", "value": "={{ $now.toISO() }}", "type": "string"},
    ]}, "options": {}},
                   "id": uid(), "name": "Set Scan Scope",
                   "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [440, 300]})

    # 3. Check Email Suppression Table (Airtable)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(LEAD_BASE_ID, TABLE_EMAIL_SUPPRESSION),
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Check Suppression Table",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [660, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 4. Check Decision Log (Airtable)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(ORCH_BASE_ID, TABLE_DECISION_LOG),
        "filterByFormula": "=IS_AFTER({created_at}, DATEADD(TODAY(), -30, 'days'))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Check Decision Log",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [660, 420], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 5. Compile Compliance Data (Code)
    nodes.append({"parameters": {"jsCode": """const suppressions = $('Check Suppression Table').all();
const decisions = $('Check Decision Log').all();
const scope = $('Set Scan Scope').first().json;

const suppressionCount = suppressions.length;
const suppressionStatuses = {};
for (const s of suppressions) {
  const status = s.json.status || s.json.Status || 'Unknown';
  suppressionStatuses[status] = (suppressionStatuses[status] || 0) + 1;
}

const decisionCount = decisions.length;
const unreviewed = decisions.filter(d => !(d.json.reviewed || d.json.status === 'Reviewed')).length;

return { json: {
  scan_id: scope.scan_id,
  scan_date: scope.scan_date,
  departments: scope.departments,
  suppression_count: suppressionCount,
  suppression_breakdown: JSON.stringify(suppressionStatuses),
  decision_count: decisionCount,
  unreviewed_decisions: unreviewed,
  email_compliance: suppressionCount > 0 ? 'Active' : 'Warning - Empty suppression list',
  audit_trail: decisionCount > 0 ? 'Active' : 'Warning - No decisions logged',
}};"""},
                   "id": uid(), "name": "Compile Compliance Data",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [900, 300]})

    # 6. AI Compliance Assessment (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1200,
  "messages": [
    {"role": "system", "content": "You are a compliance auditor for a South African digital marketing company. Assess compliance based on: email suppression (POPIA), audit trail completeness, data handling. Return JSON: {overall_score: 0-100, findings: [{area, status: 'Compliant'|'Non-Compliant'|'Warning', detail, severity: 'Critical'|'High'|'Medium'|'Low'}], recommendations: [], risk_level: 'Low'|'Medium'|'High'|'Critical'}"},
    {"role": "user", "content": "Monthly Compliance Scan {{ $json.scan_id }}\\nDepartments: {{ $json.departments }}\\n\\nEmail Suppression: {{ $json.suppression_count }} entries ({{ $json.suppression_breakdown }})\\nEmail Compliance: {{ $json.email_compliance }}\\nDecision Log: {{ $json.decision_count }} entries, {{ $json.unreviewed_decisions }} unreviewed\\nAudit Trail: {{ $json.audit_trail }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Compliance Assessment",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [1120, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 7. Parse Assessment (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let assessment = {};
try { assessment = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { assessment = {overall_score: 0, findings: [], recommendations: ['Parse failed - manual review needed'], risk_level: 'High'}; }
const meta = $('Compile Compliance Data').first().json;
const nonCompliant = (assessment.findings || []).filter(f => f.status === 'Non-Compliant');
return { json: {
  scan_id: meta.scan_id,
  overall_score: assessment.overall_score || 0,
  findings: JSON.stringify(assessment.findings || []),
  findings_count: (assessment.findings || []).length,
  non_compliant_count: nonCompliant.length,
  recommendations: (assessment.recommendations || []).join('; '),
  risk_level: assessment.risk_level || 'Unknown',
  scan_date: meta.scan_date,
  has_violations: nonCompliant.length > 0,
}};"""},
                   "id": uid(), "name": "Parse Assessment",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1340, 300]})

    # 8. Write Compliance Results (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_COMPLIANCE_AUDIT),
        "columns": {"value": {
            "scan_id": "={{ $json.scan_id }}",
            "audit_type": "Monthly Compliance Scan",
            "overall_score": "={{ $json.overall_score }}",
            "findings": "={{ $json.findings }}",
            "recommendations": "={{ $json.recommendations }}",
            "risk_level": "={{ $json.risk_level }}",
            "non_compliant_count": "={{ $json.non_compliant_count }}",
            "status": "={{ $json.has_violations ? 'Action Required' : 'Compliant' }}",
            "scanned_at": "={{ $json.scan_date }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Compliance Results",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [1560, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 9. Check Violations (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $('Parse Assessment').first().json.non_compliant_count }}", "rightValue": 0,
         "operator": {"type": "number", "operation": "gt"}}]}, "options": {}},
                   "id": uid(), "name": "Has Violations",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1780, 300]})

    # 10. Alert Email (Gmail - violations found)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=COMPLIANCE ALERT: {{ $('Parse Assessment').first().json.non_compliant_count }} violations found - {{ $('Parse Assessment').first().json.risk_level }} Risk",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#DC3545;padding:15px;text-align:center"><h2 style="color:white;margin:0">Compliance Alert</h2></div>
<div style="padding:20px">
<p><b>Scan ID:</b> {{ $('Parse Assessment').first().json.scan_id }}</p>
<h3>Overall Score: {{ $('Parse Assessment').first().json.overall_score }}/100</h3>
<p><b>Risk Level:</b> <span style="color:red;font-weight:bold">{{ $('Parse Assessment').first().json.risk_level }}</span></p>
<p><b>Non-Compliant Findings:</b> {{ $('Parse Assessment').first().json.non_compliant_count }}</p>
<h3>Findings</h3><p style="font-size:12px">{{ $('Parse Assessment').first().json.findings }}</p>
<h3>Recommendations</h3><p>{{ $('Parse Assessment').first().json.recommendations }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Compliance Auditor - Automated Alert</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Alert Violations Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "position": [2000, 200], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 11. Summary Email (Gmail - all clear)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=Monthly Compliance Scan - Score: {{ $('Parse Assessment').first().json.overall_score }}/100 - All Clear",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#28A745;padding:15px;text-align:center"><h2 style="color:white;margin:0">Compliance Scan - All Clear</h2></div>
<div style="padding:20px">
<p><b>Scan ID:</b> {{ $('Parse Assessment').first().json.scan_id }}</p>
<h3>Overall Score: {{ $('Parse Assessment').first().json.overall_score }}/100</h3>
<p><b>Risk Level:</b> {{ $('Parse Assessment').first().json.risk_level }}</p>
<p><b>Total Findings:</b> {{ $('Parse Assessment').first().json.findings_count }}</p>
<h3>Recommendations</h3><p>{{ $('Parse Assessment').first().json.recommendations }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Compliance Auditor - Automated Report</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Summary Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "position": [2000, 420], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_comply01_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Set Scan Scope", "type": "main", "index": 0}]]},
        "Set Scan Scope": {"main": [[
            {"node": "Check Suppression Table", "type": "main", "index": 0},
            {"node": "Check Decision Log", "type": "main", "index": 0},
        ]]},
        "Check Suppression Table": {"main": [[{"node": "Compile Compliance Data", "type": "main", "index": 0}]]},
        "Check Decision Log": {"main": [[{"node": "Compile Compliance Data", "type": "main", "index": 0}]]},
        "Compile Compliance Data": {"main": [[{"node": "AI Compliance Assessment", "type": "main", "index": 0}]]},
        "AI Compliance Assessment": {"main": [[{"node": "Parse Assessment", "type": "main", "index": 0}]]},
        "Parse Assessment": {"main": [[{"node": "Write Compliance Results", "type": "main", "index": 0}]]},
        "Write Compliance Results": {"main": [[{"node": "Has Violations", "type": "main", "index": 0}]]},
        "Has Violations": {"main": [
            [{"node": "Alert Violations Email", "type": "main", "index": 0}],
            [{"node": "Summary Email", "type": "main", "index": 0}],
        ]},
    }


# ======================================================================
# COMPLY-02: Ad Policy Check (Wednesday 09:00 SAST = 07:00 UTC)
# ======================================================================

def build_comply02_nodes():
    nodes = []

    # 1. Schedule Trigger (Wed 07:00 UTC = 09:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 7 * * 3"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Read Recent Ad Campaigns (Airtable - Content Calendar filtered for ads)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(MARKETING_BASE_ID, TABLE_CONTENT_CALENDAR),
        "filterByFormula": "=AND(OR({content_type} = 'ad', {content_type} = 'sponsored', {content_type} = 'paid'), IS_AFTER({created_at}, DATEADD(TODAY(), -7, 'days')))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Recent Ads",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [440, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Aggregate Ad Data (Code)
    nodes.append({"parameters": {"jsCode": """const items = $('Read Recent Ads').all();
if (items.length === 0 || (items.length === 1 && !items[0].json.id)) {
  return { json: { ad_count: 0, ad_data: 'No recent ad campaigns found.', check_date: new Date().toISOString() }};
}
const adList = items.map(i => {
  const d = i.json;
  return 'Title: ' + (d.title || d.Name || 'Untitled') + '\\nPlatform: ' + (d.platform || 'N/A') + '\\nContent: ' + (d.content || d.body || d.description || 'N/A').substring(0, 400) + '\\nCTA: ' + (d.cta || d.call_to_action || 'N/A');
}).join('\\n---\\n');
return { json: { ad_count: items.length, ad_data: adList, check_date: new Date().toISOString() }};"""},
                   "id": uid(), "name": "Aggregate Ad Data",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [660, 300]})

    # 4. AI Policy Check (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1500,
  "messages": [
    {"role": "system", "content": "You are an advertising policy compliance checker. Check ads against Google Ads, Meta (Facebook/Instagram), and TikTok advertising policies. Common violations: misleading claims, prohibited content, missing disclaimers, trademark issues, targeting restrictions. Return JSON: {compliant_count: number, violation_count: number, findings: [{ad_title, platform, violation_type, policy_reference, severity: 'Critical'|'High'|'Medium'|'Low', recommendation}], overall_risk: 'Low'|'Medium'|'High'|'Critical'}"},
    {"role": "user", "content": "Check {{ $json.ad_count }} recent ad campaigns for policy compliance:\\n\\n{{ $json.ad_data }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Policy Check",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [880, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 5. Parse Policy Results (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let check = {};
try { check = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { check = {compliant_count: 0, violation_count: 0, findings: [], overall_risk: 'Unknown'}; }
const meta = $('Aggregate Ad Data').first().json;
return { json: {
  ad_count: meta.ad_count,
  compliant_count: check.compliant_count || 0,
  violation_count: check.violation_count || 0,
  findings: JSON.stringify(check.findings || []),
  overall_risk: check.overall_risk || 'Unknown',
  check_date: meta.check_date,
  has_violations: (check.violation_count || 0) > 0,
}};"""},
                   "id": uid(), "name": "Parse Policy Results",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1100, 300]})

    # 6. Write Findings (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_COMPLIANCE_AUDIT),
        "columns": {"value": {
            "scan_id": "=AD-CHECK-{{ $json.check_date }}",
            "audit_type": "Ad Policy Check",
            "overall_score": "={{ Math.round((($json.compliant_count || 0) / Math.max($json.ad_count, 1)) * 100) }}",
            "findings": "={{ $json.findings }}",
            "recommendations": "={{ $json.violation_count }} violations found across {{ $json.ad_count }} ads",
            "risk_level": "={{ $json.overall_risk }}",
            "non_compliant_count": "={{ $json.violation_count }}",
            "status": "={{ $json.has_violations ? 'Action Required' : 'Compliant' }}",
            "scanned_at": "={{ $json.check_date }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Findings",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [1320, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 7. Check for Violations (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $('Parse Policy Results').first().json.violation_count }}", "rightValue": 0,
         "operator": {"type": "number", "operation": "gt"}}]}, "options": {}},
                   "id": uid(), "name": "Has Policy Violations",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1540, 300]})

    # 8. Alert Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=AD POLICY ALERT: {{ $('Parse Policy Results').first().json.violation_count }} violations - {{ $('Parse Policy Results').first().json.overall_risk }} Risk",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#DC3545;padding:15px;text-align:center"><h2 style="color:white;margin:0">Ad Policy Violations Found</h2></div>
<div style="padding:20px">
<p><b>Ads Checked:</b> {{ $('Parse Policy Results').first().json.ad_count }}</p>
<p><b>Violations:</b> {{ $('Parse Policy Results').first().json.violation_count }}</p>
<p><b>Risk Level:</b> <span style="color:red;font-weight:bold">{{ $('Parse Policy Results').first().json.overall_risk }}</span></p>
<h3>Findings</h3><p style="font-size:12px">{{ $('Parse Policy Results').first().json.findings }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Compliance Auditor - Ad Policy Check</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Alert Policy Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "position": [1760, 200], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_comply02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Read Recent Ads", "type": "main", "index": 0}]]},
        "Read Recent Ads": {"main": [[{"node": "Aggregate Ad Data", "type": "main", "index": 0}]]},
        "Aggregate Ad Data": {"main": [[{"node": "AI Policy Check", "type": "main", "index": 0}]]},
        "AI Policy Check": {"main": [[{"node": "Parse Policy Results", "type": "main", "index": 0}]]},
        "Parse Policy Results": {"main": [[{"node": "Write Findings", "type": "main", "index": 0}]]},
        "Write Findings": {"main": [[{"node": "Has Policy Violations", "type": "main", "index": 0}]]},
        "Has Policy Violations": {"main": [
            [{"node": "Alert Policy Email", "type": "main", "index": 0}],
        ]},
    }


# ======================================================================
# COMPLY-03: POPIA Audit (Monthly 15th 08:00 SAST = 06:00 UTC)
# ======================================================================

def build_comply03_nodes():
    nodes = []

    # 1. Schedule Trigger (15th 06:00 UTC = 08:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6 15 * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Read Suppression Records (Airtable)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(LEAD_BASE_ID, TABLE_EMAIL_SUPPRESSION),
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Suppression Records",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [440, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Read Lead Data (Airtable - check for PII)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(LEAD_BASE_ID, "REPLACE_AFTER_SETUP"),
        "filterByFormula": "=IS_AFTER({created_at}, DATEADD(TODAY(), -30, 'days'))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Lead Data",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [440, 420], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 4. Scan for PII Compliance (Code)
    nodes.append({"parameters": {"jsCode": """const suppressions = $('Read Suppression Records').all();
const leads = $('Read Lead Data').all();

// Check consent and opt-out processing
const suppressionCount = suppressions.length;
const optOutStatuses = {};
for (const s of suppressions) {
  const status = s.json.status || s.json.Status || 'Unknown';
  optOutStatuses[status] = (optOutStatuses[status] || 0) + 1;
}

// Scan leads for PII fields
const piiFields = ['id_number', 'national_id', 'passport', 'bank_account', 'credit_card', 'medical', 'race', 'religion', 'political'];
const piiFindings = [];
let leadsWithConsent = 0;
let leadsWithoutConsent = 0;

for (const lead of leads) {
  const d = lead.json;
  for (const field of piiFields) {
    if (d[field] && String(d[field]).trim().length > 0) {
      piiFindings.push({ record_id: d.id || 'unknown', field, has_value: true });
    }
  }
  if (d.consent || d.opted_in || d.consent_given) leadsWithConsent++;
  else leadsWithoutConsent++;
}

// Check data retention (records older than 2 years)
const twoYearsAgo = new Date();
twoYearsAgo.setFullYear(twoYearsAgo.getFullYear() - 2);
const oldRecords = leads.filter(l => {
  const created = new Date(l.json.created_at || l.json.createdTime || '');
  return created < twoYearsAgo;
}).length;

return { json: {
  suppression_count: suppressionCount,
  opt_out_breakdown: JSON.stringify(optOutStatuses),
  lead_count: leads.length,
  leads_with_consent: leadsWithConsent,
  leads_without_consent: leadsWithoutConsent,
  pii_findings_count: piiFindings.length,
  pii_findings: JSON.stringify(piiFindings.slice(0, 20)),
  old_records_count: oldRecords,
  scan_date: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Scan PII Compliance",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [700, 300]})

    # 5. AI POPIA Assessment (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1500,
  "messages": [
    {"role": "system", "content": "You are a POPIA (Protection of Personal Information Act, South Africa) compliance auditor. Assess data handling practices. Key POPIA requirements: lawful processing, purpose limitation, data minimization, storage limitation, integrity/confidentiality, information officer duties. Return JSON: {popia_score: 0-100, findings: [{area, status: 'Compliant'|'Non-Compliant'|'Warning', detail, popia_section, severity: 'Critical'|'High'|'Medium'|'Low'}], data_retention_compliant: bool, consent_management_score: 0-100, recommendations: [], risk_level: 'Low'|'Medium'|'High'|'Critical'}"},
    {"role": "user", "content": "POPIA Audit Data:\\n- Email Suppressions: {{ $json.suppression_count }} ({{ $json.opt_out_breakdown }})\\n- Total Leads (30 days): {{ $json.lead_count }}\\n- Leads WITH consent: {{ $json.leads_with_consent }}\\n- Leads WITHOUT consent: {{ $json.leads_without_consent }}\\n- PII fields found: {{ $json.pii_findings_count }}\\n- PII details: {{ $json.pii_findings }}\\n- Records older than 2 years: {{ $json.old_records_count }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI POPIA Assessment",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [940, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 6. Parse POPIA Results (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let audit = {};
try { audit = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { audit = {popia_score: 0, findings: [], data_retention_compliant: false, consent_management_score: 0, recommendations: ['Parse failed'], risk_level: 'High'}; }
const meta = $('Scan PII Compliance').first().json;
const nonCompliant = (audit.findings || []).filter(f => f.status === 'Non-Compliant');
return { json: {
  popia_score: audit.popia_score || 0,
  consent_score: audit.consent_management_score || 0,
  data_retention_compliant: audit.data_retention_compliant || false,
  findings: JSON.stringify(audit.findings || []),
  findings_count: (audit.findings || []).length,
  non_compliant_count: nonCompliant.length,
  recommendations: (audit.recommendations || []).join('; '),
  risk_level: audit.risk_level || 'Unknown',
  scan_date: meta.scan_date,
  has_violations: nonCompliant.length > 0,
}};"""},
                   "id": uid(), "name": "Parse POPIA Results",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1160, 300]})

    # 7. Write POPIA Audit (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_COMPLIANCE_AUDIT),
        "columns": {"value": {
            "scan_id": "=POPIA-{{ $now.toFormat('yyyy-MM') }}",
            "audit_type": "POPIA Audit",
            "overall_score": "={{ $json.popia_score }}",
            "findings": "={{ $json.findings }}",
            "recommendations": "={{ $json.recommendations }}",
            "risk_level": "={{ $json.risk_level }}",
            "non_compliant_count": "={{ $json.non_compliant_count }}",
            "status": "={{ $json.has_violations ? 'Action Required' : 'Compliant' }}",
            "scanned_at": "={{ $json.scan_date }}"}},
        "options": {}},
                   "id": uid(), "name": "Write POPIA Audit",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [1380, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 8. Check Violations (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $('Parse POPIA Results').first().json.non_compliant_count }}", "rightValue": 0,
         "operator": {"type": "number", "operation": "gt"}}]}, "options": {}},
                   "id": uid(), "name": "Has POPIA Violations",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1600, 300]})

    # 9. Alert Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=POPIA COMPLIANCE ALERT: {{ $('Parse POPIA Results').first().json.non_compliant_count }} violations - Score {{ $('Parse POPIA Results').first().json.popia_score }}/100",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#DC3545;padding:15px;text-align:center"><h2 style="color:white;margin:0">POPIA Compliance Alert</h2></div>
<div style="padding:20px">
<h3>POPIA Score: {{ $('Parse POPIA Results').first().json.popia_score }}/100</h3>
<p><b>Consent Management Score:</b> {{ $('Parse POPIA Results').first().json.consent_score }}/100</p>
<p><b>Data Retention Compliant:</b> {{ $('Parse POPIA Results').first().json.data_retention_compliant }}</p>
<p><b>Risk Level:</b> <span style="color:red;font-weight:bold">{{ $('Parse POPIA Results').first().json.risk_level }}</span></p>
<p><b>Non-Compliant Findings:</b> {{ $('Parse POPIA Results').first().json.non_compliant_count }}</p>
<h3>Findings</h3><p style="font-size:12px">{{ $('Parse POPIA Results').first().json.findings }}</p>
<h3>Recommendations</h3><p>{{ $('Parse POPIA Results').first().json.recommendations }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Compliance Auditor - POPIA Audit</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Alert POPIA Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "position": [1820, 200], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 10. Summary Email (Gmail - all clear)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=POPIA Audit Passed - Score: {{ $('Parse POPIA Results').first().json.popia_score }}/100",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#28A745;padding:15px;text-align:center"><h2 style="color:white;margin:0">POPIA Audit - Compliant</h2></div>
<div style="padding:20px">
<h3>POPIA Score: {{ $('Parse POPIA Results').first().json.popia_score }}/100</h3>
<p><b>Consent Management:</b> {{ $('Parse POPIA Results').first().json.consent_score }}/100</p>
<p><b>Data Retention Compliant:</b> {{ $('Parse POPIA Results').first().json.data_retention_compliant }}</p>
<h3>Recommendations</h3><p>{{ $('Parse POPIA Results').first().json.recommendations }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Compliance Auditor - POPIA Audit</div></div>""",
        "options": {}},
                   "id": uid(), "name": "POPIA Summary Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "position": [1820, 420], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_comply03_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Suppression Records", "type": "main", "index": 0},
            {"node": "Read Lead Data", "type": "main", "index": 0},
        ]]},
        "Read Suppression Records": {"main": [[{"node": "Scan PII Compliance", "type": "main", "index": 0}]]},
        "Read Lead Data": {"main": [[{"node": "Scan PII Compliance", "type": "main", "index": 0}]]},
        "Scan PII Compliance": {"main": [[{"node": "AI POPIA Assessment", "type": "main", "index": 0}]]},
        "AI POPIA Assessment": {"main": [[{"node": "Parse POPIA Results", "type": "main", "index": 0}]]},
        "Parse POPIA Results": {"main": [[{"node": "Write POPIA Audit", "type": "main", "index": 0}]]},
        "Write POPIA Audit": {"main": [[{"node": "Has POPIA Violations", "type": "main", "index": 0}]]},
        "Has POPIA Violations": {"main": [
            [{"node": "Alert POPIA Email", "type": "main", "index": 0}],
            [{"node": "POPIA Summary Email", "type": "main", "index": 0}],
        ]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "comply01": {"name": "COMPLY-01 Monthly Compliance Scan", "build_nodes": build_comply01_nodes,
                 "build_connections": build_comply01_connections,
                 "filename": "comply01_monthly_compliance_scan.json", "tags": ["compliance", "monthly", "audit"]},
    "comply02": {"name": "COMPLY-02 Ad Policy Check", "build_nodes": build_comply02_nodes,
                 "build_connections": build_comply02_connections,
                 "filename": "comply02_ad_policy_check.json", "tags": ["compliance", "ads", "policy"]},
    "comply03": {"name": "COMPLY-03 POPIA Audit", "build_nodes": build_comply03_nodes,
                 "build_connections": build_comply03_connections,
                 "filename": "comply03_popia_audit.json", "tags": ["compliance", "popia", "privacy"]},
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
        "meta": {"templateCredsSetupCompleted": True, "builder": "deploy_compliance_auditor.py",
                 "built_at": datetime.now().isoformat()},
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "compliance"
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
        print("AVM Compliance Auditor - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_compliance_auditor.py build              # Build all")
        print("  python tools/deploy_compliance_auditor.py build comply01     # Build one")
        print("  python tools/deploy_compliance_auditor.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_compliance_auditor.py activate           # Build + Deploy + Activate")
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
    print("AVM COMPLIANCE AUDITOR - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/compliance/")

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
