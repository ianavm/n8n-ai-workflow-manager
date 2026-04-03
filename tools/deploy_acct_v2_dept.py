"""
Plug-and-Play Accounting Module — Master Deploy Orchestrator

Builds, deploys, and activates all 10 accounting workflow modules.
Each module is a separate deploy script that can also run standalone.

Usage:
    python tools/deploy_acct_v2_dept.py build                    # Build all workflow JSONs
    python tools/deploy_acct_v2_dept.py build wf02               # Build specific workflow
    python tools/deploy_acct_v2_dept.py deploy                   # Deploy all to n8n
    python tools/deploy_acct_v2_dept.py activate                 # Deploy + activate all
    python tools/deploy_acct_v2_dept.py activate wf04 wf05       # Activate specific workflows
    python tools/deploy_acct_v2_dept.py status                   # Show deployment status

Deployment Order (recommended activation sequence):
    Phase 1 (monitoring): wf10 (exceptions), wf09 (reporting)
    Phase 2 (core):       wf01 (master data), wf02 (invoicing), wf03 (sending)
    Phase 3 (AP):         wf06 (bill intake), wf07 (supplier payments)
    Phase 4 (AR):         wf04 (collections), wf05 (payments)
    Phase 5 (approvals):  wf08 (approval engine)
"""

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))


# ============================================================
# Workflow Registry
# ============================================================

WORKFLOW_REGISTRY: dict[str, dict[str, Any]] = {
    "wf01": {
        "module": "deploy_acct_v2_wf01",
        "name": "ACCT-01 Customer & Supplier Master Data",
        "filename": "wf01_master_data.json",
        "phase": 2,
        "description": "Customer/supplier CRUD, dedup, accounting software sync",
    },
    "wf02": {
        "module": "deploy_acct_v2_wf02",
        "name": "ACCT-02 Invoice Creation Engine",
        "filename": "wf02_invoice_creation.json",
        "phase": 2,
        "description": "Invoice creation, VAT calc, approval routing, accounting sync",
    },
    "wf03": {
        "module": "deploy_acct_v2_wf03",
        "name": "ACCT-03 Invoice Sending & Notifications",
        "filename": "wf03_invoice_sending.json",
        "phase": 2,
        "description": "Email/WhatsApp delivery, reminder scheduling",
    },
    "wf04": {
        "module": "deploy_acct_v2_wf04",
        "name": "ACCT-04 Collections & Follow-ups",
        "filename": "wf04_collections.json",
        "phase": 4,
        "description": "Overdue detection, tiered reminders, POP handling, escalation",
    },
    "wf05": {
        "module": "deploy_acct_v2_wf05",
        "name": "ACCT-05 Payment Capture & Reconciliation",
        "filename": "wf05_payments.json",
        "phase": 4,
        "description": "Gateway webhooks, AI fuzzy matching, receipt generation",
    },
    "wf06": {
        "module": "deploy_acct_v2_wf06",
        "name": "ACCT-06 Supplier Bill Intake",
        "filename": "wf06_bill_intake.json",
        "phase": 3,
        "description": "Email/upload intake, OCR extraction, auto-approve logic",
    },
    "wf07": {
        "module": "deploy_acct_v2_wf07",
        "name": "ACCT-07 Supplier Payments",
        "filename": "wf07_supplier_payments.json",
        "phase": 3,
        "description": "Payment batching, remittance advice, accounting sync",
    },
    "wf08": {
        "module": "deploy_acct_v2_wf08",
        "name": "ACCT-08 Approval Engine",
        "filename": "wf08_approvals.json",
        "phase": 5,
        "description": "Email/portal approval handler, entity status updates",
    },
    "wf09": {
        "module": "deploy_acct_v2_wf09",
        "name": "ACCT-09 Reporting & Month-End",
        "filename": "wf09_reporting.json",
        "phase": 1,
        "description": "Aged receivables/payables, cashflow, AI management pack",
    },
    "wf10": {
        "module": "deploy_acct_v2_wf10",
        "name": "ACCT-10 Exception Management",
        "filename": "wf10_exceptions.json",
        "phase": 1,
        "description": "Overdue task escalation, failed workflow retry, alerts",
    },
}

OUTPUT_DIR = Path(__file__).parent.parent / "workflows" / "accounting-v2"


def build_workflow(wf_id: str) -> dict[str, Any]:
    """Import and build a workflow from its deploy module."""
    entry = WORKFLOW_REGISTRY[wf_id]
    mod = importlib.import_module(entry["module"])
    nodes = mod.build_nodes()
    connections = mod.build_connections()

    from acct_helpers import build_workflow_json

    return build_workflow_json(entry["name"], nodes, connections)


def save_workflow(wf_id: str, workflow: dict[str, Any]) -> Path:
    """Save workflow JSON to the output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = WORKFLOW_REGISTRY[wf_id]["filename"]
    output_path = OUTPUT_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_stats(wf_id: str, workflow: dict[str, Any]) -> None:
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])
    entry = WORKFLOW_REGISTRY[wf_id]

    print(f"  {wf_id}: {entry['name']}")
    print(f"    Nodes: {len(func_nodes)} | Connections: {conn_count}")
    print(f"    Phase: {entry['phase']} | {entry['description']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plug-and-Play Accounting — Master Deploy Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/deploy_acct_v2_dept.py build              Build all 10 workflows
  python tools/deploy_acct_v2_dept.py build wf02 wf03    Build specific workflows
  python tools/deploy_acct_v2_dept.py deploy              Deploy all to n8n
  python tools/deploy_acct_v2_dept.py activate wf09 wf10  Activate monitoring first
  python tools/deploy_acct_v2_dept.py status              Show n8n deployment status
        """,
    )
    parser.add_argument(
        "action",
        choices=["build", "deploy", "activate", "status"],
        help="Action to perform",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=[],
        help="Specific workflow IDs (e.g., wf01 wf02). Omit for all.",
    )
    parsed = parser.parse_args()

    # Determine targets
    valid_ids = list(WORKFLOW_REGISTRY.keys())
    if parsed.targets:
        for t in parsed.targets:
            if t not in valid_ids:
                print(f"ERROR: Unknown workflow '{t}'. Valid: {', '.join(valid_ids)}")
                sys.exit(1)
        targets = parsed.targets
    else:
        targets = valid_ids

    print("=" * 60)
    print("PLUG-AND-PLAY ACCOUNTING — MASTER ORCHESTRATOR")
    print("=" * 60)
    print(f"Action: {parsed.action}")
    print(f"Targets: {', '.join(targets)} ({len(targets)} workflows)")
    print()

    if parsed.action == "status":
        _show_status()
        return

    # Build all targeted workflows
    workflows: dict[str, dict[str, Any]] = {}
    total_nodes = 0

    for wf_id in targets:
        try:
            workflow = build_workflow(wf_id)
            output_path = save_workflow(wf_id, workflow)
            workflows[wf_id] = workflow
            node_count = len([n for n in workflow["nodes"] if n["type"] != "n8n-nodes-base.stickyNote"])
            total_nodes += node_count
            print(f"  Built {wf_id}: {node_count} nodes -> {output_path.name}")
        except Exception as e:
            print(f"  ERROR building {wf_id}: {e}")
            continue

    print(f"\nTotal: {len(workflows)} workflows, {total_nodes} nodes")

    if parsed.action == "build":
        print(f"\nJSON files saved to: {OUTPUT_DIR}")
        print("Run with 'deploy' to push to n8n.")
        return

    # Deploy / Activate
    if parsed.action in ("deploy", "activate"):
        _deploy_workflows(workflows, activate=parsed.action == "activate")


def _deploy_workflows(
    workflows: dict[str, dict[str, Any]],
    activate: bool = False,
) -> None:
    """Deploy workflows to n8n Cloud."""
    try:
        from config_loader import load_config
        from n8n_client import N8nClient
    except ImportError:
        print("ERROR: config_loader or n8n_client not found in tools/")
        sys.exit(1)

    config = load_config()
    api_key = config["api_keys"]["n8n"]
    base_url = config["n8n"]["base_url"]

    print(f"\nConnecting to {base_url}...")

    with N8nClient(
        base_url,
        api_key,
        timeout=config["n8n"].get("timeout_seconds", 30),
        cache_dir=config["paths"]["cache_dir"],
    ) as client:
        health = client.health_check()
        if not health["connected"]:
            print(f"ERROR: Cannot connect: {health.get('error')}")
            sys.exit(1)
        print("Connected!")

        # Get existing workflows for name matching
        existing_wfs = client.list_workflows()
        name_map = {wf["name"]: wf["id"] for wf in existing_wfs}

        deployed_ids: dict[str, str] = {}

        for wf_id, workflow in workflows.items():
            wf_name = workflow["name"]
            print(f"\nDeploying {wf_id} ({wf_name})...")

            payload = {
                "name": wf_name,
                "nodes": workflow["nodes"],
                "connections": workflow["connections"],
                "settings": workflow["settings"],
            }

            if wf_name in name_map:
                existing_id = name_map[wf_name]
                result = client.update_workflow(existing_id, payload)
                deployed_ids[wf_id] = result.get("id", existing_id)
                print(f"  Updated (ID: {deployed_ids[wf_id]})")
            else:
                result = client.create_workflow(payload)
                deployed_ids[wf_id] = result.get("id", "")
                print(f"  Created (ID: {deployed_ids[wf_id]})")

            if activate and deployed_ids.get(wf_id):
                client.activate_workflow(deployed_ids[wf_id])
                print(f"  Activated!")

        # Print summary
        print("\n" + "=" * 60)
        print("DEPLOYMENT SUMMARY")
        print("=" * 60)
        for wf_id, n8n_id in deployed_ids.items():
            status = "ACTIVE" if activate else "DEPLOYED"
            print(f"  {wf_id}: {n8n_id} [{status}]")

        # Save deployed IDs for config reference
        ids_file = OUTPUT_DIR / "deployed_ids.json"
        with open(ids_file, "w") as f:
            json.dump(deployed_ids, f, indent=2)
        print(f"\nDeployed IDs saved to: {ids_file}")


def _show_status() -> None:
    """Show current deployment status."""
    ids_file = OUTPUT_DIR / "deployed_ids.json"
    if not ids_file.exists():
        print("No deployments found. Run 'deploy' first.")
        return

    with open(ids_file) as f:
        deployed_ids = json.load(f)

    print("\nDeployed Workflows:")
    for wf_id, n8n_id in deployed_ids.items():
        entry = WORKFLOW_REGISTRY.get(wf_id, {})
        name = entry.get("name", "Unknown")
        print(f"  {wf_id}: {n8n_id} — {name}")

    print(f"\nTotal: {len(deployed_ids)} workflows deployed")

    # Check for missing
    missing = [wf for wf in WORKFLOW_REGISTRY if wf not in deployed_ids]
    if missing:
        print(f"\nNot yet deployed: {', '.join(missing)}")

    print("\nRecommended activation order:")
    for phase in sorted(set(e["phase"] for e in WORKFLOW_REGISTRY.values())):
        wfs = [k for k, v in WORKFLOW_REGISTRY.items() if v["phase"] == phase]
        print(f"  Phase {phase}: {', '.join(wfs)}")


if __name__ == "__main__":
    main()
