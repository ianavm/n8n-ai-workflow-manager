"""
DEMO-04: Hook Lab

One content idea in → 5 platform-optimized hook variations out → AI picks
the winner after (simulated or real) engagement. Built as a sales-demo
workflow: runs end-to-end in DEMO_MODE without any external publishing
credentials so it can be shown cold on a prospect call.

Flow:
    Form Trigger / Webhook
        → Demo Config (Set: brand voice, DEMO_MODE flag)
        → Build Variation Prompt (Code)
        → AI Generate Variations (OpenRouter → Claude)
        → Parse & Fan Out (Code, one item per variation)
        → Log Variation to Airtable (DEMO_Hook_Experiments)
        → DEMO_MODE Switch
            → DEMO_MODE=1 : Simulate Engagement (Code)
            → DEMO_MODE=0 : Schedule via Blotato → Wait +24h → Fetch metrics
        → Aggregate (Code, fan-in)
        → AI Pick Winner (OpenRouter)
        → Update Winner in Airtable
        → Respond to Webhook + Slack summary

Usage:
    python tools/deploy_demo_hook_lab.py build        # Build JSON only
    python tools/deploy_demo_hook_lab.py deploy       # Build + push to n8n
    python tools/deploy_demo_hook_lab.py activate     # Build + deploy + activate
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

WORKFLOW_NAME = "DEMO-04 Hook Lab"
WORKFLOW_FILENAME = "demo04_hook_lab.json"

AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_HOOK_EXPERIMENTS = os.getenv(
    "DEMO_TABLE_HOOK_EXPERIMENTS", "REPLACE_WITH_TABLE_ID"
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL_FAST = "anthropic/claude-haiku-4-5"
AI_MODEL_QUALITY = "anthropic/claude-sonnet-4-20250514"

BRAND_VOICE = (
    "AnyVision Media — punchy, direct, SA-SME-focused. Talks like a founder, "
    "not a marketer. Short lines, no fluff, 1-2 emojis max, CTA always earns "
    "the click."
)


def uid() -> str:
    return str(uuid.uuid4())


# ==================================================================
# NODE BUILDERS
# ==================================================================


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    # --- 1a. Form Trigger -------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Form Trigger",
        "type": "n8n-nodes-base.formTrigger",
        "typeVersion": 2.2,
        "position": [200, 260],
        "webhookId": "demo04-hook-lab-form",
        "parameters": {
            "formTitle": "Hook Lab — AnyVision Media",
            "formDescription": (
                "Give us one content idea. We'll generate 5 winning hooks per "
                "platform, score them, and tell you which one to post."
            ),
            "formFields": {
                "values": [
                    {"fieldLabel": "Core Idea", "fieldType": "textarea", "requiredField": True},
                    {
                        "fieldLabel": "Platforms",
                        "fieldType": "dropdown",
                        "fieldOptions": {
                            "values": [
                                {"option": "instagram,linkedin,tiktok,twitter"},
                                {"option": "instagram,linkedin"},
                                {"option": "tiktok,twitter"},
                                {"option": "linkedin"},
                            ]
                        },
                        "requiredField": True,
                    },
                    {"fieldLabel": "Target Audience", "fieldType": "text", "requiredField": False},
                    {
                        "fieldLabel": "Demo Mode",
                        "fieldType": "dropdown",
                        "fieldOptions": {
                            "values": [
                                {"option": "1"},
                                {"option": "0"},
                            ]
                        },
                        "requiredField": True,
                    },
                ]
            },
            "responseMode": "lastNode",
            "options": {},
        },
    })

    # --- 1b. Webhook Trigger (for programmatic demo) ---------------------
    nodes.append({
        "id": uid(),
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [200, 480],
        "webhookId": "demo04-hook-lab",
        "parameters": {
            "httpMethod": "POST",
            "path": "demo04-hook-lab",
            "responseMode": "lastNode",
            "options": {},
        },
    })

    # --- 2. Demo Config ---------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Demo Config",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [420, 370],
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {
                        "id": uid(),
                        "name": "idea",
                        "type": "string",
                        "value": "={{ $json['Core Idea'] || $json.idea || 'We just launched a 5-tool AI stack for SA SMEs under R2k/mo' }}",
                    },
                    {
                        "id": uid(),
                        "name": "platforms",
                        "type": "string",
                        "value": "={{ $json['Platforms'] || $json.platforms || 'instagram,linkedin,tiktok,twitter' }}",
                    },
                    {
                        "id": uid(),
                        "name": "audience",
                        "type": "string",
                        "value": "={{ $json['Target Audience'] || $json.audience || 'SA SME owners, 30-55, hands-on' }}",
                    },
                    {
                        "id": uid(),
                        "name": "demoMode",
                        "type": "string",
                        "value": "={{ String($json['Demo Mode'] ?? $json.demoMode ?? '1') }}",
                    },
                    {"id": uid(), "name": "experimentId", "type": "string", "value": "={{ 'HL-' + $now.toFormat('yyyyLLdd-HHmmss') }}"},
                    {"id": uid(), "name": "brandVoice", "type": "string", "value": BRAND_VOICE},
                ]
            },
            "options": {},
        },
    })

    # --- 3. Build Variation Prompt ---------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Build Variation Prompt",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [640, 370],
        "parameters": {
            "mode": "runOnceForEachItem",
            "jsCode": """const cfg = $json;
const platforms = String(cfg.platforms || '').split(',').map(s => s.trim()).filter(Boolean);

const prompt = `You are a direct-response copywriter writing for ${cfg.brandVoice}.
Target audience: ${cfg.audience}.

Core idea: ${cfg.idea}

Produce 5 hook variations for EACH of these platforms: ${platforms.join(', ')}.

Each variation must use a DIFFERENT emotional angle from this list:
curiosity | contrarian | fear-of-missing-out | social-proof | transformation

Respect platform norms:
- instagram: 1-2 lines, 1 emoji OK, strong first 6 words
- linkedin: 2-3 lines, no emoji, no hashtags in hook, professional tone
- tiktok: 1 line, punchy, can be playful, on-beat with gen-z speak if audience allows
- twitter: <= 240 chars, provocative, 1 emoji max
- facebook: conversational, question or story opener
- youtube: title-style, curiosity-driven, all caps forbidden

Return STRICT JSON, no prose, no code fences:
{
  "variations": [
    {"platform":"instagram","angle":"curiosity","hook":"...","cta":"..."},
    ...
  ]
}`;

return { json: { ...cfg, prompt, platformsArray: platforms } };""",
        },
    })

    # --- 4. AI Generate Variations ---------------------------------------
    nodes.append({
        "id": uid(),
        "name": "AI Generate Variations",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [860, 370],
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
                f"model: '{AI_MODEL_QUALITY}', "
                "max_tokens: 2200, "
                "temperature: 0.85, "
                "messages: [{role: 'user', content: $json.prompt}] "
                "}) }}"
            ),
            "options": {"timeout": 45000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 5. Parse & Fan Out ----------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Parse & Fan Out",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1080, 370],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const cfg = $('Demo Config').first().json;
const aiResp = $input.first().json || {};

// Pull raw content string from OpenRouter response.
let raw = '';
try {
  raw = aiResp.choices && aiResp.choices[0] && aiResp.choices[0].message
    ? aiResp.choices[0].message.content
    : '';
} catch (e) { raw = ''; }

function fallbackVariations(idea, platforms) {
  const angles = ['curiosity','contrarian','fomo','social-proof','transformation'];
  const out = [];
  for (const p of platforms) {
    for (let i = 0; i < 5; i++) {
      out.push({
        platform: p,
        angle: angles[i],
        hook: `[fallback] ${angles[i]} hook for ${p}: ${idea.slice(0, 80)}`,
        cta: 'DM us "GO"'
      });
    }
  }
  return out;
}

let variations = [];
try {
  const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
  const parsed = cleaned ? JSON.parse(cleaned) : {};
  variations = Array.isArray(parsed.variations) ? parsed.variations : [];
} catch (e) {
  variations = [];
}

if (!variations.length) {
  variations = fallbackVariations(cfg.idea, cfg.platformsArray || []);
}

return variations.map((v, i) => ({
  json: {
    experimentId: cfg.experimentId,
    idea: cfg.idea,
    variationIdx: i + 1,
    platform: v.platform,
    angle: v.angle,
    hook: v.hook,
    cta: v.cta,
    demoMode: cfg.demoMode,
    createdAt: new Date().toISOString(),
  }
}));""",
        },
    })

    # --- 6. Log Variation to Airtable ------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Log Variation to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [1300, 370],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_HOOK_EXPERIMENTS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Experiment ID": "={{ $json.experimentId }}",
                    "Variation Idx": "={{ $json.variationIdx }}",
                    "Platform": "={{ $json.platform }}",
                    "Angle": "={{ $json.angle }}",
                    "Hook": "={{ $json.hook }}",
                    "CTA": "={{ $json.cta }}",
                    "Idea": "={{ $json.idea }}",
                    "Created At": "={{ $json.createdAt }}",
                },
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 7. DEMO_MODE Switch ---------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "DEMO_MODE Switch",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [1540, 370],
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

    # --- 8a. Simulate Engagement (DEMO path) -----------------------------
    nodes.append({
        "id": uid(),
        "name": "Simulate Engagement",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1780, 260],
        "parameters": {
            "mode": "runOnceForEachItem",
            "jsCode": """// Deterministic synthetic engagement so demos are repeatable.
// Contrarian + curiosity hooks tend to win; social-proof on LinkedIn.
const v = $json;

function seeded(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h % 10000) / 10000;
}

const base = seeded(v.hook + v.platform + v.angle);
let score = 0.35 + base * 0.5;

if (v.angle === 'contrarian') score += 0.08;
if (v.angle === 'curiosity') score += 0.05;
if (v.platform === 'linkedin' && v.angle === 'social-proof') score += 0.1;
if (v.platform === 'tiktok' && v.angle === 'fomo') score += 0.07;

score = Math.max(0, Math.min(1, score));

const impressions = Math.floor(2000 + base * 8000);
const engagementRate = Number((score * 12).toFixed(2));

return {
  json: {
    ...v,
    simulated: true,
    impressions,
    engagementRate,
    score24h: Number(score.toFixed(3)),
  }
};""",
        },
    })

    # --- 8b. Live Path Placeholder ---------------------------------------
    # In production you'd schedule via Blotato + wait 24h + fetch metrics.
    # For the demo we just stamp a flag and pass through so the flow still
    # completes even if someone picks demoMode=0 without credentials.
    nodes.append({
        "id": uid(),
        "name": "Live Path Placeholder",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [1780, 480],
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "simulated", "type": "boolean", "value": False},
                    {"id": uid(), "name": "impressions", "type": "number", "value": 0},
                    {"id": uid(), "name": "engagementRate", "type": "number", "value": 0},
                    {"id": uid(), "name": "score24h", "type": "number", "value": 0},
                    {
                        "id": uid(),
                        "name": "livePathNote",
                        "type": "string",
                        "value": "Live mode: wire Blotato schedule + 24h wait + metrics fetch here.",
                    },
                ]
            },
            "include": "all",
            "options": {},
        },
    })

    # --- 9. Merge Paths --------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Merge Paths",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [2020, 370],
        "parameters": {"mode": "append"},
    })

    # --- 10. Aggregate Results -------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Aggregate Results",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2240, 370],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all().map(i => i.json);

// Winner = highest score24h, tiebreak on engagementRate.
const sorted = [...items].sort((a, b) => {
  const s = (b.score24h || 0) - (a.score24h || 0);
  return s !== 0 ? s : (b.engagementRate || 0) - (a.engagementRate || 0);
});

const winner = sorted[0] || null;
return [{
  json: {
    experimentId: items[0]?.experimentId,
    idea: items[0]?.idea,
    totalVariations: items.length,
    winner,
    allVariations: sorted,
    timestamp: new Date().toISOString(),
  }
}];""",
        },
    })

    # --- 11. AI Pick Winner ----------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "AI Explain Winner",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2460, 370],
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
                f"model: '{AI_MODEL_FAST}', "
                "max_tokens: 400, "
                "temperature: 0.4, "
                "messages: [{role: 'user', content: "
                "'Given this winning hook variation, write a 2-sentence rationale explaining WHY it is likely to outperform the alternatives. Be concrete about the psychology. Output plain text, no markdown.\\n\\nWinner: ' "
                "+ JSON.stringify($json.winner) + '\\n\\nAll variations (for context): ' "
                "+ JSON.stringify($json.allVariations.slice(0,10))"
                "}] "
                "}) }}"
            ),
            "options": {"timeout": 30000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 12. Finalize Payload --------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Finalize Payload",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2680, 370],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const agg = $('Aggregate Results').first().json;
const aiResp = $input.first().json || {};

let rationale = '';
try {
  rationale = aiResp.choices && aiResp.choices[0] && aiResp.choices[0].message
    ? aiResp.choices[0].message.content.trim()
    : '';
} catch (e) { rationale = ''; }
if (!rationale) rationale = 'Winner selected by highest synthetic engagement score.';

return [{
  json: {
    experimentId: agg.experimentId,
    idea: agg.idea,
    winner: agg.winner,
    winnerRationale: rationale,
    topThree: (agg.allVariations || []).slice(0, 3),
    totalVariations: agg.totalVariations,
    timestamp: agg.timestamp,
    status: 'complete',
  }
}];""",
        },
    })

    # --- 13. Log Winner to Airtable --------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Log Winner to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2900, 370],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_HOOK_EXPERIMENTS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Experiment ID": "={{ $json.experimentId + '-WINNER' }}",
                    "Variation Idx": "=0",
                    "Platform": "={{ $json.winner && $json.winner.platform ? $json.winner.platform : 'n/a' }}",
                    "Angle": "={{ $json.winner && $json.winner.angle ? $json.winner.angle : 'n/a' }}",
                    "Hook": "={{ $json.winner && $json.winner.hook ? $json.winner.hook : 'no winner' }}",
                    "CTA": "={{ $json.winner && $json.winner.cta ? $json.winner.cta : '' }}",
                    "Idea": "={{ $json.idea }}",
                    "Is Winner": "=true",
                    "Winner Rationale": "={{ $json.winnerRationale }}",
                    "Created At": "={{ $json.timestamp }}",
                },
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 14. Respond to Webhook ------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Respond",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [3120, 370],
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify($json) }}",
            "options": {},
        },
    })

    return nodes


def build_connections(nodes: list[dict]) -> dict:
    """Dual triggers → linear until DEMO_MODE Switch → rejoin via Merge."""
    connections: dict = {
        "Form Trigger": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Webhook Trigger": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Demo Config": {
            "main": [[{"node": "Build Variation Prompt", "type": "main", "index": 0}]]
        },
        "Build Variation Prompt": {
            "main": [[{"node": "AI Generate Variations", "type": "main", "index": 0}]]
        },
        "AI Generate Variations": {
            "main": [[{"node": "Parse & Fan Out", "type": "main", "index": 0}]]
        },
        "Parse & Fan Out": {
            "main": [[{"node": "Log Variation to Airtable", "type": "main", "index": 0}]]
        },
        "Log Variation to Airtable": {
            "main": [[{"node": "DEMO_MODE Switch", "type": "main", "index": 0}]]
        },
        "DEMO_MODE Switch": {
            "main": [
                [{"node": "Simulate Engagement", "type": "main", "index": 0}],
                [{"node": "Live Path Placeholder", "type": "main", "index": 0}],
            ]
        },
        "Simulate Engagement": {
            "main": [[{"node": "Merge Paths", "type": "main", "index": 0}]]
        },
        "Live Path Placeholder": {
            "main": [[{"node": "Merge Paths", "type": "main", "index": 1}]]
        },
        "Merge Paths": {
            "main": [[{"node": "Aggregate Results", "type": "main", "index": 0}]]
        },
        "Aggregate Results": {
            "main": [[{"node": "AI Explain Winner", "type": "main", "index": 0}]]
        },
        "AI Explain Winner": {
            "main": [[{"node": "Finalize Payload", "type": "main", "index": 0}]]
        },
        "Finalize Payload": {
            "main": [[{"node": "Log Winner to Airtable", "type": "main", "index": 0}]]
        },
        "Log Winner to Airtable": {
            "main": [[{"node": "Respond", "type": "main", "index": 0}]]
        },
    }
    return connections


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

    if "REPLACE" in TABLE_HOOK_EXPERIMENTS:
        print("WARNING: DEMO_TABLE_HOOK_EXPERIMENTS not set in .env")
        print("         Airtable log steps will fail at runtime.")
        print("         Run: python tools/setup_demo_airtable.py")

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
