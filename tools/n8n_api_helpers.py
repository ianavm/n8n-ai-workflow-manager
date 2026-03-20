"""
Shared helpers for n8n fix/deploy scripts.

Provides error-safe wrappers around N8nClient operations and a standard
build_client() factory. Import these in fix_*.py scripts instead of
duplicating the pattern.

Usage:
    from n8n_api_helpers import build_client_safe, safe_get_workflow, safe_update_workflow, run_fix

    def patch_workflow(wf):
        # ... modify wf in place ...
        return ["change 1", "change 2"]

    if __name__ == "__main__":
        run_fix(
            workflow_id="abc123",
            name="BOOK-02 Fix",
            patch_fn=patch_workflow,
        )
"""

import sys
import json
from pathlib import Path
from typing import Optional, Callable, List

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient


def build_client_safe(config: Optional[dict] = None) -> Optional[N8nClient]:
    """Create N8nClient from config with error handling.

    Returns None and prints error if config is missing or connection fails.
    """
    if config is None:
        try:
            config = load_config()
        except Exception as e:
            print(f"ERROR: Failed to load config: {e}")
            return None

    try:
        return N8nClient(
            base_url=config["n8n"]["base_url"],
            api_key=config["api_keys"]["n8n"],
            timeout=config["n8n"].get("timeout_seconds", 30),
            max_retries=config["n8n"].get("max_retries", 3),
        )
    except KeyError as e:
        print(f"ERROR: Missing config key: {e}")
        print("  Check config.json has n8n.base_url and api_keys.n8n")
        return None
    except Exception as e:
        print(f"ERROR: Failed to create n8n client: {e}")
        return None


def safe_get_workflow(client: N8nClient, workflow_id: str) -> Optional[dict]:
    """Fetch workflow with error handling. Returns None on failure."""
    try:
        wf = client.get_workflow(workflow_id)
        if not wf or "nodes" not in wf:
            print(f"ERROR: Workflow {workflow_id} returned invalid data (no nodes)")
            return None
        return wf
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            print(f"ERROR: Workflow {workflow_id} not found (404)")
        elif "401" in error_msg or "403" in error_msg:
            print(f"ERROR: Authentication failed for workflow {workflow_id}")
            print("  Check N8N_API_KEY in your .env file")
        elif "ConnectError" in type(e).__name__ or "connect" in error_msg.lower():
            print(f"ERROR: Cannot reach n8n at {client.base_url}")
            print("  Is the n8n instance running?")
        else:
            print(f"ERROR: Failed to fetch workflow {workflow_id}: {e}")
        return None


def safe_update_workflow(client: N8nClient, workflow_id: str, payload: dict) -> Optional[dict]:
    """Push workflow update with error handling. Returns None on failure."""
    try:
        result = client.update_workflow(workflow_id, payload)
        return result
    except Exception as e:
        error_msg = str(e)
        if "422" in error_msg:
            print(f"ERROR: Workflow {workflow_id} rejected update (422 - validation error)")
            print(f"  Details: {error_msg}")
        elif "ConnectError" in type(e).__name__ or "connect" in error_msg.lower():
            print(f"ERROR: Cannot reach n8n at {client.base_url}")
        else:
            print(f"ERROR: Failed to update workflow {workflow_id}: {e}")
        return None


# Keys to strip from workflow before PUT (runtime-only fields)
STRIP_KEYS = {
    "id", "active", "createdAt", "updatedAt", "versionId",
    "activeVersionId", "versionCounter", "triggerCount", "shared",
    "activeVersion", "isArchived", "homeProject", "usedCredentials",
    "sharedWithProjects",
}


def make_update_payload(wf: dict) -> dict:
    """Build a clean payload for workflow update, stripping runtime fields."""
    return {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {}),
    }


def run_fix(
    workflow_id: str,
    name: str,
    patch_fn: Callable[[dict], List[str]],
    backup_prefix: Optional[str] = None,
):
    """Standard fix script runner with error handling and backup.

    Args:
        workflow_id: n8n workflow ID to patch
        name: Human-readable name for the fix (e.g., "BOOK-02 Fix")
        patch_fn: Function that takes workflow dict and returns list of change descriptions
        backup_prefix: Optional prefix for backup filename (defaults to workflow_id)
    """
    print("=" * 60)
    print(name)
    print("=" * 60)

    config = load_config()
    client = build_client_safe(config)
    if client is None:
        sys.exit(1)

    try:
        # 1. Fetch
        print(f"\n[FETCH] Getting workflow {workflow_id}...")
        wf = safe_get_workflow(client, workflow_id)
        if wf is None:
            sys.exit(1)
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        # 2. Patch
        print("\n[PATCH] Applying fixes...")
        changes = patch_fn(wf)

        if not changes:
            print("  No changes needed - workflow already patched.")
            return

        for i, c in enumerate(changes, 1):
            print(f"  {i}. {c}")

        # 3. Backup
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        prefix = backup_prefix or workflow_id
        backup_path = output_dir / f"{prefix}_pre_fix.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[BACKUP] Saved to {backup_path}")

        # 4. Deploy
        print("\n[DEPLOY] Pushing patched workflow to n8n...")
        payload = make_update_payload(wf)
        result = safe_update_workflow(client, workflow_id, payload)
        if result is None:
            print("  FAILED - workflow NOT updated. Check errors above.")
            sys.exit(1)

        print(f"  Deployed: {result['name']} (ID: {result.get('id', workflow_id)})")
        print(f"  Active: {result.get('active')}")
        print(f"  Nodes: {len(result.get('nodes', []))}")

        print("\n" + "=" * 60)
        print("FIX DEPLOYED SUCCESSFULLY")
        print("=" * 60)

    finally:
        client.close()
