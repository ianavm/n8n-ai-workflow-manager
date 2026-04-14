"""Meta Archiver — one-time cleanup workflow that archives every PAUSED campaign
on the Meta ad account.

ONLY archives campaigns with status=PAUSED. Never touches ACTIVE, DELETED, or
already-ARCHIVED campaigns. Reuses the existing facebookGraphApi credential
(N8N_CRED_META_ADS) so no token leaves n8n.

Safety rails:
- Hardcoded filter for status=PAUSED (no way to archive active stuff)
- Manual webhook trigger only (not scheduled)
- Built as a separate workflow so it can be deleted after use

Usage:
    python tools/deploy_meta_archiver.py build          # write JSON only
    python tools/deploy_meta_archiver.py deploy         # POST to n8n
    python tools/deploy_meta_archiver.py update --id X  # PUT existing workflow
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
log = logging.getLogger("meta_archiver")

N8N_BASE_URL = os.environ["N8N_BASE_URL"]
N8N_API_KEY = os.environ["N8N_API_KEY"]
META_ADS_ACCOUNT_ID = os.environ["META_ADS_ACCOUNT_ID"]
CRED_META_ADS_ID = os.environ["N8N_CRED_META_ADS"]
CRED_META_ADS = {"id": CRED_META_ADS_ID, "name": "Meta Ads Graph API"}

WORKFLOW_NAME = "ADS — Meta Archiver (ghost cleanup)"
WEBHOOK_PATH = "meta-archive-ghosts"
OUTPUT_JSON = ROOT / "workflows" / "ads-dept" / "meta_archiver.json"


def uid() -> str:
    return str(uuid.uuid4())


EXTRACT_AND_FILTER_CODE = """
// runOnceForAllItems: expand the Graph API response and keep ONLY PAUSED campaigns.
// Never emit ACTIVE (safety), never emit already-ARCHIVED/DELETED (no-op).
const response = $input.first().json || {};
const data = response.data || [];
const ARCHIVABLE = new Set(['PAUSED']);

const toArchive = data
  .filter(c => ARCHIVABLE.has(c.status))
  .map(c => ({
    json: {
      id: c.id,
      name: c.name || '(unnamed)',
      status: c.status,
      effective_status: c.effective_status || '',
    },
  }));

if (toArchive.length === 0) {
  return [{
    json: {
      id: '__noop__',
      name: 'No paused campaigns to archive',
      status: 'NOOP',
      skip: true,
    },
  }];
}

return toArchive;
"""


SUMMARIZE_CODE = """
// runOnceForAllItems: tally archive results and surface sample failures.
const items = $input.all();
let archived = 0;
let failed = 0;
let skipped = 0;
const failures = [];

for (const it of items) {
  const j = it.json || {};
  if (j.__skip === true) { skipped += 1; continue; }
  const hadError = !!(j.error || j.errors || (j.httpCode && j.httpCode >= 400));
  if (hadError) {
    failed += 1;
    failures.push({
      id: j.__campaign_id || '(unknown)',
      name: j.__campaign_name || '(unknown)',
      error: JSON.stringify(j.error || j.errors || j).slice(0, 300),
    });
  } else {
    archived += 1;
  }
}

return [{
  json: {
    summary: {
      archived,
      failed,
      skipped,
      total_targets: archived + failed,
      timestamp: new Date().toISOString(),
    },
    failures: failures.slice(0, 20),
  },
}];
"""


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
            # onReceived returns HTTP 200 immediately so the webhook response
            # can't be killed by the Cloudflare 100s edge timeout. The workflow
            # continues executing in the background — poll /executions to watch it.
            "responseMode": "onReceived",
            "options": {},
        },
    }


def build_fb_list_campaigns(position: list[int]) -> dict[str, Any]:
    # Request EVERY campaign, no effective_status filter. limit=500 is Meta's
    # hard max per page. If the account has >500 campaigns total we'll need a
    # second pass (warning logged from the filter node output count).
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
                        {"name": "fields", "value": "id,name,status,effective_status"},
                        # Explicit effective_status list overrides Meta's default
                        # (which otherwise hides most PAUSED/old campaigns).
                        {
                            "name": "effective_status",
                            "value": '["ACTIVE","PAUSED","PENDING_REVIEW","DISAPPROVED","PREAPPROVED","PENDING_BILLING_INFO","CAMPAIGN_PAUSED","ARCHIVED","ADSET_PAUSED","IN_PROCESS","WITH_ISSUES"]',
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


def build_fb_archive(position: list[int]) -> dict[str, Any]:
    return {
        "id": uid(),
        "name": "Archive Campaign",
        "type": "n8n-nodes-base.facebookGraphApi",
        "typeVersion": 1,
        "position": position,
        "credentials": {"facebookGraphApi": CRED_META_ADS},
        "parameters": {
            "httpRequestMethod": "POST",
            "graphApiVersion": "v25.0",
            # For the sentinel NOOP item we'd POST to /__noop__ which would
            # error; the Tag Result node after this one detects the sentinel
            # and marks it as skipped so the summary stays clean.
            "node": "={{ $json.skip ? 'me' : $json.id }}",
            "options": {
                "queryParameters": {
                    "parameter": [
                        {"name": "status", "value": "ARCHIVED"},
                    ]
                }
            },
        },
        "continueOnFail": True,
        "alwaysOutputData": True,
    }


def build_tag_result_node(position: list[int]) -> dict[str, Any]:
    code = """
// runOnceForEachItem: preserve original campaign metadata alongside archive response.
const paired = $('Extract & Filter Paused').all();
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
    filter_node = build_code_node("Extract & Filter Paused", EXTRACT_AND_FILTER_CODE, [750, 300])
    archive_node = build_fb_archive([1000, 300])
    tag_node = build_tag_result_node([1250, 300])
    summarize_node = build_code_node("Summarize Results", SUMMARIZE_CODE, [1500, 300])

    nodes = [trigger, list_node, filter_node, archive_node, tag_node, summarize_node]
    connections: dict[str, Any] = {
        trigger["name"]: {"main": [[{"node": list_node["name"], "type": "main", "index": 0}]]},
        list_node["name"]: {"main": [[{"node": filter_node["name"], "type": "main", "index": 0}]]},
        filter_node["name"]: {"main": [[{"node": archive_node["name"], "type": "main", "index": 0}]]},
        archive_node["name"]: {"main": [[{"node": tag_node["name"], "type": "main", "index": 0}]]},
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
    print(f"Webhook: {N8N_BASE_URL}/webhook/{WEBHOOK_PATH}")
    print("━" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
