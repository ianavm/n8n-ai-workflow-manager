"""
Social Content - Carousel Engine (SC-07)

Sheet-driven, approval-gated evolution of SC-06. Turns "shipping a carousel"
into "fill a row in Google Sheets, flip Status to Approved."

Why this exists:
    SC-06 hardcodes one carousel's content in this deploy script. Ian hit his
    Airtable limit and wants a reusable engine with:
      - Google Sheets as content source + log (no Airtable)
      - Human approval gate (Status = Approved)
      - Automatic retry with per-row retry cap
      - Zero code edits per new carousel

Flow:
    Schedule (every 5 min) / Manual / Webhook trigger
      -> Read Carousels sheet
      -> Filter eligible rows (Status=Approved, Posted At empty,
         Scheduled At <= now+10min, Retry Count < 3)
      -> Pick earliest; short-circuit if none
      -> Mark row as Posting (row lock)
      -> Expand image URLs, upload each to Blotato
      -> Aggregate Blotato CDN URLs
      -> Fan out to IG / LI / FB (pageId required for FB)
      -> POST /v2/posts per platform (no retries -- Blotato double-books)
      -> Collect per-platform results
      -> Append one row per platform to Post Log tab
      -> Update Carousels row: Status=Posted/Failed, Posted At, Blotato IDs
      -> Email summary to ian@anyvisionmedia.com

Usage:
    python tools/deploy_sc07_carousel_engine.py build      # Build JSON only
    python tools/deploy_sc07_carousel_engine.py deploy     # Build + push
    python tools/deploy_sc07_carousel_engine.py activate   # Build + deploy + activate

Env vars required (in .env):
    N8N_API_KEY               -- n8n Cloud API key
    CAROUSEL_GSHEET_ID        -- ID of the "AVM Carousel Engine" Google Sheet
                                 (run setup_carousel_gsheet.py to create it)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from credentials import CRED_BLOTATO, CRED_GMAIL, CRED_GOOGLE_SHEETS  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


# ==================================================================
# CONFIG
# ==================================================================

WORKFLOW_NAME = "Social Content - Carousel Engine (SC-07)"
WORKFLOW_FILENAME = "sc07_carousel_engine.json"

CAROUSEL_GSHEET_ID = os.getenv("CAROUSEL_GSHEET_ID", "REPLACE_WITH_GSHEET_ID")

CAROUSELS_TAB = "Carousels"
POST_LOG_TAB = "Post Log"
ERRORS_TAB = "Errors"

BLOTATO_API_BASE = "https://backend.blotato.com/v2"

BLOTATO_ACCOUNTS = {
    "instagram": {"accountId": "35463", "name": "Instagram (anyvision.media)"},
    "linkedin": {"accountId": "15167", "name": "LinkedIn (Ian Immelman)"},
    "facebook": {
        "accountId": "27283",
        "pageId": "972448295960293",
        "name": "Facebook (Any Vision Media)",
    },
}

NOTIFY_RECIPIENT = os.getenv("SC07_NOTIFY_EMAIL", "ian@anyvisionmedia.com")

MAX_RETRIES = 3
SCHEDULE_LOOKAHEAD_MIN = 10  # pick up rows scheduled within this window
IG_MAX_HASHTAGS = 5


# ==================================================================
# HELPERS
# ==================================================================

def uid() -> str:
    return str(uuid.uuid4())


def _gsheet_doc() -> dict:
    return {"__rl": True, "mode": "id", "value": CAROUSEL_GSHEET_ID}


def _gsheet_tab(name: str) -> dict:
    return {"__rl": True, "mode": "name", "value": name}


# ==================================================================
# NODE BUILDERS
# ==================================================================

def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    # --- Trigger: Schedule (every 5 min) ------------------------------
    nodes.append({
        "id": uid(),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [180, 200],
        "parameters": {
            "rule": {
                "interval": [{"field": "minutes", "minutesInterval": 5}]
            }
        },
    })

    # --- Trigger: Manual ---------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [180, 380],
        "parameters": {},
    })

    # --- Trigger: Webhook --------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [180, 560],
        "webhookId": "sc07-carousel-trigger",
        "parameters": {
            "httpMethod": "POST",
            "path": "sc07-carousel-trigger",
            "responseMode": "lastNode",
            "options": {},
        },
    })

    # --- 1. Read Carousels Sheet -------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Read Carousels Sheet",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [420, 380],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "parameters": {
            "operation": "read",
            "documentId": _gsheet_doc(),
            "sheetName": _gsheet_tab(CAROUSELS_TAB),
            "options": {"range": "A:Z"},
        },
        "onError": "stopWorkflow",
    })

    # --- 2. Filter Eligible Rows --------------------------------------
    # Picks the EARLIEST row matching:
    #   Status == Approved, Posted At empty, Scheduled At <= now+10min,
    #   Retry Count < MAX_RETRIES. Returns [] when none -> short-circuits.
    nodes.append({
        "id": uid(),
        "name": "Filter Eligible Rows",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [640, 380],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": f"""const rows = $input.all().map(i => i.json);
const now = new Date();
const cutoff = new Date(now.getTime() + {SCHEDULE_LOOKAHEAD_MIN} * 60 * 1000);

const eligible = rows
  .filter(r =>
    String(r['Status'] || '').trim() === 'Approved' &&
    !String(r['Posted At'] || '').trim() &&
    r['Scheduled At'] &&
    !isNaN(new Date(r['Scheduled At']).getTime()) &&
    new Date(r['Scheduled At']) <= cutoff &&
    Number(r['Retry Count'] || 0) < {MAX_RETRIES} &&
    String(r['Carousel ID'] || '').trim() !== '' &&
    String(r['Image URLs'] || '').trim() !== ''
  )
  .sort((a, b) => new Date(a['Scheduled At']) - new Date(b['Scheduled At']));

if (eligible.length === 0) {{
  return [];
}}

return [{{ json: eligible[0] }}];""",
        },
    })

    # --- 3. Carousel Config (Set) -------------------------------------
    # Normalises the sheet row into the shape downstream nodes expect.
    # Hashtags are split; IG hashtags are capped at {IG_MAX_HASHTAGS}.
    nodes.append({
        "id": uid(),
        "name": "Carousel Config",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [860, 380],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": f"""const row = $input.first().json;

function splitUrls(s) {{
  return String(s || '')
    .split(/[\\n,]+/)
    .map(x => x.trim())
    .filter(Boolean);
}}

function splitTags(s) {{
  return String(s || '')
    .split(/[\\s,]+/)
    .map(x => x.trim())
    .filter(Boolean)
    .map(t => t.startsWith('#') ? t : '#' + t);
}}

function joinCaption(caption, tags, maxTags) {{
  const limitedTags = maxTags ? tags.slice(0, maxTags) : tags;
  if (limitedTags.length === 0) return caption;
  return caption + '\\n\\n' + limitedTags.join(' ');
}}

const publicImageUrls = splitUrls(row['Image URLs']);
const hashtagsIg = splitTags(row['Hashtags IG']);
const hashtagsLi = splitTags(row['Hashtags LI']);

return [{{
  json: {{
    carouselId: String(row['Carousel ID']).trim(),
    title: String(row['Title'] || '').trim(),
    scheduledAt: new Date(row['Scheduled At']).toISOString(),
    publicImageUrls,
    captionInstagram: joinCaption(String(row['IG Caption'] || ''), hashtagsIg, {IG_MAX_HASHTAGS}),
    captionLinkedin: joinCaption(String(row['LI Caption'] || ''), hashtagsLi, null),
    captionFacebook: String(row['FB Caption'] || ''),
    retryCount: Number(row['Retry Count'] || 0),
    approvedBy: String(row['Approved By'] || '').trim(),
  }}
}}];""",
        },
    })

    # --- 4. Mark In-Progress (Google Sheets upsert) -------------------
    # Locks the row so a concurrent run can't double-post.
    nodes.append({
        "id": uid(),
        "name": "Mark In-Progress",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [1080, 380],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "parameters": {
            "operation": "appendOrUpdate",
            "documentId": _gsheet_doc(),
            "sheetName": _gsheet_tab(CAROUSELS_TAB),
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Carousel ID": "={{ $json.carouselId }}",
                    "Status": "Posting",
                    "Approved At": "={{ new Date().toISOString() }}",
                    "Last Error": "",
                },
                "matchingColumns": ["Carousel ID"],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 5. Expand Images --------------------------------------------
    # Fan out: 1 item per image URL for per-image Blotato media upload.
    nodes.append({
        "id": uid(),
        "name": "Expand Images",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1300, 380],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const cfg = $('Carousel Config').first().json;
const urls = Array.isArray(cfg.publicImageUrls)
  ? cfg.publicImageUrls
  : [];

return urls.map((url, idx) => ({
  json: {
    index: idx,
    url,
    carouselId: cfg.carouselId,
  }
}));""",
        },
    })

    # --- 6. Upload to Blotato (media upload, per-image) ---------------
    nodes.append({
        "id": uid(),
        "name": "Upload to Blotato",
        "type": "@blotato/n8n-nodes-blotato.blotato",
        "typeVersion": 2,
        "position": [1520, 380],
        "parameters": {
            "resource": "media",
            "operation": "upload",
            "useBinaryData": False,
            "mediaUrl": "={{ $json.url }}",
        },
        "credentials": {"blotatoApi": CRED_BLOTATO},
        "onError": "continueRegularOutput",
    })

    # --- 7. Aggregate Blotato URLs (fan-in) ---------------------------
    # IMPORTANT: no executeOnce -- that drops all but the first item.
    nodes.append({
        "id": uid(),
        "name": "Aggregate Blotato URLs",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1740, 380],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all();
const uploadedUrls = items.map(i => {
  const resp = i.json || {};
  return resp.url || resp.mediaUrl || '';
}).filter(Boolean);

const cfg = $('Carousel Config').first().json;

return [{
  json: {
    ...cfg,
    blotatoMediaUrls: uploadedUrls,
    uploadedCount: uploadedUrls.length,
  }
}];""",
        },
    })

    # --- 8. Fan Out Platforms -----------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Fan Out Platforms",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1960, 380],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": f"""const cfg = $input.first().json;
const media = cfg.blotatoMediaUrls || [];
const ACCOUNTS = {json.dumps(BLOTATO_ACCOUNTS)};

function buildPost(platform, accountId, text, extraTarget) {{
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
        ...(extraTarget || {{}}),
      }},
    }},
    scheduledTime: cfg.scheduledAt,
  }};
}}

return [
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
  {{
    json: {{
      platform: 'facebook',
      postBody: buildPost(
        'facebook',
        ACCOUNTS.facebook.accountId,
        cfg.captionFacebook,
        {{ pageId: ACCOUNTS.facebook.pageId }}
      ),
      carouselId: cfg.carouselId,
      scheduledAt: cfg.scheduledAt,
    }}
  }},
];""",
        },
    })

    # --- 9. Post Carousel to Blotato (HTTP, no retries) ---------------
    nodes.append({
        "id": uid(),
        "name": "Post Carousel to Blotato",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2180, 380],
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

    # --- 10. Collect Results ------------------------------------------
    nodes.append({
        "id": uid(),
        "name": "Collect Results",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2400, 380],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all();
const fanout = $('Fan Out Platforms').all();
const cfg = $('Aggregate Blotato URLs').first().json;

function errString(err) {
  if (!err) return null;
  if (typeof err === 'string') return err;
  return err.description || err.message || JSON.stringify(err);
}

const results = items.map((item, idx) => {
  const platform = fanout[idx]?.json?.platform || 'unknown';
  const resp = item.json || {};
  const scheduleId = resp.scheduleId || resp.id || null;
  const submissionId = resp.postSubmissionId || null;
  const error = errString(resp.error) || (resp.message && !submissionId ? resp.message : null);
  return {
    platform,
    success: Boolean(submissionId) && !error,
    submissionId,
    scheduleId,
    error,
    responseSummary: JSON.stringify(resp).slice(0, 500),
  };
});

return results.map(r => ({
  json: {
    ...r,
    carouselId: cfg.carouselId,
    title: cfg.title,
    scheduledAt: cfg.scheduledAt,
  }
}));""",
        },
    })

    # --- 11a. Log per Platform (append) -------------------------------
    nodes.append({
        "id": uid(),
        "name": "Log per Platform",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2620, 260],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "parameters": {
            "operation": "append",
            "documentId": _gsheet_doc(),
            "sheetName": _gsheet_tab(POST_LOG_TAB),
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Log ID": "={{ 'sc07-' + $json.carouselId + '-' + $json.platform + '-' + Date.now() }}",
                    "Carousel ID": "={{ $json.carouselId }}",
                    "Platform": "={{ $json.platform }}",
                    "Status": "={{ $json.success ? 'success' : 'failure' }}",
                    "Blotato Schedule ID": "={{ $json.scheduleId || $json.submissionId || '' }}",
                    "Scheduled At": "={{ $json.scheduledAt }}",
                    "Response Summary": "={{ $json.responseSummary }}",
                    "Error": "={{ $json.error || '' }}",
                    "Created At": "={{ new Date().toISOString() }}",
                },
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 11b. Aggregate Final (fan-in before carousel row update) -----
    nodes.append({
        "id": uid(),
        "name": "Aggregate Final",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2620, 500],
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": """const items = $input.all().map(i => i.json);
const cfg = $('Carousel Config').first().json;
const allSuccess = items.length > 0 && items.every(r => r.success);
const anyFail = items.some(r => !r.success);

const failedPlatforms = items.filter(r => !r.success).map(r => r.platform);
const lastError = items.filter(r => r.error).map(r => r.platform + ': ' + r.error).join(' | ');

const scheduleIds = {};
for (const r of items) {
  scheduleIds[r.platform] = r.scheduleId || r.submissionId || null;
}

const summary = items.map(r =>
  r.success ? r.platform + ': OK (' + (r.scheduleId || r.submissionId) + ')'
            : r.platform + ': FAIL (' + (r.error || 'no id') + ')'
).join(' | ');

return [{
  json: {
    carouselId: cfg.carouselId,
    title: cfg.title,
    scheduledAt: cfg.scheduledAt,
    allSuccess,
    anyFail,
    failedPlatforms,
    lastError,
    scheduleIdsJson: JSON.stringify(scheduleIds),
    retryCount: cfg.retryCount,
    newRetryCount: allSuccess ? cfg.retryCount : cfg.retryCount + 1,
    newStatus: allSuccess ? 'Posted' : 'Failed',
    postedAt: allSuccess ? new Date().toISOString() : '',
    summary,
    timestamp: new Date().toISOString(),
    platformsResults: items,
  }
}];""",
        },
    })

    # --- 12. Update Carousel Row (upsert) -----------------------------
    nodes.append({
        "id": uid(),
        "name": "Update Carousel Row",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [2840, 500],
        "credentials": {"googleSheetsOAuth2Api": CRED_GOOGLE_SHEETS},
        "parameters": {
            "operation": "appendOrUpdate",
            "documentId": _gsheet_doc(),
            "sheetName": _gsheet_tab(CAROUSELS_TAB),
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Carousel ID": "={{ $json.carouselId }}",
                    "Status": "={{ $json.newStatus }}",
                    "Posted At": "={{ $json.postedAt }}",
                    "Blotato Schedule IDs": "={{ $json.scheduleIdsJson }}",
                    "Last Error": "={{ $json.lastError || '' }}",
                    "Retry Count": "={{ $json.newRetryCount }}",
                },
                "matchingColumns": ["Carousel ID"],
                "schema": [],
            },
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    # --- 13. Notify (Gmail) -------------------------------------------
    subject_tpl = "={{ 'SC-07 ' + ($json.allSuccess ? '[OK]' : '[FAIL]') + ' ' + $json.title }}"
    body_tpl = (
        "={{ '<h2>Carousel posting summary</h2>'"
        " + '<p><b>Title:</b> ' + $json.title + '</p>'"
        " + '<p><b>Carousel ID:</b> ' + $json.carouselId + '</p>'"
        " + '<p><b>Scheduled:</b> ' + $json.scheduledAt + '</p>'"
        " + '<p><b>Status:</b> ' + $json.newStatus + '</p>'"
        " + '<p><b>Retry count:</b> ' + $json.newRetryCount + '</p>'"
        " + '<p><b>Per platform:</b><br/>' + $json.summary + '</p>'"
        " + ($json.lastError ? ('<p><b>Errors:</b> ' + $json.lastError + '</p>') : '')"
        " }}"
    )
    nodes.append({
        "id": uid(),
        "name": "Notify",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [3060, 500],
        "credentials": {"gmailOAuth2": CRED_GMAIL},
        "parameters": {
            "resource": "message",
            "operation": "send",
            "sendTo": NOTIFY_RECIPIENT,
            "subject": subject_tpl,
            "emailType": "html",
            "message": body_tpl,
            "options": {},
        },
        "onError": "continueRegularOutput",
    })

    return nodes


def build_connections(nodes: list[dict]) -> dict:
    """Triggers fan-in at 'Read Carousels Sheet', then linear until
    'Collect Results' which forks to per-platform log + aggregate-final.
    """
    connections: dict = {
        "Schedule Trigger": {"main": [[{"node": "Read Carousels Sheet", "type": "main", "index": 0}]]},
        "Manual Trigger": {"main": [[{"node": "Read Carousels Sheet", "type": "main", "index": 0}]]},
        "Webhook Trigger": {"main": [[{"node": "Read Carousels Sheet", "type": "main", "index": 0}]]},
    }

    linear_chain = [
        "Read Carousels Sheet",
        "Filter Eligible Rows",
        "Carousel Config",
        "Mark In-Progress",
        "Expand Images",
        "Upload to Blotato",
        "Aggregate Blotato URLs",
        "Fan Out Platforms",
        "Post Carousel to Blotato",
        "Collect Results",
    ]
    for i in range(len(linear_chain) - 1):
        connections[linear_chain[i]] = {
            "main": [[{"node": linear_chain[i + 1], "type": "main", "index": 0}]]
        }

    # Collect Results forks: per-platform log + aggregate-final.
    connections["Collect Results"] = {
        "main": [[
            {"node": "Log per Platform", "type": "main", "index": 0},
            {"node": "Aggregate Final", "type": "main", "index": 0},
        ]]
    }
    connections["Aggregate Final"] = {
        "main": [[{"node": "Update Carousel Row", "type": "main", "index": 0}]]
    }
    connections["Update Carousel Row"] = {
        "main": [[{"node": "Notify", "type": "main", "index": 0}]]
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

    api_key = os.environ["N8N_API_KEY"]  # raise KeyError if missing
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")

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
            logger.info("  Updated: %s (ID: %s)", result.get("name"), wf_id)
        else:
            result = client.create_workflow(payload)
            wf_id = result.get("id")
            logger.info("  Created: %s (ID: %s)", result.get("name"), wf_id)

        if activate and wf_id:
            client.activate_workflow(wf_id)
            logger.info("  Activated!")

        return wf_id or ""


def main() -> None:
    args = sys.argv[1:]
    action = args[0] if args else "build"

    logger.info("=" * 60)
    logger.info("SC-07 CAROUSEL ENGINE: %s", action)
    logger.info("=" * 60)

    if "REPLACE" in CAROUSEL_GSHEET_ID:
        logger.warning("WARNING: CAROUSEL_GSHEET_ID not set in .env")
        logger.warning("         Google Sheets nodes will fail at runtime.")
        logger.warning("         Run tools/setup_carousel_gsheet.py first.")

    workflow = build_workflow()
    output_path = save_workflow(workflow)
    logger.info(
        "Built %d nodes, %d connections",
        len(workflow["nodes"]),
        len(workflow["connections"]),
    )
    logger.info("Saved: %s", output_path)

    if action == "build":
        logger.info("\nBuild complete. Run with 'deploy' or 'activate' to push to n8n.")
        return

    if action in ("deploy", "activate"):
        logger.info("\nDeploying to n8n...")
        wf_id = deploy_workflow(workflow, activate=(action == "activate"))
        logger.info("\nWorkflow ID: %s", wf_id)


if __name__ == "__main__":
    main()
