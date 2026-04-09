"""
AVM DevOps Coordinator - Workflow Builder & Deployer

Builds 3 DevOps workflows for deployment monitoring, credential rotation
alerts, and automated release notes generation.

Workflows:
    DEVOPS-01: Auto-Deploy Monitor      (Webhook) - Deploy/rollback with health checks
    DEVOPS-02: Credential Rotation Alert (Daily 07:00 SAST = 05:00 UTC)
    DEVOPS-03: Release Notes Generator   (Webhook) - AI-generated release notes

Usage:
    python tools/deploy_devops_coordinator.py build              # Build all JSONs
    python tools/deploy_devops_coordinator.py build devops01     # Build DEVOPS-01 only
    python tools/deploy_devops_coordinator.py deploy             # Build + Deploy (inactive)
    python tools/deploy_devops_coordinator.py activate           # Build + Deploy + Activate
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
CRED_N8N_API = {
    "id": os.getenv("SELFHEALING_N8N_API_CRED_ID", "xymp9Nho08mRW2Wz"),
    "name": "n8n API Key",
}

# -- Airtable IDs --
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "appTCh0EeXQp0XqzW")
TABLE_DEVOPS_RELEASES = os.getenv("DEVOPS_TABLE_RELEASES", "REPLACE_AFTER_SETUP")

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
# DEVOPS-01: Auto-Deploy Monitor (Webhook)
# ======================================================================

def build_devops01_nodes():
    nodes = []

    # 1. Webhook
    nodes.append({"parameters": {"path": "devops-deploy", "responseMode": "responseNode", "options": {}},
                   "id": uid(), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                   "position": [220, 300], "webhookId": uid()})

    # 2. Parse Deploy Request (Code)
    nodes.append({"parameters": {"jsCode": """const body = $input.first().json.body || $input.first().json;
return { json: {
  workflow_id: body.workflow_id || '',
  action: body.action || 'deploy',
  source: body.source || 'manual',
  deploy_id: 'DEP-' + Date.now().toString(36).toUpperCase(),
  requested_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Parse Deploy Request", "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [440, 300]})

    # 3. Fetch Current Workflow (n8n API)
    nodes.append({"parameters": {
        "method": "GET",
        "url": "=" + N8N_BASE_URL + "/api/v1/workflows/{{ $json.workflow_id }}",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "options": {}},
                   "id": uid(), "name": "Fetch Current Workflow",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [660, 300], "credentials": {"httpHeaderAuth": CRED_N8N_API}})

    # 4. Store Pre-Deploy Snapshot (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DEVOPS_RELEASES),
        "columns": {"value": {
            "deploy_id": "={{ $('Parse Deploy Request').first().json.deploy_id }}",
            "workflow_id": "={{ $('Parse Deploy Request').first().json.workflow_id }}",
            "action": "={{ $('Parse Deploy Request').first().json.action }}",
            "source": "={{ $('Parse Deploy Request').first().json.source }}",
            "workflow_name": "={{ $json.name || 'Unknown' }}",
            "pre_deploy_snapshot": "={{ JSON.stringify({active: $json.active, nodeCount: ($json.nodes || []).length, updatedAt: $json.updatedAt}).substring(0, 1000) }}",
            "status": "In Progress",
            "started_at": "={{ $('Parse Deploy Request').first().json.requested_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Store Snapshot",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [880, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 5. Execute Deploy Action (Code - activate or deactivate)
    nodes.append({"parameters": {"jsCode": """const req = $('Parse Deploy Request').first().json;
const action = req.action;
const workflowId = req.workflow_id;

// Determine the API call to make
let apiAction = '';
if (action === 'deploy' || action === 'activate') {
  apiAction = 'activate';
} else if (action === 'rollback' || action === 'deactivate') {
  apiAction = 'deactivate';
} else {
  apiAction = 'activate';
}

return { json: {
  workflow_id: workflowId,
  deploy_id: req.deploy_id,
  api_action: apiAction,
  action_url: '""" + N8N_BASE_URL + """/api/v1/workflows/' + workflowId + '/' + apiAction,
}};"""},
                   "id": uid(), "name": "Prepare Action",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1100, 300]})

    # 6. Execute Action (httpRequest to n8n API)
    nodes.append({"parameters": {
        "method": "POST",
        "url": "={{ $json.action_url }}",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "options": {}},
                   "id": uid(), "name": "Execute Action",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [1320, 300], "credentials": {"httpHeaderAuth": CRED_N8N_API}})

    # 7. Wait 60 seconds for health check
    nodes.append({"parameters": {"amount": 60, "unit": "seconds"},
                   "id": uid(), "name": "Wait 60s",
                   "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [1540, 300]})

    # 8. Health Check - fetch recent executions
    nodes.append({"parameters": {
        "method": "GET",
        "url": "=" + N8N_BASE_URL + "/api/v1/executions?workflowId={{ $('Prepare Action').first().json.workflow_id }}&limit=3&status=error",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "options": {}},
                   "id": uid(), "name": "Health Check Executions",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [1760, 300], "credentials": {"httpHeaderAuth": CRED_N8N_API}})

    # 9. Evaluate Health (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const executions = resp.data || resp.results || [];
const recentErrors = executions.filter(e => {
  const finishedAt = new Date(e.stoppedAt || e.startedAt || '');
  const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000);
  return finishedAt > fiveMinAgo;
});
const deployId = $('Prepare Action').first().json.deploy_id;
const workflowId = $('Prepare Action').first().json.workflow_id;
const healthy = recentErrors.length === 0;
return { json: {
  deploy_id: deployId,
  workflow_id: workflowId,
  healthy,
  recent_error_count: recentErrors.length,
  health_checked_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Evaluate Health",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1980, 300]})

    # 10. If healthy
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.healthy }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "equals"}}]}, "options": {}},
                   "id": uid(), "name": "Is Healthy",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [2200, 300]})

    # 11. Update Success (Airtable)
    nodes.append({"parameters": {"operation": "update", **airtable_ref(ORCH_BASE_ID, TABLE_DEVOPS_RELEASES),
        "columns": {"value": {
            "status": "Success",
            "health_check": "Passed",
            "completed_at": "={{ $('Evaluate Health').first().json.health_checked_at }}"}},
        "options": {}, "matchingColumns": ["deploy_id"]},
                   "id": uid(), "name": "Update Success",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [2420, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 12. Auto-Rollback (httpRequest - deactivate)
    nodes.append({"parameters": {
        "method": "POST",
        "url": "=" + N8N_BASE_URL + "/api/v1/workflows/{{ $('Evaluate Health').first().json.workflow_id }}/deactivate",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "options": {}},
                   "id": uid(), "name": "Auto-Rollback",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [2420, 420], "credentials": {"httpHeaderAuth": CRED_N8N_API}})

    # 13. Update Failed (Airtable)
    nodes.append({"parameters": {"operation": "update", **airtable_ref(ORCH_BASE_ID, TABLE_DEVOPS_RELEASES),
        "columns": {"value": {
            "status": "Rolled Back",
            "health_check": "=Failed - {{ $('Evaluate Health').first().json.recent_error_count }} errors",
            "completed_at": "={{ $('Evaluate Health').first().json.health_checked_at }}"}},
        "options": {}, "matchingColumns": ["deploy_id"]},
                   "id": uid(), "name": "Update Failed",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [2640, 420], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 14. Alert Rollback Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=DEPLOY ROLLBACK: {{ $('Evaluate Health').first().json.workflow_id }} - {{ $('Evaluate Health').first().json.recent_error_count }} errors",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#DC3545;padding:15px;text-align:center"><h2 style="color:white;margin:0">Deployment Rolled Back</h2></div>
<div style="padding:20px">
<p><b>Deploy ID:</b> {{ $('Evaluate Health').first().json.deploy_id }}</p>
<p><b>Workflow ID:</b> {{ $('Evaluate Health').first().json.workflow_id }}</p>
<p><b>Errors Detected:</b> {{ $('Evaluate Health').first().json.recent_error_count }}</p>
<p style="color:red;font-weight:bold">Workflow has been automatically deactivated due to health check failure.</p>
<p>Please investigate the errors and redeploy when fixed.</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM DevOps Coordinator - Auto-Rollback</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Alert Rollback Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [2860, 420], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 15. Respond Webhook
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": "={{ JSON.stringify({success: true, deploy_id: $('Evaluate Health').first().json.deploy_id, healthy: $('Evaluate Health').first().json.healthy, workflow_id: $('Evaluate Health').first().json.workflow_id}) }}",
        "options": {}},
                   "id": uid(), "name": "Respond Webhook",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [2860, 300]})

    return nodes


def build_devops01_connections(nodes):
    return {
        "Webhook": {"main": [[{"node": "Parse Deploy Request", "type": "main", "index": 0}]]},
        "Parse Deploy Request": {"main": [[{"node": "Fetch Current Workflow", "type": "main", "index": 0}]]},
        "Fetch Current Workflow": {"main": [[{"node": "Store Snapshot", "type": "main", "index": 0}]]},
        "Store Snapshot": {"main": [[{"node": "Prepare Action", "type": "main", "index": 0}]]},
        "Prepare Action": {"main": [[{"node": "Execute Action", "type": "main", "index": 0}]]},
        "Execute Action": {"main": [[{"node": "Wait 60s", "type": "main", "index": 0}]]},
        "Wait 60s": {"main": [[{"node": "Health Check Executions", "type": "main", "index": 0}]]},
        "Health Check Executions": {"main": [[{"node": "Evaluate Health", "type": "main", "index": 0}]]},
        "Evaluate Health": {"main": [[{"node": "Is Healthy", "type": "main", "index": 0}]]},
        "Is Healthy": {"main": [
            [{"node": "Update Success", "type": "main", "index": 0}],
            [{"node": "Auto-Rollback", "type": "main", "index": 0}],
        ]},
        "Update Success": {"main": [[{"node": "Respond Webhook", "type": "main", "index": 0}]]},
        "Auto-Rollback": {"main": [[{"node": "Update Failed", "type": "main", "index": 0}]]},
        "Update Failed": {"main": [[{"node": "Alert Rollback Email", "type": "main", "index": 0}]]},
        "Alert Rollback Email": {"main": [[{"node": "Respond Webhook", "type": "main", "index": 0}]]},
    }


# ======================================================================
# DEVOPS-02: Credential Rotation Alert (Daily 07:00 SAST = 05:00 UTC)
# ======================================================================

def build_devops02_nodes():
    nodes = []

    # 1. Schedule Trigger (daily 05:00 UTC = 07:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 5 * * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Check Credential Expiry (Code)
    nodes.append({"parameters": {"jsCode": """// Known credential rotation schedule
// Format: {name, type, last_rotated (ISO), rotation_interval_days, warn_days_before}
const credentials = [
  {name: 'OpenRouter API Key', type: 'httpHeaderAuth', last_rotated: '2026-01-15', rotation_interval_days: 90, warn_days_before: 7},
  {name: 'Gmail OAuth', type: 'gmailOAuth2', last_rotated: '2026-02-01', rotation_interval_days: 365, warn_days_before: 30},
  {name: 'Airtable PAT', type: 'airtableTokenApi', last_rotated: '2026-01-01', rotation_interval_days: 180, warn_days_before: 14},
  {name: 'n8n API Key', type: 'httpHeaderAuth', last_rotated: '2026-02-15', rotation_interval_days: 90, warn_days_before: 7},
  {name: 'QuickBooks OAuth', type: 'quickBooksOAuth2Api', last_rotated: '2026-01-20', rotation_interval_days: 365, warn_days_before: 30},
  {name: 'SerpAPI Key', type: 'httpHeaderAuth', last_rotated: '2026-02-01', rotation_interval_days: 365, warn_days_before: 14},
  {name: 'Tavily API Key', type: 'httpHeaderAuth', last_rotated: '2026-03-01', rotation_interval_days: 365, warn_days_before: 14},
];

const now = new Date();
const results = [];
let expiringCount = 0;
let expiredCount = 0;

for (const cred of credentials) {
  const lastRotated = new Date(cred.last_rotated);
  const expiresAt = new Date(lastRotated.getTime() + cred.rotation_interval_days * 86400000);
  const warnAt = new Date(expiresAt.getTime() - cred.warn_days_before * 86400000);
  const daysUntilExpiry = Math.round((expiresAt - now) / 86400000);

  let status = 'OK';
  if (daysUntilExpiry <= 0) { status = 'EXPIRED'; expiredCount++; }
  else if (now >= warnAt) { status = 'EXPIRING_SOON'; expiringCount++; }

  results.push({
    name: cred.name, type: cred.type, status, days_until_expiry: daysUntilExpiry,
    expires_at: expiresAt.toISOString().split('T')[0],
    last_rotated: cred.last_rotated,
  });
}

const needsAlert = expiringCount > 0 || expiredCount > 0;
return { json: {
  credentials: results,
  total: credentials.length,
  expiring_count: expiringCount,
  expired_count: expiredCount,
  needs_alert: needsAlert,
  checked_at: now.toISOString(),
  summary: results.filter(r => r.status !== 'OK').map(r => r.name + ': ' + r.status + ' (' + r.days_until_expiry + ' days)').join('; ') || 'All credentials OK',
}};"""},
                   "id": uid(), "name": "Check Credential Expiry",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [440, 300]})

    # 3. Write Check Results (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DEVOPS_RELEASES),
        "columns": {"value": {
            "deploy_id": "=CRED-CHECK-{{ $now.toFormat('yyyy-MM-dd') }}",
            "action": "credential_check",
            "status": "={{ $json.needs_alert ? 'Action Required' : 'All Clear' }}",
            "health_check": "={{ $json.summary }}",
            "pre_deploy_snapshot": "={{ JSON.stringify($json.credentials) }}",
            "started_at": "={{ $json.checked_at }}",
            "completed_at": "={{ $json.checked_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Check Results",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [660, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 4. If needs alert
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $('Check Credential Expiry').first().json.needs_alert }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "equals"}}]}, "options": {}},
                   "id": uid(), "name": "Needs Alert",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [880, 300]})

    # 5. Alert Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=CREDENTIAL ALERT: {{ $('Check Credential Expiry').first().json.expired_count }} expired, {{ $('Check Credential Expiry').first().json.expiring_count }} expiring soon",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FFA500;padding:15px;text-align:center"><h2 style="color:white;margin:0">Credential Rotation Alert</h2></div>
<div style="padding:20px">
<p><b>Expired:</b> <span style="color:red;font-weight:bold">{{ $('Check Credential Expiry').first().json.expired_count }}</span></p>
<p><b>Expiring Soon:</b> <span style="color:orange;font-weight:bold">{{ $('Check Credential Expiry').first().json.expiring_count }}</span></p>
<h3>Details</h3><p>{{ $('Check Credential Expiry').first().json.summary }}</p>
<h3>All Credentials</h3>
<table style="width:100%;border-collapse:collapse;font-size:12px">
<tr style="background:#f0f0f0"><th style="padding:5px;border:1px solid #ddd">Name</th><th style="padding:5px;border:1px solid #ddd">Status</th><th style="padding:5px;border:1px solid #ddd">Days Left</th><th style="padding:5px;border:1px solid #ddd">Expires</th></tr>
</table>
<p style="font-size:11px;color:#666">{{ JSON.stringify($('Check Credential Expiry').first().json.credentials) }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM DevOps Coordinator - Credential Monitor</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Alert Credential Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1100, 200], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_devops02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Check Credential Expiry", "type": "main", "index": 0}]]},
        "Check Credential Expiry": {"main": [[{"node": "Write Check Results", "type": "main", "index": 0}]]},
        "Write Check Results": {"main": [[{"node": "Needs Alert", "type": "main", "index": 0}]]},
        "Needs Alert": {"main": [
            [{"node": "Alert Credential Email", "type": "main", "index": 0}],
        ]},
    }


# ======================================================================
# DEVOPS-03: Release Notes Generator (Webhook)
# ======================================================================

def build_devops03_nodes():
    nodes = []

    # 1. Webhook
    nodes.append({"parameters": {"path": "devops-release-notes", "responseMode": "responseNode", "options": {}},
                   "id": uid(), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                   "position": [220, 300], "webhookId": uid()})

    # 2. Parse Request (Code)
    nodes.append({"parameters": {"jsCode": """const body = $input.first().json.body || $input.first().json;
const now = new Date();
const sevenDaysAgo = new Date(now.getTime() - 7 * 86400000);
return { json: {
  from_date: body.from_date || sevenDaysAgo.toISOString().split('T')[0],
  to_date: body.to_date || now.toISOString().split('T')[0],
  requested_by: body.requested_by || 'system',
  release_id: 'REL-' + Date.now().toString(36).toUpperCase(),
  requested_at: now.toISOString(),
}};"""},
                   "id": uid(), "name": "Parse Request", "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [440, 300]})

    # 3. Fetch Recent Executions (n8n API)
    nodes.append({"parameters": {
        "method": "GET",
        "url": "=" + N8N_BASE_URL + "/api/v1/executions?limit=50&status=success",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "options": {}},
                   "id": uid(), "name": "Fetch Executions",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [660, 200], "credentials": {"httpHeaderAuth": CRED_N8N_API}})

    # 4. Fetch Workflows (n8n API)
    nodes.append({"parameters": {
        "method": "GET",
        "url": "=" + N8N_BASE_URL + "/api/v1/workflows?limit=100",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "options": {}},
                   "id": uid(), "name": "Fetch Workflows",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [660, 420], "credentials": {"httpHeaderAuth": CRED_N8N_API}})

    # 5. Compile Changes (Code)
    nodes.append({"parameters": {"jsCode": """const execResp = $('Fetch Executions').first().json;
const wfResp = $('Fetch Workflows').first().json;
const req = $('Parse Request').first().json;
const fromDate = new Date(req.from_date);
const toDate = new Date(req.to_date);
toDate.setHours(23, 59, 59);

const executions = execResp.data || execResp.results || [];
const workflows = wfResp.data || wfResp.results || [];

// Find workflows updated in date range
const updatedWfs = workflows.filter(wf => {
  const updated = new Date(wf.updatedAt || '');
  return updated >= fromDate && updated <= toDate;
});

// Count executions per workflow in date range
const execCounts = {};
for (const exec of executions) {
  const started = new Date(exec.startedAt || '');
  if (started >= fromDate && started <= toDate) {
    const wfId = exec.workflowId || exec.workflowData?.id || '';
    execCounts[wfId] = (execCounts[wfId] || 0) + 1;
  }
}

const changeLog = updatedWfs.map(wf => {
  return 'Workflow: ' + wf.name + ' (ID: ' + wf.id + ')\\nUpdated: ' + (wf.updatedAt || 'N/A') + '\\nActive: ' + wf.active + '\\nNodes: ' + (wf.nodes || []).length + '\\nExecutions in period: ' + (execCounts[wf.id] || 0);
}).join('\\n---\\n');

return { json: {
  release_id: req.release_id,
  from_date: req.from_date,
  to_date: req.to_date,
  updated_workflow_count: updatedWfs.length,
  total_executions: Object.values(execCounts).reduce((a, b) => a + b, 0),
  change_log: changeLog || 'No workflow changes detected in this period.',
}};"""},
                   "id": uid(), "name": "Compile Changes",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [900, 300]})

    # 6. AI Generate Release Notes (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1500,
  "messages": [
    {"role": "system", "content": "Generate professional release notes for AnyVision Media's automation platform. Format as markdown with sections: ## Summary, ## Changes, ## Stats, ## Notes. Be concise and highlight key changes."},
    {"role": "user", "content": "Generate release notes for period {{ $json.from_date }} to {{ $json.to_date }}.\\n\\nUpdated Workflows: {{ $json.updated_workflow_count }}\\nTotal Executions: {{ $json.total_executions }}\\n\\nChange Log:\\n{{ $json.change_log }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Generate Release Notes",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [1120, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 7. Extract Notes (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const releaseNotes = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : 'No release notes generated.';
const meta = $('Compile Changes').first().json;
return { json: {
  release_id: meta.release_id,
  from_date: meta.from_date,
  to_date: meta.to_date,
  release_notes: releaseNotes,
  updated_workflows: meta.updated_workflow_count,
  total_executions: meta.total_executions,
  generated_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Extract Notes",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1340, 300]})

    # 8. Write Release Notes (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_DEVOPS_RELEASES),
        "columns": {"value": {
            "deploy_id": "={{ $json.release_id }}",
            "action": "release_notes",
            "workflow_name": "=Release {{ $json.from_date }} to {{ $json.to_date }}",
            "status": "Generated",
            "health_check": "={{ $json.updated_workflows }} workflows, {{ $json.total_executions }} executions",
            "pre_deploy_snapshot": "={{ $json.release_notes.substring(0, 2000) }}",
            "started_at": "={{ $json.generated_at }}",
            "completed_at": "={{ $json.generated_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Release Notes",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1560, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 9. Respond Webhook
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": "={{ JSON.stringify({success: true, release_id: $('Extract Notes').first().json.release_id, release_notes: $('Extract Notes').first().json.release_notes, period: $('Extract Notes').first().json.from_date + ' to ' + $('Extract Notes').first().json.to_date}) }}",
        "options": {}},
                   "id": uid(), "name": "Respond Webhook",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [1780, 300]})

    return nodes


def build_devops03_connections(nodes):
    return {
        "Webhook": {"main": [[{"node": "Parse Request", "type": "main", "index": 0}]]},
        "Parse Request": {"main": [[
            {"node": "Fetch Executions", "type": "main", "index": 0},
            {"node": "Fetch Workflows", "type": "main", "index": 0},
        ]]},
        "Fetch Executions": {"main": [[{"node": "Compile Changes", "type": "main", "index": 0}]]},
        "Fetch Workflows": {"main": [[{"node": "Compile Changes", "type": "main", "index": 0}]]},
        "Compile Changes": {"main": [[{"node": "AI Generate Release Notes", "type": "main", "index": 0}]]},
        "AI Generate Release Notes": {"main": [[{"node": "Extract Notes", "type": "main", "index": 0}]]},
        "Extract Notes": {"main": [[{"node": "Write Release Notes", "type": "main", "index": 0}]]},
        "Write Release Notes": {"main": [[{"node": "Respond Webhook", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "devops01": {"name": "DEVOPS-01 Auto-Deploy Monitor", "build_nodes": build_devops01_nodes,
                 "build_connections": build_devops01_connections,
                 "filename": "devops01_auto_deploy_monitor.json", "tags": ["devops", "deploy", "health-check"]},
    "devops02": {"name": "DEVOPS-02 Credential Rotation Alert", "build_nodes": build_devops02_nodes,
                 "build_connections": build_devops02_connections,
                 "filename": "devops02_credential_rotation_alert.json", "tags": ["devops", "credentials", "security"]},
    "devops03": {"name": "DEVOPS-03 Release Notes Generator", "build_nodes": build_devops03_nodes,
                 "build_connections": build_devops03_connections,
                 "filename": "devops03_release_notes_generator.json", "tags": ["devops", "release-notes", "documentation"]},
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
        "meta": {"templateCredsSetupCompleted": True, "builder": "deploy_devops_coordinator.py",
                 "built_at": datetime.now().isoformat()},
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "devops"
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
        print("AVM DevOps Coordinator - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_devops_coordinator.py build              # Build all")
        print("  python tools/deploy_devops_coordinator.py build devops01     # Build one")
        print("  python tools/deploy_devops_coordinator.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_devops_coordinator.py activate           # Build + Deploy + Activate")
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
    print("AVM DEVOPS COORDINATOR - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/devops/")

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
