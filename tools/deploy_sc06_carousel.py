"""
Social Content Distribution - Carousel Post (SC-06)

Builds and deploys the SC-06 workflow: a manual-trigger n8n workflow that
posts a multi-image carousel to Blotato across Instagram, LinkedIn, and
Facebook at a scheduled time.

Why this exists:
    SC-05 (existing) uses the @blotato n8n node which only accepts a single
    mediaUrl per post. Carousels (multiple images) aren't exposed by that
    node, so this workflow bypasses it by calling Blotato's REST API directly
    (POST https://backend.blotato.com/v2/posts with content.mediaUrls[] array)
    via an HTTP Request node that borrows the existing 'Blotato AVM'
    credential through predefinedCredentialType=blotatoApi.

    Media upload still uses the existing Blotato node (known to work).

Usage:
    python tools/deploy_sc06_carousel.py build           # Build JSON only
    python tools/deploy_sc06_carousel.py deploy          # Build + push to n8n
    python tools/deploy_sc06_carousel.py activate        # Build + deploy + activate

The Set node "Carousel Config" holds the current carousel's values
(image URLs, captions, scheduled time). Edit it in the n8n UI to post a
different carousel, or re-run this script after editing the constants below.
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
from credentials import CRED_AIRTABLE, CRED_BLOTATO  # noqa: E402

# ==================================================================
# CONFIG
# ==================================================================

WORKFLOW_NAME = "Social Content - Carousel Post (SC-06)"
WORKFLOW_FILENAME = "sc06_carousel_distribution.json"

AIRTABLE_BASE_ID = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TABLE_PRODUCTION_LOG = os.getenv("SC_TABLE_PRODUCTION_LOG", "REPLACE_WITH_TABLE_ID")

BLOTATO_API_BASE = "https://backend.blotato.com/v2"

BLOTATO_ACCOUNTS = {
    "instagram": {"accountId": "35463", "name": "Instagram (anyvision.media)"},
    "linkedin": {"accountId": "15167", "name": "LinkedIn (Ian Immelman)"},
}

# Facebook requires target.pageId. Reconnected 2026-04-15 after permission
# error — new accountId is 27283 (was 23022, revoked). Only the real
# "Any Vision Media" brand page is posted to; "Any Vision Media1" is a
# duplicate and skipped.
FACEBOOK_PAGES = [
    {"accountId": "27283", "pageId": "972448295960293", "name": "Any Vision Media"},
]

# ------------------------------------------------------------------
# Default carousel payload — AI Misconceptions (2026-04-14)
# These populate the "Carousel Config" Set node. They can be edited in
# the n8n UI after deployment to re-post a different carousel.
# ------------------------------------------------------------------

DEFAULT_CAROUSEL_ID = "ai-misconceptions-2026-04-14"

SUPABASE_PUBLIC = (
    "https://qfvsqjsrlnxjplqefhon.supabase.co/storage/v1/object/public/avm-public"
    "/carousels/ai-misconceptions-2026-04-14"
)
DEFAULT_IMAGE_URLS = [
    f"{SUPABASE_PUBLIC}/slide1.png",
    f"{SUPABASE_PUBLIC}/slide2.png",
    f"{SUPABASE_PUBLIC}/slide3.png",
]

DEFAULT_SCHEDULED_AT = "2026-04-15T06:00:00Z"  # 2026-04-15 08:00 SAST

CAPTION_INSTAGRAM = """Most business owners are getting AI completely wrong.

They think it's:
→ Too complex to learn
→ A threat to their team
→ Overhyped Silicon Valley noise

Meanwhile, the SMEs who figured it out are quietly:
→ Cutting admin time by 70%
→ Doubling their content output
→ Closing deals while they sleep

The gap between "AI-aware" and "AI-active" businesses is widening fast.

Which side will you be on in 6 months?

💬 DM "AI" and we'll send you the exact 5 tools we use to run AnyVision Media — no fluff, no jargon, just what works.

.
.
.

#AIforBusiness #SMEgrowth #BusinessAutomation #AItools #AnyVisionMedia"""

CAPTION_LINKEDIN = """Most business owners are getting AI completely wrong.

They think it's:
→ Too complex to implement
→ A threat to their team
→ Overhyped industry noise

Meanwhile, the SMEs who figured it out are:
→ Cutting admin time by 70%
→ Doubling their content output
→ Closing deals at a compounding rate

The gap between "AI-aware" and "AI-active" businesses is widening every single week.

Which side will you be on in 6 months?

If you're an SME owner ready to deploy real AI tools — not chatbots, not demos — comment "AI" below or DM me, and I'll send you the exact 5-tool stack we use to run AnyVision Media.

#AIforBusiness #SME #DigitalTransformation #BusinessAutomation #Leadership #Entrepreneurship"""

CAPTION_FACEBOOK = """Most business owners are getting AI completely wrong.

They think it's:
→ Too complex to learn
→ A threat to their team
→ Overhyped tech marketing

Meanwhile, the SMEs who figured it out are quietly:
→ Cutting admin time by 70%
→ Doubling their content output
→ Closing deals while they sleep

The gap between "AI-aware" and "AI-active" businesses is widening fast.

Which side will you be on in 6 months?

Message us "AI" and we'll send you the exact 5 tools we use to run AnyVision Media."""


# ==================================================================
# HELPERS
# ==================================================================

def uid() -> str:
    return str(uuid.uuid4())


# ==================================================================
# NODE BUILDERS
# ==================================================================

def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    # --- 1a. Manual Trigger (for UI-based runs) ---
    nodes.append({
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [200, 300],
        "parameters": {},
    })

    # --- 1b. Webhook Trigger (for programmatic runs via n8n MCP / curl) ---
    nodes.append({
        "id": uid(),
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [200, 500],
        "webhookId": "sc06-carousel-trigger",
        "parameters": {
            "httpMethod": "POST",
            "path": "sc06-carousel-trigger",
            "responseMode": "lastNode",
            "options": {},
        },
    })

    # --- 2. Carousel Config (Set) ---
    # Holds all the per-carousel config. Edit values here (or in the n8n UI)
    # to post a different carousel.
    nodes.append({
        "id": uid(),
        "name": "Carousel Config",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [420, 400],
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {
                "assignments": [
                    {"id": uid(), "name": "carouselId", "type": "string", "value": DEFAULT_CAROUSEL_ID},
                    {"id": uid(), "name": "scheduledAt", "type": "string", "value": DEFAULT_SCHEDULED_AT},
                    {"id": uid(), "name": "captionInstagram", "type": "string", "value": CAPTION_INSTAGRAM},
                    {"id": uid(), "name": "captionLinkedin", "type": "string", "value": CAPTION_LINKEDIN},
                    {"id": uid(), "name": "captionFacebook", "type": "string", "value": CAPTION_FACEBOOK},
                    {"id": uid(), "name": "publicImageUrls", "type": "array", "value": json.dumps(DEFAULT_IMAGE_URLS)},
                ]
            },
            "options": {},
        },
    })

    # --- 3. Expand Images (Code, fan-out) ---
    # Output 1 item per public image URL so the Upload node runs 3 times.
    nodes.append({
        "id": uid(),
        "name": "Expand Images",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [640, 400],
        "parameters": {
            "jsCode": """const config = $input.first().json;
const urls = Array.isArray(config.publicImageUrls)
  ? config.publicImageUrls
  : JSON.parse(config.publicImageUrls || '[]');

return urls.map((url, idx) => ({
  json: {
    index: idx,
    url,
    // pass the rest of config through for downstream merge
    carouselId: config.carouselId,
    scheduledAt: config.scheduledAt,
    captionInstagram: config.captionInstagram,
    captionLinkedin: config.captionLinkedin,
    captionFacebook: config.captionFacebook,
    publicImageUrls: urls,
  }
}));""",
        },
    })

    # --- 4. Upload to Blotato (n8n Blotato node, resource=media) ---
    nodes.append({
        "id": uid(),
        "name": "Upload to Blotato",
        "type": "@blotato/n8n-nodes-blotato.blotato",
        "typeVersion": 2,
        "position": [860, 400],
        "parameters": {
            "resource": "media",
            "operation": "upload",
            "useBinaryData": False,
            "mediaUrl": "={{ $json.url }}",
        },
        "credentials": {"blotatoApi": CRED_BLOTATO},
        "onError": "continueRegularOutput",
    })

    # --- 5. Aggregate URLs (Code, fan-in, runOnceForAllItems) ---
    # Collect the 3 Blotato-hosted URLs into a single array alongside config.
    # IMPORTANT: No `executeOnce: true` here — that caused the node to only
    # see the first input item, dropping 2 of 3 uploaded URLs.
    nodes.append({
        "id": uid(),
        "name": "Aggregate Blotato URLs",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1080, 400],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all();
const uploadedUrls = items.map(i => {
  const resp = i.json || {};
  return resp.url || resp.mediaUrl || '';
}).filter(Boolean);

const config = $('Carousel Config').first().json;

return [{
  json: {
    carouselId: config.carouselId,
    scheduledAt: config.scheduledAt,
    captionInstagram: config.captionInstagram,
    captionLinkedin: config.captionLinkedin,
    captionFacebook: config.captionFacebook,
    publicImageUrls: Array.isArray(config.publicImageUrls)
      ? config.publicImageUrls
      : JSON.parse(config.publicImageUrls || '[]'),
    blotatoMediaUrls: uploadedUrls,
    uploadedCount: uploadedUrls.length,
  }
}];""",
        },
    })

    # --- 6. Fan Out Platforms (Code) ---
    # Produce 1 item per target platform/page with a ready-to-send post body.
    # Facebook target requires an explicit pageId (unlike IG/LI). Fan out
    # to BOTH connected FB pages.
    nodes.append({
        "id": uid(),
        "name": "Fan Out Platforms",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1300, 400],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": f"""const cfg = $input.first().json;
const media = cfg.blotatoMediaUrls || [];

const ACCOUNTS = {json.dumps(BLOTATO_ACCOUNTS)};
const FB_PAGES = {json.dumps(FACEBOOK_PAGES)};

function buildPost(platform, accountId, text, extraTarget = {{}}) {{
  return {{
    post: {{
      accountId,
      content: {{
        text,
        mediaUrls: media,
        platform,
      }},
      target: {{
        targetType: platform,
        ...extraTarget,
      }},
    }},
    scheduledTime: cfg.scheduledAt,
  }};
}}

const out = [
  {{
    json: {{
      platform: 'instagram',
      postBody: buildPost('instagram', ACCOUNTS.instagram.accountId, cfg.captionInstagram),
      carouselId: cfg.carouselId,
      scheduledAt: cfg.scheduledAt,
    }}
  }},
  {{
    json: {{
      platform: 'linkedin',
      postBody: buildPost('linkedin', ACCOUNTS.linkedin.accountId, cfg.captionLinkedin),
      carouselId: cfg.carouselId,
      scheduledAt: cfg.scheduledAt,
    }}
  }},
];

for (const fb of FB_PAGES) {{
  out.push({{
    json: {{
      platform: 'facebook:' + fb.name,
      postBody: buildPost(
        'facebook',
        fb.accountId,
        cfg.captionFacebook,
        {{ pageId: fb.pageId }}
      ),
      carouselId: cfg.carouselId,
      scheduledAt: cfg.scheduledAt,
    }}
  }});
}}

return out;""",
        },
    })

    # --- 7. Post Carousel to Blotato (HTTP Request) ---
    # Direct REST call to /v2/posts because @blotato node doesn't expose
    # multi-image mediaUrls. Uses the existing Blotato credential via
    # predefinedCredentialType. No retries: Blotato creates a duplicate
    # schedule on retry even when the first call already succeeded.
    nodes.append({
        "id": uid(),
        "name": "Post Carousel to Blotato",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1540, 400],
        "credentials": {"blotatoApi": CRED_BLOTATO},
        "parameters": {
            "method": "POST",
            "url": f"{BLOTATO_API_BASE}/posts",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "blotatoApi",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.postBody) }}",
            "options": {"timeout": 60000},
        },
        "onError": "continueRegularOutput",
    })

    # --- 8. Collect Results (Code) ---
    # No executeOnce: node was previously dropping 2 of 3 items.
    nodes.append({
        "id": uid(),
        "name": "Collect Results",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1780, 400],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all();
const fanout = $('Fan Out Platforms').all();

function errString(err) {
  if (!err) return null;
  if (typeof err === 'string') return err;
  return err.description || err.message || JSON.stringify(err);
}

const results = items.map((item, idx) => {
  const platform = fanout[idx]?.json?.platform || 'unknown';
  const resp = item.json || {};
  const submissionId = resp.postSubmissionId || null;
  const error = errString(resp.error) || (resp.message && !submissionId ? resp.message : null);
  return {
    platform,
    success: Boolean(submissionId) && !error,
    submissionId,
    error,
  };
});

const cfg = $('Aggregate Blotato URLs').first().json;
const summary = results.map(r =>
  r.success
    ? `${r.platform}: OK (${r.submissionId})`
    : `${r.platform}: FAIL (${r.error || 'no id'})`
).join(' | ');

return [{
  json: {
    carouselId: cfg.carouselId,
    scheduledAt: cfg.scheduledAt,
    blotatoMediaUrls: cfg.blotatoMediaUrls,
    publicImageUrls: cfg.publicImageUrls,
    results,
    summary,
    allSuccess: results.every(r => r.success),
    timestamp: new Date().toISOString(),
  }
}];""",
        },
    })

    # --- 9. Log to Airtable (SC_Production_Log) ---
    # Schema (verified via metadata API 2026-04-14):
    #   Log ID (text), Script ID (text), Action (singleSelect),
    #   Platform (singleSelect), Duration Sec (number),
    #   Response (multilineText), Created At (dateTime)
    # We only populate text/multiline/datetime fields to avoid the
    # singleSelect automap trap.
    nodes.append({
        "id": uid(),
        "name": "Log to Airtable",
        "type": "n8n-nodes-base.airtable",
        "typeVersion": 2.1,
        "position": [2020, 400],
        "credentials": {"airtableTokenApi": CRED_AIRTABLE},
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": AIRTABLE_BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_PRODUCTION_LOG},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Log ID": "={{ 'sc06-' + $json.carouselId + '-' + Date.now() }}",
                    "Script ID": "={{ $json.carouselId }}",
                    "Response": "={{ 'SC-06 carousel | ' + ($json.allSuccess ? 'SCHEDULED' : 'PARTIAL') + ' | scheduledAt=' + $json.scheduledAt + ' | ' + $json.summary }}",
                    "Created At": "={{ $json.timestamp }}",
                },
                "matchingColumns": [],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    return nodes


def build_connections(nodes: list[dict]) -> dict:
    """Both triggers flow into Carousel Config, then linear chain."""
    chain = [
        "Carousel Config",
        "Expand Images",
        "Upload to Blotato",
        "Aggregate Blotato URLs",
        "Fan Out Platforms",
        "Post Carousel to Blotato",
        "Collect Results",
        "Log to Airtable",
    ]
    connections: dict = {
        "Manual Trigger": {"main": [[{"node": "Carousel Config", "type": "main", "index": 0}]]},
        "Webhook Trigger": {"main": [[{"node": "Carousel Config", "type": "main", "index": 0}]]},
    }
    for i in range(len(chain) - 1):
        connections[chain[i]] = {
            "main": [[{"node": chain[i + 1], "type": "main", "index": 0}]]
        }
    return connections


# ==================================================================
# BUILD / DEPLOY / ACTIVATE
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
    output_dir = Path(__file__).parent.parent / "workflows" / "social-content-dept"
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
            print(f"  Updated: {result.get('name')} (ID: {wf_id})")
        else:
            result = client.create_workflow(payload)
            wf_id = result.get("id")
            print(f"  Created: {result.get('name')} (ID: {wf_id})")

        if activate and wf_id:
            client.activate_workflow(wf_id)
            print("  Activated!")

        return wf_id or ""


def main() -> None:
    args = sys.argv[1:]
    action = args[0] if args else "build"

    print("=" * 60)
    print(f"SC-06 CAROUSEL WORKFLOW: {action}")
    print("=" * 60)

    if "REPLACE" in TABLE_PRODUCTION_LOG:
        print("WARNING: SC_TABLE_PRODUCTION_LOG not set in .env")
        print("         Airtable log step will fail at runtime.")

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
        print("\nNext: run this workflow manually via n8n UI or")
        print(f"      python -c \"from tools.n8n_client import N8nClient; ...\"  # trigger by ID {wf_id}")


if __name__ == "__main__":
    main()
