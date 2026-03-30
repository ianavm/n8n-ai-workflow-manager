"""
Fix FA workflow environment variable references.

n8n Cloud (non-Enterprise) doesn't support $env variables.
This script patches all FA workflows to use hardcoded values
instead of $env.* references.

Secrets (Supabase keys, API keys) are read from local .env
and injected directly into workflow node parameters.

Usage:
    python tools/fix_fa_env_vars.py preview   # Show what would change
    python tools/fix_fa_env_vars.py apply      # Apply changes to n8n Cloud
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    load_dotenv(Path(__file__).parent.parent / "client-portal" / ".env.local")
except ImportError:
    pass

from n8n_client import N8nClient


# ============================================================
# Configuration: env var name -> actual value
# ============================================================

ENV_REPLACEMENTS: dict[str, str] = {
    "SUPABASE_ANON_KEY": os.getenv(
        "SUPABASE_ANON_KEY",
        os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""),
    ),
    "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
    "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    "FA_WHATSAPP_PHONE_NUMBER_ID": os.getenv("FA_WHATSAPP_PHONE_NUMBER_ID", "PLACEHOLDER"),
    "FA_WHATSAPP_ACCESS_TOKEN": os.getenv("FA_WHATSAPP_ACCESS_TOKEN", "PLACEHOLDER"),
    "FA_TEAMS_CHAT_ID": os.getenv("FA_TEAMS_CHAT_ID", "PLACEHOLDER"),
    "FA_FIRM_NAME": os.getenv("FA_FIRM_NAME", "AnyVision Financial Advisory"),
    "PORTAL_URL": os.getenv("PORTAL_URL", "https://portal.anyvisionmedia.com"),
    "FA_COMPLIANCE_EMAIL": os.getenv("FA_COMPLIANCE_EMAIL", "ian@anyvisionmedia.com"),
}

# FA workflow IDs on n8n Cloud
FA_WORKFLOW_IDS: dict[str, str] = {
    "fa01": "0kXaGEfwAdTvSfD0",
    "fa02": "2tbs2BASV132Hq9a",
    "fa03": "g0iJU06wQMbcqHdq",
    "fa04": "9mh6mj96w8f4tmKU",
    "fa05": "t7bgW9jDMCBdG0qQ",
    "fa06": "2JqMzIOnBbnINGvL",
    "fa07a": "JjnhoxMX9R5Q0h0V",
    "fa07b": "vfHepMY5AK9Z6D3P",
    "fa08": "bmERknvAKhd4L54c",
    "fa09": "v0TfqXNNXsDvEgmh",
    "fa10": "jk8QDQyOP5VyAwGj",
}


def replace_env_refs(text: str) -> tuple[str, list[str]]:
    """Replace all {{ $env.VAR_NAME }} references with actual values.

    Returns (new_text, list_of_replacements_made).
    """
    changes: list[str] = []

    for env_name, env_value in ENV_REPLACEMENTS.items():
        # Match patterns like {{ $env.VAR_NAME }} or {{$env.VAR_NAME}}
        patterns = [
            rf"\{{\{{\s*\$env\.{env_name}\s*\}}\}}",  # {{ $env.VAR }}
            rf"\$env\.{env_name}",                       # $env.VAR (inside expressions)
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                old_text = text
                # For the full mustache pattern, replace with just the value
                text = re.sub(
                    rf"\{{\{{\s*\$env\.{env_name}\s*\}}\}}",
                    env_value,
                    text,
                )
                # For bare $env references inside larger expressions, replace with quoted value
                text = re.sub(
                    rf"\$env\.{env_name}",
                    f"'{env_value}'" if not env_value.startswith("'") else env_value,
                    text,
                )
                if text != old_text:
                    val_preview = env_value[:30] + "..." if len(env_value) > 30 else env_value
                    changes.append(f"$env.{env_name} -> {val_preview}")

    return text, changes


def process_node_params(params: dict, path: str = "") -> tuple[dict, list[str]]:
    """Recursively process all string values in node parameters."""
    all_changes: list[str] = []
    new_params = {}

    for key, value in params.items():
        current_path = f"{path}.{key}" if path else key

        if isinstance(value, str):
            new_value, changes = replace_env_refs(value)
            if changes:
                for c in changes:
                    all_changes.append(f"  {current_path}: {c}")
            new_params[key] = new_value
        elif isinstance(value, dict):
            new_value, changes = process_node_params(value, current_path)
            all_changes.extend(changes)
            new_params[key] = new_value
        elif isinstance(value, list):
            new_list = []
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    new_item, changes = process_node_params(item, f"{current_path}[{i}]")
                    all_changes.extend(changes)
                    new_list.append(new_item)
                elif isinstance(item, str):
                    new_item, changes = replace_env_refs(item)
                    if changes:
                        for c in changes:
                            all_changes.append(f"  {current_path}[{i}]: {c}")
                    new_list.append(new_item)
                else:
                    new_list.append(item)
            new_params[key] = new_list
        else:
            new_params[key] = value

    return new_params, all_changes


def _get_client() -> N8nClient | None:
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY", "")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        return None
    return N8nClient(base_url=base_url, api_key=api_key)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("preview", "apply"):
        print("Usage: python fix_fa_env_vars.py <preview|apply>")
        sys.exit(1)

    command = sys.argv[1]
    client = _get_client()
    if not client:
        sys.exit(1)

    # Check for missing values
    missing = [k for k, v in ENV_REPLACEMENTS.items() if not v or v == "PLACEHOLDER"]
    if missing:
        print(f"WARNING: These env vars are missing/placeholder: {', '.join(missing)}")
        print("  Nodes referencing them will get 'PLACEHOLDER' value.\n")

    total_changes = 0

    for wf_key, wf_id in FA_WORKFLOW_IDS.items():
        print(f"\n{'='*60}")
        print(f"[{wf_key.upper()}] Processing workflow {wf_id}")
        print(f"{'='*60}")

        wf = client.get_workflow(wf_id)
        nodes = wf.get("nodes", [])
        connections = wf.get("connections", {})
        wf_changes = 0
        patched_nodes = []

        for node in nodes:
            params = node.get("parameters", {})
            new_params, changes = process_node_params(params)

            if changes:
                wf_changes += len(changes)
                print(f"\n  Node: {node['name']} ({node['type']})")
                for c in changes:
                    print(f"    {c}")

            patched_node = {**node, "parameters": new_params}
            patched_nodes.append(patched_node)

        if wf_changes == 0:
            print("  No $env references found.")
            continue

        total_changes += wf_changes
        print(f"\n  Total changes for {wf_key}: {wf_changes}")

        if command == "apply":
            try:
                client.update_workflow(wf_id, {
                    "name": wf.get("name", ""),
                    "nodes": patched_nodes,
                    "connections": connections,
                    "settings": wf.get("settings", {}),
                })
                print(f"  APPLIED to n8n Cloud.")
            except Exception as e:
                print(f"  ERROR applying: {e}")

    print(f"\n{'='*60}")
    print(f"Total: {total_changes} env var replacements across {len(FA_WORKFLOW_IDS)} workflows.")
    if command == "preview":
        print("Run with 'apply' to push changes to n8n Cloud.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
