"""Deactivate all 11 ADS department workflows.

Department has been degraded for weeks (Google Ads cred broken until 2026-04-15,
Meta paused for bot-traffic, SHM expressions broken). Turning the whole dept off
cleanly rather than leaving cron + webhook triggers firing into broken code.

Idempotent — safe to re-run. 404s are treated as already-deactivated and logged
as a skip rather than a failure.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from n8n_client import N8nClient  # noqa: E402
from config_loader import load_config  # noqa: E402


# All 11 ADS workflows (IDs resolved live from n8n 2026-04-17; memory IDs were stale).
ADS_WORKFLOWS: list[tuple[str, str]] = [
    ("mrzwNb9Eul9Lq2uM", "AVM Ads: Strategy Generator"),
    ("7BBjmuvwF1l8DMQX", "AVM Ads: Copy & Creative Generator"),
    ("oEZIqJ81NXOb3jix", "AVM Ads: Campaign Builder"),
    ("rIYu0FHFx741ml8d", "AVM Ads: Performance Monitor"),
    ("cfDyiFLx0X89s3VL", "AVM Ads: Optimization Engine"),
    ("bXxRU6rBC4kKw8bZ", "AVM Ads: Creative Recycler"),
    ("HkhBl7f69GckvEpY", "AVM Ads: Attribution Engine"),
    ("m8Kjjiy9jwliykOo", "AVM Ads: Reporting Dashboard"),
    ("YR6LFkWO9rnNceOp", "AVM Ads: Budget Enforcer"),
    ("5k1OKJuaAWVPf7Lb", "AVM Ads: Self-Healing Monitor"),
    ("L915QaaJuo6au7Oe", "AVM Ads: Error Handler"),
]

MANIFEST_PATH = Path(__file__).parent.parent / ".tmp" / "ads_deactivated_manifest.json"


Status = Literal["deactivated", "already_inactive", "not_found", "error"]


@dataclass(frozen=True)
class Result:
    id: str
    name: str
    status: Status
    active_before: bool | None
    active_after: bool | None
    error: str | None = None


def _fetch_active(client: N8nClient, workflow_id: str) -> bool | None:
    """Return current active state, or None if the workflow doesn't exist."""
    try:
        wf = client.get_workflow(workflow_id)
        return bool(wf.get("active"))
    except Exception:
        return None


def _deactivate_one(client: N8nClient, wf_id: str, name: str) -> Result:
    print(f"Deactivating: {name} ({wf_id})...")
    active_before = _fetch_active(client, wf_id)

    if active_before is None:
        print("  SKIP - workflow not found in n8n")
        return Result(wf_id, name, "not_found", None, None)

    if not active_before:
        print("  SKIP - already inactive")
        return Result(wf_id, name, "already_inactive", False, False)

    try:
        client.deactivate_workflow(wf_id)
        active_after = _fetch_active(client, wf_id)
        print("  OK - deactivated")
        return Result(wf_id, name, "deactivated", True, active_after)
    except Exception as exc:
        print(f"  FAILED - {exc}")
        return Result(wf_id, name, "error", active_before, active_before, str(exc))


def main() -> None:
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    if not api_key:
        print("Error: N8N_API_KEY not found in environment variables.")
        sys.exit(1)
    base_url = config["n8n"]["base_url"]

    print("=" * 60)
    print("DEACTIVATING ALL 11 ADS WORKFLOWS")
    print("=" * 60)
    print(f"Target instance: {base_url}")
    print(f"Workflows: {len(ADS_WORKFLOWS)}")
    print()

    results: list[Result] = []
    with N8nClient(base_url, api_key) as client:
        for wf_id, name in ADS_WORKFLOWS:
            results.append(_deactivate_one(client, wf_id, name))

    # Summary
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'NAME':<40} {'ID':<20} {'BEFORE':<8} {'AFTER':<8} {'STATUS'}")
    print("-" * 100)
    for r in results:
        before = "-" if r.active_before is None else str(r.active_before)
        after = "-" if r.active_after is None else str(r.active_after)
        print(f"{r.name:<40} {r.id:<20} {before:<8} {after:<8} {r.status}")
    print()
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")

    # Persist manifest for audit trail
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "created_at": datetime.now().isoformat(),
                "purpose": "ADS department full shutdown (11 workflows)",
                "results": [r.__dict__ for r in results],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nManifest saved to: {MANIFEST_PATH}")

    # Exit non-zero if any hard failure (doesn't count already_inactive / not_found)
    if by_status.get("error", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
