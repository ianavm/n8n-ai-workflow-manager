"""WF-12 Meta CAPI Sync — server-side Conversions API backup for form submissions.

Closes the iOS 14+/ad-blocker attribution gap: when the client-side Meta Pixel
is blocked, the browser silently drops the Lead event. WF-12 receives a copy
of the lead via webhook, SHA-256 hashes the PII per Meta's spec, and POSTs
to graph.facebook.com/{PIXEL_ID}/events with the SAME event_id as the client
pixel so Meta deduplicates and counts each lead exactly once.

Flow:
    Webhook (POST /webhook/meta-capi-lead)
        -> Hash PII (code: sha256 email/phone/name, normalize)
        -> Post to Meta CAPI (facebookGraphApi POST /{PIXEL_ID}/events)
        -> Respond to caller

IMPORTANT — setup required before this workflow will fire successfully:
    The existing `facebookGraphApi` credential (4UZH1VRXvVufgvrI) has an
    ads_management-scoped access token for the ad account, but Meta rejects
    CAPI posts to the pixel unless the token also has access to that specific
    pixel asset. On the first smoke test Meta returned:

        "Object with ID '2503365216786353' does not exist, cannot be loaded
         due to missing permissions, or does not support this operation."

    Two ways to fix:

    OPTION A (recommended): Add the pixel as an asset to the existing System
    User in Meta Business Manager.
        1. business.facebook.com → Business Settings → Users → System Users
        2. Select the System User whose token is stored in the n8n credential
        3. "Add Assets" → Data Sources → select pixel 2503365216786353
        4. Grant "Manage Pixel" permission
        5. No new token needed — the existing one inherits the new asset scope

    OPTION B: Generate a dedicated CAPI access token from Events Manager.
        1. business.facebook.com/events_manager → Data Sources → pixel 2503365216786353
        2. Settings → Conversions API → Generate Access Token
        3. Copy the token, create a new n8n credential of type "facebookGraphApi",
           update this deploy script's CRED_META_ADS to point at the new credential ID

    After either fix: activate WF-12 in n8n (currently deactivated) and run the
    smoke test again — `python tools/deploy_wf12_capi_sync.py build` to rebuild
    then curl the webhook with a sample payload. Check Meta Events Manager →
    Test Events → Server Events to confirm the event arrives and dedupes with
    the client pixel eventID.

Usage:
    python tools/deploy_wf12_capi_sync.py build
    python tools/deploy_wf12_capi_sync.py deploy
    python tools/deploy_wf12_capi_sync.py update --id <workflow_id>
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
log = logging.getLogger("wf12_capi_sync")

N8N_BASE_URL = os.environ["N8N_BASE_URL"]
N8N_API_KEY = os.environ["N8N_API_KEY"]
CRED_META_ADS_ID = os.environ["N8N_CRED_META_ADS"]
CRED_META_ADS = {"id": CRED_META_ADS_ID, "name": "Meta Ads Graph API"}

# Pixel ID is embedded in landing-pages/deploy/*.html — matches client-side fbq('init', ...)
META_PIXEL_ID = os.getenv("META_PIXEL_ID", "2503365216786353")

WORKFLOW_NAME = "WF-12 Meta CAPI Sync"
WEBHOOK_PATH = "meta-capi-lead"
OUTPUT_JSON = ROOT / "workflows" / "ads-dept" / "wf12_meta_capi_sync.json"


def uid() -> str:
    return str(uuid.uuid4())


# Hash PII per Meta CAPI spec:
#   - lowercase + trim before hashing
#   - phone: strip non-digits, include country code
#   - SHA-256 hex digest
HASH_PII_CODE = r"""
// Server-side hashing of PII for Meta CAPI.
// Meta requires SHA-256 hex digest of normalised values.
const crypto = require('crypto');

function sha256(s) {
  return crypto.createHash('sha256').update(s).digest('hex');
}

function normaliseEmail(e) {
  return (e || '').toString().trim().toLowerCase();
}

function normalisePhone(p) {
  // strip all non-digits; Meta expects E.164-ish digits (country code + number)
  const digits = (p || '').toString().replace(/\D/g, '');
  // If it starts with 27 (ZA) that's fine; if it starts with 0, replace with 27
  if (digits.startsWith('0')) return '27' + digits.slice(1);
  return digits;
}

function normaliseName(n) {
  return (n || '').toString().trim().toLowerCase();
}

const items = $input.all();
const results = [];

for (const item of items) {
  const body = item.json.body || item.json || {};

  const email = normaliseEmail(body.email);
  const phone = normalisePhone(body.phone);
  const firstName = normaliseName(body.firstName || (body.name || '').split(' ')[0] || '');
  const lastName = normaliseName(body.lastName || (body.name || '').split(' ').slice(1).join(' ') || '');
  const city = normaliseName(body.city);
  const country = 'za';  // AnyVision Media is South African

  // Meta requires em/ph be arrays of hashed values; drop if we don't have it
  const userData = {};
  if (email) userData.em = [sha256(email)];
  if (phone) userData.ph = [sha256(phone)];
  if (firstName) userData.fn = [sha256(firstName)];
  if (lastName) userData.ln = [sha256(lastName)];
  if (city) userData.ct = [sha256(city)];
  userData.country = [sha256(country)];

  // Client IP + UA improve Meta's match quality score
  if (body.client_ip_address) userData.client_ip_address = body.client_ip_address;
  if (body.client_user_agent) userData.client_user_agent = body.client_user_agent;

  // event_id MUST match what the client-side fbq sent, so Meta dedups.
  // If the caller didn't pass one, generate a random id — Meta will just count
  // it as a separate event (no dedup, but still tracked).
  const eventId = body.event_id || ('capi_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10));
  const eventTime = Math.floor(Date.now() / 1000);
  const eventName = body.event_name || 'Lead';

  const customData = {
    currency: body.currency || 'ZAR',
    value: body.value || 5000,
  };
  if (body.content_name) customData.content_name = body.content_name;

  results.push({
    json: {
      // Payload for Meta CAPI /events endpoint
      capi_body: {
        data: [{
          event_name: eventName,
          event_time: eventTime,
          event_id: eventId,
          action_source: 'website',
          event_source_url: body.page_url || body.source_url || 'https://www.anyvisionmedia.com/',
          user_data: userData,
          custom_data: customData,
        }],
      },
      // Echoed fields for the response + debugging
      event_id: eventId,
      event_name: eventName,
      email_hashed: userData.em ? userData.em[0].slice(0, 16) + '…' : null,
      has_phone: !!userData.ph,
    },
  });
}

return results;
"""


RESPONSE_CODE = r"""
// Build a clean response for the frontend caller.
const items = $input.all();
if (items.length === 0) {
  return [{ json: { ok: false, error: 'no items' } }];
}
const d = items[0].json || {};
const capiResp = d.events_received !== undefined ? d : (d.body || {});

return [{
  json: {
    ok: !!(capiResp.events_received && capiResp.events_received > 0),
    event_id: $('Hash PII').first().json.event_id,
    events_received: capiResp.events_received || 0,
    fbtrace_id: capiResp.fbtrace_id || null,
    messages: capiResp.messages || null,
  },
}]
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
            "responseMode": "lastNode",
            "options": {},
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


def build_capi_post(position: list[int]) -> dict[str, Any]:
    """Facebook Graph API node: POST /{PIXEL_ID}/events with the built payload."""
    return {
        "id": uid(),
        "name": "Post to Meta CAPI",
        "type": "n8n-nodes-base.facebookGraphApi",
        "typeVersion": 1,
        "position": position,
        "credentials": {"facebookGraphApi": CRED_META_ADS},
        "parameters": {
            "httpRequestMethod": "POST",
            "graphApiVersion": "v25.0",
            "node": f"={META_PIXEL_ID}/events",
            "options": {
                "queryParameters": {
                    "parameter": [
                        {
                            "name": "data",
                            "value": "={{ JSON.stringify($json.capi_body.data) }}",
                        },
                    ],
                },
            },
        },
        "continueOnFail": True,
        "alwaysOutputData": True,
        "retryOnFail": True,
        "maxTries": 2,
        "waitBetweenTries": 3000,
    }


def build_workflow() -> dict[str, Any]:
    trigger = build_webhook_trigger([250, 300])
    hash_node = build_code_node("Hash PII", HASH_PII_CODE, [500, 300])
    capi_node = build_capi_post([750, 300])
    respond_node = build_code_node("Build Response", RESPONSE_CODE, [1000, 300])

    nodes = [trigger, hash_node, capi_node, respond_node]
    connections: dict[str, Any] = {
        trigger["name"]: {"main": [[{"node": hash_node["name"], "type": "main", "index": 0}]]},
        hash_node["name"]: {"main": [[{"node": capi_node["name"], "type": "main", "index": 0}]]},
        capi_node["name"]: {"main": [[{"node": respond_node["name"], "type": "main", "index": 0}]]},
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
    print(f"Webhook path: /webhook/{WEBHOOK_PATH}")
    print(f"Pixel ID: {META_PIXEL_ID}")
    print("━" * 70)
    print()
    print("Next steps:")
    print("  1. Activate the workflow in n8n")
    print("  2. Verify frontend posts to the CAPI webhook on form submit")
    print("  3. Check Meta Events Manager → Test Events for dedup confirmation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
