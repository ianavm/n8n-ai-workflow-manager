"""Emergency kill-switch — pause EVERY campaign on the Meta ad account.

Sources the campaign list from Meta Graph API directly (not from Airtable)
so no campaign can be missed because it failed to log insights. Reusable
whenever spend needs to be stopped immediately.

Usage:
    python tools/pause_all_meta_campaigns.py --dry-run   # list only, no writes
    python tools/pause_all_meta_campaigns.py             # prompts for confirmation
    python tools/pause_all_meta_campaigns.py --yes       # skips the prompt
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

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
log = logging.getLogger("pause_all_meta")

META_API_VERSION = "v25.0"
GRAPH = f"https://graph.facebook.com/{META_API_VERSION}"

ACCESS_TOKEN = (
    os.getenv("META_ACCESS_TOKEN")
    or os.getenv("META_ADS_ACCESS_TOKEN")
    or os.getenv("FACEBOOK_ACCESS_TOKEN")
)
ACCOUNT_ID = os.getenv("META_ADS_ACCOUNT_ID") or os.getenv("META_ACCOUNT_ID")

INACTIVE_STATUSES = frozenset({"PAUSED", "DELETED", "ARCHIVED"})


@dataclass(frozen=True)
class Campaign:
    id: str
    name: str
    status: str
    effective_status: str
    daily_budget_zar: float  # already converted from cents
    lifetime_budget_zar: float


def _require_env() -> None:
    missing: list[str] = []
    if not ACCESS_TOKEN:
        missing.append("META_ACCESS_TOKEN (or META_ADS_ACCESS_TOKEN / FACEBOOK_ACCESS_TOKEN)")
    if not ACCOUNT_ID:
        missing.append("META_ADS_ACCOUNT_ID")
    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(2)
    if ACCOUNT_ID and not ACCOUNT_ID.startswith("act_"):
        log.error("META_ADS_ACCOUNT_ID must start with 'act_' (got %r)", ACCOUNT_ID)
        sys.exit(2)


def _to_zar(minor_units: str | int | None) -> float:
    """Meta returns budgets in the account currency's minor unit (cents for ZAR)."""
    if minor_units is None or minor_units == "":
        return 0.0
    try:
        return float(minor_units) / 100.0
    except (TypeError, ValueError):
        return 0.0


def list_all_campaigns() -> list[Campaign]:
    """Fetch every campaign on the ad account, following paging.next."""
    url: str | None = f"{GRAPH}/{ACCOUNT_ID}/campaigns"
    params: dict[str, str | int] | None = {
        "fields": "id,name,status,effective_status,daily_budget,lifetime_budget",
        "limit": 200,
        "access_token": ACCESS_TOKEN or "",
    }
    results: list[Campaign] = []
    page = 0
    while url:
        page += 1
        r = httpx.get(url, params=params, timeout=30)
        if r.status_code != 200:
            log.error("Graph API error on page %d: HTTP %d: %s", page, r.status_code, r.text[:300])
            sys.exit(3)
        body = r.json()
        for item in body.get("data", []):
            results.append(
                Campaign(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    status=str(item.get("status", "")),
                    effective_status=str(item.get("effective_status", "")),
                    daily_budget_zar=_to_zar(item.get("daily_budget")),
                    lifetime_budget_zar=_to_zar(item.get("lifetime_budget")),
                )
            )
        next_url = body.get("paging", {}).get("next")
        url = next_url
        params = None  # the next-URL already contains params
    return results


def pause_campaign(campaign_id: str) -> tuple[bool, str]:
    """POST status=PAUSED to a single campaign. Mirrors tools/pause_overspend_campaigns.py:216."""
    try:
        r = httpx.post(
            f"{GRAPH}/{campaign_id}",
            params={"status": "PAUSED", "access_token": ACCESS_TOKEN or ""},
            timeout=30,
        )
        if r.status_code == 200:
            return True, "OK"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except httpx.HTTPError as e:
        return False, str(e)


def _print_campaign_table(campaigns: list[Campaign], title: str) -> None:
    print()
    print("━" * 78)
    print(f"{title}  ({len(campaigns)} campaign(s))")
    print("━" * 78)
    if not campaigns:
        print("  (none)")
        return
    for c in campaigns:
        budget_bits: list[str] = []
        if c.daily_budget_zar:
            budget_bits.append(f"daily R{c.daily_budget_zar:,.0f}")
        if c.lifetime_budget_zar:
            budget_bits.append(f"lifetime R{c.lifetime_budget_zar:,.0f}")
        budget_str = ", ".join(budget_bits) or "no campaign-level budget"
        print(f"  • [{c.status:<10}] {c.name}")
        print(f"      id={c.id}  effective={c.effective_status}  {budget_str}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List only, no pause calls")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    _require_env()

    log.info("Listing campaigns on %s ...", ACCOUNT_ID)
    all_campaigns = list_all_campaigns()
    log.info("  fetched %d total campaigns", len(all_campaigns))

    targets = [c for c in all_campaigns if c.status not in INACTIVE_STATUSES]
    already_off = [c for c in all_campaigns if c.status in INACTIVE_STATUSES]

    _print_campaign_table(already_off, "Already inactive (no action)")
    _print_campaign_table(targets, "WILL BE PAUSED")

    total_daily = sum(c.daily_budget_zar for c in targets)
    total_lifetime = sum(c.lifetime_budget_zar for c in targets)
    print()
    print("━" * 78)
    print(f"Total daily budget to be taken offline:    R{total_daily:,.0f}")
    print(f"Total lifetime budget across targets:      R{total_lifetime:,.0f}")
    print("━" * 78)

    if not targets:
        print("✅ Nothing to pause — every campaign is already off.")
        return 0

    if args.dry_run:
        print("[dry-run] No API writes made.")
        return 0

    if not args.yes:
        print()
        answer = input(f"Pause {len(targets)} campaign(s)? Type 'PAUSE' to confirm: ").strip()
        if answer != "PAUSE":
            print("Aborted — nothing paused.")
            return 1

    print()
    print("━" * 78)
    print("Executing pauses ...")
    print("━" * 78)

    paused = 0
    failed: list[tuple[Campaign, str]] = []
    for c in targets:
        ok, msg = pause_campaign(c.id)
        if ok:
            print(f"  ✅ {c.name}  ({c.id})")
            paused += 1
        else:
            print(f"  ❌ {c.name}  ({c.id}) — {msg}")
            failed.append((c, msg))

    print()
    print(f"Paused: {paused}   Failed: {len(failed)}")

    # Verify: re-list and assert nothing is still ACTIVE.
    print()
    log.info("Verifying — re-listing campaigns ...")
    after = list_all_campaigns()
    still_active = [c for c in after if c.status not in INACTIVE_STATUSES]
    if still_active:
        print()
        print("⚠️  Some campaigns are still active after pause:")
        for c in still_active:
            print(f"    • [{c.status}] {c.name}  ({c.id})")
        return 2

    print("✅ Verification passed — 0 active campaigns remaining on account.")
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
