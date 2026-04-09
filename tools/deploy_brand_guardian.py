"""
AVM Brand Guardian - Workflow Builder & Deployer

Builds 3 brand protection workflows for content compliance,
weekly audits, and competitor differentiation analysis.

Workflows:
    BRAND-01: Pre-Publish Gate    (Webhook) - AI brand compliance scoring before content goes live
    BRAND-02: Weekly Brand Audit  (Sun 04:00 SAST = 02:00 UTC) - Audit recent content for brand consistency
    BRAND-03: Competitor Diff     (Mon 08:00 SAST = 06:00 UTC) - Compare positioning vs competitors

Usage:
    python tools/deploy_brand_guardian.py build              # Build all JSONs
    python tools/deploy_brand_guardian.py build brand01      # Build BRAND-01 only
    python tools/deploy_brand_guardian.py deploy             # Build + Deploy (inactive)
    python tools/deploy_brand_guardian.py activate           # Build + Deploy + Activate
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
TABLE_BRAND_AUDIT = os.getenv("BRAND_TABLE_AUDIT", "REPLACE_AFTER_SETUP")
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
# BRAND-01: Pre-Publish Gate (Webhook)
# ======================================================================

def build_brand01_nodes():
    nodes = []

    # 1. Webhook
    nodes.append({"parameters": {"path": "brand-check", "responseMode": "responseNode", "options": {}},
                   "id": uid(), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
                   "position": [220, 300], "webhookId": uid()})

    # 2. Parse Content (Code)
    nodes.append({"parameters": {"jsCode": """const body = $input.first().json.body || $input.first().json;
return { json: {
  title: body.title || '',
  body: body.body || body.content || '',
  platform: body.platform || 'unknown',
  content_type: body.content_type || 'general',
  submitted_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Parse Content", "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [440, 300]})

    # 3. AI Brand Check (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 800,
  "messages": [
    {"role": "system", "content": "Score this content for brand compliance. Check: tone (professional, innovative), terminology (use 'digital growth partner' not 'agency'), color references (#FF6D5A), call to action clarity. Return JSON only: {compliance_score: 0-100, issues: [], recommendations: [], approved: bool}. approved = true if score >= 80."},
    {"role": "user", "content": "Title: {{ $json.title }}\\nPlatform: {{ $json.platform }}\\nContent Type: {{ $json.content_type }}\\nBody: {{ $json.body }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Brand Check",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [660, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 4. Parse Score (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let result = {};
try { result = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { result = {compliance_score: 0, issues: ['Parse failed'], recommendations: ['Manual review required'], approved: false}; }
const content = $('Parse Content').first().json;
return { json: {
  compliance_score: result.compliance_score || 0,
  issues: result.issues || [],
  recommendations: result.recommendations || [],
  approved: result.approved || false,
  title: content.title,
  body: content.body,
  platform: content.platform,
  content_type: content.content_type,
  submitted_at: content.submitted_at,
  checked_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Parse Score",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [880, 300]})

    # 5. Check Threshold (If v2.2) - score >= 80
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.compliance_score }}", "rightValue": 80,
         "operator": {"type": "number", "operation": "gte"}}]}, "options": {}},
                   "id": uid(), "name": "Check Threshold",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1100, 300]})

    # 6. Respond Approved (respondToWebhook)
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": "={{ JSON.stringify({approved: true, compliance_score: $('Parse Score').first().json.compliance_score, recommendations: $('Parse Score').first().json.recommendations}) }}",
        "options": {}},
                   "id": uid(), "name": "Respond Approved",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [1320, 200]})

    # 7. Write Audit Record (Airtable - for failed content)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_BRAND_AUDIT),
        "columns": {"value": {
            "audit_type": "Pre-Publish Gate",
            "title": "={{ $('Parse Score').first().json.title }}",
            "platform": "={{ $('Parse Score').first().json.platform }}",
            "compliance_score": "={{ $('Parse Score').first().json.compliance_score }}",
            "issues": "={{ $('Parse Score').first().json.issues.join('; ') }}",
            "recommendations": "={{ $('Parse Score').first().json.recommendations.join('; ') }}",
            "status": "Failed",
            "checked_at": "={{ $('Parse Score').first().json.checked_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Audit Record",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1320, 420], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 8. Respond Rejected (respondToWebhook)
    nodes.append({"parameters": {"respondWith": "json",
        "responseBody": "={{ JSON.stringify({approved: false, compliance_score: $('Parse Score').first().json.compliance_score, issues: $('Parse Score').first().json.issues, recommendations: $('Parse Score').first().json.recommendations}) }}",
        "options": {}},
                   "id": uid(), "name": "Respond Rejected",
                   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [1540, 420]})

    return nodes


def build_brand01_connections(nodes):
    return {
        "Webhook": {"main": [[{"node": "Parse Content", "type": "main", "index": 0}]]},
        "Parse Content": {"main": [[{"node": "AI Brand Check", "type": "main", "index": 0}]]},
        "AI Brand Check": {"main": [[{"node": "Parse Score", "type": "main", "index": 0}]]},
        "Parse Score": {"main": [[{"node": "Check Threshold", "type": "main", "index": 0}]]},
        "Check Threshold": {"main": [
            [{"node": "Respond Approved", "type": "main", "index": 0}],
            [{"node": "Write Audit Record", "type": "main", "index": 0}],
        ]},
        "Write Audit Record": {"main": [[{"node": "Respond Rejected", "type": "main", "index": 0}]]},
    }


# ======================================================================
# BRAND-02: Weekly Brand Audit (Sunday 04:00 SAST = 02:00 UTC)
# ======================================================================

def build_brand02_nodes():
    nodes = []

    # 1. Schedule Trigger (Sun 02:00 UTC = 04:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 2 * * 0"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Fetch Recent Content (Airtable - Content Calendar, last 7 days)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(MARKETING_BASE_ID, TABLE_CONTENT_CALENDAR),
        "filterByFormula": "=IS_AFTER({created_at}, DATEADD(TODAY(), -7, 'days'))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Fetch Recent Content",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [440, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Aggregate Content (Code)
    nodes.append({"parameters": {"jsCode": """const items = $('Fetch Recent Content').all();
const contentList = items.map(i => {
  const d = i.json;
  return 'Title: ' + (d.title || d.Name || 'Untitled') + '\\nPlatform: ' + (d.platform || 'N/A') + '\\nContent: ' + (d.content || d.body || d.description || 'N/A').substring(0, 500);
}).join('\\n---\\n');
return { json: { content_count: items.length, content_list: contentList, audit_date: new Date().toISOString() }};"""},
                   "id": uid(), "name": "Aggregate Content",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [660, 300]})

    # 4. AI Audit (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1500,
  "messages": [
    {"role": "system", "content": "You are AnyVision Media's brand auditor. Analyze all content for brand consistency. Brand guidelines: tone=professional+innovative, terminology='digital growth partner' (not 'agency'), primary color=#FF6D5A, values=innovation+results+transparency. Return JSON: {overall_score: 0-100, content_audited: number, consistent_count: number, inconsistent_items: [{title, issues}], trends: string, recommendations: []}"},
    {"role": "user", "content": "Audit {{ $json.content_count }} pieces of content from the past week:\\n\\n{{ $json.content_list }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Brand Audit",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [880, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 5. Parse Audit Results (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let audit = {};
try { audit = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { audit = {overall_score: 0, content_audited: 0, consistent_count: 0, inconsistent_items: [], trends: 'Parse failed', recommendations: ['Manual review needed']}; }
const meta = $('Aggregate Content').first().json;
return { json: {
  overall_score: audit.overall_score || 0,
  content_audited: audit.content_audited || meta.content_count,
  consistent_count: audit.consistent_count || 0,
  inconsistent_items: JSON.stringify(audit.inconsistent_items || []),
  trends: audit.trends || '',
  recommendations: (audit.recommendations || []).join('; '),
  audit_date: meta.audit_date,
}};"""},
                   "id": uid(), "name": "Parse Audit Results",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1100, 300]})

    # 6. Write Audit Results (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_BRAND_AUDIT),
        "columns": {"value": {
            "audit_type": "Weekly Brand Audit",
            "compliance_score": "={{ $json.overall_score }}",
            "title": "=Weekly Brand Audit {{ $json.audit_date }}",
            "issues": "={{ $json.inconsistent_items }}",
            "recommendations": "={{ $json.recommendations }}",
            "status": "={{ $json.overall_score >= 80 ? 'Passed' : 'Action Required' }}",
            "checked_at": "={{ $json.audit_date }}"}},
        "options": {}},
                   "id": uid(), "name": "Write Audit Results",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1320, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 7. Send Report Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=Weekly Brand Health Report - Score: {{ $('Parse Audit Results').first().json.overall_score }}/100",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Weekly Brand Health Report</h2></div>
<div style="padding:20px">
<h3>Overall Score: {{ $('Parse Audit Results').first().json.overall_score }}/100</h3>
<p><b>Content Audited:</b> {{ $('Parse Audit Results').first().json.content_audited }}</p>
<p><b>Consistent:</b> {{ $('Parse Audit Results').first().json.consistent_count }}</p>
<h3>Trends</h3><p>{{ $('Parse Audit Results').first().json.trends }}</p>
<h3>Recommendations</h3><p>{{ $('Parse Audit Results').first().json.recommendations }}</p>
<h3>Inconsistent Items</h3><p style="font-size:12px">{{ $('Parse Audit Results').first().json.inconsistent_items }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Brand Guardian - Automated Report</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Send Report Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1540, 300], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_brand02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Fetch Recent Content", "type": "main", "index": 0}]]},
        "Fetch Recent Content": {"main": [[{"node": "Aggregate Content", "type": "main", "index": 0}]]},
        "Aggregate Content": {"main": [[{"node": "AI Brand Audit", "type": "main", "index": 0}]]},
        "AI Brand Audit": {"main": [[{"node": "Parse Audit Results", "type": "main", "index": 0}]]},
        "Parse Audit Results": {"main": [[{"node": "Write Audit Results", "type": "main", "index": 0}]]},
        "Write Audit Results": {"main": [[{"node": "Send Report Email", "type": "main", "index": 0}]]},
    }


# ======================================================================
# BRAND-03: Competitor Differentiation (Monday 08:00 SAST = 06:00 UTC)
# ======================================================================

def build_brand03_nodes():
    nodes = []

    # 1. Schedule Trigger (Mon 06:00 UTC = 08:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6 * * 1"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [220, 300]})

    # 2. Set Competitor List
    nodes.append({"parameters": {"assignments": {"assignments": [
        {"id": uid(), "name": "competitors", "value": "digital marketing agencies Johannesburg, SEO companies South Africa, social media marketing Fourways, digital growth partners Gauteng", "type": "string"},
        {"id": uid(), "name": "our_positioning", "value": "AnyVision Media - Digital Growth Partner specializing in AI-powered automation, workflow optimization, and data-driven marketing for South African businesses", "type": "string"},
    ]}, "options": {}},
                   "id": uid(), "name": "Set Competitor List",
                   "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [440, 300]})

    # 3. Tavily Search Competitors (httpRequest)
    nodes.append({"parameters": {
        "method": "POST", "url": "https://api.tavily.com/search",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "query": "{{ $json.competitors }}",
  "search_depth": "advanced",
  "max_results": 10,
  "include_answer": true,
  "include_raw_content": false
}""",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Content-Type", "value": "application/json"}
        ]},
        "options": {}},
                   "id": uid(), "name": "Tavily Search Competitors",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [660, 300]})

    # 4. Extract Search Results (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const results = resp.results || [];
const answer = resp.answer || '';
const summaries = results.map(r => 'Source: ' + r.url + '\\nTitle: ' + r.title + '\\nSnippet: ' + (r.content || '').substring(0, 300)).join('\\n---\\n');
const positioning = $('Set Competitor List').first().json.our_positioning;
return { json: { competitor_data: summaries, answer, our_positioning: positioning, result_count: results.length, searched_at: new Date().toISOString() }};"""},
                   "id": uid(), "name": "Extract Search Results",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [880, 300]})

    # 5. AI Differentiation Analysis (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """{
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1500,
  "messages": [
    {"role": "system", "content": "Analyze competitor positioning vs AnyVision Media. Return JSON: {differentiation_score: 0-100, our_strengths: [], competitor_threats: [], messaging_gaps: [], opportunities: [], recommended_actions: [], executive_summary: string}. Focus on actionable insights for South African digital marketing landscape."},
    {"role": "user", "content": "Our Positioning: {{ $json.our_positioning }}\\n\\nCompetitor Intelligence ({{ $json.result_count }} sources):\\n{{ $json.competitor_data }}\\n\\nSearch Summary: {{ $json.answer }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Differentiation Analysis",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "onError": "continueRegularOutput",
                   "position": [1100, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 6. Parse Analysis (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let analysis = {};
try { analysis = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { analysis = {differentiation_score: 0, our_strengths: [], competitor_threats: [], messaging_gaps: [], opportunities: [], recommended_actions: [], executive_summary: 'Parse failed'}; }
const meta = $('Extract Search Results').first().json;
return { json: {
  differentiation_score: analysis.differentiation_score || 0,
  our_strengths: (analysis.our_strengths || []).join('; '),
  competitor_threats: (analysis.competitor_threats || []).join('; '),
  messaging_gaps: (analysis.messaging_gaps || []).join('; '),
  opportunities: (analysis.opportunities || []).join('; '),
  recommended_actions: (analysis.recommended_actions || []).join('; '),
  executive_summary: analysis.executive_summary || '',
  searched_at: meta.searched_at,
}};"""},
                   "id": uid(), "name": "Parse Analysis",
                   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1320, 300]})

    # 7. Write to Brand Audit (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_BRAND_AUDIT),
        "columns": {"value": {
            "audit_type": "Competitor Differentiation",
            "title": "=Competitor Analysis {{ $json.searched_at }}",
            "compliance_score": "={{ $json.differentiation_score }}",
            "issues": "=Threats: {{ $json.competitor_threats }}. Gaps: {{ $json.messaging_gaps }}",
            "recommendations": "={{ $json.recommended_actions }}",
            "status": "={{ $json.differentiation_score >= 70 ? 'Strong' : 'Needs Attention' }}",
            "checked_at": "={{ $json.searched_at }}"}},
        "options": {}},
                   "id": uid(), "name": "Write to Brand Audit",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1540, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 8. Send Insights Email (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=Competitor Differentiation Report - Score: {{ $('Parse Analysis').first().json.differentiation_score }}/100",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FF6D5A;padding:15px;text-align:center"><h2 style="color:white;margin:0">Competitor Differentiation Report</h2></div>
<div style="padding:20px">
<h3>Differentiation Score: {{ $('Parse Analysis').first().json.differentiation_score }}/100</h3>
<p><b>Executive Summary:</b> {{ $('Parse Analysis').first().json.executive_summary }}</p>
<h3>Our Strengths</h3><p>{{ $('Parse Analysis').first().json.our_strengths }}</p>
<h3>Competitor Threats</h3><p>{{ $('Parse Analysis').first().json.competitor_threats }}</p>
<h3>Messaging Gaps</h3><p>{{ $('Parse Analysis').first().json.messaging_gaps }}</p>
<h3>Opportunities</h3><p>{{ $('Parse Analysis').first().json.opportunities }}</p>
<h3>Recommended Actions</h3><p>{{ $('Parse Analysis').first().json.recommended_actions }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Brand Guardian - Automated Report</div></div>""",
        "options": {}},
                   "id": uid(), "name": "Send Insights Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "onError": "continueRegularOutput",
                   "position": [1760, 300], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_brand03_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Set Competitor List", "type": "main", "index": 0}]]},
        "Set Competitor List": {"main": [[{"node": "Tavily Search Competitors", "type": "main", "index": 0}]]},
        "Tavily Search Competitors": {"main": [[{"node": "Extract Search Results", "type": "main", "index": 0}]]},
        "Extract Search Results": {"main": [[{"node": "AI Differentiation Analysis", "type": "main", "index": 0}]]},
        "AI Differentiation Analysis": {"main": [[{"node": "Parse Analysis", "type": "main", "index": 0}]]},
        "Parse Analysis": {"main": [[{"node": "Write to Brand Audit", "type": "main", "index": 0}]]},
        "Write to Brand Audit": {"main": [[{"node": "Send Insights Email", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "brand01": {"name": "BRAND-01 Pre-Publish Gate", "build_nodes": build_brand01_nodes,
                "build_connections": build_brand01_connections,
                "filename": "brand01_pre_publish_gate.json", "tags": ["brand", "compliance", "webhook"]},
    "brand02": {"name": "BRAND-02 Weekly Brand Audit", "build_nodes": build_brand02_nodes,
                "build_connections": build_brand02_connections,
                "filename": "brand02_weekly_brand_audit.json", "tags": ["brand", "audit", "weekly"]},
    "brand03": {"name": "BRAND-03 Competitor Differentiation", "build_nodes": build_brand03_nodes,
                "build_connections": build_brand03_connections,
                "filename": "brand03_competitor_differentiation.json", "tags": ["brand", "competitor", "intelligence"]},
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
        "meta": {"templateCredsSetupCompleted": True, "builder": "deploy_brand_guardian.py",
                 "built_at": datetime.now().isoformat()},
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "brand-guardian"
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
        print("AVM Brand Guardian - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_brand_guardian.py build              # Build all")
        print("  python tools/deploy_brand_guardian.py build brand01      # Build one")
        print("  python tools/deploy_brand_guardian.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_brand_guardian.py activate           # Build + Deploy + Activate")
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
    print("AVM BRAND GUARDIAN - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/brand-guardian/")

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
