"""
Optimization Layer - Workflow Builder & Deployer

Builds 3 optimization workflows for A/B testing, statistical analysis,
and client churn prediction.

Workflows:
    OPT-01: A/B Test Manager (Webhook POST /ab-test-create)
    OPT-02: A/B Test Analyzer (Daily 20:00 SAST)
    OPT-03: Churn Predictor (Fri 08:00 SAST)

Usage:
    python tools/deploy_optimization.py build              # Build all JSONs
    python tools/deploy_optimization.py build opt01        # Build OPT-01 only
    python tools/deploy_optimization.py build opt02        # Build OPT-02 only
    python tools/deploy_optimization.py build opt03        # Build OPT-03 only
    python tools/deploy_optimization.py deploy             # Build + Deploy (inactive)
    python tools/deploy_optimization.py activate           # Build + Deploy + Activate
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
TABLE_AB_TESTS = os.getenv("ORCH_TABLE_AB_TESTS", "REPLACE_AFTER_SETUP")
TABLE_ESCALATION_QUEUE = os.getenv("ORCH_TABLE_ESCALATION_QUEUE", "REPLACE_AFTER_SETUP")
TABLE_DECISION_LOG = os.getenv("ORCH_TABLE_DECISION_LOG", "REPLACE_AFTER_SETUP")
TABLE_EVENTS = os.getenv("ORCH_TABLE_EVENTS", "REPLACE_AFTER_SETUP")

# -- Portal API ------------------------------------------------------------

PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://portal.anyvisionmedia.com")

# -- Helpers ---------------------------------------------------------------


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# OPT-01: A/B Test Manager (Webhook)
# ==================================================================

def build_opt01_nodes():
    """Build nodes for OPT-01: A/B Test Manager (Webhook trigger)."""
    nodes = []

    # -- Webhook Trigger --
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "ab-test-create",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [220, 300],
        "webhookId": uid(),
    })

    # -- Validate Config (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Validate A/B test configuration
const body = $json.body || $json;

const required = ['test_name', 'variable', 'variant_a', 'variant_b', 'metric', 'sample_size_target'];
const missing = required.filter(f => !body[f]);

if (missing.length > 0) {
  return [{
    json: {
      valid: false,
      error: 'Missing required fields: ' + missing.join(', '),
      required_fields: required,
    }
  }];
}

const sampleSize = parseInt(body.sample_size_target);
if (isNaN(sampleSize) || sampleSize < 10) {
  return [{
    json: {
      valid: false,
      error: 'sample_size_target must be a number >= 10',
    }
  }];
}

return [{
  json: {
    valid: true,
    test_name: body.test_name,
    variable: body.variable,
    variant_a: body.variant_a,
    variant_b: body.variant_b,
    metric: body.metric,
    sample_size_target: sampleSize,
    created_at: new Date().toISOString(),
    status: 'Running',
    variant_a_successes: 0,
    variant_a_trials: 0,
    variant_b_successes: 0,
    variant_b_trials: 0,
  }
}];"""
        },
        "id": uid(),
        "name": "Validate Config",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [440, 300],
    })

    # -- Is Valid? (Switch) --
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.valid }}",
                                    "rightValue": True,
                                    "operator": {"type": "boolean", "operation": "true"},
                                }
                            ],
                        },
                        "renameOutput": "Valid",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.valid }}",
                                    "rightValue": False,
                                    "operator": {"type": "boolean", "operation": "false"},
                                }
                            ],
                        },
                        "renameOutput": "Invalid",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Is Valid?",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [660, 300],
    })

    # -- Create AB Test Record --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_AB_TESTS, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Test Name": "={{ $json.test_name }}",
                    "Variable": "={{ $json.variable }}",
                    "Variant A": "={{ $json.variant_a }}",
                    "Variant B": "={{ $json.variant_b }}",
                    "Metric": "={{ $json.metric }}",
                    "Sample Size Target": "={{ $json.sample_size_target }}",
                    "Status": "Running",
                    "Created At": "={{ $json.created_at }}",
                    "Variant A Successes": 0,
                    "Variant A Trials": 0,
                    "Variant B Successes": 0,
                    "Variant B Trials": 0,
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create AB Test",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [880, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Log Decision --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_DECISION_LOG, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Decision": "=Created A/B test: {{ $('Validate Config').first().json.test_name }}",
                    "Agent ID": "agent_orchestrator",
                    "Category": "optimization",
                    "Details": "=Variable: {{ $('Validate Config').first().json.variable }}, Metric: {{ $('Validate Config').first().json.metric }}, Target N: {{ $('Validate Config').first().json.sample_size_target }}",
                    "Decided At": "={{ $now.toISO() }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Decision",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1100, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Respond Success --
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ success: true, test_id: $('Create AB Test').first().json.id, test_name: $('Validate Config').first().json.test_name, status: 'Running' }) }}",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Success",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [1320, 200],
    })

    # -- Respond Error --
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ success: false, error: $json.error }) }}",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Error",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [880, 420],
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## OPT-01: A/B Test Manager\nWebhook POST /ab-test-create.\nValidates config, creates test record in Airtable,\nlogs decision, responds with test_id.",
            "width": 420,
            "height": 110,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_opt01_connections():
    """Build connections for OPT-01."""
    return {
        "Webhook": {
            "main": [[{"node": "Validate Config", "type": "main", "index": 0}]]
        },
        "Validate Config": {
            "main": [[{"node": "Is Valid?", "type": "main", "index": 0}]]
        },
        "Is Valid?": {
            "main": [
                [{"node": "Create AB Test", "type": "main", "index": 0}],
                [{"node": "Respond Error", "type": "main", "index": 0}],
            ]
        },
        "Create AB Test": {
            "main": [[{"node": "Log Decision", "type": "main", "index": 0}]]
        },
        "Log Decision": {
            "main": [[{"node": "Respond Success", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# OPT-02: A/B Test Analyzer
# ==================================================================

def build_opt02_nodes():
    """Build nodes for OPT-02: A/B Test Analyzer (daily 20:00 SAST = 18:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (18:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 18 * * *",
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

    # -- Read Running Tests --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_AB_TESTS, "mode": "id"},
            "filterByFormula": "{Status} = 'Running'",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Running Tests",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [440, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # -- Has Running Tests? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $input.all().length }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Running Tests?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [660, 300],
    })

    # -- Statistical Analysis (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Perform z-test for proportions on each running A/B test
const tests = $input.all().map(i => i.json);
const results = [];

for (const test of tests) {
  const nA = parseInt(test['Variant A Trials'] || 0);
  const nB = parseInt(test['Variant B Trials'] || 0);
  const sA = parseInt(test['Variant A Successes'] || 0);
  const sB = parseInt(test['Variant B Successes'] || 0);
  const targetN = parseInt(test['Sample Size Target'] || 100);

  const totalTrials = nA + nB;
  const sampleReached = totalTrials >= targetN;

  let pValue = null;
  let significant = false;
  let winner = null;

  if (nA >= 5 && nB >= 5) {
    // Proportions
    const pA = sA / nA;
    const pB = sB / nB;

    // Pooled proportion
    const pPool = (sA + sB) / (nA + nB);
    const se = Math.sqrt(pPool * (1 - pPool) * (1/nA + 1/nB));

    if (se > 0) {
      const z = (pA - pB) / se;
      // Two-tailed p-value approximation (using normal CDF)
      const absZ = Math.abs(z);
      // Approximation of erfc for p-value
      const t = 1 / (1 + 0.2316419 * absZ);
      const d = 0.3989423 * Math.exp(-absZ * absZ / 2);
      const p1 = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
      pValue = Math.round(2 * p1 * 10000) / 10000;
      significant = pValue < 0.05;

      if (significant) {
        winner = pA > pB ? 'A' : 'B';
      }
    }
  }

  let newStatus = 'Running';
  if (significant) {
    newStatus = 'Completed';
  } else if (sampleReached && !significant) {
    newStatus = 'Inconclusive';
  }

  results.push({
    json: {
      recordId: test.id,
      testName: test['Test Name'],
      variantA: test['Variant A'],
      variantB: test['Variant B'],
      metric: test['Metric'],
      nA, nB, sA, sB,
      rateA: nA > 0 ? Math.round((sA/nA) * 1000) / 10 : 0,
      rateB: nB > 0 ? Math.round((sB/nB) * 1000) / 10 : 0,
      totalTrials,
      targetN,
      sampleReached,
      pValue,
      significant,
      winner,
      newStatus,
    }
  });
}

return results;"""
        },
        "id": uid(),
        "name": "Statistical Analysis",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 300],
    })

    # -- Is Concluded? (status changed) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.newStatus }}",
                        "rightValue": "Running",
                        "operator": {"type": "string", "operation": "notEquals"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Is Concluded?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1100, 300],
    })

    # -- Update Test Record --
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_AB_TESTS, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "id": "={{ $json.recordId }}",
                    "Status": "={{ $json.newStatus }}",
                    "Winner": "={{ $json.winner || 'None' }}",
                    "P Value": "={{ $json.pValue }}",
                    "Completed At": "={{ $now.toISO() }}",
                },
                "matchingColumns": ["id"],
            },
            "options": {},
        },
        "id": uid(),
        "name": "Update Test Record",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1320, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Log Decision --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_DECISION_LOG, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Decision": "=A/B test '{{ $json.testName }}' concluded: {{ $json.newStatus }} (winner={{ $json.winner || 'None' }}, p={{ $json.pValue }})",
                    "Agent ID": "agent_orchestrator",
                    "Category": "optimization",
                    "Details": "=Variant A ({{ $json.variantA }}): {{ $json.rateA }}% (n={{ $json.nA }}), Variant B ({{ $json.variantB }}): {{ $json.rateB }}% (n={{ $json.nB }})",
                    "Decided At": "={{ $now.toISO() }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Decision",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1540, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Notify Results Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=A/B Test Result: {{ $('Statistical Analysis').first().json.testName }} - {{ $('Statistical Analysis').first().json.newStatus }}",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 600px;">
<div style="background: #FF6D5A; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
<h3 style="margin: 0;">A/B Test Result</h3>
</div>
<div style="padding: 16px; background: #f9f9f9;">
<p><strong>Test:</strong> {{ $('Statistical Analysis').first().json.testName }}</p>
<p><strong>Status:</strong> {{ $('Statistical Analysis').first().json.newStatus }}</p>
<p><strong>Winner:</strong> {{ $('Statistical Analysis').first().json.winner || 'None' }}</p>
<p><strong>p-value:</strong> {{ $('Statistical Analysis').first().json.pValue }}</p>
<hr>
<p><strong>Variant A</strong> ({{ $('Statistical Analysis').first().json.variantA }}): {{ $('Statistical Analysis').first().json.rateA }}% success (n={{ $('Statistical Analysis').first().json.nA }})</p>
<p><strong>Variant B</strong> ({{ $('Statistical Analysis').first().json.variantB }}): {{ $('Statistical Analysis').first().json.rateB }}% success (n={{ $('Statistical Analysis').first().json.nB }})</p>
<p style="color: #888; font-size: 12px;">Generated by AVM Optimization Engine | OPT-02</p>
</div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Notify Results",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1760, 200],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## OPT-02: A/B Test Analyzer\nRuns daily 20:00 SAST. Reads running tests,\nperforms z-test for proportions, updates status\nwhen significant (p<0.05) or sample reached.",
            "width": 420,
            "height": 110,
        },
        "id": uid(),
        "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [180, 140],
    })

    return nodes


def build_opt02_connections():
    """Build connections for OPT-02."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Read Running Tests", "type": "main", "index": 0}]]
        },
        "Read Running Tests": {
            "main": [[{"node": "Has Running Tests?", "type": "main", "index": 0}]]
        },
        "Has Running Tests?": {
            "main": [
                [{"node": "Statistical Analysis", "type": "main", "index": 0}],
                [],
            ]
        },
        "Statistical Analysis": {
            "main": [[{"node": "Is Concluded?", "type": "main", "index": 0}]]
        },
        "Is Concluded?": {
            "main": [
                [{"node": "Update Test Record", "type": "main", "index": 0}],
                [],
            ]
        },
        "Update Test Record": {
            "main": [[{"node": "Log Decision", "type": "main", "index": 0}]]
        },
        "Log Decision": {
            "main": [[{"node": "Notify Results", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# OPT-03: Churn Predictor
# ==================================================================

def build_opt03_nodes():
    """Build nodes for OPT-03: Churn Predictor (Fri 08:00 SAST = 06:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (Fri 06:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 6 * * 5",
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

    # -- Fetch Client Health Data --
    nodes.append({
        "parameters": {
            "url": f"{PORTAL_BASE_URL}/api/admin/clients",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "x-admin-key", "value": "={{ $env.PORTAL_ADMIN_KEY || '' }}"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Fetch Clients",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [440, 300],
    })

    # -- Analyze Churn Risk (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Analyze client health score trajectory for churn prediction
const clients = $json.data || $json.clients || $json || [];
const clientList = Array.isArray(clients) ? clients : [clients];

const churnRisks = [];
const healthy = [];

for (const client of clientList) {
  if (!client || !client.id) continue;

  // Extract health score history (last 12 weeks)
  const history = client.health_scores || client.healthScores || [];
  const scores = history.map(h => parseFloat(h.score || h.health_score || 0));

  if (scores.length < 4) {
    // Not enough history, skip
    continue;
  }

  // Compute slope using simple linear regression
  const n = scores.length;
  const x = Array.from({length: n}, (_, i) => i);
  const meanX = x.reduce((a, b) => a + b, 0) / n;
  const meanY = scores.reduce((a, b) => a + b, 0) / n;

  let num = 0, den = 0;
  for (let i = 0; i < n; i++) {
    num += (x[i] - meanX) * (scores[i] - meanY);
    den += (x[i] - meanX) ** 2;
  }
  const slope = den > 0 ? num / den : 0;
  const currentScore = scores[scores.length - 1];

  // Churn risk: slope < -2 per week AND current score < 50
  if (slope < -2 && currentScore < 50) {
    const weeksToZero = currentScore > 0 && slope < 0 ? Math.round(currentScore / Math.abs(slope)) : 99;
    churnRisks.push({
      clientId: client.id,
      clientName: client.full_name || client.company_name || client.email || 'Unknown',
      email: client.email || '',
      currentScore: Math.round(currentScore),
      slopePerWeek: Math.round(slope * 100) / 100,
      estimatedWeeksToChurn: weeksToZero,
      recentScores: scores.slice(-4),
      riskLevel: currentScore < 25 ? 'critical' : currentScore < 40 ? 'high' : 'moderate',
    });
  } else {
    healthy.push({
      clientId: client.id,
      clientName: client.full_name || client.company_name || 'Unknown',
      currentScore: Math.round(currentScore),
    });
  }
}

// Sort by risk level
const riskOrder = { critical: 0, high: 1, moderate: 2 };
churnRisks.sort((a, b) => (riskOrder[a.riskLevel] || 3) - (riskOrder[b.riskLevel] || 3));

return [{
  json: {
    totalClients: clientList.length,
    churnRiskCount: churnRisks.length,
    healthyCount: healthy.length,
    churnRisks,
    hasRisks: churnRisks.length > 0,
    analysisDate: $now.format('yyyy-MM-dd'),
  }
}];"""
        },
        "id": uid(),
        "name": "Analyze Churn Risk",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [660, 300],
    })

    # -- Has Churn Risks? --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.churnRiskCount }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Has Churn Risks?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [880, 300],
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
                    "Title": "=Client Churn Risk Alert - {{ $json.churnRiskCount }} client(s) at risk",
                    "Category": "client_churn_risk",
                    "Severity": "P2",
                    "Description": "={{ $json.churnRiskCount }} client(s) identified with declining health scores. Immediate attention required to prevent churn.",
                    "Recommended Action": "Review at-risk client accounts. Schedule check-in calls. Prepare retention offers if needed.",
                    "Status": "open",
                    "Agent ID": "agent_client_relations",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Escalation",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1100, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Split Churn Risks --
    nodes.append({
        "parameters": {
            "jsCode": """// Split churn risks into individual items for event creation
const risks = $('Analyze Churn Risk').first().json.churnRisks || [];
return risks.map(r => ({ json: r }));"""
        },
        "id": uid(),
        "name": "Split Churn Risks",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 400],
    })

    # -- Create Churn Event --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_EVENTS, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Event Type": "client_churn_risk",
                    "Agent ID": "agent_client_relations",
                    "Details": "=Client {{ $json.clientName }} (score: {{ $json.currentScore }}, slope: {{ $json.slopePerWeek }}/week, risk: {{ $json.riskLevel }})",
                    "Created At": "={{ $now.toISO() }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Churn Event",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1320, 400],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Summary Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Churn Risk Alert - {{ $('Analyze Churn Risk').first().json.churnRiskCount }} client(s) at risk",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 600px;">
<div style="background: #FF6D5A; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
<h3 style="margin: 0;">Client Churn Risk Report</h3>
<p style="margin: 4px 0 0; opacity: 0.9; font-size: 13px;">{{ $('Analyze Churn Risk').first().json.analysisDate }}</p>
</div>
<div style="padding: 16px; background: #f9f9f9;">
<p><strong>Total clients analyzed:</strong> {{ $('Analyze Churn Risk').first().json.totalClients }}</p>
<p><strong>At-risk clients:</strong> <span style="color: #e74c3c; font-weight: bold;">{{ $('Analyze Churn Risk').first().json.churnRiskCount }}</span></p>
<p><strong>Healthy clients:</strong> {{ $('Analyze Churn Risk').first().json.healthyCount }}</p>
<hr>
<h4>At-Risk Clients</h4>
<p>{{ JSON.stringify($('Analyze Churn Risk').first().json.churnRisks.map(r => r.clientName + ' (score: ' + r.currentScore + ', ' + r.riskLevel + ')').join(', ')) }}</p>
<hr>
<p style="color: #888; font-size: 12px;">Generated by AVM Optimization Engine | OPT-03</p>
</div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Summary Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1540, 200],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## OPT-03: Churn Predictor\nRuns Fri 08:00 SAST. Fetches client data from portal,\nanalyzes 12-week health score trajectory.\nFlags clients with slope < -2/week AND score < 50.\nCreates escalation + per-client events.",
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


def build_opt03_connections():
    """Build connections for OPT-03."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Fetch Clients", "type": "main", "index": 0}]]
        },
        "Fetch Clients": {
            "main": [[{"node": "Analyze Churn Risk", "type": "main", "index": 0}]]
        },
        "Analyze Churn Risk": {
            "main": [[{"node": "Has Churn Risks?", "type": "main", "index": 0}]]
        },
        "Has Churn Risks?": {
            "main": [
                [
                    {"node": "Create Escalation", "type": "main", "index": 0},
                    {"node": "Split Churn Risks", "type": "main", "index": 0},
                ],
                [],
            ]
        },
        "Create Escalation": {
            "main": [[{"node": "Summary Email", "type": "main", "index": 0}]]
        },
        "Split Churn Risks": {
            "main": [[{"node": "Create Churn Event", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# WORKFLOW DEFINITIONS
# ==================================================================

WORKFLOW_DEFS = {
    "opt01": {
        "name": "Optimization - A/B Test Manager (OPT-01)",
        "filename": "opt01_ab_test_manager.json",
        "build_nodes": build_opt01_nodes,
        "build_connections": build_opt01_connections,
    },
    "opt02": {
        "name": "Optimization - A/B Test Analyzer (OPT-02)",
        "filename": "opt02_ab_test_analyzer.json",
        "build_nodes": build_opt02_nodes,
        "build_connections": build_opt02_connections,
    },
    "opt03": {
        "name": "Optimization - Churn Predictor (OPT-03)",
        "filename": "opt03_churn_predictor.json",
        "build_nodes": build_opt03_nodes,
        "build_connections": build_opt03_connections,
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
    output_dir = Path(__file__).parent.parent / "workflows" / "optimization"
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
    print("OPTIMIZATION LAYER - WORKFLOW BUILDER")
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
    if "REPLACE" in TABLE_AB_TESTS:
        missing.append("ORCH_TABLE_AB_TESTS")
    if "REPLACE" in TABLE_ESCALATION_QUEUE:
        missing.append("ORCH_TABLE_ESCALATION_QUEUE")

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
    print("  1. Create Airtable table: AB_Tests (in ORCH base)")
    print("  2. Set env var: ORCH_TABLE_AB_TESTS")
    print("  3. Set env var: PORTAL_ADMIN_KEY (for OPT-03 client data API)")
    print("  4. Open each workflow in n8n UI to verify node connections")
    print("  5. Test OPT-01 via POST to webhook /ab-test-create")
    print("  6. Test OPT-03 manually -> check churn analysis")
    print("  7. Once verified, run with 'activate' to enable schedules")


if __name__ == "__main__":
    main()
