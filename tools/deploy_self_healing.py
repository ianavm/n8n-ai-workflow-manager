"""
Universal Self-Healing Workflow Builder & Deployer

Builds a single self-healing workflow that monitors ALL workflows on an n8n
instance and auto-recovers from common errors. Deploy one per n8n instance.

Features:
    - Error Trigger catches all workflow errors instance-wide
    - AI classification via OpenRouter (5 categories)
    - Auto-fix: retry, deactivate/reactivate, delayed retry
    - Human alert for unfixable errors (credential, code, validation)
    - 15-minute health checks with email reports
    - Airtable error logging (optional)
    - Webhook for external error reporting
    - Deployable to any n8n instance (own + clients)

Usage:
    python tools/deploy_self_healing.py build
    python tools/deploy_self_healing.py deploy
    python tools/deploy_self_healing.py activate
    python tools/deploy_self_healing.py activate --set-error-workflow

Options:
    --email EMAIL           Alert email override
    --instance NAME         Instance display name override
    --no-airtable           Disable Airtable logging
    --set-error-workflow    Set this as error workflow for ALL other workflows
"""

import json
import sys
import uuid
import os
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# ── Credential Constants ──────────────────────────────────────
CRED_OPENROUTER = {"id": "9ZgHenDBrFuyboov", "name": "OpenRouter 2WC"}
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_N8N_API = {
    "id": os.getenv("SELFHEALING_N8N_API_CRED_ID", "REPLACE_WITH_N8N_HEADER_AUTH_CRED"),
    "name": "n8n API Key",
}

# ── Parameterized Config ──────────────────────────────────────
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
INSTANCE_NAME = os.getenv("SELFHEALING_INSTANCE_NAME", "AnyVision Production")
AIRTABLE_ENABLED = os.getenv("SELFHEALING_AIRTABLE_ON", "true").lower() == "true"
AIRTABLE_BASE_ID = os.getenv("SELFHEALING_AIRTABLE_BASE", os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID"))
TABLE_ERROR_LOG = os.getenv("SELFHEALING_TABLE_ERROR_LOG", "REPLACE_WITH_TABLE_ID")
CHECK_INTERVAL = int(os.getenv("SELFHEALING_CHECK_INTERVAL", "15"))


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════
# CODE NODE SCRIPTS
# ══════════════════════════════════════════════════════════════

EXTRACT_ERROR_CODE = r"""
// Normalizes error data from Error Trigger, Manual Test, or Webhook
const input = $input.first().json;

let errorMessage, errorNode, executionId, executionUrl, workflowId, workflowName;

if (input.testMode) {
  // From Manual Trigger test
  errorMessage = input.errorMessage || 'Test error: connection timeout';
  errorNode = input.errorNode || 'HTTP Request';
  executionId = 'test-' + Date.now();
  executionUrl = '';
  workflowId = input.workflowId || 'test';
  workflowName = input.workflowName || 'Test Workflow';
} else if (input.execution) {
  // From Error Trigger
  const execution = input.execution;
  const workflow = input.workflow || {};
  errorMessage = execution.error?.message || 'Unknown error';
  errorNode = execution.error?.node?.name || execution.lastNodeExecuted || 'Unknown';
  executionId = execution.id || '';
  executionUrl = execution.url || '';
  workflowId = execution.workflowId || '';
  workflowName = workflow.name || 'Unknown';
} else {
  // From Webhook external report
  errorMessage = input.error_message || input.message || 'Unknown error';
  errorNode = input.error_node || input.node || 'Unknown';
  executionId = input.execution_id || '';
  executionUrl = input.execution_url || '';
  workflowId = input.workflow_id || '';
  workflowName = input.workflow_name || 'External Report';
}

// Quick regex pre-classification
let hintCategory = 'unknown';
const msg = errorMessage.toLowerCase();
if (msg.includes('timeout') || msg.includes('econnreset') || msg.includes('econnrefused') || msg.includes('enotfound')) {
  hintCategory = 'connection_timeout';
} else if (msg.includes('429') || msg.includes('rate limit') || msg.includes('too many requests')) {
  hintCategory = 'rate_limit';
} else if (msg.includes('500') || msg.includes('502') || msg.includes('503') || msg.includes('504')) {
  hintCategory = 'server_error';
} else if (msg.includes('webhook') && (msg.includes('stuck') || msg.includes('not responding') || msg.includes('listen'))) {
  hintCategory = 'webhook_stuck';
} else if (msg.includes('credential') || msg.includes('unauthorized') || msg.includes('401') || msg.includes('403')) {
  hintCategory = 'credential_error';
} else if (msg.includes('quota') || (msg.includes('gmail') && msg.includes('limit'))) {
  hintCategory = 'quota_exceeded';
} else if (msg.includes('syntax') || msg.includes('unexpected token') || msg.includes('is not defined') || msg.includes('is not a function')) {
  hintCategory = 'code_error';
} else if (msg.includes('required') || msg.includes('missing') || msg.includes('validation') || msg.includes('could not find')) {
  hintCategory = 'validation_error';
}

// Cooldown check via static data
const staticData = $getWorkflowStaticData('global');
const cooldownKey = `${workflowId}_${errorNode}`;
const now = Date.now();
const lastFixed = staticData[cooldownKey] || 0;
const cooldownMs = 5 * 60 * 1000; // 5 minute cooldown
const inCooldown = (now - lastFixed) < cooldownMs;

return {
  json: {
    errorMessage,
    errorNode,
    executionId,
    executionUrl,
    workflowId,
    workflowName,
    hintCategory,
    timestamp: new Date().toISOString(),
    isTest: !!input.testMode,
    inCooldown,
    cooldownKey,
  }
};
""".strip()

PARSE_AI_RESPONSE_CODE = r"""
// Parse OpenRouter AI classification response with regex fallback
const input = $input.first().json;
const errorData = $('Extract Error Data').first().json;

let classification;
try {
  const content = input.choices[0].message.content;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  const jsonMatch = cleaned.match(/\{[\s\S]*\}/);
  classification = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);
} catch(e) {
  // Fallback to regex-based classification
  const hint = errorData.hintCategory;
  const categoryMap = {
    'connection_timeout': 'auto_retry',
    'rate_limit': 'delay_retry',
    'server_error': 'auto_retry',
    'webhook_stuck': 'deactivate_reactivate',
    'credential_error': 'needs_human',
    'quota_exceeded': 'delay_retry',
    'code_error': 'needs_human',
    'validation_error': 'needs_human',
  };
  classification = {
    category: categoryMap[hint] || 'needs_human',
    confidence: 0.5,
    explanation: `Regex fallback: ${hint} (AI unavailable: ${e.message})`,
    suggested_action: categoryMap[hint] || 'alert_human',
    wait_seconds: hint === 'quota_exceeded' ? 3600 : hint === 'rate_limit' ? 30 : 0,
    retry_count: hint === 'server_error' ? 3 : hint === 'connection_timeout' ? 2 : 1,
  };
}

// Low confidence → escalate to human
if ((classification.confidence || 0) < 0.6) {
  classification.category = 'needs_human';
  classification.explanation = (classification.explanation || '') + ' (low confidence — escalating)';
}

// If in cooldown, force to needs_human to avoid retry loops
if (errorData.inCooldown) {
  classification.category = 'needs_human';
  classification.explanation = `Repeat error within 5min cooldown. Original: ${classification.category}. ${classification.explanation || ''}`;
}

return {
  json: {
    ...errorData,
    category: classification.category || 'needs_human',
    confidence: classification.confidence || 0,
    explanation: classification.explanation || '',
    suggestedAction: classification.suggested_action || 'alert_human',
    waitSeconds: classification.wait_seconds || 0,
    retryCount: classification.retry_count || 1,
  }
};
""".strip()

COMPUTE_DELAY_CODE = r"""
// Determine wait time based on error type
const input = $input.first().json;

let waitSeconds = input.waitSeconds || 30;
const msg = input.errorMessage.toLowerCase();

if (msg.includes('gmail') || msg.includes('quota')) {
  waitSeconds = 3600; // 1 hour for Gmail quota
} else if (msg.includes('rate limit') || msg.includes('429')) {
  waitSeconds = 30;
} else if (msg.includes('airtable') && msg.includes('rate')) {
  waitSeconds = 30;
}

// Record cooldown in static data
const staticData = $getWorkflowStaticData('global');
staticData[input.cooldownKey] = Date.now();

return {
  json: {
    ...input,
    waitSeconds,
    fixAction: 'delayed_retry',
    fixDescription: `Waiting ${waitSeconds}s before retry: ${input.explanation}`,
  }
};
""".strip()

SET_RETRY_RESULT_CODE = r"""
// Tag result from auto-retry branch
const input = $input.first().json;
const errorData = $('Parse AI Response').first().json;

// Record cooldown
const staticData = $getWorkflowStaticData('global');
staticData[errorData.cooldownKey] = Date.now();

return {
  json: {
    ...errorData,
    fixAction: 'retried',
    fixResult: input.success !== false ? 'success' : 'failed',
    fixDescription: 'Auto-retried execution via n8n API',
  }
};
""".strip()

SET_REACTIVATE_RESULT_CODE = r"""
// Tag result from deactivate/reactivate branch
const errorData = $('Parse AI Response').first().json;

// Record cooldown
const staticData = $getWorkflowStaticData('global');
staticData[errorData.cooldownKey] = Date.now();

return {
  json: {
    ...errorData,
    fixAction: 'deactivated_reactivated',
    fixResult: 'success',
    fixDescription: 'Deactivated and reactivated workflow to reset triggers',
  }
};
""".strip()

SET_DELAYED_RESULT_CODE = r"""
// Tag result from delayed retry branch
const input = $input.first().json;
const errorData = $('Compute Wait Time').first().json;
return {
  json: {
    ...errorData,
    fixResult: input.success !== false ? 'success' : 'failed',
  }
};
""".strip()

BUILD_ALERT_EMAIL_CODE = r"""
// Build HTML alert email for human-intervention errors
const data = $input.first().json;
const instanceName = '""" + INSTANCE_NAME + r"""';

const severityColor = data.category === 'needs_human' ? '#dc2626' : '#f59e0b';
const severityLabel = data.category === 'needs_human' ? 'REQUIRES ACTION' : 'UNKNOWN ERROR';

const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;background-color:#f4f4f4;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background-color:#ffffff;">
    <tr>
      <td style="padding:30px 40px 20px;border-bottom:3px solid ${severityColor};">
        <h1 style="margin:0;font-size:22px;color:#1A1A2E;">Self-Healing Alert</h1>
        <p style="margin:5px 0 0;font-size:12px;color:${severityColor};text-transform:uppercase;letter-spacing:1px;">${severityLabel}</p>
      </td>
    </tr>
    <tr>
      <td style="padding:30px 40px;">
        <div style="margin:0 0 20px;padding:16px;background-color:#FEF2F2;border-left:3px solid ${severityColor};border-radius:4px;">
          <p style="margin:0;font-size:14px;color:#333;line-height:1.8;">
            <strong>Workflow:</strong> ${data.workflowName}<br>
            <strong>Failed Node:</strong> ${data.errorNode}<br>
            <strong>Time:</strong> ${data.timestamp}<br>
            <strong>Category:</strong> ${data.category}<br>
            <strong>Confidence:</strong> ${Math.round((data.confidence || 0) * 100)}%
          </p>
        </div>
        <p style="margin:0 0 12px;font-size:15px;color:#333;"><strong>Error Message:</strong></p>
        <div style="margin:0 0 20px;padding:12px;background:#f8f8f8;border-radius:4px;font-family:monospace;font-size:13px;color:#c0392b;word-break:break-all;">
          ${data.errorMessage}
        </div>
        <p style="margin:0 0 12px;font-size:15px;color:#333;"><strong>AI Analysis:</strong></p>
        <p style="margin:0 0 20px;font-size:14px;color:#666;">${data.explanation}</p>
        ${data.executionUrl ? '<p style="margin:0;"><a href="' + data.executionUrl + '" style="display:inline-block;padding:10px 24px;background-color:#FF6D5A;color:#fff;text-decoration:none;border-radius:4px;font-size:14px;">View Execution in n8n</a></p>' : ''}
      </td>
    </tr>
    <tr>
      <td style="padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;">
        <p style="margin:0;font-size:11px;color:#999;line-height:1.5;">
          AnyVision Media Self-Healing Monitor | ${instanceName}<br>
          This error could not be auto-resolved. Manual intervention required.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>`;

return {
  json: {
    ...data,
    alertHtml: html,
    alertSubject: `[SELF-HEALING] ${severityLabel}: ${data.workflowName} - ${data.errorNode}`,
    fixAction: 'alerted_human',
    fixResult: 'pending',
    fixDescription: 'Sent alert email — requires manual intervention',
  }
};
""".strip()

ANALYZE_HEALTH_CODE = r"""
// Analyze instance health from workflow list + recent errors
const workflows = $('Fetch All Workflows').first().json;
const errorsData = $('Fetch Recent Errors').first().json;

const workflowList = Array.isArray(workflows) ? workflows : (workflows.data || []);
const errorList = Array.isArray(errorsData) ? errorsData : (errorsData.data || []);

const totalWorkflows = workflowList.length;
const activeWorkflows = workflowList.filter(w => w.active).length;
const inactiveWorkflows = totalWorkflows - activeWorkflows;

// Count errors per workflow
const errorsByWorkflow = {};
const errorThreshold = 3;

for (const exec of errorList) {
  const wfId = exec.workflowId || 'unknown';
  const wfName = exec.workflowData?.name || workflowList.find(w => w.id === wfId)?.name || 'Unknown';
  if (!errorsByWorkflow[wfId]) {
    errorsByWorkflow[wfId] = { name: wfName, count: 0, lastError: '' };
  }
  errorsByWorkflow[wfId].count++;
  if (!errorsByWorkflow[wfId].lastError) {
    errorsByWorkflow[wfId].lastError = exec.stoppedAt || '';
  }
}

const problematicWorkflows = Object.entries(errorsByWorkflow)
  .filter(([_, data]) => data.count >= errorThreshold)
  .map(([id, data]) => ({ id, ...data }));

// Suspicious inactive: not test/draft/backup/copy/old/disabled
const suspiciousInactive = workflowList
  .filter(w => !w.active)
  .filter(w => {
    const name = (w.name || '').toLowerCase();
    return !name.includes('test') && !name.includes('draft') &&
           !name.includes('backup') && !name.includes('old') &&
           !name.includes('copy') && !name.includes('disabled') &&
           !name.includes('combined');
  })
  .slice(0, 5);

const hasIssues = problematicWorkflows.length > 0;

return {
  json: {
    hasIssues,
    totalWorkflows,
    activeWorkflows,
    inactiveWorkflows,
    recentErrorCount: errorList.length,
    problematicWorkflows,
    suspiciousInactive,
    checkedAt: new Date().toISOString(),
  }
};
""".strip()

BUILD_HEALTH_REPORT_CODE = r"""
// Build HTML health report email
const data = $input.first().json;
const instanceName = '""" + INSTANCE_NAME + r"""';

const problematicRows = (data.problematicWorkflows || []).map(w =>
  `<tr>
    <td style="padding:8px 12px;border-bottom:1px solid #eee;">${w.name}</td>
    <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;color:#dc2626;font-weight:bold;">${w.count}</td>
    <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:12px;color:#999;">${w.lastError || 'N/A'}</td>
  </tr>`
).join('');

const suspiciousRows = (data.suspiciousInactive || []).map(w =>
  `<tr>
    <td style="padding:8px 12px;border-bottom:1px solid #eee;">${w.name}</td>
    <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:12px;color:#999;">${w.id}</td>
  </tr>`
).join('');

const statusColor = data.hasIssues ? '#dc2626' : '#22c55e';

const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background-color:#f4f4f4;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background-color:#ffffff;">
    <tr>
      <td style="padding:30px 40px 20px;border-bottom:3px solid ${statusColor};">
        <h1 style="margin:0;font-size:22px;color:#1A1A2E;">Health Check Report</h1>
        <p style="margin:5px 0 0;font-size:12px;color:${statusColor};text-transform:uppercase;letter-spacing:1px;">${data.hasIssues ? 'ISSUES DETECTED' : 'ALL CLEAR'}</p>
      </td>
    </tr>
    <tr>
      <td style="padding:30px 40px;">
        <table width="100%" cellpadding="0" cellspacing="8" style="margin:0 0 20px;">
          <tr>
            <td style="padding:16px;background:#f0fdf4;border-radius:8px;text-align:center;width:33%;">
              <p style="margin:0;font-size:28px;font-weight:bold;color:#166534;">${data.activeWorkflows}</p>
              <p style="margin:4px 0 0;font-size:12px;color:#666;">Active</p>
            </td>
            <td style="padding:16px;background:#fefce8;border-radius:8px;text-align:center;width:33%;">
              <p style="margin:0;font-size:28px;font-weight:bold;color:#854d0e;">${data.inactiveWorkflows}</p>
              <p style="margin:4px 0 0;font-size:12px;color:#666;">Inactive</p>
            </td>
            <td style="padding:16px;background:#fef2f2;border-radius:8px;text-align:center;width:33%;">
              <p style="margin:0;font-size:28px;font-weight:bold;color:#991b1b;">${data.recentErrorCount}</p>
              <p style="margin:4px 0 0;font-size:12px;color:#666;">Recent Errors</p>
            </td>
          </tr>
        </table>
        ${problematicRows ? `
        <h3 style="margin:20px 0 8px;font-size:16px;color:#333;">Problematic Workflows</h3>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          <tr style="background:#f8f8f8;">
            <th style="padding:8px 12px;text-align:left;font-size:12px;border-bottom:2px solid #ddd;">Workflow</th>
            <th style="padding:8px 12px;text-align:center;font-size:12px;border-bottom:2px solid #ddd;">Errors</th>
            <th style="padding:8px 12px;text-align:left;font-size:12px;border-bottom:2px solid #ddd;">Last Error</th>
          </tr>
          ${problematicRows}
        </table>` : ''}
        ${suspiciousRows ? `
        <h3 style="margin:20px 0 8px;font-size:16px;color:#333;">Potentially Inactive Workflows</h3>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          <tr style="background:#f8f8f8;">
            <th style="padding:8px 12px;text-align:left;font-size:12px;border-bottom:2px solid #ddd;">Workflow</th>
            <th style="padding:8px 12px;text-align:left;font-size:12px;border-bottom:2px solid #ddd;">ID</th>
          </tr>
          ${suspiciousRows}
        </table>` : ''}
        <p style="margin:20px 0 0;font-size:12px;color:#999;">Checked: ${data.checkedAt}</p>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 40px;background-color:#f8f8f8;border-top:1px solid #eee;">
        <p style="margin:0;font-size:11px;color:#999;">AnyVision Media Self-Healing Monitor | ${instanceName}</p>
      </td>
    </tr>
  </table>
</body>
</html>`;

return {
  json: {
    ...data,
    reportHtml: html,
    reportSubject: `[HEALTH CHECK] ${data.hasIssues ? 'ISSUES DETECTED' : 'ALL CLEAR'} - ${data.totalWorkflows} workflows, ${data.recentErrorCount} errors`,
  }
};
""".strip()

VALIDATE_WEBHOOK_CODE = r"""
// Validate external error report payload
const body = $input.first().json.body || $input.first().json;

const required = ['error_message', 'workflow_name'];
const missing = required.filter(f => !body[f]);

if (missing.length > 0) {
  return {
    json: {
      valid: false,
      error: `Missing fields: ${missing.join(', ')}`,
      ...body,
    }
  };
}

return {
  json: {
    valid: true,
    error_message: body.error_message,
    error_node: body.error_node || 'Unknown',
    workflow_name: body.workflow_name,
    workflow_id: body.workflow_id || '',
    execution_id: body.execution_id || '',
    execution_url: body.execution_url || '',
  }
};
""".strip()

# ── AI Classification Prompt ──────────────────────────────────
AI_SYSTEM_PROMPT = (
    "You are an n8n workflow error classifier. Given an error message and context, "
    "classify it into exactly one category and provide a recovery recommendation.\\n\\n"
    "Categories:\\n"
    "1. auto_retry - Transient errors that will likely succeed on retry (connection timeouts, ECONNRESET, temporary 5xx server errors, Airtable rate limits)\\n"
    "2. deactivate_reactivate - Errors requiring a workflow restart (webhook stuck, listener not responding, trigger registration failures)\\n"
    "3. delay_retry - Errors requiring a wait period before retry (429 rate limits, Gmail quota exceeded, API daily limits)\\n"
    "4. needs_human - Errors requiring human intervention (expired credentials, 401/403 auth errors, code syntax errors, missing required fields, data validation failures, schema changes)\\n"
    "5. unknown - Cannot confidently classify\\n\\n"
    "Respond ONLY with valid JSON, no markdown:\\n"
    '{\"category\": \"<one of 5>\", \"confidence\": <0.0-1.0>, \"explanation\": \"<brief>\", '
    '\"suggested_action\": \"<action>\", \"wait_seconds\": <0 if n/a>, \"retry_count\": <1-3>}'
)


# ══════════════════════════════════════════════════════════════
# SELF-HEALING WORKFLOW BUILDER
# ══════════════════════════════════════════════════════════════

def build_nodes():
    """Build all 28 nodes + 2 sticky notes for the Self-Healing workflow."""
    nodes = []

    # ══════════════════════════════════════════════════════════
    # STICKY NOTES
    # ══════════════════════════════════════════════════════════

    nodes.append({
        "parameters": {
            "content": f"## Self-Healing Monitor — {INSTANCE_NAME}\n"
                       "Catches all workflow errors, classifies via AI, auto-fixes known patterns.\n"
                       "Sends alerts only for errors requiring human intervention.",
            "width": 1600,
            "height": 120,
            "color": 4,
        },
        "id": uid(),
        "name": "Note - Overview",
        "type": "n8n-nodes-base.stickyNote",
        "position": [160, 260],
        "typeVersion": 1,
    })

    nodes.append({
        "parameters": {
            "content": "## Error Categories\n"
                       "| Category | Action | Examples |\n"
                       "|----------|--------|----------|\n"
                       "| auto_retry | Retry immediately | Timeout, 5xx, ECONNRESET |\n"
                       "| deactivate_reactivate | Toggle workflow | Webhook stuck |\n"
                       "| delay_retry | Wait then retry | 429, Gmail quota |\n"
                       "| needs_human | Email alert | Credentials, code errors |\n"
                       "| unknown | Email alert | Low confidence |",
            "width": 600,
            "height": 200,
            "color": 6,
        },
        "id": uid(),
        "name": "Note - Categories",
        "type": "n8n-nodes-base.stickyNote",
        "position": [580, 100],
        "typeVersion": 1,
    })

    # ══════════════════════════════════════════════════════════
    # FLOW A: ERROR TRIGGER PATH (y=400)
    # ══════════════════════════════════════════════════════════

    # ── 1. Error Trigger ──
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 400],
        "typeVersion": 1,
    })

    # ── 2. Extract Error Data (Code) ──
    nodes.append({
        "parameters": {
            "jsCode": EXTRACT_ERROR_CODE,
        },
        "id": uid(),
        "name": "Extract Error Data",
        "type": "n8n-nodes-base.code",
        "position": [460, 500],
        "typeVersion": 2,
    })

    # ── 3. AI Classify Error (HTTP Request to OpenRouter) ──
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": '={"model":"anthropic/claude-sonnet-4-20250514","messages":[{"role":"system","content":"'
                        + AI_SYSTEM_PROMPT
                        + '"},{"role":"user","content":"Error in workflow \'{{ $json.workflowName }}\' at node \'{{ $json.errorNode }}\':\\n{{ $json.errorMessage }}\\n\\nPre-classification hint: {{ $json.hintCategory }}"}],"temperature":0.1,"max_tokens":300}',
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Classify Error",
        "type": "n8n-nodes-base.httpRequest",
        "position": [700, 500],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # ── 4. Parse AI Response (Code) ──
    nodes.append({
        "parameters": {
            "jsCode": PARSE_AI_RESPONSE_CODE,
        },
        "id": uid(),
        "name": "Parse AI Response",
        "type": "n8n-nodes-base.code",
        "position": [940, 500],
        "typeVersion": 2,
    })

    # ── 5. Route by Category (Switch v3.2) ──
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "outputKey": "auto_retry",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.category }}",
                                    "rightValue": "auto_retry",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                    },
                    {
                        "outputKey": "deactivate_reactivate",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.category }}",
                                    "rightValue": "deactivate_reactivate",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                    },
                    {
                        "outputKey": "delay_retry",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.category }}",
                                    "rightValue": "delay_retry",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                    },
                    {
                        "outputKey": "needs_human",
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.category }}",
                                    "rightValue": "needs_human",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                    },
                ],
            },
            "options": {"fallbackOutput": "extra"},
        },
        "id": uid(),
        "name": "Route by Category",
        "type": "n8n-nodes-base.switch",
        "position": [1180, 500],
        "typeVersion": 3.2,
    })

    # ── 6. Execute Retry (HTTP: POST /executions/{id}/retry) ──
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $env.N8N_BASE_URL }}/api/v1/executions/{{ $json.executionId }}/retry",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Execute Retry",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1420, 300],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # ── 7. Tag Retry Result (Code) ──
    nodes.append({
        "parameters": {
            "jsCode": SET_RETRY_RESULT_CODE,
        },
        "id": uid(),
        "name": "Tag Retry Result",
        "type": "n8n-nodes-base.code",
        "position": [1660, 300],
        "typeVersion": 2,
    })

    # ── 8. Deactivate Workflow (HTTP) ──
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $env.N8N_BASE_URL }}/api/v1/workflows/{{ $json.workflowId }}/deactivate",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Deactivate Workflow",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1420, 500],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # ── 9. Wait Then Reactivate ──
    nodes.append({
        "parameters": {"amount": 5, "unit": "seconds"},
        "id": uid(),
        "name": "Wait Then Reactivate",
        "type": "n8n-nodes-base.wait",
        "position": [1660, 500],
        "typeVersion": 1.1,
        "webhookId": uid(),
    })

    # ── 10. Reactivate Workflow (HTTP) ──
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $('Parse AI Response').first().json.workflowId ? $env.N8N_BASE_URL + '/api/v1/workflows/' + $('Parse AI Response').first().json.workflowId + '/activate' : '' }}",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Reactivate Workflow",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1900, 500],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # ── 11. Tag Reactivate Result (Code) ──
    nodes.append({
        "parameters": {
            "jsCode": SET_REACTIVATE_RESULT_CODE,
        },
        "id": uid(),
        "name": "Tag Reactivate Result",
        "type": "n8n-nodes-base.code",
        "position": [2140, 500],
        "typeVersion": 2,
    })

    # ── 12. Compute Wait Time (Code) — delay_retry branch ──
    nodes.append({
        "parameters": {
            "jsCode": COMPUTE_DELAY_CODE,
        },
        "id": uid(),
        "name": "Compute Wait Time",
        "type": "n8n-nodes-base.code",
        "position": [1420, 700],
        "typeVersion": 2,
    })

    # ── 13. Wait Before Retry ──
    nodes.append({
        "parameters": {
            "amount": "={{ $json.waitSeconds }}",
            "unit": "seconds",
        },
        "id": uid(),
        "name": "Wait Before Retry",
        "type": "n8n-nodes-base.wait",
        "position": [1660, 700],
        "typeVersion": 1.1,
        "webhookId": uid(),
    })

    # ── 14. Execute Delayed Retry (HTTP) ──
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $('Compute Wait Time').first().json.executionId ? $env.N8N_BASE_URL + '/api/v1/executions/' + $('Compute Wait Time').first().json.executionId + '/retry' : '' }}",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Execute Delayed Retry",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1900, 700],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # ── 15. Tag Delayed Result (Code) ──
    nodes.append({
        "parameters": {
            "jsCode": SET_DELAYED_RESULT_CODE,
        },
        "id": uid(),
        "name": "Tag Delayed Result",
        "type": "n8n-nodes-base.code",
        "position": [2140, 700],
        "typeVersion": 2,
    })

    # ── 16. Build Alert Email (Code) — needs_human + fallback branches ──
    nodes.append({
        "parameters": {
            "jsCode": BUILD_ALERT_EMAIL_CODE,
        },
        "id": uid(),
        "name": "Build Alert Email",
        "type": "n8n-nodes-base.code",
        "position": [1420, 900],
        "typeVersion": 2,
    })

    # ── 17. Send Alert Email (Gmail) ──
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "={{ $json.alertSubject }}",
            "emailType": "html",
            "message": "={{ $json.alertHtml }}",
            "options": {"appendAttribution": False},
        },
        "id": uid(),
        "name": "Send Alert Email",
        "type": "n8n-nodes-base.gmail",
        "position": [1660, 900],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # ── 18. Log to Airtable (optional — all fix paths converge here) ──
    if AIRTABLE_ENABLED:
        nodes.append({
            "parameters": {
                "operation": "create",
                "base": {"__rl": True, "mode": "list", "value": AIRTABLE_BASE_ID},
                "table": {"__rl": True, "mode": "list", "value": TABLE_ERROR_LOG},
                "columns": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "Error ID": "=SH-{{ Date.now() }}",
                        "Timestamp": "={{ $json.timestamp }}",
                        "Instance": INSTANCE_NAME,
                        "Workflow Name": "={{ $json.workflowName }}",
                        "Workflow ID": "={{ $json.workflowId }}",
                        "Error Node": "={{ $json.errorNode }}",
                        "Error Message": "={{ $json.errorMessage }}",
                        "Category": "={{ $json.category }}",
                        "AI Confidence": "={{ $json.confidence }}",
                        "AI Explanation": "={{ $json.explanation }}",
                        "Action Taken": "={{ $json.fixAction || 'none' }}",
                        "Action Result": "={{ $json.fixResult || 'pending' }}",
                        "Execution ID": "={{ $json.executionId }}",
                        "Execution URL": "={{ $json.executionUrl }}",
                        "Is Test": "={{ $json.isTest }}",
                    },
                    "schema": [],
                },
                "options": {},
            },
            "id": uid(),
            "name": "Log to Airtable",
            "type": "n8n-nodes-base.airtable",
            "position": [2380, 500],
            "typeVersion": 2.1,
            "credentials": {"airtableTokenApi": CRED_AIRTABLE},
            "onError": "continueRegularOutput",
        })

    # ══════════════════════════════════════════════════════════
    # FLOW B: HEALTH CHECK PATH (y=1200)
    # ══════════════════════════════════════════════════════════

    # ── 19. Health Check Schedule ──
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "minutes", "minutesInterval": CHECK_INTERVAL}]
            }
        },
        "id": uid(),
        "name": "Health Check Schedule",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 1200],
        "typeVersion": 1.2,
    })

    # ── 20. Fetch All Workflows (HTTP) ──
    nodes.append({
        "parameters": {
            "url": "={{ $env.N8N_BASE_URL }}/api/v1/workflows?limit=250",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Fetch All Workflows",
        "type": "n8n-nodes-base.httpRequest",
        "position": [460, 1200],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # ── 21. Fetch Recent Errors (HTTP) ──
    nodes.append({
        "parameters": {
            "url": "={{ $env.N8N_BASE_URL }}/api/v1/executions?status=error&limit=20",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Fetch Recent Errors",
        "type": "n8n-nodes-base.httpRequest",
        "position": [700, 1200],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
        "onError": "continueRegularOutput",
    })

    # ── 22. Analyze Health (Code) ──
    nodes.append({
        "parameters": {
            "jsCode": ANALYZE_HEALTH_CODE,
        },
        "id": uid(),
        "name": "Analyze Health",
        "type": "n8n-nodes-base.code",
        "position": [940, 1200],
        "typeVersion": 2,
    })

    # ── 23. Has Issues? (If) ──
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.hasIssues }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
                "combinator": "and",
            },
        },
        "id": uid(),
        "name": "Has Issues?",
        "type": "n8n-nodes-base.if",
        "position": [1180, 1200],
        "typeVersion": 2.2,
    })

    # ── 24. Build Health Report (Code) ──
    nodes.append({
        "parameters": {
            "jsCode": BUILD_HEALTH_REPORT_CODE,
        },
        "id": uid(),
        "name": "Build Health Report",
        "type": "n8n-nodes-base.code",
        "position": [1420, 1200],
        "typeVersion": 2,
    })

    # ── 25. Send Health Alert (Gmail) ──
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "={{ $json.reportSubject }}",
            "emailType": "html",
            "message": "={{ $json.reportHtml }}",
            "options": {"appendAttribution": False},
        },
        "id": uid(),
        "name": "Send Health Alert",
        "type": "n8n-nodes-base.gmail",
        "position": [1660, 1200],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # ══════════════════════════════════════════════════════════
    # FLOW C: MANUAL TEST (y=1500)
    # ══════════════════════════════════════════════════════════

    # ── 26. Manual Trigger ──
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 1500],
        "typeVersion": 1,
    })

    # ── 27. Test Config (Set — sample error data) ──
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "testMode", "value": "=true", "type": "boolean"},
                    {"id": uid(), "name": "errorMessage", "value": "ECONNRESET: connection reset by peer", "type": "string"},
                    {"id": uid(), "name": "errorNode", "value": "HTTP Request", "type": "string"},
                    {"id": uid(), "name": "workflowName", "value": "Test Workflow (Self-Healing Check)", "type": "string"},
                    {"id": uid(), "name": "workflowId", "value": "test-123", "type": "string"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Test Config",
        "type": "n8n-nodes-base.set",
        "position": [460, 1500],
        "typeVersion": 3.4,
    })

    # ══════════════════════════════════════════════════════════
    # FLOW D: EXTERNAL WEBHOOK (y=1700)
    # ══════════════════════════════════════════════════════════

    # ── 28. Report Webhook ──
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "self-healing/report",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Report Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 1700],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # ── 28b. Webhook Auth Check ──
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
        "name": "Webhook Auth Check",
        "type": "n8n-nodes-base.code",
        "position": [330, 1700],
        "typeVersion": 2,
    })

    # ── 29. Validate Webhook Input (Code) ──
    nodes.append({
        "parameters": {
            "jsCode": VALIDATE_WEBHOOK_CODE,
        },
        "id": uid(),
        "name": "Validate Webhook Input",
        "type": "n8n-nodes-base.code",
        "position": [460, 1700],
        "typeVersion": 2,
    })

    # ── 30. Respond to Webhook ──
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": '={"status":"received","valid":{{ $json.valid }},"timestamp":"{{ $now.toISO() }}"}',
            "options": {},
        },
        "id": uid(),
        "name": "Respond to Webhook",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [700, 1700],
        "typeVersion": 1.1,
        "onError": "continueRegularOutput",
    })

    return nodes


def build_connections():
    """Build connections for the Self-Healing workflow."""
    connections = {
        # ── Flow A: Error Trigger Path ──
        "Error Trigger": {
            "main": [[{"node": "Extract Error Data", "type": "main", "index": 0}]],
        },
        "Extract Error Data": {
            "main": [[{"node": "AI Classify Error", "type": "main", "index": 0}]],
        },
        "AI Classify Error": {
            "main": [[{"node": "Parse AI Response", "type": "main", "index": 0}]],
        },
        "Parse AI Response": {
            "main": [[{"node": "Route by Category", "type": "main", "index": 0}]],
        },
        "Route by Category": {
            "main": [
                # Output 0: auto_retry
                [{"node": "Execute Retry", "type": "main", "index": 0}],
                # Output 1: deactivate_reactivate
                [{"node": "Deactivate Workflow", "type": "main", "index": 0}],
                # Output 2: delay_retry
                [{"node": "Compute Wait Time", "type": "main", "index": 0}],
                # Output 3: needs_human
                [{"node": "Build Alert Email", "type": "main", "index": 0}],
                # Output 4: fallback (unknown)
                [{"node": "Build Alert Email", "type": "main", "index": 0}],
            ],
        },

        # Auto-retry branch
        "Execute Retry": {
            "main": [[{"node": "Tag Retry Result", "type": "main", "index": 0}]],
        },

        # Deactivate/reactivate branch
        "Deactivate Workflow": {
            "main": [[{"node": "Wait Then Reactivate", "type": "main", "index": 0}]],
        },
        "Wait Then Reactivate": {
            "main": [[{"node": "Reactivate Workflow", "type": "main", "index": 0}]],
        },
        "Reactivate Workflow": {
            "main": [[{"node": "Tag Reactivate Result", "type": "main", "index": 0}]],
        },

        # Delay retry branch
        "Compute Wait Time": {
            "main": [[{"node": "Wait Before Retry", "type": "main", "index": 0}]],
        },
        "Wait Before Retry": {
            "main": [[{"node": "Execute Delayed Retry", "type": "main", "index": 0}]],
        },
        "Execute Delayed Retry": {
            "main": [[{"node": "Tag Delayed Result", "type": "main", "index": 0}]],
        },

        # Human alert branch
        "Build Alert Email": {
            "main": [[{"node": "Send Alert Email", "type": "main", "index": 0}]],
        },

        # ── Flow B: Health Check ──
        "Health Check Schedule": {
            "main": [[{"node": "Fetch All Workflows", "type": "main", "index": 0}]],
        },
        "Fetch All Workflows": {
            "main": [[{"node": "Fetch Recent Errors", "type": "main", "index": 0}]],
        },
        "Fetch Recent Errors": {
            "main": [[{"node": "Analyze Health", "type": "main", "index": 0}]],
        },
        "Analyze Health": {
            "main": [[{"node": "Has Issues?", "type": "main", "index": 0}]],
        },
        "Has Issues?": {
            "main": [
                [{"node": "Build Health Report", "type": "main", "index": 0}],
                [],  # false — no issues, stop
            ],
        },
        "Build Health Report": {
            "main": [[{"node": "Send Health Alert", "type": "main", "index": 0}]],
        },

        # ── Flow C: Manual Test ──
        "Manual Trigger": {
            "main": [[{"node": "Test Config", "type": "main", "index": 0}]],
        },
        "Test Config": {
            "main": [[{"node": "Extract Error Data", "type": "main", "index": 0}]],
        },

        # ── Flow D: External Webhook ──
        "Report Webhook": {
            "main": [[{"node": "Webhook Auth Check", "type": "main", "index": 0}]],
        },
        "Webhook Auth Check": {
            "main": [[{"node": "Validate Webhook Input", "type": "main", "index": 0}]],
        },
        "Validate Webhook Input": {
            "main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]],
        },
        "Respond to Webhook": {
            "main": [[{"node": "Extract Error Data", "type": "main", "index": 0}]],
        },
    }

    # Connect fix result branches to Airtable log if enabled
    if AIRTABLE_ENABLED:
        connections["Tag Retry Result"] = {
            "main": [[{"node": "Log to Airtable", "type": "main", "index": 0}]],
        }
        connections["Tag Reactivate Result"] = {
            "main": [[{"node": "Log to Airtable", "type": "main", "index": 0}]],
        }
        connections["Tag Delayed Result"] = {
            "main": [[{"node": "Log to Airtable", "type": "main", "index": 0}]],
        }
        connections["Send Alert Email"] = {
            "main": [[{"node": "Log to Airtable", "type": "main", "index": 0}]],
        }

    return connections


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY
# ══════════════════════════════════════════════════════════════

WORKFLOW_DEFS = {
    "self_healing": {
        "name": f"Self-Healing Monitor - {INSTANCE_NAME}",
        "build_nodes": lambda: build_nodes(),
        "build_connections": lambda: build_connections(),
    },
}


def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
    if wf_id not in WORKFLOW_DEFS:
        raise ValueError(f"Unknown workflow: {wf_id}")

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
            "errorWorkflow": "",  # Blank — prevents infinite recursion
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    output_dir = Path(__file__).parent.parent / "workflows" / "self-healing"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "wf_self_healing.json"

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
    parser = argparse.ArgumentParser(description="Self-Healing Workflow Builder & Deployer")
    parser.add_argument("action", nargs="?", default="build",
                        choices=["build", "deploy", "activate"])
    parser.add_argument("--email", default=None, help="Alert email override")
    parser.add_argument("--instance", default=None, help="Instance name override")
    parser.add_argument("--no-airtable", action="store_true", help="Disable Airtable logging")
    parser.add_argument("--set-error-workflow", action="store_true",
                        help="Set this as error workflow for ALL other workflows")
    args = parser.parse_args()

    # Apply overrides
    global ALERT_EMAIL, INSTANCE_NAME, AIRTABLE_ENABLED
    if args.email:
        ALERT_EMAIL = args.email
    if args.instance:
        INSTANCE_NAME = args.instance
    if args.no_airtable:
        AIRTABLE_ENABLED = False

    # Re-evaluate workflow name with possible override
    WORKFLOW_DEFS["self_healing"]["name"] = f"Self-Healing Monitor - {INSTANCE_NAME}"

    # Add tools dir to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("SELF-HEALING WORKFLOW BUILDER")
    print("=" * 60)
    print(f"  Instance: {INSTANCE_NAME}")
    print(f"  Alert Email: {ALERT_EMAIL}")
    print(f"  Airtable Logging: {'ON' if AIRTABLE_ENABLED else 'OFF'}")
    print(f"  Health Check: every {CHECK_INTERVAL} min")

    # Check n8n API credential
    if "REPLACE" in CRED_N8N_API["id"]:
        print()
        print("WARNING: n8n API credential not configured!")
        print("  1. Create HTTP Header Auth credential in n8n UI:")
        print("     Header Name: X-N8N-API-KEY")
        print("     Header Value: <your n8n API key>")
        print("  2. Set SELFHEALING_N8N_API_CRED_ID in .env")
        print()
        if args.action in ("deploy", "activate"):
            print("  Continuing anyway — you'll need to bind the credential in n8n UI.")
        print()

    # Build
    wf_id = "self_healing"
    print(f"\nBuilding {wf_id}...")
    workflow = build_workflow(wf_id)
    output_path = save_workflow(wf_id, workflow)
    print_workflow_stats(wf_id, workflow)
    print(f"  Saved to: {output_path}")

    if args.action == "build":
        print("\nBuild complete. Run with 'deploy' to push to n8n.")
        return

    # Deploy to n8n
    if args.action in ("deploy", "activate"):
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

            # Check if workflow already exists (no cache — avoid duplicates)
            existing = None
            try:
                all_wfs = client.list_workflows(use_cache=False)
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
                deployed_id = result.get("id")
                print(f"  Updated: {result.get('name')} (ID: {deployed_id})")
            else:
                create_payload = {
                    "name": workflow["name"],
                    "nodes": workflow["nodes"],
                    "connections": workflow["connections"],
                    "settings": workflow["settings"],
                }
                result = client.create_workflow(create_payload)
                deployed_id = result.get("id")
                print(f"  Created: {result.get('name')} (ID: {deployed_id})")

            if args.action == "activate" and deployed_id:
                print(f"  Activating...")
                try:
                    client.activate_workflow(deployed_id)
                    print(f"  Activated!")
                except Exception as e:
                    print(f"  Activation failed: {e}")
                    print(f"  This may be because the n8n API Header Auth credential isn't bound yet.")
                    print(f"  Bind the credential in n8n UI, then activate manually.")

            # Set as error workflow for all other workflows
            if args.set_error_workflow and deployed_id:
                print(f"\n  Setting as error workflow for all other workflows...")
                all_wfs = client.list_workflows(use_cache=False)
                updated_count = 0
                for wf in all_wfs:
                    if wf["id"] != deployed_id:
                        try:
                            # Must fetch full workflow — API requires complete body on PUT
                            full_wf = client.get_workflow(wf["id"])
                            full_settings = full_wf.get("settings", {})
                            full_settings["errorWorkflow"] = deployed_id
                            client.update_workflow(wf["id"], {
                                "name": full_wf["name"],
                                "nodes": full_wf["nodes"],
                                "connections": full_wf["connections"],
                                "settings": full_settings,
                            })
                            updated_count += 1
                        except Exception as e:
                            print(f"    Warning: Could not update '{wf.get('name', wf['id'])}': {e}")
                print(f"  Updated {updated_count} workflows to use self-healing error handler.")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Open workflow in n8n UI, verify all node connections")
    print("  2. Create HTTP Header Auth credential in n8n UI:")
    print("     Header Name: X-N8N-API-KEY")
    print("     Header Value: <your n8n API key>")
    print("     Then bind it to all 'httpHeaderAuth' nodes")
    print("  3. Test with Manual Trigger")
    print("  4. If not already done, run with --set-error-workflow to configure all workflows")
    print("  5. Monitor incoming alerts and health reports")


if __name__ == "__main__":
    main()
