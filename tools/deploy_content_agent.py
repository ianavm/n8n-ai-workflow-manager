"""
AVM Content Agent - Workflow Builder & Deployer

Builds 2 content agent workflows for n8n Cloud.

Workflows:
    CONTENT-01: Performance Feedback Loop (Wed 09:00 SAST = 07:00 UTC)
        - Reads last 30 days of published content, aggregates engagement by type/topic,
          asks Claude for recommendations, writes to Content_Topics, emails insights.
    CONTENT-02: Multi-Format Generator (Webhook trigger)
        - Accepts content ID + target formats, fetches source content, generates
          blog/social/newsletter/video-script variants, writes to Content_Variants.

Usage:
    python tools/deploy_content_agent.py build              # Build all JSONs
    python tools/deploy_content_agent.py build content01    # Build CONTENT-01 only
    python tools/deploy_content_agent.py deploy             # Build + Deploy (inactive)
    python tools/deploy_content_agent.py activate           # Build + Deploy + Activate
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
MARKETING_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_CONTENT_CALENDAR = os.getenv("SEO_TABLE_CONTENT_CALENDAR", "tblf3QGxX9K1y2h2H")
TABLE_CONTENT_TOPICS = os.getenv("SEO_TABLE_CONTENT_TOPICS", "tbljaHug3yScfhrcf")
TABLE_CONTENT_VARIANTS = os.getenv("CONTENT_TABLE_VARIANTS", "REPLACE_AFTER_SETUP")

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

CONTENT01_AGGREGATE_CODE = r"""
// Aggregate engagement scores by content type and topic from last 30 days
const items = $input.all();

const byType = {};
const byTopic = {};

for (const item of items) {
  const d = item.json;
  const contentType = d['Content Type'] || d.Type || 'Unknown';
  const topic = d.Topic || d.Category || 'General';
  const engagement = (d['Engagement Score'] || d.Engagement || 0);
  const impressions = d.Impressions || d.Views || 0;
  const clicks = d.Clicks || 0;
  const shares = d.Shares || 0;
  const comments = d.Comments || 0;

  // Aggregate by content type
  if (!byType[contentType]) {
    byType[contentType] = {
      type: contentType,
      totalEngagement: 0,
      totalImpressions: 0,
      totalClicks: 0,
      totalShares: 0,
      totalComments: 0,
      count: 0,
    };
  }
  byType[contentType].totalEngagement += engagement;
  byType[contentType].totalImpressions += impressions;
  byType[contentType].totalClicks += clicks;
  byType[contentType].totalShares += shares;
  byType[contentType].totalComments += comments;
  byType[contentType].count++;

  // Aggregate by topic
  if (!byTopic[topic]) {
    byTopic[topic] = {
      topic,
      totalEngagement: 0,
      totalImpressions: 0,
      totalClicks: 0,
      count: 0,
    };
  }
  byTopic[topic].totalEngagement += engagement;
  byTopic[topic].totalImpressions += impressions;
  byTopic[topic].totalClicks += clicks;
  byTopic[topic].count++;
}

// Compute averages and sort
const typeStats = Object.values(byType).map(t => ({
  ...t,
  avgEngagement: t.count > 0 ? Math.round(t.totalEngagement / t.count * 100) / 100 : 0,
  engagementRate: t.totalImpressions > 0
    ? Math.round(t.totalEngagement / t.totalImpressions * 10000) / 100
    : 0,
})).sort((a, b) => b.avgEngagement - a.avgEngagement);

const topicStats = Object.values(byTopic).map(t => ({
  ...t,
  avgEngagement: t.count > 0 ? Math.round(t.totalEngagement / t.count * 100) / 100 : 0,
  engagementRate: t.totalImpressions > 0
    ? Math.round(t.totalEngagement / t.totalImpressions * 10000) / 100
    : 0,
})).sort((a, b) => b.avgEngagement - a.avgEngagement);

const totalPieces = items.length;
const topTypes = typeStats.slice(0, 5);
const topTopics = topicStats.slice(0, 5);
const bottomTypes = typeStats.length > 3 ? typeStats.slice(-2) : [];
const bottomTopics = topicStats.length > 3 ? topicStats.slice(-2) : [];

return {
  json: {
    totalContentPieces: totalPieces,
    periodDays: 30,
    typeStats,
    topicStats,
    topTypes: topTypes.map(t => t.type),
    topTopics: topTopics.map(t => t.topic),
    bottomTypes: bottomTypes.map(t => t.type),
    bottomTopics: bottomTopics.map(t => t.topic),
    generatedAt: new Date().toISOString(),
  }
};
""".strip()

CONTENT02_PARSE_INPUT_CODE = r"""
// Parse webhook input: content ID + target formats
const input = $input.first().json;
const body = input.body || input;

const contentId = body.contentId || body.content_id || body.id || '';
const targetFormats = body.formats || body.targetFormats
  || ['blog', 'social', 'newsletter', 'video-script'];
const tone = body.tone || 'professional';
const audience = body.audience || 'business owners';

if (!contentId) {
  throw new Error('Missing required field: contentId. Send {"contentId": "recXXX", "formats": ["blog","social"]}');
}

return {
  json: {
    contentId,
    targetFormats: Array.isArray(targetFormats)
      ? targetFormats
      : targetFormats.split(',').map(f => f.trim()),
    tone,
    audience,
  }
};
""".strip()

CONTENT02_SPLIT_VARIANTS_CODE = r"""
// Split AI-generated variants into separate items for Airtable batch create
const response = $input.first().json;
const aiText = (response.choices && response.choices[0])
  ? response.choices[0].message.content
  : '';

const sourceData = $('Read Source Content').first().json;
const params = $('Parse Input').first().json;
const contentId = params.contentId;
const sourceTitle = sourceData.Title || sourceData.Name || 'Untitled';

// Parse variants from AI response (expects JSON array or sectioned text)
let variants = [];
try {
  // Try parsing as JSON first (with or without code fences)
  const jsonMatch = aiText.match(/```json\s*([\s\S]*?)```/) || aiText.match(/\[[\s\S]*\]/);
  if (jsonMatch) {
    variants = JSON.parse(jsonMatch[1] || jsonMatch[0]);
  }
} catch (e) {
  // Fall back to section-based parsing
}

if (variants.length === 0) {
  // Parse sections delimited by format headers (e.g., "## Blog", "## Social")
  const sections = aiText.split(/^##\s+/m).filter(s => s.trim());
  for (const section of sections) {
    const lines = section.trim().split('\n');
    const format = lines[0].trim().replace(/[:#]/g, '').trim();
    const content = lines.slice(1).join('\n').trim();
    if (format && content) {
      variants.push({ format, content });
    }
  }
}

// If still empty, return the whole response as a single variant
if (variants.length === 0) {
  variants.push({ format: 'general', content: aiText });
}

return variants.map((v, idx) => ({
  json: {
    'Source Content ID': contentId,
    'Source Title': sourceTitle,
    'Format': v.format || v.type || `variant_${idx}`,
    'Generated Content': v.content || v.text || '',
    'Tone': params.tone,
    'Audience': params.audience,
    'Status': 'Draft',
    'Generated At': new Date().toISOString(),
  }
}));
""".strip()


# ======================================================================
# CONTENT-01: Performance Feedback Loop
# ======================================================================

def build_content01_nodes():
    """Build nodes for CONTENT-01: Performance Feedback Loop (Wed 09:00 SAST = 07:00 UTC)."""
    nodes = []

    # 1. Schedule Trigger (Wed 09:00 SAST = 07:00 UTC)
    nodes.append({
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 7 * * 3"}]}
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Read Content Calendar (last 30 days published)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CONTENT_CALENDAR, "mode": "id"},
            "filterByFormula": "=AND({Status} = 'Published', IS_AFTER({Published Date}, DATEADD(TODAY(), -30, 'days')))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Published Content",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [460, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 3. Aggregate Engagement (Code node)
    nodes.append({
        "parameters": {"jsCode": CONTENT01_AGGREGATE_CODE},
        "id": uid(),
        "name": "Aggregate Engagement",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [720, 300],
    })

    # 4. AI Analysis (OpenRouter HTTP - Claude Sonnet)
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514",
  "max_tokens": 1500,
  "messages": [
    {
      "role": "system",
      "content": "You are the AVM Content Performance Analyst. Analyze 30-day content engagement data and generate actionable recommendations. Focus on: 1) Which content types perform best and should be scaled, 2) Which topics resonate most with the audience, 3) Underperforming areas to deprioritize or improve, 4) 3-5 specific new content topic suggestions based on patterns. Format as a structured brief with sections. Currency is ZAR (R). Keep under 400 words."
    },
    {
      "role": "user",
      "content": "30-Day Content Performance Summary:\\n\\nTotal pieces analyzed: {{ $json.totalContentPieces }}\\n\\nBy Content Type:\\n{{ JSON.stringify($json.typeStats, null, 2) }}\\n\\nBy Topic:\\n{{ JSON.stringify($json.topicStats, null, 2) }}\\n\\nTop performing types: {{ $json.topTypes.join(', ') || 'N/A' }}\\nTop performing topics: {{ $json.topTopics.join(', ') || 'N/A' }}\\nBottom performing types: {{ $json.bottomTypes.join(', ') || 'N/A' }}\\nBottom performing topics: {{ $json.bottomTopics.join(', ') || 'N/A' }}\\n\\nProvide content strategy recommendations and suggest new topics."
    }
  ]
}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Content Analyst",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [960, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # 5. Extract AI Recommendations (Code node)
    nodes.append({
        "parameters": {
            "jsCode": """// Extract AI recommendation and prepare Airtable record
const response = $input.first().json;
const recommendation = (response.choices && response.choices[0])
  ? response.choices[0].message.content
  : 'AI recommendation unavailable.';

const stats = $('Aggregate Engagement').first().json;

return {
  json: {
    recommendation,
    topTypes: stats.topTypes,
    topTopics: stats.topTopics,
    bottomTypes: stats.bottomTypes,
    bottomTopics: stats.bottomTopics,
    totalContentPieces: stats.totalContentPieces,
    generatedAt: new Date().toISOString(),
  }
};""",
        },
        "id": uid(),
        "name": "Extract Recommendations",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1200, 300],
    })

    # 6. Create Content Topics record (Airtable create - AI recommendations)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CONTENT_TOPICS, "mode": "id"},
            "columns": {
                "value": {
                    "Topic": "=AI Recommendations - {{ $now.format('yyyy-MM-dd') }}",
                    "Source": "Performance Feedback Loop",
                    "AI Recommendation": "={{ $json.recommendation }}",
                    "Top Types": "={{ $json.topTypes.join(', ') }}",
                    "Top Topics": "={{ $json.topTopics.join(', ') }}",
                    "Content Pieces Analyzed": "={{ $json.totalContentPieces }}",
                    "Status": "New",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Save to Content Topics",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1440, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 7. Send Insights Email (Gmail)
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=AVM Content Performance Insights - {{ $now.format('yyyy-MM-dd') }}",
            "emailType": "html",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<div style="background: #FF6D5A; padding: 20px; text-align: center;">
<h1 style="color: white; margin: 0;">Content Performance Feedback</h1>
<p style="color: white; margin: 5px 0;">30-Day Analysis | {{ $now.format('yyyy-MM-dd') }}</p>
</div>
<div style="padding: 20px;">
<h2 style="color: #333;">AI Recommendations</h2>
<div style="background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 20px; white-space: pre-wrap;">{{ $('Extract Recommendations').first().json.recommendation }}</div>
<h2 style="color: #333;">Key Metrics</h2>
<ul>
<li><strong>Content pieces analyzed:</strong> {{ $('Extract Recommendations').first().json.totalContentPieces }}</li>
<li><strong>Top content types:</strong> {{ $('Extract Recommendations').first().json.topTypes.join(', ') || 'N/A' }}</li>
<li><strong>Top topics:</strong> {{ $('Extract Recommendations').first().json.topTopics.join(', ') || 'N/A' }}</li>
<li><strong>Underperforming types:</strong> {{ $('Extract Recommendations').first().json.bottomTypes.join(', ') || 'None' }}</li>
<li><strong>Underperforming topics:</strong> {{ $('Extract Recommendations').first().json.bottomTopics.join(', ') || 'None' }}</li>
</ul>
</div>
<div style="background: #f0f0f0; padding: 15px; text-align: center; font-size: 12px; color: #666;">
Generated by AVM Content Agent | {{ $now.format('yyyy-MM-dd HH:mm') }}
</div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Send Insights Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1680, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_content01_connections(nodes):
    """Build connections for CONTENT-01."""
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Published Content", "type": "main", "index": 0},
        ]]},
        "Read Published Content": {"main": [[
            {"node": "Aggregate Engagement", "type": "main", "index": 0},
        ]]},
        "Aggregate Engagement": {"main": [[
            {"node": "AI Content Analyst", "type": "main", "index": 0},
        ]]},
        "AI Content Analyst": {"main": [[
            {"node": "Extract Recommendations", "type": "main", "index": 0},
        ]]},
        "Extract Recommendations": {"main": [[
            {"node": "Save to Content Topics", "type": "main", "index": 0},
        ]]},
        "Save to Content Topics": {"main": [[
            {"node": "Send Insights Email", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# CONTENT-02: Multi-Format Generator
# ======================================================================

def build_content02_nodes():
    """Build nodes for CONTENT-02: Multi-Format Generator (Webhook trigger)."""
    nodes = []

    # 1. Webhook Trigger
    nodes.append({
        "parameters": {
            "httpMethod": "POST",
            "path": "content-generate",
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

    # 2. Parse Input (Code node - extract contentId + formats)
    nodes.append({
        "parameters": {"jsCode": CONTENT02_PARSE_INPUT_CODE},
        "id": uid(),
        "name": "Parse Input",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [460, 300],
    })

    # 3. Read Source Content (Airtable search by record ID)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CONTENT_CALENDAR, "mode": "id"},
            "filterByFormula": "=RECORD_ID() = '{{ $json.contentId }}'",
            "options": {},
        },
        "id": uid(),
        "name": "Read Source Content",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [720, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 4. AI Multi-Format Generator (OpenRouter HTTP - Claude Sonnet)
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={
  "model": "anthropic/claude-sonnet-4-20250514",
  "max_tokens": 3000,
  "messages": [
    {
      "role": "system",
      "content": "You are the AVM Multi-Format Content Generator. Given source content, generate variants for the requested formats. Output a JSON array where each element has 'format' and 'content' keys. Supported formats: blog (800-1200 words SEO-optimized article), social (platform-optimized posts for Instagram/LinkedIn/Twitter with hashtags), newsletter (email-friendly summary with CTA), video-script (90-second script with scene directions and talking points). Maintain brand voice: professional, approachable, South African business context. Currency is ZAR (R)."
    },
    {
      "role": "user",
      "content": "Source Content:\\nTitle: {{ $json.Title || $json.Name || 'Untitled' }}\\nType: {{ $json['Content Type'] || $json.Type || 'Article' }}\\nBody: {{ ($json.Content || $json.Body || $json.Description || 'No content body available').substring(0, 4000) }}\\nTopic: {{ $json.Topic || $json.Category || 'General' }}\\n\\nTarget formats: {{ $('Parse Input').first().json.targetFormats.join(', ') }}\\nTone: {{ $('Parse Input').first().json.tone }}\\nAudience: {{ $('Parse Input').first().json.audience }}\\n\\nGenerate all requested format variants. Return as a JSON array: ```json\\n[{\"format\": \"...\", \"content\": \"...\"}]\\n```"
    }
  ]
}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Format Generator",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [960, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # 5. Split Variants (Code node - parse AI response into individual items)
    nodes.append({
        "parameters": {"jsCode": CONTENT02_SPLIT_VARIANTS_CODE},
        "id": uid(),
        "name": "Split Variants",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1200, 300],
    })

    # 6. Create Content Variants records (Airtable batch create)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CONTENT_VARIANTS, "mode": "id"},
            "columns": {
                "value": {
                    "Source Content ID": "={{ $json['Source Content ID'] }}",
                    "Source Title": "={{ $json['Source Title'] }}",
                    "Format": "={{ $json.Format }}",
                    "Generated Content": "={{ $json['Generated Content'] }}",
                    "Tone": "={{ $json.Tone }}",
                    "Audience": "={{ $json.Audience }}",
                    "Status": "={{ $json.Status }}",
                    "Generated At": "={{ $json['Generated At'] }}",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Save Content Variants",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1440, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 7. Respond to Webhook
    nodes.append({
        "parameters": {
            "respondWith": "json",
            "responseBody": """={
  "success": true,
  "contentId": "{{ $('Parse Input').first().json.contentId }}",
  "variantsGenerated": {{ $('Split Variants').all().length }},
  "formats": {{ JSON.stringify($('Split Variants').all().map(i => i.json.Format)) }},
  "message": "Content variants generated and saved to Airtable"
}""",
            "options": {},
        },
        "id": uid(),
        "name": "Respond to Webhook",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [1680, 300],
    })

    return nodes


def build_content02_connections(nodes):
    """Build connections for CONTENT-02."""
    return {
        "Webhook": {"main": [[
            {"node": "Parse Input", "type": "main", "index": 0},
        ]]},
        "Parse Input": {"main": [[
            {"node": "Read Source Content", "type": "main", "index": 0},
        ]]},
        "Read Source Content": {"main": [[
            {"node": "AI Format Generator", "type": "main", "index": 0},
        ]]},
        "AI Format Generator": {"main": [[
            {"node": "Split Variants", "type": "main", "index": 0},
        ]]},
        "Split Variants": {"main": [[
            {"node": "Save Content Variants", "type": "main", "index": 0},
        ]]},
        "Save Content Variants": {"main": [[
            {"node": "Respond to Webhook", "type": "main", "index": 0},
        ]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "content01": {
        "name": "CONTENT-01 Performance Feedback Loop",
        "build_nodes": build_content01_nodes,
        "build_connections": build_content01_connections,
        "filename": "content01_performance_feedback.json",
        "tags": ["content", "analytics", "feedback-loop", "auto-ops"],
    },
    "content02": {
        "name": "CONTENT-02 Multi-Format Generator",
        "build_nodes": build_content02_nodes,
        "build_connections": build_content02_connections,
        "filename": "content02_multi_format_generator.json",
        "tags": ["content", "generation", "multi-format", "auto-ops"],
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
            "builder": "deploy_content_agent.py",
            "built_at": datetime.now().isoformat(),
        },
    }


def save_workflow(key, workflow_json):
    """Save workflow JSON to disk."""
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "content-agent"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / builder["filename"]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)

    node_count = len(workflow_json["nodes"])
    print(f"  + {builder['name']:<45} ({node_count} nodes) -> {output_path}")
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
        print(f"  + {builder['name']:<45} Deployed -> {wf_id}")

        if activate:
            import time
            time.sleep(2)
            client.activate_workflow(wf_id)
            print(f"    Activated: {wf_id}")

        return wf_id
    else:
        print(f"  - {builder['name']:<45} FAILED to deploy")
        return None


def main():
    if len(sys.argv) < 2:
        print("AVM Content Agent - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_content_agent.py build              # Build all")
        print("  python tools/deploy_content_agent.py build content01    # Build one")
        print("  python tools/deploy_content_agent.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_content_agent.py activate           # Build + Deploy + Activate")
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
    print("AVM CONTENT AGENT - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/content-agent/")

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
