"""
AVM Autonomous Operations - Central Orchestrator Workflow Builder & Deployer

Builds 4 orchestrator workflows that form the central brain of the
autonomous operations system. Coordinates all department agents.

Workflows:
    ORCH-01: Health Monitor (every 15 min) - Poll n8n API, compute health, auto-fix/escalate
    ORCH-02: Cross-Dept Router (webhook) - Central event bus for inter-agent coordination
    ORCH-03: Daily KPI Aggregation (daily 06:00 SAST) - Aggregate metrics, detect anomalies
    ORCH-04: Weekly Report Generator (Mon 07:00 SAST) - Executive summary via Claude + email

Usage:
    python tools/deploy_orchestrator.py build              # Build all JSONs
    python tools/deploy_orchestrator.py build orch01       # Build ORCH-01 only
    python tools/deploy_orchestrator.py deploy             # Build + Deploy (inactive)
    python tools/deploy_orchestrator.py activate           # Build + Deploy + Activate
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
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}
CRED_N8N_API = {
    "id": os.getenv("SELFHEALING_N8N_API_CRED_ID", "xymp9Nho08mRW2Wz"),
    "name": "n8n API Key",
}

# -- Airtable IDs --
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "REPLACE_AFTER_SETUP")
TABLE_AGENT_REGISTRY = os.getenv("ORCH_TABLE_AGENT_REGISTRY", "REPLACE_AFTER_SETUP")
TABLE_EVENTS = os.getenv("ORCH_TABLE_EVENTS", "REPLACE_AFTER_SETUP")
TABLE_KPI_SNAPSHOTS = os.getenv("ORCH_TABLE_KPI_SNAPSHOTS", "REPLACE_AFTER_SETUP")
TABLE_ESCALATION_QUEUE = os.getenv("ORCH_TABLE_ESCALATION_QUEUE", "REPLACE_AFTER_SETUP")
TABLE_DECISION_LOG = os.getenv("ORCH_TABLE_DECISION_LOG", "REPLACE_AFTER_SETUP")

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

# -- All monitored workflow IDs grouped by agent --
AGENT_WORKFLOW_MAP = {
    "agent_marketing": [
        "twSg4SfNdlmdITHj", "CWQ9zjCTaf56RBe6", "ygwBtSysINRWHJxB", "ZEcxIC9M5ehQvsbg",
        "5XZFaoQxfyJOlqje", "ipsnBC5Xox4DWgBg", "u7LSuq6zmAY8P7fU", "M67NBeAEHfDIJ9wz",
        "BpZ4LkxKjHoGfjUq", "Xlu3tGHgM5DDXnkl", "Y80dDSmWQfUlfvib", "0US5H9smGsrCUsv7",
        "IqODyj5suLusrkIx", "tOT9DtpE8DspXSjm", "0ynfcpEwHrPaghTl", "OlHyOU8mHxJ1uZuc",
    ],
    "agent_finance": [
        "twSg4SfNdlmdITHj", "CWQ9zjCTaf56RBe6", "ygwBtSysINRWHJxB", "ZEcxIC9M5ehQvsbg",
        "f0Wh4SOxbODbs4TE", "gwMuSElYqDTRGFKa", "EmpOzaaDGqsLvg5j",
    ],
    "agent_content": ["ygwBtSysINRWHJxB", "ipsnBC5Xox4DWgBg", "u7LSuq6zmAY8P7fU"],
    "agent_client_relations": [],
    "agent_support": [],
    "agent_whatsapp": [],
}


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════
# CODE NODE SCRIPTS
# ══════════════════════════════════════════════════════════════

ORCH01_BUILD_AGENT_LIST_CODE = r"""
// Build flat list of all workflow IDs grouped by agent for health checking
const agentWorkflows = ##AGENT_WORKFLOW_MAP##;

const checkItems = [];
for (const [agentId, workflowIds] of Object.entries(agentWorkflows)) {
  for (const wfId of workflowIds) {
    checkItems.push({
      json: { agentId, workflowId: wfId }
    });
  }
}

// Deduplicate workflow IDs (some shared across agents)
const seen = new Set();
const unique = checkItems.filter(item => {
  const key = item.json.workflowId;
  if (seen.has(key)) return false;
  seen.add(key);
  return true;
});

return unique;
""".strip()

ORCH01_COMPUTE_HEALTH_CODE = r"""
// Aggregate execution results into per-agent health scores
const executionResults = $input.all();
const agentWorkflows = ##AGENT_WORKFLOW_MAP##;

// Build execution status map: workflowId -> {success, error, total}
const statusMap = {};
for (const item of executionResults) {
  const d = item.json;
  const wfId = d.workflowId;
  if (!statusMap[wfId]) {
    statusMap[wfId] = { success: 0, error: 0, total: 0, workflowId: wfId };
  }
  const executions = d.executions || [];
  for (const exec of executions) {
    statusMap[wfId].total++;
    if (exec.status === 'success') statusMap[wfId].success++;
    else if (exec.status === 'error') statusMap[wfId].error++;
  }
}

// Compute per-agent health
const agentScores = [];
for (const [agentId, workflowIds] of Object.entries(agentWorkflows)) {
  if (workflowIds.length === 0) {
    agentScores.push({
      json: {
        agentId,
        healthScore: 100,
        status: 'Active',
        workflowsChecked: 0,
        totalExecutions: 0,
        totalErrors: 0,
        errorWorkflows: [],
      }
    });
    continue;
  }

  let totalExecs = 0;
  let totalSuccess = 0;
  let totalErrors = 0;
  const errorWorkflows = [];

  for (const wfId of workflowIds) {
    const s = statusMap[wfId] || { success: 0, error: 0, total: 0 };
    totalExecs += s.total;
    totalSuccess += s.success;
    totalErrors += s.error;
    if (s.error > 0) {
      errorWorkflows.push({ workflowId: wfId, errors: s.error, total: s.total });
    }
  }

  const successRate = totalExecs > 0 ? (totalSuccess / totalExecs * 100) : 50;
  let healthScore = Math.round(successRate);
  if (totalErrors > 5) healthScore = Math.max(0, healthScore - 20);

  let status = 'Active';
  if (healthScore < 60) status = 'Degraded';
  if (healthScore < 30) status = 'Down';

  agentScores.push({
    json: {
      agentId,
      healthScore,
      status,
      workflowsChecked: workflowIds.length,
      totalExecutions: totalExecs,
      totalErrors,
      successRate: Math.round(successRate * 10) / 10,
      errorWorkflows,
    }
  });
}

return agentScores;
""".strip()

ORCH01_DECIDE_ACTION_CODE = r"""
// For each agent, decide: OK / auto-fix / escalate
const agents = $input.all();
const results = [];

for (const agent of agents) {
  const d = agent.json;
  const action = { ...d };

  if (d.status === 'Active') {
    action.action = 'none';
    action.actionLabel = 'Healthy - no action needed';
  } else if (d.status === 'Degraded' && d.totalErrors <= 3) {
    action.action = 'auto_retry';
    action.actionLabel = 'Auto-retry failed workflows';
    action.retryWorkflows = d.errorWorkflows.map(w => w.workflowId);
  } else if (d.status === 'Degraded' && d.totalErrors > 3) {
    action.action = 'escalate';
    action.actionLabel = 'Multiple failures - escalating to human';
    action.severity = 'P3';
  } else if (d.status === 'Down') {
    action.action = 'escalate';
    action.actionLabel = 'Agent DOWN - immediate escalation';
    action.severity = 'P1';
  } else {
    action.action = 'none';
    action.actionLabel = 'No action required';
  }

  results.push({ json: action });
}

return results;
""".strip()

ORCH02_ROUTE_EVENT_CODE = r"""
// Parse incoming webhook event and determine routing
const input = $input.first().json;

const eventType = input.event_type || input.eventType || 'unknown';
const sourceAgent = input.source_agent || input.sourceAgent || 'unknown';
const payload = input.payload || input;
const priority = input.priority || 'Medium';

// Route based on event type
let targetAgent = 'agent_orchestrator';
let action = 'log';

switch (eventType) {
  case 'lead_qualified':
    targetAgent = 'agent_client_relations';
    action = 'create_interaction';
    break;
  case 'invoice_created':
    targetAgent = 'agent_finance';
    action = 'track_revenue';
    break;
  case 'content_published':
    targetAgent = 'agent_marketing';
    action = 'track_content';
    break;
  case 'support_ticket':
    targetAgent = 'agent_support';
    action = 'create_ticket';
    break;
  case 'whatsapp_urgent':
    targetAgent = 'agent_whatsapp';
    action = 'escalate';
    break;
  case 'client_churn_risk':
    targetAgent = 'agent_client_relations';
    action = 'churn_intervention';
    break;
  default:
    action = 'log_only';
}

return {
  json: {
    eventType,
    sourceAgent,
    targetAgent,
    action,
    priority,
    payload: JSON.stringify(payload),
    timestamp: new Date().toISOString(),
    eventId: `evt_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
  }
};
""".strip()

ORCH03_COMPUTE_KPIS_CODE = r"""
// Merge all data sources into per-agent KPI snapshots
const today = $now.toFormat('yyyy-MM-dd');

// Try to read from previous nodes (graceful if missing)
let marketingMetrics = {};
let financeMetrics = {};
let executionStats = {};

try { marketingMetrics = $('Read Marketing Metrics').first().json || {}; } catch(e) {}
try { financeMetrics = $('Read Finance Metrics').first().json || {}; } catch(e) {}
try { executionStats = $('Read Execution Stats').first().json || {}; } catch(e) {}

const snapshots = [
  {
    json: {
      'Snapshot ID': `agent_marketing_${today}`,
      'Snapshot Date': today,
      'Agent ID': 'agent_marketing',
      'Content Published': marketingMetrics.contentPublished || 0,
      'Emails Sent': marketingMetrics.emailsSent || 0,
      'Leads Generated': marketingMetrics.leadsGenerated || 0,
      'Success Rate': executionStats.marketingSuccessRate || 0,
    }
  },
  {
    json: {
      'Snapshot ID': `agent_finance_${today}`,
      'Snapshot Date': today,
      'Agent ID': 'agent_finance',
      'Revenue ZAR': financeMetrics.revenueZAR || 0,
      'Success Rate': executionStats.financeSuccessRate || 0,
    }
  },
  {
    json: {
      'Snapshot ID': `agent_content_${today}`,
      'Snapshot Date': today,
      'Agent ID': 'agent_content',
      'Content Published': marketingMetrics.contentPublished || 0,
      'Success Rate': executionStats.contentSuccessRate || 0,
    }
  },
  {
    json: {
      'Snapshot ID': `agent_support_${today}`,
      'Snapshot Date': today,
      'Agent ID': 'agent_support',
      'Tickets Resolved': 0,
      'Success Rate': 0,
    }
  },
  {
    json: {
      'Snapshot ID': `agent_client_relations_${today}`,
      'Snapshot Date': today,
      'Agent ID': 'agent_client_relations',
      'Success Rate': 0,
    }
  },
  {
    json: {
      'Snapshot ID': `agent_whatsapp_${today}`,
      'Snapshot Date': today,
      'Agent ID': 'agent_whatsapp',
      'Messages Handled': 0,
      'Success Rate': 0,
    }
  },
];

return snapshots;
""".strip()

ORCH04_FORMAT_REPORT_CODE = r"""
// Format weekly report data into HTML email body
const kpiData = $('Read KPI History').all();
const escalations = $('Read Escalations').all();
const decisions = $('Read Decisions').all();
const aiSummary = $('AI Generate Summary').first().json;

const reportDate = $now.toFormat('yyyy-MM-dd');
const weekStart = $now.minus({days: 7}).toFormat('yyyy-MM-dd');

// Build agent summary table rows
let agentRows = '';
const agentMap = {};
for (const item of kpiData) {
  const d = item.json;
  const agentId = d['Agent ID'] || '';
  if (!agentMap[agentId]) {
    agentMap[agentId] = { total: 0, leads: 0, content: 0, revenue: 0, successRates: [] };
  }
  agentMap[agentId].leads += d['Leads Generated'] || 0;
  agentMap[agentId].content += d['Content Published'] || 0;
  agentMap[agentId].revenue += d['Revenue ZAR'] || 0;
  if (d['Success Rate']) agentMap[agentId].successRates.push(d['Success Rate']);
  agentMap[agentId].total++;
}

for (const [agentId, data] of Object.entries(agentMap)) {
  const avgSuccess = data.successRates.length > 0
    ? Math.round(data.successRates.reduce((a, b) => a + b, 0) / data.successRates.length)
    : 0;
  const name = agentId.replace('agent_', '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  agentRows += `<tr>
    <td style="padding:8px;border-bottom:1px solid #eee;">${name}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">${avgSuccess}%</td>
    <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">${data.leads}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">${data.content}</td>
    <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">R${data.revenue.toLocaleString()}</td>
  </tr>`;
}

const summaryText = (aiSummary.choices && aiSummary.choices[0])
  ? aiSummary.choices[0].message.content
  : 'AI summary unavailable.';

const openEscalations = escalations.filter(e => e.json.Status === 'Open').length;
const totalDecisions = decisions.length;

const html = `
<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
  <div style="background: #FF6D5A; padding: 20px; text-align: center;">
    <h1 style="color: white; margin: 0;">AVM Weekly Operations Report</h1>
    <p style="color: white; margin: 5px 0;">${weekStart} to ${reportDate}</p>
  </div>

  <div style="padding: 20px;">
    <h2 style="color: #333;">Executive Summary</h2>
    <div style="background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
      ${summaryText.replace(/\\n/g, '<br>')}
    </div>

    <h2 style="color: #333;">Agent Performance</h2>
    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
      <thead>
        <tr style="background: #f0f0f0;">
          <th style="padding: 10px; text-align: left;">Agent</th>
          <th style="padding: 10px; text-align: center;">Success Rate</th>
          <th style="padding: 10px; text-align: center;">Leads</th>
          <th style="padding: 10px; text-align: center;">Content</th>
          <th style="padding: 10px; text-align: right;">Revenue</th>
        </tr>
      </thead>
      <tbody>${agentRows}</tbody>
    </table>

    <div style="display: flex; gap: 20px; margin-bottom: 20px;">
      <div style="flex: 1; background: ${openEscalations > 0 ? '#fff3f0' : '#f0fff0'}; padding: 15px; border-radius: 8px; text-align: center;">
        <div style="font-size: 24px; font-weight: bold; color: ${openEscalations > 0 ? '#FF6D5A' : '#22c55e'};">${openEscalations}</div>
        <div>Open Escalations</div>
      </div>
      <div style="flex: 1; background: #f0f0ff; padding: 15px; border-radius: 8px; text-align: center;">
        <div style="font-size: 24px; font-weight: bold; color: #6366f1;">${totalDecisions}</div>
        <div>AI Decisions Made</div>
      </div>
    </div>
  </div>

  <div style="background: #f0f0f0; padding: 15px; text-align: center; font-size: 12px; color: #666;">
    Generated by AVM Central Orchestrator | ${new Date().toISOString()}
  </div>
</div>
`;

return { json: { html, subject: `AVM Weekly Report: ${weekStart} to ${reportDate}`, summaryText } };
""".strip()


# ══════════════════════════════════════════════════════════════
# ORCH-01: Health Monitor
# ══════════════════════════════════════════════════════════════

def build_orch01_nodes():
    """Build nodes for ORCH-01: Health Monitor (every 15 min)."""
    nodes = []

    # 1. Schedule Trigger (every 15 min)
    nodes.append({
        "parameters": {
            "rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Build Agent List (Code)
    agent_map_json = json.dumps(AGENT_WORKFLOW_MAP)
    nodes.append({
        "parameters": {
            "jsCode": ORCH01_BUILD_AGENT_LIST_CODE.replace("##AGENT_WORKFLOW_MAP##", agent_map_json),
        },
        "id": uid(),
        "name": "Build Agent List",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [440, 300],
    })

    # 3. Loop Over Workflows (SplitInBatches)
    nodes.append({
        "parameters": {"batchSize": 5, "options": {}},
        "id": uid(),
        "name": "Batch Workflows",
        "type": "n8n-nodes-base.splitInBatches",
        "typeVersion": 3,
        "position": [660, 300],
    })

    # 4. Fetch Executions (HTTP Request to n8n API)
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": f"={N8N_BASE_URL}/api/v1/executions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "workflowId", "value": "={{ $json.workflowId }}"},
                    {"name": "limit", "value": "20"},
                    {"name": "status", "value": "error,success"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Executions",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [880, 300],
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
    })

    # 5. Map Results (Set node)
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "workflowId", "value": "={{ $('Batch Workflows').item.json.workflowId }}", "type": "string"},
                    {"id": uid(), "name": "agentId", "value": "={{ $('Batch Workflows').item.json.agentId }}", "type": "string"},
                    {"id": uid(), "name": "executions", "value": "={{ $json.data }}", "type": "string"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Map Results",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [1100, 300],
    })

    # 6. Compute Health Scores (Code)
    nodes.append({
        "parameters": {
            "jsCode": ORCH01_COMPUTE_HEALTH_CODE.replace("##AGENT_WORKFLOW_MAP##", agent_map_json),
        },
        "id": uid(),
        "name": "Compute Health Scores",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 300],
    })

    # 7. Decide Action (Code)
    nodes.append({
        "parameters": {
            "jsCode": ORCH01_DECIDE_ACTION_CODE,
        },
        "id": uid(),
        "name": "Decide Action",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1540, 300],
    })

    # 8. Switch on Action
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "conditions": [{"leftValue": "={{ $json.action }}", "rightValue": "none", "operator": {"type": "string", "operation": "equals"}}]
                        },
                        "renameOutput": True,
                        "outputKey": "Healthy",
                    },
                    {
                        "conditions": {
                            "conditions": [{"leftValue": "={{ $json.action }}", "rightValue": "auto_retry", "operator": {"type": "string", "operation": "equals"}}]
                        },
                        "renameOutput": True,
                        "outputKey": "Auto Fix",
                    },
                    {
                        "conditions": {
                            "conditions": [{"leftValue": "={{ $json.action }}", "rightValue": "escalate", "operator": {"type": "string", "operation": "equals"}}]
                        },
                        "renameOutput": True,
                        "outputKey": "Escalate",
                    },
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Route Action",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [1760, 300],
    })

    # 9. Update Agent Registry (Healthy path - just update heartbeat)
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_AGENT_REGISTRY, "mode": "id"},
            "columns": {
                "value": {
                    "Status": "={{ $json.status }}",
                    "Health Score": "={{ $json.healthScore }}",
                }
            },
            "options": {},
            "matchingColumns": ["Agent ID"],
        },
        "id": uid(),
        "name": "Update Registry Healthy",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [2000, 100],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 10. Log Decision (Auto Fix path)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_DECISION_LOG, "mode": "id"},
            "columns": {
                "value": {
                    "Decision ID": "=dec_{{ $now.toFormat('yyyyMMddHHmmss') }}_{{ $json.agentId }}",
                    "Agent ID": "={{ $json.agentId }}",
                    "Decision Type": "auto_retry",
                    "Context": "={{ JSON.stringify($json.errorWorkflows) }}",
                    "Decision": "={{ $json.actionLabel }}",
                    "Outcome": "Pending",
                    "Confidence": 0.8,
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Auto Fix Decision",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [2000, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 11. Create Escalation (Escalate path)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ESCALATION_QUEUE, "mode": "id"},
            "columns": {
                "value": {
                    "Title": "=Agent {{ $json.agentId }} - {{ $json.status }}: {{ $json.totalErrors }} errors",
                    "Agent ID": "={{ $json.agentId }}",
                    "Severity": "={{ $json.severity || 'P3' }}",
                    "Category": "Workflow Failure",
                    "Description": "=Agent {{ $json.agentId }} has {{ $json.totalErrors }} errors across {{ $json.workflowsChecked }} workflows. Health score: {{ $json.healthScore }}. Error workflows: {{ JSON.stringify($json.errorWorkflows) }}",
                    "Recommended Action": "={{ $json.actionLabel }}",
                    "Status": "Open",
                    "Owner": ALERT_EMAIL,
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Escalation",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [2000, 520],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 12. Send Alert Email (Escalate path)
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=AVM ALERT: Agent {{ $('Create Escalation').item.json.fields['Agent ID'] }} - {{ $('Decide Action').item.json.severity }}",
            "emailType": "html",
            "message": """=<div style="font-family: Arial; max-width: 600px; margin: 0 auto;">
<div style="background: #FF6D5A; padding: 15px; text-align: center;">
<h2 style="color: white; margin: 0;">AVM Agent Alert</h2>
</div>
<div style="padding: 20px;">
<p><strong>Agent:</strong> {{ $('Decide Action').item.json.agentId }}</p>
<p><strong>Status:</strong> {{ $('Decide Action').item.json.status }}</p>
<p><strong>Health Score:</strong> {{ $('Decide Action').item.json.healthScore }}%</p>
<p><strong>Errors:</strong> {{ $('Decide Action').item.json.totalErrors }}</p>
<p><strong>Severity:</strong> {{ $('Decide Action').item.json.severity }}</p>
<p><strong>Action:</strong> {{ $('Decide Action').item.json.actionLabel }}</p>
<hr>
<p style="font-size: 12px; color: #666;">Generated by AVM Central Orchestrator</p>
</div></div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Send Alert Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [2240, 520],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_orch01_connections(nodes):
    """Build connections for ORCH-01."""
    node_map = {n["name"]: n for n in nodes}
    return {
        "Schedule Trigger": {"main": [[{"node": "Build Agent List", "type": "main", "index": 0}]]},
        "Build Agent List": {"main": [[{"node": "Batch Workflows", "type": "main", "index": 0}]]},
        "Batch Workflows": {"main": [
            [{"node": "Fetch Executions", "type": "main", "index": 0}],
            [{"node": "Compute Health Scores", "type": "main", "index": 0}],
        ]},
        "Fetch Executions": {"main": [[{"node": "Map Results", "type": "main", "index": 0}]]},
        "Map Results": {"main": [[{"node": "Batch Workflows", "type": "main", "index": 0}]]},
        "Compute Health Scores": {"main": [[{"node": "Decide Action", "type": "main", "index": 0}]]},
        "Decide Action": {"main": [[{"node": "Route Action", "type": "main", "index": 0}]]},
        "Route Action": {"main": [
            [{"node": "Update Registry Healthy", "type": "main", "index": 0}],
            [{"node": "Log Auto Fix Decision", "type": "main", "index": 0}],
            [{"node": "Create Escalation", "type": "main", "index": 0}],
        ]},
        "Create Escalation": {"main": [[{"node": "Send Alert Email", "type": "main", "index": 0}]]},
    }


# ══════════════════════════════════════════════════════════════
# ORCH-02: Cross-Department Router
# ══════════════════════════════════════════════════════════════

def build_orch02_nodes():
    """Build nodes for ORCH-02: Cross-Dept Router (webhook)."""
    nodes = []

    # 1. Webhook Trigger
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "orchestrator-event",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [220, 300],
        "webhookId": uid(),
    })

    # 2. Route Event (Code)
    nodes.append({
        "parameters": {"jsCode": ORCH02_ROUTE_EVENT_CODE},
        "id": uid(),
        "name": "Route Event",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [440, 300],
    })

    # 3. Log Event to Airtable
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_EVENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Event ID": "={{ $json.eventId }}",
                    "Event Type": "={{ $json.eventType }}",
                    "Source Agent": "={{ $json.sourceAgent }}",
                    "Target Agent": "={{ $json.targetAgent }}",
                    "Priority": "={{ $json.priority }}",
                    "Status": "Pending",
                    "Payload": "={{ $json.payload }}",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Event",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [660, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 4. Respond to Webhook
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": '={"status": "received", "event_id": "{{ $json.fields[\'Event ID\'] || $json.eventId }}", "routed_to": "{{ $(\'Route Event\').first().json.targetAgent }}"}',
            "options": {},
        },
        "id": uid(),
        "name": "Respond OK",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [880, 300],
    })

    return nodes


def build_orch02_connections(nodes):
    """Build connections for ORCH-02."""
    return {
        "Webhook Trigger": {"main": [[{"node": "Route Event", "type": "main", "index": 0}]]},
        "Route Event": {"main": [[{"node": "Log Event", "type": "main", "index": 0}]]},
        "Log Event": {"main": [[{"node": "Respond OK", "type": "main", "index": 0}]]},
    }


# ══════════════════════════════════════════════════════════════
# ORCH-03: Daily KPI Aggregation
# ══════════════════════════════════════════════════════════════

def build_orch03_nodes():
    """Build nodes for ORCH-03: Daily KPI Aggregation (06:00 SAST)."""
    nodes = []

    # 1. Schedule Trigger (daily 06:00 SAST = 04:00 UTC)
    nodes.append({
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 4 * * *"}]}
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Set Date Range
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "today", "value": "={{ $now.toFormat('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "yesterday", "value": "={{ $now.minus({days: 1}).toFormat('yyyy-MM-dd') }}", "type": "string"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Dates",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [440, 300],
    })

    # 3. Read Marketing Metrics (Airtable - content calendar)
    mkt_content_table = os.getenv("MARKETING_TABLE_CONTENT", "tblf3QGxX9K1y2h2H")
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": "apptjjBx34z9340tK", "mode": "id"},
            "table": {"__rl": True, "value": mkt_content_table, "mode": "id"},
            "filterByFormula": "=IS_SAME({Published Date}, '{{ $json.yesterday }}', 'day')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Marketing Metrics",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [660, 140],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 4. Read Finance Metrics (placeholder - would connect to QuickBooks)
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "revenueZAR", "value": "0", "type": "number"},
                    {"id": uid(), "name": "invoicesCreated", "value": "0", "type": "number"},
                    {"id": uid(), "name": "paymentsReceived", "value": "0", "type": "number"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Read Finance Metrics",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [660, 340],
    })

    # 5. Read Execution Stats (HTTP to n8n API)
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": f"{N8N_BASE_URL}/api/v1/executions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "limit", "value": "100"},
                    {"name": "status", "value": "error,success"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Read Execution Stats",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [660, 540],
        "credentials": {"httpHeaderAuth": CRED_N8N_API},
    })

    # 6. Compute KPIs (Code)
    nodes.append({
        "parameters": {"jsCode": ORCH03_COMPUTE_KPIS_CODE},
        "id": uid(),
        "name": "Compute KPIs",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [940, 300],
    })

    # 7. Write KPI Snapshots to Airtable
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_KPI_SNAPSHOTS, "mode": "id"},
            "columns": {
                "value": {
                    "Snapshot ID": "={{ $json['Snapshot ID'] }}",
                    "Snapshot Date": "={{ $json['Snapshot Date'] }}",
                    "Agent ID": "={{ $json['Agent ID'] }}",
                    "Revenue ZAR": "={{ $json['Revenue ZAR'] || 0 }}",
                    "Leads Generated": "={{ $json['Leads Generated'] || 0 }}",
                    "Content Published": "={{ $json['Content Published'] || 0 }}",
                    "Emails Sent": "={{ $json['Emails Sent'] || 0 }}",
                    "Messages Handled": "={{ $json['Messages Handled'] || 0 }}",
                    "Tickets Resolved": "={{ $json['Tickets Resolved'] || 0 }}",
                    "Success Rate": "={{ $json['Success Rate'] || 0 }}",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write KPI Snapshots",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1160, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 8. Update Agent Registry health scores
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_AGENT_REGISTRY, "mode": "id"},
            "columns": {
                "value": {
                    "KPIs": "={{ JSON.stringify($json) }}",
                }
            },
            "options": {},
            "matchingColumns": ["Agent ID"],
        },
        "id": uid(),
        "name": "Update Agent KPIs",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1380, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    return nodes


def build_orch03_connections(nodes):
    """Build connections for ORCH-03."""
    return {
        "Schedule Trigger": {"main": [[{"node": "Set Dates", "type": "main", "index": 0}]]},
        "Set Dates": {"main": [
            [{"node": "Read Marketing Metrics", "type": "main", "index": 0}],
            [{"node": "Read Finance Metrics", "type": "main", "index": 0}],
            [{"node": "Read Execution Stats", "type": "main", "index": 0}],
        ]},
        "Read Marketing Metrics": {"main": [[{"node": "Compute KPIs", "type": "main", "index": 0}]]},
        "Read Finance Metrics": {"main": [[{"node": "Compute KPIs", "type": "main", "index": 0}]]},
        "Read Execution Stats": {"main": [[{"node": "Compute KPIs", "type": "main", "index": 0}]]},
        "Compute KPIs": {"main": [[{"node": "Write KPI Snapshots", "type": "main", "index": 0}]]},
        "Write KPI Snapshots": {"main": [[{"node": "Update Agent KPIs", "type": "main", "index": 0}]]},
    }


# ══════════════════════════════════════════════════════════════
# ORCH-04: Weekly Report Generator
# ══════════════════════════════════════════════════════════════

def build_orch04_nodes():
    """Build nodes for ORCH-04: Weekly Report Generator (Mon 07:00 SAST)."""
    nodes = []

    # 1. Schedule Trigger (Mon 07:00 SAST = 05:00 UTC)
    nodes.append({
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 5 * * 1"}]}
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Read KPI History (last 7 days)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_KPI_SNAPSHOTS, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Snapshot Date}, DATEADD(TODAY(), -7, 'days'))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read KPI History",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [440, 140],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 3. Read Escalations (last 7 days)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ESCALATION_QUEUE, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Created At}, DATEADD(TODAY(), -7, 'days'))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Escalations",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [440, 340],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 4. Read Decisions (last 7 days)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_DECISION_LOG, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Created At}, DATEADD(TODAY(), -7, 'days'))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Decisions",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [440, 540],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 5. Merge All Data
    nodes.append({
        "parameters": {"mode": "combine", "combinationMode": "mergeByPosition", "options": {}},
        "id": uid(),
        "name": "Merge Data",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [700, 300],
    })

    # 6. AI Generate Summary (OpenRouter - Claude Sonnet)
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514",
  "max_tokens": 1500,
  "messages": [
    {
      "role": "system",
      "content": "You are the AVM Operations Intelligence Agent. Generate a concise executive summary for the weekly operations report. Focus on: 1) Key wins, 2) Areas of concern, 3) Recommendations. Use bullet points. Reference specific metrics. Be concise (max 400 words). Currency is ZAR (R)."
    },
    {
      "role": "user",
      "content": "Weekly Operations Data:\\n\\nKPI Snapshots (7 days): {{ JSON.stringify($('Read KPI History').all().map(i => i.json)) }}\\n\\nEscalations: {{ JSON.stringify($('Read Escalations').all().map(i => i.json)) }}\\n\\nAI Decisions Made: {{ $('Read Decisions').all().length }}\\n\\nGenerate the executive summary."
    }
  ]
}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Generate Summary",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [940, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # 7. Format Report (Code)
    nodes.append({
        "parameters": {"jsCode": ORCH04_FORMAT_REPORT_CODE},
        "id": uid(),
        "name": "Format Report",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1160, 300],
    })

    # 8. Send Weekly Email
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.html }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Weekly Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1380, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_orch04_connections(nodes):
    """Build connections for ORCH-04."""
    return {
        "Schedule Trigger": {"main": [
            [{"node": "Read KPI History", "type": "main", "index": 0}],
            [{"node": "Read Escalations", "type": "main", "index": 0}],
            [{"node": "Read Decisions", "type": "main", "index": 0}],
        ]},
        "Read KPI History": {"main": [[{"node": "Merge Data", "type": "main", "index": 0}]]},
        "Read Escalations": {"main": [[{"node": "Merge Data", "type": "main", "index": 1}]]},
        "Read Decisions": {"main": [[{"node": "AI Generate Summary", "type": "main", "index": 0}]]},
        "Merge Data": {"main": [[{"node": "AI Generate Summary", "type": "main", "index": 0}]]},
        "AI Generate Summary": {"main": [[{"node": "Format Report", "type": "main", "index": 0}]]},
        "Format Report": {"main": [[{"node": "Send Weekly Email", "type": "main", "index": 0}]]},
    }


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ══════════════════════════════════════════════════════════════

WORKFLOW_BUILDERS = {
    "orch01": {
        "name": "ORCH-01 Health Monitor",
        "build_nodes": build_orch01_nodes,
        "build_connections": build_orch01_connections,
        "filename": "orch01_health_monitor.json",
        "tags": ["orchestrator", "health-monitor", "auto-ops"],
    },
    "orch02": {
        "name": "ORCH-02 Cross-Dept Router",
        "build_nodes": build_orch02_nodes,
        "build_connections": build_orch02_connections,
        "filename": "orch02_cross_dept_router.json",
        "tags": ["orchestrator", "event-router", "auto-ops"],
    },
    "orch03": {
        "name": "ORCH-03 Daily KPI Aggregation",
        "build_nodes": build_orch03_nodes,
        "build_connections": build_orch03_connections,
        "filename": "orch03_daily_kpi_aggregation.json",
        "tags": ["orchestrator", "kpi", "analytics", "auto-ops"],
    },
    "orch04": {
        "name": "ORCH-04 Weekly Report Generator",
        "build_nodes": build_orch04_nodes,
        "build_connections": build_orch04_connections,
        "filename": "orch04_weekly_report.json",
        "tags": ["orchestrator", "reporting", "auto-ops"],
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
            "builder": "deploy_orchestrator.py",
            "built_at": datetime.now().isoformat(),
        },
    }


def save_workflow(key, workflow_json):
    """Save workflow JSON to disk."""
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "orchestrator"
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
        print("AVM Central Orchestrator - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_orchestrator.py build              # Build all")
        print("  python tools/deploy_orchestrator.py build orch01       # Build one")
        print("  python tools/deploy_orchestrator.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_orchestrator.py activate           # Build + Deploy + Activate")
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
    print("AVM CENTRAL ORCHESTRATOR - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/orchestrator/")

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
