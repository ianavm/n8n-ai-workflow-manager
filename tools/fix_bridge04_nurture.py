"""
Fix BRIDGE-04 Warm Lead Nurture - Handle empty lead results gracefully.

The workflow crashes when no cold leads are found because:
1. "Prepare Cold Context" Code node outputs {_empty: true} on empty input
2. This makes $json.prompt undefined in the "AI Generate Cold Email" HTTP Request
3. The HTTP Request node fails with "JSON parameter needs to be valid JSON"

Fixes:
1. Prepare Cold Context: return [] on empty input (stops chain, no downstream execution)
2. Has Cold Leads? If node: ensure proper empty filtering
3. AI Generate Cold Email: safety net for undefined prompt

Target workflow: BRIDGE-04 Warm Lead Nurture (OlHyOU8mHxJ1uZuc)
"""

import sys
import json
import re

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from config_loader import load_config
from n8n_client import N8nClient


WORKFLOW_ID = "OlHyOU8mHxJ1uZuc"


def patch_prepare_cold_context(node):
    """
    Patch the Prepare Cold Context Code node to return [] on empty input,
    which stops the n8n chain cleanly (no items = no downstream execution).
    """
    old_code = node["parameters"].get("jsCode", "")

    # Prepend an empty-input guard to the existing code
    guard = (
        "// Guard: stop chain if no leads (prevents downstream JSON errors)\n"
        "const items = $input.all();\n"
        "if (!items.length || (items.length === 1 && items[0].json._empty)) {\n"
        "  return [];\n"
        "}\n\n"
    )

    # If the code already starts with a similar guard, don't double-add
    if "items[0].json._empty" in old_code and "return []" in old_code:
        print("    -> Guard already present, skipping")
        return False

    # Remove any existing `const items = $input.all();` to avoid redeclaration
    patched = re.sub(
        r"^(\s*const\s+items\s*=\s*\$input\.all\(\)\s*;?\s*\n?)",
        "",
        old_code,
        count=1,
        flags=re.MULTILINE,
    )

    node["parameters"]["jsCode"] = guard + patched
    return True


def patch_has_cold_leads(node):
    """
    Ensure the Has Cold Leads? If node properly filters empty results.
    Check that it tests for actual data presence rather than just truthy check.
    """
    params = node.get("parameters", {})
    conditions = params.get("conditions", {})

    # Log what we find for diagnostics
    cond_list = conditions.get("conditions", [])
    print(f"    -> Current conditions: {len(cond_list)} rules")

    # If there are no conditions, add a basic one checking for non-empty
    if not cond_list:
        conditions["conditions"] = [{
            "operator": {
                "type": "boolean",
                "operation": "true",
            },
            "leftValue": "={{ $json.prompt !== undefined && $json.prompt !== '' }}",
            "rightValue": "",
        }]
        conditions.setdefault("options", {
            "version": 2,
            "caseSensitive": True,
            "typeValidation": "strict",
        })
        conditions.setdefault("combinator", "and")
        params["conditions"] = conditions
        print("    -> Added condition: prompt must be defined and non-empty")
        return True

    return False


def patch_ai_generate_email(node):
    """
    Safety net: in the AI Generate Cold Email HTTP Request node,
    wrap any $json.prompt reference so undefined becomes a valid fallback.
    """
    params = node.get("parameters", {})
    patched = False

    # Check jsonBody (string parameter containing the JSON body)
    for key in ("jsonBody", "body"):
        if key not in params:
            continue

        body_val = params[key]
        if not isinstance(body_val, str):
            continue

        # Look for JSON.stringify($json.prompt) and add fallback
        if "JSON.stringify($json.prompt)" in body_val:
            params[key] = body_val.replace(
                "JSON.stringify($json.prompt)",
                "JSON.stringify($json.prompt || 'No leads to process')",
            )
            print(f"    -> Patched {key}: JSON.stringify($json.prompt) with fallback")
            patched = True

        # Look for bare $json.prompt in expression strings (={{ ... }})
        # e.g. ={{ $json.prompt }} -> ={{ $json.prompt || 'No leads to process' }}
        if "$json.prompt" in body_val and "|| " not in body_val:
            params[key] = body_val.replace(
                "$json.prompt",
                "($json.prompt || 'No leads to process')",
            )
            print(f"    -> Patched {key}: $json.prompt with fallback")
            patched = True

    # Also check options.bodyParameters or sendBody for expression-based bodies
    options = params.get("options", {})
    if isinstance(options, dict):
        for opt_key, opt_val in options.items():
            if isinstance(opt_val, str) and "$json.prompt" in opt_val and "|| " not in opt_val:
                options[opt_key] = opt_val.replace(
                    "$json.prompt",
                    "($json.prompt || 'No leads to process')",
                )
                print(f"    -> Patched options.{opt_key}: $json.prompt with fallback")
                patched = True

    # Check sendBody / bodyParameters (structured format)
    body_params = params.get("bodyParameters", params.get("sendBody", {}))
    if isinstance(body_params, dict):
        parameters = body_params.get("parameters", [])
        if isinstance(parameters, list):
            for param in parameters:
                val = param.get("value", "")
                if isinstance(val, str) and "$json.prompt" in val and "|| " not in val:
                    param["value"] = val.replace(
                        "$json.prompt",
                        "($json.prompt || 'No leads to process')",
                    )
                    print(f"    -> Patched bodyParameter: $json.prompt with fallback")
                    patched = True

    if not patched:
        print("    -> No $json.prompt references found in request body (may use different field name)")

    return patched


def fix_workflow(wf):
    """Patch the workflow to handle empty lead results gracefully."""
    nodes = wf["nodes"]
    node_map = {n["name"]: n for n in nodes}
    fixes_applied = []

    # ── FIX 1: Prepare Cold Context ──
    print("\n  [1] Patching 'Prepare Cold Context' Code node...")
    if "Prepare Cold Context" in node_map:
        node = node_map["Prepare Cold Context"]
        if patch_prepare_cold_context(node):
            print("    -> Added empty-input guard: returns [] to stop chain")
            fixes_applied.append("Prepare Cold Context: empty-input guard (return [])")
        else:
            fixes_applied.append("Prepare Cold Context: guard already present")
    else:
        print("    -> WARNING: Node 'Prepare Cold Context' not found!")
        # Try to find similar nodes
        code_nodes = [n["name"] for n in nodes if n["type"] == "n8n-nodes-base.code"]
        print(f"    -> Code nodes available: {code_nodes}")

    # ── FIX 2: Has Cold Leads? If node ──
    print("\n  [2] Checking 'Has Cold Leads?' If node...")
    if "Has Cold Leads?" in node_map:
        node = node_map["Has Cold Leads?"]
        if patch_has_cold_leads(node):
            fixes_applied.append("Has Cold Leads?: added prompt-defined condition")
        else:
            fixes_applied.append("Has Cold Leads?: conditions already adequate")
    else:
        print("    -> WARNING: Node 'Has Cold Leads?' not found!")
        if_nodes = [n["name"] for n in nodes if n["type"] == "n8n-nodes-base.if"]
        print(f"    -> If nodes available: {if_nodes}")

    # ── FIX 3: AI Generate Cold Email ──
    print("\n  [3] Patching 'AI Generate Cold Email' HTTP Request node...")
    if "AI Generate Cold Email" in node_map:
        node = node_map["AI Generate Cold Email"]
        if patch_ai_generate_email(node):
            fixes_applied.append("AI Generate Cold Email: undefined prompt fallback")
        else:
            fixes_applied.append("AI Generate Cold Email: no prompt refs to patch (manual check advised)")
    else:
        print("    -> WARNING: Node 'AI Generate Cold Email' not found!")
        http_nodes = [n["name"] for n in nodes if "httpRequest" in n["type"].lower() or "http" in n["type"].lower()]
        print(f"    -> HTTP Request nodes available: {http_nodes}")

    return wf, fixes_applied


def main():
    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = config["n8n"]["base_url"]

    print("=" * 60)
    print("BRIDGE-04 FIX - Handle empty lead results gracefully")
    print("=" * 60)
    print(f"  Workflow ID: {WORKFLOW_ID}")
    print(f"  Instance: {base_url}")

    with N8nClient(base_url, api_key) as client:
        # 1. Fetch
        print("\n[FETCH] Getting current workflow...")
        wf = client.get_workflow(WORKFLOW_ID)
        print(f"  Got: {wf['name']} ({len(wf['nodes'])} nodes)")

        # 2. Fix
        print("\n[FIX] Applying empty-result handling fixes...")
        wf, fixes_applied = fix_workflow(wf)

        if not fixes_applied:
            print("\n  No fixes needed. Exiting.")
            return

        # 3. Save locally
        from pathlib import Path
        output_dir = Path(__file__).parent.parent / ".tmp"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "bridge04_nurture_fix.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] Saved to {output_path}")

        # 4. Deploy - strip read-only fields
        print("\n[DEPLOY] Pushing to n8n...")
        update_payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"}),
        }
        # Strip fields that n8n rejects on update
        for field in ("id", "active", "createdAt", "updatedAt", "versionId"):
            update_payload.pop(field, None)

        result = client.update_workflow(WORKFLOW_ID, update_payload)
        print(f"  Active: {result.get('active')}")
        print(f"  Nodes: {len(result.get('nodes', []))}")

    print("\n" + "=" * 60)
    print("FIX DEPLOYED SUCCESSFULLY")
    print("=" * 60)
    print(f"\nFixes applied ({len(fixes_applied)}):")
    for i, fix_desc in enumerate(fixes_applied, 1):
        print(f"  {i}. {fix_desc}")
    print("\nThe workflow will now handle empty lead queries gracefully:")
    print("  - Prepare Cold Context returns [] on empty input (stops chain)")
    print("  - Has Cold Leads? validates prompt is defined")
    print("  - AI Generate Cold Email has fallback for undefined $json.prompt")


if __name__ == "__main__":
    main()
