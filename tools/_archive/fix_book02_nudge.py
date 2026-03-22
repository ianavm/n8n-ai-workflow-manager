"""
Fix BOOK-02 Follow-Up Nudge - Empty Airtable crash.

The workflow crashes at "Send Reminder Email" with:
    Cannot read properties of undefined (reading 'split')
because $json.contact_email is undefined when Airtable returns empty data
but the "Has Upcoming Meetings" If node still passes it through.

Execution path:
    Schedule Trigger -> Read Upcoming Bookings (1 empty item)
    -> Has Upcoming Meetings (passes empty item through)
    -> Send Reminder Email (crashes on undefined contact_email)

Fixes:
1. Set alwaysOutputData: false on Airtable read node so empty results
   produce zero output items (no downstream execution).
2. Update "Has Upcoming Meetings" If node condition to check that
   contact_email exists and is not empty (string isNotEmpty).

Usage:
    python tools/fix_book02_nudge.py
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient


WORKFLOW_ID = "yIQe9s8RVdMs91oo"

STRIP_KEYS = {
    "id", "active", "createdAt", "updatedAt", "versionId",
    "activeVersionId", "versionCounter", "triggerCount", "shared",
    "activeVersion", "isArchived", "homeProject", "usedCredentials",
    "sharedWithProjects",
}


def build_client(config):
    """Create N8nClient from config."""
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def patch_workflow(wf):
    """Apply fixes to the workflow dict. Returns list of changes made."""
    changes = []
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}

    # ── FIX 1: Airtable read node - stop passing empty items downstream ──
    airtable_name = "Read Upcoming Bookings"
    if airtable_name in node_map:
        airtable_node = node_map[airtable_name]

        # Set alwaysOutputData to false so empty results produce zero items
        if airtable_node.get("alwaysOutputData") is not False:
            airtable_node["alwaysOutputData"] = False
            changes.append(
                f"'{airtable_name}': set alwaysOutputData=false "
                "(empty results now produce zero output items)"
            )
        else:
            changes.append(f"'{airtable_name}': alwaysOutputData already false")
    else:
        print(f"  WARNING: Node '{airtable_name}' not found in workflow")

    # ── FIX 2: If node - check contact_email is not empty ──
    if_name = "Has Upcoming Meetings"
    if if_name in node_map:
        if_node = node_map[if_name]
        params = if_node.get("parameters", {})

        # Build a proper condition that checks contact_email isNotEmpty
        new_conditions = {
            "options": {
                "version": 2,
                "caseSensitive": True,
                "typeValidation": "strict",
            },
            "combinator": "and",
            "conditions": [
                {
                    "operator": {
                        "type": "string",
                        "operation": "isNotEmpty",
                    },
                    "leftValue": "={{ $json.contact_email }}",
                    "rightValue": "",
                }
            ],
        }

        old_conditions = params.get("conditions", {})
        params["conditions"] = new_conditions
        if_node["parameters"] = params

        changes.append(
            f"'{if_name}': replaced condition with contact_email isNotEmpty check"
        )

        # Log the old condition for reference
        old_conds = old_conditions.get("conditions", [])
        if old_conds:
            for cond in old_conds:
                left = cond.get("leftValue", "?")
                op = cond.get("operator", {}).get("operation", "?")
                changes.append(f"  (was: {left} {op})")
    else:
        print(f"  WARNING: Node '{if_name}' not found in workflow")

    return changes


def main():
    config = load_config()

    print("=" * 60)
    print("BOOK-02 FIX - Empty Airtable Crash Prevention")
    print("=" * 60)

    with build_client(config) as client:
        # 1. Fetch
        print(f"\n[FETCH] Getting workflow {WORKFLOW_ID}...")
        wf = client.get_workflow(WORKFLOW_ID)
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        # 2. Patch
        print("\n[PATCH] Applying fixes...")
        changes = patch_workflow(wf)

        if not changes:
            print("  No changes needed - workflow already patched.")
            return

        for i, c in enumerate(changes, 1):
            print(f"  {i}. {c}")

        # 3. Save local backup
        from pathlib import Path

        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        backup_path = output_dir / "book02_nudge_pre_fix.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[BACKUP] Saved pre-fix snapshot to {backup_path}")

        # 4. Deploy - strip runtime fields
        print("\n[DEPLOY] Pushing patched workflow to n8n...")
        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {}),
        }
        result = client.update_workflow(WORKFLOW_ID, payload)
        print(f"  Deployed: {result['name']} (ID: {result.get('id', WORKFLOW_ID)})")
        print(f"  Active: {result.get('active')}")
        print(f"  Nodes: {len(result.get('nodes', []))}")

    print("\n" + "=" * 60)
    print("FIX DEPLOYED SUCCESSFULLY")
    print("=" * 60)
    print("\nChanges made:")
    print("  1. 'Read Upcoming Bookings' Airtable node: alwaysOutputData=false")
    print("     -> Empty results no longer produce phantom items")
    print("  2. 'Has Upcoming Meetings' If node: checks contact_email isNotEmpty")
    print("     -> Only items with a real email address pass through")
    print("  3. Root cause fixed: Send Reminder Email will never receive")
    print("     undefined contact_email again")


if __name__ == "__main__":
    main()
