"""META Kill-Switch — emergency n8n workflow that pauses every active Meta campaign.

Reuses the existing facebookGraphApi credential (N8N_CRED_META_ADS) so no token
ever leaves n8n. Manual-trigger only, safe to execute on demand.

Node chain:
    Manual Trigger
        -> List Meta Campaigns (facebookGraphApi GET /act_xxx/campaigns)
        -> Extract & Filter Active (Code: keep non-PAUSED/DELETED/ARCHIVED)
        -> Pause Campaign (facebookGraphApi POST /{id}?status=PAUSED)  [continueOnFail]
        -> Summarize Results (Code: tally success/fail)

Usage:
    python tools/deploy_meta_kill_switch.py build    # write JSON only
    python tools/deploy_meta_kill_switch.py deploy   # POST to n8n
    python tools/deploy_meta_kill_switch.py update   # PUT to existing workflow ID
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "tools"))

from n8n_client import N8nClient  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("meta_kill_switch")

N8N_BASE_URL = os.environ["N8N_BASE_URL"]
N8N_API_KEY = os.environ["N8N_API_KEY"]
META_ADS_ACCOUNT_ID = os.environ["META_ADS_ACCOUNT_ID"]
CRED_META_ADS_ID = os.environ["N8N_CRED_META_ADS"]
CRED_META_ADS = {"id": CRED_META_ADS_ID, "name": "Meta Ads Graph API"}

WORKFLOW_NAME = "ADS — Meta Kill Switch (manual)"
OUTPUT_JSON = ROOT / "workflows" / "ads-dept" / "meta_kill_switch.json"


def uid() -> str:
    return str(uuid.uuid4())


EXTRACT_AND_FILTER_CODE = """
// runOnceForAllItems: expand the Graph API response and drop already-inactive campaigns.
const response = $input.first().json || {};
const data = response.data || [];
const inactive = new Set(['PAUSED', 'DELETED', 'ARCHIVED']);

const toPause = data
  .filter(c => !inactive.has(c.status))
  .map(c => ({
    json: {
      id: c.id,
      name: c.name || '(unnamed)',
      status: c.status,
      effective_status: c.effective_status || '',
      daily_budget_zar: c.daily_budget ? parseFloat(c.daily_budget) / 100 : 0,
      lifetime_budget_zar: c.lifetime_budget ? parseFloat(c.lifetime_budget) / 100 : 0,
    },
  }));

if (toPause.length === 0) {
  // Emit a single sentinel item so downstream nodes don't fail on empty input.
  return [{
    json: {
      id: '__noop__',
      name: 'No active campaigns — nothing to pause',
      status: 'NOOP',
      skip: true,
      daily_budget_zar: 0,
      lifetime_budget_zar: 0,
    },
  }];
}

return toPause;
"""


SUMMARIZE_CODE = """
// runOnceForAllItems: tally pause results and build a summary item.
const items = $input.all();
let paused = 0;
let failed = 0;
let skipped = 0;
const failures = [];
const successes = [];

for (const it of items) {
  const j = it.json || {};
  // Sentinel from the filter step when nothing was active.
  if (j.skip === true || j.status === 'NOOP') {
    skipped += 1;
    continue;
  }
  // After Pause Campaign (facebookGraphApi POST) the $json is the Graph API response.
  // On success Meta returns { success: true }. On failure, an { error: {...} } object.
  // We pair it with the original via $('Extract & Filter Active') lookup inside the node.
  const hadError = !!(j.error || j.errors || (j.httpCode && j.httpCode >= 400));
  if (hadError) {
    failed += 1;
    failures.push({
      id: j.__campaign_id || '(unknown)',
      name: j.__campaign_name || '(unknown)',
      error: JSON.stringify(j.error || j.errors || j).slice(0, 300),
    });
  } else {
    paused += 1;
    successes.push({
      id: j.__campaign_id || '(unknown)',
      name: j.__campaign_name || '(unknown)',
    });
  }
}

return [{
  json: {
    summary: {
      paused,
      failed,
      skipped,
      total_targets: paused + failed,
      timestamp: new Date().toISOString(),
    },
    successes,
    failures,
  },
}];
"""


WEBHOOK_PATH = "meta-kill-switch"


def build_webhook_trigger(position: list[int]) -> dict[str, Any]:
    return {
        "id": uid(),
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": position,
        "webhookId": uid(),
        "parameters": {
            "httpMethod": "POST",
            "path": WEBHOOK_PATH,
            "responseMode": "lastNode",
            "options": {},
        },
    }


def build_fb_list_campaigns(position: list[int]) -> dict[str, Any]:
    # effective_status filter scopes the response to campaigns Meta considers
    # currently spending-eligible, so we don't paginate through thousands of
    # historical PAUSED drafts just to find the handful still running.
    return {
        "id": uid(),
        "name": "List Meta Campaigns",
        "type": "n8n-nodes-base.facebookGraphApi",
        "typeVersion": 1,
        "position": position,
        "credentials": {"facebookGraphApi": CRED_META_ADS},
        "parameters": {
            "httpRequestMethod": "GET",
            "graphApiVersion": "v25.0",
            "node": f"={META_ADS_ACCOUNT_ID}/campaigns",
            "options": {
                "queryParameters": {
                    "parameter": [
                        {
                            "name": "fields",
                            "value": "id,name,status,effective_status,daily_budget,lifetime_budget",
                        },
                        {
                            "name": "effective_status",
                            "value": '["ACTIVE","IN_PROCESS","WITH_ISSUES","PENDING_REVIEW","PENDING_BILLING_INFO","CAMPAIGN_PAUSED"]',
                        },
                        {"name": "limit", "value": "500"},
                    ]
                }
            },
        },
    }


def build_code_node(name: str, code: str, position: list[int]) -> dict[str, Any]:
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {"mode": "runOnceForAllItems", "jsCode": code},
    }


def build_fb_pause(position: list[int]) -> dict[str, Any]:
    return {
        "id": uid(),
        "name": "Pause Campaign",
        "type": "n8n-nodes-base.facebookGraphApi",
        "typeVersion": 1,
        "position": position,
        "credentials": {"facebookGraphApi": CRED_META_ADS},
        "parameters": {
            "httpRequestMethod": "POST",
            "graphApiVersion": "v25.0",
            "node": "={{ $json.skip ? 'me' : $json.id }}",
            "options": {
                "queryParameters": {
                    "parameter": [
                        {"name": "status", "value": "PAUSED"},
                    ]
                }
            },
        },
        "continueOnFail": True,
        "alwaysOutputData": True,
    }


def build_tag_result_node(position: list[int]) -> dict[str, Any]:
    """Joins each pause response with the original campaign metadata so the
    Summarize step can report id+name for each success/failure."""
    code = """
// runOnceForEachItem: attach the original campaign id/name to the pause response.
const paired = $('Extract & Filter Active').all();
const idx = $itemIndex;
const orig = paired[idx] ? paired[idx].json : {};
return {
  json: {
    ...$json,
    __campaign_id: orig.id || null,
    __campaign_name: orig.name || null,
    __skip: orig.skip === true,
  },
};
"""
    return {
        "id": uid(),
        "name": "Tag Result",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {"mode": "runOnceForEachItem", "jsCode": code},
    }


def build_workflow() -> dict[str, Any]:
    trigger = build_webhook_trigger([250, 300])
    list_node = build_fb_list_campaigns([500, 300])
    filter_node = build_code_node("Extract & Filter Active", EXTRACT_AND_FILTER_CODE, [750, 300])
    pause_node = build_fb_pause([1000, 300])
    tag_node = build_tag_result_node([1250, 300])
    summarize_node = build_code_node("Summarize Results", SUMMARIZE_CODE, [1500, 300])

    nodes = [trigger, list_node, filter_node, pause_node, tag_node, summarize_node]

    connections: dict[str, Any] = {
        trigger["name"]: {"main": [[{"node": list_node["name"], "type": "main", "index": 0}]]},
        list_node["name"]: {"main": [[{"node": filter_node["name"], "type": "main", "index": 0}]]},
        filter_node["name"]: {"main": [[{"node": pause_node["name"], "type": "main", "index": 0}]]},
        pause_node["name"]: {"main": [[{"node": tag_node["name"], "type": "main", "index": 0}]]},
        tag_node["name"]: {"main": [[{"node": summarize_node["name"], "type": "main", "index": 0}]]},
    }

    return {
        "name": WORKFLOW_NAME,
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


def save_json(workflow: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    log.info("Wrote %s", OUTPUT_JSON.relative_to(ROOT))


def deploy(workflow: dict[str, Any], workflow_id: str | None) -> str:
    with N8nClient(N8N_BASE_URL, N8N_API_KEY) as client:
        if workflow_id:
            result = client.update_workflow(workflow_id, workflow)
        else:
            result = client.create_workflow(workflow)
        return str(result.get("id", ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "deploy", "update"])
    parser.add_argument("--id", help="Workflow ID (required for update)")
    args = parser.parse_args()

    workflow = build_workflow()
    save_json(workflow)

    if args.action == "build":
        return 0

    if args.action == "update" and not args.id:
        log.error("--id required for update")
        return 2

    wf_id = deploy(workflow, args.id if args.action == "update" else None)
    print()
    print("━" * 70)
    print(f"Workflow ID: {wf_id}")
    print(f"Open: {N8N_BASE_URL}/workflow/{wf_id}")
    print("Execute manually in the n8n UI or via the n8n-cloud MCP.")
    print("━" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
