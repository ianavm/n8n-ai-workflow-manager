"""Collapse historical Ad_Performance hourly snapshots → 1 row per (campaign, date).

Background: ADS-04 used to write Performance ID = `{platform}_{id}_{date}_{hour}`,
producing 4 rows/day/campaign — but the metrics in each row were cumulative
(Google = lifetime, Meta = since-midnight) so summing them inflated totals 6-12x.

This script:
1. Groups all rows by (Campaign Name, Platform, Date)
2. Picks the row with the highest Snapshot Hour as the canonical end-of-day row
3. Renames its Performance ID from `..._date_hour` → `..._date` (matches new ADS-04 format)
4. Deletes the other rows in the bucket

Idempotent: re-running after the new ADS-04 lands does nothing.

Usage:
    python tools/dedupe_ads_perf_to_daily.py --dry-run
    python tools/dedupe_ads_perf_to_daily.py
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
log = logging.getLogger("dedupe_perf")

ADS_BASE = os.getenv("MARKETING_AIRTABLE_BASE_ID", "apptjjBx34z9340tK")
TBL_PERFORMANCE = os.getenv("ADS_TABLE_PERFORMANCE", "tblH1ztufqk5Kkkln")
HEADERS = {
    "Authorization": f"Bearer {os.environ['AIRTABLE_API_TOKEN']}",
    "Content-Type": "application/json",
}
URL = f"https://api.airtable.com/v0/{ADS_BASE}/{TBL_PERFORMANCE}"


def fetch_all() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = httpx.get(URL, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        d = r.json()
        records.extend(d.get("records", []))
        offset = d.get("offset")
        if not offset:
            break
    return records


def collapse(dry_run: bool) -> tuple[int, int, int]:
    records = fetch_all()
    log.info("fetched %d total Ad_Performance rows", len(records))

    # Bucket by (campaign, platform, date)
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        f = rec.get("fields", {})
        name = f.get("Campaign Name")
        platform = f.get("Platform")
        date = (f.get("Date") or "")[:10]
        if not (name and platform and date):
            continue
        buckets[(name, platform, date)].append(rec)

    to_delete: list[str] = []
    to_rename: list[tuple[str, str]] = []  # (record_id, new_perf_id)

    for (name, platform, date), group in buckets.items():
        if len(group) == 1:
            # Single row — just check the Performance ID format
            rec = group[0]
            pid = rec["fields"].get("Performance ID", "")
            new_pid = canonicalize_pid(pid, platform, date)
            if new_pid and new_pid != pid:
                to_rename.append((rec["id"], new_pid))
            continue

        # Multiple rows — pick the one with the highest Snapshot Hour
        group.sort(
            key=lambda r: (
                r["fields"].get("Snapshot Hour", "00:00"),
                r.get("createdTime", ""),
            ),
            reverse=True,
        )
        keeper = group[0]
        # Rename keeper's Performance ID to drop _hour
        keeper_pid = keeper["fields"].get("Performance ID", "")
        new_pid = canonicalize_pid(keeper_pid, platform, date)
        if new_pid and new_pid != keeper_pid:
            to_rename.append((keeper["id"], new_pid))
        # Mark the rest for deletion
        for dup in group[1:]:
            to_delete.append(dup["id"])

    log.info("plan: keep %d, delete %d, rename %d", len(buckets), len(to_delete), len(to_rename))

    if dry_run:
        for i, (rid, new_pid) in enumerate(to_rename[:5]):
            log.info("  [dry] rename %s → %s", rid, new_pid)
        for i, rid in enumerate(to_delete[:5]):
            log.info("  [dry] delete %s", rid)
        return (len(buckets), len(to_delete), len(to_rename))

    # Apply deletes (batch 10)
    deleted = 0
    for i in range(0, len(to_delete), 10):
        chunk = to_delete[i : i + 10]
        params = [("records[]", rid) for rid in chunk]
        r = httpx.delete(URL, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        deleted += len(chunk)
    log.info("deleted %d rows", deleted)

    # Apply renames (PATCH, batch 10)
    renamed = 0
    for i in range(0, len(to_rename), 10):
        chunk = to_rename[i : i + 10]
        body = {
            "records": [
                {"id": rid, "fields": {"Performance ID": new_pid}}
                for rid, new_pid in chunk
            ]
        }
        r = httpx.patch(URL, headers=HEADERS, json=body, timeout=30)
        r.raise_for_status()
        renamed += len(chunk)
    log.info("renamed %d Performance IDs", renamed)

    return (len(buckets), deleted, renamed)


def canonicalize_pid(pid: str, platform: str, date: str) -> str | None:
    """Return the new Performance ID format for this row, or None if unparseable."""
    if not pid:
        return None
    # Old format: gads_<id>_2026-04-10_04:00 or meta_<id>_2026-04-10_04:00
    # New format: gads_<id>_2026-04-10
    parts = pid.split("_")
    if len(parts) < 3:
        return None
    prefix = parts[0]
    # Date is always the second-to-last segment in old format (last is HH:MM)
    # Find date pattern YYYY-MM-DD in the parts
    for idx, p in enumerate(parts):
        if len(p) == 10 and p[4] == "-" and p[7] == "-":
            # Truncate everything after the date
            return "_".join(parts[: idx + 1])
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.dry_run:
        log.info("=== DRY RUN ===")

    try:
        kept, deleted, renamed = collapse(args.dry_run)
    except httpx.HTTPError as e:
        log.exception("HTTP error: %s", e)
        return 1

    print()
    print("━" * 60)
    print(f"Result: {kept} unique buckets | {deleted} deleted | {renamed} renamed")
    print("━" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
