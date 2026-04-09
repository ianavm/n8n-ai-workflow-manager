"""
AVM Autonomous Operations - Marketing Agent Workflow Builder & Deployer

Builds 2 marketing agent workflows for campaign ROI tracking and budget optimization.

Workflows:
    MKT-05: Campaign ROI Tracker (daily 19:00 SAST) - Track per-channel ROI, flag underperformers
    MKT-06: Budget Optimizer (Mon 08:00 SAST) - Analyze 30-day spend, recommend budget reallocation

Usage:
    python tools/deploy_marketing_agent.py build              # Build all JSONs
    python tools/deploy_marketing_agent.py build mkt05        # Build MKT-05 only
    python tools/deploy_marketing_agent.py deploy             # Build + Deploy (inactive)
    python tools/deploy_marketing_agent.py activate           # Build + Deploy + Activate
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

# -- Airtable IDs --
MARKETING_BASE_ID = "apptjjBx34z9340tK"
TABLE_CONTENT_CALENDAR = os.getenv("MARKETING_TABLE_CONTENT", "tblf3QGxX9K1y2h2H")
TABLE_DISTRIBUTION_LOG = os.getenv("MARKETING_TABLE_DISTRIBUTION", "tblLI70ZD0DkJKXvI")
TABLE_SEO_LEADS = "tblwOPTPY85Tcj7NJ"
TABLE_ANALYTICS_SNAPSHOTS = os.getenv("SEO_TABLE_ANALYTICS", "tblPBAnhRf6K1le6F")

# Orchestrator tables (for cross-agent event logging)
ORCH_BASE_ID = os.getenv("ORCH_AIRTABLE_BASE_ID", "REPLACE_AFTER_SETUP")
TABLE_ORCH_EVENTS = os.getenv("ORCH_TABLE_EVENTS", "REPLACE_AFTER_SETUP")

# -- Config --
ALERT_EMAIL = os.getenv("SELFHEALING_ALERT_EMAIL", "ian@anyvisionmedia.com")
OPENROUTER_MODEL = "anthropic/claude-sonnet-4-20250514"

# ROI threshold: content below this ROI_Score gets flagged
ROI_THRESHOLD = 0.5


def uid():
    """Generate UUID for node IDs."""
    return str(uuid.uuid4())


# ======================================================================
# CODE NODE SCRIPTS
# ======================================================================

MKT05_COMPUTE_ROI_CODE = r"""
// Compute cost-per-lead per channel and engagement-to-conversion ratio
const distributionItems = $('Read Distribution Log').all();
const conversionItems = $('Read Lead Conversions').all();

// Aggregate distribution metrics by channel
const channelStats = {};
for (const item of distributionItems) {
  const d = item.json;
  const channel = d.Channel || d.Platform || 'Unknown';
  if (!channelStats[channel]) {
    channelStats[channel] = {
      channel,
      totalPosts: 0,
      totalEngagement: 0,
      totalImpressions: 0,
      contentIds: [],
    };
  }
  channelStats[channel].totalPosts++;
  channelStats[channel].totalEngagement += (d.Engagement || d.Likes || 0) + (d.Shares || 0) + (d.Comments || 0);
  channelStats[channel].totalImpressions += d.Impressions || d.Views || 0;
  if (d['Content ID']) channelStats[channel].contentIds.push(d['Content ID']);
}

// Count conversions
const totalConversions = conversionItems.length;
const conversionsBySource = {};
for (const item of conversionItems) {
  const src = item.json.Source || item.json.Channel || 'Direct';
  conversionsBySource[src] = (conversionsBySource[src] || 0) + 1;
}

// Compute per-channel ROI metrics
const results = [];
for (const [channel, stats] of Object.entries(channelStats)) {
  const channelConversions = conversionsBySource[channel] || 0;
  const engagementRate = stats.totalImpressions > 0
    ? (stats.totalEngagement / stats.totalImpressions * 100).toFixed(2)
    : 0;
  const conversionRate = stats.totalEngagement > 0
    ? (channelConversions / stats.totalEngagement * 100).toFixed(2)
    : 0;
  const costPerLead = channelConversions > 0
    ? (stats.totalPosts / channelConversions).toFixed(2)
    : 'N/A';

  // ROI score: 0-1 composite (engagement weight 0.4, conversion weight 0.6)
  const engScore = Math.min(parseFloat(engagementRate) / 10, 1);
  const convScore = Math.min(parseFloat(conversionRate) / 5, 1);
  const roiScore = (engScore * 0.4 + convScore * 0.6).toFixed(3);

  results.push({
    json: {
      channel,
      totalPosts: stats.totalPosts,
      totalEngagement: stats.totalEngagement,
      totalImpressions: stats.totalImpressions,
      engagementRate: parseFloat(engagementRate),
      channelConversions,
      conversionRate: parseFloat(conversionRate),
      costPerLead,
      roiScore: parseFloat(roiScore),
      contentIds: stats.contentIds,
      belowThreshold: parseFloat(roiScore) < ##ROI_THRESHOLD##,
    }
  });
}

// If no distribution data, return a placeholder
if (results.length === 0) {
  results.push({
    json: {
      channel: 'None',
      totalPosts: 0,
      roiScore: 0,
      belowThreshold: false,
      message: 'No distribution data in last 24 hours',
    }
  });
}

return results;
""".strip()

MKT06_COMPUTE_BUDGET_CODE = r"""
// Compute per-channel ROI from 30-day analytics and identify top/bottom performers
const analyticsItems = $('Read Analytics Snapshots').all();
const tokenData = $('Read Token Usage').first().json;

// Aggregate by channel/platform
const channelPerf = {};
for (const item of analyticsItems) {
  const d = item.json;
  const channel = d.Platform || d.Channel || 'Organic';
  if (!channelPerf[channel]) {
    channelPerf[channel] = {
      channel,
      totalEngagement: 0,
      totalImpressions: 0,
      totalContent: 0,
      dates: [],
    };
  }
  channelPerf[channel].totalEngagement += d.Engagement || d['Total Engagement'] || 0;
  channelPerf[channel].totalImpressions += d.Impressions || d.Pageviews || 0;
  channelPerf[channel].totalContent++;
  if (d.Date || d['Snapshot Date']) {
    channelPerf[channel].dates.push(d.Date || d['Snapshot Date']);
  }
}

// Compute engagement rate and rank
const channels = Object.values(channelPerf).map(c => {
  c.engagementRate = c.totalImpressions > 0
    ? (c.totalEngagement / c.totalImpressions * 100)
    : 0;
  return c;
});

channels.sort((a, b) => b.engagementRate - a.engagementRate);

const topPerformers = channels.slice(0, 3).map(c => c.channel);
const bottomPerformers = channels.length > 3
  ? channels.slice(-2).map(c => c.channel)
  : [];

// Token/cost summary
const totalTokens = tokenData.totalTokens || 0;
const estimatedCostZAR = (totalTokens / 1000 * 0.05).toFixed(2);

return {
  json: {
    periodDays: 30,
    channelCount: channels.length,
    channels: channels.map(c => ({
      channel: c.channel,
      engagement: c.totalEngagement,
      impressions: c.totalImpressions,
      engagementRate: Math.round(c.engagementRate * 100) / 100,
      contentPieces: c.totalContent,
    })),
    topPerformers,
    bottomPerformers,
    totalTokensUsed: totalTokens,
    estimatedAICostZAR: parseFloat(estimatedCostZAR),
    generatedAt: new Date().toISOString(),
  }
};
""".strip()


# ======================================================================
# MKT-05: Campaign ROI Tracker
# ======================================================================

def build_mkt05_nodes():
    """Build nodes for MKT-05: Campaign ROI Tracker (daily 19:00 SAST = 17:00 UTC)."""
    nodes = []

    # 1. Schedule Trigger (daily 19:00 SAST = 17:00 UTC)
    nodes.append({
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 17 * * *"}]}
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Read Distribution Log (Airtable search last 24h)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_DISTRIBUTION_LOG, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Published Date}, DATEADD(TODAY(), -1, 'days'))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Distribution Log",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [460, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 3. Read Lead Conversions (Airtable search SEO leads with status=Converted)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_SEO_LEADS, "mode": "id"},
            "filterByFormula": "=AND({Status} = 'Converted', IS_AFTER({Converted Date}, DATEADD(TODAY(), -1, 'days')))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Lead Conversions",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [460, 420],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 4. Compute ROI (Code node)
    code = MKT05_COMPUTE_ROI_CODE.replace("##ROI_THRESHOLD##", str(ROI_THRESHOLD))
    nodes.append({
        "parameters": {"jsCode": code},
        "id": uid(),
        "name": "Compute ROI",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [720, 300],
    })

    # 5. Update Content Calendar with ROI_Score (Airtable update)
    nodes.append({
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_CONTENT_CALENDAR, "mode": "id"},
            "columns": {
                "value": {
                    "ROI_Score": "={{ $json.roiScore }}",
                    "Engagement Rate": "={{ $json.engagementRate }}",
                    "Conversion Rate": "={{ $json.conversionRate }}",
                }
            },
            "options": {},
            "matchingColumns": ["Content ID"],
        },
        "id": uid(),
        "name": "Update Content ROI",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [960, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 6. If any content ROI below threshold
    nodes.append({
        "parameters": {
            "conditions": {
                "conditions": [
                    {
                        "leftValue": "={{ $json.belowThreshold }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "equals"},
                    }
                ],
            },
            "options": {},
        },
        "id": uid(),
        "name": "If Low ROI",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [1200, 300],
    })

    # 7. AI Agent: Suggest content strategy adjustments (OpenRouter - Claude)
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
  "max_tokens": 1200,
  "messages": [
    {
      "role": "system",
      "content": "You are the AVM Marketing Intelligence Agent. Analyze content ROI data and suggest specific, actionable content strategy adjustments. Focus on: 1) Which channels to double-down on, 2) Which content types to reduce, 3) Optimal posting times based on engagement patterns. Keep response under 300 words. Currency is ZAR (R)."
    },
    {
      "role": "user",
      "content": "Content ROI Analysis (last 24h):\\n\\nChannel performance: {{ JSON.stringify($('Compute ROI').all().map(i => i.json)) }}\\n\\nChannels below ROI threshold ({{ """ + str(ROI_THRESHOLD) + """ }}): {{ $('Compute ROI').all().filter(i => i.json.belowThreshold).map(i => i.json.channel).join(', ') || 'None' }}\\n\\nProvide strategy adjustment recommendations."
    }
  ]
}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Strategy Advisor",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1440, 200],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # 8. Extract AI response (Code)
    nodes.append({
        "parameters": {
            "jsCode": """// Extract AI recommendation text
const response = $input.first().json;
const recommendation = (response.choices && response.choices[0])
  ? response.choices[0].message.content
  : 'AI recommendation unavailable.';

const roiData = $('Compute ROI').all().map(i => i.json);
const lowROI = roiData.filter(c => c.belowThreshold).map(c => c.channel);

return {
  json: {
    recommendation,
    lowROIChannels: lowROI,
    channelCount: roiData.length,
    timestamp: new Date().toISOString(),
  }
};""",
        },
        "id": uid(),
        "name": "Extract Recommendation",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1680, 200],
    })

    # 9. Log to Orchestrator Events (Airtable create)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ORCH_EVENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Event ID": "=evt_mkt05_{{ $now.toFormat('yyyyMMddHHmmss') }}",
                    "Event Type": "kpi_update",
                    "Source Agent": "agent_marketing",
                    "Target Agent": "agent_orchestrator",
                    "Priority": "P3",
                    "Status": "Completed",
                    "Payload": "={{ JSON.stringify({ lowROIChannels: $json.lowROIChannels, channelCount: $json.channelCount, recommendation: $json.recommendation.substring(0, 500) }) }}",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log to Orchestrator",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1920, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 10. Log no-action event (false branch of If)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ORCH_EVENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Event ID": "=evt_mkt05_ok_{{ $now.toFormat('yyyyMMddHHmmss') }}",
                    "Event Type": "kpi_update",
                    "Source Agent": "agent_marketing",
                    "Target Agent": "agent_orchestrator",
                    "Priority": "P4",
                    "Status": "Completed",
                    "Payload": "=All channels above ROI threshold. No action needed.",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log OK Status",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1440, 420],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    return nodes


def build_mkt05_connections(nodes):
    """Build connections for MKT-05."""
    return {
        "Schedule Trigger": {"main": [
            [
                {"node": "Read Distribution Log", "type": "main", "index": 0},
                {"node": "Read Lead Conversions", "type": "main", "index": 0},
            ],
        ]},
        "Read Distribution Log": {"main": [[{"node": "Compute ROI", "type": "main", "index": 0}]]},
        "Read Lead Conversions": {"main": [[{"node": "Compute ROI", "type": "main", "index": 0}]]},
        "Compute ROI": {"main": [[{"node": "Update Content ROI", "type": "main", "index": 0}]]},
        "Update Content ROI": {"main": [[{"node": "If Low ROI", "type": "main", "index": 0}]]},
        "If Low ROI": {"main": [
            [{"node": "AI Strategy Advisor", "type": "main", "index": 0}],
            [{"node": "Log OK Status", "type": "main", "index": 0}],
        ]},
        "AI Strategy Advisor": {"main": [[{"node": "Extract Recommendation", "type": "main", "index": 0}]]},
        "Extract Recommendation": {"main": [[{"node": "Log to Orchestrator", "type": "main", "index": 0}]]},
    }


# ======================================================================
# MKT-06: Budget Optimizer
# ======================================================================

def build_mkt06_nodes():
    """Build nodes for MKT-06: Budget Optimizer (Mon 08:00 SAST = 06:00 UTC)."""
    nodes = []

    # 1. Schedule Trigger (Mon 08:00 SAST = 06:00 UTC)
    nodes.append({
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 6 * * 1"}]}
        },
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [220, 300],
    })

    # 2. Read Analytics Snapshots (last 30 days)
    nodes.append({
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "value": MARKETING_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ANALYTICS_SNAPSHOTS, "mode": "id"},
            "filterByFormula": "=IS_AFTER({Snapshot Date}, DATEADD(TODAY(), -30, 'days'))",
            "returnAll": True,
            "options": {},
        },
        "id": uid(),
        "name": "Read Analytics Snapshots",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [460, 200],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "alwaysOutputData": True,
    })

    # 3. Read Token Usage (placeholder Set node)
    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "totalTokens", "value": "0", "type": "number"},
                    {"id": uid(), "name": "periodDays", "value": "30", "type": "number"},
                    {"id": uid(), "name": "source", "value": "placeholder - connect to OpenRouter usage API", "type": "string"},
                ]
            },
            "options": {},
        },
        "id": uid(),
        "name": "Read Token Usage",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [460, 420],
    })

    # 4. Compute Budget Analysis (Code)
    nodes.append({
        "parameters": {"jsCode": MKT06_COMPUTE_BUDGET_CODE},
        "id": uid(),
        "name": "Compute Budget Analysis",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [720, 300],
    })

    # 5. AI Agent: Generate budget reallocation recommendations (OpenRouter - Claude)
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
      "content": "You are the AVM Budget Optimization Agent. Analyze 30-day channel performance data and recommend budget reallocation. Consider: 1) Engagement rate trends per channel, 2) Cost efficiency (AI token spend vs output), 3) Recommended % allocation per channel. Format as a clear executive brief with a budget table. Currency is ZAR (R). Keep under 400 words."
    },
    {
      "role": "user",
      "content": "30-Day Marketing Performance Analysis:\\n\\n{{ JSON.stringify($json) }}\\n\\nTop performers: {{ $json.topPerformers.join(', ') }}\\nBottom performers: {{ $json.bottomPerformers.join(', ') || 'N/A' }}\\nAI cost (30d): R{{ $json.estimatedAICostZAR }}\\n\\nGenerate budget reallocation recommendations."
    }
  ]
}""",
            "options": {},
        },
        "id": uid(),
        "name": "AI Budget Advisor",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [960, 300],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
    })

    # 6. Create Orchestrator Event (Airtable create with event_type=kpi_update)
    nodes.append({
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "value": ORCH_BASE_ID, "mode": "id"},
            "table": {"__rl": True, "value": TABLE_ORCH_EVENTS, "mode": "id"},
            "columns": {
                "value": {
                    "Event ID": "=evt_mkt06_{{ $now.toFormat('yyyyMMddHHmmss') }}",
                    "Event Type": "kpi_update",
                    "Source Agent": "agent_marketing",
                    "Target Agent": "agent_orchestrator",
                    "Priority": "P3",
                    "Status": "Completed",
                    "Payload": "={{ JSON.stringify({ type: 'budget_optimization', topPerformers: $('Compute Budget Analysis').first().json.topPerformers, channelCount: $('Compute Budget Analysis').first().json.channelCount }) }}",
                }
            },
            "options": {},
        },
        "id": uid(),
        "name": "Log KPI Event",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1200, 300],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
    })

    # 7. Format and Send Email Summary
    nodes.append({
        "parameters": {
            "sendTo": ALERT_EMAIL,
            "subject": "=AVM Weekly Budget Optimization Report - {{ $now.toFormat('yyyy-MM-dd') }}",
            "emailType": "html",
            "message": """=<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<div style="background: #FF6D5A; padding: 20px; text-align: center;">
<h1 style="color: white; margin: 0;">Weekly Budget Optimization</h1>
<p style="color: white; margin: 5px 0;">30-Day Performance Analysis</p>
</div>
<div style="padding: 20px;">
<h2 style="color: #333;">AI Recommendation</h2>
<div style="background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 20px; white-space: pre-wrap;">{{ $('AI Budget Advisor').first().json.choices[0].message.content }}</div>
<h2 style="color: #333;">Key Metrics</h2>
<ul>
<li><strong>Channels analyzed:</strong> {{ $('Compute Budget Analysis').first().json.channelCount }}</li>
<li><strong>Top performers:</strong> {{ $('Compute Budget Analysis').first().json.topPerformers.join(', ') }}</li>
<li><strong>AI cost (30d):</strong> R{{ $('Compute Budget Analysis').first().json.estimatedAICostZAR }}</li>
</ul>
</div>
<div style="background: #f0f0f0; padding: 15px; text-align: center; font-size: 12px; color: #666;">
Generated by AVM Marketing Agent | {{ $now.toFormat('yyyy-MM-dd HH:mm') }}
</div>
</div>""",
            "options": {},
        },
        "id": uid(),
        "name": "Send Budget Report",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [1440, 300],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
    })

    return nodes


def build_mkt06_connections(nodes):
    """Build connections for MKT-06."""
    return {
        "Schedule Trigger": {"main": [
            [
                {"node": "Read Analytics Snapshots", "type": "main", "index": 0},
                {"node": "Read Token Usage", "type": "main", "index": 0},
            ],
        ]},
        "Read Analytics Snapshots": {"main": [[{"node": "Compute Budget Analysis", "type": "main", "index": 0}]]},
        "Read Token Usage": {"main": [[{"node": "Compute Budget Analysis", "type": "main", "index": 0}]]},
        "Compute Budget Analysis": {"main": [[{"node": "AI Budget Advisor", "type": "main", "index": 0}]]},
        "AI Budget Advisor": {"main": [[{"node": "Log KPI Event", "type": "main", "index": 0}]]},
        "Log KPI Event": {"main": [[{"node": "Send Budget Report", "type": "main", "index": 0}]]},
    }


# ======================================================================
# WORKFLOW ASSEMBLY & DEPLOYMENT
# ======================================================================

WORKFLOW_BUILDERS = {
    "mkt05": {
        "name": "MKT-05 Campaign ROI Tracker",
        "build_nodes": build_mkt05_nodes,
        "build_connections": build_mkt05_connections,
        "filename": "mkt05_campaign_roi_tracker.json",
        "tags": ["marketing", "roi", "analytics", "auto-ops"],
    },
    "mkt06": {
        "name": "MKT-06 Budget Optimizer",
        "build_nodes": build_mkt06_nodes,
        "build_connections": build_mkt06_connections,
        "filename": "mkt06_budget_optimizer.json",
        "tags": ["marketing", "budget", "optimization", "auto-ops"],
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
            "builder": "deploy_marketing_agent.py",
            "built_at": datetime.now().isoformat(),
        },
    }


def save_workflow(key, workflow_json):
    """Save workflow JSON to disk."""
    builder = WORKFLOW_BUILDERS[key]
    output_dir = Path(__file__).parent.parent / "workflows" / "marketing-agent"
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
        print("AVM Marketing Agent - Workflow Builder")
        print()
        print("Usage:")
        print("  python tools/deploy_marketing_agent.py build              # Build all")
        print("  python tools/deploy_marketing_agent.py build mkt05        # Build one")
        print("  python tools/deploy_marketing_agent.py deploy             # Build + Deploy (inactive)")
        print("  python tools/deploy_marketing_agent.py activate           # Build + Deploy + Activate")
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
    print("AVM MARKETING AGENT - WORKFLOW BUILDER")
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
        print("Build complete. Inspect workflows in: workflows/marketing-agent/")

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
