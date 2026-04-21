"""
Swap a stale n8n credential reference across every workflow that uses it.

Use case
--------
A credential is deleted/rotated in n8n, leaving many workflows silently broken
with "Credential with ID X does not exist" at runtime. This tool scans every
workflow (active and inactive), finds nodes referencing the old credential ID,
and PUTs them back pointing at the replacement ID.

Usage
-----
    python tools/rotate_credential_ref.py --from OLD_ID --to NEW_ID --dry-run
    python tools/rotate_credential_ref.py --from OLD_ID --to NEW_ID
    python tools/rotate_credential_ref.py --from OLD_ID --to NEW_ID --active-only
    python tools/rotate_credential_ref.py --from OLD_ID --to NEW_ID --new-name "My New Cred"

The --new-name flag is optional; when omitted, keeps the existing display name
n8n stored on each node. The credential TYPE on each node is preserved.
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

# n8n Cloud API accepts only this subset of settings on PUT.
# (Any extra keys trigger "must NOT have additional properties".)
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
    return {k: raw[k] for k in PRESERVED_SETTINGS_KEYS if k in raw}


def rewrite_nodes(nodes: list[dict[str, Any]], old_id: str, new_id: str,
                  new_name: str | None) -> tuple[list[dict[str, Any]], int]:
    """Return (new_nodes, changed_count)."""
    changed = 0
    out: list[dict[str, Any]] = []
    for n in nodes:
        creds = n.get("credentials") or {}
        new_creds: dict[str, Any] = {}
        node_changed = False
        for ctype, cval in creds.items():
            if isinstance(cval, dict) and cval.get("id") == old_id:
                new_cred = dict(cval)
                new_cred["id"] = new_id
                if new_name:
                    new_cred["name"] = new_name
                new_creds[ctype] = new_cred
                node_changed = True
                changed += 1
            else:
                new_creds[ctype] = cval
        if node_changed:
            new_node = dict(n)
            new_node["credentials"] = new_creds
            out.append(new_node)
        else:
            out.append(n)
    return out, changed


def process(client: N8nClient, *, old_id: str, new_id: str,
            new_name: str | None, dry_run: bool, active_only: bool) -> int:
    workflows = client.list_workflows(active_only=False, use_cache=False)
    if active_only:
        workflows = [w for w in workflows if w.get("active")]

    print(f"\nScanning {len(workflows)} workflows for credential '{old_id}'...")

    touched: list[tuple[str, str, int, bool]] = []
    failed: list[tuple[str, str, str]] = []

    for preview in workflows:
        wf_id = preview["id"]
        name = preview.get("name", "<unnamed>")
        try:
            full = client.get_workflow(wf_id)
        except Exception as exc:  # noqa: BLE001
            failed.append((wf_id, name, f"GET failed: {exc}"))
            continue

        new_nodes, changed = rewrite_nodes(full.get("nodes", []), old_id, new_id, new_name)
        if not changed:
            continue

        touched.append((wf_id, name, changed, full.get("active", False)))

        if dry_run:
            continue

        payload = {
            "name": full.get("name", name),
            "nodes": new_nodes,
            "connections": full.get("connections", {}),
            "settings": clean_settings(full.get("settings") or {}),
        }
        try:
            client.update_workflow(wf_id, payload)
        except Exception as exc:  # noqa: BLE001
            failed.append((wf_id, name, f"PUT failed: {exc}"))

    verb = "Would update" if dry_run else "Updated"
    print(f"\n--- {verb} ---")
    for wf_id, name, cnt, active in touched:
        flag = "ACTIVE  " if active else "inactive"
        print(f"  [{flag}] {name:<50} ({wf_id})  {cnt} node(s)")

    print(f"\nTotal workflows touched: {len(touched)}")
    print(f"Total node refs rewritten: {sum(t[2] for t in touched)}")
    print(f"Failures: {len(failed)}")
    for wf_id, name, err in failed:
        print(f"  ! {name} ({wf_id}): {err}")

    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="old_id", required=True,
                        help="Credential ID to replace")
    parser.add_argument("--to", dest="new_id", required=True,
                        help="Replacement credential ID")
    parser.add_argument("--new-name", default=None,
                        help="Optional new display name for the credential")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--active-only", action="store_true")
    args = parser.parse_args()

    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env", file=sys.stderr)
        sys.exit(2)

    with N8nClient(base_url=base_url, api_key=api_key) as client:
        rc = process(client, old_id=args.old_id, new_id=args.new_id,
                     new_name=args.new_name, dry_run=args.dry_run,
                     active_only=args.active_only)
    sys.exit(rc)


if __name__ == "__main__":
    main()
