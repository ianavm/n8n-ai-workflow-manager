"""
DEMO-01: Video Clip Factory

Long-form video in → 5 short-form clips with burned captions + platform-
specific hooks + captions ready to publish on TikTok, Instagram Reels,
YouTube Shorts, and LinkedIn.

Flow:
    Form Trigger / Webhook
        → Demo Config (Set: DEMO_MODE, source URL, title)
        → DEMO_MODE Switch
            → DEMO_MODE=1 : Load Fixture (transcript + 5 pre-picked segments
                            + 5 pre-rendered clip URLs)
            → DEMO_MODE=0 : Transcribe (AssemblyAI or Whisper) → AI Segment
                            Selection → Remotion Render per segment
        → Merge Paths
        → Fan Out Clips (Code)
        → AI Platform Copy (OpenRouter → Claude)
            → returns per-platform hook + caption + hashtags
        → Log Clip to Airtable
        → Optional Blotato schedule (disabled in demo)
        → Aggregate & Respond

Usage:
    python tools/deploy_demo_video_clips.py build
    python tools/deploy_demo_video_clips.py deploy
    python tools/deploy_demo_video_clips.py activate
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

WORKFLOW_NAME = "DEMO-01 Video Clip Factory"
WORKFLOW_FILENAME = "demo01_video_clips.json"

AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_VIDEO_CLIPS = os.getenv(
    "DEMO_TABLE_VIDEO_CLIPS", "REPLACE_WITH_TABLE_ID"
)

REMOTION_RENDER_URL = os.getenv(
    "REMOTION_RENDER_URL", "https://social-render.up.railway.app"
)
ASSEMBLYAI_API_URL = "https://api.assemblyai.com/v2"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

AI_MODEL_SEGMENTS = "anthropic/claude-sonnet-4-20250514"
AI_MODEL_COPY = "anthropic/claude-haiku-4-5"

BRAND_VOICE = (
    "AnyVision Media — punchy, direct, SA-SME-focused. Founder voice, "
    "not corporate. First 6 words earn the scroll. No fluff."
)

# Fixture — a 45-minute podcast about AI for SME owners (synthetic content).
FIXTURE_VIDEO = {
    "sourceUrl": "https://example.com/demos/avm-podcast-ep12.mp4",
    "title": "AI for SMEs — 5 Tools That Run Our Agency (Ep. 12)",
    "durationSec": 2710,
}

FIXTURE_TRANSCRIPT_SEGMENTS = [
    {
        "startSec": 312,
        "endSec": 348,
        "hook": "Most SMEs think AI costs R50k a month. Ours runs on R2k.",
        "summary": "Ian breaks down the actual monthly AI stack cost for a 12-person agency — sub-R2k total.",
        "retentionScore": 94,
        "clipUrl": "https://social-render.up.railway.app/demo-clips/avm-ep12-clip1.mp4",
    },
    {
        "startSec": 612,
        "endSec": 648,
        "hook": "The tool we fired last month saved us R18k in 30 days.",
        "summary": "Story of replacing a R5k/mo SaaS with a 15-line n8n workflow that runs for free.",
        "retentionScore": 91,
        "clipUrl": "https://social-render.up.railway.app/demo-clips/avm-ep12-clip2.mp4",
    },
    {
        "startSec": 1104,
        "endSec": 1138,
        "hook": "Stop hiring VAs. Do this instead.",
        "summary": "Why a well-designed automation outperforms a junior VA for 80% of repeatable admin work.",
        "retentionScore": 89,
        "clipUrl": "https://social-render.up.railway.app/demo-clips/avm-ep12-clip3.mp4",
    },
    {
        "startSec": 1632,
        "endSec": 1668,
        "hook": "The 3 AI mistakes that will burn your SA SME in 2026.",
        "summary": "Three pitfalls: chasing hype, over-engineering, and skipping the human-in-the-loop. Fix each in one line.",
        "retentionScore": 87,
        "clipUrl": "https://social-render.up.railway.app/demo-clips/avm-ep12-clip4.mp4",
    },
    {
        "startSec": 2205,
        "endSec": 2240,
        "hook": "One client 10x'd bookings. Here's the exact workflow.",
        "summary": "The one-hour-per-week customer-reactivation flow that drove a R420k uplift for a Fourways gym.",
        "retentionScore": 93,
        "clipUrl": "https://social-render.up.railway.app/demo-clips/avm-ep12-clip5.mp4",
    },
]


def uid() -> str:
    return str(uuid.uuid4())


# ==================================================================
# NODE BUILDERS
# ==================================================================


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    # --- 1a. Form Trigger -----------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Form Trigger",
        "type": "n8n-nodes-base.formTrigger",
        "typeVersion": 2.2,
        "position": [200, 260],
        "webhookId": "demo01-video-clips-form",
        "parameters": {
            "formTitle": "Video Clip Factory — AnyVision Media",
            "formDescription": (
                "Drop your YouTube / Drive / direct mp4 link. We'll pick the "
                "5 best moments and generate platform-optimised captions + "
                "hooks for TikTok, Reels, Shorts, LinkedIn."
            ),
            "formFields": {
                "values": [
                    {"fieldLabel": "Video URL", "fieldType": "url", "requiredField": True},
                    {"fieldLabel": "Title", "fieldType": "text", "requiredField": True},
                    {
                        "fieldLabel": "Demo Mode",
                        "fieldType": "dropdown",
                        "fieldOptions": {
                            "values": [{"option": "1"}, {"option": "0"}]
                        },
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
        "position": [200, 480],
        "webhookId": "demo01-video-clips",
        "parameters": {
            "httpMethod": "POST",
            "path": "demo01-video-clips",
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
        "position": [420, 370],
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "sourceUrl", "type": "string",
                     "value": "={{ $json['Video URL'] || $json.sourceUrl || '" + FIXTURE_VIDEO["sourceUrl"] + "' }}"},
                    {"id": uid(), "name": "title", "type": "string",
                     "value": "={{ $json['Title'] || $json.title || '" + FIXTURE_VIDEO["title"] + "' }}"},
                    {"id": uid(), "name": "demoMode", "type": "string",
                     "value": "={{ String($json['Demo Mode'] ?? $json.demoMode ?? '1') }}"},
                    {"id": uid(), "name": "brandVoice", "type": "string", "value": BRAND_VOICE},
                    {"id": uid(), "name": "videoId", "type": "string",
                     "value": "={{ 'VID-' + $now.toFormat('yyyyLLdd-HHmmss') }}"},
                    {"id": uid(), "name": "fixtureSegments", "type": "string",
                     "value": json.dumps(FIXTURE_TRANSCRIPT_SEGMENTS)},
                ]
            },
            "options": {},
        },
    })

    # --- 3. DEMO_MODE Switch --------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "DEMO_MODE Switch",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [640, 370],
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

    # --- 4a. Load Fixture Segments (DEMO path) --------------------------
    nodes.append({
        "id": uid(),
        "name": "Load Fixture Segments",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [860, 260],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const cfg = $('Demo Config').first().json;
const segs = JSON.parse(cfg.fixtureSegments || '[]');
return segs.map((s, i) => ({
  json: {
    videoId: cfg.videoId,
    sourceUrl: cfg.sourceUrl,
    title: cfg.title,
    segmentIdx: i + 1,
    startSec: s.startSec,
    endSec: s.endSec,
    durationSec: s.endSec - s.startSec,
    hook: s.hook,
    summary: s.summary,
    retentionScore: s.retentionScore,
    clipUrl: s.clipUrl,
    source: 'fixture',
  }
}));""",
        },
    })

    # --- 4b. Transcribe with AssemblyAI (LIVE path) ---------------------
    nodes.append({
        "id": uid(),
        "name": "Submit Transcription",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [860, 480],
        "parameters": {
            "method": "POST",
            "url": f"{ASSEMBLYAI_API_URL}/transcript",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "={{ $env.ASSEMBLYAI_API_KEY || 'MISSING' }}"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ audio_url: $('Demo Config').first().json.sourceUrl, auto_highlights: true, auto_chapters: true }) }}",
            "options": {"timeout": 30000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 4b'. Wait Poll for Transcription Complete ----------------------
    # In the live path we'd poll /transcript/{id} until status=completed.
    # For the demo workflow we keep this as a placeholder so the node map
    # reads correctly; prospects should see that the live path exists.
    nodes.append({
        "id": uid(),
        "name": "Poll Transcription",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1080, 480],
        "parameters": {
            "method": "GET",
            "url": "={{ 'https://api.assemblyai.com/v2/transcript/' + ($json.id || 'MISSING') }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Authorization", "value": "={{ $env.ASSEMBLYAI_API_KEY || 'MISSING' }}"}
                ]
            },
            "options": {"timeout": 30000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 4b''. AI Segment Picker (LIVE) ---------------------------------
    nodes.append({
        "id": uid(),
        "name": "AI Segment Picker",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1300, 480],
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
                f"model: '{AI_MODEL_SEGMENTS}', "
                "max_tokens: 2000, "
                "temperature: 0.4, "
                "messages: [{role:'user', content: "
                "'Given this transcript with timestamps, return the 5 segments MOST LIKELY to go viral as 20-40s short-form clips. Pick for emotional punch, quotable lines, or contrarian framing. Return STRICT JSON: {\"segments\":[{\"startSec\":n,\"endSec\":n,\"hook\":\"...\",\"summary\":\"...\",\"retentionScore\":0-100}]}\\n\\nTranscript: ' "
                "+ JSON.stringify($json.utterances || $json.text || '')"
                "}] "
                "}) }}"
            ),
            "options": {"timeout": 60000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 4b'''. Render Clips via Remotion (LIVE) ------------------------
    # In a real build this would loop per segment. We keep a single node
    # with a structured body so the prospect sees the integration point.
    nodes.append({
        "id": uid(),
        "name": "Remotion Render (Live)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1520, 480],
        "parameters": {
            "method": "POST",
            "url": f"{REMOTION_RENDER_URL}/render",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({ "
                "composition: 'ClipWithBurnedCaptions', "
                "props: { "
                "sourceUrl: $('Demo Config').first().json.sourceUrl, "
                "segments: $json.segments || [] "
                "} "
                "}) }}"
            ),
            "options": {"timeout": 300000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 5. Merge Paths --------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Merge Paths",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [1740, 370],
        "parameters": {"mode": "append"},
    })

    # --- 6. Build Platform Copy Prompt ----------------------------------
    nodes.append({
        "id": uid(),
        "name": "Build Platform Copy Prompt",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1960, 370],
        "parameters": {
            "mode": "runOnceForEachItem",
            "jsCode": """const v = $json;
const cfg = $('Demo Config').first().json;
const prompt = `You are a direct-response copywriter for ${cfg.brandVoice}.

Write platform-optimised captions for this clip (NOT hooks — the hook is
burned into the video; captions accompany the post).

Clip metadata:
- Title: ${cfg.title}
- Hook (burned in): "${v.hook}"
- Summary: ${v.summary}
- Duration: ${v.durationSec}s

Produce captions for: tiktok, instagram, youtube, linkedin.

Per platform:
- tiktok     : 1-2 lines + 3 niche hashtags. Playful.
- instagram  : 3-5 lines, 1 emoji, ends with DM-call-to-action. 3 hashtags.
- youtube    : SEO-friendly one-sentence description. No hashtags.
- linkedin   : 4-6 lines, no emoji, 1 line per idea, ends with a question.

Return STRICT JSON:
{
  "copy": {
    "tiktok":   {"caption":"...","hashtags":["...","...","..."]},
    "instagram":{"caption":"...","hashtags":["...","...","..."]},
    "youtube":  {"caption":"..."},
    "linkedin": {"caption":"..."}
  }
}`;
return { json: { ...v, copyPrompt: prompt } };""",
        },
    })

    # --- 7. AI Platform Copy --------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "AI Platform Copy",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2180, 370],
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
                f"model: '{AI_MODEL_COPY}', "
                "max_tokens: 1200, "
                "temperature: 0.7, "
                "messages: [{role:'user', content: $json.copyPrompt}] "
                "}) }}"
            ),
            "options": {"timeout": 30000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 8. Parse Copy --------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Parse Copy",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2400, 370],
        "parameters": {
            "mode": "runOnceForEachItem",
            "jsCode": """const clip = $('Build Platform Copy Prompt').item.json;
const aiResp = $json || {};

let raw = '';
try {
  raw = aiResp.choices && aiResp.choices[0] && aiResp.choices[0].message
    ? aiResp.choices[0].message.content : '';
} catch (e) { raw = ''; }

let copy = null;
try {
  const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
  const parsed = cleaned ? JSON.parse(cleaned) : {};
  copy = parsed.copy || null;
} catch (e) { copy = null; }

if (!copy) {
  copy = {
    tiktok:    { caption: clip.hook, hashtags: ['#AIforSMEs','#BusinessAutomation','#SA'] },
    instagram: { caption: clip.hook + '\\n\\nDM us GO', hashtags: ['#smegrowth','#aibusiness','#anyvision'] },
    youtube:   { caption: clip.title + ' — ' + clip.summary },
    linkedin:  { caption: clip.hook + '\\n\\n' + clip.summary + '\\n\\nWhat would you do first?' }
  };
}

return { json: { ...clip, copy } };""",
        },
    })

    # --- 9. Log Clip to Airtable ----------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Log Clip to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2620, 370],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_VIDEO_CLIPS},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Video ID": "={{ $json.videoId }}",
                    "Title": "={{ $json.title }}",
                    "Source URL": "={{ $json.sourceUrl }}",
                    "Segment Idx": "={{ $json.segmentIdx }}",
                    "Start Sec": "={{ $json.startSec }}",
                    "End Sec": "={{ $json.endSec }}",
                    "Duration Sec": "={{ $json.durationSec }}",
                    "Hook": "={{ $json.hook }}",
                    "Summary": "={{ $json.summary }}",
                    "Retention Score": "={{ $json.retentionScore }}",
                    "Clip URL": "={{ $json.clipUrl }}",
                    "Caption TikTok": "={{ $json.copy && $json.copy.tiktok ? $json.copy.tiktok.caption : '' }}",
                    "Caption Instagram": "={{ $json.copy && $json.copy.instagram ? $json.copy.instagram.caption : '' }}",
                    "Caption YouTube": "={{ $json.copy && $json.copy.youtube ? $json.copy.youtube.caption : '' }}",
                    "Caption LinkedIn": "={{ $json.copy && $json.copy.linkedin ? $json.copy.linkedin.caption : '' }}",
                    "Source": "={{ $json.source || 'live' }}",
                    "Created At": "={{ new Date().toISOString() }}",
                },
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 10. Aggregate Clips --------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Aggregate Clips",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2840, 370],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all().map(i => i.json);
const cfg = $('Demo Config').first().json;
return [{
  json: {
    videoId: cfg.videoId,
    title: cfg.title,
    sourceUrl: cfg.sourceUrl,
    clipsProduced: items.length,
    clips: items.map(c => ({
      segmentIdx: c.segmentIdx,
      hook: c.hook,
      clipUrl: c.clipUrl,
      durationSec: c.durationSec,
      retentionScore: c.retentionScore,
      copy: c.copy,
    })),
    timestamp: new Date().toISOString(),
    status: 'complete',
  }
}];""",
        },
    })

    # --- 11. Respond ----------------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Respond",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [3060, 370],
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
        "Demo Config": {"main": [[{"node": "DEMO_MODE Switch", "type": "main", "index": 0}]]},
        "DEMO_MODE Switch": {
            "main": [
                [{"node": "Load Fixture Segments", "type": "main", "index": 0}],
                [{"node": "Submit Transcription", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Segments": {"main": [[{"node": "Merge Paths", "type": "main", "index": 0}]]},
        "Submit Transcription": {"main": [[{"node": "Poll Transcription", "type": "main", "index": 0}]]},
        "Poll Transcription": {"main": [[{"node": "AI Segment Picker", "type": "main", "index": 0}]]},
        "AI Segment Picker": {"main": [[{"node": "Remotion Render (Live)", "type": "main", "index": 0}]]},
        "Remotion Render (Live)": {"main": [[{"node": "Merge Paths", "type": "main", "index": 1}]]},
        "Merge Paths": {"main": [[{"node": "Build Platform Copy Prompt", "type": "main", "index": 0}]]},
        "Build Platform Copy Prompt": {"main": [[{"node": "AI Platform Copy", "type": "main", "index": 0}]]},
        "AI Platform Copy": {"main": [[{"node": "Parse Copy", "type": "main", "index": 0}]]},
        "Parse Copy": {"main": [[{"node": "Log Clip to Airtable", "type": "main", "index": 0}]]},
        "Log Clip to Airtable": {"main": [[{"node": "Aggregate Clips", "type": "main", "index": 0}]]},
        "Aggregate Clips": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
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

    if "REPLACE" in TABLE_VIDEO_CLIPS:
        print("WARNING: DEMO_TABLE_VIDEO_CLIPS not set in .env")
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
