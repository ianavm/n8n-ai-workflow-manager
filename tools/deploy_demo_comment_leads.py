"""
DEMO-03: Comment Lead Miner

Every comment on a social post that says "how much?", "link?", "DM me",
or "need this" is a qualified lead. This workflow scores incoming
comments with Claude, routes high-intent ones to Slack + CRM, and logs
everything to Airtable.

Flow:
    Webhook Trigger / Schedule Trigger
        → Demo Config (Set: DEMO_MODE, post URL, brand)
        → DEMO_MODE Switch
            → DEMO_MODE=1 : Load Fixture Comments (Set, inline seed of 12)
            → DEMO_MODE=0 : Apify IG Comment Scraper (HTTP)
        → Merge
        → Fan Out Comments (Code)
        → Dedupe via Airtable Search (optional; skipped in demo)
        → AI Classify Intent (OpenRouter → Claude)
        → Parse & Fan Out Classifications (Code)
        → Score Router (Switch)
            → high (>=70)  : Log + Slack Alert + AI Reply Draft
            → medium (30-69): Log only (nurture queue)
            → low (<30)    : Log only
        → Aggregate & Respond

Usage:
    python tools/deploy_demo_comment_leads.py build
    python tools/deploy_demo_comment_leads.py deploy
    python tools/deploy_demo_comment_leads.py activate
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from credentials import CRED_AIRTABLE, CRED_OPENROUTER  # noqa: E402

# ==================================================================
# CONFIG
# ==================================================================

WORKFLOW_NAME = "DEMO-03 Comment Lead Miner"
WORKFLOW_FILENAME = "demo03_comment_leads.json"

AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_COMMENT_LEADS = os.getenv(
    "DEMO_TABLE_COMMENT_LEADS", "REPLACE_WITH_TABLE_ID"
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL_CLASSIFY = "anthropic/claude-haiku-4-5"
AI_MODEL_REPLY = "anthropic/claude-sonnet-4-20250514"

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

BRAND_INFO = (
    "AnyVision Media — Johannesburg-based AI automation agency for SA SMEs. "
    "Helps 3-50 person businesses deploy AI tools without a tech team. "
    "Typical package R2k-R15k/mo. Founder: Ian Immelman."
)

# 12 hand-crafted fixture comments covering the realistic spread of intent.
FIXTURE_COMMENTS = [
    {
        "commentId": "fx-001",
        "username": "@kagiso_sme",
        "text": "Wait this is exactly what my cleaning business needs. How much does the full stack cost?",
        "likes": 3,
        "timestamp": "2026-04-20T09:12:03Z",
    },
    {
        "commentId": "fx-002",
        "username": "@thando_creates",
        "text": "Love this. Been following your journey for months 🔥",
        "likes": 7,
        "timestamp": "2026-04-20T09:14:22Z",
    },
    {
        "commentId": "fx-003",
        "username": "@nightshade_ops",
        "text": "DM me the link please, I want to sign up today before month end.",
        "likes": 0,
        "timestamp": "2026-04-20T09:15:48Z",
    },
    {
        "commentId": "fx-004",
        "username": "@marketbuster",
        "text": "lol this won't work for property agents, too niche",
        "likes": 1,
        "timestamp": "2026-04-20T09:17:01Z",
    },
    {
        "commentId": "fx-005",
        "username": "@lindiwe_jhb",
        "text": "Do you offer the onboarding in Zulu? Asking for my mom's salon business.",
        "likes": 2,
        "timestamp": "2026-04-20T09:19:33Z",
    },
    {
        "commentId": "fx-006",
        "username": "@startup_wayne",
        "text": "Can we jump on a demo call this week? Running 12 person team, real pain with admin.",
        "likes": 0,
        "timestamp": "2026-04-20T09:21:05Z",
    },
    {
        "commentId": "fx-007",
        "username": "@random_bot_42",
        "text": "Check out my profile for free crypto giveaway",
        "likes": 0,
        "timestamp": "2026-04-20T09:22:14Z",
    },
    {
        "commentId": "fx-008",
        "username": "@retail_pieter",
        "text": "What's the pricing for a 5-person team?",
        "likes": 4,
        "timestamp": "2026-04-20T09:24:41Z",
    },
    {
        "commentId": "fx-009",
        "username": "@gardeningqueen",
        "text": "Is there a free trial? Would love to test before committing.",
        "likes": 2,
        "timestamp": "2026-04-20T09:26:08Z",
    },
    {
        "commentId": "fx-010",
        "username": "@joburg_dentist",
        "text": "Terrible experience with the last automation tool I tried. How is yours different?",
        "likes": 1,
        "timestamp": "2026-04-20T09:28:15Z",
    },
    {
        "commentId": "fx-011",
        "username": "@samkeleisha",
        "text": "Link in bio?",
        "likes": 1,
        "timestamp": "2026-04-20T09:29:44Z",
    },
    {
        "commentId": "fx-012",
        "username": "@fourways_fitness",
        "text": "Just signed up last week — best decision this year. Bookings up 40% already.",
        "likes": 9,
        "timestamp": "2026-04-20T09:31:22Z",
    },
]


def uid() -> str:
    return str(uuid.uuid4())


# ==================================================================
# NODE BUILDERS
# ==================================================================


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    # --- 1a. Webhook Trigger (demo entrypoint) ---------------------------
    nodes.append({
        "id": uid(),
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [200, 300],
        "webhookId": "demo03-comment-leads",
        "parameters": {
            "httpMethod": "POST",
            "path": "demo03-comment-leads",
            "responseMode": "lastNode",
            "options": {},
        },
    })

    # --- 1b. Schedule Trigger (production polling) -----------------------
    nodes.append({
        "id": uid(),
        "name": "Every 5 Minutes",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [200, 520],
        "parameters": {
            "rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}
        },
    })

    # --- 2. Demo Config --------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Demo Config",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [420, 410],
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "demoMode",
                        "type": "string",
                        "value": "={{ String($json.demoMode ?? '1') }}",
                    },
                    {
                        "id": uid(),
                        "name": "postUrl",
                        "type": "string",
                        "value": "={{ $json.postUrl || 'https://instagram.com/p/DEMO' }}",
                    },
                    {
                        "id": uid(),
                        "name": "platform",
                        "type": "string",
                        "value": "={{ $json.platform || 'instagram' }}",
                    },
                    {"id": uid(), "name": "brandInfo", "type": "string", "value": BRAND_INFO},
                    {"id": uid(), "name": "runId", "type": "string", "value": "={{ 'CL-' + $now.toFormat('yyyyLLdd-HHmmss') }}"},
                    {
                        "id": uid(),
                        "name": "fixtureComments",
                        "type": "string",
                        "value": json.dumps(FIXTURE_COMMENTS),
                    },
                ]
            },
            "options": {},
        },
    })

    # --- 3. DEMO_MODE Switch ---------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "DEMO_MODE Switch",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [640, 410],
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.demoMode }}",
                                    "rightValue": "1",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "demo",
                    },
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.demoMode }}",
                                    "rightValue": "0",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "live",
                    },
                ]
            },
            "options": {"fallbackOutput": 0},
        },
    })

    # --- 4a. Load Fixture Comments ---------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Load Fixture Comments",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [860, 300],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const cfg = $('Demo Config').first().json;
const fx = JSON.parse(cfg.fixtureComments || '[]');
return fx.map(c => ({
  json: {
    ...c,
    postUrl: cfg.postUrl,
    platform: cfg.platform,
    runId: cfg.runId,
    source: 'fixture',
  }
}));""",
        },
    })

    # --- 4b. Apify IG Comment Scraper (live path) -----------------------
    # Uses Apify "instagram-comment-scraper" actor. Requires APIFY_API_TOKEN
    # to be set on the httpHeaderAuth credential named "Apify". For the demo
    # we leave the URL templated; the node errors gracefully without a token.
    nodes.append({
        "id": uid(),
        "name": "Apify Comment Scrape",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [860, 520],
        "parameters": {
            "method": "POST",
            "url": "https://api.apify.com/v2/acts/apify~instagram-comment-scraper/run-sync-get-dataset-items",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "token", "value": "={{ $env.APIFY_API_TOKEN || 'MISSING' }}"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ directUrls: [$json.postUrl], resultsLimit: 50 }) }}",
            "options": {"timeout": 60000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 4b'. Normalise Apify Response ----------------------------------
    nodes.append({
        "id": uid(),
        "name": "Normalise Apify",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1080, 520],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all();
const cfg = $('Demo Config').first().json;
const out = [];
for (const item of items) {
  const rows = Array.isArray(item.json) ? item.json : [item.json];
  for (const r of rows) {
    if (!r || !r.text) continue;
    out.push({
      json: {
        commentId: r.id || r.pk || String(Date.now()) + Math.random(),
        username: r.ownerUsername ? '@' + r.ownerUsername : (r.username || '@unknown'),
        text: r.text,
        likes: r.likesCount || 0,
        timestamp: r.timestamp || new Date().toISOString(),
        postUrl: cfg.postUrl,
        platform: cfg.platform,
        runId: cfg.runId,
        source: 'apify',
      }
    });
  }
}
return out.length ? out : [{ json: { _empty: true, runId: cfg.runId } }];""",
        },
    })

    # --- 5. Merge Comment Sources ---------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Merge Comments",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [1300, 410],
        "parameters": {"mode": "append"},
    })

    # --- 6. Build Classification Prompt ---------------------------------
    nodes.append({
        "id": uid(),
        "name": "Build Classification Prompt",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1520, 410],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const comments = $input.all()
  .map(i => i.json)
  .filter(c => c && c.text);

const cfg = $('Demo Config').first().json;

const prompt = `You are a sales qualifier for ${cfg.brandInfo}

Score each of these social-media comments on buying intent (0-100).
Category must be one of: pricing | demo-request | objection | endorsement | support | spam | generic.

Scoring guide:
- 0-29   = low intent (fan noise, spam, random)
- 30-69  = medium intent (curious, asking general questions, objections)
- 70-100 = high intent (asking price, wants demo, ready to buy)

For HIGH intent comments, also draft a 1-2 sentence reply that feels human,
addresses their question, and invites them to DM or book a call. No emoji
unless the original comment used one. Never pitch hard — earn the click.

For MEDIUM intent, draft a softer nurture reply (1 sentence).
For LOW, suggestedReply = null.

Return STRICT JSON, no prose:
{
  "results": [
    {
      "commentId":"...",
      "intentScore": 0-100,
      "category":"...",
      "reasoning":"one short sentence",
      "suggestedReply":"..." | null
    }
  ]
}

Comments to score:
${JSON.stringify(comments.map(c => ({commentId: c.commentId, username: c.username, text: c.text})), null, 2)}`;

return [{ json: { prompt, comments } }];""",
        },
    })

    # --- 7. AI Classify Intent ------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "AI Classify Intent",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1740, 410],
        "credentials": {"httpHeaderAuth": CRED_OPENROUTER},
        "parameters": {
            "method": "POST",
            "url": OPENROUTER_URL,
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({ "
                f"model: '{AI_MODEL_CLASSIFY}', "
                "max_tokens: 2500, "
                "temperature: 0.2, "
                "messages: [{role: 'user', content: $json.prompt}] "
                "}) }}"
            ),
            "options": {"timeout": 45000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 8. Merge Classifications & Fan Out -----------------------------
    nodes.append({
        "id": uid(),
        "name": "Merge & Fan Out",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1960, 410],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const promptPayload = $('Build Classification Prompt').first().json;
const comments = promptPayload.comments || [];

const aiResp = $input.first().json || {};
let raw = '';
try {
  raw = aiResp.choices && aiResp.choices[0] && aiResp.choices[0].message
    ? aiResp.choices[0].message.content : '';
} catch (e) { raw = ''; }

let results = [];
try {
  const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
  const parsed = cleaned ? JSON.parse(cleaned) : {};
  results = Array.isArray(parsed.results) ? parsed.results : [];
} catch (e) { results = []; }

// Heuristic fallback — basic keyword intent if AI fails.
function heuristic(text) {
  const t = (text || '').toLowerCase();
  let score = 10, cat = 'generic';
  if (/(how much|price|pricing|cost|rate|quote)/.test(t)) { score = 82; cat = 'pricing'; }
  else if (/(demo|jump on a call|book)/.test(t)) { score = 88; cat = 'demo-request'; }
  else if (/(dm|link|sign up|sign-up|trial)/.test(t)) { score = 74; cat = 'pricing'; }
  else if (/(won't work|terrible|bad experience)/.test(t)) { score = 45; cat = 'objection'; }
  else if (/(🔥|love this|amazing|game-changer|best decision)/.test(t)) { score = 30; cat = 'endorsement'; }
  else if (/(crypto|giveaway|check my profile)/.test(t)) { score = 0; cat = 'spam'; }
  return { score, cat };
}

const byId = new Map(results.map(r => [r.commentId, r]));

return comments.map(c => {
  let r = byId.get(c.commentId);
  if (!r) {
    const h = heuristic(c.text);
    r = {
      commentId: c.commentId,
      intentScore: h.score,
      category: h.cat,
      reasoning: 'heuristic fallback',
      suggestedReply: null,
    };
  }
  return {
    json: {
      ...c,
      intentScore: Number(r.intentScore) || 0,
      category: r.category || 'generic',
      reasoning: r.reasoning || '',
      suggestedReply: r.suggestedReply || null,
      tier: (r.intentScore >= 70) ? 'high' : (r.intentScore >= 30 ? 'medium' : 'low'),
    }
  };
});""",
        },
    })

    # --- 9. Log Lead to Airtable -----------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Log Lead to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2200, 410],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_COMMENT_LEADS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Comment ID": "={{ $json.commentId }}",
                    "Run ID": "={{ $json.runId }}",
                    "Platform": "={{ $json.platform }}",
                    "Post URL": "={{ $json.postUrl }}",
                    "Username": "={{ $json.username }}",
                    "Comment Text": "={{ $json.text }}",
                    "Intent Score": "={{ $json.intentScore }}",
                    "Category": "={{ $json.category }}",
                    "Tier": "={{ $json.tier }}",
                    "Reasoning": "={{ $json.reasoning }}",
                    "Suggested Reply": "={{ $json.suggestedReply || '' }}",
                    "Likes": "={{ $json.likes }}",
                    "Source": "={{ $json.source }}",
                    "Commented At": "={{ $json.timestamp }}",
                    "Created At": "={{ new Date().toISOString() }}",
                },
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 10. Tier Router -------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Tier Router",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [2440, 410],
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.tier }}",
                                    "rightValue": "high",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "high",
                    },
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.tier }}",
                                    "rightValue": "medium",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "medium",
                    },
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.tier }}",
                                    "rightValue": "low",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                        },
                        "outputKey": "low",
                    },
                ]
            },
            "options": {"fallbackOutput": 2},
        },
    })

    # --- 11. Slack Alert (HIGH) -----------------------------------------
    # Uses webhook URL; graceful failure if SLACK_WEBHOOK_URL is missing.
    nodes.append({
        "id": uid(),
        "name": "Slack Alert — High Intent",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2680, 260],
        "parameters": {
            "method": "POST",
            "url": "={{ $env.SLACK_WEBHOOK_URL || 'https://hooks.slack.com/services/DISABLED' }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({ "
                "text: '🔥 HIGH-INTENT LEAD on ' + $json.platform + "
                "'\\nScore: ' + $json.intentScore + ' (' + $json.category + ')' + "
                "'\\nFrom: ' + $json.username + "
                "'\\nComment: \"' + $json.text + '\"' + "
                "'\\nSuggested reply: ' + ($json.suggestedReply || '(draft yourself)') + "
                "'\\nPost: ' + $json.postUrl"
                "}) }}"
            ),
            "options": {"timeout": 10000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 12. Aggregate Summary ------------------------------------------
    # Collects everything that flowed through for the final response.
    nodes.append({
        "id": uid(),
        "name": "Pass-through Medium",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [2680, 410],
        "parameters": {},
    })
    nodes.append({
        "id": uid(),
        "name": "Pass-through Low",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [2680, 560],
        "parameters": {},
    })

    # --- 13. Merge Tiers ------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Merge Tiers",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [2900, 410],
        "parameters": {"mode": "append"},
    })

    # --- 14. Summarise Run ----------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Summarise Run",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3120, 410],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all().map(i => i.json).filter(c => c && c.commentId);
const tiers = { high: 0, medium: 0, low: 0 };
for (const c of items) tiers[c.tier] = (tiers[c.tier] || 0) + 1;

const highs = items.filter(c => c.tier === 'high').map(c => ({
  username: c.username,
  score: c.intentScore,
  text: c.text,
  category: c.category,
  suggestedReply: c.suggestedReply,
}));

const runId = items[0]?.runId || ('CL-' + Date.now());

return [{
  json: {
    runId,
    total: items.length,
    breakdown: tiers,
    highIntentLeads: highs,
    timestamp: new Date().toISOString(),
    status: 'complete',
  }
}];""",
        },
    })

    # --- 15. Respond ----------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Respond",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [3340, 410],
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify($json) }}",
            "options": {},
        },
    })

    return nodes


def build_connections(nodes: list[dict]) -> dict:
    return {
        "Webhook Trigger": {"main": [[{"node": "Demo Config", "type": "main", "index": 0}]]},
        "Every 5 Minutes": {"main": [[{"node": "Demo Config", "type": "main", "index": 0}]]},
        "Demo Config": {"main": [[{"node": "DEMO_MODE Switch", "type": "main", "index": 0}]]},
        "DEMO_MODE Switch": {
            "main": [
                [{"node": "Load Fixture Comments", "type": "main", "index": 0}],
                [{"node": "Apify Comment Scrape", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Comments": {"main": [[{"node": "Merge Comments", "type": "main", "index": 0}]]},
        "Apify Comment Scrape": {"main": [[{"node": "Normalise Apify", "type": "main", "index": 0}]]},
        "Normalise Apify": {"main": [[{"node": "Merge Comments", "type": "main", "index": 1}]]},
        "Merge Comments": {"main": [[{"node": "Build Classification Prompt", "type": "main", "index": 0}]]},
        "Build Classification Prompt": {"main": [[{"node": "AI Classify Intent", "type": "main", "index": 0}]]},
        "AI Classify Intent": {"main": [[{"node": "Merge & Fan Out", "type": "main", "index": 0}]]},
        "Merge & Fan Out": {"main": [[{"node": "Log Lead to Airtable", "type": "main", "index": 0}]]},
        "Log Lead to Airtable": {"main": [[{"node": "Tier Router", "type": "main", "index": 0}]]},
        "Tier Router": {
            "main": [
                [{"node": "Slack Alert — High Intent", "type": "main", "index": 0}],
                [{"node": "Pass-through Medium", "type": "main", "index": 0}],
                [{"node": "Pass-through Low", "type": "main", "index": 0}],
            ]
        },
        "Slack Alert — High Intent": {"main": [[{"node": "Merge Tiers", "type": "main", "index": 0}]]},
        "Pass-through Medium": {"main": [[{"node": "Merge Tiers", "type": "main", "index": 1}]]},
        "Pass-through Low": {"main": [[{"node": "Merge Tiers", "type": "main", "index": 2}]]},
        "Merge Tiers": {"main": [[{"node": "Summarise Run", "type": "main", "index": 0}]]},
        "Summarise Run": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
    }


# ==================================================================
# BUILD / DEPLOY
# ==================================================================


def build_workflow() -> dict:
    nodes = build_nodes()
    connections = build_connections(nodes)
    return {
        "name": WORKFLOW_NAME,
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


def save_workflow(workflow: dict) -> Path:
    output_dir = Path(__file__).parent.parent / "workflows" / "demos"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / WORKFLOW_FILENAME
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    return output_path


def deploy_workflow(workflow: dict, activate: bool = False) -> str:
    from n8n_client import N8nClient

    api_key = os.getenv("N8N_API_KEY")
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    if not api_key:
        raise RuntimeError("N8N_API_KEY not set in .env")

    with N8nClient(base_url, api_key, timeout=30) as client:
        health = client.health_check()
        if not health["connected"]:
            raise RuntimeError(f"Cannot connect to n8n: {health.get('error')}")

        existing = None
        for wf in client.list_workflows():
            if wf["name"] == workflow["name"]:
                existing = wf
                break

        payload = {
            "name": workflow["name"],
            "nodes": workflow["nodes"],
            "connections": workflow["connections"],
            "settings": workflow["settings"],
        }
        if existing:
            result = client.update_workflow(existing["id"], payload)
            wf_id = result.get("id") or existing["id"]
        else:
            result = client.create_workflow(payload)
            wf_id = result.get("id")

        if activate and wf_id:
            client.activate_workflow(wf_id)

        return wf_id or ""


def main() -> None:
    args = sys.argv[1:]
    action = args[0] if args else "build"

    print("=" * 60)
    print(f"{WORKFLOW_NAME}: {action}")
    print("=" * 60)

    if "REPLACE" in TABLE_COMMENT_LEADS:
        print("WARNING: DEMO_TABLE_COMMENT_LEADS not set in .env")
        print("         Airtable log step will fail at runtime.")
        print("         Run: python tools/setup_demo_airtable.py")

    if not SLACK_WEBHOOK_URL:
        print("NOTE: SLACK_WEBHOOK_URL not set — Slack alerts will hit a "
              "disabled URL and silently fail (workflow still completes).")

    workflow = build_workflow()
    output_path = save_workflow(workflow)
    print(f"Built {len(workflow['nodes'])} nodes, {len(workflow['connections'])} connections")
    print(f"Saved: {output_path}")

    if action == "build":
        print("\nBuild complete. Run with 'deploy' or 'activate' to push to n8n.")
        return

    if action in ("deploy", "activate"):
        print("\nDeploying to n8n...")
        wf_id = deploy_workflow(workflow, activate=(action == "activate"))
        print(f"\nWorkflow ID: {wf_id}")


if __name__ == "__main__":
    main()
