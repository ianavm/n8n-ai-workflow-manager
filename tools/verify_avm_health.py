"""Verify health of all AVM standalone workflows.

Checks:
1. Code nodes: typeVersion set, jsCode present, no orphaned Airtable creds
2. Airtable nodes: mappingMode on updates, alwaysOutputData on searches, continueOnFail
3. Code nodes: upstream $('NodeName') refs wrapped in try/catch
4. HTTP nodes: placeholder URLs have continueOnFail
5. All node connections valid (no dangling references)
"""
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from n8n_client import N8nClient

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
    # Overview
    "Zp1gCxlgYtXA9lJO": "AVM Overview (275 nodes)",
}

# Known Airtable tables that exist
KNOWN_TABLES = {
    # WhatsApp base (appzcZpiIZ6QPtJXT)
    "tblHCkr9weKQAHZoB", "tbl72lkYHRbZHIK4u", "tbluSD0m6zIAVmsGm",
    "tblM6CJi7pyWQWmeD", "tbludJQgwxtvcyo2Q", "tblUFcG2FXrc0gsAj",
    "tblcfbzWkQBg8371Y", "tblXBHOpJbxozBCRK", "tbluQzwLUNtrVsBXR",
    "tblU9LBeWnX9aiJEs", "tblztAJJPs2DHAB2J", "tblZgUhYagCaoUUww",
    # Marketing base (apptjjBx34z9340tK) - assume all exist
    # Lead scraper base (app2ALQUP7CKEkHOz) - assume all exist
}


def check_workflow(client, wf_id, wf_label):
    """Check a single workflow for issues. Returns list of issues."""
    issues = []

    try:
        wf = client.get_workflow(wf_id)
    except Exception as e:
        return [f"FETCH FAILED: {e}"]

    nodes = wf["nodes"]
    connections = wf.get("connections", {})
    node_names = {n["name"] for n in nodes}

    for node in nodes:
        name = node["name"]
        ntype = node.get("type", "")
        params = node.get("parameters", {})

        # Skip sticky notes and triggers
        if ntype in ("n8n-nodes-base.stickyNote", "n8n-nodes-base.manualTrigger"):
            continue

        # === Code node checks ===
        if ntype == "n8n-nodes-base.code":
            # Check typeVersion
            tv = node.get("typeVersion")
            if not tv:
                issues.append(f"CODE_NO_VERSION: {name} (typeVersion missing)")

            # Check jsCode exists
            js = params.get("jsCode", "")
            if not js:
                issues.append(f"CODE_EMPTY: {name} (no jsCode)")

            # Check orphaned Airtable credentials
            creds = node.get("credentials", {})
            if "airtableTokenApi" in creds or "airtableOAuth2Api" in creds:
                issues.append(f"CODE_ORPHAN_CREDS: {name} (has Airtable creds on Code node)")

            # Check upstream references without try/catch
            if js:
                refs = re.findall(r"\$\('([^']+)'\)", js)
                for ref in refs:
                    if ref in node_names:
                        # Check if ref is to an Airtable/HTTP node
                        ref_node = next((n for n in nodes if n["name"] == ref), None)
                        if ref_node and ref_node.get("type") in ("n8n-nodes-base.airtable", "n8n-nodes-base.httpRequest"):
                            # Check if wrapped in try/catch
                            if "try" not in js and "catch" not in js:
                                issues.append(f"CODE_UNWRAPPED_REF: {name} -> $'{ref}' (Airtable/HTTP ref not in try/catch)")

        # === Airtable node checks ===
        elif ntype == "n8n-nodes-base.airtable":
            op = params.get("operation", "")

            # Check update nodes have mappingMode
            if op == "update":
                columns = params.get("columns", {})
                if isinstance(columns, dict) and "value" in columns:
                    if "mappingMode" not in columns:
                        issues.append(f"AT_NO_MAPPING_MODE: {name} (update missing mappingMode)")

            # Check search nodes have alwaysOutputData
            if op == "search" and not node.get("alwaysOutputData"):
                issues.append(f"AT_NO_ALWAYS_OUTPUT: {name} (search missing alwaysOutputData)")

            # Check continueOnFail
            if not node.get("continueOnFail") and not node.get("onError"):
                issues.append(f"AT_NO_CONTINUE: {name} (no continueOnFail)")

            # Check table exists (only for WhatsApp base where we have full list)
            table = params.get("table", {})
            if isinstance(table, dict):
                table_id = table.get("value", "")
                base = params.get("base", {})
                base_id = base.get("value", "") if isinstance(base, dict) else ""
                if base_id == "appzcZpiIZ6QPtJXT" and table_id and table_id not in KNOWN_TABLES:
                    if not node.get("continueOnFail") and not node.get("onError"):
                        issues.append(f"AT_MISSING_TABLE: {name} (table {table_id} not found, no fallback)")

        # === HTTP node checks ===
        elif ntype == "n8n-nodes-base.httpRequest":
            url = str(params.get("url", ""))
            if "example" in url.lower() or not url:
                if not node.get("continueOnFail") and not node.get("onError"):
                    issues.append(f"HTTP_PLACEHOLDER: {name} (placeholder URL, no fallback)")

        # === Gmail node checks ===
        elif ntype == "n8n-nodes-base.gmail":
            creds = node.get("credentials", {})
            if not creds.get("gmailOAuth2"):
                issues.append(f"GMAIL_NO_CREDS: {name} (no Gmail OAuth2 credential)")

    # === Connection checks ===
    for source_name, conns in connections.items():
        if source_name not in node_names:
            issues.append(f"CONN_DANGLING_SOURCE: Connection from '{source_name}' (node doesn't exist)")
        if isinstance(conns, dict):
            for conn_type, outputs in conns.items():
                if isinstance(outputs, list):
                    for output in outputs:
                        if isinstance(output, list):
                            for target in output:
                                target_name = target.get("node", "")
                                if target_name and target_name not in node_names:
                                    issues.append(f"CONN_DANGLING_TARGET: '{source_name}' -> '{target_name}' (target doesn't exist)")

    return issues


def main():
    base_url = os.getenv("N8N_BASE_URL", "https://ianimmelman89.app.n8n.cloud")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set in .env")
        sys.exit(1)
    client = N8nClient(base_url=base_url, api_key=api_key)

    total_issues = 0
    clean_count = 0
    issue_workflows = []

    for wf_id, wf_label in AVM_WORKFLOWS.items():
        issues = check_workflow(client, wf_id, wf_label)

        if issues:
            print(f"\n  ISSUES in {wf_label} ({wf_id}):")
            for issue in issues:
                print(f"    - {issue}")
            total_issues += len(issues)
            issue_workflows.append((wf_label, issues))
        else:
            print(f"  OK: {wf_label}")
            clean_count += 1

    print(f"\n{'='*60}")
    print(f"SUMMARY: {clean_count} clean, {len(issue_workflows)} with issues, {total_issues} total issues")
    print(f"{'='*60}")

    if issue_workflows:
        print("\nWorkflows needing attention:")
        for label, issues in issue_workflows:
            print(f"  {label}: {len(issues)} issues")


if __name__ == "__main__":
    main()
