"""
Enable MCP access on all active n8n workflows.

Background
----------
The n8n Cloud MCP server exposes workflows only when `settings.availableInMCP`
is True. Historically, many fix/deploy scripts strip this key when patching
workflows, leaving most active workflows un-inspectable via MCP.

This script iterates every active workflow, and for any that has
`availableInMCP != True`, fetches the full workflow, sets the flag, and PUTs
it back. Uses the shared N8nClient for retries/rate-limit handling.

Usage
-----
    python tools/enable_mcp_access_all_active.py --dry-run    # show what would change
    python tools/enable_mcp_access_all_active.py              # apply
    python tools/enable_mcp_access_all_active.py --check      # report status only
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from n8n_client import N8nClient  # noqa: E402

load_dotenv()

# Keys that n8n Cloud's PUBLIC REST API accepts inside settings on PUT.
# The full settings object returned by GET includes extras (binaryMode,
# executionTimeout) that the PUT schema rejects as "additional properties".
# Keep this list tight — every entry has been verified against a real PUT.
PRESERVED_SETTINGS_KEYS: tuple[str, ...] = (
    "executionOrder",
    "saveManualExecutions",
    "saveDataErrorExecution",
    "saveDataSuccessExecution",
    "saveExecutionProgress",
    "callerPolicy",
    "availableInMCP",
    "errorWorkflow",
    "timezone",
)


def clean_settings(raw: dict[str, Any]) -> dict[str, Any]:
    """Return only n8n-tolerated keys from settings."""
    return {k: raw[k] for k in PRESERVED_SETTINGS_KEYS if k in raw}


def build_update_payload(wf: dict[str, Any]) -> dict[str, Any]:
    """
    Build a minimal PUT payload that preserves structure and flips
    availableInMCP to True.
    """
    settings = clean_settings(wf.get("settings") or {})
    settings["availableInMCP"] = True
    return {
        "name": wf.get("name", ""),
        "nodes": wf.get("nodes", []),
        "connections": wf.get("connections", {}),
        "settings": settings,
    }


def process(client: N8nClient, *, dry_run: bool, check_only: bool) -> int:
    workflows = client.list_workflows(active_only=True, use_cache=False)
    active = [w for w in workflows if w.get("active")]

    print(f"\nActive workflows: {len(active)}")

    already_enabled: list[tuple[str, str]] = []
    to_enable: list[tuple[str, str]] = []
    failed: list[tuple[str, str, str]] = []

    for preview in active:
        wf_id = preview["id"]
        name = preview.get("name", "<unnamed>")

        # List API may not include the flag — fetch detail to be sure.
        try:
            full = client.get_workflow(wf_id)
        except Exception as exc:  # noqa: BLE001 — surface then continue
            failed.append((wf_id, name, f"GET failed: {exc}"))
            continue

        settings = full.get("settings") or {}
        if settings.get("availableInMCP") is True:
            already_enabled.append((wf_id, name))
            continue

        to_enable.append((wf_id, name))

        if check_only or dry_run:
            continue

        try:
            client.update_workflow(wf_id, build_update_payload(full))
        except Exception as exc:  # noqa: BLE001
            failed.append((wf_id, name, f"PUT failed: {exc}"))

    print("\n--- Summary ---")
    print(f"  Already enabled : {len(already_enabled)}")
    print(f"  Needing enable  : {len(to_enable)}")
    print(f"  Failed          : {len(failed)}")

    if to_enable:
        verb = "Would enable" if (dry_run or check_only) else "Enabled"
        print(f"\n{verb}:")
        for wf_id, name in to_enable:
            print(f"  + {name}  ({wf_id})")

    if failed:
        print("\nFailures:")
        for wf_id, name, err in failed:
            print(f"  ! {name}  ({wf_id}): {err}")

    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print changes without applying.")
    parser.add_argument("--check", action="store_true",
                        help="Report status only, never mutate.")
    args = parser.parse_args()

    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env", file=sys.stderr)
        sys.exit(2)

    with N8nClient(base_url=base_url, api_key=api_key) as client:
        rc = process(client, dry_run=args.dry_run, check_only=args.check)
    sys.exit(rc)


if __name__ == "__main__":
    main()
