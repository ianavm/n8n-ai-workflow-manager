"""
Fix $env references in live RE workflows.

Replaces $env.RE_WF_* expressions with actual workflow IDs.
n8n Cloud blocks $env access, so these must be hardcoded.

Usage:
    python tools/fix_re_env_refs_live.py [preview|apply]
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from config_loader import load_config
from n8n_client import N8nClient

# Mapping of $env variable names to actual values
ENV_REPLACEMENTS = {
    "$env.RE_WF_RE02_ID": "bJeb4zpmohTE1st4",
    "$env.RE_WF_RE03_ID": "KsWDHyXUmtxno12T",
    "$env.RE_WF_RE04_ID": "YzMyYwPZXHiBtiBL",
    "$env.RE_WF_RE10_ID": "tI5ZBhikrNLoow5C",
    "$env.RE_WF_RE15_ID": "Y3csJfc9iGhOcOoc",
    "$env.RE_WF_RE16_ID": "9TociwjnepPEUrLk",
    "$env.RE_WF_RE18_ID": "BHxuBeVNOH0ecuyI",
    "$env.RE_WF_RE19_ID": "rJbZxRVeeXIkoUJX",
    "$env.RE_GDRIVE_ROOT_FOLDER_ID": "1uADkEzkR34TVciAOko6uAcosfT3zRIo6",
    "$env.RE_GDRIVE_BUYER_PACK_FOLDER_ID": "1HCcYMvv3eg-M8x2sY5OVXDd05G3jnc2O",
    "$env.RE_GDRIVE_SELLER_PACK_FOLDER_ID": "1N_n36EhGE36UKDm8A5FNLnmr8_dt1FS7",
    "$env.RE_WHATSAPP_PHONE_ID": "956186580917374",
    "$env.N8N_API_KEY": "__USE_CREDENTIAL_INSTEAD__",
}

# Active RE workflows to fix
ACTIVE_RE_WORKFLOWS = {
    "RE-01": "jSQffhA4lVBEFa0B",
    "RE-09": "6dx07Rl1R9kyxXDH",
    "RE-11": "RMfnjJLTYJqrbNfx",
    "RE-12": "m8SCmtv4RTyay036",
    "RE-13": "QzfuUFjAKhOFfMyb",
    "RE-14": "AZHnQmu1bY9d67xG",
    "RE-17": "CsNZ0pHR28MMU00I",
}

BACKUP_DIR = Path(__file__).parent.parent / ".tmp" / "backups" / "re_env_refs"


def build_client(config: dict) -> N8nClient:
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def replace_env_in_value(value, depth=0):
    """Recursively walk a JSON-like structure, replacing $env refs in strings."""
    fixes = []
    if isinstance(value, str):
        new_val = value
        for env_ref, actual_val in ENV_REPLACEMENTS.items():
            if env_ref in new_val:
                if actual_val == "__USE_CREDENTIAL_INSTEAD__":
                    continue  # Skip N8N_API_KEY -- needs credential approach
                # Replace patterns like: ={{ $env.RE_WF_RE18_ID || '' }}
                pattern_full = "={{ " + env_ref + " || '' }}"
                if pattern_full in new_val:
                    new_val = new_val.replace(pattern_full, actual_val)
                    fixes.append(env_ref)
                # Also try without spaces
                pattern_compact = "={{" + env_ref + " || ''}}"
                if pattern_compact in new_val:
                    new_val = new_val.replace(pattern_compact, actual_val)
                    fixes.append(env_ref)
                # Raw ref (e.g., in Code node jsCode)
                if env_ref in new_val:
                    new_val = new_val.replace(env_ref, actual_val)
                    fixes.append(env_ref)
        return new_val, fixes
    elif isinstance(value, dict):
        all_fixes = []
        new_dict = {}
        for k, v in value.items():
            new_v, f = replace_env_in_value(v, depth + 1)
            new_dict[k] = new_v
            all_fixes.extend(f)
        return new_dict, all_fixes
    elif isinstance(value, list):
        all_fixes = []
        new_list = []
        for item in value:
            new_item, f = replace_env_in_value(item, depth + 1)
            new_list.append(new_item)
            all_fixes.extend(f)
        return new_list, all_fixes
    return value, []


def fix_workflow(client: N8nClient, label: str, wf_id: str, dry_run: bool) -> bool:
    """Fix $env references in a single live workflow."""
    print(f"\n  {label} ({wf_id}):")

    wf = client.get_workflow(wf_id)

    # Backup
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{label}_{wf_id}.json"
    backup.write_text(json.dumps(wf, indent=2))

    # Fix all nodes
    all_fixes = []
    new_nodes = []
    for node in wf["nodes"]:
        new_node, fixes = replace_env_in_value(node)
        new_nodes.append(new_node)
        for f in fixes:
            all_fixes.append((node.get("name", "?"), f))

    if not all_fixes:
        print("    No $env references found (clean)")
        return True

    for node_name, env_ref in all_fixes:
        print(f"    Fixed: {env_ref} in '{node_name}'")

    if dry_run:
        print(f"    [DRY RUN] Would push {len(all_fixes)} fix(es)")
        return True

    wf["nodes"] = new_nodes
    try:
        client.update_workflow(wf_id, {
            "name": wf["name"],
            "nodes": new_nodes,
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"}),
        })
        print(f"    Deployed with {len(all_fixes)} fix(es)")
        return True
    except Exception as e:
        print(f"    ERROR deploying: {e}")
        return False


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    dry_run = mode != "apply"

    if dry_run:
        print("*** PREVIEW MODE ***\n")
    else:
        print("*** APPLY MODE ***\n")

    config = load_config()
    client = build_client(config)

    results = {}
    for label, wf_id in ACTIVE_RE_WORKFLOWS.items():
        results[label] = fix_workflow(client, label, wf_id, dry_run)

    print(f"\n{'=' * 50}")
    print(f"RESULTS ({'PREVIEW' if dry_run else 'APPLIED'}):")
    for label, ok in results.items():
        print(f"  [{('OK' if ok else 'FAIL'):4s}] {label}")
    print("=" * 50)


if __name__ == "__main__":
    main()
