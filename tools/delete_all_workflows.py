"""
Delete ALL workflows from n8n Cloud.
Used for full reset / starting from scratch.

Usage:
    python tools/delete_all_workflows.py --dry-run    # preview
    python tools/delete_all_workflows.py               # execute
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient
from config_loader import load_config

MANIFEST_PATH = Path(__file__).parent.parent / ".tmp" / "delete_all_2026_03_28_manifest.json"

DRY_RUN = "--dry-run" in sys.argv


def main() -> None:
    config = load_config()
    client = N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )

    print("=" * 60)
    print("DELETE ALL WORKFLOWS -- Full Reset")
    if DRY_RUN:
        print("*** DRY RUN ***")
    print("=" * 60)

    # Fetch all workflows
    all_wf = client.list_workflows(use_cache=False)
    print(f"\n  Total workflows to delete: {len(all_wf)}")

    # Deactivate active ones first
    active = [w for w in all_wf if w.get("active")]
    if active:
        print(f"\n  Deactivating {len(active)} active workflows first...")
        for wf in active:
            if not DRY_RUN:
                try:
                    client.deactivate_workflow(wf["id"])
                except Exception as e:
                    print(f"    ERR deactivating {wf.get('name')}: {e}")
            else:
                print(f"    [DRY] Would deactivate: {wf.get('name')}")

    # Save manifest before deletion
    manifest = {
        "created_at": datetime.now().isoformat(),
        "purpose": "Full reset -- delete all workflows to start from scratch",
        "total": len(all_wf),
        "workflows": [
            {
                "id": w["id"],
                "name": w.get("name", "Unknown"),
                "active": w.get("active", False),
                "nodeCount": w.get("nodeCount", 0),
                "tags": [t.get("name", "") for t in w.get("tags", [])],
            }
            for w in all_wf
        ],
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\n  Manifest saved: {MANIFEST_PATH}")

    # Delete all
    deleted = 0
    errors = 0
    for wf in all_wf:
        wf_id = wf["id"]
        name = wf.get("name", "Unknown")
        if DRY_RUN:
            print(f"  [DRY] Would delete: {name} ({wf_id})")
            deleted += 1
            continue

        try:
            client.delete_workflow(wf_id)
            deleted += 1
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                deleted += 1  # already gone
            else:
                errors += 1
                print(f"  ERR  {name}: {e}")

    print(f"\n{'=' * 60}")
    print(f"  Deleted: {deleted}")
    print(f"  Errors: {errors}")
    print(f"  n8n Cloud is now empty.")
    print(f"  Local JSON exports in workflows/ are preserved.")
    print(f"{'=' * 60}")

    client.close()


if __name__ == "__main__":
    main()
