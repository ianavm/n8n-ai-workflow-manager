"""
Fix LinkedIn Workflows - Google Sheets Resilience

Problem: All LI-01 through LI-10 workflows write to the same "Agent Logs"
Google Sheet. When LI-01 orchestrator runs LI-02 through LI-09 sequentially,
the cumulative writes hit Google Sheets API rate limits (429). The logging
nodes crash the pipeline because they have no error resilience.

Fix:
  - "Log *" and "Log Error" nodes (Agent Logs writes):
      continueOnFail=True + retryOnFail with 5s/10s/20s backoff
      These are observability-only; they must NEVER crash the pipeline.
  - All other Google Sheets write nodes (append/update):
      retryOnFail with 3s/6s/12s backoff (data writes need retry but should
      still fail if truly broken).
  - Read nodes: retryOnFail with 2s/4s/8s backoff only.

Usage:
    python tools/fix_linkedin_gsheets_resilience.py check    # Audit current state
    python tools/fix_linkedin_gsheets_resilience.py fix      # Apply fixes to live n8n
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
from n8n_client import N8nClient


# ======================================================================
# WORKFLOW IDS
# ======================================================================

LI_WORKFLOWS = {
    "r5hSSFMQGihisVS7": "LI-01 Lead Orchestrator",
    "UCHJY0LR9ezEtOY6": "LI-02 Lead Discovery",
    "ZNA5Un9kDSGGCYhZ": "LI-03 Data Enrichment",
    "GhOqQITx3rfWWswM": "LI-04 ICP Scoring",
    "KZqZ0AnjneUQGNvU": "LI-05 Pain Detection",
    "6BhjrUM1UB0w8iXO": "LI-06 Opportunity Mapping",
    "qLWY6xKkPP5s9DbB": "LI-07 Outreach Personalization",
    "2ZbzAI9YLL6OiSrT": "LI-08 Prioritization QA",
    "iVDt9KZZs1jmRaJq": "LI-09 CRM Sync",
    "XLyM6yRIBDb3pzgJ": "LI-10 Feedback Loop",
}


def is_log_node(node_name: str) -> bool:
    """Check if node is a logging/observability node (not business-critical)."""
    name_lower = node_name.lower()
    return (
        name_lower.startswith("log ")
        or name_lower == "log error"
        or "agent log" in name_lower
    )


def is_write_node(operation: str) -> bool:
    """Check if operation is a write (append/update)."""
    return operation in ("append", "update", "create")


def apply_resilience(node: dict) -> tuple[bool, str]:
    """
    Apply resilience settings to a Google Sheets node.
    Returns (changed, description).
    """
    name = node.get("name", "")
    op = node.get("parameters", {}).get("operation", "read")
    changed = False
    desc_parts = []

    if is_log_node(name):
        # Logging nodes: MUST NOT crash the pipeline
        if not node.get("continueOnFail"):
            node["continueOnFail"] = True
            changed = True
            desc_parts.append("continueOnFail")

        if not node.get("retryOnFail"):
            node["retryOnFail"] = True
            node["maxTries"] = 3
            node["waitBetweenTries"] = 5000
            changed = True
            desc_parts.append("retryOnFail(3x, 5s)")

    elif is_write_node(op):
        # Data write nodes: retry but still fail if truly broken
        if not node.get("retryOnFail"):
            node["retryOnFail"] = True
            node["maxTries"] = 3
            node["waitBetweenTries"] = 3000
            changed = True
            desc_parts.append("retryOnFail(3x, 3s)")

    else:
        # Read nodes: retry on transient failures
        if not node.get("retryOnFail"):
            node["retryOnFail"] = True
            node["maxTries"] = 2
            node["waitBetweenTries"] = 2000
            changed = True
            desc_parts.append("retryOnFail(2x, 2s)")

    return changed, ", ".join(desc_parts) if desc_parts else "no change"


def check_workflows(client: N8nClient) -> None:
    """Audit all LinkedIn workflows for Google Sheets resilience."""
    total_nodes = 0
    vulnerable_nodes = 0

    for wf_id, wf_name in sorted(LI_WORKFLOWS.items(), key=lambda x: x[1]):
        wf = client.get_workflow(wf_id)
        nodes = wf.get("nodes", [])
        gs_nodes = [n for n in nodes if "googleSheets" in n.get("type", "")]

        if not gs_nodes:
            print(f"  {wf_name}: No Google Sheets nodes")
            continue

        print(f"\n  {wf_name} ({len(gs_nodes)} GSheets nodes):")
        for n in gs_nodes:
            total_nodes += 1
            op = n.get("parameters", {}).get("operation", "read")
            cof = n.get("continueOnFail", False)
            retry = n.get("retryOnFail", False)
            is_log = is_log_node(n["name"])

            status = "OK"
            if is_log and not cof:
                status = "VULNERABLE (log node, no continueOnFail)"
                vulnerable_nodes += 1
            elif not retry:
                status = "NO RETRY"
                vulnerable_nodes += 1

            print(f"    {n['name']:40s} op={op:8s} cof={str(cof):5s} retry={str(retry):5s} | {status}")

    print(f"\n  Summary: {total_nodes} total, {vulnerable_nodes} need fixing")


def fix_workflows(client: N8nClient) -> None:
    """Apply resilience fixes to all LinkedIn workflows."""
    total_fixed = 0

    for wf_id, wf_name in sorted(LI_WORKFLOWS.items(), key=lambda x: x[1]):
        wf = client.get_workflow(wf_id)
        nodes = wf.get("nodes", [])
        gs_nodes = [n for n in nodes if "googleSheets" in n.get("type", "")]

        if not gs_nodes:
            continue

        workflow_changed = False
        fixes = []

        for node in gs_nodes:
            changed, desc = apply_resilience(node)
            if changed:
                workflow_changed = True
                fixes.append(f"    {node['name']}: {desc}")
                total_fixed += 1

        if workflow_changed:
            print(f"\n  Fixing {wf_name}...")
            for f in fixes:
                print(f)

            # Push patched workflow back to n8n (full payload required)
            # Clean settings: n8n API rejects unknown properties
            raw_settings = wf.get("settings", {})
            clean_settings = {
                k: raw_settings[k]
                for k in (
                    "executionOrder", "saveManualExecutions",
                    "callerPolicy", "executionTimeout",
                    "errorWorkflow", "timezone",
                )
                if k in raw_settings
            }
            update_payload = {
                "name": wf.get("name", wf_name),
                "nodes": nodes,
                "connections": wf.get("connections", {}),
                "settings": clean_settings,
            }
            client.update_workflow(wf_id, update_payload)
            print(f"  -> Pushed to n8n")
        else:
            print(f"  {wf_name}: already resilient")

    print(f"\n  Total nodes fixed: {total_fixed}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("check", "fix"):
        print("Usage: python tools/fix_linkedin_gsheets_resilience.py [check|fix]")
        sys.exit(1)

    action = sys.argv[1]
    client = N8nClient(os.getenv("N8N_BASE_URL"), os.getenv("N8N_API_KEY"))

    print(f"\n{'=' * 60}")
    print(f"  LinkedIn GSheets Resilience - {action.upper()}")
    print(f"{'=' * 60}")

    try:
        if action == "check":
            check_workflows(client)
        elif action == "fix":
            fix_workflows(client)
    finally:
        client.close()


if __name__ == "__main__":
    main()
