"""
Accounting Department - Master Workflow Builder & Deployer

Builds all Accounting Department workflows as n8n workflow JSON files,
and optionally deploys them to the n8n instance. Can build individual
workflows, all workflows separately, or a single combined workflow.

Workflows:
    WF-01: Sales & Invoicing (AR)
    WF-02: Collections & Follow-ups
    WF-03: Payments & Reconciliation
    WF-04: Supplier Bills (AP)
    WF-05: Month-End Close
    WF-06: Master Data & Audit
    WF-07: Exception Handler

Usage:
    python tools/deploy_accounting_dept.py build              # Build all workflow JSONs
    python tools/deploy_accounting_dept.py build wf01         # Build WF-01 only
    python tools/deploy_accounting_dept.py build combined     # Build combined single workflow
    python tools/deploy_accounting_dept.py deploy             # Build + Deploy (inactive)
    python tools/deploy_accounting_dept.py activate           # Build + Deploy + Activate
"""

import json
import sys
import uuid
import os
import importlib
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Add tools dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# ── Airtable IDs (for validation) ───────────────────────────
AIRTABLE_BASE_ID = os.getenv("ACCOUNTING_AIRTABLE_BASE_ID", "REPLACE_WITH_BASE_ID")

# ── Module Imports ───────────────────────────────────────────
# Each wfXX module exposes build_nodes() and build_connections()

def _import_wf(module_name):
    """Dynamically import a workflow module."""
    return importlib.import_module(module_name)


# ── Workflow Registry ────────────────────────────────────────

WORKFLOW_REGISTRY = {
    "wf01": {
        "module": "deploy_accounting_wf01",
        "name": "Accounting Dept - Sales & Invoicing (WF-01)",
        "filename": "wf01_sales_invoicing.json",
        "description": "Invoice generation, Xero sync, PDF + email delivery",
    },
    "wf02": {
        "module": "deploy_accounting_wf02",
        "name": "Accounting Dept - Collections & Follow-ups (WF-02)",
        "filename": "wf02_collections.json",
        "description": "Overdue invoice reminders, multi-channel, dispute handling",
    },
    "wf03": {
        "module": "deploy_accounting_wf03",
        "name": "Accounting Dept - Payments & Reconciliation (WF-03)",
        "filename": "wf03_payments_reconciliation.json",
        "description": "Stripe/PayFast capture, AI matching, receipt sending",
    },
    "wf04": {
        "module": "deploy_accounting_wf04",
        "name": "Accounting Dept - Supplier Bills AP (WF-04)",
        "filename": "wf04_supplier_bills.json",
        "description": "Email bill intake, AI extraction, approval routing, Xero sync",
    },
    "wf05": {
        "module": "deploy_accounting_wf05",
        "name": "Accounting Dept - Month End Close (WF-05)",
        "filename": "wf05_month_end_close.json",
        "description": "Aged receivables/payables, AI summary, management pack",
    },
    "wf06": {
        "module": "deploy_accounting_wf06",
        "name": "Accounting Dept - Master Data & Audit (WF-06)",
        "filename": "wf06_master_data_audit.json",
        "description": "Config cache, audit log webhook, customer CRUD",
    },
    "wf07": {
        "module": "deploy_accounting_wf07",
        "name": "Accounting Dept - Exception Handler (WF-07)",
        "filename": "wf07_exception_handling.json",
        "description": "Task queue, overdue escalation, approval webhook",
    },
}


# ══════════════════════════════════════════════════════════════
# COMBINED WORKFLOW BUILDER
# ══════════════════════════════════════════════════════════════

def build_combined_nodes_and_connections():
    """
    Build a single combined workflow containing all 7 sub-workflows.

    Each sub-workflow's nodes are offset on the canvas (Y-axis) so they
    don't overlap. Connections are merged — since node names are unique
    across workflows (each is prefixed with its context), they combine
    cleanly.
    """
    all_nodes = []
    all_connections = {}

    # Canvas layout: stack workflows vertically with spacing
    y_offsets = {
        "wf06": 0,       # Master Data (utility — top)
        "wf01": 1200,    # Sales & Invoicing
        "wf03": 2600,    # Payments & Reconciliation
        "wf02": 4000,    # Collections & Follow-ups
        "wf04": 5400,    # Supplier Bills
        "wf05": 6800,    # Month-End Close
        "wf07": 8200,    # Exception Handler
    }

    # Add section sticky notes for visual organization
    section_colors = {
        "wf06": 4,  # Blue
        "wf01": 2,  # Green
        "wf03": 6,  # Purple
        "wf02": 3,  # Yellow
        "wf04": 5,  # Red
        "wf05": 1,  # Orange
        "wf07": 7,  # Pink
    }

    for wf_id, reg in WORKFLOW_REGISTRY.items():
        y_offset = y_offsets[wf_id]

        # Add section sticky note
        all_nodes.append({
            "parameters": {
                "content": f"## {reg['name']}\n{reg['description']}",
                "width": 1600,
                "height": 200,
                "color": section_colors.get(wf_id, 1),
            },
            "id": str(uuid.uuid4()),
            "name": f"Note - {wf_id.upper()}",
            "type": "n8n-nodes-base.stickyNote",
            "position": [100, y_offset - 100],
            "typeVersion": 1,
        })

        # Import module and build nodes
        mod = _import_wf(reg["module"])
        nodes = mod.build_nodes()
        connections = mod.build_connections()

        # Offset node Y positions
        for node in nodes:
            if "position" in node:
                node["position"] = [
                    node["position"][0],
                    node["position"][1] + y_offset,
                ]

        all_nodes.extend(nodes)
        all_connections.update(connections)

    return all_nodes, all_connections


# ══════════════════════════════════════════════════════════════
# WORKFLOW ASSEMBLY
# ══════════════════════════════════════════════════════════════

def build_workflow(wf_id):
    """Assemble a complete workflow JSON."""
    if wf_id == "combined":
        nodes, connections = build_combined_nodes_and_connections()
        name = "Accounting Dept - All Workflows (Combined)"
    elif wf_id in WORKFLOW_REGISTRY:
        mod = _import_wf(WORKFLOW_REGISTRY[wf_id]["module"])
        nodes = mod.build_nodes()
        connections = mod.build_connections()
        name = WORKFLOW_REGISTRY[wf_id]["name"]
    else:
        valid = list(WORKFLOW_REGISTRY.keys()) + ["combined"]
        raise ValueError(f"Unknown workflow: {wf_id}. Valid: {', '.join(valid)}")

    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "pinData": {},
        "tags": [],
    }


def save_workflow(wf_id, workflow):
    """Save workflow JSON to file."""
    if wf_id == "combined":
        filename = "combined_all_workflows.json"
    else:
        filename = WORKFLOW_REGISTRY[wf_id]["filename"]

    output_dir = Path(__file__).parent.parent / "workflows" / "accounting-dept"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)

    return output_path


def print_workflow_stats(wf_id, workflow):
    """Print workflow statistics."""
    all_nodes = workflow["nodes"]
    func_nodes = [n for n in all_nodes if n["type"] != "n8n-nodes-base.stickyNote"]
    note_nodes = [n for n in all_nodes if n["type"] == "n8n-nodes-base.stickyNote"]
    conn_count = len(workflow["connections"])

    print(f"  Name: {workflow['name']}")
    print(f"  Nodes: {len(func_nodes)} functional + {len(note_nodes)} sticky notes")
    print(f"  Connections: {conn_count}")


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    action = args[0] if args else "build"
    target = args[1] if len(args) > 1 else "all"

    print("=" * 60)
    print("ACCOUNTING DEPARTMENT - WORKFLOW BUILDER")
    print("=" * 60)

    # Determine which workflows to build
    valid_wfs = list(WORKFLOW_REGISTRY.keys()) + ["combined"]
    if target == "all":
        # Build all individual + combined
        workflow_ids = list(WORKFLOW_REGISTRY.keys()) + ["combined"]
    elif target in valid_wfs:
        workflow_ids = [target]
    else:
        print(f"ERROR: Unknown target '{target}'. Use: all, {', '.join(valid_wfs)}")
        sys.exit(1)

    # Check Airtable config
    if "REPLACE" in AIRTABLE_BASE_ID:
        print()
        print("WARNING: Airtable IDs not configured!")
        print("  Run setup_accounting_airtable.py first, then set these env vars:")
        print("  - ACCOUNTING_AIRTABLE_BASE_ID")
        print("  - ACCOUNTING_TABLE_CUSTOMERS")
        print("  - ACCOUNTING_TABLE_SUPPLIERS")
        print("  - ACCOUNTING_TABLE_PRODUCTS_SERVICES")
        print("  - ACCOUNTING_TABLE_INVOICES")
        print("  - ACCOUNTING_TABLE_PAYMENTS")
        print("  - ACCOUNTING_TABLE_SUPPLIER_BILLS")
        print("  - ACCOUNTING_TABLE_TASKS")
        print("  - ACCOUNTING_TABLE_AUDIT_LOG")
        print("  - ACCOUNTING_TABLE_SYSTEM_CONFIG")
        print()
        if action in ("deploy", "activate"):
            print("Cannot deploy with placeholder IDs. Aborting.")
            sys.exit(1)
        print("Continuing build with placeholder IDs (for preview only)...")
        print()

    # Build workflows
    workflows = {}
    for wf_id in workflow_ids:
        print(f"\nBuilding {wf_id}...")
        try:
            workflow = build_workflow(wf_id)
            output_path = save_workflow(wf_id, workflow)
            workflows[wf_id] = workflow
            print_workflow_stats(wf_id, workflow)
            print(f"  Saved to: {output_path}")
        except Exception as e:
            print(f"  ERROR building {wf_id}: {e}")
            if action in ("deploy", "activate"):
                print("  Aborting deployment due to build error.")
                sys.exit(1)

    if action == "build":
        print("\n" + "=" * 60)
        print("BUILD COMPLETE")
        print("=" * 60)
        print(f"\nBuilt {len(workflows)} workflow(s):")
        for wf_id in workflows:
            label = "Combined All" if wf_id == "combined" else WORKFLOW_REGISTRY[wf_id]["name"]
            print(f"  {wf_id}: {label}")
        print("\nRun with 'deploy' to push to n8n.")
        return

    # Deploy to n8n
    if action in ("deploy", "activate"):
        from config_loader import load_config
        from n8n_client import N8nClient

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
                print(f"  ERROR: Cannot connect to n8n: {health.get('error')}")
                sys.exit(1)
            print("  Connected!")

            deployed_ids = {}

            for wf_id, workflow in workflows.items():
                print(f"\nDeploying {wf_id}...")

                # Check if workflow already exists (by name)
                existing = None
                try:
                    all_wfs = client.list_workflows()
                    for wf in all_wfs:
                        if wf["name"] == workflow["name"]:
                            existing = wf
                            break
                except Exception:
                    pass

                if existing:
                    # Update existing
                    update_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.update_workflow(existing["id"], update_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Updated: {result.get('name')} (ID: {result.get('id')})")
                else:
                    # Create new — only send fields the n8n API accepts
                    create_payload = {
                        "name": workflow["name"],
                        "nodes": workflow["nodes"],
                        "connections": workflow["connections"],
                        "settings": workflow["settings"],
                    }
                    result = client.create_workflow(create_payload)
                    deployed_ids[wf_id] = result.get("id")
                    print(f"  Created: {result.get('name')} (ID: {result.get('id')})")

                if action == "activate" and deployed_ids.get(wf_id):
                    if wf_id == "combined":
                        print(f"  Skipping activation for combined (backup only — duplicate triggers)")
                    else:
                        print(f"  Activating {wf_id}...")
                        client.activate_workflow(deployed_ids[wf_id])
                        print(f"  Activated!")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Workflows:")
    for wf_id in workflow_ids:
        if wf_id == "combined":
            print(f"  combined: Accounting Dept - All Workflows (Combined)")
        else:
            print(f"  {wf_id}: {WORKFLOW_REGISTRY[wf_id]['name']}")

    print()
    print("Next steps:")
    print("  1. Open each workflow in n8n UI to verify node connections")
    print("  2. Verify credential bindings (Xero OAuth2, Airtable, Gmail, Stripe)")
    print("  3. Run setup_accounting_airtable.py --seed to populate config + products")
    print("  4. Test WF-06: POST to /accounting/audit-log and /accounting/customer")
    print("  5. Test WF-01: Create Draft invoice in Airtable -> trigger -> verify Xero + email")
    print("  6. Test WF-03: Stripe test payment -> verify matching + receipt")
    print("  7. Test WF-02: Seed overdue invoices -> trigger -> verify reminder emails")
    print("  8. Test WF-04: Send bill PDF to accounts inbox -> verify AI extraction")
    print("  9. Test WF-05: Manual trigger -> verify month-end report generation")
    print(" 10. Test WF-07: Click approve/reject links -> verify task resolution")
    print(" 11. Once verified, activate all schedule triggers")


if __name__ == "__main__":
    main()
