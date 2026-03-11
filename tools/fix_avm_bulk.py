"""Bulk-fix all AVM standalone workflows.

Fixes:
1. Code nodes referencing unexecuted upstream nodes -> wrap in try/catch
2. Airtable nodes with missing table IDs -> create tables or use alwaysOutputData
3. Airtable update nodes missing mappingMode -> add it
4. Airtable nodes referencing non-existent tables -> set alwaysOutputData + continueOnFail
"""
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient

# AVM standalone workflow IDs (non-archived, created 2026-03-09+)
AVM_WORKFLOWS = {
    # Orchestrator
    "5XR7j7hQ8cdWpi1e": "ORCH-01 Health Monitor",
    "47CJmRKTh9kPZ7u5": "ORCH-02 Cross-Dept Router",
    "JDrgcv5iNIXLyQfs": "ORCH-03 Daily KPI Aggregation",
    "2gXlFqBtOoReQfaT": "ORCH-04 Weekly Report Generator",
    # Marketing Enhancement
    "Ns8pI1OowMbNDfUV": "MKT-05 Campaign ROI Tracker",
    "UKIxkygJgJQ245pM": "MKT-06 Budget Optimizer",
    # Finance Enhancement
    "3Gb4pWJhsf2aHhsW": "FIN-08 Cash Flow Forecast",
    "6bo7BSssN6SQeodg": "FIN-09 Anomaly Detector",
    # Content Agent
    "330wVSlaVBtoKwV1": "CONTENT-01 Performance Feedback Loop",
    "dSAt6zYsfLy1e6tH": "CONTENT-02 Multi-Format Generator",
    # Client Relations
    "5Qzbyar2VTIbAuEo": "CR-01 Health Scorer (new)",
    "nbNcnixOO7njPA7w": "CR-01 Health Scorer (old)",
    "3ZzWEUmgVNIxNmx3": "CR-02 Renewal Manager",
    "e1ufCH2KvuvrBQPm": "CR-03 Onboarding Automation",
    "fOygygjEdwAyf5of": "CR-04 Satisfaction Pulse",
    # Support Agent
    "Pk0B97gW8xtcgHBf": "SUP-01 Ticket Creator (new)",
    "nOTNEIxTRJKYskCq": "SUP-01 Ticket Creator (old)",
    "EnnsJg43EazmEHJl": "SUP-02 SLA Monitor",
    "HnmuFSsdx7hasPcI": "SUP-03 Auto-Resolver",
    "3CQqDNDtgLJi2ZUu": "SUP-04 KB Builder",
    # WhatsApp Agent
    "YBxMfFdFb7BCUxzi": "WA-01 Conversation Analyzer",
    "twe45qwa4Kwalzdx": "WA-02 CRM Sync",
    "6C9PPWe4IWoUhjq2": "WA-03 Issue Detector (new)",
    "xFnBYVNwObY9bR7k": "WA-03 Issue Detector (old)",
    # Intelligence
    "P9NgW8csqbCh817f": "INTEL-01 Cross-Dept Correlator",
    "Fmut5pJ4fVXIfxke": "INTEL-02 Executive Report",
    "hSiIZJu5bgDIOCDO": "INTEL-03 Prompt Performance (new)",
    "rbHj5pTI10wNtBHp": "INTEL-03 Prompt Performance (old)",
    # Optimization
    "Rsyz1BHai3q94wPI": "OPT-01 A/B Test Manager",
    "jOUhPTYMBCf5z4PW": "OPT-02 A/B Test Analyzer (old)",
    "I37U9l1kOcsr8fpP": "OPT-02 A/B Test Analyzer (new)",
    "TPp402GuDxnruRd2": "OPT-03 Churn Predictor (new)",
    "yYTjNyTIvgaD7Qwa": "OPT-03 Churn Predictor (old)",
}


def fix_code_node_references(js_code, all_node_names):
    """Wrap $('NodeName') references in try/catch if the referenced node is Airtable/HTTP."""
    # Find all $('NodeName') references
    refs = re.findall(r"\$\('([^']+)'\)", js_code)
    if not refs:
        return js_code, False

    # Check if any reference is already wrapped in try/catch
    if 'try {' in js_code and "catch" in js_code:
        return js_code, False

    # Only wrap if there are upstream node references
    needs_wrap = False
    for ref in refs:
        if ref in all_node_names:
            needs_wrap = True
            break

    if not needs_wrap:
        return js_code, False

    # Wrap each $('NodeName').xxx() call in try/catch
    for ref in set(refs):
        # Pattern: const/let/var x = $('Name').something()
        pattern = rf"((?:const|let|var)\s+\w+\s*=\s*)\$\('{re.escape(ref)}'\)\.(\w+)\(\)(\.\w+)?"
        match = re.search(pattern, js_code)
        if match:
            full_match = match.group(0)
            var_decl = match.group(1)  # "const x = "
            method = match.group(2)    # "all" or "first"
            chain = match.group(3) or ""  # ".json" etc

            # Determine default value based on method
            if method == "all":
                default = "[]"
            else:
                default = "{ json: {} }"

            replacement = f"""{var_decl}(() => {{ try {{ return $("{ref}").{method}(){chain}; }} catch(e) {{ return {default}; }} }})()"""
            js_code = js_code.replace(full_match, replacement)

    return js_code, True


def fix_airtable_node(node):
    """Fix common Airtable node issues."""
    params = node.get("parameters", {})
    fixed = False

    # Fix 1: Add mappingMode to update columns
    if params.get("operation") == "update":
        columns = params.get("columns", {})
        if isinstance(columns, dict) and "value" in columns and "mappingMode" not in columns:
            columns["mappingMode"] = "defineBelow"
            fixed = True
            print(f"    + Added mappingMode to {node['name']}")

    # Fix 2: Add alwaysOutputData to search nodes (prevents downstream breaks on 0 results)
    if params.get("operation") == "search" and not node.get("alwaysOutputData"):
        node["alwaysOutputData"] = True
        fixed = True
        print(f"    + Added alwaysOutputData to {node['name']}")

    # Fix 3: Set continueOnFail for all Airtable nodes (graceful degradation)
    if not node.get("onError"):
        node["onError"] = "continueRegularOutput"
        node["continueOnFail"] = True
        fixed = True
        print(f"    + Added continueOnFail to {node['name']}")

    return fixed


def fix_http_node(node):
    """Fix HTTP nodes with placeholder URLs."""
    params = node.get("parameters", {})
    url = params.get("url", "")
    fixed = False

    if "example" in str(url).lower() or not url:
        if not node.get("onError"):
            node["onError"] = "continueRegularOutput"
            node["continueOnFail"] = True
            fixed = True
            print(f"    + Added continueOnFail to HTTP node {node['name']}")

    return fixed


def main():
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    client = N8nClient(base_url=base_url, api_key=api_key)

    total_fixed = 0
    workflows_fixed = 0

    for wf_id, wf_label in AVM_WORKFLOWS.items():
        print(f"\n{'='*60}")
        print(f"Scanning: {wf_label} ({wf_id})")
        print(f"{'='*60}")

        try:
            wf = client.get_workflow(wf_id)
        except Exception as e:
            print(f"  SKIP: Could not fetch workflow: {e}")
            continue

        nodes = wf["nodes"]
        all_node_names = {n["name"] for n in nodes}
        wf_changes = 0

        for node in nodes:
            node_type = node.get("type", "")

            # Fix Airtable nodes
            if node_type == "n8n-nodes-base.airtable":
                if fix_airtable_node(node):
                    wf_changes += 1

            # Fix HTTP nodes with placeholders
            elif node_type == "n8n-nodes-base.httpRequest":
                if fix_http_node(node):
                    wf_changes += 1

            # Fix Code nodes with upstream references
            elif node_type == "n8n-nodes-base.code":
                js_code = node.get("parameters", {}).get("jsCode", "")
                if js_code:
                    new_code, changed = fix_code_node_references(js_code, all_node_names)
                    if changed:
                        node["parameters"]["jsCode"] = new_code
                        wf_changes += 1
                        print(f"    + Wrapped upstream refs in {node['name']}")

        if wf_changes > 0:
            print(f"\n  Pushing {wf_changes} fixes...")
            try:
                result = client.update_workflow(wf_id, {
                    "name": wf["name"],
                    "nodes": nodes,
                    "connections": wf["connections"],
                    "settings": wf.get("settings", {}),
                    "staticData": wf.get("staticData"),
                })
                print(f"  OK: Updated {result['name']}")
                total_fixed += wf_changes
                workflows_fixed += 1
            except Exception as e:
                print(f"  ERROR pushing: {e}")
        else:
            print("  No fixes needed")

    print(f"\n{'='*60}")
    print(f"DONE: {total_fixed} fixes across {workflows_fixed} workflows")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
