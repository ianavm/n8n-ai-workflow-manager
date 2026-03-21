"""
WhatsApp Agent - Workflow Builder & Deployer

Builds all WhatsApp Agent analytics/integration workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance.

Note: WhatsApp is currently INACTIVE (pending Meta verification), so triggers use
schedule/webhook standins that can be swapped to WhatsApp triggers later.

Workflows:
    WA-01: Conversation Analyzer (Hourly)
    WA-02: CRM Sync (Every 30min)
    WA-03: Issue Detector (Webhook)

Usage:
    python tools/deploy_whatsapp_agent.py build              # Build all workflow JSONs
    python tools/deploy_whatsapp_agent.py build wa01          # Build WA-01 only
    python tools/deploy_whatsapp_agent.py build wa02          # Build WA-02 only
    python tools/deploy_whatsapp_agent.py build wa03          # Build WA-03 only
    python tools/deploy_whatsapp_agent.py deploy              # Build + Deploy (inactive)
    python tools/deploy_whatsapp_agent.py activate            # Build + Deploy + Activate
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

WHATSAPP_BASE_ID = "appzcZpiIZ6QPtJXT"
TABLE_MESSAGE_LOG = "tbl72lkYHRbZHIK4u"
TABLE_CONVERSATION_ANALYTICS = os.getenv("WA_TABLE_CONVERSATION_ANALYTICS", "REPLACE_WITH_TABLE_ID")

ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")
TABLE_ESCALATION_QUEUE = os.getenv("ORCH_TABLE_ESCALATION_QUEUE", "REPLACE_WITH_TABLE_ID")
TABLE_EVENTS = os.getenv("ORCH_TABLE_EVENTS", "REPLACE_WITH_TABLE_ID")

# -- Constants -------------------------------------------------------------

PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://portal.anyvisionmedia.com")
ALERT_EMAIL = "ian@anyvisionmedia.com"
AI_MODEL = "anthropic/claude-sonnet-4-20250514"

# -- AI Prompts ------------------------------------------------------------

ISSUE_CLASSIFIER_PROMPT = """You are an issue classifier for AnyVision Media's WhatsApp support channel, a digital media and AI automation agency in South Africa.

## Your Task
Classify the severity and type of a detected urgent issue from a WhatsApp message.

## Severity Levels
- critical: Service outage, data breach, legal threat, financial loss
- high: Client threatening to leave, billing dispute, broken feature blocking work
- medium: Feature request with urgency, performance complaint, confusion about service
- low: General frustration, minor inconvenience, cosmetic issue

## Issue Types
- service_outage: Something is completely broken/down
- billing: Payment, invoice, subscription issues
- feature_broken: Specific feature not working
- complaint: General dissatisfaction
- churn_risk: Client indicating they want to cancel/leave
- security: Data or access concerns
- other: Doesn't fit above categories

## Output Format (JSON only, no markdown, no backticks):
{
  "severity": "critical|high|medium|low",
  "issue_type": "service_outage|billing|feature_broken|complaint|churn_risk|security|other",
  "summary": "1 sentence summary of the issue",
  "suggested_action": "What should be done immediately",
  "confidence": 0.85,
  "create_support_ticket": true
}

## Rules
- Be conservative: if unsure, classify as higher severity
- Always set create_support_ticket to true for critical/high severity
- South African business context"""


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# WA-01: CONVERSATION ANALYZER
# ==================================================================

CONVERSATION_ANALYTICS_CODE = """// Compute conversation analytics from message log
const messages = $input.all();
const now = new Date();
const twentyFourHoursAgo = new Date(now - 24 * 60 * 60 * 1000);

let totalMessages = 0;
let responseTimes = [];
let sentimentCounts = { positive: 0, neutral: 0, negative: 0 };
let resolvedCount = 0;
let topicCounts = {};
let contactSet = new Set();

for (const item of messages) {
  const fields = item.json.fields || item.json;
  const createdAt = new Date(fields['Created At'] || fields.created_at || now);

  // Only count last 24h
  if (createdAt < twentyFourHoursAgo) continue;

  totalMessages++;
  contactSet.add(fields['Contact'] || fields.contact || fields['From'] || 'unknown');

  // Response time (if available)
  const responseTime = fields['Response Time'] || fields.response_time_seconds || null;
  if (responseTime && typeof responseTime === 'number') {
    responseTimes.push(responseTime);
  }

  // Sentiment
  const sentiment = (fields['Sentiment'] || fields.sentiment || 'neutral').toLowerCase();
  if (sentiment.includes('positive') || sentiment.includes('good')) {
    sentimentCounts.positive++;
  } else if (sentiment.includes('negative') || sentiment.includes('bad') || sentiment.includes('angry')) {
    sentimentCounts.negative++;
  } else {
    sentimentCounts.neutral++;
  }

  // Resolution
  if ((fields['Status'] || fields.status || '').toLowerCase().includes('resolved')) {
    resolvedCount++;
  }

  // Topics
  const topic = fields['Topic'] || fields.topic || fields['Category'] || 'general';
  topicCounts[topic] = (topicCounts[topic] || 0) + 1;
}

const avgResponseTime = responseTimes.length > 0
  ? Math.round(responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length)
  : 0;

const sentimentScore = totalMessages > 0
  ? Math.round(((sentimentCounts.positive * 100 + sentimentCounts.neutral * 50) / totalMessages))
  : 50;

const resolutionRate = totalMessages > 0
  ? Math.round((resolvedCount / totalMessages) * 100)
  : 0;

// Top 5 topics
const topTopics = Object.entries(topicCounts)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 5)
  .map(([topic, count]) => ({ topic, count }));

return {
  json: {
    total_messages: totalMessages,
    unique_contacts: contactSet.size,
    avg_response_time_seconds: avgResponseTime,
    sentiment_distribution: sentimentCounts,
    sentiment_score: sentimentScore,
    resolution_rate: resolutionRate,
    resolved_count: resolvedCount,
    top_topics: topTopics,
    analyzed_at: now.toISOString(),
    period: '24h',
  }
};"""


PER_AGENT_ANALYTICS_CODE = """// Break down analytics by agent_id for daily report
const messages = $('Read Message Log').all();
const now = new Date();
const twentyFourHoursAgo = new Date(now - 24 * 60 * 60 * 1000);
const agents = {};

for (const item of messages) {
  const f = item.json.fields || item.json;
  const createdAt = new Date(f['Created At'] || f.created_at || now);
  if (createdAt < twentyFourHoursAgo) continue;

  const agentId = f.agent_id || f['Agent ID'] || 'unknown';
  if (!agents[agentId]) {
    agents[agentId] = { total: 0, inbound: 0, outbound: 0, handoffs: 0, errors: 0, leads: 0 };
  }
  agents[agentId].total++;

  const dir = (f.direction || f['Direction'] || '').toLowerCase();
  if (dir === 'inbound') agents[agentId].inbound++;
  if (dir === 'outbound') agents[agentId].outbound++;

  if (f.handoff_triggered || f['Handoff Triggered']) agents[agentId].handoffs++;
  if ((f.response_type || f['Response Type'] || '') === 'handoff') agents[agentId].handoffs++;
}

// Build text report
let report = '';
for (const [id, stats] of Object.entries(agents)) {
  const responseRate = stats.inbound > 0 ? Math.round((stats.outbound / stats.inbound) * 100) : 0;
  const handoffRate = stats.total > 0 ? Math.round((stats.handoffs / stats.total) * 100) : 0;
  report += id + ':\\n';
  report += '  Messages: ' + stats.total + ' (in: ' + stats.inbound + ', out: ' + stats.outbound + ')\\n';
  report += '  Response rate: ' + responseRate + '%\\n';
  report += '  Handoff rate: ' + handoffRate + '%\\n\\n';
}

if (!report) report = 'No messages in last 24 hours.';

// Compute Johannesburg hour for daily email check
const joburg = new Date(new Date().toLocaleString('en-US', {timeZone: 'Africa/Johannesburg'}));
const hourJoburg = joburg.getHours();

return { json: { agents, report, agent_count: Object.keys(agents).length, hour_joburg: hourJoburg } };"""


def build_wa01_nodes():
    """Build all nodes for the Conversation Analyzer workflow."""
    nodes = []

    # -- Schedule Trigger (hourly) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 * * * *"}]
            }
        },
        "id": uid(),
        "name": "Hourly Trigger",
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

    # -- Read Message Log (last 24h) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": WHATSAPP_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_MESSAGE_LOG, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Created At}, DATEADD(NOW(), -24, 'hours'))",
        },
        "id": uid(),
        "name": "Read Message Log",
        "type": "n8n-nodes-base.airtable",
        "position": [440, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # -- Compute Analytics --
    nodes.append({
        "parameters": {
            "jsCode": CONVERSATION_ANALYTICS_CODE,
        },
        "id": uid(),
        "name": "Compute Analytics",
        "type": "n8n-nodes-base.code",
        "position": [680, 400],
        "typeVersion": 2,
    })

    # -- Set Structured Output --
    nodes.append({
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "period", "value": "={{ $json.period }}", "type": "string"},
                    {"id": uid(), "name": "total_messages", "value": "={{ $json.total_messages }}", "type": "number"},
                    {"id": uid(), "name": "unique_contacts", "value": "={{ $json.unique_contacts }}", "type": "number"},
                    {"id": uid(), "name": "avg_response_time", "value": "={{ $json.avg_response_time_seconds }}", "type": "number"},
                    {"id": uid(), "name": "sentiment_score", "value": "={{ $json.sentiment_score }}", "type": "number"},
                    {"id": uid(), "name": "resolution_rate", "value": "={{ $json.resolution_rate }}", "type": "number"},
                    {"id": uid(), "name": "top_topics", "value": "={{ JSON.stringify($json.top_topics) }}", "type": "string"},
                    {"id": uid(), "name": "analyzed_at", "value": "={{ $json.analyzed_at }}", "type": "string"},
                ]
            },
        },
        "id": uid(),
        "name": "Structure Output",
        "type": "n8n-nodes-base.set",
        "position": [920, 400],
        "typeVersion": 3.4,
    })

    # -- Create Analytics Record --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": WHATSAPP_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CONVERSATION_ANALYTICS, "mode": "id"},
            "columns": {
                "value": {
                    "Period": "={{ $('Compute Analytics').first().json.period }}",
                    "Total Messages": "={{ $('Compute Analytics').first().json.total_messages }}",
                    "Unique Contacts": "={{ $('Compute Analytics').first().json.unique_contacts }}",
                    "Avg Response Time": "={{ $('Compute Analytics').first().json.avg_response_time_seconds }}",
                    "Sentiment Score": "={{ $('Compute Analytics').first().json.sentiment_score }}",
                    "Resolution Rate": "={{ $('Compute Analytics').first().json.resolution_rate }}",
                    "Top Topics": "={{ JSON.stringify($('Compute Analytics').first().json.top_topics) }}",
                    "Analyzed At": "={{ $('Compute Analytics').first().json.analyzed_at }}",
                },
                "schema": [
                    {"id": "Period", "type": "string", "display": True, "displayName": "Period"},
                    {"id": "Total Messages", "type": "number", "display": True, "displayName": "Total Messages"},
                    {"id": "Unique Contacts", "type": "number", "display": True, "displayName": "Unique Contacts"},
                    {"id": "Avg Response Time", "type": "number", "display": True, "displayName": "Avg Response Time"},
                    {"id": "Sentiment Score", "type": "number", "display": True, "displayName": "Sentiment Score"},
                    {"id": "Resolution Rate", "type": "number", "display": True, "displayName": "Resolution Rate"},
                    {"id": "Top Topics", "type": "string", "display": True, "displayName": "Top Topics"},
                    {"id": "Analyzed At", "type": "string", "display": True, "displayName": "Analyzed At"},
                ],
                "mappingMode": "defineBelow",
            },
            "options": {},
        },
        "id": uid(),
        "name": "Save Analytics",
        "type": "n8n-nodes-base.airtable",
        "position": [1160, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- If Poor Metrics --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "combinator": "or",
                "conditions": [
                    {
                        "leftValue": "={{ $('Compute Analytics').first().json.sentiment_score }}",
                        "rightValue": 50,
                        "operator": {"type": "number", "operation": "lt"},
                    },
                    {
                        "leftValue": "={{ $('Compute Analytics').first().json.resolution_rate }}",
                        "rightValue": 70,
                        "operator": {"type": "number", "operation": "lt"},
                    },
                ],
            },
        },
        "id": uid(),
        "name": "Poor Metrics?",
        "type": "n8n-nodes-base.if",
        "position": [1400, 400],
        "typeVersion": 2.2,
    })

    # -- Create Escalation --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ESCALATION_QUEUE, "mode": "id"},
            "columns": {
                "value": {
                    "Category": "WhatsApp_Quality_Alert",
                    "Source Workflow": "WA-01 Conversation Analyzer",
                    "Priority": "High",
                    "Description": "=WhatsApp metrics below threshold - Sentiment: {{ $('Compute Analytics').first().json.sentiment_score }}/100, Resolution: {{ $('Compute Analytics').first().json.resolution_rate }}%",
                    "Details": "={{ JSON.stringify($('Compute Analytics').first().json) }}",
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
        "name": "Escalate Poor Metrics",
        "type": "n8n-nodes-base.airtable",
        "position": [1640, 300],
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
            "subject": "WA-01 ERROR - Conversation Analyzer",
            "emailType": "html",
            "message": "=<h2>Conversation Analyzer Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
            "options": {},
        },
        "id": uid(),
        "name": "Error Notification",
        "type": "n8n-nodes-base.gmail",
        "position": [440, 880],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Per-Agent Breakdown (Code node) --
    nodes.append({
        "parameters": {
            "jsCode": PER_AGENT_ANALYTICS_CODE,
        },
        "id": uid(),
        "name": "Per-Agent Breakdown",
        "type": "n8n-nodes-base.code",
        "position": [1640, 600],
        "typeVersion": 2,
    })

    # -- Check If Daily Email Time (07:00 SAST = only run email at 7am) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.hour_joburg }}",
                        "rightValue": 7,
                        "operator": {"type": "number", "operation": "equals"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Is 7AM?",
        "type": "n8n-nodes-base.if",
        "position": [1880, 600],
        "typeVersion": 2.2,
    })

    # -- Daily Email Summary --
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=WhatsApp AI Pilot - Daily Report ({{ $now.setZone('Africa/Johannesburg').toFormat('dd MMM yyyy') }})",
            "emailType": "html",
            "message": (
                "=<h2>WhatsApp AI Pilot - Daily Summary</h2>"
                "<p><strong>Period:</strong> Last 24 hours</p>"
                "<p><strong>Total Messages:</strong> {{ $('Compute Analytics').first().json.total_messages }}</p>"
                "<p><strong>Unique Contacts:</strong> {{ $('Compute Analytics').first().json.unique_contacts }}</p>"
                "<p><strong>Sentiment Score:</strong> {{ $('Compute Analytics').first().json.sentiment_score }}/100</p>"
                "<p><strong>Resolution Rate:</strong> {{ $('Compute Analytics').first().json.resolution_rate }}%</p>"
                "<hr>"
                "<h3>Per-Agent Breakdown</h3>"
                "<pre>{{ $('Per-Agent Breakdown').first().json.report }}</pre>"
                "<hr>"
                "<p><a href=\"https://portal.anyvisionmedia.com/admin/agents\">View Agent Dashboard</a></p>"
            ),
            "options": {},
        },
        "id": uid(),
        "name": "Daily Email Summary",
        "type": "n8n-nodes-base.gmail",
        "position": [2120, 500],
        "typeVersion": 2.1,
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "continueOnFail": True,
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## WA-01: Conversation Analyzer\n\n**Schedule:** Hourly\n**Purpose:** Compute WhatsApp analytics (messages, response time, sentiment, resolution rate, topics). Escalate if metrics drop.\n\n**Pilot addition:** Daily 07:00 email with per-agent breakdown.",
            "height": 180, "width": 420,
        },
        "id": "wa01-note-1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note 1",
    })

    return nodes


def build_wa01_connections():
    """Build connections for the Conversation Analyzer workflow."""
    return {
        "Hourly Trigger": {
            "main": [[{"node": "Read Message Log", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "Read Message Log", "type": "main", "index": 0}]],
        },
        "Read Message Log": {
            "main": [[{"node": "Compute Analytics", "type": "main", "index": 0}]],
        },
        "Compute Analytics": {
            "main": [[{"node": "Structure Output", "type": "main", "index": 0}]],
        },
        "Structure Output": {
            "main": [[{"node": "Save Analytics", "type": "main", "index": 0}]],
        },
        "Save Analytics": {
            "main": [[
                {"node": "Poor Metrics?", "type": "main", "index": 0},
                {"node": "Per-Agent Breakdown", "type": "main", "index": 0},
            ]],
        },
        "Poor Metrics?": {
            "main": [
                [{"node": "Escalate Poor Metrics", "type": "main", "index": 0}],
                [],
            ],
        },
        "Per-Agent Breakdown": {
            "main": [[{"node": "Is 7AM?", "type": "main", "index": 0}]],
        },
        "Is 7AM?": {
            "main": [
                [{"node": "Daily Email Summary", "type": "main", "index": 0}],
                [],
            ],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# WA-02: CRM SYNC
# ==================================================================

EXTRACT_CONTACTS_CODE = """// Extract unique new contacts from message log (last 2h)
const messages = $input.all();
const now = new Date();
const twoHoursAgo = new Date(now - 2 * 60 * 60 * 1000);
const contactMap = {};

for (const item of messages) {
  const fields = item.json.fields || item.json;
  const createdAt = new Date(fields['Created At'] || fields.created_at || now);

  if (createdAt < twoHoursAgo) continue;

  const contact = fields['Contact'] || fields.contact || fields['From'] || '';
  const name = fields['Contact Name'] || fields.contact_name || '';
  const phone = fields['Phone'] || fields.phone || contact;

  if (!contact || contactMap[contact]) continue;

  contactMap[contact] = {
    contact_id: contact,
    name: name,
    phone: phone,
    first_message_at: createdAt.toISOString(),
    message_count: 1,
  };
}

// Deduplicate
const uniqueContacts = Object.values(contactMap);

return {
  json: {
    contacts: uniqueContacts,
    total_new: uniqueContacts.length,
    sync_at: now.toISOString(),
  }
};"""


def build_wa02_nodes():
    """Build all nodes for the CRM Sync workflow."""
    nodes = []

    # -- Schedule Trigger (every 30 min) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "*/30 * * * *"}]
            }
        },
        "id": uid(),
        "name": "Every 30min",
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

    # -- Read Message Log (new contacts last 2h) --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": WHATSAPP_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_MESSAGE_LOG, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Created At}, DATEADD(NOW(), -2, 'hours'))",
        },
        "id": uid(),
        "name": "Read Recent Messages",
        "type": "n8n-nodes-base.airtable",
        "position": [440, 400],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
        "onError": "continueRegularOutput",
    })

    # -- Extract Unique Contacts --
    nodes.append({
        "parameters": {
            "jsCode": EXTRACT_CONTACTS_CODE,
        },
        "id": uid(),
        "name": "Extract Contacts",
        "type": "n8n-nodes-base.code",
        "position": [680, 400],
        "typeVersion": 2,
    })

    # -- Update Agent Status --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"={PORTAL_BASE_URL}/api/admin/agents",
            "authentication": "none",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({agent: 'agent_whatsapp', status: 'healthy', last_run: $now.toFormat('yyyy-MM-dd HH:mm:ss'), metrics: {new_contacts: $json.total_new, sync_at: $json.sync_at}}) }}",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Update Agent Status",
        "type": "n8n-nodes-base.httpRequest",
        "position": [920, 400],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Prepare Lead Items --
    nodes.append({
        "parameters": {
            "jsCode": (
                "const contacts = $('Extract Contacts').first().json.contacts || [];\n"
                "if (contacts.length === 0) {\n"
                "  return { json: { skip: true, message: 'No new contacts' } };\n"
                "}\n"
                "return contacts.map(c => ({\n"
                "  json: {\n"
                "    contact_id: c.contact_id,\n"
                "    name: c.name,\n"
                "    phone: c.phone,\n"
                "    source: 'whatsapp',\n"
                "    first_message_at: c.first_message_at,\n"
                "  }\n"
                "}));"
            ),
        },
        "id": uid(),
        "name": "Prepare Lead Items",
        "type": "n8n-nodes-base.code",
        "position": [1160, 400],
        "typeVersion": 2,
    })

    # -- Post Lead Created --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": f"={PORTAL_BASE_URL}/api/stats/lead-created",
            "authentication": "none",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({contact_id: $json.contact_id, name: $json.name, phone: $json.phone, source: 'whatsapp', first_message_at: $json.first_message_at}) }}",
            "options": {"timeout": 15000},
        },
        "id": uid(),
        "name": "Post Lead Created",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1400, 400],
        "typeVersion": 4.2,
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
            "subject": "WA-02 ERROR - CRM Sync",
            "emailType": "html",
            "message": "=<h2>CRM Sync Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
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
            "content": "## WA-02: CRM Sync\n\n**Schedule:** Every 30 minutes\n**Purpose:** Extract new WhatsApp contacts, update portal agent status, create lead records.",
            "height": 160, "width": 420,
        },
        "id": "wa02-note-1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note 1",
    })

    return nodes


def build_wa02_connections():
    """Build connections for the CRM Sync workflow."""
    return {
        "Every 30min": {
            "main": [[{"node": "Read Recent Messages", "type": "main", "index": 0}]],
        },
        "Manual Trigger": {
            "main": [[{"node": "Read Recent Messages", "type": "main", "index": 0}]],
        },
        "Read Recent Messages": {
            "main": [[{"node": "Extract Contacts", "type": "main", "index": 0}]],
        },
        "Extract Contacts": {
            "main": [[{"node": "Update Agent Status", "type": "main", "index": 0}]],
        },
        "Update Agent Status": {
            "main": [[{"node": "Prepare Lead Items", "type": "main", "index": 0}]],
        },
        "Prepare Lead Items": {
            "main": [[{"node": "Post Lead Created", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# WA-03: ISSUE DETECTOR
# ==================================================================

SCAN_URGENCY_CODE = """// Scan message for urgency keywords
const body = $json.body || $json;
const message = (body.message || body.text || body.body || '').toLowerCase();
const contact = body.contact || body.from || body.phone || '';
const contactName = body.contact_name || body.name || '';

const urgencyKeywords = [
  'complaint', 'urgent', 'problem', 'refund', 'angry', 'help',
  'broken', 'cancel', 'furious', 'unacceptable', 'terrible',
  'not working', 'down', 'error', 'fail', 'frustrated',
  'disappointed', 'worst', 'scam', 'lawyer', 'legal',
];

const foundKeywords = urgencyKeywords.filter(kw => message.includes(kw));
const isUrgent = foundKeywords.length > 0;
const urgencyScore = Math.min(100, foundKeywords.length * 20);

return {
  json: {
    message: body.message || body.text || body.body || '',
    contact: contact,
    contact_name: contactName,
    is_urgent: isUrgent,
    urgency_score: urgencyScore,
    found_keywords: foundKeywords,
    scanned_at: new Date().toISOString(),
  }
};"""

PARSE_ISSUE_CODE = """// Parse AI issue classification
const input = $input.first().json;
const scanData = $('Scan Urgency').first().json;

let classification;
try {
  const content = input.choices[0].message.content;
  const cleaned = content.replace(/```json\\n?/g, '').replace(/```\\n?/g, '').trim();
  const jsonMatch = cleaned.match(/\\{[\\s\\S]*\\}/);
  classification = JSON.parse(jsonMatch ? jsonMatch[0] : cleaned);
} catch(e) {
  classification = {
    severity: 'medium',
    issue_type: 'complaint',
    summary: 'Urgent message detected with keywords: ' + scanData.found_keywords.join(', '),
    suggested_action: 'Manual review required',
    confidence: 0.0,
    create_support_ticket: true,
  };
}

return {
  json: {
    scan: scanData,
    classification: classification,
  }
};"""


def build_wa03_nodes():
    """Build all nodes for the Issue Detector workflow."""
    nodes = []

    # -- Webhook Trigger --
    nodes.append({
        "parameters": {
            "path": "whatsapp-issue-detect",
            "httpMethod": "POST",
            "responseMode": "responseNode",
            "options": {},
        },
        "id": uid(),
        "name": "Issue Detect Webhook",
        "type": "n8n-nodes-base.webhook",
        "position": [200, 400],
        "typeVersion": 2,
        "webhookId": uid(),
    })

    # -- Scan Urgency Keywords --
    nodes.append({
        "parameters": {
            "jsCode": SCAN_URGENCY_CODE,
        },
        "id": uid(),
        "name": "Scan Urgency",
        "type": "n8n-nodes-base.code",
        "position": [440, 400],
        "typeVersion": 2,
    })

    # -- If Urgent --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [
                    {
                        "leftValue": "={{ $json.is_urgent }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Is Urgent?",
        "type": "n8n-nodes-base.if",
        "position": [680, 400],
        "typeVersion": 2.2,
    })

    # -- AI Classify Issue (true branch) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={\n"
                "  \"model\": \"" + AI_MODEL + "\",\n"
                "  \"max_tokens\": 500,\n"
                "  \"temperature\": 0.3,\n"
                "  \"messages\": [\n"
                "    {\n"
                "      \"role\": \"system\",\n"
                f"      \"content\": {json.dumps(ISSUE_CLASSIFIER_PROMPT)}\n"
                "    },\n"
                "    {\n"
                "      \"role\": \"user\",\n"
                "      \"content\": {{ JSON.stringify('MESSAGE: ' + $json.message + '\\n\\nCONTACT: ' + $json.contact + '\\n\\nURGENCY KEYWORDS FOUND: ' + $json.found_keywords.join(', ') + '\\nURGENCY SCORE: ' + $json.urgency_score + '/100') }}\n"
                "    }\n"
                "  ]\n"
                "}",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "AI Classify Issue",
        "type": "n8n-nodes-base.httpRequest",
        "position": [920, 300],
        "typeVersion": 4.2,
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    })

    # -- Parse Issue Classification --
    nodes.append({
        "parameters": {
            "jsCode": PARSE_ISSUE_CODE,
        },
        "id": uid(),
        "name": "Parse Issue",
        "type": "n8n-nodes-base.code",
        "position": [1160, 300],
        "typeVersion": 2,
    })

    # -- Create Support Ticket via webhook --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "={{ $env.N8N_BASE_URL || 'https://ianimmelman89.app.n8n.cloud' }}/webhook/support-ticket",
            "authentication": "none",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({email: $json.scan.contact, subject: 'WhatsApp Issue: ' + $json.classification.summary, body: $json.scan.message, source: 'whatsapp_issue_detector', severity: $json.classification.severity, issue_type: $json.classification.issue_type}) }}",
            "options": {"timeout": 30000},
        },
        "id": uid(),
        "name": "Create Support Ticket",
        "type": "n8n-nodes-base.httpRequest",
        "position": [1400, 300],
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
    })

    # -- Create Escalation --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ESCALATION_QUEUE, "mode": "id"},
            "columns": {
                "value": {
                    "Category": "WhatsApp_Urgent_Issue",
                    "Source Workflow": "WA-03 Issue Detector",
                    "Priority": "={{ $('Parse Issue').first().json.classification.severity === 'critical' ? 'Critical' : 'High' }}",
                    "Description": "={{ $('Parse Issue').first().json.classification.summary }}",
                    "Details": "={{ JSON.stringify({contact: $('Parse Issue').first().json.scan.contact, severity: $('Parse Issue').first().json.classification.severity, issue_type: $('Parse Issue').first().json.classification.issue_type, keywords: $('Parse Issue').first().json.scan.found_keywords}) }}",
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
        "name": "Escalate Issue",
        "type": "n8n-nodes-base.airtable",
        "position": [1400, 500],
        "typeVersion": 2.1,
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "onError": "continueRegularOutput",
    })

    # -- Respond to Webhook (urgent path) --
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({success: true, urgent: true, severity: $('Parse Issue').first().json.classification.severity, issue_type: $('Parse Issue').first().json.classification.issue_type, keywords_found: $('Scan Urgency').first().json.found_keywords}) }}",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Urgent",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [1640, 400],
        "typeVersion": 1.1,
    })

    # -- Respond Not Urgent (false branch) --
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({success: true, urgent: false, message: 'No urgency detected'}) }}",
            "options": {},
        },
        "id": uid(),
        "name": "Respond Not Urgent",
        "type": "n8n-nodes-base.respondToWebhook",
        "position": [920, 550],
        "typeVersion": 1.1,
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
            "subject": "WA-03 ERROR - Issue Detector",
            "emailType": "html",
            "message": "=<h2>Issue Detector Error</h2>\n<p><strong>Workflow:</strong> {{ $json.workflow.name }}</p>\n<p><strong>Error:</strong> {{ $json.execution.error.message }}</p>\n<p><strong>Node:</strong> {{ $json.execution.lastNodeExecuted }}</p>\n<p><a href=\"{{ $json.execution.url }}\">View Execution</a></p>",
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
            "content": "## WA-03: Issue Detector\n\n**Trigger:** Webhook POST /whatsapp-issue-detect\n**Purpose:** Scan WhatsApp messages for urgency, AI-classify issues, create support tickets, escalate.",
            "height": 160, "width": 420,
        },
        "id": "wa03-note-1",
        "type": "n8n-nodes-base.stickyNote",
        "position": [140, 220],
        "typeVersion": 1,
        "name": "Note 1",
    })

    return nodes


def build_wa03_connections():
    """Build connections for the Issue Detector workflow."""
    return {
        "Issue Detect Webhook": {
            "main": [[{"node": "Scan Urgency", "type": "main", "index": 0}]],
        },
        "Scan Urgency": {
            "main": [[{"node": "Is Urgent?", "type": "main", "index": 0}]],
        },
        "Is Urgent?": {
            "main": [
                [{"node": "AI Classify Issue", "type": "main", "index": 0}],
                [{"node": "Respond Not Urgent", "type": "main", "index": 0}],
            ],
        },
        "AI Classify Issue": {
            "main": [[{"node": "Parse Issue", "type": "main", "index": 0}]],
        },
        "Parse Issue": {
            "main": [[
                {"node": "Create Support Ticket", "type": "main", "index": 0},
                {"node": "Escalate Issue", "type": "main", "index": 0},
            ]],
        },
        "Create Support Ticket": {
            "main": [[{"node": "Respond Urgent", "type": "main", "index": 0}]],
        },
        "Error Trigger": {
            "main": [[{"node": "Error Notification", "type": "main", "index": 0}]],
        },
    }


# ==================================================================
# WORKFLOW DEFINITIONS & BUILD INFRASTRUCTURE
# ==================================================================

WORKFLOW_DEFS = {
    "wa01": {
        "name": "WhatsApp Agent - Conversation Analyzer (WA-01)",
        "build_nodes": lambda: build_wa01_nodes(),
        "build_connections": lambda: build_wa01_connections(),
    },
    "wa02": {
        "name": "WhatsApp Agent - CRM Sync (WA-02)",
        "build_nodes": lambda: build_wa02_nodes(),
        "build_connections": lambda: build_wa02_connections(),
    },
    "wa03": {
        "name": "WhatsApp Agent - Issue Detector (WA-03)",
        "build_nodes": lambda: build_wa03_nodes(),
        "build_connections": lambda: build_wa03_connections(),
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
        "wa01": "wa01_conversation_analyzer.json",
        "wa02": "wa02_crm_sync.json",
        "wa03": "wa03_issue_detector.json",
    }

    output_dir = Path(__file__).parent.parent / "workflows" / "whatsapp-agent"
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
    print("WHATSAPP AGENT - WORKFLOW BUILDER")
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
    print("  1. Set WA_TABLE_CONVERSATION_ANALYTICS in .env (or create table)")
    print("  2. Open each workflow in n8n UI to verify node connections")
    print("  3. Test WA-03 webhook: curl -X POST .../webhook/whatsapp-issue-detect -d '{\"message\":\"This is urgent, my service is broken\",\"contact\":\"27821234567\"}'")


if __name__ == "__main__":
    main()
