"""
Market Intelligence - Workflow Builder & Deployer

Builds 3 market intelligence workflows using Tavily API for competitive
monitoring, weekly digests, and regulatory alerts.

Workflows:
    INTEL-04: Daily Competitive Scan (Daily 06:00 SAST)
    INTEL-05: Weekly Market Digest (Mon 07:00 SAST)
    INTEL-06: Regulatory Alert (Daily 08:00 SAST)

Usage:
    python tools/deploy_market_intel.py build              # Build all JSONs
    python tools/deploy_market_intel.py build intel04      # Build INTEL-04 only
    python tools/deploy_market_intel.py build intel05      # Build INTEL-05 only
    python tools/deploy_market_intel.py build intel06      # Build INTEL-06 only
    python tools/deploy_market_intel.py deploy             # Build + Deploy (inactive)
    python tools/deploy_market_intel.py activate           # Build + Deploy + Activate
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

# -- Airtable IDs ---------------------------------------------------------

ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "appTCh0EeXQp0XqzW")
TABLE_MARKET_INTEL = os.getenv("MARKET_INTEL_TABLE_ID", "REPLACE_AFTER_SETUP")

# -- AI Config ------------------------------------------------------------

AI_MODEL = "anthropic/claude-sonnet-4-20250514"

# -- Tavily Config ---------------------------------------------------------

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# -- Helpers ---------------------------------------------------------------


def uid():
    """Generate a UUID for node IDs."""
    return str(uuid.uuid4())


# ==================================================================
# INTEL-04: Daily Competitive Scan
# ==================================================================

def build_intel04_nodes():
    """Build nodes for INTEL-04: Daily Competitive Scan (Daily 06:00 SAST = 04:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (04:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 4 * * *",
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

    # -- Set Competitors --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "scanDate",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "competitors",
                        "value": "AnyVision Media, anyvisionmedia.com, digital agency Johannesburg, South Africa marketing agency",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Competitors",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [440, 300],
    })

    # -- Tavily Search (HTTP Request) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://api.tavily.com/search",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "api_key": "{TAVILY_API_KEY}",
  "query": "AnyVision Media OR anyvisionmedia.com competitor digital agency Johannesburg",
  "search_depth": "advanced",
  "max_results": 10
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "Tavily Search",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [660, 300],
    })

    # -- Parse Results (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Parse Tavily search results and extract competitive intelligence
const results = $json.results || [];
const scanDate = $('Set Competitors').first().json.scanDate;

const parsed = results.map(r => ({
  title: r.title || '',
  url: r.url || '',
  snippet: r.content || '',
  score: r.score || 0,
  published_date: r.published_date || '',
}));

// Detect competitor mentions
const competitorKeywords = [
  'anyvision', 'digital agency', 'johannesburg agency',
  'marketing agency south africa', 'web development johannesburg',
  'seo agency gauteng', 'social media agency sa',
];

const findings = parsed.map(r => {
  const textLower = (r.title + ' ' + r.snippet).toLowerCase();
  const mentions = competitorKeywords.filter(k => textLower.includes(k));
  return {
    ...r,
    competitorMentions: mentions,
    isRelevant: mentions.length > 0 || r.score > 0.7,
    scanDate,
  };
}).filter(r => r.isRelevant);

return [{
  json: {
    totalResults: results.length,
    relevantFindings: findings.length,
    findings,
    scanDate,
    rawResultCount: results.length,
  }
}];"""
        },
        "id": uid(),
        "name": "Parse Results",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 300],
    })

    # -- AI Analyze Changes (OpenRouter) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 1500,
  "messages": [
    {{
      "role": "system",
      "content": "You are a competitive intelligence analyst for AnyVision Media, a South African digital agency in Johannesburg. Analyze search results for competitive intelligence. For each finding, classify its Category as one of: Pricing, Service, Hiring, Market, Regulatory. Rate Significance as High, Medium, or Low. Return a JSON array of objects with keys: competitor, finding, category, significance. Be concise and specific."
    }},
    {{
      "role": "user",
      "content": "Analyze these search results for competitive intelligence. Identify new competitor activities, pricing changes, service launches, or market shifts relevant to a South African digital agency:\\n\\n" + JSON.stringify($json.findings, null, 2)
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Analyze Changes",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [1100, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Prepare Records (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Parse AI response and prepare Airtable records
const aiResponse = $json.choices[0].message.content;
const scanDate = $('Parse Results').first().json.scanDate;
const rawData = JSON.stringify($('Parse Results').first().json.findings);

// Try to parse AI JSON response
let findings = [];
try {
  // Extract JSON array from response (may be wrapped in markdown)
  const jsonMatch = aiResponse.match(/\\[[\\ \\s\\S]*\\]/);
  if (jsonMatch) {
    findings = JSON.parse(jsonMatch[0]);
  }
} catch (e) {
  // Fallback: single finding from raw text
  findings = [{
    competitor: 'Unknown',
    finding: aiResponse.substring(0, 500),
    category: 'Market',
    significance: 'Medium',
  }];
}

// Valid categories and significance levels
const validCategories = ['Pricing', 'Service', 'Hiring', 'Market', 'Regulatory'];
const validSignificance = ['High', 'Medium', 'Low'];

const records = findings.map(f => ({
  json: {
    Date: scanDate,
    Source: 'Tavily Competitive Scan',
    Competitor: (f.competitor || 'Unknown').substring(0, 200),
    Finding: (f.finding || '').substring(0, 1000),
    Category: validCategories.includes(f.category) ? f.category : 'Market',
    Significance: validSignificance.includes(f.significance) ? f.significance : 'Medium',
    'Raw Data': rawData.substring(0, 5000),
  }
}));

if (records.length === 0) {
  return [{
    json: {
      Date: scanDate,
      Source: 'Tavily Competitive Scan',
      Competitor: 'None',
      Finding: 'No significant competitive findings today.',
      Category: 'Market',
      Significance: 'Low',
      'Raw Data': rawData.substring(0, 5000),
    }
  }];
}

return records;"""
        },
        "id": uid(),
        "name": "Prepare Records",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 300],
    })

    # -- Write to Airtable --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_MARKET_INTEL, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Date": "={{ $json.Date }}",
                    "Source": "={{ $json.Source }}",
                    "Competitor": "={{ $json.Competitor }}",
                    "Finding": "={{ $json.Finding }}",
                    "Category": "={{ $json.Category }}",
                    "Significance": "={{ $json.Significance }}",
                    "Raw Data": "={{ $json['Raw Data'] }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1540, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Check Significance (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.Significance }}",
                        "rightValue": "High",
                        "operator": {"type": "string", "operation": "equals"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Check Significance",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1760, 300],
    })

    # -- Alert Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=High Significance Alert: {{ $json.Competitor }} - {{ $json.Category }}",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #FF6D5A; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
    <h2 style="margin: 0;">Competitive Intelligence Alert</h2>
    <p style="margin: 4px 0 0; opacity: 0.9;">{{ $json.Date }}</p>
  </div>
  <div style="background: white; padding: 20px; border: 1px solid #e0e0e0; border-radius: 0 0 8px 8px;">
    <p><strong>Competitor:</strong> {{ $json.Competitor }}</p>
    <p><strong>Category:</strong> {{ $json.Category }}</p>
    <p><strong>Significance:</strong> <span style="color: #d32f2f; font-weight: bold;">HIGH</span></p>
    <p><strong>Finding:</strong></p>
    <p style="background: #f5f5f5; padding: 12px; border-radius: 4px;">{{ $json.Finding }}</p>
    <hr style="border: 1px solid #eee;">
    <p style="color: #888; font-size: 11px;">Generated by AVM Market Intelligence | INTEL-04</p>
  </div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Alert Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1980, 200],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## INTEL-04: Daily Competitive Scan\nRuns daily 06:00 SAST. Searches Tavily for competitor\nactivity, AI classifies findings by category & significance,\nwrites to Airtable, emails high-significance alerts.",
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


def build_intel04_connections():
    """Build connections for INTEL-04."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Competitors", "type": "main", "index": 0}]]
        },
        "Set Competitors": {
            "main": [[{"node": "Tavily Search", "type": "main", "index": 0}]]
        },
        "Tavily Search": {
            "main": [[{"node": "Parse Results", "type": "main", "index": 0}]]
        },
        "Parse Results": {
            "main": [[{"node": "AI Analyze Changes", "type": "main", "index": 0}]]
        },
        "AI Analyze Changes": {
            "main": [[{"node": "Prepare Records", "type": "main", "index": 0}]]
        },
        "Prepare Records": {
            "main": [[{"node": "Write to Airtable", "type": "main", "index": 0}]]
        },
        "Write to Airtable": {
            "main": [[{"node": "Check Significance", "type": "main", "index": 0}]]
        },
        "Check Significance": {
            "main": [
                [{"node": "Alert Email", "type": "main", "index": 0}],
                [],
            ]
        },
    }


# ==================================================================
# INTEL-05: Weekly Market Digest
# ==================================================================

def build_intel05_nodes():
    """Build nodes for INTEL-05: Weekly Market Digest (Mon 07:00 SAST = 05:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (Mon 05:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 5 * * 1",
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

    # -- Set Date Range --
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "startDate",
                        "value": "={{ $now.minus({days: 7}).toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "endDate",
                        "value": "={{ $now.toFormat('yyyy-MM-dd') }}",
                        "type": "string",
                    },
                    {
                        "id": uid(),
                        "name": "weekLabel",
                        "value": "={{ $now.minus({days: 7}).toFormat('dd MMM') }} - {{ $now.toFormat('dd MMM yyyy') }}",
                        "type": "string",
                    },
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Set Date Range",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [440, 300],
    })

    # -- Read Week's Findings --
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_MARKET_INTEL, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Date}, '{{ $json.startDate }}')",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Week Findings",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [660, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # -- AI Market Digest (OpenRouter) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 2000,
  "messages": [
    {{
      "role": "system",
      "content": "You are a market intelligence analyst for AnyVision Media, a South African digital agency. Create a weekly market intelligence digest from competitive findings. Group by category (Pricing, Service, Hiring, Market, Regulatory), highlight trends, and provide 3-5 strategic recommendations. Use clear headers and concise bullet points. Currency in ZAR."
    }},
    {{
      "role": "user",
      "content": "Create a weekly market intelligence digest for " + $('Set Date Range').first().json.weekLabel + " from these competitive findings:\\n\\n" + JSON.stringify($input.all().map(i => i.json), null, 2)
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Market Digest",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [880, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Format HTML Report (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Format weekly market digest as branded HTML email
const digest = $json.choices[0].message.content;
const weekLabel = $('Set Date Range').first().json.weekLabel;
const findings = $('Read Week Findings').all().map(i => i.json);

// Count by category
const byCat = {};
for (const f of findings) {
  const cat = f.Category || 'Unknown';
  byCat[cat] = (byCat[cat] || 0) + 1;
}

// Count by significance
const bySig = {};
for (const f of findings) {
  const sig = f.Significance || 'Unknown';
  bySig[sig] = (bySig[sig] || 0) + 1;
}

const catBadges = Object.entries(byCat).map(([cat, count]) =>
  `<span style="display: inline-block; background: #f0f0f0; padding: 4px 10px; border-radius: 12px; margin: 2px; font-size: 12px;">${cat}: ${count}</span>`
).join(' ');

const html = `<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
  <div style="background: #FF6D5A; color: white; padding: 24px; border-radius: 8px 8px 0 0;">
    <h1 style="margin: 0; font-size: 22px;">Weekly Market Intelligence Digest</h1>
    <p style="margin: 5px 0 0; opacity: 0.9; font-size: 14px;">${weekLabel}</p>
  </div>

  <div style="background: white; padding: 24px; border: 1px solid #e0e0e0;">
    <div style="display: flex; gap: 16px; margin-bottom: 20px;">
      <div style="flex: 1; background: #f7f7f7; padding: 16px; border-radius: 6px; text-align: center;">
        <div style="font-size: 28px; font-weight: bold; color: #FF6D5A;">${findings.length}</div>
        <div style="font-size: 12px; color: #888;">Total Findings</div>
      </div>
      <div style="flex: 1; background: #f7f7f7; padding: 16px; border-radius: 6px; text-align: center;">
        <div style="font-size: 28px; font-weight: bold; color: #d32f2f;">${bySig['High'] || 0}</div>
        <div style="font-size: 12px; color: #888;">High Significance</div>
      </div>
      <div style="flex: 1; background: #f7f7f7; padding: 16px; border-radius: 6px; text-align: center;">
        <div style="font-size: 28px; font-weight: bold; color: #f57c00;">${bySig['Medium'] || 0}</div>
        <div style="font-size: 12px; color: #888;">Medium</div>
      </div>
      <div style="flex: 1; background: #f7f7f7; padding: 16px; border-radius: 6px; text-align: center;">
        <div style="font-size: 28px; font-weight: bold; color: #388e3c;">${bySig['Low'] || 0}</div>
        <div style="font-size: 12px; color: #888;">Low</div>
      </div>
    </div>

    <div style="margin-bottom: 16px;">${catBadges}</div>

    <h3 style="color: #333; border-bottom: 2px solid #FF6D5A; padding-bottom: 8px;">Analysis & Recommendations</h3>
    <div style="line-height: 1.6; color: #444;">${digest.replace(/\\n/g, '<br>')}</div>

    <hr style="border: 1px solid #eee; margin: 24px 0;">
    <p style="color: #888; font-size: 11px;">Generated by AVM Market Intelligence | INTEL-05 | ${findings.length} findings analyzed</p>
  </div>
</div>`;

return [{ json: { html, subject: 'Weekly Market Intel Digest - ' + weekLabel } }];"""
        },
        "id": uid(),
        "name": "Format HTML Report",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 300],
    })

    # -- Send Digest Email --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "={{ $json.subject }}",
            "message": "={{ $json.html }}",
            "options": {},
        },
        "id": uid(),
        "name": "Send Digest Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1320, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## INTEL-05: Weekly Market Digest\nRuns Monday 07:00 SAST. Reads last 7 days of\ncompetitive findings from Airtable, AI generates\ngrouped digest with recommendations, branded HTML email.",
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


def build_intel05_connections():
    """Build connections for INTEL-05."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Set Date Range", "type": "main", "index": 0}]]
        },
        "Set Date Range": {
            "main": [[{"node": "Read Week Findings", "type": "main", "index": 0}]]
        },
        "Read Week Findings": {
            "main": [[{"node": "AI Market Digest", "type": "main", "index": 0}]]
        },
        "AI Market Digest": {
            "main": [[{"node": "Format HTML Report", "type": "main", "index": 0}]]
        },
        "Format HTML Report": {
            "main": [[{"node": "Send Digest Email", "type": "main", "index": 0}]]
        },
    }


# ==================================================================
# INTEL-06: Regulatory Alert
# ==================================================================

def build_intel06_nodes():
    """Build nodes for INTEL-06: Regulatory Alert (Daily 08:00 SAST = 06:00 UTC)."""
    nodes = []

    # -- Schedule Trigger (06:00 UTC) --
    nodes.append({
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 6 * * *",
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

    # -- Tavily Search Regulatory (HTTP Request) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://api.tavily.com/search",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "api_key": "{TAVILY_API_KEY}",
  "query": "South Africa POPIA digital marketing regulation law change 2026",
  "search_depth": "advanced",
  "max_results": 10
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "Tavily Search Regulatory",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [440, 300],
    })

    # -- Parse Regulatory Results (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Filter for actual regulatory content
const results = $json.results || [];
const today = DateTime.now().toFormat('yyyy-MM-dd');

const regulatoryKeywords = [
  'popia', 'regulation', 'compliance', 'law', 'legislation',
  'act', 'amendment', 'gazette', 'directive', 'policy',
  'data protection', 'privacy', 'consumer protection',
  'advertising standards', 'asa', 'icasa', 'information regulator',
];

const filtered = results.filter(r => {
  const text = ((r.title || '') + ' ' + (r.content || '')).toLowerCase();
  return regulatoryKeywords.some(kw => text.includes(kw));
});

return [{
  json: {
    scanDate: today,
    totalResults: results.length,
    regulatoryResults: filtered.length,
    hasResults: filtered.length > 0,
    findings: filtered.map(r => ({
      title: r.title || '',
      url: r.url || '',
      content: (r.content || '').substring(0, 1000),
      score: r.score || 0,
      published_date: r.published_date || '',
    })),
  }
}];"""
        },
        "id": uid(),
        "name": "Parse Regulatory Results",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [660, 300],
    })

    # -- Check New Alerts (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $json.regulatoryResults }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Check New Alerts",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [880, 300],
    })

    # -- AI Classify Impact (OpenRouter) --
    nodes.append({
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "HTTP-Referer", "value": "https://anyvisionmedia.com"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f"""={{{{
  "model": "{AI_MODEL}",
  "max_tokens": 1500,
  "messages": [
    {{
      "role": "system",
      "content": "You are a regulatory compliance analyst for AnyVision Media, a South African digital agency. Analyze regulatory search results and classify each finding. For each, provide: regulation (name/reference), description (1-2 sentences), impact (High/Medium/Low), action_required (specific action the business should take). Return a JSON array. Focus on POPIA, advertising standards, digital marketing laws, and data protection regulations relevant to South Africa."
    }},
    {{
      "role": "user",
      "content": "Classify these regulatory findings for business impact:\\n\\n" + JSON.stringify($json.findings, null, 2)
    }}
  ]
}}}}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Classify Impact",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "onError": "continueRegularOutput",
        "position": [1100, 200],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # -- Prepare Alert Records (Code) --
    nodes.append({
        "parameters": {
            "jsCode": """// Parse AI classification and prepare Airtable records
const aiResponse = $json.choices[0].message.content;
const scanDate = $('Parse Regulatory Results').first().json.scanDate;

let classifications = [];
try {
  const jsonMatch = aiResponse.match(/\\[[\\s\\S]*\\]/);
  if (jsonMatch) {
    classifications = JSON.parse(jsonMatch[0]);
  }
} catch (e) {
  classifications = [{
    regulation: 'Unclassified',
    description: aiResponse.substring(0, 500),
    impact: 'Medium',
    action_required: 'Manual review required',
  }];
}

const validImpact = ['High', 'Medium', 'Low'];

const records = classifications.map(c => ({
  json: {
    Date: scanDate,
    Regulation: (c.regulation || 'Unknown').substring(0, 200),
    Description: (c.description || '').substring(0, 1000),
    Impact: validImpact.includes(c.impact) ? c.impact : 'Medium',
    'Action Required': (c.action_required || '').substring(0, 500),
    Status: 'New',
    hasHighImpact: c.impact === 'High',
  }
}));

if (records.length === 0) {
  return [{
    json: {
      Date: scanDate,
      Regulation: 'No findings',
      Description: 'No regulatory changes detected today.',
      Impact: 'Low',
      'Action Required': 'None',
      Status: 'New',
      hasHighImpact: false,
    }
  }];
}

return records;"""
        },
        "id": uid(),
        "name": "Prepare Alert Records",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 200],
    })

    # -- Write Alert to Airtable --
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_MARKET_INTEL, "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Date": "={{ $json.Date }}",
                    "Source": "Regulatory Scan",
                    "Competitor": "={{ $json.Regulation }}",
                    "Finding": "={{ $json.Description }}",
                    "Category": "Regulatory",
                    "Significance": "={{ $json.Impact }}",
                    "Raw Data": "={{ $json['Action Required'] }}",
                },
            },
            "options": {},
        },
        "id": uid(),
        "name": "Write Alert",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1540, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # -- Alert if High Impact (If) --
    nodes.append({
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": ""},
                "conditions": [
                    {
                        "leftValue": "={{ $('Prepare Alert Records').first().json.hasHighImpact }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true"},
                    }
                ],
            },
        },
        "id": uid(),
        "name": "Alert if High Impact",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1760, 200],
    })

    # -- Send High Impact Alert --
    nodes.append({
        "parameters": {
            "sendTo": "ian@anyvisionmedia.com",
            "subject": "=Regulatory Alert: {{ $('Prepare Alert Records').first().json.Regulation }}",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #d32f2f; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
    <h2 style="margin: 0;">Regulatory Alert - HIGH IMPACT</h2>
    <p style="margin: 4px 0 0; opacity: 0.9;">{{ $('Prepare Alert Records').first().json.Date }}</p>
  </div>
  <div style="background: white; padding: 20px; border: 1px solid #e0e0e0; border-radius: 0 0 8px 8px;">
    <p><strong>Regulation:</strong> {{ $('Prepare Alert Records').first().json.Regulation }}</p>
    <p><strong>Description:</strong></p>
    <p style="background: #fff3e0; padding: 12px; border-radius: 4px; border-left: 4px solid #d32f2f;">{{ $('Prepare Alert Records').first().json.Description }}</p>
    <p><strong>Action Required:</strong></p>
    <p style="background: #fce4ec; padding: 12px; border-radius: 4px;">{{ $('Prepare Alert Records').first().json['Action Required'] }}</p>
    <hr style="border: 1px solid #eee;">
    <p style="color: #888; font-size: 11px;">Generated by AVM Market Intelligence | INTEL-06</p>
  </div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Send High Impact Alert",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "position": [1980, 100],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    # -- Sticky Note --
    nodes.append({
        "parameters": {
            "content": "## INTEL-06: Regulatory Alert\nRuns daily 08:00 SAST. Searches Tavily for SA\nregulatory changes (POPIA, digital marketing law),\nAI classifies impact, writes to Airtable,\nemails high-impact alerts immediately.",
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


def build_intel06_connections():
    """Build connections for INTEL-06."""
    return {
        "Schedule Trigger": {
            "main": [[{"node": "Tavily Search Regulatory", "type": "main", "index": 0}]]
        },
        "Tavily Search Regulatory": {
            "main": [[{"node": "Parse Regulatory Results", "type": "main", "index": 0}]]
        },
        "Parse Regulatory Results": {
            "main": [[{"node": "Check New Alerts", "type": "main", "index": 0}]]
        },
        "Check New Alerts": {
            "main": [
                [{"node": "AI Classify Impact", "type": "main", "index": 0}],
                [],
            ]
        },
        "AI Classify Impact": {
            "main": [[{"node": "Prepare Alert Records", "type": "main", "index": 0}]]
        },
        "Prepare Alert Records": {
            "main": [[{"node": "Write Alert", "type": "main", "index": 0}]]
        },
        "Write Alert": {
            "main": [[{"node": "Alert if High Impact", "type": "main", "index": 0}]]
        },
        "Alert if High Impact": {
            "main": [
                [{"node": "Send High Impact Alert", "type": "main", "index": 0}],
                [],
            ]
        },
    }


# ==================================================================
# WORKFLOW DEFINITIONS
# ==================================================================

WORKFLOW_DEFS = {
    "intel04": {
        "name": "Market Intel - Daily Competitive Scan (INTEL-04)",
        "filename": "intel04_competitive_scan.json",
        "build_nodes": build_intel04_nodes,
        "build_connections": build_intel04_connections,
    },
    "intel05": {
        "name": "Market Intel - Weekly Market Digest (INTEL-05)",
        "filename": "intel05_weekly_digest.json",
        "build_nodes": build_intel05_nodes,
        "build_connections": build_intel05_connections,
    },
    "intel06": {
        "name": "Market Intel - Regulatory Alert (INTEL-06)",
        "filename": "intel06_regulatory_alert.json",
        "build_nodes": build_intel06_nodes,
        "build_connections": build_intel06_connections,
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
    output_dir = Path(__file__).parent.parent / "workflows" / "market-intel"
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
    print("MARKET INTELLIGENCE - WORKFLOW BUILDER")
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
    if "REPLACE" in TABLE_MARKET_INTEL:
        missing.append("MARKET_INTEL_TABLE_ID")
    if not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")

    if missing:
        print()
        print("WARNING: Missing configuration:")
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
    print("  1. Create Market_Intel Airtable table (or reuse existing)")
    print("  2. Set env vars: MARKET_INTEL_TABLE_ID, TAVILY_API_KEY")
    print("  3. Open each workflow in n8n UI to verify node connections")
    print("  4. Test INTEL-04 manually -> check Tavily search + Airtable write")
    print("  5. Test INTEL-05 manually -> check weekly digest email")
    print("  6. Test INTEL-06 manually -> check regulatory scan + classification")
    print("  7. Once verified, run with 'activate' to enable schedules")


if __name__ == "__main__":
    main()
