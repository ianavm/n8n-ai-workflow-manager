"""
Full revision fix script — 2026-03-17

Fixes 3 workflows with code/config issues that can be patched via API:

1. QA-03 Performance Benchmark (N0VEU3RHsq3OIoqR)
   - "Set Target URLs" Code node returns bare objects without {json: ...} wrapper
   - Fix: wrap return values in proper n8n format

2. INTEL-06 Regulatory Alert (sbEwotSVpnyqrQtG)
   - "Tavily Search Regulatory" JSON body uses ={{ }} expression syntax
   - n8n tries to evaluate double-braces as JS expression -> "invalid syntax"
   - Fix: convert to static JSON (no dynamic expressions needed)

3. BRAND-03 Competitor Differentiation (f3TES6QXLW5VQNHA)
   - "Tavily Search Competitors" has no API key at all (authentication: "none")
   - Fix: add Tavily API key to JSON body

Usage:
    python tools/fix_revision_2026_03_17.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient


# Tavily API key from INTEL-06's live workflow (already in n8n, not a secret leak)
TAVILY_API_KEY = "REDACTED_TAVILY_KEY"


def build_client(config):
    return N8nClient(
        base_url=config["n8n"]["base_url"],
        api_key=config["api_keys"]["n8n"],
        timeout=config["n8n"].get("timeout_seconds", 30),
        max_retries=config["n8n"].get("max_retries", 3),
    )


def deploy_workflow(client, workflow_id, wf):
    """Push patched workflow to n8n, stripping read-only fields."""
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }
    result = client.update_workflow(workflow_id, payload)
    return result


# ─────────────────────────────────────────────────────────────
# FIX 1: QA-03 Performance Benchmark
# ─────────────────────────────────────────────────────────────

def fix_qa03(client):
    """Fix QA-03 'Set Target URLs' Code node to return proper {json: ...} format."""
    wf_id = "N0VEU3RHsq3OIoqR"

    print("\n" + "=" * 60)
    print("FIX: QA-03 Performance Benchmark")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    # Fix "Set Target URLs" - must return [{json: {...}}, ...] format
    target_node = node_map.get("Set Target URLs")
    if target_node:
        old_code = target_node["parameters"].get("jsCode", "")
        # The current code returns bare objects: [{url, name}, ...]
        # n8n Code node v2 in runOnceForAllItems mode requires {json: ...} wrapper
        new_code = (
            'return [\n'
            '  {json: {"url": "https://www.anyvisionmedia.com", "name": "Landing Page"}},\n'
            '  {json: {"url": "https://portal.anyvisionmedia.com", "name": "Client Portal"}}\n'
            '];'
        )
        target_node["parameters"]["jsCode"] = new_code
        changes.append("'Set Target URLs': wrapped return values in {json: ...} format")
    else:
        print("  WARNING: 'Set Target URLs' node not found")

    # Fix "Split Targets" - now receives proper items, simplify
    split_node = node_map.get("Split Targets")
    if split_node:
        # Input is already individual items from Set Target URLs
        # Just pass through - each item already has {url, name} in $json
        new_code = (
            '// Each input item already has url and name from Set Target URLs\n'
            'return $input.all();'
        )
        split_node["parameters"]["jsCode"] = new_code
        changes.append("'Split Targets': simplified to pass-through (items already split)")
    else:
        print("  WARNING: 'Split Targets' node not found")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ─────────────────────────────────────────────────────────────
# FIX 2: INTEL-06 Regulatory Alert
# ─────────────────────────────────────────────────────────────

def fix_intel06(client):
    """Fix INTEL-06 Tavily node: remove ={{ }} expression wrapper, use static JSON."""
    wf_id = "sbEwotSVpnyqrQtG"

    print("\n" + "=" * 60)
    print("FIX: INTEL-06 Regulatory Alert")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    tavily_node = node_map.get("Tavily Search Regulatory")
    if tavily_node:
        params = tavily_node["parameters"]
        old_body = params.get("jsonBody", "")

        # The body is static (no $json refs) - convert from expression to plain JSON
        # Remove the ={{ }} wrapper and use static JSON
        new_body = json.dumps({
            "api_key": TAVILY_API_KEY,
            "query": "South Africa POPIA digital marketing regulation law change 2026",
            "search_depth": "advanced",
            "max_results": 10
        }, indent=2)

        params["jsonBody"] = new_body
        # Ensure specifyBody is set correctly
        params["specifyBody"] = "json"
        params["sendBody"] = True
        params["contentType"] = "json"

        changes.append(
            "'Tavily Search Regulatory': removed ={{ }} expression wrapper, "
            "using static JSON body with valid API key"
        )
    else:
        print("  WARNING: 'Tavily Search Regulatory' node not found")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ─────────────────────────────────────────────────────────────
# FIX 3: BRAND-03 Competitor Differentiation
# ─────────────────────────────────────────────────────────────

def fix_brand03(client):
    """Fix BRAND-03 Tavily node: add API key to the JSON body."""
    wf_id = "f3TES6QXLW5VQNHA"

    print("\n" + "=" * 60)
    print("FIX: BRAND-03 Competitor Differentiation")
    print("=" * 60)

    wf = client.get_workflow(wf_id)
    print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

    node_map = {n["name"]: n for n in wf["nodes"]}
    changes = []

    tavily_node = node_map.get("Tavily Search Competitors")
    if tavily_node:
        params = tavily_node["parameters"]
        old_body = params.get("jsonBody", "")

        # Add api_key to the existing JSON body
        # The body uses expression syntax for $json.competitors, so keep =
        new_body = (
            '={\n'
            f'  "api_key": "{TAVILY_API_KEY}",\n'
            '  "query": "{{ $json.competitors }}",\n'
            '  "search_depth": "advanced",\n'
            '  "max_results": 10,\n'
            '  "include_answer": true,\n'
            '  "include_raw_content": false\n'
            '}'
        )

        params["jsonBody"] = new_body
        changes.append(
            "'Tavily Search Competitors': added Tavily API key to JSON body"
        )
    else:
        print("  WARNING: 'Tavily Search Competitors' node not found")

    if changes:
        result = deploy_workflow(client, wf_id, wf)
        print(f"  Deployed: {result['name']} (active: {result.get('active')})")
        for c in changes:
            print(f"  - {c}")
    else:
        print("  No changes needed")

    return changes


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    config = load_config()

    print("=" * 60)
    print("FULL REVISION FIX - 2026-03-17")
    print("Fixing QA-03, INTEL-06, BRAND-03")
    print("=" * 60)

    with build_client(config) as client:
        all_changes = []

        try:
            changes = fix_qa03(client)
            all_changes.extend(changes)
        except Exception as e:
            print(f"  ERROR fixing QA-03: {e}")

        try:
            changes = fix_intel06(client)
            all_changes.extend(changes)
        except Exception as e:
            print(f"  ERROR fixing INTEL-06: {e}")

        try:
            changes = fix_brand03(client)
            all_changes.extend(changes)
        except Exception as e:
            print(f"  ERROR fixing BRAND-03: {e}")

    print("\n" + "=" * 60)
    print(f"COMPLETE - {len(all_changes)} fixes deployed")
    print("=" * 60)
    for i, c in enumerate(all_changes, 1):
        print(f"  {i}. {c}")


if __name__ == "__main__":
    main()
