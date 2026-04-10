"""ADS Critical Fixes — 2026-04-10

Addresses 4 real issues identified by `tools/analyze_ads_full.py`:

1. **ADS-04 Performance Monitor** writes duplicate Ad_Performance rows
   (3.54x inflation on Campaign #1 — R53,406 reported / R15,091 real).
   Fix: switch "Write Ad Performance" from `create` → `upsert` with
   matching column "Performance ID".

2. **ADS-04 historical duplicates** in Ad_Performance table.
   Fix: dedupe by Performance ID, keep most-recent row per ID.

3. **ADS-02 Copy & Creative Generator** writes "Unknown" Campaign Name to
   Ad_Creatives + Campaign_Approvals because Parse Creatives can't recover
   the original campaign metadata after the Switch+Merge.
   Fix: walk back via `$('Read Campaign Plans').itemMatching($itemIndex)`
   in Parse Creatives, drop items that can't be matched (no "Unknown" rows).
   Also fix Create Approval Request expression to use Parse Creatives output
   directly via paired-item reference.

4. **8 stale "Unknown" approvals** in Campaign_Approvals (95h+ stale).
   Fix: delete the orphan rows.

Documents user-action items at the end (n8n credentials, Google OAuth,
conversion tracking).

Usage:
    python tools/fix_ads_critical_2026_04_10.py [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
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
log = logging.getLogger("fix_ads")

# ── Config ──────────────────────────────────────────────────────────────
N8N_BASE = os.environ["N8N_BASE_URL"].rstrip("/") + "/api/v1"
N8N_HEADERS = {
    "X-N8N-API-KEY": os.environ["N8N_API_KEY"],
    "Content-Type": "application/json",
}
AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {os.environ['AIRTABLE_API_TOKEN']}",
    "Content-Type": "application/json",
}

WF_ADS_02 = "7BBjmuvwF1l8DMQX"  # Copy & Creative Generator
WF_ADS_04 = "rIYu0FHFx741ml8d"  # Performance Monitor
ADS_BASE = "apptjjBx34z9340tK"
TBL_PERFORMANCE = "tblH1ztufqk5Kkkln"
TBL_APPROVALS = "tblov57B8uj09ZF2k"


# ── New Parse Creatives code (with paired-item lookup + drop unknowns) ──
NEW_PARSE_CREATIVES_CODE = r"""
// Parse AI creative responses and prepare for Airtable.
// Recovers Campaign Name + Platform via paired-item lookup to
// `Read Campaign Plans`. Drops items that cannot be matched
// instead of writing "Unknown" rows.
const items = $input.all();
const results = [];
const now = new Date().toISOString().split('T')[0];
let idx = 0;

for (let i = 0; i < items.length; i++) {
  const item = items[i];
  if (item.json.skip) continue;

  // Recover original campaign via paired-item reference
  let campaignName = null;
  let platform = null;
  try {
    const original = $('Read Campaign Plans').itemMatching(i);
    if (original && original.json) {
      const fields = original.json.fields || original.json;
      campaignName = fields['Campaign Name'] || null;
      platform = fields['Platform'] || null;
    }
  } catch (e) {
    // pairedItem unavailable — fall through
  }

  // Fall back to inline metadata if present
  if (!campaignName) campaignName = item.json._campaignName || null;
  if (!platform) platform = item.json._platform || 'google_ads';

  // Drop items with no recoverable campaign — prevents "Unknown" garbage rows
  if (!campaignName || campaignName === 'Unknown') continue;

  const resp = item.json;
  const content = resp.choices?.[0]?.message?.content || JSON.stringify(resp);

  let creative;
  try {
    const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    creative = JSON.parse(cleaned);
  } catch (e) {
    creative = {raw: content};
  }

  // Handle Google RSA format
  if (creative.headlines) {
    idx++;
    results.push({json: {
      'Creative Name': `${campaignName} - RSA ${now} #${idx}`,
      'Campaign Name': campaignName,
      'Platform': platform,
      'Ad Format': 'RSA',
      'Status': 'Draft',
      'Headlines': JSON.stringify(creative.headlines),
      'Descriptions': JSON.stringify(creative.descriptions || []),
      'CTA': 'Learn_More',
      'Created At': now,
    }});
  }

  // Handle Meta format with variants
  if (creative.variants) {
    for (const v of creative.variants) {
      idx++;
      results.push({json: {
        'Creative Name': `${campaignName} - Meta ${now} #${idx}`,
        'Campaign Name': campaignName,
        'Platform': platform,
        'Ad Format': 'Image',
        'Status': 'Draft',
        'Primary Text': v.primary_text || '',
        'Headlines': JSON.stringify([v.headline || '']),
        'Descriptions': JSON.stringify([v.description || '']),
        'CTA': (v.cta || 'Learn_More'),
        'Created At': now,
      }});
    }
  }

  // Handle TikTok format
  if (creative.hook && creative.script) {
    idx++;
    results.push({json: {
      'Creative Name': `${campaignName} - TikTok ${now} #${idx}`,
      'Campaign Name': campaignName,
      'Platform': platform,
      'Ad Format': 'Video',
      'Status': 'Draft',
      'Primary Text': creative.script,
      'Headlines': JSON.stringify([creative.hook]),
      'Descriptions': JSON.stringify([creative.caption || '']),
      'CTA': 'Learn_More',
      'Created At': now,
    }});
  }
}

return results.length > 0 ? results : [{json: {skip: true, reason: 'No creatives parsed'}}];
"""


def get_workflow(wf_id: str) -> dict[str, Any]:
    r = httpx.get(f"{N8N_BASE}/workflows/{wf_id}", headers=N8N_HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def update_workflow(wf_id: str, wf: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    r = httpx.put(
        f"{N8N_BASE}/workflows/{wf_id}",
        headers=N8N_HEADERS,
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


# ── FIX 1: ADS-04 → upsert ──────────────────────────────────────────────
def fix_ads04_upsert(dry_run: bool) -> bool:
    log.info("FIX 1: ADS-04 Write Ad Performance → upsert")
    wf = get_workflow(WF_ADS_04)
    node = next((n for n in wf["nodes"] if n["name"] == "Write Ad Performance"), None)
    if not node:
        log.error("  Write Ad Performance node not found")
        return False

    params = node["parameters"]
    if params.get("operation") == "upsert":
        log.info("  Already upsert — skipping")
        return True

    params["operation"] = "upsert"
    # Airtable v2.1 upsert: matchingColumns must be INSIDE parameters.columns,
    # NOT at parameters root (verified against runtime "Could not get parameter"
    # error 2026-04-10).
    params.pop("matchingColumns", None)
    params["columns"]["matchingColumns"] = ["Performance ID"]
    log.info("  Patched: operation=upsert, columns.matchingColumns=['Performance ID']")

    if dry_run:
        log.info("  [dry-run] would PUT workflow")
        return True
    update_workflow(WF_ADS_04, wf)
    log.info("  Deployed ADS-04")
    return True


# ── FIX 2: Dedupe Campaign #1 perf rows ─────────────────────────────────
def fetch_all_perf() -> list[dict[str, Any]]:
    """Fetch all Ad_Performance records."""
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = httpx.get(
            f"https://api.airtable.com/v0/{ADS_BASE}/{TBL_PERFORMANCE}",
            headers=AIRTABLE_HEADERS,
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        records.extend(d.get("records", []))
        offset = d.get("offset")
        if not offset:
            break
    return records


def dedupe_perf(dry_run: bool) -> int:
    log.info("FIX 2: Dedupe Ad_Performance by Performance ID")
    records = fetch_all_perf()
    log.info("  fetched %d total records", len(records))

    by_perf_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        pid = rec["fields"].get("Performance ID")
        if pid:
            by_perf_id[pid].append(rec)

    to_delete: list[str] = []
    for pid, group in by_perf_id.items():
        if len(group) > 1:
            # Keep most recent (latest createdTime), delete the rest
            group.sort(key=lambda r: r["createdTime"], reverse=True)
            keep = group[0]
            for dup in group[1:]:
                to_delete.append(dup["id"])
            log.debug("  %s: keeping %s, deleting %d", pid, keep["id"], len(group) - 1)

    log.info("  identified %d duplicate rows to delete", len(to_delete))
    if not to_delete:
        return 0

    if dry_run:
        log.info("  [dry-run] would delete %d rows", len(to_delete))
        return len(to_delete)

    # Airtable batch delete: 10 at a time
    deleted = 0
    for i in range(0, len(to_delete), 10):
        chunk = to_delete[i : i + 10]
        params = [("records[]", rid) for rid in chunk]
        r = httpx.delete(
            f"https://api.airtable.com/v0/{ADS_BASE}/{TBL_PERFORMANCE}",
            headers=AIRTABLE_HEADERS,
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        deleted += len(chunk)
    log.info("  deleted %d rows", deleted)
    return deleted


# ── FIX 3: ADS-02 Parse Creatives + Create Approval Request ─────────────
def fix_ads02_parse(dry_run: bool) -> bool:
    log.info("FIX 3: ADS-02 Parse Creatives + Create Approval Request")
    wf = get_workflow(WF_ADS_02)
    node_map = {n["name"]: n for n in wf["nodes"]}

    parse = node_map.get("Parse Creatives")
    if not parse:
        log.error("  Parse Creatives not found")
        return False
    parse["parameters"]["jsCode"] = NEW_PARSE_CREATIVES_CODE.lstrip("\n")
    log.info("  Patched Parse Creatives jsCode (paired-item lookup, drops unknowns)")

    approval = node_map.get("Create Approval Request")
    if approval:
        # Use paired-item reference to Parse Creatives so we get the
        # creative's Campaign Name even after the Write Creatives node.
        cols = approval["parameters"].get("columns", {}).get("value", {})
        cols["Campaign Name"] = (
            "={{ $('Parse Creatives').item.json['Campaign Name'] }}"
        )
        cols["Details"] = (
            "={{ $('Parse Creatives').item.json['Creative Name'] + ' (' + "
            "$('Parse Creatives').item.json['Platform'] + ')' }}"
        )
        approval["parameters"]["columns"]["value"] = cols
        log.info("  Patched Create Approval Request expressions")

    if dry_run:
        log.info("  [dry-run] would PUT workflow")
        return True
    update_workflow(WF_ADS_02, wf)
    log.info("  Deployed ADS-02")
    return True


# ── FIX 4: Delete stale Unknown approvals ───────────────────────────────
def cleanup_stale_approvals(dry_run: bool) -> int:
    log.info("FIX 4: Delete stale 'Unknown' approvals")
    r = httpx.get(
        f"https://api.airtable.com/v0/{ADS_BASE}/{TBL_APPROVALS}",
        headers=AIRTABLE_HEADERS,
        params={
            "filterByFormula": (
                "AND({Status}='Pending', {Campaign Name}='Unknown', {Requested By}='ADS-02')"
            ),
            "pageSize": 100,
        },
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json().get("records", [])
    log.info("  found %d stale Unknown approvals", len(rows))

    if not rows:
        return 0

    if dry_run:
        log.info("  [dry-run] would delete %d rows", len(rows))
        return len(rows)

    deleted = 0
    ids = [r["id"] for r in rows]
    for i in range(0, len(ids), 10):
        chunk = ids[i : i + 10]
        params = [("records[]", rid) for rid in chunk]
        d = httpx.delete(
            f"https://api.airtable.com/v0/{ADS_BASE}/{TBL_APPROVALS}",
            headers=AIRTABLE_HEADERS,
            params=params,
            timeout=30,
        )
        d.raise_for_status()
        deleted += len(chunk)
    log.info("  deleted %d rows", deleted)
    return deleted


# ── Main ────────────────────────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="No writes")
    args = p.parse_args()

    if args.dry_run:
        log.info("=== DRY RUN — no writes will be made ===\n")

    results: dict[str, Any] = {}
    try:
        results["fix_ads04_upsert"] = fix_ads04_upsert(args.dry_run)
        results["dedupe_perf"] = dedupe_perf(args.dry_run)
        results["fix_ads02_parse"] = fix_ads02_parse(args.dry_run)
        results["cleanup_stale_approvals"] = cleanup_stale_approvals(args.dry_run)
    except httpx.HTTPError as e:
        log.exception("HTTP error: %s", e)
        return 1

    print()
    print("━" * 60)
    print("RESULTS")
    print("━" * 60)
    for k, v in results.items():
        print(f"  {k}: {v}")

    print()
    print("━" * 60)
    print("USER ACTIONS REQUIRED (cannot be fixed by code)")
    print("━" * 60)
    print(
        """
1. Re-authorize Google Ads OAuth2 credential
   - Open n8n: https://ianimmelman89.app.n8n.cloud/credentials
   - Find credential id `abkg9bL66BFOj2F3` (Google Ads OAuth2)
   - Click 'Reconnect' / re-authenticate
   - Then activate workflow `oEZIqJ81NXOb3jix` (AVM Ads: Campaign Builder)

2. Fix Self-Healing Monitor HTTP credential
   - Find credential id `xymp9Nho08mRW2Wz` ("n8n API Header Auth")
   - The header name is currently "AVM Tutorial" (invalid HTTP token)
   - Change header name to: X-N8N-API-KEY
   - Header value: <your n8n API key from .env>
   (NOTE: recent ADS-SHM runs are succeeding, so this may already be fixed.
    Verify by checking the credential and most-recent SHM execution.)

3. Configure Google Ads conversion actions
   - Cause: 155K clicks → 0 conversions across all campaigns
   - Fix: in Google Ads UI > Tools > Conversions, create at least one
     conversion action (lead form submit, page view, etc.) and link to
     the website tag. Until this exists, ADS-04 will keep recording 0.

4. Configure Meta pixel conversion events
   - Same issue on Meta side. Confirm pixel is firing 'Lead' or 'Purchase'
     events on the landing pages.

5. Investigate "Campaign #1" in Google Ads
   - This is a real Google Ads campaign (id 23718111299) with R15K spend,
     but it's NOT in your Ad_Campaigns table — it was created outside
     the ADS-03 pipeline. Either:
     a) Add it to Ad_Campaigns (run the deploy script's sync, or add manually)
     b) Pause / rename it in Google Ads UI if it's a leftover test
"""
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
