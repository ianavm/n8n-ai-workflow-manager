"""Deploy ADS-09: Budget Enforcer.

A schedule-driven n8n workflow that:
1. Reads current spend per campaign from Ad_Performance (last 30 days)
2. Aggregates by day / week / month and compares to caps
   (R666 daily, R5000 weekly, R20000 monthly per AVM_DAILY_HARD_CAP_ZAR etc.)
3. For each violator: pauses the campaign on its native platform
   - Google Ads: HTTP POST to googleads.googleapis.com mutate API
   - Meta Ads:   HTTP POST to graph.facebook.com /{campaign_id} with status=PAUSED
4. Writes a pause event to Brain (or Airtable Approvals fallback)
5. Sends Ian an email with the list of paused campaigns

Runs every 30 minutes — fast enough that no campaign can burn more than
R333 (half daily cap) before being caught.

Build:    python tools/deploy_ads_budget_enforcer.py build
Deploy:   python tools/deploy_ads_budget_enforcer.py deploy
Activate: python tools/deploy_ads_budget_enforcer.py activate

NOTE: Google Ads pause requires the OAuth2 credential to be re-authorized.
Until then, the Google branch will fail-open (continueOnFail) and only
Meta campaigns will be auto-paused. The Brain log will surface the gap.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# Import helpers from the main deploy script — these are stable building blocks
from deploy_ads_dept import (  # type: ignore
    CRED_AIRTABLE,
    CRED_GMAIL,
    CRED_GOOGLE_ADS,
    CRED_META_ADS,
    DAILY_CAP,
    GOOGLE_ADS_CUSTOMER_ID,
    GOOGLE_ADS_MANAGER_ID,
    MARKETING_BASE_ID,
    META_ADS_ACCOUNT_ID,
    MONTHLY_CAP,
    TABLE_CAMPAIGNS,
    TABLE_PERFORMANCE,
    WEEKLY_CAP,
    build_airtable_search,
    build_code_node,
    build_gmail_send,
    build_if_node,
    build_merge_node,
    build_schedule_trigger,
    make_resilient,
)

from n8n_client import N8nClient

ALERT_EMAIL = "ian@anyvisionmedia.com"
WORKFLOW_NAME = "AVM Ads: Budget Enforcer"
OUTPUT_PATH = ROOT / "workflows" / "ads-dept" / "ads09_budget_enforcer.json"

# Brain Writer sub-workflow (AVM: Brain Writer) — logs audit events to Postgres
BRAIN_WF_ID = "XpGdo7DKv3XEpqZc"
SELF_WORKFLOW_ID = "YR6LFkWO9rnNceOp"


def uid() -> str:
    return str(uuid.uuid4())


# ── Code: aggregate spend + flag violations ─────────────────────────────
# CRITICAL: Ad_Performance snapshots have DIFFERENT semantics per platform.
#  - Google Ads (n8n googleAds node): each row is LIFETIME CUMULATIVE since
#    campaign launch. To get totals, take the LATEST snapshot per campaign.
#    To get a day's spend, compute (latest cum on date D) - (latest cum on D-1).
#  - Meta Ads (facebookGraphApi date_preset=today): each row is CUMULATIVE
#    SINCE MIDNIGHT — resets daily. To get a day's spend, take MAX per
#    (campaign, date). To get totals, sum those daily values.
# Naive sum across rows over-counts both platforms.
COMPUTE_VIOLATIONS_CODE = r"""
const items = $input.all();
const DAILY_CAP = """ + str(DAILY_CAP) + r""";
const WEEKLY_CAP = """ + str(WEEKLY_CAP) + r""";
const MONTHLY_CAP = """ + str(MONTHLY_CAP) + r""";

const today = new Date().toISOString().slice(0, 10);
const weekStart = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
const monthStart = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);

// ── Step 1: bucket records ────────────────────────────────────────────
// Google: keep latest snapshot per (campaign, date)  → cumulative-since-launch
// Meta: keep MAX snapshot per (campaign, date)       → cumulative-since-midnight
const googleByDate = {};   // key: name|date  → {date, hour, spend, name, platform, ext_id}
const metaByDate = {};     // key: name|date  → {date, spend, name, platform, ext_id}

function extId(pid) {
  if (!pid) return null;
  const m = pid.match(/^[a-z]+_([^_]+)_/);
  return m ? m[1] : null;
}

for (const item of items) {
  const f = item.json.fields || item.json;
  const name = f['Campaign Name'];
  if (!name) continue;
  const date = (f['Date'] || '').slice(0, 10);
  if (!date) continue;
  const hour = f['Snapshot Hour'] || '';
  const spend = parseFloat(f['Spend ZAR'] || 0);
  const platform = f['Platform'] || 'unknown';
  const id = extId(f['Performance ID'] || '');

  if (platform === 'google_ads') {
    const key = name + '|' + date;
    const cur = googleByDate[key];
    if (!cur || (hour > cur.hour) || (spend > cur.spend)) {
      googleByDate[key] = {date, hour, spend, name, platform, ext_id: id || (cur && cur.ext_id) || null};
    }
  } else if (platform === 'meta_ads') {
    const key = name + '|' + date;
    const cur = metaByDate[key];
    if (!cur || spend > cur.spend) {
      metaByDate[key] = {date, spend, name, platform, ext_id: id || (cur && cur.ext_id) || null};
    }
  }
}

// ── Step 2: compute per-campaign daily/weekly/monthly with platform logic
const byCampaign = {};

// Google: build sorted date list per campaign and compute deltas
const googleByCamp = {};
for (const k of Object.keys(googleByDate)) {
  const r = googleByDate[k];
  if (!googleByCamp[r.name]) googleByCamp[r.name] = [];
  googleByCamp[r.name].push(r);
}
for (const name of Object.keys(googleByCamp)) {
  const rows = googleByCamp[name].sort((a, b) => a.date.localeCompare(b.date));
  const platform = rows[0].platform;
  const ext_id = rows.find(r => r.ext_id)?.ext_id || null;
  let prev = 0;
  let daily = 0, weekly = 0;
  const lifetime = rows[rows.length - 1].spend;
  for (const r of rows) {
    const delta = Math.max(0, r.spend - prev);
    if (r.date === today) daily += delta;
    if (r.date >= weekStart) weekly += delta;
    prev = r.spend;
  }
  byCampaign[name + '|google_ads'] = {
    campaign: name, platform, external_id: ext_id,
    daily, weekly, monthly: lifetime, // lifetime ≈ monthly within 30d window
  };
}

// Meta: daily=max-of-today, weekly=sum of daily-max in last 7 days, monthly=sum in last 30
const metaByCamp = {};
for (const k of Object.keys(metaByDate)) {
  const r = metaByDate[k];
  if (!metaByCamp[r.name]) metaByCamp[r.name] = [];
  metaByCamp[r.name].push(r);
}
for (const name of Object.keys(metaByCamp)) {
  const rows = metaByCamp[name];
  const platform = rows[0].platform;
  const ext_id = rows.find(r => r.ext_id)?.ext_id || null;
  let daily = 0, weekly = 0, monthly = 0;
  for (const r of rows) {
    if (r.date === today) daily += r.spend;
    if (r.date >= weekStart) weekly += r.spend;
    if (r.date >= monthStart) monthly += r.spend;
  }
  byCampaign[name + '|meta_ads'] = {
    campaign: name, platform, external_id: ext_id, daily, weekly, monthly,
  };
}

// ── Step 3: identify violations ────────────────────────────────────────
const violations = [];
let totalDaily = 0, totalWeekly = 0, totalMonthly = 0;
for (const c of Object.values(byCampaign)) {
  totalDaily += c.daily;
  totalWeekly += c.weekly;
  totalMonthly += c.monthly;
  const reasons = [];
  if (c.daily > DAILY_CAP) reasons.push(`daily R${c.daily.toFixed(0)} > R${DAILY_CAP}`);
  if (c.weekly > WEEKLY_CAP) reasons.push(`weekly R${c.weekly.toFixed(0)} > R${WEEKLY_CAP}`);
  if (c.monthly > MONTHLY_CAP) reasons.push(`monthly R${c.monthly.toFixed(0)} > R${MONTHLY_CAP}`);
  if (reasons.length > 0) {
    violations.push({...c, reasons: reasons.join('; '), action: 'PAUSE'});
  }
}

// Global cap breach: top spender pays the price if no individual breach yet
const globalBreach = totalDaily > DAILY_CAP || totalWeekly > WEEKLY_CAP || totalMonthly > MONTHLY_CAP;
if (globalBreach && violations.length === 0) {
  const sorted = Object.values(byCampaign).sort((a, b) => b.daily - a.daily);
  if (sorted[0]) {
    violations.push({
      ...sorted[0],
      reasons: `global breach: daily R${totalDaily.toFixed(0)}/R${DAILY_CAP}, weekly R${totalWeekly.toFixed(0)}/R${WEEKLY_CAP}, monthly R${totalMonthly.toFixed(0)}/R${MONTHLY_CAP}`,
      action: 'PAUSE',
    });
  }
}

if (violations.length === 0) {
  return [{json: {
    skip: true,
    summary: {totalDaily, totalWeekly, totalMonthly, campaignCount: Object.keys(byCampaign).length},
  }}];
}

return violations.map(v => ({json: v}));
"""

# ── Code: route by platform (split google vs meta) ──────────────────────
# CRITICAL: must return [] (not a skip sentinel) when no routable violations.
# A skip sentinel would leak into "Is Google?" and cascade to a bogus pause
# attempt with no external_id, producing "? (?): FAILED" alerts.
ROUTE_PLATFORM_CODE = r"""
// Tag each violation with platform-specific pause payload
const items = $input.all();
const out = [];
for (const item of items) {
  const v = item.json;
  if (v.skip) continue;
  if (!v.external_id) continue;  // can't pause without an id

  const platform = (v.platform || '').toLowerCase();
  if (platform.includes('google')) {
    out.push({json: {...v, _route: 'google'}, pairedItem: {item: items.indexOf(item)}});
  } else if (platform.includes('meta') || platform.includes('facebook')) {
    out.push({json: {...v, _route: 'meta'}, pairedItem: {item: items.indexOf(item)}});
  }
}
return out;  // may be [] — downstream nodes will not execute
"""

# ── Code: tag pause result with recovered violation context ─────────────
# Runs in runOnceForEachItem mode so $('Route by Platform').item.json gives
# the paired upstream violation (survives HTTP pause-node failure).
TAG_GOOGLE_PAUSE_CODE = r"""
// runOnceForEachItem mode
let v = {};
try { v = $('Route by Platform').item.json || {}; } catch (e) { v = {}; }
const errored = !!($json.error || $json.errors || $json.httpCode >= 400);
return {
  json: {
    campaign: v.campaign || '(unknown)',
    platform: 'google_ads',
    external_id: v.external_id || '(no id)',
    reasons: v.reasons || '',
    api_status: errored ? 'FAILED' : 'PAUSED',
    api_error: errored ? JSON.stringify($json.error || $json.errors || $json).slice(0, 500) : null,
    paused_at: new Date().toISOString(),
  },
};
"""

TAG_META_PAUSE_CODE = r"""
// runOnceForEachItem mode
let v = {};
try { v = $('Route by Platform').item.json || {}; } catch (e) { v = {}; }
const errored = !!($json.error || $json.errors || $json.httpCode >= 400);
return {
  json: {
    campaign: v.campaign || '(unknown)',
    platform: 'meta_ads',
    external_id: v.external_id || '(no id)',
    reasons: v.reasons || '',
    api_status: errored ? 'FAILED' : 'PAUSED',
    api_error: errored ? JSON.stringify($json.error || $json.errors || $json).slice(0, 500) : null,
    paused_at: new Date().toISOString(),
  },
};
"""

# ── (Classify Pause Results Code node removed — replaced by an If node
#     routing on api_status === 'PAUSED'. Multi-output Code nodes in n8n
#     v2 fail validation with "Code doesn't return items properly" when
#     returning the documented [[output0],[output1]] shape from certain
#     Merge upstreams, so we use the native If instead.)

# ── Code: format paused summary (success only) ──────────────────────────
FORMAT_PAUSED_SUMMARY_CODE = r"""
const items = $input.all();
const paused = items.map(i => i.json).filter(d =>
  d.api_status === 'PAUSED' &&
  d.campaign && d.campaign !== '(unknown)' &&
  d.platform
);
if (paused.length === 0) {
  return [];  // nothing real to report
}
return [{json: {
  paused,
  count: paused.length,
  summary: paused.map(p => `${p.campaign} (${p.platform}): ${p.reasons || 'cap exceeded'}`).join('\n'),
}}];
"""

# ── Code: format failed summary (failures only) ─────────────────────────
FORMAT_FAILED_SUMMARY_CODE = r"""
const items = $input.all();
const failed = items.map(i => i.json).filter(d => d.api_status === 'FAILED');
if (failed.length === 0) {
  return [];
}
return [{json: {
  failed,
  count: failed.length,
  summary: failed.map(f =>
    `${f.campaign || '(unknown)'} (${f.platform || '(unknown)'}) id=${f.external_id || '?'}: ${f.api_error || 'unknown error'}`
  ).join('\n'),
}}];
"""


# ── Build nodes ─────────────────────────────────────────────────────────
def build_pause_google_node(name: str, position: list[int]) -> dict:
    """HTTP node that pauses a Google Ads campaign via the v20 mutate API.

    v17 is sunset (2025-08). Matches pattern used by ADS-03 Campaign Builder
    in deploy_ads_dept.py::1956. jsonBody is built as an n8n expression so
    `$json.external_id` interpolates per-item.
    """
    # Built as a single n8n expression — the `=` prefix tells n8n to evaluate
    # the JS inside {{}}. JSON.stringify produces the final JSON body.
    json_body_expr = (
        "={{ JSON.stringify({"
        "operations: [{"
        f"update: {{resourceName: 'customers/{GOOGLE_ADS_CUSTOMER_ID}/campaigns/' + $json.external_id, "
        "status: 'PAUSED'}, "
        "updateMask: 'status'"
        "}]"
        "}) }}"
    )
    node = {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "credentials": {"googleAdsOAuth2Api": CRED_GOOGLE_ADS},
        "parameters": {
            "method": "POST",
            "url": f"https://googleads.googleapis.com/v20/customers/{GOOGLE_ADS_CUSTOMER_ID}/campaigns:mutate",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "googleAdsOAuth2Api",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "login-customer-id", "value": GOOGLE_ADS_MANAGER_ID},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": json_body_expr,
            "options": {"timeout": 30000},
        },
    }
    return make_resilient(node, retries=2, wait_ms=5000)


def build_pause_meta_node(name: str, position: list[int]) -> dict:
    """HTTP node that pauses a Meta campaign via Graph API POST /{campaign_id}."""
    node = {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.facebookGraphApi",
        "typeVersion": 1,
        "position": position,
        "credentials": {"facebookGraphApi": CRED_META_ADS},
        "parameters": {
            "httpRequestMethod": "POST",
            "graphApiVersion": "v25.0",
            "node": "={{ $json.external_id }}",
            "options": {
                "queryParameters": {
                    "parameter": [{"name": "status", "value": "PAUSED"}]
                }
            },
        },
    }
    return make_resilient(node, retries=2, wait_ms=5000)


def build_code_node_each(name: str, js_code: str, position: list[int]) -> dict:
    """Code node in runOnceForEachItem mode — lets $('NodeName').item.json
    resolve the paired upstream item even after a failed HTTP pause node."""
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {
            "mode": "runOnceForEachItem",
            "jsCode": js_code,
        },
    }


def build_brain_write_node(
    name: str,
    position: list[int],
    event_type_expr: str,
    severity_expr: str,
    summary_expr: str,
    details_expr: str,
) -> dict:
    """Execute Workflow node that calls AVM: Brain Writer with ADS-09 context.

    All expression strings should be n8n expressions starting with `=`.
    Pattern mirrors deploy_ads_shm.py::Write to Brain.
    """
    return {
        "id": uid(),
        "name": name,
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.2,
        "position": position,
        "onError": "continueRegularOutput",
        "parameters": {
            "workflowId": {"__rl": True, "mode": "id", "value": BRAIN_WF_ID},
            "options": {"waitForSubWorkflow": False},
            "inputData": {
                "values": [
                    {"name": "source", "value": "=n8n:ADS-09"},
                    {"name": "source_type", "value": "=workflow"},
                    {"name": "event_type", "value": event_type_expr},
                    {"name": "severity", "value": severity_expr},
                    {"name": "department", "value": "=ads"},
                    {"name": "summary", "value": summary_expr},
                    {"name": "details", "value": details_expr},
                    {"name": "entity_id", "value": f"={SELF_WORKFLOW_ID}"},
                    {"name": "entity_name", "value": "=AVM Ads: Budget Enforcer"},
                ],
            },
        },
    }


def build_ads09_nodes() -> list[dict]:
    nodes: list[dict] = []

    # 1. Schedule every 30 minutes
    nodes.append(build_schedule_trigger("Schedule Trigger", "*/30 * * * *", [250, 300]))

    # 2. Read 30 days of Ad_Performance
    nodes.append(build_airtable_search(
        "Read Recent Performance",
        MARKETING_BASE_ID, TABLE_PERFORMANCE,
        "=IS_AFTER({Date}, DATEADD(TODAY(), -30, 'days'))",
        [500, 300],
    ))

    # 3. Compute violations
    nodes.append(build_code_node(
        "Compute Violations", COMPUTE_VIOLATIONS_CODE, [750, 300]
    ))

    # 4. If has violations
    nodes.append(build_if_node(
        "Has Violations?", "={{ !$json.skip }}", [1000, 300]
    ))

    # 5. Route by platform
    nodes.append(build_code_node(
        "Route by Platform", ROUTE_PLATFORM_CODE, [1250, 200]
    ))

    # 6. Split into google + meta branches via IF
    nodes.append(build_if_node(
        "Is Google?", "={{ $json._route === 'google' }}", [1500, 200]
    ))

    # 7. Pause Google campaign
    nodes.append(build_pause_google_node("Pause Google Campaign", [1750, 100]))

    # 8. Pause Meta campaign
    nodes.append(build_pause_meta_node("Pause Meta Campaign", [1750, 300]))

    # 9. Tag Google pause result (runOnceForEachItem — recovers paired violation)
    nodes.append(build_code_node_each(
        "Tag Google Pause Result", TAG_GOOGLE_PAUSE_CODE, [2000, 100]
    ))

    # 10. Tag Meta pause result
    nodes.append(build_code_node_each(
        "Tag Meta Pause Result", TAG_META_PAUSE_CODE, [2000, 300]
    ))

    # 11. Merge tagged results (google + meta)
    nodes.append(build_merge_node("Merge Pause Results", [2250, 200]))

    # 12. Classify via native If node (deterministic — no Code validation surprises)
    nodes.append(build_if_node(
        "Is Paused?",
        "={{ $json.api_status === 'PAUSED' }}",
        [2500, 200],
    ))

    # 13. Format paused summary (success branch)
    nodes.append(build_code_node(
        "Format Paused Summary", FORMAT_PAUSED_SUMMARY_CODE, [2750, 100]
    ))

    # 14. Format failed summary (failure branch)
    nodes.append(build_code_node(
        "Format Failed Summary", FORMAT_FAILED_SUMMARY_CODE, [2750, 300]
    ))

    # 15. Email Ian with successful-pause report
    paused_email_body = (
        "={{ '<h2>🚨 ADS Budget Enforcer — Campaigns Paused</h2>"
        "<p>The following campaigns exceeded budget caps and have been paused:</p>"
        "<pre>' + $json.summary + '</pre>"
        "<p>Run <code>python tools/analyze_ads_full.py</code> for the full picture.</p>' }}"
    )
    nodes.append(build_gmail_send(
        "Email Paused Report",
        ALERT_EMAIL,
        "=🚨 AVM Ads — Auto-paused {{ $json.count }} campaigns",
        paused_email_body,
        [3000, 100],
    ))

    # 16. Email Ian with pause-failed alert
    failed_email_body = (
        "={{ '<h2>⚠️ ADS Budget Enforcer — Pause FAILED (manual action needed)</h2>"
        "<p>The enforcer detected budget violations and attempted to pause the "
        "following campaigns, but the platform API rejected the calls. "
        "<b>Manual intervention required.</b></p>"
        "<pre>' + $json.summary + '</pre>"
        "<p>Check Google Ads / Meta OAuth credentials, then run: "
        "<code>python tools/analyze_ads_full.py</code></p>' }}"
    )
    nodes.append(build_gmail_send(
        "Email Failed Alert",
        ALERT_EMAIL,
        "=⚠️ AVM Ads — {{ $json.count }} pause attempts FAILED (manual action)",
        failed_email_body,
        [3000, 300],
    ))

    # 17. Brain Writer — log successful pause event (audit trail)
    nodes.append(build_brain_write_node(
        "Brain: Log Paused",
        [3250, 100],
        event_type_expr='="fix_applied"',
        severity_expr='="warning"',
        summary_expr='={{ "Budget Enforcer auto-paused " + $json.count + " campaign(s): " + $json.summary.replace(/\\n/g, " | ") }}',
        details_expr='={{ JSON.stringify({count: $json.count, paused: $json.paused}) }}',
    ))

    # 18. Brain Writer — log pause failure (critical)
    nodes.append(build_brain_write_node(
        "Brain: Log Failed",
        [3250, 300],
        event_type_expr='="alert"',
        severity_expr='="critical"',
        summary_expr='={{ "Budget Enforcer FAILED to pause " + $json.count + " campaign(s): " + $json.summary.replace(/\\n/g, " | ") }}',
        details_expr='={{ JSON.stringify({count: $json.count, failed: $json.failed}) }}',
    ))

    # 19. No-violation pass-through
    no_violation = {
        "id": uid(),
        "name": "No Violations",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [1250, 400],
        "parameters": {},
    }
    nodes.append(no_violation)

    return nodes


def build_ads09_connections(nodes: list[dict]) -> dict:
    return {
        "Schedule Trigger": {"main": [[
            {"node": "Read Recent Performance", "type": "main", "index": 0}
        ]]},
        "Read Recent Performance": {"main": [[
            {"node": "Compute Violations", "type": "main", "index": 0}
        ]]},
        "Compute Violations": {"main": [[
            {"node": "Has Violations?", "type": "main", "index": 0}
        ]]},
        "Has Violations?": {"main": [
            [{"node": "Route by Platform", "type": "main", "index": 0}],
            [{"node": "No Violations", "type": "main", "index": 0}],
        ]},
        "Route by Platform": {"main": [[
            {"node": "Is Google?", "type": "main", "index": 0}
        ]]},
        "Is Google?": {"main": [
            [{"node": "Pause Google Campaign", "type": "main", "index": 0}],
            [{"node": "Pause Meta Campaign", "type": "main", "index": 0}],
        ]},
        "Pause Google Campaign": {"main": [[
            {"node": "Tag Google Pause Result", "type": "main", "index": 0}
        ]]},
        "Pause Meta Campaign": {"main": [[
            {"node": "Tag Meta Pause Result", "type": "main", "index": 0}
        ]]},
        "Tag Google Pause Result": {"main": [[
            {"node": "Merge Pause Results", "type": "main", "index": 0}
        ]]},
        "Tag Meta Pause Result": {"main": [[
            {"node": "Merge Pause Results", "type": "main", "index": 1}
        ]]},
        "Merge Pause Results": {"main": [[
            {"node": "Is Paused?", "type": "main", "index": 0}
        ]]},
        "Is Paused?": {"main": [
            [{"node": "Format Paused Summary", "type": "main", "index": 0}],
            [{"node": "Format Failed Summary", "type": "main", "index": 0}],
        ]},
        "Format Paused Summary": {"main": [[
            {"node": "Email Paused Report", "type": "main", "index": 0},
            {"node": "Brain: Log Paused", "type": "main", "index": 0},
        ]]},
        "Format Failed Summary": {"main": [[
            {"node": "Email Failed Alert", "type": "main", "index": 0},
            {"node": "Brain: Log Failed", "type": "main", "index": 0},
        ]]},
    }


def build_workflow() -> dict:
    nodes = build_ads09_nodes()
    return {
        "name": WORKFLOW_NAME,
        "nodes": nodes,
        "connections": build_ads09_connections(nodes),
        "settings": {"executionOrder": "v1"},
    }


def get_client() -> N8nClient:
    return N8nClient(
        base_url=os.environ["N8N_BASE_URL"],
        api_key=os.environ["N8N_API_KEY"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "deploy", "activate", "all"])
    args = parser.parse_args()

    wf = build_workflow()

    if args.action in ("build", "all"):
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(wf, indent=2), encoding="utf-8")
        print(f"  Built {OUTPUT_PATH.relative_to(ROOT)} ({len(wf['nodes'])} nodes)")

    if args.action in ("deploy", "all"):
        client = get_client()
        # Look up existing workflow by name
        existing = [w for w in client.list_workflows(use_cache=False) if w.get("name") == WORKFLOW_NAME]
        if existing:
            wf_id = existing[0]["id"]
            client.update_workflow(wf_id, wf)
            print(f"  Updated {WORKFLOW_NAME} (id={wf_id})")
        else:
            created = client.create_workflow(wf)
            wf_id = created.get("id")
            print(f"  Created {WORKFLOW_NAME} (id={wf_id})")

    if args.action in ("activate", "all"):
        client = get_client()
        existing = [w for w in client.list_workflows(use_cache=False) if w.get("name") == WORKFLOW_NAME]
        if not existing:
            print("  ERROR: workflow not found, deploy first")
            return 1
        wf_id = existing[0]["id"]
        client.activate_workflow(wf_id)
        print(f"  Activated {WORKFLOW_NAME} (id={wf_id})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
