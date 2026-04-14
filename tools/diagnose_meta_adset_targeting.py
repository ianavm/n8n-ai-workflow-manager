"""One-shot diagnostic — pulls adset-level targeting for the 5 Meta campaigns
that were paused on 2026-04-14 so we can understand why CPC was R0.10.

Deploys a temporary n8n workflow that uses the existing facebookGraphApi
credential to fetch /{campaign_id}/adsets with targeting, optimization_goal,
billing_event, and bid_strategy. Fires the webhook, reads the execution
result via the n8n API, writes a report to .tmp/meta_adset_targeting.json,
then deletes the temporary workflow.

Usage:
    python tools/diagnose_meta_adset_targeting.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
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
log = logging.getLogger("adset_diagnose")

N8N_BASE_URL = os.environ["N8N_BASE_URL"]
N8N_API_KEY = os.environ["N8N_API_KEY"]
CRED_META_ADS_ID = os.environ["N8N_CRED_META_ADS"]
CRED_META_ADS = {"id": CRED_META_ADS_ID, "name": "Meta Ads Graph API"}
META_ADS_ACCOUNT_ID = os.environ["META_ADS_ACCOUNT_ID"]

# The 5 Meta campaigns paused on 2026-04-14 at 18:41 SAST
CAMPAIGN_IDS = [
    "120240610637340259",  # AI Automation Lead Magnet - Service Pages
    "120240610636970259",  # Q2 Planning Retargeting
    "120240357686180259",  # SA AI Consulting - High Intent Search
    "120240357686020259",  # SMB Workflow Automation - Search Intent
    "120240357685680259",  # AI Transformation Social Proof
]

WORKFLOW_NAME = "DIAG — Meta Adset Targeting (temporary)"
WEBHOOK_PATH = "diag-meta-adset-targeting"
OUTPUT_JSON = ROOT / ".tmp" / "meta_adset_targeting.json"


def uid() -> str:
    return str(uuid.uuid4())


# Iterate input items (one per campaign_id), fetch each campaign's adsets,
# return a flat list.
FETCH_CODE = r"""
const accountId = 'act_26395704183451218';
const campaignIds = [
  '120240610637340259',
  '120240610636970259',
  '120240357686180259',
  '120240357686020259',
  '120240357685680259',
];
// Emit one item per campaign so the downstream facebookGraphApi node
// executes once per campaign via item-iteration.
return campaignIds.map(id => ({ json: { campaign_id: id } }));
"""


AGGREGATE_CODE = r"""
// runOnceForAllItems: aggregate every adset response with its parent campaign id
// (available via the paired input node 'Seed Campaigns'). Produce a single
// summary item that captures targeting + bid/billing for each adset.
const fetches = $input.all();
const seeds = $('Seed Campaigns').all();

const results = [];
for (let i = 0; i < fetches.length; i++) {
  const campId = seeds[i] && seeds[i].json ? seeds[i].json.campaign_id : null;
  const body = fetches[i].json || {};
  const adsets = body.data || [];
  for (const a of adsets) {
    const t = a.targeting || {};
    results.push({
      campaign_id: campId,
      adset_id: a.id,
      adset_name: a.name,
      status: a.status,
      effective_status: a.effective_status,
      optimization_goal: a.optimization_goal,
      billing_event: a.billing_event,
      bid_strategy: a.bid_strategy,
      daily_budget: a.daily_budget,
      lifetime_budget: a.lifetime_budget,
      targeting: {
        age_min: t.age_min,
        age_max: t.age_max,
        genders: t.genders,
        geo_locations: t.geo_locations,
        publisher_platforms: t.publisher_platforms,
        facebook_positions: t.facebook_positions,
        instagram_positions: t.instagram_positions,
        audience_network_positions: t.audience_network_positions,
        interests_count: (t.flexible_spec || []).reduce((n, g) => n + ((g.interests || []).length), 0),
        behaviors_count: (t.flexible_spec || []).reduce((n, g) => n + ((g.behaviors || []).length), 0),
        custom_audiences_count: (t.custom_audiences || []).length,
        excluded_custom_audiences_count: (t.excluded_custom_audiences || []).length,
        has_advantage_plus: !!t.targeting_automation,
      },
    });
  }
}

return [{ json: { adsets: results, total_adsets: results.length } }];
"""


def build_workflow() -> dict[str, Any]:
    webhook = {
        "id": uid(),
        "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [250, 300],
        "webhookId": uid(),
        "parameters": {
            "httpMethod": "POST",
            "path": WEBHOOK_PATH,
            "responseMode": "onReceived",
            "options": {},
        },
    }
    seed = {
        "id": uid(),
        "name": "Seed Campaigns",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [500, 300],
        "parameters": {"mode": "runOnceForAllItems", "jsCode": FETCH_CODE},
    }
    fetch_node = {
        "id": uid(),
        "name": "Fetch Adsets",
        "type": "n8n-nodes-base.facebookGraphApi",
        "typeVersion": 1,
        "position": [750, 300],
        "credentials": {"facebookGraphApi": CRED_META_ADS},
        "parameters": {
            "httpRequestMethod": "GET",
            "graphApiVersion": "v25.0",
            "node": "={{ $json.campaign_id }}/adsets",
            "options": {
                "queryParameters": {
                    "parameter": [
                        {
                            "name": "fields",
                            "value": "id,name,status,effective_status,optimization_goal,billing_event,bid_strategy,daily_budget,lifetime_budget,targeting",
                        },
                        # Meta's default filter omits PAUSED/CAMPAIGN_PAUSED adsets;
                        # explicit list is required to see adsets under paused campaigns.
                        {
                            "name": "effective_status",
                            "value": '["ACTIVE","PAUSED","CAMPAIGN_PAUSED","ADSET_PAUSED","PENDING_REVIEW","DISAPPROVED","PREAPPROVED","PENDING_BILLING_INFO","ARCHIVED","WITH_ISSUES","IN_PROCESS"]',
                        },
                        {"name": "limit", "value": "100"},
                    ]
                }
            },
        },
        "continueOnFail": True,
        "alwaysOutputData": True,
    }
    agg = {
        "id": uid(),
        "name": "Aggregate",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1000, 300],
        "parameters": {"mode": "runOnceForAllItems", "jsCode": AGGREGATE_CODE},
    }

    return {
        "name": WORKFLOW_NAME,
        "nodes": [webhook, seed, fetch_node, agg],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Seed Campaigns", "type": "main", "index": 0}]]},
            "Seed Campaigns": {"main": [[{"node": "Fetch Adsets", "type": "main", "index": 0}]]},
            "Fetch Adsets": {"main": [[{"node": "Aggregate", "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1"},
    }


def main() -> int:
    hdr = {"X-N8N-API-KEY": N8N_API_KEY}
    wf = build_workflow()

    with N8nClient(N8N_BASE_URL, N8N_API_KEY) as client:
        created = client.create_workflow(wf)
        wf_id = created["id"]
    log.info("Created diagnostic workflow id=%s", wf_id)

    try:
        r = httpx.post(f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}/activate", headers=hdr, timeout=30)
        r.raise_for_status()
        log.info("Activated")

        r = httpx.post(f"{N8N_BASE_URL}/webhook/{WEBHOOK_PATH}", json={"trigger": "diag"}, timeout=30)
        log.info("Webhook fired: %s", r.status_code)

        # Poll for completion
        exec_id: str | None = None
        deadline = time.time() + 120
        while time.time() < deadline:
            r = httpx.get(
                f"{N8N_BASE_URL}/api/v1/executions",
                headers=hdr,
                params={"workflowId": wf_id, "limit": 1},
                timeout=30,
            )
            execs = r.json().get("data", [])
            if execs and execs[0].get("stoppedAt"):
                exec_id = execs[0]["id"]
                break
            time.sleep(5)

        if not exec_id:
            log.error("Execution did not complete in 120s")
            return 2

        r = httpx.get(
            f"{N8N_BASE_URL}/api/v1/executions/{exec_id}",
            headers=hdr,
            params={"includeData": "true"},
            timeout=30,
        )
        e = r.json()
        rd = (e.get("data") or {}).get("resultData", {}).get("runData", {})
        agg_runs = rd.get("Aggregate", [])
        if not agg_runs:
            log.error("No Aggregate node output")
            return 2
        items = agg_runs[0].get("data", {}).get("main", [[]])[0]
        summary = items[0].get("json", {}) if items else {}

        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        log.info("Wrote %s — %d adsets", OUTPUT_JSON, summary.get("total_adsets", 0))

        # Print a quick readout
        for a in summary.get("adsets", []):
            t = a.get("targeting", {})
            platforms = t.get("publisher_platforms") or []
            geo = t.get("geo_locations") or {}
            print(
                f"  cid={a['campaign_id']}  adset={a['adset_name'][:30]:30}"
                f"  optim={a.get('optimization_goal','?')}"
                f"  bill={a.get('billing_event','?')}"
                f"  platforms={','.join(platforms) if platforms else 'ALL(default)'}"
                f"  age={t.get('age_min','?')}-{t.get('age_max','?')}"
                f"  interests={t.get('interests_count',0)}"
                f"  custom_audiences={t.get('custom_audiences_count',0)}"
            )

    finally:
        try:
            httpx.post(f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}/deactivate", headers=hdr, timeout=30)
        except Exception:
            pass
        try:
            httpx.delete(f"{N8N_BASE_URL}/api/v1/workflows/{wf_id}", headers=hdr, timeout=30)
            log.info("Cleaned up diagnostic workflow")
        except Exception as exc:
            log.warning("Failed to delete diagnostic workflow: %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
