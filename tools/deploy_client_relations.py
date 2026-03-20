"""
Client Relations Department - Workflow Builder & Deployer

Builds all Client Relations workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance.

Workflows:
    CR-01: Client Health Scorer (Daily 08:00 SAST)
    CR-02: Renewal Manager (Daily 09:00 SAST)
    CR-03: Onboarding Automation (Webhook)
    CR-04: Client Satisfaction Pulse (Monthly 1st 10:00 SAST)

Usage:
    python tools/deploy_client_relations.py build              # Build all workflow JSONs
    python tools/deploy_client_relations.py build cr01         # Build CR-01 only
    python tools/deploy_client_relations.py build cr02         # Build CR-02 only
    python tools/deploy_client_relations.py build cr03         # Build CR-03 only
    python tools/deploy_client_relations.py build cr04         # Build CR-04 only
    python tools/deploy_client_relations.py deploy             # Build + Deploy (inactive)
    python tools/deploy_client_relations.py activate           # Build + Deploy + Activate
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
CRED_GMAIL = {"id": "2IuycrTIgWJZEjBE", "name": "Gmail account AVM Tutorial"}
CRED_AIRTABLE = {"id": "ZyBrcAO6fps7YB3u", "name": "Airtable account"}

# -- Airtable IDs ---------------------------------------------------------

ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
TABLE_ESCALATION_QUEUE = os.getenv("ORCH_TABLE_ESCALATION_QUEUE", "REPLACE_WITH_TABLE_ID")
TABLE_EVENTS = os.getenv("ORCH_TABLE_EVENTS", "REPLACE_WITH_TABLE_ID")
TABLE_DECISION_LOG = os.getenv("ORCH_TABLE_DECISION_LOG", "REPLACE_WITH_TABLE_ID")

# -- Constants -------------------------------------------------------------

PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://portal.anyvisionmedia.com")
ALERT_EMAIL = "ian@anyvisionmedia.com"
AI_MODEL = "anthropic/claude-sonnet-4-20250514"

# -- AI Prompts ------------------------------------------------------------

CLIENT_SATISFACTION_PROMPT = """You are a client relations specialist for AnyVision Media, a digital media and AI automation agency based in South Africa.

## Your Task
Draft a personalized check-in email for each client based on their usage data, subscription status, and recent activity. The email should feel genuine and personal, not templated.

## Company Context
- Brand: AnyVision Media
- Owner: Ian Immelman
- Services: AI workflow automation, web development, social media management
- Tone: Professional but warm, relationship-focused, value-driven

## For Each Client, Generate:
1. A personalized subject line referencing something specific to their usage
2. A warm greeting using their name
3. 1-2 sentences acknowledging their specific usage patterns or achievements
4. A helpful tip or suggestion based on their plan/usage
5. An open-ended question to encourage dialogue
6. A professional sign-off

## Output Format (JSON only, no markdown, no backticks):
{
  "emails": [
    {
      "client_email": "email",
      "client_name": "name",
      "subject": "personalized subject",
      "body_html": "<p>Full HTML email body</p>",
      "tone": "warm|celebratory|supportive|re-engaging"
    }
  ],
  "summary": "Brief summary of outreach batch"
}

## Rules
- Never use generic phrases like "Just checking in" or "Hope you're well"
- Reference specific data points (e.g., "Your team ran 142 automations this month")
- South African business context (ZAR, local references where natural)
- Keep each email under 200 words
- Flag any clients who seem disengaged for special attention"""


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# CR-01: CLIENT HEALTH SCORER
# ==================================================================

HEALTH_SCORER_CODE = """// Client Health Scorer - scores each client on 4 dimensions
const clients = $input.first().json.body || $input.first().json || [];
const clientList = Array.isArray(clients) ? clients : (clients.data || clients.clients || []);

const results = [];
for (const client of clientList) {
  // Usage frequency (0-25): based on logins/actions in last 30 days
  const usageRaw = client.usage_count || client.logins_30d || 0;
  const usageScore = Math.min(25, Math.round(usageRaw / 4));

  // Payment history (0-25): based on on-time payment ratio
  const paymentRatio = client.payment_on_time_ratio || client.payment_score || 0;
  const paymentScore = Math.min(25, Math.round(paymentRatio * 25));

  // Portal engagement (0-25): based on features used, pages visited
  const engagement = client.portal_engagement || client.features_used || 0;
  const engagementScore = Math.min(25, Math.round(engagement * 2.5));

  // Support tickets (0-25): inverse - fewer open tickets = healthier
  const openTickets = client.open_tickets || 0;
  const ticketScore = Math.max(0, 25 - (openTickets * 5));

  const composite = usageScore + paymentScore + engagementScore + ticketScore;

  results.push({
    client_id: client.id || client.client_id || 'unknown',
    client_email: client.email || '',
    client_name: client.name || client.company || '',
    plan: client.plan || client.subscription || 'unknown',
    scores: {
      usage: usageScore,
      payment: paymentScore,
      engagement: engagementScore,
      support: ticketScore
    },
    composite_score: composite,
    health_grade: composite >= 80 ? 'Healthy' : composite >= 60 ? 'Stable' : composite >= 40 ? 'At Risk' : 'Critical',
    scored_at: new Date().toISOString()
  });
}

const atRisk = results.filter(r => r.composite_score < 40);
const avgScore = results.length > 0 ? Math.round(results.reduce((a, b) => a + b.composite_score, 0) / results.length) : 0;

return {
  json: {
    clients: results,
    at_risk_clients: atRisk,
    summary: {
      total_clients: results.length,
      avg_score: avgScore,
      at_risk_count: atRisk.length,
      healthy_count: results.filter(r => r.composite_score >= 80).length,
      scored_at: new Date().toISOString()
    }
  }
};"""

AT_RISK_ALERT_HTML = """=<h2>Client Churn Risk Alert</h2>
<p>The following clients have health scores below 40 (Critical):</p>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
<tr style="background:#FF6D5A;color:white;">
<th>Client</th><th>Email</th><th>Score</th><th>Grade</th><th>Weakest Area</th>
</tr>
{{ $json.at_risk_clients.map(c => {
  const scores = c.scores;
  const weakest = Object.entries(scores).sort((a,b) => a[1]-b[1])[0];
  return '<tr><td>' + c.client_name + '</td><td>' + c.client_email + '</td><td>' + c.composite_score + '/100</td><td>' + c.health_grade + '</td><td>' + weakest[0] + ' (' + weakest[1] + '/25)</td></tr>';
}).join('') }}
</table>
<p><strong>Total at-risk:</strong> {{ $json.at_risk_clients.length }} clients</p>
<p><strong>Action required:</strong> Review each client and schedule personal outreach.</p>"""


def build_cr01_nodes():
    """Build all nodes for the Client Health Scorer workflow."""
    nodes = []

    # -- Schedule Trigger --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 6 * * *"}]
            }
        },
        "id": uid(),
        "name": "Daily 08:00 SAST",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.toFormat('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                    {"id": uid(), "name": "portalUrl", "value": PORTAL_BASE_URL, "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 400],
        "typeVersion": 3.4,
    })

    # -- Fetch All Clients --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": f"={PORTAL_BASE_URL}/api/admin/clients",
            "authentication": "none",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Fetch All Clients",
        "type": "n8n-nodes-base.httpRequest",
        "position": [680, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # -- Score Clients --
    nodes.append({
        "parameters": {
            "jsCode": HEALTH_SCORER_CODE,
        },
        "id": uid(),
        "name": "Score Clients",
        "type": "n8n-nodes-base.code",
        "position": [920, 400],
        "typeVersion": 2,
    })

    # -- If Any At Risk --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.summary.at_risk_count }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Any At Risk?",
        "type": "n8n-nodes-base.if",
        "position": [1160, 400],
        "typeVersion": 2.2,
    })

    # -- Create Escalation (true branch) --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ESCALATION_QUEUE, "mode": "id"},
            "columns": {
                "value": {
                    "Category": "Client_Churn_Risk",
                    "Source Workflow": "CR-01 Client Health Scorer",
                    "Priority": "High",
                    "Description": "={{ $json.summary.at_risk_count }} clients with health score < 40. Avg score: {{ $json.summary.avg_score }}",
                    "Details": "={{ JSON.stringify($json.at_risk_clients.map(c => ({name: c.client_name, email: c.client_email, score: c.composite_score}))) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}",
                    "Status": "Open",
                },
                "schema": [
                    {"id": "Category", "type": "string", "display": True, "displayName": "Category"},
                    {"id": "Source Workflow", "type": "string", "display": True, "displayName": "Source Workflow"},
                    {"id": "Priority", "type": "string", "display": True, "displayName": "Priority"},
                    {"id": "Description", "type": "string", "display": True, "displayName": "Description"},
                    {"id": "Details", "type": "string", "display": True, "displayName": "Details"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Create Escalation",
        "type": "n8n-nodes-base.airtable",
        "position": [1400, 300],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Update Agent Status --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"={PORTAL_BASE_URL}/api/admin/agents",
            "authentication": "none",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({agent: 'agent_client_relations', status: 'healthy', last_run: $now.toFormat('yyyy-MM-dd HH:mm:ss'), metrics: {total_clients: $json.summary.total_clients, avg_score: $json.summary.avg_score, at_risk: $json.summary.at_risk_count}}) }}",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Update Agent Status",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1400, 500],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Gmail Alert --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=CLIENT CHURN RISK: {{ $('Score Clients').first().json.summary.at_risk_count }} clients at risk",
            "emailType": "html",
            "message": AT_RISK_ALERT_HTML,
            "options": {},
        },
        "id": uid(),
        "name": "Alert At-Risk Clients",
        "type": "n8n-nodes-base.gmail",
        "position": [1640, 300],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # -- Log Event --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_EVENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Event Type": "health_score_completed",
                    "Source": "CR-01",
                    "Details": "={{ JSON.stringify($('Score Clients').first().json.summary) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}",
                },
                "schema": [
                    {"id": "Event Type", "type": "string", "display": True, "displayName": "Event Type"},
                    {"id": "Source", "type": "string", "display": True, "displayName": "Source"},
                    {"id": "Details", "type": "string", "display": True, "displayName": "Details"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Health Score Event",
        "type": "n8n-nodes-base.airtable",
        "position": [1640, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 880],
        "typeVersion": 1,
    })
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "CR-01 ERROR - Client Health Scorer",
            "emailType": "html",
            "message": "=<h2>Client Health Scorer Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Notes --
    nodes.append({
        "parameters": {
            "content": "## CR-01: Client Health Scorer\n\n**Schedule:** Daily 08:00 SAST\n**Purpose:** Score each client on 4 dimensions (usage, payment, engagement, support) and flag at-risk clients for intervention.",
            "height": 160, "width": 420,
        },
        "id": f"cr01-note-1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note 1",
    })

    return nodes


def build_cr01_connections():
    """Build connections for the Client Health Scorer workflow."""
    return {
        "Daily 08:00 SAST": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Fetch All Clients", "type": "main", "index": 0}]],
        },
        "Fetch All Clients": {
            "main": [[{"node": "Score Clients", "type": "main", "index": 0}]],
        },
        "Score Clients": {
            "main": [[{"node": "Any At Risk?", "type": "main", "index": 0}]],
        },
        "Any At Risk?": {
            "main": [
                [
                    {"node": "Create Escalation", "type": "main", "index": 0},
                    {"node": "Alert At-Risk Clients", "type": "main", "index": 0},
                ],
                [
                    {"node": "Update Agent Status", "type": "main", "index": 0},
                ],
            ],
        },
        "Create Escalation": {
            "main": [[{"node": "Update Agent Status", "type": "main", "index": 0}]],
        },
        "Update Agent Status": {
            "main": [[{"node": "Log Health Score Event", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# CR-02: RENEWAL MANAGER
# ==================================================================

RENEWAL_FILTER_CODE = """// Filter subscriptions by expiry window and join with health context
const input = $input.first().json;
const subscriptions = input.body || input.data || input || [];
const subList = Array.isArray(subscriptions) ? subscriptions : (subscriptions.subscriptions || []);

const now = new Date();
const results = {
  expiring_30: [],
  expiring_60: [],
  expiring_90: [],
  expired: [],
};

for (const sub of subList) {
  const expiryDate = new Date(sub.expires_at || sub.end_date || sub.renewal_date);
  const daysUntil = Math.round((expiryDate - now) / (1000 * 60 * 60 * 24));
  const healthScore = sub.health_score || sub.composite_score || 50;

  const record = {
    client_id: sub.client_id || sub.id,
    client_email: sub.email || sub.client_email || '',
    client_name: sub.name || sub.client_name || '',
    plan: sub.plan || sub.subscription_plan || 'unknown',
    expires_at: expiryDate.toISOString(),
    days_until_expiry: daysUntil,
    health_score: healthScore,
    health_status: healthScore >= 60 ? 'healthy' : 'at_risk',
    monthly_value: sub.monthly_value || sub.amount || 0,
  };

  if (daysUntil < 0) {
    results.expired.push(record);
  } else if (daysUntil <= 30) {
    results.expiring_30.push(record);
  } else if (daysUntil <= 60) {
    results.expiring_60.push(record);
  } else if (daysUntil <= 90) {
    results.expiring_90.push(record);
  }
}

const allExpiring = [...results.expiring_30, ...results.expiring_60, ...results.expiring_90];
const healthyRenewals = allExpiring.filter(r => r.health_status === 'healthy');
const atRiskRenewals = allExpiring.filter(r => r.health_status === 'at_risk');

return {
  json: {
    healthy_renewals: healthyRenewals,
    at_risk_renewals: atRiskRenewals,
    expired: results.expired,
    summary: {
      total_expiring: allExpiring.length,
      healthy_count: healthyRenewals.length,
      at_risk_count: atRiskRenewals.length,
      expired_count: results.expired.length,
    }
  }
};"""


def build_cr02_nodes():
    """Build all nodes for the Renewal Manager workflow."""
    nodes = []

    # -- Schedule Trigger --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 7 * * *"}]
            }
        },
        "id": uid(),
        "name": "Daily 09:00 SAST",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.toFormat('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 400],
        "typeVersion": 3.4,
    })

    # -- Fetch Subscriptions --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": f"={PORTAL_BASE_URL}/api/billing/subscriptions",
            "authentication": "none",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Fetch Subscriptions",
        "type": "n8n-nodes-base.httpRequest",
        "position": [680, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # -- Filter & Classify --
    nodes.append({
        "parameters": {
            "jsCode": RENEWAL_FILTER_CODE,
        },
        "id": uid(),
        "name": "Filter Renewals",
        "type": "n8n-nodes-base.code",
        "position": [920, 400],
        "typeVersion": 2,
    })

    # -- Switch: Renewal Type --
    nodes.append({
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.summary.healthy_count }}",
                                    "rightValue": 0,
                                    "operator": {"type": "number", "operation": "gt"},
                                }
                            ]
                        },
                        "renameOutput": True, "outputKey": "healthy_renewal",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.summary.at_risk_count }}",
                                    "rightValue": 0,
                                    "operator": {"type": "number", "operation": "gt"},
                                }
                            ]
                        },
                        "renameOutput": True, "outputKey": "at_risk_renewal",
                    },
                    {
                        "conditions": {
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.summary.expired_count }}",
                                    "rightValue": 0,
                                    "operator": {"type": "number", "operation": "gt"},
                                }
                            ]
                        },
                        "renameOutput": True, "outputKey": "expired",
                    },
                ]
            }
        },
        "id": uid(),
        "name": "Route Renewal Type",
        "type": "n8n-nodes-base.switch",
        "position": [1160, 400],
        "typeVersion": 3.2,
    })

    # -- Healthy Renewal: Auto-send Reminder --
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.healthy_renewals.map(r => r.client_email).join(',') }}",
            "subject": "=Your AnyVision Media subscription is coming up for renewal",
            "emailType": "html",
            "message": "=<h2>Subscription Renewal Reminder</h2>\n<p>Hi there,</p>\n<p>Your subscription with AnyVision Media is approaching its renewal date. We're glad to have you on board!</p>\n<p><strong>Details:</strong></p>\n<ul>\n{{ $json.healthy_renewals.map(r => '<li>' + r.client_name + ' - ' + r.plan + ' (expires ' + r.expires_at.substring(0,10) + ', ' + r.days_until_expiry + ' days)</li>').join('') }}\n</ul>\n<p>No action needed - your subscription will auto-renew. If you have any questions, just reply to this email.</p>\n<p>Best regards,<br>AnyVision Media Team</p>",
            "options": {},
        },
        "id": uid(),
        "name": "Send Renewal Reminder",
        "type": "n8n-nodes-base.gmail",
        "position": [1440, 250],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # -- At-Risk Renewal: Create Escalation --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ESCALATION_QUEUE, "mode": "id"},
            "columns": {
                "value": {
                    "Category": "Renewal_At_Risk",
                    "Source Workflow": "CR-02 Renewal Manager",
                    "Priority": "High",
                    "Description": "={{ $json.summary.at_risk_count }} at-risk renewals need personal outreach",
                    "Details": "={{ JSON.stringify($json.at_risk_renewals.map(r => ({name: r.client_name, email: r.client_email, plan: r.plan, days: r.days_until_expiry, health: r.health_score}))) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}",
                    "Status": "Open",
                },
                "schema": [
                    {"id": "Category", "type": "string", "display": True, "displayName": "Category"},
                    {"id": "Source Workflow", "type": "string", "display": True, "displayName": "Source Workflow"},
                    {"id": "Priority", "type": "string", "display": True, "displayName": "Priority"},
                    {"id": "Description", "type": "string", "display": True, "displayName": "Description"},
                    {"id": "Details", "type": "string", "display": True, "displayName": "Details"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                    {"id": "Status", "type": "string", "display": True, "displayName": "Status"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Escalate At-Risk Renewal",
        "type": "n8n-nodes-base.airtable",
        "position": [1440, 450],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Expired: Urgent Notification --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=URGENT: {{ $json.summary.expired_count }} expired subscriptions",
            "emailType": "html",
            "message": "=<h2 style=\"color:#FF6D5A;\">Expired Subscriptions</h2>\n<p>The following subscriptions have expired and need immediate attention:</p>\n<table border=\"1\" cellpadding=\"8\" cellspacing=\"0\" style=\"border-collapse:collapse;\">\n<tr style=\"background:#FF6D5A;color:white;\"><th>Client</th><th>Email</th><th>Plan</th><th>Expired</th><th>Health</th></tr>\n{{ $json.expired.map(r => '<tr><td>' + r.client_name + '</td><td>' + r.client_email + '</td><td>' + r.plan + '</td><td>' + r.expires_at.substring(0,10) + '</td><td>' + r.health_score + '/100</td></tr>').join('') }}\n</table>",
            "options": {},
        },
        "id": uid(),
        "name": "Alert Expired",
        "type": "n8n-nodes-base.gmail",
        "position": [1440, 650],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # -- Log Event --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_EVENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Event Type": "renewal_check_completed",
                    "Source": "CR-02",
                    "Details": "={{ JSON.stringify($('Filter Renewals').first().json.summary) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}",
                },
                "schema": [
                    {"id": "Event Type", "type": "string", "display": True, "displayName": "Event Type"},
                    {"id": "Source", "type": "string", "display": True, "displayName": "Source"},
                    {"id": "Details", "type": "string", "display": True, "displayName": "Details"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Renewal Event",
        "type": "n8n-nodes-base.airtable",
        "position": [1680, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 880],
        "typeVersion": 1,
    })
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "CR-02 ERROR - Renewal Manager",
            "emailType": "html",
            "message": "=<h2>Renewal Manager Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## CR-02: Renewal Manager\n\n**Schedule:** Daily 09:00 SAST\n**Purpose:** Check subscription expiry dates, auto-remind healthy clients, escalate at-risk, alert on expired.",
            "height": 160, "width": 420,
        },
        "id": "cr02-note-1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note 1",
    })

    return nodes


def build_cr02_connections():
    """Build connections for the Renewal Manager workflow."""
    return {
        "Daily 09:00 SAST": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Fetch Subscriptions", "type": "main", "index": 0}]],
        },
        "Fetch Subscriptions": {
            "main": [[{"node": "Filter Renewals", "type": "main", "index": 0}]],
        },
        "Filter Renewals": {
            "main": [[{"node": "Route Renewal Type", "type": "main", "index": 0}]],
        },
        "Route Renewal Type": {
            "main": [
                [{"node": "Send Renewal Reminder", "type": "main", "index": 0}],
                [{"node": "Escalate At-Risk Renewal", "type": "main", "index": 0}],
                [{"node": "Alert Expired", "type": "main", "index": 0}],
            ],
        },
        "Send Renewal Reminder": {
            "main": [[{"node": "Log Renewal Event", "type": "main", "index": 0}]],
        },
        "Escalate At-Risk Renewal": {
            "main": [[{"node": "Log Renewal Event", "type": "main", "index": 0}]],
        },
        "Alert Expired": {
            "main": [[{"node": "Log Renewal Event", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# CR-03: ONBOARDING AUTOMATION
# ==================================================================

ONBOARDING_EXTRACT_CODE = """// Extract client data from webhook body
const body = $json.body || $json;
const client = {
  email: (body.email || body.client_email || '').toLowerCase().trim(),
  name: body.name || body.client_name || body.full_name || '',
  company: body.company || body.organization || '',
  plan: body.plan || body.subscription_plan || 'starter',
  phone: body.phone || '',
  source: body.source || body.utm_source || 'direct',
};

if (!client.email) {
  throw new Error('Client email is required for onboarding');
}

return { json: { client } };"""

WELCOME_EMAIL_HTML = """=<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
<div style="background:#FF6D5A;padding:30px;text-align:center;">
<h1 style="color:white;margin:0;">Welcome to AnyVision Media!</h1>
</div>
<div style="padding:30px;background:#f9f9f9;">
<p>Hi {{ $json.client.name || 'there' }},</p>
<p>Welcome aboard! We're thrilled to have {{ $json.client.company || 'you' }} as part of the AnyVision Media family.</p>
<h3 style="color:#FF6D5A;">Getting Started in 3 Easy Steps:</h3>
<ol>
<li><strong>Log in to your portal:</strong> <a href="https://portal.anyvisionmedia.com">portal.anyvisionmedia.com</a></li>
<li><strong>Complete your profile:</strong> Add your business details and preferences</li>
<li><strong>Explore your dashboard:</strong> See real-time analytics and workflow status</li>
</ol>
<h3 style="color:#FF6D5A;">Your Plan: {{ $json.client.plan }}</h3>
<p>Here's what's included with your plan and how to make the most of it:</p>
<ul>
<li>AI-powered workflow automation</li>
<li>Real-time performance dashboard</li>
<li>Dedicated support via email or WhatsApp</li>
</ul>
<p>If you have any questions, simply reply to this email or reach out to us anytime.</p>
<p>Looking forward to building something amazing together!</p>
<p>Best regards,<br><strong>Ian Immelman</strong><br>AnyVision Media</p>
</div>
</div>"""


def build_cr03_nodes():
    """Build all nodes for the Onboarding Automation workflow."""
    nodes = []

    # -- Webhook Trigger --
    nodes.append({
        "parameters": {
            "path": "client-onboarding",
            "httpMethod": "POST",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Onboarding Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 400],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # -- Extract Client Data --
    nodes.append({
        "parameters": {
            "jsCode": ONBOARDING_EXTRACT_CODE,
        },
        "id": uid(),
        "name": "Extract Client Data",
        "type": "n8n-nodes-base.code",
        "position": [440, 400],
        "typeVersion": 2,
    })

    # -- Send Welcome Email --
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.client.email }}",
            "subject": "=Welcome to AnyVision Media, {{ $json.client.name || 'there' }}!",
            "emailType": "html",
            "message": WELCOME_EMAIL_HTML,
            "options": {},
        },
        "id": uid(),
        "name": "Send Welcome Email",
        "type": "n8n-nodes-base.gmail",
        "position": [680, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # -- Create Orchestrator Event --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_EVENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Event Type": "client_onboarded",
                    "Source": "CR-03",
                    "Details": "={{ JSON.stringify({email: $('Extract Client Data').first().json.client.email, name: $('Extract Client Data').first().json.client.name, plan: $('Extract Client Data').first().json.client.plan}) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}",
                },
                "schema": [
                    {"id": "Event Type", "type": "string", "display": True, "displayName": "Event Type"},
                    {"id": "Source", "type": "string", "display": True, "displayName": "Source"},
                    {"id": "Details", "type": "string", "display": True, "displayName": "Details"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Onboarding Event",
        "type": "n8n-nodes-base.airtable",
        "position": [920, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Respond to Webhook --
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({success: true, message: 'Onboarding initiated', client_email: $('Extract Client Data').first().json.client.email, plan: $('Extract Client Data').first().json.client.plan}) }}",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Success",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [1160, 400],
        "typeVersion": 1.1,
    })

    # -- Notify Ian --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=New Client Onboarded: {{ $('Extract Client Data').first().json.client.name }} ({{ $('Extract Client Data').first().json.client.plan }})",
            "emailType": "html",
            "message": "=<h2>New Client Onboarded</h2>\n<p><strong>Name:</strong> {{ $('Extract Client Data').first().json.client.name }}</p>\n<p><strong>Email:</strong> {{ $('Extract Client Data').first().json.client.email }}</p>\n<p><strong>Company:</strong> {{ $('Extract Client Data').first().json.client.company }}</p>\n<p><strong>Plan:</strong> {{ $('Extract Client Data').first().json.client.plan }}</p>\n<p><strong>Source:</strong> {{ $('Extract Client Data').first().json.client.source }}</p>",
            "options": {},
        },
        "id": uid(),
        "name": "Notify Owner",
        "type": "n8n-nodes-base.gmail",
        "position": [920, 600],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 800],
        "typeVersion": 1,
    })
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "CR-03 ERROR - Onboarding Automation",
            "emailType": "html",
            "message": "=<h2>Onboarding Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 800],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## CR-03: Onboarding Automation\n\n**Trigger:** Webhook POST /client-onboarding\n**Purpose:** Send welcome email, log event, notify owner on new client signup.",
            "height": 160, "width": 420,
        },
        "id": "cr03-note-1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note 1",
    })

    return nodes


def build_cr03_connections():
    """Build connections for the Onboarding Automation workflow."""
    return {
        "Onboarding Webhook": {
            "main": [[{"node": "Extract Client Data", "type": "main", "index": 0}]],
        },
        "Extract Client Data": {
            "main": [[{"node": "Send Welcome Email", "type": "main", "index": 0}]],
        },
        "Send Welcome Email": {
            "main": [[
                {"node": "Log Onboarding Event", "type": "main", "index": 0},
                {"node": "Notify Owner", "type": "main", "index": 0},
            ]],
        },
        "Log Onboarding Event": {
            "main": [[{"node": "Respond Success", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# CR-04: CLIENT SATISFACTION PULSE
# ==================================================================

FILTER_ACTIVE_CLIENTS_CODE = """// Filter active clients, exclude recently contacted (last 14 days)
const input = $input.first().json;
const clients = input.body || input.data || input || [];
const clientList = Array.isArray(clients) ? clients : (clients.clients || []);

const now = new Date();
const fourteenDaysAgo = new Date(now - 14 * 24 * 60 * 60 * 1000);

const activeClients = clientList.filter(c => {
  const isActive = (c.status || '').toLowerCase() === 'active' || c.active === true;
  const lastContacted = c.last_contacted ? new Date(c.last_contacted) : null;
  const notRecentlyContacted = !lastContacted || lastContacted < fourteenDaysAgo;
  return isActive && notRecentlyContacted;
});

return {
  json: {
    clients: activeClients.map(c => ({
      email: c.email || c.client_email || '',
      name: c.name || c.client_name || '',
      company: c.company || '',
      plan: c.plan || 'unknown',
      usage_count: c.usage_count || c.logins_30d || 0,
      features_used: c.features_used || 0,
      health_score: c.health_score || 50,
      last_login: c.last_login || '',
      subscription_start: c.subscription_start || c.created_at || '',
    })),
    total_eligible: activeClients.length,
  }
};"""


def build_cr04_nodes():
    """Build all nodes for the Client Satisfaction Pulse workflow."""
    nodes = []

    # -- Schedule Trigger (Monthly 1st, 10:00 SAST = 08:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 8 1 * *"}]
            }
        },
        "id": uid(),
        "name": "Monthly 1st 10:00 SAST",
        "type": "n8n-nodes-base.scheduleTrigger",
        "position": [200, 400],
        "typeVersion": 1.2,
    })
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "position": [200, 600],
        "typeVersion": 1,
    })

    # -- System Config --
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "todayDate", "value": "={{ $now.toFormat('yyyy-MM-dd') }}", "type": "string"},
                    {"id": uid(), "name": "aiModel", "value": AI_MODEL, "type": "string"},
                    {"id": uid(), "name": "companyName", "value": "AnyVision Media", "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "System Config",
        "type": "n8n-nodes-base.set",
        "position": [440, 400],
        "typeVersion": 3.4,
    })

    # -- Fetch All Clients --
    nodes.append({
        "parameters": {
            "method": "GET",
            "url": f"={PORTAL_BASE_URL}/api/admin/clients",
            "authentication": "none",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Fetch All Clients",
        "type": "n8n-nodes-base.httpRequest",
        "position": [680, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # -- Filter Active Clients --
    nodes.append({
        "parameters": {
            "jsCode": FILTER_ACTIVE_CLIENTS_CODE,
        },
        "id": uid(),
        "name": "Filter Active Clients",
        "type": "n8n-nodes-base.code",
        "position": [920, 400],
        "typeVersion": 2,
    })

    # -- AI Draft Emails --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"{{ $('System Config').first().json.aiModel }}\",\n"
                "  \"max_tokens\": 3000,\n"
                "  \"temperature\": 0.7,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(CLIENT_SATISFACTION_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify('CLIENT DATA: ' + JSON.stringify($json.clients).substring(0, 4000) + '\\n\\nTotal eligible clients: ' + $json.total_eligible) }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 90000},
        },
        "id": uid(),
        "name": "AI Draft Check-in Emails",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1160, 400],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 5000,
    })

    # -- Parse & Send Emails --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const input = $input.first().json;\n"
                "let emails;\n"
                "try {\n"
                "  const content = input.choices[0].message.content;\n"
                "  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();\n"
                "  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);\n"
                "  emails = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);\n"
                "} catch(e) {\n"
                "  return { json: { error: 'Failed to parse AI response', raw: input } };\n"
                "}\n"
                "\n"
                "// Return individual items for loop processing\n"
                "const items = (emails.emails || []).map(e => ({\n"
                "  json: {\n"
                "    client_email: e.client_email,\n"
                "    client_name: e.client_name,\n"
                "    subject: e.subject,\n"
                "    body_html: e.body_html,\n"
                "    tone: e.tone,\n"
                "  }\n"
                "}));\n"
                "\n"
                "return items.length > 0 ? items : [{ json: { error: 'No emails generated' } }];"
            ),
        },
        "id": uid(),
        "name": "Parse AI Emails",
        "type": "n8n-nodes-base.code",
        "position": [1400, 400],
        "typeVersion": 2,
    })

    # -- Send Check-in Email (loops over items) --
    nodes.append({
        "parameters": {
            "sendTo": "={{ $json.client_email }}",
            "subject": "={{ $json.subject }}",
            "emailType": "html",
            "message": "={{ $json.body_html }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Check-in Email",
        "type": "n8n-nodes-base.gmail",
        "position": [1640, 400],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "onError": "continueRegularOutput",
    })

    # -- Log to Events --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_EVENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Event Type": "satisfaction_pulse_sent",
                    "Source": "CR-04",
                    "Details": "={{ JSON.stringify({total_eligible: $('Filter Active Clients').first().json.total_eligible, emails_sent: $input.all().length}) }}",
                    "Created At": "={{ $now.toFormat('yyyy-MM-dd HH:mm:ss') }}",
                },
                "schema": [
                    {"id": "Event Type", "type": "string", "display": True, "displayName": "Event Type"},
                    {"id": "Source", "type": "string", "display": True, "displayName": "Source"},
                    {"id": "Details", "type": "string", "display": True, "displayName": "Details"},
                    {"id": "Created At", "type": "string", "display": True, "displayName": "Created At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log Pulse Event",
        "type": "n8n-nodes-base.airtable",
        "position": [1880, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Error Handling --
    nodes.append({
        "parameters": {},
        "id": uid(),
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "position": [200, 880],
        "typeVersion": 1,
    })
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "CR-04 ERROR - Client Satisfaction Pulse",
            "emailType": "html",
            "message": "=<h2>Satisfaction Pulse Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## CR-04: Client Satisfaction Pulse\n\n**Schedule:** Monthly 1st 10:00 SAST\n**Purpose:** AI-drafted personalized check-in emails to active clients based on usage data.",
            "height": 160, "width": 420,
        },
        "id": "cr04-note-1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note 1",
    })

    return nodes


def build_cr04_connections():
    """Build connections for the Client Satisfaction Pulse workflow."""
    return {
        "Monthly 1st 10:00 SAST": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "System Config", "type": "main", "index": 0}]],
        },
        "System Config": {
            "main": [[{"node": "Fetch All Clients", "type": "main", "index": 0}]],
        },
        "Fetch All Clients": {
            "main": [[{"node": "Filter Active Clients", "type": "main", "index": 0}]],
        },
        "Filter Active Clients": {
            "main": [[{"node": "AI Draft Check-in Emails", "type": "main", "index": 0}]],
        },
        "AI Draft Check-in Emails": {
            "main": [[{"node": "Parse AI Emails", "type": "main", "index": 0}]],
        },
        "Parse AI Emails": {
            "main": [[{"node": "Send Check-in Email", "type": "main", "index": 0}]],
        },
        "Send Check-in Email": {
            "main": [[{"node": "Log Pulse Event", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# WORKFLOW DEFINITIONS & BUILD INFRASTRUCTURE
# ==================================================================

WORKFLOW_DEFS = {
    "cr01": {
        "name": "Client Relations - Health Scorer (CR-01)",
        "build_nodes": lambda: build_cr01_nodes(),
        "build_connections": lambda: build_cr01_connections(),
    },
    "cr02": {
        "name": "Client Relations - Renewal Manager (CR-02)",
        "build_nodes": lambda: build_cr02_nodes(),
        "build_connections": lambda: build_cr02_connections(),
    },
    "cr03": {
        "name": "Client Relations - Onboarding Automation (CR-03)",
        "build_nodes": lambda: build_cr03_nodes(),
        "build_connections": lambda: build_cr03_connections(),
    },
    "cr04": {
        "name": "Client Relations - Satisfaction Pulse (CR-04)",
        "build_nodes": lambda: build_cr04_nodes(),
        "build_connections": lambda: build_cr04_connections(),
    },
}


def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
    if wf_id not in WORKFLOW_DEFS:
        raise ValueError(f"Unknown workflow: {wf_id}. Valid: {', '.join(WORKFLOW_DEFS.keys())}")

    wf_def = WORKFLOW_DEFS[wf_id]
    nodes = wf_def["build_nodes"]()
    connections = wf_def["build_connections"]()

    settings = {
        "executionOrder": "v1",
        "saveManualExecutions": True,
        "callerPolicy": "workflowsFromSameOwner",
    }

    return {
        "name": wf_def["name"],
        "nodes": nodes,
        "connections": connections,
        "settings": settings,
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    filenames = {
        "cr01": "cr01_client_health_scorer.json",
        "cr02": "cr02_renewal_manager.json",
        "cr03": "cr03_onboarding_automation.json",
        "cr04": "cr04_satisfaction_pulse.json",
    }

    output_dir = Path(__file__).parent.parent / "workflows" / "client-relations"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filenames[wf_id]

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

    # Add tools dir to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("=" * 60)
    print("CLIENT RELATIONS - WORKFLOW BUILDER")
    print("=" * 60)

    # Determine which workflows to build
    valid_wfs = list(WORKFLOW_DEFS.keys())
    if target == "all":
        workflow_ids = valid_wfs
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Check Airtable config
    if "REPLACE" in ORCH_BASE_ID:
        print()
        print("WARNING: Airtable IDs not configured!")
        print("  Set these env vars in .env:")
        print("  - ORCH_AIRTABLE_BASE_ID")
        print("  - ORCH_TABLE_ESCALATION_QUEUE, ORCH_TABLE_EVENTS, ORCH_TABLE_DECISION_LOG")
        print()
        if action in ("deploy", "activate"):
            print("Cannot deploy with placeholder IDs. Aborting.")
            sys.exit(1)
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
                    print(f"  Activated!")

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
    print("  1. Open each workflow in n8n UI to verify node connections")
    print("  2. Test webhook endpoints with sample payloads")
    print("  3. Verify Airtable credential has access to orchestrator base")


if __name__ == "__main__":
    main()
