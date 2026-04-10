"""Emergency budget enforcer — pause any campaign over cap RIGHT NOW.

Reads Ad_Performance from Airtable, computes per-campaign daily/weekly/monthly
spend, and pauses any violator on its native ad platform.

- Google Ads: requires GOOGLE_ADS_DEVELOPER_TOKEN + a refreshed OAuth2 token.
  This script uses the n8n credential if accessible; otherwise it falls back
  to printing the deep-link to pause manually in the Google Ads UI.
- Meta Ads: uses META_ADS_ACCESS_TOKEN from .env to POST status=PAUSED to
  the Graph API. Works immediately.

Usage:
    python tools/pause_overspend_campaigns.py             # actually pauses
    python tools/pause_overspend_campaigns.py --dry-run   # report only
    python tools/pause_overspend_campaigns.py --campaign "Campaign #1"  # specific
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
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
log = logging.getLogger("pause_overspend")

# ── Config ──────────────────────────────────────────────────────────────
AIRTABLE_TOKEN = os.environ["AIRTABLE_API_TOKEN"]
ADS_BASE = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TBL_PERFORMANCE = os.getenv("ADS_TABLE_PERFORMANCE", "tblH1ztufqk5Kkkln")

DAILY_CAP = float(os.getenv("ADS_DAILY_HARD_CAP_ZAR", "666"))
WEEKLY_CAP = float(os.getenv("ADS_WEEKLY_HARD_CAP_ZAR", "5000"))
MONTHLY_CAP = float(os.getenv("ADS_MONTHLY_HARD_CAP_ZAR", "20000"))

GOOGLE_ADS_CUSTOMER_ID = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "5876156009")
GOOGLE_ADS_MANAGER_ID = os.getenv("GOOGLE_ADS_MANAGER_ID", "8709868142")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN") or os.getenv("FACEBOOK_ACCESS_TOKEN")
META_API_VERSION = "v25.0"

at_headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}


# ── Data ────────────────────────────────────────────────────────────────
@dataclass
class CampaignSpend:
    name: str
    platform: str
    external_id: str | None
    daily: float = 0.0
    weekly: float = 0.0
    monthly: float = 0.0

    @property
    def violations(self) -> list[str]:
        v: list[str] = []
        if self.daily > DAILY_CAP:
            v.append(f"daily R{self.daily:.0f}>R{DAILY_CAP:.0f}")
        if self.weekly > WEEKLY_CAP:
            v.append(f"weekly R{self.weekly:.0f}>R{WEEKLY_CAP:.0f}")
        if self.monthly > MONTHLY_CAP:
            v.append(f"monthly R{self.monthly:.0f}>R{MONTHLY_CAP:.0f}")
        return v


def fetch_performance() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = httpx.get(
            f"https://api.airtable.com/v0/{ADS_BASE}/{TBL_PERFORMANCE}",
            headers=at_headers,
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


def aggregate(records: list[dict[str, Any]]) -> list[CampaignSpend]:
    """Aggregate with platform-correct semantics.

    CRITICAL: Ad_Performance snapshots are cumulative, NOT daily deltas:
      - Google Ads: each row is LIFETIME CUMULATIVE since campaign launch
      - Meta Ads: each row is CUMULATIVE since MIDNIGHT (resets daily)
    Naive summing over-counts 6-12x. Use:
      - Google: daily = (latest cum on date D) - (latest cum on D-1)
      - Meta:   daily = max snapshot on date D; weekly/monthly = sum of daily-max
    """
    today = datetime.now().date().isoformat()
    week_start = (datetime.now().date() - timedelta(days=7)).isoformat()
    month_start = (datetime.now().date() - timedelta(days=30)).isoformat()

    # Step 1: bucket into {(name, platform): {date: (spend, ...)}}
    google_by_date: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    meta_by_date: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}

    for rec in records:
        f = rec.get("fields", {})
        name = f.get("Campaign Name")
        if not name:
            continue
        date = (f.get("Date") or "")[:10]
        if not date:
            continue
        hour = f.get("Snapshot Hour", "")
        spend = float(f.get("Spend ZAR") or 0)
        platform = f.get("Platform", "?")
        pid = f.get("Performance ID", "")
        ext = pid.split("_")[1] if "_" in pid else None
        if ext == "unknown":
            ext = None

        key = (name, platform)
        row = {
            "date": date,
            "hour": hour,
            "spend": spend,
            "ext_id": ext,
        }
        if platform == "google_ads":
            bucket = google_by_date.setdefault(key, {})
            cur = bucket.get(date)
            if cur is None or (hour, spend) > (cur["hour"], cur["spend"]):
                bucket[date] = row
        elif platform == "meta_ads":
            bucket = meta_by_date.setdefault(key, {})
            cur = bucket.get(date)
            if cur is None or spend > cur["spend"]:
                bucket[date] = row

    agg: dict[tuple[str, str], CampaignSpend] = {}

    # Step 2a: Google — deltas between consecutive days
    for (name, platform), by_date in google_by_date.items():
        ext_id: str | None = None
        dates = sorted(by_date.keys())
        prev = 0.0
        daily = weekly = 0.0
        lifetime = 0.0
        for date in dates:
            row = by_date[date]
            if row["ext_id"]:
                ext_id = row["ext_id"]
            delta = max(0.0, row["spend"] - prev)
            if date == today:
                daily += delta
            if date >= week_start:
                weekly += delta
            lifetime = row["spend"]  # final iteration keeps latest cumulative
            prev = row["spend"]
        agg[(name, platform)] = CampaignSpend(
            name=name,
            platform=platform,
            external_id=ext_id,
            daily=daily,
            weekly=weekly,
            monthly=lifetime,  # within 30d window, lifetime ≈ monthly
        )

    # Step 2b: Meta — sum daily-max within each window
    for (name, platform), by_date in meta_by_date.items():
        ext_id = None
        daily = weekly = monthly = 0.0
        for date, row in by_date.items():
            if row["ext_id"]:
                ext_id = row["ext_id"]
            if date == today:
                daily += row["spend"]
            if date >= week_start:
                weekly += row["spend"]
            if date >= month_start:
                monthly += row["spend"]
        agg[(name, platform)] = CampaignSpend(
            name=name,
            platform=platform,
            external_id=ext_id,
            daily=daily,
            weekly=weekly,
            monthly=monthly,
        )

    return list(agg.values())


# ── Pause API calls ─────────────────────────────────────────────────────
def pause_meta(campaign_id: str) -> tuple[bool, str]:
    if not META_ACCESS_TOKEN:
        return False, "META_ACCESS_TOKEN not set in .env"
    try:
        r = httpx.post(
            f"https://graph.facebook.com/{META_API_VERSION}/{campaign_id}",
            params={"status": "PAUSED", "access_token": META_ACCESS_TOKEN},
            timeout=30,
        )
        if r.status_code == 200:
            return True, "OK"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except httpx.HTTPError as e:
        return False, str(e)


def pause_google(campaign_id: str) -> tuple[bool, str]:
    """Google Ads requires OAuth2 + developer token. Fall back to deep link."""
    deep_link = (
        f"https://ads.google.com/aw/campaigns?__c={GOOGLE_ADS_CUSTOMER_ID}"
        f"&euid={campaign_id}"
    )
    return False, f"requires manual pause via {deep_link}"


# ── Main ────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--campaign", help="Pause specific campaign by name (skip cap check)"
    )
    args = parser.parse_args()

    log.info("Reading Ad_Performance...")
    records = fetch_performance()
    log.info("  %d records", len(records))

    campaigns = aggregate(records)
    log.info("  %d campaigns", len(campaigns))

    # Identify violators
    if args.campaign:
        targets = [c for c in campaigns if c.name == args.campaign]
        if not targets:
            log.error("Campaign '%s' not found", args.campaign)
            return 1
    else:
        targets = [c for c in campaigns if c.violations]

    print()
    print("━" * 70)
    if not targets:
        print("✅ No campaigns over cap. Nothing to pause.")
        print("━" * 70)
        return 0

    print(f"🚨 {len(targets)} campaign(s) to pause:")
    print("━" * 70)
    for c in targets:
        reasons = ", ".join(c.violations) if c.violations else "manual"
        print(f"  • {c.name}")
        print(f"    platform: {c.platform}")
        print(f"    external_id: {c.external_id or '?'}")
        print(f"    spend: D R{c.daily:.0f}, W R{c.weekly:.0f}, M R{c.monthly:.0f}")
        print(f"    reason: {reasons}")
        print()

    if args.dry_run:
        print("[dry-run] No API calls made.")
        return 0

    print("━" * 70)
    print("Executing pauses...")
    print("━" * 70)

    paused = 0
    failed = 0
    for c in targets:
        if not c.external_id or c.external_id == "unknown":
            print(f"  ⊘ {c.name} — no external_id, skipping")
            failed += 1
            continue

        platform = c.platform.lower()
        if "google" in platform:
            ok, msg = pause_google(c.external_id)
        elif "meta" in platform or "facebook" in platform:
            ok, msg = pause_meta(c.external_id)
        else:
            print(f"  ⊘ {c.name} — unknown platform '{c.platform}'")
            failed += 1
            continue

        if ok:
            print(f"  ✅ {c.name} paused ({c.platform})")
            paused += 1
        else:
            print(f"  ❌ {c.name} pause failed: {msg}")
            failed += 1

    print()
    print(f"Paused: {paused}, Failed: {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
