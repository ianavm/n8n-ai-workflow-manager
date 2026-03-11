"""
Throttle SLA Monitor (SUP-02) emails from every-15-min to once daily.

Also fixes expression mismatch: If/Gmail nodes referenced $json.summary.*
but Code node outputs at top level ($json.breached_count, etc.).

Usage:
    python tools/fix_sla_daily_email.py preview   # Show what will change
    python tools/fix_sla_daily_email.py deploy     # Patch live workflow
"""

import sys
import json

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
import httpx

WORKFLOW_ID = "EnnsJg43EazmEHJl"


def get_headers(config):
    return {
        "X-N8N-API-KEY": config["api_keys"]["n8n"],
        "Content-Type": "application/json",
    }


def fetch_workflow(config):
    url = f"{config['n8n']['base_url']}/api/v1/workflows/{WORKFLOW_ID}"
    resp = httpx.get(url, headers=get_headers(config), timeout=30)
    resp.raise_for_status()
    return resp.json()


def patch_workflow(wf):
    """Apply all patches to the workflow dict. Returns list of changes made."""
    changes = []
    node_map = {n["name"]: n for n in wf["nodes"]}

    # 1. Change schedule trigger from every 15min to once daily at 9am SAST (7am UTC)
    old_trigger_name = "Every 15min Business Hours"
    new_trigger_name = "Daily 9am SAST"

    if old_trigger_name in node_map:
        trigger = node_map[old_trigger_name]
        old_cron = trigger["parameters"]["rule"]["interval"][0]["expression"]
        new_cron = "0 7 * * 1-5"
        trigger["parameters"]["rule"]["interval"][0]["expression"] = new_cron
        trigger["name"] = new_trigger_name
        changes.append(f"Schedule: '{old_cron}' -> '{new_cron}' (once daily 9am SAST)")
        changes.append(f"Trigger renamed: '{old_trigger_name}' -> '{new_trigger_name}'")

        # Update connections that reference the old trigger name
        if old_trigger_name in wf["connections"]:
            wf["connections"][new_trigger_name] = wf["connections"].pop(old_trigger_name)
            changes.append("Connections updated for renamed trigger")

    # 2. Fix If node expressions: $json.summary.* -> $json.*
    for if_name, field in [
        ("Any SLA Breached?", "breached_count"),
        ("Any SLA Warning?", "warning_count"),
    ]:
        if if_name in node_map:
            node = node_map[if_name]
            conditions = node["parameters"]["conditions"]["conditions"]
            for cond in conditions:
                old_expr = cond.get("leftValue", "")
                if "summary." in old_expr:
                    new_expr = old_expr.replace(".summary.", ".")
                    cond["leftValue"] = new_expr
                    changes.append(f"If '{if_name}': '{old_expr}' -> '{new_expr}'")

    # 3. Fix Gmail node expressions: .json.summary.* -> .json.*
    for gmail_name in ["Alert SLA Breach", "Warn SLA Approaching"]:
        if gmail_name in node_map:
            node = node_map[gmail_name]
            for param_key in ["subject", "message"]:
                val = node["parameters"].get(param_key, "")
                if ".json.summary." in val:
                    new_val = val.replace(".json.summary.", ".json.")
                    node["parameters"][param_key] = new_val
                    changes.append(f"Gmail '{gmail_name}' {param_key}: fixed .summary. references")

    # 4. Update sticky note
    for node in wf["nodes"]:
        if node.get("type") == "n8n-nodes-base.stickyNote":
            content = node["parameters"].get("content", "")
            if "Every 15min" in content:
                node["parameters"]["content"] = content.replace(
                    "Every 15min, Mon-Fri 08:00-17:00 SAST",
                    "Once daily at 09:00 SAST, Mon-Fri"
                )
                changes.append("Sticky note updated")

    return changes


def push_workflow(config, wf):
    """PUT the patched workflow back to n8n."""
    # n8n PUT only accepts these fields
    allowed_keys = {
        "name", "nodes", "connections", "settings", "staticData",
        "pinData", "tags",
    }
    payload = {k: v for k, v in wf.items() if k in allowed_keys}
    print(f"  Payload keys: {list(payload.keys())}")
    # Also strip node-level fields n8n doesn't accept on PUT
    for node in payload.get("nodes", []):
        node.pop("continueOnFail", None)
    url = f"{config['n8n']['base_url']}/api/v1/workflows/{WORKFLOW_ID}"
    resp = httpx.put(url, headers=get_headers(config), json=payload, timeout=30)
    if resp.status_code >= 400:
        print(f"PUT error {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    return resp.json()


def activate_workflow(config):
    """POST to activate the workflow."""
    url = f"{config['n8n']['base_url']}/api/v1/workflows/{WORKFLOW_ID}/activate"
    resp = httpx.post(url, headers=get_headers(config), timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if action not in ("preview", "deploy"):
        print("Usage: python tools/fix_sla_daily_email.py [preview|deploy]")
        sys.exit(1)

    config = load_config()
    print(f"Fetching SUP-02 (ID: {WORKFLOW_ID})...")
    data = fetch_workflow(config)

    # n8n API may wrap in data or not
    wf = data if "nodes" in data else data.get("data", data)

    changes = patch_workflow(wf)

    if not changes:
        print("No changes needed - workflow already patched.")
        return

    print(f"\n{'=' * 50}")
    print(f"Changes ({len(changes)}):")
    for i, c in enumerate(changes, 1):
        print(f"  {i}. {c}")
    print(f"{'=' * 50}")

    if action == "preview":
        print("\nRun with 'deploy' to apply these changes.")
        return

    print("\nPushing patched workflow...")
    push_workflow(config, wf)
    print("Activating workflow...")
    activate_workflow(config)
    print("\nDone! SUP-02 now runs once daily at 09:00 SAST (Mon-Fri).")

    # Save updated local export
    export_path = __import__('pathlib').Path(__file__).parent.parent / "workflows" / "support-agent" / "sup02_sla_monitor.json"
    # Strip runtime fields for clean export
    export_wf = {k: v for k, v in wf.items() if k not in ("id", "versionId", "updatedAt", "createdAt", "active")}
    with open(export_path, "w") as f:
        json.dump(export_wf, f, indent=2)
    print(f"Local export updated: {export_path}")


if __name__ == "__main__":
    main()
