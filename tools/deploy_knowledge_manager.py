"""
AVM Knowledge Manager - Workflow Builder & Deployer

Builds 3 knowledge management workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance.

Workflows:
    KM-01: Document Indexer          (Daily 02:00 SAST = 00:00 UTC) - Index Google Drive docs with AI
    KM-02: Contradiction Detector    (Wed 03:00 SAST = 01:00 UTC) - Find inconsistencies across docs
    KM-03: FAQ Generator             (Fri 04:00 SAST = 02:00 UTC) - Generate FAQs from support tickets

Usage:
    python tools/deploy_knowledge_manager.py build              # Build all workflow JSONs
    python tools/deploy_knowledge_manager.py build km01         # Build KM-01 only
    python tools/deploy_knowledge_manager.py build km02         # Build KM-02 only
    python tools/deploy_knowledge_manager.py build km03         # Build KM-03 only
    python tools/deploy_knowledge_manager.py deploy             # Build + Deploy (inactive)
    python tools/deploy_knowledge_manager.py activate           # Build + Deploy + Activate
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
TABLE_KNOWLEDGE_GRAPH = os.getenv("KM_TABLE_KNOWLEDGE_GRAPH", "REPLACE_AFTER_SETUP")

# Support tables (for FAQ generator)
SUPPORT_BASE_ID = os.getenv("SUPPORT_AIRTABLE_BASE_ID", "REPLACE_AFTER_SETUP")
TABLE_SUPPORT_KB = os.getenv("SUPPORT_TABLE_KNOWLEDGE_BASE", "REPLACE_AFTER_SETUP")

# -- Config --
AI_MODEL = "anthropic/claude-sonnet-4-20250514"
ALERT_EMAIL = "ian@anyvisionmedia.com"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
GOOGLE_DRIVE_API = "https://www.googleapis.com/drive/v3"


def uid():
    return str(uuid.uuid4())


def airtable_ref(base, table):
    return {"base": {"__rl": True, "value": base, "mode": "id"},
            "table": {"__rl": True, "value": table, "mode": "id"}}


# ======================================================================
# KM-01: Document Indexer (Daily 02:00 SAST = 00:00 UTC)
# ======================================================================

def build_km01_nodes():
    nodes = []

    # 1. Schedule Trigger (00:00 UTC = 02:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 0 * * *"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                   "position": [220, 300]})

    # 2. Fetch Recent Google Drive Files (httpRequest v4.2 - last 24h)
    nodes.append({"parameters": {
        "method": "GET",
        "url": "=" + GOOGLE_DRIVE_API + "/files",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "googleDriveOAuth2Api",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "q", "value": "=modifiedTime > '{{ $now.minus({hours: 24}).toISO() }}' and mimeType != 'application/vnd.google-apps.folder' and trashed = false"},
            {"name": "fields", "value": "files(id,name,mimeType,modifiedTime,webViewLink,owners)"},
            {"name": "pageSize", "value": "50"},
            {"name": "orderBy", "value": "modifiedTime desc"},
        ]},
        "options": {"timeout": 30000}},
                   "id": uid(), "name": "Fetch Recent Drive Files",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [440, 300]})

    # 3. Extract File List (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const files = resp.files || [];
if (files.length === 0) {
  return { json: { skip: true, message: 'No recently modified files found', indexed_count: 0 } };
}
return files.map(f => ({json: {
  file_id: f.id,
  file_name: f.name,
  mime_type: f.mimeType,
  modified_at: f.modifiedTime,
  web_link: f.webViewLink || '',
  owner: (f.owners && f.owners[0]) ? f.owners[0].emailAddress : '',
  skip: false,
}}));"""},
                   "id": uid(), "name": "Extract File List",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [660, 300]})

    # 4. Check if files found (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.skip }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "notEquals"}}],
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"}}},
                   "id": uid(), "name": "Has Files",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2,
                   "position": [880, 300]})

    # 5. Export File Content (httpRequest - Google Drive export)
    nodes.append({"parameters": {
        "method": "GET",
        "url": "={{ '" + GOOGLE_DRIVE_API + "/files/' + $json.file_id + '/export?mimeType=text/plain' }}",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "googleDriveOAuth2Api",
        "options": {"timeout": 30000, "response": {"response": {"responseFormat": "text"}}},
    },
                   "id": uid(), "name": "Export File Content",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [1100, 300],
                   "onError": "continueRegularOutput"})

    # 6. AI Summarize and Tag (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 600,
  "messages": [
    {"role": "system", "content": "Summarize this document in 2-3 sentences. Classify type: Contract, SOP, FAQ, Brand Guide, Policy, Template. Extract key terms as tags (comma-separated, max 8). Output JSON only: {summary: string, doc_type: string, tags: string, key_topics: [string]}"},
    {"role": "user", "content": "File: {{ $('Extract File List').item.json.file_name }}\\nContent (first 3000 chars):\\n{{ String($json.data || $json.body || $json).substring(0, 3000) }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Summarize and Tag",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [1320, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 7. Extract AI Result (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let ai = {};
try { ai = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { ai = {summary: 'Parse failed', doc_type: 'Unknown', tags: '', key_topics: []}; }
const fileInfo = $('Extract File List').item.json;
return { json: {
  doc_id: 'DOC-' + fileInfo.file_id.substring(0, 8),
  file_id: fileInfo.file_id,
  file_name: fileInfo.file_name,
  mime_type: fileInfo.mime_type,
  web_link: fileInfo.web_link,
  owner: fileInfo.owner,
  doc_type: ai.doc_type || 'Unknown',
  summary: ai.summary || '',
  tags: ai.tags || '',
  key_topics: (ai.key_topics || []).join(', '),
  modified_at: fileInfo.modified_at,
  indexed_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Extract AI Result",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [1540, 300]})

    # 8. Write/Update Knowledge_Graph (Airtable create)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_KNOWLEDGE_GRAPH),
        "columns": {"value": {
            "doc_id": "={{ $json.doc_id }}",
            "file_name": "={{ $json.file_name }}",
            "doc_type": "={{ $json.doc_type }}",
            "summary": "={{ $json.summary }}",
            "tags": "={{ $json.tags }}",
            "key_topics": "={{ $json.key_topics }}",
            "web_link": "={{ $json.web_link }}",
            "owner": "={{ $json.owner }}",
            "indexed_at": "={{ $json.indexed_at }}",
            "contradictions": ""}},
        "options": {}},
                   "id": uid(), "name": "Write Knowledge Graph",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [1760, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 9. Log Indexed Count (Code)
    nodes.append({"parameters": {"jsCode": """const allItems = $('Extract File List').all();
const indexed = allItems.filter(i => !i.json.skip).length;
return { json: {
  status: 'Document indexing complete',
  indexed_count: indexed,
  completed_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Log Indexed Count",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [1980, 300]})

    return nodes


def build_km01_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Fetch Recent Drive Files", "type": "main", "index": 0}]]},
        "Fetch Recent Drive Files": {"main": [[{"node": "Extract File List", "type": "main", "index": 0}]]},
        "Extract File List": {"main": [[{"node": "Has Files", "type": "main", "index": 0}]]},
        "Has Files": {"main": [
            [{"node": "Export File Content", "type": "main", "index": 0}],
            [],
        ]},
        "Export File Content": {"main": [[{"node": "AI Summarize and Tag", "type": "main", "index": 0}]]},
        "AI Summarize and Tag": {"main": [[{"node": "Extract AI Result", "type": "main", "index": 0}]]},
        "Extract AI Result": {"main": [[{"node": "Write Knowledge Graph", "type": "main", "index": 0}]]},
        "Write Knowledge Graph": {"main": [[{"node": "Log Indexed Count", "type": "main", "index": 0}]]},
    }


# ======================================================================
# KM-02: Contradiction Detector (Wednesday 03:00 SAST = 01:00 UTC)
# ======================================================================

def build_km02_nodes():
    nodes = []

    # 1. Schedule Trigger (Wednesday 01:00 UTC = 03:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 1 * * 3"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                   "position": [220, 300]})

    # 2. Read All Knowledge_Graph Records (Airtable)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(ORCH_BASE_ID, TABLE_KNOWLEDGE_GRAPH),
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read All Knowledge Records",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [440, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Group by Topic/Tags (Code)
    nodes.append({"parameters": {"jsCode": """const records = $input.all();
if (records.length === 0) {
  return { json: { skip: true, message: 'No knowledge records found', groups: [] } };
}

// Group documents by overlapping tags/topics
const tagIndex = {};
for (const item of records) {
  const doc = item.json;
  const tags = (doc.tags || '').split(',').map(t => t.trim().toLowerCase()).filter(Boolean);
  const topics = (doc.key_topics || '').split(',').map(t => t.trim().toLowerCase()).filter(Boolean);
  const allTerms = [...new Set([...tags, ...topics])];

  for (const term of allTerms) {
    if (!tagIndex[term]) tagIndex[term] = [];
    tagIndex[term].push({
      doc_id: doc.doc_id || doc.id,
      file_name: doc.file_name || '',
      doc_type: doc.doc_type || '',
      summary: doc.summary || '',
    });
  }
}

// Find groups with 2+ docs sharing a topic (potential contradiction sources)
const groups = Object.entries(tagIndex)
  .filter(([_, docs]) => docs.length >= 2)
  .map(([topic, docs]) => ({
    topic: topic,
    doc_count: docs.length,
    documents: docs.slice(0, 5), // limit to 5 per group for AI context
  }))
  .sort((a, b) => b.doc_count - a.doc_count)
  .slice(0, 10); // top 10 groups

return { json: {
  skip: groups.length === 0,
  total_records: records.length,
  topic_groups: groups.length,
  groups: groups,
}};"""},
                   "id": uid(), "name": "Group by Topic",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [660, 300]})

    # 4. Check if groups found (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.skip }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "notEquals"}}],
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"}}},
                   "id": uid(), "name": "Has Topic Groups",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2,
                   "position": [880, 300]})

    # 5. AI Contradiction Detection (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 1500,
  "messages": [
    {"role": "system", "content": "Compare these documents covering the same topic. Identify any contradictions, inconsistencies, or outdated information. For each contradiction, cite the specific documents and conflicting statements. Output JSON: {contradictions_found: number, contradictions: [{topic, doc_a: {doc_id, file_name, statement}, doc_b: {doc_id, file_name, statement}, severity: high/medium/low, recommendation}], summary: string}"},
    {"role": "user", "content": "Knowledge base documents grouped by shared topics ({{ $json.total_records }} total docs, {{ $json.topic_groups }} topic groups):\\n{{ JSON.stringify($json.groups) }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Contradiction Detection",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [1100, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 6. Extract Contradictions (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '{}';
let ai = {};
try { ai = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { ai = {contradictions_found: 0, contradictions: [], summary: 'Parse failed'}; }

// Build update records for affected docs
const updates = [];
const seen = new Set();
for (const c of (ai.contradictions || [])) {
  if (c.doc_a && c.doc_a.doc_id && !seen.has(c.doc_a.doc_id)) {
    seen.add(c.doc_a.doc_id);
    updates.push({json: {
      doc_id: c.doc_a.doc_id,
      contradictions: c.topic + ': ' + c.recommendation,
    }});
  }
  if (c.doc_b && c.doc_b.doc_id && !seen.has(c.doc_b.doc_id)) {
    seen.add(c.doc_b.doc_id);
    updates.push({json: {
      doc_id: c.doc_b.doc_id,
      contradictions: c.topic + ': ' + c.recommendation,
    }});
  }
}

if (updates.length === 0) {
  return { json: {
    contradictions_found: ai.contradictions_found || 0,
    ai_summary: ai.summary || 'No contradictions detected',
    has_contradictions: false,
  }};
}

return [{ json: {
  contradictions_found: ai.contradictions_found || 0,
  contradictions: ai.contradictions || [],
  ai_summary: ai.summary || '',
  has_contradictions: true,
  affected_docs: updates.map(u => u.json.doc_id),
}}];"""},
                   "id": uid(), "name": "Extract Contradictions",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [1320, 300]})

    # 7. Check if contradictions found (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.has_contradictions }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "equals"}}],
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"}}},
                   "id": uid(), "name": "Contradictions Found",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2,
                   "position": [1540, 300]})

    # 8. Alert Email - Contradictions (Gmail)
    nodes.append({"parameters": {
        "sendTo": ALERT_EMAIL,
        "subject": "=KNOWLEDGE BASE: {{ $('Extract Contradictions').first().json.contradictions_found }} contradictions detected",
        "emailType": "html",
        "message": """=<div style="font-family:Arial,sans-serif;max-width:600px">
<div style="background:#FFA500;padding:15px;text-align:center"><h2 style="color:white;margin:0">Knowledge Base Contradictions</h2></div>
<div style="padding:20px">
<p><b>Contradictions Found:</b> {{ $('Extract Contradictions').first().json.contradictions_found }}</p>
<h3>Summary</h3>
<p>{{ $('Extract Contradictions').first().json.ai_summary }}</p>
<h3>Details</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
<tr style="background:#FF6D5A;color:white;"><th>Topic</th><th>Doc A</th><th>Doc B</th><th>Severity</th><th>Action</th></tr>
{{ $('Extract Contradictions').first().json.contradictions.map(c => '<tr><td>' + c.topic + '</td><td>' + (c.doc_a ? c.doc_a.file_name : 'N/A') + '</td><td>' + (c.doc_b ? c.doc_b.file_name : 'N/A') + '</td><td>' + c.severity + '</td><td>' + c.recommendation + '</td></tr>').join('') || '<tr><td colspan="5">None</td></tr>' }}
</table>
<p><b>Affected Documents:</b> {{ JSON.stringify($('Extract Contradictions').first().json.affected_docs) }}</p>
</div>
<div style="background:#f0f0f0;padding:10px;font-size:12px;color:#666;text-align:center">AVM Knowledge Manager - Contradiction Detector</div>
</div>""",
        "options": {}},
                   "id": uid(), "name": "Alert Contradictions Email",
                   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
                   "position": [1760, 200], "credentials": {"gmailOAuth2": CRED_GMAIL}})

    return nodes


def build_km02_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[{"node": "Read All Knowledge Records", "type": "main", "index": 0}]]},
        "Read All Knowledge Records": {"main": [[{"node": "Group by Topic", "type": "main", "index": 0}]]},
        "Group by Topic": {"main": [[{"node": "Has Topic Groups", "type": "main", "index": 0}]]},
        "Has Topic Groups": {"main": [
            [{"node": "AI Contradiction Detection", "type": "main", "index": 0}],
            [],
        ]},
        "AI Contradiction Detection": {"main": [[{"node": "Extract Contradictions", "type": "main", "index": 0}]]},
        "Extract Contradictions": {"main": [[{"node": "Contradictions Found", "type": "main", "index": 0}]]},
        "Contradictions Found": {"main": [
            [{"node": "Alert Contradictions Email", "type": "main", "index": 0}],
            [],
        ]},
    }


# ======================================================================
# KM-03: FAQ Generator (Friday 04:00 SAST = 02:00 UTC)
# ======================================================================

def build_km03_nodes():
    nodes = []

    # 1. Schedule Trigger (Friday 02:00 UTC = 04:00 SAST)
    nodes.append({"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 2 * * 5"}]}},
                   "id": uid(), "name": "Schedule Trigger",
                   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                   "position": [220, 300]})

    # 2. Read Resolved Tickets from Support KB (Airtable)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(SUPPORT_BASE_ID, TABLE_SUPPORT_KB),
        "filterByFormula": "=AND({category} != '', IS_AFTER({created_at}, DATEADD(TODAY(), -14, 'days')))",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Resolved Tickets",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [440, 200], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 3. Read Existing FAQs from Knowledge_Graph (Airtable)
    nodes.append({"parameters": {"operation": "search", **airtable_ref(ORCH_BASE_ID, TABLE_KNOWLEDGE_GRAPH),
        "filterByFormula": "={doc_type} = 'FAQ'",
        "returnAll": True, "options": {}},
                   "id": uid(), "name": "Read Existing FAQs",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [440, 420], "credentials": {"airtableTokenApi": CRED_AIRTABLE},
                   "alwaysOutputData": True})

    # 4. AI Generate New FAQs (OpenRouter)
    nodes.append({"parameters": {
        "method": "POST", "url": OPENROUTER_URL,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514", "max_tokens": 2000,
  "messages": [
    {"role": "system", "content": "Based on these resolved support tickets, generate FAQ entries. Avoid duplicating existing FAQs. Format output as JSON array: [{question: string, answer: string, category: string, source_articles: [string], confidence: 0-1}]. Only generate FAQs for recurring patterns or commonly asked questions. Max 5 new FAQs."},
    {"role": "user", "content": "Resolved support KB articles ({{ $('Read Resolved Tickets').all().length }}):\\n{{ $('Read Resolved Tickets').all().map(i => 'Title:' + (i.json.title||i.json.article_id||'N/A') + ' Category:' + (i.json.category||'N/A') + ' Content:' + (i.json.content||'N/A').substring(0, 200)).join('\\n') || 'None.' }}\\n\\nExisting FAQ titles:\\n{{ $('Read Existing FAQs').all().map(i => '- ' + (i.json.file_name||i.json.summary||'N/A')).join('\\n') || 'None.' }}"}
  ]}""",
        "options": {}},
                   "id": uid(), "name": "AI Generate FAQs",
                   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                   "position": [700, 300], "credentials": {"httpHeaderAuth": CRED_OPENROUTER}})

    # 5. Parse and Deduplicate FAQs (Code)
    nodes.append({"parameters": {"jsCode": """const resp = $input.first().json;
const raw = (resp.choices && resp.choices[0]) ? resp.choices[0].message.content : '[]';
let faqs = [];
try { faqs = JSON.parse(raw.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim()); } catch(e) { faqs = []; }
if (!Array.isArray(faqs)) faqs = [];

const existing = $('Read Existing FAQs').all().map(i => (i.json.file_name || i.json.summary || '').toLowerCase());
const unique = faqs.filter(f => f.question && !existing.some(e => e.includes(f.question.toLowerCase().substring(0, 30))));

if (unique.length === 0) {
  return { json: { skip: true, message: 'No new unique FAQs generated', faq_count: 0 } };
}

return unique.map(f => ({json: {
  doc_id: 'FAQ-' + Date.now().toString(36).toUpperCase() + '-' + Math.random().toString(36).substring(2, 6).toUpperCase(),
  file_name: 'FAQ: ' + f.question,
  doc_type: 'FAQ',
  summary: 'Q: ' + f.question + '\\nA: ' + f.answer,
  tags: f.category || 'general',
  key_topics: (f.source_articles || []).join(', '),
  confidence: f.confidence || 0.8,
  skip: false,
}}));"""},
                   "id": uid(), "name": "Parse and Deduplicate",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [920, 300]})

    # 6. Check if new FAQs (If v2.2)
    nodes.append({"parameters": {"conditions": {"conditions": [
        {"leftValue": "={{ $json.skip }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "notEquals"}}],
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"}}},
                   "id": uid(), "name": "Has New FAQs",
                   "type": "n8n-nodes-base.if", "typeVersion": 2.2,
                   "position": [1140, 300]})

    # 7. Create FAQ Records in Knowledge_Graph (Airtable)
    nodes.append({"parameters": {"operation": "create", **airtable_ref(ORCH_BASE_ID, TABLE_KNOWLEDGE_GRAPH),
        "columns": {"value": {
            "doc_id": "={{ $json.doc_id }}",
            "file_name": "={{ $json.file_name }}",
            "doc_type": "FAQ",
            "summary": "={{ $json.summary }}",
            "tags": "={{ $json.tags }}",
            "key_topics": "={{ $json.key_topics }}",
            "indexed_at": "={{ $now.toISO() }}",
            "contradictions": ""}},
        "options": {}},
                   "id": uid(), "name": "Create FAQ Records",
                   "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
                   "position": [1360, 300], "credentials": {"airtableTokenApi": CRED_AIRTABLE}})

    # 8. Log FAQ Generation Count (Code)
    nodes.append({"parameters": {"jsCode": """const allItems = $('Parse and Deduplicate').all();
const created = allItems.filter(i => !i.json.skip).length;
return { json: {
  status: 'FAQ generation complete',
  faqs_created: created,
  completed_at: new Date().toISOString(),
}};"""},
                   "id": uid(), "name": "Log FAQ Count",
                   "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [1580, 300]})

    return nodes


def build_km03_connections(nodes):
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Resolved Tickets", "type": "main", "index": 0},
            {"node": "Read Existing FAQs", "type": "main", "index": 0},
        ]]},
        "Read Resolved Tickets": {"main": [[{"node": "AI Generate FAQs", "type": "main", "index": 0}]]},
        "Read Existing FAQs": {"main": [[{"node": "AI Generate FAQs", "type": "main", "index": 0}]]},
        "AI Generate FAQs": {"main": [[{"node": "Parse and Deduplicate", "type": "main", "index": 0}]]},
        "Parse and Deduplicate": {"main": [[{"node": "Has New FAQs", "type": "main", "index": 0}]]},
        "Has New FAQs": {"main": [
            [{"node": "Create FAQ Records", "type": "main", "index": 0}],
            [],
        ]},
        "Create FAQ Records": {"main": [[{"node": "Log FAQ Count", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "km01": {"name": "KM-01 Document Indexer", "build_nodes": build_km01_nodes,
             "build_connections": build_km01_connections,
             "filename": "km01_document_indexer.json", "tags": ["knowledge", "indexer", "drive"]},
    "km02": {"name": "KM-02 Contradiction Detector", "build_nodes": build_km02_nodes,
             "build_connections": build_km02_connections,
             "filename": "km02_contradiction_detector.json", "tags": ["knowledge", "contradiction", "weekly"]},
    "km03": {"name": "KM-03 FAQ Generator", "build_nodes": build_km03_nodes,
             "build_connections": build_km03_connections,
             "filename": "km03_faq_generator.json", "tags": ["knowledge", "faq", "weekly"]},
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
        "meta": {"templateCredsSetupCompleted": True, "builder": "deploy_knowledge_manager.py",
                 "built_at": datetime.now().isoformat()},
    }


def save_workflow(key, workflow_json):
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "knowledge-manager"
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
        print("AVM Knowledge Manager - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_knowledge_manager.py build              # Build all")
        print("  python tools/deploy_knowledge_manager.py build km01         # Build one")
        print("  python tools/deploy_knowledge_manager.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_knowledge_manager.py activate           # Build + Deploy + Activate")
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
    print("AVM KNOWLEDGE MANAGER - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/knowledge-manager/")

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
