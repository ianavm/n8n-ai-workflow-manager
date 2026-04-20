"""
DEMO-02: UGC Ops Autopilot

Ecommerce brand describes a UGC campaign → workflow finds creators,
scores fit, drafts personalised briefs, sends outreach via Gmail, and
tracks everything in Airtable (campaigns + creators + outreach log).

Flow:
    Form Trigger / Webhook (brand, product, budget, quantity, niche)
        → Demo Config (Set: DEMO_MODE, campaign config)
        → Create Campaign Record (Airtable)
        → DEMO_MODE Switch
            → DEMO_MODE=1 : Load Fixture Creators (Set, inline seed of 10)
            → DEMO_MODE=0 : Apify TikTok Hashtag Scraper
        → Merge Creator Sources
        → Fan Out Creators (Code)
        → AI Score + Personalise per creator (OpenRouter → Claude)
        → Filter (fitScore >= 7)
        → Log Creator to Airtable
        → DEMO_MODE Switch #2
            → DEMO_MODE=1 : Simulate Send (Code, mark outreach_sent)
            → DEMO_MODE=0 : Send Gmail outreach
        → Merge
        → Log Outreach
        → Aggregate & Respond

Usage:
    python tools/deploy_demo_ugc_ops.py build
    python tools/deploy_demo_ugc_ops.py deploy
    python tools/deploy_demo_ugc_ops.py activate
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
from credentials import CRED_AIRTABLE, CRED_GMAIL_OAUTH2, CRED_OPENROUTER  # noqa: E402

# ==================================================================
# CONFIG
# ==================================================================

WORKFLOW_NAME = "DEMO-02 UGC Ops Autopilot"
WORKFLOW_FILENAME = "demo02_ugc_ops.json"

AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_CAMPAIGNS = os.getenv(
    "DEMO_TABLE_UGC_CAMPAIGNS", "REPLACE_WITH_TABLE_ID"
)
TABLE_CREATORS = os.getenv(
    "DEMO_TABLE_UGC_CREATORS", "REPLACE_WITH_TABLE_ID"
)
TABLE_OUTREACH = os.getenv(
    "DEMO_TABLE_UGC_OUTREACH", "REPLACE_WITH_TABLE_ID"
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL = "anthropic/claude-sonnet-4-20250514"

FIXTURE_CREATORS = [
    {
        "handle": "@miriam_wellness",
        "platform": "tiktok",
        "followers": 28400,
        "niche": "wellness, supplements, morning routines",
        "avgViews": 18900,
        "engagementRate": 6.8,
        "samplePost": "day 14 of trying every supplement on clean-tok — the only one that actually helped my 3pm crash",
        "email": "miriam@creators.demo",
        "rateCard": 850,
    },
    {
        "handle": "@fitness_nandi",
        "platform": "instagram",
        "followers": 42100,
        "niche": "fitness, SA women in sport, moms-who-lift",
        "avgViews": 31200,
        "engagementRate": 5.1,
        "samplePost": "post-workout recovery stack — this one saved my joints after marathon training",
        "email": "nandi@creators.demo",
        "rateCard": 1400,
    },
    {
        "handle": "@dietitian_jay",
        "platform": "tiktok",
        "followers": 67800,
        "niche": "registered dietitian, debunks supplement hype",
        "avgViews": 52000,
        "engagementRate": 7.9,
        "samplePost": "I reviewed 200 supplements. These 5 are worth your money, the rest are scams.",
        "email": "jay@creators.demo",
        "rateCard": 2200,
    },
    {
        "handle": "@fast_lane_cars",
        "platform": "instagram",
        "followers": 89200,
        "niche": "car enthusiasts, reviews",
        "avgViews": 41000,
        "engagementRate": 3.2,
        "samplePost": "new BMW M4 feature nobody's talking about",
        "email": "cars@creators.demo",
        "rateCard": 1800,
    },
    {
        "handle": "@salon_kholi",
        "platform": "tiktok",
        "followers": 19700,
        "niche": "SA salon owner, beauty entrepreneurs",
        "avgViews": 8200,
        "engagementRate": 9.4,
        "samplePost": "the morning supplement routine that made me stop skipping breakfast as a salon owner",
        "email": "kholi@creators.demo",
        "rateCard": 600,
    },
    {
        "handle": "@run_club_tebogo",
        "platform": "instagram",
        "followers": 15400,
        "niche": "running, endurance, SA run clubs",
        "avgViews": 9800,
        "engagementRate": 6.2,
        "samplePost": "5 things I take pre-run — no, not caffeine pills",
        "email": "tebogo@creators.demo",
        "rateCard": 500,
    },
    {
        "handle": "@busy_mom_van",
        "platform": "tiktok",
        "followers": 34500,
        "niche": "busy moms, wellness hacks, SA mompreneurs",
        "avgViews": 22100,
        "engagementRate": 8.1,
        "samplePost": "the 3-supplement morning stack that stopped me crashing at 2pm",
        "email": "vanessa@creators.demo",
        "rateCard": 1100,
    },
    {
        "handle": "@crypto_randy",
        "platform": "twitter",
        "followers": 52000,
        "niche": "crypto, trading signals",
        "avgViews": 7000,
        "engagementRate": 0.8,
        "samplePost": "BTC to the moon 🚀",
        "email": "randy@creators.demo",
        "rateCard": 900,
    },
    {
        "handle": "@zulu_yogi",
        "platform": "instagram",
        "followers": 24800,
        "niche": "yoga, mindful wellness, mental health SA",
        "avgViews": 14600,
        "engagementRate": 7.3,
        "samplePost": "post-yoga recovery routine — what I put in my body matters as much as the practice",
        "email": "zulu@creators.demo",
        "rateCard": 750,
    },
    {
        "handle": "@food_chef_thabo",
        "platform": "tiktok",
        "followers": 11200,
        "niche": "cooking, nutrition, SA home chefs",
        "avgViews": 4900,
        "engagementRate": 5.8,
        "samplePost": "what I actually feed my kids vs what the ads say you should",
        "email": "thabo@creators.demo",
        "rateCard": 400,
    },
]


def uid() -> str:
    return str(uuid.uuid4())


# ==================================================================
# NODE BUILDERS
# ==================================================================


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    # --- 1a. Form Trigger ------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Form Trigger",
        "type": "n8n-nodes-base.formTrigger",
        "typeVersion": 2.2,
        "position": [200, 260],
        "webhookId": "demo02-ugc-ops-form",
        "parameters": {
            "formTitle": "UGC Campaign Launcher — AnyVision Media",
            "formDescription": (
                "Describe your UGC campaign. We'll find creators, score fit, "
                "draft personalised briefs, and send outreach in under 60 seconds."
            ),
            "formFields": {
                "values": [
                    {"fieldLabel": "Brand", "fieldType": "text", "requiredField": True},
                    {"fieldLabel": "Product Name", "fieldType": "text", "requiredField": True},
                    {"fieldLabel": "Product Brief", "fieldType": "textarea", "requiredField": True},
                    {"fieldLabel": "Niche Keywords", "fieldType": "text", "requiredField": True,
                     "placeholder": "wellness, supplements, SA moms"},
                    {"fieldLabel": "Deliverables", "fieldType": "text", "requiredField": True,
                     "placeholder": "1 × 30s TikTok, 1 × IG reel"},
                    {"fieldLabel": "Budget Per Creator (ZAR)", "fieldType": "number", "requiredField": True},
                    {"fieldLabel": "Quantity", "fieldType": "number", "requiredField": True},
                    {
                        "fieldLabel": "Demo Mode",
                        "fieldType": "dropdown",
                        "fieldOptions": {"values": [{"option": "1"}, {"option": "0"}]},
                        "requiredField": True,
                    },
                ]
            },
            "responseMode": "lastNode",
            "options": {},
        },
    })

    # --- 1b. Webhook Trigger --------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [200, 500],
        "webhookId": "demo02-ugc-ops",
        "parameters": {
            "httpMethod": "POST",
            "path": "demo02-ugc-ops",
            "responseMode": "lastNode",
            "options": {},
        },
    })

    # --- 2. Demo Config -------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Demo Config",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [420, 380],
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "campaignId", "type": "string",
                     "value": "={{ 'UGC-' + $now.toFormat('yyyyLLdd-HHmmss') }}"},
                    {"id": uid(), "name": "brand", "type": "string",
                     "value": "={{ $json['Brand'] || $json.brand || 'VitalityCo' }}"},
                    {"id": uid(), "name": "productName", "type": "string",
                     "value": "={{ $json['Product Name'] || $json.productName || 'Morning Stack Supplement' }}"},
                    {"id": uid(), "name": "productBrief", "type": "string",
                     "value": "={{ $json['Product Brief'] || $json.productBrief || 'Locally-sourced daily stack for busy professionals — no caffeine, no crash.' }}"},
                    {"id": uid(), "name": "niche", "type": "string",
                     "value": "={{ $json['Niche Keywords'] || $json.niche || 'wellness, supplements, SA moms, busy professionals' }}"},
                    {"id": uid(), "name": "deliverables", "type": "string",
                     "value": "={{ $json['Deliverables'] || $json.deliverables || '1 × 30s TikTok + 1 × IG reel' }}"},
                    {"id": uid(), "name": "budgetPerCreator", "type": "number",
                     "value": "={{ Number($json['Budget Per Creator (ZAR)'] ?? $json.budgetPerCreator ?? 1200) }}"},
                    {"id": uid(), "name": "quantity", "type": "number",
                     "value": "={{ Number($json['Quantity'] ?? $json.quantity ?? 5) }}"},
                    {"id": uid(), "name": "demoMode", "type": "string",
                     "value": "={{ String($json['Demo Mode'] ?? $json.demoMode ?? '1') }}"},
                    {"id": uid(), "name": "fixtureCreators", "type": "string",
                     "value": json.dumps(FIXTURE_CREATORS)},
                ]
            },
            "options": {},
        },
    })

    # --- 3. Create Campaign Record --------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Create Campaign Record",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [640, 380],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_CAMPAIGNS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Campaign ID": "={{ $json.campaignId }}",
                    "Brand": "={{ $json.brand }}",
                    "Product Name": "={{ $json.productName }}",
                    "Product Brief": "={{ $json.productBrief }}",
                    "Niche": "={{ $json.niche }}",
                    "Deliverables": "={{ $json.deliverables }}",
                    "Budget Per Creator": "={{ $json.budgetPerCreator }}",
                    "Quantity": "={{ $json.quantity }}",
                    "Status": "Sourcing",
                    "Created At": "={{ new Date().toISOString() }}",
                },
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 4. DEMO_MODE Switch --------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "DEMO_MODE Switch",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [860, 380],
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $('Demo Config').first().json.demoMode }}",
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
                                    "leftValue": "={{ $('Demo Config').first().json.demoMode }}",
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

    # --- 5a. Load Fixture Creators --------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Load Fixture Creators",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1080, 260],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const cfg = $('Demo Config').first().json;
const fx = JSON.parse(cfg.fixtureCreators || '[]');
return fx.map(c => ({ json: { ...c, campaignId: cfg.campaignId, source: 'fixture' } }));""",
        },
    })

    # --- 5b. Apify TikTok Hashtag Scraper (live path) -------------------
    nodes.append({
        "id": uid(),
        "name": "Apify TikTok Scrape",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1080, 500],
        "parameters": {
            "method": "POST",
            "url": "https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "token", "value": "={{ $env.APIFY_API_TOKEN || 'MISSING' }}"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ hashtags: ($('Demo Config').first().json.niche || '').split(',').map(s => s.trim()).filter(Boolean), resultsPerPage: 20 }) }}",
            "options": {"timeout": 120000},
        },
        "onError": "continueRegularOutput",
    })

    nodes.append({
        "id": uid(),
        "name": "Normalise Apify Creators",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1300, 500],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const cfg = $('Demo Config').first().json;
const items = $input.all();
const out = [];
const seen = new Set();
for (const item of items) {
  const rows = Array.isArray(item.json) ? item.json : [item.json];
  for (const r of rows) {
    const author = r.authorMeta || r.author || {};
    const handle = author.name ? '@' + author.name : null;
    if (!handle || seen.has(handle)) continue;
    seen.add(handle);
    out.push({
      json: {
        handle,
        platform: 'tiktok',
        followers: author.fans || 0,
        niche: cfg.niche,
        avgViews: r.playCount || 0,
        engagementRate: r.playCount ? ((r.diggCount || 0) + (r.commentCount || 0)) / r.playCount * 100 : 0,
        samplePost: r.text || '',
        email: author.email || '',
        rateCard: 0,
        campaignId: cfg.campaignId,
        source: 'apify',
      }
    });
  }
}
return out.length ? out : [{ json: { _empty: true, campaignId: cfg.campaignId } }];""",
        },
    })

    # --- 6. Merge Creator Sources ---------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Merge Creators",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [1520, 380],
        "parameters": {"mode": "append"},
    })

    # --- 7. Build Scoring Prompt (per creator) --------------------------
    nodes.append({
        "id": uid(),
        "name": "Build Scoring Prompt",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1740, 380],
        "parameters": {
            "mode": "runOnceForEachItem",
            "jsCode": """const c = $json;
if (c._empty) return { json: c };
const cfg = $('Demo Config').first().json;

const prompt = `You are a UGC casting director for ${cfg.brand}.

Campaign:
- Product: ${cfg.productName}
- Brief: ${cfg.productBrief}
- Niche keywords: ${cfg.niche}
- Deliverables: ${cfg.deliverables}
- Budget per creator: R${cfg.budgetPerCreator}

Creator:
- Handle: ${c.handle} (${c.platform})
- Followers: ${c.followers} | Avg views: ${c.avgViews} | ER: ${c.engagementRate}%
- Niche: ${c.niche}
- Sample post: "${c.samplePost}"
- Rate card: R${c.rateCard}

Task: score fit 1-10 and draft a personalised outreach DM + subject line.

Scoring rubric:
- 9-10 = niche alignment perfect, audience match, within budget, high engagement
- 7-8  = strong match, minor gap (rate slightly high, niche adjacent)
- 4-6  = weak match
- 1-3  = wrong niche / audience / quality

Return STRICT JSON:
{
  "fitScore": n,
  "fitReasoning": "one sentence",
  "outreachSubject": "short, <= 60 chars, no clickbait",
  "outreachBody": "2-3 short paragraphs referencing their sample post specifically, proposing the collab, mentioning budget, easy reply CTA"
}`;
return { json: { ...c, scoringPrompt: prompt } };""",
        },
    })

    # --- 8. AI Score + Brief -------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "AI Score + Brief",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1960, 380],
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
                f"model: '{AI_MODEL}', "
                "max_tokens: 900, "
                "temperature: 0.7, "
                "messages: [{role:'user', content: $json.scoringPrompt || ''}] "
                "}) }}"
            ),
            "options": {"timeout": 45000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 9. Parse Score + Filter ---------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Parse Score",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2180, 380],
        "parameters": {
            "mode": "runOnceForEachItem",
            "jsCode": """const c = $('Build Scoring Prompt').item.json;
if (c._empty) return { json: c };

const aiResp = $json || {};
let raw = '';
try {
  raw = aiResp.choices && aiResp.choices[0] && aiResp.choices[0].message
    ? aiResp.choices[0].message.content : '';
} catch (e) { raw = ''; }

let parsed = null;
try {
  const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
  parsed = cleaned ? JSON.parse(cleaned) : null;
} catch (e) { parsed = null; }

if (!parsed) {
  // Heuristic fallback: niche keyword overlap
  const nicheTokens = (c.niche || '').toLowerCase().split(/[,\\s]+/).filter(Boolean);
  const campaignTokens = ($('Demo Config').first().json.niche || '').toLowerCase().split(/[,\\s]+/).filter(Boolean);
  const overlap = nicheTokens.filter(t => campaignTokens.some(ct => ct.includes(t) || t.includes(ct))).length;
  parsed = {
    fitScore: Math.min(10, Math.max(1, 3 + overlap)),
    fitReasoning: 'Heuristic niche overlap fallback (' + overlap + ' tokens).',
    outreachSubject: 'Quick collab idea — ' + c.handle,
    outreachBody: 'Hey, loved your recent post. We run ' + ($('Demo Config').first().json.brand) + ' and think it fits your audience. Budget R' + ($('Demo Config').first().json.budgetPerCreator) + ' for ' + ($('Demo Config').first().json.deliverables) + '. Interested?',
  };
}

return {
  json: {
    ...c,
    fitScore: Number(parsed.fitScore) || 0,
    fitReasoning: parsed.fitReasoning || '',
    outreachSubject: parsed.outreachSubject || '',
    outreachBody: parsed.outreachBody || '',
  }
};""",
        },
    })

    # --- 10. Filter Qualified (fitScore >= 7) --------------------------
    nodes.append({
        "id": uid(),
        "name": "Filter Qualified",
        "type": "n8n-nodes-base.filter",
        "typeVersion": 2.2,
        "position": [2400, 380],
        "parameters": {
            "conditions": {
                "combinator": "and",
                "conditions": [
                    {
                        "leftValue": "={{ $json.fitScore }}",
                        "rightValue": 7,
                        "operator": {"type": "number", "operation": "gte"},
                    },
                    {
                        "leftValue": "={{ $json._empty }}",
                        "rightValue": "={{ true }}",
                        "operator": {"type": "boolean", "operation": "notEqual"},
                    },
                ],
            },
            "options": {},
        },
    })

    # --- 11. Log Creator to Airtable ----------------------------------
    nodes.append({
        "id": uid(),
        "name": "Log Creator",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2620, 380],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_CREATORS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Campaign ID": "={{ $json.campaignId }}",
                    "Handle": "={{ $json.handle }}",
                    "Platform": "={{ $json.platform }}",
                    "Followers": "={{ $json.followers }}",
                    "Avg Views": "={{ $json.avgViews }}",
                    "Engagement Rate": "={{ $json.engagementRate }}",
                    "Niche": "={{ $json.niche }}",
                    "Sample Post": "={{ $json.samplePost }}",
                    "Email": "={{ $json.email }}",
                    "Rate Card": "={{ $json.rateCard }}",
                    "Fit Score": "={{ $json.fitScore }}",
                    "Fit Reasoning": "={{ $json.fitReasoning }}",
                    "Outreach Subject": "={{ $json.outreachSubject }}",
                    "Outreach Body": "={{ $json.outreachBody }}",
                    "Status": "Qualified",
                    "Source": "={{ $json.source }}",
                    "Created At": "={{ new Date().toISOString() }}",
                },
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 12. DEMO_MODE Switch #2 (send vs simulate) ----------------------
    nodes.append({
        "id": uid(),
        "name": "Send Mode Switch",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [2840, 380],
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "combinator": "and",
                            "conditions": [
                                {
                                    "leftValue": "={{ $('Demo Config').first().json.demoMode }}",
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
                                    "leftValue": "={{ $('Demo Config').first().json.demoMode }}",
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

    # --- 13a. Simulate Send ---------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Simulate Send",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [3060, 260],
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "outreachStatus", "type": "string", "value": "simulated_sent"},
                    {"id": uid(), "name": "messageId", "type": "string",
                     "value": "={{ 'SIM-' + $json.handle + '-' + Date.now() }}"},
                    {"id": uid(), "name": "sentAt", "type": "string", "value": "={{ new Date().toISOString() }}"},
                ]
            },
            "include": "all",
            "options": {},
        },
    })

    # --- 13b. Send Gmail ------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Send Gmail Outreach",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [3060, 500],
        "credentials": {"gmailOAuth2": CRED_GMAIL_OAUTH2},
        "parameters": {
            "sendTo": "={{ $json.email }}",
            "subject": "={{ $json.outreachSubject }}",
            "message": "={{ $json.outreachBody }}",
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 14. Merge Send Paths -------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Merge Send Paths",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [3300, 380],
        "parameters": {"mode": "append"},
    })

    # --- 15. Log Outreach -----------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Log Outreach",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [3520, 380],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_OUTREACH},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Campaign ID": "={{ $json.campaignId }}",
                    "Handle": "={{ $json.handle }}",
                    "Email": "={{ $json.email }}",
                    "Subject": "={{ $json.outreachSubject }}",
                    "Body": "={{ $json.outreachBody }}",
                    "Status": "={{ $json.outreachStatus || 'sent' }}",
                    "Message ID": "={{ $json.messageId || ($json.id || '') }}",
                    "Sent At": "={{ $json.sentAt || new Date().toISOString() }}",
                },
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 16. Aggregate Campaign -----------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Aggregate Campaign",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3740, 380],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all().map(i => i.json);
const cfg = $('Demo Config').first().json;
return [{
  json: {
    campaignId: cfg.campaignId,
    brand: cfg.brand,
    productName: cfg.productName,
    quantityRequested: cfg.quantity,
    creatorsReached: items.length,
    creators: items.map(c => ({
      handle: c.handle,
      platform: c.platform,
      fitScore: c.fitScore,
      outreachStatus: c.outreachStatus,
      subject: c.outreachSubject,
    })),
    timestamp: new Date().toISOString(),
    status: 'outreach_complete',
  }
}];""",
        },
    })

    # --- 17. Respond ----------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Respond",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [3960, 380],
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify($json) }}",
            "options": {},
        },
    })

    return nodes


def build_connections(nodes: list[dict]) -> dict:
    return {
        "Form Trigger": {"main": [[{"node": "Demo Config", "type": "main", "index": 0}]]},
        "Webhook Trigger": {"main": [[{"node": "Demo Config", "type": "main", "index": 0}]]},
        "Demo Config": {"main": [[{"node": "Create Campaign Record", "type": "main", "index": 0}]]},
        "Create Campaign Record": {"main": [[{"node": "DEMO_MODE Switch", "type": "main", "index": 0}]]},
        "DEMO_MODE Switch": {
            "main": [
                [{"node": "Load Fixture Creators", "type": "main", "index": 0}],
                [{"node": "Apify TikTok Scrape", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Creators": {"main": [[{"node": "Merge Creators", "type": "main", "index": 0}]]},
        "Apify TikTok Scrape": {"main": [[{"node": "Normalise Apify Creators", "type": "main", "index": 0}]]},
        "Normalise Apify Creators": {"main": [[{"node": "Merge Creators", "type": "main", "index": 1}]]},
        "Merge Creators": {"main": [[{"node": "Build Scoring Prompt", "type": "main", "index": 0}]]},
        "Build Scoring Prompt": {"main": [[{"node": "AI Score + Brief", "type": "main", "index": 0}]]},
        "AI Score + Brief": {"main": [[{"node": "Parse Score", "type": "main", "index": 0}]]},
        "Parse Score": {"main": [[{"node": "Filter Qualified", "type": "main", "index": 0}]]},
        "Filter Qualified": {"main": [[{"node": "Log Creator", "type": "main", "index": 0}]]},
        "Log Creator": {"main": [[{"node": "Send Mode Switch", "type": "main", "index": 0}]]},
        "Send Mode Switch": {
            "main": [
                [{"node": "Simulate Send", "type": "main", "index": 0}],
                [{"node": "Send Gmail Outreach", "type": "main", "index": 0}],
            ]
        },
        "Simulate Send": {"main": [[{"node": "Merge Send Paths", "type": "main", "index": 0}]]},
        "Send Gmail Outreach": {"main": [[{"node": "Merge Send Paths", "type": "main", "index": 1}]]},
        "Merge Send Paths": {"main": [[{"node": "Log Outreach", "type": "main", "index": 0}]]},
        "Log Outreach": {"main": [[{"node": "Aggregate Campaign", "type": "main", "index": 0}]]},
        "Aggregate Campaign": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
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

    for label, val in [
        ("DEMO_TABLE_UGC_CAMPAIGNS", TABLE_CAMPAIGNS),
        ("DEMO_TABLE_UGC_CREATORS", TABLE_CREATORS),
        ("DEMO_TABLE_UGC_OUTREACH", TABLE_OUTREACH),
    ]:
        if "REPLACE" in val:
            print(f"WARNING: {label} not set in .env")

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
