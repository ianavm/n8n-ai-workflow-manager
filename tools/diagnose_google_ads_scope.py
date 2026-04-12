"""One-shot Google Ads mutate-scope diagnostic.

Creates a throwaway n8n workflow that runs 3 probes against the Google Ads
API using the existing `googleAdsOAuth2Api` credential:

  1. List Accessible Customers   -> auth + developer token sanity check
  2. Search specific campaign    -> customer ID + manager header + read path
  3. Validate-only mutate        -> definitive write-path check (no side effect)

Probes all run with `continueOnFail: true` so the summary always fires.
After the result comes back, the workflow is deactivated + deleted.

Usage: python tools/diagnose_google_ads_scope.py
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
log = logging.getLogger("diag_gads")

sys.path.insert(0, str(Path(__file__).parent))
from n8n_client import N8nClient  # noqa: E402

# ── Config ──────────────────────────────────────────────────────────────
N8N_BASE = os.environ["N8N_BASE_URL"].rstrip("/")
N8N_API_KEY = os.environ["N8N_API_KEY"]
CRED_GOOGLE_ADS_ID = os.getenv("N8N_CRED_GOOGLE_ADS", "abkg9bL66BFOj2F3")
CRED_GOOGLE_ADS_NAME = "Google Ads AVM"
GOOGLE_ADS_CUSTOMER_ID = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "5876156009")
GOOGLE_ADS_MANAGER_ID = os.getenv("GOOGLE_ADS_MANAGER_ID", "8709868142")
TEST_CAMPAIGN_ID = "23712857496"  # SA AI Consulting - High Intent Search

WEBHOOK_PATH = f"diag-gads-scope-{uuid.uuid4().hex[:8]}"
WORKFLOW_NAME = "AVM Diag: Google Ads Scope Test (TEMP)"


def uid() -> str:
    return str(uuid.uuid4())


# ── Node builders ───────────────────────────────────────────────────────
def build_webhook() -> dict[str, Any]:
    return {
        "id": uid(),
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [250, 300],
        "webhookId": uid(),
        "parameters": {
            "path": WEBHOOK_PATH,
            "httpMethod": "POST",
            "responseMode": "responseNode",
            "options": {},
        },
    }


def build_gads_http(
    name: str,
    method: str,
    url: str,
    position: list[int],
    body: dict[str, Any] | None = None,
    with_manager_header: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "method": method,
        "url": url,
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googleAdsOAuth2Api",
        "options": {"timeout": 30000, "response": {"response": {"fullResponse": False}}},
    }
    if with_manager_header:
        params["sendHeaders"] = True
        params["headerParameters"] = {
            "parameters": [
                {"name": "login-customer-id", "value": GOOGLE_ADS_MANAGER_ID}
            ]
        }
    if body is not None:
        params["sendBody"] = True
        params["specifyBody"] = "json"
        params["jsonBody"] = json.dumps(body)
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "credentials": {
            "googleAdsOAuth2Api": {
                "id": CRED_GOOGLE_ADS_ID,
                "name": CRED_GOOGLE_ADS_NAME,
            }
        },
        "continueOnFail": True,
        "alwaysOutputData": True,
        "parameters": params,
    }


COLLECT_CODE = r"""
// Classify each probe and emit one summary object.
function classify(nodeName) {
  let item;
  try {
    item = $(nodeName).first().json;
  } catch (e) {
    return {status: 'not_run', message: String(e).slice(0, 300)};
  }
  if (!item) return {status: 'no_data'};
  if (item.error || item.errors) {
    const err = item.error || (Array.isArray(item.errors) ? item.errors[0] : item.errors);
    let msg = '';
    let code = null;
    let desc = '';
    let rawType = '';
    if (typeof err === 'string') {
      msg = err.slice(0, 600);
    } else if (err) {
      msg = (err.message || '').toString().slice(0, 300);
      desc = (err.description || '').toString().slice(0, 800);
      code = err.httpCode || err.code || err.status || null;
      rawType = err.name || err.type || '';
    }
    // Also grab any raw JSON body if present
    let raw = '';
    try { raw = JSON.stringify(item).slice(0, 800); } catch (e) {}
    return {status: 'failed', message: msg, description: desc, httpCode: code, type: rawType, raw};
  }
  let preview = '';
  try { preview = JSON.stringify(item).slice(0, 400); } catch (e) {}
  return {status: 'ok', preview};
}

const probe1 = classify('Probe 1 List Customers');
const probe2 = classify('Probe 2 Search Campaign');
const probe3 = classify('Probe 3 ValidateOnly Mutate');

// Derive diagnosis
let diagnosis = 'unknown';
let next_step = '';
if (probe1.status === 'failed') {
  diagnosis = 'auth_or_dev_token';
  next_step = 'Reconnect the googleAdsOAuth2Api credential in n8n. Confirm the developer token field is populated.';
} else if (probe1.status === 'ok' && probe2.status === 'failed') {
  diagnosis = 'customer_or_campaign_id';
  next_step = 'Verify customer ID 5876156009, manager ID 8709868142, and campaign ID 23712857496 in the Google Ads UI.';
} else if (probe1.status === 'ok' && probe2.status === 'ok' && probe3.status === 'failed') {
  diagnosis = 'mutate_scope_missing';
  next_step = 'Re-auth the credential with full https://www.googleapis.com/auth/adwords scope (not read-only).';
} else if (probe1.status === 'ok' && probe2.status === 'ok' && probe3.status === 'ok') {
  diagnosis = 'all_ok';
  next_step = 'Everything works. Budget Enforcer is fully armed for Google Ads.';
}

return [{
  json: {
    customer_id: '5876156009',
    manager_id: '8709868142',
    test_campaign_id: '23712857496',
    probes: {
      '1_list_customers': probe1,
      '2_search_campaign': probe2,
      '3_validate_only_mutate': probe3,
    },
    diagnosis,
    next_step,
    ts: new Date().toISOString(),
  }
}];
"""


def build_workflow_dict() -> dict[str, Any]:
    base_url = "https://googleads.googleapis.com/v20"
    nodes = [
        build_webhook(),
        build_gads_http(
            "Probe 1 List Customers",
            "GET",
            f"{base_url}/customers:listAccessibleCustomers",
            [500, 150],
        ),
        build_gads_http(
            "Probe 2 Search Campaign",
            "POST",
            f"{base_url}/customers/{GOOGLE_ADS_CUSTOMER_ID}/googleAds:search",
            [500, 300],
            body={
                "query": (
                    "SELECT campaign.id, campaign.name, campaign.status "
                    f"FROM campaign WHERE campaign.id = {TEST_CAMPAIGN_ID}"
                )
            },
            with_manager_header=True,
        ),
        build_gads_http(
            "Probe 3 ValidateOnly Mutate",
            "POST",
            f"{base_url}/customers/{GOOGLE_ADS_CUSTOMER_ID}/campaigns:mutate",
            [500, 450],
            body={
                "operations": [
                    {
                        "update": {
                            "resourceName": (
                                f"customers/{GOOGLE_ADS_CUSTOMER_ID}/"
                                f"campaigns/{TEST_CAMPAIGN_ID}"
                            ),
                            "status": "PAUSED",
                        },
                        "updateMask": "status",
                    }
                ],
                "validateOnly": True,
            },
            with_manager_header=True,
        ),
        {
            "id": uid(),
            "name": "Collect Results",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [800, 300],
            "parameters": {"jsCode": COLLECT_CODE},
        },
        {
            "id": uid(),
            "name": "Respond",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [1050, 300],
            "parameters": {"respondWith": "json", "responseBody": "={{ $json }}"},
        },
    ]

    # Chain sequentially — continueOnFail keeps the chain alive past failures,
    # and the fan-in of multiple parallel branches → single Code node causes
    # "upstream $() not yet run" errors in n8n.
    connections = {
        "Webhook": {
            "main": [[{"node": "Probe 1 List Customers", "type": "main", "index": 0}]]
        },
        "Probe 1 List Customers": {
            "main": [[{"node": "Probe 2 Search Campaign", "type": "main", "index": 0}]]
        },
        "Probe 2 Search Campaign": {
            "main": [[{"node": "Probe 3 ValidateOnly Mutate", "type": "main", "index": 0}]]
        },
        "Probe 3 ValidateOnly Mutate": {
            "main": [[{"node": "Collect Results", "type": "main", "index": 0}]]
        },
        "Collect Results": {
            "main": [[{"node": "Respond", "type": "main", "index": 0}]]
        },
    }

    return {
        "name": WORKFLOW_NAME,
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


# ── Main ────────────────────────────────────────────────────────────────
def print_report(summary: dict[str, Any]) -> None:
    probes = summary.get("probes", {})
    icon = {"ok": "✅", "failed": "❌", "no_data": "⊘", "error": "⚠"}

    print()
    print("━" * 72)
    print("Google Ads Scope Diagnostic")
    print("━" * 72)
    print(f"  customer_id:      {summary.get('customer_id')}")
    print(f"  manager_id:       {summary.get('manager_id')}")
    print(f"  test_campaign_id: {summary.get('test_campaign_id')}")
    print()

    for key, label in [
        ("1_list_customers", "1. List Accessible Customers"),
        ("2_search_campaign", "2. Search Specific Campaign  "),
        ("3_validate_only_mutate", "3. Validate-Only Mutate      "),
    ]:
        p = probes.get(key, {})
        status = p.get("status", "?")
        i = icon.get(status, "?")
        print(f"  {i} {label}  [{status}]")
        if status == "failed":
            msg = p.get("message", "")
            desc = p.get("description", "")
            code = p.get("httpCode") or ""
            print(f"       httpCode: {code}")
            if msg:
                print(f"       message:  {msg[:300]}")
            if desc and desc != msg:
                # Desc may contain the raw Google Ads JSON/HTML — trim noise
                short = desc.replace("\n", " ")[:400]
                print(f"       detail:   {short}")

    print()
    print("━" * 72)
    diag = summary.get("diagnosis", "?")
    print(f"  Diagnosis:  {diag}")
    print(f"  Next step:  {summary.get('next_step', '?')}")
    print("━" * 72)


def main() -> int:
    client = N8nClient(base_url=N8N_BASE, api_key=N8N_API_KEY, max_retries=2)

    wf_dict = build_workflow_dict()
    created = None
    try:
        log.info("Creating diagnostic workflow...")
        created = client.create_workflow(wf_dict)
        wf_id = created["id"]
        log.info("  id=%s", wf_id)

        log.info("Activating...")
        client.activate_workflow(wf_id)

        # n8n cloud needs a beat to register the webhook route
        time.sleep(3)

        webhook_url = f"{N8N_BASE}/webhook/{WEBHOOK_PATH}"
        log.info("POSTing to webhook: %s", webhook_url)
        try:
            r = httpx.post(webhook_url, json={}, timeout=90)
        except httpx.HTTPError as e:
            log.error("Webhook call failed: %s", e)
            return 1

        if r.status_code >= 400:
            log.error("Webhook returned HTTP %d: %s", r.status_code, r.text[:500])
            return 1

        try:
            summary = r.json()
        except ValueError:
            log.error("Non-JSON response: %s", r.text[:500])
            return 1

        if isinstance(summary, list) and summary:
            summary = summary[0]

        print_report(summary)
        return 0 if summary.get("diagnosis") == "all_ok" else 2

    finally:
        if created and created.get("id"):
            wf_id = created["id"]
            try:
                log.info("Cleanup: deactivating %s", wf_id)
                client.deactivate_workflow(wf_id)
            except Exception as e:
                log.warning("deactivate failed: %s", e)
            try:
                log.info("Cleanup: deleting %s", wf_id)
                client.delete_workflow(wf_id)
            except Exception as e:
                log.warning("delete failed: %s", e)
        client.close()


if __name__ == "__main__":
    sys.exit(main())
