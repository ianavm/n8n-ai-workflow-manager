"""
AVM Support Agent - Workflow Builder & Deployer

Builds 4 support workflows for ticket management, SLA monitoring,
auto-resolution, and knowledge base generation.

Workflows:
    SUP-01: Ticket Creator       (Webhook) - Classify, summarize, create ticket, auto-resolve or notify
    SUP-02: SLA Monitor          (Every 15 min, 08:00-17:00 SAST) - Check deadlines, warn/escalate
    SUP-03: Auto-Resolver        (Sub-workflow, webhook) - KB search + AI draft + confidence gate
    SUP-04: KB Builder           (Sun 20:00 SAST = 18:00 UTC) - Generate KB articles from resolved tickets

Usage:
    python tools/deploy_support_agent.py build              # Build all JSONs
    python tools/deploy_support_agent.py build sup01         # Build SUP-01 only
    python tools/deploy_support_agent.py deploy              # Build + Deploy (inactive)
    python tools/deploy_support_agent.py activate            # Build + Deploy + Activate
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
SUPPORT_BASE_ID = os.getenv("SUPPORT_AIRTABLE_BASE_ID", "REPLACE_AFTER_SETUP")
TABLE_TICKETS = os.getenv("SUPPORT_TABLE_TICKETS", "REPLACE_AFTER_SETUP")
TABLE_KNOWLEDGE_BASE = os.getenv("SUPPORT_TABLE_KNOWLEDGE_BASE", "REPLACE_AFTER_SETUP")
TABLE_SLA_CONFIG = os.getenv("SUPPORT_TABLE_SLA_CONFIG", "REPLACE_AFTER_SETUP")

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"


def uid():
    return str(uuid.uuid4())


def airtable_ref(base, table):
    return {"base": {"__rl": True, "value": base, "mode": "id"},
            "table": {"__rl": True, "value": table, "mode": "id"}}


def ai_call(system_prompt, user_expr, max_tokens=800):
    """Build an httpRequest node dict for OpenRouter AI call."""
    return {
        "method": "POST",
        "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={"model":"' + OPENROUTER_MODEL + '","max_tokens":' + str(max_tokens) + ',"messages":[{"role":"system","content":"' + system_prompt.replace('"', '\\"').replace('\n', '\\n') + '"},{"role":"user","content":"' + user_expr + '"}]}',
        "options": {},
    }


# ======================================================================
# SUP-01: Ticket Creator
# ======================================================================

def build_sup01_nodes():
    nodes = []

    # 1. Webhook
    nodes.append({"parameters": {"path": "support-ticket", "responseMode": "responseNode", "options": {}},
                   "id": uid(), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                   "position": [220, 300], "webhookId": uid()})

    # 2. Parse Input (Code)
    nodes.append({"parameters": {"jsCode": """const body = $input.first().json.body || $input.first().json;
return { json: {
  ticket_id: 'TKT-' + Date.now().toString(36).toUpperCase(),
  client_email: body.client_email || body.from || body.email || '',
  client_id: body.client_id || '',
  subject: body.subject || body.title || 'No subject',
  body: body.body || body.message || body.text || '',
  received_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Parse Input", "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [440, 300]})

    # 3. AI Classify + Summarize
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 800,
  "messages": [
    {"role": "system", "content": "You are a support ticket classifier. Output JSON: {priority: P1/P2/P3/P4, summary: string, suggestion: string, auto_resolvable: bool, confidence: 0-1}. P1=system down, P2=major issue, P3=minor, P4=question."},
    {"role": "user", "content": "Subject: {{ $json.subject }}\\nBody: {{ $json.body }}\\nClient: {{ $json.client_email }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Classify Ticket",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [660, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 4. Extract Classification (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let c = {};
try { c = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { c = {priority:'P3',summary:'Parse failed',suggestion:'Manual review',auto_resolvable:false,confidence:0}; }
const parsed = $('Parse Input').first().json;
const slaH = {P1:4,P2:8,P3:24,P4:168};
const deadline = new Date(Date.now() + (slaH[c.priority]||24)*3600000);
return { json: { ticket_id: parsed.ticket_id, client_id: parsed.client_id, client_email: parsed.client_email,
  subject: parsed.subject, body: parsed.body, priority: c.priority||'P3', status: 'Open',
  ai_summary: c.summary||'', ai_suggestion: c.suggestion||'', sla_deadline: deadline.toISOString(),
  created_at: new Date().toISOString(), auto_resolvable: c.auto_resolvable||false, confidence: c.confidence||0 }};"""},
                   "id": uid(), "name": "Extract Classification",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [880, 300]})

    # 5. Create Ticket (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(SUPPORT_BASE_ID, TABLE_TICKETS),
        "columns": {"value": {"ticket_id": "={{ $json.ticket_id }}", "client_id": "={{ $json.client_id }}",
            "client_email": "={{ $json.client_email }}", "subject": "={{ $json.subject }}",
            "body": "={{ $json.body }}", "priority": "={{ $json.priority }}", "status": "Open",
            "ai_summary": "={{ $json.ai_summary }}", "ai_suggestion": "={{ $json.ai_suggestion }}",
            "sla_deadline": "={{ $json.sla_deadline }}", "created_at": "={{ $json.created_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Create Ticket",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1100, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 6. Switch: auto-resolvable? confidence > 0.85
    nodes.append({"parameters": {"rules": {"values": [
        {"conditions": {"conditions": [
            {"leftValue": "={{ $('Extract Classification').first().json.auto_resolvable }}", "rightValue": True,
             "operator": {"type": "boolean", "operation": "equals"}},
            {"leftValue": "={{ $('Extract Classification').first().json.confidence }}", "rightValue": 0.85,
             "operator": {"type": "number", "operation": "gt"}}]},
         "outputKey": "auto_resolve"},
        {"conditions": {"conditions": [
            {"leftValue": True, "rightValue": True,
             "operator": {"type": "boolean", "operation": "equals"}}]},
         "outputKey": "manual"}]}, "options": {}},
                   "id": uid(), "name": "Auto-Resolvable?",
                   "type": "n8n-nodes-base.switch", "typeVersion": 3.2, "position": [1320, 300]})

    # 7. AI Draft Response
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 600,
  "messages": [
    {"role": "system", "content": "Draft a professional support email response. Use the AI suggestion as guide. Sign off as AnyVision Media Support Team."},
    {"role": "user", "content": "Ticket: {{ $('Extract Classification').first().json.ticket_id }}\\nSubject: {{ $('Extract Classification').first().json.subject }}\\nBody: {{ $('Extract Classification').first().json.body }}\\nSuggestion: {{ $('Extract Classification').first().json.ai_suggestion }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Draft Response",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [1560, 180], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 8. Send Auto-Response (Gmail)
    nodes.append({"parameters": {
        "sendTo": "={{ $('Extract Classification').first().json.client_email }}",
        "subject": "=Re: {{ $('Extract Classification').first().json.subject }} [{{ $('Extract Classification').first().json.ticket_id }}]",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">AnyVision Media Support</h2></div>
<div style="padding:20px"><p>Ticket: <strong>{{ $('Extract Classification').first().json.ticket_id }}</strong></p>
<div style="white-space:pre-wrap">{{ $json.choices[0].message.content }}</div></div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">Automated response. Reply if you need further help.</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Send Auto-Response",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1780, 180], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 9. Notify Support Team (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=[{{ $('Extract Classification').first().json.priority }}] {{ $('Extract Classification').first().json.subject }}",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">New Support Ticket</h2></div>
<div style="padding:20px">
<p><b>Ticket:</b> {{ $('Extract Classification').first().json.ticket_id }}</p>
<p><b>Priority:</b> {{ $('Extract Classification').first().json.priority }}</p>
<p><b>Client:</b> {{ $('Extract Classification').first().json.client_email }}</p>
<p><b>Subject:</b> {{ $('Extract Classification').first().json.subject }}</p>
<h3>AI Summary</h3><p>{{ $('Extract Classification').first().json.ai_summary }}</p>
<h3>AI Suggestion</h3><p>{{ $('Extract Classification').first().json.ai_suggestion }}</p>
<p><b>SLA Deadline:</b> {{ $('Extract Classification').first().json.sla_deadline }}</p></div></div>""",
        "options": {}},
                   "id": uid(), "name": "Notify Support Team",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1560, 420], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 10. Respond Webhook
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": "={{ JSON.stringify({success:true, ticket_id:$('Extract Classification').first().json.ticket_id, priority:$('Extract Classification').first().json.priority}) }}",
        "options": {}},
                   "id": uid(), "name": "Respond Webhook",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [2000, 300]})

    return nodes


def build_sup01_connections(nodes):
    return {
        "Webhook": {"main": [[{"node": "Parse Input", "type": "main", "index": 0}]]},
        "Parse Input": {"main": [[{"node": "AI Classify Ticket", "type": "main", "index": 0}]]},
        "AI Classify Ticket": {"main": [[{"node": "Extract Classification", "type": "main", "index": 0}]]},
        "Extract Classification": {"main": [[{"node": "Create Ticket", "type": "main", "index": 0}]]},
        "Create Ticket": {"main": [[{"node": "Auto-Resolvable?", "type": "main", "index": 0}]]},
        "Auto-Resolvable?": {"main": [
            [{"node": "AI Draft Response", "type": "main", "index": 0}],
            [{"node": "Notify Support Team", "type": "main", "index": 0}],
        ]},
        "AI Draft Response": {"main": [[{"node": "Send Auto-Response", "type": "main", "index": 0}]]},
        "Send Auto-Response": {"main": [[{"node": "Respond Webhook", "type": "main", "index": 0}]]},
        "Notify Support Team": {"main": [[{"node": "Respond Webhook", "type": "main", "index": 0}]]},
    }


# ======================================================================
# SUP-02: SLA Monitor
# ======================================================================

def build_sup02_nodes():
    nodes = []

    # 1. Schedule Trigger (every 15 min, business hours: */15 6-15 * * 1-5 UTC = 08-17 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "*/15 6-15 * * 1-5"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Read Open Tickets
    nodes.append({"parameters": {"operation": "search", **airtable_ref(SUPPORT_BASE_ID, TABLE_TICKETS),
        "filterByFormula": "=AND({status} != 'Resolved', {status} != 'Closed')", "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Open Tickets",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [440, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Check SLA Deadlines (Code)
    nodes.append({"parameters": {"jsCode": """const tickets = $('Read Open Tickets').all();
const now = new Date();
const results = [];
for (const item of tickets) {
  const t = item.json;
  const deadline = t.sla_deadline ? new Date(t.sla_deadline) : null;
  if (!deadline) { results.push({json:{...t, sla_status:'no_deadline'}}); continue; }
  const hoursLeft = (deadline - now) / 3600000;
  let sla_status = 'ok';
  if (hoursLeft <= 0) sla_status = 'breached';
  else if (hoursLeft <= 1) sla_status = 'warning';
  results.push({json:{...t, sla_status, hours_remaining: Math.round(hoursLeft*10)/10, deadline_iso: deadline.toISOString()}});
}
if (results.length === 0) results.push({json:{sla_status:'no_tickets'}});
return results;"""},
                   "id": uid(), "name": "Check SLA Deadlines",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [660, 300]})

    # 4. Switch: OK / Warning / Breached
    nodes.append({"parameters": {"rules": {"values": [
        {"conditions": {"conditions": [{"leftValue": "={{ $json.sla_status }}", "rightValue": "warning",
          "operator": {"type": "string", "operation": "equals"}}]}, "outputKey": "warning"},
        {"conditions": {"conditions": [{"leftValue": "={{ $json.sla_status }}", "rightValue": "breached",
          "operator": {"type": "string", "operation": "equals"}}]}, "outputKey": "breached"},
    ]}, "options": {"fallbackOutput": "extra"}},
                   "id": uid(), "name": "SLA Status",
                   "type": "n8n-nodes-base.switch", "typeVersion": 3.2, "position": [880, 300]})

    # 5. Gmail: SLA Warning
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=SLA Warning: {{ $json.ticket_id || $json.id }} ({{ $json.hours_remaining }}h left)",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif"><div style="background:#FFA500;padding:15px;text-align:center"><h2 style="color:white;margin:0">SLA Warning</h2></div>
<div style="padding:20px"><p><b>Ticket:</b> {{ $json.ticket_id }}</p><p><b>Priority:</b> {{ $json.priority }}</p>
<p><b>Hours Remaining:</b> {{ $json.hours_remaining }}</p><p><b>Subject:</b> {{ $json.subject }}</p></div></div>""",
        "options": {}},
                   "id": uid(), "name": "Send SLA Warning",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1120, 180], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 6. Escalate Ticket (Airtable update)
    nodes.append({"parameters": {"operation": "update", **airtable_ref(SUPPORT_BASE_ID, TABLE_TICKETS),
        "columns": {"value": {"status": "In_Progress", "assigned_to": "ESCALATED",
            "ai_summary": "=SLA BREACHED - {{ $json.ai_summary || 'Immediate attention required' }}"}},
        "options": {}, "matchingColumns": ["ticket_id"]},
                   "id": uid(), "name": "Escalate Ticket",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1120, 420], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 7. Gmail: Breach Alert
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=URGENT SLA BREACH: {{ $('SLA Status').item.json.ticket_id }}",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif"><div style="background:#DC3545;padding:15px;text-align:center"><h2 style="color:white;margin:0">SLA BREACHED</h2></div>
<div style="padding:20px"><p><b>Ticket:</b> {{ $('SLA Status').item.json.ticket_id }}</p>
<p><b>Priority:</b> {{ $('SLA Status').item.json.priority }}</p><p><b>Client:</b> {{ $('SLA Status').item.json.client_email }}</p>
<p><b>Subject:</b> {{ $('SLA Status').item.json.subject }}</p>
<p style="color:red;font-weight:bold">Ticket escalated. SLA deadline exceeded.</p></div></div>""",
        "options": {}},
                   "id": uid(), "name": "Send Breach Alert",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1360, 420], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_sup02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Read Open Tickets", "type": "main", "index": 0}]]},
        "Read Open Tickets": {"main": [[{"node": "Check SLA Deadlines", "type": "main", "index": 0}]]},
        "Check SLA Deadlines": {"main": [[{"node": "SLA Status", "type": "main", "index": 0}]]},
        "SLA Status": {"main": [
            [{"node": "Send SLA Warning", "type": "main", "index": 0}],
            [{"node": "Escalate Ticket", "type": "main", "index": 0}],
        ]},
        "Escalate Ticket": {"main": [[{"node": "Send Breach Alert", "type": "main", "index": 0}]]},
    }


# ======================================================================
# SUP-03: Auto-Resolver (sub-workflow)
# ======================================================================

def build_sup03_nodes():
    nodes = []

    # 1. Webhook
    nodes.append({"parameters": {"path": "support-auto-resolve", "responseMode": "responseNode", "options": {}},
                   "id": uid(), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                   "position": [220, 300], "webhookId": uid()})

    # 2. Read Ticket
    nodes.append({"parameters": {"operation": "search", **airtable_ref(SUPPORT_BASE_ID, TABLE_TICKETS),
        "filterByFormula": "=({ticket_id} = '{{ $json.body.ticket_id }}')", "returnAll": False, "options": {}},
                   "id": uid(), "name": "Read Ticket",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [440, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Search KB Articles
    nodes.append({"parameters": {"operation": "search", **airtable_ref(SUPPORT_BASE_ID, TABLE_KNOWLEDGE_BASE),
        "filterByFormula": "=OR(FIND(LOWER('{{ $('Read Ticket').first().json.subject }}'), LOWER({keywords})), FIND(LOWER('{{ $('Read Ticket').first().json.subject }}'), LOWER({title})))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Search KB Articles",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [660, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 4. AI Draft from KB
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 800,
  "messages": [
    {"role": "system", "content": "Draft a support response using KB articles. Rate confidence 0-1 that this resolves the issue. End with 'Confidence: X.XX'. If KB is insufficient, set confidence < 0.5."},
    {"role": "user", "content": "Subject: {{ $('Read Ticket').first().json.subject }}\\nBody: {{ $('Read Ticket').first().json.body }}\\n\\nKB Articles ({{ $('Search KB Articles').all().length }}):\\n{{ $('Search KB Articles').all().map(i => '- ' + (i.json.title||'') + ': ' + (i.json.content||'').substring(0,300)).join('\\n') || 'None found.' }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Draft from KB",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [880, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 5. Rate Confidence (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const aiContent = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '';
let confidence = 0;
const match = aiContent.match(/[Cc]onfidence:\\s*([\\d.]+)/);
if (match) confidence = parseFloat(match[1]);
const draft = aiContent.replace(/[Cc]onfidence:\\s*[\\d.]+/g, '').trim();
const ticket = $('Read Ticket').first().json;
return { json: { ticket_id: ticket.ticket_id||ticket.id, client_email: ticket.client_email,
  subject: ticket.subject, draft_reply: draft, confidence, auto_resolve: confidence > 0.85 }};"""},
                   "id": uid(), "name": "Rate Confidence",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1100, 300]})

    # 6. If confidence > 0.85
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.confidence }}", "rightValue": 0.85,
         "operator": {"type": "number", "operation": "gt"}}]}, "options": {}},
                   "id": uid(), "name": "If High Confidence",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1320, 300]})

    # 7. Send Resolution Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": "={{ $json.client_email }}", "subject": "=Re: {{ $json.subject }} [{{ $json.ticket_id }}]",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">AnyVision Media Support</h2></div>
<div style="padding:20px"><p>Ticket: <strong>{{ $json.ticket_id }}</strong></p>
<div style="white-space:pre-wrap">{{ $json.draft_reply }}</div></div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">Auto-resolved from KB. Reply for further help.</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Send Resolution Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1560, 200], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    # 8. Update Ticket Resolved (Airtable)
    nodes.append({"parameters": {"operation": "update", **airtable_ref(SUPPORT_BASE_ID, TABLE_TICKETS),
        "columns": {"value": {"status": "Resolved", "resolved_at": "={{ $now.toISO() }}",
            "ai_suggestion": "=Auto-resolved (confidence {{ $('Rate Confidence').first().json.confidence }})"}},
        "options": {}, "matchingColumns": ["ticket_id"]},
                   "id": uid(), "name": "Update Ticket Resolved",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1780, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 9. Respond Webhook
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": "={{ JSON.stringify({success:true, ticket_id:$('Rate Confidence').first().json.ticket_id, auto_resolved:$('Rate Confidence').first().json.auto_resolve, confidence:$('Rate Confidence').first().json.confidence}) }}",
        "options": {}},
                   "id": uid(), "name": "Respond Webhook",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [2000, 300]})

    return nodes


def build_sup03_connections(nodes):
    return {
        "Webhook": {"main": [[{"node": "Read Ticket", "type": "main", "index": 0}]]},
        "Read Ticket": {"main": [[{"node": "Search KB Articles", "type": "main", "index": 0}]]},
        "Search KB Articles": {"main": [[{"node": "AI Draft from KB", "type": "main", "index": 0}]]},
        "AI Draft from KB": {"main": [[{"node": "Rate Confidence", "type": "main", "index": 0}]]},
        "Rate Confidence": {"main": [[{"node": "If High Confidence", "type": "main", "index": 0}]]},
        "If High Confidence": {"main": [
            [{"node": "Send Resolution Email", "type": "main", "index": 0}],
            [{"node": "Respond Webhook", "type": "main", "index": 0}],
        ]},
        "Send Resolution Email": {"main": [[{"node": "Update Ticket Resolved", "type": "main", "index": 0}]]},
        "Update Ticket Resolved": {"main": [[{"node": "Respond Webhook", "type": "main", "index": 0}]]},
    }


# ======================================================================
# SUP-04: KB Builder
# ======================================================================

def build_sup04_nodes():
    nodes = []

    # 1. Schedule Trigger (Sun 18:00 UTC = 20:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 18 * * 0"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Read Resolved Tickets (last 7 days)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(SUPPORT_BASE_ID, TABLE_TICKETS),
        "filterByFormula": "=AND({status} = 'Resolved', IS_AFTER({resolved_at}, DATEADD(TODAY(), -7, 'days')))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Resolved Tickets",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [440, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Read Existing KB (for dedup)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(SUPPORT_BASE_ID, TABLE_KNOWLEDGE_BASE),
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Existing KB",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [440, 420], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 4. AI Generate KB Articles
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 2000,
  "messages": [
    {"role": "system", "content": "Analyze resolved support tickets. Generate a JSON array of KB articles: [{title, category (FAQ/Troubleshooting/How-To/Policy), content, keywords (comma-separated), source_tickets, confidence (0-1)}]. Only create articles for recurring patterns (2+ tickets) or likely-to-recur issues. Max 5 articles."},
    {"role": "user", "content": "Resolved tickets ({{ $('Read Resolved Tickets').all().length }}):\\n{{ $('Read Resolved Tickets').all().map(i => 'ID:' + (i.json.ticket_id||i.json.id) + ' Subject:' + i.json.subject + ' Resolution:' + (i.json.ai_suggestion||i.json.ai_summary||'N/A')).join('\\n') || 'None.' }}\\n\\nExisting KB titles:\\n{{ $('Read Existing KB').all().map(i => '- ' + i.json.title).join('\\n') || 'None.' }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Generate Articles",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [700, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 5. Deduplicate (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '[]';
let articles = [];
try { articles = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { articles = []; }
const existing = $('Read Existing KB').all().map(i => (i.json.title||'').toLowerCase());
const unique = articles.filter(a => a.title && !existing.includes(a.title.toLowerCase()));
if (unique.length === 0) return {json:{skip:true, message:'No new unique articles'}};
return unique.map(a => ({json:{
  article_id: 'KB-' + Date.now().toString(36).toUpperCase() + '-' + Math.random().toString(36).substring(2,6).toUpperCase(),
  title: a.title, category: a.category||'FAQ', content: a.content, keywords: a.keywords||'',
  source_ticket_ids: a.source_tickets||'', confidence_score: a.confidence||0.8, skip: false}}));"""},
                   "id": uid(), "name": "Deduplicate Articles",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [940, 300]})

    # 6. If has new articles
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.skip }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "notEquals"}}]}, "options": {}},
                   "id": uid(), "name": "If New Articles",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1160, 300]})

    # 7. Create KB Article (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(SUPPORT_BASE_ID, TABLE_KNOWLEDGE_BASE),
        "columns": {"value": {"article_id": "={{ $json.article_id }}", "title": "={{ $json.title }}",
            "category": "={{ $json.category }}", "content": "={{ $json.content }}",
            "keywords": "={{ $json.keywords }}", "source_ticket_ids": "={{ $json.source_ticket_ids }}",
            "confidence_score": "={{ $json.confidence_score }}",
            "created_at": "={{ $now.toISO() }}", "last_updated": "={{ $now.toISO() }}"}},
        "options": {}},
                   "id": uid(), "name": "Create KB Article",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1380, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    return nodes


def build_sup04_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Resolved Tickets", "type": "main", "index": 0},
            {"node": "Read Existing KB", "type": "main", "index": 0},
        ]]},
        "Read Resolved Tickets": {"main": [[{"node": "AI Generate Articles", "type": "main", "index": 0}]]},
        "Read Existing KB": {"main": [[{"node": "AI Generate Articles", "type": "main", "index": 0}]]},
        "AI Generate Articles": {"main": [[{"node": "Deduplicate Articles", "type": "main", "index": 0}]]},
        "Deduplicate Articles": {"main": [[{"node": "If New Articles", "type": "main", "index": 0}]]},
        "If New Articles": {"main": [[{"node": "Create KB Article", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "sup01": {"name": "SUP-01 Ticket Creator", "build_nodes": build_sup01_nodes,
              "build_connections": build_sup01_connections,
              "filename": "sup01_ticket_creator.json", "tags": ["support", "tickets", "ai-classify"]},
    "sup02": {"name": "SUP-02 SLA Monitor", "build_nodes": build_sup02_nodes,
              "build_connections": build_sup02_connections,
              "filename": "sup02_sla_monitor.json", "tags": ["support", "sla", "monitoring"]},
    "sup03": {"name": "SUP-03 Auto-Resolver", "build_nodes": build_sup03_nodes,
              "build_connections": build_sup03_connections,
              "filename": "sup03_auto_resolver.json", "tags": ["support", "auto-resolve", "kb"]},
    "sup04": {"name": "SUP-04 KB Builder", "build_nodes": build_sup04_nodes,
              "build_connections": build_sup04_connections,
              "filename": "sup04_kb_builder.json", "tags": ["support", "knowledge-base", "ai-generate"]},
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
        "meta": {"templateCredsSetupCompleted": True, "builder": "deploy_support_agent.py",
                 "built_at": datetime.now().isoformat()},
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "support-agent"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / builder["filename"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)
    node_count = len(workflow_json["nodes"])
    print(f"  + {builder['name']:<40} ({node_count} nodes) -> {output_path}")
    return output_path


def deploy_workflow(key, workflow_json, activate=False):
    from n8n_client import N8nClient
    client = N8nClient()
    builder = WORKFLOW_BUILDERS[key]
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
        print("AVM Support Agent - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_support_agent.py build              # Build all")
        print("  python tools/deploy_support_agent.py build sup01        # Build one")
        print("  python tools/deploy_support_agent.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_support_agent.py activate           # Build + Deploy + Activate")
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
    print("AVM SUPPORT AGENT - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/support-agent/")

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
